from pathlib import Path

import duckdb


BRONZE_BASE = Path("data/bronze/air_quality")
SILVER_BASE = Path("data/silver/air_quality")


POLLUTANTS = [
    {
        "raw_column": "PM<sub>10</sub> particulate matter (Hourly measured)",
        "pollutant": "PM10",
    },
    {
        "raw_column": "Nitric oxide",
        "pollutant": "NO",
    },
    {
        "raw_column": "Nitrogen dioxide",
        "pollutant": "NO2",
    },
    {
        "raw_column": "Nitrogen oxides as nitrogen dioxide",
        "pollutant": "NOx",
    },
    {
        "raw_column": "Ozone",
        "pollutant": "O3",
    },
    {
        "raw_column": "PM<sub>2.5</sub> particulate matter (Hourly measured)",
        "pollutant": "PM2.5",
    },
    {
        "raw_column": "Sulphur dioxide",
        "pollutant": "SO2",
    },
]


def create_recorded_at_expression() -> str:
    """
    Build a timestamp from the DEFRA Date and time columns.

    Handles:
    - Date values like 1/1/2024
    - Date values already converted by DuckDB, like 2024-01-01
    - Special 24:00 values by moving them to the next day at 00:00
    """

    return """
        CASE
            WHEN TRIM(CAST(time AS VARCHAR)) = '24:00'
            THEN CAST(
                COALESCE(
                    TRY_CAST(Date AS DATE),
                    CAST(TRY_STRPTIME(TRIM(CAST(Date AS VARCHAR)), '%d/%m/%Y') AS DATE),
                    CAST(TRY_STRPTIME(TRIM(CAST(Date AS VARCHAR)), '%Y-%m-%d %H:%M:%S') AS DATE)
                ) + INTERVAL 1 DAY
                AS TIMESTAMP
            )
            ELSE CAST(
                CAST(
                    COALESCE(
                        TRY_CAST(Date AS DATE),
                        CAST(TRY_STRPTIME(TRIM(CAST(Date AS VARCHAR)), '%d/%m/%Y') AS DATE),
                        CAST(TRY_STRPTIME(TRIM(CAST(Date AS VARCHAR)), '%Y-%m-%d %H:%M:%S') AS DATE)
                    ) AS VARCHAR
                )
                || ' '
                || TRIM(CAST(time AS VARCHAR))
                AS TIMESTAMP
            )
        END
    """


def create_silver_air_quality() -> None:
    """
    Convert bronze DEFRA air-quality Parquet files into clean silver Parquet files.

    Bronze format:
        Date | time | PM10 | status | unit | NO2 | status | unit | ...

    Silver format:
        recorded_at | site_name | pollutant | value | unit | year | source_file

    Cleaning rules:
    - Blank pollutant readings become NULL
    - Invalid numeric values become NULL
    - Negative pollutant readings become NULL
    - Valid zero values stay as 0
    """

    SILVER_BASE.mkdir(parents=True, exist_ok=True)

    parquet_files = sorted(BRONZE_BASE.glob("year=*/*.parquet"))

    if not parquet_files:
        raise FileNotFoundError(
            f"No bronze Parquet files found under {BRONZE_BASE}. "
            "Run pipelines/create_bronze_air_quality.py first."
        )

    con = duckdb.connect()

    for parquet_file in parquet_files:
        year = parquet_file.parent.name.replace("year=", "")

        output_dir = SILVER_BASE / f"year={year}"
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = output_dir / f"silver_air_quality_{year}.parquet"

        union_queries = []

        for item in POLLUTANTS:
            raw_column = item["raw_column"]
            pollutant = item["pollutant"]

            query = f"""
                SELECT
                    {create_recorded_at_expression()} AS recorded_at,
                    site_name,
                    '{pollutant}' AS pollutant,
                    CASE
                        WHEN TRY_CAST("{raw_column}" AS DOUBLE) < 0 THEN NULL
                        ELSE TRY_CAST("{raw_column}" AS DOUBLE)
                    END AS value,
                    'ugm-3' AS unit,
                    source_year AS year,
                    source_file
                FROM read_parquet('{parquet_file.as_posix()}')
                WHERE Date IS NOT NULL
                  AND TRIM(CAST(Date AS VARCHAR)) <> ''
            """

            union_queries.append(query)

        final_query = "\nUNION ALL\n".join(union_queries)

        print(f"Creating silver air quality for {year}")

        con.execute(
            f"""
            COPY (
                SELECT
                    recorded_at,
                    site_name,
                    pollutant,
                    value,
                    unit,
                    year,
                    source_file
                FROM ({final_query})
                WHERE recorded_at IS NOT NULL
            )
            TO '{output_file.as_posix()}'
            (FORMAT PARQUET);
            """
        )

        row_count = con.execute(
            f"""
            SELECT COUNT(*)
            FROM read_parquet('{output_file.as_posix()}');
            """
        ).fetchone()[0]

        valid_count = con.execute(
            f"""
            SELECT COUNT(value)
            FROM read_parquet('{output_file.as_posix()}');
            """
        ).fetchone()[0]

        missing_or_invalid_count = row_count - valid_count

        print(f"Saved: {output_file}")
        print(f"Rows written: {row_count}")
        print(f"Valid pollutant readings: {valid_count}")
        print(f"Missing/invalid pollutant readings: {missing_or_invalid_count}")

    con.close()

    print("Silver air quality layer created successfully.")


if __name__ == "__main__":
    create_silver_air_quality()