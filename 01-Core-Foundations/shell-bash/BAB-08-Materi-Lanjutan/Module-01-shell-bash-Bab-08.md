# Bab 08 Module 01: Pure Bash Parameter Expansion & In-Memory String Manipulation Engine

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Anda akan memiliki kemampuan terukur untuk:
- Mengeliminasi *bottleneck* performa sistem berbasis Shell dengan mengganti pemanggilan *external subshell/binary* (`sed`, `awk`, `cut`, `basename`, `dirname`) menggunakan native Bash Parameter Expansion.
- Mengimplementasikan seluruh varian manipulasi *string* bawaan Bash—termasuk *conditional fallback assignment*, *prefix/suffix pattern stripping*, *substring slicing*, *pattern search & replace*, *case modification*, dan *indirect expansion*—dengan presisi deterministik.
- Menganalisis alur eksekusi internal Bash parser dalam fase ekspansi parameter guna mencegah kerentanan keamanan seperti *unintended globbing*, *word splitting*, dan *command injection*.
- Merancang modul skrip infrastruktur tingkat produksi yang tahan terhadap *edge-case* (seperti nilai kosong vs tidak terdefinisi/unset) sesuai spesifikasi POSIX dan ekstensi GNU Bash 4.x/5.x.

---

### 2. Prerequisite
Sebelum mempelajari modul ini, Anda wajib memahami:
- **Arsitektur Eksekusi Bash:** Siklus hidup proses, parsing token, perlakuan terhadap Whitespace, Word Splitting, dan Pathname Expansion (Globbing).
- **Bash Primitive Variables:** Deklarasi variabel, pembedaan *environment variable* vs *local shell variable*, dan *quoting rules* (perbedaan mendasar antara evaluasi `""`, `''`, dan tanpa kutip).
- **Status Exit & Error Handling:** Konsep dasar exit codes (`$?`), penanganan status eksekusi dengan `set -e`, `set -u`, `set -o pipefail`.

---

### 3. Concept
Bash Parameter Expansion adalah mekanisme evaluasi variabel internal di mana shell memanipulasi, memotong, memvalidasi, atau mengubah nilai variabel secara langsung di dalam alokasi memori proses shell utama sebelum token dievaluasi menjadi argumen perintah.

Secara konseptual, ekspansi parameter berada pada tahap ke-5 dari 7 tahap *Word Expansion* dalam siklus eksekusi Bash:
1. *Brace Expansion* (`{a,b}`)
2. *Tilde Expansion* (`~`)
3. *Parameter and Variable Expansion* (`$VAR`, `${VAR}`)
4. *Arithmetic Expansion* (`$(( ... ))`)
5. *Command Substitution* (`$( ... )`)
6. *Word Splitting* (berdasarkan `$IFS`)
7. *Pathname Expansion / Globbing* (`*.log`)

Ketika Anda menjalankan perintah eksternal seperti `basename "$PATH_VAR"` atau `echo "$VAR" | cut -d'.' -f1`, Bash terpaksa melakukan *system call* `fork()`, menduplikasi ruang memori proses, melakukan `execve()` untuk memuat binary eksternal ke dalam sistem operasi, membangun IPC pipe, membaca buffer I/O, dan mengeksekusi `wait4()`. 

Sebaliknya, Bash Parameter Expansion (`${PATH_VAR##*/}`) dieksekusi secara instan di ruang *Heap/Stack* internal proses Bash yang sudah ada via *pointer arithmetic* dan *string matching table*. Operasi ini tidak memerlukan alokasi PID baru, tidak melibatkan context switching kernel CPU, dan menghemat ribuan instruksi CPU per iterasi.

---

### 4. Why
Di lingkungan produksi skala besar (telemetri pemrosesan log, CI/CD runners, container initialization, automasi deployment Kubernetes), efisiensi eksekusi skrip Bash sering kali diabaikan hingga menimbulkan degradasi latensi yang masif.

