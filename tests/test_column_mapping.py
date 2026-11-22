"""Tests for custom column mapping (Issue #2).

The cleaner expects Date/Item/Qty/Price headers; real shop exports use
different names. A mapping renames them before cleaning, so every
downstream step (dedupe, quarantine, summary, CSV/Excel output) works
unchanged on the mapped data.
"""
import json

import pandas as pd
import pytest

from sales_automation import CleanConfig, clean_sales, load_csv
from sales_automation.cleaner import apply_column_mapping
from sales_automation.cli import (
    load_column_map_file,
    main as cli_main,
    parse_column_map,
)

ALT_MAP = {"date": "Tarikh", "item": "Cheez", "qty": "Miqdar", "price": "Qeemat"}
ALT_MAP_SPEC = "date:Tarikh,item:Cheez,qty:Miqdar,price:Qeemat"


@pytest.fixture
def alt_raw() -> pd.DataFrame:
    return load_csv("data/sales_messy_alt.csv")


@pytest.fixture
def std_result():
    return clean_sales(load_csv("data/sales_messy.csv"))


# ------------------------------------------------------------------ unit ---

def test_apply_column_mapping_renames(alt_raw):
    out = apply_column_mapping(alt_raw, ALT_MAP)
    assert list(out.columns) == ["Date", "Item", "Qty", "Price"]
    assert out.iloc[0]["Item"] == "CHAI"


def test_apply_column_mapping_case_insensitive(alt_raw):
    out = apply_column_mapping(
        alt_raw, {"DATE": "tarikh", "Item": "CHEEZ", "Qty": "miqdar", "Price": "qeemat"})
    assert list(out.columns) == ["Date", "Item", "Qty", "Price"]


def test_apply_column_mapping_missing_column_names_it(alt_raw):
    with pytest.raises(ValueError, match="Tarikh") as excinfo:
        apply_column_mapping(alt_raw, {"date": "Nope", "item": "Cheez"})
    msg = str(excinfo.value)
    assert "Date" in msg                      # the canonical target is named
    assert "Tarikh" in msg                    # ...and the headers found are listed
    assert "Cheez" in msg


def test_apply_column_mapping_unknown_key(alt_raw):
    with pytest.raises(ValueError, match="Unknown column key"):
        apply_column_mapping(alt_raw, {"day": "Tarikh"})


def test_apply_column_mapping_partial_mapping():
    df = pd.DataFrame([{"Tarikh": "2026-10-10", "Item": "Sugar",
                        "Qty": "10", "Price": "100"}])
    out = apply_column_mapping(df, {"date": "Tarikh"})
    assert list(out.columns) == ["Date", "Item", "Qty", "Price"]


def test_apply_column_mapping_collision_errors():
    df = pd.DataFrame([{"Date": "2026-10-10", "Tarikh": "2026-10-11",
                        "Item": "Sugar", "Qty": "10", "Price": "100"}])
    with pytest.raises(ValueError, match="already has a 'Date' column"):
        apply_column_mapping(df, {"date": "Tarikh"})


def test_apply_column_mapping_no_mapping_is_noop(alt_raw):
    assert apply_column_mapping(alt_raw, None) is alt_raw


# -------------------------------------------------------------- pipeline ---

def test_clean_sales_with_mapping_matches_standard(alt_raw, std_result):
    result = clean_sales(alt_raw, CleanConfig(column_mapping=ALT_MAP))
    assert result.stats.as_dict() == std_result.stats.as_dict()
    assert result.clean[["Date", "Item", "Qty", "Price", "Amount"]].equals(
        std_result.clean[["Date", "Item", "Qty", "Price", "Amount"]])
    assert result.quarantined.shape == std_result.quarantined.shape


def test_clean_sales_mapping_extra_columns_ignored():
    df = pd.DataFrame([{"Tarikh": "2026-10-10", "Cheez": "Sugar",
                        "Miqdar": "10", "Qeemat": "100", "Dukaan": "Main"}])
    result = clean_sales(df, CleanConfig(column_mapping=ALT_MAP))
    assert len(result.clean) == 1
    assert "Dukaan" in result.clean.columns  # extra column kept, not an error


# ------------------------------------------------------------------- CLI ---

def test_parse_column_map():
    assert parse_column_map(ALT_MAP_SPEC) == ALT_MAP
    assert parse_column_map(" DATE : Tarikh , Item:Cheez ") == {
        "date": "Tarikh", "item": "Cheez"}


