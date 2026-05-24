# London Environmental Time-Series Pipeline

A production-style batch data engineering pipeline for analysing London Bloomsbury air-quality and weather data from 2022 to 2025.

This project uses AWS S3, Apache Airflow, DuckDB, Parquet, GX Core, TimescaleDB, Grafana, Terraform and GitHub Actions to build a realistic batch data engineering workflow. Raw environmental data is ingested, transformed through medallion layers, validated, loaded into a serving database and visualised in Grafana.

The project was first built and tested locally using Astro Airflow and Docker. It has now been extended with Terraform-managed AWS infrastructure and GitHub Actions CI.

---

## Project Status

The current implementation includes:

- DEFRA air-quality CSV files stored in AWS S3
- Airflow task to sync raw DEFRA files from S3 into the local runtime
- Open-Meteo historical weather extraction
- Bronze, silver and gold medallion layers using DuckDB and Parquet
- Cleaning logic for missing, invalid and negative pollutant readings
- GX Core validation before loading data into the serving layer
- TimescaleDB tables for dashboard-ready metrics
- Grafana dashboard for air-quality, weather and completeness metrics
- Terraform infrastructure for S3, EC2, IAM, security group and Elastic IP
- GitHub Actions CI for dependency installation, Python compilation and tests
- Successful local end-to-end DAG execution

The next planned step is to deploy the Astro/Docker stack to the Terraform-provisioned EC2 instance and add GitHub Actions CD for deployment from `main`.

---

## Architecture

```text
DEFRA CSV files
        ↓
AWS S3 raw bucket
        ↓
Airflow extracts/syncs raw files from S3
        ↓
Raw layer
        ↓
Bronze air-quality Parquet
        ↓
Silver air-quality Parquet
        ↓
Gold air-quality metrics
        ↓
GX Core validation
        ↓
TimescaleDB
        ↓
Grafana


Open-Meteo API
        ↓
Airflow extracts historical weather data
        ↓
Raw weather JSON
        ↓
Bronze weather Parquet
        ↓
Silver weather Parquet
        ↓
Gold weather and joined environment metrics
        ↓
GX Core validation
        ↓
TimescaleDB
        ↓
Grafana
```

---

## Tech Stack

| Area | Tool |
|---|---|
| Orchestration | Apache Airflow via Astro CLI |
| Raw Storage | AWS S3 |
| Transformation | DuckDB |
| File Format | Parquet |
| Data Quality | GX Core |
| Serving Layer | TimescaleDB / PostgreSQL |
| Dashboarding | Grafana |
| Infrastructure | Terraform |
| Containerisation | Docker / Astro |
| CI | GitHub Actions |
| Testing | pytest |

---

## Data Sources

### DEFRA UK-AIR

The air-quality data comes from DEFRA UK-AIR monitoring files for the London Bloomsbury station.

The project currently processes hourly readings for:

- NO
- NO₂
- NOx
- O₃
- PM10
- PM2.5
- SO₂

The current year range is:

- 2022
- 2023
- 2024
- 2025

Raw DEFRA files are stored in S3 using this structure:

```text
s3://london-environment-bucket-98/raw/defra/london_bloomsbury/year=2022/london_bloomsbury_2022.csv
s3://london-environment-bucket-98/raw/defra/london_bloomsbury/year=2023/london_bloomsbury_2023.csv
s3://london-environment-bucket-98/raw/defra/london_bloomsbury/year=2024/london_bloomsbury_2024.csv
s3://london-environment-bucket-98/raw/defra/london_bloomsbury/year=2025/london_bloomsbury_2025.csv
```

Airflow downloads these files into:

```text
data/raw/defra/london_bloomsbury/year=2022/
data/raw/defra/london_bloomsbury/year=2023/
data/raw/defra/london_bloomsbury/year=2024/
data/raw/defra/london_bloomsbury/year=2025/
```

### Open-Meteo Historical Weather API

Open-Meteo is used to extract historical hourly weather data for London.

The weather variables include:

- Temperature
- Relative humidity
- Precipitation
- Mean sea-level pressure
- Wind speed

Weather data is saved year by year:

```text
data/raw/open_meteo/year=2022/london_weather_2022.json
data/raw/open_meteo/year=2023/london_weather_2023.json
data/raw/open_meteo/year=2024/london_weather_2024.json
data/raw/open_meteo/year=2025/london_weather_2025.json
```

This structure makes it easier to add future years without changing the full pipeline design.

---

## Medallion Architecture

The project follows a medallion architecture:

```text
Raw → Bronze → Silver → Gold
```

### Raw Layer

The raw layer stores source data as close to the original format as possible.

```text
data/raw/
```

DEFRA data arrives as CSV files from S3.

Open-Meteo data is extracted as JSON from the API.

---

### Bronze Layer

The bronze layer converts raw source files into Parquet while keeping most of the original structure.

```text
data/bronze/air_quality/
data/bronze/weather/
```

For air quality, the bronze process reads the raw DEFRA CSV files and adds lineage columns such as:

- `site_name`
- `source_year`
- `source_file`

