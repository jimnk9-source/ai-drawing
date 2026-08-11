#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <ArduinoJson.h>
#include <ESP32Servo.h>

// --- 하드웨어 핀 설정 (DRV8825 및 기기 스펙 반영) ---
#define X_STEP_PIN 26
#define X_DIR_PIN  25
#define Y_STEP_PIN 14
#define Y_DIR_PIN  12
#define MOTORS_EN_PIN 27

#define X_LIMIT_PIN 33
#define Y_LIMIT_PIN 32

#define SERVO_PIN 4

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
}

void setup() {
  Serial.begin(115200);
  Serial.println("Motor Test Start - Continuous Rotation Mode");

  // 모터 초기화
  setupMotors();
  delay(1000);
}

void loop() {
  // 모터 회전 한 방향 고정
  digitalWrite(X_DIR_PIN, HIGH);
  digitalWrite(Y_DIR_PIN, HIGH);

  // X축 및 Y축 모터에 펄스를 인가하여 한 동작 스텝 진행
  digitalWrite(X_STEP_PIN, HIGH);
  digitalWrite(Y_STEP_PIN, HIGH);
  delayMicroseconds(800); // 펄스 폭 유지
  digitalWrite(X_STEP_PIN, LOW);
  digitalWrite(Y_STEP_PIN, LOW);
  delayMicroseconds(800); // 다음 펄스 전 대기 (모터 속도 결정)
}
