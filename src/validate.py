"""
Data validation module: schema and quality checks on raw datasets.

Checks here are read-only: they never mutate the data or raise on data
quality issues (missing values, duplicates, out-of-range ratings, orphaned
foreign keys). Cleaning happens in transform.py; this module's job is to
detect and report issues so they can be logged and surfaced in the data
quality report.
"""

import logging
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = {
    'products': ['product_id', 'product_name', 'category', 'num_ingredients'],
    'sales': ['transaction_id', 'product_id', 'customer_id', 'total_amount_usd'],
    'feedback': ['feedback_id', 'product_id', 'customer_id', 'quality_rating', 'overall_satisfaction'],
    'ingredients': ['ingredient_id', 'ingredient_name', 'cost_per_kg_usd'],
}


def _check_schema(name: str, df: pd.DataFrame) -> list[str]:
    missing = [c for c in REQUIRED_COLUMNS[name] if c not in df.columns]
    return [f"missing required column '{c}'" for c in missing]


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


def _check_range(df: pd.DataFrame, col: str, min_val: float, max_val: float) -> list[str]:
    if col not in df.columns:
        return []
    out_of_range = df[col].notna() & ((df[col] < min_val) | (df[col] > max_val))
    n = int(out_of_range.sum())
    return [f"{n} value(s) in '{col}' outside [{min_val}, {max_val}]"] if n else []


def _check_referential_integrity(df: pd.DataFrame, fk_col: str, valid_ids: pd.Series) -> list[str]:
    if fk_col not in df.columns:
        return []
    orphans = df[fk_col].notna() & (~df[fk_col].isin(valid_ids))
    n = int(orphans.sum())
    return [f"{n} '{fk_col}' value(s) not found in products"] if n else []


def validate_all(data: dict[str, pd.DataFrame], thresholds: dict[str, Any] | None = None) -> dict[str, list[str]]:
    """
    Run schema and quality checks on the raw datasets returned by extract_all().

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
            _check_schema('products', products)
            + _check_nulls(products, ['product_name', 'category', 'num_ingredients'])
            + _check_duplicates(products, 'product_id')
        ),
        'sales': (
            _check_schema('sales', sales)
            + _check_nulls(sales, ['customer_id', 'total_amount_usd'])
            + _check_duplicates(sales, 'transaction_id')
            + _check_referential_integrity(sales, 'product_id', products['product_id'])
        ),
        'feedback': (
            _check_schema('feedback', feedback)
            + _check_nulls(feedback, ['customer_id', 'quality_rating'])
            + _check_duplicates(feedback, 'feedback_id')
            + _check_referential_integrity(feedback, 'product_id', products['product_id'])
            + _check_range(feedback, 'quality_rating', rating_min, rating_max)
            + _check_range(feedback, 'overall_satisfaction', rating_min, rating_max)
        ),
        'ingredients': (
            _check_schema('ingredients', ingredients)
            + _check_duplicates(ingredients, 'ingredient_id')
        ),
    }

    for dataset, issues in report.items():
        for issue in issues:
            logger.warning(f"[{dataset}] {issue}")

    total_issues = sum(len(issues) for issues in report.values())
    logger.info(f"Validation complete: {total_issues} issue(s) found across {len(report)} dataset(s)")

    return report
