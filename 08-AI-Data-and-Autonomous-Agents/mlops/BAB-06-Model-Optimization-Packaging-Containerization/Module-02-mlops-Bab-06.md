# BAB 06: Model Optimization, Packaging & Containerization
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Merancang dan mengeksekusi pipeline optimasi model tingkat lanjut menggunakan kompilasi graf (*graph compilation*), kuantisasi INT8 (*Quantization-Aware Training* dan *Post-Training Quantization* dengan kalibrasi KL-Divergence), serta pemangkasan bobot (*structured pruning*).
- Mengonversi dan memvalidasi artefak model dari framework dinamis (PyTorch) ke format portabel performa tinggi (ONNX dan NVIDIA TensorRT Engine) dengan dynamic axes handling.
- Menyusun arsitektur packaging model berstandar enterprise menggunakan Triton Inference Server Model Repository, lengkap dengan konfigurasi *Dynamic Batching*, *Concurrent Model Execution*, dan *Model Pipelining/Ensemble*.
- Membangun image container inference ultra-minimalis, *hardened*, dan siap produksi yang memanfaatkan *pinned memory*, *shared memory (IPC)*, serta integrasi CUDA runtime modern.
- Menganalisis metrik performa latensi P95/P99, throughput (QPS), dan GPU memory footprint menggunakan tools profiling industri seperti `perf_analyzer` dan NVIDIA Nsight Systems.

---

### 2. Prerequisite

Peserta wajib menguasai:
- **Sistem Operasi & Hardware**: Linux system administration tingkat lanjut, Linux cgroups, driver NVIDIA, arsitektur GPU CUDA (Streaming Multiprocessors, VRAM HBM/GDDR, Tensor Cores).
- **Machine Learning Core**: PyTorch tingkat lanjut (Autograd engine, `torch.export`, dynamic graph vs static graph execution).
- **Containerization**: Docker multi-stage build, rootless containers, Container Network Interface (CNI), NVIDIA Container Toolkit (`nvidia-container-runtime`).
- **Software Engineering**: Pemrograman C++ dasar (opsional namun dianjurkan) dan Python 3.10+ (typing, asyncio, multiprocessing, ctypes).

---

### 3. Concept & Internal Architecture

Memindahkan model machine learning dari lingkungan riset (Jupyter Notebook / PyTorch eager mode) menuju lingkungan produksi berlatensi rendah memerlukan rekonstruksi total terhadap bagaimana instruksi komputasi dieksekusi oleh perangkat keras.

```
+-----------------------------------------------------------------------------------+
|                            COMPILATION & RUNTIME LAYERS                           |
+-----------------------------------------------------------------------------------+
|  [PyTorch Eager Graph]                                                            |
|         │                                                                         |
|         ▼ (Tracing / AOT Autograd)                                                |
|  [Intermediate Representation (IR)] ──> ONNX Operator Graph                       |
|         │                                                                         |
|         ▼ (Graph Optimization & Kernel Fusion)                                    |
|  [Target-Specific Engine]           ──> TensorRT Engine / OpenVINO IR             |
|         │                                                                         |
|         ▼ (Serving Layer)                                                         |
|  [Triton Inference Server]          ──> C++ Backend / Dynamic Batching Scheduler  |
|         │                                                                         |
|         ▼ (Hardware Layer)                                                        |
|  [NVIDIA GPU / Tensor Cores]        ──> FP16/INT8 Matrix Multiplication (Sgemm)  |
+-----------------------------------------------------------------------------------+
```

#### A. Graph Optimization Mechanics
Model deep learning konvensional mengeksekusi operasi matematika secara sekuensial melalui abstraksi framework:
1. **Operator Fusion (Fusi Operator)**: Menggabungkan beberapa operasi kernel mikro menjadi satu kernel GPU. Contoh: `Conv2D + BatchNorm + ReLU` diubah menjadi satu instruksi `FusedConvReluKernel`. Hal ini mengeliminasi *round-trip memory overhead* antara GPU SRAM (Register/Shared Memory) dan VRAM (High-Bandwidth Memory - HBM).
2. **Constant Folding & Dead Code Elimination**: Mengevaluasi sub-grafik statis saat kompilasi. Jika bobot model dan parameter normalisasi bersifat deterministik, engine pra-menghitung nilai tersebut sehingga tidak ada komputasi redundan di runtime.
3. **Horizontal Layer Fusion**: Menggabungkan layer yang memiliki input dan tipe operasi serupa ke dalam satu kernel terpadu untuk memaksimalkan paralelisasi *Streaming Multiprocessors* (SM).

#### B. Quantization Mechanics: FP32 to INT8
Representasi float standar memakan alokasi 32-bit (1 sign bit, 8 exponent bits, 23 mantissa bits). Kuantisasi memetakan rentang kontinu bernilai riil $x \in [\alpha, \beta]$ ke rentang diskrit bernilai integer $q \in [-128, 127]$ (signed INT8):

$$q = \text{round}\left(\frac{x}{S}\right) + Z$$

Di mana:
- $S$ (*Scale factor*): Menentukan rasio kompresi rentang dinamis nilai riil terhadap batas integer.
- $Z$ (*Zero-point*): Nilai integer yang merepresentasikan nilai float 0.0 (pada kuantisasi simetris, $Z = 0$).

Tantangan utama pada **Post-Training Quantization (PTQ)** adalah menentukan clipping threshold $[\alpha, \beta]$ secara optimal agar informasi penting pada ekor distribusi bobot dan aktivasi tidak terpotong drastis (*saturation error* vs *quantization noise*). Untuk layer aktivasi, TensorRT menggunakan **Kullback-Leibler (KL) Divergence Calibration**:

$$D_{KL}(P \parallel Q) = \sum_{i=1}^{N} P(i) \log \left(\frac{P(i)}{Q(i)}\right)$$

Algoritma kalibrasi mengukur relative entropy antara distribusi aktivasi asli (FP32, $P$) dengan distribusi aktivasi yang dikuantisasi lalu didekuantisasi kembali ($Q$), mencari nilai pemotongan (*saturation point*) yang meminimalkan hilangnya informasi statistik.

#### C. Memory Lifecycle & Server Concurrency
Arsitektur inference engine modern meminimalkan alokasi memori dinamis (*zero-allocation principle* saat *steady-state*). 
- **Pinned Host Memory (Page-Locked Memory)**: Triton Inference Server mengalokasikan buffer memory request input pada pinned system memory (`cudaHostAlloc`). Hal ini memungkinkan GPU Direct DMA (Direct Memory Access) mentransfer buffer ke VRAM tanpa intervensi CPU, melipatgandakan throughput PCI-Express.
- **Dynamic Batching**: Server menahan request individual dalam queue mikro selama kurun waktu tertentu (`max_queue_delay_microseconds`), menggabungkan payload tensor secara kontinu sebelum mengirimkannya ke antrean komputasi CUDA Stream, memaksimalisasi saturasi utilisasi Tensor Cores tanpa mengorbankan Service Level Objective (SLO) latensi individual.

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional (Python Flask/FastAPI) | Pendekatan Enterprise MLOps (Triton + TensorRT) |
| :--- | :--- | :--- |
| **Execution Mode** | Python Eager Mode, overhead Global Interpreter Lock (GIL). | Native C++ Runtime Engine, zero GIL dependency. |
| **Throughput (QPS)** | Terbatas pada serialisasi process-based worker (`gunicorn -w 4`). | Skala masif via *Dynamic Batching* dan asynchronous CUDA streams. |
| **Hardware Saturation** | 15% - 35% utilisasi GPU (sering terjadi bottleneck CPU-GPU memory copy). | 80% - 98% utilisasi GPU melalui kernel fusion & INT8 Tensor Core execution. |
| **Memory Footprint** | Duplikasi runtime PyTorch per worker instance (menghabiskan VRAM). | Single Shared Engine Context di VRAM, mendukung concurrent instances. |
| **Contract & SLA** | Rest API JSON payload yang boros bandwidth, parsing CPU intensif. | Binary gRPC payload via HTTP/2, Shared Memory IPC, typed flatbuffers/protobuf. |

**Mengapa ini penting?** 
Pada skala enterprise, latensi berlebih berbanding lurus dengan churn rate dan biaya infrastruktur. Sebuah model LLM atau Computer Vision yang berjalan di AWS `g5.xlarge` tanpa optimasi dapat memakan biaya \$1,000/bulan per instance. Dengan optimasi TensorRT dan Triton Dynamic Batching, satu instance dapat menangani beban yang sebelumnya membutuhkan 4–6 instance, menghasilkan penurunan biaya *compute infrastructure* sebesar 60–80%.

---

### 5. How (Workflow Detail)

Alur kerja implementasi produksi model packaging dan optimasi:

```
[PyTorch Model (.pt)]
         │
         ▼
[Export Phase: Torch Dynamo / ONNX opset 18+]
         │
         ▼
[ONNX Validation & Shape Verification]
         │
         ▼
[TensorRT Compilation (FP16/INT8 with Calibration Engine)]
         │
         ▼
[Assembly Triton Model Repository (config.pbtxt, dynamic batcher, versioning)]
         │
         ▼
[Container Packaging (Hardened Distroless Base, Shared Memory /dev/shm Tuning)]
         │
         ▼
[Production Stress Profiling (perf_analyzer saturation test)]
```

1. **Model Checkpoint Freezing**: Mengekstraksi arsitektur dan state dict model terlatih, membersihkan hook debugging, dan mengisolasi bobot.
2. **Graph Intermediate Export (ONNX)**: Mengekspor representasi graf menggunakan `torch.onnx.export` dengan deklarasi eksplisit dynamic axes untuk batch dimension dan sequence dimension.
3. **Targeted Engine Compilation**: Membangun engine berbasis hardware arsitektur spesifik (Ampere, Hopper, Lovelace) menggunakan NVIDIA `trtexec` atau Python TensorRT API, menyertakan dataset kalibrasi representatif untuk INT8.
4. **Repository Packaging**: Mengonstruksi direktori Triton sesuai spesifikasi strict semantic versioning. Menulis file deklarasi konfigurasi model (`config.pbtxt`).
5. **Container Assembly**: Menggunakan teknik multi-stage build untuk mengisolasi Triton Inference Server runtime, menonaktifkan privilege root, dan mengatur IPC shm parameter.
6. **Profiling & Benchmarking**: Menentukan sweet-spot batas maksimal dynamic queue delay dan instance concurrency melalui benchmark terautomasi.

---

### 6. Analogy & Diagram ASCII

#### Analogi Sistem
Bayangkan PyTorch Eager Mode seperti **Dapur Restoran Tradisional**:
Setiap pesanan (input inference) memicu juru masak membaca resep langkah demi langkah (Python interpreter parsing instruksi), berjalan bolak-balik mengambil bahan dari kulkas besar di lantai bawah ke meja masak (VRAM ke Cache transfer untuk tiap layer), dan memasak satu porsi makanan per wajan (unbatched execution).

