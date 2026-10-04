# BAB 08: Quiz, Challenge, & Knowledge Check
**I/O Tingkat Rendah, File Descriptor, & POSIX Syscalls**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Jelaskan perbedaan mendasar antara *Standard I/O Library* (`<stdio.h>`: `fopen`, `fread`, `fwrite`) dan *POSIX Low-Level I/O* (`<unistd.h>`, `<fcntl.h>`: `open`, `read`, `write`)!**  
   Fokuskan jawaban Anda pada alokasi *user-space buffer*, transisi *context switch* ke *kernel space*, dan determinisme latensi saat berhadapan dengan *real-time execution*.

2. **Bagaimana kernel Linux mengorganisir abstraksi I/O melalui tiga struktur data: *Process File Descriptor Table*, *System-wide Open File Table*, dan *Inode Table*?**  
   Gambarkan hubungan relasional antarketiganya dan jelaskan di tabel mana *file offset* serta *access mode flags* (`O_RDONLY`, `O_SYNC`, dll.) disimpan.

3. **Mengapa nilai kembalian (*return value*) dari *syscall* `read()` atau `write()` tidak menjamin bahwa seluruh *byte* yang diminta berhasil diproses (*short read/write*)?**  
   Sebutkan kondisi-kondisi valid di mana *short count* terjadi pada *regular file*, *pipe*, dan *socket*, serta bagaimana struktur perulangan idiomatik C yang benar untuk memitigasi hal ini.

4. **Bagaimana semantik kerja *syscall* `dup()` dan `dup2()`, serta apa perbedaan perilakunya dibanding manipulasi via `fcntl(fd, F_DUPFD, ...)`?**  
   Jelaskan mengapa penggunaan `dup2(oldfd, newfd)` rentan terhadap *race condition* tersembunyi pada arsitektur program *multithreaded*, dan alternatif atomik apa yang disediakan standar POSIX terkini.

5. **Bandingkan mekanisme dan dampak performa antara `fsync()`, `fdatasync()`, dan flag `O_SYNC` saat memanggil `open()`!**  
   Kapan seorang *systems engineer* secara spesifik harus memilih `fdatasync()` dibanding `fsync()` untuk mengoptimalkan operasi *write-heavy disk throughput*?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Sebuah proses melakukan `open()` terhadap suatu file, lalu mengeksekusi `fork()`.**  
   - Apakah *child process* mendapatkan salinan independen dari *file offset*, atau keduanya berbagi *offset* yang sama?  
   - Bagaimana jika skenario tersebut diganti menggunakan `pthread_create()` alih-alih `fork()`? Jelaskan dampaknya terhadap integritas data jika kedua entitas mengeksekusi `write()` secara simultan tanpa *synchronization primitive*.

2. **Ditinjau dari perspektif kernel POSIX, mengapa pendekatan penulisan log menggunakan kombinasi `lseek(fd, 0, SEEK_END)` diikuti `write(fd, buf, len)` TIDAK atomik, sedangkan membuka file dengan flag `O_APPEND` menjamin atomisitas penulisan lintas proses?**  
   Jelaskan kondisi balapan (*race condition*) yang terjadi pada level instruksi kernel.

3. **Apa perbedaan teknis antara pasangan *syscall* `read()`/`write()` dengan `pread()`/`pwrite()`?**  
   Mengapa *database storage engine* modern (seperti SQLite, RocksDB, atau InnoDB) sangat bergantung pada `pread()`/`pwrite()` untuk operasi I/O multi-utas (*concurrent multi-threaded reads/writes*) pada file data yang sama?

4. **Jelaskan risiko keamanan (*security vulnerability*) dan stabilitas yang disebabkan oleh kebocoran *file descriptor* (*FD leak*) saat proses memanggil fungsi turunan `exec()` (`execve`, `execl`, dll.)!**  
   Bagaimana flag `O_CLOEXEC` pada `open()` atau flag `FD_CLOEXEC` pada `fcntl()` mengatasi masalah ini secara atomik, dan mengapa operasi `fcntl(fd, F_SETFD, FD_CLOEXEC)` non-atomik berbahaya dalam program *multi-threaded*?

