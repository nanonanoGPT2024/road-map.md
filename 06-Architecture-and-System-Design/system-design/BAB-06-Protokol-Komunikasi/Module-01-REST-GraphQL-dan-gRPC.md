# MODULE 01: REST vs GraphQL vs gRPC

## 1. Learning Objective
Setelah menyelesaikan module ini, Anda mampu:
1. Membandingkan secara teknis dan performa arsitektur **REST (HTTP/1.1 JSON)**, **GraphQL (Query-Driven)**, dan **gRPC (HTTP/2 Protocol Buffers)**.
2. Mendiagnosa masalah klasik REST: **Over-fetching** (mengambil data berlebih) dan **Under-fetching / N+1 Problem** (membutuhkan panggilan beruntun).
3. Menjelaskan efisiensi serialisasi biner **Protocol Buffers (Protobuf)** dibandingkan teks JSON murni.
4. Menganalisis fitur **HTTP/2 Transport**: Multiplexing, Header Compression (HPACK), dan Server Streaming.
5. Menjalankan benchmark langsung ukuran payload dan latensi serialisasi JSON vs Protobuf menggunakan hands-on script.

---

## 2. Prerequisite
- Telah menyelesaikan [BAB 03: Traffic Management, Load Balancing, & Gateway](../BAB-03-Traffic-Management-Load-Balancing/).
- Memahami konsep dasar protokol TCP, HTTP request-response, dan serialisasi data.

---

## 3. Concept
Dalam sistem terdistribusi modern, bagaimana komponen sistem saling bertukar informasi menentukan efisiensi jaringan (*bandwidth efficiency*), latensi komputasi CPU, dan kenyamanan kolaborasi antar-tim engineer (*Developer Experience*).

Tiga paradigma komunikasi dominan:
1. **REST (Representational State Transfer):** Arsitektur berbasis resource yang memanfaatkan metode HTTP standar (`GET`, `POST`, `PUT`, `DELETE`) dan payload teks JSON. Standar industri untuk API publik.
2. **GraphQL:** Bahasa query untuk API yang memungkinkan klien meminta secara presisi hanya data yang dibutuhkan dalam 1 kali request.
3. **gRPC (Google Remote Procedure Call):** Framework RPC berkinerja tinggi berbasis protokol **HTTP/2** dan skema biner **Protocol Buffers (Protobuf)**. Standar industri komunikasi internal antar-microservices (*East-West traffic*).

---

## 4. Why? (Mengapa REST JSON Tidak Cukup untuk Microservices?)

### Overhead Teks JSON & Protokol HTTP/1.1
Ketika sebuah sistem memiliki 500 microservices yang saling bertukar jutaan pesan per detik di dalam cluster:
1. **Inefisiensi Serialisasi Teks JSON:** JSON adalah format berbasis teks yang boros karakter (kunci string berulang, tanda kutip, koma, spasi). Mem-parsing string JSON memakan siklus CPU yang besar di setiap hop microservice!
2. **Head-of-Line Blocking pada HTTP/1.1:** HTTP/1.1 membutuhkan satu koneksi TCP terpisah untuk setiap request paralel, atau request berikutnya harus mengantre menunggu respon request sebelumnya selesai (*Head-of-Line Blocking*).
3. **Ketiadaan Kontrak Tipe Kuat (*No Strict Schema*):** JSON bersifat dinamis. Jika Service A mengubah nama field dari `user_id` menjadi `userId`, Service B yang memanggilnya bisa crash seketika saat runtime tanpa deteksi di waktu kompilasi (*Type Safety Failure*).

Dengan **gRPC & Protobuf**:
- Payload dienkode ke biner murni (ukuran terpangkas **60% - 80%**).
- Menggunakan 1 koneksi TCP tunggal yang di-multiplexing via HTTP/2 (ratusan request/response paralel tanpa blocking).
- Skema terdefinisi kaku di file `.proto` yang menghasilkan kode client/server otomatis dalam berbagai bahasa (*Strict Type Safety*).

---

## 5. What? (Tabel Perbandingan Komprehensif: REST vs GraphQL vs gRPC)

