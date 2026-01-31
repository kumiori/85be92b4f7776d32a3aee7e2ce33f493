from __future__ import annotations

import streamlit as st

from infra.app_context import get_active_session, get_authenticator, get_notion_repo
from infra.app_state import (
    ensure_auth,
    ensure_session_state,
    remember_access,
    set_session,
    mint_anon_token,
)
from ui import apply_theme, heading, microcopy, set_page, sidebar_debug_state


def main() -> None:
    set_page()
    apply_theme()
    ensure_session_state()
    sidebar_debug_state()

    heading("Welcome")
    microcopy("Enter your access token, emoji tail, or passphrase.")

    repo = get_notion_repo()
    authenticator = get_authenticator(repo)

    name, authentication_status, _ = ensure_auth(
        authenticator, callback=remember_access, key="access-key-login", location="main"
    )
    if authentication_status:
        authenticator.logout(button_name="Logout", location="sidebar")

    with st.expander("Mint access token"):
        st.caption("Create a single access token for a new collaborator.")
        mint_role = st.selectbox(
            "Role", ["Contributor", "Admin"], index=0, key="mint-role"
        )
        mint_name = st.text_input("Display name (optional)", key="mint-name")
        if st.button("Mint token", type="secondary", use_container_width=True):
            try:
                access_key, _, payload = authenticator.register_user(
                    metadata={"name": mint_name, "role": mint_role}
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

    if authentication_status:
        st.info("We baked a cookie for you for 30 minutes. This keeps you signed in while you navigate.")
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
        if st.button("Enter lobby", type="primary", use_container_width=True):
            st.switch_page("pages/02_Home.py")
    elif authentication_status is False:
        st.error("Key invalid or ambiguous. Try full hash or more emoji.")


if __name__ == "__main__":
    main()
