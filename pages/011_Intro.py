from __future__ import annotations

import hashlib
import time

import streamlit as st

from infra.app_context import (
    get_active_session,
    get_authenticator,
    get_auth_runtime_config,
    get_notion_repo,
    load_config,
)
from infra.app_state import (
    ensure_auth,
    ensure_session_state,
    mint_anon_token,
    remember_access,
    set_session,
)
from infra.event_logger import log_event, get_module_logger
from infra.event_logger import perf_timer, log_perf
from models.catalog import questions_for_session
from repositories.base import InteractionRepository
from repositories.interaction_repo import (
    NotionInteractionRepository,
)
from services.presence import touch_player_presence

from ui import (
    apply_auth_input_form_styles,
    apply_theme,
    render_orientation_sidebar,
    set_page,
    sidebar_debug_state,
    update_sidebar_task,
)

PRE_SIGNAL_ID = "ORGANISATION_SIGNAL"
CONTACT_METHOD_ID = "CONTACT_METHOD"
FINAL_FEEDBACK_ID = "FINAL_FEEDBACK"
EMOTION_QUESTION_IDS = {
    "ARRIVAL_EMOTION",
    "ENVIRONMENT_CHANGE_EMOTION",
    "SOCIETAL_CHANGE_EMOTION",
}
PRE_LOBBY_RADIO_IDS = {
    "COLLABORATION_READINESS",
    "PERSONAL_AGENCY",
    CONTACT_METHOD_ID,
}
PRE_SIGNAL_TEXT_ID = "pre_lobby_signal_v0"
PRE_LOBBY_MODULE_TEXT_ID = "pre_lobby_module_v1"
AUTH_LOGGER = get_module_logger("iceicebaby.auth")
INTRO_STEP_KEY = "intro_step"
INTRO_ANIMATE_KEY = "intro_animate_text"
INTRO_COMPLETED_KEY = "intro_seen_once"


def _intro_stream_timing_config() -> tuple[float, dict[str, float]]:
    cfg = load_config().get("intro", {}).get("streaming", {})

    base_delay_raw = cfg.get("base_delay_s", 0.04)
    try:
        base_delay_s = max(0.001, float(base_delay_raw))
    except Exception:
        base_delay_s = 0.04

    raw_coef = cfg.get("punctuation_pause_coef", {}) or {}

    def _coef(name: str, default: float) -> float:
        try:
            return max(1.0, float(raw_coef.get(name, default)))
        except Exception:
            return default

    punctuation_coef = {
        ",": _coef("comma", 1.8),
        ";": _coef("semicolon", 2.0),
        ":": _coef("colon", 2.0),
        ".": _coef("period", 2.4),
        "!": _coef("exclamation", 2.4),
        "?": _coef("question", 2.4),
    }
    return base_delay_s, punctuation_coef


def _stream_writer(text: str, delay_s: float, punctuation_coef: dict[str, float]):
    words = text.split(" ")
    for i, word in enumerate(words):
        if i == 0:
            yield word
        else:
            yield " " + word
        trailing = word.rstrip()[-1:] if word else ""
        coef = punctuation_coef.get(trailing, 1.0)
        time.sleep(delay_s * coef)


def _render_streamed_paragraph(text: str, key: str, animate: bool = True) -> None:
    done_key = f"intro_stream_done:{key}"
    if not animate or st.session_state.get(done_key):
        st.markdown(text)
        return
    base_delay_s, punctuation_coef = _intro_stream_timing_config()
    st.write_stream(_stream_writer(text, base_delay_s, punctuation_coef))
    st.session_state[done_key] = True


def _build_interaction_repository(notion_repo) -> tuple[InteractionRepository, str]:
    if not notion_repo:
        raise ValueError("Notion repository is unavailable.")
    notion_cfg = st.secrets.get("notion", {})
    db_id = (
        notion_cfg.get("ice_interaction_responses_db_id")
        or notion_cfg.get("interaction_responses_db_id")
        or notion_cfg.get("ice_responses_db_id")
        or ""
    )
    if not db_id:
        raise ValueError(
            "Missing Database secret in [notion]: ice_interaction_responses_db_id or ice_responses_db_id"
        )
    return NotionInteractionRepository(notion_repo, str(db_id)), "notion"


