#!/bin/bash
# VII Telegram Remote — Launch Script
# Developed by The 747 Lab
cd "$(dirname "$0")"
export VII_TELEGRAM_TOKEN="8593543492:AAG4F2I-wPH4TiyU_28jUes5SvqR0G70maQ"
export VII_TELEGRAM_CHAT_ID="1217359466"
exec ./tts-venv/bin/python3 telegram_remote.py
