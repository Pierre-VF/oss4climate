"""
Module to manage markdown text
"""

import re

from markdown import markdown

from oss4climate.src.nlp.html_io import html_to_search_plaintext


def _replace_markdown_links(text):
    """
    Replace markdown links with their link text

    :param text: Markdown text containing links
    :return: Text with links replaced by their link text
    """
    # Regex pattern to match markdown links
    pattern = r"\[([^\]]+)\]\(.*?\)"

    # Replacement function to keep only the link text
    def repl(match):
        return match.group(1)

    # Use the sub method to replace the links
    result = re.sub(pattern, repl, text)

    return result


def _fix_titles_and_multiple_spaces(text: str) -> str:
    """
    Fix markdown titles and normalize multiple spaces

    :param text: Text to process
    :return: Processed text with titles fixed and spaces normalized
    """
    # Use the sub method to replace the links
    result = text.replace("#", " ")
    result = re.sub(r"\s+", " ", result)
    return result


def find_all_links_in_markdown(markdown_text: str) -> list[str]:
    """
    Find all links in markdown text

    :param markdown_text: Markdown text to parse
    :return: List of URLs found in markdown links
    """
    pattern = r"\[([^\]]+)\]\(([^\)]+)\)|\[([^\]]+)\]\s*\[([^\]]*)\]"
    out = re.findall(pattern, markdown_text)
    return [i[1] for i in out]


def markdown_to_search_plaintext(
    md_str: str | None,
    remove_code: bool = True,
) -> str | None:
    """This method converts a markdown string to plaintext

    :param md_str: Markdown as str
    :param remove_code: Whether to remove code blocks from markdown
    :return: plaintext str (or None is input if None)
    """
    if md_str is None:
        return None
    html = markdown(md_str)

    if remove_code:
        html = re.sub(r"<code>(.*?)</code >", " ", html)
        html = re.sub(r"<pre>(.*?)</pre>", " ", html)

    return html_to_search_plaintext(html)
