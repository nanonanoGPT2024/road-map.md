# Enterprise Inference Engineering: High-Throughput & Low-Latency AI Systems

Repository ini berisi silabus kurikulum komprehensif 10 Bab untuk penguasaan domain **Inference Engineering**. Materi ini dirancang untuk Machine Learning Engineers (MLE), Systems Engineers, dan Backend Platform Engineers yang bertransisi dari fase pelatihan model (*model training/fine-tuning*) menuju rekayasa komputasi inferensi skala produksi yang deterministik, berbiaya optimal, dan berlatensi ultra-rendah (*sub-second latencies*).

---

## 1. Course Overview & Engineering Mindset

Inferensi model bahasa besar (*Large Language Models*) dan model generatif modern bukan sekadar mengeksekusi metode `model.forward()`. Inferensi produksi adalah masalah **sistem komputasi terdistribusi**, **manajemen hierarki memori**, dan **optimasi throughput versus latensi**.

```
Training Phase                   Inference Engineering Phase
+-----------------------+        +-----------------------------------------------+
| Optimize Loss         |  --->  | Optimize TTFT (Time-To-First-Token)           |
| Maximize GPU Compute  |        | Optimize ITL (Inter-Token Latency)            |
| Static Batching       |        | Maximize Concurrency per GPU Dollar ($/Token) |
| Compute-Bound         |        | Memory-Bound (KV-Cache, Bandwidth Bottleneck) |
+-----------------------+        +-----------------------------------------------+
```

### Filosofi Sistem & Prinsip Kerja
1. **Memory Bandwidth Is the Real Bottleneck**: Komputasi LLM autoregresif didominasi oleh transfer data bobot dan KV-cache dari High Bandwidth Memory (HBM) ke SRAM GPU (GEMV-bound). Memahami *Roofline Model* dan *Arithmetic Intensity* adalah syarat mutlak.
2. **Deterministic Latency Budgets**: Produksi enterprise menuntut SLA ketat: P99 Time-To-First-Token (TTFT) dan P99 Inter-Token-Latency (ITL). Fluktuasi performa adalah bug arsitektural.
3. **Dynamic Resource Allocation**: Beban inferensi bersifat bursty dan bervariasi dalam panjang konteks. Penggunaan teknik seperti *PagedAttention*, *Continuous Batching*, dan *Chunked Prefill* membedakan platform pemula dengan engine enterprise.
4. **Hardware-Software Co-Design**: Menguasai interaksi antara CUDA kernel, GPU streaming multiprocessor (SM), NVLink interconnects, precision scaling (FP8, INT4), dan runtime compiler (TensorRT-LLM, vLLM).

---

## 2. Learning Roadmap

```text
Inference Engineering Roadmap
│
├── [Bab 01] Foundations of ML Inference & Hardware Mechanics
│   ├── Tokenomics, FLOPs/Token, & Hardware Profiling
│   └── The Roofline Model: Compute-Bound vs. Memory-Bound
│
├── [Bab 02] Transformer Computation & KV-Cache Dynamics
│   ├── Prefill Phase vs. Decode Phase Mechanics
│   ├── KV-Cache Growth, Memory Footprint, & Fragmentation
│   └── Context Window Scaling (RoPE, YaRN, ALiBi)
│
├── [Bab 03] High-Throughput Serving Engines & Paged Scheduling
│   ├── Continuous / Dynamic In-Flight Batching
│   ├── PagedAttention Memory Virtualization
│   └── Chunked Prefill & Hybrid Execution Scheduling
│
├── [Bab 04] Quantization & Precision Engineering
│   ├── Weight-Only vs. Weight-Activation (W8A8, W4A16, FP8)
│   ├── Post-Training Quantization (AWQ, GPTQ, SmoothQuant)
│   └── Dequantization Overhead, Packed GEMM, & CUDA Cores
│
├── [Bab 05] Latency Optimization & Speculative Execution
│   ├── Speculative Decoding & Medusa Architecture
│   ├── FlashAttention-2 / FlashAttention-3 & Kernel Fusion
│   └── Constrained Decoding & Grammar-Guided Acceleration
│
├── [Bab 06] Distributed Inference & Parallelism Schemes
│   ├── Tensor Parallelism (TP) for Mega-Models
│   ├── Pipeline (PP) and Context/Sequence Parallelism (CP/SP)
│   └── All-Reduce, All-Gather, & NCCL Topology Tuning
│
├── [Bab 07] Enterprise Serving Platforms & Compilation
│   ├── Triton Inference Server Deep-Dive
│   ├── TensorRT-LLM Graph Compilation & Kernel Selection
│   └── Semantic Caching & Smart Gateway Routing
│
├── [Bab 08] Compound Inference Pipelines & Embeddings
│   ├── Embedding & Cross-Encoder Serving (Sub-10ms SLAs)
│   ├── Speculative Retrieval-Augmented Generation (RAG)
│   └── Prefix Caching & Multi-Turn State Reuse
│
├── [Bab 09] Observability, Profiling, & Benchmarking
│   ├── Inference Telemetry: TTFT, ITL, Generation Throughput
│   ├── GPU Profiling: Nsight Systems & PyTorch Profiler
│   └── Load Testing, Stress Profiling, & Synthetic Traces
│
└── [Bab 10] Production Operations, Edge, & Cost Economics
    ├── Kubernetes GPU Scheduling (MIG, Time-Slicing, KEDA)
    ├── Serverless GPU Optimization & Cold-Start Mitigation
    └── FinOps: Unit Economics ($ per 1M Output Tokens)
```

---

## 3. Detail Modul Pembelajaran

### Bab 01: Foundations of ML Inference & Hardware Mechanics
Membangun pemahaman kuantitatif tentang bagaimana bobot model dan token diterjemahkan ke dalam instruksi perangkat keras dan siklus clock memori GPU.

- **Modul 01-1**: [Analisis Komputasi Token dan Estimasi FLOPs](./01-inference-fundamentals/01-hardware-primitives-and-roofline.md)
  - Formula analitik FLOPs per token (forward pass training vs. inference).
  - Karakteristik arsitektur GPU modern: H100/A100 SRAM, HBM3e, Tensor Cores, dan interconnect throughput (NVLink vs. PCIe Gen5).
- **Modul 01-2**: [The Roofline Model & Arithmetic Intensity](./01-inference-fundamentals/02-transformer-inference-mechanics.md)
  - Identifikasi batas performa sistem (*Operational Intensity* vs. *Memory Bandwidth*).
  - Mengapa inferensi LLM bergeser dari Compute-bound (saat *prefill*) ke Memory-bound (saat *decoding*).
  - Studi kasus: Menghitung theoretical maximum token generation rate pada NVIDIA A100-SXM4-80GB.

---

### Bab 02: Transformer Computation & KV-Cache Dynamics
Membedah struktur komputasi internal Transformer selama generasi autoregresif dan implikasinya terhadap konsumsi memori VRAM.

- **Modul 02-1**: [Dinamika Komputasi Prefill vs. Decode Phase](./02-kv-cache-architecture/01-prefill-vs-decode-dynamics.md)
  - GEMM (General Matrix Multiply) pada prefill versus GEMV (General Matrix-Vector) pada decode.
  - Dampak Time-To-First-Token (TTFT) terhadap user experience dan load spike backend.
- **Modul 02-2**: [KV-Cache Memory Footprint & Fragmentasi](./02-kv-cache-architecture/02-kv-cache-memory-allocation.md)
  - Kalkulasi ukuran KV-cache: `2 × 2 × n_layers × n_heads × d_head × precision × context_length`.
  - Masalah alokasi memori kontigu statis (*internal & external memory fragmentation*).
- **Modul 02-3**: [Context Window Scaling & Position Embeddings](./02-kv-cache-architecture/03-context-window-scaling-rope.md)
  - Dampak RoPE (Rotary Position Embeddings), YaRN, dan ALiBi terhadap *KV computation cache overhead*.
  - Strategi mitigasi retensi memori pada dokumen panjang (32k s/d 128k context).

---

### Bab 03: High-Throughput Serving Engines & Paged Scheduling
Mempelajari arsitektur internal engine inferensi modern (seperti vLLM) yang merevolusi throughput penayangan model LLM.

