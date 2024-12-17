from oss4climate.src.nlp.html_io import find_all_links_in_html
from oss4climate.src.nlp.markdown_io import find_all_links_in_markdown
from oss4climate.src.nlp.rst_io import find_all_links_in_rst


def test_find_all_links(github_organisation_url, github_repo_url):
    assert find_all_links_in_rst(
        """
Python_ is `my favourite programming language`__.

.. _Python: http://www.python.org/
.. _Python2: http://www.pythonx.org/

__ Python2_
    """
    ) == ["http://www.python.org/", "http://www.pythonx.org/"]

    assert find_all_links_in_markdown(
        f"""
    [repo]({github_organisation_url}) 
    and 
    [org]({github_repo_url})
            """
    ) == [github_organisation_url, github_repo_url]

    assert find_all_links_in_html("""""") == []
