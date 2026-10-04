# Kurikulum Rekayasa Perangkat Lunak Enterprise: Node.js Networking Lanjutan
## BAB 04: Enterprise Networking (HTTP/S, HTTP/2, WebSockets, gRPC)
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
- Menguasai arsitektur internal protokol HTTP/1.1, HTTP/2, WebSockets (RFC 6455), dan gRPC di atas Node.js dan runtime V8/libuv.
- Mengimplementasikan HTTP/2 multiplexing dan gRPC streaming (Unary, Client Streaming, Server Streaming, Bidirectional) berkinerja tinggi menggunakan native buffer dan Protobuf.
- Merancang dan membangun klaster WebSocket enterprise yang mendukung skala horizontal dengan Redis Pub/Sub backplane, deteksi *dead connection* adaptif (*heartbeat/ping-pong*), serta mitigasi *backpressure* pada level socket TCP.
- Menganalisis *packet framing*, *flow control window*, *head-of-line blocking*, dan *TLS termination overhead* untuk mengoptimalkan throughput dan memangkas p99/p999 latency hingga tingkat sub-milidetik.
- Mendiagnosis dan menyelesaikan kegagalan jaringan skala produksi seperti *socket leak*, *TCP buffer bloat*, *ephemeral port exhaustion*, dan *half-open connection states*.

---

### 2. Prerequisite
Untuk memahami materi ini secara mendalam, peserta wajib menguasai:
- **Node.js Core Internals**: Event Loop libuv (Phases: Timers, Poll, Check, Close), Streams API (Readable, Writable, Duplex, Transform, backpressure handling), Buffer manipulation (`Buffer.allocUnsafe`, zero-copy operations).
- **Computer Networking Fundamental**: Model OSI & TCP/IP, TCP 3-way handshake, TLS 1.3 handshake, TCP Flow Control (`rwnd`) & Congestion Control (`cwnd`), socket state lifecycle (`TIME_WAIT`, `CLOSE_WAIT`, `ESTABLISHED`).
- **Primitif Bahasa**: TypeScript tingkat lanjut / JavaScript modern (ES2022+), Promises, Async Iterators.
- **Tools**: Wireshark/tcpdump (packet analysis), `k6` atau `autocannon` (load testing), OpenSSL CLI.

---

### 3. Concept & Internal Architecture (Mendalam)

Implementasi jaringan di Node.js bersandar pada integrasi antara V8 JavaScript Engine, layer abstraksi I/O C++ (`node::crypto`, `node::http2`, `node::tls`), dan libuv thread pool / poll loop.

```
+-----------------------------------------------------------------------+
|                         V8 JavaScript Layer                           |
|       (http, https, http2, @grpc/grpc-js, ws/uWebSockets.js)          |
+------------------------------------+----------------------------------+
                                     | JavaScript Streams API
+------------------------------------v----------------------------------+
|                          Node.js C++ Bindings                         |
|     (node_http2.cc, node_crypto.cc, tls_wrap.cc, stream_base.cc)     |
+------------------------------------+----------------------------------+
                                     | Direct Pointers / Zero-Copy Data
+-----------------+------------------+------------------+---------------+
| nghttp2 (C Lib) | OpenSSL / Boring |  zlib (Deflate)  |  HTTP-Parser/ |
|  (H2 Framing)   |  (TLS Engine)    | (Per-message)    |   llhttp      |
+-----------------+------------------+------------------+---------------+
                                     |
+------------------------------------v----------------------------------+
|                         libuv (I/O Multiplexing)                      |
|                  (epoll [Linux], kqueue [macOS], IOCP [Win])          |
+------------------------------------+----------------------------------+
                                     |
+------------------------------------v----------------------------------+
|                 Kernel Space (TCP/IP Network Stack)                   |
|       Socket Buffers (SO_RCVBUF, SO_SNDBUF) -> NIC Ring Buffer        |
+-----------------------------------------------------------------------+
```

#### A. HTTP/1.1 vs HTTP/2 Internal Mechanics
- **HTTP/1.1**: Bersifat *text-based* dan sekuensial. Satu *request-response pair* memonopoli satu koneksi TCP hingga selesai (*Head-of-Line Blocking* di tingkat aplikasi). Node.js menggunakan C++ parser (`llhttp`) untuk membaca data masuk secara parsing token per baris.
- **HTTP/2**: Bersifat *binary framing layer*. Menggunakan *C-library* `nghttp2` yang di-binding langsung ke runtime C++ Node.js.
  - **Frame Types**: `DATA`, `HEADERS`, `PRIORITY`, `RST_STREAM`, `SETTINGS`, `PUSH_PROMISE`, `PING`, `GOAWAY`, `WINDOW_UPDATE`, `CONTINUATION`.
  - **Multiplexing**: Banyak *stream* logis berjalan di atas satu koneksi TCP fisik tunggal secara paralel. Tiap frame memiliki metadata *Stream Identifier* (31-bit).
  - **Flow Control**: Bersifat hop-by-hop. Mengatur kredit data (`WINDOW_UPDATE`) pada level individual stream dan level koneksi penuh, mencegah buffer overflow di sisi receiver.
  - **HPACK Compression**: State-based header compression. Node.js dan client mempertahankan *Static Table* (definisi header standar) dan *Dynamic Table* (header unik yang di-cache selama koneksi berlangsung).

