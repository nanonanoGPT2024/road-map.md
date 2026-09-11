---
[⬅️ BAB 06 Quiz & Challenge](../BAB-06-Autentikasi-Full-Stack-dan-WebAuthn/BAB-06-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: PWA, Service Workers, & Offline-First ➡️](./Module-02-PWA-Service-Workers-Offline-First-dan-Web-Push.md)
---

# Module 01: Real-Time Architecture: WebSockets, Server-Sent Events (SSE), Pusher/Ably, & Scaling dengan Redis Pub/Sub

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- Menganalisis perbedaan mendasar antara empat paradigma komunikasi web: **Short Polling**, **Long Polling**, **Server-Sent Events (SSE)**, dan **WebSockets (Full-Duplex)**.
- Memahami tantangan arsitektural **The Serverless Real-Time Dilemma**: mengapa serverless functions transien tidak dapat menampung koneksi soket persisten dan bagaimana mengatasinya menggunakan arsitektur *Hybrid Stateful Gateway* atau layanan terkelola (Pusher, Ably, Cloudflare Durable Objects).
- Merancang dan membangun arsitektur kluster WebSocket multi-node yang diskalakan secara horizontal (*horizontal scaling*) menggunakan **Redis Pub/Sub Channel Adapter**.
- Mengimplementasikan mekanisme ketahanan jaringan real-time: **Heartbeat Protocol (Ping/Pong Frames)**, deteksi pemutusan koneksi (*Connection Drop Detection*), dan **Exponential Backoff Reconnection dengan Jitter**.
- Menangani manajemen state kehadiran pengguna (*User Presence Tracking*) dan penyiaran pesan (*Broadcast Channels / Rooms*) secara terdistribusi.

---

## 2. Prerequisite
- Memahami protokol TCP/IP dan jabat tangan HTTP (*HTTP Handshake Upgrade*).
- Memahami Event Loop dan asynchronous stream di Node.js.
- Memahami dasar-dasar Redis (In-Memory Key-Value & Pub/Sub commands: `PUBLISH`, `SUBSCRIBE`).

---

## 3. Concept
Secara historis, web bekerja dengan model **Request-Response (Pull Model)**: browser meminta data, server merespons, lalu koneksi ditutup. Jika client ingin tahu apakah ada pesan baru, client harus bertanya berulang-ulang (*polling*).

**Real-Time Architecture** mengubah pola ini menjadi **Event-Driven Push Model**: koneksi dibiarkan tetap terbuka secara terus menerus, sehingga server dapat mendorong (*push*) data baru ke browser seketika saat event terjadi di dunia nyata (seperti pesan obrolan, pergerakan kursor kolaboratif, atau pergerakan harga saham).

```
[ BROWSER CLIENT ]                                 [ SERVER APLIKASI ]
        |                                                  |
        | 1. HTTP GET /chat (Headers: Upgrade: websocket) |
        | -----------------------------------------------> |
        |                                                  | 2. 101 Switching Protocols
        | <----------------------------------------------- |
        |                                                  |
        | <============ PIPA TCP DUA ARAH (WSS) ==========>|
        | (Koneksi Persisten Terbuka Penuh, Latensi < 5ms) |
        | 3. Frame Data Real-Time (Server Push)            |
        | <----------------------------------------------- |
```

Setelah jabat tangan HTTP Upgrade disetujui (Status `101 Switching Protocols`), protokol beralih dari HTTP menjadi **WebSocket (`wss://`)**, mengalirkan frame data biner atau teks dua arah dengan overhead header hanya 2 sampai 10 bytes (jauh lebih hemat dibanding header HTTP biasa yang berukuran 500–1000 bytes).

---

## 4. Why? (Kapan Memilih SSE vs WebSockets?)

| Kriteria | Server-Sent Events (SSE) | WebSockets (WS) |
| :--- | :--- | :--- |
| **Arah Komunikasi** | **Satu Arah (Unidirectional: Server -> Client)** | **Dua Arah (Bidirectional / Full-Duplex)** |
| **Protokol Dasar** | HTTP/1.1 atau HTTP/2 murni (`text/event-stream`) | Protokol TCP khusus (`ws://`, `wss://`) |
| **Efisiensi Firewall/Proxy** | **Sangat Baik** (Bekerja di port 80/443 standar) | Kadang diblokir proxy korporat kaku |
| **Auto-Reconnection** | **Bawaan Browser (`EventSource`)** | Wajib diimplementasikan manual di JavaScript |
| **Beban Overhead** | Ringan (Memanfaatkan multiplexing HTTP/2) | Sangat Ringan (Frame header 2-10 bytes) |
| **Use Case Ideal** | Notifikasi, Live Feed Berita, AI Streaming Response (ChatGPT) | Chat dua arah, Game Multiplayer, Dokumen Kolaboratif (Figma) |

