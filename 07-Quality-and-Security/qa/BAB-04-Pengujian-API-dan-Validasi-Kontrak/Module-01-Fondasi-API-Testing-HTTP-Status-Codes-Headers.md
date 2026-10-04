---
[⬅️ BAB 03: Quiz & Challenge](../BAB-03-Teknik-Perancangan-Test-Case-Black-Box-White-Box/BAB-03-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: JSON Schema & Contract Testing ➡️](./Module-02-Otomasi-API-JSON-Schema-Validation-Mocking.md)
---

# Module 01: Fondasi API Testing: Anatomi HTTP, Status Codes, Headers, & Idempotensi

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- Memahami peran krusial **Application Programming Interface (API) Testing** di lapisan tengah piramida pengujian (*Integration / Service Layer*).
- Menguasai anatomi lengkap dari transaksi HTTP: **HTTP Methods/Verbs**, **Request Headers**, **Path Parameters**, **Query Parameters**, **Request Body**, dan **Response Body**.
- Menganalisis dan menguji spektrum kode status HTTP standar RFC 9110: **2xx Success**, **3xx Redirection**, **4xx Client Error** (termasuk 400, 401, 403, 404, 409, 422, 429), dan **5xx Server Error** (500, 502, 503, 504).
- Menguji konsep **Idempotency** (metode yang aman diulang tanpa mengubah status akhir: `GET`, `PUT`, `DELETE`, `HEAD`, `OPTIONS`) versus metode non-idempoten (`POST`, `PATCH`).
- Merancang test suite pengujian fungsional API yang memverifikasi kepatuhan payload, response time (SLA latency), dan format otentikasi Bearer Token.

---

## 2. Prerequisite
- Memahami konsep dasar tingkat pengujian (Unit vs Integration vs System) dari BAB 02.
- Pemahaman dasar tentang format data **JSON** (JavaScript Object Notation: objek, array, string, number, boolean).

---

## 3. Concept
Dalam arsitektur modern (Microservices, Single Page Applications, Mobile Apps), antarmuka grafis (UI) hanyalah lapisan tipis (*thin client*) yang menampilkan data. Otak bisnis, pengolahan data, transaksi finansial, dan basis data dioperasikan melalui **Application Programming Interface (API)**, umumnya menggunakan arsitektur RESTful melalui protokol HTTP/HTTPS.

**API Testing** adalah pengujian perangkat lunak yang berfokus langsung pada lapisan logika bisnis (*business logic layer*), mengabaikan tampilan visual antarmuka pengguna. Pengujian API memeriksa apakah data yang dikirim dan diterima sesuai spesifikasi kontrak, apakah status code yang dikembalikan akurat, bagaimana sistem merespon masukan salah, dan apakah waktu respon berada dalam batas toleransi SLA (*Service Level Agreement*).

---

## 4. Why?
Mengapa API Testing menjadi keterampilan wajib bagi QA modern?
1. **Kecepatan dan Stabilitas Tinggi**: Berbeda dengan UI testing yang lambat dan sering gagal palsu karena perubahan tata letak halaman (*selector flakiness*), API test beroperasi murni pada data transfer, berjalan dalam hitungan milidetik, dan sangat deterministik.
2. **Penerapan Nyata Shift-Left Testing**: Pengujian API dapat dimulai segera setelah spesifikasi endpoint (OpenAPI / Swagger) disepakati, bahkan sebelum tim frontend selesai membuat tombol atau halaman web.
3. **Mendeteksi Bug Keamanan yang Tersembunyi dari UI**: Validasi form di sisi frontend (misal: membatasi input umur 18+) sangat mudah dibobol oleh peretas menggunakan cURL atau Postman. Pengujian API memverifikasi bahwa backend memiliki validasi mandiri yang kokoh.

---

## 5. What?

### A. Anatomi Permintaan dan Respon HTTP (HTTP Request & Response)

```text
========================================================================================
                          HTTP REQUEST STRUCTURE
========================================================================================
 POST /api/v1/orders?promo=HEMAT20 HTTP/1.1       <-- Request Line (Method, Path, Query)
 Host: api.ecommerce.com                          <-- Request Headers
 Authorization: Bearer eyJhbGciOiJIUzI1Ni...
 Content-Type: application/json
 Accept: application/json
 
 {                                                <-- Request Body (Payload JSON)
   "productId": "PROD-9982",
   "quantity": 2,
   "paymentMethod": "BCA_VA"
 }

========================================================================================
                          HTTP RESPONSE STRUCTURE
========================================================================================
 HTTP/1.1 201 Created                             <-- Status Line (Protocol, Status Code)
 Content-Type: application/json                   <-- Response Headers
 X-Response-Time: 42ms
 
 {                                                <-- Response Body
   "orderId": "ORD-202609-8812",
   "status": "PENDING_PAYMENT",
   "totalAmount": 250000,
   "createdAt": "2026-09-11T15:30:00Z"
 }
```

