# BAB 01: Fondasi dan Arsitektur
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi (Inference Engineering)

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis dan Membedah Arsitektur Runtime Inference Modern**: Memahami alur eksekusi komputasi Large Language Model (LLM) pada level hardware (SRAM, HBM, Tensor Cores) dan memory manager.
- **Mengimplementasikan Optimasi KV Cache Lanjutan**: Merancang dan merekayasa subsistem alokasi memori non-contiguous seperti *PagedAttention* dan *RadixAttention* untuk mengeliminasi fragmentasi memori GPU internal hingga mendekati 0%.
- **Membangun Dynamic Continuous Batching Scheduler**: Mengembangkan scheduler berbasis iterasi (iteration-level scheduling) untuk menggantikan static request-level batching guna memaksimalkan throughput (tokens/sec) tanpa mendegradasi target Service Level Objective (SLO).
- **Menerapkan Multi-GPU Parallelism Strategies**: Mengonfigurasi dan mengoptimalkan Tensor Parallelism (TP) dan Pipeline Parallelism (PP) menggunakan NCCL all-reduce/all-gather primitives untuk mendistribusikan beban memori dan komputasi model bernilai miliaran parameter.
- **Mendesain Arsitektur Produksi Resilien**: Mengintegrasikan model serving engine (seperti vLLM/TensorRT-LLM) dengan proxy orchestration, load balancer terdistribusi, dan telemetry framework untuk menjamin p99 Time-To-First-Token (TTFT) dan Time-Per-Output-Token (TPOT) yang deterministik.

---

### 2. Prerequisites

Sebelum mempelajari modul ini, Anda wajib menguasai:
- **Arsitektur Transformer**: Self-Attention mechanism, Query/Key/Value matrix projections, multi-head attention (MHA), multi-query attention (MQA), dan grouped-query attention (GQA).
- **GPU Architecture Fundamentals**: Arsitektur dasar NVIDIA GPU (Streaming Multiprocessors [SM], High Bandwidth Memory [HBM], L1/L2 Cache, SRAM, Warp scheduling, dan Memory Bandwidth Bound vs Compute Bound operations).
- **Pemrograman Sistem & Konkurensi**: Asynchronous I/O di Python (`asyncio`), threading, multiprocessing, dan shared-memory primitives.
- **Networking & Distributed Primitives**: Protokol gRPC, HTTP/2 streaming, IPC (Inter-Process Communication), serta collective communication primitives (All-Reduce, All-Gather, Reduce-Scatter).

---

### 3. Concept & Internal Architecture

Inference Engineering modern bukan sekadar mengeksekusi model via framework seperti `model.forward()`, melainkan menyelesaikan persoalan optimasi rekayasa sistem hardware-software co-design:

```
[Client Requests]
       │
       ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        Inference Server Engine                         │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ Iteration-Level Scheduler (Continuous Batching)                   │  │
│  │  - Prefill Queue (Compute Bound)                                 │  │
│  │  - Decode Queue (Memory-Bandwidth Bound)                         │  │
│  │  - Chunked Prefill Arbiter                                       │  │
│  └──────────────────────────────────┬───────────────────────────────┘  │
│                                     │ Token-by-Token Iteration Step    │
│  ┌──────────────────────────────────▼───────────────────────────────┐  │
│  │ KV Cache Memory Manager (PagedAttention)                         │  │
│  │  - Physical Block Table (HBM Pools)                              │  │
│  │  - Logical-to-Physical Address Translation Engine                │  │
│  │  - Block Sharing & Copy-on-Write (Prefix Caching)                │  │
│  └──────────────────────────────────┬───────────────────────────────┘  │
│                                     │ Pointers to Cache Blocks         │
│  ┌──────────────────────────────────▼───────────────────────────────┐  │
│  │ Distributed Execution Engine (Tensor Parallel via NCCL)          │  │
│  │                                                                  │  │
│  │    GPU 0 (Rank 0)                 GPU 1 (Rank 1)                 │  │
│  │  ┌────────────────────────┐     ┌────────────────────────┐       │  │
│  │  │ Column Parallel QKV    │     │ Column Parallel QKV    │       │  │
│  │  │ Attention Kernel       │     │ Attention Kernel       │       │  │
│  │  │ Row Parallel Linear    │     │ Row Parallel Linear    │       │  │
│  │  └───────────┬────────────┘     └───────────┬────────────┘       │  │
│  │              └─────────── NCCL All-Reduce ──┘                    │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
```

#### 3.1. Karakteristik Komputasi: Prefill Phase vs. Decode Phase
Siklus hidup inferensi LLM terbagi menjadi dua fase dengan karakteristik performa hardware yang berlawanan:
1. **Fase Prefill (Prompt Processing)**:
   - Input: $N$ token secara simultan.
   - Karakteristik: **Compute-Bound**. Operasi GEMM (General Matrix Multiply) mendominasi, di mana rasio Arithmetic Intensity tinggi ($FLOPs/Byte \gg 1$). Tensor Cores beroperasi mendekati utilisasi puncak (Peak TFLOPS).
   - Metrik Kritis: **TTFT (Time-To-First-Token)**.
2. **Fase Decode (Autoregressive Generation)**:
   - Input: 1 token per langkah komputasi secara sekuensial.
   - Karakteristik: **Memory Bandwidth-Bound**. Operasi GEMV (General Matrix-Vector) mendominasi, di mana arithmetic intensity sangat rendah. Setiap token baru mengharuskan transfer seluruh weight model dan riwayat KV Cache dari HBM ke SRAM.
   - Metrik Kritis: **TPOT (Time-Per-Output-Token)** / Inter-Token Latency (ITL).

#### 3.2. KV Cache Bottleneck & PagedAttention
Pada vanilla auto-regressive generation, representasi Key dan Value dari seluruh token sebelumnya disimpan di GPU VRAM untuk menghindari komputasi ulang $O(N^2)$.
- Ukuran memori KV Cache untuk satu model per token:
  $$\text{Memori}_{\text{KV}} = 2 \times 2 \times L \times H_{\text{kv}} \times D \times \text{sizeof(dtype)}$$
  *(Keterangan: $2$ untuk Key dan Value, $2$ untuk bytes FP16/BF16, $L$ = Layers, $H_{\text{kv}}$ = KV Heads, $D$ = Head Dimension).*
