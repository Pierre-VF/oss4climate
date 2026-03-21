import os
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from urllib.request import urlretrieve

from oss4climate.src.config import (
    FILE_INPUT_LISTINGS_INDEX,
    FILE_OUTPUT_DIR,
    URL_LISTINGS_INDEX,
)
from oss4climate.src.helpers import sorted_list_of_unique_elements
from oss4climate.src.log import log_warning
from oss4climate.src.models import EnumLicenseCategories

from oss4climate_app.config import URL_LISTING_FEATHER
from oss4climate_app.src.search import typesense_io


def download_file(url: str, target: str, force_refresh: bool = True) -> None:
    if os.path.exists(target) and (not force_refresh):
        return
    print(f"Fetching {url}")
    urlretrieve(url, target)
    print(f"-> Downloaded to {target}")


def download_listing_data_for_app(
    force_refresh: bool = True, load_feather_listing: bool = True
):
    from oss4climate_scripts.src.config import FILE_OUTPUT_LISTING_FEATHER

    os.makedirs(FILE_OUTPUT_DIR, exist_ok=True)
    download_file(
        URL_LISTINGS_INDEX, FILE_INPUT_LISTINGS_INDEX, force_refresh=force_refresh
    )
    if load_feather_listing:
        download_file(
            URL_LISTING_FEATHER,
            FILE_OUTPUT_LISTING_FEATHER,
            force_refresh=force_refresh,
        )
    print("Download complete")


def _f_none_to_unknown(x: str | date | None) -> str:
    if x is None:
        return "(unknown)"
    else:
        return str(x)


@dataclass
class _RepositoryIndexCharacteristics:
    unique_licenses: list[str]
    unique_languages: list[str]
    n_repositories_indexed: int


@lru_cache(maxsize=1)
def repository_index_characteristics_from_documents() -> (
    _RepositoryIndexCharacteristics
):
    # TODO: fill this
    licenses = []
    languages = []
    return _RepositoryIndexCharacteristics(
        unique_licenses=sorted_list_of_unique_elements(licenses),
        unique_languages=sorted_list_of_unique_elements(languages),
        n_repositories_indexed=n_repositories_indexed(),
    )


@lru_cache(maxsize=1)
def unique_license_categories() -> list[EnumLicenseCategories]:
    return [i for i in EnumLicenseCategories]


@lru_cache(maxsize=1)
def n_repositories_indexed():
    # TODO : avoid on the fly client creation
    x = typesense_io.search_with_query(
        typesense_io.generate_client(), " ", results_per_page=2
    )
    return x.total_results


def clear_cache():
    repository_index_characteristics_from_documents.cache_clear()
    n_repositories_indexed.cache_clear()
    unique_license_categories.cache_clear()


def refresh_data(force_refresh: bool = False):
    from oss4climate_scripts.src.config import FILE_OUTPUT_LISTING_FEATHER

    if force_refresh or not os.path.exists(FILE_OUTPUT_LISTING_FEATHER):
        log_warning("- Listing not found, downloading again")
        download_listing_data_for_app()
