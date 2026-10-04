# BAB 05: Quiz, Challenge, & Knowledge Check
**Modularitas Fungsi, Subshell, & Environment Management**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Mekanisme Dynamic Scoping vs Lexical Scoping:**  
   Bash menerapkan *dynamic scoping* untuk variabel, bukan *lexical scoping*. Jelaskan secara mendalam bagaimana resolusi variabel terjadi saat fungsi `FuncA` mendeklarasikan variabel `local x=10` kemudian memanggil fungsi `FuncB` yang juga membaca nilai `x` tanpa mendeklarasikannya secara lokal. Apa risiko arsitektural dari perilaku ini dalam basis kode skala besar?

2. **Divergensi Kontrak: Return Value vs Standard Output:**  
   Banyak pengembang pemula menyamakan instruksi `return` pada fungsi Bash dengan `return` pada bahasa seperti C atau Python. Jelaskan perbedaan fundamental antara batasan nilai pengembalian integer (8-bit unsigned integer, range 0–255) via `return` dan transfer data arbitrer melalui standard output stream (`stdout`). Bagaimana cara mendesain fungsi modular yang harus mengembalikan payload data kompleks sekaligus status eksekusi secara idiomatis?

3. **Subshell Execution Context vs Command Grouping:**  
   Bandingkan eksekusi subshell via sintaks `( ... )` dengan *command grouping* di thread/proses yang sama via `{ ...; }`. Tinjau dari perspektif *kernel process creation* (`fork()`), alokasi memori, duplikasi *file descriptor table*, dan dampaknya terhadap mutasi variabel environment pada proses induk (*parent shell*).

4. **Siklus Hidup Variabel Environment & Direktif `export`:**  
   Jelaskan representasi internal dari environment variable dalam proses Linux dan bagaimana direktif `export` pada Bash berinteraksi dengan array `char **environ`. Mengapa proses anak (*child process*) secara arsitektural mustahil memutasi environment variable milik *parent process* secara langsung tanpa bantuan IPC (*Inter-Process Communication*)?

5. **Eksekusi Script vs Dot-Sourcing:**  
   Analisis perbedaan teknis mendalam antara mengeksekusi pustaka fungsi via `./lib_network.sh` (atau `bash lib_network.sh`) dibandingkan dengan *dot-sourcing* (`. ./lib_network.sh` atau `source ./lib_network.sh`). Jelaskan dampaknya terhadap isolasi scope, penanganan signal trap, alokasi PID, serta potensi polusi *global state*.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Anomali `$BASHPID` vs `$$` dalam Subshell Asinkron:**  
   Jelaskan mengapa dalam subshell berulang atau pipeline yang dieksekusi secara asinkron (`( ... ) &`), variabel `$$` tetap mengembalikan PID dari *main shell process*, sedangkan `$BASHPID` mengembalikan PID riil dari proses subshell yang sedang berjalan. Apa implikasi kritis dari perbedaan ini saat mendesain mekanisme *distributed file locking* berbasis PID (`/var/run/*.pid`)?

2. **The "Pipeline Subshell Trap" dan Evaluasi `lastpipe`:**  
   Diberikan potongan kode bermasalah berikut:
   ```bash
   processed_count=0
   generate_metrics | while read -r line; do
       ((processed_count++))
   done
   echo "Total: $processed_count" # Selalu menghasilkan "Total: 0"
   ```
   Bedah arsitektur pemanggilan pipeline pada Bash yang menyebabkan variabel `processed_count` tidak termutasi pada parent shell. Jelaskan dua strategi mitigasi produksi: pertama menggunakan *Process Substitution* (`< <(...)`), dan kedua menggunakan opsi internal shell `shopt -s lastpipe` (sertakan prasyarat penonaktifan *job control* agar `lastpipe` berfungsi pada skrip non-interaktif).

