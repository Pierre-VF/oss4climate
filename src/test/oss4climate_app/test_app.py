import pytest
from fastapi.testclient import TestClient
from oss4climate_app import app, mark_test_mode
from oss4climate_app.src.search import typesense_io


@pytest.fixture
def app_test_client(typesense_client):
    mark_test_mode()
    # Override dependencies
    app.dependency_overrides[typesense_io.generate_client] = lambda: typesense_client
    with TestClient(app=app) as tc:
        yield tc


def test_app(app_test_client):
    tc = app_test_client
    assert tc.get("/", follow_redirects=False).status_code == 307
    assert tc.get("/ui/search").status_code == 200
    assert tc.get("/ui/results?query=iot&license=*&language=*").status_code == 200

    assert tc.get("/api/search?query=iot").status_code == 200
    assert tc.get("/api/data/credits").status_code == 200
    assert tc.get("/api/data/credits_html").status_code == 200

    # SEO endpoints test
    for i in ["robots.txt", "sitemap.xml"]:
        assert tc.get(f"/{i}").status_code == 200


def test_empty_string_search_does_not_crash(app_test_client):
    """Regression test for issue #141: empty string search crashed due to shared
    mutable state in search_for_results. Calling it multiple times must not corrupt
    the shared DataFrame."""
    tc = app_test_client
    # First call with empty query
    assert tc.get("/ui/results").status_code == 200
    # Second call with empty query (would corrupt state before the fix)
    assert tc.get("/ui/results").status_code == 200
    # Non-empty query after empty query (would crash before the fix)
    assert tc.get("/ui/results?query=solar").status_code == 200
    # Empty query after non-empty query (would crash before the fix)
    assert tc.get("/ui/results").status_code == 200
