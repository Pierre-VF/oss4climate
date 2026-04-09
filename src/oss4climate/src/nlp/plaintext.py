import re


def remove_linebreaks_and_excess_spaces(txt: str) -> str:
    """
    Remove line breaks and normalize spaces in text

    :param txt: Text to process
    :return: Processed text with line breaks removed and spaces normalized
    """
    # Basic fixes
    txt = txt.replace("\n", "")
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt
