---
[⬅️ Module 01: Desain RESTful API & Idempotency](./Module-01-Desain-RESTful-API-Richardson-Maturity-Idempotency.md) | [📋 Silabus Induk](../README.md) | [BAB 03 Quiz & Challenge ➡️](./BAB-03-Quiz-dan-Challenge.md)
---

# Module 02: Modern RPC: gRPC, Protocol Buffers, & GraphQL N+1 Problem

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik mampu:
- Mengidentifikasi keterbatasan mendasar dari REST API berbasis JSON pada komunikasi microservice ber-throughput tinggi (*over-fetching*, *under-fetching*, dan *CPU parsing overhead*).
- Menguasai definisi skema dan serialisasi biner **Protocol Buffers (Protobuf v3)**: aturan penomoran tag biner (*field tags*), varints, serta aturan kompatibilitas maju dan mundur (*backward/forward compatibility*).
- Mengimplementasikan 4 mode komunikasi **gRPC** di atas HTTP/2: *Unary*, *Server Streaming*, *Client Streaming*, dan *Bidirectional Streaming*.
- Menjelaskan arsitektur **GraphQL**: Schema Definition Language (SDL), Type System, Resolvers, Query, Mutation, dan Subscription.
- Menganalisis akar penyebab **GraphQL N+1 Problem** dan mengeliminasinya secara elegan menggunakan pola **DataLoader (Batching & In-Memory Caching)**.
- Memilih protokol API yang paling tepat (*REST vs GraphQL vs gRPC*) menggunakan matriks keputusan arsitektur sistem.

---

## 2. Prerequisite
- Memahami konsep RESTful API dan semantik HTTP (Modul 01).
- Memahami protokol HTTP/2 Multiplexing (Bab 01).
- Pengetahuan dasar tentang sintaks asynchronous (Promises, Async/Await).

---

## 3. Concept
Ketika arsitektur backend berevolusi dari monolit menjadi puluhan microservices yang saling berkomunikasi ribuan kali per detik, protokol REST/JSON mulai menunjukkan kelemahannya:
1. **JSON adalah Format Teks (Text-based)**: Ukuran payload besar (nama field diulang di setiap baris JSON), dan proses serialisasi/deserialisasi teks menghabiskan 30-50% siklus CPU server.
2. **Schema Drift**: Tidak ada kontrak tipe data yang ketat antara produsen dan konsumen API secara bawaan, memicu bug runtime saat tipe data berubah.
3. **Over-fetching & Under-fetching**: Aplikasi mobile seringkali hanya membutuhkan nama pengguna, namun REST mengembalikan 50 field yang tidak dibutuhkan (*Over-fetching*), atau harus memanggil 4 endpoint terpisah untuk merender 1 halaman (*Under-fetching*).

Dua teknologi modern hadir untuk menyelesaikan spektrum masalah ini:
- **gRPC (Google Remote Procedure Call)**: Dirancang untuk komunikasi **Service-to-Service (Backend-to-Backend)** dengan performa biner maksimal menggunakan **Protocol Buffers** di atas **HTTP/2**.
- **GraphQL**: Dirancang untuk komunikasi **Client-to-Backend (Frontend/Mobile ke API Gateway)** di mana client menentukan secara presisi data apa saja yang ingin diambil dalam satu request tunggal.

```
+-----------------------------------------------------------------------------------+
|                        MODERN API ECOSYSTEM ARCHITECTURE                          |
|                                                                                   |
|  [ Mobile App / Frontend Browser ]                                                |
|       |                                                                           |
|       | 1. GraphQL Query: { user(id: 1) { name, avatarUrl } }                     |
|       |    (Flexible, Zero Over-fetching, Single Round-Trip)                      |
|       v                                                                           |
|  +-----------------------------------------------------------------------------+  |
|  | API GATEWAY / BACKEND FOR FRONTEND (BFF)                                     |  |
|  | (Resolves GraphQL & Dispatches gRPC Calls to Internal Microservices)       |  |
|  +-----------------------------------------------------------------------------+  |
|       |                                                    |                      |
|       | 2. gRPC Unary Call                                 | 3. gRPC Bi-di Stream |
|       |    Protobuf Binary over HTTP/2                     |    High Throughput   |
|       v                                                    v                      |
|  [ User Microservice ]                             [ Payment Microservice ]       |
|  (Microsecond serialization latency)               (Streaming financial ledger)   |
+-----------------------------------------------------------------------------------+
```

