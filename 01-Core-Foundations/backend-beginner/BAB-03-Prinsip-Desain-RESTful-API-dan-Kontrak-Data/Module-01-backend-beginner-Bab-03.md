# Bab 03 – Module 01: HTTP & Web Fundamentals

## Kurikulum: Backend Beginner | Kategori: 01-Core-Foundations

---

# SECTION 01 — LEARNING OBJECTIVE

## Tujuan Pembelajaran

Setelah menyelesaikan modul ini, peserta didik mampu:

1. **Menjelaskan** cara kerja protokol HTTP/HTTPS secara konseptual dan teknis
2. **Mengidentifikasi** komponen-komponen request dan response HTTP beserta fungsinya
3. **Membedakan** HTTP methods (GET, POST, PUT, PATCH, DELETE) dan kapan menggunakannya
4. **Menginterpretasikan** HTTP status codes dan maknanya dalam konteks aplikasi backend
5. **Memahami** konsep stateless, headers, cookies, dan session dalam komunikasi web
6. **Mengimplementasikan** server HTTP sederhana menggunakan Node.js native
7. **Menerapkan** best practices keamanan dasar pada komunikasi HTTP

### Peta Kompetensi

```
LEVEL BLOOM          KOMPETENSI TARGET
─────────────────────────────────────────────────────
Remember     →  Hafal HTTP methods & status codes umum
Understand   →  Jelaskan request-response lifecycle
Apply        →  Buat server HTTP sederhana
Analyze      →  Bedakan kapan pakai GET vs POST
Evaluate     →  Pilih status code yang tepat per kasus
Create       →  Rancang endpoint API sederhana
```

### Prasyarat Modul

| Prasyarat | Level |
|-----------|-------|
| Bab 01 – Pengenalan Backend Development | Wajib |
| Bab 02 – Dasar-Dasar JavaScript/Node.js | Wajib |
| Pemahaman dasar terminal/CLI | Wajib |
| Konsep client-server (konseptual) | Dianjurkan |

---

# SECTION 02 — CONCEPT OVERVIEW

## Gambaran Konsep: HTTP sebagai Bahasa Web

**HTTP (HyperText Transfer Protocol)** adalah protokol komunikasi yang menjadi fondasi pertukaran data di World Wide Web. Setiap kali Anda membuka browser, mengirim form, atau aplikasi mobile Anda mengambil data dari server — HTTP adalah "bahasa" yang digunakan kedua pihak untuk berkomunikasi.

### Definisi Inti

```
HTTP = Aturan tata bahasa komunikasi antara CLIENT dan SERVER
       di atas jaringan TCP/IP
```

### Karakteristik Fundamental HTTP

| Karakteristik | Penjelasan |
|--------------|------------|
| **Text-based** | Pesan HTTP dapat dibaca manusia (human-readable) |
| **Stateless** | Setiap request berdiri sendiri, server tidak "mengingat" request sebelumnya |
| **Request-Response** | Selalu ada pasangan: client meminta, server menjawab |
| **Application Layer** | Beroperasi di Layer 7 model OSI |
| **Platform-agnostic** | Bisa digunakan oleh browser, mobile app, IoT device, dll |

### Evolusi HTTP

```
HTTP/0.9 (1991)  →  Hanya GET, hanya HTML
HTTP/1.0 (1996)  →  Headers, status codes, methods tambahan
HTTP/1.1 (1997)  →  Persistent connection, chunked transfer (STANDAR LAMA)
HTTP/2  (2015)   →  Multiplexing, header compression, binary protocol
HTTP/3  (2022)   →  QUIC protocol, UDP-based, lebih cepat
```

> **Fokus Modul Ini:** HTTP/1.1 sebagai fondasi — dipahami dulu sebelum HTTP/2 dan HTTP/3.

---

# SECTION 03 — WHY IT MATTERS

## Mengapa HTTP Wajib Dikuasai Backend Developer?

### Argumen Utama

**HTTP adalah kontrak kerja antara frontend dan backend.** Tanpa memahami HTTP secara mendalam, seorang backend developer tidak bisa:

- Merancang API yang benar dan konsisten
- Men-debug masalah komunikasi client-server
- Mengimplementasikan autentikasi dan keamanan
- Mengoptimalkan performa aplikasi web
- Memahami error yang dilaporkan pengguna

### Analogi Dunia Nyata

```
HTTP ≈ Sistem Surat Resmi Kantor

┌─────────────────────────────────────────────────────┐
│  CLIENT (Pengirim Surat)                            │
│  ┌─────────────────────────────────────────────┐   │
│  │ Kepada: api.toko.com                        │   │
│  │ Perihal: Daftar Produk (GET /products)      │   │
│  │ Lampiran: Token Autentikasi                 │   │
│  └─────────────────────────────────────────────┘   │
│                        │                            │
│                        ▼ (Internet)                 │
│  SERVER (Penerima & Pembalas Surat)                 │
│  ┌─────────────────────────────────────────────┐   │
│  │ Status: 200 OK (Berhasil diproses)          │   │
│  │ Isi: [{"id":1,"nama":"Laptop",...}]         │   │
│  └─────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

### Dampak Nyata di Industri

```
MASALAH UMUM AKIBAT KURANG PAHAM HTTP:
─────────────────────────────────────────────────────
❌  API mengembalikan 200 OK meski data tidak ditemukan
❌  Menggunakan GET untuk operasi yang mengubah data
❌  Tidak mengatur cache headers → performa buruk
❌  CORS error karena salah konfigurasi headers
❌  Session tidak aman karena salah implementasi cookies
❌  Debugging lama karena tidak bisa baca HTTP traffic
```

### Relevansi Karir

Pemahaman HTTP yang solid adalah **syarat minimum** untuk posisi:
- Junior Backend Developer
- API Developer
- Full-Stack Developer
- DevOps Engineer (untuk konfigurasi server/proxy)
- Security Engineer (untuk analisis traffic)

---

# SECTION 04 — WHAT IS HTTP

## Apa Itu HTTP: Definisi Teknis Lengkap

### Definisi Formal

**HTTP (HyperText Transfer Protocol)** adalah protokol komunikasi lapisan aplikasi (application-layer protocol) berbasis teks yang mendefinisikan format dan urutan pesan yang dikirimkan antara client dan server dalam jaringan komputer, serta tindakan yang harus diambil oleh server dan client sebagai respons terhadap berbagai perintah.

### Komponen Ekosistem HTTP

```
┌─────────────────────────────────────────────────────────────┐
│                    EKOSISTEM HTTP                           │
│                                                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐             │
│  │  CLIENT  │    │ NETWORK  │    │  SERVER  │             │
│  │          │    │          │    │          │             │
│  │ Browser  │◄──►│ Internet │◄──►│ Node.js  │             │
│  │ Mobile   │    │ TCP/IP   │    │ Nginx    │             │
│  │ cURL     │    │ DNS      │    │ Apache   │             │
│  │ Postman  │    │ TLS/SSL  │    │ Express  │             │
│  └──────────┘    └──────────┘    └──────────┘             │
│                                                             │
│  Protokol Pendukung:                                        │
│  • DNS  → Resolusi nama domain ke IP address               │
│  • TCP  → Transport layer, jaminan pengiriman data         │
│  • TLS  → Enkripsi (HTTP + TLS = HTTPS)                   │
└─────────────────────────────────────────────────────────────┘
```

### Anatomi URL (Uniform Resource Locator)

URL adalah "alamat" yang digunakan HTTP untuk menemukan resource:

```
https://api.toko.com:443/products/laptop?sort=harga&limit=10#spesifikasi
│       │            │   │               │                   │
│       │            │   │               │                   └─ Fragment
│       │            │   │               └─ Query String
│       │            │   └─ Path
│       │            └─ Port
│       └─ Host (Domain)
└─ Scheme (Protocol)
```

| Komponen | Contoh | Keterangan |
|----------|--------|------------|
| Scheme | `https://` | Protokol yang digunakan |
| Host | `api.toko.com` | Domain atau IP address server |
| Port | `:443` | Port jaringan (opsional, default: 80/443) |
| Path | `/products/laptop` | Lokasi resource di server |
| Query String | `?sort=harga&limit=10` | Parameter tambahan |
| Fragment | `#spesifikasi` | Anchor di halaman (tidak dikirim ke server) |

### HTTP vs HTTPS

```
HTTP   = HyperText Transfer Protocol
HTTPS  = HyperText Transfer Protocol SECURE

Perbedaan:
┌────────────────┬──────────────────┬──────────────────────┐
│ Aspek          │ HTTP             │ HTTPS                │
├────────────────┼──────────────────┼──────────────────────┤
│ Port Default   │ 80               │ 443                  │
│ Enkripsi       │ Tidak ada        │ TLS/SSL              │
│ Keamanan       │ Rentan disadap   │ Terenkripsi          │
│ Sertifikat     │ Tidak perlu      │ Wajib (SSL Cert)     │
│ Performa       │ Sedikit lebih    │ Overhead enkripsi    │
│                │ cepat (teori)    │ (minimal di HTTP/2)  │
│ Penggunaan     │ Development      │ Production WAJIB     │
└────────────────┴──────────────────┴──────────────────────┘
```

---

# SECTION 05 — HOW HTTP WORKS

## Cara Kerja HTTP: Request-Response Lifecycle

### Alur Lengkap dari Browser ke Server

```
STEP 1: User mengetik URL di browser
        https://api.toko.com/products

STEP 2: DNS Resolution
        api.toko.com → 203.0.113.42

STEP 3: TCP Handshake (3-way)
        Client → SYN      → Server
        Client ← SYN-ACK  ← Server
        Client → ACK      → Server

STEP 4: TLS Handshake (jika HTTPS)
        Negosiasi cipher, pertukaran sertifikat,
        pembentukan session key

STEP 5: HTTP Request dikirim
        GET /products HTTP/1.1
        Host: api.toko.com
        ...

STEP 6: Server memproses request
        Routing → Controller → Database → Response

STEP 7: HTTP Response dikirim
        HTTP/1.1 200 OK
        Content-Type: application/json
        ...

STEP 8: Browser/Client memproses response
        Render HTML / Parse JSON / dll

STEP 9: Koneksi ditutup atau dipertahankan
        (Connection: keep-alive)
```

