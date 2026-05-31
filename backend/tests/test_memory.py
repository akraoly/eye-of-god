def test_save_and_get_memory(client):
    r = client.post("/api/memory/save", json={
        "memory_type": "user",
        "key": "test_key",
        "value": "test_value",
        "importance": 0.9,
    })
    assert r.status_code == 200
    assert r.json()["key"] == "test_key"

    r = client.get("/api/memory/get")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    keys = [m["key"] for m in r.json()]
    assert "test_key" in keys


def test_profile(client):
    r = client.post("/api/memory/profile", json={"field": "nom", "value": "Testeur"})
    assert r.status_code == 200

    r = client.get("/api/memory/profile")
    assert r.status_code == 200
    assert r.json().get("nom") == "Testeur"


def test_user_profile_route(client):
    r = client.get("/api/user/profile")
    assert r.status_code == 200
    assert "profile" in r.json()
    assert "user_memories" in r.json()
