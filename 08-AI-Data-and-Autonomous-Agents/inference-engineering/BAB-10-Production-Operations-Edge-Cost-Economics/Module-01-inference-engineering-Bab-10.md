# Modul 10.1: Arsitektur Model Serving Skala Produksi, Dynamic/Continuous Batching, dan Optimasi Unit Economics GPU

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Menganalisis dan Membedakan Metrik Kunci Inferensi Generatif**: Mengukur dan mengevaluasi *Time-To-First-Token* (TTFT), *Inter-Token Latency* (ITL), *Tokens Per Second* (TPS), dan utilisasi *Key-Value* (KV) *Cache Memory Pressure* pada arsitektur serving modern.
2. **Merancang Mekanisme Penjadwalan Iteration-Level (Continuous Batching)**: Mengimplementasikan logika scheduling berbasis iterasi langkah demi langkah untuk menghilangkan *bubble latency* akibat variasi panjang prompt dan completion.
3. **Mengoptimalkan Unit Economics Inferensi (Cost per 1M Tokens)**: Menghitung secara analitis dan meminimalkan Total Cost of Ownership (TCO) GPU cluster berdasarkan rasio throughput terhadap biaya sewa komputasi cloud ($/GPU-hour).
4. **Membangun Sistem Autoscaling Berbasis Metrik Inferensi Domain-Specific**: Mengonfigurasi kontrol autoscaling menggunakan metrik saturasi KV-cache dan antrean iterasi alih-alih metrik konvensional seperti *Raw GPU Utilization*.
5. **Mengisolasi dan Memitigasi Kegagalan Sistem Serving**: Menangani skenario *KV-cache eviction*, *prompt-bombing*, dan *head-of-line blocking* dengan strategi preemption (*recompute* vs *swap*).

---

## 2. Concept Overview

Model serving untuk Large Language Model (LLM) dan arsitektur Transformer memiliki karakteristik beban kerja yang fundamental berbeda dari layanan berbasis CPU konvensional maupun microservices stateless. Dua fase komputasi utama dalam LLM inference menciptakan profil hambatan perangkat keras (*hardware bottleneck*) yang asimetris:

```
+----------------------------------------------------------------------------------+
|                            SIKLUS HIDUP INFERENSI LLM                            |
+----------------------------------------------------------------------------------+
| 1. PREFILL PHASE (Prompt Processing)      | 2. DECODE PHASE (Token Generation)   |
| - Karakteristik: Compute-Bound            | - Karakteristik: Memory Bandwidth-   |
| - Karakteristik Operasi: GEMM             |   Bound                              |
|   (General Matrix Multiply)               | - Karakteristik Operasi: GEMV        |
| - Paralelisasi tinggi di seluruh tensor   |   (General Matrix-Vector Multiply)   |
| - Utilisasi Tensor Core: Maksimal         | - Eksekusi: Sequential (1 token/step)|
| - Sensitivitas: Latensi jaringan & bus    | - Utilisasi Tensor Core: Rendah      |
|   PCIe/NVLink                             | - Sensitivitas: HBM Bandwidth (TB/s) |
+----------------------------------------------------------------------------------+
```

### Paradigma Batching: Dari Statis ke Continuous Batching

1. **Static / Naive Dynamic Batching**: Kumpulan request dikelompokkan bersama di level request HTTP. Eksekusi batch berjalan serentak. Jika Request A menghasilkan 10 token dan Request B menghasilkan 500 token, komputasi untuk Request A akan menganggur (*idling/padding bubble*) selama 490 langkah eksekusi hingga Request B selesai.
2. **Continuous / Iteration-Level Batching**: Alih-alih mengikat batch pada siklus hidup seluruh request, scheduler beroperasi pada *single step iteration*. Begitu Request A selesai menghasilkan token `<EOS>` pada iterasi ke-10, slot komputasinya langsung dievakuasi, dan request baru dari antrean dialokasikan ke dalam batch pada iterasi ke-11 tanpa harus menunggu Request B selesai.

### Formulasi Matematika Unit Economics Inferensi

Metrik efisiensi ekonomi inferensi dinyatakan dalam biaya per satu juta token:

$$\text{Cost per 1M Tokens} = \left( \frac{\text{GPU Instance Cost per Hour}}{\text{Effective Tokens Processed per Hour}} \right) \times 1{,}000{,}000$$

Di mana throughput efektif token per jam ($\text{ETPH}$) dipengaruhi secara langsung oleh efisiensi batching:

$$\text{ETPH} = 3600 \times \sum_{i=1}^{N} \left( \text{BatchSize}_i \times \frac{1}{\text{StepLatency}_i} \right) \times (1 - \text{PaddingRatio})$$

