"""Interactive Sales Automation Dashboard.

Upload a messy sales CSV (or use the built-in sample), tune the cleaning
options live, and explore the results: KPIs, trends, a data-quality report
and the cleaned data itself — downloadable in one click.

Run:  streamlit run dashboard_app.py
"""
from __future__ import annotations

import io

import pandas as pd
import plotly.express as px
import streamlit as st

from sales_automation import CleanConfig, clean_sales, load_csv
from sales_automation.analyzer import daily_trend, kpis, top_items
from sales_automation.reporter import quality_report_text

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

config = CleanConfig(
    remove_duplicates=remove_dupes,
    standardize_names=standardize,
    drop_outliers=drop_outliers,
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

result = clean_sales(raw, config)
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
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No dated transactions to plot.")
    with col2:
        st.subheader("Top items by revenue")
        top = top_items(df, 10)
        if not top.empty:
            fig = px.bar(top, x="Item", y="Amount", text="Amount",
                         labels={"Amount": "Revenue (Rs)"})
            fig.update_traces(textposition="outside")
            st.plotly_chart(fig, use_container_width=True)
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
        st.dataframe(quarantined, use_container_width=True, hide_index=True)

with tab_data:
    st.subheader("Cleaned sales data")
    st.dataframe(df, use_container_width=True, hide_index=True)
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download cleaned CSV", csv_bytes,
                       file_name="sales_clean.csv", mime="text/csv",
                       use_container_width=True)
