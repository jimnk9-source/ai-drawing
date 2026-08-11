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
    contours: Optional[list] = None

class ContoursData(BaseModel):
    width: int
    height: int
    contours: list

class ClearRequest(BaseModel):
    saved_ids: list[int]

# 임시 데이터 저장소 (다중 큐 및 히스토리 관리)
tasks_db = []  # 각 task: {"task_id": int, "gcode": str, "contours": list, "status": str ("pending" | "drawing" | "complete")}
task_counter = 0

# 경로 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "../frontend")
if not os.path.exists(FRONTEND_DIR):
    FRONTEND_DIR = os.path.join(BASE_DIR, "../../web/frontend")

load_dotenv()

# --- G-Code 생성 로직 (하드웨어 최적화 버전) ---
# [수정] 펜 업/다운 명령을 표준 G-code 관례에 맞춰 통일:
#   M3 = Pen Down (펜 내림)
#   M5 = Pen Up   (펜 올림)
# ESP32 펌웨어의 processGCodeLine()이 "M3"이면 무조건 penDown(),
# "M5"이면 무조건 penUp()을 호출하므로 (S 파라미터는 읽지 않음),
# 기존처럼 "M3 S30"/"M3 S10"으로만 구분하면 둘 다 penDown()으로 처리되어
# 펜이 올라가야 할 때도 올라가지 않는 버그가 있었습니다.

def generate_gcode(contours, img_w, img_h):
    # A4 종이 너비(210mm) 기준, 여백 제외 약 180mm로 스케일링
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
        
        # 1. 시작점으로 이동 (Pen Up 상태)
        start_x = round(path[0]['x'] * scale, 2)
        start_y = round((img_h - path[0]['y']) * scale, 2) # Y축 반전
        gcode.append(f"G0 X{start_x} Y{start_y}")
        
        # 2. 펜 내리기
        gcode.append("M3 ; Pen Down")
        gcode.append("G4 P150 ; Wait for servo")
        
        # 3. 경로 따라 그리기
        for p in path:
            x_mm = round(p['x'] * scale, 2)
            y_mm = round((img_h - p['y']) * scale, 2) # Y축 반전
            gcode.append(f"G1 X{x_mm} Y{y_mm} F1500")
            
        # 4. 펜 올리기 (패스 끝)
        gcode.append("M5 ; Pen Up")
        gcode.append("G4 P150 ; Wait for servo")
        
    gcode.append("G0 X0 Y0 ; Return to home")
    return "\n".join(gcode)

# --- API 정의 시작 ---

@app.get("/")
async def read_index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

@app.post("/api/clear-task")
async def clear_task(req: ClearRequest):
    global tasks_db
    try:
        # 보관된 saved_ids에 들어있거나 현재 출력중('drawing')인 작업만 남겨두고 나머지는 큐에서 제거
        tasks_db = [t for t in tasks_db if t["task_id"] in req.saved_ids or t["status"] == "drawing"]
        print(f">>> SUCCESS: Queue Cleared (Saved preserved: {req.saved_ids})")
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
        print(f">>> SUCCESS: Task {task_counter} Pushed")
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
    # pending인 작업 중 가장 오래된 작업을 꺼내 상태를 drawing으로 업데이트 후 ESP32에 제공
    for task in tasks_db:
        if task["status"] == "pending":
            task["status"] = "drawing"
            print(f">>> ESP32 fetched task {task['task_id']}. Status: drawing")
            return {"task_id": task["task_id"], "gcode": task["gcode"]}
    return {"task_id": 0, "gcode": ""}

@app.post("/api/complete-task")
async def complete_task(task_id: int):
    global tasks_db
    for task in tasks_db:
        if task["task_id"] == task_id:
            task["status"] = "complete"
            print(f">>> ESP32 completed task {task_id}. Status: complete")
            return {"status": "success", "message": f"Task {task_id} completed"}
    return JSONResponse(status_code=404, content={"status": "error", "message": "태스크를 찾을 수 없습니다."})

@app.get("/api/tasks-status")
async def get_tasks_status():
    global tasks_db
    # 프론트엔드가 실시간 썸네일을 렌더링하기 위해 contours 전송
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
            # 직접 그린 그림이나 수정된 그림의 경우: 단순 이진화로 선의 형태를 최대한 보존
            # Canny나 AdaptiveThreshold를 쓰면 선의 안팎이 다 따져서 이중으로 그려질 수 있음
            _, combined_edges = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
        else:
            # 일반 사진의 경우: 기존 AI 드로잉 스타일(Canny + Adaptive) 적용
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            gray_clahe = clahe.apply(gray)
            blurred = cv2.bilateralFilter(gray_clahe, 11, 150, 150)
            edged = cv2.Canny(blurred, 50, 150) 
            thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 15, 4)
            combined_edges = cv2.bitwise_or(edged, thresh)

        contours, _ = cv2.findContours(combined_edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_TC89_L1)
        
        raw_contours = []
        if not is_drawing_bool:
            # (사진용) 어두운 영역 채우기 로직 유지
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
            
        # 외곽선 데이터화
        for cnt in contours:
            length = cv2.arcLength(cnt, True)
            area = cv2.contourArea(cnt)
            # 너무 작은 점들은 무시하되, 직접 그리기일 때는 더 민감하게 반응하도록 함
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
        
        # 수정된 G-Code 생성 호출 (w, h 파라미터 추가)
        gcode = generate_gcode(optimized_contours, w, h)
        
        _, buffer = cv2.imencode('.jpg', img)
        img_str = base64.b64encode(buffer).decode('utf-8')
        return {"width": w, "height": h, "contours": optimized_contours, "image": img_str, "gcode": gcode}
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import sys
    import os
    # 실행 시 상위 폴더(web 폴더 상위)도 인식할 수 있도록 경로 추가
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    
    # 코드 수정 시 자동으로 서버가 재시작되도록 reload=True 옵션 추가
    # python web/backend/server.py 로 실행 시 현재 파일이 server.py 이므로 "server:app" 사용
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)