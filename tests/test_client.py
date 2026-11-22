import json
import pytest
import requests
from src.client import (
    LLMClient,
    LLMConnectionError,
    LLMResponseError,
    LLMTimeoutError,
)

MOCK_LLM_URL = "https://mock-llm.local:9001"
MOCK_LLM_MODEL = "mock-model:latest"


@pytest.fixture
def llm_client(monkeypatch):
    monkeypatch.setenv("LLM_URL", MOCK_LLM_URL)
    monkeypatch.setenv("LLM_MODEL", MOCK_LLM_MODEL)
    monkeypatch.setenv("LLM_TIMEOUT", "45")
    return LLMClient()
 

def test_extract_event_data_success(requests_mock, llm_client):
    mock_event = {
        "titulo": "Reunião de alinhamento técnico",
        "data_hora": "amanhã às 14h",
        "local": "Sala de Conferência 2",
        "descricao": "arquitetura da nova API.",
        "prioridade": "alta"
    } 

    requests_mock.post(
        f"{MOCK_LLM_URL}/api/generate",
        json={"response": json.dumps(mock_event)},
        status_code=200,
    )

    result = llm_client.extract_event_data(
        "Precisamos fazer uma reunião de alinhamento técnico amanhã às 14h na Sala de Conferência 2 para discutir sobre a arquitetura da nova API."
    )

    assert result == mock_event
    assert requests_mock.last_request.verify is False

def test_extract_event_data_normalizes_missing_fields_and_priority(requests_mock, llm_client):
    mock_event = {
        "titulo": "Almoço com cliente",
        "data_hora": "Sexta ao meio-dia",
        "descricao": "Alinhamento comercial.",
        "prioridade": "urgente",
    }

    requests_mock.post(
        f"{MOCK_LLM_URL}/api/generate",
        json={"response": json.dumps(mock_event)},
        status_code=200,
    )

    result = llm_client.extract_event_data("Almoço sexta ao meio-dia")

    assert result["local"] == ""
    assert result["prioridade"] == "média"


def test_extract_event_data_timeout(requests_mock, llm_client):
    requests_mock.post(
        f"{MOCK_LLM_URL}/api/generate",
        exc=requests.exceptions.Timeout,
    )

    with pytest.raises(LLMTimeoutError, match="demorou muito para responder"):
        llm_client.extract_event_data("Teste de timeout")


def test_extract_event_data_connection_error(requests_mock, llm_client):
    requests_mock.post(
        f"{MOCK_LLM_URL}/api/generate",
        exc=requests.exceptions.ConnectionError,
    )

    with pytest.raises(LLMConnectionError, match="Não foi possível conectar"):
        llm_client.extract_event_data("Teste de queda de rede")


def test_extract_event_data_http_error(requests_mock, llm_client):
    requests_mock.post(
        f"{MOCK_LLM_URL}/api/generate",
        status_code=500,
    )

    with pytest.raises(LLMResponseError, match="HTTP 500"):
        llm_client.extract_event_data("Teste de erro interno do Ollama")


def test_extract_event_data_invalid_json(requests_mock, llm_client):
    requests_mock.post(
        f"{MOCK_LLM_URL}/api/generate",
        json={"response": "Claro! O evento será amanhã às 10h."},
        status_code=200,
    )

    with pytest.raises(LLMResponseError, match="formato JSON válido"):
        llm_client.extract_event_data("Teste de alucinação do modelo")


def test_sanitize_text_truncates_long_input():
    sensitive_text = "Reunião confidencial com CPF 123.456.789-00 e senha secreta no cofre."
    sanitized = LLMClient._sanitize_text(sensitive_text, max_chars=25)

    assert len(sanitized) == 28  # 25 caracteres + "..."
    assert "123.456.789-00" not in sanitized
    assert sanitized.endswith("...")


def test_check_health_reachable(requests_mock, llm_client):
    requests_mock.get(
        f"{MOCK_LLM_URL}/api/tags",
        json={"models": [{"name": "qwen3.5:9b-q4_K_M"}]},
        status_code=200,
    )

    status = llm_client.check_health()
    assert status["reachable"] is True
    assert status["status_code"] == 200