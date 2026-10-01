"""Edit-input tracking logic.

This module has no dependencies on the UI or on the input hooks, so it can be
unit-tested on any platform. Feed it press/release events (with a monotonic
timestamp in seconds) and it returns Feedback objects when an edit is
confirmed or when an input mistake is detected.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

SUCCESS = "success"   # edit confirmed correctly
ERROR = "error"       # edit was not confirmed (input mistake)
WARNING = "warning"   # select held too long in edit-on-release mode


@dataclass
class Feedback:
    kind: str
    message: str


@dataclass
class TrackerSettings:
    edit_on_release: bool = True
    edit: Optional[str] = None
    select: Optional[str] = "mouse_left"
    reset: Optional[str] = None
    # Inputs that leave edit mode (build pieces, weapon slots, pickaxe...),
    # mapped to a readable label used in error messages.
    exit_keys: Dict[str, str] = field(default_factory=dict)
    # Edit on release only: warn when select is held longer than this. 0 = off.
    max_hold_ms: int = 1000
    # Forget an edit that has had no activity for this long. Guards against
    # pressing edit while not looking at a build (the game ignores it). 0 = off.
    edit_timeout_ms: int = 3000


class EditTracker:
    def __init__(self, settings: Optional[TrackerSettings] = None):
        self.settings = settings or TrackerSettings()
        self.down = set()
        self.reset()

    def configure(self, settings: TrackerSettings) -> None:
        self.settings = settings
        self.reset()

    def reset(self) -> None:
        """Forget any edit in progress (keeps track of physically held inputs)."""
        self.editing = False
        self.changed = False       # tiles selected / reset since entering edit
        self.holding = False       # select pressed during this edit, not yet released
        self.hold_started = 0.0
        self.hold_warned = False
        self.last_activity = 0.0

    # -- input events -----------------------------------------------------

    def on_press(self, name: str, t: float) -> Optional[Feedback]:
        if name in self.down:
            return None  # keyboard auto-repeat
        self.down.add(name)
        self._expire(t)
        s = self.settings

        if not self.editing:
            if name == s.edit:
                self._enter(t)
            return None

        if name == s.edit:
            if s.edit_on_release and self.holding:
                return self._fail("Pressed edit while still holding select. "
                                  "Release select to confirm the edit.")
            if self.changed:
                return self._ok("Edit confirmed")
            self.reset()  # opened and closed edit without changing anything
            return None

        if name == s.select:
            self.changed = True
            self.last_activity = t
            if s.edit_on_release:
                self.holding = True
                self.hold_started = t
                self.hold_warned = False
            return None

        if name == s.reset:
            self.changed = True
            self.last_activity = t
            return None

        if name in s.exit_keys:
            label = s.exit_keys[name]
            if self.holding:
                return self._fail(f"Switched to {label} while still holding select. "
                                  "Edit was not confirmed.")
            if self.changed:
                confirm = "pressing edit" if not s.edit_on_release else "confirming"
                return self._fail(f"Switched to {label} before {confirm}. "
                                  "Edit was not confirmed.")
            self.reset()
            return None

        return None

    def on_release(self, name: str, t: float) -> Optional[Feedback]:
        self.down.discard(name)
        self._expire(t)
        s = self.settings
        if self.editing and s.edit_on_release and self.holding and name == s.select:
            held_ms = (t - self.hold_started) * 1000
            return self._ok(f"Edit confirmed on release ({held_ms:.0f} ms hold)")
        return None

    def tick(self, t: float) -> Optional[Feedback]:
        """Call regularly to detect time-based problems."""
        self._expire(t)
        s = self.settings
        if (self.editing and self.holding and s.max_hold_ms > 0
                and not self.hold_warned
                and (t - self.hold_started) * 1000 >= s.max_hold_ms):
            self.hold_warned = True
            return Feedback(WARNING, "Still holding select. Release it to confirm the edit.")
        return None

    # -- helpers ----------------------------------------------------------

    def _enter(self, t: float) -> None:
        self.reset()
        self.editing = True
        self.last_activity = t

    def _expire(self, t: float) -> None:
        timeout = self.settings.edit_timeout_ms
        if (self.editing and not self.holding and timeout > 0
                and (t - self.last_activity) * 1000 > timeout):
            self.reset()

    def _ok(self, message: str) -> Feedback:
        self.reset()
        return Feedback(SUCCESS, message)

    def _fail(self, message: str) -> Feedback:
        self.reset()
        return Feedback(ERROR, message)
