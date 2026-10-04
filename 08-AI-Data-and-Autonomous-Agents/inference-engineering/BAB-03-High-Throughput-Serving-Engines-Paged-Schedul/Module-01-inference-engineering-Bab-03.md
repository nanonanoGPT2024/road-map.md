# Bab 03: High-Throughput Serving Engines & Paged Scheduling (Module 01)

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Menganalisis Bottleneck Inferensi Konvensional**: Mengidentifikasi inefisiensi *static request-level batching* dan mengukur rasio fragmentasi memori (*internal vs. external fragmentation*) pada alokasi KV Cache kontigu.
2. **Merancang Mekanisme Paged KV Cache**: Mengimplementasikan arsitektur *paging* memori virtual yang memetakan *logical block addresses* ke *physical block frames* pada High Bandwidth Memory (HBM) GPU.
3. **Mengembangkan Continuous Iteration-Level Scheduler**: Mengonstruksi *scheduler* berorientasi iterasi (*iteration-level/step-level*) yang mampu menggabungkan fase *prefill* dan *decode* secara dinamis tanpa memblokir siklus eksekusi GPU.
4. **Mengimplementasikan Kebijakan Preemption**: Membangun mekanisme mitigasi *memory exhaustion* menggunakan teknik *swapping* (Host RAM $\leftrightarrow$ GPU HBM) dan *recomputation*.
5. **Mengoptimalkan Metrik Kritis Sistem**: Menurunkan *Time to First Token* (TTFT) dan *Inter-Token Latency* (ITL) sekaligus meningkatkan *engine throughput* (token/detik) hingga batas saturasi compute/memory bandwidth.

---

## 2. Concept Overview

Sistem penyajian Large Language Model (LLM) modern beroperasi di bawah batasan *memory bandwidth-bound* pada fase *auto-regressive decode*. Setiap token yang dihasilkan memerlukan pembacaan bobot model dan seluruh riwayat *Key-Value* (KV) Cache dari HBM ke *SRAM/Register Core*. 

Secara historis, mesin inferensi memperlakukan komputasi *sequence* seperti proses *batching* tradisional pada *deep learning* konvensional:

```
[Traditional Batching]
Req 1: |--- Prefill ---|------------ Decode ------------| [IDLE WAITING...]
Req 2: |--- Prefill ---|---- Decode ----| [IDLE WAITING...................]
Req 3: |--- Prefill ---|------------------------ Decode -------------------|
Batched Step Execution: Menunggu sequence terpanjang selesai sebelum batch baru diproses.
```

### Mental Model: Continuous Batching & Virtual Memory

Dua paradigma fundamental merevolusi arsitektur *serving engine*:

1. **Continuous (Iteration-Level) Batching**: Eksekusi tidak lagi diikat pada level *request*, melainkan pada level *iteration step*. Segera setelah suatu *sequence* menghasilkan token `<eos>`, posisinya dalam *active batch* langsung diisi oleh *token decode* dari *request* lain atau dialokasikan untuk fase *prefill request* baru.
2. **PagedAttention & Virtual Memory Mapping**: Terinspirasi oleh *virtual memory management* pada kernel sistem operasi (seperti paging pada arsitektur x86), KV cache dipecah menjadi blok-blok berukuran tetap (*block frames*). Sebuah *sequence* dialokasikan *logical blocks* yang dipetakan secara dinamis ke *physical blocks* GPU yang tidak harus berurutan (*non-contiguous*).

```
[Logical Memory (Token Sequence)]
Token Index: [ 0,  1,  2,  3] [ 4,  5,  6,  7] [ 8,  9, 10, 11]
Logical Block:     Block 0          Block 1          Block 2
                      |                |                |
                      v                v                v
[Block Table]      Frame 42         Frame 07         Frame 19
                      |                |                |
                      v                v                v
[Physical Memory (HBM GPU Pool)]
Physical Block: ... [Frame 07] ... [Frame 19] ... [Frame 42] ...
```

---

## 3. Why It Matters

Pada implementasi inferensi naif (misal: HuggingFace Accelerate baseline), memori untuk KV cache dialokasikan secara statis berdasarkan `max_sequence_length` (contoh: 2048 atau 4096 token) menggunakan tensor kontigu. Praktik ini memicu tiga jenis pemborosan memori struktural:

* **Reserved/Unused Memory (Hingga 60-80%)**: Sistem mengalokasikan memori untuk panjang maksimum, padahal panjang generasi aktual sering kali jauh lebih pendek.
* **Internal Fragmentation**: Alokasi berbasis *slot* tetap yang tidak terpakai oleh *sequence* pendek.
* **External Fragmentation**: Ruang memori yang tidak dapat dialokasikan karena ketidaktersediaan blok kontigu yang cukup besar, meskipun akumulasi memori bebas secara total masih mencukupi.

### Bottleneck Finansial dan Operasional

