from datetime import date

import pytest

from pipelines import extract_raw_s3, extract_weather

pytestmark = pytest.mark.unit


# --- dynamic year range -----------------------------------------------------

def test_parse_years_spans_start_to_current_year():
    years = extract_weather.parse_years()
    current_year = date.today().year

    assert years[0] == extract_weather.START_YEAR
    assert years[-1] == current_year
    # Contiguous, no gaps, no hardcoded ceiling.
    assert years == list(range(extract_weather.START_YEAR, current_year + 1))


# --- frozen-tail extraction decision ----------------------------------------

def test_current_and_previous_year_are_always_refetched():
    # The "moving head" is always re-fetched regardless of any existing file.
    assert extract_weather.needs_extraction(2030, 2030) is True
    assert extract_weather.needs_extraction(2029, 2030) is True


def test_frozen_year_is_fetched_only_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(extract_weather, "RAW_WEATHER_BASE", tmp_path)

    # Closed year with no output yet -> must fetch (first-time backfill).
    assert extract_weather.needs_extraction(2000, 2030) is True

    # Once its output exists, the frozen year is skipped.
    output_file = extract_weather.weather_output_file(2000)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text("{}", encoding="utf-8")
    assert extract_weather.needs_extraction(2000, 2030) is False


# --- incremental S3 sync (skip unchanged) -----------------------------------

def test_missing_local_file_is_downloaded(tmp_path):
    local_path = tmp_path / "london_bloomsbury_2025.csv"
    assert extract_raw_s3.is_already_downloaded(local_path, {"Size": 100}) is False


def test_matching_size_is_skipped(tmp_path):
    local_path = tmp_path / "london_bloomsbury_2025.csv"
    local_path.write_bytes(b"0123456789")  # 10 bytes
    assert extract_raw_s3.is_already_downloaded(local_path, {"Size": 10}) is True


def test_size_mismatch_is_redownloaded(tmp_path):
    # The growing current-year file changes size, so it must re-download.
    local_path = tmp_path / "london_bloomsbury_2026.csv"
    local_path.write_bytes(b"0123456789")  # 10 bytes
    assert extract_raw_s3.is_already_downloaded(local_path, {"Size": 4096}) is False
