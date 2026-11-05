"""Apply configurable quality gates to model metrics."""
from pathlib import Path
import yaml


def evaluate_quality(metrics: dict, config_path: str = "config/quality_gate.yaml") -> dict:
    with Path(config_path).open(encoding="utf-8") as stream:
        config = yaml.safe_load(stream) or {}
    thresholds = config.get("thresholds", {})
    checks = {name: metrics.get(name, 0.0) >= minimum for name, minimum in thresholds.items()}
    return {"passed": all(checks.values()), "checks": checks, "thresholds": thresholds}
