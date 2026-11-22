"""Shop Sales Automation — clean messy sales CSVs, get reports & dashboards."""
from .cleaner import (
    CANONICAL_COLUMNS,
    CleanConfig,
    CleanResult,
    CleanStats,
    apply_column_mapping,
    clean_sales,
    load_csv,
)

__all__ = ["CANONICAL_COLUMNS", "CleanConfig", "CleanResult", "CleanStats",
           "apply_column_mapping", "clean_sales", "load_csv"]
__version__ = "1.0.0"
