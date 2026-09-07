from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
from urllib.parse import quote
import uuid

import streamlit as st

from conference.context import get_conference_repo
from conference.events import (
    UN_WG2_SESSION_CODE,
    conference_event_context,
    text_ids_for_session_code,
)
from conference.question_sets import question_by_id
from conference.registry import resolve_question_set_bundle
from conference.repo import emoji_suffix
from conference.session_window import filter_rows_to_session_window
from conference.ui import apply_conference_styles, conference_header
from conference.wg2_members import (
    build_wg2_member_candidates,
    claim_directory_entries,
    create_identity_claim,
    create_recovery_request,
    mask_email,
    public_claiming_enabled,
    recovery_token_fingerprint,
    recovery_token_state,
    reduce_recovery_events,
    resolve_member_route_state,
    verify_recovery_token,
)
from conference.wg2_schema import build_refinement_bundle
from conference.wg2_ux import host_role_allowed
from infra.app_context import get_notion_repo
from infra.app_state import ensure_session_state, remember_access
from infra.event_logger import list_logged_events, log_event
from ui import set_page


RECOVERY_LOG_PAGE = "un_wg2_recovery"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _recovery_secret() -> str:
    cookie = st.secrets.get("cookie", {})
    return str(cookie.get("key") or "").strip()


def _pilot_access_code() -> str:
    config = st.secrets.get("wg2_recovery", {})
    return str(config.get("access_code") or "").strip()


def _log_recovery(
    event_type: str,
    *,
    session_id: str,
    player_id: str = "",
    metadata: dict | None = None,
    status: str = "ok",
) -> bool:
    return log_event(
        module="iceicebaby.un_wg2.recovery",
        event_type=event_type,
        page=RECOVERY_LOG_PAGE,
        session_id=session_id,
        player_id=player_id,
        status=status,
        metadata=metadata or {},
        level="ERROR" if status == "error" else "INFO",
    )


def _pilot_access_allowed(events: list[dict]) -> bool:
    if public_claiming_enabled(events):
        return True
    if st.session_state.get("wg2_recovery_pilot_access"):
        return True
    role = str(st.session_state.get("player_role") or "")
    if host_role_allowed(role):
        return True
    expected = _pilot_access_code()
    if not expected:
        st.warning(
            "Public WG2 member claiming is currently closed. Ask a WG2 host to open "
            "claiming from WG2 Host → Member recovery."
        )
        return False
    st.caption(
        "Public claiming is currently closed. You can still continue with the "
        "leadership/core access code."
    )
    with st.form("wg2-recovery-pilot-access"):
        entered = st.text_input("Leadership/core access code", type="password")
        submitted = st.form_submit_button("Open participant recovery", type="primary")
    if submitted:
        if hmac.compare_digest(str(entered or "").strip(), expected):
            st.session_state["wg2_recovery_pilot_access"] = True
            st.rerun()
        st.error("That pilot access code is not valid.")
    return False


def _candidate_data(repo, notion_repo, session: dict, question_set):
    rows = repo.get_session_rows(
        str(session.get("id") or ""),
        text_ids=text_ids_for_session_code(UN_WG2_SESSION_CODE),
    )
    submissions = repo.group_rows_by_submission(
        filter_rows_to_session_window(rows, session)
    )
    players = notion_repo.list_all_players(limit=500)
    return build_wg2_member_candidates(
        submissions=submissions,
        players=players,
        current_schema=question_set,
        session_id=str(session.get("id") or ""),
    )


def _render_host_approval_link() -> None:
    st.caption(
        "Host action: sign in as a host or administrator, then open "
        "WG2 Host → Member recovery."
    )
    st.page_link(
        "pages/27_UN_WG2_Host.py",
        label="Open WG2 Host approval",
        icon=":material/admin_panel_settings:",
    )


