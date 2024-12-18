from bs4 import BeautifulSoup


def find_all_links_in_html(html_str: str) -> list[str]:
    b = BeautifulSoup(html_str, features="html.parser")
    rs = b.findAll(name="a")
    return [x.get("href") for x in rs]


def html_to_search_plaintext(html_str: str) -> list[str]:
    b = BeautifulSoup(html_str, features="html.parser")
    return b.get_text(separator=" ")
