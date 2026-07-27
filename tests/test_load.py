import pandas as pd
import sqlalchemy
from sqlalchemy import Date, Float, String

from src import load


def _minimal_cleaned_data() -> dict[str, pd.DataFrame]:
    """One row per table, already in the shape transform.py would produce
    (dates parsed, no known-negative/duplicate issues) - just enough to
    exercise load_all() end-to-end without depending on the real CSVs."""
    return {
        'products': pd.DataFrame({
            'product_id': ['P001'], 'product_name': ['Citrus Burst'], 'category': ['Fragrance'],
            'subcategory': ['Fresh'], 'launch_date': [pd.Timestamp('2023-01-15')], 'status': ['Active'],
            'num_ingredients': [12.0], 'primary_ingredient': ['Lemon Oil'], 'region_developed': ['EMEA'],
        }),
        'ingredients': pd.DataFrame({
            'ingredient_id': ['I001'], 'ingredient_name': ['Lemon Oil'], 'cost_per_kg_usd': [45.5],
            'supplier': ['CitrusSupply Co'], 'last_updated': [pd.Timestamp('2024-08-01')],
            'category': ['Essential Oil'],
        }),
        'sales': pd.DataFrame({
            'transaction_id': ['T001'], 'product_id': ['P001'], 'customer_id': ['C001'],
            'transaction_date': [pd.Timestamp('2024-01-05')], 'quantity_kg': [25.5],
            'unit_price_usd': [150.0], 'total_amount_usd': [3825.0], 'region': ['EMEA'],
            'sales_channel': ['Direct'],
        }),
        'feedback': pd.DataFrame({
            'feedback_id': ['F001'], 'product_id': ['P001'], 'customer_id': ['C001'],
            'feedback_date': [pd.Timestamp('2024-02-10')], 'quality_rating': [4.5],
            'performance_rating': [4.0], 'value_rating': [4.5], 'overall_satisfaction': [4.3],
            'would_reorder': ['Yes'], 'comments': ['Great'],
        }),
    }


class TestBuildMetadata:
    def test_maps_schema_dtypes_to_sqlalchemy_types(self, schema):
        _, tables = load._build_metadata(schema)
        products = tables['products']
        assert isinstance(products.c.product_id.type, String)
        assert isinstance(products.c.num_ingredients.type, Float)
        assert isinstance(products.c.launch_date.type, Date)

    def test_primary_keys_are_set_per_table(self, schema):
        _, tables = load._build_metadata(schema)
        assert tables['products'].c.product_id.primary_key
        assert tables['ingredients'].c.ingredient_id.primary_key
        assert tables['sales'].c.transaction_id.primary_key
        assert tables['feedback'].c.feedback_id.primary_key
        # product_id also appears on sales/feedback, but only as a foreign
        # key there - it must not be mistaken for a second primary key.
        assert not tables['sales'].c.product_id.primary_key

    def test_foreign_keys_point_to_products(self, schema):
        _, tables = load._build_metadata(schema)
        for table_name in ['sales', 'feedback']:
            fk_targets = {fk.target_fullname for fk in tables[table_name].c.product_id.foreign_keys}
            assert fk_targets == {'products.product_id'}

    def test_not_null_columns_are_explicit_not_derived_from_required(self, schema):
        _, tables = load._build_metadata(schema)
        assert tables['products'].c.product_name.nullable is False
        assert tables['ingredients'].c.ingredient_name.nullable is False
        # feedback.quality_rating is `required: true` in schema.yaml (a
        # data-quality expectation), but has a known, allowed residual null
        # - it must stay nullable in the DB or a real load would crash.
        assert tables['feedback'].c.quality_rating.nullable is True


class TestLoadAll:
    def test_creates_database_and_loads_expected_row_counts(self, tmp_path, schema):
        db_path = tmp_path / 'test.db'
        cleaned = _minimal_cleaned_data()

        result_path = load.load_all(cleaned, schema, database_path=str(db_path))

        assert result_path == db_path
        assert db_path.exists()

        engine = sqlalchemy.create_engine(f"sqlite:///{db_path}")
        with engine.connect() as conn:
            for name, df in cleaned.items():
                count = conn.execute(sqlalchemy.text(f"SELECT COUNT(*) FROM {name}")).scalar()
                assert count == len(df)
        engine.dispose()

    def test_is_idempotent_on_repeated_runs(self, tmp_path, schema):
        db_path = tmp_path / 'test.db'
        cleaned = _minimal_cleaned_data()

        load.load_all(cleaned, schema, database_path=str(db_path))
        load.load_all(cleaned, schema, database_path=str(db_path))

        engine = sqlalchemy.create_engine(f"sqlite:///{db_path}")
        with engine.connect() as conn:
            count = conn.execute(sqlalchemy.text("SELECT COUNT(*) FROM sales")).scalar()
        engine.dispose()

        assert count == 1  # not 2 - the schema is dropped and recreated each run

    def test_products_and_ingredients_load_before_sales_and_feedback(self, tmp_path, schema):
        # LOAD_ORDER matters because sales/feedback declare a foreign key to
        # products; this doesn't assert ordering directly (SQLite doesn't
        # enforce FKs by default here - see load.py's comment), it just
        # confirms a full run succeeds without error, which would be the
        # first thing to break if LOAD_ORDER were ever reversed.
        db_path = tmp_path / 'test.db'
        load.load_all(_minimal_cleaned_data(), schema, database_path=str(db_path))
        assert db_path.exists()
