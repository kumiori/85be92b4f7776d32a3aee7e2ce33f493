from __future__ import annotations

from dataclasses import dataclass
from typing import Any


YOUNG_SESSION_CODE = "pisa-conference-session"
COMPLEXITY_SESSION_CODE = "petnica_2026"
DALAMBERTIENNES_SESSION_CODE = "dalembertiennes_2026"
UN_WG2_SESSION_CODE = "un_wg2_core_2026"
UN_WG2_DEBUG_SESSION_CODE = "un_wg2_debug_2026"
PREDICTION_SESSION_CODE = "prediction_2026"
PREDICTION_DEBUG_SESSION_CODE = "prediction_debug_2026"
UNESCO_SESSION_CODE = "global-session"
YOUNG_TEXT_ID = "pisa_session_v2"
COMPLEXITY_TEXT_ID = "petnica_2026"
LEGACY_COMPLEXITY_TEXT_ID = "complexity_session_v2"
DALAMBERTIENNES_TEXT_ID = "dalembertiennes_v1"
LEGACY_DALAMBERTIENNES_TEXT_ID = "dalembertiennes_v0"
UN_WG2_TEXT_ID = "un_wg2_v1"
COMPLEXITY_EVENT_CODE = COMPLEXITY_SESSION_CODE
COMPLEXITY_EVENT_LABEL = "COMPLEXITY"
COMPLEXITY_EVENT_LOCATION = "Petnica"
DALAMBERTIENNES_EVENT_CODE = DALAMBERTIENNES_SESSION_CODE
DALAMBERTIENNES_EVENT_LABEL = "D'Alembertiennes"
DALAMBERTIENNES_EVENT_LOCATION = "D'Alembert Lab"
UN_WG2_EVENT_CODE = UN_WG2_SESSION_CODE
UN_WG2_EVENT_LABEL = "Working Group 2 — Module 1: Visibility"
UN_WG2_EVENT_LOCATION = "UN Cryosphere Decade"
UN_WG2_DEBUG_EVENT_SLUG = "un_wg2_visibility_debug"

YOUNG_OVERVIEW_PAGE = "pages/17_Young_Overview.py"
COMPLEXITY_ENTRY_PAGE = "pages/15_Pisa_Meeting.py"
COMPLEXITY_HOST_PAGE = "pages/16_Pisa_Meeting_Host.py"
COMPLEXITY_OVERVIEW_PAGE = "pages/20_Complexity_Overview.py"
DALAMBERTIENNES_ENTRY_PAGE = "pages/21_Dalembertiennes.py"
DALAMBERTIENNES_HOST_PAGE = "pages/23_Dalembertiennes_Host.py"
DALAMBERTIENNES_OVERVIEW_PAGE = "pages/22_Dalembertiennes_Overview.py"
UN_WG2_ENTRY_PAGE = "pages/25_UN_WG2_Icebreaker.py"
UN_WG2_OVERVIEW_PAGE = "pages/26_UN_WG2_Overview.py"
UN_WG2_HOST_PAGE = "pages/27_UN_WG2_Host.py"


@dataclass(frozen=True)
class EventIdentityPolicy:
    identified: bool = False
    required_fields: tuple[str, ...] = ()
    optional_fields: tuple[str, ...] = ()
    recovery_mode: str = "access_key"
    semantic_fields: tuple[tuple[str, str], ...] = ()

    def semantic_type_for(self, field: str) -> str:
        return dict(self.semantic_fields).get(str(field or "").strip(), "text")


@dataclass(frozen=True)
class EventResultConfig:
    kind: str = "generic"
    visible_when: str = "submitted"


@dataclass(frozen=True)
class NavigationItem:
    title: str
    page: str
    url_path: str
    icon: str


@dataclass(frozen=True)
class ConferenceEventConfig:
    slug: str
    session_code: str
    label: str
    location: str
    text_ids: tuple[str, ...]
    primary_text_id: str
    question_set_id: str
    schema_id: str
    questionnaire_page: str
    overview_page: str
    host_page: str
    response_scope: str = "event_specific"
    aliases: tuple[str, ...] = ()
    test_mode: bool = False
    test_session_code: str = ""
    title: str = ""
    subtitle: str = ""
    description: str = ""
    place: str = ""
    dates: str = ""
    intro_title: str = ""
    intro_body: str = ""
    closing_title: str = ""
    closing_body: str = ""
    identity_policy: EventIdentityPolicy = EventIdentityPolicy()
    result_config: EventResultConfig = EventResultConfig()


