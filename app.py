import streamlit as st

from ui import apply_theme, heading, microcopy, set_page, display_centered_prompt


def main() -> None:
    set_page()
    apply_theme()
    heading("IceIceBaby v0")
    microcopy("Use the sidebar or jump to the login page to start.")
    display_centered_prompt("One key. And a <em>twist</em>.")

    st.markdown(
        """
    ### irreversibility <br /> <small>/ˌɪr.ɪˌvɜː.səˈbɪ.lɪ.ti/</small>, <br /> <small>/ir-ih-ver-suh-BIL-ih-tee/</small> <br /> _ 
    ### _(property.)_ Anchors action in the present, where choice _still_ exists. 
    ### This space is where traces & decisions are made visible. _Then_ action follows. 
    """,
        unsafe_allow_html=True,
    )

    st.divider()

    st.markdown("### Do you already have an access key?")

    if st.button("Go to Login", type="secondary", use_container_width=True):
        st.switch_page("pages/01_Login.py")


if __name__ == "__main__":
    main()
