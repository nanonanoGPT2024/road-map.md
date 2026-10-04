# BAB 07: Enterprise Serving Platforms & Compilation
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis Arsitektur Kompilasi Inferensi**: Membedakan alur eksekusi graf komputasi (computation graph lowering) dari High-Level IR (PyTorch FX, TorchDynamo) menuju Low-Level IR (MLIR, TVM, TensorRT) hingga menghasilkan instruksi mesin mikro-arsitektur GPU (PTX/SASS).
2. **Mengonfigurasi dan Mengoptimasi Triton Inference Server**: Mengimplementasikan arsitektur *multi-model pipelining* menggunakan *Business Logic Scripting* (BLS) dan *Ensemble Models*, lengkap dengan *dynamic batching*, *model concurrency*, dan integrasi *CUDA Shared Memory*.
3. **Mendesain Infrastruktur Disaggregated LLM Serving**: Merancang dan mengoperasikan kluster *prefill-decode disaggregation* berskala produksi menggunakan vLLM/TensorRT-LLM, memisahkan *compute-bound phase* (prefill/prompt processing) dan *memory-bandwidth-bound phase* (token generation/decoding).
4. **Mengatasi Bottleneck Hardware & Runtime**: Mengidentifikasi dan memitigasi *GPU memory fragmentation*, *dynamic shape recompilation penalties*, serta *KV-cache starvation* melalui *kernel fusion*, *PagedAttention*, dan CUDA Graphs.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta diwajibkan menguasai:
*   **Sistem Komputasi Akselerator**: Pemahaman mendalam arsitektur GPU NVIDIA (Ampere, Hopper, Blackwell), hierarki memori (HBM3/e, SRAM/Shared Memory, L2 Cache, Register File), dan protokol interkoneksi (NVLink, NVSwitch, PCIe Gen5).
*   **Pemrograman Sistem & C++ Modern**: Pemahaman C++17/20 (RAII, smart pointers, threading concurrency, memory alignment) dan Python 3.11+ C-API.
*   **PyTorch Internals**: Memahami `torch.nn.Module`, autograd engine lifecycle, PyTorch Dispatcher, ATen library, serta mekanisme eksekusi eager execution vs graph capture.
*   **Dasar-Dasar Inferensi**: Konsep dasar kuantisasi (INT8, FP8, INT4 AWQ/GPTQ), batching statis vs dinamis, serta kalkulasi memori aktivasi dan model parameters.

---

### 3. Concept & Internal Architecture

Ekosistem *inference engineering* tingkat lanjut berfokus pada transisi dari *flexible eager execution* menuju *static deterministic computation* dengan memaksimalkan *hardware utilization* (FLOPS dan Memory Bandwidth).

```
+-----------------------------------------------------------------------------+
|                            COMPILATION PIPELINE                             |
|                                                                             |
|  [PyTorch Eager Code]                                                       |
|          |                                                                  |
|          v                                                                  |
|  [TorchDynamo] --------> Frame Evaluation & Bytecode Analysis               |
|          |                                                                  |
|          v                                                                  |
|  [AOTAutograd / FX Graph] -> High-Level IR (Target-Agnostic Operators)     |
|          |                                                                  |
|          v                                                                  |
|  [TorchInductor / TVM / MLIR / TensorRT] -> Lowering to Low-Level IR        |
|          |                                                                  |
|          +---> Loop Fusion, Memory Planning, Layout Transformation (NHWC)   |
|          |                                                                  |
|          v                                                                  |
|  [Codegen: C++/Triton/CUDA/PTX] -> JIT Compiler (NVCC/NVRTC)                |
|          |                                                                  |
|          v                                                                  |
|  [Binary SASS] ----------------> Direct Hardware Execution on SMs           |
+-----------------------------------------------------------------------------+
```

#### A. Lowering & Compilation Engine
Eksekusi Python konvensional memiliki *overhead* berupa interpretasi *bytecode*, alokasi memori berulang (*memory churn*), dan peluncuran kernel (*kernel launch overhead*) melalui CUDA runtime driver. 

1. **Graph Capture**: TorchDynamo mengintersepsi frame evaluasi Python pada tingkat C-API. Dynamo memisahkan bagian kode dinamis murni Python dari graf tensor PyTorch tanpa memerlukan *code rewriting* manual, menghasilkan graf representasi `torch.fx`.
2. **Intermediate Representation (IR) Lowering**: Graf ditransformasikan ke High-Level IR (AOTAutograd/FX), di mana optimasi aljabar (*constant folding*, *dead code elimination*) berlangsung. Selanjutnya, ditransformasikan ke Low-Level IR (seperti Triton IR atau MLIR dialect).
3. **Loop & Kernel Fusion**: Bottleneck utama model transformer seperti Transformer Decoder sering kali bersifat *memory-bandwidth bound* (misalnya operasi `Add` dilanjutkan `LayerNorm` dilanjutkan `GELU`). Kompiler menggabungkan (*fuse*) ketiga operasi ini ke dalam satu kernel CUDA. Data tetap berada di SRAM (*Shared Memory/Registers*) tanpa perlu dibaca/tulis berulang kali ke *High Bandwidth Memory* (HBM).
4. **Target Hardware Codegen**: Low-Level IR ditransformasikan ke PTX (*Parallel Thread Execution*), kemudian dikompilasi oleh assembler GPU ke SASS (*Source-level Assembly*) yang ditargetkan khusus ke arsitektur SM (*Streaming Multiprocessor*) GPU target.

#### B. Triton Inference Server Architecture
NVIDIA Triton mengelola *hardware lifecycle*, konkurensi model, dan perutean permintaan secara deterministik:

*   **Dynamic Batcher**: Agregator antrean tingkat hardware. Permintaan individual dari berbagai thread HTTP/gRPC dikumpulkan ke dalam satu batch komputasi berdasarkan parameter `max_queue_delay_microseconds` dan `max_batch_size`.
*   **Sequence Batcher**: Khusus untuk model stateful (seperti RNN atau LLM streaming) untuk menjamin pemetaan state/KV-cache ke instance model yang sama tanpa konflik ID sesi.
*   **BLS (Business Logic Scripting)**: Eksekusi C++ atau Python orchestration terpadu langsung di memori Triton. BLS mengizinkan model orkestrator (misal: pre-processing, embedding routing, ensemble reranking) berkomunikasi tanpa overhead serialisasi jaringan (menggunakan Triton C API dan *Shared Memory* IPC).

