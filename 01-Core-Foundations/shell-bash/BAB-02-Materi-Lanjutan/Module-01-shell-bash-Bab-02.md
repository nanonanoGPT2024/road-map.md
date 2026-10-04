# Modul 01: Arsitektur File Descriptor, Standard Streams, dan Mekanisme I/O Redirection

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta mampu:
* Membedah representasi kernel Linux terhadap abstraksi *stream* menggunakan File Descriptor (FD) secara programatis.
* Mengimplementasikan manipulasi tabel I/O proses menggunakan operator redireksi POSIX (`<`, `>`, `>>`, `>&`, `|`, `exec`).
* Mendiagnosis dan menyelesaikan *race condition*, *descriptor leak*, serta *broken pipe signal* (`SIGPIPE`) pada *pipeline* produksi berskala besar.
* Mengisolasi aliran *standard error* (`stderr`) dan *standard output* (`stdout`) secara presisi untuk kebutuhan *observability* dan penulisan log terstruktur.

---

### 2. Prerequisite
* Pemahaman fundamental mengenai arsitektur sistem operasi berbasis UNIX/Linux (ruang pengguna vs ruang kernel).
* Penguasaan eksekusi perintah dasar Bash (*builtins* vs *external binaries*).
* Kemampuan membaca representasi memori dasar dan status proses melalui filesystem virtual Linux (`/proc`).

---

### 3. Concept
Di Linux dan sistem operasi turunan UNIX lainnya, berlaku paradigma *"everything is a file"*. Pada tingkat kernel, setiap entitas yang menangani transfer data—berkas reguler pada *disk*, *socket* jaringan, *pipe*, hingga perangkat keras fisik—diakses melalui antarmuka seragam berupa aliran *byte* (*stream*).

Ketika suatu proses diinisialisasi melalui *system call* `fork()`, kernel Linux membuat struktur data `struct task_struct` di dalam tabel proses. Di dalam struktur ini terdapat penunjuk `struct files_struct *files`, yang mereferensikan **File Descriptor Table** milik proses tersebut. 

File Descriptor (FD) adalah nilai integer non-negatif sederhana yang berfungsi sebagai indeks array pada tabel berkas proses. Indeks ini menunjuk ke entri global di kernel: **Open File Table** (`struct file`), yang melacak *offset*, status *flags* (seperti `O_APPEND`, `O_NONBLOCK`), serta penunjuk ke struktur *inode* atau VFS (*Virtual File System*).

```
[Proses Space: File Descriptor Table]
  Index 0 (stdin)  -----> [Open File Table Entry (Kernel)] -----> [VFS Inode / Device]
  Index 1 (stdout) -----> [Open File Table Entry (Kernel)] -----> [VFS Inode / TTY]
  Index 2 (stderr) -----> [Open File Table Entry (Kernel)] -----> [VFS Inode / TTY]
```

Redireksi dalam Bash bukanlah manipulasi data *in-memory* oleh program aplikasi, melainkan instruksi kepada *shell* untuk memanggil *system call* sistem operasi (`open()`, `dup2()`, dan `close()`) sebelum proses baru dieksekusi melalui `execve()`.

---

### 4. Why
Dalam rekayasa sistem produksi dan automasi DevOps:
1. **Pemisahan Data Operasional dan Data Diagnostik**: Kegagalan memisahkan `stdout` (aliran payload fungsional) dan `stderr` (aliran jejak error) dapat merusak pemrosesan hilir (*downstream parser* seperti `jq` atau parser JSON log), yang berakibat pada kegagalan *pipeline* CI/CD atau proses ETL.
2. **Resource Leak Prevention**: Kegagalan menutup file descriptor kustom (misal FD 3 sampai 9) pada skrip berdurasi panjang (*long-running daemon*) memicu kondisi *exhaustion* batas sistem (`EMFILE: Too many open files`).
3. **Atomic File Operations**: Memahami mekanisme kernel saat menangani flag `O_CREAT`, `O_TRUNC`, dan `O_APPEND` mencegah terjadinya korupsi log akibat akses berkas yang tumpang tindih.

---

### 5. What
Bash mewarisi tiga File Descriptor standar secara otomatis saat proses berjalan:

| FD Index | Simbol POSIX | Default Device File | Deskripsi Fungsional |
| :--- | :--- | :--- | :--- |
| **0** | `STDIN_FILENO` | `/dev/pts/X` (Terminal Input) | Aliran data masuk ke dalam proses. |
| **1** | `STDOUT_FILENO` | `/dev/pts/X` (Terminal Output) | Aliran data keluar normal/sukses. |
| **2** | `STDERR_FILENO` | `/dev/pts/X` (Terminal Output) | Aliran status error, log unbuffered, dan diagnostik. |

