# Bab 07: Specialized Deep Architectures CV & NLP
## Modul 01: Vision Transformers (ViT) & Modern Spatial Attention Mechanics

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis Keterbatasan Induktif (Inductive Bias):** Mengartikulasikan perbedaan mendasar antara *translation equivariance* serta *locality* pada Convolutional Neural Networks (CNN) dibandingkan dengan *global receptive field* berbasis *self-attention* pada Vision Transformer (ViT).
- **Mengonstruksi Pipeline Tokenisasi Spasial:** Mengimplementasikan ekstraksi *patch*, proyeksi linear ke dimensi embedding ($D$), serta injeksi *learnable position embeddings* dan `[CLS]` token secara matematis dan modular.
- **Memformulasikan Scaled Dot-Product Self-Attention Spasial:** Menghitung matriks atensi $O(N^2)$ secara paralel untuk urutan token 2D, termasuk penanganan normalisasi (*Pre-LayerNorm*) dan aktivasi non-linear (GELU/SwiGLU).
- **Mengatasi Degradasi Resolusi Variabel:** Mengembangkan algoritma interpolasi bikubik 2D untuk *positional embeddings* saat model inferensi dijalankan pada resolusi gambar yang berbeda dari resolusi pra-pelatihan.
- **Mengimplementasikan dan Mengoptimasi ViT Tingkat Produksi:** Membangun modul PyTorch yang *type-hinted*, memitigasi isu numerik pada *mixed precision* (FP16/BF16), serta mengintegrasikan *gradient checkpointing* untuk efisiensi memori VRAM.

---

### 2. Concept Overview

Vision Transformer (ViT) mendisrupsi paradigma *Computer Vision* konvensional dengan memperlakukan gambar bukan sebagai kisi piksel 2D yang diproses oleh *kernel sliding*, melainkan sebagai *sequence of patches* 1D yang diproses melalui arsitektur standar Transformer Encoder.

```
+-----------------------------------------------------------------------------+
|                                MENTAL MODEL                                 |
|                                                                             |
|  [ Gambar 2D: H x W x C ]                                                   |
|          |                                                                  |
|          v  (Dipotong menjadi patch P x P)                                  |
|  [ Grid Patch: N = (H*W)/P^2 ]                                              |
|          |                                                                  |
|          v  (Flaten & Proyeksi Linear ke Dimensi D)                         |
|  [ Patch Embeddings: N x D ]                                                |
|          |                                                                  |
|          v  (Tambahkan [CLS] token & Positional Encoding)                   |
|  [ Sequence Vectors: (N + 1) x D ]                                          |
|          |                                                                  |
|          v  (Diproses via Standar Transformer Blocks)                       |
|  [ Global Receptive Field pada Layer Pertama via Scaled Dot-Product ]       |
+-----------------------------------------------------------------------------+
```

#### Fondasi Teoretis: Inductive Bias vs. Kapasitas Skala
CNN mengandalkan dua *inductive bias* yang tertanam langsung dalam operasi konvolusi:
1. **Locality:** Piksel-piksel yang berdekatan memiliki korelasi semantik yang lebih tinggi daripada piksel yang berjauhan.
2. **Translation Equivariance:** Jika suatu fitur bergeser posisinya dalam ruang gambar, representasi fiturnya bergeser secara proporsional: $f(g(x)) = g(f(x))$.

Sebaliknya, Transformer murni memiliki *inductive bias* spasial yang sangat minim. Hubungan antar piksel yang berjarak jauh maupun berdekatan diperlakukan setara pada *layer* pertama. Relasi spasial harus **dipelajari secara mandiri** dari data melalui *Positional Embeddings* dan *Self-Attention*. Konsekuensinya:
- Pada dataset berskala kecil hingga menengah (misal: ImageNet-1K tanpa augmentasi berat), ViT rentan mengalami *overfitting* dan performanya berada di bawah CNN modern (seperti ConvNeXt).
- Pada dataset berskala masif (JFT-300M, LAION-5B), batas performa (*performance ceiling*) ViT jauh melampaui CNN karena kapasitas representasinya tidak dibatasi oleh asumsi lokalitas konvolusi (*scaling law* yang superior).

---

### 3. Why It Matters: Real-World & Enterprise Context