#### C. LLM Serving: Continuous Batching & Disaggregated Prefill/Decode
Sistem serving generasi terbaru untuk LLM mengadopsi pemisahan fase inferensi:
*   **Continuous / Iteration-Level Batching**: Menghilangkan inefisiensi *static padding*. Alih-alih menunggu seluruh batch selesai men-generate seluruh token hingga panjang maksimum, scheduler mengevaluasi status per-iterasi langkah decoding. Token yang menghasilkan tag `<eos>` langsung di-evict dari batch, dan request baru dari antrean dialokasikan secara instan ke dalam slot kosong.
*   **PagedAttention**: Manajemen KV-cache yang terinspirasi oleh *virtual memory paging* pada sistem operasi. KV-cache dialokasikan dalam blok-blok diskret berukuran tetap (misal: 16 atau 32 token). Menghilangkan fragmentasi memori internal dan eksternal, meningkatkan kapasitas penampungan batch hingga 2x-4x pada kapasitas HBM yang sama.
*   **Disaggregated Prefill/Decode**:
    *   *Prefill Node (Compute-Bound)*: Memproses prompt masukan dengan paralelisme tinggi (TFLOPS jenuh, saturasi Tensor Core). Operasi didominasi oleh *matrix multiplication* gemm standar.
    *   *Decode Node (Memory-Bandwidth Bound)*: Memproses satu token baru per request per iterasi. Mengalami batasan transfer data KV-cache dari HBM ke SRAM.
    *   *Interkoneksi*: KV-cache yang dihitung oleh Prefill Node ditransfer ke Decode Node via RDMA (*Remote Direct Memory Access*) over RoCEv2 atau InfiniBand, memotong latensi TTFT (*Time-to-First-Token*) tanpa membebani *decoding throughput*.

---

### 4. Why & What

| Dimensi | Serving Naif (FastAPI + PyTorch Eager) | Enterprise Serving Platform (Triton + TensorRT/vLLM) |
| :--- | :--- | :--- |
| **Concurrency Control** | Diblokir oleh Python Global Interpreter Lock (GIL); multi-process memicu replikasi model berlebih. | Manajemen multithread native C++, konkurensi instance model deterministik pada GPU yang sama. |
| **Batching Mechanism** | Static batching atau ad-hoc queue manual di level aplikasi; membuang komputasi akibat padding masif. | Iteration-level continuous batching + dynamic batch aggregation terintegrasi di layer runtime C-API. |
| **GPU Memory Safety** | Risiko tinggi *out-of-memory* (OOM) seketika saat lonjakan traffic; alokator memori CUDA terfragmentasi. | Pre-allocated static buffers, PagedAttention block pooling, circuit breaking, dan graceful queue throttling. |
| **Kernel Execution** | Eager kernel launches berulang memicu CPU overhead dan *GPU idle bubbles*. | Kernel fusion, CUDA Graphs capture (zero launch overhead), kompilasi JIT/AOT deterministik. |
| **Latency Consistency** | P99 latency fluktuatif tajam akibat garbage collection dan inter-process serialization overhead. | P99 latency stabil, komunikasi inter-model via POSIX/CUDA Shared Memory tanpa latensi jaringan. |

---

### 5. How (Workflow Detail)

Alur kerja deployment kompilasi dan serving enterprise:

```
[PyTorch Checkpoint] 
         │
         ▼
[Tracing / Graph Lowering via TorchDynamo] 
         │
         ▼
[Optimization & Kernel Fusion via TensorRT / TorchInductor]
         │
         ▼
[Engine Serialization (.engine / .pt2)]
         │
         ▼
[Packaging ke Triton Model Repository Directory]
         ├── config.pbtxt (Scheduling, Memory, Dynamic Batching Rules)
         └── 1/model.plan
         │
         ▼
[Triton Initialization & Memory Pre-allocation]
         ├── Load CUDA Kernels
         ├── Setup IPC & Shared Memory Pools
         └── Warmup runs & CUDA Graph Capture
         │
         ▼
[Serving Ingress: gRPC/HTTP API via Dynamic Batch Scheduler]
```

1. **Graph Capture & Optimization**:
   Model diekspor ke representasi statis menggunakan `torch.export` atau TensorRT builder API. Pada tahap ini, layer-layer seperti `Conv + BatchNorm` atau `QKV Projection GEMM` digabung. Dilakukan penentuan profile dimensi input (*min, opt, max shapes*).
2. **Model Serialization**:
   Engine biner diekspor. TensorRT menghasilkan file `.engine` / `.plan`, sedangkan TorchInductor menghasilkan *shared object* C++ (`.so`) atau artefak AOTI (`.pt2`).
3. **Penyusunan Model Repository**:
   Artefak diletakkan dalam hierarki direktori Triton beserta `config.pbtxt` yang mendefinisikan tipe scheduler, alokasi GPU instance, batasan antrean, dan input/output layout.
4. **Orkestrasi Pipeline (BLS / Ensemble)**:
   Jika inferensi melibatkan alur kompleks (misalnya: *Tokenizer C++ -> Embedding Lookup -> TensorRT Core -> Detokenizer*), buat ensemble definition atau C++ BLS script untuk mengeksekusi end-to-end inferensi secara in-memory.
5. **Runtime Ingress & Warmup**:
   Saat server boot, Triton menjalankan rangkaian *warmup requests* untuk memaksa inisialisasi CUDA context dan melakukan kompilasi JIT jika masih terdapat layer dinamis. Hal ini mencegah *latency spike* pada request pertama dari pengguna riil.

---

### 6. Analogy & Diagram ASCII

