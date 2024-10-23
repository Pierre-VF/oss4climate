"""
CLI module
"""

import typer

from oss4climate import scripts
from oss4climate.scripts import data_publication, listing_search, repository_scraping

app = typer.Typer()


@app.command()
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


@app.command()
def format():
    """Formats I/O files"""
    scripts.format_files()


@app.command()
def discover():
    """Generates an index"""
    scripts.update_listing_of_listings()
    scripts.discover_projects()
    scripts.format_files()


@app.command()
def publish():
    """Publishes the data to an online FTP"""
    data_publication.publish_to_ftp()


@app.command()
def generate_listing():
    """Generates the updated listing"""
    repository_scraping.scrape_all()


@app.command()
def search():
    """Searches in the listing"""
    listing_search.search_in_listing()


@app.command()
def download_data():
    """Downloads the latest listing"""
    listing_search.download_data()


if __name__ == "__main__":
    app()
