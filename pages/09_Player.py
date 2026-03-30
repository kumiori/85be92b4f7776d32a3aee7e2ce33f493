from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st

from infra.app_context import get_authenticator, get_notion_repo
from infra.app_state import (
    ensure_auth,
    ensure_session_context,
    ensure_session_state,
    remember_access,
    require_login,
)
from models.catalog import QUESTION_BY_ID
from repositories.interaction_repo import NotionInteractionRepository
from ui import apply_theme, heading, microcopy, set_page, sidebar_debug_state


def _interaction_repo(repo) -> NotionInteractionRepository:
    notion_cfg = st.secrets.get("notion", {})
    db_id = (
        notion_cfg.get("ice_interaction_responses_db_id")
        or notion_cfg.get("interaction_responses_db_id")
        or notion_cfg.get("ice_responses_db_id")
        or ""
    )
    if not db_id:
        raise ValueError("Missing interaction responses DB id in secrets.")
    return NotionInteractionRepository(repo, str(db_id))


def _score_from_choice(choice: Any) -> int | None:
    if not isinstance(choice, str):
        return None
    txt = choice.strip().lower()
    if txt.startswith("yes"):
        return 1
    if "upon condition" in txt or "depending on conditions" in txt or "depending upon conditions" in txt or "condition" in txt:
        return 0
    if txt.startswith("no"):
        return -1
    return None


