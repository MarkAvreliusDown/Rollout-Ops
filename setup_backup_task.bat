@echo off
cd /d "%~dp0"
echo Настраиваю ежедневный бэкап в 10:00 через Планировщик заданий Windows...
schtasks /create /tn "CF_Board_Backup" /tr "\"%~dp0backup_silent.bat\"" /sc daily /st 10:00 /f
if errorlevel 1 (
    echo Не получилось создать задание. Попробуй запустить этот файл от имени администратора.
) else (
    echo Готово! Бэкап будет делаться каждый день в 10:00 автоматически.
    echo Посмотреть/изменить задание можно в Планировщике заданий Windows,
    echo задание называется "CF_Board_Backup".
)
pause
