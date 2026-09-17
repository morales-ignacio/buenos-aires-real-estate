import json
import re
from pathlib import Path

# ML search pages embed the full result set as JSON inside
# <script id="__NORDIC_RENDERING_CTX__">_n.ctx.r={...};...</script>
# so we read that instead of the rendered HTML cards.
CTX_SCRIPT = re.compile(
    r'<script id="__NORDIC_RENDERING_CTX__"[^>]*>\s*_n\.ctx\.r\s*=', re.S
)

# attribute texts look like "2 ambientes", "1 baño", "45 m² cubiertos", "1 dormitorio"
RANGE = re.compile(r"\d+\s*(?:-|a)\s*\d")   # "1 a 2 ambs.", "28 - 46 m²" -> projects, ambiguous


def first_int(text):
    """'2 ambientes' -> 2, '1.200' -> 1200. None for ranges like '1 a 2'."""
    if not text or RANGE.search(text):
        return None
    m = re.search(r"\d[\d.]*", text)
    if not m:
        return None
    digits = m.group(0).replace(".", "")
    return int(digits) if digits.isdigit() else None


def extract_state(html):
    """Return initialState (dict) from the embedded rendering context, or None."""
    m = CTX_SCRIPT.search(html)
    if not m:
        return None
    obj, _ = json.JSONDecoder().raw_decode(html[m.end():].lstrip())
    return obj.get("appProps", {}).get("pageProps", {}).get("initialState")


def parse_pagination(state):
    pag = (state or {}).get("pagination") or {}
    nxt = pag.get("next_page") or {}
    return {
        "page": pag.get("selected_page"),
        "page_count": pag.get("page_count"),
        "results_limit": pag.get("results_limit"),
        "next_url": nxt.get("url") if nxt.get("show") else None,
    }


def parse_card(polycard):
    md = polycard.get("metadata", {})
    comps = {c.get("id"): c for c in polycard.get("components", [])}

    # developments ("EMPRENDIMIENTO" pill, "Desde" price, attribute ranges) are
    # buildings with many units, not one listing -> not comparable, skip
    pill = (comps.get("project") or {}).get("pill", {}).get("text", "")
    price_comp = (comps.get("price") or {}).get("price", {})
    prefix = (price_comp.get("prefix") or {}).get("text", "")
    domain = md.get("domain_id", "") or ""
    is_project = "EMPRENDIMIENTO" in pill.upper() or prefix == "Desde" or "DEVELOPMENT" in domain
    if is_project:
        return None

    source_id = md.get("id")
    url = md.get("url", "")
    if url and not url.startswith("http"):
        url = "https://" + url

    headline = (comps.get("headline") or {}).get("headline", {}).get("text", "").lower()
    if "FOR_SALE" in domain or "venta" in headline:
        operation = "sale"
    elif "FOR_RENT" in domain or "alquiler" in headline:
        operation = "rent"
    else:
        operation = None

    if "APARTMENT" in domain or "departamento" in headline:
        property_type = "apartment"
    elif "HOUSE" in domain or "casa" in headline:
        property_type = "house"
    elif "_PH_" in domain or " ph " in f" {headline} ":
        property_type = "ph"
    else:
        property_type = None

    cur = price_comp.get("current_price") or {}
    price = cur.get("value")
    price = int(price) if isinstance(price, (int, float)) else None
    currency = cur.get("currency")
    if currency not in ("USD", "ARS"):
        currency = None

    # location: "CABELLO 3881, Palermo, Capital Federal" or "Palermo, Capital Federal".
    # raw_neighborhood keeps the last two parts ("Barrio, Capital Federal") so it
    # has the same shape as Argenprop's and normalize.clean_barrio() works unchanged.
    loc = (comps.get("location") or {}).get("location", {}).get("text", "") or ""
    parts = [p.strip() for p in loc.split(",") if p.strip()]
    neighborhood = ", ".join(parts[-2:]) if len(parts) >= 2 else (parts[0] if parts else None)
    address = parts[0] if len(parts) >= 3 else None

    covered_m2 = total_m2 = ambientes = bedrooms = bathrooms = None
    texts = (comps.get("attributes_list") or {}).get("attributes_list", {}).get("texts", [])
    for t in texts:
        low = t.lower()
        if "m²" in low or "m2" in low:
            if "total" in low:
                total_m2 = first_int(t)
            else:
                covered_m2 = first_int(t)
        elif "monoambiente" in low:
            ambientes = 1
        elif "amb" in low:
            ambientes = first_int(t)
        elif "dorm" in low:
            bedrooms = first_int(t)
        elif "baño" in low:
            bathrooms = first_int(t)

    # like Argenprop, the URL slug often carries ambientes when the card doesn't.
    # 1-2 digits not preceded by another digit, so "MLA-3459193162-ambiente-nuevo"
    # (listing id + a title starting with "ambiente") doesn't match.
    if ambientes is None and url:
        if "monoambiente" in url:
            ambientes = 1
        else:
            m = re.search(r"(?<!\d)(\d{1,2})-ambientes?", url)
            if m:
                ambientes = int(m.group(1))

    # the DB columns are SMALLINT; anything this large is a parse error, not a value
    ambientes = ambientes if ambientes is not None and ambientes < 100 else None
    bedrooms = bedrooms if bedrooms is not None and bedrooms < 100 else None
    bathrooms = bathrooms if bathrooms is not None and bathrooms < 100 else None

    # expensas are not part of the search card in the samples seen so far; keep
    # the key so the dict matches Argenprop's, and pick it up if ML ever adds it
    expensas = None
    for c in polycard.get("components", []):
        blob = json.dumps(c, ensure_ascii=False)
        if "expensas" in blob.lower():
            m = re.search(r"\$\s*([\d.]+)", blob)
            expensas = first_int(m.group(1)) if m else None
            break

    return {
        "source": "mercadolibre",
        "source_id": source_id,
        "url": url,
        "operation": operation,
        "property_type": property_type,
        "raw_neighborhood": neighborhood,
        "address": address,
        "price": price,
        "currency": currency,
        "expensas": expensas,
        "covered_m2": covered_m2,
        "total_m2": total_m2,
        "ambientes": ambientes,
        "bedrooms": bedrooms,
        "bathrooms": bathrooms,
    }


def parse_page(html):
    """Return (listings, pagination, skipped_projects) for one search page."""
    state = extract_state(html)
    if state is None:
        return [], parse_pagination(None), 0

    listings, skipped = [], 0
    for r in state.get("results", []):
        pc = r.get("polycard")
        if not pc:
            continue   # GROUP_ITEMS_INTERVENTION and other non-listing blocks
        item = parse_card(pc)
        if item is None:
            skipped += 1
        elif item["source_id"]:
            listings.append(item)
    return listings, parse_pagination(state), skipped


def parse_listings(html):
    """Same contract as parse_argenprop.parse_listings."""
    return parse_page(html)[0]


if __name__ == "__main__":
    html = Path("samples/mercadolibre.html").read_text(encoding="utf-8")
    listings, pagination, skipped = parse_page(html)
    print(f"Parsed {len(listings)} listings, skipped {skipped} developments, pagination={pagination}\n")
    for item in listings[:3]:
        for k, v in item.items():
            print(f"  {k}: {v}")
        print()
