# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Kategori:** 04-Backend-and-Database  
**Bab 01:** Fondasi dan Arsitektur  
**Jalur:** Enterprise PostgreSQL Database Administrator (DBA)

---

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis dan Membedah Arsitektur Memori dan Proses Tingkat Rendah:** Memahami interaksi antara *Shared Memory* (Buffer Pool, WAL Buffers, Lock Manager) dan *Local Memory* (Work Mem, Maintenance Work Mem) serta orkestrasi *Background Processes* PostgreSQL.
2. **Membedah Anatomi Storage Engine dan Page Layout:** Menginspeksi struktur biner 8KB *Page/Block*, tuple header, *Free Space Map* (FSM), *Visibility Map* (VM), dan mekanisme MVCC pada level disk.
3. **Mengoptimalkan Pipeline Write-Ahead Logging (WAL) dan Checkpointing:** Menghilangkan fenomena I/O spikes melalui tuning *spread checkpoints*, tuning WAL segment sizing, dan sinkronisasi flush disk.
4. **Menerapkan Strategi Mitigasi Buffer Contention dan Lock Spikes:** Mengidentifikasi *buffer lock starvation*, *dirty page eviction storms*, dan mengonfigurasi mekanisme *Clock Sweep* pada buffer eviction.
5. **Mengaudit dan Memvalidasi State Database Menggunakan Ekstensi Internal:** Menggunakan `pageinspect`, `pg_buffercache`, dan utilitas `pg_waldump` untuk troubleshooting insiden produksi secara deterministik.

---

## 2. Prerequisite
Untuk memahami materi modul ini secara komprehensif, peserta diwajibkan telah menguasai:
- Konsep dasar Relational Database Management System (ACID, relasi tabel, indexing dasar).
- Arsitektur sistem operasi Linux tingkat menengah (Virtual Memory Management, Dirty Pages, Kernel Page Cache, System Calls seperti `mmap`, `fsync`, `fdatasync`, `posix_fadvise`).
- Pengoperasian shell Bash dan administrasi Linux (penggunaan utilitas seperti `sysctl`, `iostat`, `vmstat`, `strace`, `perf`).
- Menyelesaikan Modul 01: Fondasi Instalasi, Basic Client-Server Protocol, dan Konfigurasi Dasar PostgreSQL.

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Model Proses dan Paradigma Shared-Memory Multi-Process
PostgreSQL tidak mengadopsi model *multi-threaded* melainkan *process-based concurrency model* berbasis model proses UNIX fork-and-exec historis:
- **Postmaster (Proses Induk):** Bertanggung jawab atas inisialisasi server, alokasi blok *System V Shared Memory* atau POSIX *mmap shared memory*, serta menangani sinyal sistem (`SIGTERM`, `SIGHUP`, `SIGQUIT`). Setiap ada request koneksi TCP/IP baru dari klien, Postmaster memvalidasi otentikasi awal, kemudian melakukan `fork()` untuk membuat proses dedicated bernama **Backend Process (Client Backend)**.
- **Backend Process:** Satu proses independen dialokasikan untuk setiap koneksi klien aktif. Proses ini mengeksekusi siklus query lifecycle (Parse, Rewrite, Plan, Execute). Isolasi memori antar proses dijamin oleh kernel, namun komunikasi antar proses dan akses data bersama dilakukan melalui alokasi **Shared Memory**.
- **Background Processes Mandatori:**
  - **Checkpointer:** Mengatur flush *dirty pages* dari Shared Buffers ke storage sistem secara periodik untuk mempercepat Recovery Time Objective (RTO).
  - **Background Writer (BgWriter):** Melakukan pembersihan *dirty pages* secara bertahap dan proaktif ke disk agar Backend Process yang membutuhkan buffer kosong tidak terblokir oleh operasi disk sync yang lambat.
  - **WAL Writer:** Memindahkan data log transaksi dari `wal_buffers` ke disk secara berkala atau ketika transaksi melakukan `COMMIT`.
  - **Autovacuum Launcher & Workers:** Daemon yang memicu sub-proses *autovacuum worker* untuk membersihkan *dead tuples*, mencegah *transaction ID (XID) wraparound*, dan memperbarui statistik katalog (`pg_statistic`).
  - **Stats Collector (pada PG <= 14) / Shared Memory Stats (PG 15+):** Mengagregasi metrik aktivitas database (I/O stats, index usage, table scans).
  - **Archiver:** Mengirim file segment WAL yang telah tertutup (16MB) ke media cold storage atau backup secondary.

```
+-----------------------------------------------------------------------------------+
| Linux Operating System / Host Resources                                           |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  | PostgreSQL Shared Memory Pool                                               |  |
|  |  +-----------------------------------------------------------------------+  |  |
|  |  | Shared Buffers (8KB Blocks Cache)                                     |  |  |
|  |  +-----------------------------------------------------------------------+  |  |
|  |  | WAL Buffers | Lock Tables | IPC Hash Tables | Free Space / Proc Array |  |  |
|  |  +-----------------------------------------------------------------------+  |  |
|  +-----------------------------------------------------------------------------+  |
|                                                                                   |
|  +----------------------+  +----------------------+  +-------------------------+  |
|  | Backend Process 1    |  | Backend Process 2    |  | Background Processes    |  |
|  | (Client Connection)  |  | (Client Connection)  |  |                         |  |
|  | +------------------+ |  | +------------------+ |  | [Checkpointer]          |  |
|  | | work_mem         | |  | | work_mem         | |  | [Background Writer]     |  |
|  | | maintenance_w_mem| |  | | maintenance_w_mem| |  | [WAL Writer]            |  |
|  | | temp_buffers     | |  | | temp_buffers     | |  | [Autovacuum Launcher]   |  |
|  | +------------------+ |  | +------------------+ |  | [Archiver]              |  |
|  +----------------------+  +----------------------+  +-------------------------+  |
+-----------------------------------------------------------------------------------+
```

