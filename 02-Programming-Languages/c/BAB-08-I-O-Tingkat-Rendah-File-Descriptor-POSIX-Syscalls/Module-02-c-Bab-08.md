# BAB 08: I/O Tingkat Rendah, File Descriptor & POSIX Syscalls
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis dan Memanipulasi VFS Abstraction Layer**: Memahami siklus hidup data dari *user-space buffer*, *glibc wrapper*, *kernel system call table*, VFS (*Virtual File System*), hingga *Page Cache* dan *Block Device Driver*.
2. **Menguasai I/O Tingkat Lanjut**: Mengimplementasikan *Vectored I/O* (`readv`, `writev`), *Zero-Copy primitives* (`sendfile`, `splice`, `vmsplice`), dan *Memory-Mapped I/O* (`mmap`, `msync`, `madvise`).
3. **Mengendalikan Flag Kernel & Kontrol Konkurensi**: Mengontrol semantik berkas menggunakan `fcntl(2)` untuk *non-blocking state* (`O_NONBLOCK`), *direct I/O* (`O_DIRECT`), *append-only consistency* (`O_APPEND`), serta POSIX *advisory record locking* (`F_SETLK`, `F_SETLKW`).
4. **Membangun Subsistem I/O Skala Enterprise**: Merancang *storage-engine I/O layer* berperforma tinggi dengan *deterministic latency*, *zero-copy ring buffering*, serta *crash-recovery atomic update* berbasis `fsync`/`fdatasync`.

---

### 2. Prerequisite
Sebelum mendalami modul ini, peserta wajib menguasai:
* Pemrograman C Dasar hingga Menengah (Memory Layout, Pointer Arithmetic, Struct Alignment/Padding, Bitwise Operations).
* Konsep Dasar OS: Process Control Block (PCB), Virtual Memory (Page, Page Table, TLB, Page Fault), Interrupts & Context Switching.
* Dasar I/O POSIX: `open(2)`, `close(2)`, `read(2)`, `write(2)`, `lseek(2)`, errno handling.
* Tooling & Debugging: GCC/Clang tooling flag (`-Wall -Wextra -pedantic -O2`), GDB, `strace`, dan POSIX Signal (`SIGIO`, `SIGBUS`, `SIGPIPE`).

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1 Kernel Data Structures: File Descriptor Table vs Open File Table vs Vnode/Inode
Ketika sebuah proses memanggil `open(2)`, Kernel Linux tidak langsung memetakan nilai integer File Descriptor (FD) ke storage block fisik. Terdapat tiga lapis struktur data terpisah di kernel:

1. **Per-Process File Descriptor Table (`task_struct->files`)**:
   Berada di memori proses (kernel space per process). Mengandung array pointer bertipe `struct file *`. Integer FD (misal `3`) hanyalah sebuah indeks offset ke array `fd_array[]` ini. Flag yang tersimpan di sini hanyalah atribut level descriptor seperti `FD_CLOEXEC`.
2. **System-Wide Open File Table (`struct file`)**:
   Setiap entri merepresentasikan *open file description* aktif di seluruh sistem. Struktur ini memegang:
   * Current file offset (`f_pos`).
   * File status flags (`f_flags`: `O_RDONLY`, `O_NONBLOCK`, `O_SYNC`, `O_DIRECT`).
   * Access mode (`f_mode`).
   * Reference count (`f_count`).
   * Pointer ke entri VFS Inode (`f_inode`) dan Operasi File (`f_op`).
3. **VFS Inode Table & Inode Fisik (`struct inode`)**:
   Representasi abstrak dari entitas fisik pada disk. Menyimpan metadata: kepemilikan UID/GID, permission mode, ukuran berkas riil, timestamp, blok pointer disk, dan pointer ke *Address Space* (`struct address_space`) yang mengelola Page Cache.

```
+-------------------------------------------------------------------------------+
| Process A (PID 1001)                                                          |
| task_struct -> files_struct                                                  |
|   fd[0] -> stdin                                                              |
|   fd[1] -> stdout                                                             |
|   fd[3] ---------------\                                                      |
+------------------------|------------------------------------------------------+
                         |
+------------------------|------------------------------------------------------+
| Process B (PID 1002)   |                                                      |
|   fd[3] ---------------+                                                      |
|   fd[4] -------------\ |                                                      |
+----------------------|-|------------------------------------------------------+
                       | |
                       v v  (System-Wide Open File Table)
            +-------------------------+
            | struct file #1          |
            | - f_pos: 4096           |
            | - f_flags: O_RDWR       |
            | - f_count: 2            |
            | - f_inode --------------|---------\
            +-------------------------+         |
            +-------------------------+         |
            | struct file #2          |         |
            | - f_pos: 0              |         |
            | - f_flags: O_RDONLY     |         |
            | - f_count: 1            |         |
            | - f_inode --------------|-----+   |
            +-------------------------+     |   |
                                            |   |
                                            v   v (VFS Inode Table)
                                  +-----------------------+
                                  | struct inode (File A) |
                                  | - size: 1048576       |
                                  | - address_space       |
                                  |   (Page Cache Radix)  |
                                  +-----------------------+
```

Jika Process A melakukan `fork()`, Child Process mewarisi tabel FD Process A; kedua proses mereferensikan `struct file` yang **sama**, berbagi kursor `f_pos` yang identik. Namun, jika Process B memanggil `open()` pada file path yang sama, kernel mengalokasikan `struct file` **baru** dengan `f_pos` independen, tetapi menunjuk ke `struct inode` yang sama.

#### 3.2 Linux Page Cache, Dirty Pages, dan Write-back Architecture
Operasi `write(2)` standar POSIX bersifat *buffered via Page Cache*:
1. `write(fd, buf, count)` menyalin data dari user-space memory buffer ke satu atau lebih alokasi 4KiB Physical Page Frames di Kernel (*Page Cache*).
2. Begitu data tersalin ke Page Cache, page tersebut ditandai sebagai **Dirty Page**.
3. Panggilan `write()` langsung mengembalikan status sukses (`count` bytes written) ke user-space, **sebelum** data menyentuh storage non-volatile (NVMe/SSD/HDD).
4. Kernel thread background (`flusher threads` atau `kswapd`/`bdi-default`) secara asinkron melakukan flush data kotor tersebut ke media fisik berdasarkan threshold sysctl (`dirty_background_ratio`, `dirty_expire_centisecs`).
5. Implikasi: Pemadaman listrik mendadak (*power failure*) sebelum flush selesai mengakibatkan data hilang atau *data corruption*.

#### 3.3 Zero-Copy Mechanics: Mengapa Standard I/O Lambat
Standard pipeline `read(disk_fd, buf, len)` dilanjutkan `write(socket_fd, buf, len)` menghasilkan beban CPU dan memori signifikan:
* **4 Context Switches** (User $\to$ Kernel $\to$ User $\to$ Kernel $\to$ User).
* **4 Data Copies**:
  1. DMA Engine menyalin dari Disk ke Kernel Page Cache.
  2. CPU menyalin dari Kernel Page Cache ke User Buffer (`buf`).
  3. CPU menyalin dari User Buffer (`buf`) ke Socket Buffer (Kernel).
  4. DMA Engine menyalin dari Socket Buffer ke NIC Ring Buffer.

Zero-copy primitive (`sendfile`, `splice`) mengeliminasi traversal data ke User Space:
* Mengurangi context switch menjadi **2**.
* Eliminasi CPU copies: Data ditransfer antar *kernel page cache buffers* atau langsung di-map ke NIC via scatter-gather DMA descriptor (*True Zero-Copy*).

---

### 4. Why & What

| Mekanisme | What (Definisi Teknis) | Why (Kapan & Alasan Dipakai) | Konsekuensi / Risiko |
| :--- | :--- | :--- | :--- |
| **Vectored I/O** (`readv`/`writev`) | Transfer banyak buffer non-kontigu (*scatter-gather*) dalam 1 syscall atomik. | Menghindari penggabungan (*memcpy*) buffer header & payload secara manual di user-space. | Memory alignment harus presisi; batas array vector dibatasi oleh `IOV_MAX` (biasanya 1024). |
| **Memory Mapping** (`mmap`) | Memetakan virtual memory address space proses langsung ke kernel page cache berkas. | Akses berkas besar secara random (*random reads*) tanpa overhead traversal `read()` syscall. | *Page fault overhead*, `SIGBUS` fatal jika berkas ter-truncate oleh proses lain saat diakses. |
| **Direct I/O** (`O_DIRECT`) | Bypass kernel page cache sepenuhnya; DMA mentransfer langsung user-memory $\leftrightarrow$ disk. | Digunakan oleh RDBMS (misal PostgreSQL/MySQL) yang mengelola cache management sendiri. | Memori user-space, buffer offset, dan transfer size wajib rataan (*aligned*) kelipatan block size disk (biasanya 4096 byte). |
| **Zero-Copy** (`sendfile`/`splice`) | Transfer data pipeline in-kernel antar descriptor tanpa singgah di user-space. | Proxy server, static file serving (Nginx/Kafka style) untuk saturasi 40/100 GbE link. | Fleksibilitas manipulasi payload terbatas karena user-space tidak memeriksa data bytes. |
| **Atomic Sync** (`fsync` vs `fdatasync`) | Memaksa dirty page dan metadata berkas untuk di-flush ke disk non-volatile. | Menjamin durabilitas ACID pada Write-Ahead Logging (WAL) database. | Sangat lambat (*I/O barrier stall*); `fdatasync` menghemat disk write dengan tidak me-flush metadata non-esensial (misal: st_atime). |

---

### 5. How (Workflow Detail)

#### Pipeline Zero-Copy & Vectored Engine
Diagram alir berikut menunjukkan keputusan eksekusi I/O pada subsistem berperforma tinggi:

```
[Mulai Operasi I/O]
        |
        v
Apakah I/O melibatkan Socket Pipeline (cth: File -> Network)?
   |                 |
 [YA]               [TIDAK]
   |                 |
   v                 v
Gunakan splice()     Apakah ukuran buffer fragmented (Header + Data + Trailer)?
atau sendfile()         |                 |
                      [YA]               [TIDAK]
                        |                 |
                        v                 v
                 Gunakan writev()    Apakah butuh custom buffer management (DBMS)?
                 Scatter-Gather I/O     |                 |
                                      [YA]               [TIDAK]
                                        |                 |
                                        v                 v
                                  Buka berkas       Gunakan mmap()
                                  dgn O_DIRECT      atau read()/write()
                                  Align ke 4096B    dengan buffered Page Cache
```

#### Siklus Eksekusi `fdatasync` vs `fsync`
1. Thread menulis WAL buffer melalui `write()`.
2. Halaman memori berubah status menjadi *Dirty Page* di Page Cache.
3. Thread memanggil `fdatasync(fd)`:
   * Kernel melacak blok data yang kotor.
   * Kernel menerbitkan perintah flush perintah NVMe/SCSI (`SYNCHRONIZE CACHE`).
   * Kernel **tidak** menulis modifikasi metadata jika ukuran berkas tidak berubah (menghindari double disk-seek).
4. Storage Controller melakukan *write to non-volatile cache (Power-Loss Protection / PLP capacitor)*.
5. Syscall kembali dengan return value `0`.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Birokrasi Logistik Kontainer
* **Standard `read()`/`write()`**: Truk barang (Disk) datang ke gudang pusat (Page Cache). Barang dibongkar, dibawa kurir naik motor ke kantor Anda (User Space Buffer), Anda stempel, lalu kurir membawa barang itu kembali ke kantor pos (Socket Buffer) untuk dimuat ke truk kargo lain (NIC). Banyak tenaga terbuang.
* **Vectored I/O (`writev`)**: Mengirim beberapa kotak terpisah dalam satu kali angkut kontainer, tanpa Anda harus menyatukan semua isi kotak ke dalam satu kardus raksasa terlebih dahulu.
* **Direct I/O (`O_DIRECT`)**: Anda menyewa truk kargo langsung ke pabrik Anda tanpa singgah di gudang konsolidasi pemda (Page Cache).
* **Zero-Copy (`sendfile`/`splice`)**: Petugas di gudang pusat langsung mengalihkan muatan kontainer dari kereta barang ke kapal kargo tanpa pernah membawanya keluar gerbang pelabuhan.

#### Diagram Ringkasan Interaksi Memori
```
============================= USER SPACE =============================
 [Process Memory: Struct Buffer 1] [Process Memory: Struct Buffer 2]
                \                     /
                 \                   /  writev() (Scatter-Gather)
==================\=================/=================================
                   \               /
                    v             v
============================ KERNEL SPACE ============================
                     [ Page Cache / Socket Buffers ]
                                    |
      Direct I/O (O_DIRECT)         | Regular I/O
      (Bypass Page Cache)           v
               |          [ File System (VFS: ext4/xfs) ]
               |                    |
               +-------------\      |
                             v      v
=========================== HARDWARE LAYER ===========================
                     [ NVMe Controller / Block Device ]
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Atomic Vectored I/O (`writev`)
Contoh menggabungkan protokol frame header dan payload binary tanpa overhead `memcpy` intermediate.

```c
#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/uio.h>
#include <stdint.h>
#include <errno.h>

#pragma pack(push, 1)
typedef struct {
    uint32_t magic;
    uint32_t payload_len;
    uint8_t  crc8;
} PacketHeader;
#pragma pack(pop)

