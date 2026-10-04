# BAB 06: Transaction Management & Concurrency Control
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis Internal Multi-Version Concurrency Control (MVCC)** pada tingkat biner, mencakup struktur `HeapTupleHeaderData`, bit `t_infomask`, dan mekanisme pemetaan status transaksi di dalam `pg_xact` (CLOG).
- **Mendemonstrasikan Rekayasa Snapshot**: Menguraikan algoritma kalkulasi visibilitas tuple (`SnapshotData`) dan memprediksi visibilitas baris data pada level isolasi *Read Committed*, *Repeatable Read*, dan *Serializable Snapshot Isolation (SSI)*.
- **Menguasai Arsitektur Lock Manager**: Mendiagnosis hierarki *Heavyweight Locks*, *Lightweight Locks (LWLocks)*, dan *Spinlocks*, serta menavigasi struktur memori *Fast Path Locking* dan tabel hash lock utama.
- **Mengimplementasikan Pola Konkurensi Tingkat Lanjut**: Membangun mekanisme antrean performa tinggi tanpa blokade menggunakan `SELECT ... FOR UPDATE SKIP LOCKED` dan sinkronisasi terdistribusi berbasis *PostgreSQL Advisory Locks*.
- **Memitigasi Insiden Konkurensi Skala Enterprise**: Mendiagnosis dan menyelesaikan *lock contention*, *deadlock cascade*, degradasi akibat *subtransaction cache overflow*, serta penanganan *two-phase commit (2PC) orphan transactions*.
- **Merancang Strategi Migrasi Skema Zero-Downtime**: Menghindari *lock starvation* dan antrean blokade global pada operasi DDL di sistem OLTP 24/7.

---

### 2. Prerequisites

Sebelum mempelajari modul ini, peserta diwajibkan telah menguasai:
- **Arsitektur Dasar PostgreSQL**: Struktur shared memory (`shared_buffers`), proses latar belakang (*background workers*, *checkpointer*, *writer*, *walwriter*), dan Write-Ahead Logging (WAL).
- **Fundamental SQL & Transaksi**: Sintaks dasar SQL, konsep ACID (*Atomicity, Consistency, Isolation, Durability*), dan pemahaman isolasi data standar ANSI/ISO SQL.
- **Dasar Sistem Operasi & Memori**: Konsep *paging*, *virtual memory*, *inter-process communication (IPC)*, serta primitif sinkronisasi kernel (*mutexes*, *semaphores*).
- **Modul Prasyarat**: *BAB-06 Modul 01: Fondasi Transaksi dan Transaksi Terdistribusi Sederhana*.

---

### 3. Concept & Internal Architecture

#### 3.1 Struktur Fisik Heap Tuple dan Infomask

Setiap baris data (*tuple*) di dalam PostgreSQL disimpan pada blok data (*heap page*) berukuran default 8 KB. Tuple tidak diperbarui langsung di tempat (*in-place update*), melainkan disalin sebagai versi baru untuk mengakomodasi MVCC.

Header dari setiap tuple didefinisikan dalam struktur internal C `HeapTupleHeaderData`:

```c
struct HeapTupleHeaderData {
    union {
        HeapTupleFields t_heap;
        DatumTupleFields t_datum;
    } t_choice;

    ItemPointerData t_ctid;           /* Offset fisik tuple ini atau versi terbarunya */

    uint16          t_infomask2;      /* Atribut count dan flag HStore/HOT */
    uint16          t_infomask;       /* Flag visibilitas status transaksi */
    uint8           t_hoff;           /* Offset ke user data (NULL bitmap dsb) */
    /* NULL bitmap dan User Data berada setelah header ini */
};
```

Komponen kunci penentu visibilitas pada `t_heap` meliputi:
- `t_xmin` (32-bit): Transaction ID (XID) yang menyisipkan (*INSERT*) tuple ini ke dalam tabel.
- `t_xmax` (32-bit): Transaction ID yang memperbarui (*UPDATE*) atau menghapus (*DELETE*) tuple ini. Jika tuple belum dimodifikasi, nilai ini adalah `0`.
- `t_cid` (*Command Identifier*): Urutan perintah SQL dalam transaksi yang sama yang memodifikasi tuple tersebut.
- `t_ctid`: Pointer fisik `(block_number, tuple_offset)`. Jika tuple telah di-*update*, `t_ctid` tuple lama akan menunjuk ke lokasi fisik tuple baru.

