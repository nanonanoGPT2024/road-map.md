# BAB 07: Quiz, Challenge, & Knowledge Check
**Job Control, Process Lifecycle, & Asynchronous Concurrency**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Anatomi System Call Fork-Exec dan Copy-On-Write (COW)
Ketika Bash mengeksekusi subshell asinkron (misalnya `( do_work ) &`) versus mengeksekusi binary eksternal (misalnya `/usr/bin/ffmpeg &`), kernel Linux memanggil urutan *system call* yang berbeda. 
* Jelaskan secara teknis siklus transisi dari `fork()`, `execve()`, hingga alokasi memori virtual melalui mekanisme *Copy-On-Write* (COW).
* Apa implikasi performa dan jejak memori (*memory footprint*) jika sebuah skrip Bash yang telah mengonsumsi variabel array sebesar 2 GB di memori melakukan `fork()` untuk ratusan proses anak?

### Soal 1.2: Matriks Sinyal IPC: Trap Masking dan Non-Catchable Signals
Sinyal POSIX adalah mekanisme asynchronous notification antar-proses. Bandingkan karakteristik perilaku dan penanganan kernel untuk pasangan sinyal berikut:
1. `SIGINT` (2) vs `SIGQUIT` (3)
2. `SIGTERM` (15) vs `SIGKILL` (9)
* Mengapa arsitektur kernel Linux secara mutlak melarang proses pengguna menangkap (*catch*), memblokir (*mask*), atau mengabaikan (*ignore*) sinyal `SIGKILL` dan `SIGSTOP`? 
* Jelaskan skenario di mana proses yang berstatus `D` (*Uninterruptible Sleep*) menolak mati meskipun telah dikirimi sinyal `kill -9`.

### Soal 1.3: Terminal Foreground Process Group vs Background Process Group
Dalam konteks interaktif POSIX Job Control:
* Jelaskan peran *Process Group ID* (PGID), *Session ID* (SID), dan bagaimana kernel mengontrol kepemilikan terminal pengontrol (*controlling terminal*) via syscall `tcsetpgrp()`.
* Apa yang terjadi secara internal di tingkat kernel ketika sebuah proses yang berjalan di latar belakang (*background job*) mencoba membaca dari standard input (`stdin`) atau menulis ke standard output (`stdout`) terminal, dan bagaimana peran sinyal `SIGTTIN` serta `SIGTTOU` dalam mekanisme ini?

### Soal 1.4: Patologi Siklus Hidup Proses: Zombie (`Z`) vs Orphan
* Uraikan perbedaan siklus hidup antara *Zombie (Defunct) Process* dan *Orphan Process*. 
* Mengapa entri Zombie masih membutuhkan slot di dalam *Kernel Process Table* (`struct task_struct`), dan mengapa eksekusi `kill -9 <PID_ZOMBIE>` tidak akan pernah berhasil mematikan proses tersebut?
* Jelaskan bagaimana mekanisme *reparenting* bekerja pada Linux modern, khususnya keterlibatan `systemd` (PID 1) atau inisialisasi thread dengan flag `PR_SET_CHILD_SUBREAPER`.

### Soal 1.5: Semantik Builtin `wait` dan Pengambilan Asynchronous Exit Status
Ketika sebuah proses dilepas ke latar belakang menggunakan operator `&`, Bash menyimpan entri proses tersebut ke dalam internal *jobs table*.
* Jelaskan bagaimana mekanisme pengembalian *Exit Status* (`$?`) bekerja ketika skrip memanggil `wait $PID` dibandingkan dengan memanggil `wait` tanpa argumen.
* Apa yang terjadi jika proses anak selesai dieksekusi jauh sebelum perintah `wait $PID` dipanggil oleh shell induk? Di mana exit status tersebut disimpan sementara waktu dan bagaimana kernel mencegah hilangnya metadata tersebut?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Perilaku Isolasi Sinyal pada Subshell vs Grouping Environment
Diberikan dua struktur eksekusi berikut:
```bash
# Struktur A
trap 'echo "Parent Cleanup"' EXIT
( trap 'echo "Subshell Cleanup"' EXIT; sleep 10 )

# Struktur B
trap 'echo "Parent Cleanup"' EXIT
{ trap 'echo "Block Cleanup"' EXIT; sleep 10; }
```
* Analisis perbedaan eksekusi signal trap pada Struktur A dan Struktur B saat menerima sinyal `SIGINT` di tengah eksekusi `sleep 10`.
* Mengapa pada Struktur B trap `EXIT` milik parent tertimpa secara permanen, sementara pada Struktur A tidak? Jelaskan mekanisme internal Bash dalam mengkloning dan merestorasi *trap execution context*.

