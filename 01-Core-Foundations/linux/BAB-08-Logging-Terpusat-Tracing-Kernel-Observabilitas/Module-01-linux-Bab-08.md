## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** Linux Systems Engineering & Infrastructure Architecture
*   **Kategori:** 01-Core-Foundations
*   **Bab 08:** Logging Terpusat, Tracing Kernel, dan Observabilitas
*   **Modul 01:** Arsitektur Logging Linux, Kernel Tracing, dan Fondasi Observabilitas Sistem
*   **Tingkat Kesulitan:** Advanced / Enterprise-Grade
*   **Prasyarat:** Pemahaman mendalam tentang Linux Kernel Space vs User Space, Socket IPC (`AF_UNIX`, `AF_INET`), System Call Interface, POSIX Signals, Manajemen Daemon `systemd`, dan Jaringan TCP/IP Dasar.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, engineer diharapkan mampu:

1.  **Menganalisis dan Membedah Jalur Logging Linux:** Mengurai transmisi pesan log mulai dari pemanggilan `printk()` di kernel space, abstraksi socket `/dev/log` dan `/dev/kmsg`, hingga penanganan paralel oleh `systemd-journald` dan `rsyslog`.
2.  **Merancang dan Mengonfigurasi Agregasi Log Aman:** Mengonfigurasi `rsyslog` dan `systemd-journal-remote` untuk pengiriman log terpusat dengan enkripsi mutual TLS (mTLS) dan protokol andal (RELP) guna menjamin zero-message-loss.
3.  **Mengoperasikan Subsistem Kernel Tracing Rendah Overhead:** Menggunakan `ftrace`, dynamic tracepoints, `kprobes`, dan `uprobes` via antarmuka `tracefs` tanpa modul eksternal pihak ketiga.
4.  **Menerapkan Observabilitas Berbasis eBPF Tingkat Dasar:** Menyusun dan menjalankan probe observabilitas menggunakan `bpftrace` untuk mengukur latensi I/O disk dan eksekusi syscall secara real-time.
5.  **Mendeteksi dan Memitigasi Bottleneck Observabilitas:** Mengidentifikasi kondisi *log-drop*, *buffer overrun*, dan overhead performa yang diakibatkan oleh instrumentasi tracing yang agresif.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                       [ Linux Observability Stack ]
                                     |
         +---------------------------+---------------------------+
         |                                                       |
[ Telemetri & Event Logging ]                             [ Dynamic Tracing ]
         |                                                       |
   +-----+-----+                                           +-----+-----+
   |           |                                           |           |
[Kernel Space] [User Space]                           [Kernel Space] [User Space]
   |           |                                           |           |
printk()     syslog(3) / libc                         tracefs / eBPF   uprobes
   |           |                                           |           |
/dev/kmsg    /run/systemd/journal/dev-log             Tracepoints/     Glibc wrappers
   |           |                                      kprobes/kretprobes
   +-----+-----+                                           |
         |                                            ring_buffer
  systemd-journald (Binary Journal)                        |
         |                                            bpftrace / perf
  Forwarding (Socket IPC / In-Memory Queue)
         |
      rsyslog (Rainerscript Engine)
         |
    +----+----+
    |         |
Local FS   Remote SIEM/Log Collector (via RELP/TLS)
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Sistem produksi modern berskala masif tidak dapat ditoleransi memiliki titik buta (*blind spots*). Ketika latensi P99 sebuah microservice melonjak atau sistem crash dengan status *Kernel Panic*, inspeksi pasca-kejadian (post-mortem) bergantung sepenuhnya pada kualitas data telemetri yang tercatat.

1.  **Kehilangan Bukti Forensik:** Logging standar via plain UDP syslog rentan mengalami *silent packet drop* saat terjadi lonjakan trafik atau serangan DoS. Tanpa arsitektur logging bertingkat (*tiered*), pesan crash krusial tidak pernah sampai ke storage persisten.
2.  **Limitasi Metrik Agregat:** Metrik CPU dan memory berbasis polling interval (seperti Prometheus node\_exporter tiap 15 detik) tidak mampu mendeteksi *micro-bursts* I/O atau syscall blocking berdurasi 50 milidetik yang melumpuhkan thread runtime aplikasi.
3.  **Biaya Operasional Tracing Non-Invasif:** Menggunakan profiler berbasis debugger (`gdb` atau `strace` berulang) pada beban produksi menghentikan eksekusi (*stop-the-world*) dan memberikan overhead hingga ratusan persen. Pemahaman atas *kernel tracing primitives* (`ftrace`, `eBPF`) memungkinkan ekstraksi data berkecepatan nanodetik dengan overhead CPU kurang dari 1-2%.