| Parameter | REST | GraphQL | gRPC |
|---|---|---|---|
| **Protokol Transport** | HTTP/1.1 atau HTTP/2 | Biasanya HTTP/1.1 atau HTTP/2 | **Wajib HTTP/2** murni |
| **Format Payload** | JSON, XML (Teks) | JSON (Teks) | **Protocol Buffers (Biner)** |
| **Model Desain** | Berorientasi Resource (`/users/1`) | Berorientasi Query Data (`query { user }`) | Berorientasi Aksi RPC (`UserService.GetUser()`) |
| **Efisiensi Payload** | Sedang (Sering Over-fetching) | **Sangat Tinggi** (Presisi diminta klien) | **Ekstrem Tinggi** (Biner padat) |
| **Kinerja & Latensi** | Standar (~5-20 ms) | Sedang (Overhead parsing query di server) | **Ultra-Cepat** (~0.5 - 2 ms) |
| **Streaming Support** | Terbatas (SSE / WebSockets) | GraphQL Subscriptions (WebSocket) | **Native 4 Model** (Unary, Client, Server, Bi-di) |
| **Dukungan Browser** | Universal (100% didukung) | Universal (didukung via HTTP POST) | Terbatas (Butuh gRPC-Web Proxy) |
| **Use Case Ideal** | Public API, Webhook, Mobile app umum | Frontend Dashboard, Aggregator BFF | **Komunikasi Antar-Microservices (East-West)** |

---

## 6. How? (Over-fetching, Under-fetching, & Protocol Buffers)

### A. Anatomi Masalah REST: Over-fetching & Under-fetching

```text
[ SKENARIO: Aplikasi Mobile hanya butuh menampilkan Nama Pengguna dan 1 Foto ]

1. MASALAH OVER-FETCHING (REST):
   GET /api/v1/users/101
   Backend mengembalikan 50 kolom (alamat, KTP, no telepon, riwayat login, tanggal lahir).
   -> 95% bandwidth internet seluler terbuang sia-sia!

2. MASALAH UNDER-FETCHING & N+1 PROBLEM (REST):
   Aplikasi butuh menampilkan nama user dan 5 judul postingan terakhirnya:
   - Request 1: GET /api/v1/users/101 (Mendapatkan list 5 post IDs)
   - Request 2: GET /api/v1/posts/1
   - Request 3: GET /api/v1/posts/2
   - Request 4: GET /api/v1/posts/3 ... (Butuh 6 round-trip HTTP berurutan!)

3. SOLUSI DENGAN GRAPHQL:
   POST /graphql
   Body: query { user(id: 101) { name, avatar, posts(limit: 5) { title } } }
   -> 1 kali request, 0 bytes data berlebih, 0 round-trip tambahan!
```

---

### B. Keajaiban Biner Protocol Buffers (gRPC)
Pada JSON:
```json
{"user_id": 101, "name": "Budi", "is_active": true}
// Ukuran: 52 Bytes teks UTF-8 mentah!
```
Pada Protocol Buffers (`.proto`):
```protobuf
syntax = "proto3";
message User {
  int32 user_id = 1;
  string name = 2;
  bool is_active = 3;
}
```
Protobuf tidak menyertakan nama field string seperti `"user_id"`. Protobuf hanya menyematkan nomor field integer (1, 2, 3) dan tipe data menggunakan teknik **Varint Encoding**:
$$\text{Ukuran Payload Protobuf} \approx \mathbf{10 \text{ Bytes!}} \quad (\text{Hemat } 80\% \text{ Bandwidth})$$

---

## 7. Analogy: Cara Memesan Makanan di Restoran
- **REST:** Seperti membeli Paket Nasi Ayam di restoran cepat saji. Paket datang lengkap dengan nasi, ayam, kentang, dan soda. Anda hanya lapar ingin ayamnya saja, tetapi Anda terpaksa menerima dan membayar seluruh isi paket (*Over-fetching*). Jika ingin saus ekstra, Anda harus antre di kasir kedua (*Under-fetching*).
- **GraphQL:** Seperti restoran prasmanan (*All-You-Can-Eat Buffet*). Anda membawa piring sendiri dan hanya mengambil 1 potong ayam dan 2 sendok nasi. Tidak ada makanan berlebih yang mubazir di piring Anda.
- **gRPC:** Seperti saluran pipa tabung pneumatic berkecepatan tinggi antara dapur koki dan gudang bahan makanan. Koki tidak berbicara menggunakan bahasa manusia, melainkan menekan tombol kode biner instan (*Code 01-A-03*), dan seketika bahan makanan melesat keluar dari tabung pipa dalam 1 detik.

---

## 8. Diagram: HTTP/1.1 vs HTTP/2 Multiplexing

