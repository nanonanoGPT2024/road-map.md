# BAB 08: Quiz, Challenge, & Knowledge Check
**Integrasi Database, Connection Pooling, & Edge Storage**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Serverless Connection Exhaustion Mechanics**  
   Jelaskan secara mendalam mengapa arsitektur Serverless Function pada Next.js (seperti Vercel atau AWS Lambda) dapat menghabiskan kuota koneksi (*max_connections*) PostgreSQL/MySQL konvensional dalam hitungan detik saat terjadi lonjakan *traffic*, padahal aplikasi monolitik tradisional dengan beban kerja yang sama mampu bertahan menggunakan *in-memory connection pool* standar!

2. **Node.js Runtime vs. Edge Runtime DB Constraints**  
   Bandingkan batasan arsitektural antara Node.js Runtime dan Edge Runtime di Next.js dalam konteks I/O database. Mengapa *driver* database standar (seperti `pg` atau `mysql2`) secara *default* gagal dieksekusi di Edge Runtime, dan bagaimana protokol komunikasi berbasis HTTP/WebSocket atau driver khusus seperti `@neondatabase/serverless` mengatasi hambatan ini?

3. **Singleton Pattern & HMR Connection Leaks**  
   Perhatikan pola inisialisasi Prisma/Drizzle client berikut:
   ```typescript
   import { PrismaClient } from '@prisma/client';
   const prisma = new PrismaClient();
   export default prisma;
   ```
   Jelaskan mengapa kode di atas memicu *connection leak* masif di lingkungan *development* Next.js, dan bagaimana implementasi pattern `globalThis` mencegah instansiasi ganda akibat *Hot Module Replacement* (HMR).

4. **Transaction Pooling vs. Session Pooling**  
   Dalam implementasi proxy koneksi database eksternal (seperti PgBouncer, Supabase Supavisor, atau AWS RDS Proxy), jelaskan perbedaan fundamental antara mode *Session Pooling* dan *Transaction Pooling*. Mode manakah yang direkomendasikan untuk Serverless Next.js Route Handlers/Server Actions, dan apa konsekuensinya terhadap fitur SQL seperti `PREPARE`, temporary tables, atau session-level variables?

5. **Karakteristik Konsistensi Edge Storage**  
   Edge Storage (seperti Cloudflare KV, Vercel KV/Upstash, atau Edge-replicated database seperti Turso/libSQL) mengadopsi model konsistensi yang berbeda (misalnya *eventual consistency* vs. *strong consistency*). Jelaskan trade-off antara latensi baca (*read latency*) dan risiko *stale read* saat memilih Edge KV untuk menyimpan data sesi (*session state*) dibanding data inventaris produk.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Prepared Statement Collision pada PgBouncer**  
   Saat menggunakan ORM (seperti Prisma atau Drizzle) dengan PostgreSQL yang berada di balik PgBouncer (mode *transaction pooling*), aplikasi tiba-tiba melempar *error*: `prepared statement "s0" already exists` atau `prepared statement does not exist`. Bedah akar masalah internal dari error ini dan jelaskan solusi konfigurasinya (misalnya penyesuaian *connection string parameter* `pgbouncer=true` atau penonaktifan *prepared statement cache*).

2. **Read-After-Write Inconsistency pada Read Replicas**  
   Sebuah Server Action di Next.js menjalankan mutasi data pengguna (INSERT/UPDATE ke database Primary/Writer), lalu langsung memicu `revalidatePath()` yang memicu Server Component untuk membaca data dari Database Read Replica. Pengguna melaporkan bahwa UI sering kali tidak menampilkan perubahan yang baru saja disimpan. Analisis fenomena *replication lag* ini dan rancang strategi mitigasi arsitektur (seperti *write-to-read window leasing* atau perutean dinamis reader/writer) agar UI selalu konsisten tanpa membebani Primary DB secara berlebihan.

3. **Cold Start & ORM Engine Binary Footprint**  
   Bandingkan dampak *Cold Start* antara ORM yang mengandalkan Native Query Engine Binary (seperti Prisma versi klasik) versus ORM berbasis TypeScript murni/lightweight (seperti Drizzle ORM atau Kysely) pada Vercel Serverless Functions. Parameter apa saja dalam proses inisialisasi memori dan V8 isolate execution yang menyebabkan deviasi latensi signifikan pada *invocation* pertama?

4. **Connection Timeout Tuning pada Serverless Burst**  
   Ketika 1.000 request masuk secara simultan dalam 500ms ke Route Handler `/api/checkout`, puluhan instance Lambda/Vercel Function baru ter-spawning secara paralel. Sebagian instance melempar error: `Connection pool timeout: Timed out fetching a connection from the pool`. Bagaimana Anda menyetel parameter `connection_limit`, `pool_timeout`, dan `idle_timeout` pada ORM client jika Anda memiliki pooler perantara dengan kuota 100 koneksi ke database fisik?

