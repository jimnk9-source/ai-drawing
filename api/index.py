from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse
from dotenv import load_dotenv
import os
import cv2
import numpy as np
import base64
from pydantic import BaseModel
from typing import Optional

app = FastAPI()

# 데이터 모델 정의
class DrawingTask(BaseModel):
    gcode: str
    contours: Optional[list] = None

class ContoursData(BaseModel):
    width: int
    height: int
    contours: list

class ClearRequest(BaseModel):
    saved_ids: list[int]

# 임시 데이터 저장소 (다중 큐 및 히스토리 관리)
tasks_db = []
task_counter = 0

# 경로 설정 (Vercel 배포 환경 고려)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "../web/frontend")
if not os.path.exists(FRONTEND_DIR):
    FRONTEND_DIR = os.path.join(BASE_DIR, "../frontend")
if not os.path.exists(FRONTEND_DIR):
    FRONTEND_DIR = os.path.join(BASE_DIR, "../../web/frontend")

load_dotenv()

def generate_gcode(contours, img_w, img_h):
    target_width_mm = 180.0
    scale = target_width_mm / img_w
    
    gcode = [
        "G21 ; Set units to mm",
        "G90 ; Absolute positioning",
        "M5 ; Pen Up",
        "G4 P150 ; Wait for servo",
        "F2000 ; Set default speed"
    ]
    
    for path in contours:
        if not path: continue
        start_x = round(path[0]['x'] * scale, 2)
        start_y = round((img_h - path[0]['y']) * scale, 2)
        gcode.append(f"G0 X{start_x} Y{start_y}")
        gcode.append("M3 ; Pen Down")
        gcode.append("G4 P150 ; Wait for servo")
        
        for p in path:
            x_mm = round(p['x'] * scale, 2)
            y_mm = round((img_h - p['y']) * scale, 2)
            gcode.append(f"G1 X{x_mm} Y{y_mm} F1500")
            
        gcode.append("M5 ; Pen Up")
        gcode.append("G4 P150 ; Wait for servo")
        
    gcode.append("G0 X0 Y0 ; Return to home")
    return "\n".join(gcode)

@app.get("/")
async def read_index():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return JSONResponse(status_code=404, content={"detail": "index.html을 찾을 수 없습니다."})

@app.post("/api/clear-task")
async def clear_task(req: ClearRequest):
    global tasks_db
    try:
        tasks_db = [t for t in tasks_db if t["task_id"] in req.saved_ids or t["status"] == "drawing"]
        return JSONResponse(content={"status": "success", "message": "저장된 데이터를 제외하고 모든 G-Code가 삭제되었습니다."})
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

@app.post("/api/push-task")
async def push_task(task: DrawingTask):
    global tasks_db, task_counter
    try:
        task_counter += 1
        new_task = {
            "task_id": task_counter,
            "gcode": task.gcode,
            "contours": task.contours or [],
            "status": "pending"
        }
        tasks_db.append(new_task)
        return {"status": "success", "task_id": task_counter}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/update-gcode")
async def update_gcode(data: ContoursData):
    try:
        gcode = generate_gcode(data.contours, data.width, data.height)
        return {"status": "success", "gcode": gcode}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/get-task")
async def get_task():
    global tasks_db
    for task in tasks_db:
        if task["status"] == "pending":
            task["status"] = "drawing"
            return {"task_id": task["task_id"], "gcode": task["gcode"]}
    return {"task_id": 0, "gcode": ""}

@app.post("/api/complete-task")
async def complete_task(task_id: int):
    global tasks_db
    for task in tasks_db:
        if task["task_id"] == task_id:
            task["status"] = "complete"
            return {"status": "success", "message": f"Task {task_id} completed"}
    return JSONResponse(status_code=404, content={"status": "error", "message": "태스크를 찾을 수 없습니다."})

@app.get("/api/tasks-status")
async def get_tasks_status():
    global tasks_db
    return [
        {
            "task_id": t["task_id"],
            "contours": t["contours"],
            "status": t["status"]
        } for t in tasks_db
    ]

@app.post("/api/process-image")
async def process_image(file: UploadFile = File(...), is_drawing: str = Form("false")):
    try:
        is_drawing_bool = is_drawing.lower() == "true"
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None: return {"error": "이미지를 읽을 수 없습니다."}

        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        if is_drawing_bool:
            _, combined_edges = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
        else:
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            gray_clahe = clahe.apply(gray)
            blurred = cv2.bilateralFilter(gray_clahe, 11, 150, 150)
            edged = cv2.Canny(blurred, 50, 150) 
            thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 15, 4)
            combined_edges = cv2.bitwise_or(edged, thresh)

        contours, _ = cv2.findContours(combined_edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_TC89_L1)
        raw_contours = []
        
        for cnt in contours:
            length = cv2.arcLength(cnt, True)
            area = cv2.contourArea(cnt)
            min_len = 2 if is_drawing_bool else 5
            min_area = 1 if is_drawing_bool else 5
            
            if length >= min_len and area > min_area: 
                epsilon = 0.001 * length 
                approx = cv2.approxPolyDP(cnt, epsilon, True)
                points = [{"x": int(p[0][0]), "y": int(p[0][1])} for p in approx]
                if len(points) > 1: raw_contours.append(points)

        optimized_contours = []
        if raw_contours:
            raw_contours.sort(key=lambda c: (c[0]['y'], c[0]['x']))
            current_path = raw_contours.pop(0)
            while raw_contours:
                last_p = current_path[-1]
                found_next = False
                for i in range(min(len(raw_contours), 20)):
                    next_cnt = raw_contours[i]
                    dist = ((last_p['x'] - next_cnt[0]['x'])**2 + (last_p['y'] - next_cnt[0]['y'])**2)**0.5
                    if dist < 10:
                        current_path.extend(raw_contours.pop(i))
                        found_next = True
                        break
                if not found_next:
                    optimized_contours.append(current_path)
                    current_path = raw_contours.pop(0)
            optimized_contours.append(current_path)
        
        gcode = generate_gcode(optimized_contours, w, h)
        _, buffer = cv2.imencode('.jpg', img)
        img_str = base64.b64encode(buffer).decode('utf-8')
        return {"width": w, "height": h, "contours": optimized_contours, "image": img_str, "gcode": gcode}
    except Exception as e:
        return {"error": str(e)}