---

## SEKSI 05 — APA ITU (WHAT)

Observabilitas Linux adalah kemampuan untuk menyimpulkan kondisi internal sistem operasi dan beban kerja yang berjalan di atasnya melalui data eksternal: **Logs**, **Traces**, dan **Metrics**.

*   **Kernel Ring Buffer & `printk`:** Struktur data siklik di dalam kernel memory yang menampung pesan kernel internal. Data ini dibaca melalui interface `/dev/kmsg` atau syscall `syslog(2)` (diakses via utility `dmesg`).
*   **Structured Logging (`systemd-journald`):** Kolektor log native yang menerima pesan dari socket `/dev/log`, `/dev/kmsg`, standard output/error service systemd, dan native API `sd_journal_send()`. Log disimpan dalam format binary biner terindeks (mengandung metadata PID, UID, cgroup, SELinux context).
*   **Log Forwarder (`rsyslog`):** Daemon pemrosesan log modular berkinerja tinggi yang mengimplementasikan protokol syslog (RFC 3164, RFC 5424) dan Reliable Event Logging Protocol (RELP). Menggunakan bahasa konfigurasi *RainerScript* untuk routing, parsing, manipulasi, dan enkripsi payload log.
*   **Kernel Tracing Infrastructure:**
    *   **Tracepoints:** Penanda statis yang disematkan langsung oleh kernel developer dalam source code kernel Linux. Stabil antar-versi.
    *   **Kprobes/Kretprobes:** Mekanisme penusukan dinamis yang dapat menyisipkan breakpoint instruksi pada hampir semua alamat memori kernel guna membaca argument fungsi dan return value.
    *   **Uprobes:** Kprobes untuk ruang pengguna (userspace), memungkinkan instrumentasi dinamis terhadap binary elf dan library (`glibc`).
    *   **eBPF (Extended Berkeley Packet Filter):** Mesin virtual register-based di dalam kernel yang memungkinkan eksekusi program sandboxed secara aman ketika suatu event (tracepoint/kprobe/network packet) terpicu.

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

### 1. Siklus Hidup Event Logging Linux

```
[ Application Process ]
       | (calls syslog(3))
       v
  [ AF_UNIX Domain Socket: /dev/log -> /run/systemd/journal/dev-log ]
       |
       v
[ systemd-journald ]
   |-- Membaca Metadata Proses (/proc/$PID/cgroup, status, dll.)
   |-- Tulis ke Binary Journal Storage (/run/log/journal/ atau /var/log/journal/)
   |-- Meneruskan stream log via socket IPC (/run/systemd/journal/syslog)
       |
       v
[ rsyslogd ]
   |-- Module imuxsock / imjournal membaca payload
   |-- Parsing Ruleset (Rainerscript)
   |-- Enqueue ke In-Memory Queue (Disk-Assisted)
   |-- Thread Worker melakukan Serialization (JSON/RFC5424)
   v
[ Network Egress: TLS / RELP Handshake ] ---> [ Centralized Collector ]
```

1.  Aplikasi memanggil fungsi C `syslog(priority, format, ...)`. Glibc mengarahkan data ini ke socket file `/dev/log` (yang merupakan symbolic link ke `/run/systemd/journal/dev-log`).
2.  `systemd-journald` membaca buffer dari socket tersebut. Sebelum menulis data, journald mengambil metadata autentik dari kernel via credential passing (`SO_PASSCRED`), seperti: `_PID`, `_UID`, `_GID`, `_COMM`, serta informasi slice systemd.
3.  Pesan ditulis ke file biner jurnal `.journal`. File ini diamankan dengan hashing cryptographic jika fitur *Forward Secure Sealing (FSS)* diaktifkan.
4.  Jika `ForwardToSyslog=yes` aktif pada `/etc/systemd/journald.conf`, journald menyalurkan event ke socket `/run/systemd/journal/syslog`.
5.  `rsyslogd` menangkap pesan via module `imjournal` atau `imuxsock`. Melalui pipeline RainerScript, pesan diuraikan, dialirkan ke queue berkonsep buffer-protection, lalu dikirim via TCP terenkripsi TLS atau protokol RELP ke server log terpusat.

