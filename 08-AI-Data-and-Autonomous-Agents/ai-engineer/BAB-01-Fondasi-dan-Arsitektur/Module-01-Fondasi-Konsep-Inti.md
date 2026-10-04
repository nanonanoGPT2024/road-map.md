# Bab 01: Fondasi AI Engineering & Arsitektur Model Skala Besar
## Modul 01: Arsitektur Transformer, Komputasi Self-Attention, dan Lifecycle LLM Inference

---

### 1. Title & Metadata
* **Domain:** AI Engineering & Generative AI Infrastructure
* **Module Code:** AIE-01-01
* **Level:** Advanced
* **Prerequisites:** Pemahaman linear algebra (matriks perkalian, eigenvalue, proyeksi), kalkulus multivariat (chain rule, gradient backpropagation), Python 3.11+, PyTorch fundamentals (`torch.Tensor`, autograd, memory allocation).

---

### 2. Learning Objectives
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
1. **Menganalisis** kompleksitas komputasional dan memori dari algoritma *Scaled Dot-Product Attention* secara matematis ($O(N^2)$ time/space complexity).
2. **Mengimplementasikan** modul *Multi-Head Attention* (MHA) berkinerja tinggi lengkap dengan *Key-Value (KV) Cache* manual dari *scratch* menggunakan PyTorch.
3. **Mengidentifikasi** perbedaan mendasar antara fase *Prefill* (compute-bound) dan fase *Decoding* (memory-bandwidth-bound) dalam inferensi Large Language Models (LLM).
4. **Mengevaluasi** jejak alokasi memori runtime (VRAM footprint) berdasarkan konfigurasi batch size, sequence length, dan arsitektur model.
5. **Menerapkan** causal masking numerik yang stabil untuk mencegah *attention leakage* pada autoregressive sequence generation.

---

### 3. Conceptual Foundation
Large Language Models (LLM) modern berbasis arsitektur Transformer Decoder-Only (seperti LLaMA, Mistral, GPT-4) beroperasi berdasarkan mekanisme penentuan probabilitas token berikutnya secara autoregresif:

$$P(w_1, w_2, \dots, w_T) = \prod_{t=1}^T P(w_t \mid w_1, \dots, w_{t-1})$$

Inti komputasi yang memungkinkan pemodelan relasi jarak jauh tanpa bias induktif sekuensial (seperti pada RNN/LSTM) adalah **Scaled Dot-Product Attention**. Diberikan matriks representasi Query ($Q \in \mathbb{R}^{N \times d_k}$), Key ($K \in \mathbb{R}^{M \times d_k}$), dan Value ($V \in \mathbb{R}^{M \times d_v}$), operasinya diformulasikan sebagai:

$$\text{Attention}(Q, K, V) = \text{softmax}\left(\frac{QK^T}{\sqrt{d_k}} + M\right)V$$

Di mana:
* $N$ adalah sequence length untuk Query, dan $M$ adalah sequence length untuk Key/Value.
* $\sqrt{d_k}$ bertindak sebagai scaling factor untuk mencegah dot product bernilai terlalu besar pada dimensi laten tinggi, yang dapat mendorong fungsi softmax ke daerah dengan gradien sangat kecil (*gradient saturation*).
* $M \in \mathbb{R}^{N \times M}$ adalah mask tensor. Untuk model autoregresif, $M_{i,j} = -\infty$ jika $j > i$, dan $0$ jika sebaliknya.

Dalam arsitektur **Multi-Head Attention (MHA)**, proyeksi linier independen diterapkan sebanyak $h$ kali:

$$\text{MHA}(Q, K, V) = \text{Concat}(\text{head}_1, \dots, \text{head}_h)W^O$$
$$\text{head}_i = \text{Attention}(QW_i^Q, KW_i^K, VW_i^V)$$

