# 04-Backend-and-Database / nodejs / Bab 04 Module 01: Enterprise Networking: HTTP/S, HTTP/2, WebSockets, & gRPC

---

## 01. Identitas Modul
* **Domain Kurikulum:** Backend Development & Distributed Systems
* **Jalur Spesialisasi:** Node.js Systems Engineering & High-Throughput Networking
* **Kode Modul:** `NODE-NET-0401`
* **Prasyarat Pengetahuan:** 
  * Node.js Event Loop, Streams API, dan Async/Await internals.
  * Dasar-dasar Layer OSI (khususnya Layer 4 TCP/UDP dan Layer 7 Application).
  * Penggunaan Public Key Infrastructure (PKI), TLS/SSL Handshake, dan format X.509 Certificates.
* **Target Tingkat Kemahiran:** Advanced / Principal Engineer
* **Estimasi Waktu Penyelesaian:** 12 - 16 Jam Kerja Terfokus

---

## 02. Learning Objectives
Setelah menyelesaikan modul ini, Anda akan memiliki kemampuan teruji untuk:
1. **Menganalisis dan Membedakan Karakteristik Transport Layer 7:** Menguraikan lifecycle, framing format, statefulness, dan connection reuse pada protokol HTTP/1.1, HTTP/2, WebSocket (RFC 6455), dan gRPC berbasis HTTP/2.
2. **Merancang TLS/mTLS Edge Architecture:** Mengonfigurasi engine native TLS (`node:tls`, `node:https`, `node:http2`) dengan cipher suite modern (TLS 1.3), ALPN (Application-Layer Protocol Negotiation), dan mutual TLS authentication untuk keamanan komunikasi zero-trust.
3. **Mengeliminasi Head-of-Line (HoL) Blocking:** Mengimplementasikan multiplexing menggunakan binary framing layer pada HTTP/2 dan gRPC di atas single TCP connection.
4. **Membangun Full-Duplex Real-Time Data Plane:** Mengembangkan WebSocket engine performa tinggi menggunakan alokasi buffer biner nol (zero-copy), masking, frame fragmentation, serta penanganan backpressure.
5. **Mengimplementasikan gRPC Polyglot Communication:** Mengonfigurasi contract-first RPC menggunakan Protocol Buffers v3, streaming RPC (unary, client, server, bidirectional), serta custom metadata interceptors.
6. **Menerapkan Production-Grade Resiliency Patterns:** Melakukan tuning socket keep-alive, TCP Window sizes, idle timeout cleanup, TLS session resumption, dan structured observability.

---

## 03. Concept Map Diagram ASCII

```
                                [ CLIENT / CONSUMER ]
                                          |
                +-------------------------+-------------------------+
                |                         |                         |
           (HTTPS/REST)                (HTTP/2)               (WebSocket)
                |                         |                         |
                v                         v                         v
       +-----------------+       +-----------------+       +-----------------+
       | Node:https      |       | Node:http2      |       | RFC 6455 Engine |
       | Text Framing    |       | Binary Framing  |       | Full-Duplex     |
       | 1 Req / Conn    |       | Multiplexing    |       | Persistent      |
       | (Keep-Alive)    |       | Stream Prio     |       | Framing / Ping  |
       +-----------------+       +-----------------+       +-----------------+
                |                         |                         |
                +------------+------------+                         |
                             | (Internal Service-to-Service)        |
                             v                                      |
                    +------------------+                            |
                    | gRPC Server Engine|                            |
                    | (Protobuf v3)    |<---------------------------+
                    | ALPN: h2         |
                    +------------------+
                             |
    =========================v====================================================
                       NODE.JS RUNTIME & OS NETWORKING CORE
    ------------------------------------------------------------------------------
       [ libuv Event Loop ] <---> [ node:net / Socket ] <---> [ OpenSSL Engine ]
                                         |
                                         v
       [ TCP / IP Stack ] <---> [ OS Kernel Sockets ] <---> [ NIC Buffers ]
    ==============================================================================
```