#### Analogi Konseptual
Bayangkan sebuah **Dapur Restoran Bintang Lima**:
*   *Serving Naif (FastAPI/Eager)*: Setiap kali pesanan (request) datang, koki (CPU) membaca resep langkah demi langkah dari buku, mengambil satu bahan dari gudang utama (HBM) ke meja potong (SRAM), memotongnya, lalu mengembalikannya ke gudang, baru mengambil bahan berikutnya. Jika ada 10 pesanan berbeda, koki memasak satu per satu, membuat pelanggan di antrean belakang kelaparan.
*   *Enterprise Serving + Compilation (Triton + Continuous Batching)*: Koki kepala telah mengompilasi resep: bahan-bahan diproses bersamaan dalam satu wajan besar (*Kernel Fusion*). Dapur menggunakan sistem ban berjalan (*Dynamic Batching*). Koki tidak menunggu satu meja selesai makan seluruh kursus makanan sebelum melayani meja lain; setiap kali ada piring kosong di meja mana pun, makanan berikutnya langsung disajikan dari wajan yang sama (*Continuous Batching & PagedAttention*). Gudang bahan terkoneksi via lift khusus berkecepatan tinggi (*CUDA Shared Memory*).

#### Arsitektur Topologi Produksi

```
                                  [API Gateway / Ingress Router]
                                                │
                     ┌──────────────────────────┴──────────────────────────┐
                     │ (gRPC Streaming / HTTP2)                            │
                     ▼                                                     ▼
      [Triton Serving Instance 01]                          [Triton Serving Instance 02]
   ┌─────────────────────────────────────┐               ┌─────────────────────────────────────┐
   │ [BLS Pipeline Orchestrator]         │               │ [BLS Pipeline Orchestrator]         │
   │  ├─ Tokenizer (C++ HuggingFace)     │               │  ├─ Tokenizer (C++ HuggingFace)     │
   │  └─ Dynamic Dispatcher              │               │  └─ Dynamic Dispatcher              │
   └───────────────┬─────────────────────┘               └───────────────┬─────────────────────┘
                   │                                                     │
         ┌─────────┴─────────┐                                 ┌─────────┴─────────┐
         │ (RDMA / NVLink)   │                                 │ (RDMA / NVLink)   │
         ▼                   ▼                                 ▼                   ▼
 ┌──────────────┐     ┌──────────────┐                 ┌──────────────┐     ┌──────────────┐
 │ PREFILL NODE │     │ DECODE NODE  │                 │ PREFILL NODE │     │ DECODE NODE  │
 │ (GPU 0, 1)   │────>│ (GPU 2, 3)   │                 │ (GPU 4, 5)   │────>│ (GPU 6, 7)   │
 │ Compute      │     │ Memory-BW    │                 │ Compute      │     │ Memory-BW    │
 │ TensorRT-LLM │ KV  │ Continuous   │                 │ TensorRT-LLM │ KV  │ Continuous   │
 │ Chunked      │Cache│ Batching     │                 │ Chunked      │Cache│ Batching     │
 │ Prefill      │Pool │ PagedAttn    │                 │ Prefill      │Pool │ PagedAttn    │
 └──────────────┘     └──────────────┘                 └──────────────┘     └──────────────┘
         ▲                   ▲                                 ▲                   ▲
         └───────────────────┴───────────────┬─────────────────┴───────────────────┘
                                             │
                                  [Distributed Shared Memory]
                                [KV-Cache Transfer Fabric: RDMA]
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: TorchInductor AOT Compilation dengan Dynamic Shapes

Contoh berikut menunjukkan cara mengompilasi model deep learning menggunakan `torch.compile` dengan backend TorchInductor dan dynamic shape profiling untuk inferensi produksi bebas Python GIL.

```python
import torch
import torch._dynamo
import time

