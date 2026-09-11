# Module 03: Desain Arsitektur — Chat System Real-Time (WhatsApp / Discord)

## 1. Learning Objective
Setelah menyelesaikan modul ini, Anda akan mampu:
- Merancang arsitektur sistem pesan instan berskala besar (**Chat System**) yang mendukung percakapan 1-on-1 dan group chat hingga ratusan ribu anggota.
- Memahami strategi scaling **Persistent WebSocket Connections** untuk menangani jutaan koneksi concurrent simultan.
- Mendesain subsistem status kehadiran online pengguna (**Online Presence System**) berbasis heartbeat dan distributed memory store.
- Menyelesaikan masalah pengiriman pesan grup (*Fan-Out Problem*) antara grup privat kecil (WhatsApp) vs server publik raksasa (Discord).
- Memilih database yang tepat untuk menyimpan riwayat percakapan dengan pola tulis tinggi (*Write-Heavy Sequential Log*).

## 2. Prerequisite
- Memahami protokol WebSockets dan SSE dari BAB 06 Module 02.
- Memahami Message Brokers & Streaming dari BAB 07.
- Memahami Database Sharding dan NoSQL Columnar dari BAB 05.

## 3. Concept
Membangun sistem chat real-time berbeda secara mendasar dari aplikasi web standar:
1. **Stateful vs Stateless**: Web biasa bersifat *stateless* (request-response lalu putus). Chat system bersifat **stateful**: jutaan klien mempertahankan koneksi TCP/WebSocket terbuka terus-menerus ke server gateway.
2. **Bi-directional Low Latency**: Pesan harus terkirim ke lawan bicara dalam waktu < 100 milidetik.
3. **Penyimpanan Pesan Raksasa**: Miliaran pesan dikirim per hari. Pengguna mengharapkan pesan lama dapat di-scroll tanpa batas secara mulus.

## 4. Why?
Aplikasi seperti WhatsApp, Telegram, Slack, dan Discord adalah tulang punggung komunikasi dunia. Memahami arsitektur chat melatih arsitek dalam menguasai:
- Penanganan jutaan koneksi soket jaringan yang terus hidup (*Long-Lived Socket Management*).
- Sinkronisasi state pengguna secara real-time lintas server cluster.
- Desain penyimpanan data sekuensial berkecepatan tinggi.

## 5. What?
### Komponen Utama Arsitektur:
1. **WebSocket Gateway Cluster**: Kumpulan server (biasanya ditulis dalam Go, Erlang, atau Node.js) yang bertugas menahan koneksi WebSocket jutaan pengguna ponsel.
2. **Session / Routing Table (Redis / In-Memory)**: Memetakan setiap `user_id` ke server gateway mana dia sedang terhubung (misal: `User_A -> ws-server-04`).
3. **Message Service**: Logika bisnis untuk validasi pesan, filter spam, dan persistensi database.
4. **Distributed Message Backplane (Kafka / RabbitMQ)**: Mendistribusikan pesan antar server gateway yang berbeda.
5. **Presence Service**: Melacak apakah pengguna sedang *Online*, *Offline*, atau *Away* menggunakan mekanisme Heartbeat.
6. **Chat History Storage (Apache Cassandra / ScyllaDB)**: Basis data NoSQL Wide-Column yang dioptimasi untuk penulisan sekuensial berkecepatan jutaan write per detik.
7. **Push Notification Service (FCM / APNs)**: Mengirimkan pop-up notifikasi jika pengguna penerima sedang offline (aplikasi ditutup).

## 6. How?
### Alur Pengiriman Pesan 1-on-1:
```text
[User A (Pengirim)] 
        │ (1. Kirim Pesan via WebSocket)
        ▼
[WS Server 1] ──> [Message Service] ──(2. Simpan Pesan)──> [Cassandra DB]
                         │
                         ├── (3. Cek Lokasi User B di Redis Session Table)
                         │   Hasil: User B terhubung di [WS Server 2]
                         │
                         ├── (4a. User B Online?)
                         │    └── Publish ke Message Bus ──> [WS Server 2] ──(5. WS Push)──> [User B]
                         │
                         └── (4b. User B Offline?)
                              └── Kirim Task ke ──> [Push Notification Service] ──> [FCM / APNs]
```