---

## 04. Mengapa Relevan
Dalam arsitektur microservices berskala enterprise, bottleneck performa utama sering kali bukan berada pada CPU atau disk I/O, melainkan pada **Network I/O** dan overhead protokol komunikasi. 

* **HTTP/1.1** memiliki keterbatasan *Head-of-Line (HoL) Blocking* di level HTTP dan header bloat (akibat metadata teks berulang).
* **HTTP/2** menyelesaikan masalah multiplexing banyak request melalui satu koneksi TCP via *binary framing*, serta mendukung *header compression* via HPACK.
* **WebSocket** mengeliminasi overhead polling untuk kebutuhan real-time bidirectional stream, mempertahankan satu koneksi persistent full-duplex.
* **gRPC** memaksimalkan efisiensi komunikasi antar-layanan (East-West traffic) dengan serialisasi biner Protocol Buffers dan *strict contract-first API schema*, mengurangi latency serialisasi JSON dan konsumsi bandwidth secara signifikan.

Penguasaan arsitektur ini di Node.js krusial untuk membangun data plane yang mampu melayani ratusan ribu request per detik secara stabil dengan alokasi resource komputasi yang efisien.

---

## 05. Anatomi Konsep Inti

```
+-----------------------------------------------------------------------------------+
|                        PROTOCOLS TAXONOMY COMPARISON                              |
+-------------------+----------------+----------------+---------------+-------------+
| Feature           | HTTP/1.1       | HTTP/2         | WebSockets    | gRPC (h2)   |
+-------------------+----------------+----------------+---------------+-------------+
| Transport Layer   | TCP            | TCP            | TCP           | TCP         |
| Framing           | Plain Text     | Binary Frames  | Binary Frames | Binary Frame|
| Multiplexing      | Pipelining (X) | Stream IDs (V) | N/A (1:1 Conn)| Stream IDs  |
| Compression       | Body Only      | HPACK (Hdr+Bdy)| Per-message   | Protobuf+Hdr|
| Duplexity         | Half-Duplex    | Half/Full Req  | Full-Duplex   | Full (4 Typ)|
| Schema Contract   | Optional (OAS) | Optional (OAS) | Custom Event  | Protobuf (V)|
| Node.js Native API| `node:https`   | `node:http2`   | 3rd Party/Net | `@grpc/grpc`|
+-------------------+----------------+----------------+---------------+-------------+
```

### 1. HTTP/S & HTTP/2 Internals
* **TLS Engine & ALPN Negotiation:** Node.js menggunakan integrasi V8 dan OpenSSL. Saat client melakukan TLS Handshake, client mengirimkan ekstensi *Application-Layer Protocol Negotiation (ALPN)* (`h2`, `http/1.1`). Node.js memilih protokol yang cocok secara instan tanpa additional round-trips.
* **HTTP/2 Binary Framing Layer:** Mengonversi data stream menjadi frame biner: `HEADERS`, `DATA`, `SETTINGS`, `RST_STREAM`, dan `PING`. Setiap stream memiliki identifier (`Stream ID`, ganjil untuk client-initiated, genap untuk server-initiated), memungkinkan interleaving data independen pada single TCP stream.

### 2. RFC 6455 WebSocket Engine
* **Handshake Upgrade:** Client mengirimkan HTTP/1.1 request dengan header `Upgrade: websocket` dan `Sec-WebSocket-Key`. Server merespons dengan status `101 Switching Protocols` dan hash SHA-1 dari key tersebut ditambah magic GUID (`258EAFA5-E914-47DA-95CA-C5AB0DC85B11`).
* **Frame Masking & Zero-Copy Parsing:** Sesuai RFC 6455, frame dari client **harus** di-mask dengan 4-byte key acak untuk mencegah *cache poisoning* pada proxy perantara. Server Node.js harus melakukan unmasking data binary secara efisien menggunakan bitwise XOR langsung pada native `Buffer`.

