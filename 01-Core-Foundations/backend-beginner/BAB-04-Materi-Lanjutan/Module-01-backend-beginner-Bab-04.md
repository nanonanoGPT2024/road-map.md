# Bab 04 Module 01: HTTP & Web Fundamentals — Cara Internet Berkomunikasi

## Kurikulum: Backend Beginner | Kategori: 01-Core-Foundations

---

# SECTION 01 — LEARNING OBJECTIVES

## Tujuan Pembelajaran

Setelah menyelesaikan modul ini, peserta didik akan mampu:

**Pengetahuan (Knowledge):**
- Menjelaskan arsitektur client-server dan peran masing-masing komponen dalam komunikasi web
- Mendefinisikan protokol HTTP dan HTTPS beserta perbedaan fundamental keduanya
- Mengidentifikasi anatomi lengkap HTTP Request dan HTTP Response
- Menyebutkan seluruh HTTP Methods beserta semantik penggunaannya yang tepat
- Mengklasifikasikan HTTP Status Codes berdasarkan kategori dan maknanya

**Pemahaman (Comprehension):**
- Menjelaskan siklus lengkap request-response dari browser hingga server dan kembali
- Menginterpretasikan HTTP Headers yang umum digunakan dalam request dan response
- Membedakan stateless vs stateful communication dan implikasinya pada desain backend
- Menjelaskan konsep URL, URI, dan Query Parameters secara struktural

**Penerapan (Application):**
- Menganalisis HTTP traffic menggunakan browser DevTools dan tools seperti curl
- Merancang endpoint URL yang semantik dan RESTful
- Memilih HTTP Method yang tepat untuk setiap operasi CRUD
- Mengimplementasikan response dengan status code yang akurat dan headers yang sesuai

**Analisis (Analysis):**
- Membandingkan trade-off antara berbagai pendekatan desain HTTP API
- Mendiagnosis masalah komunikasi HTTP dari log dan error messages
- Mengevaluasi keamanan dasar komunikasi HTTP vs HTTPS

---

# SECTION 02 — PREREQUISITES & CONTEXT

## Prasyarat dan Konteks Modul

### Prasyarat Wajib
Sebelum memulai modul ini, peserta didik harus telah menguasai:

```
✅ Bab 01: Pengenalan Backend Development
   └── Memahami apa itu server dan client secara konseptual

✅ Bab 02: Lingkungan Development
   └── Terminal/CLI dasar, instalasi tools

✅ Bab 03: Dasar-dasar Jaringan Komputer
   └── IP Address, DNS, Port, TCP/IP dasar
```

### Posisi Modul dalam Kurikulum

```
KURIKULUM BACKEND BEGINNER
│
├── Bab 01: Pengenalan Backend Development     ✅ Selesai
├── Bab 02: Lingkungan Development             ✅ Selesai
├── Bab 03: Dasar Jaringan Komputer            ✅ Selesai
├── Bab 04: HTTP & Web Fundamentals            ◀ ANDA DI SINI
│   ├── Module 01: HTTP Fundamentals           ◀ MODUL INI
│   ├── Module 02: REST API Design
│   └── Module 03: Authentication & Security
├── Bab 05: Database Fundamentals
└── Bab 06: Building Your First API
```

### Mengapa Modul Ini Kritis

HTTP adalah **bahasa universal internet**. Setiap backend developer, tanpa terkecuali, harus memahami HTTP secara mendalam karena:

1. Semua komunikasi web modern menggunakan HTTP/HTTPS
2. REST API — standar industri — dibangun di atas HTTP
3. Debugging backend selalu bermuara pada pemahaman HTTP
4. Security, performance, dan scalability bergantung pada penggunaan HTTP yang benar

---

# SECTION 03 — CORE CONCEPT INTRODUCTION

## Konsep Inti: HTTP sebagai Bahasa Komunikasi Web

### Analogi Kehidupan Nyata

Bayangkan Anda mengirim **surat resmi ke kantor pemerintah**:

```
ANALOGI SURAT RESMI ←→ HTTP COMMUNICATION
─────────────────────────────────────────────────────────

SURAT RESMI                    HTTP REQUEST
─────────────────              ─────────────────────────
Kop Surat (identitas)    →     Request Headers
Nomor Surat              →     Request ID / Correlation ID
Kepada Yth. (alamat)     →     URL / Endpoint
Perihal                  →     HTTP Method + Path
Isi Surat                →     Request Body
Tanda Tangan             →     Authentication Token

BALASAN KANTOR                 HTTP RESPONSE
─────────────────              ─────────────────────────
Nomor Balasan            →     Response Headers
Status (Disetujui/Tolak) →     HTTP Status Code
Isi Balasan              →     Response Body
Stempel Resmi            →     Content-Type Header
```

### Definisi Formal

**HTTP (HyperText Transfer Protocol)** adalah protokol komunikasi lapisan aplikasi (Application Layer) yang mendefinisikan aturan bagaimana pesan dikirim dan diterima antara client dan server di World Wide Web.

**Karakteristik Fundamental HTTP:**

| Karakteristik | Penjelasan | Implikasi |
|---------------|------------|-----------|
| **Stateless** | Setiap request independen, server tidak mengingat request sebelumnya | Perlu mekanisme session/token |
| **Text-based** | Pesan HTTP adalah teks yang dapat dibaca manusia | Mudah di-debug, overhead lebih besar |
| **Request-Response** | Selalu ada pasangan request dari client dan response dari server | Komunikasi sinkron |
| **Connectionless** | Setelah response dikirim, koneksi dapat ditutup | Efisien untuk sumber daya |
| **Flexible** | Dapat mengirim berbagai tipe data (HTML, JSON, gambar, video) | Serbaguna |

---

# SECTION 04 — WHY THIS MATTERS

## Mengapa HTTP Fundamental untuk Backend Developer

### 4.1 HTTP adalah Fondasi Semua Web Communication

```
TANPA PEMAHAMAN HTTP          DENGAN PEMAHAMAN HTTP
──────────────────────        ──────────────────────────────
❌ Tidak tahu kenapa          ✅ Langsung tahu: status 401
   API error 401                 = Unauthorized, perlu token

❌ Asal pilih POST untuk      ✅ Tahu kapan pakai GET, POST,
   semua operasi                 PUT, PATCH, DELETE

❌ Tidak bisa debug           ✅ Bisa baca curl output dan
   network issues                browser DevTools

❌ API design berantakan      ✅ Merancang API yang intuitif
                                 dan mengikuti standar industri

❌ Tidak paham CORS error     ✅ Mengerti dan bisa fix
                                 Cross-Origin issues
```

### 4.2 Relevansi di Dunia Kerja Nyata

**Skenario 1 — Bug Production:**
```
Tim QA melaporkan: "Fitur upload foto gagal di production"

Developer tanpa HTTP knowledge:
→ Panik, tidak tahu harus mulai dari mana
→ Coba-coba random, buang waktu berjam-jam

Developer dengan HTTP knowledge:
→ Cek response status code: 413 Payload Too Large
→ Langsung tahu: perlu naikkan limit ukuran request di server
→ Fix dalam 5 menit
```

**Skenario 2 — Performance Issue:**
```
Aplikasi lambat saat load pertama kali

Developer tanpa HTTP knowledge:
→ Salahkan database, optimasi query (salah arah)

Developer dengan HTTP knowledge:
→ Cek Network tab di DevTools
→ Lihat tidak ada Cache-Control header
→ Tambahkan caching headers yang tepat
→ Load time turun 70%
```

### 4.3 HTTP dalam Ekosistem Modern

```
HTTP digunakan oleh:

Web Apps          → Browser ↔ Web Server
Mobile Apps       → Android/iOS ↔ Backend API
Microservices     → Service A ↔ Service B
IoT Devices       → Sensor ↔ Cloud Server
Webhooks          → Third-party ↔ Your Server
GraphQL           → Client ↔ GraphQL Server (via HTTP POST)
gRPC (HTTP/2)     → Service ↔ Service
```

---

# SECTION 05 — WHAT IS HTTP

## Apa Itu HTTP: Definisi Komprehensif

### 5.1 Sejarah Singkat HTTP

```
EVOLUSI HTTP
────────────────────────────────────────────────────────────

1991  HTTP/0.9   → Hanya GET, hanya HTML
      │
1996  HTTP/1.0   → Headers, status codes, berbagai content type
      │            Setiap request = koneksi TCP baru
      │
1997  HTTP/1.1   → Keep-Alive, chunked transfer, virtual hosting
      │            STANDAR DOMINAN selama 18 tahun
      │            ← FOKUS PEMBELAJARAN KITA
      │
2015  HTTP/2     → Multiplexing, header compression, server push
      │            Binary protocol (bukan text)
      │
2022  HTTP/3     → Berbasis QUIC (UDP), lebih cepat, lebih andal
```

### 5.2 HTTP dalam OSI Model

```
OSI MODEL                    TCP/IP MODEL
─────────────────────────    ─────────────────────────
7. Application Layer  ←──── HTTP, HTTPS, FTP, SMTP
6. Presentation Layer ←──── SSL/TLS (untuk HTTPS)
5. Session Layer      ←──┐
4. Transport Layer    ←──┴── TCP (port 80/443)
3. Network Layer      ←──── IP
2. Data Link Layer    ←──── Ethernet, WiFi
1. Physical Layer     ←──── Kabel, Sinyal Radio
```

### 5.3 HTTP vs HTTPS

```
HTTP                          HTTPS
──────────────────────────    ──────────────────────────────
Port default: 80              Port default: 443
Tidak terenkripsi             Terenkripsi (TLS/SSL)
Data dapat disadap            Data aman dari penyadapan
Tidak ada verifikasi          Ada verifikasi identitas server
  identitas server              via Certificate
Cocok untuk: development      Wajib untuk: production
  lokal                         semua aplikasi

CARA KERJA HTTPS:
Client → [TLS Handshake] → Server
       ← [Certificate]   ←
       → [Verify Cert]   →
       ← [Session Key]   ←
       → [Encrypted Data]→
       ← [Encrypted Resp]←
```

