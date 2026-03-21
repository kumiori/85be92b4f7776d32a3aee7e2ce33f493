from __future__ import annotations

from collections import Counter
from datetime import datetime
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
<iframe width="100%" height="100" scrolling="no" frameborder="no" allow="autoplay" src="https://w.soundcloud.com/player/?url=https%3A//api.soundcloud.com/tracks/soundcloud%253Atracks%253A2286855149&color=%23ff5500&auto_play=false&hide_related=false&show_comments=true&show_user=true&show_reposts=false&show_teaser=true&visual=true"></iframe>
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
        for part in "".join(
            ch.lower() if ch.isalnum() else "-" for ch in str(value or "")
        ).split("-")
        if part
    )


@st.cache_data(ttl=300, show_spinner=False)
def _sessions_cache() -> List[Dict[str, Any]]:
    repo = get_notion_repo()
    if not repo:
        return []
    sessions = repo.list_sessions(limit=200)
    sessions = sorted(
        sessions,
        key=lambda s: (
            int(s.get("session_order", 999)),
            str(s.get("session_code", "")).upper(),
        ),
    )
    return sessions


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
    return sorted(names, key=lambda n: (n == "🧊", n.lower()))


def _event_header() -> str:
    return (
        "Date 19 March 2026 · Time: 16:00-17:30 (CET) · Room XI, UNESCO Headquarters"
        "\n\nOrganisers and co-organisers: Ignacio Palomo, Andrés León Baldelli, Leopold Bouzard, "
        "Veronique Dansereau, Jean-François Delhom, Bruno Doucey"
    )


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
    pool = sorted(
        pool, key=lambda r: str(r.get("submitted_at") or r.get("timestamp") or "")
    )
    return pool[-1] if pool else None


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
        for key in [
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
        ]
    ):
        return "Tension and conflict"
    return "Other"


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
            dot_rows.append(
                {
                    "emotion": label,
                    "cluster": cluster,
                    "x": i,
                }
            )
        if label in personal_set:
            marker_rows.append(
                {
                    "emotion": label,
                    "cluster": cluster,
                    "x": 0.35,
                }
            )

    dots_df = (
        pd.DataFrame(dot_rows)
        if dot_rows
        else pd.DataFrame(columns=["emotion", "cluster", "x"])
    )
    markers_df = (
        pd.DataFrame(marker_rows)
        if marker_rows
        else pd.DataFrame(columns=["emotion", "cluster", "x"])
    )

    domain = ordered_labels
    computed_height = max(height, 34 * max(1, len(domain)))
    base = alt.Chart(dots_df).encode(
        y=alt.Y(
            "emotion:N",
            sort=domain,
            title=None,
            axis=alt.Axis(labelOverlap=False),
        ),
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
            y=alt.Y(
                "emotion:N",
                sort=domain,
                title=None,
                axis=alt.Axis(labelOverlap=False),
            ),
            x=alt.X(
                "x:Q", scale=alt.Scale(domain=[0, max(1.0, float(max_count) + 1.0)])
            ),
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
            {
                "emotion": label,
                "count": int(counts.get(label, 0)),
                "x": max(1.0, float(max_count) + 0.25),
            }
            for label in ordered_labels
        ]
    )
    counts_layer = (
        alt.Chart(count_labels)
        .mark_text(align="left", baseline="middle", dx=4, color="#444444")
        .encode(
            y=alt.Y(
                "emotion:N",
                sort=domain,
                title=None,
                axis=alt.Axis(labelOverlap=False),
            ),
            x=alt.X(
                "x:Q", scale=alt.Scale(domain=[0, max(1.0, float(max_count) + 1.0)])
            ),
            text=alt.Text("count:Q", format=".0f"),
        )
    )

    chart = (dots + marker_layer + counts_layer).properties(
        title=title, height=computed_height
    )
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
    top_tags = [
        k for k, _ in sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:3]
    ]
    overlap = len(set(answer).intersection(top_tags))
    if overlap >= 2:
        return "Your emotional profile strongly overlaps with the room’s leading tones."
    if overlap == 1:
        return (
            "Your emotional profile partially overlaps with the room’s leading tones."
        )
    return "Your emotional profile highlights less represented tones in the room."


