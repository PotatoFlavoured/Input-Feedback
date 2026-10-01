@echo off
cd /d "%~dp0"
python -m pip install --quiet -r requirements.txt
start "" pythonw input_feedback.py
