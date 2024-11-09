import os
from datetime import date
from functools import lru_cache

import pandas as pd
from tqdm import tqdm

from oss4climate.scripts import (
    FILE_OUTPUT_LISTING_FEATHER,
    listing_search,
)
from oss4climate.src.log import log_info, log_warning
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


@lru_cache(maxsize=1)
def unique_licenses() -> list[str]:
    x = SEARCH_RESULTS.documents["license"].apply(_f_none_to_unknown).unique()
    x.sort()
    return x.tolist()


@lru_cache(maxsize=1)
def unique_languages() -> list[str]:
    x = SEARCH_RESULTS.documents["language"].apply(_f_none_to_unknown).unique()
    x.sort()
    return x.tolist()


@lru_cache(maxsize=1)
def n_repositories_indexed():
    return SEARCH_RESULTS.n_documents


@lru_cache(maxsize=10)
def search_for_results(query: str) -> pd.DataFrame:
    if len(query) < 1:
        df_x = SEARCH_RESULTS.documents.drop(columns=["readme"])
        df_x["score"] = 1
        return df_x

    log_info(f"Searching for {query}")
    res_desc = SEARCH_ENGINE_DESCRIPTIONS.search(query)
    res_readme = SEARCH_ENGINE_READMES.search(query)

    df_combined = (
        res_desc.to_frame("description")
        .merge(
            res_readme.to_frame("readme"),
            how="outer",
            left_index=True,
            right_index=True,
        )
        .fillna(0)
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
    df_out = SEARCH_RESULTS.documents.drop(columns=["readme"]).merge(
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
    unique_licenses.cache_clear()
    unique_languages.cache_clear()
    n_repositories_indexed.cache_clear()
    search_for_results.cache_clear()


def refresh_data(force_refresh: bool = False):
    if force_refresh or not os.path.exists(FILE_OUTPUT_LISTING_FEATHER):
        log_warning("- Listing not found, downloading again")
        listing_search.download_listing_data_for_app()
    log_info("- Loading documents")
    SEARCH_RESULTS.load_documents(FILE_OUTPUT_LISTING_FEATHER)
    for __, r in tqdm(SEARCH_RESULTS.documents.iterrows()):
        # Skip repos with missing info
        for k in ["readme", "description"]:
            if r[k] is None:
                r[k] = ""
        SEARCH_ENGINE_DESCRIPTIONS.index(url=r["url"], content=r["description"])
        SEARCH_ENGINE_READMES.index(r["url"], content=r["readme"])
