"""
Module for text classification
"""

import pandas as pd


def tf_idf(documents: list[str]) -> pd.DataFrame:
    from sklearn.feature_extraction.text import TfidfVectorizer

    # Initialize TfidfVectorizer
    vectorizer = TfidfVectorizer()

    # Learn the vocabulary and transform the documents into a TF-IDF matrix
    tf_idf_matrix = vectorizer.fit_transform(documents)

    # Get the vocabulary (unique words) and their corresponding indices
    vocabulary = vectorizer.get_feature_names_out()

    df = pd.DataFrame(tf_idf_matrix.todense().T, index=vocabulary).T
    return df