### 5.4 URL Anatomy (Anatomi URL)

```
https://api.tokobuku.com:443/v1/books?genre=fiction&limit=10#results
│       │               │   │        │                      │
│       │               │   │        │                      └── Fragment
│       │               │   │        └── Query String
│       │               │   └── Path
│       │               └── Port
│       └── Host (Domain)
└── Scheme (Protocol)

BREAKDOWN DETAIL:
┌─────────────────────────────────────────────────────────────┐
│ Komponen    │ Nilai              │ Keterangan                │
├─────────────┼────────────────────┼───────────────────────────┤
│ Scheme      │ https              │ Protokol yang digunakan   │
│ Host        │ api.tokobuku.com   │ Domain/IP server          │
│ Port        │ 443                │ Port (opsional jika default)│
│ Path        │ /v1/books          │ Resource yang diminta     │
│ Query       │ genre=fiction      │ Parameter filter/search   │
│             │ &limit=10          │ Diawali '?', dipisah '&'  │
│ Fragment    │ #results           │ Anchor di halaman (client)│
└─────────────────────────────────────────────────────────────┘
```

---

# SECTION 06 — HOW HTTP WORKS

## Cara Kerja HTTP: Mekanisme Lengkap

### 6.1 Siklus Request-Response

```
SIKLUS LENGKAP HTTP REQUEST-RESPONSE
══════════════════════════════════════════════════════════════

BROWSER/CLIENT                              SERVER
     │                                         │
     │  1. User ketik URL di browser           │
     │     atau klik link                      │
     │                                         │
     │  2. DNS Resolution                      │
     │     api.tokobuku.com → 203.0.113.42     │
     │                                         │
     │  3. TCP Connection (3-way handshake)    │
     │─────── SYN ────────────────────────────▶│
     │◀────── SYN-ACK ─────────────────────────│
     │─────── ACK ────────────────────────────▶│
     │                                         │
     │  4. TLS Handshake (jika HTTPS)          │
     │─────── ClientHello ─────────────────────▶│
     │◀────── ServerHello + Certificate ────────│
     │─────── Key Exchange ────────────────────▶│
     │◀────── Finished ─────────────────────────│
     │                                         │
     │  5. HTTP Request                        │
     │─────── GET /v1/books HTTP/1.1 ──────────▶│
     │        Host: api.tokobuku.com           │
     │        Accept: application/json         │
     │        Authorization: Bearer token123   │
     │                                         │
     │  6. Server Processing                   │
     │                              ┌──────────┤
     │                              │ Route    │
     │                              │ Handler  │
     │                              │ Database │
     │                              │ Business │
     │                              │ Logic    │
     │                              └──────────┤
     │                                         │
     │  7. HTTP Response                       │
     │◀────── HTTP/1.1 200 OK ─────────────────│
     │        Content-Type: application/json   │
     │        Content-Length: 1234             │
     │                                         │
     │        {"books": [...]}                 │
     │                                         │
     │  8. Browser render / App process data   │
     │                                         │
     │  9. Connection close atau Keep-Alive    │
     │                                         │
```

### 6.2 Anatomi HTTP Request

```
HTTP REQUEST STRUCTURE
══════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────┐
│                      REQUEST LINE                           │
│  GET /v1/books?genre=fiction HTTP/1.1                       │
│  ─── ──────────────────────── ────────                      │
│  │   │                        │                             │
│  │   └── Request Target       └── HTTP Version             │
│  └── HTTP Method                                            │
├─────────────────────────────────────────────────────────────┤
│                      HEADERS                                │
│  Host: api.tokobuku.com                                     │
│  Accept: application/json                                   │
│  Accept-Language: id-ID, en;q=0.9                           │
│  Authorization: Bearer eyJhbGciOiJIUzI1NiJ9...             │
│  User-Agent: Mozilla/5.0 (Windows NT 10.0)                  │
│  Connection: keep-alive                                     │
│  Cache-Control: no-cache                                    │
├─────────────────────────────────────────────────────────────┤
│                    BLANK LINE                               │
│  (Memisahkan headers dari body)                             │
├─────────────────────────────────────────────────────────────┤
│                      BODY                                   │
│  (Kosong untuk GET request)                                 │
│                                                             │
│  Untuk POST/PUT, berisi data:                               │
│  {                                                          │
│    "title": "Laskar Pelangi",                               │
│    "author": "Andrea Hirata",                               │
│    "price": 85000                                           │
│  }                                                          │
└─────────────────────────────────────────────────────────────┘
```

### 6.3 Anatomi HTTP Response

```
HTTP RESPONSE STRUCTURE
══════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────┐
│                      STATUS LINE                            │
│  HTTP/1.1 200 OK                                            │
│  ──────── ─── ──                                            │
│  │        │   │                                             │
│  │        │   └── Reason Phrase (deskripsi singkat)         │
│  │        └── Status Code (3 digit angka)                   │
│  └── HTTP Version                                           │
├─────────────────────────────────────────────────────────────┤
│                      HEADERS                                │
│  Content-Type: application/json; charset=utf-8              │
│  Content-Length: 1234                                       │
│  Date: Mon, 15 Jan 2024 10:30:00 GMT                        │
│  Server: nginx/1.24.0                                       │
│  Cache-Control: max-age=3600                                │
│  X-Request-ID: abc123def456                                 │
│  Access-Control-Allow-Origin: *                             │
├─────────────────────────────────────────────────────────────┤
│                    BLANK LINE                               │
├─────────────────────────────────────────────────────────────┤
│                      BODY                                   │
│  {                                                          │
│    "status": "success",                                     │
│    "data": {                                                │
│      "books": [                                             │
│        {                                                    │
│          "id": 1,                                           │
│          "title": "Laskar Pelangi",                         │
│          "author": "Andrea Hirata"                          │
│        }                                                    │
│      ]                                                      │
│    },                                                       │
│    "meta": {                                                │
│      "total": 150,                                          │
│      "page": 1,                                             │
│      "limit": 10                                            │
│    }                                                        │
│  }                                                          │
└─────────────────────────────────────────────────────────────┘
```

---

# SECTION 07 — ASCII DIAGRAM: ARSITEKTUR HTTP

## Diagram Arsitektur Lengkap

### 7.1 Arsitektur Client-Server HTTP

```
╔══════════════════════════════════════════════════════════════════╗
║              ARSITEKTUR HTTP CLIENT-SERVER                       ║
╚══════════════════════════════════════════════════════════════════╝

    ┌─────────────────┐         Internet          ┌──────────────────────┐
    │   CLIENT SIDE   │                           │    SERVER SIDE       │
    │                 │                           │                      │
    │  ┌───────────┐  │    ┌─────────────────┐   │  ┌────────────────┐  │
    │  │  Browser  │  │    │   Load Balancer  │   │  │  Web Server    │  │
    │  │  atau     │──┼───▶│   (nginx/HAProxy)│──▶│  │  (nginx/Apache)│  │
    │  │  Mobile   │  │    │                 │   │  │                │  │
    │  │  App      │  │    └─────────────────┘   │  └───────┬────────┘  │
    │  └───────────┘  │                           │          │           │
    │                 │                           │          ▼           │
    │  ┌───────────┐  │    ┌─────────────────┐   │  ┌────────────────┐  │
    │  │  curl /   │  │    │   CDN / Cache   │   │  │  App Server    │  │
    │  │  Postman  │──┼───▶│   (CloudFlare)  │   │  │  (Node.js/     │  │
    │  │  Insomnia │  │    │                 │   │  │   Python/Go)   │  │
    │  └───────────┘  │    └─────────────────┘   │  └───────┬────────┘  │
    │                 │                           │          │           │
    │  ┌───────────┐  │                           │          ▼           │
    │  │  IoT /    │  │                           │  ┌────────────────┐  │
    │  │  Service  │──┼───────────────────────────┼─▶│   Database     │  │
    │  │  Lain     │  │                           │  │  (PostgreSQL/  │  │
    │  └───────────┘  │                           │  │   MongoDB)     │  │
    └─────────────────┘                           │  └────────────────┘  │
                                                  └──────────────────────┘

    ◀──────────────── HTTP REQUEST ─────────────────────────────────────▶
    ◀──────────────── HTTP RESPONSE ────────────────────────────────────▶
```

### 7.2 HTTP Methods Decision Tree

```
╔══════════════════════════════════════════════════════════════════╗
║              HTTP METHODS DECISION TREE                          ║
╚══════════════════════════════════════════════════════════════════╝

                    Operasi apa yang ingin dilakukan?
                              │
              ┌───────────────┼───────────────┐
              │               │               │
           Baca            Tulis           Hapus
           Data            Data            Data
              │               │               │
              ▼               │               ▼
           GET ✓          ┌───┴───┐         DELETE ✓
                          │       │
                       Buat    Update
                       Baru    Data
                          │       │
                          ▼    ┌──┴──┐
                        POST   │     │
                               │     │
                            Seluruh  Sebagian
                            Resource Resource
                               │     │
                               ▼     ▼
                              PUT  PATCH


RINGKASAN HTTP METHODS:
┌─────────┬──────────────────────────────┬──────────┬────────────┐
│ Method  │ Kegunaan                     │ Has Body │ Idempotent │
├─────────┼──────────────────────────────┼──────────┼────────────┤
│ GET     │ Ambil resource               │ Tidak    │ Ya         │
│ POST    │ Buat resource baru           │ Ya       │ Tidak      │
│ PUT     │ Update resource (seluruhnya) │ Ya       │ Ya         │
│ PATCH   │ Update resource (sebagian)   │ Ya       │ Tidak*     │
│ DELETE  │ Hapus resource               │ Tidak    │ Ya         │
│ HEAD    │ Seperti GET, tanpa body      │ Tidak    │ Ya         │
│ OPTIONS │ Cek method yang tersedia     │ Tidak    │ Ya         │
└─────────┴──────────────────────────────┴──────────┴────────────┘
* PATCH bisa idempotent tergantung implementasi
```

