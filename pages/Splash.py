from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

import streamlit as st

from infra.app_context import get_authenticator, get_notion_repo
from infra.app_state import ensure_session_state
from infra.credentials_pdf import build_credentials_pdf
from infra.key_codec import split_emoji_symbols
from infra.event_logger import log_event, get_module_logger
from ui import (
    apply_theme,
    heading,
    set_page,
    sidebar_debug_state,
)

MINT_RESULT_KEY = "splash_mint_result"
SHOW_MINT_DIALOG_KEY = "splash_show_mint_dialog"
SHOW_MINT_FORM_KEY = "splash_show_mint_form"
MINT_JUST_COMPLETED_KEY = "splash_mint_just_completed"
AUTH_LOGGER = get_module_logger("iceicebaby.auth")


@st.dialog("Create your access key")
def _render_mint_info_dialog() -> None:
    st.markdown(
        """
This platform is designed to be transparent and anonymous. In order to collect and aggregate valuable information, **you will create your  unique access key**.

**You may make your experience easier**:

• Name or nickname — so the platform can greet you when you return.

• Motivation — one short line about why you are joining the conversation.

• Email — optional, used only to send you a reminder of your credentials.

All answers remain anonymous and associated only with your key.
"""
    )
    if st.button(
        "Understood, let's create the key",
        type="primary",
        use_container_width=True,
        key="splash-open-mint-form",
    ):
        st.session_state[SHOW_MINT_FORM_KEY] = True
        st.session_state[SHOW_MINT_DIALOG_KEY] = False
        st.rerun()


def _build_mint_result(
    access_key: str, payload: Dict[str, Any], mint_name: str
) -> Dict[str, Any]:
    emoji_value = str(payload.get("emoji", ""))
    phrase_value = str(payload.get("phrase", ""))
    emoji_symbols = split_emoji_symbols(emoji_value)
    suffix4 = "".join(emoji_symbols[-4:]) if len(emoji_symbols) >= 4 else emoji_value
    suffix6 = "".join(emoji_symbols[-6:]) if len(emoji_symbols) >= 6 else emoji_value
    pdf_bytes = build_credentials_pdf(
        access_key=access_key,
        emoji=emoji_value,
        phrase=phrase_value,
        nickname=str(mint_name or ""),
        role="Player",
        title="Access Card",
    )
    filename = f"iceicebaby-key-{datetime.now().strftime('%Y%m%d-%H%M%S')}.pdf"
    return {
        "access_key": access_key,
        "emoji": emoji_value,
        "phrase": phrase_value,
        "emoji4": suffix4,
        "emoji6": suffix6,
        "pdf_bytes": pdf_bytes,
        "filename": filename,
    }


def _render_mint_panel(authenticator: Any) -> None:
    st.session_state.setdefault(MINT_RESULT_KEY, None)
    st.session_state.setdefault(SHOW_MINT_FORM_KEY, False)

    if not bool(st.session_state.get(SHOW_MINT_FORM_KEY)):
        return

    with st.container(border=True):
        st.markdown("### Add optional details to your key")
        with st.form("splash-mint-token-form"):
            mint_name = st.text_input(
                "Name or nickname (for your reference)",
                key="splash-mint-name",
            )
            mint_intent = st.text_input(
                "Why are you joining this conversation? (optional)",
                key="splash-mint-intent",
                max_chars=120,
            )
            mint_email = st.text_input(
                "Email (optional, only for credential reminder)",
                key="splash-mint-email",
            )
            mint_submit = st.form_submit_button(
                "Generate Access Key",
                type="primary",
                use_container_width=True,
            )

        if not mint_submit:
            return

        with st.status("Minting access key...", expanded=True) as status:
            status.update(label="Starting mint workflow", state="running")
            try:
                status.update(
                    label="Calling to register new participant",
                    state="running",
                )
                access_key, _, payload = authenticator.register_user(
                    metadata={
                        "name": mint_name,
                        "intent": mint_intent,
                        "email": mint_email,
                        "role": "Player",
                    }
                )
                status.update(label="register_user returned", state="running")
            except Exception as exc:
                status.update(label="Minting failed", state="error")
                st.error(f"Minting failed: {exc}")
                return

            try:
                status.update(label="Building PDF payload", state="running")
                st.session_state[MINT_RESULT_KEY] = _build_mint_result(
                    access_key=str(access_key or ""),
                    payload=payload,
                    mint_name=mint_name,
                )
                log_event(
                    module="iceicebaby.auth",
                    event_type="mint_key",
                    player_id=str(access_key or ""),
                    value_label=str(payload.get("emoji", "")),
                    metadata={"has_email": bool(str(mint_email).strip())},
                )
                status.update(label="PDF payload built", state="running")
            except Exception as exc:
                status.update(label="Minting failed at PDF step", state="error")
                AUTH_LOGGER.error("mint key failed at PDF step: %s", exc)
                st.error(f"Minted but could not build PDF: {exc}")
                return
            status.update(label="Minting complete", state="complete")
        st.session_state[SHOW_MINT_FORM_KEY] = False
        st.session_state[SHOW_MINT_DIALOG_KEY] = False
        st.session_state[MINT_JUST_COMPLETED_KEY] = True
        st.rerun()