int main(void) {
    const char *filepath = "packet_output.bin";
    int fd = open(filepath, O_CREAT | O_WRONLY | O_TRUNC, 0640);
    if (fd < 0) {
        perror("open failed");
        return EXIT_FAILURE;
    }

    PacketHeader header = {
        .magic = 0xDEADBEEF,
        .payload_len = 16,
        .crc8 = 0x7F
    };

    char payload[16] = "HIGH_PERF_SYSTEM";

    struct iovec iov[2];
    // Vector 0: Header
    iov[0].iov_base = &header;
    iov[0].iov_len = sizeof(PacketHeader);

    // Vector 1: Payload
    iov[1].iov_base = payload;
    iov[1].iov_len = sizeof(payload);

    // Atomic write across both buffers
    ssize_t bytes_written = writev(fd, iov, 2);
    if (bytes_written < 0) {
        perror("writev failed");
        close(fd);
        return EXIT_FAILURE;
    }

    printf("Successfully wrote %zd bytes via vectored I/O.\n", bytes_written);

    close(fd);
    unlink(filepath);
    return EXIT_SUCCESS;
}
```

#### 7.2 Practical Example: Enterprise WAL (Write-Ahead Log) Appender Engine
Engine penyimpan log transaksi terisolasi yang mengimplementasikan `O_DIRECT`, memory alignment check, non-blocking control `fcntl`, dan disk flushing durability.

```c
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <stdint.h>
#include <sys/stat.h>
#include <stdbool.h>

#define ALIGNMENT_SIZE 4096
#define BLOCK_SIZE     4096

typedef struct {
    int fd;
    size_t write_cursor;
    uint8_t *aligned_buffer;
} WALEngine;

int wal_init(WALEngine *wal, const char *path) {
    if (!wal || !path) return -1;

    // Membuka dengan Direct I/O dan Direct Sync flag
    int flags = O_CREAT | O_RDWR | O_DIRECT;
    wal->fd = open(path, flags, 0600);
    if (wal->fd < 0) {
        perror("wal_init: open O_DIRECT failed");
        return -1;
    }

    // Mengalokasikan memory page-aligned untuk Direct I/O
    int res = posix_memalign((void **)&wal->aligned_buffer, ALIGNMENT_SIZE, BLOCK_SIZE);
    if (res != 0) {
        close(wal->fd);
        errno = res;
        return -1;
    }

    memset(wal->aligned_buffer, 0, BLOCK_SIZE);
    wal->write_cursor = 0;
    return 0;
}

ssize_t wal_append_record(WALEngine *wal, const void *data, size_t size) {
    if (!wal || !data || size == 0) return -1;
    if (size > BLOCK_SIZE - sizeof(uint32_t)) {
        errno = EMSGSIZE;
        return -1;
    }

    // Mengemas record: [Len (4B)] + [Raw Data]
    uint32_t record_len = (uint32_t)size;
    memcpy(wal->aligned_buffer, &record_len, sizeof(uint32_t));
    memcpy(wal->aligned_buffer + sizeof(uint32_t), data, size);

    // Padding sisanya dengan 0 agar sesuai dengan block size
    memset(wal->aligned_buffer + sizeof(uint32_t) + size, 0, BLOCK_SIZE - (sizeof(uint32_t) + size));

    // Menulis blok utuh ter-align ke kernel bypass cache
    ssize_t written = write(wal->fd, wal->aligned_buffer, BLOCK_SIZE);
    if (written < 0) {
        return -1;
    }

    // Memaksa controller flush
    if (fdatasync(wal->fd) < 0) {
        return -1;
    }

    wal->write_cursor += BLOCK_SIZE;
    return written;
}

void wal_destroy(WALEngine *wal) {
    if (!wal) return;
    if (wal->fd >= 0) {
        close(wal->fd);
        wal->fd = -1;
    }
    if (wal->aligned_buffer) {
        free(wal->aligned_buffer);
        wal->aligned_buffer = NULL;
    }
}