### 2. Mekanisme Dynamic Tracing via Kernel Tracefs

Tracing tidak melakukan interupsi berbasis context-switch manual. Subsistem `ftrace` memanfaatkan fitur compiler `-pg` (profiling) dan mekanisme binary patching `mcount`/`fentry`:

1.  Saat kernel dikompilasi dengan `CONFIG_FUNCTION_TRACER`, compiler GCC menambahkan instruksi dummy (misalnya `nop` 5-byte pada arsitektur x86_64) di setiap prolog fungsi kernel.
2.  Ketika tracer diaktifkan melalui `/sys/kernel/tracing/current_tracer`, kernel memodifikasi instruksi `nop` tersebut secara runtime (hot-patching) menjadi instruksi `call trace_caller`.
3.  Saat fungsi dieksekusi, execution flow dialihkan ke `trace_caller`, yang bertugas mengumpulkan metadata pemanggilan (instruksi pointer, timestamp TSC, ID CPU, pointer stack) dan menyimpannya ke per-CPU lockless circular ring buffer.
4.  Userspace process membaca buffer tersebut secara non-blocking melalui interface virtual file `/sys/kernel/tracing/trace_pipe`.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### Arsitektur Aliran I/O Logging dan Kernel Tracing

```
================================ KERNEL SPACE ================================
  +------------------+     +------------------+     +-------------------+
  |  printk() calls  |     | Kernel Functions |     | Dynamic Kprobes   |
  +--------+---------+     +--------+---------+     +---------+---------+
           |                        |                         |
           v                        v (fentry call)           v
  [ /dev/kmsg Ring ]       [ ftrace Engine ]        [ eBPF Virtual Machine ]
  (printk buffer)                   \                         /
           |                         v                       v
           |                 +---------------------------------------+
           |                 | Per-CPU Lockless Ring Buffers         |
           |                 | (/sys/kernel/tracing/trace_pipe)      |
           |                 +-------------------+-------------------+
           |                                     |
===========|=====================================|=============================
           | System Call Reads                   | mmap() / read()
===========|=====================================|=============================
           v                                     v
================================ USER SPACE ==================================
  +----------------------+             +------------------------------------+
  | systemd-journald     |             | Tracing Consumer Engine            |
  | (/dev/kmsg, /dev/log)|             | (bpftrace, perf, trace-cmd)        |
  +----------+-----------+             +------------------+-----------------+
             |                                            |
      (Unix Domain Sock)                                  | (Stdout/Analysis)
             v                                            v
  +----------------------+                      Terminal / Alerting Dashboard
  | rsyslog daemon       |
  |  +----------------+  |
  |  | In-Memory Queue|  |
  |  +-------+--------+  |
  |          |           |
  |  +-------v--------+  |
  |  | omfwd / omrelp |  |
  +----------+-----------+
             |
             | TCP/IP (mTLS over RELP, Port 20514)
             v
  +-------------------------------------------------------------------------+
  | Centralized SIEM / Log Collector (e.g., Elasticsearch, Vector, Graylog) |
  +-------------------------------------------------------------------------+
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

### Observabilitas Cepat Kernel Ring Buffer dan ftrace

Mengaktifkan function tracing untuk memantau pemanggilan fungsi kernel `do_sys_openat2` (fungsi backend pemanggilan sistem pembukaan file) secara manual tanpa tool eksternal.

```bash
# 1. Masuk sebagai root dan berpindah ke direktori tracefs
sudo su -
cd /sys/kernel/tracing

# 2. Reset tracer dan bersihkan buffer sebelumnya
echo 0 > tracing_on
echo nop > current_tracer
echo > trace

# 3. Tentukan filter fungsi target
echo do_sys_openat2 > set_ftrace_filter

# 4. Aktifkan tracer tipe function
echo function > current_tracer

# 5. Aktifkan penulisan trace buffer
echo 1 > tracing_on

