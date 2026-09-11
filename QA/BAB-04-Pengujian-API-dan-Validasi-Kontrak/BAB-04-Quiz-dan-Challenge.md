---
[⬅️ Module 02: JSON Schema & Contract Testing](./Module-02-Otomasi-API-JSON-Schema-Validation-Mocking.md) | [📋 Silabus Induk](../README.md) | [BAB 05: Fondasi Otomasi Pengujian ➡️](../BAB-05-Fondasi-Otomasi-Pengujian-dan-Pemrograman/Module-01-JavaScript-TypeScript-untuk-QA-Async-Assertions.md)
---

# BAB 04: Quiz, Evaluasi, & Practical Challenge

## 1. Chapter Summary & Evaluasi Pemahaman
Pada BAB 04, Anda telah menguasai domain penting pengujian API pada lapisan tengah piramida:
1. **Anatomi HTTP**: Membedakan peran Method/Verb, Path/Query parameters, Request Headers, dan Request/Response Body.
2. **Kepatuhan Status Code**: Memahami spektrum 2xx, 3xx, 4xx (Client error: 400, 401, 403, 404, 409, 422, 429), dan 5xx (Server error: 500, 502, 503, 504), serta menolak anti-pattern *False 200 OK*.
3. **Idempotensi HTTP**: Menjamin bahwa metode idempoten (`GET`, `PUT`, `DELETE`) aman diulang, dan metode non-idempoten (`POST`) dilindungi oleh header `Idempotency-Key` untuk mencegah transaksi ganda.
4. **JSON Schema Validation**: Memvalidasi integritas tipe data, field wajib, dan batasan nilai secara deklaratif guna mencegah *Schema Drift*.
5. **Contract Testing & Pact**: Mengisolasi integrasi microservices dengan pengujian kontrak berbasis kebutuhan konsumen (*Consumer-Driven Contracts*).
6. **API Security & Rate Limiting**: Memverifikasi ketahanan terhadap celah BOLA (IDOR) dan memverifikasi batas kuota pemanggilan (HTTP 429).

---

## 2. Interactive Quiz

### Bagian A: Basic Questions (Konseptual Fundamental)
1. **Pertanyaan 1**: Apa perbedaan antara **401 Unauthorized** dan **403 Forbidden**? Berikan contoh kasus nyata yang membedakan keduanya!
2. **Pertanyaan 2**: Mengapa metode HTTP `PUT` dikatakan idempoten, sedangkan metode `POST` dikatakan tidak idempoten?
3. **Pertanyaan 3**: Apa bahaya anti-pattern *False 200 OK* (server membalas status HTTP 200 tetapi di dalam body tertulis `{"status": "error"}`) terhadap sistem pemantauan otomatis (*Observability*)?
4. **Pertanyaan 4**: Apa fungsi kata kunci `"additionalProperties": false` di dalam dokumen JSON Schema?
5. **Pertanyaan 5**: Apa yang dimaksud dengan **Consumer-Driven Contract Testing (CDC)** dan masalah apa dalam arsitektur Microservices yang diselesaikannya?

### Bagian B: Intermediate Questions (Analisis & Desain Uji)
6. **Pertanyaan 6**: Jelaskan alur kerja pengujian header **`Idempotency-Key`** pada endpoint transaksi pembayaran kartu kredit untuk mencegah nasabah terdebit dua kali saat koneksi internet terputus!
7. **Pertanyaan 7**: Sebuah API merespons permintaan dengan status HTTP 429. Sebutkan header standar apa yang wajib disertakan oleh server dalam respon tersebut untuk memandu klien kapan boleh mencoba kembali?
8. **Pertanyaan 8**: Jelaskan apa itu kerentanan **Broken Object Level Authorization (BOLA / IDOR)** pada endpoint REST API dan bagaimana seorang QA dapat mereproduksinya secara otomatis dalam test script!
9. **Pertanyaan 9**: Kapan seorang QA harus memilih menguji menggunakan **Mock Server / Service Virtualization** dibandingkan memanggil server sandbox pihak ketiga secara nyata?
10. **Pertanyaan 10**: Apa perbedaan tujuan pengujian antara memvalidasi query parameter `GET /products?page=2&limit=20` dan path parameter `GET /products/PROD-102`?

