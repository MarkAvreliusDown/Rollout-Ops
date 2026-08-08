@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
set OUT=project_source_dump.txt
if exist "%OUT%" del "%OUT%"

echo === PROJECT SOURCE DUMP === > "%OUT%"

for /r %%f in (*.py) do (
    echo %%f | findstr /i "venv migrations\\0000 __pycache__" >nul
    if errorlevel 1 (
        echo. >> "%OUT%"
        echo ##### %%f ##### >> "%OUT%"
        type "%%f" >> "%OUT%"
    )
)

for /r %%f in (*.html) do (
    echo %%f | findstr /i "venv" >nul
    if errorlevel 1 (
        echo. >> "%OUT%"
        echo ##### %%f ##### >> "%OUT%"
        type "%%f" >> "%OUT%"
    )
)

echo Готово: %OUT%
pause