For weather, the Open-Meteo JSON is flattened into hourly rows and written as Parquet.

---

### Silver Layer

The silver layer cleans, standardises and reshapes the data.

```text
data/silver/air_quality/
data/silver/weather/
```

For air quality, the original wide DEFRA format is converted into a long analytical format:

```text
recorded_at
site_name
pollutant
value
unit
year
source_file
```

Cleaning rules include:

- Blank pollutant readings are converted to `NULL`
- Invalid numeric values are converted to `NULL`
- Negative pollutant readings are converted to `NULL`
- Valid zero readings are kept as `0`

Missing readings are not replaced with zero because that would create misleading pollution values.

---

### Gold Layer

The gold layer creates analytics-ready datasets.

```text
data/gold/
```

Gold outputs include:

```text
daily_air_quality_metrics.parquet
daily_weather_metrics.parquet
hourly_environment_metrics.parquet
```

These outputs are validated with GX Core before being loaded into TimescaleDB.

---

## Airflow DAG

The main DAG is:

```text
london_environment_timeseries_pipeline
```

The DAG runs the full batch workflow:

```text
extract_raw_s3
    ↓
create_bronze_air_quality
    ↓
create_silver_air_quality

extract_weather
    ↓
create_bronze_weather
    ↓
create_silver_weather

create_silver_air_quality + create_silver_weather
    ↓
create_gold
    ↓
validate_gold_with_gx
    ↓
create_timescale_tables
    ↓
load_gold_to_timescale
```

The DAG is scheduled as a weekly batch pipeline:

```python
schedule="0 6 * * 1"
catchup=False
max_active_runs=1
```

This means:

- The DAG runs every Monday at 6am
- Missed historical runs are not backfilled automatically
- Only one active run is allowed at a time

The DAG can also be triggered manually from the Airflow UI.

---

## S3 Integration

S3 is used as the production-style raw zone for DEFRA CSV files.

The S3 bucket is provisioned with Terraform:

```text
london-environment-bucket-98
```

The Airflow task `extract_raw_s3` downloads raw files from S3 into the local runtime folder:

```text
data/raw/defra/london_bloomsbury/
```

The pipeline uses this pattern:

```text
S3 raw bucket
        ↓
extract_raw_s3.py
        ↓
data/raw/
        ↓
create_bronze_air_quality.py
```

This keeps the bronze script simple because it reads from local files rather than directly from S3. It also makes the project easier to debug locally and easier to deploy later on EC2.

---

## Data Quality

GX Core is used to validate the gold layer before loading data into TimescaleDB.

Validation checks include:

- Required columns are present
- Important fields are not null
- Pollutant values are within expected categories
- Completeness percentages are between 0 and 100
- Valid reading counts do not exceed expected reading counts
- Weather join quality is checked in the hourly environment table

This creates a quality gate before data reaches the serving layer.

---

## TimescaleDB Serving Layer

TimescaleDB is used as the serving database for Grafana.

The pipeline creates and loads these tables:

```text
daily_air_quality_metrics
daily_weather_metrics
hourly_environment_metrics
```

The load process uses upsert logic, so rerunning the pipeline does not duplicate rows.

The behaviour is:

```text
New row       → inserted
Existing row  → updated
Duplicate row → not created
```

This makes the pipeline safe to rerun.

---

## Grafana Dashboard

Grafana connects to TimescaleDB and visualises the final gold metrics.

The dashboard includes:

- Average NO₂
- Peak NO₂
- Average PM2.5
- Average wind speed
- Daily pollution trend
- Daily average temperature
- Highest key pollution day
- Completeness metrics

The dashboard JSON is exported and stored in the repository under:

```text
grafana/
```

---

## Terraform Infrastructure

Terraform provisions the AWS infrastructure required for the production-style version of the project.

Resources created include:

- S3 bucket for raw data
- S3 public access block
- S3 versioning
- S3 server-side encryption
- IAM role for EC2
- IAM policy allowing EC2 to read from S3
- IAM instance profile
- EC2 instance
- Security group
- Elastic IP

Terraform outputs include:

```text
s3_bucket_name
s3_bucket_arn
ec2_public_ip
airflow_url
grafana_url
```

Example output:

```text
airflow_url = "http://13.63.212.99:8080"
grafana_url = "http://13.63.212.99:3000"
s3_bucket_name = "london-environment-bucket-98"
```

The EC2 instance is intended to host:

- Astro Airflow
- TimescaleDB
- Grafana
- The pipeline code

---

## Why Elastic IP Is Used

An Elastic IP gives the EC2 instance a stable public IP address.

This matters because GitHub Actions will later SSH into the EC2 instance during deployment.

Without an Elastic IP, stopping and starting the EC2 instance could change the public IP and break:

- SSH commands
- GitHub Actions deployment secrets
- Airflow URL
- Grafana URL

---

## Why IAM Role Is Used

The EC2 IAM role allows Airflow to read from S3 without hardcoding AWS credentials.

Locally, `boto3` can use AWS CLI credentials.

On EC2, `boto3` can use the EC2 instance role automatically.