---

## 4. Why?
Mengapa menguasai gRPC dan GraphQL merupakan syarat wajib backend modern?
1. **Efisiensi Throughput Komunikasi Internal**: Serialisasi biner Protobuf 7x hingga 10x lebih cepat daripada parsing JSON, dan ukuran payload 50-70% lebih kecil. Pada cluster 500 microservices, ini menghemat ratusan server instance dan memangkas latensi p99 jaringan.
2. **Type Safety & Auto-Generated Code**: Skema `.proto` atau `.graphql` bertindak sebagai kontrak tunggal (*Single Source of Truth*). SDK client dalam bahasa Go, Java, TypeScript, Python, atau Rust di-generate otomatis via compiler, mengeliminasi kesalahan pengetikan manual (*typo-free contracts*).
3. **Eliminasi Latency Mobile**: GraphQL memangkas 5 pemanggilan REST API menjadi 1 query tunggal, sangat vital untuk jaringan seluler di negara berkembang.

---

## 5. What?

### A. Protocol Buffers (Protobuf v3) Internals
Protobuf tidak mengirimkan nama field (seperti `"first_name": "Alex"` di JSON). Protobuf hanya mengirimkan **Field Tag Number** dan nilai datanya dalam format biner terkompresi (*Varints*).

```protobuf
syntax = "proto3";

package banking.v1;

enum AccountStatus {
  ACCOUNT_STATUS_UNSPECIFIED = 0;
  ACCOUNT_STATUS_ACTIVE = 1;
  ACCOUNT_STATUS_FROZEN = 2;
}

message TransferRequest {
  int64 sender_account_id = 1;    // Tag 1 (1 byte wire representation)
  int64 receiver_account_id = 2;  // Tag 2
  double amount = 3;              // Tag 3
  string idempotency_key = 4;     // Tag 4
}

message TransferResponse {
  string transaction_id = 1;
  AccountStatus status = 2;
  int64 timestamp_ms = 3;
}

service PaymentService {
  // Unary RPC
  rpc ExecuteTransfer (TransferRequest) returns (TransferResponse);
  // Server Streaming RPC (Live audit stream)
  rpc StreamTransactions (TransferRequest) returns (stream TransferResponse);
}
```

> [!IMPORTANT]
> **ATURAN EMAS PROTOBUF**: Jangan pernah mengubah nomor tag biner (`= 1`, `= 2`) dari field yang sudah dirilis ke produksi! Mengubah nomor tag akan merusak kompatibilitas biner client lama. Jika suatu field sudah usang, tandai dengan `reserved`.

### B. GraphQL dan The Infamous N+1 Problem
GraphQL mengeksekusi *Resolver* secara independen pada setiap level hierarki.

Bayangkan query berikut:
```graphql
query {
  posts(limit: 10) {
    id
    title
    author {
      id
      name
    }
  }
}
```

**Bagaimana Resolver Default Bekerja Tanpa Optimasi?**
1. Eksekusi query pertama: `SELECT * FROM posts LIMIT 10;` (Mendapatkan 10 post) $\rightarrow$ **1 Query**.
2. Untuk **setiap** post, GraphQL memanggil resolver `author`:
   - Post 1: `SELECT * FROM users WHERE id = 101;`
   - Post 2: `SELECT * FROM users WHERE id = 102;`
   - ...
   - Post 10: `SELECT * FROM users WHERE id = 110;` $\rightarrow$ **N (10) Queries**.
3. Total Query ke Database = $1 + 10 = \mathbf{11 \text{ Query!}}$
Jika limit post adalah 1.000, database Anda akan dihantam $1.001$ query secara beruntun, memicu lonjakan CPU database dan latensi 10 detik!

### C. Solusi Penyelamat: Pattern DataLoader
Diciptakan oleh tim engineering Facebook:
**DataLoader** memanfaatkan mekanisme *Tick Event Loop*:
1. Saat resolver meminta author untuk Post 1, DataLoader **tidak langsung menjalankan SQL**. DataLoader menampung ID `101` ke dalam antrean batch lokal.
2. DataLoader menunggu hingga siklus tick eksekusi saat ini selesai (mengumpulkan seluruh ID: `[101, 102, 103, ...]`).
3. DataLoader mengeksekusi **tepat 1 Query SQL Batch tunggal**:
   `SELECT * FROM users WHERE id IN (101, 102, 103, ...);`
