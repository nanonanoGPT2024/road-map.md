# Bab 01: Fondasi Sistem Backend
## Module 01: Arsitektur Client-Server dan Siklus Hidup HTTP Request-Response

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- **Menganalisis** siklus hidup transaksi jaringan dari resolusi DNS, pembuatan socket TCP, TLS *handshake*, transmisi *stream* HTTP, hingga *socket termination*.
- **Mendekonstruksi** payload HTTP mentah (*raw wire format*) menjadi komponen struktural: *Request-Line*, *Headers*, *Carriage Return Line Feed* (`\r\n`), dan *Message Body*.
- **Mengimplementasikan** server HTTP minimalis berbasis soket TCP mentah tanpa abstraksi *framework* guna memahami parsing protokol di level sistem operasi.
- **Mengevaluasi** dampak performa dari *head-of-line blocking*, *connection pooling*, dan *keep-alive timeouts* pada infrastruktur backend skala produksi.

---

### 2. Konsep Utama
Bayangkan sistem backend sebagai **kantor pos modular dengan konveyor berjalan**.
- **Klien (Browser/Mobile App)** bertindak sebagai pengirim surat yang memasukkan dokumen ke dalam amplop berstandar internasional (Protokol HTTP).
- **Jaringan Internet** adalah sistem kurir dan rute logistik (IP Routing) yang membutuhkan alamat pasti (IP Address) yang didapat dari buku telepon global (DNS).
- **Socket TCP** adalah selang pneumatik fisik yang disambungkan antara pengirim dan kantor pos sebelum dokumen ditransfer.
- **Server Backend** adalah juru sortir di ujung selang: ia membaca stempel di bagian luar amplop (*Headers*), memastikan keabsahan segel keamanan (*TLS/SSL*), membaca isi instruksi (*Body*), memproses data ke gudang penyimpanan (*Database*), lalu menembakkan amplop balasan melalui selang pneumatik yang sama sebelum memutus sambungan atau membiarkannya terbuka (*Keep-Alive*).

---

### 3. Mengapa Ini Penting?
Banyak pengembang pemula memulai dengan *framework* tingkat tinggi (Express, NestJS, Spring Boot, Laravel) dan memperlakukan fungsi `req` dan `res` sebagai objek magis. Ketidaktahuan terhadap apa yang terjadi di bawah lapisan abstraksi (*leaky abstraction*) menimbulkan konsekuensi fatal di produksi:

1. **Memory Leaks & File Descriptor Exhaustion:** Mengabaikan *lifecycle* koneksi menyebabkan ribuan soket TCP menggantung dalam status `CLOSE_WAIT` atau `TIME_WAIT`, melumpuhkan server saat menerima lonjakan trafik (*traffic spike*).
2. **Masalah Keamanan (Request Smuggling):** Ketidaksesuaian interpretasi *header* `Content-Length` versus `Transfer-Encoding: chunked` antara reverse proxy (Nginx) dan backend server dapat dieksploitasi untuk menyuntikkan *request* berbahaya (*HTTP Request Smuggling* - CWE-444).
3. **Latensi Tinggi:** Gagal mengimplementasikan HTTP Persistent Connections (`Keep-Alive`) memaksa sistem melakukan *three-way handshake* TCP dan TLS *negotiation* berulang-ulang untuk setiap aset kecil, menambah *Round Trip Time* (RTT) sebesar 100ms–300ms secara tidak perlu.

---

### 4. Apa Sebenarnya Ini?
Arsitektur Client-Server adalah model komputasi terdistribusi di mana beban kerja dibagi antara penyedia sumber daya/layanan (*server*) dan pemohon layanan (*client*). Komunikasi ini distandarisasi oleh protokol **Hypertext Transfer Protocol (HTTP)** yang berjalan di lapisan aplikasi (Layer 7 OSI).

Berdasarkan **RFC 9112 (HTTP/1.1)**, data yang dikirim melalui jaringan merupakan deretan byte teks polos (sebelum dienkripsi TLS) yang diakhiri oleh pemisah baris spesifik `CRLF` (`\r\n` atau byte `0x0D 0x0A`).

