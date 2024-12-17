from docutils import frontend, utils
from docutils.parsers.rst import Parser

from .html_io import find_all_links_in_html


def find_all_links_in_rst(rst_str: str) -> str | None:
    settings = frontend.get_default_settings(Parser)
    document = utils.new_document("out.rst", settings)
    Parser().parse(rst_str, document)

    links = find_all_links_in_html(document.pformat())
    return links
