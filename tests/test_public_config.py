async def test_config_endpoint_default(client):
    resp = await client.get("/api/config")
    assert resp.status_code == 200
    assert resp.json() == {"demo_mode": False}
