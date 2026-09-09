from conference.events import event_config_for_request, public_event_configs
from conference.session_routes import (
    normalize_prediction_view,
    prediction_primary_links,
    prediction_sidebar_links,
    prediction_url,
)


def test_prediction_canonical_urls_use_explicit_view_vocabulary():
    assert prediction_url() == "/prediction"
    assert prediction_url(view="results") == "/prediction?view=results"
    assert prediction_url(view="host") == "/prediction?view=host"
    assert prediction_url(view="unknown") == "/prediction"


def test_prediction_test_mode_composes_with_every_view():
    assert prediction_url(test=True) == "/prediction?test=1"
    assert prediction_url(view="results", test=True) == (
        "/prediction?view=results&test=1"
    )
    assert prediction_url(view="host", test=True) == (
        "/prediction?view=host&test=1"
    )

    assert prediction_primary_links(test_mode=True) == (
        ("Join", "/prediction?test=1"),
        ("Results", "/prediction?view=results&test=1"),
    )
    assert prediction_sidebar_links(test_mode=True) == (
        ("Host", "/prediction?view=host&test=1"),
        ("Test", "/prediction?test=1"),
    )


def test_production_navigation_never_emits_a_test_flag():
    links = prediction_primary_links(test_mode=False)
    assert links == (
        ("Join", "/prediction"),
        ("Results", "/prediction?view=results"),
    )
    assert all("?results" not in url and "?host" not in url for _, url in links)
    assert prediction_sidebar_links(test_mode=False) == (
        ("Host", "/prediction?view=host"),
        ("Test", "/prediction?test=1"),
    )


def test_unknown_or_absent_prediction_view_defaults_to_join():
    assert normalize_prediction_view("") == "join"
    assert normalize_prediction_view("unexpected") == "join"
    assert normalize_prediction_view("RESULTS") == "results"


def test_sessions_index_exposes_only_production_canonical_routes():
    configs = public_event_configs()
    assert all(not config.test_mode for config in configs)
    assert all("?test=" not in config.canonical_path for config in configs)
    assert event_config_for_request("prediction").canonical_path == "prediction"
    assert event_config_for_request("prediction", test=True).canonical_path == "prediction"