### 3.2 Alokasi Memori: Shared Memory vs. Local Backend Memory
Arsitektur memori PostgreSQL terfragmentasi menjadi dua domain kritis:
1. **Shared Memory:** Dialokasikan saat instans PostgreSQL booting.
   - `shared_buffers`: Cache data page bersama. Nilai tipikal: 25%–40% dari total RAM fisik.
   - `wal_buffers`: Cache sirkular untuk record transaksi sebelum di-flush ke disk (default auto-tuned: 1/32 dari `shared_buffers`, maksimal 16MB).
   - Lock Spaces: Tracking lock level tabel, page, tuple, dan *advisory locks*.
2. **Local Memory (Per-Backend):** Dialokasikan dinamis oleh masing-masing Backend Process dari kernel memory (Heap) dan dilepaskan setelah eksekusi operasi tuntas:
   - `work_mem`: Alokasi memori untuk operasi sortasi (`ORDER BY`), hash tables (`Hash Join`), dan bitmap scans. *Penting:* Alokasi ini adalah per-node-per-query, bukan per-koneksi. Satu query kompleks dengan 4 join dapat mengalokasikan $4 \times \text{work\_mem}$.
   - `maintenance_work_mem`: Digunakan oleh operasi DDL dan maintenance berat seperti `VACUUM`, `CREATE INDEX`, dan penambahan Foreign Key.
   - `temp_buffers`: Menyimpan tabel sementara (*temporary tables*) lokal per koneksi.

### 3.3 Anatomi Storage: Heap File, Page Layout, dan Tuple Internals
Setiap relasi (tabel dan indeks) di PostgreSQL dipetakan ke disk sebagai sekumpulan file fisik di dalam direktori cluster (`$PGDATA/base/<database_oid>/<relfilenode>`). Jika ukuran tabel melebihi 1GB, PostgreSQL memotongnya menjadi segmen: `<relfilenode>.1`, `<relfilenode>.2`, dst.

Setiap file dipecah menjadi blok-blok tetap berukuran **8192 bytes (8KB)** yang disebut **Page**.

```
+--------------------------------------------------------------------+
|                         8192 Bytes Page                            |
+--------------------------------------------------------------------+
| PageHeaderData (24 bytes)                                          |
|   pd_lsn (8B) | pd_checksum (2B) | pd_flags (2B)                   |
|   pd_lower (2B) | pd_upper (2B) | pd_special (2B)                  |
|   pd_pagesize_version (2B) | pd_prune_xid (4B)                     |
+--------------------------------------------------------------------+
| ItemIdData Array (Line Pointers) [lp1, lp2, lp3, ...]             |
| (Tiap entri 4 bytes: offset, flags, length)  --------+            |
+------------------------------------------------------|-------------+
|               FREE SPACE AREA                        |             |
| (Area kosong tempat pd_lower bergerak turun,         |             |
|  dan pd_upper bergerak naik seiring alokasi)         |             |
|                                                      |             |
+------------------------------------------------------|-------------+
| HeapTupleHeaderData + Data (Tuple 3)                 |             |
| HeapTupleHeaderData + Data (Tuple 2)                 |             |
| HeapTupleHeaderData + Data (Tuple 1) <---------------+             |
+--------------------------------------------------------------------+
| Special Space (Hanya digunakan oleh indeks, 0 bytes pada Heap)     |
+--------------------------------------------------------------------+
```

#### Struktur Biner 8KB Page Header
- **PageHeaderData (24 bytes):**
  - `pd_lsn`: *Log Sequence Number* (64-bit unsigned integer). Mencatat byte offset WAL terakhir yang memodifikasi page ini. Digunakan untuk menegakkan aturan WAL Protocol dan Crash Recovery.
  - `pd_checksum`: Checksum integritas bit page untuk mendeteksi silent data corruption / hardware degradation.
  - `pd_lower`: Byte offset penunjuk akhir dari array *Line Pointer* (ItemId). Bertumbuh ke arah bawah (ke offset byte yang lebih besar).
  - `pd_upper`: Byte offset penunjuk awal dari *Tuple Data* terakhir yang ditulis. Bertumbuh ke arah atas (ke offset byte yang lebih kecil).
  - `pd_special`: Byte offset untuk struktur data khusus (misalnya pohon B-Tree). Pada heap page reguler, nilainya sama dengan ukuran block (8192).

#### Line Pointer (ItemIdData - 4 Bytes)
Line pointer adalah pointer internal array yang menunjuk ke lokasi fisik tuple di dalam page. Terdiri atas:
- Offset: Jarak dari byte ke-0 page menuju awal `HeapTupleHeaderData`.
- Flags: Menyimpan state pointer (`00`: Unused, `01`: Used/Normal, `10`: Hot-redirect, `11`: Dead).
- Length: Panjang biner tuple dalam satuan bytes.

Kombinasi antara **Nomor Block (32-bit)** dan **Line Pointer Offset (16-bit)** membentuk identitas fisik tuple yang dinamakan **ItemPointerData (CTID)**, dengan format `(block_number, line_pointer_index)`.

#### HeapTupleHeaderData (Minimal 23 Bytes)
Setiap baris data fisik dibungkus oleh metadata:
- `t_xmin`: Transaction ID (XID) dari transaksi yang memasukkan (*insert*) tuple ini.
- `t_xmax`: Transaction ID dari transaksi yang menghapus (*delete*) atau meng-update tuple ini. Jika tuple masih aktif, bernilai `0`.
- `t_cid`: *Command Identifier*, melacak urutan query dalam satu transaksi yang sama.
- `t_ctid`: Pointer yang menunjuk ke versi terbaru dari baris ini. Jika baris belum pernah di-update, `t_ctid` menunjuk ke dirinya sendiri. Jika baris telah di-update, `t_ctid` menunjuk ke CTID baris baru (bisa di page yang sama melalui HOT (*Heap-Only Tuple*) atau di page berbeda).
- `t_infomask` & `t_infomask2`: Bit flags penyimpan status transaksi (`HEAP_XMIN_COMMITTED`, `HEAP_XMIN_ABORTED`, `HEAP_XMAX_COMMITTED`, struktur null bitmap, dan jumlah atribut).

### 3.4 Buffer Manager dan Algoritma Clock Sweep
Buffer Manager mengontrol pemuatan page disk ke dalam `shared_buffers`. Ketika query membutuhkan page:
1. Buffer Manager melakukan hashing pada *Buffer Tag* (RelFileNode, ForkNumber, BlockNumber).
2. Jika ada di Shared Buffers (*Buffer Hit*), pin counter dinaikkan, dan buffer di-lock (Shared atau Exclusive).
3. Jika tidak ada (*Buffer Miss*), page harus dibaca dari disk (OS Page Cache atau Block Storage). Buffer Manager mencari slot kosong menggunakan algoritma **Clock Sweep**:
   - Jarum penunjuk (*clock hand*) menyusuri array buffer header sirkular.
   - Jika suatu buffer memiliki pin count > 0, buffer dilewati karena sedang dibaca oleh backend lain.
   - Jika pin count == 0, sistem memeriksa `usage_count`. Jika `usage_count > 0`, nilainya didekremen sebesar 1, dan jarum bergerak ke buffer berikutnya.
   - Jika `usage_count == 0` dan pin count == 0, buffer tersebut dipilih sebagai kandidat eviksi (*victim buffer*).
   - Jika buffer kandidat berada dalam status *dirty* (termodifikasi), proses backend terpaksa melakukan synchronous write ke OS Page Cache sebelum menimpa slot buffer tersebut dengan page baru.

---

## 4. Why & What

### Mengapa Paradigma Shared Buffers + OS Page Cache (Double Buffering) Diterapkan?
PostgreSQL tidak menggunakan direct I/O (`O_DIRECT`) secara default; ia mengandalkan arsitektur *Double Buffering*. Data dibaca dari storage fisik ke dalam kernel Linux Page Cache terlebih dahulu, baru kemudian disalin ke dalam `shared_buffers` PostgreSQL.
- **Kelebihan:** Operasi penulisan buffer dapat didelegasikan ke kernel caching subsystem. Kernel melakukan pengurutan blok (I/O scheduler elevator) dan *read-ahead optimization*.
- **Konsekuensi DBA:** Anda tidak boleh mengalokasikan 100% RAM ke `shared_buffers`. Mengalokasikan 80% RAM ke `shared_buffers` sering kali menyebabkan degradasi performa karena PostgreSQL bersaing langsung dengan Linux Dirty Page cache dan buffer kernel, memicu latency spikes akibat swapping atau OOM killer invocation.

### Mengapa Append-Only Storage Engine (MVCC) Menyebabkan Table Bloat?
PostgreSQL mengimplementasikan Multi-Version Concurrency Control (MVCC) tanpa *Undo Logs* (berbeda dari Oracle atau MySQL InnoDB). 
- Operasi `UPDATE` secara fisik adalah `DELETE` (menandai `t_xmax` tuple lama) diikuti oleh `INSERT` (menuliskan tuple baru lengkap beserta header baru di lokasi lain).
- Operasi `DELETE` hanya menandai baris sebagai *dead tuple* dengan mencatat commit XID pada `t_xmax`.
- Data fisik lama tidak dihapus secara *in-place* saat transaksi selesai agar transaksi konkuren lain yang berjalan pada isolasi `REPEATABLE READ` atau `READ COMMITTED` tetap dapat membaca snapshot data historis.
- Akibatnya: Jika sistem memiliki write-throughput tinggi tanpa konfigurasi `autovacuum` yang agresif, ruang disk akan membengkak (*bloat*), menurunkan scanning throughput dan cache hit ratio.

---

## 5. How (Workflow Detail)

### Alur Eksekusi Transaksi End-to-End: Write Path & WAL Emission

```
[Client]                [Backend Engine]           [Shared Buffers]          [WAL Buffers]            [Disk Subsystem]
   |                           |                          |                        |                         |
   |--- 1. BEGIN ------------->|                          |                        |                         |
   |--- 2. UPDATE t SET v=1 -->|                          |                        |                         |
   |                           |-- 3. Read Page --------->|                        |                         |
   |                           |   (Buffer Cache Hit)     |                        |                         |
   |                           |                          |                        |                         |
   |                           |-- 4. Mutasi Tuple ------>| (Mark Page DIRTY)      |                         |
   |                           |-- 5. Construct WAL rec -------------------------->|                         |
   |                           |                          |                        |                         |
   |--- 6. COMMIT ------------>|                          |                        |                         |
   |                           |-- 7. Request WAL Sync --------------------------->|                         |
   |                           |                          |                        |-- 8. Write & fsync() -->|
   |                           |                          |                        |      (Append to WAL)    |
   |<-- 9. Success (ACK) ------|                          |                        |                         |
   |                           |                          |                        |                         |
   |                           |              ... Waktu Berlalu ...                |                         |
   |                           |                          |                        |                         |
   |                           |                  [Checkpointer Engine]            |                         |
   |                           |                          |-- 10. Flush Dirty Page ------------------------->|
   |                           |                          |       (Sync ke base/)  |                         |
```

1. **Transaction Begin:** Klien mengirim perintah transaksi. Backend menginisialisasi state transaksi dan mengalokasikan Virtual XID (VXID).
2. **Execution & Buffer Pinning:** Backend mem-parsing perintah SQL. Backend membaca page yang bersangkutan ke dalam `shared_buffers` (jika belum ada). Pin counter dinaikkan, shared/exclusive buffer content lock diakuisisi.
3. **In-Memory Mutation:** Baris lama ditandai dengan `t_xmax = CurrentXID`. Baris baru disisipkan ke dalam page (bisa di blok yang sama jika muat, atau di blok baru). Page ditandai sebagai **DIRTY**.
4. **WAL Generation:** Backend memformat deskripsi biner perubahan data menjadi *WAL Record*. WAL record disalin ke dalam `wal_buffers`. LSN (Log Sequence Number) baru dicatat di header page yang bersangkutan (`pd_lsn`).
5. **Commit Phase:** Klien mengirimkan sinyal `COMMIT`. Transaksi mendapatkan global Real 32-bit XID dari *ProcArray*. Backend menandai status transaksi menjadi `COMMITTED` di `pg_xact` (dulu dikenal sebagai `pg_clog`).
6. **Synchronous WAL Flushing:** Berdasarkan setting `synchronous_commit = on`, backend memicu sistem untuk menulis seluruh data di `wal_buffers` hingga LSN commit transaksi ke storage fisik menggunakan system call `fdatasync()` / `fsync()`.
7. **Client Acknowledgment:** Begitu bit WAL telah terkunci di disk fisik, database mengembalikan status `SUCCESS` ke klien. *Page data yang termodifikasi di Shared Buffers tetap berada dalam kondisi DIRTY di RAM dan belum ditulis ke data file utama (`base/`).*
8. **Asynchronous Checkpointing:** Di latar belakang, proses `Checkpointer` bangun secara berkala (ditentukan oleh `checkpoint_timeout` atau volume `max_wal_size`), mengekstrak daftar dirty pages dari `shared_buffers`, menyortirnya berdasarkan lokasi disk (untuk meminimalkan random I/O seek), dan menuliskannya secara bertahap ke operating system page cache, diakhiri dengan pemanggilan `sync()` pada file data.

---

## 6. Analogi & Diagram ASCII

### Analogi: Pabrik Dokumen Arsip
Bayangkan arsitektur PostgreSQL seperti kantor audit enterprise:
- **Shared Buffers:** Meja kerja utama bersama tempat dokumen aktif diletakkan. Pegawai dapat membaca dan mencoret dokumen di meja ini.
- **Backend Process:** Pegawai audit independen. Masing-masing memiliki map catatan pribadi di tasnya (**Local Memory / `work_mem`**). Jika tasnya penuh, dia terpaksa menumpuk kertas coretan di lantai koridor (**Spill to disk / Temp files**).
- **WAL (Write-Ahead Log):** Buku jurnal hitam tebal berantai yang tidak bisa dihapus. Sebelum seorang pegawai mengubah angka pada formulir di meja kerja, dia **wajib** mencatat di buku jurnal hitam: *"Saya mengubah formulir #105 baris 3 dari nilai X menjadi Y"*. Buku ini langsung distempel basah dan dikunci di brankas baja (**fsync**). Jika gedung runtuh (server crash), isi formulir di meja kerja yang rusak dapat direkonstruksi dari buku jurnal ini.
- **Checkpointer:** Petugas kebersihan yang datang setiap 15 menit. Dia memfotokopi dokumen-dokumen yang telah dicoret-coret di meja kerja bersama dan menyusunnya rapi ke dalam lemari arsip baja di gudang (**Disk Heap Files**).

### Visualisasi: Siklus Hidup Buffer Page & Eviction
```
          [Disk Base Storage]
                   |
           (read 8KB block)
                   v
+------------------------------------+
|       Shared Buffers Pool          |
|                                    |
| [Buffer A]  [Buffer B]  [Buffer C] |
| (usage: 3)  (usage: 0)  (usage: 1) |
|   PIN: 1      PIN: 0      PIN: 0   |
|   CLEAN       DIRTY       CLEAN    |
+------------------------------------+
                   ^
                   | (Clock Hand Scan)
                   |
    Jarum Clock Sweep memeriksa Buffer B:
    1. Pin Count == 0? YES
    2. usage_count == 0? YES
    3. State: DIRTY!
       --> Backend terpaksa write Buffer B ke disk! (I/O Stall)
       --> Buffer B dievつい dan diganti Page Baru dari disk.
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Membedah Page Layout Menggunakan `pageinspect`
Kita akan menginspeksi representasi internal byte-level dari sebuah tuple menggunakan ekstensi bawaan PostgreSQL.

```sql
-- Inisialisasi ekstensi internal
CREATE EXTENSION IF NOT EXISTS pageinspect;

-- Buat skema tabel pengujian
DROP TABLE IF EXISTS accounts_test;
CREATE TABLE accounts_test (
    id int,
    username varchar(20),
    balance numeric(10,2)
);

-- Insert satu baris data
INSERT INTO accounts_test (id, username, balance) 
VALUES (1, 'alice', 1500.00);

-- Ambil koordinat fisik CTID
SELECT ctid, id, username, balance FROM accounts_test;
-- Output ctid bernilai: (0,1) -> Block 0, Line Pointer 1

-- Inspeksi Header Page dari Blok 0
SELECT lsn, checksum, flags, lower, upper, special, pagesize 
FROM page_header(get_raw_page('accounts_test', 0));

-- Hasil Tipikal:
-- lower: 28  (24 byte header + 4 byte line pointer lp1)
-- upper: 8152 (Tuple dialokasikan dari byte 8152 sampai 8192 = 40 bytes)
-- special: 8192

-- Inspeksi Detail ItemId / Line Pointer
SELECT * FROM page_items(get_raw_page('accounts_test', 0));
-- lp | lp_off | lp_flags | lp_len
--  1 |   8152 |        1 |     40

-- Inspeksi Header Tuple (t_xmin, t_xmax, t_ctid)
SELECT t_xmin, t_xmax, t_field3 as t_cid, t_ctid, 
       t_infomask2, t_infomask, to_hex(t_infomask) as infomask_hex
FROM heap_page_items(get_raw_page('accounts_test', 0));
```

Update tuple tersebut untuk melihat efek append-only MVCC:
```sql
-- Lakukan mutasi in-place secara logika
UPDATE accounts_test SET balance = 2000.00 WHERE id = 1;

-- Inspeksi kembali page_items
SELECT lp, lp_off, lp_flags, lp_len, t_xmin, t_xmax, t_ctid 
FROM heap_page_items(get_raw_page('accounts_test', 0));

-- Hasil observasi:
-- lp 1: t_xmin = XID_INSERT, t_xmax = XID_UPDATE, t_ctid = (0,2) -> Dead tuple
-- lp 2: t_xmin = XID_UPDATE, t_xmax = 0,          t_ctid = (0,2) -> Live tuple
```

### 7.2 Practical Example: Audit Shared Buffers Menggunakan `pg_buffercache`
Untuk menganalisis secara real-time data apa yang mendominasi Shared Memory di environment produksi:

```sql
CREATE EXTENSION IF NOT EXISTS pg_buffercache;

-- Query analisis pemanfaatan shared buffer per relasi dalam database
SELECT 
    c.relname,
    pg_size_pretty(count(*) * 8192) as buffered_size,
    round(100.0 * count(*) / ((SELECT setting FROM pg_settings WHERE name='shared_buffers')::integer), 2) AS buffer_utilization_pct,
    round(100.0 * count(*) * 8192 / NULLIF(pg_relation_size(c.oid), 0), 2) AS pct_of_relation_cached,
    count(*) FILTER (WHERE b.isdirty) AS dirty_pages_count
FROM pg_buffercache b
JOIN pg_class c ON b.relfilenode = pg_relation_filenode(c.oid)
JOIN pg_database d ON (b.reldatabase = d.oid AND d.datname = current_database())
GROUP BY c.oid, c.relname
ORDER BY count(*) DESC
LIMIT 10;
```

### 7.3 Practical Example: Bedah WAL Menggunakan `pg_waldump`
Jalankan di terminal Linux instance PostgreSQL untuk melihat deskripsi operasi I/O transaksi:
```bash
# Menemukan file WAL aktif terkini
WAL_FILE=$(psql -U postgres -Atc "SELECT pg_walfile_name(pg_current_wal_lsn());")
WAL_DIR="/var/lib/postgresql/data/pg_wal"

echo "Current active WAL segment: $WAL_FILE"

# Jalankan dump record secara terfilter (Hanya resource manager Heap dan Transaction)
pg_waldump ${WAL_DIR}/${WAL_FILE} -r Heap,Transaction -n 10
```

Output interpretasi:
```text
rmgr: Heap        len(rec):       79, tg: 0, desc: INSERT ... rel 1663/16384/24589 blk 0
rmgr: Transaction len(rec):       34, tg: 0, desc: COMMIT 2026-03-30 08:34:10.123 UTC
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario Insiden: Payment Gateway 50.000 TPS Mengalami P99 Latency Spikes
**Environment:**
- Node: Bare-metal Dual AMD EPYC 7763 (128 Cores, 256 Threads), 512 GB RAM, NVMe Array PCIe Gen4 RAID 10.
- PostgreSQL 15, Database size: 4 TB OLTP.
- Beban: 50.000 Write TPS saat Flash Sale.

**Gejala Masalah:**
Tiap interval 5 menit, P99 Latency melesat tajam dari 3ms menjadi 12.000ms (12 detik). Metrik sistem menunjukkan *iowait* melonjak hingga 80%, Backend Process masuk dalam antrian panjang dengan state wait event: `IO:BufFileWrite`, `IO:DataFileExtend`, dan `IPC:BufferContent`. Sejumlah connection poolers (PgBouncer) kehabisan koneksi karena antrian timeout.

**Investigasi Root-Cause:**
1. Ekstraksi log PostgreSQL menunjukkan insiden bertepatan persis dengan log:
   `LOG: checkpoint starting: time` dan `LOG: checkpoint complete: wrote 420102 buffers (6.4%) ...`.
2. Analisis parameter konfigurasi:
   - `max_wal_size = 16GB` (terlalu kecil untuk 50K TPS; WAL 16GB habis dalam waktu kurang dari 2 menit).
   - `checkpoint_completion_target = 0.5` (Checkpointer mengeksekusi flush dirty buffers secepat mungkin hanya dalam separuh siklus timeout, mengakibatkan lonjakan saturasi write I/O bandwidth).
   - `checkpoint_timeout = 5min`.
   - `shared_buffers = 256GB` (50% dari RAM fisik). Terlalu banyak dirty pages tertampung di RAM (hingga 40GB dirty page terkumpul sebelum flush dimulai).
   - Kernel Linux default `vm.dirty_background_ratio = 10` dan `vm.dirty_ratio = 20`. Di sistem RAM 512GB, 20% adalah 102,4GB dirty pages. Begitu ambang batas 20% tersentuh, kernel Linux **membekukan seluruh I/O write proses (proses PostgreSQL dipaksa wait secara synchronous)** untuk membersihkan buffer cache Linux ke disk NVMe (*flushing storm*).

**Langkah Remidiasi dan Resolusi:**
1. **Penyesuaian Kernel Linux `/etc/sysctl.conf`:**
   Mencegah kernel membiarkan dirty bytes menumpuk secara masif:
   ```ini
   # Ubah dari rasio persen ke absolut bytes
   vm.dirty_background_bytes = 268435456   # 256 MB (Kernel mulai background flusher lebih dini)
   vm.dirty_bytes = 1073741824              # 1 GB (Batas keras sebelum proses diblokir)
   ```
   Terapkan: `sysctl -p`.

2. **Remidiasi Engine `postgresql.conf`:**
   ```ini
   # Turunkan shared_buffers untuk memberi ruang agresif pada OS Page Cache
   shared_buffers = 128GB                  # 25% dari total 512GB RAM

   # Perlebar siklus checkpoint dan smoothing flush
   checkpoint_timeout = 30min              # Interval diperlebar agar akumulasi WAL efisien
   max_wal_size = 128GB                    # Mencegah checkpoint prematur akibat volume WAL
   min_wal_size = 32GB
   checkpoint_completion_target = 0.9      # Spread I/O tulis merata di 90% waktu interval (27 menit)
   
   # Aktifkan Background Writer proaktif agar Backend tidak mengurusi dirty pages
   bgwriter_delay = 10ms
   bgwriter_lru_maxpages = 800
   bgwriter_lru_multiplier = 3.0
   ```

