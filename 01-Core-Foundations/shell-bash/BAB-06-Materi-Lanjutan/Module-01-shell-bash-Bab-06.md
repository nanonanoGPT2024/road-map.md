## SEKSI 01 — IDENTITAS MODUL

* **Kurikulum**: Shell & Bash Systems Automation
* **Kategori**: 01-Core-Foundations
* **Bab 06**: Advanced Text Processing
* **Modul 01**: Stream Processing, Pattern Matching, and Data Transformation
* **Kode Modul**: `SB-COR-0601`
* **Prasyarat**:
  * Pemahaman mendalam tentang I/O Redirection, Pipes (`|`), dan File Descriptors (`0`, `1`, `2`).
  * Kemampuan dasar eksekusi perintah POSIX (`cat`, `head`, `tail`, `wc`).
  * Sintaks dasar variabel Bash dan control flow (`if`, `while`).
* **Estimasi Waktu**: 180 menit (Materi: 75 menit, Praktik Hands-On: 105 menit)
* **Tingkat Kesulitan**: Intermediate to Advanced

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis Perbedaan Regular Expressions**: Mengidentifikasi dan membedakan implementasi *Basic Regular Expressions* (BRE), *Extended Regular Expressions* (ERE), dan *Perl-Compatible Regular Expressions* (PCRE) dalam konteks utilitas standar Linux.
2. **Menguasai Stream Editing dengan `sed`**: Mengimplementasikan manipulasi teks baris-per-baris non-interaktif, termasuk substitusi pola kompleks, manipulasi *Pattern Space* dan *Hold Space*, serta eksekusi skrip kondisional.
3. **Membangun Pipeline Ekstraksi Data dengan `awk`**: Menulis program `awk` modular menggunakan pattern-action blocks, manipulasi field/record separators (`FS`, `OFS`, `RS`, `ORS`), array asosiatif, dan fungsi built-in untuk komputasi analitik langsung pada stream teks.
4. **Mengorkestrasi Core Text Utilities**: Mengombinasikan `cut`, `tr`, `sort`, `uniq`, `paste`, dan `join` secara optimal untuk memproses dataset skala menengah tanpa dependensi runtime eksternal (seperti Python atau Perl).
5. **Mengoptimalkan Performa Pipeline Teks**: Mendiagnosis bottleneck I/O, memanfaatkan locale (`LC_ALL=C`), dan mengeliminasi proses redundan (*Useless Use of Cat*) guna mencapai throughput pemrosesan data tertinggi.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                       [ Unix Text Processing Paradigm ]
                                       │
            ┌──────────────────────────┴──────────────────────────┐
            ▼                                                     ▼
   [ Stream Architecture ]                               [ Pattern Engines ]
      - Line-Oriented Processing                            - BRE (sed, grep)
      - Stdout-to-Stdin Piping                              - ERE (egrep, awk, sed -E)
      - Buffering (Block vs Line)                           - PCRE (grep -P)
            │                                                     │
            └──────────────────────────┬──────────────────────────┘
                                       │
                    ┌──────────────────┴──────────────────┐
                    ▼                                     ▼
         [ Stream Editors & Engines ]          [ Specialized Utilities ]
         ┌──────────────────────────┐          ┌───────────────────────┐
         │ sed (Stream Editor)      │          │ cut   (Field slicing) │
         │  - Pattern/Hold Space    │          │ tr    (Char translit) │
         │  - Addressing & Cycles   │          │ sort  (Radix/Merge)   │
         ├──────────────────────────┤          │ uniq  (Deduplication) │
         │ awk (Report Generator)   │          │ paste (Horizontal mrg)│
         │  - Records & Fields      │          │ join  (Relational mrg)│
         │  - Associative Arrays    │          └───────────────────────┘
         │  - BEGIN/END Blocks      │
         └──────────────────────────┘
                                       │
                                       ▼
                       [ Production-Grade Pipelines ]
                          - High-throughput parsing
                          - Log extraction & aggregation
                          - Deterministic formatting
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Dalam filosofi Unix, teks adalah antarmuka universal (*universal interface*). Berbeda dengan sistem operasi berbasis objek murni atau API biner tertutup, subsistem Linux mengekspos konfigurasi kernel (`/proc`, `/sys`), metrik sistem, status jaringan, file konfigurasi, hingga log aplikasi dalam format teks ASCII/UTF-8 mentah.

