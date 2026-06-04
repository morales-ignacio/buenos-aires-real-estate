import re
from pathlib import Path
from bs4 import BeautifulSoup

BASE = "https://www.argenprop.com"


def first_int(text):
    """Pull the first number out of text like 'USD 2.400.000' -> 2400000."""
    if not text:
        return None
    m = re.search(r"[\d.]+", text)
    if not m:
        return None
    digits = m.group(0).replace(".", "")
    return int(digits) if digits.isdigit() else None


def parse_listings(html):
    soup = BeautifulSoup(html, "html.parser")
    results = []

    for card in soup.select("a.card"):
        href = card.get("href", "")
        if not href:
            continue

        id_match = re.search(r"(\d+)\s*$", href)
        source_id = id_match.group(1) if id_match else None

        operation = "sale" if "-venta" in href else "rent" if "-alquiler" in href else None
        if "departamento" in href:
            property_type = "apartment"
        elif "casa" in href:
            property_type = "house"
        elif "/ph" in href or "-ph-" in href:
            property_type = "ph"
        else:
            property_type = None

        # title: "Departamento en Venta en Palermo Chico, Palermo"
        title_el = card.select_one("p.card__title--primary")
        title = title_el.get_text(" ", strip=True) if title_el else ""
        parts = [p.strip() for p in title.split(" en ")]
        neighborhood = parts[-1] if len(parts) >= 3 else None

        addr_el = card.select_one("p.card__address")
        address = addr_el.get_text(" ", strip=True) if addr_el else None

        # price, currency, expensas
        price = currency = expensas = None
        price_el = card.select_one("p.card__price")
        if price_el:
            cur_el = price_el.find("span", class_="card__currency")
            raw_currency = cur_el.get_text(strip=True) if cur_el else ""
            currency = "USD" if "usd" in raw_currency.lower() else ("ARS" if "$" in raw_currency else None)

            exp_el = price_el.find("span", class_="card__expenses")
            exp_text = exp_el.get_text(" ", strip=True) if exp_el else ""
            if exp_el:
                expensas = first_int(exp_text)

            full = price_el.get_text(" ", strip=True)
            price_part = full.replace(exp_text, "") if exp_text else full
            price = first_int(price_part)

        # features (size, rooms) identified by icon class
        covered_m2 = bedrooms = ambientes = bathrooms = None
        feats = card.select_one("ul.card__main-features")
        if feats:
            for li in feats.find_all("li"):
                icon = li.find("i")
                cls = " ".join(icon.get("class", [])) if icon else ""
                val = first_int(li.get_text(" ", strip=True))
                if "superficie_cubierta" in cls:
                    covered_m2 = val
                elif "cantidad_dormitorios" in cls:
                    bedrooms = val
                elif "ambiente" in cls:
                    ambientes = val
                elif "bano" in cls:
                    bathrooms = val

        # ambientes is often in the URL even when not in the feature icons
        amb_match = re.search(r"(\d+)-ambiente", href)
        if amb_match and ambientes is None:
            ambientes = int(amb_match.group(1))

        results.append({
            "source": "argenprop",
            "source_id": source_id,
            "url": BASE + href if href.startswith("/") else href,
            "operation": operation,
            "property_type": property_type,
            "raw_neighborhood": neighborhood,
            "address": address,
            "price": price,
            "currency": currency,
            "expensas": expensas,
            "covered_m2": covered_m2,
            "ambientes": ambientes,
            "bedrooms": bedrooms,
            "bathrooms": bathrooms,
        })

    return results


if __name__ == "__main__":
    html = Path("samples/argenprop.html").read_text(encoding="utf-8")
    listings = parse_listings(html)
    print(f"Parsed {len(listings)} listings\n")
    for item in listings[:3]:
        for k, v in item.items():
            print(f"  {k}: {v}")
        print()