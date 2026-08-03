ARG PYTHON_IMAGE=python:3.13.11-slim
FROM ${PYTHON_IMAGE} AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/opt/venv/bin:$PATH

RUN python -m venv /opt/venv \
    && useradd --create-home --uid 10001 --shell /usr/sbin/nologin supportops

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY src ./src
USER 10001:10001
EXPOSE 8080

CMD ["uvicorn", "supportops_api.main:app", "--app-dir", "/app/src", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers"]