4. DataLoader mendistribusikan data hasil query kembali ke masing-masing promise resolver yang menunggunya.
5. Hasil: Dari 11 Query dipangkas menjadi **hanya 2 Query Database!**

---

## 6. How?

### Implementasi DataLoader di Node.js GraphQL

```javascript
const DataLoader = require('dataloader');

// 1. Batch Function: Menerima array keys dan mengembalikan array data berurutan
async function batchGetUsers(userIds) {
  console.log(`[DATABASE HIT] SELECT * FROM users WHERE id IN (${userIds.join(', ')})`);
  const users = await db.findUsersByIds(userIds);
  
  // Wajib mengembalikan urutan array yang persis sama dengan urutan userIds!
  const userMap = new Map(users.map(u => [u.id, u]));
  return userIds.map(id => userMap.get(id) || null);
}

// 2. Inisialisasi DataLoader per request context
const userLoader = new DataLoader(keys => batchGetUsers(keys));

// 3. Resolver GraphQL yang Bersih dan Bebas N+1
const resolvers = {
  Post: {
    author: (parentPost, args, context) => {
      // Menggunakan DataLoader: Otomatis dibatch dalam 1 SQL query!
      return context.userLoader.load(parentPost.authorId);
    }
  }
};
```

---

## 7. Analogy
Bayangkan **Pemesanan Kopi Kantor**:
- **REST**: Anda menelepon barista: *"Tolong kirimkan paket sarapan lengkap (Kopi, Roti, Telur, Donat)"*. Padahal Anda hanya ingin meminum kopinya (**Over-fetching**).
- **gRPC**: Anda dan barista menggunakan **Bahasa Sandi Biner Cepat**. Anda hanya menyebutkan: *"Kode 1, Nilai 2"*. Barista langsung mengerti tanpa basa-basi kalimat panjang, menyajikan kopi dalam 1 detik.
- **GraphQL**: Anda mengisi formulir kustom: *"Saya hanya ingin Kopi Hitam, ukuran Medium, tanpa gula"*. Barista meracik persis sesuai spesifikasi formulir Anda.
- **GraphQL N+1 Problem**: Ada 10 karyawan di lantai 3 yang ingin kopi. Seorang kurir magang turun ke lantai 1 mengambil 1 cangkir untuk Karyawan 1, naik kembali ke lantai 3. Lalu turun lagi mengambil 1 cangkir untuk Karyawan 2... Bolak-balik sebanyak 11 kali (**N+1 Disaster**).
- **DataLoader**: Kurir senior membawa nampan besar, bertanya ke seluruh 10 karyawan sekaligus, lalu turun ke lantai 1 dan membawa 10 cangkir kopi sekaligus dalam 1 perjalanan tunggal (**Batching**).

---

## 8. Diagram: gRPC Binary Framing vs GraphQL DataLoader

```
+---------------------------------------------------------------------------------+
|                       PROTOBUF VS DATALOADER ARCHITECTURE                       |
+---------------------------------------------------------------------------------+

1. JSON VS PROTOBUF SERIALIZATION:
   JSON (Text-based):
   {"sender_id":1001,"amount":250.5} ---> 33 Bytes in Wire (ASCII parsing CPU load)

   Protobuf (Binary Tag-Length-Value):
   [08][E9][07][19][00][00][00][00][00][A8][6F][40] ---> 12 Bytes in Wire! (No text parse!)

-----------------------------------------------------------------------------------

2. GRAPHQL N+1 MITIGATION VIA DATALOADER:
   WITHOUT DATALOADER:
   Post 1 ---> DB Query 1 (SELECT * FROM user WHERE id = 1)
   Post 2 ---> DB Query 2 (SELECT * FROM user WHERE id = 2)
   Post 3 ---> DB Query 3 (SELECT * FROM user WHERE id = 3)

   WITH DATALOADER (Single Tick Batching):
   Post 1 --+
   Post 2 --+---> DataLoader Queue [1, 2, 3] ---> 1 DB Query:
   Post 3 --+                                     SELECT * FROM users WHERE id IN (1, 2, 3)
```

---

## 9. Simple Example: Definisi Protobuf & gRPC Unary Call (Node.js)

