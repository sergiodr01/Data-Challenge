-- SQL queries answering the 5 business questions from challengers/README.md.
-- Run against symrise_data.db (produced by `python -m src.pipeline`).
--
-- Schema recap (see src/load.py):
--   products(product_id PK, product_name, category, subcategory, launch_date,
--            status, num_ingredients, primary_ingredient, region_developed)
--   ingredients(ingredient_id PK, ingredient_name, cost_per_kg_usd, supplier,
--               last_updated, category)
--   sales(transaction_id PK, product_id FK, customer_id, transaction_date,
--         quantity_kg, unit_price_usd, total_amount_usd, region, sales_channel)
--   feedback(feedback_id PK, product_id FK, customer_id, feedback_date,
--            quality_rating, performance_rating, value_rating,
--            overall_satisfaction, would_reorder, comments)


-- =====================================================================
-- Q1. What are the top 5 best-selling product categories by revenue?
-- =====================================================================
-- LEFT JOIN (not INNER): one sales row references a product_id that
-- doesn't exist in products (see transform.py/validate.py - we kept that
-- row instead of dropping real revenue). It surfaces here under
-- 'Unknown/Unmatched Product' instead of silently vanishing from the total.
-- There are only 2 categories in the data (Flavor, Fragrance), so "top 5"
-- returns everything there is; the query itself doesn't assume a count.
SELECT
    COALESCE(p.category, 'Unknown/Unmatched Product') AS category,
    SUM(s.total_amount_usd) AS total_revenue,
    COUNT(*) AS num_transactions
FROM sales s
LEFT JOIN products p ON s.product_id = p.product_id
GROUP BY category
ORDER BY total_revenue DESC
LIMIT 5;


-- =====================================================================
-- Q2. Which region has the highest average customer satisfaction score?
-- =====================================================================
-- feedback has no region column of its own - only sales does. We infer a
-- feedback row's region via the (customer_id, product_id) pair it shares
-- with sales, on the assumption that a given customer buys a given product
-- from one consistent region (true in this dataset: the one duplicated
-- (customer_id, product_id) combo - the T011 collision - has the same
-- region on both rows). The inner SELECT DISTINCT collapses that
-- duplication so a feedback row can't fan out into two joined rows and
-- get double-counted in the average.
SELECT
    customer_region.region,
    ROUND(AVG(f.overall_satisfaction), 3) AS avg_overall_satisfaction,
    COUNT(*) AS num_feedback
FROM feedback f
JOIN (
    SELECT DISTINCT customer_id, product_id, region FROM sales
) AS customer_region
    ON f.customer_id = customer_region.customer_id
   AND f.product_id = customer_region.product_id
GROUP BY customer_region.region
ORDER BY avg_overall_satisfaction DESC;
-- The top row is the answer; the full ranking is left visible for context.


-- =====================================================================
-- Q3. Relationship between product complexity (num_ingredients) and
--     customer satisfaction?
-- =====================================================================
-- SQLite has no built-in CORR()/STDDEV() aggregate, so the Pearson
-- correlation coefficient itself can't be computed in pure SQL - it needs
-- to be computed downstream (e.g. pandas' .corr()) on the raw pairs
-- returned by query 3a. Query 3b gives a SQL-only, eyeball-able view of
-- the same relationship (average satisfaction per ingredient count).
-- num_ingredients is left NULL for the one product where it's
-- unrecoverable (see transform.py) - excluded here via the JOIN/WHERE
-- since there's nothing honest to correlate it against.

-- 3a. Raw (num_ingredients, overall_satisfaction) pairs for pandas .corr()
SELECT
    p.num_ingredients,
    f.overall_satisfaction
FROM feedback f
JOIN products p ON f.product_id = p.product_id
WHERE p.num_ingredients IS NOT NULL;

-- 3b. Grouped view: average satisfaction per ingredient count
SELECT
    p.num_ingredients,
    ROUND(AVG(f.overall_satisfaction), 3) AS avg_overall_satisfaction,
    COUNT(*) AS num_feedback
FROM feedback f
JOIN products p ON f.product_id = p.product_id
WHERE p.num_ingredients IS NOT NULL
GROUP BY p.num_ingredients
ORDER BY p.num_ingredients;


-- =====================================================================
-- Q4. Products with declining sales trends (last 2 quarters)
-- =====================================================================
-- "Last 2 quarters" is computed dynamically per product from whatever
-- quarters it actually has sales in, not hardcoded calendar dates -
-- products can have gaps or different launch dates, so a fixed date
-- range would misclassify products that simply weren't sold in one of
-- two arbitrary fixed quarters. A product only appears here if it has
-- at least 2 distinct quarters of sales AND its most recent quarter's
-- revenue is lower than the one before it.
WITH quarterly_sales AS (
    SELECT
        product_id,
        CAST(strftime('%Y', transaction_date) AS INTEGER) * 10
            + ((CAST(strftime('%m', transaction_date) AS INTEGER) - 1) / 3 + 1) AS year_quarter,
        SUM(total_amount_usd) AS revenue
    FROM sales
    WHERE product_id IS NOT NULL
    GROUP BY product_id, year_quarter
),
ranked AS (
    SELECT
        product_id,
        year_quarter,
        revenue,
        ROW_NUMBER() OVER (PARTITION BY product_id ORDER BY year_quarter DESC) AS quarter_rank
    FROM quarterly_sales
)
SELECT
    curr.product_id,
    p.product_name,
    prev.year_quarter AS previous_quarter,
    prev.revenue AS previous_quarter_revenue,
    curr.year_quarter AS latest_quarter,
    curr.revenue AS latest_quarter_revenue,
    ROUND((curr.revenue - prev.revenue) * 100.0 / prev.revenue, 1) AS pct_change
FROM ranked curr
JOIN ranked prev
    ON curr.product_id = prev.product_id
   AND curr.quarter_rank = 1
   AND prev.quarter_rank = 2
LEFT JOIN products p ON curr.product_id = p.product_id
WHERE curr.revenue < prev.revenue
ORDER BY pct_change ASC;


-- =====================================================================
-- Q5. Profit margin per product category (Revenue - Ingredient Costs)
-- =====================================================================
-- Data limitation (documented in load.py): products.csv only records one
-- primary_ingredient per product, not the full ingredient list implied by
-- num_ingredients. So "ingredient cost" here is an approximation: primary
-- ingredient's cost_per_kg_usd x quantity_kg sold, not the true fully-
-- loaded formulation cost. Treat this as a directional estimate, not an
-- exact margin. Joined on ingredient_name (primary_ingredient matches
-- ingredient_name exactly for every product in this dataset - verified,
-- not assumed).
SELECT
    p.category,
    SUM(s.total_amount_usd) AS total_revenue,
    SUM(s.quantity_kg * COALESCE(i.cost_per_kg_usd, 0)) AS total_ingredient_cost_estimate,
    SUM(s.total_amount_usd) - SUM(s.quantity_kg * COALESCE(i.cost_per_kg_usd, 0)) AS profit_margin_usd,
    ROUND(
        (SUM(s.total_amount_usd) - SUM(s.quantity_kg * COALESCE(i.cost_per_kg_usd, 0))) * 100.0
        / SUM(s.total_amount_usd), 1
    ) AS profit_margin_pct
FROM sales s
JOIN products p ON s.product_id = p.product_id
LEFT JOIN ingredients i ON p.primary_ingredient = i.ingredient_name
GROUP BY p.category
ORDER BY profit_margin_usd DESC;
