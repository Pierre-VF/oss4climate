def test_import():
    # The most basic test to at least ensure that all dependencies imported work out

    import oss4climate
    from oss4climate import app, listings

    # Package
    assert isinstance(oss4climate.__name__, str)
    assert isinstance(listings.__name__, str)
    assert isinstance(app.__name__, str)
