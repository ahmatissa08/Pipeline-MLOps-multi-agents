# Contrat d'interfaces : pipeline MLOps multi-agents

Ce document et `core/contract.py` sont la référence commune. Toute modification passe par une Pull Request relue par les deux autres membres.

## 1. Périmètre

Le pipeline traite **un dataset tabulaire (CSV) d'apprentissage supervisé** : classification binaire, classification multiclasse ou régression. Hors périmètre : images, texte, séries temporelles. L'utilisateur fournit le CSV et un fichier `dataset.yaml` ; le pipeline détecte le type de tâche, propose des algorithmes, entraîne, vérifie, puis déploie après approbation humaine.

## 2. Responsabilités

| Membre | Blocs | Fichiers |
|---|---|---|
| **Hereta** | Agent Data, Agent Training, accès LLM | `agents/data_agent.py`, `agents/training_agent.py`, `core/profiling.py`, `core/modeling.py`, `core/llm.py` |
| **Ahmat** | Orchestrateur, Agent QA, quality gate, baseline | `orchestrator/graph.py`, `agents/qa_agent.py`, `core/gate.py`, `config/quality_gate.yaml`, `baseline/run_pipeline.py` |
| **Clement** | Agent Release, serving, Kubernetes, CI/CD, IHM | `agents/release_agent.py`, `serving/`, `k8s/`, `.github/workflows/`, `ui/app.py` |
| **Partagé** | Contrat, stockage, découpage train/test | `core/contract.py`, `core/storage.py`, `core/split.py` |

## 3. Organisation de MinIO

```
raw-data/<dataset>/v<N>/data.csv          # dépôt de l'utilisateur
raw-data/<dataset>/v<N>/dataset.yaml
clean-data/<dataset>/v<N>/clean.csv       # sortie de l'Agent Data
clean-data/<dataset>/v<N>/profile.json
model-registry/<dataset>/<version>/model.joblib
model-registry/<dataset>/<version>/schema.json
model-registry/<dataset>/<version>/metadata.json
pipeline-runs/<run_id>/state.json         # état de l'exécution, lu par l'IHM
mlflow/                                   # artefacts MLflow
```

Nouveau bucket à créer : `docker exec silo mcli mb local/pipeline-runs`.

## 4. `dataset.yaml`

```yaml
name: adult
target: class
task: auto                       # auto | binary | multiclass | regression
sensitive_features: [sex, race]  # optionnel : active le test d'équité
```

Si le fichier est absent, l'Agent Data propose la dernière colonne comme cible et le signale dans `warnings` : l'IHM demande confirmation à l'humain.

## 5. État partagé et traçabilité

Défini dans `core/contract.py` (`PipelineState`). Règles :
- un agent **lit** tout l'état mais **n'écrit que sa section** (`data`, `training`, `qa`, `gate`, `release`) et `decisions` ;
- chaque agent renvoie un dictionnaire partiel, par exemple `{"data": {...}, "decisions": [make_decision(...)]}` ;
- l'orchestrateur écrit l'état complet dans `pipeline-runs/<run_id>/state.json` **après chaque étape** ;
- tout échec lève `AgentError` : le pipeline s'arrête, `status = FAILED`, et une notification est émise.

Découpage train/test : **une seule fonction**, `core/split.py::split_data(df, target, task_type)`, avec `SEED = 42`, `TEST_SIZE = 0.2` et stratification pour la classification. Training et QA l'appellent tous les deux, donc ils utilisent exactement le même jeu de test.

## 6. Signatures des agents

### Agent Data (Hereta)

```python
# agents/data_agent.py
def run(state: PipelineState) -> dict: ...
#   lit  : state["dataset_name"], ["dataset_version"], ["config"]
#   écrit: state["data"] (DataSection) + decisions

# core/profiling.py
def profile_dataframe(df, target: str) -> dict: ...
#   types, manquants par colonne, cardinalité, doublons, colonnes constantes,
#   colonnes de type identifiant, valeurs extrêmes
def detect_task(y, declared: str = "auto") -> tuple[TaskType, list[str]]: ...
#   renvoie (type de tâche, avertissements) ; cas ambigus signalés, jamais tranchés en silence
def clean_dataframe(df, target: str) -> tuple["DataFrame", dict]: ...
#   NON-FUITE : ne fait que doublons, colonnes constantes/identifiant, valeurs invalides.
#   L'imputation et l'encodage se font dans le Pipeline sklearn (voir Training).
def compute_hash(df) -> str: ...   # sha256 du CSV canonique
```

