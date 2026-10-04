# BAB 03: Quiz, Challenge, & Knowledge Check
**Variabel, Parameter Expansion, & Struktur Data**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Semantik Word Splitting dan Ekspansi Parameter:**
   Jelaskan secara presisi perbedaan mekanisme ekspansi antara `$*`, `$@`, `"$*"`, dan `"$@"` ketika shell beroperasi dalam konteks tokenisasi argumen. Mengapa penggunaan `"$@"` mutlak diwajibkan dalam *defensive programming* saat membangun wrapper scripts di lingkungan enterprise?

2. **Diferensiasi Manipulasi String Murni (Pure Bash):**
   Uraikan cara kerja internal dari parameter expansion prefix/suffix stripping: `${var#pattern}`, `${var##pattern}`, `${var%pattern}`, dan `${var%%pattern}`. Kapan Anda harus memprioritaskan ekspansi bawaan ini dibandingkan memanggil eksternal utility seperti `sed`, `awk`, atau `cut` ditinjau dari metrik *fork-exec overhead*?

3. **Perilaku State Variabel (Unset vs Null):**
   Bandingkan evaluasi kondisi pada operator parameter expansion berikut terhadap variabel yang berada dalam status *unset* versus *null (empty string)*:
   * `${var:-default}` vs `${var-default}`
   * `${var:=default}` vs `${var=default}`
   * `${var:?error}` vs `${var?error}`
   Sajikan matriks atau analisis komparatif mengenai implikasi modifikasi state variabel global/lokal dari operator-operator tersebut.

4. **Karakteristik Alokasi Memori Struktur Data Bash:**
   Bagaimana Bash mengelola alokasi memori untuk *Indexed Arrays* (`declare -a`) dibandingkan dengan *Associative Arrays* (`declare -A`)? Mengapa array asosiatif mewajibkan deklarasi eksplisit sebelum inisialisasi, sedangkan indexed array dapat dialokasikan secara implisit?

5. **Scoping, Environment Inheritance, dan Boundary Ekspor:**
   Jelaskan hierarki *scoping* antara variabel skalar standar, variabel berkonteks `local` di dalam fungsi, dan variabel yang diekspor melalui `export`. Mengapa struktur data array Bash (baik indexed maupun associative) secara arsitektural tidak dapat diwariskan ke proses *child* non-Bash melalui standar IEEE Std 1003.1 (POSIX) environment table?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Arsitektur Nameref dan Mitigasi Circular Reference:**
   Fitur *Nameref* (`declare -n ref=target`) diperkenalkan pada Bash 4.3 untuk menangani *call-by-reference*. Jelaskan bahaya *circular reference* yang dapat terjadi ketika nama variabel nameref identik dengan nama target dalam *call stack* lokal fungsi. Bagaimana Bash mendeteksi kondisi ini, dan apa pola arsitektur terbaik untuk menghindarinya?

2. **Perilaku Sparse Array dan Metrik Kapasitas:**
   Di Bash, indexed array bersifat *sparse* (indeks tidak harus berurutan). Jika Anda mengeksekusi operasi berikut:
   ```bash
   arr[0]="node-01"
   arr[1000000]="node-02"
   ```
   Bagaimana representasi data internal Bash menangani alokasi indeks tersebut? Bandingkan output serta kompleksitas komputasi antara `${#arr[@]}` (panjang elemen) dan `${!arr[@]}` (daftar indeks) pada *sparse array* berukuran besar.

3. **Interaksi Antara IFS, Unquoted Expansion, dan Pathname Expansion (Globbing):**
   Diberikan sebuah skenario di mana konfigurasi sistem dibaca dari variabel:
   ```bash
   input="conf*:/etc/conf.d:backup *"
   IFS=":"
   for item in $input; do
       echo "Processing: $item"
   done
   ```
   Bedah secara kronologis bagaimana parser Bash mengeksekusi siklus hidup ekspansi: *Parameter Expansion* $\rightarrow$ *Word Splitting* $\rightarrow$ *Pathname Expansion (Globbing)*. Tunjukkan bug destruktif yang berpotensi terjadi dan bagaimana memperbaikinya tanpa mengubah nilai `input`.

