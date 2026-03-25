from __future__ import annotations

import streamlit as st

from ui import set_page, stylable_container


PALETTES = {
    "Paper": {
        "bg_top": "#f8f3eb",
        "bg_bottom": "#f4efe6",
        "paper": "rgba(255, 251, 244, 0.78)",
        "ink": "#161616",
        "muted": "#6b665f",
        "accent": "#de4f42",
        "rule": "rgba(22, 22, 22, 0.11)",
        "chip_bg": "rgba(222, 79, 66, 0.10)",
        "chip_fg": "#8f2f27",
    },
    "Swiss Red": {
        "bg_top": "#ef493d",
        "bg_bottom": "#e23d34",
        "paper": "rgba(255, 250, 247, 0.10)",
        "ink": "#111111",
        "muted": "rgba(17, 17, 17, 0.68)",
        "accent": "#fff4e8",
        "rule": "rgba(17, 17, 17, 0.20)",
        "chip_bg": "rgba(255, 244, 232, 0.24)",
        "chip_fg": "#fff4e8",
    },
    "Night Studio": {
        "bg_top": "#17181c",
        "bg_bottom": "#0f1013",
        "paper": "rgba(255, 255, 255, 0.04)",
        "ink": "#f4f1eb",
        "muted": "rgba(244, 241, 235, 0.62)",
        "accent": "#f3d64e",
        "rule": "rgba(244, 241, 235, 0.14)",
        "chip_bg": "rgba(243, 214, 78, 0.14)",
        "chip_fg": "#f3d64e",
    },
    "Glacier": {
        "bg_top": "#eef5fb",
        "bg_bottom": "#dde9f2",
        "paper": "rgba(255, 255, 255, 0.76)",
        "ink": "#132434",
        "muted": "#607384",
        "accent": "#2c6fa3",
        "rule": "rgba(19, 36, 52, 0.12)",
        "chip_bg": "rgba(44, 111, 163, 0.12)",
        "chip_fg": "#20577f",
    },
    "Moss": {
        "bg_top": "#eef1e5",
        "bg_bottom": "#dfe5d1",
        "paper": "rgba(255, 255, 251, 0.74)",
        "ink": "#172019",
        "muted": "#687264",
        "accent": "#6d7d3a",
        "rule": "rgba(23, 32, 25, 0.11)",
        "chip_bg": "rgba(109, 125, 58, 0.12)",
        "chip_fg": "#56632c",
    },
}


