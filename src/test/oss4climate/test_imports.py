from oss4climate.src import models
from oss4climate.src.database import scrape_cache


def test_import():
    # The most basic test to at least ensure that all dependencies imported work out

    import oss4climate
    from oss4climate import src
    from oss4climate.src import config, helpers, log, nlp, parsers

    # Package
    assert isinstance(oss4climate.__name__, str)
    assert isinstance(src.__name__, str)

    assert isinstance(scrape_cache.__name__, str)
    assert isinstance(nlp.__name__, str)
    assert isinstance(parsers.__name__, str)
    assert isinstance(config.__name__, str)
    assert isinstance(helpers.__name__, str)
    assert isinstance(log.__name__, str)
    assert isinstance(models.__name__, str)
