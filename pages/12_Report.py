from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import altair as alt
import pandas as pd
import streamlit as st

from infra.app_context import get_notion_repo
from infra.event_logger import log_event
from models.catalog import QUESTION_BY_ID
from services.aggregator import get_overview_payload
from services.presence import count_active_users
from services.response_reader import fetch_session_responses
from ui import apply_theme, heading, set_page

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
    "inspired": "Engagement",
    "hopeful": "Engagement",
    "hope": "Engagement",
    "calm": "Engagement",
    "solidarity": "Engagement",
    "energised": "Engagement",
    "protective": "Responsibility and action",
    "responsibility": "Responsibility and action",
    "responsible": "Responsibility and action",
    "determination": "Responsibility and action",
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
}

EMOTION_CLUSTER_COLOURS = {
    "Curiosity and openness": "#5e81ac",
    "Engagement": "#2e7d32",
    "Tension and conflict": "#c62828",
    "Responsibility and action": "#ef6c00",
    "Other": "#757575",
}


def _slugify(value: str) -> str:
    return "-".join(
        part
        for part in "".join(ch.lower() if ch.isalnum() else "-" for ch in str(value or "")).split("-")
        if part
    )


@st.cache_data(ttl=300, show_spinner=False)
def _sessions_cache() -> List[Dict[str, Any]]:
    repo = get_notion_repo()
    if not repo:
        return []
    sessions = repo.list_sessions(limit=200)
    return sorted(
        sessions,
        key=lambda s: (int(s.get("session_order", 999)), str(s.get("session_code", "")).upper()),
    )


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
        if len(nickname) == 32 and all(ch in "0123456789abcdefABCDEF" for ch in nickname):
            if not access_key or nickname.upper() == access_key.upper():
                return "🧊"
        return nickname

    names = [display_name(p) for p in players]
    names = [n for n in names if n]
    return sorted(names, key=lambda n: (n == "🧊", n.lower()))


def _event_header() -> str:
    return (
        "Date 19 March 2026 · Time: 16:00-17:30 (CET) · Room XI, UNESCO Headquarters"
        "\n\nOrganisers and co-organisers: Ignacio Palomo, Andrés León Baldelli, Leopold Bouzard, "
        "Veronique Dansereau, Jean-François Delhom, Bruno Doucey"
    )


def _extract_choice(value_json: Any) -> Any:
    if isinstance(value_json, dict):
        if "answer" in value_json:
            return value_json.get("answer")
        if "choice" in value_json:
            return value_json.get("choice")
    return value_json


def _normalise_choices(value_json: Any) -> List[str]:
    choice = _extract_choice(value_json)
    if isinstance(choice, list):
        return [str(x).strip() for x in choice if str(x).strip()]
    if isinstance(choice, str) and choice.strip():
        return [choice.strip()]
    return []


def _latest_player_response(
    rows: List[Dict[str, Any]],
    item_id: str,
    player_page_id: str,
    device_id: str,
) -> Optional[Dict[str, Any]]:
    candidates = [r for r in rows if str(r.get("item_id") or "") == item_id]
    if not candidates:
        return None
    mine = [
        r
        for r in candidates
        if (player_page_id and str(r.get("player_id") or "") == player_page_id)
        or (device_id and str(r.get("device_id") or "") == device_id)
    ]
    pool = mine if mine else candidates
    pool = sorted(pool, key=lambda r: str(r.get("submitted_at") or r.get("timestamp") or ""))
    return pool[-1] if pool else None


def _find_question(payload: Dict[str, Any], item_id: str) -> Dict[str, Any]:
    for q in payload.get("questions", []):
        if str(q.get("item_id") or "") == item_id:
            return q
    return {}


def _question_prompt(item_id: str) -> str:
    q = QUESTION_BY_ID.get(item_id)
    return str(getattr(q, "prompt", item_id))


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
        key in token
        for key in ["fear", "anx", "anger", "sad", "concern", "urg", "conflict", "overwhelm", "grief", "powerless"]
    ):
        return "Tension and conflict"
    return "Other"


