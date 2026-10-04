# Bab 02: Transformer Computation & KV-Cache Dynamics (Module 01)

## 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
*   **Menganalisis Karakteristik Komputasi Prefill vs. Decode**: Mengidentifikasi transisi sistem dari *compute-bound* (GEMM) pada fase *prefill* ke *memory-bandwidth-bound* (GEMV) pada fase *decode* menggunakan analisis *Roofline Model*.
*   **Menghitung Profil Memori KV-Cache Secara Presisi**: Menghitung alokasi memori runtime KV-cache per token, per layer, dan per *request* untuk arsitektur Multi-Head Attention (MHA), Multi-Query Attention (MQA), dan Grouped-Query Attention (GQA) pada berbagai presisi data (FP16, BF16, FP8).
*   **Merancang dan Mengimplementasikan Static/Dynamic Cache Buffer**: Mengembangkan mekanisme manajemen buffer KV-cache dengan PyTorch yang mengeliminasi fragmentasi memori, menangani alokasi statis, dan memitigasi *GPU memory allocation overhead* selama inferensi autoregresif.
*   **Mendiagnosis Failure Mode Memori Inferensi**: Mengidentifikasi, mengisolasi, dan memulihkan sistem dari *Out-of-Memory (OOM)* akibat ledakan konteks (*context explosion*), fragmentasi *virtual memory* CUDA, dan inefisiensi *batching*.

---

## 2. Concept Overview

Inferensi *Large Language Model* (LLM) berbasis decoder-only Transformer memiliki sifat eksekusi dual-fase: **Fase Prefill (Prompt Processing)** dan **Fase Decode (Token Generation)**.

```
+-----------------------------------------------------------------------------+
|                               ROOFLINE MODEL                                |
|  Attainable                                                                 |
|  Performance  ^                     Peak Compute Performance (TFLOPs)       |
|  (FLOP/s)     |                             +---------------------------    |
|               |                            /                                |
|               |                           /  <- Compute-Bound (Prefill)     |
|               |                          /                                  |
|               |                         /                                   |
|               |                        /                                    |
|               |  Memory-Bound         /                                     |
|               |  (Decode) ->         /                                      |
|               |              +------+                                       |
|               |             /                                               |
|               |            /  Slope = Peak Memory Bandwidth (GB/s)          |
|               |           /                                                 |
|               +----------+-------------------------------------------->     |
|                          Operational Intensity (FLOPs/Byte)                 |
+-----------------------------------------------------------------------------+
```

### Mental Model: Dynamic State Retention
Pada fase prefill, model memproses seluruh prompt input $N$ secara paralel. Operasi matriks utama didominasi oleh perkalian matriks-matriks besar ($Q \times K^T$ dan $\text{Attention} \times V$), yang memiliki *arithmetic intensity* (rasio FLOP terhadap byte yang ditransfer dari HBM) yang tinggi. Operasi ini menempati zona **Compute-Bound** pada *Roofline Model*.

Sebaliknya, fase decode bersifat autoregresif: menghasilkan satu token $t_{n+1}$ berdasarkan token sebelumnya $t_{1:n}$. Tanpa optimasi, layer attention harus menghitung ulang representasi key ($K$) dan value ($V$) untuk seluruh token $t_{1:n}$ pada setiap langkah generasi. Hal ini menyebabkan komputasi kuadratik $O(N^2)$ yang redundan.

**Key-Value (KV) Caching** menyimpan tensor representasi $K$ dan $V$ dari token-token sebelumnya di High-Bandwidth Memory (HBM) GPU. Dengan demikian, pada step $t_{n+1}$, model hanya menghitung proyeksi $Q_{n+1}, K_{n+1}, V_{n+1}$ untuk token baru tersebut, menggabungkan $K_{n+1}$ dan $V_{n+1}$ ke dalam cache, lalu menjalankan *scaled dot-product attention* antara vektor query tunggal $Q_{n+1}$ dengan seluruh matriks $K_{\le n+1}$ dan $V_{\le n+1}$.