- **Masalah Vanilla Allocation**: Alokasi buffer contiguous menghasilkan *internal fragmentation* (alokasi dialokasikan untuk `max_seq_len` terburuk) dan *external fragmentation*.
- **PagedAttention Mechanism**: Mengadopsi prinsip Virtual Memory paging sistem operasi:
  - KV Cache dipartisi menjadi blok-blok fisik statis berukuran tetap (misal: 16 atau 32 token).
  - Model logical KV Cache merujuk ke tabel pemetaan blok fisik (`Block Table`).
  - Alokasi memori dilakukan secara dinamik berbasis alokasi blok per blok sesuai ekspansi token baru secara on-demand, mereduksi pemborosan memori hingga $< 4\%$.

#### 3.3. Continuous Batching (Iteration-Level Scheduling)
Static Batching mengunci batch hingga sequence terpanjang selesai generate, menyebabkan GPU kelaparan (underutilization) akibat *padding bubbles*. Continuous Batching memperkenalkan paradigma:
- Eksekusi dijadwalkan pada level iterasi token (*step*), bukan pada level request.
- Request yang selesai generate (*hit EOS* atau *max_tokens*) segera dikeluarkan dari batch saat iterasi tersebut usai.
- Request baru dari prefill queue langsung disisipkan ke dalam slot batch yang kosong pada iterasi berikutnya.

#### 3.4. Distributed Parallelism: Tensor Parallelism (TP)
Ketika parameter model dan KV Cache melebihi kapasitas memori satu kartu GPU:
- **Megatron-LM Style 1D Tensor Parallelism**:
  - Linear layer pertama (Projection/MLP First Layer) dipartisi secara **Column Parallel** ($Y_1 = X W_1$, $Y_2 = X W_2$).
  - Linear layer kedua (Out-Projection/MLP Second Layer) dipartisi secara **Row Parallel** ($Z = Y_1 W_3 + Y_2 W_4$).
  - Komunikasi: Membutuhkan operasi primitif `NCCL All-Reduce` pada akhir row-parallel layer untuk menjumlahkan output parsial antar-GPU.

---

### 4. Why & What

| Dimensi | Naive PyTorch Serving | Optimized Inference Engine (vLLM/TGI/TRT-LLM) |
| :--- | :--- | :--- |
| **KV Cache Allocation** | Contiguous static allocation (OOM rentan terjadi) | Paged memory, zero-fragmentation, prefix caching |
| **Batching Strategy** | Static Request-Level Batching | Dynamic Continuous/Iteration-Level Batching |
| **Hardware Saturation** | Buruk (< 20% Model FLOPs Utilization / MFU) | Tinggi (50% - 75% MFU) |
| **Tail Latency (p99)** | Sangat berfluktuasi akibat Head-of-Line blocking | Konsisten dengan Chunked Prefill & Iteration Preemption |
| **Throughput Scaling** | Sub-linear, dibatasi kapasitas VRAM statis | Linear, kapasitas batch adaptif berbasis kapasitas token fisik |

**Kenapa harus arsitektur inference khusus?**
LLM bukanlah *stateless API* standar. Ketergantungan status memori yang dinamis (KV Cache) dan sifat decoding autoregressive menuntut engine yang mampu mengabstraksikan hardware VRAM layaknya kernel OS mengelola RAM fisik, sembari mengorkestrasi komputasi paralel deterministik dengan latency mikrodetik.

---

### 5. How (Workflow Detail)

Alur eksekusi request pada arsitektur produksi continuous batching:

```
[Incoming Request] ──> (Admission Controller)
                              │
                              ▼
                     [Prefill/Wait Queue]
                              │
                    ┌─────────┴─────────┐
                    │ Scheduler Loop    │ <───────────────────────────────┐
                    └─────────┬─────────┘                                 │
                              │ 1. Pilih Batch Aktif                      │
                              │ 2. Cek ketersediaan Physical Blocks       │
                              ▼                                           │
                    [Block Table Allocation]                              │
                              │                                           │
                              ▼                                           │
               [Distributed Kernel Execution]                             │
               - Forward Pass Prefill / Decode Chunk                      │
               - NCCL All-Reduce (Cross-GPU TP)                           │
               - Output Logits & Token Sampler                            │
                              │                                           │
                              ▼                                           │
               [Post-Processing & Validation]                             │
               - Cek stop conditions (EOS, Length, Stop Token)            │
               - Stream token ke SSE/gRPC streaming pipeline              │
                              │                                           │
                              ├───────────── Request Belum Selesai? ──────┘
                              ▼
                        [Request End]
                 (Deallocate Physical Blocks)
```

1. **Admission & Tokenization**: Request masuk via HTTP/gRPC, ditokenisasi, lalu diubah menjadi struktur logical sequence.
2. **Scheduling Step**:
   - Engine mengevaluasi *Prefill Queue* dan *Running/Decode Queue*.
   - Scheduler menjalankan policy (contoh: FCFS dengan preemptive priority).
   - Memeriksa ketersediaan blok KV Cache fisik di HBM. Jika blok habis, request di-preempt (swap ke Host RAM atau recompute).
3. **Memory Virtualization Update**:
   - Engine memetakan logical token IDs ke ID blok memori fisik yang dialokasikan di HBM melalui Block Table.
4. **Model Execution Phase**:
   - Chunked Prefill: Prompt panjang dipecah menjadi chunk (misal: 512 token) dan dieksekusi bersamaan dengan request fase decoding.
   - Eksekusi kernel FlashAttention / PagedAttention yang membaca KV Cache langsung dari pointer blok fisik.
5. **Sampling & Stream Out**:
   - Logits diproses (Greedy, Temperature, Top-P, atau Min-P).
   - Token terpilih dikirim secara asinkron ke response streaming channel pemanggil.
   - Jika EOS token dicapai, Block Table request tersebut dilepaskan kembali ke *Free Block Pool*.

---

