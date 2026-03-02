from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
import os
from pathlib import Path

router = APIRouter(tags=["files"])

DOWNLOAD_PATH = "downloads"

@router.get("/files/{filename}")
async def get_file(filename: str):
    file_path = os.path.join(DOWNLOAD_PATH, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type='application/octet-stream'
    )