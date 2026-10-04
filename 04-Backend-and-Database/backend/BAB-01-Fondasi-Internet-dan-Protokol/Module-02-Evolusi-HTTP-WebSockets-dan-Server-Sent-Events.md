---
[⬅️ Module 01: Internet, TCP, & TLS 1.3](./Module-01-Bagaimana-Internet-Bekerja-IP-DNS-TCP-UDP-TLS.md) | [📋 Silabus Induk](../README.md) | [BAB 01 Quiz & Challenge ➡️](./BAB-01-Quiz-dan-Challenge.md)
---

# Module 02: Evolusi Protokol: HTTP/1.1 vs HTTP/2 vs HTTP/3, WebSockets, & Server-Sent Events (SSE)

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik mampu:
- Menganalisis evolusi protokol Hypertext Transfer Protocol dari **HTTP/1.1** $\rightarrow$ **HTTP/2** $\rightarrow$ **HTTP/3 (QUIC)**.
- Menjelaskan fenomena **Head-of-Line (HoL) Blocking** pada level aplikasi (HTTP/1.1) vs level transport TCP (HTTP/2), serta bagaimana QUIC (HTTP/3) mengeliminasinya secara total.
- Menguasai arsitektur internal HTTP/2: *Binary Framing Layer*, *Stream Multiplexing*, *HPACK Header Compression*, dan *Stream Priority*.
- Memahami protokol komunikasi real-time dua arah (**WebSockets - RFC 6455**): mekanisme handshake upgrade HTTP 101, framing biner, masking key, dan manajemen heartbeat (*ping/pong*).
- Mengimplementasikan streaming data searah berlatensi rendah (**Server-Sent Events / SSE**) untuk skenario pembaruan data berkala dan streaming token AI (LLM streaming response).
- Memilih protokol yang tepat berdasarkan matriks trade-off teknis dan kebutuhan bisnis.

---

## 2. Prerequisite
- Memahami TCP 3-Way Handshake dan dasar pengalamatan IP (Modul 01).
- Memahami format dasar HTTP Request dan Response (Headers, Method, Status Code, Body).
- Konsep dasar socket programming dan I/O non-blocking.

---

## 3. Concept
Web modern tidak lagi hanya menyajikan dokumen HTML statis. Aplikasi saat ini membutuhkan interaksi instan: dashboard perdagangan saham dengan pembaruan harga sub-milidetik, aplikasi ride-hailing yang melacak pergerakan kendaraan real-time, dan asisten AI yang melakukan *streaming token* kata per kata.

Untuk memenuhi kebutuhan ini, protokol lapisan aplikasi (*Application Layer*) mengalami lompatan arsitektur besar:
1. **HTTP/1.1**: Teks murni, satu request-response bergantian per koneksi (lambat).
2. **HTTP/2**: Format biner terkompresi, banyak request dapat dikirim serentak melalui satu koneksi TCP (*Multiplexing*).
3. **HTTP/3**: Mengganti transport TCP dengan **QUIC over UDP**, meniadakan keterlambatan paket hilang (*Zero HoL Blocking*) dan mendukung perpindahan jaringan mulus (*Connection Migration*).
4. **WebSockets**: Saluran pipa dua arah (*Full-Duplex*) permanen antara client dan backend.
5. **Server-Sent Events (SSE)**: Saluran pipa searah (*Unidirectional*) berbasis HTTP standar di mana server dapat terus-menerus mendorong (*push*) data ke client.

```
+-----------------------------------------------------------------------------------+
|                        APPLICATION PROTOCOL COMPARISON                            |
|                                                                                   |
|  [ HTTP/1.1 ]   Client ---> Request 1 ---> Server (Client waits...)               |
|                 Client <--- Response 1 <--- Server                                |
|                 Client ---> Request 2 ---> Server (Head-of-Line Blocking!)        |
|                                                                                   |
|  [ HTTP/2 ]     +--- Stream 1: GET /api/user --------+                            |
|                 |--- Stream 3: GET /api/products ----| Single TCP Connection      |
|                 +--- Stream 5: POST /api/checkout ---+ (Multiplexed Binary Frames)|
|                                                                                   |
|  [ WEBSOCKET ]  Client <====================================> Server              |
|                 (Full-Duplex Persistent Bi-directional TCP Stream via HTTP 101)   |
|                                                                                   |
|  [ SSE ]        Client -------------------------------------> Server (Connect)    |
|                 Client <===================================== Server (Data Stream)|
|                 (Unidirectional Server Push: text/event-stream)                   |
+-----------------------------------------------------------------------------------+
```

