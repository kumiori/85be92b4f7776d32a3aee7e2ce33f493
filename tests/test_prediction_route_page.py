from importlib import import_module
from types import SimpleNamespace


def test_prediction_route_establishes_page_shell_before_rendering_navigation(monkeypatch):
    page = import_module("pages.36_Prediction")
    calls: list[str] = []

    monkeypatch.setattr(page.st, "query_params", {"view": "results"})
    monkeypatch.setattr(page, "set_page", lambda: calls.append("set_page"), raising=False)
    monkeypatch.setattr(
        page,
        "render_prediction_navigation",
        lambda **_kwargs: calls.append("navigation"),
    )
    monkeypatch.setattr(
        page,
        "import_module",
        lambda _name: SimpleNamespace(main=lambda **_kwargs: calls.append("results")),
    )

    page.main()

    assert calls == ["set_page", "navigation", "results"]
