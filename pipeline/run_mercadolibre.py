"""Mercado Libre Inmuebles scraper: apartments for sale in CABA, one search per barrio.

    python pipeline/run_mercadolibre.py                       # every barrio in BARRIOS
    python pipeline/run_mercadolibre.py puerto-madero palermo # only these
    python pipeline/run_mercadolibre.py --from villa-lugano   # resume from that barrio
    python pipeline/run_mercadolibre.py agronomia --max-pages 2   # smoke test
    python pipeline/run_mercadolibre.py agronomia --dry-run --sample samples/mercadolibre.html
                                            # parse and print, store nothing, keep page 1's HTML

Each barrio is stored as soon as it finishes, so a block half-way through loses
nothing already collected; ON CONFLICT (source, source_id) dedupes across runs.
"""
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from db.connection import get_engine
from pipeline.store import store
from scrapers.parse_mercadolibre import parse_page

SOURCE = "mercadolibre"

# "propiedades-individuales" excludes developments (EMPRENDIMIENTO cards); the
# parser drops them too, this just avoids paying ~40 pages of them per barrio.
SEARCH_URL = (
    "https://inmuebles.mercadolibre.com.ar/departamentos/venta/"
    "propiedades-individuales/{ambientes}capital-federal/{barrio}/"
)

# ML caps every search at 2.000 results (pagination.results_limit). Barrios
# above that are split into three searches by ambientes. Barrios known to be
# big skip the probe; any other barrio whose plain search hits the cap on page 1
# is abandoned and re-run split (costs one request).
AMBIENTES_SEGMENTS = ["1-ambiente/", "2-ambientes/", "mas-de-3-ambientes/"]
SPLIT_BY_AMBIENTES = {
    "almagro", "balvanera", "belgrano", "caballito", "nunez",
    "palermo", "puerto-madero", "recoleta", "villa-crespo", "villa-urquiza",
}

# slugs as they appear in ML's "Barrios" filter for Capital Federal (63).
# ML lists sub-barrios (palermo-soho, belgrano-r, las-canitas...) separately.
# Comment out or reorder freely; the DB dedupes.
BARRIOS = [
    "agronomia", "almagro", "balvanera", "barracas", "barrio-norte",
    "belgrano", "belgrano-barrancas", "belgrano-c", "belgrano-chico", "belgrano-r",
    "boedo", "botanico", "caballito", "chacarita", "coghlan",
    "colegiales", "congreso", "constitucion", "flores", "floresta",
    "la-boca", "las-canitas", "liniers", "mataderos", "monserrat",
    "monte-castro", "nueva-pompeya", "nunez", "once", "palermo",
    "palermo-chico", "palermo-hollywood", "palermo-nuevo", "palermo-soho", "palermo-viejo",
    "parque-avellaneda", "parque-centenario", "parque-chacabuco", "parque-chas", "parque-patricios",
    "paternal", "puerto-madero", "recoleta", "retiro", "saavedra",
    "san-cristobal", "san-nicolas", "san-telmo", "santa-rita", "velez-sarsfield",
    "versalles", "villa-crespo", "villa-del-parque", "villa-devoto", "villa-gral-mitre",
    "villa-lugano", "villa-luro", "villa-ortuzar", "villa-pueyrredon", "villa-real",
    "villa-riachuelo", "villa-soldati", "villa-urquiza",
]

MAX_PAGES = 45                  # ML never serves more than 42 (2.000 / 48)
DELAY_RANGE = (3.0, 5.0)        # seconds between pages
RETRY_BACKOFF = [30, 60, 120, 240, 480]   # seconds, +jitter, one per retry

# ML randomly answers a filtered search URL with a 301 to the same barrio WITHOUT
# the filters (".../propiedades-individuales/capital-federal/almagro/" ->
# "/capital-federal/almagro/": all operations and property types). Following it
# silently poisons the data, so redirects are never followed: a 3xx is retried
# on the same URL, quickly, until ML serves the page we asked for.
REDIRECT_RETRIES = 10
REDIRECT_DELAY = (2.0, 5.0)

# full Chrome header set (Sec-Fetch-*, sec-ch-ua): ML doesn't need it, but some
# portals fingerprint these headers and refuse requests without them
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "Upgrade-Insecure-Requests": "1",
}


class BlockedError(Exception):
    """Fetch failed after every retry; the site is most likely rate-limiting us."""


