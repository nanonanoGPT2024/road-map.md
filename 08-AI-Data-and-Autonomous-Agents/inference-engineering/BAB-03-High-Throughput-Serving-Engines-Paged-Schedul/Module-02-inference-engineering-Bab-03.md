# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 03: High-Throughput Serving Engines: Paged KV-Cache & Iteration-Level Scheduling**  
**Kategori: 08-AI-Data-and-Autonomous-Agents / inference-engineering**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Mengonstruksi dan Menjelaskan Arsitektur Virtual Memory PagedAttention**: Membedah translasi logical block ke physical block pada GPU HBM (*High Bandwidth Memory*), eliminasi fragmentasi internal/eksternal, serta mekanisme alokasi blok non-kontigu.
2. **Merancang Algoritma Iteration-Level (Continuous) Scheduling**: Mengembangkan state machine scheduler yang mengeliminasi masalah *head-of-line blocking* dan *static padding overhead* melalui dynamic prefill/decode batching.
3. **Mengimplementasikan Decoupled Chunked Prefill & Prefix Caching**: Mengintegrasikan algoritma Radix Tree / Hash-based prefix matching untuk reusability KV cache pada multi-turn conversation dan system prompt bersamaan dengan penjadwalan chunked prefill untuk menekan jitter *Time-to-First-Token* (TTFT).
4. **Membangun Inference Engine Mandiri Tingkat Produksi**: Mengimplementasikan custom cache engine, block manager, dan continuous batching scheduler berbasis PyTorch/C++ wrapper yang siap diintegrasikan dengan *distributed tensor-parallel runtimes* (Ray/NCCL).
5. **Mendiagnosis dan Mengoptimasi Trade-off Inferensi Enterprise**: Menyelesaikan masalah KV cache thrashing, starvation fase decode, ketidakseimbangan alokasi NUMA, dan degradasi latensi inter-token (*Inter-Token Latency* / ITL).

---

## 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib memahami:
* **Deep Learning Compute Basics**: Operasi *scaled dot-product attention* ($O(N^2)$ time/space complexity) dan transformasi matriks $Q, K, V$.
* **Sistem Memori GPU & CUDA Basics**: Memori hirarkis NVIDIA (Global Memory/HBM, Shared Memory/SRAM, Registers, L2 Cache), CUDA Streams, pinned host memory (`cudaHostAlloc`), serta unified virtual addressing (UVA).
* **Distributed Parallelism**: Dasar-dasar Tensor Parallelism (TP - Megatron-LM row/column parallel linear layers) dan Pipeline Parallelism (PP).
* **Concurrency di Python & C++**: Asynchronous programming (`asyncio`), threading, multithreading GIL considerations, dan dasar-dasar C++17/20 STL (pointers, memory arenas).

---

## 3. Concept & Internal Architecture

### 3.1 Masalah Fundamental Alokasi Memori KV Cache Konvensional
Pada LLM autoregresif, inferensi terbagi menjadi dua fase:
1. **Prefill Phase (Compute-bound)**: Memproses input token secara paralel, menghasilkan tensor $K$ dan $V$ untuk seluruh context window.
2. **Decode Phase (Memory-bandwidth bound)**: Menghasilkan satu token per langkah (*step-by-step*), di mana tensor $K$ dan $V$ baru ditambahkan ke cache historis.

Pada engine generasi pertama (misal: vanilla Hugging Face Transformers), memori KV cache dialokasikan secara statis berdasarkan `max_sequence_length` yang diantisipasi (misal: 4096 atau 8192 token). Untuk arsitektur Llama-3-70B ($L=80$, $H_{kv}=8$, $D_{head}=128$, data type FP16):
$$\text{Memory per token} = 2 \times L \times H_{kv} \times D_{head} \times \text{sizeof(FP16)} = 2 \times 80 \times 8 \times 128 \times 2 = 327{,}680 \text{ bytes} \approx 320 \text{ KB}$$

Jika sebuah request hanya menghasilkan 200 token tetapi sistem memesan buffer untuk 4096 token ($4096 \times 320 \text{ KB} = 1.31 \text{ GB}$), terjadi **Internal Fragmentation** hingga 95%. Sebaliknya, jika memori dialokasikan secara dinamis menggunakan `torch.cat`, terjadi alokasi ulang dan penyalinan data terus-menerus yang memicu **External Fragmentation** parah dan memicu `CUDA out of memory` (OOM) meskipun kapasitas total memori fisik HBM masih tersisa puluhan gigabyte.

### 3.2 Arsitektur PagedAttention
PagedAttention memecahkan fragmentasi memori dengan mengadopsi prinsip **Paging Virtual Memory** pada sistem operasi (OS).

```
+--------------------------------------------------------------------------------+
|                             LOGICAL KV CACHE SPACE                             |
|  Request 0:  [ Block 0 ] -> [ Block 1 ] -> [ Block 2 ] (Logical Tokens 0..47)   |
|  Request 1:  [ Block 0 ] -> [ Block 1 ]                 (Logical Tokens 0..31)   |
+--------------------------------------------------------------------------------+
                                       |
                                       v  (Block Table Mapping)
+--------------------------------------------------------------------------------+
|                         PHYSICAL HBM MEMORY BLOCKS                             |
|  Slot 0: Free        | Slot 1: Req0_Blk0 | Slot 2: Req1_Blk0 | Slot 3: Free    |
|  Slot 4: Req0_Blk2   | Slot 5: Req1_Blk1 | Slot 6: Req0_Blk1 | Slot 7: Free    |
+--------------------------------------------------------------------------------+
```

1. **Logical Blocks**: Token-token KV sequence dipecah menjadi blok-blok berukuran tetap (*block size* $B$, umumnya bernilai 16 atau 32 token).
2. **Physical Blocks**: Pool memori dialokasikan di muka (*pre-allocated tensor*) di HBM GPU. Setiap slot physical block memiliki kapasitas $B \times H_{kv} \times D_{head} \times \text{dtype\_size}$.
3. **Block Table**: Metadata mapping layer yang mencatat pemetaan dari *Logical Block Number* ke *Physical Block ID* untuk setiap request individual, beserta jumlah slot token yang terisi (*fill count*).