- **Modul 03-1**: [Continuous & Dynamic In-Flight Batching](./03-high-throughput-serving/01-continuous-batching-scheduler.md)
  - Mengatasi masalah *naive static batching* (padding token waste).
  - Algoritma penjadwalan *iteration-level scheduling* (Orca architecture).
- **Modul 03-2**: [PagedAttention: Virtual Memory Virtualization untuk GPU](./03-high-throughput-serving/02-paged-attention-deep-dive.md)
  - Menerapkan konsep *Operating System Virtual Memory & Paging* ke VRAM GPU.
  - Implementasi *block table*, pemetaan pointer non-kontigu, dan *zero memory waste*.
- **Modul 03-3**: [Chunked Prefill & Hybrid Execution Scheduling](./03-high-throughput-serving/03-chunked-prefill-hybrid-execution.md)
  - Mitigasi kelaparan proses decode (*decode starvation*) akibat batch prefill masif.
  - Interleaving token prefill dan decode dalam satu siklus iterasi (Sarathi-Serve approach).

---

### Bab 04: Quantization & Precision Engineering
Optimasi representasi numerik bobot dan aktivasi untuk menurunkan footprint memori dan melipatgandakan kecepatan transfer HBM.

- **Modul 04-1**: [Post-Training Quantization (PTQ) Paradigms](./04-quantization-and-compression/01-post-training-quantization-w8a8-w4a16.md)
  - Perbedaan mendasar W8A8 (Weights & Activations) vs W4A16 (Weight-only).
  - Dampak kuantisasi terhadap degradasi perplexity dan akurasi logika model.
- **Modul 04-2**: [Advanced Quantization Schemes: AWQ, GPTQ, dan FP8](./04-quantization-and-compression/02-advanced-schemes-gptq-awq-fp8.md)
  - Activation-aware Weight Quantization (AWQ): Proteksi outlier channels.
  - GPTQ: Second-order error compensation via Hessian matrix.
  - FP8 (E4M3 vs E5M2) native acceleration pada arsitektur Hopper/Ada Lovelace.
- **Modul 04-3**: [Dequantization Overhead & Kernel Optimizations](./04-quantization-and-compression/03-dequantization-overhead-kernel-support.md)
  - Meminimalkan latensi konversi tipe data on-the-fly di SRAM.
  - Marlin & ExLlamaV2 high-performance CUDA kernels untuk inferensi INT4.

---

### Bab 05: Latency Optimization & Speculative Execution
Teknik tingkat lanjut untuk mereduksi Inter-Token Latency (ITL) di bawah batas fisik *memory-bandwidth bound*.

- **Modul 05-1**: [Speculative Decoding Mechanics](./05-latency-and-speculative-decoding/01-speculative-decoding-mechanisms.md)
  - Skema Draft Model vs Target (Verifier) Model.
  - Rejection Sampling, Verification Trees, dan hitungan ekspektasi acceptance rate ($\alpha$).
- **Modul 05-2**: [FlashAttention-2, FlashAttention-3 & Kernel Fusion](./05-latency-and-speculative-decoding/02-flashattention-and-kernel-fusion.md)
  - Tiling dan IO-awareness: Menghindari bolak-balik I/O antara HBM dan SRAM.
  - FlashDecoding: Paralelisasi decoding phase di seluruh Tensor Core blocks.
- **Modul 05-3**: [Constrained & Structured Generation Optimization](./05-latency-and-speculative-decoding/03-structured-generation-acceleration.md)
  - Akselerasi output valid JSON / Regex via Finite State Machines (FSM).
  - Mengatasi penalti latensi pada masking logit (Outlines vs SGLang runtime).

---

### Bab 06: Distributed Inference & Parallelism Schemes
Penskalaan inferensi untuk model-model yang melebihi kapasitas memori satu GPU tunggal (e.g., Llama-3-70B/405B).

- **Modul 06-1**: [Tensor Parallelism (TP) Deep Dive](./06-distributed-inference/01-tensor-parallelism-deep-dive.md)
  - Megatron-LM tensor slicing: Column Parallel Linear dan Row Parallel Linear.
  - Mengurangi latensi komunikasi All-Reduce pada cluster NVLink vs. PCIe.
