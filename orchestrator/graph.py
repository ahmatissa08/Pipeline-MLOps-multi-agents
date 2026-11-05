"""LangGraph orchestration for the demo MLOps workflow."""
from typing import Any, TypedDict
from langgraph.graph import END, START, StateGraph
from agents.data_agent import load_data
from agents.training_agent import train_and_evaluate
from agents.qa_agent import evaluate_quality
from agents.release_agent import release_model


class PipelineState(TypedDict, total=False):
    data: dict[str, Any]
    result: dict[str, Any]
    quality: dict[str, Any]
    artifact_path: str
    error: str


def _data(state: PipelineState) -> dict:
    return {"data": load_data()}


def _train(state: PipelineState) -> dict:
    return {"result": train_and_evaluate(state["data"])}


def _qa(state: PipelineState) -> dict:
    return {"quality": evaluate_quality(state["result"]["metrics"])}


def _release(state: PipelineState) -> dict:
    quality = state["quality"]
    if not quality["passed"]:
        return {"error": f"Quality gate failed: {quality['checks']}"}
    return {"artifact_path": release_model(state["result"], quality)}


def build_graph():
    graph = StateGraph(PipelineState)
    graph.add_node("data", _data)
    graph.add_node("training", _train)
    graph.add_node("qa", _qa)
    graph.add_node("release", _release)
    graph.add_edge(START, "data")
    graph.add_edge("data", "training")
    graph.add_edge("training", "qa")
    graph.add_edge("qa", "release")
    graph.add_edge("release", END)
    return graph.compile()


pipeline = build_graph()