4. **Manipulasi Atribut Variabel dan Immutabilitas:**
   Analisis perbedaan mekanisme antara `readonly var=value` dengan `declare -r var=value`. Apa yang terjadi secara internal di tabel simbol Bash saat perintah `unset -v var` dieksekusi terhadap variabel *read-only*? Jelaskan risiko arsitektur dari variabel *read-only* dalam konteks pengujian *unit testing* menggunakan framework Bash (misalnya BATS) yang mengeksekusi tes dalam proses shell yang sama.

5. **Advanced String Transformation via Case & Substring Mechanics:**
   Diberikan variabel string terstruktur (misal: log ISO timestamp terkompresi). Tunjukkan bagaimana mengekstraksi substring dan memanipulasi kapitalisasi menggunakan *Parameter Expansion* lanjutan (`${var^}`, `${var^^}`, `${var,}`, `${var,,}`) dan *Offset/Length Expansion* (`${var:offset:length}`). Jelaskan apa yang terjadi jika parameter `offset` bernilai negatif dan mengapa spasi pemisah wajib diberikan sebelum operator negatif (misal: `${var: -5}`).

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden OOM dan CPU Spiking pada Log Aggregator Engine
Sebuah skrip Bash berjalan sebagai daemon untuk melakukan agregasi metrik *real-time* dari access log sebuah web server berskala 50.000 requests/detik. Skrip tersebut menggunakan *Associative Array* untuk menghitung frekuensi kemunculan IP address:
```bash
declare -A ip_counter
while read -r ip _; do
    ((ip_counter["$ip"]++))
done < <(tail -n 1000000 /var/log/nginx/access.log)
```
**Dampak:** Setelah memproses sekitar 300.000 baris unik, performa skrip terdegradasi secara eksponensial (CPU pinning 100% pada satu core), konsumsi memori melambung melampaui 1.5 GB, dan sistem Linux memicu *OOM (Out-of-Memory) Killer*.
* **Pertanyaan Diagnostik:**
  1. Analisis mengapa implementasi hash table internal Bash pada associative array sangat tidak efisien untuk dataset skala ratusan ribu *keys*.
  2. Identifikasi penyebab degradasi CPU eksponensial selama operasi penulisan/pencarian (*lookup/write*) berlangsung di Bash associative array berukuran masif.
  3. Desain ulang arsitektur pemrosesan tersebut menggunakan pendekatan Bash murni yang membatasi retensi struktur data di memori, atau kombinasikan secara tepat dengan stream processing POSIX.

---

### Skenario B: Subshell Scoping Trap pada Provisioning Pipeline Multi-Server
Seorang DevOps Engineer membuat skrip otomatisasi deployment infrastruktur. Skrip ini membaca file inventory server dan harus menyimpan server yang gagal di-deploy ke dalam indexed array untuk diteruskan ke sistem notifikasi alert:
```bash
#!/usr/bin/env bash
set -euo pipefail

declare -a failed_nodes=()

cat inventory.txt | while read -r node; do
    if ! ping -c 1 -W 1 "$node" >/dev/null 2>&1; then
        echo "Node unreachable: $node"
        failed_nodes+=("$node")
    fi
done

echo "Total nodes failed: ${#failed_nodes[@]}"
if [[ ${#failed_nodes[@]} -gt 0 ]]; then
    send_alert_notification "${failed_nodes[@]}"
fi
```
**Dampak:** Meskipun terminal mencetak pesan "Node unreachable" untuk 5 server, output baris terakhir selalu `Total nodes failed: 0`, dan fungsi notifikasi tidak pernah terpicu.
* **Pertanyaan Diagnostik:**
  1. Bedah mekanisme *Process Execution Environment* dan POSIX subshell creation yang menyebabkan state array `failed_nodes` hilang setelah loop selesai.
  2. Jelaskan mengapa pengaturan `set -e` dan `set -o pipefail` gagal mendeteksi atau memitigasi kegagalan logis ini.
  3. Berikan dua solusi arsitektur Bash yang idiomatis untuk memperbaiki *variable scoping loss* tersebut: satu menggunakan *Process Substitution* dan satu menggunakan *Shell Execution Option* (`lastpipe`).

