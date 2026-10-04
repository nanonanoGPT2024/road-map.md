# Bab 07 Module 01: HTTP Protocol & RESTful API Design

## Kurikulum: Backend Beginner | Kategori: 01-Core-Foundations

---

# SECTION 01 — LEARNING OBJECTIVE

## Tujuan Pembelajaran

Setelah menyelesaikan modul ini, peserta didik mampu:

1. **Memahami** arsitektur dan cara kerja protokol HTTP secara menyeluruh, termasuk request-response lifecycle, method, status code, dan header
2. **Menjelaskan** prinsip-prinsip desain RESTful API dan mengapa REST menjadi standar industri untuk komunikasi antar sistem
3. **Merancang** endpoint API yang bersih, konsisten, dan mengikuti konvensi REST dengan benar
4. **Mengimplementasikan** RESTful API sederhana menggunakan Node.js/Express dengan penanganan error yang tepat
5. **Membedakan** antara berbagai HTTP method dan kapan menggunakannya secara tepat
6. **Mengevaluasi** kualitas desain API berdasarkan kriteria keterbacaan, konsistensi, dan kemudahan penggunaan

### Prasyarat Modul Ini

```
✅ Bab 01-06 telah diselesaikan
✅ Memahami dasar JavaScript (fungsi, objek, array)
✅ Node.js terinstal (v18+)
✅ Familiar dengan terminal/command line
✅ Memahami konsep JSON
```

### Estimasi Waktu

| Komponen | Durasi |
|---|---|
| Membaca materi | 90 menit |
| Latihan terpandu | 60 menit |
| Proyek praktis | 120 menit |
| Kuis & evaluasi | 30 menit |
| **Total** | **~5 jam** |

---

# SECTION 02 — CONCEPT OVERVIEW

## Gambaran Konsep: HTTP & REST

### Apa yang Kita Bangun?

Bayangkan Anda membangun sebuah **restoran digital**. Dalam restoran ini:

- **Pelanggan** (client/browser/aplikasi mobile) datang dengan **pesanan** (HTTP Request)
- **Pelayan** (HTTP Protocol) membawa pesanan ke dapur dan membawa kembali makanan
- **Dapur** (server/backend) memproses pesanan dan menyiapkan makanan (response)
- **Menu** (API Documentation) adalah daftar apa yang bisa dipesan dan bagaimana cara memesannya

**HTTP (HyperText Transfer Protocol)** adalah bahasa komunikasi antara client dan server — aturan baku tentang bagaimana pesan dikirim dan diterima di internet.

**REST (Representational State Transfer)** adalah **gaya arsitektur** — sekumpulan prinsip desain untuk membuat API yang mudah dipahami, digunakan, dan dipelihara.

### Posisi dalam Ekosistem Backend

```
┌─────────────────────────────────────────────────────────┐
│                    EKOSISTEM BACKEND                     │
│                                                          │
│  ┌──────────┐    HTTP/REST    ┌──────────────────────┐  │
│  │  CLIENT  │ ◄────────────► │    BACKEND SERVER     │  │
│  │(Browser/ │                │  ┌────────────────┐   │  │
│  │ Mobile/  │                │  │  API Layer     │   │  │
│  │ 3rd Party│                │  │  (Module ini)  │   │  │
│  └──────────┘                │  └────────────────┘   │  │
│                              │  ┌────────────────┐   │  │
│                              │  │  Business Logic│   │  │
│                              │  └────────────────┘   │  │
│                              │  ┌────────────────┐   │  │
│                              │  │    Database    │   │  │
│                              │  └────────────────┘   │  │
│                              └──────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Mengapa Ini Fondasi yang Kritis?

Hampir **semua** komunikasi di web modern menggunakan HTTP. Memahami HTTP dan REST bukan pilihan — ini adalah **literasi dasar** seorang backend developer. Tanpa pemahaman ini, Anda tidak bisa:

- Membangun API yang bisa digunakan orang lain
- Men-debug masalah jaringan
- Mengintegrasikan layanan pihak ketiga
- Merancang sistem yang scalable

---

# SECTION 03 — WHY THIS MATTERS

## Mengapa HTTP & REST Penting?

### Konteks Historis: Sebelum REST

Sebelum REST dipopulerkan oleh Roy Fielding pada tahun 2000 dalam disertasi doktoralnya, komunikasi antar sistem sangat **kacau dan tidak konsisten**:

```
❌ SEBELUM REST (Chaos Era):
─────────────────────────────────────────────────────
GET /getUser?id=123
GET /fetchAllProducts
POST /doCreateOrder
GET /deleteItem?itemId=456    ← DELETE via GET? 😱
POST /updateUserProfile
GET /getUserOrders?userId=123&format=xml
─────────────────────────────────────────────────────
Setiap developer membuat konvensi sendiri.
Tidak ada standar. Integrasi = mimpi buruk.
```

```
✅ DENGAN REST (Standar Modern):
─────────────────────────────────────────────────────
GET    /users/123
GET    /products
POST   /orders
DELETE /items/456
PUT    /users/123/profile
GET    /users/123/orders
─────────────────────────────────────────────────────
Konsisten, dapat diprediksi, mudah dipahami.
```

### Dampak Nyata di Industri

**Statistik yang perlu diketahui:**

| Fakta | Angka |
|---|---|
| Persentase API publik yang menggunakan REST | ~83% |
| Pertumbuhan API economy per tahun | ~25% |
| Rata-rata aplikasi enterprise mengonsumsi API | 15-20 API eksternal |
| Waktu debugging API yang buruk vs baik | 3x lebih lama |

### Skenario Nyata: Mengapa Desain API Buruk Mahal

```
SKENARIO: Startup e-commerce dengan API yang buruk

Masalah yang terjadi:
├── Frontend developer bingung endpoint mana yang benar
│   → 2 hari debugging = Rp 2.000.000 terbuang
├── Mobile app salah interpretasi response format
│   → Bug di production = kehilangan 500 transaksi
├── Partner bisnis tidak bisa integrasi
│   → Kehilangan kontrak senilai Rp 500.000.000
└── Onboarding developer baru butuh 2 minggu
    → Produktivitas hilang = Rp 10.000.000

TOTAL KERUGIAN DARI API YANG BURUK: Sangat signifikan
```

### Relevansi untuk Karir Anda

Sebagai backend developer, Anda akan **selalu** bekerja dengan HTTP dan API:

- **Junior Developer**: Mengimplementasikan endpoint sesuai spesifikasi
- **Mid-level Developer**: Merancang API untuk fitur baru
- **Senior Developer**: Mendefinisikan standar API untuk seluruh tim
- **Tech Lead**: Mengevaluasi arsitektur API sistem

---

# SECTION 04 — WHAT IS HTTP?

## Apa Itu HTTP?

### Definisi Formal

**HTTP (HyperText Transfer Protocol)** adalah protokol komunikasi lapisan aplikasi (Application Layer) berbasis teks yang mendefinisikan aturan pertukaran data antara client dan server di jaringan komputer.

Karakteristik utama HTTP:

| Karakteristik | Penjelasan |
|---|---|
| **Stateless** | Setiap request berdiri sendiri; server tidak "mengingat" request sebelumnya |
| **Text-based** | Pesan HTTP dapat dibaca manusia (human-readable) |
| **Request-Response** | Selalu ada pasangan: satu request menghasilkan satu response |
| **Client-Server** | Pemisahan jelas antara yang meminta dan yang melayani |
| **Cacheable** | Response dapat disimpan sementara untuk efisiensi |

### Anatomi HTTP Request

Setiap HTTP Request terdiri dari komponen berikut:

```
┌─────────────────────────────────────────────────────────┐
│                    HTTP REQUEST                          │
├─────────────────────────────────────────────────────────┤
│  REQUEST LINE                                           │
│  ┌─────────────────────────────────────────────────┐   │
│  │  POST /api/users HTTP/1.1                        │   │
│  │   ▲       ▲          ▲                           │   │
│  │  Method  Path      Version                       │   │
│  └─────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────┤
│  HEADERS                                                │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Host: api.example.com                           │   │
│  │  Content-Type: application/json                  │   │
│  │  Authorization: Bearer eyJhbGc...                │   │
│  │  Accept: application/json                        │   │
│  │  Content-Length: 85                              │   │
│  └─────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────┤
│  BLANK LINE (pemisah header dan body)                   │
├─────────────────────────────────────────────────────────┤
│  BODY (opsional)                                        │
│  ┌─────────────────────────────────────────────────┐   │
│  │  {                                               │   │
│  │    "name": "Budi Santoso",                       │   │
│  │    "email": "budi@example.com",                  │   │
│  │    "password": "SecurePass123!"                  │   │
│  │  }                                               │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### Anatomi HTTP Response