3. **Injeksi Lingkungan dan Mitigasi Function Exporting (`export -f`):**  
   Bagaimana mekanisme `export -f` merepresentasikan fungsi ke dalam environment variable tabel kernel (misalnya format prefix `BASH_FUNC_func_name%%`)? Kaitkan arsitektur ini dengan kerentanan historis *Shellshock* (CVE-2014-6271), dan jelaskan postur keamanan modern ketika mengekspor fungsi melewati *execution boundary* (seperti `sudo`, SSH restricted shells, atau container runtimes).

4. **Ketiadaan Tail Call Optimization (TCO) dan Kontrol `FUNCNEST`:**  
   Bash tidak memiliki mekanisme *Tail Call Optimization* (TCO). Jelaskan apa yang terjadi pada *call stack frame* di memori Bash ketika sebuah fungsi rekursif dieksekusi tanpa terminasi yang tepat. Bagaimana variabel internal `FUNCNEST` digunakan untuk mencegah kondisi *segmentation fault* akibat eksploitasi rekursi tak terbatas (*stack overflow*)?

5. **Manipulasi File Descriptor dalam Scope Fungsi & Restorasi Otomatis:**  
   Tinjau potongan kode berikut:
   ```bash
   redirect_audit() {
       exec 3>&1
       exec 1>>/var/log/audit.log
   }
   ```
   Jelaskan mengapa manipulasi *file descriptor* di atas bersifat persisten dan menembus batas akhir fungsi (*leaking to caller*). Bagaimana cara mendesain abstraksi fungsi yang aman untuk meredireksi I/O lokal tanpa mengubah status file descriptor pemanggilnya saat fungsi mengembalikan kontrol?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: PID Exhaustion & CPU Throttling pada High-Throughput Orchestration
Sebuah skrip deployment microservice mengeksekusi iterasi pengecekan status 200 kontainer secara paralel. Pengembang menggunakan struktur:
```bash
for container in "${containers[@]}"; do
    status=$(get_container_health "$container") # get_container_health memanggil curl via subshell berkali-kali
    record_status "$container" "$status" &
done
wait
```
Setelah berjalan di server target berkapasitas 64-core, sistem mengalami *kernel process table saturation* (PID exhaustion: `fork: retry: Resource temporarily unavailable`) dan CPU context switching meroket ke jutaan switch/detik, menyebabkan node Kubernetes mengalami *NodeNotReady*.

* **Pertanyaan Diagnostik:**
  1. Identifikasi akumulasi subshell implisit yang terjadi pada loop di atas. Hitung estimasi proses yang tercipta per iterasi.
  2. Rancang ulang arsitektur fungsi dan eksekusi tersebut menggunakan pooling worker berkonsep antrean FIFO (*named pipe*) atau `xargs -P` / GNU `parallel` idiomatis Bash, tanpa melakukan *forking* liar.
  3. Bagaimana Anda mengeliminasi subshell `status=$(...)` dengan memanfaatkan *dynamic variable reference* (`declare -n`) atau *pass-by-reference* untuk mengembalikan string health status secara langsung di *in-memory process*?

### Skenario B: Race Condition dan State Corruption pada Telemetri Asinkron
Sebuah agent telemetri berbasis Bash dijalankan sebagai daemon. Agent ini membaca sensor metrik CPU dan memori di latar belakang menggunakan subshell paralel:
```bash
declare -A NODE_METRICS
collect_cpu() {
    NODE_METRICS["cpu"]=$(cat /proc/loadavg | awk '{print $1}')
}
collect_mem() {
    NODE_METRICS["mem"]=$(free -m | awk '/Mem:/ {print $3}')
}
collect_cpu &
collect_mem &
wait
echo "Metrics: CPU=${NODE_METRICS["cpu"]} MEM=${NODE_METRICS["mem"]}"
```
Hasil output selalu menampilkan nilai kosong: `Metrics: CPU= MEM=`. Pengembang senior menduga adanya *memory separation* dan mengusulkan penggunaan *shared state file* di `/dev/shm`, namun muncul kondisi *race condition* baru saat file tersebut ditulis secara bersamaan.

