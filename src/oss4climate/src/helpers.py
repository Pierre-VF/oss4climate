"""
Module with convenience helper functions
"""

from typing import Any
from urllib.parse import urlparse

import pandas as pd


def sorted_list_of_unique_elements(x: list | pd.Series):
    """
    Return a sorted list of unique elements from input

    :param x: Input list or pandas Series
    :return: Sorted list of unique elements
    :raises TypeError: If input is not a list or pandas Series
    """
    if isinstance(x, list):
        s = pd.Series(x)
    elif isinstance(x, pd.Series):
        s = x
    else:
        raise TypeError("Input must be list or pandas.Series")
    return list(s.sort_values().unique())


def url_base_matches_domain(url: str, domain: str) -> bool:
    """
    Check if a URL's domain matches the specified domain

    :param url: URL to check
    :param domain: Domain to match against
    :return: True if URL domain matches specified domain, False otherwise
    """
    parsed_url = urlparse(url)
    return parsed_url.netloc == domain


def cleaned_url(url: str) -> str:
    """
    Clean a URL by removing query parameters and fragments

    :param url: URL to clean
    :return: Cleaned URL string
    """
    parsed_url = urlparse(url)

    out = f"{parsed_url.scheme}://{parsed_url.hostname}{parsed_url.path}"
    if " " in out:
        out = out.split(" ")[0]
    return out


def sorted_list_of_cleaned_urls(urls: list[str]) -> list[str]:
    """
    Return a sorted list of unique cleaned URLs

    :param urls: List of URLs to clean and sort
    :return: Sorted list of unique cleaned URLs
    """
    return sorted_list_of_unique_elements([cleaned_url(i) for i in urls])


def get_key_of_maximum_value(x: dict[Any, float | int]) -> Any:
    """
    Get the key with the maximum value from a dictionary

    :param x: Dictionary with numeric values
    :return: Key with the maximum value
    """
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
