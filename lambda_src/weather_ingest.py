"""Land validated Open-Meteo ERA5 weather responses in the raw S3 zone."""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import UTC, date, datetime, timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import boto3
from botocore.exceptions import ClientError


LOG = logging.getLogger(__name__)
LOG.setLevel(logging.INFO)

BUCKET_NAME = os.environ.get("S3_BUCKET", "")
S3_PREFIX = os.environ.get("S3_PREFIX", "raw/open_meteo").strip("/")
LATITUDE = os.environ.get("LATITUDE", "51.522290")
LONGITUDE = os.environ.get("LONGITUDE", "-0.125889")
START_DATE = date.fromisoformat(os.environ.get("START_DATE", "2022-01-01"))
TIMEZONE = os.environ.get("TIMEZONE", "GMT")
MODEL = os.environ.get("WEATHER_MODEL", "era5")
ARCHIVE_LAG_DAYS = int(os.environ.get("ARCHIVE_LAG_DAYS", "5"))
YEARS_TO_REFRESH = int(os.environ.get("YEARS_TO_REFRESH", "2"))
SOURCE_ENDPOINT = "https://archive-api.open-meteo.com/v1/archive"
MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024

HOURLY_FIELDS = (
    "time",
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "pressure_msl",
    "wind_speed_10m",
)


def available_through(today: date | None = None) -> date:
    """Latest date expected to be stable in the ERA5 archive."""
    return (today or date.today()) - timedelta(days=ARCHIVE_LAG_DAYS)


def configured_years(today: date | None = None) -> list[int]:
    latest_year = available_through(today).year
    return list(range(START_DATE.year, latest_year + 1))


def parse_event_years(event: dict | None, today: date | None = None) -> list[int]:
    if not event or "years" not in event:
        return configured_years(today)

    raw_years = event["years"]
    if not isinstance(raw_years, list) or not raw_years or len(raw_years) > 10:
        raise ValueError("event.years must be a non-empty list of at most 10 years")

    latest_year = available_through(today).year
    years = []
    for value in raw_years:
        if isinstance(value, bool):
            raise ValueError(f"Invalid year: {value!r}")
        try:
            year = int(value)
        except (TypeError, ValueError) as error:
            raise ValueError(f"Invalid year: {value!r}") from error
        if not START_DATE.year <= year <= latest_year:
            raise ValueError(f"Year is outside the configured range: {year}")
        if year not in years:
            years.append(year)
    return years


def year_bounds(year: int, today: date | None = None) -> tuple[date, date] | None:
    start = max(START_DATE, date(year, 1, 1))
    end = min(date(year, 12, 31), available_through(today))
    if end < start:
        return None
    return start, end


def destination_key(year: int) -> str:
    return f"{S3_PREFIX}/year={year}/london_weather_{year}.json"


def source_url(start: date, end: date) -> str:
    query = urlencode(
        {
            "latitude": LATITUDE,
            "longitude": LONGITUDE,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "hourly": ",".join(HOURLY_FIELDS[1:]),
            "timezone": TIMEZONE,
            "models": MODEL,
        }
    )
    return f"{SOURCE_ENDPOINT}?{query}"


def download_weather(year: int, today: date | None = None) -> tuple[dict, str]:
    bounds = year_bounds(year, today)
    if bounds is None:
        raise ValueError(f"No archived weather dates are available for {year}")

    url = source_url(*bounds)
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "london-environment-pipeline/1.0",
        },
    )
    try:
        with urlopen(request, timeout=120) as response:  # noqa: S310 - fixed HTTPS host
            payload = response.read(MAX_DOWNLOAD_BYTES + 1)
    except (HTTPError, URLError, TimeoutError) as error:
        raise RuntimeError(
            f"Failed to download Open-Meteo weather for {year}: {error}"
        ) from error

    if len(payload) > MAX_DOWNLOAD_BYTES:
        raise ValueError(
            f"Open-Meteo response for {year} exceeds {MAX_DOWNLOAD_BYTES} bytes"
        )
    try:
        return json.loads(payload), url
    except json.JSONDecodeError as error:
        raise ValueError(f"Open-Meteo returned invalid JSON for {year}") from error