# 1. Definisikan arsitektur inferensi berbasis Transformer block sederhana
class OptimizedAttentionBlock(torch.nn.Module):
    def __init__(self, dim: int = 1024, heads: int = 16):
        super().__init__()
        self.dim = dim
        self.heads = heads
        self.head_dim = dim // heads
        self.qkv = torch.nn.Linear(dim, dim * 3, bias=False)
        self.out_proj = torch.nn.Linear(dim, dim, bias=False)
        self.norm = torch.nn.LayerNorm(dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        residual = x
        x = self.norm(x)
        b, s, _ = x.shape
        qkv = self.qkv(x).reshape(b, s, 3, self.heads, self.head_dim).permute(2, 0, 3, 1, 4)
        q, k, v = qkv[0], qkv[1], qkv[2]
        
        # Menggunakan FlashAttention kernel terintegrasi via SDPA
        attn_out = torch.nn.functional.scaled_dot_product_attention(q, k, v, is_causal=True)
        attn_out = attn_out.permute(0, 2, 1, 3).reshape(b, s, self.dim)
        return self.out_proj(attn_out) + residual

# 2. Setup Device & Model
device = "cuda" if torch.cuda.is_available() else "cpu"
model = OptimizedAttentionBlock().to(device=device, dtype=torch.float16).eval()

# 3. Compile graf menggunakan backend inductor dengan mode 'max-autotune'
# Dynamic=True memungkinkan batch size dan sequence length bervariasi tanpa re-kompilasi
torch._dynamo.reset()
compiled_model = torch.compile(
    model,
    backend="inductor",
    mode="max-autotune",
    dynamic=True,
    options={"triton.cudagraphs": True}
)

# 4. Warm-up phase untuk memicu JIT tracing dan CUDA Graph Capture
print("[INFO] Melakukan Warmup & Graph Capture...")
dummy_input = torch.randn(4, 512, 1024, device=device, dtype=torch.float16)
with torch.inference_mode():
    for _ in range(5):
        _ = compiled_model(dummy_input)
print("[INFO] Warmup Selesai. Model siap untuk inferensi deterministik.")
```

#### B. Practical Example: Production Triton Model Configuration & Custom Python/C-API Backend

Berikut adalah implementasi konfigurasi dan backend kustom NVIDIA Triton Inference Server untuk model inferensi enterprise dengan dynamic batching dan CUDA memory optimization.

##### File: `model_repository/transformer_engine/config.pbtxt`
```protobuf
name: "transformer_engine"
backend: "python"
max_batch_size: 64

input [
  {
    name: "input_ids"
    data_type: TYPE_INT32
    dims: [ -1 ]
  },
  {
    name: "attention_mask"
    data_type: TYPE_INT32
    dims: [ -1 ]
  }
]

output [
  {
    name: "embeddings"
    data_type: TYPE_FP16
    dims: [ 1024 ]
  }
]

# Konfigurasi Dynamic Batching Tingkat Lanjut
dynamic_batching {
  preferred_batch_size: [ 8, 16, 32, 64 ]
  max_queue_delay_microseconds: 5000
  preserve_ordering: false
}

# Manajemen Alokasi Instance GPU
instance_group [
  {
    count: 2
    kind: KIND_GPU
    gpus: [ 0 ]
  }
]

# Optimasi Akselerasi Runtime
optimization {
  cuda {
    graphs: 1
    busy_wait_events: 1
  }
}
```

##### File: `model_repository/transformer_engine/1/model.py`
```python
import json
import torch
import triton_python_backend_utils as pb_utils

class TritonPythonModel:
    def initialize(self, args):
        """Inisialisasi engine inferensi, CUDA stream, dan pre-alokasi memori."""
        self.model_config = json.loads(args['model_config'])
        self.device = f"cuda:{args['target_device_id']}"
        
        # Load bobot yang sudah dikompilasi (AOT Inductor / TorchScript)
        # Di lingkungan riil: load file serialize .pt2 atau .engine
        self.model = torch.nn.Sequential(
            torch.nn.Embedding(30522, 1024),
            torch.nn.Linear(1024, 1024),
            torch.nn.LayerNorm(1024)
        ).to(self.device).half().eval()
        
        # Membaca konfigurasi output types
        output_config = pb_utils.get_output_config_by_name(self.model_config, "embeddings")
        self.output_dtype = pb_utils.triton_string_to_numpy(output_config['data_type'])
        
        # Menginisialisasi CUDA Stream eksklusif per instance untuk memotong default stream synchronization
        self.cuda_stream = torch.cuda.Stream(device=self.device)

    def execute(self, requests):
        """
        Batch request executor. requests berisi kumpulan inferensi yang 
        telah diagregasi oleh Triton Dynamic Batcher.
        """
        responses = []
        batch_input_ids = []
        batch_masks = []
        req_lens = []

        # Ekstraksi tensor input tanpa round-trip serialization CPU-GPU
        for request in requests:
            in_ids_triton = pb_utils.get_input_tensor_by_name(request, "input_ids")
            # Konversi zero-copy pointer langsung ke PyTorch Tensor pada GPU
            in_ids_torch = torch.as_tensor(in_ids_triton.as_numpy(), device=self.device)
            batch_input_ids.append(in_ids_torch)
            req_lens.append(in_ids_torch.shape[0])

        with torch.cuda.stream(self.cuda_stream):
            with torch.inference_mode():
                # Pad secara dinamis sesuai tensor terpanjang di dalam sub-batch yang terbentuk
                padded_inputs = torch.nn.utils.rnn.pad_sequence(
                    batch_input_ids, batch_first=True, padding_value=0
                )
                
                # Eksekusi komputasi forward
                hidden_states = self.model[0](padded_inputs)
                projected = self.model[1](hidden_states)
                normalized = self.model[2](projected)
                
                # Mean pooling sederhana untuk representasi embedding sequence
                sentence_embeddings = normalized.mean(dim=1).to(torch.float16)

        # Tunggu stream GPU lokal selesai mengeksekusi kernel
        self.cuda_stream.synchronize()

        # Rekonstruksi respons Triton kembali ke masing-masing pemanggil secara independen
        for idx in range(len(requests)):
            single_emb = sentence_embeddings[idx].detach().cpu().numpy().astype(self.output_dtype)
            out_tensor = pb_utils.Tensor("embeddings", single_emb)
            inference_response = pb_utils.InferenceResponse(output_tensors=[out_tensor])
            responses.append(inference_response)

        return responses

    def finalize(self):
        """Cleanup handler memori saat worker dimatikan."""
        torch.cuda.empty_cache()
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Arsitektur Pemrosesan Fraud & Summarization FinTech Global
*   **Profil Perusahaan**: Platform Pembayaran Digital Skala Global (50,000 requests/second pada transaksi finansial P99 SLA < 15ms; 1,200 req/sec untuk LLM Automated Dispute Explainer P99 TTFT < 300ms).
*   **Masalah Arsitektural**:
    1. Sistem sebelumnya menggunakan kluster monolith Python/FastAPI di belakang Load Balancer: GPU utilization hanya mencapai 23% rata-rata, namun latensi melonjak drastis saat terjadi spike transaksi akhir bulan.
    2. Dynamic shape mismatch memicu *recompilation storm* pada model PyTorch, menyebabkan spike latensi (P99 hingga 2.800ms) dan timeout berantai (cascading failure).
    3. LLM serving untuk resolusi sengketa memonopoli memori HBM GPU A100 (80GB), memblokir alokasi model deteksi fraud berbasis GNN/Transformer tabular.

#### Solusi Arsitektur
1. **Pemisahan Jalur Berdasarkan Compute Profile**:
   * *Critical Path (Fraud Detection)*: Mengonversi model tabular-transformer ke **TensorRT FP16 Engine**. Mengimplementasikan explicit dimension profile:
     - Min: `[1, 128]`
     - Optimal: `[128, 128]`
     - Max: `[512, 128]`
     Model di-deploy di Triton Inference Server menggunakan *CUDA Shared Memory IPC*. Komunikasi dari Go Gateway ke Triton dilakukan via Shared Memory tanpa overhead soket TCP/IP loopback.
   * *High-Capacity Path (Disaggregated LLM Dispute Explainer)*:
     - Kluster dibagi menjadi 4 Prefill Nodes (GPU Hopper H100 SXM5, memproses prompt panjang ringkasan riwayat nasabah) dan 8 Decode Nodes (GPU A100-80GB, dioptimalkan untuk continuous generation token-by-token).
     - KV-cache dipindahkan antar-node menggunakan protokol RDMA (Remote Direct Memory Access) over 400Gbps RoCEv2.
2. **Implementasi Triton Dynamic Batching & Queue Throttling**:
   - `max_queue_delay_microseconds`: diset ke `2000` (2 ms) untuk mengumpulkan batch hingga 128 transaksi per proses komputasi GPU, menghasilkan *sweet spot* throughput maksimum tanpa mengorbankan SLA 15ms.

#### Metrik Hasil Transformasi Produksi
*   **Throughput Puncak**: Meningkat 4.3x dari 11,500 req/sec menjadi 50,000+ req/sec pada armada hardware yang sama.
*   **P99 Latency Fraud Check**: Turun dari 85ms ke 8.4ms (perbaikan ~90%).
*   **Rata-rata Utilitas GPU**: Meningkat dari 23% ke 88% saturasi compute core.
*   **Infrastruktur Savings**: Menghemat belanja cloud (GPU compute billing) sebesar $1.8 Juta USD per tahun melalui konsolidasi node dan eliminasi idle compute bubble.

---

### 9. Trade-offs

Mengonfigurasi platform kompilasi dan serving tingkat lanjut menuntut kompromi rekayasa:

```
               Throughput (Dynamic Batching Tinggi)
                            ▲
                           / \
                          /   \
                         /     \
                        /       \
                       /  SWEET  \
                      /   SPOT    \
                     /             \
                    /               \
 Latency ◄─────────-------------------─────────► Compilation Overhead
 (Strict Realtime SLA)                          (AOT/JIT, Memory Footprint)
```

1. **Throughput vs. P99 Latency (Queue Delay)**:
   * Menambahkan `max_queue_delay_microseconds` pada Dynamic Batcher meningkatkan throughput dan saturasi Tensor Core secara masif.
   * *Konsekuensi*: Permintaan pertama yang tiba di antrean harus menunggu jendela waktu delay habis sebelum dikirim ke GPU, secara inheren mendegradasi batas bawah latensi (P50 & P99).
2. **Kompilasi AOT (TensorRT/Inductor Static) vs. Fleksibilitas JIT Eager Execution**:
   * Graf statis yang dikompilasi TensorRT memberikan performa komputasi tercepat dan konsumsi memori terendah melalui kernel fusion dan graph optimization.
   * *Konsekuensi*: Tidak ramah terhadap input dimensi yang sangat bervariasi (*ragged inputs*). Penggunaan di luar profil shape yang didefinisikan dapat menyebabkan fallback lambat atau *fatal execution abort*.
3. **Kuantisasi Agresif (FP8/INT4) vs. Degradasi Akurasi Numerik**:
   * Format FP8 / INT4 (AWQ/GPTQ) melipatgandakan *memory bandwidth efficiency* dan menaikkan batasan context window LLM.
   * *Konsekuensi*: Potensi degradasi pada tugas penalaran kompleks (*complex reasoning*), pergeseran distribusi nilai token langka (*outlier activations*), serta dibutuhkannya proses kalibrasi dataset (*calibration steps*) yang memakan waktu sebelum deployment.

---

### 10. Common Mistakes & Troubleshooting

#### 1. Kesalahan Fatal: TorchDynamo Dynamic Shape Recompilation Loops
*   **Gejala**: Latensi berfluktuasi secara masif; CPU utilization 100%, log sistem mencatat pesan berulang: `[TorchDynamo] Recompiling graph...`.
*   **Penyebab**: Script model memiliki percabangan logika Python native berdasarkan nilai tensor internal (`if tensor.item() > 0:`), atau shape input yang bervariasi tanpa mengaktifkan `dynamic=True` pada konfigurasi compiler.
*   **Troubleshooting**:
    Gunakan utility diagnosis internal Dynamo:
    ```bash
    TORCH_LOGS="+dynamo" TORCHDYNAMO_VERBOSE=1 python serve.py
    ```
    Identifikasi baris kode pemecah graf (*graph break*) via:
    ```python
    import torch._dynamo
    explanation = torch._dynamo.explain(model, sample_input)
    print(explanation)
    ```

#### 2. Triton Server C++ Memory Leaks via Python Backend
*   **Gejala**: Server Triton crash setelah beberapa jam/hari beroperasi dengan status `Exit Code 137` (OOM Killer oleh Linux OS), padahal memori HBM GPU masih longgar.
*   **Penyebab**: Memindahkan tensor Triton Python Backend (`pb_utils.Tensor`) ke NumPy atau PyTorch tanpa melakukan dereferensi memori C++ secara eksplisit, menyebabkan akumulasi memori di shared memory POSIX (`/dev/shm`).
*   **Mitigasi**:
    Pastikan container Docker dijalankan dengan flag alokasi IPC Shared Memory yang memadai:
    ```bash
    docker run --gpus all --shm-size=16g -p 8000:8000 -p 8001:8001 -p 8002:8002 triton-server
    ```
    Hapus tensor intermediate secara eksplisit di script Python:
    ```python
    del in_ids_triton, in_ids_torch
    ```

#### 3. CUDA Graphs Capture Failures
*   **Gejala**: Error `CUDA error: operation not permitted when stream is capturing`.
*   **Penyebab**: Kode yang dijalankan saat graph capture memanggil alokasi memori dinamis (`cudaMalloc`) di dalam capturing loop, sinkronisasi stream eksplisit (`torch.cuda.synchronize()`), atau operasi I/O file/socket.
*   **Mitigasi**: Alokasikan seluruh buffer tensor secara statis sebelum capture dimulai. Pastikan tidak ada komunikasi inter-thread atau inter-device di dalam capture region.

---

### 11. Best Practices (Production Checklist)

Gunakan daftar checklist ini sebelum mempromosikan model ke cluster produksi:

*   [ ] **Model Profiling Definitif**: Profiling telah dijalankan menggunakan NVIDIA Nsight Systems (`nsys`) untuk memverifikasi bahwa tidak ada *GPU bubbles*, *excessive kernel launches*, atau transfer implisit Host-to-Device (PCIe) selama inferensi.
*   [ ] **Static Pre-allocation**: Alokator memori GPU dibatasi (misal: setting `gpu_memory_fraction` atau pre-alokasi pool KV-cache vLLM) untuk mencegah tabrakan alokasi CUDA runtime.
*   [ ] **Warmup Sequences**: Konfigurasi `model_warmup` didefinisikan secara eksplisit di file `config.pbtxt` Triton dengan ragam variasi dimensi input untuk memicu kompilasi kernel dan CUDA graphs sebelum menerima traffic hidup.
*   [ ] **Host CPU Pinning & NUMA Awareness**: Thread worker Triton di-pin ke socket CPU yang memiliki interkoneksi langsung (PCIe root complex) dengan GPU target guna menghindari latensi bus QPI/UPI.
*   [ ] **Triton Health & Liveness Probes**: Endpoint `/v2/health/ready` dan `/v2/health/live` terintegrasi dengan readiness probe Kubernetes.
*   [ ] **Circuit Breakers**: Implementasi batasan panjang antrean antrean request (`max_queue_size`) di layer gateway untuk menolak request (mengembalikan HTTP 429 / gRPC ResourceExhausted) daripada membiarkan P99 latency memburuk secara katastropik.

---

### 12. Hands-on Practice

Buat dan simpan seluruh file implementasi berikut di dalam direktori `hands-on/m02/`.

#### Struktur Direktori
```
hands-on/m02/
├── Dockerfile
├── docker-compose.yml
├── client_benchmark.py
└── model_repository/
    └── deep_transformer/
        ├── 1/
        │   └── model.py
        └── config.pbtxt
```

#### Langkah 1: Siapkan Environment Deployment
Buat file `hands-on/m02/Dockerfile`:
```dockerfile
FROM nvcr.io/nvidia/tritonserver:24.01-py3

RUN pip install --no-cache-dir \
    torch==2.2.0 \
    transformers==4.38.0 \
    numpy==1.26.4 \
    tritonclient[all]==2.42.0

WORKDIR /workspace
```

Buat file `hands-on/m02/docker-compose.yml`:
```yaml
version: '3.8'

services:
  triton:
    build: .
    shm_size: '8gb'
    ulimits:
      memlock: -1
      stack: 67108864
    ports:
      - "8000:8000"
      - "8001:8001"
      - "8002:8002"
    volumes:
      - ./model_repository:/models
    command: ["tritonserver", "--model-repository=/models", "--strict-model-config=false", "--log-verbose=0"]
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

#### Langkah 2: Buat Model Repository Triton
Buat file `hands-on/m02/model_repository/deep_transformer/config.pbtxt`:
```protobuf
name: "deep_transformer"
backend: "python"
max_batch_size: 32

input [
  {
    name: "input_ids"
    data_type: TYPE_INT32
    dims: [ 128 ]
  }
]

output [
  {
    name: "output_logits"
    data_type: TYPE_FP32
    dims: [ 128, 512 ]
  }
]

dynamic_batching {
  preferred_batch_size: [ 8, 16, 32 ]
  max_queue_delay_microseconds: 10000
}

instance_group [
  {
    count: 1
    kind: KIND_GPU
    gpus: [ 0 ]
  }
]
```

Buat file `hands-on/m02/model_repository/deep_transformer/1/model.py`:
```python
import torch
import triton_python_backend_utils as pb_utils

class TritonPythonModel:
    def initialize(self, args):
        self.device = "cuda:0"
        # Dummy network yang disederhanakan
        self.linear = torch.nn.Linear(128, 512).to(self.device).eval()

    def execute(self, requests):
        responses = []
        batch_tensors = []
        for req in requests:
            inp = pb_utils.get_input_tensor_by_name(req, "input_ids")
            batch_tensors.append(torch.as_tensor(inp.as_numpy(), device=self.device).float())

        stacked_input = torch.stack(batch_tensors, dim=0)
        
        with torch.inference_mode():
            # Eksekusi komputasi
            out = self.linear(stacked_input)

        out_np = out.detach().cpu().numpy()
        for idx in range(len(requests)):
            triton_out = pb_utils.Tensor("output_logits", out_np[idx])
            responses.append(pb_utils.InferenceResponse(output_tensors=[triton_out]))
            
        return responses

    def finalize(self):
        pass
```

#### Langkah 3: Eksekusi dan Verifikasi Client Benchmark
Jalankan container Triton:
```bash
cd hands-on/m02/
docker compose up -d --build
```

Buat script `hands-on/m02/client_benchmark.py`:
```python
import tritonclient.http as httpclient
import numpy as np
import time

def run_inference():
    client = httpclient.InferenceServerClient(url="localhost:8000")
    
    # Tunggu kesiapan server
    while not client.is_server_ready():
        time.sleep(1)
    
    input_data = np.ones((1, 128), dtype=np.int32)
    inputs = [httpclient.InferInput("input_ids", [1, 128], "TYPE_INT32")]
    inputs[0].set_data_from_numpy(input_data)
    
    start_time = time.perf_counter()
    latencies = []
    
    print("[INFO] Mengirimkan 200 batch requests...")
    for _ in range(200):
        t0 = time.perf_counter()
        _ = client.infer(model_name="deep_transformer", inputs=inputs)
        latencies.append((time.perf_counter() - t0) * 1000)

    print(f"P50 Latency: {np.percentile(latencies, 50):.2f} ms")
    print(f"P95 Latency: {np.percentile(latencies, 95):.2f} ms")
    print(f"P99 Latency: {np.percentile(latencies, 99):.2f} ms")

if __name__ == "__main__":
    run_inference()
```

Jalankan pengujian performa:
```bash
python client_benchmark.py
```

---

### 13. Exercise

#### Level 1 - Easy
Ubah konfigurasi file `config.pbtxt` pada `hands-on/m02/model_repository/deep_transformer/` untuk mengaktifkan 2 instance GPU concurrency pada GPU 0, lalu verifikasi peningkatan throughput menggunakan `perf_analyzer` bawaan Triton.
*Kriteria Sukses*: Output `perf_analyzer` menunjukkan peningkatan inferensi per detik (Concurrency = 4).

#### Level 2 - Medium
Gantilah dummy model pada `1/model.py` dengan model Hugging Face RoBERTa mini nyata. Bungkus eksekusi forward model menggunakan `torch.compile(model, backend="inductor")` di dalam method `initialize()`. Pastikan `execute()` memproses input tensor secara dynamic tanpa memicu re-kompilasi.
*Kriteria Sukses*: Pengujian 500 requests dengan sequence length dinamis (berkisar antara 32 hingga 128 token) tidak menghasilkan warning Dynamo recompilation pada standard output server.

#### Level 3 - Hard
Implementasikan skema Triton Business Logic Scripting (BLS) di mana model `tokenizer_bls` menerima raw string array via input gRPC, melakukan tokenisasi sub-word di CPU menggunakan Rust Tokenizers C-bindings, lalu mengirimkan tensor ID melalui C-API pointer/CUDA Shared Memory ke model `transformer_engine` tanpa melewati serialisasi soket loopback.
*Kriteria Sukses*: Menghasilkan end-to-end P99 latency di bawah 12ms untuk raw text string input.

---

### 14. Challenge

**Skenario**:
Sebuah platform streaming video global memiliki model ensemble *Video Content Moderation* multimodal yang terdiri dari 3 model:
1. ResNet3D (Video Feature Extractor - Heavy Compute, input batch dinamis)
2. Audio Whisper Encoder (Audio Transcribe - Dynamic audio duration, irregular shapes)
3. Cross-Attention Fusion LLM (Multi-modal decision engine - Memory-bound, autoregressive)

Saat ini seluruh sistem berjalan di Kubernetes pod terpisah dengan FastAPI via REST JSON serialization. Latensi P99 mencapai 1,450ms, dan cluster sering kehabisan GPU memory (CUDA OOM) saat terjadi lonjakan video viral berdurasi 60 detik.

**Tugas Arsitektur**:
Rancang arsitektur serving zero-copy terpadu berbasis Triton Inference Server dan vLLM/TensorRT-LLM:
1. Buat blueprint arsitektur yang mengeliminasi transport serialization overhead antara ke-3 model menggunakan Triton Ensemble atau BLS.
2. Definisikan strategi alokasi memori agar video feature extraction yang bersifat *bursty* tidak merebut pool memori PagedAttention milik modul LLM.
3. Rancang mekanisme *graceful degradation* (circuit breaker & dynamic request prioritization) saat incoming load melampaui 3x lipat batas *provisioned throughput*.

*Instruksi Pengerjaan*: Sajikan rancangan arsitektur lengkap beserta diagram aliran memori, pseudocode Triton BLS model controller, dan konfigurasi `config.pbtxt` yang detail dan valid.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic Questions
1. Apa fungsi utama dari lapisan abstraksi TorchDynamo pada PyTorch 2.x?
2. Mengapa static padding pada inferensi batch transformer standar menyebabkan pemborosan komputasi pada GPU?
3. Sebutkan perbedaan utama antara protocol HTTP/REST standar dan gRPC binary protocol dalam konteks serving model performa tinggi.
4. Apa yang dimaksud dengan *Kernel Fusion*, dan jenis bottleneck hardware apa yang dipecahkannya?
5. Mengapa PagedAttention lebih efisien dalam mengelola memori KV-cache dibanding alokasi memori tensor standar PyTorch?

#### Intermediate Questions
6. Pada kondisi apa pengaktifan *Dynamic Batching* di Triton justru merugikan nilai P99 Latency dari sebuah sistem inferensi?
7. Bagaimana CUDA Graphs memotong overhead CPU launch pada model-model deep learning, dan apa batasannya terhadap bentuk dimensi masukan (input shapes)?
8. Jelaskan perbedaan mendasar antara *Prefill Phase* dan *Decode Phase* pada LLM inference dari sudut pandang *Arithmetic Intensity* (FLOPS/Byte ratio)!
9. Bagaimana cara kerja mekanisme Triton *Business Logic Scripting* (BLS) dalam mengeksekusi inferensi multi-model tanpa latensi overhead jaringan inter-process?
10. Mengapa kompilasi AOT (Ahead-Of-Time) sering kali menghasilkan performa lebih deterministik dibanding JIT (Just-In-Time) untuk sistem serving berskala enterprise?

#### Production Scenarios
11. **Kasus A**: Server Triton Anda tiba-tiba mengalami lonjakan drastis pada waktu respon (P99 dari 20ms melonjak ke 400ms). Saat diperiksa via `nvidia-smi`, penggunaan daya (*power draw*) dan utilisasi GPU SM justru anjlok ke angka 15%. Log tidak mencatat adanya error. Komponen arsitektur apa yang paling mungkin menjadi biang keladi (*root cause*), dan bagaimana langkah investigasi konkret Anda?
12. **Kasus B**: Kluster LLM serving Anda mengalami error `CUDA Out of Memory` secara sporadis ketika beberapa user mengirimkan prompt dengan panjang 4.000 token secara bersamaan, padahal rata-rata panjang prompt user lain hanya 150 token. Konfigurasi apa pada level engine LLM (vLLM / TensorRT-LLM) yang harus disesuaikan untuk mengisolasi kasus ini tanpa mengurangi throughput user lain?
13. **Kasus C**: Anda ditugaskan mengompilasi model Vision-Language yang kompleks menggunakan TensorRT. Selama tahap profiling, engine builder macet (*hang*) dan membutuhkan waktu lebih dari 6 jam sebelum akhirnya gagal karena alokasi RAM CPU host habis. Apa konfigurasi builder yang salah, dan bagaimana Anda mengatasinya?

---

#### Kunci Jawaban & Pembahasan Quiz

##### Jawaban Basic
1. **Fungsi TorchDynamo**: Mengintersepsi frame evaluasi bytecode Python pada level C-API untuk menangkap graf komputasi tensor PyTorch secara transparan dan aman tanpa memutus kompatibilitas fitur Python dinamis.
2. **Inefisiensi Static Padding**: GPU terpaksa melakukan perkalian matriks (FLOPs) terhadap token dummy (nilai padding nol) agar dimensi seluruh sequence dalam batch seragam, membuang alokasi Tensor Core dan bandwidth memori untuk kalkulasi yang nilainya dibuang.
3. **HTTP vs gRPC**: HTTP/REST menggunakan text serialization (JSON) yang membutuhkan proses parsing CPU intensif dan transport layer yang relatif lambat; gRPC menggunakan HTTP/2 biner multiplexed dengan serialisasi Protobuf yang cepat, zero-copy ready, dan hemat bandwidth.
4. **Kernel Fusion & Bottleneck**: Penggabungan instruksi beberapa operasi berurutan (misal: Bias Add + Relu + Layernorm) ke dalam satu fungsi kernel CUDA tunggal. Ini memecahkan bottleneck *Memory Bandwidth* (mengurangi trip baca/tulis tensor perantara ke HBM GPU).
5. **PagedAttention vs Standar**: Alokasi standar membutuhkan blok memori contiguous yang besar sehingga memicu fragmentasi internal/eksternal dan pemesanan berlebih (over-allocation). PagedAttention memecah KV-cache ke dalam halaman diskret non-contiguous, memungkinkan pemanfaatan memori mendekati 100%.

##### Jawaban Intermediate
6. **Dynamic Batching Latency Penalty**: Jika traffic masukan rendah atau jarang, permintaan pertama harus menunggu selama periode timeout (`max_queue_delay_microseconds`) hingga batch terisi penuh. Penundaan statis ini langsung mendegradasi P99 latency pada skenario traffic tipis.
7. **CUDA Graphs**: Merekam urutan eksekusi kernel dan dependensi grafiknya pada level driver GPU sekali saja, lalu meluncurkannya kembali dengan satu instruksi CPU tunggal (mengeliminasi ratusan CPU overhead syscall). Batasannya: graph capture menuntut alamat pointer memori dan dimensi tensor yang mutlak statis (tidak mendukung dynamic shapes secara native tanpa multi-graphs).
8. **Prefill vs Decode Arithmetic Intensity**:
   * *Prefill*: Memproses seluruh prompt secara paralel, menghasilkan *high arithmetic intensity* (Compute-Bound / GEMM), menjenuhkan Tensor Cores.
   * *Decode*: Memproses token satu per satu di mana setiap token membutuhkan pembacaan seluruh KV-cache masa lalu dari HBM ke SRAM, menghasilkan *low arithmetic intensity* (Memory-Bandwidth Bound / GEMV).
9. **Mekanisme BLS**: BLS mengeksekusi pipeline di dalam address space process yang sama atau melalui C-API IPC Triton. Data tensor dioper antar model melalui pointer memori GPU atau pointer memori sistem (Shared Memory) tanpa proses serialisasi JSON/Protobuf dan tanpa melalui TCP stack loopback.
10. **AOT vs JIT**: AOT mengompilasi seluruh kernel secara statis sebelum deployment, sehingga latency request pertama sama stabilnya dengan request keseribu. JIT memicu kompilasi di tengah-tengah runtime saat menemui shape atau branch baru, menyebabkan *unpredictable latency spikes* (cold start overhead).

##### Jawaban Production Scenarios
11. **Pembahasan Kasus A**:
    * *Root Cause*: Bottleneck di sisi Host CPU (Pipeline Preprocessing / Postprocessing) atau thread contention di Dynamic Batcher. GPU kekurangan suplai data (*GPU starvation*). Kemungkinan lain: terjadi CPU GIL contention pada Python Backend akibat loop CPU parsing serialization data.
    * *Langkah Investigasi*: Jalankan `nsys profile` untuk melihat visualisasi CUDA stream timeline (apakah terdapat jeda panjang/bubbles di antara peluncuran kernel). Periksa utilisasi CPU host per core (apakah ada satu core 100% dan terjadi thread locking). Evaluasi `/v2/metrics` Triton untuk metrik `nv_inference_queue_duration_us` vs `nv_inference_compute_input_duration_us`.
12. **Pembahasan Kasus B**:
    * *Solusi*: Aktifkan **Chunked Prefill** pada engine serving LLM (misal: parameter `--enable-chunked-prefill` pada vLLM atau TensorRT-LLM). Chunked prefill memecah prompt masukan yang masif (4.000 token) menjadi beberapa potongan kecil (misal: chunk size 512 token) dan menyisipkannya bersamaan dengan request decoding reguler. Ini mencegah lonjakan alokasi KV-cache secara seketika dan menstabilkan latensi TTFT seluruh antrean antrean.
13. **Pembahasan Kasus C**:
    * *Root Cause*: TensorRT Engine Builder secara default mencoba mengevaluasi ratusan kombinasi kernel (*tactic search*) untuk seluruh profil shape yang tidak dibatasi, memakan ruang paging RAM CPU dan swap space.
    * *Solusi*: Batasi profiling tactics dengan menetapkan flag `BuilderFlag::kDISABLE_TIMING_CACHE` dinonaktifkan, gunakan tactic library yang terfokus (misal: batasi cuDNN / cuBLAS specific tactics). Definisikan batasan *Optimization Profile* secara ketat (`min`, `opt`, `max` shape) jangan biarkan span terlalu lebar, dan turunkan workspace size limit via `config->setMemoryPoolLimit(MemoryPoolType::kWORKSPACE, size)`.

---

### 16. Summary

Implementasi enterprise serving dan kompilasi inferensi berfokus pada efisiensi perangkat keras melalui reduksi overhead eksekusi:

1. **Efisiensi Kompilasi**: Transisi dari eager model ke *lowered static/dynamic representations* (TorchInductor, TensorRT) merevolusi inferensi deep learning melalui *kernel fusion*, eliminasi instruksi redundan, dan pemanfaatan micro-architecture SASS secara langsung.
2. **Kekuatan Serving Terpadu**: NVIDIA Triton Inference Server menyediakan kontrol runtime mutlak melalui *Dynamic Batching*, *Concurrency Instances*, dan alur data *in-memory* berkecepatan tinggi via Shared Memory dan C-API BLS.
3. **Arsitektur LLM Generasi Baru**: Pemisahan fase *Prefill-Decode Disaggregation*, alokasi memori berdasar *PagedAttention*, dan penjadwalan *Continuous Iteration Batching* merupakan fondasi wajib dalam menekan latensi TTFT dan memaksimalkan *generation throughput* pada model transformer skala besar.