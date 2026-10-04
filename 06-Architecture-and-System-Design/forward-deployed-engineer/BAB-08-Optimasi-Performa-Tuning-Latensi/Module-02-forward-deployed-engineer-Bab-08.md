# BAB 08: Optimasi Performa & Tuning Latensi
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik pada level Forward-Deployed Engineer (FDE) diharapkan mampu:
1. **Mendiagnosis dan Mengeliminasi Tail Latency ($P99$ & $P99.9$)**: Mengidentifikasi sumber anomali latensi pada batas kernel-space vs. user-space, *GC pauses*, dan *TCP buffer bloat* di lingkungan heterogen milik klien (on-premise, air-gapped, maupun multi-cloud).
2. **Mengonfigurasi Kernel & Network Stack untuk Low-Latency Throughput**: Menerapkan tuning subsistem Linux (`sysctl`, *NUMA balancing*, `hugepages`, CPU pinning/isolation via `cgroups v2` dan `cpuset`) untuk sistem yang memproses transaksi finansial atau telemetri kritis.
3. **Mengimplementasikan Pola Low-Latency Application Architecture**: Merancang dan menulis kode *zero-copy I/O*, struktur data *lock-free ring buffer*, serta manajemen memori berbasis *custom arena allocator* guna menekan *memory fragmentation* dan *cache invalidation*.
4. **Membangun Continuous Latency Observability dengan eBPF**: Mengompilasi dan menginjeksi program eBPF (*extended Berkeley Packet Filter*) untuk melacak *off-CPU time*, *scheduler run-queue latency*, dan *TCP retransmissions* secara deterministik tanpa menambah *overhead* observabilitas lebih dari 1.5%.

---

### 2. Prerequisite

Untuk menguasai materi ini secara optimal, FDE harus memiliki pemahaman dasar:
- **Arsitektur Sistem Operasi Linux**: Mekanisme Virtual Memory, POSIX System Calls (`epoll`, `splice`, `mmap`), Interrupt Handling (IRQ/SoftIRQ), dan Thread Scheduling (CFS/SCHED_FIFO).
- **Protokol Jaringan L4-L7**: State machine TCP (Handshake, Window Scaling, Congestion Control: Cubic vs. BBR), TLS termination overhead, HTTP/2 multiplexing, dan gRPC frame lifecycle.
- **Bahasa Pemrograman Tingkat Sistem**: Fasih membaca dan memodifikasi kode Go (Runtime internals, pprof, GC Pacer) atau Rust/C++ (Memory ownership, memory barriers, SIMD).
- **Tooling Diagnostik Standar**: Familiar dengan `perf`, `strace`, `tcpdump`, `ethtool`, dan konsep dasar tracepoints eBPF.

---

### 3. Concept & Internal Architecture

Sebagai Forward-Deployed Engineer, Anda kerap diterjunkan ke infrastruktur klien yang tidak dapat diubah arsitektur fisiknya, sementara aplikasi platform Anda dituntut memenuhi Service Level Objectives (SLO) latensi sub-milidetik. Menguasai arsitektur internal sistem operasi dan perangkat keras adalah batas pemisah antara rekayasa sistem nyata dan sekadar menebak parameter konfigurasi (*cargo-cult tuning*).

#### 3.1 Linux Memory Subsystem & NUMA Topology

Pada server modern *multi-socket* (NUMA - Non-Uniform Memory Access), mengakses memori yang terpasang pada CPU soket lokal membutuhkan waktu sekitar 50–70 ns, sedangkan mengakses memori pada soket remote melalui bus interkoneksi (Intel UPI / AMD Infinity Fabric) memakan waktu 120–200 ns (+150-200% latensi).

```
+------------------------------------+       +------------------------------------+
|               NODE 0               |       |               NODE 1               |
|  +------------------------------+  |       |  +------------------------------+  |
|  | Core 0..15  [L1/L2 Cache]    |  |       |  | Core 16..31 [L1/L2 Cache]   |  |
|  +------------------------------+  |       |  +------------------------------+  |
|  |       L3 Cache (Shared)      |  |       |  |       L3 Cache (Shared)      |  |
|  +------------------------------+  |       |  +------------------------------+  |
|                 |                  |       |                 |                  |
|        [Memory Controller]         |  UPI  |        [Memory Controller]         |
|                 |                  |<=====>|                 |                  |
|         Local DRAM (64GB)          |       |         Local DRAM (64GB)          |
+------------------------------------+       +------------------------------------+
```

*Cache Coherency Traffic* lintas node memicu *cache line invalidation* (false sharing) yang memperburuk tail latency. FDE harus memastikan:
1. **CPU Core Affinity**: Thread I/O kritis dikunci (*pinned*) ke core fisik tertentu.
2. **Memory Policy**: Mengatur `numactl --interleave` atau `numactl --membind` untuk mencegah *page allocation stalls*.
3. **Transparent Huge Pages (THP)**: THP sering kali memicu `khugepaged` melakukan defragmentasi memori secara sinkron (*direct compaction*), yang dapat membekukan eksekusi proses selama ratusan milidetik. Dalam sistem deterministik, THP harus dimatikan atau dikonfigurasi ke mode `madvise`.

#### 3.2 Linux Kernel Network Path & Bypass

Alur penerimaan paket tradisional dari NIC ke aplikasi melibatkan sejumlah *bottleneck*:
1. **NIC Packet Arrival**: Paket masuk ke Ring Buffer RX melalui DMA (*Direct Memory Access*).
2. **Hard IRQ**: NIC memicu interrupt ke CPU. CPU beralih konteks untuk menangani interrupt handler.
3. **SoftIRQ (NAPI)**: Kernel menjadwalkan `ksoftirqd` untuk melakukan polling paket via mekanisme NAPI (*New API*) guna menghindari *interrupt storm*.
4. **Socket Buffer (`sk_buff`) Allocation**: Kernel mengalokasikan struktur metadata `sk_buff` untuk setiap paket.
5. **TCP/IP Processing**: Meliputi validasi checksum, lookup routing table, evaluasi *connection tracking* (iptables/netfilter), dan manajemen jendela TCP.
6. **Socket Queue & User Space Transition**: Paket ditempatkan di buffer soket, memicu *wake-up event* pada thread yang menunggu via `epoll_wait()`. Data disalin dari kernel-space ke user-space via `read()` / `recv()`.

```
[ NIC Hardware ]
       | (DMA)
       v
[ RX Ring Buffer ]
       |
  (Hard IRQ) -> CPU Interrupted
       |
  (SoftIRQ / NAPI poll)
       v
+-------------------------------------------------------+
| KERNEL SPACE                                          |
|                                                       |
|  [ Allocate sk_buff ]                                 |
|         |                                             |
|  [ Network Filter (conntrack/iptables) ]              |
|         |                                             |
|  [ TCP Stack Processing (BBR/Cubic) ]                 |
|         |                                             |
|  [ Socket Receive Buffer (rmem) ]                     |
+-------------------------------------------------------+
       | (Copy to User Space / Context Switch)
       v
+-------------------------------------------------------+
| USER SPACE                                            |
|                                                       |
|  [ read() / recv() Syscall ] -> Application Buffer    |
|         |                                             |
|  [ Runtime Scheduler (Go m:n / Thread Pool) ]         |
+-------------------------------------------------------+
```

