FROM python:3.13-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1
WORKDIR /opt/generate_ledger

COPY . /opt/generate_ledger

RUN uv sync

ENV PATH="/opt/generate_ledger/.venv/bin:$PATH"

# CMD ["python", "ledger"]
