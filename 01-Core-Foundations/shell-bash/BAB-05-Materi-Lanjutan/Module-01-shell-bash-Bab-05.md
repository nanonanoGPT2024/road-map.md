## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul:** CORE-BASH-0501
* **Nama Modul:** Fungsi, Subshell & Environment
* **Kategori:** 01-Core-Foundations
* **Tingkat Kesulitan:** Intermediate
* **Prasyarat:**
  * Pemahaman eksekusi perintah dasar Bash dan operator I/O redirection.
  * Pemahaman variabel, parameter ekspansi, dan kontrol alur (*if-else*, *loops*).
  * Pemahaman mendasar tentang konsep proses pada sistem operasi UNIX/Linux (*PID, fork, exec*).
* **Alokasi Waktu:** 180 Menit (Teori: 60 Menit, Praktik Hands-On: 120 Menit)
* **Target Pembaca:** DevOps Engineers, System Administrators, Backend Developers, dan Cloud Infrastructure Engineers yang ingin membangun otomasi Bash tingkat lanjut dengan arsitektur kode modular, minim *side-effect*, dan memiliki isolasi *process context* yang ketat.
* **Tags:** `bash`, `functions`, `subshell`, `environment-variables`, `scoping`, `posix-fork`, `bashpid`

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta diharapkan mampu:

1. **Menganalisis dan Membedakan** konteks eksekusi antara proses induk (*current shell*), pengelompokan perintah (*command grouping* `{ ...; }`), dan proses anak (*subshell* `( ... )`).
2. **Mengimplementasikan** fungsi Bash modular dengan isolasi variabel lokal secara eksplisit (`local`, `declare`) serta mengelola nilai kembalian numerik (*exit code*) dan output data (*stdout*).
3. **Mendiagnosis dan Mengatasi Bug Scoping** yang sering terjadi akibat piping (`|`), termasuk hilangnya mutasi variabel di dalam subshell pipeline.
4. **Menerapkan Mekanisme Inheritance Environment** dengan benar melalui utilitas `export` dan menganalisis dampaknya pada *process tree*.
5. **Menggunakan Arsitektur Subshell Terisolasi** untuk operasi yang berisiko mengubah *global state* (seperti mutasi direktori kerja `cd`, manipulasi umask, atau *temporary traps*).

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```text
                                [Execution Contexts in Bash]
                                             │
               ┌─────────────────────────────┴─────────────────────────────┐
               ▼                                                           ▼
       [Current Shell Context]                                     [Subshell Context]
       (Operates in-process)                                       (Invokes fork() system call)
         ├── Grouping: { cmd; }                                      ├── Parenthesized: ( cmd )
         ├── Bash Functions                                          ├── Pipelines: cmd1 | cmd2
         └── Sourced Scripts (`. script.sh`)                         ├── Command Substitution: $(cmd)
               │                                                     └── Process Substitution: <(cmd)
               ▼                                                           │
       [Variable Scoping]                                                  ▼
         ├── Global Environment (`export`)                         [State Isolation]
         ├── Global Shell Variables                                  ├── Copy of Parent Memory (COW)
         └── Local Scope (`local`, `declare`)                        ├── Changes DO NOT leak upward
                                                                     └── Has distinct $BASHPID != $$
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

1. **Integritas Global State:** Pada arsitektur otomasi infrastruktur skala besar, satu mutasi direktori kerja global (`cd /var/log`) atau modifikasi variabel konfigurasi global dapat merusak alur eksekusi script secara keseluruhan. Memahami subshell memungkinkan isolasi state tanpa efek samping (*zero side-effects*).
2. **Divergensi Antara Data vs Status:** Bash tidak memiliki mekanisme `return` tipe data kompleks (array/string) layaknya bahasa pemrograman tingkat tinggi. Pemahaman yang keliru antara *exit status code* (`return 0-255`) dan *standard output stream* sering kali memicu *silent failure* pada sistem produksi.
3. **The Pipeline Subshell Trap:** Permasalahan paling klasik di mana seorang engineer melakukan iterasi data menggunakan loop yang di-pipe (`cat file | while read ...; do count=$((count+1)); done; echo $count`), lalu mendapati nilai variabel tetap bernilai awal (0). Pemahaman mendalam tentang *subshell fork boundary* menghilangkan frustrasi akibat bug ini.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Fungsi Bash (Bash Functions)
Fungsi dalam Bash adalah kumpulan perintah majemuk (*compound commands*) yang dimuat ke dalam memori shell induk dan dipanggil layaknya *built-in command*. Fungsi dieksekusi di dalam konteks shell yang sama (*current process*), sehingga dapat memanipulasi variabel shell secara langsung kecuali dideklarasikan secara eksplisit dengan keyword `local`.

### 2. Subshell
Subshell adalah duplikasi (*exact clone*) dari proses Bash induk yang dibuat menggunakan *system call* `fork()`. Subshell mewarisi deskriptor file terbuka, variabel environment, dan *shell settings*, namun beroperasi di dalam ruang memori alamat virtual yang terisolasi. Segala mutasi pada variabel, penyesuaian *umask*, atau perpindahan direktori di dalam subshell **tidak akan pernah** mencemari proses induk.

### 3. Environment & Export
*Environment* adalah blok memori khusus tipe *key-value* (berupa *null-terminated strings*) yang diserahkan oleh kernel sistem operasi ke sebuah proses saat inisialisasi. 
* Variabel shell biasa: Hanya eksis di internal proses shell yang aktif.
* `export`: Menandai variabel shell agar dimasukkan ke dalam *process environment table*, sehingga dapat diwariskan ke proses turunan (*child processes* / subshell / binary eksternal).

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

### Mekanisme Fork dan Copy-on-Write (COW)
Ketika Bash mengeksekusi sintaks `(...)` atau pipeline `|`, Bash memanggil `fork()`. Kernel Linux menduplikasi struktur `task_struct`, alokasi Page Table, dan deskriptor file dari shell induk ke proses anak. Melalui mekanisme *Copy-on-Write* (COW), kedua proses awalnya berbagi halaman memori fisik yang sama hingga salah satu proses menulis data baru (misalnya mengubah isi variabel).

### Resolusi Variabel PID vs BASHPID
Terdapat perbedaan fundamental dalam melacak identitas proses:
* `$$`: Merupakan variabel yang mengembalikan PID dari shell utama / shell induk tempat script pertama kali diinisialisasi. Variabel ini **tidak berubah** meskipun dipanggil di dalam subshell.
* `$BASHPID`: Parameter internal Bash yang merefleksikan PID aktual dari proses Bash yang sedang mengeksekusi instruksi tersebut. Di dalam subshell, `$BASHPID` akan bernilai beda dari `$$`.

```bash
echo "Shell Utama PID: $$ (BASHPID: $BASHPID)"
(
    echo "Subshell PID : $$ (BASHPID: $BASHPID)" # $$ tetap sama, $BASHPID berbeda!
)
```

### Eksekusi Grouping: `{}` vs `()`
* Grouping `{ list; }`: Menjalankan *list* perintah di dalam konteks proses saat ini (*current shell execution environment*). Tidak ada pemanggilan `fork()`. Modifikasi variabel dan direktori bersifat permanen terhadap sesi shell. Wajib diakhiri dengan titik koma (`;`) atau *newline* sebelum kurung kurawal tutup.
* Subshell `( list )`: Menjalankan *list* perintah di dalam proses turunan (*child shell*). Menggunakan `fork()`. Modifikasi bersifat lokal bagi subshell tersebut.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### Visualisasi Scoping, Pewarisan Environment, dan Isolasi Subshell

```text
+-----------------------------------------------------------------------------------+
| PROSES INDUK (Parent Shell) [PID: 1050, BASHPID: 1050]                            |
|                                                                                   |
| Variables:                                                                        |
|  - GLOBAL_VAR="Production"                                                        |
|  - LOCAL_SHELL_VAR="Secret123" (Non-exported)                                     |
|                                                                                   |
| Environment Table:                                                                |
|  - [EXPORTED] GLOBAL_VAR="Production"                                             |
|                                                                                   |
| Direktori Aktif: /home/deployer                                                   |
+-----------------------------------------------------------------------------------+
             │                                          │
             │ Panggilan: func_current_shell()           │ Eksekusi: ( subshell )
             │ (In-Process Execution)                   │ via fork()
             ▼                                          ▼
