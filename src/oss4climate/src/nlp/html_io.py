import re

from bs4 import BeautifulSoup

from oss4climate.src.log import log_warning


def find_all_links_in_html(html_str: str) -> list[str]:
    """
    Find all links in HTML content

    :param html_str: HTML string to parse
    :return: List of href attributes from all anchor tags
    """
    b = BeautifulSoup(html_str, features="html.parser")
    rs = b.find_all(name="a")
    return [x.get("href") for x in rs]


def html_to_search_plaintext(html_str: str, remove_code: bool = True) -> list[str]:
    """
    Convert HTML to plain text for search purposes

    :param html_str: HTML string to convert
    :param remove_code: Whether to remove code blocks from HTML
    :return: Plain text extracted from HTML
    """
    if remove_code:
        try:
            html_str = re.sub(r"<code>(.*?)</code >", " ", html_str)
            html_str = re.sub(r"<pre>(.*?)</pre>", " ", html_str)
        except TypeError:
            log_warning("Unable to remove code from HTML")
    b = BeautifulSoup(html_str, features="html.parser")
    return b.get_text(separator=" ")