def _render_claim_start(
    candidates: list[dict], session_id: str, events: list[dict]
) -> None:
    st.write("These participants have already contributed to the WG2 pilot.")
    directory_entries = claim_directory_entries(candidates)
    if not directory_entries:
        st.info("No WG2 participant trajectories are available for claiming.")
        return
    identified_count = sum(bool(item.get("claimable")) for item in directory_entries)
    anonymous_count = len(directory_entries) - identified_count
    st.caption(
        f"{len(directory_entries)} contributors · {identified_count} identified · "
        f"{anonymous_count} anonymous"
    )
    for candidate in directory_entries:
        row = st.columns([3, 1, 1])
        row[0].write(candidate["display_name"])
        if candidate.get("claimable"):
            row[1].caption("Identified")
            if row[2].button(
                "That's me",
                key=f"wg2-claim-select-{candidate['player_id']}",
            ):
                st.session_state["wg2_claim_candidate_id"] = candidate["player_id"]
                st.rerun()
        else:
            row[1].caption("Anonymous")
            row[2].caption("Included")

    selected_id = str(st.session_state.get("wg2_claim_candidate_id") or "")
    selected = next(
        (
            item
            for item in directory_entries
            if item["player_id"] == selected_id and item.get("claimable")
        ),
        None,
    )
    if not selected:
        return

    st.markdown(f"### {selected['display_name']}")
    request_states = reduce_recovery_events(events)
    pending = any(
        str(state.get("player_id") or "") == selected_id
        and str(state.get("status") or "")
        in {"pending", "approved", "ready_to_send", "sent"}
        for state in request_states.values()
    )
    if pending:
        st.info(
            "A recovery request for this trajectory is already awaiting host action."
        )
        _render_host_approval_link()
        return

    if selected["email"]:
        st.write("We already have a contact address for this participant:")
        st.markdown(f"**{mask_email(selected['email'])}**")
        if st.button("Send my access reminder", type="primary"):
            request = create_recovery_request(
                selected,
                requested_at=_now_iso(),
            )
            recorded = _log_recovery(
                "recovery_reminder_requested",
                session_id=session_id,
                player_id=selected_id,
                metadata=request,
            )
            if recorded:
                st.success(
                    "Request recorded. A WG2 host will send your one-time recovery link."
                )
                _render_host_approval_link()
            else:
                st.error(
                    "The recovery request could not be recorded. No request was created; "
                    "please try again or contact a WG2 host."
                )
        return

    with st.form(f"wg2-identity-claim-{selected_id}"):
        proposed_email = st.text_input(
            "Where should we send your access recovery link?"
        )
        submitted = st.form_submit_button("Claim access", type="primary")
    if submitted:
        try:
            claim = create_identity_claim(
                player_id=selected_id,
                proposed_email=proposed_email,
                requested_at=_now_iso(),
            )
        except ValueError as exc:
            st.error(str(exc))
        else:
            recorded = _log_recovery(
                "identity_claim_requested",
                session_id=session_id,
                player_id=selected_id,
                metadata=claim,
            )
            if recorded:
                st.success(
                    "Claim requested. A WG2 host must approve it before anything changes."
                )
                _render_host_approval_link()
            else:
                st.error(
                    "The identity claim could not be recorded. No claim was created; "
                    "please try again or contact a WG2 host."
                )


