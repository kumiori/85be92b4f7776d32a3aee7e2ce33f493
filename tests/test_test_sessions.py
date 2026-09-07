from conference.test_sessions import (
    DebugSessionSpec,
    debug_session_access_enabled,
    ensure_test_session,
    wg2_debug_session_spec,
)


class _Repo:
    def __init__(self, session=None):
        self.session = session
        self.created = []
        self.updated = []

    def get_session_by_code(self, session_code):
        if self.session and self.session.get("session_code") == session_code:
            return dict(self.session)
        return None

    def create_session(self, session_code, mode):
        self.created.append((session_code, mode))
        self.session = {"id": "debug-session", "session_code": session_code}
        return dict(self.session)

    def update_session(self, session_id, **fields):
        self.updated.append((session_id, fields))
        self.session = {**self.session, **fields}
        return dict(self.session)


def _spec():
    return DebugSessionSpec(
        session_code="event_debug_2026",
        production_session_code="event_2026",
        session_name="Event Debug",
        session_title="TEST · Event",
        session_description="Isolated test data",
        session_order=41,
    )


def test_ensure_test_session_creates_a_distinct_inactive_session():
    repo = _Repo()

    session, created = ensure_test_session(repo, _spec())

    assert created is True
    assert repo.created == [("event_debug_2026", "Non-linear")]
    assert session["session_code"] == "event_debug_2026"
    assert session["active"] is False
    assert session["status"] == "Lobby"


def test_ensure_test_session_reuses_existing_session():
    repo = _Repo({"id": "debug-session", "session_code": "event_debug_2026"})

    session, created = ensure_test_session(repo, _spec())

    assert created is False
    assert repo.created == []
    assert session["session_title"] == "TEST · Event"


def test_test_session_cannot_reuse_production_code():
    repo = _Repo()
    spec = DebugSessionSpec(
        session_code="event_2026",
        production_session_code="event_2026",
        session_name="Bad",
        session_title="Bad",
        session_description="Bad",
        session_order=1,
    )

    try:
        ensure_test_session(repo, spec)
    except ValueError as exc:
        assert "must not reuse" in str(exc)
    else:
        raise AssertionError("Expected production/test session collision to fail.")


def test_debug_entry_is_closed_by_default_and_reduced_from_host_events():
    assert debug_session_access_enabled([]) is False
    assert debug_session_access_enabled(
        [
            {"timestamp": "2026-09-06T10:00:00Z", "event_type": "debug_session_access_enabled"},
            {"timestamp": "2026-09-06T11:00:00Z", "event_type": "debug_session_access_disabled"},
        ]
    ) is False


def test_wg2_debug_session_spec_is_canonical_and_distinct():
    spec = wg2_debug_session_spec()

    assert spec.session_code == "un_wg2_debug_2026"
    assert spec.production_session_code == "un_wg2_core_2026"
    assert spec.session_code != spec.production_session_code