### Penanganan Fan-Out Grup:
- **WhatsApp Model (Grup Kecil < 256 / 1024 orang)**:
  *Fan-Out on Write (Message Inboxing)*: Saat 1 orang mengirim pesan ke grup, server menduplikasi pointer pesan ke inbox masing-masing anggota.
- **Discord Model (Server Raksasa 100.000+ member)**:
  *Fan-Out on Read (Shared Channel Log)*: Pesan hanya disimpan **satu kali** di tabel channel: `messages (channel_id, message_id, content)`. Server tidak menduplikasi pesan ke 100.000 inbox! Hanya anggota yang sedang aktif membuka channel tersebut yang menerima stream pesan via WebSocket.

## 7. Analogy
- **WebSocket Gateway = Operator Sentral Telepon Kabel**: Anda mengangkat gagang telepon dan saluran tetap terhubung ke papan operator. Operator tahu kabel nomor berapa yang tersambung ke rumah teman Anda.
- **Heartbeat Presence = Satpam yang Mengabsen Setiap 5 Detik**: Ponsel Anda mengirim sinyal "Saya masih hidup!" tiap 5 detik. Jika dalam 15 detik satpam tidak mendengar kabar Anda, status Anda diubah menjadi "Offline".

## 8. Diagram

```text
================ ARSITEKTUR REAL-TIME CHAT SYSTEM ================

[Mobile Client A] ──(WebSocket)──> [WS Gateway Node 1] ──┐
                                                           │
[Mobile Client B] ──(WebSocket)──> [WS Gateway Node 2] ───┼──> [Distributed Message Bus]
                                                           │     (Kafka / Redis PubSub)
[Mobile Client C] ──(WebSocket)──> [WS Gateway Node 3] ──┘                 │
                                                                           ▼
                                                                  [Presence Servers]
                                                                  [Chat History DB]
                                                                  [Push Notif (FCM)]
```

## 9. Simple Example: Skema Database Riwayat Chat di Cassandra
Cassandra sangat sempurna untuk chat karena data diurutkan berdasarkan `Clustering Key`:
```sql
CREATE TABLE group_messages (
    channel_id UUID,
    message_id TIMEUUID, -- Berisi timestamp presisi mikrodetik + UUID unik
    sender_id BIGINT,
    content TEXT,
    PRIMARY KEY (channel_id, message_id)
) WITH CLUSTERING ORDER BY (message_id DESC);
```
Query memuat 50 pesan terakhir:
`SELECT * FROM group_messages WHERE channel_id = ? LIMIT 50;`  
Query ini berjalan dalam **1-2 milidetik** karena data tersimpan sekuensial di satu partisi disk!

## 10. Practical Example: Mekanisme Heartbeat Presence
Jika sistem memiliki 50 juta pengguna aktif, memperbarui database status setiap detik akan membunuh database.  
**Solusi**:
1. Client mengirim sinyal `ping` setiap **10 detik**.
2. Presence Service menyetel kunci di Redis dengan masa kedaluwarsa 30 detik:
   `SET user:123:presence "online" EX 30`
3. Jika koneksi putus atau HP mati kehabisan baterai, kunci di Redis akan otomatis hangus (*expire*) setelah 30 detik tanpa perlu intervensi manual!

## 11. Real World Example
- **Discord**: Menggunakan bahasa pemrograman **Elixir / Rust** untuk menangani jutaan koneksi soket per server dan memigrasikan database chat dari MongoDB ke Cassandra, lalu ke **ScyllaDB** untuk menangani miliaran pesan per hari dengan latensi p99 konsisten.
- **WhatsApp**: Terkenal mampu menangani 2 Miliar pengguna dengan tim engineer yang sangat ramping karena memanfaatkan **Erlang / BEAM VM** yang mampu menjalankan jutaan proses konkruen ringan (*lightweight processes*) per mesin server.

