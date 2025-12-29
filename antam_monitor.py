import streamlit as st
import requests
import json
import os
import csv
import pandas as pd
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from datetime import datetime
from streamlit_autorefresh import st_autorefresh
import atexit
from zoneinfo import ZoneInfo  # Python 3.9+

# =====================
# CONFIG
# =====================
URL = "https://www.logammulia.com/id/purchase/gold"
GRAM_LIST = ["0.5 gr", "1 gr", "2 gr", "3 gr", "5 gr", "10 gr"]
MODE = "VALIDASI"  # VALIDASI | PRODUKSI
AUTO_REFRESH_MIN = 1
STATE_FILE = "last_status.json"
CSV_LOG = "stock_log.csv"
SCREENSHOT_DIR = "screenshots"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; AntamMonitor/1.0)"}

# =====================
# LOAD ENV
# =====================
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# =====================
# TELEGRAM
# =====================
def send_telegram(msg, photo=None):
    if not BOT_TOKEN or not CHAT_ID:
        return
    try:
        if photo and os.path.exists(photo):
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
            with open(photo, "rb") as f:
                requests.post(
                    url,
                    data={"chat_id": CHAT_ID, "caption": msg, "parse_mode": "HTML"},
                    files={"photo": f},
                    timeout=20
                )
        else:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            requests.post(
                url,
                data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"},
                timeout=15
            )
    except Exception as e:
        st.error(f"Telegram error: {e}")

# =====================
# STOP NOTIF
# =====================
def notify_app_end():
    send_telegram(
        "🔴 <b>ANTAM MONITOR STOPPED</b>\n"
        f"{datetime.now(ZoneInfo('Asia/Jakarta')).strftime('%Y-%m-%d %H:%M:%S')}"
    )
atexit.register(notify_app_end)

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
        w.writerow([ts, gram, 1 if habis else 0])

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
        if key not in text or "belumtersedia" in text:
            result[gram] = True
        else:
            result[gram] = False
    return result, r.text  # HTML dikembalikan untuk screenshot

# =====================
# AUTO REFRESH
# =====================
st_autorefresh(interval=AUTO_REFRESH_MIN * 60 * 1000, key="auto_refresh")

# =====================
# UI
# =====================
st.set_page_config(page_title="ANTAM Monitor", layout="wide")
st.title("🟡 ANTAM Gold Stock Monitor")
st.caption(f"⏱️ Auto refresh tiap {AUTO_REFRESH_MIN} menit")

# =====================
# START / WAKE NOTIF
# =====================
now_jakarta = datetime.now(ZoneInfo("Asia/Jakarta"))
if "app_started" not in st.session_state:
    st.session_state.app_started = True
    st.session_state.notif_sent_start = False
    st.session_state.last_ping = now_jakarta

if not st.session_state.notif_sent_start:
    send_telegram(
        f"🟢 <b>ANTAM MONITOR STARTED</b>\nMODE: <b>{MODE}</b>\n{now_jakarta.strftime('%Y-%m-%d %H:%M:%S')}"
    )
    st.session_state.notif_sent_start = True

delta = (now_jakarta - st.session_state.last_ping).seconds
if delta > 1800:
    send_telegram(f"⚡ <b>ANTAM MONITOR WAKE UP</b>\n{now_jakarta.strftime('%Y-%m-%d %H:%M:%S')}")
st.session_state.last_ping = now_jakarta

# =====================
# MAIN CHECK
# =====================
last = load_state()
now = now_jakarta.strftime("%Y-%m-%d %H:%M:%S")

try:
    current, html_content = check_stock()
except Exception as e:
    st.error(f"Gagal ambil data: {e}")
    st.stop()

notif_sent = False
for gram, habis in current.items():
    last_status = last.get(gram)
    log_csv(now, gram, habis)

    # Simpan screenshot HTML tiap cek
    screenshot_path = os.path.join(SCREENSHOT_DIR, f"{MODE}_{gram}_{now.replace(':','_')}.html")
    with open(screenshot_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    # PRODUKSI → notif hanya jika stok tersedia baru
    if MODE == "PRODUKSI":
        if not habis and last_status is not False:
            send_telegram(f"🟢 <b>STOK ANTAM TERSEDIA</b>\n{gram}\n{now}", photo=screenshot_path)
            notif_sent = True

    # VALIDASI → kirim notif selalu (sanity test)
    elif MODE == "VALIDASI":
        send_telegram(f"🧪 <b>VALIDASI SCRAPER</b>\n{gram}\n{'HABIS' if habis else 'TERSEDIA'}\n{now}", photo=screenshot_path)
        notif_sent = True

save_state(current)

# =====================
# STATUS TABLE
# =====================
st.subheader("📦 Status Terkini")
status_df = pd.DataFrame([{"Gram": g, "Status": "HABIS" if current[g] else "TERSEDIA"} for g in GRAM_LIST])
st.dataframe(status_df, use_container_width=True)

if notif_sent:
    st.success("🔔 Notifikasi Telegram dikirim")

# =====================
# GRAFIK CSV
# =====================
if os.path.exists(CSV_LOG):
    st.subheader("📊 Riwayat Ketersediaan (1 = HABIS)")
    df = pd.read_csv(CSV_LOG)
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp"])
    if not df.empty:
        pivot = df.pivot_table(index="timestamp", columns="gram", values="status", aggfunc="last")
        st.line_chart(pivot)

# =====================
# MANUAL REFRESH BUTTON
# =====================
if st.button("🔄 Refresh Manual"):
    st.experimental_rerun()
