ARG MLFLOW_BASE_IMAGE=ghcr.io/mlflow/mlflow:v3.15.0-full

FROM ${MLFLOW_BASE_IMAGE}

RUN python -m pip install --no-cache-dir \
    boto3==1.38.8 \
    psycopg2-binary==2.9.10

USER 1000:1000