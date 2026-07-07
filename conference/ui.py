from __future__ import annotations

import html

import streamlit as st


def apply_typography_theme() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght,SOFT@9..144,300..700,0..100&family=Space+Grotesk:wght@400;500;700&display=swap');

        :root {
            --type-font-sans: "Space Grotesk", "Avenir Next", "Segoe UI", system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
            --type-font-serif: "Fraunces", Georgia, "Times New Roman", serif;
            --type-bg-top: #eef5fb;
            --type-bg-bottom: #dde9f2;
            --type-paper: rgba(255, 255, 255, 0.76);
            --type-paper-strong: rgba(255, 255, 255, 0.92);
            --type-ink: #132434;
            --type-muted: #607384;
            --type-soft: rgba(96, 115, 132, 0.76);
            --type-border: rgba(19, 36, 52, 0.12);
            --type-accent: #2c6fa3;
            --type-accent-soft: rgba(44, 111, 163, 0.12);
            --type-measure: 66ch;
            --type-measure-lead: 62ch;
            --type-measure-note: 54ch;
            --type-measure-narrow: 58ch;
            --type-space-xs: 0.35rem;
            --type-space-sm: 0.65rem;
            --type-space-md: 1rem;
            --type-space-lg: 1.55rem;
            --type-space-xl: 2.35rem;
            --type-display: clamp(3.05rem, 6.8vw, 4.65rem);
            --type-headline: clamp(1.8rem, 3.8vw, 2.45rem);
            --type-section: clamp(1.16rem, 1.8vw, 1.35rem);
            --type-body: clamp(1.02rem, 1.1vw, 1.1rem);
            --type-lead: clamp(1.14rem, 1.35vw, 1.24rem);
            --type-caption: clamp(0.94rem, 1vw, 1rem);
            --type-caption-small: clamp(0.82rem, 0.9vw, 0.9rem);
            --type-page-title: var(--type-display);
            --type-page-subtitle: var(--type-headline);
            --type-section-title: var(--type-section);
            --type-question-title: var(--type-headline);
            --type-helper: var(--type-caption);
        }

        .block-container {
            max-width: min(900px, calc(100vw - 2rem)) !important;
        }

        .reading-block,
        .page-subtitle,
        .question-context,
        .helper-text,
        .conference-body {
            max-width: var(--type-measure);
        }

        .page-kicker {
            margin: 0 0 1rem 0;
            font-family: var(--type-font-serif);
            font-size: var(--type-caption);
            line-height: 1.35;
            font-weight: 500;
            letter-spacing: 0;
            color: var(--type-soft);
        }

        .page-title {
            margin: 0 0 1.5rem 0;
            max-width: min(720px, 100%);
            font-family: var(--type-font-sans);
            font-size: var(--type-page-title);
            line-height: 1.02;
            font-weight: 700;
            letter-spacing: 0;
            color: var(--type-ink);
            text-wrap: balance;
        }

        .page-subtitle {
            margin: 0 0 2rem 0;
            max-width: min(680px, 100%);
            font-family: var(--type-font-sans);
            font-size: var(--type-page-subtitle);
            line-height: 1.14;
            font-weight: 700;
            letter-spacing: 0;
            color: var(--type-ink);
            text-wrap: balance;
        }

        .section-title {
            margin: 3.25rem 0 0.75rem 0;
            font-family: var(--type-font-sans);
            font-size: var(--type-section-title);
            line-height: 1.2;
            font-weight: 700;
            letter-spacing: 0;
            color: var(--type-ink);
            text-wrap: balance;
        }

        .question-title {
            margin: 0 0 var(--type-space-sm) 0;
            max-width: var(--type-measure-narrow);
            font-family: var(--type-font-sans);
            font-size: var(--type-question-title);
            line-height: 1.1;
            font-weight: 700;
            letter-spacing: 0;
            color: var(--type-ink);
            text-wrap: balance;
        }

        .question-context,
        .helper-text {
            margin: 0 0 0.9rem 0;
            font-family: var(--type-font-sans);
            font-size: clamp(1.14rem, 1.45vw, 1.28rem);
            line-height: 1.5;
            font-weight: 400;
            letter-spacing: 0;
            color: var(--type-muted);
        }

        .helper-text {
            margin-bottom: var(--type-space-lg);
            font-size: var(--type-helper);
            line-height: 1.62;
        }

        .question-context-label {
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
            font-size: 0.9em;
            font-weight: 700;
            color: var(--type-ink);
        }

        .caption {
            margin: 0 0 var(--type-space-sm) 0;
            font-family: var(--type-font-sans);
            font-size: var(--type-caption-small);
            line-height: 1.42;
            font-weight: 500;
            letter-spacing: 0;
            color: var(--type-soft);
        }

        .primary-action,
        .secondary-action {
            font-family: var(--type-font-sans);
            font-size: 0.98rem;
            line-height: 1.2;
            font-weight: 700;
            letter-spacing: 0;
        }

        .primary-action {
            color: #fff;
        }

        .secondary-action {
            color: var(--type-ink);
        }

        .entry-hero {
            max-width: min(820px, 100%);
            margin: 0;
            padding: 0;
        }

        .entry-display {
            margin: 0 0 0.8rem 0;
            max-width: min(740px, 100%);
            font-family: var(--type-font-sans);
            font-size: var(--type-display);
            line-height: 1.02;
            font-weight: 700;
            letter-spacing: 0;
            color: var(--type-ink);
            text-wrap: balance;
        }

        .entry-headline {
            margin: 0 0 1rem 0;
            max-width: min(680px, 100%);
            font-family: var(--type-font-sans);
            font-size: var(--type-section);
            line-height: 1.14;
            font-weight: 700;
            letter-spacing: 0;
            color: var(--type-ink);
            text-wrap: balance;
        }

        .entry-kicker {
            margin: 0 0 0.95rem 0;
            font-family: var(--type-font-serif);
            font-size: var(--type-lead);
            line-height: 1.38;
            font-weight: 500;
            letter-spacing: 0;
            color: var(--type-soft);
        }

        .entry-meta {
            margin: 0 0 2.8rem 0;
            max-width: min(620px, 100%);
            padding: 0.85rem 1rem;
            border-radius: 0.5rem;
            background: rgba(255, 255, 255, 0.58);
            border: 1px solid var(--type-border);
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
            font-size: 0.92rem;
            line-height: 1.45;
            letter-spacing: 0;
            white-space: pre-wrap;
            color: var(--type-muted);
        }

        .entry-block {
            margin: 0 0 2.2rem 0;
            max-width: var(--type-measure-lead);
        }

        .entry-block-grid {
            display: grid;
            grid-template-columns: minmax(0, 1.35fr) minmax(14rem, 0.8fr);
            gap: clamp(1.4rem, 4vw, 3rem);
            align-items: start;
            margin: 0 0 2.45rem 0;
        }

        .entry-block-grid .entry-block {
            margin-bottom: 0;
        }

        .entry-block-label {
            margin: 0 0 0.62rem 0;
            font-family: var(--type-font-serif);
            font-size: var(--type-caption-small);
            line-height: 1.35;
            font-weight: 600;
            letter-spacing: 0;
            text-transform: uppercase;
            color: var(--type-soft);
        }

        .entry-lead {
            margin: 0;
            font-family: var(--type-font-sans);
            font-size: var(--type-lead);
            line-height: 1.5;
            font-weight: 400;
            letter-spacing: 0;
            color: var(--type-ink);
        }

        .entry-note {
            margin: 0;
            max-width: var(--type-measure-note);
            font-family: var(--type-font-serif);
            font-size: var(--type-caption);
            line-height: 1.36;
            font-weight: 400;
            letter-spacing: 0;
            color: var(--type-muted);
        }

        .entry-note ul {
            margin: 0;
            padding-left: 1rem;
        }

        .entry-note li {
            margin: 0.08rem 0;
            padding-left: 0.15rem;
        }

        .entry-action-title {
            margin: 0 0 0.7rem 0;
            font-family: var(--type-font-sans);
            font-size: var(--type-section);
            line-height: 1.2;
            font-weight: 700;
            letter-spacing: 0;
            color: var(--type-ink);
        }

        .question-progress {
            margin: 0 0 1.75rem 0;
            font-family: var(--type-font-serif);
            font-size: var(--type-caption);
            line-height: 1.35;
            font-weight: 600;
            letter-spacing: 0;
            color: var(--type-soft);
        }

        .question-validation {
            min-height: 2rem;
            margin: 1.1rem 0 0.55rem 0;
            padding: 0.55rem 0.75rem;
            border-radius: 0.5rem;
            border: 1px solid rgba(161, 82, 40, 0.2);
            background: rgba(255, 244, 235, 0.72);
            font-family: var(--type-font-sans);
            font-size: 0.95rem;
            line-height: 1.35;
            font-weight: 500;
            color: #7a3f20;
        }

        .question-validation-empty {
            visibility: hidden;
        }

        [data-testid="stMarkdownContainer"] p {
            font-family: var(--type-font-sans);
            font-size: var(--type-body);
            line-height: 1.62;
            letter-spacing: 0;
        }

        [data-testid="stCaptionContainer"] {
            color: var(--type-muted);
        }

        @media (max-width: 640px) {
            :root {
                --type-measure: 100%;
                --type-measure-lead: 100%;
                --type-measure-note: 100%;
                --type-measure-narrow: 100%;
                --type-space-xl: 1.8rem;
                --type-display: clamp(3.1rem, 13vw, 3.9rem);
                --type-headline: clamp(1.75rem, 7vw, 2.15rem);
            }

            .page-title {
                max-width: 100%;
            }

            .question-title {
                font-size: var(--type-headline);
            }

            .entry-hero {
                padding-top: 0;
            }

            .entry-display {
                margin-bottom: 1.25rem;
            }

            .entry-headline {
                margin-bottom: 0.85rem;
            }

            .entry-kicker {
                margin-bottom: 0.85rem;
            }

            .entry-meta {
                margin-bottom: 2.1rem;
            }

            .entry-block {
                margin-bottom: 2.1rem;
            }

            .entry-block-grid {
                grid-template-columns: 1fr;
                gap: 2.1rem;
                margin-bottom: 2.1rem;
            }

            .entry-block-grid .entry-block {
                margin-bottom: 0;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def apply_conference_styles() -> None:
    apply_typography_theme()
    st.markdown(
        """
        <style>
        :root {
            --conference-bg: var(--type-bg-bottom);
            --conference-ink: var(--type-ink);
            --conference-muted: var(--type-muted);
            --conference-panel: var(--type-paper);
            --conference-panel-strong: var(--type-paper-strong);
            --conference-border: var(--type-border);
            --conference-accent: var(--type-accent);
            --conference-accent-soft: var(--type-accent-soft);
        }
        .stApp {
            background:
                radial-gradient(circle at 12% 12%, rgba(255, 255, 255, 0.62), transparent 30rem),
                linear-gradient(180deg, var(--type-bg-top) 0%, var(--type-bg-bottom) 100%);
            color: var(--conference-ink);
        }
        .block-container {
            padding-top: clamp(1.6rem, 4vw, 3rem);
            padding-bottom: 4rem;
        }
        .st-key-conference_entry_card {
            max-width: min(820px, 100%);
            margin-top: clamp(0.5rem, 3vw, 2rem);
            padding: clamp(2rem, 5vw, 3.1rem) clamp(1.2rem, 4vw, 2.75rem);
            border: 1px solid var(--conference-border);
            border-radius: 0.5rem;
            background:
                linear-gradient(135deg, rgba(255, 255, 255, 0.86), rgba(241, 248, 252, 0.74)),
                var(--conference-panel);
            box-shadow: 0 24px 60px rgba(19, 36, 52, 0.08);
        }
        .st-key-conference_entry_card [data-testid="stVerticalBlock"] {
            gap: 0.8rem;
        }
        [data-testid="stHeader"] {
            background: transparent;
        }
        [data-testid="stAppViewContainer"] {
            font-family: var(--type-font-sans);
        }
        h1, h2, h3 {
            color: var(--conference-ink);
            letter-spacing: 0;
            line-height: 1.08;
            text-wrap: balance;
        }
        .conference-body {
            font-size: var(--type-body);
            line-height: 1.62;
            color: var(--conference-muted);
            margin-bottom: 1.25rem;
        }
        .conference-card {
            padding: 1.1rem 1.2rem;
            border-radius: 0.5rem;
            background: var(--conference-panel);
            border: 1px solid var(--conference-border);
            margin-bottom: 0.9rem;
            box-shadow: 0 16px 42px rgba(19, 36, 52, 0.06);
        }
        .conference-card-title {
            font-family: var(--type-font-serif);
            font-size: var(--type-caption);
            letter-spacing: 0;
            color: var(--conference-muted);
            margin-bottom: 0.3rem;
        }
        .conference-card-body {
            font-size: 1.02rem;
            line-height: 1.5;
            color: var(--conference-ink);
        }
        .stButton > button,
        .stDownloadButton > button {
            min-height: 3.3rem;
            border-radius: 999px;
            border: 1.5px solid rgba(19, 36, 52, 0.3);
            background: var(--conference-panel-strong);
            color: var(--conference-ink);
            font-family: var(--type-font-sans);
            font-size: 0.98rem;
            font-weight: 700;
            letter-spacing: 0;
            padding-left: 1.35rem;
            padding-right: 1.35rem;
            box-shadow: 0 10px 24px rgba(19, 36, 52, 0.07);
            transition: transform 120ms ease, box-shadow 120ms ease, background 120ms ease;
        }
        .stButton > button:hover,
        .stDownloadButton > button:hover {
            transform: translateY(-1px);
            border-color: var(--conference-ink);
            box-shadow: 0 14px 30px rgba(19, 36, 52, 0.11);
        }
        .stButton > button[kind="primary"] {
            background: var(--conference-ink);
            color: #f7fbff;
            border-color: var(--conference-ink);
        }
        .stButton > button[kind="primary"] p,
        .stButton > button[kind="primary"] span {
            color: #f7fbff !important;
        }
        [data-testid="stPills"] [data-baseweb="button-group"] {
            gap: 0.65rem !important;
        }
        [data-testid="stPills"] button {
            min-height: 3.5rem !important;
            padding: 0.72rem 1rem !important;
            border-radius: 999px !important;
            background: rgba(255, 255, 255, 0.76) !important;
            border: 1px solid var(--conference-border) !important;
            box-shadow: 0 8px 20px rgba(19, 36, 52, 0.05);
        }
        [data-testid="stPills"] button[aria-pressed="true"] {
            background: var(--conference-accent-soft) !important;
            border-color: rgba(44, 111, 163, 0.45) !important;
        }
        [data-testid="stPills"] button p,
        [data-testid="stPills"] button span,
        [data-testid="stPills"] button div {
            font-family: var(--type-font-sans) !important;
            font-size: 1rem !important;
            line-height: 1.25 !important;
            white-space: normal !important;
            text-align: center !important;
            color: var(--conference-ink) !important;
        }
        .stTextInput input,
        .stTextArea textarea {
            min-height: 3.4rem;
            border-radius: 0.5rem !important;
            background: rgba(255, 255, 255, 0.82) !important;
            border-color: var(--conference-border) !important;
            color: var(--conference-ink) !important;
            font-family: var(--type-font-sans) !important;
        }
        .stTextInput label,
        .stTextArea label {
            color: var(--conference-muted) !important;
            font-family: var(--type-font-serif) !important;
        }
        [data-testid="stSidebar"] {
            background: rgba(238, 245, 251, 0.96);
            border-right: 1px solid var(--conference-border);
        }
        @media (max-width: 640px) {
            .block-container {
                padding-top: 1.4rem;
                padding-left: 1rem;
                padding-right: 1rem;
            }
            h1 {
                font-size: var(--type-page-title);
            }
            .entry-hero {
                padding: 0;
            }
            .st-key-conference_entry_card {
                padding: 1.5rem 1rem;
            }
            [data-testid="stPills"] button {
                min-height: 3.7rem !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def conference_header(title: str, body: str, step: str = "") -> None:
    safe_title = html.escape(str(title or ""))
    safe_body = html.escape(str(body or ""))
    safe_step = html.escape(str(step or ""))
    if step:
        st.markdown(
            f'<div class="page-kicker">{safe_step}</div>',
            unsafe_allow_html=True,
        )
    st.markdown(
        f'<h1 class="page-title">{safe_title}</h1>',
        unsafe_allow_html=True,
    )
    if body:
        st.markdown(
            f'<div class="conference-body helper-text">{safe_body}</div>',
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
