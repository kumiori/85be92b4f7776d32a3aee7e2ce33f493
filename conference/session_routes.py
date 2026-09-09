from __future__ import annotations

from html import escape
from urllib.parse import urlencode

import streamlit as st

from ui import is_production_runtime


PREDICTION_VIEWS = {"join", "results", "host"}


def normalize_prediction_view(value: object) -> str:
    token = str(value or "").strip().lower()
    return token if token in PREDICTION_VIEWS else "join"


def query_requests_test(value: object) -> bool:
    return value is True or str(value or "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def prediction_url(*, view: str = "join", test: bool = False) -> str:
    normalized_view = normalize_prediction_view(view)
    params: list[tuple[str, str]] = []
    if normalized_view != "join":
        params.append(("view", normalized_view))
    if test:
        params.append(("test", "1"))
    query = urlencode(params)
    return f"/prediction?{query}" if query else "/prediction"


def prediction_primary_links(*, test_mode: bool) -> tuple[tuple[str, str], ...]:
    return (
        ("Join", prediction_url(view="join", test=test_mode)),
        ("Results", prediction_url(view="results", test=test_mode)),
    )


def prediction_sidebar_links(*, test_mode: bool) -> tuple[tuple[str, str], ...]:
    return (
        ("Host", prediction_url(view="host", test=test_mode)),
        ("Test", prediction_url(test=True)),
    )


def render_prediction_navigation(*, current_view: str, test_mode: bool) -> None:
    current = normalize_prediction_view(current_view)
    links = tuple(
        (
            label,
            url,
            (label.lower() == current and not (label == "Join" and test_mode))
            or (label == "Test" and test_mode and current == "join"),
        )
        for label, url in prediction_primary_links(test_mode=test_mode)
    )
    rendered = "".join(
        f'<a class="prediction-route-link{" is-active" if active else ""}" href="{escape(url)}">{escape(label)}</a>'
        for label, url, active in links
    )
    st.markdown(
        """
<style>
.prediction-route-nav { display:flex; flex-wrap:wrap; gap:.55rem; margin:0 0 1.5rem; }
.prediction-route-link { border:1px solid rgba(19,36,52,.16); border-radius:999px; color:#365064!important; font:600 .78rem/1 "Space Grotesk",sans-serif; letter-spacing:.04em; padding:.68rem 1rem; text-decoration:none!important; }
.prediction-route-link:hover,.prediction-route-link.is-active { background:#132434; border-color:#132434; color:#fff!important; }
</style>
"""
        f'<nav class="prediction-route-nav" aria-label="Prediction session">{rendered}</nav>',
        unsafe_allow_html=True,
    )
    if not is_production_runtime():
        sidebar_links = "".join(
            f'<a href="{escape(url)}">{escape(label)}</a><br>'
            for label, url in prediction_sidebar_links(test_mode=test_mode)
        )
        st.sidebar.markdown("### Prediction")
        st.sidebar.markdown(sidebar_links, unsafe_allow_html=True)