#### B. WebSocket Protocol (RFC 6455)
WebSocket diawali dengan *HTTP Upgrade Handshake*:
1. Client mengirim header: `Upgrade: websocket`, `Connection: Upgrade`, `Sec-WebSocket-Key: <base64>`, `Sec-WebSocket-Version: 13`.
2. Node.js memvalidasi, menghitung SHA-1 dari `Key + 258EAFA5-E914-47DA-95CA-C5AB0DC85B11`, lalu merespons dengan HTTP status `101 Switching Protocols` dan header `Sec-WebSocket-Accept`.
3. Setelah handshake, koneksi dilepas dari HTTP parser (`req.socket.removeListener('data')`) dan dialihkan sepenuhnya ke WebSocket Frame Parser.
4. **Frame Layout**:
   - FIN bit (1 bit), RSV1-3 (3 bits), Opcode (4 bits: text, binary, ping, pong, close).
   - Mask bit (1 bit): Wajib 1 dari client ke server.
   - Payload Length: 7 bits, 7+16 bits, atau 7+64 bits.
   - Masking Key (32 bits): Melindungi caching proxy dari serangan peracunan cache (*cache poisoning*).
   - Payload Data: XOR unmasking dilakukan byte demi byte oleh CPU.

#### C. gRPC (HTTP/2 + Protocol Buffers)
gRPC mengandalkan HTTP/2 sebagai transport:
- Seluruh RPC dipetakan ke HTTP/2 POST request.
- Path berbentuk: `/<package>.<service>/<method>`.
- Header: `content-type: application/grpc+proto` atau `application/grpc`.
- **Payload Framing**: 5-byte prefix mendahului setiap Protobuf payload:
  - 1-byte flag kompresi (`0` = uncompressed, `1` = compressed).
  - 4-byte big-endian integer yang mendefinisikan panjang byte payload Protobuf berikutnya.
- Status penyelesaian dikirim via HTTP/2 *trailers* (`grpc-status`, `grpc-message`), bukan di initial headers.

---

### 4. Why & What

| Dimensi Protokol | HTTP/1.1 | HTTP/2 | WebSockets | gRPC |
| :--- | :--- | :--- | :--- | :--- |
| **Transport** | TCP (Text-based) | TCP (Binary Framing) | TCP (Framed) | HTTP/2 (Binary Proto) |
| **Multiplexing** | Tidak (Pipelining cacat) | Ya (Fully Multiplexed) | Tidak (Full-duplex point-to-point) | Ya (Melalui HTTP/2 Engine) |
| **Pola Komunikasi**| Request-Response | Request-Response / Push | Full-Duplex Bi-directional | Unary, Client/Server/Bi-di Stream |
| **Efisiensi Header**| Rendah (Plaintext redundan) | Tinggi (HPACK stateful) | Sangat Tinggi (2-14 byte overhead)| Sangat Tinggi (HPACK + Protobuf) |
| **Use Case Utama** | Public API, legacy, static | RESTful API, Modern Web | Chat, Game, Real-time Dashboard | Microservices Inter-service IPC |

#### Alasan Memilih Protokol Tertentu di Node.js:
1. **Pilih HTTP/2**: Untuk interaksi Browser-ke-Server modern dengan traffic padat di mana penghematan latency koneksi dan efisiensi overhead header sangat krusial.
2. **Pilih WebSocket**: Jika aplikasi membutuhkan stream data real-time berbasis event dengan latency ultra-rendah tanpa overhead request-response HTTP (contoh: orderbook financial exchange).
3. **Pilih gRPC**: Untuk komunikasi antar microservice backend. gRPC memanfaatkan serialization Protocol Buffers yang jauh lebih cepat, hemat CPU, dan type-safe dibanding JSON parsing di V8 runtime.

---

### 5. How (Workflow Detail)

#### End-to-End WebSocket Lifecycle & Event Loop Integration
1. **TCP SYN-ACK**: Client menginisiasi TCP socket ke port Node.js via libuv.
2. **TLS Handshake**: Jika WSS, OpenSSL mengurus negosiasi cipher suite dan Application-Layer Protocol Negotiation (ALPN).
3. **Upgrade Validation**: Node.js `http.Server` menerima request, memicu event `'upgrade'`.
4. **Socket Detachment**: Event loop memutus pipeline parser `llhttp` dari socket TCP.
5. **Masking & Framing**: Frame masuk diekstrak via transform stream, di-unmasking menggunakan bitwise XOR.
6. **Application Logic**: Event `'message'` terpanggil di JavaScript execution thread.
7. **Backpressure Propagation**: Jika write buffer client lambat, metode `ws.send()` mendeteksi buffer internal penuh (`bufferedAmount > threshold`), menunda pengiriman hingga event `'drain'` terpancar dari TCP socket kernel.

#### gRPC Bidirectional Streaming Workflow
1. Client membuat single HTTP/2 TCP connection.
2. Client membuka stream baru (`HEADERS` frame dengan URI RPC).
3. Client dan Server dapat secara independen mengirim frame `DATA` yang dibungkus format prefix 5-byte.
4. Engine Node.js (`@grpc/grpc-js`) memetakan Node.js `Duplex Stream` langsung ke layer HTTP/2 stream frame generator.
5. Selesai transmisi: Client mengirim frame dengan flag `END_STREAM`, server mengirim frame `HEADERS` (trailers) berisi `grpc-status: 0`.

---

### 6. Analogy & Diagram ASCII

#### A. Multiplexing (HTTP/2) vs Head-of-Line Blocking (HTTP/1.1)

