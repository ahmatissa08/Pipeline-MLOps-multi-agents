"""Persist a model only after its quality gate passes."""
from pathlib import Path
import joblib


def release_model(result: dict, quality: dict, artifact_path: str = "artifacts/model.joblib") -> str:
    if not quality["passed"]:
        raise ValueError(f"Quality gate failed: {quality['checks']}")
    path = Path(artifact_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": result["model"], "feature_names": result["feature_names"],
                 "target_names": result["target_names"], "metrics": result["metrics"]}, path)
    return str(path)
