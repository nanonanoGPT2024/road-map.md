# Bab 01: Fondasi Arsitektur Web & Protokol Komunikasi Modern
## Modul 01: Arsitektur Client-Server, HTTP/HTTPS Protocol Mechanics, dan Dekonstruksi Siklus Hidup Request-Response Modern

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
- **Menganalisis (C4)** siklus hidup *end-to-end* request HTTP dari resolusi DNS, *TCP/TLS handshake*, transmisi data, hingga rendering visual pada browser (*Critical Rendering Path*).
- **Mendiagnosis (C4)** anomali latensi jaringan dan *bottleneck* performa pada transport layer dan application layer menggunakan *network profiler* dan CLI tools.
- **Mengonstruksi (C3)** implementasi server HTTP berbasis soket TCP murni (level transport) tanpa framework komersial untuk membuktikan mekanika dasar framing protokol web.
- **Mengevaluasi (C5)** trade-off arsitektural antara protokol HTTP/1.1, HTTP/2, dan HTTP/3 (QUIC) serta pengaruhnya terhadap desain sistem aplikasi Full Stack skala enterprise.
- **Memitigasi (C3)** celah keamanan fundamental pada layer transport dan HTTP headers (*request smuggling*, *slowloris*, *protocol injection*).

---

### 2. Concept Definition
Arsitektur Web Full Stack modern adalah sistem terdistribusi heterogen berbasis model **Client-Server** yang beroperasi di atas protokol jaringan bertingkat (OSI/Internet Protocol Suite). Inti dari operasi Full Stack terletak pada kemampuan menjembatani interaksi antara komponen eksekusi terdistribusi:

1. **The Client (User Agent):** Sistem runtime deterministik terisolasi (contoh: V8 Engine + Blink/Gecko pada browser atau VM seluler) yang bertanggung jawab atas kompilasi UI, *state machine* presentasi, eksekusi JavaScript, dan orkestrasi pemanggilan network remote.
2. **The Transport & Application Wire Protocol (TCP/IP, TLS, HTTP):** Spesifikasi mekanis transmisi data biner/teks yang menjamin delivery, integritas, enkripsi, dan negosiasi kapabilitas komputasi antar entitas yang terpisah secara fisik.
3. **The Server (Application Runtime):** Lingkungan pemrosesan paralel asinkron (Node.js, Go, Rust, JVM) yang mengeksekusi logika bisnis, mengelola konektivitas basis data, serta menjamin konsistensi *state* dan *security boundary*.

Secara formal, **HTTP (Hypertext Transfer Protocol)** adalah protokol aplikasi *stateless*, berbasis *message-passing*, dan berorientasi *request-response* yang ditransmisikan melalui protokol transport yang andal (*reliable stream-oriented* seperti TCP, atau *multiplexed datagrams* seperti QUIC/UDP).

---

### 3. Why This Concept Matters
Pemahaman dangkal terhadap arsitektur web menyebabkan engineer memperlakukan sistem jaringan sebagai "pipa abstrak yang instan dan tanpa biaya" (*Fallacies of Distributed Computing*). Pada skala produksi dengan throughput tinggi, ketidaktahuan akan protokol menyebabkan kegagalan sistemik yang masif:

- **Latency Amplification:** Kurangnya pemahaman tentang *TCP Slow Start* dan *TLS Handshake Round-Trip Times (RTT)* menyebabkan arsitektur SPA (*Single Page Application*) modern memicu lusinan *network waterfall chains* yang menghancurkan metrik Core Web Vitals (misal: LCP melonjak > 4 detik).
- **Connection Starvation & Socket Exhaustion:** Kesalahan konfigurasi HTTP Keep-Alive, reverse proxy connection pool, dan *file descriptor limits* pada server runtime dapat melumpuhkan seluruh kluster komputasi saat terjadi lonjakan trafik mikro (*traffic spikes*).
- **Silent Security Breaches:** Kegagalan mengelola parsing batas payload HTTP (*Content-Length* vs *Transfer-Encoding: chunked*) membuka celah *HTTP Request Smuggling*, memungkinkan penyerang membajak session user lain di level reverse proxy.

---

### 4. What It Is vs What It Isn't

