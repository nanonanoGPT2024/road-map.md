# Kurikulum Lengkap Backend Beginner: Rekayasa Sistem Sisi Server (Server-Side Engineering)

Selamat datang di repositori silabus komprehensif **Backend Beginner**. Kurikulum ini dirancang berdasarkan standar industri global dan roadmap resmi [roadmap.sh: Backend Developer](https://roadmap.sh/backend). Fokus utama kurikulum ini bukan sekadar mengajarkan sintaks dasar bahasa pemrograman, melainkan membentuk fondasi berpikir rekayasa perangkat lunak backend (Backend Systems Engineering): bagaimana membangun layanan yang modular, terukur, aman, dan dapat diandalkan di lingkungan produksi enterprise.

---

## 1. Course Overview & Mindset

### Paradigma Rekayasa Backend
Backend engineering berakar pada pengelolaan status (*state*), manipulasi data, integrasi jaringan, dan penegakan invariant bisnis. Di era cloud-native saat ini, seorang insinyur backend bertanggung jawab untuk menjamin ketersediaan (*availability*), integritas data (*data integrity*), keamanan autentikasi, serta latensi rendah pada seluruh siklus interaksi aplikasi.

```
+---------------+     HTTP/HTTPS       +---------------------------------------------+
|    Client     |  =================>  |              Reverse Proxy                  |
| (Web/Mobile)  |  <=================  |               (e.g., Nginx)                 |
+---------------+     JSON Payload     +---------------------------------------------+
                                                              |
                                                              v
+------------------------------------------------------------------------------------+
|                               Application Runtime                                  |
|                                                                                    |
|  [ Middleware Pipeline: Logger -> Auth Guard -> Rate Limiter -> Body Validator ]   |
|                                     |                                              |
|                                     v                                              |
|                       [ Business Service Layer ]                                   |
|                               /           \                                        |
|                              v             v                                       |
|                  [ In-Memory Cache ]     [ Repository Layer ]                      |
|                     (Redis Cache)                  |                               |
+----------------------------------------------------+-------------------------------+
                                                     |
                                                     v
                                         +-----------------------+
                                         |      PostgreSQL       |
                                         | (Primary Relational)  |
                                         +-----------------------+
```

### Prinsip Fondasi Kurikulum
1. **Deterministic Execution**: Semua pemrosesan data, validasi, dan penanganan error harus eksplisit dan dapat diprediksi (*deterministic*).
2. **Data Integrity First**: Database adalah single source of truth; ACID compliance dan perancangan constraint tidak boleh dikompromikan demi kenyamanan kode.
3. **Defense in Depth**: Keamanan diterapkan di setiap lapisan; mulai dari validasi payload HTTP, otorisasi berbasis peran (RBAC), sanitasi database query, hingga isolasi container.
4. **Observable Systems**: Kode yang tidak memancarkan log terstruktur dan metrik yang jelas adalah kode yang tidak dapat dioperasikan di level produksi.

---

## 2. Learning Roadmap (Diagram Pohon 10 BAB)

```
ROADMAP BACKEND BEGINNER (SERVER-SIDE ENGINEERING)
|
+-- Bab 01: Fondasi Backend & Arsitektur Internet
|   |-- 01.1 Internet Lifecycle & Resolusi DNS
|   |-- 01.2 Model Klien-Server & Siklus Hidup Request-Response
|   \-- 01.3 Arsitektur Jaringan: IP, TCP/UDP, Port, & TLS
|
+-- Bab 02: Protokol HTTP/HTTPS & Web Communication
|   |-- 02.1 Anatomi HTTP Message: Verbs, Headers, & Status Codes
|   |-- 02.2 Negosiasi Konten, Payload Serialisasi, & Idempotensi
|   \-- 02.3 Transport Security: TLS Handshake & Komunikasi Aman
|
+-- Bab 03: Prinsip Desain RESTful API & Kontrak Data
|   |-- 03.1 Pemodelan Resource & Naming Convention REST
|   |-- 03.2 Standarisasi Payload Error & Metadata Pagination
|   \-- 03.3 Spesifikasi API-First: OpenAPI/Swagger Specification
|
+-- Bab 04: Runtime Backend & Concurrency Model
|   |-- 04.1 Eksekusi Proses: Single-Threaded Event Loop vs Multi-Threading
|   |-- 04.2 Operasi I/O Non-Blocking & Asynchronous Programming
|   \-- 04.3 Manajemen Konfigurasi Runtime, Signals, & Graceful Shutdown
|
+-- Bab 05: Relational Database Management Systems (PostgreSQL)
|   |-- 05.1 Desain Relasi Data: Normalisasi, DDL, & Invariant Constraints
|   |-- 05.2 Eksekusi Query DML, Operasi Join, & Indeksasi (B-Tree)
|   \-- 05.3 Prinsip Transaksi ACID & Tingkat Isolasi (Isolation Levels)
|
+-- Bab 06: Data Access Patterns & Manajemen Koneksi
|   |-- 06.1 Connection Pooling, Latensi Jaringan, & Driver Database
|   |-- 06.2 Raw SQL vs Query Builders vs ORM: Analisis Trade-off
|   \-- 06.3 Mitigasi SQL Injection melalui Prepared Statements
|
+-- Bab 07: Autentikasi, Otorisasi, & Keamanan Identitas
|   |-- 07.1 Hashing Kriptografis: Bcrypt/Argon2 & Penyimpanan Kredensial
|   |-- 07.2 Stateful Session Management vs Stateless Token (JWT)
|   \-- 07.3 Role-Based Access Control (RBAC) & Middleware Pipeline
|
+-- Bab 08: Validasi Input, Error Handling, & Observabilitas
|   |-- 08.1 Sanitasi Input & Validasi Schema Payload
|   |-- 08.2 Sentralisasi Exception Handling & Hierarki Error Domain
|   \-- 08.3 Structured Logging (JSON) & Contextual Trace IDs
|
+-- Bab 09: Caching Strategies & Background Job Basics
|   |-- 09.1 In-Memory Caching (Redis) & Pola Cache-Aside
|   |-- 09.2 Cache Invalidation, TTL, Race Conditions, & Thundering Herd
|   \-- 09.3 Paradigma Komputasi Asinkron: Message Broker & Workers
|
\-- Bab 10: Containerization, Testing, & Enterprise Deployment
    |-- 10.1 Testing Pyramid: Unit, Integration, & Mocking Dependencies
    |-- 10.2 Containerization menggunakan Docker & Multi-Stage Builds
    \-- 10.3 Automasi CI/CD & Deployment Strategy untuk Layanan Backend
```

---

## 3. Navigasi Detail Bab 01 s/d Bab 10

### [Bab 01: Fondasi Backend & Arsitektur Internet](./bab-01-fondasi-backend-arsitektur-internet/README.md)
*Fokus: Mengupas mekanisme fundamental bagaimana data berpindah secara global dari perangkat pengguna akhir hingga mencapai daemon aplikasi di sisi server.*

* **[Modul 01.1: Internet Lifecycle & Resolusi DNS](./bab-01-fondasi-backend-arsitektur-internet/01-resolusi-dns-dan-lifecycle.md)**
  * Target: Memahami bagaimana DNS resolver memetakan domain menjadi IP melalui Root, TLD, dan Authoritative Nameservers.
  * Ringkasan: Alur rekursif DNS query, rekaman DNS utama (A, AAAA, CNAME, TXT), dan konsep DNS caching pada OS dan ISP.
* **[Modul 01.2: Model Klien-Server & Siklus Hidup Request-Response](./bab-01-fondasi-backend-arsitektur-internet/02-model-klien-server-lifecycle.md)**
  * Target: Menguasai lifecycle lengkap transmisi data bolak-balik antara frontend/klien ke backend server.
  * Ringkasan: Anatomi socket connection, buffering I/O, parsing byte payload, dan serialisasi response stream.
* **[Modul 01.3: Arsitektur Jaringan: IP, TCP/UDP, Port, & TLS](./bab-01-fondasi-backend-arsitektur-internet/03-arsitektur-jaringan-ip-tcp-port.md)**
  * Target: Mengetahui perbedaan transport layer protocols dan peran abstraksi port dalam sistem operasi.
  * Ringkasan: Three-way handshake (SYN, SYN-ACK, ACK), reliabilitas TCP vs throughput UDP, abstraksi socket multiplexing.

---

### [Bab 02: Protokol HTTP/HTTPS & Web Communication](./bab-02-protokol-http-https/README.md)
*Fokus: Membedah protokol aplikasi paling dominan di web saat ini secara mendalam pada level byte dan header.*

* **[Modul 02.1: Anatomi HTTP Message: Verbs, Headers, & Status Codes](./bab-02-protokol-http-https/01-anatomi-http-message.md)**
  * Target: Menguasai struktur frame protokol HTTP (Request Line, Status Line, Headers, dan Body).
  * Ringkasan: Karakteristik semantik method HTTP (GET, POST, PUT, PATCH, DELETE), kategori status codes (2xx, 3xx, 4xx, 5xx), serta header esensial.
* **[Modul 02.2: Negosiasi Konten, Payload Serialisasi, & Idempotensi](./bab-02-protokol-http-https/02-konten-serialisasi-idempotensi.md)**
  * Target: Membangun API yang mematuhi standar transmisi representasi data dan memahami safe vs idempotent methods.
  * Ringkasan: MIME Types (`application/json`, `multipart/form-data`), Content-Type vs Accept header, serta analisis matematis sifat idempotensi.
* **[Modul 02.3: Transport Security: TLS Handshake & Komunikasi Aman](./bab-02-protokol-http-https/03-tls-handshake-komunikasi-aman.md)**
  * Target: Memahami bagaimana enkripsi asimetris dan simetris menjamin integritas komunikasi HTTP melalui HTTPS.
  * Ringkasan: Mekanisme TLS 1.3 handshake, Certificate Authority (CA), verifikasi public/private key, dan degradasi performa enkripsi.

---

### [Bab 03: Prinsip Desain RESTful API & Kontrak Data](./bab-03-desain-restful-api/README.md)
*Fokus: Perancangan antarmuka antarsistem berbasis standar arsitektural REST yang intuitif, konsisten, dan mudah dikonsumsi klien.*

* **[Modul 03.1: Pemodelan Resource & Naming Convention REST](./bab-03-desain-restful-api/01-pemodelan-resource-naming.md)**
  * Target: Merancang resource URI yang konsisten berorientasi pada kata benda jamak (nouns) dan nesting hierarkis.
  * Ringkasan: Anti-pattern URI, filtering, sorting, handling parent-child resources, dan versioning strategi API (`/api/v1`).
* **[Modul 03.2: Standarisasi Payload Error & Metadata Pagination](./bab-03-desain-restful-api/02-standarisasi-error-pagination.md)**
  * Target: Menyeragamkan respons backend dan mengoptimasi pengiriman data bervolume besar secara bertahap.
  * Ringkasan: RFC 7807 (Problem Details), format pagination (Offset-based vs Cursor-based), dan arsitektur respons global.
* **[Modul 03.3: Spesifikasi API-First: OpenAPI/Swagger Specification](./bab-03-desain-restful-api/03-openapi-swagger-specification.md)**
  * Target: Menulis dokumentasi API sebagai kontrak hidup (*living contract*) yang dapat diverifikasi secara otomatis.
  * Ringkasan: Anatomi YAML OpenAPI 3.0, skema request/response modeling, dan validasi runtime berbasis spesifikasi kontrak.

---

### [Bab 04: Runtime Backend & Concurrency Model](./bab-04-runtime-backend-concurrency/README.md)
*Fokus: Mengupas bagaimana server runtime mengelola memori, thread eksekusi, serta I/O non-blocking dalam menangani ribuan koneksi bersamaan.*

* **[Modul 04.1: Eksekusi Proses: Single-Threaded Event Loop vs Multi-Threading](./bab-04-runtime-backend-concurrency/01-proses-eventloop-multithreading.md)**
  * Target: Membedah arsitektur runtime server modern (e.g., Node.js event loop vs Worker Threads/Go Goroutines).
  * Ringkasan: Call stack, event queue, libuv/thread pool, memory layout proses, dan profiling utilisasi CPU.
* **[Modul 04.2: Operasi I/O Non-Blocking & Asynchronous Programming](./bab-04-runtime-backend-concurrency/02-nonblocking-io-asynchronous.md)**
  * Target: Mengimplementasikan eksekusi asinkron tanpa mengorbankan keterbacaan kode (*callback hell mitigation*).
  * Ringkasan: Pola Promises, `async/await`, Event Emitters, streams, dan handling I/O bound vs CPU bound processing.
* **[Modul 04.3: Konfigurasi Runtime, Signals, & Graceful Shutdown](./bab-04-runtime-backend-concurrency/03-konfigurasi-graceful-shutdown.md)**
  * Target: Membangun aplikasi yang mampu mati secara elegan tanpa menyebabkan data korup atau transaksi terputus.
  * Ringkasan: 12-Factor App Config (`process.env`), handling sinyal OS (`SIGINT`, `SIGTERM`), dan pengurasan antrean koneksi (*draining*).

---

### [Bab 05: Relational Database Management Systems (PostgreSQL)](./bab-05-relational-database-postgresql/README.md)
*Fokus: Penguasaan sistem basis data relasional sebagai fondasi persistensi data transaksional.*

* **[Modul 05.1: Desain Relasi Data: Normalisasi, DDL, & Invariant Constraints](./bab-05-relational-database-postgresql/01-normalisasi-ddl-constraints.md)**
  * Target: Merancang skema tabel yang mematuhi bentuk normal ke-3 (3NF) dan integritas data yang kokoh.
  * Ringkasan: DDL syntax, Primary Keys, Foreign Keys dengan cascading rules, Unique constraints, dan Check constraints.
* **[Modul 05.2: Eksekusi Query DML, Operasi Join, & Indeksasi (B-Tree)](./bab-05-relational-database-postgresql/02-dml-joins-indexes.md)**
  * Target: Menulis query kompleks secara efisien dan mempercepat waktu eksekusi melalui indeksasi B-Tree.
  * Ringkasan: Filtering, Inner/Left/Right/Full Joins, agregasi, subqueries, indeksasi selektif, dan analisis output `EXPLAIN ANALYZE`.
* **[Modul 05.3: Prinsip Transaksi ACID & Tingkat Isolasi (Isolation Levels)](./bab-05-relational-database-postgresql/03-transaksi-acid-isolation-levels.md)**
  * Target: Mencegah anomali konkurensi (Dirty Read, Non-repeatable Read, Phantom Read) pada mutasi data multi-tabel.
  * Ringkasan: Atomicity, Consistency, Isolation, Durability; sintaks `BEGIN`, `COMMIT`, `ROLLBACK`, dan perbandingan isolation level.

---

### [Bab 06: Data Access Patterns & Manajemen Koneksi](./bab-06-data-access-patterns/README.md)
*Fokus: Mengintegrasikan aplikasi backend dengan database engine menggunakan pola akses data yang efisien dan aman dari eksploitasi.*

* **[Modul 06.1: Connection Pooling, Latensi Jaringan, & Driver Database](./bab-06-data-access-patterns/01-connection-pooling-latensi.md)**
  * Target: Mengelola siklus hidup koneksi TCP ke database agar efisien dan tidak menguras alokasi memori server.
  * Ringkasan: Arsitektur connection pool (min/max connections, idle timeout), amortisasi koneksi TCP, dan driver level database.
* **[Modul 06.2: Raw SQL vs Query Builders vs ORM: Analisis Trade-off](./bab-06-data-access-patterns/02-raw-sql-querybuilder-orm.md)**
  * Target: Menentukan teknologi data access layer yang tepat berdasarkan kompleksitas domain bisnis dan performa.
  * Ringkasan: Perbandingan arsitektur Prisma/TypeORM/Knex vs Raw Query, bahaya N+1 query problem, dan teknik eager loading.
* **[Modul 06.3: Mitigasi SQL Injection melalui Prepared Statements](./bab-06-data-access-patterns/03-mitigasi-sql-injection-prepared-statements.md)**
  * Target: Menjamin seluruh query yang dikompilasi oleh aplikasi kebal dari serangan injeksi kode berbahaya.
  * Ringkasan: Mekanisme parsing query plan di database, parameterized queries, bahaya string concatenation, dan audit keamanan DML.

---

### [Bab 07: Autentikasi, Otorisasi, & Keamanan Identitas](./bab-07-autentikasi-otorisasi-keamanan/README.md)
*Fokus: Menerapkan mekanisme verifikasi identitas pengguna dan pembatasan hak akses terhadap resource terproteksi.*

* **[Modul 07.1: Hashing Kriptografis: Bcrypt/Argon2 & Penyimpanan Kredensial](./bab-07-autentikasi-otorisasi-keamanan/01-kriptografi-hashing-kredensial.md)**
  * Target: Menyimpan kredensial otentikasi secara aman menggunakan fungsi hash adaptif searah.
  * Ringkasan: Perbedaan enkripsi vs hashing, peran Salt dan Work Factor/Cost, mitigasi rainbow table attacks menggunakan Bcrypt/Argon2id.
* **[Modul 07.2: Stateful Session Management vs Stateless Token (JWT)](./bab-07-autentikasi-otorisasi-keamanan/02-stateful-session-vs-jwt.md)**
  * Target: Mengimplementasikan sistem autentikasi modern berbasis JSON Web Token (Access & Refresh Token).
  * Ringkasan: Struktur 3-bagian JWT (Header, Payload, Signature), mitigasi XSS/CSRF via HttpOnly Secure Cookies, dan strategi token revocation.
* **[Modul 07.3: Role-Based Access Control (RBAC) & Middleware Pipeline](./bab-07-autentikasi-otorisasi-keamanan/03-rbac-middleware-pipeline.md)**
  * Target: Membangun mekanisme interceptor (*middleware*) untuk membatasi endpoint berdasarkan role dan permission.
  * Ringkasan: Rantai eksekusi middleware (*chain of responsibility*), ekstraksi context user, pengujian permission matrix (Admin, Staff, Customer).

---

### [Bab 08: Validasi Input, Error Handling, & Observabilitas](./bab-08-validasi-error-observabilitas/README.md)
*Fokus: Menghadirkan pertahanan input yang kokoh, penanganan error yang tidak membocorkan stack trace, serta logging untuk debugging produksi.*

* **[Modul 08.1: Sanitasi Input & Validasi Schema Payload](./bab-08-validasi-error-observabilitas/01-sanitasi-input-validasi-schema.md)**
  * Target: Memvalidasi keabsahan data HTTP body/query sebelum dieksekusi oleh domain logic layer.
  * Ringkasan: Penggunaan schema validator (e.g., Zod/Joi), type inference, white-list payload stripping, dan sanitasi payload XSS.
* **[Modul 08.2: Sentralisasi Exception Handling & Hierarki Error Domain](./bab-08-validasi-error-observabilitas/02-sentralisasi-exception-hierarki-error.md)**
  * Target: Menghilangkan unhandled promise rejections dan mengembalikan pesan kesalahan yang terstandarisasi.
  * Ringkasan: Pembuatan custom base `AppError` class, pemetaan status code otomatis, handling operational error vs programmer error.
* **[Modul 08.3: Structured Logging (JSON) & Contextual Trace IDs](./bab-08-validasi-error-observabilitas/03-structured-logging-trace-ids.md)**
  * Target: Menghasilkan log yang mudah di-parse oleh log aggregators (ELK/Datadog) lengkap dengan Correlation ID.
  * Ringkasan: Pola log level (DEBUG, INFO, WARN, ERROR), structured JSON format (Pino/Winston), dan tracing request lifecycle via UUID context.

---

### [Bab 09: Caching Strategies & Background Job Basics](./bab-09-caching-background-jobs/README.md)
*Fokus: Mengoptimalkan throughput aplikasi backend dengan mereduksi beban I/O database dan mendeligasikan pemrosesan berat secara asinkron.*

* **[Modul 09.1: In-Memory Caching (Redis) & Pola Cache-Aside](./bab-09-caching-background-jobs/01-in-memory-caching-redis.md)**
  * Target: Memanfaatkan cache engine berbasis memori untuk menyajikan data statis atau sering diakses secara sub-milidetik.
  * Ringkasan: Anatomi Redis key-value store, implementasi pola Cache-Aside (Lazy Loading), dan penentuan Time-To-Live (TTL).
* **[Modul 09.2: Cache Invalidation, TTL, Race Conditions, & Thundering Herd](./bab-09-caching-background-jobs/02-cache-invalidation-tradeoffs.md)**
  * Target: Mengelola masa kedaluwarsa cache secara akurat guna menghindari data basi (*stale data*) dan lonjakan beban tiba-tiba.
  * Ringkasan: Strategi invalidasi (Write-Through vs Write-Back), Thundering Herd problem, Cache Penetration, dan Cache Stampede mitigations.
* **[Modul 09.3: Paradigma Komputasi Asinkron: Message Broker & Workers](./bab-09-caching-background-jobs/03-asynchronous-jobs-worker-queues.md)**
  * Target: Memisahkan pemrosesan I/O berat (pengiriman email, invoice PDF) dari request-response cycle utama.
  * Ringkasan: Konsep Producer-Queue-Consumer, antrean pesan (Redis Streams/BullMQ), mekanisme retry, backoff strategy, dan Dead Letter Queue (DLQ).

---

### [Bab 10: Containerization, Testing, & Enterprise Deployment](./bab-10-testing-containerization-deployment/README.md)
*Fokus: Mengemas aplikasi ke dalam kontainer standar industri, memverifikasi fungsionalitas melalui otomasi pengujian, dan mendistribusikannya ke lingkungan live.*

* **[Modul 10.1: Testing Pyramid: Unit, Integration, & Mocking Dependencies](./bab-10-testing-containerization-deployment/01-testing-pyramid-integration.md)**
  * Target: Mengembangkan rangkaian tes otomatis untuk menjamin aplikasi tidak mengalami regresi fungsional.
  * Ringkasan: Framework pengujian (Jest/Vitest/Supertest), perancangan mock object untuk database/layanan pihak ketiga, dan isolated test databases.
* **[Modul 02: Containerization menggunakan Docker & Multi-Stage Builds](./bab-10-testing-containerization-deployment/02-docker-multi-stage-builds.md)**
  * Target: Mengemas aplikasi dan seluruh dependensi eksternal ke dalam Docker image yang ringkas, aman, dan deterministik.
  * Ringkasan: Anatomi Dockerfile, multi-stage builds untuk memperkecil ukuran image, manajemen non-root user, dan konfigurasi `docker-compose.yml`.
* **[Modul 10.3: Automasi CI/CD & Deployment Strategy untuk Layanan Backend](./bab-10-testing-containerization-deployment/03-cicd-deployment-strategy.md)**
  * Target: Mengotomatisasi siklus rilis kode dari repositori git hingga berjalan di remote cloud environment.
  * Ringkasan: Pipeline GitHub Actions (Lint -> Test -> Build -> Push Image), strategi deployment (Rolling update basics), dan health check probes.

---

## 4. Spesifikasi Capstone Project Enterprise

### Judul Proyek: "Core Commerce: Multi-Tenant Inventory & Order Engine"
Siswa diwajibkan membangun micro-monolith backend service berskala enterprise yang mengelola katalog barang multi-tenant, reservasi inventaris berkonsistensi tinggi (*high concurrency safe*), dan pemrosesan pesanan.

```
                                  CAPSTONE ARCHITECTURE
                             
[ HTTP Client / API Consumers ]
               |
               v
     +-------------------+
     |   API Gateway /   |   --> Enforces Rate Limiting
     |  Middleware Chain |   --> Extracts JWT Claims & Context Injection
     +-------------------+   --> Formats RFC 7807 Error Responses
               |
               +-------------------------------------------------+
               |                                                 |
               v                                                 v
    +-----------------------+                         +----------------------+
    | Catalog & Order API   |                         |  Auth & User API     |
    +-----------------------+                         +----------------------+
          |           \                                          |
          |            \ (On Cache Miss)                         |
          |             v                                        |
          |       +---------------+                              |
          |       |  Redis Cache  |                              |
          |       +---------------+                              |
          |                                                      |
          +-----------------------+                              |
          |                       |                              |
          v                       v                              v
+-------------------+   +--------------------+        +----------------------+
| PostgreSQL Engine |   | Async Job Producer |        | PostgreSQL Engine    |
| (ACID Transaction |   +--------------------+        | (Tenant Isolation    |
|  Strict Locking)  |             |                   |  Users, Roles, Auth) |
+-------------------+             v                   +----------------------+
                         +--------------------+
                         | Redis Queue Broker |
                         +--------------------+
                                  |
                                  v
                         +--------------------+
                         | Background Worker  |
                         | (Email/DLQ Engine) |
                         +--------------------+
```

### 1. Spesifikasi Fungsional & Modul Layanan
* **Identity & Access Management (IAM)**: Registrasi akun, verifikasi email token, login dengan rate limiting, penerbitan Access Token (JWT) dan Refresh Token yang tersimpan aman di database/Redis dengan rotasi otomatis.
* **Hierarchical Role-Based Access Control (RBAC)**: Pembagian akses spesifik untuk 3 peran: `SUPER_ADMIN`, `TENANT_MERCHANT`, dan `CUSTOMER`.
* **Inventory Management with Pessimistic Locking**: Penanganan stok produk menggunakan database transactional locks (`SELECT ... FOR UPDATE`) untuk mencegah kondisi *overselling* saat beberapa order mengakses stok terakhir secara bersamaan.
* **Order Processing State Machine**: Alur status transaksi pesanan yang terkendali: `PENDING_PAYMENT` -> `PAID` -> `PROCESSING` -> `SHIPPED` -> `COMPLETED` atau `CANCELLED`. Pembatalan pesanan wajib mengembalikan kuantitas stok secara otomatis via transaksi ACID.
* **Asynchronous Notification Service**: Pengiriman tanda terima pesanan diproses di luar siklus request HTTP utama menggunakan antrean latar belakang (*background message queue*) lengkap dengan skenario eksponensial retry.

### 2. Standar Arsitektur & Aturan Non-Fungsional (Enterprise SLA)
* **Pemisahan Layer (Layered Clean Architecture)**:
  * `Controller / Handler`: Bertanggung jawab atas ekstraksi data HTTP, pemetaan status code, dan orkestrasi payload.
  * `Service / Domain Layer`: Pusat implementasi invariant bisnis; murni, tidak bergantung langsung pada objek context request HTTP.
  * `Repository Layer`: Satu-satunya pintu akses mutasi basis data.
* **Transaksional Database**: Seluruh mutasi yang mencakup lebih dari satu tabel (contoh: pembuatan data Order + pemotongan data Stock + pembuatan OrderHistory) WAJIB dieksekusi di dalam satu blok transaksi atomik.
* **Desain Skema Basis Data Relasional**:
  * Menggunakan database PostgreSQL.
  * Seluruh primary key wajib menggunakan format UUIDv4 atau ULID guna mencegah eksploitasi enumerasi ID.
  * Menerapkan audit timestamp (`created_at`, `updated_at`, `deleted_at` untuk soft-deletes).
* **Standar Respon API & Error Handling**:
  * Seluruh payload error WAJIB mematuhi format RFC 7807 (Problem Details).
  * Request correlation ID (`X-Request-ID`) wajib disertakan di setiap request dan tercatat pada output log yang berformat JSON.

### 3. Kriteria Pengujian & Otomasi CI/CD
* **Unit Testing Coverage**: Menghasilkan minimal cakupan tes 80% pada seluruh fungsi di Service / Domain Layer.
* **Integration Testing**: Menyediakan skenario pengujian endpoint interaktif dari level HTTP hingga ke database nyata (menggunakan testcontainers atau database uji terisolasi).
* **Container Packaging**: Proyek harus memiliki file `Dockerfile` (multi-stage build dengan ukuran maksimal image < 150MB) dan `docker-compose.yml` yang menjalankan aplikasi, database PostgreSQL, dan Redis hanya dengan perintah `docker-compose up --build`.

---
*Silabus ini merupakan dokumen panduan hidup. Lanjutkan proses belajar dengan menavigasi modul pertama pada tautan berikut: [Bab 01: Fondasi Backend & Arsitektur Internet](./bab-01-fondasi-backend-arsitektur-internet/README.md).*