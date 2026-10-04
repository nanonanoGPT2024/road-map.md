# Panduan Hands-on: Lab 10 - Enterprise Observability, Logpush Pipeline, & SIEM Simulator

Selamat datang di laboratorium praktis Enterprise Observability Cloudflare. Pada lab ini, Anda akan menjalankan simulator ingestion pipeline end-to-end yang mengemulasikan pengiriman telemetri Cloudflare Logpush ke SIEM (Datadog/Splunk), pemrosesan payload terkompresi GZIP, sanitasi record NDJSON, dan deteksi anomali keamanan real-time.

---

## 1. Arsitektur Hands-on

Lab ini mengeksekusi arsitektur terintegrasi dalam skrip `logpush_siem_pipeline_sim.py`:
1. **Ownership Challenge Handler:** Memvalidasi handshake kepemilikan sink sesuai standar verifikasi Cloudflare Logpush API.
2. **GZIP NDJSON Ingestion Engine:** Server HTTP lokal non-blocking yang menerima streaming payload batch terkompresi secara real-time.
3. **Security & Latency Analyzer:** Membedah dataset `firewall_events` dan `http_requests`, memfilter ancaman WAF, serta mendeteksi lonjakan error server (5xx).
4. **Autonomous Emitter:** Mengemulasikan node edge global Cloudflare yang memancarkan log secara berkala.

---

## 2. Persyaratan Sistem
* Python versi 3.8 atau lebih baru.
* `curl` (opsional, untuk pengujian handshake manual).
* Tidak memerlukan dependensi library pihak ketiga (hanya pustaka standar Python).

---

## 3. Langkah-Langkah Menjalankan Lab

### Langkah 1: Verifikasi File Skrip
Pastikan file skrip simulator telah memiliki izin eksekusi:
```bash
chmod +x hands-on/m01/logpush_siem_pipeline_sim.py
cd hands-on/m01
```

### Langkah 2: Menjalankan Pipeline Simulator
Eksekusi simulator secara langsung menggunakan Python 3:
```bash
python3 logpush_siem_pipeline_sim.py
```

### Langkah 3: Mengamati Output Telemetri Real-Time
Perhatikan log interaktif pada terminal Anda:
1. **SINK-CHALLENGE:** Mengonfirmasi bahwa Cloudflare berhasil memverifikasi endpoint sink.
2. **SIEM-ALERT-WAF:** Muncul saat simulator mendeteksi aksi mitigasi WAF (`block`, `challenge`) lengkap dengan Attacker IP dan RayID.
3. **SIEM-ALERT-5XX:** Muncul saat origin gateway mengalami HTTP error 500-504 dengan rekaman durasi latency.
4. **DASHBOARD SUMMARY:** Menampilkan ringkasan metrik akhir termasuk rasio ancaman, volume payload terkompresi, dan rata-rata performa origin.

---

## 4. Eksperimen Lanjutan Mandiri (Uji Coba Eksternal)

Sambil skrip simulator berjalan, buka terminal kedua untuk menguji penerimaan secara manual menggunakan `curl`:

### A. Uji Ownership Challenge
```bash
curl -i "http://127.0.0.1:8888/logpush/ownership?challenge=token-verifikasi-enterprise-999"
```
**Ekspektasi Output:** HTTP `200 OK` dengan payload JSON berisi token validasi.

### B. Uji Ingestion Payload NDJSON Manual
```bash
# Buat file NDJSON sederhana
echo '{"RayID":"manual-test-ray-001","ClientIP":"192.168.1.10","EdgeResponseStatus":503,"ClientRequestURI":"/api/v1/payment"}' > test.ndjson

# Kirimkan data ke receiver
curl -i -X POST "http://127.0.0.1:8888/api/v2/logs" \
     -H "Content-Type: application/x-ndjson" \
     --data-binary @test.ndjson

# Bersihkan file uji
rm test.ndjson
```
**Ekspektasi Output:** Terminal simulator akan langsung mendeteksi alert `SIEM-ALERT-5XX` untuk `manual-test-ray-001`.

---

## 5. Kriteria Keberhasilan Hands-on
* Seluruh 5 batch pengujian terkirim dan diproses tanpa error `Corrupted GZIP stream`.
* Dashboard akhir memunculkan statistik metrik dengan status `OPERATIONAL / HEALTHY`.
* Peserta didik memahami siklus hidup data: dari request client di edge, pembentukan file NDJSON, kompresi GZIP, hingga korelasi ancaman di SIEM.