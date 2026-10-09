@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel% equ 0 (
  py -3 learning_loop.py serve
) else (
  python learning_loop.py serve
)
pause
