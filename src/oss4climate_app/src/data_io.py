import os
from dataclasses import dataclass
from datetime import date
from functools import lru_cache

import pandas as pd
from tqdm import tqdm

from oss4climate.scripts import (
    FILE_OUTPUT_OPTIMISED_LISTING_FEATHER,
    listing_search,
)
from oss4climate.src.helpers import sorted_list_of_unique_elements
from oss4climate.src.log import log_info, log_warning
from oss4climate.src.nlp.plaintext import (
    get_spacy_english_model,
    reduce_to_informative_lemmas,
)
from oss4climate.src.nlp.search import SearchResults
from oss4climate.src.nlp.search_engine import SearchEngine
from oss4climate.src.parsers.licenses import LicenseCategoriesEnum

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
        df_docs = SEARCH_RESULTS.documents_without_readme
        if df_docs is None:
            raise RuntimeError(
                "Documents must be loaded when no input for 'documents' is provided"
            )
        n = len(df_docs)
        licenses = df_docs["license"].unique().tolist()
        languages = df_docs["language"].unique().tolist()
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
def unique_license_categories() -> list[LicenseCategoriesEnum]:
    return [i for i in LicenseCategoriesEnum]


@lru_cache(maxsize=1)
def n_repositories_indexed():
    return SEARCH_RESULTS.n_documents


NLP_MODEL = get_spacy_english_model()


@lru_cache(maxsize=10)
def search_for_results(query: str) -> pd.DataFrame:
    if len(query) < 1:
        df_x = SEARCH_RESULTS.documents_without_readme
        df_x["score"] = 1
        return df_x

    lemmatized_query = " ".join(
        reduce_to_informative_lemmas(query, nlp_model=NLP_MODEL)
    )
    log_info(f"Searching for {query} / lemmatized to {lemmatized_query}")

    res_desc = SEARCH_ENGINE_DESCRIPTIONS.search(lemmatized_query)
    res_readme = SEARCH_ENGINE_READMES.search(lemmatized_query)

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
        x_lower = x.lower()
        for i in kw:
            if len(i) > 3:  # To reduce noise (quick and dirty)
                if i in x_lower:
                    res += 1
        return res

    df_combined["score"] = df_combined["description"] * 10 + df_combined["readme"]
    df_out = SEARCH_RESULTS.documents_without_readme.merge(
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


def refresh_data(force_refresh: bool = False):
    if force_refresh or not os.path.exists(FILE_OUTPUT_OPTIMISED_LISTING_FEATHER):
        log_warning("- Listing not found, downloading again")
        listing_search.download_listing_data_for_app()
    log_info("- Loading documents")
    for r in tqdm(SEARCH_RESULTS.iter_documents(FILE_OUTPUT_OPTIMISED_LISTING_FEATHER)):
        # Skip repos with missing info
        for k in ["optimised_readme", "optimised_description"]:
            if r[k] is None:
                r[k] = ""
        SEARCH_ENGINE_DESCRIPTIONS.index(
            url=r["url"], content=r["optimised_description"]
        )
        SEARCH_ENGINE_READMES.index(r["url"], content=r["optimised_readme"])