### Soal 2.2: Coprocess (`coproc`) dan Deadlock pada File Descriptor Pipe
Bash menyediakan konstruksi `coproc` untuk interaksi dua arah secara asinkron.
* Jelaskan bagaimana kernel mengalokasikan array file descriptor `${COPROC[0]}` (output proses) dan `${COPROC[1]}` (input proses).
* Analisis skenario deadlock yang umum terjadi ketika data yang dikirimkan melewati batas kapasitas buffer pipa Linux (*Linux pipe buffer capacity*, default 64KB) tanpa adanya pembacaan aktif. Bagaimana Anda mendesain mekanisme I/O multiplexing atau non-blocking read untuk mengatasinya murni di Bash?

### Soal 2.3: Skalabilitas Concurrency: Analisis Kritis `wait -n`
Bash 4.3 memperkenalkan `wait -n` (menunggu *setiap satu* job selesai dari kumpulan background jobs).
* Bagaimana Anda memanfaatkan `wait -n` untuk membuat *worker pool* dinamis dengan kapasitas konstan $N$?
* Jelaskan kelemahan (*race condition* dan hilangnya exit status) dari implementasi `wait -n` pada Bash versi sebelum 5.1 ketika beberapa proses anak selesai hampir bersamaan (*burst completion*), dan bagaimana Bash 5.1+ merevisi perilaku ini dengan parameter array output.

### Soal 2.4: Interupsi Syscall dan Karakteristik Blocking pada Foreground `sleep`
Perhatikan skrip berikut:
```bash
#!/usr/bin/env bash
trap 'echo "Handling SIGTERM"; exit 0' SIGTERM
sleep 300
```
Jika sinyal `SIGTERM` dikirim ke skrip ini saat `sleep 300` berjalan di foreground:
* Mengapa handler trap tidak langsung tereksekusi pada beberapa varian sistem operasi POSIX sampai `sleep` selesai, sedangkan jika skrip diubah menjadi:
```bash
sleep 300 &
wait $!
```
handler trap dapat langsung tereksekusi seketika?
* Jelaskan dari perspektif penanganan *restartable system calls* (`SA_RESTART`) dan bagaimana kernel mengembalikan kontrol ke shell interpreter saat interupsi terjadi.

### Soal 2.5: Subshell Pipeline Mutability vs Process Substitution IPC
Banyak engineer pemula membuat bug logika berikut:
```bash
count=0
cat metrics.txt | while read -r line; do
    ((count++))
done
echo "Total: $count" # Output selalu 0
```
* Terangkan secara mendalam arsitektur proses di balik fenomena di atas (tinjau dari alokasi *subshell* pada pipeline POSIX).
* Bandingkan performa dan arsitektur IPC jika kode di atas diubah menggunakan *Process Substitution*:
```bash
count=0
while read -r line; do
    ((count++))
done < <(cat metrics.txt)
echo "Total: $count"
```
Jelaskan mengapa pendekatan kedua berhasil mempertahankan mutabilitas variabel `count` dan apa yang terjadi pada *Named Pipe* (`/dev/fd/XX` atau FIFO anonim) di balik layar.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Fork Bomb dan PID Exhaustion di Lingkungan Container Minimalist
Sebuah microservice analitik berbasis container Docker (menggunakan *base image* Alpine Linux) menjalankan sebuah skrip Bash entrypoint `pipeline.sh` sebagai PID 1. Skrip ini bertugas memicu ratusan sub-task pemrosesan data paralel melalui loop:
```bash
for file in /data/*.gz; do
    process_chunk "$file" &
done
wait
```

