# BAB 10: PRODUCTION AI ENGINEERING DEPLOYMENT, OBSERVABILITY & GOVERNANCE

## Modul 01: High-Throughput Inference Serving, Continuous Batching, dan Memory-Aware Engine Architecture

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Menganalisis Bottleneck Inferensi LLM**: Membedakan karakteristik komputasi dan memori antara fase *Prefill* (compute-bound) dan fase *Decode* (memory-bandwidth bound) pada arsitektur Transformer modern.
2. **Mengalkulasi Memory Footprint KV-Cache**: Menghitung kebutuhan VRAM untuk KV-cache secara deterministik berdasarkan parameter model ($n_{\text{layers}}, d_{\text{head}}, n_{\text{kv\_heads}}$, precision) dan target konkurensi throughput.
3. **Mengimplementasikan Logika PagedAttention & Continuous Batching**: Merancang mekanisme penjadwalan iterasi (*iteration-level scheduling*) dan manajemen memori terfragmentasi non-kontigu berbasis tabel halaman virtual.
4. **Membangun Inference Gateway Standar Produksi**: Mengembangkan asynchronous model serving proxy menggunakan Python/AsyncIO yang menangani *backpressure*, *dynamic queue management*, pembatalan klien (*cancellation propagation*), dan *streaming Server-Sent Events (SSE)*.
5. **Menerapkan Telemetri Kinerja Rendah-Latensi**: Menginstrumentasikan metrik inti (*Time to First Token* [TTFT], *Inter-Token Latency* [ITL], dan *KV-Cache Utilization*) sesuai spesifikasi OpenTelemetry dan Prometheus.

---

### 2. Concept Overview

Penyajian model fondasi (*LLM Serving*) di lingkungan produksi menghadapi batasan fisik perangkat keras akselerator (GPU/TPU) yang berbeda secara fundamental dari inferensi model *deep learning* konvensional (ResNet, BERT). Inferensi LLM autoregresif mengeksekusi dua fase berurutan dengan profil konsumsi sumber daya asimetris:

```
[Prompt Masuk] 
       │
       ▼
┌────────────────────────────────────────────────────────┐
│ 1. Phase 1: Prefill / Prompt Processing                │
│    - Memproses seluruh prompt konteks secara paralel   │
│    - Compute-Bound (Pemanfaatan Tensor Core Maksimal)  │
│    - Karakteristik: High FLOPs/byte, Arithmetic High   │
└────────────────────────────────────────────────────────┘
       │
       ▼  Menghasilkan Token Pertama (Time To First Token / TTFT)
┌────────────────────────────────────────────────────────┐
│ 2. Phase 2: Autoregressive Decode                      │
│    - Menghasilkan 1 token per langkah (step-by-step)   │
│    - Memory-Bandwidth Bound                            │
│    - Membaca Bobot + Membaca Seluruh KV Cache Lama     │
│    - Karakteristik: Low Arithmetic Intensity           │
└────────────────────────────────────────────────────────┘
       │
       ▼  Selesai saat token <EOS> atau max_tokens tercapai
[Output Streaming Selesai]
```

Dalam skenario serving naif (*static batching*), server mengelompokkan request dan mengunci ukuran batch hingga request terpanjang dalam batch selesai dieksekusi. Hal ini menyebabkan dua inefisiensi kritis:
1. **Bubble Latensi & Idle Resource**: GPU Tensor Core menganggur menunggu sekuens pendek yang telah memancarkan token `<EOS>` sementara sekuens panjang belum selesai.
2. **Fragmentasi Memori KV-Cache**: Memori GPU dialokasikan di muka (*pre-allocation*) untuk panjang konteks maksimum teoritis, menyebabkan pemborosan VRAM sebesar 60–80% akibat alokasi kontigu yang tidak pernah terpakai.

Arsitektur serving generasi baru mengatasi hambatan ini dengan memisahkan siklus eksekusi ke tingkat iterasi (*Continuous Batching* atau *Iteration-Level Scheduling*) dan memvirtualisasikan memori cache representasi atensi (*PagedAttention*).

---

### 3. Why It Matters

Penerapan serving arsitektur enterprise bukan sekadar peningkatan throughput mikro; ini adalah pembeda mendasar antara arsitektur bernilai ekonomis tinggi versus sistem yang kolaps pada beban konkurensi menengah:

