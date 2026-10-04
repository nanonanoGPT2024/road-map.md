# Bab 02: LLM Internals: Arsitektur Transformer & Mekanisme Inferensi

## Module 01: Anatomi Decoder-Only Transformer, KV-Cache, dan Dinamika Inferensi Autoregresif

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. **Menganalisis Arsitektur Decoder-Only Modern**: Menguraikan komponen kritis arsitektur berbasis LLaMA/Mistral (RMSNorm, Rotary Position Embedding/RoPE, SwiGLU, Grouped-Query Attention/GQA).
2. **Membedah Mekanisme Inferensi Dua Fase**: Membedakan profil komputasi dan memori antara fase *Prefill* (*compute-bound*) dan fase *Decode* (*memory-bandwidth bound*).
3. **Mengimplementasikan KV-Cache & GQA dari Awal**: Membangun modul *Grouped-Query Attention* berbasis PyTorch dengan integrasi *stateful Key-Value (KV) Cache* dan RoPE tanpa pustaka pihak ketiga tingkat tinggi.
4. **Menghitung Footprint Memori VRAM Inferensi**: Menghitung kebutuhan kapasitas VRAM runtime secara deterministik berdasarkan parameter model, context length, batch size, dan presisi numerik (*FP16/BF16/FP8*).
5. **Mengoptimalkan Algoritma Decoding**: Mengonstruksi pipeline sampling deterministik dan stokastik (*Greedy*, *Temperature*, *Top-K*, *Top-P/Nucleus*) langsung pada tensor logits.

---

### 2. Concept Overview

Model Bahasa Skala Besar (Large Language Models / LLM) modern yang mendominasi industri sistem otonom dan AI data pipelines mengadopsi varian **Decoder-Only Transformer**. Berbeda dengan arsitektur orisinal Vaswani et al. (2017) yang menggunakan encoder-decoder, decoder-only transformer menyederhanakan alur komputasi menjadi proses autoregresif murni: memprediksi token $t_{i}$ berdasarkan konteks token sebelumnya $t_{1}, \dots, t_{i-1}$.

```
Input Tokens: [x_1, ..., x_t]
      │
      ▼
┌──────────────┐
│ Token Embed  │ + RoPE (Rotary Position Embeddings)
└──────┬───────┘
       │
┌──────▼─────────────────────────────────────────────────┐
│ Transformer Block x N                                  │
│  ┌──────────────────────────────────────────────────┐  │
│  │ RMSNorm(x)                                       │  │
│  │   ▼                                              │  │
│  │ Grouped-Query Attention (GQA) with KV-Cache      │  │
│  │   ▼                                              │  │
│  │ Residual Add: x = x + Attention(RMSNorm(x))      │  │
│  │   ▼                                              │  │
│  │ RMSNorm(x)                                       │  │
│  │   ▼                                              │  │
│  │ SwiGLU Feed-Forward Network (FFN)                │  │
│  │   ▼                                              │  │
│  │ Residual Add: x = x + SwiGLU(RMSNorm(x))         │  │
│  └──────────────────────────────────────────────────┘  │
└──────┬─────────────────────────────────────────────────┘
       │
┌──────▼───────┐
│ Final RMSNorm│
└──────┬───────┘
       │
┌──────▼───────┐
│ LM Head      │ (Linear Projection: hidden_dim -> vocab_size)
└──────┬───────┘
       ▼
Logits -> Softmax/Sampling -> Next Token: x_{t+1}
```

#### Komponen Kunci Arsitektur Modern:
1. **Pre-Layer Normalization (RMSNorm)**: Menghapus dependensi mean-centering dari Standard LayerNorm untuk memangkas overhead pemrosesan tensor:
   $$\text{RMSNorm}(x) = \frac{x}{\sqrt{\frac{1}{d}\sum_{i=1}^d x_i^2 + \epsilon}} \odot \gamma$$
2. **Rotary Position Embedding (RoPE)**: Mengenkode informasi posisi relatif langsung ke dalam vektor *Query* dan *Key* melalui rotasi bidang ortogonal kompleks, menjaga properti invarian terhadap jarak token.
3. **SwiGLU Activation**: Mengganti ReLU/GELU standar dengan Swish-Gated Linear Unit yang meningkatkan laju konvergensi parameter pada rasio throughput representasi yang sama:
   $$\text{SwiGLU}(x) = \left(x W_{\text{gate}} \cdot \sigma(x W_{\text{gate}})\right) \otimes (x W_{\text{up}}) W_{\text{down}}$$