def _data_chip(label: str, value: Any) -> str:
    return f"<span class='report-chip'>{label}: <code>{value}</code></span>"


def _render_signal_glyphs(counts: Dict[str, int]) -> None:
    yes_n = int(counts.get("yes", 0))
    maybe_n = int(counts.get("maybe", 0))
    no_n = int(counts.get("no", 0))

    def _block(colour: str, n: int) -> str:
        if n <= 0:
            return ""
        circles = "".join(
            f"<span style='display:inline-block;width:30px;height:30px;border-radius:50%;background:{colour};margin:3px;'></span>"
            for _ in range(n)
        )
        return f"<span style='display:inline-flex;flex-wrap:wrap;max-width:100%;margin-right:10px'>{circles}</span>"

    html = (
        "<div style='display:flex;justify-content:center;flex-wrap:wrap;align-items:center;gap:8px'>"
        f"{_block('#2e7d32', yes_n)}"
        f"{_block('#fbc02d', maybe_n)}"
        f"{_block('#c62828', no_n)}"
        "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)
    st.caption("Legend: green = yes · yellow = maybe · red = no")


def _render_emotion_field(
    title: str,
    counts: Dict[str, int],
    *,
    personal_choices: Optional[List[str]] = None,
    height: int = 280,
) -> None:
    if not counts and not personal_choices:
        st.caption("No data yet.")
        return

    personal_set = {str(x).strip() for x in (personal_choices or []) if str(x).strip()}
    labels = set(counts.keys()) | personal_set
    ordered_labels = sorted(
        labels,
        key=lambda x: (
            EMOTION_CLUSTER_ORDER.index(_emotion_cluster(x))
            if _emotion_cluster(x) in EMOTION_CLUSTER_ORDER
            else 999,
            -int(counts.get(x, 0)),
            str(x).lower(),
        ),
    )

    dot_rows: List[Dict[str, Any]] = []
    marker_rows: List[Dict[str, Any]] = []
    max_count = 0
    for label in ordered_labels:
        cluster = _emotion_cluster(label)
        count = int(counts.get(label, 0))
        max_count = max(max_count, count)
        for i in range(1, count + 1):
            dot_rows.append({"emotion": label, "cluster": cluster, "x": i})
        if label in personal_set:
            marker_rows.append({"emotion": label, "cluster": cluster, "x": 0.35})

    dots_df = pd.DataFrame(dot_rows) if dot_rows else pd.DataFrame(columns=["emotion", "cluster", "x"])
    markers_df = pd.DataFrame(marker_rows) if marker_rows else pd.DataFrame(columns=["emotion", "cluster", "x"])
    domain = ordered_labels
    computed_height = max(height, 34 * max(1, len(domain)))

    base = alt.Chart(dots_df).encode(
        y=alt.Y("emotion:N", sort=domain, title=None, axis=alt.Axis(labelOverlap=False)),
        x=alt.X(
            "x:Q",
            title=None,
            axis=alt.Axis(labels=False, ticks=False, domain=False, grid=False),
            scale=alt.Scale(domain=[0, max(1.0, float(max_count) + 1.0)]),
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
        ],
    )
    dots = base.mark_circle(size=270, opacity=0.7)

    marker_layer = (
        alt.Chart(markers_df)
        .mark_point(shape="diamond", size=420, filled=True)
        .encode(
            y=alt.Y("emotion:N", sort=domain, title=None, axis=alt.Axis(labelOverlap=False)),
            x=alt.X("x:Q", scale=alt.Scale(domain=[0, max(1.0, float(max_count) + 1.0)])),
            color=alt.Color(
                "cluster:N",
                scale=alt.Scale(
                    domain=list(EMOTION_CLUSTER_COLOURS.keys()),
                    range=list(EMOTION_CLUSTER_COLOURS.values()),
                ),
                legend=None,
            ),
            tooltip=[alt.Tooltip("emotion:N", title="Your selection")],
        )
    )

    count_labels = pd.DataFrame(
        [
            {"emotion": label, "count": int(counts.get(label, 0)), "x": max(1.0, float(max_count) + 0.25)}
            for label in ordered_labels
        ]
    )
    counts_layer = (
        alt.Chart(count_labels)
        .mark_text(align="left", baseline="middle", dx=4, color="#444444")
        .encode(
            y=alt.Y("emotion:N", sort=domain, title=None, axis=alt.Axis(labelOverlap=False)),
            x=alt.X("x:Q", scale=alt.Scale(domain=[0, max(1.0, float(max_count) + 1.0)])),
            text=alt.Text("count:Q", format=".0f"),
        )
    )

    chart = (dots + marker_layer + counts_layer).properties(title=title, height=computed_height)
    st.altair_chart(chart, width="stretch")
    st.caption("Each dot equals one selection. ◆ marks your own selection.")


def _comparison_label_single(answer: str, counts: Dict[str, int]) -> str:
    if not answer or not counts:
        return "No comparison is available yet."
    ordered = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    top = ordered[0][0] if ordered else ""
    second = ordered[1][0] if len(ordered) > 1 else ""
    if answer == top:
        return "Your answer aligns with the room’s strongest signal."
    if second and answer == second:
        return "Your answer sits close to the room’s strongest signal."
    return "Your answer adds a less common perspective to the room."


def _comparison_label_multi(answer: List[str], counts: Dict[str, int]) -> str:
    if not answer or not counts:
        return "No comparison is available yet."
    top_tags = [k for k, _ in sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:3]]
    overlap = len(set(answer).intersection(top_tags))
    if overlap >= 2:
        return "Your emotional profile strongly overlaps with the room’s leading tones."
    if overlap == 1:
        return "Your emotional profile partially overlaps with the room’s leading tones."
    return "Your emotional profile highlights less represented tones in the room."


