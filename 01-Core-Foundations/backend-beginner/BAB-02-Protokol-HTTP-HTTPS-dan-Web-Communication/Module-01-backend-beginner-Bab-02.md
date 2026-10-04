# Bab 02 - Module 01: Protokol HTTP & Siklus Request-Response

## Kurikulum: Backend Beginner | Kategori: 01-Core-Foundations

---

## SEKSI 01 — IDENTITAS MODUL

```
Modul          : 02-01
Judul          : Protokol HTTP & Siklus Request-Response
Kurikulum      : backend-beginner
Kategori       : 01-Core-Foundations
Tingkat        : Beginner
Estimasi Waktu : 4 jam (teori 2 jam + praktik 2 jam)
Prasyarat      : Bab 01 - Pengenalan Backend Development
Versi          : 1.0.0
Penulis        : Senior Technical Curriculum Architect
Terakhir Diperbarui : 2024
```

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik mampu:

```
[ ] LO-01 : Menjelaskan apa itu protokol HTTP dan mengapa ia menjadi
            fondasi komunikasi web modern.

[ ] LO-02 : Mengidentifikasi komponen-komponen dalam sebuah HTTP Request
            (method, URL, headers, body) dengan benar.

[ ] LO-03 : Mengidentifikasi komponen-komponen dalam sebuah HTTP Response
            (status code, headers, body) dengan benar.

[ ] LO-04 : Membedakan HTTP Methods (GET, POST, PUT, PATCH, DELETE)
            dan menentukan kapan masing-masing digunakan.

[ ] LO-05 : Menginterpretasikan HTTP Status Codes (1xx, 2xx, 3xx,
            4xx, 5xx) dan maknanya dalam konteks backend.

[ ] LO-06 : Menjelaskan siklus lengkap Request-Response dari browser
            hingga server dan kembali ke browser.

[ ] LO-07 : Membedakan HTTP/1.1, HTTP/2, dan HTTP/3 pada level konsep.

[ ] LO-08 : Menggunakan tool (curl, Postman) untuk menginspeksi dan
            mengirim HTTP request secara manual.
```

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
┌─────────────────────────────────────────────────────────────────┐
│                    EKOSISTEM HTTP                                │
│                                                                 │
│   CLIENT                    INTERNET                 SERVER     │
│  ┌───────┐    HTTP Request  ┌─────────┐  Forward   ┌────────┐  │
│  │Browser│ ──────────────► │ Router/ │ ──────────► │ Web    │  │
│  │  /    │                 │  DNS    │             │ Server │  │
│  │ App   │ ◄────────────── │         │ ◄────────── │        │  │
│  └───────┘   HTTP Response └─────────┘             └────────┘  │
│                                                                 │
│  KOMPONEN HTTP REQUEST          KOMPONEN HTTP RESPONSE          │
│  ┌──────────────────────┐       ┌──────────────────────┐       │
│  │ Method + URL + Ver.  │       │ Version + Status Code │       │
│  │ Headers              │       │ Headers               │       │
│  │ [blank line]         │       │ [blank line]          │       │
│  │ Body (optional)      │       │ Body                  │       │
│  └──────────────────────┘       └──────────────────────┘       │
└─────────────────────────────────────────────────────────────────┘
```

**Konsep-konsep kunci dalam modul ini:**

| No | Konsep | Definisi Singkat |
|----|--------|-----------------|
| 1 | **HTTP** | HyperText Transfer Protocol — aturan komunikasi client-server |
| 2 | **Request** | Pesan yang dikirim client ke server berisi permintaan resource |
| 3 | **Response** | Pesan balasan server kepada client berisi hasil permintaan |
| 4 | **Method** | Kata kerja HTTP yang mendefinisikan aksi (GET, POST, dll) |
| 5 | **Status Code** | Kode numerik 3-digit yang menunjukkan hasil pemrosesan |
| 6 | **Headers** | Metadata tambahan yang menyertai request/response |
| 7 | **Body** | Konten utama data yang dikirim dalam request/response |
| 8 | **Stateless** | Setiap request independen, server tidak mengingat state |

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

### 4.1 Posisi HTTP dalam Ekosistem Backend

HTTP adalah **bahasa universal** yang digunakan oleh hampir seluruh aplikasi web dan API modern. Sebagai backend developer, Anda tidak hanya menulis kode — Anda menulis kode yang **berbicara melalui HTTP**. Tanpa memahami HTTP secara mendalam, Anda akan:

- Kesulitan men-debug masalah jaringan dan API
- Tidak mampu merancang API yang semantically correct
- Gagal mengoptimalkan performa aplikasi
- Tidak bisa membaca error log server dengan efektif

### 4.2 Relevansi di Dunia Nyata

```
SKENARIO NYATA YANG MEMBUTUHKAN PEMAHAMAN HTTP:

1. "API kita lambat" → Perlu memahami HTTP caching headers
2. "Login user hilang" → Perlu memahami stateless + session/cookie
3. "CORS error di frontend" → Perlu memahami HTTP headers & preflight
4. "Upload file gagal" → Perlu memahami Content-Type & multipart
5. "SEO website buruk" → Perlu memahami redirect (301 vs 302)
6. "API tidak aman" → Perlu memahami HTTPS & security headers
```

### 4.3 Fondasi untuk Topik Lanjutan

```
HTTP (Modul ini)
    │
    ├── REST API Design (Bab 05)
    ├── Authentication & Authorization (Bab 08)
    ├── Caching Strategy (Bab 11)
    ├── WebSocket & Real-time (Bab 14)
    └── API Security (Bab 16)
