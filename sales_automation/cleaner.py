"""Advanced sales-data cleaning pipeline.

Takes messy shop sales CSVs (missing values, inconsistent names, currency
symbols, bad numbers, mixed date formats, duplicates, outliers) and returns
a clean DataFrame plus a full data-quality report.

Nothing is silently thrown away: unparseable rows go to a quarantine
DataFrame so the user can review them.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from difflib import get_close_matches
import re

import pandas as pd


# ---------------------------------------------------------------------------
# Config & results
# ---------------------------------------------------------------------------

@dataclass
class CleanConfig:
    """Toggles for the cleaning pipeline."""
    drop_missing_item: bool = True
    remove_duplicates: bool = True
    standardize_names: bool = True
    name_similarity_cutoff: float = 0.85
    drop_outliers: bool = False          # False = flag only, keep the row
    date_column: str = "Date"
    item_column: str = "Item"
    qty_column: str = "Qty"
    price_column: str = "Price"


@dataclass
class CleanStats:
    rows_in: int = 0
    rows_out: int = 0
    missing_item_dropped: int = 0
    quarantined: int = 0
    duplicates_removed: int = 0
    names_standardized: int = 0
    outliers_flagged: int = 0
    outliers_dropped: int = 0

    def as_dict(self) -> dict:
        return {
            "Rows read": self.rows_in,
            "Rows after cleaning": self.rows_out,
            "Dropped (missing item)": self.missing_item_dropped,
            "Quarantined (bad nums)": self.quarantined,
            "Duplicates removed": self.duplicates_removed,
            "Item names standardized": self.names_standardized,
            "Outliers flagged": self.outliers_flagged,
            "Outliers dropped": self.outliers_dropped,
        }


@dataclass
class CleanResult:
    clean: pd.DataFrame
    quarantined: pd.DataFrame
    stats: CleanStats = field(default_factory=CleanStats)


# ---------------------------------------------------------------------------
# Individual cleaning steps
# ---------------------------------------------------------------------------

_CURRENCY_RE = re.compile(r"(?i)\b(rs|pkr|usd)\b|[$€£]")


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().title() for c in df.columns]
    return df


def strip_text(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    df = df.copy()
    for col in columns:
        if col in df.columns:
            df[col] = df[col].astype("string").str.strip()
            df[col] = df[col].replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})
    return df


def strip_currency(series: pd.Series) -> pd.Series:
    """'Rs 1,200' -> 1200.0 ; unparseable -> NaN (always Float64)."""
    s = series.astype("string").str.strip()
    s = s.str.replace(_CURRENCY_RE, "", regex=True)
    s = s.str.replace(",", "", regex=False).str.strip()
    return pd.to_numeric(s, errors="coerce").astype("Float64")


def coerce_qty(series: pd.Series) -> pd.Series:
    """'5' -> 5 ; 'two' -> NaN ; 5.0 -> 5 (nullable Int64)."""
    numeric = pd.to_numeric(series.astype("string").str.strip(), errors="coerce")
    return numeric.round().astype("Int64")


def parse_dates(series: pd.Series) -> pd.Series:
    """Parse mixed formats, Pakistani DD/MM/YYYY first.

    Pass 1 uses dayfirst (so 12/10/2026 -> 12 Oct, not 10 Dec).
    Leftovers (ISO, 'Oct 13 2026', ...) go through a second pass.
    """
    s = series.astype("string").str.strip()
    parsed = pd.to_datetime(s, dayfirst=True, errors="coerce")
    mask = parsed.isna() & s.notna() & (s != "")
    if mask.any():
        parsed = parsed.copy()
        parsed[mask] = pd.to_datetime(s[mask], format="mixed", errors="coerce")
    return parsed


def standardize_names(series: pd.Series, cutoff: float = 0.85) -> tuple[pd.Series, int]:
    """Fuzzy-map variants (' CHAI ', 'chai', 'Chai') to the most common form."""
    counts = series.value_counts()
    mapping: dict[str, str] = {}
    for name in counts.index:
        if name in mapping:
            continue
        matches = get_close_matches(name, counts.index.tolist(), n=10, cutoff=cutoff)
        canonical = max(matches, key=lambda m: counts[m]) if matches else name
        for m in matches:
            mapping[m] = canonical
    result = series.map(lambda x: mapping.get(x, x))
    changed = int((result != series).sum())
    return result, changed


def flag_outliers_iqr(series: pd.Series) -> pd.Series:
    """IQR rule: outside [Q1 - 1.5*IQR, Q3 + 1.5*IQR] -> True."""
    q1, q3 = series.quantile(0.25), series.quantile(0.75)
    iqr = q3 - q1
    if iqr == 0 or pd.isna(iqr):
        return pd.Series(False, index=series.index)
    lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    return (series < lower) | (series > upper)


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------

def clean_sales(raw: pd.DataFrame, config: CleanConfig | None = None) -> CleanResult:
    """Run the full cleaning pipeline. Returns clean + quarantined + stats."""
    config = config or CleanConfig()
    stats = CleanStats(rows_in=len(raw))
    df = normalize_columns(raw)

    date_c, item_c = config.date_column, config.item_column
    qty_c, price_c = config.qty_column, config.price_column

    df = strip_text(df, [c for c in [item_c, date_c] if c in df.columns])

    # Title-case item names first so fuzzy matching compares like with like.
    if item_c in df.columns:
        df[item_c] = df[item_c].str.title()

    # Numeric coercion (currency symbols stripped from Price).
    df["_qty"] = coerce_qty(df[qty_c]) if qty_c in df.columns else pd.NA
    df["_price"] = strip_currency(df[price_c]) if price_c in df.columns else pd.NA
    df["_date"] = parse_dates(df[date_c]) if date_c in df.columns else pd.NaT

    # 1) Drop rows with no item name.
    if config.drop_missing_item and item_c in df.columns:
        missing = df[item_c].isna()
        stats.missing_item_dropped = int(missing.sum())
        df = df[~missing]

    # 2) Quarantine bad numbers (unparseable or negative).
    bad = df["_qty"].isna() | df["_price"].isna() | (df["_qty"] < 0) | (df["_price"] < 0)
    quarantined = df[bad].drop(columns=["_qty", "_price", "_date"], errors="ignore")
    stats.quarantined = len(quarantined)
    df = df[~bad].copy()
    df[qty_c] = df["_qty"].astype("int64")
    df[price_c] = df["_price"].astype("float64")
    df[date_c] = df["_date"]
    df = df.drop(columns=["_qty", "_price", "_date"])

    # 3) Fuzzy-standardize item names.
    if config.standardize_names and item_c in df.columns:
        df[item_c], stats.names_standardized = standardize_names(
            df[item_c], cutoff=config.name_similarity_cutoff)

    # 4) Remove exact duplicates.
    if config.remove_duplicates:
        before = len(df)
        df = df.drop_duplicates(subset=[c for c in [date_c, item_c, qty_c, price_c]
                                        if c in df.columns])
        stats.duplicates_removed = before - len(df)

    # 5) Amount + outliers.
    df["Amount"] = df[qty_c] * df[price_c]
    outlier_mask = flag_outliers_iqr(df["Amount"])
    stats.outliers_flagged = int(outlier_mask.sum())
    df["Outlier"] = outlier_mask
    if config.drop_outliers:
        stats.outliers_dropped = int(outlier_mask.sum())
        df = df[~outlier_mask].copy()

    stats.rows_out = len(df)
    df = df.reset_index(drop=True)
    return CleanResult(clean=df, quarantined=quarantined.reset_index(drop=True), stats=stats)


def load_csv(path: str) -> pd.DataFrame:
    """Read a CSV with everything as text (coercion happens in the pipeline)."""
    return pd.read_csv(path, dtype=str, keep_default_na=True)