* **Pertanyaan Diagnostik:**
  1. Jelaskan secara mendalam mengapa modifikasi elemen array asosiatif `NODE_METRICS` di dalam subshell latar belakang (`&`) tidak pernah terefleksi ke *parent process*.
  2. Rancang arsitektur IPC aman berbasis *Anonymous Pipe* (via `coproc` atau *dedicated file descriptors*) yang memungkinkan fungsi-fungsi pengumpul metrik streaming data kembali ke parent shell secara deterministik dan non-blocking tanpa membuat file sementara di disk.

### Skenario C: Dynamic Module Sourcing & Crash Isolation pada Enterprise CLI Framework
Anda sedang mendesain enterprise CLI framework modular (mirip arsitektur `aws-cli` atau `kubectl`) berbasis Bash. Framework ini memiliki direktori `plugins/` yang memuat file `.sh` eksternal yang ditulis oleh berbagai tim pengembang. Persyaratan kritis:
- Framework memuat plugin secara dinamis saat *runtime* berbasis perintah user (misal: `mycli network deploy`).
- Plugin pihak ketiga **dilarang keras** memodifikasi variabel inti konfigurasi framework (`FRAMEWORK_AUTH_TOKEN`, `FRAMEWORK_VERSION`).
- Jika sebuah plugin mengalami `fatal error` (misal memicu `exit 1` atau `set -e` failure), proses utama framework tidak boleh mati mendadak; framework harus menangkap kegagalan tersebut, membersihkan resource, dan mencatat event ke logging stream secara elegan.

* **Pertanyaan Diagnostik:**
  1. Mengapa memuat plugin via `source plugins/$plugin.sh` melanggar seluruh batasan isolasi di atas? 
  2. Rancang arsitektur *isolated execution layer* menggunakan *subshell execution wrapper* yang membungkus pemanggilan fungsi plugin, mengontrol `trap '...' ERR`, serta menggunakan atribut `readonly` untuk memproteksi variabel kritis parent environment dari mutasi atau *unsetting* oleh plugin.

---

## 4. Chapter Challenge

### Tantangan Praktis: Pembangunan Isolated Micro-Task Execution Framework ("BashTaskEngine")

#### Problem Statement
Di lingkungan CI/CD mission-critical, skrip automasi sering kali gagal secara katastropik karena fungsi pihak ketiga memanggil `exit`, mengubah working directory (`cd`) tanpa restorasi, memanipulasi *file descriptor*, atau mencemari environment global induk (`PATH`, `IFS`, token autentikasi). Anda ditugaskan membangun engine eksekusi task mikro yang sepenuhnya terisolasi, aman, dan modular murni menggunakan Bash built-in.

#### Requirements
1. **Engine Core (`run_isolated_task`)**:
   - Buat fungsi `run_isolated_task` yang menerima:
     - Argumen 1: Nama fungsi task yang akan dieksekusi.
     - Argumen 2: Variabel referensi (*pass-by-reference* via `declare -n`) untuk menampung stdout payload hasil eksekusi task.
     - Argumen sisa: Parameter yang akan diteruskan ke fungsi task.
2. **Isolasi Mutlak**:
   - Eksekusi fungsi harus berjalan dalam *execution boundary* terisolasi. Jika fungsi task mengeksekusi `exit 42`, parent script **tidak boleh berhenti**, melainkan menangkap exit code `42` tersebut.
   - Perubahan variabel environment, working directory (`cd /tmp`), atau redirection file descriptor di dalam task tidak boleh memengaruhi state parent runner.
3. **IPC Output & Error Segregation**:
   - Standard error (`stderr`) dari task harus tetap dialirkan ke `stderr` terminal secara real-time.
   - Standard output (`stdout`) dari task harus ditangkap ke dalam variabel referensi tanpa menggunakan temporary file fisik pada filesystem (manfaatkan process substitution atau memory pipe).
4. **Proteksi Waktu Eksekusi (Timeout Control)**:
   - Framework harus mendukung batasan waktu eksekusi (timeout) via variabel `TASK_TIMEOUT_SEC`. Jika task menggantung (*hang*), engine harus membunuh subshell task tersebut secara bersih (*graceful termination* via `SIGTERM`, lalu `SIGKILL` jika membandel) dan mengembalikan exit status `124`.

