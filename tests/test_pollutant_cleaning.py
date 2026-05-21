import duckdb


def clean_pollutant_value(raw_value: str):
    """
    Applies the same cleaning rule used in the silver air-quality layer.

    Negative pollutant values become NULL.
    Zero and positive values are kept.
    Invalid text becomes NULL.
    """

    con = duckdb.connect()

    cleaned_value = con.execute(
        """
        SELECT
            CASE
                WHEN TRY_CAST(? AS DOUBLE) < 0 THEN NULL
                ELSE TRY_CAST(? AS DOUBLE)
            END AS cleaned_value;
        """,
        [raw_value, raw_value],
    ).fetchone()[0]

    con.close()

    return cleaned_value


def test_negative_pollutant_value_becomes_null():
    assert clean_pollutant_value("-0.5") is None


def test_zero_pollutant_value_is_kept():
    assert clean_pollutant_value("0") == 0


def test_positive_pollutant_value_is_kept():
    assert clean_pollutant_value("12.5") == 12.5


def test_invalid_pollutant_value_becomes_null():
    assert clean_pollutant_value("bad-value") is None