from __future__ import annotations

from html import escape

import streamlit as st

from conference.events import public_event_configs
from ui import apply_theme, set_page


def main() -> None:
    set_page()
    apply_theme()
    st.caption("SESSIONS")
    st.title("Participatory sessions")
    st.markdown(
        "Choose a session to join. These links always open the production entry point; test mode must be selected explicitly inside a session."
    )
    for config in public_event_configs():
        route = str(config.canonical_path or "").strip()
        if not route:
            continue
        with st.container(border=True):
            st.subheader(config.title or config.label)
            if config.subtitle:
                st.write(config.subtitle)
            details = " · ".join(item for item in (config.place, config.dates) if item)
            if details:
                st.caption(details)
            st.markdown(
                f'<a href="/{escape(route)}">Open session</a>',
                unsafe_allow_html=True,
            )


if __name__ == "__main__":
    main()
