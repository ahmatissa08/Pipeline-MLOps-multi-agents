import io
import os

import boto3
import pandas as pd
from botocore.config import Config

ENDPOINT = os.getenv("S3_ENDPOINT_URL", "http://localhost:9000")
ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "minioadmin")
SECRET_KEY = os.getenv("S3_SECRET_KEY", "minioadmin")


def get_s3():
    return boto3.client(
        "s3",
        endpoint_url=ENDPOINT,
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        region_name="us-east-1",
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
            retries={"max_attempts": 5},
        ),
    )


def read_csv(bucket: str, key: str) -> pd.DataFrame:
    obj = get_s3().get_object(Bucket=bucket, Key=key)
    return pd.read_csv(io.BytesIO(obj["Body"].read()))


def write_csv(df: pd.DataFrame, bucket: str, key: str) -> None:
    get_s3().put_object(
        Bucket=bucket, Key=key, Body=df.to_csv(index=False).encode("utf-8")
    )