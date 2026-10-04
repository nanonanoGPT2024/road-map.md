# BAB 08: Quiz, Challenge, & Knowledge Check
**Logging Terpusat, Tracing Kernel, dan Observabilitas (eBPF)**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Arsitektur Jalur Ingesti Log Lokal (`/dev/log` vs `systemd-journald`)
Jelaskan secara mendalam siklus hidup sebuah pesan log yang dipancarkan oleh aplikasi via `syslog(3)` di sistem modern berbasis `systemd`. Bagaimana interaksi antara *UNIX domain socket* (`/dev/log`), proses `systemd-journald`, dan *forwarder downstream* seperti `rsyslog` atau `vector` terjadi? Bahas implikasi performa dari transisi pesan dari *stream/datagram socket* ke *ephemeral memory ring buffer* dan persistensi disk (`/var/log/journal`).

### Soal 1.2: Anatomi Kernel Dynamic Instrumentation vs Static Instrumentation
Bandingkan mekanisme internal antara **Tracepoints** (Static Tracing) dan **Kprobes/Kretprobes** (Dynamic Tracing) pada Linux Kernel:
- Bagaimana kernel menyisipkan instruksi pada saat kompilasi vs modifikasi kode secara runtime via *breakpoint instruction patching* (e.g., `int3` pada x86_64)?
- Mengapa *Tracepoints* dianggap stabil secara API (*stable ABI contract*), sedangkan *Kprobes* rapuh terhadap perubahan rilis minor kernel?
- Apa dampak performa (*overhead*) dari eksekusi instruksi trap/breakpoint pada *instruction pipeline* dan *CPU context switch*?

### Soal 1.3: Model Komputasi dan Jaminan Keamanan Mesin Virtual eBPF
Mesin virtual eBPF dalam kernel mengeksekusi *in-kernel bytecode* yang disediakan oleh user-space.
- Jelaskan peran konkret dari **BPF Verifier** dalam menganalisis *Directed Acyclic Graph* (DAG) dari program sebelum instruksi dimuat: bagaimana verifier membuktikan *termination* (mencegah *infinite loop*), memverifikasi akses batas memori (*out-of-bounds safety*), dan tipe pointer (*register type tracking*)?
- Mengapa JIT (*Just-In-Time Compiler*) pada eBPF krusial untuk performa pemantauan latensi rendah (*sub-microsecond tracing*) dibanding interpretasi instruksi biasa?

### Soal 1.4: Semantik Transportasi Logging Jarak Jauh: TCP vs UDP vs RELP
Dalam mendesain sistem pengiriman log terpusat dari ribuan node Linux ke klaster ingestor (seperti Kafka atau OpenSearch):
- Analisis kelemahan fatal penggunaan syslog berbasis **UDP (RFC 5426)** di jaringan dengan *packet loss* tinggi dan saturasi bandwidth.
- Mengapa **TCP biasa (RFC 5425/6587)** dapat memicu fenomena *cascading failure* (*head-of-line blocking* dan *thread starvation*) pada aplikasi penghasil log ketika server penampung log mengalami degradasi (*unresponsive ingestor*)?
- Bagaimana protokol **RELP (Reliable Event Logging Protocol)** memitigasi risiko kehilangan data (*log duplicity & truncation*) saat koneksi terputus di tengah pengiriman *window ack*?

### Soal 1.5: Push-Based vs Pull-Based Observability Engine dan Beban Kernel Socket
Bandingkan model arsitektur pengumpulan metrik/observabilitas *Push-based* (e.g., daemon mengirim metrik ke *time-series gateway*) versus *Pull-based* (e.g., Prometheus melakukan *HTTP scraping* berkala pada endpoint `/metrics`):
- Bagaimana interaksi *polling* berkala berbasis pull memengaruhi *TCP socket state allocation* (TIME_WAIT, ephemeral port exhaustion) pada beban ratusan *scrape target* frekuensi tinggi (e.g., interval 1 detik)?
- Kapan model push berbasis UDP/eBPF ring buffer lebih unggul dalam meminimalisir interferensi observabilitas terhadap alokasi *kernel memory* dan *scheduler workload*?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Diagnostik Degradasi Akibat Journald Log Dropping & Rate Limiting
Sebuah instance basis data berkinerja tinggi mengalami insiden: query error kritis tidak tercatat di `/var/log/messages` maupun `journalctl`. Anda menemukan baris log:
`systemd-journald[450]: Suppressed 28419 messages from /system.slice/payment-api.service`
- Parameter internal apa pada `/etc/systemd/journald.conf` yang memicu suppression ini (`RateLimitIntervalSec`, `RateLimitBurst`)?
- Bagaimana mekanisme backpressure `journald` beroperasi ketika buffer `/run/log/journal` (volatile) atau `/var/log/journal` (persistent) kehabisan IOPS disk?
- Apa konfigurasi presisi untuk mematikan *rate-limiting* secara selektif per-*systemd unit file* tanpa membahayakan *systemd-journald* dari risiko DoS lokal?

