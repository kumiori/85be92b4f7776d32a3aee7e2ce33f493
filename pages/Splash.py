from __future__ import annotations

from datetime import datetime
import time
from typing import Any, Dict

import streamlit as st

from infra.app_context import get_authenticator, get_notion_repo
from infra.app_state import ensure_session_state
from infra.cryosphere_cracks import cryosphere_crack_points
from infra.credentials_pdf import build_credentials_pdf
from infra.key_codec import split_emoji_symbols
from ui import (
    apply_theme,
    cracks_globe_block,
    display_centered_prompt,
    heading,
    microcopy,
    render_info_block,
    set_page,
    sidebar_debug_state,
)

MINT_RESULT_KEY = "splash_mint_result"
OPEN_MINT_KEY = "focus_mint_token"
MINT_DEBUG_KEY = "splash_mint_debug"
MINT_DEBUG_TRACE_KEY = "mint_debug_trace"


def _render_intro() -> None:
    heading("<center>Glaciers, Listening to Society</center>")
    st.caption(f"### `The copy that follows is subject to change.`")

    st.markdown(
        """
### Developed for the World Day for Glaciers at UNESCO, within the Decade of Action for Cryospheric Sciences (2024-2035).
#### TODAY WE COMMUNICATE WITH ARTS, PHOTOGRAPHY, LITERATURE, POETRY, and SOUND.
"""
    )
    st.markdown(
        """
Room XXX, 4pm, March 19, 2026. Organised by: ______, ______, ______, ______, and ______.
"""
    )
    cracks_globe_block(
        cryosphere_crack_points(),
        height=600,
        key="home-header-cracks",
        auto_rotate_speed=0.8,
        camera_lat=-28.0,
        camera_lng=10.0,
        camera_altitude=0.8,
    )
    microcopy(
        "Planet Earth at night. Signals concentrate where the cryosphere is under stress. Suggested listening: Computations - Kenn-Eerik, 2023"
    )
    display_centered_prompt("Something is happening now.")
    render_info_block(
        left_title="Why participate?",
        left_subtitle="signals · choices · transitions",
        right_content="\n".join(
            [
                "### Glaciers, ice shelves, and frozen ground are _evolving_ systems. These systems speak many languages.",
                # "#### Understanding their transitions is not about _tracking_ them.",
                "",
                # "#### When systems approach thresholds, signals appear before they break.",
                "#### Detecting and understanding them requires attention, interpretation, and collective judgement.",
                "",
                "#### This platform invites your observations, responses, and interactions. In real time.",
            ]
        ),
    )


