# PostgreSQL Memory Hierarchy (Shared Buffers, work_mem) & 8KB Disk Storage Page Layout

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, Anda mampu:

1. **Menjelaskan** hierarki memori PostgreSQL secara lengkap — dari shared memory hingga local memory per-proses — beserta peran masing-masing komponen dalam siklus baca/tulis data.
2. **Mengkonfigurasi** parameter `shared_buffers`, `work_mem`, `maintenance_work_mem`, `effective_cache_size`, dan `wal_buffers` secara tepat berdasarkan karakteristik workload (OLTP vs OLAP).
3. **Membedah** struktur fisik halaman disk 8KB PostgreSQL — header, item pointers, tuple data, free space — dan memahami bagaimana data disimpan, diakses, dan dimodifikasi di level byte.
4. **Mendiagnosis** masalah performa produksi seperti buffer cache miss tinggi, OOM akibat `work_mem` terlalu besar, dan bloat halaman menggunakan query sistem (`pg_buffercache`, `pg_freespace`, `pageinspect`).
5. **Membangun** keputusan arsitektur yang tepat: kapan menaikkan `shared_buffers`, kapan menggunakan `work_mem` per-session, dan bagaimana layout halaman memengaruhi strategi indexing.

---

## 2. Prerequisite

Sebelum melanjutkan, pastikan Anda telah memahami:

| Konsep | Tingkat Pemahaman yang Dibutuhkan |
|---|---|
| Arsitektur proses PostgreSQL (postmaster, backend, bgwriter) | Mengerti peran masing-masing proses |
| Konsep dasar OS: virtual memory, page cache, file system | Memahami perbedaan RAM vs disk |
| SQL dasar: SELECT, INSERT, UPDATE, DELETE | Dapat menjalankan query sederhana |
| Konsep MVCC (Multi-Version Concurrency Control) | Memahami bahwa setiap baris memiliki versi |
| Dasar-dasar sistem file Linux (inode, block size) | Mengerti konsep blok penyimpanan |
| Instalasi PostgreSQL dan akses psql | Dapat terhubung ke database |

---

## 3. Concept

### Gambaran Besar: Mengapa Memori dan Storage Saling Terkait?

PostgreSQL adalah database yang dirancang dengan filosofi **"data harus melewati memori sebelum diproses"**. Tidak ada operasi yang bekerja langsung pada file disk — setiap baca dan tulis harus melalui lapisan memori yang terstruktur. Pemahaman tentang hierarki memori dan format penyimpanan disk adalah fondasi untuk memahami **mengapa query tertentu lambat**, **mengapa database menggunakan banyak RAM**, dan **bagaimana PostgreSQL menjamin konsistensi data**.

### Dua Dunia yang Saling Terhubung

**Dunia Memori** dan **Dunia Disk** di PostgreSQL berbicara dalam bahasa yang sama: **halaman (page) berukuran 8KB**. Sebuah halaman di disk memiliki format identik dengan sebuah buffer di memori. Ketika PostgreSQL membaca data, ia mengangkat halaman 8KB dari disk ke dalam slot buffer 8KB di shared memory. Ketika menulis, ia menyalin buffer 8KB kembali ke posisi yang tepat di file disk. Konsistensi format ini adalah kunci elegansnya.

### Lapisan-Lapisan Memori PostgreSQL

PostgreSQL mengelola memori dalam dua kategori utama:

**1. Shared Memory (Memori Bersama)**
Dialokasikan satu kali saat PostgreSQL startup dan diakses bersama oleh semua proses backend. Komponen utamanya:
- **Shared Buffer Pool**: Cache halaman data utama
- **WAL Buffers**: Buffer untuk Write-Ahead Log sebelum ditulis ke disk
- **Lock Table**: Tabel manajemen kunci
- **Shared Catalog Cache**: Cache untuk metadata sistem

**2. Local Memory (Memori Per-Proses)**
Setiap proses backend mengalokasikan memorinya sendiri, tidak dibagi dengan proses lain:
- **work_mem**: Untuk operasi sorting dan hashing
- **maintenance_work_mem**: Untuk VACUUM, CREATE INDEX, ALTER TABLE
- **temp_buffers**: Buffer untuk tabel temporary

### Format Halaman 8KB: Bahasa Universal PostgreSQL

Setiap file data PostgreSQL (disebut **relation**) terdiri dari halaman-halaman berukuran 8192 byte (8KB). Ukuran ini dikompilasi ke dalam PostgreSQL dan tidak dapat diubah tanpa recompile (meskipun ada varian dengan `--with-blocksize`). Setiap halaman mengandung:

