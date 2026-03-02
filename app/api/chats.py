from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

from app.db import crud
from app.db.db import get_db
from app.db.models import Chat
from app.schemas import Chat as ChatSchema

router = APIRouter(prefix="/chats", tags=["chats"])

@router.get("/", response_model=List[ChatSchema])
async def get_chats(db: Session = Depends(get_db)):
    return crud.get_all_chats(db)

@router.get("/{chat_id}", response_model=ChatSchema)
async def get_chat(chat_id: int, db: Session = Depends(get_db)):
    chat = crud.get_chat_by_telegram_id(db, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    return chat