```
┌─────────────────────────────────────────────────────────┐
│                    HTTP RESPONSE                         │
├─────────────────────────────────────────────────────────┤
│  STATUS LINE                                            │
│  ┌─────────────────────────────────────────────────┐   │
│  │  HTTP/1.1 201 Created                            │   │
│  │     ▲       ▲    ▲                               │   │
│  │  Version  Code  Reason Phrase                    │   │
│  └─────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────┤
│  HEADERS                                                │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Content-Type: application/json                  │   │
│  │  Location: /api/users/789                        │   │
│  │  X-Request-ID: req_abc123                        │   │
│  │  Date: Mon, 15 Jan 2024 10:30:00 GMT             │   │
│  └─────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────┤
│  BLANK LINE                                             │
├─────────────────────────────────────────────────────────┤
│  BODY                                                   │
│  ┌─────────────────────────────────────────────────┐   │
│  │  {                                               │   │
│  │    "id": 789,                                    │   │
│  │    "name": "Budi Santoso",                       │   │
│  │    "email": "budi@example.com",                  │   │
│  │    "createdAt": "2024-01-15T10:30:00Z"           │   │
│  │  }                                               │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### HTTP Methods (Verbs)

HTTP mendefinisikan beberapa **method** yang menunjukkan **aksi** yang ingin dilakukan:

| Method | Aksi | Idempoten? | Safe? | Body? |
|---|---|---|---|---|
| **GET** | Mengambil data | ✅ Ya | ✅ Ya | ❌ Tidak |
| **POST** | Membuat data baru | ❌ Tidak | ❌ Tidak | ✅ Ya |
| **PUT** | Mengganti data sepenuhnya | ✅ Ya | ❌ Tidak | ✅ Ya |
| **PATCH** | Memperbarui sebagian data | ❌ Tidak* | ❌ Tidak | ✅ Ya |
| **DELETE** | Menghapus data | ✅ Ya | ❌ Tidak | Opsional |
| **HEAD** | Seperti GET tapi tanpa body | ✅ Ya | ✅ Ya | ❌ Tidak |
| **OPTIONS** | Menanyakan method yang tersedia | ✅ Ya | ✅ Ya | ❌ Tidak |

> **Idempoten**: Memanggil berkali-kali menghasilkan efek yang sama
> **Safe**: Tidak mengubah state server

---

# SECTION 05 — WHAT IS REST?

## Apa Itu REST?

### Definisi dan Asal-usul

**REST (Representational State Transfer)** adalah gaya arsitektur perangkat lunak yang didefinisikan oleh Roy Fielding dalam disertasinya tahun 2000. REST bukan protokol atau standar — melainkan **sekumpulan constraint (batasan)** yang jika diikuti, menghasilkan sistem yang scalable, maintainable, dan interoperable.

### 6 Constraint REST (Prinsip Utama)

```
┌─────────────────────────────────────────────────────────┐
│              6 CONSTRAINT REST ARCHITECTURE              │
│                                                          │
│  1. CLIENT-SERVER                                        │
│     ┌──────────┐              ┌──────────┐              │
│     │  Client  │◄────────────►│  Server  │              │
│     │(UI/Logic)│   Terpisah   │(Data/API)│              │
│     └──────────┘              └──────────┘              │
│     → Separation of concerns, evolusi independen         │
│                                                          │
│  2. STATELESS                                            │
│     Request 1: [Data Lengkap] → Server proses           │
│     Request 2: [Data Lengkap] → Server proses           │
│     → Server tidak simpan session antar request          │
│                                                          │
│  3. CACHEABLE                                            │
│     Response ditandai: cacheable / non-cacheable         │
│     → Performa lebih baik, beban server berkurang        │
│                                                          │
│  4. UNIFORM INTERFACE                                    │
│     - Resource identification via URI                    │
│     - Manipulation via representations                   │
│     - Self-descriptive messages                          │
│     - HATEOAS (Hypermedia as Engine of App State)        │
│                                                          │
│  5. LAYERED SYSTEM                                       │
│     Client → [Load Balancer] → [Cache] → Server         │
│     → Client tidak perlu tahu ada berapa layer           │
│                                                          │
│  6. CODE ON DEMAND (Opsional)                            │
│     Server bisa kirim executable code ke client          │
│     → Contoh: JavaScript dari server                     │
└─────────────────────────────────────────────────────────┘
```

### Resource: Konsep Inti REST

Dalam REST, segalanya adalah **Resource** — entitas yang dapat diidentifikasi, diakses, dan dimanipulasi.

```
RESOURCE dalam sistem e-commerce:
├── /users          → Koleksi semua pengguna
├── /users/123      → Pengguna dengan ID 123
├── /products       → Koleksi semua produk
├── /products/456   → Produk dengan ID 456
├── /orders         → Koleksi semua pesanan
├── /orders/789     → Pesanan dengan ID 789
└── /users/123/orders → Semua pesanan milik user 123
```

**Aturan penamaan resource:**

```
✅ BENAR (Noun, Plural):
/users
/products
/orders
/categories

❌ SALAH (Verb, Singular):
/getUser
/createProduct
/deleteOrder
/category
```

### RESTful vs Non-RESTful

```
OPERASI CRUD pada Resource "User":

┌─────────────────────────────────────────────────────────┐
│  OPERASI    │  NON-RESTful          │  RESTful           │
├─────────────┼───────────────────────┼────────────────────┤
│  Baca semua │ GET /getAllUsers       │ GET /users         │
│  Baca satu  │ GET /getUser?id=1     │ GET /users/1       │
│  Buat baru  │ POST /createUser      │ POST /users        │
│  Update     │ POST /updateUser/1    │ PUT /users/1       │
│  Hapus      │ GET /deleteUser?id=1  │ DELETE /users/1    │
└─────────────┴───────────────────────┴────────────────────┘
```

---

# SECTION 06 — HTTP STATUS CODES

## Kode Status HTTP

### Kategori Status Code

Status code adalah **bahasa server** untuk memberitahu client apa yang terjadi dengan requestnya.

```
┌─────────────────────────────────────────────────────────┐
│                 KATEGORI STATUS CODE                     │
│                                                          │
│  1xx  INFORMATIONAL  ──────────────────────────────     │
│       Request diterima, proses berlanjut                 │
│       Jarang digunakan langsung                          │
│                                                          │
│  2xx  SUCCESS  ────────────────────────────────────     │
│       Request berhasil diproses                          │
│       ✅ Ini yang kita inginkan                          │
│                                                          │
│  3xx  REDIRECTION  ────────────────────────────────     │
│       Client perlu melakukan aksi tambahan               │
│       Resource telah pindah                              │
│                                                          │
│  4xx  CLIENT ERROR  ───────────────────────────────     │
│       Kesalahan dari sisi client                         │
│       ❌ Request tidak valid                             │
│                                                          │
│  5xx  SERVER ERROR  ───────────────────────────────     │
│       Kesalahan dari sisi server                         │
│       🔥 Server gagal memproses request yang valid       │
└─────────────────────────────────────────────────────────┘
```

### Status Code yang Wajib Dikuasai

**2xx — Success:**

| Code | Nama | Kapan Digunakan |
|---|---|---|
| **200** | OK | GET berhasil, PUT/PATCH berhasil |
| **201** | Created | POST berhasil membuat resource baru |
| **204** | No Content | DELETE berhasil, tidak ada body response |
| **206** | Partial Content | Response sebagian (pagination/streaming) |

**3xx — Redirection:**

| Code | Nama | Kapan Digunakan |
|---|---|---|
| **301** | Moved Permanently | URL lama → URL baru permanen |
| **302** | Found | Redirect sementara |
| **304** | Not Modified | Cache masih valid, tidak perlu download ulang |

**4xx — Client Error:**

| Code | Nama | Kapan Digunakan |
|---|---|---|
| **400** | Bad Request | Request malformed, validasi gagal |
| **401** | Unauthorized | Belum login / token tidak valid |
| **403** | Forbidden | Sudah login tapi tidak punya izin |
| **404** | Not Found | Resource tidak ditemukan |
| **405** | Method Not Allowed | Method tidak didukung endpoint ini |
| **409** | Conflict | Konflik data (email sudah terdaftar) |
| **422** | Unprocessable Entity | Validasi bisnis gagal |
| **429** | Too Many Requests | Rate limit terlampaui |

**5xx — Server Error:**

| Code | Nama | Kapan Digunakan |
|---|---|---|
| **500** | Internal Server Error | Error tak terduga di server |
| **502** | Bad Gateway | Server upstream bermasalah |
| **503** | Service Unavailable | Server sedang maintenance/overload |
| **504** | Gateway Timeout | Server upstream timeout |

### Panduan Memilih Status Code

```
FLOWCHART PEMILIHAN STATUS CODE:

Request masuk
     │
     ▼
Apakah request valid secara sintaks?
     │
     ├── TIDAK → 400 Bad Request
     │
     └── YA
          │
          ▼
     Apakah user terautentikasi?
          │
          ├── TIDAK → 401 Unauthorized
          │
          └── YA
               │
               ▼
          Apakah user punya izin?
               │
               ├── TIDAK → 403 Forbidden
               │
               └── YA
                    │
                    ▼
               Apakah resource ada?
                    │
                    ├── TIDAK → 404 Not Found
                    │
                    └── YA
                         │
                         ▼
                    Apakah ada konflik data?
                         │
                         ├── YA → 409 Conflict
                         │
                         └── TIDAK
                              │
                              ▼
                         Proses berhasil?
                              │
                              ├── TIDAK → 500 Internal Server Error
                              │
                              └── YA
                                   │
                                   ├── POST (buat baru) → 201 Created
                                   ├── DELETE → 204 No Content
                                   └── GET/PUT/PATCH → 200 OK
```

---

# SECTION 07 — HTTP HEADERS

## HTTP Headers: Metadata Komunikasi

### Apa Itu Headers?

Headers adalah **metadata** yang menyertai setiap HTTP request dan response. Mereka memberikan informasi kontekstual tentang pesan yang dikirim.

```
┌─────────────────────────────────────────────────────────┐
│                   KATEGORI HEADERS                       │
│                                                          │
│  GENERAL HEADERS (berlaku untuk request & response)     │
│  ├── Date: Mon, 15 Jan 2024 10:30:00 GMT                │
│  ├── Connection: keep-alive                              │
│  └── Cache-Control: no-cache                            │
│                                                          │
│  REQUEST HEADERS (hanya di request)                     │
│  ├── Host: api.example.com                              │
│  ├── User-Agent: Mozilla/5.0...                         │
│  ├── Accept: application/json                           │
│  ├── Accept-Language: id-ID,id;q=0.9                    │
│  ├── Authorization: Bearer <token>                       │
│  └── Content-Type: application/json                     │
│                                                          │
│  RESPONSE HEADERS (hanya di response)                   │
│  ├── Content-Type: application/json; charset=utf-8      │
│  ├── Content-Length: 256                                │
│  ├── Location: /api/users/789                           │
│  ├── WWW-Authenticate: Bearer realm="api"               │
│  └── X-Rate-Limit-Remaining: 99                         │
└─────────────────────────────────────────────────────────┘
```

### Headers Paling Penting untuk Backend Developer

**Content-Type & Accept:**

```
Content-Type: application/json
→ "Isi body yang saya kirim adalah JSON"

Accept: application/json
→ "Saya ingin menerima response dalam format JSON"

Content-Type: multipart/form-data
→ "Saya mengirim form data (termasuk file upload)"

Content-Type: application/x-www-form-urlencoded
→ "Saya mengirim data form HTML biasa"
```

**Authorization:**

```
# Basic Auth (username:password di-encode base64)
Authorization: Basic dXNlcjpwYXNzd29yZA==

# Bearer Token (JWT)
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# API Key
X-API-Key: sk_live_abc123def456
```

**Cache Control:**

```
Cache-Control: no-store          → Jangan cache sama sekali
Cache-Control: no-cache          → Cache tapi selalu validasi
Cache-Control: max-age=3600      → Cache selama 1 jam
Cache-Control: public            → Bisa di-cache siapa saja
Cache-Control: private           → Hanya cache di browser user
```

**CORS Headers:**

```
# Response dari server untuk mengizinkan cross-origin request
Access-Control-Allow-Origin: https://app.example.com
Access-Control-Allow-Methods: GET, POST, PUT, DELETE
Access-Control-Allow-Headers: Content-Type, Authorization
Access-Control-Max-Age: 86400
```

---

# SECTION 08 — ASCII DIAGRAM: HTTP REQUEST-RESPONSE LIFECYCLE

## Diagram: Siklus Hidup HTTP Request-Response

```
╔═════════════════════════════════════════════════════════════════════╗
║              HTTP REQUEST-RESPONSE LIFECYCLE                        ║
╚═════════════════════════════════════════════════════════════════════╝

  CLIENT                    NETWORK                      SERVER
  (Browser/App)             (Internet)                   (Backend)
     │                          │                            │
     │  1. User action          │                            │
     │  (klik tombol, dll)      │                            │
     │                          │                            │
     │  2. Buat HTTP Request    │                            │
     │  ┌─────────────────┐     │                            │
     │  │ GET /api/users  │     │                            │
     │  │ Host: api.ex.com│     │                            │
     │  │ Auth: Bearer... │     │                            │
     │  └─────────────────┘     │                            │
     │                          │                            │
     │──────── Request ─────────►                            │
     │                          │                            │
     │                          │  3. DNS Resolution         │
     │                          │  api.example.com           │
     │                          │  → 203.0.113.42            │
     │                          │                            │
     │                          │  4. TCP Handshake          │
     │                          │  SYN → SYN-ACK → ACK       │
     │                          │                            │
     │                          │  5. TLS Handshake (HTTPS)  │
     │                          │  Negosiasi enkripsi        │
     │                          │                            │
     │                          │──── Request ──────────────►│
     │                          │                            │
     │                          │              6. Server     │
     │                          │              terima request│
     │                          │                    │       │
     │                          │              7. Middleware │
     │                          │              (Auth, Log)   │
     │                          │                    │       │
     │                          │              8. Route      │
     │                          │              matching      │
     │                          │                    │       │
     │                          │              9. Controller │
     │                          │              logic         │
     │                          │                    │       │
     │                          │              10. Database  │
     │                          │              query         │
     │                          │                    │       │
     │                          │              11. Buat      │
     │                          │              Response      │
     │                          │                            │
     │                          │◄─── Response ─────────────│
     │                          │                            │
     │◄──────── Response ───────│                            │
     │                          │                            │
     │  12. Terima Response     │                            │
     │  ┌─────────────────┐     │                            │
     │  │ HTTP/1.1 200 OK │     │                            │
     │  │ Content-Type:   │     │                            │
     │  │ application/json│     │                            │
     │  │                 │     │                            │
     │  │ {"users": [...]}│     │                            │
     │  └─────────────────┘     │                            │
     │                          │                            │
     │  13. Parse & Render      │                            │
     │  (tampilkan ke user)     │                            │
     │                          │                            │