### 7.3 HTTP Status Codes Map

```
╔══════════════════════════════════════════════════════════════════╗
║              HTTP STATUS CODES — PETA LENGKAP                    ║
╚══════════════════════════════════════════════════════════════════╝

1xx INFORMATIONAL          2xx SUCCESS
────────────────────       ────────────────────────────────────────
100 Continue               200 OK
101 Switching Protocols    201 Created
102 Processing             204 No Content
                           206 Partial Content

3xx REDIRECTION            4xx CLIENT ERROR
────────────────────       ────────────────────────────────────────
301 Moved Permanently      400 Bad Request
302 Found (Temporary)      401 Unauthorized
304 Not Modified           403 Forbidden
307 Temporary Redirect     404 Not Found
308 Permanent Redirect     405 Method Not Allowed
                           408 Request Timeout
                           409 Conflict
                           410 Gone
                           413 Payload Too Large
                           422 Unprocessable Entity
                           429 Too Many Requests

5xx SERVER ERROR
────────────────────────────────────────────────────────────────
500 Internal Server Error
501 Not Implemented
502 Bad Gateway
503 Service Unavailable
504 Gateway Timeout

CARA MUDAH MENGINGAT:
┌─────┬──────────────────────────────────────────────────────────┐
│ 1xx │ "Tunggu dulu, masih proses..."                           │
│ 2xx │ "Berhasil! ✅"                                           │
│ 3xx │ "Pindah ke sana ya..."                                   │
│ 4xx │ "Salah kamu! ❌" (Client error)                          │
│ 5xx │ "Salah saya! 💥" (Server error)                          │
└─────┴──────────────────────────────────────────────────────────┘
```

---

# SECTION 08 — SIMPLE EXAMPLE

## Contoh Sederhana: HTTP Request Pertama Anda

### 8.1 Menggunakan curl untuk HTTP Request

```bash
# ============================================================
# CONTOH 1: GET Request Paling Sederhana
# ============================================================

# Kirim GET request ke API publik
curl https://jsonplaceholder.typicode.com/posts/1

# OUTPUT:
# {
#   "userId": 1,
#   "id": 1,
#   "title": "sunt aut facere repellat provident occaecati",
#   "body": "quia et suscipit\nsuscipit recusandae..."
# }
```

```bash
# ============================================================
# CONTOH 2: Lihat HTTP Headers Lengkap
# ============================================================

# Flag -v = verbose, tampilkan semua detail HTTP
curl -v https://jsonplaceholder.typicode.com/posts/1

# OUTPUT VERBOSE:
# * Trying 104.21.x.x:443...
# * Connected to jsonplaceholder.typicode.com
# * SSL connection using TLSv1.3
#
# > GET /posts/1 HTTP/2              ← REQUEST LINE
# > Host: jsonplaceholder.typicode.com
# > User-Agent: curl/7.88.1          ← REQUEST HEADERS
# > Accept: */*
# >
# < HTTP/2 200                       ← STATUS LINE
# < content-type: application/json   ← RESPONSE HEADERS
# < cache-control: max-age=43200
# < x-powered-by: Express
# <
# {                                  ← RESPONSE BODY
#   "userId": 1,
#   "id": 1,
#   "title": "..."
# }
```

```bash
# ============================================================
# CONTOH 3: POST Request dengan Body JSON
# ============================================================

curl -X POST \
  https://jsonplaceholder.typicode.com/posts \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Buku Baru",
    "body": "Isi buku yang menarik",
    "userId": 1
  }'

# OUTPUT:
# {
#   "title": "Buku Baru",
#   "body": "Isi buku yang menarik",
#   "userId": 1,
#   "id": 101
# }
# Status: 201 Created
```

### 8.2 Membaca HTTP di Browser DevTools

```
LANGKAH MEMBUKA DEVTOOLS:
1. Buka browser (Chrome/Firefox)
2. Tekan F12 atau Ctrl+Shift+I
3. Klik tab "Network"
4. Buka website mana saja
5. Klik salah satu request

YANG AKAN ANDA LIHAT:
┌─────────────────────────────────────────────────────────────┐
│ HEADERS TAB                                                 │
│                                                             │
│ General                                                     │
│   Request URL: https://api.example.com/users                │
│   Request Method: GET                                       │
│   Status Code: 200 OK                                       │
│   Remote Address: 203.0.113.42:443                          │
│                                                             │
│ Response Headers                                            │
│   content-type: application/json                            │
│   cache-control: max-age=3600                               │
│                                                             │
│ Request Headers                                             │
│   Accept: application/json                                  │
│   Authorization: Bearer eyJ...                              │
└─────────────────────────────────────────────────────────────┘
```

---

# SECTION 09 — PRACTICAL EXAMPLE

## Contoh Praktis: Membangun HTTP Server Sederhana

### 9.1 HTTP Server dengan Node.js (Built-in)

```javascript
// file: http-server-basic.js
// ============================================================
// HTTP Server paling sederhana menggunakan Node.js built-in
// Tidak perlu install package apapun
// ============================================================

const http = require('http');

// Konfigurasi server
const HOST = 'localhost';
const PORT = 3000;

// Simulasi "database" sederhana
const books = [
  { id: 1, title: 'Laskar Pelangi', author: 'Andrea Hirata', price: 85000 },
  { id: 2, title: 'Bumi Manusia', author: 'Pramoedya Ananta Toer', price: 95000 },
  { id: 3, title: 'Cantik Itu Luka', author: 'Eka Kurniawan', price: 78000 },
];

// ============================================================
// REQUEST HANDLER — Jantung dari HTTP Server
// ============================================================
const requestHandler = (req, res) => {
  // Log setiap request yang masuk
  console.log(`[${new Date().toISOString()}] ${req.method} ${req.url}`);

  // Parse URL untuk routing
  const url = new URL(req.url, `http://${req.headers.host}`);
  const pathname = url.pathname;
  const method = req.method;

  // ──────────────────────────────────────────────────────────
  // ROUTE 1: GET /health — Health Check
  // ──────────────────────────────────────────────────────────
  if (pathname === '/health' && method === 'GET') {
    res.writeHead(200, {
      'Content-Type': 'application/json',
      'X-Server': 'MyHTTPServer/1.0'
    });
    res.end(JSON.stringify({
      status: 'healthy',
      timestamp: new Date().toISOString(),
      uptime: process.uptime()
    }));
    return;
  }

  // ──────────────────────────────────────────────────────────
  // ROUTE 2: GET /books — Ambil semua buku
  // ──────────────────────────────────────────────────────────
  if (pathname === '/books' && method === 'GET') {
    // Baca query parameter
    const genre = url.searchParams.get('genre');
    const limit = parseInt(url.searchParams.get('limit')) || 10;

    // Filter data (simulasi)
    let result = books;
    if (genre) {
      result = books.filter(b => b.genre === genre);
    }
    result = result.slice(0, limit);

    // Kirim response sukses
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      status: 'success',
      data: result,
      meta: {
        total: result.length,
        limit: limit
      }
    }));
    return;
  }

  // ──────────────────────────────────────────────────────────
  // ROUTE 3: GET /books/:id — Ambil satu buku
  // ──────────────────────────────────────────────────────────
  const bookMatch = pathname.match(/^\/books\/(\d+)$/);
  if (bookMatch && method === 'GET') {
    const bookId = parseInt(bookMatch[1]);
    const book = books.find(b => b.id === bookId);

    if (!book) {
      // 404 Not Found — resource tidak ada
      res.writeHead(404, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({
        status: 'error',
        message: `Buku dengan ID ${bookId} tidak ditemukan`
      }));
      return;
    }

    // 200 OK — resource ditemukan
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      status: 'success',
      data: book
    }));
    return;
  }

  // ──────────────────────────────────────────────────────────
  // ROUTE 4: POST /books — Tambah buku baru
  // ──────────────────────────────────────────────────────────
  if (pathname === '/books' && method === 'POST') {
    let body = '';

    // Kumpulkan data dari request body (streaming)
    req.on('data', chunk => {
      body += chunk.toString();
    });

    req.on('end', () => {
      try {
        const newBook = JSON.parse(body);

        // Validasi sederhana
        if (!newBook.title || !newBook.author) {
          res.writeHead(400, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({
            status: 'error',
            message: 'Field title dan author wajib diisi'
          }));
          return;
        }

        // Tambah ke "database"
        const createdBook = {
          id: books.length + 1,
          ...newBook,
          createdAt: new Date().toISOString()
        };
        books.push(createdBook);

        // 201 Created — resource berhasil dibuat
        res.writeHead(201, {
          'Content-Type': 'application/json',
          'Location': `/books/${createdBook.id}` // Header Location penting!
        });
        res.end(JSON.stringify({
          status: 'success',
          message: 'Buku berhasil ditambahkan',
          data: createdBook
        }));

      } catch (error) {
        // 400 Bad Request — JSON tidak valid
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
          status: 'error',
          message: 'Format JSON tidak valid'
        }));
      }
    });
    return;
  }

  // ──────────────────────────────────────────────────────────
  // DEFAULT: 404 Not Found — Route tidak ditemukan
  // ──────────────────────────────────────────────────────────
  res.writeHead(404, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({
    status: 'error',
    message: `Route ${method} ${pathname} tidak ditemukan`
  }));
};

// ============================================================
// BUAT DAN JALANKAN SERVER
// ============================================================
const server = http.createServer(requestHandler);

