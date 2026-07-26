"""
Data validation module: structure and quality checks on raw datasets.

Two tiers, on purpose:
  - Structure (validate_structure / check_structure): required columns and
    at least one row. A violation here means the pipeline cannot proceed
    sensibly, so it raises SchemaValidationError and stops.
  - Quality (validate_all): missing values, duplicates, out-of-range
    ratings, orphaned foreign keys. These are logged as warnings and the
    pipeline keeps going - transform.py cleans what it can, and whatever
    remains is reported in the data quality report rather than blocking
    the run.

All checks are read-only: they never mutate the data themselves.
"""

import logging
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


class SchemaValidationError(Exception):
    """
    Raised when a dataset is missing a required column or has no rows.
    Unlike the issues in validate_all() (nulls, duplicates, out-of-range
    values, orphan foreign keys), these are contract violations, not dirty
    data: there's no reasonable way to clean or aggregate around a column
    that doesn't exist, so the pipeline fails fast here instead of letting
    a broken structure flow silently into transform/load.
    """


REQUIRED_COLUMNS = {
    'products': ['product_id', 'product_name', 'category', 'num_ingredients'],
    'sales': ['transaction_id', 'product_id', 'customer_id', 'total_amount_usd'],
    'feedback': ['feedback_id', 'product_id', 'customer_id', 'quality_rating', 'overall_satisfaction'],
    'ingredients': ['ingredient_id', 'ingredient_name', 'cost_per_kg_usd'],
}


def _check_schema(name: str, df: pd.DataFrame) -> list[str]:
    missing = [c for c in REQUIRED_COLUMNS[name] if c not in df.columns]
    return [f"missing required column '{c}'" for c in missing]


def _check_not_empty(df: pd.DataFrame) -> list[str]:
    return ["dataset is empty (0 rows)"] if df.empty else []


def check_structure(data: dict[str, pd.DataFrame]) -> dict[str, list[str]]:
    """
    Structural checks only: required columns present, at least one row.
    Read-only, like every other check in this module - it never mutates
    `data` or raises by itself. Raising is validate_structure()'s job.
    """
    return {
        name: _check_schema(name, df) + _check_not_empty(df)
        for name, df in data.items()
    }


def validate_structure(data: dict[str, pd.DataFrame]) -> None:
    """
    Hard gate: stop the pipeline immediately if any dataset is missing a
    required column or has zero rows, instead of letting validate_all()
    log it as one warning among many and continuing anyway. Call this
    right after extract_all() (and again after transform_all(), as a
    safety net) - before doing any further work on data whose shape can't
    be trusted.

    Raises:
        SchemaValidationError: naming every dataset and issue found, so the
            failure is visible in one place instead of buried in a log.
    """
    structure_report = check_structure(data)
    failures = [
        f"[{dataset}] {issue}"
        for dataset, issues in structure_report.items()
        for issue in issues
    ]
    if not failures:
        return

    for failure in failures:
        logger.error(failure)

    raise SchemaValidationError(
        "Data does not match the required structure - fix the source file(s) "
        "or config['paths'] and re-run. Failures:\n  " + "\n  ".join(failures)
    )


def _check_nulls(df: pd.DataFrame, columns: list[str]) -> list[str]:
    issues = []
    for col in columns:
        if col not in df.columns:
            continue
        n = int(df[col].isna().sum())
        if n:
            issues.append(f"{n} null value(s) in '{col}'")
    return issues


def _check_duplicates(df: pd.DataFrame, id_col: str) -> list[str]:
    if id_col not in df.columns:
        return []
    n = int(df[id_col].duplicated().sum())
    return [f"{n} duplicate '{id_col}' value(s)"] if n else []