def _inject_report_css() -> None:
    st.markdown(
        """
<style>
.report-hero {
  padding: 2.6rem 1.8rem;
  border-radius: 14px;
  background: linear-gradient(120deg, #eaf4fb 0%, #f8fbff 55%, #eef7f1 100%);
  border: 1px solid rgba(14, 30, 60, 0.08);
}
.report-hero h2 { margin: 0; font-size: 2.6rem; line-height: 1.08; }
.report-hero p { margin-top: .6rem; margin-bottom: 0; }
.report-section { margin-top: 4.4rem; margin-bottom: 4.4rem; }
.report-title { font-size: 1.65rem; font-weight: 760; margin-bottom: 0.85rem; }
.report-body { font-size: 1.08rem; line-height: 1.65; font-weight: 430; }
.report-chip {
  display: inline-block;
  margin-right: .5rem;
  margin-bottom: .4rem;
  padding: .22rem .56rem;
  border-radius: 999px;
  border: 1px solid rgba(60, 80, 120, .18);
  background: rgba(245, 248, 255, 1);
  font-size: .92rem;
}
.report-interpret {
  padding: 1rem 1.1rem;
  border-left: 3px solid rgba(46,125,50,.45);
  background: rgba(245, 250, 246, .7);
  border-radius: 8px;
}
.report-centred { text-align: center; }
.report-narrow { max-width: 920px; margin: 0 auto; }
.report-cta {
  padding: 1.2rem;
  border-radius: 12px;
  border: 1px solid rgba(14, 30, 60, 0.08);
  background: #f7fafc;
}
.block-container { max-width: 1120px !important; }
</style>
""",
        unsafe_allow_html=True,
    )


def render_hero(participants: List[str]) -> None:
    st.markdown(
        """
<div class="report-hero">
  <h2>Art for the Cryosphere</h2>
  <p><strong>A collective experiment at UNESCO</strong></p>
</div>
""",
        unsafe_allow_html=True,
    )
    st.caption(_event_header())
    if participants:
        st.markdown("**Participants snapshot**")
        st.write(", ".join(participants))


