# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, engineer diharapkan memiliki kompetensi tingkat lanjut untuk:
- Menguasai manipulasi File Descriptor (FD) kustom (FD 3–9), manipulasi *anonymous pipe*, serta *named pipe* (FIFO) untuk komunikasi antar-proses.
- Memahami perbedaan mendasar antara eksekusi *subshell* (`fork()` tanpa `execve()`) dan *child process* (`fork()` diikuti `execve()`), serta dampaknya terhadap alokasi memori dan persistensi variabel.
- Mengimplementasikan pola konkurensi tingkat lanjut menggunakan *coprocess* (`coproc`), *job control*, dan *worker pool* berbasis *semaphore* murni dalam Bash.
- Mendesain arsitektur otomasi dan *data pipeline* kelas enterprise yang tahan terhadap kegagalan (*fault-tolerant*), mengelola sinyal POSIX secara deterministik, serta menerapkan *graceful shutdown*.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, pastikan Anda telah menguasai:
- Konsep dasar shell scripting: manipulasi string, struktur kontrol, dan fungsi modular.
- Konsep dasar sistem operasi POSIX: alokasi memori virtual, *system calls*, tabel *process control block* (PCB), dan struktur I/O dasar (`stdin`, `stdout`, `stderr`).
- Penggunaan alat diagnostik sistem Linux dasar: `lsof`, `strace`, `ps`, `kill`, dan `procfs` (`/proc/$PID/`).

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Linux Kernel Primitive: `task_struct`, `files_struct`, dan File Descriptors

Di dalam Linux kernel, setiap proses direpresentasikan oleh struktur data `task_struct`. Salah satu komponen kritis di dalamnya adalah penunjuk ke `struct files_struct *files`, yang merepresentasikan tabel File Descriptor (FD) proses tersebut:

```
task_struct
  ├── pid_t pid
  ├── struct mm_struct *mm
  └── struct files_struct *files
        └── struct fdtable *fdt
              └── struct file **fd  ──> [0] -> /dev/pts/0 (stdin)
                                        [1] -> /dev/pts/0 (stdout)
                                        [2] -> /dev/pts/0 (stderr)
                                        [3] -> pipe:[184920] (custom input)
                                        [4] -> /var/log/audit.log (custom output)
```

Ketika Bash melakukan manipulasi I/O:
1. **Redirection (`>`, `<`, `>>`)**: Menggunakan *system call* `openat(2)` untuk mendapatkan integer FD baru, diikuti dengan `dup2(oldfd, newfd)` untuk menimpa FD target (misal FD 1), lalu menutup FD lama via `close(oldfd)`.
2. **Duplikasi FD (`>&`, `<&`)**: Memanggil `dup2(src_fd, dst_fd)` secara langsung tanpa alokasi file baru, menduplikasi penunjuk pada level kernel `struct file`.

### 3.2 Subshell vs Child Process vs Command Group

Penting untuk membedakan ketiga mekanisme eksekusi ini:

1. **Command Group (`{ list; }`)**:
   - Berjalan dalam konteks proses Bash yang sama.
   - Tidak ada alokasi proses kernel baru (`fork()` tidak dipanggil).
   - Modifikasi variabel dan modifikasi status shell (misal: `cd`) tetap persisten setelah blok selesai dieksekusi.
2. **Subshell (`( list )`)**:
   - Memanggil `fork()` murni.
   - Menggandakan *address space* proses induk melalui *Copy-On-Write* (COW).
   - **Tidak** memanggil `execve()`. Proses anak tetap mengeksekusi *binary* Bash yang sama dengan salinan *environment*, variabel internal, dan fungsi.
   - Segala mutasi variabel di dalam subshell terisolasi dan musnah saat subshell keluar (`exit`).
3. **Child Process / External Command (misal: `grep`, `awk`, script baru)**:
   - Memanggil `fork()` diikuti dengan `execve()`.
   - *Address space* diganti sepenuhnya dengan *binary executable* baru. Seluruh variabel Bash internal yang tidak di-`export` akan dibuang.

```
Execution Comparison:

1. Command Group:   [Bash PID 100] ── (In-Process Execution) ──> [Bash PID 100]
2. Subshell:        [Bash PID 100] ── fork() ──> [Bash PID 101 (Copy-On-Write)] (No execve)
3. External Exec:   [Bash PID 100] ── fork() ──> [Bash PID 102] ── execve(/bin/grep) ──> Binary Baru
```

