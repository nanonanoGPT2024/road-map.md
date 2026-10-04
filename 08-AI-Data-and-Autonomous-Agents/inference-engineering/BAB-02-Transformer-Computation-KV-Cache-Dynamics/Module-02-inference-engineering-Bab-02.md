# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 02: Transformer Computation & KV Cache Dynamics**
**Jalur Pembelajaran: Inference Engineering (08-AI-Data-and-Autonomous-Agents)**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Menganalisis Arithmetic Intensity dan Profil Komputasi:** Mengidentifikasi batas komputasi (*compute-bound*) pada fase *Prefill* dan batas *bandwidth* memori (*memory-bound*) pada fase *Decode* menggunakan *Roofline Model*.
2. **Menghitung Footprint Memori KV Cache Secara Presisi:** Mengalkulasikan kebutuhan VRAM KV Cache secara matematis untuk berbagai varian arsitektur (*Multi-Head Attention*, *Multi-Query Attention*, dan *Grouped-Query Attention*) pada berbagai tingkat konkurensi.
3. **Merancang Sistem Alokasi Memori PagedAttention:** Mengimplementasikan modul *Virtual Memory Manager* berbasis blok untuk mengeliminasi fragmentasi internal dan eksternal pada VRAM GPU.
4. **Mengimplementasikan Teknik Optimasi KV Cache Lanjutan:** Menerapkan kuantisasi KV Cache (FP8/INT8), *Sliding Window Attention*, dan *Prefix Caching* (Copy-on-Write) untuk meminimalkan *Inter-Token Latency* (ITL).
5. **Mendiagnosis dan Memecahkan Bottleneck Produksi:** Menemukan *memory leak*, CUDA *synchronization overhead*, dan de-kuantisasi *overhead* pada *serving engine* skala enterprise.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib menguasai:

* **Arsitektur Internal Transformer:** Mekanisme *Scaled Dot-Product Attention*, struktur matriks $W_Q, W_K, W_V, W_O$, dan *autoregressive decoding loop*.
* **Hirarki Memori Akselerator GPU:** Karakteristik HBM (*High Bandwidth Memory*), SRAM/Shared Memory, L2 Cache, serta konsep *Memory Bandwidth* vs *TFLOPS Compute*.
* **Sistem Pemrograman PyTorch/C++:** Pemahaman tentang *tensor striding*, alokasi memori CUDA, dan eksekusi *kernel-level primitives*.
* **Konsep Sistem Operasi:** *Virtual Memory Management*, *Paging*, *Page Tables*, dan *Translation Lookaside Buffer* (TLB).

---

## 3. Concept & Internal Architecture

Dalam inferensi *Large Language Model* (LLM), proses *autoregressive generation* membagi inferensi menjadi dua fase komputasi yang karakternya bertolak belakang: **Prefill Phase** dan **Decode Phase**.

### 3.1. Anatomi Komputasi: Prefill vs. Decode

Diberikan sebuah sequence input $X \in \mathbb{R}^{B \times S \times D}$ di mana $B$ adalah *batch size*, $S$ adalah panjang sequence, dan $D$ adalah dimensi model:

$$\text{Attention}(Q, K, V) = \text{softmax}\left(\frac{QK^T}{\sqrt{d_k}}\right)V$$

```
Prefill (Compute-Bound: GEMM)
Input: S tokens simultaneously
+-----------------------------------------------------------+
| Q * K^T Matrix Multiplication                             |
| FLOPs: O(S^2 * D) -> Sangat tinggi                        |
| Arithmetic Intensity: > 100 FLOPs/byte (Mencapai TFLOPS)  |
+-----------------------------------------------------------+

Decode (Memory-Bound: GEMV)
Input: 1 token at step t (mengakses historical KV 1 to t-1)
+-----------------------------------------------------------+
| q_t * (K_past)^T Matrix-Vector Multiplication             |
| FLOPs: O(t * D) -> Rendah                                 |
| Arithmetic Intensity: < 2 FLOPs/byte (Terhambat HBM BW)   |
+-----------------------------------------------------------+
```

Pada fase **Prefill**, model memproses seluruh prompt secara paralel. Komputasi didominasi oleh operasi *General Matrix Multiply* (GEMM), di mana *operational intensity* (rasio FLOPs terhadap akses memori) tinggi, sehingga mengeksploitasi seluruh *Tensor Cores* pada GPU.

Pada fase **Decode**, model menghasilkan satu token per langkah ($t$). Matriks $Q$ menciut menjadi sebuah vektor $q_t \in \mathbb{R}^{1 \times D}$. Operasi berubah menjadi *General Matrix-Vector Multiply* (GEMV). 

Jika *Key* dan *Value* dari token-token sebelumnya ($K_{1:t-1}, V_{1:t-1}$) tidak disimpan di memori, GPU terpaksa menghitung ulang seluruh state masa lalu ($O(t^2)$ FLOPs per step). Untuk mengatasi hal ini, state $K$ dan $V$ di-*cache* ke dalam VRAM: inilah **KV Cache**.

### 3.2. Formulasi Matematika Footprint KV Cache

Kapasitas VRAM yang dihabiskan untuk menyimpan KV Cache untuk satu token tunggal di seluruh layer dihitung melalui parameter:
* $L$: Jumlah layer (*num_hidden_layers*)
* $H_{kv}$: Jumlah attention head untuk Key/Value
* $D_{head}$: Dimensi per head ($d_k = D / H_q$)
* $P$: Presisi dalam byte (FP16/BF16 = 2 bytes, FP8 = 1 byte, INT4 = 0.5 bytes)

Ukuran KV Cache per token ($M_{token}$):