### Soal 2.2: Memory Model eBPF: `BPF_MAP_TYPE_PERF_EVENT_ARRAY` vs `BPF_MAP_TYPE_RINGBUF`
Pada kernel versi lama, komunikasi data antara eBPF program ke user-space bergantung pada `PERF_EVENT_ARRAY`. Kernel modern (>= 5.8) memperkenalkan `BPF_MAP_TYPE_RINGBUF`.
- Jelaskan arsitektur memori internal yang membedakan keduanya (khususnya alokasi *per-CPU buffer* vs *single multi-producer single-consumer ring-buffer*).
- Mengapa `PERF_EVENT_ARRAY` boros memori pada server dengan ratusan core (CPU-dense architecture) dan sering menghasilkan data event yang tidak berurutan (*out-of-order events*)?
- Bagaimana `BPF_MAP_TYPE_RINGBUF` mengeliminasi *overhead* alokasi memori sekaligus menjamin urutan data (*in-order preservation*) dan mendukung *zero-copy memory reservation* (`bpf_ringbuf_reserve`)?

### Soal 2.3: Ftrace dan Debugging Latensi Penjadwalan Kernel Tanpa Overhead eBPF
Anda mendeteksi lonjakan latensi (*latency spike*) 200 milidetik pada thread aplikasi realtime, namun eBPF tooling tidak diizinkan di kernel produksi karena kebijakan audit.
- Bagaimana Anda mengonfigurasi `ftrace` secara manual melalui antarmuka virtual filesystem `/sys/kernel/tracing/` untuk melacak latensi penjadwalan menggunakan tracer `preemptirqsoff` atau `wakeup`?
- Tuliskan langkah-langkah eksak (via CLI `sysfs`) untuk:
  1. Membatasi tracing hanya pada PID tertentu.
  2. Mengaktifkan filter fungsi kernel (e.g., fungsi-fungsi `sched_*`).
  3. Mengatur *latency threshold* agar buffer ftrace hanya mencatat event yang melampaui 50 milidetik.
- Bagaimana cara mengekstrak output trace tanpa memicu overhead I/O tambahan pada konsol tty?

### Soal 2.4: Evolusi Probe Return: Kretprobes vs Fexit (BPF Trampolines)
Ketika melacak waktu eksekusi fungsi kernel (tracing return value dan durasi):
- Bagaimana implementasi tradisional **kretprobe** memodifikasi return address di stack execution thread, dan mengapa hal ini rentan memicu degradasi performa (*stack frame rewriting*) dan rentan kehilangan data saat penanganan rekursif (*kretprobe instance exhaustion*)?
- Bagaimana teknologi modern **BPF Trampoline** (`fexit` / `fentry` yang membutuhkan `CONFIG_BPF_JIT` dan BTF / *BPF Type Format*) mengeliminasi overhead instruksi `breakpoint` serta menembus batas keterbatasan kretprobes secara *zero-overhead direct jump*?