Urgensi teknis penerapan pure Parameter Expansion meliputi:
1. **Pencegahan Fork Bombing & Latency Bloat:** Dalam sebuah perulangan (*loop*) yang memproses 50.000 baris data, pemanggilan `sed` atau `cut` akan memicu 50.000 kali pemanggilan syscall `fork()` dan `execve()`. Operasi ini dapat memakan waktu hingga puluhan detik hingga hitungan menit serta menguras PID table kernel Linux. Parameter expansion native memproses dataset yang sama dalam pecahan milidetik.
2. **Deterministic Sandboxing & Minimalist Runtime:** Pada *container* berbasis scratch atau distroless (yang tidak memiliki coreutils seperti `sed`, `awk`, atau `grep`), native parameter expansion memungkinkan pemrosesan *string*, parsing konfigurasi, dan preparasi path tanpa perlu memasang dependensi biner tambahan yang memperbesar *attack surface* (CVEs).
3. **Imutabilitas State & Safe Error Propagation:** Penggunaan ekspansi parameter bertipe assertion (`${var:?error_message}`) memberikan penghentian eksekusi atomik instan saat variabel kritis tidak terdefinisi, mencegah eksekusi operasi destruktif yang tidak disengaja (misal: `rm -rf /${DIR}`).

---

### 5. What
Komponen manipulasi Bash Parameter Expansion terbagi dalam taksonomi formal berikut:

#### A. Fallback & State Evaluation
- `${VAR:-default}`: Gunakan *default* jika `VAR` belum di-set atau kosong (*null*).
- `${VAR-default}`: Gunakan *default* HANYA jika `VAR` belum di-set (*unset*). Jika kosong (*empty string*), tetap bernilai kosong.
- `${VAR:=default}`: Tetapkan `VAR` dengan *default* jika `VAR` unset/null (melakukan *in-place assignment*).
- `${VAR:?error_message}`: Cetak *error_message* ke `stderr` dan hentikan skrip dengan exit code non-zero jika `VAR` unset/null.
- `${VAR:+alternate}`: Gunakan nilai alternatif jika `VAR` telah di-set dan tidak null; kebalikannya menghasilkan *empty string*.

#### B. Substring Stripping (Pattern Matching via Glob)
- `${VAR#pattern}`: Hapus kecocokan *pattern* terpendek dari **awal** (*prefix*) string.
- `${VAR##pattern}`: Hapus kecocokan *pattern* terpanjang (rakus/*greedy*) dari **awal** (*prefix*) string.
- `${VAR%pattern}`: Hapus kecocokan *pattern* terpendek dari **akhir** (*suffix*) string.
- `${VAR%%pattern}`: Hapus kecocokan *pattern* terpanjang (rakus/*greedy*) dari **akhir** (*suffix*) string.

#### C. Slicing & Offset Manipulation
- `${VAR:offset}`: Ambil substring mulai dari indeks `offset` (0-indexed).
- `${VAR:offset:length}`: Ambil substring mulai dari indeks `offset` sebanyak `length` karakter.
- `${VAR: -offset}`: Ambil substring mulai dari `offset` karakter dari akhir string (wajib diberi spasi sebelum `-` untuk mencegah ambiguasi dengan `${VAR:-default}`).

#### D. Search & Replace
- `${VAR/pattern/replacement}`: Ganti kecocokan **pertama** dari `pattern` dengan `replacement`.
- `${VAR//pattern/replacement}`: Ganti **semua** kecocokan dari `pattern` dengan `replacement`.
- `${VAR/#pattern/replacement}`: Ganti kecocokan HANYA jika berada di **awal** string.
- `${VAR/%pattern/replacement}`: Ganti kecocokan HANYA jika berada di **akhir** string.

#### E. String Metadata, Transformations, & Indirection
- `${#VAR}`: Menghasilkan panjang string (jumlah karakter) dari `VAR`.
- `${VAR^}`, `${VAR^^}`: Ubah karakter pertama / seluruh karakter menjadi huruf kapital (*uppercase*).
- `${VAR,}`, `${VAR,,}`: Ubah karakter pertama / seluruh karakter menjadi huruf kecil (*lowercase*).
- `${!VAR}`: *Indirect expansion*—mengambil nilai dari variabel yang namanya disimpan dalam `VAR`.

---

### 6. How
Di bawah kap mesin (*under the hood*), eksekusi parameter expansion dilakukan oleh parser Bash (`parse.y` dan `subst.c` pada source code GNU Bash).

```
[ Lexer / Reader ]
        │
        ▼
[ Token Parsing: "${VAR##*/}" ]
        │
        ▼