**Hasil Pasca-Implementasi:**
P99 latency stabil di angka 4.2ms tanpa ada lonjakan berkala. Throughput I/O tersalurkan secara linier (flat continuous line 120MB/s) menggantikan pola osilasi gergaji (0 MB/s lalu spike ke 3.5 GB/s).

---

## 9. Trade-offs (Performance, Latency, Scalability, Cost)

| Parameter / Arsitektur | Opsi Konfigurasi | Keuntungan (Pros) | Biaya / Konsekuensi (Cons) | Rekomendasi Beban Kerja |
| :--- | :--- | :--- | :--- | :--- |
| **`synchronous_commit`** | `off` | Latensi commit turun drastis (mikrodetik). TPS naik hingga $5\times-10\times$. | Potensi kehilangan data transaksi terakhir (sepanjang $3\times$ `wal_writer_delay`, misal 30ms) jika OS crash mendadak. Integritas ACID tidak korup, hanya data terpotong (*no corruption, only data loss*). | Data audit log, telemetri IoT, metrics ingestion. DILARANG untuk transaksi ledger finansial. |
| **`shared_buffers`** | Ekstrem Besar (> 50% RAM) | Cache hit ratio query statis/baca tinggi di dalam proses database. | Mengakibatkan *Double Buffering Overhead*, waktu scan eviction buffer memanjang, checkpoint burst meningkat, latency stall saat scanning table besar. | Analitikal read-only tanpa transaksi write intensif. |
| **`shared_buffers`** | Konservatif (15%–25% RAM) | Kompatibilitas tinggi dengan OS page cache, read-ahead kernel bekerja optimal, checkpoint flush lebih cepat selesai. | Cache hit ratio di engine lebih rendah jika memory allocator kernel Linux terfragmentasi. | General OLTP enterprise dengan traffic write tinggi. |
| **`work_mem`** | Alokasi Agresif (misal 512MB+) | Sorting dan Hash Joins tereksekusi murni di RAM tanpa temp files pada disk storage. Query analitik menjadi sangat cepat. | Bahaya **Kernel OOM-Killer**: Jika 200 koneksi bersamaan menjalankan query dengan 3 hash joins, penggunaan RAM lokal melonjak hingga $200 \times 3 \times 512\text{MB} = 300\text{GB}$. Postmaster terbunuh paksa. | Data Warehouse dengan koneksi terbatas (`max_connections <= 30`). |
| **Full Page Writes (`full_page_writes`)** | `off` | Mengurangi volume data WAL secara dramatis hingga 40-70%. I/O storage lebih awet dan hemat. | Jika storage atau host OS mengalami *power outage* di tengah penulisan blok (torn-page write), **seluruh cluster database berisiko korup total dan tidak dapat direcover**. | HANYA untuk read-replica sementara atau restoring data master sekali pakai. |

---

## 10. Common Mistakes & Troubleshooting

### Kesalahan Fatal 1: Salah Menyetel `max_connections` Tanpa Connection Pooler
- **Masalah:** Mengubah parameter `max_connections = 5000` di PostgreSQL untuk melayani lonjakan aplikasi web microservices.
- **Dampak Arsitektur:** Terjadi thrashing context-switching CPU drastis, memori lokal meledak, serta lock contention brutal di kernel semaphore dan PostgreSQL `ProcArrayLock`.
- **Troubleshooting & Fix:**
  Gunakan **PgBouncer** atau **pgcat** di layer arsitektur depan. Terapkan prinsip:
  $$\text{Target Max Connections} = (\text{Core CPU Count} \times 2) + \text{Spindle/Drive Count}$$
  Batasi `max_connections` di PostgreSQL antara 100 - 300 koneksi, sisanya ditampung dalam pooler antrean.

### Kesalahan Fatal 2: Misalignment Alokasi Memori Linux (OOM Panic)
- **Masalah:** Kernel Linux default memiliki parameter overcommit memory: `vm.overcommit_memory = 0`. Backend processes PostgreSQL yang meminta alokasi `work_mem` virtual diizinkan overcommit oleh kernel hingga RAM habis. Kernel Linux OOM-Killer kemudian aktif dan membunuh proses backend yang paling rakus.
- **Dampak:** Matinya satu backend proses secara abnormal memicu Postmaster mendeteksi *shared memory corruption hazard*. Seluruh backend koneksi klien seketika diputus paksa (*server abort*), cluster masuk ke recovery mode (`FATAL: the database system is in recovery mode`).
- **Pencegahan:**
  ```ini
  # Setting pada /etc/sysctl.conf
  vm.overcommit_memory = 2
  vm.overcommit_ratio = 80
  ```
  Lindungi proses postmaster dari seleksi OOM-Killer pada systemd unit:
  ```ini
  # /etc/systemd/system/postgresql-15.service.d/override.conf
  [Service]
  OOMScoreAdjust=-1000
  ```

---

## 11. Best Practices (Production Checklist)

1. [ ] **Tuning Arsitektur Checkpoint:** Atur `checkpoint_completion_target = 0.9` dan `checkpoint_timeout = 15min` hingga `30min`.
2. [ ] **Kalkulasi Shared Buffers:** Alokasikan nilai default awal sebesar 25% dari total System RAM. Jangan melebihi 40% kecuali divalidasi oleh benchmark sintetis `pgbench`.
3. [ ] **Maintenance Work Mem:** Berikan alokasi besar pada `maintenance_work_mem` (misal 2GB–4GB) untuk mempercepat runtime `VACUUM` dan indexing periodik.
4. [ ] **Aktifkan Data Checksums:** Inisialisasi cluster selalu dengan `initdb -k` atau `--data-checksums` untuk memverifikasi proteksi kerusakan blok pada level disk controller.
5. [ ] **Manajemen Wal Size:** Setel `max_wal_size` minimal 32GB s/d 64GB pada instance transaksi OLTP padat agar checkpointer tidak dipaksa flush sebelum periodenya.
6. [ ] **Disable Huge Pages Fragmentation:** Setel `huge_pages = try` atau `on`. Alokasikan *Linux Transparent Huge Pages (THP)* ke status `madvise` atau `never` untuk menghindari memory compaction latency freeze.
7. [ ] **Pantau Wait Events:** Selalu gunakan view `pg_stat_activity` untuk mengidentifikasi query yang terhambat di subsistem spesifik (`wait_event_type = 'IO'`, `'Lock'`, atau `'LWLock'`).

