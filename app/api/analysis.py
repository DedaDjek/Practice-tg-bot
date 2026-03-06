from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

from app.db.db import get_db
from app.db import crud, models
from app.llm.quality_analyzer import YandexMessageAnalyzer
from app.schemas import AnalysisRequest, AnalysisResponse

router = APIRouter(prefix="/analysis", tags=["analysis"])

@router.post("/analyze")
async def analyze_messages(
    request: AnalysisRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    messages = db.query(models.Message).filter(
        models.Message.id.in_(request.message_ids)
    ).all()
    
    if not messages:
        raise HTTPException(status_code=404, detail="Messages not found")
    
    messages_data = []
    for msg in messages:
        context = db.query(models.Message).filter(
            models.Message.chat_id == msg.chat_id,
            models.Message.id < msg.id
        ).order_by(models.Message.id.desc()).limit(3).all()
        
        context_texts = [ctx.text for ctx in context if ctx.text]
        
        messages_data.append({
            'message_id': msg.id,
            'text': msg.text,
            'context': context_texts
        })
    
    background_tasks.add_task(run_analysis, messages_data, db)
    
    return {"status": "Analysis started", "messages_count": len(messages_data)}

@router.get("/message/{message_id}")
async def get_message_analysis(message_id: int, db: Session = Depends(get_db)):
    analyses = crud.get_message_analyses(db, message_id)
    if not analyses:
        raise HTTPException(status_code=404, detail="No analyses found")
    return analyses

@router.get("/needs-review")
async def get_messages_for_review(limit: int = 50, db: Session = Depends(get_db)):
    messages = crud.get_messages_needing_review(db, limit)
    return messages

@router.get("/stats")
async def get_quality_stats(
    chat_id: Optional[int] = None,
    days: int = 7,
    db: Session = Depends(get_db)
):
    stats = crud.get_quality_stats(db, chat_id, days)
    return {
        "avg_quality": float(stats.avg_quality) if stats.avg_quality else 0,
        "total_analyzed": stats.total_analyzed,
        "needs_review": stats.needs_review,
        "period_days": days
    }

async def run_analysis(messages_data: List[dict], db: Session):
    analyzer = YandexMessageAnalyzer()
    results = await analyzer.analyze_batch(messages_data)
    
    for result in results:
        analysis_data = {
            'message_id': result['message_id'],
            **result['analysis']
        }
        crud.create_message_analysis(db, analysis_data)