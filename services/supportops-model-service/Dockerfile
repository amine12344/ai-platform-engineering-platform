ARG PYTHON_IMAGE=python:3.13.11-slim
FROM ${PYTHON_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN groupadd --gid 10002 supportops \
    && useradd --uid 10002 --gid 10002 --create-home supportops

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

COPY src ./src

USER 10002:10002
EXPOSE 8081

CMD ["uvicorn", "supportops_model_service.main:app", "--app-dir", "/app/src", "--host", "0.0.0.0", "--port", "8081"]