---

### Skenario C: Data Injection & Privilege Escalation via Indirect Expansion
Dalam pipeline CI/CD dinamis, sebuah skrip memuat variabel konfigurasi lingkungan kerja berdasarkan input branch pengguna:
```bash
# Target: memuat variabel TARGET_ENV_$BRANCH_TYPE
# Input branch dikontrol oleh developer external: "STAGING; rm -rf /" atau "PROD"
branch_type="$1"
config_var="CONFIG_${branch_type}"

# Implementasi Tim Dev:
eval "current_config=\$$config_var"
```
Untuk menghindari kritik security terkait `eval`, tim lain mengusulkan penggantian menjadi:
```bash
branch_type="$1"
config_var="CONFIG_${branch_type}"
current_config="${!config_var}"
```
* **Pertanyaan Diagnostik:**
  1. Apakah penggantian `eval` menggunakan *Indirect Parameter Expansion* (`${!var}`) sepenuhnya menutup celah eksploitasi jika variabel `$branch_type` dimanipulasi dengan karakter berbahaya (misalnya karakter array subscript atau ekspresi aritmatika: `STAGING[$(malicious_command)]`)? Jelaskan mekanisme internalnya!
  2. Bagaimana *Nameref* (`declare -n`) merespons vektor serangan input yang sama?
  3. Rancang sebuah fungsi validasi dan parsing variabel dinamis yang aman secara enterprise (*bulletproof*) menggunakan whitelist sanitization dan type-safe attributes.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Pure-Bash Configuration & State Serialization Engine

#### Problem:
Sebuah *micro-agent* monitoring pada server edge memiliki resource sangat terbatas (tidak memiliki runtime python, jq, perl, sed, ataupun awk). Anda diwajibkan menulis fungsi Bash library bernama `parse_and_transform_config` yang mem-parsing file konfigurasi hibrida (berisi environment variables, key-value berulang, dan nested data sederhana) menjadi struktur data native Bash, melakukan validasi integritas tipe data, dan mengekspor hasilnya ke format flat-key state table tanpa menghasilkan *child process/fork* satupun.

#### Requirements:
1. **Zero-Fork Execution:**
   Dilarang keras menggunakan command eksternal maupun subshell. Tidak boleh ada pemanggilan binary POSIX (`cat`, `sed`, `awk`, `grep`, `cut`, `tr`, `head`, `tail`) maupun operator subshell `$(...)` atau `(...)`. Gunakan hanya built-in Bash (`read`, parameter expansion, regex matching `[[ =~ ]]`, indexed array, associative array, looping murni).
2. **Parser Specification:**
   Fungsi harus menerima string *raw config* dan mem-parsingnya ke dalam associative array dengan aturan:
   * Mengabaikan baris kosong dan komentar (diawali karakter `#`).
   * Memotong spasi di awal dan akhir string (*leading/trailing whitespace trimming*) secara murni melalui parameter expansion.
   * Mendukung format key-value: `KEY="VALUE"` atau `KEY=VALUE`.
   * Mendukung validasi tipe data:
     * Jika value bertipe Integer: assign atribut integer (`declare -i`).
     * Jika value diawali `arr:` (misal `arr:a,b,c`), parse menjadi indexed array.
   * Mendukung nesting via delimiter dot (`service.database.host=localhost`), disimpan ke associative array dengan *composite key*.
