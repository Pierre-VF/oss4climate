
CLI_NAME := "oss4climate_scripts.cli"

.PHONY: install
install:
	uv sync --all-groups


.PHONY: build
build:
	uv lock

.PHONY: code_cleanup
code_cleanup:
	uv tool run pre-commit install
	uv tool run pre-commit run --all

.PHONY: run_app
run_app:
	uv run gunicorn -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000 app:app

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

.PHONY: seed_typesense
seed_typesense:
	uv run src/oss4climate_app/seed_typesense.py


# ----------------------------------------------------------------------------
# Kept for legacy reasons (backwards compatibility)
# ----------------------------------------------------------------------------
.PHONY: check_code
check_code:
	make code_cleanup
