from __future__ import annotations

from datetime import datetime
import time
from typing import Any, Dict

import streamlit as st

from infra.app_context import get_authenticator, get_notion_repo, load_config
from infra.app_state import ensure_session_state
from infra.credentials_pdf import build_credentials_pdf
from infra.key_codec import split_emoji_symbols
from infra.event_logger import log_event, get_module_logger
from ui import (
    apply_theme,
    display_centered_prompt,
    heading,
    set_page,
    sidebar_debug_state,
    sticky_container,
)

MINT_RESULT_KEY = "splash_mint_result"
MINT_DEBUG_KEY = "splash_mint_debug"
MINT_DEBUG_TRACE_KEY = "mint_debug_trace"
SHOW_MINT_DIALOG_KEY = "splash_show_mint_dialog"
SHOW_MINT_FORM_KEY = "splash_show_mint_form"
HIDE_ACCESS_INTRO_KEY = "splash_hide_access_intro"
AUTH_LOGGER = get_module_logger("iceicebaby.auth")


def _splash_stream_timing_config() -> tuple[float, dict[str, float]]:
    root = load_config()
    cfg = (
        root.get("splash", {}).get("streaming", {})
        or root.get("intro", {}).get("streaming", {})
        or {}
    )
    base_raw = cfg.get("base_delay_s", 0.04)
    try:
        base_delay_s = max(0.001, float(base_raw))
    except Exception:
        base_delay_s = 0.04
    raw_coef = cfg.get("punctuation_pause_coef", {}) or {}

    def _coef(name: str, default: float) -> float:
        try:
            return max(1.0, float(raw_coef.get(name, default)))
        except Exception:
            return default

    punctuation_coef = {
        ",": _coef("comma", 1.8),
        ";": _coef("semicolon", 2.0),
        ":": _coef("colon", 2.0),
        ".": _coef("period", 2.4),
        "!": _coef("exclamation", 2.4),
        "?": _coef("question", 2.4),
    }
    return base_delay_s, punctuation_coef


def _stream_writer(text: str, delay_s: float, punctuation_coef: dict[str, float]):
    words = text.split(" ")
    for i, word in enumerate(words):
        yield word if i == 0 else " " + word
        trailing = word.rstrip()[-1:] if word else ""
        coef = punctuation_coef.get(trailing, 1.0)
        time.sleep(delay_s * coef)


def _render_streamed_paragraph(text: str, key: str, animate: bool = True) -> None:
    done_key = f"splash_stream_done:{key}"
    if not animate or st.session_state.get(done_key):
        st.markdown(text)
        return
    base_delay_s, punctuation_coef = _splash_stream_timing_config()
    st.write_stream(_stream_writer(text, base_delay_s, punctuation_coef))
    st.session_state[done_key] = True


def _render_access_cta() -> None:
    has_mint_result = bool(st.session_state.get(MINT_RESULT_KEY))
    hide_intro = bool(st.session_state.get(HIDE_ACCESS_INTRO_KEY, False))
    display_centered_prompt("Access")
    if not hide_intro:
        animate = bool(st.session_state.get("splash_animate_text", True))
        _render_streamed_paragraph(
            "### This platform gathers individual points of view and follows how they shift through time.",
            key="access_p1",
            animate=animate,
        )
        _render_streamed_paragraph(
            "### A unique access key lets you enter, respond, and trace your path across the session.",
            key="access_p2",
            animate=animate,
        )
        _render_streamed_paragraph(
            "### This exchange sheds light on the temperature in the room: how we arrive emotionally, how we relate to the themes ahead, and whether we should continue the conversation.",
            key="access_p3",
            animate=animate,
        )
    if st.button(
        "Create access key",
        type="secondary" if has_mint_result else "primary",
        use_container_width=True,
        key="splash-create-key",
    ):
        st.session_state[HIDE_ACCESS_INTRO_KEY] = True
        st.session_state[SHOW_MINT_DIALOG_KEY] = True
        st.rerun()
    st.caption("Generate your personal emoji access key and start.")

    st.page_link("pages/011_Intro.py", label="I already have an access key")


@st.dialog("Create your access key")
def _render_mint_info_dialog() -> None:
    st.markdown(
        """
This platform is designed to be transparent and anonymous.
Your responses are linked only to your personal access key.

You may customise the key to make your experience easier:

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
    st.session_state.setdefault(MINT_DEBUG_KEY, [])
    st.session_state.setdefault(MINT_DEBUG_TRACE_KEY, [])
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
                log_event(
                    module="iceicebaby.auth",
                    event_type="mint_key",
                    player_id=str(access_key or ""),
                    value_label=str(payload.get("emoji", "")),
                    metadata={"has_email": bool(str(mint_email).strip())},
                )
                status.update(label="PDF payload built", state="running")
                debug_steps.append(
                    f"build_pdf_done_ms={int((time.perf_counter() - t2) * 1000)}"
                )
            except Exception as exc:
                status.update(label="Minting failed at PDF step", state="error")
                AUTH_LOGGER.error("mint key failed at PDF step: %s", exc)
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

    st.success("Your access key")
    st.markdown(
        """
A unique access key has been created for you.

This key allows you to enter the platform, answer questions, and return later to continue your trajectory. Your responses remain anonymous and are linked only to this key.

Please store your key somewhere safe. If you provide an email below, we can send you a reminder of your credentials.

You can now begin the session.
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
    with st.expander("Show full credentials", expanded=False):
        st.code(f"Access key: {mint_result.get('access_key', '')}", language="text")
        st.write("Emoji:", mint_result.get("emoji", "—"))
        st.write("Phrase:", mint_result.get("phrase", "—"))
        st.write("Emoji suffix 4:", mint_result.get("emoji4", "—"))
        st.write("Emoji suffix 6:", mint_result.get("emoji6", "—"))

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

    with sticky_container(mode="top"):
        heading("<center>Glaciers, Listening to Society</center>")
        _render_access_cta()
    if bool(st.session_state.get(SHOW_MINT_DIALOG_KEY)):
        _render_mint_info_dialog()
    _render_mint_panel(authenticator)
    _render_mint_result()


if __name__ == "__main__":
    main()
