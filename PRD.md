# PRD: Vico - Ai drawing

## 1. 프로젝트 개요
사용자가 웹사이트에 이미지를 업로드하면, AI가 해당 이미지의 외곽선을 분석하고 추출하여 ESP32로 제어되는 X-Y 플로터가 종이 위에 그림을 자동으로 그려주는 프로젝트입니다.

## 2. 프로젝트 목적
- 복잡한 이미지를 단순화하여 아날로그 방식(볼펜)으로 재현하는 재미 제공
- ESP32의 무선 통신 기능을 활용한 편리한 데이터 전송 경험 구현
- 3D 프린터의 X, Y축 메커니즘을 이해하고 응용하는 하드웨어 프로젝트

## 3. 핵심 기능
- **이미지 업로드 웹사이트**: 사용자가 이미지를 업로드하고 드로잉 상태를 확인하는 인터페이스.
- **AI 이미지 분석 (외곽선 추출)**: Python(OpenCV)을 사용하여 외곽선을 추출하고, 이를 G-Code 형태의 좌표 데이터로 변환.
- **ESP32 무선 제어**: Wi-Fi를 통해 서버로부터 좌표 데이터를 수신하여 무선으로 코드 업로드/실행.
- **X-Y 플로터 제어**: ESP32가 스테퍼 모터와 서보 모터(펜 리프트)를 제어하여 3D 프린터 방식으로 그림 출력 (Z축 제외).

## 4. 기술 스택
### Software
- **Frontend**: React.js (사용자 인터페이스)
- **Backend**: Python / FastAPI (이미지 처리 및 API 서버)
- **AI/Image Processing**: OpenCV (Canny Edge Detection, Vectorization)
- **Firmware**: ESP32 (Arduino framework, G-Code Parsing)

### Hardware
- **MCU**: ESP32
- **모터**: Stepper Motors (X, Y축), Servo Motor (펜 리프트)
- **드라이버**: A4988 스테퍼 모터 드라이버
- **통신**: Wi-Fi (WebSocket 또는 HTTP)

## 5. 시스템 아키텍처
1. **사용자**: 웹사이트 접속 및 이미지 업로드
2. **Backend**: 이미지 분석 -> 외곽선 추출 -> G-Code(좌표 데이터) 생성
3. **Communication**: Wi-Fi를 통해 ESP32에 G-Code 전송
4. **Hardware**: ESP32가 모터 드라이버를 통해 X-Y 축 구동 및 펜 리프트 제어

## 6. 향후 로드맵
- Phase 1: 기본 외곽선 추출 알고리즘 및 ESP32 모터 제어 기초 구현
- Phase 2: 웹 서버 구축 및 무선 데이터 전송 연동
- Phase 3: 하드웨어 프레임 조립 및 전체 시스템 통합 테스트
