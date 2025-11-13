import time
import threading
from websocket import WebSocketApp
from pynput import keyboard, mouse

ESP_IP = "ws://192.168.0.139:81"

ws_app = None
connected = False
running = True

FORWARDING = False
canFORWARD = False

mouse_listener = None #keyboard.Listener()
key_listener = None #mouse.Listener()

shift_pressed = False
ctrl_pressed = False
alt_pressed = False

# Track previous mouse position for relative movement
last_mouse_pos = None


def log_status(msg, level="INFO"):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [{level}] {msg}")


# ---------------------------------------------------------
#  WebSocket Handling
# ---------------------------------------------------------

def on_open(ws):
    global connected
    connected = True
    log_status(f"✓ Connected to {ESP_IP}", "SUCCESS")


def on_close(ws, code, msg):
    global connected
    connected = False
    log_status("Connection closed", "ERROR")


def on_error(ws, error):
    global connected
    connected = False
    log_status(f"WebSocket error: {error}", "ERROR")


def start_websocket():
    global ws_app
    ws_app = WebSocketApp(
        ESP_IP,
        on_open=on_open,
        on_close=on_close,
        on_error=on_error
    )
    ws_app.run_forever()


def connect_thread():
    t = threading.Thread(target=start_websocket, daemon=True)
    t.start()


def send_message(msg):
    if not connected:
        return False
    try:
        ws_app.send(msg)
        return True
    except Exception as e:
        log_status(f"Send failed: {e}", "ERROR")
        return False


# ---------------------------------------------------------
#  Input Handling
# ---------------------------------------------------------

def toggle_forwarding():
    """Enable or disable forwarding, blocking local input when active"""
    global FORWARDING, mouse_listener,key_listener
    FORWARDING = not FORWARDING
    state = "ENABLED" if FORWARDING else "DISABLED"
    mouse.Listener.suppress=FORWARDING
    keyboard.Listener.suppress=FORWARDING
    log_status(f"Forwarding {state}", "INFO")


def on_key_press(key):
    """Handle keyboard input"""
    global shift_pressed, ctrl_pressed, alt_pressed, canFORWARD

    # Handle toggle with `
    if str(key) == "'`'":
        toggle_forwarding()
        return

    # Track modifiers
    if key in (keyboard.Key.shift, keyboard.Key.shift_r):
        shift_pressed = True
    if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_r):
        ctrl_pressed = True
    if key in (keyboard.Key.alt, keyboard.Key.alt_r):
        alt_pressed = True

    log_status(f"Key Press: {key} | Forwarding: {FORWARDING} | Connected: {connected}", "DEBUG")

    if not FORWARDING or not connected:
        return

    # Build modifier prefix
    mod_prefix = ""
    if ctrl_pressed: mod_prefix += "CTRL+"
    if shift_pressed: mod_prefix += "SHIFT+"
    if alt_pressed: mod_prefix += "ALT+"

    try:
        # Regular characters
        if hasattr(key, "char") and key.char:
            msg = f"KEY:{mod_prefix}{key.char}"
            send_message(msg)
            log_status(f"Sent: {msg}", "SEND")
        else:
            # Special keys
            special = {
                keyboard.Key.enter: "0xB0",
                keyboard.Key.backspace: "0xB2",
                keyboard.Key.tab: "0xB3",
                keyboard.Key.esc: "0xB1",
                keyboard.Key.space: " "
            }
            if key in special:
                msg = f"KEY:{mod_prefix}{special[key]}"
                send_message(msg)
                log_status(f"Sent: {msg}", "SEND")
    except Exception as e:
        log_status(f"Key handling error: {e}", "ERROR")


def on_key_release(key):
    """Track modifier release"""
    global shift_pressed, ctrl_pressed, alt_pressed
    if key in (keyboard.Key.shift, keyboard.Key.shift_r):
        shift_pressed = False
    if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_r):
        ctrl_pressed = False
    if key in (keyboard.Key.alt, keyboard.Key.alt_r):
        alt_pressed = False

last_move_time = 0
MOVE_INTERVAL = 0.016  # ≈60 Hz (16 ms)

def on_mouse_move(x, y):
    """Handle relative mouse movement with rate limiting and debug logs"""
    global last_mouse_pos, last_move_time

    if not FORWARDING or not connected:
        last_mouse_pos = (x, y)
        return

    if last_mouse_pos is None:
        last_mouse_pos = (x, y)
        return

    now = time.time()
    if now - last_move_time < MOVE_INTERVAL:
        return  # skip too-frequent updates

    dx = x - last_mouse_pos[0]
    dy = y - last_mouse_pos[1]

    if dx == 0 and dy == 0:
        return

    msg = f"MOVE:{dx}:{dy}"
    send_message(msg)
    last_move_time = now
    log_status(f"Sent MOVE `x={x}, y={y}", "DEBUG")
    log_status(f"Sent MOVE dx={dx}, dy={dy}", "DEBUG")


def on_mouse_click(x, y, button, pressed):
    if not FORWARDING or not connected or not pressed:
        return
    if button == mouse.Button.left:
        send_message("CLICK:LEFT")
        log_status("Sent: CLICK:LEFT", "SEND")
    elif button == mouse.Button.right:
        send_message("CLICK:RIGHT")
        log_status("Sent: CLICK:RIGHT", "SEND")


def main():
    global running, mouse_listener,key_listener
    log_status("Starting WebSocket Input Forwarder (Windows)", "INFO")
    log_status(f"Target: {ESP_IP}", "INFO")
    log_status("Press ` (backtick) to toggle forwarding", "INFO")

    connect_thread()

    # Keyboard & mouse listeners
    key_listener = keyboard.Listener(
        on_press=on_key_press,
        on_release=on_key_release
    )
    mouse_listener = mouse.Listener(
        on_click=on_mouse_click,
        on_move=on_mouse_move
    )
    key_listener.start()    
    mouse_listener.start()
    
    try:
        while running:
            time.sleep(0.2)
    except KeyboardInterrupt:
        log_status("Shutting down...", "INFO")


if __name__ == "__main__":
    main()
