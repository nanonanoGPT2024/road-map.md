# BAB 02: Quiz, Challenge, & Knowledge Check
**Manajemen Shell, Stream I/O, dan Otomasi Bash Lanjutan**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Anatomi File Descriptor & Urutan Evaluasi Redirection:**
   Jelaskan perbedaan mendasar pada level kernel VFS (*Virtual File System*) antara sintaks `command > output.txt 2>&1` dengan `command 2>&1 > output.txt`. Mengapa urutan token parser Bash pada kedua perintah tersebut menghasilkan status stream `stderr` yang sepenuhnya berbeda?

2. **Siklus Hidup Subshell dan Pipeline:**
   Pada pipeline `cat access.log | grep "500" | while read -r line; do ((count++)); done; echo "$count"`, mengapa nilai variabel `count` selalu kembali kosong atau bernilai awal (misal: 0) setelah loop selesai? Jelaskan arsitektur *fork-exec*, isolasi *memory space*, dan alokasi *file descriptor* yang mendasari fenomena ini.

3. **Mekanisme Eksekusi `exec` dan Modifikasi Tabel FD:**
   Bagaimana cara kerja perintah `exec 3<> /dev/tcp/127.0.0.1/8080` dan `exec 1>&-` dalam memanipulasi struktur *file descriptor table* dari proses shell yang sedang berjalan tanpa menciptakan *child process* baru?

4. **Dekomposisi Strict Mode `set -euo pipefail`:**
   Analisis secara mendalam apa yang terjadi di internal shell engine ketika setiap flag dalam `set -euo pipefail` diaktifkan:
   - Bagaimana penanganan *exit status* array `${PIPESTATUS[@]}` berubah dengan adanya `-o pipefail`?
   - Mengapa pengecekan variabel kosong (`-u`) dapat memicu terminasi prematur pada parameter opsional, dan bagaimana cara penulisan defensif yang benar untuk memitigasinya?

5. **Substitusi Proses (*Process Substitution*) vs Pipa Bernama (*Named Pipe/FIFO*):**
   Uraikan cara kerja internal Bash saat mengeksekusi sintaks `diff <(command1) <(command2)`. Apa yang sebenarnya dioperasikan di balik layar pada direktori `/dev/fd/` atau `/proc/self/fd/`, dan bagaimana siklus hidup *anonymous pipe* tersebut dikelola hingga terminasi proses?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Standard I/O Buffering Deadlock & Mitigation:**
   Sebuah pipeline pemantauan log `tail -f /var/log/app.log | grep --line-buffered "ERROR" | awk '{print $1, $4}' | while read -r time err; do send_alert "$time" "$err"; done` mengalami *latency* tinggi hingga notifikasi tertunda bermenit-menit meskipun event log terus masuk. Selidiki akar masalahnya berdasarkan mekanisme *block-buffering* vs *line-buffering* pada runtime `glibc`. Mengapa `awk` mengabaikan aliran instan tersebut dan bagaimana utilitas `stdbuf` mengintervensi alokasi buffer via `LD_PRELOAD`?

2. **Signal Trapping dalam Subshell dan Race Condition:**
   Diberikan blok skrip automasi pembersihan resource:
   ```bash
   trap 'rm -f /tmp/lock.pid; exit 1' SIGINT SIGTERM
   long_running_binary &
   wait $!
   ```
   Jika sinyal `SIGINT` (Ctrl+C) dikirimkan tepat saat kernel mentransisikan proses dari `long_running_binary` ke shell wrapper, jelaskan potensi *race condition* yang terjadi pada penanganan trap. Mengapa konstruksi idiomatis Bash memerlukan penanganan khusus pada *exit status* `128 + N` saat menerima sinyal interupsi?

3. **Atomic File Locking Menggunakan `flock`:**
   Mengapa penguncian file berbasis `test -f lockfile || touch lockfile` memiliki kerentanan *Time-of-Check to Time-of-Use* (TOCTOU)? Bandingkan keandalan pendekatan tersebut dengan implementasi *system-call level lock* menggunakan `flock(2)` pada *dedicated file descriptor* (misal: `exec 200>/var/lock/app.lock; flock -n 200`). Apa yang terjadi pada kernel inode lock saat proses wrapper mati secara abnormal (`SIGKILL`)?

4. **Dynamic Descriptors dan Coprocess Communication:**
   Jelaskan arsitektur *two-way asynchronous communication* menggunakan fitur `coproc` di Bash. Bagaimana array file descriptor `${NAME[0]}` (output) dan `${NAME[1]}` (input) dialokasikan? Berikan satu skenario *edge case* di mana pembacaan dari coprocess mengalami *deadlock* akibat ketiadaan karakter *newline* (`\n`) atau penutupan stream EOF yang tidak eksplisit.

5. **Here-Strings, Here-Docs, dan Memory/Disk Offloading:**
   Bandingkan alokasi memori internal dan I/O footprint antara `cat <<EOF`, `cat <<-EOF`, dan `cat <<< "$VARIABLE"`. Pada kondisi apa shell membuat *unlinked temporary file* di direktori `/tmp` untuk menampung payload *here-document*, dan kapan shell modern memilih *pipe descriptor* in-memory?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck I/O pada Batch Processing Skala Besar