---

### B. Taksonomi Kode Status HTTP untuk QA

| Kategori | Kode & Nama | Makna Bisnis & Ekspektasi QA | Kapan Diharapkan? |
|---|---|---|---|
| **2xx (Success)** | **200 OK** | Permintaan sukses dan menghasilkan respon data. | `GET` data sukses, `PUT`/`PATCH` perbaikan sukses. |
| | **201 Created** | Sumber daya (*resource*) baru berhasil dibuat di database. | `POST` pembuatan data pengguna / transaksi baru. |
| | **204 No Content** | Operasi sukses, namun server sengaja tidak mengembalikan body. | `DELETE` data sukses. |
| **3xx (Redirection)**| **301 Moved Permanently** | URL lama dialihkan permanen ke URL baru. | Migrasi versi endpoint API lama ke API baru. |
| | **304 Not Modified** | Data di server belum berubah sejak request terakhir (Cache). | Menghemat bandwidth menggunakan header `ETag` / `If-None-Match`. |
| **4xx (Client Error)**| **400 Bad Request** | Format payload JSON rusak, sintaks invalid, atau tipe data salah. | Mengirim string pada field yang mewajibkan integer. |
| | **401 Unauthorized** | Pengguna belum terautentikasi (Token JWT hilang/kedaluwarsa). | Request tanpa header `Authorization`. |
| | **403 Forbidden** | Terotentikasi, namun role pengguna dilarang mengakses data ini. | Pengguna biasa mencoba mengakses endpoint Admin. |
| | **404 Not Found** | Resource atau ID yang diminta tidak ada di database. | `GET /api/v1/users/999999` (ID fiktif). |
| | **409 Conflict** | Terjadi tabrakan status (misal: duplikasi data unik). | Mendaftar akun dengan email yang sudah terdaftar. |
| | **422 Unprocessable Entity** | JSON valid, namun aturan validasi bisnis gagal. | Umur bernilai negatif, format nomor telepon salah. |
| | **429 Too Many Requests** | Klien melebihi batas kuota pemanggilan (*Rate Limiting*). | Melakukan 100 request dalam 1 detik. |
| **5xx (Server Error)**| **500 Internal Server Error** | Cacat program backend! Exception tidak tertangani (*Unhandled*). | Bug kritis! Harus dilaporkan ke developer. |
| | **502 Bad Gateway** | Reverse proxy (Nginx) gagal menghubungi worker service backend. | Service backend crash atau mati. |
| | **503 Service Unavailable**| Server sedang kelebihan beban atau maintenance terjadwal. | Downtime terencana atau server throttling. |
| | **504 Gateway Timeout** | Service backend butuh waktu terlalu lama untuk menjawab proxy. | Query SQL macet atau bottleneck database. |

---

### C. Idempotensi Metode HTTP (HTTP Idempotency)
Sebuah metode HTTP dikatakan **Idempoten** jika memanggil request tersebut 1 kali menghasilkan status akhir di server yang persis sama dengan memanggil request tersebut 100 kali berturut-turut.

| HTTP Method | Idempoten? | Aman (Safe)? | Penjelasan Teknis |
|---|---|---|---|
| **GET** | **YA** | **YA** | Hanya membaca data (*Read-Only*). Berulang kali dipanggil tidak mengubah data server. |
| **PUT** | **YA** | TIDAK | Mengganti (*Replace*) seluruh objek. Memperbarui status ke "ACTIVE" 100 kali hasilnya tetap "ACTIVE". |
| **DELETE** | **YA** | TIDAK | Menghapus objek ID 10. Penghapusan pertama berhasil; panggilan berikutnya tetap memastikan objek ID 10 terhapus (atau mengembalikan 404). Status akhir server identik. |
| **POST** | **TIDAK** | TIDAK | Membuat objek baru. Memanggil 5 kali akan membuat 5 record baru di database (atau duplikasi pembayaran jika tidak dilindungi *Idempotency-Key*). |
| **PATCH** | **TIDAK** | TIDAK | Memodifikasi sebagian data (*Partial Update*). Contoh: `{ $inc: { balance: 100 } }` jika dipanggil 2 kali akan menambah saldo 200 (tidak idempoten). |