# 6. Baca live output tracing (jalankan perintah lain di terminal terpisah, misal: ls /root)
head -n 20 trace_pipe

# 7. Nonaktifkan kembali tracing segera untuk menghemat siklus CPU
echo 0 > tracing_on
echo nop > current_tracer
echo > set_ftrace_filter
```

**Output Tipikal:**
```text
# TASK-PID     CPU#  |||||  TIMESTAMP  FUNCTION
#    | |         |   |||||      |         |
    bash-4210   [002] ..... 31405.129481: do_sys_openat2 <-do_sys_open
    bash-4210   [002] ..... 31405.129505: do_sys_openat2 <-do_sys_open
      ls-4822   [001] ..... 31407.892110: do_sys_openat2 <-do_sys_open
```

*Penjelasan:* Output menampilkan nama task dan Process ID (`ls-4822`), core CPU tempat instruksi dieksekusi (`CPU# 001`), timestamp presisi microsecond, dan fungsi kernel target yang dipanggil beserta *caller function*-nya (`do_sys_open`).

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

### Skenario: Implementasi High-Reliability Log Forwarding (Rsyslog + RELP + TLS) dan Monitoring Latensi Blok I/O Menggunakan bpftrace

#### Bagian 1: Konfigurasi Log Shipper Produksi (`/etc/rsyslog.d/99-secure-forward.conf`)

Tujuan: Mengirimkan seluruh log tingkat `warning` ke atas ke remote centralized collector secara terenkripsi, dengan garansi zero-drop via disk-assisted queue jika jaringan terputus.

```rainerscript
# Muat modul output RELP
module(load="omrelp")

# Template format RFC 5424 presisi tinggi dengan timestamp ISO-8601
template(name="RFC5424Format" type="string"
   string="<%PRI%>1 %TIMESTAMP:::date-rfc3339% %HOSTNAME% %APP-NAME% %PROCID% %MSGID% %STRUCTURED-DATA% %msg%\n"
)

# Definisi In-Memory Disk-Assisted Queue
action(
    type="omrelp"
    target="log-aggregator.internal.net"
    port="20514"
    template="RFC5424Format"
    
    # Pengaturan Enkripsi mTLS
    tls="on"
    tls.cafile="/etc/ssl/certs/internal_ca.crt"
    tls.mycert="/etc/ssl/certs/node_client.crt"
    tls.myprivkey="/etc/ssl/private/node_client.key"
    tls.authmode="fingerprint"
    tls.permittedpeer=["SHA1:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX"]

    # Konfigurasi Queue Resiliensi Tinggi
    queue.type="LinkedList"
    queue.filename="relp_forward_queue"
    queue.spacedrop.threshold="0"          # Jangan drop event penting
    queue.maxdiskspace="5368709120"        # Alokasikan disk buffer maks 5GB
    queue.maxfilesize="268435456"          # Rotasi file antrian disk tiap 256MB
    queue.size="500000"                    # Batas elemen di memori RAM
    queue.highwatermark="400000"           # Mulai offload ke disk saat RAM 80% penuh
    queue.lowwatermark="100000"            # Kembali ke in-memory saat isi di bawah 20%
    queue.saveonshutdown="on"              # Flush semua antrian memori ke disk jika node reboot
    
    # Retry Policy
    action.resumeRetryCount="-1"           # Coba selamanya, jangan drop
    action.resumeInterval="5"              # Interval pengecekan koneksi 5 detik
)
```

Verifikasi konfigurasi dan reload daemon:
```bash
sudo rsyslogd -N1
sudo systemctl restart rsyslog
```

#### Bagian 2: Diagnostik Masalah Latensi Sistem dengan bpftrace

Saat aplikasi mengalami lagging secara intermiten, kita perlu memeriksa apakah kernel scheduler atau disk I/O layer yang menjadi akar masalah. Skrip berikut menelusuri latensi operasi block driver secara real-time.

Buat file executable `biolatency.bt`:

