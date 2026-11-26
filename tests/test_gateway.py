import json
import pytest
import requests
from fastapi.testclient import TestClient

from src.app import app

MOCK_URL = "https://mock-llm.local:9001"
MOCK_MODEL = "mock-model:latest"
MOCK_KEY = "test-secret-token"


@pytest.fixture
def configured_env(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_URL", MOCK_URL)
    monkeypatch.setenv("LLM_MODEL", MOCK_MODEL)
    monkeypatch.setenv("LLM_API_KEY", MOCK_KEY)
    monkeypatch.setenv("LLM_TIMEOUT", "45")
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    return tmp_path


def test_post_events_rejects_empty_text(configured_env):
    client = TestClient(app)
    response = client.post("/events", json={"text": "    ", "output_format": "csv"})
    assert response.status_code == 422


def test_post_events_returns_only_event_data_by_default(requests_mock, configured_env):
    mock_event = {
        "titulo": "Deploy Release v3",
        "data_hora": "Sexta às 14h",
        "local": "Sala 2",
        "descricao": "Subida da API modular.",
        "prioridade": "alta",
    }
    requests_mock.post(
        f"{MOCK_URL}/api/generate",
        json={"response": json.dumps(mock_event)},
        status_code=200,
    )

    client = TestClient(app)
    response = client.post(
        "/events",
        json={"text": "Deploy da release v3 sexta às 14h na Sala 2."},
    )

    assert response.status_code == 200
    assert response.json() == mock_event
    assert response.headers["x-file-saved"].endswith(".csv")

    saved_files = list(configured_env.glob("evento_*.csv"))
    assert len(saved_files) == 1


def test_post_events_optional_download_returns_file(requests_mock, configured_env):
    mock_event = {
        "titulo": "Reunião Técnica",
        "data_hora": "Segunda às 10h",
        "local": "Sala 1",
        "descricao": "Alinhamento de sprint.",
        "prioridade": "média",
    }
    requests_mock.post(
        f"{MOCK_URL}/api/generate",
        json={"response": json.dumps(mock_event)},
        status_code=200,
    )

    client = TestClient(app)
    response = client.post(
        "/events",
        json={
            "text": "Reunião técnica segunda às 10h na Sala 1.",
            "output_format": "json",
            "download": True,
        },
    )

    assert response.status_code == 200
    assert "attachment;" in response.headers["content-disposition"]
    assert ".json" in response.headers["content-disposition"]
    assert response.json() == mock_event


def test_post_events_returns_500_when_credential_missing(configured_env, monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    client = TestClient(app)
    response = client.post("/events", json={"text": "Reunião amanhã às 10h"})
    assert response.status_code == 500
    assert "Credencial ausente" in response.json()["detail"]


def test_post_events_returns_401_on_invalid_credential(requests_mock, configured_env):
    requests_mock.post(f"{MOCK_URL}/api/generate", status_code=401)
    client = TestClient(app)
    response = client.post("/events", json={"text": "Reunião amanhã às 10h"})
    assert response.status_code == 401
    assert "Credencial inválida" in response.json()["detail"]


def test_post_events_returns_504_on_timeout(requests_mock, configured_env):
    requests_mock.post(f"{MOCK_URL}/api/generate", exc=requests.exceptions.Timeout)
    client = TestClient(app)
    response = client.post("/events", json={"text": "Reunião amanhã às 10h"})
    assert response.status_code == 504