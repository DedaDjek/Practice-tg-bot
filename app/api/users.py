from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

from app.db import crud
from app.db.db import get_db
from app.db.models import User
from app.schemas import User as UserSchema

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/", response_model=List[UserSchema])
async def get_users(db: Session = Depends(get_db)):
    return db.query(User).all()

@router.get("/admins", response_model=List[UserSchema])
async def get_admins(db: Session = Depends(get_db)):
    return crud.get_all_admins(db)

@router.get("/{user_id}", response_model=UserSchema)
async def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user