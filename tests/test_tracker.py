import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from tracker import ERROR, SUCCESS, WARNING, EditTracker  # noqa: E402


def make(eor: bool, **overrides) -> EditTracker:
    cfg = {**config.DEFAULTS, "binds": dict(config.DEFAULTS["binds"]), "edit_on_release": eor}
    cfg.update(overrides)
    return EditTracker(config.tracker_settings(cfg))


class Runner:
    def __init__(self, tracker):
        self.tr = tracker
        self.t = 0.0
        self.out = []

    def press(self, name, dt=0.05):
        self.t += dt
        self._add(self.tr.on_press(name, self.t))

    def release(self, name, dt=0.05):
        self.t += dt
        self._add(self.tr.on_release(name, self.t))

    def tap(self, name):
        self.press(name)
        self.release(name)

    def wait(self, seconds):
        self.t += seconds
        self._add(self.tr.tick(self.t))

    def _add(self, fb):
        if fb:
            self.out.append(fb.kind)


class EditOnReleaseOn(unittest.TestCase):
    def test_release_confirms(self):
        r = Runner(make(True))
        r.tap("g")
        r.press("mouse_left")
        r.release("mouse_left")
        self.assertEqual(r.out, [SUCCESS])

    def test_edit_again_while_holding_select_is_error(self):
        r = Runner(make(True))
        r.tap("g")
        r.press("mouse_left")
        r.tap("g")
        r.release("mouse_left")
        self.assertEqual(r.out, [ERROR])

    def test_switching_weapon_while_holding_is_error(self):
        r = Runner(make(True))
        r.tap("g")
        r.press("mouse_left")
        r.tap("1")
        r.release("mouse_left")
        self.assertEqual(r.out, [ERROR])

    def test_building_while_holding_is_error(self):
        r = Runner(make(True))
        r.tap("g")
        r.press("mouse_left")
        r.tap("f1")
        self.assertEqual(r.out, [ERROR])

    def test_slow_release_warns_then_confirms(self):
        r = Runner(make(True))
        r.tap("g")
        r.press("mouse_left")
        r.wait(1.2)
        r.release("mouse_left")
        self.assertEqual(r.out, [WARNING, SUCCESS])

    def test_opening_and_closing_edit_is_neutral(self):
        r = Runner(make(True))
        r.tap("g")
        r.tap("g")
        r.tap("1")
        self.assertEqual(r.out, [])

    def test_edit_then_build_without_selecting_is_error(self):
        r = Runner(make(True))
        r.tap("g")
        r.tap("f1")
        self.assertEqual(r.out, [ERROR])

    def test_select_held_before_edit_then_build_is_error(self):
        r = Runner(make(True))
        r.press("mouse_left")
        r.tap("g")
        r.tap("f2")
        self.assertEqual(r.out, [ERROR])

    def test_reset_then_edit_confirms(self):
        r = Runner(make(True))
        r.tap("g")
        r.tap("mouse_right")
        r.tap("g")
        self.assertEqual(r.out, [SUCCESS])

    def test_select_held_from_before_edit_confirms_on_release(self):
        r = Runner(make(True))
        r.press("mouse_left")
        r.tap("g")
        r.release("mouse_left")
        self.assertEqual(r.out, [SUCCESS])

    def test_shooting_outside_edit_is_ignored(self):
        r = Runner(make(True))
        r.tap("mouse_left")
        r.tap("1")
        r.tap("f1")
        self.assertEqual(r.out, [])


class EditOnReleaseOff(unittest.TestCase):
    def test_edit_select_edit_confirms(self):
        r = Runner(make(False))
        r.tap("g")
        r.tap("mouse_left")
        r.tap("mouse_left")
        r.tap("g")
        self.assertEqual(r.out, [SUCCESS])

    def test_switching_before_confirm_is_error(self):
        r = Runner(make(False))
        r.tap("g")
        r.tap("mouse_left")
        r.tap("2")
        self.assertEqual(r.out, [ERROR])

    def test_edit_then_build_without_selecting_is_error(self):
        r = Runner(make(False))
        r.tap("g")
        r.tap("f3")
        self.assertEqual(r.out, [ERROR])

    def test_escape_before_confirm_is_error(self):
        r = Runner(make(False))
        r.tap("g")
        r.tap("mouse_left")
        r.tap("esc")
        self.assertEqual(r.out, [ERROR])

    def test_holding_select_is_fine(self):
        r = Runner(make(False))
        r.tap("g")
        r.press("mouse_left")
        r.wait(1.5)
        r.tap("g")
        r.release("mouse_left")
        self.assertEqual(r.out, [SUCCESS])

    def test_stale_edit_is_forgotten(self):
        r = Runner(make(False))
        r.tap("g")          # not looking at a build, nothing happens in game
        r.tap("mouse_left")  # shooting
        r.wait(4)
        r.tap("1")
        self.assertEqual(r.out, [])


class Misc(unittest.TestCase):
    def test_key_repeat_ignored(self):
        r = Runner(make(False))
        r.press("g")
        r.press("g")  # auto-repeat while held
        r.release("g")
        r.tap("mouse_left")
        r.tap("g")
        self.assertEqual(r.out, [SUCCESS])

    def test_edit_bind_never_counts_as_exit(self):
        binds = dict(config.DEFAULTS["binds"], edit="1")
        settings = config.tracker_settings({**config.DEFAULTS, "binds": binds})
        self.assertNotIn("1", settings.exit_keys)


if __name__ == "__main__":
    unittest.main()
