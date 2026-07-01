from __future__ import annotations

from conference.events import DALAMBERTIENNES_SESSION_CODE
from conference.public_routes import ensure_public_route_query
from conference.questionnaire import run_conference_questionnaire_page


def _climate_session_code(_repo) -> str:
    return DALAMBERTIENNES_SESSION_CODE


def main() -> None:
    ensure_public_route_query("climate")
    run_conference_questionnaire_page(
        session_code_resolver=_climate_session_code,
        public_route_path="climate",
    )


if __name__ == "__main__":
    main()
