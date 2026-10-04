# BAB 08 / MODUL 01: I/O TINGKAT RENDAH, FILE DESCRIPTOR, & POSIX SYSCALLS

---

### SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** 02-Programming-Languages
*   **Mata Kuliah:** Pemrograman Sistem Berkinerja Tinggi dalam C
*   **Kode Modul:** C-SYS-0801
*   **Prasyarat:**
    *   Pemahaman mendalam tentang Pointer, Manipulasi Memori (`malloc`, `free`), dan Bitwise Operations.
    *   Konsep Arsitektur Komputer: *User Mode* vs *Kernel Mode*, Interupsi Perangkat Keras, dan Struktur Sistem Berkas (Inodes).
*   **Target Audiens:** *Systems Engineers*, *Kernel/Embedded Developers*, *Infrastructure Engineers*, dan Pengembang C tingkat lanjut.
*   **Estimasi Waktu Belajar:** 6 Jam (Teori, Analisis Source Code, Praktikum, dan Debugging Berbasis Profiling).

---

### SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1.  **Membongkar Mekanisme Abstraksi POSIX I/O:** Membedakan antara standard I/O streams terbuffer (`FILE*` di libc) dengan file descriptor mentah (*low-level integer index*) pada tabel proses kernel.
2.  **Mengoperasikan Primitif Pemanggilan Sistem POSIX:** Mengimplementasikan operasi siklus hidup I/O secara deterministik menggunakan `open()`, `read()`, `write()`, `lseek()`, `close()`, dan `fcntl()`.
3.  **Memitigasi Jebakan I/O Tingkat Rendah:** Mengisolasi dan menangani interupsi sinyal (`EINTR`), *short reads/writes*, manipulasi *file offset*, serta kebocoran sumber daya sistem (*resource exhaustion*).
4.  **Menerapkan Pola I/O Kritis untuk Lingkungan Produksi:** Mengintegrasikan flag POSIX mutakhir (`O_CLOEXEC`, `O_DIRECT`, `O_SYNC`, `O_NOFOLLOW`) untuk menjamin konsistensi data (*crash-resilient*) dan keamanan struktural.
5.  **Mendiagnosis Anomali Sistem Berkas Tingkat Kernel:** Melacak, menginspeksi, dan menyelesaikan *bottleneck* I/O menggunakan antarmuka `/proc` serta *tracing tools* sistem operasi (`strace`, `lsof`).

---

### SEKSI 03 — MINDSET & MENTAL MODEL

Dalam pemrograman C tingkat tinggi, berkas sering dipandang sebagai aliran data linier (*stream*) tak terhingga yang diabstraksikan oleh runtime library melalui pointer `FILE*`. Model mental ini menyembunyikan realitas perangkat keras demi kemudahan portabilitas. 

Namun, ketika Anda memasuki ranah **Pemrograman Sistem**, abstraksi ini harus diruntuhkan.

```
Mental Model Tradisional (High-Level):
[Program C] ---> [Buffer Libc (4KB-8KB)] ---> [Sistem Berkas]

Mental Model Rekayasa Sistem (POSIX Low-Level):
[Program C (User Space)]
       │ (Ring 3)
═══════╪═════════════════════════════════════════════════════════ [Syscall Barrier]
       ▼ (Ring 0)
[System Call Interface: sys_read/sys_write]
       │
[Process FD Table] ---> [Open File Description] ---> [VFS Inode / Page Cache]
                                                                │
                                                     [Block Device Driver]
                                                                │
                                                      [Physical Storage (NVMe/SSD)]
```

*File Descriptor* (FD) bukanlah berkas, bukan pointer memori, dan bukan struktur data di *user space*. **File Descriptor hanyalah sebuah bilangan bulat non-negatif (`int`)**, sebuah indeks yang menunjuk ke dalam array penunjuk privat milik kernel (*File Descriptor Table*) yang berada di dalam struktur data proses Anda (`task_struct`).

Mengoperasikan I/O tingkat rendah berarti menginstruksikan kernel secara langsung melalui pemanggilan sistem (*system calls / syscalls*). Anda melepaskan jaring pengaman libc—tidak ada *auto-buffering*, tidak ada penanganan otomatis atas fragmentasi *packet/block*, dan tidak ada proteksi konkurensi bawaan. Tanggung jawab manajemen siklus hidup blok data beralih sepenuhnya ke tangan Anda.

---

### SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Untuk memahami bagaimana sebuah proses berinteraksi dengan kernel melalui FD, perhatikan hierarki relasi data struktural pada kernel Linux berikut:

```
Process A (PID: 1024)
┌─────────────────────────────────┐
│ task_struct                     │
│   files_struct *files           │
│     ┌─────────────────────────┐ │
│     │ fdtable (Array of ptrs) │ │
│     │ 0: stdin                │ │
│     │ 1: stdout               │ │
│     │ 2: stderr               │ │
│     │ 3: fd3 ─────────┐       │ │
│     │ 4: fd4 ─────┐   │       │ │
│     └─────────────┼───┼───────┘ │
└───────────────────┼───┼─────────┘
                    │   │
Process B (PID: 1025)   │   │
┌───────────────────┼───┼─────────┐
│ fdtable           │   │         │
│ 3: fd3 ───────────┘   │         │
└───────────────────────┼─────────┘
                        │
                        ▼ Kernel Global Space
      ┌────────────────────────────────────────────────────────┐
      │ Open File Table (struct file)                          │
      │ ┌────────────────────────────────────────────────────┐ │
      │ │ struct file (Instance 1)                           │ │
      │ │  - f_mode (FMODE_READ | FMODE_WRITE)               │ │
      │ │  - f_pos (File offset cursor: misal 4096)          │ │
      │ │  - f_count (Reference count: 1)                    │ │
      │ │  - f_inode ────────────────────────┐               │ │
      │ └────────────────────────────────────┼───────────────┘ │
      │                                      │                 │
      │ ┌────────────────────────────────────┼───────────────┐ │
      │ │ struct file (Instance 2)           │               │ │
      │ │  - f_mode (FMODE_READ)             │               │ │
      │ │  - f_pos (File offset cursor: 0)   │               │ │
      │ │  - f_count (Reference count: 2)    │               │ │
      │ │  - f_inode ────────────────────────┤               │ │
      │ └────────────────────────────────────┼───────────────┘ │
      └──────────────────────────────────────┼─────────────────┘
                                             │
                                             ▼
      ┌────────────────────────────────────────────────────────┐
      │ VFS Inode Table (struct inode)                         │
      │ ┌────────────────────────────────────────────────────┐ │
      │ │ struct inode (File: "/var/log/syslog")             │ │
      │ │  - i_size (Ukuran aktual berkas: 1048576 byte)     │ │
      │ │  - i_permissions (0644)                            │ │
      │ │  - i_data (Address space mapping -> Page Cache)    │ │
      │ │  - Operations (*read, *write, *fallocate)          │ │
      │ └────────────────────────────────────────────────────┘ │
      └────────────────────────────────────────────────────────┘
```

