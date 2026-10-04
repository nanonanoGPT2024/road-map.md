# BAB 01: Quiz, Challenge, & Knowledge Check
**Fondasi Shell, Terminal, & Arsitektur Eksekusi Bash**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Dekonstruksi Arsitektur TTY, PTY, Terminal Emulator, dan Shell
Jelaskan secara mendalam perbedaan arsitektural dan batas tanggung jawab (*separation of concerns*) antara:
1. Perangkat keras TTY/Terminal fisik (historical context).
2. Terminal Emulator (seperti Alacritty, GNOME Terminal, atau WezTerm).
3. PTY subsystem pada Linux Kernel (Master/Slave pair dan *line discipline*).
4. Shell (Bash itu sendiri).

Uraikan siklus transmisi data saat pengguna menekan tombol `Ctrl+C`: komponen mana yang menangkap *raw scancode*, komponen mana yang memproses *line discipline*, dan bagaimana sinyal POSIX (`SIGINT`) akhirnya dikirimkan ke target process group.

### Soal 1.2: Anatomi Siklus Hidup Eksekusi Perintah & Urutan Ekspansi
Sebelum sebuah baris instruksi dieksekusi oleh kernel melalui syscall `execve()`, Bash menjalankan serangkaian tahapan parsing dan ekspansi (*expansion pipeline*). 
1. Urutkan dan jelaskan secara deterministik tahapan ekspansi yang terjadi (Brace Expansion, Tilde Expansion, Parameter/Variable Expansion, Command Substitution, Arithmetic Expansion, Process Substitution, Word Splitting, dan Pathname Expansion/Globbing).
2. Mengapa urutan ini krusial terhadap keamanan sistem? Berikan satu contoh kasus di mana kesalahan asumsi urutan ekspansi dapat memicu *command injection* atau *arbitrary file overwrite*.

### Soal 1.3: Determinisme Resolusi Perintah (Lookup Hierarchy)
Ketika Anda mengetikkan sebuah identifier (misalnya: `test`) pada prompt Bash tanpa path absolut, Bash mengidentifikasi entitas yang akan dieksekusi berdasarkan hierarki preseden yang ketat.
1. Sebutkan urutan hierarki lengkap dari resolusi perintah di Bash (Aliases, Keywords, Functions, Builtins, External Binaries via `$PATH`, serta `hash` table).
2. Mengapa perintah manipulasi status proses dan shell seperti `cd`, `export`, `umask`, dan `ulimit` **secara absolut tidak mungkin** diimplementasikan sebagai binary eksternal independen di `/usr/bin/`? Jelaskan konsekuensi isolasi *virtual memory* proses Linux jika hal tersebut dipaksakan.

### Soal 1.4: Mekanisme Pewarisan Lingkungan dan Copy-On-Write (COW)
Ketika sebuah variabel dideklarasikan pada shell session (`FOO="bar"`), variabel tersebut tidak serta-merta tersedia pada child process sebelum dilakukan perintah `export FOO`.
1. Jelaskan mekanisme representasi memori variabel shell vs variabel lingkungan (*environment variables* berbasis `char **environ`) di level process control block (`task_struct`).
2. Apa yang terjadi pada alokasi memori halaman (*memory pages*) saat syscall `fork()` dipanggil untuk menjalankan sub-proses, bagaimana mekanisme Linux kernel *Copy-On-Write* (COW) memengaruhi performa startup process, dan mengapa child process tidak pernah bisa memutasi environment parent process secara direct memory write?

### Soal 1.5: Subshell Isolation vs Grouping Execution
Analisis perbedaan mendasar antara sintaks Subshell `( command1; command2 )` dan Grouping Execution `{ command1; command2; }`.
1. Ditinjau dari alokasi Process ID (PID), konsumsi stack/heap memori, dan retensi modifikasi variable terhadap shell pemanggil, jelaskan perbedaan operasional keduanya.
2. Jelaskan pula perbedaan mekanismenya dalam menangani *open file descriptors*, traps, dan status `$BASHPID` vs `$$`.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Asinkronisitas Pipeline dan Subshell Isolation Bug
Perhatikan potongan kode Bash berikut:
```bash
counter=0
cat /etc/passwd | while IFS=: read -r username _ _ _ _ _ _; do
    ((counter++))
done
echo "Total users processed: $counter"
```
1. Mengapa output dari baris terakhir selalu `Total users processed: 0` pada konfigurasi default Bash di Linux? Bedah perilaku kernel terkait pembuatan subshell pada sisi kanan pipeline POSIX (`|`).
2. Bagaimana cara kerja opsi `shopt -s lastpipe` menyelesaikan masalah tersebut, dan apa batasan lingkungan (*job control state*) agar `lastpipe` dapat berfungsi efektif? Tuliskan solusi alternatif yang idiomatik tanpa menggunakan `cat` dan tanpa pipeline subshell.

