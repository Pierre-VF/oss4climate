from fastapi.testclient import TestClient

from . import app


def test_app():
    with TestClient(app=app) as tc:
        assert tc.get("/", follow_redirects=False).status_code == 307
        assert tc.get("/ui/search").status_code == 200
        assert tc.get("/ui/results?query=iot&license=*&language=*").status_code == 200
