"""Load and split a small, local scikit-learn dataset for the demo pipeline."""
from sklearn.datasets import load_breast_cancer
from sklearn.model_selection import train_test_split


def load_data(test_size: float = 0.2, random_state: int = 42) -> dict:
    dataset = load_breast_cancer(as_frame=True)
    X_train, X_test, y_train, y_test = train_test_split(
        dataset.data, dataset.target, test_size=test_size,
        random_state=random_state, stratify=dataset.target,
    )
    return {
        "X_train": X_train, "X_test": X_test,
        "y_train": y_train, "y_test": y_test,
        "feature_names": list(dataset.feature_names),
        "target_names": list(dataset.target_names),
    }