def render_block_1_what_happened(payload: Dict[str, Any], session_id: str, participants: List[str]) -> None:
    participant_count = int(payload.get("participant_count", 0))
    response_count = int(payload.get("response_count", 0))
    active_24h = int(count_active_users(24 * 60, session_id=session_id))
    name_excerpt = ", ".join(participants[:24]) if participants else "participants"

    st.markdown("<div class='report-section'>", unsafe_allow_html=True)
    st.markdown("<div class='report-title'>What happened?</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='report-body'>"
        "poetry, photography, questions, emotions, science and art.<br/>"
        "A handful of open and connecting questions.<br/>"
        "Participants entered with different dispositions, expectations, and thresholds."
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        _data_chip("Responses", response_count)
        + _data_chip("Participants", participant_count)
        + _data_chip("Active in last 24h", active_24h),
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='report-body'>Each response carries a position, an emotion, a direction.</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<div class='report-body'>Thanks to: <code>{name_excerpt}</code></div>",
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)


def render_block_2_core_narrative(
    payload: Dict[str, Any],
    rows: List[Dict[str, Any]],
    player_page_id: str,
    device_id: str,
) -> None:
    st.markdown("<div class='report-section'>", unsafe_allow_html=True)
    left, right = st.columns([1.6, 1], vertical_alignment="top")

    with left:
        st.markdown("<div class='report-title'>Core narrative</div>", unsafe_allow_html=True)
        st.markdown(
            "<div class='report-body'>"
            "Signals did not emerge as isolated points. They emerged as a shared field. "
            "Arrival emotions indicate the room’s initial texture: openness, engagement, "
            "tension, and responsibility co-existing rather than replacing one another."
            "</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<div class='report-interpret report-body'>"
            "Interpretation: this opening pattern suggests a room ready to continue, "
            "while keeping conditions, concerns, and asymmetries visible."
            "</div>",
            unsafe_allow_html=True,
        )
        st.components.v1.html(SOUNDCLOUD_EMBED, height=140)

    with right:
        st.caption(f"Question: {_question_prompt('ARRIVAL_EMOTION')}")
        arr = _find_question(payload, "ARRIVAL_EMOTION")
        arr_row = _latest_player_response(rows, "ARRIVAL_EMOTION", player_page_id, device_id)
        personal_arr = _normalise_choices(arr_row.get("value_json")) if arr_row else []
        _render_emotion_field(
            "Arrival emotions",
            arr.get("counts", {}),
            personal_choices=personal_arr,
            height=260,
        )

    st.markdown("</div>", unsafe_allow_html=True)


def render_block_3_decision(payload: Dict[str, Any]) -> None:
    st.markdown("<div class='report-section report-centred report-narrow'>", unsafe_allow_html=True)
    st.markdown("<div class='report-title'>Decision pivot</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='report-body'>"
        "Question: Should we organise another event and continue the conversation?"
        "</div>",
        unsafe_allow_html=True,
    )
    org = _find_question(payload, "ORGANISATION_SIGNAL")
    _render_signal_glyphs(org.get("counts", {}))
    yes = int(org.get("counts", {}).get("yes", 0))
    maybe = int(org.get("counts", {}).get("maybe", 0))
    no = int(org.get("counts", {}).get("no", 0))
    st.markdown(
        _data_chip("yes", yes) + _data_chip("maybe", maybe) + _data_chip("no", no),
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='report-body'>"
        "The room currently leans toward continuation, with a substantial conditional layer."
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)


