# BAB 04: Quiz, Challenge, & Knowledge Check
**Resource Management & Low-Level I/O**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Siklus Hidup File Descriptor dan GC Finalization
Jelaskan secara mendalam mengapa mengandalkan Garbage Collector (GC) dan mekanisme *finalizer* bawaan Ruby untuk menutup file descriptor (`IO#close`) dikategorikan sebagai *architectural anti-pattern* yang fatal pada aplikasi *high-throughput*. Mengapa konstruksi blok `File.open(path, mode) { |fh| ... }` menjamin determinisme yang tidak bisa diberikan oleh siklus hidup objek CRuby biasa?

### Soal 1.2: Userspace Buffering vs Direct System Calls
Bandingkan arsitektur kerja antara metode standard I/O (`IO#read`, `IO#write`) dengan metode *system-level* unbuffered (`IO#sysread`, `IO#syswrite`) pada CRuby. Apa bahaya teknis (*data corruption*, *state de-synchronization*) yang timbul jika kedua kelompok metode ini dieksekusi secara bergantian pada stream `IO` yang sama?

### Soal 1.3: Semantik Buffering dan Deteksi TTY
Secara *default*, Ruby menerapkan strategi *buffering* yang berbeda bergantung pada target stream. Jelaskan perbedaan perilaku antara *fully-buffered*, *line-buffered*, dan *unbuffered*. Bagaimana Ruby mendeteksi apakah suatu IO terhubung ke Terminal Interaktif (TTY) atau dialihkan (*redirected*) ke berkas/pipa (*pipe*), dan apa implikasi pengubahan `$stdout.sync = true` terhadap performa *throughput* kernel?

### Soal 1.4: Integritas Data Persisten: `flush` vs `fsync` vs `fdatasync`
Uraikan batasan teknis dari method `IO#flush`. Di lapisan abstraksi mana (Ruby runtime, C-runtime/glibc, OS page cache, storage hardware) `IO#flush` berhenti bekerja? Bandingkan fungsinya dengan POSIX system call `IO#fsync` dan `IO#fdatasync` dalam konteks durabilitas data (ACID *guarantees*) ketika terjadi *kernel panic* atau *power loss*.

### Soal 1.5: Mekanisme Advisory Locking via `flock`
Bagaimana cara kerja file locking menggunakan `File#flock` (`File::LOCK_EX`, `File::LOCK_SH`, `File::LOCK_NB`)? Jelaskan mengapa locking ini disebut *advisory* ketimbang *mandatory*, serta sebutkan keterbatasan teknisnya saat dieksekusi di atas sistem berkas terdistribusi (*Network File Systems* / NFS) atau pada arsitektur multithreaded dalam satu proses Ruby yang sama.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Non-Blocking I/O dan Mitigasi Overhead Alokasi Objek
Pada implementasi *event loop* kustom berbasis `IO#read_nonblock` dan `IO#write_nonblock`, pendekatan konvensional menangkap *exception* `IO::WaitReadable` atau `IO::WaitWritable`. Mengapa pendekatan berbasis *exception handling* ini memicu penurunan performa CPU drastis (*GC pressure*) di bawah beban I/O tinggi, dan bagaimana penggunaan parameter `exception: false` mengubah alur eksekusi serta memori footprint?

### Soal 2.2: Diagnostik `Errno::EMFILE` vs `Errno::ENFILE`
Dalam insiden produksi, aplikasi Ruby Anda memuntahkan *exception* I/O. Bedakan secara presisi akar penyebab sistemik antara `Errno::EMFILE` dan `Errno::ENFILE`. Tuliskan langkah investigasi level OS menggunakan antarmuka `/proc` Linux dan CLI (`ulimit`, `lsof`, `sysctl`) untuk menentukan apakah kebocoran terjadi pada alokasi per-proses atau batas global kernel.

### Soal 2.3: File Descriptor Inheritance dan Flag `O_CLOEXEC`
Saat proses Ruby melakukan `Process.fork` atau mengeksekusi sub-proses (`Kernel#spawn`, `Kernel#system`), semua *open file descriptors* secara *default* dapat diwariskan ke *child process*. Jelaskan resiko keamanan (*descriptor leaking*) dan kehabisan port/file yang diakibatkannya. Bagaimana konstanta `File::CLOEXEC` atau method `IO#close_on_exec=` memitigasi anomali ini pada level POSIX?

### Soal 2.4: Struktur `rb_io_t` dan GVL Release pada Operasi I/O
Berdasarkan implementasi internal CRuby, struktur C apa yang membungkus objek `IO` (`rb_io_t`)? Jelaskan bagaimana CRuby mengelola pelepasan Global VM Lock (GVL) saat operasi I/O pemblokir (*blocking system call*) dipanggil via `rb_thread_call_without_gvl`, dan apa yang terjadi jika sebuah thread Ruby mencoba memanggil `IO#close` dari thread lain terhadap deskriptor yang sedang diblokir tersebut.

