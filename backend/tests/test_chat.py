import pytest

# Les tests chat nécessitent ANTHROPIC_API_KEY dans .env

def test_chat_endpoint_exists(client):
    """Vérifier que l'endpoint existe (retourne 422 sans body, pas 404)"""
    r = client.post("/api/chat/")
    assert r.status_code in (200, 422, 500)  # pas 404

def test_clear_session(client):
    r = client.delete("/api/chat/session/test-session")
    assert r.status_code == 200
    assert "effacée" in r.json()["message"]
