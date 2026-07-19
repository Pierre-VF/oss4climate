# Scraping Process

This document describes the scraping pipeline for OSS4Climate repositories.

## Overview

The scraping process manages the collection of metadata from Git hosting platforms (GitHub, GitLab, Codeberg, Bitbucket) and stores it in a SQLModel-backed database. The pipeline is orchestrated by the `RepositoryScraper` class.

## Architecture

```
TOML Index (source of truth)
    │
    ▼
RepositoryScraper.sync_from_toml()          ← per-platform sync with interruption tolerance
    │
    ├──► GitHub organisations → commit after each org
    ├──► GitLab groups        → commit after each group
    ├──► Codeberg organisations  (org records only; no detailed scraping)
    └──► Bitbucket projects   → commit after each project
    │
    ▼ mark_repos_inactive()                    ← prune repos removed from TOML
RepositoryScraper.scrape_active_repos()      ← per-repo streaming within platform buckets
    │
    ├──► GitHub scraper (rate limit break-out)
    ├──► GitLab scraper
    ├──► Codeberg scraper  (NotImplementedError → logged as failure)
    └──► Bitbucket scraper (NotImplementedError → logged as failure)
    │
    ▼ RepositoryScraper.export_*()             ← CSV / JSON / Feather + summary TOML + failures TOML
```

## Database Schema

### Organisations Table

Stores metadata about organisations/groups from Git hosting platforms.

| Column | Type | Description |
|--------|------|-------------|
| `id` | string (PK) | Format: `"host/org_path"` (e.g., `"github.com/oss4climate"`) |
| `name` | string | Organisation name |
| `description` | string | Organisation description |
| `url` | string | Organisation URL |
| `created_at` | datetime | Creation timestamp |
| `updated_at` | datetime | Last update timestamp |
| `public_repos` | integer | Number of public repositories |
| `total_private_repos` | integer | Number of private repositories |
| `has_organization_projects` | boolean | Whether org has projects |
| `blog` | string | Organisation blog URL |
| `location` | string | Organisation location |
| `email` | string | Organisation email |
| `last_scraped_at` | datetime | Last successful scrape timestamp |
| `last_error` | string | Last error message (NULL if no error) |
| `error_count` | integer | Number of consecutive errors (NULL if no error) |

### Repositories Table

Stores metadata about individual repositories.

| Column | Type | Description |
|--------|------|-------------|
| `id` | string (PK) | Format: `"host/repo_path"` (e.g., `"github.com/oss4climate/oss4climate"`) |
| `organisation_id` | string (FK) | Reference to organisations.id |
| `name` | string | Repository name |
| `url` | string | Full repository URL |
| `website` | string | Project website URL |
| `description` | string | Repository description |
| `licence` | string | Licence name |
| `licence_url` | string | Licence file URL |
| `latest_update` | date | Last update date |
| `last_commit` | date | Last commit date |
| `language` | string | Dominant programming language |
| `all_languages` | text | JSON array of all languages (stored as JSON-encoded string) |
| `open_pull_requests` | integer | Number of open PRs |
| `master_branch` | string | Default branch name |
| `readme` | text | Cleaned README content (search plaintext) |
| `readme_type` | string | README type: `"md"`, `"rst"`, `"html"`, `"?"` |
| `is_fork` | boolean | Whether the repo is a fork |
| `forked_from` | string | URL of the original repo (if forked) |
| `last_scraped_at` | datetime | Last successful scrape timestamp |
| `last_error` | string | Last error message (NULL if no error) |
| `error_count` | integer | Number of consecutive errors (NULL if no error) |
| `disappeared_on` | date | Date repo was marked inactive (NULL if active) |
| `active` | boolean | Whether the repo is currently in scope (`True` by default) |

## Configuration

### Database URL

The repository database URL is configured via the `REPOS_DATABASE_URL` environment variable or config setting.

- **Default**: `sqlite:///.data/repos.sqlite`
- **PostgreSQL example**: `postgresql+psycopg2://user:pass@host:5432/oss4climate_repos`

### Refresh Interval and Cache Lifetime