### Soal 2.5: I/O Multiplexing: Keterbatasan `IO.select` vs Fiber Scheduler
Analisis kelemahan struktural metode `IO.select` (yang bertumpu pada POSIX `select(2)`) terkait batasan nilai deskriptor `FD_SETSIZE` (biasanya 1024) dan kompleksitas algoritma $\mathcal{O}(N)$. Bandingkan arsitektur ini dengan mekanisme Ruby 3+ *Fiber Scheduler* (`io_uring`, `epoll`, atau `kqueue`) dalam menangani konkurensi $100.000$ koneksi secara transparan tanpa mengubah gaya kode sinkron.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Exhaustion File Descriptor pada High-Throughput Webhook Ingestion Service
*Konteks*: Sebuah microservice Ruby (Puma, multi-threaded) menerima 8.000 webhook/detik. Setiap webhook diparsing, lalu dituliskan ke file log audit lokal dan diteruskan ke upstream API via HTTP client. Setelah berjalan stabil selama 4 jam, server mendadak lumpuh total dengan cascade error:
`Errno::EMFILE: Too many open files - accept(2)`
Puma tidak lagi dapat menerima koneksi TCP baru. Pengecekan awal menunjukkan `ulimit -n` proses telah diatur ke `65535`.
*   **Pertanyaan Diagnostik**:
    1. Mengapa Puma menolak koneksi pada tahap `accept(2)` ketika limit file descriptor tercapai?
    2. Bagaimana Anda merancang skrip investigasi diagnostik cepat untuk memverifikasi apakah kebocoran deskriptor (*FD leak*) berasal dari penulisan log lokal, koneksi HTTP client (socket pool leak), atau penanganan file sementara (*Tempfile*) yang tidak terunlink?
    3. Apa langkah mitigasi arsitektur di level Ruby runtime untuk mencegah instansiasi deskriptor melebihi ambang batas aman tanpa menumbangkan seluruh proses?

### Skenario B: Race Condition dan File Corruption pada Multi-Worker Shared Log File
*Konteks*: Sekelompok worker proses Ruby terpisah (8 worker hasil `fork` dari master process) menulis metrik metrik agregasi langsung ke satu file bersama (`/var/log/app_metrics.log`) menggunakan mode append (`File.open("...", "a")`). Pada load tinggi, tim data engineering mendapati bahwa beberapa baris metrik saling bertumpuk (*interleaved lines*), format JSON terpotong di tengah jalan, dan berkas sesekali mengalami *null-byte corruption*.
*   **Pertanyaan Diagnostik**:
    1. Mengapa flag `O_APPEND` dari POSIX tidak menjamin atomisitas penulisan data jika operasi `write` melampaui ukuran tertentu (`PIPE_BUF` atau batasan I/O buffer kernel)?
    2. Mengapa penggunaan `IO#write` standar memperparah masalah *interleaving* ini dibandingkan menggunakan direct system call `IO#syswrite`?
    3. Rancang strategi locking non-blocking atau arsitektur substitusi (misal: domain socket pipe / dedicated logging actor) agar proses penulisan thread-safe dan process-safe dengan penalti performa seminimal mungkin.

### Skenario C: Bottleneck Memory Leak pada Ekspor Berkas Data Raksasa
*Konteks*: Layanan pelaporan mengekspor data transaksi database ke file CSV raksasa (ukuran berkisar antara 15 GB hingga 50 GB) langsung ke disk mount penyimpanan jaringan (NFS/EFS). Implementasi saat ini menggunakan blok iterasi:
```ruby
File.open("export.csv", "w") do |file|
  Transaction.find_each(batch_size: 5000) do |trx|
    file.write(trx.to_csv_line)
  end
end
```
Server mengalami degradasi performa drastis: Resident Set Size (RSS) memori Ruby membengkak hingga puluhan gigabyte sampai proses dihentikan oleh OS OOM Killer (*Out Of Memory*). Selain itu, latensi penulisan ke network mount menyebabkan penumpukan thread.
*   **Pertanyaan Diagnostik**:
    1. Mengapa memori RSS membengkak padahal data dibaca menggunakan batching database (`find_each`) dan ditulis baris per baris? Jelaskan peran internal Ruby IO buffer dan OS Dirty Pages dalam kasus ini.
    2. Bagaimana network latency pada disk mount memicu *backpressure* ke dalam alokasi objek Ruby di heap?
    3. Rekonstruksi implementasi ekspor data tersebut menggunakan pendekatan *low-level I/O streaming* yang menerapkan *bounded buffer*, pelepasan memori string agresif, dan kontrol *flush/fsync* adaptif agar RSS memori stabil di bawah 150 MB.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Resilient Binary Stream Chunk-Rotator Engine

#### Problem Statement
Anda ditugaskan membangun komponen core *Data Ingestion Engine* bertingkat rendah (*low-level*) tanpa framework eksternal. Engine ini harus membaca *stream* biner masukan tak berhingga (*unbounded binary stream*, disimulasikan dari `STDIN` atau Named Pipe/FIFO), memvalidasi integritas setiap frame data, dan memecahnya ke dalam berkas-berkas *chunk* berukuran tepat $64\text{ MiB}$ pada disk. Engine harus tahan terhadap *crash*, kebal terhadap kebocoran file descriptor, dan zero-allocation pada main read loop.

