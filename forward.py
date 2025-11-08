import websocket
import threading
import time
import sys
from evdev import InputDevice, categorize, ecodes, list_devices
from select import select

ESP_IP = "ws://192.168.0.139:81"
ws = None
ws_lock = threading.Lock()
connected = False
FORWARDING = False
canFORWARD = False
running = True
# Track modifier key states
shift_pressed = False
ctrl_pressed = False
alt_pressed = False
# Global device references for grab/ungrab
keyboard = None
mouse = None

def log_status(msg, level="INFO"):
    """Log with timestamp"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {msg}")

def connect_websocket():
    """Connect to WebSocket with error handling"""
    global ws, connected
    try:
        with ws_lock:
            ws = websocket.WebSocket()
            ws.settimeout(5)
            ws.connect(ESP_IP)
            connected = True
        log_status(f"✓ Connected to {ESP_IP}", "SUCCESS")
        return True
    except Exception as e:
        connected = False
        log_status(f"✗ Connection failed: {e}", "ERROR")
        return False

def send_message(msg):
    """Send message with connection check and error handling"""
    global connected
    if not connected:
        return False
    
    try:
        with ws_lock:
            if ws:
                ws.send(msg)
        return True
    except Exception as e:
        log_status(f"Send failed: {e}", "ERROR")
        connected = False
        return False

def connection_monitor():
    """Monitor and maintain WebSocket connection"""
    global running
    reconnect_delay = 5
    
    while running:
        if not connected:
            log_status("Attempting to reconnect...", "INFO")
            if connect_websocket():
                reconnect_delay = 5
            else:
                time.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 1.5, 30)
        time.sleep(1)

def toggle_forwarding():
    global FORWARDING, keyboard, mouse
    FORWARDING = not FORWARDING
    status = "ENABLED" if FORWARDING else "DISABLED"
    log_status(f"Forwarding {status}", "INFO")
    
    # Grab/ungrab devices to intercept input
    try:
        if FORWARDING:
            if keyboard:
                keyboard.grab()
                log_status("✓ Keyboard grabbed (input intercepted)", "INFO")
            if mouse:
                mouse.grab()
                log_status("✓ Mouse grabbed (input intercepted)", "INFO")
        else:
            if keyboard:
                keyboard.ungrab()
                log_status("✓ Keyboard released", "INFO")
            if mouse:
                mouse.ungrab()
                log_status("✓ Mouse released", "INFO")
    except Exception as e:
        log_status(f"Error toggling device grab: {e}", "ERROR")

def handle_keyboard_event(event):
    """Handle keyboard events"""
    global shift_pressed, ctrl_pressed, alt_pressed, canFORWARD
    
    if event.type != ecodes.EV_KEY:
        return
    
    data = categorize(event)
    keycode = data.keycode
    keystate = data.keystate
    
    # Handle different key types (keycode can be a list)
    if isinstance(keycode, list):
        keycode = keycode[0]
    
    # Track modifier key states
    if keycode in ['KEY_LEFTSHIFT', 'KEY_RIGHTSHIFT']:
        shift_pressed = (keystate in [1, 2])  # 1=press, 2=hold, 0=release
    elif keycode in ['KEY_LEFTCTRL', 'KEY_RIGHTCTRL']:
        ctrl_pressed = (keystate in [1, 2])
    elif keycode in ['KEY_LEFTALT', 'KEY_RIGHTALT']:
        alt_pressed = (keystate in [1, 2])
    
    # Log every key press
    modifiers = []
    if shift_pressed:
        modifiers.append("SHIFT")
    if ctrl_pressed:
        modifiers.append("CTRL")
    if alt_pressed:
        modifiers.append("ALT")
    mod_str = "+".join(modifiers) + "+" if modifiers else ""
    log_status(f"Key: {mod_str}{keycode} | State: {keystate} | Forwarding: {FORWARDING} canFORWARD: {canFORWARD} | Connected: {connected}", "DEBUG")
        
    # Check for backtick toggle (KEY_GRAVE)
    if keycode == 'KEY_GRAVE' and keystate == 1 and canFORWARD == False:
        canFORWARD = True# Only toggle on press, not hold
        #toggle_forwarding()
        return
        
    if keycode == 'KEY_GRAVE' and keystate == 0 and canFORWARD == True:
        canFORWARD = False# Only toggle on press, not hold
        toggle_forwarding()
        return
    
    # Only act on key down (1) or hold (2), ignore key up (0)
    if keystate == 0:
        return
    
    if not FORWARDING or not connected:
        return
    
    # Map keys to their hex codes (matching USB HID usage codes)
    hex_key_map = {
        'KEY_ESC': '0xB1',
        'KEY_ENTER': '0xB0',  # KEY_RETURN
        'KEY_BACKSPACE': '0xB2',
        'KEY_TAB': '0xB3',
        'KEY_SPACE': '0x20',
        'KEY_CAPSLOCK': '0xC1',
        'KEY_F1': '0xC2',
        'KEY_F2': '0xC3',
        'KEY_F3': '0xC4',
        'KEY_F4': '0xC5',
        'KEY_F5': '0xC6',
        'KEY_F6': '0xC7',
        'KEY_F7': '0xC8',
        'KEY_F8': '0xC9',
        'KEY_F9': '0xCA',
        'KEY_F10': '0xCB',
        'KEY_F11': '0xCC',
        'KEY_F12': '0xCD',
        'KEY_INSERT': '0xD1',
        'KEY_HOME': '0xD2',
        'KEY_PAGEUP': '0xD3',
        'KEY_DELETE': '0xD4',
        'KEY_END': '0xD5',
        'KEY_PAGEDOWN': '0xD6',
        'KEY_RIGHT': '0xD7',
        'KEY_LEFT': '0xD8',
        'KEY_DOWN': '0xD9',
        'KEY_UP': '0xDA',
    }
    
    # Build modifier prefix
    mod_prefix = ""
    if ctrl_pressed:
        mod_prefix += "CTRL+"
    if shift_pressed:
        mod_prefix += "SHIFT+"
    if alt_pressed:
        mod_prefix += "ALT+"
    
    # Don't send modifier keys by themselves
    if keycode in ['KEY_LEFTSHIFT', 'KEY_RIGHTSHIFT', 'KEY_LEFTCTRL', 'KEY_RIGHTCTRL', 'KEY_LEFTALT', 'KEY_RIGHTALT', 'KEY_LEFTMETA', 'KEY_RIGHTMETA']:
        return
    
    if keycode in hex_key_map:
        msg = f"KEY:{mod_prefix}{hex_key_map[keycode]}"
        send_message(msg)
        log_status(f"Sent: {msg}", "SEND")
    elif keycode.startswith('KEY_'):
        # Extract character for regular keys (e.g., KEY_A -> a)
        char = keycode.replace('KEY_', '').lower()
        if len(char) == 1 and char.isalpha():
            # Send as character for a-z
            msg = f"KEY:{mod_prefix}{char}"
            send_message(msg)
            log_status(f"Sent: {msg}", "SEND")
        elif len(char) == 1 and char.isdigit():
            # Send digits 0-9
            msg = f"KEY:{mod_prefix}{char}"
            send_message(msg)
            log_status(f"Sent: {msg}", "SEND")
        else:
            # Handle special punctuation keys
            punctuation_map = {
                'KEY_MINUS': '-',
                'KEY_EQUAL': '=',
                'KEY_LEFTBRACE': '[',
                'KEY_RIGHTBRACE': ']',
                'KEY_SEMICOLON': ';',
                'KEY_APOSTROPHE': "'",
                'KEY_GRAVE': '`',
                'KEY_BACKSLASH': '\\',
                'KEY_COMMA': ',',
                'KEY_DOT': '.',
                'KEY_SLASH': '/',
            }
            if keycode in punctuation_map:
                msg = f"KEY:{mod_prefix}{punctuation_map[keycode]}"
                send_message(msg)
                log_status(f"Sent: {msg}", "SEND")

def handle_mouse_event(event):
    """Handle mouse events"""
    if not FORWARDING or not connected:
        return
    
    if event.type == ecodes.EV_KEY:
        # Mouse button
        data = categorize(event)
        keycode = data.keycode
        keystate = data.keystate
        
        log_status(f"Mouse Button: {keycode} | State: {keystate}", "DEBUG")
        
        if keystate == 1:  # Button press
            if 'BTN_LEFT' in keycode :
                send_message("CLICK:LEFT")
                log_status("Sent: CLICK:LEFT", "SEND")
            elif keycode == 'BTN_RIGHT':
                send_message("CLICK:RIGHT")
                log_status("Sent: CLICK:RIGHT", "SEND")
    
    elif event.type == ecodes.EV_REL:
        # Mouse movement
        if event.code == ecodes.REL_X:
            msg = f"MOVE:{event.value}:0"
            send_message(msg)
            log_status(f"Sent: {msg}", "SEND")
        elif event.code == ecodes.REL_Y:
            msg = f"MOVE:0:{event.value}"
            send_message(msg)
            log_status(f"Sent: {msg}", "SEND")
        elif event.code == ecodes.REL_WHEEL:
            msg = f"SCROLL:{event.value}"
            send_message(msg)
            log_status(f"Sent: {msg}", "SEND")

def main():
    global running, keyboard, mouse
    
    log_status("Starting WebSocket Input Forwarder", "INFO")
    log_status(f"Target: {ESP_IP}", "INFO")
    log_status("Press ` (backtick/grave) to toggle forwarding", "INFO")
    
    # Find devices
    devices = [InputDevice(fn) for fn in list_devices()]
    keyboard = None
    mouse = None
    
    for dev in devices:
        caps = dev.capabilities()
        if ecodes.EV_KEY in caps:
            if ecodes.KEY_A in caps[ecodes.EV_KEY]:
                keyboard = dev
                log_status(f"Found keyboard: {dev.name}", "INFO")
            if ecodes.BTN_LEFT in caps[ecodes.EV_KEY]:
                log_status(f"Found mouse: {dev.name}", "INFO")
                if dev.name == "USB Gaming Mouse":
                    mouse = dev
                    log_status(f"set mouse: {dev.name}", "INFO")
    
    if not keyboard:
        log_status("No keyboard found!", "ERROR")
        return
    if not mouse:
        log_status("No mouse found!", "ERROR")
        return
    
    # Initial connection
    connect_websocket()
    
    # Start connection monitor
    monitor_thread = threading.Thread(target=connection_monitor, daemon=True)
    monitor_thread.start()
    
    log_status("Listening for input events. Press CTRL+C to exit.", "INFO")
    
    try:
        while running:
            r, w, x = select([keyboard, mouse], [], [], 0.1)
            for dev in r:
                try:
                    for event in dev.read():
                        if dev == keyboard:
                            handle_keyboard_event(event)
                        elif dev == mouse:
                            handle_mouse_event(event)
                except BlockingIOError:
                    pass
    except KeyboardInterrupt:
        log_status("Shutting down...", "INFO")
        running = False
        with ws_lock:
            if ws:
                ws.close()
        log_status("Disconnected", "INFO")

if __name__ == "__main__":
    main()
