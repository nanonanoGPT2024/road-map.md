# MODULE 02: Real-time Communication (WebSockets, SSE, Polling, & Webhooks)

## 1. Learning Objective
Setelah menyelesaikan module ini, Anda mampu:
1. Membedakan secara arsitektural 5 mekanisme komunikasi real-time: **Short Polling**, **Long Polling**, **Server-Sent Events (SSE)**, **WebSockets**, dan **Webhooks**.
2. Mengidentifikasi kebutuhan arah aliran data: **Full-Duplex (Dua Arah Simultan)** vs **Half-Duplex** vs **Unidirectional Push (Satu Arah dari Server)**.
3. Menjelaskan proses **HTTP-to-WebSocket Protocol Upgrade Handshake** dan efisiensi framing biner (overhead 2-10 bytes vs 1 KB HTTP header).
4. Merancang arsitektur **Horizontal Scaling WebSocket Cluster** menggunakan backbone **Redis Pub/Sub**.
5. Menjalankan pengujian langsung komparasi efisiensi Long Polling vs SSE vs WebSockets menggunakan hands-on script.

---

## 2. Prerequisite
- Telah menyelesaikan [BAB 06 — Module 01: REST vs GraphQL vs gRPC](./Module-01-REST-GraphQL-dan-gRPC.md).
- Memahami konsep dasar soket koneksi TCP dua arah (*bidirectional TCP socket*).

---

## 3. Concept
Protokol HTTP tradisional dirancang berdasarkan model **Request-Response** yang diinisiasi oleh klien (*Client-Pull*): Server tidak memiliki cara standar untuk mengirimkan data secara proaktif ke browser tanpa adanya permintaan dari browser terlebih dahulu.

Dalam aplikasi modern seperti live chat (WhatsApp/Discord), ticker pergerakan harga saham, kolaborasi dokumen (Google Docs), dan notifikasi live (pesanan ojek online mendekat), sistem membutuhkan **Real-time Communication**: kemampuan mentransmisikan data dari server ke klien seketika saat peristiwa (*event*) terjadi dengan latensi sub-detik.

---

## 4. Why? (Mengapa Short Polling Merupakan Bencana Skalabilitas?)

```text
       [ PERBANDINGAN ALUR SHORT POLLING vs WEBSOCKET ]
       
   SHORT POLLING (Membuang 99% Bandwidth):
   Client ──(GET /messages: Ada pesan baru?)──▶ Server (Tidak ada)  [+1KB HTTP Headers]
   Client ──(GET /messages: Ada pesan baru?)──▶ Server (Tidak ada)  [+1KB HTTP Headers]
   Client ──(GET /messages: Ada pesan baru?)──▶ Server (Tidak ada)  [+1KB HTTP Headers]
   Client ──(GET /messages: Ada pesan baru?)──▶ Server (Ada! Ini dia)
   
   -----------------------------------------------------------------------------------
   
   WEBSOCKET (1x Handshake, Koneksi Tetap Terbuka Selamanya):
   Client ──(Upgrade: websocket)──────────────▶ Server (101 Switching Protocols)
   [ KONEKSI PERSISTEN TCP FULL-DUPLEX TERBENTUK ]
   Server ──(Push Pesan Baru Seketika)────────▶ Client [Hanya 2 Bytes Overhead!]
```

### Hitungan Kerugian Short Polling:
Jika 1 juta pengguna membuka aplikasi dan polling setiap 2 detik:
- Database menerima **500.000 QPS query kosong** tanpa hasil.
- Server membuang gigabyte bandwidth hanya untuk mengirimkan HTTP header berulang (`User-Agent`, `Cookies`, `Content-Type`) tanpa membawa data apa pun!

---

## 5. What? (Tabel Komparasi 5 Paradigma Real-time)

| Teknologi | Arah Data | Protokol | Overhead Frame | Dukungan Reconnect | Firewall / Proxy Friendly | Use Case Ideal |
|---|---|---|---|---|---|---|
| **Short Polling** | Client -> Server | HTTP/1.1 | Sangat Tinggi (~1 KB/req) | Manual di kode | Sangat Baik (HTTP murni) | Dashboard metrik sederhana |
| **Long Polling** | Client -> Server | HTTP/1.1 | Tinggi | Manual di kode | Sangat Baik | Fallback legacy browser |
| **Server-Sent Events (SSE)** | **Server -> Client** (Satu Arah) | HTTP/2 (`text/event-stream`) | Sangat Rendah | **Bawaan Browser (Otomatis)** | **Sangat Baik** (Berjalan di port 443 standar) | Live Score, Notifikasi, Status AI Streaming |
| **WebSockets** | **Dua Arah Simultan (Full-Duplex)** | TCP (`ws://` & `wss://`) | **Ultra-Rendah (2-10 Bytes)** | Manual (Heartbeat Ping-Pong) | Butuh konfigurasi LB khusus | Chat real-time, Game online, Trading |
| **Webhooks** | **Server -> Server** (Event Push) | HTTP POST | Standar HTTP | Retry backoff sistem | Sangat Baik | Notifikasi payment gateway (Stripe/Midtrans) |

---

## 6. How? (Arsitektur Scaling WebSocket Multi-Node)

### Masalah Skalabilitas WebSocket:
Koneksi WebSocket bersifat **Stateful**:
- Klien A terhubung dan memegang socket TCP di **Server Node 1**.
- Klien B terhubung dan memegang socket TCP di **Server Node 2**.
Ketika Klien A mengirim pesan chat ke Klien B, Server Node 1 tidak memiliki koneksi soket langsung ke Klien B!

### Solusi Arsitektur: Redis Pub/Sub Backbone

```text
[ Client A ]                                                   [ Client B ]
     │ (Koneksi Socket A)                                           ▲ (Koneksi Socket B)
     ▼                                                              │
+-------------------+                                      +-------------------+
|  GATEWAY NODE 1   |                                      |  GATEWAY NODE 2   |
+---------+---------+                                      +---------+---------+
          │                                                          ▲
          ├── 1. Publish: "Pesan ke B"                               │ 3. Terima pesan &
          │                                                          │    kirim ke Socket B
          ▼                                                          │
    =======================================================================
                        [ REDIS PUB/SUB MESSAGE BACKBONE ]
                         Channel: "chat:channel_global"
    =======================================================================
```

---

## 7. Analogy: Berbagai Cara Menerima Berita
- **Short Polling:** Anda menelepon resepsionis hotel setiap 10 detik: *"Apakah paket saya sudah sampai?"* Resepsionis menjawab: *"Belum"*. Sepuluh detik kemudian Anda menelepon lagi dengan pertanyaan yang sama.
- **Long Polling:** Anda menelepon resepsionis hotel dan berkata: *"Saya tunggu di telepon ini, jangan ditutup sampai paket saya tiba!"*
- **Server-Sent Events (SSE):** Seperti **Mendengarkan Radio FM**. Anda menyalakan radio (koneksi terbuka satu arah). Stasiun radio menyiarkan informasi berita breaking news seketika saat ada kejadian. Anda hanya mendengarkan dan tidak berbicara kembali lewat radio tersebut.
- **WebSockets:** Seperti **Panggilan Telepon Dua Arah**. Saluran kabel telepon tersambung langsung. Anda dan lawan bicara bisa saling berbicara dan menimpali secara bersamaan tanpa jeda (*Full-Duplex*).
- **Webhooks:** Anda meninggalkan nomor handphone di kantor pos dan pulang ke rumah. Saat paket datang, kantor pos mengirim SMS notifikasi ke handphone Anda (*Server-to-server callback*).

---

## 8. Diagram: Alur WebSocket Upgrade Handshake

```text
[ Browser Client ]                                     [ Backend Server ]
        │                                                       │
        ├── 1. GET /chat HTTP/1.1                               │
        │      Host: app.com                                    │
        │      Upgrade: websocket                               │
        │      Connection: Upgrade                              │
        │      Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==     │
        │      Sec-WebSocket-Version: 13                        │
        │──────────────────────────────────────────────────────▶│
        │                                                       │ (Validasi Key)
        │◀──────────────────────────────────────────────────────┤
        │      HTTP/1.1 101 Switching Protocols                 │
        │      Upgrade: websocket                               │
        │      Connection: Upgrade                              │
        │      Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=│
        │                                                       │
        ▼                                                       ▼
   [ PROTOKOL HTTP DIHENTIKAN -> BERUBAH MENJADI MURNI TCP WEBSOCKET FRAME ]
        │═══════════════════════════════════════════════════════│
        │  Frame Data Biner / Teks Ringan (Overhead 2 Bytes)   │
```

---

