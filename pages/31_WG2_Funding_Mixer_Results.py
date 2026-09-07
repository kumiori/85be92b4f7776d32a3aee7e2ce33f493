from __future__ import annotations

import html
from typing import Any

import streamlit as st

from conference.context import get_conference_repo
from conference.wg2_funding_mixer import (
    CHANNELS,
    DEFAULT_SESSION_CODE,
    aggregate_allocations,
)
from infra.event_logger import log_event


def _session_code() -> str:
    return str(st.query_params.get("session", DEFAULT_SESSION_CODE) or "").strip()


def _style() -> None:
    st.set_page_config(page_title="WG2 · Funding mixer results", layout="wide")
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"], [data-testid="stHeader"], footer {display:none!important;}
        .stApp{background:#eef3f0;color:#17231f;}
        .block-container{max-width:1040px;padding:1.4rem 1.4rem 2.5rem;}
        .results-kicker{font:700 .72rem/1.2 ui-monospace,monospace;letter-spacing:.14em;color:#466158;}
        .result-row{display:grid;grid-template-columns:minmax(150px,240px) 1fr 64px;gap:1rem;align-items:center;margin:1.2rem 0;}
        .result-label{font-weight:700;line-height:1.2;}
        .result-track{height:18px;position:relative;background:#d7e0dc;border-radius:999px;overflow:visible;}
        .result-range{position:absolute;top:5px;height:8px;background:#7cb7a5;border-radius:999px;}
        .result-median{position:absolute;top:-3px;width:4px;height:24px;background:#0f6d62;border-radius:3px;transform:translateX(-2px);}
        .result-value{font:750 1.15rem/1 ui-monospace,monospace;text-align:right;}
        .trace-row{display:grid;grid-template-columns:repeat(7,1fr);gap:.35rem;margin:.2rem 0;}
        .trace-cell{height:5px;background:#d7e0dc;border-radius:4px;overflow:hidden;}
        .trace-cell i{display:block;height:100%;background:#0f6d6250;}
        @media(max-width:650px){.result-row{grid-template-columns:120px 1fr 42px;gap:.55rem}.result-label{font-size:.8rem}}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _resolve(repo: Any) -> tuple[dict[str, Any] | None, str]:
    code = _session_code()
    if not code:
        return None, "This results page needs an explicit session code."
    if repo is None or not repo.is_ready():
        return None, "The response store is unavailable."
    session = repo.resolve_session(session_code=code)
    if not session or not str(session.get("id") or "").strip():
        return None, f"Session {code!r} was not found."
    return session, ""


@st.fragment(run_every=5)
def _live_results(repo: Any, session: dict[str, Any]) -> None:
    rows = repo.interaction_repo().get_responses(str(session["id"]))
    aggregate = aggregate_allocations(rows)
    participants = int(aggregate["submission_count"])
    revisions = int(aggregate["revision_count"])
    left, right = st.columns(2)
    left.metric("Participants", participants)
    right.metric("Committed revisions", revisions)
    if participants == 0:
        st.info("No funding mixes have been committed yet. This page refreshes every five seconds.")
        return

    st.markdown("### Collective profile")
    st.caption("Median allocation; the lighter bar shows the observed range. Latest revision per participant.")
    for channel in CHANNELS:
        stats = aggregate["channels"][channel.key]
        low, high, midpoint = stats["min"], stats["max"], stats["median"]
        st.markdown(
            f"""
            <div class="result-row">
              <div class="result-label">{html.escape(channel.label)}</div>
              <div class="result-track" title="range {low:g}–{high:g}; median {midpoint:g}">
                <i class="result-range" style="left:{low}%;width:{max(0, high-low)}%"></i>
                <i class="result-median" style="left:{midpoint}%"></i>
              </div>
              <div class="result-value">{midpoint:g}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("### Anonymous individual traces")
    st.caption("Each faint row is one participant’s latest 100-token mix.")
    for trace in aggregate["traces"]:
        cells = "".join(
            f'<span class="trace-cell" title="{html.escape(channel.label)}: {int(trace[channel.key])}"><i style="width:{int(trace[channel.key])}%"></i></span>'
            for channel in CHANNELS
        )
        st.markdown(f'<div class="trace-row">{cells}</div>', unsafe_allow_html=True)


def main() -> None:
    _style()
    repo = get_conference_repo()
    session, error = _resolve(repo)
    if error:
        st.error(error)
        return
    assert session is not None
    log_event(
        module="iceicebaby.wg2_funding_mixer",
        event_type="page_view",
        page="wg2_funding_mixer_results",
        session_id=str(session["id"]),
        metadata={"session_code": _session_code(), "mode": "aggregate"},
    )
    st.markdown('<div class="results-kicker">LIVE COLLECTIVE VIEW</div>', unsafe_allow_html=True)
    st.title("WG2 — funding mix results")
    st.caption(f"Session: {_session_code()} · refreshes every five seconds")
    _live_results(repo, session)


if __name__ == "__main__":
    main()
