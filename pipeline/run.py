"""Argenprop scraper: apartments for sale in CABA, one search per barrio.

    python pipeline/run.py                        # every barrio in BARRIOS
    python pipeline/run.py villa-real belgrano    # only these
    python pipeline/run.py --from villa-lugano    # resume from that barrio
    python pipeline/run.py coghlan --max-pages 2 --dry-run   # smoke test, nothing stored

The global search (/departamentos/venta/capital-federal) dies at ~2.000 listings
once the AWS WAF kicks in; per-barrio searches are small enough to finish and
paginate without limit. Each barrio is stored as soon as it finishes, so a block
half-way through loses nothing; ON CONFLICT (source, source_id) dedupes.
"""
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from sqlalchemy import text

from db.connection import get_engine
from pipeline.store import store
from scrapers.parse_argenprop import parse_listings

SOURCE = "argenprop"

# clean base URL (no ?pagina, no sort); the loop adds page numbers
SEARCH_URL = "https://www.argenprop.com/departamentos/venta/{barrio}"

# slugs as they appear in Argenprop's "Barrio" filter for Capital Federal (54),
# taken from the data-filter-value attributes of the search sidebar. Argenprop
# folds sub-barrios (Palermo Soho, Las Cañitas...) into their parent search.
# Comment out or reorder freely; the DB dedupes.
BARRIOS = [
    "abasto", "agronomia", "almagro", "balvanera", "barracas",
    "barrio-norte", "barrio-santa-rita", "belgrano", "boca", "boedo",
    "caballito", "centro", "chacarita", "coghlan", "colegiales",
    "congreso", "constitucion", "flores", "floresta", "liniers",
    "mataderos", "monserrat", "monte-castro", "nunez", "once",
    "palermo", "parque-avellaneda", "parque-centenario", "parque-chacabuco", "parque-chas",
    "parque-patricios", "paternal", "pompeya", "puerto-madero", "recoleta",
    "retiro", "saavedra", "san-cristobal", "san-nicolas", "san-telmo",
    "velez-sarsfield", "versalles", "villa-crespo", "villa-del-parque", "villa-devoto",
    "villa-general-mitre", "villa-lugano", "villa-luro", "villa-ortuzar", "villa-pueyrredon",
    "villa-real", "villa-riachuelo", "villa-soldati", "villa-urquiza",
]

MAX_PAGES = 600                 # Palermo alone has ~534 pages of 20
DELAY_RANGE = (3.0, 5.0)        # seconds between pages
RETRY_BACKOFF = [30, 60, 120, 240, 480]   # seconds, +jitter, one per retry

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


class BlockedError(Exception):
    """Fetch failed after every retry; the WAF is most likely blocking us."""


class WafChallenge(Exception):
    """AWS WAF answered instead of the site: HTTP 202 with a JS challenge page."""


def fetch(client, url):
    resp = client.get(url)
    resp.raise_for_status()
    # the WAF challenge is a 202 with a tiny page; raise_for_status() lets it through
    # and the parser would return [] as if the search had simply ended
    if resp.status_code == 202 or "awsWafCookieDomainList" in resp.text:
        raise WafChallenge(f"status {resp.status_code}, {len(resp.text)} bytes")
    return resp.text


def page_url(base, page):
    return base if page == 1 else f"{base}?pagina-{page}"


def sleep_between_pages():
    time.sleep(random.uniform(*DELAY_RANGE))


def fetch_page(client, url):
    """GET + parse with exponential backoff. Raises BlockedError when retries run out."""
    for attempt, backoff in enumerate([0] + RETRY_BACKOFF):
        if backoff:
            wait = backoff + random.uniform(0, backoff / 4)
            print(f"retry {attempt}/{len(RETRY_BACKOFF)} in {wait:.0f}s...", end=" ", flush=True)
            time.sleep(wait)
        try:
            return parse_listings(fetch(client, url))
        except (httpx.HTTPError, WafChallenge) as e:
            print(f"({type(e).__name__}: {str(e)[:60]})", end=" ", flush=True)
    raise BlockedError(url)