### Soal 2.2: Transisi PID 1, Syscall `execve()`, dan Signal Handling pada Container
Banyak *entrypoint script* container Docker/Kubernetes ditulis seperti ini:
```bash
#!/usr/bin/env bash
# Inisialisasi konfigurasi
setup_config() { /app/configure.sh; }
setup_config

# Jalankan daemon
/usr/bin/my-daemon --start
```
1. Analisis mengapa penulisan baris terakhir di atas merupakan anti-pattern fatal dalam arsitektur container microservices, khususnya terkait penerimaan sinyal `SIGTERM` dan `SIGKILL` dari container runtime saat proses deployment/eviction.
2. Mengapa mengganti baris tersebut menjadi `exec /usr/bin/my-daemon --start` menyelesaikan masalah tersebut? Jelaskan apa yang terjadi pada *process table entry*, PID, dan struktur alokasi memori ketika syscall `execve` dieksekusi tanpa didahului oleh `fork`.

### Soal 2.3: Redirection Precedence & Kernel VFS Duplication (`dup2`)
Dua instruksi berikut menghasilkan perilaku yang bertolak belakang ketika sebuah perintah menghasilkan data pada `stdout` dan `stderr`:
* Perintah A: `command > /var/log/app.log 2>&1`
* Perintah B: `command 2>&1 > /var/log/app.log`

1. Jelaskan pemrosesan kedua perintah tersebut dari sudut pandang kernel Linux file table, *file descriptor array* (FD 1 dan FD 2), pointer `struct file`, dan sistem panggilan `dup2()`.
2. Ke mana aliran byte dari standard output dan standard error bermuara pada Perintah B, dan jelaskan mengapa fenomena tersebut terjadi berdasarkan urutan *left-to-right evaluation* pada Bash redirection parser.

### Soal 2.4: Pathological Word Splitting & IFS Exploitation
Diberikan script audit keamanan yang menerima list path direktori:
```bash
scan_directories() {
    for dir in $1; do
        if [ -d $dir ]; then
            echo "Scanning directory: $dir"
            /usr/local/bin/deep-scan $dir
        fi
    done
}
scan_directories "$USER_INPUT"
```
1. Paparkan bagaimana skenario eksploitasi dapat terjadi jika `$USER_INPUT` mengandung spasi, karakter wildcard (`*`), newline, atau dimanipulasi melalui modifikasi variabel `$IFS` (*Internal Field Separator*).
2. Tuliskan refaktorisasi kode di atas dengan standard enterprise defensive programming: gunakan Bash arrays, double quoting yang ketat, dan null-delimited processing untuk menjamin keamanan dari *arbitrary command injection* maupun *path expansion attack*.

### Soal 2.5: WCE (Wait and Cooperative Exit) & Propagation Trap Sinyal
Ketika sebuah shell script mengeksekusi long-running pipeline atau child process di latar belakang (*background job*), penanganan sinyal seperti `SIGINT` atau `SIGTERM` sering kali tidak menghentikan child process tersebut, mengakibatkan *orphan/zombie process*.
1. Jelaskan implementasi POSIX "Wait and Cooperative Exit" (WCE) pada Bash: apa yang terjadi ketika pengguna menekan `Ctrl+C` saat Bash sedang menunggu eksekusi external process yang berada dalam foreground group?
2. Bagaimana desain idiomatis penulisan `trap` handler pada Bash yang menjamin seluruh child process group (`pgid`) dihentikan secara deterministik (*graceful shutdown followed by hard-kill*) saat parent script menerima `SIGTERM`?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Fork Bomb & Degradasi Kernel Task Tracker pada High-Throughput Cluster
**Konteks Masalah:**
Pada sebuah klaster compute node berbasis Ubuntu 22.04 LTS yang menjalankan pipeline automated CI/CD workers, node tiba-tiba berhenti merespons permintaan SSH. Metrik pemantauan menunjukkan CPU dan Memory utilitas berada di bawah 30%, namun sistem melempar eror masif:
`bash: fork: retry: Resource temporarily unavailable`
`bash: fork: Resource temporarily unavailable`

