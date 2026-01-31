import streamlit as st

from ui import apply_theme, heading, microcopy, set_page


def main() -> None:
    set_page()
    apply_theme()
    heading("IceIceBaby v0")
    microcopy("Use the sidebar or jump to the login page to start.")
    if st.button("Go to Login", type="primary", use_container_width=True):
        st.switch_page("pages/01_Login.py")


if __name__ == "__main__":
    main()