Di sebuah kluster perbankan, sebuah skrip agregasi transaksi harian memproses file berukuran 120 GB dengan format CSV. Implementasi awal ditulis sebagai berikut:
```bash
#!/usr/bin/env bash
set -eo pipefail

while IFS=',' read -r id timestamp amount status; do
    if [[ "$status" == "SETTLED" ]]; then
        echo "$id,$amount" >> /mnt/nfs/settled.csv
    fi
done < /mnt/nfs/raw_transactions.csv
```
*Dampak Masalah:* Skrip memakan waktu lebih dari 14 jam untuk selesai, utilisasi CPU sangat rendah (< 5%), tetapi operasi I/O pada NFS storage melonjak tajam dengan ribuan status *I/O wait* (`wa` pada `top`).

**Pertanyaan Diagnostik:**
1. Identifikasi dua faktor kritis pada level sistem operasi dan shell execution loop yang menjadi penyebab utama bottleneck performa di atas!
2. Rancang ulang (tuliskan ulang) arsitektur pemrosesan file tersebut menggunakan paradigma *stream-processing* murni (kombinasi `awk`/`sed`/`cut`), *file descriptor multiplexing*, serta optimasi I/O block buffer agar pipeline selesai dalam hitungan menit tanpa overhead pembukaan/penutupan file descriptor berulang kali ke NFS!

---

### Skenario B: Race Condition dan File Corruption pada Multitenant Daemon
Sebuah cluster worker node menjalankan *cron job* periodik setiap menit secara paralel di bawah 16 proses independen. Seluruh proses bertugas menuliskan ringkasan metrik kesehatan host ke file bersama `/var/log/node_health.json`. Setiap worker mengeksekusi format penulisan:
```bash
# Menghasilkan output JSON
payload=$(collect_metrics)
echo "$payload" >> /var/log/node_health.json
```
*Dampak Masalah:* File log secara acak mengalami korupsi data berupa *interleaved lines* (karakter dari worker A bercampur di tengah-tengah baris worker B) dan sesekali mengalami *zero-byte file truncation*.

**Pertanyaan Diagnostik:**
1. Berdasarkan standar IEEE Std 1003.1 (POSIX) terkait flag `O_APPEND` dan konstanta batasan kernel `PIPE_BUF`, jelaskan mengapa penulisan `echo "$payload" >> file` tidak menjamin integritas atomik saat ukuran payload melebihi threshold tertentu!
2. Rancang solusi arsitektur Bash berbasis *named pipe* (FIFO) tersentralisasi atau implementasi `flock` mutlak pada FD tertentu yang menjamin *zero-data-corruption* dan *non-blocking execution* bagi worker-worker tersebut!

---

### Skenario C: Orphan Process Leak dan Broken Pipe Cascade
Sebuah microservice orchestration script menggunakan Bash untuk mengeksekusi serangkaian pipeline analitik yang mengonsumsi stream Kafka via utilitas CLI:
```bash
consumer_cmd | transformer_cmd | loader_cmd
```
Ketika `loader_cmd` mengalami *crash* (segmentation fault) akibat *out of memory* (OOM), proses `consumer_cmd` tetap berjalan di background secara tak terbatas (*zombie/orphan task*), menahan network socket terbuka dan memblokir alokasi resource worker berikutnya.

**Pertanyaan Diagnostik:**
1. Mengapa transmisi sinyal `SIGPIPE` gagal menumbangkan `consumer_cmd` secara instan pada skenario tertentu?
2. Bagaimana mekanisme interaksi antara kernel buffer, write system call, dan penanganan sinyal default pada sub-proses pipeline saat ujung hilir (*consumer of the pipe*) terputus?
3. Rancang sebuah *fail-safe wrapper pattern* menggunakan `set`, traps, dan monitoring PID eksplisit untuk memastikan seluruh dependensi dalam rantai proses dimusnahkan secara deterministik saat salah satu komponen pipa mati mendadak!

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Throughput Log Sanitizer and Dispatcher Daemon Engine

#### Problem:
Tim keamanan mendeteksi bahwa log akses produksi mentah (`/var/log/ingress/raw.log`) mengandung informasi sensitif (PII: Credit Card dan IPv4 internal) yang tertulis secara masif (±15.000 baris/detik). Anda diminta merancang sebuah *lightweight log ingestion & sanitization engine* murni berbasis Bash dan standard coreutils. Engine ini harus berjalan secara daemonized/background, memproses stream secara real-time tanpa latensi buffer, melakukan mask/redaksi pada PII, mendistribusikan log terfilter ke dua tujuan berbeda secara paralel, serta mampu menerima rotasi file dan interupsi sistem tanpa kehilangan satu baris log pun (*zero data loss*).