Dampaknya, komputasi decode bertransisi menjadi perkalian matriks-vektor (GEMV). *Operational intensity* anjlok drastis ke level di mana GPU menghabiskan sebagian besar siklus clock-nya untuk menunggu transfer bobot model dan KV-cache dari DRAM/HBM ke *SRAM (Registers/Shared Memory)*. Fase ini sepenuhnya berada di zona **Memory-Bandwidth-Bound**.

---

## 3. Why It Matters

Dalam skala enterprise, performa serving model dipatok pada metrik:
1. **Time-To-First-Token (TTFT)**: Ditentukan oleh kecepatan fase *prefill*.
2. **Time-Per-Output-Token (TPOT)** atau *Inter-Token Latency (ITL)*: Ditentukan oleh fase *decode*.
3. **Serving Concurrency & Throughput**: Berapa banyak stream concurrent request yang dapat dilayani satu node GPU tanpa mengalami OOM.

KV-cache menjadi bottleneck utama kapasitas serving:
*   **Konsumsi Memori Skala Eksponensial**: Untuk model Llama-3-70B (GQA: 8 KV heads, head dimension 128, 80 layers), pada presisi FP16 (2 byte per elemen), KV-cache membutuhkan:
    $$\text{Ukuran per token} = 2 \times 80 \times 8 \times 128 \times 2 \text{ byte} = 327.680 \text{ byte} \approx 320 \text{ KB/token}$$
    Jika melayani konteks 8.192 token untuk 32 concurrent requests, KV-cache membutuhkan:
    $$32 \times 8.192 \times 320 \text{ KB} \approx 80 \text{ GB}$$
    Artinya, **seluruh memori satu GPU NVIDIA H100 (80GB) habis hanya untuk menyimpan KV-cache**, belum termasuk 140 GB yang dibutuhkan untuk bobot model FP16 itu sendiri.
*   **Memory Fragmentation**: Tanpa sistem manajemen alokasi yang deterministik, alokasi memori dinamis PyTorch (`cudaMalloc`) menyebabkan fragmentasi virtual memory yang masif, memicu error OOM semu meski *free physical memory* masih tersedia.

---

## 4. Arsitektur & Diagram Komponen

Diagram berikut membedah aliran data komputasi prefill, pembaruan cache, dan perulangan auto-regresif decode:

```
[ INPUT PROMPT: T_1 ... T_N ]
            |
            v  (Fase Prefill: Compute-Bound GEMM)
+-------------------------------------------------------------------------------+
| Layer Transformer l (0 <= l < L)                                             |
|                                                                               |
|  X_prefill in R^(Batch x SeqLen x HiddenDim)                                  |
|         |                                                                     |
|         +---> [ W_q ] ---> Q in R^(Batch x SeqLen x (H_q * D))                |
|         |                                                                     |
|         +---> [ W_k ] ---> K_new in R^(Batch x SeqLen x (H_kv * D)) --+       |
|         |                                                             |       |
|         +---> [ W_v ] ---> V_new in R^(Batch x SeqLen x (H_kv * D)) --|-+     |
|                                                                       | |     |
+-----------------------------------------------------------------------|-|-----+
                                                                        | |
                                       WRITE KE GPU HBM (KV-CACHE)     | |
                                       +--------------------------------+ |
                                       |                                  |
                                       v                                  v
+-------------------------------------------------------------------------------+
| KV-CACHE BUFFER LAYER l (Pre-allocated in DRAM/HBM)                           |
|                                                                               |
| K_Cache: [Batch, H_kv, MaxSeqLen, D]  <-- Injeksi K_new pada indeks [0 : N]   |
| V_Cache: [Batch, H_kv, MaxSeqLen, D]  <-- Injeksi V_new pada indeks [0 : N]   |
+-------------------------------------------------------------------------------+
                                       |                  |
                                       | BACA SELURUH     | BACA SELURUH
                                       | HISTORI K        | HISTORI V
                                       v                  v
+-------------------------------------------------------------------------------+
| Fase Decode (Token Generation t = N + 1): Memory-Bound GEMV                   |
|                                                                               |
| Input: Token t_N                                                              |
| Q_(N+1) = x_(N+1) * W_q        -> Shape: [Batch, H_q, 1, D]                   |
| K_(N+1) = x_(N+1) * W_k        -> Append to K_Cache at index N+1              |
| V_(N+1) = x_(N+1) * W_v        -> Append to V_Cache at index N+1              |
|                                                                               |
| Attention Computation:                                                        |
|   Scores = (Q_(N+1) * (K_Cache[:, :, 0:N+1, :])^T) / sqrt(D)                  |
|   Shape Scores: [Batch, H_q, 1, N+1]                                          |
|                                                                               |
|   Attn_Probs = Softmax(Scores, dim=-1)                                        |
|   Context = Attn_Probs * V_Cache[:, :, 0:N+1, :]                              |
|   Shape Context: [Batch, H_q, 1, D]                                           |
|                                                                               |
| Output Projection & Sampling -> Output Token t_(N+1)                          |
+-------------------------------------------------------------------------------+
                                |
                                +--- Loop hingga batas EOS atau Max Sequence ---+
```

