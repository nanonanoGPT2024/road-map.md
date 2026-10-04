# BAB 10: Quiz, Challenge, & Knowledge Check
**Automasi Enterprise, System Administration, & CI/CD Pipelines**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Mekanisme dan Anatomi `set -euo pipefail`**
   Jelaskan secara mendalam apa yang terjadi pada tingkat interpreter Bash ketika opsi `set -euo pipefail` diaktifkan. Uraikan konsekuensi dari masing-masing flag (`-e`, `-u`, `-o pipefail`), serta sebutkan minimal dua skenario di mana kombinasi ini dapat memicu *false-positive exit* (skrip berhenti secara prematur padahal eksekusi normal/diharapkan).

2. **Diferensiasi Lingkungan Eksekusi: Interactive Login vs Non-Interactive Non-Login Shell**
   Dalam pipeline CI/CD (seperti GitLab CI Runner atau GitHub Actions), skrip Bash dijalankan sebagai *non-interactive, non-login shell*. Analisis perbedaan pemuatan file konfigurasi lingkungan (`/etc/profile`, `~/.bash_profile`, `~/.bashrc`, dan variabel `$BASH_ENV`) antara kedua mode tersebut, serta jelaskan dampaknya terhadap resolusi variabel `$PATH` dan pemanggilan alias/fungsi kustom.

3. **Prinsip Idempotensi dalam Automasi Shell**
   Definisikan konsep *idempotency* dalam konteks administrasi sistem berbasis skrip Bash. Mengapa skrip linear imperatif (seperti runtunan perintah `mkdir`, `useradd`, `sed`) rentan menimbulkan kegagalan fatal pada eksekusi berulang (*re-run*), dan paradigma apa yang harus diterapkan untuk mengubahnya menjadi eksekusi yang konvergen terhadap *state* target?

4. **Konkurensi dan Proteksi Eksekusi Tunggal via File Locking**
   Bandingkan kelemahan mekanisme *PID-file check* konvensional (contoh: membaca `/var/run/app.pid` lalu mengecek via `kill -0 $PID`) dengan implementasi *advisory locking* menggunakan utilitas `flock` berbasis kernel system call (`flock(2)`). Mengapa *PID reuse/recycling* dan *race condition* pada pembuatan PID-file menjadi celah kritis pada sistem enterprise?

5. **Propagasi Sinyal dan Life-Cycle Management (PID 1 Problem)**
   Ketika skrip Bash bertindak sebagai *entrypoint* dalam kontainer Docker/Kubernetes (PID 1), jelaskan bagaimana Bash menangani sinyal standar sistem operasi (`SIGTERM`, `SIGINT`). Mengapa Bash secara default *tidak* meneruskan sinyal tersebut ke *child processes* di latar belakang (*background processes*), dan bagaimana solusi arsitekturalnya menggunakan `trap` dan perintah `exec`?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Masking Exit Code pada Pipeline dan Evaluasi Kondisional**
   Diberikan potongan skrip berikut:
   ```bash
   set -eo pipefail
   if grep -q "CRITICAL" /var/log/app.log | tee /tmp/filtered.log; then
       echo "Alert triggered"
   fi
   echo "System status checked: $?"
   ```
   Bagaimana Bash mengevaluasi status keluar (*exit status*) dari pipeline di dalam klausa `if`? Mengapa `set -e` dinonaktifkan secara implisit di dalam ekspresi pengujian kondisional (`if`, `while`, `until`), dan apa implikasi logisnya terhadap integritas penanganan galat (*error handling*) pada pipeline bertingkat?

2. **Subshell Overhead, Variable Scoping, dan State Leaks**
   Dalam pemrosesan log bervolume besar, seorang engineer menggunakan konstruksi berikut:
   ```bash
   TOTAL_ERRORS=0
   cat /var/log/syslog | while read -r line; do
       if [[ "$line" =~ ERROR ]]; then
           ((TOTAL_ERRORS++))
       fi
   done
   echo "Total: $TOTAL_ERRORS"
   ```
   Mengapa variabel `$TOTAL_ERRORS` selalu mencetak nilai `0` setelah perulangan selesai pada lingkungan Bash standar? Uraikan arsitektur *process fork* yang terjadi pada pipeline tersebut dan sajikan minimal dua pendekatan refaktor tanpa mengorbankan performa memori (termasuk penggunaan *process substitution* dan *lastpipe*).