Kategori Operator Redireksi Kunci:
* `<` : Mengalihkan sumber input (`stdin`) dari berkas (`O_RDONLY`).
* `>` : Mengarahkan output (`stdout`) ke berkas, menimpa berkas jika ada (`O_WRONLY | O_CREAT | O_TRUNC`).
* `>>` : Mengarahkan output ke berkas dengan menambahkan ke baris akhir (`O_WRONLY | O_CREAT | O_APPEND`).
* `&>` atau `>&` : Mengarahkan `stdout` dan `stderr` secara bersamaan ke tujuan yang sama.
* `M>&N` : Menggabungkan (*duplicate*) File Descriptor $M$ agar merujuk ke File Descriptor $N$ melalui *syscall* `dup2()`.
* `exec M>file` : Membuka alokasi descriptor permanen di dalam sesi *current shell*.
* `M<&-` atau `M>&-` : Menutup (*close*) File Descriptor $M$.

---

### 6. How
Mekanisme kernel di balik eksekusi sintaks: `cmd > output.log 2>&1`

Evaluasi shell diproses dari **kiri ke kanan**:

1. **Token Parsing**: Bash membaca baris instruksi dan mendeteksi token redireksi `> output.log` dan `2>&1`.
2. **Fork**: Bash menjalankan *system call* `fork()` untuk membuat *child process*.
3. **Redireksi 1 (`> output.log`)**:
   * Shell memanggil *system call* `open("output.log", O_WRONLY|O_CREAT|O_TRUNC, 0666)`. Misal, kernel memberikan FD sementara bernilai `3`.
   * Shell memanggil `dup2(3, 1)`. Artinya: Ubah slot FD 1 (`stdout`) pada tabel proses agar merujuk ke entri file yang sama dengan FD 3 (`output.log`).
   * Shell menutup FD 3 via `close(3)`. Sekarang FD 1 terhubung ke `output.log`.
4. **Redireksi 2 (`2>&1`)**:
   * Shell memproses instruksi duplikasi descriptor 2 ke descriptor 1.
   * Shell memanggil `dup2(1, 2)`. Sekarang FD 2 (`stderr`) merujuk ke tabel berkas kernel yang dituju oleh FD 1 saat ini (`output.log`).
5. **Execution**: Child process memanggil `execve("/bin/cmd", ...)`. 
   * Program `cmd` tidak memiliki kesadaran bahwa I/O telah diarahkan ke berkas. Ia hanya menulis data ke FD 1 dan FD 2 secara konvensional.

> **PENTING: Urutan Penulisan Redireksi.**  
> Jika ditulis `cmd 2>&1 > output.log`:
> 1. `dup2(1, 2)`: FD 2 menunjuk ke tujuan FD 1 saat ini (yaitu Terminal/TTY).
> 2. `open("output.log")` -> FD 1 dialihkan ke `output.log`.
> *Hasil*: `stderr` tetap keluar ke Terminal, sementara `stdout` masuk ke berkas. Ini adalah *common anti-pattern*.

---

### 7. Analogy
Bayangkan File Descriptor Table sebagai **Panel Hubung Telepon Manual (Switchboard)** di kantor pos:
* **Index 0, 1, 2** adalah soket kabel berlabel: Masuk (0), Keluar (1), Peringatan (2).
* Secara *default*, soket 1 dan 2 ditancapkan kabel yang terhubung langsung ke pengeras suara aula (`/dev/tty`).
* Instruksi `> output.log` mencabut kabel dari soket 1 lalu menancapkannya ke sebuah mesin perekam pita (`output.log`).
* Instruksi `2>&1` mengambil soket 2, menduplikat sambungan fisiknya, lalu menancapkannya ke terminal yang sama dengan soket 1 saat itu (mesin perekam).
* Perintah eksekusi hanya mengirimkan sinyal melalui soket tersebut tanpa peduli apakah ujung kabel terhubung ke pengeras suara, pita kaset, atau tempat sampah (`/dev/null`).

---

### 8. Diagram
Diagram alur state File Descriptor Table saat eksekusi `command > file.txt 2>&1`:

```
1. Default State (Inisialisasi):
   [Process File Descriptor Table]           [Kernel Open File Table]
   | FD 0 (stdin)  | ----------------------> | /dev/pts/0 (Keyboard)  |
   | FD 1 (stdout) | ----------------------> | /dev/pts/0 (Screen)    |
   | FD 2 (stderr) | ----------------------> | /dev/pts/0 (Screen)    |

2. Setelah parsing '> file.txt' (dup2 file descriptor ke FD 1):
   [Process File Descriptor Table]           [Kernel Open File Table]
   | FD 0 (stdin)  | ----------------------> | /dev/pts/0             |
   | FD 1 (stdout) | ---(Diubah via dup2)---> | file.txt (Offset: 0)   |
   | FD 2 (stderr) | ----------------------> | /dev/pts/0             |

3. Setelah parsing '2>&1' (dup2 FD 1 ke FD 2):
   [Process File Descriptor Table]           [Kernel Open File Table]
   | FD 0 (stdin)  | ----------------------> | /dev/pts/0             |
   | FD 1 (stdout) | ----------------------> | file.txt (Offset: 0)   |
   | FD 2 (stderr) | ---(Diubah via dup2)---> | file.txt (Offset: 0)   |
```

---

### 9. Simple Example
Melihat langsung File Descriptor dari dalam proses yang sedang berjalan:

```bash
# Buka subshell, alihkan file descriptor 3 ke sebuah berkas sementara,
# lalu periksa entri fd pada /proc virtual filesystem.
(
  exec 3> /tmp/custom_fd_test.txt
  ls -l /proc/$$/fd/
  exec 3>&- # Tutup kembali descriptor 3
)
```

Output Terminal:
```text
total 0
lrwx------ 1 user user 64 Feb 18 10:00 0 -> /dev/pts/1
lrwx------ 1 user user 64 Feb 18 10:00 1 -> /dev/pts/1
lrwx------ 1 user user 64 Feb 18 10:00 2 -> /dev/pts/1
l-wx------ 1 user user 64 Feb 18 10:00 3 -> /tmp/custom_fd_test.txt
```

---

### 10. Practical Example
Berikut adalah implementasi *framework* eksekusi batch terstruktur dengan *isolated logging*: memisahkan log audit operasional dengan data stream murni tanpa memicu subshell berlebih.

```bash
#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

readonly LOG_FILE="/tmp/service_execution.log"
readonly METRICS_FILE="/tmp/metrics.csv"

# 1. Buka File Descriptor 3 untuk penulisan log secara permanen dalam sesi ini
exec 3>> "${LOG_FILE}"

# 2. Buka File Descriptor 4 untuk stream penulisan metrik data
exec 4>> "${METRICS_FILE}"

log_message() {
    local level="$1"
    local message="$2"
    # Tulis langsung ke File Descriptor 3
    printf '[%s] [%s] %s\n' "$(date --utc +'%Y-%m-%dT%H:%M:%SZ')" "${level}" "${message}" >&3
}

emit_metric() {
    local metric_name="$1"
    local value="$2"
    # Tulis langsung ke File Descriptor 4
    printf '%s,%s,%s\n' "$(date +%s)" "${metric_name}" "${value}" >&4
}

# --- Eksekusi Utama ---
log_message "INFO" "Proses batching data diinisialisasi."

# Jalankan command sistem, buang stdout reguler ke null, 
# tetapi alihkan stderr ke sistem log via FD 3
if ! ls /root/restricted_area > /dev/null 2>&3; then
    log_message "WARN" "Gagal membaca direktori /root/restricted_area. Fallback diaktifkan."
fi

emit_metric "cpu_load_ratio" "0.45"
emit_metric "processed_chunks" "12"

log_message "INFO" "Proses batching data selesai. Menutup custom descriptors."

# 3. Cleanup: Tutup File Descriptor 3 dan 4 secara eksplisit
exec 3>&-
exec 4>&-
```

---

### 11. Real World Example
**Skenario**: Sistem *log collection* pada kluster perbankan berskala besar. Tim platform mengharuskan setiap komponen skrip *backup database* menghasilkan file dump terenkripsi (`stdout`), mencatat audit transaksional ke berkas audit aman, dan memancarkan notifikasi insiden hanya jika terjadi galat (`stderr`), tanpa risiko terputusnya transmisi pipa (`broken pipe`).