def test_parse_column_map_rejects_bad_input():
    import argparse
    with pytest.raises(argparse.ArgumentTypeError):
        parse_column_map("date-Tarikh")
    with pytest.raises(argparse.ArgumentTypeError):
        parse_column_map("day:Tarikh")
    with pytest.raises(argparse.ArgumentTypeError):
        parse_column_map("date:")


def test_load_column_map_file(tmp_path):
    f = tmp_path / "map.json"
    f.write_text(json.dumps(ALT_MAP))
    assert load_column_map_file(str(f)) == ALT_MAP


def test_load_column_map_file_rejects_bad_json(tmp_path):
    f = tmp_path / "map.json"
    f.write_text("{not json")
    with pytest.raises(ValueError, match="not valid JSON"):
        load_column_map_file(str(f))
    f.write_text(json.dumps(["date", "Tarikh"]))
    with pytest.raises(ValueError, match="must contain a JSON object"):
        load_column_map_file(str(f))


def test_cli_map_inline(tmp_path, std_result):
    out = tmp_path / "out"
    assert cli_main(["data/sales_messy_alt.csv", "-o", str(out),
                     "--map", ALT_MAP_SPEC]) == 0
    assert (out / "sales_clean.csv").exists()
    clean = pd.read_csv(out / "sales_clean.csv")
    assert len(clean) == len(std_result.clean) == 16
    assert (out / "report.txt").read_text().count("Rows read from CSV") == 1


def test_cli_map_file(tmp_path, std_result):
    f = tmp_path / "map.json"
    f.write_text(json.dumps(ALT_MAP))
    out = tmp_path / "out"
    assert cli_main(["data/sales_messy_alt.csv", "-o", str(out),
                     "--map-file", str(f)]) == 0
    clean = pd.read_csv(out / "sales_clean.csv")
    assert len(clean) == len(std_result.clean) == 16
    assert clean.iloc[0]["Item"] == std_result.clean.iloc[0]["Item"]


def test_cli_map_file_xlsx(tmp_path, std_result):
    f = tmp_path / "map.json"
    f.write_text(json.dumps(ALT_MAP))
    out = tmp_path / "out"
    assert cli_main(["data/sales_messy_alt.csv", "-o", str(out),
                     "--map-file", str(f), "--format", "xlsx"]) == 0
    import openpyxl
    wb = openpyxl.load_workbook(out / "sales_clean.xlsx")
    assert wb["Cleaned Data"].max_row == 17  # 16 rows + header
    assert wb["Summary"]["B2"].value == 26


def test_cli_map_wins_over_map_file(tmp_path):
    # --map-file points at a missing header (would fail); --map is correct,
    # so a successful run proves --map wins.
    f = tmp_path / "map.json"
    f.write_text(json.dumps({"date": "Nope", "item": "Cheez"}))
    out = tmp_path / "out"
    assert cli_main(["data/sales_messy_alt.csv", "-o", str(out),
                     "--map-file", str(f), "--map", ALT_MAP_SPEC]) == 0
    assert len(pd.read_csv(out / "sales_clean.csv")) == 16


def test_cli_map_missing_column_fails_cleanly(tmp_path, capsys):
    out = tmp_path / "out"
    assert cli_main(["data/sales_messy_alt.csv", "-o", str(out),
                     "--map", "date:Nope,item:Cheez"]) == 2
    err = capsys.readouterr().err
    assert "Nope" in err
    assert "Tarikh" in err  # found headers are listed


def test_cli_map_bad_spec_exits_2(tmp_path):
    with pytest.raises(SystemExit) as excinfo:
        cli_main(["data/sales_messy_alt.csv", "-o", str(tmp_path / "out"),
                  "--map", "date-Tarikh"])
    assert excinfo.value.code == 2


def test_cli_no_map_default_unchanged(tmp_path):
    out = tmp_path / "out"
    assert cli_main(["data/sales_messy.csv", "-o", str(out)]) == 0
    assert len(pd.read_csv(out / "sales_clean.csv")) == 16


def test_cli_no_map_alt_headers_hint(tmp_path, capsys):
    # No mapping and no canonical headers: runs (nothing crashes) but the
    # user gets a hint pointing at --map / --map-file.
    out = tmp_path / "out"
    assert cli_main(["data/sales_messy_alt.csv", "-o", str(out)]) == 0
    assert "--map" in capsys.readouterr().err
