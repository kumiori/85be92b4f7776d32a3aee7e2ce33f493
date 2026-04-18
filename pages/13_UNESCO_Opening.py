from __future__ import annotations

import datetime as dt
from statistics import pstdev
from typing import Any, Dict, List

import altair as alt
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from infra.app_context import get_notion_repo
from infra.event_logger import log_event
from models.catalog import QUESTION_BY_ID
from services.aggregator import get_overview_payload
from services.presence import count_active_users
from ui import apply_theme, set_page, stylable_container

GLOBAL_SESSION_SLUG = "global-session"
IMAGE_URLS = [
    "https://i.postimg.cc/c1zZQRmx/Delhom-JF-031825.jpg",
    "https://i.postimg.cc/ryHcS1Jq/Delhom-JF-032452.jpg",
    "https://i.postimg.cc/3rq7gXBh/Delhom-JF-032659.jpg",
    "https://i.postimg.cc/SQPqW6rq/Delhom-JF-033442.jpg",
]
GALLERY_URLS = [
    "https://i.postimg.cc/Pr2BWrwS/APC-6808.jpg",
    "https://i.postimg.cc/DyBtryXB/APC-6810.jpg",
    "https://i.postimg.cc/WbXQGbk9/APC-6812.jpg",
    "https://i.postimg.cc/nc064cDR/APC-6814.jpg",
    "https://i.postimg.cc/4NBr6N9j/APC-6815.jpg",
    "https://i.postimg.cc/vH3prHVJ/APC-6816.jpg",
    "https://i.postimg.cc/c4XVR43q/APC-6818.jpg",
    "https://i.postimg.cc/GhqZFhDw/APC-6819.jpg",
]
SOUNDCLOUD_EMBED = """
<iframe width="100%" height="120" scrolling="no" frameborder="no" allow="autoplay"
src="https://w.soundcloud.com/player/?url=https%3A//api.soundcloud.com/tracks/soundcloud%253Atracks%253A2286855149&color=%23ff5500&auto_play=false">
</iframe>
""".strip()
MEDIA_CAPTIONS = {
    "hero_names": (
        "Contributors and affiliations: Bruno Doucey (poet, writer, editor), "
        "Jean-François Delhom (landscape photographer), Leopold Bouzard "
        "(behavioural sciences and ecological transitions), Véronique Dansereau "
        "(researcher in geophysical media), Andrés León Baldelli "
        "(researcher in fracture and irreversible systems)."
    ),
    "sound": "Field recording and sonic trace placed here as a threshold for listening.",
    "image_1_title": "Immersion",
    "image_1_kicker": "Image",
    "image_1": "Jean-François Delhom, ice cave photograph, shown here as an opening immersion.",
    "image_2_title": "Reset attention",
    "image_2_kicker": "Image",
    "image_2": "A second photograph to reset attention before the emotional field deepens.",
    "image_3_title": "Pause",
    "image_3_kicker": "Image",
    "image_3": "A pause after the decision pivot: image as breath, not decoration. Location to be checked with Jean-François.",
    "gallery": "Additional traces from the UNESCO moment.",
    "svalbard": (
        "Selected Svalbard points: Longyearbreen 78.2232° N, 15.6267° E · "
        "Larsbreen 78.1908° N, 15.6049° E · Esmarkbreen 78.0553° N, 13.6231° E."
    ),
}

SOUND_BLOCK = {
    "title": "Have you ever heard the voice of a glacier?",
    "subtitle": "Have you ever heard how it cracks at night and how it collapses in the daylight?",
    "quote": (
        "“It is as if the mountain is screaming. The roar of the falling ice makes me think "
        "Tocllaraju is crying for help.”"
    ),
    "credit": "Liz Macedo, Guardian of the Ishinca Hut in Peru",
    "prompt": "What do we do, now that we know?",
}

OPENING_LEAD = (
    "We bring together a constellation of practices engaging with ice, glaciers, and "
    "the evolving states of the cryosphere."
)

OPENING_PARAGRAPHS = [
    "Across photography, poetry, sound, and scientific inquiry, our works trace shifting spaces, sometimes irreversibly, under the pressure of climate disruption.",
    "Rather than describing these changes from a distance, this is an invitation to enter them: through images, language, listening, and collective perception.",
    "What emerges is a field of signals that allow multiple narratives.",
]

CONTRIBUTOR_LINE = (
    "Bruno Doucey<sup>1</sup>, poet, writer, and editor; Jean-François Delhom<sup>2</sup>, "
    "landscape photographer; Ignacio Palomo<sup>3</sup>, researcher in environmental sciences; Leopold Bouzard<sup>4</sup>, researcher in behavioural sciences; "
    "Véronique Dansereau<sup>5</sup>, researcher and lecturer on mechanical interactions "
    "in complex geophysical media; and Andrés León Baldelli<sup>6</sup>, researcher in "
    "fracture mechanics and irreversible evolutionary systems."
)
AFFILIATION_LINE = (
    "<sup>1</sup>: https://editions-brunodoucey.com • "
    "<sup>2</sup>: https://photo-philo-delhom.com • "
    "<sup>3</sup>: Institut de Recherche pour le Développement, Université Grenoble-Alpes, CNRS, Grenoble • "
    "<sup>4</sup>: Fabrique d'Innovation pour les Transitions, General Secretariat of the Ministry of Ecological Transition • "
    "<sup>5</sup>: Institut des Sciences de la Terre and Institut des Géosciences de l’Environnement, Université Grenoble-Alpes, Grenoble • "
    "<sup>6</sup>: Institut ∂'Alembert, CNRS, Sorbonne Université, Paris • "
)

CORE_OBJECTIVE_PARAGRAPHS = [
    "As Jean-François Delhom noted, “two thirds of the ice caves I documented in this photographic exploration no longer exist”. Entire glaciers have already disappeared.",
    "The question is no longer whether rapid natural transitions will happen. It is how we frame and understand them, as well as how we act through them.",
    "To do so, we experimented with a simple idea:",
]