### Diagram Sequence Lengkap

```
CLIENT                    DNS SERVER              WEB SERVER
  │                           │                       │
  │──── DNS Query ────────────►│                       │
  │◄─── IP Address ───────────│                       │
  │                           │                       │
  │──── TCP SYN ──────────────────────────────────────►│
  │◄─── TCP SYN-ACK ──────────────────────────────────│
  │──── TCP ACK ──────────────────────────────────────►│
  │                           │                       │
  │──── HTTP Request ─────────────────────────────────►│
  │     GET /products HTTP/1.1│                       │
  │     Host: api.toko.com    │                       │
  │                           │                       │
  │                           │         ┌─────────────┤
  │                           │         │ Process     │
  │                           │         │ Request     │
  │                           │         └─────────────┤
  │                           │                       │
  │◄─── HTTP Response ────────────────────────────────│
  │     HTTP/1.1 200 OK       │                       │
  │     Content-Type: json    │                       │
  │     {"products": [...]}   │                       │
  │                           │                       │
```

### Struktur HTTP Request

```
┌─────────────────────────────────────────────────────────┐
│                    HTTP REQUEST                         │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │ REQUEST LINE                                    │   │
│  │ GET /products?limit=10 HTTP/1.1                 │   │
│  │ ─── ──────────────────── ────────               │   │
│  │  ↑         ↑                ↑                   │   │
│  │ Method    Path           Version                │   │
│  └─────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────┐   │
│  │ HEADERS                                         │   │
│  │ Host: api.toko.com                              │   │
│  │ Accept: application/json                        │   │
│  │ Authorization: Bearer eyJhbGci...               │   │
│  │ Content-Type: application/json                  │   │
│  │ User-Agent: Mozilla/5.0...                      │   │
│  └─────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────┐   │
│  │ BLANK LINE (pemisah headers dan body)           │   │
│  └─────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────┐   │
│  │ BODY (opsional, biasanya pada POST/PUT/PATCH)   │   │
│  │ {                                               │   │
│  │   "nama": "Laptop Gaming",                      │   │
│  │   "harga": 15000000                             │   │
│  │ }                                               │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### Struktur HTTP Response

```
┌─────────────────────────────────────────────────────────┐
│                    HTTP RESPONSE                        │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │ STATUS LINE                                     │   │
│  │ HTTP/1.1 200 OK                                 │   │
│  │ ──────── ─── ──                                 │   │
│  │    ↑      ↑   ↑                                 │   │
│  │ Version Code Reason Phrase                      │   │
│  └─────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────┐   │
│  │ HEADERS                                         │   │
│  │ Content-Type: application/json; charset=utf-8   │   │
│  │ Content-Length: 1234                            │   │
│  │ Cache-Control: max-age=3600                     │   │
│  │ X-Request-ID: abc-123-def                       │   │
│  └─────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────┐   │
│  │ BLANK LINE                                      │   │
│  └─────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────┐   │
│  │ BODY                                            │   │
│  │ {                                               │   │
│  │   "status": "success",                          │   │
│  │   "data": [...]                                 │   │
│  │ }                                               │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

---

# SECTION 06 — ASCII DIAGRAM: HTTP ECOSYSTEM

## Diagram Ekosistem HTTP Lengkap

```
╔═══════════════════════════════════════════════════════════════════╗
║                    EKOSISTEM HTTP LENGKAP                        ║
╠═══════════════════════════════════════════════════════════════════╣
║                                                                   ║
║  ┌─────────────────┐         ┌─────────────────────────────────┐ ║
║  │   CLIENT SIDE   │         │         SERVER SIDE             │ ║
║  │                 │         │                                 │ ║
║  │  ┌───────────┐  │         │  ┌──────────┐  ┌────────────┐  │ ║
║  │  │  Browser  │  │         │  │  Nginx   │  │  Node.js   │  │ ║
║  │  │  Firefox  │  │         │  │ (Reverse │  │  Express   │  │ ║
║  │  │  Chrome   │  │         │  │  Proxy)  │  │  Fastify   │  │ ║
║  │  └─────┬─────┘  │         │  └────┬─────┘  └─────┬──────┘  │ ║
║  │        │        │         │       │               │         │ ║
║  │  ┌─────▼─────┐  │         │  ┌────▼───────────────▼──────┐  │ ║
║  │  │  Mobile   │  │         │  │      Application Layer    │  │ ║
║  │  │   App     │  │         │  │  Router → Controller →    │  │ ║
║  │  └─────┬─────┘  │         │  │  Service → Repository     │  │ ║
║  │        │        │         │  └───────────────┬───────────┘  │ ║
║  │  ┌─────▼─────┐  │         │                  │              │ ║
║  │  │   cURL/   │  │         │  ┌───────────────▼───────────┐  │ ║
║  │  │  Postman  │  │         │  │         Database           │  │ ║
║  │  └─────┬─────┘  │         │  │  PostgreSQL / MongoDB      │  │ ║
║  └─────────┼───────┘         │  │  Redis (Cache)             │  │ ║
║            │                 │  └───────────────────────────┘  │ ║
║            │                 └─────────────────────────────────┘ ║
║            │                                   ▲                 ║
║            │         ┌─────────────────────────┘                 ║
║            │         │                                           ║
║            ▼         │                                           ║
║  ┌─────────────────────────────────────────────────────────────┐ ║
║  │                      INTERNET                               │ ║
║  │                                                             │ ║
║  │  HTTP Request  ──────────────────────────────────────────►  │ ║
║  │  HTTP Response ◄──────────────────────────────────────────  │ ║
║  │                                                             │ ║
║  │  Layer Stack:                                               │ ║
║  │  [HTTP/HTTPS] → [TLS] → [TCP] → [IP] → [Ethernet/WiFi]    │ ║
║  └─────────────────────────────────────────────────────────────┘ ║
║                                                                   ║
║  PROTOKOL PENDUKUNG:                                              ║
║  ┌──────────┬──────────────────────────────────────────────────┐ ║
║  │ DNS      │ Translasi domain → IP address                    │ ║
║  │ TCP      │ Reliable transport, connection-oriented          │ ║
║  │ TLS/SSL  │ Enkripsi end-to-end (HTTPS)                     │ ║
║  │ CDN      │ Distribusi konten statis secara global           │ ║
║  └──────────┴──────────────────────────────────────────────────┘ ║
╚═══════════════════════════════════════════════════════════════════╝
```

### Diagram HTTP Methods & CRUD Mapping

```
╔═══════════════════════════════════════════════════════════════╗
║              HTTP METHODS ↔ CRUD OPERATIONS                  ║
╠═══════════════════════════════════════════════════════════════╣
║                                                               ║
║  HTTP Method    CRUD      Contoh Endpoint    Idempoten?       ║
║  ───────────────────────────────────────────────────────────  ║
║  GET         →  Read    →  GET /products      ✅ Ya           ║
║  POST        →  Create  →  POST /products     ❌ Tidak        ║
║  PUT         →  Replace →  PUT /products/1    ✅ Ya           ║
║  PATCH       →  Update  →  PATCH /products/1  ⚠️  Tergantung  ║
║  DELETE      →  Delete  →  DELETE /products/1 ✅ Ya           ║
║                                                               ║
║  Methods Lain:                                                ║
║  HEAD    → Seperti GET tapi tanpa body (cek metadata)        ║
║  OPTIONS → Tanya server: method apa yang didukung?           ║
║  CONNECT → Buat tunnel (dipakai proxy HTTPS)                 ║
║  TRACE   → Debug: echo request kembali ke client             ║
╚═══════════════════════════════════════════════════════════════╝
```

---

# SECTION 07 — SIMPLE EXAMPLE

## Contoh Sederhana: HTTP Request & Response Manual

### Contoh 1: Melihat HTTP Traffic dengan cURL

```bash
# Kirim HTTP GET request dan lihat semua detail
curl -v https://httpbin.org/get

# Output yang akan muncul:
# * Trying 54.91.118.50:443...
# * Connected to httpbin.org
# * SSL handshake...
# > GET /get HTTP/2
# > Host: httpbin.org
# > User-Agent: curl/7.88.1
# > Accept: */*
# >
# < HTTP/2 200
# < content-type: application/json
# < content-length: 256
# <
# {
#   "headers": {
#     "Accept": "*/*",
#     "Host": "httpbin.org",
#     "User-Agent": "curl/7.88.1"
#   },
#   "url": "https://httpbin.org/get"
# }
```

### Contoh 2: HTTP Request Mentah (Raw)

Inilah yang sebenarnya dikirim melalui jaringan:

```
GET /products HTTP/1.1
Host: api.toko.com
Accept: application/json
Accept-Language: id-ID,id;q=0.9
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)
Connection: keep-alive

```
*(baris kosong menandai akhir headers)*

### Contoh 3: HTTP Response Mentah

```
HTTP/1.1 200 OK
Date: Mon, 15 Jan 2024 08:30:00 GMT
Content-Type: application/json; charset=utf-8
Content-Length: 89
Connection: keep-alive
Cache-Control: public, max-age=3600

{"status":"success","data":[{"id":1,"nama":"Laptop","harga":15000000}]}
```

### Contoh 4: Server HTTP Paling Sederhana (Node.js)

```javascript
// file: server-sederhana.js
// Jalankan: node server-sederhana.js
// Test: buka browser ke http://localhost:3000

const http = require('http');

// Buat server HTTP
const server = http.createServer((request, response) => {
  // 'request' = HTTP Request dari client
  // 'response' = HTTP Response yang akan kita kirim

  // Tulis status line dan headers
  response.writeHead(200, {
    'Content-Type': 'text/plain',
  });

  // Tulis body dan akhiri response
  response.end('Halo, ini server HTTP pertama saya!\n');
});

// Server mendengarkan di port 3000
server.listen(3000, () => {
  console.log('Server berjalan di http://localhost:3000');
});
```

