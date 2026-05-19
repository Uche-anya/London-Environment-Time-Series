from pathlib import Path

import duckdb
import great_expectations as gx

context = gx.get_context()


GOLD_AIR_QUALITY_PATH = (
    "data/gold/daily_air_quality/daily_air_quality_metrics.parquet"
)

GOLD_WEATHER_PATH = (
    "data/gold/daily_weather/daily_weather_metrics.parquet"
)

GOLD_ENVIRONMENT_PATH = (
    "data/gold/hourly_environment_metrics/hourly_environment_metrics.parquet"
)


def validate_daily_air_quality() -> bool:

    con = duckdb.connect()

    df = con.execute(
        f"""
        SELECT *
        FROM read_parquet('{GOLD_AIR_QUALITY_PATH}');
        """
    ).fetchdf()

    con.close()

    validator = gx.validator.validator.Validator(
        execution_engine=gx.execution_engine.PandasExecutionEngine(),
        batches=[
            gx.core.batch.Batch(
                data=df
            )
        ],
    )

    validator.expect_table_row_count_to_be_between(min_value=10000, max_value=11000)

    validator.expect_column_values_to_not_be_null("reading_date")
    validator.expect_column_values_to_not_be_null("site_name")
    validator.expect_column_values_to_not_be_null("pollutant")
    validator.expect_column_values_to_be_between(
    "min_value",
    min_value=0,
    mostly=1.0,
)

    validator.expect_column_values_to_be_in_set(
        "pollutant",
        ["NO", "NO2", "NOx", "O3", "PM10", "PM2.5", "SO2"],
    )

    validator.expect_column_values_to_be_between(
        "completeness_pct",
        min_value=0,
        max_value=100,
    )

    validator.expect_column_pair_values_A_to_be_greater_than_B(
        column_A="expected_readings",
        column_B="valid_readings",
        or_equal=True,
    )

    result = validator.validate()

    print("Daily air quality success:", result.success)
    return result.success


def validate_daily_weather() -> bool:

    con = duckdb.connect()

    df = con.execute(
        f"""
        SELECT *
        FROM read_parquet('{GOLD_WEATHER_PATH}');
        """
    ).fetchdf()

    con.close()

    validator = gx.validator.validator.Validator(
        execution_engine=gx.execution_engine.PandasExecutionEngine(),
        batches=[
            gx.core.batch.Batch(
                data=df
            )
        ],
    )

    validator.expect_table_row_count_to_be_between(min_value=1400, max_value=1500)

    validator.expect_column_values_to_not_be_null("reading_date")
    validator.expect_column_values_to_not_be_null("city")

    validator.expect_column_values_to_be_between(
        "avg_temperature_2m",
        min_value=-20,
        max_value=45,
    )

    validator.expect_column_values_to_be_between(
        "temperature_completeness_pct",
        min_value=0,
        max_value=100,
    )

    result = validator.validate()

    print("Daily weather success:", result.success)
    return result.success


def validate_hourly_environment_metrics() -> bool:
    print("Validating gold hourly environment metrics...")

    con = duckdb.connect()

    # We validate summary values instead of loading all 245k rows into GX.
    df = con.execute(
        f"""
        SELECT
            COUNT(*) AS total_rows,
            COUNT(temperature_2m) AS weather_matched_rows,
            ROUND(COUNT(temperature_2m) * 100.0 / COUNT(*), 2) AS weather_match_pct
        FROM read_parquet('{GOLD_ENVIRONMENT_PATH}');
        """
    ).fetchdf()

    con.close()

    validator = gx.validator.validator.Validator(
        execution_engine=gx.execution_engine.PandasExecutionEngine(),
        batches=[
            gx.core.batch.Batch(
                data=df
            )
        ],
    )

    validator.expect_column_values_to_be_between(
        "total_rows",
        min_value=240000,
        max_value=250000,
    )

    validator.expect_column_values_to_be_between(
        "weather_match_pct",
        min_value=99,
        max_value=100,
    )

    result = validator.validate()

    print("Hourly environment success:", result.success)
    return result.success


def main() -> None:
    required_files = [
        GOLD_AIR_QUALITY_PATH,
        GOLD_WEATHER_PATH,
        GOLD_ENVIRONMENT_PATH,
    ]

    for file_path in required_files:
        if not Path(file_path).exists():
            raise FileNotFoundError(f"Missing gold file: {file_path}")

    results = [
        validate_daily_air_quality(),
        validate_daily_weather(),
        validate_hourly_environment_metrics(),
    ]

    if not all(results):
        raise ValueError("One or more GX data quality validations failed.")

    print("All GX validations passed.")


if __name__ == "__main__":
    main()