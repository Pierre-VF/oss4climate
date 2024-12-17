from docutils.core import publish_string

from oss4climate.src.nlp.html_io import find_all_links_in_html, html_to_clean_plaintext


def __rst_to_html(rst_str: str) -> str:
    x = publish_string(
        rst_str,
        parser_name="restructuredtext",
        writer_name="html",
    )
    return x


def find_all_links_in_rst(rst_str: str) -> list[str]:
    x = __rst_to_html(rst_str)
    links = find_all_links_in_html(x)
    return links


def rst_to_clean_plaintext(rst_str: str, *args, **kwargs) -> str:
    x = __rst_to_html(rst_str)
    return html_to_clean_plaintext(x)
