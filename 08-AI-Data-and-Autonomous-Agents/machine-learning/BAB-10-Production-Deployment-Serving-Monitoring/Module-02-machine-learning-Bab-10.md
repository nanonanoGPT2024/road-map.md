# Kurikulum Rekayasa Perangkat Lunak & Sistem AI Enterprise
## Kategori: 08-AI-Data-and-Autonomous-Agents
### Topik: Machine Learning
#### Bab 10: Production Deployment, Serving & Monitoring
#### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta didik pada level Senior/Staff Engineer diharapkan mampu:
- **Menganalisis dan Memilih Engine Inferensi Kinerja Tinggi:** Mengonfigurasi dan mengoperasikan *inference serving engine* tingkat lanjut (seperti NVIDIA Triton Inference Server dan ONNX Runtime) menggunakan komunikasi gRPC berkinerja tinggi serta *zero-copy memory sharing*.
- **Merancang Dynamic Batching & Concurrency Scheduling:** Mengonfigurasi penjadwalan *dynamic batching*, *model concurrency instances*, dan *CUDA stream pipelines* untuk memaksimalkan saturasi GPU/TPU tanpa melanggar Service Level Objective (SLO) latensi p99.
- **Mengimplementasikan Strategi Deployment Lanjutan:** Merancang arsitektur *Canary Rollout*, *A/B Testing*, dan *Shadow Traffic Routing* menggunakan Service Mesh (Envoy/Istio) pada klaster Kubernetes tanpa menambah latensi inferensi.
- **Membangun Sistem Deteksi Data & Concept Drift:** Mengimplementasikan pipeline monitoring statistik non-parametrik (Kolmogorov-Smirnov Test, Population Stability Index, dan Wasserstein Distance) secara streaming dan batch untuk mendeteksi *covariate shift* dan *concept drift*.
- **Menangani Degradasi & Failover:** Merancang sirkuit pemutus (*circuit breaker*), mekanisme *graceful degradation* (misal: *fallback* ke model heuristik linier), dan orkestrasi *auto-rollback* berbasis anomali metrik produksi.

---

### 2. Prerequisites
Untuk menyerap materi ini secara optimal, peserta harus menguasai:
- **Sistem Operasi & Hardware Interfacing:** Pemahaman mendalam tentang POSIX thread, CUDA stream, interaksi PCI-Express (PCIe Gen4/Gen5 bandwidth limits), *host-to-device memory copy* ($H2D/D2H$), dan manajemen Unified Virtual Memory (UVM).
- **Jaringan & RPC:** Protokol HTTP/2, Protobuf, gRPC stream architectures, dan manajemen koneksi TCP multiplexing.
- **Matematika & Teori Probabilitas Terapan:**
  - *Empirical Cumulative Distribution Functions* (eCDF).
  - Two-sample hypothesis testing ($p$-values, $\alpha$-thresholds).
  - Information theory: Relative Entropy / Kullback-Leibler (KL) Divergence dan Jensen-Shannon Divergence.
- **Containerization & Orchestration:** Kubernetes primitives (Custom Resource Definitions, Pod Disruption Budgets, HPA berbasis custom Prometheus metrics).

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. Arsitektur Internal Serving Engine: Dynamic Batching & CUDA Streams
Menjalankan inferensi model dengan membungkusnya dalam web server WSGI/ASGI Python standar (seperti Gunicorn + FastAPI) memiliki kelemahan arsitektural: *Python Global Interpreter Lock* (GIL) contention, *high-overhead serialization*, serta ketidakmampuan menjadwalkan utilisasi tensor core GPU secara adaptif.

```
Request Queue              Dynamic Batch Scheduler             GPU Execution Engine
[Req 1 (t=0ms)]  ──┐
[Req 2 (t=1ms)]  ──┼──>  [Koleksi Tensor dalam Window: Δt] ──>  [Merger Tensor: Batch N]
[Req 3 (t=3ms)]  ──┘     Kriteria: Max Queue Delay OR Max Size    │ (CUDA Stream 1)
                                                                  ▼
                                                            [Tensor Core Matrix Mul]
                                                                  │
[Res 1, 2, 3]    <────── [Demultiplexing Output Slices] <─────────┘
```

Dedicated Inference Server (seperti Triton) mengabstraksi eksekusi model melalui pipeline multi-threaded C++ murni:
1. **Request Queue Management:** Tiap model memiliki antrean permintaan inferensi independen yang bersifat *lock-free* atau berbasis *low-contention ring-buffers*.
2. **Dynamic Batch Scheduler:** Scheduler menahan request pertama yang masuk selama interval waktu maksimal ($\Delta t$ *max_queue_delay_microseconds*). Jika akumulasi request mencapai *max_batch_size* sebelum $\Delta t$ tercapai, batch langsung dieksekusi. Jika batas waktu tercapai, scheduler mengeksekusi berapapun request yang terkumpul dalam antrean parsial.
3. **Penyalinan Memori Zero-Copy via IPC System V / POSIX Shared Memory:** Jika klien berada pada host fisik atau node K8s yang sama, tensor input/output tidak dikirimkan melalui loopback socket TCP/IP, melainkan dipetakan (*memory-mapped*) langsung ke virtual address space Triton, meniadakan *copying overhead*.
4. **Eksekusi CUDA Stream Paralel:** Engine mengalokasikan beberapa instans model yang identik pada GPU yang sama. Masing-masing instans mengeksekusi inferensi pada *CUDA Stream* yang berbeda, memungkinkan overlapping antara operasi komputasi (GEMM kernels) dan transfer data I/O ($H2D$/$D2H$).

#### B. Teori Pergeseran Distribusi (Data & Concept Drift)
Dalam sistem inferensi produksi, performa model dapat terdegradasi secara silently tanpa menghasilkan *runtime exception*.

- **Covariate Shift ($P(X_{\text{inference}}) \neq P(X_{\text{training}})$):** Distribusi fitur input berubah, namun fungsi pemetaan bersyarat $P(Y|X)$ tetap konstan.
- **Concept Drift ($P(Y|X_{\text{inference}}) \neq P(Y|X_{\text{training}})$):** Hubungan kausal atau korelasi antara input $X$ dan target $Y$ bergeser (misal: pola transaksi penipuan baru yang sengaja mengelabui model deteksi fraud).

