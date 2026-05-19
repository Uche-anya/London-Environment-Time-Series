from pathlib import Path

import duckdb


RAW_WEATHER_PATH = Path("data/raw/open_meteo/london_weather_2022_2025.json")
BRONZE_WEATHER_BASE = Path("data/bronze/weather")


def create_bronze_weather() -> None:
    if not RAW_WEATHER_PATH.exists():
        raise FileNotFoundError(
            f"Weather JSON not found: {RAW_WEATHER_PATH}. "
            "Run pipelines/extract_weather.py first."
        )

    BRONZE_WEATHER_BASE.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect()

    print(f"Reading raw weather JSON: {RAW_WEATHER_PATH}")

    con.execute(
        f"""
        CREATE OR REPLACE TABLE weather_bronze AS
        SELECT
            unnest(hourly.time) AS recorded_at,
            unnest(hourly.temperature_2m) AS temperature_2m,
            unnest(hourly.relative_humidity_2m) AS relative_humidity_2m,
            unnest(hourly.precipitation) AS precipitation,
            unnest(hourly.pressure_msl) AS pressure_msl,
            unnest(hourly.wind_speed_10m) AS wind_speed_10m,
            'London' AS city,
            'Open-Meteo' AS source_name
        FROM read_json_auto('{RAW_WEATHER_PATH.as_posix()}');
        """
    )

    years = con.execute(
        """
        SELECT DISTINCT EXTRACT(YEAR FROM CAST(recorded_at AS TIMESTAMP)) AS year
        FROM weather_bronze
        ORDER BY year;
        """
    ).fetchall()

    for (year,) in years:
        output_dir = BRONZE_WEATHER_BASE / f"year={int(year)}"
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = output_dir / f"bronze_weather_{int(year)}.parquet"

        print(f"Writing bronze weather for {int(year)}: {output_file}")

        con.execute(
            f"""
            COPY (
                SELECT *
                FROM weather_bronze
                WHERE EXTRACT(YEAR FROM CAST(recorded_at AS TIMESTAMP)) = {int(year)}
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

    con.close()
    print("Bronze weather layer created successfully.")


if __name__ == "__main__":
    create_bronze_weather()

    