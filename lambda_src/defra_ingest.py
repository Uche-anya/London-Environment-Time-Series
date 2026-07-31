"""Download recent London Bloomsbury CSVs from DEFRA and store them in S3."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import os
from datetime import UTC, date, datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import boto3
from botocore.exceptions import ClientError

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.INFO)

BUCKET_NAME = os.environ.get("S3_BUCKET", "")
S3_PREFIX = os.environ.get("S3_PREFIX", "raw/defra/london_bloomsbury").strip("/")
SITE_CODE = os.environ.get("DEFRA_SITE_CODE", "CLL2")
YEARS_TO_REFRESH = int(os.environ.get("YEARS_TO_REFRESH", "2"))
SOURCE_URL_TEMPLATE = os.environ.get(
    "SOURCE_URL_TEMPLATE",
    "https://uk-air.defra.gov.uk/datastore/data_files/site_data/"
    "{site_code}_{year}.csv?v=1",
)
MAX_DOWNLOAD_BYTES = 25 * 1024 * 1024
REQUIRED_COLUMNS = {"Date", "time", "Nitrogen dioxide"}
DATE_FORMATS = ("%d-%m-%Y", "%d/%m/%Y")


def source_url(year: int) -> str:
    return SOURCE_URL_TEMPLATE.format(site_code=SITE_CODE, year=year)


def destination_key(year: int) -> str:
    return f"{S3_PREFIX}/year={year}/london_bloomsbury_{year}.csv"


def default_years(today: date | None = None) -> list[int]:
    """Return the moving head: current year plus recent revisable years."""
    current_year = (today or date.today()).year
    return [current_year - offset for offset in range(YEARS_TO_REFRESH)]


def parse_event_years(event: dict | None, today: date | None = None) -> list[int]:
    """Allow a manual invocation to request specific years for repair/backfill."""
    if not event or "years" not in event:
        return default_years(today)
    raw_years = event["years"]
    if not isinstance(raw_years, list) or not raw_years or len(raw_years) > 10:
        raise ValueError("event.years must be a non-empty list of at most 10 years")
    years = []
    for value in raw_years:
        if isinstance(value, bool):
            raise ValueError(f"Invalid year: {value!r}")
        try:
            year = int(value)
        except (TypeError, ValueError) as error:
            raise ValueError(f"Invalid year: {value!r}") from error
        if not 1990 <= year <= (today or date.today()).year:
            raise ValueError(f"Year is outside the supported range: {year}")
        if year not in years:
            years.append(year)
    return years


def download_csv(year: int) -> tuple[bytes, str]:
    url = source_url(year)
    request = Request(
        url,
        headers={
            "Accept": "text/csv,text/plain;q=0.9,*/*;q=0.1",
            "User-Agent": "london-environment-pipeline/1.0",
        },
    )
    try:
        with urlopen(request, timeout=60) as response:  # noqa: S310 - fixed HTTPS host
            payload = response.read(MAX_DOWNLOAD_BYTES + 1)
    except (HTTPError, URLError, TimeoutError) as error:
        raise RuntimeError(f"Failed to download DEFRA CSV for {year}: {error}") from error
    if len(payload) > MAX_DOWNLOAD_BYTES:
        raise ValueError(f"DEFRA CSV for {year} exceeds {MAX_DOWNLOAD_BYTES} bytes")
    return payload, url


def _parse_date(value: str) -> date:
    for date_format in DATE_FORMATS:
        try:
            return datetime.strptime(value.strip(), date_format).date()
        except ValueError:
            continue
    raise ValueError(f"Unrecognised DEFRA date: {value!r}")


def validate_csv(payload: bytes, expected_year: int) -> dict[str, str | int]:
    """Reject error pages, malformed files, and data for an unexpected year."""
    if not payload:
        raise ValueError(f"DEFRA CSV for {expected_year} is empty")
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = payload.decode("latin-1")
    if text.lstrip().lower().startswith(("<!doctype html", "<html")):
        raise ValueError(f"DEFRA returned HTML instead of CSV for {expected_year}")

    rows = list(csv.reader(io.StringIO(text)))
    if len(rows) < 6:
        raise ValueError(f"DEFRA CSV for {expected_year} has no data rows")
    if not rows[0] or not rows[0][0].startswith("Data supplied by UK-AIR"):
        raise ValueError(f"DEFRA CSV for {expected_year} has an unexpected preamble")
    header = rows[4]
    missing_columns = REQUIRED_COLUMNS.difference(header)
    if missing_columns:
        raise ValueError(
            f"DEFRA CSV for {expected_year} is missing columns: {sorted(missing_columns)}"
        )

    date_index = header.index("Date")
    data_dates = []
    for row_number, row in enumerate(rows[5:], start=6):
        if not row or not any(cell.strip() for cell in row):
            continue
        if len(row) <= date_index:
            raise ValueError(f"Malformed DEFRA CSV row {row_number} for {expected_year}")
        parsed_date = _parse_date(row[date_index])
        if parsed_date.year != expected_year:
            raise ValueError(
                f"DEFRA CSV for {expected_year} contains date {parsed_date.isoformat()}"
            )
        data_dates.append(parsed_date)
    if not data_dates:
        raise ValueError(f"DEFRA CSV for {expected_year} has no valid data rows")
    return {
        "row_count": len(data_dates),
        "latest_data_date": max(data_dates).isoformat(),
    }


def _existing_checksum(s3_client, key: str) -> str | None:
    try:
        response = s3_client.head_object(Bucket=BUCKET_NAME, Key=key)
    except ClientError as error:
        error_code = error.response.get("Error", {}).get("Code")
        if error_code in {"404", "NoSuchKey", "NotFound"}:
            return None
        raise
    return response.get("Metadata", {}).get("sha256")


def ingest_year(s3_client, year: int) -> dict[str, str | int]:
    payload, url = download_csv(year)
    validation = validate_csv(payload, year)
    checksum = hashlib.sha256(payload).hexdigest()
    key = destination_key(year)
    if _existing_checksum(s3_client, key) == checksum:
        LOG.info("Unchanged: s3://%s/%s", BUCKET_NAME, key)
        return {"year": year, "key": key, "status": "unchanged", **validation}

    response = s3_client.put_object(
        Bucket=BUCKET_NAME,
        Key=key,
        Body=payload,
        ContentType="text/csv",
        Metadata={
            "sha256": checksum,
            "source-url": url,
            "fetched-at": datetime.now(UTC).isoformat(),
            "latest-data-date": str(validation["latest_data_date"]),
            "row-count": str(validation["row_count"]),
        },
    )
    LOG.info(
        "Uploaded %s rows to s3://%s/%s (version %s)",
        validation["row_count"], BUCKET_NAME, key,
        response.get("VersionId", "unversioned"),
    )
    return {
        "year": year,
        "key": key,
        "status": "uploaded",
        "version_id": response.get("VersionId", ""),
        **validation,
    }


def lambda_handler(event, _context):
    if not BUCKET_NAME:
        raise ValueError("S3_BUCKET environment variable must be set")
    years = parse_event_years(event)
    LOG.info("Starting DEFRA ingestion for years: %s", years)
    s3_client = boto3.client("s3")
    results = [ingest_year(s3_client, year) for year in years]
    return {"statusCode": 200, "body": json.dumps({"results": results})}
