# BAB 04: Quiz, Challenge, & Knowledge Check
**Logika Kontrol, Arithmetic, & Evaluasi Kondisi**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Anatomi Mekanisme Evaluasi Kondisi: `[` vs `[[`
Jelaskan perbedaan arsitektural dan mekanisme eksekusi antara utility `[` (alias `test`) dengan compound command `[[ ... ]]` pada Bash. Mengapa ekspresi `[ $foo = "bar" ]` berisiko menimbulkan *syntax error* saat `$foo` bernilai kosong atau mengandung spasi, sedangkan `[[ $foo == "bar" ]]` dijamin aman dievaluasi tanpa deklarasi kutip (*quoting*) eksplisit?

### Soal 1.2: Semantik Boolean dan Exit Status
Bash tidak memiliki tipe data primitif `boolean` (`true` atau `false`). Jelaskan bagaimana Bash memperlakukan *exit status code* ($?) dari suatu perintah untuk menentukan alur eksekusi pada *control structures* (`if`, `while`, `until`). Mengapa nilai numerik `0` merepresentasikan keberhasilan/kebenaran (*truthiness*), sementara dalam konteks arithmetic evaluation `$(( ... ))`, nilai `0` justru dievaluasi sebagai false?

### Soal 1.3: Limitasi dan Karakteristik Native Arithmetic Bash
Jelaskan karakteristik *integer arithmetic engine* internal Bash yang diakses melalui sintaks `$(( ... ))` atau `let`. Mengapa Bash tidak mendukung *floating-point arithmetic* secara *native*, berapa batas kapasitas representasi integer bertanda (*signed integer width*) yang didukung, dan apa implikasi keamanan/stabilitas saat memproses angka dengan *leading zero* (misal: `08` atau `09`) di dalam ekspresi aritmatika?

### Soal 1.4: Precedence dan Fallacy pada Short-Circuit Evaluation
Pola idiomatis `command1 && command2 || command3` sering disalahartikan sebagai ekuivalen penuh dari blok kondisional `if command1; then command2; else command3; fi`. Analisis kesalahan asumsi ini berdasarkan *operator precedence* dan evaluasi *exit status*. Berikan skenario konkret di mana pola short-circuit tersebut memicu eksekusi *fallback* yang tidak diinginkan (*unintended execution branch*).

### Soal 1.5: Mekanisme Branching Pattern Matching: `case` Statements
Jelaskan keunggulan komputasional dan keterbacaan instruksi `case ... esac` dibandingkan rantai `if-elif-else` yang panjang ketika mengevaluasi kecocokan string berbasis pola (*globbing*). Terangkan pula perbedaan fungsi terminator klausa: double semicolon (`;;`), ampersand semicolon (`;&`), dan double semicolon ampersand (`;;&`).

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Quoting Trap pada Regex Operator `[[ $var =~ $pattern ]]`
Perhatikan dua potongan kode evaluasi regular expression berikut:

```bash
# Versi A
pattern="^[0-9]+$"
if [[ $input =~ $pattern ]]; then ... fi

# Versi B
if [[ $input =~ "^[0-9]+$" ]]; then ... fi
```

Jelaskan mengapa Versi B gagal mencocokkan input angka pada Bash versi 3.2 ke atas. Bagaimana Bash parser membedakan *quoted string literal* dan *regex pattern* di sisi kanan operator `=~`, dan bagaimana Anda mengakses sub-pola hasil *regex capture group* secara aman tanpa mengeksekusi *external process* seperti `sed` atau `awk`?

### Soal 2.2: Subshell Variable Loss pada Pipeline Loop
Seorang engineer menulis skrip auditing kapasitas disk berikut:

```bash
total_bytes=0
df -k | tail -n +2 | while read -r fs size used avail pct mnt; do
    total_bytes=$(( total_bytes + used ))
done
echo "Total Used: $total_bytes"
```

Ketika dijalankan, output `$total_bytes` selalu bernilai `0`. Bedah mekanisme internal proses eksekusi pipeline Bash yang menyebabkan nilai `$total_bytes` hilang saat loop selesai. Berikan dua solusi perbaikan: satu menggunakan *Process Substitution* dan satu menggunakan Bash *built-in option* (`lastpipe`).