---

## 4. Why?
Mengapa pemahaman mendalam tentang protokol aplikasi sangat penting bagi Backend Engineer?
1. **Efisiensi Sumber Daya Server**: Pada HTTP/1.1, browser membuka hingga 6 koneksi TCP paralel per domain untuk mengakali keterlambatan request. Ini membebani RAM dan socket file descriptor di server. HTTP/2 dan HTTP/3 menyelesaikan masalah ini dengan hanya membutuhkan 1 koneksi.
2. **Pilihan Arsitektur Real-Time yang Tepat**: Banyak developer pemula memaksakan WebSocket untuk notifikasi satu arah, yang justru menambah kompleksitas stateful connection di load balancer. SSE seringkali menjadi solusi yang jauh lebih ringan dan tangguh.
3. **Optimasi Mobile & Poor Networks**: HTTP/3 memungkinkan pengguna berganti jaringan (misal dari Wi-Fi rumah ke 4G/5G) tanpa memutuskan panggilan API transaksi yang sedang berjalan (*zero disconnects*).

---

## 5. What?

### A. Anatomi HTTP/2 Binary Framing
HTTP/2 memecah komunikasi HTTP menjadi frame-frame biner:
- **Stream**: Saluran virtual dua arah di dalam satu koneksi TCP yang membawa sepasang request/response. Setiap stream memiliki ID unik (*Stream ID*).
- **Message**: Sekumpulan frame yang membentuk pesan utuh (request atau response).
- **Frame**: Unit komunikasi terkecil, terdiri dari:
  - `HEADERS Frame`: Membawa metadata HTTP headers (terkompresi via HPACK).
  - `DATA Frame`: Membawa payload body aplikasi.
  - `SETTINGS Frame`: Menegosiasikan konfigurasi koneksi.
  - `RST_STREAM Frame`: Membatalkan stream secara instan tanpa menutup koneksi TCP.

### B. Masalah Head-of-Line (HoL) Blocking & Solusi QUIC (HTTP/3)
- **HoL Blocking di HTTP/1.1 (Application Layer)**: Jika Request 1 membutuhkan waktu 5 detik di backend, Request 2 yang antre di koneksi yang sama harus menunggu 5 detik sebelum diproses.
- **HoL Blocking di HTTP/2 (Transport Layer)**: Karena semua stream HTTP/2 dilewatkan dalam **satu koneksi TCP tunggal**, jika ada 1 paket TCP yang hilang di tengah jalan (misal karena sinyal drop), kernel sistem operasi akan **menahan seluruh stream lainnya** sampai paket yang hilang tersebut selesai ditransmisikan ulang!
- **Solusi HTTP/3 (QUIC over UDP)**: Setiap stream di QUIC diperlakukan secara independen di atas UDP. Jika paket Stream 1 hilang, Stream 2 dan Stream 3 tetap mengalir tanpa penundaan sama sekali!

### C. WebSockets vs Server-Sent Events (SSE)

| Fitur | WebSockets (RFC 6455) | Server-Sent Events (SSE) |
|---|---|---|
| **Arah Komunikasi** | **Bi-directional (Full-Duplex)**: Client dan Server bisa saling kirim kapan saja | **Unidirectional**: Server ke Client saja |
| **Protokol Dasar** | Awalnya HTTP, lalu di-upgrade menjadi koneksi biner TCP mandiri (`ws://` atau `wss://`) | HTTP murni standar (`http://` atau `https://`) |
| **Content-Type** | N/A (Frame biner/teks khusus) | `text/event-stream` |
| **Kompatibilitas Proxy/Firewall**| Seringkali butuh konfigurasi khusus di NGINX/Load Balancer | Berjalan mulus di atas seluruh HTTP proxy dan CDN |
| **Fitur Reconnection** | Harus diimplementasikan manual oleh developer | **Bawaan browser otomatis** (EventSource API + `Last-Event-ID`) |
| **Tipe Data** | Teks (UTF-8) dan Biner (ArrayBuffer/Blob) | Teks murni (UTF-8) |

---

## 6. How?

### A. Alur Handshake Upgrade WebSocket (RFC 6455)
Koneksi WebSocket dimulai sebagai request HTTP/1.1 biasa dengan header khusus:

#### Request Client:
```http
GET /chat/room-101 HTTP/1.1
Host: api.perusahaan.com
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==
Sec-WebSocket-Version: 13
```

#### Respon Server:
Server mengambil `Sec-WebSocket-Key`, menggabungkannya dengan GUID statis standar (`258EAFA5-E914-47DA-95CA-C5AB0DC85B11`), menghitung hash SHA-1, dan meng-encode-nya menjadi Base64:

```http
HTTP/1.1 101 Switching Protocols
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=
```
Setelah status `101 Switching Protocols` dikembalikan, koneksi TCP tidak lagi menggunakan format HTTP, melainkan bertransformasi menjadi framing biner WebSocket.

### B. Format Data Server-Sent Events (SSE)
Server merespons request HTTP biasa dengan header `Content-Type: text/event-stream` dan membiarkan koneksi tetap terbuka (*chunked transfer*):

```http
HTTP/1.1 200 OK
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive

id: 1001
event: stock-price
data: {"symbol": "BBCA", "price": 9850, "timestamp": 1718002400}

id: 1002
event: stock-price
data: {"symbol": "BBRI", "price": 5400, "timestamp": 1718002401}
```

Jika koneksi jaringan terputus, browser client akan otomatis menyambung kembali dan mengirimkan header:
`Last-Event-ID: 1002`, sehingga backend tahu persis dari titik mana streaming data harus dilanjutkan!

---

## 7. Analogy
Bayangkan **Alat Komunikasi Manusia**:
- **HTTP/1.1**: Seperti **Surat Menyurat Melalui Pos Konvensional**. Anda mengirim satu surat pertanyaan, lalu Anda harus menunggu di depan kotak pos sampai surat balasan tiba sebelum Anda boleh mengirimkan surat kedua.
- **HTTP/2**: Seperti **Satu Kantor Pos Khusus dengan Puluhan Kurir Bersamaan**. Anda bisa memasukkan banyak amplop sekaligus, dan amplop-amplop tersebut dikirim bersamaan dalam satu mobil boks logistik.
- **HTTP/3**: Setiap kurir menggunakan sepeda motor masing-masing di atas jalan raya (UDP). Jika salah satu motor bannya bocor, motor-motor lainnya tetap melaju sampai ke tujuan tanpa terhenti.
- **WebSocket**: Seperti **Panggilan Telepon Langsung**. Anda dan lawan bicara mengangkat gagang telepon, saluran terbuka terus-menerus, dan kedua belah pihak dapat berbicara serentak tanpa jeda.
- **Server-Sent Events (SSE)**: Seperti **Siaran Berita Radio FM**. Anda menyalakan radio dan mendengarkan informasi terus-menerus dari stasiun pemancar. Anda tidak bisa membalas berbicara ke stasiun radio melalui pemancar tersebut.

---

## 8. Diagram: Arsitektur Frame HTTP/2 vs WebSocket vs SSE

```
+---------------------------------------------------------------------------------+
|                       REAL-TIME ARCHITECTURE COMPARISON                         |
+---------------------------------------------------------------------------------+

1. HTTP/2 MULTIPLEXING:
   TCP Socket: [Stream 1: Head][Stream 3: Head][Stream 1: Data][Stream 3: Data]...

2. WEBSOCKET FRAME STRUCTURE (RFC 6455):
    0                   1                   2                   3
    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
   +-+-+-+-+-------+-+-------------+-------------------------------+
   |F|R|R|R| opcode|M| Payload len |    Extended payload length    |
   |I|S|S|S|  (4)  |A|     (7)     |             (16/64)           |
   |N|V|V|V|       |S|             |   (if payload len==126/127)   |
   | |1|2|3|       |K|             |                               |
   +-+-+-+-+-------+-+-------------+ - - - - - - - - - - - - - - - +
   |     Masking-key (32-bit)      |          Payload Data         |
   +-------------------------------+ - - - - - - - - - - - - - - - +

3. SSE PAYLOAD STRUCTURE:
   TCP Socket: "id: 1\nevent: update\ndata: {\"status\":\"ok\"}\n\n"
```

---

## 9. Simple Example: Node.js Server-Sent Events Endpoint

```javascript
const http = require('http');

http.createServer((req, res) => {
  if (req.url === '/events') {
    // 1. Set headers wajib untuk SSE
    res.writeHead(200, {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
      'Access-Control-Allow-Origin': '*'
    });

    let counter = 1;
    // 2. Kirim data periodik ke client
    const intervalId = setInterval(() => {
      res.write(`id: ${counter}\n`);
      res.write(`event: notification\n`);
      res.write(`data: ${JSON.stringify({ message: "Ping dari server", tick: counter })}\n\n`);
      counter++;
    }, 2000);

    // 3. Bersihkan interval saat client menutup koneksi
    req.on('close', () => {
      clearInterval(intervalId);
      res.end();
    });
  } else {
    res.writeHead(404);
    res.end();
  }
}).listen(8080, () => console.log("SSE Server berjalan di port 8080"));
```

