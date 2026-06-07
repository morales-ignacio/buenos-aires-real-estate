CREATE TABLE IF NOT EXISTS neighborhoods (
    id           SERIAL PRIMARY KEY,
    name         TEXT UNIQUE NOT NULL,
    comuna       SMALLINT,
    centroid_lat NUMERIC,
    centroid_lng NUMERIC
);

CREATE TABLE IF NOT EXISTS scrape_runs (
    id            BIGSERIAL PRIMARY KEY,
    source        TEXT NOT NULL,
    started_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at   TIMESTAMPTZ,
    status        TEXT,
    listings_seen INTEGER DEFAULT 0,
    listings_new  INTEGER DEFAULT 0,
    error_count   INTEGER DEFAULT 0,
    notes         TEXT
);

CREATE TABLE IF NOT EXISTS listings (
    id               BIGSERIAL PRIMARY KEY,
    source           TEXT NOT NULL,
    source_id        TEXT NOT NULL,
    url              TEXT NOT NULL,
    operation        TEXT,
    property_type    TEXT,
    neighborhood_id  INTEGER REFERENCES neighborhoods(id),
    raw_neighborhood TEXT,
    total_m2         NUMERIC,
    covered_m2       NUMERIC,
    ambientes        SMALLINT,
    bedrooms         SMALLINT,
    bathrooms        SMALLINT,
    is_pozo          BOOLEAN,
    latitude         NUMERIC,
    longitude        NUMERIC,
    description      TEXT,
    first_seen_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_active        BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (source, source_id)
);

CREATE TABLE IF NOT EXISTS listing_snapshots (
    id                BIGSERIAL PRIMARY KEY,
    listing_id        BIGINT NOT NULL REFERENCES listings(id),
    run_id            BIGINT NOT NULL REFERENCES scrape_runs(id),
    price             NUMERIC,
    currency          TEXT,
    expensas          NUMERIC,
    expensas_currency TEXT,
    captured_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);



CREATE INDEX IF NOT EXISTS idx_snap_listing_time ON listing_snapshots (listing_id, captured_at);
CREATE INDEX IF NOT EXISTS idx_listings_hood ON listings (neighborhood_id);