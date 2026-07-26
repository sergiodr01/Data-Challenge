-- Exploratory / analytical SQL queries beyond the 5 required business questions.
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
-- A1. Monthly revenue trend
-- =====================================================================
-- Overall revenue trajectory across the full sales history, independent
-- of category/product breakdowns - useful as a sanity check before
-- trusting any per-product trend (e.g. Q4 in queries.sql).
SELECT
    strftime('%Y-%m', transaction_date) AS year_month,
    SUM(total_amount_usd) AS revenue,
    COUNT(*) AS num_transactions
FROM sales
GROUP BY year_month
ORDER BY year_month;


-- =====================================================================
-- A2. Revenue and product count by status (Active / Discontinued / ...)
-- =====================================================================
-- Shows how much revenue rides on products that are no longer actively
-- sold, and whether the catalog is dominated by active products.
SELECT
    COALESCE(p.status, 'Unknown') AS status,
    COUNT(DISTINCT p.product_id) AS num_products,
    SUM(s.total_amount_usd) AS total_revenue
FROM products p
LEFT JOIN sales s ON s.product_id = p.product_id
GROUP BY status
ORDER BY total_revenue DESC;


-- =====================================================================
-- A3. Sales channel mix: revenue and average order size
-- =====================================================================
SELECT
    sales_channel,
    COUNT(*) AS num_transactions,
    SUM(total_amount_usd) AS total_revenue,
    ROUND(AVG(total_amount_usd), 2) AS avg_order_value,
    ROUND(AVG(quantity_kg), 2) AS avg_quantity_kg
FROM sales
GROUP BY sales_channel
ORDER BY total_revenue DESC;


-- =====================================================================
-- A4. Region developed vs. region sold: does a product sell best in the
--     region it was developed in?
-- =====================================================================
SELECT
    p.region_developed,
    s.region AS region_sold,
    SUM(s.total_amount_usd) AS revenue,
    COUNT(*) AS num_transactions
FROM sales s
JOIN products p ON s.product_id = p.product_id
GROUP BY p.region_developed, s.region
ORDER BY p.region_developed, revenue DESC;


-- =====================================================================
-- A5. Top 10 products by revenue, with their average satisfaction
-- =====================================================================
-- Flags products that sell well but score poorly (or vice versa) -
-- useful for spotting a product whose sales are outrunning its
-- reputation, which queries.sql's per-category rollups can't show.
SELECT
    p.product_id,
    p.product_name,
    p.category,
    SUM(s.total_amount_usd) AS total_revenue,
    ROUND(AVG(f.overall_satisfaction), 2) AS avg_satisfaction,
    COUNT(DISTINCT s.transaction_id) AS num_transactions,
    COUNT(DISTINCT f.feedback_id) AS num_feedback
FROM sales s
JOIN products p ON s.product_id = p.product_id
LEFT JOIN feedback f ON f.product_id = p.product_id
GROUP BY p.product_id, p.product_name, p.category
ORDER BY total_revenue DESC
LIMIT 10;


-- =====================================================================
-- A6. Would-reorder rate by category
-- =====================================================================
-- A cheap proxy for loyalty/satisfaction that's independent of the
-- numeric rating scales - a category can score well on ratings but
-- still have a weak reorder intent, or vice versa.
SELECT
    p.category,
    COUNT(*) AS num_feedback,
    SUM(CASE WHEN f.would_reorder = 'Yes' THEN 1 ELSE 0 END) AS num_would_reorder,
    ROUND(
        100.0 * SUM(CASE WHEN f.would_reorder = 'Yes' THEN 1 ELSE 0 END) / COUNT(*), 1
    ) AS reorder_rate_pct
FROM feedback f
JOIN products p ON f.product_id = p.product_id
GROUP BY p.category
ORDER BY reorder_rate_pct DESC;


-- =====================================================================
-- A7. Ingredient cost distribution by category
-- =====================================================================
-- Context for the profit-margin approximation in queries.sql Q5: shows
-- whether high/low margin categories are explained by ingredient cost
-- spread rather than pricing/volume alone.
SELECT
    category,
    COUNT(*) AS num_ingredients,
    ROUND(MIN(cost_per_kg_usd), 2) AS min_cost_per_kg,
    ROUND(AVG(cost_per_kg_usd), 2) AS avg_cost_per_kg,
    ROUND(MAX(cost_per_kg_usd), 2) AS max_cost_per_kg
FROM ingredients
GROUP BY category
ORDER BY avg_cost_per_kg DESC;


-- =====================================================================
-- A8. Customer concentration: revenue share of top 10 customers
-- =====================================================================
-- Highlights revenue concentration risk - excludes the 'UNKNOWN'
-- customer_id introduced by transform.py for rows with an originally
-- missing customer_id, since that bucket isn't a real customer.
SELECT
    customer_id,
    SUM(total_amount_usd) AS total_revenue,
    COUNT(*) AS num_transactions,
    ROUND(100.0 * SUM(total_amount_usd) / (SELECT SUM(total_amount_usd) FROM sales), 2) AS pct_of_total_revenue
FROM sales
WHERE customer_id != 'UNKNOWN'
GROUP BY customer_id
ORDER BY total_revenue DESC
LIMIT 10;


-- =====================================================================
-- A9. Products never sold
-- =====================================================================
-- Catalog items with zero transactions - candidates for discontinuation
-- review, or a sign of a launch that hasn't ramped up yet.
SELECT
    p.product_id,
    p.product_name,
    p.category,
    p.status,
    p.launch_date
FROM products p
LEFT JOIN sales s ON s.product_id = p.product_id
WHERE s.transaction_id IS NULL
ORDER BY p.launch_date DESC;


-- =====================================================================
-- A10. Rating breakdown: quality vs. performance vs. value
-- =====================================================================
-- Decomposes overall_satisfaction into its three components per category,
-- to see which lever (quality, performance, or perceived value) is
-- dragging a category's overall score down.
SELECT
    p.category,
    ROUND(AVG(f.quality_rating), 2) AS avg_quality,
    ROUND(AVG(f.performance_rating), 2) AS avg_performance,
    ROUND(AVG(f.value_rating), 2) AS avg_value,
    ROUND(AVG(f.overall_satisfaction), 2) AS avg_overall
FROM feedback f
JOIN products p ON f.product_id = p.product_id
GROUP BY p.category
ORDER BY avg_overall DESC;