### 3.3 Dynamic Chunked Prefill & Iteration-Level Continuous Batching
Dalam *static batching*, batch baru hanya dapat diproses setelah seluruh sequence dalam batch sebelumnya selesai dieksekusi. Ini mengakibatkan utilisasi GPU menurun drastis karena token decode yang lambat mengunci resource.

**Continuous Batching (Iteration-level Scheduling)**:
Proses scheduling dilakukan pada setiap iterasi/langkah inferensi forward. Decode token yang sedang berjalan dapat dibatch bersamaan dengan request baru yang masuk. 

**Chunked Prefill**:
Prefill request berukuran besar (misal: 8192 token) membutuhkan waktu eksekusi GPU yang lama, menyebabkan fluktuasi latensi ekstrem (*spikes*) pada iterasi decode sequence lain (masalah *starvation*). Dynamic Chunked Prefill memecah prompt panjang menjadi potongan-potongan kecil (misal: $\text{chunk\_size} = 512$). Dengan ini, satu forward pass model menggabungkan:
* Sejumlah chunk prefill token (compute-bound)
* Sejumlah decode tokens dari multiple active requests (memory-bandwidth bound)

Hal ini menjaga utilisasi compute core (Tensor Core) tetap tinggi tanpa mengorbankan batasan Inter-Token Latency (ITL) pada request decode yang sedang berlangsung.

---

## 4. Why & What

| Dimensi | Static Batching Tradisional | Continuous Batching + Paged KV-Cache |
| :--- | :--- | :--- |
| **Alokasi Memori** | Statis, kontigu per request (worst-case allocation). | Paged, non-kontigu, on-demand per $B$ token. |
| **Fragmentasi Memori** | Internal: 60%–80%, External: Parah. | Internal: $< \frac{1}{\text{Block Size}}$ (rata-rata $< 3\%$), External: 0%. |
| **Unit Penjadwalan** | Request-level (request terkunci hingga selesai). | Iteration-level (step-by-step forward execution). |
| **Dukungan Prefix Cache** | Sulit/Tidak efisien (harus copy memory kontigu). | Seamless (hanya copy pointer/index pada block table). |
| **Throughput (Tokens/sec)**| Baseline ($1\times$). | **$3\times - 8\times$ peningkatan throughput.** |
| **Latensi P99 Decode** | Sangat terganggu oleh interupsi prefill baru. | Terkendali melalui Chunked Prefill & Budgeting. |

---

## 5. How (Workflow Detail)

Siklus hidup penjadwalan dan alokasi memori pada High-Throughput Serving Engine:

```
[Request Inflow] ---> [Waiting Queue (FIFO/Priority)]
                              |
                     [Scheduler Iteration]
                              |
    +-------------------------+-------------------------+
    |                                                   |
    v                                                   v
[Prefill / Chunk Scheduler]                 [Running Decode Scheduler]
  - Hitung sisa block fisik                   - Ambil 1 token per request
  - Chunk prompt sesuai budget token          - Cek apakah butuh alokasi block baru
  - Radix tree match (Prefix cache)           - Jika slot blok habis -> Swap out / Evict
    |                                                   |
    +-------------------------+-------------------------+
                              |
                              v
                [Construct Batch Execution Plan]
                  - Menggabungkan physical block IDs
                  - Membangun Input Tensor & Slot Mapping
                              |
                              v
                [Forward Pass Execution]
                  - Custom PagedAttention Kernel
                  - Tensor Parallel All-Reduce (NCCL)
                              |
                              v
                [Sampling & Token Generation]
                  - Argmax / Top-P / Top-K
                  - Update Block Table (Fill Count++)
                  - Cek Stop Condition (EOS / Max Tokens)
                              |
      +-----------------------+-----------------------+
      |                                               |
      v [Selesai]                                     v [Belum Selesai]
[Release Physical Blocks]                    [Kembalikan ke Running Pool]
```

### Langkah-demi-Langkah Komputasi PagedAttention Kernel:
1. **Thread Block Mapping**: Setiap thread block pada GPU memproses satu head attention untuk satu sequence (atau partisi decoding sequence pada PagedAttention v2).
2. **Logical to Physical Translation**: Kernel membaca `block_tables` untuk mengidentifikasi pointer physical block dari index sequence yang sedang diproses.
3. **KV Fetching**: Thread memuat vektor $K$ dan $V$ langsung dari physical memory blocks yang tersebar ke Shared Memory (SRAM) per blok.
4. **Online Softmax**: Menghitung dot product $Q \times K^T$, menormalkan nilai secara dinamis menggunakan online softmax reduction (*FlashAttention-style*), kemudian dikalikan dengan $V$.
5. **Output Writeback**: Hasil attention dituliskan kembali ke buffer tensor output.

---

## 6. Analogy & Diagram ASCII

### Analogi: RAM OS vs Memori GPU LLM
Bayangkan Anda menjalankan sistem operasi konvensional. Jika program memerlukan memori, OS tidak mencarikan blok memori kontigu sepanjang 16 GB, melainkan membaginya ke dalam *4 KB Pages*. 

* **Vanilla KV Cache**: Seperti memesan seluruh gerbong kereta untuk satu penumpang yang *mungkin* akan membawa teman di stasiun berikutnya. Kursi kosong tidak boleh diduduki siapa pun.
* **PagedAttention**: Seperti memesan kursi satuan di bioskop. Penumpang baru dialokasikan kursi kosong di mana pun posisinya berada. Sistem hanya menyimpan nomor kursi (pointer table).

### Diagram Interaksi Komponen Core Engine

```
+----------------------------------------------------------------------------+
| ENGINE CONTROLLER                                                          |
|                                                                            |
|  +--------------------+        +---------------------+                     |
|  | Request Scheduler  |------->| Physical Block Pool |                     |
|  +--------------------+        +---------------------+                     |
|            |                              ^                                |
|            v                              |                                |
|  +--------------------+        +---------------------+                     |
|  | Block Allocator    |------->| Free List: [3, 7, 8]|                     |
|  | (Logical->Physical)|        | Used List: [1, 2, 4]|                     |
|  +--------------------+        +---------------------+                     |
|            |                                                               |
|            v                                                               |
|  +--------------------+        +----------------------------------------+  |
|  | Execution Context  |------->| Forward Pass (PagedAttention Triton/C++)|  |
|  +--------------------+        +----------------------------------------+  |
+----------------------------------------------------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Simulasi Logical-to-Physical Block Manager
Implementasi dasar manajemen tabel blok menggunakan Python murni untuk memahami mekanisme pemetaan virtual memory.

```python
from typing import List, Dict, Optional

