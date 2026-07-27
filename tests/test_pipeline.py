from pathlib import Path

import pandas as pd
import pytest
import sqlalchemy
import yaml

from src import pipeline, validate


def _write_csvs(tmp_path: Path) -> dict[str, str]:
    """One clean row per dataset - no seeded quality issues, so a
    successful run_ingestion()/run_pipeline() call is expected to report
    zero residual issues. Quality-issue handling is transform.py/validate.py's
    job and is already covered there; this module only tests orchestration."""
    products = pd.DataFrame({
        'product_id': ['P001'], 'product_name': ['Citrus Burst'], 'category': ['Fragrance'],
        'subcategory': ['Fresh'], 'launch_date': ['2023-01-15'], 'status': ['Active'],
        'num_ingredients': [12], 'primary_ingredient': ['Lemon Oil'], 'region_developed': ['EMEA'],
    })
    sales = pd.DataFrame({
        'transaction_id': ['T001'], 'product_id': ['P001'], 'customer_id': ['C001'],
        'transaction_date': ['2024-01-05'], 'quantity_kg': [25.5], 'unit_price_usd': [150.0],
        'total_amount_usd': [3825.0], 'region': ['EMEA'], 'sales_channel': ['Direct'],
    })
    feedback = pd.DataFrame({
        'feedback_id': ['F001'], 'product_id': ['P001'], 'customer_id': ['C001'],
        'feedback_date': ['2024-02-10'], 'quality_rating': [4.5], 'performance_rating': [4.0],
        'value_rating': [4.5], 'overall_satisfaction': [4.3], 'would_reorder': ['Yes'],
        'comments': ['Great'],
    })
    ingredients = pd.DataFrame({
        'ingredient_id': ['I001'], 'ingredient_name': ['Lemon Oil'], 'cost_per_kg_usd': [45.5],
        'supplier': ['CitrusSupply Co'], 'last_updated': ['2024-08-01'], 'category': ['Essential Oil'],
    })

    products.to_csv(tmp_path / 'products.csv', index=False)
    sales.to_csv(tmp_path / 'sales.csv', index=False)
    feedback.to_csv(tmp_path / 'feedback.csv', index=False)
    ingredients.to_csv(tmp_path / 'ingredients.csv', index=False)

    return {
        'products_csv': str(tmp_path / 'products.csv'),
        'sales_csv': str(tmp_path / 'sales.csv'),
        'feedback_csv': str(tmp_path / 'feedback.csv'),
        'ingredient_costs_csv': str(tmp_path / 'ingredients.csv'),
        'database': str(tmp_path / 'test.db'),
    }


def _write_config(tmp_path: Path, paths: dict[str, str]) -> Path:
    config = {
        'paths': paths,
        'quality_thresholds': {'rating_min': 0, 'rating_max': 5},
        'logging': {'level': 'WARNING'},  # keep test output quiet
    }
    config_path = tmp_path / 'pipeline_config.yaml'
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(config, f)
    return config_path


# The real config/schema.yaml, not a copy - schema_path's default already
# resolves to it via pipeline._resolve() (relative to the project root, not
# the CSVs' tmp_path), so tests exercise the actual data contract.
REAL_SCHEMA_PATH = "config/schema.yaml"


class TestRunIngestion:
    def test_happy_path_returns_cleaned_data_with_no_residual_issues(self, tmp_path):
        paths = _write_csvs(tmp_path)
        config_path = _write_config(tmp_path, paths)

        cleaned_data, post_report = pipeline.run_ingestion(str(config_path), REAL_SCHEMA_PATH)

        assert set(cleaned_data) == {'products', 'sales', 'feedback', 'ingredients'}
        assert len(cleaned_data['products']) == 1
        assert all(issues == [] for issues in post_report.values())

    def test_missing_required_column_raises_schema_validation_error(self, tmp_path):
        paths = _write_csvs(tmp_path)
        # Corrupt the products CSV in place: drop a required column.
        broken = pd.read_csv(paths['products_csv']).drop(columns=['category'])
        broken.to_csv(paths['products_csv'], index=False)
        config_path = _write_config(tmp_path, paths)

        with pytest.raises(validate.SchemaValidationError, match="category"):
            pipeline.run_ingestion(str(config_path), REAL_SCHEMA_PATH)


class TestRunPipeline:
    def test_creates_database_with_expected_row_counts(self, tmp_path):
        paths = _write_csvs(tmp_path)
        config_path = _write_config(tmp_path, paths)

        pipeline.run_pipeline(str(config_path), REAL_SCHEMA_PATH)

        db_path = Path(paths['database'])
        assert db_path.exists()

        engine = sqlalchemy.create_engine(f"sqlite:///{db_path}")
        with engine.connect() as conn:
            for table in ['products', 'sales', 'feedback', 'ingredients']:
                count = conn.execute(sqlalchemy.text(f"SELECT COUNT(*) FROM {table}")).scalar()
                assert count == 1
        engine.dispose()

    def test_is_idempotent_end_to_end(self, tmp_path):
        # Regression guard for the wiring itself: if pipeline.py ever forgot
        # to pass `schema` through to load.load_all(), this would still
        # "work" today (schema.yaml matches this fixture) but would be the
        # kind of silent drift these tests exist to catch.
        paths = _write_csvs(tmp_path)
        config_path = _write_config(tmp_path, paths)

        pipeline.run_pipeline(str(config_path), REAL_SCHEMA_PATH)
        pipeline.run_pipeline(str(config_path), REAL_SCHEMA_PATH)

        engine = sqlalchemy.create_engine(f"sqlite:///{paths['database']}")
        with engine.connect() as conn:
            count = conn.execute(sqlalchemy.text("SELECT COUNT(*) FROM sales")).scalar()
        engine.dispose()

        assert count == 1  # not 2

    def test_missing_csv_raises_file_not_found(self, tmp_path):
        paths = _write_csvs(tmp_path)
        paths['ingredient_costs_csv'] = str(tmp_path / 'does_not_exist.csv')
        config_path = _write_config(tmp_path, paths)

        with pytest.raises(FileNotFoundError):
            pipeline.run_pipeline(str(config_path), REAL_SCHEMA_PATH)