- **Modul 06-2**: [Pipeline & Context/Sequence Parallelism (PP & CP/SP)](./06-distributed-inference/02-pipeline-and-sequence-parallelism.md)
  - Pengurangan bubble overhead pada inferensi multi-node via Pipeline Parallelism.
  - Sequence Parallelism untuk konteks 128k+: Ring Attention dalam eksekusi inferensi.
- **Modul 06-3**: [NCCL Topology Tuning & InfiniBand Fabrics](./06-distributed-inference/03-multi-node-nccl-communication.md)
  - Kalibrasi environment variable NCCL (`NCCL_BUFFSIZE`, `NCCL_CROSS_NIC`).
  - Identifikasi NUMA node alignment dan PCIe bus contention.

---

### Bab 07: Enterprise Serving Platforms & Compilation
Membangun platform penayangan kelas industri menggunakan server inferensi standar enterprise.

- **Modul 07-1**: [Triton Inference Server Architecture](./07-enterprise-serving-engines/01-triton-inference-server-architecture.md)
  - Multi-model orchestration, dynamic batching, dan shared memory IPC.
  - Triton C++ Backend integration untuk vLLM dan TensorRT-LLM.
- **Modul 07-2**: [TensorRT-LLM Graph Compilation & Engine Building](./07-enterprise-serving-engines/02-tensorrt-llm-compilation.md)
  - Parsing ONNX/HuggingFace checkpoints ke TensorRT execution graphs.
  - Ahead-of-Time (AOT) compilation, auto-tuning kernel GEMM, dan memory pooling.
- **Modul 07-3**: [Semantic Caching & Smart Gateway Routing](./07-enterprise-serving-engines/03-semantic-caching-routing-gateways.md)
  - Arsitektur cache semantik multi-tier (Redis + Vector Search) untuk bypass model pass.
  - Model multiplexing dan dynamic routing berdasarkan panjang prompt dan latency budget.

---

### Bab 08: Compound Inference Pipelines & Embeddings
Mengoptimalkan sistem inferensi AI modular yang melibatkan multiple non-autoregressive dan autoregressive models.

- **Modul 08-1**: [Sub-10ms Embedding & Cross-Encoder Serving](./08-compound-inference-systems/01-embedding-and-reranker-serving.md)
  - Optimasi model BERT/Bi-Encoder menggunakan ONNX Runtime + INT8 TensorRT.
  - Padding reduction dan dynamic token sorting untuk batched embeddings throughput.
- **Modul 08-2**: [Speculative RAG Pipeline Optimization](./08-compound-inference-systems/02-speculative-rag-pipeline-optimization.md)
  - Parallel chunk reranking dan streaming response generation.
  - Minimasi latency overhead dari network I/O antarmuka Vector Database dan Inference Engine.
- **Modul 08-3**: [Prefix Caching & Multi-Turn State Reuse](./08-compound-inference-systems/03-prefix-caching-prompt-state-reuse.md)
  - Shared system prompts caching (Radix Attention pada SGLang).
  - Reuse alokasi memori KV-cache untuk skenario multi-turn conversational agents.

---

### Bab 09: Observability, Profiling, & Benchmarking
Pengukuran performa inferensi yang presisi secara matematis dan isolasi *bottleneck* mikroarsitektur.

- **Modul 09-1**: [Metrik Inti Inferensi: TTFT, ITL, dan Effective Troughput](./09-benchmarking-and-observability/01-llm-inference-metrics-ttft-itl.md)
  - Menghitung P50, P90, P99 Time-To-First-Token (TTFT) dan Inter-Token-Latency (ITL).
  - Mengukur concurrency limit sebelum terjadi degradasi eksponensial (Queue Latency cliff).
- **Modul 09-2**: [GPU Kernel Profiling: NVIDIA Nsight & PyTorch Profiler](./09-benchmarking-and-observability/02-gpu-profiling-nsight-and-torch-profiler.md)
  - Tracing timeline eksekusi CUDA: Analisis kernel launch overhead dan bubble idle.
  - Identifikasi GPU Warp Occupancy, Memory Throttle, dan DRAM Bandwidth Saturation.
