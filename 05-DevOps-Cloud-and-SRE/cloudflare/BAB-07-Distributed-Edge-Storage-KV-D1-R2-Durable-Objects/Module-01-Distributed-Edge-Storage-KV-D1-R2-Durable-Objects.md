# Modul 01: Distributed Edge Storage & State Management

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Menguasai spektrum persistensi data Cloudflare Edge: Workers KV, Cloudflare D1, Cloudflare R2, Durable Objects, dan Vectorize.
- Menganalisis trade-off model konsistensi (Eventual Consistency vs Strong Consistency/Linearizability) pada sistem terdistribusi edge.
- Mengimplementasikan pola arsitektur Actor Model menggunakan Cloudflare Durable Objects untuk kasus *stateful coordination* tanpa race condition.
- Mendesain pipeline integrasi multi-storage (Hybrid Edge Persistence Architecture) yang menggabungkan blob storage, metadata relasional, in-memory state coordination, dan semantic search secara cost-efficient.
- Mengoperasikan, mendebug, dan mengoptimalkan performa I/O data edge serta latensi propagasi replikasi global pada skala enterprise.

---

## 2. Prerequisite
Sebelum mempelajari modul ini, peserta wajib memahami:
- Arsitektur eksekusi serverless Cloudflare Workers berbasis V8 Isolate (Modul Fundamental Workers).
- Dasar-dasar Sistem Terdistribusi: CAP Theorem, PACELC Theorem, Write Amplification, dan Replikasi Master-Replica vs Quorum.
- Sintaksis modern TypeScript/JavaScript (ESModules, Async/Await, Web Streams API).
- Penggunaan dasar `wrangler` CLI (versi 3.x ke atas).
- Dasar-dasar model data Relasional (SQL/SQLite) dan Object Storage (S3 API).

---

## 3. Concept
Komputasi edge secara historis bersifat *stateless* karena sifat data centers yang terfragmentasi di ratusan Point of Presence (PoP) di seluruh dunia. Menyimpan status (*state*) di edge memunculkan tantangan fundamental: latensi jaringan (speed of light constraints), konflik konkurensi antar-region, dan kompleksitas sinkronisasi data.

Cloudflare Distributed Storage Engine memecah spektrum penyimpanan menjadi lima primitif dengan karakteristik performa dan konsistensi yang presisi:
1. **Workers KV**: Sistem penyimpanan Key-Value terdistribusi berskala global yang dioptimalkan untuk rasio pembacaan sangat tinggi (*read-heavy*, >99% read) dengan model konsistensi *eventual consistency*.
2. **Cloudflare D1**: Database relasional berbasis SQLite terdistribusi dengan model arsitektur *Single-Primary Write, Read-Replication Globally Distributed*.
3. **Cloudflare R2**: Object Storage nir-egress (*zero egress fees*) yang kompatibel dengan protokol S3 API, dirancang untuk penyimpanan aset biner skala besar (unstructured data).
4. **Durable Objects (DO)**: Primitif komputasi terkoordinasi berbasis *Actor Model* yang menjamin konsistensi mutlak (*strong consistency* / *linearizability*) dengan persistensi lokal berlatensi rendah dan kapabilitas in-memory state processing.
5. **Vectorize**: Database vektor terdistribusi terdedikasi untuk pengindeksan dan pencarian *approximate nearest neighbor* (ANN) guna integrasi AI/LLM langsung di edge.

---

## 4. Why
Dalam arsitektur *centralized cloud* konvensional (misal: AWS us-east-1), worker edge di Jakarta, Tokyo, atau Frankfurt harus menempuh round-trip latency ratusan milidetik hanya untuk membaca konfigurasi kecil, memvalidasi session token, atau mengambil blob image.