class SimpleBlockManager:
    def __init__(self, num_blocks: int, block_size: int):
        self.block_size = block_size
        self.free_blocks: List[int] = list(range(num_blocks))
        # Mapping request_id -> List of physical block IDs
        self.block_tables: Dict[str, List[int]] = {}

    def allocate(self, request_id: str, num_tokens: int) -> bool:
        needed_blocks = (num_tokens + self.block_size - 1) // self.block_size
        if len(self.free_blocks) < needed_blocks:
            return False # OOM pencegahan di level scheduler
        
        allocated = [self.free_blocks.pop(0) for _ in range(needed_blocks)]
        self.block_tables[request_id] = allocated
        return True

    def append_token(self, request_id: str, current_token_count: int) -> Optional[int]:
        """Menambahkan token baru, mengalokasikan blok baru jika batas blok terlampaui."""
        if current_token_count % self.block_size == 0:
            if not self.free_blocks:
                return None # Cache thrashing / Out of physical blocks
            new_block = self.free_blocks.pop(0)
            self.block_tables[request_id].append(new_block)
            return new_block
        return self.block_tables[request_id][-1]

    def free(self, request_id: str):
        if request_id in self.block_tables:
            self.free_blocks.extend(self.block_tables[request_id])
            del self.block_tables[request_id]

# Driver execution
mgr = SimpleBlockManager(num_blocks=4, block_size=4)
print(f"Initial Free Blocks: {mgr.free_blocks}")
assert mgr.allocate("req-01", num_tokens=6) == True # Butuh 2 blok (kapasitas 8 token)
print(f"Allocated 'req-01': {mgr.block_tables['req-01']}, Sisa Free: {mgr.free_blocks}")
mgr.free("req-01")
print(f"After Free: {mgr.free_blocks}")
```

---

### 7.2 Practical Example: Production-Grade KV Cache Engine & Triton Paged Kernel
Contoh industri: Engine PyTorch dengan Custom Kernel PagedAttention menggunakan Triton dan Dynamic Continuous Scheduler.

#### File: `paged_cache_engine.py`
```python
import torch
import triton
import triton.language as tl
from typing import List, Tuple, Dict

@triton.jit
def _paged_attention_decode_kernel(
    Out,                # Output tensor pointer
    Q,                  # Query tensor [Batch, Num_Heads, Head_Dim]
    K_Cache,            # Physical KV Cache [Total_Blocks, Num_Heads, Block_Size, Head_Dim]
    V_Cache,            # Physical KV Cache [Total_Blocks, Num_Heads, Block_Size, Head_Dim]
    Block_Tables,       # Lookup Table [Batch, Max_Blocks_Per_Seq]
    Context_Lens,       # Length tensor per sequence [Batch]
    sm_scale,           # Softmax scaling factor: 1 / sqrt(Head_Dim)
    stride_out_b, stride_out_h, stride_out_d,
    stride_q_b, stride_q_h, stride_q_d,
    stride_k_b, stride_k_h, stride_k_bs, stride_k_d,
    stride_v_b, stride_v_h, stride_v_bs, stride_v_d,
    stride_bt_b, stride_bt_m,
    BLOCK_SIZE: tl.constexpr,
    HEAD_DIM: tl.constexpr,
):
    seq_idx = tl.program_id(0)
    head_idx = tl.program_id(1)

    cur_len = tl.load(Context_Lens + seq_idx)
    if cur_len <= 0:
        return

    # Load Query Vector: [1, HEAD_DIM]
    q_offs = head_idx * stride_q_h + tl.arange(0, HEAD_DIM) * stride_q_d
    q_ptr = Q + seq_idx * stride_q_b + q_offs
    q = tl.load(q_ptr)

    # Initializing Online Softmax Statistics
    m_i = -float("inf")
    l_i = 0.0
    acc = tl.zeros([HEAD_DIM], dtype=tl.float32)

    num_blocks = (cur_len + BLOCK_SIZE - 1) // BLOCK_SIZE

    for block_num in range(num_blocks):
        phys_block_idx = tl.load(Block_Tables + seq_idx * stride_bt_b + block_num * stride_bt_m)

        # Offsets inside the physical block
        tokens_in_block = tl.minimum(BLOCK_SIZE, cur_len - block_num * BLOCK_SIZE)
        slot_offs = tl.arange(0, BLOCK_SIZE)
        mask = slot_offs < tokens_in_block

        # Load K block: shape [BLOCK_SIZE, HEAD_DIM]
        k_offs = (
            phys_block_idx * stride_k_b
            + head_idx * stride_k_h
            + slot_offs[:, None] * stride_k_bs
            + tl.arange(0, HEAD_DIM)[None, :] * stride_k_d
        )
        k = tl.load(K_Cache + k_offs, mask=mask[:, None], other=0.0)

        # Scaled dot-product: [BLOCK_SIZE]
        qk = tl.sum(q[None, :] * k, axis=1) * sm_scale
        qk = tl.where(mask, qk, -float("inf"))

        # Online Softmax update
        m_curr = tl.maximum(m_i, tl.max(qk, axis=0))
        alpha = tl.exp(m_i - m_curr)
        p = tl.exp(qk - m_curr)

        l_i = l_i * alpha + tl.sum(p, axis=0)

        # Load V block: shape [BLOCK_SIZE, HEAD_DIM]
        v_offs = (
            phys_block_idx * stride_v_b
            + head_idx * stride_v_h
            + slot_offs[:, None] * stride_v_bs
            + tl.arange(0, HEAD_DIM)[None, :] * stride_v_d
        )
        v = tl.load(V_Cache + v_offs, mask=mask[:, None], other=0.0)

        # Accumulate Output
        acc = acc * alpha + tl.sum(p[:, None] * v, axis=0)
        m_i = m_curr

    # Final normalization
    acc = acc / l_i

    # Write output to global memory
    out_offs = (
        seq_idx * stride_out_b
        + head_idx * stride_out_h
        + tl.arange(0, HEAD_DIM) * stride_out_d
    )
    tl.store(Out + out_offs, acc)


