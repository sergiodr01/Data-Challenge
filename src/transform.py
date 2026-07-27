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


def _dedupe_fact_ids(df: pd.DataFrame, id_col: str, name: str) -> pd.DataFrame:
    """
    Disambiguate fact rows (sales, feedback) that share an ID but are NOT
    identical (an ID collision, not a true duplicate) by suffixing later
    occurrences. Safe here because nothing else references a transaction_id
    or feedback_id, so renaming one can't silently break another table's
    foreign key. Dropping instead of renaming would lose real records
    (e.g. real revenue).
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


def _resolve_dimension_conflicts(
    df: pd.DataFrame, id_col: str, name: str, ignore_cols: list[str] | None = None
) -> pd.DataFrame:
    """
    Deduplicate dimension rows (products, ingredients) that share an ID but
    are NOT identical. Unlike fact IDs, a dimension ID is a foreign key
    target for other tables (sales.product_id, feedback.product_id), so it
    must never be renamed - that would silently orphan every row that
    already points at it. Instead, keep the first occurrence deterministically.

    Two outcomes, logged at different levels:
      - The conflicting rows agree on every other column (ignore_cols aside,
        e.g. an alternate id column that's expected to differ) - nothing
        real is lost, just a redundant label. Logged as info.
      - The conflicting rows genuinely disagree elsewhere - there's no way
        to tell which one is "correct" from the data alone, so dropping is
        a judgment call, not a safe merge. Logged as a warning, same as
        before.
    """
    ignore = {id_col, *(ignore_cols or [])}
    compare_cols = [c for c in df.columns if c not in ignore]

    conflict_mask = df[id_col].duplicated(keep=False)
    if conflict_mask.any():
        for key, group in df.loc[conflict_mask].groupby(id_col):
            if len(group[compare_cols].drop_duplicates()) == 1:
                logger.info(
                    f"[{name}] '{key}' appears in {len(group)} rows that agree on every "
                    f"other column; merged safely, kept the first occurrence"
                )
            else:
                logger.warning(
                    f"[{name}] '{key}' has {len(group)} conflicting non-identical rows; "
                    f"kept the first occurrence and dropped the rest, since {id_col} is "
                    f"referenced by other tables"
                )
    return df.drop_duplicates(subset=[id_col], keep='first').reset_index(drop=True)


def _strip_string_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Strip leading/trailing whitespace from every text column at once. Safe
    to apply universally (unlike .capitalize()/.title()/canonical maps,
    which depend on what a column *means*): removing accidental whitespace
    never changes the intended value, regardless of the column's role.
    """
    df = df.copy()
    for col in df.select_dtypes(include=['object', 'str']).columns:
        df[col] = df[col].str.strip()
    return df


def _nan_negative_values(df: pd.DataFrame, col: str, name: str) -> pd.DataFrame:
    """
    Set negative values to NaN rather than guessing the true value (e.g.
    assuming a sign flip) - same treatment as products.num_ingredients,
    reused for every quantity/price/cost column that can't legitimately be
    negative.
    """
    negative = df[col] < 0
    if negative.any():
        df.loc[negative, col] = float('nan')
        logger.warning(
            f"[{name}] {negative.sum()} negative '{col}' value(s) are not "
            f"plausible; set to NaN rather than guessing the true value"
        )
    return df


def _canonicalize(series: pd.Series, allowed_values: list[str]) -> pd.Series:
    """
    Normalize casing/whitespace against a small, closed vocabulary sourced
    from schema.yaml (e.g. 'emea' / ' EMEA' / 'Emea' -> 'EMEA'). Safe only
    because these values are known in advance and won't grow - unlike
    category/subcategory, which use .title() instead, since new categories
    can legitimately appear over time and a fixed map would wrongly turn
    them into NaN. A value with no case-insensitive match becomes NaN,
    which is intentional: it surfaces an unrecognized region as a null
    rather than silently keeping a typo as its own new "region".
    """
    lookup = {v.lower(): v for v in allowed_values}
    return series.str.lower().map(lookup)


def clean_products(df: pd.DataFrame, schema: dict | None = None) -> pd.DataFrame:
    schema = schema or {}
    df = _drop_exact_duplicates(df, 'products')
    df = _resolve_dimension_conflicts(df, 'product_id', 'products')
    df = _strip_string_columns(df)

    missing_name = df['product_name'].isna()
    if missing_name.any():
        df.loc[missing_name, 'product_name'] = 'Unknown (' + df.loc[missing_name, 'product_id'] + ')'
        logger.warning(f"[products] filled {missing_name.sum()} missing product_name from product_id")

    df['status'] = df['status'].str.capitalize()
    df['category'] = df['category'].str.title()
    df['subcategory'] = df['subcategory'].str.title()
    df['launch_date'] = pd.to_datetime(df['launch_date'], format='mixed', errors='coerce')

    region_values = schema.get('products', {}).get('region_developed', {}).get('allowed_values')
    if region_values:
        df['region_developed'] = _canonicalize(df['region_developed'], region_values)

    df = _nan_negative_values(df, 'num_ingredients', 'products')

    return df


def clean_sales(df: pd.DataFrame, schema: dict | None = None) -> pd.DataFrame:
    schema = schema or {}
    df = _drop_exact_duplicates(df, 'sales')
    df = _dedupe_fact_ids(df, 'transaction_id', 'sales')
    df = _strip_string_columns(df)

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

    df['transaction_date'] = pd.to_datetime(df['transaction_date'], format='mixed', errors='coerce')
    df['sales_channel'] = df['sales_channel'].str.capitalize()

    region_values = schema.get('sales', {}).get('region', {}).get('allowed_values')
    if region_values:
        df['region'] = _canonicalize(df['region'], region_values)

    df = _nan_negative_values(df, 'quantity_kg', 'sales')
    df = _nan_negative_values(df, 'unit_price_usd', 'sales')
    df = _nan_negative_values(df, 'total_amount_usd', 'sales')

    return df


def clean_feedback(df: pd.DataFrame, rating_min: float = 0, rating_max: float = 5) -> pd.DataFrame:
    df = _drop_exact_duplicates(df, 'feedback')
    df = _dedupe_fact_ids(df, 'feedback_id', 'feedback')
    df = _strip_string_columns(df)

    missing_customer = df['customer_id'].isna()
    if missing_customer.any():
        df.loc[missing_customer, 'customer_id'] = 'UNKNOWN'
        logger.warning(f"[feedback] filled {missing_customer.sum()} missing customer_id with 'UNKNOWN'")

    for col in ['quality_rating', 'performance_rating', 'value_rating', 'overall_satisfaction']:
        out_of_range = df[col].notna() & ((df[col] < rating_min) | (df[col] > rating_max))
        if out_of_range.any():
            df.loc[out_of_range, col] = df.loc[out_of_range, col].clip(rating_min, rating_max)
            logger.warning(f"[feedback] clipped {out_of_range.sum()} out-of-range value(s) in '{col}' to [{rating_min}, {rating_max}]")

    df['would_reorder'] = df['would_reorder'].str.capitalize()
    df['feedback_date'] = pd.to_datetime(df['feedback_date'], format='mixed', errors='coerce')

    return df


def clean_ingredients(df: pd.DataFrame) -> pd.DataFrame:
    df = _drop_exact_duplicates(df, 'ingredients')
    df = _resolve_dimension_conflicts(df, 'ingredient_id', 'ingredients')
    # products.primary_ingredient links to ingredients by NAME, not
    # ingredient_id (there's no ingredient_id column on products), so a
    # duplicate ingredient_name under two different ingredient_ids (e.g.
    # 'Lemon Oil' as both I001 and I018) is a real join hazard even though
    # ingredient_id itself stayed unique: it silently fans out any
    # name-based cost join into duplicate rows, double-counting revenue.
    # ingredient_id is expected to differ here (that's the whole conflict),
    # so it's excluded from the "otherwise identical" comparison.
    df = _resolve_dimension_conflicts(df, 'ingredient_name', 'ingredients', ignore_cols=['ingredient_id'])
    df = _strip_string_columns(df)

    df['category'] = df['category'].str.title()
    df['last_updated'] = pd.to_datetime(df['last_updated'], format='mixed', errors='coerce')
    df = _nan_negative_values(df, 'cost_per_kg_usd', 'ingredients')

    return df


def transform_all(
    data: dict[str, pd.DataFrame], thresholds: dict[str, Any] | None = None, schema: dict | None = None
) -> dict[str, pd.DataFrame]:
    """
    Apply all cleaning steps to the raw datasets returned by extract_all().

    Args:
        data: Dict with keys 'products', 'sales', 'feedback', 'ingredients'.
        thresholds: Optional dict with 'rating_min' / 'rating_max', typically
            sourced from pipeline_config.yaml's quality_thresholds section.
        schema: The data contract loaded from config/schema.yaml - supplies
            the closed vocabularies (e.g. region names) used to normalize
            products.region_developed and sales.region.

    Returns:
        Dict with the same keys, holding cleaned DataFrames.
    """
    thresholds = thresholds or {}
    schema = schema or {}
    rating_min = thresholds.get('rating_min', 0)
    rating_max = thresholds.get('rating_max', 5)

    cleaned = {
        'products': clean_products(data['products'], schema),
        'sales': clean_sales(data['sales'], schema),
        'feedback': clean_feedback(data['feedback'], rating_min, rating_max),
        'ingredients': clean_ingredients(data['ingredients']),
    }

    logger.info("Transformation complete for all datasets")
    return cleaned
