import os
from pathlib import Path

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()

S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
S3_PREFIX = os.getenv("S3_PREFIX", "raw/defra/london_bloomsbury")
AWS_REGION = os.getenv("AWS_REGION", "eu-north-1")
LOCAL_RAW_BASE = Path("data/raw")


def list_s3_csv_objects(bucket_name: str, prefix: str) -> list[dict]:
    s3 = boto3.client("s3", region_name=AWS_REGION)
    paginator = s3.get_paginator("list_objects_v2")

    objects = []
    for page in paginator.paginate(Bucket=bucket_name, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.lower().endswith(".csv"):
                objects.append(obj)

    return objects


def local_path_for_s3_key(key: str, prefix_root: str) -> Path:
    prefix_root = prefix_root.rstrip("/")
    if key.startswith(prefix_root + "/"):
        relative_key = key[len(prefix_root) + 1 :]
    else:
        relative_key = key

    return LOCAL_RAW_BASE / relative_key


def download_s3_object(bucket_name: str, key: str, local_path: Path) -> None:
    local_path.parent.mkdir(parents=True, exist_ok=True)

    s3 = boto3.client("s3", region_name=AWS_REGION)
    print(f"Downloading s3://{bucket_name}/{key} to {local_path}")

    try:
        s3.download_file(bucket_name, key, str(local_path))
    except ClientError as error:
        raise RuntimeError(f"Failed to download {key} from S3: {error}") from error


def main() -> None:
    if not S3_BUCKET_NAME:
        raise ValueError("S3_BUCKET_NAME must be set in the environment or .env file.")

    print(f"Syncing raw DEFRA CSVs from S3 bucket '{S3_BUCKET_NAME}' with prefix '{S3_PREFIX}'")

    objects = list_s3_csv_objects(S3_BUCKET_NAME, S3_PREFIX)
    if not objects:
        raise FileNotFoundError(
            f"No CSV objects found in s3://{S3_BUCKET_NAME}/{S3_PREFIX}"
        )

    for obj in objects:
        key = obj["Key"]
        local_path = local_path_for_s3_key(key, "raw")
        download_s3_object(S3_BUCKET_NAME, key, local_path)

    print("Raw DEFRA CSV sync completed successfully.")


if __name__ == "__main__":
    main()
