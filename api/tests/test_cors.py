# api/tests/test_cors.py
def test_cors_rejects_unknown_origin(client):
    resp = client.options(
        "/health",
        headers={"Origin": "https://evil.com", "Access-Control-Request-Method": "GET"},
    )
    # Should NOT have Access-Control-Allow-Origin for evil.com
    assert resp.headers.get("access-control-allow-origin") != "https://evil.com"


def test_cors_allows_localhost(client):
    resp = client.options(
        "/health",
        headers={"Origin": "http://localhost:8000", "Access-Control-Request-Method": "GET"},
    )
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:8000"
