@echo off
title Telegram Thumbnail Watermark Bot - 24/7 Service
echo ==========================================================
echo  Starting Telegram Watermark Bot with 24/7 Auto-Restart...
echo ==========================================================

:loop
echo [%date% %time%] Launching bot.py...
python bot.py
echo.
echo [%date% %time%] Bot exited or crashed.
echo Restarting in 5 seconds... Press Ctrl+C to stop.
timeout /t 5 /nobreak >nul
goto loop
