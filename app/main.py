import asyncio
import logging

import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from fastapi import FastAPI

from app.bot.router import main_router
from app.config import settings
from app.services.grafana import GrafanaService

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

api = FastAPI(title="Grafana Bot API", version="0.1.0")


@api.get("/health", tags=["ops"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Bot startup
# ---------------------------------------------------------------------------


async def start_bot() -> None:
    bot = Bot(
        token=settings.TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(main_router)

    grafana = GrafanaService(
        url=settings.GRAFANA_URL,
        user=settings.GRAFANA_USER,
        password=settings.GRAFANA_PASSWORD,
    )

    logger.info("Starting Telegram bot (long-polling)…")
    await dp.start_polling(
        bot,
        allowed_updates=dp.resolve_used_update_types(),
        # Injected as a dependency into every handler that declares `grafana`
        grafana=grafana,
    )


# ---------------------------------------------------------------------------
# API startup
# ---------------------------------------------------------------------------


async def start_api() -> None:
    config = uvicorn.Config(
        app=api,
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )
    server = uvicorn.Server(config)
    logger.info("Starting FastAPI server on http://0.0.0.0:8000")
    await server.serve()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def main() -> None:
    """Run the Telegram bot and FastAPI server concurrently in one process."""
    await asyncio.gather(start_bot(), start_api())


def run() -> None:
    """Sync entry point for the `grafana-bot` script."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