Untuk mendeteksi *Covariate Shift* secara terukur tanpa label kebenaran (*ground truth labels*) yang tertunda, kita menggunakan dua instrumen statistik:

1. **Kolmogorov-Smirnov (KS) Test (Fitur Kontinu/Numerik):**
   Uji non-parametrik dua sampel yang mengukur deviasi absolut maksimum antara dua fungsi distribusi kumulatif empiris ($F_{\text{ref}}$ dan $F_{\text{prod}}$):
   $$D = \sup_x |F_{\text{ref}}(x) - F_{\text{prod}}(x)|$$
   Hipotesis nol ($H_0$) ditolak jika nilai $D > c(\alpha) \sqrt{\frac{n_1 + n_2}{n_1 n_2}}$, mengindikasikan adanya drift.

2. **Population Stability Index (PSI) (Fitur Kategorikal atau Binned Continuous):**
   Menghitung divergensi simetris antara distribusi referensi ($B_{\text{actual}}$) dan target produksi ($B_{\text{expected}}$) pada $K$ bins:
   $$\text{PSI} = \sum_{k=1}^K \left( P_k - Q_k \right) \times \ln\left(\frac{P_k}{Q_k}\right)$$
   di mana $P_k = \frac{\text{prod}_k}{N_{\text{prod}}}$ dan $Q_k = \frac{\text{ref}_k}{N_{\text{ref}}}$.
   - $\text{PSI} < 0.1$: Tidak ada perubahan signifikan (*No Drift*).
   - $0.1 \le \text{PSI} < 0.25$: Terjadi pergeseran moderat (*Moderate Drift*), sistem harus memberikan peringatan untuk evaluasi.
   - $\text{PSI} \ge 0.25$: Terjadi pergeseran drastis (*Significant Drift*), memicu peringatan darurat dan orkestrasi pelatihan ulang (*retraining*).

---

### 4. Why & What

| Dimensi | Pendekatan Naive (Flask / FastAPI) | Pendekatan Enterprise (Triton / ONNX Runtime + Istio) |
| :--- | :--- | :--- |
| **Throughput & Concurrency** | Terhambat oleh CPython GIL; 1 request memblokir 1 CPU worker/GPU lock context. | Antrean multi-threaded C++; GPU memproses multi-instance concurrent streams secara serentak. |
| **GPU Utilization** | Rendah (< 25%), GPU sering *idle* menunggu latensi HTTP parsing dan de-serialisasi data. | Sangat Tinggi (75-95%) melalui *dynamic batching scheduler* dan memori *pinned host*. |
| **Deployment Safety** | All-or-nothing (downtime restart) atau rolling-update standar yang buta terhadap drift performa model. | *Shadow mirroring* (0% blast-radius testing), Canary traffic splitting via Layer-7 dynamic weighting. |
| **Monitoring Observability** | Terbatas pada system metrics standar (CPU, RAM, HTTP Error Rate). | Deep Model Observability: Latensi per-layer, tensor queue delay, $p99$ tail inference, PSI drift continuous profiling. |

---

### 5. How (Workflow Detail)

Arsitektur siklus inferensi produksi enterprise diatur dalam urutan berikut:

1. **Model Optimization & Serialization:** Model dilatih di PyTorch/TensorFlow, kemudian dibekukan (*freeze*) dan diekspor ke representasi intermediate (ONNX). Graph dioptimalkan (Constant Folding, Layer Fusion) dan dikonversi ke engine TensorRT (FP16/INT8 precision dengan calibration cache).
2. **Model Repository Deployment:** Model binary diletakkan di distributed object store (misal: S3/GCS) dengan metadata schema yang ketat (`config.pbtxt`).
3. **Traffic Splitting / Shadow Ingress:**
   - Klien mengirim payload inference via gRPC/HTTP/2 ke Service Ingress Gateway (Envoy).
   - Envoy mereplikasi traffic: 100% dialirkan ke Model v1 (Active), dan salinan identik (*asynchronous shadow clone*) dialirkan ke Model v2 (Candidate) tanpa memblokir response ke klien.
4. **Execution & Hardware Scheduler:** Worker Triton menerima request, memasukkannya ke antrean batch dinamis, menyalin tensor ke GPU melalui pinned memory, dan memicu eksekusi kernel via CUDA stream.
5. **Real-time Telemetry & Asynchronous Drift Logging:**
   - Triton meng-expose OpenMetrics format ke Prometheus (latensi inferensi, waktu antrean).
   - Sample tensor input/output dikirim secara asynchronous via message broker (Kafka/Redpanda) menuju Drift Detection Worker.
6. **Automated Governance Loop:** Drift engine menjalankan KS-Test/PSI secara berkala terhadap baseline training. Jika anomali terdeteksi melebihi ambang batas risiko, webhook dikirimkan ke Kubernetes Control Plane untuk menurunkan bobot Canary ke 0% dan mengaktifkan fallback circuit breaker.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Gerbang Tol Cerdas (Dynamic Batching) & Quality Control Paralel
Bayangkan loket gerbang tol konvensional di mana satu mobil dilayani satu per satu oleh satu petugas (FastAPI). Mobil besar dan kecil harus menunggu antrean individual secara sekuensial. 

*Dynamic Batching Engine* adalah gerbang tol pintar yang memiliki area tunggu mini. Ketika sebuah kendaraan masuk, sistem menunggu hingga 3 milidetik: jika ada 7 mobil lain yang tiba, ke-8 mobil tersebut digandengkan ke sebuah platform pendorong hidrolik berkecepatan tinggi dan dilesatkan serentak melalui lintasan super lebar (Tensor Core GPU). 

Sementara itu, kamera pengawas (Monitoring Drift Engine) memindai dimensi setiap mobil yang lewat secara real-time. Jika tiba-tiba 80% mobil yang lewat adalah truk tronton (padahal jalan didesain untuk sedan—*Data Drift*), sirene darurat berbunyi untuk mengalihkan rute jalan sebelum aspal hancur (*Degradation/Crash*).

