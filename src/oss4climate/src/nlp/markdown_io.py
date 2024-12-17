"""
Module to manage markdown text
"""

import re

from bs4 import BeautifulSoup
from markdown import markdown


def _replace_markdown_links(text):
    # Regex pattern to match markdown links
    pattern = r"\[([^\]]+)\]\(.*?\)"

    # Replacement function to keep only the link text
    def repl(match):
        return match.group(1)

    # Use the sub method to replace the links
    result = re.sub(pattern, repl, text)

    return result


def _fix_titles_and_multiple_spaces(text: str) -> str:
    # Use the sub method to replace the links
    result = text.replace("#", " ")
    result = re.sub(r"\s+", " ", result)
    return result


def markdown_to_clean_plaintext(
    x: str | None, remove_code: bool = True, remove_linebreaks: bool = False
) -> str | None:
    """This method converts a markdown string to plaintext

    :param x: _description_
    :return: _description_
    """
    if x is None:
        return None
    html = markdown(x)

    if remove_code:
        html = re.sub(r"<code>(.*?)</code >", " ", html)
        html = re.sub(r"<pre>(.*?)</pre>", " ", html)

    x = BeautifulSoup(html, features="html.parser")
    text = "".join(x.find_all(string=True))
    if remove_linebreaks:
        text = text.replace("\n", " ")
    # Collapse multiple spaces to a single
    text = re.sub(r"\s+", " ", text)
    return text.strip()