## 9. Simple Example: Implementasi Server-Sent Events (SSE)
SSE sangat sederhana karena berjalan di atas protokol HTTP standar:
```javascript
// Endpoint SSE di Node.js Express
app.get('/events', (req, res) => {
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');

  // Kirim event secara berkala ke browser
  const timer = setInterval(() => {
    res.write(`data: ${JSON.stringify({ score: "Liverpool 2 - 1 Chelsea", time: "75'" })}\n\n`);
  }, 5000);

  req.on('close', () => clearInterval(timer));
});
```

---

## 10. Practical Code Example
Lihat perbandingan eksekusi teknis antara Long Polling, SSE, dan WebSockets pada:
`System-Design/BAB-06-Protokol-Komunikasi/hands-on/m02/realtime_comparison.js`

---

## 11. Real World Example: Discord Chat vs ChatGPT Streaming vs Uber Ride Tracking
- **Discord Voice & Text Chat:** Discord mengelola ratusan juta pengguna online bersamaan. Mereka menggunakan **WebSockets** yang di-scale menggunakan cluster Elixir/Erlang (*BEAM Virtual Machine*) yang sangat efisien dalam menangani jutaan koneksi soket konkuren ringan.
- **ChatGPT Streaming (OpenAI):** Saat ChatGPT menghasilkan teks jawaban kata-demi-kata, OpenAI **TIDAK menggunakan WebSockets**. Mereka menggunakan **Server-Sent Events (SSE)** karena komunikasinya bersifat satu arah murni dari server ke browser, berjalan mulus di atas HTTP/2, dan tidak bermasalah dengan proxy perusahaan.
- **Stripe & GitHub Webhooks:** Saat pembayaran kartu kredit sukses, server Stripe mengirimkan HTTP POST payload JSON ke endpoint server merchant (`https://toko.com/api/webhooks/stripe`) dengan tanda tangan HMAC (*Signature Verification*) untuk menjamin keaslian pengirim.

---

## 12. Trade-offs (WebSockets vs Server-Sent Events)

| Aspek | WebSockets (`ws://`) | Server-Sent Events (SSE) |
|---|---|---|
| **Arah Komunikasi** | **Dua Arah Simultan (Bidirectional)** | **Satu Arah (Server-ke-Client)** |
| **Kompleksitas Protokol** | Membutuhkan TCP socket handling khusus | Berjalan di atas HTTP standar murni |
| **Dukungan Proxy / Load Balancer** | Sering terputus oleh corporate firewall / proxy | 100% kompatibel dengan seluruh Load Balancer |
| **Beban Baterai Mobile** | Lebih boros baterai (koneksi raw TCP aktif) | Sangat hemat (mengikuti multiplexing HTTP/2) |
| **Format Data** | Teks UTF-8 dan Biner Murni (ArrayBuffer) | Teks murni UTF-8 |

---

## 13. When To Use What
- **Gunakan WebSockets jika:** Anda membangun aplikasi yang membutuhkan input frekuensi tinggi dua arah dari klien dan server secara bersamaan (Multiplayer Game, Live Chat Group, Whiteboard interaktif Figma).
- **Gunakan Server-Sent Events (SSE) jika:** Aliran data bersifat satu arah dari server ke klien (Live Sports Ticker, Notifikasi Dashboard, Streaming Token LLM AI, Status Monitoring Server).
- **Gunakan Webhooks jika:** Komunikasi terjadi antar-server secara asinkron (*Asynchronous Server-to-Server Event Delivery*).

---

## 14. When NOT To Use WebSockets
- **Jangan gunakan WebSockets untuk sekadar menampilkan notifikasi lonceng atau teks streaming AI:** Menggunakan WebSockets untuk komunikasi satu arah menambah kerumitan pengelolaan cluster, load balancer, dan reconnections tanpa manfaat teknis yang relevan. Gunakan **SSE**!

---

## 15. Common Mistakes
1. **Tidak Memasang Ping/Pong Heartbeat pada WebSockets:** Jika koneksi idle selama 60 detik tanpa data, firewall atau Cloud Load Balancer (seperti AWS ALB) akan memutus koneksi secara sepihak (*Silent Drop*). Klien mengira soket masih hidup, padahal sudah mati!
2. **Thundering Herd saat Mass Reconnection:** Saat 1 server WebSocket crash dan restart, 100.000 klien secara serentak mencoba menyambung ulang di detik yang sama. Server baru langsung tumbang seketika. Selalu pasang **Exponential Backoff dengan Random Jitter** pada logika reconnect klien!
3. **Mengabaikan Limit File Descriptors (Sockets) di Linux:** Setiap koneksi TCP WebSocket memakan 1 File Descriptor (FD). Default limit Linux adalah 1.024 socket. Server akan melempar error `Too many open files` jika `ulimit -n` tidak dinaikkan ke 1.000.000!

