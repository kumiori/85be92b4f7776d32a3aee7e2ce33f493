from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from infra.app_context import get_authenticator, get_notion_repo
from infra.app_state import (
    ensure_auth,
    ensure_session_context,
    ensure_session_state,
    remember_access,
    require_login,
)
from ui import apply_theme, heading, microcopy, set_page, sidebar_debug_state

ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"
ABSTRACT_MD = ASSETS_DIR / "abstract_decision.txt"
FORM_DETAILS_MD = ASSETS_DIR / "form_details.md"

DECISION_CHOICES = ["👍 keep", "👎 drop", "✏️ change"]

FORM_FIELDS = [
    {"id": "title", "label": "Title of the event", "type": "select"},
    {
        "id": "description",
        "label": "Description (key focus, objectives, outcomes, contribution)",
        "type": "textarea",
    },
    {
        "id": "agenda",
        "label": "Tentative agenda (speakers, structure, interaction)",
        "type": "textarea",
    },
    {
        "id": "objectives",
        "label": "Main objectives and contribution",
        "type": "textarea",
    },
    {
        "id": "format",
        "label": "Event format",
        "type": "select",
        "options": ["Online", "In person", "Hybrid"],
    },
    {
        "id": "preferred_day",
        "label": "Preferred day",
        "type": "select",
        "options": ["19 March", "20 March", "No preference", "Other"],
    },
    {
        "id": "language",
        "label": "Language",
        "type": "select",
        "options": [
            "English",
            "French",
            "Arabic",
            "Chinese",
            "Russian",
            "Spanish",
            "Other",
        ],
    },
    {
        "id": "translation",
        "label": "Need live translation?",
        "type": "select",
        "options": ["Yes", "No"],
    },
    {
        "id": "participants",
        "label": "Expected number of participants and audience",
        "type": "text",
    },
    {
        "id": "requirements",
        "label": "Special technical or logistical requirements",
        "type": "text",
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
    microcopy("Review the application form and choose an abstract version.")

    if not repo or not session_id or not player_page_id:
        st.error("Missing session or player context.")
        return

    abstracts = {}
    if ABSTRACT_MD.exists():
        raw = ABSTRACT_MD.read_text(encoding="utf-8")
        blocks = raw.split("###")
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            lines = block.splitlines()
            title = lines[0].strip().lower().replace("version", "version").replace(" ", "_")
            body = "\n".join(lines[1:]).strip()
            if title.startswith("version_"):
                abstracts[title] = body

    st.subheader("Abstract versions")
    abstract_keys = ["version_0", "version_a", "version_b"]
    available_keys = [k for k in abstract_keys if k in abstracts] or abstract_keys
    abstract_choice = st.selectbox(
        "Select the abstract version",
        options=available_keys,
        format_func=lambda k: k.replace("_", " ").title(),
        key="abstract-choice",
    )
    st.markdown(abstracts.get(abstract_choice, "Missing abstract text."))

    with st.form("decision-form"):

        st.subheader("Application form fields")
        field_payload = {}
        title_options = _parse_title_options()
        for field in FORM_FIELDS:
            st.markdown(f"**{field['label']}**")
            decision = st.radio(
                "Decision",
                DECISION_CHOICES,
                key=f"decision-{field['id']}",
                horizontal=True,
                index=2,
            )
            value = ""
            if field["type"] == "text":
                value = st.text_input("Value", key=f"value-{field['id']}")
            elif field["type"] == "textarea":
                value = st.text_area("Value", key=f"value-{field['id']}", height=120)
            elif field["type"] == "select":
                if field["id"] == "title":
                    value = st.selectbox(
                        "Value",
                        title_options + ["Add another…"],
                        key=f"value-{field['id']}",
                    )
                    if value == "Add another…":
                        value = st.text_input(
                            "Custom title", key=f"custom-{field['id']}"
                        )
                else:
                    value = st.selectbox(
                        "Value", field["options"], key=f"value-{field['id']}"
                    )
            change_note = ""
            if decision == "✏️ change":
                change_note = st.text_area(
                    "Proposed change", key=f"change-{field['id']}", height=80
                )
            field_payload[field["id"]] = {
                "decision": decision,
                "value": value,
                "change_note": change_note,
            }

        st.subheader("Journey A → B")
        journey_choice = st.selectbox(
            "Pick a journey pair",
            options=[j["id"] for j in JOURNEY_OPTIONS],
            format_func=lambda jid: jid.replace("_", " ").title(),
        )
        journey = next(
            (j for j in JOURNEY_OPTIONS if j["id"] == journey_choice), JOURNEY_OPTIONS[0]
        )
        st.markdown(f"**A:** {journey['A']}")
        st.markdown(f"**B:** {journey['B']}")

        submitted = st.form_submit_button("Submit decisions")

    if submitted:
        chosen = st.session_state.get("abstract-choice", abstract_choice)
        payload = {
            "abstract_version": chosen,
            "abstract_text": abstracts.get(chosen, ""),
            "fields": field_payload,
            "journey": {"id": journey_choice, "A": journey["A"], "B": journey["B"]},
        }
        repo.create_decision(
            session_id=session_id,
            player_id=player_page_id,
            decision_type="micro_decision",
            payload=json.dumps(payload),
        )
        st.success("Thanks, your input is saved.")


if __name__ == "__main__":
    main()