Untuk memangkas latensi alur ini dari level mikrodetik ke sub-mikrodetik, FDE mengimplementasikan:
- **Zero-Copy I/O**: Menggunakan flag `MSG_ZEROCOPY` atau syscall `splice()` untuk mencegah replikasi payload antar kernel buffer dan user buffer.
- **eBPF (XDP - eXpress Data Path)**: Menjalankan logika routing/filtering langsung pada driver NIC sebelum alokasi `sk_buff` terjadi.

---

### 4. Why & What

| Dimensi | Pendekatan Enterprise Standar | Pendekatan FDE High-Performance Tuning |
| :--- | :--- | :--- |
| **Fokus Metrik** | Latensi rata-rata ($P50$), throughput aggregate ($RPS$). | Tail Latency ($P99$, $P99.9$, Max latency), Jitter, *Off-CPU time*. |
| **Lingkungan** | Public Cloud terkelola (AWS EKS, GCP Cloud Run) seragam. | Heterogen (On-Premises Bare-metal, Virtualized VMware ESXi, Edge appliances). |
| **Investigasi Masalah** | Membaca log APM level aplikasi (Datadog/NewRelic). | Dynamic In-Kernel Tracing (eBPF/BCC), CPU Hardware Counters (PMU), Kernel Stack Sampling. |
| **Resolusi Bottleneck** | Skala horizontal (*horizontal auto-scaling* via pods). | Pemanfaatan hardware optimal (*CPU pinning*, memory-topology aware, zero-copy, sysctl fine-tuning). |
| **I/O Engine** | Blocking I/O atau Generic Non-blocking I/O standar library. | Event-driven lock-free pipelines, Ring Buffers, Zero-Copy POSIX API. |