---

## 6. How? Strategi Merancang Skenario Pengujian API (API Test Design)

Untuk setiap endpoint REST API, QA wajib merancang 4 kategori pengujian:

1. **Happy Path (Positive Testing)**:
   - Mengirimkan data payload lengkap dan valid.
   - Verifikasi Status Code: 200 OK atau 201 Created.
   - Verifikasi Response Body: Semua field penting terisi, tipe data sesuai kontrak.
2. **Negative Testing (Boundary & Bad Input)**:
   - Mengosongkan field wajib (*Required Field Missing*) -> Ekspektasi: 400 Bad Request atau 422 Unprocessable Entity.
   - Mengirim tipe data salah (string di field angka) -> Ekspektasi: 400 Bad Request.
   - Mengirim ID yang tidak ada di database -> Ekspektasi: 404 Not Found.
3. **Security & Authorization Testing**:
   - Request tanpa Bearer Token -> Ekspektasi: 401 Unauthorized.
   - Request dengan Token yang diubah 1 karakter -> Ekspektasi: 401 Unauthorized.
   - Request menggunakan token Member Biasa ke endpoint `/admin/settings` -> Ekspektasi: 403 Forbidden.
4. **Performance / SLA Testing**:
   - Memverifikasi response header atau durasi waktu request tidak melebihi batas toleransi SLA (misal: $\le 200$ ms).

---

## 7. Analogy
Bayangkan memesan makanan di kasir restoran cepat saji:
- **Endpoint**: Loket pemesanan makanan (`/pesan-makanan`).
- **HTTP Method**:
  - `GET`: Anda melihat daftar menu di papan harga (hanya membaca, tidak memesan).
  - `POST`: Anda memesan 1 paket burger (menciptakan pesanan baru di dapur).
  - `DELETE`: Anda membatalkan pesanan sebelum dimasak.
- **Header**: Kartu identitas member restoran yang Anda tunjukkan (`Authorization: Bearer Member123`).
- **Status Codes**:
  - `200/201`: Burger berhasil dimasak dan diserahkan ke nampan Anda.
  - `400`: Anda memesan menu yang tidak masuk akal ("Pesan es teh hangat rasa bensin").
  - `401`: Anda mengaku anggota VIP tapi tidak bisa menunjukkan kartu member.
  - `404`: Anda memesan menu yang sudah dihapus dari katalog 5 tahun lalu.
  - `500`: Kompor dapur restoran meledak dan koki pingsan (kesalahan internal pihak restoran).

---

## 8. Diagram

```text
========================================================================================
                          API TESTING VERIFICATION MATRIX
========================================================================================

                 [ QA Client (cURL / Test Script / Runner) ]
                                      |
                                      | HTTP Request (Method + Path + Headers + Body)
                                      v
                             [ API Gateway / Router ]
                                      |
         +----------------------------+----------------------------+
         |                                                         |
  (Token Hilang/Salah)                                     (Token Valid)
         v                                                         v
   [ 401 Unauthorized ]                                    [ Business Logic Service ]
                                                                   |
                                              +--------------------+--------------------+
                                              |                                         |
                                       (Payload Salah)                            (Payload Valid)
                                              v                                         v
                                     [ 400 / 422 Error ]                          [ Database Query ]
                                                                                        |
                                                                           +------------+------------+
                                                                           |                         |
                                                                     (Data Tidak Ada)          (Data Tersimpan)
                                                                           v                         v
                                                                    [ 404 Not Found ]        [ 201 Created ]
```

---

## 9. Simple Example: Pengujian API Menggunakan Native Fetch & Assertions

```javascript
// Pengujian endpoint POST /api/v1/users secara programatik
async function testCreateUserApi() {
  const payload = {
    name: "Ahmad Fauzi",
    email: "ahmad.fauzi@company.id",
    role: "DEVELOPER"
  };

  const response = await fetch("https://api.staging.internal/v1/users", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": "Bearer tok_valid_jwt_token"
    },
    body: JSON.stringify(payload)
  });

  // Assertion 1: Status Code wajib 201 Created
  if (response.status !== 201) {
    throw new Error(`Expected HTTP 201 Created, but received ${response.status}`);
  }

  // Assertion 2: Header Content-Type wajib JSON
  const contentType = response.headers.get("content-type");
  if (!contentType || !contentType.includes("application/json")) {
    throw new Error(`Expected application/json header, received ${contentType}`);
  }

  // Assertion 3: Response body memiliki ID baru
  const body = await response.json();
  if (!body.id || body.name !== payload.name) {
    throw new Error("Response body verification failed!");
  }

  console.log("✓ API Test: POST /v1/users PASSED!");
}
```