+------------------------------------+   +------------------------------------------+
| EXECUTION CONTEXT: FUNCTION        |   | PROSES ANAK (Subshell)                   |
| (Dalam Memori Parent - PID 1050)   |   | [PID: 1051, BASHPID: 1051]               |
|                                    |   +------------------------------------------+
|  local FUNCTION_VAR="Valid"        |   | Mewarisi:                                |
|  GLOBAL_VAR="Overwritten"          |   |  - GLOBAL_VAR="Production" (Environment) |
|                                    |   |  - LOCAL_SHELL_VAR="Secret123" (Copy)    |
| Efek ke Parent:                    |   |                                          |
|  -> GLOBAL_VAR BERUBAH DI PARENT!  |   | Eksekusi:                                |
|  -> FUNCTION_VAR musnah saat exit  |   |  cd /tmp                                 |
|                                    |   |  GLOBAL_VAR="Destroyed"                  |
|                                    |   |                                          |
|                                    |   | Efek ke Parent:                          |
|                                    |   |  -> Direktori Parent TETAP /home/deployer|
|                                    |   |  -> GLOBAL_VAR Parent TETAP "Overwritten"|
+------------------------------------+   +------------------------------------------+
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

### 1. Fungsi dengan Variabel `local` vs Bocor (*Leakage*)

```bash
#!/usr/bin/env bash
set -euo pipefail

leak_variable() {
    leaked_data="Ini mencemari global namespace"
}

safe_variable() {
    local secured_data="Ini terisolasi di dalam fungsi"
    echo "Dalam safe_variable(): ${secured_data}"
}

leak_variable
echo "Global namespace check: ${leaked_data}" # Berhasil tercetak (Buruk!)

safe_variable
# Baris berikut akan memicu error "unbound variable" karena isolasi scope
# echo "${secured_data}"
```

### 2. Membedakan `return` vs `echo`

```bash
#!/usr/bin/env bash

# Fungsi mengembalikan EXIT CODE (0 - 255)
is_root() {
    if [[ "${EUID}" -eq 0 ]]; then
        return 0 # Status: Sukses
    else
        return 1 # Status: Gagal
    fi
}

# Fungsi mengembalikan DATA (via stdout)
calculate_tax() {
    local amount="$1"
    local rate="0.11"
    # Menghitung data via standard output stream
    awk -v a="${amount}" -v r="${rate}" 'BEGIN { printf "%.2f", a * r }'
}

# Evaluasi Exit Code menggunakan struktur kontrol
if is_root; then
    echo "Status: Berjalan sebagai Superuser."
else
    echo "Status: Berjalan sebagai Unprivileged User."
fi

# Mengambil Data Hasil Eksekusi Fungsi via Command Substitution
tax_result=$(calculate_tax 500000)
echo "Pajak terhitung: IDR ${tax_result}"
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Kasus dunia nyata: Sebuah skrip deployment zero-downtime yang harus mengekstrak arsip konfigurasi ke direktori sementara (*temporary staging*), memvalidasi integritas data, dan membaca parameter tanpa mengubah direktori kerja skrip utama atau mencemari environment global.

```bash
#!/usr/bin/env bash
# ==============================================================================
# SCRIPT: secure_deploy_artifact.sh
# DESKRIPSI: Staging dan deployment konfigurasi menggunakan isolasi subshell
# ==============================================================================
set -euo pipefail

readonly BASE_DIR="/opt/production/app"
readonly ARTIFACT_PATH="/var/backups/release-2026.03.tar.gz"

log_info() {
    local -r timestamp
    timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
    echo "[INFO] [${timestamp}] [PID:${BASHPID}] $*"
}

log_error() {
    local -r timestamp
    timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
    echo "[ERROR] [${timestamp}] [PID:${BASHPID}] $*" >&2
}

# Fungsi demonstrasi pemrosesan staging dalam isolasi subshell
stage_and_verify_artifact() {
    local -r archive_file="$1"
    local staging_dir
    staging_dir=$(mktemp -d -t deploy-XXXXXX)

    log_info "Memulai proses staging di folder: ${staging_dir}"

    # EKSEKUSI SUBSHELL TERISOLASI
    # Menggunakan ( ... ) agar operasi 'cd' dan manipulasi environment 
    # terisolasi total dan mati bersama subshell
    (
        # Set trap internal subshell untuk pembersihan lokal
        trap 'rm -rf "${staging_dir}"; log_info "Staging dir dibersihkan."' EXIT

        # Pindah ke direktori staging (hanya berefek pada subshell ini)
        cd "${staging_dir}"

        log_info "Mengekstrak file payload..."
        tar -xzf "${archive_file}" 2>/dev/null || {
            log_error "Gagal mengekstrak arsip!"
            exit 12
        }

        # Override variabel lokal hanya untuk konfigurasi runtime di subshell
        export RUNTIME_MODE="STAGING_VERIFY"
        
        # Validasi eksistensi manifest
        if [[ ! -f "manifest.json" ]]; then
            log_error "manifest.json tidak ditemukan di dalam arsip!"
            exit 13
        fi

        log_info "Validasi sukses pada BASHPID: ${BASHPID}"
        # Subshell keluar secara normal, trigger EXIT trap lokal
    )

    local -r subshell_exit_code=$?

    if [[ ${subshell_exit_code} -ne 0 ]]; then
        log_error "Subshell staging mengalami kegagalan dengan kode: ${subshell_exit_code}"
        return ${subshell_exit_code}
    fi

    log_info "Kembali ke shell utama [BASHPID: ${BASHPID}]. Direktori aktif: $(pwd)"
    return 0
}

main() {
    log_info "Memulai orchestrator deployment..."
    
    # Mensimulasikan pembuatan mock archive untuk running test
    local mock_archive="/tmp/test_release.tar.gz"
    mkdir -p /tmp/mock_app && touch /tmp/mock_app/manifest.json
    tar -czf "${mock_archive}" -C /tmp/mock_app .
    rm -rf /tmp/mock_app

    # Jalankan fungsi
    stage_and_verify_artifact "${mock_archive}"
    
    # Bersihkan file arsip mock
    rm -f "${mock_archive}"
    
    log_info "Deployment orkestrasi selesai tanpa kebocoran state direktori."
}

main "$@"
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Pendekatan | Kelebihan | Kelemahan | Kapan Digunakan |
| :--- | :--- | :--- | :--- |
| **Current Shell Functions (`func()`)** | Eksekusi sangat cepat (*zero fork overhead*). Dapat memanipulasi variabel shell secara langsung jika diinginkan. | Memori global rentan terhadap polusi jika lupa menyematkan keyword `local`. | Manipulasi internal state, operasi logik umum, helpers perhitungan data. |
| **Command Grouping (`{ list; }`)** | Menggabungkan multiple perintah untuk dialihkan (*redirection*) sekaligus tanpa membuat proses baru. | Berjalan di shell utama; mutasi variabel dan direktori tetap bertahan (*leaking*). | Mengalirkan output dari banyak perintah ke satu file/pipe secara efisien. |
| **Subshell (`( list )`)** | Isolasi total. Perubahan `cd`, `umask`, `trap`, dan variabel langsung musnah saat subshell selesai. | Memiliki penalti performa karena memanggil *system call* `fork()`. Tidak bisa melempar variabel kembali ke parent. | Operasi destruktif sementara, perubahan direktori kerja lokal, kalkulasi sandboxed. |
| **External Script (`./script.sh`)** | Isolasi tingkat sistem operasi (menjalankan `fork()` dan `execve()`). Lingkungan terpisah secara penuh. | Paling lambat (*highest overhead*). Membutuhkan *binary resolution* via disk I/O dan re-parsing parser shell. | Modul independen, *standalone CLI applications*, komponen sistem terpisah. |

---

## SEKSI 11 — BEST PRACTICES

1. **Selalu Gunakan `local` atau `declare` untuk Variabel Fungsi:**
   Jangan pernah mengasumsikan variabel di dalam fungsi bersifat privat. Deklarasikan variabel secara eksplisit sebagai `local`:
   ```bash
   process_data() {
       local item="$1"
       local -i count=0
       local -r max_threshold=100  # Immutable/Read-only
   }
   ```
2. **Hindari Menulis Output Diagnostik ke Standard Output:**
   Fungsi yang mengembalikan data tekstual harus menjaga `stdout` tetap bersih dari log. Alihkan log ke Standard Error (`>&2`):
   ```bash
   get_cluster_ip() {
       echo "Pencarian IP..." >&2  # Diagnostic logging ke stderr
       echo "192.168.1.10"         # Data murni ke stdout
   }
   ```
3. **Gunakan Process Substitution untuk Menghindari Pipeline Subshell Issue:**
   Alih-alih `cmd | while read line`, gunakan `while read line; do ... done < <(cmd)`. Hal ini memastikan *loop body* berjalan di shell utama.
4. **Validasi Jumlah Argumen Posisi:**
   Fungsi harus memvalidasi `$#` di baris pertama eksekusinya untuk menghindari *unbound variable errors* atau kalkulasi `null`.
5. **Karantina Operasi Berbahaya dalam Kurung Lengkung Subshell:**
   Jika sebuah proses membutuhkan perpindahan direktori dinamis (`cd`), bungkus dalam `( cd "$dir" && dangerous_task )` agar shell utama tidak bergeser dari *current working directory*-nya.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. The Pipeline Subshell Trap (Kehilangan Mutasi Data)
```bash
# SALAH: while dijalankan di subshell proses turunan dari pipe
count=0
find . -type f -name "*.log" | while read -r file; do
    ((count++))
done
echo "Total file: ${count}" # OUTPUT SELALU: 0

# BENAR: Menggunakan process substitution agar loop tetap di parent context
count=0
while read -r file; do
    ((count++))
done < <(find . -type f -name "*.log")
echo "Total file: ${count}" # OUTPUT BENAR
```

### 2. Memanggil `exit` di dalam Fungsi, Bukan `return`
```bash
# SALAH: Menghentikan SELURUH skrip aplikasi induk
validate_input() {
    [[ -z "$1" ]] && exit 1 # FATAL! Seluruh script terminasi
}

# BENAR: Keluar dari fungsi saja dan serahkan penanganan error ke caller
validate_input() {
    [[ -z "$1" ]] && return 1
}
```