TensorRT + Triton Inference Server adalah **Pabrik Makanan Otomatis Berkecepatan Tinggi**:
Resep telah disederhanakan dan beberapa langkah memasak digabung ke dalam satu mesin konveyor terpadu (*Operator Fusion*). Ukuran kemasan distandardisasi (*Quantization*). Pesanan yang datang dalam milidetik yang sama dikumpulkan dan dimasukkan serentak ke mesin pemasak berukuran besar (*Dynamic Batching*), meminimalisasi pemborosan energi dan menghasilkan output masif dengan presisi tinggi.

#### Diagram Arsitektur Internal Triton Inference Server

```
Client Requests (gRPC / HTTP2)
           │
           ▼
┌──────────────────────────────────────────────────────────┐
│              TRITON INFERENCE SERVER CORE                │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │               Endpoint Frontend Queue              │  │
│  └─────────────────────────┬──────────────────────────┘  │
│                            │                             │
│                            ▼                             │
│  ┌────────────────────────────────────────────────────┐  │
│  │ Dynamic Batching Scheduler                         │  │
│  │  - max_queue_delay_microseconds: 5000              │  │
│  │  - max_batch_size: 64                              │  │
│  │  [Req 1] [Req 2] [Req 3] ──> Packed Batch [B=3]     │  │
│  └─────────────────────────┬──────────────────────────┘  │
│                            │                             │
│         ┌──────────────────┴──────────────────┐          │
│         ▼                                     ▼          │
│  ┌──────────────┐                      ┌──────────────┐  │
│  │ Model Inst 0 │                      │ Model Inst 1 │  │
│  │ (CUDA Str 0) │                      │ (CUDA Str 1) │  │
│  │ ┌──────────┐ │                      │ ┌──────────┐ │  │
│  │ │ TensorRT │ │                      │ │ TensorRT │ │  │
│  │ │ Engine   │ │                      │ │ Engine   │ │  │
│  │ └──────────┘ │                      │ └──────────┘ │  │
│  └──────┬───────┘                      └──────┬───────┘  │
│         │                                     │          │
│         └──────────────────┬──────────────────┘          │
│                            ▼                             │
│  ┌────────────────────────────────────────────────────┐  │
│  │ IPC System / Pinned Shared Memory Output Buffer    │  │
│  └────────────────────────────────────────────────────┘  │
└────────────────────────────┬─────────────────────────────┘
                             │
                             ▼
                      Client Responses
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: PyTorch ke ONNX dengan Dynamic Batching
Skrip ekspor model PyTorch standar ke ONNX dengan dukungan dynamic batch size:

```python
import torch
import torch.nn as nn

class ProductionFeatureExtractor(nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int, output_dim: int):
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.BatchNorm1d(hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, output_dim)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.network(x)

# Inisialisasi model
model = ProductionFeatureExtractor(input_dim=128, hidden_dim=64, output_dim=10)
model.eval()

# Dummy input untuk tracing
dummy_input = torch.randn(1, 128, requires_grad=False)

# Export ke ONNX
onnx_output_path = "feature_extractor.onnx"
torch.onnx.export(
    model,
    dummy_input,
    onnx_output_path,
    export_params=True,
    opset_version=17,
    do_constant_folding=True,
    input_names=["input_tensor"],
    output_names=["output_tensor"],
    dynamic_axes={
        "input_tensor": {0: "batch_size"},
        "output_tensor": {0: "batch_size"}
    }
)
print(f"Model berhasil diekspor ke: {onnx_output_path}")
```

#### B. Practical Example: Kompilasi TensorRT, Triton Model Config, dan Client Inference

##### 1. TensorRT INT8 Calibrator & Engine Builder (`build_engine.py`)

```python
import os
import tensorrt as trt
import pycuda.driver as cuda
import pycuda.autoinit
import numpy as np

TRT_LOGGER = trt.Logger(trt.Logger.INFO)

class SyntheticEntropyCalibrator(trt.IInt8EntropyCalibrator2):
    def __init__(self, batch_size: int, channels: int, total_images: int, cache_file: str):
        super().__init__()
        self.batch_size = batch_size
        self.shape = (batch_size, channels)
        self.total_images = total_images
        self.cache_file = cache_file
        self.current_index = 0
        
        # Alokasi memory CUDA device untuk feeding data kalibrasi
        self.device_input = cuda.mem_alloc(np.prod(self.shape) * 4) # float32 = 4 bytes

    def get_batch_size(self):
        return self.batch_size

    def get_batch(self, names):
        if self.current_index + self.batch_size > self.total_images:
            return None
        
        # Simulasi fetching batch data asli representatif
        synthetic_batch = np.ascontiguousarray(
            np.random.normal(0.0, 1.0, self.shape).astype(np.float32)
        )
        cuda.memcpy_htod(self.device_input, synthetic_batch)
        self.current_index += self.batch_size
        return [int(self.device_input)]

    def read_calibration_cache(self):
        if os.path.exists(self.cache_file):
            with open(self.cache_file, "rb") as f:
                return f.read()
        return None

    def write_calibration_cache(self, cache):
        with open(self.cache_file, "wb") as f:
            f.write(cache)