$$M_{token} = 2 \times L \times H_{kv} \times D_{head} \times P \quad \text{(faktor 2 berasal dari Key dan Value)}$$

Untuk *serving engine* yang menangani batch berukuran $B$ dengan context length $S$:

$$M_{total}(B, S) = B \times S \times M_{token}$$

#### Perbandingan Arsitektur Attention: MHA vs. MQA vs. GQA
* **Multi-Head Attention (MHA):** $H_{kv} = H_q$. Konsumsi memori maksimal.
* **Multi-Query Attention (MQA):** $H_{kv} = 1$. Seluruh query head berbagi satu pasangan head K dan V. Reduksi memori hingga $H_q \times$. Kelemahan: Penurunan akurasi/kapasitas representasi.
* **Grouped-Query Attention (GQA):** $H_{kv} = \frac{H_q}{G}$, di mana $G$ adalah ukuran grup (misal Llama-3-70B: $H_q = 64, H_{kv} = 8$). Menawarkan titik optimal antara akurasi model dan efisiensi memori.

```
       MHA (H_q = 8, H_kv = 8)            GQA (H_q = 8, H_kv = 2)           MQA (H_q = 8, H_kv = 1)
Q: [0] [1] [2] [3] [4] [5] [6] [7]  Q: [0] [1] [2] [3] [4] [5] [6] [7]  Q: [0] [1] [2] [3] [4] [5] [6] [7]
    |   |   |   |   |   |   |   |       \   /   \   /   \   /   \   /       \   \   \   |   /   /   /   /
KV:[0] [1] [2] [3] [4] [5] [6] [7]  KV:   [0]     [1]     [2]     [3]   KV:              [0]
   (KV Cache Size: 100%)                  (KV Cache Size: 25%)                   (KV Cache Size: 12.5%)
```

### 3.3. Masalah Fragmentasi Memori & Arsitektur PagedAttention

Secara naif, alokasi KV Cache dilakukan menggunakan memori kontigu statis (*contiguous buffer*) seukuran `max_model_len` (misal 8192 token). Pendekatan konvensional ini merusak kapasitas *throughput* karena dua anomali:
1. **Internal Fragmentation:** Ruang buffer dialokasikan untuk 8192 token, tetapi request pengguna selesai pada token ke-150. Sisanya terbuang tak terpakai.
2. **External Fragmentation:** Alokasi dinamis sederhana menyebabkan memori VRAM terpecah menjadi potongan-potongan kecil yang tidak cukup besar untuk request baru.

```
Pendekatan Naif (Buffer Kontigu Statis):
Request 1: [Aktif: 200 token][Reservasi Kosong: 7992 token               ] -> VRAM terbuang 97.5%
Request 2: [Aktif: 50 token ][Reservasi Kosong: 8142 token               ] -> VRAM terbuang 99.3%

PagedAttention (Alokasi Non-Kontigu Berbasis Blok/Halaman):
Physical Blocks (GPU VRAM Pool):
[Block 0][Block 1][Block 2][Block 3][Block 4][Block 5] ... [Block N]
(Ukuran blok seragam, misal: 16 token per blok)

Logical-to-Physical Mapping (Block Table):
Req 1, Block 0 -> Phys Block 4
Req 1, Block 1 -> Phys Block 12
Req 2, Block 0 -> Phys Block 1
```

**PagedAttention** mengadaptasi prinsip *Virtual Memory* dari Kernel Sistem Operasi:
* KV Cache untuk sebuah sequence dipecah menjadi kumpulan blok (*Logical Blocks*). Setiap blok menampung sejumlah token tetap (umumnya $B_{size} = 16$ atau $32$).
* Blok-blok fisik (*Physical Blocks*) tidak perlu berada pada alamat VRAM yang berurutan.
* *Engine* memelihara **Block Table** yang memetakan:
  $$\text{Logical Block Index} \xrightarrow{\text{Block Table}} \text{Physical Block Index}$$
* Alokasi bersifat *on-demand*. Ketika token baru digenerasikan dan blok saat ini telah penuh, alokator mengambil satu blok bebas dari pool (*Free List*). Fragmentasi internal hanya terjadi pada blok terakhir dari sebuah sequence ($< B_{size}$ token).

---

## 4. Why & What

| Dimensi | Alokasi Kontigu Naif | PagedAttention Engine |
| :--- | :--- | :--- |
| **Pemanfaatan VRAM** | 20% - 40% (sisanya *reserved waste*) | > 96% pemanfaatan riil |
| **Konkurensi Sistem** | Rendah (OOM terjadi prematur) | 2x - 4x Batch Size efektif |
| **Dukungan Prefix Sharing** | Duplikasi buffer memori secara penuh | Nol salinan (*Copy-on-Write Reference Count*) |
| **Efisiensi Beam Search** | Eksponensial duplikasi memori | Berbagi *parent blocks*, cabang baru di-fork |
| **Bottleneck Dominan** | VRAM Out-of-Memory (Capacity-bound) | Saturasi Memory Bandwidth (Bandwidth-bound) |

### Mengapa Memory Bandwidth Mengunci Latensi Decode?
Dalam fase decode, untuk setiap token tunggal yang dihasilkan oleh model dengan parameter $W$ dan KV Cache $M_{kv}$, GPU harus membaca seluruh parameter $W$ dan seluruh history $M_{kv}$ dari HBM ke SRAM.

$$\text{Waktu Baca Token} \approx \frac{\text{Bytes}(W) + \text{Bytes}(M_{kv})}{\text{Bandwidth HBM}}$$

Jika GPU H100 memiliki bandwidth 3.35 TB/s, dan model Llama-3-70B FP16 memiliki ukuran bobot 140 GB, membaca bobot saja membutuhkan:

$$\frac{140 \times 10^9 \text{ bytes}}{3.35 \times 10^{12} \text{ bytes/s}} \approx 41.7 \text{ ms}$$

Batas teoretis *serving* tanpa batching adalah $\approx 24 \text{ token/s}$. Untuk meningkatkan throughput secara drastis, kita **wajib** meningkatkan konkurensi (batching), sehingga bobot model yang sama dibaca sekali dari HBM untuk melayani banyak token secara simultan. Di sinilah efisiensi alokasi memori KV Cache menjadi penentu: jika KV Cache memboroskan VRAM, konkurensi batching tidak dapat dinaikkan.

---

## 5. How: Alur Kerja Komputasi dan Siklus Hidup Blok

```
[Request User Masuk]
        │
        ▼
[1. Scheduler & Tokenizer]
        │
        ▼
[2. Prefill Phase Check]
        ├─ Ada Prefix Cache yang cocok?
        │      ├─ YA  ──> Arahkan Logical Block ke Physical Block yang ada (Inkrementasi Ref Count)
        │      └─ TIDAK ─> Alokasikan Blok Fisik baru dari Free List
        │
        ▼
[3. Chunked Prefill Execution]
        │  (Hitung Attention & isi Physical Blocks K dan V)
        ▼
[4. Autoregressive Decode Loop (Token-by-Token)]
        │
        ├─> [Cek Kapasitas Blok Aktif]
        │      ├─ Blok Penuh? ──> Alokasikan Blok Fisik baru dari Free List; Update Block Table
        │      └─ Masih Cukup? ──> Tulis k_t, v_t ke slot index offset di blok aktif
        │
        ├─> [Eksekusi PagedAttention Kernel]
        │      (Akses memori tak berurutan melalui lookup Block Table via SRAM)
        │
        ├─> [Sampling & Detokenize]
        │      (Dapatkan token ID baru)
        │
        └─ Selesai (EOS / Max Tokens)?
               ├─ TIDAK ──> Kembali ke Langkah 4
               └─ YA ───> Lanjut ke Langkah 5
        ▼
[5. Request Completion & Resource Freeing]
        │
        ▼
[6. Block Manager Reclaim]
        (Dekrementasi Ref Count. Jika Ref Count == 0, kembalikan Physical Block ke Free List)
```

---

## 6. Analogi & Diagram ASCII

### Analogi Virtual Memory
Bayangkan KV Cache adalah **ruang kantor sewaan**.
* **Naif:** Anda menyewa 1 lantai gedung pencakar langit (8192 meja) untuk setiap klien baru, meskipun klien tersebut hanya datang membawa 2 orang staf selama 10 menit. Anda kehabisan lantai gedung dengan sangat cepat.
* **PagedAttention:** Anda menyewa ruang kerja *coworking* dalam unit meja modular (1 blok = 16 meja). Ketika staf klien bertambah, sistem resepsionis (*Block Table*) mencatat bahwa klien Anda memakai Meja #4 di Lantai 2, dan Meja #18 di Lantai 5. Ketika rapat selesai, meja langsung dikembalikan ke daftar meja kosong untuk digunakan klien lain.

### Pemetaan Memori PagedAttention

```
========================================================================================
LOGICAL VIEW (Sequence 0, Panjang 37 Token, Block Size = 16)
========================================================================================
Logical Blocks:
[Block 0: Tokens 0-15]     [Block 1: Tokens 16-31]     [Block 2: Tokens 32-36 (11 Free Slots)]
         │                           │                            │
         ▼                           ▼                            ▼
========================================================================================
BLOCK TABLE (Sequence 0 Mapping)
========================================================================================
Logical Idx:    0                          1                           2
Physical Block: [7]                        [3]                         [9]
========================================================================================
PHYSICAL VRAM POOL (Contiguous Array of Blocks in GPU Memory)
========================================================================================
+-----------+-----------+-----------+-----------+-----------+-----------+-----------+-----------+
| Block 0   | Block 1   | Block 2   | Block 3   | Block 4   | ...       | Block 7   | ...       |
| (Req 1)   | (Free)    | (Req 2)   | (Req 0,L1)| (Req 1)   |           | (Req 0,L0)|           |
+-----------+-----------+-----------+-----------+-----------+-----------+-----------+-----------+
                                          ▲                                   ▲
                                          │                                   │
                                          └───────────────────────────────────┘
```

---

## 7. Implementasi Kode Standar Industri

Berikut adalah implementasi Python yang memodelkan logika fundamental dari alokator memori PagedAttention, kalkulator dinamika KV Cache, dan simulasi penulisan buffer non-kontigu berstandar enterprise.