### 3. Mengira `export` Membawa Perubahan ke Shell Pemanggil (Upward Leak)
Proses anak secara arsitektural di Linux **mustahil** memanipulasi environment proses induk secara langsung:
```bash
# SKRIP: update_env.sh
export BACKEND_URL="https://api.internal.net"

# EKSEKUSI DARI TERMINAL:
# $ ./update_env.sh
# $ echo $BACKEND_URL  --> KOSONG! (Karena ./ dijalankan sebagai child process)
# SOLUSI: Jalankan dengan sourcing jika ingin mengubah parent env:
# $ source ./update_env.sh ATAU . ./update_env.sh
```

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1 (Tingkat Dasar): Scoping Validator
* **Tantangan:** Buat script Bash yang mendeklarasikan variabel global `APP_ENV="production"`. Buat fungsi bernama `set_staging_context()` yang di dalamnya mendeklarasikan variabel `APP_ENV="staging"`. Pastikan bahwa setelah fungsi tersebut dipanggil, nilai `APP_ENV` pada parent context **tetap bernilai** `"production"`.
* **Kriteria Uji:** Cetak isi variabel sebelum, selama eksekusi fungsi, dan sesudah eksekusi fungsi ke konsol.

### Latihan 2 (Tingkat Menengah): Pipeline Refactoring
* **Tantangan:** Diberikan baris kode yang rusak di bawah ini:
  ```bash
  total_bytes=0
  ls -l /var/log | awk '{print $5}' | while read -r bytes; do
      total_bytes=$((total_bytes + bytes))
  done
  echo "Total Storage Used: ${total_bytes}"
  ```
  Perbaiki script di atas tanpa menggunakan file sementara (*temporary files*) agar nilai `total_bytes` merefleksikan akumulasi data secara akurat.

### Latihan 3 (Tingkat Mahir): Transactional Sandbox Runner
* **Tantangan:** Rancang fungsi bernama `execute_in_sandbox()` yang menerima direktori target dan blok perintah string. Fungsi tersebut harus:
  1. Melakukan `cd` ke direktori target.
  2. Menerapkan `umask 077` untuk keamanan file baru.
  3. Menjalankan string instruksi yang dipassing ke dalam fungsi.
  4. Seluruh operasi tersebut harus terisolasi di dalam subshell. Buktikan bahwa umask dan direktori kerja dari caller script tidak mengalami perubahan sedikit pun sebelum dan sesudah eksekusi `execute_in_sandbox`.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

1. **Apa yang terjadi pada memori proses induk ketika sebuah subshell memodifikasi variabel `export`?**
   * A. Variabel pada proses induk otomatis diperbarui karena pointer memori mengarah ke heap yang sama.
   * B. Variabel pada proses induk tidak terpengaruh sama sekali akibat isolasi copy-on-write virtual memory.
   * C. Bash melemparkan runtime warning terkait permission denied.
   * D. Modifikasi hanya terbaca jika parent shell menggunakan built-in `reload`.

2. **Diberikan potongan kode berikut:**
   ```bash
   x=10
   { x=20; }
   ( x=30 )
   echo "$x"
   ```
   **Berapa nilai output yang dicetak ke stdout?**
   * A. 10
   * B. 20
   * C. 30
   * D. Error syntax

3. **Perbedaan utama antara ekspresi `$$` dan `$BASHPID` saat berada di dalam command substitution `$( ... )` adalah...**
   * A. Tidak ada bedanya, keduanya merujuk ke identifier subshell yang baru dibuat.
   * B. `$$` mengembalikan PID dari main shell script, sedangkan `$BASHPID` mengembalikan PID aktual dari subshell.
   * C. `$BASHPID` bersifat POSIX-compliant, sedangkan `$$` spesifik Bash.
   * D. `$$` dinamis diperbarui per subshell, sedangkan `$BASHPID` statis.

4. **Bagaimana cara paling idiomatik bagi sebuah fungsi untuk mengembalikan array atau data kompleks ke shell pemanggil tanpa menggunakan subshell?**
   * A. Menggunakan perintah `return array_name`.
   * B. Mengalihkan data melalui global variable name injection atau Nameref (`declare -n`).
   * C. Memanggil `exit 0` bersamaan dengan parameter array.
   * D. Tidak mungkin dilakukan dalam shell scripting tanpa third-party compiler.