### 3.3 IPC Tingkat Lanjut: Anonymous Pipes, Named Pipes (FIFO), dan Coprocess

- **Anonymous Pipe (`|`)**:
  Bash membuat pipa kernel berkapasitas tetap (umumnya 64 KB di Linux modern via `fcntl(fd, F_SETPIPE_SZ)`) menggunakan *system call* `pipe(2)`. Bash memanggil `fork()` untuk kedua sisi *pipeline* secara konkuren. Sisi kiri menduplikasi ujung *write* ke FD 1, sisi kanan menduplikasi ujung *read* ke FD 0.
- **Process Substitution (`<(cmd)`, `>(cmd)`)**:
  Bash membuat *anonymous pipe* atau menggunakan `/dev/fd/<n>`. Perintah di dalam kurung dieksekusi secara asinkron di subshell, sementara jalurnya dipassing sebagai argumen string ke perintah utama (misal `/dev/fd/63`).
- **Coprocess (`coproc`)**:
  Mekanisme Bash untuk meluncurkan subshell asinkron dengan saluran komunikasi dua arah (*bidirectional*) yang terhubung langsung ke dua FD kustom pada proses utama induk melalui array `${NAME_PID}` dan `${NAME[@]}`.

---

## 4. Why & What

### Mengapa Pendekatan Tradisional Gagal?
Banyak skrip Bash produksi gagal memenuhi standar enterprise karena:
1. **Subshell Pitfall**: Mengiterasi baris teks menggunakan `cat file | while read line; do ... done` menyebabkan blok perulangan berjalan di subshell. Variabel akumulator yang dimodifikasi di dalam loop akan bernilai kosong setelah loop selesai.
2. **Resource Exhaustion**: Meluncurkan ribuan proses *background* (`&`) tanpa pembatasan (*throttling*) memicu kehabisan PID (*PID exhaustion*) dan aktivasi Linux OOM Killer.
3. **Signal Mismanagement**: Skrip shell di dalam container (Docker/Kubernetes) yang tidak menangani `SIGTERM` akan digantung oleh init system hingga batas waktu *graceful termination* berakhir, kemudian dihentikan paksa via `SIGKILL`.

### Solusi Arsitektur
Dengan mengimplementasikan *Process Substitution*, manipulasi FD eksplisit, dan *asynchronous worker queue*, kita mendapatkan pemrosesan data bervolume tinggi dengan konsumsi CPU dan memori minimal tanpa perlu menginstal dependensi runtime eksternal seperti Python atau Node.js pada *base image*.

---

## 5. How (Workflow Detail)

Alur kerja arsitektur pemrosesan aliran data (*stream processing*) paralel berbasis FD:

```
[Main Bash Controller Engine]
        │
        ├── 1. Inisialisasi Mutex / Semaphore FIFO via FD 3
        │
        ├── 2. Konfigurasi Trap Handler (EXIT, SIGINT, SIGTERM, ERR)
        │
        ├── 3. Alokasi Worker Pool (Slot Concurrency Token)
        │       │
        │       ├── Worker Thread 1 (Background Process) ── Read Token ── Eksekusi Task ── Return Token
        │       ├── Worker Thread 2 (Background Process) ── Read Token ── Eksekusi Task ── Return Token
        │       └── Worker Thread N (Background Process) ── Read Token ── Eksekusi Task ── Return Token
        │
        ├── 4. Job Synchronization Bar (`wait`)
        │
        └── 5. Cleanup Deterministic: Hapus FIFO, Tutup Custom FD, Flush Buffer
```

---

## 6. Analogy & Diagram ASCII

Bayangkan sistem I/O Linux sebagai sentral instalasi pipa fluida:

```
      Standard Setup:
      [ Keyboard (FD 0) ] ──> [ Process Engine ] ──> [ Terminal Screen (FD 1) ]
                                      │
                                      └──> [ Error Log Display (FD 2) ]

      Advanced Enterprise Architecture:
                                      ┌──> [ Audit Stream (FD 3) ] ──> /var/log/audit.pipe
                                      │
      [ /dev/urandom ] ──> [ FD 0 ] ──┼──> [ Metrics Engine (FD 4) ] ──> Prometheus Exporter
                                      │
                                      └──> [ FD 1 (stdout) ] ──> Consumer Downstream
```