```python
"""
Enterprise Inference Engine: PagedAttention Block Manager & Dynamic KV Cache Simulator.
Arsitektur dirancang untuk mendukung GQA, Copy-on-Write, dan tracking fragmentasi memori.
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
import torch


@dataclass(frozen=True)
class ModelConfig:
    num_layers: int
    num_query_heads: int
    num_kv_heads: int
    head_dim: int
    dtype: torch.dtype = torch.float16

    @property
    def bytes_per_element(self) -> int:
        return torch.tensor([], dtype=self.dtype).element_size()

    @property
    def kv_cache_bytes_per_token(self) -> int:
        # 2 represents Key and Value tensors
        return 2 * self.num_layers * self.num_kv_heads * self.head_dim * self.bytes_per_element


@dataclass
class PhysicalBlock:
    block_id: int
    block_size: int
    ref_count: int = 0

    def is_free(self) -> bool:
        return self.ref_count == 0


class BlockManager:
    """
    Mengelola alokasi, pelepasan, dan pemetaan halaman fisik KV Cache di VRAM GPU.
    """
    def __init__(self, block_size: int, total_gpu_blocks: int):
        self.block_size = block_size
        self.total_gpu_blocks = total_gpu_blocks
        self.free_blocks: List[int] = list(range(total_gpu_blocks - 1, -1, -1))
        self.physical_blocks: List[PhysicalBlock] = [
            PhysicalBlock(block_id=i, block_size=block_size) for i in range(total_gpu_blocks)
        ]
        # Mapping request_id -> List[Physical Block Indices]
        self.block_tables: Dict[str, List[int]] = {}

    def get_num_free_blocks(self) -> int:
        return len(self.free_blocks)

    def allocate_block(self) -> int:
        if not self.free_blocks:
            raise MemoryError("CUDA OOM: Out of Physical Blocks in KV Cache Pool!")
        block_id = self.free_blocks.pop()
        self.physical_blocks[block_id].ref_count = 1
        return block_id

    def register_request(self, request_id: str, prompt_tokens: int) -> None:
        """Mengalokasikan blok awal untuk prompt pada fase prefill."""
        num_blocks_needed = math.ceil(prompt_tokens / self.block_size)
        if num_blocks_needed > len(self.free_blocks):
            raise MemoryError(
                f"Cannot allocate {num_blocks_needed} blocks. Only {len(self.free_blocks)} available."
            )

        allocated: List[int] = [self.allocate_block() for _ in range(num_blocks_needed)]
        self.block_tables[request_id] = allocated

    def append_slot(self, request_id: str, current_seq_len: int) -> Tuple[int, int]:
        """
        Menyediakan slot fisik untuk token baru pada fase decode.
        Return: (physical_block_id, offset_in_block)
        """
        table = self.block_tables[request_id]
        offset = current_seq_len % self.block_size

        if offset == 0:
            # Membutuhkan blok baru karena blok sebelumnya telah penuh
            new_block_id = self.allocate_block()
            table.append(new_block_id)
            physical_block_id = new_block_id
            block_offset = 0
        else:
            # Menggunakan slot tersisa di blok aktif
            physical_block_id = table[-1]
            block_offset = offset

        return physical_block_id, block_offset

    def fork_sequence(self, source_request_id: str, target_request_id: str) -> None:
        """
        Mendukung teknik Parallel Sampling / Beam Search via Copy-on-Write.
        Menduplikasi tabel tanpa menduplikasi alokasi memori fisik.
        """
        source_table = self.block_tables[source_request_id]
        for b_id in source_table:
            self.physical_blocks[b_id].ref_count += 1
        self.block_tables[target_request_id] = list(source_table)

    def free_request(self, request_id: str) -> None:
        """Membersihkan alokasi sequence dan mengembalikan blok yang tidak lagi direferensikan."""
        if request_id not in self.block_tables:
            return

        for block_id in self.block_tables[request_id]:
            block = self.physical_blocks[block_id]
            block.ref_count -= 1
            if block.ref_count == 0:
                self.free_blocks.append(block_id)

        del self.block_tables[request_id]


class ProductionPagedKVCache:
    """
    Abstraksi memori KV Cache fisik non-kontigu pada level GPU Tensor.
    """
    def __init__(self, config: ModelConfig, block_size: int, total_blocks: int, device: str = "cpu"):
        self.config = config
        self.block_size = block_size
        self.total_blocks = total_blocks
        self.device = device
        
        # Tensor Pool Fisik: [Total_Blocks, Layers, 2 (K/V), Block_Size, Num_KV_Heads, Head_Dim]
        self.cache_pool = torch.empty(
            (total_blocks, config.num_layers, 2, block_size, config.num_kv_heads, config.head_dim),
            dtype=config.dtype,
            device=device
        )
        self.manager = BlockManager(block_size=block_size, total_gpu_blocks=total_blocks)

    def write_single_token(
        self,
        request_id: str,
        current_seq_len: int,
        layer_idx: int,
        k_val: torch.Tensor,
        v_val: torch.Tensor
    ) -> None:
        """
        Menulis representasi K dan V satu token decode ke dalam struktur paged.
        Shape k_val & v_val: [Num_KV_Heads, Head_Dim]
        """
        phys_block_id, offset = self.manager.append_slot(request_id, current_seq_len)
        
        # Penulisan non-kontigu ke blok fisik
        self.cache_pool[phys_block_id, layer_idx, 0, offset, :, :] = k_val
        self.cache_pool[phys_block_id, layer_idx, 1, offset, :, :] = v_val

    def read_sequence_kv(self, request_id: str, seq_len: int, layer_idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Merekonsiliasi blok-blok non-kontigu menjadi matriks representasi kontigu untuk komputasi attention.
        """
        block_table = self.manager.block_tables[request_id]
        keys = []
        vals = []
        
        tokens_remaining = seq_len
        for b_id in block_table:
            take_tokens = min(self.block_size, tokens_remaining)
            keys.append(self.cache_pool[b_id, layer_idx, 0, :take_tokens])
            vals.append(self.cache_pool[b_id, layer_idx, 1, :take_tokens])
            tokens_remaining -= take_tokens
            if tokens_remaining <= 0:
                break
                
        return torch.cat(keys, dim=0), torch.cat(vals, dim=0)


# ==========================================
# Verifikasi & Simulasi Eksekusi
# ==========================================
if __name__ == "__main__":
    # Konfigurasi Llama-3-8B (GQA: 32 Query Heads, 8 KV Heads)
    llama3_8b = ModelConfig(
        num_layers=32,
        num_query_heads=32,
        num_kv_heads=8,
        head_dim=128,
        dtype=torch.float16
    )

    print("=== KV Cache Architectural Calculation ===")
    token_bytes = llama3_8b.kv_cache_bytes_per_token
    print(f"Memory KV Cache per token: {token_bytes} bytes ({token_bytes / 1024:.2f} KB)")
    
    context_window = 8192
    single_req_gb = (token_bytes * context_window) / (1024 ** 3)
    print(f"KV Cache per 8k context (Single Request): {single_req_gb:.4f} GB")
    
    # Inisialisasi Paged Engine dengan 1024 blok (16 tokens/blok) = Kapasitas 16,384 tokens
    BLOCK_SIZE = 16
    TOTAL_BLOCKS = 1024
    engine = ProductionPagedKVCache(llama3_8b, block_size=BLOCK_SIZE, total_blocks=TOTAL_BLOCKS)
    
    # 1. Alokasi Request Baru
    req_a = "req-job-001"
    prompt_len = 35  # Membutuhkan ceil(35/16) = 3 Blok
    engine.manager.register_request(req_a, prompt_tokens=prompt_len)
    
    print(f"\nAlokasi Awal '{req_a}' ({prompt_len} token):")
    print(f"  Physical Blocks Alokasi: {engine.manager.block_tables[req_a]}")
    print(f"  Sisa Physical Blocks Pool: {engine.manager.get_num_free_blocks()}")
    
    # 2. Simulasi 1 Step Decode
    dummy_k = torch.randn((8, 128), dtype=torch.float16)
    dummy_v = torch.randn((8, 128), dtype=torch.float16)
    engine.write_single_token(req_a, current_seq_len=35, layer_idx=0, k_val=dummy_k, v_val=dummy_v)
    
    print("\nSetelah 1 Token Decode (Total: 36 token):")
    print(f"  Physical Blocks Terpakai: {engine.manager.block_tables[req_a]}")
    
    # 3. Pengujian Fork Sequence (Beam Search / CoW)
    req_b = "req-job-001-child"
    engine.manager.fork_sequence(req_a, req_b)
    print(f"\nFork Sequence '{req_a}' -> '{req_b}':")
    print(f"  Req B Table: {engine.manager.block_tables[req_b]}")
    first_block = engine.manager.block_tables[req_b][0]
    print(f"  Ref count Blok Fisik #{first_block}: {engine.manager.physical_blocks[first_block].ref_count}")
    
    # 4. Cleanup Sequence A
    engine.manager.free_request(req_a)
    print(f"\nSetelah Release Request '{req_a}':")
    print(f"  Ref count Blok Fisik #{first_block}: {engine.manager.physical_blocks[first_block].ref_count} (Masih ditahan Req B)")
    
    engine.manager.free_request(req_b)
    print(f"Setelah Release Request '{req_b}':")
    print(f"  Ref count Blok Fisik #{first_block}: {engine.manager.physical_blocks[first_block].ref_count}")
    print(f"  Total Blok Bebas Kembali: {engine.manager.get_num_free_blocks()} / {TOTAL_BLOCKS}")
```