5. **Manakah dari perintah berikut yang dieksekusi di dalam current shell context (TIDAK melakukan fork)?**
   * A. `$(cat /etc/hostname)`
   * B. `cat /etc/passwd | grep root`
   * C. `. ./scripts/config.sh`
   * D. `( cd /tmp && ls )`

---

### Kunci Jawaban & Rasionalisasi
* **1. Jawaban B:** Setiap proses di Linux memiliki ruang alamat terpisah. Subshell adalah proses anak yang menerima salinan lingkungan, sehingga perubahan ke tabel environment lokal anak tidak pernah menular ke atas (*downstream inheritance only*).
* **2. Jawaban B:** Grouping `{ x=20; }` berjalan di current shell dan menimpa variabel global `$x` menjadi 20. Subshell `( x=30 )` memodifikasi salinannya sendiri di child process (menjadi 30) namun mati tanpa memengaruhi parent. Jadi nilai akhir di parent adalah 20.
* **3. Jawaban B:** Variabel `$$` diekspansi menjadi PID dari invocation shell utama dan tidak diupdate oleh subshell. `$BASHPID` adalah internal parameter Bash yang secara akurat menampilkan nomor PID proses saat ini dari tabel proses OS.
* **4. Jawaban B:** Namerefs (`declare -n var_ref="$1"`) memungkinkan referensi pass-by-reference secara langsung ke variabel di outer context tanpa memecah arsitektur variabel ke global scope secara kasar.
* **5. Jawaban C:** Tanda titik (`.`) adalah alias POSIX untuk built-in `source`, yang memerintahkan interpreter membaca dan mengeksekusi file langsung pada *current process context*. Opsi A, B, dan D memicu *fork* subshell.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **Manual System:** `man 1 bash` (Seksi: *COMMAND EXECUTION ENVIRONMENT*, *FUNCTIONS*, *PARAMETERS*).
* **POSIX Base Specifications:** IEEE Std 1003.1-2017 - Chapter 2: Shell Command Language (*Shell Execution Environment*).
* **Buku:** *Wicked Cool Shell Scripts, 2nd Edition* oleh Dave Taylor and Brandon Perry (Starch Press).
* **Dokumentasi Resmi GNU:** [Bash Reference Manual: Command Execution Environment](https://www.gnu.org/software/bash/manual/html_node/Command-Execution-Environment.html).
* **Arsitektur Kernel:** *Advanced Programming in the UNIX Environment (APUE)* oleh W. Richard Stevens (Pemahaman `fork()`, `exec()`, dan *Process Memory Layout*).

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1. **Fungsi Bash** bukan merupakan binary terpisah; mereka dieksekusi di *memory context* proses shell saat ini.
2. Gunakan selalu `local` untuk variabel fungsi guna mencegah **namespace collision** dan *state corruption*.
3. Nilai yang dikeluarkan oleh pernyataan `return` adalah **status numerik** (0–255), bukan tipe data output. Untuk mengembalikan data, gunakan penulisan ke aliran `stdout` dan ditangkap via *command substitution*.
4. **Subshell** `( ... )` menduplikasi proses saat ini via *system call* `fork()`. Modifikasi apapun di dalamnya (variabel, umask, working directory) bersifat terisolasi total.
5. Jalur **Pipeline (`|`)** secara *default* mengeksekusi tahapan pipeline di dalam subshell context. Hindari mutasi variabel penting di dalam pipeline loop dan gunakan **Process Substitution** `< <(...)` sebagai alternatif standar produksi.
6. Perbedaan utama identitas proses: `$$` merepresentasikan *root shell invocation*, sedangkan `$BASHPID` mencerminkan *actual OS PID* pada titik eksekusi tersebut.

---

## SEKSI 17 — GLOSARIUM

* **BASHPID:** Variabel internal GNU Bash yang menghasilkan Process ID aktual dari entitas shell yang tengah mengeksekusi kode, sensitif terhadap subshell boundary.
* **Command Grouping:** Eksekusi serangkaian instruksi yang dikelompokkan dengan kurung kurawal `{ list; }` di dalam konteks memori shell yang aktif tanpa `fork()`.
* **Copy-on-Write (COW):** Mekanisme optimasi manajemen memori kernel di mana proses anak dan induk berbagi halaman fisik data yang sama pasca `fork()` hingga modifikasi data pertama kali dilakukan.
* **Exit Status Code:** Angka integer 8-bit (rentang 0-255) yang dikembalikan oleh setiap perintah atau fungsi Linux untuk mengindikasikan keberhasilan (`0`) atau kode kegagalan (`1-255`).
* **Export:** Atribut instruksi Bash yang memaksa variabel shell didaftarkan ke dalam *global environment table* proses untuk diwariskan ke proses turunan.
* **Fork:** *System call* standar POSIX yang digunakan oleh sistem operasi untuk menduplikasi proses yang sedang berjalan menjadi proses anak.
* **Nameref:** Referensi variabel (`declare -n`) yang mengarahkan pembacaan atau penulisan nilai ke nama variabel lain, sering digunakan untuk *pass-by-reference* pada fungsi.
* **Subshell:** Instance terpisah dari command processor yang diluncurkan oleh shell utama untuk mengeksekusi blok kode terisolasi via sistem kloning proses.

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Titik Krusial Miskonsepsi Siswa:** Siswa yang datang dari latar belakang C, Python, atau Java kerap berasumsi bahwa menulis `return "sukses"` adalah valid di Bash. Tegaskan sejak awal bahwa `return` murni untuk exit status code (`0` hingga `255`). Tunjukkan langsung bagaimana Bash mencetak error `numeric argument required` jika hal ini dilanggar.
* **Eksperimen Interaktif di Kelas:** Bimbing siswa untuk melihat langsung perbedaan `$$` dan `$BASHPID` secara real-time:
  ```bash
  $ echo "Parent -> PID: $$, BASHPID: $BASHPID"
  $ ( echo "Subshell -> PID: $$, BASHPID: $BASHPID" )
  ```
  Tunjukkan bahwa `$$` membohongi mereka jika sedang berada di dalam subshell, sedangkan `$BASHPID` menampilkan kebenaran struktural proses dari OS.
* **Lab Debugging:** Saat demonstrasi pipeline bug, demonstrasikan bagaimana `set -x` sering kali gagal memperingatkan siswa bahwa `while` berada di child subshell. Siswa harus dilatih membaca struktur hierarki proses melalui `pstree` atau `ps -ef --forest`.

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi 1.2.0 (2026-03-30):**
  * Penambahan rincian teknis terkait mekanisme *Copy-on-Write* (COW) pada level POSIX.
  * Pembaruan script deployment praktis menggunakan idiom shell modern (`set -euo pipefail`).
  * Integrasi studi komparasi eksplisit antara `$$` vs `$BASHPID`.
* **Versi 1.1.0 (2024-11-15):**
  * Perbaikan diagram alir ASCII untuk mempertegas batas memori subshell.
  * Penambahan materi Namerefs (`declare -n`) untuk penanganan struktur data array pada fungsi.
* **Versi 1.0.0 (2023-08-01):**
  * Inisiasi rilis modul pertama kurikulum Core-Foundations Shell-Bash.

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya:** [CORE-BASH-0401: Control Structures, Loops & Branching](../04-control-structures/module-01.md)
* **Modul Saat Ini:** CORE-BASH-0501: Fungsi, Subshell & Environment
* **Modul Berikutnya:** [CORE-BASH-0502: Advanced Functions, Traps & Signal Handling](../05-functions-subshell/module-02.md)
* **Indeks Modul:** [Kembali ke Master Kurikulum Shell-Bash](../../README.md)