def _extract_player_rows(
    rows: List[Dict[str, Any]],
    *,
    player_page_id: str,
    player_access_key: str,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows:
        pid = str(row.get("player_id") or "").strip()
        if pid and pid == player_page_id:
            out.append(row)
            continue
        raw_access = str(row.get("access_key") or "").strip()
        if raw_access and player_access_key and raw_access == player_access_key:
            out.append(row)
    return out


def _question_prompt(item_id: str) -> str:
    q = QUESTION_BY_ID.get(item_id)
    return str(getattr(q, "prompt", "") or item_id)


def _question_sort_key(item_id: str) -> Tuple[int, str]:
    q = QUESTION_BY_ID.get(item_id)
    order = int(getattr(q, "order", 9999) or 9999)
    return order, item_id


def _format_timestamp(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "—"
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.strftime("%d %b %Y · %H:%M")
    except Exception:
        return raw


def _normalise_latest_answer(row: Dict[str, Any]) -> str:
    value_label = str(row.get("value_label") or "").strip()
    if value_label:
        return value_label

    value = row.get("response_value")
    if isinstance(value, list):
        return ", ".join(str(v) for v in value if str(v).strip()) or "—"
    if isinstance(value, str):
        return value.strip() or "—"

    payload = row.get("value_json")
    if isinstance(payload, dict):
        choice = payload.get("choice", payload.get("answer", ""))
        if isinstance(choice, list):
            joined = ", ".join(str(v) for v in choice if str(v).strip())
            if joined:
                return joined
        if isinstance(choice, str) and choice.strip():
            return choice.strip()
        comment = str(payload.get("comment") or payload.get("optional_text") or "").strip()
        if comment:
            return comment
    return "—"


def _revision_summary(row: Dict[str, Any]) -> str:
    answer = _normalise_latest_answer(row)
    comment = ""
    payload = row.get("value_json")
    if isinstance(payload, dict):
        comment = str(payload.get("comment") or payload.get("optional_text") or "").strip()
    if comment and comment not in answer:
        return f"{answer} — {comment}"
    return answer


def _row_is_player_owned(row: Dict[str, Any], *, player_page_id: str, player_access_key: str) -> bool:
    pid = str(row.get("player_id") or "").strip()
    if pid and pid == player_page_id:
        return True
    access_key = str(row.get("access_key") or "").strip()
    return bool(player_access_key and access_key and access_key == player_access_key)


def _latest_rows_by_question(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    latest: Dict[str, Dict[str, Any]] = {}
    ordered = sorted(
        rows,
        key=lambda x: (
            str(x.get("timestamp") or x.get("created_at") or ""),
            str(x.get("response_id") or ""),
        ),
    )
    for row in ordered:
        item_id = str(row.get("item_id") or row.get("question_id") or "").strip()
        if not item_id:
            continue
        latest[item_id] = row
    return latest


def _decode_existing_payload(question_id: str, row: Dict[str, Any]) -> Dict[str, Any]:
    payload = row.get("value_json")
    if isinstance(payload, dict):
        choice = payload.get("choice", payload.get("answer", ""))
        if question_id == "FINAL_FEEDBACK":
            rating = None
            if isinstance(choice, str) and choice.startswith("faces:"):
                try:
                    rating = int(choice.split(":", 1)[1])
                except Exception:
                    rating = None
            return {
                "choice": choice if isinstance(choice, str) else "",
                "rating": rating,
                "comment": str(payload.get("comment") or payload.get("optional_text") or "").strip(),
                "contact_value": str(payload.get("contact_value") or "").strip(),
            }
        return {
            "choice": choice if isinstance(choice, (str, list)) else "",
            "comment": str(payload.get("comment") or payload.get("optional_text") or "").strip(),
            "contact_value": str(payload.get("contact_value") or "").strip(),
        }

    response_value = row.get("response_value")
    if question_id == "FINAL_FEEDBACK" and isinstance(response_value, str) and response_value.startswith("faces:"):
        try:
            rating = int(response_value.split(":", 1)[1])
        except Exception:
            rating = None
        return {"choice": response_value, "rating": rating, "comment": "", "contact_value": ""}

    if isinstance(response_value, list):
        return {"choice": response_value, "comment": "", "contact_value": ""}
    return {"choice": str(response_value or ""), "comment": "", "contact_value": ""}


def _build_revision_payload(
    *,
    question_id: str,
    session_id: str,
    latest_row: Dict[str, Any],
    choice: Any,
    comment: str,
    contact_value: str,
    revision_count: int,
) -> Dict[str, Any]:
    q = QUESTION_BY_ID.get(question_id)
    qtype = str(getattr(q, "qtype", "") or "")
    base_payload = latest_row.get("value_json") if isinstance(latest_row.get("value_json"), dict) else {}
    old_page_index = base_payload.get("page_index")
    old_depth = base_payload.get("depth")
    payload: Dict[str, Any] = {
        "choice": choice,
        "answer": choice,
        "comment": comment.strip(),
        "optional_text": comment.strip(),
        "revision_index": revision_count + 1,
        "revision_of": str(latest_row.get("response_id") or ""),
        "session_id": session_id,
    }
    if isinstance(old_page_index, (int, float)):
        payload["page_index"] = int(old_page_index)
    if isinstance(old_depth, (int, float)):
        payload["depth"] = int(old_depth)

    if question_id == "ORGANISATION_SIGNAL":
        txt = str(choice or "").strip().lower()
        if txt.startswith("yes"):
            payload["score"] = 1
        elif "upon condition" in txt or "depending on conditions" in txt or "depending upon conditions" in txt or "condition" in txt:
            payload["score"] = 0
        elif txt.startswith("no"):
            payload["score"] = -1
        payload["question_type"] = "signal"
        payload["type"] = "pre_signal"
        return payload

    if question_id == "CONTACT_METHOD":
        payload["contact_value"] = contact_value.strip()
        payload["question_type"] = "single"
        payload["type"] = "pre_lobby"
        return payload

    if question_id == "FINAL_FEEDBACK":
        payload["question_type"] = "feedback"
        payload["type"] = "pre_lobby"
        return payload

    if qtype == "multi":
        payload["question_type"] = "multi"
    elif qtype in {"single", "pre_signal"}:
        payload["question_type"] = "single"
    else:
        payload["question_type"] = "text"
    return payload


@st.dialog("Revise response", width="large")
def _render_response_dialog(
    *,
    ir: NotionInteractionRepository,
    player_page_id: str,
    player_access_key: str,
    session_title: str,
    session_id: str,
    latest_row: Dict[str, Any],
    revision_rows: List[Dict[str, Any]],
) -> None:
    question_id = str(latest_row.get("item_id") or latest_row.get("question_id") or "").strip()
    q = QUESTION_BY_ID.get(question_id)
    if not q:
        st.error("Question metadata is unavailable for this response.")
        return

    st.caption(session_title)
    st.markdown(f"### {q.prompt}")
    if q.short_description:
        st.caption(q.short_description)

    existing = _decode_existing_payload(question_id, latest_row)
    choice = existing.get("choice", "")
    comment = str(existing.get("comment") or "")
    contact_value = str(existing.get("contact_value") or "")

    new_choice: Any = choice
    new_comment = comment
    new_contact = contact_value

    if question_id == "FINAL_FEEDBACK":
        default_rating = existing.get("rating", None)
        rating = st.feedback("faces", key=f"player-feedback-{question_id}")
        if rating is None:
            rating = default_rating
        new_choice = "" if rating is None else f"faces:{int(rating)}"
        new_comment = st.text_area(
            "Comment",
            value=comment,
            placeholder="Add a short reflection",
            key=f"player-feedback-comment-{question_id}",
        )
    elif q.qtype == "multi":
        defaults = choice if isinstance(choice, list) else []
        new_choice = st.multiselect(
            "Select one or more",
            q.options or [],
            default=defaults,
            max_selections=q.max_select,
            key=f"player-multi-{question_id}",
        )
        if q.show_text_field and any(str(v).lower() == "other" for v in new_choice):
            new_comment = st.text_input(
                "If you selected Other, specify",
                value=comment,
                placeholder=q.placeholder or "Your comment",
                key=f"player-comment-{question_id}",
            )
    elif q.qtype in {"single", "pre_signal"}:
        options = q.options or []
        selected_idx = options.index(choice) if isinstance(choice, str) and choice in options else 0
        new_choice = st.radio(
            "Select one option",
            options,
            index=selected_idx if options else None,
            key=f"player-single-{question_id}",
        )
        lower_choice = str(new_choice or "").strip().lower()
        if question_id == "CONTACT_METHOD":
            if lower_choice == "email":
                new_contact = st.text_input(
                    "Email",
                    value=contact_value,
                    placeholder="name@example.org",
                    key=f"player-contact-{question_id}",
                )
            elif lower_choice in {"in person", "video call"}:
                new_contact = st.text_input(
                    "Email or phone",
                    value=contact_value,
                    placeholder="Email or phone number",
                    key=f"player-contact-{question_id}",
                )
            else:
                new_contact = ""
        elif q.show_text_field and (
            any(
                marker in lower_choice
                for marker in [
                    "upon condition",
                    "depending on conditions",
                    "depending upon conditions",
                    "condition",
                ]
            )
            or lower_choice == "other"
        ):
            new_comment = st.text_input(
                "Condition or comment",
                value=comment,
                placeholder=q.placeholder or "Your condition or comment",
                key=f"player-comment-{question_id}",
            )
    else:
        new_choice = st.text_area(
            "Your response",
            value=str(choice or ""),
            placeholder=q.placeholder or "Write your response",
            key=f"player-text-{question_id}",
        )

    revision_count = len(revision_rows)
    st.caption(
        f"Saving a revision appends a new response and keeps the previous {revision_count} revision"
        f"{'' if revision_count == 1 else 's'} in history."
    )
    if revision_rows:
        with st.expander("Revision history", expanded=False):
            history_rows = [
                {
                    "time": _format_timestamp(r.get("timestamp") or r.get("created_at")),
                    "answer": _revision_summary(r),
                }
                for r in sorted(
                    revision_rows,
                    key=lambda x: str(x.get("timestamp") or x.get("created_at") or ""),
                    reverse=True,
                )
            ]
            st.dataframe(history_rows, width="stretch", hide_index=True)

    save_col, cancel_col = st.columns([1, 1])
    with save_col:
        save = st.button("Save revision", type="primary", width="stretch")
    with cancel_col:
        cancel = st.button("Cancel", width="stretch")

    if cancel:
        st.rerun()

    if not save:
        return

    if q.qtype == "multi" and not isinstance(new_choice, list):
        st.error("Please select one or more options.")
        return
    if q.qtype == "multi" and not new_choice:
        st.error("Select at least one option.")
        return
    if q.qtype in {"single", "pre_signal"} and not str(new_choice or "").strip():
        st.error("Select one option.")
        return
    if q.qtype == "text" and not str(new_choice or "").strip():
        st.error("Write a response before saving.")
        return
    if question_id == "CONTACT_METHOD":
        choice_text = str(new_choice or "").strip().lower()
        if choice_text not in {"i don't want to be in touch", "i dont want to be in touch"} and not str(new_contact or "").strip():
            st.error("Add an email or phone detail for this contact preference.")
            return

    payload = _build_revision_payload(
        question_id=question_id,
        session_id=session_id,
        latest_row=latest_row,
        choice=new_choice,
        comment=new_comment,
        contact_value=new_contact,
        revision_count=revision_count,
    )
    text_id = str(latest_row.get("text_id") or session_title or session_id)
    device_id = str(
        st.session_state.get("anon_token")
        or latest_row.get("device_id")
        or player_access_key
    ).strip()
    ir.save_response(
        session_id=session_id,
        player_id=player_page_id or None,
        question_id=question_id,
        value=payload,
        text_id=text_id,
        device_id=device_id,
    )
    st.session_state["player_response_edit_success"] = question_id
    st.rerun()


def main() -> None:
    set_page()
    apply_theme()
    ensure_session_state()
    repo = get_notion_repo()
    authenticator = get_authenticator(repo)
    ensure_auth(authenticator, callback=remember_access, key="player-dashboard-login")
    ensure_session_context(repo)
    require_login()
    sidebar_debug_state()

    heading("Your trajectory")
    microcopy(
        "This page gathers the signals you have sent so far: your responses, your sessions, and the path your participation has taken through time."
    )
    if st.session_state.get("authentication_status"):
        authenticator.logout(button_name="Logout", location="sidebar")

    if not repo:
        st.error("Notion repository unavailable.")
        return

    player_page_id = str(st.session_state.get("player_page_id") or "").strip()
    player_access_key = str(st.session_state.get("player_access_key") or "").strip()
    if not player_page_id and player_access_key:
        player = repo.get_player_by_id(player_access_key)
        if player and player.get("id"):
            player_page_id = str(player["id"])
    else:
        player = repo.get_player_by_id(player_page_id) if player_page_id else None
    if not player:
        st.error("Could not resolve your player profile.")
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Nickname", str(player.get("nickname") or "—"))
    c2.metric(
        "Access key",
        (str(player.get("access_key") or "")[-8:] or "—"),
    )
    c3.metric("Role", str(player.get("role") or "—"))
    c4.metric("Last activity", str(player.get("last_joined_on") or "—"))
    st.caption(
        "Response edits append a new revision and keep the previous history. You can update optional metadata below."
    )

    with st.expander("Edit optional metadata", expanded=False):
        with st.form("player-metadata-form"):
            nickname = st.text_input(
                "Name or nickname",
                value=str(player.get("nickname") or ""),
            )
            intent = st.text_input(
                "Motivation (optional)",
                value=str(player.get("intent") or ""),
            )
            email = st.text_input(
                "Email (optional, for reminder)",
                value=str(player.get("email") or ""),
            )
            consent_play = st.checkbox(
                "Consent play",
                value=bool(player.get("consent_play")),
            )
            consent_research = st.checkbox(
                "Consent research",
                value=bool(player.get("consent_research")),
            )
            submit = st.form_submit_button("Save metadata", type="primary")
        if submit:
            updated = repo.update_player_metadata(
                player_page_id or str(player.get("id") or ""),
                nickname=nickname,
                intent=intent,
                email=email,
                consent_play=consent_play,
                consent_research=consent_research,
            )
            if not updated:
                st.error("Could not save metadata.")
            else:
                st.success("Metadata updated.")
                st.rerun()

    sessions = repo.list_sessions(limit=200)
    session_by_id = {str(s.get("id") or ""): s for s in sessions}
    session_ids = list(dict.fromkeys(player.get("session_ids") or []))
    if not session_ids and st.session_state.get("session_id"):
        session_ids = [str(st.session_state.get("session_id"))]

    if not session_ids:
        st.info("No joined sessions yet.")
        return

    try:
        ir = _interaction_repo(repo)
    except Exception as exc:
        st.error(f"Could not initialise interaction repository: {exc}")
        return

    all_rows: List[Dict[str, Any]] = []
    for sid in session_ids:
        try:
            rows = ir.get_responses(sid)
        except Exception:
            rows = []
        all_rows.extend(
            _extract_player_rows(
                rows,
                player_page_id=player_page_id,
                player_access_key=player_access_key,
            )
        )

    st.subheader("Sessions joined")
    session_rows = []
    for sid in session_ids:
        sess = session_by_id.get(sid) or {}
        code = str(sess.get("session_code") or sid)
        count = sum(1 for r in all_rows if str(r.get("session_id") or "") == sid)
        session_rows.append({"session": code, "responses": count})
    st.dataframe(session_rows, width="stretch")

    st.subheader("Activity timeline")
    timeline_rows = []
    for r in all_rows:
        t = str(r.get("timestamp") or r.get("created_at") or "")
        if not t:
            continue
        timeline_rows.append({"time": t, "count": 1})
    timeline_rows.sort(key=lambda x: x["time"])
    if timeline_rows:
        st.line_chart(timeline_rows, x="time", y="count")
    else:
        st.caption("No timeline data yet.")

    st.subheader("Personal signal trajectory")
    signal_rows = []
    for r in all_rows:
        if str(r.get("item_id") or "") != "ORGANISATION_SIGNAL":
            continue
        score = _score_from_choice(str(r.get("value_label") or ""))
        if score is None:
            payload = r.get("value_json")
            if isinstance(payload, dict):
                score = _score_from_choice(str(payload.get("choice") or ""))
        if score is None:
            continue
        signal_rows.append(
            {
                "time": str(r.get("timestamp") or r.get("created_at") or ""),
                "score": score,
            }
        )
    signal_rows.sort(key=lambda x: x["time"])
    if signal_rows:
        cumulative = 0
        cum_rows = []
        for row in signal_rows:
            cumulative += int(row["score"])
            cum_rows.append({"time": row["time"], "cumulative": cumulative})
        st.line_chart(cum_rows, x="time", y="cumulative")
    else:
        st.caption("No organisation signal submissions yet.")

    st.subheader("Your responses")
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for r in all_rows:
        sid = str(r.get("session_id") or "")
        grouped.setdefault(sid, []).append(r)
    edited_question_id = str(st.session_state.pop("player_response_edit_success", "") or "").strip()
    if edited_question_id:
        st.success(f"Saved a new revision for {_question_prompt(edited_question_id)}.")
    for sid, rows in grouped.items():
        sess = session_by_id.get(sid) or {}
        title = str(sess.get("session_code") or sid)
        with st.expander(title, expanded=False):
            latest_by_question = _latest_rows_by_question(rows)
            item_ids = sorted(latest_by_question.keys(), key=_question_sort_key)
            for item_id in item_ids:
                latest_row = latest_by_question[item_id]
                question_rows = [
                    r
                    for r in rows
                    if str(r.get("item_id") or r.get("question_id") or "").strip() == item_id
                ]
                q = QUESTION_BY_ID.get(item_id)
                answer_text = _normalise_latest_answer(latest_row)
                revision_count = max(len(question_rows) - 1, 0)
                top_col, action_col = st.columns([5, 1])
                with top_col:
                    st.markdown(f"**{getattr(q, 'prompt', item_id)}**")
                    if q and getattr(q, "short_description", ""):
                        st.caption(str(q.short_description))
                with action_col:
                    if st.button(
                        "Revise",
                        key=f"player-revise-{sid}-{item_id}",
                        width="stretch",
                    ):
                        _render_response_dialog(
                            ir=ir,
                            player_page_id=player_page_id,
                            player_access_key=player_access_key,
                            session_title=title,
                            session_id=sid,
                            latest_row=latest_row,
                            revision_rows=question_rows,
                        )
                meta_col1, meta_col2, meta_col3 = st.columns([3, 2, 2])
                meta_col1.markdown(f"`Latest:` {answer_text}")
                meta_col2.caption(
                    f"Updated {_format_timestamp(latest_row.get('timestamp') or latest_row.get('created_at'))}"
                )
                meta_col3.caption(
                    f"{revision_count} earlier revision{'' if revision_count == 1 else 's'}"
                )
                if revision_count > 0:
                    with st.expander("See revision history", expanded=False):
                        history_rows = [
                            {
                                "time": _format_timestamp(r.get("timestamp") or r.get("created_at")),
                                "answer": _revision_summary(r),
                            }
                            for r in sorted(
                                question_rows,
                                key=lambda x: str(x.get("timestamp") or x.get("created_at") or ""),
                                reverse=True,
                            )
                        ]
                        st.dataframe(history_rows, width="stretch", hide_index=True)
                st.divider()


if __name__ == "__main__":
    main()
