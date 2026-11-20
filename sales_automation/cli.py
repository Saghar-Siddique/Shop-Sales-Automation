"""Command-line interface: clean a messy sales CSV in one command.

Example:
    python -m sales_automation.cli data/sales_messy.csv -o out/
"""
from __future__ import annotations

import argparse
from pathlib import Path

from .cleaner import CleanConfig, clean_sales, load_csv
from .analyzer import kpis
from .reporter import quality_report_text, save_report, save_workbook


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
    config = CleanConfig(
        drop_missing_item=not args.keep_missing,
        remove_duplicates=not args.no_dedupe,
        standardize_names=not args.no_standardize,
        drop_outliers=args.drop_outliers,
    )

    raw = load_csv(args.input)
    result = clean_sales(raw, config)

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