def render_block_4_deepening(
    payload: Dict[str, Any],
    rows: List[Dict[str, Any]],
    player_page_id: str,
    device_id: str,
) -> None:
    st.markdown("<div class='report-section'>", unsafe_allow_html=True)
    left, right = st.columns([1, 1.6], vertical_alignment="top")

    with left:
        env_q = _find_question(payload, "ENVIRONMENT_CHANGE_EMOTION")
        env_row = _latest_player_response(rows, "ENVIRONMENT_CHANGE_EMOTION", player_page_id, device_id)
        personal_env = _normalise_choices(env_row.get("value_json")) if env_row else []
        st.caption(f"Question: {_question_prompt('ENVIRONMENT_CHANGE_EMOTION')}")
        _render_emotion_field(
            "Emotion toward environmental change",
            env_q.get("counts", {}),
            personal_choices=personal_env,
            height=260,
        )

    with right:
        st.markdown("<div class='report-title'>Deepening</div>", unsafe_allow_html=True)
        st.markdown(
            "<div class='report-body'>"
            "Environmental change is not only assessed; it is felt. "
            "The emotional field shows concern and urgency, but also care and openness. "
            "This coexistence matters for collective coordination."
            "</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<div class='report-interpret report-body'>"
            "Visuals are evidence, not decoration. Text is interpretation, not explanation."
            "</div>",
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)


def render_block_5_societal_projection(
    payload: Dict[str, Any],
    rows: List[Dict[str, Any]],
    player_page_id: str,
    device_id: str,
) -> None:
    st.markdown("<div class='report-section'>", unsafe_allow_html=True)
    left, right = st.columns([1.6, 1], vertical_alignment="top")

    with left:
        st.markdown("<div class='report-title'>Societal projection</div>", unsafe_allow_html=True)
        st.markdown(
            "<div class='report-body'>"
            "When participants move from cryosphere signals to societal change, "
            "emotional tones shift. Some carry urgency into action, others remain "
            "in tension, uncertainty, or guarded hope."
            "</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<div class='report-body'>"
            "This block tracks where collective momentum may stabilise and where it may still require facilitation."
            "</div>",
            unsafe_allow_html=True,
        )

    with right:
        soc_q = _find_question(payload, "SOCIETAL_CHANGE_EMOTION")
        soc_row = _latest_player_response(rows, "SOCIETAL_CHANGE_EMOTION", player_page_id, device_id)
        personal_soc = _normalise_choices(soc_row.get("value_json")) if soc_row else []
        st.caption(f"Question: {_question_prompt('SOCIETAL_CHANGE_EMOTION')}")
        _render_emotion_field(
            "Emotion toward societal change",
            soc_q.get("counts", {}),
            personal_choices=personal_soc,
            height=260,
        )

    st.markdown("</div>", unsafe_allow_html=True)


