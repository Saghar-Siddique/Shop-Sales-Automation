# 🏪 Shop Sales Automation

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![pandas](https://img.shields.io/badge/pandas-150458?logo=pandas&logoColor=white)](https://pandas.pydata.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![Tests](https://img.shields.io/badge/tests-14%20passed-brightgreen)]()

**Messy sales CSV in — clean data, quality report & dashboard out.**

A professional data-cleaning pipeline for small shops: it takes the kind of
messy sales records shopkeepers actually keep (missing values, " CHAI " vs
"chai", `Rs 1,200` prices, mixed date formats, duplicates, outliers) and
turns them into trustworthy data — with a full report of everything it fixed.
Nothing is deleted silently: bad rows go to quarantine for review.

**Perfect for:** retail shops, distributors, and small businesses that track
sales in Excel/CSV and need reliable numbers without manual cleanup.

## What it cleans

| Mess | Handling |
|---|---|
| Missing item names | Dropped (counted in report) |
| Unparseable / negative Qty / Price | **Quarantined** to a separate CSV for review |
| `" CHAI "` vs `"chai"` vs `"Chaai"` | Stripped + fuzzy-standardized to one name |
| `"Rs 1,200"`, `"$5"` | Currency symbols stripped → numbers |
| `12/10/2026`, `Oct 13 2026` | Mixed date formats parsed |
| Exact duplicates | Removed (counted) |
| Outliers (IQR rule) | Flagged by default, optionally dropped |

## Quickstart

```bash
pip install -r requirements.txt

# CLI: clean the sample messy file
python -m sales_automation.cli data/sales_messy.csv -o out/

# Interactive dashboard
streamlit run dashboard_app.py
```

CLI options: `--no-dedupe`, `--no-standardize`, `--drop-outliers`,
`--keep-missing`, `-o/--output-dir`.

## Interactive dashboard

- 📤 Upload your own CSV **or** use the built-in messy sample
- ⚙️ Toggle every cleaning rule live in the sidebar and watch results change
- 📊 KPIs, daily trend & top-items charts (Plotly)
- 🧹 Data-quality tab: exactly what was fixed, dropped or quarantined
- ⬇️ One-click download of the cleaned CSV

## Project structure

```
sales_automation/
  cleaner.py     # pandas cleaning pipeline (CleanConfig / CleanResult)
  analyzer.py    # KPIs, daily trend, top items
  reporter.py    # plain-text quality report
  cli.py         # argparse entry point
dashboard_app.py # Streamlit dashboard
tests/           # pytest suite (cleaner, analyzer, CLI)
data/
  sales_messy.csv  # 26-row sample with 8 kinds of mess
requirements.txt
```

## Sample data

`data/sales_messy.csv` (26 rows) contains: missing values, case/space
variants, a fuzzy typo (`Chaai`), currency-formatted prices, mixed date
formats, 5 duplicate pairs, bad/negative numbers and a price outlier —
so every feature is demonstrable in one run.

## Tests

```bash
pytest -q
```