[ Symbol Table Lookup ] ──> Pointer to struct variable (Memory)
        │
        ├── String ditemukan: Ambil base address buffer (char *val)
        │
        ▼
[ Substring/Pattern Matching ] ──> Menggunakan fnmatch(3) atau internal glob match
        │                          (Pointer di-advance tanpa re-alokasi memori berat)
        ▼
[ Output String Allocation ] ───> Menghasilkan pointer baru ke buffer hasil ekspansi
        │
        ▼
[ Placement to AST Command Node ]
```

1. **Tokenization:** Saat parser menemukan karakter `$`, ia mengecek token pembuka `{`. Jika ada, seluruh blok hingga penutup `}` diisolasi sebagai parameter expansion node.
2. **Evaluation:** Engine melakukan lookup pada tabel simbol lokal/global Bash (`struct variable *v = find_variable (name)`).
3. **Pattern Engine:** Operasi seperti `#`, `##`, `%`, `%%` tidak memanggil library regex POSIX (`regcomp`/`regexec`), melainkan menggunakan internal recursive string glob matching (`strmatch`). Ini berjalan langsung di tingkat CPU register dan pointer memori stack, tanpa alokasi subproses.
4. **Result Substitution:** String hasil manipulasi disisipkan menggantikan token parameter pada Abstract Syntax Tree (AST) sebelum perintah final dieksekusi.

---

### 7. Analogy
Bayangkan Anda memiliki sebuah dokumen formulir di meja kerja Anda dan perlu mengubah satu baris teks:
- **Pendekatan Binary Eksternal (`cut`, `sed`, `awk`):** Anda menelepon kurir, memfotokopi dokumen, membungkusnya dalam amplop (*fork*), menyerahkannya ke kurir (*IPC pipe write*), kurir pergi ke kantor percetakan terpisah di ujung kota (*execve* alokasi binary baru), percetakan mengedit satu baris, mengirimkan kurir balik membawa hasil cetak (*IPC pipe read*), lalu Anda membuka amplop dan membaca isinya.
- **Pendekatan Parameter Expansion:** Anda mengambil pensil dan stip yang sudah ada di atas meja Anda, langsung menghapus dan menulis ulang baris tersebut pada lembaran formulir di hadapan Anda secara instan (*in-place memory pointer operation*).

---

### 8. Diagram
Perbandingan arsitektural antara Pipeline Eksternal vs Pure Native Parameter Expansion:

#### Skenario A: Mengambil Nama File Tanpa Ekstensi via External Process
```
+─────────────────────────────────────────────────────────────────────────────+
| BASH PROCESS (PID 1001)                                                     |
|                                                                             |
| $ echo "$FILE" | awk -F. '{print $1}'                                       |
|   │                                                                         |
|   ├── 1. pipe() syscall ───────────────>[ Pipe Buffer Kernel ]              |
|   │                                              │                          |
|   ├── 2. fork() ──> [ Subshell PID 1002 ]        │                          |
|   │                 - execve("echo")             │                          |
|   │                 - write stdout to pipe ──────┘                          |
|   │                                              │                          |
|   ├── 3. fork() ─────────────────────────────────┼──>[ Subshell PID 1003 ]  |
|   │                                              │     - execve("/bin/awk") |
|   │                                              └──── - read stdin         |
|   │                                                    - parse record       |
|   │                                                    - write to pipe      |
|   └── 4. wait4() x 2 (Context switch blocks shell)                          |
+─────────────────────────────────────────────────────────────────────────────+
Latency: ~2 - 10 milliseconds (CPU Intensive / Syscall Overhead)
```

#### Skenario B: Mengambil Nama File Tanpa Ekstensi via Native Expansion
```
+─────────────────────────────────────────────────────────────────────────────+
| BASH PROCESS (PID 1001)                                                     |
|                                                                             |
| $ BASE="${FILE%.*}"                                                         |
|   │                                                                         |
|   ├── 1. Memory Lookup: Symbol Table ("FILE")                               |
|   ├── 2. Pointer Scan: Cari karakter '.' dari arah belakang (strmatch)      |
|   ├── 3. Slice Buffer: Buat slice pointer string tanpa karakter ekstensi     |
|   └── 4. Variable Store: Masukkan ke symbol "BASE"                          |
+─────────────────────────────────────────────────────────────────────────────+
Latency: ~50 - 150 nanoseconds (Zero Syscall / Zero Subprocess)
```