TOTAL WAKTU TIPIKAL:
├── DNS Resolution: 1-100ms
├── TCP Handshake: 1-3 RTT
├── TLS Handshake: 1-2 RTT (TLS 1.3 lebih cepat)
├── Server Processing: 1ms - beberapa detik
└── Data Transfer: tergantung ukuran response
```

### URL Anatomy

```
  https://api.example.com:443/api/v1/users/123?include=orders&limit=10#section
  ─────┬─ ──────────┬────── ─┬─ ──┬── ──┬─── ─┬─ ──────────┬───────── ──┬────
       │            │        │    │     │      │            │             │
    Scheme       Hostname  Port  Base  Resource Query      Parameters  Fragment
    (Protocol)             (def) Path  Path    Separator
                                                │
                                         ?key=value&key2=value2
```

---

# SECTION 09 — SIMPLE EXAMPLE

## Contoh Sederhana: API "Hello World"

### Setup Proyek

```bash
# Buat direktori proyek
mkdir belajar-rest-api
cd belajar-rest-api

# Inisialisasi Node.js project
npm init -y

# Install Express
npm install express

# Install nodemon untuk development
npm install --save-dev nodemon

# Struktur file
touch app.js
```

### Kode: Server HTTP Paling Sederhana

```javascript
// app.js - Server HTTP Sederhana dengan Node.js built-in

const http = require('http');

// Buat server
const server = http.createServer((request, response) => {
  // Log setiap request yang masuk
  console.log(`${request.method} ${request.url}`);

  // Set header response
  response.setHeader('Content-Type', 'application/json');

  // Routing sederhana
  if (request.method === 'GET' && request.url === '/') {
    // Response untuk root endpoint
    response.statusCode = 200;
    response.end(JSON.stringify({
      message: 'Selamat datang di API saya!',
      version: '1.0.0',
      timestamp: new Date().toISOString()
    }));

  } else if (request.method === 'GET' && request.url === '/health') {
    // Health check endpoint
    response.statusCode = 200;
    response.end(JSON.stringify({
      status: 'healthy',
      uptime: process.uptime()
    }));

  } else {
    // 404 untuk semua route yang tidak dikenal
    response.statusCode = 404;
    response.end(JSON.stringify({
      error: 'Not Found',
      message: `Route ${request.url} tidak ditemukan`
    }));
  }
});

// Server mendengarkan di port 3000
const PORT = 3000;
server.listen(PORT, () => {
  console.log(`✅ Server berjalan di http://localhost:${PORT}`);
});
```

### Menjalankan dan Menguji

```bash
# Jalankan server
node app.js

# Output:
# ✅ Server berjalan di http://localhost:3000
```

```bash
# Test dengan curl (terminal baru)

# Test root endpoint
curl -i http://localhost:3000/

# Output:
# HTTP/1.1 200 OK
# Content-Type: application/json
# Date: Mon, 15 Jan 2024 10:30:00 GMT
# Connection: keep-alive
# Transfer-Encoding: chunked
#
# {"message":"Selamat datang di API saya!","version":"1.0.0","timestamp":"2024-01-15T10:30:00.000Z"}

# Test health endpoint
curl http://localhost:3000/health

# Output:
# {"status":"healthy","uptime":42.5}

# Test 404
curl -i http://localhost:3000/tidak-ada

# Output:
# HTTP/1.1 404 Not Found
# ...
# {"error":"Not Found","message":"Route /tidak-ada tidak ditemukan"}
```

### Versi dengan Express (Lebih Bersih)

```javascript
// app-express.js - Versi Express yang lebih bersih

const express = require('express');
const app = express();

// Middleware untuk parse JSON body
app.use(express.json());

// Middleware logging sederhana
app.use((req, res, next) => {
  console.log(`[${new Date().toISOString()}] ${req.method} ${req.path}`);
  next(); // Lanjutkan ke handler berikutnya
});

// Route: Root
app.get('/', (req, res) => {
  res.status(200).json({
    message: 'Selamat datang di API saya!',
    version: '1.0.0',
    timestamp: new Date().toISOString()
  });
});

// Route: Health Check
app.get('/health', (req, res) => {
  res.status(200).json({
    status: 'healthy',
    uptime: process.uptime()
  });
});

// Route: 404 Handler (harus di paling bawah)
app.use((req, res) => {
  res.status(404).json({
    error: 'Not Found',
    message: `Route ${req.path} tidak ditemukan`
  });
});

// Jalankan server
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`✅ Server Express berjalan di http://localhost:${PORT}`);
});
```

---

# SECTION 10 — PRACTICAL EXAMPLE

## Contoh Praktis: RESTful API untuk Manajemen Buku

### Spesifikasi API

Kita akan membangun API untuk perpustakaan digital dengan resource **Books**:

```
ENDPOINT SPECIFICATION:

GET    /api/v1/books           → Ambil semua buku
GET    /api/v1/books/:id       → Ambil buku berdasarkan ID
POST   /api/v1/books           → Tambah buku baru
PUT    /api/v1/books/:id       → Update buku sepenuhnya
PATCH  /api/v1/books/:id       → Update sebagian buku
DELETE /api/v1/books/:id       → Hapus buku

QUERY PARAMETERS untuk GET /books:
?page=1&limit=10               → Pagination
?search=javascript             → Pencarian
?genre=programming             → Filter genre
?sort=title&order=asc          → Sorting
```

### Struktur Proyek

```
buku-api/
├── package.json
├── app.js                    ← Entry point
├── src/
│   ├── routes/
│   │   └── books.routes.js   ← Definisi route
│   ├── controllers/
│   │   └── books.controller.js ← Logic handler
│   ├── middleware/
│   │   └── validate.js       ← Validasi input
│   └── data/
│       └── books.data.js     ← Data in-memory (simulasi DB)
└── README.md
```

### Implementasi Lengkap

```javascript
// src/data/books.data.js
// Simulasi database menggunakan array in-memory

let books = [
  {
    id: 1,
    title: 'Clean Code',
    author: 'Robert C. Martin',
    isbn: '978-0132350884',
    genre: 'programming',
    publishedYear: 2008,
    available: true,
    createdAt: '2024-01-01T00:00:00Z',
    updatedAt: '2024-01-01T00:00:00Z'
  },
  {
    id: 2,
    title: 'The Pragmatic Programmer',
    author: 'David Thomas & Andrew Hunt',
    isbn: '978-0135957059',
    genre: 'programming',
    publishedYear: 2019,
    available: true,
    createdAt: '2024-01-01T00:00:00Z',
    updatedAt: '2024-01-01T00:00:00Z'
  },
  {
    id: 3,
    title: 'Atomic Habits',
    author: 'James Clear',
    isbn: '978-0735211292',
    genre: 'self-help',
    publishedYear: 2018,
    available: false,
    createdAt: '2024-01-01T00:00:00Z',
    updatedAt: '2024-01-01T00:00:00Z'
  }
];

// Counter untuk ID auto-increment
let nextId = 4;

module.exports = {
  // Ambil semua buku dengan filter, search, sort, pagination
  findAll: ({ page = 1, limit = 10, search, genre, sort = 'id', order = 'asc' }) => {
    let result = [...books];

    // Filter berdasarkan genre
    if (genre) {
      result = result.filter(book =>
        book.genre.toLowerCase() === genre.toLowerCase()
      );
    }

    // Pencarian berdasarkan judul atau penulis
    if (search) {
      const searchLower = search.toLowerCase();
      result = result.filter(book =>
        book.title.toLowerCase().includes(searchLower) ||
        book.author.toLowerCase().includes(searchLower)
      );
    }

    // Sorting
    result.sort((a, b) => {
      const valA = a[sort];
      const valB = b[sort];
      if (order === 'asc') return valA > valB ? 1 : -1;
      return valA < valB ? 1 : -1;
    });

    // Pagination
    const total = result.length;
    const startIndex = (page - 1) * limit;
    const endIndex = startIndex + parseInt(limit);
    const paginatedResult = result.slice(startIndex, endIndex);

    return {
      data: paginatedResult,
      pagination: {
        total,
        page: parseInt(page),
        limit: parseInt(limit),
        totalPages: Math.ceil(total / limit),
        hasNextPage: endIndex < total,
        hasPrevPage: page > 1
      }
    };
  },

  // Cari buku berdasarkan ID
  findById: (id) => {
    return books.find(book => book.id === parseInt(id)) || null;
  },

  // Cari buku berdasarkan ISBN
  findByIsbn: (isbn) => {
    return books.find(book => book.isbn === isbn) || null;
  },

  // Buat buku baru
  create: (bookData) => {
    const now = new Date().toISOString();
    const newBook = {
      id: nextId++,
      ...bookData,
      available: bookData.available ?? true,
      createdAt: now,
      updatedAt: now
    };
    books.push(newBook);
    return newBook;
  },

  // Update buku sepenuhnya (PUT)
  replace: (id, bookData) => {
    const index = books.findIndex(book => book.id === parseInt(id));
    if (index === -1) return null;

    const updatedBook = {
      id: parseInt(id),
      ...bookData,
      createdAt: books[index].createdAt,
      updatedAt: new Date().toISOString()
    };
    books[index] = updatedBook;
    return updatedBook;
  },

  // Update sebagian buku (PATCH)
  update: (id, partialData) => {
    const index = books.findIndex(book => book.id === parseInt(id));
    if (index === -1) return null;

    books[index] = {
      ...books[index],
      ...partialData,
      id: parseInt(id),           // ID tidak boleh berubah
      createdAt: books[index].createdAt, // createdAt tidak berubah
      updatedAt: new Date().toISOString()
    };
    return books[index];
  },

  // Hapus buku
  delete: (id) => {
    const index = books.findIndex(book => book.id === parseInt(id));
    if (index === -1) return false;

    books.splice(index, 1);
    return true;
  }
};
```

```javascript
// src/middleware/validate.js
// Middleware validasi input

