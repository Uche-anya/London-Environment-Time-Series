from pathlib import Path

import duckdb


RAW_BASE = Path("data/raw/defra/london_bloomsbury")

EXPECTED_COLUMNS = [
    "Date",
    "time",
    "PM<sub>10</sub> particulate matter (Hourly measured)",
    "Nitric oxide",
    "Nitrogen dioxide",
    "Nitrogen oxides as nitrogen dioxide",
    "Ozone",
    "PM<sub>2.5</sub> particulate matter (Hourly measured)",
    "Sulphur dioxide",
]

POLLUTANT_COLUMNS = [
    "PM<sub>10</sub> particulate matter (Hourly measured)",
    "Nitric oxide",
    "Nitrogen dioxide",
    "Nitrogen oxides as nitrogen dioxide",
    "Ozone",
    "PM<sub>2.5</sub> particulate matter (Hourly measured)",
    "Sulphur dioxide",
]


def inspect_file(con: duckdb.DuckDBPyConnection, csv_file: Path) -> None:
    year = csv_file.parent.name.replace("year=", "")

    print("\n" + "=" * 100)
    print(f"Inspecting {year}: {csv_file}")
    print("=" * 100)

    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE raw_data AS
        SELECT *
        FROM read_csv_auto(
            '{csv_file.as_posix()}',
            skip=4,
            header=true,
            nullstr=['', ' ', 'NA', 'N/A'],
            ignore_errors=true
        )
        WHERE Date IS NOT NULL
          AND TRIM(CAST(Date AS VARCHAR)) <> '';
        """
    )

    columns = con.execute("DESCRIBE raw_data;").fetchdf()["column_name"].tolist()

    print("\nColumn check:")
    for col in EXPECTED_COLUMNS:
        status = "OK" if col in columns else "MISSING"
        print(f"{status}: {col}")

    row_count = con.execute("SELECT COUNT(*) FROM raw_data;").fetchone()[0]

    distinct_datetime_count = con.execute(
        """
        SELECT COUNT(*)
        FROM (
            SELECT Date, time
            FROM raw_data
            GROUP BY Date, time
        );
        """
    ).fetchone()[0]

    duplicate_datetime_count = con.execute(
        """
        SELECT COUNT(*)
        FROM (
            SELECT Date, time, COUNT(*) AS row_count
            FROM raw_data
            GROUP BY Date, time
            HAVING COUNT(*) > 1
        );
        """
    ).fetchone()[0]

    midnight_24_count = con.execute(
        """
        SELECT COUNT(*)
        FROM raw_data
        WHERE TRIM(CAST(time AS VARCHAR)) = '24:00';
        """
    ).fetchone()[0]

    print("\nBasic row checks:")
    print(f"Total raw hourly rows: {row_count}")
    print(f"Distinct Date/time pairs: {distinct_datetime_count}")
    print(f"Duplicate Date/time pairs: {duplicate_datetime_count}")
    print(f"Rows with 24:00 time: {midnight_24_count}")

    print("\nMissing and negative pollutant check:")

    for col in POLLUTANT_COLUMNS:
        if col not in columns:
            print(f"SKIPPED missing column: {col}")
            continue

        result = con.execute(
            f"""
            SELECT
                COUNT(*) AS total_rows,
                COUNT(TRY_CAST("{col}" AS DOUBLE)) AS valid_readings,
                COUNT(*) - COUNT(TRY_CAST("{col}" AS DOUBLE)) AS missing_readings,
                SUM(
                    CASE
                        WHEN TRY_CAST("{col}" AS DOUBLE) < 0 THEN 1
                        ELSE 0
                    END
                ) AS negative_readings,
                MIN(TRY_CAST("{col}" AS DOUBLE)) AS min_value,
                MAX(TRY_CAST("{col}" AS DOUBLE)) AS max_value
            FROM raw_data;
            """
        ).fetchdf()

        print(f"\n{col}")
        print(result.to_string(index=False))


def main() -> None:
    csv_files = sorted(RAW_BASE.glob("year=*/london_bloomsbury_*.csv"))

    if not csv_files:
        raise FileNotFoundError(
            f"No CSV files found under {RAW_BASE}. Check file names and folders."
        )

    con = duckdb.connect()

    for csv_file in csv_files:
        inspect_file(con, csv_file)

    con.close()

    print("\nRaw inspection completed for all available years.")


if __name__ == "__main__":
    main()