Memindahkan layer data ke edge menyelesaikan masalah latensi round-trip (RTT), namun memicu masalah baru:
- Jika semua penyimpanan di edge dibuat *strongly consistent*, operasi penulisan menjadi sangat lambat karena memerlukan *distributed consensus* (seperti Raft/Paxos lintas benua).
- Jika semua penyimpanan dibuat *eventually consistent*, data finansial atau inventaris tiket akan mengalami masalah *double-spending* atau *overselling*.
- Biaya transfer data egress cloud publik konvensional (AWS S3 egress $0.09/GB) mencekik margin margin operasional aplikasi global.

Dengan mengombinasikan kelima primitif data Cloudflare:
- Cache dan konfigurasi statis dialirkan via **KV** (<15ms read time).
- Relasi metadata transaksional disimpan di **D1**.
- File media, dataset, dan backup disimpan di **R2** tanpa biaya egress.
- Logika stateful konkuren (misal: collaborative doc, live auction, rate limiter, cart) dikunci dengan mutlak menggunakan **Durable Objects**.
- Pencarian semantik dan knowledge retrieval dieksekusi secara instan via **Vectorize**.

---

## 5. What (Deep-Dive Teknis Lengkap)

### 5.1 Workers KV: Internals & Consistency Mechanics
Workers KV menyimpan data dalam sistem tiered storage berjenjang:
- **Central Storage Layer**: Cluster penyimpanan terdistribusi persisten utama.
- **Edge Cache Layer**: Data yang dibaca di sebuah PoP di-cache secara agresif di memory dan SSD PoP lokal tersebut.

**Mekanisme Propagasi & Konsistensi**:
- Model konsistensi KV adalah **Eventual Consistency**.
- Operasi `put()` menulis data langsung ke Central Storage. Invalidasi cache disebarkan (*purged*) ke edge colos secara asinkron.
- Edge PoP yang baru saja menerima request write dijamin mendapatkan data baru jika membaca via koneksi yang sama, namun PoP lain di belahan bumi lain mungkin memerlukan waktu propagasi hingga **60 detik** sebelum cache lokal mereka kedaluwarsa atau ter-invalidasi.
- Karakteristik batas: Key size maksimal 512 bytes, Value size maksimal 25 MB. Tidak dirancang untuk operasi yang memerlukan locking atomik atau write-heavy counters.

### 5.2 Cloudflare D1: SQLite Replicas at Edge
D1 dibangun di atas fondasi SQLite open-source engine:
- **Write Path**: D1 menggunakan arsitektur *single-primary*. Seluruh operasi modifikasi data (`INSERT`, `UPDATE`, `DELETE`) diarahkan (*forwarded*) secara otomatis ke PoP data center yang ditunjuk sebagai Primary Location. Primary memproses transaksi ke Write-Ahead Log (WAL).
- **Read Path**: Transaksi dari primary dialirkan secara asinkron (*log streaming*) ke Read Replicas yang berlokasi dekat dengan PoP pengguna. Operasi `SELECT` dieksekusi lokal di replica dengan latensi super rendah (<10-25ms).
- **Time-Travel & Point-in-Time Recovery**: D1 secara periodik mengambil snapshot WAL ke Cloudflare R2, memungkinkan restore basis data ke microsecond tertentu dalam kurun waktu 30 hari terakhir.

### 5.3 Cloudflare R2: Zero-Egress S3-Compatible Object Store
R2 menghilangkan batas biaya transfer egress antar-cloud:
- Memiliki native runtime integration dengan Workers melalui direct bindings (`env.MY_BUCKET.put()`, `env.MY_BUCKET.get()`), memotong overhead parsing HTTP/TCP/TLS.
- Kompatibilitas luas: Mendukung S3 API Signature Version 4 (SigV4), memungkinkan penggunaan AWS CLI, Terraform, boto3, atau Go AWS SDK.
- Data disimpan secara redundancy-encoded lintas multiple availability zone pada region yang ditentukan secara otomatis (*Jurisdictional Restrictions* tersedia untuk regulasi GDPR/EU).

### 5.4 Durable Objects (DO): The Edge Actor Model & Linearizability
Durable Objects memadukan kapabilitas *compute* dan *storage* dalam satu kesatuan runtime.
- **Single Instance Guarantee**: Untuk satu `id` Durable Object tertentu (dihasilkan via string nama atau random), Cloudflare menjamin bahwa **hanya ada tepat satu instance virtual isolate** yang aktif di seluruh jaringan global Cloudflare pada satu waktu.
- **Actor Model Execution**: Semua incoming request untuk ID tersebut di-routing ke instance tunggal tersebut. Eksekusi kode bersifat *single-threaded non-blocking event-loop*. Ini berarti mutasi state bebas dari kondisi *race condition* multithread konvensional tanpa memerlukan database row locks yang kompleks.
- **Linearizable Storage API**: DO memiliki storage engine tertanam (SQLite-backed persistent engine per object) yang menjamin konsistensi serializable/linearizable.
- **WebSockets Hibernation API**: DO dapat memelihara jutaan koneksi WebSocket terbuka secara simultan. Jika tidak ada payload data yang masuk, state isolate disimpan ke memory/disk (hibernasi) tanpa memakan kuota CPU, lalu dibangunkan secara instan (0ms overhead) saat pesan tiba.

### 5.5 Vectorize: Edge Vector Search Engine
Vectorize menyediakan storage dan indexing untuk vektor numerik hasil embedding model LLM:
- **Index Algorithms**: Mendukung algoritma Approximate Nearest Neighbor (ANN) seperti HNSW (Hierarchical Navigable Small World).
- **Distance Metrics**: Mendukung Euclidean (L2), Cosine Distance, dan Dot Product.
- **Edge Native**: Didesain terikat (*tightly coupled*) dengan Workers AI. Vektor dapat langsung dicari di edge tanpa menembus API Pinecone atau Milvus eksternal.

---

## 6. How
Implementasi dilakukan via konfigurasi declarative infrastruktur menggunakan `wrangler.toml` dan interface binding Worker TypeScript.

### Arsitektur Konfigurasi (`wrangler.toml`):
```toml
name = "distributed-edge-storage-pipeline"
main = "src/index.ts"
compatibility_date = "2024-04-01"

# 1. KV Binding
[[kv_namespaces]]
binding = "CONFIG_KV"
id = "a1b2c3d4e5f6_config_id"

# 2. D1 Database Binding
[[d1_databases]]
binding = "METADATA_DB"
database_name = "prod-metadata-d1"
database_id = "f7e8d9c0-b1a2-3c4d-5e6f-7a8b9c0d1e2f"

# 3. R2 Bucket Binding
[[r2_buckets]]
binding = "ASSETS_BUCKET"
bucket_name = "enterprise-media-r2"

# 4. Durable Objects Binding
[[durable_objects.bindings]]
name = "COORDINATOR_DO"
class_name = "GlobalStateCoordinator"

# Durable Object Migrations
[[migrations]]
tag = "v1"
new_classes = ["GlobalStateCoordinator"]

# 5. Vectorize Binding
[[vectorize]]
binding = "SEMANTIC_INDEX"
index_name = "product-embeddings-idx"
```

---

## 7. Analogy
Bayangkan operasional sebuah **Jaringan Restoran Cepat Saji Global**:
- **Workers KV** = *Papan Menu Dinding di Setiap Cabang*. Ditulis sekali oleh kantor pusat, dibaca ribuan pengunjung cabang secara cepat. Jika ada perubahan harga menu, butuh waktu bagi staf cabang untuk mengganti stiker papan menu (eventual consistency).
- **Cloudflare D1** = *Buku Kasir dan Inventaris Harian Cabang*. Cabang bisa melihat stok lokal dengan cepat (read replica), tetapi jika ada pesanan barang besar masuk atau update pembukuan resmi, kasir harus menelepon dan mencatatnya ke Server Kasir Pusat (single-primary).
- **Cloudflare R2** = *Gudang Kontainer Pendingin Raksasa*. Digunakan menyimpan pasokan bahan mentah, foto dokumentasi, dan rekaman CCTV (object binary storage). Gratis mengambil barang sebanyak mungkin tanpa ada pajak bea-cukai keluar gerbang (zero egress fees).
- **Durable Objects** = *Seorang Manajer Antrean VIP Khusus*. Hanya ada SATU manajer untuk meja VIP tertentu. Semua pesanan meja tersebut harus lewat manajer ini. Manajer mengingat pesanan di kepalanya (in-memory) dan mencatatnya di buku catatan pribadinya (persistent linearizable storage). Tidak mungkin terjadi salah paham pesanan karena manajer melayani pesanan satu demi satu.
- **Vectorize** = *Resepsionis Jenius Pencocok Selera*. Saat tamu berkata "Saya ingin makanan yang hangat, berkuah, tapi tidak terlalu pedas", resepsionis membandingkan koordinat rasa dan langsung menunjuk nomor menu yang paling mendekati secara instan.

---

## 8. Diagram (ASCII)

```
[ Incoming Global Client Requests ]
                |
                v
========================================================================
             CLOUDFLARE EDGE NETWORK (300+ Cities Global PoP)
========================================================================
                |
    +-----------+-----------------------------------+
    |                                               |
    v                                               v
[ Edge Worker Instance 1 ]             [ Edge Worker Instance 2 ]
(Tokyo PoP - Edge Isolate)             (Frankfurt PoP - Edge Isolate)
    |          |          |                         |
    |          |          +--------------+          |
    | (Read)   | (Query Local Replica)   |          | (Direct Access)
    v          v                         v          v
+--------+ +-------------+         +-------------------------------+
| KV     | | D1 Replica  |         | Durable Object Routing Engine |
| Edge   | | (Read-Only) |         +-------------------------------+
| Cache  | +------+------+                         |
+--------+        ^                                | (Strict Global Routing)
                  | (Log Stream)                   v
                  |               +---------------------------------+
                  |               | Durable Object (Single Isolate) |
                  |               | Location: Ashburn, USA          |
                  |               |  - Actor Model Non-blocking I/O |
                  |               |  - In-Memory Fast State Engine  |
                  |               |  - Linearizable SQLite Storage  |
                  |               +---------------------------------+
                  |
    +-------------+-----------------------+
    | (Direct Writes Routed to Primary)   | (Blob I/O)
    v                                     v
+------------------------+      +-----------------------------------+
| D1 Primary Database    |      | R2 Object Storage                 |
| (Single Primary PoP)   |      | (Zero Egress Distributed Storage) |
| Transactional Log (WAL)|      +-----------------------------------+
+------------------------+
            ^
            | (Snapshots & PITR)
            +-----------------------------+
```

---

## 9. Simple Example
Menyimpan dan membaca metadata cepat menggunakan kombinasi Workers KV dan R2.

```typescript
export interface Env {
  CONFIG_KV: KVNamespace;
  ASSETS_BUCKET: R2Bucket;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    const filename = url.pathname.slice(1);

    if (request.method === "GET") {
      // 1. Baca metadata status dari KV (Fast Read)
      const isBlacklisted = await env.CONFIG_KV.get(`blacklist:${filename}`);
      if (isBlacklisted === "true") {
        return new Response("File Blocked by Policy", { status: 403 });
      }

      // 2. Ambil blob binary stream dari R2
      const object = await env.ASSETS_BUCKET.get(filename);
      if (!object) {
        return new Response("Object Not Found", { status: 404 });
      }

      const headers = new Headers();
      object.writeHttpMetadata(headers);
      headers.set("etag", object.httpEtag);

      return new Response(object.body, { headers });
    }

    if (request.method === "PUT") {
      // Stream payload request langsung ke R2
      await env.ASSETS_BUCKET.put(filename, request.body, {
        httpMetadata: request.headers,
      });
      return new Response(`Uploaded ${filename} successfully.`, { status: 201 });
    }

    return new Response("Method not allowed", { status: 405 });
  },
};
```