**Output saat diakses:**
```
Halo, ini server HTTP pertama saya!
```

**HTTP Response yang dikirim server:**
```
HTTP/1.1 200 OK
Content-Type: text/plain
Date: Mon, 15 Jan 2024 08:30:00 GMT
Connection: keep-alive
Transfer-Encoding: chunked

Halo, ini server HTTP pertama saya!
```

---

# SECTION 08 — PRACTICAL EXAMPLE

## Contoh Praktis: Server HTTP dengan Routing Lengkap

### Skenario

Membangun server HTTP untuk **Toko Online Sederhana** yang melayani:
- Daftar produk
- Detail produk
- Tambah produk baru
- Hapus produk

### Implementasi Lengkap

```javascript
// file: toko-server.js
// Jalankan: node toko-server.js

const http = require('http');

// ─── DATABASE SIMULASI ────────────────────────────────────────
let products = [
  { id: 1, nama: 'Laptop Gaming ASUS', harga: 15000000, stok: 10 },
  { id: 2, nama: 'Mouse Wireless Logitech', harga: 350000, stok: 50 },
  { id: 3, nama: 'Keyboard Mechanical', harga: 800000, stok: 25 },
];
let nextId = 4;

// ─── HELPER FUNCTIONS ─────────────────────────────────────────

/**
 * Kirim response JSON dengan status code tertentu
 */
function sendJSON(response, statusCode, data) {
  response.writeHead(statusCode, {
    'Content-Type': 'application/json; charset=utf-8',
    'X-Powered-By': 'Node.js HTTP Module',
  });
  response.end(JSON.stringify(data, null, 2));
}

/**
 * Parse request body (untuk POST/PUT/PATCH)
 * Mengembalikan Promise karena data datang dalam chunks
 */
function parseBody(request) {
  return new Promise((resolve, reject) => {
    let body = '';

    // Data datang dalam potongan-potongan (chunks)
    request.on('data', (chunk) => {
      body += chunk.toString();

      // Batasi ukuran body untuk keamanan (1MB)
      if (body.length > 1e6) {
        reject(new Error('Request body terlalu besar'));
        request.destroy();
      }
    });

    // Semua data sudah diterima
    request.on('end', () => {
      try {
        resolve(body ? JSON.parse(body) : {});
      } catch (error) {
        reject(new Error('Format JSON tidak valid'));
      }
    });

    request.on('error', reject);
  });
}

// ─── ROUTER ───────────────────────────────────────────────────

/**
 * Router sederhana berbasis method dan path
 */
async function router(request, response) {
  const { method, url } = request;

  // Parse URL untuk mendapatkan path dan query string
  const parsedUrl = new URL(url, `http://${request.headers.host}`);
  const pathname = parsedUrl.pathname;

  console.log(`[${new Date().toISOString()}] ${method} ${pathname}`);

  // ── GET /products ──────────────────────────────────────────
  if (method === 'GET' && pathname === '/products') {
    // Ambil query parameter untuk filtering
    const minHarga = parsedUrl.searchParams.get('min_harga');
    const maxHarga = parsedUrl.searchParams.get('max_harga');

    let hasil = [...products];

    if (minHarga) {
      hasil = hasil.filter((p) => p.harga >= parseInt(minHarga));
    }
    if (maxHarga) {
      hasil = hasil.filter((p) => p.harga <= parseInt(maxHarga));
    }

    return sendJSON(response, 200, {
      status: 'success',
      total: hasil.length,
      data: hasil,
    });
  }

  // ── GET /products/:id ──────────────────────────────────────
  const matchDetail = pathname.match(/^\/products\/(\d+)$/);
  if (method === 'GET' && matchDetail) {
    const id = parseInt(matchDetail[1]);
    const product = products.find((p) => p.id === id);

    if (!product) {
      return sendJSON(response, 404, {
        status: 'error',
        message: `Produk dengan ID ${id} tidak ditemukan`,
      });
    }

    return sendJSON(response, 200, {
      status: 'success',
      data: product,
    });
  }

  // ── POST /products ─────────────────────────────────────────
  if (method === 'POST' && pathname === '/products') {
    let body;
    try {
      body = await parseBody(request);
    } catch (error) {
      return sendJSON(response, 400, {
        status: 'error',
        message: error.message,
      });
    }

    // Validasi input
    const { nama, harga, stok } = body;
    const errors = [];

    if (!nama || typeof nama !== 'string' || nama.trim() === '') {
      errors.push('Field "nama" wajib diisi dan harus berupa string');
    }
    if (!harga || typeof harga !== 'number' || harga <= 0) {
      errors.push('Field "harga" wajib diisi dan harus berupa angka positif');
    }
    if (stok !== undefined && (typeof stok !== 'number' || stok < 0)) {
      errors.push('Field "stok" harus berupa angka non-negatif');
    }

    if (errors.length > 0) {
      return sendJSON(response, 422, {
        status: 'error',
        message: 'Validasi gagal',
        errors,
      });
    }

    // Buat produk baru
    const productBaru = {
      id: nextId++,
      nama: nama.trim(),
      harga,
      stok: stok ?? 0,
    };

    products.push(productBaru);

    // 201 Created = resource baru berhasil dibuat
    return sendJSON(response, 201, {
      status: 'success',
      message: 'Produk berhasil ditambahkan',
      data: productBaru,
    });
  }

  // ── DELETE /products/:id ───────────────────────────────────
  const matchDelete = pathname.match(/^\/products\/(\d+)$/);
  if (method === 'DELETE' && matchDelete) {
    const id = parseInt(matchDelete[1]);
    const index = products.findIndex((p) => p.id === id);

    if (index === -1) {
      return sendJSON(response, 404, {
        status: 'error',
        message: `Produk dengan ID ${id} tidak ditemukan`,
      });
    }

    const deleted = products.splice(index, 1)[0];

    return sendJSON(response, 200, {
      status: 'success',
      message: `Produk "${deleted.nama}" berhasil dihapus`,
    });
  }

  // ── GET / (Health Check) ───────────────────────────────────
  if (method === 'GET' && pathname === '/') {
    return sendJSON(response, 200, {
      status: 'ok',
      message: 'Toko API berjalan normal',
      version: '1.0.0',
      timestamp: new Date().toISOString(),
    });
  }

  // ── 404 Not Found ──────────────────────────────────────────
  return sendJSON(response, 404, {
    status: 'error',
    message: `Endpoint ${method} ${pathname} tidak ditemukan`,
  });
}

// ─── SERVER ───────────────────────────────────────────────────

const server = http.createServer(async (request, response) => {
  try {
    await router(request, response);
  } catch (error) {
    console.error('Server Error:', error);
    sendJSON(response, 500, {
      status: 'error',
      message: 'Terjadi kesalahan internal server',
    });
  }
});

const PORT = process.env.PORT || 3000;

server.listen(PORT, () => {
  console.log(`
╔════════════════════════════════════════╗
║   🛒 Toko API Server                  ║
║   Berjalan di: http://localhost:${PORT}  ║
╠════════════════════════════════════════╣
║   Endpoint yang tersedia:             ║
║   GET    /                            ║
║   GET    /products                    ║
║   GET    /products?min_harga=500000   ║
║   GET    /products/:id                ║
║   POST   /products                    ║
║   DELETE /products/:id                ║
╚════════════════════════════════════════╝
  `);
});
```

### Testing dengan cURL

```bash
# 1. Health check
curl http://localhost:3000/

# 2. Ambil semua produk
curl http://localhost:3000/products

# 3. Filter produk berdasarkan harga
curl "http://localhost:3000/products?min_harga=500000&max_harga=1000000"

# 4. Ambil produk by ID
curl http://localhost:3000/products/1

# 5. Tambah produk baru
curl -X POST http://localhost:3000/products \
  -H "Content-Type: application/json" \
  -d '{"nama":"Headset Gaming","harga":750000,"stok":30}'

# 6. Hapus produk
curl -X DELETE http://localhost:3000/products/1

# 7. Test 404
curl http://localhost:3000/kategori
```

### Output Testing

```bash
# GET /products
{
  "status": "success",
  "total": 3,
  "data": [
    { "id": 1, "nama": "Laptop Gaming ASUS", "harga": 15000000, "stok": 10 },
    { "id": 2, "nama": "Mouse Wireless Logitech", "harga": 350000, "stok": 50 },
    { "id": 3, "nama": "Keyboard Mechanical", "harga": 800000, "stok": 25 }
  ]
}

# POST /products (sukses)
{
  "status": "success",
  "message": "Produk berhasil ditambahkan",
  "data": { "id": 4, "nama": "Headset Gaming", "harga": 750000, "stok": 30 }
}

