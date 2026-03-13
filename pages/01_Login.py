from __future__ import annotations

import hashlib
from datetime import datetime

import streamlit as st

from infra.app_context import (
    get_active_session,
    get_authenticator,
    get_auth_runtime_config,
    get_notion_repo,
)
from infra.app_state import (
    ensure_auth,
    ensure_session_state,
    remember_access,
    set_session,
    mint_anon_token,
)
from infra.cryosphere_cracks import CRYOSPHERE_CRACKS, cryosphere_crack_points
from infra.credentials_pdf import build_credentials_pdf
from models.catalog import questions_for_session
from repositories.base import InteractionRepository
from repositories.interaction_repo import (
    NotionInteractionRepository,
)
from services.presence import touch_player_presence

from ui import (
    apply_theme,
    heading,
    microcopy,
    set_page,
    sidebar_debug_state,
    cracks_globe_block,
    display_centered_prompt,
    render_info_block,
)

PRE_SIGNAL_ID = "ORGANISATION_SIGNAL"
PRE_LOBBY_RADIO_IDS = {"COLLABORATION_READINESS", "PERSONAL_AGENCY"}
PRE_SIGNAL_TEXT_ID = "pre_lobby_signal_v0"
PRE_LOBBY_MODULE_TEXT_ID = "pre_lobby_module_v1"
PRE_SIGNAL_SCORE = {
    "Yes — we need to develop collective dynamics": 1,
    "Maybe — depending on conditions": 0,
    "No — for other reasons, stop here": -1,
}


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