### Soal 2.3: Safe Arithmetic Expansion dan Code Injection Vulnerability
Ekspresi aritmatika Bash `$(( ... ))` melakukan dereferensi variabel secara rekursif. Analisis kerentanan keamanan (*arbitrary code execution*) dari kode berikut jika variabel `user_input` berasal dari payload HTTP eksternal yang tidak disanitasi:

```bash
read -r user_input
result=$(( user_input + 10 ))
```

Bagaimana penyerang dapat mengeksploitasi baris tersebut untuk menghapus file atau membuka *reverse shell*? Bagaimana cara memvalidasi dan memitigasi risiko ini tanpa dependensi tools pihak ketiga?

### Soal 2.4: Integer Overflow dan Wraparound Behavior
Jelaskan fenomena yang terjadi pada level C runtime/CPU register ketika operasi Bash arithmetic melampaui batas maksimum integer 64-bit (`$(( 2**63 - 1 ))`). Apa output dari evaluasi `$(( 9223372036854775807 + 1 ))`? Jelaskan bagaimana seorang engineer harus mengimplementasikan proteksi *boundary check* sebelum eksekusi aritmatika dilakukan guna mencegah *silent wraparound bug* pada sistem billing/quota.

### Soal 2.5: Idiom Nested Ternary Operator pada Variable Assignment
Dalam parameter ekspansi atau evaluasi aritmatika, Bash mengizinkan operator ternary `(( cond ? expr1 : expr2 ))`. Analisis snippet berikut:

```bash
(( status = (retry_count > max_retries) ? 1 : (is_degraded ? 2 : 0) ))
```

Apakah evaluasi kedua ekspresi pada rantai ternary dilakukan secara *eager* atau *lazy* (*short-circuited*)? Apa konsekuensinya terhadap modifikasi variabel jika ekspresi ternary kedua mengandung *side-effect assignment* seperti `var++`?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Performance Degradation pada Skrip Parser Log Skala Besar
Sebuah skrip parser monitoring berjalan setiap 5 menit di lingkungan produksi Kubernetes untuk memvalidasi jutaan baris log metrik jaringan. Skrip tersebut mengalami *timeout* dan memicu *CPU throttling*. Setelah ditelusuri, kode loop pemrosesan data terlihat seperti ini:

```bash
sum=0
while IFS=',' read -r timestamp metric_id latency; do
    # Validasi angka
    if [ $(echo "$latency > 100.0" | bc) -eq 1 ]; then
        alert_count=$(expr $alert_count + 1)
    fi
    sum=$(echo "$sum + $latency" | bc)
done < "/var/log/traffic_large.csv"
```

* **Pertanyaan Diagnostik & Solusi:**
  1. Identifikasi *system call overhead* dan *process lifecycle bottleneck* utama pada blok kode di atas.
  2. Rancang ulang algoritma parsing tersebut secara menyeluruh menggunakan pure Bash control structures dan native evaluation (konversi desimal ke representasi integer/fixed-point milli-units untuk meniadakan ketergantungan pada binary eksternal `bc` dan `expr`).
  3. Jelaskan estimasi perbandingan *time complexity* dan reduksi utilisasi CPU *context switching* pasca optimasi.

---

### Skenario B: Race Condition dan State Flapping pada Lock Check Automation
Sebuah cron job otomatisasi backup mengeksekusi fungsi pengecekan file lock untuk memastikan konkurensi tunggal:

```bash
LOCK_FILE="/var/run/backup.lock"

if [ ! -f "$LOCK_FILE" ]; then
    sleep 1 # Simulasi latensi evaluasi disk mount
    echo "$$" > "$LOCK_FILE"
    execute_critical_backup
    rm -f "$LOCK_FILE"
else
    echo "Process currently running. Aborting."
    exit 1
fi
```

Pada periode tertentu, backup mengalami korupsi data akibat dua proses worker berjalan secara simultan (*overlapping execution*).

