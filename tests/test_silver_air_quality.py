from datetime import datetime

import duckdb
import pytest

from pipelines.create_silver_air_quality import (
    POLLUTANTS,
    create_recorded_at_expression,
)

pytestmark = pytest.mark.unit


def _recorded_at(date_value, time_value):
    """Run the production recorded_at SQL expression against a single synthetic row."""
    con = duckdb.connect()
    expr = create_recorded_at_expression()
    row = con.execute(
        f'SELECT {expr} AS recorded_at FROM (SELECT ? AS "Date", ? AS "time")',
        [date_value, time_value],
    ).fetchone()
    con.close()
    return row[0]


# --- recorded_at timestamp construction -------------------------------------

def test_normal_time_with_dmy_date():
    # DEFRA's day/month/year date plus a normal hour.
    assert _recorded_at("1/1/2024", "13:00") == datetime(2024, 1, 1, 13, 0)


def test_iso_date_is_parsed():
    # Dates already in ISO form must still parse.
    assert _recorded_at("2024-03-15", "09:00") == datetime(2024, 3, 15, 9, 0)


def test_24_00_rolls_to_next_day():
    # DEFRA encodes midnight as 24:00 of the *previous* day; it must roll forward.
    assert _recorded_at("1/1/2024", "24:00") == datetime(2024, 1, 2, 0, 0)


def test_24_00_rolls_across_year_boundary():
    # The roll-forward must also cross month/year boundaries.
    assert _recorded_at("31/12/2024", "24:00") == datetime(2025, 1, 1, 0, 0)


# --- pollutant pivot mapping ------------------------------------------------

def test_pollutant_mapping_is_complete():
    # The silver pivot must emit exactly these seven pollutants, matching the
    # set the GX validation expects downstream.
    names = {item["pollutant"] for item in POLLUTANTS}
    assert names == {"NO", "NO2", "NOx", "O3", "PM10", "PM2.5", "SO2"}
    assert len(POLLUTANTS) == 7


def test_pollutant_entries_have_raw_column_and_name():
    # Each mapping needs a source column and a target pollutant label.
    for item in POLLUTANTS:
        assert item["raw_column"]
        assert item["pollutant"]
