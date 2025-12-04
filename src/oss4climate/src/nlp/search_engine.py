"""
A minimal search engine implementation

Taken from https://github.com/alexmolas/microsearch/blob/main/src/microsearch/engine.py
"""

import string
import sys
from collections import defaultdict
from functools import cached_property
from math import log
from typing import Any

import pandas as pd

from oss4climate.src.log import log_warning


def update_url_scores(old: dict[str, float], new: dict[str, float]):
    for url, score in new.items():
        if url in old:
            old[url] += score
        else:
            old[url] = score
    return old


def normalize_string(input_string: str | Any) -> str:
    if not isinstance(input_string, str):
        return ""
    # Note : this currently does stuff beyond the lemmatizer optimisation (hence required to keep for well functioning)
    translation_table = str.maketrans(string.punctuation, " " * len(string.punctuation))
    string_without_punc = input_string.translate(translation_table)
    string_without_double_spaces = " ".join(string_without_punc.split())
    return string_without_double_spaces.lower()


class SearchEngine:
    def __init__(
        self,
        k1: float = 1.5,
        b: float = 0.75,
    ):
        self._index: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._documents_length: dict[str, str] = {}
        self.k1 = k1
        self.b = b

    @property
    def indexed_items(self) -> list[str]:
        return list(self._documents_length.keys())

    @cached_property
    def number_of_items(self) -> int:
        return len(self._documents_length)

    @property
    def avdl(self) -> float:
        if not hasattr(self, "_avdl"):
            self._avdl = (
                sum(list(self._documents_length.values())) / self.number_of_items
            )
        return self._avdl

    def idf(self, kw: str) -> float:
        n = self.number_of_items
        n_kw = len(self.get_urls(kw))
        return log((n - n_kw + 0.5) / (n_kw + 0.5) + 1)

    def bm25(self, kw: str) -> dict[str, float]:
        result = {}
        idf_score = self.idf(kw)
        avdl = self.avdl
        for url, freq in self.get_urls(kw).items():
            numerator = freq * (self.k1 + 1)
            denominator = freq + self.k1 * (
                1 - self.b + self.b * self._documents_length[url] / avdl
            )
            result[url] = idf_score * numerator / denominator
        return result

    def search(
        self,
        query: str,
    ) -> pd.Series:
        keywords = normalize_string(query).split(" ")
        url_scores: dict[str, float] = {}
        for kw in keywords:
            kw_urls_score = self.bm25(kw)
            url_scores = update_url_scores(url_scores, kw_urls_score)
        return pd.Series(list(url_scores.values()), index=list(url_scores.keys()))

    def index(
        self,
        url: str,
        content: str,
        memory_safe: bool = True,
        bytes_limit: int = 5e5,
    ) -> None:
        """Method to index content for a URL (with a safe to avoid memory usage explosions)

        :param url: URL to use as index key
        :param content: content to index for the URL
        :param memory_safe: whether to adopt a memory safe (not adding the content if memory used by index increases by
            more than 'bytes_limit' - this is useful for avoiding errors with tricky READMEs), defaults to True
        :param bytes_limit: limit of number of bytes of index extension (used wnen 'memory_safe' is True), defaults to 5e5
        """
        if isinstance(content, str):
            self._documents_length[url] = len(content)
        else:
            if pd.isna(content):
                self._documents_length[url] = 0
            else:
                log_warning(
                    f"Uncovered indexing type ({content.__class__.__name__} - skipping indexing of {url})"
                )
                self._documents_length[url] = 0
        words = normalize_string(content).split(" ")
        if memory_safe:
            new_words_indexed = dict()
            for word in words:
                if word not in new_words_indexed:
                    new_words_indexed[word] = 0
                else:
                    new_words_indexed[word] += 1
            index_size_increase = sys.getsizeof(new_words_indexed)
            if index_size_increase > bytes_limit:
                # To avoid size exploding
                log_warning(
                    f"Skipping indexing of URL {url} as it would yield a {round(index_size_increase / 1e6, 1)} MB size increase"
                )
            else:
                for k, v in new_words_indexed.items():
                    self._index[k][url] = v
        else:
            for word in words:
                self._index[word][url] += 1
        if hasattr(self, "_avdl"):
            del self._avdl

    @property
    def index_size(self) -> int:
        return sys.getsizeof(self._index)

    def bulk_index(self, documents: list[tuple[str, str]]):
        for url, content in documents:
            self.index(url, content)

    def get_urls(self, keyword: str) -> dict[str, int]:
        keyword = normalize_string(keyword)
        return self._index[keyword]