```c
#!/usr/bin/env bpftrace

BEGIN
{
    printf("Tracing block device I/O latency... Tekan Ctrl-C untuk berhenti.\n");
}

/* Tangkap inisiasi I/O request ke layer block device */
tracepoint:block:block_bio_queue
{
    @start[args.dev, args.sector] = nsecs;
}

/* Tangkap waktu ketika request I/O selesai diproses driver */
tracepoint:block:block_bio_complete
/@start[args.dev, args.sector]/
{
    $duration_us = (nsecs - @start[args.dev, args.sector]) / 1000;
    @usecs = hist($duration_us);
    
    /* Tandai jika ada anomali I/O di atas 50 milidetik (50000 us) */
    if ($duration_us > 50000) {
        printf("WARNING: Disk latency spike! Dev: %d, Comm: %s, Latency: %d ms\n", 
               args.dev, curtask->comm, $duration_us / 1000);
    }

    delete(@start[args.dev, args.sector]);
}

END
{
    clear(@start);
    printf("\nDistribusi Latensi I/O Block Device (microsecond):\n");
}
```

Jalankan skrip bpftrace:
```bash
sudo chmod +x biolatency.bt
sudo ./biolatency.bt
```

**Output Distribusi (Histogram):**
```text
@usecs: 
[16, 32)            1208 |@@@@@@@@@@@@@@@@@@@@                               |
[32, 64)            2450 |@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@            |
[64, 128)            890 |@@@@@@@@@@@@@@                                      |
[128, 256)           102 |@                                                   |
[256, 512)            23 |                                                    |
[512, 1K)              5 |                                                    |
[10K, 20K)             2 |                                                    |
[64K, 128K)            1 |                                                    |
```
*Interpretasi:* Terlihat distribusi dominan di 32-64 mikrodetik (normal SSD performance), namun terdapat 1 outlier di kisaran 64-128 milidetik yang memicu trigger warning dan mengindikasikan bottleneck pada storage layer atau I/O starvation.

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Dimensi | Pendekatan A (Plain Syslog / UDP) | Pendekatan B (Structured Journald + RELP mTLS) | Pendekatan C (Full eBPF / Trace Logging) |
| :--- | :--- | :--- | :--- |
| **Keandalan Pengiriman** | **Rendah**: Zero ACK, paket hilang tanpa peringatan saat jaringan saturated. | **Sangat Tinggi**: RELP mengelola ACK di level aplikasi; *Disk-Assisted queue*. | **Konteks Spesifik**: eBPF menggunakan per-CPU ring buffer. Event di-drop jika buffer userspace lambat membaca. |
| **Konsumsi CPU/Memory** | **Minimal**: Beban serialization sangat rendah. | **Moderat**: Enkripsi TLS dan operasi disk buffer memakan 3-7% CPU pada burst. | **Bervariasi**: Tergantung frekuensi event. Menelusuri instruksi dengan hit-rate tinggi (`kprobe:vfs_read`) memicu overhead CPU signifikan. |
| **Struktur & Richness Data** | **Rendah**: Teks mentah (unstructured), parsing via Regex kompleks di sisi SIEM. | **Tinggi**: Metadata POSIX lengkap terikat natively (PID, cgroup, UUID). | **Ultra Tinggi**: Akses penuh ke parameter register kernel, memory address, dan stack traces. |
| **Kompleksitas Operasional**| **Sangat Rendah**: Konfigurasi minimal `*.* @IP:514`. | **Tinggi**: Diperlukan manajemen rotasi sertifikat TLS dan monitoring kapasitas disk buffer. | **Tinggi**: Butuh kernel Linux modern (`>= 5.4`), BTF (*BPF Type Format*), dan kernel-headers terpasang. |

---

## SEKSI 11 — BEST PRACTICES

1.  **Isolasi Storage untuk Logging:** Jangan satukan direktori `/var/log` atau `/var/log/journal` pada partisi root filesystem (`/`). Jika volume log membesar secara mendadak akibat *crash loop*, root disk tidak akan mengalami kehabisan kapasitas (*disk exhaustion*) yang dapat memicu *kernel panic*.
2.  **Konfigurasi Rate Limiting Ketat pada Journald:** Definisikan pembatasan volume log pada `/etc/systemd/journald.conf`:
    ```ini
    RateLimitIntervalSec=30s
    RateLimitBurst=20000
    SystemMaxUse=4G
    RuntimeMaxUse=512M
    ```
