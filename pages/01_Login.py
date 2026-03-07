from __future__ import annotations

import hashlib
from datetime import datetime

import streamlit as st

from infra.app_context import (
    get_active_session,
    get_authenticator,
    get_auth_runtime_config,
    get_notion_repo,
)
from infra.app_state import (
    ensure_auth,
    ensure_session_state,
    remember_access,
    set_session,
    mint_anon_token,
)
from infra.cryosphere_cracks import CRYOSPHERE_CRACKS, cryosphere_crack_points
from infra.credentials_pdf import build_credentials_pdf
from models.catalog import QUESTION_BY_ID
from repositories.base import InteractionRepository
from repositories.interaction_repo import (
    NotionInteractionRepository,
    SQLiteInteractionRepository,
)

from ui import (
    apply_theme,
    heading,
    microcopy,
    set_page,
    sidebar_debug_state,
    cracks_globe_block,
    display_centered_prompt,
    render_info_block,
)

PRE_SIGNAL_ID = "ORGANISATION_SIGNAL"
PRE_SIGNAL_TEXT_ID = "pre_lobby_signal_v0"
PRE_SIGNAL_SCORE = {
    "Yes — continue": 1,
    "Maybe — depending upon conditions": 0,
    "No — stop here": -1,
}


def _build_interaction_repository(notion_repo) -> tuple[InteractionRepository, str]:
    sqlite_repo = SQLiteInteractionRepository("data/interaction_v0.sqlite")
    notion_cfg = st.secrets.get("notion", {})
    db_id = (
        notion_cfg.get("ice_interaction_responses_db_id")
        or notion_cfg.get("interaction_responses_db_id")
        or notion_cfg.get("interaction_responses")
        or ""
    )
    if not notion_repo or not db_id:
        return sqlite_repo, "sqlite"
    try:
        return NotionInteractionRepository(notion_repo, str(db_id)), "notion"
    except Exception:
        return sqlite_repo, "sqlite"


