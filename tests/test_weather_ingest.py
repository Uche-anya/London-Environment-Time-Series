from datetime import date
from urllib.parse import parse_qs, urlparse

import pytest

from lambda_src import weather_ingest


pytestmark = pytest.mark.unit


def _weather_response(year: int = 2026) -> dict:
    timestamps = [f"{year}-07-26T22:00", f"{year}-07-26T23:00"]
    return {
        "hourly": {
            "time": timestamps,
            "temperature_2m": [18.1, 17.8],
            "relative_humidity_2m": [70, 72],
            "precipitation": [0.0, 0.0],
            "pressure_msl": [1012.1, 1012.0],
            "wind_speed_10m": [8.2, 7.9],
        }
    }


def test_archive_availability_applies_five_day_lag(monkeypatch):
    monkeypatch.setattr(weather_ingest, "ARCHIVE_LAG_DAYS", 5)
    assert weather_ingest.available_through(date(2026, 7, 31)) == date(2026, 7, 26)
    assert weather_ingest.year_bounds(2026, date(2026, 7, 31)) == (
        date(2026, 1, 1),
        date(2026, 7, 26),
    )


def test_configured_years_include_backfill_through_available_year(monkeypatch):
    monkeypatch.setattr(weather_ingest, "START_DATE", date(2022, 1, 1))
    monkeypatch.setattr(weather_ingest, "ARCHIVE_LAG_DAYS", 5)
    assert weather_ingest.configured_years(date(2026, 7, 31)) == [
        2022,
        2023,
        2024,
        2025,
        2026,
    ]


def test_source_url_uses_era5_and_gmt(monkeypatch):
    monkeypatch.setattr(weather_ingest, "MODEL", "era5")
    monkeypatch.setattr(weather_ingest, "TIMEZONE", "GMT")
    query = parse_qs(
        urlparse(
            weather_ingest.source_url(date(2026, 1, 1), date(2026, 7, 26))
        ).query
    )
    assert query["models"] == ["era5"]
    assert query["timezone"] == ["GMT"]
    assert query["end_date"] == ["2026-07-26"]


def test_validate_weather_checks_schema_lengths_and_year():
    result = weather_ingest.validate_weather(_weather_response(), 2026)
    assert result == {"row_count": 2, "latest_timestamp": "2026-07-26T23:00"}

    invalid = _weather_response()
    invalid["hourly"]["precipitation"] = [0.0]
    with pytest.raises(ValueError, match="length mismatches"):
        weather_ingest.validate_weather(invalid, 2026)


def test_serialisation_ignores_volatile_generation_time():
    first = _weather_response()
    second = _weather_response()
    first["generationtime_ms"] = 1.23
    second["generationtime_ms"] = 9.87

    assert weather_ingest.serialise_weather(first) == weather_ingest.serialise_weather(
        second
    )


def test_destination_key_matches_weather_partition_layout(monkeypatch):
    monkeypatch.setattr(weather_ingest, "S3_PREFIX", "raw/open_meteo")
    assert weather_ingest.destination_key(2026) == (
        "raw/open_meteo/year=2026/london_weather_2026.json"
    )