class RedirectedError(Exception):
    """ML kept answering with a redirect to a different (unfiltered) search."""


def sleep_between_pages():
    time.sleep(random.uniform(*DELAY_RANGE))


SAMPLE_PATH = None   # set by --sample; the first page fetched is written there


def get_exact(client, url):
    """GET url and return the response only if it is the page we asked for (no redirect)."""
    for attempt in range(REDIRECT_RETRIES + 1):
        resp = client.get(url)
        if not resp.is_redirect:
            if attempt:
                print(f"(ok after {attempt} redirect{'s' if attempt > 1 else ''})", end=" ", flush=True)
            return resp
        if attempt == 0:
            print("(301, retrying same url)", end=" ", flush=True)
        time.sleep(random.uniform(*REDIRECT_DELAY))
    raise RedirectedError(f"{REDIRECT_RETRIES} redirects in a row to {resp.headers.get('location', '?')[:80]}")


def fetch_page(client, url):
    """GET + parse with exponential backoff. Raises BlockedError when retries run out."""
    global SAMPLE_PATH
    for attempt, backoff in enumerate([0] + RETRY_BACKOFF):
        if backoff:
            wait = backoff + random.uniform(0, backoff / 4)
            print(f"retry {attempt}/{len(RETRY_BACKOFF)} in {wait:.0f}s...", end=" ", flush=True)
            time.sleep(wait)
        try:
            resp = get_exact(client, url)
            resp.raise_for_status()
            listings, pagination, skipped = parse_page(resp.text)
            if pagination["page"] is None:
                # 200 but no embedded state: challenge/interstitial page
                raise ValueError(f"no embedded search state (status {resp.status_code}, {len(resp.text)} bytes)")
            if SAMPLE_PATH:
                Path(SAMPLE_PATH).write_text(resp.text, encoding="utf-8")
                print(f"(saved {SAMPLE_PATH})", end=" ", flush=True)
                SAMPLE_PATH = None
            return listings, pagination, skipped, str(resp.url)
        except (httpx.HTTPError, ValueError, RedirectedError) as e:
            print(f"({type(e).__name__}: {str(e)[:80]})", end=" ", flush=True)
    raise BlockedError(url)


def collect_search(client, first_url, max_pages, abort_if_capped=False):
    """Follow next_page links from first_url. Returns (listings, hit_cap).
    With abort_if_capped, a search at the 2.000 cap returns ([], True) after page 1
    so the caller can re-run it split by ambientes instead."""
    all_items, seen_ids = [], set()
    url, page, hit_cap = first_url, 1, False
    last_page = max_pages
    while url and page <= last_page:
        print(f"    page {page}...", end=" ", flush=True)
        listings, pagination, skipped, final_url = fetch_page(client, url)

        # past its last page ML redirects to a free-text search with its own
        # 42-page pagination (".../1-ambiente-capital-federal-almagro_Desde_...")
        # that ignores our filters, so never trust next_page beyond page_count,
        # and stop if the response didn't come from the search we asked for
        if not final_url.startswith(first_url):
            print(f"redirected to {final_url[:90]}, stopping.")
            break
        if page == 1:
            hit_cap = (pagination["results_limit"] or 0) >= 2000
            last_page = min(max_pages, pagination["page_count"] or max_pages)
            print(f"[{pagination['page_count']} pages, {pagination['results_limit']} results"
                  f"{' - AT 2.000 CAP' if hit_cap else ''}]", end=" ")
            if hit_cap and abort_if_capped:
                print("-> splitting by ambientes instead")
                return [], True

        new_here = 0
        for item in listings:
            if item["source_id"] not in seen_ids:
                seen_ids.add(item["source_id"])
                all_items.append(item)
                new_here += 1
        print(f"{len(listings)} listings, {new_here} new, {skipped} developments skipped")

        if not listings or new_here == 0:
            break
        url = pagination["next_url"]
        page += 1
        if url:
            sleep_between_pages()
    return all_items, hit_cap


def split_searches(barrio):
    return [(seg.rstrip("/"), SEARCH_URL.format(ambientes=seg, barrio=barrio)) for seg in AMBIENTES_SEGMENTS]


def searches_for(barrio):
    if barrio in SPLIT_BY_AMBIENTES:
        return split_searches(barrio)
    return [("all", SEARCH_URL.format(ambientes="", barrio=barrio))]