### Soal 2.5: Verifier Error Resolution: Analisis Pointer Register Arithmetic & Bounds Violation
Sebuah program eBPF yang menginspeksi payload paket jaringan gagal di-load ke kernel dengan error berikut:
```text
R1 invalid mem access 'inv'
dereference of modified ctx ptr R1 off=16 disallowed
bpf verifier: math between ctx and foo pointer is forbidden
processed 42 insns (limit 1000000) max_states_per_insn 0
load program: Permission denied
```
- Apa akar penyebab logis dari pesan kesalahan *verifier* tersebut ditinjau dari cara kernel melacak register context (`struct __sk_buff` atau `struct xdp_md`)?
- Mengapa compiler Clang/LLVM terkadang memvalidasi pointer arithmetic yang kemudian ditolak mentah-mentah oleh kernel BPF verifier?
- Tuliskan pola kode C (BPF) standar yang menggunakan *boundary check guard* eksplisit (`data + sizeof(hdr) > data_end`) untuk membuktikan kepada *verifier* bahwa pembacaan memori berada dalam batas aman.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden "Log Storm" Berujung Stalling Proses Produksi (TCP Buffer Backpressure Collapse)
Sebuah klaster microservice memproses lonjakan traffic 10x lipat saat flash sale. Daemon logging terpusat (`rsyslog`) di setiap host dikonfigurasi untuk mengirim log aplikasi secara sinkronus via TCP ke log aggregator terpusat.
- **Kondisi:** Log aggregator terpusat mengalami degradasi I/O disk, menyebabkan TCP receive window-nya menyusut ke 0 (*TCP ZeroWindow*).
- **Gejala:** Aplikasi di node produksi berhenti merespons HTTP request baru (*hang*). Load average CPU melonjak drastis, tetapi pemanfaatan CPU (*user space*) hampir 0%. Mayoritas thread aplikasi terjebak dalam status `D` (Uninterruptible Sleep).
- **Pertanyaan Diagnostik:**
  1. Telusuri rantai kausalitas: bagaimana kemacetan TCP pada rsyslog merambat (*cascading backpressure*) hingga menyebabkan thread runtime aplikasi (e.g., Java/Go/Node.js) terkunci pada *system call* `write(2)` atau `sendmsg(2)` ke `/dev/log`?
  2. Perintah diagnostik Linux apa (`ss`, `lsof`, `strace`, `vmstat`) yang Anda jalankan untuk membuktikan bahwa buffer `/dev/log` (*UNIX domain socket*) penuh dan aplikasi mengalami blocking?
  3. Konfigurasi mitigasi arsitektur apa yang harus dipasang pada logging forwarder (`rsyslog`/`vector`) untuk mengisolasi kegagalan transmisi jaringan agar tidak merusak ketersediaan proses aplikasi (*disk-assisted queues*, non-blocking drops, rate-limiting buffer)?

### Skenario B: Diagnostik Silent Packet Drops di Jalur Kernel Menggunakan eBPF Tracepoint
Kluster Kubernetes Anda mengalami masalah performa: koneksi TCP antar-pod sering mengalami *retransmission timeout* (RTO) 1 detik secara acak. Metrik infrastruktur jaringan standar (`ifconfig`, `ip -s link`) menunjukkan nilai `RX/TX dropped = 0` dan `RX/TX errors = 0`. Firewall (`iptables`/`nftables`) tampaknya bersih dari rule drop yang eksplisit.
- **Kondisi:** Paket dijatuhkan secara diam-diam (*silent drop*) di dalam lapisan internal Linux Network Stack (antara layer IP routing, Netfilter, atau socket buffer allocation).
- **Gejala:** Ping stabil tanpa packet drop, namun payload TCP berukuran besar di atas MTU terkadang lenyap di kernel host pengirim atau penerima.
- **Pertanyaan Diagnostik:**
  1. Bagaimana Anda menggunakan kernel static tracepoint `skb:kfree_skb` untuk melacak lokasi pasti kode kernel tempat `sk_buff` dibebaskan tanpa dikirim ke socket tujuan?
  2. Tuliskan satu perintah instan berbasis `bpftrace` yang mengekstrak alamat instruksi kernel penjatuh paket (`__builtin_return_address(0)` atau argumen kernel drop reason) dan mengelompokkan drop rate berdasarkan fungsi kernel pemanggil!
  3. Jika kernel Anda sudah mendukung kernel drop reason (Linux >= 5.17), bagaimana Anda mengidentifikasi apakah drop tersebut dipicu oleh `SKB_DROP_REASON_NETFILTER_DROP`, `SKB_DROP_REASON_TCP_CSUM`, atau `SKB_DROP_REASON_PKT_TOO_BIG`?

### Skenario C: Dilema Arsitektur Observabilitas: Full-Trace Auditd vs eBPF CO-RE Engine
Perusahaan fintech Anda harus mematuhi standar regulasi keamanan (PCI-DSS & SOC2) yang mewajibkan audit atas eksekusi setiap proses binari (`execve`), pembukaan file sensitif di `/etc/` (`openat`), dan pembukaan socket koneksi outbound (`connect`).
- **Kondisi Saat Ini:** Sistem menggunakan daemon `auditd` tradisional dengan puluhan audit rules di `/etc/audit/rules.d/`.
- **Dampak:** Di server dengan beban transaksi 50.000 RPS, `auditd` menyebabkan *CPU stealing* hingga 35%, serta memicu system call latency p99 membengkak sebesar 18% akibat overhead alokasi `audit_buffer` dan *context switching* ke user-space daemon `auditd`.
- **Pertanyaan Arsitektural:**
  1. Analisis mengapa arsitektur `auditd` (berbasis `NETLINK_AUDIT` socket queue dan sinkronisasi spinlock di kernel `audit_log_start`) menyebabkan penalti performa masif pada I/O-intensive workloads.
  2. Rancang arsitektur pengganti modern berbasis eBPF menggunakan pendekatan **CO-RE (Compile Once – Run Everywhere)** dengan BTF. Hook kernel mana yang lebih efisien digunakan (`LSM BPF hooks` vs `raw_tracepoints:sys_enter_execve`)?
  3. Apa konsekuensi trade-off dari migrasi ke eBPF jika kernel crash terjadi atau jika terjadi kehilangan event (*ring buffer buffer overrun*)? Bagaimana Anda membuktikan kepada auditor bahwa integritas data log tracing eBPF setara atau melampaui jaminan keamanan `auditd`?