Struktur anatomis HTTP Request mentah:
```text
GET /api/v1/users?page=1 HTTP/1.1\r\n             <-- Request-Line (Method, URI, HTTP-Version)
Host: api.example.com\r\n                         <-- Mandatory Header pada HTTP/1.1
User-Agent: curl/8.4.0\r\n                        <-- Request Header
Accept: application/json\r\n                      <-- Request Header
Content-Length: 0\r\n                             <-- Entity Header
\r\n                                              <-- CRLF kosong (Pemisah Headers & Body)
[Optional Request Body di sini]                   <-- Payload data
```

Struktur anatomis HTTP Response mentah:
```text
HTTP/1.1 200 OK\r\n                               <-- Status-Line (Version, Status Code, Reason)
Date: Mon, 01 Jan 2024 12:00:00 GMT\r\n           <-- Response Header
Content-Type: application/json; charset=UTF-8\r\n <-- Representation Header
Content-Length: 27\r\n                            <-- Ukuran byte body
Connection: keep-alive\r\n                        <-- Connection Directive
\r\n                                              <-- CRLF kosong
{"status":"success","data":[]}                   <-- Response Body mentah
```

---

### 5. Bagaimana Cara Kerjanya?
Tahapan transmisi dari input URL hingga data diterima aplikasi backend:

1. **Resolusi DNS (Domain Name System):**
   - Klien mengecek *local cache* OS, resolver ISP, hingga *Authoritative Name Server* untuk mengubah `api.example.com` menjadi IP publik (misal: `93.184.216.34`).
2. **TCP 3-Way Handshake (Lapisan Transport - Layer 4):**
   - Klien mengirim paket `SYN` (Synchronize).
   - Server membalas dengan `SYN-ACK` (Synchronize-Acknowledge).
   - Klien membalas dengan `ACK` (Acknowledge). Koneksi *bidirectional stream socket* terbentuk di kernel OS.
3. **TLS Handshake (Khusus HTTPS / Port 443):**
   - Negosiasi cipher suite, pertukaran sertifikat SSL/TLS publik, dan derivasi kunci enkripsi simetris menggunakan algoritma Diffie-Hellman Ephemeral (DHE).
4. **Transmisi HTTP Request:**
   - Klien mem-format string HTTP mentah, mengalirkan byte ke soket TCP lokal kernel, dipaketkan ke segmen TCP, lalu ditransmisikan melalui kartu jaringan (NIC).
5. **Pemrosesan di Sisi Kernel Server & Web Server:**
   - Kernel server menerima interupsi perangkat keras dari NIC, merakit paket IP menjadi aliran TCP, menempatkannya di *Receive Buffer* (`SO_RCVBUF`).
   - Sistem backend membaca *buffer* via syscall (`read()` atau `recv()`), melakukan parsing HTTP *headers*, memvalidasi payload, mengeksekusi logika bisnis/kueri database, lalu menuliskan byte respons ke *Write Buffer* (`SO_SNDBUF`).
6. **Koneksi Dikelola atau Ditutup:**
   - Jika header `Connection: keep-alive` aktif, soket dipertahankan untuk request berikutnya. Jika `Connection: close`, soket diakhiri dengan proses *TCP 4-Way Handshake* (`FIN-ACK`).

---

### 6. Diagram Alur