/**
 * Validasi data buku untuk POST (semua field wajib)
 */
const validateCreateBook = (req, res, next) => {
  const { title, author, isbn, genre, publishedYear } = req.body;
  const errors = [];

  // Validasi field wajib
  if (!title || typeof title !== 'string' || title.trim().length === 0) {
    errors.push({ field: 'title', message: 'Judul buku wajib diisi' });
  }

  if (!author || typeof author !== 'string' || author.trim().length === 0) {
    errors.push({ field: 'author', message: 'Nama penulis wajib diisi' });
  }

  if (!isbn || typeof isbn !== 'string') {
    errors.push({ field: 'isbn', message: 'ISBN wajib diisi' });
  } else if (!/^978-\d{10}$/.test(isbn)) {
    errors.push({ field: 'isbn', message: 'Format ISBN tidak valid (contoh: 978-0132350884)' });
  }

  if (!genre || typeof genre !== 'string') {
    errors.push({ field: 'genre', message: 'Genre wajib diisi' });
  }

  if (!publishedYear || typeof publishedYear !== 'number') {
    errors.push({ field: 'publishedYear', message: 'Tahun terbit wajib diisi (angka)' });
  } else if (publishedYear < 1000 || publishedYear > new Date().getFullYear()) {
    errors.push({ field: 'publishedYear', message: 'Tahun terbit tidak valid' });
  }

  // Jika ada error, kembalikan 400
  if (errors.length > 0) {
    return res.status(400).json({
      success: false,
      error: 'Validation Error',
      message: 'Data yang dikirim tidak valid',
      details: errors
    });
  }

  // Sanitasi data sebelum lanjut
  req.body.title = title.trim();
  req.body.author = author.trim();

  next();
};

/**
 * Validasi data buku untuk PATCH (semua field opsional)
 */
const validateUpdateBook = (req, res, next) => {
  const { title, author, isbn, genre, publishedYear, available } = req.body;
  const errors = [];

  // Pastikan ada minimal satu field yang diupdate
  if (Object.keys(req.body).length === 0) {
    return res.status(400).json({
      success: false,
      error: 'Validation Error',
      message: 'Minimal satu field harus diisi untuk update'
    });
  }

  // Validasi field yang ada (jika dikirim)
  if (title !== undefined && (typeof title !== 'string' || title.trim().length === 0)) {
    errors.push({ field: 'title', message: 'Judul tidak boleh kosong' });
  }

  if (isbn !== undefined && !/^978-\d{10}$/.test(isbn)) {
    errors.push({ field: 'isbn', message: 'Format ISBN tidak valid' });
  }

  if (publishedYear !== undefined) {
    if (typeof publishedYear !== 'number' ||
        publishedYear < 1000 ||
        publishedYear > new Date().getFullYear()) {
      errors.push({ field: 'publishedYear', message: 'Tahun terbit tidak valid' });
    }
  }

  if (available !== undefined && typeof available !== 'boolean') {
    errors.push({ field: 'available', message: 'Available harus berupa boolean' });
  }

  if (errors.length > 0) {
    return res.status(400).json({
      success: false,
      error: 'Validation Error',
      details: errors
    });
  }

  next();
};

module.exports = { validateCreateBook, validateUpdateBook };
```

```javascript
// src/controllers/books.controller.js
// Controller: Logic untuk setiap endpoint

const booksData = require('../data/books.data');

/**
 * GET /api/v1/books
 * Ambil semua buku dengan filter, search, sort, pagination
 */
const getAllBooks = (req, res) => {
  try {
    const { page, limit, search, genre, sort, order } = req.query;

    const result = booksData.findAll({
      page: page || 1,
      limit: limit || 10,
      search,
      genre,
      sort: sort || 'id',
      order: order || 'asc'
    });

    res.status(200).json({
      success: true,
      ...result
    });

  } catch (error) {
    console.error('Error getAllBooks:', error);
    res.status(500).json({
      success: false,
      error: 'Internal Server Error',
      message: 'Gagal mengambil data buku'
    });
  }
};

/**
 * GET /api/v1/books/:id
 * Ambil satu buku berdasarkan ID
 */
const getBookById = (req, res) => {
  try {
    const { id } = req.params;

    // Validasi ID harus angka
    if (isNaN(id)) {
      return res.status(400).json({
        success: false,
        error: 'Bad Request',
        message: 'ID buku harus berupa angka'
      });
    }

    const book = booksData.findById(id);

    if (!book) {
      return res.status(404).json({
        success: false,
        error: 'Not Found',
        message: `Buku dengan ID ${id} tidak ditemukan`
      });
    }

    res.status(200).json({
      success: true,
      data: book
    });

  } catch (error) {
    console.error('Error getBookById:', error);
    res.status(500).json({
      success: false,
      error: 'Internal Server Error',
      message: 'Gagal mengambil data buku'
    });
  }
};

/**
 * POST /api/v1/books
 * Tambah buku baru
 */
const createBook = (req, res) => {
  try {
    const { title, author, isbn, genre, publishedYear, available } = req.body;

    // Cek duplikasi ISBN
    const existingBook = booksData.findByIsbn(isbn);
    if (existingBook) {
      return res.status(409).json({
        success: false,
        error: 'Conflict',
        message: `Buku dengan ISBN ${isbn} sudah ada di sistem`,
        existingBook: { id: existingBook.id, title: existingBook.title }
      });
    }

    // Buat buku baru
    const newBook = booksData.create({
      title,
      author,
      isbn,
      genre,
      publishedYear,
      available
    });

    // 201 Created + Location header menunjuk ke resource baru
    res.status(201)
      .header('Location', `/api/v1/books/${newBook.id}`)
      .json({
        success: true,
        message: 'Buku berhasil ditambahkan',
        data: newBook
      });

  } catch (error) {
    console.error('Error createBook:', error);
    res.status(500).json({
      success: false,
      error: 'Internal Server Error',
      message: 'Gagal menambahkan buku'
    });
  }
};

/**
 * PUT /api/v1/books/:id
 * Ganti data buku sepenuhnya
 */
const replaceBook = (req, res) => {
  try {
    const { id } = req.params;

    if (isNaN(id)) {
      return res.status(400).json({
        success: false,
        error: 'Bad Request',
        message: 'ID buku harus berupa angka'
      });
    }

    // Cek apakah buku ada
    const existingBook = booksData.findById(id);
    if (!existingBook) {
      return res.status(404).json({
        success: false,
        error: 'Not Found',
        message: `Buku dengan ID ${id} tidak ditemukan`
      });
    }

    const { title, author, isbn, genre, publishedYear, available } = req.body;

    // Cek konflik ISBN (jika ISBN berubah)
    if (isbn !== existingBook.isbn) {
      const bookWithSameIsbn = booksData.findByIsbn(isbn);
      if (bookWithSameIsbn) {
        return res.status(409).json({
          success: false,
          error: 'Conflict',
          message: `ISBN ${isbn} sudah digunakan buku lain`
        });
      }
    }

    const updatedBook = booksData.replace(id, {
      title, author, isbn, genre, publishedYear, available
    });

    res.status(200).json({
      success: true,
      message: 'Buku berhasil diperbarui',
      data: updatedBook
    });

  } catch (error) {
    console.error('Error replaceBook:', error);
    res.status(500).json({
      success: false,
      error: 'Internal Server Error',
      message: 'Gagal memperbarui buku'
    });
  }
};

/**
 * PATCH /api/v1/books/:id
 * Update sebagian data buku
 */
const updateBook = (req, res) => {
  try {
    const { id } = req.params;

    if (isNaN(id)) {
      return res.status(400).json({
        success: false,
        error: 'Bad Request',
        message: 'ID buku harus berupa angka'
      });
    }

    const existingBook = booksData.findById(id);
    if (!existingBook) {
      return res.status(404).json({
        success: false,
        error: 'Not Found',
        message: `Buku dengan ID ${id} tidak ditemukan`
      });
    }

    // Hanya ambil field yang boleh diupdate
    const allowedFields = ['title', 'author', 'isbn', 'genre', 'publishedYear', 'available'];
    const updateData = {};

    allowedFields.forEach(field => {
      if (req.body[field] !== undefined) {
        updateData[field] = req.body[field];
      }
    });

    const updatedBook = booksData.update(id, updateData);

    res.status(200).json({
      success: true,
      message: 'Buku berhasil diperbarui',
      data: updatedBook
    });

  } catch (error) {
    console.error('Error updateBook:', error);
    res.status(500).json({
      success: false,
      error: 'Internal Server Error',
      message: 'Gagal memperbarui buku'
    });
  }
};

/**
 * DELETE /api/v1/books/:id
 * Hapus buku
 */
const deleteBook = (req, res) => {
  try {
    const { id } = req.params;

    if (isNaN(id)) {
      return res.status(400).json({
        success: false,
        error: 'Bad Request',
        message: 'ID buku harus berupa angka'
      });
    }

    const existingBook = booksData.findById(id);
    if (!existingBook) {
      return res.status(404).json({
        success: false,
        error: 'Not Found',
        message: `Buku dengan ID ${id} tidak ditemukan`
      });
    }

    booksData.delete(id);

    // 204 No Content - berhasil hapus, tidak ada body
    res.status(204).send();

  } catch (error) {
    console.error('Error deleteBook:', error);
    res.status(500).json({
      success: false,
      error: 'Internal Server Error',
      message: 'Gagal menghapus buku'
    });
  }
};

module.exports = {
  getAllBooks,
  getBookById,
  createBook,
  replaceBook,
  updateBook,
  deleteBook
};
```

```javascript
// src/routes/books.routes.js
// Definisi semua route untuk resource Books

const express = require('express');
const router = express.Router();
const booksController = require('../controllers/books.controller');
const { validateCreateBook, validateUpdateBook } = require('../middleware/validate');

// GET /api/v1/books - Ambil semua buku
router.get('/', booksController.getAllBooks);

// GET /api/v1/books/:id - Ambil satu buku
router.get('/:id', booksController.getBookById);

// POST /api/v1/books - Buat buku baru
router.post('/', validateCreateBook, booksController.createBook);

// PUT /api/v1/books/:id - Ganti buku sepenuhnya
router.put('/:id', validateCreateBook, booksController.replaceBook);

// PATCH /api/v1/books/:id - Update sebagian buku
router.patch('/:id', validateUpdateBook, booksController.updateBook);

// DELETE /api/v1/books/:id - Hapus buku
router.delete('/:id', booksController.deleteBook);

module.exports = router;
```

```javascript
// app.js - Entry point aplikasi

const express = require('express');
const app = express();

// ─── MIDDLEWARE GLOBAL ────────────────────────────────────────────────────────

// Parse JSON request body
app.use(express.json());