```

> **Analogi:** HTTP adalah seperti tata bahasa dalam komunikasi manusia. Anda bisa berbicara tanpa memahami tata bahasa secara formal, tetapi Anda tidak akan bisa berkomunikasi secara efektif, profesional, dan bebas kesalahan.

---

## SEKSI 05 — APA ITU HTTP (WHAT)

### 5.1 Definisi Formal

**HTTP (HyperText Transfer Protocol)** adalah protokol komunikasi lapisan aplikasi (*application layer*) yang mendefinisikan format dan aturan pertukaran pesan antara client dan server di atas jaringan TCP/IP.

```
OSI MODEL LAYER POSITIONING:
┌─────────────────────────────────────┐
│  Layer 7 - Application  ← HTTP/HTTPS│  ← Kita bekerja di sini
├─────────────────────────────────────┤
│  Layer 6 - Presentation             │
├─────────────────────────────────────┤
│  Layer 5 - Session                  │
├─────────────────────────────────────┤
│  Layer 4 - Transport    ← TCP/UDP   │
├─────────────────────────────────────┤
│  Layer 3 - Network      ← IP        │
├─────────────────────────────────────┤
│  Layer 2 - Data Link    ← Ethernet  │
├─────────────────────────────────────┤
│  Layer 1 - Physical     ← Kabel/WiFi│
└─────────────────────────────────────┘
```

### 5.2 Karakteristik Fundamental HTTP

```
┌─────────────────────────────────────────────────────────────┐
│ KARAKTERISTIK HTTP                                          │
│                                                             │
│ 1. STATELESS                                                │
│    Setiap request adalah transaksi independen.              │
│    Server tidak menyimpan informasi tentang request         │
│    sebelumnya dari client yang sama.                        │
│                                                             │
│ 2. TEXT-BASED (HTTP/1.1)                                    │
│    Pesan HTTP adalah teks yang dapat dibaca manusia.        │
│    HTTP/2 menggunakan binary framing untuk efisiensi.       │
│                                                             │
│ 3. CLIENT-SERVER MODEL                                      │
│    Komunikasi selalu diinisiasi oleh client.                │
│    Server hanya merespons, tidak pernah memulai.            │
│                                                             │
│ 4. REQUEST-RESPONSE PATTERN                                 │
│    Setiap komunikasi terdiri dari satu request              │
│    dan satu response yang berpasangan.                      │
│                                                             │
│ 5. EXTENSIBLE                                               │
│    Headers dapat ditambahkan untuk memperluas               │
│    fungsionalitas tanpa mengubah protokol inti.             │
└─────────────────────────────────────────────────────────────┘
```

### 5.3 Evolusi Versi HTTP

| Versi | Tahun | Fitur Utama | Status |
|-------|-------|-------------|--------|
| HTTP/0.9 | 1991 | Hanya GET, hanya HTML | Obsolete |
| HTTP/1.0 | 1996 | Headers, status codes, methods | Obsolete |
| HTTP/1.1 | 1997 | Persistent connection, chunked transfer | Masih digunakan |
| HTTP/2 | 2015 | Multiplexing, header compression, server push | Aktif |
| HTTP/3 | 2022 | QUIC protocol (UDP-based), 0-RTT | Berkembang |

---

## SEKSI 06 — BAGAIMANA HTTP BEKERJA (HOW)

### 6.1 Siklus Request-Response Lengkap

```
SIKLUS LENGKAP: User mengetik URL di browser

LANGKAH 1: DNS Resolution
┌──────────┐         ┌─────────────┐
│ Browser  │ ──────► │  DNS Server │
│          │ ◄────── │             │
└──────────┘  IP:    └─────────────┘
           93.184.216.34

LANGKAH 2: TCP Handshake (3-way)
┌──────────┐                    ┌──────────┐
│  Client  │ ──── SYN ────────► │  Server  │
│          │ ◄─── SYN-ACK ───── │          │
│          │ ──── ACK ────────► │          │
└──────────┘                    └──────────┘

LANGKAH 3: TLS Handshake (jika HTTPS)
┌──────────┐                    ┌──────────┐
│  Client  │ ── ClientHello ──► │  Server  │
│          │ ◄─ ServerHello ─── │          │
│          │ ── Key Exchange ─► │          │
│          │ ◄─ Finished ─────  │          │
└──────────┘                    └──────────┘

LANGKAH 4: HTTP Request
┌──────────┐                    ┌──────────┐
│  Client  │ ── HTTP Request ─► │  Server  │
└──────────┘                    └──────────┘

LANGKAH 5: Server Processing
                                ┌──────────┐
                                │  Server  │
                                │ ┌──────┐ │
                                │ │Router│ │
                                │ └──┬───┘ │
                                │    │     │
                                │ ┌──▼───┐ │
                                │ │Handler│ │
                                │ └──┬───┘ │
                                │    │     │
                                │ ┌──▼───┐ │
                                │ │  DB  │ │
                                │ └──────┘ │
                                └──────────┘

LANGKAH 6: HTTP Response
┌──────────┐                    ┌──────────┐
│  Client  │ ◄─ HTTP Response ─ │  Server  │
└──────────┘                    └──────────┘

LANGKAH 7: Browser Rendering
┌──────────┐
│ Browser  │
│ ┌──────┐ │
│ │ HTML │ │
│ │ CSS  │ │
│ │  JS  │ │
│ └──────┘ │
└──────────┘
```

### 6.2 Anatomi HTTP Request

```
HTTP REQUEST STRUCTURE:
═══════════════════════════════════════════════════════════

REQUEST LINE:
┌─────────────────────────────────────────────────────────┐
│  POST /api/users HTTP/1.1                               │
│  ──┬─  ────┬──── ────┬───                              │
│    │       │         └── HTTP Version                  │
│    │       └──────────── Request Target (URL Path)     │
│    └──────────────────── HTTP Method                   │
└─────────────────────────────────────────────────────────┘

HEADERS:
┌─────────────────────────────────────────────────────────┐
│  Host: api.example.com                                  │
│  Content-Type: application/json                         │
│  Content-Length: 45                                     │
│  Authorization: Bearer eyJhbGciOiJIUzI1NiJ9...         │
│  Accept: application/json                               │
│  User-Agent: Mozilla/5.0 (...)                          │
└─────────────────────────────────────────────────────────┘

BLANK LINE (WAJIB):
┌─────────────────────────────────────────────────────────┐
│  [CRLF - Carriage Return + Line Feed]                   │
└─────────────────────────────────────────────────────────┘

BODY (Optional):
┌─────────────────────────────────────────────────────────┐
│  {                                                      │
│    "name": "Budi Santoso",                              │
│    "email": "budi@example.com"                          │
│  }                                                      │
└─────────────────────────────────────────────────────────┘
```

### 6.3 Anatomi HTTP Response

```
HTTP RESPONSE STRUCTURE:
═══════════════════════════════════════════════════════════

STATUS LINE:
┌─────────────────────────────────────────────────────────┐
│  HTTP/1.1 201 Created                                   │
│  ────┬─── ─┬─ ──────                                   │
│      │     │   └── Reason Phrase (deskripsi teks)      │
│      │     └────── Status Code (3 digit)               │
│      └──────────── HTTP Version                        │
└─────────────────────────────────────────────────────────┘

HEADERS:
┌─────────────────────────────────────────────────────────┐
│  Content-Type: application/json                         │
│  Content-Length: 89                                     │
│  Location: /api/users/123                               │
│  X-Request-ID: req-abc-123                              │
│  Cache-Control: no-cache                                │
│  Date: Mon, 15 Jan 2024 10:30:00 GMT                    │
└─────────────────────────────────────────────────────────┘

BLANK LINE (WAJIB):
┌─────────────────────────────────────────────────────────┐
│  [CRLF]                                                 │
└─────────────────────────────────────────────────────────┘

BODY:
┌─────────────────────────────────────────────────────────┐
│  {                                                      │
│    "id": 123,                                           │
│    "name": "Budi Santoso",                              │
│    "email": "budi@example.com",                         │
│    "created_at": "2024-01-15T10:30:00Z"                 │
│  }                                                      │
└─────────────────────────────────────────────────────────┘
```

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### 7.1 HTTP Methods Decision Tree

```
KAPAN MENGGUNAKAN HTTP METHOD APA?