---

## 10. Practical Example: Checklist Validasi Header dan Idempotensi

### 1. Verifikasi Header Keamanan Respon (Security Headers Check):
- [ ] `Content-Type`: Wajib mencantumkan format dan charset persis (misal `application/json; charset=utf-8`).
- [ ] `X-Content-Type-Options: nosniff`: Mencegah browser melakukan MIME-sniffing.
- [ ] `Strict-Transport-Security (HSTS)`: Memaksa koneksi aman HTTPS.

### 2. Pengujian Idempotensi pada Transaksi Pembayaran:
- Kirim `POST /api/v1/payments` dengan header `Idempotency-Key: idempotency-uuid-7712` dan nominal Rp 100.000.
  - Server memproses dan mengembalikan `201 Created` (Saldo terpotong Rp 100.000).
- Kirim ulang **persis request yang sama** dengan `Idempotency-Key` yang sama (mensimulasikan koneksi pengguna putus dan tombol terklik dua kali).
  - **Ekspektasi QA**: Server mengembalikan respon transaksi terdahulu (atau `200 OK`) dan **TIDAK MEMOTONG SALDO DUA KALI**!

---

## 11. Real World Example: Kerugian Duplikasi Pembayaran Akibat Abaikan Idempotensi
Sebuah aplikasi fintech dompet digital di Asia Tenggara meluncurkan promo cashback:
- Pengguna dengan koneksi seluler 3G yang lambat menekan tombol *"Konfirmasi Pembayaran"* sebanyak 4 kali karena layar loading berputar lambat.
- Karena endpoint `POST /api/v1/transactions` tidak mengimplementasikan mekanisme *Idempotency-Key* di database, server menerima dan mengeksekusi ke-4 request tersebut sebagai transaksi independen terpisah.
- Akibatnya saldo pengguna terdebit 4 kali dan merchant menerima pembayaran ganda. Tim customer care menerima puluhan ribu komplain dalam 24 jam dan tim data engineer harus melakukan *database manual rollback reconciliation*.

---

## 12. Trade-offs

| Aspek Pengujian | UI Testing (End-to-End) | API Testing (Service Level) |
|---|---|---|
| **Kecepatan Eksekusi** | Sangat Lambat (5–30 detik per skenario). | Sangat Cepat (10–100 milidetik per skenario). |
| **Kestabilan (Flakiness)**| Rentan Flaky (Perubahan DOM, CSS, animasi browser). | Sangat Stabil (Hanya berubah jika kontrak data berubah). |
| **Fokus Verifikasi** | Tampilan visual, rendering grafis, user experience. | Logika bisnis, integritas data, status code, keamanan header. |
| **Biaya Pemeliharaan** | Tinggi. | Rendah hingga Sedang. |

---

## 13. When To Use
- Terapkan **API Testing** pada seluruh produk backend modern (REST, GraphQL, gRPC).
- Jalankan automated API regression suite pada setiap pull request di pipeline CI/CD sebelum kode di-deploy ke staging.
- Uji endpoint API secara mendalam sebelum aplikasi mobile atau frontend web mulai diintegrasikan.

## 14. When NOT To Use
- Jangan menggunakan API testing untuk memverifikasi apakah warna tombol berwarna hijau atau apakah animasi modal dialog bergeser halus dari atas ke bawah. Itu adalah tugas UI Testing.

---

## 15. Common Mistakes

```text
1. MISTAKE: Server mengembalikan HTTP 200 OK padahal terjadi error di backend (False 200 OK).
   WHY IT HAPPENS: Developer pemula membungkus seluruh controller dengan try-catch tanpa menetapkan status code error:
   Respon: HTTP 200 OK dengan body: {"status": "error", "message": "User not found"}.
   WHY IT IS BAD: Melanggar standar RFC protokol HTTP. Monitoring tools (Datadog/NewRelic) mengira sistem 100% sehat.
   CORRECT APPROACH: Kembalikan status code HTTP yang semantik (404 Not Found atau 400 Bad Request) jika terjadi kegagalan.

2. MISTAKE: QA hanya menguji Happy Path (Status 200/201) dan lupa menguji status 4xx.
   WHY IT HAPPENS: QA hanya menyalin contoh payload valid dari dokumentasi Postman.
   WHY IT IS BAD: Celah keamanan dan bad-input crashes tidak terdeteksi.
   CORRECT APPROACH: Rancang minimal 3 skenario negatif (Invalid Payload, Missing Token, Expired Token) untuk setiap 1 skenario positif.
```

