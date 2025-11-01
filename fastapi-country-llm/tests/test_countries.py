from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_get_country_facts():
    response = client.get("/api/v1/countries/USA/facts")
    assert response.status_code == 200
    assert "capital" in response.json()
    assert "population" in response.json()

def test_get_country_culture():
    response = client.get("/api/v1/countries/USA/culture")
    assert response.status_code == 200
    assert "traditions" in response.json()
    assert "languages" in response.json()

def test_invalid_country():
    response = client.get("/api/v1/countries/INVALID/culture")
    assert response.status_code == 404
    assert response.json() == {"detail": "Country not found"}