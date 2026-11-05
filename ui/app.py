"""Streamlit interface to launch and inspect the MLOps pipeline."""
import streamlit as st
from orchestrator.graph import pipeline

st.set_page_config(page_title="MLOps Agents", page_icon="🤖")
st.title("Pipeline MLOps multi-agents")
st.write("Entraînement, contrôle qualité et publication d’un modèle de démonstration.")
if st.button("Lancer le pipeline", type="primary"):
    with st.spinner("Exécution du pipeline…"):
        state = pipeline.invoke({})
    if state.get("error"):
        st.error(state["error"])
    else:
        st.success(f"Modèle publié : {state['artifact_path']}")
        st.metric("Accuracy", f"{state['result']['metrics']['accuracy']:.3f}")
        st.json({"metrics": state["result"]["metrics"], "quality": state["quality"]})