### Bagian C: Scenario-Based Questions (Problem Solving Dunia Nyata)
11. **Skenario 1**: Tim mobile banking merilis versi aplikasi Android terbaru. Namun begitu aplikasi dibuka oleh nasabah, terjadi force close massal. Setelah diinvestigasi, backend mengubah format tanggal dari string ISO-8601 (`"2026-09-11T15:00:00Z"`) menjadi integer Unix timestamp (`1789138800`). Mengapa pengujian unit test di backend gagal menangkap isu ini, dan bagaimana strategi JSON Schema di pipeline CI/CD dapat mencegahnya?
12. **Skenario 2**: Anda sedang menguji endpoint registrasi pengguna: `POST /api/v1/auth/register`. Jika pendaftaran dikirimkan dengan email yang sudah terdaftar sebelumnya di database, status code HTTP manakah yang paling tepat menurut standar RFC? Mengapa bukan 400 Bad Request atau 500 Server Error?
13. **Skenario 3**: Sebuah merchant e-commerce diserang bot yang melakukan scraping harga produk 500 kali per detik, menyebabkan database kehabisan koneksi (*Connection Pool Exhausted*). Sebagai QA Engineer, bagaimana Anda merancang skenario pengujian untuk memvalidasi fitur Rate Limiter dan Circuit Breaker API Gateway?

---

## 3. Chapter Challenge: Perancangan Test Suite API Layanan E-Wallet

### Deskripsi Skenario
Sebuah startup fintech bernama **"DompetKilat"** sedang mengembangkan API microservice baru untuk transaksi transfer saldo dompet digital:
- **Endpoint**: `POST /api/v1/wallets/transfer`
- **Request Headers Wajib**:
  - `Authorization: Bearer <JWT_TOKEN>`
  - `Content-Type: application/json`
  - `Idempotency-Key: <UUID>`
- **Request Body JSON**:
  ```json
  {
    "recipientWalletId": "WAL-9901",
    "amount": 50000,
    "currency": "IDR",
    "notes": "Bayar kopi"
  }
  ```
- **Aturan Bisnis & Batasan**:
  - `amount` minimal Rp 10.000 dan maksimal Rp 10.000.000 per transaksi.
  - `currency` harus bernilai "IDR".
  - Saldo pengirim harus mencukupi.
  - Rate limit transaksi: maksimal 2 transfer per menit per pengguna.

### Tugas Anda (Deliverables):
1. **JSON Schema Specification**:
   Tuliskan dokumen JSON Schema lengkap (Draft-07) untuk memvalidasi respon sukses (`201 Created`) yang mengembalikan field: `transferId`, `status`, `amount`, `fee`, `remainingBalance`, dan `timestamp`.
2. **Matriks Skenario Uji API Fungsional & Status Code**:
   Susun tabel skenario uji lengkap yang mencakup minimal 6 kasus (1 Happy path 201, 1 Token invalid 401, 1 Saldo kurang 422, 1 Penerima tidak ditemukan 404, 1 Duplikasi Idempotency-Key 200, dan 1 Rate limit exceeded 429).
3. **Skenario Pengujian Penetrasi BOLA (IDOR)**:
   Jelaskan langkah-langkah detail untuk membuktikan bahwa User A tidak dapat memanipulasi request agar saldo terdebit dari dompet milik User B.

---

## 4. Knowledge Check & Mastery Checklist

### Saya Harus Memahami:
- [ ] Anatomi protokol HTTP (Verbs, Headers, Body, Parameters).
- [ ] Arti dan penggunaan semantik seluruh kategori status code (2xx, 3xx, 4xx, 5xx).
- [ ] Konsep Idempotensi pada metode HTTP dan implementasi header `Idempotency-Key`.
- [ ] Cara menulis dan mengevaluasi JSON Schema draft standar.
- [ ] Konsep Consumer-Driven Contract Testing (Pact).
- [ ] Pola pengujian keamanan API dasar (BOLA/IDOR dan Rate Limiting).

### Saya Tidak Perlu Menghafal:
- [ ] Semua 60+ kode status HTTP yang jarang digunakan (cukup kode-kode inti 200, 201, 204, 400, 401, 403, 404, 409, 422, 429, 500, 502, 503, 504).
- [ ] Sintaks JSON Schema meta-schema internal.

### Saya Harus Bisa Melakukan:
- [ ] Menulis test runner otomatis untuk memvalidasi endpoint API tanpa dependensi pihak ketiga.
- [ ] Mendeteksi bug *False 200 OK* pada layanan backend.
- [ ] Menguji ketahanan rate limiter dengan mengirimkan lonjakan request cepat.

---
[⬅️ Module 02: JSON Schema & Contract Testing](./Module-02-Otomasi-API-JSON-Schema-Validation-Mocking.md) | [📋 Silabus Induk](../README.md) | [BAB 05: Fondasi Otomasi Pengujian ➡️](../BAB-05-Fondasi-Otomasi-Pengujian-dan-Pemrograman/Module-01-JavaScript-TypeScript-untuk-QA-Async-Assertions.md)
---
