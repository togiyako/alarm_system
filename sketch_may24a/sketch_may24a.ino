#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>

#include <Crypto.h>
#include <ChaCha.h>         // rweather's ChaCha20 implementation
#include <Base64.h>         // rweather's Base64 encoder

// === Wi-Fi & Server ===
const char* ssid = "707";
const char* password = "Krupchuk77";
const char* serverURL = "http://10.10.10.101:5001/notify";

// === Sensors & Actuators ===
const int pirPin = 26;
const int ledPin = 25;
const int gasSensorPin = 13;
const int buzzerPin = 33;

// === ChaCha20 Parameters ===
const byte chachaKey[32] = {
  0x00,0x01,0x02,0x03,0x04,0x05,0x06,0x07,
  0x08,0x09,0x0A,0x0B,0x0C,0x0D,0x0E,0x0F,
  0x10,0x11,0x12,0x13,0x14,0x15,0x16,0x17,
  0x18,0x19,0x1A,0x1B,0x1C,0x1D,0x1E,0x1F
};
byte chachaNonce[12];  // 12-byte nonce: 8 random + 4 counter
uint32_t chachaCounter = 0;

// === State ===
int pirState = LOW;
bool gasState = LOW;

// === Melody ===
#include <pitches.h>
int melody[] = {
  NOTE_E4, NOTE_B3, NOTE_E4, NOTE_B3
};

int noteDurations[] = {
  2, 2, 2, 2
};

// === Function Prototypes ===
void setupWiFi();
void sendEncryptedNotification(const String& type, bool state);
void encryptChaCha(const byte* plaintext, byte* cipher, size_t length);
uint64_t getRandom64();
void playMelody();

void setup() {
  Serial.begin(115200);
  pinMode(pirPin, INPUT);
  pinMode(ledPin, OUTPUT);
  pinMode(gasSensorPin, INPUT);
  pinMode(buzzerPin, OUTPUT);
  setupWiFi();
}

void loop() {
  int motionVal = digitalRead(pirPin);
  if (motionVal == HIGH && pirState == LOW) {
    digitalWrite(ledPin, HIGH);
    Serial.println("⚠️ Motion detected!");
    sendEncryptedNotification("motion", true);
    pirState = HIGH;
  } else if (motionVal == LOW && pirState == HIGH) {
    digitalWrite(ledPin, LOW);
    Serial.println("✅ Motion stopped.");
    pirState = LOW;
  }

  int currentGasVal = digitalRead(gasSensorPin);
  if (currentGasVal != gasState) {
    gasState = currentGasVal;
    if (gasState == HIGH) {
      Serial.println("🔥 Flame detected");
      sendEncryptedNotification("gas", true);
      playMelody();
    } else {
      Serial.println("✅ Flame gone");
    }
  }

  delay(200);
}

void setupWiFi() {
  WiFi.begin(ssid, password);
  Serial.print("Connecting to Wi-Fi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected");
  Serial.println(WiFi.localIP());
}

void sendEncryptedNotification(const String& type, bool state) {
  if (WiFi.status() != WL_CONNECTED) return;
  String json = "{\"" + type + "\": " + (state ? "true" : "false") + "}";
  size_t msgLen = json.length();
  byte plaintext[msgLen];
  memcpy(plaintext, json.c_str(), msgLen);

  uint64_t rnd = getRandom64();
  memcpy(chachaNonce, &rnd, 8);
  memcpy(chachaNonce + 8, &chachaCounter, 4);
  chachaCounter++;

  byte cipher[msgLen];
  encryptChaCha(plaintext, cipher, msgLen);

  String b64nonce = base64::encode(chachaNonce, sizeof(chachaNonce));
  String b64data  = base64::encode(cipher, msgLen);

  String payload = "{\"nonce\":\"" + b64nonce + "\",\"data\":\"" + b64data + "\"}";

  HTTPClient http;
  http.begin(serverURL);
  http.addHeader("Content-Type", "application/json");
  int code = http.POST(payload);
  if (code > 0) {
    Serial.printf("📨 %s response: %d\n", type.c_str(), code);
  } else {
    Serial.printf("❌ %s error: %s\n", type.c_str(), http.errorToString(code).c_str());
  }
  http.end();
}

void encryptChaCha(const byte* plaintext, byte* cipher, size_t length) {
  ChaCha chacha;
  chacha.clear();
  chacha.setKey(chachaKey, sizeof(chachaKey));
  chacha.setIV(chachaNonce, sizeof(chachaNonce));
  chacha.encrypt(cipher, plaintext, length);
}

uint64_t getRandom64() {
  uint64_t r = 0;
  for (int i = 0; i < 8; ++i) r = (r << 8) | (esp_random() & 0xFF);
  return r;
}

void playMelody() {
  for (int i = 0; i < 8; ++i) {
    int duration = 1000 / noteDurations[i];
    tone(buzzerPin, melody[i], duration);
    delay(duration * 1.30);
    noTone(buzzerPin);
  }
}