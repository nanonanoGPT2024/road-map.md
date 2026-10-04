# BAB 09: Capacity Planning, Performance Engineering & Chaos Engineering
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis dan Memodelkan Kapasitas Sistem Non-Linear**: Mengimplementasikan Universal Scalability Law (USL) dan Little's Law untuk memprediksi titik jenuh (*saturation point*) dan degradasi konkurensi (retrograde behavior) secara matematis pada sistem terdistribusi.
2. **Mendeteksi Bottleneck Sistem Level Kernel via Continuous Profiling**: Menjalankan profiling runtime berbasis eBPF (*Extended Berkeley Packet Filter*) untuk menganalisis CPU saturation, lock contention (*futex*), memory allocations, dan I/O wait tanpa mengorbankan stabilitas produksi (*overhead* < 1%).
3. **Mengeliminasi Fenomena Coordinated Omission**: Merancang dan mengeksekusi pengujian performa beban tinggi (*open-system vs closed-system load generation*) untuk mengekspos tail latency ($p99$, $p99.9$, $p99.99$) yang akurat.
4. **Merancang dan Mengotomatisasi Arsitektur Continuous Chaos Verification**: Membangun *steady-state hypothesis testing framework* otomatis di dalam pipeline CI/CD dan Kubernetes produksi menggunakan Chaos Mesh/LitmusChaos dengan batas *blast radius* yang terkendali ketat.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib menguasai:
* Konsep dasar SRE: SLI/SLO/SLA, Error Budget, dan Monitoring/Observability (Prometheus & OpenTelemetry).
* Pemahaman arsitektur kernel Linux: Process scheduling (CFS), memory management (paging, swap, slab allocator), syscalls, dan socket lifecycle (`TCP/IP stack`, `epoll`).
* Pengalaman praktis dengan Kubernetes orchestration: CRD (*Custom Resource Definition*), CNI (*Container Network Interface*), Resource Quotas, HPA/VPA internals.
* Penguasaan bahasa pemrograman Go atau Python untuk komputasi numerik dan automasi sistem.
* Familiaritas dengan CLI tracing dasar: `perf`, `strace`, `bpftrace`, `sysstat` (`vmstat`, `iostat`, `mpstat`).

---

### 3. Concept & Internal Architecture

#### 3.1 Teori Kapasitas Lanjutan: Dari Amdahl ke Universal Scalability Law (USL)

Kapasitas sistem terdistribusi tidak pernah bersifat linear. Pendekatan kapasitas tradisional sering kali salah mengasumsikan bahwa menambah $N$ *node* akan meningkatkan throughput sebesar $N \times \text{throughput single-node}$.

##### Hukum Amdahl vs USL (Neil J. Gunther)
Hukum Amdahl hanya memperhitungkan faktor serialisasi (*contention*):

$$C(N) = \frac{N}{1 + \sigma(N - 1)}$$

Dimana:
* $C(N)$: Skalabilitas relatif atau throughput pada konkurensi $N$.
* $N$: Jumlah *worker*, thread, atau node.
* $\sigma$ (*sigma*): Fraksi sistem yang harus dieksekusi secara serial (concurrency bottleneck, e.g., database mutex, global lock).

Model Amdahl mengasumsikan throughput mendekati asimtot konstan saat $N \to \infty$. Namun, sistem terdistribusi nyata mengalami **penurunan performa absolut (retrograde behavior)** akibat *coherency overhead* (misal: *cache invalidation protocols*, *two-phase commit*, *cross-node gossip protocols*, *distributed consensus*).

Neil J. Gunther memformulasikan **Universal Scalability Law (USL)**:

$$C(N) = \frac{N}{1 + \sigma(N - 1) + \kappa N(N - 1)}$$

Dimana:
* $\kappa$ (*kappa*): Parameter *cross-talk* atau penundaan koherensi data antar-node (komunikasi $N(N-1)$ pasang node).

```
Throughput C(N)
   ^
   |        / Ideal Linear Scalability (Slope = 1)
   |       /
   |      /     --- Amdahl's Limit (Asymptote = 1/σ)
   |     /   .-'
   |    /  .'
   |   /  /
   |  / .'   __...---\
   | / /  .-'         \    <-- USL Real-World System with Retrograde
   |/.-'               \       (Capacity drops due to Crosstalk / Coherency: κ)
   +-------------------------------------> Concurrency / Nodes (N)
                    ^ N_max (Peak Capacity Point)
```

Titik balik kapasitas maksimum ($N_{\max}$) sebelum degradasi sistem:

$$N_{\max} = \sqrt{\frac{1 - \sigma}{\kappa}}$$

Throughput maksimum yang dapat dicapai ($C_{\max}$):

$$C_{\max} = \frac{1}{\sigma + 2\sqrt{\kappa(1 - \sigma)} - \kappa}$$

##### Little's Law dan Derivasinya pada Antrean Sistem
Little's Law mendefinisikan hubungan invariabel dalam kondisi stabil (*steady state*):

$$L = \lambda W$$

* $L$: Rata-rata jumlah request dalam sistem (*concurrency* / *in-flight requests*).
* $\lambda$: *Arrival rate* rata-rata (throughput, requests/second).
* $W$: Rata-rata waktu tinggal request dalam sistem (*residence time* / latency).

Ketika sistem mendekati kapasitas jenuh ($L \to L_{\max}$), antrean memanjang secara eksponensial berdasarkan teori antrean $M/M/1$ atau $M/M/c$:

$$W = \frac{1}{\mu - \lambda}$$

Jika $\lambda \to \mu$ (utilisasi $\rho = \lambda/\mu \to 1$), maka latency $W \to \infty$.

---

#### 3.2 Performance Profiling Internals: Continuous eBPF & Kernel Tracing

