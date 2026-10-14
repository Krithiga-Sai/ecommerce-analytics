"""
pipeline.py
-----------
A small end-to-end data pipeline:
  1. Generate fake e-commerce order data (with deliberate mistakes in it)
  2. Save it as a "raw" CSV file, then read it back (this is our ingestion step)
  3. Clean the data
  4. Store the clean data in a SQLite database
  5. Check the database with a SQL query
"""

from pathlib import Path
import sqlite3

import numpy as np
import pandas as pd

# ----------------------------------------------------------------------
# Settings: where files live and how much data to make
# ----------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent   # the folder this script is in
DATA_DIR = BASE_DIR / "data"                 # a sub-folder called "data"
RAW_CSV = DATA_DIR / "raw_orders.csv"        # the messy file we will create
DB_FILE = BASE_DIR / "ecommerce.db"          # the database file we will create

NUM_ORDERS = 1000


# ----------------------------------------------------------------------
# Step 1: Generate fake business data
# ----------------------------------------------------------------------
def generate_raw_data(num_orders=NUM_ORDERS):
    """Create a table of fake orders with random but realistic values."""
    rng = np.random.default_rng(seed=42)  # seed=42 makes the "random" data the same every run

    countries = ["India", "USA", "UK", "Germany", "Australia"]
    country_probs = [0.35, 0.25, 0.15, 0.15, 0.10]

    base_prices = {
        "Electronics": 250.0,
        "Clothing": 40.0,
        "Home & Kitchen": 60.0,
        "Books": 15.0,
        "Sports": 80.0,
    }
    categories = list(base_prices.keys())
    category_probs = [0.20, 0.30, 0.20, 0.15, 0.15]

    customer_numbers = rng.integers(1, 301, size=num_orders)   # 300 possible customers
    order_offsets = rng.integers(0, 365, size=num_orders)      # days after 1 Jan 2025

    df = pd.DataFrame(
        {
            "order_id": [f"ORD-{i:05d}" for i in range(1, num_orders + 1)],
            "customer_id": [f"CUST-{n:04d}" for n in customer_numbers],
            "order_date": pd.Timestamp("2025-01-01")
            + pd.to_timedelta(order_offsets, unit="D"),
            "country": rng.choice(countries, size=num_orders, p=country_probs),
            "product_category": rng.choice(categories, size=num_orders, p=category_probs),
            "quantity": rng.integers(1, 6, size=num_orders).astype(float),
        }
    )

    price_noise = rng.uniform(0.8, 1.2, size=num_orders)
    df["unit_price"] = (
        df["product_category"].map(base_prices).to_numpy() * price_noise
    ).round(2)

    return df


def add_data_problems(df):
    """Deliberately break the data, the way real-world data is often broken."""
    rng = np.random.default_rng(seed=7)
    n = len(df)

    missing_country_rows = rng.choice(n, size=50, replace=False)
    missing_quantity_rows = rng.choice(n, size=30, replace=False)
    negative_price_rows = rng.choice(n, size=20, replace=False)
    negative_quantity_rows = rng.choice(n, size=15, replace=False)

    df.loc[missing_country_rows, "country"] = np.nan
    df.loc[missing_quantity_rows, "quantity"] = np.nan
    df.loc[negative_price_rows, "unit_price"] = -df.loc[negative_price_rows, "unit_price"]
    df.loc[negative_quantity_rows, "quantity"] = -df.loc[negative_quantity_rows, "quantity"]

    # Copy 25 random rows and add them again to create duplicate orders
    duplicates = df.sample(n=25, random_state=1)
    df = pd.concat([df, duplicates], ignore_index=True)

    return df


# ----------------------------------------------------------------------
# Step 2: Ingestion (read the raw file from disk)
# ----------------------------------------------------------------------
def ingest_raw_data():
    """Read the raw CSV file into a pandas table (called a DataFrame)."""
    return pd.read_csv(RAW_CSV)