```
HTTP/1.1 (Satu Lajur Antrean Kendaraan):
Client  [Req 1] ------------> Server (Req 2 harus menunggu Req 1 selesai diproses)
Client  <----------- [Res 1] Server
Client  [Req 2] ------------> Server
Client  <----------- [Res 2] Server

HTTP/2 (Rel Kereta Api Kontainer Tersegmentasi):
Stream 1: [Data Chunk A1] -----\
Stream 2:   [Data Chunk B1] ----+--> [ Single TCP Connection ] ---> Receiver Merakit Ulang
Stream 1: [Data Chunk A2] -----/
```

#### B. WebSocket Frame Bitmasking
```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-------+-+-------------+-------------------------------+
|F|R|R|R| opcode|M| Payload len |    Extended payload length    |
|I|S|S|S|  (4)  |A|     (7)     |             (16/64)           |
|N|V|V|V|       |S|             |   (if payload len==126/127)   |
| |1|2|3|       |K|             |                               |
+-+-+-+-+-------+-+-------------+ - - - - - - - - - - - - - - - +
|     Extended payload length continued, if payload len == 127  |
+ - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - +
|                     Masking-key (if MASK set to 1)            |
+-------------------------------+-------------------------------+
|                        Payload Data                           |
|       (Unmasked byte-by-byte: Payload[i] ^ MaskKey[i % 4])    |
+---------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### Implementasi Praktis: HTTP/2 Secure Server dengan Multiplexed Streaming & Native Backpressure

Simpan file di bawah sebagai `src/http2-server.ts`:

```typescript
import http2 from 'node:http2';
import fs from 'node:fs';
import path from 'node:path';
import { pipeline } from 'node:stream/promises';
import { Readable } from 'node:stream';

const server = http2.createSecureServer({
  key: fs.readFileSync(path.join(__dirname, '../certs/server.key')),
  cert: fs.readFileSync(path.join(__dirname, '../certs/server.crt')),
  allowHTTP1: false, // Strict HTTP/2 only
  settings: {
    maxConcurrentStreams: 100,
    initialWindowSize: 1024 * 1024, // 1MB Flow Control Window
  }
});

server.on('error', (err) => console.error('HTTP2 Server Error:', err));

server.on('stream', async (stream, headers) => {
  const method = headers[':method'];
  const reqPath = headers[':path'];

  console.log(`[Stream ${stream.id}] Received request: ${method} ${reqPath}`);

  if (method === 'GET' && reqPath === '/stream-data') {
    stream.respond({
      ':status': 200,
      'content-type': 'application/json',
      'cache-control': 'no-cache'
    });

    // Generator simulasi telemetry volume tinggi
    async function* generateTelemetry() {
      for (let i = 0; i < 50; i++) {
        const payload = JSON.stringify({
          streamId: stream.id,
          sequence: i,
          timestamp: Date.now(),
          cpuLoad: Math.random() * 100
        }) + '\n';
        
        yield Buffer.from(payload);
        // Simulasi latensi processing per record
        await new Promise((resolve) => setTimeout(resolve, 50));
      }
    }

    try {
      const readable = Readable.from(generateTelemetry());
      // Pipeline memastikan backpressure dari network stream HTTP/2 dihormati penuh
      await pipeline(readable, stream);
      console.log(`[Stream ${stream.id}] Successfully completed.`);
    } catch (err: any) {
      if (err.code === 'ERR_STREAM_PREMATURE_CLOSE') {
        console.warn(`[Stream ${stream.id}] Client abruptly closed the connection.`);
      } else {
        console.error(`[Stream ${stream.id}] Pipeline failure:`, err);
      }
    }
  } else {
    stream.respond({ ':status': 404, 'content-type': 'text/plain' });
    stream.end('Resource Not Found');
  }
});

const PORT = 8443;
server.listen(PORT, () => {
  console.log(`HTTP/2 Multiplexing Server running on https://localhost:${PORT}`);
});
```

---

#### Implementasi Praktis: Production WebSocket Server dengan Adaptive Heartbeat & Backpressure Control

Simpan file di bawah sebagai `src/websocket-broker.ts`:

```typescript
import { createServer } from 'node:http';
import WebSocket, { WebSocketServer } from 'ws';

interface ExtendedWebSocket extends WebSocket {
  isAlive: boolean;
  userId?: string;
  ipAddr?: string;
}

const server = createServer();
const wss = new WebSocketServer({ 
  noServer: true,
  maxPayload: 64 * 1024 // Batasi payload max 64KB untuk mencegah DoS
});

// Upgrade listener eksplisit untuk otentikasi awal sebelum TCP socket di-takeover
server.on('upgrade', (request, socket, head) => {
  const url = new URL(request.url || '', `http://${request.headers.host}`);
  const authToken = url.searchParams.get('token');

  // Simulasi validasi auth level transport
  if (!authToken || authToken !== 'enterprise-secret') {
    socket.write('HTTP/1.1 401 Unauthorized\r\n\r\n');
    socket.destroy();
    return;
  }

  wss.handleUpgrade(request, socket, head, (ws) => {
    wss.emit('connection', ws, request);
  });
});

