from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

from infra.app_context import get_authenticator, get_notion_repo
from infra.cryosphere_cracks import cryosphere_crack_points
from infra.pixel_transition_component import build_pixel_transition_geo_html


VIEWS = [
    {
        "kind": "text",
        "title": "Signal",
        "subtitle": "Pre-fracture scan",
        "body": "Contours align, tension accumulates, and weak zones begin to organize.",
        "bullets": [
            "Detect early stress pathways",
            "Compare shelf, glacier, and sea-ice behavior",
            "Prepare for transition",
        ],
    },
    {
        "kind": "text",
        "title": "Threshold",
        "subtitle": "Near the break",
        "body": "Micro-decisions become irreversible when local failures synchronize.",
        "bullets": [
            "Track local-to-global coupling",
            "Spot hesitation and acceleration",
            "Hold context while switching views",
        ],
    },
    {
        "kind": "globe",
        "title": "Cracks",
        "subtitle": "Where major fracture is observed",
        "body": "Live crack markers and heat intensity share the same surface tone as the frame, so the plot feels embedded rather than pasted.",
        "bullets": [
            "Auto-rotating cryosphere map",
            "Hover for region and relative energy",
            "Seamless background blend",
        ],
    },
    {
        "kind": "markers",
        "title": "Locations",
        "subtitle": "Elastic energy intensity ledger",
        "body": "Each site is listed with elastic energy intensity. Marker density uses # so the strongest signals read at a glance.",
        "bullets": [
            "# count scales with intensity",
            "Sorted from highest to lowest energy",
            "Designed for rapid scan before action",
        ],
    },
    {
        "kind": "text",
        "title": "Action",
        "subtitle": "From map to coordination",
        "body": "The interface returns to editorial mode with the same pixel mask language.",
        "bullets": [
            "Turn observations into prompts",
            "Prioritize interventions",
            "Move to coordinated decisions",
        ],
    },
]


def main() -> None:
    st.set_page_config(page_title="Test · Pixelated Geo Fusion", layout="wide")
    if st.session_state.get("authentication_status"):
        repo = get_notion_repo()
        authenticator = get_authenticator(repo)
        authenticator.logout(button_name="Logout", location="sidebar")
    components.html(
        build_pixel_transition_geo_html(VIEWS, crack_points=cryosphere_crack_points()),
        height=1100,
        scrolling=False,
    )


if __name__ == "__main__":
    main()