- **Dampak Finansial (GPU Cost Amortization)**: Pada kluster GPU H100 SXM5 80GB, static batching biasanya hanya mampu mempertahankan konkurensi 4–8 sekuens konteks panjang sebelum mengalami *Out of Memory* (CUDA OOM). Dengan PagedAttention dan continuous batching, kluster yang sama dapat menampung konkurensi 32–64 sekuens tanpa degradasi latensi rata-rata, memangkas biaya infrastruktur per *token served* hingga 4x–8x.
- **SLA & User Experience (TTFT vs. ITL)**: Pengguna mentoleransi waktu tunggu awal yang moderat (TTFT $\le 800\text{ ms}$), tetapi membutuhkan kelancaran perseptual saat membaca teks streaming (*Inter-Token Latency* atau ITL $\le 30\text{–}50\text{ ms}$). Static batching merusak ITL karena request baru yang membutuhkan prefill besar akan memblokir (*freeze*) seluruh langkah decode yang sedang berlangsung.
- **Resiliensi Sistem pada Lonjakan Trafik**: Tanpa penjadwalan sadar memori (*memory-aware scheduling*), lonjakan panjang konteks masukan mendadak akan memicu panic OOM pada kernel CUDA driver. Arsitektur produksi harus memiliki protokol preemption (*swap/recompute*) yang menjaga ketersediaan layanan meskipun VRAM jenuh.

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan alur kontrol dan data dari request masuk hingga eksekusi kernel CUDA pada distributed inference engine.