CORE_OBJECTIVE_ACCENT = "Can a group make its perceptions visible, in real time, and use them as signals for collective orientation?"

METHOD_PARAGRAPHS = [
    "We combined multiple languages: images, texts, sounds, scientific questions, gesture, experience, and a live participatory interface.",
    "Participants are invited not only to listen, but to respond.",
    "Each response is anonymous and carries an intuition, an emotion, a direction.",
    "What follows is an attempt at reading these signals.",
]

META_PARAGRAPHS = [
    "Signals form a field; they are not isolated points in a dataset.",
    "What appears here is a structured coexistence of positions, emotions, and intentions.",
    "This complexity is what makes coordination possible.",
]

GLACIER_THEME = {
    "bg_top": "#eef5fb",
    "bg_bottom": "#dde9f2",
    "paper": "rgba(255, 255, 255, 0.78)",
    "paper_soft": "rgba(255, 255, 255, 0.58)",
    "ink": "#132434",
    "muted": "#607384",
    "accent": "#2c6fa3",
    "plot_blue": "#6f8ea4",
    "serif": "#6c7888",
    "rule": "rgba(19, 36, 52, 0.12)",
    "chip_bg": "rgba(44, 111, 163, 0.10)",
    "chip_fg": "#20577f",
}

CARD_SOFT_CSS = """
background: rgba(255,255,255,0.58);
border: 1px solid rgba(19,36,52,0.08);
border-radius: 20px;
padding: 28px;
"""

CARD_SECTION_CSS = """
background: rgba(255,255,255,0.72);
border: 1px solid rgba(19,36,52,0.08);
border-radius: 20px;
padding: 34px;
margin-bottom: 40px;
"""

CARD_PAPER_CSS = """
background: rgba(255,255,255,0.92);
border: 1px solid rgba(19,36,52,0.10);
border-radius: 22px;
padding: 30px 32px;
margin: 0 0 24px 0;
box-shadow: 0 12px 26px rgba(19,36,52,0.06);
"""

CARD_INTERPRETATION_CSS = """
background: rgba(255,255,255,0.7);
border-left: 4px solid rgba(44,111,163,0.45);
border-radius: 18px;
padding: 30px 32px;
margin-bottom: 40px;
"""

CARD_DECISION_CSS = """
background: rgba(255,255,255,0.8);
border: 1px solid rgba(19,36,52,0.10);
border-radius: 24px;
padding: 38px 34px;
margin-bottom: 40px;
"""

CARD_ACTION_CSS = """
background: rgba(255,255,255,0.78);
border: 1px solid rgba(19,36,52,0.10);
border-radius: 24px;
padding: 28px;
margin-bottom: 24px;
"""

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
  --unesco-bg-top: {palette["bg_top"]};
  --unesco-bg-bottom: {palette["bg_bottom"]};
  --unesco-paper: {palette["paper"]};
  --unesco-paper-soft: {palette["paper_soft"]};
  --unesco-ink: {palette["ink"]};
  --unesco-muted: {palette["muted"]};
  --unesco-accent: {palette["accent"]};
  --unesco-serif: {palette["serif"]};
  --unesco-rule: {palette["rule"]};
  --unesco-chip-bg: {palette["chip_bg"]};
  --unesco-chip-fg: {palette["chip_fg"]};
  --vr-body-gap: 1.35rem;
  --vr-heading-after: 1.35rem;
  --vr-section-gap: 2.7rem;
  --vr-kicker-after: 0.65rem;
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
  margin-bottom: var(--vr-kicker-after);
}}

[data-testid="stMarkdownContainer"] p.unesco-body {{
  font-size: 1.24rem;
  line-height: 1.62;
  max-width: 62ch;
  letter-spacing: -0.01em;
  margin: 0 0 var(--vr-body-gap) 0;
}}

.unesco-accent {{
  font-family: "Fraunces", Georgia, serif;
  color: var(--unesco-accent);
}}