// Request logger
app.use((req, res, next) => {
  const start = Date.now();

  // Log saat response selesai
  res.on('finish', () => {
    const duration = Date.now() - start;
    const statusEmoji = res.statusCode < 400 ? '✅' : '❌';
    console.log(
      `${statusEmoji} [${new Date().toISOString()}] ` +
      `${req.method} ${req.originalUrl} ` +
      `→ ${res.statusCode} (${duration}ms)`
    );
  });

  next();
});

// ─── ROUTES ──────────────────────────────────────────────────────────────────

// Health check
app.get('/health', (req, res) => {
  res.status(200).json({
    status: 'healthy',
    service: 'Buku API',
    version: '1.0.0',
    uptime: Math.floor(process.uptime()),
    timestamp: new Date().toISOString()
  });
});

// API Routes dengan versioning
const booksRouter = require('./src/routes/books.routes');
app.use('/api/v1/books', booksRouter);

// ─── ERROR HANDLERS ───────────────────────────────────────────────────────────

// 404 Handler
app.use((req, res) => {
  res.status(404).json({
    success: false,
    error: 'Not Found',
    message: `Endpoint ${req.method} ${req.path} tidak ditemukan`,
    availableEndpoints: [
      'GET    /health',
      'GET    /api/v1/books',
      'GET    /api/v1/books/:id',
      'POST   /api/v1/books',
      'PUT    /api/v1/books/:id',
      'PATCH  /api/v1/books/:id',
      'DELETE /api/v1/books/:id'
    ]
  });
});

// Global Error Handler
app.use((err, req, res, next) => {
  console.error('Unhandled Error:', err);
  res.status(500).json({
    success: false,
    error: 'Internal Server Error',
    message: 'Terjadi kesalahan yang tidak terduga'
  });
});

// ─── START SERVER ─────────────────────────────────────────────────────────────

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log('═══════════════════════════════════════');
  console.log('  📚 Buku API Server');
  console.log('═══════════════════════════════════════');
  console.log(`  🚀 Running: http://localhost:${PORT}`);
  console.log(`  📋 Health:  http://localhost:${PORT}/health`);
  console.log(`  📖 Books:   http://localhost:${PORT}/api/v1/books`);
  console.log('═══════════════════════════════════════');
});

module.exports = app;
```

### Pengujian API

```bash
# ─── TEST SEMUA ENDPOINT ──────────────────────────────────────────────────────

# 1. GET semua buku
curl -s http://localhost:3000/api/v1/books | json_pp

# 2. GET dengan filter dan pagination
curl -s "http://localhost:3000/api/v1/books?genre=programming&page=1&limit=5" | json_pp

# 3. GET dengan pencarian
curl -s "http://localhost:3000/api/v1/books?search=clean" | json_pp

# 4. GET satu buku
curl -s http://localhost:3000/api/v1/books/1 | json_pp

# 5. POST - Tambah buku baru
curl -s -X POST http://localhost:3000/api/v1/books \
  -H "Content-Type: application/json" \
  -d '{
    "title": "JavaScript: The Good Parts",
    "author": "Douglas Crockford",
    "isbn": "978-0596517748",
    "genre": "programming",
    "publishedYear": 2008
  }' | json_pp

# 6. PATCH - Update status ketersediaan
curl -s -X PATCH http://localhost:3000/api/v1/books/1 \
  -H "Content-Type: application/json" \
  -d '{"available": false}' | json_pp

# 7. PUT - Ganti data sepenuhnya
curl -s -X PUT http://localhost:3000/api/v1/books/1 \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Clean Code (Revised Edition)",
    "author": "Robert C. Martin",
    "isbn": "978-0132350884",
    "genre": "programming",
    "publishedYear": 2008,
    "available": true
  }' | json_pp

# 8. DELETE - Hapus buku
curl -s -X DELETE http://localhost:3000/api/v1/books/1 -v

# 9. Test 404
curl -s http://localhost:3000/api/v1/books/999 | json_pp

# 10. Test validasi error
curl -s -X POST http://localhost:3000/api/v1/books \
  -H "Content-Type: application/json" \
  -d '{"title": ""}' | json_pp
```

---

# SECTION 11 — TRADE-OFFS & CONSIDERATIONS

## Trade-offs dalam Desain HTTP & REST API

### 1. REST vs GraphQL vs gRPC

```
┌─────────────────────────────────────────────────────────────────────┐
│              PERBANDINGAN PARADIGMA API                              │
├──────────────┬──────────────────┬──────────────────┬────────────────┤
│  Aspek       │  REST            │  GraphQL         │  gRPC          │
├──────────────┼──────────────────┼──────────────────┼────────────────┤
│  Protokol    │ HTTP/1.1, HTTP/2 │ HTTP/1.1, HTTP/2 │ HTTP/2         │
│  Format      │ JSON/XML         │ JSON             │ Protocol Buffer│
│  Typing      │ Tidak ada        │ Schema kuat      │ Schema kuat    │
│  Overfetch   │ Sering terjadi   │ Tidak ada        │ Tidak ada      │
│  Underfetch  │ Sering terjadi   │ Tidak ada        │ Tidak ada      │
│  Learning    │ Mudah            │ Sedang           │ Sulit          │
│  Tooling     │ Sangat banyak    │ Banyak           │ Terbatas       │
│  Browser     │ Native           │ Butuh library    │ Tidak langsung │
│  Caching     │ Mudah (HTTP)     │ Kompleks         │ Kompleks       │
│  Use case    │ Public API,      │ Mobile app,      │ Microservices, │
│              │ CRUD sederhana   │ complex queries  │ high perf      │
└──────────────┴──────────────────┴──────────────────┴────────────────┘

KAPAN PILIH REST:
✅ API publik yang akan digunakan banyak pihak
✅ Tim yang baru belajar API design
✅ CRUD sederhana tanpa query kompleks
✅ Butuh caching HTTP yang mudah

KAPAN PILIH GraphQL:
✅ Mobile app dengan bandwidth terbatas
✅ Data dengan relasi kompleks
✅ Multiple client dengan kebutuhan data berbeda

KAPAN PILIH gRPC:
✅ Komunikasi internal microservices
✅ Butuh performa sangat tinggi
✅ Streaming data real-time
```

### 2. Stateless vs Stateful

```
STATELESS (REST):
┌─────────────────────────────────────────────────────────┐
│  Request 1: POST /login → Token JWT                     │
│  Request 2: GET /profile + Token → Data user            │
│  Request 3: GET /orders + Token → Data orders           │
│                                                          │
│  ✅ Mudah di-scale horizontal                           │
│  ✅ Tidak ada session state di server                   │
│  ✅ Setiap server bisa handle request apapun            │
│  ❌ Token harus dikirim setiap request                  │
│  ❌ Token lebih besar dari session ID                   │
└─────────────────────────────────────────────────────────┘

STATEFUL (Session-based):
┌─────────────────────────────────────────────────────────┐
│  Request 1: POST /login → Session ID (cookie)           │
│  Request 2: GET /profile + Cookie → Data user           │
│  Request 3: GET /orders + Cookie → Data orders          │
│                                                          │
│  ✅ Token lebih kecil (hanya session ID)                │
│  ✅ Mudah invalidate session                            │
│  ❌ Server harus simpan session (memory/Redis)          │
│  ❌ Sticky session atau shared session store            │
└─────────────────────────────────────────────────────────┘
```

### 3. Versioning Strategy

```
OPSI 1: URL Path Versioning
GET /api/v1/users
GET /api/v2/users

✅ Paling jelas dan eksplisit
✅ Mudah di-test dan di-debug
❌ URL menjadi panjang
❌ Melanggar prinsip "URI sebagai resource identifier"

OPSI 2: Header Versioning
GET /api/users
Accept: application/vnd.myapi.v2+json

✅ URL bersih
✅ Lebih "RESTful"
❌ Tidak bisa di-test langsung dari browser
❌ Lebih sulit di-cache

OPSI 3: Query Parameter
GET /api/users?version=2

✅ Mudah di-test
❌ Bisa ter-cache dengan versi yang salah
❌ Kurang elegan

REKOMENDASI untuk Pemula: URL Path Versioning
→ Paling mudah dipahami dan di-debug
```

### 4. Response Format: Flat vs Nested

```javascript
// OPSI A: Flat Response
{
  "id": 1,
  "title": "Clean Code",
  "authorId": 5,
  "authorName": "Robert C. Martin",
  "authorEmail": "bob@example.com"
}

// OPSI B: Nested Response
{
  "id": 1,
  "title": "Clean Code",
  "author": {
    "id": 5,
    "name": "Robert C. Martin",
    "email": "bob@example.com"
  }
}

// OPSI C: JSON:API Standard
{
  "data": {
    "type": "books",
    "id": "1",
    "attributes": {
      "title": "Clean Code"
    },
    "relationships": {
      "author": {
        "data": { "type": "authors", "id": "5" }
      }
    }
  },
  "included": [
    {
      "type": "authors",
      "id": "5",
      "attributes": {
        "name": "Robert C. Martin"
      }
    }
  ]
}

TRADE-OFFS:
Flat    → Sederhana tapi data duplikat
Nested  → Intuitif tapi bisa sangat dalam
JSON:API → Standar tapi verbose
```

---

# SECTION 12 — BEST PRACTICES

## Best Practices Desain RESTful API

### 1. Penamaan Resource

```
✅ GUNAKAN:
/users                    → Noun, plural
/products/123             → Resource dengan ID
/users/123/orders         → Nested resource
/orders?status=pending    → Filter via query param

❌ HINDARI:
/getUsers                 → Verb dalam URL
/user                     → Singular
/users/getOrders          → Verb dalam nested
/users/123?action=delete  → Action via query param
```

### 2. Konsistensi Response Format

```javascript
// ✅ STANDAR RESPONSE FORMAT yang konsisten

// Success Response
{
  "success": true,
  "data": { ... },           // atau array
  "message": "Opsional",
  "meta": {                  // Opsional, untuk pagination
    "total": 100,
    "page": 1,
    "limit": 10
  }
}

// Error Response
{
  "success": false,
  "error": "Error Type",     // Kategori error
  "message": "Pesan human-readable",
  "details": [               // Opsional, untuk validasi
    { "field": "email", "message": "Format tidak valid" }
  ],
  "requestId": "req_abc123"  // Untuk debugging
}
```

### 3. Versioning API

```javascript
// ✅ Selalu gunakan versioning dari awal
app.use('/api/v1/books', booksRouterV1);
app.use('/api/v2/books', booksRouterV2);

// ✅ Dokumentasikan deprecation
app.use('/api/v1/books', (req, res, next) => {
  res.setHeader('Deprecation', 'true');
  res.setHeader('Sunset', 'Sat, 31 Dec 2024 23:59:59 GMT');
  res.setHeader('Link', '</api/v2/books>; rel="successor-version"');
  next();
}, booksRouterV1);
```

### 4. Pagination yang Baik

```javascript
// ✅ Response pagination yang informatif
{
  "success": true,
  "data": [...],
  "pagination": {
    "total": 150,
    "page": 2,
    "limit": 10,
    "totalPages": 15,
    "hasNextPage": true,
    "hasPrevPage": true,
    "links": {
      "self":  "/api/v1/books?page=2&limit=10",
      "first": "/api/v1/books?page=1&limit=10",
      "prev":  "/api/v1/books?page=1&limit=10",
      "next":  "/api/v1/books?page=3&limit=10",
      "last":  "/api/v1/books?page=15&limit=10"
    }
  }
}
```

### 5. Security Headers

```javascript
// ✅ Tambahkan security headers
const helmet = require('helmet');
app.use(helmet());