```
                      INCOMING INFERENCE REQUESTS (HTTP/gRPC)
                                      │
                                      ▼
             ┌──────────────────────────────────────────────────┐
             │       API Gateway & Reverse Proxy (Ingress)      │
             │   - SSE Protocol Termination & Auth Check        │
             │   - Request Sanitization & Schema Validation     │
             └────────────────────────┬─────────────────────────┘
                                      │
                                      ▼
             ┌──────────────────────────────────────────────────┐
             │          Continuous Batch Engine Scheduler       │
             │ ┌──────────────────────────────────────────────┐ │
             │ │ Request Queues (WAITING / RUNNING / SWAPPED) │ │
             │ └──────────────────────┬───────────────────────┘ │
             │                        ▼                         │
             │ ┌──────────────────────────────────────────────┐ │
             │ │         Block Allocator & Virtual Table      │ │
             │ │ - Logical Block to Physical Block Mapping    │ │
             │ │ - Prefill/Decode Batch Builder               │ │
             │ └──────────────────────────────────────────────┘ │
             └────────────────────────┬─────────────────────────┘
                                      │
              Worker Step IPC (Ray / Distributed SHM Socket)
                                      │
             ┌────────────────────────▼─────────────────────────┐
             │            GPU Worker Process (Tensor Parallel)   │
             │ ┌──────────────────────────────────────────────┐ │
             │ │ C++ Execution Engine (e.g., vLLM / TensorRT) │ │
             │ └──────────────────────┬───────────────────────┘ │
             │                        │                         │
             │         ┌──────────────┴──────────────┐          │
             │         ▼                             ▼          │
             │ ┌───────────────────────┐ ┌────────────────────┐ │
             │ │ FlashAttention/Paged  │ │ Model Weights      │ │
             │ │ Attention Kernels     │ │ (Sharded FP16/FP8) │ │
             │ └───────────┬───────────┘ └──────────┬─────────┘ │
             │             │                        │           │
             │             └───────────┬────────────┘           │
             │                         ▼                        │
             │           GPU High Bandwidth Memory (HBM)        │
             │   [ Block 0 ] [ Block 1 ] ... [ Block N-1 ]      │
             └──────────────────────────────────────────────────┘
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### 5.1 Formula Memori KV-Cache
Dalam transformer standar, untuk setiap layer, attention head menyimpan Key ($K$) dan Value ($V$) untuk seluruh konteks token masa lalu.

Ukuran KV-cache per token dapat dihitung secara matematis melalui rumus:

$$\text{Bytes Per Token} = 2 \times (\text{Key} + \text{Value}) = 2 \times 2 \times n_{\text{layers}} \times n_{\text{kv\_heads}} \times d_{\text{head}} \times P$$

Di mana:
- $n_{\text{layers}}$: Jumlah lapisan transformator.
- $n_{\text{kv\_heads}}$: Jumlah head Key/Value (pada Multi-Query Attention / Grouped-Query Attention, $n_{\text{kv\_heads}} \ll n_{\text{heads}}$).
- $d_{\text{head}}$: Dimensi masing-masing head ($\frac{d_{\text{model}}}{n_{\text{heads}}}$).
- $P$: Presisi penyimpanan dalam byte (FP16/BF16 = 2 bytes, FP8 = 1 byte).

**Contoh Kasus**: Model Llama-3-70B-Instruct ($n_{\text{layers}}=80, n_{\text{kv\_heads}}=8, d_{\text{head}}=128$):
$$\text{Size per token} = 4 \times 80 \times 8 \times 128 \times 2 \text{ bytes} = 655{,}360 \text{ bytes} \approx 640 \text{ KiB/token}$$

Jika server menampung 32 request secara simultan dengan panjang konteks 4.096 token:
$$\text{Total KV Cache} = 32 \times 4096 \times 640 \text{ KiB} \approx 83.88 \text{ GB}$$
Ini membuktikan bahwa KV-cache melampaui kapasitas VRAM dari satu GPU 80GB hanya untuk konteks dinamis, menuntut alokasi presisi tanpa fragmentasi.

#### 5.2 PagedAttention dan Virtual Block Allocation
Dalam implementasi standar tanpa paging, memori dialokasikan secara kontigu. Jika model mengalokasikan ruang untuk 2.048 token namun hanya menggunakan 500 token, sisanya menjadi fragmentasi internal (*internal fragmentation*). 

PagedAttention mengadopsi konsep *Virtual Memory Paging* dari Sistem Operasi:
1. Memori KV Cache GPU dibagi menjadi kumpulan blok fisik berukuran tetap (*Physical Blocks*), misalnya masing-masing menampung 16 token.
2. Setiap sekuens memiliki *Logical Blocks* yang dipetakan ke *Physical Blocks* acak melalui tabel halaman (*Block Table*).
3. Blok fisik dialokasikan hanya saat token baru dihasilkan dan blok sebelumnya telah terisi penuh. 

```
Logical Blocks (Sequence A):
Block 0 (Token 0-15)  --> Map to Physical Block 12
Block 1 (Token 16-31) --> Map to Physical Block 4
Block 2 (Token 32-47) --> Map to Physical Block 95 (Allocated dynamically)
```

Dengan arsitektur ini, pemborosan memori tereduksi hingga mendekati 0%, terbatas hanya pada fragmentasi internal di blok fisik terakhir dari sebuah sekuens ($< 16 \text{ token}$).

#### 5.3 Continuous Batching Scheduling Lifecycle
Penjadwal (*scheduler*) beroperasi pada tingkat *iteration-level loop*, bukan tingkat sekuens:
1. **Fetch Step**: Scheduler memeriksa antrean `WAITING` dan kapasitas blok KV-cache yang tersedia.
2. **Form Batch**: 
   - Request aktif dalam status `RUNNING` diprioritaskan untuk mengeksekusi 1 token decoding step.
   - Jika sisa blok fisik mencukupi, satu atau lebih request dari antrean `WAITING` dimasukkan ke dalam batch untuk fase prefill.
3. **Chunked Prefill**: Untuk mencegah prefill dari prompt besar memonopoli komputasi dan memicu spike ITL pada request yang sedang decode, prompt dibagi menjadi segmen-segmen (*chunks*, misal 512 token) dan di-interleave bersama token-token decode aktif.
4. **Retire/Preempt**: Request yang menghasilkan token `<EOS>` segera melepaskan blok fisiknya kembali ke allocator pool. Request yang tidak dapat dialokasikan blok baru akibat VRAM jenuh dipindahkan ke antrean `SWAPPED` atau dipreempt menggunakan recomputation.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi Production-Ready Asynchronous Serving Gateway dan Memory-Aware Continuous Batching Scheduler menggunakan Python 3.11+, AsyncIO, dan Pydantic. Arsitektur memisahkan state management, token block management, and streaming response handler.

```python
# inference_runtime.py
"""
Production-grade Inference Serving Engine Engine Prototype
Demonstrating Async Continuous Batching, Virtual Block Cache Allocation,
and Streaming Response Pipeline.
"""

from __future__ import annotations

import asyncio
import enum
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import AsyncGenerator, Dict, List, Optional, Set

from pydantic import BaseModel, Field

# Setup Enterprise Logging Configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
)
logger = logging.getLogger("InferenceRuntime")


# =====================================================================
# Domain Models & Schemas
# =====================================================================