Di mana $W_i^Q \in \mathbb{R}^{d_{\text{model}} \times d_k}$, $W_i^K \in \mathbb{R}^{d_{\text{model}} \times d_k}$, $W_i^V \in \mathbb{R}^{d_{\text{model}} \times d_v}$, dan $W^O \in \mathbb{R}^{h d_v \times d_{\text{model}}}$.

---

### 4. Why This Matters
Dalam rekayasa sistem AI, memperlakukan LLM sebagai "black box API" menyebabkan kegagalan fatal pada skalabilitas dan biaya. 

Ketika melakukan deployment internal (self-hosting LLM):
1. **Inefisiensi GPU Memory:** Tanpa pemahaman mendalam tentang *KV Cache*, engineer sering mengalami *CUDA Out-of-Memory (OOM)* saat concurrency meningkat.
2. **Karakteristik Komputasi:** Fase *Prefill* (pemrosesan prompt) didominasi oleh operasi General Matrix Multiply (GEMM) yang bersifat **compute-bound**. Sebaliknya, fase *Decoding* (generasi token satu per satu) didominasi oleh operasi General Matrix-Vector (GEMV) yang bersifat **memory-bandwidth bound**.
3. **Bottleneck Optimasi:** Kegagalan membedakan kedua fase ini menyebabkan kesalahan pemilihan hardware (misal: memilih GPU dengan TFLOPS tinggi tetapi memori bandwidth rendah untuk beban decoding interaktif).

---

### 5. What You Are Building
Kita akan membangun komponen inti transformer decoder dari *first principles*:
* Modul `CausalSelfAttentionWithKVCache`: Mengimplementasikan multi-head self-attention dari proyeksi tensor dasar, mendukung causal masking, serta memiliki kemampuan stateful *KV Cache* dinamis untuk inferensi berkecepatan tinggi.
* Test suite verifikasi numerik: Memvalidasi equivalensi output antara inferensi *naive* ($O(N^2)$ per step) versus inferensi teroptimasi *KV Cache* ($O(N)$ per step).

---

### 6. System Architecture & Component Interactions

```
+---------------------------------------------------------------------------------------+
|                              Transformer Decoder Block                                |
|                                                                                       |
|   Input Token IDs: [Batch, SeqLen]                                                    |
|           |                                                                           |
|           v                                                                           |
|   +-----------------------+     +--------------------------+                          |
|   | Token Embedding Matrix| +   | Positional Encoding (RoPE|                          |
|   +-----------------------+     +--------------------------+                          |
|           |                                                                           |
|           v                                                                           |
|   Hidden States: X [B, S, D]                                                          |
|           |                                                                           |
|           +---------------------------+ (Residual Connection)                         |
|           |                           |                                               |
|           v                           |                                               |
|   +-----------------------+           |                                               |
|   | RMSNorm / LayerNorm   |           |                                               |
|   +-----------------------+           |                                               |
|           |                           |                                               |
|           v                           |                                               |
|   +---------------------------------------+                                           |
|   | Multi-Head Attention (MHA)            |                                           |
|   |                                       |                                           |
|   |  +---------+   +---------+  +-------+ |       KV Cache Storage                    |
|   |  | Q-Proj  |   | K-Proj  |  | V-Proj| |    +--------------------+                 |
|   |  +---------+   +---------+  +-------+ |    | Past Keys: [B,H,S,D|                 |
|   |       |             |           |     |    | Past Vals: [B,H,S,D|                 |
|   |       |             +-----> [Update Cache] --->+                    |             |
|   |       |             |           |     |    +--------------------+                 |
|   |       v             v           v     |               |                           |
|   |  [    Attention(Q, K_all, V_all)    ] <---------------+                           |
|   |                     |                 |                                           |
|   |                     v                 |                                           |
|   |               +-----------+           |                                           |
|   |               | Out-Proj  |           |                                           |
|   |               +-----------+           |                                           |
|   +---------------------------------------+                                           |
|           |                           |                                               |
|           v                           |                                               |
|           +<--------------------------+ (Residual Add)                                |
|           |                                                                           |
|           v                                                                           |
|       [To MLP/Feed-Forward Network & Next Layers]                                     |
+---------------------------------------------------------------------------------------+
```