Anda ingin melakukan operasi apa?
│
├── MEMBACA data?
│   └── GET
│       ├── Tidak mengubah data di server
│       ├── Dapat di-cache
│       ├── Dapat di-bookmark
│       └── Body request: TIDAK ADA
│
├── MEMBUAT data baru?
│   └── POST
│       ├── Membuat resource baru
│       ├── Tidak idempotent*
│       ├── Response: 201 Created
│       └── Body request: ADA (data baru)
│
├── MENGGANTI data SELURUHNYA?
│   └── PUT
│       ├── Replace complete resource
│       ├── Idempotent*
│       ├── Response: 200 OK atau 204 No Content
│       └── Body request: ADA (data lengkap)
│
├── MENGUBAH data SEBAGIAN?
│   └── PATCH
│       ├── Partial update
│       ├── Idempotent (umumnya)
│       ├── Response: 200 OK
│       └── Body request: ADA (field yang diubah saja)
│
└── MENGHAPUS data?
    └── DELETE
        ├── Menghapus resource
        ├── Idempotent*
        ├── Response: 204 No Content
        └── Body request: Biasanya tidak ada

*Idempotent: Mengirim request yang sama berkali-kali
             menghasilkan efek yang sama seperti sekali kirim.
```

### 7.2 Status Code Map

```
HTTP STATUS CODE LANDSCAPE:
═══════════════════════════════════════════════════════════════

1xx INFORMATIONAL (Jarang ditemui langsung)
├── 100 Continue
└── 101 Switching Protocols (WebSocket upgrade)

2xx SUCCESS ✓
├── 200 OK              → Request berhasil, ada response body
├── 201 Created         → Resource baru berhasil dibuat
├── 202 Accepted        → Request diterima, diproses async
├── 204 No Content      → Berhasil, tidak ada response body
└── 206 Partial Content → Range request (streaming video)

3xx REDIRECTION →
├── 301 Moved Permanently  → URL berubah permanen (SEO-friendly)
├── 302 Found              → Redirect sementara
├── 304 Not Modified       → Cache masih valid, gunakan cache
└── 307 Temporary Redirect → Redirect sementara, method dipertahankan

4xx CLIENT ERROR ✗ (Salah di sisi client)
├── 400 Bad Request        → Request malformed/invalid
├── 401 Unauthorized       → Belum login / token invalid
├── 403 Forbidden          → Login tapi tidak punya izin
├── 404 Not Found          → Resource tidak ditemukan
├── 405 Method Not Allowed → Method tidak didukung endpoint ini
├── 409 Conflict           → Konflik state (email sudah terdaftar)
├── 422 Unprocessable      → Validasi gagal
└── 429 Too Many Requests  → Rate limit terlampaui

5xx SERVER ERROR ✗ (Salah di sisi server)
├── 500 Internal Server Error → Bug di server
├── 502 Bad Gateway           → Upstream server error
├── 503 Service Unavailable   → Server overload/maintenance
└── 504 Gateway Timeout       → Upstream server timeout
```

### 7.3 Persistent Connection vs Non-Persistent

```
HTTP/1.0 - NON-PERSISTENT CONNECTION:
┌────────┐                              ┌────────┐
│ Client │                              │ Server │
└───┬────┘                              └───┬────┘
    │──── TCP Connect ──────────────────────►│
    │──── GET /index.html ──────────────────►│
    │◄─── 200 OK (HTML) ────────────────────│
    │──── TCP Close ─────────────────────────►│
    │                                        │
    │──── TCP Connect ──────────────────────►│  ← Koneksi baru!
    │──── GET /style.css ───────────────────►│
    │◄─── 200 OK (CSS) ─────────────────────│
    │──── TCP Close ─────────────────────────►│
    │                                        │
    │──── TCP Connect ──────────────────────►│  ← Koneksi baru lagi!
    │──── GET /script.js ───────────────────►│
    │◄─── 200 OK (JS) ──────────────────────│
    │──── TCP Close ─────────────────────────►│
    │                                        │
    OVERHEAD: 3 TCP handshake untuk 3 file

HTTP/1.1 - PERSISTENT CONNECTION (Keep-Alive):
┌────────┐                              ┌────────┐
│ Client │                              │ Server │
└───┬────┘                              └───┬────┘
    │──── TCP Connect ──────────────────────►│
    │──── GET /index.html ──────────────────►│
    │◄─── 200 OK (HTML) ────────────────────│
    │                                        │  ← Koneksi TETAP TERBUKA
    │──── GET /style.css ───────────────────►│
    │◄─── 200 OK (CSS) ─────────────────────│
    │                                        │  ← Koneksi TETAP TERBUKA
    │──── GET /script.js ───────────────────►│
    │◄─── 200 OK (JS) ──────────────────────│
    │──── TCP Close ─────────────────────────►│
    │                                        │
    EFISIENSI: 1 TCP handshake untuk 3 file
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

### 8.1 HTTP Request Paling Sederhana

Bayangkan Anda membuka browser dan mengetik `http://example.com/hello`.

**Yang sebenarnya dikirim browser ke server (teks mentah):**

```
GET /hello HTTP/1.1
Host: example.com
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)
Accept: text/html,application/xhtml+xml
Accept-Language: id-ID,id;q=0.9,en;q=0.8
Connection: keep-alive

```
*(baris kosong di akhir adalah bagian dari protokol)*

**Yang server kirimkan kembali:**

```
HTTP/1.1 200 OK
Content-Type: text/html; charset=UTF-8
Content-Length: 48
Date: Mon, 15 Jan 2024 10:00:00 GMT
Server: Apache/2.4.41

<html><body><h1>Halo, Dunia!</h1></body></html>
```

### 8.2 Analogi Kehidupan Nyata

```
HTTP REQUEST-RESPONSE ≈ MEMESAN MAKANAN DI RESTORAN

CLIENT (Anda)                    SERVER (Restoran)
─────────────────────────────────────────────────────
Anda duduk di meja               Server terhubung ke internet
Memanggil pelayan         →      Menerima koneksi
Memesan "Nasi Goreng"     →      HTTP GET /menu/nasi-goreng
  + "Meja 5"              →        Host: restoran.com
  + "Tanpa Pedas"         →        X-Preference: no-spicy

Pelayan ke dapur          →      Server memproses request
Dapur memasak             →      Database query / business logic

Pelayan kembali           →      HTTP Response
  Status: "Pesanan siap"  →        200 OK
  Makanan di piring       →        Body: {data: "nasi goreng"}
  Struk tagihan           →        Headers: Content-Type, etc.

Anda makan, selesai       →      Koneksi ditutup (stateless)
Pelayan tidak ingat Anda  →      Server tidak ingat request ini
  saat Anda datang lagi   →        (kecuali ada session/cookie)
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

### 9.1 Menggunakan `curl` untuk Menginspeksi HTTP

`curl` adalah tool command-line yang memungkinkan kita mengirim HTTP request dan melihat response secara detail.

**Instalasi (jika belum ada):**
```bash
# Ubuntu/Debian
sudo apt-get install curl

