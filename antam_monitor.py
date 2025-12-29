import requests
import json
import os
import csv
import time

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from datetime import datetime

# =====================
# CONFIG
# =====================
URL = "https://www.logammulia.com/id/purchase/gold"
GRAM_LIST = ["0.5 gr", "1 gr", "2 gr", "3 gr", "5 gr", "10 gr"]

MODE = "PRODUKSI"   # VALIDASI | PRODUKSI
INTERVAL = 60

STATE_FILE = "last_status.json"
CSV_LOG = "stock_log.csv"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AntamMonitor/1.0)"
}

# =====================
# LOAD ENV
# =====================
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# =====================
# TELEGRAM
# =====================
def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(
            url,
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
# STATE
# =====================
def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

# =====================
# CSV LOG
# =====================
def log_csv(ts, gram, habis):
    exists = os.path.exists(CSV_LOG)
    with open(CSV_LOG, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(["timestamp", "gram", "status"])
        w.writerow([ts, gram, "HABIS" if habis else "TERSEDIA"])

# =====================
# CHECK STOCK
# =====================
def check_stock():
    r = requests.get(URL, headers=HEADERS, timeout=30)
    soup = BeautifulSoup(r.text, "html.parser")

    text = soup.get_text(" ").lower().replace(" ", "")
    result = {}

    for gram in GRAM_LIST:
        key = gram.replace(" ", "").lower()
        if key not in text:
            result[gram] = True
        elif "belumtersedia" in text:
            result[gram] = True
        else:
            result[gram] = False

    return result

# =====================
# MAIN (1x RUN - STREAMLIT FRIENDLY)
# =====================
def run_once():
    last = load_state()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    current = check_stock()

    for gram, habis in current.items():
        last_status = last.get(gram)

        log_csv(now, gram, habis)

        if MODE == "VALIDASI" and habis:
            send_telegram(f"🧪 VALIDASI\n{gram}\nBELUM TERSEDIA\n{now}")

        elif MODE == "PRODUKSI":
            if not habis and last_status is not False:
                send_telegram(
                    f"🟢 <b>STOK ANTAM TERSEDIA</b>\n{gram}\n{now}"
                )

    save_state(current)
    print("✔ UPDATE", now)

if __name__ == "__main__":
    run_once()