| Dimensi | Konsep Nyata (What It Is) | Miskonsepsi Umum (What It Isn't) |
| :--- | :--- | :--- |
| **HTTP Protocol** | Protokol transport pesan berbasis framing (teks pada HTTP/1.1, biner pada H2/H3) di atas socket byte-stream. | Objek JSON sederhana yang dikirimkan secara otomatis via function call `fetch()`. |
| **Client-Server** | Asinkron, terdistribusi temporal, boundary sistem tanpa trust implisit di mana server memegang validasi mutlak. | Dua folder kode (`frontend` dan `backend`) di dalam monorepo yang langsung tersambung otomatis. |
| **Connection State** | Socket stateful berbasis TCP (ESTABLISHED) yang dipertahankan di level OS kernel layer transport. | Protokol HTTP itu sendiri yang stateful (HTTP tetap *stateless* di level application context). |
| **Web Rendering** | Pipeline rendering deterministik non-linier: Parsing HTML $\to$ DOM $\to$ CSSOM $\to$ Render Tree $\to$ Layout $\to$ Paint $\to$ Composite. | Proses instan seketika saat data respons HTTP selesai di-download oleh browser. |

---

### 5. How It Works: Architectural Deep-Dive

Siklus hidup sebuah request web dari penekanan tombol 'Enter' pada address bar hingga pixel pertama tampil di layar (*First Contentful Paint*) melewati 4 fase kritis:

```
[User Input: URL]
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│ 1. RESOLUSI JARINGAN (DNS Resolution Architecture)           │
│ Browser Cache ─► OS Cache ─► Router Cache ─► Resolver (ISP) │
│                                                     │       │
│ Root Server (.) ◄── TLD (.com) ◄── Authoritative NS ┘       │
└─────────────────────────────────────────────────────────────┘
       │
       ▼  IP Address Didapatkan
┌─────────────────────────────────────────────────────────────┐
│ 2. ESTABILISASI KONEKSI (Transport & Security Layer)        │
│                                                             │
│ [TCP 3-Way Handshake]: SYN ──► SYN-ACK ──► ACK              │
│                                                             │
│ [TLS 1.3 Handshake]: ClientHello + Key Share                │
│                      ◄── ServerHello + Key Share + Cert     │
│                      Client Finished ──► [Encrypted Channel]│
└─────────────────────────────────────────────────────────────┘
       │
       ▼  Secure Stream Terbuka
┌─────────────────────────────────────────────────────────────┐
│ 3. PERTUKARAN DATA HTTP (Application Protocol Mechanics)    │
│ Client: Menulis Request Headers + Payload ke Buffer Soket   │
│ Jaringan: Segmentasi TCP Packet, Flow Control (CWND), ACK    │
│ Server OS: TCP Receive Window ──► Buffer Socket Runtime     │
│ Server App: HTTP Parsing (Header/Body) ──► Routing ──► Exec │
│ Server Response: 200 OK + Stream Body (Chunked / Static)    │
└─────────────────────────────────────────────────────────────┘
       │
       ▼  Byte Stream Diterima Client
┌─────────────────────────────────────────────────────────────┐
│ 4. CRITICAL RENDERING PATH (Browser Engine Processing)       │
│ Tokens ──► Nodes ──► DOM Tree                               │
│ Tokens ──► Nodes ──► CSSOM Tree ──► Render Tree             │
│                                            │                │
│ Composite ◄── Paint ◄── Layout (Reflow) ◄──┘                │
└─────────────────────────────────────────────────────────────┘
```

#### A. Mekanika Resolusi DNS
1. Browser mengecek cache lokal (*browser DNS cache*). Jika *miss*, memanggil fungsi kernel resolver OS via API `getaddrinfo`.
2. Jika *miss* pada OS cache / `hosts` file, query UDP Port 53 diteruskan ke Recursive Resolver (ISP atau public DNS seperti 1.1.1.1).
3. Resolver melakukan iterasi rekursif:
   - Root Name Server (`.`)
   - TLD Name Server (`.com`, `.id`)
   - Authoritative Name Server milik domain target, mengembalikan DNS Record (A, AAAA, CNAME).

#### B. Transport & Security Layer Handshake
1. **TCP 3-Way Handshake:**
   - Client mengirim paket `SYN` (Sequence Number $= X$).
   - Server merespons `SYN-ACK` (Sequence Number $= Y$, Acknowledgment $= X + 1$).
   - Client membalas `ACK` (Sequence Number $= X + 1$, Acknowledgment $= Y + 1$).
2. **TLS 1.3 Negotiation:**
   - Berbeda dari TLS 1.2 yang membutuhkan 2 RTT, TLS 1.3 mereduksinya menjadi **1 RTT**.
   - `ClientHello` membawa cipher suites yang didukung beserta parameter Diffie-Hellman Key Exchange (*Key Share*).
   - Server membalas `ServerHello` dengan konfirmasi Key Share, sertifikat server, dan tanda tangan digital.
   - Sesi terenkripsi langsung terbentuk, request HTTP pertama dapat dikirimkan bersamaan (*0-RTT* pada sesi resumption via *Early Data*).

#### C. Demultiplexing & OS Kernel Buffer
Pada sisi server, network interface card (NIC) menerima frame Ethernet, memvalidasi checksum, memicu Interrupt Request (IRQ), memindahkan payload ke kernel memory (*sk_buff*), dan memasukkannya ke socket *receive queue*. Runtime aplikasi (misal: Node.js epoll loop) dibangunkan oleh event kernel untuk membaca stream byte mentah tersebut dan memparsingnya sesuai spesifikasi RFC 9112 / RFC 9113.

#### D. Critical Rendering Path
Saat byte HTML pertama tiba di browser via streaming:
- **Lexical Analysis & Tokenization:** Mengubah raw stream menjadi tag tokens (`StartTag: html`, `StartTag: body`, dll).
- **DOM Construction:** Node dihubungkan membentuk Tree hierarchical.
- **CSSOM Construction:** Tokenisasi stylesheet eksternal dan inline `<style>`, menghitung kalkulasi spesifisitas gaya visual cascading.
- **Render Tree Execution:** Menggabungkan DOM dan CSSOM, mengabaikan node non-visual (`<head>`, elemen ber-`display: none`).
- **Layout (Reflow):** Menghitung geometri tepat, koordinat $X, Y$, serta lebar dan tinggi masing-masing node di dalam viewport browser.
- **Painting & Compositing:** Menggambar visual layer bitmap ke GPU VRAM untuk ditransfer langsung ke frame buffer monitor.

---

### 6. ASCII Architecture Diagram

Detail siklus request HTTP/1.1 vs HTTP/2 Multiplexing di atas transport level:

```
=== HTTP/1.1 Pipelining / Head-of-Line Blocking pada 1 Koneksi TCP ===

Client Buffer                                                     Server Socket
     │                                                                 │
     ├─── [Request 1: HTML] ──────────────────────────────────────────►│
     │    (Server memproses Request 1: 50ms)                           │
     ├─── [Request 2: CSS (Tertahan menunggu Resp 1)]                  │
     │                                                                 │
     │◄── [Response 1: HTML Selesai] ──────────────────────────────────┤
     │                                                                 │
     ├─── [Request 2: Dikirimkan Sekarang] ───────────────────────────►│
     │    (Server memproses Request 2: 10ms)                           │
     │◄── [Response 2: CSS Selesai] ───────────────────────────────────┤
     ▼                                                                 ▼
Total Latency = Sum(Network RTT) + Processing(Req 1) + Processing(Req 2)


=== HTTP/2 Binary Framing & Multiplexing pada 1 Koneksi TCP Tunggal ===

Client Buffer                                                     Server Socket
     │                                                                 │
     ├─── Stream 1, Frame HEADERS (Req 1: HTML) ──────────────────────►│
     ├─── Stream 3, Frame HEADERS (Req 2: CSS)  ──────────────────────►│
     ├─── Stream 5, Frame HEADERS (Req 3: API)  ──────────────────────►│
     │                                                                 │
     │◄── Stream 3, Frame DATA (CSS Selesai lebih awal) ───────────────┤
     │◄── Stream 1, Frame DATA (HTML Chunk 1) ─────────────────────────┤
     │◄── Stream 5, Frame DATA (API Response) ─────────────────────────┤
     │◄── Stream 1, Frame DATA (HTML Chunk 2 - Selesai) ───────────────┤
     ▼                                                                 ▼
Total Latency = Max(Network RTT + Processing) -> Non-blocking Interleaved Concurrency
```

---

### 7. Progressive Code Examples: Minimal / Raw Implementation

Implementasi server HTTP/1.1 murni dari level socket TCP mentah menggunakan pustaka `net` standar Node.js. Kode ini mengilustrasikan framing data teks mentah tanpa bantuan layer abstraksi HTTP module Node.js.

```javascript
// raw-http-server.js
// Implementasi HTTP/1.1 Server berbasis Raw TCP Socket (Transport Layer Level)
const net = require('node:net');

const PORT = 8080;
const CRLF = '\r\n';

const server = net.createServer((socket) => {
  // Tangani event pembacaan stream biner dari socket
  socket.on('data', (chunk) => {
    const rawRequest = chunk.toString('utf-8');
    
    // Parsing manual line-by-line protokol HTTP
    const lines = rawRequest.split(CRLF);
    const requestLine = lines[0]; // Format: METHOD PATH VERSION
    const [method, path, version] = requestLine.split(' ');

    console.log(`[RAW TCP] Inbound Request: ${method} ${path} via ${version}`);

    // Parsing HTTP Headers menjadi Hash Map
    const headers = {};
    let headerIdx = 1;
    while (lines[headerIdx] && lines[headerIdx] !== '') {
      const [key, ...values] = lines[headerIdx].split(':');
      headers[key.trim().toLowerCase()] = values.join(':').trim();
      headerIdx++;
    }

    // Bangun Response Body secara terisolasi
    const payload = JSON.stringify({
      message: 'Halo dari Socket TCP Mentah!',
      pathReceived: path,
      methodReceived: method,
      clientHeaders: headers,
      timestamp: new Date().toISOString()
    });

    const payloadBuffer = Buffer.from(payload, 'utf-8');

    // Konstruksi HTTP Response Envelope mentah
    // WAJIB menyertakan Content-Length agar HTTP client tidak hanging
    const rawResponse = 
      'HTTP/1.1 200 OK' + CRLF +
      'Content-Type: application/json; charset=UTF-8' + CRLF +
      `Content-Length: ${payloadBuffer.length}` + CRLF +
      'Connection: close' + CRLF + // Menutup koneksi TCP setelah request selesai
      CRLF; // Double CRLF menandakan akhir dari header HTTP

    // Tulis Header ke TCP Socket Stream
    socket.write(rawResponse);
    // Tulis Body Payload ke TCP Socket Stream
    socket.write(payloadBuffer);
    // Flush dan terminasi socket TCP
    socket.end();
  });

  socket.on('error', (err) => {
    console.error(`[SOCKET ERROR]: ${err.message}`);
  });
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`Low-level TCP HTTP Server berjalan di port ${PORT}`);
});
```

---

### 8. Progressive Code Examples: Practical Implementation

Implementasi server Node.js HTTP/1.1 native yang menangani content negotiation, parsing streaming body dengan batas memory allocation (*backpressure & payload size limiting*), serta error boundary parsing.

```typescript
// practical-server.ts
import http, { IncomingMessage, ServerResponse } from 'node:http';
import { StringDecoder } from 'node:string_decoder';

const MAX_PAYLOAD_BYTES = 1024 * 1024; // 1 Megabyte hard limit

interface ParsedRequest {
  path: string;
  method: string;
  headers: http.IncomingHttpHeaders;
  body: unknown;
}

function parseJsonBody(req: IncomingMessage, maxBytes: number): Promise<unknown> {
  return new Promise((resolve, reject) => {
    let totalBytesRead = 0;
    const decoder = new StringDecoder('utf-8');
    let rawBody = '';

    req.on('data', (chunk: Buffer) => {
      totalBytesRead += chunk.length;

      // Guard pattern: Mencegah serangan Memory Exhaustion (Denial of Service)
      if (totalBytesRead > maxBytes) {
        req.destroy(new Error('PAYLOAD_TOO_LARGE'));
        return;
      }

      rawBody += decoder.write(chunk);
    });

    req.on('end', () => {
      rawBody += decoder.end();

      if (!rawBody || rawBody.trim() === '') {
        return resolve({});
      }

      try {
        const parsed = JSON.parse(rawBody);
        resolve(parsed);
      } catch (err) {
        reject(new Error('INVALID_JSON_BODY'));
      }
    });

    req.on('error', (err) => reject(err));
  });
}

const server = http.createServer(async (req: IncomingMessage, res: ServerResponse) => {
  const parsedUrl = new URL(req.url || '/', `http://${req.headers.host}`);
  const method = (req.method || 'GET').toUpperCase();

  // Content Negotiation Guard
  const acceptHeader = req.headers['accept'] || '*/*';
  const acceptsJson = acceptHeader.includes('application/json') || acceptHeader.includes('*/*');

  if (!acceptsJson) {
    res.writeHead(406, { 'Content-Type': 'text/plain' });
    res.end('Not Acceptable: Application only serves application/json');
    return;
  }

  // Routing Handler
  if (parsedUrl.pathname === '/api/v1/resource' && method === 'POST') {
    try {
      const body = await parseJsonBody(req, MAX_PAYLOAD_BYTES);

      const responsePayload = JSON.stringify({
        status: 'success',
        receivedData: body,
        meta: {
          requestId: req.headers['x-request-id'] || 'generated-uuid-example',
          contentType: req.headers['content-type']
        }
      });

      res.writeHead(201, {
        'Content-Type': 'application/json; charset=utf-8',
        'Cache-Control': 'no-store, no-cache, must-revalidate',
        'X-Content-Type-Options': 'nosniff'
      });
      res.end(responsePayload);
    } catch (error: any) {
      if (error.message === 'PAYLOAD_TOO_LARGE') {
        res.writeHead(413, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Payload size exceeds limit of 1MB' }));
      } else if (error.message === 'INVALID_JSON_BODY') {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Malformed JSON syntax' }));
      } else {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Internal Server Error' }));
      }
    }
  } else {
    res.writeHead(404, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Endpoint Not Found' }));
  }
});

server.listen(3000, () => {
  console.log('Production-patterned native HTTP server operational on port 3000');
});
```

---

### 9. Progressive Code Examples: Enterprise/Production-Grade

Implementasi HTTP Client/Server boundary berskala enterprise menggunakan Node.js dengan connection pooling, socket-level timeouts (*keep-alive, headers timeout, request timeout*), circuit protection, dan graceful shutdown primitives.

```typescript
// enterprise-http-orchestrator.ts
import http from 'node:http';
import https from 'node:https';
import { pipeline } from 'node:stream/promises';

// 1. Connection Pool & Agent Hardening untuk Downstream Consumption
const secureOutboundAgent = new https.Agent({
  keepAlive: true,
  keepAliveMsecs: 30000, // Menjaga TCP socket aktif selama 30 detik
  maxSockets: 100,       // Maksimum koneksi paralel per host
  maxFreeSockets: 20,    // Maksimum pool idle sockets
  timeout: 5000          // Socket connection timeout
});

// 2. HTTP Server Engine Initialization
const appServer = http.createServer({
  keepAlive: true,
  keepAliveTimeout: 61000, // Wajib LEBIH BESAR dari AWS ALB / NGINX keepalive (umumnya 60s)
  headersTimeout: 65000,   // Wajib LEBIH BESAR dari keepAliveTimeout untuk mitigasi Race Conditions
  maxHeaderSize: 16384     // Batasi header maksimum 16KB untuk mencegah Memory Exhaustion
});

// 3. Central Application Router Logic
appServer.on('request', async (req: http.IncomingMessage, res: http.ServerResponse) => {
  const startTime = process.hrtime.bigint();

  // Definisikan timeout request eksplisit (Anti-Hanging Protection)
  req.setTimeout(15000, () => {
    res.writeHead(504, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Gateway Timeout: Processing exceeded 15000ms' }));
    req.destroy();
  });

  if (req.url === '/healthz' && req.method === 'GET') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'UP', uptime: process.uptime() }));
    return;
  }

  if (req.url === '/proxy-outbound' && req.method === 'GET') {
    try {
      // Pemanggilan aman ke microservice downstream via pool agent
      const upstreamReq = https.request(
        'https://httpbin.org/delay/1',
        {
          method: 'GET',
          agent: secureOutboundAgent,
          timeout: 4000
        },
        (upstreamRes) => {
          res.writeHead(upstreamRes.statusCode || 502, {
            'Content-Type': upstreamRes.headers['content-type'] || 'application/json',
            'X-Upstream-Latency-MS': `${Number(process.hrtime.bigint() - startTime) / 1e6}ms`
          });
          // Pipe data stream secara aman tanpa buffering di memori runtime
          upstreamRes.pipe(res);
        }
      );

      upstreamReq.on('timeout', () => {
        upstreamReq.destroy(new Error('UPSTREAM_SOCKET_TIMEOUT'));
      });

      upstreamReq.on('error', (err) => {
        if (!res.headersSent) {
          res.writeHead(502, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: 'Bad Gateway: Upstream Unreachable', detail: err.message }));
        }
      });

      upstreamReq.end();
    } catch (error) {
      if (!res.headersSent) {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Fatal Execution Failure' }));
      }
    }
  } else {
    res.writeHead(404, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Resource Not Found' }));
  }
});

