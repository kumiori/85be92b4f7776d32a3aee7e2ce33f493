from __future__ import annotations

import inspect
from pathlib import Path
from typing import Dict, Optional, Tuple

import streamlit as st
import yaml
from importlib.metadata import PackageNotFoundError, version
from yaml.loader import SafeLoader


from infra.key_auth import AuthenticateWithKey
from infra.key_codec import hex_to_emoji, hex_to_phrase, normalize_access_key
from infra.notion_repo import NotionRepo, init_notion_repo
from infra.app_context import get_auth_runtime_config

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.yaml"
DEFAULT_SESSION_CODE = st.secrets.get("notion", {}).get(
    "default_session_code", "GLOBAL-SESSION"
)


def _pkg_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "not installed"
    except Exception as exc:  # pragma: no cover
        return f"error: {exc}"


@st.cache_data(show_spinner=False)
def load_config(path: str) -> Dict:
    if not Path(path).exists():
        return {}
    with open(path, "r", encoding="utf-8") as file:
        return yaml.load(file, Loader=SafeLoader) or {}


def _resolve_id_with_source(
    notion_keys: list[str]
) -> Tuple[str, str]:
    notion_secrets = st.secrets.get("notion", {})
    for key in notion_keys:
        value = notion_secrets.get(key)
        if value:
            return str(value), f"st.secrets['notion']['{key}']"
    return "", "<missing>"


def ensure_shared_state() -> None:
    ss = st.session_state
    ss.setdefault("player_id", "")
    ss.setdefault("nickname", "")
    ss.setdefault("mode", "Non-linear")
    ss.setdefault("session_code", DEFAULT_SESSION_CODE)
    ss.setdefault("access_payload", None)


ensure_shared_state()

config = load_config(str(CONFIG_PATH))

resolved_session_db_id, session_source = _resolve_id_with_source(
    notion_keys=["ice_sessions_db_id", "sessions_db_id", "sessions"],
)
resolved_players_db_id, players_source = _resolve_id_with_source(
    notion_keys=["ice_players_db_id", "players_db_id", "players"],
)

notion_repo = init_notion_repo(
    session_db_id=resolved_session_db_id,
    players_db_id=resolved_players_db_id,
)


def remember_access(payload: Dict) -> None:
    st.session_state.access_payload = payload
    player = payload.get("player") or {}
    st.session_state.player_id = player.get("player_id") or st.session_state.player_id
    st.session_state.nickname = player.get("nickname") or st.session_state.nickname
    st.session_state.mode = player.get("preferred_mode") or st.session_state.mode
    st.session_state.session_code = DEFAULT_SESSION_CODE
    session_id = getattr(authenticator.auth_model, "session_id", None)
    if session_id:
        st.session_state.session_id = session_id


st.set_page_config(page_title="Access Keys · Idea Resonance", page_icon="🔑")
st.title("🔑 Access Keys · Idea Resonance")
st.caption("Mint or enter an access key, then jump straight into the idea round.")

with st.expander("Debug: Notion connection", expanded=True):
    st.write("Resolved IDs")
    st.code(
        (
            f"ice_sessions_db_id={resolved_session_db_id or '<missing>'}\n"
            f"ice_sessions_db_id source={session_source}\n"
            f"ice_players_db_id={resolved_players_db_id or '<missing>'}\n"
            f"ice_players_db_id source={players_source}"
        )
    )
    st.write("Python package versions")
    st.code(
        (
            f"streamlit={_pkg_version('streamlit')}\n"
            f"notion-client={_pkg_version('notion-client')}\n"
            f"streamlit-notion={_pkg_version('streamlit-notion')}\n"
            f"streamlit-authenticator={_pkg_version('streamlit-authenticator')}"
        )
    )
    if notion_repo:
        client = notion_repo.client
        databases_endpoint = getattr(client, "databases", None)
        query_method = getattr(databases_endpoint, "query", None)
        data_sources_endpoint = getattr(client, "data_sources", None)
        ds_query_method = getattr(data_sources_endpoint, "query", None)
        st.code(
            (
                f"client_type={type(client).__module__}.{type(client).__name__}\n"
                f"databases_endpoint_type={type(databases_endpoint).__module__}.{type(databases_endpoint).__name__ if databases_endpoint else 'None'}\n"
                f"has_databases_query={bool(query_method)}\n"
                f"query_signature={inspect.signature(query_method) if query_method else '<missing>'}\n"
                f"data_sources_endpoint_type={type(data_sources_endpoint).__module__}.{type(data_sources_endpoint).__name__ if data_sources_endpoint else 'None'}\n"
                f"has_data_sources_query={bool(ds_query_method)}\n"
                f"data_sources_query_signature={inspect.signature(ds_query_method) if ds_query_method else '<missing>'}"
            )
        )
    else:
        st.error("Notion repo could not be initialized.")

