# Hands-On Lab: OpenTelemetry Tracing Pipeline & High-Cardinality Protection

## 1. Deskripsi Lab
Lab praktis ini bertujuan untuk memberikan pengalaman langsung kepada SRE dalam:
- Mengoperasikan OpenTelemetry SDK secara terprogram.
- Melakukan injeksi dan ekstraksi propagasi konteks terdistribusi mengacu pada spesifikasi standar **W3C TraceContext**.
- Membangun mekanisme filter sanitasi atribut untuk mencegah degradasi **High Cardinality TSDB Explosion**.
- Memahami implementasi perekaman **Exemplars** yang mengaitkan metrik histogram ke `trace-id`.

---

## 2. Struktur Direktori
```
hands-on/m01/
├── README.md
└── opentelemetry_tracing_pipeline.py
```

---

## 3. Prasyarat Lingkungan
Pastikan workstation atau server Anda memiliki dependensi berikut:
- Python 3.10 atau versi lebih baru
- `pip` package manager
- Akses terminal/shell Linux, macOS, atau Windows WSL2

---

## 4. Langkah Instalasi

1. Buat virtual environment terisolasi:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. Pasang pustaka resmi OpenTelemetry SDK:
   ```bash
   pip install --upgrade pip
   pip install \
       opentelemetry-api \
       opentelemetry-sdk
   ```

---

## 5. Menjalankan Kode Hands-on

Jalankan skrip pipeline:
```bash
python3 opentelemetry_tracing_pipeline.py
```

---

## 6. Output yang Diharapkan & Analisis Verifikasi

Saat skrip dijalankan, Anda akan melihat serangkaian output logis pada terminal:

### A. Propagasi Header W3C TraceContext
```
[API Gateway] Transaksi Diterima. TraceID: 80f3b4998782a2010839e083cbe9aef6
[API Gateway] Terbentuk W3C Header traceparent: 00-80f3b4998782a2010839e083cbe9aef6-928d1a0e882bf901-01
  [Payment Service] Terkoneksi ke downstream! TraceID: 80f3b4998782a2010839e083cbe9aef6, ParentSpanID: 928d1a0e882bf901
```
*Verifikasi*: Perhatikan bahwa `TraceID` downstream identik dengan API gateway, sedangkan `ParentSpanID` mencerminkan ID milik span pemanggil. Rantai kausalitas tidak terputus.

### B. Proteksi Kardinalitas TSDB
Pada log eksportasi metrik:
```json
{
  "name": "http_server_duration_milliseconds",
  "attributes": {
    "http.method": "POST",
    "http.route": "/api/v1/checkout",
    "http.status_code": 200
  }
}
```
*Verifikasi*: Field berbahaya seperti `user.id`, `credit_card`, dan `user_email` berhasil dieliminasi dari dimensi metrik. Nilai-nilai tersebut aman disimpan hanya di dalam span atribut tracing dengan masking PII aktif:
```json
{
  "attributes": {
    "payment.card_number": "[CARD_MASKED]",
    "user.email": "[REDACTED]"
  }
}
```

---

## 7. Eksperimen Mandiri (Self-Guided Challenge)
1. Buka file `opentelemetry_tracing_pipeline.py` dan ubah fungsi `mock_payment_downstream_service` untuk menyimulasikan kegagalan acak (*random failure*) yang memicu status code HTTP 500.
2. Tambahkan atribut `error=True` pada span dan amati bagaimana status error terekam pada Trace waterfall.
3. Coba matikan proteksi `sanitize_metric_attributes()` dan biarkan `user_id` masuk ke atribut histogram. Amati ledakan dimensi metrik secara teoritis jika simulasi dijalankan untuk 10.000 user yang berbeda.