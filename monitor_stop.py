from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import os
import requests
from dotenv import load_dotenv

# =====================
# LOAD ENV
# =====================
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

HEARTBEAT_FILE = "heartbeat.txt"
TIMEOUT_MINUTES = 3

if not BOT_TOKEN or not CHAT_ID:
    raise RuntimeError("BOT_TOKEN / CHAT_ID tidak ditemukan di .env")

# =====================
# TELEGRAM
# =====================
def send(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={
                "chat_id": CHAT_ID,
                "text": msg,
                "parse_mode": "HTML"
            },
            timeout=15
        )
    except Exception as e:
        print("Telegram error:", e)

# =====================
# CHECK HEARTBEAT
# =====================
if os.path.exists(HEARTBEAT_FILE):
    with open(HEARTBEAT_FILE, "r") as f:
        last = datetime.fromisoformat(f.read().strip())

    now = datetime.now(ZoneInfo("Asia/Jakarta"))

    if now - last > timedelta(minutes=TIMEOUT_MINUTES):
        send(
            "🔴 <b>ANTAM MONITOR STOPPED</b>\n"
            f"{now.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        os.remove(HEARTBEAT_FILE)
