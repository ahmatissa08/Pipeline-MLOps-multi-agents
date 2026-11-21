"""Inspecte un dataset déposé dans MinIO.

Usage : python -m scripts.check_dataset <nom> [version]
Exemple : python -m scripts.check_dataset adult
"""
from __future__ import annotations

import sys

import yaml

from core.contract import BUCKET_RAW, raw_key
from core.storage import read_csv, read_text

name = sys.argv[1] if len(sys.argv) > 1 else "adult"
version = int(sys.argv[2]) if len(sys.argv) > 2 else 1

cfg = yaml.safe_load(read_text(BUCKET_RAW, raw_key(name, version, "dataset.yaml")))
df = read_csv(BUCKET_RAW, raw_key(name, version))
target = cfg["target"]

print(f"Dataset {name} v{version} : {df.shape[0]} lignes x {df.shape[1]} colonnes")
print("Configuration :", cfg)

missing = df.isna().sum()
print("\nValeurs manquantes :", missing[missing > 0].to_dict() or "aucune")
print("Doublons :", int(df.duplicated().sum()))

y = df[target]
print(f"\nCible {target!r} : dtype={y.dtype}, valeurs distinctes={y.nunique()}")
if y.nunique() <= 20:
    print(y.value_counts(normalize=True).round(3).to_string())
else:
    print(y.describe().round(3).to_string())