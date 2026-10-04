# Modul 01: Capacity Planning, Performance Engineering, & Chaos Testing

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta mampu:
- Menerapkan kalkulasi matematis antrean dan konkurensi menggunakan **Little's Law** dan batasan skalabilitas konkuren dengan **Amdahl's Law** serta **Universal Scalability Law (USL)**.
- Merancang dan mengeksekusi arsitektur *Capacity Planning* prediktif berbasis pemodelan saturasi resource (*CPU, Memory, Disk I/O, Network Throughput*).
- Mengembangkan skenario uji beban (*Performance & Stress Testing*) terdistribusi bebas dari bias *Coordinated Omission* menggunakan **k6** dan **Locust**.
- Menginternalisasi prinsip-prinsip **Chaos Engineering**, mendefinisikan *Steady State Hypothesis*, memitigasi *Blast Radius*, dan mengeksekusi injeksi kegagalan (*Fault Injection*) menggunakan **Chaos Mesh** dan manifest Kubernetes native.
- Memfasilitasi dan mengorkestrasi agenda **Game Day** produksi yang aman, terukur, dan terautomasi dalam siklus rilis platform cloud-native.

---

## 2. Prerequisite
Peserta diharapkan telah memiliki pemahaman operasional terhadap:
- **SRE Core Metrics**: Pemahaman mendalam tentang SLI, SLO, SLA, dan *Four Golden Signals* (Latency, Traffic, Errors, Saturation).
- **Kubernetes Architecture**: Pemahaman tentang Pod lifecycle, Resource Requests/Limits, QoS Classes (`Guaranteed`, `Burstable`), Horizontal Pod Autoscaler (HPA), dan Custom Resource Definitions (CRD).
- **Networking Protocols**: TCP handshakes, windowing, network namespaces, Linux `tc` (traffic control), `cgroups`, dan `iptables/nftables`.
- **Python/JavaScript Fundamentals**: Mampu membaca dan memodifikasi skrip pengujian beban k6 (JavaScript) dan Locust (Python).

---

## 3. Concept
Dalam rekayasa keandalan sistem berskala besar (*large-scale distributed systems*), performa dan keandalan bukanlah atribut pasif, melainkan hasil rekayasa probabilistik aktif:

1. **Capacity Planning & Saturation Forecasting**: Menghitung secara empiris kapan infrastruktur akan kehabisan kapasitas sebelum degradasi performa terjadi. Pendekatan reaktif berbasis *threshold alerting* (contoh: "Alert saat CPU > 80%") tidak memadai karena antrean (*queuing*) meningkat secara asimtotik non-linear ketika utilisasi mendekati kapasitas jenuh.
2. **Performance Engineering**: Disiplin analitis untuk mengidentifikasi dan memusnahkan *bottleneck* sebelum kode mencapai fase rilis. Menggunakan hukum matematis sistem antrean untuk memvalidasi apakah penambahan node atau resource komputasi akan memberikan peningkatan throughput secara linier atau justru memicu *contention penalty*.
3. **Chaos Engineering**: Pendekatan eksperimental empiris untuk membangun keyakinan (*confidence*) terhadap ketahanan sistem di lingkungan terdistribusi melalui injeksi turbulensi terkontrol. Menghilangkan asumsi keandalan dengan membuktikan bagaimana komponen sistem bereaksi ketika dependensi eksternal, jaringan, atau komputasi mengalami kegagalan parsial (*grey failures*).

---

## 4. Why
Mengapa modul ini krusial bagi Site Reliability Engineer tingkat lanjut?
- **Kegagalan Skalabilitas Statis**: Menambah CPU core tidak selalu membuat aplikasi berjalan lebih cepat. Berdasarkan *Amdahl's Law* dan *USL*, sinkronisasi data antar-thread atau serialisasi database justru menyebabkan degradasi performa (*crosstalk penalty*) saat konkurensi dinaikkan secara masif.
- **Deteksi Silent Failures**: Lebih dari 70% insiden berskala besar di lingkungan cloud terjadi bukan karena server mati total, melainkan akibat *grey failures*—seperti lonjakan latensi mikro (p99/p99.9), kehilangan paket jaringan (packet loss 2%), atau thread pool starvation yang tidak memicu alarm infrastruktur standar namun merusak SLO bisnis.
- **Pencegahan Over-Provisioning vs. Under-Provisioning**: Menghemat biaya infrastruktur cloud ratusan ribu dolar dengan mengetahui kapasitas optimal sebenarnya secara analitis, alih-alih menebak-nebak ukuran kluster Kubernetes.
- **Validasi Failover Otomatis**: Memastikan mekanisme resiliensi (seperti *circuit breaker*, *exponential backoff with jitter*, dan HPA) benar-benar berfungsi saat terjadi bencana di bawah beban traffic nyata.