```bash
#!/usr/bin/env bash
set -Eeuo pipefail

BACKUP_TARGET="/mnt/secure_backup/pg_dump_$(date +%Y%m%d%H%M%S).sql.gz"
AUDIT_PIPE="/tmp/audit.fifo"
ALERT_LOG="/var/log/alerts.log"

# Siapkan Named Pipe (FIFO) untuk pemrosesan audit paralel non-blocking
[[ -p "${AUDIT_PIPE}" ]] || mkfifo "${AUDIT_PIPE}"

# Jalankan konsumsi audit log di background (FD isolation)
tee -a /var/log/db_audit.log < "${AUDIT_PIPE}" > /dev/null &
AUDIT_PID=$!

# Buka custom FD 5 menuju FIFO stream
exec 5> "${AUDIT_PIPE}"

# Penanganan sinyal untuk memastikan FIFO dan custom FD dibersihkan
cleanup() {
    local exit_code=$?
    exec 5>&- || true
    rm -f "${AUDIT_PIPE}" || true
    kill "${AUDIT_PID}" 2>/dev/null || true
    exit "${exit_code}"
}
trap cleanup EXIT ERR SIGTERM

# Eksekusi database dump stream:
# 1. FD 1 (dump binary) diarahkan via pipe langsung ke gzip, lalu ke disk
# 2. FD 2 dialihkan secara presisi ke berkas log peringatan
# 3. FD 5 mencatat status checkpoint secara sinkron
printf 'ACTION=INIT_BACKUP TIMESTAMP=%s\n' "$(date +%s)" >&5

# Simulasi stream pipeline database
{
    echo "DUMP_RAW_SQL_RECORD_001"
    echo "CRITICAL: Index out of sync on table 'users'" >&2
    echo "DUMP_RAW_SQL_RECORD_002"
} 2>> "${ALERT_LOG}" \
  | gzip -9 -c > "${BACKUP_TARGET}"

printf 'ACTION=COMPLETE_BACKUP STATUS=SUCCESS TIMESTAMP=%s\n' "$(date +%s)" >&5
```

---

### 12. Trade-offs
Memanipulasi File Descriptor secara manual vs menggunakan *Standard Shell Pipeline*:

* **Advantages**:
  * Efisiensi performa: Menghindari pembuatan *subshell* implisit yang menyertai setiap karakter pipa (`|`), sehingga menghemat alokasi memori sistem.
  * Granularitas tinggi: Mampu mengalirkan output dari satu proses ke berbagai tujuan berkas dan *socket* yang berbeda secara simultan.
* **Disadvantages**:
  * Tingkat keterbacaan kode (*code readability*) menurun; sintaks *descriptor swapping* (`3>&1 1>&2 2>&3`) memerlukan pemahaman mendalam tentang POSIX.
  * Debugging kompleks: Kesalahan penutupan FD memicu *leaking descriptor* yang sulit dilacak tanpa inspeksi runtime di `/proc/$PID/fd`.
* **Complexity**: Tinggi jika menangani *custom descriptors* (>3).
* **Performance**: Maksimal; *overhead* pemanggilan sistem operasi terminimalisasi langsung pada tingkat C runtime kernel.
* **Cost**: Utilisasi CPU sangat rendah, tetapi biaya kognitif *code review* meningkat signifikan.

---

### 13. When To Use
* Saat merancang *framework daemon*, skrip sistem berskala enterprise, atau *entrypoint script* container (Docker).
* Ketika operasi I/O membutuhkan pemisahan deterministik antara artefak fungsional (misal: JSON/Binary) dan pesan status log.
* Saat menulis skrip yang memproses iterasi file masukan berukuran gigabyte (*streaming*) tanpa membaca seluruh file ke memori (RAM).

---

### 14. When NOT To Use
* Untuk skrip automasi sederhana satu baris (*one-liner* pemeliharaan rutin).
* Ketika data pemrosesan perlu dimodifikasi secara interaktif di terminal oleh manusia.
* Pada aplikasi berorientasi konkurensi tingkat tinggi yang memerlukan *thread-safe memory sharing*; gunakan bahasa pemrograman sistem seperti Go, Rust, atau C.

---

### 15. Common Mistakes
1. **Urutan Evaluasi Redireksi yang Terbalik**:
   ```bash
   # SALAH: stderr tetap terikat ke terminal/stdout awal sebelum stdout dipindah
   cmd 2>&1 > /tmp/output.log

   # BENAR: stdout dipindah ke file, kemudian stderr diduplikasi ke lokasi stdout baru
   cmd > /tmp/output.log 2>&1
   ```
