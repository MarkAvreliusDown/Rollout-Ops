@echo off
chcp 866 >nul
cd /d "%~dp0"
call venv\Scripts\activate.bat
echo Делаю снимок проекта в git (код + база + медиа)...
python manage.py git_snapshot
pause