- **Header** (24 byte): Metadata halaman — LSN terakhir, checksum, flag
- **Item Pointer Array**: Array offset yang menunjuk ke lokasi tuple dalam halaman
- **Free Space**: Ruang kosong di tengah halaman
- **Tuple Data**: Data aktual baris, tumbuh dari bawah ke atas
- **Special Space**: Data khusus untuk index (B-tree, GiST, dll.)

---

## 4. Why?

### Masalah yang Dipecahkan

#### Masalah 1: Disk I/O adalah Bottleneck Terbesar

Kecepatan akses disk (bahkan SSD NVMe) masih 100–1000x lebih lambat dari RAM. Tanpa lapisan caching memori, setiap query SELECT sederhana akan memerlukan operasi disk I/O yang mahal. `shared_buffers` memecahkan ini dengan menyimpan halaman yang sering diakses di RAM.

```
Latensi Akses (perbandingan kasar):
- L1 Cache CPU     : ~1 ns
- RAM              : ~100 ns
- SSD NVMe         : ~100,000 ns (100 µs)
- HDD              : ~10,000,000 ns (10 ms)

Rasio RAM vs SSD   : 1,000x lebih cepat
Rasio RAM vs HDD   : 100,000x lebih cepat
```

#### Masalah 2: Operasi Sort/Hash Membutuhkan Ruang Kerja Terisolasi

Ketika PostgreSQL menjalankan `ORDER BY`, `GROUP BY`, atau `HASH JOIN`, ia membutuhkan ruang kerja sementara. Jika ruang ini terlalu kecil, PostgreSQL terpaksa menggunakan disk (temporary files) yang ribuan kali lebih lambat. `work_mem` menyediakan ruang kerja ini di RAM.

#### Masalah 3: Konsistensi Data Saat Crash

Tanpa format halaman yang terdefinisi dengan baik, crash di tengah penulisan bisa menghasilkan data yang korup. Format halaman 8KB dengan LSN (Log Sequence Number) dan checksum memungkinkan PostgreSQL mendeteksi dan memulihkan halaman yang rusak menggunakan WAL.

#### Masalah 4: MVCC Membutuhkan Metadata Per-Tuple

PostgreSQL mengimplementasikan MVCC dengan menyimpan metadata visibilitas (xmin, xmax, cmin, cmax) langsung di dalam setiap tuple dalam halaman. Format halaman yang fixed dan terdokumentasi memungkinkan mekanisme ini bekerja secara efisien.

---

## 5. What?

### Definisi Teknis Presisi

#### Shared Buffers

**Definisi**: Area memori bersama yang berfungsi sebagai **buffer pool** — cache antara disk storage dan proses-proses backend PostgreSQL. Diimplementasikan sebagai array dari `NBuffers` slot, masing-masing berukuran `BLCKSZ` (default 8192 byte).

**Spesifikasi Teknis**:
- Tipe: Shared memory (POSIX `shmget` atau `mmap`)
- Ukuran default: 128MB (sangat konservatif, harus disesuaikan)
- Parameter: `shared_buffers` di `postgresql.conf`
- Unit: Dapat dinyatakan dalam kB, MB, GB (e.g., `shared_buffers = 4GB`)
- Efektif: Memerlukan restart PostgreSQL untuk mengubah nilai
- Algoritma eviction: **Clock Sweep** (variasi dari LRU)

**Struktur Internal Buffer Descriptor**:
```c
/* Dari src/include/storage/buf_internals.h */
typedef struct BufferDesc {
    BufferTag   tag;           /* ID halaman: relfilenode, fork, blocknum */
    int         buf_id;        /* nomor buffer (0..NBuffers-1) */
    pg_atomic_uint32 state;    /* flag: dirty, valid, pinned */
    int         wait_backend_pgprocno;
    int         freeNext;      /* link untuk free list */
    LWLock      content_lock;  /* lock untuk isi buffer */
} BufferDesc;
```

#### work_mem

**Definisi**: Memori yang dialokasikan **per-operasi** (bukan per-query, bukan per-koneksi) untuk operasi yang membutuhkan ruang kerja sementara seperti sort, hash join, dan hash aggregation.

**Spesifikasi Teknis**:
- Tipe: Local memory (heap proses backend)
- Ukuran default: 4MB
- Parameter: `work_mem` di `postgresql.conf` atau `SET work_mem = '64MB'`
- Scope: Dapat diset per-session atau per-transaction
- **Penting**: Satu query kompleks bisa menggunakan `work_mem` **berkali-kali** (satu per node sort/hash dalam query plan)
- Tidak memerlukan restart untuk mengubah nilai

#### Halaman 8KB (Block)

**Definisi**: Unit penyimpanan fundamental PostgreSQL. Setiap file data dibagi menjadi blok-blok berukuran `BLCKSZ` byte (default 8192). Setiap blok memiliki nomor urut yang disebut **block number** (dimulai dari 0).