---

## 16. Best Practices

- **Must Have:**
  - Pasang mekanisme **Heartbeat Ping/Pong (setiap 30-45 detik)** pada implementasi WebSocket.
  - Terapkan **Exponential Backoff + Jitter** pada sisi klien untuk rekoneksi otomatis.
- **Recommended:**
  - Gunakan **Redis Pub/Sub** atau **Kafka** sebagai backbone penyiaran pesan antar-node WebSocket gateway.
- **Advanced:**
  - Tuning kernel Linux untuk server WebSocket:
    `fs.file-max = 2097152` dan `net.ipv4.tcp_max_syn_backlog = 8192`.
- **Avoid / Overengineering:**
  - Membangun custom binary protocol di atas WebSockets jika payload Anda hanya berupa JSON chat sederhana.

---

## 17. Troubleshooting Guide
```text
Gejala: Koneksi WebSocket terputus tepat setiap 60 detik sekali di lingkungan cloud.
-----------------------------------------------------------------------------------
Penyebab:
AWS ALB / Nginx Reverse Proxy memiliki idle connection timeout default sebesar 60 detik. Jika tidak ada paket yang lewat, proxy memutuskan socket TCP.

Solusi:
1. Naikkan Idle Timeout di Load Balancer (misal menjadi 3600 detik).
2. Kirimkan pesan Ping/Pong (Heartbeat Frame) dari server ke client setiap 30 detik:
   ws.ping(); // Menjaga socket tetap hidup di mata Load Balancer.
```

---

## 18. Hands-on Lab: Simulator Real-time (Long Polling vs SSE vs WebSockets)

File lab sudah disiapkan di:
`System-Design/BAB-06-Protokol-Komunikasi/hands-on/m02/realtime_comparison.js`

### Jalankan Uji Coba:
Buka terminal dan jalankan:
```bash
node System-Design/BAB-06-Protokol-Komunikasi/hands-on/m02/realtime_comparison.js
```

### Yang Ditampilkan Script Ini:
1. Menyimulasikan pola **Long Polling**: Request tertahan sampai event muncul, lalu koneksi tertutup dan wajib dibuka ulang (biaya overhead tinggi).
2. Menyimulasikan pola **Server-Sent Events (SSE)**: Satu koneksi persisten HTTP yang memancarkan event streaming secara kontinu tanpa rekoneksi.
3. Menyimulasikan pola **WebSocket Full-Duplex**: Pertukaran pesan dua arah berkecepatan tinggi dengan overhead frame minimal.

---

## 19. Exercises (Latihan)

### Level 1 (Easy):
Sebutkan perbedaan mendasar antara *Server-Sent Events (SSE)* dan *WebSockets* dalam hal arah transmisi data!

### Level 2 (Medium):
Sebuah aplikasi web kolaborasi dokumen (seperti Google Docs) memiliki 50.000 pengguna aktif yang mengetik bersamaan.
1. Mengapa WebSockets adalah pilihan paling tepat untuk fitur pengetikan kolaboratif ini?
2. Jika server backend di-deploy menggunakan 5 instance container di balik Load Balancer, jelaskan mengapa kita membutuhkan message broker (seperti Redis Pub/Sub) agar pengguna di Container 1 bisa melihat ketikan pengguna di Container 3!

### Level 3 (Hard):
Jelaskan fenomena **Thundering Herd Reconnection Storm** pada sistem chat saat data center mengalami gangguan jaringan sesaat! Tuliskan formula matematika logika rekoneksi klien yang menggunakan **Exponential Backoff dengan Full Jitter** untuk melindungi server dari serangan denial-of-service tidak sengaja oleh klien sendiri!

---

## 20. Summary & Knowledge Check
- [ ] Memahami inefisiensi Short Polling dan kelemahan Long Polling.
- [ ] Menguasai arsitektur dan use-case Server-Sent Events (SSE).
- [ ] Menguasai protokol WebSocket Handshake dan komunikasi Full-Duplex.
- [ ] Memahami arsitektur horizontal scaling WebSocket menggunakan Redis Pub/Sub.
- [ ] Menguasai pencegahan dead socket via Ping/Pong Heartbeat dan Exponential Backoff Jitter.
