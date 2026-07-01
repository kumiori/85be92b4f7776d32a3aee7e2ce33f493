from __future__ import annotations

from conference.events import DALAMBERTIENNES_SESSION_CODE
from conference.questionnaire import run_conference_questionnaire_page


def _dalembertiennes_session_code(_repo) -> str:
    return DALAMBERTIENNES_SESSION_CODE


def main() -> None:
    run_conference_questionnaire_page(
        session_code_resolver=_dalembertiennes_session_code,
    )


if __name__ == "__main__":
    main()