def build_int8_engine(onnx_file_path: str, engine_file_path: str):
    builder = trt.Builder(TRT_LOGGER)
    network_flags = 1 << int(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH)
    network = builder.create_network(network_flags)
    parser = trt.OnnxParser(network, TRT_LOGGER)

    with open(onnx_file_path, "rb") as model_file:
        if not parser.parse(model_file.read()):
            for error in range(parser.num_errors):
                print(parser.get_error(error))
            raise RuntimeError("Gagal mem-parsing ONNX file.")

    config = builder.create_builder_config()
    config.set_memory_pool_limit(trt.MemoryPoolType.WORKSPACE, 1 << 30) # 1GB
    
    if builder.platform_has_fast_int8:
        config.set_flag(trt.BuilderFlag.INT8)
        calibrator = SyntheticEntropyCalibrator(
            batch_size=8, channels=128, total_images=128, cache_file="calibration.cache"
        )
        config.int8_calibrator = calibrator
    else:
        config.set_flag(trt.BuilderFlag.FP16)

    # Menangani Dynamic Shapes
    profile = builder.create_optimization_profile()
    profile.set_shape("input_tensor", min=(1, 128), opt=(16, 128), max=(64, 128))
    config.add_optimization_profile(profile)

    serialized_engine = builder.build_serialized_network(network, config)
    with open(engine_file_path, "wb") as f:
        f.write(serialized_engine)
    print(f"TensorRT engine berhasil dikompilasi: {engine_file_path}")

if __name__ == "__main__":
    build_int8_engine("feature_extractor.onnx", "model.plan")
```

##### 2. Triton Model Configuration (`config.pbtxt`)
Lokasi file: `model_repository/feature_extractor/config.pbtxt`

```protobuf
name: "feature_extractor"
platform: "tensorrt_plan"
max_batch_size: 64

input [
  {
    name: "input_tensor"
    data_type: TYPE_FP32
    dims: [ 128 ]
  }
]

output [
  {
    name: "output_tensor"
    data_type: TYPE_FP32
    dims: [ 10 ]
  }
]

# Konfigurasi Dynamic Batcher untuk saturasi GPU
dynamic_batching {
  max_queue_delay_microseconds: 5000
  preferred_batch_size: [ 8, 16, 32, 64 ]
}

# Skalabilitas horizontal di dalam GPU tunggal
instance_group [
  {
    count: 2
    kind: KIND_GPU
    gpus: [ 0 ]
  }
]
```

##### 3. High-Performance Triton gRPC Python Client (`client.py`)

```python
import numpy as np
import tritonclient.grpc as grpcclient
from tritonclient.utils import InferenceServerException
import sys

def execute_inference():
    server_url = "localhost:8001"
    model_name = "feature_extractor"

    try:
        triton_client = grpcclient.InferenceServerClient(url=server_url, verbose=False)
    except Exception as e:
        print(f"Inisialisasi channel gagal: {e}")
        sys.exit(1)

    # Verifikasi status server dan model
    if not triton_client.is_server_live():
        raise RuntimeError("Triton server tidak responsif (liveness probe failed).")
    
    if not triton_client.is_model_ready(model_name=model_name):
        raise RuntimeError(f"Model {model_name} belum siap (readiness probe failed).")

    # Siapkan payload
    batch_size = 4
    raw_data = np.random.randn(batch_size, 128).astype(np.float32)

    inputs = [grpcclient.InferInput("input_tensor", raw_data.shape, "FP32")]
    inputs[0].set_data_from_numpy(raw_data)

    outputs = [grpcclient.InferRequestedOutput("output_tensor")]

    # Kirim inference request secara sinkron via gRPC
    print(f"Mengirim batch {batch_size} tensor ke model {model_name}...")
    response = triton_client.infer(
        model_name=model_name,
        inputs=inputs,
        outputs=outputs,
        client_timeout=10.0
    )

    result = response.as_numpy("output_tensor")
    print("Inference berhasil. Shape output:", result.shape)
    print("Output sample (Row 0):", result[0])

if __name__ == "__main__":
    execute_inference()
```

##### 4. Production-Ready Dockerfile Multi-Stage Build

```dockerfile
# Stage 1: Build & Compilation environment
FROM nvcr.io/nvidia/tensorrt:23.10-py3 AS builder

WORKDIR /workspace
RUN pip install --no-cache-dir onnx==1.15.0 pycuda==2022.2.2

COPY feature_extractor.onnx build_engine.py ./
RUN python3 build_engine.py

# Stage 2: Minimal Production Serving Environment
FROM nvcr.io/nvidia/tritonserver:23.10-py3-min

ENV MODEL_REPOSITORY=/models
WORKDIR /opt/tritonserver

# Buat direktori repository sesuai spesifikasi Triton
RUN mkdir -p ${MODEL_REPOSITORY}/feature_extractor/1

# Salin konfigurasi dan binary engine dari stage 1
COPY --from=builder /workspace/model.plan ${MODEL_REPOSITORY}/feature_extractor/1/model.plan
COPY config.pbtxt ${MODEL_REPOSITORY}/feature_extractor/config.pbtxt

# Terapkan konfigurasi non-root untuk keamanan kontainer
RUN chown -R triton-server:triton-server ${MODEL_REPOSITORY}
USER triton-server

EXPOSE 8000 8001 8002

ENTRYPOINT ["tritonserver"]
CMD ["--model-repository=/models", "--strict-model-config=true", "--log-verbose=0"]
```

---

### 8. Real World Case Study (Enterprise Scale)

**Kasus**: Fintech Payment Gateway - Fraud Detection Core Engine.
- **Problem**: 
  Sistem transaksi real-time memproses puncaknya hingga **35.000 Transaksi per Detik (TPS)**. Setiap transaksi harus divalidasi oleh model ensemble (Tabular Transformer + XGBoost) dengan budget latensi maksimal $15\text{ ms}$ (P99). Sistem lama berbasis Python Gunicorn melanggar SLA latensi ($45\text{ ms}$) saat load melonjak dan menghabiskan 40 instance AWS `c5.4xlarge`.
- **Solution Architecture**:
  1. Kompilasi Tabular Transformer ke TensorRT FP16 engine dengan Dynamic Batching.
  2. Eksekusi XGBoost model memanfaatkan Triton Forest Inference Library (FIL) backend.
  3. Desain Triton Ensemble Model Pipeline: Request HTTP transaksi masuk via gRPC, diteruskan ke layer pre-processing C++, lalu dieksekusi secara paralel di GPU via model pipeline Triton.
  4. Penyebaran arsitektur menggunakan Triton Server di atas Kubernetes (EKS) dengan GPU node `g5.2xlarge` (NVIDIA A10G).
- **Hasil Terukur**:
  - P99 Latency terpangkas drastis dari $45\text{ ms}$ menjadi **$6.2\text{ ms}$**.
  - Total Node footprint berkurang dari 40 instance CPU menjadi **6 instance GPU**.
  - Infrastruktur cost berkurang **68%** per kuartal.
  - Nilai throughput per node naik sebesar $420\%$.

---

### 9. Trade-offs

| Parameter | Pendekatan A | Pendekatan B | Keputusan Arsitektural / Analisis Trade-off |
| :--- | :--- | :--- | :--- |
| **Precision Strategy** | **FP16 (Half Precision)** | **INT8 (Quantized Integer)** | FP16 mempertahankan akurasi 99.9% tanpa kalibrasi, namun throughput 2x lebih rendah dari INT8. INT8 memotong konsumsi VRAM hingga 50% dan meningkatkan komputasi Tensor Core, namun membutuhkan dataset kalibrasi yang representatif dan rawan regresi akurasi. |
| **Model Format** | **ONNX Runtime Engine** | **TensorRT Native Plan Engine** | ONNX Runtime sangat portabel (dapat dipindahkan lintas vendor GPU/CPU), namun mengorbankan 15–35% latensi puncak dibanding TensorRT yang dikompilasi secara spesifik terhadap arsitektur chip target (misal: compute capability 8.6). TensorRT engine tidak kompatibel lintas arsitektur GPU yang berbeda. |
| **Batching Mechanism** | **Stateless Single Inference** | **Dynamic Batching Engine** | Single inference menghasilkan latensi individu terendah (*zero delay queue*), namun throughput server sangat rendah. Dynamic batching mengorbankan latensi P50 (karena antrean mikro) demi mendongkrak throughput total secara eksponensial. |
| **Instance Concurrency** | **Single Model Instance / GPU** | **Multiple Instances per GPU** | Multiple instance (`count > 1` di `instance_group`) mengurangi latency starvation pada payload kecil, tetapi dapat memicu thrashing VRAM dan CUDA Context switching jika GPU memory bandwidth tersaturasi penuh. |

---

### 10. Common Mistakes & Troubleshooting

1. **Kesalahan Penanganan Dynamic Axis pada ONNX Export**:
   - *Gejala*: Model melempar runtime exception `Input shape mismatch: expected [1, 128], received [8, 128]` saat Triton melakukan dynamic batching.
   - *Penyebab*: `torch.onnx.export` dijalankan tanpa menyertakan argumen `dynamic_axes`, sehingga batch size terkunci secara statis pada nilai `1`.
   - *Solusi*: Tentukan secara eksplisit indeks dimensi variabel pada konfigurasi ekspor:
     ```python
     dynamic_axes={'input_tensor': {0: 'batch_size'}, 'output_tensor': {0: 'batch_size'}}
     ```

2. **CUDA Out-Of-Memory (OOM) Akibat Workspace TensorRT yang Terlalu Agresif**:
   - *Gejala*: Triton server crash secara instan saat inisialisasi model (`CUDA error: out of memory`).
   - *Penyebab*: Alokasi memory pool workspace TensorRT diset melebihi sisa VRAM fisik yang dialokasikan Docker container (terutama jika ada instance group ganda).
   - *Solusi*: Batasi ukuran workspace melalui builder config: `config.set_memory_pool_limit(trt.MemoryPoolType.WORKSPACE, 1 << 29)` (512MB), serta pastikan kapasitas VRAM dihitung:
     $$\text{Total VRAM} \ge \text{Instance Count} \times (\text{Engine Size} + \text{Workspace Size} + \text{Max Batch Activation Size})$$

3. **IPC Latency Bottleneck Akibat Kurangnya Shared Memory pada Docker**:
   - *Gejala*: Request throughput tersendat di angka rendah dan utilisasi CPU sistem mencapai 100% (*high iowait/system time*).
   - *Penyebab*: Secara default, Docker membatasi ukuran `/dev/shm` ke 64MB. Saat mentransfer tensor berukuran masif antar proses atau via Triton C-API, alokasi memori beralih ke swap disk.
   - *Solusi*: Berikan alokasi flag shared memory penuh saat container run: `--shm-size=4g` atau `--ipc=host`.

---

### 11. Best Practices (Production Checklist)

- [ ] **Grafik Deterministik**: Pastikan tidak ada dynamic control flow Python murni (`if-else` berbasis tensor content) saat melakukan tracing model.
- [ ] **Kompilasi Hardware-Specific**: Engine TensorRT wajib dikompilasi pada GPU target yang sama persis dengan spesifikasi node worker cluster produksi.
- [ ] **Penyelarasan Presisi Kalibrasi**: Gunakan minimum 500–1000 sampel data inferensi riil yang terdistribusi normal untuk kalibrasi INT8.
- [ ] **Suhu Operasional & Clock Rate**: Set GPU compute mode ke default dan aktifkan persistence mode (`nvidia-smi -pm 1`) pada host machine agar driver CUDA context tidak ter-reset.
- [ ] **Strict Model Control Triton**: Selalu jalankan Triton dengan `--model-control-mode=explicit` di environment produksi untuk mendukung canary deployment dan hot-reloading model tanpa restart kontainer.
- [ ] **Liveness & Readiness Probes**: Konfigurasikan Kubernetes probe mengarah ke endpoint HTTP Triton (`/v2/health/live` dan `/v2/health/ready`).
- [ ] **Container Hardening**: Buang development tools (gcc, git, pip cache) dari final container image. Jalankan Triton di bawah non-root UID/GID.

---

### 12. Hands-on Practice

Buat struktur direktori di mesin lokal Anda:
```bash
mkdir -p hands-on/m02/model_repository/linear_classifier/1
cd hands-on/m02
```

#### Langkah 1: Siapkan Virtual Environment & Dependencies
```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install torch torchvision onnx tritonclient[all] numpy
```

#### Langkah 2: Buat Script Export PyTorch ke ONNX (`export.py`)
Simpan script berikut di `hands-on/m02/export.py`:

```python
import torch
import torch.nn as nn

