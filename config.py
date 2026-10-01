"""Load and save settings to config.json next to the program."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

from tracker import TrackerSettings

# Edit-related binds shown in the settings window.
EDIT_BINDS = [
    ("edit", "Edit"),
    ("select", "Select (edit tiles)"),
    ("reset", "Reset edit"),
]

# Binds that take you out of edit mode. Pressing one of these before the edit
# is confirmed means the edit didn't go through.
EXIT_BINDS = [
    ("wall", "Wall"),
    ("floor", "Floor"),
    ("stairs", "Stairs"),
    ("roof", "Cone / Roof"),
    ("trap", "Trap"),
    ("build_toggle", "Build mode toggle"),
    ("pickaxe", "Pickaxe"),
    ("slot1", "Weapon slot 1"),
    ("slot2", "Weapon slot 2"),
    ("slot3", "Weapon slot 3"),
    ("slot4", "Weapon slot 4"),
    ("slot5", "Weapon slot 5"),
]

# Fortnite's default keyboard & mouse binds.
DEFAULTS = {
    "edit_on_release": True,
    "binds": {
        "edit": "g",
        "select": "mouse_left",
        "reset": "mouse_right",
        "wall": "f1",
        "floor": "f2",
        "stairs": "f3",
        "roof": "f4",
        "trap": "f5",
        "build_toggle": "q",
        "pickaxe": "f",
        "slot1": "1",
        "slot2": "2",
        "slot3": "3",
        "slot4": "4",
        "slot5": "5",
    },
    "max_hold_ms": 1000,
    "edit_timeout_ms": 3000,
    "red_ms": 1500,
    "only_when_fortnite_focused": True,
    "pause_key": "f8",
    "overlay": {"x": 40, "y": 40, "size": 36},
}


def config_path() -> Path:
    if getattr(sys, "frozen", False):  # packaged .exe
        base = Path(sys.executable).parent
    else:
        base = Path(__file__).resolve().parent
    return base / "config.json"


def _merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        elif k in out:
            out[k] = v
    return out


def load() -> dict:
    path = config_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return _merge(DEFAULTS, data)
    except (OSError, ValueError):
        return copy.deepcopy(DEFAULTS)


def save(cfg: dict) -> None:
    try:
        config_path().write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    except OSError:
        pass


def tracker_settings(cfg: dict) -> TrackerSettings:
    binds = cfg["binds"]
    exit_keys = {"esc": "Escape"}
    for key, label in EXIT_BINDS:
        if binds.get(key):
            exit_keys[binds[key]] = label
    # Never treat an edit bind as an exit bind.
    for key, _ in EDIT_BINDS:
        exit_keys.pop(binds.get(key), None)
    return TrackerSettings(
        edit_on_release=cfg["edit_on_release"],
        edit=binds.get("edit"),
        select=binds.get("select"),
        reset=binds.get("reset"),
        exit_keys=exit_keys,
        max_hold_ms=int(cfg["max_hold_ms"]),
        edit_timeout_ms=int(cfg["edit_timeout_ms"]),
    )