server.listen(PORT, HOST, () => {
  console.log(`
╔════════════════════════════════════════╗
║   HTTP Server berjalan!                ║
║   URL: http://${HOST}:${PORT}          ║
╠════════════════════════════════════════╣
║   Endpoints tersedia:                  ║
║   GET  /health                         ║
║   GET  /books                          ║
║   GET  /books/:id                      ║
║   POST /books                          ║
╚════════════════════════════════════════╝
  `);
});

// Graceful shutdown
process.on('SIGTERM', () => {
  console.log('Server shutting down...');
  server.close(() => {
    console.log('Server closed.');
    process.exit(0);
  });
});
```

### 9.2 Testing Server dengan curl

```bash
# ============================================================
# TEST SEMUA ENDPOINT
# ============================================================

# 1. Health Check
curl http://localhost:3000/health
# Response: {"status":"healthy","timestamp":"...","uptime":5.2}

# 2. Get All Books
curl http://localhost:3000/books
# Response: {"status":"success","data":[...],"meta":{"total":3}}

# 3. Get Books dengan Query Parameter
curl "http://localhost:3000/books?limit=2"
# Response: {"status":"success","data":[buku1, buku2],...}

# 4. Get Single Book
curl http://localhost:3000/books/1
# Response: {"status":"success","data":{"id":1,"title":"Laskar Pelangi",...}}

# 5. Get Book yang Tidak Ada (404)
curl http://localhost:3000/books/999
# Response: {"status":"error","message":"Buku dengan ID 999 tidak ditemukan"}

# 6. Create New Book (POST)
curl -X POST http://localhost:3000/books \
  -H "Content-Type: application/json" \
  -d '{"title":"Pulang","author":"Tere Liye","price":72000}'
# Response: {"status":"success","message":"Buku berhasil ditambahkan",...}

# 7. Create Book tanpa field wajib (400)
curl -X POST http://localhost:3000/books \
  -H "Content-Type: application/json" \
  -d '{"price":50000}'
# Response: {"status":"error","message":"Field title dan author wajib diisi"}

# 8. Lihat status code di response
curl -o /dev/null -s -w "%{http_code}\n" http://localhost:3000/books
# Output: 200

curl -o /dev/null -s -w "%{http_code}\n" http://localhost:3000/books/999
# Output: 404
```

---

# SECTION 10 — HTTP HEADERS DEEP DIVE

## HTTP Headers: Panduan Komprehensif

### 10.1 Kategori HTTP Headers

```
HTTP HEADERS TAXONOMY
══════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────┐
│                    REQUEST HEADERS                          │
├──────────────────┬──────────────────────────────────────────┤
│ Header           │ Contoh & Penjelasan                      │
├──────────────────┼──────────────────────────────────────────┤
│ Host             │ api.tokobuku.com                         │
│                  │ WAJIB di HTTP/1.1, identifikasi server   │
├──────────────────┼──────────────────────────────────────────┤
│ Accept           │ application/json, text/html;q=0.9        │
│                  │ Format response yang diterima client      │
├──────────────────┼──────────────────────────────────────────┤
│ Content-Type     │ application/json; charset=utf-8          │
│                  │ Format data yang dikirim di body          │
├──────────────────┼──────────────────────────────────────────┤
│ Authorization    │ Bearer eyJhbGciOiJIUzI1NiJ9...           │
│                  │ Kredensial autentikasi                    │
├──────────────────┼──────────────────────────────────────────┤
│ User-Agent       │ Mozilla/5.0 (Windows NT 10.0; Win64)     │
│                  │ Identitas client/browser                  │
├──────────────────┼──────────────────────────────────────────┤
│ Accept-Encoding  │ gzip, deflate, br                        │
│                  │ Kompresi yang didukung client             │
├──────────────────┼──────────────────────────────────────────┤
│ Cookie           │ session_id=abc123; theme=dark            │
│                  │ Cookie yang disimpan browser              │
├──────────────────┼──────────────────────────────────────────┤
│ If-None-Match    │ "etag-value-here"                        │
│                  │ Conditional request untuk caching         │
└──────────────────┴──────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    RESPONSE HEADERS                         │
├──────────────────┬──────────────────────────────────────────┤
│ Content-Type     │ application/json; charset=utf-8          │
│                  │ Format data yang dikirim server           │
├──────────────────┼──────────────────────────────────────────┤
│ Content-Length   │ 1234                                     │
│                  │ Ukuran body dalam bytes                   │
├──────────────────┼──────────────────────────────────────────┤
│ Cache-Control    │ max-age=3600, public                     │
│                  │ Instruksi caching                         │
├──────────────────┼──────────────────────────────────────────┤
│ Set-Cookie       │ session_id=xyz; HttpOnly; Secure         │
│                  │ Set cookie di browser                     │
├──────────────────┼──────────────────────────────────────────┤
│ Location         │ /books/101                               │
│                  │ Redirect URL atau URL resource baru       │
├──────────────────┼──────────────────────────────────────────┤
│ ETag             │ "33a64df551425fcc55e"                    │
│                  │ Versi resource untuk caching              │
├──────────────────┼──────────────────────────────────────────┤
│ CORS Headers     │ Access-Control-Allow-Origin: *           │
│                  │ Izin cross-origin request                 │
└──────────────────┴──────────────────────────────────────────┘
```

### 10.2 Content-Type yang Paling Umum

```javascript
// ============================================================
// CONTENT-TYPE REFERENCE
// ============================================================

const CONTENT_TYPES = {
  // Data Formats
  'application/json':                'JSON data (API paling umum)',
  'application/xml':                 'XML data',
  'application/x-www-form-urlencoded': 'HTML form data',
  'multipart/form-data':             'File upload + form data',

  // Text Formats
  'text/html':                       'HTML document',
  'text/plain':                      'Plain text',
  'text/css':                        'CSS stylesheet',
  'text/javascript':                 'JavaScript file',

  // Media
  'image/jpeg':                      'JPEG image',
  'image/png':                       'PNG image',
  'image/webp':                      'WebP image',
  'video/mp4':                       'MP4 video',
  'audio/mpeg':                      'MP3 audio',

  // Documents
  'application/pdf':                 'PDF document',
  'application/zip':                 'ZIP archive',
  'application/octet-stream':        'Binary data (download)',
};

// Cara set Content-Type di response
res.setHeader('Content-Type', 'application/json; charset=utf-8');
```

---

# SECTION 11 — STATELESS & STATE MANAGEMENT

## HTTP Stateless: Konsep dan Solusinya

### 11.1 Memahami Stateless

```
MASALAH STATELESS HTTP
══════════════════════════════════════════════════════════════

Request 1: Login
Client ──── POST /login {username, password} ────▶ Server
       ◀─── 200 OK {token: "abc123"} ─────────────

Request 2: Get Profile (Server sudah "lupa" siapa Anda!)
Client ──── GET /profile ────────────────────────▶ Server
       ◀─── 401 Unauthorized ────────────────────

SOLUSI: Kirim identitas di setiap request
Client ──── GET /profile ────────────────────────▶ Server
            Authorization: Bearer abc123
       ◀─── 200 OK {user data} ─────────────────

MEKANISME STATE MANAGEMENT:
┌─────────────────────────────────────────────────────────────┐
│ Metode          │ Cara Kerja          │ Cocok Untuk         │
├─────────────────┼─────────────────────┼─────────────────────┤
│ Cookie          │ Browser simpan &    │ Web apps            │
│                 │ kirim otomatis      │ traditional         │
├─────────────────┼─────────────────────┼─────────────────────┤
│ Session         │ Server simpan state,│ Web apps dengan     │
│                 │ client punya ID     │ server-side render  │
├─────────────────┼─────────────────────┼─────────────────────┤
│ JWT Token       │ Token berisi data,  │ REST API, Mobile    │
│                 │ dikirim di header   │ Apps, SPA           │
├─────────────────┼─────────────────────┼─────────────────────┤
│ API Key         │ Key unik per client │ Server-to-server,   │
│                 │ di header/query     │ Third-party API     │
└─────────────────┴─────────────────────┴─────────────────────┘
```

### 11.2 Implementasi Cookie dan Session

```javascript
// ============================================================
// SIMULASI COOKIE-BASED SESSION
// ============================================================

const http = require('http');
const crypto = require('crypto');

// Penyimpanan session di memory (production: gunakan Redis)
const sessions = new Map();

// Helper: Parse cookies dari header
function parseCookies(cookieHeader) {
  const cookies = {};
  if (!cookieHeader) return cookies;

  cookieHeader.split(';').forEach(cookie => {
    const [name, value] = cookie.trim().split('=');
    cookies[name] = value;
  });
  return cookies;
}

// Helper: Generate session ID
function generateSessionId() {
  return crypto.randomBytes(32).toString('hex');
}

const server = http.createServer((req, res) => {
  const cookies = parseCookies(req.headers.cookie);
  const sessionId = cookies['session_id'];

  // ──────────────────────────────────────────────────────────
  // POST /login — Buat session baru
  // ──────────────────────────────────────────────────────────
  if (req.url === '/login' && req.method === 'POST') {
    let body = '';
    req.on('data', chunk => body += chunk);
    req.on('end', () => {
      const { username, password } = JSON.parse(body);

      // Validasi (simplified)
      if (username === 'admin' && password === 'secret') {
        const newSessionId = generateSessionId();

        // Simpan session data di server
        sessions.set(newSessionId, {
          userId: 1,
          username: 'admin',
          loginAt: new Date().toISOString()
        });

        // Set cookie di browser
        res.writeHead(200, {
          'Content-Type': 'application/json',
          'Set-Cookie': [
            `session_id=${newSessionId}; HttpOnly; Secure; SameSite=Strict; Max-Age=3600`,
            `logged_in=true; Max-Age=3600` // Non-HttpOnly untuk JS
          ]
        });
        res.end(JSON.stringify({ message: 'Login berhasil' }));
      } else {
        res.writeHead(401, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ message: 'Username atau password salah' }));
      }
    });
    return;
  }

  // ──────────────────────────────────────────────────────────
  // GET /profile — Butuh autentikasi
  // ──────────────────────────────────────────────────────────
  if (req.url === '/profile' && req.method === 'GET') {
    if (!sessionId || !sessions.has(sessionId)) {
      res.writeHead(401, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ message: 'Silakan login terlebih dahulu' }));
      return;
    }

    const sessionData = sessions.get(sessionId);
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      message: 'Profile berhasil diambil',
      user: sessionData
    }));
    return;
  }

  // ──────────────────────────────────────────────────────────
  // POST /logout — Hapus session
  // ──────────────────────────────────────────────────────────
  if (req.url === '/logout' && req.method === 'POST') {
    if (sessionId) {
      sessions.delete(sessionId);
    }

    // Hapus cookie dengan Max-Age=0
    res.writeHead(200, {
      'Content-Type': 'application/json',
      'Set-Cookie': 'session_id=; HttpOnly; Max-Age=0'
    });
    res.end(JSON.stringify({ message: 'Logout berhasil' }));
    return;
  }
});