# ----------------------------------------------------------------------
# Step 3: Cleaning
# ----------------------------------------------------------------------
def clean_data(df):
    """Fix duplicates, missing values, negative numbers and wrong data types."""
    df = df.copy()

    # 1. Remove rows that are exact copies of another row
    df = df.drop_duplicates()

    # 2. Dates arrive as plain text in a CSV, so convert them to real dates
    df["order_date"] = pd.to_datetime(df["order_date"])

    # 3. Missing country: we can't guess it, so label it "Unknown"
    df["country"] = df["country"].fillna("Unknown")

    # 4. Negative numbers: treat them as typing mistakes and flip the sign
    df["quantity"] = df["quantity"].abs()
    df["unit_price"] = df["unit_price"].abs()

    # 5. Missing quantity: fill with the median (the "middle" value), then
    #    convert to whole numbers because you can't buy 2.5 items
    median_quantity = df["quantity"].median()
    df["quantity"] = df["quantity"].fillna(median_quantity).astype(int)

    # 6. Create a new column: revenue = quantity x price
    df["revenue"] = (df["quantity"] * df["unit_price"]).round(2)

    # 7. Sort by date and tidy up the row numbers
    df = df.sort_values("order_date").reset_index(drop=True)

    return df


# ----------------------------------------------------------------------
# Step 4: Store in a SQL database
# ----------------------------------------------------------------------
def load_to_database(df):
    """Save the clean table into a SQLite database file."""
    df_to_save = df.copy()
    # SQLite has no special date type, so store dates as text like 2025-03-14
    df_to_save["order_date"] = df_to_save["order_date"].dt.strftime("%Y-%m-%d")

    conn = sqlite3.connect(DB_FILE)
    df_to_save.to_sql("orders", conn, if_exists="replace", index=False)
    conn.commit()
    conn.close()


# ----------------------------------------------------------------------
# Step 5: Check the database using SQL
# ----------------------------------------------------------------------
def verify_database():
    """Run a simple SQL query to prove the data is really in the database."""
    query = """
        SELECT
            COUNT(*)                     AS total_orders,
            COUNT(DISTINCT customer_id)  AS unique_customers,
            ROUND(SUM(revenue), 2)       AS total_revenue
        FROM orders;
    """
    conn = sqlite3.connect(DB_FILE)
    result = pd.read_sql_query(query, conn)
    conn.close()
    print(result.to_string(index=False))


# ----------------------------------------------------------------------
# Run everything in order
# ----------------------------------------------------------------------
def main():
    DATA_DIR.mkdir(exist_ok=True)  # create the "data" folder if it doesn't exist

    print("STEP 1: Generating fake data...")
    raw_df = generate_raw_data()
    raw_df = add_data_problems(raw_df)
    raw_df.to_csv(RAW_CSV, index=False)
    print(f"  Saved {len(raw_df)} raw rows to {RAW_CSV.name}")

    print("\nSTEP 2: Reading the raw file (ingestion)...")
    df = ingest_raw_data()
    print(f"  Rows read: {len(df)}")
    print("  Problems found:")
    print(f"    Duplicate rows:       {df.duplicated().sum()}")
    print(f"    Missing country:      {df['country'].isna().sum()}")
    print(f"    Missing quantity:     {df['quantity'].isna().sum()}")
    print(f"    Negative quantity:    {(df['quantity'] < 0).sum()}")
    print(f"    Negative unit price:  {(df['unit_price'] < 0).sum()}")

    print("\nSTEP 3: Cleaning the data...")
    clean_df = clean_data(df)
    print(f"  Rows after cleaning: {len(clean_df)}")
    print("  Problems remaining:")
    print(f"    Missing values (all columns): {clean_df.isna().sum().sum()}")
    print(f"    Negative quantity:            {(clean_df['quantity'] < 0).sum()}")
    print(f"    Negative unit price:          {(clean_df['unit_price'] < 0).sum()}")

    print("\nSTEP 4: Saving to the SQLite database...")
    load_to_database(clean_df)
    print(f"  Created {DB_FILE.name}")

    print("\nSTEP 5: Checking the database with SQL...")
    verify_database()

    print("\nPipeline finished successfully!")


# This line means: "only run main() if this file is run directly"
if __name__ == "__main__":
    main()