# POST /products (validasi gagal)
{
  "status": "error",
  "message": "Validasi gagal",
  "errors": ["Field \"harga\" wajib diisi dan harus berupa angka positif"]
}
```

---

# SECTION 09 — HTTP STATUS CODES

## HTTP Status Codes: Panduan Lengkap

Status code adalah kode 3 digit yang dikirim server untuk memberitahu client hasil dari request-nya.

### Kategori Status Code

```
1xx → Informational  (Proses sedang berlangsung)
2xx → Success        (Request berhasil)
3xx → Redirection    (Client perlu melakukan tindakan lain)
4xx → Client Error   (Kesalahan dari sisi client)
5xx → Server Error   (Kesalahan dari sisi server)
```

### Status Codes yang Wajib Dikuasai

```
╔═══════════════════════════════════════════════════════════════════╗
║                    HTTP STATUS CODES                             ║
╠══════════╦════════════════════════╦══════════════════════════════╣
║  CODE    ║  NAMA                  ║  KAPAN DIGUNAKAN             ║
╠══════════╬════════════════════════╬══════════════════════════════╣
║  200     ║  OK                    ║  Request berhasil (GET/PUT)  ║
║  201     ║  Created               ║  Resource baru dibuat (POST) ║
║  204     ║  No Content            ║  Sukses tapi tanpa body      ║
╠══════════╬════════════════════════╬══════════════════════════════╣
║  301     ║  Moved Permanently     ║  URL berubah permanen        ║
║  302     ║  Found                 ║  Redirect sementara          ║
║  304     ║  Not Modified          ║  Cache masih valid           ║
╠══════════╬════════════════════════╬══════════════════════════════╣
║  400     ║  Bad Request           ║  Request tidak valid/rusak   ║
║  401     ║  Unauthorized          ║  Belum login/autentikasi     ║
║  403     ║  Forbidden             ║  Login tapi tidak punya akses║
║  404     ║  Not Found             ║  Resource tidak ditemukan    ║
║  405     ║  Method Not Allowed    ║  Method tidak didukung       ║
║  409     ║  Conflict              ║  Konflik data (email duplikat║
║  422     ║  Unprocessable Entity  ║  Validasi gagal              ║
║  429     ║  Too Many Requests     ║  Rate limit terlampaui       ║
╠══════════╬════════════════════════╬══════════════════════════════╣
║  500     ║  Internal Server Error ║  Error tak terduga di server ║
║  502     ║  Bad Gateway           ║  Upstream server error       ║
║  503     ║  Service Unavailable   ║  Server sedang maintenance   ║
║  504     ║  Gateway Timeout       ║  Upstream server timeout     ║
╚══════════╩════════════════════════╩══════════════════════════════╝
```

### Decision Tree: Memilih Status Code

```
Request masuk ke server
        │
        ▼
Apakah request valid secara sintaks?
   │              │
  TIDAK           YA
   │              │
   ▼              ▼
  400          Apakah user terautentikasi?
Bad Request       │              │
               TIDAK             YA
                │                │
                ▼                ▼
               401           Apakah user punya izin?
           Unauthorized          │              │
                               TIDAK            YA
                                │               │
                                ▼               ▼
                               403          Apakah resource ada?
                           Forbidden            │              │
                                             TIDAK             YA
                                              │                │
                                              ▼                ▼
                                             404          Proses request
                                          Not Found            │
                                                               ▼
                                                        Apakah berhasil?
                                                            │       │
                                                          YA       TIDAK
                                                           │         │
                                                           ▼         ▼
                                                    2xx Success   5xx Error
```

### Kesalahan Umum Status Code

```javascript
// ❌ SALAH: Mengembalikan 200 meski data tidak ditemukan
app.get('/products/:id', (req, res) => {
  const product = findProduct(req.params.id);
  res.status(200).json({ data: product }); // product bisa null!
});

// ✅ BENAR: Status code sesuai kondisi
app.get('/products/:id', (req, res) => {
  const product = findProduct(req.params.id);

  if (!product) {
    return res.status(404).json({
      status: 'error',
      message: 'Produk tidak ditemukan',
    });
  }

  res.status(200).json({
    status: 'success',
    data: product,
  });
});
```

---

# SECTION 10 — HTTP HEADERS

## HTTP Headers: Metadata Komunikasi

Headers adalah pasangan key-value yang membawa informasi tambahan tentang request atau response.

### Kategori Headers

```
┌─────────────────────────────────────────────────────────────┐
│                    JENIS HTTP HEADERS                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  General Headers  → Berlaku untuk request DAN response     │
│  ─────────────────────────────────────────────────────────  │
│  Date: Mon, 15 Jan 2024 08:30:00 GMT                       │
│  Connection: keep-alive                                     │
│  Cache-Control: no-cache                                    │
│                                                             │
│  Request Headers  → Hanya ada di HTTP Request              │
│  ─────────────────────────────────────────────────────────  │
│  Host: api.toko.com                                         │
│  Accept: application/json                                   │
│  Authorization: Bearer <token>                              │
│  User-Agent: Mozilla/5.0...                                 │
│  Content-Type: application/json                             │
│  Accept-Language: id-ID                                     │
│  Accept-Encoding: gzip, deflate, br                         │
│                                                             │
│  Response Headers → Hanya ada di HTTP Response             │
│  ─────────────────────────────────────────────────────────  │
│  Content-Type: application/json; charset=utf-8             │
│  Content-Length: 1234                                       │
│  Set-Cookie: session=abc123; HttpOnly; Secure               │
│  Location: /products/4  (untuk redirect)                   │
│  WWW-Authenticate: Bearer realm="api"                       │
│                                                             │
│  Custom Headers   → Didefinisikan aplikasi (prefix X-)     │
│  ─────────────────────────────────────────────────────────  │
│  X-Request-ID: uuid-abc-123                                 │
│  X-Rate-Limit-Remaining: 95                                 │
│  X-API-Version: 2.1.0                                       │
└─────────────────────────────────────────────────────────────┘
```

### Headers Penting untuk Backend Developer

```javascript
// ─── CONTENT NEGOTIATION ──────────────────────────────────────

// Client memberitahu server format apa yang bisa diterima
// Request Header:
// Accept: application/json, text/html;q=0.9, */*;q=0.8

// Server memberitahu client format apa yang dikirim
// Response Header:
// Content-Type: application/json; charset=utf-8

// ─── AUTENTIKASI ──────────────────────────────────────────────

// Basic Auth (username:password di-encode Base64)
// Authorization: Basic dXNlcjpwYXNzd29yZA==

// Bearer Token (JWT)
// Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

// API Key
// X-API-Key: sk-prod-abc123def456

// ─── CACHING ──────────────────────────────────────────────────

// Server memberitahu client cara cache response
// Cache-Control: public, max-age=3600      → Cache 1 jam
// Cache-Control: private, no-cache         → Jangan cache
// Cache-Control: no-store                  → Jangan simpan sama sekali
// ETag: "abc123"                           → Versi resource
// Last-Modified: Mon, 15 Jan 2024 08:00:00 GMT

// ─── CORS (Cross-Origin Resource Sharing) ─────────────────────

// Server mengizinkan request dari domain lain
// Access-Control-Allow-Origin: https://toko.com
// Access-Control-Allow-Methods: GET, POST, PUT, DELETE
// Access-Control-Allow-Headers: Content-Type, Authorization
// Access-Control-Max-Age: 86400

// ─── KEAMANAN ─────────────────────────────────────────────────

// Mencegah clickjacking
// X-Frame-Options: DENY

// Mencegah MIME sniffing
// X-Content-Type-Options: nosniff

// Paksa HTTPS
// Strict-Transport-Security: max-age=31536000; includeSubDomains

// Content Security Policy
// Content-Security-Policy: default-src 'self'
```

### Implementasi Headers di Node.js

```javascript
const http = require('http');

const server = http.createServer((req, res) => {
  // Baca request headers
  const contentType = req.headers['content-type'];
  const authorization = req.headers['authorization'];
  const userAgent = req.headers['user-agent'];

  console.log('Content-Type:', contentType);
  console.log('Authorization:', authorization);
  console.log('User-Agent:', userAgent);

  // Set response headers
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('X-Request-ID', generateRequestId());
  res.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate');

  // Security headers
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('X-Frame-Options', 'DENY');

  res.writeHead(200);
  res.end(JSON.stringify({ status: 'ok' }));
});

function generateRequestId() {
  return Math.random().toString(36).substring(2, 15);
}
```

---

# SECTION 11 — STATELESS & STATE MANAGEMENT

## Stateless HTTP dan Manajemen State

### Konsep Stateless

HTTP adalah protokol **stateless** — setiap request diperlakukan sebagai transaksi independen. Server tidak menyimpan informasi tentang request sebelumnya.

```
ILUSTRASI STATELESS:

Request 1:  "Saya ingin login"
Server:     "OK, login berhasil" (lalu melupakan segalanya)

Request 2:  "Saya ingin lihat profil saya"
Server:     "Siapa kamu? Saya tidak kenal kamu"
```

### Mengapa Stateless?

```
KEUNTUNGAN STATELESS:
✅ Skalabilitas tinggi (setiap server bisa handle request apapun)
✅ Lebih mudah di-debug (setiap request self-contained)
✅ Fault tolerance (jika satu server mati, request bisa ke server lain)
✅ Caching lebih mudah

KERUGIAN STATELESS:
❌ Harus mengirim informasi identitas di setiap request
❌ Overhead data lebih besar per request
❌ Implementasi "session" memerlukan mekanisme tambahan
```

### Solusi Manajemen State

```
┌─────────────────────────────────────────────────────────────┐
│              SOLUSI MANAJEMEN STATE DI HTTP                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. COOKIES                                                 │
│  ─────────────────────────────────────────────────────────  │
│  Server → Set-Cookie: session_id=abc123; HttpOnly; Secure   │
│  Client → Cookie: session_id=abc123  (dikirim otomatis)     │
│  Cocok untuk: Web browser, session management               │
│                                                             │
│  2. JWT (JSON Web Token)                                    │
│  ─────────────────────────────────────────────────────────  │
│  Server → Token berisi data user (terenkripsi/signed)       │
│  Client → Authorization: Bearer <jwt_token>                 │
│  Cocok untuk: API, mobile app, microservices                │
│                                                             │
│  3. SESSION SERVER-SIDE                                     │
│  ─────────────────────────────────────────────────────────  │
│  Server menyimpan state di database/Redis                   │
│  Client hanya menyimpan session ID                          │
│  Cocok untuk: Aplikasi dengan data session besar            │
│                                                             │
│  4. URL PARAMETERS / QUERY STRING                           │
│  ─────────────────────────────────────────────────────────  │
│  State disimpan di URL: /checkout?step=2&cart=abc           │
│  Cocok untuk: Wizard/multi-step form, shareable state       │
└─────────────────────────────────────────────────────────────┘
```

### Implementasi Cookie Sederhana

```javascript
const http = require('http');

// Simulasi penyimpanan session
const sessions = new Map();

function generateSessionId() {
  return Math.random().toString(36).substring(2) + Date.now().toString(36);
}

const server = http.createServer((req, res) => {
  const { url, method } = req;

  // ── POST /login ──────────────────────────────────────────
  if (method === 'POST' && url === '/login') {
    // Dalam praktik nyata: validasi username/password ke database
    const sessionId = generateSessionId();

    // Simpan data session di server
    sessions.set(sessionId, {
      userId: 1,
      username: 'budi',
      loginAt: new Date().toISOString(),
    });

    // Kirim session ID ke client via cookie
    res.setHeader('Set-Cookie', [
      `session_id=${sessionId}; HttpOnly; Path=/; Max-Age=3600`,
      // HttpOnly: tidak bisa diakses JavaScript (mencegah XSS)
      // Path=/: berlaku untuk semua path
      // Max-Age=3600: expired dalam 1 jam
    ]);

    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'success', message: 'Login berhasil' }));
    return;
  }

  // ── GET /profile ─────────────────────────────────────────
  if (method === 'GET' && url === '/profile') {
    // Baca cookie dari request
    const cookieHeader = req.headers.cookie || '';
    const cookies = Object.fromEntries(
      cookieHeader.split(';').map((c) => c.trim().split('='))
    );

    const sessionId = cookies['session_id'];

    if (!sessionId || !sessions.has(sessionId)) {
      res.writeHead(401, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'error', message: 'Silakan login terlebih dahulu' }));
      return;
    }

    const sessionData = sessions.get(sessionId);

    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      status: 'success',
      data: { username: sessionData.username, loginAt: sessionData.loginAt },
    }));
    return;
  }

  res.writeHead(404);
  res.end('Not Found');
});

