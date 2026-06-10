from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn
import os

app = FastAPI()

# 프론트엔드 파일 경로 설정
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "../frontend")

@app.get("/")
async def read_index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

if __name__ == "__main__":
    print("Vico UI 서버를 시작합니다: http://127.0.0.1:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000)
