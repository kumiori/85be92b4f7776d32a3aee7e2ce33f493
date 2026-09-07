from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from typing import Any

import pandas as pd
import streamlit as st

from conference.context import get_conference_bundle, get_conference_repo
from conference.events import (
    UN_WG2_DEBUG_SESSION_CODE,
    UN_WG2_SESSION_CODE,
    conference_event_context,
    text_ids_for_session_code,
)
from conference.registry import resolve_question_set_bundle
from conference.session_window import filter_rows_to_session_window
from conference.test_sessions import (
    debug_session_access_enabled,
    ensure_test_session,
    wg2_debug_session_spec,
)
from conference.ui import apply_conference_styles, conference_header
from conference.wg2_members import (
    approve_identity_claim_with_audit,
    build_wg2_member_candidates,
    issue_recovery_token,
    public_claiming_enabled,
    recovery_message,
    recovery_token_fingerprint,
    reduce_recovery_events,
)
from conference.wg2_ux import host_role_allowed
from infra.app_context import get_authenticator, get_notion_repo
from infra.app_state import ensure_auth, ensure_session_state, remember_access, require_login
from infra.event_logger import list_logged_events, log_event
from ui import set_page, sidebar_debug_state


RECOVERY_LOG_PAGE = "un_wg2_recovery"


def _resolve_un_wg2_session() -> dict[str, Any] | None:
    bundle = get_conference_bundle(session_code=UN_WG2_SESSION_CODE)
    session = bundle.get("session") if isinstance(bundle, dict) else None
    return session if isinstance(session, dict) else None


def _event_scope_text(session: dict[str, Any]) -> str:
    context = conference_event_context(session=session)
    location = str(context.get("event_location") or "").strip()
    if location:
        return f"{context['event_label']} in {location}"
    return str(context.get("event_label") or context.get("event_code") or "this event")


def _pretty(token: str) -> str:
    return str(token or "").replace("_", " ").strip().title()


WG2_GROUPS = (
    "I. Who is speaking?",
    "II. Spatial context",
    "III. Needs",
    "IV. Action",
)

WG2_STEP_GROUPS = {
    "role_lens": "I. Who is speaking?",
    "expertise": "I. Who is speaking?",
    "support_needs": "I. Who is speaking?",
    "work_style": "I. Who is speaking?",
    "main_location": "II. Spatial context",
    "region": "II. Spatial context",
    "cryosphere_domain": "II. Spatial context",
    "needs": "III. Needs",
    "policy_interface": "III. Needs",
    "uncertainty": "III. Needs",
    "timescale": "III. Needs",
    "stakeholder_group": "IV. Action",
    "contribution": "IV. Action",
    "coordination_signal": "IV. Action",
    "coordination_resonance": "IV. Action",
}


def _active_flow_steps(resolved_bundle: Any) -> list[str]:
    question_set = resolved_bundle.question_set
    default_mode = str(getattr(question_set, "default_mode", "") or "quick")
    mode_payload = question_set.flow_modes.get(default_mode) or next(
        iter(question_set.flow_modes.values()),
        {},
    )
    return [str(step) for step in mode_payload.get("steps", [])]


def _question_by_step(resolved_bundle: Any) -> dict[str, Any]:
    return {
        str(question.step): question
        for question in resolved_bundle.question_set.questions
    }


def _question_groups(resolved_bundle: Any) -> dict[str, list[Any]]:
    by_step = _question_by_step(resolved_bundle)
    grouped: dict[str, list[Any]] = {group: [] for group in WG2_GROUPS}
    for step in _active_flow_steps(resolved_bundle):
        question = by_step.get(step)
        if not question:
            continue
        group = WG2_STEP_GROUPS.get(step, "Other")
        grouped.setdefault(group, []).append(question)
    return grouped


def _disabled_questions(resolved_bundle: Any) -> list[Any]:
    active_steps = set(_active_flow_steps(resolved_bundle))
    return [
        question
        for question in resolved_bundle.question_set.questions
        if str(question.step) not in active_steps
    ]