Dalam analogi ini:
- Mengubah arah pipa (`dup2`) seperti memindahkan sambungan selang dari satu tangki ke tangki lain.
- Membuka FD kustom (`exec 3<>pipe`) seperti memasang keran bypass tambahan agar aliran utama tidak terhambat (*non-blocking*).

---

## 7. Practical Implementation

### 7.1 Robust Worker Pool Concurrency (Semaphore via FIFO & FD)

Script berikut mengimplementasikan konkurensi terkontrol tanpa perkakas eksternal (`xargs -P` atau `parallel`), murni menggunakan fitur bawaan Bash:

```bash
#!/usr/bin/env bash
# ==============================================================================
# Script: concurrent_engine.sh
# Description: Engine worker-pool konkurensi tinggi berbasis FIFO File Descriptor
# ==============================================================================

set -Eeuo pipefail
shopt -s inherit_errexit

# Konfigurasi Pool
readonly MAX_CONCURRENCY=4
readonly SEM_FIFO="/tmp/worker_pool_${BASHPID}.fifo"

# Buat FIFO untuk mekanisme token semaphore
mkfifo "${SEM_FIFO}"

# Buka FIFO pada FD 3 untuk read-write, lalu hapus file dari filesystem.
# Referensi inode tetap aktif selama FD 3 terbuka (atomic cleanup protection).
exec 3<>"${SEM_FIFO}"
rm -f "${SEM_FIFO}"

# Inisialisasi pool dengan token sesuai limit konkurensi
for ((i = 0; i < MAX_CONCURRENCY; i++)); do
    echo >&3
done

# Cleanup function untuk determinisme sistem
cleanup() {
    local exit_code=$?
    trap - EXIT INT TERM
    echo "[INFO] Menutup File Descriptor dan membersihkan proses anak..."
    exec 3<&- # Tutup read
    exec 3>&- # Tutup write
    wait
    exit "${exit_code}"
}
trap cleanup EXIT INT TERM

# Task Payload Definition
process_payload() {
    local payload_id="$1"
    local execution_time=$(( (RANDOM % 3) + 1 ))

    printf "[%s] [START] Task %02d dialokasikan (estimasi %ds)\n" \
        "$(date +'%H:%M:%S')" "${payload_id}" "${execution_time}"
    
    sleep "${execution_time}"
    
    printf "[%s] [FINISH] Task %02d selesai dieksekusi\n" \
        "$(date +'%H:%M:%S')" "${payload_id}"
}

# Pipeline Execution Loop
TOTAL_TASKS=12
echo "[INFO] Meluncurkan ${TOTAL_TASKS} tasks dengan limit konkurensi ${MAX_CONCURRENCY}..."

for ((task_id = 1; task_id <= TOTAL_TASKS; task_id++)); do
    # Ambil token dari semaphore (blocking read jika pool habis)
    read -r -u 3

    # Luncurkan worker secara asinkron
    (
        # Jalankan payload
        process_payload "${task_id}"
        
        # Kembalikan token ke FD 3 setelah selesai
        echo >&3
    ) &
done

# Tunggu seluruh proses anak di background selesai
wait
echo "[INFO] Seluruh pemrosesan payload selesai secara deterministik."
```

### 7.2 IPC Dupleks Menggunakan Coprocess

Contoh berikut menunjukkan komunikasi dua arah (*duplex*) antara proses utama dengan *subshell backend transformer*:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail

# Inisialisasi coprocess sebagai stream JSON normalizer
coproc JSON_ENGINE {
    while read -r raw_line; do
        if [[ "${raw_line}" == "QUIT" ]]; then
            break
        fi
        # Transformasi input menjadi format JSON terstruktur
        printf '{"timestamp": "%s", "data": "%s", "status": "PROCESSED"}\n' \
            "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "${raw_line^^}"
    done
}

echo "[INFO] Coprocess diluncurkan dengan PID: ${JSON_ENGINE_PID}"
echo "[INFO] FD Output Coprocess: ${JSON_ENGINE[1]}, FD Input Coprocess: ${JSON_ENGINE[0]}"

# Mengirim data ke FD Write coprocess
declare -a inputs=("transaksi-alpha" "order-beta" "settlement-charlie")

for item in "${inputs[@]}"; do
    echo "${item}" >&"${JSON_ENGINE[1]}"
    # Membaca hasil transformasi dari FD Read coprocess
    read -r -u "${JSON_ENGINE[0]}" response
    echo "[ENGINE RESPONSE] ${response}"