- **Modul 09-3**: [Automated Stress Testing & Realistic Trace Replay](./09-benchmarking-and-observability/03-load-testing-and-stress-benchmarks.md)
  - Pengujian beban menggunakan `genai-perf` dan kustom Locust trace simulators.
  - Pemodelan variasi Poisson arrival rate untuk mensimulasikan trafik dunia nyata.

---

### Bab 10: Production Operations, Edge, & Cost Economics
Operasionalisasi infrastruktur inferensi dalam skala besar dengan fokus pada ketahanan (*resilience*) dan FinOps.

- **Modul 10-1**: [Kubernetes GPU Orchestration & KEDA Autoscaling](./10-production-deployment-and-cost/01-k8s-gpu-orchestration-keda-autoscaling.md)
  - Kubernetes device plugins, Multi-Instance GPU (MIG), dan GPU fractionalization.
  - Autoscaling berbasis metrik real-time: Pending requests queue & KV-cache saturation via Prometheus.
- **Modul 10-2**: [Serverless GPU Infrastructure & Cold-Start Mitigation](./10-production-deployment-and-cost/02-serverless-gpu-and-cold-start-mitigation.md)
  - Optimasi model checkpoint streaming (safetensors direct memory mapping).
  - Container image layer optimization untuk container startup sub-10 detik.
- **Modul 10-3**: [Inference FinOps: Analisis Biaya Unit per Token](./10-production-deployment-and-cost/03-finops-and-cost-per-million-tokens.md)
  - Pemodelan biaya: Spot instances vs. Reserved instances vs. Hosted APIs.
  - Formula perhitungan unit economics: Total Cost of Ownership (TCO) per $1\text{M}$ Output Tokens.

---

## 4. Enterprise Capstone Project

### Judul Proyek
**"Architecting and Deploying an Ultra-Low Latency, High-Throughput Sovereign LLM Gateway with Distributed TensorRT-LLM and Triton"**

```
[Clients: API, Web, Agent Workers]
                 │
                 ▼
     [Reverse Proxy / Envoy Gateway]
                 │
                 ▼
┌────────────────────────────────────────────────────────┐
│  AI Routing Gateway (Rust / Golang)                   │
│  - Semantic Cache Layer (DragonflyDB / Redis)         │
│  - Token Bucket Rate Limiter & Priority Queue         │
│  - Chunked Context Partitioning                       │
└────────────────┬───────────────────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────────────────┐
│  Triton Inference Server Cluster (Multi-Node / Multi-GPU)
│  ┌──────────────────────────────────────────────────┐  │
│  │ TensorRT-LLM Execution Engine (Orchestrated)     │  │
│  │ - Base Model: Llama-3-70B-Instruct (FP8 / AWQ)   │  │
│  │ - Speculative Drafter: Llama-3-8B-Instruct       │  │
│  │ - PagedAttention + Chunked Prefill Scheduler     │  │
│  │ - Tensor Parallelism: TP=4 (NVLink Interconnect) │  │
│  │ - Radix / Prefix Caching Enabled                 │  │
│  └──────────────────────────────────────────────────┘  │
└────────────────┬───────────────────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────────────────┐
│  Telemetry & Infrastructure Plane                     │
│  - OpenTelemetry Traces + Prometheus Metrics Export   │
│  - Grafana Dashboards: TTFT, ITL, KV-Cache Saturation  │
│  - KEDA Autoscaler based on Engine Request Queuing    │
└────────────────────────────────────────────────────────┘
```

### Objektif Proyek
Membangun infrastruktur inferensi produksi tingkat enterprise end-to-end yang meng-host **Llama-3-70B-Instruct** dengan dukungan akselerasi **Speculative Decoding** (menggunakan model draft teroptimasi Llama-3-8B), ditayangkan melalui **Triton Inference Server** dengan backend **TensorRT-LLM**.

