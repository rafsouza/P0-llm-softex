import json

from src.exceptions import InvalidResponseError, ModelUnavailableError

EXPECTED_FIELDS = ("titulo", "data_hora", "local", "descricao", "prioridade")
CORE_CONTENT_FIELDS = ("titulo", "data_hora", "local", "descricao")
PRIORITY_MAP = {
    "alta": "alta",
    "média": "média",
    "media": "média",
    "baixa": "baixa",
}


def parse_event_response(raw_api_body: dict) -> dict:
    """Normalização dos campos do evento."""
    if not isinstance(raw_api_body, dict):
        raise InvalidResponseError(
            "Resposta do servidor LLM em formato inesperado (objeto JSON esperado)."
        )

    # Trata erros explícitos devolvidos no corpo JSON do Ollama
    error_message = raw_api_body.get("error")
    if error_message:
        if "not found" in str(error_message).lower():
            raise ModelUnavailableError("O modelo LLM escolhido não foi encontrado no servidor.")
        raise InvalidResponseError(f"Erro informado pelo servidor LLM: {error_message}")

    raw_model_output = raw_api_body.get("response")
    if not isinstance(raw_model_output, str) or not raw_model_output.strip():
        raise InvalidResponseError("O servidor LLM retornou uma resposta vazia.")

    try:
        parsed_event = json.loads(raw_model_output)
    except json.JSONDecodeError:
        raise InvalidResponseError(
            "O servidor LLM retornou dados em formato inesperado (JSON inválido)."
        )

    if not isinstance(parsed_event, dict):
        raise InvalidResponseError(
            "O servidor LLM não retornou um objeto JSON estruturado para o evento."
        )

    normalized = {
        field: str(parsed_event.get(field, "") or "").strip()
        for field in EXPECTED_FIELDS
    }

    if not any(normalized[field] for field in CORE_CONTENT_FIELDS):
        raise InvalidResponseError(
            "A resposta do LLM não contém informações válidas de evento."
        )

    raw_priority = normalized["prioridade"].lower()
    normalized["prioridade"] = PRIORITY_MAP.get(raw_priority, "média")

    return normalized