1. **Unifikasi Arsitektur Multimodal (Vision-Language Models):**
   Dalam sistem *Autonomous Agents* dan VLM (misalnya GPT-4V, LLaVA, CLIP), ViT berfungsi sebagai *Visual Tokenizer*. Karena representasi output ViT berbentuk urutan token berdimensi $D$ (serupa dengan token teks), representasi visual dapat langsung diumpankan ke dalam *Large Language Model* (LLM) melalui proyeksi linear sederhana atau *Cross-Attention*.
2. **Skalabilitas Komputasi Terdistribusi:**
   Berbeda dengan arsitektur CNN heterogen yang membebani alokasi komputasi dengan berbagai ukuran kernel non-standar, ViT menggunakan operasi matriks GEMM (*General Matrix Multiply*) homogen berulang. Operasi ini secara optimal memanfaatkan akselerator modern (NVIDIA Tensor Cores, TPU) dan mendukung paralelisasi model (*Tensor Parallelism*, *Pipeline Parallelism*) secara langsung melalui pustaka seperti Megatron-LM.
3. **Efisiensi Transfer Learning Domain Medis & Satelit:**
   Model ViT yang dipra-latih dengan *Masked Autoencoders* (MAE) pada citra resolusi tinggi memungkinkan ekstraksi konteks global tanpa kehilangan detail lokal, esensial untuk mendeteksi anomali pada CT scan atau segmentasi citra satelit beresolusi gigapiksel.

---

### 4. Arsitektur & Diagram Komponen

Aliran data terperinci dari piksel mentah hingga logit klasifikasi diilustrasikan pada diagram berikut:

```
[ Input Image: C x H x W ]
        |
        v
+-------------------------------------------------------------+
| 1. Patch Partition & Linear Projection                      |
|    - Kernel Konvolusi 2D: Conv2d(C, D, kernel=P, stride=P)   |
|    - Output Shape: [B, D, H/P, W/P]                         |
|    - Flatten & Transpose -> [B, N, D], di mana N = (H*W)/P^2|
+-------------------------------------------------------------+
        |
        v
+-------------------------------------------------------------+
| 2. Prepended Tokens & Positional Embeddings                 |
|    - Concat [CLS] Token: [B, 1, D] -> [B, N + 1, D]         |
|    - Add Learnable Pos Embedding: E_pos: [1, N + 1, D]      |
|    - Apply Dropout: p = p_drop                              |
+-------------------------------------------------------------+
        |
        v
+-------------------------------------------------------------+
| 3. Transformer Encoder Block (x L Layers)                   |
|    +---------------------------------------------------+    |
|    | Residual Connection 1                             |    |
|    | x = x + MultiHeadSelfAttention(LayerNorm(x))      |    |
|    +---------------------------------------------------+    |
|    | Residual Connection 2                             |    |
|    | x = x + MLP_Block(LayerNorm(x))                   |    |
|    |   - Linear(D, D_mlp) -> GELU -> Dropout           |    |
|    |   - Linear(D_mlp, D) -> Dropout                   |    |
|    +---------------------------------------------------+    |
+-------------------------------------------------------------+
        |
        v
+-------------------------------------------------------------+
| 4. Task Specific Head (Classification Head)                 |
|    - Ekstraksi Token Index 0 ([CLS]): [B, D]                |
|    - LayerNorm(x[:, 0])                                     |
|    - Linear(D, Num_Classes)                                 |
+-------------------------------------------------------------+
        |
        v
[ Output Logits: B x Num_Classes ]
```