class ProductionPagedCacheEngine:
    def __init__(
        self,
        num_blocks: int,
        block_size: int,
        num_heads: int,
        head_dim: int,
        dtype: torch.dtype = torch.float16,
        device: str = "cuda",
    ):
        self.num_blocks = num_blocks
        self.block_size = block_size
        self.num_heads = num_heads
        self.head_dim = head_dim
        self.device = device
        self.dtype = dtype

        # Pre-allocate physical memory arenas (Zero memory copy during run)
        self.k_cache = torch.empty(
            (num_blocks, num_heads, block_size, head_dim), dtype=dtype, device=device
        )
        self.v_cache = torch.empty(
            (num_blocks, num_heads, block_size, head_dim), dtype=dtype, device=device
        )

        self.free_blocks = set(range(num_blocks))
        self.block_tables: Dict[int, List[int]] = {}

    def allocate(self, req_id: int, num_tokens: int) -> List[int]:
        needed = (num_tokens + self.block_size - 1) // self.block_size
        if len(self.free_blocks) < needed:
            raise MemoryError("GPU HBM Paged Out-Of-Memory: No blocks available.")
        allocated = [self.free_blocks.pop() for _ in range(needed)]
        self.block_tables[req_id] = allocated
        return allocated

    def append_slot(self, req_id: int, current_len: int) -> int:
        """Memastikan physical slot tersedia untuk token berikutnya."""
        if current_len % self.block_size == 0:
            if not self.free_blocks:
                raise MemoryError("Eviction/Swapping Required: GPU Pool exhausted.")
            new_block = self.free_blocks.pop()
            self.block_tables[req_id].append(new_block)
        return self.block_tables[req_id][-1]

    def free(self, req_id: int):
        if req_id in self.block_tables:
            for b in self.block_tables[req_id]:
                self.free_blocks.add(b)
            del self.block_tables[req_id]

    def execute_decode_paged_attention(
        self,
        query: torch.Tensor,       # [B, H, D]
        context_lens: torch.Tensor # [B]
    ) -> torch.Tensor:
        batch_size, num_heads, head_dim = query.shape
        out = torch.empty_like(query)

        max_blocks_per_seq = max(len(tbl) for tbl in self.block_tables.values())
        block_tables_tensor = torch.zeros(
            (batch_size, max_blocks_per_seq), dtype=torch.int32, device=self.device
        )

        for i, req_id in enumerate(self.block_tables.keys()):
            table = self.block_tables[req_id]
            block_tables_tensor[i, :len(table)] = torch.tensor(table, dtype=torch.int32)

        sm_scale = 1.0 / (head_dim ** 0.5)
        grid = (batch_size, num_heads)

        _paged_attention_decode_kernel[grid](
            out, query, self.k_cache, self.v_cache,
            block_tables_tensor, context_lens, sm_scale,
            out.stride(0), out.stride(1), out.stride(2),
            query.stride(0), query.stride(1), query.stride(2),
            self.k_cache.stride(0), self.k_cache.stride(1), self.k_cache.stride(2), self.k_cache.stride(3),
            self.v_cache.stride(0), self.v_cache.stride(1), self.v_cache.stride(2), self.v_cache.stride(3),
            block_tables_tensor.stride(0), block_tables_tensor.stride(1),
            BLOCK_SIZE=self.block_size,
            HEAD_DIM=self.head_dim,
        )
        return out
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Tier-1 Payment Processing Assistant (Conversational Core)
* **Beban Trafik**: Puncak 12.000 Concurrency Session, throughput target $\ge 250.000$ tokens/detik secara global.
* **SLA Ketat**:
  * P99 Time-to-First-Token (TTFT) $\le 80 \text{ ms}$
  * P99 Inter-Token Latency (ITL) $\le 20 \text{ ms}$
  * Zero-Drop Session Persistence (OOM drop rate = 0%).
* **Infrastruktur**: Klaster 16x Node HGX H100 (128x GPU H100 80GB SXM5), terhubung InfiniBand NDR 400 Gbps.

### Permasalahan Lapangan
Ketika migrasi dari arsitektur serving awal (Triton C++ dengan TensorRT-LLM static buffer):
1. **Memory Starvation**: Sesi obrolan rata-rata 3.500 token menempati full memory buffer (dialokasikan untuk 8.192 token). Utilisasi kapasitas fisik HBM mencapai 90%, tetapi konkurensi aktual terhenti di angka 1.800 request karena out-of-memory.
2. **TTFT Degradation**: Ketika ada user mengirim laporan audit (panjang prompt 16.000 token), prefill step mengunci GPU compute engine selama 420 ms. Hal ini menyebabkan ITL dari 1.700 pengguna aktif lainnya melonjak dari 15 ms menjadi 450 ms (pelanggaran SLA massal).

### Solusi Arsitektural Terapan
```
+-------------------------------------------------------------------------------+
| INCOMING REQUESTS                                                             |
+-------------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------------+
| RADIX TREE PREFIX CACHER (System prompt & history deduplication)             |
| Match Hash -> Reuse Physical Block IDs (Zero Compute, Zero Memory Duplication)|
+-------------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------------+
| CONTINUOUS SCHEDULER W/ DYNAMIC CHUNK BUDGETING                               |
| Max Token Budget per Step: 4096 tokens                                        |
| Split: 512 Chunked Prefill Tokens + 3584 Decode Tokens                       |
+-------------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------------+
| DISTRIBUTED PAGED CACHE MANAGER                                               |
| HBM Block Pool (Primary) <---> NVMe SSD Cache Arena (Host Spillover via UVA)  |
+-------------------------------------------------------------------------------+
```

1. **Adopsi PagedAttention (Block Size = 32)**: Menghilangkan alokasi *worst-case*. Kapasitas konkurensi naik seketika sebesar $4.2\times$ pada footprint hardware yang identik.
2. **Dynamic Chunked Prefill (Token Budget = 4096)**: Prompt panjang 16.000 token dipartisi menjadi sub-chunk 512 token per iteration batch. Komputasi decode token tidak lagi terganggu secara masif. P99 ITL stabil di angka 16.2 ms (SLA terpenuhi).
3. **Multi-tier Prefix Caching (Radix Tree)**: System instructions institusi perbankan (berukuran ~1.200 token yang statis) hanya dikomputasi satu kali. Block table untuk seluruh koneksi aktif langsung mereferensikan physical blocks yang sama via mekanisme *Copy-on-Write* (CoW). Beban prefill berkurang hingga 68%.

