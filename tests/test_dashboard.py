"""Dashboard smoke tests (Streamlit AppTest)."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parent.parent / "dashboard_app.py"


def test_dashboard_download_buttons():
    at = AppTest.from_file(str(APP)).run()
    assert not at.exception
    labels = [b.label for b in at.download_button]
    assert "⬇️ Download cleaned CSV" in labels
    assert "⬇️ Download cleaned Excel (.xlsx)" in labels
