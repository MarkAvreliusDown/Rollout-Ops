@echo off
cd /d "%~dp0"
call venv\Scripts\activate.bat

echo Проверяем, не завис ли старый сервер на порту 8000...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr "0.0.0.0:8000" ^| findstr "LISTENING"') do (
    echo Останавливаем старый процесс, PID %%p...
    taskkill /F /PID %%p >nul 2>&1
)

echo Запускаем сервер...
echo На этом компьютере:            http://127.0.0.1:8000
echo С другого устройства в сети:   http://IP-этого-компьютера:8000
echo (IP смотреть командой ipconfig, строка IPv4-адрес)
python manage.py runserver 0.0.0.0:8000 --noreload
pause
