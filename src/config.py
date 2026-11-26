import logging
import os
from dataclasses import dataclass
from urllib.parse import urlparse
from dotenv import load_dotenv

from src.exceptions import ConfigurationError, MissingCredentialError


load_dotenv()


@dataclass(frozen=True)
class AppConfig:
    llm_url: str
    llm_model: str
    llm_api_key: str
    llm_timeout: int
    output_dir: str
    verify_ssl: bool


def configure_logging() -> None:
    """Configuração do log."""
    os.makedirs("logs", exist_ok=True)
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        logging.basicConfig(
            filename="logs/client.log",
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )


def load_config() -> AppConfig:
    """Carregamento e validação das variáveis de ambiente."""
    raw_url = (os.getenv("LLM_URL") or "").strip()
    if not raw_url:
        raise ConfigurationError(
            "Configuração de acesso ausente: defina a variável de ambiente 'LLM_URL'."
        )

    parsed_url = urlparse(raw_url)
    if parsed_url.scheme not in ("http", "https") or not parsed_url.netloc:
        raise ConfigurationError(
            "Configuração de acesso inválida: 'LLM_URL' deve ser uma URL http ou https válida."
        )

    llm_model = (os.getenv("LLM_MODEL") or "").strip()
    if not llm_model:
        raise ConfigurationError(
            "Configuração de acesso ausente: defina a variável de ambiente 'LLM_MODEL'."
        )

    llm_api_key = (os.getenv("LLM_API_KEY") or "").strip()
    if not llm_api_key:
        raise MissingCredentialError(
            "Credencial ausente: defina a variável de ambiente 'LLM_API_KEY'."
        )

    raw_timeout = (os.getenv("LLM_TIMEOUT") or "45").strip()
    try:
        llm_timeout = int(raw_timeout)
        if llm_timeout <= 0:
            raise ValueError
    except ValueError:
        raise ConfigurationError(
            "Configuração inválida: 'LLM_TIMEOUT' deve ser um número inteiro maior que zero."
        )

    output_dir = (os.getenv("OUTPUT_DIR") or "data").strip()
    if not output_dir:
        raise ConfigurationError(
            "Configuração inválida: 'OUTPUT_DIR' não pode estar vazio."
        )

    # Padrão 'false' para compatibilidade com o certificado SSL autogerado interno
    verify_ssl = (os.getenv("LLM_VERIFY_SSL") or "false").strip().lower() == "true"

    return AppConfig(
        llm_url=raw_url.rstrip("/"),
        llm_model=llm_model,
        llm_api_key=llm_api_key,
        llm_timeout=llm_timeout,
        output_dir=output_dir,
        verify_ssl=verify_ssl,
    )