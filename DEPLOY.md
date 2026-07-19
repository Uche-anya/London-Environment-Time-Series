# Deploy — free-tier ($0) one-shot run on EC2

This runs the pipeline **once** on a free-tier `t3.micro` and shows the result in
Grafana. Airflow is **not** used here (it needs ~4 GB RAM and won't fit 1 GB) — the
box runs `run_pipeline.py` via the slim [`docker-compose.prod.yml`](docker-compose.prod.yml).
Airflow stays for local dev (`astro dev start`).

Stack on the box: **TimescaleDB** (serving DB) + **Grafana** (dashboard) + a one-shot
**pipeline** container. The pipeline image is **built by GitHub Actions and pushed to
ECR** — nothing is built on your laptop or on the t3.micro; the box just pulls it.
Cost: $0 for the 12-month AWS free-tier window (ECR storage for a ~1 GB image is a
few cents/month at most).

---

## 1. Provision infra (Terraform)

This resizes the box to free-tier `t3.micro` (with a 2 GB swapfile so the one-shot
run doesn't OOM) and creates the ECR repo + GitHub OIDC role.

```bash
cd terraform
terraform apply
terraform output ec2_public_ip
terraform output ecr_repository_url        # e.g. 753675398762.dkr.ecr.eu-north-1.amazonaws.com/london-environment-pipeline
terraform output github_actions_role_arn   # e.g. arn:aws:iam::753675398762:role/london-environment-pipeline-github-actions-ecr-push
```

> Changing `user_data` replaces the instance (new box, same Elastic IP). The instance
> IAM role gives the box **S3 read + ECR pull with no keys**, so extraction and image
> pull both work without AWS credentials in `.env` on the server.

## 2. Wire GitHub Actions → ECR (one-time)

In the GitHub repo (**Settings → Secrets and variables → Actions**) add:

| Kind | Name | Value (from step 1 outputs) |
| --- | --- | --- |
| Secret | `AWS_ROLE_ARN` | `github_actions_role_arn` |
| Variable | `ECR_REPOSITORY_URL` | `ecr_repository_url` |
| Variable | `AWS_REGION` | `eu-north-1` (optional; defaults to this) |

Then push to `main` (or run the **Build and push pipeline image** workflow manually via
*Actions → Run workflow*). It builds `Dockerfile.pipeline` and pushes
`:latest` + `:<git-sha>` to ECR — **no long-lived AWS keys** (OIDC).

## 3. Get the code + config onto the box

```bash
ssh ubuntu@<EIP>
git clone https://github.com/Uche-anya/London-Environment-Time-Series.git
cd London-Environment-Time-Series
cp .env.example .env
nano .env      # POSTGRES_*, GF_*, S3_BUCKET, LATITUDE/START_DATE, etc.
               # Leave AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY blank — the IAM role covers it.

# Point the pipeline service at the ECR image (from step 1):
echo "PIPELINE_IMAGE=<ecr_repository_url>:latest" >> .env
```

## 4. Log in to ECR, pull, and run once

```bash
# Authenticate Docker to ECR using the instance role (awscli is preinstalled via user_data):
aws ecr get-login-password --region eu-north-1 \
  | docker login --username AWS --password-stdin <ecr_repository_url>

docker compose -f docker-compose.prod.yml up -d              # TimescaleDB + Grafana
docker compose -f docker-compose.prod.yml pull pipeline      # pull the image from ECR (no build)
docker compose -f docker-compose.prod.yml run --rm pipeline  # loads the data (one-shot)
```

The pipeline logs 10 stages and finishes with `Pipeline finished OK`. Expected load
(current data): ~11,361 daily air-quality rows, ~1,661 daily weather rows, ~272,496
hourly rows.

## 5. See it in Grafana → screenshot

Open `http://<EIP>:3000` (login = `GF_SECURITY_ADMIN_USER` / `GF_SECURITY_ADMIN_PASSWORD`).

1. **Add datasource** → PostgreSQL:
   - Host: `timescaledb:5432`  (Grafana reaches it by service name on the compose network)
   - Database / User / Password: your `POSTGRES_*` values
   - TLS/SSL mode: `disable`
2. **Import dashboard** → upload [`grafana/dashboard/london_environment_dashboard.json`](grafana/dashboard/london_environment_dashboard.json), pick the datasource above.

That's the portfolio artifact — a live dashboard on AWS backed by the real pipeline.

## 6. Stop billing when you're done

```bash
# on the box
docker compose -f docker-compose.prod.yml down     # stop containers (keeps data volumes)
```

To remove all AWS resources entirely: `cd terraform && terraform destroy`.

---

### Notes

- **The `-pipeline` ECR login host is the repo URL without the `:tag`.** `docker login`
  targets the registry host; `docker pull` targets the full `:tag`.
- **Grafana datasource host is `timescaledb`, not `localhost`** — both run as containers
  on the same Docker network.
- **Re-running is safe.** The load upserts (`ON CONFLICT DO UPDATE`), so
  `run --rm pipeline` again just refreshes rows, never duplicates them.
- **If the run gets killed on 1 GB**, confirm swap is on (`swapon --show`); the Terraform
  `user_data` sets up a 2 GB swapfile automatically on a fresh box.
- **ECR login expires after 12 h.** If a later pull fails auth, re-run the
  `aws ecr get-login-password ... | docker login ...` command.
