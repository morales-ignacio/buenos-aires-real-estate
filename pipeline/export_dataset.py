import pandas as pd
from db.connection import get_engine

query = """
WITH latest AS (
    SELECT DISTINCT ON (listing_id) listing_id, price, currency, captured_at
    FROM listing_snapshots
    ORDER BY listing_id, captured_at DESC
)
SELECT
    l.neighborhood,
    s.price,
    l.covered_m2,
    l.ambientes,
    l.bedrooms,
    l.url,
    s.captured_at
FROM latest s
JOIN listings l ON l.id = s.listing_id
WHERE s.currency = 'USD'
  AND l.covered_m2 > 0
  AND s.price IS NOT NULL
  AND l.neighborhood IS NOT NULL
ORDER BY l.neighborhood
"""

def main():
    engine = get_engine()
    df = pd.read_sql(query, engine)
    df["price_per_m2"] = (df["price"] / df["covered_m2"]).round(0).astype(int)
    df.to_csv("data/listings.csv", index=False)
    print(f"Wrote {len(df)} rows to data/listings.csv")

if __name__ == "__main__":
    main()