## 12. Trade-offs

| Parameter | Fan-Out on Write (WhatsApp) | Fan-Out on Read (Discord) |
|---|---|---|
| **Kelebihan** | Membaca feed/inbox sangat cepat (O(1)) | Penulisan pesan sangat murah (O(1)), skala grup tak terbatas |
| **Kekurangan** | Menulis pesan grup besar sangat lambat ($O(N)$ write ke $N$ inbox) | Membaca riwayat membutuhkan query channel log |
| **Ideal Untuk** | 1-on-1 Chat & Grup Keluarga Kecil | Channel Komunitas Publik & Gamer Servers |

## 13. When To Use
- Aplikasi pesan instan, chat support pelanggan di e-commerce, fitur in-game chat multiplayer.

## 14. When NOT To Use
- Komunikasi asinkron non-interaktif seperti email massal atau buletin bulanan (gunakan SMTP / Task Queue).

## 15. Common Mistakes
1. **Menyimpan Pesan di Database Relasional Monolitik (MySQL) Tanpa Sharding**: Melakukan `JOIN` dan pagination dengan `OFFSET` pada tabel chat berisi ratusan juta baris akan membuat CPU database meledak.
2. **Koneksi WebSocket Tanpa Heartbeat (Ghost Connections)**: Ketika pengguna masuk ke terowongan kereta dan kehilangan sinyal tanpa mengirim frame close TCP, server tetap menahan koneksi tersebut di memori RAM selamanya jika tidak ada ping/pong heartbeat timeout.

## 16. Best Practices
- **End-to-End Encryption (Signal Protocol)**: Untuk chat 1-on-1 privat, pesan harus dienkripsi di perangkat pengirim dan hanya bisa didekripsi di perangkat penerima. Server chat hanya bertindak sebagai perantara biner buta (*blind broker*).
- **Client-Side Message ID (UUID)**: Buat ID pesan di perangkat ponsel sebelum dikirim untuk menjamin idempotency dan mencegah pesan terkirim ganda saat koneksi seluler tidak stabil.

## 17. Troubleshooting
- **Masalah: Server Gateway mengalami crash karena kehabisan file descriptors (OOM / Socket Error)**.
  - *Sebab*: Default limit Linux `ulimit -n` hanya 1024 koneksi soket.
  - *Solusi*: Naikkan batas limit OS di `/etc/security/limits.conf` menjadi minimal `1000000` dan lakukan tuning TCP buffer window memory (`net.ipv4.tcp_rmem`).

## 18. Hands-on Practice
Mari kita buktikan arsitektur sistem chat interaktif lengkap: WebSocket Gateway routing, Session Presence tracker berbasis heartbeat, dan Message Inboxing di `hands-on/m03/chat_system_service.js`.

## 19. Exercises & Challenge
- **Exercise**: Hitung kebutuhan memori RAM pada satu server gateway jika 1 koneksi WebSocket aktif memakan alokasi buffer kernel TCP sebesar 10 KB, dan server tersebut menampung 50.000 koneksi concurrent. (Jawaban: $50.000 \times 10\text{ KB} = 500\text{ MB RAM}$, sangat ringan!).
- **Challenge**: Rancang skema *Typing Indicator* ("Budi sedang mengetik...") yang efisien tanpa membanjiri message bus dan database.

## 20. Summary
Merancang sistem chat berskala real-time menuntut keahlian dalam mengelola koneksi soket stateful yang berumur panjang. Melalui kombinasi **WebSocket Gateway Cluster**, **Redis Presence Heartbeat**, dan pemisahan strategi **Fan-Out on Write vs Fan-Out on Read**, sistem chat mampu melayani ratusan juta pengguna dengan pesan yang terkirim dalam fraksi milidetik.
