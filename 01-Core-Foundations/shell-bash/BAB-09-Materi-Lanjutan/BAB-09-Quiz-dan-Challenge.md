# BAB 09: Quiz, Challenge, & Knowledge Check
**Defensive Scripting, Testing, & Static Code Analysis**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Anatomi dan Batasan Strict Mode (`set -euo pipefail`):**
   Uraikan implikasi operasional dari masing-masing opsi dalam idiom `set -euo pipefail`. Mengapa `set -e` sering dikritik memberikan ilusi keamanan palsu (*false sense of security*), khususnya saat mengevaluasi perintah di dalam blok kondisional (`if`, `while`), ekspresi compound (`||`, `&&`), atau subshell?

2. **Dinamika Word Splitting dan Globbing pada Unquoted Expansion:**
   Jelaskan secara mendalam bagaimana Bash Parser mengeksekusi ekspansi variabel tanpa tanda kutip (`$var`) dibandingkan dengan variabel yang dikutip ganda (`"$var"`). Bagaimana parameter `IFS` (*Internal Field Separator*) dan fase *Pathname Expansion* memicu celah keamanan fatal pada sistem berkas ketika menangani masukan yang mengandung spasi atau karakter *wildcard*?

3. **Enforcement Kontrak Variabel via Parameter Expansion:**
   Jelaskan perbedaan semantik dan perilaku eksekusi antara ekspresi berikut:
   * `${CONFIG_DIR:-/etc/app}`
   * `${CONFIG_DIR:=/etc/app}`
   * `${CONFIG_DIR:?Path konfigurasi wajib didefinisikan}`
   * `${CONFIG_DIR+alternate}`
   
   Kapan seorang *engineer* harus memprioritaskan operator penugasan kondisional versus penghentian instan menggunakan operator verifikasi kesalahan (`:?`)?

4. **Metodologi dan Batasan Static Code Analysis (ShellCheck):**
   Bagaimana cara kerja parser ShellCheck dalam mengidentifikasi pola anti-defensif secara statis dibandingkan evaluasi dinamis oleh *interpreter* Bash? Jelaskan mengapa ShellCheck dapat mendeteksi potensi *bug* seperti `SC2086` (*Double quote to prevent globbing and word splitting*), namun memiliki keterbatasan mutlak dalam memverifikasi *runtime race conditions* atau efek samping manipulasi direktori secara konkuren.

5. **Arsitektur Pengujian Unit Terisolasi dengan BATS (Bash Automated Testing System):**
   Bagaimana BATS memanfaatkan mekanisme subshell untuk menjamin bahwa eksekusi suatu *test case* (`@test`) tidak mencemari variabel global, *working directory*, atau *environment state* dari *test case* lainnya? Bagaimana alur penanganan asersi terhadap kombinasi `$status`, `$output`, dan `$lines` bekerja secara internal?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Perilaku Sinyal dan Pewarisan Trap (`ERR`, `EXIT`, `RETURN`):**
   Secara *default*, *trap* pada sinyal `ERR` tidak diwariskan ke dalam fungsi, substitusi perintah, atau subshell. Mengapa perilaku default ini berbahaya dalam paradigma *defensive scripting*, dan bagaimana flag `set -E` (`set -o errtrace`) serta `set -T` (`set -o functrace`) memodifikasi tabel penanganan sinyal Bash secara internal?

2. **Diagnostik Pipeline Failure via `${PIPESTATUS[@]}`:**
   Diberikan pipeline kompleks: `cat /var/log/app.json | jq '.error' | grep -v 'ignored' | tee -a /tmp/errors.log`.
   Jika `jq` mengalami *segfault* (exit code 139) tetapi `tee` berhasil menulis file (exit code 0), apa yang terjadi jika script berjalan di bawah `set -e` tanpa `pipefail`? Bagaimana Anda mengabstraksi pembacaan array `${PIPESTATUS[@]}` untuk mengisolasi kegagalan spesifik per stage secara terprogram tanpa merusak alur eksekusi script?

3. **Eksploitasi TOCTOU dan Mitigasi Atomic File Operations:**
   Analisis skrip berikut yang membuat berkas sementara:
   ```bash
   TMP_FILE="/tmp/worker-script.$$.tmp"
   if [ ! -f "$TMP_FILE" ]; then
       echo "data" > "$TMP_FILE"
   fi
   ```
   Tunjukkan celah keamanan *Time-of-Check to Time-of-Use* (TOCTOU) dan *Symlink Attack* pada implementasi di atas. Tuliskan rekonstruksi kode defensif menggunakan `mktemp` dengan parameter isolasi umask dan trap *cleanup* yang *bulletproof*.

4. **Masking Exit Code pada Deklarasi Variabel Lokal:**
   Jelaskan secara mendalam mengapa sintaksis berikut melanggar prinsip *defensive programming*:
   ```bash
   local payload=$(fetch_remote_payload)
   ```
   Bagaimana kata kunci `local` memanipulasi nilai balik `$?` dari pemanggilan perintah di dalam command substitution? Tuliskan pola koreksi yang memisahkan deklarasi lingkup variabel dengan penugasan nilainya.