3. **Reference Mapping via Nameref:**
   Fungsi parsing harus menerima referensi target associative array via *Nameref* argumen pertama, sehingga tidak menggunakan global variable polution:
   `parse_and_transform_config target_map <<< "$raw_data"` atau parsing baris per baris.
4. **Resilience & Strict Mode:**
   Kode harus lulus dieksekusi di bawah mode `set -euo pipefail` tanpa menimbulkan false positive crash saat mencari *key* yang opsional.

#### Constraints:
* Kompatibel penuh dengan Bash 4.4+ dan Bash 5.x.
* Penggunaan memori O(N) linier terhadap ukuran file konfigurasi.
* Eksekusi parsing 1.000 baris file konfigurasi harus selesai dalam waktu < 200 ms.

#### Expected Output:
Skrip demonstrasi harus mampu memproses teks konfigurasi berikut:
```text
# Server Configuration
app.name = "Payment Gateway"
app.port = 8080
app.workers = 4
app.hosts = arr:192.168.1.1,192.168.1.2,192.168.1.3
# Edge Settings
app.debug = false
```
Dan mengekstraksi nilai secara programatis melalui array asosiatif target:
```bash
echo "${target_map["app.name"]}"    # Output: Payment Gateway
echo "${target_map["app.port"]}"    # Output: 8080
echo "${target_map["app.workers"]}" # Output: 4 (Tervalidasi integer)
# host list diekstrak sebagai elemen array
```

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Siklus hidup tokenisasi Bash: urutan eksekusi Parameter Expansion, Word Splitting, dan Pathname Expansion.
- [ ] Perbedaan semantik mendasar dan penggunaan yang aman antara `"$@"`, `"$*"`, `$@`, dan `$*`.
- [ ] Mekanisme stripping prefix/suffix (`#`, `##`, `%`, `%%`) dan pattern replacement (`/`, `//`) berbasis Glob, bukan Regex.
- [ ] Perbedaan perilaku operator default expansion antara parameter berstatus *Unset* dan bernilai *Null* (tanda titik dua `:` vs non-titik dua).
- [ ] Keterbatasan arsitektur Bash Associative Array (overhead memori internal bucket hash table) dibanding indexed array.
- [ ] Mekanisme subshell isolation saat berinteraksi dengan pipeline (`|`) dan teknik mitigasinya (`lastpipe`, process substitution `<()`).
- [ ] Risiko keamanan injeksi kode pada `eval`, indirect expansion (`${!var}`), dan nameref (`declare -n`).
- [ ] Skup variabel (`local`, `declare`, `export`) dan batasan ekspor struktur data kompleks ke child process.

### Saya tidak perlu menghafal:
- [ ] Seluruh tabel kode karakter ASCII heksadesimal untuk konversi karakter string.
- [ ] Pola *Extended Globbing* (`extglob`) ekstrem yang jarang digunakan; dokumentasi manual Bash dapat dijadikan referensi rujukan cepat sintaksis regex.
- [ ] Implementasi algoritma hashing internal C yang digunakan source code Bash (GNU `variables.c`).

### Saya harus bisa melakukan:
- [ ] Melakukan manipulasi string kompleks (trimming, slicing, replacement, case shifting) secara murni via Parameter Expansion tanpa invoking subprocess.
- [ ] Menulis skrip wrapper CLI defensif yang mem-forward seluruh positional arguments secara presisi tanpa merusak spasi atau karakter whitespace lainnya.
- [ ] Mengimplementasikan struktur data Indexed Array dan Associative Array untuk menyelesaikan problem agregasi data transaksional.
- [ ] Menggunakan *Process Substitution* untuk menghindari subshell data-loss trap dalam loop pengolahan data tabular.
- [ ] Menggunakan *Nameref* secara aman untuk menciptakan fungsi modular yang mengembalikan atau memutasi struktur data kompleks dari caller.
- [ ] Mengisolasi dan mendeteksi variabel *unbound* (`set -u`) dengan menerapkan default value fallback patterns yang aman.