---

## 10. Practical Example: Implementasi WebSocket Ping-Pong Heartbeat

Koneksi WebSocket yang tidak memiliki aktivitas traffic seringkali diputus secara diam-diam oleh NAT gateway atau firewall router (*stale connection*). Mekanisme heartbeat wajib diimplementasikan:

```javascript
// Konsep Pola Heartbeat Backend
const WebSocket = require('ws');
const wss = new WebSocket.Server({ port: 8081 });

wss.on('connection', (ws) => {
  ws.isAlive = true;

  // Tanggapi respons pong dari client
  ws.on('pong', () => {
    ws.isAlive = true;
  });

  ws.on('message', (message) => {
    console.log(`Pesan diterima: ${message}`);
    ws.send(`Echo: ${message}`);
  });
});

// Interval pemeriksaan liveness setiap 30 detik
const interval = setInterval(() => {
  wss.clients.forEach((ws) => {
    if (ws.isAlive === false) {
      console.log("Client mati terdeteksi! Memutus socket zombie...");
      return ws.terminate();
    }
    ws.isAlive = false;
    ws.ping(); // Kirim frame biner Ping (Opcode 0x9)
  });
}, 30000);
```

---

## 11. Real World Example: Mengapa OpenAI Menggunakan SSE, Bukan WebSocket
Ketika OpenAI merilis antarmuka ChatGPT untuk menghasilkan teks berbasis Large Language Model (LLM), mereka memilih **Server-Sent Events (SSE)** alih-alih WebSocket:
1. **Pola Komunikasi Alami**: Interaksi prompt-to-response adalah model asimetris: Pengguna mengirim 1 prompt utuh (via standar HTTP POST), dan server membalas dengan ratusan token yang mengalir bertahap (*Stream Response*).
2. **Kesesuaian dengan Infrastruktur Edge**: SSE adalah protokol HTTP standar. Layanan seperti Cloudflare CDN, AWS CloudFront, dan API Gateway dapat me-route, membatasi laju (*rate-limiting*), dan menginspeksi traffic SSE tanpa memerlukan penanganan connection state yang rumit seperti pada WebSocket.
3. **Automatic Reconnection & Resilience**: Jika koneksi seluler smartphone pengguna terputus sesaat, browser otomatis menyambung kembali ke backend dengan header `Last-Event-ID`.

---

## 12. Trade-offs

| Kriteria | HTTP/2 | HTTP/3 (QUIC) | WebSockets | Server-Sent Events (SSE) |
|---|---|---|---|---|
| **Kompleksitas Backend** | Rendah (Didukung webserver modern) | Menengah (Memerlukan dukungan kernel UDP) | Tinggi (Stateful connection management) | Sangat Rendah (HTTP biasa) |
| **Skalabilitas Load Balancer** | Stateless / L7 Balancing mudah | Stateless L7 (menggunakan Connection ID) | Rumit (Sticky sessions / Redis Adapter) | Mudah (Sama seperti HTTP standar) |
| **Overhead Framing** | Minimal (HPACK compression) | Sangat Minimal (QPACK compression) | 2-10 byte per frame | Header teks HTTP |
| **Kebutuhan Duplex** | Half-duplex per stream | Half-duplex per stream | **Murni Full-Duplex** | Unidirectional (Server ke Client) |

---

## 13. When To Use
- Gunakan **HTTP/2** atau **HTTP/3** untuk seluruh RESTful API dan arsitektur gRPC backend antar-microservice.
- Gunakan **WebSockets** untuk aplikasi kolaboratif interaktif multi-user (seperti Google Docs / Figma live editing), game multiplayer berbasis browser, atau ruang obrolan chatting instan.
- Gunakan **Server-Sent Events (SSE)** untuk streaming token Generative AI (LLM), pemantauan log server real-time, feed harga cryptocurrency/saham, atau notifikasi push dashboard.

---

## 14. When NOT To Use
- **JANGAN** menggunakan WebSockets hanya untuk menampilkan badge notifikasi unread email (gunakan SSE atau push notification service).
- **JANGAN** menggunakan HTTP/1.1 tanpa Keep-Alive di lingkungan microservice ber-throughput tinggi.
- Hindari SSE jika aplikasi membutuhkan pengiriman data biner mentah frekuensi tinggi dari client ke server.

---

