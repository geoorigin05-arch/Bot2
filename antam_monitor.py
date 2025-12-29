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

# =====================
# CONFIG
# =====================
URL = "https://www.logammulia.com/id/purchase/gold"
GRAM_LIST = ["0.5 gr", "1 gr", "2 gr", "3 gr", "5 gr", "10 gr"]

MODE = "PRODUKSI"   # VALIDASI | PRODUKSI
AUTO_REFRESH_MIN = 1   # ⏱️ AUTO REFRESH (MENIT)

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
# NOTIF END APP
# =====================
def notify_app_end():
    send_telegram(
        "🔴 <b>ANTAM MONITOR STOPPED</b>\n"
        f"{datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%Y-%m-%d %H:%M:%S")}"
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
# START NOTIF (ANTI-SPAM)
# =====================
if "app_started" not in st.session_state:
    st.session_state.app_started = True
    st.session_state.notif_sent_start = False
    st.session_state.last_ping = datetime.now()

# START notif hanya sekali
if not st.session_state.notif_sent_start:
    send_telegram(
        "🟢 <b>ANTAM MONITOR STARTED</b>\n"
        f"MODE: <b>{MODE}</b>\n"
        f"{datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%Y-%m-%d %H:%M:%S")}"
    )
    st.session_state.notif_sent_start = True

# DETEKSI WAKEUP > 30 menit
delta = (datetime.now() - st.session_state.last_ping).seconds
if delta > 1800:
    send_telegram(
        "⚡ <b>ANTAM MONITOR WAKE UP</b>\n"
        f"{datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%Y-%m-%d %H:%M:%S")}"
    )

st.session_state.last_ping = datetime.now()

# =====================
# MAIN CHECK
# =====================
last = load_state()
now = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%Y-%m-%d %H:%M:%S")


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
# GRAFIK CSV (ANTI-CRASH)
# =====================
if os.path.exists(CSV_LOG):
    st.subheader("📊 Riwayat Ketersediaan (1 = HABIS)")
    df = pd.read_csv(CSV_LOG)

    st.caption(f"Kolom CSV terdeteksi: {list(df.columns)}")

    if "status" not in df.columns:
        if "status_num" in df.columns:
            df["status"] = df["status_num"]
        else:
            st.warning("CSV tidak punya kolom status/status_num")
            st.stop()

    if "timestamp" not in df.columns or "gram" not in df.columns:
        st.warning("CSV tidak sesuai format grafik")
        st.stop()

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
# MANUAL BUTTON
# =====================
if st.button("🔄 Refresh Manual"):
    st.experimental_rerun()