---

## 8. Real World Case Study: FinTech Banking LLM Platform

### Deskripsi Masalah
Sebuah bank investasi global menggelar layanan *autonomous agent* untuk menganalisis dokumen regulasi keuangan menggunakan **Llama-3-70B-Instruct** pada kluster **8x NVIDIA H100 SXM5 (80GB)** menggunakan *Tensor Parallelism* ($TP = 8$).

* **Beban Kerja:** 500 pengguna konkuren. Panjang dokumen prompt rata-rata 12.000 token, panjang output decode rata-rata 500 token.
* **Insiden Produksi:** Engine mengalami kegagalan berulang akibat *CUDA Out Of Memory* (OOM). Metrik *Time-to-First-Token* (TTFT) melonjak ke 18 detik, dan throughput terhenti pada $\approx 12$ request/menit.

### Analisis Akar Masalah (Root Cause Analysis)
1. **Engine Menggunakan Alokasi Statis Konvensional:** Engine mengalokasikan buffer kontigu statis sebesar `max_model_len = 16384` untuk setiap slot batch.
   $$\text{Konsumsi Memori Statis per Request} = 16384 \times M_{token} = 16384 \times 160 \text{ KB} \approx 2.56 \text{ GB}$$
   Untuk 500 request: Membutuhkan $1.28 \text{ TB}$ hanya untuk KV Cache, jauh melampaui VRAM yang tersedia setelah bobot model dimuat ($8 \times 80\text{GB} - 140\text{GB} = 500\text{GB}$).
2. **Tidak Ada Prefix Sharing:** Ratusan request menganalisis draf dokumen regulasi yang sama (10.000 token sistem prompt yang identik), namun engine menduplikasi token-token tersebut di memori untuk setiap request.

### Solusi Teknis & Arsitektur
1. **Migrasi ke PagedAttention (Block Size = 16):** Menghilangkan alokasi statis 16k token. Memori dialokasikan secara granular sesuai konsumsi riil.
2. **Automatic Prefix Caching (APC):** System prompt dokumen regulasi (10k token) disimpan pada blok persisten dengan *reference count* berbasis hash SHA-256. Seluruh 500 request diarahkan untuk mereferensikan blok fisik yang sama.
3. **Kuantisasi KV Cache ke FP8 (E4M3):** Mengonversi penyimpanan KV Cache dari FP16 (2 byte) ke FP8 (1 byte), memangkas *memory footprint* per token hingga 50% ($80 \text{ KB/token}$).

### Hasil & Dampak Metrik Produksi

| Metrik | Sebelum Implementasi | Setelah Optimasi (Paged + APC + FP8) | Imbas Bisnis |
| :--- | :--- | :--- | :--- |
| **Max Concurrent Requests** | 18 request (sebelum OOM) | 320 request | Peningkatan kapasitas $17.7\times$ |
| **TTFT (P99)** | 18.200 ms | 480 ms (Cache Hit) / 2.100 ms (Miss) | Penurunan latensi hingga 97% |
| **Inter-Token Latency (ITL)** | 92 ms/token | 18 ms/token | Respon *streaming* instan |
| **VRAM Fragmentation** | 68% (Terbuang) | < 3.8% | Efisiensi hardware maksimal |

---

## 9. Trade-offs Architecture Matrix

| Parameter Desain | Opsi A | Opsi B | Trade-off Analysis |
| :--- | :--- | :--- | :--- |
| **Ukuran Blok PagedAttention** | **Kecil (e.g., 8 tokens)** | **Besar (e.g., 64 tokens)** | **Blok Kecil:** Fragmentasi internal mendekati nol, namun *Block Table overhead* melonjak dan kernel launch GPU kurang efisien.<br>**Blok Besar:** Efisiensi akses memori kontigu GPU meningkat (*vectorized load*), namun fragmentasi internal pada token akhir meningkat. |
| **Format Presisi KV** | **Uncompressed (FP16/BF16)** | **Quantized (FP8 / INT4)** | **FP16:** Presisi numerik sempurna, degradasi *perplexity* 0%. Footprint memori masif.<br>**FP8:** Kapasitas VRAM naik 2x, sedikit kehilangan akurasi pada attention score ekstrim. Butuh de-kuantisasi *on-the-fly* pada hardware non-native FP8. |
| **Eviction Policy** | **Sliding Window (Local)** | **Full Context Retention** | **Sliding Window:** Penggunaan VRAM konstan dan bounded ($O(W)$), namun model kehilangan memori jangka panjang (*catastrophic forgetting*).<br>**Full Context:** Retensi informasi sempurna, namun konsumsi VRAM tumbuh linear $O(S)$ hingga batas hardware. |

---

## 10. Common Mistakes & Troubleshooting

### 1. CUDA Graph Broken oleh Dinamika Paged Memory
* **Gejala:** Latensi decode token meningkat secara sporadis, eksekusi CPU memblokir GPU (*high CPU dispatch overhead*).
* **Penyebab:** *CUDA Graphs* memerlukan alamat memori tensor dan *shape* yang statis. Alokasi blok yang berubah secara dinamis pada setiap token memutus kemampuan *replay* CUDA Graph.
* **Mitigasi:** Gunakan teknik *Slot Mapping Buffer* yang dialokasikan di awal (*pre-allocated fixed-size buffer*). Rekam CUDA Graph untuk ukuran batch tetap, dan lakukan *indirect indexing* melalui tensor referensi pointer.

### 2. Synchronization Pitfall saat Membaca Block Table dari Host (CPU)
* **Gejala:** Throughput menurun hingga 60% ketika konkurensi naik, GPU idle tinggi pada trace *NVIDIA Nsight Systems*.
* **Penyebab:** Melakukan pemindahan (*copy*) metadata `block_table` dari CPU Host ke GPU Device di setiap langkah decode menggunakan `tensor.to('cuda')` sinkron, memicu *device-host barrier*.
* **Mitigasi:** Kelola seluruh metadata Block Table langsung di GPU VRAM atau gunakan *Pinned Memory* (Page-locked) dengan alokasi asinkron via `cudaMemcpyAsync`.

### 3. Numerical Instability pada FP8 KV Cache Dequantization
* **Gejala:** Model tiba-tiba menghasilkan output repetitif atau karakter sampah (*gibberish*) setelah berjalan lebih dari 2048 token pada format FP8.
* **Penyebab:** Outlier aktivasi pada matriks *Key* menyebabkan *underflow* numerik jika menggunakan *per-tensor quantization scale*.
* **Mitigasi:** Terapkan skema kuantisasi **per-channel** atau **per-block** (misal per 128 elemen) alih-alih per-tensor, serta simpan scaling factor $\alpha$ dalam FP32 di level head.

---

## 11. Production Best Practices Checklist

- [ ] **Rasio Alokasi Memori KV Cache Dinamis:** Konfigurasikan engine untuk mengunci rasio VRAM KV Cache statis (misal 90% dari sisa VRAM setelah bobot model dimuat) guna mencegah benturan alokasi dengan CUDA Driver context.
- [ ] **Optimalisasi Block Size Sesuai Karakteristik Serving:** Gunakan block size 16 untuk beban kerja dengan context pendek (dialog customer service), atau block size 32/64 untuk pemrosesan dokumen masif (RAG/Document Parsing).
- [ ] **Prefix Caching Hash Indexing:** Implementasikan struktur data *Radix Tree* atau *Trie* terindeks untuk melakukan pencarian prefix prompt secara deterministik dalam kompleksitas $O(K)$.
- [ ] **Chunked Prefill Activation:** Konfigurasikan batas pemotongan prefill (misal `max_num_batched_tokens = 512`) untuk menyisipkan operasi prefill panjang ke dalam siklus komputasi decode tanpa merusak *Inter-Token Latency SLA*.
- [ ] **Memory Watermark Eviction Guard:** Definisikan ambang batas intervensi (misal saat 98% blok terpakai) untuk menunda request baru (*backpressure*) atau menukar (*swap*) blok KV sequence terlama ke Host CPU RAM via PCIe.

---

## 12. Hands-on Practice

Dalam latihan ini, Anda akan membangun skrip profil memori dan verifikasi alokator KV Cache untuk mengukur fragmentasi memori internal secara kuantitatif.

