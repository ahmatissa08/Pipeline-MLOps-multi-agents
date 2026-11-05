# MLOps Agents

Démonstrateur de pipeline de machine learning comparant une orchestration LangGraph et une exécution baseline. Le jeu Breast Cancer Wisconsin de scikit-learn est utilisé localement, sans téléchargement.

## Prérequis

Python 3.11 recommandé.

## Installation et lancement

```bash
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python -m baseline.run_pipeline
streamlit run ui/app.py
```

Le pipeline publie le modèle dans `artifacts/model.joblib` si les seuils définis dans `config/quality_gate.yaml` sont atteints. L’API démarre avec `uvicorn serving.app:app --reload` et expose `/health` et `/predict`.

## API

`POST /predict` reçoit un tableau `features` contenant les 30 valeurs du jeu de données, dans l’ordre fourni par scikit-learn. `/docs` expose la documentation interactive.

## Conteneurs

Générer d’abord l’artefact en local, puis lancer `docker compose up --build`. L’image monte `artifacts/` pour servir le modèle. Le manifeste Kubernetes déploie l’API et un Service interne.

## CI

GitHub Actions exécute la baseline puis les tests unitaires à chaque push ou pull request.