def _render_member_trajectory(
    repo, session: dict, candidate: dict, question_set
) -> None:
    player_id = str(candidate["player_id"])
    alignment = candidate["alignment"]
    log_token = f"{player_id}:{candidate['response_id']}:{question_set.schema_id}"
    if st.session_state.get("wg2_alignment_log_token") != log_token:
        st.session_state["wg2_alignment_log_token"] = log_token
        _log_recovery(
            "schema_alignment_checked",
            session_id=str(session.get("id") or ""),
            player_id=player_id,
            metadata={
                "schema_id": question_set.schema_id,
                "current": len(alignment["current"]),
                "needs_refinement": len(alignment["needs_refinement"]),
                "new_questions": len(alignment["new_questions"]),
                "legacy_only": len(alignment["legacy_only"]),
            },
        )

    conference_header(
        f"Welcome back, {candidate['display_name']}.", "", step="WG2 member"
    )
    st.markdown("## Your WG2 trajectory")
    metrics = st.columns(3)
    metrics[0].metric("Responses", candidate["response_count"])
    metrics[1].metric("Still current", len(alignment["current"]))
    metrics[2].metric("Needs review", len(alignment["needs_refinement"]))
    st.caption(f"{len(alignment['new_questions'])} new question(s) are available.")
    if alignment["new_questions"]:
        with st.expander("New optional questions", expanded=False):
            for item in alignment["new_questions"]:
                st.write(item["question"])

    refinements = alignment["needs_refinement"]
    if not refinements:
        st.success("Your WG2 trajectory is up to date.")
        complete_token = f"{player_id}:{candidate['response_id']}"
        if st.session_state.get("wg2_alignment_complete_token") != complete_token:
            st.session_state["wg2_alignment_complete_token"] = complete_token
            _log_recovery(
                "response_alignment_completed",
                session_id=str(session.get("id") or ""),
                player_id=player_id,
                metadata={"schema_id": question_set.schema_id},
            )
        return

    noun = "question has" if len(refinements) == 1 else "questions have"
    st.warning(f"{len(refinements)} {noun} been refined.")
    if not st.session_state.get("wg2_review_updates"):
        if st.button("Review updates", type="primary"):
            st.session_state["wg2_review_updates"] = True
            item = refinements[0]
            _log_recovery(
                "response_refinement_opened",
                session_id=str(session.get("id") or ""),
                player_id=player_id,
                metadata={"question_id": item["question_id"]},
            )
            st.rerun()
        return

    item = refinements[0]
    question = question_by_id(question_set, item["question_id"])
    if not question:
        st.error("The refined question is not available in the active schema.")
        return
    st.markdown("### We refined this question")
    st.caption("Previously we asked")
    st.write(item["previous_question"])
    st.caption("Your previous answer")
    st.write(item["previous_answer_label"])
    st.caption("Reason for change")
    st.write(item["reason"])
    st.markdown(f"### {item['question']}")
    option_labels = {option["value"]: option["label"] for option in question.options}
    answer = st.pills(
        question.prompt,
        list(option_labels),
        selection_mode="multi" if question.input_type == "multi" else "single",
        format_func=lambda value: option_labels.get(value, value),
        label_visibility="collapsed",
        key=f"wg2-refinement-{question.question_id}",
    )
    if st.button("Save clarification", type="primary"):
        normalized_answer = (
            list(answer or []) if question.input_type == "multi" else str(answer or "")
        )
        if not normalized_answer:
            st.error("Choose an answer before saving this clarification.")
            return
        access_key = str(candidate.get("access_key") or "")
        if not access_key:
            st.error("The existing participant credential could not be resolved.")
            return
        refined = build_refinement_bundle(
            previous_bundle=candidate["submission"],
            question=question,
            current_schema=question_set,
            answer=normalized_answer,
            previous_response_id=str(candidate.get("response_id") or ""),
        )
        event_context = conference_event_context(session=session)
        refined_session = dict(refined.get("session") or {})
        refined_session.update(
            {
                "event_slug": event_context["event_slug"],
                "event_label": event_context["event_label"],
                "event_code": event_context["event_code"],
                "event_location": event_context["event_location"],
                "event_status": event_context["event_status"],
                "session_code": str(session.get("session_code") or ""),
                "session_id": str(session.get("id") or ""),
                "text_id": event_context["text_id"],
                "question_set_id": event_context["question_set_id"],
                "response_scope": event_context["response_scope"],
            }
        )
        refined["session"] = refined_session
        repo.save_session_response_set(
            str(session.get("id") or ""),
            player_id,
            "un_wg2_v1",
            str(st.session_state.get("conference_device_id") or uuid.uuid4().hex[:16]),
            hashlib.sha256(access_key.encode("utf-8")).hexdigest(),
            emoji_suffix(access_key),
            refined,
            {"alias": candidate["display_name"], "contact": candidate["email"]},
        )
        _log_recovery(
            "response_refinement_submitted",
            session_id=str(session.get("id") or ""),
            player_id=player_id,
            metadata={
                "question_id": question.question_id,
                "supersedes": question.revision.supersedes if question.revision else "",
                "previous_response_id": candidate.get("response_id"),
                "append_only": True,
            },
        )
        st.session_state["wg2_review_updates"] = False
        st.session_state.pop("wg2_alignment_log_token", None)
        st.rerun()