```text
[ CLIENT ]                                                   [ SERVER ]
    |                                                            |
    |---- 1. DNS Resolution (api.example.com -> IP) ------------>|
    |<--- IP Address Returned -----------------------------------|
    |                                                            |
    |================ TCP 3-WAY HANDSHAKE =======================|
    |---- SYN (Seq=X) ------------------------------------------>|
    |<--- SYN-ACK (Seq=Y, Ack=X+1) ------------------------------|
    |---- ACK (Ack=Y+1) ---------------------------------------->|
    |                                                            |
    |================ TLS HANDSHAKE (HTTPS) =====================|
    |---- Client Hello ----------------------------------------->|
    |<--- Server Hello, Certificate, Key Exchange ---------------|
    |---- Key Exchange, Finished -------------------------------->|
    |<--- Session Established (Symmetric Encryption) ------------|
    |                                                            |
    |================ HTTP TRANSACTION LAYER ====================|
    |---- HTTP POST /api/v1/checkout HTTP/1.1\r\n -------------->| (Syscall: write)
    |     Host: ...\r\n                                          | --> Masuk OS RCVBUF
    |     Content-Length: 15\r\n\r\n                             | --> Parser membaca CRLF
    |     {"order_id":99}                                        | --> Logika Bisnis & DB
    |                                                            |
    |<--- HTTP/1.1 201 Created\r\n ------------------------------| (Syscall: send)
    |     Content-Type: application/json\r\n                     | <-- Keluar dari SNDBUF
    |     Content-Length: 16\r\n\r\n                             |
    |     {"status":"ok"}                                        |
    |                                                            |
    |============ CONNECTION TERMINATION (If Close) =============|
    |---- FIN (Seq=U) ------------------------------------------>|
    |<--- ACK (Ack=U+1) -----------------------------------------|
    |<--- FIN (Seq=V) -------------------------------------------|
    |---- ACK (Ack=V+1) ---------------------------------------->|
```

---

### 7. Contoh Sederhana: Raw TCP Server sebagai HTTP Server
Berikut adalah implementasi server HTTP primitif menggunakan modul soket murni (`node:net`) di Node.js. Server ini tidak menggunakan modul bawaan `node:http` agar proses parsing manual terlihat jelas.

```javascript
// raw-http-server.mjs
import net from 'node:net';

const server = net.createServer((socket) => {
  console.log(`[TCP] Client connected from ${socket.remoteAddress}:${socket.remotePort}`);

  socket.on('data', (buffer) => {
    const rawRequest = buffer.toString('utf-8');
    console.log('[DEBUG WIRE INBOUND]:\n' + rawRequest);

    // 1. Parsing Request-Line
    const lines = rawRequest.split('\r\n');
    const [requestLine] = lines;
    const [method, path, version] = requestLine.split(' ');

    console.log(`Parsed: Method=${method}, Path=${path}, Version=${version}`);

    // 2. Logika Respons Sederhana
    let body = '';
    let statusCode = '200 OK';

    if (method === 'GET' && path === '/') {
      body = JSON.stringify({ message: "Hello from Raw Socket Engine" });
    } else {
      statusCode = '404 Not Found';
      body = JSON.stringify({ error: "Resource Not Found" });
    }

    const payloadByteLength = Buffer.byteLength(body, 'utf-8');

    // 3. Membangun HTTP Response Mentah sesuai RFC 9112
    const rawResponse = 
      `HTTP/1.1 ${statusCode}\r\n` +
      `Date: ${new Date().toUTCString()}\r\n` +
      `Content-Type: application/json; charset=utf-8\r\n` +
      `Content-Length: ${payloadByteLength}\r\n` +
      `Connection: close\r\n` +
      `\r\n` +
      body;

    // 4. Kirim byte mentah ke soket TCP dan putus koneksi
    socket.write(rawResponse);
    socket.end();
  });

  socket.on('error', (err) => {
    console.error(`[TCP Error]: ${err.message}`);
  });
});

const PORT = 3000;
server.listen(PORT, '127.0.0.1', () => {
  console.log(`Raw HTTP Engine listening directly on TCP port ${PORT}`);
});
```

---

### 8. Contoh Kompleks: Production-Grade HTTP Dispatcher Native
Di level industri, kita menggunakan abstraksi `node:http` bawaan runtime, namun wajib mengelola *event stream*, alokasi memori buffer, penanganan error tak terduga, graceful timeout, dan *headers parsing*.

