import json
import os
from datetime import date
from pathlib import Path

import requests
from dotenv import load_dotenv


load_dotenv()


LATITUDE = os.getenv("LATITUDE", "51.5072")
LONGITUDE = os.getenv("LONGITUDE", "-0.1276")
TIMEZONE = os.getenv("TIMEZONE", "Europe/London")

# First year of data. Derived from START_DATE (e.g. 2022-01-01) so the year
# range below extends automatically to the present instead of stopping at a
# hardcoded list.
START_YEAR = int(os.getenv("START_DATE", "2022-01-01")[:4])

RAW_WEATHER_BASE = Path("data/raw/open_meteo")


def parse_years() -> list[int]:
    """All years from the configured start year through the current year."""
    return list(range(START_YEAR, date.today().year + 1))



def weather_output_file(year: int) -> Path:
    return RAW_WEATHER_BASE / f"year={year}" / f"london_weather_{year}.json"


def needs_extraction(year: int, current_year: int) -> bool:
    """Decide whether to (re)fetch a year.

    The moving head -- the current year and the previous year -- is always
    refreshed, because the current year is still being filled in and the
    previous year may still be revised. Older, frozen years are fetched only
    if we don't already have their output file (i.e. first-time backfill).
    """
    if year >= current_year - 1:
        return True
    return not weather_output_file(year).exists()


def fetch_weather_for_year(year: int) -> dict:
    start_date = f"{year}-01-01"

    # The Open-Meteo archive only covers dates up to ~5 days ago, so for the
    # current year cap the request at today rather than 31 Dec.
    today = date.today()
    end_date = today.isoformat() if year == today.year else f"{year}-12-31"

    url = (
        "https://archive-api.open-meteo.com/v1/archive"
        f"?latitude={LATITUDE}"
        f"&longitude={LONGITUDE}"
        f"&start_date={start_date}"
        f"&end_date={end_date}"
        "&hourly=temperature_2m,relative_humidity_2m,precipitation,pressure_msl,wind_speed_10m"
        f"&timezone={TIMEZONE}"
    )

    print(f"Fetching Open-Meteo weather data for {year}")
    print(url)

    response = requests.get(url, timeout=120)
    response.raise_for_status()

    data = response.json()

    if "hourly" not in data:
        raise ValueError(
            f"Open-Meteo response for {year} does not contain hourly data: {data}"
        )

    required_hourly_fields = [
        "time",
        "temperature_2m",
        "relative_humidity_2m",
        "precipitation",
        "pressure_msl",
        "wind_speed_10m",
    ]

    missing_fields = [
        field for field in required_hourly_fields if field not in data["hourly"]
    ]

    if missing_fields:
        raise ValueError(
            f"Open-Meteo response for {year} is missing fields: {missing_fields}"
        )

    return data


def save_weather_json(year: int, data: dict) -> None:
    output_file = weather_output_file(year)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # "w" overwrites the file.
    # Do not use "a", because append mode can corrupt JSON files.
    with open(output_file, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)

    print(f"Saved weather data to: {output_file}")


def main() -> None:
    current_year = date.today().year
    years = parse_years()

    for year in years:
        if not needs_extraction(year, current_year):
            print(f"Skipping {year}: frozen year already extracted.")
            continue

        weather_data = fetch_weather_for_year(year)
        save_weather_json(year, weather_data)

    print("Weather extraction completed successfully.")


if __name__ == "__main__":
    main()