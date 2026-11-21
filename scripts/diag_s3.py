"""Diagnostic : quelles méthodes de dépôt fonctionnent avec Silo ?

Chaque test est limité dans le temps, le script ne peut donc pas se bloquer.
Usage : python -m scripts.diag_s3
"""
from __future__ import annotations

import io
import os
import tempfile
import threading
import time

import boto3
from boto3.s3.transfer import TransferConfig
from botocore.config import Config

BUCKET = "raw-data"
PREFIX = "_diag"
ESSAIS = 2
LIMITE_S = 30


def client():
    return boto3.client(
        "s3",
        endpoint_url="http://localhost:9000",
        aws_access_key_id="minioadmin",
        aws_secret_access_key="minioadmin",
        region_name="us-east-1",
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
            connect_timeout=5,
            read_timeout=10,
            retries={"max_attempts": 1},
        ),
    )


def t_put_5_octets(key):
    client().put_object(Bucket=BUCKET, Key=key, Body=b"hello")


def t_put_bytesio(key):
    client().put_object(Bucket=BUCKET, Key=key, Body=io.BytesIO(b"hello"))


def t_put_2ko(key):
    client().put_object(Bucket=BUCKET, Key=key, Body=b"x" * 2048)


def t_put_5mo(key):
    client().put_object(Bucket=BUCKET, Key=key, Body=b"x" * 5 * 1024 * 1024)


def t_fileobj_petit_threads(key):
    client().upload_fileobj(io.BytesIO(b"hello"), BUCKET, key)


def t_fileobj_petit_sans_threads(key):
    cfg = TransferConfig(use_threads=False)
    client().upload_fileobj(io.BytesIO(b"hello"), BUCKET, key, Config=cfg)


def t_upload_file_petit(key):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
        f.write(b"hello")
        path = f.name
    try:
        client().upload_file(path, BUCKET, key)
    finally:
        os.unlink(path)


TESTS = [
    ("put_object 5 octets", t_put_5_octets),
    ("put_object 5 octets (BytesIO)", t_put_bytesio),
    ("put_object 2 Ko", t_put_2ko),
    ("put_object 5 Mo", t_put_5mo),
    ("upload_fileobj 5 octets", t_fileobj_petit_threads),
    ("upload_fileobj 5 octets, sans threads", t_fileobj_petit_sans_threads),
    ("upload_file 5 octets (fichier)", t_upload_file_petit),
]


def run_limited(fn, key):
    """Renvoie ('OK', None) / ('ERREUR', nom) / ('BLOQUÉ', None)."""
    result: dict = {}

    def target():
        try:
            fn(key)
            result["status"] = ("OK", None)
        except Exception as exc:  # noqa: BLE001 - diagnostic
            result["status"] = ("ERREUR", type(exc).__name__)

    th = threading.Thread(target=target, daemon=True)
    th.start()
    th.join(LIMITE_S)
    return result.get("status", ("BLOQUÉ", None))


def main() -> None:
    print(f"{'méthode':42s} {'réussites':10s} erreurs")
    for name, fn in TESTS:
        ok, problems = 0, []
        for i in range(ESSAIS):
            key = f"{PREFIX}/{name.replace(' ', '_')}_{i}"
            status, detail = run_limited(fn, key)
            if status == "OK":
                ok += 1
            else:
                problems.append(detail or status)
            time.sleep(0.5)
        print(f"{name:42s} {ok}/{ESSAIS:<8d} {', '.join(sorted(set(problems))) or '-'}")

    try:  # nettoyage
        c = client()
        for obj in c.list_objects_v2(Bucket=BUCKET, Prefix=PREFIX).get("Contents", []):
            c.delete_object(Bucket=BUCKET, Key=obj["Key"])
    except Exception:  # noqa: BLE001
        pass


if __name__ == "__main__":
    main()