---

### 7. Mechanics & Data Flow

Berikut adalah jejak eksekusi inferensi autoregresif dengan KV Cache untuk token baru $t_n$:

```
Step 1: Input Shape [Batch=1, SeqLen=1, Dim=4096]
              |
              v
Step 2: Projections
        Q_n = Input * W_Q  --> [1, Heads, 1, HeadDim]
        K_n = Input * W_K  --> [1, Heads, 1, HeadDim]
        V_n = Input * W_V  --> [1, Heads, 1, HeadDim]
              |
              v
Step 3: KV Cache Concat
        K_all = torch.cat([K_cache, K_n], dim=2) --> [1, Heads, n, HeadDim]
        V_all = torch.cat([V_cache, V_n], dim=2) --> [1, Heads, n, HeadDim]
              |
              v
Step 4: Scaled Dot-Product
        Scores = (Q_n @ K_all.transpose(-1, -2)) / sqrt(HeadDim)
        Shape: [1, Heads, 1, n]
              |
              v
Step 5: Softmax Over Context (dim=-1)
        Weights = Softmax(Scores, dim=-1) --> [1, Heads, 1, n]
              |
              v
Step 6: Context Aggregation
        Context = Weights @ V_all --> [1, Heads, 1, HeadDim]
              |
              v
Step 7: Final Linear Projection
        Output = Context.view(1, 1, Dim) @ W_O --> [1, 1, Dim]
```

---

### 8. Minimal Conceptual Implementation
Kode konseptual tanpa dependensi kompleks untuk memahami mekanik dasar:

```python
import torch
import math

def simple_attention(q: torch.Tensor, k: torch.Tensor, v: torch.Tensor, mask: torch.Tensor = None) -> torch.Tensor:
    # q, k, v: [Batch, Sequence_Length, Dimension]
    d_k = q.size(-1)
    # Matmul Q & K^T -> [Batch, Seq_Q, Seq_K]
    scores = torch.bmm(q, k.transpose(1, 2)) / math.sqrt(d_k)
    
    if mask is not None:
        scores = scores.masked_fill(mask == 0, -1e9)
        
    weights = torch.softmax(scores, dim=-1)
    # Matmul Weights & V -> [Batch, Seq_Q, Dimension]
    output = torch.bmm(weights, v)
    return output

# Dimensi sederhana: 1 batch, 3 tokens, 4 embedding dims
q = torch.randn(1, 3, 4)
k = torch.randn(1, 3, 4)
v = torch.randn(1, 3, 4)
# Causal Lower-Triangular Mask
causal_mask = torch.tril(torch.ones(1, 3, 3))

out = simple_attention(q, k, v, causal_mask)
print("Attention Shape Output:", out.shape)
```

---

### 9. Edge Cases & Failure Modes

| Failure Mode | Root Cause | Behavioral Impact | Engineering Mitigation |
| :--- | :--- | :--- | :--- |
| **Attention NaN Overflow** | Nilai FP16 melampaui $65504$ sebelum Softmax pada sequence panjang. | Bobot Softmax menjadi `NaN`, seluruh state model rusak. | Gunakan BF16 atau skala pembagi $\sqrt{d_k}$ secara konsisten sebelum dot product; simpan accumulator dalam FP32. |
| **Causal Mask Leaking** | Indeks diagonal masking off-by-one ($j \ge i$ alih-alih $j > i$). | Model dapat membaca token masa depan selama pelatihan, performa inferensi anjlok (*degraded generation*). | Validasi assertion invariant: bobot probabilitas masa depan harus bernilai eksak `0.0`. |
| **KV Cache VRAM Exhaustion** | Alokasi dinamis `torch.cat` berulang kali menyebabkan fragmentasi memori ekstrem pada GPU. | Intermittent OOM bahkan ketika total memory usage terlihat aman. | Alokasikan *pre-allocated buffer memory* menggunakan PagedAttention (standar industri vLLM). |
| **Zero Division Scaler** | Dimensi head ($d_k$) bernilai 0 karena salah parsing arsitektur. | Crash saat inisialisasi. | Sanity check validasi pada inisialisasi `assert head_dim > 0`. |