### 3. gRPC Core Engine
* **Transport Substrate:** Menggunakan HTTP/2 streams (`content-type: application/grpc`).
* **Framing Model:** Setiap pesan gRPC dibungkus dalam *5-byte prefix* (1 byte flag kompresi + 4 byte message length big-endian), diikuti oleh payload Protocol Buffers terkompresi/tidak terkompresi.
* **Trailer-Based Status:** Status eksekusi RPC tidak dikirimkan di awal respons, melainkan melalui HTTP/2 Trailing Headers (`grpc-status`, `grpc-message`) setelah stream data selesai dikonsumsi.

---

## 06. Panduan Implementasi Step-by-Step

### Tahap 1: Pembangkitan Self-Signed Certificates dengan ALPN Support
Jalankan instruksi shell ini untuk membuat Public Key Infrastructure (PKI) lokal:

```bash
# 1. Generate Root CA
openssl req -x509 -new -nodes -newkey rsa:4096 -keyout ca.key -sha256 -days 365 -out ca.crt -subj "/CN=EnterpriseDevCA"

# 2. Generate Server Certificate Signing Request (CSR) & Key
openssl req -nodes -newkey rsa:2048 -keyout server.key -out server.csr -subj "/CN=localhost"

# 3. Buat file ekstensi SAN (Subject Alternative Name)
cat > server.ext <<EOF
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage = digitalSignature, nonRepudiation, keyEncipherment, dataEncipherment
subjectAltName = @alt_names

[alt_names]
DNS.1 = localhost
IP.1 = 127.0.0.1
EOF

# 4. Tandatangani Server Certificate dengan CA
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out server.crt -days 365 -sha256 -extfile server.ext
```

### Tahap 2: Implementasi Universal Gateway (HTTPS + HTTP/2 Native)
Gunakan modul native `node:http2` dengan parameter `allowHTTP1: true` untuk mengaktifkan fallback otomatis berdasarkan negosiasi ALPN.

---

## 07. Contoh Kasus Sederhana: Native Multi-Protocol Server

File: `simple-server.mjs`
```javascript
import http2 from 'node:http2';
import fs from 'node:fs';

const options = {
  key: fs.readFileSync('server.key'),
  cert: fs.readFileSync('server.crt'),
  allowHTTP1: true // Mengizinkan fallback otomatis ke HTTP/1.1 jika client tidak support H2
};

const server = http2.createSecureServer(options, (req, res) => {
  const protocol = req.httpVersion;
  res.writeHead(200, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({
    message: 'Hello Secure World',
    negotiatedProtocol: protocol,
    alpn: req.socket.alpnProtocol
  }));
});

server.listen(8443, () => {
  console.log('Secure multi-protocol server listening on https://localhost:8443');
});
```

---

## 08. Implementasi Production-Grade Lengkap Kode

Berikut adalah implementasi sistem gateway terpadu yang memadukan:
1. **HTTP/2 TLS ALPN Server** (dengan fallback HTTP/1.1).
2. **WebSocket Native RFC 6455 Engine** (menggunakan direct socket handling tanpa dependency pihak ketiga).
3. **gRPC Server** (menggunakan `@grpc/grpc-js` dan `@grpc/proto-loader`) yang melayani stream binary metrics.

### Project Setup
```bash
npm init -y
npm install @grpc/grpc-js @grpc/proto-loader
```

### File 1: `proto/telemetry.proto`
```protobuf
syntax = "proto3";

package telemetry;

service MetricService {
  rpc StreamMetrics (MetricRequest) returns (stream MetricResponse);
}

message MetricRequest {
  string service_id = 1;
  int32 interval_ms = 2;
}

message MetricResponse {
  string timestamp = 1;
  double cpu_usage = 2;
  double memory_usage_mb = 3;
}
```

