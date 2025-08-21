from oss4climate.src.nlp.html_io import find_all_links_in_html
from oss4climate.src.nlp.markdown_io import find_all_links_in_markdown
from oss4climate.src.nlp.rst_io import find_all_links_in_rst


def test_find_all_links(github_organisation_url, github_repo_url):
    res = [github_organisation_url, github_repo_url]
    assert (
        find_all_links_in_rst(
            f"""
x0_ is `my favourite programming language`__.

.. _x0: {github_organisation_url}
.. _x1: {github_repo_url}

__ x1_
    """
        )
        == res
    )

    assert (
        find_all_links_in_markdown(
            f"""
    [repo]({github_organisation_url})
    and
    [org]({github_repo_url})
            """
        )
        == res
    )

    assert (
        find_all_links_in_html(
            f"""
<html>
    <body>
        <p>
            <a href="{github_organisation_url}">A</a>
            and
            <a href="{github_repo_url}">B</a>
        </p>
    </body>
</html>
            """
        )
        == res
    )
