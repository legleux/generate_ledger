ARG PY_VERSION=3.13
ARG DISTRO=slim-trixie
# ARG UV_VERSION=
FROM python:${PY_VERSION}-${DISTRO}
# FROM python:${PY_VERSION}-slim-bookworm
# COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1
WORKDIR /opt/generate_ledger

COPY . /opt/generate_ledger
RUN --mount=from=ghcr.io/astral-sh/uv,source=/uv,target=/bin/uv \
    uv sync

ENV PATH="/opt/generate_ledger/.venv/bin:$PATH"
