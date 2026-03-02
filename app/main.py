import sys
import os
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from fastapi import FastAPI
import asyncio
import logging
from dotenv import load_dotenv

from app.api.health import router as health_router
from app.api.messages import router as messages_router
from app.api.chats import router as chats_router
from app.api.users import router as users_router
from app.api.files import router as files_router
from app.db.db import engine, Base
from app.telegram.bot import UnifiedTelegramBot

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Telegram Message Collector API")

app.include_router(health_router)
app.include_router(messages_router)
app.include_router(chats_router)
app.include_router(users_router)
app.include_router(files_router)

telegram_bot = None

@app.on_event("startup")
async def startup_event():
    global telegram_bot
    
    logger.info("Starting up...")
    
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    admin_ids = os.getenv("TELEGRAM_ADMIN_IDS", "").split(",")
    admin_ids = [int(id.strip()) for id in admin_ids if id.strip()]
    
    if bot_token and admin_ids:
        telegram_bot = UnifiedTelegramBot(bot_token, admin_ids)
        asyncio.create_task(telegram_bot.run())
        logger.info("Telegram bot started")
        logger.info(f"Admin IDs: {admin_ids}")
    else:
        logger.warning("TELEGRAM_BOT_TOKEN or TELEGRAM_ADMIN_IDS not set in .env file")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down...")
    
    if telegram_bot:
        await telegram_bot.stop()

@app.get("/")
async def root():
    return {
        "message": "Telegram Message Collector API",
        "version": "1.0.0",
        "endpoints": [
            "/health",
            "/docs"
        ]
    }