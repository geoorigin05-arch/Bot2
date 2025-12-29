notif_sent = False
for gram, habis in current.items():
    last_status = last.get(gram)
    log_csv(now, gram, habis)

    if MODE == "PRODUKSI":
        # Kirim notif hanya jika stok tersedia baru
        if not habis and last_status is not False:
            send_telegram(
                f"🟢 <b>STOK ANTAM TERSEDIA</b>\n"
                f"{gram}\n"
                f"{now}"
            )
            notif_sent = True

    elif MODE == "VALIDASI":
        # Kirim notif untuk tiap gram, tanpa cek status sebelumnya
        send_telegram(
            f"🧪 <b>VALIDASI SCRAPER</b>\n"
            f"{gram}\n"
            f"{'HABIS' if habis else 'TERSEDIA'}\n"
            f"{now}"
        )
        notif_sent = True