Dalam skala enterprise:
* Satu GPU NVIDIA H100 SXM5 (80 GB) memiliki batasan kapasitas yang ketat. Jika sebuah model LLaMA-3-70B di-kuantisasi ke 16-bit (FP16/BF16), bobot model mengonsumsi $\approx 140\text{ GB}$ (membutuhkan tensor parallel 2 GPU $\times$ 80 GB). Sisa memori $\approx 20\text{ GB}$ harus diperebutkan oleh KV Cache dan *scratchpad memory*.
* Mengurangi pemborosan KV Cache dari $70\%$ ke $<4\%$ via *paged allocation* menaikkan *concurrency limit* dari 4 *concurrent requests* menjadi 20–30 *concurrent requests* per node. 
* Peningkatan ini secara langsung menurunkan *Cost per 1K Tokens* hingga lebih dari 65% dan memangkas degradasi *tail latency* ($P_{99}$).

---

## 4. Arsitektur & Diagram Komponen

Diagram berikut merepresentasikan alur kerja subsistem *Serving Engine* modern, yang memisahkan bidang penjadwalan (*control plane*) dan bidang komputasi tensor (*data plane*).

```
+-----------------------------------------------------------------------------------------+
|                                    INFERENCE ENGINE                                     |
+-----------------------------------------------------------------------------------------+
                                             |
                                  [Incoming HTTP / gRPC]
                                             v
                      +---------------------------------------------+
                      |               Request Manager               |
                      |   - Tokenizer / Sequence Parsing            |
                      |   - Request State Assignment (WAITING)      |
                      +---------------------------------------------+
                                             |
                                             v
+-----------------------------------------------------------------------------------------+
|                                      SCHEDULER                                          |
|                                                                                         |
|  +--------------------+     Dynamic Batching    +------------------------------------+  |
|  |   Waiting Queue    | --------------------->  |           Running Queue            |  |
|  +--------------------+   (Prefill Scheduling)  +------------------------------------+  |
|            ^                                                      |                     |
|            | Preempt (Recompute)                                  | Step Completed      |
|            |                                                      v                     |
|  +--------------------+                         +------------------------------------+  |
|  |   Swapped Queue    | <---------------------- |     Free Slots / Termination       |  |
|  +--------------------+    Preempt (Swap Host)  +------------------------------------+  |
+-----------------------------------------------------------------------------------------+
       |                                                                |
       | Query / Free Blocks                                            | Submit Batch
       v                                                                v
+------------------------------------+       Step       +---------------------------------+
|        BLOCK ALLOCATOR             |   Tensor Alloc   |       MODEL WORKER EXECUTION    |
|                                    | ---------------> |                                 |
| +--------------------------------+ |                  | +-----------------------------+ |
| | GPU Free Block Pool            | |                  | | Tensor Parallel Execution   | |
| | [Block 0, 1, ..., N-1]         | |                  | | (Attention + PagedAttention)| |
| +--------------------------------+ |                  | +-----------------------------+ |
| +--------------------------------+ |                  |                |                |
| | CPU Free Block Pool (Swap)     | |                  |                v                |
| | [HostBlock 0, ..., M-1]        | |                  | +-----------------------------+ |
| +--------------------------------+ |                  | | Physical Memory (HBM)       | |
| +--------------------------------+ |                  | | Key Cache   [Pool of Pages] | |
| | Block Tables (Per Sequence ID) | |                  | | Value Cache [Pool of Pages] | |
| +--------------------------------+ |                  | +-----------------------------+ |
+------------------------------------+                  +---------------------------------+
```

---

## 5. Deep Dive Mekanisme & Prinsip Kerja

### 5.1 Perhitungan Dimensi Memori KV Cache

Untuk memahami urgensi manajemen blok, perhatikan formulasi kebutuhan memori KV Cache untuk satu token pada satu *sequence*:

$$\text{KV Size per Token (Bytes)} = 2 \times (\text{layers}) \times (\text{kv\_heads}) \times (\text{head\_dim}) \times (\text{bytes\_per\_element})$$

*Faktor 2 mengindikasikan komponen Key dan Value.*

Sebagai contoh, pada model LLaMA-3-8B:
* Layers = $32$
* KV Heads = $8$ (Grouped-Query Attention)
* Head Dimension = $128$
* Data Type = FP16 ($2 \text{ bytes}$)

$$\text{KV Size per Token} = 2 \times 32 \times 8 \times 128 \times 2 = 131.072 \text{ bytes} \approx 128 \text{ KB / token}$$

Untuk *sequence* sepanjang $4.096$ token:
$$\text{Total KV per Sequence} = 128 \text{ KB} \times 4096 \approx 512 \text{ MB}$$

Jika mesin menangani $128$ *concurrent sequences*, kapasitas HBM yang dibutuhkan murni untuk KV Cache adalah:
$$128 \times 512 \text{ MB} = 64 \text{ GB}$$