#### Requirements:
1. **Strict Core Implementation:** Skrip harus mengimplementasikan safe mode (`set -euo pipefail`), melarang hardcode temp file sembarangan, dan harus menggunakan *dynamic file descriptors* (alokasi FD > 3 via `exec`).
2. **Stream Demultiplexing:** Menggunakan *process substitution* dan alur `tee` untuk mengirim stream data ke dua tujuan secara bersamaan:
   - Destinasi A: Di-hash menggunakan SHA-256 per baris untuk audit trail dan ditulis ke `/var/log/ingress/audit.log`.
   - Destinasi B: Divalidasi dan di-mask (Ganti format CC `\b[0-9]{4}-[0-9]{4}-[0-9]{4}-[0-9]{4}\b` menjadi `[REDACTED_CC]`) lalu disimpan ke `/var/log/ingress/sanitized.log`.
3. **Locking & Concurrency Safety:** Implementasikan locking berbasis `flock` pada file state engine untuk mencegah eksekusi instance ganda.
4. **Resilient Signal Handling (Graceful Shutdown & Reopen):**
   - Tangkap sinyal `SIGTERM` dan `SIGINT`: Engine harus berhenti membaca input baru, melakukan *flush* buffer yang tersisa ke disk, menutup seluruh FD kustom, membersihkan lock, dan keluar dengan exit code `0`.
   - Tangkap sinyal `SIGHUP`: Engine harus melakukan *reopen log handle* (simulasi log rotation awareness) tanpa mematikan proses utama.
5. **No Overhead Rule:** Dilarang menggunakan bahasa interpreter eksternal (Python, Node.js, Perl). Gunakan kombinasi `bash` internal, `sed`/`awk`, `tr`, `tee`, dan Linux pipes.

#### Constraints:
- Skrip tidak boleh membocorkan resource: Tidak boleh ada *orphaned background processes* di `/proc/$PID/task/` setelah script menerima `SIGTERM`.
- Memory footprint maksimal wrapper Bash tidak boleh melampaui 30 MB RSS.
- Harus tahan terhadap lonjakan stream tanpa menghasilkan *broken pipe* (`SIGPIPE` error).

#### Expected Output & Verification:
- Sebuah skrip utuh bernama `log_dispatcher.sh`.
- Perintah simulasi untuk memverifikasi fungsionalitas engine:
  1. *Stream test injection* menggunakan `logger` atau generator file loop.
  2. Verifikasi masking regex pada target file.
  3. Verifikasi transmisi sinyal `kill -HUP <PID>` dan `kill -TERM <PID>` yang membuktikan engine membersihkan dirinya sendiri secara elegan (`trap` verification via `/proc`).

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Representasi arsitektural *File Descriptor Table*, *Open File Description Table*, dan *Inode Table* pada kernel Linux.
- [ ] Perbedaan fungsional antara *forking subshell* `(...)` vs *grouped command context* `{ ...; }`.
- [ ] Mekanisme propagasi error dalam pipeline, array `${PIPESTATUS[@]}`, dan determinasi exit status dengan `pipefail`.
- [ ] Cara kerja *kernel buffer pipe* (default 64KB pada Linux) dan implikasinya terhadap *throughput* serta *blocking I/O*.
- [ ] Konsekuensi *standard streams line-buffering* vs *full-buffering* pada interaksi antar utilitas user-space (POSIX `libc` behavior).
- [ ] Mekanisme pembersihan sumber daya internal shell melalui manipulasi *anonymous pipe* dan virtual descriptor `/dev/fd/`.
- [ ] Standar POSIX terhadap batasan atomisitas operasi I/O file append (`O_APPEND` dan `PIPE_BUF`).

### Saya tidak perlu menghafal:
- [ ] Setiap kode sinyal numerik kernel (misal: cukup mengetahui konsep `SIGTERM`, `SIGINT`, `SIGHUP` secara simbolis tanpa menghafal nilai integer POSIX vs non-POSIX).
- [ ] Nilai eksak ukuran kernel pipe buffer pada setiap rilis arsitektur Linux secara spesifik (cukup pahami batas teoritis dan cara inspeksi dinamisnya via `fcntl` / `ulimit -p`).
- [ ] Seluruh parameter opsi *esoterik* dari perkakas POSIX bawaan sistem (cukup kuasai opsi standar I/O streaming).

### Saya harus bisa melakukan:
- [ ] Mengalokasikan, mereplikasi, membaca dari, dan menutup *arbitrary file descriptor* secara manual menggunakan `exec [N]<>`.
- [ ] Mengonfigurasi skrip automasi produksi berbasis *strict mode* (`set -euo pipefail`) yang kebal terhadap edge cases.
- [ ] Menerapkan *non-blocking file locking mechanism* berbasis `flock` untuk melindungi segmen *critical section*.
- [ ] Mendesain skema *signal trapping* terpadu untuk mencegah kebocoran file sementara, *zombie processes*, dan *dangling background descriptors*.
- [ ] Men-debug pipeline macet akibat *buffering bottleneck* menggunakan perkakas intervensi seperti `stdbuf`, `mawk -W interactive`, atau inspeksi I/O via `lsof -p <PID>` dan `/proc/<PID>/fd/`.
- [ ] Mengarahkan stream log multi-arah menggunakan kombinasi *named pipes*, *process substitution*, dan `tee` tanpa degradasi performa I/O signifikan.