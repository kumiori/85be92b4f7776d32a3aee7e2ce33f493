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
from ui import apply_theme, set_page

COPY_PATH = Path("data/unesco-opening.txt")
IMAGE_URLS = [
    "https://i.postimg.cc/c1zZQRmx/Delhom-JF-031825.jpg",
    "https://i.postimg.cc/ryHcS1Jq/Delhom-JF-032452.jpg",
    "https://i.postimg.cc/3rq7gXBh/Delhom-JF-032659.jpg",
    "https://i.postimg.cc/SQPqW6rq/Delhom-JF-033442.jpg",
]
GLOBAL_SESSION_SLUG = "global-session"
SOUNDCLOUD_EMBED = """
<iframe width="100%" height="120" scrolling="no" frameborder="no" allow="autoplay"
src="https://w.soundcloud.com/player/?url=https%3A//api.soundcloud.com/tracks/soundcloud%253Atracks%253A2286855149&color=%23ff5500&auto_play=false">
</iframe>
""".strip()

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


def _inject_css() -> None:
    st.markdown(
        """
<style>
.unesco-open-shell {
  display: grid;
  gap: 4.75rem;
}
.unesco-open-hero {
  padding: 3.2rem 2.1rem;
  border-radius: 22px;
  background:
    radial-gradient(circle at top right, rgba(120, 180, 220, 0.18), transparent 28%),
    linear-gradient(135deg, #e8f1f8 0%, #f8fbfd 52%, #eef5ef 100%);
  border: 1px solid rgba(14, 30, 60, 0.08);
}
.unesco-open-title {
  margin: 0;
  font-size: 3rem;
  line-height: 0.98;
  font-weight: 820;
  letter-spacing: -0.03em;
}
.unesco-open-subtitle {
  margin: 0.75rem 0 0 0;
  font-size: 1.2rem;
  line-height: 1.45;
  font-weight: 530;
  max-width: 50rem;
}
.unesco-open-meta {
  margin-top: 1.2rem;
  font-size: 0.95rem;
  line-height: 1.55;
  max-width: 48rem;
}
.unesco-open-section {
  margin-top: 1.2rem;
}
.unesco-open-heading {
  margin: 0 0 0.8rem 0;
  font-size: 1.55rem;
  line-height: 1.15;
  font-weight: 760;
}
.unesco-open-body {
  font-size: 1.08rem;
  line-height: 1.72;
  font-weight: 430;
  max-width: 58rem;
}
.unesco-open-highlight {
  font-size: 1.32rem;
  line-height: 1.45;
  font-weight: 620;
  max-width: 52rem;
}
.unesco-open-interpret {
  padding: 1.1rem 1.25rem;
  border-left: 3px solid rgba(46, 125, 50, 0.45);
  border-radius: 10px;
  background: rgba(245, 250, 246, 0.88);
}
.unesco-open-centred {
  text-align: centre;
}
.unesco-open-chip {
  display: inline-block;
  margin-right: 0.5rem;
  margin-bottom: 0.45rem;
  padding: 0.22rem 0.58rem;
  border-radius: 999px;
  border: 1px solid rgba(60, 80, 120, 0.18);
  background: rgba(245, 248, 255, 1);
  font-size: 0.92rem;
}
.unesco-open-grid-note {
  display: grid;
  gap: 1rem;
}
.unesco-open-gallery {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1rem;
}
.unesco-open-cta {
  padding: 1.2rem;
  border-radius: 14px;
  border: 1px solid rgba(14, 30, 60, 0.08);
  background: #f7fafc;
  text-align: centre;
}
.block-container {
  max-width: 1180px !important;
}
@media (max-width: 900px) {
  .unesco-open-title {
    font-size: 2.35rem;
  }
  .unesco-open-gallery {
    grid-template-columns: 1fr;
  }
}
</style>
""",
        unsafe_allow_html=True,
    )


