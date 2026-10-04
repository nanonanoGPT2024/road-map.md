# Hands-On Lab: Cloudflare WAF, Managed Rulesets, & Rate Limiting Simulation

## 1. Deskripsi Lab
Lab ini menyediakan lingkungan simulasi mandiri (*standalone environment*) berbasis Python untuk membedah internal pipeline evaluasi **Cloudflare Ruleset Engine v2**, mencakup **Custom Expression Rules**, **Bot Management Score**, **Advanced Rate Limiting**, dan **OWASP Core Ruleset (CRS) Anomaly Scoring Engine**.

Tidak diperlukan akun Cloudflare Enterprise aktif untuk memvalidasi logika inspeksi; seluruh evaluasi regex, transformasi payload, dan sliding window rate-limiting dieksekusi secara lokal persis seperti cara kerja Cloudflare Edge Anycast.

---

## 2. Struktur Lab
```text
hands-on/m01/
├── README.md                     # Panduan operasional lab
└── cloudflare_waf_rules_sim.py   # Engine simulator & runnable test suite
```

---

## 3. Prasyarat Sistem
- Python versi `3.8` atau yang lebih baru.
- Terminal Linux / macOS / WSL2 (Windows).
- Tidak ada dependensi pustaka pihak ketiga eksternal (menggunakan modul murni Python Standard Library: `re`, `time`, `urllib`, `dataclasses`, `json`).

---

## 4. Langkah Pengujian & Instruksi Eksekusi

### Langkah 1: Verifikasi File Skrip
Pastikan izin eksekusi skrip telah aktif:
```bash
cd hands-on/m01/
chmod +x cloudflare_waf_rules_sim.py
```

### Langkah 2: Jalankan Simulasi Baseline
Jalankan simulator untuk memverifikasi evaluasi aturan bawaan:
```bash
python3 cloudflare_waf_rules_sim.py
```

### Langkah 3: Analisis Output
Perhatikan bagaimana simulator memproses request secara berurutan sesuai fase (*phases*):
1. **Test Case #1:** Request legitimate GET lolos seluruh fase dengan skor anomali 0.
2. **Test Case #2:** Request ke `/admin/dashboard` dicegat di fase `http_request_firewall_custom` dengan HTTP 403 karena IP tidak terdaftar pada CIDR internal.
3. **Test Case #3:** Request POST melebihi batas buffer 128KB pada auth route dicegat dengan HTTP 413.
4. **Test Case #4:** Payload SQL Injection memicu Rule OWASP `942100` pada Paranoia Level 1.
5. **Test Case #5:** Payload Log4Shell (`${jndi:ldap...}`) di dalam header memicu rule OWASP `944100` dan skor bot rendah, dicegat secara instan.
6. **Rate Limiting Burst:** Hit ke 1-5 diizinkan; hit ke-6 langsung dicegat dengan HTTP 429 dan status isolasi aktif.

---

## 5. Eksperimen Hands-On Mandiri

### Eksperimen A: Menyetel Paranoia Level & Threshold
Buka file `cloudflare_waf_rules_sim.py` menggunakan text editor favorit Anda, cari baris inisialisasi:
```python
waf = CloudflareWAFSimulator(paranoia_level=2, anomaly_threshold=25)
```
1. Ubah parameter `paranoia_level=1`.
2. Jalankan ulang script. Amati apakah pengujian directory traversal (`../../../../etc/passwd`) pada Test Case #6 masih terdeteksi atau lolos!
3. Naikkan parameter `anomaly_threshold=60` (Low Sensitivity). Amati apakah payload SQL injection pada Test Case #4 sekarang diizinkan lolos atau tetap diblokir.

### Eksperimen B: Menambahkan Custom Expression Rule Baru
Tambahkan aturan baru pada metode `evaluate()` di dalam blok `PHASE 1: CUSTOM RULES`:
- **Skenario:** Blokir setiap request HTTP method `PUT` atau `DELETE` yang mengakses rute berawalan `/api/v1/public/` tanpa menyertakan header otentikasi `Authorization`.
```python
if request.method in ["PUT", "DELETE"] and normalized_path.startswith("/api/v1/public/"):
    if "Authorization" not in request.headers:
        result.allowed = False
        result.status_code = 401
        result.phase_terminated = "http_request_firewall_custom"
        result.action_taken = "block"
        result.triggered_rules.append("CR_003_UNAUTHORIZED_MUTATION")
        result.details["reason"] = "Mutasi publik wajib menyertakan Authorization header."
        return result
```
Uji aturan baru tersebut dengan menambahkan objek `HTTPRequest` baru ke array `test_cases`.

---

## 6. Validasi & Troubleshooting
- **Error: `ModuleNotFoundError`:** Pastikan Anda menggunakan runtime Python 3 standard:
  ```bash
  python3 --version
  ```
- **False Negative pada OWASP Engine:** Pastikan string regex mencakup flag case-insensitive `(?i)` dan variabel payload telah melalui pembersihan `urllib.parse.unquote()` untuk mencegah bypass enkripsi URL.