def main() -> None:
    set_page()
    apply_theme()
    ensure_session_state()
    sidebar_debug_state()

    heading("<center>Glaciers, Listening to Society</center>")
    st.markdown(
        """
### Developed for the World Day for Glaciers at UNESCO, within the Decade of Action for Cryospheric Sciences (2024-2035).
"""
    )
    st.markdown(
        """
Room XXX, 4pm, March 19, 2026. Organised by: ______, ______, ______, ______, and ______.
"""
    )
    display_centered_prompt("A moment before deciding.")
    st.markdown(
        """
### Transitions in nature rarely announce themselves clearly. Signals accumulate. Tensions build, energy stores. Then systems shift. 
#### Understanding these transitions is a scientific challenge. Acting through them is a collective one.
### To act in the decade Decade of Action for Cryospheric Sciences (2025–2034), we need new languages and new coordination experiments.
        """
    )
    st.divider()
    locations_md = []
    for category, entries in CRYOSPHERE_CRACKS.items():
        regions = ", ".join(entry["Region"] for entry in entries)
        locations_md.append(f"- **{category}**: {regions}")

    render_info_block(
        left_title="Decision signals",
        left_subtitle="collective experiment",
        right_content="\n".join(
            [
                "#### New problems require new forms of interaction. Today we speak through the arts and sciences.",
                "",
                "#### This platform explores how groups perceive signals, exchange perspectives, and form decisions together.",
                "",
                "#### What happens _next_ depends on the signals we generate here.",
                "",
            ]
        ),
    )
    display_centered_prompt("The first signal begins with you.")
    repo = get_notion_repo()
    authenticator = get_authenticator(repo)
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
        name, authentication_status, _ = ensure_auth(
            authenticator,
            callback=remember_access,
            key="access-key-login",
            location="main",
        )

    open_mint = bool(st.session_state.pop("focus_mint_token", False))

    if authentication_status:
        display_name = name or st.session_state.get("player_name") or "collaborator"
        prev_auth = st.session_state.get("_prev_auth_status")
        if prev_auth is not True:
            ok, err = touch_player_presence(
                str(st.session_state.get("player_page_id", "")),
                page="login",
                session_slug=str(st.session_state.get("session_label", "")),
            )
            if not ok:
                st.toast(f"Presence update failed: {err}", icon="⚠️")
        st.session_state["_prev_auth_status"] = True
        # st.success(f"Authentication status: LOGGED IN")
        st.success(
            f"Hello {display_name}. Before entering the lobby, we invite you to send a first signal."
        )
        # st.info(
        #     "Your session cookie is active. You can continue directly to the lobby."
        # )
        session = get_active_session(repo)
        if session:
            set_session(session.get("id", ""), session.get("session_code", "Session"))
        session_id = st.session_state.get("session_id", "")
        player_page_id = st.session_state.get("player_page_id", "")
        signal_repo: InteractionRepository | None = None
        signal_backend = "notion"
        storage_error = ""
        try:
            signal_repo, signal_backend = _build_interaction_repository(repo)
        except Exception as exc:
            storage_error = str(exc)
            st.error(
                "Interaction storage is not available in Notion. "
                f"Fix Database settings/schema to proceed. Details: {storage_error}"
            )
        salt = st.secrets.get("anon_salt", "iceicebaby")
        anon_token = mint_anon_token(
            st.session_state.get("session_id", ""),
            st.session_state.get("player_access_key", ""),
            salt,
        )
        st.session_state["anon_token"] = anon_token
        st.markdown(
            "### This opening module collects the room's first signals: how we arrive, how we feel, and whether we want to continue together."
        )
        st.markdown(
            "#### A short path or a deeper one? You can select the depth of this first module using the slider below."
        )
        pre_lobby_depth = st.slider(
            "Depth controls how far you go.",
            min_value=0,
            max_value=5,
            value=0,
            step=1,
            help="Use the slider to keep the interaction minimal or to explore a few more questions before entering the lobby.",
        )
        st.markdown(
            "At minimal depth (0), you are invited to respond to only one key question. Higher levels unlock a few more short questions on emotion and interpretation."
        )
        current_session_code = (
            str(st.session_state.get("session_title", "") or "").strip()
            or str((session or {}).get("session_code", "") or "").strip()
            or "GLOBAL-SESSION"
        )
        pre_lobby_questions = sorted(
            [
                q
                for q in questions_for_session(current_session_code)
                if q.visible_before_lobby and q.depth <= pre_lobby_depth
            ],
            key=lambda q: (q.depth, q.order, q.id),
        )
        signal_count = sum(1 for q in pre_lobby_questions if q.depth == 0)
        emotional_count = sum(1 for q in pre_lobby_questions if q.depth >= 1)
        st.caption(
            f"Selected depth [{pre_lobby_depth}]: includes "
            f"{signal_count} signal question and {emotional_count} emotional question(s)."
        )
        pre_lobby_signature = (
            f"{session_id}:{player_page_id}:{pre_lobby_depth}:"
            f"{','.join(q.id for q in pre_lobby_questions)}"
        )
        module_done_key = f"pre_lobby_submitted:{pre_lobby_signature}"
        pre_signal_submitted = bool(st.session_state.get(module_done_key, False))
        depth_confirm_key = "pre_lobby_depth_confirm_sig"
        depth_sig = f"{session_id}:{player_page_id}:{pre_lobby_depth}"
        depth_confirmed = st.session_state.get(depth_confirm_key) == depth_sig

        if pre_lobby_questions and not depth_confirmed:
            st.markdown("---")
            if st.button(
                "Continue with selected depth",
                type="secondary",
                use_container_width=True,
                key="pre-lobby-depth-continue",
            ):
                st.session_state[depth_confirm_key] = depth_sig
                st.rerun()
            st.info("Confirm depth first, then continue to the first question.")

        if pre_lobby_questions and depth_confirmed:
            st.markdown("---")
            # st.subheader("Ice breaker")

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
                choice_val = answers.get(qid, {}).get("choice", "")
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

            st.markdown(f"### {q.prompt}")
            if q.short_description:
                st.caption(q.short_description)

            if q.depth == 0 or q.id in PRE_LOBBY_RADIO_IDS:
                options = ["Select an option"] + (q.options or [])
                existing_choice = str(answers.get(q.id, {}).get("choice", "") or "")
                selected_idx = (
                    options.index(existing_choice) if existing_choice in options else 0
                )
                selected = st.radio(
                    "Response",
                    options,
                    index=selected_idx,
                    key=f"pre-lobby-choice-{q.id}",
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
                        key=f"pre-lobby-choice-{q.id}",
                        label_visibility="collapsed",
                    )
                    or []
                )

            comment_existing = str(answers.get(q.id, {}).get("comment", "") or "")
            comment = comment_existing
            maybe_selected = False
            other_selected = False
            if isinstance(choice, list):
                maybe_selected = any("maybe" in str(x).lower() for x in choice)
                other_selected = "Other" in choice
            else:
                maybe_selected = "maybe" in str(choice).lower()
                other_selected = choice == "Other"

            if q.show_text_field and (maybe_selected or other_selected):
                comment = st.text_input(
                    "Condition or comment",
                    value=comment_existing,
                    placeholder=q.placeholder or "Your condition or comment",
                    key=f"pre-lobby-comment-{q.id}",
                )
            answers[q.id] = {
                "choice": choice,
                "score": _signal_score(choice) if q.id == PRE_SIGNAL_ID else None,
                "comment": comment.strip(),
                "type": "pre_signal" if q.depth == 0 else "pre_lobby",
                "question_type": "signal"
                if q.depth == 0
                else ("multi" if isinstance(choice, list) else "single"),
                "page_index": idx + 1,
                "depth": q.depth,
            }
            st.session_state[ui_answers_key] = answers
            answered = sum(1 for item in pre_lobby_questions if _is_valid(item.id))
            st.progress(answered / total if total else 0.0)
            st.caption(f"Progress: {answered} / {total} answered")

            back_col, next_col, submit_col = st.columns(3)
            with back_col:
                if st.button(
                    "Back",
                    use_container_width=True,
                    disabled=idx == 0,
                    key="pre-lobby-back",
                ):
                    st.session_state[ui_idx_key] = max(0, idx - 1)
                    st.rerun()
            with next_col:
                if st.button(
                    "Next",
                    use_container_width=True,
                    disabled=idx >= total - 1 or not _is_valid(q.id),
                    key="pre-lobby-next",
                ):
                    st.session_state[ui_idx_key] = min(total - 1, idx + 1)
                    st.rerun()
            with submit_col:
                submit_module = st.button(
                    "Send signal again" if pre_signal_submitted else "Send signal",
                    type="primary",
                    use_container_width=True,
                    disabled=idx != total - 1 or answered < total,
                    key="pre-lobby-submit",
                )

            if submit_module:
                if not session_id:
                    st.error("No active session found. Please refresh and try again.")
                elif not signal_repo:
                    st.error(
                        "Responses could not be saved because Database interaction storage is unavailable."
                    )
                else:
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
                    # Presence heartbeat for "choices submitted" event.
                    ok, err = touch_player_presence(
                        str(player_page_id or ""),
                        page="choices_submit",
                        session_slug=str(st.session_state.get("session_label", "")),
                    )
                    if not ok:
                        st.toast(f"Presence update failed: {err}", icon="⚠️")
                    st.session_state[module_done_key] = True
                    pre_signal_submitted = True
                    st.success(f"✨ Signal recorded.")
                    st.balloons()
        if st.button(
            "Enter lobby",
            type="secondary",
            use_container_width=True,
            disabled=not pre_signal_submitted,
        ):
            ok, err = touch_player_presence(
                str(player_page_id or ""),
                page="enter_lobby",
                session_slug=str(st.session_state.get("session_label", "")),
            )
            if not ok:
                st.toast(f"Presence update failed: {err}", icon="⚠️")
            st.switch_page("pages/02_Home.py")
        if not pre_signal_submitted:
            st.warning("Send a signal above before entering the lobby.")
        authenticator.logout(button_name="Logout", location="main")
    elif authentication_status is False:
        st.session_state["_prev_auth_status"] = False
    else:
        st.session_state["_prev_auth_status"] = None
        st.info("Authentication status: Offline")
        st.caption("Use the access key form above to log in.")


if __name__ == "__main__":
    main()
