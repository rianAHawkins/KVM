# KVM

# ESP32-S3 HID Forwarder  
Forward keyboard and mouse input from **PC1** to **PC2** using Wi-Fi + USB HID.

- PC1 runs a Python script that captures local keyboard/mouse events
- Events are sent over a WebSocket to the ESP32-S3
- The ESP32-S3 emulates a USB HID keyboard and mouse on PC2

---

## ✅ System Diagram

```text
┌──────────┐          WebSocket           ┌──────────────┐      USB HID       ┌──────────┐
│   PC1    │ ───────────────────────────► │  ESP32-S3     │ ───────────────►  │   PC2     │
│ (Linux)  │                              │ (Wi-Fi + HID) │                   │ (Target)  │
└──────────┘                              └──────────────┘                    └──────────┘

            [Capture Input]                      [Parse]                         [Acts like]
       Keyboard + Mouse Events   ───►    Receive Commands   ───►       Keyboard + Mouse Device
       (evdev Python script)           (WebSocket Server)               (Type & Move Cursor)

