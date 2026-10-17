"""Cleaner accuracy eval for Shop-Sales-Automation.

Tough, adversarial cases: fuzzy-merge traps (incl. a suspected
mapping-overwrite chain bug), false-merge traps (similar names that are
different products), quarantine edge cases, currency quirks ('Rs. 1,200'),
fractional quantities, garbage dates, and duplicates.

  python evals/run_cleaner_eval.py

Dataset: evals/cleaner_cases.csv — every row carries its ground truth
(expected_verdict / expected_item / expected_qty / expected_price /
expected_date) plus a notes column. Cases whose notes start with
'ADVISORY' are reported separately: they document known design
trade-offs, not pass/fail.

Scoring per case:
  expected_verdict 'clean'       -> row must survive in the clean output
                                   AND item/qty/price/date must match
  expected_verdict 'quarantined' -> row must land in the quarantine output
  expected_verdict 'dropped'     -> row must appear in NEITHER output
Reports overall accuracy, per-bucket accuracy, and every failure with
expected vs got.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from sales_automation.cleaner import clean_sales, load_csv  # noqa: E402

CASES = Path(__file__).with_name("cleaner_cases.csv")


def load_cases(path: Path = CASES) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def norm_date(ts) -> str:
    if pd.isna(ts):
        return "NaT"
    return pd.Timestamp(ts).date().isoformat()


def check(case: dict, clean: pd.DataFrame, quar: pd.DataFrame) -> tuple[bool, str]:
    cid = case["case_id"]
    in_clean = clean[clean["Case_Id"] == cid]
    in_quar = quar[quar["Case_Id"] == cid]
    verdict = case["expected_verdict"]

    if verdict == "quarantined":
        if len(in_quar) == 1 and len(in_clean) == 0:
            return True, ""
        return False, f"expected quarantined, got clean={len(in_clean)} quar={len(in_quar)}"
    if verdict == "dropped":
        if len(in_clean) == 0 and len(in_quar) == 0:
            return True, ""
        where = "clean" if len(in_clean) else "quarantine"
        return False, f"expected dropped, row survived in {where}"
    # verdict == "clean"
    if len(in_clean) != 1:
        return False, f"expected 1 clean row, found {len(in_clean)}"
    row = in_clean.iloc[0]
    problems = []
    if case["expected_item"] and str(row["Item"]) != case["expected_item"]:
        problems.append(f"item: expected {case['expected_item']!r}, got {row['Item']!r}")
    if case["expected_qty"] and str(row["Qty"]) != case["expected_qty"]:
        problems.append(f"qty: expected {case['expected_qty']!r}, got {row['Qty']!r}")
    if case["expected_price"] and abs(float(row["Price"]) - float(case["expected_price"])) > 0.01:
        problems.append(f"price: expected {case['expected_price']!r}, got {row['Price']!r}")
    if case["expected_date"] and norm_date(row["Date"]) != case["expected_date"]:
        problems.append(f"date: expected {case['expected_date']!r}, got {norm_date(row['Date'])!r}")
    if problems:
        return False, "; ".join(problems)
    return True, ""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default=str(CASES))
    a = ap.parse_args()

    cases = load_cases(Path(a.cases))
    raw = load_csv(a.cases)
    result = clean_sales(raw)
    clean, quar = result.clean, result.quarantined

    buckets: dict[str, list[int]] = {}
    fails: list[tuple[dict, str]] = []
    advisories: list[tuple[dict, str]] = []
    for case in cases:
        ok, detail = check(case, clean, quar)
        b = buckets.setdefault(case["bucket"], [0, 0])
        b[1] += 1
        if ok:
            b[0] += 1
        else:
            fails.append((case, detail))
        if case["notes"].startswith("ADVISORY"):
            advisories.append((case, "PASS" if ok else f"FAIL: {detail}"))

    total_ok = sum(v[0] for v in buckets.values())
    total = sum(v[1] for v in buckets.values())
    print(f"Overall: {total_ok}/{total} = {round(100 * total_ok / total)}%")
    for name, (ok, n) in buckets.items():
        print(f"  {name:<15} {ok}/{n}")
    print()
    for case, detail in fails:
        print(f"FAIL [{case['bucket']}] {case['case_id']}: "
              f"in=({case['Item']!r}, qty={case['Qty']!r}, price={case['Price']!r})")
        print(f"  expected: verdict={case['expected_verdict']}"
              + (f", item={case['expected_item']!r}" if case["expected_item"] else "")
              + (f", qty={case['expected_qty']!r}" if case["expected_qty"] else "")
              + (f", price={case['expected_price']!r}" if case["expected_price"] else ""))
        print(f"  got: {detail}")
        if case["notes"]:
            print(f"  note: {case['notes']}")
    if advisories:
        print("\nAdvisories (design trade-offs, not failures):")
        for case, status in advisories:
            print(f"  [{status}] {case['case_id']}: {case['notes'][9:].strip()}")


if __name__ == "__main__":
    main()
