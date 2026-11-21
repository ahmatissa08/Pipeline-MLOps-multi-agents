# EXAMMLOPS : pipeline MLOps multi-agents

## Démarrage
```powershell
docker compose up -d
docker exec silo mcli alias set local http://127.0.0.1:9000 minioadmin minioadmin
docker exec silo mcli mb local/raw-data local/clean-data local/mlflow local/model-registry
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install pandas scikit-learn boto3
python scripts/upload_dataset.py
```
Interfaces : MLflow http://localhost:5000, console Silo http://localhost:9001

## Équipe
- Ahmat : orchestration, quality gate, IHM
- Hereta : agents Data, Training, QA
- Clement : agent Release, serving, CI/CD