### 6. Analogy & Diagram ASCII

#### Analogi PagedAttention: OS Virtual Memory vs. Dynamic KV Cache
Bayangkan VRAM GPU adalah sebuah perpustakaan.
- **Naive Allocation**: Anda memesan 1 rak penuh (1000 halaman) meskipun Anda baru membawa buku catatan berisi 1 halaman, hanya karena Anda "mungkin" akan menulis hingga 1000 halaman. Akibatnya, rak cepat penuh dan pengunjung lain ditolak (OOM), meskipun 99% rak kosong.
- **PagedAttention**: Perpustakaan menggunakan sistem binder binder-lepas (loose-leaf). Anda hanya diberi 1 lembar kertas (1 blok) saat Anda butuh menulis. Begitu lembar tersebut terisi 16 kalimat, pustakawan membawakan 1 lembar kosong baru dan mencatat lokasinya di indeks buku Anda (Block Table). Tidak ada kertas yang terbuang sia-sia.

```
Logical Blocks (Virtual Sequence):
[ Logical Block 0 ] ──> [ Tokens 0 - 15  ]
[ Logical Block 1 ] ──> [ Tokens 16 - 31 ]
[ Logical Block 2 ] ──> [ Tokens 32 - 47 ]

Physical Block Table Mapping:
┌──────────────────┬──────────────────┐
│ Logical Block ID │ Physical Page ID │
├──────────────────┼──────────────────┤
│        0         │      #104        │ ──> HBM Address 0x7F00...
│        1         │      #012        │ ──> HBM Address 0x1A40...
│        2         │      #519        │ ──> HBM Address 0x8C20...
└──────────────────┴──────────────────┘

HBM Physical Pool (Non-contiguous Allocation):
[Page #012] ... [Page #519] ... [Page #104] ... [Free Page]
```

---

### 7. Code Implementations

#### 7.1 Simple Example: Algoritma Paged KV-Cache Memory Manager
Simulasi internal logic dari block allocation, mapping, dan deallocation tanpa ketergantungan hardware CUDA.

```python
from typing import List, Dict, Optional
import math

class PhysicalBlock:
    def __init__(self, block_id: int, block_size: int):
        self.block_id = block_id
        self.block_size = block_size
        self.ref_count = 0

    def allocate(self):
        self.ref_count += 1

    def free(self):
        assert self.ref_count > 0, "Double-free detected!"
        self.ref_count -= 1

class PagedKVCacheManager:
    def __init__(self, total_blocks: int, block_size: int = 16):
        self.block_size = block_size
        self.free_blocks: List[PhysicalBlock] = [
            PhysicalBlock(i, block_size) for i in range(total_blocks)
        ]
        # Mapping: request_id -> List of physical block IDs
        self.block_tables: Dict[str, List[PhysicalBlock]] = {}

    def allocate_for_request(self, request_id: str, prompt_token_count: int) -> List[int]:
        needed_blocks = math.ceil(prompt_token_count / self.block_size)
        if len(self.free_blocks) < needed_blocks:
            raise MemoryError("GPU Out of Memory (OOM): Insufficient physical KV blocks.")

        allocated: List[PhysicalBlock] = []
        for _ in range(needed_blocks):
            block = self.free_blocks.pop()
            block.allocate()
            allocated.append(block)

        self.block_tables[request_id] = allocated
        return [b.block_id for b in allocated]

    def append_token(self, request_id: str, current_token_count: int) -> Optional[int]:
        """Menambahkan slot baru jika panjang token melintasi batas blok."""
        if current_token_count % self.block_size == 1:
            # Membutuhkan blok fisik baru
            if not self.free_blocks:
                raise MemoryError(f"OOM: Gagal mengalokasikan blok baru untuk request {request_id}")
            new_block = self.free_blocks.pop()
            new_block.allocate()
            self.block_tables[request_id].append(new_block)
            return new_block.block_id
        return None

    def free_request(self, request_id: str):
        if request_id not in self.block_tables:
            return
        for block in self.block_tables[request_id]:
            block.free()
            self.free_blocks.append(block)
        del self.block_tables[request_id]

# Testing Alur Eksekusi
if __name__ == "__main__":
    mgr = PagedKVCacheManager(total_blocks=4, block_size=16)
    req_id = "req-001"
    
    # Prompt: 30 tokens -> Membutuhkan ceil(30/16) = 2 blok
    blocks = mgr.allocate_for_request(req_id, prompt_token_count=30)
    print(f"Allocated physical blocks for {req_id}: {blocks}")
    print(f"Remaining free blocks: {len(mgr.free_blocks)}")

    # Decode: Token ke-31, 32 (masih dalam kapasitas blok ke-2)
    mgr.append_token(req_id, 31)
    mgr.append_token(req_id, 32)
    print(f"Blocks after 32 tokens: {[b.block_id for b in mgr.block_tables[req_id]]}")

    # Decode: Token ke-33 melintasi batas blok -> Alokasi blok ke-3
    new_blk = mgr.append_token(req_id, 33)
    print(f"Token 33 triggered allocation of block: {new_blk}")
    print(f"Remaining free blocks: {len(mgr.free_blocks)}")

    # Selesai
    mgr.free_request(req_id)
    print(f"After release, total free blocks: {len(mgr.free_blocks)}")
```

#### 7.2 Practical Example: High-Throughput Production-Ready Continuous Batching Engine
Implementasi async inference engine dengan iteration-level continuous batching, streaming response via async generators, dan simulasi non-blocking execution queue.

