# London Environmental Time-Series Pipeline

A production-style batch data engineering pipeline for analysing London Bloomsbury air-quality and weather data from 2022 to 2025.

The project uses Airflow to orchestrate the pipeline, S3 as the raw data source for DEFRA air-quality CSV files, Open-Meteo for historical weather extraction, DuckDB for transformations, Parquet for bronze/silver/gold storage, GX Core for data quality validation, TimescaleDB as the serving layer, and Grafana for dashboarding.

The project was first built and tested locally with Astro Airflow and Docker, then extended with Terraform-managed AWS infrastructure and GitHub Actions CI.

---

## Project Status

Current implementation:

- DEFRA air-quality CSVs stored in an AWS S3 raw bucket
- Airflow task syncs raw DEFRA files from S3 into the local pipeline runtime
- Open-Meteo historical weather data extracted from API year by year
- Bronze, silver and gold layers created with DuckDB and Parquet
- Negative pollutant readings cleaned to `NULL` in the silver layer
- GX Core validates gold outputs before loading
- TimescaleDB stores dashboard-ready metrics
- Grafana visualises pollution, weather and data quality metrics
- Terraform provisions AWS S3 and EC2 infrastructure
- GitHub Actions CI runs dependency install, Python compilation and pytest checks
- Airflow DAG runs successfully end-to-end locally

Planned next step:

- Deploy the Astro/Docker stack to the Terraform-provisioned EC2 instance
- Add GitHub Actions CD to deploy from `main` to EC2

---

## Architecture