done

# Terminasi coprocess secara rapi
echo "QUIT" >&"${JSON_ENGINE[1]}"
wait "${JSON_ENGINE_PID}"
```

---

## 8. Real-World Case Study (Enterprise Scale)

### Kasus: Pipeline Ingesti dan Sensor Data Sensitif (PII/Secret Redaction)
**Konteks**: Sebuah infrastruktur perbankan membutuhkan agen pada Node Linux yang memproses *stream log* secara *real-time* dari aplikasi monolitik sebesar puluhan gigabyte per jam, menyensor data nomor kartu kredit (PAN), dan mendistribusikan log:
1. Log audit lengkap (terenkripsi) diarahkan ke file penyimpanan dingin (*cold storage*).
2. Log yang sudah disensor (*redacted*) diarahkan ke *standard forwarder* log server.

Script harus memiliki *footprint* memori statis (<10 MB), tidak boleh membuat file sementara (*zero disk write* untuk raw secrets), dan wajib menangani sinyal rotasi log (`SIGHUP`) serta terminasi platform container (`SIGTERM`).

```bash
#!/usr/bin/env bash
# ==============================================================================
# Enterprise Stream Ingestion & PII Redactor
# ==============================================================================

set -Eeuo pipefail
shopt -s inherit_errexit

readonly AUDIT_LOG="/var/log/audit_encrypted.log"
readonly FORWARD_PIPE="/tmp/log_forwarder.fifo"
readonly LOG_SOURCE="/var/log/app_source.stream"

# Pastikan Named Pipe tersedia
[[ -p "${FORWARD_PIPE}" ]] || mkfifo "${FORWARD_PIPE}"

# Inisialisasi FD kustom
# FD 3: Menulis ke cold storage terenkripsi
# FD 4: Menulis ke pipe downstream forwarder
exec 3>>"${AUDIT_LOG}"
exec 4<>"${FORWARD_PIPE}"

# State Machine Management
declare -i RUNNING=1

handle_sigterm() {
    printf "[%s] [ALERT] Menerima SIGTERM, memulai graceful drain...\n" "$(date)" >&2
    RUNNING=0
}

handle_sighup() {
    printf "[%s] [ALERT] Menerima SIGHUP, memutar rotasi FD audit...\n" "$(date)" >&2
    exec 3>&-
    exec 3>>"${AUDIT_LOG}"
}

trap handle_sigterm SIGTERM
trap handle_sighup SIGHUP

# Simulasi Input Data Stream (Process Substitution untuk menghindari subshell utama)
stream_producer() {
    while (( RUNNING )); do
        echo "PAYMENT user=budi card=4532-1122-3344-5566 amount=500000 status=success"
        echo "AUTH user=ani card=5412-9988-7766-5544 status=failed"
        sleep 0.5
    done
}

# Redaction Logic via AWK Stream Transformation
redaction_engine() {
    awk '{
        raw = $0;
        # Masking nomor kartu (16 digit format berpemisah)
        gsub(/[0-9]{4}-[0-9]{4}-[0-9]{4}-[0-9]{4}/, "XXXX-XXXX-XXXX-XXXX", $0);
        # Kirim data bersih ke stdout (akan dialirkan ke FD 4)
        print $0;
        # Kirim data raw ke FD 3 (Audit) via print redirection internal awk
        print raw > "/dev/fd/3";
        fflush();
    }'
}

# Pipeline Execution: Producer dialirkan langsung tanpa memecah environment controller
echo "[INFO] Menjalankan Enterprise Stream Engine..."
while (( RUNNING )); do
    # Jalankan consumer loop membaca dari producer stream via process substitution
    while IFS= read -r redacted_line; do
        # Salurkan data bersih ke Forwarder Log (FD 4)
        echo "${redacted_line}" >&4
        
        # Validasi sinyal interrupt
        (( RUNNING == 0 )) && break
    done < <(stream_producer | redaction_engine)
done

