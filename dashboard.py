"""
dashboard.py
------------
Reads the clean data from the SQLite database (ecommerce.db), asks it
questions using SQL, and draws a one-page dashboard with two charts:
  1. Monthly revenue (line chart)
  2. Revenue by product category (bar chart)

Run pipeline.py first, because this script needs ecommerce.db to exist.
"""

from pathlib import Path
import sqlite3

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import pandas as pd

# ----------------------------------------------------------------------
# Settings: file locations and colours
# ----------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "ecommerce.db"
CHART_FILE = BASE_DIR / "dashboard.png"

SURFACE = "#fcfcfb"     # background of the page
TEXT = "#0b0b0b"        # main text (near black)
TEXT_SOFT = "#52514e"   # secondary text (dark grey)
GRID = "#e4e3df"        # very light grey for grid lines
BLUE = "#2a78d6"        # the colour of our data


# ----------------------------------------------------------------------
# A small helper that sends a SQL question to the database
# ----------------------------------------------------------------------
def run_query(sql):
    """Send one SQL query to the database and return the answer as a table."""
    conn = sqlite3.connect(DB_FILE)
    result = pd.read_sql_query(sql, conn)
    conn.close()
    return result


# ----------------------------------------------------------------------
# The three SQL questions we ask
# ----------------------------------------------------------------------
SUMMARY_SQL = """
    SELECT
        COUNT(*)                     AS total_orders,
        COUNT(DISTINCT customer_id)  AS unique_customers,
        ROUND(SUM(revenue), 2)       AS total_revenue,
        ROUND(AVG(revenue), 2)       AS avg_order_value
    FROM orders;
"""

MONTHLY_SQL = """
    SELECT
        strftime('%Y-%m', order_date)  AS month,
        ROUND(SUM(revenue), 2)         AS revenue
    FROM orders
    GROUP BY month
    ORDER BY month;
"""

CATEGORY_SQL = """
    SELECT
        product_category,
        ROUND(SUM(revenue), 2)  AS revenue,
        COUNT(*)                AS orders
    FROM orders
    GROUP BY product_category
    ORDER BY revenue DESC;
"""


# ----------------------------------------------------------------------
# Drawing helpers
# ----------------------------------------------------------------------
def money_in_thousands(value, _position):
    """Turn 20000 into $20k, so axis labels stay short."""
    if value == 0:
        return "\\$0"
    return f"\\${value / 1000:,.0f}k"


def tidy_axes(ax):
    """Remove clutter: no box around the chart, quiet grey text."""
    for side in ["top", "right", "left"]:
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=TEXT_SOFT, length=0, labelsize=10)
    ax.set_facecolor(SURFACE)


def draw_monthly_chart(ax, monthly):
    """Line chart: revenue for each month, with the best month labelled."""
    tidy_axes(ax)
    positions = list(range(len(monthly)))
    month_names = pd.to_datetime(monthly["month"] + "-01").dt.strftime("%b")

    ax.plot(positions, monthly["revenue"], color=BLUE, linewidth=2)

    # Mark and label the best month
    best = monthly["revenue"].idxmax()
    best_value = monthly["revenue"].max()
    ax.plot(
        best, best_value, marker="o", markersize=9,
        color=BLUE, markeredgecolor=SURFACE, markeredgewidth=2,
    )
    if best < len(positions) / 2:
        label_side, label_shift = "left", 10    # best month is on the left: write to the right
    else:
        label_side, label_shift = "right", -10  # best month is on the right: write to the left
    ax.annotate(
        f"Best month: \\${best_value:,.0f}",
        xy=(best, best_value), xytext=(label_shift, 10), textcoords="offset points",
        ha=label_side, fontsize=10, color=TEXT,
    )

    ax.set_xticks(positions)
    ax.set_xticklabels(month_names)
    ax.set_xlim(-0.5, len(positions) - 0.5)
    ax.set_ylim(0, best_value * 1.2)
    ax.yaxis.set_major_formatter(FuncFormatter(money_in_thousands))
    ax.grid(axis="y", color=GRID, linewidth=1)
    ax.set_axisbelow(True)
    ax.set_title("Monthly revenue", loc="left", fontsize=13,
                 fontweight="bold", color=TEXT, pad=14)


def draw_category_chart(ax, categories):
    """Horizontal bar chart: total revenue per product category."""
    tidy_axes(ax)
    ax.barh(categories["product_category"], categories["revenue"],
            color=BLUE, height=0.6)
    ax.invert_yaxis()  # put the biggest category at the top

    biggest = categories["revenue"].max()
    for row_number, value in enumerate(categories["revenue"]):
        ax.text(value + biggest * 0.02, row_number, f"\\${value:,.0f}",
                va="center", fontsize=10, color=TEXT)

    ax.set_xlim(0, biggest * 1.25)
    ax.set_xticks([])  # the numbers are written on the bars, so no axis needed
    ax.tick_params(axis="y", labelsize=11, colors=TEXT)
    ax.set_title("Revenue by product category", loc="left", fontsize=13,
                 fontweight="bold", color=TEXT, pad=14)


# ----------------------------------------------------------------------
# Run everything
# ----------------------------------------------------------------------
def main():
    if not DB_FILE.exists():
        print("Could not find ecommerce.db.")
        print("Run this first:  python pipeline.py")
        return

    summary = run_query(SUMMARY_SQL)
    monthly = run_query(MONTHLY_SQL)
    categories = run_query(CATEGORY_SQL)

    print("Summary:")
    print(summary.to_string(index=False))
    print("\nRevenue by category:")
    print(categories.to_string(index=False))

    row = summary.iloc[0]
    headline = (
        f"{int(row['total_orders']):,} orders   |   "
        f"{int(row['unique_customers']):,} customers   |   "
        f"\\${row['total_revenue']:,.0f} total revenue   |   "
        f"\\${row['avg_order_value']:,.2f} average order"
    )

    fig = plt.figure(figsize=(13, 6), facecolor=SURFACE)
    grid = fig.add_gridspec(
        1, 2, width_ratios=[3, 2], wspace=0.28,
        left=0.06, right=0.97, top=0.74, bottom=0.10,
    )
    ax_line = fig.add_subplot(grid[0])
    ax_bar = fig.add_subplot(grid[1])

    fig.text(0.06, 0.93, "E-Commerce Sales Dashboard", fontsize=22,
             fontweight="bold", color=TEXT, ha="left")
    fig.text(0.06, 0.86, headline, fontsize=12, color=TEXT_SOFT, ha="left")

    draw_monthly_chart(ax_line, monthly)
    draw_category_chart(ax_bar, categories)

    fig.savefig(CHART_FILE, dpi=150, facecolor=fig.get_facecolor())
    print(f"\nSaved the chart as {CHART_FILE.name}")

    plt.show()  # opens a window; close it to finish the script


if __name__ == "__main__":
    main()
    