# Data dictionary

`listings.csv` is a cleaned, single-snapshot dataset of apartment sale listings in the
City of Buenos Aires (CABA), scraped from Mercado Libre Inmuebles and Argenprop on
16–17 September 2026. Each row is one listing, taken from its most recent scrape. The
file holds 59,069 listings across all 48 barrios (58,999 from Mercado Libre, 70 from
Argenprop).

**Scope:** apartments for sale (`operation = sale`, `property_type = apartment`, as
classified by the source), priced in USD, with a recognized barrio, and within
plausibility bounds: price USD 20,000–5,000,000, covered area 15–500 m², 1–8 ambientes.
Rows outside these bounds were data-entry errors (USD 111 asking prices, "1 m²"
placeholders, 44-"ambiente" hotels listed as apartments) or lacked the field; together
they were 5.2% of the 62,318 listings scraped. Rentals, offices, PHs and houses that
the sources mixed into apartment searches are excluded.

## Columns

| Column        | Type      | Description |
|---------------|-----------|-------------|
| source        | text      | Portal the listing was scraped from: `mercadolibre` or `argenprop`. Listing IDs are per source, so a unit published on both portals appears twice. |
| neighborhood  | text      | The barrio (one of CABA's 48 official neighborhoods), standardized from the sources' raw labels (64 raw values mapped to 48 barrios): sub-zones such as Palermo Soho, Las Cañitas or Belgrano R are folded into their official barrio, and informal names such as Barrio Norte, Once or Congreso into Recoleta and Balvanera. |
| price         | number    | Listing asking price, in USD. |
| covered_m2    | number    | Covered surface area in square meters. This is covered area, not total area. |
| ambientes     | number    | The local count of a unit's main living spaces, not bedrooms: 1 is a single combined living and sleeping space, 2 has a separate bedroom, and so on. Excludes bathroom and kitchen, and runs roughly bedrooms plus one. Populated for every row. |
| bedrooms      | number    | Number of bedrooms. Only Argenprop exposes it in search results, so it is populated for 0.2% of rows (101 listings) and blank for the rest. Use `ambientes` instead. |
| url           | text      | Link to the original listing. |
| captured_at   | timestamp | When the listing was scraped (UTC). |
| price_per_m2  | number    | Derived: price divided by covered_m2, in USD per square meter. |

## Notes

- Prices are asking prices from listings, not closed transaction prices.
- Coverage per barrio is complete for Mercado Libre except in the largest barrios:
  the portal caps every search at 2,000 results, so searches were split by ambientes
  (1, 2, 3+) and the 3+ segment of Palermo, Belgrano, Recoleta and Caballito still hit
  the cap. Those four barrios are therefore slightly under-represented in large units.
  Argenprop covers only Villa Real: its anti-bot protection blocked the per-barrio
  crawl after the first barrio.
- Mercado Libre also lists new developments ("emprendimientos", a building with many
  units and a "from" price); these are not single listings and were dropped.
- Bathroom counts are available for most Mercado Libre rows in the database but are not
  part of this file, to keep the column set of the previous release.
- This is a single snapshot, not a time series, so there is no price history.
- The `url` column points to each listing as it existed at `captured_at`. Listings get
  removed over time as they sell or expire, so some links may now return a 404 or
  redirect to search. This is expected, not a data error.