```python
import asyncio
import time
from typing import AsyncGenerator, Dict, List, Optional
from dataclasses import dataclass, field
import uuid

@dataclass
class GenerationRequest:
    request_id: str
    prompt: str
    max_tokens: int
    output_queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    generated_tokens: int = 0
    is_finished: bool = False
    arrival_time: float = field(default_factory=time.time)

class ProductionContinuousBatchingEngine:
    def __init__(self, max_batch_size: int = 4, latency_per_step: float = 0.02):
        self.max_batch_size = max_batch_size
        self.latency_per_step = latency_per_step
        self.waiting_queue: asyncio.Queue[GenerationRequest] = asyncio.Queue()
        self.active_batch: List[GenerationRequest] = []
        self._is_running = False
        self._loop_task: Optional[asyncio.Task] = None

    async def start(self):
        self._is_running = True
        self._loop_task = asyncio.create_task(self._scheduler_loop())

    async def stop(self):
        self._is_running = False
        if self._loop_task:
            await self._loop_task

    async def submit(self, prompt: str, max_tokens: int) -> AsyncGenerator[str, None]:
        req_id = f"req-{uuid.uuid4().hex[:8]}"
        request = GenerationRequest(request_id=req_id, prompt=prompt, max_tokens=max_tokens)
        await self.waiting_queue.put(request)

        while not request.is_finished:
            token = await request.output_queue.get()
            if token is None:  # Sentinel value indicating end of generation
                break
            yield token

    async def _scheduler_loop(self):
        """Loop iterasi berkelanjutan (Continuous Iteration Engine)."""
        while self._is_running:
            # 1. Mengisi batch jika ada slot kosong
            while len(self.active_batch) < self.max_batch_size and not self.waiting_queue.empty():
                new_request = self.waiting_queue.get_nowait()
                self.active_batch.append(new_request)

            if not self.active_batch:
                await asyncio.sleep(0.005)
                continue

            # 2. Simulasi komputasi forward-pass paralel (GEMV/Tensor Core Execution)
            await asyncio.sleep(self.latency_per_step)

            # 3. Iteration Step Execution
            finished_requests = []
            for req in self.active_batch:
                req.generated_tokens += 1
                simulated_token = f"[Tkn_{req.generated_tokens}]"
                await req.output_queue.put(simulated_token)

                if req.generated_tokens >= req.max_tokens:
                    req.is_finished = True
                    await req.output_queue.put(None)  # Kirim EOS signal
                    finished_requests.append(req)

            # 4. Eviction: Hapus request selesai secara instan di akhir iterasi
            for req in finished_requests:
                self.active_batch.remove(req)

# Entry point demonstrasi penggunaan konkurensi
async def client_worker(engine: ProductionContinuousBatchingEngine, client_id: int, num_tokens: int):
    print(f"[{time.time():.2f}] Client {client_id} mengirim request ({num_tokens} tokens)...")
    tokens_received = 0
    t0 = time.time()
    first_token_time = None

    async for token in engine.submit(prompt=f"Prompt {client_id}", max_tokens=num_tokens):
        if tokens_received == 0:
            first_token_time = time.time() - t0
        tokens_received += 1

    total_duration = time.time() - t0
    print(f"[{time.time():.2f}] Client {client_id} selesai! "
          f"TTFT: {first_token_time*1000:.2f}ms, Total: {total_duration:.2f}s, "
          f"TPOT: {(total_duration - first_token_time)/(tokens_received - 1)*1000:.2f}ms")

async def main():
    engine = ProductionContinuousBatchingEngine(max_batch_size=2, latency_per_step=0.03)
    await engine.start()

    # Eksekusi secara konkuren dengan waktu submit berbeda
    tasks = [
        asyncio.create_task(client_worker(engine, 1, 5)),
        asyncio.create_task(client_worker(engine, 2, 2)),
    ]
    # Beri jeda sejenak, lalu submit client ke-3 untuk membuktikan dynamic slot fill
    await asyncio.sleep(0.04)
    tasks.append(asyncio.create_task(client_worker(engine, 3, 3)))

    await asyncio.gather(*tasks)
    await engine.stop()

if __name__ == "__main__":
    asyncio.run(main())
```

---

### 8. Real-World Case Study (Enterprise Scale)

**Kasus**: Sistem Core Search & Question Answering Enterprise (Contoh: Skenario 150 Juta User Aktif, Peak QPS: 12.000).
- **Infrastruktur Target**: Cluster 64 Nodes x 8x NVIDIA H100 SXM5 (80GB). Model: Llama-3-70B-Instruct (FP16: ~140GB base weights).
- **Tantangan SLO**:
  - p99 TTFT $\le 120\text{ ms}$
  - p99 TPOT $\le 18\text{ ms}$
  - Error rate (HTTP 5xx / dropped streams) $\le 0.001\%$

#### Masalah Produksi Awal (Baseline Architecture Fail)
Saat arsitektur awal diluncurkan menggunakan Naive PyTorch model serving standard:
1. **OOM Cascades**: Prompt panjang pengguna (rag document dump 8k tokens) mengalokasikan memory contiguous besar, menyebabkan node crash dan memicu evictions massal.
2. **Head-of-Line (HoL) Blocking**: Satu request 2048 token mengunci 7 request lain berukuran 50 token dalam static batch. Utilisasi GPU turun drastis ke 14% MFU.
3. **Network Incast di NCCL**: Distribusi multi-node tanpa NUMA node awareness memicu inter-switch bandwidth bottlenecks.

#### Desain Solusi Rekayasa Produksi
```
                                 [Global Ingress Layer]
                                           │
                   ┌───────────────────────┴───────────────────────┐
                   ▼                                               ▼
          [Engine Pod: TP=4, PP=1]                        [Engine Pod: TP=4, PP=1]
   ┌─────────────────────────────────────┐         ┌─────────────────────────────────────┐
   │ - PagedAttention (Block Size = 16)  │         │ - PagedAttention (Block Size = 16)  │
   │ - Chunked Prefill (max=512 tokens)  │         │ - Chunked Prefill (max=512 tokens)  │
   │ - RadixAttention Prefix Caching     │         │ - RadixAttention Prefix Caching     │
   │ - FP8 E4M3 Quantized Weights & KV   │         │ - FP8 E4M3 Quantized Weights & KV   │
   └─────────────────────────────────────┘         └─────────────────────────────────────┘
```

1. **Topologi Model Parallelism**: 
   - Konfigurasi $TP=4$ per pod (terisolasi dalam 1 node NVLink domain; kecepatan transfer 900 GB/s per arah, menghindari cross-node latency via Ethernet/InfiniBand). Model weights di-shard ke 4 GPU x 80GB = 320GB VRAM pool.
