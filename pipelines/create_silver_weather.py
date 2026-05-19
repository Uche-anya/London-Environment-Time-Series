from pathlib import Path

import duckdb


BRONZE_WEATHER_BASE = Path("data/bronze/weather")
SILVER_WEATHER_BASE = Path("data/silver/weather")


def create_silver_weather() -> None:
    SILVER_WEATHER_BASE.mkdir(parents=True, exist_ok=True)

    parquet_files = sorted(BRONZE_WEATHER_BASE.glob("year=*/*.parquet"))

    if not parquet_files:
        raise FileNotFoundError(
            f"No bronze weather Parquet files found under {BRONZE_WEATHER_BASE}."
        )

    con = duckdb.connect()

    for parquet_file in parquet_files:
        year = parquet_file.parent.name.replace("year=", "")

        output_dir = SILVER_WEATHER_BASE / f"year={year}"
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = output_dir / f"silver_weather_{year}.parquet"

        print(f"Creating silver weather for {year}")

        con.execute(
            f"""
            COPY (
                SELECT
                    CAST(recorded_at AS TIMESTAMP) AS recorded_at,
                    city,
                    TRY_CAST(temperature_2m AS DOUBLE) AS temperature_2m,
                    TRY_CAST(relative_humidity_2m AS DOUBLE) AS relative_humidity_2m,
                    TRY_CAST(precipitation AS DOUBLE) AS precipitation,
                    TRY_CAST(pressure_msl AS DOUBLE) AS pressure_msl,
                    TRY_CAST(wind_speed_10m AS DOUBLE) AS wind_speed_10m,
                    EXTRACT(YEAR FROM CAST(recorded_at AS TIMESTAMP)) AS year,
                    source_name
                FROM read_parquet('{parquet_file.as_posix()}')
                WHERE recorded_at IS NOT NULL
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
    print("Silver weather layer created successfully.")


if __name__ == "__main__":
    create_silver_weather()