# BAB 06: Quiz, Challenge, & Knowledge Check
**Data Access Patterns & Manajemen Koneksi**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Overhead Koneksi & Justifikasi Connection Pooling**
   Mengapa membuka dan menutup koneksi database (TCP connection) pada setiap siklus HTTP request dianggap sebagai *anti-pattern* fatal dalam arsitektur backend berkinerja tinggi? Uraikan siklus hidup pembentukan koneksi database dari sudut pandang *network handshake* (TCP 3-way handshake, TLS negotiation), autentikasi protokol database, alokasi memori di sisi server engine, dan bagaimana mekanisme *connection pooling* memitigasi overhead tersebut secara teramortisasi.

2. **Active Record vs. Data Mapper: Arsitektur & Domain Purity**
   Bandingkan pola desain arsitektural antara *Active Record* (contoh: Eloquent, Prisma standard, Ruby on Rails ActiveRecord) dan *Data Mapper* (contoh: Hibernate/JPA, TypeORM DataMapper mode, SQLAlchemy Data Mapper). Analisis trade-off keduanya berdasarkan prinsip *Single Responsibility Principle* (SRP), *Domain-Driven Design* (DDD) purity, maintainability untuk sistem berskala enterprise, dan biaya kognitif (*cognitive load*) tim pengembang.

3. **Repository Pattern vs. Data Access Object (DAO)**
   Meskipun sering dianggap sinonim, *Repository Pattern* dan *DAO Pattern* memiliki level abstraksi semantik yang fundamental berbeda. Jelaskan perbedaan semantik antara Repository (sebagai emulasi *in-memory collection* dari domain aggregate) dengan DAO (sebagai abstraksi direct CRUD pada tabel database). Kapan penggunaan DAO murni lebih superior dibandingkan Repository dalam konteks arsitektur backend modern?

4. **Anatomi Siklus Hidup Connection Pool**
   Sebuah connection pool modern (seperti HikariCP, pgpool, atau database driver bawaan) mengelola status koneksi melalui *state machine*. Jelaskan transisi status koneksi antara: `Idle`, `Active/In-Use`, `Suspended`, dan `Evicted/Closed`. Apa implikasi teknis dari parameter konfigurasi `maxLifetime`, `idleTimeout`, dan `connectionTimeout` terhadap kestabilan sistem jika database berada di balik infrastruktur NAT gateway atau AWS Network Load Balancer (NLB)?

5. **Mekanisme Terjadinya N+1 Query Problem**
   Jelaskan secara mekanis bagaimana *N+1 Query Problem* terjadi pada lapisan abstraksi ORM (Object-Relational Mapping). Mengapa *Lazy Loading* secara default menjadi pedang bermata dua (*double-edged sword*)? Bedakan dua pendekatan mitigasinya: *Eager Loading* menggunakan single query dengan `LEFT JOIN` versus *Batch Loading* (dua query dengan operator `IN (...)`) dalam hal performa memori aplikasi dan saturasi CPU database.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Kekeliruan Sizing Connection Pool & Thread Starvation**
   Banyak pengembang beranggapan bahwa menetapkan ukuran connection pool sebesar-besarnya (misalnya `max_pool_size = 500`) pada backend instance akan meningkatkan concurrency. Buktikan secara matematis/arsitektural mengapa konfigurasi ini justru memicu degradasi performa (*disk thrashing*, *CPU context switching*, dan *lock contention*) pada database engine relasional (seperti PostgreSQL/MySQL). Jelaskan relevansi rumus empiris connection pool:
   $$\text{Connections} = (\text{Core Count} \times 2) + \text{Effective Spindle Count}$$

2. **Connection Leak & Transaction Hanging Mechanics**
   Apa yang terjadi di balik layar database engine ketika sebuah thread aplikasi backend meminjam koneksi dari pool, memulai transaksi (`BEGIN`), mengeksekusi satu *write operation*, namun gagal mengeksekusi `COMMIT` atau `ROLLBACK` sebelum koneksi dikembalikan (atau thread crash/hang)? Jelaskan dampak fenomena ini terhadap mekanika MVCC (Multi-Version Concurrency Control), bloating tabel (*dead tuples* yang gagal di-vacuum), dan saturasi table/row locks.

3. **Prepared Statements Caching: Driver-level vs. Server-side**
   Bagaimana cara kerja *Prepared Statement* secara internal di level protokol database dalam memisahkan fase parsing SQL, kompilasi *execution plan*, dan eksekusi data? Apa perbedaan mendasar antara *Client-Side Statement Caching* (di level driver backend) dan *Server-Side Prepared Statement* (di level database instance)? Apa risiko arsitektural dari *server-side statement cache exhaustion* jika aplikasi menggunakan query dynamic tanpa parameterization yang konsisten?

