from datetime import date

import pytest

from lambda_src import defra_ingest


pytestmark = pytest.mark.unit


def _csv_payload(year: int = 2026) -> bytes:
    return (
        f"Data supplied by UK-AIR on 31/7/{year}\n"
        "All Data GMT hour ending\n"
        "Status: R =Ratified P=Provisional,P*=As supplied\n"
        ",,London Bloomsbury,,\n"
        "Date,time,Nitrogen dioxide,status,unit\n"
        f"30-07-{year},23:00,13.77,P,ugm-3\n"
        f"30-07-{year},24:00:00,15.10875,P,ugm-3\n"
    ).encode()


def test_default_years_refreshes_current_and_previous(monkeypatch):
    monkeypatch.setattr(defra_ingest, "YEARS_TO_REFRESH", 2)
    assert defra_ingest.default_years(date(2026, 7, 31)) == [2026, 2025]


def test_manual_event_years_are_validated_and_deduplicated():
    assert defra_ingest.parse_event_years(
        {"years": ["2026", 2025, 2026]}, date(2026, 7, 31)
    ) == [2026, 2025]
    with pytest.raises(ValueError, match="outside the supported range"):
        defra_ingest.parse_event_years({"years": [2027]}, date(2026, 7, 31))


def test_validate_csv_accepts_current_defra_midnight_format():
    result = defra_ingest.validate_csv(_csv_payload(), 2026)
    assert result == {"row_count": 2, "latest_data_date": "2026-07-30"}


def test_validate_csv_rejects_html_and_wrong_year():
    with pytest.raises(ValueError, match="HTML instead of CSV"):
        defra_ingest.validate_csv(b"<html>temporary error</html>", 2026)
    with pytest.raises(ValueError, match="contains date"):
        defra_ingest.validate_csv(_csv_payload(2025), 2026)


def test_destination_key_matches_existing_partition_layout(monkeypatch):
    monkeypatch.setattr(
        defra_ingest, "S3_PREFIX", "raw/defra/london_bloomsbury"
    )
    assert defra_ingest.destination_key(2026) == (
        "raw/defra/london_bloomsbury/year=2026/london_bloomsbury_2026.csv"
    )