_EVENT_CONFIGS = (
    ConferenceEventConfig(
        slug="prediction",
        session_code=PREDICTION_SESSION_CODE,
        label="PREDICTION",
        location="Udine",
        text_ids=("prediction_v0",),
        primary_text_id="prediction_v0",
        question_set_id="prediction_v0",
        schema_id="questionnaire_v2",
        questionnaire_page="pages/33_Event.py",
        overview_page="pages/34_Event_Overview.py",
        host_page="pages/35_Event_Host.py",
        response_scope="event_session",
        aliases=("prediction", PREDICTION_SESSION_CODE),
        test_session_code=PREDICTION_DEBUG_SESSION_CODE,
        title="CISM-EUROMECH Advanced Course",
        subtitle="Damage and Fracture Mechanics of Fluid-Infiltrated Geomaterials",
        description="A shared scientific reflection on prediction in damage and fracture.",
        place="Udine",
        dates="7–11 September 2026",
        intro_title="Prediction",
        intro_body="Share your perspective as the course develops.",
        closing_title="Responses recorded",
        closing_body="Keep your access key so you can return to your answers.",
        identity_policy=EventIdentityPolicy(
            identified=True,
            required_fields=("name", "email"),
            optional_fields=("institution", "base_location"),
            recovery_mode="host_assisted",
            semantic_fields=(("base_location", "location"),),
        ),
        result_config=EventResultConfig(kind="generic", visible_when="submitted"),
    ),
    ConferenceEventConfig(
        slug="prediction_debug",
        session_code=PREDICTION_DEBUG_SESSION_CODE,
        label="TEST · PREDICTION",
        location="Udine",
        text_ids=("prediction_v0",),
        primary_text_id="prediction_v0",
        question_set_id="prediction_v0",
        schema_id="questionnaire_v2",
        questionnaire_page="pages/33_Event.py",
        overview_page="pages/34_Event_Overview.py",
        host_page="pages/35_Event_Host.py",
        response_scope="debug_session",
        aliases=("prediction_debug", PREDICTION_DEBUG_SESSION_CODE),
        test_mode=True,
        title="TEST · CISM-EUROMECH Advanced Course",
        subtitle="Damage and Fracture Mechanics of Fluid-Infiltrated Geomaterials",
        description="Test copy of the course questionnaire.",
        place="Udine",
        dates="7–11 September 2026",
        intro_title="Prediction",
        intro_body="Share your perspective as the course develops.",
        closing_title="Test responses recorded",
        closing_body="This test remains separate from course responses.",
        identity_policy=EventIdentityPolicy(
            identified=True,
            required_fields=("name", "email"),
            optional_fields=("institution", "base_location"),
            recovery_mode="host_assisted",
            semantic_fields=(("base_location", "location"),),
        ),
        result_config=EventResultConfig(kind="generic", visible_when="submitted"),
    ),
    ConferenceEventConfig(
        slug="complexity",
        session_code=COMPLEXITY_SESSION_CODE,
        label=COMPLEXITY_EVENT_LABEL,
        location=COMPLEXITY_EVENT_LOCATION,
        text_ids=(COMPLEXITY_TEXT_ID, LEGACY_COMPLEXITY_TEXT_ID),
        primary_text_id=COMPLEXITY_TEXT_ID,
        question_set_id="complexity_v2",
        schema_id="complexity_v2",
        questionnaire_page=COMPLEXITY_ENTRY_PAGE,
        overview_page=COMPLEXITY_OVERVIEW_PAGE,
        host_page=COMPLEXITY_HOST_PAGE,
        aliases=("complexity", "petnica", COMPLEXITY_SESSION_CODE),
    ),
    ConferenceEventConfig(
        slug="dalembertiennes",
        session_code=DALAMBERTIENNES_SESSION_CODE,
        label=DALAMBERTIENNES_EVENT_LABEL,
        location=DALAMBERTIENNES_EVENT_LOCATION,
        text_ids=(DALAMBERTIENNES_TEXT_ID, LEGACY_DALAMBERTIENNES_TEXT_ID),
        primary_text_id=DALAMBERTIENNES_TEXT_ID,
        question_set_id=DALAMBERTIENNES_TEXT_ID,
        schema_id=DALAMBERTIENNES_TEXT_ID,
        questionnaire_page=DALAMBERTIENNES_ENTRY_PAGE,
        overview_page=DALAMBERTIENNES_OVERVIEW_PAGE,
        host_page=DALAMBERTIENNES_HOST_PAGE,
        aliases=("dalembertiennes", DALAMBERTIENNES_SESSION_CODE),
    ),
    ConferenceEventConfig(
        slug="un_wg2_visibility",
        session_code=UN_WG2_SESSION_CODE,
        label=UN_WG2_EVENT_LABEL,
        location=UN_WG2_EVENT_LOCATION,
        text_ids=(UN_WG2_TEXT_ID,),
        primary_text_id=UN_WG2_TEXT_ID,
        question_set_id=UN_WG2_TEXT_ID,
        schema_id="questionnaire_v2",
        questionnaire_page=UN_WG2_ENTRY_PAGE,
        overview_page=UN_WG2_OVERVIEW_PAGE,
        host_page=UN_WG2_HOST_PAGE,
        response_scope="event_session",
        aliases=(
            "un_wg2_visibility",
            "un-wg2",
            "un-wg2-icebreaker",
            UN_WG2_SESSION_CODE,
        ),
    ),
    ConferenceEventConfig(
        slug=UN_WG2_DEBUG_EVENT_SLUG,
        session_code=UN_WG2_DEBUG_SESSION_CODE,
        label=f"TEST · {UN_WG2_EVENT_LABEL}",
        location=UN_WG2_EVENT_LOCATION,
        text_ids=(UN_WG2_TEXT_ID,),
        primary_text_id=UN_WG2_TEXT_ID,
        question_set_id=UN_WG2_TEXT_ID,
        schema_id="questionnaire_v2",
        questionnaire_page=UN_WG2_ENTRY_PAGE,
        overview_page=UN_WG2_OVERVIEW_PAGE,
        host_page=UN_WG2_HOST_PAGE,
        response_scope="debug_session",
        aliases=(
            UN_WG2_DEBUG_EVENT_SLUG,
            "un-wg2-debug",
            UN_WG2_DEBUG_SESSION_CODE,
        ),
        test_mode=True,
    ),
)
_EVENT_CONFIG_BY_CODE = {item.session_code: item for item in _EVENT_CONFIGS}
_EVENT_CONFIG_BY_ALIAS = {
    alias.lower(): item for item in _EVENT_CONFIGS for alias in item.aliases
}


