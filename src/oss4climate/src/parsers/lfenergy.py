"""
Parser for LF Energy projects
"""

from datetime import timedelta

import yaml
from bs4 import BeautifulSoup

from oss4climate.src.parsers import (
    ParsingTargets,
    cached_web_get_text,
    identify_parsing_targets,
)
from oss4climate.src.parsers.git_platforms.github_io import GithubScraper
from oss4climate.src.parsers.gitlab_data_io import GITLAB_ANY_URL_PREFIX

_PROJECT_PAGE_URL_BASE = "https://lfenergy.org/projects/"


def fetch_all_project_urls_from_lfe_webpage(
    cache_lifetime: timedelta | None = None,
) -> list[str]:
    r_text = cached_web_get_text(
        "https://lfenergy.org/our-projects/", cache_lifetime=cache_lifetime
    )
    b = BeautifulSoup(r_text, features="html.parser")

    rs = b.findAll(name="a")
    shortlisted_urls = [
        i for i in [x.get("href") for x in rs] if i.startswith(_PROJECT_PAGE_URL_BASE)
    ]
    # Ensure unicity of links
    return list(set(shortlisted_urls))


def fetch_project_github_urls_from_lfe_energy_project_webpage(
    project_url: str,
    cache_lifetime: timedelta | None = None,
) -> ParsingTargets:
    if not project_url.startswith(_PROJECT_PAGE_URL_BASE):
        raise ValueError(f"Unsupported page URL ({project_url})")
    r_text = cached_web_get_text(project_url, cache_lifetime=cache_lifetime)
    b = BeautifulSoup(r_text, features="html.parser")

    rs = b.findAll(name="a", attrs={"class": "projects-icon"})

    # Github URLs
    github_urls = [
        i for i in [x.get("href") for x in rs] if GithubScraper.is_relevant_url(i)
    ]
    github_urls = [i for i in github_urls if not i.endswith(".md")]
    # Gitlab URLs
    gitlab_urls = [
        i for i in [x.get("href") for x in rs] if i.startswith(GITLAB_ANY_URL_PREFIX)
    ]
    gitlab_urls = [i for i in gitlab_urls if not i.endswith(".md")]

    return identify_parsing_targets(github_urls + gitlab_urls)


def get_open_source_energy_projects_from_landscape(
    cache_lifetime: timedelta | None = None,
) -> ParsingTargets:
    r = cached_web_get_text(
        "https://raw.githubusercontent.com/lf-energy/lfenergy-landscape/main/landscape.yml",
        cache_lifetime=cache_lifetime,
    )
    out = yaml.load(r, Loader=yaml.CLoader)

    def _list_if_exists(x, k):
        v = x.get(k)
        if v is None:
            return []
        else:
            return v

    repos = []
    for x in _list_if_exists(out, "landscape"):
        for sc in _list_if_exists(x, "subcategories"):
            for i in _list_if_exists(sc, "items"):
                repo_url = i.get("repo_url")
                if repo_url:
                    repos.append(repo_url)

    return identify_parsing_targets(repos)
