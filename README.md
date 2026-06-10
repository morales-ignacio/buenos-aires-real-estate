# Buenos Aires Real Estate

An end-to-end data pipeline that scrapes Buenos Aires property listings, builds a structured dataset of current listings, and turns it into a written market analysis. It focuses on the things that make scraped data actually usable:

- **A reproducible, code-driven pipeline**, run on demand (cloud scheduling was attempted but blocked by the site's bot protection)
- **Fault-tolerant collection**, so a single failed page never loses a whole run
- **Sale prices in USD, analyzed across neighborhoods**
- **A documented dataset**, cleaned and published for reuse


## The problem

There is no clean, public dataset of Buenos Aires apartment prices broken down by
barrio. Listings sit scattered across real-estate portals in inconsistent, messy
form. This project builds one from scratch: it scrapes CABA apartment sale listings,
cleans and standardizes them, and uses the result to ask how price per m² varies
across the city and what drives the differences.


## Findings

1. **CABA has a clear price-per-m² map, and Puerto Madero is in its own tier.** Median
   price per m² runs from about 1,600 USD in the cheapest barrios to about 3,150 in the
   priciest, with Puerto Madero alone at about 5,800.
2. **Location drives price per m², not unit size.** Smaller units are not pricier per
   m². The most expensive barrio per m² also has the largest apartments.
3. **Expensive overall and expensive per m² are not the same ranking.** Recoleta ranks
   near the top on total price but only mid-pack on price per m².


## Report

The full writeup with charts and method is in [report/report.md](report/report.md).


## Tech stack

Python, uv, httpx, BeautifulSoup, PostgreSQL, SQLAlchemy, pandas, matplotlib, Jupyter


## Project structure

\`\`\`
analysis/      eda.ipynb and queries.ipynb, the work behind the findings
data/          the cleaned dataset (listings.csv) and its data_dictionary.md
db/            schema.sql defines the tables, init_db.py creates them, connection.py connects
pipeline/      run.py scrapes and loads listings; normalize.py standardizes barrios; export_dataset.py writes the published CSV
report/        report.md, its charts, and make_figures.ipynb
samples/       a saved Argenprop page used to develop the parser offline
scrapers/      parses listing data out of Argenprop's HTML (parse_argenprop.py)
\`\`\`


## How to run

1. Set `DATABASE_URL` in a `.env` file (your Postgres connection string).
2. Install dependencies: `uv sync`
3. Create the database tables: `uv run python -m db.init_db`
4. Scrape Argenprop and load the listings: `uv run python -m pipeline.run`
5. Normalize barrio names: `uv run python -m pipeline.normalize`
6. Open the notebooks in `analysis/` to reproduce the analysis.


## Limitations

This is a single snapshot rather than a series over time, some barrios rest on small
samples, and pricing is USD-only.