## 15. Common Mistakes
1. **Buffer Bloat pada SSE**: Lupa melakukan flushing pada buffer middleware kompresi (seperti `gzip`), sehingga data SSE tertahan di memori server dan baru dikirim sekaligus ke browser saat stream selesai, merusak efek streaming real-time.
2. **Koneksi Zombie WebSocket**: Tidak mengimplementasikan mekanisme *ping-pong heartbeat*. Ketika kabel LAN client dicabut, server mengira client masih terhubung dan terus menyimpan socket di memori hingga server kehabisan RAM.
3. **Mengabaikan Batas Koneksi HTTP/1.1 di Browser**: Browser membatasi maksimal 6 koneksi HTTP/1.1 per domain. Jika pengguna membuka 6 tab yang masing-masing menjalankan SSE di HTTP/1.1, tab ke-7 akan macet total. Solusi: Gunakan HTTP/2 agar semua SSE berjalan dalam 1 koneksi multiplexed!

---

## 16. Best Practices
- **Must Have**: Matikan buffering proxy pada NGINX untuk endpoint SSE:
  ```nginx
  proxy_set_header Connection '';
  proxy_http_version 1.1;
  chunked_transfer_encoding off;
  proxy_buffering off;
  proxy_cache off;
  ```
- **Recommended**: Terapkan mekanisme autentikasi token JWT pada saat handshake WebSocket awal (lewat query param atau header cookie) sebelum upgrade diizinkan.
- **Advanced**: Implementasikan **Redis Pub/Sub** atau **NATS** sebagai message backbone di belakang cluster WebSocket server agar pesan dapat di-broadcast ke seluruh pengguna di lintas server instance (*horizontal scaling*).
- **Avoid**: Mengirimkan payload JSON berukuran megabyte di dalam satu frame WebSocket.

---

## 17. Troubleshooting Guide
```
Masalah: Koneksi WebSocket gagal terbentuk dan mengembalikan HTTP 400 Bad Request atau 502 Bad Gateway di belakang NGINX.
Penyebab : NGINX secara default menghapus header 'Upgrade' dan 'Connection' saat mem-proxy request.
Diagnosa : Periksa header yang diterima oleh backend server:
           curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" http://api.perusahaan.com/ws
Solusi   : Tambahkan konfigurasi berikut pada blok NGINX location:
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection "upgrade";

Masalah: EventSource SSE di browser client terus-menerus melakukan reconnect setiap 60 detik.
Penyebab : Load balancer (seperti AWS ALB) memiliki idle timeout default 60 detik dan memutus koneksi karena server tidak mengirim data.
Solusi   : Kirimkan komentar kosong heartbeat (contoh: ":keepalive\n\n") setiap 15-30 detik dari server untuk menjaga koneksi tetap aktif.
```

---

## 18. Exercise
1. Bangun server HTTP sederhana di Node.js atau bahasa pilihan Anda yang melayani endpoint SSE `/prices`.
2. Kirimkan perubahan harga dummy setiap 1 detik dalam format JSON standar SSE.
3. Buka browser dan gunakan JavaScript `new EventSource('/prices')` untuk mendengarkan event tersebut dan tampilkan data di console.

---

## 19. Challenge
Rancang arsitektur WebSocket cluster yang mampu menangani **1.000.000 koneksi concurrent** (simultan) di platform live streaming:
1. Hitung kebutuhan memori RAM di level kernel Linux (`wmem`, `rmem`, socket file descriptors).
2. Rancang arsitektur pub/sub terdistribusi (menggunakan Redis Cluster atau Apache Kafka) untuk menyebarkan pesan obrolan ke jutaan pengguna di 20 instance server backend.
3. Jelaskan strategi graceful reconnect saat terjadi deployment rilis server baru tanpa memicu serangan *Thundering Herd*!

---

## 20. Summary
Evolusi protokol dari HTTP/1.1 menuju HTTP/2 dan HTTP/3 menghapuskan keterbatasan performa masa lalu dengan menghadirkan multiplexing biner dan ketahanan transportasi QUIC. Sementara itu, pemilihan cerdas antara WebSockets (untuk komunikasi dua arah interaktif) dan Server-Sent Events (untuk streaming data terdistribusi dan token AI) adalah pondasi krusial bagi arsitektur backend modern berkinerja tinggi.

---
[⬅️ Module 01: Internet, TCP, & TLS 1.3](./Module-01-Bagaimana-Internet-Bekerja-IP-DNS-TCP-UDP-TLS.md) | [📋 Silabus Induk](../README.md) | [BAB 01 Quiz & Challenge ➡️](./BAB-01-Quiz-dan-Challenge.md)
---