// Atau manual:
app.use((req, res, next) => {
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('X-Frame-Options', 'DENY');
  res.setHeader('X-XSS-Protection', '1; mode=block');
  res.setHeader('Strict-Transport-Security', 'max-age=31536000');
  next();
});
```

### 6. Rate Limiting

```javascript
// ✅ Implementasi rate limiting
const rateLimit = require('express-rate-limit');

const limiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 menit
  max: 100,                  // Maksimal 100 request per window
  message: {
    success: false,
    error: 'Too Many Requests',
    message: 'Terlalu banyak request. Coba lagi dalam 15 menit.',
    retryAfter: '15 minutes'
  },
  headers: true              // Tambahkan X-RateLimit-* headers
});

app.use('/api/', limiter);
```

### 7. Checklist Desain API

```
CHECKLIST SEBELUM DEPLOY API:

NAMING & STRUCTURE:
□ Semua endpoint menggunakan noun (bukan verb)
□ Resource name menggunakan plural
□ URL menggunakan lowercase dan kebab-case
□ Versioning sudah ada (/api/v1/)

HTTP METHODS:
□ GET tidak mengubah data
□ POST untuk create, mengembalikan 201
□ PUT untuk replace, idempoten
□ PATCH untuk partial update
□ DELETE mengembalikan 204

STATUS CODES:
□ Status code sesuai dengan situasi
□ Error response memiliki pesan yang jelas
□ Validasi error menunjukkan field yang bermasalah

RESPONSE FORMAT:
□ Format response konsisten di semua endpoint
□ Pagination ada untuk list endpoint
□ Timestamp menggunakan ISO 8601

SECURITY:
□ Input divalidasi dan disanitasi
□ Authentication diperlukan untuk endpoint sensitif
□ Rate limiting aktif
□ CORS dikonfigurasi dengan benar

DOCUMENTATION:
□ Semua endpoint terdokumentasi
□ Request/response example tersedia
□ Error codes terdokumentasi
```

---

# SECTION 13 — COMMON MISTAKES & HOW TO AVOID THEM

## Kesalahan Umum dan Cara Menghindarinya

### Kesalahan #1: Menggunakan GET untuk Operasi yang Mengubah Data

```javascript
// ❌ SALAH - GET mengubah data
app.get('/users/delete/:id', (req, res) => {
  // Ini sangat berbahaya!
  // Browser bisa pre-fetch URL ini
  // Log/cache bisa menyimpan URL ini
  deleteUser(req.params.id);
  res.json({ message: 'Deleted' });
});

// ✅ BENAR - Gunakan DELETE
app.delete('/users/:id', (req, res) => {
  deleteUser(req.params.id);
  res.status(204).send();
});
```

### Kesalahan #2: Status Code yang Tidak Tepat

```javascript
// ❌ SALAH - Selalu 200 meski ada error
app.get('/users/:id', (req, res) => {
  const user = findUser(req.params.id);
  if (!user) {
    return res.status(200).json({  // ← SALAH!
      success: false,
      message: 'User not found'
    });
  }
  res.json(user);
});

// ✅ BENAR - Status code yang tepat
app.get('/users/:id', (req, res) => {
  const user = findUser(req.params.id);
  if (!user) {
    return res.status(404).json({  // ← BENAR
      success: false,
      error: 'Not Found',
      message: `User dengan ID ${req.params.id} tidak ditemukan`
    });
  }
  res.status(200).json({ success: true, data: user });
});
```

### Kesalahan #3: Mengekspos Detail Error Internal

```javascript
// ❌ SALAH - Mengekspos stack trace ke client
app.get('/users', async (req, res) => {
  try {
    const users = await db.query('SELECT * FROM users');
    res.json(users);
  } catch (error) {
    res.status(500).json({
      error: error.message,        // ← Bisa ekspos info sensitif
      stack: error.stack           // ← JANGAN PERNAH kirim ini!
    });
  }
});

// ✅ BENAR - Log internal, kirim pesan generik
app.get('/users', async (req, res) => {
  try {
    const users = await db.query('SELECT * FROM users');
    res.json(users);
  } catch (error) {
    // Log detail error di server (untuk debugging)
    console.error('Database error:', error);

    // Kirim pesan generik ke client
    res.status(500).json({
      success: false,
      error: 'Internal Server Error',
      message: 'Gagal mengambil data pengguna',
      requestId: req.id  // ID untuk tracking, bukan detail error
    });
  }
});
```

### Kesalahan #4: Tidak Memvalidasi Input

```javascript
// ❌ SALAH - Langsung gunakan input tanpa validasi
app.post('/users', (req, res) => {
  const user = createUser(req.body);  // SQL Injection? XSS? 😱
  res.json(user);
});

// ✅ BENAR - Validasi dan sanitasi semua input
app.post('/users', (req, res) => {
  const { name, email, age } = req.body;

  // Validasi
  if (!name || typeof name !== 'string') {
    return res.status(400).json({
      error: 'Validation Error',
      details: [{ field: 'name', message: 'Nama wajib diisi' }]
    });
  }

  if (!email || !isValidEmail(email)) {
    return res.status(400).json({
      error: 'Validation Error',
      details: [{ field: 'email', message: 'Format email tidak valid' }]
    });
  }

  // Sanitasi
  const sanitizedData = {
    name: name.trim().substring(0, 100),  // Batasi panjang
    email: email.toLowerCase().trim(),
    age: parseInt(age)
  };

  const user = createUser(sanitizedData);
  res.status(201).json({ success: true, data: user });
});
```

### Kesalahan #5: Tidak Konsisten dalam Response Format

```javascript
// ❌ SALAH - Format berbeda di setiap endpoint
app.get('/users', (req, res) => {
  res.json([{ id: 1, name: 'Budi' }]);  // Array langsung
});

app.get('/products', (req, res) => {
  res.json({ products: [...], count: 10 });  // Wrapped berbeda
});

app.get('/orders', (req, res) => {
  res.json({ data: [...], total: 5, success: true });  // Format lain
});

// ✅ BENAR - Format konsisten
const sendSuccess = (res, data, statusCode = 200, meta = null) => {
  const response = { success: true, data };
  if (meta) response.meta = meta;
  res.status(statusCode).json(response);
};

app.get('/users', (req, res) => {
  sendSuccess(res, users, 200, { total: users.length });
});

app.get('/products', (req, res) => {
  sendSuccess(res, products, 200, { total: products.length });
});
```

---

# SECTION 14 — HANDS-ON EXERCISE

## Latihan Praktis

### Latihan 1: Analisis API (15 menit)

Analisis endpoint berikut dan identifikasi masalahnya:

```
ENDPOINT YANG PERLU DIANALISIS:

1. GET /api/getAllActiveUsers
2. POST /api/user/delete?id=5
3. GET /api/createNewProduct
4. POST /api/updateUserEmail
5. DELETE /api/users/remove/123
6. GET /api/orders/user/123/getOrderHistory
7. POST /api/v1/books/search
8. GET /api/users?action=deactivate&id=456
```

**Jawaban yang diharapkan:**

```
1. GET /api/getAllActiveUsers
   ❌ Masalah: Verb dalam URL, tidak plural konsisten
   ✅ Perbaikan: GET /api/v1/users?status=active

2. POST /api/user/delete?id=5
   ❌ Masalah: Verb "delete" dalam URL, gunakan DELETE method
   ✅ Perbaikan: DELETE /api/v1/users/5

3. GET /api/createNewProduct
   ❌ Masalah: GET tidak boleh membuat data, verb dalam URL
   ✅ Perbaikan: POST /api/v1/products

4. POST /api/updateUserEmail
   ❌ Masalah: Verb dalam URL
   ✅ Perbaikan: PATCH /api/v1/users/:id (body: {email: "..."})

5. DELETE /api/users/remove/123
   ❌ Masalah: "remove" adalah verb yang redundan
   ✅ Perbaikan: DELETE /api/v1/users/123

6. GET /api/orders/user/123/getOrderHistory
   ❌ Masalah: Verb dalam URL, struktur tidak jelas
   ✅ Perbaikan: GET /api/v1/users/123/orders

7. POST /api/v1/books/search
   ❌ Masalah: Search seharusnya via GET dengan query params
   ✅ Perbaikan: GET /api/v1/books?search=keyword

8. GET /api/users?action=deactivate&id=456
   ❌ Masalah: GET mengubah state, action via query param
   ✅ Perbaikan: PATCH /api/v1/users/456 (body: {active: false})
```

### Latihan 2: Implementasi Endpoint Baru (45 menit)

Tambahkan fitur berikut ke API Buku yang sudah dibuat:

```
TUGAS:
1. GET /api/v1/books/:id/reviews
   → Ambil semua review untuk buku tertentu

2. POST /api/v1/books/:id/reviews
   → Tambah review baru untuk buku
   → Body: { rating: 1-5, comment: "string" }

3. GET /api/v1/stats
   → Statistik: total buku, buku tersedia, per genre

KRITERIA PENILAIAN:
□ Status code yang tepat
□ Validasi input
□ Response format konsisten
□ Error handling
□ Kode bersih dan terdokumentasi
```

### Latihan 3: Debugging API (30 menit)

Temukan dan perbaiki bug dalam kode berikut:

```javascript
// KODE DENGAN BUG - Temukan minimal 5 masalah!

app.post('/users', (req, res) => {
  const user = req.body;

  if (!user.email) {
    res.status(200).json({ error: 'Email required' });
  }

  const newUser = createUser(user);

  res.status(200).json(newUser);
});

app.get('/users/:id', (req, res) => {
  const user = findUser(req.params.id);
  res.json(user);
});