// 4. Graceful Shutdown Controller (Mencegah abrupt connection termination)
function initiateGracefulShutdown(signal: string) {
  console.log(`Menerima sinyal ${signal}. Memulai Graceful Shutdown sequence...`);

  // Menolak request baru yang masuk
  appServer.close((err) => {
    if (err) {
      console.error('Error saat menutup HTTP server:', err);
      process.exit(1);
    }
    console.log('HTTP Server berhasil ditutup. Semua socket pasif telah didestruksi.');
    
    // Hancurkan pool koneksi agent outbound
    secureOutboundAgent.destroy();
    process.exit(0);
  });

  // Paksa terminasi jika downstream/koneksi aktif tidak selesai dalam window waktu toleransi
  const forceKillTimer = setTimeout(() => {
    console.error('Gagal menyelesaikan pending request dalam 10s. Force exit.');
    process.exit(1);
  }, 10000);

  forceKillTimer.unref(); // Membiarkan runtime exit jika koneksi selesai secara alami
}

process.on('SIGTERM', () => initiateGracefulShutdown('SIGTERM'));
process.on('SIGINT', () => initiateGracefulShutdown('SIGINT'));

appServer.listen(8080, () => {
  console.log('Enterprise HTTP Cluster Node online pada port 8080. Process PID:', process.pid);
});
```

---

### 10. Trade-offs and Design Decisions

Tinjauan performa dan arsitektur antar-versi protokol aplikasi web:

| Parameter Evaluasi | HTTP/1.1 | HTTP/2 | HTTP/3 (QUIC) |
| :--- | :--- | :--- | :--- |
| **Transport Layer** | TCP murni | TCP murni | UDP (QUIC Layer) |
| **Connection Setup** | 1 RTT (TCP) + 1-2 RTT (TLS) | 1 RTT (TCP) + 1-2 RTT (TLS) | 0-1 RTT (QUIC + TLS 1.3 Terintegrasi) |
| **Multiplexing** | Tidak ada (Perlu Multiple TCP Connections / Max 6 per domain) | Ya (Multiplexed Streams di atas 1 TCP socket) | Ya (Multiplexed Streams independen via UDP Datagrams) |
| **Head-of-Line (HoL) Blocking** | Terjadi di **Layer Aplikasi** dan **Layer Transport** | Terjadi di **Layer Transport** (Packet loss TCP membekukan seluruh streams) | **Eliminasi Total** (Packet loss pada satu stream tidak menghentikan stream lain) |
| **Header Compression** | Tidak ada (Karakter teks mentah berulang) | HPACK (Kamus statis & dinamis biner) | QPACK (Non-blocking, dioptimasi untuk out-of-order execution) |
| **Beban CPU Runtime** | Sangat Rendah (Parsing teks primitif) | Sedang (Framing biner & kalkulasi HPACK state) | Tinggi (Enkripsi paket per datagram di kernel/user space UDP) |
| **Kesesuaian Kasus** | Internal LAN / Service-to-Service performa konstan | Web Browsing umum via broadband stabil | Jaringan seluler tidak stabil (*lossy networks* / sering ganti IP) |

---

### 11. Common Pitfalls & Anti-Patterns

| Simptom Masalah | Akar Masalah (Root Cause) | Dampak Kegagalan Produksi | Solusi Remediasi Rekayasa |
| :--- | :--- | :--- | :--- |
| Error `502 Bad Gateway` sporadis saat load stabil | `keepAliveTimeout` Node.js **lebih rendah** daripada timeout Keep-Alive reverse proxy (NGINX/AWS ALB). | Reverse proxy mengirim data ke koneksi TCP yang sedang ditutup sepihak oleh runtime Node.js. | Konfigurasi runtime `keepAliveTimeout = 61000ms`, pastikan selalu lebih besar dari ALB (60000ms). |
| Server crash dengan `JavaScript heap out of memory` | Membaca HTTP Request Body menggunakan string concat besar tanpa streaming atau byte counter. | Buffer overflow DoS saat ada user jahat mengunggah payload 500MB via endpoint POST. | Terapkan hard limit size guard pada chunk handler stream sebelum data di-parse. |
| Browser membeku (*jank*) selama > 1.5 detik | Memuat script JavaScript non-defer/non-async di `<head>` HTML dokumen. | Browser memblokir HTML parsing engine untuk mengunduh dan mengeksekusi script secara sinkron. | Gunakan atribut `defer` atau `type="module"` pada script tags eksternal. |
| Socket descriptor exhaustion (`EMFILE`) | Membuka koneksi `http.request()` baru pada setiap cycle tanpa mendefinisikan `http.Agent({ keepAlive: true })`. | Pool koneksi OS habis karena socket tertahan di state `TIME_WAIT` (terbatas ~65,535 ephemeral ports). | Gunakan shared connection pool via persistent agent singleton di seluruh instance HTTP request. |

---

### 12. Best Practices & Production Checklist

- [ ] **Protokol Keep-Alive Tersinkronisasi:** Pastikan `Server.keepAliveTimeout` runtime lebih besar minimal 1-2 detik daripada idle timeout upstream gateway/load balancer.
- [ ] **Alokasi Timeout Berlapis:** Tetapkan `headersTimeout`, `requestTimeout`, dan upstream `socket.setTimeout()` secara eksplisit pada setiap node runtime.
- [ ] **Payload Sanitization & Boundary:** Pasang guard size limit payload (misal: 1MB untuk JSON, 10MB untuk binary) sebelum stream dibaca oleh deserializer.
- [ ] **Header Hardening Standar Produksi:**
  - Sertakan `Strict-Transport-Security: max-age=63072000; includeSubDomains; preload` (HSTS).
  - Sertakan `X-Content-Type-Options: nosniff` untuk mencegah MIME-type sniffing.
  - Sertakan `Content-Security-Policy` yang ketat tanpa mengizinkan `unsafe-eval`.
- [ ] **Optimasi Transport:** Aktifkan kompresi HTTP respons dinamis (`brotli`, `gzip`) hanya untuk payload teks berukuran $> 1KB$. Hindari kompresi file biner/gambar (hanya membuang CPU server).
- [ ] **Graceful Drain Listener:** Ikat event OS `SIGTERM` dan `SIGINT` untuk menghentikan penerimaan request baru via `server.close()` sembari menuntaskan *in-flight requests*.

---

### 13. Real-World Case Studies: Failure Story

**Konteks Insiden:** Sebuah platform tiket daring berskala unicorn mengalami kelumpuhan total (*cascade crash*) pada sistem backend checkout saat penjualan tiket konser global dimulai.

**Mekanisme Kegagalan:**
1. Frontend arsitektur Single Page Application (SPA) memicu 8 request parallel secara serentak (`fetch`) saat user mengklik halaman reservasi.
2. Server backend diorkestrasi menggunakan Node.js di belakang AWS ALB.
3. Node.js backend default runtime memiliki `keepAliveTimeout: 5000ms`, sementara AWS ALB dikonfigurasi dengan `Idle Timeout: 60000ms`.
4. Pada kondisi lonjakan trafik mencapai 40.000 req/sec, terjadi anomali **Race Condition TCP Reset**: ALB memilih koneksi idle yang ada di pool untuk menyalurkan traffic user, namun pada milidetik yang sama, Node.js mengirimkan paket `TCP FIN` untuk menutup socket karena timeout 5 detiknya terpenuhi.
5. ALB menerima paket `FIN` saat sedang mentransmisikan data request baru, menyebabkan ALB memutus paksa koneksi dan mengembalikan respons `502 Bad Gateway` ke ratusan ribu pengguna secara instan.
6. User yang panik menekan refresh browser berkali-kali (*retry storm*), menyebabkan volume request berlipat ganda hingga socket descriptor pada cluster kernel Linux habis (*EMFILE* socket exhaustion). Sistem tumbang total selama 47 menit.

**Resolusi:**
- Menyesuaikan `keepAliveTimeout` backend Node.js menjadi `65000ms` dan `headersTimeout` ke `66000ms`.
- Menambahkan exponential backoff dan jitter pada API retry client.

---

### 14. Real-World Case Studies: Success Story

**Konteks Transformasi:** Perusahaan media global mengonversi situs portal beritanya dari tumpukan HTTP/1.1 monolitik menjadi HTTP/2 Edge Delivery Network dengan optimasi Critical Rendering Path.

**Strategi Optimasi Teknis:**
1. Mengubah struktur aset CSS yang masif (1.2MB tunggal) menjadi *critical inline CSS* khusus area *Above-the-Fold*, serta me-load sisanya secara asinkron (`media="print"` onload pattern).
2. Memigrasi gateway ke HTTP/2 dengan persistent single-connection multiplexing ke Edge Cloudflare.
3. Mengganti domain sharding lama (`assets1.domain.com`, `assets2.domain.com`) kembali menjadi domain root tunggal guna meniadakan alokasi biaya DNS Lookup, TCP Handshake, dan TLS Handshake redundan (menghemat ~300ms per origin sharding).
4. Menerapkan instruksi `Link: </style.css>; rel=preload; as=style` pada header HTTP.

**Hasil Terukur:**
- **Time to First Byte (TTFB):** Turun dari 450ms menjadi **120ms** di tingkat global.
- **Largest Contentful Paint (LCP):** Berkurang drastis dari 4.8 detik menjadi **1.1 detik** (Peningkatan 77%).
- **Server CPU Consumption:** Penggunaan CPU backend turun **35%** karena berkurangnya overhead pembuatan socket koneksi TCP/TLS baru berkat reuse multiplexing HTTP/2.

---

### 15. Edge Cases & Boundary Conditions

1. **Slowloris Attacks (Slow HTTP Headers):**
   - *Boundary:* Klien membuka koneksi TCP dan mengirimkan header HTTP byte-per-byte setiap beberapa detik tanpa pernah menyelesaikan delimiter `\r\n\r\n`.
   - *Mitigasi:* Gunakan batas waktu agresif penerimaan header via `headersTimeout` (maksimal 5-10 detik untuk first byte header) dan terminasi socket jika buffer parsial tidak rampung.

2. **Large Cookie Boundary Exhaustion:**
   - *Boundary:* Akumulasi cookie klien melampaui alokasi limit header internal web server (contoh default Node.js: 16KB).
   - *Mitigasi:* Server akan merespons status code `431 Request Header Fields Too Large`. Hindari penyimpanan token sesi (JWT) raksasa di dalam HTTP Cookie.

3. **Client Abrupt Disconnection During Long Compute:**
   - *Boundary:* Klien menutup browser saat server sedang mengeksekusi kueri database berat selama 10 detik.
   - *Mitigasi:* Server harus mendengarkan event socket close (`req.on('close')`) dan segera membatalkan transaksi downstream menggunakan mekanisme `AbortController` untuk menghemat resource thread pool dan memory backend.

---

### 16. Performance Optimization & Benchmarking

Untuk mengukur kapasitas throughput koneksi HTTP dan latensi under-concurrency, gunakan tool load-testing modern `autocannon` (HTTP/1.1 benchmark) atau `h2load` (HTTP/2 benchmark).

#### Menjalankan Stress Test
Jalankan tes konkurensi 100 koneksi simultan selama 30 detik:

```bash
# Instalasi benchmarking tool
npm install -g autocannon

