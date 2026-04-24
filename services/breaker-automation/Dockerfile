# Cloud Functions (2nd gen) image. functions-framework hosts the entry point.
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .
ENV FUNCTION_TARGET=on_anomaly
ENV FUNCTION_SOURCE=/app/src/msm_breaker/presentation/function.py
USER 1000:1000
CMD ["functions-framework", "--target=on_anomaly", "--port=8080"]