class Classifier(nn.Module):
    def __init__(self):
        super().__init__()
        self.fc = nn.Linear(32, 2)
    def forward(self, x):
        return self.fc(x)

model = Classifier()
model.eval()
dummy = torch.randn(1, 32)

torch.onnx.export(
    model, 
    dummy, 
    "model_repository/linear_classifier/1/model.onnx",
    input_names=["input"],
    output_names=["output"],
    dynamic_axes={"input": {0: "batch"}, "output": {0: "batch"}},
    opset_version=17
)
print("Model ONNX berhasil dibuat.")
```
Jalankan: `python export.py`

#### Langkah 3: Konfigurasi Triton Model (`config.pbtxt`)
Buat file `hands-on/m02/model_repository/linear_classifier/config.pbtxt`:

```protobuf
name: "linear_classifier"
platform: "onnxruntime_onnx"
max_batch_size: 32

input [
  {
    name: "input"
    data_type: TYPE_FP32
    dims: [ 32 ]
  }
]
output [
  {
    name: "output"
    data_type: TYPE_FP32
    dims: [ 2 ]
  }
]

dynamic_batching {
  max_queue_delay_microseconds: 2000
}
```

#### Langkah 4: Jalankan Server Triton via Docker
```bash
docker run --rm -d --gpus all \
  --shm-size=1g \
  -p 8000:8000 -p 8001:8001 -p 8002:8002 \
  -v $(pwd)/model_repository:/models \
  nvcr.io/nvidia/tritonserver:23.10-py3 \
  tritonserver --model-repository=/models
```

#### Langkah 5: Jalankan Stress Testing Menggunakan `perf_analyzer`
Jalankan container performance evaluation NVIDIA:
```bash
docker run --rm -it --net=host nvcr.io/nvidia/tritonserver:23.10-py3-sdk \
  perf_analyzer -m linear_classifier \
  -u localhost:8001 -i gRPC \
  --concurrency-range 2:16:2 \
  --measurement-interval 5000
