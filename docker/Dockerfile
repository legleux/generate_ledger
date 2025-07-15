ARG PY_VERSION=3.13
FROM python:${PY_VERSION}-slim-bookworm

ENV PYTHONUNBUFFERED=1

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /opt/generate_ledger

COPY . /opt/generate_ledger

RUN uv sync

ENV PATH="/opt/generate_ledger/.venv/bin:$PATH"

# CMD ["python", "version"]