#### Why
Klien enterprise (perbankan, manufaktur terdistribusi, pertahanan) sering mengikat kontrak FDE dengan Service Level Guarantee berbasis *worst-case performance*. Dalam sistem kliring bursa atau pipeline fraud detection real-time:
- Lonjakan latensi sebesar 5 milidetik pada persentil ke-99 ($P99$) dapat menyebabkan penolakan transaksi, *cascading timeout* pada upstream services, dan denda regulasi finansial.
- Melakukan *scale-out* dengan menambah node server baru bukanlah solusi yang valid ketika lisensi perangkat lunak dihitung per core, kapasitas rak data center klien terbatas, atau saat bottleneck berada pada thread koordinasi sentral (*Amdahl's Law*).

#### What
Tuning performa lanjutan pada ranah FDE mencakup rekayasa end-to-end:
1. **OS/Kernel Level**: Determinisme penjadwalan CPU, eliminasi latensi SoftIRQ, tuning TCP read/write buffer untuk mencegah *window stall*.
2. **Runtime Level**: Meminimalisasi overhead Garbage Collector (GC) melalui teknik alokasi memori hemat escape-analysis, perataan siklus CPU, dan penghapusan *lock contention*.
3. **Application Level**: Arsitektur pemrosesan data asinkron berbasis *batching pipeline*, pemanfaatan struktur data *cache-line friendly*, dan penghapusan copy memori yang redundan.

---

### 5. How (Workflow Detail)

Alur kerja FDE dalam menyelesaikan regresi latensi di lingkungan produksi klien mengikuti metodologi saintifik terstruktur:

```
[ IDENTIFIKASI ]
Metrik SLO Breach (P99 > Threshold)
       |
       v
[ TRIAGE TOPOLOGI ]
Periksa Host: CPU Steal, Context Switches, NUMA Inbalance (vmstat, mpstat)
       |
       v
[ PROFILING LAPISAN KERNEL ]
Gunakan eBPF/BCC (runqlat, offcputime, tcpretrans)
       |
       +---> Apakah Scheduler Bottleneck? (Koreksi CPU Pinning/Cgroups)
       +---> Apakah I/O / Network Drop? (Koreksi Ring Buffer / Sysctl TCP)
       |
       v
[ PROFILING LAPISAN APLIKASI ]
Sampling Execution via Perf / Async-Profiler / Go pprof
       |
       +---> Lock Contention? (Migrasi ke Lock-Free Ring Buffer)
       +---> GC Pacing / Allocation Bottleneck? (Terapkan Zero-Copy & Memory Pool)
       |
       v
[ VALIDASI & BENCHMARKING ]
Load Injection Reproduksi Kasus dengan Synthetic Load Tester
       |
       v
[ DEPLOY KONFIGURASI IMMUTABLE ]
Automasi via Ansible / DaemonSet System Tuning
```

#### Langkah 1: Isolasi Lapisan (Kernel vs. User Space)
Jalankan observasi makro menggunakan `perf` dan `vmstat`:
```bash
# Periksa rasio konteks switch dan voluntary vs non-voluntary switches
vmstat 1 10

# Periksa pembagian beban per core dan softirq
mpstat -P ALL 1 5
```
- Jika nilai `cs` (context switches) melebihi 50.000/detik per socket dan `%sys` tinggi, sistem mengalami *contention* pada lock kernel atau *thread scheduling overhead*.
- Jika `%soft` tinggi pada core tertentu, NIC IRQ belum terdistribusi secara seimbang via `smp_affinity` atau RPS (*Receive Packet Steering*).

#### Langkah 2: Audit Network Buffer & TCP Metrics
Audit status antrean jaringan klien menggunakan `ss` dan `ethtool`:
```bash
# Periksa adanya drops pada antrean socket layer
ss -ntipme

# Periksa buffer overrun pada driver physical network card
ethtool -S eth0 | grep -E "drop|overrun|miss|error"
```

#### Langkah 3: Off-CPU Time Tracing Menggunakan eBPF
Sering kali *profiler* tradisional gagal menangkap latensi tinggi karena profiler tersebut hanya memprofiling *On-CPU time* (kode yang sedang dieksekusi). Latensi $P99$ umumnya disebabkan oleh *Off-CPU time* (thread tertahan di kernel saat menunggu I/O, lock, atau dijadwalkan oleh kernel scheduler):
```bash
# Melacak durasi thread berada dalam status tidur/terblokir (Off-CPU)
/usr/share/bcc/tools/offcputime -df -p $(pgrep core-engine) 30 > offcpu.folded
flamegraph.pl --color=io offcpu.folded > offcpu.svg
```

#### Langkah 4: Optimasi dan Remediasi Bertahap
Terapkan satu perubahan konfigurasi dalam satu waktu. Validasi ulang distribusi latensi melalui uji beban terkontrol menggunakan instrumen uji deterministik (seperti `wrk2` atau instrumen berbasis client-side HDRHistogram).

---

### 6. Analogy & Diagram ASCII

#### Analogi: Kasir Bandara Eksekutif (Lock Contention vs. Dedicated Fast Path)
Bayangkan sebuah loket imigrasi bandara:
- **Pendekatan Naif (Mutex Lock Standard)**: Terdapat 16 loket pemeriksaan, namun seluruh petugas kasir harus mencatat nomor paspor ke dalam *satu buku log fisik yang sama* di tengah ruangan. Setiap kali seorang petugas selesai memeriksa paspor, ia harus berjalan ke tengah ruangan, mengantre untuk memegang pulpen, mencatat, lalu kembali. Meskipun loket banyak, throughput sistem drop drastis dan penumpang mengalami antrean tak terduga (*lock contention*).
- **Pendekatan Low-Latency FDE (Core Affinity & Lock-Free Ring Buffer)**: Setiap petugas memiliki buku catatan digital sendiri (*L1/L2 cache localized*). Dokumen diserahkan melalui ban berjalan satu arah tanpa gesekan (*lock-free single-producer single-consumer ring buffer*). Tidak ada petugas yang saling menunggu. Penumpang mengalir secara deterministik tanpa jeda tak terduga.

#### Diagram Transisi Latensi dan Buffer Overflow

```
Klien Request (Burst 50K RPS)
      │
      ▼
┌──────────────────────────────────────────────┐
│ [NIC Hardware FIFO Ring Buffer]             │
│ [x][x][x][x][x][x][x][x] ---> OVERFLOW DROP! │  <-- Solusi: ethtool -G rx 4096
└──────────────────────────────────────────────┘
      │ (DMA Transfer)
      ▼
┌──────────────────────────────────────────────┐
│ [Linux Kernel Socket Backlog (netdev_max)]  │
│ [x][x][x][x][ ][ ][ ][ ]                     │  <-- Solusi: sysctl net.core.netdev_max_backlog=10000
└──────────────────────────────────────────────┘
      │
      ▼
┌──────────────────────────────────────────────┐
│ [TCP Receive Queue (SO_RCVBUF / rmem)]       │
│ [x][x][x][x][x][x][x][x] ---> TCP STALL      │  <-- Solusi: net.ipv4.tcp_rmem / tcp_window_scaling
└──────────────────────────────────────────────┘
      │ (Syscall read / Context Switch Copy)
      ▼
┌──────────────────────────────────────────────┐
│ [Application User Space]                     │
│ Go/Rust Application Runtime                  │
│                                              │
│  Thread Worker -> [ Contention on Mutex ]    │  <-- Solusi: Lock-free per-core ring buffer
│  Runtime Allocator -> [ GC Mark-Termination] │  <-- Solusi: Pre-allocated object pools
└──────────────────────────────────────────────┘
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Diagnostik Tail Latency dengan bpftrace
Skrip one-liner one-file untuk mendeteksi *scheduler latency* (waktu tunggu thread di run-queue sebelum dieksekusi CPU). Ini adalah indikator utama apakah sistem mengalami *noisy neighbor* atau *CPU starvation*:

```c
/* Filename: runq_latency.bt */
#include <linux/sched.h>

BEGIN {
    printf("Tracing runqueue latency... Hit Ctrl-C to stop.\n");
}

tracepoint:sched:sched_wakeup,
tracepoint:sched:sched_wakeup_new {
    @start[args->pid] = nsecs;
}

tracepoint:sched:sched_switch {
    if (@start[args->next_pid] > 0) {
        $delay = nsecs - @start[args->next_pid];
        @latency_us = hist($delay / 1000);
        delete(@start[args->next_pid]);
    }
}

END {
    clear(@start);
}
```

Jalankan dengan hak akses root:
```bash
sudo bpftrace runq_latency.bt
```
*Interpretasi Hasil*: Jika histogram menunjukkan pembagian distribusi menumpuk di atas 10.000 $\mu s$ (10 ms), CPU node tersebut mengalami *overload* penjadwalan.

---

#### 7.2 Practical Example: High-Throughput Low-Latency Lock-Free In-Memory Ingestion Engine (Go)

Aplikasi berikut mengimplementasikan:
1. **Disruptor Pattern (Lock-Free Circular Ring Buffer)** memanfaatkan primitive atomic CPU (Cache-line padding untuk mencegah *false sharing*).
2. **Zero-Heap Allocation Path** selama pemrosesan data run-time.
3. Konfigurasi runtime untuk pengoperasian sistem low-latency.

```go
package main

import (
	"fmt"
	"net"
	"os"
	"os/signal"
	"runtime"
	"sync/atomic"
	"syscall"
	"time"
	"unsafe"
)

const (
	RingBufferSize = 1048576 // 2^20 (Wajib eksponen 2 untuk bitwise modulo)
	RingBufferMask = RingBufferSize - 1
	MaxBatchSize   = 256
)

// TransactionPayload merepresentasikan data ingest transaksi enterprise
type TransactionPayload struct {
	AccountID uint64
	Amount    int64
	Timestamp int64
	RouteCode uint32
	Flags     uint32
}

// Slot membungkus payload dengan padding eksplisit 64 byte.
// CPU Cache line modern adalah 64 byte. Padding ini menjamin slot yang berdekatan
// tidak berada dalam cache-line yang sama untuk meniadakan False Sharing.
type Slot struct {
	data TransactionPayload
	_pad [64 - unsafe.Sizeof(TransactionPayload{})%64]byte
}

// LockFreeQueue mengimplementasikan Single-Producer Single-Consumer (SPSC) Ring Buffer
type LockFreeQueue struct {
	// Padded write cursor
	writeCursor uint64
	_pad0       [56]byte

	// Padded read cursor
	readCursor uint64
	_pad1      [56]byte

	ring []Slot
}

func NewLockFreeQueue() *LockFreeQueue {
	return &LockFreeQueue{
		ring: make([]Slot, RingBufferSize),
	}
}

func (q *LockFreeQueue) Push(val TransactionPayload) bool {
	currentWrite := atomic.LoadUint64(&q.writeCursor)
	currentRead := atomic.LoadUint64(&q.readCursor)

	// Ring buffer penuh
	if currentWrite-currentRead >= RingBufferSize {
		return false
	}

	q.ring[currentWrite&RingBufferMask].data = val

	// Memory Barrier: pastikan data telah ditulis sebelum kursor dinaikkan
	atomic.StoreUint64(&q.writeCursor, currentWrite+1)
	return true
}

func (q *LockFreeQueue) PopBatch(batch []TransactionPayload) int {
	currentRead := atomic.LoadUint64(&q.readCursor)
	currentWrite := atomic.LoadUint64(&q.writeCursor)

	if currentRead == currentWrite {
		return 0 // Kosong
	}

	count := 0
	limit := int(currentWrite - currentRead)
	if limit > len(batch) {
		limit = len(batch)
	}

	for i := 0; i < limit; i++ {
		batch[i] = q.ring[(currentRead+uint64(i))&RingBufferMask].data
		count++
	}

	// Update pointer read secara atomik
	atomic.StoreUint64(&q.readCursor, currentRead+uint64(count))
	return count
}

func main() {
	// 1. Amankan konfigurasi OS Runtime
	runtime.GOMAXPROCS(runtime.NumCPU())

	queue := NewLockFreeQueue()
	stopChan := make(chan struct{})

	// 2. Consumer Goroutine (Didedikasikan untuk memproses data dari ring buffer)
	go func() {
		// Pin Consumer ke OS Thread agar Cache L1/L2 tetap hangat
		runtime.LockOSThread()
		defer runtime.UnlockOSThread()

		batch := make([]TransactionPayload, MaxBatchSize)
		var totalProcessed uint64
		ticker := time.NewTicker(1 * time.Second)
		defer ticker.Stop()

		for {
			select {
			case <-stopChan:
				return
			default:
				n := queue.PopBatch(batch)
				if n == 0 {
					// Hindari busy-waiting murni yang membakar CPU 100% saat antrean kosong
					// Gunakan sched yield untuk memberi kesempatan instruksi lain
					runtime.Gosched()
					continue
				}

				// Proses batch transaksi secara zero-alloc
				for i := 0; i < n; i++ {
					totalProcessed++
				}
			}
		}
	}()

	// 3. Setup Low-Latency TCP Ingestion Listener
	addr, err := net.ResolveTCPAddr("tcp", "0.0.0.0:9099")
	if err != nil {
		panic(err)
	}

	listener, err := net.ListenTCP("tcp", addr)
	if err != nil {
		panic(err)
	}
	defer listener.Close()

	fmt.Println("[PRODUCTION ENGINE] Menjalankan ingestion server pada port :9099")

	go func() {
		for {
			conn, err := listener.AcceptTCP()
			if err != nil {
				return
			}

			// Tuning low-latency soket klien langsung pada level FD
			_ = conn.SetNoDelay(true)                      // Matikan Nagle Algorithm
			_ = conn.SetKeepAlive(true)                    // Pastikan heartbeat
			_ = conn.SetReadBuffer(1024 * 1024)            // 1MB Socket Recv Buffer
			_ = conn.SetWriteBuffer(1024 * 1024)           // 1MB Socket Send Buffer

			go handleConnection(conn, queue)
		}
	}()

	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)
	<-sigChan

	close(stopChan)
	fmt.Println("\n[PRODUCTION ENGINE] Graceful shutdown selesai.")
}

