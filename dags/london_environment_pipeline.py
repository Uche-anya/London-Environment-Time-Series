from datetime import datetime, timedelta
import importlib
import os
import sys
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run_pipeline(module_name: str, callable_name: str) -> None:
   
    os.chdir(PROJECT_ROOT)
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.append(str(PROJECT_ROOT))

    module = importlib.import_module(module_name)
    getattr(module, callable_name)()


DEFAULT_ARGS = {
    "owner": "uche",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": False,
}

with DAG(
    dag_id="london_environment_timeseries_pipeline",
    description="London air quality and weather batch pipeline using S3, DuckDB, Parquet, GX Core, TimescaleDB and Grafana.",
    default_args=DEFAULT_ARGS,
    start_date=datetime(2025, 1, 1),
    schedule="0 6 * * 1",
    catchup=False,
    max_active_runs=1,
    tags=["air-quality", "weather", "s3", "duckdb", "gx", "timeseries"],
) as dag:

    extract_raw_s3 = PythonOperator(
        task_id="extract_raw_s3",
        python_callable=run_pipeline,
        op_kwargs={"module_name": "pipelines.extract_raw_s3", "callable_name": "main"},
    )

    extract_weather = PythonOperator(
        task_id="extract_weather",
        python_callable=run_pipeline,
        op_kwargs={"module_name": "pipelines.extract_weather", "callable_name": "main"},
    )

    create_bronze_air_quality = PythonOperator(
        task_id="create_bronze_air_quality",
        python_callable=run_pipeline,
        op_kwargs={
            "module_name": "pipelines.create_bronze_air_quality",
            "callable_name": "create_bronze_air_quality",
        },
    )

    create_bronze_weather = PythonOperator(
        task_id="create_bronze_weather",
        python_callable=run_pipeline,
        op_kwargs={
            "module_name": "pipelines.create_bronze_weather",
            "callable_name": "create_bronze_weather",
        },
    )

    create_silver_air_quality = PythonOperator(
        task_id="create_silver_air_quality",
        python_callable=run_pipeline,
        op_kwargs={
            "module_name": "pipelines.create_silver_air_quality",
            "callable_name": "create_silver_air_quality",
        },
    )

    create_silver_weather = PythonOperator(
        task_id="create_silver_weather",
        python_callable=run_pipeline,
        op_kwargs={
            "module_name": "pipelines.create_silver_weather",
            "callable_name": "create_silver_weather",
        },
    )

    create_gold = PythonOperator(
        task_id="create_gold",
        python_callable=run_pipeline,
        op_kwargs={"module_name": "pipelines.create_gold", "callable_name": "main"},
    )

    validate_gold_with_gx = PythonOperator(
        task_id="validate_gold_with_gx",
        python_callable=run_pipeline,
        op_kwargs={
            "module_name": "data_quality.validate_gold_gx",
            "callable_name": "main",
        },
    )

    create_timescale_tables = PythonOperator(
        task_id="create_timescale_tables",
        python_callable=run_pipeline,
        op_kwargs={
            "module_name": "pipelines.create_timescale_tables",
            "callable_name": "create_tables",
        },
    )

    load_gold_to_timescale = PythonOperator(
        task_id="load_gold_to_timescale",
        python_callable=run_pipeline,
        op_kwargs={
            "module_name": "pipelines.load_gold_to_timescale",
            "callable_name": "main",
        },
    )

    extract_raw_s3 >> create_bronze_air_quality >> create_silver_air_quality

    extract_weather >> create_bronze_weather >> create_silver_weather

    [create_silver_air_quality, create_silver_weather] >> create_gold
    create_gold >> validate_gold_with_gx >> create_timescale_tables >> load_gold_to_timescale
