from fastapi import FastAPI, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from dotenv import load_dotenv
import os
import cv2
import numpy as np
import base64
import uvicorn
from pydantic import BaseModel
from typing import Optional

app = FastAPI()

# 데이터 모델 정의
class DrawingTask(BaseModel):
    gcode: str

# 임시 데이터 저장소
drawing_queue = {
    "task_id": 0,
    "gcode": "",
    "status": "idle"
}

# 경로 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "../frontend")
if not os.path.exists(FRONTEND_DIR):
    FRONTEND_DIR = os.path.join(BASE_DIR, "../../web/frontend")

load_dotenv()

# --- G-Code 생성 로직 (하드웨어 최적화 버전) ---

def generate_gcode(contours, img_w, img_h):
    # A4 종이 너비(210mm) 기준, 여백 제외 약 180mm로 스케일링
    target_width_mm = 180.0
    scale = target_width_mm / img_w
    
    gcode = [
        "G21 ; Set units to mm",
        "G90 ; Absolute positioning",
        "M3 S30 ; Pen Up",
        "G4 P150 ; Wait for servo",
        "F2000 ; Set default speed"
    ]
    
    for path in contours:
        if not path: continue
        
        # 1. 시작점으로 이동 (Pen Up 상태)
        start_x = round(path[0]['x'] * scale, 2)
        start_y = round((img_h - path[0]['y']) * scale, 2) # Y축 반전
        gcode.append(f"G0 X{start_x} Y{start_y}")
        
        # 2. 펜 내리기
        gcode.append("M3 S10 ; Pen Down")
        gcode.append("G4 P150 ; Wait for servo")
        
        # 3. 경로 따라 그리기
        for p in path:
            x_mm = round(p['x'] * scale, 2)
            y_mm = round((img_h - p['y']) * scale, 2) # Y축 반전
            gcode.append(f"G1 X{x_mm} Y{y_mm} F1500")
            
        # 4. 펜 올리기 (패스 끝)
        gcode.append("M3 S30 ; Pen Up")
        gcode.append("G4 P150 ; Wait for servo")
        
    gcode.append("G0 X0 Y0 ; Return to home")
    return "\n".join(gcode)

# --- API 정의 시작 ---

@app.get("/")
async def read_index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

@app.post("/api/clear-task")
async def clear_task():
    global drawing_queue
    try:
        drawing_queue = {"task_id": 0, "gcode": "", "status": "idle"}
        print(">>> SUCCESS: Queue Reset")
        return JSONResponse(content={"status": "success", "message": "모든 G-Code 데이터가 삭제되었습니다."})
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

@app.post("/api/push-task")
async def push_task(task: DrawingTask):
    global drawing_queue
    try:
        drawing_queue["gcode"] = task.gcode
        drawing_queue["task_id"] += 1
        drawing_queue["status"] = "pending"
        return {"status": "success", "task_id": drawing_queue["task_id"]}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/get-task")
async def get_task():
    global drawing_queue
    if drawing_queue["status"] == "pending":
        drawing_queue["status"] = "idle"
        return {"task_id": drawing_queue["task_id"], "gcode": drawing_queue["gcode"]}
    return {"task_id": 0, "gcode": ""}

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
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        gray_clahe = clahe.apply(gray)
        blurred = cv2.bilateralFilter(gray_clahe, 11, 150, 150)
        edged = cv2.Canny(blurred, 50, 150) 
        thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 15, 4)
        combined_edges = cv2.bitwise_or(edged, thresh)
        contours, _ = cv2.findContours(combined_edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_TC89_L1)
        
        raw_contours = []
        if not is_drawing_bool:
            _, black_mask = cv2.threshold(gray, 20, 255, cv2.THRESH_BINARY_INV)
            black_cnts, _ = cv2.findContours(black_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in black_cnts:
                area = cv2.contourArea(cnt)
                if area > 2500 and area < (h * w * 0.1):
                    spacing = 8
                    mask = np.zeros_like(gray)
                    cv2.drawContours(mask, [cnt], -1, 255, -1)
                    for d in range(-h, w, spacing):
                        line_points = []
                        for x in range(max(0, d), min(w, h + d)):
                            y = x - d
                            if mask[y, x] > 0: line_points.append({"x": x, "y": y})
                            else:
                                if len(line_points) > 1: raw_contours.append(line_points)
                                line_points = []
                        if len(line_points) > 1: raw_contours.append(line_points)
            
        for cnt in contours:
            length = cv2.arcLength(cnt, True)
            area = cv2.contourArea(cnt)
            if length >= 5 and area > 5: 
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
        
        # 수정된 G-Code 생성 호출 (w, h 파라미터 추가)
        gcode = generate_gcode(optimized_contours, w, h)
        
        _, buffer = cv2.imencode('.jpg', img)
        img_str = base64.b64encode(buffer).decode('utf-8')
        return {"width": w, "height": h, "contours": optimized_contours, "image": img_str, "gcode": gcode}
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
