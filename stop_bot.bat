@echo off
echo Stopping Telegram Watermark Bot...
taskkill /F /FI "WINDOWTITLE eq Telegram Thumbnail Watermark Bot - 24/7 Service" /T >nul 2>&1
wmic process where "commandline like '%%python bot.py%%'" delete >nul 2>&1
echo Bot stopped.
pause
