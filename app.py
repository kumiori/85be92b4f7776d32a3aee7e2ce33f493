from __future__ import annotations

import streamlit as st

from ui import (
    apply_theme,
    display_centered_prompt,
    heading,
    is_production_runtime,
    render_event_details,
    set_page,
)


def render_landing_page() -> None:
    set_page()
    apply_theme()
    heading("<center>Glaciers, Listening to Society</center>")
    st.markdown(
        """
### Developed for the World Day for Glaciers at UNESCO, within the Decade of Action for Cryospheric Sciences (2024-2035).
"""
    )
    render_event_details()
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
    if st.button("Go to Login", type="secondary", width="stretch"):
        st.switch_page("pages/01_Login.py")


def _visible_pages() -> dict[str, list[st.Page]]:
    return {
        "**Entry**": [
            st.Page(
                render_landing_page,
                title="Welcome",
                icon=":material/edit_note:",
                default=True,
            ),
            st.Page("pages/Splash.py", title="Access", icon=":material/key:"),
            st.Page("pages/011_Intro.py", title="Intro", icon=":material/auto_stories:"),
            st.Page("pages/01_Login.py", title="Login", icon=":material/login:"),
        ],
        "**Session**": [
            st.Page("pages/02_Home.py", title="Lobby", icon=":material/home:"),
            st.Page("pages/03_Resonance.py", title="Resonance", icon=":material/waves:"),
            st.Page("pages/04_Questions.py", title="Questions", icon=":material/help:"),
            st.Page("pages/05_Decisions.py", title="Decisions", icon=":material/rule:"),
            st.Page("pages/06_Coordination.py", title="Coordination", icon=":material/hub:"),
        ],
        "**Collective**": [
            st.Page(
                "pages/13_UNESCO_Opening.py",
                title="UNESCO-opening",
                icon=":material/location_on:",
                url_path="unesco-opening",
            ),
            st.Page("pages/08_Overview.py", title="Overview", icon=":material/travel_explore:"),
            st.Page("pages/12_Report.py", title="Report", icon=":material/article:"),
            st.Page("pages/09_Player.py", title="Your trajectory", icon=":material/person:"),
        ],
        "**Ops**": [
            st.Page("pages/07_Admin.py", title="Admin", icon=":material/tune:"),
        ],
    }


def _lab_pages() -> list[st.Page]:
    return [
        st.Page(
            "pages/30_audience_interaction_test.py",
            title="Test · Interaction",
            icon=":material/science:",
        ),
        st.Page(
            "pages/test_access_keys.py",
            title="Test · Access keys",
            icon=":material/vpn_key:",
        ),
        st.Page(
            "pages/test_player_profile.py",
            title="Test · Player profile",
            icon=":material/badge:",
        ),
        st.Page(
            "pages/11_Session_Inspector.py",
            title="Test · Session inspector",
            icon=":material/search_insights:",
        ),
        st.Page(
            "pages/test_query_params.py",
            title="Test · Query params",
            icon=":material/link:",
        ),
        st.Page(
            "pages/test_notion.py",
            title="Test · Notion",
            icon=":material/database:",
        ),
        st.Page(
            "pages/test_typography.py",
            title="Test · Typography",
            icon=":material/text_fields:",
        ),
        st.Page(
            "pages/test_typography_native.py",
            title="Test · Typography native",
            icon=":material/view_quilt:",
        ),
        st.Page(
            "pages/test_highlight_playground.py",
            title="Test · Highlight playground",
            icon=":material/draw:",
        ),
        st.Page(
            "pages/test_geo.py",
            title="Test · Geo",
            icon=":material/public:",
        ),
        st.Page(
            "pages/test_pixelated_geo_fusion.py",
            title="Test · Pixelated geo fusion",
            icon=":material/blur_on:",
        ),
        st.Page(
            "pages/test_pixelated_steps.py",
            title="Test · Pixelated steps",
            icon=":material/animation:",
        ),
        st.Page(
            "pages/test_pixelated_transition.py",
            title="Test · Pixelated transition",
            icon=":material/blur_on:",
        ),
        st.Page(
            "pages/test_wh_questions.py",
            title="Test · WH questions",
            icon=":material/help_clinic:",
        ),
        st.Page(
            "pages/test_copy.py",
            title="Test · Copy",
            icon=":material/content_copy:",
        ),
        st.Page(
            "pages/test_app_v00.py",
            title="Test · App v00",
            icon=":material/science:",
        ),
        st.Page(
            "pages/10_Fracture.py",
            title="Fracture legacy",
            icon=":material/schema:",
        ),
    ]


def _hidden_pages() -> list[st.Page]:
    hidden_paths = [
        "pages/Splash_old.py",
    ]
    return [st.Page(path, visibility="hidden") for path in hidden_paths]


def main() -> None:
    pages = _visible_pages()
    if not is_production_runtime():
        pages["**Lab**"] = _lab_pages()
    pages["**Internal**"] = _hidden_pages()
    navigation = st.navigation(
        pages,
        position="hidden" if is_production_runtime() else "sidebar",
        expanded=not is_production_runtime(),
    )
    navigation.run()


if __name__ == "__main__":
    main()