def _render_access_cta() -> None:
    display_centered_prompt("Access")
    st.markdown(
        """
### This session ...
""",
        unsafe_allow_html=True,
    )
    st.markdown("#### Each player enters using a unique access key.")

    col_login, col_create = st.columns(2)

    with col_login:
        st.markdown("#### I already have an access key")
        st.caption("And I am ready to participate.")
        if st.button(
            "🔑 Go to Login",
            type="secondary",
            use_container_width=True,
            key="splash-go-login",
        ):
            st.switch_page("pages/01_Login.py")

    with col_create:
        st.markdown("#### Create a new access key")
        st.caption("Generate your personal token to participate.")
        if st.button(
            "✨ Create Access Key",
            type="primary",
            use_container_width=True,
            key="splash-create-key",
        ):
            st.session_state[OPEN_MINT_KEY] = True
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
    st.session_state.setdefault(MINT_DEBUG_KEY, [])
    st.session_state.setdefault(MINT_DEBUG_TRACE_KEY, [])
    open_mint = bool(st.session_state.pop(OPEN_MINT_KEY, False))

    with st.expander("Access key details", expanded=open_mint):
        st.caption(
            "All sessions are designed to be anonymous. Your access key is personal and "
            "must be stored securely. If you add an email, it is used only to send a credentials reminder."
        )
        st.markdown("### Now login with your access key to join the lobby")
        with st.form("splash-mint-token-form"):
            mint_name = st.text_input("Name or nickname", key="splash-mint-name")
            mint_intent = st.text_input(
                "What is your motivation? (optional)",
                key="splash-mint-intent",
                max_chars=120,
            )
            mint_email = st.text_input(
                "Email (optional, for credentials reminder)",
                key="splash-mint-email",
            )
            mint_submit = st.form_submit_button(
                "Create Access Key",
                type="primary",
                use_container_width=True,
            )

        if not mint_submit:
            return

        debug_steps: list[str] = []
        st.session_state[MINT_DEBUG_TRACE_KEY] = []
        t0 = time.perf_counter()
        debug_steps.append("submit_received")
        with st.status("Minting access key...", expanded=True) as status:
            status.update(label="Starting mint workflow", state="running")
            try:
                t1 = time.perf_counter()
                status.update(
                    label="Calling authenticator.register_user(...)",
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
                debug_steps.append(
                    f"register_user_done_ms={int((time.perf_counter() - t1) * 1000)}"
                )
            except Exception as exc:
                status.update(label="Minting failed", state="error")
                debug_steps.append(
                    f"register_user_failed_ms={int((time.perf_counter() - t0) * 1000)}"
                )
                st.session_state[MINT_DEBUG_KEY] = debug_steps + st.session_state.get(
                    MINT_DEBUG_TRACE_KEY, []
                )
                st.error(f"Minting failed: {exc}")
                return

            try:
                t2 = time.perf_counter()
                status.update(label="Building PDF payload", state="running")
                st.session_state[MINT_RESULT_KEY] = _build_mint_result(
                    access_key=str(access_key or ""),
                    payload=payload,
                    mint_name=mint_name,
                )
                status.update(label="PDF payload built", state="running")
                debug_steps.append(
                    f"build_pdf_done_ms={int((time.perf_counter() - t2) * 1000)}"
                )
            except Exception as exc:
                status.update(label="Minting failed at PDF step", state="error")
                debug_steps.append(
                    f"build_pdf_failed_ms={int((time.perf_counter() - t0) * 1000)}"
                )
                st.session_state[MINT_DEBUG_KEY] = debug_steps + st.session_state.get(
                    MINT_DEBUG_TRACE_KEY, []
                )
                st.error(f"Minted but could not build PDF: {exc}")
                return
            status.update(label="Minting complete", state="complete")

        debug_steps.append(f"total_ms={int((time.perf_counter() - t0) * 1000)}")
        st.session_state[MINT_DEBUG_KEY] = debug_steps + st.session_state.get(
            MINT_DEBUG_TRACE_KEY, []
        )


def _render_mint_result() -> None:
    mint_result = st.session_state.get(MINT_RESULT_KEY)
    mint_debug = st.session_state.get(MINT_DEBUG_KEY) or []
    with st.sidebar.expander("Mint debug trace", expanded=False):
        if mint_debug:
            st.code("\n".join(str(step) for step in mint_debug))
        else:
            st.caption("No minting trace yet.")
    if not mint_result:
        return

    st.success("Token minted.")
    st.markdown("### Your handy access key (emoji-4)")
    st.markdown(
        f"<div style='font-size:4.1rem;line-height:1.2;text-align:center'>{mint_result.get('emoji4', '—')}</div>",
        unsafe_allow_html=True,
    )
    st.caption(
        "A 22-emojis string unique key has been generated. In most cases, its last 4 emoji are sufficient to log in. "
        "Create a story around them to remember, or store the full key securely."
    )
    with st.expander("Show full credentials", expanded=False):
        st.code(f"Access key: {mint_result.get('access_key', '')}", language="text")
        st.write("Emoji:", mint_result.get("emoji", "—"))
        st.write("Phrase:", mint_result.get("phrase", "—"))
        st.write("Emoji suffix 4:", mint_result.get("emoji4", "—"))
        st.write("Emoji suffix 6:", mint_result.get("emoji6", "—"))

    st.download_button(
        "Download Access Card PDF",
        data=mint_result.get("pdf_bytes", b""),
        file_name=mint_result.get("filename", "iceicebaby-key.pdf"),
        mime="application/pdf",
        use_container_width=True,
        key="splash-mint-download-pdf",
    )


def main() -> None:
    set_page()
    apply_theme()
    ensure_session_state()
    sidebar_debug_state()

    repo = get_notion_repo()
    authenticator = get_authenticator(repo)

    _render_intro()
    _render_access_cta()
    _render_mint_panel(authenticator)
    _render_mint_result()


if __name__ == "__main__":
    main()