Sampling CPU tradisional berbasis interrupt (seperti `pstack` atau gprof) menimbulkan overhead tinggi dan distorsi sampling bias. Solusi modern mengandalkan **eBPF (Extended Berkeley Packet Filter)** di level kernel Linux.

##### Mekanisme Kerja eBPF Runtime Tracing
1. Kompiler memvalidasi bytecode eBPF via *Kernel In-Tree Verifier* (mencegah infinite loop, unauthorized memory access, kernel panic).
2. Bytecode di-JIT (*Just-In-Time compiled*) ke instruksi native CPU.
3. Event handler dipasang pada probe points:
   * **kprobe / kretprobe**: Dinamis, pada entry/exit fungsi kernel arbitrary (misal: `vfs_read`, `tcp_v4_connect`).
   * **tracepoint**: Statis, deterministik, di-compile langsung di kernel (misal: `sched:sched_switch`, `net:netif_receive_skb`).
   * **uprobe / uretprobe**: User-space dynamic probe (misal: alokasi `malloc`, runtime Go `runtime.casgstatus`).
   * **perf_event**: Timer interrupt berkala (misal: 99 Hz sampling frequency) untuk mengambil kernel & user call stack.
4. Data dikirim ke user-space melalui memory-efficient ring buffers (`BPF_MAP_TYPE_RINGBUF`).

```
+-----------------------------------------------------------------------+
| USER SPACE                                                            |
|  +--------------------+         +----------------------------------+  |
|  | Target Application |         | Continuous Profiling Collector   |  |
|  | (JVM / Go / Rust)  |         | (Pyroscope Agent / Parca Agent)  |  |
|  +--------------------+         +----------------------------------+  |
|            |                              ^                           |
|            |                              | (Read Aggregated Stacks)  |
|------------|------------------------------|---------------------------|
| KERNEL     v                              |                           |
|  +-----------------------------------------------------------------+  |
|  | eBPF Subsystem                                                  |  |
|  |  +---------------------+      +------------------------------+  |  |
|  |  | Tracepoint / kprobe | ---> | BPF Ring Buffer / Stack Map  |  |  |
|  |  +---------------------+      +------------------------------+  |  |
|  |             ^                                                   |  |
|  |             | (99 Hz Timer Interrupt: perf_event_open)          |  |
|  |  +---------------------+                                        |  |
|  |  | Linux CPU Scheduler | (context switches, futex locks, CFS)   |  |
|  |  +---------------------+                                        |  |
+-----------------------------------------------------------------------+
```

---

#### 3.3 Chaos Engineering: Fault Injection Internals

Chaos Engineering bukan sekadar "mematikan server secara acak". Ini adalah disiplin eksperimen berbasis hipotesis empiris pada sistem terdistribusi.

##### Mekanisme Fault Injection Level OS & Kernel
Chaos engine (seperti Chaos Mesh atau LitmusChaos) menginjeksikan kegagalan secara deterministik menggunakan fitur native Linux:

1. **Network Chaos (Latency, Packet Loss, Corruption, Duplication)**:
   * Memanfaatkan **Linux Traffic Control (`tc`)** dan subsistem **Network Emulation (`netem`)**.
   * Menambahkan queueing discipline (`qdisc`) baru pada interface virtual (`veth` / `cni0`).
   * *Packet Drop / Corruption*: Dimanipulasi melalui modifikasi aturan `iptables` / `nftables` pada chain `PREROUTING` atau interface routing eBPF.

2. **I/O Chaos (Delay, Fault Injection)**:
   * Menggunakan **FUSE (Filesystem in Userspace)** untuk me-reroute I/O syscalls (`read`, `write`, `sync`), atau menginjeksi error code (misal: `EIO`, `ENOSPC`) menggunakan uprobe/kprobe tracing via eBPF.

3. **Compute Chaos (CPU/Memory Stress, Kernel Kill)**:
   * **cgroups (Control Groups)**: Mengubah parameter `cpu.cfs_quota_us`, `memory.max`, atau memicu Linux OOM Killer dengan mengalokasikan anonymous memory hingga batas `cgroup.oom.group`.

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional | Pendekatan Enterprise SRE Lanjutan |
| :--- | :--- | :--- |
| **Capacity Planning** | Berbasis utilitas rata-rata (CPU > 70% $\to$ Scale Out). Asumsi scaling linear tak terbatas. | Pemodelan USL berbasis empiris. Identifikasi $\sigma$ dan $\kappa$ untuk mencegah keruntuhan akibat *coherency bottleneck*. |
| **Load Testing** | *Closed-loop system*: Virtual users menunggu respons sebelum mengirim request baru (Memicu *Coordinated Omission*). | *Open-loop system*: Request arrival rate independen terhadap response time sistem (Koreksi tail latency empiris). |
| **Performance Profiling** | Ad-hoc profiling saat terjadi incident menggunakan debugger (`gdb`, `jstack`), memicu latency spike. | *Continuous Always-On eBPF Profiling* dengan overhead < 1% CPU, agregasi Flame Graph secara realtime. |
| **Chaos Testing** | Manual testing di staging environment yang tidak merefleksikan load dan topology produksi. | *Continuous Automated Chaos Verification* langsung di staging/canary/production terisolasi dengan blast radius terukur. |

---

### 5. How (Workflow Detail)

Alur kerja terpadu untuk pengujian kapasitas, profiling, dan verifikasi chaos:

```
[ Phase 1: Baseline & Modeling ]
       |
       v
Collect Historical Metrics (RPS, Concurrency, p99 Latency, Errors)
       |
       +--> Run Regression to derive USL Parameters (σ, κ)
       |
       +--> Calculate Max System Capacity (N_max, C_max)
       |
[ Phase 2: Open-Model Load Generation ]
       |
       v
Configure Distributed Load Generator (e.g., k6 with constant arrival rate)
       |
       +--> Stream OpenTelemetry traces & Continuous eBPF Profiler (Pyroscope)
       |
[ Phase 3: Automated Chaos Injection ]
       |
       v
Verify Steady-State Hypothesis (SLO check: p99 < 150ms, Error Rate < 0.01%)
       |
       +--> Inject Fault via Chaos Mesh (e.g., 200ms Network Delay on DB replica)
       |
       +--> Continuously Validate SLO Breaches
       |        |
       |        +-- [Breach Detected] --> Abort Chaos Immediately (Safety Rollback)
       |        |
       |        +-- [System Resilient] -> Pass Test & Output Resilience Score
       |
[ Phase 4: Root Cause & Optimization ]
       v
Analyze Flamegraph via eBPF (Identify Lock Contention / CPU Hotspots)
       |
Remediate (e.g., adjust connection pool, replace mutex with lock-free structure)
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Jalan Tol vs. Teori Antrean & Koherensi
1. **Linear Scaling**: Menambah jumlah jalur tol akan melipatgandakan kapasitas kendaraan per jam secara sempurna tanpa hambatan.
2. **Amdahl's Law ($\sigma$)**: Jalur tol ditambah dari 2 menjadi 16 jalur, tetapi seluruh kendaraan harus berhenti di satu gerbang pembayaran manual yang sama. Gerbang manual tersebut adalah bottleneck serialisasi ($\sigma$).
3. **Universal Scalability Law ($\kappa$)**: Setiap pengemudi di jalur tol harus saling bernegosiasi via walkie-talkie dengan setiap pengemudi lain di jalur yang berbeda sebelum berpindah jalur. Ketika mobil berjumlah sedikit, komunikasi mudah. Ketika ada 1.000 mobil, waktu habis hanya untuk koordinasi antar mobil ($\kappa$). Kapasitas sistem ambruk total, bahkan lebih lambat dibanding kondisi saat hanya ada 2 jalur.
4. **Chaos Engineering**: Bukan menabrakkan truk ke pembatas jalan di jam sibuk tanpa rencana, melainkan memasang speed trap, menutup satu jalur darurat secara terukur, dan memvalidasi apakah rambu pengalihan otomatis berfungsi tanpa menyebabkan kemacetan total.

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Menghitung USL Parameter dan Prediksi Saturation (Python)

Script ini melakukan *non-linear least squares regression* pada data load test untuk menghitung koefisien $\sigma$ (serialization) dan $\kappa$ (crosstalk).

```python
#!/usr/bin/env python3
import numpy as np
from scipy.optimize import curve_fit

def usl_model(n, sigma, kappa):
    """
    Universal Scalability Law Formula
    n: Concurrency / Worker Count
    sigma: Serialization parameter
    kappa: Crosstalk / Coherency parameter
    """
    return n / (1 + sigma * (n - 1) + kappa * n * (n - 1))

# Data empiris dari load test: Concurrency (N) vs Throughput (RPS relatif)
concurrency = np.array([1, 2, 4, 8, 16, 32, 64, 96, 128], dtype=np.float64)
throughput  = np.array([1000, 1920, 3600, 6400, 10500, 14200, 12800, 9500, 6800], dtype=np.float64)

# Normalisasi throughput terhadap N=1
x_data = concurrency
y_data = throughput / throughput[0]

# Fit kurva USL
popt, _ = curve_fit(usl_model, x_data, y_data, bounds=(0, [1.0, 1.0]), p0=[0.05, 0.001])
sigma_est, kappa_est = popt

# Hitung titik kapasitas optimal
n_max = np.sqrt((1 - sigma_est) / kappa_est)
c_max = usl_model(n_max, sigma_est, kappa_est) * throughput[0]

print(f"=== Universal Scalability Law (USL) Result ===")
print(f"Sigma (Contention/Serialization) : {sigma_est:.6f}")
print(f"Kappa (Crosstalk/Coherency)     : {kappa_est:.6f}")
print(f"Optimal Concurrency (N_max)      : {n_max:.2f} workers")
print(f"Maximum Predicted Throughput     : {c_max:.2f} RPS")
```

---

#### 7.2 Practical Example: Load Testing Bebas Coordinated Omission (k6) & Fault Injection (Chaos Mesh)

##### A. Distributed k6 Script dengan Arrival-Rate Executor (Mencegah Coordinated Omission)

```javascript
// load-test-open-model.js
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter, Rate, Trend } from 'k6/metrics';

// Metrics khusus untuk memantau degradation
const customLatency = new Trend('custom_processing_duration', true);
const errorRate = new Rate('system_errors');

export const options = {
  scenarios: {
    // Open-model executor: Arrival rate independen terhadap latency target
    constant_rate_stress: {
      executor: 'constant-arrival-rate',
      rate: 15000,             // 15,000 requests
      timeUnit: '1s',           // per second
      duration: '5m',
      preAllocatedVUs: 1000,    // VU dialokasikan di awal untuk menghindari stall
      maxVUs: 5000,             // Kapasitas maksimum VUs saat latency membengkak
    },
  },
  thresholds: {
    'http_req_duration': ['p(95)<150', 'p(99)<300', 'p(99.9)<800'],
    'system_errors': ['rate<0.001'], // Maksimum 0.1% error
  },
};

const BASE_URL = __ENV.TARGET_URL || 'https://api-payment.internal.enterprise';

export default function () {
  const payload = JSON.stringify({
    account_id: 'ACC-839219',
    amount: 150000,
    currency: 'IDR',
    timestamp: Date.now(),
  });

  const params = {
    headers: {
      'Content-Type': 'application/json',
      'X-Resilience-Experiment': 'bab09-chaos-test',
    },
    timeout: '2000ms',
  };

  const start = Date.now();
  const res = http.post(`${BASE_URL}/v1/transactions`, payload, params);
  const duration = Date.now() - start;

  customLatency.add(duration);

  const isSuccess = check(res, {
    'status is 200': (r) => r.status === 200,
    'circuit-breaker not tripped': (r) => r.status !== 503,
  });

  if (!isSuccess) {
    errorRate.add(1);
  } else {
    errorRate.add(0);
  }
}
```

##### B. Chaos Mesh Custom Resource Definition (CRD): Network Delay & Packet Corruption

```yaml
# chaos-network-delay.yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: NetworkChaos
metadata:
  name: simulate-database-network-degradation
  namespace: payment-production-canary