5. **Hermetic Mocking dan Path Hijacking pada BATS:**
   Saat menguji skrip yang mengeksekusi binary destruktif (misalnya `aws s3 rm` atau `kubectl delete`), bagaimana Anda mendesain mekanisme *mocking* yang hermetis di dalam BATS tanpa mengubah kode produksi? Jelaskan manipulasi `$PATH`, pembuatan stub fungsi, dan ekspor variabel lingkungan untuk memvalidasi *flag* CLI yang diteruskan ke binary tersebut.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Fatal Data Loss pada Automated Retention Script
Sebuah skrip otomatisasi dijalankan via cron job dengan akses root untuk membersihkan artefak build yang sudah kedaluwarsa:
```bash
#!/bin/bash
set -e
TARGET_DIR=$(get_retention_target_directory)
rm -rf $TARGET_DIR/*
```
Suatu hari, fungsi internal `get_retention_target_directory` mengalami kegagalan dependensi jaringan dan mengembalikan string kosong tanpa melempar non-zero exit code. Eksekusi `rm -rf $TARGET_DIR/*` bermutasi menjadi `rm -rf /*`, melenyapkan root filesystem server produksi.

*   **Pertanyaan Diagnostik:**
    1. Mengapa `set -e` sama sekali gagal mencegah eksekusi perintah `rm` tersebut?
    2. Identifikasi minimal 3 lapisan pertahanan (*defense-in-depth*) yang dilanggar pada skrip di atas.
    3. Tulis ulang skrip tersebut dengan menerapkan *parameter expansion assertions*, validasi absolutisme path, perlindungan *word splitting*, dan verifikasi ketersediaan direktori target sebelum tindakan destruktif diizinkan.

### Skenario B: Race Condition dan Deadlock pada Distributed Cron Execution
Sebuah skrip sinkronisasi basis data dijalankan setiap 5 menit pada kluster VM. Karena volume data meningkat drastis, durasi eksekusi skrip melonjak dari 2 menit menjadi 12 menit, menyebabkan multiple instance berjalan secara simultan. Hal ini memicu tabrakan modifikasi state lokal (*data corruption*) dan menghabiskan resource memori server. Upaya awal menggunakan "lock file manual" (`touch /var/lock/sync.lock`) gagal total karena proses yang *crash* meninggalkan *stale lock* permanen.

*   **Pertanyaan Diagnostik:**
    1. Mengapa pendekatan lock berbasis pengecekan dan pembuatan file via `touch` atau `[ -f ... ]` rentan terhadap race condition?
    2. Rancang arsitektur penguncian defensif menggunakan utility sistem `flock` (File Lock) berbasis file descriptor yang terikat langsung pada siklus hidup proses kernel (termasuk *auto-release* saat proses crash atau di-*kill* paksa).
    3. Bagaimana mengimplementasikan penanganan sinyal `SIGINT` dan `SIGTERM` agar melepaskan kunci dan menghapus *working directory* temporer secara elegan?

### Skenario C: CI/CD Pipeline Failure Explosion & ShellCheck Policy Enforcement
Organisasi Anda memiliki repositori monorepo yang berisi lebih dari 200 skrip otomasi Bash yang dikelola oleh 50 engineer. Sebuah rule CI baru ditambahkan untuk memvalidasi seluruh skrip menggunakan `shellcheck --severity=style`. Hasilnya: 1.400 peringatan muncul seketika, memblokir seluruh jalur deployment kritis organisasi. Mayoritas peringatan berkutat pada `SC2086` (Double quote) pada skrip legacy yang sengaja mengandalkan ekspansi argumen, serta peringatan variasi ekspansi array.

*   **Pertanyaan Diagnostik:**
    1. Sebagai Technical Architect, bagaimana Anda merancang strategi adopsi *static code analysis* secara bertahap tanpa menghentikan produktivitas organisasi (*graceful migration*)?
    2. Bagaimana mekanisme konfigurasi `.shellcheckrc` dan teknik *in-line suppression* berbasis justifikasi struktural yang harus distandarisasi?
    3. Buat rancangan script audit CI otomatis yang membedakan verifikasi file yang diubah (*git diff target*) terhadap keseluruhan basis kode (*legacy baseline*), lengkap dengan ambang batas *severity* (error vs warning).

---

## 4. Chapter Challenge

### Tantangan Praktis: Enterprise Safe File Migration & Archive Engine
Anda ditugaskan membangun sebuah modul bash produksi bernama `safe-archive.sh` yang bertugas memindahkan, mengompresi, dan memverifikasi integritas file log dari direktori sumber ke direktori arsip.

#### 1. Problem Statement
Banyak skrip automasi pengarsipan file di infrastruktur legacy gagal menangani nama file yang mengandung karakter khusus (spasi, *newline*, globbing pattern), gagal memverifikasi integritas arsip sebelum menghapus berkas sumber, serta meninggalkan artefak sementara saat script diinterupsi oleh orkestrator (misal: Kubernetes termination grace period).