### File 2: `server-enterprise.mjs`
```javascript
import http2 from 'node:http2';
import fs from 'node:fs';
import crypto from 'node:crypto';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import grpc from '@grpc/grpc-js';
import protoLoader from '@grpc/proto-loader';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// ==========================================
// 1. HTTP/2 & HTTPS SECURE API ENGINE
// ==========================================
const tlsOptions = {
  key: fs.readFileSync(path.join(__dirname, 'server.key')),
  cert: fs.readFileSync(path.join(__dirname, 'server.crt')),
  allowHTTP1: true,
  minVersion: 'TLSv1.3',
  ciphers: 'TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256'
};

const gatewayServer = http2.createSecureServer(tlsOptions);

gatewayServer.on('error', (err) => {
  console.error('[GATEWAY_ERR]:', err);
});

// Handling Native HTTP/2 Multiplexed Streams
gatewayServer.on('stream', (stream, headers) => {
  const path = headers[':path'];
  const method = headers[':method'];

  if (path === '/api/v1/health' && method === 'GET') {
    stream.respond({
      ':status': 200,
      'content-type': 'application/json; charset=utf-8',
      'x-protocol': 'HTTP/2.0'
    });
    stream.end(JSON.stringify({ status: 'HEALTHY', timestamp: Date.now() }));
    return;
  }

  stream.respond({ ':status': 404, 'content-type': 'application/json' });
  stream.end(JSON.stringify({ error: 'Endpoint Not Found' }));
});

// Fallback logic for HTTP/1.1 requests
gatewayServer.on('request', (req, res) => {
  // Hanya dipanggil jika stream event tidak menangani (biasanya HTTP/1.1 connections)
  if (req.httpVersionMajor === 1) {
    res.writeHead(200, { 'Content-Type': 'application/json', 'x-protocol': 'HTTP/1.1' });
    res.end(JSON.stringify({ status: 'HEALTHY_FALLBACK', protocol: 'HTTP/1.1' }));
  }
});

// ==========================================
// 2. ZERO-DEPENDENCY WEBSOCKET (RFC 6455)
// ==========================================
gatewayServer.on('upgrade', (req, socket, head) => {
  if (req.headers['upgrade']?.toLowerCase() !== 'websocket') {
    socket.destroy();
    return;
  }

  const clientKey = req.headers['sec-websocket-key'];
  if (!clientKey) {
    socket.destroy();
    return;
  }

  // Calculate Accept Hash as per RFC 6455 Spec
  const GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11';
  const acceptHash = crypto
    .createHash('sha1')
    .update(clientKey + GUID)
    .digest('base64');

  const responseHeaders = [
    'HTTP/1.1 101 Switching Protocols',
    'Upgrade: websocket',
    'Connection: Upgrade',
    `Sec-WebSocket-Accept: ${acceptHash}`
  ];

  socket.write(responseHeaders.join('\r\n') + '\r\n\r\n');

  console.log('[WEBSOCKET]: Client connected via RFC 6455 Handshake');

  // Binary Frame Parsing Engine
  socket.on('data', (buffer) => {
    // Basic Parsing of unfragmented single text frame
    const firstByte = buffer.readUInt8(0);
    const isFinal = Boolean((firstByte >> 7) & 0x01);
    const opcode = firstByte & 0x0f;

    if (opcode === 0x8) {
      // Opcode 8: Connection Close Frame
      socket.end();
      return;
    }

    if (opcode === 0x1) {
      // Opcode 1: Text Frame
      const secondByte = buffer.readUInt8(1);
      const isMasked = Boolean((secondByte >> 7) & 0x01);
      let payloadLength = secondByte & 0x7f;
      let currentOffset = 2;

      if (payloadLength === 126) {
        payloadLength = buffer.readUInt16BE(currentOffset);
        currentOffset += 2;
      } else if (payloadLength === 127) {
        // High bits disregarded for standard JS safe integers
        payloadLength = Number(buffer.readBigUInt64BE(currentOffset));
        currentOffset += 8;
      }

      if (isMasked) {
        const maskingKey = buffer.subarray(currentOffset, currentOffset + 4);
        currentOffset += 4;

        const payload = buffer.subarray(currentOffset, currentOffset + payloadLength);
        const unmaskedData = Buffer.alloc(payloadLength);

        for (let i = 0; i < payloadLength; i++) {
          unmaskedData[i] = payload[i] ^ maskingKey[i % 4];
        }

        console.log(`[WEBSOCKET_RECV]: ${unmaskedData.toString('utf-8')}`);

        // Echo response as unmasked text frame (Server-to-Client must NOT be masked)
        const responseText = `ECHO: ${unmaskedData.toString('utf-8')}`;
        const responsePayload = Buffer.from(responseText, 'utf-8');
        const frameHeader = Buffer.alloc(2);

        frameHeader.writeUInt8(0x81, 0); // FIN bit set + Opcode 1 (Text)
        frameHeader.writeUInt8(responsePayload.length, 1); // Length (<= 125 bytes)

        socket.write(Buffer.concat([frameHeader, responsePayload]));
      }
    }
  });

  socket.on('error', (err) => console.error('[WS_SOCKET_ERR]:', err));
});

// ==========================================
// 3. gRPC SERVICE ENGINE
// ==========================================
const PROTO_PATH = path.join(__dirname, 'proto', 'telemetry.proto');
const packageDefinition = protoLoader.loadSync(PROTO_PATH, {
  keepCase: true,
  longs: String,
  enums: String,
  defaults: true,
  oneofs: true
});

const telemetryProto = grpc.loadPackageDefinition(packageDefinition).telemetry;

function streamMetricsImpl(call) {
  console.log(`[gRPC_STREAM]: Metric streaming requested by client: ${call.request.service_id}`);
  const intervalTime = call.request.interval_ms || 1000;

  const intervalId = setInterval(() => {
    const mem = process.memoryUsage();
    const payload = {
      timestamp: new Date().toISOString(),
      cpu_usage: Math.random() * 100, // Simulasi metrics load
      memory_usage_mb: parseFloat((mem.heapUsed / 1024 / 1024).toFixed(2))
    };

    call.write(payload);
  }, intervalTime);

  call.on('cancelled', () => {
    console.log('[gRPC_STREAM]: Client cancelled the stream.');
    clearInterval(intervalId);
  });

  call.on('end', () => {
    console.log('[gRPC_STREAM]: Stream ended.');
    clearInterval(intervalId);
    call.end();
  });
}

const grpcServer = new grpc.Server({
  'grpc.max_receive_message_length': 1024 * 1024 * 10, // 10MB
  'grpc.max_send_message_length': 1024 * 1024 * 10,
  'grpc.keepalive_time_ms': 15000,
  'grpc.keepalive_timeout_ms': 5000,
  'grpc.keepalive_permit_without_calls': 1
});

grpcServer.addService(telemetryProto.MetricService.service, {
  StreamMetrics: streamMetricsImpl
});

// ==========================================
// BOOTSTRAP SYSTEM
// ==========================================
gatewayServer.listen(8443, () => {
  console.log('[GATEWAY]: Secure HTTPS/H2 & WS Server listening on https://localhost:8443');
});

grpcServer.bindAsync('127.0.0.1:50051', grpc.ServerCredentials.createInsecure(), (err, port) => {
  if (err) {
    console.error('[gRPC_FATAL]: Failed to bind:', err);
    return;
  }
  console.log(`[gRPC]: Service Engine active on port 127.0.0.1:${port}`);
});
```