Dalam dynamic batching klasik, $\text{PaddingRatio}$ dapat mencapai $0.6 - 0.8$ (60-80% siklus komputasi terbuang sia-sia pada token padding `[PAD]`). Continuous batching mereduksi $\text{PaddingRatio} \to 0$, sehingga menurunkan Cost per 1M Tokens secara drastis pada beban trafik tinggi.

---

## 3. Why It Matters

Di tingkat enterprise, kegagalan memahami arsitektur serving LLM memicu inefisiensi modal dan pelanggaran Service Level Agreement (SLA):

* **Overprovisioning GPU Akibat Raw Metric Illusion**: Metrik `nvidia-smi` sering kali menunjukkan `GPU Utilization: 100%`. Namun, metrik ini hanya mencerminkan bahwa GPU kernel sedang aktif mengeksekusi instruksi, bukan berarti Tensor Core terutilisasi penuh. Pada fase decode, 100% pemanfaatan GPU sering kali hanya mencerminkan *memory bus* yang jenuh menunggu transfer bobot dari VRAM (HBM) ke SRAM, sementara unit komputasi menganggur. Menambah replika pod berdasarkan metrik utilitas ini menyebabkan pemborosan biaya ribuan dolar per bulan.
* **Degradasi Latensi Ekor (p99 Tail Latency)**: Lonjakan panjang konteks input (misal dokumen legal 32k token) pada worker yang melayani user interaktif (chat dengan target TTFT < 500ms) akan menyebabkan *Head-of-Line (HoL) Blocking*. Seluruh worker akan terhenti melayani decode demi memproses prefill 32k token tersebut. Tanpa arsitektur serving yang mampu memisahkan (*disaggregate*) atau memotong (*chunk*) fase prefill, SLA latensi sistem akan runtuh.
* **Out-of-Memory (OOM) Crash Akibat KV-Cache Bloat**: Tidak seperti microservices biasa yang stateless, penggunaan memori LLM bertambah secara dinamis seiring bertambahnya token yang di-generate. Tanpa manajemen memori tingkat halaman (*paging*) dan strategi preemption yang deterministik, lonjakan trafik serentak akan memicu runtime CUDA OOM yang mematikan seluruh engine serving instance.

---

## 4. Arsitektur & Diagram Komponen

Diagram berikut merepresentasikan arsitektur produksi berskala enterprise yang memisahkan Control Plane, Scheduling Plane, dan Hardware Execution Plane:

```
+---------------------------------------------------------------------------------------------------+
|                                       INGRESS LAYER & API GATEWAY                                 |
|  - Rate Limiting / Token Bucket   - Authentication / Multi-Tenancy   - Dynamic Timeout Controller |
+-------------------------------------------------+-------------------------------------------------+
                                                  |
                                                  v
+---------------------------------------------------------------------------------------------------+
|                        INFERENCE ROUTER & CAPACITY PLANNER (CONTROL PLANE)                        |
|  - KV-Cache-Aware Load Balancing  - Request Splitting (Prefill vs Decode Chunk Routing)           |
|  - SLO-Priority Queueing Engine   - Real-time Fleet Telemetry Aggregator                          |
+-------------------+-----------------------------------------------------------+-------------------+
                    |                                                           |
                    v                                                           v
+---------------------------------------------+             +---------------------------------------------+
|          INFERENCE WORKER NODE 01           |             |          INFERENCE WORKER NODE 02           |
| +-----------------------------------------+ |             | +-----------------------------------------+ |
| |        ASYNC ITERATION SCHEDULER        | |             | |        ASYNC ITERATION SCHEDULER        | |
| |  [Priority Queue] [Preemption Handler]  | |             | |  [Priority Queue] [Preemption Handler]  | |
| +--------------------+--------------------+ |             | +--------------------+--------------------+ |
|                      |                      |             |                      |                      |
|                      v                      |             |                      v                      |
| +-----------------------------------------+ |             | +-----------------------------------------+ |
| |           PAGED KV-CACHE MANAGER        | |             | |           PAGED KV-CACHE MANAGER        | |
| |  [Virtual Block Table] [GPU Block Pool] | |             | |  [Virtual Block Table] [GPU Block Pool] | |
| +--------------------+--------------------+ |             | +--------------------+--------------------+ |
|                      |                      |             |                      |                      |
|                      v                      |             |                      v                      |
| +-----------------------------------------+ |             | +-----------------------------------------+ |
| |         TENSOR PARALLEL RUNTIME         | |             | |         TENSOR PARALLEL RUNTIME         | |
| |    CUDA Kernels / FlashAttention-3      | |             | |    CUDA Kernels / FlashAttention-3      | |
| |  +-----------------------------------+  | |             | |  +-----------------------------------+  | |
| |  | GPU 0 (Master)  | GPU 1 (Worker)  |  | |             | |  | GPU 0 (Master)  | GPU 1 (Worker)  |  | |
| |  +-----------------+-----------------+  | |             | |  +-----------------+-----------------+  | |
| +-----------------------------------------+ |             | +-----------------------------------------+ |
+---------------------------------------------+             +---------------------------------------------+
                    |                                                           |
                    +-----------------------------+-----------------------------+
                                                  |
                                                  v
+---------------------------------------------------------------------------------------------------+
|                                TELEMETRY & COST ECONOMICS OBSERVER                                |
|  - TTFT / ITL Distribution  - KV Cache Fragmentation Ratio  - Cost Per 1M Tokens Aggregator       |
+---------------------------------------------------------------------------------------------------+
```