# macOS (sudah terinstall)
curl --version

# Windows (tersedia di PowerShell modern)
curl --version
```

**Contoh 1: GET Request Sederhana**
```bash
# Kirim GET request dan tampilkan response
curl https://httpbin.org/get

# Output yang diharapkan:
# {
#   "args": {},
#   "headers": {
#     "Accept": "*/*",
#     "Host": "httpbin.org",
#     "User-Agent": "curl/7.68.0"
#   },
#   "url": "https://httpbin.org/get"
# }
```

**Contoh 2: Melihat Headers Request dan Response**
```bash
# Flag -v (verbose) menampilkan semua detail
curl -v https://httpbin.org/get

# Output verbose:
# * Trying 54.208.105.16:443...
# * Connected to httpbin.org
# * TLS handshake...
# > GET /get HTTP/2              ← Request line
# > Host: httpbin.org            ← Request headers
# > User-Agent: curl/7.68.0
# > Accept: */*
# >
# < HTTP/2 200                   ← Response status
# < content-type: application/json  ← Response headers
# < content-length: 255
# <
# { ... }                        ← Response body
```

**Contoh 3: POST Request dengan JSON Body**
```bash
curl -X POST https://httpbin.org/post \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer token123" \
  -d '{
    "name": "Budi Santoso",
    "email": "budi@example.com"
  }'

# Penjelasan flags:
# -X POST          → Tentukan HTTP method
# -H "..."         → Tambahkan header
# -d '{...}'       → Request body (data)
```

**Contoh 4: Melihat Hanya Status Code**
```bash
# Hanya tampilkan status code
curl -o /dev/null -s -w "%{http_code}\n" https://httpbin.org/status/404

# Output: 404
```

**Contoh 5: PUT Request (Update Data)**
```bash
curl -X PUT https://httpbin.org/put \
  -H "Content-Type: application/json" \
  -d '{
    "id": 123,
    "name": "Budi Santoso Updated",
    "email": "budi.new@example.com",
    "role": "admin"
  }'
```

**Contoh 6: DELETE Request**
```bash
curl -X DELETE https://httpbin.org/delete \
  -H "Authorization: Bearer token123"

# Response: 200 OK dengan konfirmasi
```

**Contoh 7: PATCH Request (Partial Update)**
```bash
curl -X PATCH https://httpbin.org/patch \
  -H "Content-Type: application/json" \
  -d '{
    "email": "budi.baru@example.com"
  }'
# Hanya mengirim field yang berubah
```

### 9.2 Membuat Simple HTTP Server dengan Node.js

```javascript
// file: simple-http-server.js
// Jalankan: node simple-http-server.js
// Test: curl http://localhost:3000/

const http = require('http');

const server = http.createServer((req, res) => {
  // Log setiap request yang masuk
  console.log(`\n=== REQUEST DITERIMA ===`);
  console.log(`Method  : ${req.method}`);
  console.log(`URL     : ${req.url}`);
  console.log(`Headers : ${JSON.stringify(req.headers, null, 2)}`);

  // Routing sederhana berdasarkan method dan URL
  if (req.method === 'GET' && req.url === '/') {
    // Response untuk halaman utama
    res.writeHead(200, {
      'Content-Type': 'text/html; charset=UTF-8',
      'X-Custom-Header': 'Belajar-HTTP'
    });
    res.end('<h1>Selamat Datang di HTTP Server!</h1>');

  } else if (req.method === 'GET' && req.url === '/api/users') {
    // Response JSON untuk API endpoint
    const users = [
      { id: 1, name: 'Budi Santoso' },
      { id: 2, name: 'Siti Rahayu' }
    ];

    res.writeHead(200, {
      'Content-Type': 'application/json'
    });
    res.end(JSON.stringify({ data: users, total: users.length }));

  } else if (req.method === 'POST' && req.url === '/api/users') {
    // Baca request body
    let body = '';
    req.on('data', chunk => { body += chunk.toString(); });
    req.on('end', () => {
      const newUser = JSON.parse(body);
      console.log('Data diterima:', newUser);

      // Simulasi user baru dibuat
      const createdUser = { id: 3, ...newUser, created_at: new Date() };

      res.writeHead(201, {
        'Content-Type': 'application/json',
        'Location': `/api/users/3`
      });
      res.end(JSON.stringify({ data: createdUser }));
    });

  } else {
    // 404 untuk route yang tidak dikenal
    res.writeHead(404, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      error: 'Not Found',
      message: `Route ${req.method} ${req.url} tidak ditemukan`
    }));
  }
});

server.listen(3000, () => {
  console.log('Server berjalan di http://localhost:3000');
  console.log('Coba: curl http://localhost:3000/');
  console.log('Coba: curl http://localhost:3000/api/users');
  console.log('Coba: curl -X POST http://localhost:3000/api/users \\');
  console.log('       -H "Content-Type: application/json" \\');
  console.log('       -d \'{"name":"Andi","email":"andi@test.com"}\'');
});
```

**Output saat dijalankan dan ditest:**
```bash
$ node simple-http-server.js
Server berjalan di http://localhost:3000

# Saat curl http://localhost:3000/api/users dijalankan:
=== REQUEST DITERIMA ===
Method  : GET
URL     : /api/users
Headers : {
  "host": "localhost:3000",
  "user-agent": "curl/7.68.0",
  "accept": "*/*"
}
```

### 9.3 Menggunakan Postman (GUI Tool)

```
LANGKAH MENGGUNAKAN POSTMAN:

1. Download & Install Postman dari https://postman.com