```text
[ HTTP/1.1: Head-of-Line Blocking (Koneksi Berurutan) ]
TCP Conn 1: [ Request 1: HTML ] ────▶ [ Respon 1: HTML ] ────▶ [ Request 2: CSS ] ──▶ ...
(Jika Request 1 macet di server, Request 2 tertahan total!)

-----------------------------------------------------------------------------------------

[ HTTP/2: Binary Framing & Multiplexing (1 Koneksi Paralel) ]
TCP Conn 1: [ Req 1 Frame ] [ Req 2 Frame ] [ Req 3 Frame ] (Tercampur dalam 1 pipa)
            ══════════════════════════════════════════════════▶
            [ Res 2 Frame ] [ Res 1 Frame ] [ Res 3 Frame ] (Diterima paralel tanpa antre)
```

---

## 9. Simple Example: Skema gRPC Service Definition
```protobuf
// user_service.proto
syntax = "proto3";

package auth;

service UserService {
  // Unary RPC (Request tunggal -> Response tunggal)
  rpc GetUserProfile (UserRequest) returns (UserResponse);

  // Server Streaming RPC (Download stream data besar)
  rpc StreamAuditLogs (LogRequest) returns (stream LogEntry);
}

message UserRequest {
  int32 user_id = 1;
}

message UserResponse {
  int32 user_id = 1;
  string name = 2;
  string email = 3;
  repeated string roles = 4;
}
```

---

## 10. Practical Code Example
Lihat perbandingan ukuran byte data dan kecepatan serialisasi/deserialisasi antara JSON vs simulasi Protocol Buffers biner pada:
`System-Design/BAB-06-Protokol-Komunikasi/hands-on/m01/protocol_benchmark.js`

---

## 11. Real World Example: Migrasi Netflix & Dropbox ke gRPC
- **Netflix Microservices Mesh:** Netflix memproses ratusan miliar panggilan RPC internal setiap hari. Mereka memigrasikan seluruh arsitektur service-to-service dari REST JSON ke **gRPC**. Hasilnya: Pemanfaatan CPU server terpangkas lebih dari 25% dan latensi p99 antar-microservice turun dari 18 ms menjadi **1.8 ms**.
- **Dropbox Sync Engine:** Mesin sinkronisasi file raksasa Dropbox awalnya mengandalkan HTTP REST API. Ketika jumlah sinkronisasi file mencapai miliaran per hari, overhead parsing JSON menjadi bottleneck utama. Dropbox beralih ke gRPC biner yang menghemat petabyte bandwidth jaringan setiap bulannya.

---

## 12. Trade-offs (Pemilihan Protokol Komunikasi)

| Parameter | REST (JSON) | GraphQL | gRPC (Protobuf) |
|---|---|---|---|
| **Kemudahan Debugging** | Sangat Mudah (Bisa dibaca manusia / Postman / cURL) | Mudah (GraphiQL GUI Explorer) | Sulit (Payload biner, butuh tool khusus / BloomRPC) |
| **Caching di Level Jaringan** | Sangat Mudah (HTTP 200, 304, CDN Edge Caching) | **Sangat Sulit** (Semua request berstatus POST) | Tidak ada HTTP Caching (Harus diatur di memori) |
| **Kerapuhan Perubahan Skema** | Rentan breaking change | Sangat Aman (Bisa deprecate field tertentu) | **Sangat Aman** (Backward & Forward Compatibility) |
| **Tingkat Keahlian Tim** | Semua engineer paham | Butuh pemahaman GraphQL Schema & Resolvers | Butuh pemahaman Protobuf compiler (`protoc`) |

---

## 13. When To Use What
- **Gunakan REST jika:** Anda membangun **Public API** untuk pihak ketiga/kemitraan eksternal yang menuntut kesederhanaan integrasi dan caching CDN edge alami.
- **Gunakan GraphQL jika:** Anda membangun antarmuka frontend mobile/web yang kompleks (seperti dashboard aplikasi sosial media) di mana halaman yang sama membutuhkan data dari 10 domain berbeda secara presisi.
- **Gunakan gRPC jika:** Anda membangun **komunikasi internal antar-microservices di backend (East-West)**, sistem pemrosesan real-time berlatensi ultra-rendah, atau streaming data biner berkecepatan tinggi.

---

## 14. When NOT To Use
- **Jangan gunakan GraphQL sebagai protokol internal antar-microservices:** Parsing Abstract Syntax Tree (AST) GraphQL di setiap hop microservice akan menghancurkan performa latensi backend Anda.
- **Jangan gunakan gRPC langsung ke browser client publik tanpa pertimbangan matang:** Browser belum memiliki akses penuh ke HTTP/2 framing API bawaan, sehingga membutuhkan gRPC-Web proxy perantara.

---

