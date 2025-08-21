"""
Module parsing https://opensustain.tech/
"""

from datetime import timedelta

from bs4 import BeautifulSoup

from oss4climate.src.parsers import (
    ParsingTargets,
    ResourceListing,
    cached_web_get_text,
    isolate_relevant_urls,
)
from oss4climate.src.parsers import (
    fetch_all_project_urls_from_html_webpage as __fetch_from_html,
)


def fetch_all_project_urls_from_opensustain_webpage(
    cache_lifetime: timedelta | None = None,
) -> ParsingTargets:
    return __fetch_from_html("https://opensustain.tech/", cache_lifetime=cache_lifetime)


def _f_clean_key(x):
    return x.text.replace("¶", "")


def fetch_categorised_projects_from_opensustain_webpage(
    relevant_urls_only: bool = True,
) -> dict[str, dict[str, list[str]]]:
    """Fetching categorised links to repositories, which can later be used to build classifiers

    :return: categorised list of repositories
    """
    r_text = cached_web_get_text("https://opensustain.tech/")
    b = BeautifulSoup(r_text, features="html.parser")

    # This part is built for the specific page structure at the time of writing (18/10/2024)
    #   and assumes that the information is rolled out in a consistent sequential manner
    d = dict()
    orphan_links = []
    xs = b.findAll(name=["h2", "h3", "li"])
    current_h2 = None
    current_h3 = None
    for i in xs:
        if i.name == "h2":
            current_h2 = _f_clean_key(i)
            if current_h2 not in d.keys():
                d[current_h2] = dict()
        elif i.name == "h3":
            current_h3 = _f_clean_key(i)
            if current_h3 not in d[current_h2].keys():
                d[current_h2][current_h3] = []
        elif i.name == "li":
            links = [j.get("href") for j in i.findAll(name="a")]
            if current_h2 and current_h3:
                if current_h3 not in d[current_h2].keys():
                    d[current_h2][current_h3] = []
                d[current_h2][current_h3] += links
            else:
                orphan_links += links

    # Removing code-irrelevant fields
    for i in ["Contributors", "Artwork and License"]:
        if i in d.keys():
            d.pop(i)

    if relevant_urls_only:
        # Only keeping URLs deemed relevant
        focused_d = {
            k1: {k2: isolate_relevant_urls(v2) for k2, v2 in v1.items()}
            for k1, v1 in d.items()
        }
        return focused_d
    else:
        return d


def fetch_listing_of_listings_from_opensustain_webpage() -> ResourceListing:
    from oss4climate.src.parsers.git_platforms.github_io import GithubScraper
    from oss4climate.src.parsers.git_platforms.gitlab_io import GitlabScraper

    x = fetch_categorised_projects_from_opensustain_webpage(relevant_urls_only=False)
    listing_urls = x.get("Sustainable Development").get("Curated Lists") + x.get(
        "Sustainable Development"
    ).get("Data Catalogs and Interfaces")
    gits = isolate_relevant_urls(listing_urls)
    others = [i for i in listing_urls if i not in gits]
    ghs = GithubScraper()
    gls = GitlabScraper()
    return ResourceListing(
        github_readme_listings=[i for i in gits if ghs.is_relevant_url(i)],
        gitlab_readme_listings=[i for i in gits if gls.is_relevant_url(i)],
        fault_urls=others,
    )
