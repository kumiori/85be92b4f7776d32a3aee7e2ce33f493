from types import SimpleNamespace

from infra import event_logger


class _DataSources:
    def __init__(self, results=None):
        self.queried_id = ""
        self.results = list(results or [])

    def query(self, *, data_source_id, **_kwargs):
        self.queried_id = data_source_id
        return {"results": self.results}


class _Pages:
    def __init__(self, error=None):
        self.error = error
        self.created = []

    def create(self, **kwargs):
        if self.error:
            raise self.error
        self.created.append(kwargs)
        return {"id": "event-1"}


class _PaginatedDataSources:
    def __init__(self):
        self.calls = []

    def query(self, *, data_source_id, **kwargs):
        self.calls.append((data_source_id, kwargs))
        if not kwargs.get("start_cursor"):
            return {
                "results": [{"id": "event-1", "properties": {}}],
                "has_more": True,
                "next_cursor": "next-page",
            }
        return {
            "results": [{"id": "event-2", "properties": {}}],
            "has_more": False,
            "next_cursor": None,
        }


def test_event_reader_uses_resolved_data_source_id(monkeypatch):
    data_sources = _DataSources()
    repo = SimpleNamespace(client=SimpleNamespace(data_sources=data_sources))
    monkeypatch.setattr(
        event_logger,
        "_event_repo_info",
        lambda: {
            "enabled": True,
            "repo": repo,
            "db_id": "configured-database-id",
            "data_source_id": "resolved-data-source-id",
            "props": {},
        },
    )

    assert event_logger.list_logged_events(limit=10) == []
    assert data_sources.queried_id == "resolved-data-source-id"


def test_event_reader_tolerates_empty_notion_date(monkeypatch):
    data_sources = _DataSources(
        [{"id": "event-1", "properties": {"timestamp": {"type": "date", "date": None}}}]
    )
    repo = SimpleNamespace(client=SimpleNamespace(data_sources=data_sources))
    monkeypatch.setattr(
        event_logger,
        "_event_repo_info",
        lambda: {
            "enabled": True,
            "repo": repo,
            "db_id": "configured-database-id",
            "data_source_id": "resolved-data-source-id",
            "props": {"timestamp": {"type": "date"}},
        },
    )

    assert event_logger.list_logged_events(limit=10)[0]["timestamp"] == ""


def test_event_reader_paginates_up_to_requested_limit(monkeypatch):
    data_sources = _PaginatedDataSources()
    repo = SimpleNamespace(client=SimpleNamespace(data_sources=data_sources))
    monkeypatch.setattr(
        event_logger,
        "_event_repo_info",
        lambda: {
            "enabled": True,
            "repo": repo,
            "db_id": "configured-database-id",
            "data_source_id": "resolved-data-source-id",
            "props": {},
        },
    )

    events = event_logger.list_logged_events(limit=2)

    assert [event["id"] for event in events] == ["event-1", "event-2"]
    assert data_sources.calls[1][1]["start_cursor"] == "next-page"


def test_event_writer_reports_persistence_success(monkeypatch):
    pages = _Pages()
    repo = SimpleNamespace(client=SimpleNamespace(pages=pages))
    monkeypatch.setattr(
        event_logger,
        "_event_repo_info",
        lambda: {
            "enabled": True,
            "repo": repo,
            "db_id": "configured-database-id",
            "data_source_id": "resolved-data-source-id",
            "props": {},
        },
    )

    assert event_logger.log_event(module="test", event_type="saved") is True
    assert pages.created[0]["parent"] == {"database_id": "configured-database-id"}


def test_event_writer_reports_persistence_failure(monkeypatch):
    pages = _Pages(RuntimeError("write failed"))
    repo = SimpleNamespace(client=SimpleNamespace(pages=pages))
    monkeypatch.setattr(
        event_logger,
        "_event_repo_info",
        lambda: {
            "enabled": True,
            "repo": repo,
            "db_id": "configured-database-id",
            "data_source_id": "resolved-data-source-id",
            "props": {},
        },
    )

    assert event_logger.log_event(module="test", event_type="not-saved") is False