server.listen(3000, () => console.log('Server berjalan di port 3000'));
```

---

# SECTION 12 — TRADE-OFFS & CONSIDERATIONS

## Trade-offs dalam Desain HTTP API

### 1. Stateless vs Stateful

```
┌─────────────────────────────────────────────────────────────┐
│              STATELESS vs STATEFUL                          │
├────────────────────┬────────────────────────────────────────┤
│ STATELESS (HTTP)   │ STATEFUL (WebSocket, gRPC streaming)   │
├────────────────────┼────────────────────────────────────────┤
│ ✅ Mudah di-scale  │ ✅ Lebih efisien untuk real-time       │
│ ✅ Fault tolerant  │ ✅ Tidak perlu kirim token tiap request │
│ ✅ Cache-friendly  │ ✅ Cocok untuk chat, game, live data    │
│ ❌ Overhead token  │ ❌ Sulit di-scale horizontal            │
│ ❌ Lebih banyak    │ ❌ Server harus ingat state tiap client │
│    data per request│ ❌ Jika server mati, state hilang       │
├────────────────────┴────────────────────────────────────────┤
│ REKOMENDASI: Gunakan HTTP stateless untuk API standar.      │
│ Gunakan WebSocket hanya untuk kebutuhan real-time.          │
└─────────────────────────────────────────────────────────────┘
```

### 2. Cookie vs JWT

```
┌─────────────────────────────────────────────────────────────┐
│                   COOKIE vs JWT                             │
├────────────────────────┬────────────────────────────────────┤
│ COOKIE + SESSION       │ JWT (JSON Web Token)               │
├────────────────────────┼────────────────────────────────────┤
│ ✅ Mudah di-revoke     │ ✅ Stateless, tidak perlu DB       │
│ ✅ Lebih aman dari XSS │ ✅ Cocok untuk microservices       │
│    (HttpOnly flag)     │ ✅ Cross-domain friendly            │
│ ✅ Browser handle      │ ❌ Sulit di-revoke sebelum expired  │
│    otomatis            │ ❌ Payload bisa besar               │
│ ❌ Tidak cocok untuk   │ ❌ Rentan jika secret key bocor     │
│    mobile/API          │ ❌ Harus handle refresh token       │
│ ❌ CSRF vulnerability  │                                    │
├────────────────────────┴────────────────────────────────────┤
│ REKOMENDASI:                                                │
│ • Web app tradisional → Cookie + Session                   │
│ • REST API / Mobile   → JWT dengan refresh token           │
└─────────────────────────────────────────────────────────────┘
```

### 3. HTTP Methods: Kapan Pakai Apa?

```
SKENARIO                          METHOD YANG TEPAT
─────────────────────────────────────────────────────────────
Ambil daftar produk               GET /products
Ambil detail produk               GET /products/:id
Buat produk baru                  POST /products
Ganti seluruh data produk         PUT /products/:id
Update sebagian data produk       PATCH /products/:id
Hapus produk                      DELETE /products/:id
Cek apakah resource ada           HEAD /products/:id
Tanya method yang didukung        OPTIONS /products

JANGAN:
❌ GET /deleteProduct?id=1        → Pakai DELETE /products/1
❌ POST /getProducts              → Pakai GET /products
❌ GET /createProduct?nama=Laptop → Pakai POST /products
```

### 4. Granularitas Status Code

```
PENDEKATAN MINIMAL (hanya 3 kode):
200 OK, 400 Bad Request, 500 Internal Server Error

Kelebihan: Sederhana, mudah diimplementasi
Kekurangan: Client tidak tahu detail masalah

PENDEKATAN SEMANTIK PENUH:
200, 201, 204, 400, 401, 403, 404, 409, 422, 429, 500, 503

Kelebihan: Client bisa handle error dengan tepat
Kekurangan: Lebih kompleks, perlu konsistensi tim

REKOMENDASI: Gunakan pendekatan semantik untuk API publik.
Minimal untuk API internal yang sudah terdokumentasi.
```

---

# SECTION 13 — BEST PRACTICES

## Best Practices HTTP untuk Backend Developer

### 1. Desain URL yang Bersih

```
✅ GOOD URL DESIGN:
GET    /products                    → Daftar produk
GET    /products/123                → Detail produk ID 123
POST   /products                    → Buat produk baru
PUT    /products/123                → Update penuh produk 123
PATCH  /products/123                → Update sebagian produk 123
DELETE /products/123                → Hapus produk 123
GET    /products/123/reviews        → Review untuk produk 123
POST   /products/123/reviews        → Tambah review ke produk 123

❌ BAD URL DESIGN:
GET    /getProducts                 → Verb di URL (gunakan method)
GET    /product                     → Tidak konsisten (singular)
POST   /products/create             → Redundan
GET    /products/delete/123         → DELETE method untuk hapus
GET    /api/v1/getAllProductsList    → Terlalu verbose
```

### 2. Konsistensi Response Format

```javascript
// ✅ Format response yang konsisten
const responseFormat = {
  // Sukses dengan data
  success: {
    status: 'success',
    data: { /* ... */ },
  },

  // Sukses dengan pesan
  successMessage: {
    status: 'success',
    message: 'Operasi berhasil',
  },

  // Sukses dengan paginasi
  successPaginated: {
    status: 'success',
    data: [ /* ... */ ],
    pagination: {
      page: 1,
      limit: 10,
      total: 100,
      totalPages: 10,
    },
  },

  // Error
  error: {
    status: 'error',
    message: 'Deskripsi error yang jelas',
    errors: [ /* detail validasi jika ada */ ],
  },
};
```

### 3. Security Headers Wajib

```javascript
function setSecurityHeaders(res) {
  // Mencegah MIME type sniffing
  res.setHeader('X-Content-Type-Options', 'nosniff');

  // Mencegah clickjacking
  res.setHeader('X-Frame-Options', 'DENY');

  // Paksa HTTPS (hanya untuk production)
  res.setHeader('Strict-Transport-Security', 'max-age=31536000; includeSubDomains');

  // Batasi informasi server
  res.removeHeader('X-Powered-By');

  // Content Security Policy
  res.setHeader('Content-Security-Policy', "default-src 'self'");

  // Referrer Policy
  res.setHeader('Referrer-Policy', 'strict-origin-when-cross-origin');
}
```

### 4. Error Handling yang Baik

```javascript
// ✅ Error handling yang informatif tapi aman
function handleError(error, res) {
  console.error('[ERROR]', {
    message: error.message,
    stack: error.stack,
    timestamp: new Date().toISOString(),
  });

  // Jangan expose detail error ke client di production!
  const isProduction = process.env.NODE_ENV === 'production';

  if (error.name === 'ValidationError') {
    return sendJSON(res, 422, {
      status: 'error',
      message: 'Data tidak valid',
      errors: error.details,
    });
  }

  if (error.name === 'NotFoundError') {
    return sendJSON(res, 404, {
      status: 'error',
      message: error.message,
    });
  }

  // Generic server error
  return sendJSON(res, 500, {
    status: 'error',
    message: isProduction
      ? 'Terjadi kesalahan internal server'
      : error.message, // Hanya di development
  });
}
```

### 5. Checklist Best Practices

```
HTTP BEST PRACTICES CHECKLIST:
─────────────────────────────────────────────────────────────
DESAIN API
☐ URL menggunakan noun, bukan verb
☐ URL menggunakan lowercase dan hyphen (kebab-case)
☐ Versi API di URL (/api/v1/) atau header
☐ Response format konsisten di semua endpoint
☐ Status code semantik dan tepat

KEAMANAN
☐ Selalu gunakan HTTPS di production
☐ Set security headers (X-Content-Type-Options, dll)
☐ Validasi semua input dari client
☐ Jangan expose stack trace di production
☐ Implementasi rate limiting
☐ Cookie dengan HttpOnly dan Secure flag

PERFORMA
☐ Set Cache-Control headers yang tepat
☐ Kompres response dengan gzip/brotli
☐ Gunakan Connection: keep-alive
☐ Batasi ukuran request body
☐ Implementasi pagination untuk list data

OBSERVABILITAS
☐ Log setiap request (method, path, status, duration)
☐ Tambahkan X-Request-ID untuk tracing
☐ Monitor response time dan error rate
```

---

# SECTION 14 — COMMON MISTAKES & ANTI-PATTERNS

## Kesalahan Umum dan Anti-Pattern

### Anti-Pattern 1: Mengabaikan HTTP Methods

```javascript
// ❌ ANTI-PATTERN: Semua operasi pakai POST
app.post('/api/getProducts', handler);
app.post('/api/createProduct', handler);
app.post('/api/deleteProduct', handler);
app.post('/api/updateProduct', handler);

