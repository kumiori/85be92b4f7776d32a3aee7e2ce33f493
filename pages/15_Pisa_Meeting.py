from __future__ import annotations

import hashlib
import uuid
from typing import Any, Dict, List

import streamlit as st
import streamlit.components.v1 as components

from conference.context import get_conference_bundle, get_conference_repo
from conference.flow import (
    active_question_steps,
    active_step_sequence,
    build_identity_metadata,
    build_session_payload,
    build_payload_view,
    clear_deferred_field,
    current_step,
    defer_field,
    first_active_question_step,
    get_draft,
    init_flow_state,
    mark_submitted,
    mode_label,
    next_step,
    pending_reflection_fields,
    profile_completion_gaps,
    reset_flow_state,
    set_step,
    should_collect_contact,
    step_is_complete,
    suggested_mode_for_missing_profile_fields,
    update_draft,
)
from conference.models import (
    DEFERRABLE_FIELDS,
    FINGERPRINT_AXES,
    FINGERPRINT_LABELS,
    STEP_COPY,
    STEP_ORDER,
    field_for_step,
    field_option_label_map,
    mode_card_rows,
    question_by_step,
)
from conference.repo import emoji_suffix, resolve_access_key_input
from conference.topology import room_snapshot
from conference.ui import apply_conference_styles, conference_header, summary_card
from infra.key_codec import generate_hex_key, hex_to_emoji, split_emoji_symbols
from ui import set_page, sidebar_debug_state


PAGE_KEY = "complexity"
TEXT_ID = "complexity_session_v2"
IDENTITY_STEP = "identity"
ENTRY_KEY = "conference_entry_mode"
LOGIN_ERROR_KEY = "conference_login_error"
COMPLEXITY_OVERVIEW_PAGE = "pages/17_Pisa_Overview.py"


def _ensure_local_state() -> None:
    init_flow_state()
    st.session_state.setdefault("conference_device_id", uuid.uuid4().hex[:16])
    st.session_state.setdefault(ENTRY_KEY, "")
    st.session_state.setdefault(LOGIN_ERROR_KEY, "")
    st.session_state.setdefault("conference_hide_migration_prompt", False)


def _set_entry_mode(mode: str) -> None:
    st.session_state[ENTRY_KEY] = mode


def _entry_mode() -> str:
    return str(st.session_state.get(ENTRY_KEY, "") or "").strip()


def _clear_login_error() -> None:
    st.session_state[LOGIN_ERROR_KEY] = ""


def _set_login_error(message: str) -> None:
    st.session_state[LOGIN_ERROR_KEY] = message


def _infer_mode(submission: Dict[str, Any]) -> str:
    if submission.get("career_stage"):
        return "deep"
    if (
        submission.get("collaboration_style")
        or submission.get("scientific_home_country")
        or submission.get("complexity_fingerprint")
        or submission.get("open_question")
    ):
        return "standard"
    return "quick"


def _labels_for(field: str, value: Any) -> str:
    if field == "mode":
        return mode_label(str(value or "quick"))
    if field == "scientific_home":
        parts = [
            str(value.get("country") or "").strip(),
            str(value.get("city") or "").strip(),
            str(value.get("institution") or "").strip(),
        ] if isinstance(value, dict) else []
        return " · ".join(part for part in parts if part) or "Not yet defined"
    if field == "complexity_fingerprint":
        if not isinstance(value, dict):
            return "Deferred"
        tokens = [
            f"{FINGERPRINT_LABELS.get(axis, axis.title())} {int(value.get(axis, 0) or 0)}"
            for axis in FINGERPRINT_AXES
        ]
        if all(token.endswith(" 0") for token in tokens):
            return "Deferred"
        return " · ".join(tokens)
    label_map = field_option_label_map(field)
    if isinstance(value, list):
        labels = [label_map.get(str(item), str(item)) for item in value if str(item)]
        return ", ".join(labels) if labels else "None selected"
    if isinstance(value, str):
        return label_map.get(value, value) if value else "No answer"
    return str(value or "No answer")


