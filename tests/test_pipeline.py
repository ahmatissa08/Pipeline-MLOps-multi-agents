from agents.data_agent import load_data
from agents.training_agent import train_and_evaluate
from agents.qa_agent import evaluate_quality


def test_data_training_and_quality_gate():
    data = load_data()
    assert len(data["X_train"]) > 0
    result = train_and_evaluate(data)
    assert set(result["metrics"]) == {"accuracy", "precision", "recall", "f1"}
    quality = evaluate_quality(result["metrics"])
    assert isinstance(quality["passed"], bool)
