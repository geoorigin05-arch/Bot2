import streamlit as st
import pandas as pd
import os
from pandas.errors import EmptyDataError

st.set_page_config(
    page_title="Antam Dashboard",
    page_icon="🪙",
    layout="wide"
)

st.title("🪙 Antam Gold Stock Dashboard")

CSV_FILE = "stock_log.csv"

# =====================
# VALIDASI FILE
# =====================
if not os.path.exists(CSV_FILE):
    st.warning("📭 stock_log.csv belum ada. Jalankan antam_monitor.py dulu.")
    st.stop()

if os.path.getsize(CSV_FILE) == 0:
    st.warning("📭 stock_log.csv masih kosong. Tunggu monitor menulis data.")
    st.stop()

# =====================
# LOAD CSV (AMAN)
# =====================
try:
    df = pd.read_csv(CSV_FILE)
except EmptyDataError:
    st.warning("📭 CSV belum memiliki kolom. Tunggu 1 siklus monitoring.")
    st.stop()

# =====================
# VALIDASI KOLOM
# =====================
required_cols = {"timestamp", "gram", "status_text", "status_num"}
if not required_cols.issubset(df.columns):
    st.error("❌ Struktur CSV tidak valid.")
    st.write(df.head())
    st.stop()

df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

# =====================
# METRIC
# =====================
col1, col2, col3 = st.columns(3)
col1.metric("Total Log", len(df))
col2.metric("TERSEDIA", (df["status_text"] == "TERSEDIA").sum())
col3.metric("BELUM TERSEDIA", (df["status_text"] == "BELUM TERSEDIA").sum())

# =====================
# FILTER
# =====================
st.divider()
gram = st.selectbox(
    "Filter Gram",
    ["ALL"] + sorted(df["gram"].dropna().unique().tolist())
)

if gram != "ALL":
    df = df[df["gram"] == gram]

# =====================
# CHART
# =====================
st.subheader("📈 Grafik Ketersediaan")

chart = (
    df.groupby("timestamp", as_index=False)["status_num"]
      .sum()
      .sort_values("timestamp")
)

st.line_chart(chart, x="timestamp", y="status_num")

# =====================
# TABLE
# =====================
st.subheader("📜 Log Detail")
st.dataframe(
    df.sort_values("timestamp", ascending=False),
    use_container_width=True
)