def _check_range(df: pd.DataFrame, col: str, min_val: float, max_val: float | None = None) -> list[str]:
    if col not in df.columns:
        return []
    below = df[col] < min_val
    above = (df[col] > max_val) if max_val is not None else False
    out_of_range = df[col].notna() & (below | above)
    n = int(out_of_range.sum())
    bound = f"[{min_val}, {max_val}]" if max_val is not None else f">= {min_val}"
    return [f"{n} value(s) in '{col}' outside {bound}"] if n else []


def _check_referential_integrity(df: pd.DataFrame, fk_col: str, valid_ids: pd.Series) -> list[str]:
    if fk_col not in df.columns:
        return []
    orphans = df[fk_col].notna() & (~df[fk_col].isin(valid_ids))
    n = int(orphans.sum())
    return [f"{n} '{fk_col}' value(s) not found in products"] if n else []


def _check_dates(df: pd.DataFrame, col: str) -> list[str]:
    """
    Flag values that don't parse as a date under mixed-format inference
    (e.g. '7/15/2024' or '07-18-2024' mixed into a mostly-ISO 'YYYY-MM-DD'
    column). Raw string columns, not yet parsed - this runs on extract_all()
    output, before transform.py converts them to datetime64.
    """
    if col not in df.columns:
        return []
    parsed = pd.to_datetime(df[col], format='mixed', errors='coerce')
    unparseable = df[col].notna() & parsed.isna()
    n = int(unparseable.sum())
    return [f"{n} unparseable date value(s) in '{col}'"] if n else []


def validate_all(data: dict[str, pd.DataFrame], thresholds: dict[str, Any] | None = None) -> dict[str, list[str]]:
    """
    Run data-quality checks (not structural ones - see validate_structure())
    on the raw datasets returned by extract_all().

    Args:
        data: Dict with keys 'products', 'sales', 'feedback', 'ingredients'.
        thresholds: Optional dict with 'rating_min' / 'rating_max', typically
            sourced from pipeline_config.yaml's quality_thresholds section.

    Returns:
        Dict mapping each dataset name to a list of human-readable issue
        descriptions found in it (empty list if the dataset is clean).
    """
    thresholds = thresholds or {}
    rating_min = thresholds.get('rating_min', 0)
    rating_max = thresholds.get('rating_max', 5)

    products = data['products']
    sales = data['sales']
    feedback = data['feedback']
    ingredients = data['ingredients']

    report: dict[str, list[str]] = {
        'products': (
            _check_nulls(products, ['product_name', 'category', 'num_ingredients'])
            + _check_duplicates(products, 'product_id')
            + _check_dates(products, 'launch_date')
            + _check_range(products, 'num_ingredients', min_val=0)
        ),
        'sales': (
            _check_nulls(sales, ['customer_id', 'total_amount_usd'])
            + _check_duplicates(sales, 'transaction_id')
            + _check_referential_integrity(sales, 'product_id', products['product_id'])
            + _check_dates(sales, 'transaction_date')
        ),
        'feedback': (
            _check_nulls(feedback, ['customer_id', 'quality_rating'])
            + _check_duplicates(feedback, 'feedback_id')
            + _check_referential_integrity(feedback, 'product_id', products['product_id'])
            + _check_range(feedback, 'quality_rating', rating_min, rating_max)
            + _check_range(feedback, 'overall_satisfaction', rating_min, rating_max)
            + _check_dates(feedback, 'feedback_date')
        ),
        'ingredients': (
            _check_duplicates(ingredients, 'ingredient_id')
            # ingredient_name is the de facto join key from products.primary_ingredient
            # (there's no ingredient_id on products), so a duplicate name under two
            # different ingredient_ids is a real join hazard even with unique IDs.
            + _check_duplicates(ingredients, 'ingredient_name')
            + _check_dates(ingredients, 'last_updated')
        ),
    }

    for dataset, issues in report.items():
        for issue in issues:
            logger.warning(f"[{dataset}] {issue}")

    total_issues = sum(len(issues) for issues in report.values())
    logger.info(f"Validation complete: {total_issues} issue(s) found across {len(report)} dataset(s)")

    return report