def _field_label(field: str) -> str:
    labels = {
        "scientific_home_country": "Scientific home",
        "assets": "Assets",
        "collaboration_style": "Collaboration style",
        "complexity_fingerprint": "What gives you confidence?",
        "open_question": "What question keeps you awake?",
    }
    return labels.get(field, field.replace("_", " ").title())


def _step_for_field(field: str) -> str:
    for step in STEP_ORDER:
        if field_for_step(step) == field:
            return step
    if field in {
        "scientific_home_country",
        "scientific_home_city",
        "scientific_home_institution",
    }:
        return "scientific_home"
    return ""


def _resume_at_field(field: str, mode: str | None = None) -> None:
    next_mode = mode or str(get_draft().get("mode") or "standard")
    target_step = _step_for_field(field) or first_active_question_step()
    update_draft(mode=next_mode, submitted=False)
    set_step(target_step)
    _set_entry_mode("new")
    st.rerun()


def _load_submission_for_key(
    repo: Any,
    session_id: str,
    raw_key: str,
) -> tuple[str | None, Dict[str, Any] | None, str]:
    token = str(raw_key or "").strip()
    if not token:
        return None, None, ""
    access_key, error = resolve_access_key_input(getattr(repo, "notion_repo", None), token)
    if not access_key:
        return None, None, str(error or "")
    access_key_hash = repo.access_key_hash(access_key)
    cache_key = f"{session_id}:{access_key_hash}"
    submission = st.session_state.get("conference_submission_cache")
    if st.session_state.get("conference_submission_cache_key") != cache_key:
        submission = repo.latest_submission_by_access_key_hash(
            session_id=session_id,
            access_key_hash=access_key_hash,
        )
        st.session_state["conference_submission_cache_key"] = cache_key
        st.session_state["conference_submission_cache"] = submission
    return access_key, submission, ""


def _hydrate_existing_submission(repo: Any, session_id: str) -> None:
    if st.session_state.get("conference_hydrated"):
        return
    draft = get_draft()
    raw_key = str(draft.get("access_key") or st.query_params.get("key", "") or "").strip()
    if not raw_key:
        st.session_state["conference_hydrated"] = True
        return
    access_key, submission, _ = _load_submission_for_key(repo, session_id, raw_key)
    if access_key and submission:
        hydrated = {
            key: value
            for key, value in submission.items()
            if key in get_draft()
        }
        hydrated["mode"] = str(submission.get("mode") or _infer_mode(submission))
        hydrated["access_key"] = access_key
        hydrated["submitted"] = True
        update_draft(**hydrated)
        repo.upsert_conference_player(
            session_id=session_id,
            access_key=access_key,
            payload=build_session_payload(get_draft()),
            identity_metadata=build_identity_metadata(get_draft()),
        )
        _set_entry_mode("dashboard")
    elif access_key:
        update_draft(access_key=access_key)
    st.session_state["conference_hydrated"] = True


def _advance_step() -> None:
    next_step()


def _ensure_access_key() -> str:
    access_key = str(get_draft().get("access_key") or "").strip()
    if access_key:
        return access_key
    access_key = generate_hex_key()
    update_draft(access_key=access_key)
    return access_key


def _submit(repo: Any, session: Dict[str, Any]) -> None:
    draft = get_draft()
    payload = build_session_payload(draft)
    identity_metadata = build_identity_metadata(draft)
    access_key = _ensure_access_key()
    access_key_hash = repo.access_key_hash(access_key)
    access_key_last4 = emoji_suffix(access_key)
    player = repo.upsert_conference_player(
        session_id=session["id"],
        access_key=access_key,
        payload=payload,
        identity_metadata=identity_metadata,
    )
    repo.save_session_response_set(
        session["id"],
        str((player or {}).get("id") or ""),
        TEXT_ID,
        str(st.session_state.get("conference_device_id", "")),
        access_key_hash,
        access_key_last4,
        payload,
        identity_metadata,
    )
    st.session_state["conference_submission_cache_key"] = f"{session['id']}:{access_key_hash}"
    st.session_state["conference_submission_cache"] = build_payload_view(draft) | {
        "access_key_hash": access_key_hash,
        "access_key_last4": access_key_last4,
        "actor_key": f"player:{str((player or {}).get('id') or '')}" if (player or {}).get("id") else f"response:{access_key_hash}",
    }
    update_draft(access_key=access_key, submitted=True)
    mark_submitted()