Jika dialokasikan secara kontigu di awal tanpa paging, memori 64 GB langsung terkunci, terlepas dari apakah setiap *sequence* baru memproduksi 5 token atau 4000 token.

### 5.2 PagedAttention: Logical to Physical Mapping

PagedAttention mengabstraksi KV Cache sequence menjadi daftar blok logis:

* **Block Size ($B$)**: Jumlah token yang disimpan dalam satu unit halaman memori (biasanya bernilai 16 atau 32).
* **Logical Block Number**: $\text{LBN} = \lfloor \text{token\_index} / B \rfloor$.
* **Block Offset**: $\text{offset} = \text{token\_index} \pmod B$.

Saat token baru diproduksi:
1. Engine menghitung apakah blok logis saat ini memiliki slot kosong ($\text{offset} \neq 0$).
2. Jika slot penuh, engine meminta *Physical Block* baru dari `GPU Free Block Pool` via `BlockAllocator`.
3. Pasangan `(Sequence ID, LBN) -> Physical Frame ID` dicatat ke dalam **Block Table**.
4. Kernel CUDA PagedAttention melakukan lookup ke Block Table secara *on-the-fly* pada setiap langkah komputasi *Multi-Head Attention* untuk mengambil tensor Key/Value non-kontigu secara presisi.

```
Token Index: 33, Block Size: 16
Logical Block = floor(33 / 16) = 2
Block Offset  = 33 % 16        = 1
Physical Block Table: [LBN 0 -> Frame 102], [LBN 1 -> Frame 55], [LBN 2 -> Frame 8]
Target Write Physical Address: Frame 8, Slot Index 1
```

### 5.3 Continuous Scheduling Dynamics: Prefill vs. Decode

Proses inferensi LLM memiliki dua fase dengan profil komputasi yang sangat berbeda:
* **Prefill**: *Compute-bound*, memproses seluruh input prompt sekaligus (parallel GEMM), menghasilkan latensi tinggi per step tetapi throughput FLOPs optimal.
* **Decode**: *Memory-bandwidth-bound*, memproses 1 token per sequence per step (GEMV), latensi rendah per token tetapi pemanfaatan core compute rendah.

Scheduler bertugas menggabungkan kedua mode ini:
1. **Dynamic Prioritization**: Prefill diprioritaskan untuk meminimalkan TTFT, sedangkan Decode dijadwalkan secara teratur agar tidak melanggar batasan SLA ITL.
2. **Chunked Prefill**: Prefill yang panjang dipotong menjadi *chunk* berukuran tetap (misal: 512 token) dan di-batch bersama token decode reguler untuk mencegah lonjakan tajam pada ITL (*inter-token jitter*).

### 5.4 Preemption Strategies

Ketika memori GPU mencapai kapasitas kritis ($100\%$ pool fisik terpakai) dan terdapat *sequence running* yang memerlukan blok baru untuk token berikutnya, *scheduler* harus mengorbankan setidaknya satu sequence:

* **Swapping (Offloading)**: Blok fisik dari sequence yang dikorbankan di-copy secara asinkron (via CUDA stream non-default) ke CPU Host RAM. Status request berubah menjadi `SWAPPED`. Kelemahannya: Terbatas pada bandwidth bus PCIe (misal: PCIe Gen 5 $\approx 64 \text{ GB/s}$).
* **Recomputation**: Memori blok GPU dari sequence yang dikorbankan langsung di-`free` kembali ke pool. Prompt dan token yang telah ter-generate tetap dicatat di control plane. Ketika kapasitas memori pulih, request dijadwalkan ulang dalam antrean `WAITING` untuk mengulang fase prefill secara instan. Teknik ini sering kali lebih cepat dibanding *swapping* jika bus PCIe tersaturasi dan konteks masih berada dalam ambang batas efisiensi komputasi *prefill*.

---

## 6. Production-Ready Code Implementation

Berikut adalah implementasi *Paged KV Cache Engine Simulator* tingkat produksi yang mereplikasi arsitektur inti dari *vLLM / TensorRT-LLM*, mencakup modul `BlockAllocator`, `BlockTable`, `ContinuousScheduler`, dan pipeline eksekusinya.