```text
DEFRA CSV files
    ↓
AWS S3 raw bucket
    ↓
Airflow task: extract/sync raw data from S3
    ↓
data/raw/defra/
    ↓
Bronze air-quality Parquet
    ↓
Silver air-quality Parquet

Open-Meteo API
    ↓
Airflow task: extract weather data
    ↓
data/raw/open_meteo/
    ↓
Bronze weather Parquet
    ↓
Silver weather Parquet

Silver air quality + Silver weather
    ↓
Gold metrics
    ↓
GX Core validation
    ↓
TimescaleDB
    ↓
Grafana dashboard

| Layer            | Tool                         |
| ---------------- | ---------------------------- |
| Orchestration    | Apache Airflow via Astro CLI |
| Raw storage      | AWS S3                       |
| Transformation   | DuckDB                       |
| File format      | Parquet                      |
| Data quality     | GX Core                      |
| Serving database | TimescaleDB / PostgreSQL     |
| Dashboarding     | Grafana                      |
| Infrastructure   | Terraform                    |
| Containerisation | Docker / Astro               |
| CI               | GitHub Actions               |
| Testing          | pytest                       |


Data Sources
DEFRA UK-AIR

The air-quality data comes from DEFRA UK-AIR monitoring files for the London Bloomsbury station.

The project processes hourly readings for:

NO
NO₂
NOx
O₃
PM10
PM2.5
SO₂

The implemented scope currently covers:

2022
2023
2024
2025

The raw DEFRA files are stored in S3 using this structure:

s3://london-environment-bucket-98/raw/defra/london_bloomsbury/year=2022/london_bloomsbury_2022.csv
s3://london-environment-bucket-98/raw/defra/london_bloomsbury/year=2023/london_bloomsbury_2023.csv
s3://london-environment-bucket-98/raw/defra/london_bloomsbury/year=2024/london_bloomsbury_2024.csv
s3://london-environment-bucket-98/raw/defra/london_bloomsbury/year=2025/london_bloomsbury_2025.csv

Airflow downloads these files into:

data/raw/defra/london_bloomsbury/year=2022/
data/raw/defra/london_bloomsbury/year=2023/
data/raw/defra/london_bloomsbury/year=2024/
data/raw/defra/london_bloomsbury/year=2025/
Open-Meteo Historical Weather API

Open-Meteo is used to extract historical hourly weather data for London.

The weather variables include:

Temperature
Relative humidity
Precipitation
Mean sea-level pressure
Wind speed

Weather data is saved year by year:

data/raw/open_meteo/year=2022/london_weather_2022.json
data/raw/open_meteo/year=2023/london_weather_2023.json
data/raw/open_meteo/year=2024/london_weather_2024.json
data/raw/open_meteo/year=2025/london_weather_2025.json

This structure makes the pipeline easier to extend later when 2026 data is added.

Medallion Layers
Raw Layer

Raw data is kept as close to the source format as possible.

data/raw/

DEFRA files arrive as CSVs from S3. Open-Meteo data is extracted as JSON from the API.

Bronze Layer

The bronze layer converts raw source files into Parquet while keeping most source fields intact.

data/bronze/air_quality/
data/bronze/weather/

For air quality, the bronze layer reads the raw DEFRA CSVs and adds lineage columns:

site_name
source_year
source_file

For weather, the Open-Meteo nested JSON is flattened into hourly rows before being written as Parquet.

Silver Layer

The silver layer cleans and standardises the data.

data/silver/air_quality/
data/silver/weather/

For air quality, the wide DEFRA format is converted into a long format:

recorded_at
site_name
pollutant
value
unit
year
source_file

Cleaning rules include:

Blank pollutant readings become NULL
Invalid numeric values become NULL
Negative pollutant readings become NULL
Valid zero readings are kept as 0
Gold Layer

The gold layer creates analytics-ready outputs.

data/gold/

Gold outputs include:

daily_air_quality_metrics.parquet
daily_weather_metrics.parquet
hourly_environment_metrics.parquet

These files are then validated and loaded into TimescaleDB.

Airflow DAG

The main DAG is:

london_environment_timeseries_pipeline

The DAG runs the full batch workflow:

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

The DAG is scheduled as a weekly batch pipeline:

schedule="0 6 * * 1"
catchup=False
max_active_runs=1

This means the DAG runs every Monday at 6am, does not backfill missed historical runs, and prevents overlapping runs.

The DAG can also be triggered manually from the Airflow UI.

S3 Integration

S3 is used as the production-style raw zone for DEFRA CSV files.

The S3 bucket is provisioned with Terraform:

london-environment-bucket-98

The Airflow task extract_raw_s3 downloads the raw files from S3 into the local runtime folder:

data/raw/defra/london_bloomsbury/

This keeps the bronze air-quality script simple. It does not read directly from S3. Instead, the pipeline uses this pattern:

S3 raw bucket
    ↓
extract_raw_s3.py
    ↓
data/raw/
    ↓
create_bronze_air_quality.py

This makes the project easier to debug locally and easier to deploy on EC2 later.

Data Quality

GX Core validates the gold layer before loading into TimescaleDB.

The validation checks include:

Required columns are present
Important fields are not null
Pollutant values are within expected categories
Completeness percentages are between 0 and 100
Valid reading counts do not exceed expected reading counts
Weather join quality is checked in the hourly environment table

The pipeline keeps missing readings as NULL instead of replacing them with zero. This avoids creating misleading pollution values.

TimescaleDB Serving Layer

TimescaleDB is used as the serving database for Grafana.

The pipeline creates and loads these tables:

daily_air_quality_metrics
daily_weather_metrics
hourly_environment_metrics

The load process uses upsert logic, so rerunning the pipeline does not duplicate rows.

The behaviour is:

New row      → inserted
Existing row → updated
Duplicate row → not created

This makes the pipeline safe to rerun.

Grafana Dashboard

Grafana connects to TimescaleDB and visualises the final gold metrics.

The dashboard includes:

Average NO₂
Peak NO₂
Average PM2.5
Average wind speed
Daily pollution trend
Daily average temperature
Highest key pollution day
Completeness metrics

The dashboard JSON is exported and stored in the repo under:

grafana/
Terraform Infrastructure

Terraform currently provisions the AWS infrastructure required for the production version.

Resources created:

S3 bucket for raw data
S3 public access block
S3 versioning
S3 server-side encryption
IAM role for EC2
IAM policy allowing EC2 to read from S3
IAM instance profile
EC2 instance
Security group
Elastic IP

Terraform outputs:

s3_bucket_name
s3_bucket_arn
ec2_public_ip
airflow_url
grafana_url

Example output:

airflow_url = "http://13.63.212.99:8080"
grafana_url = "http://13.63.212.99:3000"
s3_bucket_name = "london-environment-bucket-98"

The EC2 instance is intended to host:

Astro Airflow
TimescaleDB
Grafana
The pipeline code
Why Elastic IP?

An Elastic IP gives the EC2 instance a stable public IP address.

This matters because GitHub Actions will later SSH into the EC2 instance during deployment.

Without an Elastic IP, stopping and starting the EC2 instance could change the public IP, breaking:

SSH commands
GitHub Actions deployment secrets
Airflow URL
Grafana URL
Why IAM Role?

The EC2 IAM role allows Airflow to read from S3 without hardcoding AWS credentials.

Locally, boto3 can use AWS CLI credentials.
On EC2, boto3 will use the instance role automatically.

This avoids putting these values in .env:

AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY

The EC2 role only needs read access to the raw S3 bucket.

CI with GitHub Actions

The project includes a GitHub Actions CI workflow.

The CI runs on:

push to dev
push to main
pull request into main

The CI workflow does:

Checkout repository
Set up Python 3.11
Install dependencies
Compile Python files
Run pytest

The compile step checks for basic Python syntax errors in:

dags/
pipelines/
src/
data_quality/
tests/

The pytest step currently checks:

Required project files exist
Pollutant cleaning logic behaves correctly

Current pytest result:

2 passed

This gives a basic safety net before changes are merged or deployed.

Branch Strategy

The project uses:

dev  → active development branch
main → production branch

Recommended workflow:

Work locally
    ↓
Push to dev
    ↓
GitHub Actions CI runs
    ↓
Open pull request dev → main
    ↓
CI runs again
    ↓
Merge into main
    ↓
Deployment workflow deploys to EC2

The deployment workflow is planned as the next step.

CI/CD Strategy

The project separates code deployment from data processing.

GitHub Actions = code validation and deployment
Airflow        = batch data processing
Terraform      = cloud infrastructure
S3             = raw data storage
TimescaleDB    = serving layer
Grafana        = visualisation

The best production pattern for this project is:

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

The DAG is not automatically triggered after every deployment by default. Airflow controls pipeline execution through schedule or manual trigger.

Running Locally

Start the Astro/Airflow environment:

astro dev start

Open Airflow:

http://localhost:8080

Open Grafana:

http://localhost:3000

Run the DAG from the Airflow UI:

london_environment_timeseries_pipeline
Useful Local Commands

Run tests:

pytest

Compile Python files:

python -m compileall dags pipelines src data_quality tests

Run Terraform:

cd terraform
terraform fmt
terraform validate
terraform plan
terraform apply

Check S3 files:

aws s3 ls s3://london-environment-bucket-98/raw/defra/london_bloomsbury/ --recursive

Run weather extraction manually:

python pipelines/extract_weather.py

Run bronze weather manually:

python pipelines/create_bronze_weather.py
Environment Variables

Example .env values:

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

Do not commit .env to GitHub.

Files Not Committed

The following should stay out of GitHub:

.env
.venv/
data/raw/
data/bronze/
data/silver/
data/gold/
terraform/terraform.tfvars
terraform/*.tfstate
terraform/.terraform/

The repo should contain code, configuration templates and infrastructure code, not generated data outputs or secrets.

Future Improvements

Planned improvements:

Add GitHub Actions CD to deploy main to EC2
Move from manual EC2 setup to fully automated deployment
Add optional workflow dispatch for controlled manual deployment
Add more pytest coverage for timestamp parsing and weather JSON validation
Store bronze/silver/gold Parquet outputs in S3
Add alerting for failed Airflow DAG runs
Add Grafana provisioning for dashboards and data sources
Add 2026 data as a current-year batch update
Package reusable pipeline logic as a Python module or wheel if the codebase grows
Project Summary

This project demonstrates a practical batch data engineering platform using modern tools.

It shows how raw environmental data can be stored in S3, orchestrated with Airflow, transformed with DuckDB, validated with GX Core, loaded into TimescaleDB, and visualised in Grafana.

The current version runs successfully locally and has been extended with Terraform-managed AWS infrastructure and GitHub Actions CI. The next step is production deployment to EC2 using GitHub Actions CD.