server.listen(3001, () => console.log('Auth server running on port 3001'));
```

---

# SECTION 12 — TRADE-OFFS & CONSIDERATIONS

## Trade-offs dalam Desain HTTP API

### 12.1 Trade-off Utama

```
TRADE-OFF 1: VERBOSITY vs SIMPLICITY
══════════════════════════════════════════════════════════════

VERBOSE (Detail)                  SIMPLE (Ringkas)
──────────────────────────────    ──────────────────────────────
GET /api/v1/users/123/orders      GET /getUserOrders?userId=123
  /active?page=1&limit=10

✅ RESTful dan semantik           ✅ Mudah dibuat
✅ Mudah di-cache                 ✅ Tidak perlu banyak routes
✅ Standar industri               ❌ Tidak RESTful
❌ URL lebih panjang              ❌ Sulit di-cache
❌ Butuh lebih banyak routing     ❌ Tidak konsisten

REKOMENDASI: Gunakan pendekatan verbose/RESTful
untuk API publik dan tim besar.
```

```
TRADE-OFF 2: STATUS CODE GRANULARITY
══════════════════════════════════════════════════════════════

GRANULAR                          SIMPLIFIED
──────────────────────────────    ──────────────────────────────
400 Bad Request                   400 untuk semua error client
401 Unauthorized
403 Forbidden
404 Not Found
409 Conflict
422 Unprocessable Entity
429 Too Many Requests

✅ Client tahu persis masalahnya  ✅ Lebih mudah diimplementasi
✅ Debugging lebih mudah          ✅ Konsisten
✅ Standar industri               ❌ Client tidak tahu detail
❌ Butuh lebih banyak handling    ❌ Debugging lebih sulit

REKOMENDASI: Gunakan status code yang tepat,
minimal bedakan 400/401/403/404/422/500.
```

```
TRADE-OFF 3: RESPONSE FORMAT
══════════════════════════════════════════════════════════════

ENVELOPE PATTERN                  BARE RESPONSE
──────────────────────────────    ──────────────────────────────
{                                 [
  "status": "success",              {"id": 1, "name": "..."},
  "data": [...],                    {"id": 2, "name": "..."}
  "meta": {                       ]
    "total": 100,
    "page": 1
  }
}

✅ Konsisten untuk semua response ✅ Lebih ringkas
✅ Mudah handle error             ✅ Standar JSON:API
✅ Metadata tersedia              ❌ Tidak ada metadata
❌ Response lebih besar           ❌ Error handling berbeda

REKOMENDASI: Gunakan envelope pattern untuk
konsistensi, terutama di API yang kompleks.
```

### 12.2 Perbandingan HTTP Methods

```
KAPAN MENGGUNAKAN PUT vs PATCH
══════════════════════════════════════════════════════════════

Skenario: Update profil user (hanya ubah email)

PUT /users/1
{
  "name": "Budi Santoso",    ← WAJIB kirim semua field
  "email": "budi@baru.com",  ← Field yang diubah
  "age": 25,                 ← Tidak berubah tapi wajib ada
  "phone": "08123456789"     ← Tidak berubah tapi wajib ada
}

PATCH /users/1
{
  "email": "budi@baru.com"   ← Hanya kirim yang berubah
}

KAPAN PAKAI PUT:
- Mengganti seluruh resource
- Client punya data lengkap resource
- Operasi harus idempotent

KAPAN PAKAI PATCH:
- Update sebagian field saja
- Menghemat bandwidth
- Field yang tidak dikirim tidak berubah
```

---

# SECTION 13 — BEST PRACTICES

## Best Practices HTTP API Design

### 13.1 URL Design Best Practices

```
URL DESIGN RULES
══════════════════════════════════════════════════════════════

✅ GUNAKAN NOUN (kata benda), bukan VERB
   ✅ GET /books          (noun)
   ❌ GET /getBooks       (verb)
   ❌ GET /fetchAllBooks  (verb)

✅ GUNAKAN PLURAL untuk collections
   ✅ /books              (plural)
   ✅ /users              (plural)
   ❌ /book               (singular)
   ❌ /user               (singular)

✅ GUNAKAN LOWERCASE dan HYPHEN
   ✅ /book-categories    (lowercase + hyphen)
   ❌ /BookCategories     (PascalCase)
   ❌ /book_categories    (underscore)

✅ GUNAKAN HIERARKI untuk nested resources
   ✅ /users/123/orders          (orders milik user 123)
   ✅ /orders/456/items          (items dalam order 456)
   ❌ /getUserOrders?id=123      (tidak RESTful)

✅ GUNAKAN QUERY PARAMS untuk filter, sort, paginate
   ✅ /books?genre=fiction&sort=price&page=2&limit=10
   ❌ /books/fiction/sort/price/page/2

✅ VERSIONING di URL atau Header
   ✅ /api/v1/books              (URL versioning - lebih eksplisit)
   ✅ Accept: application/vnd.api+json;version=1 (header versioning)
```

### 13.2 Response Design Best Practices

```javascript
// ============================================================
// RESPONSE FORMAT STANDAR — BEST PRACTICE
// ============================================================

// ✅ SUCCESS RESPONSE
const successResponse = {
  status: 'success',
  data: {
    // Resource atau collection
  },
  meta: {
    // Pagination, total count, dll
    total: 100,
    page: 1,
    limit: 10,
    totalPages: 10
  }
};

// ✅ ERROR RESPONSE — Informatif dan konsisten
const errorResponse = {
  status: 'error',
  error: {
    code: 'VALIDATION_ERROR',        // Machine-readable error code
    message: 'Data tidak valid',     // Human-readable message
    details: [                       // Detail spesifik (opsional)
      {
        field: 'email',
        message: 'Format email tidak valid'
      },
      {
        field: 'price',
        message: 'Harga harus berupa angka positif'
      }
    ]
  },
  requestId: 'req_abc123'           // Untuk debugging
};

// ✅ PAGINATION RESPONSE
const paginatedResponse = {
  status: 'success',
  data: [...],
  meta: {
    total: 150,
    page: 2,
    limit: 10,
    totalPages: 15,
    hasNextPage: true,
    hasPrevPage: true
  },
  links: {
    self: '/books?page=2&limit=10',
    first: '/books?page=1&limit=10',
    prev: '/books?page=1&limit=10',
    next: '/books?page=3&limit=10',
    last: '/books?page=15&limit=10'
  }
};
```

### 13.3 Security Best Practices

```
HTTP SECURITY CHECKLIST
══════════════════════════════════════════════════════════════

✅ SELALU gunakan HTTPS di production
   → Enkripsi data in-transit
   → Cegah man-in-the-middle attack

✅ Set Security Headers
   → Strict-Transport-Security: max-age=31536000
   → X-Content-Type-Options: nosniff
   → X-Frame-Options: DENY
   → Content-Security-Policy: default-src 'self'

✅ Validasi Content-Type
   → Jangan proses body jika Content-Type salah
   → Cegah content-type sniffing

✅ Rate Limiting
   → X-RateLimit-Limit: 100
   → X-RateLimit-Remaining: 95
   → X-RateLimit-Reset: 1640000000
   → Return 429 jika limit terlampaui

✅ Jangan expose informasi sensitif
   → Jangan kirim stack trace di production
   → Jangan expose versi server (Server: nginx)
   → Gunakan generic error messages

✅ Validasi semua input
   → Sanitize query parameters
   → Validate request body
   → Limit request size
```

---

# SECTION 14 — COMMON MISTAKES & ANTI-PATTERNS

## Kesalahan Umum dan Anti-Pattern

### 14.1 Kesalahan Status Code

```
KESALAHAN STATUS CODE YANG SERING TERJADI
══════════════════════════════════════════════════════════════

❌ SALAH: Return 200 untuk semua response, termasuk error
──────────────────────────────────────────────────────────────
HTTP/1.1 200 OK
{
  "success": false,
  "error": "User tidak ditemukan"
}

Masalah:
- Client harus parse body untuk tahu sukses/gagal
- Caching akan cache response error
- Monitoring tools tidak bisa detect error

✅ BENAR: Gunakan status code yang tepat
──────────────────────────────────────────────────────────────
HTTP/1.1 404 Not Found
{
  "status": "error",
  "error": {
    "code": "USER_NOT_FOUND",
    "message": "User tidak ditemukan"
  }
}


❌ SALAH: Gunakan POST untuk semua operasi
──────────────────────────────────────────────────────────────
POST /getUser
POST /deleteUser
POST /updateUser

Masalah:
- Tidak bisa di-cache (GET bisa di-cache)
- Tidak idempotent
- Tidak mengikuti standar HTTP

✅ BENAR: Gunakan method yang semantik
──────────────────────────────────────────────────────────────
GET    /users/123
DELETE /users/123
PUT    /users/123