```
Amati perubahan throughput (infer/sec) dan tail latency (P99) seiring naiknya tingkat concurrency.

---

### 13. Exercise

#### Tingkat: Easy
- **Tugas**: Modifikasi file `export.py` pada direktori latihan agar mengekspor model dengan 3 layer Dense (`nn.Linear` $\to$ `nn.ReLU` $\to$ `nn.Linear` $\to$ `nn.ReLU` $\to$ `nn.Linear`), lalu periksa model ONNX yang dihasilkan menggunakan tool `onnx.checker.check_model`.
- **Ekspektasi Output**: Skrip Python berhasil melakukan validasi visual/grafik tanpa error validasi skema tensor.

#### Tingkat: Medium
- **Tugas**: Tambahkan blok Ensemble Scheduling pada file `config.pbtxt` di mana input dinormalisasi terlebih dahulu oleh layer preprocessing berbasis custom model sebelum dialirkan ke `linear_classifier`.
- **Ekspektasi Output**: Direktori Triton memiliki 3 model: `pipeline_model`, `preprocessor`, dan `linear_classifier`, di mana klien hanya memanggil endpoint `pipeline_model`.

#### Tingkat: Hard
- **Tugas**: Tulis skrip profiling Python native berbasis `asyncio` dan `grpc.aio` yang menembakkan 10.000 inference requests secara simultan dengan konkurensi 100 workers ke model Triton, hitung secara presisi distribusi histogram latensi P50, P90, P99, serta deteksi paket loss akibat server saturation.
- **Ekspektasi Output**: Script mencetak kalkulasi ringkasan metrik statistik latensi milidetik dan throughput final tanpa terjadi crash `UNAVAILABLE: Socket closed`.

---

### 14. Challenge

**Skenario**:
Perusahaan retail Anda memiliki model Vision Transformer (ViT-Base/16) untuk ekstraksi fitur katalog produk (224x224x3 input image). Model saat ini memiliki cold-start inference time sebesar 320ms di PyTorch GPU dan gagal melewati stress-test ketika traffic Black Friday tiba.

**Instruksi**:
1. Buat pipeline konversi yang mengubah ViT-Base PyTorch ke TensorRT Engine dengan format kuantisasi campuran (FP16 compute dengan INT8 activation/weights).
2. Tentukan skema kalibrasi yang mempertahankan akurasi top-1 model hingga $\Delta \le 0.5\%$.
3. Konfigurasi model repository Triton dengan multi-instance (`count: 2`) per GPU, serta tentukan nilai parameter `max_queue_delay_microseconds` yang optimal agar latensi end-to-end tidak melebihi **15ms** pada beban 1.500 QPS di single card NVIDIA A10G (24GB VRAM).
4. Dokumentasikan seluruh konfigurasi build dan justifikasi matematis di balik pemilihan queue delay.

---

### 15. Quiz Evaluasi Pemahaman

#### Pertanyaan Basic
1. Apa fungsi utama *Operator Fusion* dalam kompilasi model deep learning?
   - A. Menghapus bobot model yang bernilai 0.
   - B. Menggabungkan beberapa operasi mikro kernel menjadi satu untuk meminimalisasi transfer data antar register dan VRAM.
   - C. Mengubah model dari format single-thread menjadi multi-thread.
   - D. Menurunkan resolusi floating-point dari float64 menjadi float32.

2. Protokol jaringan mana yang memberikan latensi terendah dan throughput tertinggi untuk inference request skala enterprise di Triton Inference Server?
   - A. HTTP/1.1 REST dengan JSON body.
   - B. WebDAV binary transfer.
   - C. gRPC via HTTP/2 dengan binary Protobuf payloads.
   - D. GraphQL.

3. Mengapa kuantisasi simetris INT8 umumnya menggunakan nilai *Zero-Point* ($Z$) bernilai nol?
   - A. Karena representasi nilai nol float harus tepat jatuh di nol integer untuk menyederhanakan perkalian matriks komputasi GPU.
   - B. Karena nilai kuantisasi simetris tidak membutuhkan kalkulasi scale factor.
   - C. Karena format INT8 tidak memiliki kapasitas representasi bilangan negatif.
   - D. Untuk menghindari overflow pada tipe data unsigned.

4. Direktori model pada Triton Inference Server harus memiliki subdirektori numerik (misal: `1/`). Apa arti angka tersebut?
   - A. ID GPU target eksekusi.
   - B. Tingkat prioritas model execution.
   - C. Semantic model versioning.
   - D. Jumlah batch size yang didukung.

5. Manakah flag compiler TensorRT yang digunakan untuk mengeksekusi kompilasi model dengan batasan dimensi input yang berubah-ubah?
   - A. Constant Axis Optimizer.
   - B. Dynamic Optimization Profile.
   - C. Static Loop Unrolling.
   - D. Polyhedral Model Compiler.

#### Pertanyaan Intermediate
6. Pada kondisi apa Dynamic Batcher pada Triton Server akan langsung mengirim batch tensor ke GPU execution pipeline sebelum parameter `max_queue_delay_microseconds` terpenuhi?
   - A. Ketika ukuran batch di queue telah mencapai `max_batch_size`.
   - B. Ketika utilisasi GPU host berada di bawah 10%.
   - C. Ketika ada request berprioritas rendah yang masuk antrean.
   - D. Ketika CPU melempar sinyal interupsi kernel.

7. Mengapa kalibrasi menggunakan metode *Kullback-Leibler (KL) Divergence* lebih dipilih daripada *MinMax Calibration* pada aktivasi INT8 model deep learning?
   - A. Karena kalkulasi KL Divergence membutuhkan komputasi matematika yang jauh lebih ringan.
   - B. Karena metode MinMax rentan terhadap outlier ekstrem yang merusak rentang dinamis representasi layer.
   - C. Karena MinMax tidak didukung oleh perangkat keras NVIDIA Tensor Cores.
   - D. Karena KL Divergence tidak memerlukan dataset kalibrasi sampel.

8. Apa efek samping arsitektural utama jika nilai parameter `max_queue_delay_microseconds` disetel terlalu tinggi (misal: $500\text{ ms}$)?
   - A. GPU akan mengalami Out-Of-Memory.
   - B. Throughput server akan anjlok drastis mendekati 0.
   - C. Latensi individual request pada low-traffic condition akan melonjak mengikuti delay maksimum antrean.
   - D. Engine TensorRT akan corrupt saat runtime.

9. Fitur Triton Inference Server mana yang mengizinkan eksekusi beberapa request secara simultan pada satu core GPU fisik yang sama tanpa saling mengunci thread?
   - A. Single Instance Locking.
   - B. Instance Groups dengan isolated CUDA Streams.
   - C. Horizontal Pod Autoscaler.
   - D. Global Interpreter Lock bypass mechanism.

10. Apa risiko utama mendistribusikan binary file `.plan` TensorRT yang dikompilasi pada arsitektur GPU NVIDIA Ampere (A100) ke server produksi yang berjalan di arsitektur Hopper (H100)?
    - A. Server akan berjalan lebih lambat 50%.
    - B. Engine gagal di-load (*fail to deserialize*) karena instruksi biner micro-architecture berbeda.
    - C. Output komputasi menghasilkan nilai NaN di seluruh layer.
    - D. Driver CUDA secara otomatis melakukan transpilasi runtime on-the-fly.

#### Skenario Kasus Produksi
11. **Skenario A**: Tim Anda meluncurkan Triton Inference Server di Kubernetes. Saat traffic naik tajam, CPU usage melompat ke 100%, utilisasi GPU hanya 20%, dan latency request melonjak hingga timeout. Investigasi menunjukkan bahwa model diekspor dalam format PyTorch eager script dan protokol input menggunakan REST HTTP/1.1 JSON parsing array berukuran besar. Tindakan prioritas mana yang paling tepat?
    - A. Menambah replika pod secara otomatis melalui HPA.
    - B. Mengompilasi model ke TensorRT, beralih ke interface gRPC binary payload, dan mengaktifkan Pinned System Memory.
    - C. Menurunkan ukuran batch size model menjadi 1.
    - D. Mengganti tipe instance node GPU dengan kapasitas CPU clock lebih rendah.

12. **Skenario B**: Model klasifikasi teks INT8 TensorRT Anda menunjukkan drop metrik F1-score sebesar $12\%$ di lingkungan produksi dibandingkan dengan model baseline FP32, meskipun proses kuantisasi selesai tanpa warning compiler. Setelah dievaluasi, data kalibrasi kuantisasi berasal dari unit-test generator (`np.random.normal`). Apa akar masalahnya?
    - A. Arsitektur Transformer tidak mendukung operasi kuantisasi INT8 secara fundamental.
    - B. Distribusi data acak sintetis gagal merefleksikan distribusi aktivasi dan sparsity kosakata dunia nyata, memicu threshold clipping yang keliru.
    - C. File cache kalibrasi terhapus otomatis oleh sistem saat kompilasi selesai.
    - D. CUDA stream mengalami packet collision saat kompilasi berlangsung.

13. **Skenario C**: Server inference Anda mengalami random crash dengan log kernel `out of memory: Kill process (tritonserver)` (OOMKilled oleh Linux OS), padahal monitoring utilisasi VRAM GPU menunjukkan penggunaan VRAM baru mencapai 60%. Konfigurasi container manakah yang kemungkinan besar terabaikan?
    - A. Port forwarding gRPC belum dialokasikan secara eksklusif.
    - B. Parameter Docker shared memory (`/dev/shm`) belum dinaikkan dari nilai default 64MB sehingga system memory exhaust saat buffering batch besar.
    - C. Nilai max_batch_size pada `config.pbtxt` bernilai ganjil.
    - D. Model instance group belum dipetakan ke GPU ID 0.

---

#### Kunci Jawaban & Rasional Singkat

1. **B**: *Operator Fusion* meniadakan siklus write-read redundan dari SRAM ke High-Bandwidth VRAM dengan memaketkan komputasi mikro ke satu kernel GPU.
2. **C**: gRPC berbasis HTTP/2 mendukung multiplexing streaming dan serialisasi binary Protocol Buffers yang menghemat CPU cycles.
3. **A**: Penyelarasan titik nol floating point tepat pada integer nol menghindari penambahan bias matrix translation tambahan pada Tensor Cores.
4. **C**: Triton menggunakan subdirektori berbasis angka untuk semantic version tracking (`1/`, `2/`).
5. **B**: Dynamic Optimization Profile mendefinisikan batasan *min, optimal, dan max* shape agar compiler dapat mengalokasikan workspace graf dinamis.
6. **A**: Dynamic batching memprioritaskan batas kapasitas muatan; jika `max_batch_size` terpenuhi, batch langsung diproses tanpa menunggu sisa jendela waktu `max_queue_delay_microseconds`.
7. **B**: Outlier ekstrem pada aktivasi menyebabkan skala kuantisasi MinMax melebar, sehingga mayoritas distribusi data yang padat kehilangan resolusi bit presisinya. KL Divergence mengabaikan outlier untuk meminimalkan kehilangan informasi murni.
8. **C**: Request yang masuk saat sistem sepi harus menunggu durasi delay maksimal antrean sebelum dieksekusi, meningkatkan latensi P50/P99 pada kondisi low-QPS.
9. **B**: Triton menjalankan instance ganda pada CUDA streams yang berbeda, mengeksploitasi hardware parallelism GPU multiprocessors secara simultan.
10. **B**: TensorRT menghasilkan binary serialization yang terikat ketat dengan instruksi ISA dan micro-architecture chip GPU spesifik.
11. **B**: Bottleneck berada di serialisasi JSON via HTTP/1.1 di level CPU host dan interpretasi PyTorch eager execution. Kompilasi TensorRT dan gRPC binary bypass mengalihkan beban ke GPU.
12. **B**: Kalibrasi kuantisasi INT8 sangat bergantung pada representasi distribusi statistik realistik. Noise Gaussian buatan merusak kalkulasi relative entropy.
13. **B**: Triton dynamic batcher menggunakan host IPC shared memory (`/dev/shm`) untuk merangkai tensor request antar proses. Alokasi default Docker (64MB) memicu Kernel OS melempar SIGKILL jika terjadi alokasi melebihi batas.

---

### 16. Summary

Mengubah artefak machine learning dari pipeline eksperimental menjadi sistem penyajian berskala enterprise membutuhkan pemahaman komprehensif mengenai batasan hardware, hierarki memori GPU, serta rekayasa runtime inference. 

Pilar utama produksi performa tinggi mencakup:
- **Graph Optimization**: Menghilangkan abstraksi framework tingkat tinggi melalui kompilasi ONNX dan TensorRT, mengeksploitasi fusi kernel dan eliminasi kalkulasi redundan.
- **Kuantisasi Terkalibrasi**: Kompresi presisi data dari FP32 ke FP16/INT8 menggunakan algoritma KL-Divergence untuk menggandakan throughput inferensi Tensor Cores tanpa mengorbankan integritas model.
- **Serving Modern**: Memanfaatkan Triton Inference Server untuk Dynamic Batching, orkestrasi memory pinning, serta eksekusi concurrent instance yang memaksimalkan saturasi infrastruktur komputasi secara efisien dan terkontrol.