---

## 5. Deep Dive Mekanisme & Prinsip Kerja

### 5.1 Perhitungan Matematika KV-Cache Footprint
Kebutuhan memori untuk KV-cache murni ditentukan oleh arsitektur model dan parameter generasi.

Variabel:
*   $b$: *Batch size* (jumlah sequence paralel)
*   $s$: *Sequence length* total (prompt length + generated output tokens)
*   $l$: *Number of layers*
*   $h_{kv}$: *Number of Key/Value heads*
*   $d_h$: *Head dimension* (biasanya $d_{\text{model}} / h_q$)
*   $P_{\text{bytes}}$: Presisi data dalam byte (FP32 = 4, FP16/BF16 = 2, FP8 = 1, INT4 = 0.5)

Formula memori total KV-Cache:
$$\text{Memory}_{\text{KV}} = 2 \times b \times s \times l \times h_{kv} \times d_h \times P_{\text{bytes}}$$

Faktor $2$ di depan merepresentasikan dua tensor independen: satu untuk Key dan satu untuk Value.

#### Komparasi Arsitektur Attention
1.  **Multi-Head Attention (MHA)**:
    $h_{kv} = h_q$. Setiap query head memiliki key dan value head khusus. Konsumsi memori KV-cache berada pada level maksimal.
2.  **Multi-Query Attention (MQA)**:
    $h_{kv} = 1$. Seluruh query head berbagi satu pasangan key dan value head yang sama. Pengurangan ukuran KV-cache sebesar faktor $h_q$ (bisa mencapai 32x hingga 64x lebih hemat).
3.  **Grouped-Query Attention (GQA)**:
    $1 < h_{kv} < h_q$, di mana $h_q$ dibagi ke dalam beberapa grup yang masing-masing terdiri dari $g = h_q / h_{kv}$ heads. Menawarkan trade-off optimal antara kapasitas representasi MHA dan efisiensi throughput MQA.

| Model | $l$ | $h_q$ | $h_{kv}$ | $d_h$ | Precision | KV-Cache per Token ($b=1$) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Llama-2-7B** (MHA) | 32 | 32 | 32 | 128 | FP16 (2B) | $2 \times 32 \times 32 \times 128 \times 2 = 524.288 \text{ B} \approx 512 \text{ KB}$ |
| **Llama-3-8B** (GQA) | 32 | 32 | 8 | 128 | FP16 (2B) | $2 \times 32 \times 8 \times 128 \times 2 = 131.072 \text{ B} \approx 128 \text{ KB}$ |
| **Llama-3-70B** (GQA) | 80 | 64 | 8 | 128 | FP16 (2B) | $2 \times 80 \times 8 \times 128 \times 2 = 327.680 \text{ B} \approx 320 \text{ KB}$ |

### 5.2 Transisi FLOPs dan Analisis Bandwidth
Pada fase prefill dengan panjang prompt $N$:
*   Operasi Attention QK: Matriks $[b, h, N, d_h] \times [b, h, d_h, N] \to 2 \cdot b \cdot h \cdot N^2 \cdot d_h$ FLOPs.
*   Arithmetic Intensity tinggi: Membaca bobot projection layer satu kali dari memory, menggunakannya untuk $N$ token.

