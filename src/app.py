import os
import csv
import json
import logging
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Literal
from pathlib import Path


load_dotenv()

from src.client import (
    LLMClient,
    LLMConnectionError,
    LLMResponseError,
    LLMTimeoutError,
)

logger = logging.getLogger(__name__)

OUTPUT_DIR = os.getenv("OUTPUT_DIR", "data")
CSV_FIELDS = ["titulo", "data_hora", "local", "descricao", "prioridade"]

llm_client = LLMClient()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Preparação dos diretórios de saída e log antes de aceitar requisições."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    logger.info(f"API de Event Extractor iniciada. Diretório de saída: '{OUTPUT_DIR}'")
    yield
    logger.info("Encerrando Event Extractor API...")


app = FastAPI(
    title="Event Extractor API (Unified)",
    version="1.0.0",
    description=(
        "API de extração de eventos de agenda a partir de texto livre "
        "utilizando LLM interno com saída em CSV ou JSON."
    ),
    lifespan=lifespan,
)


class EventRequest(BaseModel):
    text: str = Field(
        ...,
        min_length=5,
        description="Texto em linguagem natural contendo informações de um evento.",
    )
    output_format: Literal["csv", "json"] = Field(
        default="csv",
        description="Formato de saída desejado: 'csv' (padrão) ou 'json'.",
    )


def save_event_file(event_data: dict, output_format: str) -> str:
    """Salva o evento extraído em OUTPUT_DIR com timestamp no nome para evitar sobrescrita."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    filename = f"evento_{timestamp}.{output_format}"
    filepath = os.path.join(OUTPUT_DIR, filename)

    if output_format == "csv":
        with open(filepath, mode="w", encoding="utf-8", newline="") as csv_file:
            writer = csv.DictWriter(
                csv_file,
                fieldnames=CSV_FIELDS,
                extrasaction="ignore",
            )
            writer.writeheader()
            writer.writerow(event_data)
    else:
        with open(filepath, mode="w", encoding="utf-8") as json_file:
            json.dump(event_data, json_file, ensure_ascii=False, indent=4)

    return filepath


@app.get("/health")
def health_check():
    """Verificação do status da API, diretório de saída ativo e conectividade com o LLM."""
    llm_status = llm_client.check_health()
    return {
        "status": "ok",
        "output_dir": OUTPUT_DIR,
        "llm_target": llm_client.base_url,
        "llm_connection": llm_status,
    }


@app.post("/events")
def extract_and_save_event(request: EventRequest):
    """Recebimento do texto, extração os dados via LLM interno e salva em CSV ou JSON na pasta data."""
    try:
        event_data = llm_client.extract_event_data(request.text)
        filepath = save_event_file(event_data, request.output_format)

        logger.info(f"Evento processado e salvo em: {filepath}")

        return {
            "status": "success",
            "message": "Evento extraído e salvo com sucesso.",
            "format": request.output_format,
            "file_saved": filepath,
            "data": event_data,
        }

    except LLMConnectionError as exc:
        logger.error(f"Indisponibilidade do LLM: {exc}")
        raise HTTPException(status_code=503, detail=str(exc))

    except LLMTimeoutError as exc:
        logger.error(f"Timeout do LLM: {exc}")
        raise HTTPException(status_code=504, detail=str(exc))

    except LLMResponseError as exc:
        logger.error(f"Erro na resposta do LLM: {exc}")
        raise HTTPException(status_code=502, detail=str(exc))

    except OSError as exc:
        logger.error(f"Erro de escrita em disco ({OUTPUT_DIR}): {exc}")
        raise HTTPException(
            status_code=500,
            detail="Não foi possível salvar o arquivo de saída no servidor.",
        )

    except Exception as exc:
        logger.error(f"Erro interno inesperado: {exc}")
        raise HTTPException(
            status_code=500,
            detail="Ocorreu um erro interno inesperado ao processar o evento.",
        )


@app.get("/files")
def list_generated_files():
    """Listagem de todos os arquivos CSV e JSON salvos no diretório de saída."""
    base_dir = Path(OUTPUT_DIR).resolve()
    if not base_dir.exists():
        return {"output_dir": str(base_dir), "total": 0, "files": []}

    files = sorted(
        [
            f.name
            for f in base_dir.iterdir()
            if f.is_file() and f.suffix.lower() in {".csv", ".json"}
        ],
        reverse=True,
    )

    return {
        "output_dir": OUTPUT_DIR,
        "total": len(files),
        "files": files,
    }


@app.get("/files/{filename}")
def download_generated_file(filename: str):
    """Faz o download de um arquivo CSV ou JSON específico da pasta de saída."""
    base_dir = Path(OUTPUT_DIR).resolve()
    target_file = (base_dir / filename).resolve()

    # Bloqueia tentativas de sair do diretório configurado (ex: ../../.env)
    if target_file.parent != base_dir or target_file.suffix.lower() not in {".csv", ".json"}:
        raise HTTPException(status_code=400, detail="Nome de arquivo inválido.")

    if not target_file.is_file():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.")

    media_type = "text/csv" if target_file.suffix.lower() == ".csv" else "application/json"
    return FileResponse(
        path=target_file,
        filename=target_file.name,
        media_type=media_type,
    )