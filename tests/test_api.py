from fastapi.testclient import TestClient

from app.main import app


def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_creator_resolver_endpoint() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/creators/resolve",
            json={
                "url": "https://www.xiaohongshu.com/user/profile/abc123?foo=bar"
            },
        )

    assert response.status_code == 200
    assert response.json()["creator_id"] == "abc123"