Menguasai teknik pemrosesan teks tingkat lanjut bukan sekadar kemampuan memanipulasi string, melainkan fondasi utama dari:
1. **Zero-Dependency Troubleshooting**: Pada sistem produksi minimalis (*containers*, *embedded systems*, atau server darurat), *high-level runtimes* seperti Python, Ruby, atau Node.js sering kali tidak tersedia atau dilarang diinstal karena kebijakan keamanan. Toolkit `sed`, `awk`, dan utilitas inti Bash selalu tersedia secara inheren.
2. **High-Throughput Streaming Execution**: Utilitas teks Unix ditulis dalam bahasa C dengan optimasi I/O puluhan tahun. Pipeline `awk` atau `sed` yang dirancang dengan benar mampu memproses jutaan baris log per detik langsung dari disk/stream stdin dengan konsumsi memori resident (RSS) mendekati konstan, jauh lebih efisien dibandingkan skrip berbasis objek yang memuat seluruh file ke dalam RAM.
3. **Observabilitas dan Insiden Respon**: Ketika terjadi lonjakan eror pada kluster web server, operator yang menguasai ekosistem pemrosesan teks dapat mengekstrak IP penyerang, status kode HTTP dominan, dan latensi endpoint dalam hitungan detik via single command-line pipeline.

---

## SEKSI 05 — APA ITU (WHAT)

Pemrosesan teks tingkat lanjut di Bash mengacu pada ekosistem program baris perintah terspesialisasi yang beroperasi di atas aliran data (*streams*) stdin dan stdout. 

Berikut adalah taksonomi komponen utamanya:

### 1. The Regular Expression Spectrum
* **BRE (Basic Regular Expressions)**: Format standar POSIX default untuk `grep` dan `sed`. Karakter meta seperti `(`, `)`, `{`, `}`, `+`, dan `?` dianggap karakter literal kecuali di-escape dengan backslash (`\+`, `\?`, `\{`).
* **ERE (Extended Regular Expressions)**: Format yang lebih ekspresif, diaktifkan via `grep -E` (atau `egrep`), `sed -E` (atau `sed -r`), dan native pada `awk`. Karakter meta `( )`, `{ }`, `+`, `?`, dan `|` langsung diakui tanpa escape.
* **PCRE (Perl-Compatible Regular Expressions)**: Implementasi regex canggih via `grep -P`, mendukung *lookahead*, *lookbehind*, *non-greedy matching*, dan *backreferences* kompleks.

### 2. Stream Editors: `sed`
`sed` adalah editor teks non-interaktif yang membaca data baris demi baris, mengeksekusi sekumpulan instruksi (*commands*) pada buffer memori (*Pattern Space*), dan mengalirkan hasilnya ke stdout. Fitur tingkat lanjutnya mencakup penyimpanan sekunder (*Hold Space*) untuk operasi antar-baris, *branching*, dan pengalamatan selektif berdasarkan nomor baris atau regex.

### 3. Record Processing Language: `awk`
`awk` (dinamai dari penemunya: Aho, Weinberger, Kernighan) adalah bahasa pemrograman pemrosesan data lengkap bertipe Turing-complete yang dioptimalkan untuk memproses data terstruktur berbasis baris (*records*) dan kolom (*fields*). `awk` memecah baris secara otomatis ke dalam variabel `$1`, `$2`, ..., `$NF`, dikontrol oleh field separator (`FS`).

### 4. Auxiliary Core Utilities
* **`tr`**: Utilitas translasi karakter tunggal, penghapusan karakter (*squeeze/delete*), beroperasi strictly pada byte/character level.
* **`cut`**: Pemotong kolom berbasis byte, karakter, atau delimiter statis. Sangat cepat namun terbatas pada delimiter tunggal.
* **`sort`**: Mesin pengurutan berkinerja tinggi berbasis *external merge sort* yang mampu mengurutkan file yang jauh lebih besar dari kapasitas RAM fisik.
* **`uniq`**: Penghapus duplikasi baris sekuensial yang sering dipasangkan dengan `sort`.

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

### Siklus Internal `sed` (The Pattern & Hold Space Engine)

`sed` beroperasi menggunakan dua buffer memori internal:
1. **Pattern Space**: Area kerja aktif tempat baris saat ini dimuat, dimodifikasi, dan dicetak.
2. **Hold Space**: Area memori cadangan yang mempertahankan isinya di antara siklus pembacaan baris, digunakan untuk menyimpan data sementara.

Siklus eksekusi standar `sed` mengikuti alur berikut:
1. Membaca baris dari stdin/file, menghapus karakter *newline* (`\n`), menyimpannya ke **Pattern Space**.
2. Mengevaluasi instruksi berurutan. Jika pola alamat (*address*) cocok:
   * Instruksi dieksekusi memodifikasi Pattern Space.
3. Setelah akhir skrip tercapai, Pattern Space secara otomatis dicetak ke stdout (kecuali flag `-n` aktif), diikuti penambahan kembali *newline*.
4. Pattern Space dikosongkan, dan siklus berulang untuk baris berikutnya.

Manipulasi tingkat lanjut memanfaatkan instruksi perpindahan data antar-buffer:
* `h` / `H`: Salin / Tambahkan (*append*) Pattern Space ke Hold Space.
* `g` / `G`: Ambil (*get*) / Tambahkan (*append*) Hold Space ke Pattern Space.
* `x`: Tukar (*exchange*) isi Pattern Space dan Hold Space.
* `n` / `N`: Baca baris berikutnya ke Pattern Space / Tambahkan baris berikutnya ke Pattern Space tanpa mengosongkan buffer sebelumnya.

### Siklus Eksekusi `awk`

Eksekusi `awk` dibagi ke dalam tiga fase utama:

```
[ INPUT STREAM ]
       │
       ▼
 [ BEGIN Block ]  ──> Dieksekusi SEKALI sebelum baris pertama dibaca.
       │               (Inisialisasi variabel, custom FS, header)
       ▼
 [ Body Loop ]   ──> Mengulang untuk setiap Record (baris):
   ├─ Split       ──> Memecah Record menjadi $1, $2, ... $NF berdasarkan FS
   ├─ Matching    ──> Evaluasi pattern-action pairs: pattern { action }
   └─ Execution   ──> Eksekusi logika internal, akumulasi array, format output
       │
       ▼
  [ END Block ]   ──> Dieksekusi SEKALI setelah EOF (End of File) tercapai.
                       (Agregasi, kalkulasi rata-rata, pelaporan akhir)
```

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### 1. Alur Siklus Hidup Buffer `sed`

```
   INPUT STREAM: Line N
         │
         ▼
  ┌──────────────┐
  │ Read to PS   │ <────────────────────────────────────────┐
  └──────┬───────┘                                          │
         ▼                                                  │
 ┌────────────────┐         h / H (Copy/Append)      ┌──────────────┐
 │ Pattern Space  ├─────────────────────────────────>│  Hold Space  │
 │                │<─────────────────────────────────┤              │
 └───────┬────────┘         g / G (Copy/Append)      └──────────────┘
         │                         ▲
         │           x (Exchange)  │
         │<────────────────────────┘
         ▼
  ┌──────────────┐
  │ Apply Script │ (s/regex/repl/, d, p, dll.)
  └──────┬───────┘
         ▼
    Flag -n ?
    ├── YES ──> [ Tidak Cetak Otomatis ]
    └── NO  ──> Cetak Pattern Space ke STDOUT (+ '\n')
         │
         ▼
  ┌──────────────┐
  │ Clear PS     │
  └──────┬───────┘
         │
         └───────────── Periksa EOF? Jika TIDAK ────────────┘
```

### 2. Pipeline Transformasi Data Multi-Tahap

```
 [ access.log ] 
       │ (Raw Log Stream)
       ▼
 ┌─────────────┐
 │ grep -E     │ Filter baris: Hanya ambil status code 4xx/5xx
 └──────┬──────┘
        │ (Filtered Lines)
        ▼
 ┌─────────────┐
 │ awk         │ Ekstraksi Field: Ambil $1 (IP) & $7 (Endpoint), hitung panjang request
 └──────┬──────┘
        │ (TSV Stream: IP \t Path)
        ▼
 ┌─────────────┐
 │ sort -S 2G  │ Sortir menggunakan buffer memori 2GB (External Merge Sort)
 └──────┬──────┘
        │ (Sorted Stream)
        ▼
 ┌─────────────┐
 │ uniq -c     │ Agregasi: Hitung frekuensi kemunculan kombinasi IP + Path
 └──────┬──────┘
        │ (Aggregated Count)
        ▼
 ┌─────────────┐
 │ sort -rn    │ Urutkan secara numerik terbalik (frekuensi tertinggi di atas)
 └──────┬──────┘
        │ (Top Offender List)
        ▼
 ┌─────────────┐
 │ head -n 10  │ Batasi hanya 10 data teratas
 └─────────────┘
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah demonstrasi pemrosesan dasar menggunakan utilitas inti:

### 1. `sed`: Penggantian Pola Sederhana dan Ekstraksi

```bash
# Data input tiruan
cat << 'EOF' > server.conf
port=8080
bind_address=127.0.0.1
max_connections=100
environment=production
EOF

# Substitusi nilai konfigurasi in-stream
sed -E 's/bind_address=127\.0\.0\.1/bind_address=0.0.0.0/' server.conf

# Ekstraksi nilai hanya dari key 'port' (Pattern suppression via -n)
sed -n 's/^port=\([0-9]\+\)$/\1/p' server.conf
```

### 2. `awk`: Slicing Kolom dan Kondisional

```bash
# Data input proses sistem tiruan
cat << 'EOF' > processes.txt
USER       PID %CPU %MEM    VSZ   RSS STAT START   TIME COMMAND
root         1  0.0  0.1 168432 11204 ?    Ss   00:01   0:02 /sbin/init
postgres  1204  1.2  4.5 450124 98230 ?    S    00:02   1:15 /usr/bin/postgres
nginx     1501  0.5  0.8  89200 16400 ?    S    00:03   0:30 nginx: worker
alice     2100  5.0  2.1 230400 42100 pts/0 R  00:10   3:45 node server.js
EOF

# Filter baris dengan CPU usage > 1.0, cetak PID dan COMMAND
awk '$3 > 1.0 { print "PID: " $2 " -> Command: " $8 }' processes.txt
```

### 3. Kombinasi `tr`, `sort`, `uniq`

```bash
# Ekstraksi kata unik, konversi ke huruf kecil, urutkan berdasarkan frekuensi
echo "Bash text processing is fast. Text parsing in Bash is powerful!" | \
    tr '[:punct:]' ' ' | \
    tr '[:upper:]' '[:lower:]' | \
    tr -s ' ' '\n' | \
    sort | \
    uniq -c | \
    sort -rn
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Kasus Produksi: Analisis Log Web Server (Format Nginx / Apache Combined).
Tugas: Membaca log transaksi HTTP berukuran besar, memfilter request yang gagal (HTTP status code >= 400), menghitung total byte yang ditransfer ke klien untuk setiap status code, dan mencetak top 5 alamat IP yang memicu error terbanyak.

Format Baris Log Nginx Standar:
`$remote_addr - $remote_user [$time_local] "$request" $status $body_bytes_sent "$http_referer" "$http_user_agent"`

Simulasi File Log:
```bash
cat << 'EOF' > /tmp/access.log
192.168.1.50 - - [10/May/2024:14:00:01 +0000] "GET /api/v1/users HTTP/1.1" 200 4523 "-" "Curl/7.68.0"
10.0.0.12 - - [10/May/2024:14:00:02 +0000] "POST /login HTTP/1.1" 401 128 "-" "Mozilla/5.0"
172.16.0.4 - - [10/May/2024:14:00:05 +0000] "GET /dashboard HTTP/1.1" 200 12044 "-" "Mozilla/5.0"
10.0.0.12 - - [10/May/2024:14:00:08 +0000] "POST /login HTTP/1.1" 401 128 "-" "Mozilla/5.0"
192.168.1.99 - - [10/May/2024:14:00:10 +0000] "GET /non-existent HTTP/1.1" 404 231 "-" "Scanner/1.0"
10.0.0.12 - - [10/May/2024:14:00:15 +0000] "GET /admin HTTP/1.1" 403 502 "-" "Mozilla/5.0"
192.168.1.50 - - [10/May/2024:14:00:18 +0000] "GET /api/v1/metrics HTTP/1.1" 500 89 "-" "Prometheus/2.3"
10.0.0.12 - - [10/May/2024:14:00:20 +0000] "POST /login HTTP/1.1" 200 850 "-" "Mozilla/5.0"
192.168.1.99 - - [10/May/2024:14:00:25 +0000] "GET /favicon.ico HTTP/1.1" 404 231 "-" "Scanner/1.0"
EOF
```

### Skrip Otomasi Produksi: `log_analyzer.sh`

```bash
#!/usr/bin/env bash
#
# log_analyzer.sh - Advanced log parsing and aggregation engine
#
set -euo pipefail
IFS=$'\n\t'

# Paksa locale C untuk pemrosesan byte langsung (Performa maksimum regex/sort)
export LC_ALL=C

readonly LOG_FILE="${1:-/tmp/access.log}"

if [[ ! -f "${LOG_FILE}" ]]; then
    printf "Error: File %s tidak ditemukan.\n" "${LOG_FILE}" >&2
    exit 1
fi

printf "=====================================================\n"
printf "  HTTP ERROR AGGREGATION & BANDWIDTH CONSUMPTION     \n"
printf "=====================================================\n"

# 1. Parsing total bandwidth per status code (Hanya status code >= 400)
# Menggunakan awk dengan regex parsing manual untuk field HTTP request
awk '
{
    # Log parsing:
    # $1: IP
    # $9: HTTP Status Code (karena request dibungkus quote, posisi bisa bergeser jika di-split spasi biasa)
    # Pendekatan aman: Split string request menggunakan quote '"'"'
}
{
    # Memecah baris berdasarkan tanda petik ganda
    split($0, quotes, "\"")
    
    # quotes[1] = Bagian sebelum request (IP, timestamp)
    # quotes[2] = Request line ("GET /api... HTTP/1.1")
    # quotes[3] = Sisa baris (" 404 231 - ...")
    
    # Pecah quotes[3] untuk mengambil status code dan bytes
    split(quotes[3], status_bytes, " ")
    status = status_bytes[1]
    bytes  = status_bytes[2]
    
    if (status ~ /^[0-9]{3}$/ && status >= 400) {
        error_count[status]++
        error_bytes[status] += bytes
    }
}
END {
    printf "%-12s | %-12s | %-18s\n", "STATUS CODE", "TOTAL ERROR", "TOTAL BYTES (Bytes)"
    printf "-----------------------------------------------------\n"
    for (code in error_count) {
        printf "%-12s | %-12d | %-18d\n", code, error_count[code], error_bytes[code]
    }
}
' "${LOG_FILE}"

printf "\n=====================================================\n"
printf "  TOP IP SUSPECTS (HIGHEST 4XX/5XX ACTIVITY)         \n"
printf "=====================================================\n"

# 2. Pipeline stream extraction:
# - Awk mengekstrak IP yang menghasilkan status >= 400
# - sort dan uniq -c menghitung frekuensi per IP
# - sort -rn mengurutkan dari pelanggar terbanyak
# - head -n 5 mengambil 5 terbesar
awk '
{
    split($0, quotes, "\"")
    split(quotes[3], tail_fields, " ")
    status = tail_fields[1]
    ip = $1

    if (status ~ /^[0-9]{3}$/ && status >= 400) {
        print ip
    }
}
' "${LOG_FILE}" | \
sort | \
uniq -c | \
sort -rn | \
head -n 5 | \
awk '
BEGIN {
    printf "%-6s | %-15s\n", "HITS", "IP ADDRESS"
    printf "-------------------------\n"
}
{
    printf "%-6d | %-15s\n", $1, $2
}
'
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Dimensi | Pipeline Bash Coreutils (`awk`/`sed`/`sort`) | Skrip High-Level (Python / Perl) | Utilitas Biner Terdedikasi (`goaccess` / `ripgrep`) |
| :--- | :--- | :--- | :--- |
| **Dependensi Eksternal** | **Nol**. Tersedia di semua lingkungan POSIX standar. | Membutuhkan interpreter runtime dan standard library. | Membutuhkan instalasi paket biner manual. |
| **Startup Latency** | Sangat rendah (~1-3 milidetik per invokasi). | Cukup tinggi (Python butuh 30-80ms untuk init runtime). | Sangat rendah (~1-5 milidetik). |
| **Memory Footprint** | Konstan (O(1)) pada mode streaming; Terukur pada `sort` external merge. | Menengah hingga tinggi (overhead alokasi objek memory). | Sangat teroptimasi (zero-copy memory mapped files). |
| **Kompleksitas Logika** | Sulit di-maintain untuk logika multi-kondisi yang kompleks. | Sangat baik. Mendukung OOP, unit testing, modularitas. | Terbatas pada konfigurasi flags / DSL yang disediakan. |
| **Kecepatan Parsing Teks** | Sangat cepat jika dipadukan dengan `LC_ALL=C`. | Sedang (bottleneck pada string manipulation & GIL). | Ekstrem (SIMD acceleration, multi-threaded worker). |

### Kapan Menggunakan Apa:
* Gunakan **Bash Coreutils (`sed`, `awk`, `grep`)**: Untuk scheduled cron jobs, provisioning scripts, filtering log cepat di server produksi, dan operasi di dalam image Docker minimal (*Alpine/Distroless*).
* Pindah ke **Python/Go**: Ketika data memerlukan validasi schema yang rumit, interaksi dengan database relasional/API jaringan eksternal, atau transformasi JSON hirarkis multidimensi yang dalam.

---

## SEKSI 11 — BEST PRACTICES

1. **Definisikan `LC_ALL=C` untuk Pipeline Berperforma Tinggi**:
   Secara default, Linux menggunakan locale UTF-8 (misal `en_US.UTF-8`). Ini memaksa `sort`, `grep`, dan `awk` melakukan kalkulasi multi-byte character encoding dan aturan collation bahasa yang lambat. Menyetel `LC_ALL=C` menginstruksikan utilitas untuk memperlakukan data sebagai byte ASCII mentah murni, menghasilkan peningkatan performa 300% hingga 1000%.
   ```bash
   export LC_ALL=C
   sort dataset.csv
   ```

2. **Gunakan NUL Delimiter (`\0`) untuk Penanganan Jalur File Aman**:
   Karakter spasi, tab, dan newline valid digunakan pada nama file Unix. Selalu gunakan pemisah byte NUL saat memproses file via pipeline.
   ```bash
   find . -type f -name "*.log" -print0 | xargs -0 grep "FATAL"
   ```

3. **Gunakan Single Quotes Secara Konsisten pada Skrip `awk` dan `sed`**:
   Cegah Bash menginterpolasi variabel shell secara tidak sengaja (seperti `$1` atau `$NF`) sebelum skrip sampai ke `awk`.
   * Salah: `awk "{ print $1 }"` (Bash mengganti `$1` dengan argumen pertama skrip bash).
   * Benar: `awk '{ print $1 }'`

4. **Passing Variabel Bash ke Dalam `awk` Menggunakan Argumen `-v`**:
   Hindari konkatenasi string shell ke dalam body skrip `awk` yang rentan injection.
   ```bash
   threshold=500
   awk -v limit="$threshold" '$3 > limit { print $0 }' file.txt
   ```

5. **Hindari *Useless Use of Cat* (UUOC)**:
   Mengarahkan output `cat` ke `grep`, `sed`, atau `awk` menciptakan subshell dan *context-switch* yang tidak perlu.
   * Salah: `cat file.txt | grep "pattern"`
   * Benar: `grep "pattern" file.txt` atau `< file.txt grep "pattern"`

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. In-place Replacement Destruktif dengan `sed -i`
* **Gejala**: Menjalankan `sed -i 's/foo/bar/' file.txt` memicu hilangnya symlink file asli, atau merusak file jika disk penuh di tengah proses.
* **Penyebab**: `sed -i` tidak mengedit file secara langsung di inode yang sama; ia membuat file temporary baru lalu me-rename file tersebut via `rename(2)`. Hal ini memutus hardlink/symlink dan mengubah ownership/permission asli file jika tidak hati-hati.
* **Solusi**: Gunakan opsi ekstensi backup eksplisit seperti `sed -i.bak 's/foo/bar/' file.txt` atau verifikasi symlink sebelum substitusi.

### 2. Inkonsistensi ERE vs BRE pada Utility Berbeda
* **Kasus**: Developer menulis `sed 's/(foo|bar)/baz/' file.txt` dan heran mengapa regex gagal mencocokkan.
* **Penyebab**: Secara default, `sed` menggunakan BRE. Karakter `(` dan `|` dibaca sebagai karakter literal.
* **Solusi**: Tambahkan flag `-E` pada `sed` atau gunakan `sed 's/\(foo\|bar\)/baz/'`.

### 3. Asumsi Field Separator Spasi Tunggal pada `cut`
* **Kasus**: Memotong kolom dari output `ps aux` menggunakan `cut -d' ' -f2`.
* **Penyebab**: Output `ps` menggunakan multiple sequential spaces untuk perataan teks visual. `cut` memperlakukan setiap spasi sebagai delimiter independen, menghasilkan output string kosong.
* **Solusi**: Gunakan `awk '{ print $2 }'` yang secara default menganggap kumpulan whitespace berturut-turut sebagai satu delimiter pemisah.

### 4. Memory Exhaustion pada Perintah `sort` Skala Besar
* **Penyebab**: Melakukan `sort` pada file ratusan gigabyte tanpa menentukan `-T` (*temporary directory*) yang tepat dapat memenuhi partisi `/tmp` default (yang sering kali berupa `tmpfs` berbasis RAM).
* **Solusi**: Arahkan direktori temporary ke disk storage permanen: `sort -T /var/scratch/ -S 4G bigfile.txt`.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1: Ekstraksi Konfigurasi INI Menggunakan `sed`
* **Skenario**: Diberikan file konfigurasi multi-section, buatlah *one-liner* `sed` untuk mengekstrak hanya konfigurasi di dalam section `[database]`.
* **Input File (`config.ini`)**:
  ```ini
  [app]
  env = production
  port = 3000

  [database]
  host = 10.0.8.1
  port = 5432
  user = dbadmin

  [cache]
  redis_host = 127.0.0.1
  ```
* **Tugas**: Ekstrak hanya pasangan key-value di dalam section `[database]` (abaikan header section).
* **Jawaban yang Diharapkan**:
  ```
  host = 10.0.8.1
  port = 5432
  user = dbadmin
  ```

### Latihan 2: Pivot Data Metrik Menggunakan `awk`
* **Skenario**: Terdapat data transaksi metrik server CPU dan Memory dalam format CSV tidak terstruktur.
* **Input File (`metrics.csv`)**:
  ```csv
  srv-alpha,cpu,45
  srv-beta,cpu,80
  srv-alpha,mem,60
  srv-gamma,cpu,30
  srv-beta,mem,92
  srv-gamma,mem,40
  ```
* **Tugas**: Tulis skrip `awk` untuk menghitung dan mencetak rata-rata penggunaan resource per server, serta menandai server yang rata-ratanya > 75 dengan status `ALERT`.

### Latihan 3: Sanitasi dan Normalisasi Stream Data
* **Skenario**: File dump user berisi baris kosong, spasi acak di awal/akhir (*trailing spaces*), dan format nomor telepon yang tidak seragam.
* **Input File (`dirty_users.txt`)**:
  ```
     john.doe@corp.net : +62-811-2233-4455   
  
  alice.smith@corp.net : 0812-9988-7766
     bob.builder@corp.net : +62-813-0011-2233
  ```
* **Tugas**: Buat pipeline bash yang:
  1. Menghilangkan seluruh baris kosong.
  2. Menghilangkan whitespace di awal dan akhir field.
  3. Menstandarkan seluruh nomor telepon lokal (`08xx...`) menjadi format internasional (`+62-8xx...`).
  4. Menghasilkan output format TSV (Tab Separated Values): `EMAIL<tab>PHONE`.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

1. Perhatikan perintah berikut:
   ```bash
   awk 'BEGIN { FS=":" } $3 >= 1000 { print $1 }' /etc/passwd
   ```
   Pada sistem Linux modern, apa potensi bug/kegagalan dari perintah di atas jika field `$3` adalah string angka?
   * A) `FS=":"` tidak valid dieksekusi di blok `BEGIN`.
   * B) Angka `$3` akan dibandingkan secara string (*lexicographically*), sehingga ID `200` akan dianggap lebih besar dari `1000`.
   * C) `awk` akan crash karena variabel `$3` tidak diinisialisasi di blok `BEGIN`.
   * D) Field separator `/etc/passwd` selalu berupa tabulasi, bukan titik dua.

2. Apa fungsi dari perintah `sed -n '5,10p; 11q' large_file.log` dibandingkan `sed -n '5,10p' large_file.log`?
   * A) Tidak ada perbedaan fungsional maupun performa.
   * B) Perintah pertama berhenti membaca input (*quit*) segera setelah baris 11 tercapai, mencegah `sed` memproses sisa file raksasa secara sia-sia.
   * C) Perintah pertama melakukan pengurutan baris dari posisi 5 sampai 10.
   * D) Perintah pertama menyimpan output ke queue buffer memori.

3. Apa hasil output dari pipeline berikut?
   ```bash
   printf "banana\napple\nBanana\nOrange\n" | LC_ALL=C sort | head -n 2
   ```
   * A) `apple`, `banana`
   * B) `Banana`, `Orange`
   * C) `apple`, `Banana`
   * D) `banana`, `apple`

4. Di dalam `sed`, instruksi manakah yang menyalin isi dari *Pattern Space* ke *Hold Space*, menimpa isi *Hold Space* sebelumnya?
   * A) `H`
   * B) `g`
   * C) `h`
   * D) `x`

5. Mengapa pipeline berikut dianggap suboptimal dan berisiko?
   ```bash
   cat names.txt | tr 'a-z' 'A-Z' | sort | uniq | grep "ADMIN"
   ```
   * A) `grep` harus selalu berada di urutan pertama pipeline sebelum `sort` dan `uniq` untuk mereduksi volume data yang dialirkan secara drastis, serta `cat` tidak diperlukan.
   * B) `tr` tidak mendukung rentang sintaks `'a-z'`.
   * C) `uniq` akan menghasilkan error jika tidak ditambahkan argumen `-u`.
   * D) Output `printf` tidak kompatibel dengan `tr`.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **POSIX Standard Manual**:
  * [The Open Group Base Specifications Issue 7 - Shell & Utilities: `awk`](https://pubs.opengroup.org/onlinepubs/9699919799/utilities/awk.html)
  * [The Open Group Base Specifications Issue 7 - Shell & Utilities: `sed`](https://pubs.opengroup.org/onlinepubs/9699919799/utilities/sed.html)
* **GNU Documentation**:
  * [GAWK: Effective AWK Programming (Arnold D. Robbins)](https://www.gnu.org/software/gawk/manual/gawk.html)
  * [GNU sed manual: Stream Editor](https://www.gnu.org/software/sed/manual/sed.html)
* **Buku Referensi Standar**:
  * Dougherty, D., & Robbins, A. (1997). *sed & awk, 2nd Edition*. O'Reilly Media.
  * Robbins, A. (2005). *Classic Shell Scripting*. O'Reilly Media.
* **Artikel Ilmiah / Blog Teknis**:
  * Kernighan, B. W. (1988). *The AWK Programming Language*. Addison-Wesley.
  * Nemeth, E. et al. (2017). *UNIX and Linux System Administration Handbook, 5th Edition* (Bab 2: Scripting and the Shell).

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

* **Pipeline Text Processing** beroperasi di bawah prinsip streaming Unix: data dialirkan melalui stdout/stdin tanpa perlu menyimpan seluruh file ke memori secara bersamaan, menjadikannya scalable untuk data masif.
* **Regular Expressions** terbagi atas **BRE** (default pada `sed` dan basic `grep`) dan **ERE** (default pada `awk`, diaktifkan via `-E` pada `sed` dan `grep`). Menghindari kekeliruan escape karakter meta sangat penting untuk keakuratan matching.
* **`sed`** adalah editor aliran berorientasi instruksi siklik yang mengandalkan **Pattern Space** sebagai buffer kerja utama dan **Hold Space** sebagai storage tambahan untuk manipulasi teks multi-baris non-linear.
* **`awk`** adalah bahasa parsing terstruktur yang membagi record ke dalam field secara deterministik. Penggunaan blok `BEGIN`, siklus per-baris, blok `END`, serta struktur associative array menjadikannya engine sempurna untuk aggregasi, kalkulasi, dan pivoting data tabular.
* **Performa Pipeline** sangat dipengaruhi oleh variabel lingkungan `LC_ALL=C`, urutan filter (filter data seawal mungkin dengan `grep`), dan eliminasi pemanggilan proses yang redundan (*no useless `cat`*).

---

## SEKSI 17 — GLOSARIUM

* **Pattern Space**: Buffer memori jangka pendek yang digunakan oleh `sed` untuk menahan dan memodifikasi teks baris saat ini sebelum diputuskan untuk dicetak atau dibuang.
* **Hold Space**: Buffer memori tambahan pada `sed` yang mempertahankan data melewati siklus pembacaan baris, berfungsi layaknya memori *scratchpad*.
* **FS (Field Separator)**: Variabel internal `awk` yang mendefinisikan pemisah antar-kolom (default adalah sembarang spasi atau tab berturut-turut).
* **OFS (Output Field Separator)**: Karakter pemisah antar-kolom saat `awk` mencetak output menggunakan pemisah koma pada perintah `print` (default: spasi tunggal).
* **RS (Record Separator)**: Karakter pemisah antar-baris data input pada `awk` (default: `\n`).
* **ORS (Output Record Separator)**: Karakter penutup setiap record yang dicetak oleh `awk` (default: `\n`).
* **Collation Order**: Urutan pengurutan karakter yang ditentukan oleh aturan bahasa atau locale sistem operasi; di-bypass demi kecepatan murni oleh `LC_ALL=C`.
* **External Merge Sort**: Algoritma yang digunakan utilitas `sort` Linux untuk mengurutkan dataset yang ukurannya melebihi kapasitas memori RAM dengan memanfaatkan partisi disk sementara.
* **UUOC (Useless Use of Cat)**: Antipattern shell scripting saat perintah `cat` digunakan semata-mata untuk mengalirkan konten file ke stdin program lain yang sebenarnya mampu membaca file tersebut secara langsung.

---

## SEKSI 18 — CATATAN INSTRUKTUR

### Poin Penekanan Pedagogis
* **Instilling "Filter Early" Mindset**: Saat melatih mahasiswa/peserta membangun pipeline, selalu tekankan penempatan perintah `grep` atau filter reduksi di posisi paling awal. Menjalankan `sort` atau transformasi `sed` rumit pada 1.000.000 baris sebelum di-filter adalah kesalahan arsitektur data stream yang fatal.
* **Perangkap Karakter Quoting Bash**: Sering kali peserta mengira error berasal dari skrip `awk` atau `sed`, padahal error terjadi karena shell melakukan evaluasi variabel terlebih dahulu (misal `$1` digantikan nilai kosong oleh Bash). Pastikan peserta selalu membungkus program `awk`/`sed` dengan *single quotes* (`'...'`), kecuali jika mereka sengaja menginterpolasi variabel shell.
* **Demystifying Hold Space**: Hold Space pada `sed` sering dianggap membingungkan. Gunakan analogi register mikroprosesor: Pattern Space adalah *Accumulator Register (A)*, sedangkan Hold Space adalah *Data Register (B)*. Instruksi `x` adalah instruksi swap register.

### Troubleshooting di Kelas
* Jika hasil `sort` pada sistem Linux siswa berbeda urutan huruf besar/kecilnya dengan panduan instruktur, segera instruksikan untuk mengecek `echo $LC_COLLATE` atau langsung paksakan `export LC_ALL=C`.

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi 1.0.0** (Tanggal: 2024-05-10)
  * Rilis awal modul sesuai struktur baku standard kurikulum teknis GEMINI.md 20-Seksi.
  * Materi mendalam komparasi BRE/ERE/PCRE.
  * Implementasi real-world production log analysis script dengan handling nested quotes.
  * Panduan optimasi memori dan I/O streaming (`LC_ALL=C`, external sort).

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya**: `SB-COR-0501` — I/O Redirection, Pipes, and File Descriptor Manipulation
* **Modul Saat Ini**: `SB-COR-0601` — Stream Processing, Pattern Matching, and Data Transformation
* **Modul Berikutnya**: `SB-COR-0701` — Defensive Bash Scripting, Error Handling, and Robust Automation Architecture