// ✅ BENAR: Gunakan HTTP methods yang tepat
app.get('/api/products', getProducts);
app.post('/api/products', createProduct);
app.put('/api/products/:id', updateProduct);
app.delete('/api/products/:id', deleteProduct);
```

### Anti-Pattern 2: Status Code Tidak Tepat

```javascript
// ❌ ANTI-PATTERN: Selalu 200 OK
app.get('/products/:id', (req, res) => {
  const product = db.find(req.params.id);
  res.status(200).json({
    success: product ? true : false,
    data: product || null,
    error: product ? null : 'Not found',
  });
});

// ✅ BENAR: Status code mencerminkan kondisi sebenarnya
app.get('/products/:id', (req, res) => {
  const product = db.find(req.params.id);

  if (!product) {
    return res.status(404).json({
      status: 'error',
      message: 'Produk tidak ditemukan',
    });
  }

  res.status(200).json({
    status: 'success',
    data: product,
  });
});
```

### Anti-Pattern 3: Menyimpan Data Sensitif di URL

```
❌ JANGAN:
GET /login?username=budi&password=rahasia123
GET /products?api_key=sk-prod-abc123

Masalah:
- URL tersimpan di browser history
- URL muncul di server access log
- URL bisa ter-share tidak sengaja

✅ BENAR:
POST /login  (dengan body: {username, password})
GET /products  (dengan header: Authorization: Bearer <token>)
```

### Anti-Pattern 4: Tidak Memvalidasi Input

```javascript
// ❌ ANTI-PATTERN: Langsung pakai input tanpa validasi
app.post('/products', async (req, res) => {
  const product = await db.create(req.body); // BERBAHAYA!
  res.status(201).json(product);
});

// ✅ BENAR: Validasi semua input
app.post('/products', async (req, res) => {
  const { nama, harga, stok } = req.body;

  // Validasi tipe data
  if (typeof nama !== 'string' || nama.trim() === '') {
    return res.status(422).json({
      status: 'error',
      message: 'Field "nama" harus berupa string non-kosong',
    });
  }

  if (typeof harga !== 'number' || harga <= 0 || !isFinite(harga)) {
    return res.status(422).json({
      status: 'error',
      message: 'Field "harga" harus berupa angka positif',
    });
  }

  // Sanitasi input sebelum simpan ke database
  const product = await db.create({
    nama: nama.trim().substring(0, 255), // Batasi panjang
    harga: Math.round(harga),            // Pastikan integer
    stok: Math.max(0, Math.round(stok ?? 0)),
  });

  res.status(201).json({ status: 'success', data: product });
});
```

### Anti-Pattern 5: Mengabaikan CORS

```javascript
// ❌ ANTI-PATTERN: Allow semua origin tanpa pertimbangan
res.setHeader('Access-Control-Allow-Origin', '*');
// Ini berbahaya untuk API yang memerlukan autentikasi!

// ✅ BENAR: Whitelist origin yang diizinkan
const ALLOWED_ORIGINS = [
  'https://toko.com',
  'https://admin.toko.com',
  process.env.NODE_ENV === 'development' ? 'http://localhost:3000' : null,
].filter(Boolean);

function setCORSHeaders(req, res) {
  const origin = req.headers.origin;

  if (ALLOWED_ORIGINS.includes(origin)) {
    res.setHeader('Access-Control-Allow-Origin', origin);
    res.setHeader('Access-Control-Allow-Credentials', 'true');
  }

  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, PATCH, DELETE, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');
  res.setHeader('Access-Control-Max-Age', '86400'); // Cache preflight 24 jam
}
```

---

# SECTION 15 — DEBUGGING HTTP

## Cara Debug HTTP Request & Response

### Tools untuk Debugging

```
┌─────────────────────────────────────────────────────────────┐
│                    DEBUGGING TOOLS                          │
├────────────────────┬────────────────────────────────────────┤
│ TOOL               │ KEGUNAAN                               │
├────────────────────┼────────────────────────────────────────┤
│ Browser DevTools   │ Inspect request/response di browser    │
│ (Network Tab)      │ Lihat headers, body, timing            │
├────────────────────┼────────────────────────────────────────┤
│ cURL               │ Kirim HTTP request dari terminal       │
│                    │ Lihat raw request/response             │
├────────────────────┼────────────────────────────────────────┤
│ Postman            │ GUI untuk test API                     │
│                    │ Simpan collection, environment         │
├────────────────────┼────────────────────────────────────────┤
│ Insomnia           │ Alternatif Postman, lebih ringan       │
├────────────────────┼────────────────────────────────────────┤
│ httpie             │ cURL yang lebih user-friendly          │
│                    │ http GET localhost:3000/products       │
├────────────────────┼────────────────────────────────────────┤
│ Wireshark          │ Capture dan analisis network traffic   │
│                    │ Lihat packet level (advanced)          │
├────────────────────┼────────────────────────────────────────┤
│ mitmproxy          │ Man-in-the-middle proxy untuk debug    │
│                    │ Intercept dan modifikasi request       │
└────────────────────┴────────────────────────────────────────┘
```

### Request Logger Middleware

```javascript
// file: middleware/logger.js
// Implementasi request logger sederhana

function requestLogger(req, res, next) {
  const startTime = Date.now();
  const requestId = generateRequestId();

  // Tambahkan request ID ke request object
  req.requestId = requestId;

  // Log request masuk
  console.log(JSON.stringify({
    type: 'REQUEST',
    requestId,
    method: req.method,
    url: req.url,
    headers: {
      'content-type': req.headers['content-type'],
      'user-agent': req.headers['user-agent'],
      'authorization': req.headers['authorization']
        ? '[REDACTED]'  // Jangan log token!
        : undefined,
    },
    timestamp: new Date().toISOString(),
  }));

  // Intercept response untuk log status code
  const originalEnd = res.end;
  res.end = function (...args) {
    const duration = Date.now() - startTime;

    console.log(JSON.stringify({
      type: 'RESPONSE',
      requestId,
      method: req.method,
      url: req.url,
      statusCode: res.statusCode,
      duration: `${duration}ms`,
      timestamp: new Date().toISOString(),
    }));

    originalEnd.apply(res, args);
  };

  next();
}