❌ SALAH: Tidak set Content-Type
──────────────────────────────────────────────────────────────
HTTP/1.1 200 OK
{"data": "..."}

Masalah:
- Client tidak tahu cara parse response
- Browser mungkin salah interpret

✅ BENAR: Selalu set Content-Type
──────────────────────────────────────────────────────────────
HTTP/1.1 200 OK
Content-Type: application/json; charset=utf-8
{"data": "..."}
```

### 14.2 Anti-Pattern URL Design

```
URL DESIGN ANTI-PATTERNS
══════════════════════════════════════════════════════════════

❌ ANTI-PATTERN: Verb dalam URL
   /api/getBooks
   /api/createBook
   /api/deleteBook/1
   /api/updateBook/1

✅ BENAR: Noun + HTTP Method
   GET    /api/books
   POST   /api/books
   DELETE /api/books/1
   PUT    /api/books/1


❌ ANTI-PATTERN: Inkonsistensi naming
   /api/Books          (PascalCase)
   /api/user_profile   (snake_case)
   /api/getOrderList   (camelCase + verb)

✅ BENAR: Konsisten lowercase + hyphen
   /api/books
   /api/user-profiles
   /api/order-items


❌ ANTI-PATTERN: Terlalu dalam nested
   /users/1/orders/2/items/3/reviews/4/comments/5

✅ BENAR: Maksimal 3 level, gunakan query param
   /reviews/4/comments
   /comments?reviewId=4


❌ ANTI-PATTERN: Expose implementasi detail
   /api/mysql/users
   /api/v1/sql/select-all-books
   /api/internal/cache/flush

✅ BENAR: Abstraksi yang bersih
   /api/v1/users
   /api/v1/books
   /api/v1/admin/cache
```

---

# SECTION 15 — HANDS-ON EXERCISE

## Latihan Praktis

### Exercise 1: Analisis HTTP Traffic

```
TUGAS: Analisis HTTP Request menggunakan Browser DevTools

LANGKAH:
1. Buka browser Chrome/Firefox
2. Tekan F12, buka tab Network
3. Kunjungi https://jsonplaceholder.typicode.com/posts
4. Klik request yang muncul
5. Jawab pertanyaan berikut:

PERTANYAAN:
a) Apa HTTP Method yang digunakan?
b) Berapa status code response-nya?
c) Apa Content-Type response-nya?
d) Berapa lama waktu response (Time)?
e) Apakah ada Cache-Control header? Nilainya apa?
f) Berapa ukuran response body?

EXPECTED ANSWERS:
a) GET
b) 200 OK
c) application/json; charset=utf-8
d) Bervariasi, biasanya 50-200ms
e) Ada: max-age=43200 (12 jam)
f) ~28KB
```

### Exercise 2: Implementasi HTTP Server

```javascript
// ============================================================
// EXERCISE 2: Lengkapi HTTP Server berikut
// ============================================================

const http = require('http');

// Data produk (simulasi database)
let products = [
  { id: 1, name: 'Laptop', price: 8000000, stock: 10 },
  { id: 2, name: 'Mouse', price: 150000, stock: 50 },
];

const server = http.createServer((req, res) => {
  const url = new URL(req.url, `http://${req.headers.host}`);
  const pathname = url.pathname;

  // TODO 1: Implementasi GET /products
  // - Return semua products
  // - Status code: 200
  // - Support query param ?minPrice=xxx untuk filter

  // TODO 2: Implementasi GET /products/:id
  // - Return satu product berdasarkan ID
  // - Jika tidak ada: return 404 dengan pesan error

  // TODO 3: Implementasi POST /products
  // - Terima body JSON dengan name, price, stock
  // - Validasi: name dan price wajib ada
  // - Jika validasi gagal: return 400
  // - Jika berhasil: return 201 dengan data product baru

  // TODO 4: Implementasi DELETE /products/:id
  // - Hapus product berdasarkan ID
  // - Jika tidak ada: return 404
  // - Jika berhasil: return 204 (No Content)

  // Default 404
  res.writeHead(404, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({ error: 'Route not found' }));
});

server.listen(3002, () => console.log('Exercise server on port 3002'));

// ============================================================
// TEST COMMANDS (jalankan setelah implementasi):
// ============================================================
// curl http://localhost:3002/products
// curl http://localhost:3002/products?minPrice=200000
// curl http://localhost:3002/products/1
// curl http://localhost:3002/products/999
// curl -X POST http://localhost:3002/products \
//   -H "Content-Type: application/json" \
//   -d '{"name":"Keyboard","price":350000,"stock":25}'
// curl -X DELETE http://localhost:3002/products/1
```

### Exercise 3: Status Code Quiz

```
QUIZ: Pilih status code yang tepat untuk setiap skenario

Skenario 1: User berhasil login
→ Jawaban: _____

Skenario 2: User mencoba akses halaman admin tapi bukan admin
→ Jawaban: _____

Skenario 3: User belum login tapi coba akses resource protected
→ Jawaban: _____

Skenario 4: User kirim form dengan email format salah
→ Jawaban: _____

Skenario 5: Server database down, tidak bisa proses request
→ Jawaban: _____

Skenario 6: User buat order baru berhasil
→ Jawaban: _____

Skenario 7: User hapus akun, berhasil, tidak ada data dikembalikan
→ Jawaban: _____

Skenario 8: User kirim request terlalu banyak (rate limit)
→ Jawaban: _____

JAWABAN:
1. 200 OK
2. 403 Forbidden (tahu siapa dia, tapi tidak boleh)
3. 401 Unauthorized (belum terautentikasi)
4. 422 Unprocessable Entity (atau 400 Bad Request)
5. 503 Service Unavailable
6. 201 Created
7. 204 No Content
8. 429 Too Many Requests
```

---

# SECTION 16 — DEBUGGING HTTP

## Debugging HTTP: Panduan Praktis

### 16.1 Tools untuk Debugging HTTP

```
HTTP DEBUGGING TOOLKIT
══════════════════════════════════════════════════════════════

1. CURL — Command Line HTTP Client
   ─────────────────────────────────
   # Verbose output (lihat semua headers)
   curl -v https://api.example.com/users

   # Hanya tampilkan response headers
   curl -I https://api.example.com/users

   # Simpan response ke file
   curl -o response.json https://api.example.com/users

   # Custom headers
   curl -H "Authorization: Bearer token" \
        -H "Accept: application/json" \
        https://api.example.com/users

   # Timing detail
   curl -w "\nTotal time: %{time_total}s\n" \
        https://api.example.com/users

2. BROWSER DEVTOOLS
   ─────────────────────────────────
   F12 → Network Tab
   - Filter by type: XHR, Fetch, All
   - Lihat Request/Response Headers
   - Lihat Request/Response Body
   - Lihat Timing (DNS, Connect, TTFB, Download)
   - Copy as cURL untuk reproduce

3. POSTMAN / INSOMNIA
   ─────────────────────────────────
   - GUI untuk HTTP requests
   - Simpan collection requests
   - Environment variables
   - Automated testing
   - Generate code snippets

4. HTTPIE — User-friendly curl alternative
   ─────────────────────────────────
   # Install: pip install httpie
   http GET api.example.com/users
   http POST api.example.com/users name="Budi" email="budi@email.com"
   http DELETE api.example.com/users/1 Authorization:"Bearer token"

5. WIRESHARK — Network packet analyzer
   ─────────────────────────────────
   - Capture semua network traffic
   - Analisis level TCP/IP
   - Berguna untuk debugging HTTPS issues
   - Lebih advanced, untuk debugging mendalam
```

### 16.2 Debugging Checklist

```javascript
// ============================================================
// HTTP DEBUGGING CHECKLIST
// ============================================================

/*
KETIKA API TIDAK BEKERJA, CEK URUTAN INI:

1. ✅ Apakah server berjalan?
   → curl http://localhost:3000/health
   → Jika connection refused: server tidak jalan

2. ✅ Apakah URL benar?
   → Cek typo di path
   → Cek port number
   → Cek protocol (http vs https)

3. ✅ Apakah HTTP Method benar?
   → GET vs POST vs PUT vs DELETE
   → Lihat error 405 Method Not Allowed

4. ✅ Apakah Headers benar?
   → Content-Type untuk request dengan body
   → Authorization untuk protected routes
   → Accept untuk format response

5. ✅ Apakah Request Body valid?
   → Valid JSON? (gunakan JSON validator)
   → Field names benar?
   → Data types benar?

6. ✅ Baca Status Code dengan teliti
   → 400: Request kamu salah
   → 401: Perlu login/token
   → 403: Tidak punya izin
   → 404: URL salah atau resource tidak ada
   → 422: Data tidak valid
   → 500: Bug di server

7. ✅ Baca Response Body
   → Ada pesan error yang informatif?
   → Ada field yang missing?

8. ✅ Cek Server Logs
   → console.log di server
   → Error stack trace
*/

// Contoh: Middleware logging untuk debugging
function requestLogger(req, res, next) {
  const start = Date.now();

  // Log request masuk
  console.log(`→ ${req.method} ${req.url}`);
  console.log('  Headers:', JSON.stringify(req.headers, null, 2));

  // Intercept response untuk log
  const originalSend = res.send;
  res.send = function(body) {
    const duration = Date.now() - start;
    console.log(`← ${res.statusCode} (${duration}ms)`);
    console.log('  Body:', body?.substring?.(0, 200) || body);
    return originalSend.call(this, body);
  };

  next();
}
```

---

# SECTION 17 — HTTP CACHING

## HTTP Caching: Optimasi Performa

### 17.1 Konsep Caching HTTP

```
HTTP CACHING FLOW
══════════════════════════════════════════════════════════════

REQUEST PERTAMA (Cache Miss):
Client ──── GET /books ──────────────────────────────▶ Server
       ◀─── 200 OK ──────────────────────────────────
            Cache-Control: max-age=3600
            ETag: "abc123"
            [Data buku]
            ↓
       [Client simpan di cache dengan ETag]

