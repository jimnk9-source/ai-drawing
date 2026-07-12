#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <ArduinoJson.h>
#include <ESP32Servo.h>

// --- WiFi 및 서버 설정 ---
const char* ssid = "iptime_2.4GHz(1703)";
const char* password = "1305000723";
const char* vercel_url = "ai-drawing-dusky.vercel.app";

// --- 하드웨어 핀 설정 (DRV8825 및 기기 스펙 반영) ---
#define X_STEP_PIN 26
#define X_DIR_PIN  25
#define Y_STEP_PIN 14
#define Y_DIR_PIN  12
#define MOTORS_EN_PIN 27

#define X_LIMIT_PIN 33
#define Y_LIMIT_PIN 32

#define SERVO_PIN 4

// --- 펜 리프트 서보 모터 설정 ---
Servo penServo;
const int PEN_UP_ANGLE = 90;   // 펜이 종이에서 들리는 서보 각도 (물리 배치에 따라 미세조정 가능)
const int PEN_DOWN_ANGLE = 10; // 펜이 종이에 닿는 서보 각도 (물리 배치에 따라 미세조정 가능)

// --- 모터 이동 파라미터 ---
float currentX = 0.0;
float currentY = 0.0;
const float STEPS_PER_MM = 80.0; // 1mm를 움직이기 위해 필요한 모터 스텝 수 (풀리/벨트 사양)

// --- 서보 모터 펜 제어 함수 ---
void penUp() {
  penServo.write(PEN_UP_ANGLE);
  delay(300); // 서보가 움직일 물리적 시간 대기
}

void penDown() {
  penServo.write(PEN_DOWN_ANGLE);
  delay(300); // 서보가 움직일 물리적 시간 대기
}

// --- 모터 초기화 설정 ---
void setupMotors() {
  pinMode(X_STEP_PIN, OUTPUT);
  pinMode(X_DIR_PIN, OUTPUT);
  pinMode(Y_STEP_PIN, OUTPUT);
  pinMode(Y_DIR_PIN, OUTPUT);
  pinMode(MOTORS_EN_PIN, OUTPUT);
  
  // 기판형 3핀 리미트 스위치를 위한 풀업 입력 설정
  pinMode(X_LIMIT_PIN, INPUT_PULLUP);
  pinMode(Y_LIMIT_PIN, INPUT_PULLUP);

  // DRV8825 활성화 (ENABLE 핀은 LOW일 때 모터가 구동됩니다)
  digitalWrite(MOTORS_EN_PIN, LOW); 

  // 서보 모터 부착 및 초기 펜 업
  penServo.attach(SERVO_PIN);
  penUp();
}

// --- Homing (원점 복귀) 함수 ---
// 전원을 켰을 때 X축, Y축이 각각 스위치를 건드릴 때까지 반대 방향으로 이동하여 (0,0) 절대 기준점을 잡습니다.
void homing() {
  Serial.println("Homing started...");
  penUp();

  // 1. X축 홈 검색 (리미트 스위치가 눌려 LOW가 될 때까지 - 방향으로 한 스텝씩 이동)
  digitalWrite(X_DIR_PIN, LOW);
  while(digitalRead(X_LIMIT_PIN) == HIGH) {
    digitalWrite(X_STEP_PIN, HIGH);
    delayMicroseconds(1000);
    digitalWrite(X_STEP_PIN, LOW);
    delayMicroseconds(1000);
  }
  
  // 2. Y축 홈 검색 (리미트 스위치가 눌려 LOW가 될 때까지 - 방향으로 한 스텝씩 이동)
  digitalWrite(Y_DIR_PIN, LOW);
  while(digitalRead(Y_LIMIT_PIN) == HIGH) {
    digitalWrite(Y_STEP_PIN, HIGH);
    delayMicroseconds(1000);
    digitalWrite(Y_STEP_PIN, LOW);
    delayMicroseconds(1000);
  }

  // 홈 위치 지정
  currentX = 0.0;
  currentY = 0.0;
  Serial.println("Homing complete. Absolute (0,0) locked.");
}

// --- Bresenham 직선 보간 알고리즘 기반 이동 함수 ---
// X축, Y축 모터를 가속 오차를 분산하며 동시에 굴려 하나의 반듯한 사선/직선을 그리게 만듭니다.
void moveTo(float targetX, float targetY) {
  long targetStepsX = targetX * STEPS_PER_MM;
  long targetStepsY = targetY * STEPS_PER_MM;
  long currentStepsX = currentX * STEPS_PER_MM;
  long currentStepsY = currentY * STEPS_PER_MM;

  long dx = abs(targetStepsX - currentStepsX);
  long dy = abs(targetStepsY - currentStepsY);
  int sx = currentStepsX < targetStepsX ? 1 : -1;
  int sy = currentStepsY < targetStepsY ? 1 : -1;
  
  long err = dx - dy;

  // 방향 신호 설정
  digitalWrite(X_DIR_PIN, sx == 1 ? HIGH : LOW);
  digitalWrite(Y_DIR_PIN, sy == 1 ? HIGH : LOW);

  while (currentStepsX != targetStepsX || currentStepsY != targetStepsY) {
    long e2 = 2 * err;
    if (e2 > -dy) {
      err -= dy;
      currentStepsX += sx;
      digitalWrite(X_STEP_PIN, HIGH);
      delayMicroseconds(500);
      digitalWrite(X_STEP_PIN, LOW);
    }
    if (e2 < dx) {
      err += dx;
      currentStepsY += sy;
      digitalWrite(Y_STEP_PIN, HIGH);
      delayMicroseconds(500);
      digitalWrite(Y_STEP_PIN, LOW);
    }
    delayMicroseconds(1000); // 모터 물리적 최고 속도 제한(주기 대기)
  }
  
  currentX = targetX;
  currentY = targetY;
}

