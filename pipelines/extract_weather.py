import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv


load_dotenv()

LATITUDE = os.getenv("LATITUDE", "51.5072")
LONGITUDE = os.getenv("LONGITUDE", "-0.1276")
START_DATE = os.getenv("START_DATE", "2022-01-01")
END_DATE = os.getenv("END_DATE", "2025-12-31")

OUTPUT_PATH = Path("data/raw/open_meteo/london_weather_2022_2025.json")
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

url = (
    "https://archive-api.open-meteo.com/v1/archive"
    f"?latitude={LATITUDE}"
    f"&longitude={LONGITUDE}"
    f"&start_date={START_DATE}"
    f"&end_date={END_DATE}"
    "&hourly=temperature_2m,relative_humidity_2m,precipitation,pressure_msl,wind_speed_10m"
    "&timezone=Europe/London"
)

print("Fetching historical weather data from Open-Meteo...")
print(url)

response = requests.get(url, timeout=120)
response.raise_for_status()

data = response.json()

with open(OUTPUT_PATH, "w", encoding="utf-8") as file:
    json.dump(data, file, indent=2)

print(f"Weather data saved to: {OUTPUT_PATH}")