```javascript
// server-production.mjs
import http from 'node:http';
import { Buffer } from 'node:buffer';

const MAX_PAYLOAD_SIZE = 1024 * 1024; // 1 Megabyte batas perlindungan DoS

const server = http.createServer((req, res) => {
  const { method, url, headers } = req;
  const requestId = crypto.randomUUID();

  // Audit Log Transaksi
  console.log(JSON.stringify({
    timestamp: new Date().toISOString(),
    traceId: requestId,
    event: 'inbound_request',
    method,
    url,
    ip: req.socket.remoteAddress,
  }));

  // Route Guarding & Dispatching
  if (url === '/api/v1/telemetry' && method === 'POST') {
    // 1. Validasi tipe konten
    if (headers['content-type'] !== 'application/json') {
      res.writeHead(415, { 'Content-Type': 'application/json' });
      return res.end(JSON.stringify({ error: 'Unsupported Media Type: expected application/json' }));
    }

    const chunks = [];
    let receivedBytes = 0;

    // 2. Stream Buffer Processing
    req.on('data', (chunk) => {
      receivedBytes += chunk.length;

      // Proteksi Memory Exhaustion / OOM Attack
      if (receivedBytes > MAX_PAYLOAD_SIZE) {
        res.writeHead(413, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Payload Too Large: max 1MB allowed' }));
        req.destroy(); // Hentikan transmisi soket langsung
      } else {
        chunks.push(chunk);
      }
    });

    req.on('end', () => {
      if (res.writableEnded) return;

      try {
        const rawBody = Buffer.concat(chunks).toString('utf-8');
        const parsedBody = JSON.parse(rawBody);

        // Simulasi Logika Bisnis
        const responseData = {
          status: 'success',
          dataReceived: parsedBody,
          processedByTrace: requestId
        };

        const jsonOutput = JSON.stringify(responseData);

        // 3. Pengiriman Respons Aman
        res.writeHead(200, {
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(jsonOutput),
          'X-Request-Id': requestId,
          'X-Content-Type-Options': 'nosniff' // Standar Security Header
        });
        res.end(jsonOutput);

      } catch (parseError) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Malformed JSON syntax' }));
      }
    });

    req.on('error', (err) => {
      console.error(`[Stream Error] TraceId: ${requestId}:`, err);
      if (!res.headersSent) {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Internal Server Error reading payload' }));
      }
    });

  } else {
    // 404 Handler Default
    res.writeHead(404, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Route not found' }));
  }
});

// Server Configuration & Defensive Timeouts (Pencegahan Slowloris Attack)
server.timeout = 5000;         // Waktu henti respons (5 detik)
server.keepAliveTimeout = 65000; // Lebih besar dari keep-alive timeout Nginx (biasanya 60s)
server.headersTimeout = 66000;   // Waktu maksimum menerima headers

server.listen(8080, () => {
  console.log('Production-Grade HTTP server listening on port 8080');
});
```

---

### 9. Trade-offs & Analisis Perbandingan

| Dimensi Parameter | HTTP/1.1 (Persistent TCP) | HTTP/2 (Multiplexing) | Raw Socket TCP (Tanpa HTTP) |
|---|---|---|---|
| **Multiplexing** | Tidak ada. Rawan *Head-of-Line Blocking* di L7. 1 Request per TCP Connection sekaligus. | Ya. Ribuan request stream berjalan paralel dalam 1 TCP connection. | Tidak ada framing bawaan, harus didesain mandiri. |
| **Header Overhead** | Besar. Mengirim teks ASCII berulang (Cookie, User-Agent) di tiap request. | Ringkas. Menggunakan kompresi HPACK untuk efisiensi transfer data. | Nol secara default. Protokol binary kustom (paling hemat byte). |
| **Kebutuhan CPU** | Rendah. String parsing sederhana berbasis CRLF. | Menengah-Tinggi. Membutuhkan framing biner, kompresi, dan dekompresi stateful. | Sangat Rendah. Mengurai struct byte mentah secara langsung. |
| **Kemudahan Debugging**| Sangat Mudah. Dapat dibaca langsung oleh manusia (*human-readable*) via Wireshark/cURL. | Sulit. Payload biner; membutuhkan software decoder terintegrasi. | Sangat Sulit. Membutuhkan spesifikasi dokumentasi biner internal. |
| **Kompatibilitas Browser**| Universal (100% peramban dan perangkat IoT lama). | Modern (Hampir seluruh browser modern via TLS ALPN). | Nol. Browser web standar menolak komunikasi non-HTTP/WS. |