4. **Bahaya Transaction Boundary Melibatkan Network I/O (Long-Held Locks)**
   Perhatikan anti-pattern berikut:
   ```pseudocode
   BEGIN TRANSACTION;
   SELECT * FROM users WHERE id = :userId FOR UPDATE;
   res = HTTP_POST("https://payment-gateway.com/charge", amount); // External I/O
   UPDATE users SET balance = balance - amount WHERE id = :userId;
   COMMIT;
   ```
   Lakukan *failure mode analysis* terhadap kode di atas. Mengapa menyertakan operasi *synchronous network call* (RPC/HTTP) ke sistem pihak ketiga di dalam batas transaksi database lokal merupakan penyebab utama habisnya connection pool (*pool exhaustion*) dan *cascading failure* di sistem produksi?

5. **Read-Write Splitting & Replica Lag Anomalies**
   Saat menerapkan pattern *Read-Write Splitting* di mana write query diarahkan ke database *Primary* dan read query diarahkan ke database *Read Replica*, masalah apa yang terjadi akibat *asynchronous replication lag*? Jelaskan skenario "Read-Your-Own-Writes" *inconsistency* dari sudut pandang user journey (misal: user update profile, refresh halaman, data lama kembali muncul). Bagaimana teknik penanganannya pada level data access layer (misal: *sticky routing* atau *lag-aware routing*)?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Kasus Incident Connection Pool Depletion pada Flash Sale
Sebuah backend e-commerce berbasis microservices mengalami insiden saat kampanye flash sale. Log aplikasi dipenuhi error:
`ConnectionPoolTimeoutException: Timeout waiting for connection from pool (limit=30, timeout=5000ms)`
Trafik CPU pada service backend mencapai 15%, namun database CPU spike hingga 98%. Setelah dianalisis, latensi query produk yang biasanya 5ms membengkak menjadi 4500ms akibat adanya *unindexed query* yang dijalankan bersamaan dengan ribuan transaksi checkout. Akibatnya, semua worker thread di backend memblokir eksekusi sambil menunggu koneksi dari pool, memicu *thread starvation* pada HTTP server (e.g., Tomcat/Node.js/Gunicorn) dan menyebabkan *healthcheck endpoint* gagal merespons hingga Kubernetes me-restart Pod secara terus-menerus (*CrashLoopBackOff*).

* **Pertanyaan Diagnostik:**
  1. Bagaimana urutan mitigasi darurat (*circuit breaker*, degradasi fitur, isolasi connection pool) yang harus Anda instruksikan kepada tim SRE untuk memulihkan ketersediaan sistem tanpa merusak integritas database?
  2. Bagaimana merancang arsitektur isolasi connection pool (*bulkheading pattern*) antara transaksi kritikal (Order/Payment) dan operasional non-kritikal (Browsing/Search) agar query lambat pada satu domain tidak melumpuhkan seluruh aplikasi?

---

### Skenario B: Kasus Data Corruption & Lost Update pada Sistem Dompet Digital
Sebuah sistem *fintech wallet* memproses transaksi pemindahan saldo menggunakan ORM standard. Dua proses konkuren (Proses A dan Proses B) mencoba menarik saldo dari dompet yang sama secara simultan:
- **Kondisi Awal Saldo:** Rp 1.000.000
- **Proses A:** Menarik Rp 600.000
- **Proses B:** Menarik Rp 500.000
Kedua transaksi membaca saldo awal yang sama (Rp 1.000.000) ke dalam memori aplikasi menggunakan object/entity mapping standar. Proses A menghitung sisa saldo di memori ($1.000.000 - 600.000 = 400.000$) dan melakukan `UPDATE wallets SET balance = 400000`. Sesaat setelahnya, Proses B menghitung sisa saldo di memorinya ($1.000.000 - 500.000 = 500.000$) dan melakukan `UPDATE wallets SET balance = 500000`. Transaksi selesai; saldo akhir menjadi Rp 500.000 padahal total penarikan adalah Rp 1.100.000 (perusahaan rugi Rp 600.000).

* **Pertanyaan Diagnostik:**
  1. Analisis anomali konkurensi di atas. Mengapa pola abstraksi ORM "Fetch -> Mutate in Memory -> Save Entity" memicu *Second Lost Update Problem* pada level isolasi database standar (Read Committed)?
  2. Rancang **dua solusi arsitektural berbeda** untuk memecahkan masalah ini pada level Data Access Layer:
     - Solusi 1: Menggunakan *Pessimistic Locking* via Data Access Pattern yang eksplisit.
     - Solusi 2: Menggunakan *Atomic Update Query* / *Optimistic Locking* dengan version column. Bandingkan trade-off latensi dan throughput dari kedua pendekatan tersebut!