def store_with_retry(listings, notes, attempts=3):
    """store() is one transaction per barrio, so a dropped DB connection (Neon
    closes idle/long ones now and then) rolls back cleanly and can be retried."""
    for attempt in range(1, attempts + 1):
        try:
            return store(listings, SOURCE, notes=notes)
        except OperationalError as e:
            print(f"  store failed ({str(e).splitlines()[0][:70]}), attempt {attempt}/{attempts}", flush=True)
            get_engine().dispose()
            if attempt == attempts:
                raise
            time.sleep(10 * attempt)


def coverage(listings):
    """Share of listings with each key field filled, for a quick quality read."""
    n = len(listings) or 1
    fields = ["price", "currency", "raw_neighborhood", "covered_m2", "ambientes", "bedrooms", "bathrooms"]
    return "  ".join(f"{f}={sum(1 for x in listings if x[f] is not None) / n:.0%}" for f in fields)


def parse_args(argv):
    global SAMPLE_PATH
    barrios, start_from, max_pages, dry_run = [], None, MAX_PAGES, False
    it = iter(argv)
    for a in it:
        if a == "--from":
            start_from = next(it)
        elif a == "--max-pages":
            max_pages = int(next(it))
        elif a == "--dry-run":
            dry_run = True
        elif a == "--sample":
            SAMPLE_PATH = next(it)
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


def show_rows(listings, n=5):
    for item in listings[:n]:
        print("    " + "  ".join(f"{k}={v}" for k, v in item.items() if k not in ("source", "url")))


def main():
    barrios, max_pages, dry_run = parse_args(sys.argv[1:])
    if not dry_run:
        check_db()
    print(f"{len(barrios)} barrios, max {max_pages} pages per search, delay {DELAY_RANGE[0]}-{DELAY_RANGE[1]}s"
          f"{', DRY RUN (nothing stored)' if dry_run else ''}\n")

    summary = []
    with httpx.Client(headers=HEADERS, follow_redirects=False, timeout=30) as client:
        for i, barrio in enumerate(barrios):
            print(f"[{i + 1}/{len(barrios)}] {barrio}")
            barrio_items, seen_ids, blocked = [], set(), False
            searches = searches_for(barrio)
            while searches:
                label, url = searches.pop(0)
                print(f"  {label}: {url}")
                try:
                    items, hit_cap = collect_search(client, url, max_pages, abort_if_capped=(label == "all"))
                except BlockedError:
                    print("  BLOCKED: retries exhausted, storing what we have and stopping.")
                    blocked = True
                    items, hit_cap = [], False
                for item in items:
                    if item["source_id"] not in seen_ids:
                        seen_ids.add(item["source_id"])
                        barrio_items.append(item)
                if hit_cap and label == "all":
                    searches = split_searches(barrio)
                elif hit_cap:
                    print(f"  note: '{label}' hit the 2.000 cap, some listings are unreachable in this segment")
                if blocked:
                    break
                sleep_between_pages()

            if barrio_items and dry_run:
                print(f"  {len(barrio_items)} listings (not stored)  |  {coverage(barrio_items)}")
                show_rows(barrio_items)
                print()
                summary.append((barrio, len(barrio_items), 0))
            elif barrio_items:
                run_id, seen, new = store_with_retry(barrio_items, notes=f"barrio={barrio}")
                print(f"  stored run {run_id}: {seen} seen, {new} new  |  {coverage(barrio_items)}\n")
                summary.append((barrio, seen, new))
            else:
                print("  nothing to store\n")
                summary.append((barrio, 0, 0))

            if blocked:
                nxt = barrios[i] if not barrio_items else (barrios[i + 1] if i + 1 < len(barrios) else None)
                if nxt:
                    print(f"Resume later with:  python pipeline/run_mercadolibre.py --from {nxt}")
                break

    print("\nSummary (barrio, seen, new):")
    for row in summary:
        print(f"  {row[0]:22} {row[1]:5} {row[2]:5}")

    if dry_run:
        return
    with get_engine().connect() as conn:
        n_ml = conn.execute(text("SELECT count(*) FROM listings WHERE source = :s"), {"s": SOURCE}).scalar()
        n_all = conn.execute(text("SELECT count(*) FROM listings")).scalar()
        n_snaps = conn.execute(text("SELECT count(*) FROM listing_snapshots")).scalar()
    print(f"\nDatabase now has {n_ml} {SOURCE} listings ({n_all} total) and {n_snaps} snapshots.")


if __name__ == "__main__":
    main()
