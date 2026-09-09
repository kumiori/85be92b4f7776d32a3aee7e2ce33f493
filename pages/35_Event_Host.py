from __future__ import annotations

from urllib.parse import quote
import streamlit as st

from conference.context import get_conference_bundle, get_conference_repo
from conference.events import event_config_for_request
from conference.recovery import (
    issue_recovery_token,
    recovery_candidates_by_email,
    recovery_message,
    recovery_token_fingerprint,
)
from conference.ui import apply_conference_styles, conference_header
from infra.app_context import get_authenticator, get_notion_repo
from infra.app_state import ensure_auth, ensure_session_state, require_login
from conference.wg2_ux import host_role_allowed
from ui import set_page
from infra.event_logger import log_event


def main(*, event_slug_override: str = "") -> None:
    set_page()
    apply_conference_styles()
    ensure_session_state()
    authenticator = get_authenticator(get_notion_repo())
    ensure_auth(authenticator, key="conference-event-host-login")
    require_login()
    if not host_role_allowed(str(st.session_state.get("player_role") or "")):
        st.error("Host or admin access only.")
        return
    slug = str(event_slug_override or st.query_params.get("event") or "prediction").strip().lower()
    config = event_config_for_request(slug, test=st.query_params.get("test", ""))
    repo = get_conference_repo()
    bundle = get_conference_bundle(session_code=config.session_code if config else "")
    session = bundle.get("session") if isinstance(bundle, dict) else None
    if not config or not repo or not session:
        st.error("Event session is unavailable.")
        return
    conference_header(f"{config.title} host", "Host-assisted recovery", step="host")
    if config.test_mode:
        st.caption("TEST MODE · recovery is scoped to the isolated test session")
    email = st.text_input("Participant email")
    if not email:
        return
    try:
        matches = recovery_candidates_by_email(repo.notion_repo, email)
    except ValueError as exc:
        st.warning(str(exc))
        return
    scoped = [
        item for item in matches
        if str(session.get("id") or "") in set(item.get("session_ids") or [])
    ]
    if len(scoped) != 1:
        st.warning("Recovery requires exactly one participant in this event scope.")
        return
    player = scoped[0]
    st.write(str(player.get("nickname") or "Participant"))
    if st.button("Prepare one-time recovery link", type="primary"):
        recovery_config = st.secrets.get("conference_recovery", {})
        cookie_config = st.secrets.get("cookie", {})
        secret = str(
            recovery_config.get("secret") or cookie_config.get("key") or ""
        ).strip()
        token = issue_recovery_token(
            player_id=str(player.get("id") or ""),
            session_id=str(session.get("id") or ""),
            secret=secret,
        )
        recorded = log_event(
            module="iceicebaby.conference.recovery",
            event_type="recovery_link_issued",
            page="conference_recovery",
            player_id=str(player.get("id") or ""),
            session_id=str(session.get("id") or ""),
            metadata={
                "token_hash": recovery_token_fingerprint(token),
                "event_slug": config.slug,
            },
        )
        if not recorded:
            st.error("The recovery link could not be audited, so it was not exposed.")
            return
        test_query = "&test=1" if config.test_mode else ""
        route = f"/prediction?recovery={quote(token)}{test_query}"
        subject, body = recovery_message(config.title, str(player.get("nickname") or "Participant"), route)
        st.text_input("Subject", value=subject)
        st.text_area("Message", value=body, height=220)
        st.caption("Copy once and send through the conference's trusted channel.")


if __name__ == "__main__":
    main()
