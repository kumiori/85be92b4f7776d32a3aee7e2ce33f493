from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List

import altair as alt
import pandas as pd
import streamlit as st

from conference.context import get_conference_bundle, get_conference_repo
from conference.models import FLOW_MODES, field_option_label_map
from ui import set_page, stylable_container


PISA_IMAGE_PATHS: List[str] = []
PISA_GALLERY_PATHS: List[str] = []

PISA_OPENING_LEAD = (
    "A readable opening format for the Pisa meeting, gathering signals about scientific identity, "
    "systems, motivations, obstacles, and directions for future work."
)

PISA_OPENING_PARAGRAPHS = [
    "This page is a reproducible opening format. It assembles the signals gathered during the Pisa meeting without forcing them into a generic platform narrative.",
    "What appears here is an anonymous field of orientations: how participants describe their work, what kinds of systems they study, where progress slows down, and which collective challenges attract attention.",
    "The purpose is not to close interpretation, but to create a shared surface that can be read together and extended later with images, text, and further traces from Pisa.",
]

PISA_SECTION_COPY: Dict[str, Dict[str, Any]] = {
    "profile": {
        "title": "Scientific identities",
        "lead": "Who is in the room, and from which trajectories do they speak?",
        "paragraphs": [
            "The meeting gathers multiple profiles rather than a single disciplinary bloc.",
            "These distributions help clarify whether the conversation is being carried primarily by theorists, numericians, experimentalists, data-oriented contributors, or mixed positions across them.",
            "Career stage matters as well: it reveals whether the room is exploratory, established, transitional, or intergenerational.",
        ],
        "fields": ["role", "career_stage"],
    },
    "systems": {
        "title": "Systems and expectations",
        "lead": "What kinds of phenomena are under study, and how smooth or abrupt are they expected to be?",
        "paragraphs": [
            "The systems field shows the scientific terrain currently occupying participants, from static settings to dynamic and multiphysics configurations.",
            "Expectations give a complementary signal: whether these systems are approached as smooth evolutions, occasional transitions, or genuinely discontinuous regimes.",
            "Taken together, these two views indicate whether the Pisa room is centred on continuity, thresholds, rupture, or a mixture of all three.",
        ],
        "fields": ["systems", "expectations"],
    },
    "formulation": {
        "title": "Formulations and reality checks",
        "lead": "How are problems formulated, and how tightly are they tied to measurements, observations, or experiments?",
        "paragraphs": [
            "Different mathematical languages reveal different structures. This field maps whether participants move through strong forms, weak forms, variational principles, energetic approaches, or hybrids.",
            "The reality check field asks how strongly those formulations remain anchored to experiments or observed phenomena.",
            "This pairing helps identify whether Pisa is mostly a space of abstract modelling, tightly coupled validation, or layered exchanges across both.",
        ],
        "fields": ["formulation", "reality_check"],
    },
    "scale": {
        "title": "Scale and motivations",
        "lead": "At what computational scale do questions become interesting, and what ultimately drives the work?",
        "paragraphs": [
            "Some questions can be pursued analytically or on modest machines, while others only become visible at larger computational scales.",
            "Motivations reveal whether the room is oriented more strongly by mathematical theory, numerical methods, curiosity, natural systems, industrial applications, or environmental pressures.",
            "Together these signals help us understand not just what people study, but why they stay with these problems and how far they need to go technically to move them.",
        ],
        "fields": ["scale", "motivations"],
    },
    "coordination": {
        "title": "Obstacles and collective challenges",
        "lead": "Where does progress slow down, and what forms of collective work feel worth joining?",
        "paragraphs": [
            "Obstacles show where the current bottlenecks are felt most strongly: models, data, computation, validation, theory, funding, or collaboration itself.",
            "Challenges show the opposite side of the picture: where enough critical mass might turn friction into a concrete collective activity.",
            "This is the operational core of the Pisa activation. Matchmaking begins only after this structure becomes visible.",
        ],
        "fields": ["obstacle", "challenge"],
    },
    "continuation": {
        "title": "Research ecosystems and continuation",
        "lead": "How does progress usually happen, on what timescale, and how open is the room to continuing the conversation?",
        "paragraphs": [
            "Research style makes visible whether work usually progresses alone, in a local team, in an open-source community, or within larger collaborations.",
            "Timescale indicates whether participants think naturally in weeks, months, or longer horizons.",
            "The continuation signal shows whether the anonymous interaction should remain a snapshot or become the beginning of something longer.",
        ],
        "fields": ["research_style", "timescale", "continue_conversation"],
    },
}


