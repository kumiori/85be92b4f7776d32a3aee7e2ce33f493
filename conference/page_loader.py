from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import streamlit as st


def ensure_event_query(event_slug: str) -> None:
    desired = str(event_slug or "").strip()
    current = str(st.query_params.get("event", "") or "").strip()
    if current == desired:
        return
    next_params: dict[str, str] = {"event": desired}
    key = str(st.query_params.get("key", "") or "").strip()
    if key:
        next_params["key"] = key
    st.query_params.clear()
    st.query_params.update(next_params)


def load_page_module(page_filename: str, module_name: str) -> ModuleType:
    page_path = Path(__file__).resolve().parents[1] / "pages" / page_filename
    spec = importlib.util.spec_from_file_location(module_name, page_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load page module from {page_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
