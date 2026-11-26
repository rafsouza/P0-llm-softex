import logging
import requests
import urllib3
from urllib3.exceptions import InsecureRequestWarning

from src.config import AppConfig
from src.exceptions import (
    CommunicationError,
    InvalidCredentialError,
    InvalidResponseError,
    LLMTimeoutError,
    ModelUnavailableError,
)
from src.request_builder import ModelRequestSpec

urllib3.disable_warnings(InsecureRequestWarning)

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self, config: AppConfig):
        self.config = config

    def invoke(self, request_spec: ModelRequestSpec) -> dict:
        """Chamada HTTP POST ao modelo LLM."""
        logger.info(
            "Chamando LLM | modelo=%s | url=%s | preview='%s'",
            self.config.llm_model,
            request_spec.url,
            request_spec.sanitized_preview,
        )

        try:
            response = requests.post(
                request_spec.url,
                json=request_spec.payload,
                headers=request_spec.headers,
                timeout=request_spec.timeout,
                verify=request_spec.verify_ssl,
            )
        except requests.exceptions.Timeout:
            logger.error("Timeout (%ss) aguardando resposta do LLM.", request_spec.timeout)
            raise LLMTimeoutError("O servidor LLM demorou muito para responder.")
        except requests.exceptions.ConnectionError:
            logger.error("Falha de comunicação ao conectar em %s.", self.config.llm_url)
            raise CommunicationError(
                "Falha de comunicação com o servidor LLM interno. Verifique a conectividade."
            )
        except requests.exceptions.RequestException as exc:
            logger.error("Erro de transporte na comunicação com o LLM: %s", type(exc).__name__)
            raise CommunicationError("Erro de comunicação ao tentar acessar o servidor LLM.")

        self._handle_http_status(response)

        try:
            body = response.json()
        except ValueError:
            logger.error("Corpo HTTP retornado pelo servidor LLM não é JSON válido.")
            raise InvalidResponseError(
                "O servidor LLM retornou uma resposta em formato inesperado (não JSON)."
            )

        logger.info("Resposta HTTP %s recebida do servidor LLM.", response.status_code)
        return body

    def _handle_http_status(self, response: requests.Response) -> None:
        status = response.status_code

        if status in (401, 403):
            logger.error("Acesso negado pelo servidor LLM (HTTP %s).", status)
            raise InvalidCredentialError(
                "Credencial inválida ou sem permissão para acessar o servidor LLM."
            )

        if status == 404:
            logger.error("Modelo ou endpoint não encontrado no servidor LLM (HTTP 404).")
            raise ModelUnavailableError(
                f"O modelo LLM escolhido ('{self.config.llm_model}') não está disponível no servidor."
            )

        if status in (502, 503, 504):
            logger.error("Servidor LLM temporariamente indisponível (HTTP %s).", status)
            raise ModelUnavailableError(
                f"O servidor LLM escolhido está temporariamente indisponível (HTTP {status})."
            )

        if status >= 400:
            logger.error("Erro HTTP inesperado retornado pelo servidor LLM: %s.", status)
            raise InvalidResponseError(
                f"Falha ao processar solicitação no servidor LLM (HTTP {status})."
            )

    def check_health(self) -> dict:
        """Consultar disponibilidade."""
        url = f"{self.config.llm_url}/api/tags"
        headers = {"Authorization": f"Bearer {self.config.llm_api_key}"}

        try:
            response = requests.get(
                url,
                headers=headers,
                timeout=5,
                verify=self.config.verify_ssl,
            )
            if response.status_code in (401, 403):
                return {"reachable": True, "authenticated": False, "status_code": response.status_code}

            response.raise_for_status()
            models = [m.get("name") for m in response.json().get("models", []) if isinstance(m, dict)]
            return {
                "reachable": True,
                "authenticated": True,
                "model_available": self.config.llm_model in models if models else None,
                "status_code": response.status_code,
            }
        except requests.exceptions.RequestException:
            logger.warning("Healthcheck do LLM falhou ao acessar %s.", url)
            return {"reachable": False, "authenticated": False}