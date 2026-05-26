@echo off
chcp 65001 >nul
title Установка AutoDetail Pro

echo.
echo  Установка зависимостей AutoDetail Pro...
echo.

set PYTHON=
where python >nul 2>&1 && set PYTHON=python
if "%PYTHON%"=="" where python3 >nul 2>&1 && set PYTHON=python3
if "%PYTHON%"=="" (
    echo [ОШИБКА] Python не найден. Установите с python.org
    pause
    exit /b 1
)

echo  Python: %PYTHON%
echo.
echo  Устанавливаем Flask...
%PYTHON% -m pip install flask
echo.
echo  Готово! Теперь запустите start.bat
echo.
pause
