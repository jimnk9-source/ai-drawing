import os
import google.generativeai as genai
from dotenv import load_dotenv
import base64
import cv2
import numpy as np

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=api_key)

model = genai.GenerativeModel('gemini-2.0-flash-lite')

# 테스트용 더미 이미지 생성 (검은색 사각형)
img = np.zeros((100, 100, 3), dtype=np.uint8)
cv2.rectangle(img, (20, 20), (80, 80), (255, 255, 255), -1)
_, encoded_img = cv2.imencode('.jpg', img)
base64_image = base64.b64encode(encoded_img).decode('utf-8')

prompt = "Convert this image into a clean, black and white line art sketch on a white background. Return the result strictly as a base64 encoded string only, without any surrounding text."
response = model.generate_content([prompt, {"mime_type": "image/jpeg", "data": base64_image}])

print("--- Gemini API 응답 내용 ---")
print(response.text)
