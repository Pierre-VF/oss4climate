def test_import():
    # The most basic test to at least ensure that all dependencies imported work out

    import oss4climate
    from oss4climate import cli, scripts

    # Package
    assert isinstance(oss4climate.__name__, str)

    # Sub-packages
    assert isinstance(cli.__name__, str)
    assert isinstance(scripts.__name__, str)


def test_import_src():
    from oss4climate import src
    from oss4climate.src import config, database, helpers, log, model, nlp, parsers

    assert isinstance(src.__name__, str)

    assert isinstance(database.__name__, str)
    assert isinstance(nlp.__name__, str)
    assert isinstance(parsers.__name__, str)
    assert isinstance(config.__name__, str)
    assert isinstance(helpers.__name__, str)
    assert isinstance(log.__name__, str)
    assert isinstance(model.__name__, str)
