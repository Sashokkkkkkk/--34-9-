@echo off
chcp 65001 >nul
title AutoDetail Pro

echo.
echo  ╔══════════════════════════════════════════╗
echo  ║       AutoDetail Pro — Автомойка         ║
echo  ╚══════════════════════════════════════════╝
echo.

:: Ищем Python в стандартных местах
set PYTHON=
where python >nul 2>&1 && set PYTHON=python
if "%PYTHON%"=="" (
    where python3 >nul 2>&1 && set PYTHON=python3
)
if "%PYTHON%"=="" (
    if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
        set PYTHON=%LOCALAPPDATA%\Programs\Python\Python311\python.exe
    )
)
if "%PYTHON%"=="" (
    if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
        set PYTHON=%LOCALAPPDATA%\Programs\Python\Python312\python.exe
    )
)
if "%PYTHON%"=="" (
    if exist "C:\Python311\python.exe" set PYTHON=C:\Python311\python.exe
)
if "%PYTHON%"=="" (
    if exist "C:\Python312\python.exe" set PYTHON=C:\Python312\python.exe
)
if "%PYTHON%"=="" (
    echo [ОШИБКА] Python не найден!
    echo.
    echo  Установите Python с https://www.python.org/downloads/
    echo  При установке ОБЯЗАТЕЛЬНО поставьте галочку:
    echo  "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

echo  Найден Python: %PYTHON%
echo.

:: Устанавливаем Flask
echo  Проверка Flask...
%PYTHON% -m pip install flask --quiet --no-warn-script-location 2>nul
if errorlevel 1 (
    %PYTHON% -m pip install flask --quiet --user --no-warn-script-location 2>nul
)
echo  Flask готов.
echo.

:: Информация
echo  ══════════════════════════════════════════
echo   Сайт: http://127.0.0.1:5000
echo   Или:  http://localhost:5000
echo  ══════════════════════════════════════════
echo.
echo   Учётные записи:
echo   Администратор : admin    / admin123
echo   Оператор      : operator / oper1234
echo   Клиент        : client   / client12
echo.
echo   Нажмите Ctrl+C для остановки
echo  ══════════════════════════════════════════
echo.

:: Открываем браузер через 2 секунды
start "" cmd /c "timeout /t 2 >nul && start http://127.0.0.1:5000"

:: Запускаем приложение
cd /d "%~dp0"
%PYTHON% app.py

echo.
echo  Сервер остановлен.
pause