Investigasi pasca insiden menemukan sebuah build script internal yang mengotomasi kompilasi microservices mengeksekusi loop evaluasi status yang tidak deterministik:
```bash
#!/usr/bin/env bash
while ! check_service_ready; do
    log_status "Waiting for dependency..." &
    sleep 0.1
done
```
Fungsi `log_status` memanggil external binary `/usr/bin/date` dan mengirimkannya via network pipe.

**Pertanyaan Diagnostik:**
1. **Analisis Akar Masalah (RCA):** Jelaskan mengapa sistem kehabisan sumber daya meskipun CPU dan RAM masih longgar. Kaitkan analisis Anda dengan kernel limits (`/proc/sys/kernel/pid_max`, systemd `TasksMax`, dan `ulimit -u` / `nproc`).
2. **Kernel Impact:** Jelaskan dampak dari pembuatan puluhan ribu sub-proses tidak terkontrol ini terhadap Linux Kernel Scheduler (*Completely Fair Scheduler* - CFS) dan konsumsi *slab memory* (`task_struct` allocation).
3. **Mitigasi Arsitektural:** Rancang perbaikan pada Bash script tersebut agar memiliki mekanisme *concurrency throttling*, memanfaatkan builtins secara optimal tanpa fork eksternal binary, serta integrasi konfigurasi systemd cgroup v2 (`pids.max`) untuk mencegah insiden meluas ke level node-level panic.

---

### Skenario B: Race Condition dan Deadlock pada File Descriptor/FIFO Inter-Process Communication
**Konteks Masalah:**
Sebuah enterprise data platform menggunakan Bash worker untuk memproses streaming transaksi finansial berskala 100.000 events/detik. Arsitektur komunikasi antar-proses lokal menggunakan named pipe (FIFO) untuk menghubungkan ingestion engine dengan masking engine:

```bash
mkfifo /tmp/event_stream.fifo
# Producer process
cat /dev/incoming_device > /tmp/event_stream.fifo &
PRODUCER_PID=$!

# Consumer process
masking_engine < /tmp/event_stream.fifo > /data/clean_stream.log &
CONSUMER_PID=$!

wait $PRODUCER_PID $CONSUMER_PID
```
Pada kondisi beban puncak (load spikes), sistem sering mengalami *deadlock* total. Output berhenti mengalir, proses berada dalam state `D` (*Uninterruptible Sleep*) atau `S` (*Interruptible Sleep*), dan named pipe tidak lagi menerima I/O.

**Pertanyaan Diagnostik:**
1. **Analisis VFS & Pipe Deadlock:** Jelaskan semantik Linux VFS terkait pembukaan named pipe (`open(2)`) dengan flag `O_RDONLY` vs `O_WRONLY`. Apa yang terjadi ketika buffer pipe default kernel (64 KB / 16 halaman memori) penuh dan proses consumer melambat?
2. **Broken Pipe Handling:** Apa yang terjadi jika proses `masking_engine` mengalami *crash* mendadak? Jelaskan aliran sinyal POSIX (`SIGPIPE`) yang dikirim ke `PRODUCER_PID`, bagaimana default behavior Bash terhadap `SIGPIPE`, dan mengapa producer berpotensi menjadi *zombie* atau *hanging process*.
3. **Remediasi:** Rekonstruksi arsitektur eksekusi script ini menggunakan redirection dua arah (*bi-directional FD*), pemanfaatan Coprocess (`coproc`), pengelolaan non-blocking I/O (`fcntl` / timeout via `read -t`), dan error trap yang deterministik.

---

### Skenario C: Stateful Session Leaks dan Env Contamination pada Multi-Tenant CI Runner
**Konteks Masalah:**
Sebuah platform testing internal mengeksekusi puluhan bash test suites yang ditulis oleh berbagai tim pengembang secara berurutan dalam satu shared agent runner. Untuk efisiensi performa startup, platform tidak menggunakan ephemeral containers, melainkan mengeksekusi test script secara berurutan pada parent shell environment yang sama:

```bash
# Runner orchestrator loop
for test_script in /suites/*.sh; do
    echo "Executing $test_script"
    source "$test_script"
    if [ $? -ne 0 ]; then
        alert_failure "$test_script"
    fi
done
```
Setelah berjalan beberapa jam, test runner mulai menghasilkan *false positives* dan *false negatives*. Sebuah script yang sukses mendefinisikan variable readonly (`declare -r TOKEN="xyz"`), script lain memodifikasi `$PATH`, fungsi bawaan shell di-override, dan `umask` sistem berubah permanen menjadi `0000`, menyebabkan celah keamanan file permissions.

