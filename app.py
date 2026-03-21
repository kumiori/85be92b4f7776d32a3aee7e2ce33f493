import streamlit as st

from ui import (
    apply_theme,
    heading,
    set_page,
    display_centered_prompt,
    render_event_details,
)


def main() -> None:
    set_page()
    apply_theme()
    # heading("IceIceBaby v0")
    heading("<center>Glaciers, Listening to Society</center>")
    st.markdown(
        """
### Developed for the World Day for Glaciers at UNESCO, within the Decade of Action for Cryospheric Sciences (2024-2035).
"""
    )
    render_event_details()
    # microcopy("Use the sidebar or jump to the login page to start.")
    display_centered_prompt("One idea. With a <em>twist</em>.")

    st.markdown(
        """
    ### irreversibility <br /> <small>/ˌɪr.ɪˌvɜː.səˈbɪ.lɪ.ti/</small>, <br /> <small>/ir-ih-ver-suh-BIL-ih-tee/</small> <br /> _ 
    ### _(property.)_ Anchors action in the present, where choice _still_ exists. 
    ### This space is where traces & decisions were made visible. _Then_ action follows. 
    """,
        unsafe_allow_html=True,
    )

    st.divider()

    st.markdown("### Do you already have an access key?")

    if st.button("Go to Login", type="secondary", use_container_width=True):
        st.switch_page("pages/01_Login.py")


if __name__ == "__main__":
    main()