5. **Edge Data Mutations & Distributed Locks**  
   Anda membangun sistem reservasi tiket menggunakan Next.js Edge Route Handler dan Vercel KV (Redis). Mengapa perintah primitif `GET` yang diikuti `SET` rentan terhadap *race condition* parah di lingkungan Edge yang terdistribusi secara global? Jelaskan bagaimana Anda mengimplementasikan mekanisme *distributed lock* (Redlock) atau perintah atomik (Redis Lua Scripting / `SET NX EX`) untuk menjamin integritas data multi-region.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Black Friday & Postgres Pool Exhaustion
Sistem e-commerce berbasis Next.js App Router mengalami lonjakan trafik 30x lipat saat flash sale dimulai. Dalam 2 menit pertama, database AWS RDS PostgreSQL crash dengan status `FATAL: remaining connection slots are reserved for non-replication superuser connections`. 

Serverless functions di Vercel mengalami *cascading failure* dengan status HTTP 504 Gateway Timeout. Tim infrastruktur mengonfirmasi bahwa instance DB fisik memiliki batas `max_connections = 500`, sementara Vercel men-spawning hingga 2.500 *concurrent execution environments*.
* **Pertanyaan Diagnostik & Solusi:**
  1. Identifikasi kesalahan fatal dalam arsitektur koneksi database langsung dari Serverless Function ke PostgreSQL!
  2. Rancang solusi arsitektur darurat (hotfix) dan arsitektur permanen menggunakan connection pooler / database proxy (seperti RDS Proxy / Supavisor / Prisma Accelerate). Bagaimana alur koneksi dimultiplexing dari 2.500 functions ke 500 koneksi fisik database?

### Skenario B: Race Condition Saldo Dompet Digital pada Server Actions
Aplikasi FinTech menggunakan Next.js Server Actions untuk transfer dana antar pengguna. Server Action berikut diimplementasikan:
```typescript
'use server';

export async function transferBalance(senderId: string, receiverId: string, amount: number) {
  const sender = await db.user.findUnique({ where: { id: senderId } });
  
  if (sender.balance >= amount) {
    await db.user.update({
      where: { id: senderId },
      data: { balance: sender.balance - amount }
    });
    
    await db.user.update({
      where: { id: receiverId },
      data: { balance: { increment: amount } }
    });
    
    return { success: true };
  }
  throw new Error("Insufficient balance");
}
```
Saat user melakukan double-click cepat atau mengirim 2 request bersamaan dari dua tab browser berbeda, saldo pengirim berkurang melebihi saldo aslinya (menjadi negatif), tetapi saldo penerima bertambah dua kali.
* **Pertanyaan Diagnostik & Solusi:**
  1. Identifikasi anomali konkurensi database yang terjadi (misalnya *Lost Update* / *Read Skew*) dan jelaskan mengapa pengecekan `if (sender.balance >= amount)` di level JavaScript tidak efektif!
  2. Tuliskan refaktor kode Server Action di atas menggunakan mekanisme database level lock yang benar (Pilih salah satu: *Pessimistic Locking* via `SELECT ... FOR UPDATE` atau *Optimistic Concurrency Control* via versioning/atomic update statement) dalam transaksi yang ACID-compliant!

### Skenario C: Trade-off Arsitektur Edge Database vs Centralized Multi-AZ
Perusahaan SaaS enterprise global ingin memigrasikan aplikasi Next.js dari satu region (us-east-1) ke arsitektur Global Multi-Region untuk melayani pengguna di Asia, Eropa, dan Amerika dengan latensi TTFB < 100ms. CTO mengusulkan memindahkan seluruh database ke Edge-native distributed database (seperti Turso libSQL dengan embedded replicas atau Neon serverless Postgres). Namun, Lead Architect berpendapat bahwa data core finansial harus tetap berada di Centralized PostgreSQL AWS RDS multi-AZ.
* **Pertanyaan Diagnostik & Solusi:**
  1. Analisis trade-off performa (*read latency* vs. *write penalty*) dan batasan hukum/regulasi (seperti GDPR / data residency) jika seluruh operasional DB dipindahkan ke Edge Distributed Database!
  2. Rancang arsitektur hibrida (*Hybrid Edge-to-Core*): tentukan domain data apa yang layak diletakkan di Edge Storage (misalnya Upstash KV / Turso replica) dan domain data apa yang wajib diarahkan langsung ke Centralized Core DB, serta bagaimana strategi sinkronisasinya!

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Throughput Ticket Reservation Engine dengan Resilient Edge-to-Core Pipeline

#### Problem Statement
Anda ditugaskan membangun modul backend untuk sistem penjualan tiket konser berkapasitas 10.000 kursi yang diperkirakan diserbu 150.000 user dalam kurun waktu 5 menit. Seluruh aplikasi dibangun menggunakan Next.js App Router (Node.js + Edge Runtimes). Serverless functions tidak boleh meledakkan database relasional utama (PostgreSQL), dan sistem harus menjamin **Zero Overselling** (tidak boleh ada 1 kursi pun yang terpesan oleh 2 orang berbeda).

#### Requirements
1. **Singleton & Pooled Connection Module**:
   * Buat modul database client (`@/lib/db.ts`) yang menerapkan pattern anti-leak untuk HMR di *development* dan mendukung integrasi proxy pooler (PgBouncer/Supavisor) dengan pengaturan timeout yang defensif.
2. **Edge-Based Stock Checking & Rate Limiting**:
   * Implementasikan Route Handler di Edge Runtime (`/api/tickets/check-availability`) yang membaca sisa kuota tiket dari Edge Storage (Vercel KV / Redis) dengan latensi ultra-rendah (<50ms global).
3. **Atomic Reservation Server Action**:
   * Implementasikan Server Action (`reserveTicket(ticketTierId, userId)`) yang:
     * Mengeksekusi reservasi menggunakan transaksi PostgreSQL murni dengan *Pessimistic Lock* (`FOR UPDATE`) atau Atomic Conditional Decrement (`WHERE available_seats > 0`).
     * Mencegah reservasi ganda menggunakan *Idempotency Key* berbasis Redis/KV.
     * Mengurangi kuota di cache Edge secara sinkron atau mendekati real-time.
4. **Resilience & Fallback Handling**:
   * Jika database mengalami saturasi pool atau timeout, Server Action harus melempar error tertangani (`HTTP 429 / 503 Custom Code`) yang dapat dipahami oleh client-side UI, tanpa men-crash runtime container.

#### Constraints
* Tidak boleh menggunakan memori lokal serverless function (`let localCache = ...`) untuk menyimpan state kuota tiket.
* Wajib memastikan tidak ada query ORM yang memicu N+1 saat memvalidasi user dan tier tiket.
* Kode harus ditulis dalam TypeScript murni dengan *strict type safety*.

#### Expected Output
* File `lib/db.ts`: Konfigurasi singleton database client yang aman dari HMR dan kompatibel dengan PgBouncer.
* File `app/api/tickets/check-availability/route.ts`: Edge Route Handler untuk fast-read availability.
* File `app/actions/reservation.ts`: Server Action yang menangani transaksi reservasi secara atomik, aman dari *race condition*, dan memiliki penanganan saturasi pool.
* Dokumentasi arsitektur singkat (3-5 paragraf) yang menjelaskan strategi mitigasi connection exhaustion dan mekanisme pencegahan overselling.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Anatomi siklus hidup Serverless Function (Cold start, Warm instance, Spin-down) dan dampaknya terhadap koneksi TCP database.
- [ ] Batasan networking pada Edge Runtime (ketiadaan TCP socket native V8, isolasi lingkungan, dan kebutuhan akan driver HTTP/WebSocket).
- [ ] Perbedaan esensial antara PgBouncer mode *Transaction*, *Session*, dan *Statement Pooling*.
- [ ] Mengapa isolasi transaksi SQL konvensional (`SERIALIZABLE`, `REPEATABLE READ`, `READ COMMITTED`) memerlukan penanganan khusus pada arsitektur serverless multi-replica.
- [ ] Kapan harus menggunakan In-Memory Cache, Edge KV Storage, Read Replica, dan Write-Master Database.
- [ ] Karakteristik *replication lag* dan bagaimana pola *Read-After-Write Consistency* dipertahankan dalam Server Actions.

### Saya tidak perlu menghafal:
- [ ] Seluruh parameter internal konfigurasi file `pgbouncer.ini` (misal: `so_reuseport`, `pkt_buf`). Cukup pahami parameter kritis seperti `pool_mode`, `max_client_conn`, dan `default_pool_size`.
- [ ] Binary wire protocol format dari PostgreSQL / MySQL.
- [ ] Sintaks spesifik driver C-binding internal Node.js.

### Saya harus bisa melakukan:
- [ ] Mengonfigurasi singleton client (Prisma/Drizzle) dengan `globalThis` untuk mengeliminasi memory & connection leaks saat HMR aktif.
- [ ] Mengintegrasikan connection string dengan parameter proxy pooler (`pgbouncer=true`, `connection_limit=1`, dsb.) secara presisi.
- [ ] Menulis query mutasi atomik yang terproteksi dari *race condition* konkurensi tinggi menggunakan SQL transactions (`SELECT ... FOR UPDATE` atau conditional `UPDATE`).
- [ ] Mendiagnosis dan memperbaiki *bottleneck* performa akibat N+1 query dan unbounded connection allocations menggunakan tracing/telemetry.
- [ ] Mengimplementasikan distributed rate-limiting dan distributed locking menggunakan Redis / Edge KV pada Next.js API Routes dan Server Actions.