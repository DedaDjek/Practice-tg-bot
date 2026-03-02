from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

from app.db import crud
from app.db.db import get_db
from app.db.models import Message as MessageModel
from app.schemas import Message as MessageSchema

router = APIRouter(prefix="/messages", tags=["messages"])

@router.get("/", response_model=List[MessageSchema])
async def get_messages(
    chat_id: Optional[int] = None,
    user_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    if chat_id and start_date and end_date:
        messages = crud.get_messages_by_chat_and_date(db, chat_id, start_date, end_date)
    elif user_id:
        messages = crud.get_messages_by_user(db, user_id, limit)
    else:
        messages = db.query(MessageModel).limit(limit).all()
    return messages

@router.get("/{message_id}", response_model=MessageSchema)
async def get_message(message_id: int, db: Session = Depends(get_db)):
    message = db.query(MessageModel).filter(MessageModel.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    return message