def _render_mint_result() -> None:
    mint_result = st.session_state.get(MINT_RESULT_KEY)
    if not mint_result:
        return

    st.success("Your access key is ready! **You can now continue to the session.**")
    st.markdown(
        """
A unique access key has been created for you. Store it safely.
"""
    )
    st.markdown("### Your key (store safely)")
    st.markdown(
        f"<div style='font-size:4.1rem;line-height:1.2;text-align:center'>{mint_result.get('emoji4', '—')}</div>",
        unsafe_allow_html=True,
    )
    st.caption(
        "A unique 22-emoji access key has been generated.\n\n"
        "For convenience, the last four emojis are usually enough to log in.\n\n"
        "You may invent a small story with these emojis to help remember your key.\n\n"
        "Your key is personal and private, so store it somewhere safe."
    )
    st.write(
        "You can also download an Access Card containing the full credentials for safe storage."
    )
    st.download_button(
        "Download Access Card",
        data=mint_result.get("pdf_bytes", b""),
        file_name=mint_result.get("filename", "iceicebaby-key.pdf"),
        mime="application/pdf",
        use_container_width=True,
        key="splash-mint-download-pdf",
    )
    if st.button(
        "Login now",
        type="primary",
        use_container_width=True,
        key="splash-go-login-after-mint",
    ):
        st.session_state["login_access_key_prefill"] = str(
            mint_result.get("emoji4") or mint_result.get("access_key") or ""
        )
        st.switch_page("pages/011_Intro.py")


def main() -> None:
    set_page()
    apply_theme()
    ensure_session_state()
    sidebar_debug_state()
    st.session_state.setdefault(MINT_RESULT_KEY, None)
    st.session_state.setdefault(SHOW_MINT_FORM_KEY, False)
    st.session_state.setdefault(SHOW_MINT_DIALOG_KEY, False)
    st.session_state.setdefault(MINT_JUST_COMPLETED_KEY, False)
    log_event(
        module="iceicebaby.sessions",
        event_type="page_view",
        page="Splash",
        player_id=str(st.session_state.get("player_page_id", "")),
        session_id=str(st.session_state.get("session_id", "")),
        device_id=str(st.session_state.get("anon_token", "")),
        status="ok",
    )

    repo = get_notion_repo()
    authenticator = get_authenticator(repo)

    in_key_creation = bool(
        st.session_state.get(SHOW_MINT_FORM_KEY)
        or st.session_state.get(MINT_RESULT_KEY)
    )
    if not in_key_creation:
        heading("<center>Glaciers, Listening to Society</center>")

    if (
        not st.session_state.get(SHOW_MINT_FORM_KEY)
        and not st.session_state.get(MINT_RESULT_KEY)
        and not st.session_state.get(SHOW_MINT_DIALOG_KEY)
    ):
        st.session_state[SHOW_MINT_DIALOG_KEY] = True

    if bool(st.session_state.get(SHOW_MINT_DIALOG_KEY)):
        _render_mint_info_dialog()
    _render_mint_panel(authenticator)
    _render_mint_result()
    if st.session_state.pop(MINT_JUST_COMPLETED_KEY, False):
        st.balloons()
    if not st.session_state.get(SHOW_MINT_FORM_KEY) and not st.session_state.get(
        MINT_RESULT_KEY
    ):
        st.page_link("pages/011_Intro.py", label="I already have an access key")


if __name__ == "__main__":
    main()