**Insiden:**
Setelah beberapa jam di produksi, sistem menolak koneksi SSH ke node host, dan kernel meluncurkan peringatan:
`kernel: cgroups: fork rejected by pids controller in /docker/...`
Pemeriksaan dengan `docker exec` gagal dengan error: `OCI runtime exec failed: unable to start container process: fork/exec: resource temporarily unavailable`. Container membeku dan tidak merespons `SIGTERM` dari `docker stop`.

**Tugas Diagnostik & Solusi:**
1. Mengapa Bash yang berjalan sebagai PID 1 di dalam Linux Container secara default tidak otomatis membersihkan child processes yang telah mati (*zombie reaping failure*), dan mengapa PID 1 mengabaikan sinyal terminating default?
2. Bagaimana Anda merancang arsitektur ulang loop pemrosesan tersebut agar menerapkan konkurensi terkontrol (*throttling*) tanpa menghabiskan slot PID sistem (*PID exhaustion*)?
3. Jelaskan dua metode mitigasi tingkat container: integrasi init system minimal (seperti `tini` / `dumb-init`) dan konfigurasi limit kernel cgroup.

---

### Skenario B: Race Condition dan Deadlock pada File Redirection Mutex
Sebuah sistem agregasi log multi-worker dibangun menggunakan skrip Bash yang menjalankan 20 worker paralel. Semua worker menulis hasil parsing data JSON ke satu file agregasi utama `/var/log/aggregated.log`:
```bash
# worker.sh
parse_event "$input" >> /var/log/aggregated.log &
```
Secara sporadis, log agregasi mengalami anomali:
* Beberapa baris JSON terpotong dan bercampur dalam satu baris yang sama (*corrupted/interleaved records*).
* Ketika tim menambahkan penguncian file menggunakan file lock manual:
```bash
while ! ln -s /tmp/lock.target /tmp/file.lock 2>/dev/null; do
    sleep 0.01
done
# Critical Section: Write data
rm -f /tmp/file.lock
```
Sistem mengalami *deadlock* permanen ketika salah satu worker mengalami crash (OOM killed) tepat di dalam critical section.

**Tugas Diagnostik & Solusi:**
1. Jelaskan mengapa redirection `>>` (*O_APPEND*) pada Linux tidak menjamin *atomic write* ketika ukuran data melampaui ambang batas `PIPE_BUF` atau ukuran cluster block file system.
2. Identifikasi *single point of failure* (SPOF) dari implementasi symlink locking di atas saat worker terbunuh secara abnormal (`SIGKILL`).
3. Rancang mekanisme locking yang aman (*fail-safe atomic locking*) menggunakan *system advisory lock* `flock(2)` murni dari Bash, yang menjamin *lock release* otomatis bahkan jika proses worker mati terbunuh secara paksa.

---

### Skenario C: Graceful Degradation vs Zombie Leaks pada Batch Processing Cluster
Skrip orkestrator batch `batch_runner.sh` mendistribusikan ribuan pekerjaan rendering grafis ke mesin 64-core. Arsitektur lama menggunakan skema token-bucket sederhana via Named Pipe (FIFO) untuk membatasi 64 konkurensi:
```bash
# Inisialisasi token
mkfifo /tmp/token_pipe
exec 3<>/tmp/token_pipe
for ((i=0; i<64; i++)); do echo >&3; done

for job in "${jobs[@]}"; do
    read -u 3
    {
        render "$job"
        echo >&3
    } &
done
wait
exec 3>&-
rm -f /tmp/token_pipe
```

**Masalah Arsitektural:**
Ketika administrator membatalkan pipeline menggunakan kombinasi `Ctrl+C` atau orkestrator CI/CD mengirimkan `SIGTERM`:
* Skrip utama langsung berhenti, namun ke-64 background worker tetap berjalan liar (*orphaned*) membebani CPU hingga 100%.
* Pipe FIFO `/tmp/token_pipe` tertinggal di disk, memicu kegagalan fatal pada eksekusi pipeline berikutnya.
* Beberapa worker yang mencoba mengembalikan token `echo >&3` setelah token pipe ditutup mengalami crash akibat sinyal `SIGPIPE`.