def validate_weather(data: dict, expected_year: int) -> dict[str, str | int]:
    if not isinstance(data, dict) or "hourly" not in data:
        raise ValueError(
            f"Open-Meteo response for {expected_year} does not contain hourly data"
        )
    hourly = data["hourly"]
    missing_fields = [field for field in HOURLY_FIELDS if field not in hourly]
    if missing_fields:
        raise ValueError(
            f"Open-Meteo response for {expected_year} is missing fields: "
            f"{missing_fields}"
        )

    row_count = len(hourly["time"])
    if row_count == 0:
        raise ValueError(f"Open-Meteo response for {expected_year} has no rows")
    length_mismatches = {
        field: len(hourly[field])
        for field in HOURLY_FIELDS
        if not isinstance(hourly[field], list) or len(hourly[field]) != row_count
    }
    if length_mismatches:
        raise ValueError(
            f"Open-Meteo response for {expected_year} has length mismatches: "
            f"{length_mismatches}"
        )

    first_timestamp = str(hourly["time"][0])
    latest_timestamp = str(hourly["time"][-1])
    if not first_timestamp.startswith(f"{expected_year}-"):
        raise ValueError(
            f"Open-Meteo response for {expected_year} starts at {first_timestamp}"
        )
    if not latest_timestamp.startswith(f"{expected_year}-"):
        raise ValueError(
            f"Open-Meteo response for {expected_year} ends at {latest_timestamp}"
        )
    return {"row_count": row_count, "latest_timestamp": latest_timestamp}


def _head_object(s3_client, key: str) -> dict | None:
    try:
        return s3_client.head_object(Bucket=BUCKET_NAME, Key=key)
    except ClientError as error:
        error_code = error.response.get("Error", {}).get("Code")
        if error_code in {"404", "NoSuchKey", "NotFound"}:
            return None
        raise


def _metadata_result(year: int, key: str, response: dict) -> dict[str, str | int]:
    metadata = response.get("Metadata", {})
    return {
        "year": year,
        "key": key,
        "status": "existing",
        "row_count": int(metadata.get("row-count", "0")),
        "latest_timestamp": metadata.get("latest-timestamp", ""),
    }


def serialise_weather(data: dict) -> bytes:
    """Create stable source JSON without Open-Meteo request timing metadata."""
    canonical_data = {
        key: value for key, value in data.items() if key != "generationtime_ms"
    }
    return json.dumps(
        canonical_data, separators=(",", ":"), ensure_ascii=False, sort_keys=True
    ).encode()


def ingest_year(
    s3_client, year: int, today: date | None = None
) -> dict[str, str | int]:
    data, url = download_weather(year, today)
    validation = validate_weather(data, year)
    payload = serialise_weather(data)
    checksum = hashlib.sha256(payload).hexdigest()
    key = destination_key(year)
    existing = _head_object(s3_client, key)

    if existing and existing.get("Metadata", {}).get("sha256") == checksum:
        LOG.info("Unchanged: s3://%s/%s", BUCKET_NAME, key)
        return {"year": year, "key": key, "status": "unchanged", **validation}

    response = s3_client.put_object(
        Bucket=BUCKET_NAME,
        Key=key,
        Body=payload,
        ContentType="application/json",
        Metadata={
            "sha256": checksum,
            "source-url": url,
            "fetched-at": datetime.now(UTC).isoformat(),
            "latest-timestamp": str(validation["latest_timestamp"]),
            "row-count": str(validation["row_count"]),
            "model": MODEL,
            "timezone": TIMEZONE,
        },
    )
    LOG.info(
        "Uploaded %s rows to s3://%s/%s (version %s)",
        validation["row_count"],
        BUCKET_NAME,
        key,
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

    today = date.today()
    years = parse_event_years(event, today)
    latest_year = available_through(today).year
    s3_client = boto3.client("s3")
    results = []

    LOG.info("Starting Open-Meteo ingestion for years: %s", years)
    for year in years:
        key = destination_key(year)
        existing = _head_object(s3_client, key)
        is_recent = year >= latest_year - YEARS_TO_REFRESH + 1
        has_managed_checksum = bool(
            existing and existing.get("Metadata", {}).get("sha256")
        )
        if not is_recent and has_managed_checksum:
            LOG.info("Existing frozen year: s3://%s/%s", BUCKET_NAME, key)
            results.append(_metadata_result(year, key, existing))
            continue
        results.append(ingest_year(s3_client, year, today))

    return {"statusCode": 200, "body": json.dumps({"results": results})}