def main() -> None:
    set_page()
    apply_theme()
    ensure_session_state()
    sidebar_debug_state()

    heading("Ice Ice Baby · Cryosphere Signals")
    st.markdown(
        """
### Developed for the World Day for Glaciers at UNESCO, within the Decade of Action for Cryospheric Sciences (2024-2035).
"""
    )
    st.markdown(
        """
Room XXX, 4pm, March 19, 2026. Organised by: ______, ______, ______, ______, and ______.
"""
    )
    display_centered_prompt("A moment before deciding.")
    st.markdown(
        """
### Transitions in nature rarely announce themselves clearly. Signals accumulate. Tensions build, energy stores. Then systems shift. 
#### Understanding these transitions is a scientific challenge. Acting through them is a collective one.
        """
    )

    locations_md = []
    for category, entries in CRYOSPHERE_CRACKS.items():
        regions = ", ".join(entry["Region"] for entry in entries)
        locations_md.append(f"- **{category}**: {regions}")

    render_info_block(
        left_title="Decision signals",
        left_subtitle="collective experiment",
        right_content="\n".join(
            [
                "To act in a decade of irreversible transitions,",
                "we need new languages and new coordination experiments.",
                "",
                "New problems require new forms of interaction.",
                "",
                "This platform explores how groups perceive signals,",
                "exchange interpretations, and form decisions together.",
                "",
                "What happens next depends on the signals we generate here.",
                "",
            ]
        ),
    )
    display_centered_prompt("The first signal is yours to send.")
    repo = get_notion_repo()
    authenticator = get_authenticator(repo)
    auth_cfg = get_auth_runtime_config()
    key_hash_prefix = hashlib.sha256(
        auth_cfg["cookie_key"].encode("utf-8")
    ).hexdigest()[:12]
    raw_token = authenticator.cookie_controller.get_cookie()
    cookie_username = raw_token.get("username") if isinstance(raw_token, dict) else None
    cookie_player_exists = bool(
        repo.get_player_by_id(cookie_username) if repo and cookie_username else False
    )
    session_auth_status = st.session_state.get("authentication_status")
    if not raw_token:
        auth_diagnosis = "No auth cookie detected."
    elif not cookie_username:
        auth_diagnosis = "Cookie present but missing username payload."
    elif not cookie_player_exists:
        auth_diagnosis = "Cookie present, but username is not found in player records."
    elif session_auth_status is True:
        auth_diagnosis = "Cookie present and mapped to an active authenticated session."
    else:
        auth_diagnosis = (
            "Cookie present and user exists, but this run is not authenticated yet. "
            "This can happen after an invalid login attempt or stale session state."
        )

    with st.sidebar.expander("Debug: Auth cookie", expanded=False):
        st.code(
            (
                f"cookie_source={auth_cfg['source']}\n"
                f"cookie_name={auth_cfg['cookie_name']}\n"
                f"cookie_expiry_days={auth_cfg['cookie_expiry_days']}\n"
                f"cookie_key_len={len(auth_cfg['cookie_key'])}\n"
                f"cookie_key_sha256_prefix={key_hash_prefix}\n"
                f"default_session_code={auth_cfg['default_session_code']}\n"
                f"cookie_present={bool(raw_token)}\n"
                f"cookie_username={cookie_username or '<missing>'}\n"
                f"cookie_user_exists_in_repo={cookie_player_exists}\n"
                f"session_authentication_status={session_auth_status}"
            )
        )
        st.caption(f"Diagnosis: {auth_diagnosis}")

    current_auth = bool(st.session_state.get("authentication_status"))
    if current_auth:
        name = st.session_state.get("name")
        authentication_status = st.session_state.get("authentication_status")
    else:
        name, authentication_status, _ = ensure_auth(
            authenticator,
            callback=remember_access,
            key="access-key-login",
            location="main",
        )

    open_mint = bool(st.session_state.pop("focus_mint_token", False))

    if authentication_status:
        display_name = name or st.session_state.get("player_name") or "collaborator"
        st.success(f"Authentication status: LOGGED IN")
        st.success(f"Hello {display_name}. You are already logged in.")
        st.info(
            "Your session cookie is active. You can continue directly to the lobby."
        )
        session = get_active_session(repo)
        if session:
            set_session(session.get("id", ""), session.get("session_code", "Session"))
        session_id = st.session_state.get("session_id", "")
        player_page_id = st.session_state.get("player_page_id", "")
        signal_repo, signal_backend = _build_interaction_repository(repo)
        signal_done_key = f"pre_signal_submitted:{session_id}:{player_page_id}"
        pre_signal_submitted = bool(st.session_state.get(signal_done_key, False))
        salt = st.secrets.get("anon_salt", "iceicebaby")
        anon_token = mint_anon_token(
            st.session_state.get("session_id", ""),
            st.session_state.get("player_access_key", ""),
            salt,
        )
        st.session_state["anon_token"] = anon_token

        pre_signal_question = QUESTION_BY_ID.get(PRE_SIGNAL_ID)
        if pre_signal_question:
            st.markdown("---")
            st.subheader(pre_signal_question.prompt)
            st.caption(pre_signal_question.short_description)
            with st.form("pre-lobby-signal-form"):
                choice = st.radio(
                    "Collective signal",
                    pre_signal_question.options or [],
                    key="pre-signal-choice",
                    label_visibility="collapsed",
                )
                maybe_comment = ""
                if choice == "Maybe — depending upon conditions":
                    maybe_comment = st.text_input(
                        "Condition or comment",
                        placeholder=pre_signal_question.placeholder or "Your condition or comment",
                        key="pre-signal-comment",
                    )
                send_signal = st.form_submit_button(
                    "Send collective signal",
                    type="primary",
                    use_container_width=True,
                    disabled=pre_signal_submitted,
                )
            if send_signal:
                if not session_id:
                    st.error("No active session found. Please refresh and try again.")
                else:
                    score = PRE_SIGNAL_SCORE.get(choice)
                    value_payload = {
                        "choice": choice,
                        "score": score,
                        "comment": maybe_comment.strip(),
                        "type": "pre_signal",
                        "depth": 0,
                    }
                    signal_repo.save_response(
                        session_id=session_id,
                        player_id=player_page_id or None,
                        question_id=PRE_SIGNAL_ID,
                        value=value_payload,
                        text_id=PRE_SIGNAL_TEXT_ID,
                        device_id=anon_token,
                    )
                    st.session_state[signal_done_key] = True
                    pre_signal_submitted = True
                    st.success(f"Signal recorded ({signal_backend}).")
        if st.button(
            "Enter lobby",
            type="secondary",
            use_container_width=True,
            disabled=not pre_signal_submitted,
        ):
            st.switch_page("pages/02_Home.py")
        if not pre_signal_submitted:
            st.warning("Submit the collective entry signal above before entering the lobby.")
        authenticator.logout(button_name="Logout", location="main")
    elif authentication_status is False:
        st.error("Authentication status: INVALID KEY")
        st.error("Key invalid or ambiguous. Try full hash or more emoji.")
    else:
        st.info("Authentication status: NOT LOGGED IN")
        st.caption("Use the access key form above to log in.")


if __name__ == "__main__":
    main()
