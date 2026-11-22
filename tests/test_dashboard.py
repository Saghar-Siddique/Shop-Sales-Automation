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


def test_dashboard_column_mapping_input_present():
    at = AppTest.from_file(str(APP)).run()
    assert not at.exception
    labels = [t.label for t in at.sidebar.text_input]
    assert "Column mapping (optional)" in labels


def test_dashboard_column_mapping_noop_on_sample():
    # Mapping the sample's own headers is a no-op rename: still 26 -> 16 rows.
    at = AppTest.from_file(str(APP)).run()
    at.sidebar.text_input[0].set_value("date:Date,item:Item").run()
    assert not at.exception
    assert not at.error
    rows_cleaned = [m for m in at.metric if m.label == "🧹 Rows cleaned"]
    assert rows_cleaned and rows_cleaned[0].value == "26 → 16"


def test_dashboard_column_mapping_bad_header_shows_error():
    at = AppTest.from_file(str(APP)).run()
    at.sidebar.text_input[0].set_value("date:Nope").run()
    assert not at.exception
    assert at.error
    assert "Nope" in at.error[0].value


def test_dashboard_unmapped_headers_shows_warning():
    # Regression (QA Nov 2026): an uploaded CSV with unrecognised headers
    # silently zeroed the dashboard with no hint about column mapping.
    at = AppTest.from_file(str(APP)).run()
    assert not at.exception
    alt = Path(__file__).resolve().parent.parent / "data" / "sales_messy_alt.csv"
    at.sidebar.file_uploader[0].set_value(
        [("sales_messy_alt.csv", alt.read_bytes(), "text/csv")]
    ).run()
    assert not at.exception
    assert at.warning
    assert "Column mapping" in at.warning[0].value
