"""
Data transformation module: cleans and normalizes the raw datasets.

Each clean_*() function fixes exactly the issues validate.py flags for that
dataset. Rows are never dropped just because a field is unrecoverable
(e.g. a missing rating) - real revenue and feedback rows are worth more
than a spotless table, so unrecoverable fields are left as NaN and
excluded naturally by downstream aggregations (e.g. pandas/SQL AVG skips
NULLs). Fields are only dropped when they are exact duplicate rows.
"""

import logging
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


def _drop_exact_duplicates(df: pd.DataFrame, name: str) -> pd.DataFrame:
    before = len(df)
    df = df.drop_duplicates()
    removed = before - len(df)
    if removed:
        logger.info(f"[{name}] dropped {removed} exact duplicate row(s)")
    return df


def _dedupe_ids(df: pd.DataFrame, id_col: str, name: str) -> pd.DataFrame:
    """
    Disambiguate rows that share an ID but are NOT identical (an ID
    collision, not a true duplicate) by suffixing later occurrences.
    Dropping them would silently lose real records (e.g. real revenue).
    """
    df = df.copy()
    seen: dict[str, int] = {}
    new_ids = []
    for original_id in df[id_col]:
        seen[original_id] = seen.get(original_id, 0) + 1
        if seen[original_id] > 1:
            new_id = f"{original_id}-DUP{seen[original_id] - 1}"
            logger.warning(
                f"[{name}] '{original_id}' reused across non-identical rows; "
                f"renamed collision to '{new_id}'"
            )
            new_ids.append(new_id)
        else:
            new_ids.append(original_id)
    df[id_col] = new_ids
    return df


def clean_products(df: pd.DataFrame) -> pd.DataFrame:
    df = _drop_exact_duplicates(df, 'products')
    df = _dedupe_ids(df, 'product_id', 'products')

    df = df.copy()
    missing_name = df['product_name'].isna()
    if missing_name.any():
        df.loc[missing_name, 'product_name'] = 'Unknown (' + df.loc[missing_name, 'product_id'] + ')'
        logger.warning(f"[products] filled {missing_name.sum()} missing product_name from product_id")

    df['status'] = df['status'].str.strip().str.capitalize()
    df['category'] = df['category'].str.strip()
    df['subcategory'] = df['subcategory'].str.strip()
    df['launch_date'] = pd.to_datetime(df['launch_date'], errors='coerce')

    return df


def clean_sales(df: pd.DataFrame) -> pd.DataFrame:
    df = _drop_exact_duplicates(df, 'sales')
    df = _dedupe_ids(df, 'transaction_id', 'sales')

    df = df.copy()
    recoverable = (
        df['total_amount_usd'].isna()
        & df['quantity_kg'].notna()
        & df['unit_price_usd'].notna()
    )
    if recoverable.any():
        df.loc[recoverable, 'total_amount_usd'] = (
            df.loc[recoverable, 'quantity_kg'] * df.loc[recoverable, 'unit_price_usd']
        )
        logger.info(f"[sales] recomputed {recoverable.sum()} missing total_amount_usd from quantity x price")

    missing_customer = df['customer_id'].isna()
    if missing_customer.any():
        df.loc[missing_customer, 'customer_id'] = 'UNKNOWN'
        logger.warning(f"[sales] filled {missing_customer.sum()} missing customer_id with 'UNKNOWN'")

    df['transaction_date'] = pd.to_datetime(df['transaction_date'], errors='coerce')

    return df


def clean_feedback(df: pd.DataFrame, rating_min: float = 0, rating_max: float = 5) -> pd.DataFrame:
    df = _drop_exact_duplicates(df, 'feedback')
    df = _dedupe_ids(df, 'feedback_id', 'feedback')

    df = df.copy()
    missing_customer = df['customer_id'].isna()
    if missing_customer.any():
        df.loc[missing_customer, 'customer_id'] = 'UNKNOWN'
        logger.warning(f"[feedback] filled {missing_customer.sum()} missing customer_id with 'UNKNOWN'")

    for col in ['quality_rating', 'performance_rating', 'value_rating', 'overall_satisfaction']:
        out_of_range = df[col].notna() & ((df[col] < rating_min) | (df[col] > rating_max))
        if out_of_range.any():
            df.loc[out_of_range, col] = df.loc[out_of_range, col].clip(rating_min, rating_max)
            logger.warning(f"[feedback] clipped {out_of_range.sum()} out-of-range value(s) in '{col}' to [{rating_min}, {rating_max}]")

    df['would_reorder'] = df['would_reorder'].str.strip().str.capitalize()
    df['feedback_date'] = pd.to_datetime(df['feedback_date'], errors='coerce')

    return df


def clean_ingredients(df: pd.DataFrame) -> pd.DataFrame:
    df = _drop_exact_duplicates(df, 'ingredients')
    df = _dedupe_ids(df, 'ingredient_id', 'ingredients')

    df = df.copy()
    df['last_updated'] = pd.to_datetime(df['last_updated'], errors='coerce')

    return df


def transform_all(data: dict[str, pd.DataFrame], thresholds: dict[str, Any] | None = None) -> dict[str, pd.DataFrame]:
    """
    Apply all cleaning steps to the raw datasets returned by extract_all().

    Args:
        data: Dict with keys 'products', 'sales', 'feedback', 'ingredients'.
        thresholds: Optional dict with 'rating_min' / 'rating_max', typically
            sourced from pipeline_config.yaml's quality_thresholds section.

    Returns:
        Dict with the same keys, holding cleaned DataFrames.
    """
    thresholds = thresholds or {}
    rating_min = thresholds.get('rating_min', 0)
    rating_max = thresholds.get('rating_max', 5)

    cleaned = {
        'products': clean_products(data['products']),
        'sales': clean_sales(data['sales']),
        'feedback': clean_feedback(data['feedback'], rating_min, rating_max),
        'ingredients': clean_ingredients(data['ingredients']),
    }

    logger.info("Transformation complete for all datasets")
    return cleaned
