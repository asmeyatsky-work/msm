FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .
USER 1000:1000
EXPOSE 8080
CMD ["python", "-m", "msm_activation"]