### Struktur Direktori
```
hands-on/m02/
├── dynamic_kv_bench.py
├── run_profile.sh
└── test_cases.json
```

### File: `hands-on/m02/dynamic_kv_bench.py`
```python
import time
import torch
import sys

def benchmark_memory_fragmentation(seq_lengths: list[int], block_size: int = 16):
    """
    Menghitung fragmentasi internal teoretis antara Contiguous Buffering vs PagedAllocation.
    """
    total_tokens = sum(seq_lengths)
    max_len = max(seq_lengths)
    batch_size = len(seq_lengths)
    
    # 1. Analisis Contiguous Allocation
    # Buffer dialokasikan sebesar batch_size * max_len
    contiguous_allocated_slots = batch_size * max_len
    contiguous_wasted_slots = contiguous_allocated_slots - total_tokens
    contiguous_frag_pct = (contiguous_wasted_slots / contiguous_allocated_slots) * 100
    
    # 2. Analisis Paged Allocation
    paged_allocated_slots = 0
    for length in seq_lengths:
        blocks = (length + block_size - 1) // block_size
        paged_allocated_slots += blocks * block_size
        
    paged_wasted_slots = paged_allocated_slots - total_tokens
    paged_frag_pct = (paged_wasted_slots / paged_allocated_slots) * 100
    
    print("=" * 60)
    print(f"BENCHMARK HASIL ALOKASI (Batch: {batch_size}, Total Token: {total_tokens})")
    print("=" * 60)
    print(f"Contiguous Buffer Total Slots : {contiguous_allocated_slots}")
    print(f"Contiguous Buffer Wasted Slots: {contiguous_wasted_slots} ({contiguous_frag_pct:.2f}% terbuang)")
    print("-" * 60)
    print(f"Paged (B={block_size}) Allocated Slots : {paged_allocated_slots}")
    print(f"Paged (B={block_size}) Wasted Slots    : {paged_wasted_slots} ({paged_frag_pct:.2f}% terbuang)")
    print("-" * 60)
    print(f"EFISIENSI PENGHEMATAN VRAM    : {((contiguous_allocated_slots - paged_allocated_slots) / contiguous_allocated_slots) * 100:.2f}%")
    print("=" * 60)

if __name__ == "__main__":
    # Distribusi panjang request heterogen yang representatif di industri
    workload = [128, 45, 1024, 230, 12, 4096, 512, 64, 890, 120]
    benchmark_memory_fragmentation(workload, block_size=16)
```

### Langkah Eksekusi & Verifikasi
```bash
# Masuk ke direktori praktikum
mkdir -p hands-on/m02
cd hands-on/m02

# Buat file implementasi di atas menggunakan editor Anda, lalu jalankan:
python3 dynamic_kv_bench.py
```

### Ekspektasi Output
```text
============================================================
BENCHMARK HASIL ALOKASI (Batch: 10, Total Token: 7119)
============================================================
Contiguous Buffer Total Slots : 40960
Contiguous Buffer Wasted Slots: 33841 (82.62% terbuang)
------------------------------------------------------------
Paged (B=16) Allocated Slots : 7184
Paged (B=16) Wasted Slots    : 65 (0.90% terbuang)
------------------------------------------------------------
EFISIENSI PENGHEMATAN VRAM    : 82.46%
============================================================
```

---

## 13. Exercise

### Level Easy
Diberikan arsitektur model **Mistral-7B** ($L=32, H_q=32, H_{kv}=8, D_{head}=128$) menggunakan presisi **BF16**. Hitung konsumsi VRAM KV Cache murni untuk beban kerja dengan batch size 64 dan panjang sekuens rata-rata 2048 token.

### Level Medium
Modifikasi class `BlockManager` pada Bagian 7 untuk menambahkan fungsionalitas **Watermark Eviction**. Ketika jumlah sisa blok berada di bawah 10% dari total kapasitas pool, tolak request baru dengan melempar exception kustom `BackpressureError` dan catat metrik tersebut.

### Level Hard
Implementasikan algoritma alokasi **Copy-on-Write (CoW)** murni pada level array tensor:
1. Ketika sebuah sequence di-fork, buat salinan Block Table baru yang memetakan ke block ID fisik yang sama.
2. Ketika salah satu sequence menulis token baru ke blok fisik yang sedang berbagi referensi (`ref_count > 1`), alokasikan blok baru secara transparan, salin data lama dari blok fisik bersama tersebut, kurangi `ref_count` blok asal, dan update pointer sequence yang menulis ke blok baru tersebut.

---

## 14. Challenge: Arsitektur Ultra-Long Context Multi-Tenant

### Deskripsi Masalah Nyata
Perusahaan Anda sedang membangun platform inferensi untuk memproses buku, repositori kode, dan laporan hukum dengan context window hingga **128.000 token per request** menggunakan model open-weights Llama-3-70B. Platform harus beroperasi pada kluster GPU yang terbatas ($4 \times 8 \times \text{H100 } 80\text{GB}$).

Sistem dihadapkan pada skenario ekstrim:
* Pengguna mengirimkan prompt berukuran 100k token secara mendadak.
* Beberapa pengguna menuntut waktu respons *Inter-Token Latency* (ITL) $< 25\text{ ms}$ untuk token-token decode interaktif.
* Operasi prefill 100k token mengunci GPU (*head-of-line blocking*), menyebabkan request pengguna lain yang sedang decode mengalami lonjakan latensi (ITL melonjak ke 5 detik).
* VRAM GPU tidak dapat menampung lebih dari 3 request berukuran 128k secara bersamaan dalam FP16.

