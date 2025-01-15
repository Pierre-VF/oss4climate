"""
Module with convenience helper functions
"""

from typing import Any
from urllib.parse import urlparse

import pandas as pd


def sorted_list_of_unique_elements(x: list | pd.Series):
    if isinstance(x, list):
        s = pd.Series(x)
    elif isinstance(x, pd.Series):
        s = x
    else:
        raise TypeError("Input must be list or pandas.Series")
    return list(s.sort_values().unique())


def url_base_matches_domain(url: str, domain: str) -> bool:
    parsed_url = urlparse(url)
    return parsed_url.netloc == domain


def cleaned_url(url: str) -> str:
    parsed_url = urlparse(url)

    out = f"{parsed_url.scheme}://{parsed_url.hostname}{parsed_url.path}"
    if " " in out:
        out = out.split(" ")[0]
    return out


def sorted_list_of_cleaned_urls(urls: list[str]) -> list[str]:
    return sorted_list_of_unique_elements([cleaned_url(i) for i in urls])


def get_key_of_maximum_value(x: dict[Any, float | int]) -> Any:
    max_value = None
    max_key = None
    for k, v in x.items():
        if max_value is None:
            max_value = v
            max_key = k
        if max_value < v:
            max_value = v
            max_key = k
    return max_key