app.delete('/users/:id', (req, res) => {
  deleteUser(req.params.id);
  res.status(200).json({ message: 'Deleted' });
});
```

---

# SECTION 15 — QUIZ & KNOWLEDGE CHECK

## Kuis Pemahaman

### Soal Pilihan Ganda

**1. HTTP method mana yang IDEMPOTEN?**
```
A. POST
B. GET ✅
C. POST dan GET
D. Tidak ada yang idempoten
```

**2. Status code yang tepat saat berhasil membuat resource baru adalah:**
```
A. 200 OK
B. 201 Created ✅
C. 204 No Content
D. 202 Accepted
```

**3. Endpoint mana yang paling RESTful?**
```
A. GET /api/getUserById?id=5
B. GET /api/user/5
C. GET /api/v1/users/5 ✅
D. POST /api/v1/getUser/5
```

**4. Apa perbedaan utama antara PUT dan PATCH?**
```
A. PUT lebih cepat dari PATCH
B. PUT mengganti resource sepenuhnya, PATCH hanya sebagian ✅
C. PATCH mengganti resource sepenuhnya, PUT hanya sebagian
D. Tidak ada perbedaan
```

**5. Header mana yang digunakan untuk autentikasi Bearer Token?**
```
A. X-Auth-Token: Bearer <token>
B. Token: Bearer <token>
C. Authorization: Bearer <token> ✅
D. Auth: Bearer <token>
```

**6. Apa yang dimaksud "stateless" dalam REST?**
```
A. Server tidak menyimpan state apapun
B. Setiap request harus mengandung semua informasi yang diperlukan ✅
C. Client tidak menyimpan state
D. Database tidak menyimpan state
```

**7. Status code yang tepat saat user tidak memiliki izin akses (sudah login)?**
```
A. 401 Unauthorized
B. 404 Not Found
C. 403 Forbidden ✅
D. 400 Bad Request
```

**8. Cara terbaik untuk implementasi pagination adalah:**
```
A. Kirim semua data sekaligus
B. Gunakan query parameter ?page=1&limit=10 ✅
C. Gunakan header X-Page
D. Gunakan path /users/page/1
```

### Soal Essay Singkat

**9. Jelaskan mengapa REST menggunakan prinsip "stateless" dan apa keuntungannya untuk scalability?**

```
JAWABAN YANG DIHARAPKAN:

REST stateless berarti setiap HTTP request harus mengandung 
semua informasi yang diperlukan server untuk memproses request 
tersebut, tanpa bergantung pada konteks dari request sebelumnya.

Keuntungan untuk scalability:
1. Setiap request dapat diproses oleh server mana pun dalam cluster
   → Tidak perlu sticky session
2. Load balancer dapat mendistribusikan request secara bebas
   → Horizontal scaling mudah dilakukan
3. Server tidak perlu menyimpan session state
   → Penggunaan memori lebih efisien
4. Jika satu server mati, request berikutnya bisa ke server lain
   → Fault tolerance lebih baik
```

**10. Kapan Anda akan menggunakan PATCH vs PUT? Berikan contoh nyata.**

```
JAWABAN YANG DIHARAPKAN:

PUT digunakan ketika ingin mengganti SELURUH resource:
→ Contoh: User mengisi form profil lengkap dan submit
  PUT /users/123
  Body: { name, email, phone, address, birthdate }
  Semua field harus ada, field yang tidak dikirim akan hilang

PATCH digunakan ketika ingin mengubah SEBAGIAN field:
→ Contoh: User hanya mengubah nomor telepon
  PATCH /users/123
  Body: { phone: "081234567890" }
  Hanya phone yang berubah, field lain tetap

Aturan praktis:
- Jika client mengirim representasi lengkap → PUT
- Jika client mengirim perubahan parsial → PATCH
```

---

# SECTION 16 — REAL-WORLD CASE STUDY

## Studi Kasus: Redesign API E-Commerce

### Situasi

Anda bergabung sebagai backend developer di startup e-commerce "TokoKita". API yang ada saat ini memiliki banyak masalah:

```
API LAMA (Bermasalah):

POST /api/getProducts
POST /api/searchProducts
GET  /api/addToCart?productId=5&userId=3
GET  /api/removeFromCart?cartItemId=8
POST /api/doCheckout
GET  /api/getUserOrders?userId=3
POST /api/cancelOrder?orderId=10
GET  /api/getProductReviews?productId=5
POST /api/addReview
GET  /api/deleteReview?reviewId=2
```

### Analisis Masalah

```
MASALAH YANG DITEMUKAN:

1. Verb dalam URL (getProducts, searchProducts, doCheckout)
2. GET digunakan untuk operasi yang mengubah data (addToCart, removeFromCart)
3. Tidak ada versioning
4. Tidak konsisten (kadang query param, kadang tidak)
5. Tidak menggunakan HTTP method yang tepat
6. Tidak ada struktur resource yang jelas
```

### Solusi: Redesign API

```
API BARU (RESTful):

PRODUCTS:
GET    /api/v1/products                    → List produk
GET    /api/v1/products?search=baju        → Cari produk
GET    /api/v1/products?category=fashion   → Filter kategori
GET    /api/v1/products/:id                → Detail produk
GET    /api/v1/products/:id/reviews        → Review produk
POST   /api/v1/products/:id/reviews        → Tambah review
DELETE /api/v1/reviews/:id                 → Hapus review

CART:
GET    /api/v1/cart                        → Lihat keranjang
POST   /api/v1/cart/items                  → Tambah ke keranjang
PATCH  /api/v1/cart/items/:id              → Update quantity
DELETE /api/v1/cart/items/:id              → Hapus dari keranjang
DELETE /api/v1/cart                        → Kosongkan keranjang

ORDERS:
GET    /api/v1/orders                      → List pesanan user
GET    /api/v1/orders/:id                  → Detail pesanan
POST   /api/v1/orders                      → Buat pesanan (checkout)
PATCH  /api/v1/orders/:id/cancel           → Batalkan pesanan
```

### Implementasi Perubahan Bertahap

```javascript
// Strategy: Deprecate lama, perkenalkan baru secara bertahap

// Fase 1: Tambah API baru, pertahankan yang lama
app.post('/api/getProducts', deprecationWarning('/api/v1/products'), oldGetProducts);
app.get('/api/v1/products', newGetProducts);  // ← API baru

// Middleware deprecation warning
function deprecationWarning(newEndpoint) {
  return (req, res, next) => {
    res.setHeader('Deprecation', 'true');
    res.setHeader('Sunset', 'Sat, 31 Dec 2024 23:59:59 GMT');
    res.setHeader('Link', `<${newEndpoint}>; rel="successor-version"`);
    res.setHeader('Warning', `299 - "Endpoint ini deprecated. Gunakan ${newEndpoint}"`);
    next();
  };
}

// Fase 2: Komunikasikan ke semua consumer API
// Fase 3: Monitor penggunaan endpoint lama
// Fase 4: Hapus endpoint lama setelah sunset date
```

### Hasil Setelah Redesign

```
METRIK SEBELUM vs SESUDAH:

┌─────────────────────────────────────────────────────────┐
│  Metrik                  │  Sebelum  │  Sesudah         │
├─────────────────────────────────────────────────────────┤
│  Waktu onboarding dev    │  2 minggu │  3 hari          │
│  Bug integrasi per bulan │  15       │  3               │
│  Waktu debug API issue   │  4 jam    │  45 menit        │
│  Kepuasan developer      │  3/10     │  8/10            │
│  Dokumentasi coverage    │  40%      │  95%             │
└─────────────────────────────────────────────────────────┘
```

---

# SECTION 17 — TOOLS & ECOSYSTEM

## Tools untuk Bekerja dengan HTTP & REST API

### 1. API Testing Tools

```
POSTMAN / INSOMNIA
─────────────────────────────────────────────────────────
Fungsi: GUI untuk test API
Fitur:
  ✅ Simpan koleksi request
  ✅ Environment variables (dev/staging/prod)
  ✅ Automated testing
  ✅ Generate dokumentasi
  ✅ Mock server

Cara install:
→ Download dari postman.com atau insomnia.rest

CURL (Command Line)
─────────────────────────────────────────────────────────
Fungsi: Test API dari terminal
Contoh penggunaan:

# GET request
curl -X GET http://localhost:3000/api/v1/books

# POST dengan JSON body
curl -X POST http://localhost:3000/api/v1/books \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer token123" \
  -d '{"title": "New Book", "author": "Author Name"}' \
  -v  # verbose: tampilkan headers

# Simpan response ke file
curl http://localhost:3000/api/v1/books -o response.json

HTTPIE (User-friendly curl)
─────────────────────────────────────────────────────────
pip install httpie

# Lebih mudah dibaca
http GET localhost:3000/api/v1/books
http POST localhost:3000/api/v1/books title="New Book" author="Author"
http PATCH localhost:3000/api/v1/books/1 available:=false
```

### 2. API Documentation Tools

```
SWAGGER / OPENAPI
─────────────────────────────────────────────────────────
npm install swagger-ui-express swagger-jsdoc

// Contoh dokumentasi dengan JSDoc
/**
 * @swagger
 * /api/v1/books:
 *   get:
 *     summary: Ambil semua buku
 *     tags: [Books]
 *     parameters:
 *       - in: query
 *         name: page
 *         schema:
 *           type: integer
 *         description: Nomor halaman
 *     responses:
 *       200:
 *         description: Daftar buku berhasil diambil
 *         content:
 *           application/json:
 *             schema:
 *               type: object
 *               properties:
 *                 success:
 *                   type: boolean
 *                 data:
 *                   type: array
 */
```

### 3. Development Tools

```
NODEMON - Auto-restart server saat file berubah
─────────────────────────────────────────────────────────
npm install --save-dev nodemon

// package.json
{
  "scripts": {
    "dev": "nodemon app.js",
    "start": "node app.js"
  }
}

MORGAN - HTTP Request Logger
─────────────────────────────────────────────────────────
npm install morgan

const morgan = require('morgan');
app.use(morgan('dev'));
// Output: GET /api/v1/books 200 15ms - 256b

DOTENV - Environment Variables
─────────────────────────────────────────────────────────
npm install dotenv

// .env file
PORT=3000
NODE_ENV=development
API_VERSION=v1

// app.js
require('dotenv').config();
const PORT = process.env.PORT || 3000;
```

### 4. Browser DevTools untuk HTTP

```
CHROME DEVTOOLS → Network Tab
─────────────────────────────────────────────────────────
Cara akses: F12 → Network

Yang bisa dilihat:
├── Semua HTTP request yang dibuat halaman
├── Request headers dan body
├── Response headers dan body
├── Status code
├── Timing (DNS, TCP, TTFB, Download)
└── Waterfall diagram

Tips berguna:
→ Filter by XHR/Fetch untuk melihat API calls saja
→ Klik kanan request → Copy as cURL
→ Throttle network untuk simulasi koneksi lambat
```

---

# SECTION 18 — ADVANCED CONCEPTS PREVIEW

## Pratinjau Konsep Lanjutan

### Konsep yang Akan Dipelajari di Modul Berikutnya

```
┌─────────────────────────────────────────────────────────────────────┐
│              ROADMAP PEMBELAJARAN SELANJUTNYA                        │
│                                                                      │
│  MODULE 01 (SEKARANG)                                               │
│  ✅ HTTP Protocol dasar                                             │
│  ✅ REST principles                                                 │
│  ✅ CRUD API sederhana                                              │
│                                                                      │
│  MODULE 02: Authentication & Authorization                          │
│  → JWT (JSON Web Token)                                             │
│  → Session-based auth                                               │
│  → OAuth 2.0 dasar                                                  │
│  → Role-based access control (RBAC)                                 │
│                                                                      │
│  MODULE 03: Database Integration                                    │
│  → Koneksi ke PostgreSQL/MySQL                                      │
│  → ORM (Sequelize/Prisma)                                           │
│  → Query optimization                                               │
│  → Transaction handling                                             │
│                                                                      │
│  MODULE 04: Middleware & Error Handling                             │
│  → Custom middleware                                                │
│  → Global error handling                                            │
│  → Request validation (Joi/Zod)                                     │
│  → Logging (Winston)                                                │
│                                                                      │
│  MODULE 05: API Security                                            │
│  → Input sanitization                                               │
│  → SQL Injection prevention                                         │
│  → XSS prevention                                                   │
│  → CORS configuration                                               │
│  → Rate limiting                                                    │
└─────────────────────────────────────────────────────────────────────┘
```

### Konsep Lanjutan: HATEOAS

```javascript
// HATEOAS: Hypermedia as the Engine of Application State
// Response menyertakan link ke aksi yang tersedia

