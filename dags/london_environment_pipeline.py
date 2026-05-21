from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator


DEFAULT_ARGS = {
    "owner": "uche",
    "depends_on_past": False,
    "retries": 1,
}

with DAG(
    dag_id="london_environment_timeseries_pipeline",
    description="London air quality and weather batch pipeline using S3, DuckDB, Parquet, GX Core, TimescaleDB and Grafana.",
    default_args=DEFAULT_ARGS,
    start_date=datetime(2025, 1, 1),
    schedule=None,
    catchup=False,
    tags=["air-quality", "duckdb", "gx", "timeseries"],
) as dag:

    extract_raw_s3 = BashOperator(
        task_id="extract_raw_s3",
        bash_command="cd /opt/airflow && python pipelines/extract_raw_s3.py",
    )

    extract_weather = BashOperator(
        task_id="extract_weather",
        bash_command="cd /opt/airflow && python pipelines/extract_weather.py",
    )

    create_bronze_air_quality = BashOperator(
        task_id="create_bronze_air_quality",
        bash_command="cd /opt/airflow && python pipelines/create_bronze_air_quality.py",
    )

    create_bronze_weather = BashOperator(
        task_id="create_bronze_weather",
        bash_command="cd /opt/airflow && python pipelines/create_bronze_weather.py",
    )

    create_silver_air_quality = BashOperator(
        task_id="create_silver_air_quality",
        bash_command="cd /opt/airflow && python pipelines/create_silver_air_quality.py",
    )

    create_silver_weather = BashOperator(
        task_id="create_silver_weather",
        bash_command="cd /opt/airflow && python pipelines/create_silver_weather.py",
    )

    create_gold = BashOperator(
        task_id="create_gold",
        bash_command="cd /opt/airflow && python pipelines/create_gold.py",
    )

    validate_gold_with_gx = BashOperator(
        task_id="validate_gold_with_gx",
        bash_command="cd /opt/airflow && python data_quality/validate_gold_gx.py",
    )

    create_timescale_tables = BashOperator(
        task_id="create_timescale_tables",
        bash_command="cd /opt/airflow && python pipelines/create_timescale_tables.py",
    )

    load_gold_to_timescale = BashOperator(
        task_id="load_gold_to_timescale",
        bash_command="cd /opt/airflow && python pipelines/load_gold_to_timescale.py",
    )

    extract_raw_s3 >> create_bronze_air_quality >> create_silver_air_quality

    extract_weather >> create_bronze_weather >> create_silver_weather

    [create_silver_air_quality, create_silver_weather] >> create_gold
    create_gold >> validate_gold_with_gx >> create_timescale_tables >> load_gold_to_timescale