"""Contrat d'interfaces du pipeline MLOps multi-agents.

Source de vérité partagée par les trois membres :
  - Ahmat   : orchestrateur, Agent QA, quality gate, baseline
  - Hereta  : Agent Data, Agent Training, core/llm.py
  - Clement : Agent Release, API de serving, Kubernetes, CI/CD, IHM

Règle : toute modification de ce fichier passe par une Pull Request relue
par les deux autres membres. Chaque agent lit l'état, écrit UNIQUEMENT sa
propre section (plus `decisions`) et renvoie ce dictionnaire partiel.
"""
from __future__ import annotations

import operator
from datetime import datetime, timezone
from typing import Annotated, Any, Literal, TypedDict

# --------------------------------------------------------------------------
# Constantes partagées (reproductibilité)
# --------------------------------------------------------------------------
SEED = 42
TEST_SIZE = 0.2
CV_FOLDS = 5

BUCKET_RAW = "raw-data"
BUCKET_CLEAN = "clean-data"
BUCKET_REGISTRY = "model-registry"
BUCKET_RUNS = "pipeline-runs"  # à créer : mcli mb local/pipeline-runs

TaskType = Literal["binary", "multiclass", "regression"]
Status = Literal["RUNNING", "WAITING_APPROVAL", "SUCCEEDED", "REJECTED", "FAILED"]
AgentMode = Literal["rules", "llm"]
DecisionSource = Literal["rules", "llm", "human", "system"]

# Métrique principale par type de tâche : (nom, "plus grand = meilleur")
PRIMARY_METRIC: dict[str, tuple[str, bool]] = {
    "binary": ("f1_macro", True),
    "multiclass": ("f1_macro", True),
    "regression": ("rmse", False),
}


class AgentError(Exception):
    """Levée par un agent en cas d'échec : le pipeline s'arrête et notifie."""


# --------------------------------------------------------------------------
# Chemins MinIO (un seul endroit pour éviter les divergences)
# --------------------------------------------------------------------------
def raw_key(dataset: str, version: int, filename: str = "data.csv") -> str:
    return f"{dataset}/v{version}/{filename}"


def clean_key(dataset: str, version: int, filename: str = "clean.csv") -> str:
    return f"{dataset}/v{version}/{filename}"


def registry_prefix(dataset: str, model_version: str) -> str:
    """Contient model.joblib, schema.json et metadata.json."""
    return f"{dataset}/{model_version}"


def run_state_key(run_id: str) -> str:
    return f"{run_id}/state.json"


# --------------------------------------------------------------------------
# Configuration du dataset (lue depuis dataset.yaml)
# --------------------------------------------------------------------------
class DatasetConfig(TypedDict, total=False):
    name: str
    target: str  # colonne à prédire
    task: str  # "auto" | "binary" | "multiclass" | "regression"
    sensitive_features: list[str]  # optionnel : active le test d'équité


# --------------------------------------------------------------------------
# Traçabilité : chaque décision d'agent est enregistrée
# --------------------------------------------------------------------------
class Decision(TypedDict):
    ts: str
    agent: str
    step: str
    decision: str
    rationale: str
    source: DecisionSource


def make_decision(
    agent: str,
    step: str,
    decision: str,
    rationale: str,
    source: DecisionSource = "rules",
) -> Decision:
    return Decision(
        ts=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        agent=agent,
        step=step,
        decision=decision,
        rationale=rationale,
        source=source,
    )


# --------------------------------------------------------------------------
# Sections de l'état partagé (une section par agent)
# --------------------------------------------------------------------------
class DataSection(TypedDict, total=False):  # écrite par Agent Data
    raw_uri: str
    clean_uri: str
    dataset_hash: str  # sha256 du CSV nettoyé
    target: str
    task_type: TaskType
    n_rows_raw: int
    n_rows_clean: int
    dropped_columns: list[str]
    profile: dict[str, Any]
    cleaning_report: dict[str, Any]
    warnings: list[str]


class Candidate(TypedDict):
    name: str  # doit appartenir à la liste blanche ALLOWED_ESTIMATORS
    params: dict[str, Any]
    reason: str


class CandidateResult(TypedDict):
    name: str
    params: dict[str, Any]
    cv_mean: float  # métrique principale, validation croisée
    cv_std: float
    fit_seconds: float


class TrainingSection(TypedDict, total=False):  # écrite par Agent Training
    mode_used: AgentMode  # "rules" aussi si le LLM a échoué (repli)
    candidates: list[Candidate]
    results: list[CandidateResult]
    best: Candidate
    mlflow_run_id: str
    model_uri: str  # modèle complet (préprocesseur + estimateur)


class QASection(TypedDict, total=False):  # écrite par Agent QA
    primary_metric: str
    metrics: dict[str, float]
    dummy_metrics: dict[str, float]
    production_metrics: dict[str, float] | None  # None si 1er modèle
    robustness: dict[str, float]
    drift: dict[str, Any]
    fairness: dict[str, float] | None  # None si pas de colonnes sensibles
    report_uri: str


class GateSection(TypedDict, total=False):  # écrite par le quality gate
    decision: Literal["promote", "reject"]
    reasons: list[str]
    checks: dict[str, bool]


class ApprovalSection(TypedDict, total=False):  # écrite par l'IHM
    status: Literal["pending", "approved", "rejected"]
    by: str
    at: str
    comment: str


class ReleaseSection(TypedDict, total=False):  # écrite par Agent Release
    model_version: str
    image: str
    deployment: str
    strategy: str
    smoke_test_ok: bool
    rolled_back: bool


class PipelineState(TypedDict, total=False):
    run_id: str
    dataset_name: str
    dataset_version: int
    config: DatasetConfig
    agent_mode: AgentMode
    git_commit: str
    status: Status
    current_step: str
    error: str | None
    data: DataSection
    training: TrainingSection
    qa: QASection
    gate: GateSection
    approval: ApprovalSection
    release: ReleaseSection
    # Les décisions s'accumulent : chaque agent renvoie {"decisions": [...]}
    decisions: Annotated[list[Decision], operator.add]