---

## 5. Deep Dive Mekanisme & Prinsip Kerja

### 5.1 Siklus Scheduling Iteration-Level (Continuous Batching)

Continuous batching mengubah siklus inferensi dari model batch linear menjadi *state machine* reaktif:

```
[Request Inbound] 
       │
       ▼
[Admission Control] ──(Cek Kapasitas KV-Cache)──> [Insufficient Mem] ──> [Queue / Reject / Preempt]
       │
       ├─ [Sufficient Mem]
       ▼
[Active Step Batch Formation]
       │
       ├─ Gabungkan Request Fase Prefill (Chunked) & Fase Decode
       ▼
[Model Forward Step (Single Iteration)]
       │
       ├─ Prefill Token Tensor: Input Tokens -> 1st Output Token
       └─ Decode Token Tensor: Input (Step N-1 Token) -> Step N Output Token
       │
       ▼
[KV-Cache Update (PagedAllocation)]
       │
       ▼
[Output Evaluation & Streaming]
       ├─ Token == <EOS> atau Reach Max Limit ──> [Deallocate KV Block] ──> [Stream Finish]
       └─ Token != <EOS> ──────────────────────> [Retain in Batch] ──────> [Next Step Loop]
```

1. **Chunked Prefill**: Mengingat prefill memakan waktu komputasi besar yang dapat membuat langkah decode kelaparan (*starvation*), engine modern memotong prompt panjang ke dalam beberapa chunk (misalnya 512 token per chunk). Dengan demikian, komputasi prefill diselingi di antara iterasi decode yang sedang berjalan, menstabilkan P99 ITL.
2. **Kondisi Preemption**: Ketika KV Cache fisik di GPU habis terpakai dan ada request aktif yang membutuhkan alokasi block baru untuk decode token berikutnya, scheduler harus memilih:
   * **Recompute**: Membuang cache milik request dengan prioritas terendah, lalu mengkalkulasi ulang seluruh konteksnya saat kapasitas memori tersedia kembali.
   * **Swap**: Mentransfer block KV Cache dari GPU VRAM ke Host RAM (CPU Memory) melalui bus PCIe. Strategi ini memicu penalti latensi bandwidth PCIe ($\sim 32-64 \text{ GB/s}$ vs HBM $\sim 2-3 \text{ TB/s}$).

### 5.2 Formulasi Alokasi Memori PagedAttention

Ukuran KV-cache per token bersifat deterministik:

$$\text{Memory per Token (Bytes)} = 2 \times 2 \times L \times H \times D$$

Di mana:
* Nilai $2$ pertama: representasi Key dan Value tensor.
* Nilai $2$ kedua: presisi numerik (FP16 atau BF16 = 2 bytes).
* $L$: Jumlah layer transformer.
* $H$: Jumlah attention heads (atau key-value heads jika menggunakan Grouped Query Attention / GQA).
* $D$: Head dimension ($D = \text{Hidden Size} / \text{Attention Heads}$).

*Contoh Analisis Riil*:
Pada model Llama-3-70B (GQA dengan 8 KV Heads, $L = 80$, $D = 128$):
$$\text{Memory per Token} = 4 \times 80 \times 8 \times 128 = 327{,}680 \text{ Bytes} \approx 320 \text{ KB/token}$$

Jika server melayani total *concurrency* 128 request, dengan rata-rata panjang konteks 4.096 token:
$$\text{Total KV-Cache Memory} = 128 \times 4096 \times 320 \text{ KB} \approx 167.77 \text{ GB}$$

Angka ini murni memori KV-cache, belum termasuk memori bobot model (weights) sebesar $\sim 140 \text{ GB}$ (FP16). Hal ini membuktikan bahwa **kapasitas memori GPU hampir selalu menjadi bottleneck pertama sebelum compute capacity tercapai.**

---

## 6. Production-Ready Code Implementation