Pada fase decode untuk sequence yang berada di step $N$:
*   Operasi Attention QK: Matriks $[b, h, 1, d_h] \times [b, h, d_h, N] \to 2 \cdot b \cdot h \cdot 1 \cdot N \cdot d_h$ FLOPs.
*   Model harus membaca seluruh $K_{0:N}$ dan $V_{0:N}$ dari GPU HBM ke Shared Memory hanya untuk satu perkalian dot product dengan vektor query token baru.
*   Memory Traffic per step decode:
    $$\text{Traffic} = \text{Model Weights (Bytes)} + \text{KV-Cache Context (Bytes)}$$
    Karena komputasi FLOPs yang dilakukan per step sangat rendah dibanding volume data yang harus ditransfer, *execution time* per token decode dibatasi oleh spesifikasi **GPU Memory Bandwidth** (misal: 2.0 TB/s pada NVIDIA A100-SXM4-80GB, atau 3.35 TB/s pada H100 SXM5).

---

## 6. Production-Ready Code Implementation

Berikut adalah implementasi level produksi dari Layer Attention berkinerja tinggi yang mendukung **Grouped-Query Attention (GQA)** dengan **Pre-allocated Static KV-Cache Buffer** untuk mengeliminasi alokasi dinamis saat runtime inferensi.