---

## 9. Trade-offs: Performance, Latency, Scalability, Cost

Perancangan serving engine menuntut kompromi arsitektural yang presisi:

```
                  THROUGHPUT (Tokens/s)
                         /\
                        /  \
                       /    \
  (Dynamic Chunking   /      \  (Aggressive Batching,
   & Prefix Cache)   /        \  High Max Tokens)
                    /          \
                   /____________\
      LATENCY (TTFT/ITL)       HARDWARE COST ($/Token)
```

| Parameter Arsitektural | Keuntungan Ekstrem | Kerugian Ekstrem | Mitigasi Ideal Level Enterprise |
| :--- | :--- | :--- | :--- |
| **Small Block Size ($B = 8, 16$)** | Minimal internal fragmentation ($< 1\%$). Ideal untuk variansi output pendek. | Overhead manajemen metadata membengkak; utilisasi memory bandwidth GPU menurun pada kernel decoding. | Gunakan $B=16$ untuk arsitektur MQA/GQA, $B=32$ untuk standar MHA. |
| **Large Block Size ($B = 64, 128$)** | Kernel efficiency tinggi, memory bandwidth mendekati batas teoritis HBM. | Fragmentasi internal membesar untuk request dengan output singkat; boros alokasi memory pool. | Hindari kecuali context window rata-rata selalu $>32\text{k}$ tokens. |
| **Chunked Prefill Aggressive ($\text{chunk} \le 256$)** | P99 ITL sangat mulus dan stabil; starvation token decode hampir nol. | TTFT memburuk secara signifikan bagi long context prompt karena throughput prefill $TFLOPs$ sub-optimal. | Implementasikan dynamic budgeting: scale chunk size berdasarkan queue length. |
| **Host/NVMe Swapping** | Request tidak terputus (*zero drop*) saat terjadi traffic spike tak terduga. | Bandwidth PCIe Gen5 ($64 \text{ GB/s}$) jauh lebih lambat dibanding HBM3 ($3.35 \text{ TB/s}$). Severe latency degradation saat swap-in. | Utamakan preemptive re-computation (*recompute cost < swap-in latency* pada InfiniBand network). |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Block Fragmentation & Cache Thrashing
* **Gejala**: Engine sering melakukan swapping blok memori secara konstan atau melempar runtime error `No free physical blocks left` padahal total token tergenerasi jauh di bawah kapasitas teoritis total HBM.
* **Akar Masalah**: Konfigurasi parameter `gpu_memory_utilization` disetel terlalu tinggi (misal: `0.98`), tidak menyisakan ruang buffer untuk aktivasi intermediate forward pass model (gelu, linear intermediate activations, Triton workspace buffers).
* **Solusi**: Batasi `gpu_memory_utilization` maksimal di rentang `0.85` hingga `0.92`. Sisa ruang memori didedikasikan secara eksplisit untuk scratchpad aktivasi CUDA runtime.

### 10.2 Prefill Starvation pada Iteration-Level Batching
* **Gejala**: Metrik ITL tiba-tiba naik ribuan persen ($> 500\text{ ms}$) secara berkala saat request baru masuk, menghancurkan interaktivitas conversational agent.
* **Akar Masalah**: Scheduler mengizinkan eksekusi unchunked prefill request panjang langsung masuk ke active batch tanpa limitasi `max_num_batched_tokens`.
* **Solusi**: Aktifkan fitur chunked prefill kaku:
  ```python
  # Parameter setting pada vLLM / custom runtime
  engine_args = EngineArgs(
      enable_chunked_prefill=True,
      max_num_batched_tokens=2048, # Bound the maximum computation per iteration
      max_num_seqs=256
  )
  ```

### 10.3 Triton Kernel Shared Memory Overflow
* **Gejala**: CUDA driver melontarkan `CUDA_ERROR_OUT_OF_RESOURCES` saat inisialisasi kernel custom PagedAttention decode.
* **Akar Masalah**: Konfigurasi `BLOCK_SIZE` dan `HEAD_DIM` mengalokasikan shared memory (SRAM) per Streaming Multiprocessor (SM) melampaui limit arsitektur GPU (misal: 228 KB per SM pada H100).
* **Solusi**: Terapkan split-K reduction (mirip konsep FlashDecoding) atau partisi load shared memory secara streaming per sub-blok, bukan memuat full block sequence ke SRAM secara simultan.

---

## 11. Best Practices (Production Checklist)

1. [ ] **NUMA Node GPU Pinning**: Pastikan thread CPU runner terikat (*pinned*) via `numactl --cpunodebind` secara eksklusif ke NUMA domain yang terhubung langsung ke PCIe switch GPU terkait.
2. [ ] **Warmup Allocator Pools**: Selalu lakukan forward run dengan synthetic batch dummy saat startup untuk memicu inisialisasi CUDA context, memory pool HBM, dan kompilasi JIT Triton.
3. [ ] **Prefix Caching Alignment**: Selalu urutkan token input pada sistem percakapan multiround (system prompt di awal, tools specification konsisten, dynamic user tokens di paling belakang) agar Radix matching konsisten menyentuh status cache HIT.
4. [ ] **Tuning Block Size Sesuai Format Attention**:
   * *Multi-Head Attention (MHA)*: Gunakan `block_size = 16`.
   * *Grouped-Query Attention (GQA / MQA)*: Gunakan `block_size = 32` atau `64` untuk mengompensasi dimensi $K/V$ yang tereduksi.
5. [ ] **Observabilitas Metrik Internal**:
   * Pantau rasio `kv_cache_usage_percentage`. Alerting dipicu jika $> 85\%$ selama $> 10$ detik.
   * Lacak `prefix_cache_hit_rate` (Target: $> 40\%$ pada environment conversational multi-turn).
   * Lacak `gpu_execution_time_per_step` untuk memastikan variansi iterasi tetap di bawah threshold batas ITL.

---

## 12. Hands-on Practice