4. **Grouped-Query Attention (GQA)**: Solusi kompromi matematis antara Multi-Head Attention (MHA) dan Multi-Query Attention (MQA), di mana sejumlah $H_Q$ query heads membagi sejumlah $H_{KV}$ key-value heads secara proporsional ($H_Q / H_{KV} > 1$).

---

### 3. Why It Matters

Di tingkat enterprise, pemahaman mendalam tentang LLM Internals menentukan viabilitas ekonomi dan latensi arsitektur sistem berbasis *Agentic AI*. 

1. **Bottleneck Memori Grafis (The Roofline Model & Memory-Wall)**:
   Pada fase **Prefill** (pemrosesan prompt), LLM bekerja di ranah *Compute-Bound*, memanfaatkan paralelisme matriks GEMM (*General Matrix Multiply*) GPU secara maksimal. Namun, pada fase **Decode** (generasi token satu per satu), sistem bergeser menjadi *Memory-Bandwidth Bound*. GPU Tensor Cores menganggur menunggu pembacaan bobot model dan *KV-Cache* dari High-Bandwidth Memory (HBM) ke SRAM/register untuk menghasilkan hanya satu token per step.
2. **Eksplosi Biaya Infrastruktur**:
   Tanpa optimasi KV-Cache dan GQA, konteks dokumen panjang (misal 32k-128k token untuk RAG enterprise) memicu *Out-Of-Memory* (OOM) secara instan. Menguasai alokasi memori KV-Cache memungkinkan AI Platform Engineer merancang strategi kompresi, kuantisasi (*FP8/INT4 KV-Cache*), dan *continuous batching* presisi tinggi.

---

### 4. Arsitektur & Diagram Komponen

#### 4.1. Siklus Hidup Inferensi: Prefill vs. Decode

```
========================================================================================
FASE 1: PREFILL (Context Phase) - Compute-Bound
========================================================================================
Prompt: "Halo, nama saya" (Ukuran Sequence S = 4)

Tokens: [T_0, T_1, T_2, T_3] 
Parallel Processing via Attention Mask (Causal Lower Triangular):
Q = [q_0, q_1, q_2, q_3]
K = [k_0, k_1, k_2, k_3] ──> Tulis SEMUA K & V ke KV-Cache
V = [v_0, v_1, v_2, v_3] ──┘
Perhitungan Attention secara paralel untuk seluruh posisi.
Output: Logits untuk posisi terakhir (T_3) ──> Sampel token baru: "Budi" (T_4)

========================================================================================
FASE 2: DECODE (Generation Phase) - Memory-Bandwidth Bound
========================================================================================
Langkah 1:
Input: HANYA T_4 ("Budi") -> Q = [q_4], K = [k_4], V = [v_4]
Append k_4, v_4 ke KV-Cache:
  K_Cache: [k_0, k_1, k_2, k_3, k_4]
  V_Cache: [v_0, v_1, v_2, v_3, v_4]
Perhitungan Attention: q_4 di-dot product-kan ke seluruh K_Cache [k_0 .. k_4]
Output: T_5 ("adalah")

Langkah 2:
Input: HANYA T_5 ("adalah") -> Q = [q_5], K = [k_5], V = [v_5]
Append k_5, v_5 ke KV-Cache:
  K_Cache: [k_0, k_1, k_2, k_3, k_4, k_5]
  V_Cache: [v_0, v_1, v_2, v_3, v_4, v_5]
Perhitungan Attention: q_5 di-dot product-kan ke seluruh K_Cache [k_0 .. k_5]
Output: T_6 ...
========================================================================================
```

#### 4.2. Arsitektur Komparasi: MHA vs GQA vs MQA