```python
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Optional, Tuple


class StaticKVCache:
    """
    Pre-allocated tensor memory buffer untuk Key dan Value Cache.
    Menghindari degradasi performa akibat memory fragmentation dan dynamic cudaMalloc.
    """
    def __init__(
        self,
        max_batch_size: int,
        max_seq_len: int,
        num_kv_heads: int,
        head_dim: int,
        dtype: torch.dtype = torch.float16,
        device: str = "cuda"
    ):
        self.max_batch_size = max_batch_size
        self.max_seq_len = max_seq_len
        self.num_kv_heads = num_kv_heads
        self.head_dim = head_dim
        self.dtype = dtype
        self.device = device

        # Pre-alokasi tensor buffer contiguous di memori GPU
        # Shape: [Batch, Heads, MaxSeqLen, HeadDim]
        self.k_buffer = torch.zeros(
            (max_batch_size, num_kv_heads, max_seq_len, head_dim),
            dtype=dtype,
            device=device
        )
        self.v_buffer = torch.zeros(
            (max_batch_size, num_kv_heads, max_seq_len, head_dim),
            dtype=dtype,
            device=device
        )

    def update(
        self,
        key_states: torch.Tensor,
        value_states: torch.Tensor,
        batch_indices: torch.Tensor,
        start_pos: int,
        seq_len: int
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Melakukan inplace write ke buffer KV-Cache.
        
        Args:
            key_states: [batch_size, num_kv_heads, seq_len, head_dim]
            value_states: [batch_size, num_kv_heads, seq_len, head_dim]
            batch_indices: Tensor indeks batch aktif
            start_pos: Indeks posisi sekuens awal
            seq_len: Panjang sekuens yang dimasukkan
            
        Returns:
            Tuple slice tensor [k_cached, v_cached] hingga posisi start_pos + seq_len
        """
        end_pos = start_pos + seq_len
        if end_pos > self.max_seq_len:
            raise ValueError(
                f"Konteks melebihi kapasitas buffer: end_pos={end_pos} > max_seq_len={self.max_seq_len}"
            )

        # Operasi in-place tensor scattering menghindari alokasi baru
        self.k_buffer[batch_indices, :, start_pos:end_pos, :] = key_states
        self.v_buffer[batch_indices, :, start_pos:end_pos, :] = value_states

        # Kembalikan view aktif dari cache hingga token terbaru
        k_out = self.k_buffer[batch_indices, :, :end_pos, :]
        v_out = self.v_buffer[batch_indices, :, :end_pos, :]
        return k_out, v_out

    def reset(self, batch_index: Optional[int] = None):
        """Reset memori cache jika request selesai."""
        if batch_index is None:
            self.k_buffer.zero_()
            self.v_buffer.zero_()
        else:
            self.k_buffer[batch_index].zero_()
            self.v_buffer[batch_index].zero_()


class ProductionGQAttention(nn.Module):
    """
    Multi-Head / Grouped-Query Attention Layer dengan integrasi Static KV-Cache.
    """
    def __init__(
        self,
        dim: int,
        num_heads: int,
        num_kv_heads: int,
        max_batch_size: int,
        max_seq_len: int,
        dtype: torch.dtype = torch.float16
    ):
        super().__init__()
        self.dim = dim
        self.num_heads = num_heads
        self.num_kv_heads = num_kv_heads
        self.num_queries_per_kv = num_heads // num_kv_heads
        self.head_dim = dim // num_heads

        assert dim % num_heads == 0, "dim harus habis dibagi num_heads"
        assert num_heads % num_kv_heads == 0, "num_heads harus kelipatan genap dari num_kv_heads"

        # Linear projections
        self.q_proj = nn.Linear(dim, num_heads * self.head_dim, bias=False, dtype=dtype)
        self.k_proj = nn.Linear(dim, num_kv_heads * self.head_dim, bias=False, dtype=dtype)
        self.v_proj = nn.Linear(dim, num_kv_heads * self.head_dim, bias=False, dtype=dtype)
        self.out_proj = nn.Linear(num_heads * self.head_dim, dim, bias=False, dtype=dtype)

        self.scale = 1.0 / (self.head_dim ** 0.5)

        # Inisialisasi Cache
        # Pada setup enterprise, cache seringkali diinjeksi via context manager atau state dictionary
        self.cache: Optional[StaticKVCache] = None
        self.max_batch_size = max_batch_size
        self.max_seq_len = max_seq_len
        self.dtype = dtype

    def allocate_cache(self, device: str):
        self.cache = StaticKVCache(
            max_batch_size=self.max_batch_size,
            max_seq_len=self.max_seq_len,
            num_kv_heads=self.num_kv_heads,
            head_dim=self.head_dim,
            dtype=self.dtype,
            device=device
        )

    def forward(
        self,
        x: torch.Tensor,
        start_pos: int,
        mask: Optional[torch.Tensor] = None
    ) -> torch.Tensor:
        """
        Forward step yang transparan untuk fase Prefill maupun Decode.
        
        Args:
            x: [Batch, CurrentSeqLen, Dim]
            start_pos: Titik awal indeks penulisan token (0 jika prefill)
            mask: Attention mask opsional (wajib kausal untuk prefill)
        """
        batch_size, seq_len, _ = x.shape

        if self.cache is None:
            self.allocate_cache(device=str(x.device))

        # 1. Proyeksi Q, K, V
        q = self.q_proj(x)
        k = self.k_proj(x)
        v = self.v_proj(x)

        # 2. Reshape ke format multi-head
        # Q: [B, H_q, S, D]
        q = q.view(batch_size, seq_len, self.num_heads, self.head_dim).transpose(1, 2)
        # K, V: [B, H_kv, S, D]
        k = k.view(batch_size, seq_len, self.num_kv_heads, self.head_dim).transpose(1, 2)
        v = v.view(batch_size, seq_len, self.num_kv_heads, self.head_dim).transpose(1, 2)

        # 3. Update dan fetch dari Static Cache
        batch_indices = torch.arange(batch_size, device=x.device)
        k_cached, v_cached = self.cache.update(
            key_states=k,
            value_states=v,
            batch_indices=batch_indices,
            start_pos=start_pos,
            seq_len=seq_len
        )

        # 4. GQA Expansion: Broadcast Key & Value ke jumlah Head Query
        # Repeat interleave hanya jika konfigurasi adalah GQA/MQA (H_kv < H_q)
        if self.num_queries_per_kv > 1:
            k_cached = torch.repeat_interleave(k_cached, repeats=self.num_queries_per_kv, dim=1)
            v_cached = torch.repeat_interleave(v_cached, repeats=self.num_queries_per_kv, dim=1)

        # 5. Scaled Dot-Product Attention (SDPA)
        # Gunakan PyTorch FlashAttention / Memory-Efficient backend jika memungkinkan via F.scaled_dot_product_attention
        # scores: [B, H_q, S, Total_Seq_Len]
        if hasattr(F, 'scaled_dot_product_attention') and mask is None and seq_len == 1:
            # Decode step: single query token against historical context
            output = F.scaled_dot_product_attention(
                q, k_cached, v_cached, attn_mask=None, is_causal=False
            )
        else:
            # Prefill step atau custom masking logic
            scores = torch.matmul(q, k_cached.transpose(-2, -1)) * self.scale
            if mask is not None:
                scores = scores + mask
            attn_weights = F.softmax(scores, dim=-1, dtype=torch.float32).to(q.dtype)
            output = torch.matmul(attn_weights, v_cached)

        # 6. Reshape kembali ke representasi linier
        # Output: [B, S, H_q * D] -> [B, S, Dim]
        output = output.transpose(1, 2).contiguous().view(batch_size, seq_len, -1)
        return self.out_proj(output)


# =====================================================================
# Verification Script (Validasi Prefill & Auto-regressive Generation)
# =====================================================================
if __name__ == "__main__":
    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32

    batch_size = 2
    max_context = 128
    dim = 256
    num_heads = 8
    num_kv_heads = 2  # Grouped Query Attention (1 KV head untuk tiap 4 Query heads)

    attn = ProductionGQAttention(
        dim=dim,
        num_heads=num_heads,
        num_kv_heads=num_kv_heads,
        max_batch_size=batch_size,
        max_seq_len=max_context,
        dtype=dtype
    ).to(device)

    # --- Phase 1: Prefill Step (Prompt Context = 10 Tokens) ---
    prompt_len = 10
    prompt_tokens = torch.randn(batch_size, prompt_len, dim, device=device, dtype=dtype)
    
    # Causal mask sederhana untuk prefill
    causal_mask = torch.triu(torch.full((prompt_len, prompt_len), float('-inf'), device=device), diagonal=1)

    print("[Step 1] Running Prefill Phase...")
    prefill_out = attn(prompt_tokens, start_pos=0, mask=causal_mask)
    print(f"Prefill Output Shape: {prefill_out.shape} -> Expected: [{batch_size}, {prompt_len}, {dim}]")
    assert prefill_out.shape == (batch_size, prompt_len, dim)

    # --- Phase 2: Decode Step (Auto-regressive loop: 3 new tokens) ---
    print("\n[Step 2] Running Autoregressive Decode Phase...")
    current_pos = prompt_len
    generated_tokens = []

    for step in range(3):
        # Setiap token berikutnya di-generate secara individual: SeqLen = 1
        next_token = torch.randn(batch_size, 1, dim, device=device, dtype=dtype)
        decode_out = attn(next_token, start_pos=current_pos, mask=None)
        
        print(f"Decode Step {step+1} (Token Index {current_pos}) Output Shape: {decode_out.shape}")
        assert decode_out.shape == (batch_size, 1, dim)
        
        current_pos += 1

    print("\nKV-Cache State:")
    print(f"Active Cached Keys Slice Shape: {attn.cache.k_buffer[:, :, :current_pos, :].shape}")
    print("Eksekusi berhasil tanpa pelanggaran alokasi dinamis.")
```

