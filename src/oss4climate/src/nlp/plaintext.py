import re


def remove_linebreaks_and_excess_spaces(txt: str) -> str:
    # Basic fixes
    txt = txt.replace("\n", "")
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt
