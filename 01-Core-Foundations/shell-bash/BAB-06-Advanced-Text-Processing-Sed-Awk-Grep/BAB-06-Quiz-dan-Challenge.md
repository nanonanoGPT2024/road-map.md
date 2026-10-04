# BAB 06: Quiz, Challenge, & Knowledge Check
**Advanced Text Processing: Regex, Sed, & Awk Engine**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Komputasi Mesin Regex — BRE vs. ERE vs. PCRE
Jelaskan perbedaan fundamental dalam representasi sintaksis dan kemampuan komputasi antara *Basic Regular Expressions* (POSIX BRE), *Extended Regular Expressions* (POSIX ERE), dan *Perl-Compatible Regular Expressions* (PCRE). Mengapa pada BRE metakarakter seperti `(`, `)`, `{`, dan `}` memerlukan *backslash escaping* untuk mengaktifkan fungsi khususnya, sedangkan pada ERE sebaliknya? Apa implikasinya terhadap performa ketika memproses stream data skala gigabyte menggunakan `grep` vs `grep -E` vs `grep -P`?

### Soal 1.2: Siklus Eksekusi Sed Engine: Pattern Space vs. Hold Space
Uraikan secara deterministik siklus hidup pemrosesan satu baris teks (*execution cycle*) pada mesin `sed`. Jelaskan:
1. Kapan tepatnya baris input dibaca ke dalam *Pattern Space*.
2. Bagaimana interaksi antara *Pattern Space* dan *Hold Space* berlangsung saat menggunakan perintah `h`, `H`, `g`, `G`, dan `x`.
3. Kapan *newline* (`\n`) dihapus dan ditambahkan kembali selama siklus *read-evaluate-print-flush*.

### Soal 1.3: Arsitektur Parsing Field & Lifecycle Awk Engine
Bagaimana tahapan internal mesin AWK saat memecah stream masukan menjadi *Record* dan *Field*? Jelaskan keterkaitan kausal antara variabel `RS`, `FS`, `ORS`, `OFS`, `NR`, `FNR`, dan `NF`. Apa yang terjadi secara internal pada struktur memori `$0` jika seorang engineer memodifikasi nilai `$1` di tengah proses eksekusi, dan sebaliknya, apa yang terjadi pada `$1..$NF` jika nilai `$0` direassign secara manual?

### Soal 1.4: Engine Complexity: Automata DFA vs. NFA
Mengapa tool POSIX standar seperti GNU `grep` (menggunakan algoritma Thompson-style DFA) kebal terhadap fenomena *Catastrophic Backtracking*, sementara PCRE (menggunakan NFA tradisional) rentan terhadap degradasi performa $O(2^n)$? Jelaskan trade-off fungsional apa yang dikorbankan oleh DFA sehingga tidak dapat mendukung fitur seperti *backreferences* (`\1`) dan *lookaround assertions* (`(?<=...)`).

### Soal 1.5: Mekanisme In-Place Editing (`sed -i`) dan File System Inode
Secara spesifik di level *system call* kernel (seperti `open`, `write`, `rename`, `unlink`), jelaskan apa yang sebenarnya dilakukan oleh flag `-i` pada GNU `sed` dan BSD `sed`. Mengapa operasi `sed -i` berpotensi merusak *hard link*, memutus *symlink*, atau mengubah ownership/permission asli sebuah file jika tidak dikonfigurasi dengan flag khusus?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Multi-line Pattern Processing & Boundary Buffering pada Sed
Diberikan script `sed` yang bertujuan menggabungkan baris berakhiran *backslash* (`\`) dengan baris berikutnya:
```bash
sed -E ':a; /\\$/ { N; s/\\\n//; ta }' input.txt
```
Analisis cara kerja *looping construct* di atas (`:a`, `N`, `ta`). Apa yang terjadi jika file `input.txt` memiliki ukuran 2 GB yang setiap barisnya diakhiri *backslash* tanpa batas pemutus? Di mana batasan buffer *Pattern Space* GNU sed akan tercapai dan bagaimana *behavior* kernel terhadap konsumsi memory proses tersebut?

### Soal 2.2: Memory Leak & Footprint Awk pada Associative Arrays
Perhatikan potongan kode AWK berikut yang digunakan untuk agregasi data log traffic berukuran 50 GB:
```awk
{
    seen[$1][$2] += $3
}
END {
    for (ip in seen)
        for (port in seen[ip])
            print ip, port, seen[ip][port]
}
```
Jelaskan mengapa script ini memicu *Out-Of-Memory* (OOM) Killer pada mesin dengan RAM 8 GB. Bagaimana struktur internal *hash table* pada multi-dimensional associative arrays di GAWK dialokasikan? Solusi arsitektural apa yang harus diimplementasikan agar proses agregasi tetap dapat berjalan dalam *constant memory footprint* ($O(1)$) tanpa dependensi penyimpanan RAM penuh?

### Soal 2.3: POSIX Locale dan Mutasi Multi-byte Character Encoding
Sebuah pipeline `sed -E 's/[A-Z]/X/g'` dijalankan pada file teks berukuran besar dengan encoding UTF-8 di environment server produksi. Pipeline tersebut mengalami degradasi kecepatan hingga 80% lebih lambat dibandingkan server staging. Setelah dicegah OOM, output pada beberapa karakter beraksen (seperti `É` atau `Ü`) menghasilkan byte yang *corrupt*.
1. Jelaskan bagaimana variabel environment `LC_ALL`, `LANG`, dan `LC_CTYPE` mengubah parsing byte-by-byte vs wide-character multi-byte pada Regex Engine.
2. Bagaimana cara memaksa pemrosesan berbasis byte murni berkecepatan tinggi tanpa merusak integritas stream?

### Soal 2.4: Debugging Non-Deterministic Sed/Awk Execution pada Pipeline Streaming
Sebuah script Bash melakukan piping output daemon ke AWK:
```bash
tail -F /var/log/application.log | awk '/ERROR/ { print $0; fflush() }' | sed -u 's/ERROR/CRITICAL/'
```
1. Jelaskan apa perbedaan mekanisme *buffering* antara `fflush()` di AWK, `-u` di `sed`, dan fungsi bawaan libc (`_IONBF`, `_IOLBF`, `_IOFBF`).
2. Apa yang terjadi jika flag `-u` pada `sed` atau `fflush()` pada AWK dihilangkan ketika pipeline tersebut diarahkan ke output file (`> output.log`) alih-alih terminal (stdout TTY)? Jelaskan fenomena block-buffering 4096-byte yang terjadi.

### Soal 2.5: Quoting Hell & Variable Interpolation via Shell Environment
Seorang engineer mencoba memotong teks log berdasarkan variabel shell yang mengandung karakter pemisah dinamis:
```bash
DELIM="[META|DATA]"
RAW_PATTERN='([a-zA-Z0-9]+)\:\"(.*)\"'
# Eksekusi yang gagal:
awk -F "$DELIM" "{ if (\$1 ~ /$RAW_PATTERN/) print \$2 }" file.txt
```
Identifikasi tiga lapisan kesalahan quoting (evaluasi Shell expansion vs AWK lexical scanning) pada kode di atas. Bagaimana cara merancang injeksi variabel Bash ke dalam AWK runtime secara aman menggunakan flag `-v` atau array `ENVIRON` tanpa merusak regex parser?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden CPU Starvation & Bottleneck Parsing pada Pipeline 100 GB/Hari
* **Konteks:** Di sebuah cluster analitik data real-time, terdapat script Bash wrapper yang berjalan setiap 10 menit untuk memproses log transaksi Web Application Firewall (WAF) sebesar ~100 GB per hari. Script ditulis menggunakan pola iterasi:
  ```bash
  cat /var/log/waf/traffic.log | while read -r line; do
      IP=$(echo "$line" | cut -d' ' -f1)
      STATUS=$(echo "$line" | sed -E 's/.*status=([0-9]{3}).*/\1/')
      URL=$(echo "$line" | awk '{print $7}')
      if [ "$STATUS" -ge 500 ]; then
          echo "$IP $URL" >> /var/log/waf/critical_errors.log
      fi
  done
  ```
* **Dampak:** Server mengalami load average > 64 (pada mesin 16 Core), antrean log tertunda hingga berjam-jam (*lagging pipeline*), utilisasi CPU 100% didominasi oleh *system time* akibat context switching dan fork overhead.
* **Pertanyaan Diagnostik:**
  1. Analisis secara matematis berapa kali proses baru di-`fork()` dan di-`exec()` oleh script di atas jika terdapat 1.000.000 baris log.
  2. Rancang ulang arsitektur pipeline tersebut menjadi satu baris instruksi native stream menggunakan GNU AWK murni tanpa subshell, tanpa `cat`, dan tanpa looping shell, dengan throughput minimal 50x lebih cepat.

### Skenario B: Race Condition & Data Corruption pada Dynamic Configuration Updater
* **Konteks:** Sistem automasi provisioning mengeksekusi cronjob setiap 1 menit untuk memperbarui file DNS resolver `/etc/resolv.conf` dan binding HAProxy menggunakan `sed -i`:
  ```bash
  sed -i "s/nameserver .*/nameserver ${NEW_DNS}/" /etc/resolv.conf
  sed -i "s/server backend1 .*/server backend1 ${NEW_BACKEND}:8080 check/" /etc/haproxy/haproxy.cfg
  systemctl reload haproxy
  ```
* **Insiden:** 
  1. Container engine berbasis Kubernetes/Docker yang me-mount `/etc/resolv.conf` sebagai volume bind-mount melaporkan error: `Device or resource busy`.
  2. Pada saat traffic puncak, konfigurasi HAProxy tiba-tiba terbaca kosong (0 bytes) oleh daemon HAProxy, mengakibatkan reload gagal dan *outage* traffic masuk selama 15 menit.
* **Pertanyaan Diagnostik:**
  1. Mengapa `sed -i` memicu error `Device or resource busy` pada Linux mount point (khususnya file yang di-bind-mount secara spesifik di container)?
  2. Bagaimana *race condition* terjadi antara proses pembacaan oleh daemon dan proses *atomic file replacement* oleh `sed -i`?
  3. Berikan pola perbaikan POSIX compliant yang aman (*atomic and non-inode destructive*) untuk memodifikasi konten file konfigurasi tanpa mengubah nomor inode aslinya.

### Skenario C: Architectural Trade-Off: Log Parsing pada Distroless / Restricted Container Environment
* **Konteks:** Arsitek keamanan sistem Anda menghapus seluruh interpreter tingkat tinggi (Python, Perl, Ruby, Node.js) dan package manager dari container base image (*hardened minimal Alpine / Distroless-like Linux*). Yang tersisa di sistem hanyalah binary dasar POSIX: `/bin/sh`, `busybox awk`, dan `busybox sed`. Tim observability membutuhkan parser metrik yang harus mengekstrak data dari structured JSON-like log:
  ```json
  {"timestamp":"2023-10-27T10:00:00Z","level":"ERROR","service":{"name":"auth","id":42},"latency_ms":124.5,"tags":["security","auth-fail"]}
  ```
* **Masalah:** Tidak ada binary `jq`, `python`, atau library C parsing JSON yang tersedia di dalam runtime.
* **Pertanyaan Diagnostik:**
  1. Apa batasan struktural dan resiko terbesar parsing JSON menggunakan Regex/Sed/Awk dibandingkan Abstract Syntax Tree (AST) JSON parser berbasis formal grammar?
  2. Rancang sebuah implementasi parser deterministik menggunakan `awk` (kompatibel dengan Busybox/POSIX Awk) untuk mengekstrak nilai `latency_ms` dan `service.name` dengan handling jika urutan key berubah atau jika terdapat spasi acak di dalam baris payload.
  3. Berikan analisis *trade-off* reliabilitas vs efisiensi resource antara memaksakan shell/awk text parser vs menginjeksikan single binary statically-linked (seperti standalone compiled Go binary atau statically compiled `jq`).

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Log Anonymizer & Metrics Aggregator Engine
Kembangkan sebuah command-line pipeline utility enterprise berbasis Bash, Sed, dan GAWK murni tanpa dependensi compiler atau runtime bahasa tingkat tinggi lain. 

#### Deskripsi Masalah:
Perusahaan Anda mengelola ratusan gateway API yang memproduksi file audit log berskala puluhan gigabyte dengan format gabungan (Combined Log Format yang disematkan Payload Metadata):
```text
192.168.1.150 - admin [27/Oct/2023:14:32:10 +0000] "POST /api/v1/checkout HTTP/1.1" 200 4521 "Bearer eyJhbGciOi..." "Mozilla/5.0" 412ms
10.0.4.22 - - [27/Oct/2023:14:32:11 +0000] "GET /api/v1/products HTTP/1.1" 500 120 "-" "curl/7.68.0" 1250ms
```

#### Spesifikasi Kebutuhan Fungsional (Requirements):
1. **Anonymization Engine (Stream Processing via Sed/Awk):**
   * Alamat IP client (field 1) harus disamarkan: Oktet terakhir harus diubah menjadi `0` (misal: `192.168.1.150` -> `192.168.1.0`).
   * Token Authorization pada referer/payload field (`Bearer eyJ...`) harus di-masking secara deterministik menjadi `Bearer [REDACTED]` tanpa merusak format kutip ganda di sekitarnya.
2. **Metrics Extraction Engine (Single-pass GAWK):**
   * Hitung total hit request.
   * Hitung distribusi kode status HTTP (berapa kali HTTP 200, 400, 500, dst).
   * Identifikasi rata-rata respon latency (dalam milidetik) dan nilai latensi tertinggi (Max Latency) khusus untuk request yang menghasilkan HTTP code $\ge 500$.
   * Ekstrak Top 3 Endpoint URL yang paling banyak diakses.
3. **Execution Delivery:**
   * Script harus beroperasi secara streaming via UNIX pipe (membaca dari `stdin` dan mencetak log tersanitasi ke `stdout`, sedangkan ringkasan analitik dicetak ke `stderr` atau file output metrics terpisah).

#### Batasan Teknis (Constraints):
* Dilarang menggunakan loop shell (`while read`, `for in`).
* Pemrosesan data sebesar 5 GB harus selesai dalam waktu kurang dari 60 detik pada environment 4 Core vCPU.
* Alokasi memori (RAM usage) dari script tidak boleh melampaui **64 MB** selama eksekusi (wajib *constant memory streaming*, kecuali untuk tabel agregasi Top URL yang terbatas).
* Kompatibel dengan POSIX Shell + GNU Coreutils (GAWK / GNU Sed).

#### Expected Output Structure:
```text
=== METRICS SUMMARY (STDERR) ===
Total Requests      : 1000000
HTTP Status Codes   : 200: 950000 | 404: 30000 | 500: 20000
5xx Metrics         : Avg Latency = 845.21ms | Max Latency = 3200ms
Top 3 Endpoints     :
  1. /api/v1/products (650000 hits)
  2. /api/v1/checkout (250000 hits)
  3. /api/v1/auth (100000 hits)
================================
[STDOUT Stream terus mengalirkan anonymized logs...]
```

---

## 5. Knowledge Check & Checklist

Verifikasi pemahaman teknis Anda sebelum melangkah ke bab berikutnya. Tandai checklist berikut secara jujur:

### Saya harus memahami:
- [ ] Perbedaan formal antara *Regular Expression Engines*: DFA (Thompson, finite automata) vs NFA (Backtracking) dan konsekuensi kompleksitas $O(N)$ vs $O(2^N)$.
- [ ] Arsitektur memori internal Sed: Mekanisme kerja, segmentasi, dan pertukaran data antara *Pattern Space* vs *Hold Space*.
- [ ] Kapan Sed berpindah ke siklus berikutnya, kapan membuang newline, dan efek kontrol alur internal (`n`, `N`, `d`, `D`, `p`, `P`, branch `:label`, `b`, `t`).
- [ ] Siklus hidup Parsing AWK: Mekanisme inisialisasi `BEGIN`, looping record per baris, evaluasi kondisi pattern-action, parsing delimiter dinamis, dan cleanup `END`.
- [ ] Semantik I/O Low-level: Bagaimana `sed -i` bekerja terhadap *filesystem inodes*, file descriptor locks, dan symlink resolution.
- [ ] Aturan rekalkulasi AWK: Hubungan langsung antara modifikasi field `$1..$NF`, manipulasi string masukan mentah `$0`, serta variabel `FS` dan `OFS`.

### Saya tidak perlu menghafal:
- [ ] Seluruh tabel karakter ASCII octal/hexadecimal untuk transliterasi (`\033`, `\x1b`, dll) — gunakan dokumentasi referensi saat parsing binary streams.
- [ ] Semua metakarakter POSIX character classes (`[:alnum:]`, `[:punct:]`, dll) — cukup pahami konsep pemetaan multi-byte locale engine-nya.
- [ ] Ekstensi sintaks non-standar proprietary milik vendor Awk tertentu (seperti Tawk, Mawk, atau BWK Awk) — prioritaskan GNU Awk (gawk) dan POSIX Standard Awk.

### Saya harus bisa melakukan:
- [ ] Mengonversi loop bash (`while read`) yang lambat dan boros CPU menjadi single-pass streaming processing pipeline menggunakan Awk atau Sed murni.
- [ ] Menulis regular expressions deterministik yang bebas dari risiko *Catastrophic Backtracking* untuk pemrosesan teks throughput tinggi.
- [ ] Mengoperasikan manipulasi teks multi-baris (*multiline transformation*) menggunakan instruksi pattern/hold buffer `sed` tanpa bantuan high-level script.
- [ ] Melakukan isolasi dan debugging pipeline text processing yang mengalami *pipe-buffering latency* menggunakan `fflush()`, `stdbuf`, atau flag unbuffered `-u`.
- [ ] Mengimplementasikan agregasi metrik, indexing string, dan filtering structured data berbasis associative arrays di GAWK dengan alokasi memori yang stabil.