#### Alur Eksekusi Pemanggilan Sistem `read()`
Diagram alur berikut mengilustrasikan perpindahan konteks (*context switch*) dari *User Space* ke *Kernel Space* saat mengeksekusi syscall `read`:

```
User Program               Kernel (Syscall Entry)           VFS Layer              Block Layer / Cache
    │                                │                         │                           │
    │  read(fd, buf, count)          │                         │                           │
    ├───────────────────────────────>│                         │                           │
    │  [Trap via sysenter/syscall]   │ Validate FD in fdtable  │                           │
    │  [CPU Context Switch: Ring3->0]│ (Get struct file*)      │                           │
    │                                ├────────────────────────>│                           │
    │                                │                         │ Look up VFS Inode         │
    │                                │                         │ Check Page Cache          │
    │                                │                         ├──────────────────────────>│
    │                                │                         │                           │ Cache Hit / Miss
    │                                │                         │                           │ (Fetch from disk if miss)
    │                                │                         │<──────────────────────────┤
    │                                │ Copy data from Page     │                           │
    │                                │ Cache to User Buffer    │                           │
    │                                │ Update f_pos cursor     │                           │
    │                                │                         │                           │
    │<───────────────────────────────┤                         │                           │
    │  [Return bytes read / -1]      │                         │                           │
    │  [CPU Context Switch: Ring0->3]│                         │                           │
    ▼                                ▼                         ▼                           ▼
```

---

### SEKSI 05 — ANATOMI & MEKANISME INTERNAL

Sistem operasi POSIX mengelola berkas melalui tiga lapisan struktur internal:

#### 1. Per-Process Descriptor Table (`files_struct`)
Setiap proses memiliki tabel deskriptor berkas privat. Indeks tabel ini adalah integer kecil non-negatif (`0, 1, 2, ...`). Nilai kembalian syscall `open()` adalah indeks terendah yang belum terpakai dalam tabel ini. 
Setiap entri memuat sebuah pointer ke entri pada *Open File Table* milik sistem global serta himpunan flag deskriptor (seperti flag `FD_CLOEXEC`).

#### 2. System-Wide Open File Table (`struct file`)
Merupakan tabel global kernel yang merepresentasikan representasi logis dari berkas yang sedang dibuka. Satu entri dibuat setiap kali `open()` dieksekusi (kecuali diduplikasi via `dup()` atau `fork()`). 
Entri ini mengkapsulasi:
*   **File Cursor Offset (`f_pos`):** Titik baca/tulis saat ini.
*   **Status Flags:** Mode akses (`O_RDONLY`, `O_WRONLY`, `O_NONBLOCK`, dll.).
*   **Reference Count:** Jumlah referensi FD di seluruh proses yang menunjuk ke objek deskripsi ini.
*   **Pointer Inode:** Menunjuk ke simpul VFS yang mendasarinya.

#### 3. Active Inode Table (`struct inode`)
Representasi objek fisik dari berkas. Struktur ini independen dari seberapa sering berkas tersebut dibuka. Ia merefleksikan metadata nyata dari sistem berkas (tipe berkas, kepemilikan UID/GID, *permission bits*, ukuran logis berkas, dan pemetaan blok fisik pada *underlying storage*).

#### Transisi Status Ring & Eksekusi Syscall
Ketika fungsi C `read(fd, buf, size)` dipanggil:
1. Pustaka C (`glibc` atau `musl`) memuat nomor syscall (misalnya `__NR_read` = 0 pada x86_64) ke dalam register `RAX`.
2. Parameter fungsi dimuat ke register yang telah ditentukan arsitektur ABI (`RDI` = fd, `RSI` = buf, `RDX` = count).
3. CPU mengeksekusi instruksi perakitan `syscall` (atau `sysenter`).
4. CPU mengalihkan level privilege dari **User Mode (Ring 3)** ke **Supervisor/Kernel Mode (Ring 0)**, menyimpan register program counter (`RIP`), dan melompat ke alamat *System Call Entry Table*.
5. Kernel memvalidasi register memori pengarah buffer (apakah `buf` berada di dalam alokasi memori virtual proses pemanggil dan memiliki izin tulis).
6. Kernel membaca data melalui subsistem Virtual File System (VFS), menyalin byte data dari *kernel page cache* ke alamat memori pengguna menggunakan primitif `copy_to_user()`.
7. Kernel memperbarui offset berkas (`f_pos`), beralih kembali ke Ring 3 melalui instruksi `sysret`/`sysexit`, dan mengembalikan nilai byte ke program pengguna.

---

### SEKSI 06 — DEEP DIVE KONSEP & TEORI

#### POSIX Primitive I/O Syscalls

```c
#include <fcntl.h>
#include <unistd.h>
#include <sys/types.h>

int open(const char *pathname, int flags, ... /* mode_t mode */);
ssize_t read(int fd, void *buf, size_t count);
ssize_t write(int fd, const void *buf, size_t count);
off_t lseek(int fd, off_t offset, int whence);
int close(int fd);
```

##### 1. Semantik `open()` dan Flags Kritis
Eksekusi `open()` memerlukan flag konfigurasi akses yang digabungkan via bitwise OR:

*   **Mode Akses Wajib:** Tepat satu dari `O_RDONLY`, `O_WRONLY`, atau `O_RDWR`.
*   **Flags Operasional dan Keamanan:**
    *   `O_CREAT`: Membuat berkas baru jika belum ada. Jika flag ini aktif, argumen variadik ke-3 (`mode_t mode`) **wajib** disediakan (misalnya `0644`).
    *   `O_EXCL`: Jika dikombinasikan dengan `O_CREAT`, kegagalan instan terjadi jika berkas sudah ada (`errno = EEXIST`). Ini menjamin pembuatan berkas atomik untuk *file locking*.
    *   `O_TRUNC`: Jika berkas sudah ada dan dibuka dalam mode tulis, ukurannya dipotong seketika menjadi 0 byte.
    *   `O_APPEND`: Setiap operasi `write()` secara otomatis menempatkan kursor di akhir berkas secara atomik di level kernel, tanpa peduli pemanggilan `lseek()` sebelumnya.
    *   `O_CLOEXEC`: Mencegah *file descriptor leaks* ke proses anak (*child process*) yang diluncurkan melalui keluarga syscall `execve()`. Bendera ini wajib diaktifkan secara default pada aplikasi enterprise modern.
    *   `O_SYNC` vs `O_DSYNC`:
        *   `O_DSYNC`: Operasi `write()` baru selesai (*blocks*) setelah data ditransfer ke media non-volatile dan integritas data terjamin.
        *   `O_SYNC`: Serupa dengan `O_DSYNC`, namun kernel juga wajib menunggu seluruh pembaruan metadata (seperti timestamp `mtime`, `ctime`) tersimpan permanen di disk fisik.

##### 2. Semantik Asinkron/Sinkronisasi: `fsync()` vs `fdatasync()`
Operasi `write()` pada sistem operasi modern bersifat *asynchronous-buffered* secara default: kernel menyalin data dari *user buffer* ke *kernel page cache*, lalu melepaskan blok pemanggilan (`write()` kembali sukses seketika). Data fisik baru ditulis ke disk melalui *flusher threads* kernel (`flusher/kswapd`).