if not resolved_session_db_id or not resolved_players_db_id:
    st.error("Missing required Notion IDs. Set notion.ice_sessions_db_id and notion.ice_players_db_id in secrets.")
    st.stop()

try:
    auth_cfg = get_auth_runtime_config()
    authenticator = AuthenticateWithKey(
        config["credentials"],
        auth_cfg["cookie_name"],
        auth_cfg["cookie_key"],
        auth_cfg["cookie_expiry_days"],
        notion_repo=notion_repo,
        default_session_code=auth_cfg["default_session_code"],
    )
except Exception as exc:
    st.error(f"Authenticator init failed: {type(exc).__name__}: {exc}")
    st.exception(exc)
    st.stop()

name, authentication_status, username = authenticator.login(
    key="access-key-login", callback=remember_access
)

if authentication_status:
    authenticator.logout(button_name="Logout", location="sidebar")
    st.success(
        f"Access granted for **{name or username}** — continue to the round when ready."
    )
    player = (st.session_state.access_payload or {}).get("player", {})
    st.json(player)
    st.write(
        "Emoji:",
        (st.session_state.access_payload or {}).get("emoji", "—"),
        " · Phrase:",
        (st.session_state.access_payload or {}).get("phrase", "—"),
    )
elif authentication_status is False:
    st.error("Key invalid. Double-check spelling or mint a new key below.")
else:
    st.info("Enter an access key above to unlock the idea round.")

st.divider()

st.subheader("Need a key?")
st.write("Request one below; the system mints and stores it in Notion automatically.")

with st.form("access_request_form"):
    req_name = st.text_input("Preferred name or collective")
    req_email = st.text_input("Contact email")
    req_intent = st.text_area("What will you explore with this key?", height=120)
    req_mode = st.selectbox("Preferred mode", ["Non-linear", "Linear"])
    req_submit = st.form_submit_button("Mint key")

if req_submit:
    if not req_email.strip():
        st.error("Email is required so we can reach you.")
    else:
        if not notion_repo:
            st.error("Notion repo unavailable; cannot mint key right now.")
        else:
            metadata = {
                "name": req_name.strip(),
                "email": req_email.strip(),
                "intent": req_intent.strip(),
                "mode": req_mode,
            }
            try:
                access_key, _, payload = authenticator.register_user(metadata=metadata)
            except Exception as exc:
                st.error(f"Minting failed: {exc}")
            else:
                st.success("Key minted! Store the details below safely.")
                st.code(access_key)
                st.write("Emoji projection:", payload.get("emoji"))
                st.write("Passphrase:", payload.get("phrase"))
                st.info(
                    "Keys are saved in Notion (`db_name`) and can be used immediately in the login form above."
                )

st.divider()

st.subheader("Validate an existing key")
existing_key = st.text_input("Paste any access key / emoji string / passphrase")
if st.button("Validate key", disabled=not existing_key.strip()):
    if not notion_repo:
        st.error("Notion repo unavailable; cannot validate.")
    else:
        try:
            canonical = normalize_access_key(existing_key)
        except ValueError as exc:
            st.error(str(exc))
        else:
            player = notion_repo.get_player_by_id(canonical)
            if not player:
                st.error("Key not found.")
            else:
                st.success("Key is valid and stored in Notion.")
                st.json(player)
                st.write("Emoji:", hex_to_emoji(canonical))
                st.write("Phrase:", hex_to_phrase(canonical))
