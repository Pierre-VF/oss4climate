"""
Tool to scrape a website and extract the relevant links
"""

from datetime import timedelta
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from requests.exceptions import HTTPError

from oss4climate.src.log import log_info
from oss4climate.src.parsers import (
    ParsingTargets,
    cached_web_get_text,
    identify_parsing_targets,
)


def _web_get(
    url: str,
    cache_lifetime: timedelta | None = None,
    rate_limiting_wait_s: float = 0.1,
) -> str:
    """
    Perform a web GET request for website scraping

    :param url: URL to fetch
    :param cache_lifetime: Optional maximum age for cached data
    :param rate_limiting_wait_s: Time to wait between requests to avoid rate limiting
    :return: Response text
    """
    headers = None
    res = cached_web_get_text(
        url=url,
        headers=headers,
        rate_limiting_wait_s=rate_limiting_wait_s,
        cache_lifetime=cache_lifetime,
    )
    return res


def _is_interesting_internal_url(url: str) -> bool:
    """
    Check if an internal URL is interesting for scraping

    :param url: URL to check
    :return: True if URL is interesting for scraping, False otherwise
    """
    if url.startswith("javascript:"):
        return False
    elif url.endswith(".css"):
        return False
    elif url.endswith(".jpg") or url.endswith(".png") or url.endswith(".svg"):
        return False
    else:
        return True


def scrape_page(
    url: str,
    cache_lifetime: timedelta | None = None,
) -> tuple[ParsingTargets, list[str]]:
    """
    Scrape a webpage and extract internal links and external parsing targets

    :param url: URL of webpage to scrape
    :param cache_lifetime: Optional maximum age for cached data
    :return: Tuple containing list of interesting internal links and ParsingTargets for external links
    """
    page_str = _web_get(url, cache_lifetime=cache_lifetime)
    soup = BeautifulSoup(page_str, "html.parser")

    xs = soup.find_all("a", href=True)
    internal_links = []
    external_links = []
    for p in xs:
        s_i = p["href"]
        if s_i.startswith("http://") or s_i.startswith("https://"):
            external_links.append(s_i)
        else:
            local_link = urljoin(url, s_i)
            internal_links.append(local_link)

    parsing_targets = identify_parsing_targets(external_links)
    interesting_internal_links = [
        i.split("#")[0] for i in internal_links if _is_interesting_internal_url(i)
    ]

    return interesting_internal_links, parsing_targets


def crawl_website(
    url: str,
    remove_unknown: bool = True,
    cache_lifetime: timedelta | None = None,
    max_pages: int | None = None,
    ignore_path_regex: str | None = None,
) -> ParsingTargets:
    """
    Crawl a website and extract all relevant parsing targets

    :param url: Starting URL for website crawling
    :param remove_unknown: Whether to remove unknown targets from results
    :param cache_lifetime: Optional maximum age for cached data
    :param max_pages: Optional maximum number of pages to crawl
    :param ignore_path_regex: Optional regex pattern for paths to ignore (not implemented)
    :return: ParsingTargets containing all extracted project URLs
    :raises NotImplementedError: If robots.txt exists or ignore_path_regex is provided
    """
    try:
        url_raw = urlparse(url)
        _web_get(f"{url_raw.scheme}://{url_raw.hostname}/robots.txt")
        has_robots_txt = True
    except HTTPError as e:
        if "404" in e.args[0]:
            has_robots_txt = False
        else:
            raise e

    if has_robots_txt:
        raise NotImplementedError(
            "Unable to respect robots.txt at this stage - scraping is forbidden"
        )

    if ignore_path_regex:
        raise NotImplementedError("Regex for path ignore is not implemented yet")

    targets = ParsingTargets()
    urls_crawled = []
    urls_to_crawl = [url]
    crawl_counter = 0
    while len(urls_to_crawl) > 0:
        url_i = urls_to_crawl.pop(0)
        if url_i in urls_crawled:
            pass
        else:
            log_info(f"Scraping {url_i}")
            try:
                new_urls, new_targets = scrape_page(
                    url_i, cache_lifetime=cache_lifetime
                )
            except KeyboardInterrupt:
                log_info("User got tired, stopping here")
                break
            except Exception as e:
                log_info(f"Failed to scrape {url_i} ({e})")
            # Adding the results
            urls_crawled.append(url_i)
            urls_to_crawl += new_urls
            targets += new_targets
            if max_pages is not None:
                crawl_counter += 1
                if crawl_counter > max_pages:
                    log_info("Reached the maximum number of crawls - stopping")
                    break
                else:
                    log_info(f"Crawl {crawl_counter} / {max_pages} allowed")

    if remove_unknown:
        targets.unknown = []
        targets.invalid = []

    # Ensuring unicity
    targets.cleanup()
    return targets
