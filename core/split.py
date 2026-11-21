"""Découpage train/test unique, partagé par Training et QA.

Les deux agents appellent cette fonction : ils obtiennent exactement le même
jeu de test (même graine, même proportion, même stratification).
"""
from __future__ import annotations

import pandas as pd
from sklearn.model_selection import train_test_split

from core.contract import SEED, TEST_SIZE, AgentError, TaskType


def split_data(
    df: pd.DataFrame, target: str, task_type: TaskType
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    """Renvoie X_train, X_test, y_train, y_test."""
    if target not in df.columns:
        raise AgentError(f"Colonne cible absente du dataset : {target!r}")

    X = df.drop(columns=[target])
    y = df[target]

    stratify = None
    if task_type in ("binary", "multiclass"):
        smallest = int(y.value_counts().min())
        if smallest < 2:
            raise AgentError(
                f"Découpage stratifié impossible : une classe n'a que {smallest} "
                "exemple(s). L'Agent Data doit la signaler ou la retirer."
            )
        stratify = y

    return train_test_split(
        X, y, test_size=TEST_SIZE, random_state=SEED, stratify=stratify
    )