def main() -> None:
    set_page()
    apply_conference_styles()
    ensure_session_state()
    repo = get_conference_repo()
    notion_repo = get_notion_repo()
    if not repo or not notion_repo or not repo.is_ready():
        st.error(
            "WG2 member recovery is unavailable because the repository is not ready."
        )
        return
    session = repo.resolve_session(session_code=UN_WG2_SESSION_CODE)
    if not session:
        st.error("The WG2 session could not be resolved.")
        return
    bundle = resolve_question_set_bundle(session=session)
    question_set = bundle.question_set
    session_id = str(session.get("id") or "")
    events = list_logged_events(
        page=RECOVERY_LOG_PAGE, session_id=session_id, limit=500
    )

    recovery_token = str(st.query_params.get("recovery") or "").strip()
    if recovery_token:
        try:
            recovered = verify_recovery_token(
                recovery_token,
                secret=_recovery_secret(),
                expected_session_id=session_id,
            )
        except ValueError as exc:
            st.error(str(exc))
            return
        token_state = recovery_token_state(events, recovery_token)
        if token_state != "issued":
            st.error(
                "This recovery link has already been used or was not issued by the WG2 host."
            )
            return
        player_id = str(recovered["player_id"])
        player = notion_repo.get_player_by_id(player_id)
        if not player or not player.get("access_key"):
            st.error("The existing WG2 participant could not be resolved.")
            return
        recorded = _log_recovery(
            "recovery_link_redeemed",
            session_id=session_id,
            player_id=player_id,
            metadata={"token_hash": recovery_token_fingerprint(recovery_token)},
        )
        if not recorded:
            st.error(
                "This link could not be redeemed because the recovery ledger is unavailable. "
                "No access was granted; please try again."
            )
            return
        remember_access({"player": player, "access_key": player["access_key"]})
        st.session_state["wg2_member_player_id"] = player_id
        st.query_params.clear()
        st.rerun()

    recovered_player_id = str(st.session_state.get("wg2_member_player_id") or "")
    active_player_id = str(
        recovered_player_id or st.session_state.get("player_page_id") or ""
    )
    candidates: list[dict] | None = None
    if active_player_id:
        candidates = _candidate_data(repo, notion_repo, session, question_set)
        route_state, candidate = resolve_member_route_state(
            active_player_id=active_player_id,
            player_role=str(st.session_state.get("player_role") or ""),
            candidates=candidates,
            explicitly_recovered=bool(recovered_player_id),
        )
        if route_state == "member" and candidate:
            _render_member_trajectory(repo, session, candidate, question_set)
            return
        if route_state == "not_wg2_participant":
            st.warning("This participant has no response in the WG2 session.")
            return
    conference_header(
        "Reconnect to your WG2 trajectory",
        "Return to the contribution you already made without creating another identity.",
        step="member recovery",
    )
    if not _pilot_access_allowed(events):
        return
    if candidates is None:
        candidates = _candidate_data(repo, notion_repo, session, question_set)
    _render_claim_start(candidates, session_id, events)


if __name__ == "__main__":
    main()