def _normalized_code(value: Any) -> str:
    return str(value or "").strip()


def _query_param_value(name: str) -> str:
    try:
        import streamlit as st

        return str(st.query_params.get(name, "") or "").strip()
    except Exception:
        return ""


def _requested_event_token() -> str:
    return _query_param_value("event") or _query_param_value("session")


def _canonical_session_code(value: Any) -> str:
    token = _normalized_code(value)
    if not token:
        return ""
    config = _EVENT_CONFIG_BY_ALIAS.get(token.lower())
    return config.session_code if config else token


def event_config_for_session_code(session_code: str) -> ConferenceEventConfig | None:
    return _EVENT_CONFIG_BY_CODE.get(_canonical_session_code(session_code))


def event_config_for_slug(slug: str) -> ConferenceEventConfig | None:
    token = _normalized_code(slug).lower()
    return next((item for item in _EVENT_CONFIGS if item.slug.lower() == token), None)


def event_config_for_request(
    event_slug: str, *, test: bool | str = False
) -> ConferenceEventConfig | None:
    """Resolve the persisted boundary before a participant flow reads or writes."""
    config = event_config_for_slug(event_slug)
    wants_test = test is True or str(test or "").strip().lower() in {"1", "true", "yes"}
    if not config or not wants_test or config.test_mode:
        return config
    if not config.test_session_code:
        return None
    return event_config_for_session_code(config.test_session_code)