**Pertanyaan Diagnostik:**
1. **Analisis Kontaminasi Shell Context:** Jelaskan secara teknis mengapa penggunaan perintah `source` (atau `.`) menjadi penyebab kehancuran determinisme pengujian ini. Identifikasi 4 state shell yang termutasi dan tidak diisolasi ketika menggunakan `source`.
2. **Kelemahan Error Handling `$?`:** Jelaskan mengapa pemeriksaan `if [ $? -ne 0 ]` rentan gagal mendeteksi error tersembunyi (*silent failures*) di dalam `$test_script` jika skrip tersebut mengeksekusi pipeline atau memiliki command terakhir yang berhasil dieksekusi meskipun command krusial di atasnya gagal (`set -e` vs `set -o pipefail` behavior).
3. **Arsitektural Redesign:** Rancang arsitektur eksekusi baru yang menjamin isolasi total antartes tanpa menggunakan full container virtualization:
   * Pertimbangkan isolasi process space.
   * Pertimbangkan penanganan environment sanitization (`env -i`).
   * Terapkan *secure execution sandbox* menggunakan subshell yang strict, trapping return signals, reset descriptors, dan penegakan umask.

---

## 4. Chapter Challenge

### Tantangan Praktis: Implementasi Process Supervisor & Deterministic Task Runner ("BashVanguard")

#### Deskripsi Masalah:
Banyak production outage disebabkan oleh Bash wrapper script yang tidak menangani status eksekusi dengan aman, meninggalkan proses anak (*dangling/orphan child*), gagal meneruskan sinyal shutdown, atau mengalami parsing bug saat menangani argumen dinamis. Anda diminta membangun sebuah engine supervisor mini berstandar industri dengan Bash murni (*Pure Bash*) tanpa third-party binary wrapper seperti `dumb-init` atau `tini`.

#### Persyaratan Teknis (Requirements):
1. **Strict Initialization:** 
   * Skrip harus dijalankan dengan standard keamanan tinggi: `set -euo pipefail` serta tracking environment variables secara deterministik.
   * Reset `IFS` ke nilai default system dan verifikasi minimal Bash versi 5.0+.
2. **Dynamic Trap Engine:**
   * Tangkap sinyal `SIGINT`, `SIGTERM`, `SIGHUP`, dan `ERR`.
   * Saat sinyal shutdown (`SIGTERM`/`SIGINT`) diterima, supervisor harus mengirim `SIGTERM` ke seluruh process group-nya (`-PGID`), menunggu masa *graceful period* maksimal 10 detik, dan jika child process belum mati, kirim `SIGKILL` secara paksa.
3. **Sandboxed Worker Execution:**
   * Script harus mampu menerima argumen arbitrary command beserta flags dan argumen arbitrary secara aman:
     ```bash
     ./bash_vanguard.sh --timeout=30 --log-file=/var/log/worker.log -- /path/to/work-binary --arg1 "data with spaces"
     ```
   * Eksekusi target command harus terisolasi dari mutable parent state (menggunakan clean environment passing).
4. **Custom File Descriptor Routing:**
   * Tidak boleh menggunakan direct inline output redirection (`> file 2>&1`) di command level. 
   * Supervisor harus mengalokasikan File Descriptor kustom (misal FD 3 dan FD 4) via dynamic allocation (`exec {log_fd}>"$log_file"`), menduplikasi stream, dan menjamin cleanup penutupan FD saat script exit.
5. **Deterministic Exit Codes:**
   * Jika child process selesai normal, kembalikan exit code asli dari child process tersebut.
   * Jika child process timeout, matikan proses dan kembalikan exit code standar POSIX untuk timeout (124).
   * Jika child process mati karena sinyal tak tertangani, kembalikan exit code 128 + nomor sinyal.

#### Batasan Implementasi (Constraints):
* **No external supervisor tools:** Dilarang menggunakan binary eksternal `tini`, `dumb-init`, `timeout` (wajib implementasi built-in timer atau pure bash loop + sleep monitor), atau framework eksternal.
* **POSIX / Linux Native:** Harus bekerja pada platform Linux kernel 4.x / 5.x / 6.x dengan Bash 5.0+.
* **Memory Safe:** Script tidak boleh membiarkan background monitor loop terus berjalan (*no memory/thread leak*).

