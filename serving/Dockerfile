FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY agents ./agents
COPY baseline ./baseline
COPY config ./config
COPY orchestrator ./orchestrator
COPY serving ./serving
RUN python -m baseline.run_pipeline
EXPOSE 8000
CMD ["uvicorn", "serving.app:app", "--host", "0.0.0.0", "--port", "8000"]
