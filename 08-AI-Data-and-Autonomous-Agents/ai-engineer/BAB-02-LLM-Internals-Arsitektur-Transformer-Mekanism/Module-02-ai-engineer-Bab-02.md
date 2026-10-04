# Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis & Mengatasi Bottleneck Inferensi**: Menghitung secara matematis batasan memori (*Memory-Bound*) vs komputasi (*Compute-Bound*) pada fase *Pre-fill* vs *Decode* menggunakan *Roofline Model*.
- **Mengimplementasikan Arsitektur Attention Modern**: Mengembangkan algoritma *Rotary Position Embedding* (RoPE), *Grouped-Query Attention* (GQA), dan *Multi-Query Attention* (MQA) dari *first principles* menggunakan PyTorch murni.
- **Merekayasa Manajemen State Inferensi**: Mengimplementasikan *KV Cache* teroptimasi dan memahami arsitektur *PagedAttention* serta mekanisme *Continuous Batching* untuk mengeliminasi fragmentasi memori GPU.
- **Mengoptimalkan Throughput Produksi**: Mendesain konfigurasi serving LLM skala enterprise dengan mempertimbangkan trade-off *Time-to-First-Token* (TTFT), *Time-Per-Output-Token* (TPOT), *quantization* (AWQ/GPTQ/FP8), dan *Speculative Decoding*.

---

## 2. Prerequisites

Sebelum mempelajari modul ini, peserta harus menguasai:
- **Matematika Lanjutan**: Aljabar linear (perkalian tensor n-dimensi, proyeksi ortogonal, rotasi kompleks 2D), kalkulus multivariat.
- **Hardware Architecture**: Pemahaman mendasar mengenai hierarki memori GPU (HBM/VRAM, SRAM/Shared Memory, L1/L2 Cache), *memory bandwidth* (misal: 2.0 TB/s pada A100 vs 3.35 TB/s pada H100), dan *Tensor Cores*.
- **PyTorch Tensor Engineering**: Manipulasi bentuk tensor (`einsum`, `as_strided`, `view`, `transpose`), penulisan *custom autograd function*, dan profiling dasar CUDA (`torch.cuda.Event`).
- **Transformer Fundamentals**: Memahami Vanilla Multi-Head Attention (MHA), Absolute Positional Embedding, dan pipeline Decoder-Only standar (GPT-style).

---

## 3. Concept & Internal Architecture

Dalam ranah produksi skala enterprise, menjalankan LLM bukan sekadar persoalan memuat bobot model ke VRAM dan memanggil fungsi `forward()`. Eksekusi LLM memiliki dua fase fundamental yang memiliki karakteristik pemanfaatan hardware yang bertolak belakang:

### 3.1 Fase Komputasi: Pre-fill vs Decode

```
+-------------------------------------------------------------------------------+
|                             FASE PRE-FILL                                     |
|  Input: Prompt [T_prompt tokens]                                              |
|  Karakteristik: Paralel, Compute-Bound (Matrix Multiplication FLOPs dominan)   |
|  Metrik Utama: Time-To-First-Token (TTFT)                                     |
+-------------------------------------------------------------------------------+
                                      │
                                      ▼
+-------------------------------------------------------------------------------+
|                              FASE DECODE                                      |
|  Input: 1 token (autoregresif) + KV Cache [T_context tokens]                  |
|  Karakteristik: Sequential, Memory-Bandwidth Bound (Memory I/O dominan)       |
|  Metrik Utama: Time-Per-Output-Token (TPOT) / Latensi Per-Token               |
+-------------------------------------------------------------------------------+
```

Pada fase **Pre-fill**, seluruh token konteks diproses secara simultan. Operasi matriks berukuran besar ($Q \times K^T$) memaksimalkan utilisasi Tensor Cores (*Arithmetic Intensity* tinggi $\gg 100 \text{ FLOPs/byte}$).

Sebaliknya, pada fase **Decode**, LLM hanya memproses **satu token baru per step**. Untuk menghasilkan satu token tersebut, sistem harus membaca bobot model miliaran parameter dan seluruh state *Key-Value* masa lalu dari VRAM (High Bandwidth Memory/HBM) ke dalam SRAM GPU. Rasio komputasi terhadap pembacaan memori (*Arithmetic Intensity*) anjlok secara drastis hingga mendekati $\sim 1 \text{ FLOP/byte}$, menjadikan inferensi token autoregresif sangat terbatasi oleh *Memory Bandwidth* GPU, bukan daya komputasi TFLOPs.

### 3.2 Evolusi Mekanisme Atensi: Dari MHA ke MQA dan GQA

Vanilla Multi-Head Attention (MHA) mengalokasikan pasangan kepala $K$ dan $V$ independen untuk setiap kepala $Q$. Jika sebuah model memiliki $H_Q = 32$ kepala dengan dimensi per kepala $d_k = 128$, maka untuk setiap token tersimpan $2 \times 32 \times 128 = 8.192$ elemen float16 (16 KB per layer, per token).

1. **Multi-Head Attention (MHA)**: $H_Q = H_K = H_V$. Kapasitas representasi maksimal, namun memori KV Cache membengkak linear terhadap jumlah head dan panjang konteks.
2. **Multi-Query Attention (MQA)**: $H_K = H_V = 1$. Seluruh kepala query berbagi satu kepala $K$ dan satu kepala $V$. Ukuran KV Cache menyusut drastis sebesar $1 / H_Q$ (mengurangi ukuran hingga 96%), tetapi menyebabkan penurunan akurasi pada penalaran kompleks.
3. **Grouped-Query Attention (GQA)**: Titik tengah optimal (dipakai oleh Llama 2 70B, Llama 3, Mistral). Kepala Query dibagi ke dalam $G$ grup, di mana setiap grup berbagi satu set kepala $K$ dan $V$ ($H_K = H_V = G$, di mana $1 < G < H_Q$).

$$GQA\_Ratio = \frac{H_Q}{G}$$

### 3.3 Rotary Position Embedding (RoPE)

Berbeda dengan absolut positional embedding yang ditambahkan langsung ke token embedding ($x = w + p$), RoPE memutar vektor Query dan Key dalam ruang kompleks 2D berdasarkan posisi absolut token $m$. 

Secara matematis, untuk vektor 2D $[x_1, x_2]^T$ pada posisi $m$:

$$R_{\Theta, m}^d = \begin{pmatrix} \cos m\theta & -\sin m\theta \\ \sin m\theta & \cos m\theta \end{pmatrix} \begin{pmatrix} x_1 \\ x_2 \end{pmatrix}$$

Keunggulan struktural RoPE:
- **Invarian Relatif**: Dot product antara query pada posisi $m$ dan key pada posisi $n$ secara murni merefleksikan selisih jarak relatif $(m - n)$:

$$\langle R_m q, R_n k \rangle = q^T R_{n-m} k$$

- **Generalisasi Panjang Konteks**: Memungkinkan teknik interpolasi frekuensi (seperti YaRN atau RoPE NTK-Aware Scaling) untuk mengekspansi *context window* tanpa perlu melatih ulang model dari awal.

### 3.4 Arsitektur PagedAttention dan Zero-Fragmentation KV Cache

Tantangan utama dari KV Cache konvensional adalah alokasi memori kontigu statis (*pre-allocation*) untuk panjang sekuens maksimal ($L_{max}$). Hal ini menghasilkan dua problem:
1. **Internal Fragmentation**: Mengalokasikan ruang untuk 4096 token padahal model hanya menghasilkan 100 token.
2. **External Fragmentation**: Memori VRAM terpecah sehingga batch baru tidak dapat dialokasikan meskipun total VRAM bebas secara agregat masih mencukupi.

Arsitektur **PagedAttention** (fondasi vLLM) mengadaptasi konsep *Virtual Memory Paging* dari Sistem Operasi ke dalam manajemen VRAM GPU:
- Memori KV Cache dibagi menjadi blok-blok berukuran tetap (*block_size*, misal 16 atau 32 token).
- Blok fisik tidak perlu kontigu di HBM.
- *Block Table* memetakan urutan token logis ke blok fisik di GPU.

---

## 4. Why & What

| Konsep | What (Apa Karakteristiknya?) | Why (Mengapa Dibutuhkan di Produksi?) |
|---|---|---|
| **Grouped-Query Attention (GQA)** | Merelaksikan rasio kepala K/V terhadap Query menjadi $H_Q : G$. | Mengurangi footprint KV Cache di VRAM hingga 75-87.5% dibandingkan MHA tanpa degradasi akurasi signifikan, memperbesar kapasitas ukuran batch konkuren. |
| **Rotary Position Embedding (RoPE)** | Mengodekan posisi via rotasi ortogonal pada ruang vektor Query/Key. | Menghilangkan batasan posisi mutlak; menjaga properti dot-product peluruhan jarak alami (*decay distance*); memudahkan ekstrapolasi panjang token. |
| **PagedAttention** | Abstraksi non-kontigu KV Cache berbasis *physical block table*. | Menurunkan pemborosan memori akibat fragmentasi dari ~60-80% menjadi <4%, memungkinkan pelipatgandaan *throughput* serving (3x-5x). |
| **FlashAttention (v1/v2/v3)** | Reorganisasi eksekusi matriks atensi berbasis blok memanfaatkan SRAM (*tiling & online softmax*). | Menghindari I/O berulang antara SRAM dan HBM. Mengurangi kompleksitas memori dari $O(N^2)$ menjadi $O(N)$, melipatgandakan kecepatan komputasi fase pre-fill. |

---

## 5. How (Workflow Detail)

Alur eksekusi komputasi inferensi end-to-end pada runtime generasi produksi modern:

```
[Client Request: Prompt Tokens]
         │
         ▼
[1. Tokenizer Encoding] ──> Token IDs: [T1, T2, ..., Tn]
         │
         ▼
[2. Scheduler Engine (Continuous Batching)]
         │ ── Cek ketersediaan Physical Blocks di Block Manager
         │ ── Alokasikan Block Table untuk Request ID
         ▼
[3. PRE-FILL PHASE (Parallel Input)]
         │ ── Forward Pass Layer 1 s.d. Layer L
         │ ── Terapkan RoPE pada Tensor Q & K
         │ ── Hitung FlashAttention Kernel (Compute-bound)
         │ ── Simpan K & V ke Physical Memory Blocks via Paged Cache
         ▼
[First Token Generated] ──> Kirim ke Client (Metrik: TTFT tercapai)
         │
         ▼
[4. DECODE PHASE LOOP (Autoregressive)]
   ┌───> │ ── Input: 1 Token baru
   │     │ ── Terapkan RoPE pada posisi index sekarang
   │     │ ── Fetch historical KV Blocks dari HBM ke SRAM via Block Table
   │     │ ── Hitung GQA menggunakan PagedAttention Kernel (Memory-bound)
   │     │ ── Append new K & V ke blok yang sesuai (alokasikan blok baru jika penuh)
   │     │ ── Sampling / Logits Processor (Top-P, Top-K, Temperature)
   │     │ ── Output Token Streamed
   │     │
   └─── Selesai? (EOS token atau Max Context tercapai)
         │ TIDAK
         ▼ YA
[5. De-alokasi Physical Blocks ke Free List Pool]
```

---

## 6. Analogy & Diagram ASCII

### 6.1 Analogi Pemrosesan Memori

Bayangkan KV Cache sebagai buku catatan seorang analis:
- **MHA**: Analis menyiapkan 32 buku catatan khusus terpisah untuk setiap sudut pandang riset, menuliskan ringkasan untuk setiap kalimat yang ia dengar. Mejanya (VRAM) langsung penuh sesak oleh tumpukan buku catatan kosong yang belum tentu terisi.
- **GQA**: Analis mengelompokkan 32 sudut pandang tersebut ke dalam 8 kelompok kerja. Setiap kelompok kerja hanya berbagi 1 buku catatan bersama. Meja kerja menjadi 4x lebih lapang, sehingga lebih banyak klien yang bisa dilayani di ruangan yang sama.
- **PagedAttention**: Alih-alih membeli buku tulis tebal 1000 halaman untuk setiap klien yang belum tentu berbicara panjang, analis menggunakan map binder berlembar lepas. Tiap kali ada selembar kertas penuh (16 token), ia mengambil 1 lembar kosong baru dari gudang. Tidak ada kertas kosong yang tersisa sia-sia di atas meja.

### 6.2 Diagram Struktur Attention Variants

```
Multi-Head Attention (MHA)         Grouped-Query Attention (GQA)        Multi-Query Attention (MQA)
     [Q1][Q2] [Q3][Q4]                  [Q1][Q2] [Q3][Q4]                  [Q1][Q2] [Q3][Q4]
      │   │    │   │                     └──┬──┘  └──┬──┘                   └───┴───┬───┴───┘
     [K1][K2] [K3][K4]                     [K1]     [K2]                           [K1]
      │   │    │   │                        │        │                              │
     [V1][V2] [V3][V4]                     [V1]     [V2]                           [V1]
 (1 Query Head : 1 KV Head)         (N Query Heads : 1 KV Group)         (All Query Heads : 1 KV Head)
```

### 6.3 Diagram PagedAttention Logical vs Physical Mapping

```
Logical Blocks (Sequence 0)          Block Table (Req 0)             Physical Blocks (GPU HBM)
┌────────────┬────────────┐         ┌───────────┬──────────┐        ┌─────────────────────────┐
│ Block 0    │ Token 0-3  │ ──────> │ Logical 0 │ Phys #7  │ ─────> │ Phys Block #3 (Req 1)   │
├────────────┼────────────┤         ├───────────┼──────────┤        ├─────────────────────────┤
│ Block 1    │ Token 4-7  │ ──────> │ Logical 1 │ Phys #1  │ ─────> │ Phys Block #7 (Req 0)   │
├────────────┼────────────┤         ├───────────┼──────────┤        ├─────────────────────────┤
│ Block 2    │ Token 8-11 │ ──────> │ Logical 2 │ Phys #9  │ ─────> │ Phys Block #1 (Req 0)   │
└────────────┴────────────┘         └───────────┴──────────┘        ├─────────────────────────┤
                                                                    │ Phys Block #9 (Req 0)   │
                                                                    └─────────────────────────┘
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Implementasi RoPE dari First Principles

Di bawah ini adalah implementasi matematika murni *Rotary Positional Embedding* (RoPE) menggunakan tensor kompleks atau representasi pasangan bidang 2D di PyTorch:

```python
import torch
import torch.nn as nn