[data-testid="stMarkdownContainer"] p.unesco-note {{
  font-family: "Fraunces", Georgia, serif;
  font-size: 1.16rem;
  line-height: 1.5;
  color: var(--unesco-muted);
  margin: 0 0 var(--vr-body-gap) 0;
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

[data-testid="stHeadingWithActionElements"] h1 {{
  line-height: 1.04 !important;
  margin-bottom: var(--vr-heading-after) !important;
}}

[data-testid="stHeadingWithActionElements"] h2,
[data-testid="stHeadingWithActionElements"] h3 {{
  line-height: 1.12 !important;
  margin-bottom: var(--vr-heading-after) !important;
}}

[data-testid="stCaptionContainer"] {{
  margin-bottom: var(--vr-kicker-after) !important;
}}
</style>
""",
        unsafe_allow_html=True,
    )


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


def _counts_df(counts: Dict[str, int]) -> pd.DataFrame:
    rows = [{"label": str(k), "value": int(v)} for k, v in (counts or {}).items()]
    rows.sort(key=lambda row: row["value"], reverse=True)
    return pd.DataFrame(rows)


def _normalise_org_signal_counts(counts: Dict[str, int]) -> Dict[str, int]:
    buckets = {"yes": 0, "upon_condition": 0, "no": 0}
    for label, count in (counts or {}).items():
        text = str(label or "").strip().lower()
        if "yes" in text:
            buckets["yes"] += int(count)
        elif (
            "upon condition" in text
            or "maybe" in text
            or "depending on conditions" in text
            or "depending upon conditions" in text
            or "condition" in text
        ):
            buckets["upon_condition"] += int(count)
        elif "no" in text:
            buckets["no"] += int(count)
    return buckets


def _render_prose(paragraphs: List[str], *, accent_first: bool = False) -> None:
    for idx, paragraph in enumerate(paragraphs):
        if idx == 0 and accent_first:
            st.markdown(
                f"<p class='unesco-accent' style='font-size:1.6rem;line-height:1.18;margin:0 0 var(--vr-body-gap) 0;max-width:62ch;'>{paragraph}</p>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"<p class='unesco-body'>{paragraph}</p>", unsafe_allow_html=True
            )


def _render_black_lead(text: str, *, max_width: str = "18ch") -> None:
    st.markdown(
        f"<p style='font-family:\"Space Grotesk\", sans-serif;font-size:2.2rem;line-height:1.08;font-weight:700;letter-spacing:-0.05em;margin:0 0 var(--vr-heading-after) 0;max-width:{max_width};'>{text}</p>",
        unsafe_allow_html=True,
    )


def _render_metric_stack(value: Any, label: str) -> None:
    st.markdown(
        f"<div style='margin-bottom:1.1rem;'>"
        f"<div style='font-family:\"Space Grotesk\", sans-serif;font-size:3.2rem;line-height:0.96;font-weight:500;letter-spacing:-0.04em;color:var(--unesco-ink);white-space:nowrap;'>{value}</div>"
        f"<div style='font-family:\"Space Grotesk\", sans-serif;font-size:0.95rem;line-height:1.25;font-weight:400;color:var(--unesco-muted);margin-top:0.35rem;white-space:nowrap;'>{label}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )


def _render_day_stack(value: str, label: str) -> None:
    st.markdown(
        f"<div style='margin-bottom:0.35rem;'>"
        f"<div style='font-family:\"Space Grotesk\", sans-serif;font-size:1.45rem;line-height:1.15;font-weight:500;letter-spacing:-0.02em;color:var(--unesco-ink);'>{value}</div>"
        f"<div style='font-family:\"Space Grotesk\", sans-serif;font-size:0.95rem;line-height:1.25;font-weight:400;color:var(--unesco-muted);margin-top:0.3rem;'>{label}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )


def _current_day_label() -> str:
    today = dt.datetime.now().strftime("%A, %-d %B %Y")
    return today


def _decade_progress() -> tuple[float, str]:
    now = dt.datetime.now()
    start = dt.datetime(2025, 1, 1, 0, 0, 0)
    end = dt.datetime(2034, 12, 31, 23, 59, 59)
    total = max((end - start).total_seconds(), 1.0)
    elapsed = min(max((now - start).total_seconds(), 0.0), total)
    ratio = elapsed / total
    return ratio, f"{round(ratio * 100)}% into the decade 2025–2034"


def _spacer(rem: float) -> None:
    st.markdown(f"<div style='height:{rem}rem;'></div>", unsafe_allow_html=True)


def _render_data_tokens(metrics: Dict[str, Any]) -> None:
    st.markdown(
        "<p class='unesco-body unesco-token'>"
        f"<code>{metrics['responses']} responses</code> "
        f"<code>{metrics['participants']} participants</code> "
        f"<code>{metrics['active_24h']} active in the last 24h</code>"
        "</p>",
        unsafe_allow_html=True,
    )


def _sorted_counts(counts: Dict[str, int]) -> list[tuple[str, int]]:
    return sorted(
        [(str(k), int(v)) for k, v in (counts or {}).items() if int(v) > 0],
        key=lambda item: (-item[1], item[0].lower()),
    )


def _code_tokens(items: list[str]) -> str:
    if not items:
        return ""
    return " ".join(f"<code>{item}</code>" for item in items)


def _top_labels(counts: Dict[str, int], n: int = 3) -> list[str]:
    return [label for label, _ in _sorted_counts(counts)[:n]]


def _emotion_stats(counts: Dict[str, int]) -> Dict[str, Any]:
    items = _sorted_counts(counts)
    values = [value for _, value in items]
    cluster_counts: Dict[str, int] = {}
    for label, value in items:
        cluster = _emotion_cluster(label)
        cluster_counts[cluster] = cluster_counts.get(cluster, 0) + value
    cluster_items = sorted(cluster_counts.items(), key=lambda item: (-item[1], item[0]))
    return {
        "top_labels": [label for label, _ in items[:4]],
        "top_clusters": [label for label, _ in cluster_items[:3]],
        "total": sum(values),
        "active_labels": len(items),
        "std_dev": round(pstdev(values), 2) if len(values) > 1 else 0.0,
        "mode_value": values[0] if values else 0,
    }


def _counts_sentence(counts: Dict[str, int], *, item_id: str | None = None) -> str:
    normalized = _normalise_counts_to_options(counts, item_id) if item_id else counts
    items = _sorted_counts(normalized)
    if not items:
        return "No responses are available yet."
    total = sum(value for _, value in items)
    top = items[:3]
    fragments = [f"{label} ({value})" for label, value in top]
    if len(fragments) == 1:
        dominant = fragments[0]
    elif len(fragments) == 2:
        dominant = " and ".join(fragments)
    else:
        dominant = ", ".join(fragments[:-1]) + f", and {fragments[-1]}"
    return (
        f"The strongest responses are {dominant}, across {total} recorded selections."
    )


def _arrival_paragraphs(counts: Dict[str, int]) -> list[str]:
    stats = _emotion_stats(counts)
    top_labels = _code_tokens(stats["top_labels"][:3])
    top_clusters = _code_tokens(stats["top_clusters"][:3])
    return [
        "Participants arrive with layered emotional states. With information, with history.",
        "Emotions are not isolated. They are complex and intertwined.",
        f"The most visible arrival emotions are {top_labels}. At the cluster level, the room is shaped most strongly by {top_clusters}.",
        "The room held multiple emotional states at once, like a chord is a superposition of waves.",
        "This initial configuration matters. It defines the conditions under which this collective process unfolds.",
    ]


def _arrival_interpretation(counts: Dict[str, int]) -> list[str]:
    stats = _emotion_stats(counts)
    return [
        "Arrival patterns suggest a group that is open and engaged, aware of complexity, tension, and unresolved questions.",
        f"Across {stats['active_labels']} active emotional labels, the distribution has a standard variation of <code>{stats['std_dev']}</code>, which confirms that the room is not neutral and does not collapse into a single mood.",
        "A room capable of continuing, provided that conditions, asymmetries, and doubts remain visible.",
    ]


def _environment_paragraphs(counts: Dict[str, int]) -> list[str]:
    stats = _emotion_stats(counts)
    return [
        "Signals of environmental change intensify rather than flatten.",
        f"The modal emotional intensity is <code>{stats['mode_value']}</code>, and the standard variation across active labels is <code>{stats['std_dev']}</code>. The most pronounced terms are {_code_tokens(stats['top_labels'][:4])}.",
        "These emotional states coexist. That coexistence is critical: it reveals both the pressure to act and the need to remain connected, attentive, and capable of response.",
    ]


def _societal_paragraphs(counts: Dict[str, int]) -> list[str]:
    stats = _emotion_stats(counts)
    return [
        f"The room projects societal change through a mixed field led by {_code_tokens(stats['top_labels'][:4])}.",
        "Some trajectories move toward engagement and hope. Others remain in uncertainty, scepticism, or tension.",
        "When do shifts mark a threshold: from perceiving change to positioning oneself within it? The question becomes less about the system, and more about our capacity to act together.",
        "Where momentum stabilises, coordination can grow. Where it fragments, facilitation becomes necessary.",
    ]


def _collaboration_paragraphs(counts: Dict[str, int]) -> list[str]:
    return [
        "Collaboration is one of the central tests of this room.",
        _counts_sentence(counts, item_id="COLLABORATION_READINESS"),
        "The responses show whether differences are seen as workable, conditional, or too strong to hold together.",
    ]


def _agency_paragraphs(counts: Dict[str, int]) -> list[str]:
    return [
        "Collective action does not necessarily rely on agreement, but on whether participants feel capable of shaping what happens next.",
        _counts_sentence(counts, item_id="PERSONAL_AGENCY"),
        "This question makes visible the room’s perceived power to take collective decisions.",
    ]


def _priority_paragraphs(counts: Dict[str, int]) -> list[str]:
    options = ", ".join(_question_options("PRIORITY_AFTER_NO_RETURN"))
    return [
        "When reversal is no longer possible, priorities become clearer and sharper.",
        "The responses below show which orientation becomes most important under irreversible conditions.",
        f"Available orientations: {options}.",
        _counts_sentence(counts),
    ]


def _feedback_paragraphs(counts: Dict[str, int]) -> list[str]:
    labelled = {
        _feedback_label(label): value for label, value in (counts or {}).items()
    }
    return [
        "Participants were also asked how this opening module felt to them.",
        "This is not an afterthought. It measures how smooth this experience has been perceived.",
        _counts_sentence(labelled),
    ]


def _feedback_label(raw: str) -> str:
    token = str(raw or "").strip().lower()
    mapping = {
        "faces:0": "Very difficult",
        "faces:1": "Difficult",
        "faces:2": "Mixed",
        "faces:3": "Positive",
        "faces:4": "Very positive",
    }
    return mapping.get(token, raw)


def _question_options(item_id: str) -> List[str]:
    q = QUESTION_BY_ID.get(item_id)
    return list(getattr(q, "options", []) or [])


def _normalise_choice_key(value: str) -> str:
    text = str(value or "").strip()
    text = text.replace(" - ", ", ").replace(" — ", ", ")
    text = " ".join(text.split())
    return text.casefold()


def _normalise_counts_to_options(
    counts: Dict[str, int], item_id: str
) -> Dict[str, int]:
    options = _question_options(item_id)
    if not options:
        return counts
    option_lookup = {_normalise_choice_key(option): option for option in options}
    folded: Dict[str, int] = {option: 0 for option in options}
    extras: Dict[str, int] = {}
    for raw_label, raw_value in (counts or {}).items():
        canonical = option_lookup.get(_normalise_choice_key(str(raw_label)))
        if canonical:
            folded[canonical] += int(raw_value)
        else:
            extras[str(raw_label)] = extras.get(str(raw_label), 0) + int(raw_value)
    for key, value in extras.items():
        folded[key] = folded.get(key, 0) + value
    return {key: value for key, value in folded.items() if value > 0}


@st.cache_data(ttl=300, show_spinner=False)
def _participants_snapshot() -> List[str]:
    repo = get_notion_repo()
    if not repo or not hasattr(repo, "list_all_players"):
        return []
    players = repo.list_all_players(limit=500)

    def display_name(player: Dict[str, Any]) -> str:
        nickname = str(player.get("nickname") or "").strip()
        access_key = str(player.get("access_key") or "").strip()
        if not nickname:
            return "🧊"
        if len(nickname) == 32 and all(
            ch in "0123456789abcdefABCDEF" for ch in nickname
        ):
            if not access_key or nickname.upper() == access_key.upper():
                return "🧊"
        return nickname

    names = [display_name(p) for p in players]
    names = [n for n in names if n]

    deduped: List[str] = []
    seen_named: set[str] = set()
    for name in names:
        if name == "🧊":
            deduped.append(name)
            continue
        key = name.strip().lower()
        if key in seen_named:
            continue
        seen_named.add(key)
        deduped.append(name)

    return sorted(deduped, key=lambda n: (n == "🧊", n.lower()))


def render_hero(opening_lead: str) -> None:
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
        st.markdown(
            "<div class='unesco-kicker'>Opening the Decade of Action for Cryospheric Sciences</div>",
            unsafe_allow_html=True,
        )
        st.title("Art for the Cryosphere, a collective experiment at UNESCO.")
        st.markdown(
            f"<p class='unesco-accent' style='font-size:1.55rem;line-height:1.12;margin-top:-0.25rem;max-width:none;'>{opening_lead}</p>",
            unsafe_allow_html=True,
        )


def render_opening(metrics: Dict[str, Any]) -> None:
    left, right = st.columns([1.15, 0.85], vertical_alignment="top")
    with left:
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
            _render_prose(OPENING_PARAGRAPHS)
        with stylable_container(
            key="unesco-opening-contributors",
            css_styles=CARD_SOFT_CSS + "\nmargin-bottom: 40px;",
        ):
            st.caption("The session connected the voices and works of")
            st.markdown(
                f"<p class='unesco-body' style='max-width:none;'>{CONTRIBUTOR_LINE}</p>",
                unsafe_allow_html=True,
            )
            st.markdown(
                f"<p class='unesco-note' style='max-width:none;'>{AFFILIATION_LINE}</p>",
                unsafe_allow_html=True,
            )
    with right:
        with stylable_container(
            key="unesco-opening-metrics",
            css_styles=CARD_SOFT_CSS + "\nmargin-bottom: 24px;",
        ):
            st.caption("Signals at a glance")
            decade_ratio, decade_caption = _decade_progress()
            st.progress(decade_ratio, text=decade_caption)
            _spacer(1.6)
            _render_day_stack(_current_day_label(), "today")
            _spacer(1.2)
            m1, m2 = st.columns(2)
            with m1:
                _render_metric_stack(metrics["participants"], "participants")
                _render_metric_stack(metrics["emotion_total"], "emotion selections")
            with m2:
                _render_metric_stack(metrics["responses"], "responses")
                _render_metric_stack(metrics["decision_total"], "decisions")
        with stylable_container(
            key="unesco-opening-audience",
            css_styles="""
background: rgba(255,255,255,0.62);
border: 1px solid rgba(19,36,52,0.08);
border-radius: 22px;
padding: 28px;
""",
        ):
            st.caption("Audience participants")
            names = _participants_snapshot()
            if names:
                st.markdown(
                    f"<p style='font-family:\"Space Grotesk\", sans-serif;font-size:1.22rem;line-height:1.45;font-weight:500;letter-spacing:-0.01em;color:var(--unesco-ink);max-width:none;margin:0;'>{', '.join(names)}</p>",
                    unsafe_allow_html=True,
                )
                st.caption("🧊 indicates anonymous participant")
            else:
                st.caption("No participant snapshot is currently available.")


def render_full_image(
    url: str, caption: str, *, title: str = "", kicker: str = ""
) -> None:
    if kicker:
        st.markdown(
            f"<div class='unesco-kicker' style='margin-bottom:0.2rem;'>{kicker}</div>",
            unsafe_allow_html=True,
        )
    if title:
        st.markdown(
            f"<p style='font-family:\"Space Grotesk\", sans-serif;font-size:1.9rem;line-height:1.02;font-weight:700;letter-spacing:-0.04em;margin:0 0 0.8rem 0;'>{title}</p>",
            unsafe_allow_html=True,
        )
    st.image(url, width="stretch")
    st.caption(caption)
    _spacer(2.5)


def _image_meta(index: int) -> Dict[str, str]:
    idx = index + 1
    return {
        "title": str(MEDIA_CAPTIONS.get(f"image_{idx}_title") or f"Image {idx}"),
        "kicker": str(MEDIA_CAPTIONS.get(f"image_{idx}_kicker") or "Image"),
        "caption": str(
            MEDIA_CAPTIONS.get(f"image_{idx}")
            or f"Photographic trace {idx} from the UNESCO moment."
        ),
    }


def render_core_objective() -> None:
    with stylable_container(
        key="unesco-core-objective",
        css_styles=CARD_SECTION_CSS,
    ):
        st.caption("From observation to coordination")
        _render_black_lead(
            "This is our attempt to move from observation to coordination. From awareness to action.",
            max_width="none",
        )
        _render_prose(CORE_OBJECTIVE_PARAGRAPHS)
        st.markdown(
            f"<p class='unesco-accent' style='font-size:1.5rem;line-height:1.14;margin:0;'>{CORE_OBJECTIVE_ACCENT}</p>",
            unsafe_allow_html=True,
        )


def render_sound_prompt() -> None:
    st.caption("Listening")
    _render_black_lead("Have you ever heard the voice of a glacier?", max_width="none")
    st.markdown(
        f"<p class='unesco-accent' style='font-size:1.35rem;line-height:1.18;margin:0 0 var(--vr-heading-after) 0;max-width:none;'>{SOUND_BLOCK['subtitle']}</p>",
        unsafe_allow_html=True,
    )
    pad_left, centre, pad_right = st.columns([0.8, 1.3, 0.8], vertical_alignment="top")
    with centre:
        with stylable_container(
            key="unesco-sound-quote",
            css_styles=CARD_PAPER_CSS,
        ):
            st.markdown(
                f"<p class='unesco-note unesco-centre' style='max-width:none;font-size:1.56rem;line-height:1.38;margin:0 0 var(--vr-body-gap) 0;color:var(--unesco-serif);'>{SOUND_BLOCK['quote']}</p>",
                unsafe_allow_html=True,
            )
            st.markdown(
                f"<p class='unesco-note unesco-centre' style='max-width:none;margin:0;font-size:1.08rem;'>{SOUND_BLOCK['credit']}</p>",
                unsafe_allow_html=True,
            )
        with stylable_container(
            key="unesco-sound-embed",
            css_styles=CARD_SOFT_CSS + "\npadding: 24px 24px 18px;",
        ):
            st.caption("Sound")
            components.html(SOUNDCLOUD_EMBED, height=140)
            st.caption(MEDIA_CAPTIONS["sound"])
            st.markdown(
                f"<p class='unesco-note unesco-token' style='margin-top:0.75rem;'>{MEDIA_CAPTIONS['svalbard']}</p>",
                unsafe_allow_html=True,
            )
    _spacer(1.35)
    st.markdown(
        f"<p class='unesco-black-lead unesco-centre' style='max-width:none;margin:0;'>{SOUND_BLOCK['prompt']}</p>",
        unsafe_allow_html=True,
    )
    _spacer(2.7)


def render_method(metrics: Dict[str, Any]) -> None:
    with stylable_container(
        key="unesco-method",
        css_styles=CARD_SECTION_CSS,
    ):
        st.caption("Method and participation")
        _render_black_lead("Our session combined multiple languages.", max_width="none")
        _render_prose(METHOD_PARAGRAPHS)
        _render_data_tokens(metrics)


def _render_emotion_chart(title: str, counts: Dict[str, int]) -> None:
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
    rows: List[Dict[str, Any]] = []
    max_count = 0
    for label in labels:
        cluster = _emotion_cluster(label)
        count = int(counts.get(label, 0))
        max_count = max(max_count, count)
        for i in range(1, count + 1):
            rows.append({"emotion": label, "cluster": cluster, "x": i, "count": count})
    dots_df = pd.DataFrame(rows)
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
    height = max(260, 34 * len(labels))
    legend = alt.Legend(title="Emotion family", orient="bottom", direction="vertical")
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
            legend=legend,
        ),
        tooltip=[
            alt.Tooltip("emotion:N", title="Emotion"),
            alt.Tooltip("cluster:N", title="Family"),
            alt.Tooltip("count:Q", title="Count", format=".0f"),
        ],
    )
    dots = base.mark_circle(size=220, opacity=0.8)
    numbers = (
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
    st.altair_chart(
        (dots + numbers).properties(
            title=title,
            height=height,
            padding={"left": 24, "right": 42, "top": 28, "bottom": 36},
        ),
        width="stretch",
    )


def _render_counts_chart(
    title: str, counts: Dict[str, int], *, label_transform=None
) -> None:
    if not counts:
        st.caption(f"{title}: no data yet.")
        return
    rows = []
    for key, value in (counts or {}).items():
        label = label_transform(str(key)) if label_transform else str(key)
        rows.append({"label": label, "value": int(value)})
    rows.sort(key=lambda row: row["value"], reverse=True)
    df = pd.DataFrame(rows)
    chart = (
        alt.Chart(df)
        .mark_bar(color=GLACIER_THEME["plot_blue"])
        .encode(
            x=alt.X("value:Q", title="Count", axis=alt.Axis(format="d")),
            y=alt.Y(
                "label:N",
                sort="-x",
                title=None,
                axis=alt.Axis(labelOverlap=False, labelLimit=1000),
            ),
            tooltip=["label:N", alt.Tooltip("value:Q", format=".0f")],
        )
        .properties(
            title=title,
            height=max(220, 34 * len(df)),
            padding={"left": 24, "right": 42, "top": 28, "bottom": 24},
        )
    )
    st.altair_chart(chart, width="stretch")


def _render_signal_timeline(title: str, timeline: List[Dict[str, Any]]) -> None:
    if not timeline:
        st.caption(f"{title}: no time series available yet.")
        return
    df = pd.DataFrame(
        [
            {
                "t": item.get("t"),
                "cumulative": item.get("cumulative", 0),
                "score": item.get("score", 0),
                "bucket": item.get("bucket", "unknown"),
            }
            for item in timeline
            if item.get("t")
        ]
    )
    if df.empty:
        st.caption(f"{title}: no time series available yet.")
        return
    event_start = "2026-03-19T16:00:00+01:00"
    event_end = "2026-03-19T17:30:00+01:00"
    band_df = pd.DataFrame([{"start": event_start, "end": event_end}])
    marker_df = pd.DataFrame(
        [
            {
                "t": event_start,
                "label": "the event",
                "cumulative": float(df["cumulative"].max()),
            }
        ]
    )

    x_scale = alt.Scale(
        domain=[min(df["t"].min(), event_start), max(df["t"].max(), event_end)]
    )
    y_max = max(1.0, float(df["cumulative"].max()))

    base = alt.Chart(df).encode(
        x=alt.X("t:T", title=None, scale=x_scale),
        y=alt.Y(
            "cumulative:Q",
            title="Signal",
            axis=alt.Axis(format="d"),
            scale=alt.Scale(domain=[0, y_max + 1]),
        ),
        tooltip=[
            alt.Tooltip("t:T", title="Time"),
            alt.Tooltip("cumulative:Q", title="Cumulative signal", format=".0f"),
        ],
    )
    band = (
        alt.Chart(band_df)
        .mark_rect(color="#d8dde3", opacity=0.28)
        .encode(
            x=alt.X("start:T", scale=x_scale),
            x2="end:T",
        )
    )
    bucket_domain = ["yes", "upon_condition", "no", "unknown"]
    bucket_range = [
        GLACIER_THEME["plot_blue"],
        "#b29a56",
        "#8f5d67",
        "#9aa7b4",
    ]
    points = base.mark_circle(size=450, opacity=0.95).encode(
        color=alt.Color(
            "bucket:N",
            scale=alt.Scale(domain=bucket_domain, range=bucket_range),
            legend=alt.Legend(
                title="Signal event", orient="bottom", direction="horizontal"
            ),
        ),
        tooltip=[
            alt.Tooltip("t:T", title="Time"),
            alt.Tooltip("cumulative:Q", title="Cumulative signal", format=".0f"),
            alt.Tooltip("bucket:N", title="Event"),
            alt.Tooltip("score:Q", title="Mapped value", format=".0f"),
        ],
    )
    tick = (
        alt.Chart(marker_df)
        .mark_tick(color="#98a4b3", thickness=2, size=18)
        .encode(
            x=alt.X("t:T", scale=x_scale),
            y=alt.value(10),
            color=alt.Color(
                "label:N",
                legend=alt.Legend(title=None, orient="bottom", direction="horizontal"),
                scale=alt.Scale(domain=["the event"], range=["#98a4b3"]),
            ),
        )
    )
    chart = (
        (band + points + tick)
        .properties(
            title=title,
            height=300,
            padding={"left": 28, "right": 34, "top": 28, "bottom": 40},
            background=GLACIER_THEME["bg_top"],
        )
        .configure_view(stroke=None)
    )
    st.altair_chart(chart, width="stretch")


def _render_signal_line(counts: Dict[str, int]) -> None:
    buckets = _normalise_org_signal_counts(counts)

    def circles(colour: str, count: int) -> str:
        return "".join(
            f"<span style='display:inline-block;width:36px;height:36px;border-radius:50%;background:{colour};margin:0 8px 10px 0;'></span>"
            for _ in range(max(0, count))
        )

    st.markdown(
        "<div class='unesco-centre' style='margin:0.5rem 0 0.75rem 0;'>"
        f"<div>{circles('#2e7d32', buckets['yes'])}{circles('#fbc02d', buckets['upon_condition'])}{circles('#c62828', buckets['no'])}</div>"
        f"<p class='unesco-body unesco-token' style='max-width:none;'><code>yes: {buckets['yes']}</code> <code>upon condition: {buckets['upon_condition']}</code> <code>no: {buckets['no']}</code></p>"
        "</div>",
        unsafe_allow_html=True,
    )


def render_text_and_data(
    title: str, paragraphs: List[str], render_data, *, data_left: bool = False
) -> None:
    st.caption(title)
    if title == "Arrival emotions":
        _render_black_lead(
            "Before any discussion, the room already has a texture.",
            max_width="none",
        )
    elif title == "Environmental change":
        _render_black_lead(
            "As the focus shifted towards environmental change, emotional tones intensify.",
            max_width="none",
        )
    elif title == "Societal projection":
        _render_black_lead(
            "Does the field converge when projecting towards societal change?",
            max_width="none",
        )
    left, right = st.columns([1.25, 1], vertical_alignment="top")
    text_col, data_col = (right, left) if data_left else (left, right)
    with text_col:
        with stylable_container(
            key=f"{title.lower().replace(' ', '-')}-text",
            css_styles=CARD_SECTION_CSS
            + "\nmargin-bottom: 0;\npadding: 32px;\nheight: 100%;",
        ):
            _render_prose(paragraphs)
    with data_col:
        with stylable_container(
            key=f"{title.lower().replace(' ', '-')}-data",
            css_styles=CARD_SOFT_CSS + "\nheight: 100%;",
        ):
            render_data()
    _spacer(2.5)


def render_interpretation(paragraphs: List[str]) -> None:
    st.caption("First signal")
    _render_black_lead(
        "What emerges is a field of signals that allow multiple narratives.",
        max_width="none",
    )
    with stylable_container(
        key="unesco-interpretation",
        css_styles=CARD_INTERPRETATION_CSS,
    ):
        _render_prose(paragraphs)


def render_decision(counts: Dict[str, int]) -> None:
    st.caption("Decision pivot")
    _render_black_lead("Should we continue this conversation?", max_width="none")
    with stylable_container(
        key="unesco-decision",
        css_styles=CARD_DECISION_CSS,
    ):
        st.markdown("<div class='unesco-centre'>", unsafe_allow_html=True)
        _render_signal_line(counts)
        buckets = _normalise_org_signal_counts(counts)
        st.markdown(
            f"<p class='unesco-body unesco-token' style='max-width:none;'><code>{buckets['yes']} yes</code> <code>{buckets['upon_condition']} conditional</code> <code>{buckets['no']} no</code></p>",
            unsafe_allow_html=True,
        )
        _render_prose(
            [
                "The room responded with a clear orientation.",
                "The signal leans toward continuation, with a small but meaningful conditional layer. Note that the count includes test interactions during the beta testing period.",
                "This is not consensus.",
                "It is a direction that includes both momentum and attention to conditions.",
            ]
        )
        st.markdown("</div>", unsafe_allow_html=True)


def render_meta() -> None:
    with stylable_container(
        key="unesco-meta",
        css_styles=CARD_SECTION_CSS,
    ):
        st.caption("Meta interpretation")
        _render_prose(META_PARAGRAPHS)


def render_additional_signal_blocks(question_map: Dict[str, Dict[str, Any]]) -> None:
    with stylable_container(
        key="unesco-time-signal",
        css_styles=CARD_SECTION_CSS,
    ):
        st.caption("Time signal")
        _render_black_lead(
            "A collective signal accumulates through time.", max_width="none"
        )
        st.markdown(
            "<p class='unesco-body' style='max-width:none;'>"
            "This plot refers only to the collective entry question <code>Should we continue this conversation?</code>. "
            "When the curve stays close to zero, the room remains undecided or split. "
            "If the cumulative signal rises, support for continuation is growing. "
            "If it falls below zero, hesitation turns into aversion or refusal. "
            "The shape therefore reads less like a vote count than a moving orientation of the group."
            "</p>",
            unsafe_allow_html=True,
        )
        _render_signal_timeline(
            "Collective signal over time",
            question_map.get("ORGANISATION_SIGNAL", {}).get("timeline", []),
        )
        st.caption(
            "For this question, responses are mapped as yes = +1, conditional = 0, no = -1. "
            "If these signal responses are ordered by timestamp as r₁, r₂, …, rₙ, the plotted value at step k is "
            "Sₖ = Σᵢ₌₁ᵏ rᵢ. The shaded interval marks the event itself, from 19 March 2026 at 16:00 to 17:30."
        )
        st.info(
            "Some of these data already suggest tendencies. But the more the merrier. If you have not yet taken part, enter the platform and contribute with your signal."
        )
        c1, c2 = st.columns(2)
        with c1:
            st.page_link(
                "pages/01_Login.py",
                label="Login and go to session",
                icon=":material/login:",
            )
        with c2:
            st.page_link(
                "pages/Splash.py",
                label="Create key and participate",
                icon=":material/key:",
            )
    render_text_and_data(
        "Collaboration",
        _collaboration_paragraphs(
            question_map.get("COLLABORATION_READINESS", {}).get("counts", {})
        ),
        lambda: _render_counts_chart(
            "Do you feel collaboration is possible across differences?",
            _normalise_counts_to_options(
                question_map.get("COLLABORATION_READINESS", {}).get("counts", {}),
                "COLLABORATION_READINESS",
            ),
        ),
    )
    render_text_and_data(
        "Agency",
        _agency_paragraphs(question_map.get("PERSONAL_AGENCY", {}).get("counts", {})),
        lambda: _render_counts_chart(
            "Do you feel able to influence collective decisions?",
            _normalise_counts_to_options(
                question_map.get("PERSONAL_AGENCY", {}).get("counts", {}),
                "PERSONAL_AGENCY",
            ),
        ),
        data_left=True,
    )
    render_text_and_data(
        "After the point of no return",
        _priority_paragraphs(
            question_map.get("PRIORITY_AFTER_NO_RETURN", {}).get("counts", {})
        ),
        lambda: _render_counts_chart(
            "When reversal is no longer possible, what becomes most important?",
            question_map.get("PRIORITY_AFTER_NO_RETURN", {}).get("counts", {}),
        ),
    )
    render_text_and_data(
        "Opening feedback",
        _feedback_paragraphs(question_map.get("FINAL_FEEDBACK", {}).get("counts", {})),
        lambda: _render_counts_chart(
            "How did this opening module feel to the participants?",
            question_map.get("FINAL_FEEDBACK", {}).get("counts", {}),
            label_transform=_feedback_label,
        ),
        data_left=True,
    )


def render_gallery() -> None:
    st.divider()
    st.caption("Images and traces")
    cols = st.columns(3)
    for idx, url in enumerate(GALLERY_URLS):
        with cols[idx % 3]:
            st.image(url, width="stretch")
    st.caption(MEDIA_CAPTIONS["gallery"])
    _spacer(2.5)


def render_action_block() -> None:
    with stylable_container(
        key="unesco-actions",
        css_styles=CARD_ACTION_CSS,
    ):
        st.markdown("<div class='unesco-centre'>", unsafe_allow_html=True)
        st.caption("Continue")
        st.subheader("This is an opening.")
        st.markdown(
            "<p class='unesco-body' style='max-width:48ch;margin:0 auto 1.5rem auto;'>Bring this format elsewhere, return to the platform, or contact the organisers to continue the experiment.</p>",
            unsafe_allow_html=True,
        )
        c1, c2, c3 = st.columns(3)
        with c1:
            st.button(
                "Start a new session", type="secondary", width="stretch", disabled=True
            )
        with c2:
            st.page_link(
                "pages/01_Login.py", label="Join the platform", icon=":material/login:"
            )
        with c3:
            st.button(
                "Contact organisers", type="tertiary", width="stretch", disabled=True
            )
        st.markdown("</div>", unsafe_allow_html=True)


def main() -> None:
    set_page()
    apply_theme()
    _apply_page_css()

    payload = get_overview_payload(GLOBAL_SESSION_SLUG)
    question_map = {
        str(q.get("item_id") or ""): q for q in payload.get("questions", []) or []
    }
    metrics = {
        "responses": int(payload.get("response_count", 0)),
        "participants": int(payload.get("participant_count", 0)),
        "active_24h": int(count_active_users(24 * 60, session_id="")),
    }
    emotion_total = 0
    for item_id in [
        "ARRIVAL_EMOTION",
        "ENVIRONMENT_CHANGE_EMOTION",
        "SOCIETAL_CHANGE_EMOTION",
    ]:
        emotion_total += sum(
            int(v)
            for v in (question_map.get(item_id, {}).get("counts", {}) or {}).values()
        )
    decision_total = sum(
        int(v)
        for v in _normalise_org_signal_counts(
            question_map.get("ORGANISATION_SIGNAL", {}).get("counts", {})
        ).values()
    )
    metrics["emotion_total"] = emotion_total
    metrics["decision_total"] = decision_total

    render_hero(OPENING_LEAD)
    render_opening(metrics)
    for idx, image_url in enumerate(IMAGE_URLS[:1]):
        image_meta = _image_meta(idx)
        render_full_image(
            image_url,
            image_meta["caption"],
            title=image_meta["title"],
            kicker=image_meta["kicker"],
        )
    render_core_objective()
    render_sound_prompt()
    render_method(metrics)
    render_text_and_data(
        "Arrival emotions",
        _arrival_paragraphs(question_map.get("ARRIVAL_EMOTION", {}).get("counts", {})),
        lambda: _render_emotion_chart(
            "Arrival emotions",
            question_map.get("ARRIVAL_EMOTION", {}).get("counts", {}),
        ),
    )
    render_interpretation(
        _arrival_interpretation(
            question_map.get("ARRIVAL_EMOTION", {}).get("counts", {})
        )
    )
    for idx, image_url in enumerate(IMAGE_URLS[1:2], start=1):
        image_meta = _image_meta(idx)
        render_full_image(
            image_url,
            image_meta["caption"],
            title=image_meta["title"],
            kicker=image_meta["kicker"],
        )
    render_text_and_data(
        "Environmental change",
        _environment_paragraphs(
            question_map.get("ENVIRONMENT_CHANGE_EMOTION", {}).get("counts", {})
        ),
        lambda: _render_emotion_chart(
            "Emotion toward environmental change",
            question_map.get("ENVIRONMENT_CHANGE_EMOTION", {}).get("counts", {}),
        ),
        data_left=True,
    )
    render_text_and_data(
        "Societal projection",
        _societal_paragraphs(
            question_map.get("SOCIETAL_CHANGE_EMOTION", {}).get("counts", {})
        ),
        lambda: _render_emotion_chart(
            "Emotion toward societal change",
            question_map.get("SOCIETAL_CHANGE_EMOTION", {}).get("counts", {}),
        ),
    )
    render_decision(question_map.get("ORGANISATION_SIGNAL", {}).get("counts", {}))
    for idx, image_url in enumerate(IMAGE_URLS[2:3], start=2):
        image_meta = _image_meta(idx)
        render_full_image(
            image_url,
            image_meta["caption"],
            title=image_meta["title"],
            kicker=image_meta["kicker"],
        )
    render_additional_signal_blocks(question_map)
    render_meta()
    for idx, image_url in enumerate(IMAGE_URLS[3:], start=3):
        image_meta = _image_meta(idx)
        render_full_image(
            image_url,
            image_meta["caption"],
            title=image_meta["title"],
            kicker=image_meta["kicker"],
        )
    render_gallery()
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