3. **Kebocoran Kredensial via /proc dan Process Tracing**
   Jelaskan risiko keamanan saat mengeksekusi skrip deployment yang menerima token otentikasi melalui argumen baris perintah (CLI argument, misal: `./deploy.sh --token "$SECRET_TOKEN"`). Bagaimana pengguna lokal unprivileged dapat membaca rahasia tersebut melalui filesystem `/proc`, dan bagaimana Anda mendesain skrip agar mengonsumsi rahasia secara aman melalui *file descriptor*, *environment variable inheritance*, atau *named pipes* (`mkfifo`) dengan proteksi `set +x` yang deterministik?

4. **Atomic File Deployment dan Symlink Flipping**
   Operasi penimpaan file konfigurasi atau direktori aplikasi secara langsung (`cp -rf new_version/* /var/www/app/`) dapat menyebabkan *partial read / inconsistency window* bagi proses yang sedang berjalan. Rancang instruksi Bash yang memanfaatkan utilitas `ln` dan rename atomik tingkat POSIX (`rename(2)`) untuk melakukan rilis versi zero-downtime, lengkap dengan penanganan *symlink traversal safety* dan pembersihan rilis lama (*garbage collection*).

5. **Trap Context Inheritance dan Debugging ERR vs EXIT**
   Ditinjau dari Bash runtime engine, jelaskan perbedaan cakupan (*scope*) dan perilaku pewarisan antara `trap ... EXIT`, `trap ... ERR`, dan `trap ... RETURN`. Dalam kondisi apa flag `set -E` (`set -o errtrace`) mutlak diwajibkan jika Anda membangun kerangka kerja logging kesalahan terpusat (*centralized error handler*) yang melibatkan fungsi tersarang (*nested functions*) dan subshell?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Deadlock Runner CI/CD & Leaked File Descriptors
Sebuah pipeline CI/CD skala besar mengalami pembekuan (*hang* hingga mencapai *timeout limit* 2 jam) secara intermiten pada tahap *integration testing*. Pipeline tersebut menjalankan skrip deployment Bash yang mengeksekusi *background daemon* (sebuah proxy kustom) sebelum menjalankan *test runner*:
```bash
#!/usr/bin/env bash
set -euo pipefail

./bin/service-proxy --port 8080 &
npm run test:integration
```
Meskipun `npm run test:integration` selesai dengan sukses dalam 4 menit dan mencetak exit code 0, job CI runner tidak pernah selesai (*hang* pada *console output stream*).
* **Pertanyaan Diagnostik:**
  1. Analisis akar penyebab teknis (*root cause*) mengapa proses CI runner gagal mendeteksi terminasi skrip meskipun proses utama telah rampung. (Petunjuk: Tinjau status I/O streams `stdout`/`stderr` dan alokasi File Descriptor pada *child process*).
  2. Susun perbaikan skrip secara komprehensif, mencakup penutupan/redireksi *file descriptor*, pencatatan PID background process, pembersihan deterministik (*deterministic cleanup*) via sinyal termination saat skrip utama selesai atau gagal.

---

### Skenario B: Race Condition Multi-Node Deployment pada Shared State
Pada arsitektur auto-scaling, setiap instance baru yang *spin-up* mengeksekusi skrip bootstrapping Bash melalui *cloud-init*. Skrip ini bertugas memperbarui file index cache inventori global yang terletak pada direktori bersama berbasis NFSv4 (`/mnt/shared/inventory.json`).
Ketika terjadi lonjakan lalu lintas yang memicu pembuatan 50 instance baru secara bersamaan, file `inventory.json` mengalami kerusakan data (*corrupted/truncated JSON payload*), dan beberapa node membaca state parsial yang kosong.
* **Pertanyaan Diagnostik:**
  1. Mengapa implementasi penguncian file standar via Bash (seperti pembuatan direktori penanda `mkdir /mnt/shared/lock.dir` atau `flock` standar) dapat gagal atau mengalami anomali latensi pada sistem file terdistribusi/jaringan seperti NFS?
  2. Rancang arsitektur pembaruan file berbasis Bash yang menjamin *data integrity*, mengeliminasi *race condition*, dan mengimplementasikan mekanisme *exponential backoff retry with jitter* murni dalam Bash.

