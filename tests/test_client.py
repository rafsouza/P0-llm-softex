import json
import pytest
import requests

from src.client import LLMClient
from src.config import AppConfig, load_config
from src.exceptions import (
    CommunicationError,
    ConfigurationError,
    EmptyInputError,
    InvalidCredentialError,
    InvalidResponseError,
    LLMTimeoutError,
    MissingCredentialError,
    ModelUnavailableError,
)
from src.request_builder import build_generate_request, sanitize_text_for_log
from src.response_parser import parse_event_response

MOCK_URL = "https://mock-llm.local:9001"
MOCK_MODEL = "mock-model:latest"
MOCK_KEY = "test-secret-token"


@pytest.fixture
def valid_env(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_URL", MOCK_URL)
    monkeypatch.setenv("LLM_MODEL", MOCK_MODEL)
    monkeypatch.setenv("LLM_API_KEY", MOCK_KEY)
    monkeypatch.setenv("LLM_TIMEOUT", "45")
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("LLM_VERIFY_SSL", "false")


@pytest.fixture
def app_config(valid_env) -> AppConfig:
    return load_config()


# --- Testes de Carregamento de Configuração ---

def test_load_config_missing_url(valid_env, monkeypatch):
    monkeypatch.delenv("LLM_URL", raising=False)
    with pytest.raises(ConfigurationError, match="LLM_URL"):
        load_config()


def test_load_config_invalid_url_scheme(valid_env, monkeypatch):
    monkeypatch.setenv("LLM_URL", "ftp://servidor-invalido")
    with pytest.raises(ConfigurationError, match="http ou https"):
        load_config()


def test_load_config_missing_credential(valid_env, monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    with pytest.raises(MissingCredentialError, match="Credencial ausente"):
        load_config()


def test_load_config_invalid_timeout(valid_env, monkeypatch):
    monkeypatch.setenv("LLM_TIMEOUT", "abc")
    with pytest.raises(ConfigurationError, match="LLM_TIMEOUT"):
        load_config()


# --- Testes de Preparação da Solicitação ---

def test_request_builder_blocks_empty_input(app_config):
    with pytest.raises(EmptyInputError, match="não pode estar vazio"):
        build_generate_request("    \n\t  ", app_config)


def test_sanitize_text_truncates_sensitive_content():
    text = "Reunião confidencial com CPF 123.456.789-00 e dados bancários."
    preview = sanitize_text_for_log(text, max_chars=25)
    assert "123.456.789-00" not in preview
    assert preview.endswith("...")


# --- Testes de Chamada ao Modelo (HTTP Mock) ---

def test_client_invoke_success_with_bearer_and_ssl_bypass(requests_mock, app_config):
    expected_body = {"response": json.dumps({"titulo": "Daily", "prioridade": "baixa"})}
    requests_mock.post(f"{MOCK_URL}/api/generate", json=expected_body, status_code=200)

    spec = build_generate_request("Daily amanhã às 9h no Meet", app_config)
    body = LLMClient(app_config).invoke(spec)

    assert body == expected_body
    assert requests_mock.last_request.verify is False
    assert requests_mock.last_request.headers["Authorization"] == f"Bearer {MOCK_KEY}"


def test_client_invoke_invalid_credential_401(requests_mock, app_config):
    requests_mock.post(f"{MOCK_URL}/api/generate", status_code=401)
    spec = build_generate_request("Reunião amanhã às 10h", app_config)

    with pytest.raises(InvalidCredentialError, match="Credencial inválida"):
        LLMClient(app_config).invoke(spec)


def test_client_invoke_model_unavailable_404(requests_mock, app_config):
    requests_mock.post(f"{MOCK_URL}/api/generate", status_code=404)
    spec = build_generate_request("Reunião amanhã às 10h", app_config)

    with pytest.raises(ModelUnavailableError, match="não está disponível"):
        LLMClient(app_config).invoke(spec)


def test_client_invoke_service_unavailable_503(requests_mock, app_config):
    requests_mock.post(f"{MOCK_URL}/api/generate", status_code=503)
    spec = build_generate_request("Reunião amanhã às 10h", app_config)

    with pytest.raises(ModelUnavailableError, match="temporariamente indisponível"):
        LLMClient(app_config).invoke(spec)


def test_client_invoke_connection_error(requests_mock, app_config):
    requests_mock.post(f"{MOCK_URL}/api/generate", exc=requests.exceptions.ConnectionError)
    spec = build_generate_request("Reunião amanhã às 10h", app_config)

    with pytest.raises(CommunicationError, match="Falha de comunicação"):
        LLMClient(app_config).invoke(spec)


def test_client_invoke_timeout(requests_mock, app_config):
    requests_mock.post(f"{MOCK_URL}/api/generate", exc=requests.exceptions.Timeout)
    spec = build_generate_request("Reunião amanhã às 10h", app_config)

    with pytest.raises(LLMTimeoutError, match="demorou muito"):
        LLMClient(app_config).invoke(spec)


# --- Testes de Tratamento da Resposta ---

def test_parse_event_response_normalizes_fields():
    raw_body = {
        "response": json.dumps({
            "titulo": "Revisão da Sprint",
            "data_hora": "Quinta às 15h",
            "descricao": "Demonstração da release v3.",
            "prioridade": "media",
        })
    }
    parsed = parse_event_response(raw_body)
    assert parsed["local"] == ""
    assert parsed["prioridade"] == "média"


def test_parse_event_response_empty_string():
    with pytest.raises(InvalidResponseError, match="resposta vazia"):
        parse_event_response({"response": "   "})


def test_parse_event_response_invalid_json():
    with pytest.raises(InvalidResponseError, match="JSON inválido"):
        parse_event_response({"response": "Texto solto sem JSON"})


def test_parse_event_response_unexpected_structure():
    with pytest.raises(InvalidResponseError, match="objeto JSON estruturado"):
        parse_event_response({"response": '["lista", "nao", "suportada"]'})