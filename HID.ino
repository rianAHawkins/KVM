#include <WiFi.h>
#include <WebSocketsServer.h>
#include "USB.h"
#include "USBHIDKeyboard.h"
#include "USBHIDMouse.h"

const char* ssid = "WHITE25";
const char* password = "AKIRA123";

WebSocketsServer webSocket(81);

USBHIDKeyboard Keyboard;
USBHIDMouse Mouse;

void handleMessage(uint8_t num, uint8_t* payload, size_t length) {
  String msg = String((char*)payload);

  // Keyboard type text: TEXT:hello world
  if (msg.startsWith("TEXT:")) {
    Keyboard.print(msg.substring(5));
    return;
  }

  // Single key press: KEY:a or KEY:ENTER
  if (msg.startsWith("KEY:")) {
    String key = msg.substring(4);
    
    // Parse modifiers
    bool hasCtrl = false;
    bool hasShift = false;
    bool hasAlt = false;
    
    while (key.indexOf("+") > 0) {
        int plusPos = key.indexOf("+");
        String modifier = key.substring(0, plusPos);
        key = key.substring(plusPos + 1);
        
        if (modifier == "CTRL") hasCtrl = true;
        else if (modifier == "SHIFT") hasShift = true;
        else if (modifier == "ALT") hasAlt = true;
    }
    
    // Press modifiers first
    if (hasCtrl) Keyboard.press(KEY_LEFT_CTRL);
    if (hasShift) Keyboard.press(KEY_LEFT_SHIFT);
    if (hasAlt) Keyboard.press(KEY_LEFT_ALT);
    
    // Press the main key
    if (key.startsWith("0x")) {
        // Parse hex string to integer
        long hexValue = strtol(key.c_str(), NULL, 16);
        Keyboard.press(hexValue);
    }
    else if (key.length() == 1) {
        Keyboard.press(key[0]);
    }
    
    // Release all keys
    Keyboard.releaseAll();
    return;
  }

  // Mouse move: MOVE:dx:dy
  if (msg.startsWith("MOVE:")) {
    int first = msg.indexOf(':', 5);
    int dx = msg.substring(5, first).toInt();
    int dy = msg.substring(first+1).toInt();
    Mouse.move(dx, dy);
    return;
  }

  // Mouse click: CLICK:LEFT or CLICK:RIGHT
  if (msg.startsWith("CLICK:")) {
    String btn = msg.substring(6);
    if (btn == "LEFT") Mouse.click(MOUSE_LEFT);
    if (btn == "RIGHT") Mouse.click(MOUSE_RIGHT);
    return;
  }

  // Mouse scroll: SCROLL:steps
  if (msg.startsWith("SCROLL:")) {
    int steps = msg.substring(7).toInt();
    Mouse.move(0, 0, steps);
    return;
  }
}

void onWsEvent(
    uint8_t num, WStype_t type,
    uint8_t * payload, size_t length) {
  if (type == WStype_TEXT) {
    handleMessage(num, payload, length);
  }
}

void setup() {
  Serial.begin(115200);

  delay(3000);

  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(200);
    Serial.print(".");
  }

  Serial.println("\nConnected!");
  Serial.print("IP: ");
  Serial.println(WiFi.localIP());   // ✅ prints IP

  delay(3000);
  USB.begin();
  Keyboard.begin();
  Mouse.begin();

  webSocket.begin();
  webSocket.onEvent(onWsEvent);

  delay(2000);

  Keyboard.print(WiFi.localIP().toString());
}

void loop() {
  webSocket.loop();
}