---

### Skenario C: Migrasi Monolith ORM-Heavy ke High-Throughput Batch Ingestion
Sebuah perusahaan logistik menerima metrik IoT dari 50.000 armada truk setiap 10 detik. Implementasi lama menggunakan ORM (Entity-based) di mana setiap payload array JSON di-looping, di-mapping menjadi Entity object, dan disimpan menggunakan repository method:
```pseudocode
foreach (data in telemetryBatch) {
    telemetryRepo.save(new TelemetryEntity(data)); // Menghasilkan 1 insert query per record
}
```
Ketika skala armada bertambah, konsumsi RAM service melonjak menjadi 16GB (terkena *Out-Of-Memory*), dan throughput sistem mandek di angka 200 records/detik dengan jutaan antrean pesan menumpuk di Message Broker. Database engine mencatat I/O wait tinggi dengan puluhan ribu transaksi mini per detik.

* **Pertanyaan Diagnostik:**
  1. Identifikasi *memory overhead* dan *network round-trip overhead* yang diciptakan oleh lifecycle tracking/dirty checking pada ORM dalam menangani data ingestion berkecepatan tinggi.
  2. Rancang ulang arsitektur Data Access Pattern untuk kasus ini: Bagaimana kombinasi penggunaan *Unit of Work*, *JDBC/Driver Batch Execution* (`COPY` protocol pada PostgreSQL atau Multi-value `INSERT`), dan pembuangan lapisan ORM abstraksi dapat mendongkrak performa sistem hingga 50.000 records/detik dengan konsumsi RAM di bawah 512MB?

---

## 4. Chapter Challenge

### Tantangan Praktis: Implementasi Thread-Safe Database Connection Pool Sederhana dengan Leak Detection

#### Problem Description
Di lingkungan produksi, kegagalan memahami cara kerja pooler menyebabkan masalah fatal: developer tidak menutup koneksi (*connection leak*), terjadi *deadlock* saat thread kehabisan resource, atau aplikasi meminjam koneksi mati (*broken pipe*). Untuk memahami mekanisme internal secara mendalam, Anda dilarang menggunakan library pool pihak ketiga (seperti HikariCP, Apache DBCP, atau pool bawaan ORM). Anda ditantang untuk membangun sebuah modul **Custom Mini Connection Pool** yang thread-safe menggunakan abstraksi socket/mock database connection pada bahasa pemrograman backend pilihan Anda (misal: Go, Java, TypeScript/Node.js, atau Python).

#### Requirements
1. **Pool Initialization & Resource Boundary:**
   - Inisialisasi pool dengan konfigurasi: `min_connections`, `max_connections`, `acquire_timeout_ms`, dan `leak_detection_threshold_ms`.
   - Pool harus melakukan *pre-warming* koneksi sejumlah `min_connections`.
   - Kapasitas pool tidak boleh melebihi `max_connections` dalam kondisi konkurensi ekstrem.

2. **Thread-Safe Acquire & Release:**
   - Menyediakan interface/method `acquire(): Connection` dan `release(Connection)`.
   - Menggunakan mekanisme sinkronisasi primitif yang tepat (*Mutex/Locks*, *Condition Variables*, atau *Blocking Queue/Buffered Channels*) untuk mencegah *race condition* antar worker threads saat meminjam atau mengembalikan koneksi.
   - Jika koneksi kosong dan pool sudah mencapai `max_connections`, request peminjam harus menunggu secara non-busy waiting (*blocking*) hingga koneksi tersedia atau durasi `acquire_timeout_ms` terlampaui (throw exception/error timeout).

3. **Active Connection Health Check:**
   - Sebelum koneksi diserahkan ke consumer via `acquire()`, pool harus memverifikasi apakah status koneksi masih hidup (validasi ping/mock alive). Jika koneksi mati/broken, koneksi harus di-*evict*, ditutup fisiknya, dan dibuatkan koneksi baru sebagai pengganti.

4. **Connection Leak Detector:**
   - Implementasikan sistem tracking *background tracker* atau *timer task*.
   - Jika sebuah koneksi dipinjam oleh thread dan tidak dikembalikan via `release()` dalam jangka waktu melebihi `leak_detection_threshold_ms`, sistem harus mencetak log **WARNING** ke console dengan menyertakan *stack trace* pemanggil awal tempat fungsi `acquire()` dieksekusi.

