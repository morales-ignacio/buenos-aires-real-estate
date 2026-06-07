# Buenos Aires Real Estate

> **Status:** In progress, updated as I build it out.

An end-to-end data pipeline that scrapes Buenos Aires property listings, builds a structured dataset of current listings, and turns it into a written market analysis. It focuses on the things that make scraped data actually usable:

- **A reproducible, code-driven pipeline**, run on demand (cloud scheduling was attempted but blocked by the site's bot protection)
- **Fault-tolerant collection**, so a single failed page never loses a whole run
- **Sale prices in USD, analyzed across neighborhoods**
- **A documented dataset**, cleaned and published for reuse

## The problem

This project collects data independently to answer how apartment prices vary across CABA neighborhoods.

## Planned approach

1. **Reconnaissance**: inspect sources, map available fields, define the neighborhood scope
2. **Schema**: design the listings and snapshots model
3. **Pipeline**: pagination, run tracking, fault tolerance
4. **Enrichment**: neighborhood normalization
5. **Analysis and release**: aggregate views, a written market report

## Tech stack

Python, uv, httpx, BeautifulSoup, PostgreSQL, SQLAlchemy, pandas, matplotlib, Jupyter

## Project structure

```
buenos-aires-real-estate/
├── scrapers/    # Argenprop scraper + parser
├── db/          # schema + connection helpers
├── pipeline/    # scrape orchestration, normalization
├── analysis/    # aggregate views (SQL)
├── report/      # written analysis + charts
├── data/        # released dataset + data dictionary
└── .github/     # (paused) scheduled scraping workflow
```

## Limitations


- **No price trends over time.** Property prices move slowly and listings stay up for weeks or months, so meaningful trend or days-on-market analysis would need many months of continuous collection to show real signal.
- **Single source, single market.** Data comes only from Argenprop, and only for apartments for sale in CABA (Capital Federal). Other portals, property types, and the greater Buenos Aires province are not included.
- **Collection runs locally.** Cloud scheduling via GitHub Actions was attempted but blocked by the site's bot protection, which rejects data-center IPs, so runs are triggered manually from a local machine instead.