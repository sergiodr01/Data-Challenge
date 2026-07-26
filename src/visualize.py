"""
Visualization module: renders the key business metrics from the loaded
SQLite database to static PNG charts under output/visualizations/.

Reads only from the database produced by load.py - never touches the raw
CSVs or the in-memory pipeline DataFrames - so these charts always reflect
exactly what's in symrise_data.db.
"""

import logging
import sqlite3
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Categorical slots (light mode), fixed order - see dataviz skill palette.
BLUE = "#2a78d6"
ORANGE = "#eb6834"
AQUA = "#1baf7a"
YELLOW = "#eda100"
MAGENTA = "#e87ba4"
GREEN = "#008300"
VIOLET = "#4a3aa7"
RED = "#e34948"
CATEGORICAL = [BLUE, ORANGE, AQUA, YELLOW, MAGENTA, GREEN, VIOLET, RED]

INK = "#0b0b0b"
SECONDARY_INK = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
SURFACE = "#fcfcfb"

plt.rcParams.update({
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "axes.edgecolor": MUTED,
    "axes.labelcolor": SECONDARY_INK,
    "axes.titlecolor": INK,
    "text.color": INK,
    "xtick.color": SECONDARY_INK,
    "ytick.color": SECONDARY_INK,
    "grid.color": GRID,
    "font.family": "sans-serif",
    "axes.spines.top": False,
    "axes.spines.right": False,
})


def _resolve(path: str) -> Path:
    resolved = Path(path)
    return resolved if resolved.is_absolute() else PROJECT_ROOT / resolved


def _save(fig: plt.Figure, out_dir: Path, filename: str) -> Path:
    out_path = out_dir / filename
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"Saved {out_path}")
    return out_path


def plot_revenue_by_category(conn: sqlite3.Connection, out_dir: Path) -> Path:
    df = pd.read_sql(
        """
        SELECT COALESCE(p.category, 'Unknown/Unmatched Product') AS category,
               SUM(s.total_amount_usd) AS revenue
        FROM sales s
        LEFT JOIN products p ON s.product_id = p.product_id
        GROUP BY category
        ORDER BY revenue DESC
        """,
        conn,
    )
    fig, ax = plt.subplots(figsize=(6, 4))
    colors = CATEGORICAL[: len(df)]
    ax.bar(df["category"], df["revenue"], color=colors, width=0.6)
    ax.set_title("Revenue by Product Category")
    ax.set_ylabel("Revenue (USD)")
    ax.grid(axis="y", linewidth=0.5)
    ax.set_axisbelow(True)
    for i, v in enumerate(df["revenue"]):
        ax.text(i, v, f"${v:,.0f}", ha="center", va="bottom", fontsize=9, color=SECONDARY_INK)
    return _save(fig, out_dir, "revenue_by_category.png")


def plot_satisfaction_by_region(conn: sqlite3.Connection, out_dir: Path) -> Path:
    df = pd.read_sql(
        """
        SELECT customer_region.region,
               AVG(f.overall_satisfaction) AS avg_satisfaction
        FROM feedback f
        JOIN (SELECT DISTINCT customer_id, product_id, region FROM sales) AS customer_region
            ON f.customer_id = customer_region.customer_id
           AND f.product_id = customer_region.product_id
        GROUP BY customer_region.region
        ORDER BY avg_satisfaction DESC
        """,
        conn,
    )
    fig, ax = plt.subplots(figsize=(6, 4))
    colors = CATEGORICAL[: len(df)]
    ax.barh(df["region"], df["avg_satisfaction"], color=colors, height=0.6)
    ax.invert_yaxis()
    ax.set_title("Average Customer Satisfaction by Region")
    ax.set_xlabel("Average Overall Satisfaction (0-5)")
    ax.set_xlim(0, 5)
    ax.grid(axis="x", linewidth=0.5)
    ax.set_axisbelow(True)
    for i, v in enumerate(df["avg_satisfaction"]):
        ax.text(v, i, f" {v:.2f}", va="center", fontsize=9, color=SECONDARY_INK)
    return _save(fig, out_dir, "satisfaction_by_region.png")


