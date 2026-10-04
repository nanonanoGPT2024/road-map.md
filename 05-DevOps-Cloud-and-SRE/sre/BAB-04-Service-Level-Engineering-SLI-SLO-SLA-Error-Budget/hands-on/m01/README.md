# Hands-On Lab M01: Multi-Window Multi-Burn-Rate SLO Engine

Lab praktikum ini mengimplementasikan logika komputasi matematis standar **Google SRE Chapter 5** untuk penghitungan Service Level Indicator (SLI), Service Level Objective (SLO), Error Budget, dan Alerting berbasis Multi-Window Multi-Burn-Rate.

---

## 1. Prasyarat Sistem
- Python 3.8 atau versi yang lebih tinggi terpasang di sistem.
- Tidak memerlukan external package dependency (menggunakan standar pustaka Python murni: `typing`, `dataclasses`, `json`, `time`, `sys`).

---

## 2. Struktur Berkas
- `multi_burn_rate_slo_engine.py`: Skrip inti implementasi engine kalkulasi SLO dan burn rate.

---

## 3. Langkah Menjalankan Hands-On

### Langkah 1: Verifikasi Lingkungan
Pastikan environment Python Anda siap:
```bash
python3 --version
```

### Langkah 2: Jalankan Simulasi Engine
Jalankan skrip engine langsung melalui terminal:
```bash
python3 multi_burn_rate_slo_engine.py
```

### Langkah 3: Amati Hasil Simulasi Terminal
Program akan mensimulasikan 3 fase siklus operasional layanan:
1. **Fase Normal (60 Menit):**
   - Layanan memproses $10.000\text{ request/menit}$ dengan error rate sangat rendah ($0.02\%$).
   - Tidak ada alert yang terpicu.
2. **Fase Anomali Spike (15 Menit):**
   - Terjadi degradasi sistemik dengan error rate $2\%$ ($200\text{ error/menit}$).
   - Karena target SLO adalah $99.9\%$ (toleransi error $0.1\%$), laju pembakaran mencapai $20\text{x}$ lipat.
   - Pager Alert `1h-5m-HighBurn` (Severity: PAGE) terpicu karena Long Window ($1\text{h}$) dan Short Window ($5\text{m}$) melampaui batas $14.4$.
   - Output JSON menampilkan persentase Error Budget yang terkuras drastis.
3. **Fase Pemulihan (Self-Healing / Recovery):**
   - Error rate kembali turun menjadi normal ($0.01\%$).
   - Meskipun Long Window ($1\text{h}$) masih mencatat riwayat error tinggi ($BR > 14.4$), alert **otomatis berhenti memicu pager** karena Short Window ($5\text{m}$) sudah bersih ($BR < 14.4$).
   - Ini membuktikan keunggulan arsitektur multi-window dalam mencegah *alert flapping/fatigue*.

---

## 4. Eksperimen Mandiri (Code Modification)
Buka berkas `multi_burn_rate_slo_engine.py` dan lakukan modifikasi berikut untuk pendalaman:
1. **Ubah Target SLO:** Ganti `target_slo=99.9` menjadi `target_slo=99.99` pada baris inisialisasi di fungsi `run_demonstration()`. Amati bagaimana Error Budget terkuras habis secara instan saat terjadi anomali.
2. **Tambah Window Baru:** Tambahkan konfigurasi `WindowConfig` baru untuk severity `TICKET` dengan long window 12 jam dan burn rate 4.5.
3. **Eksplorasi Guard Condition:** Tambahkan pengecekan `traffic_volume` minimum sebelum alert dipicu untuk mencegah false alarm pada kondisi low-traffic.