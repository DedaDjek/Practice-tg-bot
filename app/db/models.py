from sqlalchemy import Column, Integer, String, Text, DateTime, BigInteger, ForeignKey, Boolean, Index
from sqlalchemy.orm import relationship
from datetime import datetime
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

from app.db.db import Base

class Chat(Base):
    __tablename__ = "chats"
    
    id = Column(Integer, primary_key=True)
    chat_id = Column(BigInteger, unique=True, nullable=False, index=True)
    title = Column(String(255))
    chat_type = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    messages = relationship("Message", back_populates="chat")
    users = relationship("User", secondary="chat_members", back_populates="chats")

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(255))
    first_name = Column(String(255))
    last_name = Column(String(255))
    phone = Column(String(50))
    is_bot = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    messages = relationship("Message", back_populates="user")
    chats = relationship("Chat", secondary="chat_members", back_populates="users")

class ChatMember(Base):
    __tablename__ = "chat_members"
    
    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, ForeignKey("chats.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    joined_at = Column(DateTime, default=datetime.utcnow)
    left_at = Column(DateTime, nullable=True)

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True)
    message_id = Column(BigInteger, nullable=False)
    chat_id = Column(Integer, ForeignKey("chats.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    text = Column(Text)
    file_path = Column(String(500))
    file_type = Column(String(50))
    reply_to_message_id = Column(BigInteger, nullable=True)
    forwarded_from = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_chat_message', 'chat_id', 'message_id', unique=True),
    )
    
    chat = relationship("Chat", back_populates="messages")
    user = relationship("User", back_populates="messages")

class File(Base):
    __tablename__ = "files"
    
    id = Column(Integer, primary_key=True)
    file_id = Column(String(255), unique=True, nullable=False)
    file_path = Column(String(500))
    file_name = Column(String(255))
    mime_type = Column(String(100))
    file_size = Column(BigInteger)
    message_id = Column(Integer, ForeignKey("messages.id"))
    created_at = Column(DateTime, default=datetime.utcnow)