def _open_confirm_send_dialog(repo: Any, session: Dict[str, Any]) -> None:
    @st.dialog("Save this key")
    def _confirm_send_dialog() -> None:
        access_key = _ensure_access_key()
        emoji_key = hex_to_emoji(access_key)
        emoji_symbols = split_emoji_symbols(emoji_key)
        short_emoji = "".join(emoji_symbols[-4:]) if len(emoji_symbols) >= 4 else emoji_key
        st.markdown(
            f"""
            <div style="text-align:center; font-size:4.6rem; line-height:1.15; letter-spacing:.16em; margin: 1rem 0 1.15rem 0;">
                {short_emoji}
            </div>
            """,
            unsafe_allow_html=True,
        )
        components.html(
            f"""
            <div style="display:flex; justify-content:center; margin: .5rem 0 1rem 0; background: transparent;">
              <button
                onclick="navigator.clipboard.writeText({short_emoji!r})"
                style="
                  border: 1px solid #0f6d62;
                  border-radius: 999px;
                  background: #0f6d62;
                  color: #ffffff;
                  padding: .78rem 1.2rem;
                  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                  font-size: 1rem;
                  line-height: 1.2;
                  font-weight: 700;
                  cursor: pointer;
                  box-shadow: 0 8px 24px rgba(15, 109, 98, 0.18);
                "
              >
                ⧉ Copy the emoji key
              </button>
            </div>
            """,
            height=64,
        )
        st.markdown(
            "### Complexity is anonymous first. This access key lets you return later to your profile and your pending reflections."
        )
        if st.button("Screenshot taken", type="primary", use_container_width=True):
            _submit(repo, session)
            st.rerun()

    _confirm_send_dialog()


def _start_new_participant() -> None:
    reset_flow_state()
    _clear_login_error()
    st.session_state["conference_hide_migration_prompt"] = False
    _set_entry_mode("new")
    st.rerun()


def _open_existing_login() -> None:
    _clear_login_error()
    _set_entry_mode("existing")


def _login_with_key(repo: Any, session_id: str, raw_key: str) -> None:
    access_key, submission, error = _load_submission_for_key(repo, session_id, raw_key)
    if not access_key:
        _set_login_error(error or "This access key could not be decoded.")
        return
    update_draft(access_key=access_key)
    if not submission:
        _set_login_error("No submission was found for this access key yet.")
        return
    hydrated = {
        key: value
        for key, value in submission.items()
        if key in get_draft()
    }
    hydrated["mode"] = str(submission.get("mode") or _infer_mode(submission))
    hydrated["access_key"] = access_key
    hydrated["submitted"] = True
    update_draft(**hydrated)
    repo.upsert_conference_player(
        session_id=session_id,
        access_key=access_key,
        payload=build_session_payload(get_draft()),
        identity_metadata=build_identity_metadata(get_draft()),
    )
    _clear_login_error()
    _set_entry_mode("dashboard")
    st.rerun()


def _resume_in_mode(mode: str) -> None:
    update_draft(mode=mode, submitted=False)
    set_step(first_active_question_step())
    _set_entry_mode("new")
    st.rerun()


def _render_entry(session: Dict[str, Any], repo: Any) -> None:
    conference_header("Complexity", "", step="")
    st.markdown("### Anonymous first.")
    st.markdown("### Choose how to enter.")
    if st.button("🆕 New participant", type="primary", use_container_width=True):
        _start_new_participant()
    if st.button("🔑 I already have an access key", use_container_width=True):
        _open_existing_login()
        st.rerun()
    if _entry_mode() == "existing":
        st.markdown("### Enter your emoji access key.")
        raw_key = st.text_area(
            "Access key",
            value=str(get_draft().get("access_key") or ""),
            key="conference_existing_key",
            placeholder="Paste your 4-emoji or full access key here",
            label_visibility="collapsed",
            height=110,
        )
        if st.button("Open my dashboard", type="primary", use_container_width=True):
            _login_with_key(repo, session["id"], raw_key)
        error = str(st.session_state.get(LOGIN_ERROR_KEY, "") or "")
        if error:
            st.warning(error)


