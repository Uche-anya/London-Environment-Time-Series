from pathlib import Path
import duckdb


SILVER_AIR_QUALITY_PATH = "data/silver/air_quality/year=*/silver_air_quality_*.parquet"
GOLD_AIR_QUALITY_BASE = Path("data/gold/daily_air_quality")


def create_gold_daily_air_quality() -> None:
    GOLD_AIR_QUALITY_BASE.mkdir(parents=True, exist_ok=True)

    output_file = GOLD_AIR_QUALITY_BASE / "daily_air_quality_metrics.parquet"

    con = duckdb.connect()

    print("Creating gold daily air quality metrics...")

    con.execute(
        f"""
        COPY (
            WITH silver AS (
                SELECT
                    CAST(recorded_at AS DATE) AS reading_date,
                    site_name,
                    pollutant,
                    value
                FROM read_parquet('{SILVER_AIR_QUALITY_PATH}')
            )

            SELECT
                reading_date,
                site_name,
                pollutant,

                AVG(value) AS avg_value,
                MIN(value) AS min_value,
                MAX(value) AS max_value,

                COUNT(value) AS valid_readings,
                COUNT(*) AS expected_readings,
                COUNT(*) - COUNT(value) AS missing_readings,

                ROUND(COUNT(value) * 100.0 / COUNT(*), 2) AS completeness_pct,

                EXTRACT(YEAR FROM reading_date) AS year,
                EXTRACT(MONTH FROM reading_date) AS month

            FROM silver

            GROUP BY
                reading_date,
                site_name,
                pollutant

            ORDER BY
                reading_date,
                pollutant
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

    print(f"Saved: {output_file}")
    print(f"Rows written: {row_count}")

    con.close()


if __name__ == "__main__":
    create_gold_daily_air_quality()