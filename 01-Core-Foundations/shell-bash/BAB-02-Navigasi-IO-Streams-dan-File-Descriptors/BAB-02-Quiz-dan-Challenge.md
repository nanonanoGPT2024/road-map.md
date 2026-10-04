# BAB 02: Quiz, Challenge, & Knowledge Check
**Navigasi, I/O Streams, & File Descriptors**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Mekanisme Kernel Redirection (`dup2`) dan Urutan Evaluasi**  
   Jelaskan secara mendalam mengapa perintah `command > file.txt 2>&1` menghasilkan output yang berbeda secara fundamental dibandingkan `command 2>&1 > file.txt`. Kaitkan jawaban Anda dengan pemanggilan *system call* `dup2(oldfd, newfd)`, mutasi pointer pada *Process File Descriptor Table*, dan referensi ke *Open File Description* di kernel space.

2. **Resolusi Pathing: Logical Path (`cd -L`) vs Physical Path (`cd -P`)**  
   Ketika Anda menavigasi struktur direktori yang memiliki banyak symlink, bagaimana shell melacak posisi Anda saat ini? Jelaskan perbedaan implementasi internal antara variabel `PWD`, *system call* `chdir()`, dan `getcwd()`. Apa risiko operasional saat mengeksekusi skrip otomatisasi infrastruktur yang mengandalkan jalur logis (`-L`) di atas *distributed file system* atau *nested symlink tree*?

3. **Struktur Data Kernel I/O: Process FD Table, Open File Table, & Inode Table**  
   Gambarkan dan jelaskan relasi *three-tier architecture* penanganan file di Linux:
   - *Process File Descriptor Table* (per-process)
   - *System-wide Open File Table* (global)
   - *Inode Table* (global/filesystem level)  
   Bagaimana flag file (seperti `O_APPEND`) dan *file offset pointer* dibagikan ketika sebuah child process diciptakan melalui `fork()`?

4. **Karakteristik I/O Pseudo-Devices: `/dev/null`, `/dev/zero`, dan `/dev/urandom`**  
   Dari perspektif driver kernel dan implementasi virtual *VFS (Virtual File System)*:
   - Bagaimana kernel menangani operasi `write()` pada file descriptor yang mengarah ke `/dev/null`?
   - Mengapa pembacaan tanpa limit dari `/dev/zero` memicu CPU bound pada proses yang mengonsumsinya, sedangkan membaca dari `/dev/urandom` memiliki bottleneck yang berbeda?

5. **Here-Doc (`<<`), Here-String (`<<<`), vs Process Substitution (`<(...)`)**  
   Bedah mekanisme alokasi File Descriptor dan medium I/O (apakah anonymous pipe, temporary unlinked file, atau named pipe/FIFO) yang digunakan Bash ketika mengevaluasi:
   - `cat <<EOF`
   - `cat <<< "string"`
   - `cat <(command)`  
   Manakah di antara ketiganya yang menghasilkan subshell independen, dan bagaimana dampaknya terhadap performa jika dieksekusi di dalam loop frekuensi tinggi?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Diagnostik Ghost Disk Space & Leaked Descriptors**  
   Sebuah server database kehabisan ruang disk (`No space left on device`), namun perintah `du -sh /var/log` menunjukkan ukuran direktori sangat kecil. `lsof +L1` mengonfirmasi adanya file log berukuran ratusan gigabyte dengan status `(deleted)` yang masih dipegang oleh PID daemon aktif.  
   Jelaskan mengapa disk blocks belum dilepas oleh filesystem (*ext4/xfs*). Tanpa merestart proses daemon atau menyebabkan crash aplikasi, bagaimana Anda menggunakan manipulasi `/proc/$PID/fd/` dan redirection I/O untuk mengosongkan *space* disk seketika?

2. **Buffering Boundary & Pipeline Deadlock**  
   Mengapa *pipeline* berikut sering kali gagal menampilkan data secara real-time atau mengalami *stalling* (hang):
   ```bash
   tail -f /var/log/traffic.log | grep "500" | awk '{print $7}' > alert.log
   ```
   Jelaskan perbedaan mekanika *unbuffered*, *line-buffered*, dan *fully-buffered* pada pustaka GNU C (`glibc`). Bagaimana modifikasi pipeline tersebut menggunakan `stdbuf`, `unbuffer`, atau opsi utilitas terkait agar I/O stream ter-flush secara instan?

3. **Manajemen Custom File Descriptors (FD 3 sampai 9+) dan Flag `O_CLOEXEC`**  
   Analisis blok kode berikut:
   ```bash
   exec 3< /path/to/data.csv
   exec 4> /path/to/output.log
   ./run_external_binary
   exec 3<&-
   exec 4>&-
   ```
   Apa yang terjadi pada FD 3 dan FD 4 ketika binary eksternal dijalankan melalui `execve()`? Mengapa leaking file descriptor ke child process berbahaya dalam arsitektur privilege separation, dan bagaimana Anda memastikan FD ditutup secara deterministik saat eksekusi sub-proses?

