from __future__ import annotations

import json

import streamlit as st


def _listify(value) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value]
    if value is None:
        return []
    return [str(value)]


def main() -> None:
    st.set_page_config(page_title="Test · Query Params", layout="wide")
    st.title("Test · URL Query Parameters")
    st.caption("Read and write query params to prototype sharable deep links.")

    params = st.query_params
    raw = {k: _listify(v) for k, v in params.items()}

    st.subheader("Current URL Params")
    if raw:
        st.code(json.dumps(raw, indent=2), language="json")
    else:
        st.info("No query params found in URL.")

    st.subheader("Playground")
    c1, c2, c3 = st.columns(3)
    with c1:
        player = st.text_input("player", value=raw.get("player", [""])[0])
        session = st.text_input("session", value=raw.get("session", [""])[0])
    with c2:
        step = st.text_input("step", value=raw.get("step", [""])[0])
        mode = st.text_input("mode", value=raw.get("mode", [""])[0])
    with c3:
        payload = st.text_input("payload", value=raw.get("payload", [""])[0])
        tags_csv = st.text_input(
            "tags (comma-separated)",
            value=",".join(raw.get("tags", [])),
            help="Writes repeated `tags=` params in URL.",
        )

    if st.button("Update URL Params", use_container_width=True):
        next_params: dict[str, str | list[str]] = {}
        if player.strip():
            next_params["player"] = player.strip()
        if session.strip():
            next_params["session"] = session.strip()
        if step.strip():
            next_params["step"] = step.strip()
        if mode.strip():
            next_params["mode"] = mode.strip()
        if payload.strip():
            next_params["payload"] = payload.strip()
        tags = [t.strip() for t in tags_csv.split(",") if t.strip()]
        if tags:
            next_params["tags"] = tags
        st.query_params.clear()
        if next_params:
            st.query_params.update(next_params)
        st.rerun()

    if st.button("Clear URL Params", use_container_width=True):
        st.query_params.clear()
        st.rerun()

    st.subheader("Example Links")
    st.code(
        "?player=kumiori3&session=GLOBAL-SESSION&step=3&mode=markers",
        language="text",
    )
    st.code(
        "?player=alex&payload=cracks&tags=antarctica&tags=thresholds&tags=energy",
        language="text",
    )


if __name__ == "__main__":
    main()
