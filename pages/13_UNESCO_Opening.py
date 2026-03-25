from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import altair as alt
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from infra.event_logger import log_event
from services.aggregator import get_overview_payload
from services.presence import count_active_users
from ui import apply_theme, set_page, stylable_container

COPY_PATH = Path("data/unesco-opening.txt")
GLOBAL_SESSION_SLUG = "global-session"
IMAGE_URLS = [
    "https://i.postimg.cc/c1zZQRmx/Delhom-JF-031825.jpg",
    "https://i.postimg.cc/ryHcS1Jq/Delhom-JF-032452.jpg",
    "https://i.postimg.cc/3rq7gXBh/Delhom-JF-032659.jpg",
    "https://i.postimg.cc/SQPqW6rq/Delhom-JF-033442.jpg",
]
SOUNDCLOUD_EMBED = """
<iframe width="100%" height="120" scrolling="no" frameborder="no" allow="autoplay"
src="https://w.soundcloud.com/player/?url=https%3A//api.soundcloud.com/tracks/soundcloud%253Atracks%253A2286855149&color=%23ff5500&auto_play=false">
</iframe>
""".strip()

SECTION_KEYS = {
    "1. OPENING — reframed incipit": "opening",
    "PANEL (integrated, not dominant)": "panel",
    "2. CORE OBJECTIVE — call to action": "core_objective",
    "3. TRANSITION — introducing the method": "method",
    "4. ARRIVAL — initial conditions": "arrival",
    "5. INTERPRETATION — first signal": "arrival_interpretation",
    "6. DEEPENING — environmental change": "environment",
    "7. SOCIETAL PROJECTION — shift in tone": "societal",
    "8. DECISION PIVOT — collective signal": "decision",
    "9. META — interpretation of signals": "meta",
    "10. CLOSING TRANSITION": "closing",
}

SOUND_BLOCK = {
    "title": "Have you ever heard the voice of a glacier?",
    "subtitle": "Have you ever heard how it cracks at night and how it collapses in the daylight?",
    "quote": (
        "In the words of Liz Macedo, Guardian of the Ishinca Hut in Peru, "
        "\“It is as if the mountain is screaming. The roar of the falling ice makes me think "
        "Tocllaraju is crying for help.\”"
    ),
    "prompt": (
        "We ask you a question that may or may not guide our and your next steps, "
        "a question that our daughters, sons, and grandchildren will surely ask us: "
        "What did we do, when we knew?"
    ),
}

GLACIER_THEME = {
    "bg_top": "#eef5fb",
    "bg_bottom": "#dde9f2",
    "paper": "rgba(255, 255, 255, 0.78)",
    "paper_soft": "rgba(255, 255, 255, 0.58)",
    "ink": "#132434",
    "muted": "#607384",
    "accent": "#2c6fa3",
    "serif": "#6c7888",
    "rule": "rgba(19, 36, 52, 0.12)",
    "chip_bg": "rgba(44, 111, 163, 0.10)",
    "chip_fg": "#20577f",
}

EMOTION_CLUSTER_ORDER = [
    "Curiosity and openness",
    "Engagement",
    "Tension and conflict",
    "Responsibility and action",
    "Other",
]

EMOTION_CLUSTER_MAP = {
    "curious": "Curiosity and openness",
    "curiosity": "Curiosity and openness",
    "open": "Curiosity and openness",
    "wonder": "Curiosity and openness",
    "reflective": "Curiosity and openness",
    "fascination": "Curiosity and openness",
    "awe": "Curiosity and openness",
    "engaged": "Engagement",
    "engagement": "Engagement",
    "hopeful": "Engagement",
    "hope": "Engagement",
    "calm": "Engagement",
    "solidarity": "Engagement",
    "energised": "Engagement",
    "inspired": "Engagement",
    "protective": "Responsibility and action",
    "responsibility": "Responsibility and action",
    "responsible": "Responsibility and action",
    "care": "Responsibility and action",
    "concerned": "Tension and conflict",
    "concern": "Tension and conflict",
    "urgency": "Tension and conflict",
    "fear": "Tension and conflict",
    "anxiety": "Tension and conflict",
    "anger": "Tension and conflict",
    "conflicted": "Tension and conflict",
    "overwhelmed": "Tension and conflict",
    "sceptical": "Tension and conflict",
    "skeptical": "Tension and conflict",
    "powerlessness": "Tension and conflict",
    "frustration": "Tension and conflict",
    "grief": "Tension and conflict",
    "sadness": "Tension and conflict",
    "helplessness": "Tension and conflict",
    "uncertainty": "Tension and conflict",
}

