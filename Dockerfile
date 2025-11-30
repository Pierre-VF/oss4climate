FROM ghcr.io/astral-sh/uv:0.9.13-bookworm-slim
WORKDIR /home
# Copying files over
# Index folder creation is required for operation when the indexes aren't present
RUN mkdir -p /home/app/indexes
COPY src/ pyproject.toml uv.lock .python-version README.md app.py app/
# Removing caching to keep the image lightweight
ENV UV_NO_CACHE=1
WORKDIR /home/app
# Install dependencies missing in slim images and then running the install
RUN apt-get update
RUN apt-get install -y ca-certificates
RUN update-ca-certificates
RUN uv sync --all-groups
# Run app
LABEL organisation="oss4climate"
EXPOSE 8080
ENV UV_LOCKED=1
CMD ["uv", "run", "gunicorn", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8080", "app:app"]
