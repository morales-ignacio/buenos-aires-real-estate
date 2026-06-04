# Buenos Aires Real Estate Trends

> **Status:** In progress, updated as I build it out.

An end-to-end data pipeline that scrapes Buenos Aires property listings, builds a longitudinal price dataset, and turns it into a written market analysis. It focuses on what most scraping projects skip:

- **A real time series**, daily snapshots instead of a one-off scrape
- **USD versus peso tracking**, listings joined to daily exchange rates
- **Days on market and price drops**, inferred from listings appearing and disappearing over time
- **A reproducible pipeline**, scheduled collection rather than a manual script run
- **A documented dataset**, cleaned and published for reuse

## The problem

Reliable time-series data on the Buenos Aires property market is scarce. Listings sit on portals like Zonaprop and Argenprop, but nobody publishes how prices move over time, how off-plan (pozo) units compare to finished ones, or how dollar and peso pricing diverge.

This project collects that data independently to answer two questions: (1) how prices and listing dynamics vary across neighborhoods, and (2) how the USD versus peso gap shapes the market over time.

## Planned approach

1. **Reconnaissance**: inspect sources, map available fields, define the neighborhood scope
2. **Schema and ingestion**: design the listings and snapshots model, build the first scraper end to end
3. **Pipeline**: run tracking, fault tolerance, a second source, daily scheduling via GitHub Actions
4. **Enrichment**: neighborhood normalization, currency handling, daily exchange rate ingestion
5. **Analysis and release**: aggregate views, a written market report, a published dataset

## Tech stack

Python, uv, httpx, BeautifulSoup, Playwright, PostgreSQL, SQLAlchemy, pandas, matplotlib, Jupyter, GitHub Actions

## Project structure

```
buenos-aires-real-estate/
├── scrapers/    # source-specific scrapers + shared interface
├── db/          # schema + connection helpers
├── pipeline/    # scrape orchestration, normalization, exchange rates
├── analysis/    # aggregate views (SQL)
├── report/      # written analysis + charts
├── data/        # released dataset + data dictionary
└── .github/     # scheduled scraping workflow
```