#### Diagram Arsitektur Produksi

```
[ Client Applications: Web / Mobile / IoT ]
                   │
                   ▼ (gRPC / HTTP/2 - Public Ingress)
┌─────────────────────────────────────────────────────────────┐
│                 Envoy Ingress Gateway (Service Mesh)        │
│    - Route: 90% Primary (v1) | 10% Canary (v2)               │
│    - Shadow Copy: 100% Mirroring -> Experimental (v3)       │
└──────────────┬───────────────────────────────┬──────────────┘
               │                               │
    [Primary Target]                   [Shadow / Canary]
               │                               │
               ▼                               ▼
┌─────────────────────────────────────────────────────────────┐
│       Kubernetes Cluster: Triton Inference Server Pods      │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ C++ Core Engine & Dynamic Batch Scheduler             │  │
│  │                                                       │  │
│  │   Queue [R1][R2][R3] ──> Batch (Size: 3, Timeout: 2ms)│  │
│  │                            │                          │  │
│  │                            ▼                          │  │
│  │   CUDA Stream 0   [ TensorRT Engine: Instance 1 ]     │  │
│  │   CUDA Stream 1   [ TensorRT Engine: Instance 2 ]     │  │
│  │                            │                          │  │
│  │   GPU Hardware Memory (Pinned VRAM / Tensor Cores)    │  │
│  └────────────────────────────┬──────────────────────────┘  │
└───────────────────────────────┼─────────────────────────────┘
                                │
          ┌─────────────────────┴────────────────────┐
          │ (Async Payload Streaming)                │ (Prometheus Scrape)
          ▼                                          ▼
┌──────────────────┐                       ┌──────────────────┐
│ Apache Kafka Bus │                       │ Prometheus /     │
└─────────┬────────┘                       │ Grafana Engine   │
          │                                └──────────────────┘
          ▼
┌─────────────────────────────────────────────────────────────┐
│ Drift & Statistical Anomaly Evaluator (Evidently / Custom)  │
│  - Continuous Two-Sample Kolmogorov-Smirnov Test            │
│  - Population Stability Index (PSI) Engine                  │
│                                                             │
│  [Drift Alert Trigger] ──> (Kubernetes Webhook: Rollback)   │
└─────────────────────────────────────────────────────────────┘
```

---

### 7. Simple Example & Practical Example

#### A. Konfigurasi Triton Inference Server (`config.pbtxt`)
Berikut adalah konfigurasi produksi dengan optimasi *dynamic batching* dan multi-instance execution pada platform GPU.

```protobuf
name: "fraud_detection_xgboost"
platform: "onnxruntime_onnx"
max_batch_size: 128

input [
  {
    name: "input_features"
    data_type: TYPE_FP32
    dims: [ 45 ]
  }
]

output [
  {
    name: "probabilities"
    data_type: TYPE_FP32
    dims: [ 2 ]
  }
]

# Optimasi Dynamic Batching
dynamic_batching {
  max_queue_delay_microseconds: 3000
  preferred_batch_size: [ 16, 32, 64, 128 ]
}

# Multi-instance execution: 2 instance pada GPU 0 untuk saturasi compute core
instance_group [
  {
    count: 2
    kind: KIND_GPU
    gpus: [ 0 ]
  }
]

# Optimasi Akselerasi Runtime
optimization {
  execution_accelerators {
    gpu_execution_accelerator : [ {
      name : "tensorrt"
      parameters { key: "precision_mode" value: "FP16" }
      parameters { key: "max_workspace_size_bytes" value: "1073741824" }
    }]
  }
}
```

#### B. Client Inferensi Asinkron Berkinerja Tinggi & Deteksi Drift Real-Time (Python)
Kode ini mengimplementasikan pemanggilan inferensi asinkron melalui gRPC client Triton, pelaporan metrik latensi, dan kalkulator metrik PSI (*Population Stability Index*) secara in-memory.