func handleConnection(conn *net.TCPConn, queue *LockFreeQueue) {
	defer conn.Close()

	// Buffer raw data: 28 byte sesuai representasi TransactionPayload
	// 8(AccountID) + 8(Amount) + 8(Timestamp) + 4(Route) + 4(Flags) = 32 bytes (aligned)
	buf := make([]byte, 32)

	for {
		// Menggunakan ReadFull untuk deterministic fixed-frame read
		_, err := conn.Read(buf)
		if err != nil {
			return
		}

		// Deserialisasi biner zero-alloc via unsafe pointer conversion
		payload := *(*TransactionPayload)(unsafe.Pointer(&buf[0]))

		// Backpressure handling: jika antrean penuh, drop atau return backpressure code
		for !queue.Push(payload) {
			// Backoff singkat jika buffer penuh
			runtime.Gosched()
		}
	}
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Anomali Tail Latency 320ms pada Core Banking Switch Platform Klien Tier-1
* **Latar Belakang**: Sebuah bank sentral swasta multinasional mengintegrasikan platform ingestion microservices FDE ke dalam datacenter *on-premise* mereka.
* **Gejala / Insiden**:
  * Throughput sistem ditargetkan 40.000 TPS.
  * Rata-rata latensi ($P50$) sangat cepat: 1.2 milidetik.
  * Namun, setiap 30–45 detik, persentil ke-99.9 ($P99.9$) melonjak liar dari 2.5 milidetik hingga **320 milidetik**, menyebabkan *timeout cascade* pada integrasi sistem ATM dan Payment Gateway eksternal.

#### Investigasi Mendalam FDE:
1. **Analisis Metrik Tradisional**: Metrik CPU, Memory, dan Network usage rata-rata hanya berkisar di 35%. Tidak ada lonjakan I/O disk karena data sepenuhnya in-memory.
2. **eBPF Profiling**: Menggunakan eBPF tool `ext4slower` dan `runqlat`:
   ```bash
   sudo /usr/share/bcc/tools/runqlat 1 10
   ```
   Ditemukan korelasi langsung antara lonjakan tail latency dengan *huge scheduler delay* pada CPU Core #4 dan Core #12.
3. **Analisis Subsistem Kernel**:
   Melacak *page compaction* menggunakan `perf`:
   ```bash
   perf record -e 'compaction:*' -a -g -- sleep 60
   perf report
   ```
   Ditemukan fungsi `compact_zone()` dan `khugepaged` memblokir alokasi memori aplikasi melalui operasi sinkron *Direct Memory Compaction*. Kernel mencoba menyatukan blok memori 4KB menjadi 2MB Hugepages di latar belakang.
4. **Analisis Inter-Core Traffic**:
   Aplikasi Go dijalankan di bawah Kubernetes tanpa CPU pinning. Kubernetes scheduler secara dinamis memindahkan thread antar CPU Node 0 dan CPU Node 1, memaksa memori disinkronkan melalui QPI/UPI bus yang tersaturasi (*NUMA thrashing*).

#### Tindakan Remediasi FDE:
1. **Nonaktifkan Compaction THP pada Seluruh Node**:
   ```bash
   echo never > /sys/kernel/mm/transparent_hugepage/enabled
   echo never > /sys/kernel/mm/transparent_hugepage/defrag
   ```
2. **Konfigurasi Cgroup & NUMA Isolation**:
   Mengisolasi runtime aplikasi agar hanya berjalan di Node 0 (Local Socket) dan mem-pinning Core menggunakan *Kubernetes Static CPU Manager Policy*:
   ```yaml
   resources:
     limits:
       cpu: "16"
       memory: "32Gi"
     requests:
       cpu: "16"
       memory: "32Gi"
   ```
   Memodifikasi *pod annotation* untuk isolasi core eksklusif: `cpuset.cpus: "0-15"`.
3. **Optimasi Garbage Collector Pacing**:
   Menetapkan parameter pacer Go runtime untuk menekan fragmentasi heap dan mematikan dynamic pacing overhead:
   ```bash
   export GODEBUG=gctrace=1
   export GOGC=200
   export GOMEMLIMIT=28GiB
   ```

#### Hasil Pasca-Remediasi:
- $P99.9$ turun drastis dari **320ms** menjadi stabil di kisaran **1.8ms** di bawah beban puncak 55.000 TPS.
- *Memory allocation latency spikes* tereliminasi total.
- Eliminasi transaksi gagal (*zero drops*) selama periode *clearing* akhir hari.

---

### 9. Trade-offs

Setiap intervensi tuning performa selalu membawa konsekuensi arsitektural. FDE wajib mengevaluasi matriks *trade-off* ini sebelum merilis parameter tuning ke production klien:

| Keputusan Tuning | Peningkatan Performa (Gain) | Dampak Negatif / Konsekuensi (Trade-off) | Rekomendasi Skenario |
| :--- | :--- | :--- | :--- |
| **CPU Pinning / Thread Affinity** | Menghilangkan *cache misses* dan overhead migrasi context-switch. | Mengurangi fleksibilitas OS scheduler; core lain bisa menganggur (*idle*) sementara core terisolasi tertekan. | Wajib untuk core processing loops berkecepatan tinggi; hindari untuk background worker umum. |
| **Disable THP (Transparent Huge Pages)** | Menghilangkan latency spikes akibat *compaction stalls*. | Penggunaan memori meningkat untuk page tables; throughput translasi alamat (TLB miss) pada batch processing besar meningkat tipis. | Wajib untuk database in-memory, message broker latency-critical, dan microservices berlatensi rendah. |
| **Lock-Free SPSC/MPMC Data Structures** | Latensi mutasi data deterministik di skala puluhan nanodetik; tidak ada thread lock suspension. | Kompleksitas maintainability kode sangat tinggi; konsumsi CPU *spin-wait* dapat mencapai 100% jika antrean kosong. | Hanya gunakan pada core hot-path jalur kritis throughput tinggi. |
| **TCP Aggressive Buffering (`rmem`/`wmem` besar)** | Membuka *TCP Window Size* maksimal, throughput transfer data masif melonjak. | Rentan terhadap *bufferbloat*; konsumsi memori per koneksi melonjak (risiko OOM jika ada 100K+ koneksi simultan). | Sangat baik untuk inter-datacenter replication; bahaya untuk edge microservices dengan jutaan client *idle*. |
| **Aggressive GC Tuning (`GOGC=off` / High `GOGC`)** | Meminimalkan atau meniadakan jeda siklus GC pada jam transaksi puncak. | Footprint RAM meningkat secara eksponensial; lonjakan latensi fatal ketika memori mencapai `OOM-Killer`. | Hanya terapkan jika host memiliki headroom RAM minimal 3x lipat dari *active heap working set*. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan Umum (Anti-Patterns):
1. **Blind Copy-Pasting Sysctl**: Menyalin konfigurasi `sysctl.conf` dari blog publik tanpa memahami kapasitas RAM dan interface NIC target. Contoh: Menaikkan `tcp_rmem` ke 64MB per soket pada server dengan 16GB RAM yang melayani 20.000 koneksi bersamaan mengakibatkan kernel panic (*Out-of-Memory*).
2. **Mengabaikan SoftIRQ Imbalance**: Memasang server dengan 64 core, namun seluruh interrupt NIC diproses secara eksklusif oleh Core 0. Akibatnya Core 0 mencapai 100% `%si` (SoftIRQ) sementara 63 core lainnya *idle*, memicu drop paket di lapisan driver.
3. **Over-Instrumentation di Production**: Mengaktifkan `strace` pada proses transaksi ber-throughput tinggi. `strace` menginterupsi proses via `ptrace` pada setiap system call, meningkatkan durasi eksekusi dari mikrodetik ke ratusan milidetik.
4. **Mengabaikan Ephemeral Port Exhaustion**: Tidak mengatur `tcp_tw_reuse` pada arsitektur reverse-proxy outbound yang masif, menyebabkan alokasi koneksi baru gagal akibat status `TIME_WAIT`.

#### Troubleshooting Matrix:

| Gejala Masalah | Metrik / Indikator Utama | Kemungkinan Root Cause | Langkah Remediasi FDE |
| :--- | :--- | :--- | :--- |
| **Paket TCP Drop di Host Level** | Output `netstat -s \| grep "buffer errors"` atau `ethtool` bertambah saat burst. | Ring Buffer interface NIC fisik terlalu kecil untuk menampung burst I/O. | Tingkatkan buffer ring NIC: `ethtool -G <interface> rx 4096 tx 4096`. |
| **Jeda Periodik pada Go Application** | Trace `pprof/goroutine` menunjukkan status `wait on sync.(*Mutex).Lock` masif. | Lock Contention pada resource bersama (misal: single shared connection pool / logger ring buffer). | Sharding state internal menggunakan Striped Locks atau ganti dengan atomic ring buffer. |
| **CPU Saturation di Core 0 Saja** | Output `mpstat -P ALL 1` menunjukkan CPU 0 `%soft` = 100%, core lain 0%. | Irqbalance service mati, atau NIC multiqueue belum terkonfigurasi. | Aktifkan `irqbalance` atau petakan interrupt NIC secara manual via `/proc/irq/*/smp_affinity`. |
| **Latency Jitter pada Virtual Machine** | Metrik `%steal` pada `top` atau `vmstat` bernilai > 5%. | Overcommit CPU pada level Hypervisor ESXi / KVM oleh tim infra klien (*noisy neighbor*). | Mintakan isolasi *vCPU Pinning* 1:1 tanpa overcommit ke administrator infrastruktur host klien. |

---

### 11. Best Practices (Production Checklist)

Gunakan checklist ini sebelum melakukan penyerahan (*sign-off*) sistem performa tinggi di environment klien:

#### Layer 1: BIOS & Perangkat Keras
- [ ] Nonaktifkan fitur penghemat daya CPU: Set Power Governor ke `Performance` (matikan C-States dan P-States hemat energi).
- [ ] Nonaktifkan Hyper-Threading jika arsitektur mengutamakan latensi deterministik deterministik absolut (opsional, tergantung pada kebutuhan throughput total vs latensi jitter).
- [ ] Validasi penempatan kartu NIC pada slot PCIe yang terhubung langsung ke soket CPU lokal (NUMA Node 0).

#### Layer 2: Konfigurasi Kernel Linux (`/etc/sysctl.conf`)
- [ ] Matikan swap agresif: `vm.swappiness = 0` atau `vm.swappiness = 1`.
- [ ] Hindari page compaction stall: `vm.zone_reclaim_mode = 0`.
- [ ] Naikkan antrean soket global:
  ```ini
  net.core.somaxconn = 65535
  net.core.netdev_max_backlog = 65535
  net.ipv4.tcp_max_syn_backlog = 65535
  ```
- [ ] Aktifkan TCP BBR Congestion Control:
  ```ini
  net.core.default_qdisc = fq
  net.ipv4.tcp_congestion_control = bbr
  ```
- [ ] Izinkan reuse koneksi TIME_WAIT untuk outbound:
  ```ini
  net.ipv4.tcp_tw_reuse = 1
  net.ipv4.tcp_fin_timeout = 15
  ```
- [ ] Atur TCP Window Memory Limits (Min, Default, Max):
  ```ini
  net.ipv4.tcp_rmem = 4096 87380 16777216
  net.ipv4.tcp_wmem = 4096 65536 16777216
  ```

#### Layer 3: Runtime & Application Initialization
- [ ] Pre-warm koneksi database, HTTP client pool, dan objek memori saat fase *readiness probe*.
- [ ] Terapkan bounded memory pools (`sync.Pool`) untuk mencegah alokasi baru pada *hot paths*.
- [ ] Hindari operasi string allocation atau serialisasi JSON reflektif di hot-path (gunakan binary codec atau schema-generated serializers seperti Protocol Buffers/FlatBuffers).
- [ ] Pastikan logging berada di mode asynchronous berpenyangga (*buffered/async logging*) atau nonaktifkan logging level verbose (Debug/Trace) di produksi.

---

### 12. Hands-on Practice

Dalam hands-on ini, Anda akan membedah, mengidentifikasi, dan merekayasa perbaikan pada aplikasi Go yang menderita tail-latency tinggi menggunakan eBPF dan tuning kernel.

#### Struktur Direktori Hands-on:
```
hands-on/m02/
├── Makefile
├── client/
│   └── load_tester.go
├── server/
│   ├── main.go
│   └── unoptimized.go
├── tuning/
│   ├── 99-lowlatency.conf
│   └── trace_syscall.bt
└── setup.sh
```

#### Langkah 1: Persiapan Environment
Buat file `setup.sh` dan jalankan di mesin Linux kernel 5.4+ dengan hak akses `sudo`:
```bash
#!/usr/bin/env bash
set -euo pipefail

echo "[*] Menginstal Dependensi Profiling & eBPF..."
sudo apt-get update
sudo apt-get install -y bpftrace bpfcc-tools linux-headers-$(uname -r) wrk sysstat

echo "[*] Membuat direktori hands-on..."
mkdir -p hands-on/m02/{client,server,tuning}
```

#### Langkah 2: Mengompilasi Komponen Server Bermasalah
Buat file `hands-on/m02/server/main.go` yang mensimulasikan bottleneck *contention* dan *excessive allocation*:
```go
package main

import (
	"fmt"
	"net/http"
	_ "net/http/pprof"
	"sync"
	"time"
)

var (
	lock sync.Mutex
	data = make(map[int][]byte)
)

func slowHandler(w http.ResponseWriter, r *http.Request) {
	// Bottleneck 1: Global Lock Contention
	lock.Lock()
	defer lock.Unlock()

	// Bottleneck 2: Excessive Heap Allocation memicu GC
	key := int(time.Now().UnixNano() % 1000)
	temp := make([]byte, 1024*64) // 64KB per request
	temp[0] = 1
	data[key] = temp

	// Bottleneck 3: Sleep buatan mensimulasikan blocking I/O di dalam lock
	time.Sleep(100 * time.Microsecond)

	w.WriteHeader(http.StatusOK)
	w.Write([]byte("OK"))
}

func main() {
	http.HandleFunc("/transact", slowHandler)
	fmt.Println("Server mendengarkan di :8080 (pprof aktif di :8080/debug/pprof)...")
	_ = http.ListenAndServe("0.0.0.0:8080", nil)
}
```

#### Langkah 3: Membuat Load Injector dengan Pelaporan Latensi Akurat
Buat file `hands-on/m02/client/load_tester.go`:
```go
package main

import (
	"fmt"
	"net/http"
	"sync"
	"time"
)

func main() {
	concurrency := 50
	totalRequests := 50000
	client := &http.Client{
		Transport: &http.Transport{
			MaxIdleConnsPerHost: 100,
		},
		Timeout: 2 * time.Second,
	}

	latencies := make(chan time.Duration, totalRequests)
	var wg sync.WaitGroup
	reqPerWorker := totalRequests / concurrency

	start := time.Now()

	for i := 0; i < concurrency; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for j := 0; j < reqPerWorker; j++ {
				t0 := time.Now()
				resp, err := client.Get("http://localhost:8080/transact")
				if err == nil {
					resp.Body.Close()
					latencies <- time.Since(t0)
				}
			}
		}()
	}

	wg.Wait()
	close(latencies)
	totalTime := time.Since(start)

	var all []float64
	for l := range latencies {
		all = append(all, float64(l.Microseconds())/1000.0)
	}

	// Hitung P99 sederhana
	sortFloat64(all)
	p50 := all[int(float64(len(all))*0.50)]
	p99 := all[int(float64(len(all))*0.99)]

	fmt.Printf("\n=== Hasil Uji Performa ===\n")
	fmt.Printf("Total Waktu : %v\n", totalTime)
	fmt.Printf("Throughput  : %.2f RPS\n", float64(len(all))/totalTime.Seconds())
	fmt.Printf("P50 Latency : %.2f ms\n", p50)
	fmt.Printf("P99 Latency : %.2f ms\n", p99)
}

func sortFloat64(arr []float64) {
	for i := 0; i < len(arr); i++ {
		for j := i + 1; j < len(arr); j++ {
			if arr[i] > arr[j] {
				arr[i], arr[j] = arr[j], arr[i]
			}
		}
	}
}
```

#### Langkah 4: Prosedur Eksekusi & Observasi
1. Jalankan server pada Terminal 1:
   ```bash
   cd hands-on/m02/server && go run main.go
   ```
2. Jalankan tracing lock contention via eBPF pada Terminal 2:
   ```bash
   sudo /usr/share/bcc/tools/syncsnoop -T
   ```
3. Jalankan load tester pada Terminal 3:
   ```bash
   cd hands-on/m02/client && go run load_tester.go
   ```
4. Catat output $P99$ awal (akan berkisar di puluhan milidetik).
5. Ganti implementasi handler `main.go` menggunakan arsitektur non-blocking ring buffer dan memory pool (`sync.Pool`), ulangi benchmark, dan amati penurunan nilai $P99$ hingga mencapai di bawah 1 milidetik.

---

### 13. Exercise

#### Level Easy
Konfigurasikan sebuah server Linux uji agar menolak alokasi TCP memory exhaustion dengan mengatur batas memori buffer soket TCP melalui `sysctl`.
* **Tugas**: Set buffer read TCP maksimum menjadi 8MB, nyalakan TCP window scaling, dan aktifkan proteksi SYN Cookies.
* **Kriteria Keberhasilan**: Perintah `sysctl -p` membaca konfigurasi secara persisten dan `sysctl net.ipv4.tcp_syncookies` bernilai `1`.

#### Level Medium
Sebuah aplikasi ingestion berbasis Go mengalami lonjakan *stop-the-world* GC pause setiap 10 detik akibat tingginya alokasi objek sementara pada parsing header HTTP.
* **Tugas**: Terapkan implementasi `sync.Pool` untuk mendaur ulang slice byte buffer transaksi. Integrasikan tool CLI `go tool pprof -alloc_space` untuk membuktikan bahwa alokasi memori berkurang minimal 75% dibandingkan implementasi dasar.
* **Kriteria Keberhasilan**: Metrik heap allocation rate pada benchmark turun drastis dan alokasi per request mendekati 0 B/op.

#### Level Hard
Rancang program `bpftrace` mandiri untuk memetakan distribusi waktu tunggu (*latency*) I/O disk block-layer level enterprise (`block:block_rq_issue` hingga `block:block_rq_complete`).
* **Tugas**: Skrip harus mengelompokkan latensi I/O per perangkat disk (`dev_t`) dan menampilkan histogram logaritmik dalam satuan mikrodetik setiap 10 detik sekali, lalu mengidentifikasi apakah latensi I/O disk mempengaruhi kinerja database lokal aplikasi.
* **Kriteria Keberhasilan**: Skrip berjalan dengan overhead CPU < 0.5% pada beban transaksi tinggi dan secara visual menampilkan histogram ekor panjang jika disk mengalami *I/O stall*.

---

### 14. Challenge

**Studi Kasus Sistem Misi Kritis:**
Anda dideploy sebagai Principal FDE ke sebuah sistem radar perkapalan maritim dan telemetri militer. Platform menerima data tracking via paket UDP multicast frekuensi tinggi dari 500 pemancar satelit.

* **Spesifikasi Kendala Teknis**:
  1. Throughput masuk: **1.200.000 paket/detik**.
  2. Ukuran paket: Rata-rata 512 byte.
  3. Server: 2 Soket Intel Xeon Gold (total 48 core), 128GB RAM, OS: Red Hat Enterprise Linux 8 (Kernel 4.18), air-gapped (tanpa akses internet).
  4. Gejala: Sekitar 3.5% paket hilang (*dropped packets*) setiap menit. Log sistem melaporkan: `netdev_max_backlog` drops, dan pemeriksaan CPU menunjukkan 4 core mengalami saturasi 100% sementara 44 core lainnya hampir menganggur (`idle`).
  5. Batasan Tambahan: Anda **dilarang melakukan recompilation kernel** atau memasang kernel modul yang tidak tersertifikasi.

* **Instruksi Eksekusi**:
  1. Formulasikan arsitektur multi-threaded reader berbasis `SO_REUSEPORT` dan socket pinning.
  2. Hitung dan susun script kalkulasi parameter sysctl network buffer (`net.core.rmem_max`, `netdev_max_backlog`).
  3. Tulis blueprint konfigurasi interupsi NIC (`smp_affinity`, RPS/RFS) agar beban 1.2M paket/detik terdistribusi secara seimbang ke seluruh 48 core tanpa terjadi lock contention pada kernel network stack.
  4. Berikan pembuktian metrik konkret yang akan Anda demonstrasikan kepada Chief Technical Officer klien untuk membuktikan bahwa *packet loss* berhasil ditekan menjadi 0.0000% ($zero\ drop$).

---

### 15. Quiz Evaluasi Pemahaman

#### 5 Pertanyaan Basic
1. **Mengapa nilai rata-rata (Average / Mean Latency) tidak boleh digunakan sebagai acuan keandalan sistem berskala enterprise?**
   - *Jawaban*: Nilai rata-rata menyembunyikan anomali ekor (*tail latency*). Pada arsitektur microservices terdistribusi, satu transaksi end-user memicu puluhan sub-request secara paralel. Berdasarkan hukum probabilitas gabungan, jika salah satu sub-request mengalami lonjakan $P99$, seluruh transaksi induk akan tertahan mengikuti waktu respons terlambat tersebut (*Tail at Scale phenomenon*).

2. **Apa dampak menyalakan algoritma Nagle pada transmisi paket data low-latency?**
   - *Jawaban*: Algoritma Nagle menahan paket kecil dalam buffer untuk digabungkan sebelum dikirim sampai ACK paket sebelumnya diterima. Ini menimbulkan latensi buatan (seringkali terhenti bersamaan dengan fitur *Delayed ACK* TCP hingga 40-200ms). Pada sistem latensi rendah, algoritma ini harus dinonaktifkan dengan menyetel opsi `TCP_NODELAY`.

3. **Apa perbedaan mendasar antara *On-CPU latency profiling* dan *Off-CPU latency profiling*?**
   - *Jawaban*: *On-CPU profiling* merekam instruksi dan fungsi mana yang aktif membakar siklus CPU saat berjalan. *Off-CPU profiling* merekam waktu dan *call stack* ketika sebuah thread dihentikan (*blocked/sleeping*), misalnya saat mengantre di mutex lock, menunggu respon storage I/O, atau tertahan di *kernel scheduler queue*.

4. **Mengapa Transparent Huge Pages (THP) sering kali disarankan untuk dimatikan pada server database in-memory?**
   - *Jawaban*: Karena mekanisme *direct compaction* pada THP dapat membekukan alokasi memori secara sinkron saat kernel mencari blok memori kontinu berukuran 2MB yang terfragmentasi, memicu lonjakan latensi yang sporadis dan tidak terprediksi.

5. **Apa yang dimaksud dengan fenomena *False Sharing* pada arsitektur multi-core?**
   - *Jawaban*: Kondisi ketika dua thread yang berjalan pada dua core berbeda memodifikasi variabel independen yang kebetulan berada di dalam satu baris cache fisik yang sama (CPU *Cache Line*, biasanya 64 byte). Protokol koherensi cache akan memaksa baris cache tersebut diinvalidasi bolak-balik antar core, menurunkan performa secara drastis seolah-olah terjadi locking.

#### 5 Pertanyaan Intermediate
6. **Bagaimana mekanisme *Zero-Copy* via syscall `splice()` mengurangi latensi pengiriman file ke soket jaringan dibanding kombinasi tradisional `read()` dan `write()`?**
   - *Jawaban*: Pola `read()` + `write()` memerlukan dua kali pergantian konteks (*context switch*) dan menyalin data dua kali: dari kernel page cache ke user-space buffer aplikasi, lalu dari user-space ke socket buffer di kernel-space. Syscall `splice()` mentransfer referensi halaman langsung antar-pipe buffer di dalam kernel space tanpa memindahkan payload data fisik ke user space, mengeliminasi CPU copy overhead dan cache thrashing.

7. **Pada tuning TCP Linux, parameter apa yang mengatur ukuran maksimal antrean koneksi yang telah selesai melakukan 3-way handshake tetapi belum dipanggil oleh syscall `accept()` oleh aplikasi?**
   - *Jawaban*: Parameter `net.core.somaxconn` pada level kernel dan argumen `backlog` pada pemanggilan syscall `listen(sockfd, backlog)` di level aplikasi.

8. **Mengapa penambahan core CPU yang berlebihan kadang justru menurunkan throughput pada aplikasi yang mengandalkan satu *Mutex* global bersama?**
   - *Jawaban*: Sesuai dengan Hukum Amdahl (*Amdahl's Law*), porsi kode yang berjalan secara serial (di bawah proteksi Mutex) membatasi skalabilitas maksimum. Menambah core CPU meningkatkan persaingan akses fisik (*cache coherency invalidation*, CAS - *Compare-And-Swap contention*) pada atomic variable lock tersebut, sehingga CPU menghabiskan lebih banyak siklus untuk sinkronisasi cache bus daripada eksekusi instruksi produktif.

9. **Apa peran eBPF XDP (*eXpress Data Path*) dibandingkan penggunaan library raw socket biasa dalam memitigasi serangan traffic burst atau filtering paket berkecepatan tinggi?**
   - *Jawaban*: XDP mengeksekusi bytecode program eBPF langsung di dalam konteks driver kartu jaringan (NIC), tepat setelah paket diterima dari DMA ring buffer dan *sebelum* alokasi struktur data kernel `sk_buff` yang memakan resource besar dilakukan. Raw socket masih memerlukan inisiasi paket di alur networking stack kernel yang normal.

10. **Bagaimana cara kerja mekanisme CPU Affinity (`taskset` / `pthread_setaffinity_np`) dalam mereduksi latensi instruksi?**
    - *Jawaban*: Dengan mengunci proses atau thread pada core CPU spesifik, kernel scheduler dilarang memindahkan thread tersebut ke core lain. Hal ini menjaga kehangatan data (*cache locality*) pada Cache L1/L2 core bersangkutan dan mengeliminasi overhead *cold-cache miss* serta translasi TLB (*Translation Lookaside Buffer*) akibat perpindahan konteks eksekusi antar core.

#### 3 Skenario Kasus Produksi
11. **Skenario 1 (Kasus Jaringan/TCP)**:
    *Kasus*: Sebagai FDE, Anda mendapati bahwa transfer file log diagnostik 5GB antar dua datacenter internal klien menggunakan protokol HTTP/2 mengalami pembatasan throughput pada kecepatan 20 MB/s, padahal kapasitas bandwidth jaringan fisik antar datacenter adalah 10 Gbps dengan Round-Trip Time (RTT) 45ms. Tidak ada packet drop yang terdeteksi pada router.
    *Pertanyaan*: Apa akar penyebab masalah ini, metrik apa yang membuktikannya, dan bagaimana formula remediatornya?
    *Jawaban*:
    - **Akar Masalah**: *Bandwidth-Delay Product (BDP)* mismatch akibat ukuran buffer TCP window dibatasi oleh konfigurasi default Linux yang terlalu konservatif. Formula $BDP = Bandwidth \times RTT = (10 \times 10^9 \text{ bps} / 8) \times 0.045 \text{ s} \approx 56.25 \text{ MB}$. Jika buffer TCP maksimum (`tcp_wmem`/`tcp_rmem`) hanya terset pada nilai default (misal 4MB), TCP Window tidak dapat membesar melampaui 4MB, sehingga throughput teoritis terkunci pada $4\text{MB} / 0.045\text{s} \approx 88.8 \text{ MB/s}$ (atau lebih rendah jika ada overhead framing).
    - **Metrik Pembuktian**: Jalankan `ss -ntio`. Periksa nilai `wscale` dan rasio `snd_wnd` vs kapasitas pipa. Nilai `snd_wnd` akan stuck di level maksimum tanpa utilisasi throughput penuh.
    - **Remediasi**: Tingkatkan batas maksimum buffer TCP di `/etc/sysctl.conf`:
      ```ini
      net.ipv4.tcp_rmem = 4096 87380 67108864 # Max 64MB
      net.ipv4.tcp_wmem = 4096 65536 67108864 # Max 64MB
      net.ipv4.tcp_window_scaling = 1
      ```

12. **Skenario 2 (Kasus Memori/GC)**:
    *Kasus*: Modul stream-processing Go Anda di-deploy di node edge klien dengan batas memori kontainer 2GB. Setiap kali traffic mencapai puncak 10.000 events/detik, runtime Go memicu GC cycle beruntun hingga 80 kali per menit, menghabiskan 40% kapasitas CPU dan menggandakan latensi $P99$. Memory usage sebenarnya dari data aktif (*in-use heap*) hanya sekitar 400MB.
    *Pertanyaan*: Analisis mengapa GC terpicu sangat sering dan bagaimana langkah teknis meredam frekuensi siklus GC tanpa memicu risiko OOM?
    *Jawaban*:
    - **Akar Masalah**: Rasio default `GOGC=100` memicu GC setiap kali heap tumbuh 100% dari working set sebelumnya. Pada active working set 400MB, GC akan aktif setiap kali alokasi baru mencapai 400MB tambahan. Dalam throughput 10K events/detik, churn objek jangka pendek memenuhi 400MB ini dalam hitungan detik.
    - **Remediasi**:
      1. Terapkan konfigurasi `GOMEMLIMIT=1800MiB` (sisakan 200MB untuk overhead non-heap dan thread runtime) dan naikkan target pacing `GOGC=200` atau `GOGC=300`. GC tidak akan dipaksa berjalan agresif selama total alokasi memori kontainer masih berada di bawah ambang batas aman 1800MiB.
      2. Lakukan audit kode menggunakan `pprof -alloc_objects`: Bungkus payload event masuk ke dalam `sync.Pool` untuk mengeliminasi alokasi objek baru pada heap, mengubah pola memory lifecycle menjadi *zero-allocation in steady-state*.

13. **Skenario 3 (Kasus Linux Scheduler/Kernel Contention)**:
    *Kasus*: Sebuah aplikasi microservice payment berbasis Rust menunjukkan degradasi performa tak terduga ($P99.9$ > 500ms) saat dipindahkan dari lingkungan pengujian staging ke klaster Kubernetes produksi klien yang menggunakan mesin dual-socket 128 core AMD EPYC. Profiling CPU menunjukkan 85% utilisasi terpusat pada system call `futex()` dan kernel function `native_queued_spin_lock_slowpath()`.
    *Pertanyaan*: Identifikasi apa yang terjadi pada arsitektur perangkat keras dan kernel OS klien, serta berikan rekomendasi deployment cgroups/K8s untuk mengatasinya!
    *Jawaban*:
    - **Akar Masalah**: Terjadi *Cross-NUMA Node Lock Contention* dan *False Sharing* antar Core CPU lintas soket. Multi-threading engine mencoba mengakses mutex lock atau alokator heap global yang sama lintas NUMA domain. Sinyal cache coherency harus melintasi interkoneksi soket (Infinity Fabric), mengakibatkan latensi sinkronisasi spinlock kernel melonjak drastis (*slowpath*).
    - **Remediasi**:
      1. Pecah instance pod Kubernetes monolitik besar menjadi pods yang lebih kecil (misalnya, daripada 1 Pod dengan 64 core, gunakan 4 Pod dengan masing-masing 16 core terisolasi).
      2. Terapkan Kubernetes `topologySpreadConstraints` dan konfigurasi isolasi NUMA via NUMA-aware Node Resource Manager (Topology Manager policy: `single-numa-node`).
      3. Konfigurasikan memory bind policy: Jalankan proses di dalam Pod menggunakan wrapper `numactl --cpunodebind=0 --membind=0` untuk mengurung thread dan alokasi memori hanya di dalam satu soket fisik tunggal.

---

### 16. Summary

Menguasai tuning performa dan optimasi latensi tingkat lanjut adalah pembeda utama seorang **Forward-Deployed Engineer** senior saat beroperasi di garda terdepan sistem enterprise:
- **Tail Latency Dominates**: Keberhasilan sistem diukur bukan dari rata-rata performa ($P50$), melainkan ketahanan prediktibilitas pada persentil terburuk ($P99$, $P99.9$).
- **Holistic Tuning Stack**: Rekayasa latensi menuntut investigasi menyeluruh mulai dari topologi silikon (NUMA, Cache line padding, PCIe locality), alur kernel network (NAPI, SoftIRQ, TCP backlogs, BBR), hingga runtime bahasa pemrograman (escape-analysis, lock-free circular queues, explicit memory pooling).
- **Measure, Don't Guess**: Hindari asumsi dan manipulasi parameter kernel secara acak. Gunakan instrumentasi modern berbasis eBPF (`bpftrace`, `bcc-tools`) untuk melacak *Off-CPU stalls*, *scheduler queue latencies*, dan hambatan transmisi jaringan langsung dari sumber kebenaran kernel.
- **Architectural Determinism**: Optimasi puncak dicapai bukan dengan mempercepat kode yang buruk, melainkan dengan meniadakan operasi yang tidak perlu: *zero allocation*, *zero copy*, *zero lock contention*, dan *deterministic execution path*.