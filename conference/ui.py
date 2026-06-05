from __future__ import annotations

import streamlit as st


def apply_conference_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --conference-bg: #f4efe7;
            --conference-ink: #17181c;
            --conference-muted: rgba(23, 24, 28, 0.66);
            --conference-panel: rgba(255, 255, 255, 0.84);
            --conference-panel-strong: rgba(255, 255, 255, 0.96);
            --conference-border: rgba(23, 24, 28, 0.12);
            --conference-accent: #0f6d62;
            --conference-accent-soft: rgba(15, 109, 98, 0.10);
        }
        .stApp {
            background:
                radial-gradient(circle at top right, rgba(15, 109, 98, 0.14), transparent 28%),
                linear-gradient(180deg, #f8f3ea 0%, var(--conference-bg) 100%);
            color: var(--conference-ink);
        }
        .block-container {
            max-width: 720px;
            padding-top: 2rem;
            padding-bottom: 4rem;
        }
        [data-testid="stHeader"] {
            background: transparent;
        }
        h1, h2, h3 {
            color: var(--conference-ink);
            letter-spacing: -0.04em;
            line-height: 1.02;
            text-wrap: balance;
        }
        .conference-step {
            text-transform: uppercase;
            letter-spacing: 0.08em;
            font-size: 0.82rem;
            color: var(--conference-muted);
            margin-bottom: 0.85rem;
        }
        .conference-body {
            font-size: 1.08rem;
            line-height: 1.6;
            color: var(--conference-muted);
            margin-bottom: 1.25rem;
        }
        .conference-card {
            padding: 1rem 1.1rem;
            border-radius: 1.2rem;
            background: var(--conference-panel);
            border: 1px solid var(--conference-border);
            margin-bottom: 0.9rem;
            box-shadow: 0 10px 30px rgba(28, 34, 41, 0.04);
        }
        .conference-card-title {
            font-size: 0.88rem;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: var(--conference-muted);
            margin-bottom: 0.3rem;
        }
        .conference-card-body {
            font-size: 1.02rem;
            line-height: 1.45;
            color: var(--conference-ink);
        }
        .stButton > button,
        .stDownloadButton > button {
            min-height: 4rem;
            border-radius: 1.25rem;
            border: 1px solid var(--conference-border);
            background: var(--conference-panel-strong);
            color: var(--conference-ink);
            font-size: 1rem;
            font-weight: 500;
        }
        .stButton > button[kind="primary"] {
            background: var(--conference-accent);
            color: #f7faf9;
            border-color: transparent;
        }
        [data-testid="stPills"] [data-baseweb="button-group"] {
            gap: 0.75rem !important;
        }
        [data-testid="stPills"] button {
            min-height: 4.2rem !important;
            padding: 0.75rem 1rem !important;
            border-radius: 1.35rem !important;
            background: rgba(255, 255, 255, 0.88) !important;
            border: 1px solid rgba(23, 24, 28, 0.12) !important;
        }
        [data-testid="stPills"] button[aria-pressed="true"] {
            background: var(--conference-accent-soft) !important;
            border-color: rgba(15, 109, 98, 0.45) !important;
        }
        [data-testid="stPills"] button p,
        [data-testid="stPills"] button span,
        [data-testid="stPills"] button div {
            font-size: 1.02rem !important;
            line-height: 1.25 !important;
            white-space: normal !important;
            text-align: center !important;
        }
        .stTextInput input,
        .stTextArea textarea {
            min-height: 3.4rem;
            border-radius: 1rem !important;
            background: rgba(255, 255, 255, 0.88) !important;
        }
        [data-testid="stSidebar"] {
            background: rgba(252, 249, 242, 0.98);
        }
        @media (max-width: 640px) {
            .block-container {
                padding-top: 1.4rem;
                padding-left: 1rem;
                padding-right: 1rem;
            }
            h1 {
                font-size: clamp(2.6rem, 11vw, 4rem);
            }
            [data-testid="stPills"] button {
                min-height: 4.45rem !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def conference_header(title: str, body: str, step: str = "") -> None:
    if step:
        st.markdown(
            f'<div class="conference-step">{step}</div>',
            unsafe_allow_html=True,
        )
    st.title(title)
    if body:
        st.markdown(
            f'<div class="conference-body">{body}</div>',
            unsafe_allow_html=True,
        )


def summary_card(title: str, body: str) -> None:
    st.markdown(
        f"""
        <div class="conference-card">
            <div class="conference-card-title">{title}</div>
            <div class="conference-card-body">{body}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

