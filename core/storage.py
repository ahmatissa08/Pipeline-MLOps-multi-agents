"""Accès à Silo/MinIO. Un seul endroit pour la connexion (voir le README).

Les désactivations de checksum évitent les « Connection was closed » observés
avec les versions récentes de boto3 sur des serveurs S3-compatibles.
"""
from __future__ import annotations

import io
import json
import os
import tempfile
import time
from typing import Any

import boto3
import pandas as pd
from botocore.config import Config
from botocore.exceptions import (
    ClientError,
    ConnectionClosedError,
    EndpointConnectionError,
    ReadTimeoutError,
)

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
            connect_timeout=5,
            read_timeout=30,
            retries={"max_attempts": 3},
        ),
    )


# --- octets / texte / JSON -------------------------------------------------
_RETRYABLE = (ConnectionClosedError, EndpointConnectionError, ReadTimeoutError)


def write_bytes(bucket: str, key: str, data: bytes, attempts: int = 4) -> None:
    """Dépôt d'un objet via un fichier temporaire (upload_file).

    Seule cette méthode, avec upload_fileobj sans threads, a fonctionné de façon
    fiable avec Silo sous Docker Desktop (voir scripts/diag_s3.py). En cas de
    coupure ou de délai dépassé, on réessaie avec une NOUVELLE connexion.
    """
    fd, path = tempfile.mkstemp(suffix=".bin")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        last: Exception | None = None
        for attempt in range(attempts):
            try:
                get_s3().upload_file(path, bucket, key)
                return
            except _RETRYABLE as exc:
                last = exc
                time.sleep(1 + attempt)
        raise last  # type: ignore[misc]
    finally:
        os.unlink(path)


def read_bytes(bucket: str, key: str) -> bytes:
    return get_s3().get_object(Bucket=bucket, Key=key)["Body"].read()


def write_text(bucket: str, key: str, text: str) -> None:
    write_bytes(bucket, key, text.encode("utf-8"))


def read_text(bucket: str, key: str) -> str:
    return read_bytes(bucket, key).decode("utf-8")


def write_json(bucket: str, key: str, obj: Any) -> None:
    write_text(bucket, key, json.dumps(obj, ensure_ascii=False, indent=2, default=str))


def read_json(bucket: str, key: str) -> Any:
    return json.loads(read_text(bucket, key))


# --- CSV -------------------------------------------------------------------
def read_csv(bucket: str, key: str) -> pd.DataFrame:
    return pd.read_csv(io.BytesIO(read_bytes(bucket, key)))


def write_csv(df: pd.DataFrame, bucket: str, key: str) -> None:
    write_bytes(bucket, key, df.to_csv(index=False).encode("utf-8"))


# --- exploration -----------------------------------------------------------
def exists(bucket: str, key: str) -> bool:
    try:
        get_s3().head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
            return False
        raise


def list_keys(bucket: str, prefix: str = "") -> list[str]:
    keys: list[str] = []
    paginator = get_s3().get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        keys.extend(obj["Key"] for obj in page.get("Contents", []))
    return keys