def navigation_families() -> dict[str, tuple[NavigationItem, ...]]:
    """Current participant-facing session families, ready for a future index."""
    return {
        "Complexity": (
            NavigationItem("B-Complex 2026", COMPLEXITY_ENTRY_PAGE, "complexity", ":material/groups:"),
            NavigationItem("Overview", COMPLEXITY_OVERVIEW_PAGE, "complexity-overview", ":material/insights:"),
            NavigationItem("Host", COMPLEXITY_HOST_PAGE, "pisa-meeting-host", ":material/admin_panel_settings:"),
        ),
        "Young": (
            NavigationItem("Pisa 2026", "pages/19_Pisa_Experiment.py", "pisa", ":material/history:"),
            NavigationItem("Overview", YOUNG_OVERVIEW_PAGE, "young-overview", ":material/insights:"),
            NavigationItem("Opening", "pages/18_Pisa_Opening.py", "pisa-opening", ":material/auto_stories:"),
        ),
        "Prediction": (
            NavigationItem("CISM Udine 2026", "pages/33_Event.py", "event", ":material/science:"),
            NavigationItem("Prediction Overview", "pages/34_Event_Overview.py", "event-overview", ":material/insights:"),
            NavigationItem("Prediction Host", "pages/35_Event_Host.py", "event-host", ":material/admin_panel_settings:"),
        ),
        "D'Alembertiennes": (
            NavigationItem("Climate", DALAMBERTIENNES_ENTRY_PAGE, "dalembertiennes", ":material/science:"),
            NavigationItem("Overview", DALAMBERTIENNES_OVERVIEW_PAGE, "dalembertiennes-overview", ":material/insights:"),
            NavigationItem("Host", DALAMBERTIENNES_HOST_PAGE, "dalembertiennes-host", ":material/admin_panel_settings:"),
        ),
    }


def _normalized_event_status(session: Any | None = None) -> str:
    raw_status = (
        str(session.get("status") or "").strip().lower()
        if isinstance(session, dict)
        else ""
    )
    if raw_status in {"archived", "archive"}:
        return "archived"
    if raw_status in {"closed", "done", "complete", "completed"}:
        return "closed"
    if raw_status in {"open", "live", "active"}:
        return "open"
    if raw_status in {"draft", "lobby", "setup", "planned"}:
        return "draft"
    is_active = (
        bool(session.get("session_active") or session.get("active"))
        if isinstance(session, dict)
        else False
    )
    return "open" if is_active else "draft"


def _event_write_enabled(event_status: str) -> bool:
    return str(event_status or "").strip().lower() not in {"closed", "archived"}


def conference_event_context(
    session: Any | None = None,
    *,
    session_code: str = "",
) -> dict[str, Any]:
    raw_code = session_code or (
        str(session.get("session_code") or "") if isinstance(session, dict) else ""
    )
    resolved_code = _canonical_session_code(raw_code)
    config = event_config_for_session_code(resolved_code)
    session_name = (
        str(session.get("session_name") or "").strip()
        if isinstance(session, dict)
        else ""
    )
    session_title = (
        str(session.get("session_title") or "").strip()
        if isinstance(session, dict)
        else ""
    )
    event_label = (
        session_title or session_name or (config.label if config else resolved_code)
    )
    event_location = config.location if config else ""
    event_status = _normalized_event_status(session)
    return {
        "event_slug": config.slug if config else resolved_code.lower(),
        "event_code": resolved_code,
        "event_label": event_label,
        "event_location": event_location,
        "session_code": resolved_code,
        "question_set_id": config.question_set_id if config else resolved_code,
        "text_id": config.primary_text_id if config else resolved_code,
        "schema_id": config.schema_id if config else resolved_code,
        "response_scope": config.response_scope if config else "event_specific",
        "event_status": event_status,
        "write_enabled": _event_write_enabled(event_status),
        "test_mode": bool(config.test_mode) if config else False,
        "questionnaire_page": (
            config.questionnaire_page if config else COMPLEXITY_ENTRY_PAGE
        ),
        "overview_page": config.overview_page if config else COMPLEXITY_OVERVIEW_PAGE,
        "host_page": config.host_page if config else COMPLEXITY_HOST_PAGE,
    }


