import os
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from urllib.request import urlretrieve

from oss4climate.src.helpers import sorted_list_of_unique_elements
from oss4climate.src.log import log_info, log_warning
from oss4climate.src.models import EnumLicenceCategories
from oss4climate_app.src.config import (
    FILE_INPUT_LISTINGS_INDEX,
    FILE_OUTPUT_DIR,
    FILE_OUTPUT_LISTING_FEATHER,
    URL_LISTING_FEATHER,
    URL_LISTINGS_INDEX,
)
from oss4climate_app.src.search import typesense_io


def download_file(url: str, target: str, force_refresh: bool = True) -> None:
    if os.path.exists(target) and (not force_refresh):
        return
    log_info(f"Fetching {url}")
    urlretrieve(url, target)
    log_info(f"-> Downloaded to {target}")


def download_listing_data_for_app(
    force_refresh: bool = True, load_feather_listing: bool = True
):
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
    log_info("Download complete")


def _f_none_to_unknown(x: str | date | None) -> str:
    if x is None:
        return "(unknown)"
    else:
        return str(x)


@dataclass
class _RepositoryIndexCharacteristics:
    unique_licences: list[str]
    unique_languages: list[str]
    n_repositories_indexed: int
    n_repositories_indexed_extended: int


@lru_cache(maxsize=1)
def repository_index_characteristics_from_documents() -> (
    _RepositoryIndexCharacteristics
):
    # TOODO: generate this better (doesn't get patched in tests) - in a way that works with cache
    ts_client = typesense_io.generate_client()
    licences = typesense_io.list_values(
        ts_client, typesense_io.CountableFieldsEnum.licence
    )
    languages = typesense_io.list_values(
        ts_client, typesense_io.CountableFieldsEnum.language
    )
    return _RepositoryIndexCharacteristics(
        unique_licences=sorted_list_of_unique_elements(licences),
        unique_languages=sorted_list_of_unique_elements(languages),
        n_repositories_indexed=n_repositories_indexed(extended=False),
        n_repositories_indexed_extended=n_repositories_indexed(extended=True),
    )


@lru_cache(maxsize=1)
def unique_licence_categories() -> list[EnumLicenceCategories]:
    return [i for i in EnumLicenceCategories]


@lru_cache(maxsize=2)
def n_repositories_indexed(extended: bool) -> int:
    # TODO : avoid on the fly client creation
    x = typesense_io.count_values(
        typesense_io.generate_client(),
        field=typesense_io.CountableFieldsEnum.licence,
        high_quality_only=(not extended),
    ).sum()
    return int(x)


def clear_cache():
    repository_index_characteristics_from_documents.cache_clear()
    n_repositories_indexed.cache_clear()
    unique_licence_categories.cache_clear()


def refresh_data(force_refresh: bool = False):
    """
    Refresh the data for the app.

    Note: The feather file is no longer used as the primary data source.
    The app now reads from the repository database. This function is kept
    for backward compatibility but only downloads the listings index.
    """
    if force_refresh:
        log_warning("- Force refresh requested, downloading listings index")
    download_listing_data_for_app(
        force_refresh=force_refresh, load_feather_listing=False
    )
