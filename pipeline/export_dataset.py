import pandas as pd
from db.connection import get_engine

# Plausibility bounds: outside these the value is a data-entry error, not a listing
# (USD 111 asking prices, "1 m²" placeholders, 44-"ambiente" hotels sold as apartments).
PRICE_USD = (20_000, 5_000_000)
COVERED_M2 = (15, 500)
AMBIENTES = (1, 8)

query = f"""
WITH latest AS (
    SELECT DISTINCT ON (listing_id) listing_id, price, currency, captured_at
    FROM listing_snapshots
    ORDER BY listing_id, captured_at DESC
)
SELECT
    l.source,
    l.neighborhood,
    s.price,
    l.covered_m2,
    l.ambientes,
    l.bedrooms,
    l.url,
    s.captured_at
FROM latest s
JOIN listings l ON l.id = s.listing_id
WHERE l.operation = 'sale'
  AND l.property_type = 'apartment'
  AND s.currency = 'USD'
  AND s.price      BETWEEN {PRICE_USD[0]} AND {PRICE_USD[1]}
  AND l.covered_m2 BETWEEN {COVERED_M2[0]} AND {COVERED_M2[1]}
  AND l.ambientes  BETWEEN {AMBIENTES[0]} AND {AMBIENTES[1]}
  AND l.neighborhood IS NOT NULL
ORDER BY l.neighborhood, l.source, l.id
"""

def main():
    engine = get_engine()
    df = pd.read_sql(query, engine)
    df["price_per_m2"] = (df["price"] / df["covered_m2"]).round(0).astype(int)
    df.to_csv("data/listings.csv", index=False)
    print(f"Wrote {len(df)} rows to data/listings.csv")
    print(df["source"].value_counts().to_string())
    print(f"{df['neighborhood'].nunique()} barrios")

if __name__ == "__main__":
    main()