**Aturan Arsitektur Praktis**:
- Jika Anda hanya perlu mengirim data dari server ke pengguna (seperti streaming teks token ChatGPT atau notifikasi dashboard), gunakan **Server-Sent Events (SSE)**.
- Jika pengguna harus saling mengirim pesan bolak-balik dengan frekuensi tinggi (seperti chat room atau editing bersama), gunakan **WebSockets**.

---

## 5. What? (The Serverless Real-Time Dilemma & Redis Pub/Sub)

### A. Dilema Serverless Function & WebSockets
Serverless function (seperti AWS Lambda atau Vercel Function) dirancang untuk hidup singkat: bangun, layani request, lalu mati (*scale-to-zero*). 
Sebaliknya, WebSocket menuntut koneksi persisten yang hidup berjam-jam. Jika 10.000 user membuka socket ke Lambda, 10.000 instance akan berjalan terus menerus dan membuat tagihan komputasi meledak.

**Solusi Modern**:
1. **Dedicated Stateful Gateway Node**: Node.js/Go container ringan khusus untuk menampung koneksi socket (misal: Fastify-WS / Socket.io di AWS ECS / Railway / Fly.io).
2. **Managed WebSocket Services**: Layanan seperti Pusher, Ably, atau AWS API Gateway WebSockets yang mengelola soket di depan, lalu memicu webhook serverless saat ada event masuk.

### B. Masalah Multi-Node Scaling (Redis Pub/Sub Adapter)
Ketika aplikasi Anda tumbuh dan membutuhkan 3 server WebSocket (`Node A`, `Node B`, `Node C`):
- Pengguna **Alice** terhubung ke `Node A`.
- Pengguna **Bob** terhubung ke `Node C`.
- Ketika Alice mengirim chat ke Bob, `Node A` tidak memiliki koneksi socket ke Bob!
- **Solusi**: `Node A` mempublikasikan pesan ke **Redis Pub/Sub Channel**. `Node C` yang berlangganan channel tersebut menerima pesan dan meneruskannya langsung ke socket fisik Bob di browsernya.

---

## 6. How? (Implementasi Kluster WebSocket dengan Redis Pub/Sub)

### 1. Server WebSocket Node.js dengan Redis Adapter
```typescript
import { WebSocketServer, WebSocket } from "ws";
import Redis from "ioredis";

const PORT = process.env.PORT || 8080;
const wss = new WebSocketServer({ port: Number(PORT) });

// Dua koneksi Redis terpisah: satu untuk Publish, satu untuk Subscribe
const redisPublisher = new Redis(process.env.REDIS_URL);
const redisSubscriber = new Redis(process.env.REDIS_URL);

// Map lokal koneksi client di node ini: userId -> WebSocket
const localClients = new Map<string, WebSocket>();

// Berlangganan ke channel broadcast global
redisSubscriber.subscribe("GLOBAL_CHAT", (err) => {
  if (!err) console.log("Berlangganan ke Redis Channel 'GLOBAL_CHAT'");
});

// Ketika ada pesan disiarkan dari node server lain di kluster
redisSubscriber.on("message", (channel, messageStr) => {
  if (channel === "GLOBAL_CHAT") {
    const message = JSON.parse(messageStr);
    // Siarkan ke seluruh client lokal yang terhubung di server ini
    for (const [userId, clientSocket] of localClients.entries()) {
      if (clientSocket.readyState === WebSocket.OPEN) {
        clientSocket.send(JSON.stringify(message));
      }
    }
  }
});

wss.on("connection", (socket, req) => {
  const userId = new URL(req.url!, `http://${req.headers.host}`).searchParams.get("userId") || `anon_${Date.now()}`;
  localClients.set(userId, socket);

  console.log(`[NODE CONNECT] User ${userId} terhubung ke Node ini.`);

  socket.on("message", (data) => {
    const parsed = JSON.parse(data.toString());
    const payload = {
      from: userId,
      text: parsed.text,
      timestamp: new Date().toISOString(),
    };

    // Alih-alih hanya broadcast lokal, publikasikan ke REDIS agar sampai ke semua server node!
    redisPublisher.publish("GLOBAL_CHAT", JSON.stringify(payload));
  });

  socket.on("close", () => {
    localClients.delete(userId);
    console.log(`[NODE DISCONNECT] User ${userId} terputus.`);
  });
});
```

### 2. Client Resilient WebSocket dengan Heartbeat & Exponential Backoff
```typescript
// Di kode frontend browser
class ResilientWebSocketClient {
  private url: string;
  private ws: WebSocket | null = null;
  private retryAttempts = 0;
  private maxDelay = 30000; // Maksimal 30 detik
  private pingInterval: any = null;