```python
import numpy as np
import tritonclient.grpc.aio as grpcclient
from tritonclient.utils import InferenceServerException
import asyncio
import time
from typing import Dict, Tuple, List


class DriftMetricsEvaluator:
    """
    Evaluator statistik untuk menghitung Population Stability Index (PSI)
    secara real-time antara baseline training dan live serving window.
    """
    @staticmethod
    def calculate_psi(expected: np.ndarray, actual: np.ndarray, num_bins: int = 10) -> float:
        """
        Menghitung Population Stability Index (PSI) untuk 1D array.
        expected: Data baseline pelatihan
        actual: Data produksi terkini
        """
        # Validasi ukuran data
        if len(expected) == 0 or len(actual) == 0:
            raise ValueError("Distribusi data tidak boleh kosong.")

        # Tentukan batas quantile dari data referensi (expected)
        quantiles = np.linspace(0, 100, num_bins + 1)
        bins = np.percentile(expected, quantiles)
        bins[0] = -np.inf
        bins[-1] = np.inf

        # Frekuensi pengamatan pada masing-masing bin
        expected_counts, _ = np.histogram(expected, bins=bins)
        actual_counts, _ = np.histogram(actual, bins=bins)

        # Normalisasi ke fraksi probabilitas dengan Laplace smoothing konstan
        eps = 1e-4
        expected_pct = (expected_counts / len(expected)) + eps
        actual_pct = (actual_counts / len(actual)) + eps

        # Normalisasi ulang agar total integral probabilitas = 1
        expected_pct /= np.sum(expected_pct)
        actual_pct /= np.sum(actual_pct)

        # Rumus Matematis Standar PSI
        psi_value = np.sum((actual_pct - expected_pct) * np.log(actual_pct / expected_pct))
        return float(psi_value)


class ProductionTritonClient:
    def __init__(self, server_url: str = "localhost:8001"):
        self.server_url = server_url
        self.triton_client = None

    async def connect(self):
        self.triton_client = grpcclient.InferenceServerClient(url=self.server_url)

    async def close(self):
        if self.triton_client:
            await self.triton_client.close()

    async def infer(self, model_name: str, input_tensor: np.ndarray) -> np.ndarray:
        """
        Menjalankan asynchronous inference gRPC dengan validasi input tensor.
        """
        if not self.triton_client:
            raise RuntimeError("Client gRPC belum diinisialisasi. Panggil `connect()` terlebih dahulu.")

        inputs = [grpcclient.InferInput("input_features", input_tensor.shape, "FP32")]
        inputs[0].set_data_from_numpy(input_tensor)

        outputs = [grpcclient.InferRequestedOutput("probabilities")]

        start_time = time.perf_counter()
        response = await self.triton_client.infer(
            model_name=model_name,
            inputs=inputs,
            outputs=outputs
        )
        latency_ms = (time.perf_counter() - start_time) * 1000.0

        # Ekstraksi output
        result_array = response.as_numpy("probabilities")
        return result_array, latency_ms


# Contoh Eksekusi Integrasi
async def main():
    client = ProductionTritonClient("localhost:8001")
    # Inisialisasi koneksi asinkron (Mock/Real)
    # Drift baseline mock (distribusi fitur tertentu pada training set)
    training_baseline_feature = np.random.normal(loc=0.0, scale=1.0, size=50000)
    
    # 1. Mensimulasikan data produksi normal (No drift)
    live_production_normal = np.random.normal(loc=0.02, scale=0.98, size=5000)
    psi_normal = DriftMetricsEvaluator.calculate_psi(training_baseline_feature, live_production_normal)
    print(f"[*] Baseline vs Normal Traffic - PSI: {psi_normal:.4f}")
    assert psi_normal < 0.1, "Harusnya stabil tanpa drift."

    # 2. Mensimulasikan data produksi mengalami Covariate Shift drastis (Mean Shift)
    live_production_drifted = np.random.normal(loc=0.75, scale=1.3, size=5000)
    psi_drifted = DriftMetricsEvaluator.calculate_psi(training_baseline_feature, live_production_drifted)
    print(f"[!] Baseline vs Shifted Traffic - PSI: {psi_drifted:.4f}")
    
    if psi_drifted >= 0.25:
        print("[CRITICAL ALERT] Terjadi pergeseran distribusi ekstrem (PSI >= 0.25)! Memicu auto-rollback/alerting webhook.")

if __name__ == "__main__":
    asyncio.run(main())
```

---

### 8. Real World Case Study (Enterprise Scale)

**Kasus:** Sistem Deteksi Fraud Transaksi Finansial Tier-1 Bank Global.
- **SLA & SLO:** $65,000\text{ QPS}$ pada jam sibuk, latency constraint: $p99 \le 12\text{ milidetik}$, $p99.9 \le 20\text{ milidetik}$.
- **Masalah Awal:** Menggunakan arsitektur microservice Python (FastAPI + Gunicorn workers). Server mengalami *thread starvation* ketika traffic melonjak melampaui $15,000\text{ QPS}$. Latensi $p99$ meledak hingga $>180\text{ ms}$, memaksa sistem pembayaran men-trigger *bypass rules* yang meningkatkan kerugian transaksi penipuan hingga $2.4\text{ Juta USD}$.
- **Solusi Arsitektural Terapan:**
  1. *Model Conversion:* Export model Deep Learning (Autoencoder + GBDT) ke format Open Neural Network Exchange (ONNX), lalu dikompilasi menggunakan TensorRT 8 dengan kuantisasi FP16.
  2. *Inference Serving Cluster:* Migrasi ke klaster NVIDIA Triton Inference Server di atas Kubernetes (EKS) yang didukung instance multi-GPU (NVIDIA A100 SXM4).
  3. *Tuning Dynamic Batching:* Disetel `max_queue_delay_microseconds: 2500` (2.5 ms) dan `max_batch_size: 64`.
  4. *Traffic Routing:* Menggunakan Envoy Service Mesh untuk melakukan *Dark Traffic Launching* (Shadowing) model generasi baru selama 14 hari penuh.
  5. *Streaming Drift Monitor:* Mengintegrasikan Kafka consumer yang mengambil $1\%$ sampel inferensi untuk diuji menggunakan Kolmogorov-Smirnov test terhadap continuous feature.
- **Hasil:**
  - Utilisasi GPU meningkat dari $18\%$ menjadi $82\%$.
  - Kapasitas klaster mampu menangani $85,000\text{ QPS}$ tanpa degradasi.
  - Latensi $p99$ terpangkas menjadi $8.4\text{ ms}$ (turun lebih dari $95\%$).
  - Terdeteksi 1 kasus data pipeline upstream corruption berkat alert Kolmogorov-Smirnov test dalam 15 menit pasca-deployment, mencegah *false rejection* transaksi senilai jutaan dolar.

---

### 9. Trade-offs

```
                  Latensi Rendah (Low Latency)
                           ▲
                          ╱ ╲
                         ╱   ╲
                        ╱     ╲
                       ╱       ╲
                      ╱  Sistem ╲
                     ╱   Ideal   ╲
                    ╱             ╲
  Throughput Tinggi ─────────────── Biaya Infrastruktur
  (High Throughput)                 Rendah (Low Cost)
```

1. **Throughput vs. Latency (Tuning Max Queue Delay):**
   - *Pendekatan:* Menaikkan `max_queue_delay_microseconds` (misal dari $1\text{ ms}$ ke $10\text{ ms}$) memberi kesempatan scheduler mengumpulkan batch yang lebih besar.
   - *Trade-off:* Throughput keseluruhan (total inference per second) melonjak hingga $300\%$, namun latensi individu ($p99$) meningkat secara linier sebesar waktu delay. Jika target Anda adalah microservice sinkronus checkout, delay harus dibatasi $< 3\text{ ms}$.

2. **Precision vs. Latency/Memory (FP32 vs FP16 vs INT8 Quantization):**
   - *FP32:* Akurasi penuh matematis, tetapi konsumsi VRAM besar dan throughput Tensor Core terbatas.
   - *INT8:* Throughput komputasi naik hingga $2-4\times$ lipat, VRAM turun drastis hingga $75\%$, namun membutuhkan *calibration dataset* representatif. Risiko kesalahan numerik (*underflow/overflow*) tinggi pada layer tertentu yang dapat menyebabkan degradasi metrik bisnis jika tidak divalidasi ketat.

