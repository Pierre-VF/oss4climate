"""
CLI module
"""

from datetime import timedelta

from oss4climate_scripts import scripts
from oss4climate_scripts.scripts import (
    data_publication,
    repository_scraping,
)
from oss4climate_scripts.src import utils


def add():
    """Adds a resource to the index

    :param url: URL to add to the index
    """
    urls_to_add = []
    x = "?"
    while x != "":
        x = input("Enter URL to be added (ENTER to stop adding): ")
        # Removing whitespaces
        x = x.strip()
        if len(x) > 0:
            urls_to_add.append(x)
    print(f"Adding {urls_to_add}")
    scripts.add_projects_to_listing(urls_to_add)


def format():
    """Formats I/O files"""
    scripts.format_all_files()


def discover():
    """Generates an index"""
    ttl_cache = timedelta(days=7)
    scripts.update_listing_of_listings()
    scripts.discover_projects(cache_lifetime=ttl_cache)
    scripts.format_all_files()


def publish():
    """Publishes the data to an online FTP"""
    data_publication.publish_to_ftp()


def generate_listing():
    """Generates the updated listing"""
    repository_scraping.scrape_all()


def download_data():
    """Downloads the latest listing"""
    utils.download_data()