---

## 7. Edge Cases & Failure Modes

### 1. Fragmentation & OOM saat Dynamic Allocation
*   *Mekanisme Kegagalan*: Menggunakan `torch.cat([cache, new_kv], dim=-2)` pada setiap decode step memaksa CUDA memory allocator mengalokasikan tensor baru berukuran $(N+1)$ dan mendealokasikan tensor lama berukuran $N$. Hal ini menyebabkan *severe heap fragmentation*. Ketika fragmentasi memuncak, `cudaMalloc` gagal menemukan blok contiguous baru yang cukup besar, berujung pada status `RuntimeError: CUDA out of memory`.
*   *Mitigasi*: Selalu pre-alokasikan memori maksimum buffer di awal (*Static KV-Cache*) atau adopsi algoritma paging memori non-contiguous (*PagedAttention*).

### 2. Context Window Overrun (Silent Corruption vs. Panics)
*   *Mekanisme Kegagalan*: Request mengirimkan total panjang token (prompt + generation) yang melampaui `max_seq_len`.
*   *Mitigasi*:
    ```python
    if start_pos + seq_len > self.max_seq_len:
        # Jangan izinkan silent overwrite yang merusak representasi token masa lalu
        raise ContextWindowExceededException(
            f"Batas konteks tercapai ({start_pos + seq_len} > {self.max_seq_len}). "
            "Picukan eviction strategy atau hentikan generasi."
        )
    ```