```
      Multi-Head Attention (MHA)            Grouped-Query Attention (GQA)          Multi-Query Attention (MQA)
      
    Q Heads (8)       K/V Heads (8)       Q Heads (8)       K/V Heads (2)       Q Heads (8)       K/V Heads (1)
   ┌──┬──┬──┬──┐     ┌──┬──┬──┬──┐       ┌──┬──┬──┬──┐         ┌──┐            ┌──┬──┬──┬──┐         ┌──┐   
   │q1│q2│q3│q4│     │k1│k2│k3│k4│       │q1│q2│q3│q4│───────> │k1│            │q1│q2│q3│q4│───────> │k1│   
   ├──┼──┼──┼──┤     ├──┼──┼──┼──┤       ├──┼──┼──┼──┤         └──┘            ├──┼──┼──┼──┤         └──┘   
   │q5│q6│q7│q8│     │k5│k6│k7│k8│       │q5│q6│q7│q8│───────> │k2│            │q5│q6│q7│q8│         │v1│   
   └──┴──┴──┴──┘     └──┴──┴──┴──┘       └──┴──┴──┴──┘         ┌──┐            └──┴──┴──┴──┘         └──┘   
   (Rasio KV: 1:1, KV Cache Besar)       (Grup 4:1, KV Cache Terpangkas 75%)   (Rasio 8:1, KV Cache Sangat Kecil)
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### 5.1. Rotary Position Embedding (RoPE)
Secara matematis, untuk vektor 2D $x = (x_1, x_2)^T$ pada posisi $m$, transformasi ortogonalnya adalah:
$$R_{\Theta, m}^2 x = \begin{pmatrix} \cos m\theta & -\sin m\theta \\ \sin m\theta & \cos m\theta \end{pmatrix} \begin{pmatrix} x_1 \\ x_2 \end{pmatrix}$$
Untuk dimensi embedding $d$, matriks dipecah menjadi $d/2$ sub-ruang 2D berotasi independen dengan frekuensi $\theta_i = 10000^{-2(i-1)/d}$. Keunggulannya: inner product $\langle R_m q, R_n k \rangle$ secara murni merupakan fungsi dari selisih jarak relatif $(m - n)$.

#### 5.2. Persamaan Formal Grouped-Query Attention (GQA)
Jika $H_Q$ adalah jumlah kepala Query dan $H_{KV}$ adalah jumlah kepala Key-Value, kita mendefinisikan faktor replikasi:
$$r = \frac{H_Q}{H_{KV}}$$
Setiap kepala Key dan Value di-broadcast ke $r$ kepala Query sebelum kalkulasi *Scaled Dot-Product Attention*:
$$\text{Attention}(Q_i, K_{\lfloor i/r \rfloor}, V_{\lfloor i/r \rfloor}) = \text{softmax}\left(\frac{Q_i K_{\lfloor i/r \rfloor}^T}{\sqrt{d_k}} + M\right) V_{\lfloor i/r \rfloor}$$
di mana $M$ adalah matriks *causal mask* ($-\infty$ untuk token masa depan).

#### 5.3. Formula Analitik Footprint Memori KV-Cache
Untuk model dengan konfigurasi:
* $L$: Jumlah layer (*layers*)
* $H_{KV}$: Jumlah key-value heads
* $D_h$: Dimensi head ($d_{model} / H_Q$)
* $S$: Panjang sekuens (*sequence length / context window*)
* $B$: Batch size
* $P$: Presisi byte per elemen (FP16/BF16 = 2 bytes, FP8 = 1 byte)

Kebutuhan memori KV-Cache murni dihitung melalui rumus:
$$\text{Memory}_{\text{KV-Cache}} = 2 \times L \times H_{KV} \times D_h \times S \times B \times P \quad (\text{Bytes})$$
*Catatan: Faktor 2 memperhitungkan penyimpanan terpisah untuk Key dan Value.*

---

### 6. Production-Ready Code Implementation

Berikut implementasi lengkap komponen inti Decoder-Only Transformer: Rotary Positional Embedding (RoPE), Grouped-Query Attention (GQA) terintegrasi dengan runtime-managed Dynamic KV-Cache, dan loop inferensi autoregresif dengan sampling stokastik/deterministik.

```python
"""
Core Engine: Decoder-Only Transformer Inference Module
Kompatibel: PyTorch 2.x+, Python 3.10+
"""

from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F


@dataclass(frozen=True)
class ModelArgs:
    dim: int = 1024
    n_layers: int = 8
    n_heads: int = 8          # Head Query
    n_kv_heads: int = 2       # Head Key/Value (GQA rasio 4:1)
    vocab_size: int = 8000
    multiple_of: int = 256
    ffn_dim_multiplier: Optional[float] = None
    norm_eps: float = 1e-5
    max_seq_len: int = 2048
    device: str = "cpu"


