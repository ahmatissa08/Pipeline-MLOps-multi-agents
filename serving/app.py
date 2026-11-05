"""FastAPI inference service. Set MODEL_PATH to choose the model artifact."""
import os
from pathlib import Path
import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

MODEL_PATH = Path(os.getenv("MODEL_PATH", "artifacts/model.joblib"))
app = FastAPI(title="MLOps Model API", version="0.1.0")


class PredictionRequest(BaseModel):
    features: list[float]


def load_bundle():
    if not MODEL_PATH.exists():
        raise RuntimeError(f"Model artifact not found: {MODEL_PATH}. Run the pipeline first.")
    return joblib.load(MODEL_PATH)


@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": MODEL_PATH.exists()}


@app.post("/predict")
def predict(request: PredictionRequest):
    try:
        bundle = load_bundle()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    names = bundle["feature_names"]
    if len(request.features) != len(names):
        raise HTTPException(status_code=422, detail=f"Expected {len(names)} features")
    values = pd.DataFrame([request.features], columns=names)
    prediction = int(bundle["model"].predict(values)[0])
    probabilities = bundle["model"].predict_proba(values)[0].tolist()
    return {"prediction": prediction, "label": bundle["target_names"][prediction],
            "probabilities": probabilities}
