"""Tests for .xlsx export (Issue #1)."""
import io

import pandas as pd
from openpyxl import load_workbook

from sales_automation import CleanResult, clean_sales
from sales_automation.analyzer import kpis
from sales_automation.cli import main as cli_main
from sales_automation.reporter import save_workbook


def _result() -> CleanResult:
    raw = pd.DataFrame([
        {"Date": "2026-10-10", "Item": "Sugar", "Qty": "10", "Price": "100"},
        {"Date": "2026-10-10", "Item": "Chai", "Qty": "5", "Price": "120"},
        {"Date": "2026-10-11", "Item": "Sugar", "Qty": "4", "Price": "100"},
        {"Date": "2026-10-12", "Item": "Soap", "Qty": "two", "Price": "90"},
    ])
    return clean_sales(raw)


def test_workbook_sheets_and_rows(tmp_path):
    r = _result()
    path = tmp_path / "sales_clean.xlsx"
    save_workbook(r.clean, r.stats, kpis(r.clean), r.quarantined, path)
    wb = load_workbook(path)
    assert wb.sheetnames == ["Cleaned Data", "Summary", "Quarantined"]
    back = pd.read_excel(path, sheet_name="Cleaned Data")
    assert len(back) == len(r.clean) == 3
    assert list(back.columns) == list(r.clean.columns)
    assert back["Item"].tolist() == r.clean["Item"].tolist()
    assert back["Amount"].tolist() == r.clean["Amount"].tolist()


def test_workbook_no_quarantined_sheet_when_empty(tmp_path):
    raw = pd.DataFrame([
        {"Date": "2026-10-10", "Item": "Sugar", "Qty": "10", "Price": "100"},
    ])
    r = clean_sales(raw)
    assert r.quarantined.empty
    path = tmp_path / "sales_clean.xlsx"
    save_workbook(r.clean, r.stats, kpis(r.clean), r.quarantined, path)
    assert load_workbook(path).sheetnames == ["Cleaned Data", "Summary"]


def test_workbook_summary_matches_text_report(tmp_path):
    r = _result()
    path = tmp_path / "sales_clean.xlsx"
    save_workbook(r.clean, r.stats, kpis(r.clean), r.quarantined, path)
    summary = pd.read_excel(path, sheet_name="Summary")
    by_metric = dict(zip(summary["Metric"], summary["Value"]))
    assert by_metric["Rows read from CSV"] == 4
    assert by_metric["Rows after cleaning"] == 3
    assert by_metric["Quarantined (bad nums)"] == 1
    assert by_metric["Transactions"] == 3
    assert by_metric["Total Sales (Rs)"] == 10 * 100 + 5 * 120 + 4 * 100
    assert by_metric["Top Selling Item"] == "Sugar"


def test_workbook_to_bytes_buffer():
    r = _result()
    buf = io.BytesIO()
    save_workbook(r.clean, r.stats, kpis(r.clean), r.quarantined, buf)
    assert len(buf.getvalue()) > 0
    wb = load_workbook(io.BytesIO(buf.getvalue()))
    assert "Cleaned Data" in wb.sheetnames


def test_cli_xlsx_end_to_end(tmp_path):
    messy = tmp_path / "in.csv"
    messy.write_text("Date,Item,Qty,Price\n2026-10-10,Sugar,10,100\n2026-10-10,Sugar,10,100\n")
    out = tmp_path / "out"
    assert cli_main([str(messy), "-o", str(out), "--format", "xlsx"]) == 0
    assert (out / "sales_clean.xlsx").exists()
    assert (out / "report.txt").exists()
    assert not (out / "sales_clean.csv").exists()  # xlsx replaces the CSV
    back = pd.read_excel(out / "sales_clean.xlsx", sheet_name="Cleaned Data")
    assert len(back) == 1  # duplicate removed


def test_cli_csv_unchanged(tmp_path):
    messy = tmp_path / "in.csv"
    messy.write_text("Date,Item,Qty,Price\n2026-10-10,Sugar,10,100\n2026-10-10,Sugar,10,100\n")
    out = tmp_path / "out"
    assert cli_main([str(messy), "-o", str(out)]) == 0
    assert (out / "sales_clean.csv").exists()
    assert (out / "report.txt").exists()
    assert not (out / "sales_clean.xlsx").exists()
    clean = pd.read_csv(out / "sales_clean.csv")
    assert len(clean) == 1