function generateRequestId() {
  return `req_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
}

module.exports = { requestLogger };
```

### Debugging dengan cURL

```bash
# Lihat semua detail request dan response
curl -v http://localhost:3000/products

# Kirim POST dengan body JSON
curl -v -X POST http://localhost:3000/products \
  -H "Content-Type: application/json" \
  -d '{"nama":"Test","harga":100000}'

# Lihat hanya response headers
curl -I http://localhost:3000/products

# Ikuti redirect
curl -L http://localhost:3000/old-path

# Set custom header
curl -H "Authorization: Bearer mytoken123" \
     -H "Accept: application/json" \
     http://localhost:3000/profile

# Simpan response ke file
curl -o response.json http://localhost:3000/products

# Ukur waktu response
curl -w "\nTime: %{time_total}s\nStatus: %{http_code}\n" \
     -o /dev/null -s http://localhost:3000/products
```

---

# SECTION 16 — HANDS-ON EXERCISE

## Latihan Praktis

### Exercise 1: Analisis HTTP Traffic (Beginner)

**Tujuan:** Memahami struktur request dan response HTTP

**Langkah:**
1. Buka browser Chrome/Firefox
2. Buka DevTools (F12) → Tab Network
3. Kunjungi `https://jsonplaceholder.typicode.com/posts`
4. Klik request yang muncul di panel Network
5. Jawab pertanyaan berikut:

```
Pertanyaan:
a) Apa HTTP method yang digunakan?
b) Berapa status code response-nya?
c) Apa nilai header Content-Type pada response?
d) Berapa lama waktu yang dibutuhkan (Time)?
e) Apa isi dari response body?
```

### Exercise 2: Server HTTP Dasar (Beginner)

**Tujuan:** Membuat server HTTP pertama dengan Node.js

**Tugas:**
```javascript
// Buat file: exercise-02.js
// Implementasikan server yang:
// 1. GET /  → "Selamat datang di server saya!"
// 2. GET /about → JSON: {nama: "...", versi: "1.0.0"}
// 3. GET /time → JSON: {waktu: <timestamp sekarang>}
// 4. Semua path lain → 404 dengan pesan yang jelas

// Kriteria penilaian:
// ✅ Server berjalan tanpa error
// ✅ Status code tepat (200 untuk sukses, 404 untuk tidak ditemukan)
// ✅ Content-Type header diset dengan benar
// ✅ Response body sesuai spesifikasi
```

### Exercise 3: REST API Produk (Intermediate)

**Tujuan:** Implementasi CRUD lengkap dengan HTTP

**Tugas:**
```
Buat REST API untuk manajemen buku dengan endpoint:

GET    /books              → Daftar semua buku
GET    /books/:id          → Detail buku
POST   /books              → Tambah buku baru
PUT    /books/:id          → Update buku (semua field)
PATCH  /books/:id          → Update buku (sebagian field)
DELETE /books/:id          → Hapus buku

Model Buku:
{
  id: number,
  judul: string (wajib, max 200 karakter),
  penulis: string (wajib),
  tahun: number (wajib, 1000-2024),
  isbn: string (opsional, format: XXX-X-XX-XXXXXX-X),
  tersedia: boolean (default: true)
}

Kriteria:
✅ Validasi input yang lengkap
✅ Status code yang tepat
✅ Response format konsisten
✅ Error handling yang baik
✅ Logging setiap request
```

### Exercise 4: HTTP Headers Inspector (Advanced)

**Tujuan:** Memahami dan memanipulasi HTTP headers

**Tugas:**
```javascript
// Buat server yang:
// 1. Membaca Accept header dan mengembalikan response
//    dalam format yang diminta (JSON atau XML atau plain text)
// 2. Implementasi basic authentication via Authorization header
// 3. Set cache headers yang tepat:
//    - GET /static → Cache 1 jam
//    - GET /dynamic → No cache
// 4. Tambahkan security headers ke semua response
// 5. Implementasi rate limiting sederhana (max 10 req/menit per IP)
//    menggunakan X-Rate-Limit-* headers
```

### Kunci Jawaban Exercise 2

```javascript
// exercise-02-solution.js
const http = require('http');

const server = http.createServer((req, res) => {
  const { method, url } = req;

  // Helper untuk kirim response
  const send = (statusCode, contentType, body) => {
    res.writeHead(statusCode, { 'Content-Type': contentType });
    res.end(body);
  };

  if (method !== 'GET') {
    return send(405, 'application/json',
      JSON.stringify({ error: 'Method tidak didukung' }));
  }

  switch (url) {
    case '/':
      return send(200, 'text/plain; charset=utf-8',
        'Selamat datang di server saya!');

    case '/about':
      return send(200, 'application/json',
        JSON.stringify({ nama: 'Server Latihan', versi: '1.0.0' }));

    case '/time':
      return send(200, 'application/json',
        JSON.stringify({ waktu: new Date().toISOString() }));

    default:
      return send(404, 'application/json',
        JSON.stringify({
          status: 'error',
          message: `Path "${url}" tidak ditemukan`,
        }));
  }
});

server.listen(3000, () => {
  console.log('Server berjalan di http://localhost:3000');
});
```

---

# SECTION 17 — QUIZ & ASSESSMENT

## Kuis dan Penilaian

### Kuis Pilihan Ganda

**Soal 1:** Manakah HTTP method yang bersifat idempoten DAN aman (safe)?
```
A) POST
B) PUT
C) GET  ✅
D) PATCH
```
*Penjelasan: GET bersifat idempoten (hasil sama jika diulang) dan safe (tidak mengubah state server)*

**Soal 2:** Status code apa yang tepat ketika user berhasil membuat resource baru?
```
A) 200 OK
B) 201 Created  ✅
C) 204 No Content
D) 202 Accepted
```

**Soal 3:** Header apa yang digunakan untuk mengirim token autentikasi?
```
A) X-Auth-Token
B) Cookie
C) Authorization  ✅
D) Authentication
```

**Soal 4:** Apa yang dimaksud dengan HTTP bersifat "stateless"?
```
A) Server tidak bisa menyimpan data
B) Setiap request independen, server tidak ingat request sebelumnya  ✅
C) Client tidak menyimpan state apapun
D) Tidak ada state dalam aplikasi web
```

**Soal 5:** Manakah URL yang mengikuti REST best practices?
```
A) GET /getAllProducts
B) POST /products/create
C) GET /products  ✅
D) GET /product-list
```

### Soal Essay

```
1. Jelaskan perbedaan antara PUT dan PATCH. Berikan contoh
   kasus penggunaan yang tepat untuk masing-masing.

2. Mengapa HTTP bersifat stateless? Apa keuntungan dan
   kerugiannya? Bagaimana cara mengelola state di aplikasi
   web yang menggunakan HTTP?

3. Seorang developer mengembalikan status code 200 OK
   untuk semua response, termasuk ketika terjadi error.
   Jelaskan masalah yang ditimbulkan dan bagaimana
   seharusnya.

4. Jelaskan perbedaan antara header Content-Type dan
   Accept. Kapan masing-masing digunakan?
```

### Rubrik Penilaian

```
KOMPONEN PENILAIAN:
─────────────────────────────────────────────────────────────
Kuis Pilihan Ganda (5 soal × 10 poin)      = 50 poin
Essay (4 soal × 10 poin)                   = 40 poin
Exercise Praktis (Exercise 2 & 3)          = 60 poin
─────────────────────────────────────────────────────────────
TOTAL                                      = 150 poin

GRADE:
135-150 → A (Sangat Baik)
120-134 → B (Baik)
105-119 → C (Cukup)
90-104  → D (Perlu Perbaikan)
< 90    → E (Remedial)
```

---

# SECTION 18 — FURTHER READING & RESOURCES

## Referensi dan Bacaan Lanjutan

### Dokumentasi Resmi

```
1. MDN Web Docs - HTTP
   https://developer.mozilla.org/en-US/docs/Web/HTTP
   → Referensi paling lengkap dan terpercaya untuk HTTP

2. RFC 9110 - HTTP Semantics (2022)
   https://www.rfc-editor.org/rfc/rfc9110
   → Spesifikasi resmi HTTP (untuk yang ingin sangat mendalam)

3. Node.js HTTP Module Documentation
   https://nodejs.org/api/http.html
   → Dokumentasi resmi modul http Node.js
```

### Buku Rekomendasi

```
1. "HTTP: The Definitive Guide" - David Gourley
   Level: Intermediate
   Topik: HTTP secara mendalam, caching, autentikasi

2. "RESTful Web APIs" - Leonard Richardson
   Level: Intermediate
   Topik: Desain API RESTful yang baik

3. "Web Scalability for Startup Engineers" - Artur Ejsmont
   Level: Intermediate-Advanced
   Topik: Skalabilitas aplikasi web
```

### Tools Online

```
1. httpbin.org
   → Service untuk test HTTP request (echo request, simulasi error)
   Contoh: curl https://httpbin.org/get

2. jsonplaceholder.typicode.com
   → Fake REST API untuk prototyping dan testing

3. reqbin.com
   → Online HTTP client (alternatif Postman berbasis web)

4. http.cat
   → Referensi status code dengan gambar kucing 😄
   Contoh: https://http.cat/404

5. requestbin.com
   → Inspect HTTP request yang masuk (untuk debug webhook)
```

### Video & Kursus

```
1. "HTTP Crash Course" - Traversy Media (YouTube)
   Durasi: ~1 jam, gratis

2. "Computer Networking: HTTP" - Khan Academy
   Level: Beginner, gratis

3. "REST API Design" - Pluralsight
   Level: Intermediate, berbayar
```

### Topik Lanjutan Setelah Modul Ini

```
ROADMAP BELAJAR SELANJUTNYA:
─────────────────────────────────────────────────────────────
Modul Ini (HTTP Fundamentals)
        │
        ▼
Bab 04: Express.js Framework
        │
        ▼
Bab 05: RESTful API Design
        │
        ▼
Bab 06: Autentikasi & Autorisasi (JWT, OAuth)
        │
        ▼
Bab 07: Database Integration
        │
        ▼
Bab 08: API Security & Rate Limiting
        │
        ▼
Bab 09: Caching Strategies
        │
        ▼
Bab 10: API Documentation (OpenAPI/Swagger)
```

---

# SECTION 19 — SUMMARY & KEY TAKEAWAYS

## Ringkasan dan Poin Kunci

### Recap Konsep Utama

```
╔═══════════════════════════════════════════════════════════════════╗
║              RINGKASAN BAB 03 MODULE 01: HTTP FUNDAMENTALS       ║
╠═══════════════════════════════════════════════════════════════════╣
║                                                                   ║
║  1. HTTP ADALAH FONDASI WEB                                       ║
║     • Protokol request-response antara client dan server         ║
║     • Text-based, stateless, application-layer protocol          ║
║     • HTTPS = HTTP + TLS (enkripsi end-to-end)                  ║
║                                                                   ║
║  2. ANATOMI HTTP MESSAGE                                          ║
║     Request:  Method + URL + Headers + Body                      ║
║     Response: Status Code + Headers + Body                       ║
║                                                                   ║
║  3. HTTP METHODS (CRUD MAPPING)                                   ║
║     GET    → Read (idempoten, safe)                              ║
║     POST   → Create (tidak idempoten)                            ║
║     PUT    → Replace (idempoten)                                 ║
║     PATCH  → Partial Update                                      ║
║     DELETE → Delete (idempoten)                                  ║
║                                                                   ║
║  4. STATUS CODES                                                  ║
║     2xx → Sukses (200 OK, 201 Created, 204 No Content)          ║
║     3xx → Redirect (301, 302, 304)                              ║
║     4xx → Client Error (400, 401, 403, 404, 422, 429)          ║
║     5xx → Server Error (500, 502, 503, 504)                     ║
║                                                                   ║
║  5. HTTP HEADERS                                                  ║
║     • Metadata untuk request dan response                        ║
║     • Content-Type, Authorization, Cache-Control, CORS          ║
║     • Security headers wajib di production                       ║
║                                                                   ║
║  6. STATELESS & STATE MANAGEMENT                                  ║
║     • HTTP stateless: server tidak ingat request sebelumnya     ║
║     • Solusi: Cookie, JWT, Session, URL params                   ║
║                                                                   ║
║  7. BEST PRACTICES                                                ║
║     • URL menggunakan noun, bukan verb                           ║
║     • Status code semantik dan konsisten                         ║
║     • Validasi semua input                                       ║
║     • Security headers di setiap response                        ║
║     • Log setiap request untuk observabilitas                    ║
╚═══════════════════════════════════════════════════════════════════╝
```

### Mind Map Konsep

```
                         HTTP
                          │
          ┌───────────────┼───────────────┐
          │               │               │
       REQUEST         RESPONSE        CONCEPTS
          │               │               │
    ┌─────┴─────┐   ┌─────┴─────┐   ┌───┴────┐
    │           │   │           │   │        │
  Method    Headers Status   Headers Stateless URL
    │           │   Code        │        │
  GET        Host  200      Content  Cookie  Path
  POST       Auth  201       Type    JWT    Query
  PUT        Type  404      Cache   Session  Port
  PATCH      Agent 500      CORS
  DELETE
```

### 5 Hal yang Harus Diingat

```
┌─────────────────────────────────────────────────────────────┐
│  5 TAKEAWAY UTAMA MODUL INI                                 │
│                                                             │
│  1️⃣  HTTP adalah bahasa komunikasi web — kuasai ini dulu   │
│     sebelum framework apapun                               │
│                                                             │
│  2️⃣  Gunakan HTTP method yang TEPAT sesuai operasi CRUD    │
│     (GET=Read, POST=Create, PUT=Replace, DELETE=Delete)    │
│                                                             │
│  3️⃣  Status code adalah "bahasa" server kepada client —    │
│     gunakan dengan semantik yang benar                     │
│                                                             │
│  4️⃣  HTTP stateless bukan kelemahan — ini adalah desain    │
│     yang memungkinkan skalabilitas tinggi                  │
│                                                             │
│  5️⃣  Keamanan dimulai dari HTTP — HTTPS, security headers, │
│     validasi input adalah non-negotiable di production     │
└─────────────────────────────────────────────────────────────┘
```

---

# SECTION 20 — GLOSSARY & APPENDIX

## Glosarium dan Lampiran

### Glosarium Istilah HTTP

```
┌─────────────────────────────────────────────────────────────────┐
│                         GLOSARIUM                               │
├──────────────────────┬──────────────────────────────────────────┤
│ ISTILAH              │ DEFINISI                                 │
├──────────────────────┼──────────────────────────────────────────┤
│ HTTP                 │ HyperText Transfer Protocol — protokol   │
│                      │ komunikasi web berbasis teks             │
├──────────────────────┼──────────────────────────────────────────┤
│ HTTPS                │ HTTP Secure — HTTP dengan enkripsi TLS   │
├──────────────────────┼──────────────────────────────────────────┤
│ Request              │ Pesan yang dikirim client ke server      │
├──────────────────────┼──────────────────────────────────────────┤
│ Response             │ Pesan balasan dari server ke client      │
├──────────────────────┼──────────────────────────────────────────┤
│ Header               │ Metadata key-value dalam HTTP message    │
├──────────────────────┼──────────────────────────────────────────┤
│ Body                 │ Konten/payload dalam HTTP message        │
├──────────────────────┼──────────────────────────────────────────┤
│ Status Code          │ Kode 3 digit hasil pemrosesan request    │
├──────────────────────┼──────────────────────────────────────────┤
│ URL                  │ Uniform Resource Locator — alamat resource│
├──────────────────────┼──────────────────────────────────────────┤
│ URI                  │ Uniform Resource Identifier (lebih umum) │
├──────────────────────┼──────────────────────────────────────────┤
│ REST                 │ Representational State Transfer —        │
│                      │ arsitektur desain API berbasis HTTP      │
├──────────────────────┼──────────────────────────────────────────┤
│ Stateless            │ Setiap request independen, server tidak  │
│                      │ menyimpan state antar request            │
├──────────────────────┼──────────────────────────────────────────┤
│ Idempoten            │ Operasi yang menghasilkan hasil sama     │
│                      │ meski dieksekusi berkali-kali            │
├──────────────────────┼──────────────────────────────────────────┤
│ Cookie               │ Data kecil yang disimpan browser,        │
│                      │ dikirim otomatis di setiap request       │
├──────────────────────┼──────────────────────────────────────────┤
│ Session              │ Data user yang disimpan di server        │
├──────────────────────┼──────────────────────────────────────────┤
│ JWT                  │ JSON Web Token — token autentikasi       │
│                      │ yang self-contained                      │
├──────────────────────┼──────────────────────────────────────────┤
│ CORS                 │ Cross-Origin Resource Sharing —          │
│                      │ mekanisme izin akses lintas domain       │
├──────────────────────┼──────────────────────────────────────────┤
│ TLS/SSL              │ Transport Layer Security — protokol      │
│                      │ enkripsi untuk HTTPS                     │
├──────────────────────┼──────────────────────────────────────────┤
│ DNS                  │ Domain Name System — translasi domain    │
│                      │ ke IP address                            │
├──────────────────────┼──────────────────────────────────────────┤
│ TCP                  │ Transmission Control Protocol —          │
│                      │ protokol transport yang reliable         │
├──────────────────────┼──────────────────────────────────────────┤
│ Proxy                │ Perantara antara client dan server       │
├──────────────────────┼──────────────────────────────────────────┤
│ CDN                  │ Content Delivery Network — jaringan      │
│                      │ distribusi konten global                 │
├──────────────────────┼──────────────────────────────────────────┤
│ Rate Limiting        │ Pembatasan jumlah request dalam          │
│                      │ periode waktu tertentu                   │
├──────────────────────┼──────────────────────────────────────────┤
│ Middleware           │ Fungsi yang memproses request sebelum    │
│                      │ sampai ke handler utama                  │
├──────────────────────┼──────────────────────────────────────────┤
│ Payload              │ Data yang dibawa dalam body HTTP message  │
├──────────────────────┼──────────────────────────────────────────┤
│ Endpoint             │ URL spesifik yang menangani request      │
│                      │ tertentu di server                       │
└──────────────────────┴──────────────────────────────────────────┘
```

### Appendix A: HTTP Methods Quick Reference

```
METHOD   SAFE?  IDEMPOTEN?  BODY?   RESPONSE BODY?  PENGGUNAAN
───────────────────────────────────────────────────────────────
GET      ✅     ✅          ❌      ✅              Ambil data
HEAD     ✅     ✅          ❌      ❌              Cek metadata
POST     ❌     ❌          ✅      ✅              Buat resource
PUT      ❌     ✅          ✅      ✅              Ganti resource
PATCH    ❌     ⚠️          ✅      ✅              Update sebagian
DELETE   ❌     ✅          ⚠️      ⚠️              Hapus resource
OPTIONS  ✅     ✅          ❌      ✅              Cek capabilities
CONNECT  ❌     ❌          ❌      ✅              Buat tunnel
TRACE    ✅     ✅          ❌      ✅              Debug (echo)
```

### Appendix B: Status Code Quick Reference

```
2xx SUCCESS
200 OK                    → Request berhasil
201 Created               → Resource baru dibuat
202 Accepted              → Request diterima, diproses async
204 No Content            → Sukses tanpa response body
206 Partial Content       → Sebagian konten (untuk range request)

3xx REDIRECTION
301 Moved Permanently     → URL berubah permanen
302 Found                 → Redirect sementara
304 Not Modified          → Cache masih valid
307 Temporary Redirect    → Redirect sementara (pertahankan method)
308 Permanent Redirect    → Redirect permanen (pertahankan method)

4xx CLIENT ERROR
400 Bad Request           → Request tidak valid
401 Unauthorized          → Perlu autentikasi
403 Forbidden             → Tidak punya izin
404 Not Found             → Resource tidak ada
405 Method Not Allowed    → HTTP method tidak didukung
408 Request Timeout       → Request terlalu lama
409 Conflict              → Konflik dengan state saat ini
410 Gone                  → Resource dihapus permanen
413 Payload Too Large     → Body terlalu besar
415 Unsupported Media     → Content-Type tidak didukung
422 Unprocessable Entity  → Validasi gagal
429 Too Many Requests     → Rate limit terlampaui

5xx SERVER ERROR
500 Internal Server Error → Error tak terduga
501 Not Implemented       → Fitur belum diimplementasi
502 Bad Gateway           → Upstream server error
503 Service Unavailable   → Server tidak tersedia
504 Gateway Timeout       → Upstream server timeout
```

### Appendix C: Common HTTP Headers Reference

```
REQUEST HEADERS:
Accept              → Format yang bisa diterima client
Accept-Encoding     → Encoding yang didukung (gzip, br)
Accept-Language     → Bahasa yang diinginkan
Authorization       → Kredensial autentikasi
Content-Type        → Format body yang dikirim
Content-Length      → Ukuran body dalam bytes
Cookie              → Cookie yang disimpan browser
Host                → Domain tujuan (wajib di HTTP/1.1)
If-Modified-Since   → Kondisional: jika berubah sejak tanggal
If-None-Match       → Kondisional: jika ETag berbeda
Origin              → Domain asal request (untuk CORS)
Referer             → URL halaman sebelumnya
User-Agent          → Identitas client (browser/app)

RESPONSE HEADERS:
Access-Control-*    → CORS headers
Cache-Control       → Instruksi caching
Content-Encoding    → Encoding yang digunakan (gzip)
Content-Length      → Ukuran body dalam bytes
Content-Type        → Format body response
ETag                → Versi/identifier resource
Expires             → Tanggal expired cache (lama)
Last-Modified       → Tanggal terakhir resource diubah
Location            → URL untuk redirect
Set-Cookie          → Set cookie di browser
WWW-Authenticate    → Skema autentikasi yang diperlukan

SECURITY HEADERS:
Content-Security-Policy      → Batasi sumber konten
Strict-Transport-Security    → Paksa HTTPS
X-Content-Type-Options       → Cegah MIME sniffing
X-Frame-Options              → Cegah clickjacking
X-XSS-Protection             → Filter XSS (deprecated)
Referrer-Policy              → Kontrol Referer header
Permissions-Policy           → Kontrol fitur browser
```

---

## Metadata Modul

```
╔═══════════════════════════════════════════════════════════════╗
║                    METADATA MODUL                            ║
╠═══════════════════════════════════════════════════════════════╣
║  Kurikulum    : Backend Beginner                             ║
║  Kategori     : 01-Core-Foundations                          ║
║  Bab          : 03                                           ║
║  Modul        : 01                                           ║
║  Judul        : HTTP & Web Fundamentals                      ║
║  Durasi       : 4-6 jam (termasuk latihan)                  ║
║  Level        : Beginner                                     ║
║  Prasyarat    : Bab 01, Bab 02                              ║
║  Bahasa       : Indonesia Profesional Teknis                 ║
╠═══════════════════════════════════════════════════════════════╣
║  SECTION LIST:                                               ║
║  01. Learning Objective                                      ║
║  02. Concept Overview                                        ║
║  03. Why It Matters                                          ║
║  04. What Is HTTP                                            ║
║  05. How HTTP Works                                          ║
║  06. ASCII Diagram: HTTP Ecosystem                           ║
║  07. Simple Example                                          ║
║  08. Practical Example                                       ║
║  09. HTTP Status Codes                                       ║
║  10. HTTP Headers                                            ║
║  11. Stateless & State Management                            ║
║  12. Trade-offs & Considerations                             ║
║  13. Best Practices                                          ║
║  14. Common Mistakes & Anti-Patterns                         ║
║  15. Debugging HTTP                                          ║
║  16. Hands-on Exercise                                       ║
║  17. Quiz & Assessment                                       ║
║  18. Further Reading & Resources                             ║
║  19. Summary & Key Takeaways                                 ║
║  20. Glossary & Appendix                                     ║
╚═══════════════════════════════════════════════════════════════╝
```

---

*Dokumen ini dibuat sesuai standar GEMINI.md untuk kurikulum Backend Beginner.*
*Versi: 1.0.0 | Terakhir diperbarui: 2024*