Berikut adalah implementasi *Async Continuous Batch Scheduler* berbasis arsitektur non-blocking. Implementasi ini mencakup:
1. Engine penjadwalan iteratif dengan dynamic batch slotting.
2. Tracking alokasi memori KV-Cache virtual.
3. Ekstraksi metrik real-time: TTFT, ITL, KV-Cache utilization, dan emisi sinyal autoscaling.

```python
# scheduler_engine.py
import asyncio
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


class RequestStatus(Enum):
    WAITING = "WAITING"
    RUNNING = "RUNNING"
    PREEMPTED = "PREEMPTED"
    COMPLETED = "COMPLETED"


@dataclass
class GenerationConfig:
    max_new_tokens: int
    temperature: float = 1.0
    priority: int = 0  # 0: Default, 1: High, 2: System Critical


@dataclass
class InferenceRequest:
    request_id: str
    prompt_tokens: List[int]
    config: GenerationConfig
    arrival_time: float = field(default_factory=time.monotonic)
    start_time: Optional[float] = None
    finish_time: Optional[float] = None
    generated_tokens: List[int] = field(default_factory=list)
    status: RequestStatus = RequestStatus.WAITING
    ttft_latency: Optional[float] = None
    token_latencies: List[float] = field(default_factory=list)
    allocated_blocks: int = 0
    _last_token_timestamp: Optional[float] = None

    @property
    def total_tokens(self) -> int:
        return len(self.prompt_tokens) + len(self.generated_tokens)


@dataclass
class SchedulerConfig:
    max_batch_size: int
    max_model_len: int
    gpu_memory_bytes: int
    model_weight_bytes: int
    bytes_per_token_kv: int
    block_size: int = 16  # Paged block sizing standard


class PagedMemoryManager:
    """Mengelola alokasi block KV-cache virtual pada GPU Memory Pool."""
    def __init__(self, config: SchedulerConfig):
        self.block_size = config.block_size
        self.bytes_per_block = config.bytes_per_token_kv * self.block_size
        
        # Kapasitas memori bebas yang tersedia khusus untuk KV-Cache
        available_kv_memory = config.gpu_memory_bytes - config.model_weight_bytes
        if available_kv_memory <= 0:
            raise ValueError("Model weight melebihi total memori GPU yang ditentukan!")
        
        self.total_blocks = available_kv_memory // self.bytes_per_block
        self.free_blocks = self.total_blocks
        self.allocations: Dict[str, int] = {}

    def get_utilization(self) -> float:
        return (self.total_blocks - self.free_blocks) / self.total_blocks

    def can_allocate(self, current_tokens: int, additional_tokens: int = 1) -> bool:
        current_blocks = (current_tokens + self.block_size - 1) // self.block_size
        needed_blocks = (current_tokens + additional_tokens + self.block_size - 1) // self.block_size
        blocks_delta = needed_blocks - current_blocks
        return self.free_blocks >= blocks_delta

    def allocate_for_request(self, request_id: str, total_tokens: int) -> bool:
        needed_blocks = (total_tokens + self.block_size - 1) // self.block_size
        currently_held = self.allocations.get(request_id, 0)
        delta = needed_blocks - currently_held

        if delta <= 0:
            return True

        if self.free_blocks >= delta:
            self.free_blocks -= delta
            self.allocations[request_id] = needed_blocks
            return True
        return False

    def free_request(self, request_id: str) -> None:
        if request_id in self.allocations:
            self.free_blocks += self.allocations[request_id]
            del self.allocations[request_id]


class MockTensorEngine:
    """Simulasi hardware forwarding kernel dengan karakteristik latensi realistis."""
    async def step(self, batch: List[InferenceRequest]) -> List[int]:
        if not batch:
            return []
        
        # Membedakan overhead jika terdapat fase prefill
        has_prefill = any(len(req.generated_tokens) == 0 for req in batch)
        base_latency = 0.035 if has_prefill else 0.012  # Compute vs memory bound
        
        # Simulasi compute step latency
        await asyncio.sleep(base_latency)
        
        # Return mock token (Token 50256 diasumsikan sebagai token <EOS>)
        generated = []
        for req in batch:
            if len(req.generated_tokens) + 1 >= req.config.max_new_tokens:
                generated.append(50256)  # EOS
            else:
                generated.append(100)    # Arbitrary standard token
        return generated


class ProductionContinuousScheduler:
    """Core Continuous Batching Scheduler Engine."""
    def __init__(self, config: SchedulerConfig, engine: MockTensorEngine):
        self.config = config
        self.engine = engine
        self.mem_manager = PagedMemoryManager(config)
        self.waiting_queue: List[InferenceRequest] = []
        self.running_batch: List[InferenceRequest] = []
        self._is_active = False

    def submit_request(self, prompt_tokens: List[int], config: GenerationConfig) -> str:
        req_id = f"req-{uuid.uuid4().hex[:8]}"
        req = InferenceRequest(
            request_id=req_id,
            prompt_tokens=prompt_tokens,
            config=config
        )
        # Sort waiting queue by priority level
        self.waiting_queue.append(req)
        self.waiting_queue.sort(key=lambda r: r.config.priority, reverse=True)
        return req_id

    def _preempt_lowest_priority(self) -> bool:
        """Evakuasi request dengan prioritas terendah saat kondisi memori kritis."""
        if not self.running_batch:
            return False
            
        # Cari request running dengan priority terendah dan eksekusi terpendek
        victim = sorted(
            self.running_batch, 
            key=lambda r: (r.config.priority, -len(r.generated_tokens))
        )[0]
        
        self.mem_manager.free_request(victim.request_id)
        self.running_batch.remove(victim)
        victim.status = RequestStatus.PREEMPTED
        
        # Masukkan kembali ke antrean terdepan untuk di-recompute nanti
        self.waiting_queue.insert(0, victim)
        return True

    def _schedule_iteration(self) -> None:
        """Menyusun batch dinamis untuk iterasi berikutnya (Step Phase)."""
        # 1. Bersihkan request yang telah selesai
        finished_requests = [
            req for req in self.running_batch 
            if req.status == RequestStatus.COMPLETED
        ]
        for req in finished_requests:
            self.mem_manager.free_request(req.request_id)
            self.running_batch.remove(req)

        # 2. Promosi request dari waiting_queue ke running_batch
        while self.waiting_queue and len(self.running_batch) < self.config.max_batch_size:
            candidate = self.waiting_queue[0]
            
            # Validasi apakah memori cukup untuk alokasi awal prefill
            if self.mem_manager.can_allocate(len(candidate.prompt_tokens), 1):
                self.waiting_queue.pop(0)
                self.mem_manager.allocate_for_request(
                    candidate.request_id, 
                    len(candidate.prompt_tokens)
                )
                candidate.status = RequestStatus.RUNNING
                self.running_batch.append(candidate)
            else:
                # Memori penuh, hentikan promosi request baru
                break

    async def run_loop(self) -> None:
        """Siklus eksekusi event-loop terisolasi."""
        self._is_active = True
        
        while self._is_active:
            if not self.waiting_queue and not self.running_batch:
                await asyncio.sleep(0.005)
                continue

            self._schedule_iteration()

            if not self.running_batch:
                await asyncio.sleep(0.005)
                continue

            # Validasi kebutuhan ekspansi alokasi memory per token aktif
            for req in list(self.running_batch):
                if not self.mem_manager.can_allocate(req.total_tokens, 1):
                    # Trigger preempting jika kapasitas block habis
                    preemption_success = self._preempt_lowest_priority()
                    if not preemption_success:
                        # Deadlock fallback: break eksekusi dan tunggu pembebasan memori
                        break

            # Forwarding Step melalui Inference Hardware Execution
            current_timestamp = time.monotonic()
            next_tokens = await self.engine.step(self.running_batch)

            for req, token in zip(self.running_batch, next_tokens):
                now = time.monotonic()
                if req.start_time is None:
                    req.start_time = now
                    req.ttft_latency = now - req.arrival_time
                    req._last_token_timestamp = now
                else:
                    assert req._last_token_timestamp is not None
                    req.token_latencies.append(now - req._last_token_timestamp)
                    req._last_token_timestamp = now

                req.generated_tokens.append(token)
                self.mem_manager.allocate_for_request(req.request_id, req.total_tokens)

                # Evaluasi kriteria selesai: Token EOS (50256) atau max token limit
                if token == 50256 or len(req.generated_tokens) >= req.config.max_new_tokens:
                    req.status = RequestStatus.COMPLETED
                    req.finish_time = now

    def stop(self) -> None:
        self._is_active = False


# Telemetry and Execution Demonstration
async def main() -> None:
    # Spesifikasi Hardware: 1x NVIDIA A100 (80GB VRAM)
    # Model: Bobot 30GB FP16, KV-cache consumption: ~320KB/token
    config = SchedulerConfig(
        max_batch_size=4,
        max_model_len=4096,
        gpu_memory_bytes=80 * 1024**3,        # 80 GB
        model_weight_bytes=30 * 1024**3,      # 30 GB
        bytes_per_token_kv=320 * 1024,        # 320 KB per token
        block_size=16
    )
    
    engine = MockTensorEngine()
    scheduler = ProductionContinuousScheduler(config, engine)
    
    # Jalankan background scheduler worker loop
    loop_task = asyncio.create_task(scheduler.run_loop())

    print("[SYSTEM] Continuous Batching Engine Aktif.")
    
    # Simulasi submit request secara konkurensi
    req_ids = []
    for i in range(6):
        prompt_len = 128 if i % 2 == 0 else 512
        priority = 2 if i == 0 else 0  # Request 0 diset priority tinggi
        gen_len = 5 + (i * 2)
        rid = scheduler.submit_request(
            prompt_tokens=[1] * prompt_len,
            config=GenerationConfig(max_new_tokens=gen_len, priority=priority)
        )
        req_ids.append(rid)

    # Monitor progres hingga semua request selesai
    await asyncio.sleep(1.0)
    scheduler.stop()
    await loop_task

    print("\n[TELEMETRY] Laporan Metrik Eksekusi:")
    for rid in req_ids:
        # Cari data request
        matching = [r for r in scheduler.running_batch + scheduler.waiting_queue if r.request_id == rid]
        if not matching:
            continue
        req = matching[0]
        avg_itl = sum(req.token_latencies) / len(req.token_latencies) if req.token_latencies else 0.0
        print(f"Request: {req.request_id} | Status: {req.status.value:<9} | Priority: {req.config.priority} | "
              f"TTFT: {req.ttft_latency*1000 if req.ttft_latency else 0.0:.2f}ms | "
              f"Mean ITL: {avg_itl*1000:.2f}ms | Generated: {len(req.generated_tokens)} tok")

    print(f"\nKV Cache Peak Utilization: {scheduler.mem_manager.get_utilization() * 100:.4f}%")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 7. Edge Cases & Failure Modes

Dalam produksi beban tinggi, continuous batching scheduler dapat mengalami kondisi anomali spesifik yang wajib diisolasi:

### 1. KV-Cache Trashing & Preemption Deadlock
* **Skenario**: Trafik masuk memiliki prompt panjang secara massal. Seluruh memori KV dialokasikan. Setiap langkah decode memerlukan slot baru, tetapi memori fisik bernilai 0. Scheduler memutus request A untuk di-*preempt*. Namun, token berikutnya dari request B langsung menyerap kapasitas kosong tersebut. Pada iterasi berikutnya, request B butuh alokasi lagi sehingga scheduler mem-preempt request B untuk memberi jalan request C.
* **Mitigasi**: Implementasi *Watermark Allocation Protection*. Tetapkan batas ambang (misal, 5% memori cadangan permanen). Jangan masukkan request baru dari `waiting_queue` jika utilisasi blok mencapai > 85%, sisakan sisa blok murni untuk completion request yang sedang aktif.

### 2. Prompt-Bombing & Tail-Latency Collapse (Head-of-Line Bottleneck)
* **Skenario**: Pengguna mengirimkan prompt berukuran 64.000 token pada endpoint publik yang melayani chat reguler (100 token). Komputasi prefill untuk prompt 64k token tersebut memakan waktu 3 detik di GPU. Semua request decode interaktif lain mengalami pembekuan (*starvation*), mengakibatkan lonjakan metrik p99 ITL dari 25ms menjadi 3000ms.
* **Mitigasi**: **Chunked Prefill** (misal membagi prefill ke segmen per 512 token) atau menerapkan **Disaggregated Prefill-Decode Architecture**, di mana node worker prefill dipisahkan secara fisik dari node worker decode melalui transfer KV-cache via RDMA.

### 3. Asymmetric Tensor-Parallel Desynchronization
* **Skenario**: Ketika menjalankan Tensor Parallelism (TP) di atas 8 GPU (misal instance AWS `p4de.24xlarge`), salah satu GPU mengalami thermal throttling, menurunkan *clock speed* core sebesar 15%. Operasi `all-reduce` (NCCL) pada setiap transformer layer akan tersendat pada GPU yang paling lambat.
* **Mitigasi**: Health check tingkat rendah (*watchdog worker*) memantau variansi runtime kernel GPU individual. Jika deviasi delta eksekusi step melebihi 10% antar rank GPU, cluster orchestrator menandai node tersebut sebagai *unhealthy* dan mengarahkan trafik keluar melalui circuit breaker.

---

## 8. Trade-offs & Alternatif Solusi

| Dimensi Arsitektural | Monolithic Serving (Unified Prefill & Decode) | Disaggregated Serving (Split Prefill & Decode Nodes) | Speculative Decoding / Medusa |
| :--- | :--- | :--- | :--- |
| **Kelebihan Utama** | - Infrastruktur sederhana<br>- Tidak ada latensi transfer KV-Cache via jaringan<br>- Biaya implementasi awal rendah | - Isolasi total TTFT dan ITL<br>- Resource utilization optimal (Prefill: Compute, Decode: Bandwidth)<br>- Eliminasi tail-latency degradation | - Percepatan 1.5x - 2.5x ITL pada tugas decoding memory-bound<br>- Biaya GPU per token menurun drastis |
| **Kelemahan** | - Tail-latency ITL mudah terganggu lonjakan prefill<br>- Trade-off konstan antara TTFT dan throughput | - Membutuhkan overhead transfer KV-Cache via ultra-fast network (InfiniBand/RoCE)<br>- Kompleksitas routing request tinggi | - Memerlukan penambahan draft model atau model head ekstra<br>- Utilisasi compute tambahan jika acceptance rate token rendah |
| **Throughput (Token/s/$)** | Baseline (Sedang) | Tinggi (Optimal untuk enterprise scale) | Sangat Tinggi (Bila target task predictable) |
| **Karakteristik TCO** | Efisien pada volume trafik rendah-menengah (< 100 req/sec) | Paling efisien pada volume massif multi-tenant (> 1000 req/sec) | Mengurangi TCO decode worker hingga 40% |
| **Rekomendasi Deployment** | Internal tools, single-task agents, low-budget MVP | Multi-tenant Tier-1 LLM Platform (Enterprise Core) | Layanan streaming chat latency-critical consumer-facing |

---

## 9. Best Practices & Standard Industri

1. **Metrik Observabilitas Standar Produksi**:
   * Jangan gunakan *CPU/GPU Utilization* sebagai metrik tunggal pemicu autoscaling.
   * Gunakan indikator performa utama berikut:
     * **TTFT (Time-To-First-Token)**: Targetkan $P_{95} < 800\text{ms}$ untuk interaksi interaktif.
     * **ITL (Inter-Token Latency)**: Targetkan $P_{99} < 40\text{ms}$ (setara kecepatan baca 25 token/detik).
     * **KV-Cache Memory Utilization**: Skala pod horizontal saat penggunaan rata-rata mencapai $\ge 75\%$.
     * **Waiting Queue Length**: Skala langsung saat queue $> 0$ bertahan selama $> 5$ detik berturut-turut.
2. **KEDA Autoscaling Specification**:
   Implementasikan KEDA (Kubernetes Event-driven Autoscaling) dengan memonitor metrik Prometheus dari vLLM/TGI:
   ```yaml
   apiVersion: keda.sh/v1alpha1
   kind: ScaledObject
   metadata:
     name: llm-serving-scaler
   spec:
     scaleTargetRef:
       name: vllm-worker
     minReplicaCount: 2
     maxReplicaCount: 20
     cooldownPeriod: 300
     triggers:
     - type: prometheus
       metadata:
         serverAddress: http://prometheus-server.monitoring.svc.cluster.local:9090
         metricName: vllm_num_requests_waiting
         query: sum(vllm:num_requests_waiting{model="llama-3-70b"})
         threshold: '5'
   ```
3. **Pengaturan Alokasi Presisi Bobot & KV**:
   * Simpan model dalam format native **FP8 (Floating Point 8)** jika didukung GPU (NVIDIA Ada Lovelace / Hopper) atau **AWQ / GPTQ (4-bit)** untuk memangkas konsumsi bandwidth memory.
   * Aktifkan **KV-Cache Quantization (FP8)**. Ini menggandakan ukuran konteks efektif per instance GPU tanpa menurunkan performa output model secara signifikan.

---

## 10. Hands-on Lab Exercise

### Judul Lab: Profiling TTFT, ITL, dan Stress-Testing Preemption pada Continuous Batching Engine

#### Skenario Lab
Anda bertindak sebagai Principal Inference Engineer yang ditugaskan untuk menguji ketahanan runtime serving terhadap lonjakan trafik acak (*traffic burst*), menganalisis perbedaan TTFT dan ITL di bawah saturasi, serta mengevaluasi efisiensi biaya GPU.

#### Langkah Pelaksanaan

**Langkah 1: Setup Lingkungan dan Dependensi**
Pastikan Python 3.10+ terpasang, lalu siapkan direktori kerja:
```bash
mkdir -p inference_lab && cd inference_lab
python3 -m venv venv && source venv/bin/activate
pip install numpy tabulate
```

**Langkah 2: Buat Skrip Stress Tester (`stress_bench.py`)**
Simulasikan beban dinamis dengan menuliskan skrip untuk menginjeksi 100 request simultan dengan variasi panjang prompt (short: 64 token, long: 2048 token) ke dalam engine yang telah diimplementasikan pada Bagian 6:

```python
# stress_bench.py
import asyncio
import random
import time
from tabulate import tabulate
from scheduler_engine import ProductionContinuousScheduler, SchedulerConfig, MockTensorEngine, GenerationConfig

