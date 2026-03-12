from __future__ import annotations

import hashlib
from datetime import datetime

import streamlit as st

from infra.app_context import (
    get_active_session,
    get_authenticator,
    get_auth_runtime_config,
    get_notion_repo,
)
from infra.app_state import (
    ensure_auth,
    ensure_session_state,
    remember_access,
    set_session,
    mint_anon_token,
)
from infra.cryosphere_cracks import CRYOSPHERE_CRACKS, cryosphere_crack_points
from infra.credentials_pdf import build_credentials_pdf

from ui import (
    apply_theme,
    heading,
    microcopy,
    set_page,
    sidebar_debug_state,
    cracks_globe_block,
    display_centered_prompt,
    render_info_block,
)


def main() -> None:
    set_page()
    apply_theme()
    ensure_session_state()
    sidebar_debug_state()

    heading("Welcome")
    display_centered_prompt("Subject to change.")
    st.markdown(
        """
We map where fracture signals concentrate, where flow accelerates, and where instability becomes visible.
This is a live orientation layer before entering the session lobby.
        """
    )

    locations_md = []
    for category, entries in CRYOSPHERE_CRACKS.items():
        regions = ", ".join(entry["Region"] for entry in entries)
        locations_md.append(f"- **{category}**: {regions}")

    render_info_block(
        left_title="Cryosphere",
        left_subtitle="major crack zones",
        right_content="\n".join(
            [
                "### Major Cryosphere Crack Locations",
                "",
                "Below are the principal regions currently tracked in this prototype:",
                "",
                *locations_md,
            ]
        ),
    )

    repo = get_notion_repo()
    authenticator = get_authenticator(repo)
    auth_cfg = get_auth_runtime_config()
    key_hash_prefix = hashlib.sha256(
        auth_cfg["cookie_key"].encode("utf-8")
    ).hexdigest()[:12]

    with st.sidebar.expander("Debug: Auth cookie", expanded=False):
        st.code(
            (
                f"cookie_source={auth_cfg['source']}\n"
                f"cookie_name={auth_cfg['cookie_name']}\n"
                f"cookie_expiry_days={auth_cfg['cookie_expiry_days']}\n"
                f"cookie_key_len={len(auth_cfg['cookie_key'])}\n"
                f"cookie_key_sha256_prefix={key_hash_prefix}\n"
                f"default_session_code={auth_cfg['default_session_code']}"
            )
        )

    name, authentication_status, _ = ensure_auth(
        authenticator, callback=remember_access, key="access-key-login", location="main"
    )
    if authentication_status:
        authenticator.logout(button_name="Logout", location="sidebar")

    open_mint = bool(st.session_state.pop("focus_mint_token", False))
    with st.expander("Mint access token", expanded=open_mint):
        st.caption(
            "This interaction is designed to be anonymous. Your access key is personal and "
            "must be stored securely. If you add an email, it is used only to send a credentials reminder."
        )
        with st.form("mint-token-form"):
            mint_name = st.text_input("Name or nickname", key="mint-name")
            mint_intent = st.text_input(
                "Short intent (optional)",
                key="mint-intent",
                max_chars=120,
            )
            mint_email = st.text_input(
                "Email (optional, for credentials reminder)",
                key="mint-email",
            )
            mint_submit = st.form_submit_button(
                "Create Access Key",
                type="primary",
                use_container_width=True,
            )
        if mint_submit:
            try:
                access_key, _, payload = authenticator.register_user(
                    metadata={
                        "name": mint_name,
                        "intent": mint_intent,
                        "email": mint_email,
                        "role": "Player",
                    }
                )
            except Exception as exc:
                st.error(f"Minting failed: {exc}")
            else:
                st.success("Token minted.")
                st.code(access_key or "", language="text")
                st.write("Emoji:", payload.get("emoji", "—"))
                st.write("Phrase:", payload.get("phrase", "—"))
                st.write("Emoji suffix 4:", payload.get("emoji", "")[-4:])
                st.write("Emoji suffix 6:", payload.get("emoji", "")[-6:])

                emoji_value = str(payload.get("emoji", ""))
                pdf_bytes = build_credentials_pdf(
                    access_key=str(access_key or ""),
                    emoji=emoji_value,
                    phrase=str(payload.get("phrase", "")),
                    nickname=str(mint_name or ""),
                    role="Player",
                    title="Access Card",
                )
                filename = (
                    f"iceicebaby-key-{datetime.now().strftime('%Y%m%d-%H%M%S')}.pdf"
                )
                st.download_button(
                    "Download Access Card PDF",
                    data=pdf_bytes,
                    file_name=filename,
                    mime="application/pdf",
                    use_container_width=True,
                )

    if authentication_status:
        st.info(
            "We baked a cookie for you for 30 minutes. This keeps you signed in while you navigate."
        )
        session = get_active_session(repo)
        if session:
            set_session(session.get("id", ""), session.get("session_code", "Session"))
        salt = st.secrets.get("anon_salt", "iceicebaby")
        anon_token = mint_anon_token(
            st.session_state.get("session_id", ""),
            st.session_state.get("player_access_key", ""),
            salt,
        )
        st.session_state["anon_token"] = anon_token
        st.success(f"Access granted for {name or 'collaborator'}.")
        if st.button("Enter lobby", type="secondary", use_container_width=True):
            st.switch_page("pages/02_Home.py")
    elif authentication_status is False:
        st.error("Key invalid or ambiguous. Try full hash or more emoji.")


if __name__ == "__main__":
    main()
