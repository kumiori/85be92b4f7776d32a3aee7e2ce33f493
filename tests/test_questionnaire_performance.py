from types import SimpleNamespace

from conference import questionnaire
from repositories.interaction_repo import NotionInteractionRepository


class _CheckpointRepo:
    def __init__(self):
        self.upserts = 0
        self.checkpoints = 0

    def upsert_identified_conference_player(self, **_kwargs):
        self.upserts += 1
        return {"id": "player-1"}

    def save_participation_checkpoint(self, **_kwargs):
        self.checkpoints += 1
        return {"response_id": f"checkpoint-{self.checkpoints}"}


def test_repeated_question_checkpoints_reuse_resolved_participant(monkeypatch):
    repo = _CheckpointRepo()
    question_set = SimpleNamespace(id="prediction")
    draft = {"name": "Ada", "email": "ada@example.org"}
    session = {"id": "session-1", "session_code": "prediction_2026"}
    event_config = SimpleNamespace(
        identity_policy=SimpleNamespace(identified=True)
    )

    monkeypatch.setattr(questionnaire, "st", SimpleNamespace(session_state={}))
    monkeypatch.setattr(questionnaire, "current_question_set", lambda: question_set)
    monkeypatch.setattr(questionnaire, "get_draft", lambda **_kwargs: draft)
    monkeypatch.setattr(questionnaire, "_ensure_access_key", lambda: "access-key")
    monkeypatch.setattr(questionnaire, "_payload_for_session", lambda *_args: {})
    monkeypatch.setattr(
        questionnaire, "event_config_for_session_code", lambda _code: event_config
    )
    monkeypatch.setattr(
        questionnaire,
        "_event_context",
        lambda _session: {"text_id": "prediction_v0", "test_mode": False},
    )

    assert questionnaire._persist_participation_checkpoint(
        repo, session, next_position="systems"
    )
    assert questionnaire._persist_participation_checkpoint(
        repo, session, next_position="expectations"
    )

    assert repo.upserts == 1
    assert repo.checkpoints == 2


def test_prediction_integration_only_policy_does_not_write_mid_flow(monkeypatch):
    repo = _CheckpointRepo()
    question_set = SimpleNamespace(id="prediction")
    session = {"id": "session-1", "session_code": "prediction_2026"}
    event_config = SimpleNamespace(
        persistence_policy="integration_only",
        identity_policy=SimpleNamespace(identified=True),
    )

    monkeypatch.setattr(questionnaire, "current_question_set", lambda: question_set)
    monkeypatch.setattr(
        questionnaire, "event_config_for_session_code", lambda _code: event_config
    )

    assert questionnaire._persist_participation_checkpoint(
        repo, session, next_position="systems"
    )
    assert repo.upserts == 0
    assert repo.checkpoints == 0


def test_prediction_integration_only_policy_keeps_mid_flow_events_local(monkeypatch):
    calls = []
    config = SimpleNamespace(persistence_policy="integration_only")
    monkeypatch.setattr(
        questionnaire, "event_config_for_session_code", lambda _code: config
    )
    monkeypatch.setattr(questionnaire, "log_event", lambda **kwargs: calls.append(kwargs))
    monkeypatch.setattr(questionnaire.st, "session_state", {})

    questionnaire._log_route_event(
        {"id": "session-1", "session_code": "prediction_2026"},
        event_type="question_flagged",
        step="systems",
    )

    assert calls[0]["persist"] is False


def test_event_session_bundle_is_reused_for_open_browser_flow(monkeypatch):
    calls = []
    bundle = {"session": {"id": "session-1", "session_code": "prediction_2026"}}
    monkeypatch.setattr(questionnaire.st, "session_state", {})
    monkeypatch.setattr(
        questionnaire,
        "get_conference_bundle",
        lambda **kwargs: calls.append(kwargs) or bundle,
    )

    assert questionnaire._session_bundle_for_flow("prediction_2026") is bundle
    assert questionnaire._session_bundle_for_flow("prediction_2026") is bundle
    assert calls == [{"session_code": "prediction_2026"}]


def test_checkpoint_write_skips_scientific_question_lookup():
    interaction_repo = object.__new__(NotionInteractionRepository)
    interaction_repo._question_page_by_item_id = {}

    class _NoRemoteClient:
        @property
        def data_sources(self):
            raise AssertionError("checkpoint must not query the Questions database")

    interaction_repo.client = _NoRemoteClient()
    interaction_repo._properties = {"question": {"type": "relation"}}

    assert (
        interaction_repo._resolve_question_page_id(
            "CONFERENCE_PARTICIPATION_CHECKPOINT"
        )
        is None
    )


def test_debug_participant_can_resume_its_session_scoped_checkpoint(monkeypatch):
    state = {}
    draft = {"access_key": "", "submitted": False}
    submission = {
        "_checkpoint": True,
        "_checkpoint_position": "systems",
        "mode": "integral",
        "name": "Debug Participant",
        "email": "debug@example.invalid",
    }
    repo = SimpleNamespace(upsert_conference_player=lambda **_kwargs: {"id": "p-1"})

    monkeypatch.setattr(
        questionnaire,
        "st",
        SimpleNamespace(session_state=state, rerun=lambda: None),
    )
    monkeypatch.setattr(questionnaire, "current_question_set", lambda: SimpleNamespace(id="prediction"))
    monkeypatch.setattr(questionnaire, "get_draft", lambda **_kwargs: draft)
    monkeypatch.setattr(questionnaire, "update_draft", lambda **values: draft.update(values))
    monkeypatch.setattr(questionnaire, "_event_context", lambda _session: {"test_mode": True})
    monkeypatch.setattr(questionnaire, "_load_submission_for_key", lambda *_args: ("debug-key", submission, ""))
    monkeypatch.setattr(questionnaire, "_normalize_hydrated_submission", lambda value: value)
    monkeypatch.setattr(questionnaire, "build_session_payload", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(questionnaire, "build_identity_metadata", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(questionnaire, "set_step", lambda step, **_kwargs: state.update(step=step))
    monkeypatch.setattr(questionnaire, "_set_entry_mode", lambda mode: state.update(entry_mode=mode))
    monkeypatch.setattr(questionnaire, "_clear_login_error", lambda: None)

    questionnaire._login_with_key(repo, {"id": "prediction-debug"}, "debug-key")

    assert draft["access_key"] == "debug-key"
    assert state["step"] == "systems"
    assert state["entry_mode"] == "new"