def _load_copy() -> Dict[str, str]:
    if not COPY_PATH.exists():
        return {}
    raw = COPY_PATH.read_text(encoding="utf-8").strip()
    blocks = [part.strip() for part in raw.split("⸻") if part.strip()]
    mapping: Dict[str, str] = {}
    for block in blocks:
        lines = [line.rstrip() for line in block.splitlines()]
        key = ""
        body_lines: List[str] = []
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if idx == 0 and stripped:
                key = stripped
                continue
            body_lines.append(line)
        if key:
            mapping[key] = "\n".join(body_lines).strip()
    return mapping


def _paragraphs(text: str) -> List[str]:
    if not text:
        return []
    return [para.strip() for para in text.split("\n\n") if para.strip()]


def _data_chip(label: str, value: Any) -> str:
    return f"<span class='unesco-open-chip'>{label}: <code>{value}</code></span>"


def _counts_df(counts: Dict[str, int]) -> pd.DataFrame:
    rows = [{"label": str(k), "value": int(v)} for k, v in (counts or {}).items()]
    rows.sort(key=lambda row: row["value"], reverse=True)
    return pd.DataFrame(rows)


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
    if any(
        marker in token
        for marker in [
            "fear",
            "anx",
            "anger",
            "sad",
            "concern",
            "urg",
            "conflict",
            "overwhelm",
            "grief",
            "powerless",
            "scept",
            "skept",
            "uncertain",
        ]
    ):
        return "Tension and conflict"
    return "Other"


def _render_emotion_field(title: str, counts: Dict[str, int]) -> None:
    if not counts:
        st.caption(f"{title}: no data yet.")
        return

    labels = sorted(
        counts.keys(),
        key=lambda item: (
            EMOTION_CLUSTER_ORDER.index(_emotion_cluster(item))
            if _emotion_cluster(item) in EMOTION_CLUSTER_ORDER
            else 999,
            -int(counts.get(item, 0)),
            str(item).lower(),
        ),
    )
    dot_rows: List[Dict[str, Any]] = []
    max_count = 0
    for label in labels:
        cluster = _emotion_cluster(label)
        count = int(counts.get(label, 0))
        max_count = max(max_count, count)
        for i in range(1, count + 1):
            dot_rows.append(
                {"emotion": label, "cluster": cluster, "x": i, "count": count}
            )

    dots_df = pd.DataFrame(dot_rows)
    labels_df = pd.DataFrame(
        [
            {
                "emotion": label,
                "count": int(counts.get(label, 0)),
                "x": max_count + 0.45,
            }
            for label in labels
        ]
    )
    height = max(280, 32 * len(labels))

    base = alt.Chart(dots_df).encode(
        y=alt.Y(
            "emotion:N", sort=labels, title=None, axis=alt.Axis(labelOverlap=False)
        ),
        x=alt.X(
            "x:Q",
            title=None,
            axis=alt.Axis(labels=False, ticks=False, domain=False, grid=False),
            scale=alt.Scale(domain=[0, max_count + 1]),
        ),
        color=alt.Color(
            "cluster:N",
            scale=alt.Scale(
                domain=list(EMOTION_CLUSTER_COLOURS.keys()),
                range=list(EMOTION_CLUSTER_COLOURS.values()),
            ),
            legend=alt.Legend(title="Emotion family"),
        ),
        tooltip=[
            alt.Tooltip("emotion:N", title="Emotion"),
            alt.Tooltip("cluster:N", title="Family"),
            alt.Tooltip("count:Q", title="Count", format=".0f"),
        ],
    )

    dots = base.mark_circle(size=250, opacity=0.78)
    counts_layer = (
        alt.Chart(labels_df)
        .mark_text(align="left", baseline="middle", dx=4, color="#444444")
        .encode(
            y=alt.Y(
                "emotion:N", sort=labels, title=None, axis=alt.Axis(labelOverlap=False)
            ),
            x=alt.X("x:Q", scale=alt.Scale(domain=[0, max_count + 1])),
            text=alt.Text("count:Q", format=".0f"),
        )
    )
    chart = (dots + counts_layer).properties(title=title, height=height)
    st.altair_chart(chart, width="stretch")