def render_personalised_relation(
    payload: Dict[str, Any],
    rows: List[Dict[str, Any]],
    player_page_id: str,
    device_id: str,
) -> None:
    st.markdown("<div class='report-section'>", unsafe_allow_html=True)
    st.markdown("<div class='report-title'>Your relation to the room</div>", unsafe_allow_html=True)
    if not (player_page_id or device_id):
        st.caption("Log in to see your personalised comparison with the room.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    org = _find_question(payload, "ORGANISATION_SIGNAL")
    org_row = _latest_player_response(rows, "ORGANISATION_SIGNAL", player_page_id, device_id)
    arrival = _find_question(payload, "ARRIVAL_EMOTION")
    arrival_row = _latest_player_response(rows, "ARRIVAL_EMOTION", player_page_id, device_id)
    collab = _find_question(payload, "COLLABORATION_READINESS")
    collab_row = _latest_player_response(rows, "COLLABORATION_READINESS", player_page_id, device_id)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**Organisation signal**")
        if org_row:
            answer = str(_extract_choice(org_row.get("value_json")) or org_row.get("value_label") or "")
            st.caption(f"You: {answer}")
            txt = answer.lower()
            bucket = "yes" if "yes" in txt else ("maybe" if "maybe" in txt else ("no" if "no" in txt else "unknown"))
            st.caption(
                _comparison_label_single(
                    bucket,
                    {
                        "yes": int(org.get("counts", {}).get("yes", 0)),
                        "maybe": int(org.get("counts", {}).get("maybe", 0)),
                        "no": int(org.get("counts", {}).get("no", 0)),
                    },
                )
            )
    with c2:
        st.markdown("**Arrival emotions**")
        if arrival_row:
            answer_list = _normalise_choices(arrival_row.get("value_json"))
            st.caption(f"You: {', '.join(answer_list) if answer_list else '—'}")
            st.caption(_comparison_label_multi(answer_list, arrival.get("counts", {})))
    with c3:
        st.markdown("**Collaboration readiness**")
        if collab_row:
            answer = str(_extract_choice(collab_row.get("value_json")) or collab_row.get("value_label") or "")
            st.caption(f"You: {answer}")
            st.caption(_comparison_label_single(answer, collab.get("counts", {})))

    st.markdown("</div>", unsafe_allow_html=True)


def render_gallery() -> None:
    st.markdown("<div class='report-section'>", unsafe_allow_html=True)
    st.markdown("<div class='report-title'>Images and traces</div>", unsafe_allow_html=True)
    img_path = Path("assets/img1.png")
    cols = st.columns(3)
    for col in cols:
        with col:
            if img_path.exists():
                st.image(str(img_path), width="stretch")
            else:
                st.info("Gallery image placeholder")
    st.markdown("</div>", unsafe_allow_html=True)


def render_closing_and_cta() -> None:
    st.markdown("<div class='report-section report-narrow'>", unsafe_allow_html=True)
    st.markdown("<div class='report-title'>Closing reflection</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='report-body'>"
        "Signals do not end when a page closes. They remain as trajectories "
        "that can be revisited, discussed, and extended collectively."
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown("<div class='report-cta' style='margin-top:1.2rem'>", unsafe_allow_html=True)
    st.markdown("<div class='report-title' style='font-size:1.35rem'>Continue</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='report-body'>Continue the experiment. Bring this format to another place. Invite new signals.</div>",
        unsafe_allow_html=True,
    )
    c1, c2, c3 = st.columns(3)
    c1.button("Start a new session", disabled=True, width="stretch")
    c2.page_link("pages/01_Login.py", label="Join the platform", icon="🔑")
    c3.button("Contact organisers", disabled=True, width="stretch")
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def main() -> None:
    set_page()
    apply_theme()
    _inject_report_css()

    heading("Report · Trace")

    sessions = _sessions_cache()
    session_map = {_slugify(s.get("session_code") or ""): s for s in sessions}
    default_slug = "global-session"
    selected_slug = default_slug if default_slug in session_map else (list(session_map.keys())[0] if session_map else default_slug)
    session_obj = session_map.get(selected_slug) or {}

    payload = get_overview_payload(selected_slug)
    _, rows = fetch_session_responses(selected_slug)
    player_page_id = str(st.session_state.get("player_page_id") or "")
    device_id = str(st.session_state.get("anon_token") or "")
    participants = _participants_snapshot()

    render_hero(participants)
    render_block_1_what_happened(payload, str(session_obj.get("id") or ""), participants)
    render_block_2_core_narrative(payload, rows, player_page_id, device_id)
    render_block_3_decision(payload)
    render_block_4_deepening(payload, rows, player_page_id, device_id)
    render_block_5_societal_projection(payload, rows, player_page_id, device_id)
    render_personalised_relation(payload, rows, player_page_id, device_id)
    render_gallery()
    render_closing_and_cta()

    log_event(
        module="iceicebaby.report",
        event_type="page_view",
        page="Report",
        player_id=str(st.session_state.get("player_page_id", "")),
        session_id=str(session_obj.get("id") or ""),
        device_id=str(st.session_state.get("anon_token", "")),
        value_label=str(selected_slug),
        metadata={"questions": len(payload.get("questions", []))},
    )


if __name__ == "__main__":
    main()