---

### 10. Production-Grade Implementation

Berikut adalah implementasi `CausalSelfAttentionWithKVCache` berstandar produksi dengan PyTorch. Kode ini menangani multi-head logic, FP16/BF16 stability, dynamic KV updates, causal masking, dan validasi tipe.

```python
import torch
import torch.nn as nn
from typing import Optional, Tuple

class CausalSelfAttentionWithKVCache(nn.Module):
    """
    Multi-Head Attention dengan dukungan KV Cache terintegrasi untuk inferensi berkinerja tinggi.
    Mematuhi konvensi LLM Decoder-Only modern (contoh: LLaMA).
    """
    def __init__(self, d_model: int, num_heads: int, max_seq_len: int = 4096):
        super().__init__()
        if d_model % num_heads != 0:
            raise ValueError(f"d_model ({d_model}) harus habis dibagi num_heads ({num_heads}).")

        self.d_model = d_model
        self.num_heads = num_heads
        self.head_dim = d_model // num_heads
        self.max_seq_len = max_seq_len
        self.scale = 1.0 / (self.head_dim ** 0.5)

        # Proyeksi Linear Gabungan untuk efisiensi komputasi GEMM
        self.q_proj = nn.Linear(d_model, d_model, bias=False)
        self.k_proj = nn.Linear(d_model, d_model, bias=False)
        self.v_proj = nn.Linear(d_model, d_model, bias=False)
        self.out_proj = nn.Linear(d_model, d_model, bias=False)

        # Precompute Causal Mask untuk efisiensi memori (didaftarkan sebagai buffer non-trainable)
        indices = torch.arange(max_seq_len)
        mask = indices.view(-1, 1) >= indices.view(1, -1)
        self.register_buffer("causal_mask", mask.view(1, 1, max_seq_len, max_seq_len), persistent=False)

    def forward(
        self,
        x: torch.Tensor,
        use_cache: bool = False,
        past_key_value: Optional[Tuple[torch.Tensor, torch.Tensor]] = None
    ) -> Tuple[torch.Tensor, Optional[Tuple[torch.Tensor, torch.Tensor]]]:
        """
        Argumen:
            x: Input tensor [batch_size, seq_len, d_model]
            use_cache: Boolean untuk mengaktifkan KV Cache return
            past_key_value: Tuple (cached_k, cached_v) dari step komputasi sebelumnya
                            masing-masing shape: [batch_size, num_heads, past_seq_len, head_dim]

        Return:
            output: Tensor [batch_size, seq_len, d_model]
            present_key_value: Updated KV cache tuple (jika use_cache=True)
        """
        batch_size, seq_len, _ = x.shape

        # 1. Proyeksi Linear & Reshape ke Multi-Head representation
        # [B, S, D] -> [B, S, H, D_h] -> [B, H, S, D_h]
        q = self.q_proj(x).view(batch_size, seq_len, self.num_heads, self.head_dim).transpose(1, 2)
        k = self.k_proj(x).view(batch_size, seq_len, self.num_heads, self.head_dim).transpose(1, 2)
        v = self.v_proj(x).view(batch_size, seq_len, self.num_heads, self.head_dim).transpose(1, 2)

        # 2. KV Cache Concatenation Logic
        if past_key_value is not None:
            cached_k, cached_v = past_key_value
            k = torch.cat([cached_k, k], dim=-2)
            v = torch.cat([cached_v, v], dim=-2)

        current_key_value = (k, v) if use_cache else None
        total_k_len = k.size(-2)

        # 3. Scaled Dot-Product Attention Computation
        # Q @ K^T -> [B, H, S_q, S_k]
        scores = torch.matmul(q, k.transpose(-1, -2)) * self.scale

        # 4. Terapkan Masking Autoregresif
        if seq_len > 1:
            # Prefill Phase: Seluruh sequence diproses sekaligus, perlu mask
            sub_mask = self.causal_mask[:, :, :seq_len, :total_k_len]
            scores = scores.masked_fill(~sub_mask, float("-inf"))
        else:
            # Decoding Phase: Token baru boleh membaca SEMUA token sebelumnya di cache
            pass

        # Softmax dengan precision stability di FP32
        attention_weights = torch.softmax(scores, dim=-1, dtype=torch.float32).to(x.dtype)

        # 5. Output Aggregation: [B, H, S_q, S_k] @ [B, H, S_k, D_h] -> [B, H, S_q, D_h]
        context = torch.matmul(attention_weights, v)

        # Reshape balik: [B, H, S_q, D_h] -> [B, S_q, H, D_h] -> [B, S_q, D]
        context = context.transpose(1, 2).contiguous().view(batch_size, seq_len, self.d_model)

        output = self.out_proj(context)
        return output, current_key_value
```