* **Pertanyaan Diagnostik & Solusi:**
  1. Bedah *Time-of-Check to Time-of-Use* (TOCTOU) vulnerability pada blok kondisional `if [ ! -f ... ]`. Mengapa pemeriksaan keberadaan file bukan merupakan operasi *atomic*?
  2. Rekonstruksi mekanisme kontrol di atas menggunakan Bash idioms native atau tool standar Linux (`set -C` / `noclobber` atau `flock`) sehingga evaluasi kondisi keberadaan lock dan penguncian dieksekusi secara *atomic level kernel*.
  3. Tuliskan implementasi penanganan sinyal terminasi (`trap`) untuk membersihkan lock secara deterministik apabila script menerima sinyal `SIGINT`, `SIGTERM`, atau mengalami error fatal (`set -e`).

---

### Skenario C: Dynamic State Machine Engine untuk Deployment Canary
Anda diminta merancang subsistem Bash yang bertindak sebagai *Finite State Machine* (FSM) untuk orkestrasi *zero-downtime deployment* dengan fase state: `INIT` -> `HEALTHCHECK` -> `CANARY_10%` -> `CANARY_50%` -> `FULL_PROD` -> `FINALIZED`. Jika healthcheck gagal di fase manapun, sistem harus transisi ke state `ROLLBACK`. 

Sistem tidak boleh menggunakan rantai bertingkat `if-elif-else` yang rawan human error dan sulit diekstensi.

* **Pertanyaan Diagnostik & Solusi:**
  1. Susun arsitektur loop kontrol FSM memanfaatkan `case` statements dengan fallthrough control (`;;`, `;&`, `;;&`) atau pattern matching dynamic dispatch.
  2. Implementasikan mekanisme evaluasi kondisi metrik (misal: HTTP status check dan memory consumption threshold) yang mengontrol transisi state secara deterministik.
  3. Bagaimana Anda mengisolasi eksekusi state menggunakan *defensive control* agar error tak terduga pada salah satu state tidak menghentikan eksekusi logic rollback secara prematur?

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Resilient Network Watchdog & Auto-Remediator

#### Problem Statement
Infrastruktur backend edge-node sering mengalami degradasi konektivitas parsial (*packet drop*, *DNS lookup failure*, atau *unhealthy upstream gateway*). Anda ditugaskan membangun skrip *standalone daemon* `net-watchdog.sh` dengan ketahanan level enterprise. Skrip harus berjalan terus-menerus (*daemonized loop*), melakukan healthcheck berlapis, dan mengambil keputusan mitigasi secara deterministik tanpa bergantung pada tool berat seperti Python atau Node.js.

#### Requirements
1. **Zero External Forking Logic:** Dilarang menggunakan utilitas luar seperti `bc`, `awk`, atau `sed` untuk evaluasi kondisi string, parsing status, dan kalkulasi interval. Semua evaluasi status dan arithmetic wajib diselesaikan via Bash built-ins.
2. **Fixed-Point Arithmetic:** Evaluasi ambang batas latency (contoh: warning threshold `45.50 ms`). Karena Bash native integer arithmetic tidak mendukung desimal, normalisasikan parsing string latensi ke integer berskala mikro/mili-detik (`45500 us`) untuk komparasi numerik murni.
3. **Structured Control Flow:**
   * Gunakan `[[ ... ]]` compound command untuk semua evaluasi boolean dan regex parsing validasi format IP target (`IPv4` validator regex wajib murni Bash `=~`).
   * Implementasikan finite logic menggunakan `case` untuk memproses klasifikasi respon jaringan: `HEALTHY`, `LATENCY_WARNING`, `PACKET_LOSS_CRITICAL`, dan `LINK_DOWN`.
4. **Resilient Loop & Signal Handling:**
   * Terapkan loop non-blocking dengan interval adaptif (backoff logic: jika kondisi degradasi berulang, interval diperpanjang secara eksponensial menggunakan operator bitwise atau arithmetic: `interval = base * 2^retries`).
   * Wajib menangani sinyal sistem (`SIGTERM`, `SIGINT`) untuk *graceful cleanup* dan pelaporan audit status terakhir.