**Tugas Diagnostik & Solusi:**
1. Uraikan desain *Signal Cascade Trap Architecture* yang mampu menyebarkan sinyal terminasi (`SIGTERM`, `SIGINT`) ke seluruh *process tree* yang relevan secara atomik tanpa menyisakan proses anak yang terisolasi.
2. Bagaimana Anda mengamankan file descriptor dan Named Pipe sementara (menggunakan pattern `mktemp -d` dan bind trap `EXIT`) agar *resource leak* tidak terjadi terlepas dari bagaimana skrip berhenti (*clean exit, error abort, or signal kill*)?
3. Evaluasi *trade-off* performa antara implementasi Bash FIFO semaphore di atas dibandingkan dengan eksekusi berbasis GNU Parallel atau tool native runtime (Go/Rust worker). Kapan Bash mencapai titik jenuhnya (*interpreter overhead bottleneck*)?

---

## 4. Chapter Challenge

### Tantangan Praktis: Enterprise Concurrency Throttle Engine (`bpool`)

#### Problem Statement
Di lingkungan infrastruktur skala enterprise, eksekusi pemrosesan data paralel sering kali dilakukan menggunakan Bash secara serampangan (menggunakan looping tanpa limitasi proses), yang mengakibatkan sistem mengalami *load spike*, kegagalan alokasi memori, hingga instabilitas OS. Anda diminta untuk merancang dan mengimplementasikan modul Bash murni berstandar produksi bernama **`bpool` (Bash Process Pool Engine)**.

Modul ini harus bertindak sebagai *orchestrator wrapper* yang mampu mengontrol jumlah eksekusi proses paralel, mengumpulkan status keluar dari setiap task, mencegah kebocoran proses zombie, dan merespons interupsi sistem secara elegan (*graceful shutdown*).

#### Requirements
1. **Concurrency Control:**
   * Script harus membatasi eksekusi paralel maksimum $N$ task secara ketat (dapat dikonfigurasi via parameter flags, misal: `-j 4` untuk 4 parallel jobs).
   * Slot worker harus segera diisi kembali sesegera mungkin setelah satu task selesai (*dynamic queue-based consumption*), tidak boleh menunggu seluruh batch $N$ selesai (*no batch-wait barrier*).
2. **Robust Signal Handling & Cascading:**
   * Jika menerima sinyal `SIGINT` atau `SIGTERM`, `bpool` harus menghentikan penugasan task baru, menyebarkan sinyal terminasi ke seluruh proses anak yang sedang aktif dalam process group-nya, menunggu anak-anak tersebut benar-benar mati, melakukan *cleanup* file sementara, lalu keluar dengan exit status `130` atau `143`.
3. **Failure Isolation & Exit Aggregation:**
   * Kegagalan satu task (non-zero exit code) tidak boleh menggugurkan eksekusi task lain yang sedang berjalan.
   * `bpool` harus mencatat dan menampilkan rekapitulasi status keluar: berapa task berhasil (exit `0`) dan berapa task gagal (exit `!= 0`), serta mengembalikan exit status global `1` jika minimal ada satu task yang gagal.
4. **Zero-Leak Guarantee:**
   * Skrip tidak boleh meninggalkan:
     * Zombie processes di tabel kernel.
     * File sementara atau FIFO (pipe) di sistem berkas (`/tmp`).
     * File descriptor terbuka yang tidak terpakai (*FD leaks*).

#### Constraints
* **Shell Compatibility:** Bash 4.4+ (Pure Bash).
* **Strict Mode:** Wajib menggunakan `set -euo pipefail`.
* **Zero Heavy Dependencies:** Dilarang menggunakan `xargs`, `parallel`, Python, atau runtime eksternal lainnya. Hanya diperbolehkan menggunakan Bash builtins dan POSIX standard coreutils (`kill`, `wait`, `read`, `trap`, `mkfifo`, `mktemp`, `rm`).
* **Resource Descriptors:** Seluruh komunikasi IPC internal harus menggunakan alokasi file descriptor yang aman (FD 3 ke atas, hindari konflik dengan 0, 1, dan 2).