  constructor(url: string) {
    this.url = url;
    this.connect();
  }

  private connect() {
    this.ws = new WebSocket(this.url);

    this.ws.onopen = () => {
      console.log("✅ WebSocket Terhubung!");
      this.retryAttempts = 0; // Reset counter saat berhasil terhubung
      this.startHeartbeat();
    };

    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === "PONG") return; // Tangani frame heartbeat
      console.log("Pesan Baru Masuk:", data);
    };

    this.ws.onclose = () => {
      console.warn("⚠️ Koneksi WebSocket terputus. Mencoba reconnect...");
      this.stopHeartbeat();
      this.scheduleReconnect();
    };
  }

  private startHeartbeat() {
    // Kirim PING setiap 15 detik untuk menjaga koneksi tidak diputus firewall NAT
    this.pingInterval = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: "PING" }));
      }
    }, 15000);
  }

  private stopHeartbeat() {
    clearInterval(this.pingInterval);
  }

  private scheduleReconnect() {
    this.retryAttempts++;
    // Exponential Backoff dengan Jitter Acak: delay = 2^attempts * 1000 + random(0-1000)
    const baseDelay = Math.min(Math.pow(2, this.retryAttempts) * 1000, this.maxDelay);
    const jitter = Math.random() * 1000;
    const finalDelay = baseDelay + jitter;

    console.log(`Mencoba reconnect ke-${this.retryAttempts} dalam ${Math.round(finalDelay)}ms...`);
    setTimeout(() => this.connect(), finalDelay);
  }
}
```

---

## 7. Analogy
Bayangkan dua stasiun radio di dua kota yang berbeda:
- **Komunikasi Lokal Tanpa Redis**: Pembawa acara di Stasiun Jakarta berbicara di mikrofon. Hanya pendengar yang menyetel radio ke frekuensi antena Jakarta yang mendengar suaranya. Pendengar di Surabaya yang terhubung ke pemancar Surabaya tidak mendengar apa pun (*Siloed Node Problem*).
- **Redis Pub/Sub**: Studio Jakarta dan Surabaya dihubungkan oleh kabel serat optik satelit terpusat (*Redis Pub/Sub Bus*). Saat penyiar Jakarta berbicara, suaranya dialirkan ke kabel satelit dalam hitungan milidetik, lalu dipancarkan secara serentak oleh pemancar Jakarta dan Surabaya sekaligus. Semua pendengar di seluruh nusantara mendengarkan suara yang sama di detik yang sama!

---

## 8. Diagram Arsitektur Kluster WebSocket Multi-Node

```
[ Browser Alice ]                                          [ Browser Bob ]
       |                                                          |
       | (WSS Connection)                                         | (WSS Connection)
       v                                                          v
+-----------------------+                                  +-----------------------+
| WEBSOCKET NODE A      |                                  | WEBSOCKET NODE B      |
|                       |                                  |                       |
| Alice mengirim chat:  |                                  | Menerima pesan dan    |
| "Halo Bob!"           |                                  | mendorong ke socket   |
|         |             |                                  | milik Bob             |
+---------|-------------+                                  +-----------------------+
          |                                                           ^
          | 1. PUBLISH chat_room "Halo Bob!"                          | 2. PUSH data
          v                                                           |
+-----------------------------------------------------------------------------------+
| REDIS PUB/SUB DISTRIBUTED MESSAGE BROKER                                          |
|                                                                                   |
|  Channel: `chat_room` ----------------------------------------------+             |
|  (Menyebarkan event ke seluruh instance WebSocket Server dalam kluster)           |
+-----------------------------------------------------------------------------------+
```

---

## 9. Simple Example: Server-Sent Events (SSE) di Next.js App Router

```typescript
// app/api/live-metrics/route.ts
export async function GET(request: Request) {
  const encoder = new TextEncoder();

  // ReadableStream khusus SSE
  const stream = new ReadableStream({
    start(controller) {
      const interval = setInterval(() => {
        const payload = {
          cpuUsage: (Math.random() * 100).toFixed(1),
          activeUsers: Math.floor(Math.random() * 1000),
          timestamp: new Date().toISOString(),
        };

        // Format standar SSE: "data: <JSON>\n\n"
        const sseMessage = `data: ${JSON.stringify(payload)}\n\n`;
        controller.enqueue(encoder.encode(sseMessage));
      }, 1000);

      request.signal.addEventListener("abort", () => {
        clearInterval(interval);
        controller.close();
      });
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    },
  });
}
```

---

## 10. Practical Example: Presensi Pengguna Online (Presence System)
Mengetahui siapa saja anggota tim yang sedang aktif pada dokumen kolaboratif:

```typescript
// Saat user connect: Set key di Redis dengan TTL 45 detik
async function trackUserOnline(orgId: string, userId: string) {
  const key = `presence:${orgId}:${userId}`;
  await redis.set(key, "ONLINE", "EX", 45);
}