2. **Korupsi Isi File Saat Membaca dan Menulis Berkas yang Sama**:
   ```bash
   # FATAL: Shell memproses 'O_TRUNC' pada file.txt SEBELUM command 'cat' mulai membaca
   cat file.txt | tr 'a-z' 'A-Z' > file.txt # Menghasilkan file kosong
   ```
3. **Descriptor Leaks pada Subshell**:
   Membuka `exec 3> file` di dalam skrip modular tanpa menyediakan instruksi penutupan `exec 3>&-` yang setara, memicu *resource starvation* pada pemrosesan berulang berdurasi lama.

---

### 16. Best Practices
* Gunakan sintaks modern POSIX untuk redireksi gabungan: `&> file.log` (jika eksklusif Bash) atau `> file.log 2>&1` (kompatibel lintas POSIX).
* Selalu pasang *safety traps* (`trap ... EXIT`) untuk menutup descriptor buatan pengguna (`3` sampai `9`) saat skrip keluar.
* Gunakan flag `noclobber` (`set -C`) di sesi kritis untuk mencegah penimpaan file secara tidak sengaja oleh operator `>`. Penimpaan eksplisit dapat dilakukan via `>|`.
* Tulis pesan error secara konsisten ke *standard error*:
  ```bash
  echo "Error: Koneksi basis data gagal." >&2
  ```

---

### 17. Troubleshooting
* **Masalah**: Pesan *"Bad file descriptor"* (Error Code: EBADF).
  * *Penyebab*: Skrip mencoba menulis atau membaca dari descriptor yang belum dibuka atau sudah ditutup sebelumnya.
  * *Investigasi*: Jalankan `lsof -p <PID>` atau `ls -l /proc/<PID>/fd` untuk memeriksa tabel berkas aktif pada proses tersebut.
* **Masalah**: Pipeline tiba-tiba terhenti tanpa log yang jelas.
  * *Penyebab*: `SIGPIPE` dikirim oleh kernel karena proses pembaca hilir (*downstream consumer*) ditutup lebih awal daripada proses produsen (*producer*).
  * *Mitigasi*: Periksa nilai array `${PIPESTATUS[@]}` Bash untuk mengidentifikasi segmen pipeline mana yang mengembalikan status non-zero (misal `141` = $128 + 13$ [SIGPIPE]).

---

### 18. Exercise
Selesaikan skenario berikut dengan sintaks Bash:
1. Buat berkas skrip bernama `fd_inspector.sh`.
2. Buka File Descriptor baru bernilai `7` yang mengarah ke `/tmp/fd_exercise.log`.
3. Tuliskan teks `"Kernel Level Tracking"` ke dalam File Descriptor `7` tersebut.
4. Buat sub-proses Bash yang memverifikasi eksistensi symlink File Descriptor `7` pada `/proc/$$/fd/7`.
5. Tutup File Descriptor `7` dan buktikan melalui penanganan error terstruktur bahwa penulisan ulang ke FD 7 menghasilkan galat (*Bad file descriptor*).

---

### 19. Challenge
**Rancang Mekanisme FD-Swapping Non-Destruktif**:  
Buatlah sebuah *wrapper function* bash yang mengeksekusi *command* arbitrer, lalu:
1. Menukar fungsionalitas `stdout` dan `stderr` murni hanya untuk *command* tersebut: data yang normalnya keluar ke `stdout` dipaksa keluar ke `stderr`, dan error yang normalnya keluar ke `stderr` dialihkan ke `stdout`.
2. **Kondisi Batas**: Dilarang menggunakan berkas perantara di disk (*temporary file*). Pemetaan wajib diselesaikan secara murni di level kernel memory menggunakan manipulasi direct operator FD (`>&`, `<&`).
3. Verifikasi hasilnya dengan menghubungkan fungsi tersebut ke pipeline: `wrapper_func | grep "hanya pesan stderr asli"`.

---

### 20. Summary
* File Descriptor adalah indeks numerik integer yang bertindak sebagai referensi abstrak tingkat kernel terhadap aliran data I/O.
* File descriptor 0 (`stdin`), 1 (`stdout`), dan 2 (`stderr`) adalah tiga kanal fundamental yang diwariskan kepada setiap proses Linux baru.
* Redireksi dievaluasi oleh shell dari **kiri ke kanan** menggunakan *system call* `dup2()`, bukan dievaluasi oleh utilitas biner target.
* Isolasi aliran data adalah prasyarat arsitektural untuk memastikan pipeline pemrosesan data otomatis berjalan stabil, transparan, dan tahan terhadap anomali eksekusi.