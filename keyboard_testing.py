import keyboard
import platform

# Beep function for different OS
def beep():
    if platform.system() == 'Windows':
        import winsound
        winsound.Beep(1000, 100)  # frequency (Hz), duration (ms)
    else:
        import os
        os.system('printf "\a"')  # ANSI beep (may not work on all terminals)

print("Start typing... (Press ESC to exit)")

last_key = None

while True:
    event = keyboard.read_event()
    if event.event_type == keyboard.KEY_DOWN:
        if event.name != last_key:
            print(f'You pressed: {event.name}')
            beep()
            if event.name == 'esc':
                break
            last_key = event.name
    elif event.event_type == keyboard.KEY_UP:
        # Reset last_key on key release to allow next press
        last_key = None
