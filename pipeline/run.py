import sys
from pathlib import Path

# make the project root importable so db/ and scrapers/ can be used
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from sqlalchemy import text

from db.connection import get_engine
from scrapers.parse_argenprop import parse_listings

SEARCH_URL = "https://www.argenprop.com/departamentos/venta/capital-federal"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def fetch(url):
    resp = httpx.get(url, headers=HEADERS, follow_redirects=True, timeout=30)
    resp.raise_for_status()
    return resp.text


def store(listings):
    engine = get_engine()
    new_listings = 0
    with engine.begin() as conn:
        run_id = conn.execute(text(
            "INSERT INTO scrape_runs (source, status) "
            "VALUES ('argenprop', 'running') RETURNING id"
        )).scalar()

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


if __name__ == "__main__":
    print("Fetching...")
    html = fetch(SEARCH_URL)
    listings = parse_listings(html)
    print(f"Parsed {len(listings)} listings, storing...")
    run_id, seen, new = store(listings)
    print(f"Run {run_id}: {seen} seen, {new} new.")

    engine = get_engine()
    with engine.connect() as conn:
        n_listings = conn.execute(text("SELECT count(*) FROM listings")).scalar()
        n_snaps = conn.execute(text("SELECT count(*) FROM listing_snapshots")).scalar()
    print(f"Database now has {n_listings} listings and {n_snaps} snapshots.")