### Agent Training (Hereta)

```python
# agents/training_agent.py
def run(state: PipelineState) -> dict: ...
#   lit  : state["data"], state["agent_mode"]
#   écrit: state["training"] (TrainingSection) + decisions

# core/modeling.py
ALLOWED_ESTIMATORS: dict[str, list[str]] = {
    "binary":     ["logistic_regression", "random_forest", "hist_gradient_boosting"],
    "multiclass": ["logistic_regression", "random_forest", "hist_gradient_boosting"],
    "regression": ["ridge", "random_forest", "hist_gradient_boosting"],
}
def propose_candidates(profile: dict, task_type: TaskType, mode: AgentMode) -> list[Candidate]: ...
def build_pipeline(profile: dict, name: str, params: dict): ...
#   sklearn Pipeline = ColumnTransformer (imputation + encodage + échelle) + estimateur
def cross_validate_candidates(df, target, task_type, candidates) -> list[CandidateResult]: ...
def train_final(df, target, task_type, best: Candidate, profile: dict): ...
#   journalise paramètres, métriques, graine et versions de dépendances dans MLflow
```

### Agent QA (Ahmat)

```python
# agents/qa_agent.py
def run(state: PipelineState) -> dict: ...
#   lit  : state["training"]["model_uri"], state["data"], state["config"]
#   écrit: state["qa"] (QASection) + decisions
#   contenu : métriques sur le jeu de test, comparaison à un modèle trivial (Dummy),
#   comparaison au modèle en production (si existant), robustesse (bruit sur les
#   variables numériques), dérive (Evidently), équité (Fairlearn, seulement si
#   sensitive_features est déclaré)
```

### Quality gate (Ahmat)

```python
# core/gate.py
def evaluate_gate(qa: QASection, cfg: dict, task_type: TaskType) -> GateSection: ...
```

### Agent Release (Clement)

```python
# agents/release_agent.py
def run(state: PipelineState) -> dict: ...
#   PRÉCONDITION : state["approval"]["status"] == "approved", sinon AgentError
#   étapes : enregistrement dans model-registry -> build image -> push ->
#            déploiement progressif Kubernetes -> test de fumée -> rollback si échec
#   écrit: state["release"] (ReleaseSection) + decisions
```

Seul cet agent a le droit de modifier le cluster.

### Orchestrateur (Ahmat)

```
data -> training -> qa -> gate
gate = reject   -> fin, status = REJECTED
gate = promote  -> attente d'approbation humaine (status = WAITING_APPROVAL)
approval        -> approved -> release -> fin (SUCCEEDED) ; rejected -> fin (REJECTED)
AgentError n'importe où -> notification, status = FAILED
```

## 7. Mode « règles » ou « LLM » (approche hybride)

- Variable d'environnement `AGENT_MODE` = `rules` (défaut) ou `llm`. Le mode est enregistré dans l'état.
- `rules` : `propose_candidates` applique une table de décision (taille du dataset, déséquilibre, types de colonnes). Aucun accès réseau.
- `llm` : le modèle reçoit le **profil du dataset** (jamais les données brutes) et renvoie du JSON : liste de candidats et justification. La sortie est **validée contre `ALLOWED_ESTIMATORS`** ; tout nom inconnu est rejeté.
- **Repli obligatoire** : si le LLM échoue, est indisponible ou renvoie du JSON invalide, on bascule sur `rules` et on le consigne (`mode_used = "rules"`, décision avec `source = "system"`).
- Un LLM ne reçoit **aucun outil** capable de toucher au cluster ni au registre. Il propose, les scripts exécutent.

## 8. Quality gate (`config/quality_gate.yaml`)

Les seuils absolus n'ont pas de sens sur un dataset arbitraire : le gate est **relatif**. Les valeurs ci-dessous sont des points de départ à calibrer sur les datasets de test.