```python
"""
Production-grade Implementation of Paged KV-Cache Management & Continuous Batch Scheduler.
No third-party serving dependencies; pure standard library and type safety.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
import math
from typing import Dict, List, Optional, Set, Tuple


class RequestStatus(str, Enum):
    WAITING = "WAITING"
    RUNNING = "RUNNING"
    SWAPPED = "SWAPPED"
    FINISHED = "FINISHED"


@dataclass
class LogicalTokenBlock:
    block_number: int
    num_tokens: int = 0
    max_tokens: int = 16

    @property
    def is_full(self) -> bool:
        return self.num_tokens >= self.max_tokens

    def append_token(self) -> None:
        if self.is_full:
            raise OverflowError("Attempted to append token to a full logical block.")
        self.num_tokens += 1


@dataclass
class PhysicalBlock:
    block_id: int
    device: str  # "gpu" or "cpu"
    ref_count: int = 0

    def reset(self) -> None:
        self.ref_count = 0


@dataclass
class Sequence:
    request_id: str
    prompt_tokens: List[int]
    max_tokens_to_generate: int
    output_tokens: List[int] = field(default_factory=list)
    status: RequestStatus = RequestStatus.WAITING
    logical_blocks: List[LogicalTokenBlock] = field(default_factory=list)

    @property
    def total_tokens(self) -> int:
        return len(self.prompt_tokens) + len(self.output_tokens)

    def is_finished(self) -> bool:
        return (
            self.status == RequestStatus.FINISHED
            or len(self.output_tokens) >= self.max_tokens_to_generate
        )


class BlockAllocator:
    """Mengelola alokasi dan dealokasi Physical Blocks pada GPU dan CPU memory pools."""

    def __init__(self, block_size: int, num_gpu_blocks: int, num_cpu_blocks: int) -> None:
        self.block_size = block_size
        self.num_gpu_blocks = num_gpu_blocks
        self.num_cpu_blocks = num_cpu_blocks

        self.gpu_free_blocks: List[PhysicalBlock] = [
            PhysicalBlock(block_id=i, device="gpu") for i in range(num_gpu_blocks)
        ]
        self.cpu_free_blocks: List[PhysicalBlock] = [
            PhysicalBlock(block_id=i, device="cpu") for i in range(num_cpu_blocks)
        ]

        # Tracking physical block instances
        self.all_gpu_blocks: Dict[int, PhysicalBlock] = {b.block_id: b for b in self.gpu_free_blocks}
        self.all_cpu_blocks: Dict[int, PhysicalBlock] = {b.block_id: b for b in self.cpu_free_blocks}

    def allocate_gpu_block(self) -> PhysicalBlock:
        if not self.gpu_free_blocks:
            raise MemoryError("OOM: Pool physical block GPU habis.")
        block = self.gpu_free_blocks.pop(0)
        block.ref_count = 1
        return block

    def allocate_cpu_block(self) -> PhysicalBlock:
        if not self.cpu_free_blocks:
            raise MemoryError("OOM: Pool physical block CPU (Swap) habis.")
        block = self.cpu_free_blocks.pop(0)
        block.ref_count = 1
        return block

    def free_gpu_block(self, block_id: int) -> None:
        block = self.all_gpu_blocks[block_id]
        if block.ref_count > 1:
            block.ref_count -= 1
        elif block.ref_count == 1:
            block.reset()
            self.gpu_free_blocks.append(block)
        else:
            raise ValueError(f"Double free detected on GPU block: {block_id}")

    def free_cpu_block(self, block_id: int) -> None:
        block = self.all_cpu_blocks[block_id]
        if block.ref_count > 1:
            block.ref_count -= 1
        elif block.ref_count == 1:
            block.reset()
            self.cpu_free_blocks.append(block)
        else:
            raise ValueError(f"Double free detected on CPU block: {block_id}")

    def get_num_free_gpu_blocks(self) -> int:
        return len(self.gpu_free_blocks)

    def get_num_free_cpu_blocks(self) -> int:
        return len(self.cpu_free_blocks)


class BlockManager:
    """Menangani pemetaan Logical Blocks sequence ke Physical Blocks (Block Table)."""

    def __init__(self, block_size: int, allocator: BlockAllocator) -> None:
        self.block_size = block_size
        self.allocator = allocator
        # Mapping: request_id -> List[PhysicalBlock]
        self.gpu_block_tables: Dict[str, List[PhysicalBlock]] = {}
        self.cpu_block_tables: Dict[str, List[PhysicalBlock]] = {}

    def can_allocate(self, seq: Sequence) -> bool:
        num_required_blocks = math.ceil(seq.total_tokens / self.block_size)
        return self.allocator.get_num_free_gpu_blocks() >= num_required_blocks

    def allocate_for_prefill(self, seq: Sequence) -> None:
        num_required_blocks = math.ceil(seq.total_tokens / self.block_size)
        allocated_blocks: List[PhysicalBlock] = []

        try:
            for _ in range(num_required_blocks):
                allocated_blocks.append(self.allocator.allocate_gpu_block())
        except MemoryError:
            for b in allocated_blocks:
                self.allocator.free_gpu_block(b.block_id)
            raise

        self.gpu_block_tables[seq.request_id] = allocated_blocks

        # Build initial logical structure
        seq.logical_blocks = []
        tokens_remaining = seq.total_tokens
        for i in range(num_required_blocks):
            tokens_in_this_block = min(self.block_size, tokens_remaining)
            logical_block = LogicalTokenBlock(
                block_number=i,
                num_tokens=tokens_in_this_block,
                max_tokens=self.block_size
            )
            seq.logical_blocks.append(logical_block)
            tokens_remaining -= tokens_in_this_block

    def append_slot(self, seq: Sequence) -> Optional[PhysicalBlock]:
        """Menambahkan slot alokasi untuk 1 token decode berikutnya.
        Return: PhysicalBlock baru jika alokasi block baru diperlukan, selain itu None.
        """
        last_logical = seq.logical_blocks[-1]
        if not last_logical.is_full:
            last_logical.append_token()
            return None

        # Logical block penuh, alokasikan block fisik & buat logical block baru
        if self.allocator.get_num_free_gpu_blocks() < 1:
            raise MemoryError("Tidak ada physical block GPU bebas untuk alokasi decode slot.")

        new_physical_block = self.allocator.allocate_gpu_block()
        self.gpu_block_tables[seq.request_id].append(new_physical_block)

        new_logical = LogicalTokenBlock(
            block_number=len(seq.logical_blocks),
            num_tokens=1,
            max_tokens=self.block_size
        )
        seq.logical_blocks.append(new_logical)
        return new_physical_block

    def free_sequence(self, seq: Sequence) -> None:
        if seq.request_id in self.gpu_block_tables:
            for block in self.gpu_block_tables[seq.request_id]:
                self.allocator.free_gpu_block(block.block_id)
            del self.gpu_block_tables[seq.request_id]

        if seq.request_id in self.cpu_block_tables:
            for block in self.cpu_block_tables[seq.request_id]:
                self.allocator.free_cpu_block(block.block_id)
            del self.cpu_block_tables[seq.request_id]

    def swap_out(self, seq: Sequence) -> None:
        """Offload physical blocks dari GPU ke CPU memory pool."""
        gpu_blocks = self.gpu_block_tables.get(seq.request_id, [])
        if not gpu_blocks:
            return

        if self.allocator.get_num_free_cpu_blocks() < len(gpu_blocks):
            raise MemoryError("CPU Swap memory exhausted; cannot swap out sequence.")

        cpu_blocks: List[PhysicalBlock] = []
        for _ in range(len(gpu_blocks)):
            cpu_blocks.append(self.allocator.allocate_cpu_block())

        # Di level kernel nyata: cudaMemcpyAsync(D2H) dilakukan di sini
        for b in gpu_blocks:
            self.allocator.free_gpu_block(b.block_id)

        del self.gpu_block_tables[seq.request_id]
        self.cpu_block_tables[seq.request_id] = cpu_blocks
        seq.status = RequestStatus.SWAPPED

    def swap_in(self, seq: Sequence) -> None:
        """Restore physical blocks dari CPU ke GPU memory pool."""
        cpu_blocks = self.cpu_block_tables.get(seq.request_id, [])
        if not cpu_blocks:
            return

        if self.allocator.get_num_free_gpu_blocks() < len(cpu_blocks):
            raise MemoryError("GPU memory exhausted; cannot swap in sequence.")

        gpu_blocks: List[PhysicalBlock] = []
        for _ in range(len(cpu_blocks)):
            gpu_blocks.append(self.allocator.allocate_gpu_block())

        # Di level kernel nyata: cudaMemcpyAsync(H2D) dilakukan di sini
        for b in cpu_blocks:
            self.allocator.free_cpu_block(b.block_id)

        del self.cpu_block_tables[seq.request_id]
        self.gpu_block_tables[seq.request_id] = gpu_blocks
        seq.status = RequestStatus.RUNNING


@dataclass
class SchedulerOutputs:
    scheduled_seqs: List[Sequence]
    ignored_seqs: List[Sequence]
    num_batched_tokens: int
    preempted_seqs: List[Sequence]


class ContinuousScheduler:
    """Scheduler Iteration-Level berbasis prioritas dan mitigasi memory bottleneck."""

    def __init__(
        self,
        block_manager: BlockManager,
        max_batch_size: int,
        max_model_len: int,
    ) -> None:
        self.block_manager = block_manager
        self.max_batch_size = max_batch_size
        self.max_model_len = max_model_len

        self.waiting: List[Sequence] = []
        self.running: List[Sequence] = []
        self.swapped: List[Sequence] = []

    def add_request(self, seq: Sequence) -> None:
        self.waiting.append(seq)

    def schedule(self) -> SchedulerOutputs:
        scheduled: List[Sequence] = []
        preempted: List[Sequence] = []
        ignored: List[Sequence] = []

        # 1. Evaluasi Running Queue (Prioritas fase Decode)
        remaining_running: List[Sequence] = []
        while self.running:
            seq = self.running.pop(0)

            # Coba alokasi slot untuk token berikutnya
            try:
                self.block_manager.append_slot(seq)
                remaining_running.append(seq)
            except MemoryError:
                # OOM Handler: Jalankan Preemption
                victim = self._preempt_victim(seq, remaining_running)
                preempted.append(victim)
                # Retry alokasi slot untuk token aktif setelah preemption
                try:
                    self.block_manager.append_slot(seq)
                    remaining_running.append(seq)
                except MemoryError:
                    # Jika tetap OOM, sequence saat ini juga harus di-preempt
                    self._execute_preemption(seq)
                    preempted.append(seq)

        self.running = remaining_running
        scheduled.extend(self.running)

        # 2. Evaluasi Swapped Queue (Kembalikan ke running jika kapasitas GPU tersedia)
        while self.swapped and len(scheduled) < self.max_batch_size:
            seq = self.swapped[0]
            num_blocks_needed = len(self.block_manager.cpu_block_tables.get(seq.request_id, []))
            if self.block_manager.allocator.get_num_free_gpu_blocks() >= num_blocks_needed:
                self.swapped.pop(0)
                self.block_manager.swap_in(seq)
                self.running.append(seq)
                scheduled.append(seq)
            else:
                break

        # 3. Evaluasi Waiting Queue (Prefill Scheduling)
        while self.waiting and len(scheduled) < self.max_batch_size:
            seq = self.waiting[0]

            if seq.total_tokens > self.max_model_len:
                # Drop sequence yang melampaui context limit
                self.waiting.pop(0)
                seq.status = RequestStatus.FINISHED
                ignored.append(seq)
                continue

            if self.block_manager.can_allocate(seq):
                self.waiting.pop(0)
                self.block_manager.allocate_for_prefill(seq)
                seq.status = RequestStatus.RUNNING
                self.running.append(seq)
                scheduled.append(seq)
            else:
                # GPU memory pressure: tunda prefill batch ini
                break

        num_tokens = sum(1 if s.output_tokens else len(s.prompt_tokens) for s in scheduled)
        return SchedulerOutputs(
            scheduled_seqs=scheduled,
            ignored_seqs=ignored,
            num_batched_tokens=num_tokens,
            preempted_seqs=preempted
        )

    def _preempt_victim(self, current_seq: Sequence, running_candidates: List[Sequence]) -> Sequence:
        """Pilih victim untuk preemption berdasarkan prioritas FCFS terbalik (LIFO)."""
        if running_candidates:
            victim = running_candidates.pop(-1)
        else:
            victim = current_seq

        self._execute_preemption(victim)
        return victim

    def _execute_preemption(self, seq: Sequence) -> None:
        """Preemption strategy: Coba Swap-out ke RAM, jika gagal fallback ke Recompute."""
        try:
            self.block_manager.swap_out(seq)
            self.swapped.append(seq)
        except MemoryError:
            # Fallback Recompute: Bebaskan semua blok, kembalikan ke antrean terdepan WAITING
            self.block_manager.free_sequence(seq)
            seq.output_tokens.clear()
            seq.logical_blocks.clear()
            seq.status = RequestStatus.WAITING
            self.waiting.insert(0, seq)


# =====================================================================
# Verification Execution
# =====================================================================
if __name__ == "__main__":
    import random

    # Inisialisasi: Block Size = 4 tokens, GPU Memory = 8 Blocks (Kapasitas total 32 tokens)
    # CPU Memory = 8 Blocks (Swap pool kapasitas 32 tokens)
    allocator = BlockAllocator(block_size=4, num_gpu_blocks=8, num_cpu_blocks=8)
    block_mgr = BlockManager(block_size=4, allocator=allocator)
    scheduler = ContinuousScheduler(block_manager=block_mgr, max_batch_size=4, max_model_len=64)

    # Tambahkan requests simulasi
    req1 = Sequence(request_id="req-1", prompt_tokens=[1, 2, 3, 4, 5, 6, 7], max_tokens_to_generate=5)
    req2 = Sequence(request_id="req-2", prompt_tokens=[10, 11, 12], max_tokens_to_generate=4)
    req3 = Sequence(request_id="req-3", prompt_tokens=[20, 21, 22, 23, 24], max_tokens_to_generate=6)

    scheduler.add_request(req1)
    scheduler.add_request(req2)
    scheduler.add_request(req3)

    print("=== STARTING CONTINUOUS SCHEDULING ITERATIONS ===")
    step = 0
    while scheduler.running or scheduler.waiting or scheduler.swapped:
        step += 1
        output = scheduler.schedule()

        print(f"\n--- Iteration Step {step} ---")
        print(f"Scheduled Active Seqs: {[s.request_id for s in output.scheduled_seqs]}")
        print(f"Preempted Seqs       : {[s.request_id for s in output.preempted_seqs]}")
        print(f"Free GPU Blocks      : {allocator.get_num_free_gpu_blocks()} / {allocator.num_gpu_blocks}")
        print(f"Free CPU Blocks      : {allocator.get_num_free_cpu_blocks()} / {allocator.num_cpu_blocks}")

        # Simulasi komputasi forward-pass LLM: Generate 1 token untuk setiap active sequence
        for seq in output.scheduled_seqs:
            simulated_token = random.randint(100, 999)
            seq.output_tokens.append(simulated_token)

            # Cek terminasi
            if seq.is_finished():
                seq.status = RequestStatus.FINISHED
                scheduler.running.remove(seq)
                block_mgr.free_sequence(seq)
                print(f"-> Sequence {seq.request_id} FINISHED. Generated {len(seq.output_tokens)} tokens.")

        if step > 20:  # Safety circuit breaker
            print("Force terminated due to step limit.")
            break
```

