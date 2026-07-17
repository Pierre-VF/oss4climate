def test_import():
    # The most basic test to at least ensure that all dependencies imported work out

    import oss4climate_scripts
    from oss4climate_scripts import cli, scripts
    from oss4climate_scripts.scripts import (
        data_publication,
        discover_new_sources,
        discover_projects,
        misc,
        repository_scraping,
    )

    # Package
    assert isinstance(oss4climate_scripts.__name__, str)

    # Sub-packages
    assert isinstance(cli.__name__, str)
    assert isinstance(scripts.__name__, str)

    assert isinstance(data_publication.__name__, str)
    assert isinstance(discover_new_sources.__name__, str)
    assert isinstance(discover_projects.__name__, str)
    assert isinstance(misc.__name__, str)
    assert isinstance(repository_scraping.__name__, str)