REQUEST KEDUA (Cache Hit — dalam 1 jam):
Client ──── GET /books ──────────────────────────────▶ (Cache)
       ◀─── [Data dari cache, tidak ke server] ───────
       [Hemat bandwidth dan waktu!]

REQUEST KETIGA (Cache Expired — setelah 1 jam):
Client ──── GET /books ──────────────────────────────▶ Server
            If-None-Match: "abc123"
       ◀─── 304 Not Modified (jika data belum berubah)
            [Tidak ada body, hemat bandwidth!]
       ATAU
       ◀─── 200 OK (jika data sudah berubah)
            ETag: "def456"
            [Data buku terbaru]

CACHE-CONTROL DIRECTIVES:
┌──────────────────────┬────────────────────────────────────┐
│ Directive            │ Arti                               │
├──────────────────────┼────────────────────────────────────┤
│ max-age=3600         │ Cache selama 3600 detik (1 jam)    │
│ no-cache             │ Selalu validasi ke server          │
│ no-store             │ Jangan simpan di cache sama sekali │
│ public               │ Boleh di-cache oleh CDN/proxy      │
│ private              │ Hanya boleh di-cache oleh browser  │
│ must-revalidate      │ Wajib validasi setelah expired     │
└──────────────────────┴────────────────────────────────────┘
```

### 17.2 Implementasi Caching

```javascript
// ============================================================
// IMPLEMENTASI HTTP CACHING
// ============================================================

const http = require('http');
const crypto = require('crypto');

// Simulasi data yang bisa berubah
let booksData = [
  { id: 1, title: 'Laskar Pelangi', author: 'Andrea Hirata' },
  { id: 2, title: 'Bumi Manusia', author: 'Pramoedya' },
];

// Generate ETag dari data
function generateETag(data) {
  return crypto
    .createHash('md5')
    .update(JSON.stringify(data))
    .digest('hex');
}

const server = http.createServer((req, res) => {
  if (req.url === '/books' && req.method === 'GET') {
    const responseData = JSON.stringify(booksData);
    const etag = `"${generateETag(booksData)}"`;

    // Cek apakah client punya versi yang sama (conditional request)
    const clientETag = req.headers['if-none-match'];

    if (clientETag === etag) {
      // Data tidak berubah, kirim 304 tanpa body
      res.writeHead(304, {
        'ETag': etag,
        'Cache-Control': 'public, max-age=3600'
      });
      res.end();
      console.log('Cache HIT — 304 Not Modified');
      return;
    }

    // Data berubah atau request pertama, kirim data lengkap
    res.writeHead(200, {
      'Content-Type': 'application/json',
      'Cache-Control': 'public, max-age=3600',  // Cache 1 jam
      'ETag': etag,
      'Last-Modified': new Date().toUTCString(),
      'Vary': 'Accept-Encoding'  // Cache berbeda per encoding
    });
    res.end(responseData);
    console.log('Cache MISS — 200 OK dengan data lengkap');
    return;
  }

  // Endpoint yang tidak boleh di-cache (data sensitif/real-time)
  if (req.url === '/dashboard' && req.method === 'GET') {
    res.writeHead(200, {
      'Content-Type': 'application/json',
      'Cache-Control': 'no-store',  // Jangan cache sama sekali
      'Pragma': 'no-cache'          // Backward compatibility
    });
    res.end(JSON.stringify({
      activeUsers: Math.floor(Math.random() * 1000),
      timestamp: new Date().toISOString()
    }));
    return;
  }
});

server.listen(3003, () => console.log('Caching server on port 3003'));
```

---

# SECTION 18 — CORS (CROSS-ORIGIN RESOURCE SHARING)

## CORS: Keamanan Cross-Origin

### 18.1 Memahami CORS

```
MENGAPA CORS ADA?
══════════════════════════════════════════════════════════════

TANPA CORS (Berbahaya!):
─────────────────────────────────────────────────────────────
User login ke bank.com
User buka evil.com di tab lain
evil.com kirim request ke bank.com/transfer
Browser kirim cookie bank.com secara otomatis!
→ CSRF Attack berhasil! 💀

DENGAN SAME-ORIGIN POLICY:
─────────────────────────────────────────────────────────────
Browser BLOKIR request dari evil.com ke bank.com
karena beda origin (domain berbeda)

TAPI INI MASALAH UNTUK LEGITIMATE USE CASE:
─────────────────────────────────────────────────────────────
Frontend: https://app.tokobuku.com
Backend:  https://api.tokobuku.com

Browser blokir request dari app ke api
karena beda subdomain = beda origin!

SOLUSI: CORS Headers
─────────────────────────────────────────────────────────────
Server api.tokobuku.com bilang ke browser:
"Saya izinkan request dari app.tokobuku.com"

Access-Control-Allow-Origin: https://app.tokobuku.com

Browser: "OK, request diizinkan!"

DEFINISI SAME ORIGIN:
Origin = Protocol + Domain + Port
https://app.tokobuku.com:443

Beda origin jika SALAH SATU berbeda:
- https vs http
- app.tokobuku.com vs api.tokobuku.com
- :443 vs :3000
```

### 18.2 Implementasi CORS

```javascript
// ============================================================
// CORS IMPLEMENTATION
// ============================================================

const http = require('http');

// Konfigurasi CORS
const CORS_CONFIG = {
  // Origins yang diizinkan
  allowedOrigins: [
    'https://app.tokobuku.com',
    'https://admin.tokobuku.com',
    'http://localhost:3000',  // Development
  ],

  // Methods yang diizinkan
  allowedMethods: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],

  // Headers yang diizinkan di request
  allowedHeaders: [
    'Content-Type',
    'Authorization',
    'X-Requested-With',
    'Accept',
  ],

  // Headers yang boleh dibaca oleh browser dari response
  exposedHeaders: ['X-Total-Count', 'X-Request-ID'],

  // Apakah credentials (cookies) diizinkan
  credentials: true,

  // Berapa lama preflight result di-cache (detik)
  maxAge: 86400, // 24 jam
};

function setCORSHeaders(req, res) {
  const origin = req.headers.origin;

  // Cek apakah origin diizinkan
  if (CORS_CONFIG.allowedOrigins.includes(origin)) {
    res.setHeader('Access-Control-Allow-Origin', origin);
  } else if (CORS_CONFIG.allowedOrigins.includes('*')) {
    res.setHeader('Access-Control-Allow-Origin', '*');
  }

  res.setHeader(
    'Access-Control-Allow-Methods',
    CORS_CONFIG.allowedMethods.join(', ')
  );

  res.setHeader(
    'Access-Control-Allow-Headers',
    CORS_CONFIG.allowedHeaders.join(', ')
  );

  res.setHeader(
    'Access-Control-Expose-Headers',
    CORS_CONFIG.exposedHeaders.join(', ')
  );

  if (CORS_CONFIG.credentials) {
    res.setHeader('Access-Control-Allow-Credentials', 'true');
  }

  res.setHeader('Access-Control-Max-Age', CORS_CONFIG.maxAge);
}

const server = http.createServer((req, res) => {
  // Set CORS headers untuk SEMUA response
  setCORSHeaders(req, res);

  // Handle PREFLIGHT request (OPTIONS)
  // Browser kirim ini sebelum request "berbahaya" (POST, PUT, DELETE)
  if (req.method === 'OPTIONS') {
    res.writeHead(204); // No Content
    res.end();
    return;
  }

  // Handle actual requests
  if (req.url === '/api/books' && req.method === 'GET') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ books: [] }));
    return;
  }

  res.writeHead(404);
  res.end();
});

server.listen(3004, () => console.log('CORS server on port 3004'));

/*
CORS FLOW DIAGRAM:

SIMPLE REQUEST (GET, POST dengan simple headers):
Browser ──── GET /api/books ──────────────────────▶ Server
             Origin: https://app.tokobuku.com
        ◀─── 200 OK ──────────────────────────────
             Access-Control-Allow-Origin: https://app.tokobuku.com

PREFLIGHT REQUEST (PUT, DELETE, custom headers):
Browser ──── OPTIONS /api/books ──────────────────▶ Server
             Origin: https://app.tokobuku.com
             Access-Control-Request-Method: DELETE
             Access-Control-Request-Headers: Authorization
        ◀─── 204 No Content ──────────────────────
             Access-Control-Allow-Origin: https://app.tokobuku.com
             Access-Control-Allow-Methods: GET, POST, DELETE
             Access-Control-Allow-Headers: Authorization
             Access-Control-Max-Age: 86400

Browser ──── DELETE /api/books/1 ─────────────────▶ Server
             Origin: https://app.tokobuku.com
             Authorization: Bearer token
        ◀─── 200 OK ──────────────────────────────
*/
```

---

# SECTION 19 — SUMMARY & KEY TAKEAWAYS

## Ringkasan dan Poin Kunci

### 19.1 Recap Konsep Utama

```
RINGKASAN MODUL: HTTP & WEB FUNDAMENTALS
══════════════════════════════════════════════════════════════

1. HTTP ADALAH BAHASA INTERNET
   ────────────────────────────
   • Protocol text-based untuk komunikasi client-server
   • Stateless: setiap request independen
   • Request-Response: selalu berpasangan
   • Flexible: bisa kirim berbagai tipe data

2. ANATOMI HTTP MESSAGE
   ────────────────────────────
   REQUEST:  Method + URL + Headers + Body
   RESPONSE: Status Code + Headers + Body

3. HTTP METHODS (CRUD MAPPING)
   ────────────────────────────
   GET    → Read   (ambil data)
   POST   → Create (buat baru)
   PUT    → Update (ganti seluruhnya)
   PATCH  → Update (sebagian)
   DELETE → Delete (hapus)

