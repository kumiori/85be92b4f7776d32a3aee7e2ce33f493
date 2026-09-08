from __future__ import annotations

from conference.participation import normalize_email
from conference.wg2_members import (
    issue_recovery_token,
    recovery_token_fingerprint,
    recovery_token_state,
    verify_recovery_token,
)


def recovery_candidates_by_email(notion_repo, email: str) -> list[dict]:
    """Host-only lookup; email never grants access by itself."""
    return list(notion_repo.find_players_by_email(normalize_email(email)))


def recovery_message(event_title: str, display_name: str, recovery_url: str) -> tuple[str, str]:
    subject = f"Your {event_title} recovery link"
    body = (
        f"Hello {display_name or 'participant'},\n\n"
        f"Use this one-time link to reconnect to your existing {event_title} participation:\n\n"
        f"{recovery_url}\n\n"
        "The link expires in one hour and does not contain your access key."
    )
    return subject, body


__all__ = [
    "issue_recovery_token",
    "recovery_candidates_by_email",
    "recovery_message",
    "recovery_token_fingerprint",
    "recovery_token_state",
    "verify_recovery_token",
]