Simpan seluruh file praktikum di direktori internal: `hands-on/m02/`

### Task Lab: Membangun Multi-Engine Simulation Benchmark
Bangun test script benchmarking mandiri untuk mengukur utilisasi memori, throughput, dan time-step variance antara **Static KV Cache Engine** vs **Paged KV Cache Engine**.

#### Langkah 1: Buat Struktur File
```bash
mkdir -p hands-on/m02/
cd hands-on/m02/
touch benchmark_engine.py
```

#### Langkah 2: Kode Implementasi Benchmark (`benchmark_engine.py`)
```python
import time
import torch
from typing import List

def run_static_allocation_simulation(num_requests: int, max_seq_len: int, actual_lens: List[int]):
    """Simulasi alokasi buffer statis tradisional."""
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    start_time = time.perf_counter()

    head_dim = 128
    num_heads = 8
    dtype = torch.float16

    # Alokasi worst-case upfront: [Batch, Max_Len, Num_Heads, Head_Dim]
    k_buffers = []
    v_buffers = []
    for _ in range(num_requests):
        k_buffers.append(torch.empty((max_seq_len, num_heads, head_dim), dtype=dtype, device="cuda"))
        v_buffers.append(torch.empty((max_seq_len, num_heads, head_dim), dtype=dtype, device="cuda"))

    # Simulasi eksekusi write token
    for req_idx, length in enumerate(actual_lens):
        k_buffers[req_idx][:length, :, :].zero_()
        v_buffers[req_idx][:length, :, :].zero_()

    torch.cuda.synchronize()
    peak_mem = torch.cuda.max_memory_allocated() / (1024 ** 2)
    elapsed = (time.perf_counter() - start_time) * 1000
    return peak_mem, elapsed

def run_paged_allocation_simulation(num_requests: int, block_size: int, actual_lens: List[int]):
    """Simulasi alokasi paged pool berbasis blok dinamis."""
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    start_time = time.perf_counter()

    head_dim = 128
    num_heads = 8
    dtype = torch.float16

    # Hitung kebutuhan blok fisik aktual
    total_tokens = sum(actual_lens)
    needed_blocks = sum((length + block_size - 1) // block_size for length in actual_lens)

    # Pre-allocated memory pool
    k_pool = torch.empty((needed_blocks, num_heads, block_size, head_dim), dtype=dtype, device="cuda")
    v_pool = torch.empty((needed_blocks, num_heads, block_size, head_dim), dtype=dtype, device="cuda")

    # Block table allocation simulation
    block_tables = {}
    free_blocks = list(range(needed_blocks))

    for req_idx, length in enumerate(actual_lens):
        b_count = (length + block_size - 1) // block_size
        allocated = [free_blocks.pop(0) for _ in range(b_count)]
        block_tables[req_idx] = allocated

    torch.cuda.synchronize()
    peak_mem = torch.cuda.max_memory_allocated() / (1024 ** 2)
    elapsed = (time.perf_counter() - start_time) * 1000
    return peak_mem, elapsed

if __name__ == "__main__":
    if not torch.cuda.is_available():
        print("Error: CUDA device tidak terdeteksi. Script butuh GPU aktif.")
        exit(1)

    print("=== KV CACHE MEMORY ALLOCATION BENCHMARK ===")
    num_reqs = 64
    max_len = 4096
    
    # Generate variasi actual length: Poisson-like distribution (banyak sequence pendek, sedikit yang panjang)
    torch.manual_seed(42)
    actual_seq_lens = torch.randint(low=128, high=1024, size=(num_reqs,)).tolist()

    static_mem, static_time = run_static_allocation_simulation(num_reqs, max_len, actual_seq_lens)
    paged_mem, paged_time = run_paged_allocation_simulation(num_reqs, block_size=16, actual_lens=actual_seq_lens)

    print(f"Total Requests: {num_reqs}")
    print(f"Max Context Capacity: {max_len} tokens")
    print(f"Actual Tokens Sum: {sum(actual_seq_lens)} tokens\n")
    print(f"[Static Allocation]")
    print(f"  - Peak Memory: {static_mem:.2f} MB")
    print(f"  - Elapsed Time: {static_time:.2f} ms")
    print(f"[Paged Allocation (Block=16)]")
    print(f"  - Peak Memory: {paged_mem:.2f} MB")
    print(f"  - Elapsed Time: {paged_time:.2f} ms")
    print(f"\nEfisiensi Memori: Penghematan {(1 - paged_mem / static_mem) * 100:.2f}% HBM!")
```

#### Langkah 3: Eksekusi Benchmark
```bash
python3 hands-on/m02/benchmark_engine.py
```

---

## 13. Exercise

### Level Easy
Modifikasi kelas `SimpleBlockManager` di sub-bab 7.1 untuk menyertakan pencatatan metadata `last_accessed_timestamp`. Setiap kali method `append_token()` dipanggil, update timestamp tersebut. Buat method `get_lru_request_id() -> str` yang mengembalikan request ID yang paling lama tidak melakukan decode token.

### Level Medium
Implementasikan fungsi profiling tensor PyTorch yang menghitung persentase fragmentasi internal secara akurat. Diberikan input tensor 1D berisikan panjang sequence aktual dari batch running request dan konstanta `block_size = 16`, fungsi harus me-return:
1. Total token slots yang terbuang (*wasted slots*).
2. Rasio fragmentasi internal dalam format persentase ($0.0 - 100.0\%$).

### Level Hard
Rancang dan implementasikan struktur data **Radix Tree Engine** (menggunakan Python murni atau C++) untuk mendeteksi common prefix antar prompt yang masuk ke engine scheduler. Setiap node dalam Radix Tree wajib mereferensikan list dari physical block IDs. Sistem harus mendukung:
* `insert(token_ids: List[int], block_ids: List[int])`
* `match_prefix(token_ids: List[int]) -> Tuple[List[int], int]` (mengembalikan blok IDs yang bisa di-reuse dan jumlah token yang cocok / cache-hit).
* Mekanisme reference counting (`ref_count`) pada setiap physical block, sehingga blok tidak dapat dihapus jika masih ada request aktif yang mereferensikannya.

---

## 14. Challenge

### Arsitektur Zero-Bubble Disaggregated Prefill & Decode Cluster
**Skenario Konteks**:  
Perusahaan AI skala global melayani 100 juta token per menit. Arsitektur terpadu (*colocated prefill-decode*) terbukti memicu interferensi latensi konstan: komputasi prefill yang berat merebut alokasi memory bandwidth SM dari komputasi decode token yang sensitif latensi. Anda ditunjuk sebagai Principal Infrastructure Architect untuk merancang sistem **Disaggregated Serving** generasi berikutnya (*Prefill Node Pool* terpisah secara fisik dari *Decode Node Pool*).

**Spesifikasi Desain yang Harus Disusun**:
1. **Mekanisme Transfer State KV Cache**:
   Bagaimana cara mentransfer puluhan gigabyte data KV tensor dari HBM Prefill Node ke HBM Decode Node dengan overhead mendekati nol? Evaluasi dan formulasikan arsitektur protokol transfer berbasis RDMA (Remote Direct Memory Access / InfiniBand GPUDirect Storage/RDMA) tanpa perantara memori Host RAM CPU.
2. **Dynamic Cross-Cluster Scheduling**:
   Bagaimana scheduler global menentukan kapan sebuah prefill request selesai, di node decode mana request tersebut harus di-*dispatch*, dan bagaimana physical block allocator pada Decode Engine mempersiapkan memory pool *sebelum* payload RDMA tiba?
3. **Fault Tolerance & Preemption**:
   Jika sebuah Decode Worker Node crash di tengah streaming token ke pengguna, bagaimana mekanisme pemulihan instan state KV cache tanpa harus menjalankan *full re-computation* dari context window awal?

Sajikan analisis arsitektural lengkap beserta rancangan pseudocode algoritma scheduler koordinasi antarnode.

---

## 15. Quiz Evaluasi Pemahaman

### 15.1 Bagian 1: Basic (Pilihan Ganda)
1. Apa penyebab utama pemborosan memori HBM pada static KV cache allocation?
   * A. Tingginya ukuran parameter bobot model.
   * B. Pemesanan buffer kontigu berpatokan pada batas sequence terpanjang di awal.
   * C. Overhead kompilasi Triton kernel.
   * D. Kegagalan CUDA Unified Memory mengalokasikan Swap.
2. Pada PagedAttention, berapakah batas atas teoritis fragmentasi internal pada setiap sequence?
   * A. Bergantung pada arsitektur hidden dimension.
   * B. Selalu bernilai 50%.
   * C. Maksimal sebesar $(B - 1)$ token slot per sequence, di mana $B$ adalah ukuran blok.
   * D. 0% karena memori dialokasikan per single byte.
3. Karakteristik komputasi utama pada fase Decode dalam LLM autoregresif adalah:
   * A. Compute-bound (memaksimalkan TFLOPs Tensor Core).
   * B. Memory-bandwidth bound (dibatasi oleh kecepatan pembacaan HBM ke SRAM).
   * C. I/O Disk bound (dibatasi oleh latency read NVMe SSD).
   * D. Network-latency bound pada inter-node communication.
4. Apa tujuan mendasar dari diterapkannya Iteration-Level (Continuous) Scheduling?
   * A. Mencegah program python mengalami multithreading race condition.
   * B. Mengeliminasi waiting idle akibat variansi waktu selesai token generation antar request.
   * C. Menurunkan konsumsi daya GPU ke mode idle.
   * D. Menghilangkan kebutuhan alokasi KV Cache pada fase decoding.
5. Bagaimana cara PagedAttention menangani *branching* atau *beam search* pada pemrosesan teks?
   * A. Menduplikasi seluruh tensor cache secara penuh di memori fisik HBM.
   * B. Menghentikan request lain dan memproses satu persatu.
   * C. Cukup menduplikasi entri pointer pada block table secara copy-on-write.
   * D. Melakukan transfer data paksa dari GPU ke Host CPU RAM.

### 15.2 Bagian 2: Intermediate (Pilihan Ganda & Analisis Pendek)
6. Manakah konfigurasi yang paling rentan memicu degradasi Inter-Token Latency (ITL) pada running decode requests?
   * A. Mengaktifkan chunked prefill dengan budget token 512.
   * B. Menjalankan unchunked prompt prefill sebesar 8192 token dalam forward batch yang sama dengan active decoders.
   * C. Menggunakan block size 16 pada GPU H100.
   * D. Mengimplementasikan Prefix Caching berbasis Radix Tree.
7. Mengapa PagedAttention kernel umumnya membagi komputasi menjadi format PagedAttention v1 dan v2 (Split-K/Parallel Attention)?
   * A. Untuk mengakomodasi arsitektur CNN klasik.
   * B. V1 tidak mendukung operasi konvolusi 2D.
   * C. Pada batch size kecil dengan context window panjang, v1 tidak memiliki cukup thread block untuk memenuhi utilisasi multiprocessor SM.
   * D. V2 menghilangkan kebutuhan physical memory block pool.
8. Apa dampak penghematan memori dari teknologi Grouped-Query Attention (GQA) terhadap ukuran physical KV block pool?
   * A. Tidak ada pengaruh karena jumlah key-value head identik dengan query head.
   * B. Ukuran memori physical KV cache per token menyusut proporsional dengan rasio head query terhadap head KV ($H_q / H_{kv}$).
   * C. Memori pool bertambah dua kali lipat karena komputasi grouping.
   * D. Mengubah format data FP16 secara paksa menjadi INT4.
9. Di bawah ini, kondisi manakah yang mengharuskan scheduler melakukan *preemption* (eviction / swap out) terhadap request yang sedang aktif?
   * A. TTFT mencapai di atas 20 milidetik.
   * B. Seluruh slot pada physical block pool HBM telah terpakai penuh dan ada request yang butuh alokasi token baru.
   * C. Query token menghasilkan karakter whitespace berturut-turut.
   * D. Request queue berada dalam status empty.
10. Pada teknik Radix Attention (Prefix Caching), apa yang menjadi kunci pencarian (*lookup key*) untuk mengidentifikasi keberadaan cache KV yang dapat digunakan ulang?
    * A. Hash dari representasi embedding token di layer terakhir.
    * B. Integer ID sequence dari token prompt historis yang berurutan.
    * C. Timestamp request dibuat di HTTP gateway.
    * D. Random generated UUID dari load balancer.