def _render_welcome() -> None:
    st.markdown("### How much time do you have?")
    for row in mode_card_rows():
        button_label = f"{row['accent']} {row['title']}\n{row['detail']}"
        if st.button(button_label, type="primary", use_container_width=True, key=f"conference_mode_{row['value']}"):
            update_draft(mode=str(row["value"]))
            set_step(first_active_question_step())
            st.rerun()
    summary_card("Anonymous first", STEP_COPY["welcome"]["note"])


def _render_pills(question: Dict[str, Any], current_value: Any) -> None:
    field = str(question["field"])
    option_map = {str(item["value"]): str(item["label"]) for item in question.get("options", [])}
    input_type = str(question["input_type"])
    if input_type == "multi":
        selected = st.pills(
            question["prompt"],
            list(option_map.keys()),
            default=list(current_value or []) if isinstance(current_value, list) else [],
            selection_mode="multi",
            key=f"conference_widget_{field}",
            format_func=lambda value: option_map.get(value, value),
            label_visibility="collapsed",
        )
        max_select = question.get("max_select")
        if isinstance(max_select, int) and len(selected) > max_select:
            selected = selected[:max_select]
        update_draft(**{field: list(selected)})
        if selected:
            clear_deferred_field(field)
        return

    selected_single = st.pills(
        question["prompt"],
        list(option_map.keys()),
        default=str(current_value) if isinstance(current_value, str) and current_value else None,
        selection_mode="single",
        key=f"conference_widget_{field}",
        format_func=lambda value: option_map.get(value, value),
        label_visibility="collapsed",
    )
    update_draft(**{field: str(selected_single or "")})
    if selected_single:
        clear_deferred_field(field)


def _render_scientific_home() -> None:
    draft = get_draft()
    country = st.text_input(
        "Country",
        value=str(draft.get("scientific_home_country") or ""),
        key="conference_widget_scientific_home_country",
        placeholder="Country",
    )
    city = st.text_input(
        "City",
        value=str(draft.get("scientific_home_city") or ""),
        key="conference_widget_scientific_home_city",
        placeholder="City",
    )
    institution = st.text_input(
        "Institution (optional)",
        value=str(draft.get("scientific_home_institution") or ""),
        key="conference_widget_scientific_home_institution",
        placeholder="Institution (optional)",
    )
    update_draft(
        scientific_home_country=country,
        scientific_home_city=city,
        scientific_home_institution=institution,
    )


def _render_fingerprint() -> None:
    draft = get_draft()
    fingerprint = draft.get("complexity_fingerprint", {})
    if not isinstance(fingerprint, dict):
        fingerprint = {}
    updated = {}
    for axis in FINGERPRINT_AXES:
        updated[axis] = int(
            st.slider(
                FINGERPRINT_LABELS.get(axis, axis.title()),
                min_value=0,
                max_value=5,
                value=int(fingerprint.get(axis, 0) or 0),
                key=f"conference_widget_fp_{axis}",
            )
        )
    update_draft(complexity_fingerprint=updated)
    if any(updated.values()):
        clear_deferred_field("complexity_fingerprint")


def _render_question_step(step: str) -> None:
    question = question_by_step(step)
    if not question:
        return
    field = str(question["field"])
    draft = get_draft()
    current_value = draft.get(field)
    input_type = str(question["input_type"])

    if input_type in {"single", "multi"}:
        _render_pills(question, current_value)
        return

    if input_type == "scientific_home":
        _render_scientific_home()
        return

    if input_type == "fingerprint":
        _render_fingerprint()
        return

    if input_type == "text":
        value = st.text_area(
            "",
            value=str(current_value or ""),
            key=f"conference_widget_{field}",
            placeholder=str(question.get("placeholder") or ""),
            max_chars=500,
            label_visibility="collapsed",
            height=180,
        )
        update_draft(**{field: value})
        if str(value or "").strip():
            clear_deferred_field(field)


