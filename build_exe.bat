@echo off
rem Optional: builds a single InputFeedback.exe in the dist folder.
cd /d "%~dp0"
python -m pip install --quiet -r requirements.txt pyinstaller
python -m PyInstaller --onefile --noconsole --name InputFeedback input_feedback.py
echo Done. Your exe is in the dist folder.
pause
