from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, List, Any

class MessageBase(BaseModel):
    message_id: int
    text: Optional[str] = None
    file_path: Optional[str] = None
    file_type: Optional[str] = None
    created_at: datetime

class MessageCreate(MessageBase):
    chat_id: int
    user_id: int

class Message(MessageBase):
    id: int
    chat_id: int
    user_id: int
    
    model_config = ConfigDict(from_attributes=True)

class UserBase(BaseModel):
    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_admin: bool = False

class UserCreate(UserBase):
    pass

class User(UserBase):
    id: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class ChatBase(BaseModel):
    chat_id: int
    title: Optional[str] = None
    chat_type: str

class ChatCreate(ChatBase):
    pass

class Chat(ChatBase):
    id: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class MessageExport(BaseModel):
    message_id: int
    text: Optional[str]
    user_name: str
    user_id: int
    created_at: datetime
    file_type: Optional[str]
    file_path: Optional[str]
    file_link: Optional[str] = None

class ChatExport(BaseModel):
    chat_title: str
    chat_id: int
    messages: List[MessageExport]
    start_date: datetime
    end_date: datetime

class MessageAnalysisBase(BaseModel):
    quality_score: int
    sentiment: str
    is_question: bool
    is_answer: bool
    needs_review: bool
    tags: List[str]
    summary: str

class MessageAnalysisCreate(MessageAnalysisBase):
    message_id: int

class MessageAnalysis(MessageAnalysisBase):
    id: int
    message_id: int
    analyzed_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class AnalysisRequest(BaseModel):
    message_ids: List[int]

class AnalysisResponse(BaseModel):
    message_id: int
    quality_score: int
    sentiment: str
    is_question: bool
    is_answer: bool
    needs_review: bool
    tags: List[str]
    summary: str