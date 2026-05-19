import duckdb

con = duckdb.connect()

print("\nDaily air quality:")
print(
    con.execute(
        """
        SELECT *
        FROM read_parquet('data/gold/daily_air_quality/daily_air_quality_metrics.parquet')
        ORDER BY reading_date, pollutant
        LIMIT 20;
        """
    ).fetchdf()
)

print("\nDaily weather:")
print(
    con.execute(
        """
        SELECT *
        FROM read_parquet('data/gold/daily_weather/daily_weather_metrics.parquet')
        ORDER BY reading_date
        LIMIT 20;
        """
    ).fetchdf()
)

print("\nHourly environment metrics:")
print(
    con.execute(
        """
        SELECT *
        FROM read_parquet('data/gold/hourly_environment_metrics/hourly_environment_metrics.parquet')
        ORDER BY recorded_at, pollutant
        LIMIT 20;
        """
    ).fetchdf()
)

print("\nGold row counts:")
print(
    con.execute(
        """
        SELECT 'daily_air_quality' AS table_name, COUNT(*) AS rows
        FROM read_parquet('data/gold/daily_air_quality/daily_air_quality_metrics.parquet')

        UNION ALL

        SELECT 'daily_weather' AS table_name, COUNT(*) AS rows
        FROM read_parquet('data/gold/daily_weather/daily_weather_metrics.parquet')

        UNION ALL

        SELECT 'hourly_environment_metrics' AS table_name, COUNT(*) AS rows
        FROM read_parquet('data/gold/hourly_environment_metrics/hourly_environment_metrics.parquet');
        """
    ).fetchdf()
)

con.close()