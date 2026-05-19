from io import StringIO

import duckdb

from src.utils.db import get_postgres_connection


GOLD_DAILY_AIR_QUALITY = (
    "data/gold/daily_air_quality/daily_air_quality_metrics.parquet"
)

GOLD_DAILY_WEATHER = (
    "data/gold/daily_weather/daily_weather_metrics.parquet"
)

GOLD_HOURLY_ENVIRONMENT = (
    "data/gold/hourly_environment_metrics/hourly_environment_metrics.parquet"
)


def copy_dataframe_to_table(conn, df, table_name: str) -> None:
    """
    Fast-load a DataFrame into a PostgreSQL/TimescaleDB table using COPY.
    This is faster than inserting row by row.
    """

    buffer = StringIO()

    df.to_csv(
        buffer,
        index=False,
        header=False,
        na_rep="\\N",
    )

    buffer.seek(0)

    columns = ", ".join(df.columns)

    copy_sql = f"""
        COPY {table_name} ({columns})
        FROM STDIN
        WITH (
            FORMAT CSV,
            NULL '\\N'
        );
    """

    cur = conn.cursor()
    cur.copy_expert(copy_sql, buffer)
    conn.commit()
    cur.close()


def upsert_daily_air_quality(con_duckdb, conn_pg) -> None:
    print("Incrementally loading daily_air_quality_metrics...")

    df = con_duckdb.execute(
        f"""
        SELECT
            reading_date,
            site_name,
            pollutant,
            avg_value,
            min_value,
            max_value,
            valid_readings,
            expected_readings,
            missing_readings,
            completeness_pct,
            year,
            month
        FROM read_parquet('{GOLD_DAILY_AIR_QUALITY}')
        ORDER BY reading_date, pollutant;
        """
    ).fetchdf()

    cur = conn_pg.cursor()

    cur.execute("DROP TABLE IF EXISTS staging_daily_air_quality_metrics;")

    cur.execute(
        """
        CREATE TEMP TABLE staging_daily_air_quality_metrics (
            reading_date DATE,
            site_name TEXT,
            pollutant TEXT,
            avg_value DOUBLE PRECISION,
            min_value DOUBLE PRECISION,
            max_value DOUBLE PRECISION,
            valid_readings INTEGER,
            expected_readings INTEGER,
            missing_readings INTEGER,
            completeness_pct DOUBLE PRECISION,
            year INTEGER,
            month INTEGER
        );
        """
    )

    conn_pg.commit()
    cur.close()

    copy_dataframe_to_table(conn_pg, df, "staging_daily_air_quality_metrics")

    cur = conn_pg.cursor()

    cur.execute(
        """
        INSERT INTO daily_air_quality_metrics (
            reading_date,
            site_name,
            pollutant,
            avg_value,
            min_value,
            max_value,
            valid_readings,
            expected_readings,
            missing_readings,
            completeness_pct,
            year,
            month
        )
        SELECT
            reading_date,
            site_name,
            pollutant,
            avg_value,
            min_value,
            max_value,
            valid_readings,
            expected_readings,
            missing_readings,
            completeness_pct,
            year,
            month
        FROM staging_daily_air_quality_metrics
        ON CONFLICT (reading_date, site_name, pollutant)
        DO UPDATE SET
            avg_value = EXCLUDED.avg_value,
            min_value = EXCLUDED.min_value,
            max_value = EXCLUDED.max_value,
            valid_readings = EXCLUDED.valid_readings,
            expected_readings = EXCLUDED.expected_readings,
            missing_readings = EXCLUDED.missing_readings,
            completeness_pct = EXCLUDED.completeness_pct,
            year = EXCLUDED.year,
            month = EXCLUDED.month;
        """
    )

    conn_pg.commit()
    cur.close()

    print(f"Upserted {len(df)} rows into daily_air_quality_metrics.")