---

## 10. Practical Example (Konfigurasi CLI / Terraform / Kode Hands-on)

Berikut adalah implementasi sistem **Real-Time Auction & Inventory Lock** yang menggabungkan:
1. **Durable Objects**: Memastikan tidak ada *double-bidding* atau *oversell* tiket.
2. **D1 Database**: Menyimpan histori transaksi dan audit log.
3. **Workers KV**: Menampilkan live leaderboard harga tertinggi untuk konsumsi publik.

### Durable Object: `AuctionRoom.ts`
```typescript
export class AuctionRoom implements DurableObject {
  private state: DurableObjectState;
  private currentBid: number = 0;
  private highestBidder: string = "None";

  constructor(state: DurableObjectState) {
    this.state = state;
    // Load state persisten ke dalam memory saat isolate pertama kali boot
    this.state.blockConcurrencyWhile(async () => {
      const storedBid = await this.state.storage.get<number>("currentBid");
      const storedBidder = await this.state.storage.get<string>("highestBidder");
      this.currentBid = storedBid ?? 0;
      this.highestBidder = storedBidder ?? "None";
    });
  }

  async fetch(request: Request): Promise<Response> {
    const url = new URL(request.url);

    if (url.pathname === "/bid" && request.method === "POST") {
      const payload = await request.json<{ bidder: string; amount: number }>();

      // Validasi mutlak atomik di Actor Isolate
      if (payload.amount <= this.currentBid) {
        return Response.json(
          { error: `Tawaran harus lebih tinggi dari saat ini: ${this.currentBid}` },
          { status: 400 }
        );
      }

      // Mutasi State
      this.currentBid = payload.amount;
      this.highestBidder = payload.bidder;

      // Persist ke linearizable embedded storage
      await this.state.storage.put("currentBid", this.currentBid);
      await this.state.storage.put("highestBidder", this.highestBidder);

      return Response.json({
        success: true,
        currentBid: this.currentBid,
        highestBidder: this.highestBidder,
      });
    }

    if (url.pathname === "/status" && request.method === "GET") {
      return Response.json({
        currentBid: this.currentBid,
        highestBidder: this.highestBidder,
      });
    }

    return new Response("Not Found", { status: 404 });
  }
}
```

### Worker Entry Point: `index.ts`
```typescript
import { AuctionRoom } from "./AuctionRoom";

export { AuctionRoom };

export interface Env {
  COORDINATOR_DO: DurableObjectNamespace;
  METADATA_DB: D1Database;
  CONFIG_KV: KVNamespace;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    const auctionId = url.searchParams.get("auctionId") || "default-item";

    // 1. Resolve Durable Object ID
    const doId = env.COORDINATOR_DO.idFromName(auctionId);
    const doStub = env.COORDINATOR_DO.get(doId);

    if (url.pathname === "/place-bid" && request.method === "POST") {
      const body = await request.clone().text();

      // Forward request langsung ke Durable Object (Actor)
      const doResponse = await doStub.fetch(
        new Request("http://internal/bid", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body,
        })
      );

      if (!doResponse.ok) {
        return doResponse;
      }

      const result = await doResponse.json<{ currentBid: number; highestBidder: string }>();

      // 2. Tulis ke D1 Database untuk Immutable Audit Log
      await env.METADATA_DB.prepare(
        "INSERT INTO bid_history (auction_id, bidder, amount, timestamp) VALUES (?, ?, ?, ?)"
      )
        .bind(auctionId, result.highestBidder, result.currentBid, Date.now())
        .run();

      // 3. Update KV secara asinkron untuk cache agregat publik
      await env.CONFIG_KV.put(
        `cache:highest:${auctionId}`,
        JSON.stringify(result),
        { expirationTtl: 300 }
      );

      return Response.json(result, { status: 200 });
    }

    // Endpoint fast-read via KV
    if (url.pathname === "/get-highest-fast" && request.method === "GET") {
      const cached = await env.CONFIG_KV.get(`cache:highest:${auctionId}`);
      if (cached) {
        return new Response(cached, {
          headers: { "Content-Type": "application/json", "X-Cache-Source": "KV-Edge" },
        });
      }

      // Fallback ke Durable Object jika cache kosong
      return doStub.fetch(new Request("http://internal/status"));
    }

    return new Response("Route Not Found", { status: 404 });
  },
};
```

