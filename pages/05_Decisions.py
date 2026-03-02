from __future__ import annotations

import json
import math
import random
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import streamlit as st

from infra.app_context import get_authenticator, get_notion_repo
from infra.app_state import (
    ensure_auth,
    ensure_session_context,
    ensure_session_state,
    remember_access,
    require_login,
)
from ui import (
    apply_theme,
    display_centered_prompt,
    heading,
    microcopy,
    set_page,
    sidebar_debug_state,
    render_info_block,
)

ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"
ABSTRACT_MD = ASSETS_DIR / "abstract_decision.txt"
FORM_DETAILS_MD = ASSETS_DIR / "form_details.md"
EXPECTED_OUTCOMES_MD = ASSETS_DIR / "expected_outcomes.md"

DECISION_CHOICES = ["👍 keep", "👎 drop", "✏️ change"]
OPTION_CHOICES = ["👍 keep", "👎 drop", "✏️ change", "✨ new one"]

FORM_FIELDS = [
    {"id": "title", "label": "Title of the event", "type": "select", "mandatory": True},
    # {
    #     "id": "description",
    #     "label": "Description (key focus, objectives, outcomes, contribution)",
    #     "type": "textarea",
    #     "mandatory": True,
    # },
    {
        "id": "agenda",
        "label": "Tentative agenda (speakers, structure, interaction)",
        "type": "textarea",
        "mandatory": True,
    },
    {
        "id": "expected_outcomes",
        "label": "Expected outcomes",
        "type": "option_list",
        "mandatory": False,
    },
    {
        "id": "preferred_day",
        "label": "Preferred day",
        "type": "select",
        "options": ["19 March", "20 March", "No preference", "Other"],
        "mandatory": False,
    },
    {
        "id": "language",
        "label": "Language",
        "type": "select",
        "options": [
            "English",
            "French",
            "Other",
        ],
        "mandatory": False,
    },
    {
        "id": "translation",
        "label": "Need live translation?",
        "type": "select",
        "options": ["Yes", "No"],
        "mandatory": False,
    },
    {
        "id": "participants",
        "label": "Expected number of participants and audience",
        "type": "slider",
        "mandatory": False,
    },
    {
        "id": "requirements",
        "label": "Special technical or logistical requirements",
        "type": "text",
        "mandatory": False,
    },
]

JOURNEY_OPTIONS = [
    {
        "id": "journey_1",
        "A": "Shit is hitting the fan. I know glaciers are melting. I feel concerned but powerless.",
        "B": "I experienced irreversibility. I took decisions with others. I see where agency could be rebuilt.",
    },
    {
        "id": "journey_2",
        "A": "I read the science, but I don’t know where to place it in my life.",
        "B": "I found a collective practice that makes the science actionable.",
    },
    {
        "id": "journey_3",
        "A": "I feel numb. The scale is too big.",
        "B": "I can name one lever and take one step with others.",
    },
]

ENERGY_STATES = {
    "Low energy": [
        "Detached",
        "Overwhelmed",
        "Cynical",
        "Passive",
        "Technically informed but emotionally distant",
    ],
    "Mid energy": [
        "Curious",
        "Concerned",
        "Ambivalent",
        "Intellectually engaged",
        "Morally conflicted",
    ],
    "High energy": [
        "Alarmed",
        "Motivated",
        "Indignant",
        "Ready to act",
        "Seeking coordination",
    ],
}


def _parse_title_options() -> list[str]:
    if not FORM_DETAILS_MD.exists():
        return []
    raw = FORM_DETAILS_MD.read_text(encoding="utf-8")
    options: list[str] = []
    in_section = False
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("## "):
            in_section = line.lower().startswith("## title options")
            continue
        if in_section and line.startswith("- "):
            options.append(line[2:].strip())
    return options


def _parse_expected_outcomes() -> list[str]:
    if not EXPECTED_OUTCOMES_MD.exists():
        return []
    raw = EXPECTED_OUTCOMES_MD.read_text(encoding="utf-8")
    options: list[str] = []
    in_section = False
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("## "):
            in_section = line.lower().startswith("## expected outcomes")
            continue
        if in_section and line.startswith("- "):
            options.append(line[2:].strip())
    return options