# Eksekusi stress-test terhadap endpoint
autocannon -c 100 -d 30 -p 10 http://127.0.0.1:8080/healthz
```

#### Monitoring Status Socket Kernel Linux
Pantau jumlah soket yang berada dalam state `ESTABLISHED` dan `TIME_WAIT` pada operating system:

```bash
# Monitoring alokasi socket TCP pada OS
ss -s

# Monitoring status koneksi port 8080 secara detail
ss -tan state established '( dport = :8080 or sport = :8080 )' | wc -l
ss -tan state time-wait '( dport = :8080 or sport = :8080 )' | wc -l
```

#### Checklist Optimasi Performa
1. Aktifkan **TCP Fast Open (TFO)** pada kernel OS (`net.ipv4.tcp_fastopen = 3`) untuk memfasilitasi pengiriman data pada paket SYN pembuka.
2. Konfigurasikan **Epoll/Event Loop Utilization:** Jangan pernah memblokir Node.js Event Loop dengan CPU-bound heavy logic (seperti crypto synchronous atau enkripsi data masif di thread utama).

---

### 17. Security Considerations

Tiga vektor eksploitasi fundamental pada siklus request HTTP:

1. **HTTP Request Smuggling (HRS):**
   - *Mekanisme:* Terjadi ketidakselarasan parsing antara Front-End Proxy dan Back-End Server dalam memprioritaskan header `Content-Length` vs `Transfer-Encoding: chunked`.
   - *Mitigasi:* Gunakan HTTP/2 end-to-end dari Edge ke Origin (karena HTTP/2 berbasis biner frame yang memiliki panjang stream eksplisit sehingga mustahil di-smuggle). Nonaktifkan fallback ke `Transfer-Encoding` jika header `Content-Length` telah didefinisikan.

2. **CRLF Injection (HTTP Response Splitting):**
   - *Mekanisme:* Memasukkan karakter `\r\n` (Carriage Return Line Feed) dari user input ke dalam header kustom respons server, memungkinkan injeksi respons tiruan untuk phishing atau pemalsuan cache proxy.
   - *Mitigasi:* Sanitasi dan strip semua karakter `\r` dan `\n` pada nilai header sebelum runtime memanggil `setHeader()`.

3. **Slow Read Attacks:**
   - *Mekanisme:* Klien membaca data respons dengan buffer window TCP sangat kecil (mengatur *TCP Window Size* mendekati 0), memaksa server menahan buffer respons di kernel memory untuk waktu yang sangat lama.
   - *Mitigasi:* Terapkan socket write timeouts dan monitor backpressure drain events.

---

### 18. Testing Strategies

Pengujian mekanika HTTP harus memverifikasi handling status error, parsing header, dan penanganan timeout secara deterministik.

```typescript
// practical-server.test.ts
import { describe, it, before, after } from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';

