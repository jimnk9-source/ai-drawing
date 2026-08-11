// ============================================================
//  Vico Plotter - 완전 통합 펌웨어 v3.0
//  (LCD 제거, LED 4색 상태표시 + WiFi 연결 개선)
//
//  [주요 기능]
//  1. Wi-Fi 연결 (타임아웃 + 재시도 + 절전모드 OFF)
//  2. Homing(원점 복귀) - 리미트 스위치로 절대 원점 교정
//  3. Bresenham 직선 보간 알고리즘으로 정밀 2축 동시 이동
//  4. 서보 모터로 펜 UP/DOWN 제어
//  5. 대기 중 모터 전류 완전 차단(발열 없음)
//  6. G0/G1/M3/M5 G-Code 명령 파싱 및 실행
//  7. LED 4색 상태 표시
//     - 빨강: WiFi 연결 대기중
//     - 노랑: 작업(G-code) 대기중
//     - 초록: 출력(드로잉) 중
//     - 파랑: 완료
// ============================================================

#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <ArduinoJson.h>
#include <ESP32Servo.h>

// ============================================================
//  [설정 1] Wi-Fi 및 서버 정보
// ============================================================
const char* WIFI_SSID     = "iptime_2.4GHz(1703)";
const char* WIFI_PASSWORD = "1305000723";
const char* VERCEL_HOST   = "ai-drawing-dusky.vercel.app";

const unsigned long WIFI_TIMEOUT_MS = 30000; // 15초 동안 연결 안되면 재시도

// ============================================================
//  [설정 2] 핀 번호 (motor_test.ino 기존 배선 유지)
// ============================================================
#define X_STEP_PIN    12
#define X_DIR_PIN     14
#define Y_STEP_PIN    25
#define Y_DIR_PIN     26
#define MOTORS_EN_PIN 27   // LOW=활성, HIGH=비활성(전류차단)

#define X_LIMIT_PIN   33   // X축 리미트 스위치 (C-NO, 내부 풀업)
#define Y_LIMIT_PIN   32   // Y축 리미트 스위치 (C-NO, 내부 풀업)

#define SERVO_PIN     4    // 펜 리프트 서보 시그널

// ============================================================
//  [설정 2-1] LED 상태표시 핀 (LCD 대체)
// ============================================================
#define LED_RED_PIN     21   // WiFi 연결 대기
#define LED_YELLOW_PIN  22   // 작업(G-code) 대기
#define LED_GREEN_PIN   5    // 출력(드로잉) 중
#define LED_BLUE_PIN    18   // 완료

enum PlotterState {
  STATE_WIFI_WAITING,
  STATE_CODE_WAITING,
  STATE_PRINTING,
  STATE_COMPLETE
};

// ============================================================
//  [설정 3] 서보 각도 - 물리 조립에 맞게 미세 조정하세요
// ============================================================
const int PEN_UP_ANGLE   = 90;  // 펜이 종이에서 들리는 각도
const int PEN_DOWN_ANGLE = 10;  // 펜이 종이에 닿는 각도

// ============================================================
//  [설정 4] 모터 속도 파라미터
// ============================================================
const float STEPS_PER_MM = 5.0;
const int STEP_DELAY_US  = 800;
const int HOME_DELAY_US  = 1500;

// ============================================================
//  [설정 6] Y축 최대 이동 제한 (세로 방향 10바퀴)
// ============================================================
const int   STEPS_PER_REVOLUTION = 200;
const float MAX_Y_ROTATIONS      = 10.0;
const float MAX_Y_MM = (STEPS_PER_REVOLUTION * MAX_Y_ROTATIONS) / STEPS_PER_MM;

// ============================================================
//  [설정 5] 서버 폴링 주기
// ============================================================
const int POLL_INTERVAL_MS = 5000; // 5초마다 서버 확인

// ============================================================
//  전역 변수 - 현재 위치 추적 (mm 단위)
// ============================================================
float currentX = 0.0;
float currentY = 0.0;

Servo penServo;

// ============================================================
//  [함수] setLedState(state)
//  - 4개 LED 중 현재 상태에 맞는 LED 1개만 켜고 나머지는 끔
// ============================================================
void setLedState(PlotterState state) {
  digitalWrite(LED_RED_PIN,    LOW);
  digitalWrite(LED_YELLOW_PIN, LOW);
  digitalWrite(LED_GREEN_PIN,  LOW);
  digitalWrite(LED_BLUE_PIN,   LOW);

  switch (state) {
    case STATE_WIFI_WAITING: digitalWrite(LED_RED_PIN,    HIGH); break;
    case STATE_CODE_WAITING: digitalWrite(LED_YELLOW_PIN, HIGH); break;
    case STATE_PRINTING:     digitalWrite(LED_GREEN_PIN,  HIGH); break;
    case STATE_COMPLETE:     digitalWrite(LED_BLUE_PIN,   HIGH); break;
  }
}