---

## 16. Best Practices

### Must Have
- Verifikasi tiga serangkai: **HTTP Status Code**, **Response Headers**, dan **Response Body Schema**.
- Menolak mentah-mentah error bertopeng (*False 200 OK*) yang mengembalikan body error namun berstatus 200.

### Recommended
- Mengatur batas waktu timeout pengujian (misal request harus gagal jika tidak ada jawaban dalam 3.000 ms).
- Menggunakan environment variables untuk menyimpan `BASE_URL` dan credential auth agar test suite dapat dijalankan di Lokal, Staging, maupun Pre-prod tanpa mengubah kode tes.

### Advanced
- Memverifikasi kepatuhan *Idempotency Header* pada seluruh endpoint transaksi pembayaran (`POST`).

### Avoid / Overengineering
- Melakukan hardcoding ID data yang sudah dihapus pada test suite (mengakibatkan tes gagal di eksekusi kedua). Selalu buat data uji baru secara dinamis (*Dynamic Test Data Generation*).

---

## 17. Troubleshooting: Menangani Kesalahan 500 Internal Server Error Saat Pengujian API
Jika request mengembalikan status HTTP 500:
1. **Penyebab**: Unhandled Exception pada kode backend (misal: `Cannot read property of null`, `Database Connection Pool Exhausted`).
2. **Langkah QA**:
   - Salin cURL request persis dari log pengujian.
   - Buka log server backend staging (via Cloudwatch / Kibana / Docker logs).
   - Cocokkan timestamp dan request ID untuk menemukan stack trace error.
   - Laporkan tiket bug berstatus Severity: S1/S2 dengan melampirkan payload cURL dan cuplikan stack trace backend.

---

## 18. Exercise
1. Sebuah endpoint API dokumentasi menuliskan: `POST /api/v1/auth/login`.
   - Rancang 4 skenario pengujian API yang mencakup:
     - 1 skenario sukses (Expected: 200 OK + JWT token).
     - 1 skenario password salah (Expected: 401 Unauthorized).
     - 1 skenario format email tidak valid (Expected: 400 Bad Request).
     - 1 skenario akun terkunci karena salah 5 kali (Expected: 403 Forbidden atau 423 Locked).
2. Mengapa metode `DELETE /api/v1/products/100` dikatakan idempoten, sedangkan `POST /api/v1/products` tidak idempoten? Jelaskan secara rinci.

---

## 19. Challenge
Rancang sebuah **RESTful API Test Plan Document** untuk layanan transfer uang antar-rekening bank:
- Endpoint: `POST /api/v2/transfers`
- Spesifikasi Payload: `sourceAccountId`, `destinationAccountId`, `amount`, `currency`, `notes`.
- Tuliskan 6 skenario pengujian API lengkap (Method, Headers, Request Body, Expected Status Code, Expected Response Body JSON structure, dan verifikasi Idempotency-Key).

---

## 20. Summary
- API Testing menguji lapisan logika bisnis dan integrasi sistem secara cepat, stabil, dan independen dari tampilan visual.
- Status Code HTTP terbagi menjadi 5 kategori: 2xx (Sukses), 3xx (Redirect), 4xx (Client Error), dan 5xx (Server Error). Kepatuhan status code semantik wajib ditegakkan.
- Idempotensi menjamin bahwa pengulangan panggilan request yang sama tidak menimbulkan efek samping ganda pada status akhir server.

---

## Hands-on Practice: Simulator API Test Runner & Response Validator
Jalankan script simulator mandiri yang menjalankan virtual HTTP server, mengeksekusi request suite (Happy path, Negative 4xx, Token Auth, SLA latency check), dan memvalidasi struktur data JSON secara otomatis:

```bash
node QA/BAB-04-Pengujian-API-dan-Validasi-Kontrak/hands-on/m01/api_test_runner_schema_sim.js
```

---
[⬅️ BAB 03: Quiz & Challenge](../BAB-03-Teknik-Perancangan-Test-Case-Black-Box-White-Box/BAB-03-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: JSON Schema & Contract Testing ➡️](./Module-02-Otomasi-API-JSON-Schema-Validation-Mocking.md)
---