### 3. Asymmetric Sequence Lengths pada Dynamic Batching
*   *Mekanisme Kegagalan*: Dalam batch berukuran $B$, Sequence 1 selesai pada token ke-50, sementara Sequence 2 butuh 500 token.
*   *Mitigasi*: Buffer cache harus dilacak per request menggunakan slot allocator array (`req_to_token_indices`). Request yang telah selesai harus segera di-*evict* atau dibersihkan dari index register agar slot tersebut dapat langsung direklamasi oleh incoming request tanpa menunggu siklus batch lain selesai (*In-flight / Continuous Batching*).

---

## 8. Trade-offs & Alternatif Solusi

| Pendekatan | Latency Impact | Throughput Impact | Memory Overhead | Kompleksitas Implementasi | Kasus Penggunaan Ideal |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **No-Cache (Hitung Ulang Tiap Step)** | Katastropik ($O(N^2)$ FLOPs) | Sangat Rendah | Minimal (Hanya bobot layer) | Sangat Rendah | Edge device tanpa RAM; sama sekali dihindari di datacenter. |
| **Static Tensor KV-Cache (MHA)** | Sangat Rendah | Rendah (Batch size terbatas) | Maksimal ($2 \times B \times S \times L \times H \times D$) | Rendah | Model berukuran kecil (<3B parameter) atau batch size statis rendah. |
| **Static KV-Cache (GQA/MQA)** | Sangat Rendah | Tinggi (Bisa tampung 4-8x batch) | Sedang hingga Rendah | Sedang | Standard industri modern (Llama-3, Mistral, Qwen). |
| **PagedAttention (vLLM style)** | Rendah (Overhead lookup block) | Sangat Tinggi (Mendekati nol internal fragmentation) | Nyaris Optimal (Hanya sisa slot dalam blok terakhir) | Sangat Tinggi | Enterprise Multi-Tenant LLM Serving Engines. |
| **Sliding Window / StreamingLLM** | Rendah & Konstan | Sangat Tinggi | Dibatasi oleh window $W$ ($O(W)$ footprint) | Tinggi | Task streaming tanpa batas (*infinite chat/agentic loop*), trade-off hilangnya long-range attention. |

---

## 9. Best Practices & Standar Industri

1.  **Pemisahan Presisi (KV-Cache Quantization)**:
    Implementasikan kompresi FP8 (E4M3 atau E5M2) atau INT8 pada KV-Cache. Bobot model dapat dipertahankan pada BF16 untuk akurasi reasoning, namun KV-cache di-kuantisasi saat penulisan ke buffer. Langkah ini memangkas konsumsi bandwidth memori decode sebesar 50% tanpa penurunan akurasi yang signifikan.
2.  **Prefill-Decode Decoupling (Split Architecture)**:
    Pada arsitektur inference modern tier-1, jangan jalankan prefill dan decode pada node GPU yang sama:
    *   *Prefill Worker Node*: Menggunakan node dengan compute TFLOPs tinggi untuk melahap token prompt besar.
    *   *Decode Worker Node*: Dioptimalkan untuk memori bandwidth tinggi. KV-cache dikirimkan melalui transmisi jaringan berkecepatan tinggi (RDMA / RoCE over NVLink) dari Prefill node ke Decode node.
3.  **Contiguous Indexing Over Masking**:
    Hindari padding token berlebihan pada batch inference. Terapkan strategi *packed sequence* (flattening array token dengan penunjuk offset pointer seperti layout cuDNN/FlashAttention) daripada melakukan alokasi zero-padding yang memboroskan memori KV-cache pada prompt pendek.

---

## 10. Hands-on Lab Exercise

### Misi
Tulis skrip analisis profil memori GPU aktual untuk memverifikasi konsumsi teoritis KV-cache vs. konsumsi alokasi real CUDA pada arsitektur Llama-3-8B style.

