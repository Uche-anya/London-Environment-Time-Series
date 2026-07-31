from datetime import datetime

import duckdb
import pytest

from pipelines.create_silver_air_quality import create_recorded_at_expression


pytestmark = pytest.mark.unit


def test_24_00_with_seconds_rolls_to_next_day():
    """Current DEFRA downloads can render the final hour as 24:00:00."""
    expression = create_recorded_at_expression()
    with duckdb.connect() as connection:
        recorded_at = connection.execute(
            f'SELECT {expression} FROM (SELECT ? AS "Date", ? AS "time")',
            ["30/07/2026", "24:00:00"],
        ).fetchone()[0]

    assert recorded_at == datetime(2026, 7, 31, 0, 0)
