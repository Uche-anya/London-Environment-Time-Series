import json
from pathlib import Path

import duckdb
import pandas as pd


RAW_WEATHER_BASE = Path("data/raw/open_meteo")
BRONZE_WEATHER_BASE = Path("data/bronze/weather")


REQUIRED_HOURLY_FIELDS = [
    "time",
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "pressure_msl",
    "wind_speed_10m",
]


def load_weather_json(json_file: Path) -> dict:
    with open(json_file, "r", encoding="utf-8") as file:
        data = json.load(file)

    if "hourly" not in data:
        raise ValueError(f"Missing 'hourly' section in {json_file}")

    missing_fields = [
        field for field in REQUIRED_HOURLY_FIELDS
        if field not in data["hourly"]
    ]

    if missing_fields:
        raise ValueError(f"Missing fields in {json_file}: {missing_fields}")

    return data


def flatten_weather_json(data: dict, year: int, source_file: str) -> pd.DataFrame:
    hourly = data["hourly"]

    row_count = len(hourly["time"])

    for field in REQUIRED_HOURLY_FIELDS:
        if len(hourly[field]) != row_count:
            raise ValueError(
                f"Length mismatch for field '{field}' in {source_file}. "
                f"Expected {row_count}, got {len(hourly[field])}."
            )

    return pd.DataFrame(
        {
            "recorded_at": hourly["time"],
            "temperature_2m": hourly["temperature_2m"],
            "relative_humidity_2m": hourly["relative_humidity_2m"],
            "precipitation": hourly["precipitation"],
            "pressure_msl": hourly["pressure_msl"],
            "wind_speed_10m": hourly["wind_speed_10m"],
            "city": "London",
            "source_name": "Open-Meteo",
            "source_year": year,
            "source_file": source_file,
        }
    )


def create_bronze_weather() -> None:
    BRONZE_WEATHER_BASE.mkdir(parents=True, exist_ok=True)

    json_files = sorted(RAW_WEATHER_BASE.glob("year=*/london_weather_*.json"))

    if not json_files:
        raise FileNotFoundError(
            f"No weather JSON files found under {RAW_WEATHER_BASE}. "
            "Run pipelines/extract_weather.py first."
        )

    con = duckdb.connect()

    for json_file in json_files:
        year = int(json_file.parent.name.replace("year=", ""))

        output_dir = BRONZE_WEATHER_BASE / f"year={year}"
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = output_dir / f"bronze_weather_{year}.parquet"

        print(f"Reading raw weather JSON: {json_file}")
        data = load_weather_json(json_file)

        df = flatten_weather_json(
            data=data,
            year=year,
            source_file=json_file.name,
        )

        print(f"Writing bronze weather Parquet: {output_file}")

        con.register("weather_df", df)

        con.execute(
            f"""
            COPY (
                SELECT *
                FROM weather_df
            )
            TO '{output_file.as_posix()}'
            (FORMAT PARQUET);
            """
        )

        con.unregister("weather_df")

        row_count = con.execute(
            f"""
            SELECT COUNT(*)
            FROM read_parquet('{output_file.as_posix()}');
            """
        ).fetchone()[0]

        print(f"Saved: {output_file}")
        print(f"Rows written: {row_count}")

    con.close()

    print("Bronze weather layer created successfully.")


if __name__ == "__main__":
    create_bronze_weather()