# Business Question Answers

All queries live in `sql/queries.sql` with full comments on their
assumptions; this document states the results and what they mean. Numbers
were produced by running those queries against `symrise_data.db` after
`python -m src.pipeline`. See `output/data_quality_report.md` for how the
underlying data was cleaned.

## Q1. Top 5 best-selling product categories by revenue

| Category | Total Revenue (USD) | Transactions |
|---|---|---|
| Flavor | $298,425 | 47 |
| Fragrance | $191,096 | 42 |
| Unknown/Unmatched Product | $5,400 | 1 |

**Answer:** There are only 2 real product categories in this dataset —
**Flavor ($298,425)** and **Fragrance ($191,096)** — so "top 5" returns
everything there is. Flavor outsells Fragrance by roughly 1.56x.

The third row isn't a category: it's the one sale referencing
`product_id = 'P999'`, which doesn't exist in `products.csv`. It's shown
separately (via `LEFT JOIN`) instead of being silently dropped or wrongly
folded into an existing category, since we don't actually know what that
product was.

## Q2. Region with the highest average customer satisfaction score

| Region | Avg. Overall Satisfaction | Feedback Count |
|---|---|---|
| **North America** | **4.65** | 12 |
| EMEA | 4.38 | 21 |
| LATAM | 4.13 | 8 |
| APAC | 4.07 | 14 |

**Answer: North America**, with an average `overall_satisfaction` of 4.65
out of 5, ahead of EMEA (4.38), LATAM (4.13), and APAC (4.07).

Caveat: `customer_feedback.csv` has no `region` column of its own. Region
was inferred by matching each feedback row to a sales transaction sharing
the same `(customer_id, product_id)` pair, assuming a customer buys a given
product from one consistent region (true everywhere it could be checked in
this dataset). North America's small lead over EMEA (4.65 vs 4.38) is based
on only 12 vs 21 data points, so treat the ranking as directional rather
than statistically conclusive.

## Q3. Relationship between product complexity and customer satisfaction

**Pearson correlation coefficient: r = -0.264** (n = 53 product-feedback pairs)

| num_ingredients | Avg. Satisfaction | Feedback Count |
|---|---|---|
| 5 | 4.70 | 3 |
| 6 | 4.60 | 4 |
| 7 | 4.20 | 5 |
| 8 | 4.43 | 7 |
| 9 | 4.15 | 4 |
| 10 | 4.70 | 3 |
| 11 | 4.03 | 3 |
| 12 | 4.33 | 6 |
| 13 | 4.87 | 3 |
| 14 | 4.38 | 4 |
| 15 | 4.13 | 3 |
| 16 | 4.50 | 3 |
| 17 | 2.75 | 2 |
| 18 | 4.50 | 3 |

**Answer:** There's a **weak negative correlation** (r = -0.264) between the
number of ingredients in a product and its customer satisfaction score —
more complex formulations trend slightly toward lower satisfaction, but the
relationship is weak, not a strong predictor. The grouped averages aren't
monotonic (13 ingredients averages 4.87, higher than every smaller bucket
except 5 and 10), and the lowest score in the table (2.75, at 17
ingredients) comes from only 2 feedback records — too small a sample to
treat as a real trend on its own rather than noise.

SQLite has no built-in `CORR()` aggregate, so this coefficient was computed
with `pandas.Series.corr()` on the raw pairs returned by `sql/queries.sql`
Q3a; `sql/queries.sql` Q3b provides the same grouped-average view directly
in SQL for a quick sanity check without leaving the database.

## Q4. Products with declining sales trends (last 2 quarters)

| Product | Previous Quarter Revenue | Latest Quarter Revenue | Change |
|---|---|---|---|
| Green Tea Essence (P007) | $6,600 | $3,300 | -50.0% |
| Rose Garden (P008) | $11,970 | $5,985 | -50.0% |
| Mango Tango (P009) | $12,395 | $6,197.50 | -50.0% |
| Peach Nectar (P014) | $10,980 | $5,490 | -50.0% |
| Sandalwood Mystic (P010) | $8,190 | $4,192.50 | -48.8% |
| Lavender Fields (P012) | $5,637.50 | $5,535 | -1.8% |

**Answer:** 6 products show a decline between their two most recent
quarters of recorded sales, ranging from a marginal -1.8% (Lavender Fields)
to five products essentially halving quarter-over-quarter (~-49% to -50%).

Caveat on methodology: "last 2 quarters" is computed **per product**, from
whichever two quarters that product actually has sales in — not a fixed
calendar date range. Products launched or discontinued at different times,
so a hardcoded range (e.g. "Q2 vs Q3 2024" for every product) would have
misclassified products with no sales in one of those two arbitrary
quarters as neither improving nor declining, when in fact they just weren't
being sold yet or already stopped. A product only appears in this list if
it has at least 2 distinct quarters of sales data and its most recent one
is lower than the one before.

## Q5. Profit margin per product category (Revenue - Ingredient Costs)

| Category | Revenue | Ingredient Cost (est.) | Profit Margin | Margin % |
|---|---|---|---|---|
| Flavor | $298,425 | $94,946.50 | $203,478.50 | 68.2% |
| Fragrance | $191,096 | $95,842.88 | $95,253.13 | 49.8% |

**Answer:** **Flavor has the higher margin, at 68.2%** ($203,478.50 profit
on $298,425 revenue), compared to **Fragrance at 49.8%** ($95,253.13 profit
on $191,096 revenue). Flavor products are both higher-revenue and
higher-margin in this dataset.

Important limitation: `products.csv` records only **one**
`primary_ingredient` per product, not the full ingredient list implied by
`num_ingredients` (e.g. a product with 12 ingredients still only has 1
ingredient with a known cost). "Ingredient cost" here is
`primary_ingredient`'s `cost_per_kg_usd` x `quantity_kg` sold — a
directional estimate of formulation cost, not the true fully-loaded cost of
every ingredient in the product. The real margin is almost certainly lower
than shown, since only a fraction of each product's ingredients are being
costed. This is a data limitation, not something fixable in the pipeline:
answering this question exactly would require a product-to-ingredient
bill-of-materials table that doesn't exist in the provided datasets.
