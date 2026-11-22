"""Ragged CSV handling (final QA, Nov 2026): a row with the wrong number of
fields must be skipped + reported, never crash the run with a traceback."""
from pathlib import Path

import pandas as pd
import pytest

from sales_automation import clean_sales, load_csv, load_csv_lenient
from sales_automation.cli import main

RAGGED = Path(__file__).resolve().parent.parent / "data" / "sales_ragged.csv"
APP = Path(__file__).resolve().parent.parent / "dashboard_app.py"

TOUGH = """Date,Item,Qty,Price
2026-10-12,Chai,5,120
2026-10-05,chai,3,120
2026-12-10, CHAI ,2,120
12/10/2026,Sugar,10,150
05/10/2026,sugar,5,150
2026-01-02,Rice,4,320
2026-10-12,چائے,2,120
2026-10-13,"Tea, Special",1,1200
2026-10-14,,1,100
2026-10-15,Oil,2,
2026-10-16,Ghee,-1,1200
2026-10-17,Tea,0,1200
2026-10-18,Rice,1,99999999
2026-10-19,Rice,1,"Rs 1,200"
2026-10-12,Chai,5,120
2026-10-20,Chai,1,120,EXTRA

2026/10/21,Chai,2,120
"""


def test_load_csv_lenient_skips_ragged_row():
    df, skipped = load_csv_lenient(str(RAGGED))
    assert len(df) == 2  # Chai + Rice; the ragged Sugar row is skipped
    assert len(skipped) == 1
    assert "EXTRA" in skipped[0]


def test_load_csv_keeps_old_signature():
    # Backward compatible: plain load_csv still returns just the DataFrame.
    df = load_csv(str(RAGGED))
    assert len(df) == 2
    assert "Chai" in df["Item"].tolist()


def test_cli_ragged_csv_exits_zero(tmp_path, capsys):
    out = tmp_path / "out"
    rc = main([str(RAGGED), "-o", str(out)])
    assert rc == 0
    assert (out / "sales_clean.csv").exists()
    assert (out / "report.txt").exists()
    report = (out / "report.txt").read_text(encoding="utf-8")
    assert "1 malformed row(s) skipped" in report
    _, err = capsys.readouterr()
    assert "skipped 1 malformed row" in err


def test_cli_tough_csv_with_ragged_row(tmp_path):
    tough = tmp_path / "tough.csv"
    tough.write_text(TOUGH, encoding="utf-8")
    out = tmp_path / "out"
    rc = main([str(tough), "-o", str(out), "--format", "xlsx"])
    assert rc == 0
    report = (out / "report.txt").read_text(encoding="utf-8")
    assert "1 malformed row(s) skipped" in report
    clean = pd.read_excel(out / "sales_clean.xlsx", sheet_name="Cleaned Data")
    assert len(clean) == 12
    # ISO dates preserved, DD/MM parsed as day-first (no month/day swap).
    sugar = clean[clean["Item"] == "Sugar"]
    assert set(sugar["Date"].astype(str)) == {"2026-10-12", "2026-10-05"}
    summary = pd.read_excel(out / "sales_clean.xlsx", sheet_name="Summary")
    by_metric = dict(zip(summary["Metric"], summary["Value"]))
    assert by_metric["Malformed rows skipped"] == 1


def test_cli_empty_file_clean_error(tmp_path, capsys):
    empty = tmp_path / "empty.csv"
    empty.write_text("", encoding="utf-8")
    rc = main([str(empty), "-o", str(tmp_path / "out")])
    assert rc == 2
    _, err = capsys.readouterr()
    assert "Error:" in err
    assert "Traceback" not in err


def test_dashboard_ragged_upload_shows_warning_not_traceback():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(APP)).run()
    assert not at.exception
    at.sidebar.file_uploader[0].set_value(
        [("sales_ragged.csv", RAGGED.read_bytes(), "text/csv")]
    ).run()
    assert not at.exception
    assert at.warning
    assert "malformed" in at.warning[0].value.lower()
    rows_cleaned = [m for m in at.metric if m.label == "🧹 Rows cleaned"]
    assert rows_cleaned and rows_cleaned[0].value == "2 → 2"