### File 3: `client-test-suite.mjs`
```javascript
import http2 from 'node:http2';
import grpc from '@grpc/grpc-js';
import protoLoader from '@grpc/proto-loader';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// 1. Test HTTP/2 Engine
const h2Client = http2.connect('https://localhost:8443', {
  rejectUnauthorized: false // Ignore self-signed cert for testing
});

const req = h2Client.request({ ':path': '/api/v1/health' });
req.on('response', (headers) => {
  console.log('[CLIENT_H2_STATUS]:', headers[':status']);
});

req.setEncoding('utf8');
req.on('data', (chunk) => {
  console.log('[CLIENT_H2_DATA]:', chunk);
});

req.on('end', () => {
  h2Client.close();
});

// 2. Test gRPC Server Streaming
const PROTO_PATH = path.join(__dirname, 'proto', 'telemetry.proto');
const packageDefinition = protoLoader.loadSync(PROTO_PATH, { keepCase: true });
const telemetryProto = grpc.loadPackageDefinition(packageDefinition).telemetry;

const grpcClient = new telemetryProto.MetricService(
  '127.0.0.1:50051',
  grpc.credentials.createInsecure()
);

const stream = grpcClient.StreamMetrics({ service_id: 'order-service-node-01', interval_ms: 500 });

let counter = 0;
stream.on('data', (response) => {
  console.log('[CLIENT_gRPC_STREAM_RECV]:', response);
  counter++;
  if (counter >= 3) {
    console.log('[CLIENT_gRPC]: Cancelling stream after 3 items...');
    stream.cancel();
  }
});

stream.on('error', (err) => {
  // Catch cancellation code (1 = CANCELLED)
  if (err.code !== 1) {
    console.error('[CLIENT_gRPC_ERR]:', err);
  }
});
```