int main(void) {
    const char *log_path = "./transaction.wal";
    WALEngine wal;

    printf("[Engine] Initializing Direct I/O WAL Engine...\n");
    if (wal_init(&wal, log_path) != 0) {
        // Fallback info: jika filesystem lokal tidak mendukung O_DIRECT (misal tmpfs)
        fprintf(stderr, "Initialization failed. Pastikan FS mendukung O_DIRECT.\n");
        return EXIT_FAILURE;
    }

    const char *txn_sample = "TXN_ID=10924;ACTION=TRANSFER;AMOUNT=5000000;FROM=ACC_A;TO=ACC_B";
    printf("[Engine] Committing transaction atomically...\n");
    ssize_t ret = wal_append_record(&wal, txn_sample, strlen(txn_sample));
    if (ret < 0) {
        perror("[Engine] WAL commit failed");
        wal_destroy(&wal);
        unlink(log_path);
        return EXIT_FAILURE;
    }

    printf("[Engine] Success: Committed %zd aligned bytes to disk (O_DIRECT + fdatasync).\n", ret);

    wal_destroy(&wal);
    unlink(log_path);
    return EXIT_SUCCESS;
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Arsitektur Storage Kafka-like Broker (Disk-to-NIC Throughput Optimization)
* **Konteks Masalah**: Sistem broker perpesanan memproses 10 juta events/detik (~5 GB/s throughput). Implementasi awal menggunakan standard buffered POSIX I/O (`read` berkas segment dari disk ke user buffer, parsing header, lalu `write` ke TCP socket).
* **Gejala Masalah**:
  1. Utilisation CPU mencapai 100% pada *system execution* (`sy` di `top`), bukan *user execution* (`us`).
  2. Beban Context Switch mencapai jutaan per detik.
  3. L1/L3 Data Cache Thrashing parah terdeteksi via `perf stat -e cache-misses`.
* **Analisis Bottleneck**: Terjadi duplikasi penyalinan memori berkali-kali (`Disk Page Cache -> Kernel Buffer -> User Buffer -> Socket Send Buffer -> Network Driver`). CPU habis termakan oleh *memory bus saturated bandwith* dan *virtual memory TLB invalidations*.
* **Solusi Arsitektur**:
  1. Metadata broker dipisahkan dari payload.
  2. Implementasi **Zero-Copy Pipeline** menggunakan `sendfile(2)`:
     ```c
     off_t offset = message_offset;
     ssize_t sent = sendfile(client_socket_fd, segment_fd, &offset, length);
     ```
  3. Mengatur TCP Socket Options: `TCP_CORK` diaktifkan sebelum `sendfile` untuk mengumpulkan paket header dan berkas menjadi segmen MSS (Maximum Segment Size) penuh, lalu dinonaktifkan setelah transfer selesai.
* **Hasil**:
  * Penggunaan CPU turun dari 98% ke 14%.
  * Latensi p99 turun dari 85ms ke 1.8ms.
  * Network card tersaturasi penuh hingga 40Gbps line-rate throughput tanpa packet drop.

---

### 9. Trade-offs

```
                  +-----------------------------------+
                  |        Arsitektur I/O POSIX       |
                  +-----------------------------------+
                   /                                 \
      [ Direct I/O (O_DIRECT) ]              [ Mmap / Standard Cache ]
      - Zero OS-level cache overhead         - Aggressive read-ahead otomatis
      - Deterministic memory footprint       - Dynamic dirty page write-back
      - Memerlukan custom cache-layer        - Overhead TLB Shootdown & Paging
                 |                                      |
         Latency Predictable                    Throughput Tinggi
         (Database WAL Engines)                 (File Server, General)
```

| Pendekatan | Keuntungan Utama | Kerugian / Biaya | Konsekuensi Skalabilitas |
| :--- | :--- | :--- | :--- |
| **`read`/`write` Standar** | Sederhana, aman, memanfaatkan read-ahead otomatis dari OS. | Duplikasi data di User Memory; context switch tinggi. | Bottleneck CPU pada throughput multi-gigabit. |
| **`mmap` (Memory Mapped)** | Tidak ada context switch overhead per-read; akses pointer langsung. | *Major Page Fault* memblokir eksekusi thread; overhead TLB invalidate. | Konsumsi ruang virtual memory masif pada file multi-terabyte. |
| **`O_DIRECT`** | Menghilangkan polusi OS Page Cache; I/O latency terprediksi. | Mematikan read-ahead OS; mewajibkan buffer ter-align kelipatan block size. | Engine harus mengimplementasikan caching dan double-buffering sendiri. |
| **POSIX Advisory Lock** (`fcntl`) | Menghindari *race condition* antar proses pada file storage bersama. | Lambat; *lock contention* tinggi; rentan terhadap *deadlock*. | Tidak horizontal-scalable lintas network filesystem tanpa pNFS/DLM. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Short Reads & Short Writes Handling
* **Mistake**: Berasumsi bahwa pemanggilan `read(fd, buf, 1024)` pasti menghasilkan 1024 byte jika file cukup besar, atau `write()` langsung mengirim seluruh byte. Faktanya, interupsi signal (`EINTR`) atau *pipe/socket availability* dapat menghasilkan nilai return lebih kecil dari total byte requested.
* **Troubleshooting**: Selalu bungkus read/write loop dengan *retry logic*:
```c
ssize_t robust_write(int fd, const void *buf, size_t count) {
    size_t total_written = 0;
    const char *ptr = (const char *)buf;
    while (total_written < count) {
        ssize_t n = write(fd, ptr + total_written, count - total_written);
        if (n < 0) {
            if (errno == EINTR) continue; // Terinterupsi signal, ulangi
            return -1; // Fatal error
        }
        total_written += n;
    }
    return total_written;
}
```

#### 10.2 Descriptor Leaks pada Multithreaded Forking
* **Mistake**: Membuka berkas dengan `open()` tanpa flag `O_CLOEXEC`. Ketika ada thread lain yang memanggil `fork()` + `execve()`, child process baru secara tidak sengaja mewarisi file descriptor tersebut.
* **Troubleshooting**: Selalu sertakan `O_CLOEXEC` pada parameter flags:
```c
int fd = open("secure.dat", O_RDWR | O_CLOEXEC);
```

#### 10.3 Unaligned Access pada `O_DIRECT`
* **Mistake**: Memberikan pointer yang dialokasikan via `malloc()` standar ke `write()` pada file yang dibuka dengan `O_DIRECT`. Menghasilkan error `EINVAL` (Invalid argument).
* **Troubleshooting**: Wajib gunakan `posix_memalign()` untuk memori buffer dan pastikan ukuran byte kelipatan block size storage (biasanya 512 atau 4096).

---

### 11. Best Practices (Production Checklist)

- [ ] **Selalu Gunakan `O_CLOEXEC`**: Mencegah kebocoran resource file descriptor ke child processes.
- [ ] **Terapkan Fallback Loop pada System Call**: Pastikan pengecekan terhadap error code `EINTR` (Signal interruption) dan `EAGAIN`/`EWOULDBLOCK`.
- [ ] **Gunakan `fdatasync()` Alih-alih `fsync()`**: Kecuali perubahan atribut ukuran berkas krusial, `fdatasync()` mengeliminasi disk-seek tambahan untuk flush metadata inode.
- [ ] **Evaluasi Alignment Requirement**: Untuk transfer I/O tingkat rendah berkinerja tinggi, pastikan memory alignment mematuhi batas arsitektur SIMD/DMA (64-byte atau 4096-byte boundary).
- [ ] **Pasang Batasan Sumber Daya (`RLIMIT_NOFILE`)**: Periksa dan sesuaikan limit maksimal open file descriptor sistem menggunakan `getrlimit(2)` dan `setrlimit(2)`.
- [ ] **Hindari Berbagi FD Lintas Thread Tanpa Sinkronisasi**: Kursor berkas internal kernel (`f_pos`) tidak memiliki proteksi reentrant tingkat thread untuk sequential access yang konsisten.
- [ ] **Tutup Resource dengan Pola RAII/Clean Up Label**: Gunakan single-exit pattern (`goto cleanup;`) untuk mencegah *resource leakage* saat error handling.

---

### 12. Hands-on Practice

Simpan seluruh file praktikum pada folder: `hands-on/m02/`

#### Skenario
Membuat utility enterprise storage engine yang:
1. Mengubah file descriptor menjadi non-blocking runtime menggunakan `fcntl`.
2. Mengimplementasikan advisory locking agar hanya satu proses yang dapat mengeksekusi appending.
3. Melakukan sinkronisasi durabilitas berkas secara berkala.

#### Langkah Praktikum
1. Buat direktori:
   ```bash
   mkdir -p hands-on/m02/
   cd hands-on/m02/
   ```
2. Buat file `storage_lock_engine.c`:
   ```c
   #define _GNU_SOURCE
   #include <stdio.h>
   #include <stdlib.h>
   #include <string.h>
   #include <unistd.h>
   #include <fcntl.h>
   #include <errno.h>

   int set_nonblocking(int fd) {
       int flags = fcntl(fd, F_GETFL, 0);
       if (flags == -1) return -1;
       return fcntl(fd, F_SETFL, flags | O_NONBLOCK);
   }

   int acquire_exclusive_lock(int fd) {
       struct flock fl;
       memset(&fl, 0, sizeof(fl));
       fl.l_type   = F_WRLCK;    // Exclusive write lock
       fl.l_whence = SEEK_SET;
       fl.l_start  = 0;          // Mengunci dari byte 0
       fl.l_len    = 0;          // 0 berarti seluruh berkas hingga EOF dinamis

       // Non-blocking lock attempt (F_SETLK alih-alih F_SETLKW)
       if (fcntl(fd, F_SETLK, &fl) == -1) {
           if (errno == EACCES || errno == EAGAIN) {
               return 0; // Berkas terkunci oleh proses lain
           }
           return -1; // Error sistem
       }
       return 1; // Kunci berhasil didapatkan
   }

   int release_lock(int fd) {
       struct flock fl;
       memset(&fl, 0, sizeof(fl));
       fl.l_type   = F_UNLCK;
       fl.l_whence = SEEK_SET;
       fl.l_start  = 0;
       fl.l_len    = 0;
       return fcntl(fd, F_SETLK, &fl);
   }

   int main(void) {
       const char *path = "engine.lock.db";
       int fd = open(path, O_RDWR | O_CREAT | O_CLOEXEC, 0666);
       if (fd < 0) {
           perror("Gagal membuka file database");
           return EXIT_FAILURE;
       }

       printf("[PID: %d] Mencoba mengakuisisi exclusive lock...\n", getpid());
       int lock_status = acquire_exclusive_lock(fd);
       if (lock_status == 0) {
           fprintf(stderr, "[PID: %d] Gagal: File sedang dikunci oleh proses lain!\n", getpid());
           close(fd);
           return EXIT_FAILURE;
       } else if (lock_status < 0) {
           perror("Locking system error");
           close(fd);
           return EXIT_FAILURE;
       }

       printf("[PID: %d] Lock berhasil didapatkan. Melakukan pembaruan kritis...\n", getpid());
       
       const char *entry = "TX_SECURE_PAYMENT_PAYLOAD_COMMIT\n";
       if (write(fd, entry, strlen(entry)) < 0) {
           perror("Gagal menulis data");
       }

       // Flushed to physical disk
       fdatasync(fd);
       printf("[PID: %d] Data tersinkronisasi ke media non-volatile.\n", getpid());

       // Simulasi kerja engine intensif
       sleep(5);

       printf("[PID: %d] Melepaskan lock dan shutdown...\n", getpid());
       release_lock(fd);
       close(fd);

       return EXIT_SUCCESS;
   }
   ```
3. Kompilasi program dengan flag enterprise:
   ```bash
   gcc -Wall -Wextra -pedantic -std=c11 storage_lock_engine.c -o storage_lock_engine
   ```
4. Uji lock contention:
   Jalankan `./storage_lock_engine` di Terminal 1, lalu langsung jalankan kembali `./storage_lock_engine` di Terminal 2. Terminal 2 wajib mendeteksi benturan lock secara non-blocking dan keluar dengan status gagal tanpa crash.

---

### 13. Exercise

#### Level Easy
Buat fungsi `off_t get_file_size_fd(int fd)` yang mengembalikan ukuran berkas riil menggunakan syscall `fstat(2)`. Jangan gunakan pergeseran pointer manual (`lseek`) untuk menghindari race condition pointer pada concurrent access.

#### Level Medium
Buat program pengganti `cat` menggunakan teknik **Vectored I/O** (`readv`). Program harus membaca data dari file input dalam blok 8 KiB yang dipecah merata ke dalam 4 buffer memori yang berbeda secara atomik, lalu memvalidasi urutan pembacaan bytes.

#### Level Hard
Rancang modul `circular_pipe_streamer` yang membaca berkas source berukuran gigabyte dan mentransfernya ke pipa IPC (`pipe(2)`) memanfaatkan syscall `splice(2)` tanpa pernah menyalin data melewati buffer user-space. Tangani mitigasi `EAGAIN`, blocking flow-control pipe, dan partial splices.

---

### 14. Challenge

**Skenario**: Anda ditugaskan membangun High-Frequency Trading (HFT) Market Data Feed Logger berkinerja tinggi. Logger ini harus merekam order-book update stream sebesar ratusan megabyte per detik ke media NVMe secara persistent.
* **Persyaratan Teknis**:
  1. Latensi pemanggilan tulis logging tidak boleh melebihi $5\,\mu\text{s}$ (mikrodetik) pada p99.
  2. Dilarang keras mengandalkan default Page Cache write-back (karena dapat menimbulkan synchronous unpredicted kernel stalls / page-flushing latency spikes).
  3. Menggunakan ring-buffer fixed-size memory-mapped (`mmap`) dengan proteksi `MAP_SHARED` dan *huge pages* (`madvise` dengan flag `MADV_HUGEPAGE`).
  4. Seluruh interaksi disk harus menjamin persistensi atomic block layout; jika server mati mendadak, data transaksi terakhir yang diakui tidak boleh mengalami *corrupt page*.
* **Tugas Arsitektur**:
  Tuliskan spesifikasi rancangan arsitektur C modular (lengkap dengan pseudocode low-level POSIX, pemilihan syscall flags, skema locking/barrier, dan memory layout diagram) untuk engine tersebut. Jelaskan mengapa Anda memilih atau menolak penggunaan Direct I/O vs Memory Mapped Sync I/O.

---

### 15. Quiz Evaluasi Pemahaman

#### Sesi A: 5 Pertanyaan Basic
1. Apa perbedaan mendasar antara File Descriptor Table pada level `task_struct` dengan System-Wide Open File Table pada kernel Linux?
2. Mengapa syscall `fdatasync()` umumnya memiliki performa yang lebih efisien dibandingkan `fsync()` pada operasi write log sekuensial berulang?
3. Apa fungsi struktural dari flag `FD_CLOEXEC` pada descriptor berkas?
4. Mengapa kita tidak dapat langsung mengasumsikan nilai kembalian `write(fd, buf, len)` selalu bernilai identik dengan `len`?
5. Apa konsekuensi fatal jika aplikasi melakukan akses pointer pada memori hasil `mmap()` dari berkas yang ukurannya dipotong (*truncated*) oleh proses eksternal?

#### Sesi B: 5 Pertanyaan Intermediate
1. Mengapa manipulasi status flag menggunakan `fcntl(fd, F_SETFL, O_NONBLOCK)` tidak mengubah entri pada per-process table melainkan pada open file description table? Apa dampaknya jika descriptor ini di-*share* lintas proses melalui `fork()`?
2. Pada implementasi `O_DIRECT`, sebutkan tiga parameter arsitektural yang wajib memiliki alignment terdefinisi ketat terhadap block-size storage!
3. Bagaimana mekanisme kerja *scatter-gather I/O* (`writev`) dalam meminimalkan overhead *context switching* dan alokasi memori sementara?
4. Apa yang membedakan advisory locking (`fcntl` dengan `F_SETLK`) dari mandatory locking pada lingkungan POSIX?
5. Mengapa teknik Zero-Copy seperti `sendfile(2)` tidak cocok diterapkan jika payload paket yang dikirimkan wajib melalui enkripsi TLS/AES secara *in-place* di user-space?

#### Sesi C: 3 Skenario Kasus Produksi
1. **Kasus 1**: Tim SRE melaporkan bahwa aplikasi multi-threaded C yang bertindak sebagai database engine sering mengalami *segmentation fault* atau crash yang tidak terduga setelah beroperasi 24 jam dengan beban I/O tinggi. Ditemukan bahwa thread worker berbagi nilai integer File Descriptor yang sama dan melakukan operasi `lseek()` lalu `read()` tanpa synchronization primitives. Jelaskan akar masalah level kernel dari bug ini dan berikan solusi implementasi syscall yang tepat!
2. **Kasus 2**: Sebuah server web mikro berbasis C mencatat lonjakan drastis pada metrik load memory (`RES` di `htop`) saat membaca file statis berukuran 100 GB menggunakan `mmap()`, hingga memicu Linux OOM-Killer mematikan proses. Syscall `madvise()` apa yang gagal diterapkan pengembang dan bagaimana mitigasi paging kernel-nya?
3. **Kasus 3**: Anda sedang mengaudit sistem storage distributed log. Ditemukan pemanggilan `open("wal.log", O_WRONLY | O_CREAT | O_APPEND, 0644)` diikuti serangkaian operasi `write()`. Pengembang berasumsi bahwa `O_APPEND` sudah menjamin data tertulis langsung ke storage fisik secara aman tanpa perlu memanggil keluarga `sync`. Jelaskan letak kekeliruan fatal dari asumsi durabilitas data tersebut!

---

### 16. Summary

* **File Descriptor Abstraction**: File descriptor bukan representasi fisik melainkan indeks pointer per-proses menuju *System-Wide Open File Description*, yang kemudian merujuk ke VFS Inode. Berbagi FD berarti berbagi kursor offset pencarian internal (`f_pos`).
* **Vectored & Zero-Copy Primitives**: Syscall seperti `writev`, `sendfile`, dan `splice` memotong overhead komputasi CPU secara drastis melalui pengurangan *context switching* serta eliminasi penyalinan memori perantara antara user space dan kernel memory buffers.
* **Storage Durability Realities**: `write()` hanya memindahkan data ke *Kernel Page Cache*. Menjamin data benar-benar tersimpan di piringan magnetik/sel silikon memerlukan eksekusi eksplisit `fdatasync()` guna mencegah *silent data loss* saat terjadi kegagalan daya.
* **Direct Control**: `fcntl` memberikan kontrol granular run-time terhadap atribut berkas (non-blocking, locking, status flags). Penggunaan `O_DIRECT` meniadakan campur tangan OS cache untuk kebutuhan arsitektur khusus tingkat lanjut, namun menuntut alignment ketat pada hardware boundary.