```javascript
// client.js (Menggunakan @grpc/grpc-js)
const grpc = require('@grpc/grpc-js');
const protoLoader = require('@grpc/proto-loader');

const packageDef = protoLoader.loadSync('payment.proto');
const paymentProto = grpc.loadPackageDefinition(packageDef).banking.v1;

const client = new paymentProto.PaymentService(
  'localhost:50051',
  grpc.credentials.createInsecure()
);

client.ExecuteTransfer({
  sender_account_id: 1001,
  receiver_account_id: 2002,
  amount: 750000,
  idempotency_key: "tx-uuid-8899"
}, (err, response) => {
  if (err) return console.error("gRPC Error:", err.message);
  console.log("Transfer Berhasil! Transaction ID:", response.transaction_id);
});
```

---

## 10. Practical Example: Mengukur Benchmark Throughput JSON vs Protobuf

Perbandingan waktu komputasi pemrosesan 500.000 serialisasi objek antara JSON vs Binary Buffer:

```javascript
const payload = {
  order_id: 994821,
  customer_id: 48201,
  items: ["Item A", "Item B", "Item C"],
  total_price: 450000.75,
  is_paid: true
};

// 1. Benchmark JSON
console.time("JSON stringify & parse (100.000x)");
for (let i = 0; i < 100000; i++) {
  const str = JSON.stringify(payload);
  const obj = JSON.parse(str);
}
console.timeEnd("JSON stringify & parse (100.000x)");

// JSON menghasilkan string berukuran ~120 bytes dengan overhead parsing karakter teks ASCII.
// Protobuf memangkas waktu komputasi ini hingga 70% lebih cepat karena representasi biner murni!
```

---

## 11. Real World Example: Arsitektur Skala Besar Netflix & Uber
- **Uber**: Memiliki ribuan microservices internal yang mengorkestrasikan kalkulasi tarif, pencocokan pengemudi, dan peta routing. Uber menstandarisasi seluruh komunikasi antar microservice mereka menggunakan **gRPC**. Penghematan CPU dari serialisasi Protobuf dan koneksi persisten HTTP/2 menghemat jutaan dolar infrastruktur cloud per tahun.
- **Netflix**: Menggunakan arsitektur **Federated GraphQL (Apollo Federation)** pada layer API Gateway mereka. Ratusan tim frontend (UI Smart TV, Android, iOS, Web) dapat mengombinasikan data rekomendasi film, profil pengguna, dan tagihan dalam 1 query GraphQL tanpa membebani microservice inti.

---

## 12. Trade-offs

| Dimensi | REST (JSON) | gRPC (Protobuf) | GraphQL |
|---|---|---|---|
| **Format Data** | Teks (JSON) | **Biner Terkompresi (Protobuf)** | Teks (JSON) |
| **Protokol Transport** | HTTP/1.1 atau HTTP/2 | **Wajib HTTP/2** | HTTP/1.1 atau HTTP/2 |
| **Performa Serialisasi** | Sedang | **Ekstrim (Sub-milidetik)** | Sedang (Tergantung kompleksitas resolver) |
| **Streaming Duplex** | Terbatas | **Native (4 Mode Streaming)** | Mendukung via WebSocket Subscriptions |
| **Kemudahan Debugging** | Sangat Mudah (Bisa dibaca langsung via cURL) | Butuh tooling khusus (grpcurl, Postman gRPC) | Mudah (UI GraphiQL / Apollo Sandbox) |
| **Target Terbaik** | Public Open APIs, Webhooks | **Internal Microservices (East-West traffic)** | **Client-to-BFF (North-South traffic)** |

---

## 13. When To Use
- Gunakan **gRPC** untuk seluruh komunikasi antar microservice internal (*East-West traffic*) di dalam datacenter atau cluster Kubernetes Anda.
- Gunakan **GraphQL** sebagai layer API Gateway / Backend-For-Frontend (BFF) untuk melayani klien web dan mobile multi-platform (*North-South traffic*).
- Gunakan **REST** untuk API publik eksternal yang dikonsumsi oleh ribuan developer pihak ketiga atau integrasi Webhook standar.

---

## 14. When NOT To Use
- **JANGAN** menggunakan GraphQL untuk komunikasi internal service-to-service antar microservice backend; abstraksi GraphQL menambah overhead komputasi query parsing yang sia-sia di internal network.
- **JANGAN** menggunakan GraphQL tanpa mengimplementasikan batas kedalaman query (*Query Depth Limiting*) dan *Cost Analysis*, karena penyerang dapat mengirimkan *nested recursive query* yang melumpuhkan server Anda (*Denial of Service*):
  ```graphql
  # RECURSIVE ATTACK QUERY
  query { author { posts { author { posts { author { ... } } } } } }
  ```