---

## 5. What (Deep-Dive Teknis Lengkap)

### A. Fondasi Matematika: Little's Law & Amdahl's Law

#### 1. Little's Law
Menyatakan hubungan operasional dalam sistem antrean stabil:
$$L = \lambda \times W$$
Di mana:
- $L$ = Rata-rata jumlah request dalam sistem (Concurrency / In-flight Requests).
- $\lambda$ = Rata-rata arrival rate (Throughput dalam Requests per Second / RPS).
- $W$ = Rata-rata waktu pemrosesan satu request (Residence Time / Latency dalam detik).

**Penerapan Operasional**:
Jika API Gateway Anda menerima $10.000\text{ RPS}$ ($\lambda = 10.000$) dan downstream service rata-rata membutuhkan waktu $200\text{ ms}$ ($W = 0{,}2\text{ s}$), maka jumlah *concurrent connections* ($L$) yang harus ditangani oleh sistem secara paralel adalah:
$$L = 10.000 \times 0{,}2 = 2.000\text{ koneksi paralel}$$
Jika thread pool pod Anda dibatasi hanya 200 koneksi per instance, Anda mutlak membutuhkan minimal:
$$\frac{2.000}{200} = 10\text{ Pod}$$
hanya untuk melayani traffic rata-rata tanpa antrean. Jika latensi naik menjadi $1\text{ detik}$ akibat database locking, maka kebutuhan pod melonjak seketika menjadi 50 Pod!

#### 2. Amdahl's Law
Menghitung percepatan teoretis (*speedup*) dari sistem dengan alokasi resource tambahan:
$$S_{latency}(s) = \frac{1}{(1 - p) + \frac{p}{s}}$$
Di mana:
- $S_{latency}$ = Faktor percepatan teoretis sistem.
- $p$ = Proporsi program yang dapat diparalelkan ($0 \le p \le 1$).
- $s$ = Faktor peningkatan kapasitas komputasi (misal: jumlah core baru).

Jika 20% dari eksekusi aplikasi bersifat serial (misal: transaksi ACID atau mutex lock), maka nilai $p = 0{,}8$. Berapa pun core CPU ($s \to \infty$) yang ditambahkan, percepatan maksimum sistem tidak akan pernah melebihi:
$$S_{max} = \frac{1}{1 - 0{,}8} = 5\times$$

#### 3. Universal Scalability Law (Dr. Neil Gunther)
Pengembangan dari Amdahl's Law yang memperhitungkan penalti komunikasi antar-node (*coherency delay / crosstalk*):
$$C(N) = \frac{N}{1 + \sigma(N - 1) + \kappa N(N - 1)}$$
Di mana:
- $N$ = Jumlah worker / node / core.
- $\sigma$ = Parameter kontensi (*contention / serialization*).
- $\kappa$ = Parameter koherensi (*coherency / crosstalk delay* antar worker).
Ketika $\kappa > 0$, kurva kapasitas akan berbalik menurun (*retrograde scalability*): penambahan worker setelah titik kritis justru memperlambat throughput sistem.

---

### B. Resource Saturation Forecasting
Saturasi resource diukur berdasarkan *Utilization, Saturation, and Errors (USE Method)*. Pemodelan degradasi performa non-linear dihitung menggunakan prinsip *M/M/1 Queueing Model*:
$$T_q = \frac{\rho}{\mu(1 - \rho)}$$
Di mana:
- $T_q$ = Waktu tunggu dalam antrean.
- $\rho$ = Utilisasi resource ($\frac{\lambda}{\mu}$).
- $\mu$ = Service rate.