4. **Siklus Hidup Subshell pada Pipeline vs Read Loop FD Injection**  
   Bandingkan dua pola iterasi stream berikut:
   ```bash
   # Pola A
   cat massive_data.txt | while IFS= read -r line; do
       ((count++))
   done
   echo "Total: $count"

   # Pola B
   while IFS= read -r line; do
       ((count++))
   done < massive_data.txt
   echo "Total: $count"
   ```
   Jelaskan secara presisi mengapa Pola A mencetak nilai kosong/nol, sedangkan Pola B mencetak nilai yang benar. Apa yang terjadi jika di dalam loop Pola B terdapat perintah `ssh user@node 'uptime'` yang dijalankan tanpa penyesuaian File Descriptor?

5. **Exhaustion Handling: `EMFILE` vs `ENFILE`**  
   Ketika aplikasi backend mengalami error `Too many open files`:
   - Bagaimana Anda membedakan apakah sistem terbentur limit per-proses (`EMFILE`) atau limit global kernel (`ENFILE`)?
   - Sebutkan parameter kernel (`sysctl`), konfigurasi PAM/limits, dan file di `/proc` yang harus diinvestigasi untuk mendeteksi leak FD secara presisi.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Production Outage Akibat Sync I/O Blockage pada Batch Ingestion
*Konteks Sistem:*  
Sebuah skrip otomatisasi data ingestion skala terabyte dijalankan setiap malam di server produksi. Skrip tersebut memproses ribuan file menggunakan pipeline:
```bash
./processor_binary input.raw 2>&1 | tee -a /mnt/nfs/logs/ingest.log
```
*Insiden:*  
Storage NFS mengalami lonjakan latensi tinggi (packet drops). Server secara tiba-tiba mengalami *load average spike* melebihi 200, dan prosesor binary berhenti memproses data padahal CPU dan RAM server lokal masih di bawah 20%.

*Pertanyaan Diagnostik:*
1. Mengapa *failure* pada target log NFS mampu memblokir eksekusi `./processor_binary` padahal proses tersebut sedang mengkalkulasi data di memory lokal? Jelaskan perambatan *blocking I/O backpressure* melalui anonymous pipe buffer (kapasitas default 64KB pada Linux).
2. Rancang ulang arsitektur pipeline tersebut menggunakan File Descriptor khusus, manipulasi *asynchronous non-blocking redirection*, atau *buffering isolation* agar logging ke NFS tidak memiliki kemampuan untuk memblokir laju pemrosesan utama data binary, serta memastikan output log tetap mencatat `stdout` dan `stderr` secara akurat.

---

### Skenario B: Race Condition dan File Corruption pada Konkurensi Append (`>>`)
*Konteks Sistem:*  
Delapan (8) worker bash script dijalankan secara paralel melalui background process (`&`) untuk mengekstrak metrik dan menulis hasilnya secara bersamaan ke satu file sentral:
```bash
# Dieksekusi secara konkuren oleh 8 instance
gather_metrics | parse_engine >> /var/log/metrics_consolidated.log &
```
*Insiden:*  
Saat volume throughput metrik meningkat, ditemukan baris-baris log yang terputus di tengah, baris yang saling menimpa (*interleaving corruption*), dan data yang hilang secara permanen. File system yang digunakan adalah lokal `ext4`.

*Pertanyaan Diagnostik:*
1. Secara teknis, apakah system call `write()` dengan flag `O_APPEND` selalu menjamin atomisitas data? Berapa batas ukuran buffer (`PIPE_BUF` vs `POSIX write limit`) di Linux yang menjamin sebuah write block tidak akan terpecah (*interleaved*) saat banyak proses menulis ke satu file descriptor secara konkuren?
2. Bagaimana Anda mendesain solusi bebas korupsi untuk kasus di atas tanpa menggunakan DBMS eksternal? Jelaskan pendekatan menggunakan:
   - Dedicated File Locking (`flock` pada specific FD).
   - Dedicated FIFO / Named Pipe multiplexer pattern.

---

### Skenario C: Arsitektur Zero-Dependency Network Telemetry via `/dev/tcp`
*Konteks Sistem:*  
Di sebuah lingkungan *hardened minimalist container* (distroless / recovery container), tidak terdapat binary `curl`, `wget`, `nc`, ataupun `python`. Anda bertugas melakukan diagnostik socket dan pengiriman telemetry crash-dump ke server metrik via protokol HTTP/TCP secara native.

*Pertanyaan Diagnostik:*
1. Jelaskan bagaimana mekanisme Bash mengabstraksi `/dev/tcp/HOST/PORT` menggunakan kernel network system calls (`socket`, `connect`). Mengapa `/dev/tcp` bukan merupakan file nyata yang berada di direktori `/dev` Linux?
2. Susun arsitektur skrip menggunakan *bidirectional custom file descriptor* (misal FD 3) yang:
   - Membuka koneksi TCP dua arah ke host target.
   - Mengirimkan raw HTTP/1.1 POST payload.
   - Membaca dan mem-parsing status line respons HTTP secara streaming tanpa memblokir skrip secara permanen jika server tidak menutup koneksi (*hanging connection*).
   - Menutup FD dengan benar (*clean teardown*).