spec:
  action: delay
  mode: fixed
  value: '2' # Target exactly 2 pods
  selector:
    namespaces:
      - payment-production-canary
    labelSelectors:
      app: postgresql-replica
  delay:
    latency: '180ms'
    jitter: '20ms'
    correlation: '25'
  direction: to
  target:
    selector:
      namespaces:
        - payment-production-canary
      labelSelectors:
        app: payment-core-service
    mode: all
  duration: '3m'
  scheduler:
    cron: '@every 10m'
```

##### C. eBPF Trace Script untuk Memantau Lock Contention (bpftrace)

Script ini mendeteksi proses apa yang mengalami waktu tunggu terlama pada `futex` (Fast Userspace Mutex), penyebab umum degradasi $\kappa$ pada Go/Java:

```bash
#!/usr/bin/env bpftrace

BEGIN
{
  printf("Tracing futex contention. Hit Ctrl-C to stop.\n");
}

tracepoint:syscalls:sys_enter_futex
{
  @start[tid] = nsecs;
}

tracepoint:syscalls:sys_exit_futex
/@start[tid]/
{
  $duration_us = (nsecs - @start[tid]) / 1000;
  @futex_wait_us[comm] = hist($duration_us);
  delete(@start[tid]);
}

END
{
  printf("\nHistogram of Futex Wait Latency (microseconds) by Process:\n");
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Degradasi Sistem Transaksi Core Banking saat Event Flash Sale Nasional
* **Skala Sistem**: 120 Node Kubernetes, 800 Microservices Pods, Database Distributed Postgres (1 Primary, 4 Read Replicas via connection pooler PgBouncer).
* **Load Baseline**: 3.500 RPS pada jam kerja normal ($p99 < 45\text{ms}$).
* **Kondisi Insiden**: Saat traffic meningkat menjadi 28.000 RPS akibat Flash Sale, throughput sistem tiba-tiba anjlok ke 1.200 RPS dengan error `HTTP 504 Gateway Timeout` masif. CPU utilization di seluruh node Kubernetes justru *turun* dari 65% ke 18%.

#### Investigasi Lanjutan SRE:
1. **Anti-Pattern Terdeteksi via eBPF Continuous Profiler**:
   * Tim profiling menggunakan Flame Graph menemukan bahwa 75% waktu CPU thread pool dihabiskan pada status `futex_wait_queue_me` di kernel space.
   * **Root Cause 1**: Konfigurasi koneksi database di aplikasi menggunakan pooling lokal sebesar 150 koneksi per container. Dengan 800 pod, total potensi koneksi adalah $800 \times 150 = 120.000$ koneksi ke PgBouncer, yang menyebabkan overhead pergantian konteks (*context switching*) ekstrem dan lock contention pada socket buffer.
2. **Coordinated Omission pada Load Test Sebelumnya**:
   * Load test sebelumnya menggunakan JMeter dengan thread group tertutup (*closed-model*).
   * Ketika backend melambat dari 50ms menjadi 5000ms, injector thread ikut tertahan, sehingga traffic yang dikirim turun otomatis. Laporan pengujian sebelumnya secara keliru mencatat $p99$ sebesar 120ms.
3. **Analisis USL**:
   * Evaluasi empiris data traffic menunjukkan nilai $\kappa = 0.012$.
   * Dengan formula $N_{\max} = \sqrt{(1 - \sigma)/\kappa}$, jumlah thread paralel optimal aplikasi berada di angka $N=24$. Skala pod saat itu (800 pods) telah melompati batas kapasitas optimal, mendorong sistem ke area keruntuhan kapasitas (*retrograde scaling zone*).

```
System Performance Failure Under Load:
Throughput (RPS)
  30k +                       Expected Linear Scale
      |                              /
  20k |                    USL      /
      |                  Curve    /
  10k |                . - - - . /
      |             .-'         ` - .
   0k +-----------/------------------\-------------------> Load (Active Threads)
      0         100      500         800 (Pods deployed)
                                      ^
                                      Massive Futex Lock Contention & Retrograde Collapse
```

#### Remediasi Produksi:
* Mengganti pooling per pod menjadi adaptive dynamic pooler (Max connection diturunkan dari 150 ke 12 per container).
* Menerapkan queue limiting dan adaptive concurrency control (TCP BBR-like algorithm pada ingress gateway: Netflix Concurrency Limits).
* Melakukan validasi ulang menggunakan script k6 berbasis open-loop arrival-rate. Hasil: Sistem mampu menahan 42.000 RPS stabil dengan $p99 < 110\text{ms}$.

---

### 9. Trade-offs

| Aspek Arsitektur | Pilihan A | Pilihan B | Trade-off Analysis |
| :--- | :--- | :--- | :--- |
| **Load Model Strategy** | **Closed-loop System** (Virtual Users Loop) | **Open-loop System** (Constant Arrival Rate) | Pilihan A mudah diatur tetapi menyamarkan bottleneck akibat Coordinated Omission. Pilihan B akurat mengekspos degradasi real-world, tetapi membutuhkan resource injection rig yang jauh lebih besar dan berisiko mematikan target service secara permanen jika tidak diimbangi guard rails. |
| **Continuous Profiler** | **Application Agent** (misal: Java Agent, Python cProfile) | **eBPF Kernel-space Tracing** (misal: Parca, Pyroscope) | Application Agent dapat membaca context metadata internal object runtime lebih dalam, namun memiliki overhead 5–15% CPU dan risiko memicu Stop-The-World (GC). eBPF memiliki overhead < 1% dan aman di produksi, namun memerlukan kernel Linux modern ($\ge 5.4$) dan izin `CAP_SYS_ADMIN` / `CAP_BPF`. |
| **Chaos Automation Level** | **Scheduled GameDays** (Manual trigger di non-prod) | **Continuous In-Pipeline Production Chaos** | Scheduled GameDays minim risiko operasional mendadak, namun tidak memverifikasi drifts konfigurasi harian. Continuous Production Chaos menjamin resistensi real-time, namun membutuhkan investasi besar dalam Canary Deployment, Auto-Rollback SLI, dan automated circuit-breaking. |
| **Concurrency Scaling** | **Aggressive Scale-Out** (Banyak pod kecil) | **Scale-Up / Balanced Density** (Sedikit pod besar) | Scale-out ekstrim meningkatkan fault isolation pod, namun mendegradasi performa via koherensi jaringan ($\kappa$ meningkat: distributed cache invalidation, connection explosion). Pod besar menurunkan overhead $\kappa$, namun meningkatkan blast radius saat satu proses crash. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Coordinated Omission pada Load Generation
* **Gejala**: Hasil load test menunjukkan $p99$ response time sangat rendah (misal: 80ms), namun pengguna di produksi mengalami timeout 30 detik.
* **Akar Masalah**: Load generator menunggu response sebelum mengirimkan request berikutnya. Saat service hang selama 10 detik, generator tidak mengirim request baru selama durasi tersebut. Antrean request yang seharusnya menumpuk tidak terbentuk di statistik pengujian.
* **Solusi**: Gunakan load generator yang memisahkan thread pembangkit interval (*arrival schedule*) dari thread eksekusi respons (misal: k6 `constant-arrival-rate`, Gatling, Locust `FastHttpUser` dengan paced arrival).

#### 2. False Assurance akibat Chaos Blast Radius Terlalu Longgar atau Sempit
* **Gejala**: Eksperimen Chaos selalu berhasil (*Passed*), tetapi saat kabel switch fisik switch-over di datacenter, sistem downtime selama 45 menit.
* **Akar Masalah**: Fault injection dilakukan pada mock server atau environment staging tanpa background traffic autentik. Tidak ada kompetisi resource CPU/jaringan saat kegagalan diinjeksikan.
* **Solusi**: Terapkan Chaos pada canary deployment yang menerima traffic produksi riil minimal 5%, gunakan injection bertingkat (misal: Latency 20ms $\to$ 50ms $\to$ 150ms $\to$ Packet Loss 5%), dan verifikasi bahwa *blast radius limit* diproteksi oleh automated circuit-breaker.

#### 3. Mengabaikan Metric Linux Network SoftIRQ Saturation
* **Gejala**: CPU utilization server terlihat hanya 40%, tetapi API response time melonjak tinggi dan terjadi packet drop.
* **Akar Masalah**: Antrean network packet diproses oleh single CPU core via SoftIRQ (Software Interrupt Request, `ksoftirqd/x`). Jika NIC *Receive Side Scaling* (RSS) tidak dikonfigurasi dengan benar, satu core akan terbebani 100% SoftIRQ sementara core lain menganggur.
* **Solusi**:
  ```bash
  # Cek distribusi softirq pada seluruh core
  mpstat -P ALL 1
  # Periksa konsumsi NET_RX di /proc/softirqs
  watch -d cat /proc/softirqs
  # Aktifkan Receive Packet Steering (RPS) pada interface
  echo "f" > /sys/class/net/eth0/queues/rx-0/rps_cpus
  ```

---

### 11. Best Practices (Production Checklist)

#### Capacity Planning
- [ ] Hitung nilai $\sigma$ (serialization) dan $\kappa$ (coherency) menggunakan formula USL sebelum deployment rilis arsitektur baru.
- [ ] Konfigurasikan batas atas connection pool aplikasi agar tidak melebihi kapasitas antrean core storage / database layer ($Pool \le \text{Core count} \times 2 + \text{Disk Spindle/Channel count}$).
- [ ] Set Auto-Scaling (HPA) berdasarkan metric saturasi antrean (misal: queue length, in-flight requests) bukan hanya persentase penggunaan CPU/Memory rata-rata.

#### Performance Engineering & Profiling
- [ ] Pasang Continuous eBPF Profiler di seluruh node worker cluster produksi dengan sampling rate yang aman (49 Hz atau 99 Hz).
- [ ] Lakukan benchmarking load test menggunakan model antrean terbuka (*open-system*) secara periodik.
- [ ] Kompilasi binary dengan frame pointers diaktifkan (`-fno-omit-frame-pointer` untuk C/C++/Rust, atau bawaan Go) agar eBPF stack unwinder dapat membaca call chain tanpa overhead debugging symbol yang besar.

#### Chaos Verification
- [ ] Definisikan *Steady-State Hypothesis* berbasis metrik SLI bisnis (misal: Pembayaran Berhasil per Detik), bukan hanya *HTTP status 200*.
- [ ] Pasang mekanisme *Automated Abort Condition*: Hentikan injeksi chaos secara instan jika SLO error budget terkonsumsi > 2% selama interval testing.
- [ ] Jalankan skenario chaos minimal: Latensi Dependensi Kritis, DNS Resolution Failure, CPU Throttling (CFS limits), dan Database Pod Eviction mendadak.

---

### 12. Hands-on Practice

Dalam latihan ini, Anda akan mempraktikkan diagnosis saturasi thread dan penundaan I/O menggunakan Continuous Profiling, mengeksekusi load test open-model, dan memvalidasi resiliensi pod via Chaos injection.

Struktur direktori kerja:
```
hands-on/m02/
├── app/
│   ├── main.go
│   └── Dockerfile
├── k8s/
│   ├── deployment.yaml
│   └── chaos-experiment.yaml
├── load-test/
│   └── perf-test.js
└── Makefile
```

#### Langkah 1: Siapkan Server API Target dengan Bug Lock Contention (Go)
Simpan kode ini di `hands-on/m02/app/main.go`. Aplikasi ini mensimulasikan bottleneck serialisasi global mutex.

```go
package main

import (
	"fmt"
	"math/rand"
	"net/http"
	"sync"
	"time"
)

var (
	globalLock sync.Mutex
	sharedCounter int64
)

func handler(w http.ResponseWriter, r *http.Request) {
	start := time.Now()

	// Simulasi bottleneck serialisasi data (Amdahl's sigma bottleneck)
	globalLock.Lock()
	time.Sleep(time.Duration(10+rand.Intn(5)) * time.Millisecond)
	sharedCounter++
	globalLock.Unlock()

	// Simulasi kerja CPU non-kritis
	dummySum := 0
	for i := 0; i < 50000; i++ {
		dummySum += i
	}

	w.WriteHeader(http.StatusOK)
	fmt.Fprintf(w, "OK: counter=%d, took=%s\n", sharedCounter, time.Since(start))
}

func main() {
	http.HandleFunc("/process", handler)
	fmt.Println("Server running on port 8080...")
	http.ListenAndServe(":8080", nil)
}
```

#### Langkah 2: Buat Skenario Pengujian Open-Model dengan k6
Simpan di `hands-on/m02/load-test/perf-test.js`:

```javascript
import http from 'k6/http';
import { check } from 'k6';

export const options = {
  scenarios: {
    stress_test: {
      executor: 'constant-arrival-rate',
      rate: 200,              // 200 reqs/detik (akan menjenuhkan lock 10-15ms)
      timeUnit: '1s',
      duration: '45s',
      preAllocatedVUs: 50,
      maxVUs: 300,
    },
  },
  thresholds: {
    http_req_duration: ['p(95)<500'],
  },
};

export default function () {
  const res = http.get('http://localhost:8080/process');
  check(res, { 'status is 200': (r) => r.status === 200 });
}
```

#### Langkah 3: Eksekusi dan Identifikasi Lock Bottleneck Menggunakan `bpftrace`
Buka terminal dan jalankan service:
```bash
cd hands-on/m02/app
go run main.go
```

Di terminal kedua, jalankan k6 load test:
```bash
cd hands-on/m02/load-test
k6 run perf-test.js
```

Di terminal ketiga (dengan akses `sudo`), pantau contention pada kernel scheduler:
```bash
# Jalankan profiler one-liner untuk melihat thread off-CPU wait time (akibat lock contention)
sudo bpftrace -e '
tracepoint:sched:sched_switch /comm == "main"/ {
    @switch_count[comm] = count();
}
interval:s:5 {
    time("%H:%M:%S ");
    print(@switch_count);
    clear(@switch_count);
}'
```

#### Langkah 4: Terapkan Skenario Injeksi Chaos Network Latency via Chaos Mesh
Deploy eksperimen ke namespace testing Kubernetes:
```yaml
# hands-on/m02/k8s/chaos-experiment.yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: NetworkChaos
metadata:
  name: simulate-slow-network
  namespace: default
spec:
  action: delay
  mode: all
  selector:
    namespaces:
      - default
    labelSelectors:
      app: payment-api
  delay:
    latency: '150ms'
    jitter: '10ms'
  duration: '60s'
```
Terapkan:
```bash
kubectl apply -f hands-on/m02/k8s/chaos-experiment.yaml
kubectl get networkchaos -A
```

---

### 13. Exercise

#### Level: Easy
Analisis antrean sistem perbankan. Sebuah endpoint otentikasi memproses request dengan throughput rata-rata $\lambda = 500$ request per detik. Monitoring memperlihatkan rata-rata concurrency request yang menggantung di memori sistem ($L$) adalah 75 request. Berdasarkan **Little's Law**, hitung rata-rata response time ($W$) endpoint tersebut dalam milidetik!

#### Level: Medium
Diberikan serangkaian hasil stress-test berikut:
* 1 Core: 500 RPS
* 2 Cores: 950 RPS
* 4 Cores: 1.800 RPS
* 8 Cores: 3.200 RPS
* 16 Cores: 4.800 RPS
* 32 Cores: 5.200 RPS
* 64 Cores: 3.900 RPS

Jelaskan fenomena apa yang terjadi antara alokasi 16 ke 64 cores menggunakan terminologi Universal Scalability Law ($\sigma$ dan $\kappa$). Identifikasi dua penyebab arsitektural umum dalam level runtime (Go runtime scheduler atau JVM memory model) yang memicu kurva retrograde semacam ini!

#### Level: Hard
Tuliskan template konfigurasi k6 untuk pengujian kapasitas berkonsep *Step-Up Open Arrival Rate* yang mengeksekusi load bertingkat:
* Menit 0–2: 1.000 RPS
* Menit 2–4: 5.000 RPS
* Menit 4–6: 15.000 RPS
* Menit 6–8: 30.000 RPS
Integrasikan threshold otomatis yang langsung membatalkan uji beban (*aborts the test*) jika error rate melebihi 5% atau $p99$ response time melampaui 2.000 milidetik selama lebih dari 30 detik berturut-turut.

---

### 14. Challenge

**Skenario Sistem**: Anda adalah Principal Performance Engineer pada platform e-commerce tiket konser berskala global. Sistem menggunakan Kubernetes, Redis Sentinel Cluster (untuk distributed lock antrean pembelian), dan PostgreSQL. 

**Kondisi Krisis**:
Setiap kali penjualan tiket artis tier-A dibuka (paku traffic mencapai 250.000 concurrent user dalam 3 detik), sistem mengalami anomali:
1. Load generator internal berbasis JMeter mengklaim $p99$ latency hanya 210ms.
2. Metrik gateway NGINX mencatat $p99$ melonjak hingga 14.200ms dengan 35% response menghasilkan error code `502 Bad Gateway`.
3. CPU pods microservices Go hanya berada di kisaran 30–40%.
4. Cluster Autoscaler (HPA) lambat bereaksi, dan ketika berhasil menambah pod baru dari 50 ke 300 pod, latency melonjak dua kali lipat lebih buruk (sistem mati total).

**Tugas Anda**:
Rancang dokumen *Architecture Resilience & Engineering Remediation Strategy* komprehensif yang mencakup:
* Analisis detail penyebab perbedaan metrik JMeter vs NGINX (hubungkan dengan coordinated omission).
* Formulasi matematis kapasitas maksimum menggunakan USL dan rancang guard rail untuk menghentikan autoscaler sebelum mencapai zona retrograde.
* Skenario pengujian Continuous Chaos otomatis yang harus dijalankan di pipeline staging mingguan untuk mencegah regresi performa ini terulang kembali.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic Questions
1. **Apa perbedaan mendasar antara Hukum Amdahl dan Universal Scalability Law (USL)?**
   * *Jawaban*: Hukum Amdahl hanya memodelkan pembatasan skalabilitas akibat serialisasi sistem ($\sigma$), sehingga performa akan mendekati batas datar konstan (asymptote). USL menambahkan parameter koherensi atau komunikasi antar-node ($\kappa$), sehingga mampu memodelkan fenomena *retrograde* di mana performa sistem menurun drastis saat node/thread ditambah melampaui kapasitas jenuh.

2. **Jelaskan apa yang dimaksud dengan Coordinated Omission pada load testing!**
   * *Jawaban*: Kondisi pengujian di mana keterlambatan atau stall pada sistem target secara tidak sengaja memperlambat laju pengiriman request oleh load generator (pada closed-loop test). Akibatnya, request yang seharusnya terantre diabaikan dari kalkulasi statistik, memalsukan metrik tail latency ($p99$) menjadi terlihat jauh lebih cepat dari realitas.

3. **Berapa batas aman CPU overhead untuk penggunaan continuous profiling berbasis eBPF di server produksi?**
   * *Jawaban*: Standar industri enterprise menetapkan batas overhead sampling eBPF continuous profiler (seperti Parca atau Pyroscope) adalah di bawah 1% konsumsi total CPU mesin host.

4. **Bagaimana Little's Law dinyatakan secara matematis dan apa arti masing-masing variabelnya?**
   * *Jawaban*: $L = \lambda W$. Di mana $L$ adalah jumlah rata-rata request/item di dalam sistem (*concurrency/queue depth*), $\lambda$ adalah arrival rate atau throughput kedatangan request per satuan waktu, dan $W$ adalah rata-rata residence/latency time request di dalam sistem.

5. **Di level OS, mekanisme kernel Linux apa yang paling umum dimanfaatkan oleh Chaos Mesh untuk mensimulasikan latensi dan kehilangan paket jaringan?**
   * *Jawaban*: Linux Traffic Control (`tc`) yang digabungkan dengan subsistem Network Emulation (`netem`), serta manipulasi paket melalui `iptables` / `nftables` atau filter network eBPF.

#### Intermediate Questions
6. **Mengapa menaikkan jumlah container/pod Kubernetes secara agresif melalui HPA (Horizontal Pod Autoscaler) justru bisa memperburuk sistem saat database mengalami lock contention?**
   * *Jawaban*: Setiap pod baru membawa alokasi connection pool database tersendiri. Ketika database sudah jenuh akibat serial lock, penambahan ratusan koneksi baru memicu context-switching massal, memory page-faulting, dan pertukaran pesan sinkronisasi internal di level storage engine. Ini meningkatkan faktor koherensi $\kappa$ dalam USL, menjatuhkan throughput total secara eksponensial.

7. **Mengapa profiler CPU berbasis sampling interrupt timer tradisional (seperti JVM async-profiler tanpa frame pointer OS) dapat menghasilkan bias profiling?**
   * *Jawaban*: Safepoint bias. Profiler berbasis sinyal user-space sering kali harus menunggu runtime mencapai titik aman (*safepoint*) sebelum mengambil call stack. Thread yang tertahan pada lock non-safepoint atau instruksi I/O kernel panjang tidak tersampel secara proporsional.

8. **Bagaimana parameter `jitter` pada konfigurasi Chaos Network Latency membantu menguji ketahanan distributed system?**
   * *Jawaban*: Jitter memperkenalkan variasi acak pada delay (misal: 100ms $\pm$ 30ms). Ini memecah asumsi deterministik pada connection timeouts, memicu *out-of-order packets*, mengekspos race-conditions pada algoritma konsensus distributed state, dan menguji kemampuan transport buffer TCP/HTTP2 dalam menangani paket asinkron.

9. **Apa perbedaan fungsional antara probe Linux kernel `kprobe` dan `tracepoint` dalam observabilitas performa?**
   * *Jawaban*: `tracepoint` adalah instrumen statis yang telah ditentukan dan dikompilasi langsung di kernel source code, menawarkan stabilitas API antar-versi kernel dan performa lebih cepat. `kprobe` adalah dynamic probe yang dapat dipasang di hampir semua instruksi memori entry kernel function, namun tidak memiliki garansi ABI stabil antar-versi Linux kernel dan memiliki sedikit overhead lebih tinggi.

10. **Kapan Anda harus menggunakan open-loop arrival model dibandingkan closed-loop arrival model pada stress test?**
    * *Jawaban*: Open-loop model wajib digunakan jika sistem melayani lalu lintas publik/pengguna independen (misal: HTTP web service, payment gateway, public API) di mana kedatangan request baru tidak peduli apakah request pengguna sebelumnya telah selesai diproses. Closed-loop hanya relevan untuk simulasi batch worker antrean tertutup dengan jumlah client worker yang fix.

#### Skenario Kasus Produksi
11. **Kasus 1: Thread Exhaustion Misterius pada Microservice Go**
    * *Skenario*: Microservice pemrosesan klaim mengalami timeout $p99$ hingga 10 detik saat load test mencapai 8.000 RPS. Namun, utilitas CPU mesin hanya 25% dan memory consumption sangat stabil. Profiling internal Go (`pprof`) tidak dapat diakses via endpoint HTTP karena ikut membeku (*freeze*).
    * *Langkah Diagnostik & Solusi*:
      1. Masalah: Goroutine dump internal terkunci karena handler pprof ikut tertahan scheduler (`runtime.sched`).
      2. Tindakan: Gunakan tracing eksternal via eBPF tanpa masuk ke HTTP endpoint aplikasi:
         ```bash
         sudo bpftrace -e 'tracepoint:sched:sched_switch /comm == "claim-service"/ { @blocked[kstack] = count(); }'
         ```
      3. Analisis stack trace off-CPU untuk mendeteksi apakah thread tertahan pada `runtime.semacquire` (sync.Mutex / unbuffered channel channel block) atau blocked syscall socket write.
      4. Solusi struktural: Ganti shared lock global pada cache lokal dengan striped lock architecture (*sharded locks*) atau struktur data lock-free (misal: `sync.Map` atau atomic pointer swap).

12. **Kasus 2: Degradasi I/O Akibat Page Cache Eviction under Chaos Stress**
    * *Skenario*: Engine injeksi Chaos menjalankan IOStress pada cluster worker. Seketika, pod elasticsearch yang berada pada node yang sama mengalami cluster split-brain karena heartbeat timeout antar-node gagal.
    * *Langkah Diagnostik & Solusi*:
      1. Diagnosa: Stressor I/O membanjiri write buffer kernel Linux, memaksa OS mengeksekusi synchronous write flushing (`dirty_ratio` terlampaui), menyebabkan kernel membekukan seluruh thread lain yang memerlukan alokasi page cache (termasuk JVM IO thread milik Elasticsearch).
      2. Solusi: Pisahkan *cgroup io controller* antara target testing dan pod sistem vital. Batasi `io.weight` dan `io.max` pod non-kritis menggunakan cgroups v2 di level runtime container (`containerd`).
      3. Konfigurasikan kernel parameter sysctl pada worker node produksi:
         ```bash
         sysctl -w vm.dirty_background_ratio=5
         sysctl -w vm.dirty_ratio=10
         ```
         Hal ini memaksa thread latar belakang kernel (`flusher threads`) mencicil flush data ke storage sebelum memblokir eksekusi thread user-space.

13. **Kasus 3: Canary Deployment Meledak Akibat Hidden Cross-Talk ($\kappa$)**
    * *Skenario*: Sebuah service arsitektur stateful cluster diekspansi secara dinamis menggunakan Horizontal Pod Autoscaler dari 20 node menjadi 80 node saat lonjakan event. Sesaat setelah HPA menaikkan node, latensi sistem melonjak 800% dan throughput terpotong setengahnya.
    * *Langkah Diagnostik & Solusi*:
      1. Diagnosa: Cluster state menggunakan full-mesh gossip protocol antar-node ($N(N-1)$ communication channels). Ketika node bertambah dari 20 (190 channel komunikasi) menjadi 80 node (3.160 channel komunikasi), node menghabiskan 80% siklus CPU dan bandwidth antarmuka jaringan hanya untuk sinkronisasi state membership gossip.
      2. Mitigasi Darurat: Bekukan ekspansi HPA secara manual. Kurangi instance target secara terukur ke batas kapasitas optimum sebelum titik balik kurva USL tercapai.
      3. Solusi Arsitektural: Ubah topologi full-mesh gossip menjadi hierarchical ring atau delegasikan metadata coordination kepada external distributed consensus engine yang terspesialisasi (seperti etcd atau Raft metadata cluster terisolasi), mereduksi kompleksitas koherensi dari $\mathcal{O}(N^2)$ menjadi $\mathcal{O}(N \log N)$.

---

### 16. Summary

1. **Skalabilitas Nyata Tunduk pada Universal Scalability Law (USL)**: Skalabilitas tidak pernah linear. Kapasitas sistem dibatasi oleh fraksi serialisasi data ($\sigma$, Hukum Amdahl) dan degradasi koherensi data antar-node ($\kappa$, cross-talk Gunther). Mengabaikan parameter $\kappa$ dan membiarkan HPA melakukan auto-scale secara membabi buta akan menjerumuskan sistem ke dalam *retrograde capacity collapse*.
2. **Eliminasi Coordinated Omission**: Tail latency empiris ($p99$, $p99.9$) hanya dapat diukur secara presisi menggunakan *open-system load generator* yang memiliki laju arrival independen terhadap waktu respon backend. Closed-loop load testing secara sistematis menyembunyikan bottleneck fatal pada sistem produksi.
3. **Continuous Profiling Berbasis eBPF adalah Standar Baru Observabilitas**: Profiler konvensional menimbulkan overhead dan bias yang berbahaya di produksi. Pemanfaatan kernel-native eBPF tracing mampu memotret eksekusi on-CPU dan status off-CPU (lock contention, futex waits, I/O block) secara granular dengan overhead CPU di bawah 1%.
4. **Chaos Engineering adalah Pengujian Empiris Terkendali, Bukan Kerusakan Acak**: Keberhasilan fault injection terletak pada formulasi hipotesis baseline *steady-state*, pembatasan *blast radius* yang terisolasi ketat via Linux cgroups/traffic control, serta integrasi sistem penghenti darurat (*automated circuit-breaker abort*) yang langsung aktif saat batas SLO terancam.