#### Expected Output
Skrip Anda harus mampu dieksekusi dengan struktur serupa:
```bash
./bpool -j 4 --tasks-file tasks.txt
```
Dengan format visual logging di terminal:
```text
[INFO] Initialized bpool with concurrency limit: 4
[RUN] Task 1 started (PID: 10423)
[RUN] Task 2 started (PID: 10424)
[RUN] Task 3 started (PID: 10425)
[RUN] Task 4 started (PID: 10426)
[DONE] Task 2 finished successfully (PID: 10424, Status: 0)
[RUN] Task 5 started (PID: 10450)
...
[SIGNAL] SIGINT intercepted! Propagating termination to active workers: 10423 10425 10426 10450...
[CLEANUP] All workers terminated. Temporary IPC resources unlinked.
[SUMMARY] Total: 5, Succeeded: 1, Failed/Aborted: 4
```

---

## 5. Knowledge Check & Checklist

Gunakan checklist ini untuk melakukan audit mandiri terhadap pemahaman materi sebelum melangkah ke bab berikutnya.

### Saya harus memahami:
- [ ] Mekanisme kernel POSIX terkait siklus hidup proses: transisi state (`R`, `S`, `D`, `Z`, `T`), *Process Table*, dan struktur `task_struct`.
- [ ] Perbedaan fungsionalitas dan arsitektur pemanggilan antara `fork()`, `vfork()`, `execve()`, dan dampaknya pada Copy-On-Write (COW).
- [ ] Semantik sinyal kernel: perbedaan delivery sinyal sinkron vs asinkron, peran *interrupt mask*, serta karakteristik uncatchable signals (`SIGKILL`, `SIGSTOP`).
- [ ] Konsep POSIX Job Control: Process Group ID (PGID), Session Leader, Terminal Access Control via `tcsetpgrp()`, dan sinyal `SIGTTIN`/`SIGTTOU`.
- [ ] Patologi proses: Definisi eksak Zombie process, mitigasi pembentukan Zombie via PID 1 / Subreaper reaping, dan konsekuensi *Orphan reparenting*.
- [ ] Arsitektur Subshell vs Group Command, alokasi memori independen subshell, dan perlakuan isolasi lingkungan variabel.
- [ ] Pemanfaatan IPC bawaan Bash: Anonymous Pipes, Named Pipes (FIFO), Process Substitution, dan bidirectional IPC menggunakan `coproc`.
- [ ] Batasan atomisitas operasi file system (`O_APPEND`, `PIPE_BUF`) dan penggunaan advisory locking melalui `flock(2)` untuk sinkronisasi multi-proses.

### Saya tidak perlu menghafal:
- [ ] Nomor integer sinyal POSIX non-standar di arsitektur non-x86 (cukup gunakan nama sinyal simbolik seperti `SIGTERM`, bukan representasi numeriknya).
- [ ] Kode implementasi struktur data C internal kernel Linux (misalnya representasi linked-list dari `sched_entity`).
- [ ] Sintaks flag usang dari sistem non-POSIX/System V job control.
- [ ] Tabel nomor sistem panggilan (*syscall numbers*) untuk arsitektur CPU spesifik.

### Saya harus bisa melakukan:
- [ ] Membangun *concurrency throttle engine* / *worker pool* berkapasitas dinamis murni dengan Bash menggunakan `wait -n` atau Named Pipe IPC.
- [ ] Mendesain skrip tahan banting (*fault-tolerant*) dengan trap handler terpadu untuk `EXIT`, `SIGINT`, `SIGTERM`, dan `HUP` guna menjamin zero-resource-leak.
- [ ] Melakukan debugging dan terminasi proses runaway/zombie menggunakan utilitas CLI tingkat lanjut: `ps -eo pid,ppid,stat,cmd`, `pgrep`, `pkill`, `strace`, dan eksplorasi `/proc/<PID>/`.
- [ ] Menggunakan `flock` secara presisi dalam Bash untuk melindungi *critical section* pada multi-process concurrent access.
- [ ] Mengonfigurasi container entrypoint skrip dengan penanganan sinyal yang benar untuk mencegah pengabaian sinyal `SIGTERM` oleh PID 1.
- [ ] Menulis pipeline kompleks dengan *Process Substitution* untuk menghindari hilangnya mutasi state variabel akibat subshell isolation.