3. **In-Memory Synchronous Drift Checking vs. Asynchronous Decoupled Evaluation:**
   - *Synchronous (Dalam Pipeline Inferensi):* Drift terdeteksi seketika pada setiap request, namun latensi inference membengkak drastis ($+15-50\text{ ms}$) karena komputasi uji statistik.
   - *Asynchronous (via Broker Kafka/Redpanda):* Menjaga latensi inferensi inti tetap pada level sub-10ms, namun menciptakan *detection lag* selama rentang waktu agregasi data window ($1-5\text{ menit}$). Untuk skala enterprise, arsitektur asynchronous adalah satu-satunya pilihan yang layak.

---

### 10. Common Mistakes & Troubleshooting

#### 1. Kesalahan Fatal: CUDA Out-of-Memory (OOM) Akibat Unbounded Dynamic Batching
- **Penyebab:** Menyeting `max_batch_size` terlalu besar tanpa menghitung alokasi memori internal TensorRT workspace dan activation buffers.
- **Deteksi:** Triton pod crash dengan status code `137` atau error log `CUDA failure: out of memory`.
- **Solusi:** Hitung batas VRAM secara deterministik:
  $$\text{VRAM}_{\text{total}} \ge \text{Model Weights} + \text{Workspace Size} + (\text{Max Batch Size} \times \text{Max Sequence Length} \times \text{Activation Memory per Sample} \times \text{Instance Count})$$

#### 2. Bottleneck Serialisasi Python pada Triton Custom Python Backend
- **Penyebab:** Menjalankan pra-pemrosesan (seperti regex tokenization atau resizing citra) di dalam Python backend Triton. Python backend menggunakan single-process IPC default yang mengalami kontensi serialization ketika mem-passing payload antar container memory.
- **Solusi:** Pindahkan seluruh logika pra-pemrosesan citra/teks ke C++ custom backend, gunakan DALI (*Data Loading and Augmentation Library*), atau konversi pipeline preprocessing menjadi graph ONNX native menggunakan library seperti `skl2onnx` atau `tf.data`.