def plot_complexity_vs_satisfaction(conn: sqlite3.Connection, out_dir: Path) -> Path:
    df = pd.read_sql(
        """
        SELECT p.num_ingredients, f.overall_satisfaction
        FROM feedback f
        JOIN products p ON f.product_id = p.product_id
        WHERE p.num_ingredients IS NOT NULL
        """,
        conn,
    )
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.scatter(df["num_ingredients"], df["overall_satisfaction"], color=BLUE, alpha=0.6, s=40, edgecolors="none")
    corr = df["num_ingredients"].corr(df["overall_satisfaction"])
    ax.set_title(f"Product Complexity vs. Satisfaction (r = {corr:.2f})")
    ax.set_xlabel("Number of Ingredients")
    ax.set_ylabel("Overall Satisfaction (0-5)")
    ax.grid(linewidth=0.5)
    ax.set_axisbelow(True)
    return _save(fig, out_dir, "complexity_vs_satisfaction.png")


def plot_monthly_revenue_trend(conn: sqlite3.Connection, out_dir: Path) -> Path:
    df = pd.read_sql(
        """
        SELECT strftime('%Y-%m', transaction_date) AS year_month,
               SUM(total_amount_usd) AS revenue
        FROM sales
        GROUP BY year_month
        ORDER BY year_month
        """,
        conn,
    )
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(df["year_month"], df["revenue"], color=BLUE, linewidth=2, marker="o", markersize=5)
    ax.set_title("Monthly Revenue Trend")
    ax.set_ylabel("Revenue (USD)")
    ax.grid(axis="y", linewidth=0.5)
    ax.set_axisbelow(True)
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    return _save(fig, out_dir, "monthly_revenue_trend.png")


def plot_profit_margin_by_category(conn: sqlite3.Connection, out_dir: Path) -> Path:
    df = pd.read_sql(
        """
        SELECT p.category,
               SUM(s.total_amount_usd) - SUM(s.quantity_kg * COALESCE(i.cost_per_kg_usd, 0)) AS profit_margin_usd
        FROM sales s
        JOIN products p ON s.product_id = p.product_id
        LEFT JOIN ingredients i ON p.primary_ingredient = i.ingredient_name
        GROUP BY p.category
        ORDER BY profit_margin_usd DESC
        """,
        conn,
    )
    # Diverging encoding: positive margin in blue, negative in red - the sign
    # is the thing being communicated, not category identity.
    colors = [BLUE if v >= 0 else RED for v in df["profit_margin_usd"]]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(df["category"], df["profit_margin_usd"], color=colors, width=0.6)
    ax.axhline(0, color=MUTED, linewidth=1)
    ax.set_title("Estimated Profit Margin by Category")
    ax.set_ylabel("Revenue - Est. Ingredient Cost (USD)")
    ax.grid(axis="y", linewidth=0.5)
    ax.set_axisbelow(True)
    for i, v in enumerate(df["profit_margin_usd"]):
        ax.text(i, v, f"${v:,.0f}", ha="center", va="bottom" if v >= 0 else "top", fontsize=9, color=SECONDARY_INK)
    return _save(fig, out_dir, "profit_margin_by_category.png")


PLOTS = [
    plot_revenue_by_category,
    plot_satisfaction_by_region,
    plot_complexity_vs_satisfaction,
    plot_monthly_revenue_trend,
    plot_profit_margin_by_category,
]


def generate_all(database_path: str = "symrise_data.db", output_dir: str = "output/visualizations") -> list[Path]:
    """
    Render every chart in PLOTS against the given SQLite database and save
    them as PNGs under output_dir (created if missing).

    Returns:
        List of paths to the generated PNG files.
    """
    db_path = _resolve(database_path)
    out_dir = _resolve(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        paths = [plot(conn, out_dir) for plot in PLOTS]
    finally:
        conn.close()

    logger.info(f"Generated {len(paths)} visualization(s) in {out_dir}")
    return paths


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s:%(name)s:%(message)s")
    generate_all()