---

### 9. Simple Example
Berikut demonstrasi komparasi sintaks dasar:

```bash
#!/usr/bin/env bash

TARGET_PATH="/var/log/nginx/access.2026-03-31.log"

# 1. Mendapatkan Ekstensi File
# External Anti-Pattern: EXT=$(echo "$TARGET_PATH" | awk -F. '{print $NF}')
EXT="${TARGET_PATH##*.}"
echo "Ext: $EXT" # Output: log

# 2. Mendapatkan Basename (Nama File Saja)
# External Anti-Pattern: BASE=$(basename "$TARGET_PATH")
BASE="${TARGET_PATH##*/}"
echo "Base: $BASE" # Output: access.2026-03-31.log

# 3. Mendapatkan Dirname (Direktori Induk)
# External Anti-Pattern: DIR=$(dirname "$TARGET_PATH")
DIR="${TARGET_PATH%/*}"
echo "Dir: $DIR" # Output: /var/log/nginx

# 4. Search and Replace
# Mengganti ekstensi .log menjadi .gz
ARCHIVE="${TARGET_PATH/%.log/.gz}"
echo "Archive: $ARCHIVE" # Output: /var/log/nginx/access.2026-03-31.gz

# 5. Default Fallback Value
TIMEOUT=""
# Set default 30 detik jika TIMEOUT null/kosong
APPLIED_TIMEOUT="${TIMEOUT:-30}"
echo "Timeout: ${APPLIED_TIMEOUT}s" # Output: 30s
```

---

### 10. Practical Example
Berikut adalah modul parsing konfigurasi database connection string berstandar industri tanpa memanggil binary eksternal satu kali pun.

```bash
#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

###############################################################################
# parse_connection_uri:
# Membedah URI format: engine://username:password@hostname:port/database
# Menggunakan 100% Bash Parameter Expansion.
###############################################################################
parse_connection_uri() {
    local uri="${1:?Error: URI wajib disertakan sebagai argumen 1}"

    # Ekstraksi Engine (Prefix sebelum '://')
    local engine="${uri%%://*}"
    local rest="${uri#*://}"

    # Validasi apakah URI valid
    if [[ "$engine" == "$uri" || -z "$rest" ]]; then
        printf '{"error": "Format URI tidak valid, protocol scheme hilang"}\n' >&2
        return 1
    fi

    # Ekstraksi Database (Suffix setelah '/', jika ada)
    local database=""
    if [[ "$rest" == *"/"* ]]; then
        database="${rest#*/}"
        # Hapus database dari 'rest' untuk mempermudah isolasi segmen sebelumnya
        rest="${rest%%/*}"
    fi

    # Ekstraksi Auth (Username:Password) vs Hostinfo (Host:Port)
    local auth=""
    local hostinfo=""
    if [[ "$rest" == *"@"* ]]; then
        auth="${rest%%@*}"
        hostinfo="${rest#*@}"
    else
        hostinfo="$rest"
    fi

    # Parsing Auth Credential
    local username=""
    local password=""
    if [[ -n "$auth" ]]; then
        if [[ "$auth" == *":"* ]]; then
            username="${auth%%:*}"
            password="${auth#*:}"
        else
            username="$auth"
        fi
    fi

    # Parsing Host dan Port
    local host=""
    local port=""
    if [[ "$hostinfo" == *":"* ]]; then
        host="${hostinfo%%:*}"
        port="${hostinfo#*:}"
    else
        host="$hostinfo"
    fi

    # Berikan default port berbasis engine jika kosong
    if [[ -z "$port" ]]; then
        case "${engine,,}" in
            postgres|postgresql) port="5432" ;;
            mysql)               port="3306" ;;
            redis)               port="6379" ;;
            mongodb)             port="27017" ;;
            *)                   port="unknown" ;;
        esac
    fi

    # Output Data Terstruktur (JSON)
    printf '{\n'
    printf '  "engine": "%s",\n'   "${engine,,}"
    printf '  "username": "%s",\n' "${username}"
    # Masking password untuk alasan keamanan logs: hanya tampilkan 2 karakter awal
    printf '  "password": "%s",\n' "${password:0:2}*****"
    printf '  "host": "%s",\n'     "${host,,}"
    printf '  "port": %s,\n'       "$port"
    printf '  "database": "%s"\n'  "${database}"
    printf '}\n'
}

# Driver Run
TEST_URI="postgresql://dev_admin:SuperSecretK8sP@ss@db-primary.internal.infra:5432/telemetry_db"
parse_connection_uri "$TEST_URI"
```

