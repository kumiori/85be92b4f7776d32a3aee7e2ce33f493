from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from conference.events import (
    COMPLEXITY_SESSION_CODE,
    COMPLEXITY_TEXT_ID,
    LEGACY_COMPLEXITY_TEXT_ID,
    UN_WG2_DEBUG_SESSION_CODE,
    UN_WG2_TEXT_ID,
    YOUNG_SESSION_CODE,
    YOUNG_TEXT_ID,
    complexity_text_ids,
    conference_event_context,
    conference_event_options,
    current_complexity_session_code,
    text_ids_for_session_code,
)


class _RepoWithSettings:
    class settings:
        default_session_code = "petnica_2026"


class _RepoWithLegacySetting:
    class settings:
        default_session_code = "pisa-conference-session"


class _RepoWithGlobalSetting:
    class settings:
        default_session_code = "GLOBAL-SESSION"

    class notion_repo:
        @staticmethod
        def list_sessions(limit: int = 50):
            return [
                {"session_code": "GLOBAL-SESSION", "session_name": "Global", "session_title": "Global"},
                {"session_code": "petnica_2026", "session_name": "Complexity", "session_title": "Complexity"},
            ]


class _RepoWithCustomComplexitySetting:
    class settings:
        default_session_code = "petnica_2026"


def test_current_complexity_session_code_prefers_repo_setting():
    assert current_complexity_session_code(_RepoWithSettings()) == COMPLEXITY_SESSION_CODE


def test_current_complexity_session_code_ignores_legacy_young_setting():
    assert current_complexity_session_code(_RepoWithLegacySetting()) == COMPLEXITY_SESSION_CODE


def test_current_complexity_session_code_uses_fallback_without_repo():
    assert current_complexity_session_code(None) == COMPLEXITY_SESSION_CODE


def test_current_complexity_session_code_ignores_global_session_and_discovers_complexity():
    assert current_complexity_session_code(_RepoWithGlobalSetting()) == "petnica_2026"


def test_text_ids_for_session_code_maps_known_events():
    assert text_ids_for_session_code(COMPLEXITY_SESSION_CODE) == (
        COMPLEXITY_TEXT_ID,
        LEGACY_COMPLEXITY_TEXT_ID,
    )
    assert text_ids_for_session_code(YOUNG_SESSION_CODE) == (YOUNG_TEXT_ID,)
    assert text_ids_for_session_code(UN_WG2_DEBUG_SESSION_CODE) == (UN_WG2_TEXT_ID,)


def test_text_ids_for_custom_complexity_session_code_use_complexity_bundle():
    code = current_complexity_session_code(_RepoWithCustomComplexitySetting())
    assert text_ids_for_session_code(code) == complexity_text_ids()


def test_wg2_debug_context_is_explicit_and_hidden_from_normal_event_options():
    context = conference_event_context(
        {
            "session_code": UN_WG2_DEBUG_SESSION_CODE,
            "session_title": "TEST · WG2",
            "status": "Lobby",
        }
    )

    assert context["test_mode"] is True
    assert context["response_scope"] == "debug_session"
    assert context["text_id"] == UN_WG2_TEXT_ID
    assert all(
        item["session_code"] != UN_WG2_DEBUG_SESSION_CODE
        for item in conference_event_options()
    )
    assert any(
        item["session_code"] == UN_WG2_DEBUG_SESSION_CODE
        for item in conference_event_options(include_test=True)
    )