2. Buat Request Baru:
   ┌─────────────────────────────────────────────────┐
   │  [GET ▼] [https://httpbin.org/get         ] [Send]│
   └─────────────────────────────────────────────────┘

3. Tab yang tersedia:
   ┌──────┬────────┬─────────┬──────┬──────────────┐
   │Params│ Auth   │ Headers │ Body │ Pre-req Script│
   └──────┴────────┴─────────┴──────┴──────────────┘

4. Untuk POST dengan JSON body:
   - Method: POST
   - URL: https://httpbin.org/post
   - Tab Body → raw → JSON
   - Isi body:
     {
       "name": "Test User",
       "email": "test@example.com"
     }

5. Klik Send → Lihat Response di bawah:
   ┌─────────────────────────────────────────────────┐
   │ Status: 200 OK  Time: 234ms  Size: 512B         │
   ├─────────────────────────────────────────────────┤
   │ Body  Cookies  Headers  Test Results            │
   ├─────────────────────────────────────────────────┤
   │ {                                               │
   │   "json": {                                     │
   │     "email": "test@example.com",                │
   │     "name": "Test User"                         │
   │   },                                            │
   │   ...                                           │
   │ }                                               │
   └─────────────────────────────────────────────────┘
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

### 10.1 HTTP Methods: Trade-offs

```
┌─────────────────────────────────────────────────────────────────┐
│ METHOD   │ KEUNTUNGAN              │ KETERBATASAN               │
├──────────┼─────────────────────────┼────────────────────────────┤
│ GET      │ • Dapat di-cache        │ • Tidak ada body           │
│          │ • Dapat di-bookmark     │ • Data di URL (terbatas)   │
│          │ • Idempotent & safe     │ • Tidak untuk data sensitif│
├──────────┼─────────────────────────┼────────────────────────────┤
│ POST     │ • Body bisa besar       │ • Tidak idempotent         │
│          │ • Data tidak di URL     │ • Tidak bisa di-cache      │
│          │ • Fleksibel             │ • Double-submit risk       │
├──────────┼─────────────────────────┼────────────────────────────┤
│ PUT      │ • Idempotent            │ • Harus kirim data lengkap │
│          │ • Semantik jelas        │ • Bandwidth lebih besar    │
├──────────┼─────────────────────────┼────────────────────────────┤
│ PATCH    │ • Hemat bandwidth       │ • Implementasi lebih rumit │
│          │ • Partial update        │ • Tidak selalu idempotent  │
├──────────┼─────────────────────────┼────────────────────────────┤
│ DELETE   │ • Semantik jelas        │ • Tidak bisa di-undo       │
│          │ • Idempotent            │ • Perlu konfirmasi extra   │
└─────────────────────────────────────────────────────────────────┘
```

### 10.2 HTTP vs HTTPS

```
HTTP                          HTTPS
─────────────────────────────────────────────────────────
✓ Lebih cepat (no TLS)       ✓ Terenkripsi (aman)
✓ Tidak perlu sertifikat     ✓ Autentikasi server
✗ Data bisa disadap          ✓ Integritas data
✗ Tidak ada autentikasi      ✓ SEO lebih baik (Google)
✗ Tidak aman untuk produksi  ✗ Sedikit lebih lambat
                              ✗ Perlu sertifikat SSL/TLS

KESIMPULAN: Selalu gunakan HTTPS di produksi.
            HTTP hanya untuk development lokal.
```

### 10.3 Stateless: Keuntungan dan Tantangan

```
STATELESS HTTP:

KEUNTUNGAN:
┌─────────────────────────────────────────────────────────┐
│ ✓ Scalability tinggi                                    │
│   → Setiap server bisa handle request manapun           │
│   → Mudah horizontal scaling                            │
│                                                         │
│ ✓ Reliability                                           │
│   → Jika satu server mati, request bisa ke server lain  │
│                                                         │
│ ✓ Simplicity                                            │
│   → Server tidak perlu manage state per-client          │
│   → Lebih mudah di-debug                                │
└─────────────────────────────────────────────────────────┘

TANTANGAN:
┌─────────────────────────────────────────────────────────┐
│ ✗ Setiap request harus membawa konteks sendiri          │
│   → Token/session harus dikirim di setiap request       │
│                                                         │
│ ✗ Overhead per request lebih besar                      │
│   → Headers authentication berulang                     │
│                                                         │
│ SOLUSI UMUM:                                            │
│   → Cookie untuk session ID                             │
│   → JWT (JSON Web Token) di Authorization header        │
│   → Session store di Redis/database                     │
└─────────────────────────────────────────────────────────┘
```

---

## SEKSI 11 — BEST PRACTICES

### 11.1 Penggunaan HTTP Methods yang Benar

```
✅ BENAR:
GET    /api/users          → Ambil semua user
GET    /api/users/123      → Ambil user dengan ID 123
POST   /api/users          → Buat user baru
PUT    /api/users/123      → Ganti seluruh data user 123
PATCH  /api/users/123      → Update sebagian data user 123
DELETE /api/users/123      → Hapus user 123

❌ SALAH (Anti-pattern):
GET    /api/deleteUser?id=123    → Jangan gunakan GET untuk hapus
GET    /api/createUser           → Jangan gunakan GET untuk buat
POST   /api/getUsers             → Jangan gunakan POST untuk baca
DELETE /api/users                → Terlalu berbahaya (hapus semua?)
```

### 11.2 Penggunaan Status Code yang Tepat

```
✅ BENAR:
POST /api/users → 201 Created (bukan 200 OK)
DELETE /api/users/123 → 204 No Content (bukan 200 OK)
GET /api/users/999 → 404 Not Found (bukan 200 dengan body kosong)
POST /api/login (password salah) → 401 Unauthorized
GET /api/admin (user biasa) → 403 Forbidden

❌ SALAH:
Semua response → 200 OK dengan error di body
  {
    "status": "error",    ← Ini anti-pattern!
    "code": 404,          ← Status code harus di HTTP header
    "message": "Not found"
  }
```

### 11.3 Header Best Practices

```
SELALU SERTAKAN:
┌─────────────────────────────────────────────────────────┐
│ Content-Type: application/json                          │
│   → Selalu deklarasikan tipe konten                     │
│                                                         │
│ Content-Length: [size]                                  │
│   → Membantu client mengalokasikan buffer               │
│                                                         │
│ Cache-Control: no-cache / max-age=3600                  │
│   → Kontrol caching behavior secara eksplisit           │
│                                                         │
│ X-Request-ID: [uuid]                                    │
│   → Untuk tracing dan debugging di distributed system   │
└─────────────────────────────────────────────────────────┘

SECURITY HEADERS (Wajib di Produksi):
┌─────────────────────────────────────────────────────────┐
│ Strict-Transport-Security: max-age=31536000             │
│ X-Content-Type-Options: nosniff                         │
│ X-Frame-Options: DENY                                   │
│ Content-Security-Policy: default-src 'self'             │
└─────────────────────────────────────────────────────────┘
```

### 11.4 Checklist Best Practices

```
CHECKLIST HTTP BEST PRACTICES:

REQUEST:
[ ] Gunakan HTTP method yang semantically benar
[ ] Sertakan Content-Type header jika ada body
[ ] Gunakan HTTPS di produksi
[ ] Jangan taruh data sensitif di URL (query string)
[ ] Sertakan Authorization header untuk endpoint terproteksi

RESPONSE:
[ ] Gunakan status code yang tepat dan konsisten
[ ] Selalu sertakan Content-Type header
[ ] Sertakan error message yang informatif (tapi tidak bocorkan detail internal)
[ ] Implementasikan proper caching headers
[ ] Sertakan X-Request-ID untuk tracing
[ ] Jangan expose stack trace di response produksi
```

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 12.1 Kesalahan Pemula yang Sering Terjadi

```
KESALAHAN 01: Menggunakan GET untuk operasi yang mengubah data
─────────────────────────────────────────────────────────────
❌ SALAH:
GET /api/users/123/delete

✅ BENAR:
DELETE /api/users/123

MENGAPA BERBAHAYA:
→ Browser/proxy bisa cache GET request
→ Web crawler bisa tidak sengaja menghapus data
→ Melanggar prinsip HTTP (GET harus "safe")

═══════════════════════════════════════════════════════════════

KESALAHAN 02: Selalu return 200 OK
─────────────────────────────────────────────────────────────
❌ SALAH:
// User tidak ditemukan tapi return 200
res.status(200).json({ error: "User not found" });

✅ BENAR:
res.status(404).json({ error: "User not found" });

MENGAPA BERBAHAYA:
→ Client tidak bisa detect error secara otomatis
→ Monitoring tools tidak bisa track error rate
→ Melanggar HTTP specification

═══════════════════════════════════════════════════════════════

KESALAHAN 03: Menyimpan data sensitif di URL
─────────────────────────────────────────────────────────────
❌ SALAH:
GET /api/users?password=rahasia123&token=abc

✅ BENAR:
POST /api/login
Body: { "password": "rahasia123" }
Header: Authorization: Bearer abc

MENGAPA BERBAHAYA:
→ URL tersimpan di browser history
→ URL tersimpan di server access log
→ URL bisa ter-leak di Referer header

═══════════════════════════════════════════════════════════════

KESALAHAN 04: Tidak handle error HTTP dengan benar
─────────────────────────────────────────────────────────────
❌ SALAH:
fetch('/api/users')
  .then(res => res.json())  // Tidak cek status!
  .then(data => console.log(data));

✅ BENAR:
fetch('/api/users')
  .then(res => {
    if (!res.ok) {  // Cek apakah status 2xx
      throw new Error(`HTTP Error: ${res.status}`);
    }
    return res.json();
  })
  .then(data => console.log(data))
  .catch(err => console.error('Error:', err));
```

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Exercise 01: Inspeksi HTTP Request (Tingkat: Mudah)

```
TUJUAN: Memahami struktur HTTP request dengan melihat raw request

LANGKAH:
1. Buka terminal
2. Jalankan perintah berikut satu per satu:

# a. GET request sederhana
curl -v http://httpbin.org/get 2>&1 | head -30

# b. POST request dengan body
curl -v -X POST http://httpbin.org/post \
  -H "Content-Type: application/json" \
  -d '{"nama": "Belajar HTTP"}' 2>&1

# c. Lihat hanya response headers
curl -I http://httpbin.org/get

PERTANYAAN:
1. Apa perbedaan output antara -v dan -I?
2. Header apa saja yang dikirim curl secara otomatis?
3. Apa yang berbeda antara request GET dan POST?

JAWABAN YANG DIHARAPKAN:
- -v menampilkan request + response lengkap
- -I hanya menampilkan response headers (HEAD method)
- curl otomatis mengirim: Host, User-Agent, Accept
- POST memiliki Content-Type dan Content-Length header
```

### Exercise 02: Membuat HTTP Server Sederhana (Tingkat: Menengah)

```javascript
// TUGAS: Lengkapi kode berikut
// File: exercise-02.js

const http = require('http');

const server = http.createServer((req, res) => {
  // TODO 1: Log method dan URL setiap request

  // TODO 2: Handle GET /api/products
  // Return: [{id:1, name:"Laptop"}, {id:2, name:"Mouse"}]
  // Status: 200

  // TODO 3: Handle POST /api/products
  // Baca body, parse JSON, return data yang diterima
  // Status: 201

  // TODO 4: Handle semua route lain
  // Return: {error: "Not Found"}
  // Status: 404
});

server.listen(3000, () => {
  console.log('Server running on port 3000');
});

// TEST COMMANDS:
// curl http://localhost:3000/api/products
// curl -X POST http://localhost:3000/api/products \
//   -H "Content-Type: application/json" \
//   -d '{"name":"Keyboard","price":150000}'
// curl http://localhost:3000/unknown
```

### Exercise 03: Status Code Detective (Tingkat: Mudah)

```bash
# Gunakan httpbin.org untuk trigger berbagai status code
# dan catat apa yang terjadi

# 1. Trigger 200 OK
curl -s -o /dev/null -w "Status: %{http_code}\n" \
  http://httpbin.org/status/200

# 2. Trigger 404 Not Found
curl -s -o /dev/null -w "Status: %{http_code}\n" \
  http://httpbin.org/status/404

# 3. Trigger 500 Internal Server Error
curl -s -o /dev/null -w "Status: %{http_code}\n" \
  http://httpbin.org/status/500

# 4. Trigger 301 Redirect (dan ikuti redirect)
curl -v -L http://httpbin.org/redirect/1

# PERTANYAAN:
# - Apa yang terjadi saat curl mengikuti redirect (-L flag)?
# - Berapa request yang terjadi untuk redirect?
# - Apa perbedaan 401 vs 403?
```

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

### 14.1 Quiz Pilihan Ganda

```
PERTANYAAN 01:
Anda ingin mengambil daftar semua produk dari API.
HTTP method apa yang paling tepat?

A) POST /api/products
B) GET /api/products       ← BENAR
C) FETCH /api/products
D) READ /api/products

ALASAN: GET digunakan untuk membaca/mengambil data.
        Tidak mengubah state server, dapat di-cache.

───────────────────────────────────────────────────────────────

PERTANYAAN 02:
User berhasil membuat akun baru. Status code apa yang
paling tepat dikembalikan server?

A) 200 OK
B) 201 Created             ← BENAR
C) 204 No Content
D) 202 Accepted

ALASAN: 201 Created secara spesifik menandakan bahwa
        resource baru berhasil dibuat.

───────────────────────────────────────────────────────────────

PERTANYAAN 03:
User mengirim request ke /api/admin tetapi user tersebut
sudah login namun tidak memiliki role admin.
Status code apa yang tepat?

A) 401 Unauthorized
B) 404 Not Found
C) 403 Forbidden           ← BENAR
D) 400 Bad Request

ALASAN: 401 = belum autentikasi (belum login)
        403 = sudah autentikasi tapi tidak punya izin

───────────────────────────────────────────────────────────────

PERTANYAAN 04:
Apa yang dimaksud dengan HTTP bersifat "stateless"?

A) HTTP tidak bisa menyimpan file
B) Setiap request independen, server tidak mengingat
   request sebelumnya                                  ← BENAR
C) HTTP tidak memiliki state machine
D) Server selalu dalam keadaan idle

───────────────────────────────────────────────────────────────

PERTANYAAN 05:
Anda ingin mengupdate HANYA field email dari user ID 123,
tanpa mengubah field lainnya. Method apa yang tepat?

A) PUT /api/users/123
B) POST /api/users/123
C) PATCH /api/users/123    ← BENAR
D) UPDATE /api/users/123

ALASAN: PATCH untuk partial update.
        PUT mengharuskan pengiriman seluruh data resource.
```

### 14.2 Checklist Pemahaman Mandiri

```
Centang jika Anda sudah memahami konsep berikut:

LEVEL DASAR:
[ ] Saya bisa menjelaskan apa itu HTTP dengan kata-kata sendiri
[ ] Saya tahu perbedaan HTTP Request dan HTTP Response
[ ] Saya bisa menyebutkan 5 HTTP methods dan kegunaannya
[ ] Saya bisa menginterpretasikan status code 200, 201, 400, 401, 403, 404, 500

LEVEL MENENGAH:
[ ] Saya bisa membaca raw HTTP request/response
[ ] Saya bisa menggunakan curl untuk mengirim berbagai jenis request
[ ] Saya memahami perbedaan 401 vs 403
[ ] Saya memahami mengapa HTTP bersifat stateless

LEVEL LANJUTAN:
[ ] Saya bisa membuat simple HTTP server dari scratch
[ ] Saya memahami perbedaan PUT vs PATCH
[ ] Saya tahu kapan menggunakan 204 vs 200
[ ] Saya memahami konsep idempotency
```

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

### 15.1 Dokumentasi Resmi

```
REFERENSI PRIMER:
┌─────────────────────────────────────────────────────────────┐
│ 1. MDN Web Docs - HTTP                                      │
│    https://developer.mozilla.org/en-US/docs/Web/HTTP        │
│    → Referensi paling lengkap dan mudah dipahami            │
│                                                             │
│ 2. RFC 9110 - HTTP Semantics (2022)                         │
│    https://www.rfc-editor.org/rfc/rfc9110                   │
│    → Spesifikasi resmi HTTP (untuk pembaca advanced)        │
│                                                             │
│ 3. HTTP/2 Explained                                         │
│    https://http2-explained.haxx.se/                         │
│    → Penjelasan HTTP/2 oleh Daniel Stenberg (pembuat curl)  │
└─────────────────────────────────────────────────────────────┘

TOOLS UNTUK BELAJAR:
┌─────────────────────────────────────────────────────────────┐
│ 1. httpbin.org  → API testing playground                    │
│ 2. Postman      → GUI HTTP client                           │
│ 3. curl         → CLI HTTP client                           │
│ 4. Insomnia     → Alternatif Postman                        │
│ 5. HTTPie       → curl yang lebih user-friendly             │
└─────────────────────────────────────────────────────────────┘
```

### 15.2 Topik Lanjutan yang Berkaitan

```
SETELAH MODUL INI, PELAJARI:

Immediate Next Steps:
├── Bab 02-02: URL Structure & Query Parameters
├── Bab 02-03: HTTP Headers Deep Dive
└── Bab 02-04: HTTPS & TLS/SSL Basics

Medium Term:
├── Bab 05: REST API Design Principles
├── Bab 06: JSON & Data Serialization
└── Bab 08: Authentication (JWT, Session, OAuth)

Long Term:
├── Bab 14: WebSocket & Server-Sent Events
├── Bab 16: API Security
└── Bab 18: HTTP Caching Strategies
```

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

### 16.1 Key Takeaways

```
╔═════════════════════════════════════════════════════════════╗
║              RINGKASAN MODUL 02-01                         ║
║           Protokol HTTP & Siklus Request-Response          ║
╠═════════════════════════════════════════════════════════════╣
║                                                             ║
║  1. HTTP adalah protokol komunikasi client-server yang      ║
║     menjadi fondasi seluruh komunikasi web modern.          ║
║                                                             ║
║  2. HTTP bersifat STATELESS — setiap request independen.    ║
║     Gunakan session/token untuk maintain state.             ║
║                                                             ║
║  3. HTTP Request terdiri dari:                              ║
║     Method + URL + Version | Headers | Body                 ║
║                                                             ║
║  4. HTTP Response terdiri dari:                             ║
║     Version + Status Code | Headers | Body                  ║
║                                                             ║
║  5. HTTP Methods:                                           ║
║     GET=baca, POST=buat, PUT=ganti semua,                   ║
║     PATCH=update sebagian, DELETE=hapus                     ║
║                                                             ║
║  6. Status Codes:                                           ║
║     2xx=sukses, 3xx=redirect, 4xx=error client,             ║
║     5xx=error server                                        ║
║                                                             ║
║  7. Gunakan method dan status code yang SEMANTICALLY        ║
║     CORRECT — ini adalah tanda backend developer profesional║
║                                                             ║
║  8. Selalu gunakan HTTPS di production environment.         ║
║                                                             ║
╚═════════════════════════════════════════════════════════════╝
```

### 16.2 Mental Model untuk Diingat

```
HTTP = SURAT MENYURAT DIGITAL

REQUEST (Surat yang Anda kirim):
┌─────────────────────────────────┐
│ Kepada: api.example.com         │ ← Host header
│ Perihal: Minta data user        │ ← URL + Method
│ Dari: Browser/App Anda          │ ← User-Agent
│ Token: Bearer xyz123            │ ← Authorization
│ ─────────────────────────────── │
│ Isi surat (jika ada):           │ ← Body
│ { "data": "..." }               │
└─────────────────────────────────┘

RESPONSE (Balasan yang Anda terima):
┌─────────────────────────────────┐
│ Status: 200 OK / 404 Not Found  │ ← Status Code
│ Jenis konten: application/json  │ ← Content-Type
│ Tanggal: 15 Jan 2024            │ ← Date
│ ─────────────────────────────── │
│ Isi balasan:                    │ ← Body
│ { "users": [...] }              │
└─────────────────────────────────┘
```

---

## SEKSI 17 — GLOSARIUM

```
GLOSARIUM ISTILAH TEKNIS MODUL 02-01:
═══════════════════════════════════════════════════════════════

API (Application Programming Interface)
  → Antarmuka yang memungkinkan komunikasi antar aplikasi.
  → Dalam konteks web, biasanya menggunakan HTTP.

Body
  → Bagian dari HTTP message yang berisi konten/data utama.
  → Opsional di request, umumnya ada di response.

Cache
  → Penyimpanan sementara response untuk menghindari
    request berulang ke server.

CORS (Cross-Origin Resource Sharing)
  → Mekanisme keamanan browser yang mengontrol akses
    resource dari domain berbeda menggunakan HTTP headers.

DNS (Domain Name System)
  → Sistem yang menerjemahkan nama domain (example.com)
    menjadi alamat IP (93.184.216.34).

Header
  → Metadata yang menyertai HTTP request/response.
  → Format: "Nama-Header: nilai"

HTTP (HyperText Transfer Protocol)
  → Protokol komunikasi lapisan aplikasi untuk web.

HTTPS (HTTP Secure)
  → HTTP dengan enkripsi TLS/SSL.

Idempotent
  → Operasi yang menghasilkan efek sama meskipun
    dilakukan berkali-kali.
  → GET, PUT, DELETE bersifat idempotent.
  → POST tidak idempotent.

JSON (JavaScript Object Notation)
  → Format pertukaran data berbasis teks yang ringan.
  → Paling umum digunakan sebagai body HTTP.

Method
  → Kata kerja HTTP yang mendefinisikan aksi request.
  → GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS.

Payload
  → Sinonim untuk body — data yang dibawa dalam request/response.

Protocol
  → Seperangkat aturan yang mendefinisikan format dan
    urutan pesan dalam komunikasi.

Request
  → Pesan yang dikirim client ke server.

Response
  → Pesan balasan server kepada client.

REST (Representational State Transfer)
  → Gaya arsitektur API yang menggunakan HTTP secara semantik.

Stateless
  → Setiap request berdiri sendiri tanpa bergantung pada
    request sebelumnya.

Status Code
  → Kode numerik 3-digit dalam response yang menunjukkan
    hasil pemrosesan request.

TCP (Transmission Control Protocol)
  → Protokol transport yang menjamin pengiriman data
    secara berurutan dan reliable.

TLS (Transport Layer Security)
  → Protokol enkripsi yang digunakan oleh HTTPS.

URL (Uniform Resource Locator)
  → Alamat lengkap sebuah resource di internet.
  → Format: scheme://host:port/path?query#fragment
```

---

## SEKSI 18 — CATATAN INSTRUKTUR

### 18.1 Panduan Pengajaran

```
UNTUK INSTRUKTUR:

DURASI YANG DISARANKAN:
├── Teori & Konsep (Seksi 03-07)    : 60 menit
├── Demo Live Coding (Seksi 09)     : 45 menit
├── Latihan Hands-on (Seksi 13)     : 45 menit
└── Quiz & Review (Seksi 14)        : 30 menit
                                      ─────────
                                      180 menit (3 jam)

URUTAN PENGAJARAN YANG DISARANKAN:
1. Mulai dengan analogi (restoran/surat) - 5 menit
2. Demo langsung di browser DevTools - 10 menit
   → Buka Network tab, akses website, tunjukkan request/response
3. Jelaskan komponen request dan response - 20 menit
4. HTTP Methods dengan contoh nyata - 20 menit
5. Status codes dengan skenario - 15 menit
6. Live coding simple HTTP server - 30 menit
7. Latihan curl bersama - 20 menit
8. Quiz dan diskusi - 20 menit

COMMON MISCONCEPTIONS YANG PERLU DILURUSKAN:
┌─────────────────────────────────────────────────────────┐
│ ✗ "POST lebih aman dari GET karena data tidak di URL"   │
│   → Keduanya tidak aman tanpa HTTPS                     │
│                                                         │
│ ✗ "404 berarti server mati"                             │
│   → Server hidup, hanya resource tidak ditemukan        │
│                                                         │
│ ✗ "PUT dan POST sama saja"                              │
│   → PUT idempotent, POST tidak                          │
│                                                         │
│ ✗ "HTTP/2 dan HTTP/3 tidak kompatibel dengan HTTP/1.1"  │
│   → Server modern mendukung semua versi                 │
└─────────────────────────────────────────────────────────┘

TIPS PENGAJARAN:
→ Gunakan browser DevTools (F12 → Network tab) untuk
  visualisasi real-time yang sangat efektif
→ httpbin.org adalah playground yang sangat berguna
→ Minta peserta menebak status code sebelum reveal jawaban
→ Hubungkan selalu ke pengalaman sehari-hari peserta
```

### 18.2 Diferensiasi Pembelajaran

```
UNTUK PESERTA YANG LEBIH CEPAT:
→ Eksplorasi HTTP/2 multiplexing
→ Implementasi HTTP server dengan routing lebih kompleks
→ Pelajari HTTP caching headers (ETag, Last-Modified)
→ Eksplorasi WebSocket upgrade dari HTTP

UNTUK PESERTA YANG MEMBUTUHKAN BANTUAN LEBIH:
→ Fokus pada 5 method utama saja (GET, POST, PUT, PATCH, DELETE)
→ Fokus pada status code yang paling umum (200, 201, 400, 401, 403, 404, 500)
→ Gunakan Postman (GUI) sebelum curl (CLI)
→ Berikan lebih banyak analogi kehidupan nyata
```

---

## SEKSI 19 — CHANGELOG & VERSI

```
CHANGELOG MODUL 02-01:
═══════════════════════════════════════════════════════════════

v1.0.0 (2024-01-15)
  → Initial release
  → Mencakup HTTP/1.1, HTTP/2, HTTP/3 overview
  → Ditambahkan exercise dengan httpbin.org
  → Ditambahkan Node.js practical example
  → Ditambahkan ASCII diagram untuk semua konsep utama

PLANNED UPDATES:
  → v1.1.0: Tambahkan contoh dengan Python (Flask/FastAPI)
  → v1.2.0: Tambahkan section tentang HTTP/3 & QUIC lebih detail
  → v1.3.0: Tambahkan video walkthrough links
  → v2.0.0: Tambahkan interactive exercises dengan auto-grading

COMPATIBILITY:
  → Node.js: v18.x LTS atau lebih baru
  → curl: v7.x atau lebih baru
  → Postman: v10.x atau lebih baru
  → Browser: Chrome/Firefox/Edge versi terbaru
```

---

## SEKSI 20 — NAVIGASI KURIKULUM

```
╔═════════════════════════════════════════════════════════════╗
║                  NAVIGASI KURIKULUM                        ║
║              backend-beginner | 01-Core-Foundations        ║
╠═════════════════════════════════════════════════════════════╣
║                                                             ║
║  ◄ SEBELUMNYA                                               ║
║    Bab 01 - Module 01: Pengenalan Backend Development       ║
║    Bab 01 - Module 02: Cara Kerja Internet & DNS            ║
║                                                             ║
║  ► SEKARANG                                                 ║
║  ★ Bab 02 - Module 01: Protokol HTTP & Request-Response    ║
║                                                             ║
║  ► SELANJUTNYA                                              ║
║    Bab 02 - Module 02: URL Structure & Query Parameters     ║
║    Bab 02 - Module 03: HTTP Headers Deep Dive               ║
║    Bab 02 - Module 04: HTTPS & TLS/SSL Basics               ║
║    Bab 03 - Module 01: Pengenalan Web Framework             ║
║                                                             ║
╠═════════════════════════════════════════════════════════════╣
║  PROGRESS TRACKER:                                          ║
║  ████████████████░░░░░░░░░░░░░░░░  Bab 02/10 (20%)         ║
╚═════════════════════════════════════════════════════════════╝

LEARNING PATH VISUALIZATION:
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  [Bab 01]──►[Bab 02]──►[Bab 03]──►[Bab 04]──►[Bab 05]    │
│  Internet   HTTP ★     Framework   Database    REST API     │
│  Basics     ←Anda      Basics      Basics      Design       │
│                                                             │
│  [Bab 06]──►[Bab 07]──►[Bab 08]──►[Bab 09]──►[Bab 10]    │
│  JSON &     Error       Auth &      Testing    Deployment   │
│  Validation Handling    Security    Basics     Basics       │
│                                                             │
└─────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════
  Modul ini adalah bagian dari kurikulum 'backend-beginner'
  Kategori: 01-Core-Foundations
  Total Modul dalam Kategori: 12 modul
  Estimasi Penyelesaian Kategori: 48 jam
═══════════════════════════════════════════════════════════════
```

---

*Dokumen ini dibuat sesuai standar GEMINI.md untuk kurikulum backend-beginner.*
*Versi: 1.0.0 | Kategori: 01-Core-Foundations | Bab: 02 | Modul: 01*