---

## 4. Chapter Challenge

### Tantangan Praktis: Rekayasa Engine eBPF untuk Mendeteksi Latensi Disk I/O & Block Layer Bottleneck

#### Problem Statement
Sebuah sistem penyimpanan basis data NVMe berkinerja tinggi sering mengalami fluktuasi latensi transaksi (latensi p999 menembus 500ms secara sporadis). Metrik standar dari `/proc/diskstats` dan utilitas `iostat` hanya memberikan rata-rata agregat per detik (*moving averages*), menyembunyikan (*masking*) fenomena *I/O latency microbursts*.

Anda ditugaskan merancang pipeline observabilitas berbasis **eBPF** tingkat rendah yang mampu melacak setiap request I/O pada subsistem Block Layer Linux, menghitung distribusi latensi eksekusi storage hardware secara *in-kernel*, serta meneruskan data pelanggaran SLA (> 20ms) sebagai log JSON terstruktur langsung ke pipeline logging tanpa membebani performa CPU produksi.

#### Requirements
1. **Instrumentasi Kernel:**
   - Gunakan `bpftrace` ATAU modul eBPF berbasis C (`libbpf` dengan CO-RE).
   - Hook harus disematkan pada titik siklus hidup Block I/O:
     - Entry: `block:block_rq_issue` (saat request diserahkan ke device driver NVMe).
     - Exit: `block:block_rq_complete` (saat hardware interrupt menandakan I/O selesai).
2. **Kalkulasi Metrik & Korelasi:**
   - Wajib melacak durasi waktu setiap operasi I/O menggunakan `bpf_ktime_get_ns()`.
   - Lakukan korelasi antara request issue dan completion berdasarkan nomor sektor awal (`sector`) atau pointer `struct request *`.
   - Rekam metadata kontekstual: PID proses pemanggil, nama proses (`comm`), ukuran payload I/O (jumlah bytes/sektor), tipe operasi (READ/WRITE), dan durasi eksekusi dalam mikrodetik ($\mu s$).
3. **Penyaringan & Distribusi Latensi:**
   - Buat agregasi histogram linier/logaritmik di dalam kernel space untuk memantau spektrum distribusi latensi I/O secara global tanpa mengirim seluruh data ke user space.
   - Implementasikan *threshold filter*: Hanya event individual dengan durasi $> 20.000\ \mu s$ (20 ms) yang dialirkan ke user-space buffer via eBPF Ring Buffer (`BPF_MAP_TYPE_RINGBUF`).
4. **Integrasi Pipeline Logging:**
   - User-space consumer harus memformat event yang melanggar threshold tersebut menjadi dokumen JSON terstruktur satu baris (*NDJSON*).
   - JSON wajib diinjeksikan secara *non-blocking* ke lokal `systemd-journald` menggunakan *systemd native journal protocol* (`sd_journal_send` atau via socket direct `/run/systemd/journal/socket`) dengan tag identifier `NVME_SLOW_IO`.

#### Constraints
- Program eBPF tidak boleh menggunakan probe dynamic yang berat (`kprobe`/`kretprobe`); wajib menggunakan static **tracepoints** atau **fentry/fexit (BTF)**.
- Overhead konsumsi CPU oleh eBPF tracer tidak boleh melampaui **1.5%** dari 1 core CPU pada beban 80.000 IOPS.
- Wajib menangani kondisi *unpaired events* (request yang di-issue tetapi tidak pernah selesai atau di-*merge*) agar eBPF hash map tidak mengalami kebocoran memori (*memory leak / exhaustion*).

