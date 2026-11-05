"""Non-agentic reference implementation of the same workflow."""
from agents.data_agent import load_data
from agents.training_agent import train_and_evaluate
from agents.qa_agent import evaluate_quality
from agents.release_agent import release_model


def run() -> dict:
    data = load_data()
    result = train_and_evaluate(data)
    quality = evaluate_quality(result["metrics"])
    artifact_path = release_model(result, quality) if quality["passed"] else None
    return {"metrics": result["metrics"], "quality": quality, "artifact_path": artifact_path}


if __name__ == "__main__":
    print(run())