#### 2. Functional Requirements
*   **Boilerplate Defensif:** Menggunakan `set -euo pipefail` dan trap terpadu untuk `EXIT`, `ERR`, `SIGINT`, dan `SIGTERM`.
*   **Kontrak Argumen:** Menerima flag `-s <source_dir>`, `-d <destination_dir>`, dan flag opsional `-t <retention_days>`. Skrip wajib memvalidasi bahwa argumen yang diberikan bukan direktori root (`/`), bukan string kosong, dan direktori sumber benar-benar dapat dibaca.
*   **Concurrency Guard:** Mencegah multiple execution pada instance direktori yang sama menggunakan kernel file lock (`flock`).
*   **Atomic Processing:**
    *   Buat isolated temporary directory menggunakan `mktemp -d`.
    *   Cari file yang memenuhi kriteria tanpa menggunakan parsing output `ls` (gunakan `find` dengan `-print0` atau bash globbing yang aman).
    *   Kemas file-file tersebut ke dalam tarball terkompresi (`.tar.gz`).
    *   Lakukan verifikasi integritas arsip (`tar -tzf`) dan hitung checksum SHA-256 sebelum file sumber dihapus.
*   **Structured Logging:** Output log wajib memancarkan format standar: `[ISO8601 UTC] [SEVERITY] [PID] - MESSAGE`.

#### 3. Constraints
*   **Zero ShellCheck Violations:** Skrip harus lolos validasi `shellcheck -s bash -S style` tanpa pesan kesalahan ataupun peringatan.
*   **POSIX Compatibility Boundary:** Gunakan utilitas standar sistem Linux modern, hindari Bashisms yang tidak terdefinisi dengan baik. Hindari penggunaan `eval`.
*   **Hermetic Testing Suite:** Wajib menyertakan file pengujian `safe-archive.bats` (BATS) yang mencakup:
    *   *Positive test:* Pengarsipan berhasil dan berkas sumber terhapus.
    *   *Negative test:* Direktori sumber tidak valid atau tidak memiliki izin akses (wajib gagal dengan exit code terstandarisasi).
    *   *Edge case test:* File dengan nama aneh (spasi ganda, karakter `*`, newline) terproses tanpa galat.
    *   *Interruption test:* Skrip membersihkan berkas temporer saat menerima sinyal `SIGINT`.

#### 4. Expected Deliverables
1.  Kode produksi `safe-archive.sh` lengkap dengan dokumentasi blok pertahanan.
2.  Kode pengujian `test/safe-archive.bats` yang memvalidasi integritas fungsionalitas dan skenario kegagalan.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Mekanisme internal eksekusi `set -e`, `set -u`, `set -o pipefail`, beserta kondisi di mana `set -e` di-bypass oleh subshell atau ekspresi logis.
- [ ] Dampak perbedaan antara unquoted `$var`, quoted `"$var"`, unquoted `$@`, dan quoted `"$@"`.
- [ ] Perbedaan siklus hidup dan tabel pewarisan sinyal Bash (`SIGINT`, `SIGTERM`, `EXIT`, `ERR`, `RETURN`) saat menggunakan `trap`.
- [ ] Bahaya TOCTOU (Time-of-Check to Time-of-Use) dan strategi pembuatan file temporer yang atomik via `mktemp`.
- [ ] Implikasi arsitektur dari penggunaan file locking berbasis kernel (`flock`) versus penguncian berbasis filesystem tradisional (`touch`, `mkdir`).
- [ ] Mengapa kata kunci `local` yang disatukan dengan command substitution menyamarkan status error ($?) dari subproses.
- [ ] Batasan fundamental dari Static Analysis (ShellCheck) dan kategori severity kode peringatannya.

### Saya tidak perlu menghafal:
- [ ] Seluruh penomoran kode peringatan ShellCheck (misal: SC2086, SC2155, SC2046) di luar kepala; cukup pahami akar penyebab masalah ketika kode tersebut dilaporkan.
- [ ] Seluruh opsi flag sintaksis eksperimental Bash yang spesifik pada versi mayor minor tertentu (fokus pada fitur standar Bash 4.x ke atas).
- [ ] Implementasi algoritma hash internal untuk verifikasi checksum file (cukup gunakan interface standard seperti `sha256sum`).

### Saya harus bisa melakukan:
- [ ] Menyusun standard defensive header template (`strict mode`, traps, error tracing) pada setiap skrip Bash enterprise baru.
- [ ] Memperbaiki skrip legacy yang memiliki dependensi terhadap unquoted variable expansion tanpa merusak fungsionalitas aslinya.
- [ ] Menulis suite pengujian otomatis berbasis BATS dengan *assertions* pada status keluar (*exit codes*), *stdout*, dan *stderr*.
- [ ] Mengonfigurasi linter ShellCheck pada pipeline CI (seperti GitHub Actions atau GitLab CI) dengan aturan pengecualian terkelola.
- [ ] Melakukan teknik *stubbing* dan *mocking* perintah CLI secara terisolasi tanpa mencemari sistem operasi *host*.
- [ ] Mengimplementasikan *structured logging* dan *error handler* yang menangkap nama berkas sumber, baris kesalahan (*lineno*), dan status kode saat eksekusi terhenti secara tak terduga.