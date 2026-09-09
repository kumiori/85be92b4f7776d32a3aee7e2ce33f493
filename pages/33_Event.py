from __future__ import annotations

import streamlit as st

from conference.context import get_conference_bundle, get_conference_repo
from conference.events import event_config_for_request
from conference.public_routes import ensure_public_route_query
from conference.questionnaire import run_conference_questionnaire_page
from conference.recovery import verify_recovery_token
from conference.recovery import recovery_token_fingerprint, recovery_token_state
from infra.event_logger import list_logged_events, log_event


def _event_config(event_slug_override: str = ""):
    slug = str(event_slug_override or st.query_params.get("event") or "prediction").strip().lower()
    return event_config_for_request(slug, test=st.query_params.get("test", ""))


def _requested_event_slug() -> str:
    return str(st.query_params.get("event") or "prediction").strip().lower()


def _session_code(_repo, event_slug_override: str = "") -> str:
    config = _event_config(event_slug_override)
    return str(config.session_code if config else "")


def _consume_recovery(event_slug_override: str = "") -> None:
    token = str(st.query_params.get("recovery") or "").strip()
    config = _event_config(event_slug_override)
    if not token or not config:
        return
    repo = get_conference_repo()
    bundle = get_conference_bundle(session_code=config.session_code)
    session = bundle.get("session") if isinstance(bundle, dict) else None
    if not repo or not session:
        return
    recovery_config = st.secrets.get("conference_recovery", {})
    cookie_config = st.secrets.get("cookie", {})
    secret = str(
        recovery_config.get("secret") or cookie_config.get("key") or ""
    ).strip()
    try:
        recovered = verify_recovery_token(
            token, secret=secret, expected_session_id=str(session.get("id") or "")
        )
        events = list_logged_events(
            page="conference_recovery",
            session_id=str(session.get("id") or ""),
            limit=500,
        )
        if recovery_token_state(events, token) != "issued":
            raise ValueError("Recovery link is unknown or has already been used.")
        player = repo.notion_repo.get_player_by_id(str(recovered.get("player_id") or ""))
        if not player or not str(player.get("access_key") or ""):
            raise ValueError("The existing participant could not be resolved.")
        if not log_event(
            module="iceicebaby.conference.recovery",
            event_type="recovery_link_redeemed",
            page="conference_recovery",
            player_id=str(player.get("id") or ""),
            session_id=str(session.get("id") or ""),
            metadata={"token_hash": recovery_token_fingerprint(token), "event_slug": config.slug},
        ):
            raise RuntimeError("Recovery redemption could not be recorded.")
        st.session_state["conference_recovered_access_key"] = str(player["access_key"])
        st.query_params.pop("recovery", None)
        st.success("Recovery accepted. Your saved participation is being restored.")
    except Exception as exc:
        st.error(f"Recovery link unavailable: {exc}")


def main(
    *,
    event_slug_override: str = "",
    public_route_path: str = "event",
    canonical: bool = False,
) -> None:
    config = _event_config(event_slug_override)
    if not config:
        st.error("Unknown event.")
        return
    if not canonical:
        ensure_public_route_query(
            public_route_path,
            event_slug_override=event_slug_override or _requested_event_slug(),
        )
    _consume_recovery(event_slug_override)
    run_conference_questionnaire_page(
        session_code_resolver=lambda repo: _session_code(repo, event_slug_override),
        public_route_path=public_route_path,
    )


if __name__ == "__main__":
    main()