Ketika utilisasi resource ($\rho$) melampaui $80\%$ ($0{,}8$), waktu tunggu antrean meledak secara eksponensial. Capacity planning modern memanfaatkan data timeseries dari Prometheus dikombinasikan dengan regresi polinomial atau algoritma peramalan (*forecasting*) seperti Prophet / Holt-Winters untuk mendeteksi kapan titik saturasi kritis ($80\%$) akan tersentuh berdasarkan tren pertumbuhan data.

---

### C. Performance Testing: k6, Locust, & Coordinated Omission

#### Coordinated Omission (Gil Tene)
Kesalahan fatal dalam load testing konvensional di mana tool pengujian menunggu respons dari request sebelumnya sebelum mengirimkan request berikutnya menggunakan *fixed thread pool*. Ketika server mengalami *pause* (misalnya Full GC selama 5 detik):
1. Tool load test terjeda tidak mengirim request.
2. Latensi tinggi hanya tercatat untuk 1 request yang tertahan.
3. Ratusan request yang seharusnya dijadwalkan tiba selama 5 detik tersebut tidak dikirimkan, sehingga metriks p99 tampak normal padahal di dunia nyata antrean klien sudah meledak.

**Solusi**: Gunakan tool modern seperti **k6** dengan *arrival-rate executor* (`constant-arrival-rate`) di mana throughput target dijaga konstan tanpa terikat pada waktu respons server.

---

### D. Chaos Engineering Principles & Fault Injection
Prinsip inti Chaos Engineering (*Principles of Chaos Engineering*):
1. **Build a Hypothesis around Steady State Behavior**: Definisikan kondisi normal sistem berbasis SLI/SLO (misal: "Error rate HTTP 5xx tetap di bawah 0,1% dan p99 latency < 250ms").
2. **Vary Real-world Events**: Injeksi kejadian kegagalan perangkat keras, partisi jaringan, lonjakan clock drift, atau pembatasan resource.
3. **Run Experiments in Production**: Sistem staging jarang memiliki kompleksitas topologi data dan variabilitas traffic yang identik dengan produksi.
4. **Automate Experiments to Run Continuously**: Integrasikan chaos testing ke dalam pipeline delivery.
5. **Minimize Blast Radius**: Mulai dari cakupan terkecil (1 pod / 1 canary region) dengan mekanisme pemutusan otomatis (*Automated Rollback / Circuit Breaker*) jika SLO terancam kolaps.

#### Taksonomi Injeksi Kegagalan (Chaos Primitives)
- **Latency Injection**: Menambahkan delay buatan pada paket data menggunakan Linux Traffic Control (`tc-netem`).
- **Packet Drop / Corruption**: Mensimulasikan jaringan flaky dengan menjatuhkan persentase paket tertentu di level socket kernel.
- **CPU / Memory Starvation**: Menghabiskan alokasi CPU time melalui *stress threads* atau mengonsumsi alokasi RAM hingga memicu mekanisme Linux Out-Of-Memory (OOM) Killer.

---

## 6. How
Implementasi end-to-end terbagi dalam 4 fase:

```
[Fase 1: Modeling & Baseline]
  ↳ Little's Law Sizing -> Locust/k6 Baseline Profile -> Metric Observability
[Fase 2: Target Capacity Validation]
  ↳ Constant Arrival Rate Load Test -> Profiling Saturation Curve (USL)
[Fase 3: Chaos Hypothesis & Guardrails]
  ↳ Define Steady State (SLO) -> Define Blast Radius -> Deploy Chaos Mesh CRD
[Fase 4: Game Day Orchestration]
  ↳ Inject Failure Under Load -> Observe Auto-remediation -> Post-Mortem & Fix
```

---

## 7. Analogy
Bayangkan sebuah jalan tol dengan gerbang pembayaran:
- **Little's Law**: Jika gerbang tol menerima 100 mobil per menit ($\lambda = 100$) dan setiap mobil butuh 30 detik ($W = 0{,}5\text{ menit}$) untuk transaksi kartu, maka secara stabil akan ada $100 \times 0{,}5 = 50$ mobil yang sedang berada di area loket pembayaran secara bersamaan ($L$).
- **Amdahl's Law**: Menambah 100 loket baru tidak akan membuat perjalanan pengendara 100x lebih cepat jika jembatan setelah loket tersebut hanya muat satu jalur mobil (*serial bottleneck*).
- **Chaos Testing**: Anda tidak menunggu badai salju terjadi di musim dingin untuk mengetahui apakah alat pembersih salju dan rantai ban mobil Anda berfungsi. Anda sengaja menyemprotkan air es ke jalanan tertutup pada dini hari untuk menguji sistem rem anti-selip (ABS) dan kesiapan tim derek darurat.