The default refresh interval is **28 days**. Repositories are re-scraped if:
- They have never been scraped (`last_scraped_at IS NULL`), OR
- Their last scrape was more than `refresh_days` ago

Override with the constructor parameters:

```python
scraper = RepositoryScraper(refresh_days=7, cache_lifetime=None)  # Re-scrape every 7 days; use default TTL for API caching
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `refresh_days` | `28` | Days since last scrape before re-scraping |
| `cache_lifetime` | `None` (uses platform defaults) | Optional cache lifetime for HTTP responses from Git hosting APIs |

## Pipeline Stages

### 1. Sync from TOML

The `sync_from_toml()` method reconciles the database with the TOML index file:

```python
targets = ParsingTargets.from_toml(toml_path)
```

It processes each platform in sequence, committing after every successful organisation/group for interruption tolerance:

1. **GitHub** — `_sync_github_organisations()`: For each GitHub org URL from the TOML, fetch metadata via `GithubScraper.fetch_organisation_details()` and upsert into the organisations table. Then discover repos via `fetch_repositories_in_organisation()` and upsert them with organisation_id set. Commit after each successful org.
2. **GitLab** — `_sync_gitlab_groups()`: For each GitLab group URL, fetch metadata via direct API call (`/api/v4/groups/{path}`) and discover repos via `fetch_repositories_in_group()`. Same commit-after-each pattern.
3. **Codeberg** — `_sync_codeberg_organisations()`: Only upserts the org record with its ID (no detailed scraping yet). No error persistence on failure — just logs a warning.
4. **Bitbucket** — `_sync_bitbucket_projects()`: Fetches project metadata via `/api/2.0/workspaces/{workspace}` and discovers repos via `fetch_repositories_in_group()`. Upserts errors on failure like GitHub/GitLab.

After all platforms are synced, explicit repositories listed in the TOML (per-platform) are upserted with minimal data (`id`, `url`). Finally:
5. **Prune inactive** — `mark_repos_inactive()` marks any active repo not found across all platform syncs as inactive (`active = False`, `disappeared_on = today`).

**Error handling**: GitHub and GitLab failures log a warning, upsert the org with error info (last_error + error_count), then continue. Codeberg silently logs warnings without persisting errors to the DB. Bitbucket mirrors the GitHub/GitLab pattern of persisting errors on failure. Each platform's sync loop commits after every individual organisation/group so that partial progress survives interruptions.

### 2. Scrape Active Repositories

The `scrape_active_repos()` method fetches fresh data for repositories past their refresh threshold:

1. **Query DB**: Get all active repos where `last_scraped_at IS NULL OR last_scraped_at < now() - timedelta(days=refresh_days)`.
2. **Group by platform**: Separate repo IDs into per-platform lists (GitHub, GitLab entries as `(url, id)` pairs, Codeberg, Bitbucket). Log a breakdown of counts per platform.
3. **Stream within each bucket** — processes repos one at a time with immediate DB commits:

   - **GitHub**: For each `repo_id`, calls `GithubScraper.fetch_project_details(repo_id)`. On `RateLimitError` (403), skips all remaining GitHub repos and records errors for them. On other exceptions, sets the error in the DB via `set_repo_error()` and continues to next repo.
   - **GitLab**: Same per-repo streaming pattern but without rate limit break-out — failures on one provider do not block others.
   - **Codeberg / Bitbucket**: Calls their respective scrapers' `fetch_project_details()`. Both currently raise `NotImplementedError`, so every scrape attempt for these platforms will be recorded as a failure with the error message set in DB via `set_repo_error()`.

4. For each successful fetch, `_project_details_to_dict()` converts the `ProjectDetails` object to a dict (serialising `all_languages` list → JSON string, converting `readme_type` enum → value), then upserts into the repositories table with `last_scraped_at`, `active = True`, and resets error fields via `reset_repo_error()`.

5. Returns `{repo_id: error_message}` dict for all failures.

**Interruption tolerance**: Every repo result is committed immediately to its own session, so partial progress survives process termination or Ctrl+C. Rate limit break-out only affects the GitHub bucket — other platforms continue unaffected.

### 3. Export Results

The export methods write results from the database:

- **`export_to_feather(output_path)`**: Reads all active repos and writes to a file based on extension:
  - `.feather`: Binary feather format (index set to `id`)
  - `.csv`: Semicolon-delimited CSV (`readme` column dropped)
  - `.json`: Transposed JSON object

- **`export_summary_toml(output_path)`**: Generates summary statistics including repository count, organisation count, unique languages list, and licence list. Uses tomlkit for formatting with sorted keys.

- **`export_failures_toml(output_path)`**: Queries active repos where `last_error IS NOT NULL`, writes `{repo_id: error_message}` pairs under a `"failures"` key in TOML format.

## Running the Scraper

### From Python (direct)

```python
from oss4climate.src.repository_scraper import RepositoryScraper

