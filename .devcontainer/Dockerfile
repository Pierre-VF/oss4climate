FROM mcr.microsoft.com/devcontainers/python:1-3.13-bullseye
# Adding UV (make sure to keep tag in sync with production to avoid surprises)
COPY --from=ghcr.io/astral-sh/uv:0.6.14 /uv /uvx /bin/
# Adding caching for UV
ENV UV_CACHE_DIR=".cache/uv"