wss.on('connection', (ws: ExtendedWebSocket, request) => {
  ws.isAlive = true;
  ws.ipAddr = request.socket.remoteAddress;

  console.log(`Client terhubung dari IP: ${ws.ipAddr}`);

  // Monitor Ping-Pong untuk deteksi half-open TCP states
  ws.on('pong', () => {
    ws.isAlive = true;
  });

  ws.on('message', (data: WebSocket.RawData, isBinary: boolean) => {
    // Menghormati Backpressure: Periksa buffer outgoing sebelum memproses payload
    if (ws.bufferedAmount > 1024 * 1024) { // Buffer > 1MB
      console.warn(`[Backpressure Warning] Client socket buffer overloaded. Drop message.`);
      return;
    }

    try {
      const message = isBinary ? data : data.toString();
      // Echo response dengan pengecekan performa write
      const response = JSON.stringify({ ack: true, payloadLength: data.toString().length, timestamp: Date.now() });
      
      ws.send(response, { binary: false }, (err) => {
        if (err) console.error(`Failed to send packet to ${ws.ipAddr}:`, err);
      });
    } catch (e) {
      ws.close(1007, 'Invalid UTF-8 Payload');
    }
  });

  ws.on('close', (code, reason) => {
    console.log(`Koneksi ditutup: Code ${code}, Reason: ${reason.toString()}`);
  });

  ws.on('error', (err) => {
    console.error(`Socket error pada ${ws.ipAddr}:`, err);
  });
});

// Heartbeat Reaper: Scan tiap 30 detik, musnahkan connection zombie
const HEARTBEAT_INTERVAL = 30000;
const interval = setInterval(() => {
  wss.clients.forEach((client) => {
    const extWs = client as ExtendedWebSocket;
    if (!extWs.isAlive) {
      console.warn(`Terminating dead socket: ${extWs.ipAddr}`);
      return extWs.terminate();
    }
    extWs.isAlive = false;
    extWs.ping(); // Kirim frame control 0x9 (Ping)
  });
}, HEARTBEAT_INTERVAL);

wss.on('close', () => {
  clearInterval(interval);
});

server.listen(8080, () => {
  console.log('Enterprise WebSocket Engine running on port 8080');
});
```

---

#### Implementasi Praktis: gRPC Bidirectional Streaming Microservice

Definisi proto: `protos/orderbook.proto`
```protobuf
syntax = "proto3";

package orderbook;

service OrderbookService {
  rpc StreamOrders (stream OrderRequest) returns (stream OrderResponse);
}

message OrderRequest {
  string order_id = 1;
  string symbol = 2;
  double price = 3;
  int32 quantity = 4;
}

message OrderResponse {
  string order_id = 1;
  string status = 2;
  int64 executed_at = 3;
}
```

Implementasi gRPC Server: `src/grpc-server.ts`
```typescript
import * as grpc from '@grpc/grpc-js';
import * as protoLoader from '@grpc/proto-loader';
import path from 'node:path';

const PROTO_PATH = path.join(__dirname, '../protos/orderbook.proto');
const packageDefinition = protoLoader.loadSync(PROTO_PATH, {
  keepCase: true,
  longs: String,
  enums: String,
  defaults: true,
  oneofs: true
});

const protoDescriptor = grpc.loadPackageDefinition(packageDefinition) as any;
const orderbookProto = protoDescriptor.orderbook;

function streamOrders(call: grpc.ServerDuplexStream<any, any>) {
  console.log('New gRPC Bi-directional streaming channel opened.');

  call.on('data', (orderRequest: any) => {
    console.log(`[Order Processing] ID: ${orderRequest.order_id}, Price: ${orderRequest.price}`);

    // Backpressure check: jika write buffer kernel TCP jenuh
    const canWrite = call.write({
      order_id: orderRequest.order_id,
      status: 'FILLED',
      executed_at: Date.now()
    });

    if (!canWrite) {
      console.warn('Kernel write buffer full, pausing readable stream.');
      call.pause();
      call.once('drain', () => {
        console.log('Kernel write buffer drained, resuming readable stream.');
        call.resume();
      });
    }
  });

  call.on('end', () => {
    console.log('Client ended transmission.');
    call.end();
  });

  call.on('error', (err: Error) => {
    console.error('gRPC Stream runtime error:', err);
  });
}

function startGrpcServer() {
  const server = new grpc.Server({
    'grpc.max_receive_message_length': 1024 * 1024 * 4, // 4MB
    'grpc.max_send_message_length': 1024 * 1024 * 4,
    'grpc.keepalive_time_ms': 10000,
    'grpc.keepalive_timeout_ms': 5000,
    'grpc.http2.min_ping_interval_without_data_ms': 5000
  });

  server.addService(orderbookProto.OrderbookService.service, {
    StreamOrders: streamOrders
  });

  server.bindAsync('0.0.0.0:50051', grpc.ServerCredentials.createInsecure(), (err, port) => {
    if (err) throw err;
    console.log(`gRPC Server active on port: ${port}`);
  });
}

startGrpcServer();
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Skenario Kasus: Tier-1 Financial Trading Brokerage Gateway
Sebuah platform trading kripto/saham memproses rata-rata 150.000 transaksi per detik (*TPS*) dengan kebutuhan streaming harga instan ke 300.000 web clients yang terhubung via WebSocket secara konkuren.

```
                  +-------------------------------------------------+
                  |      Enterprise Edge Layer (AWS NLB / Layer 4)  |
                  +-----------------------+-------------------------+
                                          | Terminate TLS (Optional)
               +--------------------------+--------------------------+
               |                                                     |
+--------------v---------------+                     +---------------v--------------+
| Node.js Gateway Pod 1        |                     | Node.js Gateway Pod N        |
| (uWebSockets.js / Node ws)   |                     | (uWebSockets.js / Node ws)   |
+--------------+---------------+                     +---------------+--------------+
               |                                                     |
               +--------------------------+--------------------------+
                                          |
                      +-------------------v-------------------+
                      | Redis Cluster (Pub/Sub Backplane)     |
                      | Sharded across 16 master nodes        |
                      +-------------------+-------------------+
                                          |
                      +-------------------v-------------------+
                      | Matching Engine (C++ / Go via gRPC)   |
                      | Internal Low-Latency Fabric           |
                      +---------------------------------------+
```

