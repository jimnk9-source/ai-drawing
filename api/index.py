from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

app = FastAPI()

# Vercel 환경에서는 상대 경로 관리가 중요합니다.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "../web/frontend")

@app.get("/")
async def read_index():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    return FileResponse(index_path)

# API 엔드포인트 예시 (나중에 이미지 분석용으로 사용)
@app.get("/api/health")
async def health_check():
    return {"status": "ok"}

# 이 파일이 Vercel의 진입점이 됩니다.