### Sasaran Tantangan
Rancang blueprint arsitektur sistem inferensi yang komprehensif tanpa mengubah bobot dasar model:
1. **Mekanisme Scheduling:** Formulasikan desain *Chunked Prefill* dan integrasikan dengan siklus *Continuous Batching*. Bagaimana formula ukuran chunk yang optimal untuk menyeimbangkan saturasi GEMM GPU tanpa melanggar budget latensi decode?
2. **Hirarki Penyimpanan Memori KV Cache (Tiered Storage):** Rancang arsitektur pemindahan KV Cache non-aktif dari HBM GPU ke Host CPU RAM (atau NVMe SSD) menggunakan CUDA Asynchronous Streams. Kapan paging-out dipicu, dan bagaimana alur pre-fetching blok fisik kembali ke HBM sebelum sequence terkait dijadwalkan ulang untuk decode?
3. **Kompresi Selektif:** Rancang strategi hybrid yang menggabungkan FP8/INT4 Quantization dengan *Context Eviction* dinamis (seperti StreamingLLM / Attention Sink) untuk token-token di tengah sequence tanpa merusak koherensi penalaran model.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (5 Pertanyaan)
1. **Mengapa fase Decode pada LLM autoregressive bersifat memory-bandwidth-bound, bukan compute-bound?**
2. **Berapa byte memori yang dikonsumsi oleh satu token KV Cache pada model dengan konfigurasi: 40 layer, 32 KV heads, head dimension 128, dalam presisi FP16?**
3. **Jelaskan perbedaan mendasar antara Grouped-Query Attention (GQA) dan Multi-Head Attention (MHA) dalam konteks penghematan konsumsi KV Cache!**
4. **Apa yang dimaksud dengan fragmentasi internal pada alokasi KV Cache konvensional?**
5. **Mengapa nilai Key dan Value masa lalu perlu disimpan di cache, sedangkan Query tidak perlu di-cache?**

### Bagian 2: Intermediate (5 Pertanyaan)
6. **Pada PagedAttention, apa fungsi dari Block Table dan di mana struktur data ini idealnya dipelihara saat inferensi berkecepatan tinggi?**
7. **Bagaimana mekanisme *Copy-on-Write* (CoW) menghemat VRAM secara drastis pada implementasi sampling paralel (*Beam Search* atau *multiple completions*)?**
8. **Mengapa penambahan batch size pada fase decode dapat meningkatkan *throughput* keseluruhan token/detik pada GPU?**
9. **Apa risiko arsitektural dan degradasi numerik yang dihadapi ketika melakukan kuantisasi KV Cache dari FP16 menjadi INT4, dan bagaimana cara memitigasinya?**
10. **Jelaskan fenomena *Head-of-Line Blocking* pada inferensi LLM dan bagaimana teknik *Chunked Prefill* menyelesaikannya!**

### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan)

11. **Skenario A:** Engine LLM Anda melayani permintaan customer service. VRAM GPU dilaporkan 99% penuh, namun utilisasi GPU Core (*SM Compute Throughput*) hanya 15%. Di saat yang sama, latensi inter-token sangat tinggi. Apa yang sedang terjadi pada hardware Anda, dan langkah perbaikan apa yang harus Anda lakukan?
12. **Skenario B:** Kluster produksi Anda menggunakan PagedAttention. Suatu hari, sistem mengalami *silent crash* dengan log `CUDA error: an illegal memory access was encountered` sesaat setelah sequence mencapai panjang token ke-4096. Seluruh sequence di bawah 4096 berjalan normal. Di mana letak potensi bug pada implementasi Block Manager Anda?
13. **Skenario C:** Anda memiliki budget VRAM tersisa sebesar 24 GB pada sebuah GPU untuk dialokasikan ke pool KV Cache PagedAttention. Model menggunakan GQA dengan konsumsi KV Cache sebesar $64 \text{ KB/token}$. Jika ukuran blok yang dipilih adalah 32 token, berapa jumlah blok fisik maksimal yang dapat diinisialisasi dalam pool memori tersebut?

---

## 16. Summary

```
+-----------------------------------------------------------------------------------------+
|                    KUNCI ARSITEKTUR KOMPUTASI & KV CACHE                                |
+-----------------------------------------------------------------------------------------+
| 1. Dualitas Inferensi  : Prefill = Compute-Bound (GEMM, Paralel, Saturasi Flops)        |
|                         Decode  = Memory-Bound (GEMV, Autoregressive, Saturasi HBM Bandwidth)
|                                                                                         |
| 2. Bottleneck Hardware : Decode terkunci oleh kecepatan transfer data HBM ke SRAM.       |
|                         Kenaikan throughput decode mutlak memerlukan batching konkurensi|
|                         yang tinggi.                                                    |
|                                                                                         |
| 3. Eliminasi Waste     : Alokasi statis kontigu membuang 60-80% VRAM akibat fragmentasi. |
|                         PagedAttention memecah KV Cache menjadi blok-blok diskrit virtual|
|                         memungkinkan pemanfaatan memori riil mendekati 100%.            |
|                                                                                         |
| 4. Optimasi Skala Besar: Skalabilitas enterprise memerlukan kombinasi:                 |
|                         - Paged Memory Management (Zero-fragmentation)                  |
|                         - Prefix Caching (Zero-duplication)                             |
|                         - GQA & FP8 Quantization (Reduksi footprint)                     |
|                         - Chunked Prefill (Pencegahan Head-of-line blocking)            |
+-----------------------------------------------------------------------------------------+
```

Melalui pemahaman mendalam tentang dinamika komputasi dan memori KV Cache ini, seorang *Inference Engineer* dapat merancang sistem penyajian model skala masif yang stabil, efisien secara biaya hardware, dan sanggup mempertahankan latensi ultra-rendah di bawah beban konkurensi enterprise.