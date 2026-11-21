"""Dépose les datasets de test dans MinIO, selon le contrat (raw-data/<nom>/v1/).

Usage :
    python -m scripts.seed_datasets                 # tous
    python -m scripts.seed_datasets --only adult wine
"""
from __future__ import annotations

import argparse

import yaml
from sklearn.datasets import (
    fetch_california_housing,
    fetch_openml,
    load_diabetes,
    load_wine,
)

from core.contract import BUCKET_RAW, raw_key
from core.storage import write_csv, write_text


def _adult():
    return fetch_openml(data_id=1590, as_frame=True).frame


def _wine():
    return load_wine(as_frame=True).frame


def _diabetes():
    return load_diabetes(as_frame=True).frame


def _california():
    return fetch_california_housing(as_frame=True).frame


DATASETS = {
    "adult": {
        "loader": _adult,
        "config": {
            "name": "adult",
            "target": "class",
            "task": "auto",
            "sensitive_features": ["sex", "race"],
        },
    },
    "wine": {
        "loader": _wine,
        "config": {"name": "wine", "target": "target", "task": "auto"},
    },
    "diabetes": {
        "loader": _diabetes,
        "config": {"name": "diabetes", "target": "target", "task": "auto"},
    },
    "california_housing": {
        "loader": _california,
        "config": {"name": "california_housing", "target": "MedHouseVal", "task": "auto"},
    },
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", nargs="+", choices=list(DATASETS))
    parser.add_argument("--version", type=int, default=1)
    args = parser.parse_args()

    for name in args.only or list(DATASETS):
        spec = DATASETS[name]
        df = spec["loader"]()
        write_csv(df, BUCKET_RAW, raw_key(name, args.version))
        write_text(
            BUCKET_RAW,
            raw_key(name, args.version, "dataset.yaml"),
            yaml.safe_dump(spec["config"], sort_keys=False, allow_unicode=True),
        )
        print(f"{name:20s} v{args.version} : {df.shape[0]} lignes x {df.shape[1]} colonnes")


if __name__ == "__main__":
    main()