---

## 7. Edge Cases & Failure Modes

### 7.1 Cascading Preemption (Thrashing Loop)
* **Gejala**: Engine menghabiskan siklus komputasi hanya untuk melakukan *swapping* bolak-balik antara Host RAM dan GPU HBM tanpa menghasilkan kemajuan decoding yang berarti.
* **Root Cause**: Over-committing batch size pada scheduler saat alokasi *prefill* diizinkan masuk padahal kapasitas tersisa tidak cukup untuk menampung batas *worst-case* token *decode* aktif.
* **Mitigasi**: Implementasi *Watermark Reservation*. Engine mempertahankan *headroom* minimal (misal: $5\%$ dari total *physical blocks*) khusus untuk slot *decode*. Prefill ditolak/ditunda jika free blocks $<$ *watermark threshold*.

### 7.2 Prefix Collision & Stale Cache Pointers
* **Gejala**: Token yang didekode menghasilkan output acak, halusinasi semantik berat, atau *segfault* CUDA kernel.
* **Root Cause**: Pada sistem yang mendukung RadixAttention atau Prefix Caching tingkat lanjut, blok fisik di-*share* lintas beberapa *sequence*. Modifikasi in-place pada blok memori bersama (tanpa Copy-on-Write) merusak data *sequence* lain.
* **Mitigasi**: Pastikan mekanisme *Reference Counting* bersifat *atomic*. Terapkan strategi **Copy-on-Write (CoW)**: Jika sequence perlu menulis ke blok bersama yang memiliki `ref_count > 1`, lakukan replikasi blok fisik baru sebelum penulisan.