def _page_css(palette: dict[str, str]) -> None:
    st.markdown(
        f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght,SOFT@9..144,300..700,0..100&family=Space+Grotesk:wght@400;500;700&display=swap');

:root {{
  --type-bg-top: {palette["bg_top"]};
  --type-bg-bottom: {palette["bg_bottom"]};
  --type-paper: {palette["paper"]};
  --type-ink: {palette["ink"]};
  --type-muted: {palette["muted"]};
  --type-accent: {palette["accent"]};
  --type-rule: {palette["rule"]};
  --type-chip-bg: {palette["chip_bg"]};
  --type-chip-fg: {palette["chip_fg"]};
  --space-1: 8px;
  --space-2: 16px;
  --space-3: 24px;
  --space-4: 40px;
  --space-5: 64px;
}}

html, body, [data-testid="stAppViewContainer"] {{
  background:
    radial-gradient(circle at top, rgba(255,255,255,0.68), transparent 26%),
    linear-gradient(180deg, var(--type-bg-top) 0%, var(--type-bg-bottom) 100%);
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

.type-kicker {{
  font-family: "Fraunces", Georgia, serif;
  font-size: 1.2rem;
  line-height: 1.12;
  color: rgba(22,22,22,0.45);
}}

.type-accent {{
  font-family: "Fraunces", Georgia, serif;
  color: var(--type-accent);
}}

.type-note {{
  font-family: "Fraunces", Georgia, serif;
  font-size: 1.08rem;
  line-height: 1.45;
  color: var(--type-muted);
}}

.type-token code {{
  font-family: ui-monospace, "SFMono-Regular", monospace;
  padding: 0.08rem 0.32rem;
  border-radius: 999px;
  background: var(--type-chip-bg);
  color: var(--type-chip-fg);
}}

[data-testid="stMarkdownContainer"] p.type-body {{
  font-size: 1.08rem;
  line-height: 1.62;
  max-width: 62ch;
  letter-spacing: -0.01em;
}}

[data-testid="stMarkdownContainer"] p.type-body-narrow {{
  font-size: 1.02rem;
  line-height: 1.62;
  max-width: 30ch;
}}

[data-testid="stMarkdownContainer"] p.type-body-wide {{
  font-size: 1.02rem;
  line-height: 1.62;
  max-width: 96ch;
}}

[data-testid="stSegmentedControl"] button[aria-pressed="true"] {{
  background: var(--type-ink) !important;
  color: var(--type-bg-top) !important;
  border-color: var(--type-ink) !important;
}}

[data-testid="stSegmentedControl"] button {{
  border-radius: 999px !important;
}}

div[data-testid="stButton"] > button {{
  font-family: "Space Grotesk", "Avenir Next", "Segoe UI", sans-serif !important;
  font-weight: 700 !important;
  letter-spacing: 0.06em !important;
  text-transform: uppercase !important;
  border-radius: 999px !important;
  min-height: 3.2rem !important;
  transition:
    transform 120ms ease,
    box-shadow 120ms ease,
    background-color 120ms ease,
    color 120ms ease,
    border-color 120ms ease !important;
}}

div[data-testid="stButton"] > button[kind="primary"] {{
  background: var(--type-ink) !important;
  color: #f8fbff !important;
  border-color: var(--type-ink) !important;
  box-shadow: 0 10px 24px rgba(19, 36, 52, 0.12) !important;
}}

div[data-testid="stButton"] > button[kind="secondary"] {{
  background: transparent !important;
  color: var(--type-ink) !important;
  border: 2px solid var(--type-ink) !important;
}}

div[data-testid="stButton"] > button[kind="tertiary"] {{
  background: rgba(255,255,255,0.3) !important;
  color: var(--type-ink) !important;
  border: 1px solid var(--type-rule) !important;
}}

div[data-testid="stButton"] > button:hover {{
  transform: translateY(-1px) !important;
}}

div[data-testid="stButton"] > button[kind="primary"]:hover {{
  background: color-mix(in srgb, var(--type-ink) 88%, white 12%) !important;
  color: #ffffff !important;
  box-shadow: 0 14px 28px rgba(19, 36, 52, 0.18) !important;
}}

div[data-testid="stButton"] > button[kind="secondary"]:hover {{
  background: rgba(255,255,255,0.55) !important;
  box-shadow: 0 10px 20px rgba(19, 36, 52, 0.08) !important;
}}

div[data-testid="stButton"] > button[kind="tertiary"]:hover {{
  background: rgba(255,255,255,0.48) !important;
  box-shadow: 0 8px 16px rgba(19, 36, 52, 0.06) !important;
}}

div[data-testid="stButton"] > button:active {{
  transform: translateY(1px) scale(0.99) !important;
  box-shadow: none !important;
}}

div[data-testid="stButton"] > button:focus-visible {{
  outline: 3px solid color-mix(in srgb, var(--type-accent) 55%, white 45%) !important;
  outline-offset: 2px !important;
}}
</style>
""",
        unsafe_allow_html=True,
    )


def _hero() -> None:
    with stylable_container(
        key="type-hero-native",
        css_styles="""
background:
  linear-gradient(135deg, rgba(255,255,255,0.82), rgba(255,248,240,0.74)),
  rgba(255,251,244,0.9);
border: 1px solid rgba(22,22,22,0.10);
border-radius: 28px;
padding: 48px 44px 44px;
box-shadow: 0 14px 40px rgba(27, 21, 14, 0.06);
margin-bottom: 40px;
""",
        ):
            st.markdown("<div class='type-kicker'>Typography Lab · Native structure</div>", unsafe_allow_html=True)
            st.title("Use Streamlit structure first. Style the containers, not the page with fragments of HTML.")
            st.markdown(
                "<p class='type-accent' style='font-size:1.7rem;line-height:1.08;font-weight:430;margin-top:-0.35rem;'>"
                "Second experiment: same principles, fewer hardcoded blocks.</p>",
                unsafe_allow_html=True,
            )
            st.markdown(
                "<p class='type-body'>This version keeps the hierarchy, spacing, and pairing logic, but relies on native "
                "Streamlit headings, captions, columns, dividers, metrics, and bordered containers. The only CSS is "
                "scoped to container boundaries.</p>",
                unsafe_allow_html=True,
            )


def _section_intro() -> None:
    col1, col2 = st.columns([1.25, 1], vertical_alignment="top")
    with col1:
        with stylable_container(
            key="type-native-principles",
            css_styles="""
background: rgba(255,255,255,0.72);
border: 1px solid rgba(22,22,22,0.10);
border-radius: 18px;
padding: 32px;
""",
        ):
            st.caption("Pairing")
            st.subheader("Two families. One structure.")
            st.markdown(
                "<p class='type-body type-token'>"
                "<code>Space Grotesk</code> carries display, body, and interface structure. "
                "<code>Fraunces</code> is reserved for inflection, subtitles, and note-like cues. "
                "That is enough contrast without randomising the system."
                "</p>",
                unsafe_allow_html=True,
            )
    with col2:
        with stylable_container(
            key="type-native-rules",
            css_styles="""
background: rgba(255,255,255,0.56);
border: 1px solid rgba(22,22,22,0.08);
border-radius: 18px;
padding: 32px;
""",
        ):
            st.caption("Rules")
            st.metric("Body measure", "62ch", delta_description="aim for 45 to 75 characters")
            st.metric("Body line-height", "1.62", delta_description="comfortable reading rhythm")
            st.metric("Spacing scale", "8 / 16 / 24 / 40 / 64", delta_description="systematic, not guessed")


def _section_hierarchy() -> None:
    st.divider()
    st.caption("Hierarchy")
    st.header("Make the reading order explicit")

    left, right = st.columns([1.2, 1], vertical_alignment="top")
    with left:
        with stylable_container(
            key="type-native-hierarchy-sample",
            css_styles="""
background: rgba(255,255,255,0.78);
border: 1px solid rgba(22,22,22,0.10);
border-radius: 18px;
padding: 36px;
""",
        ):
            st.markdown("<div class='type-kicker'>Primary</div>", unsafe_allow_html=True)
            st.subheader("You will read this first.")
            st.markdown(
                "<p class='type-accent' style='font-size:1.45rem;line-height:1.08;margin-top:-0.35rem;'>"
                "Then this quieter contextual line.</p>",
                unsafe_allow_html=True,
            )
            st.markdown(
                "<p class='type-body'>And only then the supporting paragraph. Hierarchy is a sequence of emphasis, "
                "not a collection of large elements.</p>",
                unsafe_allow_html=True,
            )
    with right:
        with stylable_container(
            key="type-native-hierarchy-notes",
            css_styles="""
background: rgba(255,255,255,0.6);
border: 1px solid rgba(22,22,22,0.08);
border-radius: 18px;
padding: 28px;
""",
        ):
            st.markdown(
                "<p class='type-note'>Use weight contrast with restraint. A title can be heavy because the body remains calm.</p>",
                unsafe_allow_html=True,
            )
            st.markdown(
                "<p class='type-body type-token'><code>700</code> for the title. "
                "<code>430–500</code> for the serif accent. <code>400</code> for body copy.</p>",
                unsafe_allow_html=True,
            )


def _section_measure() -> None:
    st.divider()
    st.caption("Line length")
    st.header("Measure changes readability immediately")

    left, right = st.columns([1.2, 1], vertical_alignment="top")
    with left:
        with stylable_container(
            key="type-native-measure-ideal",
            css_styles="""
background: rgba(255,255,255,0.7);
border: 1px solid rgba(22,22,22,0.08);
border-radius: 18px;
padding: 28px;
min-height: 250px;
""",
        ):
            st.caption("Recommended body measure")
            st.markdown(
                "<p class='type-body'>A comfortable reading measure sits roughly between forty-five and seventy-five "
                "characters. This width supports rhythm, scanning, and retention without making the return sweep "
                "hard to track.</p>",
                unsafe_allow_html=True,
            )
    with right:
        with stylable_container(
            key="type-native-measure-rule",
            css_styles="""
background: rgba(255,255,255,0.6);
border: 1px solid rgba(22,22,22,0.08);
border-radius: 18px;
padding: 28px;
min-height: 250px;
""",
        ):
            st.metric("Target measure", "45–75", delta_description="characters per line")
            st.markdown(
                "<p class='type-note'>For narrative pages, keep body copy near <code>58–62ch</code>. "
                "For captions and mobile blocks, shorten the measure deliberately.</p>",
                unsafe_allow_html=True,
            )


def _section_line_height_and_spacing() -> None:
    st.divider()
    st.caption("Rhythm")
    st.header("Line-height and spacing should be systematic")

    left, right = st.columns([1, 1.15], vertical_alignment="top")
    with left:
        with stylable_container(
            key="type-native-lineheight",
            css_styles="""
background: rgba(255,255,255,0.74);
border: 1px solid rgba(22,22,22,0.08);
border-radius: 18px;
padding: 28px;
""",
        ):
            st.caption("Recommended rhythm")
            st.markdown(
                "<p style='font-family:\"Space Grotesk\", sans-serif;font-size:2.1rem;line-height:1.08;"
                "font-weight:700;letter-spacing:-0.05em;margin:0 0 20px 0;max-width:12ch;'>"
                "Tracking in typography is the adjustment of space between characters.</p>",
                unsafe_allow_html=True,
            )
            st.markdown(
                "<p class='type-body'>Display text can be tight, but it still needs air. "
                "Use a consistent line-height instead of testing multiple wrong variants on the page itself.</p>",
                unsafe_allow_html=True,
            )
    with right:
        with stylable_container(
            key="type-native-spacing",
            css_styles="""
background: rgba(255,255,255,0.6);
border: 1px solid rgba(22,22,22,0.08);
border-radius: 18px;
padding: 32px;
""",
        ):
            st.caption("Spacing scale")
            st.subheader("A short bold headline.")
            st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)
            st.markdown("<p class='type-accent' style='font-size:1.3rem;line-height:1.1;margin:0;'>This is a short subheading for longer messages.</p>", unsafe_allow_html=True)
            st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)
            st.markdown("<p class='type-body'>This is a body style for storytelling and longer messages.</p>", unsafe_allow_html=True)
            st.markdown("<div style='height:40px;'></div>", unsafe_allow_html=True)
            st.caption("Caption")


def _section_buttons_and_mobile() -> None:
    st.divider()
    st.caption("Application")
    st.header("Buttons and mobile are part of the type system")

    left, right = st.columns([1, 1], vertical_alignment="top")
    with left:
        with stylable_container(
            key="type-native-buttons",
            css_styles="""
background: rgba(255,255,255,0.78);
border: 1px solid rgba(22,22,22,0.10);
border-radius: 18px;
padding: 32px;
""",
        ):
            b1, b2, b3 = st.columns(3)
            with b1:
                st.button("Primary", type="primary", key="type-native-btn-primary", width="stretch")
            with b2:
                st.button("Secondary", type="secondary", key="type-native-btn-secondary", width="stretch")
            with b3:
                st.button("Tertiary", type="tertiary", key="type-native-btn-tertiary", width="stretch")
            st.markdown(
                "<p class='type-body'>Do not make the button fight with the headline. The primary action can arrive after "
                "the supporting text if the structure first establishes what the action means.</p>",
                unsafe_allow_html=True,
            )
    with right:
        with stylable_container(
            key="type-native-mobile",
            css_styles="""
background: rgba(255,255,255,0.62);
border: 1px solid rgba(22,22,22,0.08);
border-radius: 18px;
padding: 32px;
""",
        ):
            st.caption("Mobile check")
            st.subheader("Stack first")
            st.markdown(
                "<p class='type-body type-token'>On a phone, text should usually come before charts. "
                "Titles shrink, but the hierarchy remains. Keep the same families, reduce the measure, and preserve the spacing ratio.</p>",
                unsafe_allow_html=True,
            )
            st.caption("In this example the primary button is intentionally read last, after the message has been established.")
            st.button("Example CTA", type="primary", width="stretch", key="type-native-mobile-cta")


def _section_tokens() -> None:
    st.divider()
    with stylable_container(
        key="type-native-tokens",
        css_styles="""
background: rgba(255,255,255,0.78);
border: 1px solid rgba(22,22,22,0.10);
border-radius: 18px;
padding: 32px;
margin-top: 8px;
""",
    ):
        st.caption("Integration tokens")
        st.subheader("What should move into the main app")
        st.markdown(
            "<p class='type-body type-token'>"
            "<code>--font-display: Space Grotesk</code><br/>"
            "<code>--font-accent: Fraunces</code><br/>"
            "<code>--font-body: Space Grotesk</code><br/>"
            "<code>--measure-body: 62ch</code><br/>"
            "<code>--lh-body: 1.62</code><br/>"
            "<code>--lh-display: 0.92</code><br/>"
            "<code>--space-scale: 8 / 16 / 24 / 40 / 64</code>"
            "</p>",
            unsafe_allow_html=True,
        )
        st.info(
            "If this experiment feels easier to work with, integrate it first into narrative pages, then section titles and CTA blocks, and only afterwards into shared app styles."
        )


def main() -> None:
    set_page()

    palette_name = st.segmented_control(
        "Palette",
        options=list(PALETTES.keys()),
        default="Glacier",
        selection_mode="single",
        key="typography_native_palette",
    )
    palette = PALETTES.get(str(palette_name), PALETTES["Glacier"])
    _page_css(palette)

    _hero()
    _section_intro()
    _section_hierarchy()
    _section_measure()
    _section_line_height_and_spacing()
    _section_buttons_and_mobile()
    _section_tokens()


if __name__ == "__main__":
    main()
