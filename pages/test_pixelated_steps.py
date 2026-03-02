from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

from infra.pixel_transition_component import build_pixel_transition_html


VIEWS = [
    {
        "title": "Abstract",
        "subtitle": "Converged version",
        "body": "Not commitments. Snapshots of where we stand right now.",
        "bullets": ["Keep", "Change", "Trace rationale"],
    },
    {
        "title": "Titles",
        "subtitle": "Editorial pass",
        "body": "Evaluate candidate titles one by one.",
        "bullets": ["Keep", "Drop", "Change", "New one"],
    },
    {
        "title": "Expected Outcomes",
        "subtitle": "Scope and clarity",
        "body": "Refine outcomes with minimal cognitive load.",
        "bullets": ["Confirm item", "Move to next", "Track completion"],
    },
    {
        "title": "Journey",
        "subtitle": "Energy states",
        "body": "Describe movement from initial state to coordinated action.",
        "bullets": ["Start states", "End states", "Custom tags"],
    },
]


def main() -> None:
    st.set_page_config(page_title="Test · Pixelated Steps", layout="wide")
    st.title("Test · Pixelated Step Transitions")
    st.caption("Data-driven views with pixelated view transitions.")
    components.html(build_pixel_transition_html(VIEWS), height=820, scrolling=False)


if __name__ == "__main__":
    main()
