"""Interactive Sales Automation Dashboard.

Upload a messy sales CSV (or use the built-in sample), tune the cleaning
options live, and explore the results: KPIs, trends, a data-quality report
and the cleaned data itself — downloadable in one click.

Run:  streamlit run dashboard_app.py
"""
from __future__ import annotations

import argparse
import io

import pandas as pd
import plotly.express as px
import streamlit as st

from sales_automation import CleanConfig, clean_sales, load_csv
from sales_automation.analyzer import daily_trend, kpis, top_items
from sales_automation.cli import parse_column_map
from sales_automation.reporter import quality_report_text, save_workbook

st.set_page_config(page_title="Sales Automation Dashboard", page_icon="🏪", layout="wide")
st.title("🏪 Shop Sales Automation")
st.caption("Messy sales CSV in — clean data, report & dashboard out.")

# ---------------------------------------------------------------- sidebar ---
st.sidebar.header("⚙️ Cleaning options")
use_sample = st.sidebar.checkbox("Use sample messy data", value=True)
uploaded = st.sidebar.file_uploader("...or upload your own CSV", type=["csv"])

remove_dupes = st.sidebar.checkbox("Remove duplicates", value=True)
standardize = st.sidebar.checkbox("Standardize item names (fuzzy)", value=True)
drop_outliers = st.sidebar.checkbox("Drop outliers (else just flag)", value=False)
map_spec = st.sidebar.text_input(
    "Column mapping (optional)",
    value="",
    placeholder="date:Tarikh, item:Cheez",
    help="If your CSV uses different headers, map them to Date/Item/Qty/Price, "
         "e.g. date:Tarikh,item:Cheez,qty:Miqdar,price:Qeemat. Case-insensitive.",
)

mapping = None
if map_spec.strip():
    try:
        mapping = parse_column_map(map_spec)
    except argparse.ArgumentTypeError as exc:
        st.error(f"⚠️ Invalid column mapping: {exc}")
        st.stop()

config = CleanConfig(
    remove_duplicates=remove_dupes,
    standardize_names=standardize,
    drop_outliers=drop_outliers,
    column_mapping=mapping,
)

# ------------------------------------------------------------------ data ---
@st.cache_data(show_spinner=False)
def load_raw(use_sample: bool, uploaded_name: str | None, uploaded_bytes: bytes | None) -> pd.DataFrame:
    if uploaded_bytes is not None:
        return pd.read_csv(io.BytesIO(uploaded_bytes), dtype=str)
    return load_csv("data/sales_messy.csv")

raw = load_raw(use_sample, uploaded.name if uploaded else None,
               uploaded.getvalue() if uploaded else None)
if not use_sample and uploaded is None:
    st.info("👆 Upload a CSV in the sidebar, or tick 'Use sample messy data'.")
    st.stop()

try:
    result = clean_sales(raw, config)
except ValueError as exc:
    st.error(f"⚠️ {exc}")
    st.stop()
if mapping is None:
    present = {str(c).strip().lower() for c in raw.columns}
    if not present & {"date", "item", "qty", "price"}:
        st.warning("⚠️ None of the expected columns (Date, Item, Qty, Price) "
                   "were found in this CSV — if it uses different headers, "
                   "map them in 'Column mapping (optional)' in the sidebar.")
df, stats, quarantined = result.clean, result.stats, result.quarantined
k = kpis(df)

# -------------------------------------------------------------------- KPIs ---
c1, c2, c3, c4 = st.columns(4)
c1.metric("💰 Total Sales", f"Rs {k['total_sales']:,.0f}")
c2.metric("🧾 Transactions", f"{k['transactions']}")
c3.metric("🏆 Top Item", k["top_item"])
c4.metric("🧹 Rows cleaned", f"{stats.rows_in} → {stats.rows_out}")
st.divider()

tab_dash, tab_quality, tab_data = st.tabs(["📊 Dashboard", "🧹 Data Quality", "🗂️ Cleaned Data"])

with tab_dash:
    trend = daily_trend(df)
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Daily sales trend")
        if not trend.empty:
            fig = px.line(trend, x="Date", y="Amount", markers=True,
                          labels={"Amount": "Sales (Rs)"})
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("No dated transactions to plot.")
    with col2:
        st.subheader("Top items by revenue")
        top = top_items(df, 10)
        if not top.empty:
            fig = px.bar(top, x="Item", y="Amount", text="Amount",
                         labels={"Amount": "Revenue (Rs)"})
            fig.update_traces(textposition="outside")
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("No items to rank.")

with tab_quality:
    st.subheader("What the cleaner did")
    q1, q2, q3, q4 = st.columns(4)
    q1.metric("Duplicates removed", stats.duplicates_removed)
    q2.metric("Names standardized", stats.names_standardized)
    q3.metric("Quarantined", stats.quarantined)
    q4.metric("Outliers flagged", stats.outliers_flagged)
    st.text(quality_report_text(stats, k, len(quarantined)))
    if not quarantined.empty:
        st.subheader("⚠️ Quarantined rows (review before deleting)")
        st.dataframe(quarantined, width="stretch", hide_index=True)

with tab_data:
    st.subheader("Cleaned sales data")
    st.dataframe(df, width="stretch", hide_index=True)
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download cleaned CSV", csv_bytes,
                       file_name="sales_clean.csv", mime="text/csv",
                       width="stretch")
    xlsx_buffer = io.BytesIO()
    save_workbook(df, stats, k, quarantined, xlsx_buffer)
    st.download_button("⬇️ Download cleaned Excel (.xlsx)", xlsx_buffer.getvalue(),
                       file_name="sales_clean.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       width="stretch")
