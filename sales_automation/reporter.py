"""Human-readable reports from cleaning stats + KPIs."""
from __future__ import annotations

import pandas as pd

from .cleaner import CleanStats


def summary_rows(stats: CleanStats, kpis: dict, quarantined_count: int = 0) -> list[tuple[str, object]]:
    """Metric/value rows for the Summary sheet — same numbers as the text report."""
    q = stats.as_dict()
    rows = [
        ("Rows read from CSV", q["Rows read"]),
        ("Rows after cleaning", q["Rows after cleaning"]),
        ("Dropped (missing item)", q["Dropped (missing item)"]),
        ("Quarantined (bad nums)", q["Quarantined (bad nums)"]),
        ("Duplicates removed", q["Duplicates removed"]),
        ("Item names standardized", q["Item names standardized"]),
        ("Outliers flagged", q["Outliers flagged"]),
        ("Outliers dropped", q["Outliers dropped"]),
        ("Transactions", kpis["transactions"]),
        ("Total Sales (Rs)", kpis["total_sales"]),
        ("Total Qty Sold (pcs)", kpis["total_qty"]),
        ("Average Bill (Rs)", kpis["avg_bill"]),
        ("Top Selling Item", kpis["top_item"]),
    ]
    if quarantined_count:
        rows.append(("Quarantined rows (review)", quarantined_count))
    return rows


def save_workbook(clean_df: pd.DataFrame, stats: CleanStats, kpis: dict,
                  quarantined: pd.DataFrame, path) -> None:
    """Write a .xlsx workbook: Cleaned Data + Summary (+ Quarantined).

    ``path`` may be a file path or a binary file-like object (BytesIO).
    The Quarantined sheet is only written when there are quarantined rows,
    matching the CSV behaviour (quarantined.csv is only written then).
    """
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        clean_df.to_excel(writer, sheet_name="Cleaned Data", index=False)
        summary = pd.DataFrame(summary_rows(stats, kpis, len(quarantined)),
                               columns=["Metric", "Value"])
        summary.to_excel(writer, sheet_name="Summary", index=False)
        if not quarantined.empty:
            quarantined.to_excel(writer, sheet_name="Quarantined", index=False)


def quality_report_text(stats: CleanStats, kpis: dict, quarantined_count: int = 0) -> str:
    """Plain-text report: data-quality section first, business summary after."""
    q = stats.as_dict()
    lines = [
        "===== DATA QUALITY REPORT =====",
        f"Rows read from CSV      : {q['Rows read']}",
        f"Rows after cleaning     : {q['Rows after cleaning']}",
        f"Dropped (missing item)  : {q['Dropped (missing item)']}",
        f"Quarantined (bad nums)  : {q['Quarantined (bad nums)']}",
        f"Duplicates removed      : {q['Duplicates removed']}",
        f"Item names standardized : {q['Item names standardized']}",
        f"Outliers flagged        : {q['Outliers flagged']}",
        f"Outliers dropped        : {q['Outliers dropped']}",
        "",
        "===== SALES SUMMARY =====",
        f"Transactions            : {kpis['transactions']}",
        f"Total Sales             : Rs {kpis['total_sales']:,.0f}",
        f"Total Qty Sold          : {kpis['total_qty']} pcs",
        f"Average Bill            : Rs {kpis['avg_bill']:,.0f}",
        f"Top Selling Item        : {kpis['top_item']}",
    ]
    if quarantined_count:
        lines += ["",
                  f"NOTE: {quarantined_count} row(s) were quarantined for review",
                  "(unparseable or negative Qty/Price) — nothing was deleted silently."]
    return "\n".join(lines)


def save_report(text: str, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