```yaml
classification:                 # binary et multiclass ; métrique : f1_macro
  min_gain_over_dummy: 0.10
  max_regression_vs_production: 0.02
  max_metric_drop_under_noise: 0.05
  fairness:
    max_demographic_parity_difference: 0.20   # appliqué seulement si sensitive_features
regression:                     # métrique : rmse (plus petit = meilleur)
  min_gain_over_dummy: 0.10     # réduction relative du RMSE vs prédire la moyenne
  max_regression_vs_production: 0.05
  max_metric_drop_under_noise: 0.10
human_approval:
  required: true
```

Le sujet indique que seul l'agent Release modifie le cluster, et uniquement après approbation humaine : l'approbation reste donc **toujours requise**, même si le gate est favorable.

## 9. Registre de modèles : `metadata.json`

```json
{
  "dataset_name": "adult", "dataset_version": 1, "dataset_hash": "sha256:...",
  "task_type": "binary", "target": "class",
  "algorithm": "hist_gradient_boosting", "params": {},
  "metrics": {"f1_macro": 0.0}, "git_commit": "...",
  "author": "...", "created_at": "...", "mlflow_run_id": "...", "run_id": "...",
  "gate_decision": "promote", "approved_by": "..."
}
```

`schema.json` liste les colonnes d'entrée (nom, type). `model.joblib` contient le **Pipeline complet** (préprocesseur + estimateur) : l'API n'a donc besoin d'aucune logique propre à un dataset.

## 10. API de serving (Clement)

Configurée par `MODEL_URI` (variable d'environnement). Le schéma d'entrée est lu dans `schema.json`.

| Route | Rôle |
|---|---|
| `GET /health` | état du service |
| `GET /schema` | colonnes attendues, type de tâche, version du modèle |
| `POST /predict` | corps `{"records": [{...}]}` → `{"predictions": [...], "model_version": "..."}` ; erreur 422 si des colonnes manquent |

## 11. CI/CD : décisions à prendre (Ahmat et Clement)

- Un runner GitHub hébergé **n'atteint pas** le `localhost` de nos machines. Soit la CI lance Silo et MLflow dans le job (`docker compose up`) puis un cluster `kind` éphémère, soit on utilise un runner auto-hébergé sur la machine de l'un de nous.
- Le job ne peut pas attendre l'humain pendant des heures. Option retenue par défaut : **deux phases**. Phase A (déclenchée par la CI, paramètre `dataset_name`) : data → training → qa → gate, état sauvegardé en `WAITING_APPROVAL`. Phase B (déclenchée après clic dans l'IHM) : release.
- Dans tous les cas, `pytest` s'exécute avant le pipeline.

## 12. Baseline non agentique et protocole de comparaison

Baseline (`baseline/run_pipeline.py`) : les **mêmes fonctions de `core/`** enchaînées par un script, avec un algorithme fixe, sans orchestrateur, sans LLM, sans gate. La comparaison reste ainsi équitable.

À mesurer sur **au moins trois datasets** (Adult pour la classification binaire avec équité, Wine pour le multiclasse, California Housing ou Diabetes pour la régression), avec la même graine :
- qualité du modèle (métrique principale, sur le même jeu de test) ;
- temps total d'exécution ;
- problèmes détectés (dérive, régression, biais) et empêchés d'atteindre la production ;
- traçabilité (décisions enregistrées, reproductibilité) ;
- effort humain.

## 13. Règles Git

- Une branche par fonctionnalité : `feat/agent-data`, `feat/agent-training`, `feat/orchestrator`, `feat/agent-qa`, `feat/release-k8s`, `feat/ui`.
- Pas de commit direct sur `main` : Pull Request relue par un autre membre.
- Chacun écrit les tests `pytest` de son bloc dans `tests/`.
- Configurer l'identité avant le premier commit : `git config --global user.name` et `user.email` (adresse du compte GitHub).

## 14. Questions ouvertes

1. Fournisseur LLM : clé d'API ou modèle local ? Le mode `rules` fonctionne sans.
2. CI/CD : runner auto-hébergé ou cluster éphémère dans le job ?
3. Seuils du quality gate : à calibrer après les premiers résultats.
