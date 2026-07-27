"""Shared fixtures: small raw DataFrames mirroring the real CSVs, each
carrying one instance of the data quality issues extract/validate/transform
are meant to catch and fix."""

from pathlib import Path

import pandas as pd
import pytest
import yaml

SCHEMA_PATH = Path(__file__).resolve().parent.parent / 'config' / 'schema.yaml'


@pytest.fixture
def schema() -> dict:
    """Loads the real config/schema.yaml, so tests exercise the actual data
    contract instead of a copy that could silently drift out of sync."""
    with open(SCHEMA_PATH, encoding='utf-8') as f:
        return yaml.safe_load(f)


@pytest.fixture
def raw_products() -> pd.DataFrame:
    return pd.DataFrame({
        'product_id': ['P001', 'P002', 'P003', 'P003'],
        'product_name': ['Citrus Burst', None, 'Rose Absolute', 'Rose Absolute (dup)'],
        'category': ['Fragrance', 'Flavor', 'Fragrance', 'Fragrance'],
        'subcategory': ['Fresh', 'Sweet', 'Floral', 'Floral'],
        'launch_date': ['2023-01-15', '07/15/2024', '2023-03-01', '2023-03-01'],
        'status': ['active', 'Active', 'discontinued', 'discontinued'],
        'num_ingredients': [12, -3, 6, 6],
        'primary_ingredient': ['Lemon Oil', 'Vanilla Extract', 'Rose Oil', 'Rose Oil'],
        'region_developed': ['EMEA', 'North America', 'EMEA', 'EMEA'],
    })


@pytest.fixture
def raw_sales() -> pd.DataFrame:
    return pd.DataFrame({
        'transaction_id': ['T001', 'T002', 'T003', 'T003'],
        'product_id': ['P001', 'P002', 'P999', 'P001'],
        'customer_id': ['C001', None, 'C003', 'C004'],
        'transaction_date': ['2024-01-05', '2024-01-08', '7/15/2024', '2024-02-01'],
        'quantity_kg': [25.5, 30.0, 10.0, 5.0],
        'unit_price_usd': [150.0, 200.0, 100.0, 80.0],
        'total_amount_usd': [3825.0, None, 1000.0, 400.0],
        'region': ['EMEA', 'North America', 'APAC', 'EMEA'],
        'sales_channel': ['Direct', 'Distributor', 'Direct', 'Direct'],
    })


@pytest.fixture
def raw_feedback() -> pd.DataFrame:
    return pd.DataFrame({
        'feedback_id': ['F001', 'F002', 'F003'],
        'product_id': ['P001', 'P999', 'P002'],
        'customer_id': ['C001', None, 'C002'],
        'feedback_date': ['2024-02-10', '2024-02-15', '02-18-2024'],
        'quality_rating': [4.5, None, 6.0],
        'performance_rating': [4.0, 5.0, 4.5],
        'value_rating': [4.5, 4.5, 4.0],
        'overall_satisfaction': [4.3, 4.8, 5.5],
        'would_reorder': ['yes', 'YES', 'no'],
        'comments': ['Great', 'Best', 'Too strong'],
    })


@pytest.fixture
def raw_ingredients() -> pd.DataFrame:
    return pd.DataFrame({
        'ingredient_id': ['I001', 'I002', 'I018'],
        'ingredient_name': ['Lemon Oil', 'Vanilla Extract', 'Lemon Oil'],
        'cost_per_kg_usd': [45.50, 120.00, 50.00],
        'supplier': ['CitrusSupply Co', 'VanillaPro Ltd', 'OtherCitrus Co'],
        'last_updated': ['2024-08-01', '2024-08-01', '2024-08-02'],
        'category': ['Essential Oil', 'Extract', 'Essential Oil'],
    })


@pytest.fixture
def raw_data(raw_products, raw_sales, raw_feedback, raw_ingredients) -> dict[str, pd.DataFrame]:
    return {
        'products': raw_products,
        'sales': raw_sales,
        'feedback': raw_feedback,
        'ingredients': raw_ingredients,
    }
