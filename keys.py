"""Turn pynput key / mouse events into stable, readable bind names."""
from __future__ import annotations

MOUSE_BUTTONS = {
    "left": "mouse_left",
    "right": "mouse_right",
    "middle": "mouse_middle",
    "x1": "mouse4",
    "x2": "mouse5",
}

DISPLAY = {
    "mouse_left": "Left Click",
    "mouse_right": "Right Click",
    "mouse_middle": "Middle Click",
    "mouse4": "Mouse 4",
    "mouse5": "Mouse 5",
    "wheel_up": "Scroll Up",
    "wheel_down": "Scroll Down",
    "esc": "Escape",
}


def key_to_name(key) -> str:
    """Name a pynput keyboard key. Uses the virtual-key code where possible so
    Shift/Ctrl don't change the name (Shift+1 is still "1", not "!")."""
    name = getattr(key, "name", None)
    if name:  # special key from pynput.keyboard.Key (esc, shift, f1, space...)
        return name
    vk = getattr(key, "vk", None)
    if vk is not None:
        if 0x41 <= vk <= 0x5A:
            return chr(vk).lower()
        if 0x30 <= vk <= 0x39:
            return chr(vk)
        if 0x60 <= vk <= 0x69:
            return f"num{vk - 0x60}"
    char = getattr(key, "char", None)
    if char and char.isprintable():
        return char.lower()
    return f"vk{vk}" if vk is not None else str(key)


def button_to_name(button) -> str:
    raw = getattr(button, "name", str(button))
    return MOUSE_BUTTONS.get(raw, f"mouse_{raw}")


def display_name(name) -> str:
    if not name:
        return "(not set)"
    if name in DISPLAY:
        return DISPLAY[name]
    if len(name) == 1:
        return name.upper()
    if name.startswith("num") and name[3:].isdigit():
        return f"Numpad {name[3:]}"
    if name[0] == "f" and name[1:].isdigit():
        return name.upper()
    return name.replace("_", " ").title()
