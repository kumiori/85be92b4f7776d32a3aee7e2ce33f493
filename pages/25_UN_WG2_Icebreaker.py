from __future__ import annotations

from conference.context import get_conference_bundle, get_conference_repo
from conference.events import UN_WG2_SESSION_CODE, conference_event_context
from conference.public_routes import ensure_public_route_query
from conference.questionnaire import run_conference_questionnaire_page
from infra.event_logger import log_event


def _un_wg2_session_code(_repo) -> str:
    return UN_WG2_SESSION_CODE


def main() -> None:
    ensure_public_route_query("un-wg2-icebreaker")
    repo = get_conference_repo()
    bundle = get_conference_bundle(session_code=UN_WG2_SESSION_CODE)
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
            },
        )
    run_conference_questionnaire_page(
        session_code_resolver=_un_wg2_session_code,
        public_route_path="un-wg2-icebreaker",
    )


if __name__ == "__main__":
    main()