Untuk memaksakan persistensi data ke perangkat keras fisik secara deterministik:
*   `int fsync(int fd)`: Menulis seluruh dirty page buffer berkas ke disk fisik, termasuk perubahan metadata struktural inode.
*   `int fdatasync(int fd)`: Menulis dirty page buffer berisi payload data berkas, memotong latensi dengan **tidak** memaksakan penulisan perubahan metadata (misal: waktu akses/modifikasi) kecuali perubahan metadata tersebut diperlukan untuk pembacaan data yang sukses (misal: penambahan ukuran berkas `i_size`).

##### 3. Manipulasi Pointer Berkas: `lseek()`
`lseek()` menggeser penunjuk offset baca/tulis (`f_pos`) dari struktur `struct file`.
*   `SEEK_SET`: Offset diatur relatif terhadap awal berkas (0).
*   `SEEK_CUR`: Offset diatur relatif terhadap posisi kursor saat ini.
*   `SEEK_END`: Offset diatur relatif terhadap byte terakhir berkas.

*Sparse Files:* Menulis data melewati batas akhir berkas via `lseek()` memicu pembuatan *file hole* (ruang kosong tanpa blok fisik dialokasikan di disk). Sistem berkas modern (ext4, XFS) hanya mengalokasikan metadata tanpa menghabiskan blok data nyata hingga blok tersebut diisi byte aktual.

---

### SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi utilitas kloning berkas biner (*binary file duplicator*) yang robust, bebas dari kebocoran memori/FD, aman dari interupsi OS, serta kebal terhadap *FD leakage* saat eksekusi `fork/exec`.

```c
/**
 * fundamental_io.c - Robust POSIX File Copier
 * Mematuhi POSIX.1-2008 & C11 Standards
 */

#define _POSIX_C_SOURCE 200809L

#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#include <errno.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/stat.h>

#define BUFFER_SIZE (64 * 1024) /* 64 KiB I/O chunk */

static int robust_copy(const char *src_path, const char *dst_path) {
    if (!src_path || !dst_path) {
        errno = EINVAL;
        return -1;
    }

    /* Buka berkas sumber dengan flag atomik O_CLOEXEC */
    int src_fd = open(src_path, O_RDONLY | O_CLOEXEC);
    if (src_fd < 0) {
        perror("Gagal membuka berkas sumber");
        return -1;
    }

    /* Ekstraksi metadata berkas sumber untuk menyamakan izin berkas target */
    struct stat st;
    if (fstat(src_fd, &st) < 0) {
        perror("Gagal membaca status berkas sumber");
        close(src_fd);
        return -1;
    }

    /* Validasi berkas sumber merupakan berkas reguler */
    if (!S_ISREG(st.st_mode)) {
        fprintf(stderr, "Eksklusi: Berkas sumber bukan berkas reguler!\n");
        close(src_fd);
        errno = EBADF;
        return -1;
    }

    /* Buka berkas target: Buat baru, potong jika ada, izin disesuaikan */
    mode_t dst_mode = st.st_mode & 0777;
    int dst_flags = O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC;
    int dst_fd = open(dst_path, dst_flags, dst_mode);
    if (dst_fd < 0) {
        perror("Gagal membuka/membuat berkas target");
        close(src_fd);
        return -1;
    }

    /* Alokasi buffer transfer data pada heap */
    uint8_t *buffer = malloc(BUFFER_SIZE);
    if (!buffer) {
        perror("Gagal mengalokasikan memory buffer");
        close(src_fd);
        close(dst_fd);
        return -1;
    }

    ssize_t bytes_read = 0;
    int status = 0;

    /* I/O Loop: Penanganan Short Reads & EINTR */
    while (1) {
        bytes_read = read(src_fd, buffer, BUFFER_SIZE);
        if (bytes_read < 0) {
            if (errno == EINTR) {
                /* Pembacaan terinterupsi sinyal POSIX; ulangi operasi */
                continue;
            }
            perror("Kesalahan fatal saat membaca berkas sumber");
            status = -1;
            break;
        }

        /* End-of-File (EOF) tercapai */
        if (bytes_read == 0) {
            break;
        }

        /* Loop Penulisan: Memastikan seluruh segmen tertulis (handling short writes) */
        uint8_t *write_ptr = buffer;
        size_t bytes_remaining = (size_t)bytes_read;

        while (bytes_remaining > 0) {
            ssize_t bytes_written = write(dst_fd, write_ptr, bytes_remaining);
            if (bytes_written < 0) {
                if (errno == EINTR) {
                    continue; /* Diinterupsi sinyal; coba lagi */
                }
                perror("Kesalahan fatal saat menulis ke berkas target");
                status = -1;
                goto cleanup;
            }

            bytes_remaining -= (size_t)bytes_written;
            write_ptr += bytes_written;
        }
    }

    /* Flush metadata dan dirty page buffer ke disk penyimpanan */
    if (status == 0) {
        if (fdatasync(dst_fd) < 0) {
            perror("Gagal sinkronisasi data (fdatasync)");
            status = -1;
        }
    }

cleanup:
    free(buffer);

    /* Tutup kedua file descriptor; cek status close() untuk proteksi flush error */
    if (close(src_fd) < 0) {
        perror("Peringatan: Gagal menutup src_fd");
    }

    if (close(dst_fd) < 0) {
        perror("Gagal menutup dst_fd secara bersih");
        status = -1;
    }

    return status;
}

int main(int argc, char *argv[]) {
    if (argc != 3) {
        fprintf(stderr, "Penggunaan: %s <berkas_sumber> <berkas_tujuan>\n", argv[0]);
        return EXIT_FAILURE;
    }

    if (robust_copy(argv[1], argv[2]) != 0) {
        fprintf(stderr, "Proses salin berkas gagal diselesaikan.\n");
        return EXIT_FAILURE;
    }

    printf("Salin berkas selesai secara aman dan persisten.\n");
    return EXIT_SUCCESS;
}
```

---

### SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi teknis dari komponen implementasi pada Seksi 07:

*   **Baris 6:** `#define _POSIX_C_SOURCE 200809L` menginstruksikan C preprocessor untuk mengekspos API modern POSIX standar (IEEE Std 1003.1-2008), mengaktifkan deklarasi flag seperti `O_CLOEXEC` pada `<fcntl.h>`.
*   **Baris 24:** `open(src_path, O_RDONLY | O_CLOEXEC);` membendung potensi kerentanan *descriptor leakage*. Apabila proses ini meluncurkan *fork-exec* sub-proses lain di *thread* terpisah, FD ini akan tertutup secara otomatis di proses anak.
*   **Baris 31–43:** `fstat(src_fd, &st)` mengekstrak atribut metadata langsung dari node inode kernel yang telah terbuka. Ini menghilangkan potensi *race condition* (TOCTOU) dibanding menggunakan `stat()` berbasis string path. Baris 38 memvalidasi berkas bukan berupa *directory* atau *socket/pipe*.
*   **Baris 46–48:** `open(dst_path, O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, dst_mode);` menginstruksikan kernel secara atomik: buka mode tulis, potong ukuran menjadi 0 byte jika berkas sudah ada, atau buat baru dengan hak akses yang disalin persis dari berkas sumber (`dst_mode`).
*   **Baris 67–75:** Blok penanganan eksekusi `read()`. Kernel dapat menghentikan operasi I/O dan mengembalikan `-1` dengan `errno` bernilai `EINTR` jika ada sinyal eksternal tertangkap (misal `SIGCHLD`, `SIGWINCH`). Kondisi ini bukanlah kegagalan fatal melainkan interupsi sementara; operator `continue` memaksa eksekusi loop berulang.
*   **Baris 78–80:** Ketika `read()` menghasilkan `0`, ini adalah representasi formal dari sinyal EOF (End Of File) pada POSIX standard. Loop dihentikan secara graceful.
*   **Baris 82–97:** Mengimplementasikan algoritma anti *short-write*. Pemanggilan `write()` tidak menjamin bahwa *count* total (misal 64 KiB) berhasil ditulis dalam satu siklus jika kapasitas kernel pipe buffer atau storage FIFO sedang penuh. Pointer penulisan (`write_ptr`) dan sisa muatan (`bytes_remaining`) digeser secara iteratif hingga seluruh frame buffer tuntas ditulis.
*   **Baris 101–105:** Memanggil `fdatasync(dst_fd)`. Pemanggilan ini menahan proses eksekusi (*blocking*) sampai storage controller mengonfirmasi bahwa bit data di page cache kernel telah terdistribusi ke media non-volatile. Ini melindungi integritas data jika sistem crash atau kehilangan daya beberapa detik setelah program berhenti.
*   **Baris 114–117:** Menangkap kode kembalian `close(dst_fd)`. Kesalahan penulisan data yang tertunda (*delayed write error*) dari implementasi VFS atau NFS remote file sharing seringkali baru muncul saat *close operations*.

---

### SEKSI 09 — STUDI KASUS NYATA

#### Skenario Industri: High-Reliability Write-Ahead Logging (WAL) Engine
Pada arsitektur mesin database transaksi (*Database Engine*) atau broker antrean pesan (*High-Throughput Message Queue* seperti Apache Kafka/Pulsar), kegagalan persistensi data adalah kecacatan fatal. 

**Masalah:** 
Penggunaan standar `fwrite()` dan `fprintf()` libc tidak memberikan jaminan deterministik kapan kernel mengeksekusi flush data ke disk. Ketika server mengalami kegagalan daya (*power outage* / *kernel panic*):
1. Data yang berada di buffer libc pengguna hilang total.
2. Penulisan append parsial (*torn writes*) dapat merusak struktur berkas log, membuat keseluruhan database korup dan tidak bisa di-recovery saat *booting*.

**Solusi POSIX Systems Engineering:**
Membangun mesin *Append-Only WAL Engine* berkecepatan tinggi dengan:
*   Membuka berkas log dengan kombinasi mutlak `O_WRONLY | O_CREAT | O_APPEND | O_CLOEXEC`.
*   Struktur *Binary Framing* dengan Magic Number, Frame Length, Sequence ID, Payload, dan Checksum CRC32.
*   Penerapan pemanggilan atomik `fdatasync()` per batch transaksi.
*   Pemeriksaan konsistensi pada *crash-recovery validation*.

---

### SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah implementasi sistem produksi WAL (*Write-Ahead Logging Engine*) minimalis dalam C:

```c
/**
 * wal_engine.c - Production-Grade Minimal Write-Ahead Logger
 * Target: POSIX Compliant Operating Systems (Linux, BSD, macOS)
 */

#define _POSIX_C_SOURCE 200809L

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <errno.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/types.h>
#include <sys/stat.h>

#define WAL_MAGIC 0x57414C31 /* ASCII: "WAL1" */

#pragma pack(push, 1)
typedef struct {
    uint32_t magic;       /* WAL Identifier */
    uint64_t seq_id;      /* Sequence ID Transaksi */
    uint32_t payload_len; /* Ukuran data muatan */
    uint32_t crc32;       /* Checksum payload untuk integritas */
} wal_frame_header_t;
#pragma pack(pop)

/* Implementasi Sederhana Standar IEEE 802.3 CRC32 */
static uint32_t calculate_crc32(const uint8_t *data, size_t length) {
    uint32_t crc = 0xFFFFFFFF;
    for (size_t i = 0; i < length; ++i) {
        crc ^= data[i];
        for (int j = 0; j < 8; ++j) {
            crc = (crc >> 1) ^ (0xEDB88320 & (-(crc & 1)));
        }
    }
    return ~crc;
}

typedef struct {
    int fd;
    uint64_t current_seq;
} wal_logger_t;

/* Inisialisasi atau Pembukaan Berkas WAL */
wal_logger_t *wal_open(const char *path) {
    if (!path) {
        return NULL;
    }

    wal_logger_t *logger = malloc(sizeof(wal_logger_t));
    if (!logger) {
        return NULL;
    }

    /* O_APPEND memastikan penulisan selalu berada di ujung berkas di level kernel */
    int flags = O_RDWR | O_CREAT | O_APPEND | O_CLOEXEC;
    mode_t mode = 0600; /* Proteksi keamanan: Hanya pemilik yang dapat R/W */
    
    logger->fd = open(path, flags, mode);
    if (logger->fd < 0) {
        free(logger);
        return NULL;
    }

    /* Validasi & Deteksi Urutan ID Terakhir untuk Sinkronisasi State */
    struct stat st;
    if (fstat(logger->fd, &st) < 0) {
        close(logger->fd);
        free(logger);
        return NULL;
    }

    logger->current_seq = 0;

    /* Scan berkas jika berkas sudah eksis dan berisi log lama */
    if (st.st_size > 0) {
        off_t offset = 0;
        wal_frame_header_t header;

        while (offset < st.st_size) {
            ssize_t bytes = pread(logger->fd, &header, sizeof(wal_frame_header_t), offset);
            if (bytes != (ssize_t)sizeof(wal_frame_header_t)) {
                break; /* Record rusak/terpotong di ujung berkas */
            }

            if (header.magic != WAL_MAGIC) {
                break; /* Header korup terdeteksi */
            }

            logger->current_seq = header.seq_id;
            offset += sizeof(wal_frame_header_t) + header.payload_len;
        }
    }

    return logger;
}

/* Penulisan Transaksi Atomik Ter-Frame */
bool wal_append(wal_logger_t *logger, const void *payload, uint32_t payload_len) {
    if (!logger || !payload || payload_len == 0) {
        return false;
    }

    wal_frame_header_t header;
    header.magic = WAL_MAGIC;
    header.seq_id = ++logger->current_seq;
    header.payload_len = payload_len;
    header.crc32 = calculate_crc32((const uint8_t *)payload, payload_len);

    /* Susun seluruh frame ke dalam contiguous user buffer untuk meminimalkan I/O calls */
    size_t total_frame_size = sizeof(wal_frame_header_t) + payload_len;
    uint8_t *frame_buffer = malloc(total_frame_size);
    if (!frame_buffer) {
        --logger->current_seq;
        return false;
    }

    memcpy(frame_buffer, &header, sizeof(wal_frame_header_t));
    memcpy(frame_buffer + sizeof(wal_frame_header_t), payload, payload_len);

    /* Tulis frame secara deterministik */
    uint8_t *write_ptr = frame_buffer;
    size_t bytes_to_write = total_frame_size;

    while (bytes_to_write > 0) {
        ssize_t written = write(logger->fd, write_ptr, bytes_to_write);
        if (written < 0) {
            if (errno == EINTR) {
                continue;
            }
            free(frame_buffer);
            --logger->current_seq;
            return false;
        }
        bytes_to_write -= (size_t)written;
        write_ptr += written;
    }

    free(frame_buffer);

    /* 
     * fdatasync: Memaksa kernel dan controller disk untuk melakukan flush 
     * page buffer payload ini ke media non-volatile fisik.
     */
    if (fdatasync(logger->fd) < 0) {
        return false;
    }

    return true;
}

/* Menutup WAL Logger */
void wal_close(wal_logger_t *logger) {
    if (!logger) return;
    if (logger->fd >= 0) {
        fdatasync(logger->fd);
        close(logger->fd);
    }
    free(logger);
}

int main(void) {
    const char *wal_path = "transaction_ledger.wal";
    printf("Menginisialisasi WAL Engine pada: %s\n", wal_path);

    wal_logger_t *logger = wal_open(wal_path);
    if (!logger) {
        perror("Inisialisasi WAL gagal");
        return EXIT_FAILURE;
    }

    printf("Seq ID Terakhir dari penyimpanan: %lu\n", (unsigned long)logger->current_seq);

    /* Simulasi Transaksi Finansial Tingkat Tinggi */
    const char *tx1 = "TXID=1001;SENDER=ALICE;RECV=BOB;AMOUNT=5000.00";
    const char *tx2 = "TXID=1002;SENDER=CHARLIE;RECV=DAVE;AMOUNT=125.50";

    if (wal_append(logger, tx1, (uint32_t)strlen(tx1))) {
        printf("Transaksi 1 berhasil dipersistensikan secara sinkron.\n");
    } else {
        fprintf(stderr, "Gagal menulis Transaksi 1!\n");
    }

    if (wal_append(logger, tx2, (uint32_t)strlen(tx2))) {
        printf("Transaksi 2 berhasil dipersistensikan secara sinkron.\n");
    } else {
        fprintf(stderr, "Gagal menulis Transaksi 2!\n");
    }

    wal_close(logger);
    printf("WAL Engine ditutup secara aman.\n");
    return EXIT_SUCCESS;
}
```

---

### SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

Memilih mekanisme I/O pada C melibatkan kompromi fundamental antara latensi eksekusi, penggunaan CPU, pemanfaatan memori, dan fleksibilitas kontrol.

| Kriteria | POSIX Syscalls Mentah (`open`, `read`, `write`) | C Standard I/O Library (`fopen`, `fread`, `fwrite`) | Memory-Mapped I/O (`mmap`) |
| :--- | :--- | :--- | :--- |
| **Abstraksi Penunjuk** | Integer non-negatif (`int fd`) | Pointer Struktur Objek (`FILE *`) | Pointer Ruang Memori Virtual (`void *`) |
| **User Space Buffering** | **Nir-Buffer** (Langsung menuju Kernel System Call) | **Ada** (Default: 4 KiB - 8 KiB buffer pada libc) | **Nir-Buffer** (Dikelola oleh subsistem Page Fault CPU) |
| **Overhead System Call** | **Tinggi** jika operasi baca/tulis dieksekusi per-byte/potongan kecil | **Rendah** (Libc mengagregasi ratusan I/O kecil menjadi 1 syscall) | **Sangat Rendah** (Nol syscall saat traversal data; hanya trigger page fault) |
| **Kontrol Persistensi** | **Eksplisit & Penuh** (`fsync`, `fdatasync`, `O_DIRECT`, `O_SYNC`) | **Abstrak & Parsial** (`fflush` hanya menjamin data pindah ke kernel) | **Implisit** (`msync` diperlukan untuk jaminan flush) |
| **Efisiensi Copying** | Minimal 1x user-kernel copy via `copy_to/from_user` | Minimal 2x copy (Kernel -> Libc Buffer -> User Buffer) | **Zero-Copy** (User membaca langsung Page Cache via Virtual Memory) |
| **Kasus Penggunaan Optimal** | DBMS Engine, Network Daemon, WAL, Low-level IPC | Utilitas CLI standar, Parsir Teks linier, Scripting C | Pembacaan file basis data acak berukuran masif (Read-Heavy) |

---

### SEKSI 12 — EDGE CASES & PITFALLS

1.  **Short Reads dan Short Writes:**
    *   *Realitas:* Anda meminta `write(fd, buf, 1048576)` (1 MB). Kernel hanya menulis `65536` (64 KB) dan mengembalikan nilai tersebut. Ini **bukan kegagalan**, melainkan perilaku legal sistem POSIX saat pipa memori kernel penuh atau sistem berkas mengalami fragmentasi. Mengabaikan sisa byte yang belum tertulis akan menyebabkan data korup tanpa memunculkan pesan error.
2.  **Sinyal Interupsi (`EINTR`):**
    *   Setiap pemanggilan sistem I/O yang bersifat lambat (*slow syscalls*) dapat dibatalkan sewaktu-waktu oleh sistem operasi jika proses menerima sinyal UNIX (`SIGINT`, `SIGALRM`, `SIGCHLD`). Fungsi mengembalikan `-1` dengan nilai `errno == EINTR`. Jika kode Anda tidak membungkus operasi dalam loop yang mengevaluasi `errno == EINTR`, aplikasi Anda akan mengalami crash terputus-putus (*intermittent fail*).
3.  **Batas Deskriptor Maksimum (*FD Exhaustion*):**
    *   Setiap sistem operasi memiliki batas limit proses (`RLIMIT_NOFILE`, dicek melalui `ulimit -n`). Jika kode Anda gagal memanggil `close(fd)` pada jalur error (*error execution branch*), aplikasi akan kehabisan alokasi FD. Pemanggilan `open()` atau `socket()` berikutnya akan gagal dengan `EMFILE` (*Too many open files*).
4.  **Offset Invalidation Akibat Operasi Paralel:**
    *   Jika sebuah File Descriptor diduplikasi via `dup()` atau diturunkan melalui `fork()`, proses anak dan proses induk berbagi entri `struct file` yang sama pada *Open File Table* milik kernel. Konsekuensinya: **kursor offset (`f_pos`) digunakan bersama**. Penulisan yang terjadi dari dua proses secara bersamaan tanpa sinkronisasi akan saling menimpa data satu sama lain.

---

### SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

#### Kesalahan 1: Mengabaikan Nilai `mode` saat Menggunakan `O_CREAT`
```c
/* KODE RUSAK / BERBAHAYA */
int fd = open("output.dat", O_WRONLY | O_CREAT | O_TRUNC);
```
*Dampak:* Ketika `O_CREAT` dipanggil tanpa argumen ketiga, fungsi `open` membaca data sampah dari tumpukan memori (*stack register*) sebagai izin berkas (*file permissions*). Berkas dapat tercipta dengan izin aneh (misal: `---------` tanpa hak akses sama sekali, atau set-uid bit yang aktif secara tidak sengaja).
*Perbaikan:* Selalu sertakan hak akses eksplisit.
```c
/* KODE BENAR */
int fd = open("output.dat", O_WRONLY | O_CREAT | O_TRUNC, 0644);
```

#### Kesalahan 2: Mengasumsikan `close()` Tidak Pernah Gagal
```c
/* KODE TIDAK AMAN */
write(fd, payload, size);
close(fd);
```
*Dampak:* Pada sistem berkas terdistribusi (*NFS*, *Ceph*) atau partisi tervirtualisasi, kernel mengagregasi penulisan secara asinkron. Kesalahan kegagalan transfer bit storage fisik sering kali baru dievaluasi dan dilaporkan saat operasi *flush* pada fase penutupan berkas (`close`). Mengabaikan nilai kembalian `close()` dapat menyebabkan *silent data corruption*.
*Perbaikan:* Evaluasi nilai kembalian `close()`.
```c
/* KODE BENAR */
if (close(fd) < 0) {
    log_critical("Gagal memvalidasi integritas penutupan berkas: %s", strerror(errno));
}
```

#### Kesalahan 3: FD Leakage saat Operasi `fork` / `exec`
```c
/* KODE RAWAN EKSPLOITASI */
int sensitive_fd = open("/etc/app_secrets.key", O_RDONLY);
// ...
system("/usr/bin/run_script.sh"); // Script mewarisi sensitive_fd!
```
*Dampak:* Proses anak mewarisi seluruh FD dari proses induk secara default. Anak proses yang tidak memiliki otorisasi dapat membaca atau menulis ke descriptor tersebut.
*Perbaikan:* Selalu gunakan flag `O_CLOEXEC` pada seluruh pemanggilan `open()` atau gunakan `fcntl(fd, F_SETFD, FD_CLOEXEC)`.

---

### SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Pola Defensive RAII Manual dalam ANSI C:** Gunakan pola idiomatik `goto cleanup` untuk memusatkan pelepasan sumber daya (*resource deallocation*) sehingga mencegah kebocoran FD saat terjadi kesalahan di tengah fungsi:
    ```c
    int src_fd = -1;
    int dst_fd = -1;
    void *buf = NULL;

    src_fd = open(...);
    if (src_fd < 0) goto cleanup;

    dst_fd = open(...);
    if (dst_fd < 0) goto cleanup;

    buf = malloc(SIZE);
    if (!buf) goto cleanup;

    /* Proses data */

    cleanup:
        if (buf) free(buf);
        if (dst_fd >= 0) close(dst_fd);
        if (src_fd >= 0) close(src_fd);
    ```
2.  **Ukuran Buffer I/O yang Tepat (Aligned I/O):**
    Hindari alokasi buffer dengan ukuran arbitrer (seperti `100 byte`). Gunakan kelipatan dari ukuran blok sistem berkas fisik (*block size*, umumnya **4096 byte / 4 KiB**) untuk memastikan transmisi data selaras (*aligned*) dengan transfer disk dan meminimalkan operasi read-modify-write internal hardware storage.
3.  **Gunakan `openat()`, `pread()`, dan `pwrite()`:**
    Untuk lingkungan multithreading, hindari modifikasi kursor global melalui `lseek()`. Gunakan syscall POSIX thread-safe:
    *   `pread(int fd, void *buf, size_t count, off_t offset)`
    *   `pwrite(int fd, const void *buf, size_t count, off_t offset)`
    Fungsi-fungsi ini membaca dan menulis data pada offset tertentu secara atomik tanpa memodifikasi kursor `f_pos` internal yang digunakan bersama oleh thread lain.

---

### SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

#### Menghindari Context Switch Overhead
Setiap kali program mengeksekusi syscall I/O, CPU mengeluarkan biaya mahal untuk switching dari Ring 3 ke Ring 0 (flushing register pipeline, TLB invalidation risks, evaluasi VFS). Jika Anda mengeksekusi penulisan file 1 MB dengan chunk ukuran 8 byte, program Anda akan memicu 131.072 kali *context switch*. 

```
Beban Eksekusi Berdasarkan Variasi Ukuran Buffer (Transfer File 100 MB):
1 Byte Chunk    : ~100.000.000 Syscalls -> Sangat Lambat (CPU Bound)
64 Byte Chunk   : ~1.562.500 Syscalls   -> Lambat
4096 Byte (4KB) : ~25.600 Syscalls      -> Optimal (Sesuai Ukuran Halaman Kernel)
65536 Byte(64KB): ~1.600 Syscalls       -> Sangat Efisien (Maksimalisasi Throughput L1 Cache)
```

#### Optimasi Berbasis `posix_fadvise`
Jika Anda mengetahui pola akses berkas terlebih dahulu, berikan petunjuk (*hint*) kepada kernel untuk mengoptimalkan strategi subsistem *Page Cache* dan *Readahead*:

```c
#include <fcntl.h>

/* Beri instruksi ke kernel bahwa file akan dibaca secara urut dari awal hingga akhir */
posix_fadvise(fd, 0, 0, POSIX_FADV_SEQUENTIAL);

/* Beri instruksi ke kernel bahwa data yang baru saja dibaca tidak akan digunakan lagi 
   (Kernel dapat langsung membersihkan data dari Page Cache tanpa membuang RAM) */
posix_fadvise(fd, offset, length, POSIX_FADV_DONTNEED);
```

---

### SEKSI 16 — KEAMANAN & HARDENING

Sistem I/O tingkat rendah rentan terhadap eksploitasi jika pengembang mempercayai input path secara naif:

#### 1. TOCTOU (Time-of-Check to Time-of-Use) Vulnerabilities
Mengecek status berkas dengan `access()` lalu membukanya dengan `open()` membuka celah bagi penyerang untuk menukar berkas tersebut dengan *symbolic link* berbahaya di antara dua instruksi tersebut.

*Mitigasi:*
Hindari verifikasi terpisah. Gunakan pembukaan atomik menggunakan flag kernel:
```c
/* GAGAL: Rawan race condition */
if (access("/tmp/app.lock", F_OK) != 0) {
    int fd = open("/tmp/app.lock", O_CREAT | O_WRONLY, 0600);
}

/* AMAN: Atomik di level kernel */
int fd = open("/tmp/app.lock", O_CREAT | O_EXCL | O_WRONLY, 0600);
if (fd < 0 && errno == EEXIST) {
    /* Berkas sudah ada, batalkan aksi tanpa risiko serangan symlink */
}
```

#### 2. Symlink Exploitation via `O_NOFOLLOW`
Jika aplikasi Anda berjalan dengan hak akses administratif (root/daemon), penyerang di ruang pengguna (*unprivileged user*) dapat membuat symlink dari direktori sementara yang mengarah ke `/etc/shadow` atau `/etc/passwd`.
Jika Anda memanggil `open()` pada berkas tersebut, Anda berisiko merusak konfigurasi sistem keamanan utama.
*Mitigasi:* Selalu sertakan `O_NOFOLLOW` agar pemanggilan `open()` langsung gagal jika elemen target terakhir dari path adalah sebuah symlink.

#### 3. Path Traversal & `openat()` Hierarchy Lockdown
Gunakan API POSIX modern `openat(int dirfd, const char *pathname, int flags, ...)` untuk mengunci operasi I/O hanya pada lingkup deskriptor direktori kerja tertentu, mencegah manipulasi path `../../`.

---

### SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Untuk melihat secara real-time interaksi program Anda dengan kernel:

#### 1. Tracing Menggunakan `strace`
Jalankan binary Anda di bawah pengawasan `strace` untuk melihat argumen register, nilai kembalian, durasi, dan kode error sistem berkas:
```bash
strace -T -e trace=openat,read,write,close,fdatasync ./wal_engine
```
*Output Tipikal:*
```text
openat(AT_FDCWD, "transaction_ledger.wal", O_RDWR|O_CREAT|O_APPEND|O_CLOEXEC, 0600) = 3 <0.000045>
write(3, "WAL1\1\0\0\0\0\0\0...", 66) = 66 <0.000021>
fdatasync(3)                            = 0 <0.002130>
close(3)                                = 0 <0.000015>
```
*Analisis:* Dari data di atas, kita dapat memverifikasi bahwa latency terbesar berada pada `fdatasync` (2.13 ms) yang merefleksikan persistensi fisik hardware media disk.

#### 2. Inspeksi `/proc` File System
Setiap proses Linux mengekspos tabel deskriptor aktifnya pada `/proc/<PID>/fd/`.
```bash
# Menampilkan seluruh FD yang sedang dibuka oleh proses target
ls -la /proc/$(pgrep wal_engine)/fd/

# Output:
# lrwx------ 1 user user 64 Feb 16 00:00 0 -> /dev/pts/1
# lrwx------ 1 user user 64 Feb 16 00:00 1 -> /dev/pts/1
# lrwx------ 1 user user 64 Feb 16 00:00 2 -> /dev/pts/1
# lrwx------ 1 user user 64 Feb 16 00:00 3 -> /home/user/transaction_ledger.wal
```
Untuk menginspeksi kursor offset dan status flags pada Open File Table:
```bash
cat /proc/$(pgrep wal_engine)/fdinfo/3

# Output:
# pos:    132           <-- Menunjukkan f_pos saat ini di kernel
# flags:  0102002       <-- Bit flags representasi O_RDWR | O_APPEND dsb
# mnt_id: 28
```

#### 3. Monitoring Berkas Terbuka Global via `lsof`
```bash
lsof -p <PID> -a -d ^txt,^mem,^cwd
```
Perintah ini menyaring dan hanya menampilkan file descriptor data aktual yang sedang dimanipulasi oleh target PID.

---

### SEKSI 18 — RINGKASAN & CHEAT SHEET

#### File Descriptor Standar POSIX
| Konstanta Macro | Nilai FD Integer | Keterangan Standar | Objek Libc Setara |
| :--- | :--- | :--- | :--- |
| `STDIN_FILENO` | `0` | Standard Input | `stdin` |
| `STDOUT_FILENO` | `1` | Standard Output | `stdout` |
| `STDERR_FILENO` | `2` | Standard Error | `stderr` |

#### Tabel Opsi Flag `open()` Penting
| Flag Macro | Kategori | Fungsi / Efek Sistem |
| :--- | :--- | :--- |
| `O_RDONLY` | Akses | Membuka berkas khusus untuk operasi baca. |
| `O_WRONLY` | Akses | Membuka berkas khusus untuk operasi tulis. |
| `O_RDWR` | Akses | Membuka berkas untuk operasi baca dan tulis. |
| `O_CREAT` | Pembuatan | Membuat berkas jika belum ada (wajib sertakan argumen `mode_t`). |
| `O_EXCL` | Kontrol | Bersama `O_CREAT`, gagalkan proses secara atomik jika file sudah ada. |
| `O_TRUNC` | Modifikasi | Potong ukuran berkas menjadi 0 byte saat dibuka. |
| `O_APPEND` | Offset | Posisikan kursor baca/tulis di akhir berkas pada setiap penulisan. |
| `O_CLOEXEC` | Keamanan | Tutup FD secara otomatis saat proses mengeksekusi `execve`. |
| `O_NONBLOCK` | Kontrol I/O | Operasi tidak menunggu data; kembali seketika dengan `EAGAIN`/`EWOULDBLOCK`. |
| `O_SYNC` | Integritas | Operasi penulisan memblokir eksekusi hingga data dan seluruh metadata persisten. |
| `O_DSYNC` | Integritas | Operasi penulisan memblokir eksekusi hingga payload data persisten. |
| `O_NOFOLLOW` | Keamanan | Gagal jika path target akhir adalah sebuah symbolic link. |

#### Tabel Nilai Kembalian Primitif
*   **Error Global:** Hampir seluruh POSIX I/O syscalls mengembalikan nilai `-1` jika operasi gagal dan memuat kode alasan kegagalan pada variabel global `errno`.
*   **`read()`:** Mengembalikan `> 0` (jumlah byte berhasil dibaca), `0` (EOF), atau `-1` (Error).
*   **`write()`:** Mengembalikan `>= 0` (jumlah byte berhasil ditulis), atau `-1` (Error).

---

### SEKSI 19 — KUIS EVALUASI PEMAHAMAN

#### Pertanyaan Konseptual & Dasar

1. **Mengapa nilai representasi File Descriptor selalu menggunakan tipe data `int` bertanda (*signed*), bukan bilangan bulat tak bertanda (*unsigned integer* seperti `uint32_t`)?**
   * *Jawaban:* Karena sistem operasi POSIX membutuhkan nilai negatif (secara spesifik `-1`) sebagai penanda bahwa pemanggilan sistem telah gagal mengeksekusi operasi dan memicu kernel untuk mengeset register error `errno`.

2. **Jelaskan apa yang terjadi pada *active file offset* (`f_pos`) jika sebuah proses memanggil `fork()` setelah berhasil membuka sebuah berkas!**
   * *Jawaban:* `fork()` menduplikasi tabel deskriptor proses anak dari proses induk, namun kedua entri deskriptor tersebut menunjuk ke objek `struct file` yang **sama** pada *System-Wide Open File Table* kernel. Oleh karena itu, *file offset* (`f_pos`) terbagi dan digunakan bersama: jika proses anak membaca 100 byte, offset untuk proses induk juga ikut bergeser maju 100 byte.

3. **Kapan kondisi di mana pemanggilan `read()` menghasilkan nilai kembalian `0`?**
   * *Jawaban:* Ketika kursor offset pembacaan berkas telah berada pada atau melewati batas akhir berkas (*End of File / EOF*), atau ketika membaca dari pipe/socket yang ujung penulisan (*write-end*) miliknya telah ditutup secara sempurna.