---

### 10. Panduan Implementasi Bertahap
Untuk memverifikasi konsep di atas di mesin lokal Anda:

1. Simpan kode dari Seksi 7 ke file bernama `raw-http-server.mjs`.
2. Buka terminal Anda, jalankan program:
   ```bash
   node raw-http-server.mjs
   ```
3. Buka tab terminal kedua, kirim request HTTP via `cURL` dengan mode *verbose* (`-v`) untuk melihat data soket mentah:
   ```bash
   curl -v http://127.0.0.1:3000/
   ```
4. Amati output cURL. Anda akan melihat:
   - Baris diawali `>`: Data dikirim oleh klien (Request).
   - Baris diawali `<`: Data dibalas oleh server (Response).
5. Buat simulasi HTTP Request mentah manual menggunakan utilitas jaringan tingkat rendah `nc` (*netcat*):
   ```bash
   nc 127.0.0.1 3000
   ```
   Ketik secara tepat (tekan Enter dua kali di akhir):
   ```text
   GET / HTTP/1.1
   Host: 127.0.0.1
   
   ```
6. Amati bagaimana server merespons instruksi byte Anda secara langsung.

---

### 11. Jebakan Pemula & Anti-Patterns

#### Anti-Pattern 1: Mengabaikan Penghitungan Byte Length (`Content-Length`)
Menghitung panjang body menggunakan karakter string (`string.length`), bukan ukuran byte asli (`Buffer.byteLength`).
```javascript
// BURUK (Bug Tersembunyi saat ada karakter multi-byte/Unicode):
const data = "Halo Dunia 🚀"; 
res.writeHead(200, {
  // SALAH! "Halo Dunia 🚀".length adalah 13, padahal ukuran byte aslinya adalah 15!
  'Content-Length': data.length 
});
res.end(data); // Browser memotong data karena mengira hanya ada 13 byte.

// BENAR:
const data = "Halo Dunia 🚀";
res.writeHead(200, {
  'Content-Length': Buffer.byteLength(data, 'utf-8') // 15 Bytes!
});
res.end(data);
```

#### Anti-Pattern 2: Asumsi Seluruh Body Masuk dalam 1 Chunk Event
Banyak pemula berasumsi `req.on('data', callback)` hanya dipanggil sekali.
```javascript
// BURUK:
let body;
req.on('data', (chunk) => {
  body = JSON.parse(chunk); // Crash jika payload terpotong ke beberapa paket TCP MTU!
});

// BENAR:
const chunks = [];
req.on('data', (chunk) => chunks.push(chunk));
req.on('end', () => {
  const completeBody = Buffer.concat(chunks).toString('utf-8');
  const body = JSON.parse(completeBody);
});
```

---

### 12. Best Practices & Standar Industri
- **Gunakan Keep-Alive Timeouts yang Terkoordinasi:** Nilai `server.keepAliveTimeout` di backend Node.js/Go harus selalu **lebih besar** daripada nilai *upstream idle timeout* reverse proxy (misal Nginx atau AWS ALB). Jika reverse proxy berasumsi soket masih hidup sementara backend memutusnya secara sepihak, klien akan mengalami eror `502 Bad Gateway`.
- **Enforce Content-Type Sniffing Prevention:** Wajib mencantumkan header respons `X-Content-Type-Options: nosniff` untuk mencegah browser mengeksekusi file teks biasa sebagai executable script/CSS.
- **Idempotensi HTTP Methods:** Patuhi spesifikasi RFC 9110:
  - `GET`, `HEAD`, `OPTIONS` wajib **Safe** (tidak memutasi data) dan **Idempotent**.
  - `PUT`, `DELETE` wajib **Idempotent** (eksekusi berkali-kali menghasilkan state sistem yang sama).
  - `POST`, `PATCH` bersifat **Non-Idempotent**.

---

