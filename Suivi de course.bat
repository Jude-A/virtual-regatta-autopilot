@echo off
rem Lance le tableau de bord de suivi (ouvre le navigateur sur http://127.0.0.1:8765)
cd /d "%~dp0src"
python app.py
pause