2. **Chunked Prefill Implementation**:
   - Membatasi ukuran komputasi prefill per step maksimum 512 token. Jika prompt berukuran 2048 token, scheduler membaginya ke dalam 4 iterasi step, diinterleave dengan decoding batch yang sudah berjalan.
   - Hasil: Mencegah spike TPOT pada active requests, menstabilkan tail latency TPOT di level 14.5 ms.
3. **KV Cache FP8 Quantization**:
   - KV Cache dikompresi dari FP16 ke FP8 (E4M3), mereduksi footprint memori per token hingga 50%.
   - Meningkatkan batch capacity hingga 2.2x lipat pada batas threshold VRAM yang sama.
4. **RadixAttention (Automatic Prefix Caching)**:
   - System prompt yang sama (1.2k tokens standard company policy context) di-cache dalam Radix Tree.
   - Hit rate mencapai 68%, mengubah komputasi prefill $O(N)$ menjadi penelusuran hash pointer $O(1)$, memangkas p99 TTFT dari 280ms ke 45ms.

---

### 9. Trade-offs

| Parameter Desain | Opsi A | Opsi B | Trade-off Analysis |
| :--- | :--- | :--- | :--- |
| **Quantization Scheme** | FP16 / BF16 (Unquantized) | FP8 / INT4 (W4A16 / KV-FP8) | Opsi A mempertahankan perplexity absolut tanpa loss akurasi penalaran matematis. Opsi B memangkas memory bandwidth bottleneck hingga 50-70%, menaikkan throughput total hingga 3x, namun memiliki risiko degradation akurasi numerik tipis pada edge case. |
| **Chunked Prefill Size** | Small Chunk (misal: 256 tokens) | Large Chunk (misal: 2048 tokens) | Small chunk memprioritaskan stabilitas TPOT (decode requests tidak terblokir lama), namun mereduksi efisiensi komputasi GEMM prefill (TTFT memburuk). Large chunk memaksimalkan GPU compute efficiency (TTFT cepat), tetapi mengorbankan p99 TPOT. |
| **Parallelism Topology** | Tensor Parallelism (TP) | Pipeline Parallelism (PP) | TP memiliki latency sangat rendah karena dieksekusi paralel per layer, namun mensyaratkan bandwidth interkoneksi ultra-tinggi (NVLink). PP cocok untuk cross-node (Infiniband/RoCE), namun menghasilkan "bubble latency" (idle time SM) yang memerlukan micro-batch tuning kompleks. |
| **Speculative Decoding** | Standalone Engine | Speculator Draft Model Pair | Menggunakan draft model kecil (misal: 68M draft untuk 70B target) melipatgandakan kecepatan decoding (1.8x - 2.5x speedup), namun mengonsumsi alokasi VRAM tambahan dan membuang komputasi saat draft validation rejection rate tinggi. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1. Common Mistakes
1. **Mengabaikan CUDA Context & PyTorch Memory Caching**:
   Memanggil `torch.cuda.empty_cache()` secara berulang di tengah inference loop. Hal ini memaksa sinkronisasi GPU-CPU yang memicu stall pipeline instruksi CUDA driver dan mendegradasi throughput hingga 40%.
2. **Static Padding pada Dynamic Request**:
   Membiarkan padding `<pad>` diproses di dalam attention mask forward kernel. Menggunakan matrix padding standar menyia-nyiakan komputasi Tensor Cores untuk token kosong. Wajib menggunakan kernel *unpadded/ragged flash-attention*.
3. **Cross-NUMA Memory Thread Affinity**:
   Menjalankan worker inference engine pada NUMA node 0 sementara kartu GPU PCIe terpasang pada NUMA node 1, menyebabkan penurunan performa host-to-device memory copy (HtoD) hingga 50% melewati bus QPI/UPI.

#### 10.2. Troubleshooting Playbook

##### Problem 1: CUDA Out of Memory (OOM) Mendadak saat High Concurrency
- **Symptom**: Engine crash dengan pesan `torch.cuda.OutOfMemoryError: CUDA out of memory` saat utilisasi VRAM dilaporkan belum 100%.
- **Root Cause**: Engine tidak memperhitungkan memory overhead untuk kernel activations dan temporary buffers saat alokasi awal KV cache pool.
- **Diagnostic Step**:
  ```bash
  # Pantau reservasi memori
  nvidia-smi --query-gpu=memory.used,memory.free --format=csv -l 1
  ```
- **Remediation**:
  Kunci parameter `gpu_memory_utilization` engine (misal di vLLM) ke angka `0.90` (menyisakan 10% VRAM untuk activation buffer dinamik), bukan `0.98` atau `1.0`.

##### Problem 2: NCCL Timeout Deadlock pada Multi-GPU (TP)
- **Symptom**: Request menggantung (*hang*) selamanya tanpa ada token yang dihasilkan. Log menunjukkan: `Watchdog caught collective operation timeout: WorkNCCL...`
- **Root Cause**: Desinkronisasi state antar-GPU rank; salah satu rank menerima panjang sequence berbeda atau mengalami exception tanpa membatalkan rank lainnya.
- **Remediation**:
  Export env var untuk diagnosa:
  ```bash
  export NCCL_DEBUG=INFO
  export NCCL_DEBUG_SUBSYS=COLL
  export TORCH_NCCL_ASYNC_ERROR_HANDLING=1
  export NCCL_ASYNC_ERROR_HANDLING=1
  ```
  Pastikan barrier synchronization dipanggil sebelum aborting context di level engine wrapper.

---

### 11. Best Practices & Production Checklist

#### Pre-Flight Checklist (Sebelum Deployment ke Production)
- [ ] **Hardware Alignment**: Verifikasi NUMA affinity antara CPU core binding dan PCIe switch GPU yang bersangkutan (`numactl --cpunodebind=... --membind=...`).
- [ ] **Lock GPU Clocks**: Jalankan persistency mode dan lock GPU graphics clock ke base/boost deterministik untuk menghindari throttling:
  ```bash
  sudo nvidia-smi -pm 1
  sudo nvidia-smi --lock-gpu-clocks=1980,1980
  ```