# Cleanup deterministik
echo "[INFO] Menutup koneksi seluruh File Descriptors..."
exec 3>&-
exec 4>&-
[[ -p "${FORWARD_PIPE}" ]] && rm -f "${FORWARD_PIPE}"
echo "[INFO] Pipeline shutdown dengan aman."
```

---

## 9. Trade-offs

| Parameter Arsitektur | Menggunakan Bash Native (FD & Pipes) | Menggunakan High-Level Runtimes (Python/Go) | Menggunakan CLI Wrapper (`xargs`/`parallel`) |
| :--- | :--- | :--- | :--- |
| **Footprint Memori** | Sangat Rendah (~2MB - 5MB per interpreter). | Sedang-Tinggi (20MB - 100MB+ virtual memory). | Rendah (~5MB - 10MB). |
| **Ketergantungan OS** | Nol. Berjalan di seluruh POSIX standard environment. | Bergantung pada runtime packages & libs. | Memerlukan instalasi paket eksternal. |
| **Parsing Data Kompleks**| Sangat Sulit. Berisiko jika memproses struktur nested JSON/Protobuf. | Sangat Efisien (Native JSON/Serialization support).| Tidak dirancang untuk parsing data internal. |
| **Performa CPU** | Efisien untuk routing stream; Buruk untuk manipulasi string per byte. | Sangat optimal untuk komputasi numerik & teks. | Optimal untuk batching command. |
| **Debugging Complexity**| Sangat Tinggi (Tracing race-condition, pipe locks, & traps). | Rendah-Sedang (Stack traces, debugger tools).| Rendah (Struktur linier/terbungkus argumen). |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Silent Subshell Variable Annihilation
- **Gejala**: Variabel yang dimodifikasi di dalam perulangan kembali ke nilai semula setelah perulangan selesai.
- **Penyebab**: Menggunakan pipe (`|`) ke blok `while read`, yang memaksa Bash membuat subshell via `fork()`.
- **Solusi**: Ubah ke *Process Substitution* atau aktifkan shell option `shopt -s lastpipe` (pada non-interactive shells atau matikan job control via `set +m`).

```bash
# SALAH: Counter bernilai 0 di akhir
COUNTER=0
cat /etc/hosts | while read -r line; do
    (( COUNTER++ ))
done
echo "${COUNTER}" # Output: 0

# BENAR (Process Substitution):
COUNTER=0
while read -r line; do
    (( COUNTER++ ))
done < <(cat /etc/hosts)
echo "${COUNTER}" # Output: > 0

# BENAR (lastpipe optimization):
set +m
shopt -s lastpipe
COUNTER=0
cat /etc/hosts | while read -r line; do
    (( COUNTER++ ))
done
echo "${COUNTER}" # Output: > 0
```

### 10.2 FIFO Read/Write Deadlock
- **Gejala**: Proses membeku (*hang*) saat membuka *Named Pipe* (`mkfifo`).
- **Penyebab**: Operasi `open()` pada FIFO bersifat blocking secara default hingga kedua ujung (read dan write) dibuka bersamaan oleh proses.
- **Solusi**: Gunakan dupleks redirection `exec 3<>my_fifo` agar proses membuka kedua sisi stream secara simultan, mencegah *kernel block*.

### 10.3 Dead Child Accumulation (Zombie Processes)
- **Gejala**: Output `ps aux` menampilkan status `[bash] <defunct>`.
- **Penyebab**: Background process selesai tetapi parent process tidak memanggil *system call* `wait(2)` untuk membaca status keluar anak.
- **Solusi**: Pasang handler sinyal `SIGCHLD`:

```bash
trap 'while wait -n 2>/dev/null; do :; done' SIGCHLD
```

---

## 11. Best Practices (Production Checklist)

- [ ] **Strict Execution Flags**: Menggunakan `set -Eeuo pipefail` di awal skrip tanpa kompromi.
- [ ] **Errtrace Enforcement**: Mengaktifkan `shopt -s inherit_errexit` agar fungsi dan subshell mewarisi trap `ERR` dan flag `-e`.
- [ ] **Deterministic Cleanups**: Seluruh manipulasi kustom FD (3–9) harus didaftarkan di fungsi `cleanup()` melalui `trap ... EXIT`.
- [ ] **Explicit FD Routing**: Hindari mengasumsikan nomor FD kosong; selalu tutup FD setelah tidak digunakan menggunakan sintaks `exec <FD>&-`.
- [ ] **Non-blocking Signals**: Pastikan fungsi trap tidak menjalankan komputasi berat (*blocking*) yang menahan eksekusi sinyal OS berikutnya.
- [ ] **Atomic Mutex**: Hindari menggunakan keberadaan file teks sebagai lockfile (`[ -f lock ]`). Selalu gunakan utilitas berbasis atomic lock seperti `flock(1)` atau manipulasi direktori `mkdir` (yang merupakan atomic system call pada POSIX kernel).

---

## 12. Hands-on Practice

Buatlah struktur direktori kerja dan file implementasi berikut:

```bash
mkdir -p hands-on/m02/
cd hands-on/m02/
touch pipeline_orchestrator.sh
chmod +x pipeline_orchestrator.sh
```

Tuliskan kode berikut ke dalam `pipeline_orchestrator.sh`:

```bash
#!/usr/bin/env bash
# hands-on/m02/pipeline_orchestrator.sh
set -Eeuo pipefail
shopt -s inherit_errexit

