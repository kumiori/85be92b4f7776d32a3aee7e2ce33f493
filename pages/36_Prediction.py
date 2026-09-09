from __future__ import annotations

from importlib import import_module

import streamlit as st

from conference.session_routes import (
    normalize_prediction_view,
    query_requests_test,
    render_prediction_navigation,
)


def main() -> None:
    if st.query_params.get("event"):
        st.query_params.pop("event")
    view = normalize_prediction_view(st.query_params.get("view", ""))
    test_mode = query_requests_test(st.query_params.get("test", ""))
    render_prediction_navigation(current_view=view, test_mode=test_mode)

    if view == "results":
        import_module("pages.34_Event_Overview").main(event_slug_override="prediction")
    elif view == "host":
        import_module("pages.35_Event_Host").main(event_slug_override="prediction")
    else:
        import_module("pages.33_Event").main(
            event_slug_override="prediction",
            public_route_path="prediction",
            canonical=True,
        )


if __name__ == "__main__":
    main()