def _render_identity() -> None:
    draft = get_draft()
    alias = st.text_input(
        "Alias",
        value=str(draft.get("alias") or ""),
        key="conference_widget_alias",
        placeholder="Optional public alias",
    )
    identity = st.text_input(
        "Identity",
        value=str(draft.get("identity") or ""),
        key="conference_widget_identity",
        placeholder="Optional name or affiliation",
    )
    contact = str(draft.get("contact") or "")
    if should_collect_contact(draft):
        contact = st.text_input(
            "Contact",
            value=contact,
            key="conference_widget_contact",
            placeholder="Optional email, website, or contact cue",
        )
    update_draft(alias=alias, identity=identity, contact=contact if should_collect_contact(draft) else "")


def _render_review() -> None:
    payload = build_payload_view(get_draft())
    summary_card("Mode", _labels_for("mode", str(payload.get("mode") or "quick")))
    summary_card("Profile", "Persistent across events unless you change it.")
    summary_card("Perspective", _labels_for("role", payload.get("role")))
    if payload.get("career_stage"):
        summary_card("Career stage", _labels_for("career_stage", payload.get("career_stage")))
    summary_card(
        "Scientific home",
        _labels_for(
            "scientific_home",
            {
                "country": payload.get("scientific_home_country", ""),
                "city": payload.get("scientific_home_city", ""),
                "institution": payload.get("scientific_home_institution", ""),
            },
        ),
    )
    if payload.get("scale"):
        summary_card("Computational scale", _labels_for("scale", payload.get("scale")))
    if payload.get("collaboration_style"):
        summary_card("Collaboration style", _labels_for("collaboration_style", payload.get("collaboration_style")))
    summary_card("Assets", _labels_for("assets", payload.get("assets")))
    if "complexity_fingerprint" in active_question_steps(get_draft()):
        summary_card("Complexity fingerprint", _labels_for("complexity_fingerprint", payload.get("complexity_fingerprint")))

    summary_card("Session", "These answers belong to this event and can change next time.")
    summary_card("Motivations", _labels_for("motivations", payload.get("motivations")))
    summary_card("Obstacle", _labels_for("obstacle", payload.get("obstacle")))
    summary_card("Challenge", _labels_for("challenge", payload.get("challenge")))
    summary_card("Follow-up interest", _labels_for("follow_up_interest", payload.get("follow_up_interest")))
    if payload.get("open_question"):
        summary_card("Open question", str(payload["open_question"]))

    pending = pending_reflection_fields(get_draft())
    if pending:
        summary_card(
            "Pending reflections",
            " · ".join(_field_label(field) for field in pending),
        )

    identity_parts = [
        str(payload.get("alias") or "").strip(),
        str(payload.get("identity") or "").strip(),
        str(payload.get("contact") or "").strip(),
    ]
    identity_text = " · ".join(part for part in identity_parts if part) or "Remain anonymous"
    summary_card("Alias or identity", identity_text)
def _question_teasers(submissions: List[Dict[str, Any]], self_actor: str) -> List[str]:
    entries: List[str] = []
    seen: set[str] = set()
    for item in submissions:
        if str(item.get("actor_key") or "") == self_actor:
            continue
        text = str(item.get("open_question") or "").strip()
        if not text or text in seen:
            continue
        entries.append(text)
        seen.add(text)
        if len(entries) >= 4:
            break
    return entries


def _historical_session_counts(repo: Any, current_session_id: str) -> List[Dict[str, Any]]:
    sessions = [
        {
            "code": "pisa-conference-session",
            "label": "Pisa",
            "question": "Who are you?",
        },
        {
            "code": "global-session",
            "label": "UNESCO",
            "question": "What resonates?",
        },
    ]
    rows: List[Dict[str, Any]] = []
    for item in sessions:
        session = repo.resolve_session(session_code=item["code"])
        if not session:
            continue
        if str(session.get("id") or "") == str(current_session_id or ""):
            continue
        submissions = repo.group_rows_by_submission(repo.get_session_rows(session["id"]))
        rows.append(
            {
                "label": item["label"],
                "question": item["question"],
                "participants": len(submissions),
            }
        )
    return rows


