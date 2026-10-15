"""Sales analysis: KPIs, trends and rankings from clean sales data."""
from __future__ import annotations

import pandas as pd


def kpis(df: pd.DataFrame) -> dict:
    """Headline numbers for the dashboard."""
    if df.empty:
        return {"total_sales": 0.0, "total_qty": 0, "transactions": 0,
                "top_item": "—", "avg_bill": 0.0}
    item_sales = df.groupby("Item")["Amount"].sum()
    return {
        "total_sales": float(df["Amount"].sum()),
        "total_qty": int(df["Qty"].sum()),
        "transactions": int(len(df)),
        "top_item": str(item_sales.idxmax()),
        "avg_bill": float(df["Amount"].mean()),
    }


def daily_trend(df: pd.DataFrame) -> pd.DataFrame:
    """Total sales per day, sorted by date."""
    if df.empty or "Date" not in df.columns:
        return pd.DataFrame(columns=["Date", "Amount"])
    out = (df.dropna(subset=["Date"])
             .groupby("Date", as_index=False)["Amount"].sum()
             .sort_values("Date"))
    return out


def top_items(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """Top n items by revenue."""
    if df.empty:
        return pd.DataFrame(columns=["Item", "Qty", "Amount"])
    out = (df.groupby("Item", as_index=False)
             .agg(Qty=("Qty", "sum"), Amount=("Amount", "sum"))
             .sort_values("Amount", ascending=False)
             .head(n))
    return out