#### Constraints
- Dilarang keras menggunakan library pooling yang sudah jadi (e.g., generic-pool, HikariCP, bawaan sql.DB Go untuk logic pooling-nya, dsb). Anda harus mengimplementasikan state management dan thread blocking dari nol.
- Abstraksi `Connection` boleh berupa representasi socket TCP nyata ke database lokal (PostgreSQL/MySQL) ATAU sebuah Mock Connection Object yang memiliki delay I/O buatan untuk simulasi network latency.
- Solusi harus terbebas dari *deadlock* dan *busy-waiting loop* (penggunaan `while(true) { check(); }` tanpa backoff/sleep/blocking signaling dilarang keras).

#### Expected Output
1. Source code implementasi mini connection pool yang bersih, modular, dan terdokumentasi.
2. Unit Test / Stress Test skenario:
   - **Test 1:** 50 concurrent worker threads meminjam koneksi dari pool dengan `max_connections = 10`. Buktikan tidak ada koneksi yang bocor dan throughput berjalan stabil.
   - **Test 2:** Timeout handling ketika kapasitas habis dan peminjam melebihi `acquire_timeout_ms`.
   - **Test 3:** Leak detection alert: Sengaja buat 1 worker thread meminjam koneksi tanpa memanggil `release()`, dan buktikan sistem berhasil mendeteksi serta mencetak stack trace thread yang bersalah dalam interval waktu yang ditentukan.

---

## 5. Knowledge Check & Checklist

Beri tanda centang pada item yang telah Anda kuasai secara independen. Evaluasi diri Anda dengan objektif sebelum melanjutkan ke bab berikutnya.

### Saya harus memahami:
- [ ] Siklus hidup pembentukan koneksi TCP database (overhead 3-way handshake, TLS, autentikasi protokol DB) dan pentingnya teknik amortisasi melalui Connection Pooling.
- [ ] Perbedaan filosofis dan arsitektural antara Active Record Pattern vs. Data Mapper Pattern, serta dampaknya terhadap decoupling domain model.
- [ ] Batasan konseptual antara Repository Pattern (Domain Layer abstraction) dan DAO (Infrastructure Persistence abstraction).
- [ ] Mekanisme internal Connection Pool: transisi status koneksi (*Idle*, *Active*, *Validation*, *Eviction*), sizing pool yang realistis berbasis hardware, dan kalkulasi throughput.
- [ ] Penyebab mekanis *N+1 Query Problem* pada ORM dan trade-off performa teknik mitigasi (*Join Fetching* vs. *Batch In-Query*).
- [ ] Bahaya arsitektural menaruh *External Synchronous Network I/O* di dalam boundaries transaksi database (*Long-held lock problem*).
- [ ] Fenomena *Second Lost Update* dan perancangan strategi konkurensi data access (*Pessimistic Locking* `FOR UPDATE` vs. *Optimistic Locking* via version check).
- [ ] Konsekuensi arsitektur *Read-Write Splitting* terhadap *Replication Lag* dan teknik mitigasi anomali inkonsistensi pembacaan data.

### Saya tidak perlu menghafal:
- [ ] Detail sintaks byte protocol binary dari database driver spesifik (misal: struktur PostgreSQL Frontend/Backend Protocol packet wire format).
- [ ] Nama parameter konfigurasi internal yang spesifik untuk setiap library pool komersial (misal: nama exact property camelCase vs snake_case antara HikariCP, c3p0, atau node-pool; hal ini cukup dilihat pada dokumentasi resmi).
- [ ] Implementasi algoritma low-level data structure lock-free queue (seperti *Michael-Scott Queue*) yang ada di dalam internal library concurrent programming, selama Anda memahami cara mengonsumsi primitif concurrency bahasa tersebut.

### Saya harus bisa melakukan:
- [ ] Menghitung dan mengonfigurasi ukuran connection pool aplikasi backend secara optimal berdasarkan kapasitas CPU core, disk type (SSD/NVMe), dan batasan memori engine database.
- [ ] Melakukan profiling dan debugging terhadap aplikasi backend yang mengalami *Connection Leak* menggunakan logging pool leak detector, APM tools, atau thread dump.
- [ ] Mengidentifikasi dan membasmi *N+1 query* dari log profiling SQL query aplikasi yang menggunakan ORM.
- [ ] Menulis transaksi data access yang atomic, thread-safe, dan terhindar dari *lost updates* menggunakan mekanisme locking yang tepat sesuai beban sistem.
- [ ] Merancang isolasi boundary (*Bulkhead pattern*) pada lapisan data access pool agar kegagalan atau kelambatan query pada satu use-case tidak melumpuhkan ketersediaan seluruh microservice.