---

## 12. Hands-on Practice

Buat skrip pengujian arsitektur storage dan memory di environment lokal: direktori kerja `hands-on/m02/`.

### Langkah 1: Setup Workspace & Inisialisasi Lingkungan
```bash
mkdir -p hands-on/m02
cd hands-on/m02
```

### Langkah 2: Buat Skrip Analisis Storage Page (`inspect_storage.sql`)
Simpan kode berikut sebagai `hands-on/m02/inspect_storage.sql`:

```sql
-- inspect_storage.sql
CREATE EXTENSION IF NOT EXISTS pageinspect;

DROP TABLE IF EXISTS storage_leak_test;
CREATE TABLE storage_leak_test (
    id serial PRIMARY KEY,
    payload text,
    counter int
);

-- Matikan autovacuum khusus tabel ini agar analisis deterministik
ALTER TABLE storage_leak_test SET (
    autovacuum_enabled = false
);

-- Insert 1000 baris data
INSERT INTO storage_leak_test (payload, counter)
SELECT repeat('X', 250), generate_series(1, 1000);

-- Tampilkan alokasi block dan line pointer awal
SELECT 
    pg_size_pretty(pg_relation_size('storage_leak_test')) as physical_table_size,
    pg_relation_size('storage_leak_test') / 8192 as block_count;

-- Lakukan Update massal 3 kali berturut-turut untuk menciptakan dead tuples
UPDATE storage_leak_test SET counter = counter + 1;
UPDATE storage_leak_test SET counter = counter + 1;
UPDATE storage_leak_test SET counter = counter + 1;

-- Tampilkan peningkatan ukuran fisik akibat implementasi MVCC Append-Only
SELECT 
    pg_size_pretty(pg_relation_size('storage_leak_test')) as bloated_table_size,
    pg_relation_size('storage_leak_test') / 8192 as bloated_block_count;

-- Inspeksi kondisi item pada blok ke-0 (Block 0)
SELECT 
    lp, 
    lp_off, 
    lp_flags, 
    lp_len,
    t_xmin, 
    t_xmax,
    t_ctid
FROM heap_page_items(get_raw_page('storage_leak_test', 0))
LIMIT 10;
```

### Langkah 3: Eksekusi dan Verifikasi
Jalankan skrip di atas menggunakan command psql:
```bash
psql -U postgres -d postgres -f inspect_storage.sql
```

Amati bahwa:
1. Ukuran fisik tabel bertambah hingga $\approx 4\times$ lipat meskipun jumlah data logis tetap 1000 baris.
2. Pada `heap_page_items`, Line Pointer lama memiliki flag `lp_flags = 1` dengan `t_xmax` yang telah terisi (dead tuple), dan `t_ctid` mengarah ke lokasi fisik tuple baru.

---

## 13. Exercise

### Level Easy
Tuliskan satu query SQL administrative terhadap view sistem `pg_stat_database` untuk menghitung rasio **Shared Buffers Cache Hit Ratio** dari database aktif saat ini.  
*Kriteria evaluasi:* Output harus berupa format persentase dua angka di belakang koma (misal: `99.45%`).

### Level Medium
Sebuah query batch report lambat saat memproses agregasi data besar:
```sql
SELECT customer_id, count(*), sum(amount) 
FROM transactions 
GROUP BY customer_id 
ORDER BY sum(amount) DESC;
```
Hasil `EXPLAIN ANALYZE` menunjukkan node:
`SortMethod: external merge Disk: 48512kB`.  
Jelaskan mengapa data tumpah ke disk, dan tuliskan konfigurasi SQL session-level yang tepat untuk memindahkan operasi sortasi tersebut sepenuhnya ke memori RAM tanpa mengubah parameter global server.

### Level Hard
Buat script Bash/SQL pipeline otomatis yang memanfaatkan utilitas `pageinspect` untuk memindai sebuah tabel dan menghitung secara presisi:
1. Persentase ruang kosong sebenarnya (*Free Space*).
2. Persentase ruang yang terbuang oleh *Dead Tuples*.
3. Persentase ruang yang ditempati oleh *Live Tuples*.  
Perhitungan harus dilakukan dari raw biner block tanpa menggunakan fungsi estimasi bawaan `pgstattuple`.

---

## 14. Challenge

### Studi Kasus: "The Phantom Checkpoint Storm & Replication Lag"
**Deskripsi Skenario:**  
Anda adalah Lead DBA pada platform financial broker internasional. Server Primary Anda menerima trafik penulisan derivatif masif ($>80.000$ baris per detik ke tabel partisi ledger). Anda memiliki dua Read Replicas (Physical Streaming Replication).

**Masalah Kritis Terjadi:**  
1. Setiap interval tertentu, metrik *Replication Lag* di slave melonjak secara eksponensial (dari 10ms menjadi 180 detik).
2. Analisis I/O primary menunjukkan lonjakan WAL write byte yang masif saat transaksi batch berjalan, memicu disk bottleneck di jaringan streaming replication.
3. Setelah diselidiki melalui `pg_waldump`, 70% dari volume WAL ternyata berisi record tipe: `rmgr: Btree, desc: SPLIT_R` dan `rmgr: Heap, desc: FPI (Full Page Image)`.
4. Tim infrastructure mengusulkan untuk menonaktifkan `full_page_writes = off` guna menghemat bandwidth jaringan replication.