class RMSNorm(nn.Module):
    """Root Mean Square Layer Normalization (RMSNorm) tanpa mean-centering."""
    def __init__(self, dim: int, eps: float = 1e-5):
        super().__init__()
        self.eps = eps
        self.weight = nn.Parameter(torch.ones(dim))

    def _norm(self, x: torch.Tensor) -> torch.Tensor:
        return x * torch.rsqrt(x.pow(2).mean(-1, keepdim=True) + self.eps)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        output = self._norm(x.float()).type_as(x)
        return output * self.weight


def precompute_rope_freqs_cis(dim: int, end: int, theta: float = 10000.0) -> torch.Tensor:
    """Precompute frekuensi bilangan kompleks untuk RoPE."""
    freqs = 1.0 / (theta ** (torch.arange(0, dim, 2)[: (dim // 2)].float() / dim))
    t = torch.arange(end, device=freqs.device, dtype=torch.float32)
    freqs = torch.outer(t, freqs)
    # Bentuk tensor representasi polar: exp(i * freqs) = cos + i*sin
    freqs_cis = torch.polar(torch.ones_like(freqs), freqs)
    return freqs_cis


def apply_rotary_emb(
    xq: torch.Tensor,
    xk: torch.Tensor,
    freqs_cis: torch.Tensor,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """Rotasi vektor Query dan Key menggunakan perkalian bilangan kompleks."""
    xq_ = torch.view_as_complex(xq.float().reshape(*xq.shape[:-1], -1, 2))
    xk_ = torch.view_as_complex(xk.float().reshape(*xk.shape[:-1], -1, 2))
    freqs_cis = freqs_cis.view(1, xq_.shape[1], 1, xq_.shape[-1])
    
    xq_out = torch.view_as_real(xq_ * freqs_cis).flatten(3)
    xk_out = torch.view_as_real(xk_ * freqs_cis).flatten(3)
    return xq_out.type_as(xq), xk_out.type_as(xk)


def repeat_kv(x: torch.Tensor, n_rep: int) -> torch.Tensor:
    """Menduplikasi Head Key/Value untuk menyesuaikan jumlah Head Query pada GQA."""
    if n_rep == 1:
        return x
    bs, slen, n_kv_heads, head_dim = x.shape
    return (
        x[:, :, :, None, :]
        .expand(bs, slen, n_kv_heads, n_rep, head_dim)
        .reshape(bs, slen, n_kv_heads * n_rep, head_dim)
    )


class KVCache(nn.Module):
    """Dynamic Tensor Buffer untuk KV-Cache inferensi kontinu."""
    def __init__(self, max_batch_size: int, max_seq_len: int, n_kv_heads: int, head_dim: int, device: str):
        super().__init__()
        cache_shape = (max_batch_size, max_seq_len, n_kv_heads, head_dim)
        self.register_buffer("k_cache", torch.zeros(cache_shape, dtype=torch.float32, device=device))
        self.register_buffer("v_cache", torch.zeros(cache_shape, dtype=torch.float32, device=device))

    def update(
        self, start_pos: int, seq_len: int, xk: torch.Tensor, xv: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        bsz = xk.size(0)
        self.k_cache[:bsz, start_pos : start_pos + seq_len] = xk
        self.v_cache[:bsz, start_pos : start_pos + seq_len] = xv
        
        keys = self.k_cache[:bsz, : start_pos + seq_len]
        values = self.v_cache[:bsz, : start_pos + seq_len]
        return keys, values

    def reset(self):
        self.k_cache.zero_()
        self.v_cache.zero_()


class GroupedQueryAttention(nn.Module):
    """Grouped-Query Attention (GQA) yang mendukung Prefill & Decode State Caching."""
    def __init__(self, args: ModelArgs):
        super().__init__()
        self.n_heads = args.n_heads
        self.n_kv_heads = args.n_kv_heads
        self.n_rep = self.n_heads // self.n_kv_heads
        self.head_dim = args.dim // args.n_heads

        self.wq = nn.Linear(args.dim, args.n_heads * self.head_dim, bias=False)
        self.wk = nn.Linear(args.dim, args.n_kv_heads * self.head_dim, bias=False)
        self.wv = nn.Linear(args.dim, args.n_kv_heads * self.head_dim, bias=False)