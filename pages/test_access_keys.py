from __future__ import annotations

from pathlib import Path
import os
from typing import Dict, Optional

import streamlit as st
import yaml
from yaml.loader import SafeLoader


from infra.key_auth import AuthenticateWithKey
from infra.key_codec import hex_to_emoji, hex_to_phrase, normalize_access_key
from infra.notion_repo import NotionRepo, init_notion_repo

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.yaml"
DEFAULT_SESSION_CODE = st.secrets.get("notion", {}).get(
    "default_session_code", "GLOBAL-SESSION"
)


@st.cache_data(show_spinner=False)
def load_config(path: str) -> Dict:
    with open(path, "r", encoding="utf-8") as file:
        return yaml.load(file, Loader=SafeLoader)


def ensure_shared_state() -> None:
    ss = st.session_state
    ss.setdefault("player_id", "")
    ss.setdefault("nickname", "")
    ss.setdefault("mode", "Non-linear")
    ss.setdefault("session_code", DEFAULT_SESSION_CODE)
    ss.setdefault("access_payload", None)


ensure_shared_state()

try:
    config = load_config(str(CONFIG_PATH))
except FileNotFoundError:
    st.error("config.yaml missing. Add it to the repo root and reload.")
    st.stop()

notion_repo = init_notion_repo(
    session_db_id=(
        st.secrets.get("ICE_SESSIONS_DB_ID")
        or st.secrets.get("notion", {}).get("ICE_SESSIONS_DB_ID")
        or st.secrets.get("notion", {}).get("ice_sessions_db_id")
        or st.secrets.get("notion", {}).get("sessions_db_id")
        or st.secrets.get("notion", {}).get("sessions")
        or os.getenv("ICE_SESSIONS_DB_ID", "")
        or config.get("notion", {}).get("ice_sessions_db_id")
        or config.get("notion", {}).get("sessions_db_id")
        or config.get("notion", {}).get("sessions")
    ),
    players_db_id=(
        st.secrets.get("ICE_PLAYERS_DB_ID")
        or st.secrets.get("notion", {}).get("ICE_PLAYERS_DB_ID")
        or st.secrets.get("notion", {}).get("ice_players_db_id")
        or st.secrets.get("notion", {}).get("players_db_id")
        or st.secrets.get("notion", {}).get("players")
        or os.getenv("ICE_PLAYERS_DB_ID", "")
        or config.get("notion", {}).get("ice_players_db_id")
        or config.get("notion", {}).get("players_db_id")
        or config.get("notion", {}).get("players")
    ),
)

authenticator = AuthenticateWithKey(
    config["credentials"],
    config["cookie"]["name"],
    config["cookie"]["key"],
    config["cookie"]["expiry_days"],
    notion_repo=notion_repo,
    default_session_code=DEFAULT_SESSION_CODE,
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
