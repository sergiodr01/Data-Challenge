import pandas as pd

from src import transform


class TestHelperFunctions:
    def test_strip_string_columns_trims_whitespace_on_every_text_column(self):
        df = pd.DataFrame({
            'name': [' Lemon Oil ', 'Rose Oil'],
            'category': ['Fragrance', ' Flavor'],
            'amount': [1.0, 2.0],  # numeric column - must be left untouched
        })
        out = transform._strip_string_columns(df)
        assert list(out['name']) == ['Lemon Oil', 'Rose Oil']
        assert list(out['category']) == ['Fragrance', 'Flavor']
        assert list(out['amount']) == [1.0, 2.0]

    def test_strip_string_columns_leaves_nulls_alone(self):
        df = pd.DataFrame({'name': [' Lemon Oil ', None]})
        out = transform._strip_string_columns(df)
        assert out['name'].iloc[0] == 'Lemon Oil'
        assert pd.isna(out['name'].iloc[1])

    def test_nan_negative_values_replaces_negatives_only(self):
        df = pd.DataFrame({'quantity_kg': [10.0, -5.0, 0.0, None]})
        out = transform._nan_negative_values(df, 'quantity_kg', 'sales')
        assert list(out['quantity_kg'].isna()) == [False, True, False, True]

    def test_nan_negative_values_is_no_op_when_all_valid(self):
        df = pd.DataFrame({'quantity_kg': [10.0, 5.0]})
        out = transform._nan_negative_values(df, 'quantity_kg', 'sales')
        assert list(out['quantity_kg']) == [10.0, 5.0]

    def test_canonicalize_matches_case_and_whitespace_insensitively(self):
        series = pd.Series(['emea', 'EMEA', 'North america'])
        out = transform._canonicalize(series, ['EMEA', 'APAC', 'LATAM', 'North America'])
        assert list(out) == ['EMEA', 'EMEA', 'North America']

    def test_canonicalize_turns_unrecognized_value_into_nan(self):
        series = pd.Series(['EMEA', 'Atlantis'])
        out = transform._canonicalize(series, ['EMEA', 'APAC', 'LATAM', 'North America'])
        assert out.iloc[0] == 'EMEA'
        assert pd.isna(out.iloc[1])


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

    def test_category_and_subcategory_are_title_cased(self, raw_products):
        raw_products['category'] = ['fragrance', 'flavor', 'FRAGRANCE', 'FRAGRANCE']
        raw_products['subcategory'] = ['fresh', 'sweet', 'floral', 'floral']
        out = transform.clean_products(raw_products)
        assert set(out['category']) <= {'Fragrance', 'Flavor'}
        assert set(out['subcategory']) <= {'Fresh', 'Sweet', 'Floral'}

    def test_region_developed_canonicalized(self, raw_products, schema):
        raw_products['region_developed'] = ['emea', ' EMEA', 'North america', 'North america']
        out = transform.clean_products(raw_products, schema)
        assert set(out['region_developed'].dropna()) <= {'EMEA', 'North America'}

    def test_unrecognized_region_becomes_nan(self, raw_products, schema):
        raw_products.loc[0, 'region_developed'] = 'Atlantis'
        out = transform.clean_products(raw_products, schema)
        assert pd.isna(out[out['product_id'] == 'P001'].iloc[0]['region_developed'])

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

    def test_region_canonicalized(self, raw_sales, schema):
        raw_sales['region'] = ['emea', 'north america', 'APAC', 'EMEA']
        out = transform.clean_sales(raw_sales, schema)
        assert set(out['region'].dropna()) <= {'EMEA', 'North America', 'APAC'}

    def test_sales_channel_normalized(self, raw_sales):
        raw_sales['sales_channel'] = ['direct', 'DISTRIBUTOR', 'Direct', 'direct']
        out = transform.clean_sales(raw_sales)
        assert set(out['sales_channel']) <= {'Direct', 'Distributor'}

    def test_negative_economic_values_become_nan(self, raw_sales):
        raw_sales.loc[0, 'quantity_kg'] = -25.5
        raw_sales.loc[1, 'unit_price_usd'] = -200.0
        out = transform.clean_sales(raw_sales)
        assert pd.isna(out.iloc[0]['quantity_kg'])
        assert pd.isna(out.iloc[1]['unit_price_usd'])


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

    def test_genuine_conflict_is_logged_as_warning(self, raw_ingredients, caplog):
        # raw_ingredients' two 'Lemon Oil' rows (I001, I018) have different
        # cost/supplier - a real conflict, not a redundant label.
        with caplog.at_level('WARNING', logger='src.transform'):
            transform.clean_ingredients(raw_ingredients)
        assert any('conflicting non-identical' in r.message for r in caplog.records)

    def test_identical_except_id_is_merged_as_info_not_warning(self, caplog):
        # Same case as the real 'Lemon Oil' data: two ingredient_ids share a
        # name but agree on cost/supplier/category - nothing real is lost
        # by merging, so this should be an info log, not a warning.
        df = pd.DataFrame({
            'ingredient_id': ['I001', 'I018'],
            'ingredient_name': ['Lemon Oil', 'Lemon Oil'],
            'cost_per_kg_usd': [45.5, 45.5],
            'supplier': ['CitrusSupply Co', 'CitrusSupply Co'],
            'last_updated': ['2024-08-01', '2024-08-01'],
            'category': ['Essential Oil', 'Essential Oil'],
        })
        with caplog.at_level('INFO', logger='src.transform'):
            out = transform.clean_ingredients(df)

        assert len(out) == 1
        assert out.iloc[0]['ingredient_id'] == 'I001'
        assert any('merged safely' in r.message for r in caplog.records)
        assert not any(r.levelname == 'WARNING' for r in caplog.records)

    def test_last_updated_parsed_to_datetime(self, raw_ingredients):
        out = transform.clean_ingredients(raw_ingredients)
        assert pd.api.types.is_datetime64_any_dtype(out['last_updated'])

    def test_category_is_title_cased(self, raw_ingredients):
        raw_ingredients['category'] = ['essential oil', 'EXTRACT', 'essential oil']
        out = transform.clean_ingredients(raw_ingredients)
        assert set(out['category']) <= {'Essential Oil', 'Extract'}

    def test_negative_cost_becomes_nan(self, raw_ingredients):
        raw_ingredients.loc[1, 'cost_per_kg_usd'] = -120.0
        out = transform.clean_ingredients(raw_ingredients)
        row = out[out['ingredient_id'] == 'I002'].iloc[0]
        assert pd.isna(row['cost_per_kg_usd'])


class TestTransformAll:
    def test_returns_all_four_datasets_cleaned(self, raw_data):
        cleaned = transform.transform_all(raw_data, thresholds={'rating_min': 0, 'rating_max': 5})
        assert set(cleaned) == {'products', 'sales', 'feedback', 'ingredients'}
        assert cleaned['feedback']['quality_rating'].max() <= 5
