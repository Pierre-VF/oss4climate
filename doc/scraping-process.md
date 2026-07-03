# Scraping Process

This document describes the scraping pipeline for OSS4Climate repositories.

## Overview

The scraping process manages the collection of metadata from Git hosting platforms (GitHub, GitLab, Codeberg, Bitbucket) and stores it in a SQLModel-backed database. The pipeline is orchestrated by the `RepositoryScraper` class.

## Architecture

```
TOML Index (source of truth)
    │
    ▼
RepositoryScraper.sync_from_toml()
    │
    ├──► Organisations table (org metadata)
    │
    ├──► Repositories table (repo metadata)
    │
    ▼
RepositoryScraper.scrape_active_repos()
    │
    ├──► Platform scrapers (GitHub, GitLab, Codeberg, Bitbucket)
    │
    ▼
RepositoryScraper.export_*()
    │
    ├──► Feather file (for backward compatibility)
    ├──► Summary TOML
    └──► Failures TOML
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
| `twitter_username` | string | Twitter/X username |
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
| `license` | string | License name |
| `license_url` | string | License file URL |
| `latest_update` | date | Last update date |
| `last_commit` | date | Last commit date |
| `language` | string | Dominant programming language |
| `all_languages` | text | JSON array of all languages |
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
| `active` | boolean | Whether the repo is currently in scope |

## Configuration

### Database URL

The repository database URL is configured via the `REPOS_DATABASE_URL` environment variable or config setting.

- **Default**: `sqlite:///.data/repos.sqlite`
- **PostgreSQL example**: `postgresql+psycopg2://user:pass@host:5432/oss4climate_repos`

### Refresh Interval

The default refresh interval is **28 days**. Repositories are re-scraped if:
- They have never been scraped (`last_scraped_at IS NULL`), OR
- Their last scrape was more than `refresh_days` ago

Override with the `refresh_days` parameter:

```python
scraper = RepositoryScraper(refresh_days=7)  # Re-scrape every 7 days
```

## Pipeline Stages

### 1. Sync from TOML

The `sync_from_toml()` method reconciles the database with the TOML index file:

1. **Read TOML**: Load the TOML index to get the current list of organisations and repositories.
2. **Process organisations**: For each organisation/group in the TOML:
   - Fetch metadata from the platform API
   - Upsert into the `organisations` table
   - Discover repositories via the platform API
   - Upsert discovered repositories into the `repositories` table
3. **Process explicit repositories**: For each explicitly listed repository in the TOML, upsert into the `repositories` table.
4. **Prune inactive repositories**: Mark repositories as inactive (`active = False`, `disappeared_on = today`) if they are no longer in the TOML and not discovered from any active organisation.

**Error handling**: Organisation-level failures (API errors) are logged and the organisation is upserted with error information. The sync continues with other organisations.

### 2. Scrape Active Repositories

The `scrape_active_repos()` method fetches fresh data for repositories past their refresh threshold:

1. **Query DB**: Get all active repositories where `last_scraped_at IS NULL OR last_scraped_at < now() - timedelta(days=refresh_days)`.
2. **Build targets**: Construct a `ParsingTargets` object from the repository list.
3. **Scrape**: Use the existing `scrape_all_targets()` function to fetch data from all platforms (reusing caching, rate limiting, and platform dispatch logic).
4. **Sync results**: For each scraped repository:
   - On success: upsert data, set `last_scraped_at`, reset `last_error` and `error_count`
   - On failure: update `last_error` and increment `error_count`

**Rate limiting**: Each platform scraper tracks its own rate limit state. GitHub stops after 10 consecutive 403 errors.

### 3. Export Results

The export methods write results to files:

- **`export_to_feather()`**: Reads active repositories from the DB and writes a feather file (for backward compatibility and Typesense indexing).
- **`export_summary_toml()`**: Generates summary statistics (repository count, languages, licenses).
- **`export_failures_toml()`**: Generates a TOML file with failure information for repositories that had errors.

## Running the Scraper

### From Python

```python
from oss4climate.src.repository_scraper import RepositoryScraper

scraper = RepositoryScraper(refresh_days=28)
scraper.run(
    toml_path="index.toml",
    feather_output=".data/listing_data.feather",
    summary_output=".data/summary.toml",
    failures_output=".data/failures_scraping.toml",
)
```

### From CLI (via scrape_all)

```python
from oss4climate_scripts.scripts.repository_scraping import scrape_all

scrape_all(
    target_output_file=".data/listing_data.feather",
    refresh_days=28,
)
```

## Data Flow to Typesense

The Typesense indexer (`seed_typesense.py`) reads from the repository database:

1. Query active repositories from the DB via `get_repos_for_typesense()`
2. Convert to DataFrame format
3. Mark high-quality repos (from OpenSustain Tech targets)
4. Reset Typesense schema
5. Index documents into Typesense

## Data Flow to App

The app reads from Typesense (not directly from the database). The Typesense index is the app's data source. The database is the source of truth for scraped data, and Typesense is the search index.

## Platform Support

| Platform | Organisation Discovery | Repository Scraping | README Fetching |
|----------|----------------------|---------------------|-----------------|
| GitHub | Yes | Yes | Yes |
| GitLab | Yes | Yes | Yes |
| Codeberg | Partial | Partial | No (NotImplemented) |
| Bitbucket | Partial | Partial | No (NotImplemented) |

Codeberg and Bitbucket scrapers have limited functionality. Only GitHub and GitLab scrapers are fully implemented.

## Error Tracking

Both organisations and repositories track errors:

- `last_error`: The most recent error message (NULL if no error)
- `error_count`: Number of consecutive errors (NULL if no error)

On successful scrape, both fields are reset to NULL. On failure, `last_error` is set and `error_count` is incremented.

## Database Files

| File | Purpose |
|------|---------|
| `.data/repos.sqlite` | Repository and organisation data (SQLModel tables) |
| `.data/db.sqlite` | API response cache (TTL-based, separate from repo data) |
