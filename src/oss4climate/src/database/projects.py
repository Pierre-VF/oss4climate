"""
Module to perform basic search
"""

import pandas as pd


def project_dataframe_loader(
    documents: pd.DataFrame | str | None, limit: int | None = None
):
    """
    Load project data from DataFrame or Feather file

    :param documents: DataFrame containing project data or path to Feather file
    :param limit: Optional maximum number of rows to load
    :return: DataFrame with project data
    :raises AssertionError: If file path doesn't end with .feather extension
    """
    if isinstance(documents, str):
        assert documents.endswith(".feather"), (
            f"Only accepting .feather files (not {documents})"
        )
        readme_col, description_col = "readme", "description"

        # This line and the usage of pandas is part of an explicit optimisation scheme (for <512 MB in operations)
        new_docs = pd.read_feather(
            documents,
            columns=list(
                {
                    "id",
                    "name",
                    "organisation",
                    "url",
                    "website",
                    "license",
                    "latest_update",
                    "language",
                    "last_commit",
                    "open_pull_requests",
                    "master_branch",
                    "is_fork",
                    "forked_from",
                    "readme_type",
                    "description",
                    readme_col,
                    description_col,
                }
            ),
        )
        sparse_cols = list(
            {
                "description",
                "language",
                "license",
                readme_col,
                description_col,
            }
        )
        new_docs.loc[:, sparse_cols] = new_docs[sparse_cols].astype("Sparse[str]")

        if limit is not None:
            new_docs = new_docs.head(int(limit))
    else:
        if limit is not None:
            new_docs = documents.head(int(limit))
        else:
            new_docs = documents.copy()
    return new_docs
