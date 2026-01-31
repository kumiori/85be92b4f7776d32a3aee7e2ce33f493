from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import streamlit as st
import yaml
from yaml.loader import SafeLoader

from infra.key_auth import AuthenticateWithKey
from infra.notion_repo import init_notion_repo
from ui import display_centered_prompt, morph3_block, morph3_defaults


STAGES = [
    "arrival",
    "voice",
    "hinge",
    "invitation",
    "persona",
    "trigger",
    "commit",
]

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.yaml"
DEFAULT_SESSION_CODE = st.secrets.get("notion", {}).get(
    "default_session_code", "GLOBAL-SESSION"
)

VOICE_AUDIO_PATH = "assets/voice_intro.mp3"

VOICE_SCRIPT: List[Tuple[float, str]] = [
    (0.0, "Take a breath."),
    (4.0, "We do not need to understand all of it yet."),
    (8.0, "You do not need to decide."),
]
VOICE_DURATION = 9.0

with open("assets/street.css", "r", encoding="utf-8") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def _load_config(path: str) -> Dict:
    with open(path, "r", encoding="utf-8") as file:
        return yaml.load(file, Loader=SafeLoader)


def _load_personae(path: str) -> List[Dict]:
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    return payload.get("personae", [])


def _pick_persona(personae: List[Dict]) -> Optional[Dict]:
    if not personae:
        return None
    if "persona_pick" not in st.session_state:
        st.session_state["persona_pick"] = personae[0].get("id")
    pick_id = st.session_state["persona_pick"]
    return next((p for p in personae if p.get("id") == pick_id), personae[0])


def _ensure_state() -> None:
    st.session_state.setdefault("stage", "arrival")
    st.session_state.setdefault("soft_exit", False)
    st.session_state.setdefault("voice_started_at", None)
    st.session_state.setdefault("hinge_started_at", None)
    st.session_state.setdefault("mint_payload", None)
    st.session_state.setdefault("mint_access_key", None)


def _set_stage(stage: str) -> None:
    st.session_state["stage"] = stage
    st.rerun()


def _remember_access(payload: dict) -> None:
    st.session_state.access_payload = payload
    player = payload.get("player") or {}
    st.session_state.player_id = player.get("player_id", "")
    st.session_state.nickname = player.get("nickname", "")


def _audio_button(label: str, path: str, key: str) -> None:
    if not path:
        return
    if st.button(label, key=key, use_container_width=True):
        try:
            with open(path, "rb") as audio_file:
                st.audio(audio_file.read())
        except FileNotFoundError:
            st.caption("Audio not found.")


def _stage_arrival(authenticator: AuthenticateWithKey) -> None:
    shell = st.empty()
    with shell.container():
        st.markdown(
            """
            <style>
            .stage-fade {
              animation: stageFade 0.35s ease;
            }
            @keyframes stageFade {
              from { opacity: 0; transform: translateY(6px); }
              to { opacity: 1; transform: translateY(0); }
            }
            </style>
            <div class="stage-fade">
            """,
            unsafe_allow_html=True,
        )
        st.markdown("### Access key")
        if st.session_state.get("authentication_status"):
            name = st.session_state.get("name")
            username = st.session_state.get("username")
            st.success(f"Access granted for **{name or username}**.")
            st.write(
                "Emoji:",
                (st.session_state.access_payload or {}).get("emoji", "—"),
                " · Phrase:",
                (st.session_state.access_payload or {}).get("phrase", "—"),
            )
            authenticator.logout(button_name="Logout", location="sidebar")
        else:
            name, authentication_status, username = authenticator.login(
                key="v2-access-key", callback=_remember_access
            )
            if authentication_status:
                st.success(f"Access granted for **{name or username}**.")
                authenticator.logout(button_name="Logout")

            elif authentication_status is False:
                st.error("Key invalid. Double-check spelling.")
            else:
                st.info("Enter an access key above to unlock.")

        st.caption(
            "An Idea is like a rock: it bends Timespace. And as it travels the Universe, it becomes smoother and smoother. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . _Morphing $L^p$ norm with noisy scanline rendering_."
        )

        st.markdown("## <center>`This is:`</center>", unsafe_allow_html=True)
        display_centered_prompt("subject to change.")

        st.markdown(
            """
            ### We're experimenting with ...
            ----
            """
        )

        st.markdown(
            "This is a short experience. It lasts about three minutes. Make space."
        )
        # st.markdown("You may close your eyes.")
        if st.session_state.get("soft_exit"):
            st.caption("No pressure. You can return whenever you are ready.")
        if st.button(
            "Tap to hear the voice.", type="primary", use_container_width=True
        ):
            shell.empty()
            st.session_state["voice_started_at"] = None
        st.markdown("</div>", unsafe_allow_html=True)


def _stage_commit(authenticator: AuthenticateWithKey, notion_repo_ok: bool) -> None:
    if st.session_state.get("mint_access_key") is None:
        if not notion_repo_ok:
            st.error("Notion repo unavailable; cannot mint token right now.")
        else:
            try:
                access_key, _, payload = authenticator.register_user(metadata={})
            except Exception as exc:
                st.error(f"Minting failed: {exc}")
            else:
                st.session_state["mint_access_key"] = access_key
                st.session_state["mint_payload"] = payload

    st.markdown("Token minted.")
    emoji = (st.session_state.get("mint_payload") or {}).get("emoji", "")
    if emoji:
        st.markdown(f"Emoji tail: `{emoji[-4:]}`")
    st.caption("The game remembers you.")

    if st.button("Close.", use_container_width=True):
        st.session_state.clear()
        _ensure_state()
        _set_stage("arrival")


def main() -> None:
    st.set_page_config(page_title="Subject to Change (v1)", layout="centered")
    _ensure_state()

    try:
        config = _load_config(str(CONFIG_PATH))
    except FileNotFoundError:
        st.error(f"{CONFIG_PATH} missing. Add it to the repo root and reload.")
        return

    notion_repo = init_notion_repo(
        session_db_id=config["notion"]["sessions"],
        players_db_id=config["notion"]["players"],
    )

    authenticator = AuthenticateWithKey(
        config["credentials"],
        config["cookie"]["name"],
        config["cookie"]["key"],
        config["cookie"]["expiry_days"],
        notion_repo=notion_repo,
        default_session_code=DEFAULT_SESSION_CODE,
    )

    with st.sidebar.expander("Minted token", expanded=False):
        mint_payload = st.session_state.get("mint_payload") or {}
        mint_key = st.session_state.get("mint_access_key") or ""
        if mint_key:
            st.text_input("Access key", value=mint_key, label_visibility="visible")
            st.text_input(
                "Passphrase",
                value=mint_payload.get("phrase", ""),
                label_visibility="visible",
            )
        else:
            st.caption("No token minted yet.")

    stage = st.session_state.get("stage", "arrival")

    with st.sidebar:
        st.markdown("## Stages")
        st.write(stage.title())
        for s in STAGES:
            if st.sidebar.button(
                s.replace("_", " ").title(),
                key=f"stage-btn-{s}",
                use_container_width=True,
            ):
                _set_stage(s)

    if stage == "arrival":
        _stage_arrival(authenticator)
    elif stage == "voice":
        pass
    elif stage == "hinge":
        pass
    elif stage == "invitation":
        pass
    elif stage == "persona":
        st.write("next stage")
    elif stage == "trigger":
        st.write("next stage")
    elif stage == "commit":
        _stage_commit(authenticator, notion_repo is not None)
    else:
        _set_stage("arrival")


if __name__ == "__main__":
    main()