EMOTION_CLUSTER_COLOURS = {
    "Curiosity and openness": "#6c8db8",
    "Engagement": "#5f9f67",
    "Tension and conflict": "#d06a6a",
    "Responsibility and action": "#ea8e52",
    "Other": "#9a9a9a",
}


def _apply_page_css() -> None:
    palette = GLACIER_THEME
    st.markdown(
        f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght,SOFT@9..144,300..700,0..100&family=Space+Grotesk:wght@400;500;700&display=swap');

:root {{
  --unesco-bg-top: {palette['bg_top']};
  --unesco-bg-bottom: {palette['bg_bottom']};
  --unesco-paper: {palette['paper']};
  --unesco-paper-soft: {palette['paper_soft']};
  --unesco-ink: {palette['ink']};
  --unesco-muted: {palette['muted']};
  --unesco-accent: {palette['accent']};
  --unesco-serif: {palette['serif']};
  --unesco-rule: {palette['rule']};
  --unesco-chip-bg: {palette['chip_bg']};
  --unesco-chip-fg: {palette['chip_fg']};
}}

html, body, [data-testid="stAppViewContainer"] {{
  background:
    radial-gradient(circle at top, rgba(255,255,255,0.68), transparent 26%),
    linear-gradient(180deg, var(--unesco-bg-top) 0%, var(--unesco-bg-bottom) 100%);
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
[data-testid="stMetricValue"],
[data-testid="stMetricDelta"] {{
  font-family: "Space Grotesk", "Avenir Next", "Segoe UI", sans-serif;
  color: var(--unesco-ink);
}}

.unesco-kicker {{
  font-family: "Fraunces", Georgia, serif;
  font-size: 1.18rem;
  line-height: 1.14;
  color: var(--unesco-serif);
}}

.unesco-body {{
  font-size: 1.08rem;
  line-height: 1.62;
  max-width: 62ch;
  letter-spacing: -0.01em;
}}

.unesco-accent {{
  font-family: "Fraunces", Georgia, serif;
  color: var(--unesco-accent);
}}

.unesco-note {{
  font-family: "Fraunces", Georgia, serif;
  font-size: 1.04rem;
  line-height: 1.5;
  color: var(--unesco-muted);
}}

.unesco-token code {{
  font-family: ui-monospace, "SFMono-Regular", monospace;
  padding: 0.08rem 0.32rem;
  border-radius: 999px;
  background: var(--unesco-chip-bg);
  color: var(--unesco-chip-fg);
}}

.unesco-centre {{
  text-align: center;
}}

div[data-testid="stImage"] img {{
  border-radius: 0 !important;
}}
</style>
""",
        unsafe_allow_html=True,
    )


def _load_text_blocks() -> Dict[str, List[str]]:
    if not COPY_PATH.exists():
        return {key: [] for key in SECTION_KEYS.values()}
    raw = COPY_PATH.read_text(encoding="utf-8").strip()
    chunks = [chunk.strip() for chunk in raw.split("⸻") if chunk.strip()]
    blocks: Dict[str, List[str]] = {key: [] for key in SECTION_KEYS.values()}
    for chunk in chunks:
        lines = [line.rstrip() for line in chunk.splitlines()]
        heading = lines[0].strip() if lines else ""
        block_key = SECTION_KEYS.get(heading)
        if not block_key:
            continue
        body = "\n".join(lines[1:]).strip()
        blocks[block_key] = [paragraph.strip() for paragraph in body.split("\n\n") if paragraph.strip()]
    return blocks


def _emotion_cluster(label: str) -> str:
    token = str(label or "").strip().lower()
    if token in EMOTION_CLUSTER_MAP:
        return EMOTION_CLUSTER_MAP[token]
    if "responsib" in token or "care" in token:
        return "Responsibility and action"
    if "curio" in token or "open" in token or "awe" in token:
        return "Curiosity and openness"
    if "engag" in token or "hope" in token or "inspir" in token:
        return "Engagement"
    if any(marker in token for marker in ["fear", "anx", "anger", "sad", "concern", "urg", "conflict", "overwhelm", "grief", "powerless", "scept", "skept", "uncertain"]):
        return "Tension and conflict"
    return "Other"


def _counts_df(counts: Dict[str, int]) -> pd.DataFrame:
    rows = [{"label": str(k), "value": int(v)} for k, v in (counts or {}).items()]
    rows.sort(key=lambda row: row["value"], reverse=True)
    return pd.DataFrame(rows)


def _normalise_org_signal_counts(counts: Dict[str, int]) -> Dict[str, int]:
    buckets = {"yes": 0, "maybe": 0, "no": 0}
    for label, count in (counts or {}).items():
        text = str(label or "").strip().lower()
        if "yes" in text:
            buckets["yes"] += int(count)
        elif "maybe" in text:
            buckets["maybe"] += int(count)
        elif "no" in text:
            buckets["no"] += int(count)
    return buckets


def _render_prose(paragraphs: List[str], *, accent_first: bool = False) -> None:
    for idx, paragraph in enumerate(paragraphs):
        if idx == 0 and accent_first:
            st.markdown(
                f"<p class='unesco-accent' style='font-size:1.6rem;line-height:1.12;margin:0 0 1rem 0;'>{paragraph}</p>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(f"<p class='unesco-body'>{paragraph}</p>", unsafe_allow_html=True)


def _render_data_tokens(metrics: Dict[str, Any]) -> None:
    st.markdown(
        "<p class='unesco-body unesco-token'>"
        f"<code>{metrics['responses']} responses</code> "
        f"<code>{metrics['participants']} participants</code> "
        f"<code>{metrics['active_24h']} active in the last 24h</code>"
        "</p>",
        unsafe_allow_html=True,
    )


def render_hero() -> None:
    with stylable_container(
        key="unesco-hero",
        css_styles="""
background: linear-gradient(135deg, rgba(255,255,255,0.84), rgba(241,248,252,0.76));
border: 1px solid rgba(19,36,52,0.10);
border-radius: 28px;
padding: 48px 44px 44px;
box-shadow: 0 14px 40px rgba(27,21,14,0.06);
margin-bottom: 40px;
""",
    ):
        st.markdown("<div class='unesco-kicker'>UNESCO-opening</div>", unsafe_allow_html=True)
        st.title("Art for the Cryosphere")
        st.markdown(
            "<p class='unesco-accent' style='font-size:1.7rem;line-height:1.08;margin-top:-0.35rem;'>A collective experiment at UNESCO</p>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<p class='unesco-body'>19 March 2026 · 16:00–17:30 (CET) · Room XI, UNESCO Headquarters</p>",
            unsafe_allow_html=True,
        )


def render_opening(blocks: Dict[str, List[str]]) -> None:
    with stylable_container(
        key="unesco-opening-text",
        css_styles="""
background: rgba(255,255,255,0.62);
border: 1px solid rgba(19,36,52,0.08);
border-radius: 22px;
padding: 34px;
margin-bottom: 40px;
""",
    ):
        st.caption("Opening")
        _render_prose(blocks["opening"])
        if blocks["panel"]:
            st.markdown("<p class='unesco-note'>The session connected the voices and works of:</p>", unsafe_allow_html=True)
            _render_prose(blocks["panel"])


def render_full_image(url: str) -> None:
    st.image(url, width="stretch")
    st.markdown("<div style='height:2.5rem;'></div>", unsafe_allow_html=True)


def render_core_objective(blocks: Dict[str, List[str]]) -> None:
    with stylable_container(
        key="unesco-core-objective",
        css_styles="""
background: rgba(255,255,255,0.72);
border: 1px solid rgba(19,36,52,0.08);
border-radius: 20px;
padding: 34px;
margin-bottom: 40px;
""",
    ):
        st.caption("From observation to coordination")
        if blocks["core_objective"]:
            _render_prose(blocks["core_objective"][:-1])
            st.markdown(
                f"<p class='unesco-accent' style='font-size:1.5rem;line-height:1.14;margin:0;'>{blocks['core_objective'][-1]}</p>",
                unsafe_allow_html=True,
            )


def render_sound_prompt() -> None:
    left, right = st.columns([1.1, 0.9], vertical_alignment="top")
    with left:
        with stylable_container(
            key="unesco-sound-text",
            css_styles="""
background: rgba(255,255,255,0.74);
border: 1px solid rgba(19,36,52,0.08);
border-radius: 20px;
padding: 34px;
""",
        ):
            st.caption("Listening")
            st.subheader(SOUND_BLOCK["title"])
            st.markdown(
                f"<p class='unesco-accent' style='font-size:1.35rem;line-height:1.14;margin-top:-0.15rem;'>{SOUND_BLOCK['subtitle']}</p>",
                unsafe_allow_html=True,
            )
            st.markdown(f"<p class='unesco-body'>{SOUND_BLOCK['quote']}</p>", unsafe_allow_html=True)
            st.markdown(f"<p class='unesco-body'>{SOUND_BLOCK['prompt']}</p>", unsafe_allow_html=True)
    with right:
        with stylable_container(
            key="unesco-sound-embed",
            css_styles="""
background: rgba(255,255,255,0.58);
border: 1px solid rgba(19,36,52,0.08);
border-radius: 20px;
padding: 24px 24px 18px;
""",
        ):
            st.caption("Sound")
            components.html(SOUNDCLOUD_EMBED, height=140)
    st.markdown("<div style='height:2.5rem;'></div>", unsafe_allow_html=True)


def render_method(blocks: Dict[str, List[str]], metrics: Dict[str, Any]) -> None:
    with stylable_container(
        key="unesco-method",
        css_styles="""
background: rgba(255,255,255,0.72);
border: 1px solid rgba(19,36,52,0.08);
border-radius: 20px;
padding: 34px;
margin-bottom: 40px;
""",
    ):
        st.caption("Method and participation")
        _render_prose(blocks["method"])
        _render_data_tokens(metrics)


def _render_emotion_chart(title: str, counts: Dict[str, int]) -> None:
    if not counts:
        st.caption(f"{title}: no data yet.")
        return
    labels = sorted(
        counts.keys(),
        key=lambda item: (
            EMOTION_CLUSTER_ORDER.index(_emotion_cluster(item)) if _emotion_cluster(item) in EMOTION_CLUSTER_ORDER else 999,
            -int(counts.get(item, 0)),
            str(item).lower(),
        ),
    )
    rows: List[Dict[str, Any]] = []
    max_count = 0
    for label in labels:
        cluster = _emotion_cluster(label)
        count = int(counts.get(label, 0))
        max_count = max(max_count, count)
        for i in range(1, count + 1):
            rows.append({"emotion": label, "cluster": cluster, "x": i, "count": count})
    dots_df = pd.DataFrame(rows)
    labels_df = pd.DataFrame([
        {"emotion": label, "count": int(counts.get(label, 0)), "x": max_count + 0.45}
        for label in labels
    ])
    height = max(260, 34 * len(labels))
    base = alt.Chart(dots_df).encode(
        y=alt.Y("emotion:N", sort=labels, title=None, axis=alt.Axis(labelOverlap=False)),
        x=alt.X("x:Q", title=None, axis=alt.Axis(labels=False, ticks=False, domain=False, grid=False), scale=alt.Scale(domain=[0, max_count + 1])),
        color=alt.Color(
            "cluster:N",
            scale=alt.Scale(domain=list(EMOTION_CLUSTER_COLOURS.keys()), range=list(EMOTION_CLUSTER_COLOURS.values())),
            legend=alt.Legend(title="Emotion family"),
        ),
        tooltip=[alt.Tooltip("emotion:N", title="Emotion"), alt.Tooltip("cluster:N", title="Family"), alt.Tooltip("count:Q", title="Count", format=".0f")],
    )
    dots = base.mark_circle(size=220, opacity=0.8)
    numbers = alt.Chart(labels_df).mark_text(align="left", baseline="middle", dx=4, color="#444444").encode(
        y=alt.Y("emotion:N", sort=labels, title=None, axis=alt.Axis(labelOverlap=False)),
        x=alt.X("x:Q", scale=alt.Scale(domain=[0, max_count + 1])),
        text=alt.Text("count:Q", format=".0f"),
    )
    st.altair_chart((dots + numbers).properties(title=title, height=height), width="stretch")


def _render_signal_line(counts: Dict[str, int]) -> None:
    buckets = _normalise_org_signal_counts(counts)

    def circles(colour: str, count: int) -> str:
        return "".join(
            f"<span style='display:inline-block;width:24px;height:24px;border-radius:50%;background:{colour};margin:0 6px 8px 0;'></span>"
            for _ in range(max(0, count))
        )

    st.markdown(
        "<div class='unesco-centre' style='margin:0.5rem 0 0.75rem 0;'>"
        f"<div>{circles('#2e7d32', buckets['yes'])}{circles('#fbc02d', buckets['maybe'])}{circles('#c62828', buckets['no'])}</div>"
        f"<p class='unesco-body unesco-token' style='max-width:none;'><code>yes: {buckets['yes']}</code> <code>maybe: {buckets['maybe']}</code> <code>no: {buckets['no']}</code></p>"
        "</div>",
        unsafe_allow_html=True,
    )


def render_text_and_data(title: str, paragraphs: List[str], render_data, *, data_left: bool = False) -> None:
    left, right = st.columns([1.25, 1], vertical_alignment="top")
    text_col, data_col = (right, left) if data_left else (left, right)
    with text_col:
        with stylable_container(
            key=f"{title.lower().replace(' ', '-')}-text",
            css_styles="""
background: rgba(255,255,255,0.72);
border: 1px solid rgba(19,36,52,0.08);
border-radius: 20px;
padding: 32px;
height: 100%;
""",
        ):
            st.caption(title)
            _render_prose(paragraphs)
    with data_col:
        with stylable_container(
            key=f"{title.lower().replace(' ', '-')}-data",
            css_styles="""
background: rgba(255,255,255,0.58);
border: 1px solid rgba(19,36,52,0.08);
border-radius: 20px;
padding: 28px;
height: 100%;
""",
        ):
            render_data()
    st.markdown("<div style='height:2.5rem;'></div>", unsafe_allow_html=True)


def render_interpretation(paragraphs: List[str]) -> None:
    with stylable_container(
        key="unesco-interpretation",
        css_styles="""
background: rgba(255,255,255,0.7);
border-left: 4px solid rgba(44,111,163,0.45);
border-radius: 18px;
padding: 30px 32px;
margin-bottom: 40px;
""",
    ):
        st.caption("First signal")
        _render_prose(paragraphs)


def render_decision(blocks: Dict[str, List[str]], counts: Dict[str, int]) -> None:
    with stylable_container(
        key="unesco-decision",
        css_styles="""
background: rgba(255,255,255,0.8);
border: 1px solid rgba(19,36,52,0.10);
border-radius: 24px;
padding: 38px 34px;
margin-bottom: 40px;
""",
    ):
        st.markdown("<div class='unesco-centre'>", unsafe_allow_html=True)
        st.caption("Decision pivot")
        st.subheader("Should we continue?")
        _render_signal_line(counts)
        _render_prose(blocks["decision"])
        st.markdown("</div>", unsafe_allow_html=True)


def render_meta(blocks: Dict[str, List[str]]) -> None:
    with stylable_container(
        key="unesco-meta",
        css_styles="""
background: rgba(255,255,255,0.72);
border: 1px solid rgba(19,36,52,0.08);
border-radius: 20px;
padding: 34px;
margin-bottom: 40px;
""",
    ):
        st.caption("Meta interpretation")
        _render_prose(blocks["meta"])


def render_gallery() -> None:
    st.caption("Images and traces")
    cols = st.columns(3)
    for idx, url in enumerate(IMAGE_URLS[1:]):
        with cols[idx % 3]:
            st.image(url, width="stretch")
    st.markdown("<div style='height:2.5rem;'></div>", unsafe_allow_html=True)


def render_closing(blocks: Dict[str, List[str]]) -> None:
    with stylable_container(
        key="unesco-closing",
        css_styles="""
background: rgba(255,255,255,0.7);
border: 1px solid rgba(19,36,52,0.08);
border-radius: 20px;
padding: 34px;
margin-bottom: 32px;
""",
    ):
        st.caption("Closing reflection")
        _render_prose(blocks["closing"], accent_first=True)


def render_action_block() -> None:
    with stylable_container(
        key="unesco-actions",
        css_styles="""
background: rgba(255,255,255,0.78);
border: 1px solid rgba(19,36,52,0.10);
border-radius: 24px;
padding: 28px;
margin-bottom: 24px;
""",
    ):
        st.markdown("<div class='unesco-centre'>", unsafe_allow_html=True)
        st.caption("Continue")
        st.subheader("This is an entry, not a conclusion.")
        st.markdown(
            "<p class='unesco-body' style='max-width:48ch;margin:0 auto 1.5rem auto;'>Bring this format elsewhere, return to the platform, or contact the organisers to continue the experiment.</p>",
            unsafe_allow_html=True,
        )
        c1, c2, c3 = st.columns(3)
        with c1:
            st.button("Start a new session", type="secondary", width="stretch", disabled=True)
        with c2:
            st.page_link("pages/01_Login.py", label="Join the platform", icon=":material/login:")
        with c3:
            st.button("Contact organisers", type="tertiary", width="stretch", disabled=True)
        st.markdown("</div>", unsafe_allow_html=True)


def main() -> None:
    set_page()
    apply_theme()
    _apply_page_css()

    blocks = _load_text_blocks()
    payload = get_overview_payload(GLOBAL_SESSION_SLUG)
    question_map = {str(q.get("item_id") or ""): q for q in payload.get("questions", []) or []}
    metrics = {
        "responses": int(payload.get("response_count", 0)),
        "participants": int(payload.get("participant_count", 0)),
        "active_24h": int(count_active_users(24 * 60, session_id="")),
    }

    render_hero()
    render_opening(blocks)
    render_full_image(IMAGE_URLS[0])
    render_core_objective(blocks)
    render_sound_prompt()
    render_method(blocks, metrics)
    render_text_and_data(
        "Arrival emotions",
        blocks["arrival"],
        lambda: _render_emotion_chart("Arrival emotions", question_map.get("ARRIVAL_EMOTION", {}).get("counts", {})),
    )
    render_interpretation(blocks["arrival_interpretation"])
    render_full_image(IMAGE_URLS[1])
    render_text_and_data(
        "Environmental change",
        blocks["environment"],
        lambda: _render_emotion_chart(
            "Emotion toward environmental change",
            question_map.get("ENVIRONMENT_CHANGE_EMOTION", {}).get("counts", {}),
        ),
        data_left=True,
    )
    render_text_and_data(
        "Societal projection",
        blocks["societal"],
        lambda: _render_emotion_chart(
            "Emotion toward societal change",
            question_map.get("SOCIETAL_CHANGE_EMOTION", {}).get("counts", {}),
        ),
    )
    render_decision(blocks, question_map.get("ORGANISATION_SIGNAL", {}).get("counts", {}))
    render_full_image(IMAGE_URLS[2])
    render_meta(blocks)
    render_gallery()
    render_closing(blocks)
    render_action_block()

    log_event(
        module="iceicebaby.unesco_opening",
        event_type="page_view",
        page="UNESCO-opening",
        session_id=payload.get("session_id") or "",
        value_label="unesco_opening_loaded",
        metadata={"session_slug": payload.get("session_slug", GLOBAL_SESSION_SLUG)},
    )


if __name__ == "__main__":
    main()
