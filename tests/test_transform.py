import pandas as pd

from src import transform


class TestCleanProducts:
    def test_drops_exact_duplicate_rows(self, raw_products):
        before = len(raw_products)
        out = transform.clean_products(raw_products)
        # The P003 row is an exact duplicate (same values in every column).
        assert len(out) == before - 1

    def test_negative_num_ingredients_becomes_nan(self, raw_products):
        out = transform.clean_products(raw_products)
        row = out[out['product_id'] == 'P002'].iloc[0]
        assert pd.isna(row['num_ingredients'])

    def test_missing_product_name_filled_from_id(self, raw_products):
        out = transform.clean_products(raw_products)
        row = out[out['product_id'] == 'P002'].iloc[0]
        assert row['product_name'] == 'Unknown (P002)'

    def test_status_normalized(self, raw_products):
        out = transform.clean_products(raw_products)
        assert set(out['status']) <= {'Active', 'Discontinued'}

    def test_launch_date_parsed_to_datetime(self, raw_products):
        out = transform.clean_products(raw_products)
        assert pd.api.types.is_datetime64_any_dtype(out['launch_date'])
        assert out['launch_date'].notna().all()

    def test_conflicting_duplicate_ids_keep_first_and_drop_rest(self):
        df = pd.DataFrame({
            'product_id': ['P001', 'P001'],
            'product_name': ['Version A', 'Version B'],
            'category': ['Fragrance', 'Fragrance'],
            'subcategory': ['Fresh', 'Fresh'],
            'launch_date': ['2023-01-01', '2023-01-01'],
            'status': ['Active', 'Active'],
            'num_ingredients': [5, 9],
            'primary_ingredient': ['Lemon Oil', 'Lemon Oil'],
            'region_developed': ['EMEA', 'EMEA'],
        })
        out = transform.clean_products(df)
        assert len(out) == 1
        assert out.iloc[0]['product_name'] == 'Version A'


class TestCleanSales:
    def test_recomputes_missing_total_from_qty_times_price(self, raw_sales):
        out = transform.clean_sales(raw_sales)
        row = out[out['transaction_id'] == 'T002'].iloc[0]
        assert row['total_amount_usd'] == 30.0 * 200.0

    def test_missing_customer_id_filled_with_unknown(self, raw_sales):
        out = transform.clean_sales(raw_sales)
        row = out[out['transaction_id'] == 'T002'].iloc[0]
        assert row['customer_id'] == 'UNKNOWN'

    def test_colliding_transaction_id_renamed_not_dropped(self, raw_sales):
        before = len(raw_sales)
        out = transform.clean_sales(raw_sales)
        # The two T003 rows differ (product_id/date/amount), so both survive
        # under distinct ids instead of one being silently dropped.
        assert len(out) == before
        assert 'T003-DUP1' in out['transaction_id'].values

    def test_transaction_date_parsed_to_datetime(self, raw_sales):
        out = transform.clean_sales(raw_sales)
        assert pd.api.types.is_datetime64_any_dtype(out['transaction_date'])


class TestCleanFeedback:
    def test_out_of_range_ratings_clipped(self, raw_feedback):
        out = transform.clean_feedback(raw_feedback, rating_min=0, rating_max=5)
        row = out[out['feedback_id'] == 'F003'].iloc[0]
        assert row['quality_rating'] == 5.0
        assert row['overall_satisfaction'] == 5.0

    def test_missing_customer_id_filled_with_unknown(self, raw_feedback):
        out = transform.clean_feedback(raw_feedback)
        row = out[out['feedback_id'] == 'F002'].iloc[0]
        assert row['customer_id'] == 'UNKNOWN'

    def test_would_reorder_normalized(self, raw_feedback):
        out = transform.clean_feedback(raw_feedback)
        assert set(out['would_reorder']) <= {'Yes', 'No'}

    def test_respects_custom_thresholds(self, raw_feedback):
        # Under a widened [0, 10] threshold, the rating of 6.0 needs no clipping.
        out = transform.clean_feedback(raw_feedback, rating_min=0, rating_max=10)
        row = out[out['feedback_id'] == 'F003'].iloc[0]
        assert row['quality_rating'] == 6.0


class TestCleanIngredients:
    def test_duplicate_ingredient_name_conflict_keeps_first(self, raw_ingredients):
        out = transform.clean_ingredients(raw_ingredients)
        matches = out[out['ingredient_name'] == 'Lemon Oil']
        assert len(matches) == 1
        assert matches.iloc[0]['ingredient_id'] == 'I001'

    def test_last_updated_parsed_to_datetime(self, raw_ingredients):
        out = transform.clean_ingredients(raw_ingredients)
        assert pd.api.types.is_datetime64_any_dtype(out['last_updated'])


class TestTransformAll:
    def test_returns_all_four_datasets_cleaned(self, raw_data):
        cleaned = transform.transform_all(raw_data, thresholds={'rating_min': 0, 'rating_max': 5})
        assert set(cleaned) == {'products', 'sales', 'feedback', 'ingredients'}
        assert cleaned['feedback']['quality_rating'].max() <= 5
