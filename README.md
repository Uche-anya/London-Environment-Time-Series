# London Environmental Time-Series Pipeline

A production-style batch data engineering pipeline for analysing London Bloomsbury air-quality and weather data from **2022 to the present**.

This project uses AWS S3, Apache Airflow (Astro), DuckDB, Parquet, GX Core, TimescaleDB, Grafana, Terraform and GitHub Actions to build a realistic batch data engineering workflow. Raw environmental data is ingested, transformed through medallion layers, validated, loaded into a serving database and visualised in Grafana.

The pipeline was first built and tested locally with Astro Airflow and Docker, then extended with Terraform-managed AWS infrastructure and GitHub Actions CI. It currently runs end-to-end and serves a full **2022 → present** history into TimescaleDB and Grafana.

---

## Project Status

**Working today (verified end-to-end locally):**

- DEFRA air-quality CSV files stored in AWS S3, synced into the runtime by Airflow
- Open-Meteo historical weather extraction
- Bronze, silver and gold medallion layers using DuckDB and Parquet
- Cleaning logic for missing, invalid and negative pollutant readings
- **Incremental, idempotent extraction** — a dynamic year range and a "frozen-tail" strategy so closed years aren't re-fetched
- GX Core validation with **data-driven (non-hardcoded) row-count expectations**
- TimescaleDB tables for dashboard-ready metrics, loaded with safe upserts
- Grafana dashboard for air-quality, weather and completeness metrics
- Terraform infrastructure for S3, EC2, IAM, security group and Elastic IP
- GitHub Actions CI (dependency install, Python compile, pytest)
- A successful full DAG run loading 2022 → 2026 into the serving layer

**Most recent serving-layer state:**

| Table | Rows | Date range |
|---|---|---|
| `daily_air_quality_metrics` | ~11,400 | 2022-01-01 → present |
| `daily_weather_metrics` | ~1,600 | 2022-01-01 → present |
| `hourly_environment_metrics` | ~272,000 | 2022-01-01 → present |

