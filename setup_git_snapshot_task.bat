@echo off
cd /d "%~dp0"
echo Настраиваю ежедневный снимок проекта в git в 10:10 через Планировщик Windows...
schtasks /create /tn "CF_Board_GitSnapshot" /tr "\"%~dp0git_snapshot_silent.bat\"" /sc daily /st 10:10 /f
if errorlevel 1 (
    echo Не получилось создать задачу. Попробуй запустить этот файл от имени администратора.
) else (
    echo Готово! Снимок проекта будет делаться каждый день в 10:10 автоматически.
    echo Посмотреть/удалить задачу можно в Планировщике заданий Windows,
    echo задача называется "CF_Board_GitSnapshot".
)
pause