from types import SimpleNamespace

from conference import public_routes


def test_public_route_query_preserves_test_mode_and_uses_debug_event(monkeypatch):
    query_params = {"test": "1"}
    monkeypatch.setattr(
        public_routes,
        "st",
        SimpleNamespace(query_params=query_params),
    )

    public_routes.ensure_public_route_query(
        "un-wg2-icebreaker",
        event_slug_override="un_wg2_visibility_debug",
    )

    assert query_params == {
        "test": "1",
        "public_route": "un-wg2-icebreaker",
        "campaign": "un-cryosphere-decade",
        "event": "un_wg2_visibility_debug",
    }


def test_wg2_route_and_questionnaire_keep_test_mode_visible():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    route_source = (root / "pages" / "25_UN_WG2_Icebreaker.py").read_text()
    questionnaire_source = (root / "conference" / "questionnaire.py").read_text()

    assert "UN_WG2_DEBUG_SESSION_CODE" in route_source
    assert "TEST MODE · This run is stored in the separate debug session" in questionnaire_source
    assert 'session_payload["data_classification"] = "debug"' in questionnaire_source
    assert "conference_runtime_session_scope" in questionnaire_source
    assert "Prevent browser draft/cache state crossing production and test sessions" in questionnaire_source
