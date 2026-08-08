@echo off
cd /d "%~dp0"
call venv\Scripts\activate.bat
echo ����᪠� �ࢥ�...
echo �� �⮬ ��������:            http://127.0.0.1:8000
echo � ��㣮�� ���ன�⢠ � ��:   http://IP-�⮣�-��������:8000
echo (IP ᬮ�� �������� ipconfig, ��ப� IPv4-����)
python manage.py runserver 0.0.0.0:8000 --noreload
pause