def _render_room_aggregates(submissions: List[Dict[str, Any]]) -> None:
    snapshot = room_snapshot(submissions)
    cols = st.columns(4)
    cols[0].metric("Participants", int(snapshot["participants"]))
    cols[1].metric("Countries", int(snapshot["countries"]))
    cols[2].metric("Follow-up yes", int(snapshot["follow_up"].get("yes", 0)))
    cols[3].metric("Follow-up maybe", int(snapshot["follow_up"].get("maybe", 0)))

    for title, field, counter in [
        ("The room can bring…", "assets", snapshot["assets"]),
        ("The room is trying to solve…", "obstacle", snapshot["obstacles"]),
        ("The room would join…", "challenge", snapshot["challenges"]),
    ]:
        st.markdown(f"### {title}")
        if not counter:
            st.caption("No signals yet.")
            continue
        lines = [
            f"{value} · {_labels_for(field, key)}"
            for key, value in counter.most_common(4)
        ]
        summary_card(title, "<br>".join(lines))


def _render_other_sessions(repo: Any, current_session_id: str) -> None:
    historical = _historical_session_counts(repo, current_session_id)
    if not historical:
        return
    st.markdown("### Other sessions")
    for item in historical:
        summary_card(
            item["label"],
            f'{int(item["participants"])} participants · question: {item["question"]}',
        )

def _render_personal_dashboard(repo: Any, session: Dict[str, Any]) -> None:
    payload = build_payload_view(get_draft())
    submissions = repo.group_rows_by_submission(repo.get_session_rows(session["id"]))
    conference_header("Complexity", "", step="")
    st.markdown("### Your profile is loaded.")
    summary_card("Mode", _labels_for("mode", str(payload.get("mode") or "quick")))
    summary_card("Perspective", _labels_for("role", payload.get("role")))
    summary_card("Assets", _labels_for("assets", payload.get("assets")))
    if payload.get("challenge"):
        summary_card("Current challenge", _labels_for("challenge", payload.get("challenge")))
    if payload.get("open_question"):
        summary_card("Open question", str(payload.get("open_question")))

    gaps = profile_completion_gaps(get_draft())
    if gaps and not bool(st.session_state.get("conference_hide_migration_prompt")):
        st.markdown("### We’ve added new questions")
        st.caption(f"We have added {len(gaps)} question(s) to better understand your perspective.")
        left, right = st.columns(2)
        with left:
            if st.button("Yes, enthusiastically", type="primary", use_container_width=True):
                _resume_at_field(gaps[0], suggested_mode_for_missing_profile_fields(gaps))
        with right:
            if st.button("Later", use_container_width=True):
                st.session_state["conference_hide_migration_prompt"] = True
                st.rerun()

    pending = pending_reflection_fields(get_draft())
    if pending:
        st.markdown("### Pending reflections")
        for field in pending:
            summary_card(_field_label(field), "Deferred. You can answer later.")
        if st.button("Answer pending reflections", type="primary", use_container_width=True):
            _resume_at_field(pending[0], str(payload.get("mode") or "standard"))

    teasers = _question_teasers(submissions, str(st.session_state.get("conference_submission_cache", {}).get("actor_key", "")))
    _render_room_aggregates(submissions)
    _render_other_sessions(repo, str(session.get("id") or ""))
    if teasers:
        st.markdown("### Questions in the room")
        for text in teasers:
            summary_card("Open question", text)

    mode = str(payload.get("mode") or "quick")
    if mode == "quick":
        if st.button("Continue in Standard", type="primary", use_container_width=True):
            _resume_in_mode("standard")
        if st.button("Continue in Deep dive", use_container_width=True):
            _resume_in_mode("deep")
    elif mode == "standard":
        if st.button("Continue in Deep dive", type="primary", use_container_width=True):
            _resume_in_mode("deep")
        if st.button("Edit my Standard responses", use_container_width=True):
            _resume_in_mode("standard")
    else:
        if st.button("Edit my Deep responses", type="primary", use_container_width=True):
            _resume_in_mode("deep")

    st.page_link(COMPLEXITY_OVERVIEW_PAGE, label="Open the Complexity overview", use_container_width=True, icon=":material/travel_explore:")
    if st.button("Use another access key", use_container_width=True):
        _set_entry_mode("existing")
        _clear_login_error()
        st.rerun()


