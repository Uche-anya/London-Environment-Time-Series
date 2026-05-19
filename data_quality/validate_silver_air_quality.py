import duckdb

con = duckdb.connect()

sample = con.execute(
    """
    SELECT *
    FROM read_parquet('data/silver/air_quality/year=2024/silver_air_quality_2024.parquet')
    ORDER BY recorded_at, pollutant
    LIMIT 30;
    """
).fetchdf()

print(sample)

summary = con.execute(
    """
    SELECT
        pollutant,
        COUNT(*) AS total_rows,
        COUNT(value) AS valid_readings,
        COUNT(*) - COUNT(value) AS missing_readings,
        ROUND(COUNT(value) * 100.0 / COUNT(*), 2) AS completeness_pct
    FROM read_parquet('data/silver/air_quality/year=2024/silver_air_quality_2024.parquet')
    GROUP BY pollutant
    ORDER BY pollutant;
    """
).fetchdf()

print(summary)

date_range = con.execute(
    """
    SELECT
        MIN(recorded_at) AS min_recorded_at,
        MAX(recorded_at) AS max_recorded_at,
        COUNT(*) AS total_rows
    FROM read_parquet('data/silver/air_quality/year=2024/silver_air_quality_2024.parquet');
    """
).fetchdf()

print(date_range)

con.close()