Field `t_infomask` menyimpan status pemrosesan transaksi secara *bitmap* tanpa harus selalu membaca disk atau memori `pg_xact`:
- `HEAP_XMIN_COMMITTED` (`0x0100`): Transaksi `xmin` telah di-*commit*.
- `HEAP_XMIN_INVALID` (`0x0200`): Transaksi `xmin` telah dibatalkan (*aborted*); tuple tidak valid.
- `HEAP_XMAX_COMMITTED` (`0x0400`): Transaksi `xmax` telah di-*commit*.
- `HEAP_XMAX_INVALID` (`0x0800`): Transaksi `xmax` dibatalkan atau belum ada; tuple masih aktif/terbaru.
- `HEAP_XMAX_IS_EXCL_LOCK` (`0x0040`): `xmax` merepresentasikan *exclusive row lock*, bukan operasi penghapusan data.
- `HEAP_XMAX_IS_KEYSHR_LOCK` (`0x0010`): `xmax` merepresentasikan *key-shared row lock*.

#### 3.2 Commit Log (`pg_xact`) dan Hint Bits

PostgreSQL menyimpan status global dari setiap XID di dalam direktori `$PGDATA/pg_xact`. Setiap transaksi direpresentasikan oleh 2 bit data:
1. `00`: `TRANSACTION_STATUS_IN_PROGRESS`
2. `01`: `TRANSACTION_STATUS_COMMITTED`
3. `10`: `TRANSACTION_STATUS_ABORTED`
4. `11`: `TRANSACTION_STATUS_SUB_COMMITTED`

Untuk menghindari bottleneck pembacaan berulang ke `pg_xact` pada Shared Memory saat memeriksa visibilitas (*visibility checks*), PostgreSQL menerapkan mekanisme **Hint Bits**:
1. Transaksi membaca tuple untuk pertama kali. Bit `HEAP_XMIN_COMMITTED` pada `t_infomask` belum diset.
2. Proses menelusuri `pg_xact` untuk memeriksa status `xmin`.
3. Jika `xmin` terkonfirmasi *committed*, proses memodifikasi *buffer page* tuple tersebut dan menyalakan flag `HEAP_XMIN_COMMITTED` langsung pada header tuple.
4. Operasi pembacaan berikutnya langsung mengevaluasi bit `t_infomask` tanpa menyentuh struktur memori `pg_xact`.

> **Catatan Arsitektural**: Penulisan *hint bits* mengubah bit pada heap page. Hal ini menyebabkan page menjadi *dirty* dan memaksa background writer atau checkpointer menulis page tersebut ke disk, memicu I/O bahkan pada query `SELECT` murni jika page tersebut dibaca untuk pertama kali setelah transaksi commit.

#### 3.3 Anatomi Snapshot Mesin Database

Snapshot visibilitas menentukan data mana yang berhak dilihat oleh sebuah transaksi. Representasi internal snapshot didefinisikan dalam struktur C `SnapshotData`:

```c
typedef struct SnapshotData {
    SnapshotType snapshot_type;
    TransactionId xmin;           /* XID terendah yang masih berjalan saat snapshot dibuat */
    TransactionId xmax;           /* XID pertama yang belum dialokasikan saat snapshot dibuat */
    TransactionId *xip;           /* Array dari semua active uncommitted XID di antara xmin dan xmax */
    uint32        xcnt;          /* Jumlah XID aktif dalam array xip */
    TransactionId *subxip;        /* Array active subtransactions */
    int32         subxcnt;       /* Jumlah subtransactions */
    /* ... metadata tambahan untuk serialization and sync */
} SnapshotData;
```