// ============================================================
//  [함수] 모터 전원 제어
// ============================================================
void enableMotors() {
  digitalWrite(MOTORS_EN_PIN, LOW);
}

void disableMotors() {
  digitalWrite(MOTORS_EN_PIN, HIGH);
}

// ============================================================
//  [함수] 서보 제어 - 펜 올리기 / 내리기
// ============================================================
void penUp() {
  penServo.write(PEN_UP_ANGLE);
  delay(300);
}

void penDown() {
  penServo.write(PEN_DOWN_ANGLE);
  delay(300);
}

// ============================================================
//  [함수] 하드웨어 초기화
// ============================================================
void setupMotors() {
  pinMode(X_STEP_PIN,    OUTPUT);
  pinMode(X_DIR_PIN,     OUTPUT);
  pinMode(Y_STEP_PIN,    OUTPUT);
  pinMode(Y_DIR_PIN,     OUTPUT);
  pinMode(MOTORS_EN_PIN, OUTPUT);

  pinMode(X_LIMIT_PIN, INPUT_PULLUP);
  pinMode(Y_LIMIT_PIN, INPUT_PULLUP);

  disableMotors();

  penServo.attach(SERVO_PIN);
  penUp();
}

void setupLeds() {
  pinMode(LED_RED_PIN,    OUTPUT);
  pinMode(LED_YELLOW_PIN, OUTPUT);
  pinMode(LED_GREEN_PIN,  OUTPUT);
  pinMode(LED_BLUE_PIN,   OUTPUT);

  digitalWrite(LED_RED_PIN,    LOW);
  digitalWrite(LED_YELLOW_PIN, LOW);
  digitalWrite(LED_GREEN_PIN,  LOW);
  digitalWrite(LED_BLUE_PIN,   LOW);
}

// ============================================================
//  [함수] connectWiFi()
//  - 절전모드 OFF, 이전 연결정보 초기화
//  - 타임아웃(15초) 발생 시 자동 재시도
//  - 연결 대기 중 LED 빨강 유지
// ============================================================
void connectWiFi() {
  setLedState(STATE_WIFI_WAITING);

  WiFi.mode(WIFI_STA);
  WiFi.disconnect(true);
  delay(100);
  WiFi.setSleep(false); // 절전모드 끄기 → 연결 속도/안정성 개선

  Serial.print("[WiFi] 연결 중: ");
  Serial.println(WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  unsigned long wifiStart = millis();

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");

    if (millis() - wifiStart > WIFI_TIMEOUT_MS) {
      Serial.println("\n[WiFi] 연결 실패 - 재시도합니다");
      WiFi.disconnect(true);
      delay(500);
      WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
      wifiStart = millis();
    }
  }

  Serial.println();
  Serial.print("[WiFi] 연결 완료! IP: ");
  Serial.println(WiFi.localIP());
}

// ============================================================
//  [함수] Homing (원점 복귀)
// ============================================================
void homing() {
  Serial.println("[Homing] 원점 복귀 시작...");
  penUp();
  enableMotors();
  delay(100);

  Serial.println("[Homing] X축 스위치 탐색 중...");
  digitalWrite(X_DIR_PIN, LOW);
  while (digitalRead(X_LIMIT_PIN) == HIGH) {
    digitalWrite(X_STEP_PIN, HIGH);
    delayMicroseconds(HOME_DELAY_US);
    digitalWrite(X_STEP_PIN, LOW);
    delayMicroseconds(HOME_DELAY_US);
  }
  Serial.println("[Homing] X축 원점 도달!");

  Serial.println("[Homing] Y축 스위치 탐색 중...");
  digitalWrite(Y_DIR_PIN, LOW);
  while (digitalRead(Y_LIMIT_PIN) == HIGH) {
    digitalWrite(Y_STEP_PIN, HIGH);
    delayMicroseconds(HOME_DELAY_US);
    digitalWrite(Y_STEP_PIN, LOW);
    delayMicroseconds(HOME_DELAY_US);
  }
  Serial.println("[Homing] Y축 원점 도달!");

  currentX = 0.0;
  currentY = 0.0;
  Serial.println("[Homing] 완료! 절대 원점 (0, 0) 확정.");
}