**Next major step:** deploy the Dockerised stack to the Terraform-provisioned EC2 instance and add GitHub Actions CD from `main`. See [Work To Be Done](#work-to-be-done).

---

## Architecture

```text
DEFRA CSV files                         Open-Meteo Historical API
        ↓                                         ↓
AWS S3 raw bucket                       Airflow extracts weather (JSON)
        ↓                                         ↓
Airflow syncs raw files (extract_raw_s3)   Raw weather JSON
        ↓                                         ↓
Raw layer (CSV)                          Bronze weather Parquet
        ↓                                         ↓
Bronze air-quality Parquet               Silver weather Parquet
        ↓                                         ↓
Silver air-quality Parquet  ─────────────────────┤
        ↓                                         │
        └──────────────┬──────────────────────────┘
                       ↓
              Gold metrics (daily AQ, daily weather, hourly joined)
                       ↓
              GX Core validation (quality gate)
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

Air-quality data comes from DEFRA UK-AIR monitoring files for the **London Bloomsbury** station ("All Hourly Pollutant Data, Column Format").

Pollutants processed (hourly):

- NO, NO₂, NOx, O₃, PM10, PM2.5, SO₂

**Year coverage is dynamic** — the pipeline ingests from the configured start year (`START_DATE`, currently 2022) through the **current calendar year**, so new years flow in automatically without code changes.

Raw DEFRA files are stored in S3:

```text
s3://<bucket>/raw/defra/london_bloomsbury/year=2022/london_bloomsbury_2022.csv
s3://<bucket>/raw/defra/london_bloomsbury/year=2023/london_bloomsbury_2023.csv
...
s3://<bucket>/raw/defra/london_bloomsbury/year=2026/london_bloomsbury_2026.csv
```

Airflow downloads them into a mirrored local structure under `data/raw/defra/london_bloomsbury/year=*/`.

### Open-Meteo Historical Weather API

Open-Meteo provides historical hourly weather for London:

- Temperature, relative humidity, precipitation, mean sea-level pressure, wind speed

Saved year by year:

```text
data/raw/open_meteo/year=2022/london_weather_2022.json
...
data/raw/open_meteo/year=2026/london_weather_2026.json
```

The Open-Meteo archive (ERA5) is published with a **~5-day lag**, so the current year is fetched only up to today's date.

---

## Medallion Architecture

```text
Raw → Bronze → Silver → Gold
```

### Raw
Source data kept close to original format (DEFRA CSV from S3, Open-Meteo JSON from the API).

### Bronze (`data/bronze/`)
Raw files converted to Parquet, keeping most of the original structure and adding lineage columns (`site_name`, `source_year`, `source_file`). Weather JSON is flattened into hourly rows.

### Silver (`data/silver/`)
Cleaned, standardised and reshaped. Air quality is pivoted from wide DEFRA format into a long analytical shape:

```text
recorded_at | site_name | pollutant | value | unit | year | source_file
```

Cleaning rules:

- Blank readings → `NULL`
- Invalid numeric values → `NULL`
- Negative readings → `NULL`
- Valid zero readings → kept as `0`

Missing readings are deliberately **not** replaced with zero (that would invent pollution data). The special DEFRA `24:00` timestamp is rolled to `00:00` of the next day.

### Gold (`data/gold/`)
Analytics-ready datasets:

```text
daily_air_quality_metrics.parquet
daily_weather_metrics.parquet
hourly_environment_metrics.parquet     (air quality enriched with weather)
```

These are validated with GX Core before loading into TimescaleDB.

---

## Incremental & Idempotent Design

The data has a specific shape: a large **frozen tail** (closed years that never change) and a small **moving head** (the current year, plus late-arriving / ratified data). The pipeline is built around that:

- **Dynamic year range** — extraction derives `START_YEAR … current_year` instead of a hardcoded list, so it never silently falls behind the calendar.
- **Frozen-tail weather extraction** — only the current and previous year are re-fetched each run; older years are fetched only if their output is missing (first-time backfill). This avoids hammering the free Open-Meteo API for data that can't change.
- **Incremental S3 sync** — DEFRA CSVs are skipped if a local copy already exists with a matching size. The growing current-year file changes size and re-downloads naturally.
- **Full-refresh transforms** — bronze → gold are rebuilt each run. At this data volume that is cheap and eliminates a whole class of incremental-merge bugs.
- **Idempotent load** — gold is upserted into TimescaleDB with `ON CONFLICT … DO UPDATE`, so re-running never duplicates rows:

  ```text
  New row       → inserted
  Existing row  → updated
  Duplicate row → not created
  ```

The whole DAG is therefore safe to re-run at any time.

---

## Airflow DAG

DAG id: `london_environment_timeseries_pipeline`

```text
extract_raw_s3 → create_bronze_air_quality → create_silver_air_quality ┐
                                                                        ├→ create_gold
extract_weather → create_bronze_weather → create_silver_weather ───────┘
        → validate_gold_with_gx → create_timescale_tables → load_gold_to_timescale
```

Schedule:

```python
schedule="0 6 * * 1"   # every Monday 06:00
catchup=False          # missed historical runs are not auto-backfilled
max_active_runs=1      # one run at a time
```

**Import-safety note:** task modules pull in heavy dependencies (DuckDB, Great Expectations, boto3). To keep DAG parsing fast and avoid the Airflow DagBag import timeout, the DAG imports task callables **lazily at execution time** (via `importlib` inside `run_pipeline`), not at the top of the file. Keep new top-level code in the DAG file minimal.

---

## Data Quality (GX Core)

GX Core validates the gold layer before it reaches the serving database. Checks include:

- Required columns present and key fields not null
- Pollutant values within the expected category set
- Completeness percentages between 0 and 100
- Valid reading counts never exceed expected reading counts
- Weather-join coverage on the hourly environment table

Row-count expectations are **derived from the data's own date span** (e.g. one row per date × site × pollutant) rather than hardcoded numbers, so they remain valid as new years are added while still catching missing days or duplicate-row explosions.

---

## TimescaleDB Serving Layer

TimescaleDB serves Grafana. Tables:

```text
daily_air_quality_metrics
daily_weather_metrics
hourly_environment_metrics   (TimescaleDB hypertable on recorded_at)
```

Tables and indexes are created by `pipelines/create_timescale_tables.py` (the runtime source of truth). `sql/timescale/create_table.sql` and `indexes.sql` mirror that DDL as a human-readable reference only — they are not executed by the pipeline.

---

## Grafana Dashboard

Grafana connects to TimescaleDB and visualises the gold metrics: average / peak NO₂, average PM2.5, average wind speed, daily pollution trend, daily average temperature, highest pollution day, and completeness metrics. The exported dashboard JSON lives under `grafana/`.

> Note: the Grafana datasource and imported dashboard currently live in the persisted `grafana_data` Docker volume, **not** in repo-managed provisioning files. See [Work To Be Done](#work-to-be-done).

---

## Terraform Infrastructure

Terraform provisions the AWS layer (`terraform/`):

- S3 bucket for raw data (versioned, AES256 encrypted, all public access blocked)
- IAM role + policy + instance profile letting EC2 **read S3 with no static keys**
- Security group (SSH 22, Airflow 8080, Grafana 3000 — restricted to `allowed_ip`)
- Ubuntu 22.04 EC2 instance (default `t3.small`, gp3 root volume) whose `user_data` installs Docker + the Astro CLI
- Elastic IP for a stable public address

Outputs: `s3_bucket_name`, `s3_bucket_arn`, `ec2_public_ip`, `airflow_url`, `grafana_url`.

**Important:** Terraform currently provisions *a host with Docker + Astro installed and nothing deployed*. The app is not yet brought up automatically — see the roadmap.

### Why Elastic IP
A stable public IP that survives stop/start, so SSH/CD targets, Airflow and Grafana URLs don't break.

### Why an EC2 IAM role
`boto3` uses the instance role automatically on EC2, so **AWS keys are not needed in the prod `.env`** (unlike local). The role only needs read access to the raw bucket.

---

## CI with GitHub Actions

`.github/workflows/ci.yml` runs on push to `dev`/`main` and PRs into `main`:

1. Checkout
2. Set up Python 3.11
3. Install dependencies
4. `compileall` of `dags pipelines src data_quality tests`
5. `pytest`

Current tests cover required-file existence and pollutant cleaning logic.

---

## Branch Strategy

```text
dev  → active development / integration branch
main → production branch (protected; deploy source)
```

```text
work locally → push to dev → CI runs → PR dev→main → CI runs → merge main → (planned) CD deploys to EC2
```

---

## Running Locally

```bash
astro dev start            # start Airflow + TimescaleDB + Grafana
# Airflow:  http://localhost:8080
# Grafana:  http://localhost:3000
# then trigger the DAG: london_environment_timeseries_pipeline
```

Useful commands:

```bash
pytest
python -m compileall dags pipelines src data_quality tests

cd terraform && terraform fmt && terraform validate && terraform plan

aws s3 ls s3://<bucket>/raw/defra/london_bloomsbury/ --recursive

python pipelines/extract_weather.py        # run a single stage manually
python pipelines/create_bronze_weather.py
```

---

## Configuration

Copy `.env.example` to `.env` and fill in real values (`.env` is gitignored and must never be committed):

```bash
cp .env.example .env
```

Key groups: AWS/S3 (`AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `S3_BUCKET`, `S3_RAW_PREFIX`, `DEFRA_SITE_FOLDER`), location/weather (`LATITUDE`, `LONGITUDE`, `START_DATE`, `TIMEZONE`), TimescaleDB (`POSTGRES_*`), and Grafana (`GF_SECURITY_*`).