def _render_first_signal_step(repo, authenticator) -> None:
    auth_cfg = get_auth_runtime_config()
    key_hash_prefix = hashlib.sha256(
        auth_cfg["cookie_key"].encode("utf-8")
    ).hexdigest()[:12]
    raw_token = authenticator.cookie_controller.get_cookie()
    cookie_username = raw_token.get("username") if isinstance(raw_token, dict) else None
    cookie_player_exists = bool(
        repo.get_player_by_id(cookie_username) if repo and cookie_username else False
    )
    session_auth_status = st.session_state.get("authentication_status")
    if not raw_token:
        auth_diagnosis = "No auth cookie detected."
    elif not cookie_username:
        auth_diagnosis = "Cookie present but missing username payload."
    elif not cookie_player_exists:
        auth_diagnosis = "Cookie present, but username is not found in player records."
    elif session_auth_status is True:
        auth_diagnosis = "Cookie present and mapped to an active authenticated session."
    else:
        auth_diagnosis = (
            "Cookie present and user exists, but this run is not authenticated yet. "
            "This can happen after an invalid login attempt or stale session state."
        )

    with st.sidebar.expander("Debug: Auth cookie", expanded=False):
        st.code(
            (
                f"cookie_source={auth_cfg['source']}\n"
                f"cookie_name={auth_cfg['cookie_name']}\n"
                f"cookie_expiry_days={auth_cfg['cookie_expiry_days']}\n"
                f"cookie_key_len={len(auth_cfg['cookie_key'])}\n"
                f"cookie_key_sha256_prefix={key_hash_prefix}\n"
                f"default_session_code={auth_cfg['default_session_code']}\n"
                f"cookie_present={bool(raw_token)}\n"
                f"cookie_username={cookie_username or '<missing>'}\n"
                f"cookie_user_exists_in_repo={cookie_player_exists}\n"
                f"session_authentication_status={session_auth_status}"
            )
        )
        st.caption(f"Diagnosis: {auth_diagnosis}")

    current_auth = bool(st.session_state.get("authentication_status"))
    if current_auth:
        name = st.session_state.get("name")
        authentication_status = st.session_state.get("authentication_status")
    else:
        apply_auth_input_form_styles(main_font_rem=3.0, input_height_em=2.0)
        name, authentication_status, _ = ensure_auth(
            authenticator,
            callback=remember_access,
            key="intro-access-key-login",
            location="main",
        )

    if authentication_status:
        display_name = name or st.session_state.get("player_name") or "collaborator"
        prev_auth = st.session_state.get("_prev_auth_status")
        if prev_auth is not True:
            ok, err = touch_player_presence(
                str(st.session_state.get("player_page_id", "")),
                page="intro",
                session_slug=str(st.session_state.get("session_label", "")),
            )
            if not ok:
                st.toast(f"Presence update failed: {err}", icon="⚠️")
            log_event(
                module="iceicebaby.auth",
                event_type="login_success",
                player_id=str(st.session_state.get("player_page_id", "")),
                session_id=str(st.session_state.get("session_id", "")),
                metadata={"page": "011_Intro"},
            )
        st.session_state["_prev_auth_status"] = True
        hello_key = f"intro_hello_shown:{st.session_state.get('player_page_id') or display_name}"
        if not st.session_state.get(hello_key, False):
            st.success(f"Hello {display_name}.")
            st.session_state[hello_key] = True

        session = None
        if not st.session_state.get("session_id"):
            with perf_timer("iceicebaby.auth", "active_session_lookup", page="011_Intro"):
                session = get_active_session(repo)
            if session:
                set_session(session.get("id", ""), session.get("session_code", "Session"))
        session_id = st.session_state.get("session_id", "")
        player_page_id = st.session_state.get("player_page_id", "")
        salt = st.secrets.get("anon_salt", "iceicebaby")
        anon_token = mint_anon_token(
            st.session_state.get("session_id", ""),
            st.session_state.get("player_access_key", ""),
            salt,
        )
        st.session_state["anon_token"] = anon_token
        current_session_code = "GLOBAL-SESSION"
        t_questions = time.perf_counter()
        pre_lobby_questions = sorted(
            [
                q
                for q in questions_for_session(current_session_code)
                if q.visible_before_lobby and q.qtype != "control"
            ],
            key=lambda q: (q.order, q.id),
        )
        log_perf(
            "iceicebaby.responses",
            "pre_lobby_questions_select",
            (time.perf_counter() - t_questions) * 1000.0,
            session=current_session_code,
            count=len(pre_lobby_questions),
            mode="fixed_set",
        )
        pre_lobby_signature = (
            f"{session_id}:{player_page_id}:"
            f"{','.join(q.id for q in pre_lobby_questions)}"
        )
        module_done_key = f"pre_lobby_submitted:{pre_lobby_signature}"
        pre_signal_submitted = bool(st.session_state.get(module_done_key, False))

        if pre_lobby_questions and not pre_signal_submitted:
            ui_sig_key = "pre_lobby_ui_sig"
            ui_idx_key = "pre_lobby_ui_idx"
            ui_answers_key = "pre_lobby_ui_answers"
            current_ui_sig = (
                f"{pre_lobby_signature}:{','.join(q.id for q in pre_lobby_questions)}"
            )
            if st.session_state.get(ui_sig_key) != current_ui_sig:
                st.session_state[ui_sig_key] = current_ui_sig
                st.session_state[ui_idx_key] = 0
                st.session_state[ui_answers_key] = {}

            answers: dict[str, dict[str, str | int | None]] = st.session_state.get(
                ui_answers_key, {}
            )

            def _is_valid(qid: str) -> bool:
                answer = answers.get(qid, {})
                choice_val = answer.get("choice", "")
                if qid == CONTACT_METHOD_ID:
                    choice_text = str(choice_val or "").strip().lower()
                    if not choice_text:
                        return False
                    if (
                        "dont want to be in touch" in choice_text
                        or "don't want to be in touch" in choice_text
                    ):
                        return True
                    return bool(str(answer.get("contact_value", "") or "").strip())
                if qid == FINAL_FEEDBACK_ID:
                    return bool(str(choice_val or "").strip())
                if isinstance(choice_val, list):
                    return len(choice_val) > 0
                return str(choice_val or "").strip() != ""

            def _signal_score(choice_val: str | list[str]) -> int | None:
                if not isinstance(choice_val, str):
                    return None
                txt = choice_val.strip().lower()
                if txt.startswith("yes"):
                    return 1
                if txt.startswith("no"):
                    return -1
                if "maybe" in txt:
                    return 0
                return None

            total = len(pre_lobby_questions)
            idx = min(st.session_state.get(ui_idx_key, 0), max(total - 1, 0))
            st.session_state[ui_idx_key] = idx
            q = pre_lobby_questions[idx]
            progress_slot = st.empty()
            update_sidebar_task(f"Question {idx + 1}/{total}: {q.id}")

            st.markdown(f"### {q.prompt}")
            if q.short_description:
                st.caption(q.short_description)
            if q.id in EMOTION_QUESTION_IDS:
                st.caption("Multiple choices are possible.")

            comment_existing = str(answers.get(q.id, {}).get("comment", "") or "")
            contact_existing = str(answers.get(q.id, {}).get("contact_value", "") or "")
            comment = comment_existing
            contact_value = contact_existing
            choice: str | list[str] = ""

            if q.id == FINAL_FEEDBACK_ID:
                rating = st.feedback(
                    "faces",
                    key=f"pre-lobby-feedback-intro-{q.id}",
                )
                choice = "" if rating is None else f"faces:{int(rating)}"
                comment = st.text_area(
                    "Optional comment",
                    value=comment_existing,
                    placeholder="Share one line of feedback",
                    key=f"pre-lobby-feedback-comment-intro-{q.id}",
                )
            elif q.depth == 0 or q.id in PRE_LOBBY_RADIO_IDS:
                options = ["Select an option"] + (q.options or [])
                existing_choice = str(answers.get(q.id, {}).get("choice", "") or "")
                selected_idx = (
                    options.index(existing_choice) if existing_choice in options else 0
                )
                selected = st.radio(
                    "Response",
                    options,
                    index=selected_idx,
                    key=f"pre-lobby-choice-intro-{q.id}",
                    label_visibility="collapsed",
                )
                choice: str | list[str] = (
                    "" if selected == "Select an option" else selected
                )
            else:
                existing_choice_list = answers.get(q.id, {}).get("choice", [])
                if not isinstance(existing_choice_list, list):
                    existing_choice_list = []
                choice = (
                    st.pills(
                        "Select one or more",
                        q.options or [],
                        selection_mode="multi",
                        default=existing_choice_list,
                        key=f"pre-lobby-choice-intro-{q.id}",
                        label_visibility="collapsed",
                    )
                    or []
                )
            maybe_selected = False
            other_selected = False
            if isinstance(choice, list):
                maybe_selected = any("maybe" in str(x).lower() for x in choice)
                other_selected = "Other" in choice
            else:
                maybe_selected = "maybe" in str(choice).lower()
                other_selected = choice == "Other"

            if q.id == CONTACT_METHOD_ID and isinstance(choice, str) and choice:
                choice_txt = choice.strip().lower()
                if choice_txt == "email":
                    contact_value = st.text_input(
                        "Email",
                        value=contact_existing,
                        placeholder="name@example.org",
                        key=f"pre-lobby-contact-email-intro-{q.id}",
                    ).strip()
                elif (
                    "dont want to be in touch" in choice_txt
                    or "don't want to be in touch" in choice_txt
                ):
                    contact_value = ""
                else:
                    contact_value = st.text_input(
                        "Phone",
                        value=contact_existing,
                        placeholder="+33 ...",
                        key=f"pre-lobby-contact-phone-intro-{q.id}",
                    ).strip()
            elif q.id in EMOTION_QUESTION_IDS and other_selected:
                comment = st.text_input(
                    "If you selected Other, specify",
                    value=comment_existing,
                    placeholder="Your emotion",
                    key=f"pre-lobby-other-intro-{q.id}",
                )
            elif q.show_text_field and (maybe_selected or other_selected):
                comment = st.text_input(
                    "Condition or comment",
                    value=comment_existing,
                    placeholder=q.placeholder or "Your condition or comment",
                    key=f"pre-lobby-comment-intro-{q.id}",
                )
            answers[q.id] = {
                "choice": choice,
                "score": _signal_score(choice) if q.id == PRE_SIGNAL_ID else None,
                "comment": comment.strip(),
                "contact_value": contact_value,
                "type": "pre_signal" if q.depth == 0 else "pre_lobby",
                "question_type": "signal"
                if q.depth == 0
                else (
                    "feedback"
                    if q.id == FINAL_FEEDBACK_ID
                    else ("multi" if isinstance(choice, list) else "single")
                ),
                "page_index": idx + 1,
                "depth": q.depth,
            }
            st.session_state[ui_answers_key] = answers
            answered = sum(1 for item in pre_lobby_questions if _is_valid(item.id))
            st.session_state["sidebar_responses_submitted"] = answered
            render_orientation_sidebar(
                session_name=str(st.session_state.get("session_title") or "GLOBAL SESSION"),
                question_index=idx + 1,
                question_total=total,
                responses_submitted=answered,
            )
            with progress_slot.container():
                st.progress(answered / total if total else 0.0)
                st.caption(f"Progress: {answered} / {total} answered")

            back_col, next_col, submit_col = st.columns(3)
            with back_col:
                if st.button(
                    "Back",
                    width="stretch",
                    disabled=idx == 0,
                    key="pre-lobby-back-intro",
                ):
                    update_sidebar_task("Back", done=True)
                    st.session_state[ui_idx_key] = max(0, idx - 1)
                    st.rerun()
            with next_col:
                if st.button(
                    "Next",
                    width="stretch",
                    disabled=idx >= total - 1 or not _is_valid(q.id),
                    key="pre-lobby-next-intro",
                ):
                    update_sidebar_task("Next", done=True)
                    st.session_state[ui_idx_key] = min(total - 1, idx + 1)
                    st.rerun()
            with submit_col:
                submit_module = st.button(
                    "Send signal again" if pre_signal_submitted else "Send signal",
                    type="primary",
                    width="stretch",
                    disabled=idx != total - 1 or answered < total,
                    key="pre-lobby-submit-intro",
                )

            if submit_module:
                if not session_id:
                    st.error("No active session found. Please refresh and try again.")
                    AUTH_LOGGER.warning("active session not found on signal submit")
                    log_event(
                        module="iceicebaby.responses",
                        event_type="response_save_error",
                        page="Intro",
                        player_id=str(player_page_id or ""),
                        session_id=str(session_id),
                        item_id=PRE_SIGNAL_ID,
                        status="error",
                        metadata={"reason": "active_session_missing"},
                        level="ERROR",
                    )
                else:
                    signal_repo: InteractionRepository | None = None
                    try:
                        with perf_timer(
                            "iceicebaby.responses",
                            "interaction_repo_init",
                            page="011_Intro",
                        ):
                            signal_repo, _ = _build_interaction_repository(repo)
                    except Exception as exc:
                        storage_error = str(exc)
                        AUTH_LOGGER.error("schema mismatch: %s", storage_error)
                        st.error(
                            "Interaction storage is not available in Notion. "
                            f"Fix Database settings/schema to proceed. Details: {storage_error}"
                        )
                        log_event(
                            module="iceicebaby.responses",
                            event_type="response_save_error",
                            page="Intro",
                            player_id=str(player_page_id or ""),
                            session_id=str(session_id),
                            item_id=PRE_SIGNAL_ID,
                            status="error",
                            metadata={"reason": "interaction_repo_unavailable"},
                            level="ERROR",
                        )
                        return
                    with perf_timer(
                        "iceicebaby.responses",
                        "pre_lobby_save_batch",
                        session=session_id,
                        count=len(pre_lobby_questions),
                    ):
                        for item in pre_lobby_questions:
                            signal_repo.save_response(
                                session_id=session_id,
                                player_id=player_page_id or None,
                                question_id=item.id,
                                value=answers.get(item.id, {}),
                                text_id=PRE_LOBBY_MODULE_TEXT_ID
                                if item.depth >= 1
                                else PRE_SIGNAL_TEXT_ID,
                                device_id=anon_token,
                            )
                    ok, err = touch_player_presence(
                        str(player_page_id or ""),
                        page="choices_submit",
                        session_slug=str(st.session_state.get("session_label", "")),
                    )
                    if not ok:
                        st.toast(f"Presence update failed: {err}", icon="⚠️")
                    st.session_state[module_done_key] = True
                    pre_signal_submitted = True
                    update_sidebar_task("Signal submitted", done=True)
                    log_event(
                        module="iceicebaby.responses",
                        event_type="signal_submit",
                        player_id=str(player_page_id or ""),
                        session_id=str(session_id),
                        item_id=PRE_SIGNAL_ID,
                        value_label=str(
                            answers.get(PRE_SIGNAL_ID, {}).get("choice", "")
                        ),
                        metadata={
                            "answered": answered,
                            "total": total,
                            "mode": "fixed_set",
                        },
                    )
                    st.success("✨ Signal recorded.")
                    st.balloons()
        elif pre_signal_submitted:
            render_orientation_sidebar(
                session_name=str(st.session_state.get("session_title") or "GLOBAL SESSION"),
                responses_submitted=int(st.session_state.get("sidebar_responses_submitted", 0)),
            )
            done_balloon_key = f"{module_done_key}:thankyou_balloons"
            if not st.session_state.get(done_balloon_key, False):
                st.balloons()
                st.session_state[done_balloon_key] = True
            st.success(
                "Thank you for your signal. Your contribution has been recorded and added to the collective stream."
            )
            st.markdown(
                """
Your responses are used in aggregate form to help the group observe shared tendencies, discuss differences, and reflect collectively on possible next steps.
"""
            )
            action_col1, action_col2 = st.columns(2)
            with action_col1:
                st.page_link(
                    "pages/09_Player.py",
                    label="Open your trajectory",
                    width="stretch",
                )
            with action_col2:
                st.page_link(
                    "pages/08_Overview.py",
                    label="Open global visualisation",
                    width="stretch",
                )
        if st.button(
            "Enter lobby",
            type="secondary",
            width="stretch",
            disabled=not pre_signal_submitted,
            key="intro-enter-lobby",
        ):
            update_sidebar_task("Enter lobby", done=True)
            ok, err = touch_player_presence(
                str(player_page_id or ""),
                page="enter_lobby",
                session_slug=str(st.session_state.get("session_label", "")),
            )
            if not ok:
                st.toast(f"Presence update failed: {err}", icon="⚠️")
            log_event(
                module="iceicebaby.sessions",
                event_type="enter_lobby",
                player_id=str(player_page_id or ""),
                session_id=str(session_id),
                metadata={"source_page": "011_Intro"},
            )
            st.switch_page("pages/02_Home.py")
        if not pre_signal_submitted:
            st.warning("Integrate your perspectives before discussing collectively.")
        authenticator.logout(button_name="Logout", location="main")
    elif authentication_status is False:
        st.session_state["_prev_auth_status"] = False
        render_orientation_sidebar(
            session_name=str(st.session_state.get("session_title") or "GLOBAL SESSION"),
        )
    else:
        st.session_state["_prev_auth_status"] = None
        st.info("Connection status: Offline")
        st.caption("Use the access key form above to log in.")
        render_orientation_sidebar(
            session_name=str(st.session_state.get("session_title") or "GLOBAL SESSION"),
        )