// ============================================================
//  [함수] moveTo(targetX, targetY)
// ============================================================
void moveTo(float targetX, float targetY) {
  if (targetY > MAX_Y_MM) {
    Serial.print("[경고] Y 목표 초과! ");
    Serial.print(targetY);
    Serial.print("mm → ");
    Serial.print(MAX_Y_MM);
    Serial.println("mm 로 제한됨");
    targetY = MAX_Y_MM;
  }
  if (targetY < 0) targetY = 0;

  long tStepsX = (long)(targetX * STEPS_PER_MM);
  long tStepsY = (long)(targetY * STEPS_PER_MM);
  long cStepsX = (long)(currentX * STEPS_PER_MM);
  long cStepsY = (long)(currentY * STEPS_PER_MM);

  long dx = abs(tStepsX - cStepsX);
  long dy = abs(tStepsY - cStepsY);

  if (dx == 0 && dy == 0) return;

  int sx = (cStepsX < tStepsX) ? 1 : -1;
  int sy = (cStepsY < tStepsY) ? 1 : -1;
  long err = dx - dy;

  digitalWrite(X_DIR_PIN, (sx == 1) ? HIGH : LOW);
  digitalWrite(Y_DIR_PIN, (sy == 1) ? HIGH : LOW);

  enableMotors();

  while (cStepsX != tStepsX || cStepsY != tStepsY) {
    long e2 = 2 * err;

    if (e2 > -dy && cStepsX != tStepsX) {
      err -= dy;
      cStepsX += sx;
      digitalWrite(X_STEP_PIN, HIGH);
      delayMicroseconds(STEP_DELAY_US);
      digitalWrite(X_STEP_PIN, LOW);
    }

    if (e2 < dx && cStepsY != tStepsY) {
      err += dx;
      cStepsY += sy;
      digitalWrite(Y_STEP_PIN, HIGH);
      delayMicroseconds(STEP_DELAY_US);
      digitalWrite(Y_STEP_PIN, LOW);
    }

    delayMicroseconds(STEP_DELAY_US);
  }

  disableMotors();

  currentX = targetX;
  currentY = targetY;
}

// ============================================================
//  [함수] processGCodeLine(line)
// ============================================================
void processGCodeLine(String line) {
  line.trim();
  if (line.length() == 0 || line.startsWith(";")) return;

  if (line.startsWith("G0") || line.startsWith("G1")) {
    float newX = currentX;
    float newY = currentY;

    int zIdx = line.indexOf('Z');
    if (zIdx != -1) {
      String zStr = "";
      for (int i = zIdx + 1; i < (int)line.length(); i++) {
        char c = line.charAt(i);
        if (c == ' ' || (c != '.' && c != '-' && !isDigit(c))) break;
        zStr += c;
      }
      float zVal = zStr.toFloat();
      if (zVal > 0) penUp();
      else          penDown();
    }

    int xIdx = line.indexOf('X');
    if (xIdx != -1) {
      String xStr = "";
      for (int i = xIdx + 1; i < (int)line.length(); i++) {
        char c = line.charAt(i);
        if (c == ' ' || (c != '.' && c != '-' && !isDigit(c))) break;
        xStr += c;
      }
      newX = xStr.toFloat();
    }

    int yIdx = line.indexOf('Y');
    if (yIdx != -1) {
      String yStr = "";
      for (int i = yIdx + 1; i < (int)line.length(); i++) {
        char c = line.charAt(i);
        if (c == ' ' || (c != '.' && c != '-' && !isDigit(c))) break;
        yStr += c;
      }
      newY = yStr.toFloat();
    }

    moveTo(newX, newY);
  }

  else if (line.startsWith("M3")) {
    int sIdx = line.indexOf('S');
    if (sIdx != -1) {
      float sVal = line.substring(sIdx + 1).toFloat();
      if (sVal > 15) penUp();
      else           penDown();
    } else {
      penDown();
    }
  }

  else if (line.startsWith("M5")) {
    penUp();
  }
}

