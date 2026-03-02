from sqlalchemy.orm import Session
from sqlalchemy import and_, desc
from datetime import datetime, date
from typing import List, Optional, Dict, Any
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

from app.db import models

def get_user_by_telegram_id(db: Session, telegram_id: int):
    return db.query(models.User).filter(models.User.user_id == telegram_id).first()

def create_user(db: Session, user_data: Dict[str, Any]):
    user = models.User(**user_data)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def update_user(db: Session, user_id: int, user_data: Dict[str, Any]):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user:
        for key, value in user_data.items():
            setattr(user, key, value)
        db.commit()
        db.refresh(user)
    return user

def get_all_admins(db: Session):
    return db.query(models.User).filter(models.User.is_admin == True).all()

def get_chat_by_telegram_id(db: Session, chat_id: int):
    return db.query(models.Chat).filter(models.Chat.chat_id == chat_id).first()

def create_chat(db: Session, chat_data: Dict[str, Any]):
    chat = models.Chat(**chat_data)
    db.add(chat)
    db.commit()
    db.refresh(chat)
    return chat

def update_chat(db: Session, chat_id: int, chat_data: Dict[str, Any]):
    chat = db.query(models.Chat).filter(models.Chat.id == chat_id).first()
    if chat:
        for key, value in chat_data.items():
            setattr(chat, key, value)
        db.commit()
        db.refresh(chat)
    return chat

def get_all_chats(db: Session):
    return db.query(models.Chat).all()

def create_message(db: Session, message_data: Dict[str, Any]):
    message = models.Message(**message_data)
    db.add(message)
    db.commit()
    db.refresh(message)
    return message

def get_messages_by_chat_and_date(
    db: Session, 
    chat_id: int, 
    start_date: date, 
    end_date: date
):
    return db.query(models.Message).filter(
        and_(
            models.Message.chat_id == chat_id,
            models.Message.created_at >= start_date,
            models.Message.created_at <= end_date
        )
    ).order_by(desc(models.Message.created_at)).all()

def get_messages_by_user(db: Session, user_id: int, limit: int = 100):
    return db.query(models.Message).filter(
        models.Message.user_id == user_id
    ).order_by(desc(models.Message.created_at)).limit(limit).all()

def create_file(db: Session, file_data: Dict[str, Any]):
    file = models.File(**file_data)
    db.add(file)
    db.commit()
    db.refresh(file)
    return file

def get_file_by_telegram_id(db: Session, file_id: str):
    return db.query(models.File).filter(models.File.file_id == file_id).first()

def add_user_to_chat(db: Session, chat_id: int, user_id: int):
    member = models.ChatMember(chat_id=chat_id, user_id=user_id)
    db.add(member)
    db.commit()
    return member

def remove_user_from_chat(db: Session, chat_id: int, user_id: int):
    member = db.query(models.ChatMember).filter(
        and_(
            models.ChatMember.chat_id == chat_id,
            models.ChatMember.user_id == user_id,
            models.ChatMember.left_at.is_(None)
        )
    ).first()
    if member:
        member.left_at = datetime.utcnow()
        db.commit()
    return member