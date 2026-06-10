from fastapi import FastAPI, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv
import google.generativeai as genai
import uvicorn
import os
import cv2
import numpy as np
import base64
import io

app = FastAPI()

# 1. 경로 및 환경변수 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv()

# 키 로딩
api_key = os.getenv("GOOGLE_API_KEY")
if api_key:
    print("✅ API 키 로드 성공")
    genai.configure(api_key=api_key)
else:
    print("🚨 [에러] GOOGLE_API_KEY를 찾을 수 없습니다!")

# 프론트엔드 파일 경로 설정
FRONTEND_DIR = os.path.join(BASE_DIR, "../frontend")

@app.get("/")
async def read_index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

# 스케치 효과 함수 (고품질 볼펜 스케치 느낌)
def sketch_effect(img):
    # 1. 그레이스케일 변환
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # 2. 볼펜 느낌을 위한 엣지 추출
    edges = cv2.Canny(gray, 30, 100)
    
    # 3. 펜 선 느낌을 위해 반전된 가우시안 블러를 이용한 디테일 추출
    inv = cv2.bitwise_not(gray)
    blur = cv2.GaussianBlur(inv, (21, 21), 0)
    pencil_sketch = cv2.divide(gray, cv2.bitwise_not(blur), scale=256.0)
    
    # 4. 결과 합성 (엣지 강조)
    # 스케치 위에 엣지를 조금 더 진하게 입힙니다.
    result = cv2.bitwise_and(pencil_sketch, pencil_sketch, mask=cv2.bitwise_not(edges))
    
    return cv2.cvtColor(result, cv2.COLOR_GRAY2BGR)

# G-Code 생성 함수
def generate_gcode(contours):
    gcode = ["G21 ; Set units to mm", "G90 ; Absolute positioning", "M3 S30 ; Pen Up"]
    for path in contours:
        # 펜 다운 (그리기 시작)
        gcode.append(f"G0 X{path[0]['x']} Y{path[0]['y']}")
        gcode.append("M3 S10 ; Pen Down")
        for p in path:
            gcode.append(f"G1 X{p['x']} Y{p['y']}")
        # 펜 업 (그리기 끝)
        gcode.append("M3 S30 ; Pen Up")
    return "\n".join(gcode)

@app.post("/api/process-image")
async def process_image(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            return {"error": "이미지를 읽을 수 없습니다."}

        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        gray_clahe = clahe.apply(gray)
        
        # 이미지 처리 (Opencv)
        blurred = cv2.bilateralFilter(gray_clahe, 11, 150, 150)
        edged = cv2.Canny(blurred, 50, 150) 
        thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 15, 4)
        combined_edges = cv2.bitwise_or(edged, thresh)
        _, black_mask = cv2.threshold(gray, 20, 255, cv2.THRESH_BINARY_INV) # 25 -> 20 (더 어두운 영역만)

        contours, _ = cv2.findContours(combined_edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_TC89_L1)
        black_cnts, _ = cv2.findContours(black_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        raw_contours = []
        for cnt in black_cnts:
            area = cv2.contourArea(cnt)
            if area > 2500 and area < (h * w * 0.1): # 1500 -> 2500 (더 큰 영역만)
                spacing = 8 # 밀도를 2배 높이기 위해 15에서 8로 낮춤
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
            # 형태를 가진 작은 도형은 유지하되 점 노이즈만 효과적으로 제거
            if length >= 5 and area > 5: 
                epsilon = 0.001 * length 
                approx = cv2.approxPolyDP(cnt, epsilon, True)
                points = [{"x": int(p[0][0]), "y": int(p[0][1])} for p in approx]
                if len(points) > 1:
                    raw_contours.append(points)

        optimized_contours = []
        if raw_contours:
            raw_contours.sort(key=lambda c: (c[0]['y'], c[0]['x']))
            current_path = raw_contours.pop(0)
            while raw_contours:
                last_p = current_path[-1]
                found_next = False
                for i in range(min(len(raw_contours), 20)):
                    next_cnt = raw_contours[i]
                    start_p = next_cnt[0]
                    dist = ((last_p['x'] - start_p['x'])**2 + (last_p['y'] - start_p['y'])**2)**0.5
                    if dist < 10:
                        current_path.extend(raw_contours.pop(i))
                        found_next = True
                        break
                if not found_next:
                    optimized_contours.append(current_path)
                    current_path = raw_contours.pop(0)
            optimized_contours.append(current_path)
        
        # G-Code 생성
        gcode = generate_gcode(optimized_contours)
        
        # 변환된 이미지를 다시 프론트엔드로 보내기 위해 base64로 인코딩
        _, buffer = cv2.imencode('.jpg', img)
        img_str = base64.b64encode(buffer).decode('utf-8')
        
        return {"width": w, "height": h, "contours": optimized_contours, "image": img_str, "gcode": gcode}
    except Exception as e:
        print(f"오류: {str(e)}")
        return {"error": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