---

### 11. Line-by-Line Code Walkthrough
* `line 17-21`: Validasi keterbagian `d_model` oleh `num_heads`. Jika tidak habis dibagi, konfigurasi head tidak valid secara aljabar linier. Skalar $\frac{1}{\sqrt{d_k}}$ disimpan sebagai `self.scale` untuk menghindari kalkulasi berulang per forward pass.
* `line 29-31`: `register_buffer("causal_mask", ...)` membuat tensor lower-triangular boolean mask tersimpan di memori modul tanpa didaftarkan sebagai parameter yang menerima optimasi gradien backprop, otomatis berpindah device (CPU $\to$ GPU) saat modul `.to(device)` dipanggil.
* `line 49-51`: Tensor input dipecah dari representasi global model (`d_model`) ke representasi multi-head (`num_heads, head_dim`). Transpose `(1, 2)` memastikan dimensi dimensi matriks batch dan head berada di luar, menyisakan `[Seq_len, Head_dim]` di indeks akhir untuk operasi tensor batch matrix multiply (`matmul`).
* `line 54-57`: Pengecekan KV cache. Jika state masa lalu tersedia, kita menyatukan tensor Key dan Value baru pada dimensi sequence (`dim=-2`).
* `line 67-71`: Logika seleksi masking. Jika `seq_len > 1` (Prefill phase), causal mask dipotong sesuai irisan sequence saat ini dan masa lalu. Jika `seq_len == 1` (Incremental Decoding step), causal mask dilewati karena satu token baru memiliki hak membaca seluruh masa lalu di KV cache.
* `line 74`: `torch.softmax(..., dtype=torch.float32)` adalah *numerical stabilization trick*. Dalam komputasi FP16/BF16, kalkulasi eksponensial softmax rentan underflow/overflow. Melakukan cast ke FP32 sebelum Softmax dan mengembalikan ke dtype asal menjamin stabilitas numerik tanpa degradasi performa berarti.
* `line 80`: `.contiguous()` dipanggil sebelum `.view()`. Operasi `.transpose()` memanipulasi metadata *stride* tensor tanpa memindahkan lokasi data asli di memori. Jika memori tensor tidak sekuensial, pemanggilan `.view()` akan melempar *RuntimeError*.

---

### 12. Verification & Validation

Script pengujian berikut memvalidasi bahwa output inferensi bertahap menggunakan KV Cache identik secara numerik dengan komputasi utuh tanpa cache (toleransi floating-point standard FP32):

