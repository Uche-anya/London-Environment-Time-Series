from pathlib import Path

import duckdb


RAW_BASE = Path("data/raw/defra/london_bloomsbury")
BRONZE_BASE = Path("data/bronze/air_quality")


def create_bronze_air_quality() -> None:
    BRONZE_BASE.mkdir(parents=True, exist_ok=True)

    csv_files = sorted(RAW_BASE.glob("year=*/london_bloomsbury_*.csv"))

    if not csv_files:
        raise FileNotFoundError(
            f"No CSV files found under {RAW_BASE}. "
            "Check your folder names and CSV filenames."
        )

    con = duckdb.connect()

    for csv_file in csv_files:
        year = csv_file.parent.name.replace("year=", "")

        output_dir = BRONZE_BASE / f"year={year}"
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = output_dir / f"bronze_air_quality_{year}.parquet"

        print(f"Reading raw CSV: {csv_file}")
        print(f"Writing bronze Parquet: {output_file}")

        con.execute(
            f"""
            COPY (
                SELECT
                    *,
                    'London Bloomsbury' AS site_name,
                    {int(year)} AS source_year,
                    '{csv_file.name}' AS source_file
                FROM read_csv_auto(
                    '{csv_file.as_posix()}',
                    skip=4,
                    header=true,
                    nullstr=['', ' ', 'NA', 'N/A'],
                    ignore_errors=true
                )
                WHERE Date IS NOT NULL
                  AND TRIM(CAST(Date AS VARCHAR)) <> ''
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

    con.close()

    print("Bronze air quality layer created successfully.")


if __name__ == "__main__":
    create_bronze_air_quality()