// Client mengirim heartbeat ping setiap 20 detik untuk memperpanjang TTL
async function refreshPresenceHeartbeat(orgId: string, userId: string) {
  const key = `presence:${orgId}:${userId}`;
  await redis.expire(key, 45);
}

// Mengambil daftar seluruh user yang sedang online
async function getOnlineUsers(orgId: string) {
  const keys = await redis.keys(`presence:${orgId}:*`);
  return keys.map((k) => k.split(":")[2]);
}
```
Jika browser pengguna ditutup mendadak tanpa event `onclose`, kunci di Redis otomatis kadaluwarsa (*auto-expire*) dalam 45 detik, menjaga daftar pengguna online selalu akurat!

---

## 11. Real-World Example: Collaborative Whiteboard Kursor Synchronizer
Pada aplikasi desain seperti Miro atau Canva, koordinasi kursor mouse ribuan pengguna membutuhkan efisiensi payload tingkat tinggi:

```typescript
// Optimasi: Memadatkan payload kursor menjadi array biner ringkas
// [userId (int16), x (float32), y (float32)] -> Hanya 10 bytes per broadcast!
function serializeCursor(userId: number, x: number, y: number): ArrayBuffer {
  const buffer = new ArrayBuffer(10);
  const view = new DataView(buffer);
  view.setInt16(0, userId);
  view.setFloat32(2, x);
  view.setFloat32(6, y);
  return buffer;
}
```
Mengirim biner mentah melalui WebSocket memotong penggunaan bandwidth hingga 85% dibandingkan mengirim string JSON `{"userId": 1, "x": 100.5, "y": 200.2}`.

---

## 12. Trade-offs: Self-Hosted WebSocket vs Managed Real-Time (Pusher/Ably)

| Fitur | Self-Hosted (Node.js + Redis) | Managed Gateway (Pusher / Ably) |
| :--- | :--- | :--- |
| **Biaya Skala Besar** | **Jauh Lebih Murah (Hanya biaya server VM/ECS)** | Cenderung Sangat Mahal saat traffic jutaan pesan |
| **Beban Pemeliharaan** | Tinggi (Harus manage kluster, memory leak, proxy) | **Nol (Zero Maintenance)** |
| **Dukungan Serverless** | Butuh server perantara terpisah | **Native SDK out-of-the-box** |
| **Kustomisasi Protokol** | Bebas (Bisa biner murni, Protocol Buffers) | Terbatas pada protokol platform |
| **Global CDN Routing** | Butuh konfigurasi Anycast DNS / Geo-DNS | **Otomatis Multi-Region Global Edge** |

---

## 13. When To Use WebSockets
- Aplikasi chat interaktif, obrolan tim (Slack/Discord clone).
- Canvas kolaboratif real-time dengan update kursor berkala tinggi (Figma/Miro).
- Game online multipemain di browser.

---

## 14. When NOT To Use WebSockets
- Notifikasi sederhana atau feed berita satu arah (Gunakan SSE / HTTP/2 Push).
- Aplikasi murni serverless tanpa traffic real-time persisten (Gunakan Server Actions / TanStack React Query polling interval 10 detik).

---

## 15. Common Mistakes
1. **Reconnection Storm (Thundering Herd) Tanpa Jitter**:
   - Jika koneksi internet terputus lalu kembali normal, jutaan browser mencoba reconnect serentak di detik yang sama (`delay = 1000ms`). Server akan tumbang karena serangan DDoS tak disengaja dari client sendiri.
   - *Solusi*: Selalu tambahkan variabel acak (*Jitter*) pada interval rekoneksi.
2. **Tidak Mengimplementasikan Heartbeat (Ping/Pong)**:
   - Router Wi-Fi dan firewall NAT secara otomatis memutus koneksi TCP diam (*idle TCP connection*) setelah 60 detik tanpa memberitahu browser atau server. Klien merasa masih terhubung, padahal socket sebenarnya sudah mati (*Zombie Socket*).
3. **Mengabaikan Backpressure pada WebSocket Server**:
   - Jika client memiliki koneksi lambat sementara server membanjiri pesan jutaan byte, buffer memori server akan membengkak hingga Node.js mengalami `OutOfMemoryError`.

---

## 16. Best Practices

### Must Have
- Implementasikan pertukaran frame **Ping/Pong berkala (setiap 15–30 detik)** untuk menjaga socket tetap hidup melintasi proxy/firewall.
- Terapkan **Exponential Backoff dengan Random Jitter** di sisi client saat menangani putusnya jaringan.

### Recommended
- Gunakan Redis Pub/Sub untuk menyatukan kluster WebSocket multi-node.
- Pisahkan proses komputasi berat dari event loop WebSocket; gunakan message queue (seperti BullMQ) jika pesan membutuhkan pemrosesan AI atau database berat.

### Advanced
- Kompresi payload menggunakan per-message deflate extension atau gunakan format biner Protocol Buffers untuk payload berfrekuensi tinggi.

### Avoid
- Jangan menyimpan data status login sensitif hanya di memori instance socket. Lakukan validasi JWT saat jabat tangan awal HTTP Upgrade.

---

## 17. Troubleshooting Guide

| Gejala Masalah | Kemungkinan Akar Masalah | Solusi |
| :--- | :--- | :--- |
| Koneksi putus tepat setiap 60 detik di environment produksi. | Nginx reverse proxy atau AWS ALB memotong idle socket karena timeout default 60s. | Naikkan `proxy_read_timeout 3600s;` pada Nginx dan kirim Heartbeat Ping setiap 25 detik. |
| Pengguna di server A tidak bisa melihat pesan dari pengguna di server B. | Redis Pub/Sub adapter belum terpasang atau salah nama channel broadcast. | Pastikan seluruh instance terhubung ke Redis Pub/Sub cluster yang sama. |
| Error `1006 Connection Closed Abnormally` di browser. | Jaringan client terputus tiba-tiba atau sertifikat SSL/TLS `wss://` tidak valid. | Tangani pada event listener `ws.onclose` dan picu fungsi reconnect otomatis. |