---

## 11. Real World Example
**Studi Kasus: Global Ticket Booking Platform (Flash Sale Stadion Konser)**
- **Masalah**: 500.000 pengguna mengakses web tiket secara serentak dalam 3 menit. Kapasitas tiket hanya 50.000 kursi. Jika menggunakan database relational cloud terpusat tradisional (misal: single Postgres RDS), database akan mengalami lock contention parah, connection starvation, dan CPU spike 100%, memicu race condition tiket terjual ganda (*oversold*).
- **Solusi Edge**:
  1. **Workers KV**: Melayani static seating map layout dan metadata artis dengan latensi 5ms langsung dari Edge Cache global.
  2. **Durable Objects**: Setiap Section Stadion (misal: "Cat-1-Section-A", 500 kursi) dialokasikan satu Durable Object unik. Durable Object memegang state kursi yang tersisa di dalam memori isolate. Setiap permintaan alokasi diproses secara serial tanpa locking table database.
  3. **Cloudflare D1**: Ketika reservasi terkonfirmasi oleh Durable Object, event diteruskan secara streaming ke D1 untuk generate nomor invoice dan payment token.
  4. **Cloudflare R2**: Menyimpan PDF E-Ticket barcode hasil komputasi Worker setelah pembayaran selesai, memangkas beban biaya bandwidth egress ke 0 USD.

---

## 12. Trade-offs

| Storage Type | Keunggulan Utama | Limitasi / Kekurangan | Model Konsistensi | Latensi Baca |
| :--- | :--- | :--- | :--- | :--- |
| **Workers KV** | Read speed ultra cepat (<10ms), global distribution | Propagation delay tulis ke baca (hingga 60s), tidak cocok untuk counter | Eventual Consistency | Ultra-Low (Local Edge Cache) |
| **Cloudflare D1** | Relasional SQL murni, foreign keys, read replicas global | Operasi write terikat latensi ke Primary Location | Read: Eventual/Session, Write: Strong | Rendah di Replica, Sedang di Primary |
| **Cloudflare R2** | Zero egress fees, integrasi native streams, S3 API standard | Tidak ada indexing semantik, latensi Time-To-First-Byte lebih tinggi dari KV | Read-after-write (object-level) | Sedang (Object Storage Tier) |
| **Durable Objects**| Strict Linearizability, Actor pattern, no race condition, in-memory | Routing cross-region jika user jauh dari DO colo, memory cost per instance | Strong / Linearizable | Ultra-Low di Home Colo, RTT Jaringan jika Cross-Colo |
| **Vectorize** | Native Vector Search (Cosine, Dot), tight coupling Workers AI | Bukan general-purpose document database, butuh model embedding sinkron | Read-after-write index updates | Rendah hingga Sedang (HNSW compute) |

---

## 13. When To Use
- **Gunakan Workers KV jika**: Data memiliki perbandingan baca terhadap tulis minimal 90:1 (contoh: User Feature Flags, Global Redirect Rules, IP Whitelist, Static Configuration).
- **Gunakan Cloudflare D1 jika**: Aplikasi membutuhkan relational schema, joins, SQL queries, transactional integrity antar entitas metadata (contoh: Katalog E-Commerce, User Account profiles, Log metadata).
- **Gunakan Cloudflare R2 jika**: Anda menyajikan aset statis berukuran besar >25MB, video/audio chunks, dokumen PDF, backup database, atau pipeline log agregasi jangka panjang.
- **Gunakan Durable Objects jika**: Anda memerlukan sinkronisasi state atomik strictly consistent antar multiple user (contoh: Collaborative Document Editing/CRDTs, In-Memory Game Matchmaking, Global Distributed Rate Limiter dengan strict window, Auction Engine).
- **Gunakan Vectorize jika**: Anda membangun search bar cerdas berbasis kemiripan semantik, agen AI context injection (RAG), atau rekomendasi produk berbasis embedding.

