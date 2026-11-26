import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI

from src.config import configure_logging, load_config
from src.exceptions import ConfigurationError
from src.gateway import router as gateway_router
from src.presenter import ResultPresenter

configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Valida a configuração inicial e prepara o diretório de saída ao subir o container."""
    try:
        config = load_config()
        ResultPresenter(config.output_dir).ensure_output_dir()
        logger.info(
            "Event Extractor API v3.0.0 iniciada | modelo=%s | output_dir=%s",
            config.llm_model,
            config.output_dir,
        )
    except ConfigurationError as exc:
        logger.error("Aplicação iniciada com erro de configuração: %s", exc)

    yield
    logger.info("Encerrando Event Extractor API...")


app = FastAPI(
    title="Event Extractor API",
    version="2.0.0",
    description="API modular para extração de eventos via LLM interno com download imediato em CSV/JSON.",
    lifespan=lifespan,
)

app.include_router(gateway_router)