---

### 11. Real World Example
**Kasus Nyata:** Tim Platform Engineering pada sebuah perusahaan FinTech memproses 120.000 artefak *build metadata* dari microservices dalam pipeline CI/CD Kubernetes.

Skrip legacy sebelumnya menggunakan `cut` dan `sed` untuk memvalidasi Semantic Versioning (`vMAJOR.MINOR.PATCH-PRERELEASE+METADATA`), memisahkan komponen *tag*, dan memvalidasi apakah rilis masuk ke production. Pipeline ini memakan waktu **4 menit 35 detik** hanya untuk operasi parsing string.

Setelah direkayasa ulang menggunakan pure parameter expansion, runtime dipangkas menjadi **1.2 detik** (efisiensi meningkat >99%), menghemat CPU quota pada cluster runner.

```bash
#!/usr/bin/env bash
# Production SemVer Extraction Engine (Zero-Fork Pipeline)
set -euo pipefail

process_artifact_tags() {
    local raw_tag="${1:?Tag missing}"
    
    # Menghapus leading 'v' atau 'V' jika ada
    local clean_tag="${raw_tag#[vV]}"

    # Ekstraksi Build Metadata (Suffix setelah '+')
    local build_metadata=""
    if [[ "$clean_tag" == *"+"* ]]; then
        build_metadata="${clean_tag#*+}"
        clean_tag="${clean_tag%%+*}"
    fi

    # Ekstraksi Prerelease (Suffix setelah '-')
    local prerelease=""
    if [[ "$clean_tag" == *"-"* ]]; then
        prerelease="${clean_tag#*-}"
        clean_tag="${clean_tag%%-*}"
    fi

    # Sisa string WAJIB berbentuk X.Y.Z
    local major="${clean_tag%%.*}"
    local tmp_yz="${clean_tag#*.}"
    local minor="${tmp_yz%%.*}"
    local patch="${tmp_yz#*.}"

    # Validasi bahwa parsing berhasil dan tidak ada komponen bersarang yang lolos
    if [[ -z "$major" || -z "$minor" || -z "$patch" || "$patch" == *.* ]]; then
        printf '[ERROR] Format Tag Non-SemVer Terdeteksi: %s\n' "$raw_tag" >&2
        return 1
    fi

    # Flagging environment release
    local is_production=true
    if [[ -n "$prerelease" ]]; then
        is_production=false
    fi

    printf 'ARTIFACT_MAJOR=%s ARTIFACT_MINOR=%s ARTIFACT_PATCH=%s PRERELEASE=%s PROD=%s\n' \
        "$major" "$minor" "$patch" "${prerelease:-NONE}" "$is_production"
}

# Simulasi batch test input
TAGS=(
    "v1.34.2"
    "2.0.1-rc.1"
    "v3.12.9-beta.2+sha.a1c4df2"
    "4.0.0+meta.only"
)

for tag in "${TAGS[@]}"; do
    process_artifact_tags "$tag"
done
```

---

### 12. Trade-offs

| Dimensi | Native Parameter Expansion | External Binaries (`sed`, `awk`, `cut`) |
| :--- | :--- | :--- |
| **Kecepatan / Latensi** | **Ultra Cepat** (~nanodetik). In-process, bypass syscall overhead. | **Lambat** (~milidetik per pemanggilan). Terbebani overhead `fork-exec`. |
| **Konsumsi Resource** | Sangat Rendah. Menggunakan memori Heap internal shell yang telah teralokasi. | Tinggi. Alokasi duplikasi memori (`copy-on-write`), PCB, file descriptor baru. |
| **Keterbacaan Kode** | Rendah (Kriptik). Simbol seperti `${VAR##*@}` membutuhkan kurva belajar tinggi. | Tinggi / Menengah. Sintaks DSL (`awk '{print $1}'`) lebih deklaratif bagi pemula. |
| **Kompleksitas Parsing** | Terbatas pada pola glob dasar (*fnmatch*). Tidak mendukung Lookaround Regex. | Sangat Tinggi. Mendukung PCRE (*Perl-Compatible Regular Expressions*), arbitrary state logic. |
| **Portabilitas** | Bergantung pada versi interpreter Bash (beberapa fitur butuh Bash >= 4.0). | Tinggi pada sistem Unix standar, asalkan core POSIX tools tersedia. |

---

### 13. When To Use
- **Di dalam Perulangan Intensif (*Hot Loops*):** Memproses baris demi baris file teks, membaca socket streams, atau iterasi array dengan volume data besar.
- **Normalisasi Path & File Name Sanitization:** Operasi pengganti `basename` dan `dirname` di script manajemen storage.
- **Inisialisasi Konfigurasi & Sanitasi Input:** Memberikan nilai fallback variabel environment (misal pada Docker `entrypoint.sh`).
- **Resource-Constrained Systems:** Embedded Linux, minimal container base images (Alpine, BusyBox, Distroless) di mana *tooling overhead* harus ditekan.

---

### 14. When NOT To Use
- **Pemrosesan File Raksasa (Stream Multi-Gigabyte):** Jangan membaca file 10 GB baris-per-baris dengan Bash loop dan parameter expansion. Gunakan engine C stream teroptimasi seperti `sed`, `awk`, atau binary Go/Rust khusus.
- **Kompleksitas Validasi Regex Tingkat Lanjut:** Ketika membutuhkan validasi email strict dengan RFC compliance, recursive balancing, atau *regex backreferences*. Gunakan `perl`, `python`, atau modular validation libraries.
- **Manipulasi Dokumen Terstruktur (JSON/YAML/XML):** Melakukan parsing string manual pada JSON menggunakan parameter expansion adalah *code smell* berbahaya. Gunakan `jq` atau parser berbasis AST yang valid untuk mencegah syntax corruption.

---

### 15. Common Mistakes
1. **Lupa Memberi Spasi pada Negative Slicing:**
   ```bash
   # FATAL: Dianggap sebagai default expansion '${VAR:-3}', BUKAN slicing!
   echo "${STRING:-3}" 
   
   # BENAR: Berikan spasi agar terbaca sebagai indeks negatif
   echo "${STRING: -3}"
   ```
2. **Tertukar Antara `#` (Prefix) dan `%` (Suffix):**
   - Developer sering salah mengingat arah pemotongan.
   - *Mnemonic*: `#` berada di sebelah kiri keyboard (awal/kiri string), `%` berada di sebelah kanan keyboard (akhir/kanan string).
3. **Mengabaikan Karakter Greedy (`##` vs `#`):**
   ```bash
   PATH_SEGMENT="/opt/app/releases/v1/bin"
   echo "${PATH_SEGMENT#*/}"  # Hasil: "opt/app/releases/v1/bin" (Cuma hapus '/' pertama)
   echo "${PATH_SEGMENT##*/}" # Hasil: "bin" (Rakus, hapus sampai '/' terakhir)
   ```
4. **Tidak Melakukan Quoting pada Parameter Expansion:**
   ```bash
   # RENTAN: Jika VAR bernilai "*", Word Splitting dan Globbing akan mengekspansi daftar direktori lokal!
   FILE=${VAR##*/}
   
   # BENAR: Selalu quote ekspansi
   FILE="${VAR##*/}"
   ```

---

### 16. Best Practices
- [ ] **Gunakan Assertion Expansion untuk Variabel Kritis:** Selalu gunakan `${VAR:?error}` sebelum menjalankan perintah destruktif seperti `rm -rf "${TARGET_DIR:?Target dir unset}"/*`.
- [ ] **Gunakan Format Standar POSIX Jika Portabilitas Dibutuhkan:** Karakter case conversion (`^^`, `,,`) adalah fitur Bash 4.x+. Jika skrip harus berjalan di `/bin/sh` (Dash pada Ubuntu atau Ash pada Alpine), gunakan pendekatan strictly POSIX atau explicitly hash-bang `#!/usr/bin/env bash`.
- [ ] **Isolasi Logika String yang Kompleks ke dalam Helper Functions:** Karena sintaks ekspansi parameter berpotensi kriptik, bungkus dalam fungsi deskriptif (misal: `get_extension()`, `strip_protocol()`).
- [ ] **Gunakan Default Value In-Place Assignment (`:=`) Hanya Jika Mutasi Diperlukan:** Berhati-hatilah membedakan `${VAR:=default}` (mengubah nilai asli variabel) dan `${VAR:-default}` (hanya menghasilkan nilai fallback tanpa memutasi variabel asli).

