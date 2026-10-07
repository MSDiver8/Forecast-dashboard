-- Initial schema. Long format: one row of `observations` is one value of one series
-- for one target period in one release. Rows are never updated: a new release adds rows.

CREATE TABLE sources (
    source_id    VARCHAR PRIMARY KEY,
    name         VARCHAR NOT NULL,
    organization VARCHAR NOT NULL,
    url          VARCHAR,
    license      VARCHAR,
    access       VARCHAR,
    role         VARCHAR NOT NULL  -- forecast | actual
);

CREATE TABLE indicators (
    indicator_id VARCHAR PRIMARY KEY,
    name         VARCHAR NOT NULL,
    unit         VARCHAR NOT NULL,
    transform    VARCHAR NOT NULL,  -- level, yoy, dec_dec, avg_year ...
    base         VARCHAR,
    group_id     VARCHAR NOT NULL,
    description  VARCHAR,
    precision    INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE areas (
    area_id VARCHAR PRIMARY KEY,
    name    VARCHAR NOT NULL,
    kind    VARCHAR NOT NULL  -- country | aggregate | market
);

CREATE TABLE source_series (
    source_id       VARCHAR NOT NULL,
    series_code     VARCHAR NOT NULL,
    indicator_id    VARCHAR NOT NULL,
    area_id         VARCHAR NOT NULL,
    definition_note VARCHAR,
    PRIMARY KEY (source_id, series_code, indicator_id, area_id)
);

CREATE TABLE releases (
    release_id      VARCHAR PRIMARY KEY,
    source_id       VARCHAR NOT NULL,
    title           VARCHAR NOT NULL,
    vintage_date    DATE NOT NULL,      -- publication date
    data_cutoff     VARCHAR,            -- last period treated as actual by the source
    fetched_at      TIMESTAMP NOT NULL,
    raw_path        VARCHAR NOT NULL,
    source_url      VARCHAR,
    checksum_sha256 VARCHAR NOT NULL
);

CREATE TABLE observations (
    release_id    VARCHAR NOT NULL,
    indicator_id  VARCHAR NOT NULL,
    area_id       VARCHAR NOT NULL,
    target_period VARCHAR NOT NULL,  -- 2026 | 2026-Q1 | 2026-01 | 2026/27
    frequency     VARCHAR NOT NULL,  -- A | Q | M | MY
    value         DOUBLE NOT NULL,
    lower         DOUBLE,            -- published range or interval, if any
    upper         DOUBLE,
    kind          VARCHAR NOT NULL,  -- forecast | actual | estimate
    PRIMARY KEY (release_id, indicator_id, area_id, target_period)
);

CREATE TABLE benchmark_runs (
    run_id         VARCHAR PRIMARY KEY,
    model          VARCHAR NOT NULL,
    params         VARCHAR NOT NULL,  -- JSON
    indicator_id   VARCHAR NOT NULL,
    area_id        VARCHAR NOT NULL,
    frequency      VARCHAR NOT NULL,
    origin         VARCHAR NOT NULL,  -- last actual period used
    actual_release VARCHAR NOT NULL,  -- release of the training data
    computed_at    TIMESTAMP NOT NULL
);

CREATE TABLE benchmark_forecasts (
    run_id        VARCHAR NOT NULL,
    target_period VARCHAR NOT NULL,
    value         DOUBLE NOT NULL,
    lower80       DOUBLE,
    upper80       DOUBLE,
    lower95       DOUBLE,
    upper95       DOUBLE,
    PRIMARY KEY (run_id, target_period)
);

CREATE SEQUENCE ingestion_log_seq;

CREATE TABLE ingestion_log (
    log_id      BIGINT PRIMARY KEY DEFAULT nextval('ingestion_log_seq'),
    source_id   VARCHAR NOT NULL,
    started_at  TIMESTAMP NOT NULL,
    finished_at TIMESTAMP,
    status      VARCHAR NOT NULL,  -- ok | error
    releases    INTEGER,
    rows_added  INTEGER,
    error       VARCHAR
);