---

## 14. When NOT To Use
- **JANGAN gunakan Workers KV untuk**:
  - Menyimpan balance saldo rekening atau inventaris tiket (risiko race condition *double-spend*).
  - High-frequency write loggers (KV akan melempar error rate limiting jika satu key di-update >1 kali per detik).
- **JANGAN gunakan Cloudflare D1 untuk**:
  - Transaksi high-throughput OLAP analytics skala Terabyte (Gunakan Snowflake / BigQuery).
  - Menyimpan binary file atau gambar (Gunakan R2, simpan path/URL di D1).
- **JANGAN gunakan Durable Objects untuk**:
  - Read-heavy data sederhana yang statis (Memaksa semua request global masuk ke satu Durable Object akan membuat bottleneck jaringan yang tidak perlu; gunakan KV/Cache API).
- **JANGAN gunakan R2 untuk**:
  - Metadata kecil (misal: JSON berukuran 50 bytes yang diakses 10.000 kali per detik; latensi R2 tidak optimal untuk mikro-transaksi, gunakan KV).

---

## 15. Common Mistakes
1. **Menggunakan KV sebagai Atomic Counter**:
   ```typescript
   // SALAH: Race Condition Fatal!
   let count = parseInt(await env.KV.get("visitors") || "0");
   count++;
   await env.KV.put("visitors", count.toString());
   ```
   *Dampak*: Jika 100 request datang bersamaan di PoP berbeda, 99 mutasi akan hilang (*lost update*). Solusi: Gunakan Durable Objects.
2. **Tidak Melakukan `blockConcurrencyWhile` di Durable Objects Constructor**:
   Inisialisasi state asinkron di constructor tanpa membungkusnya dalam `blockConcurrencyWhile` menyebabkan request baru dieksekusi sebelum state lama selesai dibaca dari disk storage.
3. **Mengabaikan Region Placement pada Durable Objects**:
   Membuat Durable Object tanpa opsi hint lokasi (`locationHint: "enam"`, `locationHint: "apac"`) saat inisialisasi ID dapat menempatkan Actor jauh dari mayoritas pengguna, memicu RTT latensi 250ms pada setiap panggilan.
4. **N+1 Queries pada D1 Database**:
   Mengeksekusi loop SQL queries `await env.DB.prepare(...).run()` dalam for-loop. D1 menyediakan method `env.DB.batch([...])` untuk mengeksekusi multiple statement dalam satu network trip round.

---

## 16. Best Practices
1. **D1 Batching Execution**: Selalu manfaatkan `db.batch()` untuk operasi bulk insert/update:
   ```typescript
   await env.METADATA_DB.batch([
     env.METADATA_DB.prepare("UPDATE inventory SET stock = stock - 1 WHERE id = ?").bind(productId),
     env.METADATA_DB.prepare("INSERT INTO orders (id, product_id) VALUES (?, ?)").bind(orderId, productId)
   ]);
   ```
2. **Layered Cache with Cache API & KV**: Letakkan Cloudflare Cache API (Tier 1) di depan KV (Tier 2) untuk menyerap jutaan RPS tanpa menyentuh sub-request quota KV.
3. **R2 Multipart Uploads untuk File Besar**: Untuk file >100MB, wajib gunakan S3 Multipart Upload API chunking agar upload tidak terkena batas worker memory limit (128MB).
4. **Durable Objects WebSocket Hibernation**: Aktifkan hibernation API untuk aplikasi chat/real-time:
   ```typescript
   this.state.acceptWebSocket(ws); // Otomatis masuk sleep mode jika pasif
   ```