---

### 17. Troubleshooting

#### Case 1: Skrip Langsung Exit Tanpa Error Jelas pada Assertion
- **Penyebab:** `${VAR:?}` memicu exit status 1. Jika skrip berjalan dengan `set -e`, skrip mati seketika.
- **Solusi:** Tangkap error assertion dengan explicit stderr check atau matikan sementara flag exit jika memang ingin menangani degradasi nilai:
  ```bash
  # Lakukan debug via tracing
  bash -x ./script.sh
  ```

#### Case 2: Indirection (`${!VAR}`) Mengembalikan Nilai Kosong
- **Penyebab:** String di dalam `VAR` tidak merujuk secara identik ke nama variabel yang valid atau variabel target bersifat *local scope* di fungsi lain.
  ```bash
  TARGET_ENV="PROD_DB_HOST"
  PROD_DB_HOST="10.0.4.12"
  
  # BENAR:
  echo "${!TARGET_ENV}" # Menghasilkan: 10.0.4.12
  ```

#### Case 3: Pattern Removal Tidak Berfungsi pada Multi-Line Variable
- **Penyebab:** Engine globbing Bash secara default tidak membaca karakter *newline* (`\n`) sebagai wildcard single-line matching layaknya mode `.*` pada regex tertentu.
- **Solusi:** Ubah variabel `$IFS` atau gunakan penggantian newline eksplisit terlebih dahulu via `${VAR//$'\n'/ }`.

---

### 18. Exercise
Ubahlah skrip usang di bawah ini yang menggunakan pemanggilan subshell boros menjadi skrip **pure bash parameter expansion**:

**Skrip Legacy (Performa Buruk):**
```bash
#!/usr/bin/env bash
INPUT_FILE="archive.backup.tar.gz"

# Tugas Anda: Ubah 3 variabel ini menjadi native parameter expansion!
NAME_ONLY=$(echo "$INPUT_FILE" | cut -d'.' -f1)
PRIMARY_EXT=$(echo "$INPUT_FILE" | sed 's/.*\///' | sed 's/^[^\.]*\.//')
FINAL_EXT=$(echo "$INPUT_FILE" | awk -F. '{print $NF}')

echo "Name: $NAME_ONLY"
echo "Primary Ext: $PRIMARY_EXT"
echo "Final Ext: $FINAL_EXT"
```

**Kunci Solusi Evaluasi:**
```bash
#!/usr/bin/env bash
INPUT_FILE="archive.backup.tar.gz"

# Solusi Pure Bash Parameter Expansion
NAME_ONLY="${INPUT_FILE%%.*}"
PRIMARY_EXT="${INPUT_FILE#*.}"
FINAL_EXT="${INPUT_FILE##*.}"

echo "Name: $NAME_ONLY"        # archive
echo "Primary Ext: $PRIMARY_EXT" # backup.tar.gz
echo "Final Ext: $FINAL_EXT"     # gz
```

---

### 19. Challenge
**Deskripsi Skenario Arsitektural:**
Anda diminta merancang fungsi pengurai query parameter URL HTTP berkecepatan tinggi (*zero-fork*) yang akan ditanam pada skrip gateway pelacak logging edge node.

**Spesifikasi Teknis:**
1. Nama fungsi: `extract_query_param`
2. Fungsi menerima dua argumen:
   - Argumen 1: String URL lengkap (contoh: `https://api.internal.net/v1/checkout?client=mobile&session_id=abc12345&debug=true&retry=false`)
   - Argumen 2: Kunci parameter yang dicari (contoh: `session_id`)