5. **Perhatikan *snippet* kode berikut:**
   ```c
   int fd = open("sensor_stream.fifo", O_RDONLY | O_NONBLOCK);
   char buf[128];
   ssize_t n = read(fd, buf, sizeof(buf));
   if (n == -1) {
       // Penanganan error
   }
   ```
   Jika `n == -1`, analisislah perbedaan perlakuan yang harus diambil jika `errno` bernilai `EAGAIN` (atau `EWOULDBLOCK`) dibandingkan jika bernilai `EINTR`. Tuliskan blok *error handling* standar produksi untuk kasus ini.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Latency Spike Akibat Page Cache Writeback Thrashing
Sebuah mesin peladen transaksi finansial berbasis Linux mencatat order transaksi ke dalam file log transaksi biner menggunakan I/O tingkat rendah (`write()` POSIX). Peladen berjalan dengan *throughput* 40.000 transaksi per detik. Secara periodik (setiap 30–60 detik), sistem mengalami *latency spike* hingga ratusan milidetik, di mana panggilan `write()` yang biasanya memakan waktu < 2 mikrodetik tiba-tiba memblokir eksekusi thread.

*   **Pertanyaan Diagnostik:**
    1. Mengapa *syscall* `write()` yang secara default beroperasi pada Linux *Page Cache* (bukan disk langsung) dapat memblokir eksekusi thread secara tiba-tiba? Parameter kernel apa (`/proc/sys/vm/dirty_*`) yang memicu kondisi ini?
    2. Langkah instrumentasi apa (menggunakan *command-line tools* atau *tracing*) yang dapat membuktikan bahwa *dirty page writeback* adalah penyebabnya?
    3. Solusi I/O arsitektural apa yang dapat Anda terapkan pada kode C untuk menstabilkan latensi tanpa mengorbankan integritas data secara fatal?

### Skenario B: Deadlock IPC Akibat Unclosed Pipe File Descriptor
Sebuah arsitektur komputasi terdistribusi menggunakan *forking worker model*. Proses induk (*parent*) membuat *unnamed pipe* via `pipe(pipefd)` untuk mengirimkan data ke beberapa proses anak (*child*). Setelah *fork*, proses anak membaca dari `pipefd[0]` sampai menerima *End-of-File* (EOF, ditandai dengan `read() == 0`). Namun, pada implementasi terbaru, proses anak mengalami *hang* permanen (*deadlock*) dan tidak pernah membaca nilai return 0, meskipun proses induk telah selesai menulis data dan memanggil `close(pipefd[1])`.

*   **Pertanyaan Diagnostik:**
    1. Mengapa *syscall* `read()` pada ujung baca *pipe* (`pipefd[0]`) tidak pernah mengembalikan nilai `0` (EOF) pada proses anak?
    2. Analisislah distribusi *file descriptor* pada tabel sistem kernel Linux untuk membuktikan komponen mana yang masih menahan *write-end* dari *pipe* tersebut.
    3. Rancang protokol penutupan *file descriptor* yang benar pada proses *parent* dan *child* segera setelah proses *forking* dieksekusi.

### Skenario C: File Corruption pada Multi-Process Shared Log File
Sebuah sistem *microservice* yang diorkestrasi dalam satu host Linux terdiri dari 8 proses terpisah yang menulis *event audit log* ke file log terpusat `/var/log/audit.log`. Tim QA menemukan bahwa pada beban *concurrency* tinggi, baris log berukuran besar (> 8 KB) sering kali tumpang tindih (*interleaved/corrupted*), di mana potongan baris dari Proses A muncul di tengah-tengah potongan baris dari Proses B, meskipun semua proses membuka file dengan mode `open("/var/log/audit.log", O_WRONLY | O_CREAT | O_APPEND, 0644)`.

*   **Pertanyaan Diagnostik:**
    1. Mengapa flag `O_APPEND` gagal menjamin penulisan log yang utuh (*interleaving failure*) ketika ukuran payload data melampaui batasan tertentu? Batasan arsitektural apa (`PIPE_BUF`, ukuran sektor disk, atau *filesystem block size*) yang mengatur atomisitas operasi `write()` pada Linux?
    2. Mengapa penggunaan POSIX File Locking (`fcntl` advisory locking) menjadi suboptimal atau berbahaya jika salah satu proses mengalami *crash* mendadak saat memegang *lock*?
    3. Rekomendasikan perbaikan arsitektur penulisan data performa tinggi agar data audit berukuran variatif dijamin tidak rusak dan bebas *race condition*.

---

## 4. Chapter Challenge

**Tantangan Praktis: High-Performance, Crash-Resilient Write-Ahead Log (WAL) Processor**

### Problem Statement
Anda ditugaskan merancang modul inti *storage engine* bernama `wal_writer`: sebuah sistem pencatatan transaksi Write-Ahead Log (WAL) berbasis C murni yang beroperasi langsung di atas *POSIX low-level system calls*. Modul ini harus menangani penulisan transaksi berkecepatan tinggi, kebal terhadap *abrupt crash* (misalnya `SIGKILL` atau pemutusan daya listrik), tidak menimbulkan kebocoran *file descriptor* pada kondisi *multithreading*, dan memiliki mekanisme *recovery* untuk mendeteksi *partial writes* / *torn pages*.

### Requirements
1. **Inisialisasi & Keamanan FD:**
   - Modul harus membuka atau membuat file log dengan flag yang menjamin eksekusi atomik: penulisan di akhir file, isolasi eksekusi dari child process (`O_CLOEXEC`), dan proteksi akses berkas (`0600`).
2. **Struktur Paket Transaksi (Frame):**
   Setiap transaksi yang ditulis harus dibungkus dalam *binary frame* yang terdefinisi rapi:
   - `uint32_t magic;` (0x57414C52 / "WALR")
   - `uint64_t lsn;` (Log Sequence Number, inkremental monotonik)
   - `uint32_t payload_len;` (Panjang data transaksi)
   - `uint32_t crc32;` (Checksum header + payload untuk deteksi korupsi)
   - `uint8_t payload[];` (Flexible array member berisi data transaksi)
3. **Engine Routines:**
   - `int wal_init(const char *filepath, wal_t *wal);`
   - `int wal_append(wal_t *wal, const void *data, size_t len);`
   - `int wal_sync(wal_t *wal, bool data_only);`
   - `int wal_recover(const char *filepath, wal_scan_cb callback, void *arg);`
   - `void wal_close(wal_t *wal);`
4. **Resiliensi I/O & Non-blocking Safety:**
   - Implementasikan *robust write loop* yang secara eksplisit menangani *partial writes* dan *interrupted syscalls* (`EINTR`).
   - Gunakan `fdatasync()` pada `wal_sync()` jika flag `data_only == true` untuk menghindari mutasi metadata yang tidak esensial.
5. **Recovery Engine:**
   - Fungsi `wal_recover()` harus membaca WAL dari awal hingga akhir, memvalidasi integritas `magic`, `lsn`, dan `crc32`. Jika ditemukan rekaman yang tidak utuh atau korup (*torn write* akibat crash sistem saat penulisan berlangsung), *recovery* harus memotong (*truncate*) file tepat di akhir transaksi valid terakhir menggunakan `ftruncate()`, sehingga status file log kembali konsisten.