### 13. Integrasi & Ekosistem
Siklus HTTP tidak berhenti di aplikasi backend. Di arsitektur enterprise:
- **Reverse Proxy / API Gateway (Kong, Nginx, Envoy):** Berada di lapisan terdepan publik, melakukan terminasi TLS, menampung puluhan ribu koneksi lambat dari klien mobile, lalu meneruskan request ke server backend via *internal connection pool* dengan latensi ultra-rendah.
- **Load Balancer (L4 vs L7):** Load Balancer L4 (AWS NLB) mendistribusikan lalu lintas di level paket TCP murni tanpa membaca isi request. Load Balancer L7 (AWS ALB) menginspeksi header HTTP untuk routing URL `/api/v1/auth` vs `/api/v1/orders`.
- **Database Connection Sockets:** Siklus hidup request HTTP ini memicu pembuatan soket TCP internal terpisah menuju database (misal port 5432 untuk PostgreSQL). Menggunakan *Connection Pooling* (seperti HikariCP atau PgBouncer) memisahkan daur hidup HTTP soket dari soket database.

---

### 14. Uji Kemampuan & Kasus Debugging

#### Skenario Kasus Nyata:
Server produksi berbasis microservice Anda sering mengalami kondisi hung (*stuck*) dan mengeluarkan log: `Error: read ECONNRESET` dan klien menerima status respons sporadis `502 Bad Gateway` saat jam sibuk. Server tidak crash, tetapi CPU utilisation turun drastis ke 0%.

#### Langkah Analisis Debugging:
1. **Inspeksi Network State:**
   Gunakan command Linux berikut di server untuk memeriksa tumpukan soket:
   ```bash
   ss -tan state time-wait | wc -l
   ss -tan state close-wait | wc -l
   ```
2. **Identifikasi Masalah:**
   Jika angka `CLOSE_WAIT` sangat tinggi, aplikasi Anda menerima sinyal pemutusan dari klien/proxy (`FIN`), namun kode backend Anda tidak memanggil `res.end()` atau gagal menutup soket yang bocor di blok error handling tak tertangkap (`try-catch` terlewat).
3. **Penyelesaian Kode:**
   Pastikan setiap cabang eksekusi memiliki jaminan finalisasi, serta memasang *Timeout Handler*:
   ```javascript
   req.on('timeout', () => {
     res.writeHead(408, { 'Content-Type': 'application/json' });
     res.end(JSON.stringify({ error: 'Request Timeout' }));
   });
   ```

---

### 15. Eksperimen Mandiri
Untuk mengasah pemahaman Anda hingga ke level byte:
1. **Eksperimen 1:** Jalankan server Seksi 7, ubah response `Content-Length` menjadi angka yang lebih kecil daripada ukuran aslinya (misal isi 5 padahal payload 30). Amati apa yang terjadi pada terminal cURL dan browser Anda.
2. **Eksperimen 2:** Gunakan cURL untuk membuat request HTTP dengan metode kustom yang tidak ada di standar RFC (misal: `curl -X BREW http://127.0.0.1:8080`). Amati bagaimana parser menangani string metode tersebut.
3. **Eksperimen 3:** Simulasikan *Slowloris Attack* lokal secara terkontrol menggunakan Python atau Bash script yang mengirim *header* HTTP byte-per-byte setiap 1 detik. Uji apakah konfigurasi `server.headersTimeout` pada Seksi 8 mampu memutuskan penyerang.

---

### 16. Cheat Sheet Ringkas

#### Kategori Kode Status HTTP (RFC 9110)
- `1xx Informational`: Protokol sedang diproses (contoh: `101 Switching Protocols`).
- `2xx Success`: Permintaan diterima, dipahami, dan disetujui (contoh: `200 OK`, `201 Created`, `204 No Content`).
- `3xx Redirection`: Tindakan lebih lanjut perlu diambil klien (contoh: `301 Moved Permanently`, `304 Not Modified`).
- `4xx Client Error`: Permintaan mengandung sintaks salah / otorisasi cacat (contoh: `400 Bad Request`, `401 Unauthorized`, `403 Forbidden`, `404 Not Found`, `422 Unprocessable Entity`).
- `5xx Server Error`: Server gagal memenuhi request yang valid (contoh: `500 Internal Server Error`, `502 Bad Gateway`, `503 Service Unavailable`, `504 Gateway Timeout`).