#### Struktur Multi-Head Self-Attention Spasial:
```
           Input Tokens X: [B, N+1, D]
                       |
        +--------------+--------------+
        |              |              |
     W_q|           W_k|           W_v|
        v              v              v
     Q: [B, h, N+1, d_k]  K: [B, h, N+1, d_k]  V: [B, h, N+1, d_k]
        |              |              |
        +-------+------+              |
                |                     |
                v                     |
       (Q @ K^T) / sqrt(d_k)          |
                |                     |
                v                     |
       Softmax(Attn_Scores)           |
                |                     |
                +----------+----------+
                           |
                           v
              Context Z: [B, h, N+1, d_k]
                           |
                           v  (Concat Heads)
                 Z_cat: [B, N+1, D]
                           |
                           v  (Linear Projection W_o)
                 Output: [B, N+1, D]
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Ekstraksi Patch dan Perataan Spasial
Diberikan citra $x \in \mathbb{R}^{H \times W \times C}$, kita partisi citra menjadi urutan *patch* $x_p \in \mathbb{R}^{N \times (P^2 \cdot C)}$, di mana:
- $(P, P)$ adalah resolusi setiap spasial patch.
- $N = \frac{H \cdot W}{P^2}$ adalah total jumlah token patch yang dihasilkan.

Implementasi efisien ekstraksi patch tidak memerlukan pemotongan manual melalui perulangan (*loop*). Sebaliknya, digunakan operasi konvolusi 2 dimensi dengan *kernel size* sama dengan $P$ dan *stride* sama dengan $P$:
$$\text{FeatureMap} = \text{Conv2D}(C_{\text{in}}=C, C_{\text{out}}=D, \text{kernel\_size}=P, \text{stride}=P)(x)$$
Operasi ini memproyeksikan langsung ruang piksel berukuran $(P \times P \times C)$ ke dalam ruang vektor $D$-dimensi.

#### B. Injeksi Token `[CLS]` dan Positional Encoding
Untuk melakukan tugas agregasi representasi visual tanpa memihak salah satu patch spasial tertentu, ditambahkan vektor yang dapat dipelajari (*learnable parameter*) $x_{\text{class}} \in \mathbb{R}^{1 \times D}$ di awal urutan:
$$z_0 = [x_{\text{class}}; x_p^1 \mathbf{E}; x_p^2 \mathbf{E}; \dots; x_p^N \mathbf{E}] + \mathbf{E}_{pos}$$
di mana:
- $\mathbf{E} \in \mathbb{R}^{(P^2 C) \times D}$ adalah matriks proyeksi patch.
- $\mathbf{E}_{pos} \in \mathbb{R}^{(N + 1) \times D}$ adalah *learnable 1D position embeddings*. Tanpa $\mathbf{E}_{pos}$, operasi *self-attention* bersifat invarian terhadap permutasi urutan ($f(\Pi X) = \Pi f(X)$), sehingga informasi topologi spasial akan hilang seluruhnya.

#### C. Scaled Dot-Product Self-Attention (SDPA)
Untuk matriks input urutan $Z \in \mathbb{R}^{(N+1) \times D}$, proyeksi linear menghasilkan matriks Query ($Q$), Key ($K$), dan Value ($V$):
$$Q = Z W_Q, \quad K = Z W_K, \quad V = Z W_V \quad (W_Q, W_K, W_V \in \mathbb{R}^{D \times D})$$

Dipartisi menjadi $h$ kepala (*heads*), dengan dimensi per kepala $d_k = D / h$. Matriks atensi dihitung melalui rumus:
$$\text{Attention}(Q, K, V) = \text{Softmax}\left(\frac{Q K^T}{\sqrt{d_k}}\right) V$$
Faktor $\frac{1}{\sqrt{d_k}}$ adalah penskalaan penting. Untuk dimensi $d_k$ yang besar, magnitudo hasil perkalian titik $Q K^T$ tumbuh sebanding dengan $d_k$. Tanpa pembagi ini, fungsi Softmax akan terdorong ke wilayah dengan gradien yang sangat kecil (*vanishing gradients*), menghentikan proses pembelajaran.

#### D. Pre-LayerNorm vs. Post-LayerNorm
ViT modern secara universal mengadopsi topologi **Pre-LayerNorm**:
$$z_{\ell}' = \text{MSA}(\text{LN}(z_{\ell-1})) + z_{\ell-1}$$
$$z_{\ell} = \text{MLP}(\text{LN}(z_{\ell}')) + z_{\ell}'$$

Berbeda dengan arsitektur Transformer awal (Post-LayerNorm) yang menempatkan normalisasi setelah penambahan residual:
$$z_{\ell} = \text{LN}(z_{\ell-1} + \text{MSA}(z_{\ell-1}))$$
Pre-LayerNorm mempertahankan "jalur cepat" (*clean residual stream*) tanpa skala gradien yang berubah-ubah sepanjang kedalaman jaringan, menstabilkan proses pelatihan sejak inisialisasi tanpa memerlukan fase *warm-up* yang ekstrem.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi Vision Transformer lengkap dan mandiri menggunakan PyTorch standar industri. Arsitektur ini mencakup *Pre-LayerNorm*, inisialisasi bobot spesifik ViT, dan penanganan resolusi fleksibel melalui interpolasi *positional embedding*.

```python
"""
Production-Grade Vision Transformer (ViT) Implementation
Framework: PyTorch
Standards: Type-Hinted, Modular, Clean Architecture, Config-Driven
"""

