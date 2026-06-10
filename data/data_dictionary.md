# Data dictionary

`listings.csv` is a cleaned, single-snapshot dataset of apartment sale listings in the
City of Buenos Aires (CABA), scraped from Argenprop. Each row is one listing, taken
from its most recent scrape. The file holds 1,901 listings.

**Scope:** only listings priced in USD, with a known covered area and a recognized
barrio, are included. This is the same clean subset the analysis is based on.

## Columns

| Column        | Type      | Description |
|---------------|-----------|-------------|
| neighborhood  | text      | The barrio (CABA neighborhood), standardized from Argenprop's raw, inconsistent labels (76 raw values mapped to 41 barrios). |
| price         | number    | Listing asking price, in USD. |
| covered_m2    | number    | Covered surface area in square meters. This is covered area, not total area, which the source left empty. |
| ambientes     | number    | The local count of a unit's main living spaces, not bedrooms: 1 is a single combined living and sleeping space, 2 has a separate bedroom, and so on. Excludes bathroom and kitchen, and runs roughly bedrooms plus one. Populated for nearly all listings. |
| bedrooms      | number    | Number of bedrooms. Populated for most listings; blank for the rest. |
| url           | text      | Link to the original Argenprop listing. |
| captured_at   | timestamp | When the listing was scraped (UTC). |
| price_per_m2  | number    | Derived: price divided by covered_m2, in USD per square meter. |

## Notes

- Prices are asking prices from listings, not closed transaction prices.
- The source also exposed fields for total area, a pre-construction (pozo) flag, and a
  free-text description, but all three were empty across every listing, so they are not
  included. Bathroom counts were present for only about a fifth of listings, too sparse
  to rely on, and were left out as well.
- This is a single snapshot, not a time series, so there is no price history.
- The `url` column points to each listing as it existed at `captured_at`. Listings get
  removed over time as they sell or expire, so some links may now return a 404 or
  redirect to search. This is expected, not a data error.