### Spesifikasi Teknis & Constraint
1. **Model Stack**:
   - Target Model: Llama-3-70B-Instruct terkuantisasi FP8 (atau INT4-AWQ jika dieksekusi pada arsitektur non-Hopper).
   - Draft Model: Llama-3-8B-Instruct (FP8 / INT8-GEMM).
2. **Cluster & Topology**:
   - Minimum 4x GPU cluster (NVIDIA A100-80GB SXM atau H100-80GB HBM3) yang terhubung via high-speed NVLink.
   - Tensor Parallelism (TP) di-lock pada nilai $4$.
3. **Serving Invariants**:
   - PagedAttention memory management dengan custom block size configuration.
   - KV-cache reuse diaktifkan untuk repeated system prompts (Prefix Caching).
   - Dynamic In-Flight batching dengan batasan max concurrent tokens terkontrol untuk menghindari out-of-memory (OOM).

### Target SLA & Metrik Kinerja Enterprise
Sistem yang dibangun harus lolos stress test otomatis (`genai-perf`) dengan batasan:
- **P99 Time-To-First-Token (TTFT)**: $\le 120\text{ ms}$ (pada input prompt 1.024 token).
- **P99 Inter-Token-Latency (ITL)**: $\le 15\text{ ms}$ per token (pada output length 512 token).
- **Sustained Aggregate Throughput**: $\ge 2.500\text{ output tokens/sec}$ pada kondisi concurrency penuh ($100+$ continuous parallel workers).
- **Memory Overhead**: Zero out-of-memory (OOM) failures selama running time 60 menit continuous load.

### Komponen Pengiriman (Deliverables)
1. **`engine/`**: Skrip build engine TensorRT-LLM terotomatisasi (konfigurasi builder, pemotongan bobot model TP=4, konversi kuantisasi).
2. **`gateway/`**: Gateway routing ringan (berbasis Go atau Rust) dengan integrasi Semantic Caching dan parsing streaming SSE (Server-Sent Events).
3. **`infra/`**: Helm Charts Kubernetes dan KEDA scaled objects untuk provisioning cluster Triton di private/public cloud.
4. **`benchmarks/`**: Suite benchmark load-testing lengkap dengan laporan hasil Nsight Systems profiling traces (`.nsys-rep`) yang membuktikan tidak adanya bubble pipeline yang tidak wajar pada GPU SMs.

### Rubrik Evaluasi Capstone

| Kategori | Bobot | Kriteria Kelulusan Enterprise |
| :--- | :--- | :--- |
| **Throughput & Latency SLA** | 30% | Memenuhi target P99 TTFT $\le 120\text{ ms}$ dan ITL $\le 15\text{ ms}$ di bawah beban kerja konkuren tinggi. |
| **Engine Configuration** | 25% | TensorRT-LLM engine terkompilasi optimal (menggunakan FP8/AWQ, FlashDecoding, Speculative Verification yang benar). |
| **Resilience & Scalability** | 20% | Penanganan lonjakan trafik tanpa memory crash (OOM), fallback gracefully jika draft model ditolak, KEDA autoscaling bekerja deterministik. |
| **Observability & Profiling** | 15% | Dashboard pemantauan real-time memetakan TTFT, ITL, Paged KV-cache block usage, dan analisis bottleneck via Nsight trace. |
| **Code Architecture & Docs** | 10% | Setup reproducible via automated scripts (IaC/Docker), arsitektur modular, dan dokumentasi operasional runbook yang jelas. |

---

## 5. Prasyarat & Lingkungan Pengembangan

Sebelum memulai modul pertama, pastikan lingkungan teknis Anda memenuhi kebutuhan:
- **Hardware**: Akses ke minimal 1x NVIDIA GPU dengan arsitektur Ampere (A10G, A100) atau Hopper (H100) dengan minimum VRAM 24GB (rekomendasi: 80GB SXM cluster untuk distributed bab).
- **Software**: CUDA Toolkit 12.2+, Docker dengan NVIDIA Container Toolkit, Python 3.10+, dan Git LFS.
- **Fundamental Knowledge**: Pemahaman solid tentang Transformer architecture, dasar-dasar pemrograman paralel CUDA/C++, dan familiarity dengan container orchestration (Kubernetes).