def precompute_freqs_cis(dim: int, end: int, theta: float = 10000.0) -> torch.Tensor:
    """Precompute frekuensi sudut untuk RoPE (vektor kompleks)."""
    # Dimensi harus genap karena rotasi diaplikasikan berpasangan (2D)
    assert dim % 2 == 0
    # theta_i = 10000 ^ (-2(i-1)/dim)
    freqs = 1.0 / (theta ** (torch.arange(0, dim, 2)[: (dim // 2)].float() / dim))
    t = torch.arange(end, device=freqs.device)  # Rentang posisi [0, 1, ..., end-1]
    freqs = torch.outer(t, freqs).float()       # [end, dim // 2]
    # Representasikan sebagai bilangan kompleks e^(i * theta) = cos(theta) + i*sin(theta)
    freqs_cis = torch.polar(torch.ones_like(freqs), freqs)  # Bentuk kompleks
    return freqs_cis

def apply_rotary_emb(xq: torch.Tensor, xk: torch.Tensor, freqs_cis: torch.Tensor):
    """
    Terapkan rotasi kompleks pada Query dan Key.
    xq: [batch_size, seq_len, n_local_heads, head_dim]
    """
    # Bentuk kembali komponen 2D ke dalam domain kompleks
    # [B, S, H, D] -> [B, S, H, D//2, 2] -> complex [B, S, H, D//2]
    xq_ = torch.view_as_complex(xq.float().reshape(*xq.shape[:-1], -1, 2))
    xk_ = torch.view_as_complex(xk.float().reshape(*xk.shape[:-1], -1, 2))
    
    # Slice frekuensi sesuai panjang sekuens aktual
    # [S, D//2] -> [1, S, 1, D//2]
    freqs_cis = freqs_cis[:xq.shape[1]].unsqueeze(0).unsqueeze(2)
    
    # Perkalian kompleks: (a + bi)(c + di) merepresentasikan rotasi 2D
    xq_out = torch.view_as_real(xq_ * freqs_cis).flatten(3)
    xk_out = torch.view_as_real(xk_ * freqs_cis).flatten(3)
    
    return xq_out.type_as(xq), xk_out.type_as(xk)

# Verifikasi Sederhana
if __name__ == "__main__":
    B, S, H, D = 1, 4, 2, 64
    q = torch.randn(B, S, H, D)
    k = torch.randn(B, S, H, D)
    cis = precompute_freqs_cis(D, 16)
    q_rot, k_rot = apply_rotary_emb(q, k, cis)
    print(f"Bentuk Q asal: {q.shape}, Bentuk Q setelah RoPE: {q_rot.shape}")
    assert q.shape == q_rot.shape
```

### 7.2 Practical Example: Production-Grade GQA Layer dengan Dynamic In-Memory Cache

Berikut implementasi modul PyTorch yang mereplikasi layer Grouped-Query Attention lengkap dengan penanganan cache autoregresif, broadcast $K/V$ ke head $Q$, dan pemisahan komputasi *Pre-fill* vs *Decode*.

```python
import torch
import torch.nn as nn
import torch.nn.functional as F
import math
from typing import Optional, Tuple

class GroupedQueryAttention(nn.Module):
    """
    Implementasi Grouped-Query Attention (GQA) sesuai spesifikasi arsitektur Llama 3 / Mistral.
    """
    def __init__(
        self,
        d_model: int,
        n_heads: int,
        n_kv_heads: int,
        max_batch_size: int,
        max_seq_len: int,
        device: Optional[torch.device] = None,
        dtype: Optional[torch.dtype] = None
    ):
        super().__init__()
        self.d_model = d_model
        self.n_heads = n_heads
        self.n_kv_heads = n_kv_heads
        self.n_rep = n_heads // n_kv_heads  # Faktor duplikasi K/V
        self.head_dim = d_model // n_heads

        assert d_model % n_heads == 0, "d_model harus habis dibagi n_heads"
        assert n_heads % n_kv_heads == 0, "n_heads harus kelipatan genap dari n_kv_heads"

        # Linear Projections
        self.q_proj = nn.Linear(d_model, n_heads * self.head_dim, bias=False, device=device, dtype=dtype)
        self.k_proj = nn.Linear(d_model, n_kv_heads * self.head_dim, bias=False, device=device, dtype=dtype)
        self.v_proj = nn.Linear(d_model, n_kv_heads * self.head_dim, bias=False, device=device, dtype=dtype)
        self.out_proj = nn.Linear(n_heads * self.head_dim, d_model, bias=False, device=device, dtype=dtype)

        # Static Allocation untuk KV Cache (Simulasi State Engine)
        # Dimensi: [Batch, Max_Seq, Num_KV_Heads, Head_Dim]
        cache_shape = (max_batch_size, max_seq_len, n_kv_heads, self.head_dim)
        self.register_buffer("cache_k", torch.zeros(cache_shape, device=device, dtype=dtype), persistent=False)
        self.register_buffer("cache_v", torch.zeros(cache_shape, device=device, dtype=dtype), persistent=False)

    def _repeat_kv(self, x: torch.Tensor) -> torch.Tensor:
        """
        Ekspansi head Key/Value agar menyamai jumlah Query heads.
        Bentuk input: [B, S, H_kv, D] -> Output: [B, S, H_q, D]
        """
        if self.n_rep == 1:
            return x
        bs, slen, n_kv_heads, head_dim = x.shape
        return (
            x[:, :, :, None, :]
            .expand(bs, slen, n_kv_heads, self.n_rep, head_dim)
            .reshape(bs, slen, n_kv_heads * self.n_rep, head_dim)
        )

    def forward(
        self,
        x: torch.Tensor,
        start_pos: int,
        freqs_cis: torch.Tensor,
        mask: Optional[torch.Tensor] = None
    ) -> torch.Tensor:
        bsz, seqlen, _ = x.shape

        # 1. Proyeksi Linear
        xq = self.q_proj(x).view(bsz, seqlen, self.n_heads, self.head_dim)
        xk = self.k_proj(x).view(bsz, seqlen, self.n_kv_heads, self.head_dim)
        xv = self.v_proj(x).view(bsz, seqlen, self.n_kv_heads, self.head_dim)

        # 2. Aplikasi Rotary Positional Embedding (RoPE)
        # Ambil subset freqs_cis berdasarkan posisi absolut
        freqs_cis_sub = freqs_cis[start_pos : start_pos + seqlen]
        xq, xk = apply_rotary_emb(xq, xk, freqs_cis_sub)

        # 3. Update KV Cache
        # Memperbarui cache secara in-place di VRAM
        self.cache_k[:bsz, start_pos : start_pos + seqlen] = xk
        self.cache_v[:bsz, start_pos : start_pos + seqlen] = xv

        # Ambil seluruh riwayat context sampai titik sekarang
        keys = self.cache_k[:bsz, : start_pos + seqlen]
        values = self.cache_v[:bsz, : start_pos + seqlen]

        # 4. Repeat KV heads jika menggunakan GQA (Broadcast)
        keys = self._repeat_kv(keys)      # [bsz, total_len, n_heads, head_dim]
        values = self._repeat_kv(values)  # [bsz, total_len, n_heads, head_dim]

        # Transpose untuk komputasi batched matmul: [bsz, n_heads, seqlen, head_dim]
        xq = xq.transpose(1, 2)
        keys = keys.transpose(1, 2)
        values = values.transpose(1, 2)

        # 5. Scaled Dot-Product Attention
        scores = torch.matmul(xq, keys.transpose(-2, -1)) / math.sqrt(self.head_dim)
        
        if mask is not None:
            scores = scores + mask  # Tambahkan causal attention mask

        scores = F.softmax(scores.float(), dim=-1).type_as(xq)
        output = torch.matmul(scores, values)  # [bsz, n_heads, seqlen, head_dim]

        # 6. Reshape dan Output Projection
        output = output.transpose(1, 2).contiguous().view(bsz, seqlen, -1)
        return self.out_proj(output)
```

---

## 8. Real World Case Study (Enterprise Scale)

### 8.1 Skenario Kasus
Sebuah platform perbankan multinasional menggelar sistem *Financial Agentic Copilot* menggunakan arsitektur model Llama-3-70B FP16. Layanan ini melayani **1.000 concurrent analyst**. Rata-rata prompt adalah 4.000 token dan menghasilkan 500 token jawaban.

### 8.2 Bottleneck yang Ditemukan
Saat deployment awal dengan serving engine konvensional (menggunakan naive dynamic allocation):
1. **OOM Crash Berulang**: Server crash karena GPU out-of-memory meskipun rata-rata penggunaan VRAM hanya tercatat 65%. Analisis mendalam menunjukkan fragmentasi eksternal memori mencegah alokasi *context-window* baru.
2. **Krisis Kapasitas KV Cache**:
   - Arsitektur Llama-3-70B: $H_Q = 64, H_{KV} = 8, d_k = 128, \text{Layers} = 80$.
   - Hitungan memori KV Cache FP16 (2 byte) per token:
     $$\text{KV Size per Token} = 2 \times (\text{layers}) \times (2 \times H_{KV} \times d_k) \text{ bytes}$$
     $$\text{KV Size per Token} = 2 \times 80 \times (2 \times 8 \times 128) = 327.680 \text{ bytes} \approx 320 \text{ KB/token}$$
   - Untuk 1 sesi (4.500 token): $4.500 \times 320 \text{ KB} = 1.44 \text{ GB}$ VRAM murni hanya untuk KV Cache 1 user.
   - 1.000 concurrent user = butuh $1.440 \text{ GB}$ VRAM. Jika menggunakan node 8x NVIDIA H100 (total 640 GB VRAM), sistem **defisit 800+ GB memori** bahkan sebelum menghitung bobot model (140 GB).

### 8.3 Solusi Arsitektural Produksi
Tim Principal AI Engineer merancang restrukturisasi engine inferensi:
1. **Migrasi ke PagedAttention (vLLM/TensorRT-LLM Engine)**: Menghilangkan alokasi pra-alokasi statis. Pemanfaatan memori fisik naik menjadi 96% tanpa fragmentasi.
2. **Quantization KV Cache ke FP8**: Mengompresi ukuran KV Cache dari 16-bit (2 bytes) ke 8-bit (1 byte). Ukuran per user turun dari $1.44 \text{ GB}$ menjadi $0.72 \text{ GB}$.
3. **Chunked Prefill & Continuous Batching**: Permintaan tidak lagi diantrekan secara kaku (*static batching*). Token baru disisipkan secara dinamis ke batch yang sedang berjalan pada level iterasi token (*iteration-level scheduling*).
4. **Hasil**: Kapasitas *concurrency* melonjak dari 150 request menjadi 1.000+ request stabil pada cluster 2x 8x-H100, menurunkan TTFT sebesar 54% dan biaya infrastruktur per jam sebesar 60%.

---

## 9. Trade-offs

| Dimensi | Opsi A: MHA (FP16 KV) | Opsi B: GQA (FP16 KV) | Opsi C: GQA + FP8 Paged KV Cache |
|---|---|---|---|
| **Kapasitas Representasi** | Maksimal (Head Query terisolasi penuh). | Sangat Tinggi (~99% akurasi MHA). | Tinggi (Potensi degradasi presisi minor pada penalaran matematis kompleks). |
| **Footprint VRAM KV Cache** | Sangat Besar (Basis referensi 100%). | Turun 75% - 87.5% dibanding MHA. | Turun 87.5% - 93.75% dibanding MHA. |
| **Max Concurrent Concurrency** | Rendah (Cepat OOM saat long context). | Tinggi. | Sangat Tinggi (3x - 5x lipat dibanding baseline). |
| **Hardware Overhead** | Rendah (Kernel komputasi standar). | Rendah (Memerlukan implementasi broadcast). | Memerlukan Tensor Cores modern (misal: Ada Lovelace / Hopper) untuk dekuantisasi FP8 hardware-accelerated. |
| **Kompleksitas Debugging** | Rendah. | Sedang. | Tinggi (Melibatkan scaling factor kuantisasi per tensor/channel). |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Kesalahan Fatal: Mengabaikan Posisi Frekuensi pada RoPE saat Decode
- **Symptom**: Model menghasilkan keluaran koheren pada token pertama (saat pre-fill), lalu menghasilkan teks yang berulang (*looping gibberish*) pada token-token berikutnya.
- **Root Cause**: Memberikan index offset posisi $0$ berulang-ulang pada fase decode, alih-alih memberikan offset index posisi absolut `start_pos = current_context_length`.
- **Solusi**: Pastikan variabel tracking posisi (`start_pos`) selalu bertambah secara monotonik untuk setiap step autoregresif decode:
  ```python
  # SALAH
  freqs = freqs_cis[0 : 1] # Selalu menganggap token baru berada di indeks 0
  # BENAR
  freqs = freqs_cis[current_seq_len : current_seq_len + 1]
  ```

### 10.2 KV Cache Memory Fragmentation Leakage
- **Symptom**: Driver CUDA melempar error `CUDA out of memory` mendadak padahal metrik monitoring utilisasi GPU vLLM/Triton menunjukkan pemakaian VRAM masih 70%.
- **Root Cause**: Terjadi *memory leak* pada tensor referensi Python yang menahan pointer *block table*, sehingga Garbage Collector PyTorch tidak melepaskan physical block kembali ke pool bebas.
- **Solusi**: Gunakan profiling memory via `torch.cuda.memory_allocated()` dan pastikan lifecycle tensor PyTorch dibersihkan secara eksplisit via `del` atau blok *context manager* RAII.

### 10.3 Inkompatibilitas Skew Dot-Product pada FlashAttention
- **Symptom**: Hasil output inferensi menghasilkan nilai `NaN` setelah konteks mencapai batas tertentu.
- **Root Cause**: Penggunaan scaling factor attention $\frac{1}{\sqrt{d_k}}$ terlewat atau tipe data intermediate akumulasi float16 mengalami numeric underflow/overflow sebelum Softmax.
- **Solusi**: Selalu lakukan kalkulasi Softmax dalam presisi FP32 (float), kemudian cast kembali output hasil dot product ke FP16/BF16.

---

## 11. Best Practices (Production Checklist)

- [ ] **GQA Validation**: Pastikan jumlah Head Query terbagi rata dengan Head KV ($H_Q \pmod{H_{KV}} == 0$).
- [ ] **RoPE Base Frequency Scaling**: Jika mengekspansi context window melampaui pretraining limit (misal: dari 8k ke 32k), terapkan penyesuaian RoPE base frequency via rumus RoPE NTK-aware atau YaRN:
  $$\theta' = \theta \times \alpha^{\frac{d}{d-2}}$$
- [ ] **KV Cache Pre-allocation Boundary**: Jangan menginisialisasi KV Cache menggunakan array Python dinamis (`list.append(tensor)`). Selalu alokasikan memori GPU kontinu dalam bentuk buffer tensor tetap atau blok *PagedAttention*.
- [ ] **Precision Enforcement**: Jalankan operasi linear projections dalam FP16/BF16, tetapi pertahankan skalar pembagi dan akumulator Softmax pada FP32 guna menghindari *numerical instability*.
- [ ] **Warm-up Kernel**: Lakukan eksekusi *dummy inference* 1-3 kali sebelum mengekspos endpoint ke jaringan produksi untuk memicu kompilasi kernel JIT PyTorch / CUDA graph loading.

---

## 12. Hands-on Practice

Buat struktur direktori berikut di lingkungan kerja Anda:

```bash
mkdir -p hands-on/m02
cd hands-on/m02
touch inference_benchmark.py
```

Implementasikan skrip profiling performa komparasi: **Vanilla KV-Cache Autoregressive vs Optimized GQA KV-Cache Engine**.

Isi file `hands-on/m02/inference_benchmark.py`:

```python
import time
import torch
import torch.nn as nn
import torch.nn.functional as F

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

def measure_memory_and_latency(func, *args, **kwargs):
    """Utility untuk mengukur peak memory dan eksekusi GPU latency."""
    torch.cuda.reset_peak_memory_stats()
    torch.cuda.synchronize()
    start_time = time.perf_counter()
    
    out = func(*args, **kwargs)
    
    torch.cuda.synchronize()
    latency = time.perf_counter() - start_time
    mem_used = torch.cuda.max_memory_allocated() / (1024 ** 2)  # MB
    return out, latency, mem_used

# Baseline Naive MHA (No KV Cache - Recomputes entire sequence)
def naive_generate(model_layer, input_tokens, steps=32):
    """Simulasi eksekusi tanpa KV Cache (Kuadratik FLOPs)."""
    curr_tokens = input_tokens
    for _ in range(steps):
        # Merekomputasi seluruh history token setiap kali 1 token baru dibuat
        scores = torch.matmul(curr_tokens, curr_tokens.transpose(-2, -1))
        attn = F.softmax(scores, dim=-1)
        curr_tokens = torch.cat([curr_tokens, curr_tokens[:, -1:, :]], dim=1)
    return curr_tokens

# Optimized Engine (Simulasi KV-Cache Step Autoregressive)
def cached_generate(k_cache, v_cache, new_token, current_pos, steps=32):
    """Simulasi fase decode konstan O(1) FLOPs per step via KV-Cache."""
    bsz, _, d_k = new_token.shape
    for i in range(steps):
        pos = current_pos + i
        k_cache[:, pos:pos+1, :] = new_token
        v_cache[:, pos:pos+1, :] = new_token
        
        # Read historical sequence
        k_context = k_cache[:, :pos+1, :]
        v_context = v_cache[:, :pos+1, :]
        
        # Attention Decode (Query hanya 1 token baru)
        score = torch.matmul(new_token, k_context.transpose(-2, -1))
        attn = F.softmax(score, dim=-1)
        out = torch.matmul(attn, v_context)
        new_token = out
    return k_cache

if __name__ == "__main__":
    if not torch.cuda.is_available():
        print("[WARNING] CUDA tidak terdeteksi. Script hands-on ini didesain untuk profiling GPU VRAM.")
        exit(0)

    print(f"=== Menjalankan Profiling Inferensi pada: {torch.cuda.get_device_name(0)} ===")
    
    B, S, D = 4, 1024, 4096
    steps_to_decode = 128
    
    # Inisialisasi Mock Data
    init_tokens = torch.randn(B, S, D, device=device, dtype=torch.float16)
    new_token = torch.randn(B, 1, D, device=device, dtype=torch.float16)
    
    # 1. Benchmark Naive Non-Cached Generation
    print("\n[Uji 1: Naive Full Recomputation (Tanpa KV Cache)]")
    _, lat_naive, mem_naive = measure_memory_and_latency(
        naive_generate, None, init_tokens, steps_to_decode
    )
    print(f"Latency: {lat_naive:.4f} sec | Peak VRAM: {mem_naive:.2f} MB")

    # 2. Benchmark Pre-allocated Optimized KV Cache
    print("\n[Uji 2: Stateful KV Cache Engine (Autoregressive Optimized)]")
    k_cache = torch.zeros(B, S + steps_to_decode, D, device=device, dtype=torch.float16)
    v_cache = torch.zeros(B, S + steps_to_decode, D, device=device, dtype=torch.float16)
    k_cache[:, :S, :] = init_tokens
    v_cache[:, :S, :] = init_tokens

    _, lat_cached, mem_cached = measure_memory_and_latency(
        cached_generate, k_cache, v_cache, new_token, S, steps_to_decode
    )
    print(f"Latency: {lat_cached:.4f} sec | Peak VRAM: {mem_cached:.2f} MB")
    
    print("\n=== RINGKASAN EFISIENSI ===")
    print(f"Peningkatan Kecepatan: {lat_naive / lat_cached:.2f}x lebih cepat")
```

---

## 13. Exercises

### Level Easy
Tuliskan sebuah fungsi PyTorch `compute_kv_cache_size(layers: int, h_kv: int, d_k: int, max_seq: int, bsz: int, dtype: torch.dtype) -> float` yang mengembalikan total ukuran memori yang dibutuhkan oleh Key-Value Cache dalam satuan Gigabytes (GB).

### Level Medium
Modifikasi layer `GroupedQueryAttention` dari seksi 7.2 untuk mendukung *Sliding Window Attention*. Modul harus menerima parameter baru `sliding_window_size: int`, dan saat fase decode maupun pre-fill, mask attention hanya mengizinkan token memperhatikan token masa lalu maksimal sejauh jarak rentang jendela tersebut.

### Level Hard
Rancang modul `MiniPagedAttentionBlockManager` murni dengan PyTorch CPU/CUDA yang mengimplementasikan metode:
1. `allocate(request_id: str, num_tokens: int) -> List[int]`: Mengalokasikan sejumlah indeks blok fisik berukuran fixed block (16 tokens per block) dari pool bebas.
2. `append_slot(request_id: str) -> Tuple[int, int]`: Mengembalikan pasangan koordinat `(block_number, block_offset)` untuk menaruh 1 token decode baru. Mengalokasikan blok fisik baru dari pool jika blok aktif telah terisi penuh.
3. `free(request_id: str) -> None`: Mengembalikan seluruh blok fisik milik request kembali ke daftar pool bebas.

---

## 14. Challenge

### Studi Kasus: "Zero-Downtime Dynamic Context-Aware Gateway"
Sebuah perusahaan finansial membutuhkan Gateway Model Serving yang mampu menangani request dengan panjang konteks bervariasi secara ekstrem (antara 500 token hingga 128.000 token per request) secara multi-tenant.

**Problem Statement:**
Jika arsitektur inferensi menggunakan sistem alokasi memori linear biasa, request berukuran 128k token akan langsung memicu fragmentasi memori katastropik dan menyebabkan *Head-of-Line (HoL) Blocking*, di mana request kecil (500 token) terhambat selama puluhan detik menunggu fase *Pre-fill* request 128k token selesai.

**Tantangan Arsitektur Anda:**
Rancang arsitektur level sistem (sertakan dokumen arsitektur dan pseudocode/implementasi logika orkestrasi) yang mengintegrasikan:
1. **Chunked Pre-fills**: Memecah fase pre-fill request 128k token ke dalam chunks kecil (misal per 512 token) sehingga fase *Decode* dari batch tenant lain dapat diselipkan secara bergantian (*interleaved execution*).
2. **Dynamic Prefix Caching**: Jika 100 tenant mengirimkan dokumen regulasi master yang identik (misal file audit 50k token) dengan pertanyaan berbeda, Gateway harus mengenali prefix hash token tersebut dan menggunakan referensi *physical block* KV yang sama secara read-only (Copy-on-Write semantics) tanpa merekomputasi pre-fill.
3. Rancang mekanisme pemulihan jika VRAM fisik mencapai utilisasi 99% (*GPU Block Swapping* ke Host RAM sistem via PCIe).

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: Konsep Dasar (Basic)
1. Apa alasan komputasi fase Decode pada model autoregresif bersifat *Memory-Bandwidth Bound* ketimbang *Compute-Bound*?
2. Dalam representasi RoPE, mengapa kita tidak memerlukan penambahan eksplisit vektor embedding posisi ke representasi input token ($x + pos$)?
3. Jika model memiliki 32 Query Heads dan dikonfigurasi menggunakan Grouped-Query Attention dengan 4 KV Groups, berapakah jumlah Query Heads yang dilayani oleh setiap KV Head?
4. Apa yang dimaksud dengan *Internal Memory Fragmentation* dalam konteks naif KV Cache management?
5. Mengapa format floating point FP8 (E4M3 atau E5M2) sangat diminati untuk inferensi KV Cache modern dibandingkan INT8 standar?

### Bagian B: Analisis & Mekanisme (Intermediate)
6. Jelaskan secara matematis bagaimana properti dot-product Query dan Key pada RoPE mempertahankan informasi jarak relatif $m - n$ antar token.
7. Mengapa penghematan memori dari FlashAttention tidak tercermin pada ukuran alokasi KV Cache yang disimpan di VRAM?
8. Bagaimana *Continuous Batching* (Iteration-level scheduling) mengatasi inefisiensi *Static Batching* tradisional?
9. Apa perbedaan esensial dalam transfer data fisik antara operasi attention naif ($O(N^2)$ akses HBM) vs FlashAttention Tiling di SRAM GPU?
10. Pada kondisi skenario inferensi apa penggunaan Multi-Query Attention (MQA) dapat memicu degradasi akurasi reasoning yang nyata dibandingkan Multi-Head Attention (MHA)?

### Bagian C: Kasus Troubleshooting Produksi
11. **Skenario Kasus 1**: Sistem LLM serving enterprise Anda mengalami degradasi throughput (token per detik) yang parah setiap kali panjang dokumen yang dimasukkan melampaui 8.000 token, meskipun utilisasi komputasi GPU (GPU Core Engine) berada di bawah 40%. Profiling menunjukkan waktu terbanyak dihabiskan pada kernel memory load. Identifikasi akar masalahnya dan rekomendasikan dua modifikasi arsitektur inferensi.
12. **Skenario Kasus 2**: Sebuah model Llama fine-tuned yang diekspor ke inference engine menghasilkan respons repetitif tanpa henti setelah token ke-10 pada fase serving, padahal selama evaluasi validasi offline menggunakan HuggingFace pipeline model menghasilkan teks dengan sempurna. Analisis di mana letak potensi *off-by-one bug* dalam penanganan KV Cache atau RoPE offset-nya.
13. **Skenario Kasus 3**: Layanan Anda mengalami spike latensi *Time-to-First-Token* (TTFT) sebesar 12 detik saat 5 user secara bersamaan mengirim dokumen legal berukuran 32k token, yang menyebabkan antrean timeout pada ratusan request decode pendek milik user lain. Bagaimana strategi *Chunked Prefill* mengatasi problem HoL blocking tersebut secara spesifik?

---

## 16. Summary

1. **Dualitas Fase Inferensi**: Fase Pre-fill bersifat *Compute-bound* paralel dengan Arithmetic Intensity tinggi, sedangkan fase Decode bersifat autoregresif, serial, dan sangat *Memory-bandwidth bound*. Optimalisasi LLM di ranah produksi berfokus pada reduksi lalu lintas pembacaan memori antara HBM dan SRAM GPU.
2. **Evolusi Arsitektur Attention**: Grouped-Query Attention (GQA) telah menjadi standar de-facto arsitektur model modern (seperti Llama 3) karena mampu memangkas volume pemuatan KV Cache hingga 87.5% dibandingkan MHA, mengembalikan kapasitas throughput inferensi tanpa mengorbankan kapasitas pemodelan relasi multi-head.
3. **Pemberian Posisi Modern**: Rotary Position Embedding (RoPE) memetakan orientasi token melalui rotasi kompleks 2D yang memungkinkan pelestarian invarian jarak spasial relatif antar token, membebaskan transformer dari belenggu konteks panjang statis.
4. **PagedAttention & Virtual Paging**: Dengan memecah konteks panjang ke dalam blok-blok fisik non-kontigu, PagedAttention mengeliminasi fragmentasi internal dan eksternal memori GPU, mengubah batas alokasi teoritis menjadi efisiensi throughput layanan skala enterprise.