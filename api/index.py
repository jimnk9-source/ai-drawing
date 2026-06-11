from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse
from dotenv import load_dotenv
import google.generativeai as genai
import os
import cv2
import numpy as np
import base64
from pydantic import BaseModel

app = FastAPI()

# 1. 경로 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "../web/frontend")

# 환경변수 로드
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

# 데이터 모델 정의
class DrawingTask(BaseModel):
    gcode: str

# 임시 데이터 저장소
drawing_queue = {
    "task_id": 0,
    "gcode": "",
    "status": "idle"
}

@app.get("/")
async def read_index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

# G-Code 생성 함수
def generate_gcode(contours):
    gcode = [
        "G21 ; Set units to mm",
        "G90 ; Absolute positioning",
        "M3 S30 ; Pen Up"
    ]
    for path in contours:
        if not path: continue
        gcode.append(f"G0 X{path[0]['x']} Y{path[0]['y']}")
        gcode.append("M3 S10 ; Pen Down")
        for p in path:
            gcode.append(f"G1 X{p['x']} Y{p['y']}")
        gcode.append("M3 S30 ; Pen Up")
    gcode.append("G0 X0 Y0 ; Return to home")
    return "\n".join(gcode)

@app.get("/api/get-task")
async def get_task():
    global drawing_queue
    if drawing_queue["status"] == "pending":
        drawing_queue["status"] = "idle"
        return {"task_id": drawing_queue["task_id"], "gcode": drawing_queue["gcode"]}
    return {"task_id": 0, "gcode": ""}

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
                    mask = np.zeros_like(gray)
                    cv2.drawContours(mask, [cnt], -1, 255, -1)
                    for d in range(-h, w, 8):
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
                approx = cv2.approxPolyDP(cnt, 0.001 * length, True)
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
        
        gcode = generate_gcode(optimized_contours)
        _, buffer = cv2.imencode('.jpg', img)
        img_str = base64.b64encode(buffer).decode('utf-8')
        return {"width": w, "height": h, "contours": optimized_contours, "image": img_str, "gcode": gcode}
    except Exception as e:
        return {"error": str(e)}
