from fastapi.testclient import TestClient

from . import app, mark_test_mode


def test_app():
    mark_test_mode()
    with TestClient(app=app) as tc:
        assert tc.get("/", follow_redirects=False).status_code == 307
        assert tc.get("/ui/search").status_code == 200
        assert tc.get("/ui/results?query=iot&license=*&language=*").status_code == 200

        assert tc.get("/api/search?query=iot").status_code == 200
        assert tc.get("/api/data/credits").status_code == 200
        assert tc.get("/api/data/credits_html").status_code == 200

        # SEO endpoints test
        for i in ["robots.txt", "sitemap.xml"]:
            assert tc.get(f"/{i}").status_code == 200