class GenerationConfig(BaseModel):
    max_tokens: int = Field(default=128, ge=1, le=4096)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    stop_tokens: Set[str] = Field(default_factory=lambda: {"<EOS>", "<|endoftext|>"})


class InferenceRequest(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    prompt: str = Field(..., min_length=1)
    prompt_tokens: List[int]
    config: GenerationConfig


class StreamChunk(BaseModel):
    request_id: str
    token_str: str
    token_id: int
    is_last: bool
    ttft_ms: Optional[float] = None
    itl_ms: Optional[float] = None


class SequenceStatus(enum.Enum):
    WAITING = "WAITING"
    RUNNING = "RUNNING"
    PREEMPTED = "PREEMPTED"
    FINISHED = "FINISHED"


# =====================================================================
# Memory Management: Virtual KV Cache Allocator
# =====================================================================

@dataclass
class PhysicalBlock:
    block_id: int
    ref_count: int = 0
    is_allocated: bool = False


class VirtualBlockAllocator:
    """
    Manages physical memory allocations simulating GPU KV Cache blocks.
    Prevents external memory fragmentation using fixed-size allocation.
    """
    def __init__(self, num_blocks: int, block_size: int = 16) -> None:
        self.num_blocks = num_blocks
        self.block_size = block_size  # Number of tokens per block
        self.blocks: List[PhysicalBlock] = [
            PhysicalBlock(block_id=i) for i in range(num_blocks)
        ]
        self.free_blocks: List[int] = list(range(num_blocks))

    def has_available_blocks(self, count: int = 1) -> bool:
        return len(self.free_blocks) >= count

    def allocate(self) -> int:
        if not self.free_blocks:
            raise MemoryError("Out of Virtual Memory: No physical KV blocks available")
        block_id = self.free_blocks.pop(0)
        self.blocks[block_id].is_allocated = True
        self.blocks[block_id].ref_count = 1
        return block_id

    def free(self, block_id: int) -> None:
        block = self.blocks[block_id]
        if not block.is_allocated:
            logger.warning("Double free detected for block_id: %d", block_id)
            return
        block.ref_count -= 1
        if block.ref_count <= 0:
            block.is_allocated = False
            block.ref_count = 0
            self.free_blocks.append(block_id)

    @property
    def free_block_count(self) -> int:
        return len(self.free_blocks)

    @property
    def utilization(self) -> float:
        return (self.num_blocks - len(self.free_blocks)) / self.num_blocks


# =====================================================================
# Sequence & State Tracking
# =====================================================================

@dataclass
class Sequence:
    request: InferenceRequest
    status: SequenceStatus = SequenceStatus.WAITING
    output_tokens: List[int] = field(default_factory=list)
    block_table: List[int] = field(default_factory=list)
    created_at: float = field(default_factory=time.perf_counter)
    first_token_time: Optional[float] = None
    last_token_time: Optional[float] = None
    stream_channel: asyncio.Queue[Optional[StreamChunk]] = field(
        default_factory=asyncio.Queue
    )

    def total_tokens(self) -> int:
        return len(self.request.prompt_tokens) + len(self.output_tokens)

    def num_required_blocks(self, block_size: int) -> int:
        total = self.total_tokens()
        return (total + block_size - 1) // block_size


# =====================================================================
# Continuous Batching Engine Scheduler
# =====================================================================

class ContinuousBatchScheduler:
    """
    Iteration-level Scheduler managing prefill and decoding continuous dynamic batches.
    """
    def __init__(self, allocator: VirtualBlockAllocator) -> None:
        self.allocator = allocator
        self.waiting_queue: List[Sequence] = []
        self.running_queue: List[Sequence] = []
        self._shutdown_event = asyncio.Event()

    def add_sequence(self, seq: Sequence) -> None:
        self.waiting_queue.append(seq)
        logger.debug("Request %s enqueued into WAITING queue", seq.request.request_id)

    def abort_sequence(self, request_id: str) -> None:
        """Handle client disconnections and resource deallocations."""
        for seq in self.running_queue:
            if seq.request.request_id == request_id:
                logger.info("Aborting running request: %s", request_id)
                self._free_sequence_blocks(seq)
                seq.status = SequenceStatus.FINISHED
                self.running_queue.remove(seq)
                return

        for seq in self.waiting_queue:
            if seq.request.request_id == request_id:
                logger.info("Aborting waiting request: %s", request_id)
                seq.status = SequenceStatus.FINISHED
                self.waiting_queue.remove(seq)
                return

    def _free_sequence_blocks(self, seq: Sequence) -> None:
        for block_id in seq.block_table:
            self.allocator.free(block_id)
        seq.block_table.clear()

    def step(self) -> List[StreamChunk]:
        """
        Single continuous iteration loop.
        Allocates memory, forms the batch, simulates inference forward, and yields tokens.
        """
        output_chunks: List[StreamChunk] = []
        current_time = time.perf_counter()

        # 1. Promote WAITING sequences if memory permits
        schedulable_waiting: List[Sequence] = []
        for seq in list(self.waiting_queue):
            needed_blocks = seq.num_required_blocks(self.allocator.block_size)
            if self.allocator.has_available_blocks(needed_blocks):
                for _ in range(needed_blocks):
                    seq.block_table.append(self.allocator.allocate())
                seq.status = SequenceStatus.RUNNING
                self.waiting_queue.remove(seq)
                self.running_queue.append(seq)
            else:
                # FIFO starvation prevention: Wait until resources free
                break

        # 2. Process RUNNING sequences (Decode step)
        finished_sequences: List[Sequence] = []

        for seq in self.running_queue:
            # Check if block allocation is required for next token
            needed_blocks = seq.num_required_blocks(self.allocator.block_size)
            if len(seq.block_table) < needed_blocks:
                if self.allocator.has_available_blocks(1):
                    seq.block_table.append(self.allocator.allocate())
                else:
                    # Preemption strategy: simple stall/abort for this baseline
                    logger.error(
                        "KV Cache Exhaustion! Sequence %s dropped out of memory.",
                        seq.request.request_id,
                    )
                    self._free_sequence_blocks(seq)
                    seq.status = SequenceStatus.PREEMPTED
                    finished_sequences.append(seq)
                    continue

            # Simulate Token Generation (Forward Execution Emulation)
            # Dummy logic: generate next incremental token
            simulated_token_id = 1000 + len(seq.output_tokens)
            simulated_token_str = f" token_{simulated_token_id}"
            seq.output_tokens.append(simulated_token_id)

            # Compute timing metrics
            is_first = seq.first_token_time is None
            if is_first:
                seq.first_token_time = current_time
                ttft_ms = (seq.first_token_time - seq.created_at) * 1000.0
                itl_ms = 0.0
            else:
                ttft_ms = None
                itl_ms = (current_time - (seq.last_token_time or current_time)) * 1000.0
            
            seq.last_token_time = current_time

            # Determine termination condition
            is_max = len(seq.output_tokens) >= seq.request.config.max_tokens
            is_eos = simulated_token_str.strip() in seq.request.config.stop_tokens
            is_terminal = is_max or is_eos

            chunk = StreamChunk(
                request_id=seq.request.request_id,
                token_str=simulated_token_str,
                token_id=simulated_token_id,
                is_last=is_terminal,
                ttft_ms=ttft_ms,
                itl_ms=itl_ms,
            )
            output_chunks.append(chunk)

            if is_terminal:
                seq.status = SequenceStatus.FINISHED
                finished_sequences.append(seq)

        # 3. Clean up finished sequences
        for seq in finished_sequences:
            self._free_sequence_blocks(seq)
            if seq in self.running_queue:
                self.running_queue.remove(seq)

        return output_chunks


# =====================================================================
# Engine Orchestration & Ingress Layer
# =====================================================================

class ModelServingEngine:
    def __init__(self, num_blocks: int = 1024, block_size: int = 16) -> None:
        self.allocator = VirtualBlockAllocator(num_blocks=num_blocks, block_size=block_size)
        self.scheduler = ContinuousBatchScheduler(self.allocator)
        self.active_sequences: Dict[str, Sequence] = {}
        self._engine_task: Optional[asyncio.Task[None]] = None
        self._is_running = False

    async def start(self) -> None:
        self._is_running = True
        self._engine_task = asyncio.create_task(self._execution_loop())
        logger.info("Inference Serving Engine background loop initialized.")

    async def stop(self) -> None:
        self._is_running = False
        if self._engine_task:
            self._engine_task.cancel()
            await asyncio.gather(self._engine_task, return_exceptions=True)
        logger.info("Inference Serving Engine stopped gracefully.")

    async def _execution_loop(self) -> None:
        """Continuous batching execution loop ticking at microsecond rates."""
        try:
            while self._is_running:
                if self.scheduler.running_queue or self.scheduler.waiting_queue:
                    # Execute iteration step
                    chunks = self.scheduler.step()
                    for chunk in chunks:
                        seq = self.active_sequences.get(chunk.request_id)
                        if seq:
                            await seq.stream_channel.put(chunk)
                            if chunk.is_last:
                                await seq.stream_channel.put(None)  # Sentinel to close stream
                                self.active_sequences.pop(chunk.request_id, None)
                    
                    # Yield CPU control slightly to allow event loop I/O multiplexing
                    await asyncio.sleep(0.005)
                else:
                    await asyncio.sleep(0.01)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.critical("Fatal crash in inference execution loop: %s", str(e), exc_info=True)

    async def generate_stream(
        self, request: InferenceRequest
    ) -> AsyncGenerator[StreamChunk, None]:
        """Entrypoint for serving streaming tokens to API clients."""
        sequence = Sequence(request=request)
        self.active_sequences[request.request_id] = sequence
        self.scheduler.add_sequence(sequence)

        try:
            while True:
                chunk = await sequence.stream_channel.get()
                if chunk is None:
                    break
                yield chunk
        except asyncio.CancelledError:
            logger.warning("Client disconnected prematurely: %s", request.request_id)
            self.scheduler.abort_sequence(request.request_id)
            self.active_sequences.pop(request.request_id, None)
            raise


# =====================================================================
# Execution Verification Simulation
# =====================================================================

async def main() -> None:
    # Initialize Engine with 128 physical blocks (128 * 16 = 2048 token cache capacity)
    engine = ModelServingEngine(num_blocks=128, block_size=16)
    await engine.start()

    # Create dummy workloads
    configs = GenerationConfig(max_tokens=8)
    req1 = InferenceRequest(
        prompt="Analyze quantum distributed architecture",
        prompt_tokens=[1, 45, 92, 102],
        config=configs,
    )
    req2 = InferenceRequest(
        prompt="Describe deep learning systems",
        prompt_tokens=[20, 88, 12],
        config=configs,
    )

    async def consume_stream(client_id: str, req: InferenceRequest) -> None:
        async for chunk in engine.generate_stream(req):
            if chunk.ttft_ms is not None:
                print(f"[{client_id}] TTFT: {chunk.ttft_ms:.2f}ms | First Token: '{chunk.token_str}'")
            else:
                print(f"[{client_id}] ITL: {chunk.itl_ms:.2f}ms | Token: '{chunk.token_str}'")

    # Run requests concurrently
    await asyncio.gather(
        consume_stream("Client-Alpha", req1),
        consume_stream("Client-Beta", req2),
    )

    await engine.stop()

if __name__ == "__main__":
    asyncio.run(main())
```

---

### 7. Edge Cases & Failure Modes

Pengoperasian serving engine pada skala enterprise menghadapi kegagalan sistemik yang tidak terlihat pada pengujian fungsional dasar:

#### 1. KV-Cache Exhaustion Mid-Generation
- **Kondisi**: Batch aktif telah melahap seluruh blok fisik bebas selama fase decode, sementara tidak ada sekuens yang mencapai token `<EOS>`.
- **Dampak**: Engine mengalami deadlock komputasi; model tidak dapat mengalokasikan memori untuk langkah berikutnya.
- **Strategi Mitigasi**: 
  - *Swapping*: Mentransfer blok halaman dari GPU HBM ke DRAM CPU melalui PCIe, lalu memulihkannya saat resource longgar (memiliki penalty performa tinggi).
  - *Preemption with Recomputation*: Hentikan sekuens berprioritas terendah, bebaskan seluruh blok memorinya kembali ke pool, lalu jadwalkan ulang sekuens tersebut dari awal (*re-prefill*) ketika VRAM tersedia.

#### 2. Prefill Starvation & Head-of-Line Blocking
- **Kondisi**: Masuknya request dengan konteks ekstra panjang (misal, 32.000 token) memicu komputasi matrix multiplication masif yang memakan waktu $\ge 1.500\text{ ms}$.
- **Dampak**: Puluhan request yang sedang dalam tahap decode mengalami stall parah; *Inter-Token Latency* melonjak drastis, merusak User Experience (UX) streaming.
- **Strategi Mitigasi**: Terapkan **Chunked Prefill** (misal: batasi maksimal 512 prefill token per batch iteration). Sisa prefill token dipecah ke beberapa siklus iterasi berikutnya bersamaan dengan proses decoding request lain.

#### 3. Client Cancellation Leakage
- **Kondisi**: Pengguna menutup browser atau koneksi jaringan terputus (TCP RST/FIN) saat model sedang meng-generate token ke-50 dari 2.048 target.
- **Dampak**: Jika inference gateway tidak mempropagasi event pemutusan koneksi ke internal engine, GPU akan tetap memproses komputasi token yang tersisa hingga selesai, membuang sumber daya secara cuma-cuma.
- **Strategi Mitigasi**: Manfaatkan `asyncio.CancelledError` pada stream handler API untuk langsung memanggil metode pembatalan eksplisit (`scheduler.abort_sequence`), yang secara deterministik membersihkan blok memori KV-cache yang terikat.

---

### 8. Trade-offs & Alternatif Solusi

Setiap keputusan desain dalam arsitektur inferensi membawa kompromi mendasar terhadap latensi, throughput, dan akurasi model:

| Solusi / Dimensi | vLLM (PagedAttention) | TensorRT-LLM | Triton + PyTorch Direct |
| :--- | :--- | :--- | :--- |
| **Throughput (Tokens/s)** | Sangat Tinggi (Optimal untuk LLM general) | Ekstrem (Teroptimasi secara native untuk NVIDIA) | Sedang hingga Rendah |
| **Portabilitas Hardware** | Multi-vendor (NVIDIA, AMD ROCm, Intel Gaudi) | Eksklusif NVIDIA GPU | Multi-vendor |
| **Operasional & Fleksibilitas** | Fleksibel, integrasi Pythonic mudah | Kompleks, menuntut kompilasi C++ engine artifacts | Sangat fleksibel, kustomisasi model bebas |
| **Presisi Kuantisasi** | FP8, AWQ, GPTQ, SqueezeLLM | FP8, INT4 AWQ, SmoothQuant | Tergantung implementation library |

#### Kuantisasi: FP16 vs. FP8 vs. INT4 AWQ
- **FP16 / BF16**: Mempertahankan akurasi matematis 100%, tetapi membatasi ukuran batch akibat konsumsi memori bobot dan KV-cache yang masif.
- **FP8 (Format E4M3 & E5M2)**: Standar modern untuk arsitektur Hopper/Ada Lovelace. Mengurangi ukuran bobot dan KV-cache sebesar 50% dengan degradasi perplexity hampir 0% ($< 0.1\%$). Sangat direkomendasikan untuk serving enterprise.
- **INT4 (AWQ/GPTQ)**: Mengompresi bobot ke 4-bit, ideal untuk memori terbatas, namun intensitas dekuantisasi *on-the-fly* pada decode stage dapat menambah sedikit overhead latensi jika tidak menggunakan kernel yang sangat teroptimasi.

---

### 9. Best Practices & Standard Industri

Untuk memenuhi standar SLA enterprise (misal: TTFT P99 $< 500\text{ ms}$, ITL P99 $< 40\text{ ms}$), arsitektur deployment wajib mengadopsi prinsip-prinsip berikut:

1. **Metrik Observabilitas Terpadu (Golden Signals LLM Serving)**:
   - `llm_time_to_first_token_seconds` (Histogram): Pantau pada persentil P50, P90, P99. Lonjakan mengindikasikan antrean prefill jenuh.
   - `llm_inter_token_latency_seconds` (Histogram): Indikator utama kelancaran inferensi fase decode.
   - `llm_kv_cache_usage_ratio` (Gauge): Pertahankan utilisasi pada rentang 75%–85%. Nilai $> 90\%$ mengindikasikan risiko preemption tinggi.
   - `llm_preemption_total` (Counter): Harus bernilai mendekati nol. Jika terus meningkat, lakukan down-throttle konkurensi atau autoscaling akselerator.

2. **Autoscaling Metric Selection**:
   - **JANGAN** menggunakan CPU Utilization atau GPU Compute Utilization sebagai pemicu *Horizontal Pod Autoscaler* (HPA) di Kubernetes. GPU utilization seringkali terbaca 100% meskipun hanya mengeksekusi decode untuk satu sekuens.
   - **GUNAKAN** metrik antrean aplikasi: `waiting_requests_depth` dan `kv_cache_usage_ratio`. Jika antrean menunggu melebihi ambang batas selama $\ge 30\text{ detik}$, segera picu penambahan Pod inferensi baru.

3. **Graceful Degradation via Load Shedding**:
   - Terapkan mekanisme penolakan beban (*load shedding*) berbasis HTTP 503 atau 429 ketika antrean `WAITING` melampaui toleransi antrean maksimum (`max_queue_depth`). Lebih baik menolak request di awal secara deterministik daripada membiarkan seluruh koneksi mengalami timeout di layer gateway.

---

### 10. Hands-on Lab Exercise

#### Skenario Lab
Anda ditugaskan menguji performa model serving engine dan menganalisis metrik inferensi di bawah tekanan konkurensi tinggi. Anda akan mengeksekusi engine, menjalankan load generation, dan mencatat perbandingan TTFT serta ITL ketika terjadi variasi panjang konteks.

#### File Setup
Simpan kode dari **Bagian 6** sebagai file bernama `inference_runtime.py`.

#### Langkah 1: Modifikasi dan Jalankan Stress Benchmarking
Buat skrip benchmark dengan nama `benchmark_stress.py`:

```python
# benchmark_stress.py
import asyncio
import time
import statistics
from typing import List
from inference_runtime import ModelServingEngine, InferenceRequest, GenerationConfig

async def run_benchmark(num_clients: int, prompt_len: int, max_tokens: int):
    # Setup engine dengan kapasitas blok terbatas untuk menguji memory pressure
    engine = ModelServingEngine(num_blocks=64, block_size=16)
    await engine.start()

    prompt_tokens = [42] * prompt_len
    config = GenerationConfig(max_tokens=max_tokens)
    
    ttft_records: List[float] = []
    itl_records: List[float] = []

    async def client_worker(worker_id: int):
        req = InferenceRequest(
            prompt="Simulated prompt payload",
            prompt_tokens=prompt_tokens,
            config=config,
        )
        async for chunk in engine.generate_stream(req):
            if chunk.ttft_ms is not None:
                ttft_records.append(chunk.ttft_ms)
            elif chunk.itl_ms is not None:
                itl_records.append(chunk.itl_ms)

    start_wall_time = time.perf_counter()
    
    # Jalankan request secara bersamaan
    workers = [client_worker(i) for i in range(num_clients)]
    await asyncio.gather(*workers)
    
    total_duration = time.perf_counter() - start_wall_time

    await engine.stop()

    print("\n" + "="*50)
    print(f"BENCHMARK RESULTS (Clients: {num_clients}, Context: {prompt_len}, Decode: {max_tokens})")
    print("="*50)
    print(f"Total Wall Time    : {total_duration:.2f} seconds")
    print(f"Total Tokens Decode: {len(itl_records)}")
    if ttft_records:
        print(f"TTFT Mean          : {statistics.mean(ttft_records):.2f} ms")
        print(f"TTFT P95           : {statistics.quantiles(ttft_records, n=20)[18]:.2f} ms")
    if itl_records:
        print(f"ITL Mean           : {statistics.mean(itl_records):.2f} ms")
        print(f"ITL P95            : {statistics.quantiles(itl_records, n=20)[18]:.2f} ms")
    print(f"Global Throughput  : {len(itl_records) / total_duration:.2f} tokens/sec")
    print("="*50 + "\n")

if __name__ == "__main__":
    # Test skenario konvergensi konkurensi: 16 klien dengan konteks moderat
    asyncio.run(run_benchmark(num_clients=16, prompt_len=64, max_tokens=32))
```

#### Langkah 2: Jalankan Evaluasi Eksekusi
Buka terminal dan jalankan benchmark:

```bash
python3 benchmark_stress.py
```

#### Langkah 3: Verifikasi Hasil & Pertanyaan Analisis
Amati output yang dihasilkan pada konsol terminal:
1. Perhatikan nilai **TTFT P95** versus **ITL P95**. Mengapa deviasi standar pada TTFT cenderung lebih besar daripada ITL saat konkurensi dinaikkan?
2. Ubah `num_blocks` pada `benchmark_stress.py` dari `64` menjadi `16` dan jalankan kembali script. Amati log error yang terjadi: Mengapa muncul pesan *KV Cache Exhaustion* dan bagaimana status urutan request yang dipreempt oleh penjadwal?
3. Modifikasi `prompt_len` menjadi `512` token dan catat dampaknya terhadap TTFT klien yang masuk terakhir dalam antrean continuous batching. Solusi arsitektural apa yang harus diaktifkan untuk mengatasi fenomena tersebut?