On EC2 the AWS keys are unnecessary — the instance IAM role supplies S3 access. `boto3` requires the exact names `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` (not `AWS_ACCESS_KEY` / `AWS_SECRET_KEY`).

### Files not committed

```text
.env
.venv/
data/raw/  data/bronze/  data/silver/  data/gold/
terraform/terraform.tfvars
terraform/*.tfstate  terraform/.terraform/
```

---

## Work To Be Done

### Deployment to EC2 (the headline gap)
The Terraform host has Docker + Astro installed but nothing is deployed. To make "deploy to prod EC2 via Docker" real:

1. **Standalone `docker-compose.prod.yml`** — a self-contained stack (Airflow webserver/scheduler/triggerer + metadata Postgres + TimescaleDB + Grafana) that does **not** depend on the `astro dev` dev-only command. `docker-compose.override.yml` is only an *override* of Astro's generated base and can't stand alone on a clean box.
2. **ECR repository** (Terraform) — build the image once in CI, push by git SHA, and have EC2 `docker compose pull` it. Avoid building on the prod host.
3. **GitHub Actions CD** — on merge to `main`: OIDC → build → push ECR → deploy. No long-lived AWS keys in GitHub.
4. **SSM-based deploy** — attach `AmazonSSMManagedInstanceCore` to the EC2 role and deploy via SSM Send-Command (auditable, lets you close port 22). The current role only grants S3 read.

### Infrastructure hardening
- **Remote Terraform state** — add an S3 backend + DynamoDB lock (currently local `terraform.tfstate`).
- **Persistent data volume** — move TimescaleDB + Grafana Docker volumes onto a dedicated EBS volume (or managed DB) with snapshots, so an instance replacement doesn't wipe the data.
- **Right-size the instance** — `t3.small` (2 GB) OOM-kills this stack; use `t3.medium`+ or split TimescaleDB to RDS / Timescale Cloud.
- **Secrets management** — store `POSTGRES_*` / `GF_*` in AWS SSM Parameter Store (SecureString) and render `.env` on the box at deploy.

### Reliability & observability
- **Failure alerting** — `email_on_failure` is `False`; wire Airflow callbacks to email/Slack and add CloudWatch alarms.
- **Grafana provisioning** — commit datasource + dashboard provisioning so Grafana is reproducible instead of relying on the `grafana_data` volume.
- **More tests** — cover the `24:00` timestamp handling, the silver pivot, and the gold join; add `terraform fmt/validate` to CI.

### Data & modelling
- **Persist bronze/silver/gold to S3** as a durable data lake (not just local runtime files).
- **Optional: SQL as source of truth** — have `create_timescale_tables.py` execute `sql/timescale/*.sql` instead of hardcoding DDL in Python, removing schema duplication.
- **Data-freshness panel** in Grafana (`MAX(reading_date)` per table) to validate each load at a glance.

---

## Project Summary

A practical batch data engineering platform: raw environmental data stored in S3, orchestrated with Airflow, transformed with DuckDB, validated with GX Core, loaded into TimescaleDB, and visualised in Grafana — provisioned with Terraform and gated by GitHub Actions CI. It runs successfully end-to-end and serves a dynamic 2022 → present history. The remaining work is production deployment to EC2 (standalone compose + ECR + CD), infrastructure hardening (remote state, persistent storage, right-sizing, secrets), and observability.