### Langkah-Langkah

1.  **Siapkan Environment**:
    Pastikan environment memiliki akses GPU CUDA (misal via Google Colab atau server lokal dengan GPU NVIDIA).
    ```bash
    pip install torch --extra-index-url https://download.pytorch.org/whl/cu121
    ```

2.  **Buat File Script Benchmark (`kv_cache_benchmark.py`)**:

```python
import torch
import gc

def print_gpu_memory(label: str):
    torch.cuda.synchronize()
    allocated = torch.cuda.memory_allocated() / (1024 ** 2)
    reserved = torch.cuda.memory_reserved() / (1024 ** 2)
    print(f"[{label}] Allocated: {allocated:.2f} MB | Reserved: {reserved:.2f} MB")

def run_cache_benchmark():
    if not torch.cuda.is_available():
        print("Test ini membutuhkan GPU CUDA.")
        return

    # Spesifikasi menyerupai Llama-3-8B layer attention
    num_layers = 32
    num_kv_heads = 8
    head_dim = 128
    batch_size = 4
    seq_len = 4096
    dtype = torch.float16  # 2 bytes
    element_size = 2

    # Bersihkan memori awal
    gc.collect()
    torch.cuda.empty_cache()
    print_gpu_memory("Baseline (Kosong)")

    # 1. Hitung Teori
    # Rumus: 2 * B * S * L * H_kv * D * Bytes
    bytes_per_token_all_layers = 2 * num_layers * num_kv_heads * head_dim * element_size
    theoretical_total_bytes = batch_size * seq_len * bytes_per_token_all_layers
    theoretical_total_mb = theoretical_total_bytes / (1024 ** 2)

    print(f"\n--- Spesifikasi Kalkulasi ---")
    print(f"Per Token Footprint (All Layers): {bytes_per_token_all_layers / 1024:.2f} KB")
    print(f"Total Theoretical Footprint ({batch_size=}, {seq_len=}): {theoretical_total_mb:.2f} MB\n")

    # 2. Alokasikan KV-Cache Eksplisit untuk Seluruh Layer
    print_gpu_memory("Sebelum Alokasi KV Cache")
    
    # List untuk menahan referensi buffer agar tidak di-garbage collect
    kv_buffers = []
    
    for l in range(num_layers):
        # K buffer
        k = torch.zeros(
            (batch_size, num_kv_heads, seq_len, head_dim),
            dtype=dtype,
            device="cuda"
        )
        # V buffer
        v = torch.zeros(
            (batch_size, num_kv_heads, seq_len, head_dim),
            dtype=dtype,
            device="cuda"
        )
        kv_buffers.append((k, v))

    print_gpu_memory("Setelah Alokasi KV Cache Penuh")

    # 3. Validasi
    actual_allocated_mb = torch.cuda.memory_allocated() / (1024 ** 2)
    discrepancy = abs(actual_allocated_mb - theoretical_total_mb)
    print(f"\nDelta Real vs Teori: {discrepancy:.4f} MB")
    
    if discrepancy < 1.0:
        print("STATUS: VALIDASI SUKSES - Pengukuran memori runtime identik dengan kalkulasi teori!")
    else:
        print("STATUS: PERINGATAN - Ditemukan overhead memory controller internal CUDA.")

    # 4. Cleanup
    del kv_buffers
    gc.collect()
    torch.cuda.empty_cache()
    print_gpu_memory("Setelah Pembersihan (Cleanup)")

if __name__ == "__main__":
    run_cache_benchmark()
```

3.  **Eksekusi Script**:
    ```bash
    python kv_cache_benchmark.py
    ```

4.  **Ekspektasi Output**:
    Output akan menampilkan:
    *   `Per Token Footprint`: Sekitar 128.00 KB.
    *   `Total Theoretical Footprint`: Tepat 2048.00 MB (2.0 GB).
    *   Alokasi aktual PyTorch akan naik tepat sebesar ~2048 MB, membuktikan kebenaran kalkulasi footprint memori sebelum arsitektur inferensi di-deploy ke production.