---

### Skenario C: Crash-Loop & Blast Radius Escalation pada Kubernetes InitContainer
Sebuah skrip Bash digunakan sebagai *InitContainer* pada pod kritis di cluster Kubernetes enterprise. Tugasnya adalah melakukan migrasi skema database ringan dan pendaftaran service discovery via API internal:
```bash
#!/usr/bin/env bash
set -e

RESPONSE=$(curl -s -f http://consul.internal:8500/v1/agent/service/register -d @service.json)
MIGRATION_OUT=$(./migrate-db --dry-run=false)
```
Insiden terjadi saat jaringan internal mengalami degradasi paket data (*packet loss* 15%). Beberapa pod masuk ke status `CrashLoopBackOff`, namun dampak yang fatal adalah database kehabisan *connection pool* dan server Consul internal kebanjiran jutaan request (*thundering herd problem*) akibat restart berulang yang sangat cepat dari InitContainer.
* **Pertanyaan Diagnostik:**
  1. Identifikasi kecacatan fatal pada penanganan kegagalan (*error resilience*), manajemen koneksi HTTP (`curl`), dan ketiadaan pembatasan frekuensi eksekusi (*circuit breaking*) pada skrip di atas.
  2. Tuliskan ulang skrip Bash tersebut agar mengimplementasikan:
     - Timeout yang ketat dan deterministik pada level soket dan transfer.
     - Penanganan exit code spesifik dari `curl` dan migrator.
     - Pembatasan restart pod yang tidak destruktif melalui penahanan terminasi terkendali (*controlled delay / graceful failure backoff* sebelum exit 1).

---

## 4. Chapter Challenge

### Tantangan Praktis: Production-Grade Blue/Green Deployment Agent & Rollback Engine

#### Problem Statement
Anda ditugaskan merancang sebuah skrip agen orkestrasi rilis mandiri berbasis Bash (`deploy-agent.sh`) untuk lingkungan bare-metal/VM enterprise. Skrip ini bertugas mengorkestrasi rilis biner aplikasi secara *zero-downtime* menggunakan metodologi Blue/Green deployment lokal, mengelola health check secara otonom, dan melakukan *instant automated rollback* tanpa intervensi manusia jika terjadi anomali performa.

#### Requirements
1. **Engine Semantics & Defensive Flags:**
   - Wajib berjalan pada Bash versi 4.4+.
   - Menerapkan defensive execution (`set -euo pipefail` beserta `trap` penanganan sinyal `SIGINT`, `SIGTERM`, `ERR`, dan `EXIT`).
   - Menerapkan *singleton lock* menggunakan `flock` pada dedicated file descriptor (FD 200) agar dua proses deployment tidak pernah berjalan simultan.

2. **Atomic Symlink Deployment:**
   - Struktur direktori:
     - `/opt/app/releases/<release_id>/` (Target binary baru).
     - `/opt/app/current` (Symlink atomik ke rilis aktif).
     - `/opt/app/previous` (Symlink ke rilis sebelumnya untuk rollback instan).
   - Manipulasi symlink harus dilakukan secara atomik menggunakan utilitas `ln -sfn` dan `mv -Tf` (atau konstruksi atomik setara di POSIX) untuk mencegah broken-link window.

3. **Active Health Monitoring & Automated Rollback:**
   - Lakukan polling terhadap endpoint lokal `http://127.0.0.1:<PORT>/healthz` maksimal 10 iterasi dengan interval 2 detik.
   - Endpoint harus mengembalikan HTTP status code `200` dan payload teks yang mengandung string `"STATUS_OK"`.
   - Jika health check gagal pada batas percobaan, picu fungsi `rollback()`:
     - Balikkan symlink `/opt/app/current` ke rilis sebelumnya.
     - Kirim sinyal restart/reload ke systemd unit (`systemctl restart app.service`).
     - Bersihkan artefak rilis yang rusak.
     - Keluar (*exit*) dengan kode status non-zero yang spesifik.