---

## 09. Diagram Alur Kerja ASCII: gRPC Stream vs HTTP/2 Multiplexing

```
      === HTTP/2 MULTIPLEXING ===                   === gRPC BI-DIRECTIONAL STREAM ===
  Client                         Server         Client                         Server
    |                              |              |                              |
    |---- HEADERS (Stream 1) ----->|              |---- HEADERS (Stream 1) ----->|
    |---- HEADERS (Stream 3) ----->|              |     (application/grpc)       |
    |<--- HEADERS (Stream 1) ------|              |                              |
    |---- DATA (Stream 1) -------->|              |<--- HEADERS (Stream 1) ------|
    |<--- DATA (Stream 3) ---------|              |                              |
    |<--- DATA (Stream 1) ---------|              |==== 5-Byte Framed Protobuf ==|
    |<--- HEADERS (Stream 3 FIN) --|              |---- DATA (Length-Prefixed)-->|
    |<--- HEADERS (Stream 1 FIN) --|              |<--- DATA (Length-Prefixed)---|
    |                              |              |---- DATA (Length-Prefixed)-->|
    |                              |              |<--- DATA (Length-Prefixed)---|
    |                              |              |                              |
    |                              |              |---- Trailing Headers (EOS) ->|
    |                              |              |<--- Trailing Headers --------|
    |                              |              |     (grpc-status: 0 [OK])    |
    v                              v              v                              v
 (Single TCP Connection Maintained)             (Single TCP Stream Maintained)
```

---

## 10. Analisis Trade-offs

| Aspek Desain | HTTP/1.1 | HTTP/2 | WebSocket | gRPC |
| :--- | :--- | :--- | :--- | :--- |
| **Complexity of Parsing** | **Rendah**: Teks standar, mudah di-debug via raw socket/cURL. | **Tinggi**: Membutuhkan bitwise state-machine untuk decoding frame. | **Sedang**: Membutuhkan XOR unmasking dan frame header resolution. | **Sangat Tinggi**: Memerlukan Protobuf code generation dan dynamic decoding. |
| **Proxy & Load Balancer Traversal** | **Universal**: Kompatibel dengan semua Layer-4 & Layer-7 balancer. | **Baik**: Perlu Layer-7 reverse proxy yang mendukung HTTP/2 multiplex downstream. | **Khusus**: Proxy harus mendukung upgrade headers & timeout tak terhingga. | **Tinggi**: Butuh ALPN passthrough (L4) atau native gRPC reverse proxy (Envoy). |
| **Head-of-Line (HoL) Latency** | **Tinggi**: Satu request lambat memblokir request lain dalam antrean pipeline. | **Rendah (L7)**: Multiplexed. Namun rentan TCP Packet Drop (L4 HoL). | **Nol (L7)**: Data dikirimkan secara langsung saat tersedia. | **Rendah (L7)**: Efisiensi stream independen di level aplikasi. |
| **Bandwidth Consumption** | **Sangat Boros**: Header metadata redundan berukuran besar. | **Sangat Efisien**: Kompresi Header via HPACK Table. | **Minimal**: 2-10 Byte Frame overhead per payload message. | **Optimal**: Serialisasi compact binary encoding + custom metadata. |

