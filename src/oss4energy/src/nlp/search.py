"""
Module to perform basic search
"""

from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd

from oss4energy.src.nlp.classifiers import tf_idf


def _lower_str(x: str, *args, **kwargs):
    if isinstance(x, str):
        return x.lower()  # remove_stopwords_and_punctuation(x)
    else:
        return ""


class SearchResults:
    def __init__(self, documents: pd.DataFrame | str):
        """Instantiates a result search object

        :param documents: dataframe(language,description,readme,latest_update) or filename (.feather)
        """
        if isinstance(documents, str):
            assert documents.endswith(
                ".feather"
            ), f"Only accepting .feather files (not {documents})"
            self.__documents = pd.read_feather(documents)
        else:
            self.__documents = documents.copy()

        # Ensuring that the required columns exist
        available_columns = self.__documents.keys()
        for i in ["language", "description", "readme", "latest_update"]:
            assert i in available_columns

        # Ensuring that given columns are in datetime format
        self.__documents["latest_update"] = pd.to_datetime(
            self.__documents["latest_update"]
        )

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
                self.__documents["language"].apply(
                    lambda x: (x is None) or (np.isreal(x) and np.isnan(x))
                )
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
        return self.__documents

    @property
    def n_documents(self) -> int:
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
