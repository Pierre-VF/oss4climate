
CLI_NAME := "oss4climate_scripts.cli"

.PHONY: install
install:
	uv sync --all-groups

.PHONY: add
add:
	uv run typer $(CLI_NAME) run add

.PHONY: build
build:
	uv lock

.PHONY: code_cleanup
code_cleanup:
	uv tool run pre-commit install
	uv tool run pre-commit run --all

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

.PHONY: test_with_coverage
test_with_coverage:
	uv run coverage run -m pytest src/test/.
	uv run coverage html --omit=src/test/* --omit=notebooks/*
	echo "Exposing on http://localhost:9001/"
	uv run python -m http.server 9001 --directory htmlcov/

# CLI entries
cli_help:
	uv run typer $(CLI_NAME) run --help

cli_optimise:
	uv run typer $(CLI_NAME) run optimise


# ----------------------------------------------------------------------------
# Kept for legacy reasons (backwards compatibility)
# ----------------------------------------------------------------------------
.PHONY: check_code
check_code:
	make code_cleanup
