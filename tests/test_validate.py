import pandas as pd
import pytest

from src import validate


class TestValidateAll:
    def test_flags_all_seeded_issues(self, raw_data):
        report = validate.validate_all(raw_data, thresholds={'rating_min': 0, 'rating_max': 5})

        assert any("null value(s) in 'product_name'" in i for i in report['products'])
        assert any("value(s) in 'num_ingredients' outside" in i for i in report['products'])
        assert any("duplicate 'product_id'" in i for i in report['products'])

        assert any("null value(s) in 'customer_id'" in i for i in report['sales'])
        assert any("null value(s) in 'total_amount_usd'" in i for i in report['sales'])
        assert any("duplicate 'transaction_id'" in i for i in report['sales'])
        assert any("'product_id' value(s) not found in products" in i for i in report['sales'])

        assert any("null value(s) in 'quality_rating'" in i for i in report['feedback'])
        assert any("value(s) in 'overall_satisfaction' outside" in i for i in report['feedback'])
        assert any("'product_id' value(s) not found in products" in i for i in report['feedback'])

        assert any("duplicate 'ingredient_name'" in i for i in report['ingredients'])

    def test_clean_data_produces_no_issues(self):
        clean = {
            'products': pd.DataFrame({
                'product_id': ['P001'],
                'product_name': ['Citrus Burst'],
                'category': ['Fragrance'],
                'num_ingredients': [12],
            }),
            'sales': pd.DataFrame({
                'transaction_id': ['T001'],
                'product_id': ['P001'],
                'customer_id': ['C001'],
                'total_amount_usd': [100.0],
            }),
            'feedback': pd.DataFrame({
                'feedback_id': ['F001'],
                'product_id': ['P001'],
                'customer_id': ['C001'],
                'quality_rating': [4.5],
                'overall_satisfaction': [4.5],
            }),
            'ingredients': pd.DataFrame({
                'ingredient_id': ['I001'],
                'ingredient_name': ['Lemon Oil'],
                'cost_per_kg_usd': [45.5],
            }),
        }
        report = validate.validate_all(clean)
        assert all(issues == [] for issues in report.values())

    def test_custom_rating_thresholds_are_respected(self):
        feedback = pd.DataFrame({
            'feedback_id': ['F001'],
            'product_id': ['P001'],
            'customer_id': ['C001'],
            'quality_rating': [8.0],
            'overall_satisfaction': [8.0],
        })
        data = {
            'products': pd.DataFrame({'product_id': ['P001'], 'product_name': ['X'], 'category': ['Y'], 'num_ingredients': [1]}),
            'sales': pd.DataFrame({'transaction_id': [], 'product_id': [], 'customer_id': [], 'total_amount_usd': []}),
            'feedback': feedback,
            'ingredients': pd.DataFrame({'ingredient_id': [], 'ingredient_name': [], 'cost_per_kg_usd': []}),
        }
        # A rating of 8 is in-range under a widened threshold.
        report = validate.validate_all(data, thresholds={'rating_min': 0, 'rating_max': 10})
        assert not any("outside" in i for i in report['feedback'])

        # ...but out-of-range under the default [0, 5].
        report_default = validate.validate_all(data)
        assert any("outside" in i for i in report_default['feedback'])


class TestValidateStructure:
    def test_missing_required_column_raises(self, raw_data):
        broken = dict(raw_data)
        broken['products'] = raw_data['products'].drop(columns=['category'])

        with pytest.raises(validate.SchemaValidationError, match="missing required column 'category'"):
            validate.validate_structure(broken)

    def test_missing_column_error_names_the_dataset(self, raw_data):
        broken = dict(raw_data)
        broken['products'] = raw_data['products'].drop(columns=['category'])

        with pytest.raises(validate.SchemaValidationError, match=r"\[products\]"):
            validate.validate_structure(broken)

    def test_empty_dataset_raises(self, raw_data):
        broken = dict(raw_data)
        broken['products'] = raw_data['products'].iloc[0:0]  # keep columns, drop all rows

        with pytest.raises(validate.SchemaValidationError, match="dataset is empty"):
            validate.validate_structure(broken)

    def test_valid_structure_does_not_raise(self, raw_data):
        validate.validate_structure(raw_data)  # should not raise

    def test_check_structure_reports_without_raising(self, raw_data):
        broken = dict(raw_data)
        broken['products'] = raw_data['products'].drop(columns=['category'])

        report = validate.check_structure(broken)

        assert any("missing required column 'category'" in i for i in report['products'])
        assert report['sales'] == []


class TestCheckHelpers:
    def test_check_not_empty_flags_zero_rows(self):
        df = pd.DataFrame({'id': []})
        issues = validate._check_not_empty(df)
        assert issues == ["dataset is empty (0 rows)"]

    def test_check_not_empty_accepts_nonempty(self):
        df = pd.DataFrame({'id': ['A']})
        assert validate._check_not_empty(df) == []

    def test_check_dates_accepts_mixed_valid_formats(self):
        df = pd.DataFrame({'d': ['2024-01-05', '7/15/2024', '07-18-2024']})
        issues = validate._check_dates(df, 'd')
        assert issues == []

    def test_check_dates_flags_unparseable(self):
        df = pd.DataFrame({'d': ['2024-01-05', 'not-a-date']})
        issues = validate._check_dates(df, 'd')
        assert len(issues) == 1
        assert '1 unparseable' in issues[0]

    def test_check_range_respects_bounds(self):
        df = pd.DataFrame({'r': [0, 5, -1, 6, None]})
        issues = validate._check_range(df, 'r', min_val=0, max_val=5)
        assert '2 value(s)' in issues[0]

    def test_check_duplicates_counts_extra_occurrences_only(self):
        df = pd.DataFrame({'id': ['A', 'A', 'A', 'B']})
        issues = validate._check_duplicates(df, 'id')
        assert '2 duplicate' in issues[0]