5. **Circuit Breaker State Machine:**
   * Jika error terjadi berturut-turut sebanyak 3 kali (`failures >= 3`), transisikan sirkuit ke `OPEN` state dan picu script remediator mock (`remediate_gateway`).

#### Constraints
* Engine: Bash versi 4.4+.
* Shell options: Wajib menyertakan `set -u` (fail on unbound variables) dan `set -o pipefail`.
* Strict Quoting: Kebijakan kuotasi ketat pada ekspresi variabel non-arithmetic.

#### Expected Output
Skrip mencetak formatted JSON payload ke standard output setiap iterasi tanpa dependensi binary `jq`:

```json
{"timestamp": 1718000000, "state": "HEALTHY", "latency_ms": "12.45", "consecutive_failures": 0, "next_poll_sec": 5}
{"timestamp": 1718000005, "state": "LATENCY_WARNING", "latency_ms": "68.20", "consecutive_failures": 1, "next_poll_sec": 10}
{"timestamp": 1718000015, "state": "CIRCUIT_OPEN", "action": "REMEDIATION_TRIGGERED", "consecutive_failures": 3, "next_poll_sec": 40}
```

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan fundamental parser antara operator kondisional `[` (POSIX test) dan `[[` (Bash compound command), termasuk dampaknya terhadap word splitting, globbing, dan penanganan null variables.
- [ ] Cara kerja exit status ($?) dalam evaluasi logika Bash (konvensi `0` sebagai success/truthy dan non-zero `1-255` sebagai error/falsy).
- [ ] Aturan semantic dan batas limitasi Bash integer arithmetic: 64-bit signed bounds, ketiadaan floating-point natif, evaluasi rekursif, dan bahaya oktal literal (`08`, `09`).
- [ ] Mengapa pola `cmd1 && cmd2 || cmd3` bukanlah representasi aman dari konstruksi `if-then-else` (analisis short-circuit evaluation precedence).
- [ ] Perbedaan fungsionalitas terminator branch pada `case` statements: `;;` (break), `;&` (fallthrough mutlak), dan `;;&` (evaluasi pola berikutnya).
- [ ] Dampak pipeline subshell (`cmd | while read ...`) terhadap persistensi *variable state* dan cara mitigasinya via *Process Substitution* atau `shopt -s lastpipe`.
- [ ] Risiko keamanan *code execution* yang melekat pada ekspresi aritmatika Bash `$(( ... ))` akibat resolusi variabel rekursif tak terkontrol.

### Saya tidak perlu menghafal:
- [ ] Tabel kode ASCII karakter desimal lengkap untuk operasi aritmatika karakter (gunakan utilitas `printf '%d' "'A"` saat dibutuhkan).
- [ ] Seluruh sintaks ekspresi reguler standar POSIX vs PCRE; cukup pahami cara Bash menangani operator match `=~` dan array internal `BASH_REMATCH`.
- [ ] Implementasi manual algoritma matematika kompleks (akar kuadrat, trigonometri) di dalam Bash; serahkan ke utility eksternal berkecepatan tinggi seperti `bc` atau tool runtime sistem jika presisi non-integer mutlak diperlukan.

### Saya harus bisa melakukan:
- [ ] Menulis ekspresi conditional logic yang tahan banting (*defensive programming*) tanpa memicu error parsing meski variabel bernilai kosong, mengandung karakter *whitespace*, atau *glob characters* (`*`, `?`).
- [ ] Melakukan komparasi bilangan desimal di Bash murni dengan teknik translasi *fixed-point integer arithmetic* (skala perkalian $10^N$).
- [ ] Menggunakan operator regex `=~` secara benar di dalam `[[ ... ]]` dengan penanganan quoting yang tepat guna mengekstrak token data via `BASH_REMATCH`.
- [ ] Mengonversi struktur *conditional chaining* yang panjang dan lambat menjadi *lookup table* efisien atau state machine terstruktur menggunakan `case`.
- [ ] Membangun mekanisme mutual exclusion file locking yang benar dan bebas dari race condition TOCTOU menggunakan Bash native descriptor redirection atau Linux kernel locks.