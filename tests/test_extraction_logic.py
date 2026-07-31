import pytest

from pipelines import extract_raw_s3

pytestmark = pytest.mark.unit


def test_missing_local_file_is_downloaded(tmp_path):
    local_path = tmp_path / "london_bloomsbury_2025.csv"
    assert extract_raw_s3.is_already_downloaded(local_path, {"Size": 100}) is False


def test_matching_size_is_skipped(tmp_path):
    local_path = tmp_path / "london_bloomsbury_2025.csv"
    local_path.write_bytes(b"0123456789")
    assert extract_raw_s3.is_already_downloaded(local_path, {"Size": 10}) is True


def test_size_mismatch_is_redownloaded(tmp_path):
    local_path = tmp_path / "london_bloomsbury_2026.csv"
    local_path.write_bytes(b"0123456789") 
    assert extract_raw_s3.is_already_downloaded(local_path, {"Size": 4096}) is False


def test_current_and_previous_air_quality_years_are_always_refreshed():
    assert extract_raw_s3.is_recent_year_key(
        "raw/defra/london_bloomsbury/year=2030/file.csv", 2030
    ) is True
    assert extract_raw_s3.is_recent_year_key(
        "raw/defra/london_bloomsbury/year=2029/file.csv", 2030
    ) is True
    assert extract_raw_s3.is_recent_year_key(
        "raw/defra/london_bloomsbury/year=2028/file.csv", 2030
    ) is False