### 15.3 Bagian 3: Skenario Kasus Produksi
11. **Kasus 1**: Sistem serving vLLM Anda mencatatkan rasio cache thrashing yang tinggi selama flash sale e-commerce, di mana ratusan user mengirim pertanyaan panjang menggunakan system prompt promosi yang identik. Latensi melonjak parah. Berdasarkan analisis internal architecture, langkah konfigurasi spesifik apa yang harus Anda terapkan segera tanpa menambah GPU fisik?
12. **Kasus 2**: Anda mengamati bahwa server inferensi Anda berbasis PyTorch mengalami latency drop intermiten setiap 30 detik. Profiler menunjukkan terjadinya alokasi memori internal besar berulang kali yang di-trigger oleh CUDA caching allocator. Mengapa pre-allocated physical pool PagedAttention dapat menyelesaikan anomali latensi ini?
13. **Kasus 3**: Sebuah klaster inferensi disiapkan untuk melayani context window 128k token pada model Llama-3-8B. Tim engineering melaporkan bahwa throughput drop drastis ketika context window melebihi 32k token per user, dan utilisasi Tensor Core GPU merosot di bawah 20%. Identifikasi akar masalah arsitekturalnya dan berikan solusi optimasinya!

---

### Kunci Jawaban & Panduan Solusi Quiz

#### Pilihan Ganda (1–10)
1. **B** — Pemesanan buffer kontigu worst-case di awal adalah penyebab utama internal & external fragmentation.
2. **C** — Sisa token yang belum mengisi penuh satu blok terakhir pada sequence tertentu bernilai maksimal $B - 1$.
3. **B** — Decode step membaca seluruh konteks KV masa lalu untuk hanya menghitung 1 token baru, menjadikannya memory-bandwidth bound.
4. **B** — Iteration-level continuous scheduling mengeksekusi step forward per iterasi, membebaskan request selesai lebih cepat tanpa menunggu batasan sequence lain.
5. **C** — Cukup menduplikasi pointer index blok pada level block table (metadata), data tensor di HBM fisik tidak digandakan.
6. **B** — Unchunked prefill 8192 token akan memonopoli compute core GPU selama ratusan milidetik, menahan eksekusi single decode tokens sequence lainnya.
7. **C** — PagedAttention v2 menerapkan paralelisasi melintasi context blocks (Split-K reduction) untuk memaksimalkan okupansi SM ketika batch size rendah tetapi context panjang.
8. **B** — GQA memangkas jumlah head $K$ dan $V$, menurunkan konsumsi memori per token secara linier sesuai perbandingan jumlah head.
9. **B** — Ketiadaan physical blocks kosong memaksa runtime engine menangguhkan sebagian request (swapping/recompute) demi mencegah crash fatal CUDA OOM.
10. **B** — Prefix caching menggunakan deterministic sequence dari token-token IDs historis untuk traversing tree node pencarian cache block.

#### Skenario Kasus Produksi (11–13)
11. **Solusi Kasus 1**:
    Aktifkan fitur **Prefix Caching** (misal via `--enable-prefix-caching` pada vLLM). Karena ribuan user menggunakan system prompt dan teks promosi yang identik, engine hanya perlu menghitung KV state bagian promosi tersebut **satu kali**. Request berikutnya akan langsung menggunakan physical blocks yang sama secara read-only. Ini akan menghemat memori HBM secara masif, menurunkan konsumsi GPU TFLOPs prefill hingga $>70\%$, dan menghentikan loop *thrashing*.
12. **Solusi Kasus 2**:
    Pada vanilla engine, pertambahan token memicu alokasi tensor baru (`torch.cat`) yang memaksa dynamic memory allocator CUDA mencari blok memori fisik kontigu baru. Hal ini memicu overhead manajemen heap, internal dynamic lock, serta interupsi *memory compaction*. Dengan **Pre-allocated Physical Pool**, seluruh memory arena GPU telah dialokasikan secara utuh saat server start up. Selama inferensi berjalan, engine hanya memanipulasi pointer array integer (Block Table) di sisi CPU/GPU driver tanpa menyentuh alokasi kernel memori CUDA (`cudaMalloc`/`cudaFree`), menghilangkan *garbage collection overhead* dan fluktuasi latensi.
13. **Solusi Kasus 3**:
    Akar masalahnya adalah degradasi komputasi akibat batasan memori bandwidth: pada konteks 128k, panjang KV sequence luar biasa besar sehingga decode kernel konvensional memicu overhead I/O bandwidth HBM yang masif sementara occupancy multiprocessor rendah. Solusi:
    * Terapkan arsitektur **Chunked Prefill** dipadu dengan **PagedAttention v2 / FlashDecoding** (teknik Split-K yang memecah KV dimension ke multi thread block SM).
    * Jika model mendukung, pertimbangkan kuantisasi KV Cache ke FP8/INT8 (mengurangi separuh volume transfer memory bandwidth).
    * Evaluasi ukuran block size: naikkan `block_size` dari 16 ke 32 atau 64 guna mendongkrak memory access coalescing pada long-context regime.

---

## 16. Summary

* **PagedAttention** adalah inovasi fundamental yang mentransformasikan model komputasi inferensi LLM dengan memisahkan representasi logika sequence dari penempatan memori fisik HBM GPU, mengeliminasi fragmentasi eksternal secara total dan menekan fragmentasi internal hingga di bawah 3%.
* Kombinasi **Continuous Batching (Iteration-level Scheduling)** dan **Dynamic Chunked Prefill** menyelesaikan ketegangan struktural antara *throughput* dan *latensi*: throughput ditingkatkan dengan pemadatan batch dinamis, sementara jitter TTFT/ITL ditekan melalui pemotongan beban komputasi prompt prefill panjang.
* Implementasi **Prefix Caching** memanfaatkan sifat non-kontigu dari Paged KV Cache untuk menyediakan mekanisme *Zero-Compute / Zero-Memory Replication* terhadap shared contexts (system prompt, multiround dialogues, tool schemas).
* Keberhasilan implementasi engine level enterprise bergantung pada kehati-hatian perancangan granularitas blok, pengaturan limit *budget token* per forward step, sinkronisasi NUMA-aware I/O, serta mitigasi degradasi throughput pada rezim long-context decoding.