---

## 8. Diagram (ASCII)

### A. Kurva Saturasi Sistem Antrean (USE Method)
```
Latensi
 (W)
  ^                                             / (Asimtotik)
  |                                            /
  |                                           /
  |                                          /
  |                                         /
  |                                       /
  |                                     /
  |                                   /
  |                           _ - - ~ 
  |                 _ - - ~ ~ 
  + - - - - - - - ~----------------------------> Utilisasi (rho)
  0%            50%        70%    80%   90%   100%
                [Linear]       [Kritis] [Collapse / Starvation]
```

### B. Arsitektur Chaos Injection (Chaos Mesh Controller)
```
+-----------------------------------------------------------------------+
| Kubernetes Cluster                                                    |
|                                                                       |
|  +-----------------------+           +-----------------------------+  |
|  |   Chaos Dashboard /   |  Reconcile|   Chaos Mesh Controller     |  |
|  |     CRD Spec          | --------> |   (Validates & Schedules)   |  |
|  +-----------------------+           +-----------------------------+  |
|                                                     |                 |
|                                     gRPC RPC Call   v                 |
|  +-----------------------------------------------------------------+  |
|  | Target Node                                                     |  |
|  |                                                                 |  |
|  |  +---------------------+        +----------------------------+  |  |
|  |  |   Chaos Daemon      | -----> | Target Container Namespace |  |  |
|  |  |  (DaemonSet Pod)    | cgroup | - Injects tc netem latency |  |  |
|  |  |  (Runs as root)     | iptable| - Injects packet loss      |  |  |
|  |  +---------------------+ stress | - Spawns CPU hog process   |  |  |
|  |                                 +----------------------------+  |  |
|  +-----------------------------------------------------------------+  |
+-----------------------------------------------------------------------+
```

---

## 9. Simple Example

### Menghitung Konkurensi Target Aplikasi Menggunakan Python
Berikut kalkulasi Little's Law untuk penentuan ukuran Pod:

```python
# littles_law_calculator.py

def calculate_concurrency(target_rps: float, latency_seconds: float) -> float:
    """Menghitung Concurrency (L) = Arrival Rate (lambda) * Residence Time (W)"""
    return target_rps * latency_seconds

def calculate_pods_needed(target_rps: float, p95_latency_sec: float, pod_worker_threads: int) -> int:
    import math
    required_concurrency = calculate_concurrency(target_rps, p95_latency_sec)
    pods = math.ceil(required_concurrency / pod_worker_threads)
    return pods

rps = 8500.0          # Target: 8500 Request Per Detik
p95_latency = 0.120   # 120 milidetik = 0.12 detik
threads_per_pod = 64  # Kapasitas konkurensi aman pod

concurrency = calculate_concurrency(rps, p95_latency)
pods_required = calculate_pods_needed(rps, p95_latency, threads_per_pod)

print(f"Total Concurrent In-flight Requests : {concurrency:.2f}")
print(f"Minimum Pods Diperlukan            : {pods_required} Pods")
```

---

## 10. Practical Example (Konfigurasi CLI / Terraform / Kode Hands-on)

### A. Load Testing Script Bebas Coordinated Omission (k6)
Simpan konfigurasi sebagai `k6-arrival-rate-test.js`:

```javascript
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  scenarios: {
    constant_request_rate: {
      executor: 'constant-arrival-rate',
      rate: 1500, // 1500 RPS konstan
      timeUnit: '1s',
      duration: '5m',
      preAllocatedVUs: 100, // VU yang dialokasikan sejak awal
      maxVUs: 1000,         // Kemampuan ekspansi jika latensi sistem meningkat drastis
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],   // Error rate harus < 1%
    http_req_duration: ['p(95)<200'], // 95% request harus selesai di bawah 200ms
  },
};

export default function () {
  const url = 'http://payment-service.default.svc.cluster.local:8080/api/v1/checkout';
  const payload = JSON.stringify({
    userId: 'usr-89214',
    amount: 250000,
    timestamp: Date.now(),
  });

  const params = {
    headers: {
      'Content-Type': 'application/json',
      'X-GameDay-Exercise': 'Stage-2-Stress',
    },
    timeout: '3s',
  };

  const res = http.post(url, payload, params);

  check(res, {
    'status is 200 or 201': (r) => r.status === 200 || r.status === 201,
    'latency under SLA': (r) => r.timings.duration < 500,
  });
}
```

### B. Chaos Mesh Manifest: Injeksi Latensi Jaringan dan Starvasi CPU

#### 1. Injeksi Network Latency & Flakiness (`network-chaos.yaml`)
```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: NetworkChaos
metadata:
  name: payment-network-degradation
  namespace: chaos-testing
spec:
  action: delay
  mode: fixed
  value: '2' # Menargetkan tepat 2 pod pembayaran
  selector:
    namespaces:
      - production
    labelSelectors:
      app: payment-service
  delay:
    latency: '180ms'
    jitter: '40ms'
    correlation: '50'
  loss:
    loss: '3' # 3% packet drop
    correlation: '20'
  direction: to
  target:
    selector:
      namespaces:
        - production
      labelSelectors:
        app: account-ledger-db
    mode: all
  duration: '10m'
  scheduler:
    cron: '@every 30m'
```

#### 2. Injeksi CPU Starvation (`cpu-stress-chaos.yaml`)
```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: StressChaos
metadata:
  name: cart-service-cpu-burn
  namespace: chaos-testing
spec:
  mode: one
  selector:
    namespaces:
      - production
    labelSelectors:
      app: cart-service
  stressors:
    cpu:
      workers: 4
      load: 95 # Mengonsumsi 95% kuota CPU cgroup
  duration: '5m'
```

---

## 11. Real World Example
Sebuah unicorn platform perbankan digital di Asia Tenggara menghadapi lonjakan transaksi *Payday Sale*. Tim SRE mengamati insiden di mana API Gateway mengalami *cascading failure* saat database inti mengalami kenaikan latensi dari 15ms ke 350ms.

**Investigasi**:
- Berdasarkan **Little's Law**, saat latensi melompat dari 15ms ke 350ms ($23{,}3\times$), dengan traffic konstan 12.000 RPS, jumlah koneksi terbuka pada reverse proxy melompat dari $12.000 \times 0{,}015 = 180$ koneksi menjadi $12.000 \times 0{,}350 = 4.200$ koneksi simultan.
- Reverse proxy kehabisan batas *ephemeral socket port* (`net.ipv4.ip_local_port_range`) dan alokasi `max_connections` thread pool terlampaui.

**Solusi & Validasi Game Day**:
1. Mengubah konfigurasi timeouts, memasang *active connection pool sizing*, dan mengaktifkan *resilience pattern*: **Circuit Breaker** (Resilience4j) dengan status *half-open* agresif.
2. Menggelar skenario **Game Day**: Menginjeksi latensi 400ms menggunakan Chaos Mesh pada downstream database mock service di bawah beban lalu lintas 15.000 RPS dari k6.
3. **Hasil**: Circuit breaker memutus koneksi dalam 1,2 detik setelah latensi melonjak, mengembalikan respon HTTP 429/Fallback Cache kepada 30% user sekunder, sementara 70% transaksi core tetap berjalan tanpa membuat gateway kolaps. SLO ketersediaan 99.95% tercapai.

---

## 12. Trade-offs

| Aspek | Agresif / Over-Provisioning | Presisi / Dynamic Scaling | Analisis Trade-off |
| :--- | :--- | :--- | :--- |
| **Kapasitas CPU/RAM** | Alokasi Resource Limits tinggi (Headroom 100%) | Target utilisasi optimal 70-80% via HPA & VPA | Over-provisioning meminimalkan latensi namun membuang jutaan rupiah biaya komputasi idle; dynamic scaling butuh waktu reaksi (*cold-start* pod). |
| **Chaos Testing** | Full Chaos di Produksi langsung | Chaos di Staging / Sandbox Cluster | Pengujian staging minim risiko dampak user namun sering memberikan *false sense of security*; chaos produksi berisiko merusak real revenue jika blast radius gagal dibatasi. |
| **Load Testing** | Concurrency-based Virtual Users (VU) | Constant Arrival Rate Scheduling | Model VU rentan terhadap bias *Coordinated Omission*; Arrival Rate membutuhkan node injektor beban yang jauh lebih besar dan terkontrol ketat. |