def collect_listings(client, base_url, max_pages):
    """Returns (listings, blocked). On a block, listings holds the pages fetched so far."""
    all_items = []
    seen_ids = set()
    for page in range(1, max_pages + 1):
        print(f"    page {page}...", end=" ", flush=True)
        try:
            items = fetch_page(client, page_url(base_url, page))
        except BlockedError:
            print(f"BLOCKED: retries exhausted, keeping {len(all_items)} listings from earlier pages.")
            return all_items, True
        if not items:
            print("no listings, stopping.")
            break

        new_here = 0
        for item in items:
            sid = item["source_id"]
            if sid and sid not in seen_ids:
                seen_ids.add(sid)
                all_items.append(item)
                new_here += 1
        print(f"{len(items)} on the page, {new_here} new")
        if new_here == 0:
            print("    no new listings, stopping.")
            break
        sleep_between_pages()

    return all_items, False


def coverage(listings):
    """Share of listings with each key field filled, for a quick quality read."""
    n = len(listings) or 1
    fields = ["price", "currency", "raw_neighborhood", "covered_m2", "ambientes", "bedrooms", "bathrooms", "expensas"]
    return "  ".join(f"{f}={sum(1 for x in listings if x[f] is not None) / n:.0%}" for f in fields)


def show_rows(listings, n=5):
    for item in listings[:n]:
        print("    " + "  ".join(f"{k}={v}" for k, v in item.items() if k not in ("source", "url")))


def parse_args(argv):
    barrios, start_from, max_pages, dry_run = [], None, MAX_PAGES, False
    it = iter(argv)
    for a in it:
        if a == "--from":
            start_from = next(it)
        elif a == "--max-pages":
            max_pages = int(next(it))
        elif a == "--dry-run":
            dry_run = True
        else:
            barrios.append(a)
    if not barrios:
        barrios = list(BARRIOS)
    if start_from:
        if start_from not in barrios:
            sys.exit(f"--from {start_from}: not in the barrio list")
        barrios = barrios[barrios.index(start_from):]
    unknown = [b for b in barrios if b not in BARRIOS]
    if unknown:
        print(f"warning: not in BARRIOS (running anyway): {unknown}")
    return barrios, max_pages, dry_run


def check_db():
    """Fail before spending any request on the site if the DB is unreachable."""
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        sys.exit(f"Database check failed, fix DATABASE_URL in .env (or use --dry-run):\n  {str(e).splitlines()[0]}")


def main():
    barrios, max_pages, dry_run = parse_args(sys.argv[1:])
    if not dry_run:
        check_db()
    print(f"{len(barrios)} barrios, max {max_pages} pages each, delay {DELAY_RANGE[0]}-{DELAY_RANGE[1]}s"
          f"{', DRY RUN (nothing stored)' if dry_run else ''}\n")

    summary = []
    with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=30) as client:
        for i, barrio in enumerate(barrios):
            url = SEARCH_URL.format(barrio=barrio)
            print(f"[{i + 1}/{len(barrios)}] {barrio}: {url}")
            listings, blocked = collect_listings(client, url, max_pages)

            if listings and dry_run:
                print(f"  {len(listings)} listings (not stored)  |  {coverage(listings)}")
                show_rows(listings)
                print()
                summary.append((barrio, len(listings), 0))
            elif listings:
                run_id, seen, new = store(listings, SOURCE, notes=f"barrio={barrio}")
                print(f"  stored run {run_id}: {seen} seen, {new} new  |  {coverage(listings)}\n")
                summary.append((barrio, seen, new))
            else:
                print("  nothing to store\n")
                summary.append((barrio, 0, 0))

            if blocked:
                print(f"Resume later with:  python pipeline/run.py --from {barrio}")
                break
            sleep_between_pages()

    print("\nSummary (barrio, seen, new):")
    for row in summary:
        print(f"  {row[0]:22} {row[1]:5} {row[2]:5}")

    if dry_run:
        return
    with get_engine().connect() as conn:
        n_src = conn.execute(text("SELECT count(*) FROM listings WHERE source = :s"), {"s": SOURCE}).scalar()
        n_all = conn.execute(text("SELECT count(*) FROM listings")).scalar()
        n_snaps = conn.execute(text("SELECT count(*) FROM listing_snapshots")).scalar()
    print(f"\nDatabase now has {n_src} {SOURCE} listings ({n_all} total) and {n_snaps} snapshots.")


if __name__ == "__main__":
    main()
