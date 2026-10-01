# Input Feedback

A small overlay for Fortnite that tells you whether your **edits are actually getting confirmed**.

The overlay is just one circle:

| Circle | Meaning |
|---|---|
| 🟢 Green | Your inputs are fine / your last edit was confirmed |
| 🔴 Red | You made an input mistake (stays red for 1.5 s, or until your next good edit) |
| ⚪ Grey | Paused, or Fortnite isn't the active window |

The settings window also shows confirmed edits, missed edits, slow releases, an accuracy %, and a log of what went wrong each time.

## What counts as a mistake

**Edit on release ON** (press edit → hold left click on tiles → *release* left click to confirm)
- Pressing **edit again** while still holding left click → red (the edit wasn't confirmed)
- Pressing a **build piece, weapon slot, pickaxe, build toggle or Esc** while still holding left click → red
- Holding left click in edit for longer than 1000 ms → red while you're holding, as a reminder to let go. It turns green when you release. You can change the time, or set it to 0 to turn this off.

**Edit on release OFF** (press edit → left click tiles → press *edit* again to confirm)
- Selecting tiles and then switching to a build piece, weapon, pickaxe, build toggle or pressing Esc **without pressing edit again** → red

These don't count as mistakes: opening edit and closing it without changing anything, or shooting / holding left click outside of edit.

## Setup (Windows)

1. Install Python 3.9 or newer from <https://www.python.org/downloads/>. **Tick "Add python.exe to PATH"** in the installer.
2. Download this repo (green **Code** button → *Download ZIP*) and unzip it.
3. Double-click **`run.bat`**. The first time, it installs the one dependency (`pynput`).
4. In the settings window:
   - Choose **Edit on release ON** or **OFF** to match your Fortnite setting.
   - Click **Set** next to each bind and press the key or mouse button you use in Fortnite. Mouse 4/5 and scroll wheel binds work too. Press Esc to cancel. The defaults are Fortnite's default binds.
   - Tick **Unlock overlay** and drag the circle to where you want it, then untick it so clicks pass through to the game.
5. Set Fortnite's **Window Mode to "Windowed Fullscreen"**. Overlays can't show on top of exclusive Fullscreen.

Press **F8** (you can change it) to pause or resume tracking, e.g. while typing in chat. By default it only tracks while Fortnite is the active window.

Settings are saved to `config.json` next to the program.

Optional: `build_exe.bat` packages it into a single `dist/InputFeedback.exe`.

## Good to know

- The program **only reads** your keyboard and mouse, the same way keystroke-display overlays do. It doesn't send inputs and doesn't read or change the game. Still, use any third-party tool at your own risk.
- It only sees your inputs, not the game, so it can't tell whether you were actually looking at a build when you pressed edit. To avoid false reds, an edit with no activity for 3 s is forgotten (you can change this in Options).
- Make sure your binds here match your Fortnite binds exactly. The status line warns you if two actions share the same key.

## Running the tests

```
python -m unittest discover -s tests
```