---

## 13. When To Use
- Terapkan **Capacity Planning Matematis** ketika merencanakan migrasi kluster, peluncuran produk berskala nasional (*Flash Sale / Promo*), atau penganggaran infrastruktur tahunan (*Capex/Opex forecasting*).
- Terapkan **Amdahl's/USL Modeling** saat arsitektur monolitik mulai dipecah menjadi microservices untuk mengevaluasi apakah biaya serialisasi RPC antar-service melampaui keuntungan pemisahan komputasi.
- Terapkan **Chaos Engineering** saat Anda memiliki sistem terdistribusi multi-node dengan autoscaling, multi-AZ deployment, atau database replikasi yang secara teori dirancang untuk *failover* mandiri.

---

## 14. When NOT To Use
- **Jangan jalankan Chaos Engineering jika sistem belum memiliki Baseline Observability**: Jika Anda tidak memiliki metrik latensi p99, log terpusat, atau tracing terdistribusi, injeksi kekacauan hanya akan memicu pemadaman tanpa insight yang dapat ditindaklanjuti.
- **Jangan jalankan Chaos Testing tanpa SLO dan Alerting**: Jika tidak ada tim yang dapat mendeteksi kegagalan secara real-time, pengujian tersebut bukan eksperimen keandalan melainkan sabotase operasional.
- **Hindari Capacity Modeling Rumit untuk Sistem Stateless Sepele**: Jika aplikasi hanya memproses batch data mingguan non-kritis di mana waktu eksekusi fleksibel, tuning matematis queuing theory berlebih adalah bentuk *premature optimization*.

---

## 15. Common Mistakes
1. **Mengabaikan Coordinated Omission**: Menggunakan tool load testing sederhana yang mencatat p99 rendah saat server sebenarnya mengalami *hang* atau *freezing*.
2. **Ketergantungan pada Metrik Rata-rata (Mean/Average Latency)**: Rata-rata menyembunyikan penderitaan p99 dan p99.9 user. Dalam 1.000 transaksi, 10 user yang mengalami latensi 10 detik tetap dapat menghasilkan rata-rata yang tampak bagus padahal merusak reputasi platform.
3. **Mengabaikan Blast Radius pada Chaos Injection**: Menjalankan eksperimen kegagalan jaringan di namespace produksi tanpa label selector yang presisi, mengakibatkan database inti satu kluster terputus secara global.
4. **Asumsi Skalabilitas Linier**: Menganggap menduplikasi jumlah Pod dari 10 ke 20 akan otomatis melipatgandakan throughput 2x lipat tanpa memverifikasi batasan *IOPS database, locking, dan bandwidth switch pod network*.
5. **Mengabaikan Cold Start dan Metric Scrape Delay**: Pengujian beban yang dinaikkan instan dari 0 ke 100.000 RPS dalam 2 detik akan selalu menjebol HPA, karena metric pipeline Prometheus + HPA polling loop memerlukan waktu 30-60 detik untuk mendeteksi saturasi dan menjadwalkan pod baru.

---