This avoids putting these values in `.env`:

```text
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
```

The EC2 role only needs read access to the raw S3 bucket.

---

## CI with GitHub Actions

The project includes a GitHub Actions CI workflow.

The CI runs on:

- Push to `dev`
- Push to `main`
- Pull request into `main`

The workflow does the following:

1. Checks out the repository
2. Sets up Python 3.11
3. Installs dependencies
4. Compiles Python files
5. Runs pytest

The compile step checks for basic Python syntax errors in:

```text
dags/
pipelines/
src/
data_quality/
tests/
```

The pytest step currently checks:

- Required project files exist
- Pollutant cleaning logic behaves correctly

Current pytest result:

```text
2 passed
```

This gives the project a basic safety net before changes are merged or deployed.

---

## Branch Strategy

The project uses:

```text
dev  → active development branch
main → production branch
```

Recommended workflow:

```text
Work locally
        ↓
Push to dev
        ↓
GitHub Actions CI runs
        ↓
Open pull request from dev to main
        ↓
CI runs again
        ↓
Merge into main
        ↓
Deployment workflow deploys to EC2
```

The deployment workflow is planned as the next step.

---

## CI/CD Strategy

The project separates code deployment from data processing.

```text
GitHub Actions = code validation and deployment
Airflow        = batch data processing
Terraform      = cloud infrastructure
S3             = raw data storage
TimescaleDB    = serving layer
Grafana        = visualisation
```

The intended production pattern is:

```text
Code change
        ↓
GitHub Actions CI
        ↓
Merge to main
        ↓
GitHub Actions CD deploys to EC2
        ↓
Airflow platform is updated

Scheduled/manual Airflow run
        ↓
S3 + API extraction
        ↓
Bronze/silver/gold
        ↓
GX validation
        ↓
TimescaleDB
        ↓
Grafana
```

The DAG is not automatically triggered after every deployment by default. Airflow controls pipeline execution through its schedule or through a manual trigger.

---

## Running Locally

Start the Astro/Airflow environment:

```bash
astro dev start
```

Open Airflow:

```text
http://localhost:8080
```

Open Grafana:

```text
http://localhost:3000
```

Run the DAG from the Airflow UI:

```text
london_environment_timeseries_pipeline
```

---

## Useful Commands

Run tests:

```bash
pytest
```

Compile Python files:

```bash
python -m compileall dags pipelines src data_quality tests
```

Run Terraform:

```bash
cd terraform
terraform fmt
terraform validate
terraform plan
terraform apply
```

Check S3 files:

```bash
aws s3 ls s3://london-environment-bucket-98/raw/defra/london_bloomsbury/ --recursive
```

Run weather extraction manually:

```bash
python pipelines/extract_weather.py
```

Run bronze weather manually:

```bash
python pipelines/create_bronze_weather.py
```

---

## Environment Variables

Example `.env` values:

```env
CITY=London
SITE_NAME=London Bloomsbury
LATITUDE=51.5072
LONGITUDE=-0.1276
START_DATE=2022-01-01
END_DATE=2025-12-31
TIMEZONE=Europe/London

AWS_REGION=eu-north-1
S3_BUCKET=london-environment-bucket-98
S3_RAW_PREFIX=raw
LOCAL_RAW_DIR=data/raw
DEFRA_SITE_FOLDER=defra/london_bloomsbury
YEARS=2022,2023,2024,2025

POSTGRES_USER=uche
POSTGRES_PASSWORD=change-this-password
POSTGRES_DB=environment_db
POSTGRES_HOST=timescaledb
POSTGRES_PORT=5432

GF_SECURITY_ADMIN_USER=admin
GF_SECURITY_ADMIN_PASSWORD=change-this-password
```

Do not commit `.env` to GitHub.

---

## Files Not Committed

The following should stay out of GitHub:

```text
.env
.venv/
data/raw/
data/bronze/
data/silver/
data/gold/
terraform/terraform.tfvars
terraform/*.tfstate
terraform/.terraform/
```

The repository should contain code, configuration templates and infrastructure code, not generated data outputs or secrets.

---

## Future Improvements

Planned improvements include:

- Add GitHub Actions CD to deploy `main` to EC2
- Move from manual EC2 setup to fully automated deployment
- Add optional `workflow_dispatch` for controlled manual deployment
- Add more pytest coverage for timestamp parsing and weather JSON validation
- Store bronze, silver and gold Parquet outputs in S3
- Add alerting for failed Airflow DAG runs
- Add Grafana provisioning for dashboards and data sources
- Add 2026 data as a current-year batch update
- Package reusable pipeline logic as a Python module if the codebase grows

---

## Project Summary

This project demonstrates a practical batch data engineering platform using modern tools.

It shows how raw environmental data can be stored in S3, orchestrated with Airflow, transformed with DuckDB, validated with GX Core, loaded into TimescaleDB, and visualised in Grafana.

The current version runs successfully locally and has been extended with Terraform-managed AWS infrastructure and GitHub Actions CI. The next step is production deployment to EC2 using GitHub Actions CD.