#### Expected Output
1. **Source Code eBPF:** Skrip `bpftrace` mandiri (produksi) ATAU kode C `libbpf` lengkap dengan BPF map definition dan event processing logic.
2. **Representasi Histogram Kernel:** Output ringkasan distribusi latensi I/O yang dihasilkan langsung dari memori kernel:
   ```text
   @io_latency_us: 
   [0, 16)             125841 |@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@|
   [16, 64)             45102 |@@@@@@@@@@@@@@                          |
   [64, 256)             3219 |@                                       |
   [256, 1K)              112 |                                        |
   [1K, 4K)                18 |                                        |
   [4K, 16K)                3 |                                        |
   [16K, 64K)               2 |                                        |
   ```
3. **Payload Log Insiden (JSON Terstruktur):** Bukti rekaman log di journald yang diekstrak menggunakan `journalctl -t NVME_SLOW_IO -o json-pretty`:
   ```json
   {
     "PRIORITY": "3",
     "IDENTIFIER": "NVME_SLOW_IO",
     "MESSAGE": "Block IO latency violation detected on nvme0n1",
     "PID": 18420,
     "COMM": "mysqld",
     "SECTOR": 140928304,
     "BYTES": 65536,
     "OP": "WRITE",
     "LATENCY_US": 23410,
     "KERNEL_TIMESTAMP_NS": 184029412984021
   }
   ```

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Arsitektur aliran data logging Linux: Perbedaan transmisi file log mentah, stream socket `/dev/log`, format binary `systemd-journald`, hingga parser log user-space.
- [ ] Arsitektur internal Mesin Virtual eBPF: Peran register RISC eBPF, BPF Verifier constraints, JIT compilation, dan interaksi user-kernel melalui BPF Maps.
- [ ] Klasifikasi instrumentasi tracing: Kelebihan, kelemahan, dan batas performa antara *Kprobes*, *Uprobes*, *Tracepoints*, *Ftrace*, dan *USDT (User Statically-Defined Tracing)*.
- [ ] Arsitektur BPF Ring Buffer (`BPF_MAP_TYPE_RINGBUF`): Mekanisme *epoll-compatible notification*, *memory ordering*, jaminan sinkronisasi multi-core lockless, dan mitigasi overhead per-CPU buffer.
- [ ] Konsep BTF (*BPF Type Format*) dan CO-RE (*Compile Once – Run Everywhere*): Bagaimana *field offset relocation* memungkinkan binari eBPF berjalan lintas versi kernel tanpa kompilasi lokal via `clang/llvm`.
- [ ] Dampak arsitektural Backpressure: Mengapa logging terpusat yang synchronous dan socket buffer blocking mampu melumpuhkan pipeline aplikasi produksi (TCP ZeroWindow cascading failure).

### Saya tidak perlu menghafal:
- [ ] Angka pasti nilai opcode instruksi raw eBPF assembly (e.g., `0xb7`, `0x85`)—cukup pahami cara membaca output disassembler `llvm-objdump -S` atau `bpftool prog dump xlated`.
- [ ] Seluruh signature argumen fungsi ribuan tracepoint yang ada di `/sys/kernel/tracing/available_events`—cukup kuasai cara membedah definisinya via `/sys/kernel/tracing/events/<subsystem>/<event>/format`.
- [ ] Konfigurasi sintaks mendetail dari setiap varian format vendor logging eksternal (fluentd/logstash/fluent-bit regex filters)—cukup pahami batas performa transfer data kernel-to-user dan standar serialisasi (RFC 5424, NDJSON).

### Saya harus bisa melakukan:
- [ ] Menulis dan mengeksekusi skrip *ad-hoc dynamic tracing* secara tepat menggunakan `bpftrace` untuk melacak latensi *off-CPU*, latensi *block I/O*, dan panggilan *slow system calls* pada live system.
- [ ] Mendiagnosis dan memperbaiki penolakan *verifier eBPF* pada saat memprogram tracing probe (membaca log *verifier dump*, memperbaiki *unbounded loops*, dan memperketat *null pointer checks*).
- [ ] Mengatur tuning level produksi pada `/etc/systemd/journald.conf` untuk mencegah *message loss* pada beban *log bursts* tinggi seraya mengamankan persistensi storage disk.
- [ ] Menemukan titik lokasi *silent packet drop* di stack networking kernel menggunakan tracepoint `kfree_skb` dan utilitas diagnostik kernel modern (`perf`, `bpftrace`).
- [ ] Menggunakan utilitas `bpftool` untuk menginspeksi, memverifikasi, me-load, dan melakukan dump konten memori BPF maps serta me-manage program eBPF yang aktif di subsistem Linux.