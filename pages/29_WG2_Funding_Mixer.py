from __future__ import annotations

import hashlib
import html
import uuid
from typing import Any

import streamlit as st
from philoui.survey import CustomStreamlitSurvey

from conference.context import get_conference_repo
from conference.events import UN_WG2_DEBUG_SESSION_CODE, UN_WG2_SESSION_CODE
from conference.test_sessions import debug_session_access_enabled
from conference.wg2_funding_mixer import (
    CHANNELS,
    DEFAULT_SESSION_CODE,
    INTERACTION_ID,
    TEXT_ID,
    aggregate_allocations,
    allocation_payload,
    backup_json,
    constrain_allocation,
    default_allocation,
    latest_participant_rows,
)
from infra.event_logger import list_logged_events, log_event


RECOVERY_LOG_PAGE = "un_wg2_recovery"


def _test_requested() -> bool:
    value = str(st.query_params.get("test", "") or "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _session_code() -> str:
    if _test_requested():
        return UN_WG2_DEBUG_SESSION_CODE
    return str(st.query_params.get("session", DEFAULT_SESSION_CODE) or "").strip()


def _test_entry_allowed(repo: Any) -> bool:
    production = repo.resolve_session(session_code=UN_WG2_SESSION_CODE)
    production_id = str((production or {}).get("id") or "")
    if not production_id:
        return False
    events = list_logged_events(
        page=RECOVERY_LOG_PAGE,
        session_id=production_id,
        limit=500,
    )
    return debug_session_access_enabled(events)


def _event_metadata(session_code: str) -> dict[str, Any]:
    test_mode = session_code == UN_WG2_DEBUG_SESSION_CODE
    return {
        "session_code": session_code,
        "test_mode": test_mode,
        "response_scope": "debug_session" if test_mode else "event_session",
        "data_classification": "debug" if test_mode else "production",
    }


def _results_requested() -> bool:
    value = str(st.query_params.get("results", "") or "").strip().lower()
    return value in {"1", "true", "yes", "results"}


def _phase() -> str:
    value = str(st.query_params.get("phase", "before_discussion") or "").strip()
    return (
        value
        if value in {"before_discussion", "after_discussion"}
        else "before_discussion"
    )


def _apply_page_style() -> None:
    st.set_page_config(page_title="WG2 · Funding mixer", layout="wide")
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"], [data-testid="stHeader"], footer {display:none !important;}
        .stApp {background:#eef3f0;color:#17231f;}
        .block-container {max-width:1180px;padding:1.2rem 1.4rem 2rem;}
        h1 {font-size:clamp(1.55rem,5vw,2.8rem)!important;letter-spacing:-.045em;margin:.1rem 0!important;}
        .mixer-kicker {font:700 .72rem/1.2 ui-monospace,monospace;letter-spacing:.14em;color:#466158;}
        .mixer-copy {max-width:760px;color:#465852;font-size:.95rem;line-height:1.55;margin:.65rem 0 1rem;}
        .mixer-total {font:750 clamp(2rem,8vw,4.6rem)/1 ui-monospace,monospace;letter-spacing:-.08em;margin:.35rem 0 .85rem;}
        .mixer-total span {font-size:.2em;letter-spacing:.025em;color:#60736c;}
        .channel-label {min-height:3.5rem;text-align:center;font:700 .68rem/1.25 ui-monospace,monospace;letter-spacing:.035em;display:flex;align-items:end;justify-content:center;}
        .channel-context {min-height:5.8rem;text-align:center;color:#60736c;font-size:.7rem;line-height:1.35;padding:.45rem .15rem;}
        div[data-testid="stVerticalBlockBorderWrapper"] {background:rgba(238,243,240,.5)!important;}
        iframe[title="streamlit_vertical_slider.vertical_slider"] {background:#eef3f0!important;}
        .st-key-emoji_key input {font:600 1.55rem/1.2 ui-monospace,monospace!important;letter-spacing:.08em;}
        div[data-testid="stSlider"] {min-height:19rem;display:flex;justify-content:center;}
        div[data-testid="stSlider"] > div {width:17rem;transform:rotate(-90deg);margin:7rem -6.1rem 0;}
        div[data-testid="stSlider"] label {display:none;}
        div[data-testid="stMetric"] {background:rgba(255,255,255,.48);border:1px solid rgba(23,35,31,.13);padding:.55rem;border-radius:.3rem;}
        .trace {height:.28rem;background:#0f6d6225;margin:.12rem 0;position:relative;}
        .trace > i {display:block;height:100%;background:#0f6d6266;}
        @media(max-width:650px){
          .block-container{padding:.8rem .7rem 1.5rem;}
          div[data-testid="stSlider"]{min-height:14rem;}
          div[data-testid="stSlider"] > div{width:12rem;margin:4.7rem -4.1rem 0;}
          .channel-label{font-size:.55rem;}
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _resolve_context(repo: Any, session_code: str) -> tuple[dict[str, Any] | None, str]:
    if not session_code:
        return None, "This interaction needs an explicit session code."
    if repo is None or not repo.is_ready():
        return None, "The response store is unavailable."
    session = repo.resolve_session(session_code=session_code)
    if not session:
        return None, f"Session {session_code!r} was not found."
    session_id = str(session.get("id") or "").strip()
    if not session_id:
        return None, "The resolved session has no durable id."
    status = str(session.get("status") or "").strip().lower()
    if status in {"closed", "archived"}:
        return None, f"This meeting is {status}; allocations are read-only."
    return session, ""


def _authenticate(repo: Any, session: dict[str, Any]) -> tuple[str, str] | None:
    player_id = str(st.session_state.get("player_page_id") or "").strip()
    access_key = str(st.session_state.get("player_access_key") or "").strip()
    if player_id and access_key:
        return player_id, access_key
    st.markdown(
        '<div class="mixer-kicker">WG2 · FUNDING MIXER</div>', unsafe_allow_html=True
    )
    st.title("Open your mixer")
    st.markdown("Paste your four-emoji WG2 access key.")
    with st.container(key="emoji_key"):
        raw_key = st.text_input(
            "Emoji access key",
            placeholder="Enter your four-emoji access key",
            help="Your key connects this allocation to your anonymous WG2 profile.",
        )
    if not st.button("Open mixer", type="primary", use_container_width=True):
        recovery, onboarding = st.columns(2)
        recovery.page_link("pages/01_Login.py", label="I forgot my access key")
        onboarding.page_link("pages/Splash.py", label="I don’t have an access key")
        return None
    access_key, error = repo.resolve_access_key(raw_key)
    if not access_key:
        st.error(error or "This access key could not be resolved.")
        return None
    player = repo.notion_repo.get_player_by_access_key(access_key)
    if not player:
        st.error("No participant was found for this access key.")
        return None
    player_id = str(player.get("id") or "").strip()
    if not player_id:
        st.error("The participant record has no durable id.")
        return None
    st.session_state["player_page_id"] = player_id
    st.session_state["player_access_key"] = access_key
    st.rerun()
    return None


def _all_rows(repo: Any, session_id: str) -> list[dict[str, Any]]:
    return repo.interaction_repo().get_responses(session_id)


@st.fragment(run_every=5)
def _render_results(repo: Any, session: dict[str, Any]) -> None:
    rows = _all_rows(repo, str(session["id"]))
    aggregate = aggregate_allocations(rows)
    st.markdown(
        '<div class="mixer-kicker">LIVE COLLECTIVE VIEW</div>', unsafe_allow_html=True
    )
    st.title("WG2 — collective allocation")
    st.caption(
        f"{aggregate['submission_count']} anonymous allocation(s) · latest revision per participant"
    )
    if not aggregate["submission_count"]:
        st.info(
            "No allocations have been committed yet. This view refreshes every 5 seconds."
        )
    else:
        columns = st.columns(len(CHANNELS))
        for column, channel in zip(columns, CHANNELS):
            stats = aggregate["channels"][channel.key]
            with column:
                st.metric(channel.label, f"{stats['median']:g}", help="Median tokens")
                st.caption(f"range {stats['min']:g}–{stats['max']:g}")
        st.markdown("#### Anonymous traces")
        for trace in aggregate["traces"]:
            cols = st.columns(len(CHANNELS))
            for col, channel in zip(cols, CHANNELS):
                value = int(trace[channel.key])
                col.markdown(
                    f'<div class="trace" title="{html.escape(channel.label)}: {value}"><i style="width:{value}%"></i></div>',
                    unsafe_allow_html=True,
                )
    st.markdown("### Why does our collective allocation look like this?")
    st.caption("What bottleneck would money not fix?")


def _participant_revision(rows: list[dict[str, Any]], participant_hash: str) -> int:
    revisions = [
        int(row["mixer"].get("revision") or 0)
        for row in latest_participant_rows(rows)
        if str(row["mixer"].get("participant_hash") or "") == participant_hash
    ]
    return max(revisions, default=0) + 1


def _changed_channel(
    allocation: dict[str, int], raw_values: dict[str, int]
) -> str | None:
    changed = [key for key in allocation if raw_values[key] != allocation[key]]
    if not changed:
        return None
    return max(changed, key=lambda key: abs(raw_values[key] - allocation[key]))


def _confetti() -> None:
    colours = ("#0f6d62", "#ff4b4b", "#f2c14e", "#7cb7a5", "#17231f")
    pieces = "".join(
        (
            '<i style="--x:{x}vw;--drift:{drift}px;--delay:{delay}ms;'
            '--duration:{duration}ms;--turn:{turn}deg;--colour:{colour}"></i>'
        ).format(
            x=(index * 37) % 101,
            drift=((index * 53) % 180) - 90,
            delay=(index * 41) % 650,
            duration=1800 + (index * 67) % 1500,
            turn=360 + (index * 29) % 720,
            colour=colours[index % len(colours)],
        )
        for index in range(90)
    )
    st.markdown(
        f"""
        <style>
        .wg2-confetti {{position:fixed;inset:0;z-index:999999;pointer-events:none;overflow:hidden;}}
        .wg2-confetti i {{
          position:absolute;left:var(--x);top:-18px;width:9px;height:15px;
          background:var(--colour);opacity:0;
          animation:wg2-confetti-fall var(--duration) cubic-bezier(.18,.72,.3,1)
                    var(--delay) 1 both;
        }}
        .wg2-confetti i:nth-child(3n) {{width:7px;height:7px;border-radius:50%;}}
        .wg2-confetti i:nth-child(4n) {{width:12px;height:5px;}}
        @keyframes wg2-confetti-fall {{
          0% {{opacity:0;transform:translate3d(0,-4vh,0) rotate(0);}}
          8% {{opacity:1;}}
          100% {{opacity:0;transform:translate3d(var(--drift),105vh,0) rotate(var(--turn));}}
        }}
        @media (prefers-reduced-motion:reduce) {{.wg2-confetti {{display:none;}}}}
        </style>
        <div class="wg2-confetti" aria-hidden="true">{pieces}</div>
        """,
        unsafe_allow_html=True,
    )


def _latest_for_participant(
    rows: list[dict[str, Any]], participant_hash: str
) -> dict[str, Any] | None:
    matches = [
        row
        for row in latest_participant_rows(rows)
        if str(row["mixer"].get("participant_hash") or "") == participant_hash
    ]
    return matches[0] if matches else None


def _log_backup_download(
    session_id: str, player_id: str, device_id: str, revision: int
) -> None:
    log_event(
        module="iceicebaby.wg2_funding_mixer",
        event_type="allocation_backup_downloaded",
        page="wg2_funding_mixer",
        player_id=player_id,
        session_id=session_id,
        item_id=INTERACTION_ID,
        device_id=device_id,
        metadata={**_event_metadata(_session_code()), "revision": revision},
    )


def _render_mixer(
    repo: Any, session: dict[str, Any], player_id: str, access_key: str
) -> None:
    session_id = str(session["id"])
    participant_hash = hashlib.sha256(access_key.encode("utf-8")).hexdigest()
    rows = _all_rows(repo, session_id)
    latest = _latest_for_participant(rows, participant_hash)
    if "wg2_mixer_v2_allocation" not in st.session_state:
        st.session_state["wg2_mixer_v2_allocation"] = (
            dict(latest["allocation"]) if latest else default_allocation()
        )
        st.session_state["wg2_mixer_v2_other_text"] = (
            str(latest["mixer"].get("other_text") or "") if latest else ""
        )
        st.session_state["wg2_mixer_v2_editing"] = latest is None
        if latest:
            st.session_state["wg2_mixer_v2_committed"] = {
                "revision": int(latest["mixer"].get("revision") or 1),
                "payload": dict(latest["mixer"]),
            }
    allocation = st.session_state["wg2_mixer_v2_allocation"]
    generation = int(st.session_state.setdefault("wg2_mixer_v2_generation", 0))
    survey = CustomStreamlitSurvey(label=f"wg2_funding_mixer_v2_{generation}")
    total = sum(allocation.values())
    remaining = 100 - total
    if st.session_state.pop("wg2_mixer_v2_renormalised", False):
        st.toast("Renormalised to 100 tokens — the other channels contracted.")
    st.markdown(
        '<div class="mixer-kicker">WG2 · 100 SEED TOKENS</div>', unsafe_allow_html=True
    )
    st.title("Funding mixer")
    st.markdown(
        '<div class="mixer-copy">WG2 receives 100 seed tokens. How would you allocate them across the capabilities we need to create?<br>'
        "Raise one channel and the others must contract: scarcity is part of the question.<br>"
        "There is no correct allocation — we are interested in the collective pattern.</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="mixer-total">{total} <span>/ 100 allocated · {remaining} remaining</span></div>',
        unsafe_allow_html=True,
    )
    columns = st.columns(len(CHANNELS), gap="small")
    raw_values: dict[str, int] = {}
    for column, channel in zip(columns, CHANNELS):
        with column:
            st.markdown(
                f'<div class="channel-label">{html.escape(channel.label)}</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<div class="channel-context">{html.escape(channel.description)}</div>',
                unsafe_allow_html=True,
            )
            value = survey.equaliser(
                label=channel.label,
                id=f"wg2_mixer_{channel.key}",
                height=260,
                key=f"wg2_mixer_v2_{channel.key}_{generation}",
                default_value=int(allocation[channel.key]),
                step=1,
                min_value=0,
                max_value=100,
                track_color="#ccd8d2",
                slider_color="#0f6d62",
                thumb_color="#ff4b4b",
                thumb_shape="circle",
                value_always_visible=True,
            )
            raw_values[channel.key] = int(
                value if value is not None else allocation[channel.key]
            )

    changed_key = _changed_channel(allocation, raw_values)
    if changed_key:
        raw_total = sum(raw_values.values())
        constrained = constrain_allocation(
            allocation, changed_key, raw_values[changed_key]
        )
        st.session_state["wg2_mixer_v2_allocation"] = constrained
        if raw_total > 100 and sum(constrained.values()) == 100:
            st.session_state["wg2_mixer_v2_renormalised"] = True
        st.session_state["wg2_mixer_v2_generation"] = generation + 1
        st.session_state["wg2_mixer_v2_editing"] = True
        st.rerun()

    other_text = ""
    if allocation["other"] > 0:
        other_text = st.text_input(
            "What would you fund?",
            value=str(st.session_state.get("wg2_mixer_v2_other_text") or ""),
            placeholder="Something missing from the channels above?",
        )
        st.session_state["wg2_mixer_v2_other_text"] = other_text

    committed = st.session_state.get("wg2_mixer_v2_committed")
    editing = bool(st.session_state.get("wg2_mixer_v2_editing", True))
    if committed:
        revision = int(committed["revision"])
        if st.session_state.get("wg2_mixer_v2_celebrated") != revision:
            _confetti()
            st.session_state["wg2_mixer_v2_celebrated"] = revision
        st.success(f"Allocation committed · revision {revision}")
        committed_payload = committed.get("payload")
        if isinstance(committed_payload, dict):
            device_id = str(
                st.session_state.setdefault("wg2_mixer_device_id", uuid.uuid4().hex)
            )
            st.download_button(
                "Download backup copy",
                data=backup_json(committed_payload),
                file_name=(
                    f"wg2-funding-mix-{_session_code()}-revision-{revision}.json"
                ),
                mime="application/json",
                use_container_width=True,
                on_click=_log_backup_download,
                args=(session_id, player_id, device_id, revision),
            )
        if not editing:
            if st.button("Revise allocation", type="primary", use_container_width=True):
                st.session_state["wg2_mixer_v2_editing"] = True
                st.rerun()
            return

    action_label = "COMMIT REVISION" if committed else "COMMIT ALLOCATION"
    if st.button(
        action_label,
        type="primary",
        use_container_width=True,
        disabled=total != 100,
        help="Allocate all 100 tokens before committing." if total != 100 else None,
    ):
        revision = _participant_revision(rows, participant_hash)
        payload = allocation_payload(
            allocation,
            session_code=_session_code(),
            revision=revision,
            participant_hash=participant_hash,
            phase=_phase(),
            other_text=other_text,
            test_mode=_session_code() == UN_WG2_DEBUG_SESSION_CODE,
        )
        device_id = str(
            st.session_state.setdefault("wg2_mixer_device_id", uuid.uuid4().hex)
        )
        try:
            repo.interaction_repo().save_response(
                session_id=session_id,
                player_id=player_id,
                question_id=INTERACTION_ID,
                value=payload,
                text_id=TEXT_ID,
                device_id=device_id,
            )
            log_event(
                module="iceicebaby.wg2_funding_mixer",
                event_type="allocation_committed",
                page="wg2_funding_mixer",
                player_id=player_id,
                session_id=session_id,
                item_id=INTERACTION_ID,
                device_id=device_id,
                metadata={
                    **_event_metadata(_session_code()),
                    "revision": revision,
                    "phase": _phase(),
                },
            )
        except Exception as exc:
            log_event(
                module="iceicebaby.wg2_funding_mixer",
                event_type="allocation_write_failed",
                page="wg2_funding_mixer",
                player_id=player_id,
                session_id=session_id,
                item_id=INTERACTION_ID,
                status="error",
                metadata={
                    **_event_metadata(_session_code()),
                    "error": str(exc),
                },
                level="ERROR",
            )
            st.error(f"The allocation could not be saved: {exc}")
            return
        st.session_state["wg2_mixer_v2_committed"] = {
            "revision": revision,
            "payload": payload,
        }
        st.session_state["wg2_mixer_v2_editing"] = False
        st.rerun()


def main() -> None:
    _apply_page_style()
    repo = get_conference_repo()
    if _test_requested() and (
        not repo or not repo.is_ready() or not _test_entry_allowed(repo)
    ):
        st.error(
            "WG2 test entry is closed. Ask a host to enable it from WG2 Host → "
            "Member recovery."
        )
        return
    session, error = _resolve_context(repo, _session_code())
    if error:
        st.error(error)
        return
    assert session is not None
    if _session_code() == UN_WG2_DEBUG_SESSION_CODE:
        st.warning(
            "TEST MODE · This allocation is stored in the separate WG2 debug session "
            "and is excluded from production results."
        )
    log_event(
        module="iceicebaby.wg2_funding_mixer",
        event_type="page_view",
        page="wg2_funding_mixer_results"
        if _results_requested()
        else "wg2_funding_mixer",
        session_id=str(session["id"]),
        metadata={
            **_event_metadata(_session_code()),
            "mode": "results" if _results_requested() else "participant",
        },
    )
    if _results_requested():
        _render_results(repo, session)
        return
    authenticated = _authenticate(repo, session)
    if authenticated:
        _render_mixer(repo, session, *authenticated)


if __name__ == "__main__":
    main()