PISA_OPEN_TEXT_TITLE = "Anonymous notes from Pisa"
PISA_OPEN_TEXT_LEAD = "Some of the most interesting signals are not counts but sentences."
PISA_OPEN_TEXT_PARAGRAPHS = [
    "These notes retain the open-ended part of the meeting: benchmark ideas, frustrations, questions, and directions that did not fit into a fixed option list.",
    "They should be read as fragments rather than conclusions. Even short phrases can point to missing infrastructure, latent communities, or under-articulated needs.",
]

PISA_THEME = {
    "bg_top": "#f0efe8",
    "bg_bottom": "#e5dccd",
    "paper": "rgba(255,255,255,0.78)",
    "paper_soft": "rgba(255,255,255,0.58)",
    "ink": "#181713",
    "muted": "#5f5a51",
    "accent": "#8b5e3c",
    "plot": "#597ca8",
    "serif": "#7b6a5a",
    "rule": "rgba(24,23,19,0.12)",
    "chip_bg": "rgba(139,94,60,0.10)",
    "chip_fg": "#6e472a",
}

CARD_SOFT_CSS = """
background: rgba(255,255,255,0.58);
border: 1px solid rgba(24,23,19,0.08);
border-radius: 20px;
padding: 28px;
"""

CARD_SECTION_CSS = """
background: rgba(255,255,255,0.72);
border: 1px solid rgba(24,23,19,0.08);
border-radius: 20px;
padding: 34px;
margin-bottom: 40px;
"""

CARD_PAPER_CSS = """
background: rgba(255,255,255,0.92);
border: 1px solid rgba(24,23,19,0.10);
border-radius: 22px;
padding: 30px 32px;
margin: 0 0 24px 0;
box-shadow: 0 12px 26px rgba(24,23,19,0.06);
"""


