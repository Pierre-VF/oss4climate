import re


def get_spacy_english_model(minimal: bool = True):
    try:
        import en_core_web_sm
    except ImportError:
        import os

        print("Downloading the spacy model")
        os.system("python -m spacy download en_core_web_sm")
        print("Done")
        import en_core_web_sm

    nlp_model = en_core_web_sm.load()

    if minimal:
        nlp_model.select_pipes(
            disable=[
                "parser",  # Disable dependency parsing
                "ner",  # Disable named entity recognition
                # 'lemmatizer'  # Disable lemmatization if not needed
            ]
        )
    return nlp_model


def remove_linebreaks_and_excess_spaces(txt: str) -> str:
    # Basic fixes
    txt = txt.replace("\n", "")
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt


def _f_token_is_url(token) -> bool:
    return token.like_url and ("://" in token.text)


def extract_urls(txt: str, nlp_model=None) -> list[str]:
    if nlp_model is None:
        nlp_model = get_spacy_english_model()
    urls = [token.text for token in nlp_model(txt) if _f_token_is_url(token)]
    return urls


def reduce_to_informative_lemmas(txt: str, nlp_model=None) -> list[str]:
    if nlp_model is None:
        nlp_model = get_spacy_english_model()

    def _f_useful_filter(token):
        return not (token.is_stop or token.is_punct or token.like_num)

    cleaned_lemmas = list(
        map(lambda token: token.lemma_, filter(_f_useful_filter, nlp_model(txt)))
    )
    return cleaned_lemmas