3. **Aturan Ketat:**
   - DILARANG menggunakan executable eksternal (`awk`, `sed`, `grep`, `python`, `perl`, `cut`, `tr`).
   - DILARANG menggunakan regex conditional Bash bawaan (`[[ $url =~ ... ]]`). Anda HANYA diperbolehkan menggunakan Bash Parameter Expansion murni (`#`, `##`, `%`, `%%`, `/`, `//`, `:`, length).
   - Penanganan *edge cases*: Jika query parameter tidak ditemukan, return non-zero (`1`) dan cetak string kosong. Jika ada parameter duplikat, ambil nilai yang pertama.

**Solusi Arsitektural Presisi:**
```bash
#!/usr/bin/env bash
set -euo pipefail

extract_query_param() {
    local target_url="${1:?URL required}"
    local search_key="${2:?Search key required}"

    # 1. Isolasi seluruh query string (semua karakter setelah '?')
    if [[ "$target_url" != *"?"* ]]; then
        return 1
    fi
    local query_string="${target_url#*\?}"
    
    # Hapus URL fragment jika ada (semua karakter setelah '#')
    query_string="${query_string%%#*}"

    # 2. Normalisasi: Berikan pembatas '&' di awal dan akhir query string
    #    Ini menjamin semua pasangan kunci selalu diawali '&' dan diakhiri '&'
    local norm="&${query_string}&"

    # 3. Validasi keberadaan pattern: pastikan ada string '&KEY='
    local pattern="&${search_key}="
    if [[ "$norm" != *"$pattern"* ]]; then
        return 1
    fi

    # 4. Potong string di depan kunci pencarian
    #    Hapus semua prefix sampai kecocokan pertama dari '&KEY='
    local match_segment="${norm#*${pattern}}"

    # 5. Potong sisa string setelah karakter '&' pertama
    local value="${match_segment%%&*}"

    printf '%s\n' "$value"
    return 0
}

# Unit Test Verifikasi
URL="https://api.internal.net/v1/checkout?client=mobile&session_id=abc12345&debug=true&retry=false"

printf "Session ID : %s\n" "$(extract_query_param "$URL" "session_id")"
printf "Client     : %s\n" "$(extract_query_param "$URL" "client")"
printf "Debug Flag : %s\n" "$(extract_query_param "$URL" "debug")"

# Test Edge Case Non-Existent Key
if ! extract_query_param "$URL" "auth_token" >/dev/null; then
    printf "Auth Token : [NOT FOUND] (Correct behavior)\n"
fi
```

---

### 20. Summary

| Operasi | Sintaks | Sifat Algoritma | Penggunaan Tipikal Produksi |
| :--- | :--- | :--- | :--- |
| **Default Fallback** | `${VAR:-val}` | Safe fallback check | Pengisian default config environment |
| **In-place Assign** | `${VAR:=val}` | Mutasi variabel | Self-populating configuration state |
| **Assertion Exit** | `${VAR:?err}` | Abort execution | Proteksi parameter kritis skrip infrastruktur |
| **Prefix Strip (Short)**| `${VAR#pattern}` | Non-greedy scan kiri | Menghapus single protocol/prefix scheme |
| **Prefix Strip (Long)** | `${VAR##pattern}`| Greedy scan kiri | Pure `basename` replacement, parsing extension |
| **Suffix Strip (Short)**| `${VAR%pattern}` | Non-greedy scan kanan | Pure `dirname` replacement, extension stripping |
| **Suffix Strip (Long)** | `${VAR%%pattern}`| Greedy scan kanan | Ekstraksi host domain, root base path |
| **Substring Slicing** | `${VAR:off:len}` | Direct pointer offset| Parsing fixed-width token, masking data sensitif |
| **Global Replace** | `${VAR//pat/rep}`| Search scan buffer | Pembersihan sanitasi karakter ilegal / normalisasi |
| **Case Mutation** | `${VAR,,}` / `${VAR^^}`| Direct ASCII shift | Standarisasi input string (case-insensitive checking) |

Penguasaan mendalam atas **Bash Parameter Expansion** adalah pembeda fundamental antara *script writer* amatir dan *Systems Software Engineer*. Dengan memindahkan operasi pemrosesan string dari proses eksternal langsung ke memori internal shell, skrip Anda mencapai tingkat efisiensi komputasi, keandalan, dan keamanan tertinggi di lingkungan infrastruktur modern.