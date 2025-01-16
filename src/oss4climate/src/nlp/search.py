"""
Module to perform basic search
"""

import sys
from datetime import UTC, datetime, timedelta
from typing import Any, Iterable

import pandas as pd
from tqdm import tqdm

from oss4climate.src.log import log_warning
from oss4climate.src.nlp.classifiers import tf_idf
from oss4climate.src.parsers.licenses import license_category_from_license_name


def _lower_str(x: str, *args, **kwargs):
    if isinstance(x, str):
        return x.lower()  # remove_stopwords_and_punctuation(x)
    else:
        return ""


def _documents_loader(documents: pd.DataFrame | str | None, limit: int | None = None):
    if isinstance(documents, str):
        assert documents.endswith(
            ".feather"
        ), f"Only accepting .feather files (not {documents})"
        # This line and the usage of pandas is part of an explicit optimisation scheme (for <512 MB in operations)
        new_docs = pd.read_feather(
            documents,
            columns=[
                "id",
                "name",
                "organisation",
                "url",
                "website",
                "optimised_description",
                "license",
                "latest_update",
                "language",
                "last_commit",
                "open_pull_requests",
                "master_branch",
                "optimised_readme",
                "is_fork",
                "forked_from",
                "readme_type",
                "description",
            ],
            # dtype_backend="pyarrow",
        )
        sparse_cols = [
            "description",
            "language",
            "license",
            "optimised_readme",
            "optimised_description",
        ]
        new_docs.loc[:, sparse_cols] = new_docs[sparse_cols].astype("Sparse[str]")

        if limit is not None:
            new_docs = new_docs.head(int(limit))
    else:
        if limit is not None:
            new_docs = documents.head(int(limit))
        else:
            new_docs = documents.copy()
    return new_docs


class SearchResults:
    def __init__(
        self, documents: pd.DataFrame | str | None = None, load_documents: bool = True
    ):
        """Instantiates a result search object

        :param documents: dataframe(language,description,readme,latest_update) or filename (.feather)
        """
        self.__documents = None
        if load_documents and documents:
            self.load_documents(documents)

    def iter_documents(
        self,
        documents: pd.DataFrame | str,
        load_in_object_without_readme: bool = False,
        memory_safe: bool = True,
        bytes_limit: int = 2e5,
        display_tqdm: bool = False,
    ) -> Iterable[dict[str, Any]]:
        new_docs = _documents_loader(documents=documents, limit=None)

        if display_tqdm:
            iterator_to_run = tqdm(new_docs.iterrows())
        else:
            iterator_to_run = new_docs.iterrows()

        if memory_safe:
            # Using a protection against wild readmes (with an assumption that only the readmes do run wild)
            for k, r in iterator_to_run:
                n_size = sys.getsizeof(r)
                if n_size < bytes_limit:
                    yield r
                else:
                    log_warning(
                        f"Truncating readme of {r['url']} as it would occupy {n_size/1e6} MB in memory"
                    )
                    # TODO : this is a quickfix
                    # Cutting the readme as it's likely to overflow memory
                    readme_opt = r["optimised_readme"][
                        : int(bytes_limit)
                    ]  # heuristic that every char takes a byte
                    new_docs.loc[k, "optimised_readme"] = readme_opt
                    r["optimised_readme"] = readme_opt
                    yield r
        else:
            for __, r in iterator_to_run:
                yield r

        # Loading after iterating as a way to preserve RAM
        if load_in_object_without_readme:
            cols_to_drop = [
                i
                for i in ["readme", "optimised_readme", "optimised_description"]
                if i in new_docs.columns
            ]
            self.__documents = new_docs.drop(
                columns=cols_to_drop,
            )
            self._fix_documents()

    def _fix_documents(self):
        # Ensuring that given columns are in datetime format
        self.__documents["latest_update"] = pd.to_datetime(
            self.__documents["latest_update"]
        )
        # Adding a license_category column (if missing)
        if "license_category" not in self.__documents.keys():
            self.__documents["license_category"] = self.__documents["license"].apply(
                license_category_from_license_name
            )

    def load_documents(self, documents: pd.DataFrame | str, limit: int | None = None):
        new_docs = _documents_loader(documents=documents, limit=limit)
        if self.__documents:
            self.__documents += new_docs
        else:
            self.__documents = new_docs

        # Ensuring that the required columns exist
        available_columns = self.__documents.keys()
        for i in ["language", "description", "readme", "latest_update"]:
            assert i in available_columns

        self._fix_documents()

    def __reindex(self) -> None:
        self.__documents = self.__documents.reset_index(drop=True)

    def refine_by_languages(
        self, languages: list[str], include_none: bool = False
    ) -> None:
        df_i = pd.concat(
            [self.__documents.query(f"language=='{i}'") for i in languages]
        )
        if include_none:
            df_none = self.__documents[
                self.__documents["language"].apply(lambda x: (x is None) or pd.isna(x))
            ]
            df_i = pd.concat([df_i, df_none])

        self.__documents = df_i
        self.__reindex()

    def refine_by_keyword(
        self, keyword: str, description: bool = True, readme: bool = True
    ) -> None:
        df_i = self.__documents
        f = lambda x: keyword in _lower_str(x)
        k_selected = []
        if description:
            k_selected = k_selected + df_i[df_i["description"].apply(f)].index.to_list()
        if readme:
            k_selected = k_selected + df_i[df_i["readme"].apply(f)].index.to_list()
        k_selected_unique = list(set(k_selected))
        self.__documents = df_i.iloc[k_selected_unique].copy()
        self.__reindex()

    def order_by_relevance(self, keyword: str) -> None:
        r_tfidf = tf_idf([_lower_str(i) for i in self.__documents])
        keyword = keyword.lower()
        if keyword not in r_tfidf.keys():
            raise ValueError(f"Keyword ({keyword}) not found in documents")
        ordered_results = r_tfidf[keyword].sort_values(ascending=False)
        self.__documents = self.__documents.iloc[ordered_results.index]
        self.__reindex()

    def refine_by_active_in_past_year(self) -> None:
        t_last = datetime.now(UTC) - timedelta(days=365)
        self.__documents = self.__documents[self.__documents["latest_update"] > t_last]
        self.__reindex()

    def exclude_forks(self) -> None:
        self.__documents = self.__documents[self.__documents["is_fork"] == False]
        self.__reindex()

    @property
    def documents(self) -> pd.DataFrame:
        if self.__documents is None:
            raise ValueError("Documents are not loaded")
        return self.__documents

    @property
    def documents_without_readme(self) -> pd.DataFrame:
        if self.__documents is None:
            raise ValueError("Documents are not loaded")
        if "readme" in self.__documents.columns:
            return self.__documents.drop(columns=["readme"])
        else:
            return self.__documents

    @property
    def n_documents(self) -> int:
        if self.__documents is None:
            return 0
        return len(self.__documents)

    @property
    def statistics(self):
        # Not stable yet
        x_numbers = {
            f"n_{x}s": len(self.__documents[x].unique())
            for x in ["language", "license", "organisation"]
        }
        x_details = {
            x: self.__documents[x].value_counts()
            for x in ["language", "license", "is_fork", "organisation"]
        }

        return (
            {
                "repositories": self.n_documents,
            }
            | x_numbers
            | x_details
        )