def _render_done() -> None:
    draft = get_draft()
    access_key = str(draft.get("access_key") or "")
    emoji_key = hex_to_emoji(access_key) if access_key else ""
    access_key_hash = hashlib.sha256(access_key.encode("utf-8")).hexdigest() if access_key else ""
    summary_card("Short key", "".join(split_emoji_symbols(emoji_key)[-4:]) if emoji_key else "Unavailable")
    summary_card("Hash prefix", access_key_hash[:12] if access_key_hash else "Unavailable")
    with st.expander("Full emoji key", expanded=False):
        st.markdown(
            f"<div style='font-size:2rem; line-height:1.4; text-align:center; padding:.6rem 0;'>{emoji_key or 'Unavailable'}</div>",
            unsafe_allow_html=True,
        )
    with st.expander("ASCII access key", expanded=False):
        st.code(access_key or "Unavailable")
    left, right = st.columns(2)
    with left:
        if st.button("Open my dashboard", type="primary", use_container_width=True):
            _set_entry_mode("dashboard")
            st.rerun()
    with right:
        if st.button(STEP_COPY["done"]["cta"], use_container_width=True):
            reset_flow_state()
            _set_entry_mode("")
            st.rerun()


def _render_navigation(repo: Any, session: Dict[str, Any]) -> None:
    step = current_step()
    if step in {"welcome", "done"}:
        return
    if step == "review":
        left, right = st.columns(2)
        with left:
            if st.button("Edit", use_container_width=True):
                set_step(first_active_question_step())
                st.rerun()
        with right:
            if st.button(STEP_COPY["review"]["cta"], type="primary", use_container_width=True):
                _open_confirm_send_dialog(repo, session)
        return

    if field_for_step(step) in DEFERRABLE_FIELDS:
        left, right = st.columns(2)
        with left:
            if st.button("Reflect later", use_container_width=True):
                defer_field(field_for_step(step))
                _advance_step()
                st.rerun()
        with right:
            if st.button("Continue", type="primary", use_container_width=True):
                draft = get_draft()
                if not step_is_complete(step, draft):
                    st.warning("Answer this step or defer it for later.")
                    return
                _advance_step()
                st.rerun()
        return

    if st.button("Continue", type="primary", use_container_width=True):
        draft = get_draft()
        if not step_is_complete(step, draft):
            st.warning("Complete this step before continuing.")
            return
        _advance_step()
        st.rerun()


def _render_questionnaire(repo: Any, session: Dict[str, Any]) -> None:
    if current_step() not in active_step_sequence():
        set_step("welcome")
    step = current_step()
    copy = STEP_COPY[step]
    sequence = active_step_sequence()
    step_index = sequence.index(step) + 1 if step in sequence else 1
    step_label = f"{step_index} / {len(sequence)}" if step != "done" else "complete"
    conference_header(copy["title"], "", step=step_label)
    if copy.get("body"):
        st.markdown(f"### {copy['body']}")

    if step == "welcome":
        _render_welcome()
    elif step == IDENTITY_STEP:
        _render_identity()
    elif step == "review":
        _render_review()
    elif step == "done":
        _render_done()
    else:
        _render_question_step(step)

    _render_navigation(repo, session)


def main() -> None:
    set_page()
    apply_conference_styles()
    sidebar_debug_state()
    _ensure_local_state()

    repo = get_conference_repo()
    if not repo or not repo.is_ready():
        st.error(repo.unavailable_reason if repo else "Conference repository is unavailable.")
        return

    bundle = get_conference_bundle(prefer_active=True)
    session = bundle.get("session")
    if not session:
        st.error("Conference session is missing. Ensure `pisa-conference-session` exists in the shared sessions DB.")
        return

    _hydrate_existing_submission(repo, session["id"])

    mode = _entry_mode()
    if mode == "dashboard":
        _render_personal_dashboard(repo, session)
        return
    if mode == "new" or get_draft().get("submitted"):
        _render_questionnaire(repo, session)
        return
    _render_entry(session, repo)


if __name__ == "__main__":
    main()
