from types import SimpleNamespace

from infra import notion_repo


class _RateLimitedError(notion_repo.APIResponseError):
    def __init__(self, retry_after: str = "3") -> None:
        Exception.__init__(self, "You have been rate limited.")
        self.status = 429
        self.headers = {"retry-after": retry_after}


def test_notion_retry_honours_retry_after_header(monkeypatch):
    attempts = 0
    sleeps: list[float] = []

    def request():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise _RateLimitedError("3")
        return "ok"

    monkeypatch.setattr(notion_repo.time, "sleep", sleeps.append)

    assert notion_repo._execute_with_retry(request) == "ok"
    assert sleeps == [3.0]


def test_public_questionnaire_turns_session_lookup_throttle_into_retry_ui(monkeypatch):
    from conference import questionnaire

    messages: list[str] = []
    repo = SimpleNamespace(is_ready=lambda: True)
    monkeypatch.setattr(questionnaire, "set_page", lambda: None)
    monkeypatch.setattr(questionnaire, "apply_conference_styles", lambda: None)
    monkeypatch.setattr(questionnaire, "get_conference_repo", lambda: repo)
    monkeypatch.setattr(
        questionnaire,
        "get_conference_bundle",
        lambda **_kwargs: (_ for _ in ()).throw(_RateLimitedError()),
    )
    monkeypatch.setattr(questionnaire.st, "warning", messages.append)
    monkeypatch.setattr(questionnaire.st, "button", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(questionnaire.st, "session_state", {})

    questionnaire.run_conference_questionnaire_page(
        session_code_resolver=lambda _repo: "prediction_2026",
        public_route_path="prediction",
    )

    assert messages
    assert "wait" in messages[0].lower()
    assert "answers" in messages[0].lower()


def test_rate_limited_checkpoint_keeps_browser_draft_and_uses_calm_warning(monkeypatch):
    from conference import questionnaire

    draft = {"name": "Ada", "email": "ada@example.org", "systems": ["porous"]}
    browser_state = {"conference_device_id": "device-1"}
    messages: list[str] = []
    repo = SimpleNamespace(
        upsert_identified_conference_player=lambda **_kwargs: {"id": "player-1"},
        save_participation_checkpoint=lambda **_kwargs: (_ for _ in ()).throw(
            _RateLimitedError()
        ),
    )
    config = SimpleNamespace(identity_policy=SimpleNamespace(identified=True))

    monkeypatch.setattr(
        questionnaire.st,
        "session_state",
        browser_state,
    )
    monkeypatch.setattr(questionnaire.st, "warning", messages.append)
    monkeypatch.setattr(questionnaire, "current_question_set", lambda: SimpleNamespace(id="prediction"))
    monkeypatch.setattr(questionnaire, "get_draft", lambda **_kwargs: draft)
    monkeypatch.setattr(questionnaire, "_ensure_access_key", lambda: "access-key")
    monkeypatch.setattr(questionnaire, "_payload_for_session", lambda *_args: {})
    monkeypatch.setattr(questionnaire, "event_config_for_session_code", lambda _code: config)
    monkeypatch.setattr(
        questionnaire,
        "_event_context",
        lambda _session: {"text_id": "prediction_v0", "test_mode": False},
    )

    assert not questionnaire._persist_participation_checkpoint(
        repo,
        {"id": "session-1", "session_code": "prediction_2026"},
        next_position="expected_solutions",
    )
    assert draft["systems"] == ["porous"]
    assert len(messages) == 1
    assert "open browser tab" in messages[0]
