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

# Maps config/schema.yaml's `dtype` values to SQLAlchemy column types, so the
# column type is declared once (in schema.yaml) instead of twice - previously
# this module hardcoded its own String/Float/Date per column, independently
# of schema.yaml, with no way to notice if the two ever disagreed.
DTYPE_TO_SQLA = {'string': String, 'numeric': Float, 'date': Date}

# What schema.yaml deliberately does NOT capture: these are database
# structure decisions, not data-quality contract terms, and don't map
# cleanly from schema.yaml's `required` (e.g. feedback.quality_rating is
# `required: true` in the data-quality sense - we want it flagged when
# missing - yet 1 residual null is known and allowed through by design;
# nullable=False here would reject that row and break the load).
PRIMARY_KEYS = {
    'products': 'product_id',
    'ingredients': 'ingredient_id',
    'sales': 'transaction_id',
    'feedback': 'feedback_id',
}
FOREIGN_KEYS = {
    'sales': {'product_id': 'products.product_id'},
    'feedback': {'product_id': 'products.product_id'},
}
NOT_NULL_COLUMNS = {
    'products': ['product_name'],
    'ingredients': ['ingredient_name'],
}

# Parents before children: sales/feedback reference products, and while
# SQLite doesn't enforce FKs by default (needed since a few rows reference
# an unknown product_id - see transform.py), loading in this order keeps
# the data consistent with the declared schema.
LOAD_ORDER = ['products', 'ingredients', 'sales', 'feedback']


def _build_metadata(schema: dict) -> tuple[MetaData, dict[str, Table]]:
    """
    Build the SQLAlchemy schema from config/schema.yaml's column types, with
    primary keys / foreign keys / NOT NULL constraints layered on top from
    the table-specific dicts above (deliberately not derived from
    schema.yaml - see the comment on those dicts for why).
    """
    metadata = MetaData()
    tables = {}
    for name in LOAD_ORDER:
        columns = []
        for col, spec in schema[name].items():
            args: list = [col, DTYPE_TO_SQLA[spec['dtype']]]
            fk_target = FOREIGN_KEYS.get(name, {}).get(col)
            if fk_target:
                args.append(ForeignKey(fk_target))
            kwargs = {}
            if col == PRIMARY_KEYS.get(name):
                kwargs['primary_key'] = True
            if col in NOT_NULL_COLUMNS.get(name, []):
                kwargs['nullable'] = False
            columns.append(Column(*args, **kwargs))
        tables[name] = Table(name, metadata, *columns)
    return metadata, tables


def _resolve(path: str) -> Path:
    resolved = Path(path)
    return resolved if resolved.is_absolute() else PROJECT_ROOT / resolved


def load_all(
    cleaned_data: dict[str, pd.DataFrame], schema: dict, database_path: str = "symrise_data.db"
) -> Path:
    """
    (Re)create the schema and load cleaned DataFrames into SQLite.

    Args:
        cleaned_data: Dict with keys 'products', 'sales', 'feedback',
            'ingredients' holding cleaned DataFrames from transform_all().
        schema: The data contract loaded from config/schema.yaml - supplies
            each column's type (see DTYPE_TO_SQLA above).
        database_path: Path to the SQLite database file, relative to the
            project root or absolute.

    Returns:
        The resolved path to the database file.
    """
    metadata, _ = _build_metadata(schema)

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
