from datetime import datetime, timedelta
import sys
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from data_quality.validate_gold_gx import main as validate_gold_with_gx_main
from pipelines.create_bronze_air_quality import create_bronze_air_quality
from pipelines.create_bronze_weather import create_bronze_weather
from pipelines.create_gold import main as create_gold_main
from pipelines.create_silver_air_quality import create_silver_air_quality
from pipelines.create_silver_weather import create_silver_weather
from pipelines.create_timescale_tables import main as create_timescale_tables_main
from pipelines.extract_raw_s3 import main as extract_raw_s3_main
from pipelines.extract_weather import main as extract_weather_main
from pipelines.load_gold_to_timescale import main as load_gold_to_timescale_main


def run_pipeline(task_callable):
    """Execute a pipeline task from the project root so relative paths resolve correctly."""
    import os

    os.chdir(PROJECT_ROOT)
    sys.path.append(str(PROJECT_ROOT))
    task_callable()


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
        op_kwargs={"task_callable": extract_raw_s3_main},
    )

    extract_weather = PythonOperator(
        task_id="extract_weather",
        python_callable=run_pipeline,
        op_kwargs={"task_callable": extract_weather_main},
    )

    create_bronze_air_quality = PythonOperator(
        task_id="create_bronze_air_quality",
        python_callable=run_pipeline,
        op_kwargs={"task_callable": create_bronze_air_quality},
    )

    create_bronze_weather = PythonOperator(
        task_id="create_bronze_weather",
        python_callable=run_pipeline,
        op_kwargs={"task_callable": create_bronze_weather},
    )

    create_silver_air_quality = PythonOperator(
        task_id="create_silver_air_quality",
        python_callable=run_pipeline,
        op_kwargs={"task_callable": create_silver_air_quality},
    )

    create_silver_weather = PythonOperator(
        task_id="create_silver_weather",
        python_callable=run_pipeline,
        op_kwargs={"task_callable": create_silver_weather},
    )

    create_gold = PythonOperator(
        task_id="create_gold",
        python_callable=run_pipeline,
        op_kwargs={"task_callable": create_gold_main},
    )

    validate_gold_with_gx = PythonOperator(
        task_id="validate_gold_with_gx",
        python_callable=run_pipeline,
        op_kwargs={"task_callable": validate_gold_with_gx_main},
    )

    create_timescale_tables = PythonOperator(
        task_id="create_timescale_tables",
        python_callable=run_pipeline,
        op_kwargs={"task_callable": create_timescale_tables_main},
    )

    load_gold_to_timescale = PythonOperator(
        task_id="load_gold_to_timescale",
        python_callable=run_pipeline,
        op_kwargs={"task_callable": load_gold_to_timescale_main},
    )

    extract_raw_s3 >> create_bronze_air_quality >> create_silver_air_quality

    extract_weather >> create_bronze_weather >> create_silver_weather

    [create_silver_air_quality, create_silver_weather] >> create_gold
    create_gold >> validate_gold_with_gx >> create_timescale_tables >> load_gold_to_timescale