from pathlib import Path
import ast


ROOT = Path(__file__).parents[1]


def test_streamlit_deployment_does_not_trigger_an_apt_install():
    assert not (ROOT / "packages.txt").exists()


def test_credential_pdf_keeps_a_non_noto_font_fallback():
    source = (ROOT / "infra" / "credentials_pdf.py").read_text(encoding="utf-8")

    assert "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf" in source
    assert "ImageFont.load_default()" in source


def test_every_static_streamlit_page_registration_exists():
    tree = ast.parse((ROOT / "app.py").read_text(encoding="utf-8"))
    registered = [
        node.args[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "Page"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    ]

    missing = [path for path in registered if not (ROOT / path).exists()]
    assert missing == []