### 7.3 Deadlock pada Token Boundary Multi-GPU
* **Gejala**: Pipeline parallel atau Tensor parallel workers mengalami *hang* indefinitely pada batas sinkronisasi all-reduce Attention.
* **Root Cause**: Desinkronisasi state Block Allocator antar-worker worker rank. Rank 0 memutuskan untuk mem-preempt Sequence A, sementara Rank 1 mengeksekusi decode untuk Sequence A.
* **Mitigasi**: Pindahkan logika Scheduler dan Block Manager secara terpusat pada Rank 0 (Control Plane). Rank 0 menyiarkan (*broadcast*) metadata instruksi batch dan tabel blok ke seluruh rank *worker* melalui socket IPC/NCCL berkecepatan tinggi sebelum komputasi kernel dimulai.

---

## 8. Trade-offs & Alternatif Solusi

| Parameter / Arsitektur | Opsi A | Opsi B | Trade-off Analysis |
| :--- | :--- | :--- | :--- |
| **Block Size ($B$)** | **Small ($B=8$ atau $16$)** | **Large ($B=32$ atau $64$)** | Block kecil meminimalkan *internal fragmentation* (rata-rata pemborosan blok terakhir hanya $\frac{B}{2}$ token). Namun, block kecil memperbesar overhead *Block Table lookup* pada kernel CUDA dan menurunkan efisiensi *memory coalescing*. Block 16 atau 32 adalah *sweet spot* industri. |
| **Preemption Strategy** | **Swapping (Host RAM)** | **Recomputation** | Swapping ideal jika bandwidth PCIe longgar dan sequence context sudah panjang ($> 2048$ tokens). Recompute lebih unggul jika panjang context pendek ($< 512$ tokens), karena throughput compute H100 pada phase prefill jauh lebih cepat dibanding latency transfer data via PCIe. |
| **Prefill Policy** | **Chunked Prefill** | **Disaggregated Serving** | Chunked prefill menggabungkan compute prefill dan decode dalam satu GPU engine untuk menekan jitter. Disaggregated serving memisahkan GPU khusus Prefill Worker dan GPU khusus Decode Worker secara fisik via jaringan RDMA; memberikan throughput tertinggi namun meningkatkan kompleksitas kluster. |

