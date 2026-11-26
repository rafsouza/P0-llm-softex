from dataclasses import dataclass

from src.config import AppConfig
from src.exceptions import EmptyInputError


@dataclass(frozen=True)
class ModelRequestSpec:
    url: str
    headers: dict
    payload: dict
    timeout: int
    verify_ssl: bool
    sanitized_preview: str


def sanitize_text_for_log(text: str, max_chars: int = 30) -> str:
    """Evitar vazamento de dados nos logs."""
    cleaned = " ".join(text.split())
    return f"{cleaned[:max_chars]}..." if len(cleaned) > max_chars else cleaned


def build_event_prompt(text: str) -> str:
    """Prompt instrucional estruturado para extração de dados de agenda."""
    return (
        "Você é um assistente de agendamento. Analise o texto abaixo e extraia os dados "
        "do evento para adição em uma agenda virtual.\n"
        "Retorne APENAS um objeto JSON válido com exatamente estas chaves "
        "(se algum dado não existir no texto, retorne string vazia):\n"
        "{\n"
        '  "titulo": "Título curto gerado para o evento",\n'
        '  "data_hora": "Data e hora mencionadas ou relativas",\n'
        '  "local": "Local do evento",\n'
        '  "descricao": "Resumo objetivo do contexto do evento",\n'
        '  "prioridade": "alta, média ou baixa"\n'
        "}\n\n"
        f"Texto: {text}"
    )


def build_generate_request(text: str, config: AppConfig) -> ModelRequestSpec:
    """Validação a entrada e preparação da URL, cabeçalhos e payload JSON."""
    if not isinstance(text, str) or not text.strip():
        raise EmptyInputError("O texto de entrada não pode estar vazio.")

    cleaned_text = text.strip()

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.llm_api_key}",
    }

    payload = {
        "model": config.llm_model,
        "prompt": build_event_prompt(cleaned_text),
        "stream": False,
        "format": "json",
    }

    return ModelRequestSpec(
        url=f"{config.llm_url}/api/generate",
        headers=headers,
        payload=payload,
        timeout=config.llm_timeout,
        verify_ssl=config.verify_ssl,
        sanitized_preview=sanitize_text_for_log(cleaned_text),
    )