---

## 11. Best Practices & Antipatterns

### ✅ Best Practices
1. **Reuse gRPC Channels:** Objek `Client` gRPC menyimpan TCP pool terkelola. Jangan pernah menginisialisasi `new grpc.Client()` di setiap invocation request/controller. Jadikan sebagai static singleton.
2. **Buffer Allocation Optimization:** Gunakan `Buffer.allocUnsafe()` untuk pembuatan frame WebSocket/framing gRPC hanya jika Anda langsung menulis seluruh isi buffer untuk menghindari *memory leakage* dari heap lama. Gunakan `Buffer.alloc()` bila menyangkut boundary sekuriti.
3. **Handle Flow-Control Streams (Backpressure):** Selalu dengarkan return value dari `stream.write()` dan tunggu event `'drain'` sebelum menulis payload lanjutan ke HTTP/2 atau WebSocket streams.

### ❌ Antipatterns
1. **JSON-over-WebSocket Monolith:** Mengirimkan serialized JSON besar melalui WebSocket stream secara konstan tanpa chunking atau binary compression, membebani CPU parsing JSON di Event Loop.
2. **WebSocket Heartbeat via OS TCP Keep-Alive saja:** Mengabaikan WebSocket Ping/Pong (Opcode `0x9` dan `0xA`) dan hanya mengandalkan TCP Keep-Alive. TCP stack tidak dapat mendeteksi V8/Node.js Event Loop lockup. Gunakan application-level Ping/Pong frames.
3. **Membuka Terlalu Banyak HTTP/2 Streams secara Konkuren:** Membuka puluhan ribu concurrent streams dalam satu TCP connection dapat memicu memory exhaustion di TLS context buffer server. Batasi dengan konfigurasi `settings.maxConcurrentStreams`.

---

## 12. Security Hardening

1. **Strict TLS 1.3 Configuration:**
   Nonaktifkan cipher lama, SSLv3, TLS 1.0, dan TLS 1.1 untuk memitigasi serangan downgrade (POODLE, BEAST).
   ```javascript
   const secureOptions = {
     minVersion: 'TLSv1.3',
     honorCipherOrder: true,
     ciphers: 'TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256'
   };
   ```
2. **Mitigasi Serangan WebSocket Slowloris / Memory Exhaustion:**
   Validasi payload size saat membaca byte panjang frame sebelum buffer dialokasikan ke memori:
   ```javascript
   if (payloadLength > 1024 * 1024 * 5) { // 5MB Limit
     socket.write(Buffer.from([0x88, 0x02, 0x03, 0xEE])); // Close frame: 1006 / 1002 (Protocol Error)
     socket.destroy();
     return;
   }
   ```
3. **HTTP/2 Rapid Reset Mitigation (CVE-2023-44487):**
   Batasi laju penerimaan frame `RST_STREAM` dari satu client connection. Jika rasio request dibanding pembatalan stream abnormal, segera putuskan koneksi TCP:
   ```javascript
   let rstCounter = 0;
   stream.on('close', () => {
     if (stream.rstCode !== 0) {
       rstCounter++;
       if (rstCounter > 100) {
         stream.session.destroy(); // Hancurkan keseluruhan session TCP
       }
     }
   });
   ```

---

## 13. Observabilitas & Debugging

Gunakan native trace flags bawaan Node.js dan OpenSSL untuk melacak alur negosiasi jaringan secara mendalam.

### 1. Tracing ALPN and TLS Handshake
```bash
# Debugging TLS Session Negotiation
NODE_DEBUG=tls,https node server-enterprise.mjs

# Debugging HTTP/2 Stream & Framing Lifecycle
NODE_DEBUG=http2 node server-enterprise.mjs

# Debugging gRPC Core C-Bindings / Node Subsystem
GRPC_VERBOSITY=DEBUG GRPC_TRACE=all node client-test-suite.mjs
```

