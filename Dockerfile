FROM ghcr.io/astral-sh/uv:0.13-debian-slim
WORKDIR /home/app
# Install dependencies missing in slim images and then running the install
RUN apt-get update
RUN apt-get install -y ca-certificates git
RUN update-ca-certificates
# Copying files over
# Index folder creation is required for operation when the indexes aren't present
RUN mkdir -p /home/app/indexes
COPY src/ indexes/ pyproject.toml uv.lock .python-version README.md app.py ./
# Removing caching to keep the image lightweight
ENV UV_NO_CACHE=1
WORKDIR /home/app
# Limit to relevant groups
RUN uv sync --group test --group app
# Run app
LABEL organisation="oss4climate"
EXPOSE 8080
ENV UV_LOCKED=1
# Setting up the local folder
ENV LOCAL_FOLDER=/home/app/.data
CMD ["uv", "run", "gunicorn", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8080", "app:app"]