#### Masalah Produksi yang Ditemukan:
1. **Garbage Collection Pauses**: Parsing pesan JSON berukuran jutaan objek string per detik menyebabkan V8 Scavenge & Mark-Sweep freeze selama 100-250ms, memicu drop koneksi WebSocket massal karena timeout heartbeat.
2. **Buffer Bloat & OOM (Out Of Memory)**: Ketika pasar crash, traffic order melonjak 10x lipat. Node.js gateway terus menelan data dari core engine tanpa memedulikan kemampuan koneksi internet client yang lambat. Array write buffer Node.js membengkak tak terkendali hingga pod terkena Linux OOM-Killer (`Exit Code 137`).

#### Solusi Arsitektural:
1. **Penerapan Protocol Buffers via gRPC**: Menggantikan JSON pada layer ingestion internal untuk mengeliminasi alokasi V8 heap string yang berlebihan.
2. **Hard-Limit WebSocket Backpressure Guard**:
   ```typescript
   if (socket.bufferedAmount > MAX_ALLOWED_BUFFER_PER_CLIENT) {
     metrics.droppedFramesCounter.inc();
     // Drop frame volatil non-kritis (seperti quote harga minor) atau terminate koneksi
     return;
   }
   ```
3. **Horizontal Scaling dengan Redis Pub/Sub Sharding**: Koneksi WebSocket disebar ke 50 pod Node.js di Kubernetes. State routing menggunakan hash consistent dari `instrument_id` sehingga broadcast update pasar tidak dikirim secara membanjir (*flood*) ke semua node.

---

### 9. Trade-offs

| Pendekatan/Teknologi | Keuntungan (Pros) | Biaya/Kelemahan (Cons) | Metrik Terdampak |
| :--- | :--- | :--- | :--- |
| **HTTP/2 Multiplexing** | Menghemat TCP handshakes; efisiensi tinggi pada resource-dense apps. | Rentan terhadap TCP Head-of-Line Blocking jika ada Packet Loss tinggi di jaringan lossy. | Latency p99 melonjak drastis jika packet drop > 2%. |
| **JSON vs Protocol Buffers** | JSON bersifat *human-readable*, fleksibel, native terhadap JavaScript engine. | CPU overhead tinggi untuk serialisasi/deserialisasi; ukuran byte over-the-wire besar. | Throughput CPU turun 40-60%; konsumsi bandwidth 2-3x lebih boros. |
| **uWebSockets.js vs Native `ws`**| Throughput 5-10x lebih tinggi; penggunaan RAM per-koneksi jauh lebih kecil (~2KB vs ~50KB). | Menggunakan C++ addon internal; *stack trace debugging* lebih sulit; setup build native rumit. | Memory footprint turun 80%; pemeliharaan (maintainability) meningkat tingkat kesulitannya. |
| **TLS Termination di Node.js vs API Gateway (Envoy/Nginx)** | Tidak ada insecure internal hop; enkripsi end-to-end murni hingga ke runtime. | V8 thread terbebani crypto parsing; CPU saturation terjadi lebih cepat di Node.js. | Menurunkan kapasitas konkurensi request per Node.js instance hingga 35%. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Dead Connection Zombie (TCP Half-Open)
- **Gejala**: RAM server habis perlahan, metrics menunjukkan ribuan koneksi aktif, padahal client sudah mematikan perangkat atau kehilangan sinyal seluler.
- **Penyebab**: Koneksi TCP tidak ditutup dengan sinyal `FIN` / `RST`. Server menganggap soket masih `ESTABLISHED`.
- **Troubleshooting**: Terapkan *application-level ping/pong* berjangka waktu ketat (RFC 6455). Aktifkan socket TCP keepalive pada level OS:
  ```typescript
  socket.setKeepAlive(true, 60000); // 60s idle threshold
  ```

#### 2. Unchecked Outgoing Backpressure Memory Leak
- **Gejala**: Node.js crash dengan pesan `JavaScript heap out of memory` saat melakukan broadcast data volume tinggi ke ribuan socket.
- **Penyebab**: Memanggil `ws.send()` atau `stream.write()` berulang kali tanpa memeriksa return value atau `socket.bufferedAmount`. Node.js menampung data yang belum terkirim di dalam V8 Heap.
- **Solusi**: Pantau drain event:
  ```typescript
  if (!stream.write(chunk)) {
    await events.once(stream, 'drain');
  }
  ```

#### 3. Ephemeral Port Exhaustion
- **Gejala**: Node.js melempar error `connect EADDRNOTAVAIL` saat membuat ribuan outgoing gRPC/HTTP request per detik.
- **Penyebab**: Client membuka koneksi baru untuk setiap request alih-alih melakukan connection pooling. Soket yang ditutup masuk ke state `TIME_WAIT` selama 60 detik secara default oleh Linux Kernel, menguras seluruh port keluar (rentang 32768-60999).
- **Solusi**: Gunakan reusable client instances, HTTP/2 multiplexing, atau naikkan limit kernel:
  ```bash
  sysctl -w net.ipv4.tcp_tw_reuse=1
  ```

---

### 11. Best Practices (Production Checklist)