// --- 개별 G-Code 파싱 및 제어 매핑 ---
void processGCodeLine(String line) {
  line.trim();
  if (line.length() == 0 || line.startsWith(";")) return; // 빈 줄 및 주석 건너뜀

  // G0 (빠른 이동) 및 G1 (드로잉 이동) 파싱
  if (line.startsWith("G0") || line.startsWith("G1")) {
    float newX = currentX;
    float newY = currentY;
    
    // Z축 값으로 펜 Up/Down 판단 (Z > 0 이면 펜 올림, Z <= 0 이면 펜 내림)
    int zIndex = line.indexOf('Z');
    if (zIndex != -1) {
      float zVal = line.substring(zIndex + 1).toFloat();
      if (zVal > 0) penUp();
      else penDown();
    }
    
    // X좌표 값 파싱
    int xIndex = line.indexOf('X');
    if (xIndex != -1) newX = line.substring(xIndex + 1).toFloat();
    
    // Y좌표 값 파싱
    int yIndex = line.indexOf('Y');
    if (yIndex != -1) newY = line.substring(yIndex + 1).toFloat();

    // 입력받은 목표 좌표로 동시 보간 이동 실행
    moveTo(newX, newY);
  }
  // M3 (스핀들/레이저 ON -> 플로터에서는 펜을 도화지에 내리는 제어로 매핑)
  else if (line.startsWith("M3")) {
    penDown();
  }
  // M5 (스핀들/레이저 OFF -> 플로터에서는 펜을 도화지에서 드는 제어로 매핑)
  else if (line.startsWith("M5")) {
    penUp();
  }
}

// --- 다운로드 받은 전체 G-Code 일괄 실행 제어 루프 ---
void executeGCode(String gcode) {
  int startIndex = 0;
  int endIndex = gcode.indexOf('\n');
  
  while (endIndex != -1) {
    String line = gcode.substring(startIndex, endIndex);
    processGCodeLine(line);
    startIndex = endIndex + 1;
    endIndex = gcode.indexOf('\n', startIndex);
  }
  // 개행이 없는 마지막 잔여 한 줄 처리
  if (startIndex < gcode.length()) {
    processGCodeLine(gcode.substring(startIndex));
  }
  
  // 한 도화지 드로잉 태스크가 모두 끝나면 서보 펜을 들어 올립니다.
  penUp();
}

// --- ESP32 구동 최초 1회 셋업 루프 ---
void setup() {
  Serial.begin(115200);
  
  // 모터 및 서보, 센서 상태 초기 상태화
  setupMotors();
  delay(1000);
  
  // 구동 시작 시 오차 없이 스위치를 쳐서 절대 원점 교정
  homing(); 

  // WiFi 통신 감지 및 연결 시도
  WiFi.begin(ssid, password);
  Serial.print("Connecting WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected successfully!");
}

// --- ESP32 상시 대기 루프 ---
void loop() {
  if (WiFi.status() == WL_CONNECTED) {
    WiFiClientSecure client;
    client.setInsecure(); // Vercel의 SSL 인증서 보안 검증 우회 허용
    HTTPClient http;

    String full_url = "https://" + String(vercel_url) + "/api/get-task";
    
    if (http.begin(client, full_url)) {
      int httpResponseCode = http.GET();

      if (httpResponseCode == 200) {
        String payload = http.getString();
        
        // Vercel 서버로부터 드로잉 데이터(JSON) 분석
        DynamicJsonDocument doc(16384); 
        DeserializationError error = deserializeJson(doc, payload);

        if (!error) {
          int task_id = doc["task_id"];
          
          // 신규 대기 중인 그리기 임무(task_id가 0이 아닐 때)가 확인된 경우
          if (task_id != 0) {
            Serial.println("--- New Drawing Task Received ---");
            String gcodeStr = doc["gcode"].as<String>();
            
            Serial.println("Executing G-Code Drawing...");
            executeGCode(gcodeStr); // 실시간 그리기 가동!
            Serial.println("Drawing Complete!");
            
            // 완료 후 디폴트 가공 대기 위치인 (0.0, 0.0) 원점으로 되돌아오기
            moveTo(0.0, 0.0); 
          }
        } else {
          Serial.print("JSON Parsing failed: ");
          Serial.println(error.c_str());
        }
      } else if (httpResponseCode > 0 && httpResponseCode != 204) {
        Serial.print("HTTP Error: ");
        Serial.println(httpResponseCode);
      }
      http.end();
    }
  }
  delay(5000); // 5초 대기 간격으로 Vercel 신규 드로잉 타스크를 풀링 검사
}