def _render_signal_glyphs(counts: Dict[str, int]) -> None:
    yes_n = int(counts.get("yes", 0))
    maybe_n = int(counts.get("maybe", 0))
    no_n = int(counts.get("no", 0))

    def _block(colour: str, n: int) -> str:
        if n <= 0:
            return ""
        circles = "".join(
            f"<span style='display:inline-block;width:26px;height:26px;border-radius:50%;background:{colour};margin:2px;'></span>"
            for _ in range(n)
        )
        return f"<span style='display:inline-flex;flex-wrap:wrap;max-width:100%;margin-right:8px'>{circles}</span>"

    html = (
        "<div style='display:flex;flex-wrap:wrap;align-items:center;gap:6px'>"
        f"{_block('#2e7d32', yes_n)}"
        f"{_block('#fbc02d', maybe_n)}"
        f"{_block('#c62828', no_n)}"
        "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)
    st.caption("Legend: green = yes · yellow = maybe · red = no")


def _render_bar(title: str, counts: Dict[str, int], *, height: int = 220) -> None:
    if not counts:
        st.caption("No data yet.")
        return
    rows = [{"label": str(k), "value": int(v)} for k, v in counts.items()]
    rows.sort(key=lambda x: x["value"], reverse=True)
    df = pd.DataFrame(rows)
    chart = (
        alt.Chart(df)
        .mark_bar()
        .encode(
            x=alt.X("value:Q", title="Count", axis=alt.Axis(format="d")),
            y=alt.Y("label:N", sort="-x", title=None),
            tooltip=["label:N", alt.Tooltip("value:Q", format=".0f")],
        )
        .properties(title=title, height=height)
    )
    st.altair_chart(chart, width="stretch")


def render_hero(participants: List[str]) -> None:
    st.markdown(
        """
<style>
.report-hero {
  padding: 2.2rem 1.4rem;
  border-radius: 14px;
  background: linear-gradient(120deg, #eaf4fb 0%, #f8fbff 55%, #eef7f1 100%);
  border: 1px solid rgba(14, 30, 60, 0.08);
}
.report-hero h2 {
  margin: 0;
  font-size: 2.2rem;
  line-height: 1.1;
}
.report-hero p {
  margin-top: .6rem;
  margin-bottom: 0;
}
.block-container { max-width: 1120px !important; }
</style>
""",
        unsafe_allow_html=True,
    )
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


def render_intro_text() -> None:
    st.markdown(
        """
This page is a trace of the event: a narrative built from signals, images, and shared responses.
It maps how individual points of view enter the room, meet one another, and evolve through time.
"""
    )


def render_media_block() -> None:
    left, right = st.columns([1.2, 1])
    with left:
        img_path = Path("assets/img1.png")
        if img_path.exists():
            st.image(str(img_path), width="stretch", caption="Cryosphere trace")
        else:
            st.info("Image placeholder")
    with right:
        st.markdown("**Atmosphere**")
        st.components.v1.html(SOUNDCLOUD_EMBED, height=140)
        st.caption("Sound placeholder for the event soundscape.")


def render_event_summary(payload: Dict[str, Any], session_id: str) -> None:
    st.markdown("### What happened")
    c1, c2, c3 = st.columns(3)
    c1.metric("Participants", int(payload.get("participant_count", 0)))
    c2.metric("Responses", int(payload.get("response_count", 0)))
    c3.metric("Active in last 24h", count_active_users(24 * 60, session_id=session_id))


def _find_question(payload: Dict[str, Any], item_id: str) -> Dict[str, Any]:
    for q in payload.get("questions", []):
        if str(q.get("item_id") or "") == item_id:
            return q
    return {}


def _question_prompt(item_id: str) -> str:
    q = QUESTION_BY_ID.get(item_id)
    return str(getattr(q, "prompt", item_id))


def render_data_blocks(
    payload: Dict[str, Any],
    rows: List[Dict[str, Any]],
    player_page_id: str,
    device_id: str,
) -> None:
    st.markdown("### First signals")
    arr = _find_question(payload, "ARRIVAL_EMOTION")
    org = _find_question(payload, "ORGANISATION_SIGNAL")
    arr_row = _latest_player_response(
        rows, "ARRIVAL_EMOTION", player_page_id, device_id
    )
    personal_arr = _normalise_choices(arr_row.get("value_json")) if arr_row else []

    c1, c2 = st.columns(2)
    with c1:
        st.caption(f"Question: {_question_prompt('ARRIVAL_EMOTION')}")
        _render_emotion_field(
            "Arrival emotions",
            arr.get("counts", {}),
            personal_choices=personal_arr,
        )
    with c2:
        st.caption(f"Question: {_question_prompt('ORGANISATION_SIGNAL')}")
        _render_signal_glyphs(org.get("counts", {}))


def render_narrative(payload: Dict[str, Any]) -> None:
    st.markdown("### Narrative from data")
    signal = _find_question(payload, "ORGANISATION_SIGNAL")
    counts = signal.get("counts", {})
    yes = int(counts.get("yes", 0))
    maybe = int(counts.get("maybe", 0))
    no = int(counts.get("no", 0))
    st.markdown(
        f"""
The room currently leans toward continuation (`yes: {yes}`), with a meaningful conditional layer (`maybe: {maybe}`)
and a smaller refusal signal (`no: {no}`).

Taken together, this suggests willingness to continue while keeping conditions explicit.
"""
    )


def render_personalised_blocks(
    payload: Dict[str, Any],
    rows: List[Dict[str, Any]],
    player_page_id: str,
    device_id: str,
) -> None:
    st.markdown("### Your relation to the room")
    if not (player_page_id or device_id):
        st.caption("Log in to see your personaliSed comparison with the room.")
        return

    # Block 1: organisation signal
    org = _find_question(payload, "ORGANISATION_SIGNAL")
    org_row = _latest_player_response(
        rows, "ORGANISATION_SIGNAL", player_page_id, device_id
    )
    with st.container(border=True):
        st.markdown("**Collective entry signal**")
        st.caption(f"Question: {_question_prompt('ORGANISATION_SIGNAL')}")
        if org_row:
            choice = _extract_choice(org_row.get("value_json"))
            answer = str(choice or org_row.get("value_label") or "").strip()
            if not answer:
                answer = "No answer captured"
            st.markdown(f"**Your answer:** {answer}")
            bucket_counts = {
                "yes": int(org.get("counts", {}).get("yes", 0)),
                "maybe": int(org.get("counts", {}).get("maybe", 0)),
                "no": int(org.get("counts", {}).get("no", 0)),
            }
            bucket = "unknown"
            txt = answer.lower()
            if "yes" in txt:
                bucket = "yes"
            elif "maybe" in txt:
                bucket = "maybe"
            elif "no" in txt:
                bucket = "no"
            st.caption(_comparison_label_single(bucket, bucket_counts))
        else:
            st.caption("No personal response found for this question yet.")

    # Block 2: arrival emotion
    arrival = _find_question(payload, "ARRIVAL_EMOTION")
    arrival_row = _latest_player_response(
        rows, "ARRIVAL_EMOTION", player_page_id, device_id
    )
    with st.container(border=True):
        st.markdown("**Arrival emotions**")
        st.caption(f"Question: {_question_prompt('ARRIVAL_EMOTION')}")
        if arrival_row:
            choice = _extract_choice(arrival_row.get("value_json"))
            if isinstance(choice, list):
                answer_list = [str(x) for x in choice if str(x).strip()]
                st.markdown(f"**Your answer:** {', '.join(answer_list)}")
                st.caption(
                    _comparison_label_multi(answer_list, arrival.get("counts", {}))
                )
            else:
                answer = str(choice or arrival_row.get("value_label") or "")
                st.markdown(f"**Your answer:** {answer}")
                st.caption(_comparison_label_single(answer, arrival.get("counts", {})))
        else:
            st.caption("No personal response found for this question yet.")

    # Block 3: collaboration readiness
    collab = _find_question(payload, "COLLABORATION_READINESS")
    collab_row = _latest_player_response(
        rows, "COLLABORATION_READINESS", player_page_id, device_id
    )
    with st.container(border=True):
        st.markdown("**Collaboration readiness**")
        st.caption(f"Question: {_question_prompt('COLLABORATION_READINESS')}")
        if collab_row:
            choice = _extract_choice(collab_row.get("value_json"))
            answer = str(choice or collab_row.get("value_label") or "")
            st.markdown(f"**Your answer:** {answer}")
            st.caption(_comparison_label_single(answer, collab.get("counts", {})))
        else:
            st.caption("No personal response found for this question yet.")


def render_deepening(
    payload: Dict[str, Any],
    rows: List[Dict[str, Any]],
    player_page_id: str,
    device_id: str,
) -> None:
    st.markdown("### Deepening")
    env_q = _find_question(payload, "ENVIRONMENT_CHANGE_EMOTION")
    soc_q = _find_question(payload, "SOCIETAL_CHANGE_EMOTION")
    env_row = _latest_player_response(
        rows, "ENVIRONMENT_CHANGE_EMOTION", player_page_id, device_id
    )
    soc_row = _latest_player_response(
        rows, "SOCIETAL_CHANGE_EMOTION", player_page_id, device_id
    )
    personal_env = _normalise_choices(env_row.get("value_json")) if env_row else []
    personal_soc = _normalise_choices(soc_row.get("value_json")) if soc_row else []
    c1, c2 = st.columns(2)
    with c1:
        st.caption(f"Question: {_question_prompt('ENVIRONMENT_CHANGE_EMOTION')}")
        _render_emotion_field(
            "Emotion toward environmental change",
            env_q.get("counts", {}),
            personal_choices=personal_env,
            height=240,
        )
    with c2:
        st.caption(f"Question: {_question_prompt('SOCIETAL_CHANGE_EMOTION')}")
        _render_emotion_field(
            "Emotion toward societal change",
            soc_q.get("counts", {}),
            personal_choices=personal_soc,
            height=240,
        )


def render_gallery() -> None:
    st.markdown("### Images and traces")
    img_path = Path("assets/img1.png")
    cols = st.columns(3)
    for col in cols:
        with col:
            if img_path.exists():
                st.image(str(img_path), width="stretch")
            else:
                st.info("Gallery image placeholder")


def render_closing() -> None:
    st.markdown("### Closing reflection")
    st.markdown(
        """
Signals do not end when a page closes.
They remain as trajectories that can be revisited, discussed, and extended collectively.
"""
    )


def render_call_to_action() -> None:
    st.markdown("### Continue")
    st.markdown(
        """
Continue the experiment.
Bring this format to another place.
Invite new signals.
"""
    )
    c1, c2, c3 = st.columns(3)
    c1.button("Start a new session", disabled=True, width="stretch")
    c2.page_link("pages/01_Login.py", label="Join the platform", icon="🔑")
    c3.button("Contact organisers", disabled=True, width="stretch")


def main() -> None:
    set_page()
    apply_theme()

    heading("Report · Trace")

    sessions = _sessions_cache()
    session_map = {_slugify(s.get("session_code") or ""): s for s in sessions}
    default_slug = "global-session"
    options = list(session_map.keys()) or [default_slug]
    selected_slug = st.selectbox(
        "Session",
        options=options,
        index=options.index(default_slug) if default_slug in options else 0,
        format_func=lambda slug: (session_map.get(slug) or {}).get(
            "session_code", slug
        ),
    )
    session_obj = session_map.get(selected_slug) or {}

    payload = get_overview_payload(selected_slug)
    _, rows = fetch_session_responses(selected_slug)
    player_page_id = str(st.session_state.get("player_page_id") or "")
    device_id = str(st.session_state.get("anon_token") or "")

    participants = _participants_snapshot()
    render_hero(participants)
    render_intro_text()
    render_media_block()
    render_event_summary(payload, str(session_obj.get("id") or ""))
    render_data_blocks(payload, rows, player_page_id, device_id)
    render_narrative(payload)
    render_personalised_blocks(
        payload,
        rows,
        player_page_id,
        device_id,
    )
    render_deepening(payload, rows, player_page_id, device_id)
    render_gallery()
    render_closing()
    render_call_to_action()

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
