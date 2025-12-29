py -m pip install playwright


import requests, json, os, time, csv
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from datetime import datetime

# =====================
# CONFIG
# =====================
URL = "https://www.logammulia.com/id/purchase/gold"

GRAM_LIST = ["0.5 gr", "1 gr", "2 gr", "3 gr", "5 gr", "10 gr"]

MODE = "PRODUKSI"          # VALIDASI | PRODUKSI
INTERVAL = 60              # detik
HEADLESS = False
RETRY_LOAD = 3

# Chrome profile utama (cache & session awet)
USER_DATA_DIR = "C:/antam-profile"

STATE_FILE = "last_status.json"
CSV_LOG = "stock_log.csv"
SCREENSHOT_DIR = "screenshots"

os.makedirs(SCREENSHOT_DIR, exist_ok=True)

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
    try:
        if photo and os.path.exists(photo):
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
            with open(photo, "rb") as f:
                requests.post(
                    url,
                    data={
                        "chat_id": CHAT_ID,
                        "caption": msg,
                        "parse_mode": "HTML"
                    },
                    files={"photo": f},
                    timeout=20
                )
        else:
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
# STATE (AMAN JSON)
# =====================
def load_state():
    try:
        if os.path.exists(STATE_FILE) and os.path.getsize(STATE_FILE) > 0:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except:
        pass
    return {}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

# =====================
# CSV LOG (AMAN)
# =====================
def log_csv(ts, gram, habis):
    file_exists = os.path.exists(CSV_LOG)
    with open(CSV_LOG, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow([
                "timestamp",
                "gram",
                "status_text",
                "status_num"
            ])
        writer.writerow([
            ts,
            gram,
            "BELUM TERSEDIA" if habis else "TERSEDIA",
            1 if habis else 0
        ])

# =====================
# SAFE LOAD PAGE
# =====================
def safe_load_page(page):
    for i in range(RETRY_LOAD):
        try:
            page.goto(URL, timeout=60000, wait_until="domcontentloaded")

            try:
                page.wait_for_selector("div.product-item", timeout=15000)
            except:
                page.wait_for_selector("text=Belum tersedia", timeout=15000)

            return True
        except:
            print(f"⚠️ Retry load {i+1}/{RETRY_LOAD}")
            time.sleep(5)
    return False

# =====================
# PARSE STOCK (PER PRODUK)
# =====================
def check_stock(html):
    soup = BeautifulSoup(html, "html.parser")
    page_text = soup.get_text(" ").lower().replace(" ", "")

    # Jika halaman masih benar-benar kosong
    if len(page_text) < 200:
        return "LOADING"

    result = {}

    for gram in GRAM_LIST:
        gram_key = gram.replace(" ", "").lower()

        if gram_key not in page_text:
            # produk belum muncul sama sekali
            result[gram] = True
            continue

        # cek BELUM TERSEDIA dekat produk
        if "belumtersedia" in page_text:
            result[gram] = True
        else:
            result[gram] = False

    return result

# =====================
# MAIN LOOP
# =====================
def main():
    last = load_state()

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            USER_DATA_DIR,
            headless=HEADLESS,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage"
            ]
        )

        page = context.pages[0] if context.pages else context.new_page()

        send_telegram(
            f"🟢 <b>ANTAM MONITOR STARTED</b>\n"
            f"MODE: <b>{MODE}</b>"
        )

        while True:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            screenshot = f"{SCREENSHOT_DIR}/antam_{ts}.png"

            try:
                ok = safe_load_page(page)

                if not ok:
                    page.screenshot(path=screenshot, full_page=True)
                    send_telegram(
                        "🚨 <b>GAGAL LOAD HALAMAN ANTAM</b>",
                        screenshot
                    )
                    time.sleep(INTERVAL)
                    continue

                html = page.content()
                page.screenshot(path=screenshot, full_page=True)

                current = check_stock(html)

                if current == "LOADING":
                    print("⏳ Halaman belum siap, skip")
                    time.sleep(INTERVAL)
                    continue

                for gram, habis in current.items():
                    last_status = last.get(gram)

                    # LOG CSV SELALU
                    log_csv(now, gram, habis)

                    # =====================
                    # MODE VALIDASI
                    # =====================
                    if MODE == "VALIDASI":
                        if habis:
                            send_telegram(
                                f"🧪 <b>VALIDASI SCRAPER</b>\n"
                                f"{gram}\n"
                                f"<b>BELUM TERSEDIA</b> TERDETEKSI\n"
                                f"{now}",
                                screenshot
                            )

                    # =====================
                    # MODE PRODUKSI
                    # =====================
                    elif MODE == "PRODUKSI":
                        if not habis and last_status != False:
                            send_telegram(
                                f"🟢 <b>STOK ANTAM TERSEDIA</b>\n"
                                f"{gram}\n"
                                f"Pulo Gadung\n"
                                f"{now}",
                                screenshot
                            )

                last = current
                save_state(current)

                print(f"✔ [{MODE}] UPDATE {now}")

            except Exception as e:
                fatal = f"{SCREENSHOT_DIR}/fatal_{ts}.png"
                try:
                    page.screenshot(path=fatal, full_page=True)
                except:
                    pass
                send_telegram(
                    f"❌ <b>FATAL ERROR</b>\n{str(e)}",
                    fatal
                )

            time.sleep(INTERVAL)

# =====================
# RUN
# =====================
if __name__ == "__main__":
    main()