def main() -> None:
    set_page()
    apply_theme()
    ensure_session_state()
    sidebar_debug_state()
    log_event(
        module="iceicebaby.sessions",
        event_type="page_view",
        page="Intro",
        player_id=str(st.session_state.get("player_page_id", "")),
        session_id=str(st.session_state.get("session_id", "")),
        device_id=str(st.session_state.get("anon_token", "")),
        status="ok",
    )
    st.session_state.setdefault(INTRO_STEP_KEY, 0)
    st.session_state.setdefault(INTRO_ANIMATE_KEY, True)

    t_repo = time.perf_counter()
    repo = get_notion_repo()
    log_perf(
        "iceicebaby.auth",
        "intro_repo_fetch",
        (time.perf_counter() - t_repo) * 1000.0,
        page="011_Intro",
        repo_ready=bool(repo),
    )
    t_auth = time.perf_counter()
    authenticator = get_authenticator(repo)
    log_perf(
        "iceicebaby.auth",
        "intro_authenticator_init",
        (time.perf_counter() - t_auth) * 1000.0,
        page="011_Intro",
    )

    step = int(st.session_state.get(INTRO_STEP_KEY, 0))
    if step == 1:
        st.session_state[INTRO_STEP_KEY] = 2
        st.rerun()
    is_returning = bool(
        st.session_state.get("authentication_status")
        or st.session_state.get("player_page_id")
        or st.session_state.get(INTRO_COMPLETED_KEY)
    )
    if is_returning and step < 2:
        if st.button(
            "Skip intro and go to first signal",
            type="secondary",
            width="stretch",
            key="intro-skip",
        ):
            st.session_state[INTRO_STEP_KEY] = 2
            st.rerun()

    animate = bool(st.session_state.get(INTRO_ANIMATE_KEY, True))
    if step == 0:
        _render_streamed_paragraph(
            "### To act in the Decade of Action for Cryospheric Sciences (2025–2034), we need multiple languages and new coordination experiments.",
            key="step0-p1",
            animate=animate,
        )
        _render_streamed_paragraph(
            "### Acting through transitions is a collective challenge.",
            key="step0-p2",
            animate=animate,
        )
        left, right = st.columns([1, 1.4])
        with left:
            if st.button(
                "Back",
                type="secondary",
                width="stretch",
                key="intro-step0-back",
            ):
                st.switch_page("pages/Splash.py")
        with right:
            if st.button(
                "I would like to explore this",
                type="primary",
                width="stretch",
                key="intro-step0-next",
            ):
                st.session_state[INTRO_STEP_KEY] = 2
                st.rerun()
        return

    st.session_state[INTRO_COMPLETED_KEY] = True
    _render_first_signal_step(repo, authenticator)


if __name__ == "__main__":
    main()
