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
AUTO_REFRESH_MIN = 1  # menit
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
    if not BOT_TOKEN or not CHAT_ID:
        return
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
    return result

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

# START notif hanya sekali per session
if not st.session_state.notif_sent_start:
    send_telegram(
        "🟢 <b>ANTAM MONITOR STARTED</b>\n"
        f"MODE: <b>{MODE}</b>\n"
        f"{now_jakarta.strftime('%Y-%m-%d %H:%M:%S')}"
    )
    st.session_state.notif_sent_start = True

# WAKE notif jika bangun dari sleep >30 menit
delta = (now_jakarta - st.session_state.last_ping).seconds
if delta > 1800:
    send_telegram(
        "⚡ <b>ANTAM MONITOR WAKE UP</b>\n"
        f"{now_jakarta.strftime('%Y-%m-%d %H:%M:%S')}"
    )

st.session_state.last_ping = now_jakarta

# =====================
# MAIN CHECK
# =====================
last = load_state()
now = now_jakarta.strftime("%Y-%m-%d %H:%M:%S")

try:
    current = check_stock()
except Exception as e:
    st.error(f"Gagal ambil data: {e}")
    st.stop()

notif_sent = False
for gram, habis in current.items():
    last_status = last.get(gram)
    log_csv(now, gram, habis)

    # 🔔 ANTI-SPAM LOGIC
    if MODE == "PRODUKSI":
        if not habis and last_status is not False:
            send_telegram(
                f"🟢 <b>STOK ANTAM TERSEDIA</b>\n"
                f"{gram}\n"
                f"{now}"
            )
            notif_sent = True

save_state(current)

# =====================
# STATUS TABLE
# =====================
st.subheader("📦 Status Terkini")
status_df = pd.DataFrame([
    {"Gram": g, "Status": "HABIS" if current[g] else "TERSEDIA"}
    for g in GRAM_LIST
])
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
        pivot = df.pivot_table(
            index="timestamp",
            columns="gram",
            values="status",
            aggfunc="last"
        )
        st.line_chart(pivot)

# =====================
# MANUAL REFRESH BUTTON
# =====================
if st.button("🔄 Refresh Manual"):
    st.experimental_rerun()