def _mode_step_labels(resolved_bundle: Any, mode: str) -> list[str]:
    question_set = resolved_bundle.question_set
    steps = question_set.flow_modes.get(mode, {}).get("steps", [])
    labels: list[str] = []
    for step in steps:
        copy = question_set.step_copy.get(str(step), {})
        labels.append(str(copy.get("title") or _pretty(str(step))))
    return labels


def _active_question_count(resolved_bundle: Any) -> int:
    by_step = _question_by_step(resolved_bundle)
    return sum(1 for step in _active_flow_steps(resolved_bundle) if step in by_step)


def _question_options(question: Any) -> str:
    options = getattr(question, "options", ())
    if not options:
        return ""
    return ", ".join(str(item.get("label") or item.get("value") or "") for item in options)


def _question_rows(resolved_bundle: Any) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    shared_ids = set(resolved_bundle.shared_question_ids)
    active_steps = set(_active_flow_steps(resolved_bundle))
    for index, question in enumerate(resolved_bundle.question_set.questions, start=1):
        step = str(question.step)
        rows.append(
            {
                "order": str(index),
                "question_id": str(question.question_id),
                "step": step,
                "field": str(question.field),
                "origin": "shared" if str(question.question_id) in shared_ids else "event",
                "question_group": WG2_STEP_GROUPS.get(step, "YAML-only / other"),
                "active": "yes" if step in active_steps else "no",
                "yaml_group": str(getattr(question, "group", "") or ""),
                "subgroup": str(getattr(question, "subgroup", "") or ""),
                "input_type": str(question.input_type),
                "required": "yes" if bool(question.required) else "no",
                "prompt": str(question.prompt),
                "detail_field": str(getattr(question, "free_text_field", "") or ""),
            }
        )
    return rows


def _log_credential_event(
    *,
    event_type: str,
    session: dict[str, Any],
    context: dict[str, Any],
    player_id: str = "",
    status: str = "ok",
    metadata: dict[str, Any] | None = None,
) -> None:
    log_event(
        module="iceicebaby.un_wg2.credentials",
        event_type=event_type,
        page="un_wg2_host",
        session_id=str(session.get("id") or ""),
        player_id=str(player_id or ""),
        status=status,
        metadata={
            "event_slug": str(context.get("event_slug") or ""),
            "session_code": str(context.get("session_code") or ""),
            **(metadata or {}),
        },
        level="ERROR" if status == "error" else "INFO",
    )


def _log_recovery_event(
    *,
    event_type: str,
    session: dict[str, Any],
    context: dict[str, Any],
    player_id: str = "",
    status: str = "ok",
    metadata: dict[str, Any] | None = None,
) -> bool:
    return log_event(
        module="iceicebaby.un_wg2.recovery",
        event_type=event_type,
        page=RECOVERY_LOG_PAGE,
        session_id=str(session.get("id") or ""),
        player_id=str(player_id or ""),
        status=status,
        metadata={
            "event_slug": str(context.get("event_slug") or ""),
            "session_code": str(context.get("session_code") or ""),
            **(metadata or {}),
        },
        level="ERROR" if status == "error" else "INFO",
    )


def _recovery_secret() -> str:
    cookie = st.secrets.get("cookie", {})
    return str(cookie.get("key") or "").strip()


def _recovery_route(token: str) -> str:
    config = st.secrets.get("wg2_recovery", {})
    base_url = str(config.get("base_url") or "").strip().rstrip("/")
    relative = f"/un-wg2-member?recovery={quote(token)}"
    return f"{base_url}{relative}" if base_url else relative