### 2. Network Probing via Native CLI Tools
```bash
# Uji Negosiasi ALPN HTTP/2
openssl s_client -connect localhost:8443 -alpn h2 -servername localhost

# Inspeksi Frame HTTP/2 via nghttp
nghttp -uv https://localhost:8443/api/v1/health

# Inspeksi Interaktif gRPC Server via gRPCurl
grpcurl -plaintext 127.0.0.1:50051 list
```

---

## 14. Benchmarking & Performance Analysis

Berikut adalah skrip benchmark untuk mengukur throughput komparatif serialisasi antara Protobuf Binary Format vs JSON Stringify Native Engine.

File: `benchmark-payload.mjs`
```javascript
import { performance } from 'node:perf_hooks';
import protobuf from 'protobufjs';

const iterations = 1_000_000;

// Setup Protobuf
const root = protobuf.Root.fromJSON({
  nested: {
    Metric: {
      fields: {
        timestamp: { id: 1, type: "string" },
        cpu_usage: { id: 2, type: "double" },
        memory_usage_mb: { id: 3, type: "double" }
      }
    }
  }
});
const MetricType = root.lookupType("Metric");

const rawPayload = {
  timestamp: new Date().toISOString(),
  cpu_usage: 88.4523,
  memory_usage_mb: 512.24
};

// Benchmark JSON.stringify
const startJson = performance.now();
let jsonSize = 0;
for (let i = 0; i < iterations; i++) {
  const serialized = JSON.stringify(rawPayload);
  jsonSize = Buffer.byteLength(serialized);
}
const endJson = performance.now();
const timeJson = endJson - startJson;

// Benchmark Protobuf Encode
const startProto = performance.now();
let protoSize = 0;
for (let i = 0; i < iterations; i++) {
  const errMsg = MetricType.verify(rawPayload);
  if (errMsg) throw Error(errMsg);
  const message = MetricType.create(rawPayload);
  const buffer = MetricType.encode(message).finish();
  protoSize = buffer.length;
}
const endProto = performance.now();
const timeProto = endProto - startProto;

console.log('--- HASIL BENCHMARK (1,000,000 Iterations) ---');
console.log(`JSON Stringify:   Time = ${timeJson.toFixed(2)}ms | Byte Size = ${jsonSize} bytes`);
console.log(`Protobuf Encode:  Time = ${timeProto.toFixed(2)}ms | Byte Size = ${protoSize} bytes`);
console.log(`Payload Reduction: ${(((jsonSize - protoSize) / jsonSize) * 100).toFixed(2)}% lebih hemat.`);
console.log(`Throughput Speedup: ${(timeJson / timeProto).toFixed(2)}x`);
```

---

## 15. Hands-on Lab Mini-Project: Hybrid Gateway Broker

### Deskripsi Masalah
Bangun proxy bridge yang menerima event notifikasi real-time dari client melalui WebSocket (Ingress), mengubah data ke serialisasi binary format gRPC, kemudian meneruskannya ke gRPC Collector Engine (Egress) dengan backpressure management.

```
[WebSocket Client] --(JSON Frames)--> [Node.js Hybrid Gateway] --(gRPC Stream)--> [Telemetry Engine]
```

### Panduan Solusi Singkat
1. Modifikasi event handler WebSocket `socket.on('data')`.
2. Saat payload utuh di-unmask, decode text JSON.
3. Tulis pesan langsung ke objek `client.StreamMetrics()` gRPC yang sedang terbuka tanpa membuat connection overhead baru.
4. Tangani error jika upstream gRPC server disconnect atau slow-consumer.

---

## 16. Automated Testing & Verification

Gunakan runtime test runner native Node.js (`node:test`) untuk memvalidasi interaksi TLS, HTTP/2 session, dan gRPC client tanpa external test suite runners.

File: `networking.test.mjs`
```