#### Format Output & Pembuktian (Verification):
Skrip supervisor Anda harus diverifikasi dengan skenario stress-test berikut:
1. Menjalankan dummy worker script yang *uncooperative* (mengabaikan sinyal biasa) dan memverifikasi timeout + escalasi `SIGKILL`.
2. Menjalankan worker yang mencetak payload kompleks (null bytes, special characters, whitespace) dan memverifikasi integritas log.
3. Simulasi `kill -15 <supervisor_pid>` dari terminal eksternal dan verifikasi bahwa tidak ada satu pun child process yang tertinggal pada `ps -ef` atau `pgrep`.

---

## 5. Knowledge Check & Checklist

Gunakan checklist ini untuk mengaudit pemahaman Anda terhadap arsitektur internal Bash dan POSIX shell runtime.

### Saya harus memahami:
- [ ] Batas arsitektural antara Hardware Terminal, Terminal Emulator, Kernel TTY/PTY Driver (*line discipline*), dan Shell.
- [ ] Siklus hidup pemrosesan instruksi Bash: Tokenization $\rightarrow$ Parsing $\rightarrow$ Compound Command Construction $\rightarrow$ Parameter/Arithmetic/Command/Filename Expansion $\rightarrow$ Redirection $\rightarrow$ Execution.
- [ ] Aturan lookup resolusi perintah Bash: Aliases $\rightarrow$ Reserved Keywords $\rightarrow$ Functions $\rightarrow$ Builtins $\rightarrow$ Hash Table $\rightarrow$ Search `$PATH`.
- [ ] Cara kerja syscall `fork()`, `execve()`, `clone()`, dan `waitpid()` pada eksekusi command shell.
- [ ] Mekanisme alokasi kernel *Copy-On-Write* (COW) saat proses shell membelah diri menjadi child process.
- [ ] Perbedaan memori dan proses antara subshell `(...)`, grouping `{...;}`, dan background execution `&`.
- [ ] Mekanisme kerja File Descriptor level kernel: struktur `files_struct`, pointer file table, dan penggunaan syscall `dup2()` pada redirection operator (`<`, `>`, `2>&1`, `>&-`).
- [ ] Dampak arsitektur POSIX pipeline (`cmd1 | cmd2`) terhadap subshell context, alokasi PID, serta variabel mutability.
- [ ] Perilaku transmisi sinyal POSIX (`SIGINT`, `SIGTERM`, `SIGHUP`, `SIGPIPE`, `SIGCHLD`) dan semantik WCE (Wait and Cooperative Exit).
- [ ] Karakteristik Bash PID 1 di dalam Linux containers: masalah zombie reaping dan signal swallow.

### Saya tidak perlu menghafal:
- [ ] Nomor hexadecimal spesifik untuk scancode ASCII/VT100 terminal control sequences.
- [ ] Detail internal macro implementation dari C source code `bash` (seperti struktur union C pada `parse.y`).
- [ ] Daftar lengkap seluruh parameter bawaan Bash manual (`man bash`) yang jarang digunakan, selama memahami cara mencarinya via manual page dan POSIX reference.
- [ ] Nilai numerik integer seluruh sinyal Linux selain sinyal standar (`SIGHUP=1`, `SIGINT=2`, `SIGKILL=9`, `SIGTERM=15`, `SIGCHLD=17`).

### Saya harus bisa melakukan:
- [ ] Menganalisis dan men-debug system calls yang dipicu oleh script Bash menggunakan tool tracing seperti `strace` (misal: melacak pemanggilan `fork`, `execve`, `dup2`).
- [ ] Mengonfigurasi environment strict defensif (`set -euo pipefail`, `IFS=$'\n\t'`) secara kontekstual tanpa merusak logic program.
- [ ] Mengarahkan *file descriptor* arbitrary (FD 3 ke atas) secara programmatic menggunakan sintaks modern Bash `exec {var}>&1`.
- [ ] Mengeliminasi process injection vulnerability dengan quoting strategy yang deterministik pada parameter expansion.
- [ ] Menulis sinyal trap handler yang tangguh untuk membersihkan alokasi temporary file, named pipe (FIFO), dan menghentikan child process group secara atomik saat script crash atau dihentikan paksa.
- [ ] Mengidentifikasi dan memecahkan masalah subshell variable loss pada pipeline menggunakan redirection loop (*process substitution* atau *heredoc/herestring*) atau `lastpipe`.