def _redact_response(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: ("[redacted]" if str(key) == "access_key" else _redact_response(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_response(item) for item in value]
    return value


def _render_member_recovery_support(
    *,
    notion_repo: Any,
    session: dict[str, Any],
    context: dict[str, Any],
    recovery_events: list[dict[str, Any]],
    submissions: list[dict[str, Any]],
    resolved_bundle: Any,
) -> None:
    session_id = str(session.get("id") or "")
    candidates = build_wg2_member_candidates(
        submissions=submissions,
        players=notion_repo.list_all_players(limit=500),
        current_schema=resolved_bundle.question_set,
        session_id=session_id,
    )
    states = reduce_recovery_events(recovery_events)
    states_by_player: dict[str, list[dict[str, Any]]] = {}
    for state in states.values():
        states_by_player.setdefault(str(state.get("player_id") or ""), []).append(state)

    st.markdown("### WG2 member recovery")
    with st.container(border=True):
        st.markdown("#### Test mode")
        debug_session = notion_repo.get_session_by_code(UN_WG2_DEBUG_SESSION_CODE)
        if not debug_session:
            st.caption(
                "The test questionnaire needs its own persisted session before it can open."
            )
            if st.button("Create WG2 test session", type="primary"):
                try:
                    debug_session, created = ensure_test_session(
                        notion_repo,
                        wg2_debug_session_spec(),
                    )
                except Exception as exc:
                    st.error(f"The WG2 test session could not be created: {exc}")
                else:
                    _log_recovery_event(
                        event_type="debug_session_created" if created else "debug_session_reconciled",
                        session=session,
                        context=context,
                        metadata={
                            "debug_session_id": str(debug_session.get("id") or ""),
                            "debug_session_code": UN_WG2_DEBUG_SESSION_CODE,
                        },
                    )
                    st.rerun()
        else:
            st.success(
                f"Debug session ready: `{UN_WG2_DEBUG_SESSION_CODE}`. "
                "Its responses are excluded from production WG2 results."
            )
            debug_access_is_open = debug_session_access_enabled(recovery_events)
            desired_debug_access = st.toggle(
                "Allow test entry",
                value=debug_access_is_open,
                key=f"wg2-debug-access-{int(debug_access_is_open)}",
                help=(
                    "Controls both WG2 test entry points. Test data remains in the "
                    "dedicated debug session."
                ),
            )
            if desired_debug_access != debug_access_is_open:
                recorded = _log_recovery_event(
                    event_type=(
                        "debug_session_access_enabled"
                        if desired_debug_access
                        else "debug_session_access_disabled"
                    ),
                    session=session,
                    context=context,
                    metadata={
                        "debug_session_id": str(debug_session.get("id") or ""),
                        "debug_session_code": UN_WG2_DEBUG_SESSION_CODE,
                        "test_mode": True,
                        "response_scope": "debug_session",
                        "data_classification": "debug",
                    },
                )
                if recorded:
                    st.rerun()
                else:
                    st.error("The test-entry setting could not be recorded.")
            if debug_access_is_open:
                st.link_button(
                    "Open WG2 test questionnaire",
                    "/un-wg2-icebreaker?test=1",
                    type="primary",
                    use_container_width=True,
                )
                st.link_button(
                    "Open funding mixer in test mode",
                    "/wg2-funding-mixer?test=1",
                    use_container_width=True,
                )
    claiming_is_open = public_claiming_enabled(recovery_events)
    desired_claiming_state = st.toggle(
        "Allow public claiming",
        value=claiming_is_open,
        key=f"wg2-public-claiming-{int(claiming_is_open)}",
        help=(
            "When enabled, logged-out WG2 participants can open the member route and "
            "request access to an existing trajectory."
        ),
    )
    if desired_claiming_state != claiming_is_open:
        recorded = _log_recovery_event(
            event_type=(
                "public_claiming_enabled"
                if desired_claiming_state
                else "public_claiming_disabled"
            ),
            session=session,
            context=context,
            metadata={
                "public_claiming_enabled": desired_claiming_state,
                "scope": "session",
            },
        )
        if recorded:
            st.rerun()
        else:
            st.error(
                "The claiming setting could not be recorded. Its previous state remains active."
            )
    st.caption(
        "Public claiming is open to logged-out participants."
        if claiming_is_open
        else "Public claiming is closed; hosts and access-code holders can still inspect it."
    )
    st.caption(
        "This list starts from WG2 responses and resolves their existing participant records. "
        "It does not expose access keys or pull unrelated ICE participants into the workflow."
    )
    st.info(
        "Accept identity claims here. Approval attaches the proposed email to the existing "
        "ICE Player. Then prepare and send that participant's one-time recovery link below."
    )
    if not candidates:
        st.info("No WG2 response trajectories can be matched to an existing participant yet.")
        return

    table_rows: list[dict[str, Any]] = []
    for candidate in candidates:
        player_states = states_by_player.get(candidate["player_id"], [])
        latest_state = player_states[-1] if player_states else {}
        alignment = candidate["alignment"]
        table_rows.append(
            {
                "participant": candidate["display_name"],
                "identity": candidate["identity_status"],
                "responses": candidate["response_count"],
                "schema": candidate["schema"],
                "alignment": (
                    f"{len(alignment['needs_refinement'])} refinement(s), "
                    f"{len(alignment['new_questions'])} new"
                ),
                "email": candidate["email_status"],
                "recovery": latest_state.get("status") or candidate["recovery_status"],
                "last activity": candidate["last_activity"],
            }
        )
    st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)

    pending_claims = [
        state
        for state in states.values()
        if state.get("kind") == "identity_claim" and state.get("status") == "pending"
    ]
    st.markdown(f"### Pending identity claims · {len(pending_claims)}")
    if not pending_claims:
        st.caption("No identity claims are currently waiting for approval.")
    for claim in pending_claims:
        player_id = str(claim.get("player_id") or "")
        candidate = next(
            (item for item in candidates if item["player_id"] == player_id),
            None,
        )
        label = candidate["display_name"] if candidate else player_id
        with st.container(border=True):
            st.write(f"**{label}** wants to add this recovery email:")
            st.code(str(claim.get("proposed_email") or "Not available"))
            st.caption(f"Requested {claim.get('requested_at') or 'at an unknown time'}")
            action_columns = st.columns(2)
            if action_columns[0].button(
                "Approve claim",
                type="primary",
                key=f"wg2-approve-claim-{claim.get('claim_id')}",
            ):
                try:
                    approve_identity_claim_with_audit(
                        notion_repo,
                        claim,
                        lambda: _log_recovery_event(
                            event_type="identity_claim_approved",
                            session=session,
                            context=context,
                            player_id=player_id,
                            metadata={
                                "claim_id": claim.get("claim_id"),
                                "request_id": claim.get("claim_id"),
                                "email_mask": claim.get("email_mask"),
                            },
                        ),
                    )
                except (ValueError, RuntimeError) as exc:
                    _log_recovery_event(
                        event_type="identity_claim_approval_failed",
                        session=session,
                        context=context,
                        player_id=player_id,
                        status="error",
                        metadata={"claim_id": claim.get("claim_id"), "reason": str(exc)},
                    )
                    st.error(str(exc))
                else:
                    st.rerun()
            if action_columns[1].button(
                "Reject claim",
                key=f"wg2-reject-claim-{claim.get('claim_id')}",
            ):
                recorded = _log_recovery_event(
                    event_type="identity_claim_rejected",
                    session=session,
                    context=context,
                    player_id=player_id,
                    status="rejected",
                    metadata={
                        "claim_id": claim.get("claim_id"),
                        "request_id": claim.get("claim_id"),
                    },
                )
                if recorded:
                    st.rerun()
                else:
                    st.error("Rejection could not be recorded. The claim remains pending.")

    st.markdown("### Member trajectories")
    for candidate in candidates:
        player_id = candidate["player_id"]
        player_states = states_by_player.get(player_id, [])
        latest_state = player_states[-1] if player_states else {}
        alignment = candidate["alignment"]
        with st.expander(candidate["display_name"], expanded=False):
            st.write(
                f"**Alignment:** {len(alignment['current'])} current · "
                f"{len(alignment['needs_refinement'])} need refinement · "
                f"{len(alignment['new_questions'])} new · "
                f"{len(alignment['legacy_only'])} legacy only"
            )
            st.write(f"**Email:** {candidate['email_mask'] or 'Not available'}")
            st.write(f"**Recovery status:** {latest_state.get('status') or 'No request'}")
            latest_request_id = str(
                latest_state.get("request_id") or latest_state.get("claim_id") or ""
            )
            if latest_request_id and latest_state.get("status") in {
                "pending",
                "approved",
                "ready_to_send",
                "sent",
            }:
                if st.button(
                    "Revoke and allow retry",
                    key=f"wg2-revoke-recovery-{latest_request_id}",
                ):
                    recorded = _log_recovery_event(
                        event_type="recovery_workflow_revoked",
                        session=session,
                        context=context,
                        player_id=player_id,
                        status="revoked",
                        metadata={
                            "claim_id": str(latest_state.get("claim_id") or ""),
                            "request_id": str(latest_state.get("request_id") or ""),
                            "reason": "host_debug_retry",
                        },
                    )
                    if recorded:
                        prepared = st.session_state.get("wg2_prepared_recovery", {})
                        if (
                            isinstance(prepared, dict)
                            and str(prepared.get("request_id") or "")
                            == latest_request_id
                        ):
                            st.session_state.pop("wg2_prepared_recovery", None)
                        st.rerun()
                    else:
                        st.error(
                            "Revocation could not be recorded. The workflow was not reset."
                        )
                st.caption(
                    "Revocation resets this recovery workflow so it can be requested again. "
                    "It does not delete responses or remove an email already approved."
                )
            with st.expander("Inspect alignment needs", expanded=False):
                st.json(alignment)
            with st.expander("Inspect response bundle", expanded=False):
                st.json(_redact_response(candidate["submission"]))

            actionable = [
                state
                for state in player_states
                if state.get("status") in {"pending", "approved", "ready_to_send"}
                and state.get("kind") in {"recovery", "identity_claim"}
            ]
            request = actionable[-1] if actionable else None
            if not request:
                st.caption("A participant must request recovery before a link can be issued.")
                continue
            player = notion_repo.get_player_by_id(player_id)
            email = str((player or {}).get("email") or "").strip()
            if not email:
                st.warning("Approve the identity claim before preparing a recovery link.")
                continue
            request_id = str(request.get("request_id") or request.get("claim_id") or "")
            prepared = st.session_state.get("wg2_prepared_recovery", {})
            is_prepared = (
                isinstance(prepared, dict)
                and str(prepared.get("request_id") or "") == request_id
            )
            if not is_prepared and request.get("status") != "ready_to_send" and st.button(
                "Prepare one-time recovery link",
                type="primary",
                key=f"wg2-prepare-recovery-{request_id}",
            ):
                try:
                    token = issue_recovery_token(
                        player_id=player_id,
                        session_id=session_id,
                        secret=_recovery_secret(),
                    )
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    recovery_url = _recovery_route(token)
                    subject, body = recovery_message(candidate["display_name"], recovery_url)
                    recorded = _log_recovery_event(
                        event_type="recovery_link_issued",
                        session=session,
                        context=context,
                        player_id=player_id,
                        metadata={
                            "request_id": request_id,
                            "token_hash": recovery_token_fingerprint(token),
                            "expires_at": (
                                datetime.now(timezone.utc) + timedelta(hours=1)
                            ).isoformat(),
                        },
                    )
                    if recorded:
                        st.session_state["wg2_prepared_recovery"] = {
                            "request_id": request_id,
                            "player_id": player_id,
                            "email": email,
                            "subject": subject,
                            "body": body,
                        }
                        st.rerun()
                    else:
                        st.error(
                            "The recovery link could not be recorded, so it was not exposed."
                        )

            if (
                isinstance(prepared, dict)
                and str(prepared.get("request_id") or "") == request_id
            ):
                st.code(str(prepared.get("body") or ""), language="text")
                mailto = (
                    f"mailto:{quote(email)}?subject={quote(str(prepared.get('subject') or ''))}"
                    f"&body={quote(str(prepared.get('body') or ''))}"
                )
                st.markdown(f"[Open in your email app]({mailto})")
                if st.button(
                    "Mark recovery link sent",
                    key=f"wg2-mark-recovery-sent-{request_id}",
                ):
                    recorded = _log_recovery_event(
                        event_type="recovery_link_sent",
                        session=session,
                        context=context,
                        player_id=player_id,
                        metadata={"request_id": request_id},
                    )
                    if recorded:
                        st.session_state.pop("wg2_prepared_recovery", None)
                        st.rerun()
                    else:
                        st.error(
                            "Sent status could not be recorded. The link remains prepared."
                        )


def _render_question_bundle(resolved_bundle: Any) -> None:
    question_set = resolved_bundle.question_set
    active_count = _active_question_count(resolved_bundle)
    disabled = _disabled_questions(resolved_bundle)
    metrics = st.columns(4)
    metrics[0].metric("Questions", len(question_set.questions))
    metrics[1].metric("Proposed", active_count)
    metrics[2].metric("YAML-only", len(disabled))
    metrics[3].metric("Modes", len(question_set.flow_modes))

    st.markdown("### Resolved bundle")
    meta_left, meta_right = st.columns(2)
    with meta_left:
        st.code(
            "\n".join(
                [
                    "campaign_slug  = un-cryosphere-decade",
                    f"event_slug      = {resolved_bundle.event_slug}",
                    f"session_code    = {resolved_bundle.session_code}",
                    f"text_id         = {resolved_bundle.text_id}",
                    f"question_set_id = {resolved_bundle.question_set_id}",
                    f"schema_id       = {resolved_bundle.schema_id}",
                ]
            ),
            language="text",
        )
    with meta_right:
        st.code(
            "\n".join(
                [
                    f"module          = {resolved_bundle.question_set_module}",
                    f"source_kind     = {resolved_bundle.question_set_source_kind}",
                    f"source_path     = {resolved_bundle.question_set_source_path}",
                    f"source_note     = {resolved_bundle.question_set_source_note}",
                    f"shared_ids      = {len(resolved_bundle.shared_question_ids)}",
                    f"event_ids       = {len(resolved_bundle.event_specific_question_ids)}",
                ]
            ),
            language="text",
        )

    st.markdown("### Mode structure")
    mode_columns = st.columns(max(len(question_set.flow_modes), 1))
    for column, mode in zip(mode_columns, question_set.flow_modes.keys()):
        with column:
            spec = question_set.flow_modes[mode]
            st.markdown(f"**{spec['title']}**")
            st.caption(str(spec.get("detail") or ""))
            for step_label in _mode_step_labels(resolved_bundle, str(mode)):
                st.markdown(f"- {step_label}")

    st.markdown("### Question architecture")
    for root, questions in _question_groups(resolved_bundle).items():
        with st.expander(root, expanded=True):
            if not questions:
                st.caption("No active questions in this group.")
                continue
            for index, question in enumerate(questions, start=1):
                with st.container(border=True):
                    st.markdown(f"**{index}. {str(question.prompt)}**")
                    st.caption(
                        f"`{question.question_id}` · step `{question.step}` · field `{question.field}` · "
                        f"{question.input_type} · {'required' if question.required else 'optional'}"
                    )
                    if str(question.subtitle or "").strip():
                        st.caption(str(question.subtitle))
                    options = _question_options(question)
                    if options:
                        st.markdown(f"**Options:** {options}")
                    detail_field = str(getattr(question, "free_text_field", "") or "").strip()
                    if detail_field:
                        detail_label = str(getattr(question, "free_text_label", "") or "Detail")
                        st.caption(f"Detail field: `{detail_field}` · label: {detail_label}")

    with st.expander("YAML-only or disabled questions", expanded=bool(disabled)):
        if not disabled:
            st.caption("Every question present in the YAML is active in the proposed flow.")
        for question in disabled:
            with st.container(border=True):
                st.markdown(f"**{str(question.prompt)}**")
                st.caption(
                    f"`{question.question_id}` · step `{question.step}` · field `{question.field}` · "
                    "present in YAML but not active in the proposed flow"
                )
                if str(question.subtitle or "").strip():
                    st.caption(str(question.subtitle))

    with st.expander("Flat question table", expanded=False):
        st.dataframe(pd.DataFrame(_question_rows(resolved_bundle)), use_container_width=True)


def main() -> None:
    set_page()
    apply_conference_styles()
    ensure_session_state()

    notion_repo = get_notion_repo()
    authenticator = get_authenticator(notion_repo)
    ensure_auth(authenticator, callback=remember_access, key="un-wg2-host-login")
    require_login()

    repo = get_conference_repo()
    if not repo or not repo.is_ready():
        st.error(repo.unavailable_reason if repo else "Conference repository is unavailable.")
        return

    session = _resolve_un_wg2_session()
    if not session:
        st.error(
            "UN WG2 session is missing. "
            "Run `scripts/bootstrap_un_wg2_session.py` first."
        )
        return

    context = conference_event_context(session=session)
    role = str(st.session_state.get("player_role") or "")
    if not host_role_allowed(role):
        _log_credential_event(
            event_type="credential_access_denied",
            session=session,
            context=context,
            player_id=str(st.session_state.get("player_page_id") or ""),
            status="error",
            metadata={"role": role},
        )
        st.error("Host or admin access only.")
        return
    if st.session_state.get("authentication_status"):
        authenticator.logout(button_name="Logout", location="sidebar")

    resolved_bundle = resolve_question_set_bundle(session=session)
    sidebar_debug_state(
        debug_context={
            "current_page": "un_wg2_host",
            "event_log_page": "un_wg2_host",
            "campaign_slug": "un-cryosphere-decade",
            "event_slug": resolved_bundle.event_slug,
            "session_code": resolved_bundle.session_code,
            "session_id": str(session.get("id") or ""),
            "event_label": str(context.get("event_label") or ""),
            "text_id": resolved_bundle.text_id,
            "question_set_id": resolved_bundle.question_set_id,
            "schema_id": resolved_bundle.schema_id,
            "question_set_module": resolved_bundle.question_set_module,
            "question_set_source_kind": resolved_bundle.question_set_source_kind,
            "question_set_source_path": resolved_bundle.question_set_source_path,
            "question_set_source_note": resolved_bundle.question_set_source_note,
            "question_count": len(resolved_bundle.question_ids),
            "shared_question_count": len(resolved_bundle.shared_question_ids),
            "event_specific_question_count": len(resolved_bundle.event_specific_question_ids),
            "question_ids": list(resolved_bundle.question_ids),
            "shared_question_ids": list(resolved_bundle.shared_question_ids),
            "event_specific_question_ids": list(resolved_bundle.event_specific_question_ids),
        }
    )

    response_rows = repo.get_session_rows(
        str(session.get("id") or ""),
        text_ids=text_ids_for_session_code(str(session.get("session_code") or "")),
    )
    filtered_rows = filter_rows_to_session_window(response_rows, session)
    submissions = repo.group_rows_by_submission(filtered_rows)
    event_log = list_logged_events(
        page="conference",
        session_id=str(session.get("id") or ""),
        limit=100,
    )
    credential_events = list_logged_events(
        page=RECOVERY_LOG_PAGE,
        session_id=str(session.get("id") or ""),
        limit=500,
    )

    log_event(
        module="iceicebaby.un_wg2",
        event_type="host_loaded",
        page="un_wg2_host",
        session_id=str(session.get("id") or ""),
        status="ok",
        metadata={
            "campaign_slug": "un-cryosphere-decade",
            "event_slug": resolved_bundle.event_slug,
            "session_code": resolved_bundle.session_code,
            "text_id": resolved_bundle.text_id,
            "question_set_id": resolved_bundle.question_set_id,
            "submissions": len(submissions),
        },
    )

    conference_header(
        f"{context['event_label']} host",
        f"Operator view for {_event_scope_text(session)}.",
        step="host",
    )

    tabs = st.tabs(
        ["Question set", "Member recovery", "Submissions", "Event log"]
    )
    with tabs[0]:
        _render_question_bundle(resolved_bundle)
    with tabs[1]:
        _render_member_recovery_support(
            notion_repo=notion_repo,
            session=session,
            context=context,
            recovery_events=credential_events,
            submissions=submissions,
            resolved_bundle=resolved_bundle,
        )
    with tabs[2]:
        metrics = st.columns(3)
        metrics[0].metric("Submissions", len(submissions))
        metrics[1].metric("Filtered rows", len(filtered_rows))
        metrics[2].metric("Recognized text ids", len(text_ids_for_session_code(str(session.get("session_code") or ""))))
        if submissions:
            st.dataframe(pd.DataFrame(submissions), use_container_width=True)
        else:
            st.info("No UN WG2 submissions yet.")
    with tabs[3]:
        combined_log = [*credential_events, *event_log]
        if combined_log:
            st.dataframe(pd.DataFrame(combined_log), use_container_width=True)
        else:
            st.info("No recent event log entries.")


if __name__ == "__main__":
    main()
