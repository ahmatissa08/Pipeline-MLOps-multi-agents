"""Train the baseline classifier and produce evaluation metrics."""
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score


def train_and_evaluate(data: dict, random_state: int = 42) -> dict:
    model = RandomForestClassifier(n_estimators=150, random_state=random_state, n_jobs=-1)
    model.fit(data["X_train"], data["y_train"])
    predictions = model.predict(data["X_test"])
    metrics = {
        "accuracy": float(accuracy_score(data["y_test"], predictions)),
        "precision": float(precision_score(data["y_test"], predictions, zero_division=0)),
        "recall": float(recall_score(data["y_test"], predictions, zero_division=0)),
        "f1": float(f1_score(data["y_test"], predictions, zero_division=0)),
    }
    return {"model": model, "metrics": metrics, "feature_names": data["feature_names"],
            "target_names": data["target_names"]}
