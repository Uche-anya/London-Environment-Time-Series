

CREATE EXTENSION IF NOT EXISTS timescaledb;

-- -----------------------------------------------------------------------------
-- Daily air quality metrics (one row per date / site / pollutant)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS daily_air_quality_metrics (
    reading_date       DATE             NOT NULL,
    site_name          TEXT             NOT NULL,
    pollutant          TEXT             NOT NULL,
    avg_value          DOUBLE PRECISION,
    min_value          DOUBLE PRECISION,
    max_value          DOUBLE PRECISION,
    valid_readings     INTEGER,
    expected_readings  INTEGER,
    missing_readings   INTEGER,
    completeness_pct   DOUBLE PRECISION,
    year               INTEGER,
    month              INTEGER,
    PRIMARY KEY (reading_date, site_name, pollutant)
);

-- -----------------------------------------------------------------------------
-- Daily weather metrics (one row per date / city)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS daily_weather_metrics (
    reading_date                  DATE             NOT NULL,
    city                          TEXT             NOT NULL,
    avg_temperature_2m            DOUBLE PRECISION,
    min_temperature_2m            DOUBLE PRECISION,
    max_temperature_2m            DOUBLE PRECISION,
    avg_relative_humidity_2m      DOUBLE PRECISION,
    total_precipitation           DOUBLE PRECISION,
    avg_pressure_msl              DOUBLE PRECISION,
    avg_wind_speed_10m            DOUBLE PRECISION,
    expected_readings             INTEGER,
    valid_temperature_readings    INTEGER,
    missing_temperature_readings  INTEGER,
    temperature_completeness_pct  DOUBLE PRECISION,
    year                          INTEGER,
    month                         INTEGER,
    PRIMARY KEY (reading_date, city)
);

-- -----------------------------------------------------------------------------
-- Hourly environment metrics (air quality joined to weather) -> hypertable
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS hourly_environment_metrics (
    recorded_at           TIMESTAMPTZ      NOT NULL,
    reading_date          DATE,
    site_name             TEXT             NOT NULL,
    city                  TEXT,
    pollutant             TEXT             NOT NULL,
    pollutant_value       DOUBLE PRECISION,
    pollutant_unit        TEXT,
    temperature_2m        DOUBLE PRECISION,
    relative_humidity_2m  DOUBLE PRECISION,
    precipitation         DOUBLE PRECISION,
    pressure_msl          DOUBLE PRECISION,
    wind_speed_10m        DOUBLE PRECISION,
    year                  INTEGER,
    month                 INTEGER,
    PRIMARY KEY (recorded_at, site_name, pollutant)
);

SELECT create_hypertable(
    'hourly_environment_metrics',
    'recorded_at',
    if_not_exists => TRUE
);