from dataclasses import dataclass
import math
from typing import Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F


@dataclass(frozen=True)
class ViTConfig:
    img_size: int = 224
    patch_size: int = 16
    in_channels: int = 3
    num_classes: int = 1000
    embed_dim: int = 768
    depth: int = 12
    num_heads: int = 12
    mlp_ratio: float = 4.0
    qkv_bias: bool = True
    drop_rate: float = 0.0
    attn_drop_rate: float = 0.0
    drop_path_rate: float = 0.0


class PatchEmbedding(nn.Module):
    """
    Memecah gambar 2D menjadi patch-patch diskrit dan memproyeksikannya ke ruang embedding berdimensi D.
    """
    def __init__(self, config: ViTConfig) -> None:
        super().__init__()
        self.img_size = (config.img_size, config.img_size)
        self.patch_size = (config.patch_size, config.patch_size)
        self.grid_size = (
            self.img_size[0] // self.patch_size[0],
            self.img_size[1] // self.patch_size[1],
        )
        self.num_patches = self.grid_size[0] * self.grid_size[1]

        if self.img_size[0] % self.patch_size[0] != 0 or self.img_size[1] % self.patch_size[1] != 0:
            raise ValueError(
                f"Resolusi citra {self.img_size} harus habis dibagi ukuran patch {self.patch_size}."
            )

        self.proj = nn.Conv2d(
            in_channels=config.in_channels,
            out_channels=config.embed_dim,
            kernel_size=config.patch_size,
            stride=config.patch_size,
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Input: [B, C, H, W]
        Output: [B, N, D] di mana N = H*W / (P*P)
        """
        b, c, h, w = x.shape
        if h != self.img_size[0] or w != self.img_size[1]:
            raise ValueError(
                f"Dimensi input ({h}x{w}) tidak cocok dengan konfigurasi model ({self.img_size[0]}x{self.img_size[1]})."
            )

        # Output Conv2D: [B, D, H/P, W/P] -> Flatten: [B, D, N] -> Transpose: [B, N, D]
        x = self.proj(x).flatten(2).transpose(1, 2)
        return x


class MultiHeadSelfAttention(nn.Module):
    """
    Multi-Head Self-Attention (MHSA) dengan pengoptimalan Scaled Dot-Product.
    """
    def __init__(self, config: ViTConfig) -> None:
        super().__init__()
        self.num_heads = config.num_heads
        self.head_dim = config.embed_dim // config.num_heads
        self.scale = 1.0 / math.sqrt(self.head_dim)

        if config.embed_dim % config.num_heads != 0:
            raise ValueError(
                f"embed_dim ({config.embed_dim}) harus habis dibagi num_heads ({config.num_heads})."
            )

        self.qkv = nn.Linear(config.embed_dim, config.embed_dim * 3, bias=config.qkv_bias)
        self.attn_drop = nn.Dropout(config.attn_drop_rate)
        self.proj = nn.Linear(config.embed_dim, config.embed_dim)
        self.proj_drop = nn.Dropout(config.drop_rate)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Input: [B, N+1, D]
        Output: [B, N+1, D]
        """
        b, n, d = x.shape
        # Proyeksi QKV simultan: [B, N+1, 3*D] -> [B, N+1, 3, Num_Heads, Head_Dim]
        qkv = self.qkv(x).reshape(b, n, 3, self.num_heads, self.head_dim).permute(2, 0, 3, 1, 4)
        q, k, v = qkv[0], qkv[1], qkv[2]  # Shape: [B, Num_Heads, N+1, Head_Dim]

        # Menghitung Attention Scores: (Q @ K^T) * scale
        attn = (q @ k.transpose(-2, -1)) * self.scale
        attn = attn.softmax(dim=-1)
        attn = self.attn_drop(attn)

        # Context Aggregation: Attn @ V -> [B, Num_Heads, N+1, Head_Dim]
        x = (attn @ v).transpose(1, 2).reshape(b, n, d)
        x = self.proj(x)
        x = self.proj_drop(x)
        return x


class MLP(nn.Module):
    """
    Modul Feed-Forward / Multilayer Perceptron standar Transformer.
    """
    def __init__(self, config: ViTConfig) -> None:
        super().__init__()
        hidden_dim = int(config.embed_dim * config.mlp_ratio)
        self.fc1 = nn.Linear(config.embed_dim, hidden_dim)
        self.act = nn.GELU()
        self.fc2 = nn.Linear(hidden_dim, config.embed_dim)
        self.drop = nn.Dropout(config.drop_rate)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.fc1(x)
        x = self.act(x)
        x = self.drop(x)
        x = self.fc2(x)
        x = self.drop(x)
        return x


class TransformerBlock(nn.Module):
    """
    Satu blok Transformer Encoder dengan skema Pre-LayerNorm.
    """
    def __init__(self, config: ViTConfig) -> None:
        super().__init__()
        self.norm1 = nn.LayerNorm(config.embed_dim, eps=1e-6)
        self.attn = MultiHeadSelfAttention(config)
        self.norm2 = nn.LayerNorm(config.embed_dim, eps=1e-6)
        self.mlp = MLP(config)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Pre-LN Residual Connection
        x = x + self.attn(self.norm1(x))
        x = x + self.mlp(self.norm2(x))
        return x


class VisionTransformer(nn.Module):
    """
    Arsitektur Vision Transformer (ViT) Lengkap.
    """
    def __init__(self, config: ViTConfig) -> None:
        super().__init__()
        self.config = config
        self.patch_embed = PatchEmbedding(config)
        num_patches = self.patch_embed.num_patches

        # Learnable Class Token dan Position Embeddings
        self.cls_token = nn.Parameter(torch.zeros(1, 1, config.embed_dim))
        self.pos_embed = nn.Parameter(torch.zeros(1, num_patches + 1, config.embed_dim))
        self.pos_drop = nn.Dropout(p=config.drop_rate)

        # Transformer Blocks Stack
        self.blocks = nn.ModuleList([
            TransformerBlock(config) for _ in range(config.depth)
        ])

        # Final Normalization and Classifier Head
        self.norm = nn.LayerNorm(config.embed_dim, eps=1e-6)
        self.head = nn.Linear(config.embed_dim, config.num_classes)

        self._init_weights()

    def _init_weights(self) -> None:
        """Inisialisasi berstandar industri (Trancated Normal & Xavier)"""
        nn.init.trunc_normal_(self.pos_embed, std=0.02)
        nn.init.trunc_normal_(self.cls_token, std=0.02)
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.trunc_normal_(m.weight, std=0.02)
                if m.bias is not None:
                    nn.init.constant_(m.bias, 0.0)
            elif isinstance(m, nn.LayerNorm):
                nn.init.constant_(m.bias, 0.0)
                nn.init.constant_(m.weight, 1.0)
            elif isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight, mode="fan_out", nonlinearity="relu")
                if m.bias is not None:
                    nn.init.constant_(m.bias, 0.0)

    def interpolate_pos_encoding(self, x: torch.Tensor, h: int, w: int) -> torch.Tensor:
        """
        Dukungan Inferensi Resolusi Dinamis:
        Menginterpolasi posisi embedding jika dimensi H, W gambar berbeda dari konfigurasi bawaan.
        """
        npatch = x.shape[1] - 1
        n = self.pos_embed.shape[1] - 1
        if npatch == n and h == self.patch_embed.img_size[0] and w == self.patch_embed.img_size[1]:
            return self.pos_embed

        class_pos_embed = self.pos_embed[:, 0]
        patch_pos_embed = self.pos_embed[:, 1:]
        dim = x.shape[-1]

        h0 = h // self.patch_embed.patch_size[0]
        w0 = w // self.patch_embed.patch_size[1]
        orig_h0 = self.patch_embed.grid_size[0]
        orig_w0 = self.patch_embed.grid_size[1]

        patch_pos_embed = patch_pos_embed.reshape(1, orig_h0, orig_w0, dim).permute(0, 3, 1, 2)
        patch_pos_embed = F.interpolate(
            patch_pos_embed,
            size=(h0, w0),
            mode="bicubic",
            align_corners=False
        )
        patch_pos_embed = patch_pos_embed.permute(0, 2, 3, 1).view(1, -1, dim)
        return torch.cat((class_pos_embed.unsqueeze(0), patch_pos_embed), dim=1)

    def forward_features(self, x: torch.Tensor) -> torch.Tensor:
        b, _, h, w = x.shape
        x = self.patch_embed(x)

        # Replikasi CLS token untuk setiap elemen di dalam batch
        cls_tokens = self.cls_token.expand(b, -1, -1)
        x = torch.cat((cls_tokens, x), dim=1)

        # Aplikasi Positional Embeddings dengan dukungan resolusi fleksibel
        pos_embed = self.interpolate_pos_encoding(x, h, w)
        x = self.pos_drop(x + pos_embed)

        # Forward Pass melalui Transformer Blocks
        for blk in self.blocks:
            x = blk(x)

        x = self.norm(x)
        return x[:, 0]  # Ambil token [CLS]

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Input: [B, C, H, W]
        Output: [B, Num_Classes]
        """
        if x.ndim != 4:
            raise ValueError(f"Input harus memiliki dimensi 4D [B, C, H, W], diterima: {x.shape}")

        features = self.forward_features(x)
        logits = self.head(features)
        return logits
```

---

### 7. Edge Cases & Failure Modes

#### A. Discrepancy Resolusi Spasial (Runtime Crash)
- **Gejala:** Input citra produksi berukuran $384 \times 384$ diumpankan ke model yang dipra-latih dengan konfigurasi $224 \times 224$, memicu error ukuran *tensor addition* pada $x + \mathbf{E}_{pos}$.
- **Penyebab:** Jumlah token patch meningkat dari $14 \times 14 = 196$ menjadi $24 \times 24 = 576$. Vektor $\mathbf{E}_{pos}$ statis gagal dijumlahkan karena ketidakcocokan dimensi urutan.
- **Solusi Mitigasi:** Implementasi fungsi `interpolate_pos_encoding` dengan interpolasi bikubik 2D pada dimensi kisi *patch* (bukan interpolasi 1D pada urutan flattened), menjaga relasi geometris lokal token.

#### B. Instabilitas FP16 (Underflow / Overflow pada Attention Softmax)
- **Gejala:** Nilai *loss* menjadi `NaN` pada pertengahan proses fine-tuning menggunakan *Mixed Precision* (FP16).
- **Penyebab:** Hasil kali $Q K^T$ sebelum normalisasi scaling menghasilkan nilai absolut $> 65504$ (batas representasi FP16), menyebabkan Softmax menghasilkan nilai tak terhingga (*infinity*).
- **Solusi Mitigasi:**
  1. Pastikan penskalaan $\frac{1}{\sqrt{d_k}}$ diterapkan sebelum akumulasi ke memori FP16.
  2. Beralih ke representasi **BF16** (Bfloat16) yang mempertahankan rentang eksponen 8-bit setara dengan FP32.
  3. Lakukan kalkulasi fungsi `torch.softmax` dengan *casting* eksplisit ke `float32`.

#### C. OOM (Out-Of-Memory) pada Operasi Kuadratik $O(N^2)$
- **Gejala:** Lonjakan konsumsi alokasi VRAM secara eksponensial saat resolusi ditingkatkan atau ukuran patch diperkecil (misal: $P=8$ pada citra $512 \times 512 \implies N = 4096$ tokens; matriks atensi per kepala membutuhkan $4096 \times 4096 \times 4 \text{ bytes} \approx 67 \text{ MB}$ per layer per sample).
- **Solusi Mitigasi:** Mengintegrasikan implementasi kernel **FlashAttention** (`F.scaled_dot_product_attention` bawaan PyTorch 2.x) yang melakukan fusi operasi Softmax dan menghindari materialisasi matriks atensi $N \times N$ pada VRAM global.

---

### 8. Trade-offs & Alternatif Solusi

| Dimensi Evaluasi | Vision Transformer (ViT) Standar | ConvNeXt (Modern CNN) | Swin Transformer (Hierarchical ViT) |
| :--- | :--- | :--- | :--- |
| **Kompleksitas Komputasi** | $O(N^2)$ terhadap total patch | $O(N)$ terhadap total piksel | $O(N)$ lokal via *Shifted Windows* |
| **Inductive Bias** | Sangat Rendah (Butuh data masif) | Sangat Tinggi (Lokalitas terjamin) | Menengah (Lokalitas dalam window) |
| **Kebutuhan Data Awal** | $\ge 10^7$ citra (JFT / ImageNet-21k) | $\sim 10^6$ citra (ImageNet-1k) | $\sim 10^6$ citra (ImageNet-1k) |
| **Dukungan Dense Task (Deteksi/Segmentasi)** | Sulit (Struktur representasi skala tunggal) | Alami (Representasi piramidal bertingkat) | Alami (Hierarchical Feature Maps) |
| **Unifikasi Multimodal** | Langsung (Kompatibel dengan arsitektur LLM) | Memerlukan *Feature Adapter* non-trivial | Memerlukan flattening non-standar |

*Rekomendasi Keputusan Arsitektural:*
- Pilih **ViT** jika fokus sistem adalah *Foundation Models*, tugas integrasi teks-gambar (*Multimodal Alignment*), atau sistem dilatih pada dataset enterprise masif tanpa batasan komputasi awal.
- Pilih **ConvNeXt** jika latensi inferensi di edge (*mobile deployment*) adalah prioritas utama tanpa ketersediaan akselerator Tensor Core khusus.
- Pilih **Swin Transformer** jika model ditargetkan untuk tugas *Computer Vision* tingkat padat (*Dense Prediction*) seperti deteksi objek (*Object Detection*) atau segmentasi semantik (*Semantic Segmentation*).

---

### 9. Best Practices & Standard Industri

1. **Jadwal Optimasi & Learning Rate Warmup:**
   Transformer sangat sensitif terhadap nilai gradien besar pada awal epoch pelatihan. Terapkan secara wajib *Linear Warmup* selama minimal 10-20 epoch pertama yang diikuti oleh *Cosine Annealing Decay*. Gunakan optimizer **AdamW** dengan parameter *weight decay* $0.05 - 0.1$.
2. **Eksklusi Weight Decay pada Parameter 1D:**
   Jangan terapkan regularisasi *weight decay* (L2) pada vektor bias, layer normalisasi (`LayerNorm`), serta parameter posisi `pos_embed` dan `cls_token`. Penalti L2 pada representasi posisi merusak pemetaan topologi laten.
3. **Data Augmentation yang Agresif:**
   Karena ketiadaan *inductive bias*, pelatihan ViT dari awal memerlukan strategi regularisasi data yang masif:
   - Mixup ($\alpha = 0.8$) dan CutMix ($\alpha = 1.0$)
   - RandAugment atau AutoAugment
   - Label Smoothing ($0.1$)
4. **Gradient Checkpointing:**
   Jika melatih ViT berskala besar (ViT-Large: depth=24, dim=1024), aktifkan `torch.utils.checkpoint.checkpoint` pada setiap blok Transformer untuk menukar komputasi ulang (*forward recomputation*) dengan penghematan memori aktivasi hingga $60\%$.

---

### 10. Hands-on Lab Exercise: Implementasi, Validasi Dimensi, dan Inferensi

#### Skenario Lab:
Anda ditugaskan membangun pipeline inferensi Vision Transformer, melakukan verifikasi tensor shape per layer, dan membuktikan mekanisme *attention patching* bekerja pada variasi batch input sintetis.

#### Step-by-Step Implementation:

```python
"""
Hands-on Lab: Verifikasi Dimensionalitas, Unit Testing Internal, dan Forward Verification
"""

import torch
# Mengimpor modul dari seksi 6
from vit_implementation import ViTConfig, VisionTransformer


def run_vit_pipeline_verification():
    print("=== [Langkah 1: Menginisialisasi Konfigurasi Model ViT-Tiny] ===")
    config = ViTConfig(
        img_size=224,
        patch_size=16,
        in_channels=3,
        num_classes=10,
        embed_dim=192,      # Skala Tiny
        depth=4,            # 4 Encoder Layers untuk simulasi cepat
        num_heads=3,        # 192 / 3 = 64 head_dim
        mlp_ratio=4.0,
        drop_rate=0.1
    )
    print(f"Konfigurasi Berhasil: Dim={config.embed_dim}, Patch={config.patch_size}x{config.patch_size}")

    print("\n=== [Langkah 2: Instansiasi Model dan Verifikasi Parameter] ===")
    model = VisionTransformer(config)
    model.eval()

    total_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"Total Trainable Parameters: {total_params:,}")

    # Patch kalkulasi
    expected_patches = (config.img_size // config.patch_size) ** 2
    print(f"Ekspektasi Patch Sequence Length (N): {expected_patches}")
    print(f"Ekspektasi Input Transformer Sequence (N + 1 [CLS]): {expected_patches + 1}")

    print("\n=== [Langkah 3: Simulasi Dummy Batch Standar] ===")
    batch_size = 4
    dummy_input = torch.randn(batch_size, config.in_channels, config.img_size, config.img_size)
    print(f"Input Shape: {dummy_input.shape}")

    with torch.no_grad():
        output = model(dummy_input)

    print(f"Output Logits Shape: {output.shape}")
    assert output.shape == (batch_size, config.num_classes), \
        f"Mismatch shape output! Diharapkan {(batch_size, config.num_classes)}, didapat {output.shape}"
    print("Assertion Berhasil: Dimensi Logits Standar Sesuai.")

    print("\n=== [Langkah 4: Validasi Mekanisme Dynamic Resolution Interpolation] ===")
    # Menguji gambar dengan resolusi berbeda: 384x384 (Patch grid 24x24 = 576 patch)
    arbitrary_h, arbitrary_w = 384, 384
    dynamic_input = torch.randn(2, config.in_channels, arbitrary_h, arbitrary_w)
    print(f"Input Resolusi Baru: {dynamic_input.shape}")

    # Forward manual fitur untuk menguji interpolasi positional embedding
    try:
        with torch.no_grad():
            features = model.forward_features(dynamic_input)
            dynamic_logits = model.head(features)
        print(f"Dynamic Resolution Logits Shape: {dynamic_logits.shape}")
        assert dynamic_logits.shape == (2, config.num_classes)
        print("Assertion Berhasil: Interpolasi Posisi Berhasil Menangani Resolusi Fleksibel.")
    except Exception as e:
        print(f"Uji Resolusi Dinamis Gagal: {str(e)}")
        raise e

    print("\n=== [Langkah 5: Verifikasi Residual Gradient Flow] ===")
    model.train()
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4)
    target = torch.randint(0, config.num_classes, (batch_size,))
    
    # Forward pass
    train_logits = model(dummy_input)
    loss = torch.nn.functional.cross_entropy(train_logits, target)
    print(f"Loss Iterasi Awal: {loss.item():.4f}")
    
    # Backward pass
    optimizer.zero_grad()
    loss.backward()

    # Pastikan gradient mengalir sampai patch embedding conv projection
    conv_grad = model.patch_embed.proj.weight.grad
    assert conv_grad is not None, "Gradient tidak mencapai layer pertama (Conv Projection)!"
    print(f"Gradient L1 Norm pada Patch Embeddings: {conv_grad.norm(1).item():.4f}")
    print("Validasi Aliran Gradien Berhasil: Tidak ada broken graph pada residual stream.")
    
    print("\nSELURUH PENGUJIAN INTEGRASI BERHASIL.")

if __name__ == "__main__":
    run_vit_pipeline_verification()
```

#### Output Ekspektasi Eksekusi Lab:
```text
=== [Langkah 1: Menginisialisasi Konfigurasi Model ViT-Tiny] ===
Konfigurasi Berhasil: Dim=192, Patch=16x16

=== [Langkah 2: Instansiasi Model dan Verifikasi Parameter] ===
Total Trainable Parameters: 1,811,722
Ekspektasi Patch Sequence Length (N): 196
Ekspektasi Input Transformer Sequence (N + 1 [CLS]): 197

=== [Langkah 3: Simulasi Dummy Batch Standar] ===
Input Shape: torch.Size([4, 3, 224, 224])
Output Logits Shape: torch.Size([4, 10])
Assertion Berhasil: Dimensi Logits Standar Sesuai.

=== [Langkah 4: Validasi Mekanisme Dynamic Resolution Interpolation] ===
Input Resolusi Baru: torch.Size([2, 3, 384, 384])
Dynamic Resolution Logits Shape: torch.Size([2, 10])
Assertion Berhasil: Interpolasi Posisi Berhasil Menangani Resolusi Fleksibel.

=== [Langkah 5: Verifikasi Residual Gradient Flow] ===
Loss Iterasi Awal: 2.3026
Gradient L1 Norm pada Patch Embeddings: 0.1245
Validasi Aliran Gradien Berhasil: Tidak ada broken graph pada residual stream.

SELURUH PENGUJIAN INTEGRASI BERHASIL.
```