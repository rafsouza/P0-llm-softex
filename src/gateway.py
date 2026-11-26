
import logging
from typing import Literal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from src.client import LLMClient
from src.config import load_config
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
from src.presenter import ResultPresenter
from src.request_builder import build_generate_request
from src.response_parser import parse_event_response

logger = logging.getLogger(__name__)
router = APIRouter()


class EventRequest(BaseModel):
    text: str = Field(
        ...,
        description="Texto em linguagem natural contendo informações do evento.",
    )
    output_format: Literal["csv", "json"] = Field(
        default="csv",
        description="Formato do arquivo salvo em disco: 'csv' (padrão) ou 'json'.",
    )
    download: bool = Field(
        default=False,
        description="Se false (padrão), retorna apenas os dados JSON. Se true, faz o download do arquivo gerado.",
    )

    @field_validator("text")
    @classmethod
    def validate_non_empty_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("O texto de entrada não pode estar vazio.")
        if len(cleaned) < 5:
            raise ValueError("O texto deve conter pelo menos 5 caracteres úteis.")
        return cleaned


@router.get("/health")
def health_check():
    """Verificação de status."""
    try:
        config = load_config()
    except (MissingCredentialError, ConfigurationError) as exc:
        return {"status": "degraded", "config_error": str(exc)}

    llm_status = LLMClient(config).check_health()
    return {
        "status": "ok",
        "output_dir": config.output_dir,
        "llm_model": config.llm_model,
        "llm_connection": llm_status,
    }


@router.post("/events")
def process_event(payload: EventRequest):
    """
    Pipeline modular:
    1. Captura da entrada (EventRequest)
    2. Carregamento da configuração (load_config)
    3. Preparação da solicitação (build_generate_request)
    4. Chamada ao modelo (LLMClient.invoke)
    5. Tratamento da resposta (parse_event_response)
    6. Apresentação do resultado (apenas dados JSON por padrão ou download opcional)
    """
    try:
        config = load_config()
        request_spec = build_generate_request(payload.text, config)
        raw_response = LLMClient(config).invoke(request_spec)
        event_data = parse_event_response(raw_response)

        presenter = ResultPresenter(config.output_dir)
        filepath = presenter.save_event(event_data, payload.output_format)
        logger.info("Evento salvo em: %s", filepath)

        if payload.download:
            return presenter.build_download_response(filepath, payload.output_format)

        return presenter.build_data_response(event_data, filepath)

    except EmptyInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    except (MissingCredentialError, ConfigurationError) as exc:
        logger.error("Erro de configuração: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    except InvalidCredentialError as exc:
        raise HTTPException(status_code=401, detail=str(exc))

    except (ModelUnavailableError, CommunicationError) as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    except LLMTimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc))

    except InvalidResponseError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    except OSError as exc:
        logger.error("Falha ao gravar arquivo de saída: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="Não foi possível gravar o arquivo de saída no servidor.",
        )

    except Exception as exc:
        logger.error("Erro interno inesperado: %s", type(exc).__name__)
        raise HTTPException(
            status_code=500,
            detail="Ocorreu um erro interno inesperado ao processar o evento.",
        )


@router.get("/files")
def list_generated_files():
    """Listagem dos arquivos na pasta de saída."""
    try:
        config = load_config()
    except (MissingCredentialError, ConfigurationError) as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return ResultPresenter(config.output_dir).list_files()


@router.get("/files/{filename}")
def download_generated_file(filename: str):
    """Download dos arquivos salvos."""
    try:
        config = load_config()
    except (MissingCredentialError, ConfigurationError) as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    presenter = ResultPresenter(config.output_dir)
    target_file = presenter.resolve_safe_file(filename)

    if target_file is None:
        raise HTTPException(status_code=400, detail="Nome de arquivo inválido.")

    if not target_file.is_file():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.")

    output_format = "csv" if target_file.suffix.lower() == ".csv" else "json"
    return presenter.build_download_response(target_file, output_format)
