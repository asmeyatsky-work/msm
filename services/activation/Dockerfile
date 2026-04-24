FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .
USER 1000:1000
# Invoked from Cloud Run jobs / Pub/Sub push subscription.
ENTRYPOINT ["python", "-m", "msm_activation"]