---

## 4. Chapter Challenge

### Tantangan Praktis: Multi-Stream Engine dengan Isolasi Fault & Hot-Truncation

#### Deskripsi Masalah
Anda ditugaskan merancang sebuah framework wrapper I/O enterprise bernama `stream_guard.sh`. Utilitas ini harus mengeksekusi sub-proses penghasil stream I/O yang masif dan tidak stabil, mendistribusikan alirannya ke berbagai target secara deterministik, tahan terhadap masalah disk latency, serta menyediakan kontrol inspeksi runtime tanpa dependensi eksternal selain Coreutils dan Bash bawaan.

#### Requirements
1. **Pemisahan Stream 3-Arah (Tri-Stream Separation):**
   - Skrip harus mengeksekusi sebuah target command.
   - `stdout` dialirkan ke file `output.log` DAN ditampilkan ke terminal secara unbuffered.
   - `stderr` harus dipisahkan sepenuhnya; dialirkan ke file `error.log` DAN secara simultan dialirkan melalui sub-filter real-time yang langsung mencetak alert bertuliskan `"[CRITICAL-ALERT] <isi error>"` ke layar konsol secara instan jika menemukan keyword `FATAL` atau `PANIC`.
   - File log tidak boleh tercampur (tidak boleh ada data `stdout` di dalam `error.log` dan sebaliknya).

2. **Custom File Descriptors Allocation:**
   - Framework dilarang keras menimpa FD standar (0, 1, 2) di parent script shell. Seluruh manipulasi rute harus dikelola via custom FDs (alokasikan minimal FD `3`, `4`, dan `5`).
   - Sediakan mekanisme pelepasan (closing) FD secara bersih (`exec X>&-`) ketika proses selesai atau tertangkap sinyal abort (`SIGINT`, `SIGTERM`).

3. **Zero-Lock Truncation Ready:**
   - Framework harus mendukung fungsionalitas di mana `output.log` dapat dipangkas (di-truncate menjadi 0 bytes) dari luar secara aman saat proses masih berjalan, dan proses tersebut harus terus menulis log mulai dari byte ke-0 baru tanpa perlu me-restart proses pembungkus.

4. **Kemandirian Lingkungan (Zero External Tools):**
   - Tidak boleh menggunakan `named pipes` (FIFO) yang tertinggal di filesystem; jika anonymous pipe atau FIFO digunakan, harus dijamin *auto-cleanup* di `/tmp` dengan trapping signal.

#### Constraints
- Shell: GNU Bash versi $\ge 4.4$.
- Dilarang menginstal *third-party binaries* (`moreutils`, `daemonize`, dsb).
- Harus menangani edge-case `SIGPIPE` secara elegan; matinya target penampung stream tidak boleh men-terminate aplikasi target secara prematur kecuali diinstruksikan.

#### Expected Output
Script modular siap pakai:
```bash
./stream_guard.sh --exec "./data_generator_dummy.sh" --out /var/log/app.out --err /var/log/app.err
```
Verifikasi keberhasilan:
- Terminal menampilkan output normal dan alert bertag `[CRITICAL-ALERT]` seketika saat pola error terdeteksi.
- `wc -l /var/log/app.out` dan `wc -l /var/log/app.err` menunjukkan isolasi presisi data 100%.
- Menjalankan `truncate -s 0 /var/log/app.out` tidak merusak penulisan file, data baru langsung tertulis tanpa memory leak atau error I/O.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Mekanisme pemanggilan *system call* `dup2()` dan resolusi sekuensial File Descriptor dari kiri ke kanan pada interpreter Bash.
- [ ] Hubungan internal antara File Descriptor tabel per-proses, Open File Description tabel kernel, dan Inode filesystem, termasuk implikasi flag `O_APPEND` dan file pointer sharing pasca-`fork()`.
- [ ] Perbedaan fundamental antara buffering I/O di tingkat kernel (pipe buffer) versus buffering di userspace (`glibc` streams: unbuffered, line-buffered, block-buffered).

### Saya tidak perlu menghafal:
- [ ] Nilai angka konstanta integer spesifik untuk *syscall numbers* kernel Linux (misalnya nomor integer eksak dari `sys_dup2` atau `sys_write` pada tabel arsitektur x86_64).
- [ ] Setiap variasi *implementation detail* parsing internal binary utility non-standar di luar spesifikasi POSIX/GNU.

### Saya harus bisa melakukan:
- [ ] Mengonstruksi perutean File Descriptor kompleks (membuka, menduplikasi, memindahkan, dan menutup FD arbitrary $\ge 3$) menggunakan sintaks `exec`.
- [ ] Mendiagnosis dan memperbaiki disk space yang terkunci oleh proses yang memegang *deleted file descriptor* via antarmuka `/proc/$PID/fd/` secara non-disruptif.
- [ ] Menyusun pipeline data real-time bebas deadlock dengan manajemen isolasi buffer yang tepat menggunakan `stdbuf` atau teknik FD redirection native.