---

## 15. Common Mistakes
1. **Mengabaikan N+1 Problem di GraphQL**: Menganggap GraphQL sudah otomatis cepat, lalu deploy ke produksi dan menemukan database down karena dibanjiri ribuan query individual.
2. **Mengubah Tag Number di Protobuf**: Mengubah `string name = 2;` menjadi `string name = 3;` saat menambahkan field baru. Ini menyebabkan client lama membaca data salah secara acak.
3. **Lupa Menyetel gRPC Deadlines / Timeouts**: Di gRPC, jika client tidak menyetel deadline, request dapat menggantung selamanya jika server hilir (*downstream*) lambat, menguras seluruh worker thread di upstream caller.

---

## 16. Best Practices
- **Must Have**: Wajib pasang **DataLoader** pada setiap relasi field di GraphQL schema untuk mencegah N+1 problem.
- **Recommended**: Terapkan **Query Complexity Limit** (misal via `graphql-query-complexity`) untuk memblokir query yang terlalu rakus sumber daya.
- **Advanced**: Gunakan **gRPC Metadata** untuk menyebarkan konteks distributed tracing (W3C TraceContext / OpenTelemetry traceparent) lintas batas microservices.
- **Avoid**: Mengekspos endpoint gRPC biner langsung ke browser publik tanpa layer transcoding (gRPC-Web atau Envoy gRPC-JSON transcoder).

---

## 17. Troubleshooting Guide
```
Masalah: gRPC client melempar error "UNAVAILABLE: io.grpc.StatusRuntimeException: Channel shutdown / Connection refused".
Penyebab : Service tujuan down, DNS belum ter-resolve, atau sertifikat TLS mutual mTLS tidak valid.
Diagnosa : grpcurl -plaintext localhost:50051 list
Solusi   : Pastikan endpoint target berjalan dan jika menggunakan K8s, gunakan headless service untuk client-side round-robin balancing.

Masalah: GraphQL query lambat parah (latensi 4 detik) pada query bersarang.
Penyebab : Terjadi fenomena N+1 database queries.
Diagnosa : Aktifkan SQL logging di database engine Anda:
           tail -f /var/log/postgresql/postgresql.log | grep SELECT
           Jika terlihat rentetan puluhan query serupa dalam 1 milidetik, N+1 problem sedang terjadi.
Solusi   : Bungkus resolver relasi tersebut menggunakan DataLoader batching.
```

---

## 18. Exercise
1. Tulis file skema `order.proto` yang mendefinisikan pesan `CreateOrderRequest` dan service `OrderService`.
2. Tulis skema GraphQL setara untuk entitas yang sama lengkap dengan Query dan Mutation.
3. Tulis fungsi batching DataLoader untuk entitas `OrderItems` yang dikelompokkan berdasarkan `orderId`.

---

## 19. Challenge
Rancang arsitektur API Gateway terpadu untuk platform Ride-Hailing (Gojek / Grab):
1. Klien mobile Android/iOS terhubung ke API Gateway menggunakan GraphQL.
2. API Gateway menerjemahkan query GraphQL dan memanggil 3 microservice backend terpisah (`DriverService`, `PricingService`, `MappingService`) secara simultan menggunakan gRPC parallel calls.
3. Implementasikan fallback graceful degradation jika `PricingService` mengalami timeout (gRPC deadline exceeded) setelah 200ms. Tuliskan arsitektur dan pseudocode handler-nya!

---

## 20. Summary
Tidak ada satu protokol API yang sempurna untuk semua kondisi. REST tetap menjadi standar emas integrasi publik yang ramah pengguna; GraphQL memberikan kendali data fleksibel bagi frontend dan mobile; sedangkan gRPC bersama Protocol Buffers menghadirkan kecepatan biner dan efisiensi throughput ekstrem untuk jaringan internal microservices. Memahami kapan dan bagaimana mengombinasikan ketiganya adalah ciri khas arsitek backend kelas dunia.

---
[⬅️ Module 01: Desain RESTful API & Idempotency](./Module-01-Desain-RESTful-API-Richardson-Maturity-Idempotency.md) | [📋 Silabus Induk](../README.md) | [BAB 03 Quiz & Challenge ➡️](./BAB-03-Quiz-dan-Challenge.md)
---
