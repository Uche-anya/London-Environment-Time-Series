from pathlib import Path

import duckdb


SILVER_WEATHER_PATH = "data/silver/weather/year=*/silver_weather_*.parquet"
GOLD_WEATHER_BASE = Path("data/gold/daily_weather")


def create_gold_daily_weather() -> None:
    GOLD_WEATHER_BASE.mkdir(parents=True, exist_ok=True)

    output_file = GOLD_WEATHER_BASE / "daily_weather_metrics.parquet"

    con = duckdb.connect()

    print("Creating gold daily weather metrics...")

    con.execute(
        f"""
        COPY (
            WITH silver AS (
                SELECT
                    CAST(recorded_at AS DATE) AS reading_date,
                    city,
                    temperature_2m,
                    relative_humidity_2m,
                    precipitation,
                    pressure_msl,
                    wind_speed_10m
                FROM read_parquet('{SILVER_WEATHER_PATH}')
            )

            SELECT
                reading_date,
                city,

                AVG(temperature_2m) AS avg_temperature_2m,
                MIN(temperature_2m) AS min_temperature_2m,
                MAX(temperature_2m) AS max_temperature_2m,

                AVG(relative_humidity_2m) AS avg_relative_humidity_2m,
                SUM(precipitation) AS total_precipitation,
                AVG(pressure_msl) AS avg_pressure_msl,
                AVG(wind_speed_10m) AS avg_wind_speed_10m,

                COUNT(*) AS expected_readings,
                COUNT(temperature_2m) AS valid_temperature_readings,
                COUNT(*) - COUNT(temperature_2m) AS missing_temperature_readings,
                ROUND(COUNT(temperature_2m) * 100.0 / COUNT(*), 2) AS temperature_completeness_pct,

                EXTRACT(YEAR FROM reading_date) AS year,
                EXTRACT(MONTH FROM reading_date) AS month

            FROM silver

            GROUP BY
                reading_date,
                city

            ORDER BY
                reading_date
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

    print(f"Saved: {output_file}")
    print(f"Rows written: {row_count}")

    con.close()


if __name__ == "__main__":
    create_gold_daily_weather()