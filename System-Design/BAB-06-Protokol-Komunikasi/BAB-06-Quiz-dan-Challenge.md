# BAB 06 — Evaluasi, Quiz, & Chapter Challenge
## Protokol Komunikasi & Antar Layanan

---

## 🎯 Ringkasan Bab

Dalam Bab ini, kita telah membedah lapisan komunikasi yang menjadi urat nadi dari seluruh sistem terdistribusi modern:
1. **REST vs GraphQL vs gRPC**: Memahami trade-off efisiensi serialisasi biner vs fleksibilitas schema, multiplexing HTTP/2 vs overhead HTTP/1.1 JSON, serta kapan GraphQL menyelesaikan under-fetching/over-fetching pada mobile frontend.
2. **Real-time Communication**: Mekanisme duplex WebSockets vs unidirectional Server-Sent Events (SSE), polling overhead vs persistent connection cost, serta pattern distributed pub/sub backplane (Redis Streams/NATS) untuk scaling WebSockets horizontal.

---

## 🧠 Knowledge Check

### Saya Harus Memahami:
- [ ] Perbedaan fundamental antara HTTP/1.1 (head-of-line blocking pada level koneksi) dan HTTP/2 (multiplexing over single TCP connection).
- [ ] Mengapa gRPC + Protobuf jauh lebih cepat (3x - 10x) daripada REST + JSON untuk komunikasi internal microservices.
- [ ] Kapan GraphQL tepat digunakan (BFF / client-driven aggregate) dan mengapa GraphQL berbahaya jika dipasang tanpa depth limiting & query cost analysis.
- [ ] Kapan memilih SSE (Server-Sent Events) daripada WebSockets (unidirectional data stream vs bidirectional high-frequency).
- [ ] Arsitektur stateful WebSockets pada cluster server di balik Load Balancer (kebutuhan Sticky Sessions dan Message Backplane).

### Saya Tidak Perlu Menghafal:
- Format biner spesifik dari encoding varint Protocol Buffers (cukup pahami tagging integer & field numbers).
- Header low-level frame WebSocket (FIN bit, Masking key) — abstraksi driver TCP/WebSocket mengurus hal ini.

### Saya Harus Bisa Melakukan:
- [ ] Memilih protokol yang tepat berdasarkan use case sistem (B2B API, Mobile BFF, Internal RPC, Realtime Dashboard).
- [ ] Mendesain arsitektur WebSocket cluster dengan Redis Pub/Sub backplane.
- [ ] Menghitung kebutuhan memory dan koneksi concurrent untuk ribuan client real-time.

---

## ❓ Quiz Evaluasi

### Bagian A: Pertanyaan Konseptual Fundamental (5 Soal)
1. **Mengapa gRPC menggunakan Protocol Buffers alih-alih JSON sebagai format payload default?**
2. **Apa kelemahan utama dari Short Polling dibandingkan Server-Sent Events (SSE) saat memantau status pembayaran secara real-time?**
3. **Mengapa GraphQL dapat memicu masalah database $N+1$ query jika resolver tidak dioptimasi?**
4. **Apa fungsi dari WebSocket Handshake awal yang menggunakan HTTP Status Code `101 Switching Protocols`?**
5. **Apa yang dimaksud dengan Connection Multiplexing pada HTTP/2 yang dimanfaatkan oleh gRPC?**

### Bagian B: Analisis & Intermediate (5 Soal)
6. **Dalam arsitektur Microservices berskala ribuan RPC/detik, mengapa REST over HTTP/1.1 menyebabkan pemborosan resource socket (TIME_WAIT socket exhaustion)?**
7. **Jika sebuah aplikasi dashboard saham hanya membutuhkan data harga turun dari server ke client tanpa interaksi balik, mengapa SSE lebih disukai daripada WebSockets?**
8. **Bagaimana cara mencegah pengguna mengeksekusi nested query jahat pada GraphQL endpoint yang dapat melumpuhkan database (misal: `author { books { author { books ... } } }`)?**
9. **Mengapa Load Balancer L4 (TCP) kesulitan melakukan load balancing merata pada traffic gRPC jika dibandingkan dengan Load Balancer L7 (HTTP/2)?**
10. **Ketika 10 instance WebSocket Server berjalan di Kubernetes, apa peran Redis Pub/Sub ketika User A pada Server 1 mengirim pesan ke User B yang terhubung ke Server 2?**

### Bagian C: Scenario-Based System Architecture (3 Soal)
11. **Skenario 1: FinTech Core Banking vs Mobile App**  
   Sebuah bank digital melayani jutaan pengguna aplikasi mobile dan memiliki 40 microservices internal.
   - Protokol apa yang Anda rekomendasikan untuk:
     a. Mobile App ke API Gateway?
     b. API Gateway ke Core Account Service & Transaction Service?
     c. Fitur notifikasi transfer masuk di layar HP pengguna?
   - Berikan justifikasi teknis untuk masing-masing pilihan.

12. **Skenario 2: Crypto Trading Exchange Engine**  
   Platform crypto exchange memiliki matching engine dengan order book yang berubah 50.000 kali per detik.
   - Bagaimana arsitektur distribusi data order book dari backend ke 100.000 browser trader secara simultan tanpa membuat browser crash atau server overload?
   - Diskusikan strategi throttling, framing, dan pemilihan protokol.

13. **Skenario 3: IoT Telemetry Ingestion Pipeline**  
   500.000 armada truk mengirim data GPS dan sensor suhu tiap 5 detik.
   - Apakah Anda akan memilih REST, WebSockets, gRPC, atau MQTT?
   - Mengapa REST HTTP/1.1 berpotensi menyebabkan battery drain pada perangkat IoT dan server handshake overhead tinggi?

---

## 🏆 Chapter Challenge: Distributed Realtime Collaborative Canvas Architecture

### Problem Statement
Anda diminta merancang subsistem komunikasi untuk aplikasi kolaborasi desain mirip Figma / Miro, di mana 100 desainer dapat mengedit kanvas yang sama secara bersamaan (melihat kursor mouse satu sama lain bergerak real-time dan perubahan objek vector instan).

### Requirements:
1. **Low Latency**: Pergerakan kursor mouse antar user harus tersinkronisasi dalam waktu < 50ms.
2. **Conflict Resolution**: Jika 2 user memindahkan kotak yang sama di saat yang sama, tidak boleh ada state yang corrupt.
3. **Scalability**: Mendukung 10.000 ruangan kanvas aktif secara bersamaan.
4. **Resilience**: Jika koneksi internet client putus sejenak (misal 5 detik di mobile hotspot), canvas harus otomatis reconnect dan menyelaraskan state delta tanpa reload seluruh halaman.

### Deliverables:
- Diagram arsitektur komunikasi (Client, LB, WebSocket Server nodes, Message Backplane, Storage).
- Pemilihan protokol (WebSocket vs WebRTC data channels vs gRPC).
- Strategi state sync (Operational Transformation / CRDTs vs Server authoritative).
- Rencana kapasitas memory & CPU backend.
