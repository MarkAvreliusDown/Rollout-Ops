@echo off
cd /d "%~dp0"
call venv\Scripts\activate.bat
echo Делаю бэкап базы и файлов в C:\mybacks ...
python manage.py backup
pause
