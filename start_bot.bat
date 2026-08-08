@echo off
cd /d "%~dp0"
call venv\Scripts\activate.bat
echo Запуск Telegram-бота. Не закрывайте это окно, пока бот нужен.
python manage.py telegram_bot
pause