def conference_event_options(
    repo: Any | None = None, *, include_test: bool = False
) -> list[dict[str, Any]]:
    options: list[dict[str, Any]] = []
    seen: set[str] = set()
    for config in _EVENT_CONFIGS:
        if config.test_mode and not include_test:
            continue
        session = None
        if repo and hasattr(repo, "resolve_session"):
            try:
                session = repo.resolve_session(session_code=config.session_code)
            except Exception:
                session = None
        context = conference_event_context(session, session_code=config.session_code)
        code = str(context["session_code"])
        if code in seen:
            continue
        seen.add(code)
        options.append(
            {
                "event_slug": context["event_slug"],
                "session_code": code,
                "event_label": context["event_label"],
                "event_location": context["event_location"],
                "event_status": context["event_status"],
                "write_enabled": context["write_enabled"],
                "questionnaire_page": context["questionnaire_page"],
                "overview_page": context["overview_page"],
                "host_page": context["host_page"],
                "available": bool(session),
                "test_mode": bool(context["test_mode"]),
            }
        )
    return options


def _is_reserved_non_complexity_code(value: Any) -> bool:
    token = _canonical_session_code(value).lower()
    return token in {
        "",
        YOUNG_SESSION_CODE.lower(),
        UNESCO_SESSION_CODE.lower(),
        "global-session",
        UN_WG2_SESSION_CODE.lower(),
        UN_WG2_DEBUG_SESSION_CODE.lower(),
    }


def _looks_like_complexity_session(session: Any) -> bool:
    if not isinstance(session, dict):
        return False
    code = _canonical_session_code(session.get("session_code"))
    if _is_reserved_non_complexity_code(code):
        return False
    haystack = " ".join(
        [
            code,
            _normalized_code(session.get("session_name")),
            _normalized_code(session.get("session_title")),
            _normalized_code(session.get("session_description")),
        ]
    ).lower()
    return "complex" in haystack or "dalembert" in haystack


def _discover_complexity_session_code(repo: Any | None = None) -> str:
    notion_repo = getattr(repo, "notion_repo", repo)
    active = getattr(notion_repo, "get_active_session", None)
    if callable(active):
        session = active()
        if _looks_like_complexity_session(session):
            return _canonical_session_code(session.get("session_code"))

    sessions = getattr(notion_repo, "list_sessions", None)
    if callable(sessions):
        try:
            items = sessions(limit=50)
        except TypeError:
            items = sessions()
        for preferred_code in (
            "COMPLEXITY",
            COMPLEXITY_SESSION_CODE,
            DALAMBERTIENNES_SESSION_CODE,
        ):
            match = next(
                (
                    item
                    for item in items
                    if _canonical_session_code(item.get("session_code"))
                    == preferred_code
                ),
                None,
            )
            if match:
                return _canonical_session_code(match.get("session_code"))
        for item in items:
            if _looks_like_complexity_session(item):
                return _canonical_session_code(item.get("session_code"))
        global_match = next(
            (
                item
                for item in items
                if _canonical_session_code(item.get("session_code")).upper()
                == "GLOBAL-SESSION"
            ),
            None,
        )
        if global_match:
            return _canonical_session_code(global_match.get("session_code"))
    return COMPLEXITY_SESSION_CODE


def current_complexity_session_code(repo: Any | None = None) -> str:
    requested = _canonical_session_code(_requested_event_token())
    if requested and not _is_reserved_non_complexity_code(requested):
        return requested
    configured = _canonical_session_code(
        getattr(getattr(repo, "settings", None), "default_session_code", "") or ""
    )
    if configured and not _is_reserved_non_complexity_code(configured):
        return configured
    return _discover_complexity_session_code(repo)


def complexity_text_ids() -> tuple[str, ...]:
    return (COMPLEXITY_TEXT_ID, LEGACY_COMPLEXITY_TEXT_ID)


def text_ids_for_session_code(session_code: str) -> tuple[str, ...]:
    token = _canonical_session_code(session_code)
    if token == YOUNG_SESSION_CODE:
        return (YOUNG_TEXT_ID,)
    if token == UNESCO_SESSION_CODE:
        return ()
    config = event_config_for_session_code(token)
    if config:
        return config.text_ids
    if token:
        return complexity_text_ids()
    return ()
