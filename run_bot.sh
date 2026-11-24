#!/usr/bin/env bash
# ==============================================================
# Telegram Thumbnail Watermark Bot - 24/7 Keep-Alive Runner
# Restarts automatically if crashed, stopped, or disconnected
# ==============================================================

echo "=========================================================="
echo " Starting Telegram Watermark Bot with 24/7 Auto-Restart..."
echo "=========================================================="

while true; do
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Launching bot.py..."
    python3 bot.py
    EXIT_CODE=$?
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Bot stopped with exit code ${EXIT_CODE}."
    echo "Restarting in 5 seconds... Press Ctrl+C to stop."
    sleep 5
done