scraper = RepositoryScraper(refresh_days=28, cache_lifetime=None)
scraper.run(
    toml_path="index.toml",
    feather_output=".data/listing_data.feather",  # or .csv / .json
    summary_output=".data/summary.toml",
    failures_output=".data/failures_scraping.toml",
)
```

### From CLI (via scrape_all)

```python
from oss4climate_scripts.scripts.repository_scraping import scrape_all

scrape_all(
    target_output_file=None,  # defaults to FILE_OUTPUT_LISTING_FEATHER from app config
    fail_on_issue=False,      # if True, raises on scraping failures
    refresh_days=28,          # days between re-scrapes
)
```

The `scrape_all` function:
1. Determines the output file path (defaults to feather format; CSV/JSON extensions are auto-converted internally).
2. Runs the full pipeline via `RepositoryScraper.run()`.
3. Formats all generated files using pre-commit tooling (`scripts.format_all_files()` and `scripts.format_individual_file()` for failures TOML).

## Data Flow to Typesense

The Typesense indexer reads from the repository database:

1. Query active repositories via `get_repos_for_typesense(session)` — returns a list of dicts with fields: `id`, `name`, `description`, `readme`, `organisation_id`, `licence`, `language`, `url`, `last_commit`, `is_fork`.
2. Index documents into Typesense for search functionality.

## Data Flow to App

The app reads from Typesense (not directly from the database). The Typesense index is the app's data source. The database is the source of truth for scraped data, and Typesense serves as the search layer on top.

## Platform Support

| Platform | Organisation Discovery | Repository Scraping | README Fetching |
|----------|----------------------|---------------------|-----------------|
| GitHub | Yes (full metadata) | Yes (`fetch_project_details`) | N/A — handled by `ProjectDetails` model |
| GitLab | Yes (via `/api/v4/groups/{path}` API) | Yes (`fetch_project_details`) | N/A — handled by `ProjectDetails` model |
| Codeberg | Partial (org record only; no metadata fetch) | NotImplementedError → failure logged | No (`NotImplementedError`) |
| Bitbucket | Yes (via `/api/2.0/workspaces/{workspace}` API) | NotImplementedError → failure logged | No (`fetch_repository_readme` raises `NotImplementedError`) |

Only GitHub and GitLab scrapers are fully implemented for repository data fetching. Codeberg organisation discovery creates org records without metadata; Bitbucket discovers repos but cannot scrape their details yet. All four platforms participate in the sync phase (TOML reconciliation), ensuring that even unsupported platform repos remain tracked as active/inactive based on TOML membership alone.

## Error Tracking

Both organisations and repositories track errors:

- `last_error`: The most recent error message (`NULL` if no error)
- `error_count`: Number of consecutive errors (`NULL` if no error; incremented by 1 per failure via `(repo.error_count or 0) + 1`)

On successful scrape, both fields are reset to NULL. On failure, `last_error` is set and `error_count` is incremented. Error records for organisations during sync are persisted even on interruption (commit after each org/group). Repository errors from scraping are committed immediately per-repo within their platform bucket.

## Database Files

| File | Purpose |
|------|---------|
| `.data/repos.sqlite` | Repository and organisation data (SQLModel tables) |
| `.data/db.sqlite` | API response cache (TTL-based, separate from repo data) |
