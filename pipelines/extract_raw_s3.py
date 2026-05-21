import json
import os
from pathlib import Path
import requests
from dotenv import load_dotenv


load_dotenv()


LATITUDE = os.getenv("LATITUDE", "51.5072")
LONGITUDE = os.getenv("LONGITUDE", "-0.1276")
TIMEZONE = os.getenv("TIMEZONE", "Europe/London")
YEARS = os.getenv("YEARS", "2022,2023,2024,2025")

RAW_WEATHER_BASE = Path("data/raw/open_meteo")


def parse_years() -> list[int]:
    return [int(year.strip()) for year in YEARS.split(",") if year.strip()]


def fetch_weather_for_year(year: int) -> dict:
    start_date = f"{year}-01-01"
    end_date = f"{year}-12-31"

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
    response = requests.get(url, timeout=120)
    response.raise_for_status()

    return response.json()


def save_weather_json(year: int, data: dict) -> None:
    output_dir = RAW_WEATHER_BASE / f"year={year}"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f"london_weather_{year}.json"

    with open(output_file, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)

    print(f"Saved weather data to: {output_file}")


def main() -> None:
    years = parse_years()

    for year in years:
        data = fetch_weather_for_year(year)
        save_weather_json(year, data)

    print("Weather extraction completed successfully.")


if __name__ == "__main__":
    main()