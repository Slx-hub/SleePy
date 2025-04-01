import evdev
import subprocess
import threading

# Dictionary to store key states
key_states = {}

def play_sound(sound):
    subprocess.run(["aplay", f"./sounds/{sound}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def track_keys():
    """ Reads key events in the background and updates key_states. """
    devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
    keyboard = None

    for device in devices:
        print(f"Device found: {device.name}")
        if 'keyboard' in device.name.lower():  # Find a keyboard device
            play_sound("ok.wav")
            keyboard = evdev.InputDevice(device.path)
            break

    if not keyboard:
        print("No keyboard device found!")
        play_sound("error.wav")
        return

    for event in keyboard.read_loop():
        if event.type == evdev.ecodes.EV_KEY:
            key_event = evdev.categorize(event)
            key_states[key_event.keycode] = key_event.keystate  # 1=Pressed, 0=Released

play_sound("startup.wav")

# Start the key tracker in a separate thread
key_thread = threading.Thread(target=track_keys, daemon=True)
key_thread.start()

# Function to check if a key is currently held
def is_key_held(key):
    return key_states.get(key, 0) == 1  # 1 means pressed

# Example usage:
import time
while True:
    if is_key_held("KEY_1"):
        print("1 is held down!")
        play_sound("ok.wav")
    if is_key_held("KEY_BACKSPACE"):
        print("Backspace is held down!")
        play_sound("error.wav")
    time.sleep(0.1)  # Prevent high CPU usage