- [ ] **Gunakan HTTP/2 Connection Reuse**: Pastikan client backend Anda tidak menginisialisasi new ClientSession pada setiap RPC.
- [ ] **Enforce TLS 1.3 Ciphers Only**: Nonaktifkan TLS insecure ciphers lama di konfigurasi:
  ```typescript
  tls.createSecureContext({
    minVersion: 'TLSv1.3',
    ciphers: 'TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256'
  });
  ```
- [ ] **Set Socket-level Timeouts**:
  - `headersTimeout`: Mencegah Slowloris attacks.
  - `requestTimeout`: Mencegah client menggantung koneksi tanpa data.
  - `keepAliveTimeout`: Atur selalu sedikit lebih tinggi dari timeout Load Balancer (misal: AWS ALB 60s -> Node.js 65s) untuk mencegah race condition HTTP 502.
- [ ] **Validasi Payload Size Execution**: Pasang `maxPayload` limit pada seluruh framing WebSocket/gRPC guna menangkal payload decompression bomb / memory exhaustion DoS.
- [ ] **Graceful Shutdown Jaringan**: Saat menerima sinyal `SIGTERM`, kirim frame `GOAWAY` (pada HTTP/2 & gRPC) atau status `1001 Going Away` (pada WebSocket), tunggu active streams selesai selama periode grace period (contoh: 15 detik), kemudian hancurkan instance socket.

---

### 12. Hands-on Practice

Buat dan jalankan instruksi berikut untuk memverifikasi performa jaringan HTTP/2 dan WebSocket di environment lokal.

#### Struktur Direktori:
```
hands-on/m02/
├── certs/
│   ├── make-certs.sh
├── protos/
│   └── orderbook.proto
├── src/
│   ├── http2-server.ts
│   ├── websocket-broker.ts
│   └── grpc-server.ts
├── package.json
└── tsconfig.json
```

#### Langkah 1: Inisialisasi Environment & Self-Signed Certificates
Masuk ke root workspace dan jalankan:
```bash
mkdir -p hands-on/m02/certs hands-on/m02/protos hands-on/m02/src
cd hands-on/m02

# Buat self-signed TLS certs untuk HTTP/2
openssl req -x509 -newkey rsa:2048 -nodes -sha256 -subj '/CN=localhost' \
  -keyout certs/server.key -out certs/server.crt -days 365

# Inisialisasi Project Node.js
npm init -y
npm install ws @grpc/grpc-js @proto-loader
npm install --save-dev typescript @types/node @types/ws tsx
```