#### Constraints
- **Murni Bash 4.4+**: Dilarang menggunakan binary timeout eksternal (`/usr/bin/timeout`) untuk melatih pemahaman low-level signal handling dan job control di Bash.
- **Strict Mode Compliance**: Skrip framework induk harus berjalan di bawah `set -euo pipefail`.
- **Zero Temporary Files**: Tidak boleh ada penulisan file temporer di `/tmp` atau `/dev/shm` untuk penukaran state data.

#### Expected Output
Demonstrasikan kode implementasi lengkap dengan script pengujian (*unit-like verification*) yang membuktikan:
1. Task yang memanggil `exit 99` tertangkap dengan benar, mengembalikan status 99, dan runner melanjutkan loop task berikutnya.
2. Task yang melakukan `export DANGEROUS_STATE="HACKED"` dan `cd /` tidak mengubah environment dan working directory runner.
3. Task yang berjalan melewati batas `TASK_TIMEOUT_SEC` dibunuh secara otomatis dan exit status engine bernilai `124`.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Resolusi *Dynamic Scoping* pada Bash dan bagaimana variabel `local` diwariskan menuruni call stack ke fungsi downstream.
- [ ] Perbedaan implementasi kernel antara Subshell `( )` yang memicu `fork()` syscall dengan Command Grouping `{ }` yang hanya mengubah parser grouping di thread memori yang sama.
- [ ] Keterbatasan 8-bit unsigned integer pada mekanisme `return` dan paradigma fungsional pengembalian payload via `stdout` vs *pass-by-reference* (`declare -n`).
- [ ] Perilaku *Copy-on-Write* (COW) pada tabel memori saat forking subshell, serta implikasi mutasi variabel yang hilang (*variable scoping boundary*).
- [ ] Dampak arsitektural eksekusi pipeline (`cmd1 | cmd2`) terhadap penciptaan subshell dan cara mengendalikan posisi eksekusi parent via `lastpipe`.
- [ ] Mekanisme pewarisan environment via `export` dan alasan teknis mengapa modifikasi environment oleh proses anak bersifat searah (*unidirectional inheritance*).
- [ ] Perilaku variabel internal shell: `$$` (PID proses bootstrap script), `$BASHPID` (PID kontekstual aktual dari proses kernel yang sedang berjalan), dan `FUNCNEST` (depth counter pencegah recursion stack exhaustion).

### Saya tidak perlu menghafal:
- [ ] Seluruh nomor kode error POSIX sinyal internal kernel (cukup pahami konvensi umum 128 + Signal, misal: 130 untuk SIGINT, 137 untuk SIGKILL, 143 untuk SIGTERM).
- [ ] Struktur byte layout internal binary interpreter Bash saat memparsing Abstract Syntax Tree (AST) untuk deklarasi fungsi.
- [ ] Notasi syntax kuno/obsolescent deklarasi fungsi seperti variasi whitespace anomali pada sistem Bourne Shell legacy pra-POSIX.

### Saya harus bisa melakukan:
- [ ] Menggunakan `declare -n` (*namerefs*) untuk merancang fungsi modular dengan teknik *pass-by-reference* guna menghindari subshell overhead akibat command substitution `$(...)`.
- [ ] Mengamankan pipeline dari kehilangan mutasi state menggunakan Process Substitution (`done < <(command)`) atau integrasi `shopt -s lastpipe`.
- [ ] Mencegah kebocoran file descriptor pada fungsi modular dengan teknik duplikasi dan restorasi yang benar (`exec 3>&1`, `exec 1>&3 3>&-`).
- [ ] Menulis arsitektur dynamic module loader yang aman dengan memanfaatkan Subshell Isolation Wrappers untuk mengisolasi crash, polusi namespace, dan modifikasi state direktori.
- [ ] Melakukan debugging visual secara presisi pada lingkungan modular multi-level dengan memformat prompt `PS4` menggunakan `+$BASHPID:${BASH_SOURCE}:${LINENO}:${FUNCNAME[0]}()`.