3.  **Terapkan RELP Menggantikan Plain TCP:** TCP standar rentan kehilangan frame log terakhir jika koneksi diputus secara paksa oleh firewall/NAT state-timeout di tengah transmisi. Gunakan `omrelp` untuk transaksi paket berbasis confirmation frame.
4.  **Minimalkan Penggunaan Kprobes pada Hot Path:** Hindari menaruh *dynamic kprobes* pada fungsi kernel yang dieksekusi jutaan kali per detik (seperti `native_sched_clock`, `vfs_read`, atau `packet_rcv`). Gunakan *Static Tracepoints* yang dioptimasi via static branch (`nop` replacement).
5.  **Amankan Integritasi Data Log (FSS):** Jalankan sealing pada journald secara berkala:
    ```bash
    journalctl --setup-keys
    ```
    Kunci verifikasi yang dihasilkan secara off-host memungkinkan deteksi jika penyerang berusaha memodifikasi baris log log-file historis setelah insiden intrusi.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

1.  **Membuka Tracing Pipe Tanpa Mematikan Tracer:**
    *   *Gejala:* Utilisasi CPU dari kworker melonjak tinggi, konsumsi daya server naik drastis.
    *   *Penyebab:* Menjalankan trace manual di `/sys/kernel/tracing` tanpa mengeksekusi `echo 0 > tracing_on` setelah selesai analisa. Tracer tetap mengeksekusi hook dan menulis data ke memory buffer secara kontinu.
2.  **In-Memory Queue Rsyslog Tanpa Batas Maksimum:**
    *   *Gejala:* Server kehabisan RAM (`OOM-Killer` aktif) saat agregator log eksternal mengalami *downtime*.
    *   *Penyebab:* Menggunakan konfigurasi queue tipe `LinkedList` pada rsyslog tanpa membatasi atribut `queue.maxdiskspace` atau menetapkan batas disk-assisted buffer. Log menumpuk di heap memory hingga node kolaps.
3.  **Mengandalkan `strace` untuk Debugging Beban Produksi:**
    *   *Gejala:* Latensi transaksi melonjak dari 5ms menjadi 200ms; thread pool aplikasi terkuras habis.
    *   *Penyebab:* `strace` menggunakan interface `ptrace(2)`. Tiap syscall yang terjadi memicu dua kali context switch dan menghentikan eksekusi thread target (*breakpoint trap*). Gunakan `perf trace` atau `bpftrace` yang sepenuhnya berjalan asynchronously di kernel space.
4.  **Terjadinya Deadlock pada Custom Syslog Hooks:**
    *   *Gejala:* Daemon aplikasi hang dan tidak merespons request saat logging system hang.
    *   *Penyebab:* Menulis ke `/dev/log` menggunakan blocking socket mode saat systemd-journald sedang macet (*stalled*). Pastikan aplikasi mengimplementasikan *non-blocking flag* (`O_NONBLOCK` pada socket FD).

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1: Forensik System Crash via Kernel Ring Buffer Persisten
*Instruksi:*
1.  Aktifkan penyimpanan persistent kernel log pada systemd-journald: pastikan folder `/var/log/journal` ada dan dikonfigurasi dengan mode `Storage=persistent` di `/etc/systemd/journald.conf`.
2.  Simulasikan kernel crash buatan pada mesin testing (Virtual Machine) menggunakan kernel `SysRq`:
    ```bash
    echo 1 > /proc/sys/kernel/sysrq
    echo c > /proc/sysrq-trigger
    ```
3.  Setelah mesin di-booting ulang, gunakan `journalctl` untuk mengambil stack trace panic dari boot sebelumnya (`-b -1`) dan analisis register *instruction pointer* (`RIP`) yang memicu crash tersebut.

### Latihan 2: Implementasi Dynamic Probe Monitoring Eksekusi Command
*Instruksi:*
1.  Buat skrip `bpftrace` satu baris (one-liner) untuk mendeteksi siapa saja yang mengeksekusi file executable di seluruh host.
2.  Ekstraksi: PID, UID, nama proses induk (`parent process name`), dan path absolut dari executable yang dipanggil via syscall `execve`.

*Solusi Latihan 2:*
```bash
sudo bpftrace -e 'tracepoint:syscalls:sys_enter_execve { printf("PID: %d | UID: %d | Parent: %s | Cmd: %s\n", pid, uid, curtask->parent->comm, str(args.filename)); }'
```

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