def upsert_daily_weather(con_duckdb, conn_pg) -> None:
    print("Incrementally loading daily_weather_metrics...")

    df = con_duckdb.execute(
        f"""
        SELECT
            reading_date,
            city,
            avg_temperature_2m,
            min_temperature_2m,
            max_temperature_2m,
            avg_relative_humidity_2m,
            total_precipitation,
            avg_pressure_msl,
            avg_wind_speed_10m,
            expected_readings,
            valid_temperature_readings,
            missing_temperature_readings,
            temperature_completeness_pct,
            year,
            month
        FROM read_parquet('{GOLD_DAILY_WEATHER}')
        ORDER BY reading_date;
        """
    ).fetchdf()

    cur = conn_pg.cursor()

    cur.execute("DROP TABLE IF EXISTS staging_daily_weather_metrics;")

    cur.execute(
        """
        CREATE TEMP TABLE staging_daily_weather_metrics (
            reading_date DATE,
            city TEXT,
            avg_temperature_2m DOUBLE PRECISION,
            min_temperature_2m DOUBLE PRECISION,
            max_temperature_2m DOUBLE PRECISION,
            avg_relative_humidity_2m DOUBLE PRECISION,
            total_precipitation DOUBLE PRECISION,
            avg_pressure_msl DOUBLE PRECISION,
            avg_wind_speed_10m DOUBLE PRECISION,
            expected_readings INTEGER,
            valid_temperature_readings INTEGER,
            missing_temperature_readings INTEGER,
            temperature_completeness_pct DOUBLE PRECISION,
            year INTEGER,
            month INTEGER
        );
        """
    )

    conn_pg.commit()
    cur.close()

    copy_dataframe_to_table(conn_pg, df, "staging_daily_weather_metrics")

    cur = conn_pg.cursor()

    cur.execute(
        """
        INSERT INTO daily_weather_metrics (
            reading_date,
            city,
            avg_temperature_2m,
            min_temperature_2m,
            max_temperature_2m,
            avg_relative_humidity_2m,
            total_precipitation,
            avg_pressure_msl,
            avg_wind_speed_10m,
            expected_readings,
            valid_temperature_readings,
            missing_temperature_readings,
            temperature_completeness_pct,
            year,
            month
        )
        SELECT
            reading_date,
            city,
            avg_temperature_2m,
            min_temperature_2m,
            max_temperature_2m,
            avg_relative_humidity_2m,
            total_precipitation,
            avg_pressure_msl,
            avg_wind_speed_10m,
            expected_readings,
            valid_temperature_readings,
            missing_temperature_readings,
            temperature_completeness_pct,
            year,
            month
        FROM staging_daily_weather_metrics
        ON CONFLICT (reading_date, city)
        DO UPDATE SET
            avg_temperature_2m = EXCLUDED.avg_temperature_2m,
            min_temperature_2m = EXCLUDED.min_temperature_2m,
            max_temperature_2m = EXCLUDED.max_temperature_2m,
            avg_relative_humidity_2m = EXCLUDED.avg_relative_humidity_2m,
            total_precipitation = EXCLUDED.total_precipitation,
            avg_pressure_msl = EXCLUDED.avg_pressure_msl,
            avg_wind_speed_10m = EXCLUDED.avg_wind_speed_10m,
            expected_readings = EXCLUDED.expected_readings,
            valid_temperature_readings = EXCLUDED.valid_temperature_readings,
            missing_temperature_readings = EXCLUDED.missing_temperature_readings,
            temperature_completeness_pct = EXCLUDED.temperature_completeness_pct,
            year = EXCLUDED.year,
            month = EXCLUDED.month;
        """
    )

    conn_pg.commit()
    cur.close()

    print(f"Upserted {len(df)} rows into daily_weather_metrics.")


def upsert_hourly_environment(con_duckdb, conn_pg) -> None:
    print("Incrementally loading hourly_environment_metrics...")

    df = con_duckdb.execute(
        f"""
        SELECT
            recorded_at,
            reading_date,
            site_name,
            city,
            pollutant,
            pollutant_value,
            pollutant_unit,
            temperature_2m,
            relative_humidity_2m,
            precipitation,
            pressure_msl,
            wind_speed_10m,
            year,
            month
        FROM read_parquet('{GOLD_HOURLY_ENVIRONMENT}')
        ORDER BY recorded_at, pollutant;
        """
    ).fetchdf()

    cur = conn_pg.cursor()

    cur.execute("DROP TABLE IF EXISTS staging_hourly_environment_metrics;")

    cur.execute(
        """
        CREATE TEMP TABLE staging_hourly_environment_metrics (
            recorded_at TIMESTAMPTZ,
            reading_date DATE,
            site_name TEXT,
            city TEXT,
            pollutant TEXT,
            pollutant_value DOUBLE PRECISION,
            pollutant_unit TEXT,
            temperature_2m DOUBLE PRECISION,
            relative_humidity_2m DOUBLE PRECISION,
            precipitation DOUBLE PRECISION,
            pressure_msl DOUBLE PRECISION,
            wind_speed_10m DOUBLE PRECISION,
            year INTEGER,
            month INTEGER
        );
        """
    )

    conn_pg.commit()
    cur.close()

    copy_dataframe_to_table(conn_pg, df, "staging_hourly_environment_metrics")

    cur = conn_pg.cursor()

    cur.execute(
        """
        INSERT INTO hourly_environment_metrics (
            recorded_at,
            reading_date,
            site_name,
            city,
            pollutant,
            pollutant_value,
            pollutant_unit,
            temperature_2m,
            relative_humidity_2m,
            precipitation,
            pressure_msl,
            wind_speed_10m,
            year,
            month
        )
        SELECT
            recorded_at,
            reading_date,
            site_name,
            city,
            pollutant,
            pollutant_value,
            pollutant_unit,
            temperature_2m,
            relative_humidity_2m,
            precipitation,
            pressure_msl,
            wind_speed_10m,
            year,
            month
        FROM staging_hourly_environment_metrics
        ON CONFLICT (recorded_at, site_name, pollutant)
        DO UPDATE SET
            reading_date = EXCLUDED.reading_date,
            city = EXCLUDED.city,
            pollutant_value = EXCLUDED.pollutant_value,
            pollutant_unit = EXCLUDED.pollutant_unit,
            temperature_2m = EXCLUDED.temperature_2m,
            relative_humidity_2m = EXCLUDED.relative_humidity_2m,
            precipitation = EXCLUDED.precipitation,
            pressure_msl = EXCLUDED.pressure_msl,
            wind_speed_10m = EXCLUDED.wind_speed_10m,
            year = EXCLUDED.year,
            month = EXCLUDED.month;
        """
    )

    conn_pg.commit()
    cur.close()

    print(f"Upserted {len(df)} rows into hourly_environment_metrics.")


def main() -> None:
    con_duckdb = duckdb.connect()
    conn_pg = get_postgres_connection()

    upsert_daily_air_quality(con_duckdb, conn_pg)
    upsert_daily_weather(con_duckdb, conn_pg)
    upsert_hourly_environment(con_duckdb, conn_pg)

    con_duckdb.close()
    conn_pg.close()

    print("Incremental gold load into TimescaleDB completed successfully.")


if __name__ == "__main__":
    main()