**Logika Algoritma Visibilitas Tuple:**
Untuk tuple tertentu yang sedang dievaluasi oleh Snapshot $S$:
1. Jika `t_xmin` terdaftar sebagai `ABORTED` $\rightarrow$ **Tidak Terlihat**.
2. Jika `t_xmin > S.xmax` $\rightarrow$ **Tidak Terlihat** (dibuat di masa depan relatif terhadap snapshot).
3. Jika `t_xmin < S.xmin` dan statusnya `COMMITTED` $\rightarrow$ **Terlihat**, kecuali `t_xmax` valid dan memenuhi kondisi pembatalan.
4. Jika `S.xmin <= t_xmin < S.xmax`:
   - Jika `t_xmin` berada di dalam array `S.xip` $\rightarrow$ **Tidak Terlihat** (transaksi masih aktif saat snapshot diambil).
   - Jika `t_xmin` tidak ada di dalam `S.xip` dan statusnya `COMMITTED` $\rightarrow$ **Terlihat**.
5. Jika tuple terlihat berdasarkan aturan `xmin`, evaluasi `t_xmax`:
   - Jika `t_xmax` kosong atau `ABORTED` $\rightarrow$ **Terlihat**.
   - Jika `t_xmax > S.xmax` atau `t_xmax` ada di `S.xip` $\rightarrow$ **Terlihat** (penghapusan belum terjadi menurut snapshot).
   - Jika `t_xmax < S.xmax` dan statusnya `COMMITTED` dan tidak ada di `S.xip` $\rightarrow$ **Tidak Terlihat** (tuple sudah terhapus sebelum snapshot dibuat).

#### 3.4 Mekanisme Isolasi Transaksi

```
ANSI Isolation Level   | Dirty Read | Non-Repeatable Read | Phantom Read | Serialization Anomaly
-----------------------+------------+---------------------+--------------+----------------------
Read Committed         | Not Poss.  | Possible            | Possible     | Possible
Repeatable Read        | Not Poss.  | Not Possible        | Not Poss.*   | Possible
Serializable           | Not Poss.  | Not Possible        | Not Poss.    | Not Possible
```
*\*PostgreSQL mencegah Phantom Read pada level Repeatable Read menggunakan snapshot MVCC yang konsisten sepanjang transaksi.*

- **Read Committed**: Setiap statement di dalam transaksi mendapatkan snapshot baru yang diambil pada saat statement tersebut mulai dieksekusi.
- **Repeatable Read**: Snapshot tunggal diambil pada saat statement interaktif pertama yang bukan DDL/transaksi dijalankan, dan snapshot yang sama dipertahankan hingga transaksi berakhir.
- **Serializable (SSI)**: Menggunakan teknik *Serializable Snapshot Isolation*. Snapshot bekerja mirip dengan Repeatable Read, namun menambahkan pelacakan *rw-antidependencies* (kondisi di mana sebuah transaksi membaca versi data yang ditimpa oleh transaksi lain) menggunakan struktur memori `SIREAD` lock. Jika terdeteksi siklus dependensi (misal $T_1 \rightarrow T_2 \rightarrow T_1$), engine membatalkan salah satu transaksi dengan melempar error `40001 (serialization_failure)`.

#### 3.5 Arsitektur Lock Manager

PostgreSQL mengimplementasikan sistem penguncian berlapis:
1. **Spinlocks**: Primitif penguncian tingkat CPU berbasis instruksi atomic *test-and-set*. Durasi penahanan sangat singkat (beberapa siklus clock).
2. **LWLocks (Lightweight Locks)**: Mengatur akses konkurensi ke struktur shared memory bersama (misal: penulisan ke buffer pool, alokasi XID di `ProcArray`).
3. **Heavyweight Locks (Regular Locks)**: Penguncian tingkat SQL yang mengatur objek database (tabel, tuple, halaman, advisory lock). Dikelola oleh modul *Lock Manager*.

##### Tabel Matriks Konflik Heavyweight Lock
Baris = Lock yang sudah dipegang; Kolom = Lock yang diminta.
(X = Konflik/Blokade, . = Diizinkan berjalan bersamaan)

| Mode yang Diminta $\rightarrow$<br>Mode yang Aktif $\downarrow$ | Access Share | Row Share | Row Exclusive | Share Update Exclusive | Share | Share Row Exclusive | Exclusive | Access Exclusive |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Access Share** | . | . | . | . | . | . | . | **X** |
| **Row Share** | . | . | . | . | . | . | **X** | **X** |
| **Row Exclusive** | . | . | . | . | **X** | **X** | **X** | **X** |
| **Share Update Exclusive**| . | . | . | **X** | **X** | **X** | **X** | **