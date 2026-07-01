from __future__ import annotations

from conference.events import current_complexity_session_code
from conference.questionnaire import run_conference_questionnaire_page


def main() -> None:
    run_conference_questionnaire_page(
        session_code_resolver=current_complexity_session_code,
        event_selector_key="conference-event-selector",
    )


if __name__ == "__main__":
    main()
