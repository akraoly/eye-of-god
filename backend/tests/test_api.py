def test_health(client):
    r = client.get("/api/system/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "online"
    assert "version" in data


def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["status"] == "online"


def test_metrics(client):
    r = client.get("/api/system/metrics")
    assert r.status_code == 200
    assert "cpu_percent" in r.json()


def test_agents_list(client):
    r = client.get("/api/system/agents")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