**Tugas Anda:**
1. Tolak atau terima usulan penonaktifan `full_page_writes` dengan memberikan argumentasi teknis mendalam mengenai risiko kerusakan data disk (*partial page writes*) dan cara crash-recovery PostgreSQL bekerja menggunakan LSN.
2. Diagnosis mengapa *Full Page Image (FPI)* dihasilkan dalam jumlah sangat ekstrem pasca-checkpoint.
3. Rancang arsitektur tuning konfigurasi komprehensif (`postgresql.conf` dan level OS) untuk meminimalisasi pembentukan FPI di WAL stream secara permanen tanpa mengorbankan durabilitas ACID dan keselamatan kluster data.

---

## 15. Quiz Evaluasi Pemahaman

### 15.1 Pertanyaan Basic (Pilihan Ganda)
1. Apa fungsi dari parameter `pd_lsn` yang tersimpan pada 24-byte Page Header PostgreSQL?
   - A. Menghitung jumlah tuple yang terhapus di dalam block.
   - B. Mencatat Log Sequence Number (LSN) transaksi terakhir yang memodifikasi block tersebut untuk crash recovery.
   - C. Menyimpan checksum validasi enkripsi data transparent disk.
   - D. Menunjukkan pointer offset menuju baris data berikutnya di block lain.

2. Di manakah memori untuk eksekusi query `ORDER BY` dialokasikan?
   - A. `shared_buffers`
   - B. `wal_buffers`
   - C. Local Memory backend process (`work_mem`)
   - D. `maintenance_work_mem`

3. Apa unit ukuran default dari satu Page/Block data di PostgreSQL?
   - A. 4 KB
   - B. 8 KB
   - C. 16 KB
   - D. 64 KB

4. Algoritma apa yang digunakan oleh PostgreSQL Buffer Manager untuk mencari slot buffer yang dapat dievつい (*victim buffer*)?
   - A. Least Recently Used (LRU)
   - B. First-In, First-Out (FIFO)
   - C. Clock Sweep
   - D. Most Frequently Used (MFU)

5. Apa efek dari mengeksekusi operasi `UPDATE` pada PostgreSQL terhadap layout penyimpanan fisik?
   - A. Baris di-update secara *in-place* di disk seketika tanpa mengubah file pointer.
   - B. Tuple lama ditandai mati (`t_xmax` diisi), dan baris baru di-insert sebagai tuple baru (`t_xmin` baru).
   - C. Transaksi langsung memicu auto-vacuum untuk membebaskan ruang disk lama.
   - D. Data lama dipindahkan ke file Undo Tablespace terpisah.

---

### 15.2 Pertanyaan Intermediate (Analisis Singkat)
1. Mengapa alokasi parameter `shared_buffers` yang disetel sebesar 90% dari total RAM fisik server sering kali memperburuk latensi query PostgreSQL dibandingkan alokasi 25%–30%?
2. Jelaskan perbedaan mendasar peran arsitektural antara proses **Checkpointer** dan proses **Background Writer (BgWriter)**.
3. Apa tujuan fungsional dari *Line Pointer (ItemId)*? Mengapa index tidak langsung menunjuk pada byte offset fisik tuple di dalam page?
4. Kapan proses backend PostgreSQL dipaksa menulis WAL record secara sinkron (*synchronous disk flush*)?
5. Jelaskan fenomena *HOT (Heap-Only Tuple)* update dan dua syarat wajib agar optimasi HOT dapat dieksekusi oleh storage engine!

---

### 15.3 Skenario Kasus Produksi
1. **Skenario Disk Exhaustion:**  
   Monitoring database Anda mengirimkan alert bahwa disk mount point `$PGDATA` tersisa 1% kapasitas akibat lonjakan volume WAL di direktori `pg_wal`. File WAL tidak dihapus oleh engine meskipun parameter `archive_command` telah disetel. Bagaimana Anda mendiagnosis penyebab macetnya pembersihan WAL segment ini, dan langkah mitigasi darurat apa yang harus diambil tanpa merusak kluster?
2. **Skenario Latency Lock Spikes:**  
   Dashboard grafana menunjukkan metrik wait event `LWLock:BufferContent` melonjak drastis pada aplikasi checkout e-commerce. Semua koneksi tertahan di event ini. Bagaimana cara Anda melacak block tabel/index mana yang memicu pertikaian (*hot buffer contention*) tersebut?
3. **Skenario Torn-Page Recovery Crash:**  
   Sebuah host mengalami kernel panic mendadak akibat *power failure*. Saat booting ulang, PostgreSQL gagal start dan log memunculkan error: `PANIC: invalid page in block 40294 of relation base/16384/18921`. Jelaskan mekanisme apa yang seharusnya mencegah insiden ini di layer konfigurasi PostgreSQL, dan mengapa hal tersebut bisa gagal!

---

## 16. Summary

1. **Process Isolation Model:** PostgreSQL menggunakan proses worker mandiri (*Backend Process*) per koneksi klien yang berkomunikasi lewat segmen memori terpusat (*Shared Memory*), memastikan kegagalan memori lokal satu koneksi tidak merusak koneksi lain, namun memerlukan koordinasi connection pooler eksternal untuk skalabilitas masif.
2. **Double Buffering:** Eksistensi bersama antara `shared_buffers` dan *Linux Kernel Page Cache* menuntut pemahaman arsitektur terpadu; konfigurasi parameter database tidak boleh berdiri sendiri tanpa tuning parameter dirty pages pada kernel host OS (`vm.dirty_*`).
3. **Page Anatomy & Append-Only Engine:** Setiap 8KB page diatur secara presisi dari dua arah (`pd_lower` tumbuh ke bawah, `pd_upper` tumbuh ke atas). Sifat dasar MVCC yang memutasi baris secara append-only melahirkan dead tuples yang membutuhkan autovacuum agresif guna menahan degradasi performa I/O.
4. **Durabilitas WAL & Checkpoint Pacing:** Durabilitas PostgreSQL ditopang oleh aturan fundamental *Write-Ahead Logging*—data tidak boleh menyentuh data file disk sebelum record deskripsi transaksinya ter-flush di WAL log. Smoothing flushing dirty pages via checkpoint spread (`checkpoint_completion_target = 0.9`) adalah kunci utama kestabilan performa write enterprise.