4. **Structured Logging & Telemetry:**
   - Semua log wajib dicetak ke `stderr` dalam format JSON terstruktur satu baris (*NDJSON/JSON lines*):
     `{"timestamp":"...", "level":"INFO|WARN|ERROR", "release_id":"...", "message":"..."}`.
   - Dilarang keras mengandalkan utilitas eksternal seperti `jq` atau Python untuk memformat JSON; format JSON harus dibangun secara natif melalui manipulasi string Bash.
   - Tutup/redireksi seluruh *leaked file descriptors* pada proses latar belakang.

5. **Secrets & Hygiene Constraints:**
   - Skrip harus menerima konfigurasi via environment variables, namun jika terdapat variabel bertanda `SECRET_*`, nilai tersebut tidak boleh bocor ke trace output (`set -x`) maupun ke file log.
   - Batasi retensi direktori rilis lama maksimal hanya 5 rilis terakhir (implementasikan mekanisme rotasi direktori tertua).

#### Expected Output
Sebuah file skrip tunggal `deploy-agent.sh` yang *self-contained*, sepenuhnya modular (terbagi atas fungsi: `acquire_lock`, `setup_release`, `switch_symlink`, `verify_health`, `rollback`, `cleanup_old_releases`, `log_json`), robust terhadap kegagalan, dan memiliki *clean exit code contract*:
- `0`: Deployment sukses sempurna.
- `10`: Kegagalan akuisisi lock (proses deployment lain sedang berjalan).
- `20`: Kegagalan ekstraksi/penyiapan artefak.
- `30`: Kegagalan verifikasi health check (rollback berhasil dieksekusi).
- `40`: Kegagalan kritis (rollback gagal dieksekusi, sistem butuh intervensi manual).

---

## 5. Knowledge Check & Checklist

Gunakan checklist ini untuk memvalidasi kesiapan teknis sebelum melangkah ke domain orkestrasi skala besar.

### Saya harus memahami:
- [ ] Mengapa `set -e` memiliki pengecualian (*caveats*) pada penanganan error di dalam ekspresi kondisional, subshell, dan perulangan.
- [ ] Perbedaan fundamental antara *buffered* dan *unbuffered* I/O streams serta dampaknya terhadap automasi log real-time.
- [ ] Cara kernel Linux menangani alokasi sinyal ke proses *child* dan mekanisme pelepasan proses yatim (*zombie/orphan reaping*) oleh PID 1.
- [ ] Risiko keamanan race condition tipe TOCTOU (*Time-Of-Check to Time-Of-Use*) pada pengujian ketersediaan file atau resource sebelum eksekusi.
- [ ] Batasan Bash dalam memproses konkurensi skala tinggi dan kapan sebuah task harus didelegasikan ke bahasa kompilasi (Go, Rust) atau sistem automasi (Ansible, Terraform).
- [ ] Mekanisme pewarisan file descriptor saat proses melakukan `fork(2)` dan `execve(2)`.

### Saya tidak perlu menghafal:
- [ ] Seluruh nomor kode sinyal POSIX secara manual (cukup gunakan nama sinyal standar seperti `SIGTERM`, `SIGKILL`, `SIGHUP` via `kill -l`).
- [ ] Sintaks spesifik implementasi non-standar dari tool pihak ketiga; prioritaskan kepatuhan pada POSIX standard dan Bash Built-ins.
- [ ] Regular expression rumit untuk parsing output biner sistem operasi jika tersedia format terstruktur (*flag* `--json`, parsing `/proc`, atau API).

### Saya harus bisa melakukan:
- [ ] Menulis kerangka skrip automasi enterprise dengan konfigurasi *fail-safe* deterministik (`set -euo pipefail`, trap handlers terpusat).
- [ ] Mengimplementasikan *process mutual exclusion* anti-race condition menggunakan `flock` berbasis kernel descriptor.
- [ ] Melakukan debugging proses yang menggantung (*hung/deadlocked script*) di server remote menggunakan `strace -p <PID>`, `lsof`, dan analisis `/proc/<PID>/fd`.
- [ ] Mengembangkan mekanisme deployment *symlink switching* yang atomik tanpa menimbulkan downtime mikrodetik pada layer web server/aplikasi.
- [ ] Mengontrol kebocoran kredensial sensitif pada environment multi-user dengan sanitasi trace logging dan proteksi memori file descriptor.
- [ ] Mendesain integrasi handal antara skrip Bash dengan *system manager* (systemd unit files) dan pipeline CI/CD (runner constraints handling).