// Contoh response HATEOAS untuk buku:
{
  "success": true,
  "data": {
    "id": 1,
    "title": "Clean Code",
    "available": true,
    "_links": {
      "self": {
        "href": "/api/v1/books/1",
        "method": "GET"
      },
      "update": {
        "href": "/api/v1/books/1",
        "method": "PATCH"
      },
      "delete": {
        "href": "/api/v1/books/1",
        "method": "DELETE"
      },
      "reviews": {
        "href": "/api/v1/books/1/reviews",
        "method": "GET"
      },
      "borrow": {
        "href": "/api/v1/books/1/borrow",
        "method": "POST",
        "available": true
      }
    }
  }
}
// Client tidak perlu "tahu" URL yang tersedia
// Server yang memberitahu aksi apa yang bisa dilakukan
```

### HTTP/2 dan HTTP/3

```
HTTP/1.1 (Saat ini paling umum):
├── Satu request per koneksi TCP
├── Head-of-line blocking
└── Header tidak dikompresi

HTTP/2 (Sudah banyak digunakan):
├── Multiplexing: banyak request dalam satu koneksi
├── Header compression (HPACK)
├── Server push
└── Binary protocol (bukan text)

HTTP/3 (Masa depan):
├── Berbasis QUIC (bukan TCP)
├── Mengatasi head-of-line blocking di level transport
├── Koneksi lebih cepat (0-RTT)
└── Lebih baik di jaringan tidak stabil
```

---

# SECTION 19 — SUMMARY & KEY TAKEAWAYS

## Ringkasan dan Poin Kunci

### Yang Telah Dipelajari

```
┌─────────────────────────────────────────────────────────────────────┐
│                    RINGKASAN MODUL 01                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  1. HTTP PROTOCOL                                                   │
│     • Request terdiri dari: Method, URL, Headers, Body              │
│     • Response terdiri dari: Status Code, Headers, Body             │
│     • HTTP bersifat stateless dan text-based                        │
│                                                                      │
│  2. HTTP METHODS                                                    │
│     • GET    → Baca data (safe, idempoten)                         │
│     • POST   → Buat data baru (tidak idempoten)                    │
│     • PUT    → Ganti sepenuhnya (idempoten)                        │
│     • PATCH  → Update sebagian                                     │
│     • DELETE → Hapus data (idempoten)                              │
│                                                                      │
│  3. STATUS CODES                                                    │
│     • 2xx → Sukses (200, 201, 204)                                 │
│     • 4xx → Error client (400, 401, 403, 404, 409)                │
│     • 5xx → Error server (500, 502, 503)                           │
│                                                                      │
│  4. REST PRINCIPLES                                                 │
│     • Resource-based (noun, bukan verb)                            │
│     • Stateless                                                     │
│     • Uniform interface                                             │
│     • Client-server separation                                      │
│                                                                      │
│  5. API DESIGN BEST PRACTICES                                       │
│     • Konsisten dalam naming dan response format                    │
│     • Selalu gunakan versioning                                     │
│     • Validasi semua input                                          │
│     • Handle error dengan baik                                      │
│     • Dokumentasikan API                                            │
│                                                                      │
│  6. IMPLEMENTASI                                                    │
│     • Express.js untuk routing                                      │
│     • Middleware untuk validasi dan logging                         │
│     • Controller pattern untuk separation of concerns              │
│     • Proper error handling                                         │
└─────────────────────────────────────────────────────────────────────┘
```

### Mental Model: REST API sebagai Bahasa

```
ANALOGI BAHASA:

HTTP Method  ←→  Kata Kerja (Verb)
  GET             Ambil/Baca
  POST            Buat/Kirim
  PUT             Ganti
  PATCH           Perbarui
  DELETE          Hapus

URL/Resource ←→  Kata Benda (Noun)
  /users          Pengguna
  /products       Produk
  /orders         Pesanan

Status Code  ←→  Ekspresi/Respons
  200             "Oke, ini hasilnya"
  201             "Berhasil dibuat!"
  404             "Tidak ada yang namanya itu"
  403             "Kamu tidak boleh masuk sini"
  500             "Maaf, ada masalah di pihak kami"

Jadi: "DELETE /users/123" dibaca sebagai:
→ "Hapus pengguna nomor 123"
```

### Checklist Kompetensi

```
SELF-ASSESSMENT - Centang jika sudah bisa:

HTTP FUNDAMENTALS:
□ Saya bisa menjelaskan perbedaan GET, POST, PUT, PATCH, DELETE
□ Saya memahami anatomi HTTP request dan response
□ Saya bisa memilih status code yang tepat untuk setiap situasi
□ Saya memahami fungsi HTTP headers yang umum

REST DESIGN:
□ Saya bisa merancang URL endpoint yang RESTful
□ Saya memahami prinsip stateless dan implikasinya
□ Saya bisa membedakan REST yang baik dan buruk
□ Saya memahami konsep resource dan representasi

IMPLEMENTASI:
□ Saya bisa membuat Express server dari nol
□ Saya bisa mengimplementasikan CRUD endpoint lengkap
□ Saya bisa membuat middleware validasi
□ Saya bisa menangani error dengan benar
□ Saya bisa menguji API dengan curl atau Postman

BEST PRACTICES:
□ Saya selalu memvalidasi input
□ Saya menggunakan response format yang konsisten
□ Saya tidak mengekspos detail error internal
□ Saya menggunakan versioning API
```

---

# SECTION 20 — REFERENCES & FURTHER READING

## Referensi dan Bacaan Lanjutan

### Dokumentasi Resmi

```
1. HTTP/1.1 Specification
   → RFC 7230-7235 (IETF)
   → https://tools.ietf.org/html/rfc7230

2. HTTP/2 Specification
   → RFC 7540 (IETF)
   → https://tools.ietf.org/html/rfc7540

3. REST Architectural Style
   → Roy Fielding's Dissertation (2000)
   → https://www.ics.uci.edu/~fielding/pubs/dissertation/rest_arch_style.htm

4. Express.js Documentation
   → https://expressjs.com/en/guide/routing.html

5. MDN Web Docs - HTTP
   → https://developer.mozilla.org/en-US/docs/Web/HTTP
```

### Buku Rekomendasi

```
LEVEL PEMULA:
📚 "RESTful Web APIs" - Leonard Richardson & Mike Amundsen
   → Penjelasan REST yang sangat komprehensif

📚 "Node.js Design Patterns" - Mario Casciaro
   → Pattern untuk backend Node.js

LEVEL MENENGAH:
📚 "Building Microservices" - Sam Newman
   → API design dalam konteks microservices

📚 "API Design Patterns" - JJ Geewax
   → Pattern lanjutan untuk API design

LEVEL LANJUT:
📚 "Designing Distributed Systems" - Brendan Burns
   → Sistem terdistribusi dan API
```

### Artikel & Tutorial Online

```
WAJIB DIBACA:
→ "Best Practices for REST API Design" - Stack Overflow Blog
→ "HTTP Status Codes Decision Diagram" - Restlet
→ "REST API Tutorial" - restfulapi.net
→ "Microsoft REST API Guidelines" - GitHub Microsoft

TOOLS DOKUMENTASI:
→ Swagger/OpenAPI: swagger.io
→ Postman Learning Center: learning.postman.com
→ Insomnia Docs: docs.insomnia.rest

KOMUNITAS:
→ r/webdev - Reddit
→ Dev.to - artikel komunitas
→ Stack Overflow - Q&A
→ Discord: Programmer Indonesia
```

### Proyek Latihan Mandiri

```
PROYEK UNTUK PORTFOLIO:

LEVEL 1 (Minggu ini):
□ API Todo List dengan CRUD lengkap
□ API Kontak dengan search dan filter
□ API Catatan dengan kategori

LEVEL 2 (Bulan ini):
□ API Blog dengan users, posts, comments
□ API Inventory management
□ API Booking sistem sederhana

LEVEL 3 (Setelah modul ini selesai):
□ API E-commerce mini (products, cart, orders)
□ API Social media sederhana
□ API dengan autentikasi JWT

TIPS:
→ Upload ke GitHub dengan README yang baik
→ Deploy ke Railway/Render (gratis)
→ Buat dokumentasi Swagger
→ Tulis unit test untuk setiap endpoint
```

### Glosarium Istilah Penting

```
GLOSARIUM:

API (Application Programming Interface)
→ Antarmuka yang memungkinkan aplikasi berkomunikasi

Endpoint
→ URL spesifik yang menerima request API

HTTP (HyperText Transfer Protocol)
→ Protokol komunikasi web

Idempoten
→ Operasi yang menghasilkan efek sama meski dipanggil berkali-kali

JSON (JavaScript Object Notation)
→ Format pertukaran data berbasis teks

Middleware
→ Fungsi yang berjalan antara request dan response handler

REST (Representational State Transfer)
→ Gaya arsitektur untuk API

Resource
→ Entitas yang dapat diidentifikasi dan dimanipulasi via API

Stateless
→ Setiap request berdiri sendiri tanpa konteks sebelumnya

URI (Uniform Resource Identifier)
→ String yang mengidentifikasi resource

URL (Uniform Resource Locator)
→ URI yang juga menentukan cara mengakses resource

Versioning
→ Strategi mengelola perubahan API tanpa merusak client lama
```

---

## Penutup Modul

```
╔═════════════════════════════════════════════════════════════════════╗
║                    SELAMAT! 🎉                                      ║
║                                                                     ║
║  Anda telah menyelesaikan Bab 07 Module 01:                        ║
║  HTTP Protocol & RESTful API Design                                 ║
║                                                                     ║
║  Anda sekarang memiliki fondasi yang kuat untuk:                   ║
║  ✅ Memahami cara kerja web communication                           ║
║  ✅ Merancang API yang bersih dan konsisten                         ║
║  ✅ Mengimplementasikan RESTful API dengan Express                  ║
║  ✅ Menangani error dengan profesional                              ║
║                                                                     ║
║  LANGKAH SELANJUTNYA:                                               ║
║  → Kerjakan semua latihan di Section 14                            ║
║  → Bangun proyek portfolio Level 1                                  ║
║  → Lanjut ke Module 02: Authentication & Authorization             ║
║                                                                     ║
║  "A well-designed API is a gift to developers.                     ║
║   A poorly-designed one is a curse that lasts years."              ║
║                                    — Wisdom of the Backend         ║
╚═════════════════════════════════════════════════════════════════════╝
```

---

*Dokumen ini adalah bagian dari kurikulum **backend-beginner** kategori **01-Core-Foundations**.*
*Versi: 1.0.0 | Terakhir diperbarui: 2024 | Lisensi: MIT*