#### Langkah 2: Buat tsconfig.json
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "CommonJS",
    "moduleResolution": "node",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "outDir": "./dist"
  }
}
```

#### Langkah 3: Eksekusi Server HTTP/2
Salin kode dari Bagian 7 (`src/http2-server.ts`), lalu jalankan:
```bash
npx tsx src/http2-server.ts
```

#### Langkah 4: Pengujian Menggunakan cURL (HTTP/2 Native Verification)
Buka terminal baru dan amati alur multiplexing serta header frame:
```bash
curl -k --http2 -v https://localhost:8443/stream-data
```
*Amati output konsol: Header `:status: 200`, frame transfer berlangsung secara chunked tanpa memutus koneksi.*

#### Langkah 5: Load Test WebSocket Engine
Jalankan server WebSocket:
```bash
npx tsx src/websocket-broker.ts
```
Uji menggunakan benchmark tool (misal: `autocannon` atau tool wscat):
```bash
npx wscat -c "ws://localhost:8080?token=enterprise-secret"
# Ketikkan teks sembarang: Server harus membalas dengan instant acknowledgement payload.
```

---

### 13. Exercise

#### Level: Easy
1. Modifikasi server `src/http2-server.ts` agar menangani route `/health` yang mengembalikan respon JSON `{ status: 'UP', uptime: process.uptime() }`.
2. Tambahkan pengecekan header `user-agent`. Tolak request dengan status HTTP `400` jika header tersebut tidak tersedia.

#### Level: Medium
1. Pada `src/websocket-broker.ts`, buat sistem broadcast channel terisolasi (*Rooms/Topics*).
2. Setiap kali client mengirim pesan JSON bertipe: `{ action: "join", room: "forex" }`, client didaftarkan ke Set memory room tersebut.
3. Saat client mengirim `{ action: "publish", room: "forex", data: "EURUSD: 1.085" }`, hanya client di dalam room tersebut yang menerima pesan. Pastikan validasi runtime diterapkan jika client belum join.

#### Level: Hard
1. Implementasikan native **Circuit Breaker** pada layer client gRPC yang memanggil `StreamOrders`.
2. Jika rate error RPC mencapai > 50% dalam window 10 detik, *trip the circuit* (buka sirkuit) selama 5 detik, gagalkan pemanggilan berikutnya secara langsung (`fail-fast`) tanpa menyentuh network interface.
3. Setelah cooldown 5 detik, masuki state *half-open*, izinkan 1 probe request. Jika sukses, tutup kembali sirkuit; jika gagal, reset interval cooldown dengan algoritma exponential backoff.

---

### 14. Challenge

**Skenario**: Anda ditugaskan membangun **Zero-Allocation Multiprotocol Gateway** di Node.js yang mentranslasikan ratusan ribu stream sensor IoT (WebSockets) secara langsung ke Backend Core Processing (gRPC).

**Spesifikasi Persyaratan**:
1. **Memory Budget**: Server tidak boleh mengalokasikan string baru di heap V8 per incoming packet. Seluruh payload yang diterima dari WebSocket frame harus diproses secara zero-copy menggunakan buffer biner Node.js (`Buffer.subarray`, `Buffer.copy`).
2. **Dynamic Backpressure Balancing**: Jika buffer antrean kirim gRPC ke core processing mengalami `call.write() === false`, maka WebSocket server secara otomatis harus menghentikan pembacaan frame dari koneksi socket klien TCP pengirim (`socket.pause()`) hingga event `'drain'` dari gRPC stream terpancar.
3. **Resiliency Injection**: Terapkan deteksi anomaly di mana jika satu client IoT mengirimkan data > 500 KB/sec, koneksi socket client tersebut langsung di-throttling tanpa memengaruhi I/O event loop dari klien-klien lain di satu thread Node.js yang sama.
4. **Deliverable**: File `src/gateway-challenge.ts` yang menggabungkan WS server + gRPC client stream dengan backpressure synchronization logic yang anti-kebocoran memory.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Basic Concepts (Pilihan Ganda & Konseptual)
1. **Apa perbedaan mendasar antara transport level HTTP/1.1 Pipelining dan HTTP/2 Multiplexing?**
   - *Jawaban*: HTTP/1.1 Pipelining masih mengharuskan server mengirimkan respons berurutan sesuai urutan request (tetap mengalami Head-of-Line blocking pada level HTTP), sedangkan HTTP/2 memecah pesan menjadi frames independen dengan Stream ID berbeda yang dapat disisipkan dan dirakit ulang tanpa bergantung pada urutan respons.
2. **Mengapa masking key 4-byte wajib disertakan dalam WebSocket frame dari client ke server, tetapi dilarang dari server ke client?**
   - *Jawaban*: Masking dari client wajib untuk mencegah serangan *Cache Poisoning* pada perantara/proxy HTTP perantara yang keliru menginterpretasikan payload. Dari server ke client tidak perlu dimask karena proxy tidak dapat dibodohi oleh respon upstream yang sudah terikat koneksi tunnel.
3. **Apa kegunaan dari 5-byte header prefix pada framing pesan gRPC di atas HTTP/2?**
   - *Jawaban*: Byte ke-1 digunakan sebagai flag kompresi data (Compressed-Flag), dan 4 byte berikutnya adalah Big-Endian integer penentu panjang byte aktual dari serialized Protocol Buffer payload yang menyusul.
4. **Apa implikasi pemanggilan `socket.setKeepAlive(true)` pada tingkat sistem operasi?**
   - *Jawaban*: OS akan secara periodik mengirimkan probe packet TCP ACK kosong saat soket idle untuk memverifikasi apakah remote endpoint masih hidup, membersihkan status socket secara otomatis jika probe gagal merespons.
5. **Bagian memory manakah yang menampung frame data ketika method `.write()` pada stream Node.js mengembalikan nilai `false`?**
   - *Jawaban*: Data ditampung di internal write buffer memory queue milik stream runtime Node.js (pada level heap V8) hingga buffer kernel sistem operasi (`SO_SNDBUF`) siap menerima data kembali.

#### B. Intermediate Engineering (Analisis & Troubleshooting)
6. **Jelaskan apa yang dimaksud dengan TCP Head-of-Line Blocking pada HTTP/2 dan mengapa hal ini dipecahkan oleh HTTP/3 (QUIC)?**
   - *Jawaban*: Karena seluruh stream HTTP/2 berada di atas satu koneksi TCP tunggal, jika satu segmen TCP hilang (*packet loss*), OS kernel menahan seluruh segmen berikutnya di buffer hingga paket yang hilang di-retransmit, menghentikan seluruh multiplexed streams. HTTP/3 menggunakan QUIC (berbasis UDP) sehingga packet loss pada satu stream tidak menghambat proses stream lainnya.
7. **Mengapa pembacaan buffer secara `Buffer.allocUnsafe()` jauh lebih cepat dibanding `Buffer.alloc()`, dan risiko keamanan jaringan apa yang ditimbulkannya jika tidak digunakan dengan hati-hati?**
   - *Jawaban*: `Buffer.allocUnsafe` tidak menginisialisasi memory dengan nilai nol (melewati proses zero-filling), sehingga langsung mengalokasikan segmen memory mentah. Risikonya, jika data lama di memory tersebut tidak ditimpa sepenuhnya sebelum dikirim ke socket jaringan, server berpotensi membocorkan data sensitif (seperti kredensial atau chunk TLS) ke client.
8. **Bagaimana cara kerja HPACK dynamic table dalam HTTP/2 saat koneksi berlangsung lama, dan bagaimana ini bisa menjadi celah eksploitasi jika ukurannya tidak dibatasi?**
   - *Jawaban*: HPACK memetakan header yang sering muncul ke indeks integer di dynamic table shared state antara client dan server. Jika ukurannya tidak dibatasi, penyerang dapat mengirim ribuan header unik untuk memenuhi memory server (*HPACK Bomb* / DoS). Limitasi diatur via `SETTINGS_HEADER_TABLE_SIZE`.
9. **Apa perbedaan status penutupan WebSocket `1000` vs `1006`?**
   - *Jawaban*: Code `1000` menandakan *Normal Closure* (koneksi ditutup secara sengaja oleh salah satu pihak dengan frame Close). Code `1006` adalah kode abnormal internal (tidak pernah dikirim over-the-wire) yang dimunculkan oleh library klien/server saat koneksi TCP terputus mendadak tanpa handshake close.
10. **Bagaimana Node.js memetakan thread pool libuv terhadap I/O jaringan berbasis socket?**
    - *Jawaban*: libuv **tidak** menggunakan thread pool untuk socket TCP/networking biasa. Socket I/O di-handle sepenuhnya secara non-blocking dan asynchronous menggunakan OS event notification primitives (seperti `epoll` di Linux, `kqueue` di macOS) langsung di main event loop thread.

#### C. Production Incident Scenarios (Analisis Kasus Nyata)
11. **Skenario Insiden 1**:
    *Kondisi*: Load balancer perusahaan melaporkan error massal `HTTP 502 Bad Gateway` secara sporadis tepat tiap 60 detik sekali pada klaster HTTP/2 Node.js.
    *Investigasi*: Node.js memiliki parameter default `keepAliveTimeout` sebesar 5000ms, sedangkan AWS ALB memiliki idle timeout sebesar 60000ms.
    *Pertanyaan*: Jelaskan akar masalah (root cause) race condition tersebut dan berikan konfigurasi perbaikannya!
    *Solusi*: 
    - *Root Cause*: ALB menganggap koneksi TCP masih valid karena timer-nya 60s. Tepat pada detik ke-5, Node.js mengirim frame penutupan koneksi (TCP FIN). Jika ALB meneruskan request client tepat saat FIN sedang meluncur di kabel jaringan, request membentur koneksi yang sudah ditutup Node.js, menghasilkan respons `502 Bad Gateway`.
    - *Fix*: Atur selalu `keepAliveTimeout` Node.js lebih besar dari idle timeout load balancer:
      ```typescript
      server.keepAliveTimeout = 65000; // 65 detik
      server.headersTimeout = 66000;   // Harus lebih besar dari keepAliveTimeout
      ```

12. **Skenario Insiden 2**:
    *Kondisi*: Pod Node.js yang menangani ingestion data telemetri ribuan edge device mengalami lonjakan konsumsi memori linier hingga crash restart berulang kali pada jam sibuk, meskipun CPU utilization di bawah 30%.
    *Investigasi*: Ditemukan kode internal: `deviceSocket.on('data', (chunk) => databaseClient.insert(chunk));` di mana insert database memiliki konkurensi lambat dan query queue bertambah jutaan.
    *Pertanyaan*: Diagnosa kegagalan arsitektur ini dan tuliskan perbaikan kodenya!
    *Solusi*:
    - *Root Cause*: Ketiadaan Backpressure handling. Input network dibaca tanpa henti dari TCP socket buffer, sementara penulisan ke database mengalami latensi. Hal ini menumpuk jutaan closure promise yang unresolved di dalam memory heap Node.js.
    - *Fix*:
      ```typescript
      deviceSocket.on('data', async (chunk) => {
        deviceSocket.pause(); // Hentikan pembacaan dari socket buffer kernel
        try {
          await databaseClient.insert(chunk);
        } finally {
          deviceSocket.resume(); // Lanjutkan pembacaan jika DB write telah selesai
        }
      });
      ```

13. **Skenario Insiden 3**:
    *Kondisi*: Tim keamanan siber mendapati server WebSocket Node.js menjadi unresponsive terhadap klien baru saat terjadi lonjakan traffic dari ribuan IP penyerang yang hanya membuka koneksi TLS/HTTP lalu tidak mengirimkan frame upgrade sama sekali.
    *Investigasi*: Resource file descriptors (FD) server habis (`EMFILE: too many open files`).
    *Pertanyaan*: Mekanisme apa yang absen di layer networking server dan bagaimana mitigasinya?
    *Solusi*:
    - *Root Cause*: Serangan *Slowloris / Handshake Starvation*. Penyerang mengeksekusi TCP 3-way handshake tanpa mengirim payload HTTP upgrade, menahan socket connection tetap terbuka dan menguras file descriptor server.
    - *Fix*: Terapkan timeout ketat pada level server sebelum upgrade disetujui:
      ```typescript
      server.headersTimeout = 5000; // Putus soket jika headers tidak beres dalam 5s
      server.requestTimeout = 10000;
      server.setTimeout(10000, (socket) => {
        socket.destroy(); // Musnahkan soket yang tidak responsif
      });
      ```

---

### 16. Summary

1. **Pemilihan Protokol Presisi**: HTTP/2 unggul dalam utilisasi satu koneksi untuk banyak resource via multiplexing; WebSockets adalah standar emas full-duplex bi-directional streaming murni; gRPC mengombinasikan efisiensi HTTP/2 dan kecepatan serialization binary Protobuf untuk high-throughput microservices IPC.
2. **Backpressure Adalah Hukum Mutlak**: Jangan pernah memompa stream data keluar tanpa mengevaluasi ketersediaan ruang transmisi (`socket.bufferedAmount` atau nilai return `.write()`). Mengabaikan hal ini adalah penyebab utama OOM crash server Node.js di skala enterprise.
3. **Karakteristik libuv Non-Blocking**: Seluruh socket networking di Node.js bersifat event-driven non-blocking I/O yang berjalan di thread utama. Jangan pernah memblokir thread ini dengan synchronous processing, crypto/decompression berlebihan, atau loop komputasi berat agar latensi frame networking tetap berada di level sub-milidetik.
4. **Ketahanan Jaringan Produksi**: Selalu pasang *Heartbeat Reapers* untuk menghabisi zombie half-open connections, sesuaikan timeout Node.js melebihi load-balancer timeouts, dan terapkan zero-copy binary buffering untuk performa transmisi data throughput tinggi yang stabil.