import os
import json
import logging
import requests
import urllib3
from urllib3.exceptions import InsecureRequestWarning
from dotenv import load_dotenv

load_dotenv()

urllib3.disable_warnings(InsecureRequestWarning)

os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    filename='logs/client.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LLMConnectionError(RuntimeError):
    """Falha de conexão com o servidor interno do LLM."""


class LLMTimeoutError(RuntimeError):
    """Tempo limite excedido aguardando resposta do LLM."""


class LLMResponseError(RuntimeError):
    """Erro HTTP do servidor ou resposta JSON inválida do LLM."""


class LLMClient:
    EXPECTED_FIELDS = ("titulo", "data_hora", "local", "descricao", "prioridade")

    def __init__(self):
        raw_url = os.getenv("LLM_URL")
        if not raw_url or not raw_url.strip():
            raise ValueError(
                "A variável de ambiente 'LLM_URL' é obrigatória e não foi configurada."
            )

        raw_model = os.getenv("LLM_MODEL")
        if not raw_model or not raw_model.strip():
            raise ValueError(
                "A variável de ambiente 'LLM_MODEL' é obrigatória e não foi configurada."
            )

        self.base_url = raw_url.strip().rstrip("/")
        self.model = raw_model.strip()
        self.timeout = int(os.getenv("LLM_TIMEOUT", "45"))
        

    @staticmethod
    def _sanitize_text(text: str, max_chars: int = 30) -> str:
        """Truncamento e remoção de quebras de linha do texto (evitar vazamento de dados nos logs)."""
        cleaned = " ".join(text.split())
        return f"{cleaned[:max_chars]}..." if len(cleaned) > max_chars else cleaned
    
    def _normalize_event_data(self, raw_data: dict) -> dict:
        """Garante que o retorno contenha exatamente as chaves esperadas e prioridade válida."""
        if not isinstance(raw_data, dict):
            raise LLMResponseError("O servidor LLM não retornou um objeto JSON válido.")

        normalized = {
            field: str(raw_data.get(field, "") or "").strip()
            for field in self.EXPECTED_FIELDS
        }

        prioridade = normalized["prioridade"].lower()
        if prioridade in {"alta", "média", "media", "baixa"}:
            normalized["prioridade"] = "média" if prioridade == "media" else prioridade
        else:
            normalized["prioridade"] = "média"

        return normalized

    def check_health(self) -> dict:
        """Verifica se o servidor Ollama interno está acessível (endpoint leve /api/tags)."""
        url = f"{self.base_url}/api/tags"
        try:
            response = requests.get(url, timeout=5, verify=False)
            response.raise_for_status()
            return {"reachable": True, "status_code": response.status_code}
        except requests.exceptions.RequestException as exc:
            logger.warning(f"Falha no healthcheck do LLM ({url}): {exc}")
            return {"reachable": False, "error": "Servidor LLM interno inacessível."}

    def extract_event_data(self, text: str) -> dict:
        """
        Envia o texto ao LLM interno e retorna um dicionário estruturado.
        """
        url = f"{self.base_url}/api/generate"
        
        prompt = f"""
        Você é um assistente de agendamento. Analise o texto abaixo e extraia informações de eventos.
        Retorne APENAS um JSON válido e estrito com as seguintes chaves (se algo não for encontrado, deixe vazio):
        "titulo": "Título curto gerado para o evento",
        "data_hora": "Data e hora mencionadas ou relativas",
        "local": "Local do evento",
        "descricao": "Breve descrição do contexto",
        "prioridade": "alta", "média" ou "baixa"
        
        Texto: {text}
        """
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json" 
        }
        
        safe_preview = self._sanitize_text(text)
        logger.info(f"Enviando requisição ao LLM | modelo={self.model} | preview='{safe_preview}'")
        
        try:
            response = requests.post(
                url,
                json=payload,
                timeout=self.timeout,
                verify=False,
            )
            response.raise_for_status()
            
            logger.info(f"Resposta recebida do LLM. HTTP {response.status_code}")
            
            body = response.json()
            raw_response = body.get("response")
            if not raw_response:
                logger.error("Campo 'response' ausente ou vazio no retorno do Ollama.")
                raise LLMResponseError("O servidor LLM retornou uma resposta vazia.")

            parsed = json.loads(raw_response)
            return self._normalize_event_data(parsed)
            
        except requests.exceptions.Timeout:
            logger.error(f"Timeout atingido ({self.timeout}s) na comunicação com o LLM.")
            raise LLMTimeoutError("O servidor LLM demorou muito para responder.")

        except requests.exceptions.ConnectionError:
            logger.error(f"Erro de conexão ao acessar o servidor LLM em {self.base_url}.")
            raise LLMConnectionError(
                "Não foi possível conectar ao servidor LLM interno. Tente novamente mais tarde."
            )

        except requests.exceptions.HTTPError as exc:
            status_code = exc.response.status_code
            logger.error(f"Erro HTTP {status_code} retornado pelo servidor LLM.")
            raise LLMResponseError(
                f"Falha ao contatar o servidor LLM interno (HTTP {status_code})."
            )

        except json.JSONDecodeError:
            logger.error("O LLM retornou conteúdo fora do formato JSON válido.")
            raise LLMResponseError(
                "O servidor LLM não retornou os dados em um formato JSON válido."
            )

        except LLMResponseError:
            raise

        except Exception as exc:
            logger.error(f"Erro inesperado na integração com o LLM: {exc}")
            raise LLMResponseError("Falha inesperada na comunicação com o servidor LLM.")
       