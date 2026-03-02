from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

from app.db.db import get_db

router = APIRouter(tags=["health"])

@router.get("/health")
async def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return {
        "status": "alive",
        "database": db_status,
        "service": "Telegram Message Collector API"
    }