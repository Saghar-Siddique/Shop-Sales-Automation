"""Shop Sales Automation — clean messy sales CSVs, get reports & dashboards."""
from .cleaner import (
    CleanConfig,
    CleanResult,
    CleanStats,
    clean_sales,
    load_csv,
)

__all__ = ["CleanConfig", "CleanResult", "CleanStats", "clean_sales", "load_csv"]
__version__ = "1.0.0"
