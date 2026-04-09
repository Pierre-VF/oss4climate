import warnings

from oss4climate.src.nlp.html_io import find_all_links_in_html, html_to_search_plaintext


class RstParsingError(ValueError):
    pass


def __rst_to_html(rst_str: str) -> str:
    """
    Convert reStructuredText to HTML

    :param rst_str: reStructuredText string to convert
    :return: HTML string
    :raises RstParsingError: If RST parsing fails
    """
    from docutils.core import publish_string

    try:
        with warnings.catch_warnings():
            # warnings.simplefilter("ignore")
            x = publish_string(
                rst_str,
                parser="restructuredtext",
                writer="html",
            )
    except Exception as e:
        raise RstParsingError("Failed to parse RST file") from e
    return x


def find_all_links_in_rst(rst_str: str) -> list[str]:
    """
    Find all links in reStructuredText content

    :param rst_str: reStructuredText string to parse
    :return: List of URLs found in RST content
    """
    x = __rst_to_html(rst_str)
    links = find_all_links_in_html(x)
    return links


def rst_to_search_plaintext(rst_str: str, *args, **kwargs) -> str:
    """
    Convert reStructuredText to plain text for search purposes

    :param rst_str: reStructuredText string to convert
    :return: Plain text extracted from RST
    """
    x = __rst_to_html(rst_str)
    return html_to_search_plaintext(x)
