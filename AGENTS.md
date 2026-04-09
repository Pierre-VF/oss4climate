# AGENTS.md

## Setup commands

- Install dependencies: `uv sync --all-groups`
- Running python script named `xxx.py` : `uv run xxx.py`
- Run tests: `uv run pytest src/.`
- Code cleanup and styling: `uv tool run pre-commit install && uv tool run pre-commit run --all`

## Stack

- Backend and data analytics: Python, with UV for environment management.
- Frontend: HTML and CSS using Jinja2 templates served by Python's FastAPI
- Search engine: the search engine is powered by TypeSense

## Code style

- Docstrings use reStructuredText format
- Use object-oriented patterns where meaningful
- Code style is handled by pre-commits using the command above.

## Tests

All tests are located in the `src/test` folder. The folder structure follows the folder
structure under `src` in order to facilitate overview.

## Ignore

Agents must ignore all of the following files and folders:
- any file or folder covered by `.gitignore`
- any file within `.devcontainers/`, `search_backend/` and `indexes/`