#### 3. Fenomena False-Positive pada Uji Kolmogorov-Smirnov (KS-Test)
- **Penyebab:** Menjalankan KS-test pada ukuran sampel produksi yang luar biasa besar (misal $N > 500,000$). Dalam teori statistika, dengan ukuran sampel masif, deviasi yang amat kecil dan tidak relevan terhadap performa model akan tetap menghasilkan $p\text{-value} \approx 0.0$ ($H_0$ ditolak).
- **Solusi:** Gunakan sub-sampling acak (misal $N=5,000$) untuk pengujian KS harian berulang, atau beralih menggunakan metrik berbasis magnitude efek seperti *Wasserstein Distance* (Earth Mover's Distance) atau *Population Stability Index* (PSI) dengan threshold praktis ($0.1$ / $0.25$).

---

### 11. Best Practices (Production Checklist)

#### Pra-Deployment (Staging & Build Pipeline)
- [ ] Model graph telah melalui optimasi layer fusion dan diekspor ke runtime format terkompilasi (ONNX/TensorRT).
- [ ] Eksekusi profiling latensi menggunakan tooling resmi seperti `perf_analyzer` dari NVIDIA untuk memetakan kurva saturation: Concurrency vs Throughput vs Latency.
- [ ] Baseline dataset untuk drift detection telah di-freeze, diverifikasi distribusinya, dan disimpan di metadata store (MLflow/Weights & Biases).
- [ ] Graceful termination handling: Pod menangani signal `SIGTERM` dengan menyelesaikan batch yang sedang berjalan sebelum shutdown (`terminationGracePeriodSeconds: 60`).

#### Arsitektur Serving & Infrastruktur
- [ ] Dynamic batching window dikalibrasi agar antrean tidak melanggar limit $p99$ SLO latensi.
- [ ] Shared memory (`/dev/shm`) pada pod Kubernetes dialokasikan dengan ukuran memadai (minimum $2\text{ GB}$ atau disamakan dengan memory limit pod) untuk mencegah IPC truncation.
- [ ] Health checking terpisah secara granular: Endpoint readiness (`/v2/health/ready`) harus memvalidasi kesiapan GPU, liveness (`/v2/health/live`) hanya memvalidasi proses internal server.
- [ ] Instance Group didistribusikan secara optimal melintasi kartu GPU independen, membatasi instance per GPU untuk mencegah thrashing memory cache.

#### Monitoring, Observability & Keamanan
- [ ] Metrik latency dipisahkan secara detail: `request_queue_time_duration`, `compute_input_time_duration`, `compute_infer_time_duration`, dan `compute_output_time_duration`.
- [ ] Pipeline asynchronous metric collection terhubung ke downstream Drift Detector.
- [ ] Envoy/Istio Circuit Breaker diaktifkan: Jika error rate $5xx > 1\%$ atau latensi $p99 > 30\text{ ms}$, alihkan traffic ke model fallback terdaftar.
- [ ] Input sanitization: Proteksi terhadap Denial of Service via shape dynamic mismatch (validasi tensor dimensions ketat pada schema gateway).

---

### 12. Hands-on Practice (hands-on/m02/)

Praktikum ini akan membangun infrastruktur end-to-end inferensi high-throughput menggunakan ONNX Runtime Server emulation, export model, benchmarking performa, serta pipeline drift detection.

#### Langkah 1: Struktur Direktori Praktikum
Buat struktur direktori berikut pada workstation Anda:
```bash
mkdir -p hands-on/m02/{model_repo/fraud_detector/1,client,monitoring}
cd hands-on/m02
```

#### Langkah 2: Pembuatan Model & Export ke Format ONNX
Simpan skrip berikut sebagai `hands-on/m02/build_and_export.py` untuk melatih dan mengekspor model Random Forest ke format ONNX:

```python
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from skl2onnx import convert_sklearn
from skl2onnx.common.data_types import FloatTensorType
import onnxruntime as ort

# 1. Generate Synthetic Dataset (45 Fitur Finansial)
np.random.seed(42)
X_train = np.random.randn(10000, 45).astype(np.float32)
y_train = (X_train[:, 0] + X_train[:, 1] * 2.0 > 0.5).astype(np.int64)

# Simpan baseline training untuk perbandingan drift nantinya
np.save("monitoring/training_baseline.npy", X_train)
print("[+] Data training baseline berhasil disimpan.")

# 2. Latih Model
clf = RandomForestClassifier(n_estimators=50, max_depth=8, random_state=42)
clf.fit(X_train, y_train)

# 3. Konversi ke ONNX dengan Dynamic Batching Support
initial_type = [('input_features', FloatTensorType([None, 45]))]
onnx_model = convert_sklearn(clf, initial_types=initial_type, target_opset=14)

onnx_path = "model_repo/fraud_detector/1/model.onnx"
with open(onnx_path, "wb") as f:
    f.write(onnx_model.SerializeToString())

print(f"[+] Model berhasil diekspor ke ONNX: {onnx_path}")

# Verifikasi Session Output
sess = ort.InferenceSession(onnx_path)
dummy_input = np.random.randn(5, 45).astype(np.float32)
preds = sess.run(None, {'input_features': dummy_input})
print("[+] Uji coba inferensi lokal ONNX Runtime berhasil. Output shape:", preds[1].shape)
```

Jalankan script untuk membuat artefak model:
```bash
python3 build_and_export.py
```

#### Langkah 3: Menjalankan Triton Inference Server via Docker
Jalankan instance Triton Inference Server resmi NVIDIA (menggunakan backend CPU/GPU):

```bash
docker run --rm -d --name triton-server \
  -p 8000:8000 -p 8001:8001 -p 8002:8002 \
  -v $(pwd)/model_repo:/models \
  nvcr.io/nvidia/tritonserver:23.10-py3 \
  tritonserver --model-repository=/models
```

Buat file konfigurasi model di `hands-on/m02/model_repo/fraud_detector/config.pbtxt`:
```protobuf
name: "fraud_detector"
platform: "onnxruntime_onnx"
max_batch_size: 64

input [
  {
    name: "input_features"
    data_type: TYPE_FP32
    dims: [ 45 ]
  }
]

output [
  {
    name: "probabilities"
    data_type: TYPE_FP32
    dims: [ 2 ]
  }
]

dynamic_batching {
  max_queue_delay_microseconds: 5000
}

instance_group [
  {
    count: 1
    kind: KIND_CPU
  }
]
```

Restart container agar konfigurasi baru dimuat:
```bash
docker restart triton-server
```

Validasi kesiapan endpoint Triton:
```bash
curl -v http://localhost:8000/v2/health/ready
# Ekspektasi: HTTP/1.1 200 OK
```

#### Langkah 4: Load Testing & Drift Monitoring Integration
Simpan file `hands-on/m02/client/load_and_monitor.py`:

```python
import numpy as np
import tritonclient.grpc as grpcclient
from scipy.stats import ks_2samp
import time
import sys

def main():
    try:
        client = grpcclient.InferenceServerClient(url="localhost:8001")
    except Exception as e:
        print(f"Koneksi gagal: {e}")
        sys.exit(1)

    # Muat baseline referensi
    baseline_features = np.load("monitoring/training_baseline.npy")

    print("[+] Memulai simulasi traffic inferensi...")
    drift_detected = False

    for step in range(10):
        # Setiap step mengirim batch inferensi
        # Simulasikan drift pada step >= 6
        if step < 6:
            # Data normal (sesuai distribusi baseline)
            live_batch = np.random.randn(32, 45).astype(np.float32)
        else:
            # Inject Covariate Shift: Menggeser mean secara drastis
            live_batch = (np.random.randn(32, 45) + 1.2).astype(np.float32)

        # Siapkan gRPC inference request
        inputs = [grpcclient.InferInput("input_features", live_batch.shape, "FP32")]
        inputs[0].set_data_from_numpy(live_batch)
        outputs = [grpcclient.InferRequestedOutput("probabilities")]

        t0 = time.perf_counter()
        response = client.infer("fraud_detector", inputs=inputs, outputs=outputs)
        lat_ms = (time.perf_counter() - t0) * 1000

        # Ekstraksi probabilitas (index 1 dari library skl2onnx biasanya map probabilities)
        # Evaluasi Drift pada Fitur Index 0 menggunakan Kolmogorov-Smirnov Test
        stat, p_val = ks_2samp(baseline_features[:, 0], live_batch[:, 0])

        print(f"Step {step+1:02d} | Inferences: {len(live_batch)} | Latency: {lat_ms:.2f}ms | KS-p-value (Feature 0): {p_val:.4e}")

        # Jika p-value < 0.01 secara konsisten, tandai alert
        if p_val < 0.01:
            print(f"  [ALERT] Drift Terdeteksi pada Step {step+1}! p-value di bawah threshold signifikansi kritis.")
            drift_detected = True

    if drift_detected:
        print("\n[KESIMPULAN WORKFLOW] Drift alert berhasil di-trigger. Sirkuit canary deployment aman untuk diputus.")

if __name__ == "__main__":
    main()
```

Jalankan pengujian client:
```bash
python3 client/load_and_monitor.py
```

---

### 13. Exercises

#### Level Easy
1. **Model Warmup Configuration:** Tambahkan skrip atau blok konfigurasi `model_warmup` pada `config.pbtxt` Triton untuk mengeksekusi *synthetic batch request* saat container pertama kali dinyalakan.
   *Rubrik Evaluasi:* Pastikan engine tidak mengalami latensi initialization spike pada request pertama yang diterima dari pengguna publik.

#### Level Medium
2. **Kalkulasi Earth Mover's Distance (Wasserstein Distance):** Buat sebuah Python background worker yang mengonsumsi array fitur input dan menghitung jarak Wasserstein (menggunakan `scipy.stats.wasserstein_distance`) antara baseline dan jendela moving average produksi ($N=1000$).
   *Rubrik Evaluasi:* Terapkan dynamic thresholding di mana alert dibangkitkan jika jarak Wasserstein melampaui $3\sigma$ dari historical moving mean.

#### Level Hard
3. **Automated Canary Deployment Controller:** Bangun script integrasi menggunakan library Kubernetes Python client yang memantau output metrik drift (PSI/KS). Jika nilai PSI melewati $0.2$, skrip secara terprogram harus memodifikasi resource Istio `VirtualService` untuk mengubah persentase traffic routing canary candidate dari bobot $20\%$ menjadi $0\%$ secara instan (Circuit Breaker).
   *Rubrik Evaluasi:* Program harus menerapkan idempotensi, penanganan timeout K8s API, dan zero-downtime traffic diversion.

---

### 14. Challenge (Tantangan Produksi Nyata Tanpa Solusi Instan)

**Konteks Krisis Sistem:**
Anda adalah Staff MLOps Engineer di platform E-Commerce Multi-Nasional. Tepat saat *Midnight Flash Sale* dimulai, model Rekomendasi Click-Through-Rate (CTR) mengalami *cascading collapse*:
1. Utilisasi GPU melompat seketika ke $100\%$, namun memory bandwidth drop ke $12\%$.
2. Latensi inferensi melesat dari $15\text{ ms}$ menjadi $1,400\text{ ms}$, menyebabkan upstream HTTP Gateway melemparkan error `504 Gateway Timeout`.
3. Di saat bersamaan, pipeline deteksi drift Anda memicu ribuan alert palsu (*false positive storms*) pada seluruh fitur kontinu numerik, padahal struktur data input terlihat tidak berubah secara visual.

**Tugas Anda:**
- Analisis kemungkinan akar masalah teknis (root-cause) pada layer GPU concurrency, memory allocation, dan data pipeline.
- Rancang arsitektur mitigasi darurat langkah-demi-langkah untuk:
  - Mengembalikan throughput dan memulihkan latency dalam hitungan menit tanpa me-restart seluruh klaster Kubernetes.
  - Memperbaiki sistem pengujian drift agar kebal terhadap volume ledakan data (*sample size artifact*).
  - Merancang strategi *load shedding* cerdas yang mendegradasi inferensi secara elegan tanpa merusak checkout funnel pengguna.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic
1. **Mengapa web server berbasis Python murni (seperti Flask/FastAPI) umumnya dihindari untuk inference serving GPU tingkat lanjut di skala enterprise?**
   - *Jawaban:* Python terhambat oleh *Global Interpreter Lock* (GIL) yang membatasi konkurensi thread murni, serialization/deserialization JSON yang lambat, serta ketiadaan dynamic batch scheduler bawaan yang mampu mengoptimalkan saturasi paralel tensor core pada GPU.

2. **Apa fungsi utama dari parameter `max_queue_delay_microseconds` dalam Triton Inference Server?**
   - *Jawaban:* Menentukan batas waktu maksimal scheduler untuk menunggu request-request tambahan masuk ke antrean agar dapat digabungkan menjadi batch yang optimal sebelum diproses serentak ke GPU.

3. **Apa perbedaan mendasar antara *Covariate Shift* dan *Concept Drift*?**
   - *Jawaban:* *Covariate Shift* terjadi ketika distribusi fitur input $P(X)$ berubah sementara relasi target $P(Y|X)$ tetap sama. *Concept Drift* terjadi saat relasi kausal atau probabilitas bersyarat $P(Y|X)$ itu sendiri yang berubah.

4. **Bagaimana protokol gRPC mengungguli HTTP/1.1 REST konvensional dalam konteks inferensi model berskala besar?**
   - *Jawaban:* Menggunakan multiplexing berbasis HTTP/2 dalam satu koneksi TCP tunggal, representasi serialisasi biner yang ringkas via Protocol Buffers (mengurangi beban parsing teks), dan dukungan native streaming tensor secara bidirectional.

5. **Apa indikasi klinis dari nilai Population Stability Index (PSI) bernilai $0.28$?**
   - *Jawaban:* Menandakan telah terjadi pergeseran distribusi data yang signifikan/drastis (*Significant Drift*) pada fitur yang diamati, membutuhkan penyelidikan mendalam dan retrain model segera.

---

#### B. Pertanyaan Intermediate
1. **Jelaskan mekanisme memory pin (*pinned host memory / page-locked memory*) dan perannya dalam mempercepat inferensi GPU!**
   - *Jawaban:* Sistem operasi secara default menggunakan *pageable memory* yang lokasinya di RAM dapat dipindahkan oleh OS. Pinned host memory mengunci alokasi fisik RAM agar tidak dipindahkan, memungkinkan transfer data langsung melalui Direct Memory Access (DMA) antara GPU dan RAM tanpa melibatkan intervensi CPU, sehingga memaksimalkan bandwidth jalur PCIe.

2. **Mengapa uji Kolmogorov-Smirnov (KS-Test) menghasilkan p-value mendekati 0 (menunjukkan drift) pada sampel produksi yang sangat besar padahal perbedaan distribusinya secara praktis dapat diabaikan?**
   - *Jawaban:* KS-test memiliki *statistical power* yang berbanding lurus dengan ukuran sampel ($N$). Pada $N$ yang sangat besar, *standard error* menjadi infinitesimal, sehingga deviasi fluktuasi mikro terkecil sekalipun akan dianggap signifikan secara statistik, menghasilkan bias *false-positive drift*.

3. **Bagaimana pola *Shadow Deployment* (Traffic Mirroring) bekerja dan apa keunggulannya dibandingkan pengujian di staging cluster?**
   - *Jawaban:* Envoy/Ingress Gateway menduplikasi traffic produksi nyata dan mengirimkannya ke model kandidat baru secara asinkron tanpa memulangkan responnya ke pengguna akhir. Keunggulannya adalah model kandidat diuji terhadap volume beban, variasi data, dan keanehan edge-case produksi nyata dengan $0\%$ risiko gangguan terhadap pengalaman pengguna (zero blast radius).

4. **Kapan teknik kuantisasi INT8 tidak disarankan untuk digunakan langsung dalam pipeline inferensi produksi tanpa quantization-aware training (QAT)?**
   - *Jawaban:* Ketika model memiliki dynamic range aktivasi yang sangat lebar dan bervariasi secara ekstrem (misal pada layer-layer tertentu Transformer attention blocks), atau ketika output model membutuhkan sensitivitas presisi floating point numerik tinggi (misal: regression pricing eksak), di mana Post-Training Quantization (PTQ) naif memicu fenomena *clipping error* yang merusak akurasi.

5. **Apa fungsi dari implementasi `IOBinding` pada runtime inferensi seperti ONNX Runtime?**
   - *Jawaban:* `IOBinding` memungkinkan engineer untuk mengalokasikan tensor input dan output secara eksplisit pada memori GPU terlebih dahulu sebelum eksekusi dimulai, mencegah alokasi memori internal yang berulang (*re-allocation overhead*) dan memangkas penyalinan implisit antara Host CPU dan Device GPU.

---

#### C. Skenario Kasus Produksi
1. **Skenario 1:** *Sebuah model computer vision dieksekusi di Triton menggunakan 4 model instances pada satu kartu GPU NVIDIA A10G (24GB). Selama pengujian internal latensi rata-rata stabil di 12ms. Namun, saat uji stres 10,000 QPS, latensi melambung ke 450ms tanpa ada request yang drop (error rate 0%). Metrik utilisasi VRAM menunjukkan 18GB/24GB terpakai.*
   - *Pertanyaan:* Apa akar masalah performa ini dan bagaimana solusinya?
   - *Analisis & Solusi:* Ini adalah indikasi klasik dari **Hardware Execution Serialization (CUDA Stream Contention) & Queue Saturation**. Meskipun memori VRAM mencukupi (18GB/24GB), 4 instance model bersaing memperebutkan compute SM (Streaming Multiprocessors) yang sama sementara antrean dynamic batching menumpuk. Antrean membesar tanpa batas karena request rate melampaui kemampuan komputasi fisik GPU. Solusinya: Konfigurasikan batas antrean model (`max_queue_delay_microseconds` diperketat), turunkan jumlah concurrent instance jika compute cores telah tersaturasi, terapkan upstream rate-limiting/load-shedding via Envoy, dan aktifkan Horizontal Pod Autoscaler (HPA) berdasarkan metrik Triton `nv_inference_queue_duration_us` daripada utilisasi memory CPU/VRAM.

2. **Skenario 2:** *Pipeline retraining otomatis Anda memicu build model baru setiap kali drift detector mengirim alert. Suatu hari, sistem drift mendeteksi perubahan drastis pada fitur 'kategori_transaksi' karena adanya libur nasional (Black Friday). Model baru otomatis dilatih menggunakan data 7 hari terakhir, langsung di-deploy menggantikan model lama. Dua jam kemudian, conversion rate checkout anjlok 35%.*
   - *Pertanyaan:* Mengapa degradasi ini terjadi dan bagaimana memperbaiki arsitektur siklus otomatisasi tersebut?
   - *Analisis & Solusi:* Terjadi over-reaction terhadap **Seasonal Covariate Shift temporer**. Model dilatih ulang menggunakan data anomali Black Friday yang sempit dan kehilangan generalisasi terhadap pola perilaku konsumen jangka panjang (mengalami catastrophic overfitting pada data musiman). Perbaikan arsitektur: Retraining otomatis tidak boleh langsung di-promote ke produksi tanpa evaluasi komparatif (*Champion/Challenger*). Terapkan gerbang validasi berlapis: Model baru harus melalui *shadow evaluation* offline terhadap holdout set jangka panjang, dan deployment wajib melalui canary rollout bertahap (10% -> 25% -> 50%) dengan pemantauan metrik bisnis (Conversion Rate) secara real-time, bukan hanya metrik statistik ML.

3. **Skenario 3:** *Tim Anda mengimplementasikan canary rollout 10% untuk Model v2. Envoy Gateway membagi traffic berdasarkan bobot acak (random weight routing). Beberapa pengguna melaporkan di media sosial bahwa harga barang di keranjang belanja mereka berubah-ubah secara acak setiap kali me-refresh halaman aplikasi.*
   - *Pertanyaan:* Kesalahan arsitektur jaringan apa yang terjadi di layer Service Mesh/Gateway, dan bagaimana solusi konfigurasinya?
   - *Analisis & Solusi:* Terjadi ketiadaan **Session Affinity (Sticky Sessions)** pada traffic routing canary. Envoy mendistribusikan request secara acak per koneksi/request independen, menyebabkan refresh pertama mengenai Model v1 (Harga A) dan refresh kedua mengenai Model v2 (Harga B). Solusinya: Ubah hashing policy pada Istio/Envoy `VirtualService` dari round-robin/random murni menjadi *Consistent Hashing* berbasis identitas pengguna yang stabil (misalnya HTTP Cookie `session-id` atau JWT `user_id`). Dengan demikian, seorang pengguna akan secara konsisten dipetakan ke versi model yang sama (100% v1 atau 100% v2) selama masa uji coba canary berlangsung.

---

### 16. Summary
- Melayani model inferensi berskala enterprise memerlukan pemisahan ketat antara pipeline komputasi tensor terakselerasi hardware (Triton/TensorRT) dengan pipeline komunikasi networking (Envoy/gRPC).
- **Dynamic batching** adalah mekanisme fundamental penyeimbang antara efisiensi hardware GPU dan batas toleransi latensi klien; tuning delay window merupakan kompromi antara throughput dan p99 tail latency.
- Menjamin kelangsungan performa model pasca-deployment menuntut observabilitas berbasis data statistik (*Data/Concept Drift*) menggunakan instrumen seperti **Kolmogorov-Smirnov Test** dan **Population Stability Index (PSI)** yang diisolasi secara asinkron dari jalur inferensi kritis.
- Deployment modern wajib memanfaatkan kapabilitas Service Mesh untuk menerapkan **Traffic Mirroring (Shadowing)** dan **Canary Routing** berbasis hashing konsisten, didukung oleh *circuit breaker* otomatis yang siap melakukan rollback seketika degradasi metrik sistemik terdeteksi.