def _parse_abstract_versions(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    raw = path.read_text(encoding="utf-8")
    versions: dict[str, list[str]] = {}
    current_key = ""
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped.startswith("###"):
            key = stripped.replace("#", "").strip().lower().replace(" ", "_")
            if key.startswith("version"):
                current_key = key
                versions[current_key] = []
            continue
        if current_key:
            versions[current_key].append(line)
    return {k: "\n".join(v).strip() for k, v in versions.items() if v}


def _render_option_list(
    item_key: str, label: str, options: list[str]
) -> dict[str, dict]:
    st.markdown(f"##### {label}")
    payload: dict[str, dict] = {}
    for idx, option in enumerate(options):
        action = st.radio(
            f"Action for {label} #{idx + 1} - {option}",
            OPTION_CHOICES,
            key=f"{item_key}-action-{idx}",
            horizontal=True,
        )
        proposal = ""
        if action == "✏️ change":
            proposal = st.text_input(
                "I propose",
                value=option,
                key=f"{item_key}-change-{idx}",
            )
        elif action == "✨ new one":
            proposal = st.text_input(
                "I propose",
                value="",
                key=f"{item_key}-new-{idx}",
            )
        payload[f"{item_key}_{idx}"] = {
            "decision": action,
            "other_options": option,
            "i_propose": proposal,
        }
    return payload


def _render_option_sequence(
    item_key: str, label: str, options: list[str], answered_item_ids: set[str]
) -> tuple[dict[str, dict], bool]:
    idx_key = f"{item_key}-idx"
    payload_key = f"{item_key}-payload"
    st.session_state.setdefault(idx_key, 0)
    st.session_state.setdefault(payload_key, {})
    idx = st.session_state[idx_key]
    payload = st.session_state[payload_key]
    unresolved = [
        (i, opt)
        for i, opt in enumerate(options)
        if f"{item_key}_{i}" not in answered_item_ids
    ]

    st.markdown(f"##### {label}")
    if not unresolved:
        st.success(f"{label} already completed.")
        return payload, True
    if idx >= len(unresolved):
        st.success(f"{label} confirmed in this run.")
        return payload, True

    real_idx, option = unresolved[idx]
    action = st.radio(
        f"Action for {label} #{real_idx + 1} - {option}",
        OPTION_CHOICES,
        key=f"{item_key}-action-{real_idx}",
        horizontal=True,
    )
    proposal = ""
    if action == "✏️ change":
        proposal = st.text_input(
            "I propose",
            value=option,
            key=f"{item_key}-change-{real_idx}",
        )
    elif action == "✨ new one":
        proposal = st.text_input(
            "I propose",
            value="",
            key=f"{item_key}-new-{real_idx}",
        )

    if st.button("Confirm and continue", key=f"{item_key}-confirm-{real_idx}"):
        payload[f"{item_key}_{real_idx}"] = {
            "decision": action,
            "other_options": option,
            "i_propose": proposal,
        }
        st.session_state[payload_key] = payload
        st.session_state[idx_key] = idx + 1
        st.rerun()
    return payload, False


def _coverage_from_depth(depth: int) -> float:
    return 0.1 + (depth - 1) * 0.8 / 9


def _load_answered_item_ids(
    repo, session_id: str, player_page_id: str, run_id: str
) -> set[str]:
    answered: set[str] = set()
    decisions = repo.list_decisions(session_id)
    for decision in decisions:
        players = decision.get("player_id") or []
        if player_page_id not in players:
            continue
        if decision.get("type") not in {
            "decision_item_compact_v0",
            "decision_item_diff_v0",
            "decision_item_new_v0",
        }:
            continue
        try:
            payload = json.loads(decision.get("payload") or "{}")
        except Exception:
            payload = {}
        if payload.get("run_id") != run_id:
            continue
        item_id = payload.get("item_id")
        if item_id:
            answered.add(str(item_id))
    return answered


def _sample_items(
    player_id: str, session_id: str, depth: int, sample_revision: int
) -> tuple[list[str], float, str]:
    coverage = _coverage_from_depth(depth)
    mandatory = [f for f in FORM_FIELDS if f.get("mandatory")]
    optional = [f for f in FORM_FIELDS if not f.get("mandatory")]
    optional_count = len(optional)
    target = max(0, min(optional_count, math.ceil(optional_count * coverage)))
    seed_input = f"{player_id}:{session_id}:decision_form_v0:{sample_revision}"
    seed = str(abs(hash(seed_input)))
    rng = random.Random(seed)
    optional_ids = [f["id"] for f in optional]
    picked_optional = rng.sample(optional_ids, target) if optional_ids else []
    mandatory_ids = [f["id"] for f in mandatory]
    include_ids = set(mandatory_ids + picked_optional)
    ordered = [f["id"] for f in FORM_FIELDS if f["id"] in include_ids]
    return ordered, coverage, seed


with open("assets/street.css", "r") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    st.write(f.read())


def main() -> None:
    set_page()
    apply_theme()
    ensure_session_state()
    repo = get_notion_repo()
    authenticator = get_authenticator(repo)
    ensure_auth(authenticator, callback=remember_access, key="decisions-login")
    ensure_session_context(repo)
    require_login()
    sidebar_debug_state()

    if st.session_state.get("authentication_status"):
        authenticator.logout(button_name="Logout", location="sidebar")
    session_id = st.session_state.get("session_id")
    player_page_id = st.session_state.get("player_page_id")

    heading("Decision Tool")
    microcopy("Collective Review of the application form.")

    _content = """
Participants interact with a digital interface that adapts to their chosen level of engagement. A depth slider determines how many decision points they are invited to address, from a minimal engagement to a deeper editorial involvement.

At each step, they respond to statements, propose changes, or submit questions. All actions are time-stamped and anonymised where appropriate. The system visualises aggregate signals—friction, convergence, hesitation—without exposing individual positions.

Questions enter a queue and are traced through how they are addressed, reframed, or parked.
    """
    st.divider()
    render_info_block(
        left_title="_¿" + "HOW".title() + "_",
        left_subtitle="does this work?",
        right_content=_content,
    )

    # rather than in the illusion of endless delay.
    if not repo or not session_id or not player_page_id:
        st.error("Missing session or player context.")
        return

    if "decision_run_id" not in st.session_state:
        st.session_state["decision_run_id"] = str(uuid4())
    run_id = st.session_state.get("decision_run_id", "")
    answered_item_ids = _load_answered_item_ids(repo, session_id, player_page_id, run_id)
    st.session_state.setdefault("live_answered_item_ids", set())
    live_answered = set(st.session_state.get("live_answered_item_ids", set()))
    answered_all = answered_item_ids | live_answered
    with st.sidebar.expander("Collected answers", expanded=True):
        if answered_all:
            st.markdown("### Already answered items")
            for item_id in sorted(answered_all):
                st.markdown(f"- `{item_id}`")
        else:
            st.caption("No answered items yet.")

    abstracts = _parse_abstract_versions(ABSTRACT_MD)

    display_centered_prompt("subject to change.")

    st.subheader("Abstract")
    abstract_choice = (
        "version_x"
        if "version_x" in abstracts
        else (next(iter(abstracts.keys())) if abstracts else "version_x")
    )
    st.markdown(f"### {abstract_choice.replace('_', ' ').title()}")
    abstract_text = abstracts.get(abstract_choice, "Missing abstract text.")
    for paragraph in abstract_text.split("\n\n"):
        st.markdown(f"### {paragraph}")
    word_count = len(abstract_text.split())
    char_count = len(abstract_text)
    st.markdown(f"### Words: {word_count} · Characters: {char_count}")
    abstract_action = st.radio(
        "Abstract action",
        ["👍 keep", "✏️ change"],
        key="abstract-action",
        horizontal=True,
    )
    abstract_proposal = ""
    if abstract_action == "✏️ change":
        abstract_proposal = st.text_area(
            "I propose",
            value=abstract_text,
            key="abstract-proposal",
            height=180,
        )

    # st.markdown(abstracts.get(abstract_choice, "Missing abstract text."))

    display_centered_prompt("subject to change.")

    st.subheader("Depth")
    if "decision_depth" not in st.session_state:
        st.session_state["decision_depth"] = 5
    if "sample_revision" not in st.session_state:
        st.session_state["sample_revision"] = 0
    if "depth_locked" not in st.session_state:
        st.session_state["depth_locked"] = False
    if "sampling_logged_revision" not in st.session_state:
        st.session_state["sampling_logged_revision"] = None

    depth = st.slider(
        "Effort level",
        min_value=1,
        max_value=10,
        value=st.session_state["decision_depth"],
        disabled=st.session_state["depth_locked"],
    )
    if not st.session_state["depth_locked"]:
        st.session_state["decision_depth"] = depth
    if st.button("Start new run", use_container_width=True):
        st.session_state["decision_run_id"] = str(uuid4())
        st.session_state["sample_revision"] += 1
        st.session_state["depth_locked"] = False
        st.session_state["item_ids_shown"] = []
        st.session_state["sampling_logged_revision"] = None
        st.session_state["live_answered_item_ids"] = set()
        st.session_state["title_option-idx"] = 0
        st.session_state["title_option-payload"] = {}
        st.session_state["expected_outcome-idx"] = 0
        st.session_state["expected_outcome-payload"] = {}
        st.rerun()

    item_ids_shown, coverage, seed = _sample_items(
        player_page_id,
        session_id,
        st.session_state["decision_depth"],
        st.session_state["sample_revision"],
    )
    st.session_state["item_ids_shown"] = item_ids_shown
    st.caption(f"Coverage: {int(coverage * 100)}% of form items")

    st.subheader("Application form fields")
    field_payload = {}
    title_options = _parse_title_options()
    expected_outcomes = _parse_expected_outcomes()

    title_payload, title_done = _render_option_sequence(
        "title_option", "Title options", title_options, answered_all
    )
    field_payload.update(title_payload)
    if not title_done:
        st.info("Confirm this title option to proceed.")
        st.stop()

    expected_payload, expected_done = _render_option_sequence(
        "expected_outcome", "Expected outcomes", expected_outcomes, answered_all
    )
    field_payload.update(expected_payload)
    if not expected_done:
        st.info("Confirm this expected outcome to proceed.")
        st.stop()

    shown_fields = [
        f
        for f in FORM_FIELDS
        if f["id"] in item_ids_shown and f["id"] not in {"title", "expected_outcomes"}
    ]
    answered = sum(1 for f in shown_fields if f["id"] in answered_all)
    for field in shown_fields:
        if field["id"] in answered_all:
            st.caption(f"{field['label']} already completed.")
            continue
        st.markdown(f"**{field['label']}**")
        decision = st.radio(
            "Decision",
            DECISION_CHOICES,
            key=f"decision-{field['id']}",
            horizontal=True,
            index=2,
        )
        other_options = ""
        if field["type"] == "text":
            other_options = st.text_input("Other options", key=f"value-{field['id']}")
        elif field["type"] == "textarea":
            other_options = st.text_area(
                "Other options", key=f"value-{field['id']}", height=120
            )
        elif field["type"] == "select":
            other_options = st.selectbox(
                "Other options", field["options"], key=f"value-{field['id']}"
            )
        i_propose = ""
        if decision == "✏️ change":
            i_propose = st.text_area(
                "I propose", key=f"change-{field['id']}", height=80
            )
        is_answered = (
            bool(other_options)
            if decision != "✏️ change"
            else bool(i_propose or other_options)
        )
        if is_answered:
            answered += 1
        field_payload[field["id"]] = {
            "decision": decision,
            "other_options": other_options,
            "i_propose": i_propose,
        }
        if st.button(f"Confirm {field['label']}", key=f"confirm-{field['id']}"):
            if decision == "✏️ change":
                if not i_propose:
                    st.warning("Add a proposal before confirming.")
                else:
                    repo.create_decision(
                        session_id=session_id,
                        player_id=player_page_id,
                        decision_type="decision_item_diff_v0",
                        payload=json.dumps(
                            {
                                "item_id": field["id"],
                                "decision": "change",
                                "i_propose": i_propose,
                                "other_options": other_options,
                                "run_id": run_id,
                                "sample_revision": st.session_state["sample_revision"],
                            }
                        ),
                    )
                    live_answered.add(field["id"])
                    st.session_state["live_answered_item_ids"] = live_answered
                    st.rerun()
            else:
                repo.create_decision(
                    session_id=session_id,
                    player_id=player_page_id,
                    decision_type="decision_item_compact_v0",
                    payload=json.dumps(
                        {
                            "item_id": field["id"],
                            "decision": "keep" if decision == "👍 keep" else "drop",
                            "other_options": other_options,
                            "run_id": run_id,
                            "sample_revision": st.session_state["sample_revision"],
                        }
                    ),
                )
                live_answered.add(field["id"])
                st.session_state["live_answered_item_ids"] = live_answered
                st.rerun()

    shown_count = len(shown_fields)
    if shown_count:
        st.progress(answered / shown_count)
        st.caption(f"Answered {answered} / {shown_count}")

    st.subheader("Journey A → B")
    journey_choice = st.selectbox(
        "Pick a journey pair",
        options=[j["id"] for j in JOURNEY_OPTIONS],
        format_func=lambda jid: jid.replace("_", " ").title(),
    )
    journey = next(
        (j for j in JOURNEY_OPTIONS if j["id"] == journey_choice),
        JOURNEY_OPTIONS[0],
    )
    st.markdown(f"**A:** {journey['A']}")
    st.markdown(f"**B:** {journey['B']}")
    st.markdown("**Energy states**")
    energy_start = st.pills(
        "Start state",
        ENERGY_STATES["Low energy"]
        + ENERGY_STATES["Mid energy"]
        + ENERGY_STATES["High energy"],
        selection_mode="multi",
    )
    custom_start = st.text_input("Add a custom start state (optional)")
    if custom_start:
        energy_start = list(energy_start) + [custom_start]
    energy_end = st.pills(
        "End state",
        ENERGY_STATES["Low energy"]
        + ENERGY_STATES["Mid energy"]
        + ENERGY_STATES["High energy"],
        selection_mode="multi",
    )
    custom_end = st.text_input("Add a custom end state (optional)")
    if custom_end:
        energy_end = list(energy_end) + [custom_end]

    submitted = st.button("Submit decisions", type="tertiary", use_container_width=True)

    if submitted:
        st.session_state["depth_locked"] = True
        if (
            st.session_state.get("sampling_logged_revision")
            != st.session_state["sample_revision"]
        ):
            sampling_payload = {
                "session_id": session_id,
                "player_id": player_page_id,
                "run_id": run_id,
                "depth": st.session_state["decision_depth"],
                "coverage": coverage,
                "seed": seed,
                "sample_revision": st.session_state["sample_revision"],
                "item_ids_shown": item_ids_shown,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            repo.create_decision(
                session_id=session_id,
                player_id=player_page_id,
                decision_type="decision_sampling_v0",
                payload=json.dumps(sampling_payload),
            )
            st.session_state["sampling_logged_revision"] = st.session_state[
                "sample_revision"
            ]
        for item_id, payload_item in field_payload.items():
            if item_id in answered_all:
                continue
            decision = payload_item["decision"]
            if decision == "✏️ change":
                if not payload_item["i_propose"]:
                    continue
                item_payload = {
                    "item_id": item_id,
                    "decision": "change",
                    "i_propose": payload_item["i_propose"],
                    "other_options": payload_item["other_options"],
                    "run_id": run_id,
                    "sample_revision": st.session_state["sample_revision"],
                }
                repo.create_decision(
                    session_id=session_id,
                    player_id=player_page_id,
                    decision_type="decision_item_diff_v0",
                    payload=json.dumps(item_payload),
                )
            elif decision == "✨ new one":
                if not payload_item["i_propose"]:
                    continue
                repo.create_decision(
                    session_id=session_id,
                    player_id=player_page_id,
                    decision_type="decision_item_new_v0",
                    payload=json.dumps(
                        {
                            "item_id": item_id,
                            "decision": "new_one",
                            "i_propose": payload_item["i_propose"],
                            "run_id": run_id,
                            "sample_revision": st.session_state["sample_revision"],
                        }
                    ),
                )
            else:
                compact_payload = {
                    "item_id": item_id,
                    "decision": "keep" if decision == "👍 keep" else "drop",
                    "other_options": payload_item["other_options"],
                    "run_id": run_id,
                    "sample_revision": st.session_state["sample_revision"],
                }
                repo.create_decision(
                    session_id=session_id,
                    player_id=player_page_id,
                    decision_type="decision_item_compact_v0",
                    payload=json.dumps(compact_payload),
                )
        if abstract_action == "✏️ change" and abstract_proposal:
            repo.create_decision(
                session_id=session_id,
                player_id=player_page_id,
                decision_type="decision_abstract_diff_v0",
                payload=json.dumps(
                    {
                        "item_id": "abstract",
                        "decision": "change",
                        "i_propose": abstract_proposal,
                        "run_id": run_id,
                        "sample_revision": st.session_state["sample_revision"],
                    }
                ),
            )
        else:
            repo.create_decision(
                session_id=session_id,
                player_id=player_page_id,
                decision_type="decision_abstract_compact_v0",
                payload=json.dumps(
                    {
                        "item_id": "abstract",
                        "decision": "keep",
                        "run_id": run_id,
                        "sample_revision": st.session_state["sample_revision"],
                    }
                ),
            )
        journey_payload = {
            "id": journey_choice,
            "A": journey["A"],
            "B": journey["B"],
            "energy_start": energy_start,
            "energy_end": energy_end,
            "run_id": run_id,
        }
        repo.create_decision(
            session_id=session_id,
            player_id=player_page_id,
            decision_type="decision_journey_v0",
            payload=json.dumps(journey_payload),
        )
        st.success("Thanks, your input is saved.")


if __name__ == "__main__":
    main()
