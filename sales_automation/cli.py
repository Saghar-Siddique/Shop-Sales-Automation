"""Command-line interface: clean a messy sales CSV in one command.

Example:
    python -m sales_automation.cli data/sales_messy.csv -o out/
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .cleaner import CANONICAL_COLUMNS, CleanConfig, clean_sales, load_csv_lenient
from .analyzer import kpis
from .reporter import quality_report_text, save_report, save_workbook


def parse_column_map(spec: str) -> dict[str, str]:
    """Parse 'date:Tarikh,item:Cheez' into {'date': 'Tarikh', ...}.

    Raises argparse.ArgumentTypeError on malformed input so argparse
    reports it as a usage error (exit code 2).
    """
    mapping: dict[str, str] = {}
    for pair in spec.split(","):
        pair = pair.strip()
        if not pair:
            continue
        if ":" not in pair:
            raise argparse.ArgumentTypeError(
                f"expected 'canonical:Header' pairs separated by commas, got "
                f"{pair!r} (e.g. --map date:Tarikh,item:Cheez)"
            )
        key, actual = pair.split(":", 1)
        key = key.strip().lower()
        actual = actual.strip()
        if key not in CANONICAL_COLUMNS:
            raise argparse.ArgumentTypeError(
                f"unknown column key {key!r}; expected one of: "
                f"{', '.join(sorted(CANONICAL_COLUMNS))}"
            )
        if not actual:
            raise argparse.ArgumentTypeError(f"empty header name for column {key!r}")
        mapping[key] = actual
    if not mapping:
        raise argparse.ArgumentTypeError(
            "empty mapping — expected 'canonical:Header' pairs")
    return mapping


def load_column_map_file(path: str) -> dict[str, str]:
    """Load a JSON column mapping, e.g. {"date": "Tarikh", "item": "Cheez"}."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except OSError as exc:
        raise ValueError(f"Cannot read mapping file {path!r}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Mapping file {path!r} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(
            f"Mapping file {path!r} must contain a JSON object, "
            f"got {type(data).__name__}.")
    mapping: dict[str, str] = {}
    for key, actual in data.items():
        k = str(key).strip().lower()
        if k not in CANONICAL_COLUMNS:
            raise ValueError(
                f"Unknown column key {key!r} in mapping file {path!r}; "
                f"expected one of: {', '.join(sorted(CANONICAL_COLUMNS))}.")
        if not isinstance(actual, str) or not actual.strip():
            raise ValueError(
                f"Mapping file {path!r}: header for {k!r} must be a "
                f"non-empty string.")
        mapping[k] = actual.strip()
    if not mapping:
        raise ValueError(f"Mapping file {path!r} contains no column mappings.")
    return mapping


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Clean a messy shop sales CSV and generate a report.")
    p.add_argument("input", help="Path to the messy sales CSV file")
    p.add_argument("-o", "--output-dir", default="out",
                   help="Where to write the outputs (default: out/)")
    p.add_argument("--format", choices=["csv", "xlsx"], default="csv",
                   help="Output format for the cleaned data: csv writes "
                        "sales_clean.csv (+ quarantined.csv), xlsx writes a "
                        "sales_clean.xlsx workbook with Cleaned Data, Summary "
                        "and Quarantined sheets (default: csv)")
    p.add_argument("--map", dest="map", default=None, metavar="KEY:HEADER,...",
                   type=parse_column_map,
                   help="Map non-standard CSV headers to Date/Item/Qty/Price, "
                        "e.g. --map date:Tarikh,item:Cheez,qty:Miqdar,price:Qeemat. "
                        "Matching is case-insensitive. If both --map and "
                        "--map-file are given, --map wins.")
    p.add_argument("--map-file", default=None, metavar="FILE",
                   help="JSON file with the same mapping, e.g. "
                        '{"date": "Tarikh", "item": "Cheez"}. '
                        "If both --map and --map-file are given, --map wins.")
    p.add_argument("--no-dedupe", action="store_true",
                   help="Keep duplicate rows")
    p.add_argument("--no-standardize", action="store_true",
                   help="Skip fuzzy item-name standardization")
    p.add_argument("--drop-outliers", action="store_true",
                   help="Drop outlier rows instead of just flagging them")
    p.add_argument("--keep-missing", action="store_true",
                   help="Keep rows with a missing item name")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    # --map wins over --map-file when both are given.
    mapping = args.map
    if mapping is None and args.map_file:
        try:
            mapping = load_column_map_file(args.map_file)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2

    config = CleanConfig(
        drop_missing_item=not args.keep_missing,
        remove_duplicates=not args.no_dedupe,
        standardize_names=not args.no_standardize,
        drop_outliers=args.drop_outliers,
        column_mapping=mapping,
    )

    try:
        raw, skipped_rows = load_csv_lenient(args.input)
    except OSError as exc:
        print(f"Error: Cannot read input file {args.input!r}: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    if skipped_rows:
        print(f"Warning: skipped {len(skipped_rows)} malformed row(s) "
              "(wrong number of fields) — see the report.", file=sys.stderr)
    if mapping is None:
        present = {str(c).strip().lower() for c in raw.columns}
        if not present & {"date", "item", "qty", "price"}:
            print("Hint: none of the expected columns (Date, Item, Qty, Price) "
                  "found in the CSV — if it uses different headers, map them "
                  "with --map or --map-file (see README).", file=sys.stderr)

    try:
        result = clean_sales(raw, config)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    result.stats.malformed_skipped = len(skipped_rows)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "report.txt"
    if args.format == "xlsx":
        clean_path = out_dir / "sales_clean.xlsx"
        save_workbook(result.clean, result.stats, kpis(result.clean),
                      result.quarantined, clean_path)
    else:
        clean_path = out_dir / "sales_clean.csv"
        result.clean.to_csv(clean_path, index=False)
        if not result.quarantined.empty:
            result.quarantined.to_csv(out_dir / "quarantined.csv", index=False)

    report = quality_report_text(result.stats, kpis(result.clean),
                                 len(result.quarantined))
    save_report(report, str(report_path))

    print(report)
    print(f"\n[OK] {clean_path} and {report_path} written.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