---

## 17. Troubleshooting
- **Masalah: D1 Database Locked Error (`SQLITE_BUSY` / `Database is locked`)**:
  - *Akar Masalah*: Write transaction terlalu panjang atau ada transaksi paralel yang melebihi timeout lock SQLite primary.
  - *Resolusi*: Pastikan worker tidak menjalankan fetch API eksternal yang lambat di tengah-tengah transaksi D1. Perkecil durasi operasi penulisan, pisahkan logic baca ke query terpisah.
- **Masalah: Stale Data Terbaca dari KV**:
  - *Akar Masalah*: Membaca key yang baru saja di-write dari PoP yang berbeda sebelum propagasi invalidasi global selesai.
  - *Resolusi*: Tambahkan cache-busting logic atau gunakan query parameter bypass, atau alihkan critical path data yang membutuhkan read-your-own-writes guarantees ke Durable Objects/D1.
- **Masalah: Durable Object Overloaded (High CPU Execution Timeout)**:
  - *Akar Masalah*: Isolate DO tunggal menangani beban throughput komputasi berlebihan dari seluruh dunia (melebihi limit kapasitas single core V8).
  - *Resolusi*: Lakukan teknik *sharding*. Alih-alih membuat satu object global `env.DO.idFromName("global-counter")`, pecah menjadi shards: `env.DO.idFromName("counter-shard-" + Math.floor(Math.random() * 10))`.

---

## 18. Exercise
1. Tuliskan skrip Wrangler CLI untuk membuat:
   - Sebuah D1 database bernama `edge_ecommerce`.
   - Sebuah KV Namespace bernama `GLOBAL_CACHE`.
   - Sebuah R2 Bucket bernama `product-invoices`.
2. Implementasikan tabel D1 sederhana menggunakan query migration untuk melacak inventaris barang (`id`, `sku`, `stock_count`, `updated_at`).
3. Buat sebuah worker endpoint yang mengembalikan data inventaris dari cache KV jika ada, atau membaca dari D1 jika cache kosong (Read-Through Cache Pattern).

---

## 19. Challenge
Rancang arsitektur data **Edge Semantic Recommendation Engine**:
- Buat sebuah Cloudflare Worker yang menerima upload data katalog produk berupa JSON (ID, Nama, Deskripsi).
- Simpan blob JSON asli ke Cloudflare **R2**.
- Masukkan metadata referensial ke database **D1**.
- Eksekusi pembuatan embedding vektor secara langsung di edge menggunakan Cloudflare Workers AI (`@cf/baai/bge-base-en-v1.5`).
- Simpan representasi vektor ke database **Vectorize**.
- Buat endpoint pencarian semantik `/search?q=comfort+running+shoes` yang menghasilkan rekomendasi produk paling relevan beserta signed URL file dari R2 dalam durasi total eksekusi di bawah 150 milidetik.

---

## 20. Summary
- Komputasi edge modern menuntut strategi persistensi data berlapis yang presisi untuk menyeimbangkan trade-off performa, konsistensi data, dan biaya infrastruktur.
- **Workers KV** unggul dalam low-latency static edge reads dengan model *eventual consistency*.
- **Cloudflare D1** membawa kapabilitas SQL relational SQLite terdistribusi ke edge dengan pembagian tugas: *Primary Writes & Globally Distributed Read Replicas*.
- **Cloudflare R2** mengeliminasi barrier biaya egress bandwidth untuk aset biner dan unstructured object storage berskala besar.
- **Durable Objects** menyelesaikan persoalan paling rumit pada sistem terdistribusi edge: memfasilitasi *Actor Model* dengan jaminan *Strong Consistency/Linearizability* dan in-memory compute coordination.
- **Vectorize** melengkapi ekosistem data modern edge untuk beban kerja kecerdasan buatan (AI semantic indexing & RAG retrieval).

---