## 16. Best Practices
- **Wajibkan Automated Rollback (Dead Man's Switch)**: Konfigurasikan setiap eksperimen Chaos Mesh dengan batas waktu eksekusi tegas (`duration`) dan integrasikan webhook ke Prometheus Alertmanager agar pengujian berhenti seketika saat error rate SLO terlewati.
- **Terapkan Model Constant Arrival Rate pada Load Test**: Validasi ketahanan sistem terhadap volume throughput riil per detik, bukan berdasarkan seberapa cepat injector menerima respon balik.
- **Gunakan Pendekatan Step-Load Testing**: Naikkan trafik secara bertahap (Ramping Phase): 25% -> 50% -> 75% -> 100% -> 120% (Stress Phase) untuk mengidentifikasi kurva 'lutut' (*the knee of the curve*) di mana waktu respons mulai lepas kendali.
- **Kombinasikan Chaos dengan Load Testing Bersamaan**: Injeksi kegagalan jaringan atau pod termination tidak ada artinya pada kluster idle. Jalankan chaos injection *persis saat* beban kerja sistem berada pada tingkat puncak simulasi.

---

## 17. Troubleshooting
Panduan langkah identifikasi masalah saat eksperimen gagal terkendali:

```
Masalah: Sistem Mengalami Cascading Failure Tak Terkendali Selama Eksperimen
  │
  ├── 1. Hentikan Segera Eksperimen (Rollback)
  │      └── Jalankan: kubectl delete networkchaos,stresschaos --all -A
  │
  ├── 2. Verifikasi Apakah Pod Masih Terjebak di Network Filter (iptables/tc)
  │      └── Masuk ke Node Worker Target:
  │            sudo tc qdisc show dev eth0
  │            sudo iptables -L -n -v | grep -i chaos
  │      └── Bersihkan sisa rule manual jika daemonset gagal cleanup:
  │            sudo tc qdisc del dev eth0 root
  │
  ├── 3. Evaluasi Antrean Connection Pool Downstream
  │      └── Periksa koneksi TCP CLOSE_WAIT / TIME_WAIT:
  │            ss -s
  │            netstat -tan | awk '{print $6}' | sort | uniq -c
  │
  └── 4. Evaluasi HPA Thrashing / Flapping
         └── Cek event autoscaler:
               kubectl describe hpa <service-name>
         └── Tinjau metrik: kube_horizontalpodautoscaler_status_current_replicas
```

---

## 18. Exercise
Selesaikan skenario berikut secara mandiri:
1. **Analisis Little's Law**: 
   - Service checkout memproses 4.000 RPS.
   - P99 Latency saat ini adalah 250ms.
   - Setiap kontainer memiliki worker pool maksimal 50 concurrent connection.
   - *Tugas*: Hitung berapa active connection yang berjalan di sistem dan berapa jumlah pod minimum yang harus dialokasikan agar pool tidak mengalami *exhaustion*.
2. **Kalkulasi Amdahl**:
   - Algoritma pemrosesan gambar memiliki 35% segmen kode yang mutlak berjalan serial karena membaca file dari persistent volume terenkripsi.
   - Berapa *theoretical maximum speedup* yang bisa diraih jika pod ditingkatkan dari 2 CPU core menjadi 32 CPU core?

---

## 19. Challenge
Rancang arsitektur pengujian otomatis dalam pipeline CI/CD:
- Bangun sebuah GitHub Actions / GitLab CI pipeline yang melakukan deployment ephemeral environment di Kubernetes.
- Jalankan k6 test dengan 5.000 RPS.
- Tepat di menit ke-2, picu Chaos Mesh API untuk menginjeksi 15% network packet loss pada dependensi cache Redis.
- Validasi apakah fallback ke Database lokal tetap menjaga error rate di bawah 2% dan p95 latensi di bawah 400ms.
- Batalkan deployment dan tandai pipeline *FAIL* jika sistem tidak mampu pulih (*self-healing*) dalam waktu kurang dari 60 detik pasca injeksi dihentikan.

---

## 20. Summary
- **Capacity Planning** bukan tebak-tebakan kapasitas hardware; ini adalah penerapan kalkulasi matematis probabilitas antrean (*Little's Law, USL, USE Method*) untuk memprediksi titik jenuh sistem.
- Skalabilitas tidak bersifat linier tak terbatas; batasan serialisasi dan penalti sinkronisasi data antar-node (**Amdahl's Law**) membatasi efisiensi penambahan resource secara horizontal.
- **Load Testing** modern wajib memperhitungkan bahaya *Coordinated Omission* dengan memanfaatkan skenario *constant-arrival-rate*.
- **Chaos Engineering** mengubah spekulasi ketahanan menjadi pembuktian empiris. Melalui injeksi terukur pada latensi, jaringan, dan saturasi CPU yang dibatasi oleh mitigasi blast radius yang ketat, SRE memastikan ketahanan sistem terhadap skenario kegagalan dunia nyata.