- [ ] **KV Cache Footprint Calculation**: Pastikan alokasi pool KV cache dihitung akurat terhadap target concurrent context length maksimum.
- [ ] **Kernel Warm-up**: Lakukan warmup batch passing (`dummy forward passes` untuk sequence minimum hingga maximum) sebelum membuka port ingress traffic load balancer untuk menghindari latency spikes pada user pertama akibat kompilasi kernel Triton/CUDA JIT.

#### Production Architecture Rules
1. **Selalu gunakan Streaming Response**: Jangan pernah membendung seluruh token di memory buffer backend sebelum mengirim respons ke client.
2. **Gunakan Chunked Prefill**: Selalu aktifkan fitur chunked prefill jika engine melayani prompt berukuran > 1024 token secara simultan dengan throughput traffic decoding tinggi.
3. **Observability**: Pantau metrik spesifik inference:
   - `vllm:num_requests_running`
   - `vllm:num_requests_waiting`
   - `vllm:gpu_cache_usage_factor`
   - `vllm:time_to_first_token_seconds` (Histogram)
   - `vllm:time_per_output_token_seconds` (Histogram)

---

### 12. Hands-on Practice

Target path direktori implementasi: `hands-on/m02/`

#### Langkah 1: Siapkan Virtual Environment & Dependencies
```bash
mkdir -p hands-on/m02 && cd hands-on/m02
python3 -m venv venv
source venv/bin/activate
pip install numpy fastapi uvicorn pydantic
```

#### Langkah 2: Buat File `hands-on/m02/paged_allocator.py`
Implementasikan struktur kernel block manager lengkap dengan reference counting untuk prefix caching (simulasi copy-on-write).

```python
# hands-on/m02/paged_allocator.py
from typing import List, Dict, Tuple, Optional

class Block:
    def __init__(self, block_id: int, size: int):
        self.block_id = block_id
        self.size = size
        self.tokens: List[int] = []
        self.ref_count: int = 0

    def is_full(self) -> bool:
        return len(self.tokens) >= self.size

    def append_token(self, token_id: int):
        assert not self.is_full(), "Cannot append to a full block."
        self.tokens.append(token_id)

class AdvancedRadixBlockManager:
    def __init__(self, total_memory_blocks: int, block_size: int = 16):
        self.block_size = block_size
        self.pool: List[Block] = [Block(i, block_size) for i in range(total_memory_blocks)]
        self.free_pool: List[int] = list(range(total_memory_blocks))
        # Hash table: Tuple(Token IDs) -> block_id (Prefix caching logic)
        self.prefix_tree: Dict[Tuple[int, ...], int] = {}

    def get_or_allocate_block(self, tokens: List[int]) -> Tuple[int, bool]:
        """Prefix caching lookup: kembalikan cached block jika hash token cocok."""
        key = tuple(tokens)
        if key in self.prefix_tree:
            b_id = self.prefix_tree[key]
            self.pool[b_id].ref_count += 1
            return b_id, True  # Cache Hit

        if not self.free_pool:
            raise MemoryError("Out of KV Cache physical pages!")

        b_id = self.free_pool.pop(0)
        block = self.pool[b_id]
        block.tokens = list(tokens)
        block.ref_count = 1
        
        if block.is_full():
            self.prefix_tree[key] = b_id
        return b_id, False  # Cache Miss

    def release_block(self, block_id: int):
        block = self.pool[block_id]
        block.ref_count -= 1
        if block.ref_count == 0:
            # Hapus dari prefix tree jika dibersihkan
            key = tuple(block.tokens)
            if key in self.prefix_tree:
                del self.prefix_tree[key]
            block.tokens.clear()
            self.free_pool.append(block_id)
```

#### Langkah 3: Buat Mock API Server `hands-on/m02/server.py`
Jalankan server mock inference dengan FastAPI yang mengimplementasikan streaming SSE dan dynamic scheduler.

```python
# hands-on/m02/server.py
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import asyncio
import json
from paged_allocator import AdvancedRadixBlockManager

app = FastAPI(title="Production-Grade Mock Inference Server")
mem_mgr = AdvancedRadixBlockManager(total_memory_blocks=1024, block_size=16)

class CompletionRequest(BaseModel):
    prompt: str
    max_tokens: int = 32

async def token_stream_generator(prompt: str, max_tokens: int):
    # Dummy tokenize prompt ke integer representation
    tokens = [ord(c) for c in prompt[:16]]
    # Alokasi prefix/prompt block
    b_id, is_hit = mem_mgr.get_or_allocate_block(tokens)
    hit_status = "HIT" if is_hit else "MISS"
    
    yield f"data: {json.dumps({'event': 'metadata', 'cache': hit_status, 'block_id': b_id})}\n\n"

    try:
        for i in range(max_tokens):
            await asyncio.sleep(0.015)  # Simulasi latency per token 15ms
            chunk = f" tok_{i}"
            yield f"data: {json.dumps({'token': chunk})}\n\n"
    finally:
        mem_mgr.release_block(b_id)
        yield f"data: {json.dumps({'event': 'DONE'})}\n\n"

@app.post("/v1/completions")
async def completions(req: CompletionRequest):
    return StreamingResponse(
        token_stream_generator(req.prompt, req.max_tokens),
        media_type="text/event-stream"
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

#### Langkah 4: Uji Coba Caching dan Latency
Jalankan di shell:
```bash
# Terminal 1: Run server
python server.py

# Terminal 2: Test cache miss
curl -N -X POST http://localhost:8000/v1/completions \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Hello System Infra Engine!", "max_tokens": 5}'

