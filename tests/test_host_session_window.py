from conference.session_window import filter_rows_to_session_window


def test_host_window_normalizes_naive_boundary_and_aware_rows():
    rows = [
        {"timestamp": "2026-09-10T08:59:59Z", "response_id": "old"},
        {"timestamp": "2026-09-10T09:00:00+00:00", "response_id": "current"},
    ]
    session = {"start": "2026-09-10T09:00:00", "end": ""}

    filtered = filter_rows_to_session_window(rows, session)

    assert [row["response_id"] for row in filtered] == ["current"]


def test_host_window_normalizes_aware_boundary_and_naive_rows():
    rows = [
        {"timestamp": "2026-09-10T08:59:59", "response_id": "old"},
        {"timestamp": "2026-09-10T09:00:00", "response_id": "current"},
    ]
    session = {"start": "2026-09-10T09:00:00Z", "end": ""}

    filtered = filter_rows_to_session_window(rows, session)

    assert [row["response_id"] for row in filtered] == ["current"]
