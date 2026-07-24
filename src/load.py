"""
Database load module: creates the SQLite schema and loads cleaned data into it.

Loads are idempotent: the schema is dropped and recreated on every run and
each table is fully replaced, so running the pipeline twice in a row
produces the same database instead of accumulating duplicate rows.

Note on ingredient costs: products.csv only records a single
primary_ingredient per product (not the full ingredient list implied by
num_ingredients), so any ingredient-cost join used for the profit-margin
business question is necessarily an approximation based on that one
ingredient - that's a data limitation, not something this module can fix.
"""

import logging
from pathlib import Path

import pandas as pd
from sqlalchemy import Column, Date, Float, ForeignKey, MetaData, String, Table, create_engine

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

metadata = MetaData()

products_table = Table(
    'products', metadata,
    Column('product_id', String, primary_key=True),
    Column('product_name', String, nullable=False),
    Column('category', String),
    Column('subcategory', String),
    Column('launch_date', Date),
    Column('status', String),
    Column('num_ingredients', Float),
    Column('primary_ingredient', String),
    Column('region_developed', String),
)

ingredients_table = Table(
    'ingredients', metadata,
    Column('ingredient_id', String, primary_key=True),
    Column('ingredient_name', String, nullable=False),
    Column('cost_per_kg_usd', Float),
    Column('supplier', String),
    Column('last_updated', Date),
    Column('category', String),
)

sales_table = Table(
    'sales', metadata,
    Column('transaction_id', String, primary_key=True),
    Column('product_id', String, ForeignKey('products.product_id')),
    Column('customer_id', String),
    Column('transaction_date', Date),
    Column('quantity_kg', Float),
    Column('unit_price_usd', Float),
    Column('total_amount_usd', Float),
    Column('region', String),
    Column('sales_channel', String),
)

feedback_table = Table(
    'feedback', metadata,
    Column('feedback_id', String, primary_key=True),
    Column('product_id', String, ForeignKey('products.product_id')),
    Column('customer_id', String),
    Column('feedback_date', Date),
    Column('quality_rating', Float),
    Column('performance_rating', Float),
    Column('value_rating', Float),
    Column('overall_satisfaction', Float),
    Column('would_reorder', String),
    Column('comments', String),
)

# Parents before children: sales/feedback reference products, and while
# SQLite doesn't enforce FKs by default (needed since a few rows reference
# an unknown product_id - see transform.py), loading in this order keeps
# the data consistent with the declared schema.
LOAD_ORDER = ['products', 'ingredients', 'sales', 'feedback']


def _resolve(path: str) -> Path:
    resolved = Path(path)
    return resolved if resolved.is_absolute() else PROJECT_ROOT / resolved


def load_all(cleaned_data: dict[str, pd.DataFrame], database_path: str = "symrise_data.db") -> Path:
    """
    (Re)create the schema and load cleaned DataFrames into SQLite.

    Args:
        cleaned_data: Dict with keys 'products', 'sales', 'feedback',
            'ingredients' holding cleaned DataFrames from transform_all().
        database_path: Path to the SQLite database file, relative to the
            project root or absolute.

    Returns:
        The resolved path to the database file.
    """
    db_path = _resolve(database_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}")

    # Schema (re)creation and every table load run inside one transaction,
    # so a failure partway through rolls back the whole database instead of
    # leaving it schema-only or half-loaded.
    with engine.begin() as conn:
        metadata.drop_all(conn)
        metadata.create_all(conn)
        logger.info(f"Schema (re)created at {db_path}")

        for name in LOAD_ORDER:
            df = cleaned_data[name]
            df.to_sql(name, conn, if_exists='append', index=False)
            logger.info(f"Loaded {len(df)} row(s) into '{name}'")

    engine.dispose()
    return db_path