```python
import torch

def test_kv_cache_correctness():
    torch.manual_seed(42)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    
    d_model = 64
    num_heads = 4
    attn = CausalSelfAttentionWithKVCache(d_model=d_model, num_heads=num_heads).to(device)
    attn.eval()

    # Buat sekuens input acak (Batch=1, SeqLen=5, Dim=64)
    x = torch.randn(1, 5, d_model, device=device)

    # 1. Non-Cached Full Pass
    with torch.no_grad():
        full_output, _ = attn(x, use_cache=False)

    # 2. Sequential Step-by-Step with KV Cache
    # Step 2a: Prefill dengan 3 token pertama
    with torch.no_grad():
        prefill_out, kv_cache = attn(x[:, :3, :], use_cache=True)
        
        # Step 2b: Decoding token ke-4
        tok4_out, kv_cache = attn(x[:, 3:4, :], use_cache=True, past_key_value=kv_cache)
        
        # Step 2c: Decoding token ke-5
        tok5_out, kv_cache = attn(x[:, 4:5, :], use_cache=True, past_key_value=kv_cache)

    # Satukan kembali hasil sequential decoding
    sequential_output = torch.cat([prefill_out, tok4_out, tok5_out], dim=1)

    # 3. Assert Equivalence
    discrepancy = torch.max(torch.abs(full_output - sequential_output)).item()
    print(f"Max absolute discrepancy: {discrepancy:.2e}")
    
    # Toleransi FP32: perbedaan harus berada di bawah threshold 1e-5
    assert discrepancy < 1e-5, "Validasi Gagal: Nilai KV cache berbeda dengan perhitungan non-cached!"
    print("Assertion Berhasil: Implementasi KV Cache valid secara numerik.")

if __name__ == "__main__":
    test_kv_cache_correctness()
```

---

### 13. Real-World Anti-Patterns

```
ANTIPATTERN: Dynamic Memory Allocation Inside Generative Loops
Bad Practice:
  kv_cache = None
  for token in stream:
      out, kv_cache = model(token, past_key_value=kv_cache)
      # Memicu re-alokasi tensor terus-menerus di memori GPU
      # Mengakibatkan CUDA memory fragmentation dan latency spikes (jitter)

CORRECT PATTERN: Static / Paged Memory Management
Good Practice:
  K_cache = torch.empty((B, H, MAX_SEQ, D_h), device=device)
  V_cache = torch.empty((B, H, MAX_SEQ, D_h), device=device)
  # Menulis ke slice memori yang sudah di-preallocate via index pointer:
  K_cache[:, :, current_pos:current_pos+1, :].copy_(k_new)
```

| Anti-Pattern | Gejala Produksi | Arsitektur Solusi |
| :--- | :--- | :--- |
| Mengabaikan FP32 Casting pada Softmax | NaN Loss saat fine-tuning; Karakter acak/gibberish muncul saat inference FP16. | Selalu hitung Softmax dalam presisi float32, lalu cast kembali ke low-precision. |
| Naive Full Matrix Recalculation ($O(N^2)$ generation) | Latency meningkat tajam per kata baru yang di-generate. Response time melambat seiring panjangnya teks. | Implementasikan KV Caching untuk menurunkan kompleksitas decoding dari $O(N^2)$ menjadi $O(N)$. |
| Menyimpan Positional Embedding di KV Cache | Memory leak dan desinkronisasi index context saat dynamic batching. | Simpan un-embedded Keys atau pisahkan RoPE (Rotary Position Embedding) langsung pada projection tensor. |

---

### 14. Operational Hardening & Memory Footprint

Kebutuhan memori VRAM untuk KV Cache dapat dihitung menggunakan rumus eksak:

$$\text{KV Cache Size (Bytes)} = 2 \times 2 \times n_{\text{layers}} \times n_{\text{heads}} \times d_{\text{head}} \times \text{seq\_len} \times \text{batch\_size} \times \text{bytes\_per\_param}$$

Contoh Kasus Produksi: Model Ukuran LLaMA-7B:
* $n_{\text{layers}} = 32$
* $n_{\text{heads}} = 32$
* $d_{\text{head}} = 128$
* `bytes_per_param` = 2 (untuk 16-bit Float / FP16 / BF16)
* Konstan pengali: 2 (karena menyimpan Key dan Value terpisah)

Untuk Sequence Length 4.096 dengan Concurrency (Batch Size) = 8:

$$\text{Size} = 2 \times 2 \times 32 \times 32 \times 128 \times 4096 \times 8 \times 2 \text{ bytes} \approx 17.179.869.184 \text{ bytes} \approx \mathbf{16\text{ GB VRAM}}$$

Hanya untuk menyimpan *cache state* saja dibutuhkan 16 GB VRAM di luar bobot model (weights model 7B FP16 $\approx$ 14 GB).

**Strategi Mitigasi OOM Operasional:**
1. **Multi-Query Attention (MQA) & Grouped-Query Attention (GQA):** Mengurangi jumlah key/value heads relatif terhadap query heads. LLaMA-2 70B beralih ke GQA (8 KV heads vs 64 Q heads), memotong ukuran KV Cache sebesar $8\times$.
2. **FlashAttention Optimization:** Menggunakan tiling algorithm untuk menghitung exact attention tanpa merealisasikan matriks perantara $S \times S$ ke High-Bandwidth Memory (HBM), mengeliminasi lonjakan memori pada prefill phase.

---

### 15. Security & Threat Modeling
* **Cross-Tenant State Pollution:** Pada arsitektur inference engine yang melayani multi-user dengan batching dinamis (seperti Continuous Batching), kesalahan pointer pada KV Cache memory buffer dapat menyebabkan context pengguna A tertulis atau terbaca oleh pengguna B.
    * *Mitigasi:* Isolasi memory page berbasis UUID token request dan enkripsi per-page context jika dijalankan pada multi-tenant infrastructure.
* **Denial of Service (DoS) via Context Squeezing:** Penyerang sengaja mengirimkan prompt tepat di batas maksimum limit token secara simultan. Ini memaksa alokasi memori instan pada KV Cache dan memicu OOM Panic pada CUDA runtime, merusak proses worker seluruh model server.
    * *Mitigasi:* Rate limiting berdasarkan estimasi konsumsi token buffer (bukan hanya raw HTTP request counts), serta memory-aware admission control.

---

### 16. Observability & Telemetry

Metrik utama yang wajib diekspor oleh LLM Inference Engine ke sistem monitoring (contoh: Prometheus/Grafana):

```
+-----------------------------------------------------------------------------------+
| Metric Name                      | Type      | Target SLA / Alert Threshold       |
+-----------------------------------------------------------------------------------+
| llm_time_to_first_token_seconds  | Histogram | < 200 ms (Prefill Phase Latency)   |
| llm_time_per_output_token_seconds| Histogram | < 25 ms (Decode Throughput Target) |
| llm_kv_cache_usage_ratio         | Gauge     | Alert jika > 0.85 (Mendekati OOM)  |
| llm_prefill_tflops_utilization   | Gauge     | > 60% GPU Compute Bound Maxima     |
| llm_decode_memory_bandwidth_gbps | Gauge     | > 75% Hardware Peak Spec           |
+-----------------------------------------------------------------------------------+
```

Kode instrumentasi sederhana pada inference service:

```python
import time

def instrumented_decode_step(attn_module, current_token, cache):
    start_time = torch.cuda.Event(enable_timing=True)
    end_time = torch.cuda.Event(enable_timing=True)

    start_time.record()
    with torch.no_grad():
        out, cache = attn_module(current_token, use_cache=True, past_key_value=cache)
    end_time.record()

    torch.cuda.synchronize()
    latency_ms = start_time.elapsed_time(end_time)
    
    # Ekspor ke pipeline telemetry Anda (contoh print mock)
    # telemetry.record("llm_time_per_output_token_seconds", latency_ms / 1000.0)
    return out, cache, latency_ms
```

---

### 17. Trade-Off Analysis

Dalam mendesain sistem Attention untuk context window besar, engineer harus memilih mekanisme arsitektur yang tepat:

```
Multi-Head Attention (MHA)
[Q1][Q2][Q3][Q4]
[K1][K2][K3][K4]  -> Akurasi maksimal, KV Cache paling besar
[V1][V2][V3][V4]

Grouped-Query Attention (GQA)
[Q1][Q2]  [Q3][Q4]
  [K1]      [K2]   -> Trade-off optimal (kapabilitas tinggi, memori hemat)
  [V1]      [V2]

Multi-Query Attention (MQA)
[Q1][Q2][Q3][Q4]
      [K1]         -> Cache minimal, degradasi kemampuan reasoning minor
      [V1]
```

| Tipe Attention | Rasio Query:KV Head | Throughput (Tokens/s) | Konsumsi Memori KV Cache | Dampak Kapabilitas Reasoning |
| :--- | :--- | :--- | :--- | :--- |
| **MHA** | $1 : 1$ | Rendah (Memory-bound) | 100% (Baseline tertinggi) | 100% (Baseline optimal) |
| **GQA** | $8 : 1$ | Tinggi ($2\times - 3\times$) | ~12.5% - 25% | Mendekati MHA ($>99\%$) |
| **MQA** | $N : 1$ | Ekstrem ($4\times - 5\times$) | Minima ($1/H$ dari MHA) | Penurunan akurasi pada relasi konteks kompleks |

---

### 18. Integration Patterns

Modul Attention ini berintegrasi secara vertikal dengan komponen pipeline inferensi:

```
[Client Application]
         |  (Prompt Text)
         v
[Tokenizer Engine] -> Output: Input IDs Tensor
         |
         v
[Embedding Layer + RoPE Module]
         |
         v
[Pipeline Decoder Blocks (N Layers)]
  |-- Layer 0: CausalSelfAttentionWithKVCache (Handles Layer 0 KV)
  |-- Layer 1: CausalSelfAttentionWithKVCache (Handles Layer 1 KV)
  ...
  |-- Layer N: CausalSelfAttentionWithKVCache (Handles Layer N KV)
         |
         v
[RMSNorm & Final Language Model Head (LM_Head)]
         |
         v
[Logits Output] -> [Greedy Search / Top-p Sampler] -> [Detokenizer]
```

Setiap blok attention pada sequence layer menyimpan slice referensi KV Cache miliknya sendiri. Orchestrator inference bertanggung jawab melakukan broadcast state tuple `(K, V)` ke setiap layer terkait.

---

### 19. Key Takeaways
* Large Language Model inferensi terbagi atas dua tahap kerja: **Prefill Phase** yang bersifat *compute-bound* (paralel untuk seluruh prompt token) dan **Decoding Phase** yang bersifat *memory-bandwidth bound* (sekuensial token per token).
* Mekanisme **Scaled Dot-Product Attention** memiliki kompleksitas native $O(N^2)$. Tanpa **KV Cache**, biaya komputasi decoding token baru melonjak menjadi $O(N^2)$ per step alih-alih $O(N)$.
* Scaling factor $\frac{1}{\sqrt{d_k}}$ dan eksekusi Softmax pada presisi FP32 adalah mandatory architecture pattern untuk mencegah numerical explosion / NaN degradation.
* Penggunaan memori GPU pada inferensi LLM produksi didominasi oleh KV Cache saat menangani sequence panjang dan konkurensi tinggi, bukan semata-mata ukuran bobot model statis.

---

### 20. Next Steps & References
* **Modul Berikutnya:** Modul 02: *Positional Embeddings Deep Dive: Implementasi Rotary Position Embeddings (RoPE), ALiBi, dan Scaling Context Limits*.
* **Referensi Wajib:**
  1. Vaswani et al., (2017). *Attention Is All You Need*. arXiv:1706.03762.
  2. Dao et al., (2022). *FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness*. arXiv:2205.14135.
  3. Ainslie et al., (2023). *GQA: Training Generalized Multi-Query Transformer Models from Multi-Head Checkpoints*. arXiv:2305.13245.
  4. Kwon et al., (2023). *Efficient Memory Management for Large Language Model Serving with PagedAttention*. SOSP '23.