"""
Module with convenience helper functions
"""

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