### Constraints
- Dilarang keras menggunakan fungsi dari `<stdio.h>` (`fopen`, `fwrite`, `fprintf`, dll.). Seluruh operasi disk WAJIB menggunakan POSIX syscalls: `open`, `read`, `write`, `close`, `lseek`, `ftruncate`, `fdatasync`/`fsync`.
- Standar C: C11 dengan POSIX.1-2008 compliance flag (`-D_POSIX_C_SOURCE=200809L`).
- Kode harus terhindar dari *undefined behavior*, *memory leak* (diverifikasi via Valgrind), dan harus dapat mengompilasi dengan flag ketat: `-Wall -Wextra -Werror -pedantic`.

### Expected Output
Program penguji (driver) harus memvalidasi:
1. Penulisan 10.000 frame transaksi berjalan sukses tanpa kesalahan I/O.
2. Simulasi injeksi kegagalan: Merusak 8 byte terakhir dari file WAL secara sengaja untuk menyimulasikan *torn write*.
3. Pemanggilan `wal_recover()` berhasil mendeteksi transaksi korup tersebut, membuang frame rusak via `ftruncate()`, dan mencetak log transaksi yang berhasil diselamatkan dengan total LSN yang valid.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Anatomi pemanggilan *syscall* dan perbedaannya dengan pemanggilan *library function* biasa (transisi register, *trap/sysenter*, elevasi ke *ring 0*).
- [ ] Mengapa *file descriptor* hanyalah indeks bertipe *integer non-negatif* pada tabel proses lokal dan bagaimana ia menunjuk ke *System-Wide Open File Description*.
- [ ] Semantik *low-level flags*: perbedaan mutlak antara `O_SYNC`, `O_DSYNC`, `O_RSYNC`, `O_DIRECT`, `O_NONBLOCK`, dan `O_CLOEXEC`.
- [ ] Mekanisme kerja Kernel Linux *Page Cache*, proses flushing oleh kernel thread (`pdflush`/`flush`/`kswapd`), dan alasan mengapa `write()` sukses bukan berarti data telah persisten di media fisik (NAND/Platter).
- [ ] Implikasi arsitektural penggunaan `pread()` dan `pwrite()` pada program multithreaded (independensi terhadap pergeseran kursor internal proses).
- [ ] Batasan atomisitas `O_APPEND` dan faktor ukuran buffer disk / batas paging kernel pada operasi penulisan konkuren.

### Saya tidak perlu menghafal:
- [ ] Nilai numerik integer spesifik dari syscall (misalnya nomor syscall x86_64 untuk `sys_read` adalah 0, `sys_write` adalah 1). Cukup gunakan wrapper `<unistd.h>`.
- [ ] Struktur internal tepat dari `struct inode` atau `struct file` pada kernel Linux tertentu (struktur internal kernel ini bervariasi antar-versi).
- [ ] Algoritma CRC32 internal secara matematis (dapat menggunakan implementasi referensi tabel atau pustaka standar).

### Saya harus bisa melakukan:
- [ ] Mengimplementasikan *robust I/O loop* untuk membaca (`read`) dan menulis (`write`) buffer secara lengkap dengan penanganan *short count* dan evaluasi `errno` (`EINTR`, `EAGAIN`, `EWOULDBLOCK`).
- [ ] Melakukan debugging proses I/O Linux yang macet menggunakan `strace -p <pid> -e trace=read,write,open,close -T -tt`.
- [ ] Menginspeksi status *file descriptor*, posisi *offset*, dan *flags* suatu proses secara langsung melalui filesystem `/proc/<pid>/fd/` dan `/proc/<pid>/fdinfo/`.
- [ ] Menggunakan `dup2()` atau `fcntl()` untuk melakukan I/O *redirection* secara aman dan memanipulasi *file descriptor flags* secara terisolasi.
- [ ] Menganalisis dan memperbaiki masalah kebocoran FD (*FD leaks*) menggunakan kombinasi `lsof -p <pid>` dan instrumentasi kode internal.