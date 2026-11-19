# 🌍 Listing of open-source for climate and energy applications

[![Code licence: MIT](https://img.shields.io/github/license/Pierre-VF/oss4climate)](LICENSE)
[![Search the web app](https://img.shields.io/badge/web_app-oss4climate.apps.pierrevf.com-2f8f5f)](https://oss4climate.apps.pierrevf.com/)

> **TL;DR** — just looking for the search engine? You will find it here: <https://oss4climate.apps.pierrevf.com/>

> **Warning:** the project is in active development and still at an early stage, therefore the structure may change without prior notice. If you depend on the code as a dependency to your application, please ensure to pin the specific commits in all your usages.

## What is this project?

This project provides a **listing of open-source software for energy and climate applications**, together with a **search engine** to explore it.

The vision is that this should be more than just yet another listing: it aims to provide insight on the aspects that are key to the success of open-source usage:

- maintenance
- security
- tech stack
- context data (who uses it, maintains it, ...)

All of this should be provided in a way that makes it easy to search and interface with (e.g. with a structured, machine-readable registry).

The project has not reached all of these goals yet. Contributions of all kinds are very welcome — see the [open issues](https://github.com/Pierre-VF/oss4climate/issues).

## Do you just want to search for open-source matching your needs?

No installation needed:

- **Web app:** <https://oss4climate.apps.pierrevf.com/> — search by keyword, and refine by licence, programming language or project activity. The same search is also available as an **MCP tool** for your favourite LLM and as a REST **API** (see the links in the app's navigation bar).

With the code installed (see below), you can also search from the command line:

> uv run search

## Where is the data coming from?

Inputs to the discovery process are given in the files in the **indexes** folder (you are welcome to add your own contribution):

- the listings scraped are listed in **[listings.json](indexes/listings.json)** (if you are interested in project listings, you should check all URLs in this file)
- repositories found in the listings and added manually are found in **[repositories.toml](indexes/repositories.toml)**
- the associated scrapers are provided by the [`oss4x`](https://github.com/Pierre-VF/oss4x) package (folder `oss4x/src/parsers`)

### Credits

The following projects are credited as major contributors to the underlying dataset:

- [OpenSustain.tech](https://opensustain.tech/) (who kindly licensed their dataset under *Creative Commons Attribution 4.0 International*)
- the other listings found in [listings.json](indexes/listings.json)

Data from the repositories themselves is fetched directly from the hosting platforms. The platforms currently supported are given in the table below.

| Platform  | Identified in discovery | Data scraped |
|-----------|-------------------------|--------------|
| GitLab    | Yes                     | Yes          |
| GitHub    | Yes                     | Yes          |
| Bitbucket | Yes                     | Not yet      |
| Codeberg  | Yes                     | Not yet      |

## What is the licence of the code and the data?

The licence differs between the source code and the listings data. Please make sure to check the [licence file](LICENSE) for all details.

The underlying listing data comes from a variety of repositories, some of which have a Creative Commons licence. **That means that while you are free to reuse and adapt the software, there are restrictions on the usage of the listings data.**

## Development and contribution

### Installation

The installation is straightforward if you are used to Python.

You have 2 options:

1. Simple installation:
    Create a virtual environment with Python 3.14 (the code is not tested for previous versions). Then install the package:
    > pip install .

2. Development-oriented installation (with uv), which only works on Unix systems. Run the makefile command:
    > make install

It is highly recommended to operate with a Github token (which you can create [here](https://github.com/settings/tokens/new)) in order to avoid being blocked by Github's rate limit on the API. The same consideration applies to Gitlab (token generation [here](https://gitlab.com/-/user_settings/personal_access_tokens)). These are much lower for unauthenticated accounts.

Make sure to generate this token with permissions to access public repositories.

The token can be imported by generating a *.env* file in the root of your repository with the following content:

```bash
# This is your token generated here: https://github.com/settings/tokens/new
GITHUB_API_TOKEN="...[add your token here]..."
# This is your token generated here: https://gitlab.com/-/user_settings/personal_access_tokens
GITLAB_ACCESS_TOKEN="...[add your token here]..."

# For app operation, a key to refresh the data (to avoid undesirable refreshing)
DATA_REFRESH_KEY="...[add a random key here]..."

# You can adjust the position of the cache database here (leave to default if you don't need adjustment)
SQLITE_DB=".data/db.sqlite"

# If you want to enable publication of the data to FTP, you can also set these variables
EXPORT_FTP_URL=""
EXPORT_FTP_USER=""
EXPORT_FTP_PASSWORD=""
```

### Running the code

Once you have completed the steps above, you can run the following commands (only valid on Unix systems):

Typical use-cases:

- To download the dataset:
    > uv run download_data
- To search in CLI mode (note that this is a very basic CLI):
    > uv run search

Advanced use-cases (to regenerate listings — avoid unless necessary, as this is very resource intensive):

- To generate an output dataset:
    > uv run generate_listing
- To add new resources:
    > uv run add
- To refresh the list of targets to be scraped:
    > uv run discover
- To export the datasets to FTP (using the credentials from the environment):
    > uv run publish

Note: the indexing is heavy and involves a series of web (and API) calls. A caching mechanism is therefore added in the implementation of the requests (with a simple SQLite database). This means that you might potentially end up with a large file stored locally on your disk (currently under 500 Mb).

## Need new features or found a bug?

Please open an issue on the repository [here](https://github.com/Pierre-VF/oss4climate/issues).

If you have a use-case that you would like to develop based upon this, or need new features, please get in touch with [PierreVF UG](https://www.pierrevf.com/) for support.