1.  **Apa perbedaan mendasar antara mekanisme pelaporan event melalui `/dev/kmsg` dibandingkan `/dev/log`?**
    *   *A.* `/dev/kmsg` menggunakan transport TCP, sedangkan `/dev/log` UDP.
    *   *B.* `/dev/kmsg` adalah antarmuka pembacaan/penulisan langsung ke Kernel Ring Buffer, sedangkan `/dev/log` adalah Unix Domain Socket untuk pesan userspace.
    *   *C.* `/dev/kmsg` hanya menyimpan pesan panic, sedangkan `/dev/log` menyimpan metric.
    *   *D.* Tidak ada perbedaan; keduanya symlink ke inode yang sama.
    *   *Jawaban yang Benar:* **B**

2.  **Mengapa penggunaan `perf` atau `bpftrace` jauh lebih aman dan memiliki performa lebih tinggi dibandingkan utilitas `strace` untuk tracing syscall di lingkungan produksi?**
    *   *Jawaban:* `strace` mengandalkan system call `ptrace()`, yang memaksa kernel melakukan interupsi breakpoint, dua kali context switch per syscall, dan menghentikan jalannya instruksi program secara sinkron (stop-the-world). Sebaliknya, `perf` dan `bpftrace` mengeksekusi probe hook secara in-kernel di ring buffer memori tanpa menghentikan thread aplikasi pengguna secara terus-menerus.

3.  **Protokol logging manakah yang menjamin bahwa log tidak hilang saat koneksi jaringan terputus tiba-tiba di tengah transmisi data buffer?**
    *   *A.* RFC 3164 (Plain UDP Syslog)
    *   *B.* RFC 5424 over UDP
    *   *C.* RELP (Reliable Event Logging Protocol)
    *   *D.* Syslog over Cleartext TCP
    *   *Jawaban yang Benar:* **C**

4.  **Apa implikasi performa jika direktori `/sys/kernel/tracing/set_ftrace_filter` dibiarkan kosong saat tracer tipe `function` diaktifkan?**
    *   *Jawaban:* Ftrace akan mengaktifkan dynamic binary patching pada seluruh fungsi kernel Linux yang didukung (mencapai puluhan ribu fungsi). Hal ini akan menimbulkan degradasi performa dramatis (overhead CPU masif) di seluruh subsistem operasi host.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

*   **Linux Documentation:**
    *   Kernel Tracing Architecture: `/usr/src/linux/Documentation/trace/ftrace.rst`
    *   Kernel Ring Buffer Interface: `man 2 syslog`, `man 4 kmsg`
*   **System Manuals:**
    *   `man 8 systemd-journald.service`
    *   `man 5 journald.conf`
    *   `man 8 rsyslogd`
    *   `man 5 rsyslog.conf`
*   **Buku & Modul Lanjutan:**
    *   Gregg, Brendan. *Systems Performance: Enterprise and the Cloud, 2nd Edition* (Addison-Wesley, 2020).
    *   Gregg, Brendan. *BPF Performance Tools* (Addison-Wesley Professional, 2019).
*   **Standar Spesifikasi IETF:**
    *   RFC 5424 — *The Syslog Protocol*
    *   The RELP Project Specification (librelp - rsyslog.com)

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1.  Ekosistem logging Linux beroperasi dari dua domain: **Kernel Space** (melalui buffer `printk()` dan `/dev/kmsg`) dan **User Space** (melalui standard library `syslog(3)` yang dialirkan ke socket `/dev/log`).
2.  `systemd-journald` bertindak sebagai initial ingestor yang bertugas memperkaya log dengan metadata konteks lingkungan runtime (systemd unit, PID credentials) ke dalam indexed binary log.
3.  Untuk keandalan enterprise, `rsyslog` mengambil stream dari journald dan memfasilitasi arsitektur perutean lanjutan menggunakan protokol RELP dengan enkripsi TLS dan sistem buffer *Disk-Assisted In-Memory Queue*.
4.  Observabilitas tingkat dalam tidak memerlukan perombakan biner aplikasi. Melalui `tracefs`, kernel menyediakan antarmuka terpadu via `ftrace`, tracepoints, dan uprobes/kprobes.
5.  Teknologi modern memanfaatkan eBPF via antarmuka seperti `bpftrace` untuk mengeksekusi agregasi analitik langsung di dalam kernel space, mengurangi biaya overhead transfer data ke userspace secara signifikan.

