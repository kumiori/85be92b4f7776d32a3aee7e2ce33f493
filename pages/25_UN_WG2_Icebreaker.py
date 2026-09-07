from __future__ import annotations

from conference.context import get_conference_bundle, get_conference_repo
import streamlit as st

from conference.events import (
    UN_WG2_DEBUG_EVENT_SLUG,
    UN_WG2_DEBUG_SESSION_CODE,
    UN_WG2_SESSION_CODE,
    conference_event_context,
)
from conference.public_routes import ensure_public_route_query
from conference.questionnaire import run_conference_questionnaire_page
from conference.test_sessions import debug_session_access_enabled
from infra.event_logger import list_logged_events, log_event


RECOVERY_LOG_PAGE = "un_wg2_recovery"
ROUTE_SESSION_KEY = "un_wg2_route_session_code"


def _un_wg2_session_code(_repo) -> str:
    return str(st.session_state.get(ROUTE_SESSION_KEY) or UN_WG2_SESSION_CODE)


def _test_entry_requested() -> bool:
    token = str(st.query_params.get("test", "") or "").strip().lower()
    return token in {"1", "true", "yes", "on"}


def _resolve_route_session() -> tuple[str, bool]:
    if not _test_entry_requested():
        return UN_WG2_SESSION_CODE, False
    production_bundle = get_conference_bundle(session_code=UN_WG2_SESSION_CODE)
    production = (
        production_bundle.get("session")
        if isinstance(production_bundle, dict)
        else None
    )
    production_id = str((production or {}).get("id") or "")
    if not production_id:
        return UN_WG2_SESSION_CODE, False
    events = list_logged_events(
        page=RECOVERY_LOG_PAGE,
        session_id=production_id,
        limit=500,
    )
    if debug_session_access_enabled(events):
        return UN_WG2_DEBUG_SESSION_CODE, True
    return UN_WG2_SESSION_CODE, False


def main() -> None:
    session_code, test_allowed = _resolve_route_session()
    st.session_state[ROUTE_SESSION_KEY] = session_code
    if _test_entry_requested() and not test_allowed:
        st.warning(
            "WG2 test entry is closed. Ask a host to enable it from WG2 Host → "
            "Member recovery. This page remains in the production scope."
        )
    test_mode = session_code == UN_WG2_DEBUG_SESSION_CODE
    ensure_public_route_query(
        "un-wg2-icebreaker",
        event_slug_override=UN_WG2_DEBUG_EVENT_SLUG if test_mode else "",
    )
    repo = get_conference_repo()
    bundle = get_conference_bundle(session_code=session_code)
    session = bundle.get("session") if isinstance(bundle, dict) else None
    if repo and session:
        context = conference_event_context(session=session)
        log_event(
            module="iceicebaby.un_wg2",
            event_type="page_view",
            page="un_wg2_questionnaire",
            session_id=str(session.get("id") or ""),
            status="ok",
            metadata={
                "campaign_slug": "un-cryosphere-decade",
                "event_slug": context.get("event_slug"),
                "session_code": context.get("session_code"),
                "text_id": context.get("text_id"),
                "question_set_id": context.get("question_set_id"),
                "test_mode": bool(context.get("test_mode")),
                "response_scope": context.get("response_scope"),
                "data_classification": "debug" if context.get("test_mode") else "production",
            },
        )
    run_conference_questionnaire_page(
        session_code_resolver=_un_wg2_session_code,
        public_route_path="un-wg2-icebreaker",
    )


if __name__ == "__main__":
    main()
