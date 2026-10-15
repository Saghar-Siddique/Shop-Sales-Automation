"""Human-readable reports from cleaning stats + KPIs."""
from __future__ import annotations

from .cleaner import CleanStats


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