---

## SEKSI 17 — GLOSARIUM

*   **Circular Ring Buffer:** Struktur data berbasis array melingkar berukuran tetap di mana elemen tertua akan ditimpa (*overwrite*) secara otomatis jika buffer penuh dan belum dibaca.
*   **eBPF (Extended Berkeley Packet Filter):** Mesin eksekusi bytecode sandboxed dalam kernel Linux yang memungkinkan pemrosesan paket dan penelusuran probe tanpa memodifikasi kernel source atau menyisipkan modul pihak ketiga.
*   **ftrace:** Subsistem internal Linux kernel yang bertugas menelusuri pemanggilan fungsi (*function call graph*) dan mengevaluasi latensi kernel runtime.
*   **Kprobe:** Breakpoint instruksi dinamis kernel yang memungkinkan pencatatan register memori saat fungsi tertentu dieksekusi.
*   **Kretprobe:** Variasi kprobe yang terpasang pada instruksi return suatu fungsi kernel untuk menginspeksi nilai kembalian (*return values*).
*   **RELP (Reliable Event Logging Protocol):** Protokol transport data log berbasis ACK di level aplikasi untuk meniadakan kehilangan pesan (*zero-data-loss*) akibat koneksi tertutup mendadak.
*   **Tracepoint:** Titik hook instrumentasi statis yang dikompilasi secara permanen di dalam source code kernel Linux.
*   **Uprobe:** Instrumentasi dinamis pengguna (*User-space probe*) yang disematkan pada biner executable atau file library `.so`.

---

## SEKSI 18 — CATATAN INSTRUKTUR

*   **Fokus Materi:** Modul ini padat akan konsep kernel-level. Siswa sering kali bingung membedakan antara fungsionalitas `systemd-journald` dan `rsyslog`. Tekankan bahwa keduanya tidak saling meniadakan, melainkan komplementer: Journald adalah *System Collector & Metadata Enricher*, sedangkan Rsyslog adalah *Advanced Enterprise Router & Forwarder*.
*   **Laboratorium Mandiri:** Pastikan seluruh siswa menggunakan instance Virtual Machine (KVM/VirtualBox) atau bare-metal Linux dengan akses kernel utuh (bukan Docker container standar). Docker container berbagi kernel dengan host dan umumnya memiliki pembatasan kapabilitas kernel (`CAP_SYS_ADMIN`), pembatasan akses ke `/sys/kernel/tracing`, serta tidak menjalankan init system `systemd` secara penuh.
*   **Mitigasi Masalah Teknis:** Saat menjalankan latihan bpftrace, pastikan kernel Linux node lab telah terkompilasi dengan opsi `CONFIG_BPF=y`, `CONFIG_BPF_SYSCALL=y`, dan `CONFIG_BPF_EVENTS=y`. Pada distro Debian/Ubuntu, paket `bpftrace` dan `linux-headers-$(uname -r)` wajib terinstal sebelum kelas dimulai.

---

## SEKSI 19 — CHANGELOG & VERSI

*   **Versi 1.0.0 (Maret 2025):**
    *   Rilis awal materi Arsitektur Logging Terpusat, Tracing Kernel, dan Observabilitas.
    *   Standarisasi kode RainerScript ke engine `rsyslog` modern v8+.
    *   Penyertaan implementasi monitoring berbasis `bpftrace` dan mitigasi resiko overhead `ftrace`.

---

## SEKSI 20 — NAVIGASI KURIKULUM

*   **Modul Sebelumnya:** Bab 07 Module 03 — *Network Namespace, Virtual Interfaces, and Firewalling Architecture*
*   **Modul Saat Ini:** Bab 08 Module 01 — *Arsitektur Logging Linux, Kernel Tracing, dan Fondasi Observabilitas Sistem*
*   **Modul Berikutnya:** Bab 08 Module 02 — *Metrics Collection, eBPF Deep-Dive Tracing, dan Performance Profiling*