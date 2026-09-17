# Buenos Aires Real Estate

An end-to-end data pipeline that scrapes property listings from two Buenos Aires portals, builds a structured dataset covering all 48 barrios of the city, and uses it to analyse how apartment prices vary across neighbourhoods.

The project focuses on making scraped data actually usable:

- **Reproducible pipeline** — runs barrio by barrio and saves each completed block, so an interrupted crawl does not lose everything collected before it.
- **Two sources, one schema** — listings are deduplicated by source and listing ID, with barrio names mapped to the 48 official neighbourhoods.
- **Price analysis in USD** — sale prices are cleaned with plausibility checks before calculating price per m².
- **Documented dataset** — 59,069 cleaned listings published for reuse.

## The problem

There is no clean public dataset of Buenos Aires apartment prices by barrio. Listings are spread across real-estate portals and come with different formats, naming conventions and data quality issues.

This project builds that dataset from scratch and uses it to look at how price per m² varies across the city and how much of that variation can be explained by location and unit size.

## Findings

Based on 59,069 listings across all 48 barrios (September 2026). The first version used 1,901 listings across 30 barrios; the findings below were re-tested on the larger dataset.

1. **Puerto Madero sits in a separate price tier.** Median price per m² ranges from roughly USD 1,000 in the southern barrios to around USD 3,900 in Palermo and Núñez. Puerto Madero reaches about USD 6,200, around 1.58× the next barrio. There is still overlap at the lower end, though — unlike the first version suggested.

2. **Location explains much more of price per m² than unit size.** Barrio accounts for 46% of the variation in price per m², while unit size accounts for 0.7% and adds almost nothing after barrio is included. There is one important exception: units above 100 m² tend to have a higher price per m².

3. **Total price and price per m² produce different rankings.** Recoleta ranks 3rd by median total price but 11th by price per m², largely because its typical units are larger. The two rankings are still strongly related overall, with a rank correlation of 0.93.

## Report

The full analysis, methodology and charts are in [`report/report.md`](report/report.md).

## Two sources, and why

The project started with Argenprop and collected 1,901 listings before its anti-bot protection stopped the crawl. Splitting the crawl by barrio did not solve the problem: requests were challenged after a few calls and blocked for 15 minutes or more.

I added Mercado Libre Inmuebles as a second source because its search pages expose the listings as JSON and could be accessed without the same blocking. It also covers all 48 barrios.

There are still some source-specific issues to handle. Mercado Libre limits searches to 2,000 results, so large barrios are split by number of rooms. New developments are removed, and redirects that silently remove the search filters are detected and retried.

The final dataset is therefore mainly a Mercado Libre snapshot, with Argenprop contributing 70 listings from Villa Real.

## Tech stack

Python, uv, httpx, BeautifulSoup, PostgreSQL (Neon), SQLAlchemy, pandas, matplotlib, Jupyter

## Project structure

```text
buenos-aires-real-estate/

├── analysis/      analysis_v2.ipynb re-tests the findings on the full dataset;
│                  eda.ipynb and queries.ipynb contain the original exploration
├── data/          cleaned dataset (listings.csv) and data dictionary
├── db/            database schema and connection setup
├── pipeline/      scrapers, storage, barrio normalization and dataset export
├── report/        report, charts and figure-generation notebook
├── samples/       saved search pages used to develop parsers offline
└── scrapers/      one parser per portal, both returning the same listing structure