---

## 9. Best Practices & Standar Industri

1. **Alignment Memory Boundary**: Alokasikan physical tensor memory dalam kelipatan byte yang sesuai dengan batas arsitektur GPU (misal: 128 bytes untuk L1/L2 cacheline caching pada NVIDIA Ampere/Hopper).
2. **Kuantisasi KV Cache**: Terapkan kuantisasi FP8 (E4M3 atau E5M2) atau INT8 pada Physical Block Cache. Ini melipatgandakan *capacity limit* blok fisik hingga 2x lipat tanpa penurunan perplexity model yang signifikan.
3. **Penyelarasan Chunking & Padding**: Hindari padding dinamis zero-token berbasis software. Paged scheduling memproses pointer secara selektif, menghilangkan seluruh kebutuhan *pad-tokens* yang redundan pada tensor input.
4. **Metrik Observabilitas Kritis**:
   * `kv_cache_usage_ratio`: Rasio blok GPU terpakai terhadap kapasitas total. Jika konstan di $> 90\%$, kluster membutuhkan horizontal scaling.
   * `preemption_rate`: Jumlah sequence preempted per detik. Lonjakan angka ini menandakan batas latensi SLA terlanggar.
   * `paged_internal_fragmentation_ratio`: Mengukur token tidak terpakai pada blok aktif terakhir.