---

## 18. Exercise
- **Easy**: Buat endpoint SSE di Node.js yang mengirimkan timestamp detik jam saat ini ke browser setiap 1 detik.
- **Medium**: Buat klien WebSocket di JavaScript yang mendeteksi putusnya koneksi dan menghitung jeda rekoneksi secara eksponensial.
- **Hard**: Implementasikan sistem chat room terisolasi (*Rooms / Namespaces*) menggunakan Redis Pub/Sub di mana pesan di room `"ROOM_A"` hanya didengar oleh anggota room tersebut.

---

## 19. Challenge
Rancang arsitektur obrolan real-time skala enterprise yang melayani 500.000 koneksi bersamaan (*concurrent sockets*): mencakup perutean Anycast Geo-DNS, layer gateway WebSocket (Go / Fastify), cluster Redis Pub/Sub sharded, dan penyimpanan riwayat obrolan asinkron ke database PostgreSQL menggunakan batching worker.

---

## 20. Summary
- Real-time mengubah web dari model *pull* pasif menjadi sistem *push* aktif berlatensi rendah.
- **Server-Sent Events (SSE)** adalah standar emas untuk aliran data satu arah (seperti AI token streaming).
- **WebSockets** adalah raja komunikasi dua arah interaktif berkecepatan tinggi.
- **Redis Pub/Sub** adalah jembatan penghubung yang memungkinkan kluster server WebSocket berkomunikasi satu sama lain secara horizontal, menembus batas isolasi server tunggal.

---

## Hands-on Practice: Simulasi Full-Stack WebSocket Multi-Node & Redis Pub/Sub
Jalankan simulator kluster WebSocket multi-server, penyiaran pesan Redis, dan rekoneksi exponential backoff mandiri:

```bash
node Full-Stack/BAB-07-Real-Time-WebSockets-dan-PWA-Offline/hands-on/m01/fullstack_websocket_redis_pubsub_sim.js
```

---
[⬅️ BAB 06 Quiz & Challenge](../BAB-06-Autentikasi-Full-Stack-dan-WebAuthn/BAB-06-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: PWA, Service Workers, & Offline-First ➡️](./Module-02-PWA-Service-Workers-Offline-First-dan-Web-Push.md)
---