describe('HTTP Layer Architecture Test Suite', () => {
  let serverInstance: http.Server;
  const TEST_PORT = 8989;

  before((done) => {
    // Jalankan implementasi server minimal untuk pengetesan kontrak
    serverInstance = http.createServer((req, res) => {
      if (req.url === '/test-stream' && req.method === 'POST') {
        let size = 0;
        req.on('data', (chunk) => {
          size += chunk.length;
          if (size > 50) { // Limit mini untuk testing: 50 bytes
            res.writeHead(413, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ error: 'Payload Too Large' }));
            req.destroy();
          }
        });

        req.on('end', () => {
          if (!res.writableEnded) {
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ status: 'OK', bytesReceived: size }));
          }
        });
      }
    });

    serverInstance.listen(TEST_PORT, done);
  });

  after((done) => {
    serverInstance.close(done);
  });

  it('harus mengembalikan 413 jika payload melebihi ambang batas buffer streaming', (t, done) => {
    const requestOptions = {
      hostname: '127.0.0.1',
      port: TEST_PORT,
      path: '/test-stream',
      method: 'POST',
      headers: {
        'Content-Type': 'application/octet-stream'
      }
    };

    const req = http.request(requestOptions, (res) => {
      assert.equal(res.statusCode, 413);
      let responseBody = '';
      res.on('data', (d) => { responseBody += d; });
      res.on('end', () => {
        const parsed = JSON.parse(responseBody);
        assert.equal(parsed.error, 'Payload Too Large');
        done();
      });
    });

    // Kirim string melebihi 50 bytes untuk memicu trigger proteksi
    req.write('Data ini berukuran sengaja dibuat sangat panjang hingga melampaui batas alokasi buffer 50 bytes!');
    req.end();
  });
});
```

---

### 19. Tooling & Ecosystem

| Kategori Alat | Nama Perkakas | Kasus Penggunaan Utama |
| :--- | :--- | :--- |
| **Packet Analyzer** | **Wireshark** | Menginspeksi payload biner, handshake TCP/TLS, retransmisi paket, dan window size TCP pada level interface kartu jaringan. |
| **CLI Network Diagnostics** | **curl** (`-v`, `--trace-time`) | Menginspeksi seluruh urutan pertukaran raw HTTP headers dan mengukur durasi tahapan koneksi via formatted time variables. |
| **TLS Profiling** | **OpenSSL CLI** (`s_client`) | Memverifikasi rantai validitas sertifikat, handshake latency, dan negosiasi parameter cipher TLS secara langsung. |
| **Browser Diagnostics** | **Chrome DevTools Network & Performance** | Menganalisis *Network Waterfall*, *Priority Scheduling* download aset, dan visualisasi *Critical Rendering Path* (Frame-by-frame layout & paint). |
| **Reverse Proxy/Gateway**| **NGINX / Envoy** | Standar industri untuk TLS Termination, HTTP/2 to HTTP/1.1 translation, buffering, dan rate-limiting sebelum traffic menyentuh runtime aplikasi. |

---

### 20. Summary & Next Steps

#### Rangkuman Eksekutif
Siklus request-response pada ekosistem Full Stack modern menuntut penguasaan terpadu dari level transport jaringan hingga eksekusi visual di browser. Memahami struktur socket TCP/IP, efisiensi handshake TLS 1.3, framing biner multiplexing HTTP/2 dan HTTP/3, serta proses parser rendering engine merupakan pondasi mutlak untuk membangun aplikasi web performan, tahan banting (*resilient*), dan aman pada skala enterprise.

#### Transisi ke Modul Selanjutnya
Di **Modul 02: Backend Runtime Architecture & Asynchronous I/O Execution Models**, kita akan membedah secara mendalam bagaimana server menerima stream byte dari network layer ini dan memprosesnya secara konkruen:
- Mekanisme **Event Loop** (Libuv internals, Microtasks vs Macrotasks, Epoll/Kqueue wrappers).
- Arsitektur I/O non-blocking vs Thread-Pool concurrency (Node.js vs Go vs Worker Threads).
- Rekayasa memori runtime (V8 Heap Management, Garbage Collection Pauses, dan mitigasi Memory Leaks).