---

## 10. Hands-on Lab Exercise

### Deskripsi Skenario
Anda diminta membuktikan keunggulan *Paged Memory Allocation* dibanding *Contiguous Static Allocation* melalui eksperimen simulasi benchmarking empiris.

### Langkah Kerja

1. **Setup Simulasi Baseline (Contiguous)**: Buat class `ContiguousMemorySimulator` yang mengalokasikan slot berukuran `max_sequence_len = 2048` secara flat kontigu di memori.
2. **Setup Paged Simulator**: Gunakan engine yang telah dibangun di Bab 6 dengan `block_size = 16`.
3. **Eksekusi Workload Tracing**:
   * Buat workload sintetis: 50 requests.
   * Distribusi panjang prompt: Gaussian ($\mu = 256, \sigma = 64$).
   * Distribusi panjang decode: Gaussian ($\mu = 128, \sigma = 32$).
4. **Jalankan Skrip Evaluasi**:

```python
"""
Hands-on Lab: Benchmarking Memory Footprint - Contiguous vs. PagedAllocation
"""

import numpy as np


def run_benchmark():
    np.random.seed(42)
    num_requests = 50
    block_size = 16
    max_context_len = 2048

    # Parameter LLaMA-3-8B FP16 per token = 128 KB
    bytes_per_token = 128 * 1024

    # Generate workload
    prompt_lens = np.random.normal(256, 64, num_requests).astype(int)
    decode_lens = np.random.normal(128, 32, num_requests).astype(int)

    # 1. Baseline: Contiguous Allocation (Static Reserved based on max_context_len)
    contiguous_memory_bytes = num_requests * max_context_len * bytes_per_token

    # 2. Paged Allocation (Dynamic Growth)
    total_paged_blocks = 0
    actual_tokens_generated = 0

    for p_len, d_len in zip(prompt_lens, decode_lens):
        total_tokens = p_len + d_len
        actual_tokens_generated += total_tokens
        # Paged blocks needed
        blocks_needed = math.ceil(total_tokens / block_size)
        total_paged_blocks += blocks_needed

    paged_memory_bytes = total_paged_blocks * block_size * bytes_per_token
    actual_required_bytes = actual_tokens_generated * bytes_per_token

    print("================ MEMORY BENCHMARK REPORT ================")
    print(f"Total Requests Processed     : {num_requests}")
    print(f"Total Actual Tokens Processed: {actual_tokens_generated}")
    print(f"Contiguous Static Allocation : {contiguous_memory_bytes / (1024**3):.2f} GB")
    print(f"Paged Dynamic Allocation     : {paged_memory_bytes / (1024**3):.2f} GB")
    print(f"Theoretical Absolute Minimum : {actual_required_bytes / (1024**3):.2f} GB")
    print("---------------------------------------------------------")
    waste_contiguous = (contiguous_memory_bytes - actual_required_bytes) / contiguous_memory_bytes * 100
    waste_paged = (paged_memory_bytes - actual_required_bytes) / paged_memory_bytes * 100
    memory_savings = (contiguous_memory_bytes - paged_memory_bytes) / contiguous_memory_bytes * 100

    print(f"Contiguous Memory Waste     : {waste_contiguous:.2f}%")
    print(f"Paged Internal Fragmentation: {waste_paged:.2f}%")
    print(f"Total Memory Savings (HBM)  : {memory_savings:.2f}%")
    print("=========================================================")


if __name__ == "__main__":
    run_benchmark()
```

### Pertanyaan Analisis Hasil Lab
1. Berapa persentase penghematan HBM yang Anda peroleh melalui *Paged Allocation*?
2. Jika rasio *Internal Fragmentation* meningkat drastis pada Paged Allocation, parameter apa yang harus Anda sesuaikan pada konfigurasi engine serving Anda? Berikan rasionalisasinya.