from __future__ import annotations

import streamlit as st

from ui import set_page, stylable_container


PALETTE = {
    "bg_top": "#eef5fb",
    "bg_bottom": "#dde9f2",
    "paper": "rgba(255, 255, 255, 0.76)",
    "ink": "#132434",
    "muted": "#607384",
    "accent": "#2c6fa3",
    "rule": "rgba(19, 36, 52, 0.12)",
    "chip_bg": "rgba(44, 111, 163, 0.12)",
    "chip_fg": "#20577f",
}


def _page_css() -> None:
    st.markdown(
        f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght,SOFT@9..144,300..700,0..100&family=Space+Grotesk:wght@400;500;700&display=swap');

:root {{
  --type-bg-top: {PALETTE["bg_top"]};
  --type-bg-bottom: {PALETTE["bg_bottom"]};
  --type-paper: {PALETTE["paper"]};
  --type-ink: {PALETTE["ink"]};
  --type-muted: {PALETTE["muted"]};
  --type-accent: {PALETTE["accent"]};
  --type-rule: {PALETTE["rule"]};
  --type-chip-bg: {PALETTE["chip_bg"]};
  --type-chip-fg: {PALETTE["chip_fg"]};
}}

html, body, [data-testid="stAppViewContainer"] {{
  background:
    radial-gradient(circle at top, rgba(255,255,255,0.68), transparent 26%),
    linear-gradient(180deg, var(--type-bg-top) 0%, var(--type-bg-bottom) 100%);
}}

[data-testid="stHeader"] {{
  background: transparent;
}}

.block-container {{
  max-width: 1220px !important;
  padding-top: 2.4rem !important;
  padding-bottom: 4.8rem !important;
}}

[data-testid="stHeadingWithActionElements"] h1,
[data-testid="stHeadingWithActionElements"] h2,
[data-testid="stHeadingWithActionElements"] h3,
[data-testid="stMarkdownContainer"],
[data-testid="stCaptionContainer"],
[data-testid="stMetricLabel"],
[data-testid="stMetricValue"],
[data-testid="stMetricDelta"] {{
  font-family: "Space Grotesk", "Avenir Next", "Segoe UI", sans-serif;
  color: var(--type-ink);
}}

.ql-kicker {{
  font-family: "Fraunces", Georgia, serif;
  font-size: 1.2rem;
  line-height: 1.12;
  color: rgba(19, 36, 52, 0.46);
}}

.ql-accent {{
  font-family: "Fraunces", Georgia, serif;
  color: var(--type-accent);
}}

.ql-note {{
  font-family: "Fraunces", Georgia, serif;
  font-size: 1.08rem;
  line-height: 1.45;
  color: var(--type-muted);
}}

[data-testid="stMarkdownContainer"] p.ql-body {{
  font-size: 1.08rem;
  line-height: 1.62;
  max-width: 62ch;
  letter-spacing: -0.01em;
}}

[data-testid="stMarkdownContainer"] p.ql-body-narrow {{
  font-size: 1.02rem;
  line-height: 1.62;
  max-width: 34ch;
}}

.ql-token code {{
  font-family: ui-monospace, "SFMono-Regular", monospace;
  padding: 0.08rem 0.32rem;
  border-radius: 999px;
  background: var(--type-chip-bg);
  color: var(--type-chip-fg);
}}

div[data-testid="stButton"] > button {{
  font-family: "Space Grotesk", "Avenir Next", "Segoe UI", sans-serif !important;
  font-weight: 700 !important;
  letter-spacing: 0.06em !important;
  text-transform: uppercase !important;
  border-radius: 999px !important;
  min-height: 3.2rem !important;
}}

div[data-testid="stButton"] > button[kind="primary"] {{
  background: var(--type-ink) !important;
  color: #f8fbff !important;
  border-color: var(--type-ink) !important;
  box-shadow: 0 10px 24px rgba(19, 36, 52, 0.12) !important;
}}

div[data-testid="stButton"] > button[kind="primary"] p {{
  color: #f8fbff !important;
}}

div[data-testid="stButton"] > button[kind="secondary"] {{
  background: transparent !important;
  color: var(--type-ink) !important;
  border: 2px solid var(--type-ink) !important;
}}

div[data-testid="stButton"] > button[kind="secondary"] p,
div[data-testid="stButton"] > button[kind="tertiary"] p {{
  color: var(--type-ink) !important;
}}

div[data-testid="stButton"] > button[kind="tertiary"] {{
  background: rgba(255,255,255,0.3) !important;
  color: var(--type-ink) !important;
  border: 1px solid var(--type-rule) !important;
}}
</style>
        """,
        unsafe_allow_html=True,
    )


def _hero() -> None:
    with stylable_container(
        key="questionnaire-native-hero",
        css_styles="""
background:
  linear-gradient(135deg, rgba(255,255,255,0.82), rgba(241,248,252,0.74)),
  rgba(255,255,255,0.88);
border: 1px solid rgba(19,36,52,0.10);
border-radius: 28px;
padding: 48px 44px 44px;
box-shadow: 0 14px 40px rgba(19, 36, 52, 0.07);
margin-bottom: 40px;
""",
    ):
        st.markdown(
            "<div class='ql-kicker'>Questionnaire landing · Native typography</div>",
            unsafe_allow_html=True,
        )
        st.title("Collective visibility for actionable cryosphere projections")
        st.markdown(
            "<p class='ql-accent' style='font-size:1.7rem;line-height:1.08;font-weight:430;margin-top:-0.35rem;'>"
            "A first WG2 coordination map, built from participant signals.</p>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<p class='ql-body'>This reference keeps the calm structure from the native typography lab: native headings, "
            "measured body copy, one accent voice, and interface actions that support the page instead of competing with it.</p>",
            unsafe_allow_html=True,
        )
        left, right = st.columns([0.55, 0.45], vertical_alignment="center")
        with left:
            st.button("Start questionnaire", type="primary", width="stretch")
        with right:
            st.button("I have an access key", type="secondary", width="stretch")


def _purpose_and_pilot() -> None:
    left, right = st.columns([1.2, 1], vertical_alignment="top")
    with left:
        with stylable_container(
            key="questionnaire-native-purpose",
            css_styles="""
background: rgba(255,255,255,0.72);
border: 1px solid rgba(19,36,52,0.10);
border-radius: 18px;
padding: 32px;
""",
        ):
            st.caption("Purpose")
            st.subheader("Reveal who is present, what is needed, and where coordination can begin.")
            st.markdown(
                "<p class='ql-body'>The landing page should create orientation before asking for data. "
                "It explains why the questionnaire exists, what kind of signal it produces, and why participation is worth the time.</p>",
                unsafe_allow_html=True,
            )
    with right:
        with stylable_container(
            key="questionnaire-native-pilot",
            css_styles="""
background: rgba(255,255,255,0.56);
border: 1px solid rgba(19,36,52,0.08);
border-radius: 18px;
padding: 32px;
""",
        ):
            st.caption("This pilot")
            st.markdown(
                "<p class='ql-note'>Anonymous by default. Editable. Profile details remain under participant control. "
                "Session answers stay inside this pilot.</p>",
                unsafe_allow_html=True,
            )
            st.metric("Estimated time", "5-7 min", delta_description="lightweight first pass")
            st.metric("Output", "coordination map", delta_description="needs, roles, regions, signals")


def _flow_preview() -> None:
    st.divider()
    st.caption("Flow")
    st.header("The questionnaire should feel like a conversation")
    col1, col2, col3 = st.columns(3, vertical_alignment="top")
    blocks = [
        (
            "I. Who is speaking?",
            "Role, organisation, location, domains, strengths.",
            "person",
        ),
        (
            "II. What is your perspective?",
            "Needs, uncertainty, policy interface, timescale.",
            "space / time",
        ),
        (
            "III. What are we building together?",
            "Contribution, coordination signal, follow-up, review.",
            "coordination",
        ),
    ]
    for column, (title, body, token) in zip((col1, col2, col3), blocks):
        with column:
            with stylable_container(
                key=f"questionnaire-native-flow-{token}",
                css_styles="""
background: rgba(255,255,255,0.62);
border: 1px solid rgba(19,36,52,0.09);
border-radius: 18px;
padding: 28px;
min-height: 230px;
""",
            ):
                st.markdown(f"<div class='ql-kicker'>{token}</div>", unsafe_allow_html=True)
                st.subheader(title)
                st.markdown(f"<p class='ql-body-narrow'>{body}</p>", unsafe_allow_html=True)


def _actions() -> None:
    st.divider()
    left, right = st.columns([1.2, 1], vertical_alignment="top")
    with left:
        st.caption("Action rhythm")
        st.header("One primary action. Secondary paths stay quiet.")
        st.markdown(
            "<p class='ql-body ql-token'>The final landing pattern can use <code>primary</code>, <code>secondary</code>, "
            "and <code>tertiary</code> button states without inventing separate HTML controls.</p>",
            unsafe_allow_html=True,
        )
    with right:
        st.button("Start", type="primary", width="stretch")
        st.button("Use access key", type="secondary", width="stretch")
        st.button("Preview questions", type="tertiary", width="stretch")


def main() -> None:
    set_page()
    _page_css()
    _hero()
    _purpose_and_pilot()
    _flow_preview()
    _actions()


if __name__ == "__main__":
    main()