4. STATUS CODES
   ────────────────────────────
   2xx → Sukses
   3xx → Redirect
   4xx → Salah client
   5xx → Salah server

5. HEADERS PENTING
   ────────────────────────────
   Content-Type    → Format data
   Authorization   → Autentikasi
   Cache-Control   → Instruksi caching
   CORS Headers    → Izin cross-origin

6. URL DESIGN
   ────────────────────────────
   Gunakan noun, bukan verb
   Plural untuk collections
   Hierarki untuk nested resources
   Query params untuk filter/sort/paginate

7. STATELESS MANAGEMENT
   ────────────────────────────
   Cookie → Web apps
   JWT    → REST API, Mobile
   Session → Server-side rendering

8. CACHING
   ────────────────────────────
   Cache-Control untuk instruksi
   ETag untuk validasi
   304 Not Modified untuk efisiensi

9. CORS
   ────────────────────────────
   Same-origin policy untuk keamanan
   CORS headers untuk izin cross-origin
   Preflight untuk request kompleks
```

### 19.2 Mental Model: HTTP sebagai Sistem Pos

```
MENTAL MODEL FINAL
══════════════════════════════════════════════════════════════

HTTP seperti sistem pos modern:

CLIENT = Pengirim surat
SERVER = Kantor pos tujuan

URL     = Alamat lengkap tujuan
Method  = Jenis layanan (kirim, ambil, hapus)
Headers = Informasi amplop (prioritas, jenis isi, pengirim)
Body    = Isi paket/surat
Status  = Tanda terima (berhasil/gagal/dialihkan)

STATELESS = Setiap surat dikirim tanpa ingat surat sebelumnya
           → Perlu tulis identitas di setiap surat (token)

HTTPS   = Surat dalam amplop tersegel yang hanya bisa
           dibuka oleh penerima yang tepat

CACHING = Fotokopi surat yang sering diminta, simpan
           di kantor cabang terdekat

CORS    = Aturan: hanya terima surat dari pengirim
           yang sudah terdaftar
```

---

# SECTION 20 — ASSESSMENT & NEXT STEPS

## Penilaian dan Langkah Selanjutnya

### 20.1 Self-Assessment Checklist

```
CHECKLIST KOMPETENSI — CENTANG JIKA SUDAH PAHAM
══════════════════════════════════════════════════════════════

LEVEL 1 — FUNDAMENTAL (Wajib)
□ Saya bisa menjelaskan apa itu HTTP dan bagaimana cara kerjanya
□ Saya memahami perbedaan HTTP dan HTTPS
□ Saya bisa membaca dan menginterpretasikan URL lengkap
□ Saya hafal 5 HTTP Methods utama dan kegunaannya
□ Saya bisa mengklasifikasikan status code berdasarkan kategori
□ Saya memahami anatomi HTTP Request dan Response
□ Saya bisa menggunakan curl untuk mengirim HTTP request

LEVEL 2 — INTERMEDIATE (Target)
□ Saya bisa membuat HTTP server sederhana dengan Node.js
□ Saya memahami dan bisa set HTTP Headers yang tepat
□ Saya bisa merancang URL yang RESTful dan semantik
□ Saya memahami konsep stateless dan cara manage state
□ Saya bisa debug HTTP issues menggunakan DevTools dan curl
□ Saya memahami konsep HTTP caching dasar
□ Saya bisa menjelaskan mengapa CORS ada dan cara kerjanya

LEVEL 3 — ADVANCED (Bonus)
□ Saya bisa implementasi caching dengan ETag dan 304
□ Saya bisa konfigurasi CORS yang aman dan tepat
□ Saya memahami perbedaan HTTP/1.1 vs HTTP/2
□ Saya bisa analisis HTTP performance menggunakan DevTools
□ Saya bisa implementasi rate limiting dasar
```

### 20.2 Project Mini: Toko Buku API

```javascript
// ============================================================
// MINI PROJECT: Toko Buku REST API
// Implementasikan API lengkap dengan semua yang telah dipelajari
// ============================================================

/*
REQUIREMENTS:

1. ENDPOINTS:
   GET    /api/v1/books              → List semua buku (dengan pagination)
   GET    /api/v1/books/:id          → Detail satu buku
   POST   /api/v1/books              → Tambah buku baru
   PUT    /api/v1/books/:id          → Update buku (seluruhnya)
   PATCH  /api/v1/books/:id          → Update buku (sebagian)
   DELETE /api/v1/books/:id          → Hapus buku
   GET    /api/v1/books/search       → Cari buku berdasarkan judul

2. RESPONSE FORMAT:
   - Gunakan envelope pattern (status, data, meta)
   - Status code yang tepat untuk setiap situasi
   - Content-Type: application/json

3. FEATURES:
   - Pagination: ?page=1&limit=10
   - Filter: ?genre=fiction&minPrice=50000
   - Sort: ?sort=price&order=asc
   - Search: ?q=laskar

4. ERROR HANDLING:
   - 400 untuk request tidak valid
   - 404 untuk resource tidak ada
   - 422 untuk validasi gagal
   - 500 untuk server error

5. HEADERS:
   - Set Cache-Control yang tepat
   - Set CORS headers
   - Set X-Total-Count untuk pagination

KRITERIA PENILAIAN:
□ Semua endpoint berfungsi dengan benar
□ Status code tepat untuk setiap skenario
□ Response format konsisten
□ Error handling lengkap
□ URL design mengikuti best practices
□ Bisa ditest dengan curl
*/
```

### 20.3 Referensi Lanjutan

```
REFERENSI UNTUK BELAJAR LEBIH DALAM
══════════════════════════════════════════════════════════════

DOKUMENTASI RESMI:
• MDN Web Docs - HTTP: https://developer.mozilla.org/en-US/docs/Web/HTTP
• RFC 7230-7235: HTTP/1.1 Specification
• RFC 7540: HTTP/2 Specification

TOOLS:
• Postman: https://www.postman.com
• Insomnia: https://insomnia.rest
• HTTPie: https://httpie.io
• curl manual: https://curl.se/docs/manual.html

BUKU:
• "HTTP: The Definitive Guide" - David Gourley
• "RESTful Web APIs" - Leonard Richardson

MODUL SELANJUTNYA:
┌─────────────────────────────────────────────────────────────┐
│ Bab 04 Module 02: REST API Design                           │
│ → Prinsip REST (Representational State Transfer)            │
│ → Richardson Maturity Model                                 │
│ → API Versioning Strategies                                 │
│ → OpenAPI/Swagger Documentation                             │
│                                                             │
│ Bab 04 Module 03: Authentication & Security                 │
│ → JWT (JSON Web Tokens)                                     │
│ → OAuth 2.0 Basics                                          │
│ → API Key Management                                        │
│ → HTTPS dan TLS                                             │
└─────────────────────────────────────────────────────────────┘
```

### 20.4 Glossary

```
GLOSARIUM ISTILAH PENTING
══════════════════════════════════════════════════════════════

API          Application Programming Interface — antarmuka
             untuk komunikasi antar sistem

Client       Pihak yang mengirim request (browser, app, service)

CORS         Cross-Origin Resource Sharing — mekanisme izin
             request lintas domain

ETag         Entity Tag — identifier unik versi resource
             untuk caching

Header       Metadata yang menyertai HTTP request/response

HTTP         HyperText Transfer Protocol — protokol komunikasi web

HTTPS        HTTP Secure — HTTP dengan enkripsi TLS/SSL

Idempotent   Operasi yang menghasilkan hasil sama meski
             dieksekusi berkali-kali

JSON         JavaScript Object Notation — format data populer

Method       Kata kerja HTTP yang menunjukkan jenis operasi

Origin       Kombinasi protocol + domain + port

Payload      Data yang dikirim dalam body request/response

Protocol     Aturan komunikasi yang disepakati bersama

Request      Pesan yang dikirim client ke server

Response     Pesan balasan dari server ke client

REST         Representational State Transfer — gaya arsitektur API

Server       Pihak yang menerima request dan mengirim response

Stateless    Setiap request independen, server tidak menyimpan
             state antar request

Status Code  Kode 3 digit yang menunjukkan hasil request

TLS/SSL      Transport Layer Security — protokol enkripsi

URL          Uniform Resource Locator — alamat resource di web

URI          Uniform Resource Identifier — identifier resource

Verb         Sinonim untuk HTTP Method
```

---

## Penutup Modul

```
╔══════════════════════════════════════════════════════════════════╗
║                    SELAMAT! 🎉                                   ║
║                                                                  ║
║  Anda telah menyelesaikan:                                       ║
║  Bab 04 Module 01 — HTTP & Web Fundamentals                      ║
║                                                                  ║
║  Yang telah Anda pelajari:                                       ║
║  ✅ Cara kerja HTTP dan siklus request-response                  ║
║  ✅ Anatomi HTTP Request dan Response                            ║
║  ✅ HTTP Methods dan kapan menggunakannya                        ║
║  ✅ HTTP Status Codes dan maknanya                               ║
║  ✅ HTTP Headers yang penting                                    ║
║  ✅ URL design yang baik                                         ║
║  ✅ State management di HTTP stateless                           ║
║  ✅ HTTP Caching untuk performa                                  ║
║  ✅ CORS untuk keamanan cross-origin                             ║
║  ✅ Debugging HTTP dengan berbagai tools                         ║
║                                                                  ║
║  Langkah selanjutnya:                                            ║
║  → Kerjakan Mini Project: Toko Buku API                          ║
║  → Lanjut ke Module 02: REST API Design                          ║
╚══════════════════════════════════════════════════════════════════╝
```

---

*Dokumen ini adalah bagian dari kurikulum **Backend Beginner** — Kategori **01-Core-Foundations**.*
*Versi: 1.0.0 | Standar: GEMINI.md Curriculum Architecture*
*Total Seksi: 20 | Estimasi Waktu Belajar: 8-10 jam*