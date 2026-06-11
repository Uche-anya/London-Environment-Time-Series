-- Indexes for the London Environment serving layer.
--
-- Mirrors the indexes created in pipelines/create_timescale_tables.py.
-- Kept here as a readable reference; the pipeline is the runtime source of truth.

CREATE INDEX IF NOT EXISTS idx_daily_air_quality_date_pollutant
    ON daily_air_quality_metrics (reading_date, pollutant);

CREATE INDEX IF NOT EXISTS idx_daily_weather_date
    ON daily_weather_metrics (reading_date);

CREATE INDEX IF NOT EXISTS idx_hourly_environment_time_pollutant
    ON hourly_environment_metrics (recorded_at, pollutant);

CREATE INDEX IF NOT EXISTS idx_hourly_environment_pollutant_year_month
    ON hourly_environment_metrics (pollutant, year, month);