#### Karakter Pemisah Wajib Protokol
- CRLF: `\r\n` (Hex: `0x0D 0x0A`)
- Header/Body Separator: `\r\n\r\n` (Dua kali CRLF berturut-turut)

---

### 17. Glosarium Teknis
- **Socket:** Titik akhir abstraksi software (kombinasi IP Address + Port Number) yang disediakan oleh sistem operasi untuk mengirim dan menerima data antar node jaringan.
- **Round Trip Time (RTT):** Durasi waktu yang dibutuhkan sebuah paket data untuk berpindah dari titik asal ke titik tujuan dan kembali lagi ke titik asal.
- **File Descriptor (FD):** Handle/pointer integer abstrak yang digunakan oleh OS (Unix-like) untuk mengakses file, direktori, soket jaringan, atau pipa I/O.
- **Keep-Alive:** Mekanisme penggunaan kembali (*reuse*) satu koneksi TCP yang sama untuk mengirim banyak HTTP request/response tanpa inisialisasi ulang handshake.
- **Head-of-Line (HoL) Blocking:** Fenomena di mana antrean paket atau request terhenti total karena paket paling depan mengalami penundaan/kehilangan transmisi.

---

### 18. Rekomendasi Bacaan Lanjutan
1. **RFC 9112:** *HTTP/1.1 Specification* – Baca Bab 2 (Message Abstraction) dan Bab 6 (Connection Management) untuk melihat standar protokol global resmi.
2. **High Performance Browser Networking (Ilya Grigorik):** Bab 2 (*Introduction to TCP*) dan Bab 3 (*Introduction to TLS*). Buku fundamental terbaik terkait performa jaringan.
3. **Node.js Internals Documentation:** Pahami bagaimana integrasi *libuv* mengelola I/O polling menggunakan syscall kernel seperti `epoll` (Linux) atau `kqueue` (macOS).

---

### 19. Self-Assessment Rubric

| Kriteria Penilaian | Belum Kompeten (Novice) | Kompeten (Competent) | Mahir (Advanced) |
|---|---|---|---|
| **Pemahaman Transmisi Jaringan** | Mengira HTTP dan TCP adalah hal yang sama tanpa pemisahan layer OSI. | Mampu menjelaskan urutan 3-way handshake TCP sebelum payload HTTP dikirim. | Mampu menganalisis paket TLS record dan negosiasi socket menggunakan packet analyzer (Wireshark/tcpdump). |
| **Parsing Protokol HTTP** | Tidak mengerti peran CRLF (`\r\n`) dan menganggap response dikirim otomatis. | Mampu membedakan *Request-Line*, *Headers*, dan *Body* secara konseptual. | Mampu menulis parser HTTP stream manual dari soket TCP mentah dengan penanganan chunked encoding. |
| **Defensive Backend Programming** | Mengabaikan ukuran payload, memicu celah DoS dan Crash Out-of-Memory. | Menggunakan middleware pihak ketiga untuk membatasi ukuran request. | Mengimplementasikan validasi native stream, proteksi ukuran chunk, dan defensive timeout socket secara presisi. |

---

### 20. Penutup & Jembatan ke Bab Berikutnya
Selamat! Anda telah membongkar ilusi *framework* dan memahami mekanika riil komunikasi internet: dari getaran data di soket TCP, pemisahan baris CRLF, hingga orkestrasi status code HTTP. 

Pada **Modul 02: Desain RESTful API, Serialisasi Data, dan Manajemen Kontrak JSON**, kita akan melangkah dari lapisan protokol jaringan dasar ke lapisan rekayasa data. Kita akan membedah bagaimana menstrukturkan *endpoint*, merancang format pertukaran data yang skalabel, dan menerapkan validasi skema runtime yang tangguh terhadap manipulasi input.