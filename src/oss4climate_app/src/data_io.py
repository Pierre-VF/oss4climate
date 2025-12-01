import os
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from typing import Optional

import pandas as pd
from oss4climate.src.config import (
    FILE_OUTPUT_OPTIMISED_LISTING_FEATHER,
    SETTINGS,
)
from oss4climate.src.helpers import sorted_list_of_unique_elements
from oss4climate.src.log import log_info, log_warning
from oss4climate.src.models import EnumLicenseCategories
from oss4climate.src.nlp.plaintext import (
    get_spacy_english_model,
    reduce_to_informative_lemmas,
)
from oss4climate.src.nlp.search import SearchResults
from oss4climate.src.nlp.search_engine import SearchEngine

SEARCH_ENGINE_DESCRIPTIONS = SearchEngine()
SEARCH_ENGINE_READMES = SearchEngine()
SEARCH_RESULTS = SearchResults()


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
def repository_index_characteristics_from_documents(
    documents: pd.DataFrame | str | None = None,
):
    if documents is None:
        n = SEARCH_RESULTS.n_documents
        if n == 0:
            raise RuntimeError(
                "Documents must be loaded when no input for 'documents' is provided"
            )
        licenses = SEARCH_RESULTS.documents_without_readme["license"].unique().tolist()
        languages = (
            SEARCH_RESULTS.documents_without_readme["language"].unique().tolist()
        )
    else:
        licenses = []
        languages = []
        n = 0
        for r in SEARCH_RESULTS.iter_documents(documents):
            n += 1
            licenses.append(_f_none_to_unknown(r["license"]))
            languages.append(_f_none_to_unknown(r["language"]))

    return _RepositoryIndexCharacteristics(
        unique_licenses=sorted_list_of_unique_elements(licenses),
        unique_languages=sorted_list_of_unique_elements(languages),
        n_repositories_indexed=n,
    )


@lru_cache(maxsize=1)
def unique_license_categories() -> list[EnumLicenseCategories]:
    return [i for i in EnumLicenseCategories]


@lru_cache(maxsize=1)
def n_repositories_indexed():
    return SEARCH_RESULTS.n_documents


if SETTINGS.APP_LEMATISED_SEARCH:
    NLP_MODEL = get_spacy_english_model()
else:
    NLP_MODEL = None


@lru_cache(maxsize=10)
def search_for_results(query: Optional[str] = None) -> pd.DataFrame:
    if (query is None) or (len(query) < 1):
        df_x = SEARCH_RESULTS.documents_without_readme
        df_x["score"] = 1
        df_x.sort_values("name", inplace=True)
        return df_x

    lemmatised_search = SETTINGS.APP_LEMATISED_SEARCH
    if lemmatised_search:
        optimised_query = " ".join(
            reduce_to_informative_lemmas(query, nlp_model=NLP_MODEL)
        )
        log_info(f"Searching for {query} / lemmatized to {optimised_query}")
    else:
        optimised_query = query

    res_desc = SEARCH_ENGINE_DESCRIPTIONS.search(
        optimised_query, lemmatised_search=lemmatised_search
    )
    res_readme = SEARCH_ENGINE_READMES.search(
        optimised_query, lemmatised_search=lemmatised_search
    )

    df_combined = (
        res_desc.to_frame("description")
        .merge(
            res_readme.to_frame("readme"),
            how="outer",
            left_index=True,
            right_index=True,
        )
        .fillna(0)
        .infer_objects(copy=False)  # to avoid warning on downcasting
    )

    # Also checking for keywords in name
    def _f_score_in_name(x):
        kw = query.lower().split(" ")
        res = 0
        x_lower = str(x).lower()
        for i in kw:
            if len(i) > 3:  # To reduce noise (quick and dirty)
                if i in x_lower:
                    res += 1
        return res

    df_combined["score"] = df_combined["description"] * 10 + df_combined["readme"]
    df_out = SEARCH_RESULTS.documents_without_readme
    if "score" in df_out.keys():
        df_out.drop(columns=["score"], inplace=True)

    df_out = df_out.merge(
        df_combined[["score"]],
        how="outer",
        left_on="url",
        right_index=True,
    )

    df_out["score"] = (
        df_out["score"].astype(float).fillna(0)
        + df_out["name"].apply(_f_score_in_name) * 10
        + df_out["organisation"].apply(_f_score_in_name) * 10
    )

    # Focus only on relevant outputs and carry out filtering and duplicate removal
    df_out.query("score>0", inplace=True)
    df_out.sort_values(by="score", ascending=False, inplace=True)
    df_out.drop_duplicates(subset=["url"], inplace=True)
    return df_out


def clear_cache():
    repository_index_characteristics_from_documents.cache_clear()
    search_for_results.cache_clear()
    n_repositories_indexed.cache_clear()
    unique_license_categories.cache_clear()


def refresh_data(force_refresh: bool = False):
    if force_refresh or not os.path.exists(FILE_OUTPUT_OPTIMISED_LISTING_FEATHER):
        from oss4climate.src.search import listing_search

        log_warning("- Listing not found, downloading again")
        listing_search.download_listing_data_for_app()

    listing_file, readme_field, description_field = (
        SETTINGS.get_listing_file_with_readme_and_description_file_columns()
    )

    log_info("- Loading documents")
    # Make sure to coordinate the below with the app start procedure
    for r in SEARCH_RESULTS.iter_documents(
        listing_file,
        load_in_object_without_readme=True,
        display_tqdm=True,
        memory_safe=True,
    ):
        # Skip repos with missing info
        for k in [description_field, readme_field]:
            if r[k] is None:
                r[k] = ""
        SEARCH_ENGINE_DESCRIPTIONS.index(url=r["url"], content=r[description_field])
        SEARCH_ENGINE_READMES.index(r["url"], content=r[readme_field])
