"""
CLI module
"""

from datetime import timedelta

import pandas as pd
import typer

from oss4climate import scripts
from oss4climate.scripts import data_publication, listing_search, repository_scraping
from oss4climate.src.log import log_info, log_warning

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
    scripts.format_all_files()


@app.command()
def discover():
    """Generates an index"""
    ttl_cache = timedelta(days=7)
    scripts.update_listing_of_listings()
    scripts.discover_projects(cache_lifetime=ttl_cache)
    scripts.format_all_files()


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


@app.command()
def optimise():
    from oss4climate.src.nlp.plaintext import (
        get_spacy_english_model,
        reduce_to_informative_lemmas,
    )

    log_info("Loading spaCy english model")
    nlp_model = get_spacy_english_model()
    log_info("- Loaded")

    log_info("Loading input listing")
    df = pd.read_feather(scripts.FILE_OUTPUT_LISTING_FEATHER)
    log_info("- Loaded")

    df_opt = df.drop(columns=["description", "readme"])

    def _f_opt(x: str | None) -> str | None:
        if x is None:
            return None
        try:
            out = " ".join(reduce_to_informative_lemmas(x, nlp_model=nlp_model))
        except Exception as e:
            log_warning(f"Lemmatisation error: {e}")
            out = "(OPTIMISATION ERROR)"
        return out

    log_info("Optimising descriptions")
    df_opt["description"] = df["description"].apply(_f_opt)
    log_info("Optimising readmes")
    df_opt["readme"] = df["readme"].apply(_f_opt)

    log_info("Exporting input listing")
    df_opt.to_feather(scripts.FILE_OUTPUT_OPTIMISED_LISTING_FEATHER)
    log_info("- Exported")


if __name__ == "__main__":
    app()