#### Requirements
1. **Unbuffered POSIX Operations**: Seluruh pembacaan dari input stream dan penulisan ke berkas chunk wajib menggunakan `IO#sysread` dan `IO#syswrite` (atau `IO.sysopen` & `IO.new`). Dilarang keras menggunakan `puts`, `print`, `readline`, atau `write` terbuffer standar.
2. **Deterministic Resource Management**: 
   - Berkas chunk saat ini harus ditutup seketika saat mencapai tepat $64\text{ MiB}$ ($67.108.864$ bytes) atau saat stream input mencapai EOF.
   - Rotasi berkas harus menjamin *durabilitas*: panggil `IO#fdatasync` sebelum berkas ditutup dan diberi nama final (skema *atomic rename*: tulis ke `.tmp`, sync, rename ke `.dat`).
3. **Zero Heap Allocation Loop**: 
   - Gunakan *mutable static buffer* yang dialokasikan satu kali sebelum loop (`String.new(capacity: 64 * 1024)` dengan `encoding: Encoding::BINARY`).
   - Gunakan signature `IO#sysread(maxlen, out_buffer)` untuk menulis langsung ke buffer memori yang sudah ada guna memangkas alokasi objek GC menjadi nol di hot path.
4. **Signal & Exception Safety**:
   - Tangani sinyal sistem `SIGINT` dan `SIGTERM` secara graceful: tutup chunk yang sedang aktif secara deterministik (sync -> rename) sebelum proses shutdown.
   - Pastikan bila terjadi error I/O (`Errno::EIO`, `Errno::ENOSPC`), file descriptor target di-close pada blok `ensure` tanpa meninggalkan dangling descriptor.

#### Constraints
- Ruby standard library murni (`IO`, `File`, `Process`, `Signal`).
- Dilarang menggunakan *gem* pihak ketiga apapun.
- Batas konsumsi memori alokasi proses (RSS) tidak boleh bertambah lebih dari $20\text{ MB}$ di atas base footprint Ruby, terlepas dari total terabyte data yang diproses.

#### Expected Output
Implementasikan dalam bentuk file executable tunggal `stream_rotator.rb` yang menyertakan logging internal ke `STDERR` (unbuffered) dengan format:
```text
[METRIC] Chunk rotated: chunk_000001.dat | Bytes: 67108864 | Duration: 0.412s | Syscalls: 1024
[METRIC] Chunk rotated: chunk_000002.dat | Bytes: 67108864 | Duration: 0.398s | Syscalls: 1024
[SIGNAL] SIGTERM received. Gracefully finalizing chunk_000003.tmp...
[METRIC] Final chunk flushed: chunk_000003.dat | Bytes: 14208120
[SYSTEM] Engine stopped gracefully. Total FD open: 0. Zero leaks detected.
```

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Arsitektur internal representasi I/O di CRuby (`rb_io_t`) dan relasinya dengan POSIX File Descriptors integer dari Kernel OS.
- [ ] Dampak pelepasan Global VM Lock (GVL) saat pemanggilan blocking I/O dan konsekuensi thread safety-nya.
- [ ] Perbedaan multi-layer buffering: Ruby Application Buffer -> C stdio Buffer -> Kernel Page Cache -> Storage Controller Cache.
- [ ] Mengapa *advisory locking* (`flock`) tidak menghentikan proses eksternal yang tidak kooperatif (*non-locking process*).
- [ ] Transisi status file descriptor non-blocking (`O_NONBLOCK`) dan penanganan *edge-triggered* vs *level-triggered* readiness notification.
- [ ] Mekanisme pembersihan memori OS vs Ruby Heap saat file descriptor ditutup (`close(2)`).

### Saya tidak perlu menghafal:
- [ ] Nilai integer pasti dari kode POSIX error constants (misal: `Errno::EMFILE::Errno` bernilai 24 pada Linux x86_64); cukup pahami nama simbolik dan semantiknya.
- [ ] Struktur data C internal dari `glibc` `FILE` pointer.
- [ ] Bitmask hexa spesifik untuk flag `fcntl` tingkat rendah (misal: nilai numerik bit `O_RDWR | O_CREAT`); gunakan konstanta representatif `File::RDWR`, `File::CREAT`.

### Saya harus bisa melakukan:
- [ ] Mengonfigurasi strategi buffering stream (`IO#sync=`) secara tepat sesuai kebutuhan determinisme vs performa throughput.
- [ ] Menulis operasi pembacaan dan penulisan berkas bebas alokasi objek GC menggunakan `sysread(size, buffer)` dan `syswrite`.
- [ ] Melacak dan men-debug kebocoran file descriptor pada live process menggunakan integrasi `/proc/<pid>/fd`, `lsof`, dan `ObjectSpace`.
- [ ] Mengimplementasikan *atomic file writing* menggunakan kombinasi POSIX write, `fsync`/`fdatasync`, dan `File.rename` untuk eliminasi resiko *file corruption*.
- [ ] Memanfaatkan non-blocking primitives (`read_nonblock`, `write_nonblock`) dengan argumen `exception: false` untuk membangun komponen reaktif berkinerja tinggi.