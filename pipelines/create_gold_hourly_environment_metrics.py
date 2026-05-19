from pathlib import Path

import duckdb


SILVER_AIR_QUALITY_PATH = "data/silver/air_quality/year=*/silver_air_quality_*.parquet"
SILVER_WEATHER_PATH = "data/silver/weather/year=*/silver_weather_*.parquet"

GOLD_ENVIRONMENT_BASE = Path("data/gold/hourly_environment_metrics")


def create_gold_hourly_environment_metrics() -> None:
    GOLD_ENVIRONMENT_BASE.mkdir(parents=True, exist_ok=True)

    output_file = GOLD_ENVIRONMENT_BASE / "hourly_environment_metrics.parquet"

    con = duckdb.connect()

    con.execute(
        f"""
        COPY (
            SELECT
                aq.recorded_at,
                CAST(aq.recorded_at AS DATE) AS reading_date,
                aq.site_name,
                w.city,
                aq.pollutant,
                aq.value AS pollutant_value,
                aq.unit AS pollutant_unit,
                w.temperature_2m,
                w.relative_humidity_2m,
                w.precipitation,
                w.pressure_msl,
                w.wind_speed_10m,
                EXTRACT(YEAR FROM aq.recorded_at) AS year,
                EXTRACT(MONTH FROM aq.recorded_at) AS month
            FROM read_parquet('{SILVER_AIR_QUALITY_PATH}') aq
            LEFT JOIN read_parquet('{SILVER_WEATHER_PATH}') w
                ON aq.recorded_at = w.recorded_at
            ORDER BY
                aq.recorded_at,
                aq.pollutant
        )
        TO '{output_file.as_posix()}'
        (FORMAT PARQUET);
        """
    )

    row_count = con.execute(
        f"""
        SELECT COUNT(*)
        FROM read_parquet('{output_file.as_posix()}');
        """
    ).fetchone()[0]

    weather_matched_count = con.execute(
        f"""
        SELECT COUNT(*)
        FROM read_parquet('{output_file.as_posix()}')
        WHERE temperature_2m IS NOT NULL;
        """
    ).fetchone()[0]

    print(f"Saved: {output_file}")
    print(f"Rows written: {row_count}")
    print(f"Rows with matching weather: {weather_matched_count}")
    print(f"Rows without matching weather: {row_count - weather_matched_count}")

    con.close()


if __name__ == "__main__":
    create_gold_hourly_environment_metrics()