// ============================================================
//  [함수] executeGCode(gcode)
//  - 실행 중 LED 초록 유지, 완료 후 LED 파랑
// ============================================================
void executeGCode(const String& gcode) {
  setLedState(STATE_PRINTING);

  int startIdx  = 0;
  int endIdx    = gcode.indexOf('\n');

  while (endIdx != -1) {
    String line = gcode.substring(startIdx, endIdx);
    processGCodeLine(line);
    startIdx = endIdx + 1;
    endIdx   = gcode.indexOf('\n', startIdx);
  }

  if (startIdx < (int)gcode.length()) {
    processGCodeLine(gcode.substring(startIdx));
  }

  penUp();
  Serial.println("Drawing Complete! Returning to origin...");
  moveTo(0.0, 0.0);

  setLedState(STATE_COMPLETE);
  delay(2000); // 완료 표시(파랑) 2초 유지 후 다시 대기 상태로
}

// ============================================================
//  [함수] sendTaskComplete(task_id)
//  - 드로잉을 완료했음을 백엔드 서버에 통지
// ============================================================
void sendTaskComplete(int task_id) {
  WiFiClientSecure client;
  client.setInsecure();

  HTTPClient http;
  String url = "https://" + String(VERCEL_HOST) + "/api/complete-task?task_id=" + String(task_id);

  if (http.begin(client, url)) {
    int code = http.POST(""); // POST
    if (code == 200) {
      Serial.print("[HTTP] Task 완료 보고 성공! ID: ");
      Serial.println(task_id);
    } else {
      Serial.print("[HTTP] Task 완료 보고 실패, 코드: ");
      Serial.println(code);
    }
    http.end();
  }
}

// ============================================================
//  [함수] fetchAndRun()
// ============================================================
void fetchAndRun() {
  WiFiClientSecure client;
  client.setInsecure();

  HTTPClient http;
  String url = "https://" + String(VERCEL_HOST) + "/api/get-task";

  if (!http.begin(client, url)) {
    Serial.println("[HTTP] 연결 실패");
    return;
  }

  int code = http.GET();

  if (code == 200) {
    String payload = http.getString();
    Serial.print("[HTTP] 수신 완료, 길이: ");
    Serial.println(payload.length());

    DynamicJsonDocument doc(16384);
    DeserializationError err = deserializeJson(doc, payload);

    if (err) {
      Serial.print("[JSON] 파싱 실패: ");
      Serial.println(err.c_str());
    } else {
      int task_id = doc["task_id"] | 0;

      if (task_id != 0) {
        Serial.print("[Task] 새 작업 수신! ID: ");
        Serial.println(task_id);

        const char* gcode = doc["gcode"] | "";
        String gcodeStr   = String(gcode);

        Serial.println("--- G-Code Preview (100 chars) ---");
        Serial.println(gcodeStr.substring(0, min((int)gcodeStr.length(), 100)));
        Serial.println("----------------------------------");

        Serial.println("[Task] G-Code 실행 시작...");
        executeGCode(gcodeStr);
        Serial.println("[Task] 완료!");

        // 백엔드 상태를 complete(완료)로 업데이트
        sendTaskComplete(task_id);

        setLedState(STATE_CODE_WAITING); // 완료 표시 후 다시 대기상태로 복귀
      } else {
        Serial.println("[Task] 대기 중... (task_id = 0)");
        setLedState(STATE_CODE_WAITING);
      }
    }
  } else if (code == 204) {
    setLedState(STATE_CODE_WAITING);
  } else if (code > 0) {
    Serial.print("[HTTP] 오류 코드: ");
    Serial.println(code);
  } else {
    Serial.print("[HTTP] 요청 실패, 에러: ");
    Serial.println(http.errorToString(code));
  }

  http.end();
}

// ============================================================
//  setup()
// ============================================================
void setup() {
  Serial.begin(115200);
  delay(500);

  Serial.println("========================================");
  Serial.println("  Vico Plotter Firmware v3.0 시작");
  Serial.println("========================================");

  setupLeds();
  setupMotors();
  delay(500);

  // WiFi를 먼저 연결 (빨강 LED 유지) → homing 시간과 분리해서 확인 가능
  connectWiFi();

  // WiFi 연결 후 homing 진행
  homing();

  setLedState(STATE_CODE_WAITING); // 이제부터 작업 대기 상태 (노랑)

  Serial.println("========================================");
  Serial.println("  서버 폴링 시작...");
  Serial.println("========================================");
}

// ============================================================
//  loop()
// ============================================================
void loop() {
  if (WiFi.status() == WL_CONNECTED) {
    fetchAndRun();
  } else {
    Serial.println("[WiFi] 연결 끊어짐. 재연결 시도 중...");
    setLedState(STATE_WIFI_WAITING);
    connectWiFi();
    setLedState(STATE_CODE_WAITING);
  }

  delay(POLL_INTERVAL_MS);
}