# Direktori kerja sementara
WORK_DIR=$(mktemp -d -t pipeline_m02_XXXXXX)

cleanup() {
    local ec=$?
    trap - EXIT INT TERM
    echo "[CLEANUP] Menghapus direktori ${WORK_DIR}..."
    rm -rf "${WORK_DIR}"
    exit "${ec}"
}
trap cleanup EXIT INT TERM

# 1. Alokasi FD 5 untuk file ringkasan performa
exec 5>"${WORK_DIR}/performance.log"

echo "[1/3] Menguji parallel execution pool..."
# Inisialisasi token pipe
TOKEN_FIFO="${WORK_DIR}/token.fifo"
mkfifo "${TOKEN_FIFO}"
exec 6<>"${TOKEN_FIFO}"
rm -f "${TOKEN_FIFO}"

echo "token1" >&6
echo "token2" >&6

# Jalankan 4 subtask dengan limit konkurensi 2
for idx in {1..4}; do
    read -r -u 6 token
    (
        start_time=$(date +%s%N)
        sleep 0.5
        end_time=$(date +%s%N)
        duration=$(( (end_time - start_time) / 1000000 ))
        # Catat metrik langsung ke FD 5 dari dalam proses anak
        printf "Task=%d Duration=%dms\n" "${idx}" "${duration}" >&5
        # Kembalikan token
        echo "${token}" >&6
    ) &
done

wait
echo "[2/3] Paralelisasi selesai. Isi ringkasan performa:"
exec 5>&- # Tutup FD 5
cat "${WORK_DIR}/performance.log"

echo "[3/3] Selesai secara sukses."
```

Jalankan skrip dan periksa output:
```bash
./pipeline_orchestrator.sh
```

---

## 13. Exercise

### Level Easy
Modifikasi skrip di bawah agar nilai variabel `RESULT` tidak hilang saat loop selesai:
```bash
# Problem:
RESULT=0
echo -e "1\n2\n3" | while read -r val; do
    RESULT=$(( RESULT + val ))