async def run_stress_test():
    # Setup konfigurasi GPU dengan kapasitas memori terbatas untuk memicu preemption
    config = SchedulerConfig(
        max_batch_size=8,
        max_model_len=2048,
        gpu_memory_bytes=16 * 1024**3,        # 16 GB VRAM Terbatas
        model_weight_bytes=10 * 1024**3,      # 10 GB Bobot Model (Sisa 6GB KV)
        bytes_per_token_kv=128 * 1024,        # 128 KB per token
        block_size=16
    )
    
    engine = MockTensorEngine()
    scheduler = ProductionContinuousScheduler(config, engine)
    scheduler_task = asyncio.create_task(scheduler.run_loop())
    
    print("[INIT] Mengirimkan 40 request secara serentak ke dalam antrean...")
    
    req_tracker = []
    
    # Injeksi beban campuran (Mix Load)
    for i in range(40):
        # 20% request adalah long prompt (1024 token), 80% short prompt (64 token)
        is_long = random.random() < 0.2
        prompt_len = 1024 if is_long else 64
        gen_tokens = random.randint(32, 64)
        priority = 1 if i % 10 == 0 else 0
        
        rid = scheduler.submit_request(
            prompt_tokens=[42] * prompt_len,
            config=GenerationConfig(max_new_tokens=gen_tokens, priority=priority)
        )
        req_tracker.append(rid)

    # Monitor eksekusi
    start_bench = time.monotonic()
    while True:
        all_completed = True
        # Cek apakah semua request selesai
        for r in scheduler.running_batch + scheduler.waiting_queue:
            if r.status.value != "COMPLETED":
                all_completed = False
                break
        
        if all_completed and len(scheduler.waiting_queue) == 0:
            break
            
        await asyncio.sleep(0.1)

    total_wall_time = time.monotonic() - start_bench
    scheduler.stop()
    await scheduler_task
    
    # Kumpulkan statistik
    all_requests = scheduler.running_batch
    ttft_list = [r.ttft_latency * 1000 for r in all_requests if r.ttft_latency]
    itl_list = [
        lat * 1000 
        for r in all_requests 
        for lat in r.token_latencies
    ]
    total_tokens_generated = sum(len(r.generated_tokens) for r in all_requests)
    
    # Hitung Unit Economics (Asumsi: Sewa GPU A10 = $1.00 / jam)
    gpu_cost_per_hour = 1.00
    hours_elapsed = total_wall_time / 3600.0
    cost_per_million = (gpu_cost_per_hour * hours_elapsed) / (total_tokens_generated / 1_000_000)

    # Render Tabel Telemetri
    ttft_list.sort()
    itl_list.sort()
    
    def p(data, percentile):
        if not data:
            return 0.0
        k = (len(data) - 1) * percentile
        f = int(k)
        c = f + 1 if f + 1 < len(data) else f
        return data[f] + (data[c] - data[f]) * (k - f)

    table_data = [
        ["Total Runtime (s)", f"{total_wall_time:.2f}s"],
        ["Total Generated Tokens", f"{total_tokens_generated} tokens"],
        ["Throughput Sistem", f"{total_tokens_generated / total_wall_time:.2f} tok/s"],
        ["TTFT Median (p50)", f"{p(ttft_list, 0.50):.2f} ms"],
        ["TTFT Tail (p99)", f"{p(ttft_list, 0.99):.2f} ms"],
        ["ITL Median (p50)", f"{p(itl_list, 0.50):.2f} ms"],
        ["ITL Tail (p99)", f"{p(itl_list, 0.99):.2f} ms"],
        ["Unit Economics", f"${cost_per_million:.4f} / 1M Tokens"]
    ]
    
    print("\n" + tabulate(table_data, headers=["Metrik", "Nilai Evaluasi"], tablefmt="fancy_grid"))

if __name__ == "__main__":
    asyncio.run(run_stress_test())
```

**Langkah 3: Jalankan Eksekusi Lab**
```bash
python3 stress_bench.py
```

#### Verifikasi Hasil dan Kriteria Sukses
1. Output terminal menampilkan tabel ringkasan metrik tanpa eksepsi runtime `IndexError` atau OOM deadlock.
2. Nilai `TTFT Tail (p99)` terlihat secara terukur lebih tinggi daripada `TTFT Median (p50)`, membuktikan adanya antrean pada saat *batch admission limit* tercapai.
3. Nilai `ITL Tail (p99)` tetap stabil dalam range deviasi yang sempit (< 3x dari p50), membuktikan efektivitas continuous batching yang mengisolasi phase prefill dari decode degradation.
4. Anda berhasil menghitung metrik unit economics ($/1M token) yang merefleksikan biaya operasional GPU secara akurat.