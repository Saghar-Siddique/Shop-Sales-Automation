"""Tests for analysis + CLI."""
import pandas as pd

from sales_automation import clean_sales
from sales_automation.analyzer import daily_trend, kpis, top_items
from sales_automation.cli import main as cli_main


def _clean_df() -> pd.DataFrame:
    raw = pd.DataFrame([
        {"Date": "2026-10-10", "Item": "Sugar", "Qty": "10", "Price": "100"},
        {"Date": "2026-10-10", "Item": "Chai", "Qty": "5", "Price": "120"},
        {"Date": "2026-10-11", "Item": "Sugar", "Qty": "4", "Price": "100"},
    ])
    return clean_sales(raw).clean


def test_kpis_math():
    k = kpis(_clean_df())
    assert k["total_sales"] == 10 * 100 + 5 * 120 + 4 * 100
    assert k["total_qty"] == 19
    assert k["transactions"] == 3
    assert k["top_item"] == "Sugar"
    assert k["avg_bill"] == k["total_sales"] / 3


def test_kpis_empty():
    k = kpis(pd.DataFrame())
    assert k["total_sales"] == 0.0 and k["transactions"] == 0


def test_daily_trend_sorted():
    t = daily_trend(_clean_df())
    assert t["Date"].is_monotonic_increasing
    assert t["Amount"].sum() == kpis(_clean_df())["total_sales"]


def test_top_items_ranked():
    top = top_items(_clean_df(), n=2)
    assert top.iloc[0]["Item"] == "Sugar"
    assert len(top) == 2


def test_cli_end_to_end(tmp_path):
    messy = tmp_path / "in.csv"
    messy.write_text("Date,Item,Qty,Price\n2026-10-10,Sugar,10,100\n2026-10-10,Sugar,10,100\n")
    out = tmp_path / "out"
    assert cli_main([str(messy), "-o", str(out)]) == 0
    assert (out / "sales_clean.csv").exists()
    assert (out / "report.txt").exists()
    clean = pd.read_csv(out / "sales_clean.csv")
    assert len(clean) == 1  # duplicate removed