## 15. Common Mistakes
1. **The GraphQL N+1 Database Query Trap:** Menulis resolver GraphQL naif tanpa menggunakan library batching seperti **DataLoader**. Jika query meminta 100 postingan beserta data author-nya, GraphQL mengeksekusi 1 query untuk posts + **100 query SQL terpisah ke database** untuk mengambil masing-masing author!
2. **Mengubah Nomor Field Tag pada File Protobuf:** Mengubah `int32 user_id = 1;` menjadi nomor tag lain (`= 4`). Ini akan merusak kompatibilitas biner (*breaking backward compatibility*) di seluruh microservices yang belum di-deploy!
3. **Mengabaikan Payload Size Limit pada gRPC:** Default batas pesan gRPC adalah 4 MB. Jika service mengirim payload melebihi 4 MB, koneksi langsung putus dengan error `RESOURCE_EXHAUSTED`.

---

## 16. Best Practices

- **Must Have:**
  - Gunakan **DataLoader** pada GraphQL untuk mencegah bencana N+1 database queries.
  - Jangan pernah mengubah nomor tag integer pada skema `.proto` yang sudah dirilis ke produksi.
- **Recommended:**
  - Gunakan arsitektur **Hybrid**: Gunakan REST atau GraphQL di perimeter publik (North-South), dan gunakan **gRPC murni di dalam jaringan internal cluster (East-West)**.
- **Advanced:**
  - Terapkan **HTTP/2 Connection Keep-Alive PING** pada gRPC untuk mendeteksi dead socket di balik Load Balancer cloud.
- **Avoid / Overengineering:**
  - Mengonversi aplikasi Monolith sederhana menjadi gRPC jika seluruh panggilan method hanya terjadi di dalam satu memori proses bahasa yang sama.

---

## 17. Troubleshooting Guide
```text
Gejala: Query GraphQL sering membuat database timeout (CPU 100%).
-----------------------------------------------------------------
Penyebab:
1. Malicious Client mengirimkan query rekursif bersarang tanpa batas (Deep Nested Query):
   query { user { friends { friends { friends { friends { ... } } } } } }

Solusi:
- Pasang "Query Depth Limiting" (batasi kedalaman query maksimal 4 tingkat).
- Pasang "Query Complexity Analysis": Hitung bobot biaya query sebelum dieksekusi di database; tolak request jika poin kompleksitas > 1000.
```

---

## 18. Hands-on Lab: Benchmark Ukuran & Kecepatan JSON vs Protocol Buffers

File lab sudah disiapkan di:
`System-Design/BAB-06-Protokol-Komunikasi/hands-on/m01/protocol_benchmark.js`

### Jalankan Uji Coba:
Buka terminal dan jalankan:
```bash
node System-Design/BAB-06-Protokol-Komunikasi/hands-on/m01/protocol_benchmark.js
```

### Yang Ditampilkan Script Ini:
1. Menyimulasikan serialisasi 1.000 data transaksi finansial menggunakan format **JSON standar**.
2. Menyimulasikan serialisasi data yang sama menggunakan skema **Binary Protocol Buffers (Varint Encoding)**.
3. Menghitung persentase reduksi ukuran bandwidth (Bytes) dan rasio kecepatan parsing CPU.

---

## 19. Exercises (Latihan)

### Level 1 (Easy):
Sebutkan 3 kelemahan utama dari format pertukaran data JSON berbasis teks saat digunakan untuk komunikasi ratusan microservices!

### Level 2 (Medium):
Jelaskan fenomena **N+1 Problem** pada GraphQL dan tunjukkan bagaimana mekanisme *Batching & Caching* pada **DataLoader** mampu memadatkan 100 query individual menjadi 1 query SQL tunggal menggunakan klausa `WHERE id IN (...)`!

### Level 3 (Hard):
Sebuah startup ingin mengimplementasikan gRPC untuk aplikasi mobile banking mereka. Mengapa koneksi gRPC dari aplikasi mobile Android/iOS di jaringan seluler 4G/5G membutuhkan penanganan *Connection Re-establishment & Exponential Backoff* yang jauh lebih hati-hati dibandingkan koneksi gRPC antar-server di dalam satu data center?

---

## 20. Summary & Knowledge Check
- [ ] Memahami komparasi mendalam antara REST, GraphQL, dan gRPC.
- [ ] Menguasai konsep Over-fetching dan Under-fetching.
- [ ] Memahami efisiensi biner Protocol Buffers dan Varint Encoding.
- [ ] Memahami fitur transport HTTP/2 Multiplexing.
- [ ] Mampu merancang arsitektur hybrid (REST/GraphQL di publik, gRPC di internal).