def _apply_page_css() -> None:
    palette = PISA_THEME
    st.markdown(
        f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght,SOFT@9..144,300..700,0..100&family=Space+Grotesk:wght@400;500;700&display=swap');

:root {{
  --pisa-bg-top: {palette["bg_top"]};
  --pisa-bg-bottom: {palette["bg_bottom"]};
  --pisa-paper: {palette["paper"]};
  --pisa-paper-soft: {palette["paper_soft"]};
  --pisa-ink: {palette["ink"]};
  --pisa-muted: {palette["muted"]};
  --pisa-accent: {palette["accent"]};
  --pisa-serif: {palette["serif"]};
  --pisa-rule: {palette["rule"]};
  --pisa-chip-bg: {palette["chip_bg"]};
  --pisa-chip-fg: {palette["chip_fg"]};
}}

html, body, [data-testid="stAppViewContainer"] {{
  background:
    radial-gradient(circle at top, rgba(255,255,255,0.72), transparent 28%),
    linear-gradient(180deg, var(--pisa-bg-top) 0%, var(--pisa-bg-bottom) 100%);
}}

.block-container {{
  max-width: 1220px !important;
  padding-top: 2.4rem !important;
  padding-bottom: 5rem !important;
}}

[data-testid="stHeadingWithActionElements"] h1,
[data-testid="stHeadingWithActionElements"] h2,
[data-testid="stHeadingWithActionElements"] h3,
[data-testid="stMarkdownContainer"],
[data-testid="stCaptionContainer"],
[data-testid="stMetricLabel"],
[data-testid="stMetricValue"] {{
  font-family: "Space Grotesk", "Avenir Next", "Segoe UI", sans-serif;
  color: var(--pisa-ink);
}}

.pisa-kicker {{
  font-family: "Fraunces", Georgia, serif;
  font-size: 1.18rem;
  line-height: 1.14;
  color: var(--pisa-serif);
  margin-bottom: 0.65rem;
}}

[data-testid="stMarkdownContainer"] p.pisa-body {{
  font-size: 1.2rem;
  line-height: 1.62;
  max-width: 62ch;
  letter-spacing: -0.01em;
  margin: 0 0 1.25rem 0;
}}

.pisa-accent {{
  font-family: "Fraunces", Georgia, serif;
  color: var(--pisa-accent);
}}

[data-testid="stMarkdownContainer"] p.pisa-note {{
  font-family: "Fraunces", Georgia, serif;
  font-size: 1.12rem;
  line-height: 1.5;
  color: var(--pisa-muted);
  margin: 0 0 1.25rem 0;
}}

.pisa-token code {{
  font-family: ui-monospace, "SFMono-Regular", monospace;
  padding: 0.08rem 0.32rem;
  border-radius: 999px;
  background: var(--pisa-chip-bg);
  color: var(--pisa-chip-fg);
}}

div[data-testid="stImage"] img {{
  border-radius: 0 !important;
}}

[data-testid="stHeadingWithActionElements"] h1 {{
  line-height: 1.04 !important;
  margin-bottom: 1.2rem !important;
}}

[data-testid="stHeadingWithActionElements"] h2,
[data-testid="stHeadingWithActionElements"] h3 {{
  line-height: 1.12 !important;
  margin-bottom: 1.2rem !important;
}}
</style>
""",
        unsafe_allow_html=True,
    )


def _counts(submissions: List[Dict[str, Any]], field: str) -> Counter:
    counter: Counter = Counter()
    for row in submissions:
        value = row.get(field)
        if isinstance(value, list):
            for item in value:
                token = str(item or "").strip()
                if token:
                    counter[token] += 1
        else:
            token = str(value or "").strip()
            if token:
                counter[token] += 1
    return counter


def _labels_for(field: str, value: Any) -> str:
    if field == "mode":
        mode_spec = FLOW_MODES.get(str(value or "").strip(), {})
        return str(mode_spec.get("title") or value or "Unknown")
    label_map = field_option_label_map(field)
    if isinstance(value, list):
        return ", ".join(label_map.get(str(item), str(item)) for item in value if str(item)) or "None"
    if isinstance(value, str):
        return label_map.get(value, value) if value else "No answer"
    return str(value or "No answer")


def _counts_sentence(field: str, counts: Dict[str, int]) -> str:
    if not counts:
        return "No signals have been recorded yet."
    items = sorted(counts.items(), key=lambda item: (-int(item[1]), str(item[0]).lower()))
    top = items[:3]
    fragments = [f"{_labels_for(field, key)} ({value})" for key, value in top]
    if len(fragments) == 1:
        clause = fragments[0]
    elif len(fragments) == 2:
        clause = " and ".join(fragments)
    else:
        clause = ", ".join(fragments[:-1]) + f", and {fragments[-1]}"
    total = sum(int(value) for _, value in items)
    return f"The strongest signals are {clause}, across {total} recorded selections."


def _render_prose(paragraphs: List[str], *, accent_first: bool = False) -> None:
    for idx, paragraph in enumerate(paragraphs):
        if idx == 0 and accent_first:
            st.markdown(
                f"<p class='pisa-accent' style='font-size:1.6rem;line-height:1.18;margin:0 0 1.25rem 0;max-width:62ch;'>{paragraph}</p>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(f"<p class='pisa-body'>{paragraph}</p>", unsafe_allow_html=True)


def _render_black_lead(text: str, *, max_width: str = "18ch") -> None:
    st.markdown(
        f"<p style='font-family:\"Space Grotesk\", sans-serif;font-size:2.2rem;line-height:1.08;font-weight:700;letter-spacing:-0.05em;margin:0 0 1.2rem 0;max-width:{max_width};'>{text}</p>",
        unsafe_allow_html=True,
    )


def _render_metric_stack(value: Any, label: str) -> None:
    st.markdown(
        f"<div style='margin-bottom:1.1rem;'>"
        f"<div style='font-family:\"Space Grotesk\", sans-serif;font-size:3.2rem;line-height:0.96;font-weight:500;letter-spacing:-0.04em;color:var(--pisa-ink);white-space:nowrap;'>{value}</div>"
        f"<div style='font-family:\"Space Grotesk\", sans-serif;font-size:0.95rem;line-height:1.25;font-weight:400;color:var(--pisa-muted);margin-top:0.35rem;white-space:nowrap;'>{label}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )


def _render_data_tokens(metrics: Dict[str, Any]) -> None:
    st.markdown(
        "<p class='pisa-body pisa-token'>"
        f"<code>{metrics['participants']} participants</code> "
        f"<code>{metrics['follow_up']} follow-up signals</code> "
        f"<code>{metrics['deep_dives']} deep dives</code> "
        f"<code>{metrics['notes']} anonymous notes</code>"
        "</p>",
        unsafe_allow_html=True,
    )


def _chart_df(field: str, counts: Dict[str, int]) -> pd.DataFrame:
    rows = [
        {"label": _labels_for(field, key), "value": int(value)}
        for key, value in counts.items()
        if int(value) > 0
    ]
    rows.sort(key=lambda row: (-row["value"], row["label"].lower()))
    return pd.DataFrame(rows)


def _render_horizontal_chart(field: str, counts: Dict[str, int], *, title: str = "") -> None:
    df = _chart_df(field, counts)
    if df.empty:
        st.caption(f"{title or field}: no data yet.")
        return
    chart = (
        alt.Chart(df)
        .mark_bar(color=PISA_THEME["plot"], cornerRadiusEnd=4)
        .encode(
            x=alt.X("value:Q", title="Count", axis=alt.Axis(format="d")),
            y=alt.Y(
                "label:N",
                sort="-x",
                title=None,
                axis=alt.Axis(labelLimit=1000, labelOverlap=False),
            ),
            tooltip=["label:N", alt.Tooltip("value:Q", format=".0f")],
        )
        .properties(
            title=title or field.replace("_", " ").title(),
            height=max(220, 36 * len(df)),
            padding={"left": 24, "right": 40, "top": 28, "bottom": 20},
        )
    )
    st.altair_chart(chart, width="stretch")


def _render_dual_chart_block(field_a: str, field_b: str, submissions: List[Dict[str, Any]]) -> None:
    _render_horizontal_chart(field_a, _counts(submissions, field_a), title=field_a.replace("_", " ").title())
    st.divider()
    _render_horizontal_chart(field_b, _counts(submissions, field_b), title=field_b.replace("_", " ").title())


def _render_hero() -> None:
    st.markdown(
        f"""
<div style="background:linear-gradient(135deg, rgba(255,255,255,0.84), rgba(248,243,237,0.76)); border:1px solid rgba(24,23,19,0.10); border-radius:28px; padding:48px 44px 44px; box-shadow:0 14px 40px rgba(27,21,14,0.06); margin-bottom:40px;">
  <div class='pisa-kicker'>Pisa Opening</div>
  <h1 style="margin:0 0 1rem 0;">Orchestrating solvers for real problems.</h1>
  <p class='pisa-accent' style='font-size:1.55rem;line-height:1.12;margin:0;max-width:none;'>{PISA_OPENING_LEAD}</p>
</div>
""",
        unsafe_allow_html=True,
    )


def _render_opening(metrics: Dict[str, Any]) -> None:
    left, right = st.columns([1.15, 0.85], vertical_alignment="top")
    with left:
        with stylable_container(key="pisa-opening-text", css_styles=CARD_SECTION_CSS):
            st.caption("Opening")
            _render_prose(PISA_OPENING_PARAGRAPHS)
    with right:
        with stylable_container(
            key="pisa-opening-metrics",
            css_styles=CARD_SOFT_CSS + "\nmargin-bottom:24px;",
        ):
            st.caption("Signals at a glance")
            _render_metric_stack(metrics["participants"], "participants")
            _render_metric_stack(metrics["deep_dives"], "deep dives")
            _render_metric_stack(metrics["follow_up"], "follow-up signals")
            _render_metric_stack(metrics["notes"], "anonymous notes")
        with stylable_container(key="pisa-opening-tokens", css_styles=CARD_SOFT_CSS):
            st.caption("Data tokens")
            _render_data_tokens(metrics)


def _render_image_block(paths: List[str], *, caption: str, title: str) -> None:
    if not paths:
        with stylable_container(key=f"pisa-image-slot-{title}", css_styles=CARD_PAPER_CSS):
            st.caption("Image slot")
            _render_black_lead(title, max_width="none")
            st.markdown(
                f"<p class='pisa-note' style='max-width:none;'>{caption}</p>",
                unsafe_allow_html=True,
            )
        return
    for image_path in paths:
        st.image(image_path, width="stretch")
    st.caption(caption)


def _render_text_and_data(title: str, lead: str, paragraphs: List[str], render_data, *, data_left: bool = False) -> None:
    st.caption(title)
    _render_black_lead(lead, max_width="none")
    left, right = st.columns([1.25, 1], vertical_alignment="top")
    text_col, data_col = (right, left) if data_left else (left, right)
    with text_col:
        with stylable_container(
            key=f"pisa-{title.lower().replace(' ', '-')}-text",
            css_styles=CARD_SECTION_CSS + "\nmargin-bottom:0;\npadding:32px;\nheight:100%;",
        ):
            _render_prose(paragraphs)
    with data_col:
        with stylable_container(
            key=f"pisa-{title.lower().replace(' ', '-')}-data",
            css_styles=CARD_SOFT_CSS + "\nheight:100%;",
        ):
            render_data()
    st.markdown("<div style='height:2.5rem;'></div>", unsafe_allow_html=True)


def _render_open_text(submissions: List[Dict[str, Any]]) -> None:
    notes = [
        str(row.get("open_text") or "").strip()
        for row in submissions
        if str(row.get("open_text") or "").strip()
    ]
    st.caption(PISA_OPEN_TEXT_TITLE)
    _render_black_lead(PISA_OPEN_TEXT_LEAD, max_width="none")
    left, right = st.columns([1.15, 0.85], vertical_alignment="top")
    with left:
        with stylable_container(
            key="pisa-open-text-prose",
            css_styles=CARD_SECTION_CSS + "\nmargin-bottom:0;",
        ):
            _render_prose(PISA_OPEN_TEXT_PARAGRAPHS)
    with right:
        with stylable_container(
            key="pisa-open-text-notes",
            css_styles=CARD_SOFT_CSS + "\nheight:100%;",
        ):
            if notes:
                for note in notes[:8]:
                    st.markdown(
                        f"<p class='pisa-note' style='max-width:none;border-bottom:1px solid var(--pisa-rule);padding-bottom:0.95rem;margin-bottom:0.95rem;'>{note}</p>",
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("No open notes yet.")
    st.markdown("<div style='height:2.5rem;'></div>", unsafe_allow_html=True)


def _render_gallery() -> None:
    if not PISA_GALLERY_PATHS:
        return
    st.divider()
    st.caption("Images and traces")
    cols = st.columns(3)
    for idx, path in enumerate(PISA_GALLERY_PATHS):
        with cols[idx % 3]:
            st.image(path, width="stretch")
    st.caption("Additional traces from the Pisa meeting.")


def _metrics(submissions: List[Dict[str, Any]]) -> Dict[str, int]:
    follow_up = _counts(submissions, "continue_conversation")
    return {
        "participants": len(submissions),
        "deep_dives": _counts(submissions, "mode").get("deep", 0),
        "follow_up": follow_up.get("happy_to_engage", 0) + follow_up.get("maybe_later", 0),
        "notes": sum(1 for row in submissions if str(row.get("open_text") or "").strip()),
    }


def main() -> None:
    set_page()
    _apply_page_css()

    repo = get_conference_repo()
    if not repo or not repo.is_ready():
        st.error(repo.unavailable_reason if repo else "Conference repository is unavailable.")
        return

    bundle = get_conference_bundle()
    session = bundle.get("session")
    if not session:
        st.error("Conference session is missing. Ensure `pisa-conference-session` exists in the shared sessions DB.")
        return

    submissions = repo.group_rows_by_submission(repo.get_session_rows(session["id"]))
    metrics = _metrics(submissions)

    _render_hero()
    _render_opening(metrics)
    _render_image_block(
        PISA_IMAGE_PATHS[:1],
        caption="Image slot reserved for Pisa traces and photographs. You can drop the first opening image here later.",
        title="Pisa traces",
    )

    for idx, key in enumerate(["profile", "systems", "formulation", "scale", "coordination", "continuation"]):
        section = PISA_SECTION_COPY[key]
        fields = list(section["fields"])
        field_counts = [_counts(submissions, field) for field in fields]
        narrative = list(section["paragraphs"]) + [
            _counts_sentence(fields[0], field_counts[0]),
            _counts_sentence(fields[-1], field_counts[-1]),
        ]
        _render_text_and_data(
            str(section["title"]),
            str(section["lead"]),
            narrative,
            lambda f1=fields[0], f2=fields[-1]: _render_dual_chart_block(f1, f2, submissions),
            data_left=bool(idx % 2),
        )

    _render_open_text(submissions)
    _render_gallery()


if __name__ == "__main__":
    main()
