from fastapi.testclient import TestClient

from app.main import app


def test_cors_libera_apenas_frontend_local():
    client = TestClient(app)
    local = client.options(
        "/health",
        headers={
            "Origin": "http://127.0.0.1:19006",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert local.status_code == 200
    assert local.headers["access-control-allow-origin"] == "http://127.0.0.1:19006"

    external = client.options(
        "/health",
        headers={
            "Origin": "https://example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert external.status_code == 400
    assert "access-control-allow-origin" not in external.headers