**Spesifikasi Header Halaman** (`PageHeaderData`):
```c
/* Dari src/include/storage/bufpage.h */
typedef struct PageHeaderData {
    PageXLogRecPtr pd_lsn;      /* LSN: 8 byte - posisi WAL terakhir yang memodifikasi halaman */
    uint16         pd_checksum; /* 2 byte - checksum halaman */
    uint16         pd_flags;    /* 2 byte - flag: PD_HAS_FREE_LINES, PD_PAGE_FULL, dll */
    LocationIndex  pd_lower;    /* 2 byte - offset akhir item pointer array */
    LocationIndex  pd_upper;    /* 2 byte - offset awal area tuple */
    LocationIndex  pd_special;  /* 2 byte - offset awal special space */
    uint16         pd_pagesize_version; /* 2 byte - ukuran halaman & versi */
    TransactionId  pd_prune_xid; /* 4 byte - XID pruning terbaru */
    ItemIdData     pd_linp[1];  /* item pointer array (variabel) */
} PageHeaderData;
/* Total header: 24 byte */
```

**Spesifikasi Item Pointer** (`ItemIdData`):
```c
typedef struct ItemIdData {
    unsigned    lp_off:15,  /* offset tuple dari awal halaman */
                lp_flags:2, /* status: LP_UNUSED, LP_NORMAL, LP_REDIRECT, LP_DEAD */
                lp_len:15;  /* panjang tuple dalam byte */
} ItemIdData;
/* Ukuran: 4 byte per item pointer */
```

**Spesifikasi Tuple Header** (`HeapTupleHeaderData`):
```c
/* Dari src/include/access/htup_details.h */
typedef struct HeapTupleHeaderData {
    union {
        HeapTupleFields t_heap;   /* normal tuple */
        DatumTupleFields t_datum; /* minimal tuple */
    } t_choice;
    /* t_heap berisi: */
    /* TransactionId t_xmin - XID yang menginsert tuple ini */
    /* TransactionId t_xmax - XID yang mendelete/update tuple ini */
    /* CommandId t_cid      - command ID dalam transaksi */
    
    ItemPointerData t_ctid;       /* 6 byte - TID tuple ini (atau versi terbaru) */
    uint16          t_infomask2;  /* 2 byte - jumlah atribut, flag HOT */
    uint16          t_infomask;   /* 2 byte - flag: NULL bitmap, TOAST, dll */
    uint8           t_hoff;       /* 1 byte - offset ke data user (setelah header+null bitmap) */
    /* bits8 t_bits[] - null bitmap (opsional) */
    /* data user mulai di t_hoff */
} HeapTupleHeaderData;
/* Ukuran minimal: 23 byte */
```

---

## 6. How?

### Mekanisme Kerja: Siklus Baca Data (Read Path)

```
Step 1: Backend menerima query SELECT
Step 2: Executor meminta halaman dari Buffer Manager
Step 3: Buffer Manager mengecek shared buffer pool
   ├── HIT: Halaman ditemukan di buffer → kembalikan pointer buffer
   └── MISS: Halaman tidak ada di buffer
         Step 4: Buffer Manager mencari slot kosong (Clock Sweep)
         Step 5: Jika slot kotor (dirty), tulis ke disk (bgwriter/backend)
         Step 6: Baca halaman dari disk ke slot buffer kosong
         Step 7: Kembalikan pointer buffer ke executor
Step 8: Executor membaca tuple dari buffer
Step 9: Untuk setiap tuple, cek visibilitas MVCC (xmin, xmax)
Step 10: Kembalikan tuple yang visible ke klien
```

### Mekanisme Kerja: Siklus Tulis Data (Write Path)

```
Step 1: Backend menerima query INSERT/UPDATE/DELETE
Step 2: Buffer Manager memuat halaman target ke buffer (sama seperti read path)
Step 3: Backend meminta exclusive lock pada buffer
Step 4: WAL record ditulis ke WAL buffer TERLEBIH DAHULU (Write-Ahead!)
Step 5: Modifikasi dilakukan pada buffer di memori (halaman ditandai DIRTY)
Step 6: Lock dilepas
Step 7: Commit: WAL buffer di-flush ke disk WAL (fsync)
Step 8: Buffer dirty tetap di memori (belum ditulis ke data file)
Step 9: bgwriter/checkpointer secara asinkron menulis dirty buffer ke disk
```

### Mekanisme Clock Sweep (Buffer Eviction)

Clock Sweep adalah algoritma sederhana namun efektif yang digunakan PostgreSQL untuk memilih buffer yang akan diusir ketika shared buffer pool penuh:

```
Bayangkan buffer pool sebagai lingkaran jam:

[B0] → [B1] → [B2] → [B3] → ... → [BN] → kembali ke [B0]
        ↑
     "jarum jam"

Setiap