def _render_signal_glyphs(counts: Dict[str, int]) -> None:
    yes_n = int(counts.get("yes", 0))
    maybe_n = int(counts.get("maybe", 0))
    no_n = int(counts.get("no", 0))

    def _block(colour: str, n: int) -> str:
        if n <= 0:
            return ""
        circles = "".join(
            f"<span style='display:inline-block;width:36px;height:36px;border-radius:50%;background:{colour};margin:4px;'></span>"
            for _ in range(n)
        )
        return f"<span style='display:inline-flex;flex-wrap:wrap;justify-content:center;max-width:100%;'>{circles}</span>"

    st.markdown(
        (
            "<div style='display:flex;justify-content:center;flex-wrap:wrap;align-items:center;gap:10px'>"
            f"{_block('#2e7d32', yes_n)}"
            f"{_block('#fbc02d', maybe_n)}"
            f"{_block('#c62828', no_n)}"
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def _render_choice_chart(title: str, counts: Dict[str, int]) -> None:
    if not counts:
        st.caption(f"{title}: no data yet.")
        return
    df = _counts_df(counts)
    chart = (
        alt.Chart(df)
        .mark_bar()
        .encode(
            x=alt.X("value:Q", title="Count", axis=alt.Axis(format="d")),
            y=alt.Y("label:N", sort="-x", title=None),
            tooltip=["label:N", alt.Tooltip("value:Q", format=".0f")],
        )
        .properties(title=title, height=max(220, 34 * len(df)))
    )
    st.altair_chart(chart, width="stretch")


def _full_image(url: str) -> None:
    st.image(url, width="stretch")


def _render_paragraph_block(
    title: str, paragraphs: List[str], *, narrow: bool = False
) -> None:
    st.markdown("<section class='unesco-open-section'>", unsafe_allow_html=True)
    st.markdown(
        f"<div class='unesco-open-heading'>{title}</div>", unsafe_allow_html=True
    )
    body_cls = "unesco-open-body"
    if narrow:
        st.markdown(
            "<div style='max-width:48rem;margin:0 auto;'>", unsafe_allow_html=True
        )
    for para in paragraphs:
        st.markdown(f"<div class='{body_cls}'>{para}</div>", unsafe_allow_html=True)
        st.markdown("<div style='height:0.95rem'></div>", unsafe_allow_html=True)
    if narrow:
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</section>", unsafe_allow_html=True)


def _render_two_column_text_data(
    *,
    title: str,
    paragraphs: List[str],
    render_data,
    data_left: bool = False,
) -> None:
    st.markdown("<section class='unesco-open-section'>", unsafe_allow_html=True)
    left, right = st.columns([1.55, 1], vertical_alignment="top")
    if data_left:
        left, right = right, left
    with left:
        if not data_left:
            st.markdown(
                f"<div class='unesco-open-heading'>{title}</div>",
                unsafe_allow_html=True,
            )
            for para in paragraphs:
                st.markdown(
                    f"<div class='unesco-open-body'>{para}</div>",
                    unsafe_allow_html=True,
                )
                st.markdown(
                    "<div style='height:0.95rem'></div>", unsafe_allow_html=True
                )
        else:
            render_data()
    with right:
        if not data_left:
            render_data()
        else:
            st.markdown(
                f"<div class='unesco-open-heading'>{title}</div>",
                unsafe_allow_html=True,
            )
            for para in paragraphs:
                st.markdown(
                    f"<div class='unesco-open-body'>{para}</div>",
                    unsafe_allow_html=True,
                )
                st.markdown(
                    "<div style='height:0.95rem'></div>", unsafe_allow_html=True
                )
    st.markdown("</section>", unsafe_allow_html=True)


def main() -> None:
    set_page()
    apply_theme()
    _inject_css()

    copy_map = _load_copy()
    payload = get_overview_payload(GLOBAL_SESSION_SLUG)
    question_map = {
        str(q.get("item_id") or ""): q for q in payload.get("questions", []) or []
    }
    response_count = int(payload.get("response_count", 0))
    participant_count = int(payload.get("participant_count", 0))
    active_24h = int(count_active_users(24 * 60, session_id=""))

    opening = _paragraphs(copy_map.get("1. OPENING — reframed incipit", ""))
    panel = _paragraphs(copy_map.get("PANEL (integrated, not dominant)", ""))
    core_objective = _paragraphs(copy_map.get("2. CORE OBJECTIVE — call to action", ""))
    transition = _paragraphs(copy_map.get("3. TRANSITION — introducing the method", ""))
    arrival = _paragraphs(copy_map.get("4. ARRIVAL — initial conditions", ""))
    arrival_interpret = _paragraphs(
        copy_map.get("5. INTERPRETATION — first signal", "")
    )
    environmental = _paragraphs(copy_map.get("6. DEEPENING — environmental change", ""))
    societal = _paragraphs(copy_map.get("7. SOCIETAL PROJECTION — shift in tone", ""))
    decision = _paragraphs(copy_map.get("8. DECISION PIVOT — collective signal", ""))
    meta = _paragraphs(copy_map.get("9. META — interpretation of signals", ""))
    closing = _paragraphs(copy_map.get("10. CLOSING TRANSITION", ""))

    st.markdown("<div class='unesco-open-shell'>", unsafe_allow_html=True)

    st.markdown(
        """
<section class="unesco-open-hero">
  <h1 class="unesco-open-title">Art for the Cryosphere</h1>
  <p class="unesco-open-subtitle">A collective experiment at UNESCO</p>
  <div class="unesco-open-meta">
    19 March 2026 · 16:00–17:30 (CET) · Room XI, UNESCO Headquarters
  </div>
</section>
""",
        unsafe_allow_html=True,
    )

    _render_paragraph_block(
        "Opening",
        opening + panel,
    )

    _full_image(IMAGE_URLS[0])

    st.markdown("<section class='unesco-open-section'>", unsafe_allow_html=True)
    st.markdown(
        "<div class='unesco-open-heading'>From observation to coordination</div>",
        unsafe_allow_html=True,
    )
    for para in core_objective[:-1]:
        st.markdown(
            f"<div class='unesco-open-body'>{para}</div>", unsafe_allow_html=True
        )
        st.markdown("<div style='height:0.95rem'></div>", unsafe_allow_html=True)
    if core_objective:
        st.markdown(
            f"<div class='unesco-open-highlight'>{core_objective[-1]}</div>",
            unsafe_allow_html=True,
        )
    st.markdown("</section>", unsafe_allow_html=True)

    st.markdown("<section class='unesco-open-section'>", unsafe_allow_html=True)
    st.markdown(
        "<div class='unesco-open-heading'>Have you ever heard the voice of a glacier?</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='unesco-open-highlight'>"
        "Have you ever heard how it cracks at night and how it collapses in the daylight?"
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='unesco-open-body'>"
        "In the words of Liz Macedo, Guardian of the Ishinca Hut in Peru, "
        "“It is as if the mountain is screaming. The roar of the falling ice makes me think "
        "Tocllaraju is crying for help.”"
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='unesco-open-body'>"
        "We ask you a question that may or may not guide our and your next steps, a question "
        "that our daughters, sons, and grandchildren will surely ask us: "
        "<strong>What did we do, when we knew?</strong>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)
    components.html(SOUNDCLOUD_EMBED, height=140)
    st.markdown("</section>", unsafe_allow_html=True)

    st.markdown("<section class='unesco-open-section'>", unsafe_allow_html=True)
    st.markdown(
        "<div class='unesco-open-heading'>Method and participation</div>",
        unsafe_allow_html=True,
    )
    for para in transition:
        st.markdown(
            f"<div class='unesco-open-body'>{para}</div>", unsafe_allow_html=True
        )
        st.markdown("<div style='height:0.95rem'></div>", unsafe_allow_html=True)
    st.markdown(
        _data_chip("Responses", response_count)
        + _data_chip("Participants", participant_count)
        + _data_chip("Active in last 24h", active_24h),
        unsafe_allow_html=True,
    )
    st.markdown("</section>", unsafe_allow_html=True)

    def _arrival_data() -> None:
        _render_emotion_field(
            "Arrival emotions",
            question_map.get("ARRIVAL_EMOTION", {}).get("counts", {}),
        )

    _render_two_column_text_data(
        title="Arrival emotions",
        paragraphs=arrival,
        render_data=_arrival_data,
        data_left=False,
    )

    st.markdown("<section class='unesco-open-section'>", unsafe_allow_html=True)
    st.markdown(
        "<div class='unesco-open-interpret'>",
        unsafe_allow_html=True,
    )
    for para in arrival_interpret:
        st.markdown(
            f"<div class='unesco-open-body'>{para}</div>", unsafe_allow_html=True
        )
    st.markdown("</div></section>", unsafe_allow_html=True)

    _full_image(IMAGE_URLS[1])

    def _environment_data() -> None:
        _render_emotion_field(
            "Emotion toward environmental change",
            question_map.get("ENVIRONMENT_CHANGE_EMOTION", {}).get("counts", {}),
        )

    _render_two_column_text_data(
        title="Deepening",
        paragraphs=environmental,
        render_data=_environment_data,
        data_left=True,
    )

    def _societal_data() -> None:
        _render_emotion_field(
            "Emotion toward societal change",
            question_map.get("SOCIETAL_CHANGE_EMOTION", {}).get("counts", {}),
        )

    _render_two_column_text_data(
        title="Societal projection",
        paragraphs=societal,
        render_data=_societal_data,
        data_left=False,
    )

    st.markdown("<section class='unesco-open-section'>", unsafe_allow_html=True)
    st.markdown(
        "<div class='unesco-open-heading'>Decision pivot</div>", unsafe_allow_html=True
    )
    st.markdown(
        "<div class='unesco-open-body'>Should we continue?</div>",
        unsafe_allow_html=True,
    )
    signal_counts = question_map.get("ORGANISATION_SIGNAL", {}).get("counts", {})
    _render_signal_glyphs(signal_counts)
    st.markdown(
        _data_chip("yes", int(signal_counts.get("yes", 0)))
        + _data_chip("maybe", int(signal_counts.get("maybe", 0)))
        + _data_chip("no", int(signal_counts.get("no", 0))),
        unsafe_allow_html=True,
    )
    for para in decision:
        st.markdown(
            f"<div class='unesco-open-body'>{para}</div>",
            unsafe_allow_html=True,
        )
    st.markdown("</section>", unsafe_allow_html=True)

    _full_image(IMAGE_URLS[2])

    _render_paragraph_block("Signals as a field", meta, narrow=False)

    st.markdown("<section class='unesco-open-section'>", unsafe_allow_html=True)
    st.markdown(
        "<div class='unesco-open-heading'>Images and traces</div>",
        unsafe_allow_html=True,
    )
    st.markdown("<div class='unesco-open-gallery'>", unsafe_allow_html=True)
    # for url in IMAGE_URLS[3:]:
    st.image(IMAGE_URLS[3], width="stretch")
    st.markdown("</div></section>", unsafe_allow_html=True)

    _render_paragraph_block("Closing reflection", closing, narrow=True)

    st.markdown("<section class='unesco-open-section'>", unsafe_allow_html=True)
    st.markdown("<div class='unesco-open-cta'>", unsafe_allow_html=True)
    st.markdown(
        "<div class='unesco-open-heading'>Continue</div>", unsafe_allow_html=True
    )
    st.markdown(
        "<div class='unesco-open-body'>"
        "This page is an entry into something that has already started. "
        "Carry these signals forward, return to the platform, and reopen the field elsewhere."
        "</div>",
        unsafe_allow_html=True,
    )
    c1, c2, c3 = st.columns(3)
    c1.button("Start a new session", disabled=True, width="stretch")
    c2.page_link(
        "pages/01_Login.py", label="Join the platform", icon=":material/login:"
    )
    c3.button("Contact organisers", disabled=True, width="stretch")
    st.markdown("</div></section>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

    log_event(
        module="iceicebaby.sessions",
        event_type="page_view",
        page="UNESCO-opening",
        player_id=str(st.session_state.get("player_page_id", "")),
        session_id=str(st.session_state.get("session_id", "")),
        device_id=str(st.session_state.get("anon_token", "")),
        status="ok",
        metadata={
            "responses": response_count,
            "participants": participant_count,
        },
    )


if __name__ == "__main__":
    main()
