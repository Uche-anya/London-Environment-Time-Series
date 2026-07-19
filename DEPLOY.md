# Deploy — free-tier ($0) one-shot run on EC2

This runs the pipeline **once** on a free-tier `t3.micro` and shows the result in
Grafana. Airflow is **not** used here (it needs ~4 GB RAM and won't fit 1 GB) — the
box runs `run_pipeline.py` via the slim [`docker-compose.prod.yml`](docker-compose.prod.yml).
Airflow stays for local dev (`astro dev start`).

Stack on the box: **TimescaleDB** (serving DB) + **Grafana** (dashboard) + a one-shot
**pipeline** container. Cost: $0 for the 12-month AWS free-tier window.

---

## 1. Provision / resize the box (Terraform)

The Terraform is already applied; this just resizes it to the free-tier `t3.micro`
and adds a 2 GB swapfile (so the one-shot run doesn't OOM on 1 GB).

```bash
cd terraform
terraform apply          # instance_type -> t3.micro, user_data adds swap
terraform output ec2_public_ip
terraform output grafana_url
```

> Changing `user_data` replaces the instance (new box, same Elastic IP). The IAM
> role gives the box **S3 read with no keys**, so the pipeline's S3 extract works
> without AWS credentials in `.env` on the server.

## 2. Get the code + config onto the box

```bash
ssh ubuntu@<EIP>
git clone https://github.com/Uche-anya/London-Environment-Time-Series.git
cd London-Environment-Time-Series
cp .env.example .env
nano .env                # fill in POSTGRES_*, GF_*, S3_BUCKET, LATITUDE/START_DATE, etc.
                         # On EC2 you can leave AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY blank
                         # (the instance IAM role supplies S3 access).
```

## 3. Start the serving stack, then run the pipeline once

```bash
docker compose -f docker-compose.prod.yml up -d            # TimescaleDB + Grafana
docker compose -f docker-compose.prod.yml run --rm pipeline  # loads the data (one-shot)
```

The pipeline logs 10 stages and finishes with `Pipeline finished OK`. Expected load
(current data): ~11,361 daily air-quality rows, ~1,661 daily weather rows, ~272,496
hourly rows.

## 4. See it in Grafana → screenshot

Open `http://<EIP>:3000` (login = `GF_SECURITY_ADMIN_USER` / `GF_SECURITY_ADMIN_PASSWORD`).

1. **Add datasource** → PostgreSQL:
   - Host: `timescaledb:5432`  (Grafana reaches it by service name on the compose network)
   - Database / User / Password: your `POSTGRES_*` values
   - TLS/SSL mode: `disable`
2. **Import dashboard** → upload [`grafana/dashboard/london_environment_dashboard.json`](grafana/dashboard/london_environment_dashboard.json), pick the datasource above.

That's the portfolio artifact — a live dashboard on AWS backed by the real pipeline.

## 5. Stop billing when you're done

Free tier covers a running `t3.micro`, but to be safe between demos:

```bash
# on the box
docker compose -f docker-compose.prod.yml down     # stop containers (keeps data volumes)
```

To remove the AWS resources entirely: `cd terraform && terraform destroy`.

---

### Notes

- **Grafana datasource host is `timescaledb`, not `localhost`** — both run as containers
  on the same Docker network.
- **Re-running is safe.** The load upserts (`ON CONFLICT DO UPDATE`), so
  `run --rm pipeline` again just refreshes rows, never duplicates them.
- **If the run gets killed on 1 GB**, confirm swap is on (`swapon --show`); the Terraform
  `user_data` sets up a 2 GB swapfile automatically on a fresh box.
