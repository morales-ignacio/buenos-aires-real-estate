"""Shared DB write for any source. Same statements as pipeline/run.py's store(),
with the source and a free-text note parameterised so other scrapers can reuse it
without touching the Argenprop pipeline."""

from sqlalchemy import text

from db.connection import get_engine


def store(listings, source, notes=None):
    engine = get_engine()
    new_listings = 0
    with engine.begin() as conn:
        run_id = conn.execute(text(
            "INSERT INTO scrape_runs (source, status, notes) "
            "VALUES (:source, 'running', :notes) RETURNING id"
        ), {"source": source, "notes": notes}).scalar()

        for item in listings:
            if not item["source_id"]:
                continue

            result = conn.execute(text("""
                INSERT INTO listings
                    (source, source_id, url, operation, property_type,
                     raw_neighborhood, covered_m2, ambientes, bedrooms, bathrooms)
                VALUES
                    (:source, :source_id, :url, :operation, :property_type,
                     :raw_neighborhood, :covered_m2, :ambientes, :bedrooms, :bathrooms)
                ON CONFLICT (source, source_id) DO UPDATE SET
                    last_seen_at = now(), is_active = TRUE
                RETURNING id, (xmax = 0) AS inserted
            """), {
                "source": item["source"],
                "source_id": item["source_id"],
                "url": item["url"],
                "operation": item["operation"],
                "property_type": item["property_type"],
                "raw_neighborhood": item["raw_neighborhood"],
                "covered_m2": item["covered_m2"],
                "ambientes": item["ambientes"],
                "bedrooms": item["bedrooms"],
                "bathrooms": item["bathrooms"],
            }).one()

            if result.inserted:
                new_listings += 1

            conn.execute(text("""
                INSERT INTO listing_snapshots
                    (listing_id, run_id, price, currency, expensas, expensas_currency)
                VALUES
                    (:listing_id, :run_id, :price, :currency, :expensas, :expensas_currency)
            """), {
                "listing_id": result.id,
                "run_id": run_id,
                "price": item["price"],
                "currency": item["currency"],
                "expensas": item["expensas"],
                "expensas_currency": "ARS" if item["expensas"] is not None else None,
            })

        conn.execute(text("""
            UPDATE scrape_runs
            SET finished_at = now(), status = 'success',
                listings_seen = :seen, listings_new = :new
            WHERE id = :run_id
        """), {"seen": len(listings), "new": new_listings, "run_id": run_id})

    return run_id, len(listings), new_listings