# Terminal 2: Test cache hit (dengan prompt identik)
curl -N -X POST http://localhost:8000/v1/completions \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Hello System Infra Engine!", "max_tokens": 5}'
```

---

### 13. Exercises

#### Level Easy
Tuliskan fungsi Python `calculate_kv_cache_size(layers: int, kv_heads: int, head_dim: int, seq_len: int, dtype_bytes: int = 2) -> float` yang mengembalikan ukuran KV cache dalam satuan Gigabytes (GB) untuk 1 batch size.
*Expected Output Format*: Float (GB).

#### Level Medium
Kembangkan skrip simulator load-tester async yang menembakkan 50 request secara konkuren ke endpoint `/v1/completions` dengan parameter `max_tokens` acak antara 10 hingga 100 token. Hitung dan cetak metrik agregat:
- Rata-rata Throughput Global (Tokens per Second).
- p50, p90, dan p99 Latency Total.

#### Level Hard
Ubah file `paged_allocator.py` agar mengimplementasikan algoritma **LRU (Least Recently Used) Block Eviction Policy**:
- Ketika alokasi blok baru diminta dan `free_pool` bernilai kosong (`0`), allocator tidak boleh melempar `MemoryError`.
- Sebaliknya, allocator harus mencari blok fisik yang memiliki `ref_count == 0` dengan timestamp akses tertua, mengeviksi mapping-nya, membersihkan kontennya, dan mengalokasikannya kembali untuk request aktif yang baru.

---

### 14. Real-World Challenge

**Judul Tantangan**: Zero-Drop Preemptive Chunked Scheduler Under Heavy Load Spike.

**Konteks Arsitektur**:
Sistem Anda mengalami lonjakan beban musiman (flash traffic) di mana pool memory GPU KV Cache menyentuh limit $100\%$. Dalam kondisi ini, engine standar akan menolak request baru (HTTP 429/503) atau melakukan hard crash OOM.

**Tugas Rekayasa**:
Rancang dan bangun prototipe engine scheduler berbasis modul:
1. **Dynamic Priority Queue**: Bedakan antara request *VIP/Critical SLA* dan *Batch/Standard SLA*.
2. **Preemption Mechanism (Swap or Recompute)**:
   - Jika free blocks fisik habis di tengah iterasi decoding:
     - Pilih satu atau lebih low-priority request yang sedang running.
     - Simpan metadata token sequence-nya ke Host Memory buffer (RAM) atau drop bloknya untuk nantinya di-recompute (*recompute strategy*).
     - Alokasikan blok fisik yang dibebaskan kepada high-priority request agar dapat menyelesaikan decoding tanpa interupsi.
3. **Resumption Strategy**:
   - Begitu physical block pool kembali memiliki ruang, restore low-priority request tersebut dan lanjutkan decoding-nya dari checkpoint token terakhir.
4. **Metrik Keberhasilan**: Tidak boleh ada koneksi request yang di-drop/error (0 HTTP 5xx / connection abort). Seluruh request harus berhasil dikirim ke client meskipun tail latency untuk batch tier mengalami degradasi terukur.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda & Konseptual)
1. **Operasi aljabar linier apa yang mendominasi Fase Prefill dan Fase Decode secara berturut-turut?**
   - A. GEMV dan GEMM
   - B. GEMM dan GEMV
   - C. Convolutions dan GEMM
   - D. Dot Product Element-wise dan LayerNorm
2. **Berapa kebutuhan memori KV Cache untuk model Llama-2-7B ($L=32, H=32, D=128$) dalam format FP16 untuk sequence length 2048 token per request tunggal?**
   - A. ~512 MB
   - B. ~1 GB
   - C. ~2 GB
   - D. ~4 GB
3. **Mengapa *Continuous Batching* menghasilkan throughput yang jauh lebih tinggi dibandingkan *Static Batching*?**
   - A. Karena continuous batching mengkompilasi model ke CUDA graph secara statis.
   - B. Karena continuous batching tidak perlu menghitung token attention.
   - C. Karena continuous batching mengeliminasi bubble waiting time akibat variasi panjang sequence antar-request dalam satu batch.
   - D. Karena continuous batching mengonversi komputasi GPU ke CPU secara paralel.
4. **Apa tujuan utama dari implementasi PagedAttention pada inference engine?**
   - A. Menurunkan nilai FLOPs yang dibutuhkan dalam komputasi self-attention.
   - B. Mengeliminasi pemborosan memori akibat fragmentasi internal dan alokasi contiguous berlebih.
   - C. Menggantikan proses tokenization menggunakan hardware accelerator.
   - D. Menghilangkan kebutuhan backward pass saat pelatihan model.
5. **Primitif NCCL apa yang wajib dipanggil pada akhir block forward pass dari Row-Parallel Linear layer dalam skema Tensor Parallelism?**
   - A. NCCL Broadcast
   - B. NCCL All-Gather
   - C. NCCL All-Reduce
   - D. NCCL Reduce-Scatter

#### Bagian 2: Intermediate (Analisis Kasus & Algoritma)
6. **Dalam arsitektur Grouped-Query Attention (GQA), jika jumlah Attention Heads ($Q$) adalah 32 dan jumlah Key-Value Heads ($KV$) adalah 8, bagaimana hal ini mempengaruhi konsumsi memori KV Cache dibandingkan Standard Multi-Head Attention (MHA)?**
   - *Jawaban*: Konsumsi KV Cache tereduksi sebesar faktor 4x ($32/8 = 4$). Memori yang dibutuhkan turun menjadi $25\%$ dari baseline MHA karena layer Key dan Value di-share ke setiap kelompok 4 Query head.
7. **Jelaskan fenomena *Chunked Prefill* dan bagaimana teknik ini memecahkan masalah degradasi Time-Per-Output-Token (TPOT)!**
   - *Jawaban*: Chunked prefill memecah prompt panjang yang compute-bound menjadi segmen-segmen kecil (misal 512 token) dan menggabungkannya ke dalam satu batch eksekusi bersama token-token decode yang memory-bandwidth bound. Hal ini mencegah forward pass decoding terblokir (stalled) selama ratusan milidetik oleh satu prefill sequence raksasa, sehingga lonjakan tail latency p99 TPOT dapat dicegah.
8. **Mengapa mengompilasi model LLM ke static CUDA Graphs menjadi tantangan pada inference engine yang menggunakan Dynamic Continuous Batching?**
   - *Jawaban*: CUDA Graph mensyaratkan pointer memori dan dimensi tensor (shape) yang statis dan deterministik sebelum graph dieksekusi. Pada continuous batching, ukuran batch dan token assignment berubah dinamis pada setiap iterasi. Solusinya memerlukan pembuatan multiple static graph buckets (misal untuk batch size 1, 2, 4, 8, 16) dan scheduler memetakan eksekusi ke bucket terdekat (graph padding).
9. **Kapan teknik *Speculative Decoding* TIDAK memberikan peningkatan performa (speedup) atau justru memperlambat inference pipeline?**
   - *Jawaban*: Ketika tingkat penerimaan token (*acceptance rate*) dari target model terhadap output draft model sangat rendah (misal: domain code generation yang ketat atau highly creative tasks dengan high temperature). Pada skenario ini, draft tokens selalu ditolak, sehingga siklus komputasi draft model menjadi murni pemborosan waktu dan latency bertambah akibat overhead verifikasi.
10. **Jelaskan perbedaan mendasar antara *RadixAttention* (seperti pada SGLang) dan *PagedAttention* (seperti pada vLLM)!**
    - *Jawaban*: PagedAttention menyelesaikan masalah alokasi memori fisik level rendah via paging tabel blok virtual untuk sequence aktif. RadixAttention bekerja di atas layer alokasi tersebut dengan menstrukturkan riwayat KV cache dalam struktur pohon *Radix Tree*, memungkinkan sharing KV Cache secara otomatis dan efisien tidak hanya untuk token yang sedang berjalan, tetapi juga lintas request yang memiliki kesamaan prefix (multi-turn conversation, few-shot prompts) tanpa alokasi ulang.

#### Bagian 3: Skenario Kasus Produksi
11. **Skenario A**: Cluster inference Anda menggunakan $TP=8$ pada satu node HGX H100. Utilisasi GPU compute tercatat hanya 22%, namun p99 latency sangat tinggi. Hasil profiling menunjukkan waktu eksekusi didominasi oleh event `cudaStreamSynchronize` di dalam kernel `ncclKernel_AllReduce`. Apa analisis akar masalah sistemik Anda dan solusi mitigasinya?
    - *Jawaban Analisis*: Akar masalahnya adalah komunikasi inter-GPU all-reduce mendominasi rasio total komputasi per layer. Hal ini terjadi ketika batch size terlalu kecil (under-saturating GPUs) atau terjadi thread contention pada host CPU core yang mengorkestrasi rank. Solusi: Gunakan batch size yang lebih besar melalui Dynamic Batching Timeout, pastikan NVLink bridges beroperasi pada bandwidth penuh (bukan fallback ke PCIe via setting `NCCL_P2P_DISABLE=0`), dan pastikan pin process worker ke GPU NUMA node yang tepat.
12. **Skenario B**: Sistem QA dokumen Anda memproses file PDF berukuran rata-rata 32.000 token. Saat 10 request datang bersamaan, GPU langsung mengalami out-of-memory meskipun total kapasitas VRAM cluster mencapai 320GB. Mengapa fenomena ini terjadi dan strategi inferensi apa yang wajib diterapkan?
    - *Jawaban Analisis*: Masalahnya adalah memory spike pada fase prefill prompt 32k tokens. Komputasi attention matrix standar membutuhkan alokasi temporary tensor yang proporsional terhadap $O(N^2)$ sequence length jika FlashAttention tidak diatur dengan context chunking. Selain itu, alokasi KV cache instan untuk 320.000 token sekaligus menghabiskan VRAM sebelum decoding dimulai. Solusi: Terapkan FlashAttention-2/3 untuk mereduksi footprint aktivasi memori, gunakan *Chunked Prefill* dengan chunk size 1024/2048, dan terapkan *Sliding Window Attention* (SWA) atau model berarsitektur Context Compression jika relevan.
13. **Skenario C**: Pada monitoring dashboard Prometheus, Anda melihat metrik `gpu_cache_usage_factor` bernilai $98\%$, metrik `num_requests_waiting` terus melonjak naik (backlog), namun metrik GPU Temperature dan Power Draw berada jauh di bawah TDP (misal: 180 Watt dari batas 700 Watt H100). Apa yang sedang terjadi pada inference engine Anda?
    - *Jawaban Analisis*: Engine mengalami kondisi *KV Cache Saturation / Memory Bandwidth Choke*. Kapasitas VRAM terisi penuh oleh status KV Cache request lama yang panjang (sehingga `gpu_cache_usage_factor` mendekati 100%), yang mencegah scheduler memasukkan request baru dari waiting queue. Namun, request yang ada kemungkinan besar berada dalam fase single-token decode loop dengan batch kecil atau sequence sparse, sehingga Tensor Cores sebagian besar menganggur (idle) menunggu transfer memori dari HBM, menyebabkan power draw rendah. Solusi: Aktifkan kuantisasi KV Cache ke FP8/INT8 untuk melipatgandakan kapasitas token pool, turunkan parameter timeout idle session, dan scale out pod inference baru ke Kubernetes cluster secara horizontal.

---

### 16. Summary

Inference Engineering tingkat enterprise adalah disiplin yang berfokus pada efisiensi eksekusi dan penjadwalan komputasi hardware:
- **Prefill vs Decode Dichotomy**: Memahami kontras antara fase prefill yang compute-bound ($O(N^2)$ atau chunked $O(N)$) dan fase decode yang autoregressive memory-bandwidth-bound ($O(1)$ token step) adalah kunci dasar perancangan sistem inferensi.
- **Virtual Memory Virtualization**: PagedAttention mengeliminasi pemborosan VRAM dengan memecah KV Cache menjadi blok-blok diskrit non-contiguous, memungkinkan utilisasi memori GPU mendekati $96\% - 98\%$.
- **Continuous Batching**: Menghilangkan batasan static batching bubbles dengan menjadwalkan request pada resolusi iterasi per token, memaksimalkan throughput sistem per dollar GPU.
- **Distributed Optimization**: Penggunaan Tensor Parallelism mensyaratkan hardware interkoneksi ultra-cepat (NVLink) dan alinyemen arsitektur software (NUMA affinity, chunked execution, quantization) untuk memastikan p99 TTFT dan TPOT memenuhi kriteria Service Level Agreement produksi.