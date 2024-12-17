from docutils.core import publish_string

from oss4climate.src.nlp.html_io import find_all_links_in_html


def find_all_links_in_rst(rst_str: str) -> str | None:
    x = publish_string(
        rst_str,
        parser_name="restructuredtext",
        writer_name="html",
    )

    links = find_all_links_in_html(x)
    return links
