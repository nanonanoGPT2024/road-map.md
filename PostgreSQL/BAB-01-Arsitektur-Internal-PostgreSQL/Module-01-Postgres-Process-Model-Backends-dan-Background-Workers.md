# PostgreSQL Process Architecture: Postmaster, Backend Processes, & Background Workers

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, Anda mampu:

- **Menjelaskan** hierarki proses PostgreSQL secara akurat: dari Postmaster sebagai induk hingga setiap backend process dan background worker yang di-fork darinya
- **Mengidentifikasi** setiap proses PostgreSQL yang berjalan di sistem operasi menggunakan `ps`, `pg_stat_activity`, dan `pg_stat_bgwriter`
- **Mendiagnosis** bottleneck performa yang berakar dari konfigurasi proses yang salah, seperti `max_connections` terlalu tinggi atau `autovacuum_max_workers` tidak memadai
- **Mengkonfigurasi** parameter proses kritis (`max_connections`, `max_worker_processes`, `max_parallel_workers`) berdasarkan kapasitas hardware yang tersedia
- **Membangun** custom background worker menggunakan extension API untuk kebutuhan pemrosesan asinkron
- **Menelusuri** akar masalah koneksi habis, zombie process, dan autovacuum yang tidak berjalan menggunakan query diagnostik yang tepat

---

## 2. Prerequisite

Sebelum mempelajari modul ini, Anda harus memahami:

| Konsep | Level yang Dibutuhkan | Referensi |
|---|---|---|
| **Proses & Thread di Linux** | Memahami fork(), PID, parent-child process | `man 2 fork`, `man 1 ps` |
| **Inter-Process Communication (IPC)** | Shared memory, semaphore, socket dasar | POSIX IPC fundamentals |
| **File Descriptor & Socket** | TCP socket, Unix domain socket | `man 7 socket` |
| **Dasar SQL & PostgreSQL** | Bisa menjalankan query SELECT, INSERT | PostgreSQL Getting Started |
| **Sistem File Linux** | Pemahaman `/proc`, `/var/run`, file permission | Linux filesystem hierarchy |
| **Konsep Database Umum** | Transaction, ACID, connection pooling | Database fundamentals |

---

## 3. Concept

### Paradigma Multi-Process vs Multi-Thread

PostgreSQL menggunakan arsitektur **multi-process** (bukan multi-thread seperti MySQL InnoDB atau Oracle). Setiap koneksi klien ditangani oleh **proses OS yang terpisah**, bukan thread dalam satu proses. Ini adalah keputusan arsitektur fundamental yang dibuat pada era 1990-an dan dipertahankan hingga hari ini karena alasan stabilitas dan isolasi memori.

Ketika satu backend process crash karena bug atau memory corruption, proses lain **tidak terpengaruh** — kernel OS menjamin isolasi address space antar proses. Berbanding terbalik dengan arsitektur multi-thread: satu thread yang corrupt dapat menghancurkan heap memori yang dibagi seluruh thread lain.

### Hierarki Proses PostgreSQL

```
Postmaster (PID 1 dalam konteks PostgreSQL)
│
├── Background Workers
│   ├── autovacuum launcher
│   ├── autovacuum worker (1..N)
│   ├── bgwriter
│   ├── walwriter
│   ├── checkpointer
│   ├── stats collector
│   ├── logical replication launcher
│   └── custom background workers (extensions)
│
└── Backend Processes (1 per koneksi klien)
    ├── backend untuk client A
    ├── backend untuk client B
    └── backend untuk client C
```

### Tiga Kategori Proses Utama

**1. Postmaster** — Supervisor proses tunggal yang mendengarkan koneksi masuk dan men-fork semua proses lain. Ini adalah proses pertama yang berjalan saat PostgreSQL start.

**2. Backend Processes** — Proses yang lahir untuk melayani satu koneksi klien spesifik. Hidup dan mati bersama koneksi tersebut. Menjalankan query, mengelola transaksi, dan berkomunikasi dengan klien melalui protokol wire PostgreSQL.

**3. Background Workers** — Proses yang berjalan di latar belakang untuk tugas-tugas pemeliharaan dan infrastruktur. Tidak melayani koneksi klien secara langsung. Dibagi menjadi:
- **Built-in background workers**: bgwriter, walwriter, checkpointer, autovacuum, stats collector
- **Custom background workers**: didaftarkan oleh extensions atau kode aplikasi

### Shared Memory sebagai Tulang Punggung Komunikasi

Semua proses PostgreSQL berkomunikasi melalui **shared memory segment** yang dialokasikan saat startup. Ini mencakup:
- **Buffer pool** (shared_buffers): Cache halaman data yang dibagi semua proses
- **WAL buffers**: Buffer untuk Write-Ahead Log sebelum di-flush ke disk
- **Lock table**: Struktur data untuk manajemen lock antar proses
- **Proc array**: Array metadata semua proses aktif (digunakan untuk visibility checks)

---

## 4. Why?

### Masalah yang Dipecahkan oleh Arsitektur Ini

**Masalah 1: Isolasi Kegagalan**

Bayangkan 500 pengguna terhubung ke database. Jika satu query mengalami segmentation fault karena bug di extension C, hanya proses tersebut yang mati. Postmaster mendeteksi kematian anak dan melakukan recovery terbatas. 499 pengguna lain tidak merasakan gangguan.

Dalam arsitektur thread-based, satu thread yang crash dapat mengkorupsi shared heap dan membunuh seluruh database server.

**Masalah 2: Keamanan Memory**

Setiap backend process memiliki address space privat. Data sensitif (password hash, data klien A) tidak bisa diakses oleh proses klien B meskipun keduanya berjalan di server yang sama. Kernel OS menegakkan isolasi ini secara hardware.

**Masalah 3: Tugas Pemeliharaan yang Tidak Mengganggu Klien**

Tanpa background workers, siapa yang akan membersihkan dead tuples (VACUUM)? Siapa yang menulis dirty pages ke disk secara berkala (bgwriter)? Siapa yang mem-flush WAL (walwriter)? 

Background workers memisahkan tanggung jawab pemeliharaan dari tanggung jawab melayani klien, sehingga keduanya bisa dioptimalkan secara independen.

**Masalah 4: Skalabilitas Tugas Paralel**

Dengan `max_worker_processes` dan parallel query workers, PostgreSQL dapat mendistribusikan satu query besar ke beberapa CPU core menggunakan proses terpisah yang berbagi data melalui shared memory — tanpa risiko race condition yang kompleks seperti pada multi-threading.

---

## 5. What?

### Postmaster: Definisi Presisi

**Postmaster** adalah proses supervisor PostgreSQL yang:
- Membaca file konfigurasi (`postgresql.conf`, `pg_hba.conf`) saat startup
- Mengalokasikan shared memory segment (shared_buffers, WAL buffers, lock tables)
- Membuka listening socket pada port yang dikonfigurasi (default: 5432)
- Menerima koneksi masuk dan men-fork backend process untuk setiap koneksi
- Memonitor semua child process dan melakukan cleanup jika ada yang crash
- Menangani sinyal OS (`SIGTERM` untuk shutdown graceful, `SIGINT` untuk fast shutdown, `SIGQUIT` untuk immediate shutdown)

**Binary**: `postgres` (bukan `postmaster` — nama `postmaster` adalah symlink historis)

**PID file**: `$PGDATA/postmaster.pid`

### Backend Process: Definisi Presisi

**Backend process** adalah proses yang:
- Di-fork oleh Postmaster untuk setiap koneksi klien yang diterima
- Menjalankan satu session PostgreSQL lengkap
- Mengelola state transaksi, cursor, prepared statements untuk session tersebut
- Berkomunikasi dengan klien menggunakan **PostgreSQL wire protocol** (binary protocol berbasis TCP atau Unix socket)
- Memiliki akses ke shared memory (shared_buffers) tetapi private memory untuk execution context
- Hidup selama koneksi klien aktif; mati ketika klien disconnect

**Identifikasi**: Terlihat sebagai `postgres: username database [idle|SELECT|INSERT|...]` di output `ps`

### Background Workers: Definisi Presisi

**Background workers** adalah proses yang:
- Di-fork oleh Postmaster pada startup atau secara dinamis
- Tidak memiliki koneksi klien yang dilayani
- Menjalankan tugas spesifik secara terus-menerus atau periodik
- Dapat di-restart otomatis oleh Postmaster jika crash
- Dapat mendaftarkan diri ke shared memory untuk koordinasi dengan proses lain

**Spesifikasi Teknis Built-in Background Workers:**

| Worker | Fungsi | Parameter Konfigurasi |
|---|---|---|
| `bgwriter` | Menulis dirty shared buffers ke disk secara proaktif | `bgwriter_delay`, `bgwriter_lru_maxpages` |
| `walwriter` | Mem-flush WAL buffers ke WAL files | `wal_writer_delay`, `wal_writer_flush_after` |
| `checkpointer` | Menjalankan checkpoint (sync semua dirty pages) | `checkpoint_timeout`, `checkpoint_completion_target` |
| `autovacuum launcher` | Menjadwalkan autovacuum workers | `autovacuum_naptime` |
| `autovacuum worker` | Menjalankan VACUUM/ANALYZE pada tabel | `autovacuum_max_workers`, `autovacuum_vacuum_cost_delay` |
| `stats collector` | Mengumpulkan statistik query dan tabel | `track_activities`, `track_counts` |
| `logical replication launcher` | Mengelola logical replication workers | `max_logical_replication_workers` |
| `walsender` | Mengirim WAL stream ke replica/standby | `max_wal_senders` |

---

## 6. How?

### Mekanisme Startup PostgreSQL: Step-by-Step

```
Step 1: pg_ctl start atau systemd memulai binary 'postgres'
        │
        ▼
Step 2: Postmaster membaca $PGDATA/postgresql.conf
        - Parsing semua parameter konfigurasi
        - Validasi nilai parameter
        │
        ▼
Step 3: Postmaster mengalokasikan Shared Memory
        - shmget() / mmap() untuk shared_buffers
        - Inisialisasi buffer pool dengan empty pages
        - Inisialisasi lock table (LWLock array)
        - Inisialisasi proc array (max_connections slots)
        - Inisialisasi WAL buffers
        │
        ▼
Step 4: Postmaster membuka Listening Socket
        - bind() pada port 5432 (atau yang dikonfigurasi)
        - listen() untuk menerima koneksi
        - Juga membuka Unix domain socket di /tmp/.s.PGSQL.5432
        │
        ▼
Step 5: Postmaster men-fork Background Workers
        - fork() → checkpointer process
        - fork() → bgwriter process
        - fork() → walwriter process
        - fork() → autovacuum launcher process
        - fork() → stats collector process
        │
        ▼
Step 6: Postmaster masuk ke event loop
        - accept() koneksi masuk
        - Untuk setiap koneksi: fork() → backend process baru
        - Memonitor child processes (waitpid())
        - Menangani sinyal OS
```

### Mekanisme Koneksi Klien: Step-by-Step

```
Step 1: Klien membuka TCP connection ke port 5432
        │
        ▼
Step 2: Postmaster menerima koneksi (accept())
        │
        ▼
Step 3: Postmaster men-fork() backend process baru
        - Child process mewarisi file descriptor socket
        - Parent (Postmaster) menutup socket tersebut
        - Child menjadi backend process eksklusif untuk klien ini
        │
        ▼
Step 4: Backend process melakukan Authentication
        - Membaca startup message dari klien (username, database, options)
        - Memeriksa pg_hba.conf untuk metode autentikasi
        - Menjalankan autentikasi (md5, scram-sha-256, trust, dll.)
        │
        ▼
Step 5: Backend process melakukan Initialization
        - Attach ke shared memory yang sudah ada
        - Mendaftarkan diri di proc array
        - Set search_path, timezone, dan parameter session
        │
        ▼
Step 6: Backend masuk ke query loop
        - Menerima query dari klien (ReadCommand)
        - Parse → Analyze → Rewrite → Plan → Execute
        - Mengirim hasil kembali ke klien
        - Kembali ke ReadCommand
        │
        ▼
Step 7: Klien disconnect
        - Backend process melakukan cleanup
        - Menghapus entry dari proc array
        - Melepas lock yang dipegang
        - Exit — proses mati
        - Postmaster menerima SIGCHLD, cleanup entry
```

### Mekanisme Fork dan Copy-on-Write

Ketika Postmaster men-fork backend process, kernel Linux menggunakan **Copy-on-Write (CoW)**:
- Child process awalnya berbagi page memory yang sama dengan parent
- Hanya ketika child **menulis** ke page tersebut, kernel membuat salinan privat
- Ini membuat fork() sangat efisien — backend baru tidak langsung mengkonsumsi memori besar
- Shared memory (shared_buffers) dikecualikan dari CoW — ini memang sengaja dibagi

### Mekanisme Autovacuum: Step-by-Step

```
autovacuum launcher (setiap autovacuum_naptime = 60 detik):
  │
  ├── Query pg_stat_user_tables
  ├── Identifikasi tabel yang butuh VACUUM:
  │   dead_tuples > autovacuum_vacuum_threshold + autovacuum_vacuum_scale_factor * reltuples
  │
  └── Kirim request ke Postmaster untuk fork autovacuum worker
      │
      ▼
  autovacuum worker:
  ├── Connect ke database target
  ├── Scan tabel yang ditentukan
  ├── Jalankan VACUUM (hapus dead tuples, update visibility map)
  ├── Jalankan ANALYZE jika perlu (update statistics)
  └── Exit setelah selesai
```

---

## 7. Analogy

### Analogi: Restoran dengan Sistem Pelayan Terpisah

Bayangkan PostgreSQL sebagai sebuah **restoran besar**:

**Postmaster = Manajer Restoran**
Manajer berdiri di pintu masuk, menyambut tamu yang datang. Ketika tamu tiba, manajer tidak melayani tamu itu sendiri — ia memanggil seorang pelayan khusus dan menugaskannya: *"Kamu, layani meja 7 sampai mereka selesai makan."* Manajer juga mengawasi semua pelayan — jika ada pelayan yang pingsan di tengah tu