done
echo "Total: ${RESULT}" # Harus menghasilkan 6, bukan 0.
```

### Level Medium
Buat sebuah script monitoring sistem yang:
1. Membuka FD kustom `7` yang menulis ke file `/tmp/system_health.log`.
2. Menghasilkan ringkasan penggunaan memory (`free -m`) dan storage (`df -h /`) setiap 2 detik.
3. Menggunakan sinyal `SIGUSR1` untuk mengosongkan (*truncate*) file `/tmp/system_health.log` tanpa menghentikan script yang sedang berjalan.

### Level Hard
Implementasikan skrip bash `resilient_downloader.sh` yang:
1. Mengunduh daftar URL dari file `urls.txt` secara paralel dengan konkurensi tepat `N` pekerjaan (diberikan via flag `-c <concurrency>`).
2. Tidak boleh menggunakan tool eksternal seperti `xargs`, GNU `parallel`, atau `Python`. Murni menggunakan `read`, `wait`, Bash backgrounding `&`, dan FIFO Semaphore.
3. Menangani penekanan `Ctrl+C` (`SIGINT`) dengan membatalkan (*kill*) seluruh download yang sedang berjalan saat itu juga, membersihkan seluruh token FIFO, dan keluar dengan exit code `130`.

---

## 14. Challenge

**Skenario**: Anda adalah Staff Systems Engineer di platform streaming video. Server transkoder Anda menghasilkan ribuan segmen video per detik.
**Tantangan**: Buat sistem pengontrol alur (*Rate Limiter & Load Balancer Engine*) murni dalam Bash yang:
1. Menerima aliran event via stdin secara continuous (stream berkecepatan tinggi).
2. Membagi beban ke 3 backend worker coprocess berbeda (`coproc WORKER_A`, `coproc WORKER_B`, `coproc WORKER_C`) menggunakan algoritma Round-Robin murni berbasis manipulasi File Descriptor.
3. Menerapkan *Dynamic Backpressure*: Jika salah satu worker mendeteksi CPU load sistem lokal > 80% (baca via `/proc/loadavg`), worker tersebut menahan acknowledgement, dan engine utama secara dinamis melewati worker tersebut (*skip & retry next worker*) tanpa kehilangan satu byte pun payload event data.
4. Menggunakan *Zero Disk Write* (seluruh komunikasi dilakukan via pipes/in-memory descriptors).

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda & Analisis Singkat)
1. Apa nilai default File Descriptor untuk `stdin`, `stdout`, dan `stderr`?
2. Apa yang terjadi pada level Linux kernel saat Anda menjalankan sintaks `exec 3<file.txt`?
3. Perintah `set -e` sering gagal menangkap error pada pipeline (`cmd1 | cmd2`). Opsi tambahan apa yang wajib disertakan untuk memperbaiki perilaku ini?
4. Mengapa sintaks `( cd /tmp && rm -rf * )` tidak mengubah working directory dari shell induk pemanggilnya?
5. Apa perbedaan utama pemanggilan `wait` tanpa argumen dibandingkan dengan `wait -n`?

### Bagian 2: Intermediate (Analisis Kasus & Perilaku Sistem)
6. Jelaskan apa yang terjadi jika Anda menulis data ke sebuah *Named Pipe* (FIFO) yang tidak memiliki proses pembaca (*reader*) sama sekali! Sinyal POSIX apa yang akan dibangkitkan kernel?
7. Analisis baris berikut: `exec 3>&1 1>&2 2>&3 3>&-`. Apa efek manipulasi FD tersebut terhadap output perintah berikutnya?
8. Mengapa penggunaan loop `for f in $(ls *.log)` dianggap sebagai antipattern fatal dalam Bash enterprise?
9. Apa perbedaan penggunaan *command substitution* `$(cmd)` dibandingkan *process substitution* `<(cmd)` ditinjau dari alokasi stream memori dan waktu eksekusi proses?
10. Bagaimana cara menutup ujung pembacaan (*read end*) dari custom file descriptor bernomor 4 secara aman?

### Bagian 3: Skenario Kasus Produksi
11. **Skenario Log Collector Hang**: Sebuah skrip kolektor log berjalan lancar selama 3 bulan, namun mendadak berhenti total (*hang*) tanpa error setelah volume data naik 10x lipat. Hasil debugging menunjukkan skrip terjebak di `echo "${payload}" > ${MY_FIFO}`. Mengapa ini terjadi dan bagaimana solusinya?
12. **Skenario Container OOM**: Daemon Bash yang mengorkestrasi backup internal mati terkena OOM (*Out Of Memory*) di lingkungan Kubernetes Pod. Padahal script hanya menjalankan perintah `mysqldump` secara berkala. Analisis kemungkinan kebocoran alokasi proses/subshell pada skrip Bash tersebut!
13. **Skenario Zombie Reaper**: Anda mendesain container Docker dengan Bash script sebagai `ENTRYPOINT` (PID 1). Saat aplikasi berjalan dan meluncurkan banyak proses anak via backgrounding `&`, tabel proses sistem perlahan penuh dengan ribuan entry zombie `defunct`. Mengapa Bash PID 1 tidak me-reap zombie secara otomatis dan bagaimana cara Anda merancang init-loop yang benar di dalam Bash?

---

## 16. Summary

- **File Descriptors (FD)** merupakan antarmuka primitif fundamental Linux untuk abstraksi I/O; penguasaan nomor FD 3–9 memungkinkan orkestrasi pipeline data paralel yang aman dan terisolasi.
- **Subshell** menduplikasi konteks proses menggunakan *Copy-On-Write*, namun memutus alur mutasi variabel ke *parent process*. Hindari penggunaan pipeline yang tidak perlu jika variabel induk harus dimutasi; manfaatkan *Process Substitution*.
- **Konkurensi Enterprise** dalam Bash dapat dibangun secara deterministik menggunakan FIFO sebagai token-based semaphore dan Coprocess untuk komunikasi data dua arah.
- **Resiliensi Sistem** dijamin melalui penanganan sinyal POSIX yang tepat via `trap`, pembersihan descriptor secara deterministik pada exit handler, dan penghindaran kondisi deadlock dengan dupleks file descriptor.