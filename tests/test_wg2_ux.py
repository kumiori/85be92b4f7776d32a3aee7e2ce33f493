from pathlib import Path
import hashlib
import importlib.util
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from conference.repo import ConferenceRepo
from conference.settings import ConferenceSettings
from conference.flow import build_session_payload
from conference.question_sets.un_wg2_v1 import QUESTION_SET as UN_WG2_QUESTION_SET
from conference.wg2_ux import (
    confirm_location,
    correct_location,
    credential_export_rows,
    edit_context,
    host_role_allowed,
    location_lookup_due,
    location_lookup_failure,
    merge_answer_fields,
    parse_opencage_result,
    participant_access_rows,
    reminder_status_by_player,
    resolve_scoped_participants,
    revision_payload,
)


def _load_wg2_host_module():
    path = ROOT / "pages" / "27_UN_WG2_Host.py"
    spec = importlib.util.spec_from_file_location("wg2_host_for_ux_tests", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class _FakeNotionRepo:
    client = object()


class _CapturingInteractionRepo:
    def __init__(self):
        self.calls = []

    def save_response(self, **kwargs):
        self.calls.append(dict(kwargs))


def _settings() -> ConferenceSettings:
    return ConferenceSettings(
        notion_token="",
        notion_version="2025-09-03",
        session_responses_db_id="responses-db",
        default_session_code="complexity-session",
        debug=False,
    )


def _wg2_payload(answer: str) -> dict:
    return {
        "schema_version": "2",
        "profile": {"persistence_scope": "persistent_profile"},
        "session": {
            "event_slug": "un_wg2_visibility",
            "session_code": "un_wg2_core_2026",
            "question_set_id": "un_wg2_v1",
            "response_scope": "event_session",
            "event_status": "draft",
            "text_id": "un_wg2_v1",
            "wg2_coordination_signal": answer,
        },
    }


def test_successful_automatic_lookup_after_debounce():
    assert location_lookup_due(
        query="Université Grenoble Alpes, France",
        scheduled_query="Université Grenoble Alpes, France",
        scheduled_at=10.0,
        attempted_query="",
        now=10.7,
    )
    result = parse_opencage_result(
        {
            "results": [
                {
                    "formatted": "Grenoble, Auvergne-Rhône-Alpes, France",
                    "geometry": {"lat": 45.1885, "lng": 5.7245},
                    "components": {
                        "city": "Grenoble",
                        "state": "Auvergne-Rhône-Alpes",
                        "country": "France",
                    },
                }
            ]
        },
        "Université Grenoble Alpes, France",
    )

    assert result["raw_input"] == "Université Grenoble Alpes, France"
    assert result["resolved_label"] == "Grenoble, Auvergne-Rhône-Alpes, France"
    assert result["city"] == "Grenoble"
    assert result["approximate_latitude"] == 45.1885
    assert result["confirmation_state"] == "pending"

    confirmed = confirm_location(result)
    assert confirmed["confirmation_state"] == "confirmed"
    assert confirmed["coordinates_consent"] == "lookup"


def test_lookup_failure_keeps_raw_input_and_allows_text_fallback():
    failed = location_lookup_failure(
        {"institution_location": "Remote field base"},
        "Remote field base",
        "No location match found.",
    )

    assert failed["institution_location"] == "Remote field base"
    assert failed["raw_input"] == "Remote field base"
    assert failed["lookup_status"] == "failure"
    assert failed["coordinates"] == ""


def test_manual_location_correction_preserves_raw_input():
    corrected = correct_location(
        {"raw_input": "UGA"},
        resolved_label="Grenoble, France",
        country="France",
        region="Auvergne-Rhône-Alpes",
        city="Grenoble",
        latitude="45.1885",
        longitude="5.7245",
    )

    assert corrected["raw_input"] == "UGA"
    assert corrected["source"] == "manual_correction"
    assert corrected["confirmation_state"] == "corrected"
    assert corrected["coordinates"] == "45.188500, 5.724500"


def test_resolved_location_fields_are_persisted_with_raw_text():
    location = confirm_location(
        parse_opencage_result(
            {
                "results": [
                    {
                        "formatted": "Grenoble, Auvergne-Rhône-Alpes, France",
                        "geometry": {"lat": 45.1885, "lng": 5.7245},
                        "components": {
                            "city": "Grenoble",
                            "state": "Auvergne-Rhône-Alpes",
                            "country": "France",
                        },
                    }
                ]
            },
            "Université Grenoble Alpes, France",
        )
    )
    location["country_region"] = "France"
    location["institution_location"] = "Université Grenoble Alpes"

    payload = build_session_payload(
        {"mode": "quick", "wg2_main_location": location},
        question_set=UN_WG2_QUESTION_SET,
    )
    saved = payload["profile"]["wg2_main_location"]

    assert saved["institution_location"] == "Université Grenoble Alpes"
    assert saved["raw_input"] == "Université Grenoble Alpes, France"
    assert saved["resolved_label"] == "Grenoble, Auvergne-Rhône-Alpes, France"
    assert saved["country"] == "France"
    assert saved["region"] == "Auvergne-Rhône-Alpes"
    assert saved["city"] == "Grenoble"
    assert saved["approximate_longitude"] == 5.7245
    assert saved["source"] == "opencage"
    assert saved["confirmation_state"] == "confirmed"


def test_direct_edit_context_returns_to_review_and_merges_only_answer_fields():
    context = edit_context(
        question_id="UN_WG2_ROLE_LENS",
        step="role_lens",
        original_step=4,
        submitted=False,
    )
    original = {"wg2_role_lens": ["modeller"], "wg2_needs": ["data_access"]}
    edited = {"wg2_role_lens": ["regional_expert"], "wg2_needs": ["other"]}

    merged = merge_answer_fields(original, edited, ["wg2_role_lens"])

    assert context["return_to"] == "review"
    assert context["original_step"] == 4
    assert merged["wg2_role_lens"] == ["regional_expert"]
    assert merged["wg2_needs"] == ["data_access"]


def test_draft_update_before_submission_does_not_create_revision_metadata():
    original = {"wg2_coordination_signal": "First", "submitted": False}
    edited = {"wg2_coordination_signal": "Revised", "submitted": False}

    merged = merge_answer_fields(original, edited, ["wg2_coordination_signal"])

    assert merged["wg2_coordination_signal"] == "Revised"
    assert "revision" not in merged


def test_revision_after_submission_appends_a_new_response_row():
    repo = ConferenceRepo(_FakeNotionRepo(), _settings())
    capture = _CapturingInteractionRepo()
    repo._interaction_repo = capture
    initial = _wg2_payload("First")
    revised = revision_payload(
        _wg2_payload("Revised"),
        question_id="UN_WG2_COORDINATION_SIGNAL",
        field="wg2_coordination_signal",
        previous_value="First",
        revised_at="2026-07-31T10:00:00+00:00",
    )

    for payload in (initial, revised):
        repo.save_session_response_set(
            session_id="session-wg2",
            player_id="player-1",
            text_id="un_wg2_v1",
            device_id="device-1",
            access_key_hash="hash-1",
            access_key_last4="🌒⚡🎆💿",
            payload=payload,
        )

    assert len(capture.calls) == 2
    saved_revision = capture.calls[1]["value"]["bundle"]["session"]["revision"]
    assert saved_revision["kind"] == "answer_revision"
    assert saved_revision["previous_value"] == "First"


def test_host_permission_enforcement():
    assert host_role_allowed("admin")
    assert host_role_allowed("co_organiser")
    assert not host_role_allowed("Seeker")
    assert not host_role_allowed("")


def test_credentials_are_hidden_from_default_export():
    rows = participant_access_rows(
        [
            {
                "id": "player-1",
                "nickname": "Ada",
                "email": "ada@example.org",
                "access_key": "0123456789ABCDEF0123456789ABCDEF",
            }
        ]
    )

    safe = credential_export_rows(rows)
    deliberate = credential_export_rows(rows, include_full_credentials=True)

    assert "full_credential" not in safe[0]
    assert deliberate[0]["full_credential"] == "0123456789ABCDEF0123456789ABCDEF"


def test_access_support_recovers_only_players_in_scoped_wg2_submissions():
    wg2_key = "0123456789ABCDEF0123456789ABCDEF"
    other_key = "FEDCBA9876543210FEDCBA9876543210"
    players, source = resolve_scoped_participants(
        [],
        all_players=[
            {"id": "player-wg2", "access_key": wg2_key},
            {"id": "player-other", "access_key": other_key},
        ],
        submissions=[
            {
                "access_key_hash": hashlib.sha256(
                    wg2_key.encode("utf-8")
                ).hexdigest()
            }
        ],
    )

    assert source == "submission_hash"
    assert [player["id"] for player in players] == ["player-wg2"]


def test_email_reminder_status_uses_latest_event():
    status = reminder_status_by_player(
        [
            {"event_type": "credential_email_failed", "player_id": "player-1"},
            {"event_type": "credential_email_sent", "player_id": "player-1"},
        ]
    )

    assert status["player-1"] == "sent"


def test_credential_event_logging_keeps_wg2_scope(monkeypatch):
    module = _load_wg2_host_module()
    captured = []
    monkeypatch.setattr(module, "log_event", lambda **kwargs: captured.append(kwargs))

    module._log_credential_event(
        event_type="credential_revealed",
        session={"id": "session-wg2"},
        context={
            "event_slug": "un_wg2_visibility",
            "session_code": "un_wg2_core_2026",
        },
        player_id="player-1",
    )

    assert captured[0]["event_type"] == "credential_revealed"
    assert captured[0]["session_id"] == "session-wg2"
    assert captured[0]["metadata"]["event_slug"] == "un_wg2_visibility"


def test_public_wg2_information_page_is_registered():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    page_source = (ROOT / "pages" / "28_UN_WG2_Info.py").read_text(
        encoding="utf-8"
    )

    assert 'url_path="un-wg2"' in app_source
    assert "From outside WG2" in page_source
    assert "From inside WG2" in page_source


def test_review_edit_action_is_compact_and_has_no_back_to_questions_button():
    source = (ROOT / "conference" / "questionnaire.py").read_text(encoding="utf-8")

    assert '"Edit",' in source
    assert 'type="tertiary"' in source
    assert '"Back to questions"' not in source
