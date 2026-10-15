"""Tests for the cleaning pipeline."""
import pandas as pd
import pytest

from sales_automation import CleanConfig, clean_sales
from sales_automation.cleaner import (
    coerce_qty,
    flag_outliers_iqr,
    parse_dates,
    standardize_names,
    strip_currency,
)


@pytest.fixture
def messy() -> pd.DataFrame:
    return pd.DataFrame([
        {"Date": "2026-10-10", "Item": "Sugar", "Qty": "10", "Price": "150"},
        {"Date": "12/10/2026", "Item": " CHAI ", "Qty": "5", "Price": "120"},
        {"Date": "2026-10-12", "Item": "chai", "Qty": "3", "Price": "Rs 120"},
        {"Date": "2026-10-13", "Item": "Oil", "Qty": "2", "Price": "850"},
        {"Date": "2026-10-13", "Item": "oil", "Qty": "2", "Price": "850"},
        {"Date": "2026-10-14", "Item": "", "Qty": "3", "Price": "200"},
        {"Date": "2026-10-14", "Item": "Soap", "Qty": "two", "Price": "90"},
        {"Date": "2026-10-14", "Item": "Tea", "Qty": "6", "Price": "-50"},
        {"Date": "2026-10-15", "Item": "Rice", "Qty": "1", "Price": "50000"},
    ])


def test_strip_currency():
    s = pd.Series(["Rs 120", "Rs 1,200", "$5", "150", "abc"])
    out = strip_currency(s)
    assert out.tolist()[:4] == [120.0, 1200.0, 5.0, 150.0]
    assert pd.isna(out.iloc[4])


def test_coerce_qty():
    out = coerce_qty(pd.Series(["5", "two", "3.0", ""]))
    assert out.iloc[0] == 5
    assert pd.isna(out.iloc[1])
    assert out.iloc[2] == 3
    assert pd.isna(out.iloc[3])


def test_parse_dates_mixed_formats():
    out = parse_dates(pd.Series(["12/10/2026", "2026-10-12", "Oct 13 2026", "garbage"]))
    assert out.iloc[0] == out.iloc[1] == pd.Timestamp("2026-10-12")
    assert out.iloc[2] == pd.Timestamp("2026-10-13")
    assert pd.isna(out.iloc[3])


def test_standardize_names_fuzzy():
    s = pd.Series(["Chai", "Chai", "Chai", "Chaai"])
    out, changed = standardize_names(s, cutoff=0.85)
    assert set(out.unique()) == {"Chai"}
    assert changed == 1


def test_outlier_flag():
    s = pd.Series([360.0, 600.0, 1500.0, 1700.0, 50000.0])
    flags = flag_outliers_iqr(s)
    assert flags.tolist() == [False, False, False, False, True]


def test_full_pipeline(messy):
    result = clean_sales(messy)
    st = result.stats
    assert st.rows_in == 9
    assert st.missing_item_dropped == 1
    assert st.quarantined == 2
    assert st.duplicates_removed == 1
    assert st.rows_out == 5
    assert st.outliers_flagged == 1
    # clean frame has no NaNs in key columns and an Amount column
    assert result.clean[["Item", "Qty", "Price", "Amount"]].notna().all().all()
    assert (result.clean["Amount"] == result.clean["Qty"] * result.clean["Price"]).all()


def test_quarantine_keeps_bad_rows(messy):
    result = clean_sales(messy)
    q = result.quarantined
    assert len(q) == 2
    assert set(q["Item"]) == {"Soap", "Tea"}


def test_drop_outliers_config(messy):
    result = clean_sales(messy, CleanConfig(drop_outliers=True))
    assert result.stats.outliers_dropped == 1
    assert "Rice" not in result.clean["Item"].tolist()


def test_sample_csv_integration():
    from sales_automation import load_csv
    raw = load_csv("data/sales_messy.csv")
    result = clean_sales(raw)
    st = result.stats
    assert st.rows_in == 26
    assert st.missing_item_dropped == 1
    assert st.quarantined == 3
    assert st.duplicates_removed == 6
    assert st.names_standardized == 1      # Chaai -> Chai
    assert st.outliers_flagged == 2      # Rice 50000 + Tea 7200 (IQR)
    assert st.rows_out == 16
    # every fuzzy variant collapsed
    assert "Chaai" not in result.clean["Item"].tolist()
    assert "Chai" in result.clean["Item"].tolist()
