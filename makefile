
POETRY_VERSION := 1.8.5
CLI_NAME := "oss4climate.cli"

.PHONY: install
install:
	pip install pipx
	pipx ensurepath
	pipx install poetry==$(POETRY_VERSION) || echo "Poetry already installed"
	poetry config virtualenvs.create true 
	poetry install --no-cache
	
.PHONY: install_dev
install_dev:
	uv sync

.PHONY: add
add:
	uv run typer $(CLI_NAME) run add

.PHONY: build
build:
	uv lock

.PHONY: discover
discover:
	uv run typer $(CLI_NAME) run discover

.PHONY: generate_listing
generate_listing:
	# Note: typer processes "_" as "-"
	uv run typer $(CLI_NAME) run generate-listing	

.PHONY: publish
publish:
	uv run typer $(CLI_NAME) run publish

.PHONY: search
search:
	uv run typer $(CLI_NAME) run search

.PHONY: download_data
download_data:
	uv run typer $(CLI_NAME) run download-data

.PHONY: run_app
run_app:
	uv run gunicorn -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8080 app:app

.PHONY: help
help:
	uv run typer $(CLI_NAME) run --help

.PHONY: test
test:
	uv run pytest src/.