4. **Sebutkan bahaya dari membuka berkas konfigurasi sementara di direktori publik `/tmp` dengan `open(path, O_CREAT | O_WRONLY, 0666)` tanpa menyertakan flag `O_EXCL`!**
   * *Jawaban:* Hal ini memicu kerentanan *Symlink Race Condition* (TOCTOU). Penyerang lokal dapat menempatkan symlink bernama sama di `/tmp` sebelum program kita mengeksekusi `open()`, yang mengarahkan penulisan ke berkas penting sistem sehingga berkas tersebut ditimpa dengan hak akses proses kita.

5. **Apa perbedaan mendasar antara fungsi `close(fd)` dan fungsi `fsync(fd)`?**
   * *Jawaban:* `close(fd)` hanya melepaskan indeks deskriptor dari tabel proses lokal dan menurunkan *reference count* objek `struct file` kernel tanpa menjamin dirty page buffer telah ditransfer ke disk fisik. Sedangkan `fsync(fd)` memaksa pengosongan buffer kernel page cache dan transfer seluruh blok data serta metadata ke media non-volatile secara persisten.

#### Pertanyaan Analitikal & Lanjutan

6. **Analisis potongan kode berikut. Apakah kode ini dijamin atomik pada sistem multi-thread?**
   ```c
   lseek(fd, target_offset, SEEK_SET);
   write(fd, data, data_len);
   ```
   * *Jawaban:* **Tidak dijamin atomik.** Jika ada thread lain yang mengeksekusi `lseek()` atau `write()` pada FD yang sama di antara eksekusi pemanggilan `lseek()` dan `write()` thread pertama, kursor `f_pos` akan bergeser ke lokasi yang salah. Solusi thread-safe adalah menggunakan syscall atomik `pwrite(fd, data, data_len, target_offset)`.

7. **Mengapa implementasi loop I/O tingkat rendah selalu membutuhkan pengecekan `if (errno == EINTR)` saat fungsi mengembalikan `-1`?**
   * *Jawaban:* Pemanggilan I/O primitif pada kernel UNIX dapat ditangguhkan jika sistem mendeteksi sinyal asynchronous yang masuk. Kernel melepaskan syscall tersebut dengan kode status error dan mengatur `errno = EINTR`. Ini bukanlah kerusakan fatal, melainkan instruksi bahwa operasi terhenti oleh sinyal dan harus diulang kembali oleh proses pengguna.

8. **Apa konsekuensi performa dan integritas jika kita mengganti pemanggilan `fdatasync()` dengan flag `O_SYNC` pada setiap pemanggilan `open()` dalam aplikasi penulisan streaming volume tinggi?**
   * *Jawaban:* Performa akan anjlok drastis (*throughput drop*). `O_SYNC` memaksakan sinkronisasi data fisik dan metadata inode (seperti `mtime`) pada **setiap kali** satu operasi `write()` dipanggil, memaksa disk melakukan dua kali operasi penulisan (data block + inode block). Sedangkan memanggil `fdatasync()` secara periodik (per-batch) memungkinkan pemulihan batching write di memori cache kernel sebelum dipersistensikan sekaligus.

9. **Jika sebuah berkas memiliki ukuran logis 10 byte, kemudian program memanggil `lseek(fd, 1000, SEEK_CUR)` lalu mengeksekusi `write(fd, "A", 1)`, apa yang terbentuk pada sistem berkas?**
   * *Jawaban:* Terbentuk sebuah **Sparse File**. Ruang antara byte ke-10 hingga byte ke-999 menjadi *file hole*. Kernel tidak mengalokasikan blok data fisik di hard drive untuk ruang kosong tersebut. Namun, jika ada proses lain yang mencoba membaca ruang kosong tersebut, kernel akan mengembalikan blok memori yang terisi penuh oleh karakter byte `\0` (null bytes).

10. **Mengapa penulisan ke File Descriptor yang mewakili sebuah Pipe atau Network Socket yang ujung penerimanya sudah tertutup menyebabkan proses mati secara tiba-tiba jika tidak ditangani secara khusus?**
    * *Jawaban:* Karena kernel POSIX akan mengirimkan sinyal pemutus `SIGPIPE` (*Broken Pipe*) secara default kepada proses pengirim saat mendeteksi penulisan ke saluran yang tidak memiliki reader aktif. Karena disposisi default sinyal `SIGPIPE` adalah *Process Termination*, proses C Anda akan mati mendadak kecuali sinyal tersebut diabaikan (`signal(SIGPIPE, SIG_IGN)`) atau ditangani melalui flag khusus transfer network (`MSG_NOSIGNAL`).

---

### SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

#### Proyek: Utilitas File Replacer Atomik Aman & Crash-Resilient (`atomic_replace`)

Tulis utilitas command-line dalam C standar yang mampu mengganti berkas target secara atomik tanpa merusak berkas asli jika terjadi crash di tengah proses.

#### Spesifikasi Fungsional:
1. Program menerima sintaks: `./atomic_replace <target_file> <content_string>`
2. Program **dilarang** menimpa berkas target secara langsung menggunakan `O_TRUNC`.
3. Alur Kerja Wajib:
   * Buat berkas sementara unik pada direktori yang sama dengan berkas target (misal: `<target_file>.tmp.XXXXXX`) menggunakan `open()` dengan flag proteksi `O_CREAT | O_EXCL | O_WRONLY | O_CLOEXEC`.
   * Tulis `content_string` ke dalam berkas sementara tersebut menggunakan loop anti-short-write dan penanganan `EINTR`.
   * Panggil `fdatasync()` pada berkas sementara untuk menjamin data menyentuh media disk fisik secara utuh.
   * Ambil metadata perizinan (*file mode permissions*) dari berkas asli (jika sudah ada sebelumnya) menggunakan `fstat()`, lalu terapkan ke berkas sementara via `fchmod()`.
   * Tutup berkas sementara secara aman via `close()`.
   * Lakukan pergantian atomik menggunakan syscall `rename(temp_path, target_path)`. Berdasarkan standar POSIX, syscall `rename()` menjamin bahwa proses penggantian berkas bersifat *all-or-nothing*: jika sistem kehilangan daya saat operasi ini, sistem berkas akan tetap mempertahankan berkas lama yang utuh atau berkas baru yang utuh, tanpa pernah meninggalkan status berkas yang terpotong/korup.
   * Lakukan sinkronisasi direktori induk: Buka direktori yang memuat target file menggunakan `open(dir_path, O_DIRECTORY | O_RDONLY)` dan jalankan `fsync(dir_fd)` untuk memastikan entri modifikasi tabel direktori VFS tertulis permanen ke disk.
4. Tangani pembersihan berkas sementara (`unlink()`) jika terjadi kegagalan eksekusi di titik mana pun sebelum fungsi `rename()` berhasil.

#### Standard Kualitas Kode:
*   Kompilasi bersih menggunakan compiler GCC/Clang dengan flags:
    ```bash
    gcc -Wall -Wextra -Werror -pedantic -std=c11 -D_POSIX_C_SOURCE=200809L atomic_replace.c -o atomic_replace
    ```
*   Nol kebocoran memori virtual dan nol kebocoran file descriptor (verifikasi menggunakan utilitas `valgrind --leak-check=full --track-fds=yes`).