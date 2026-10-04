# Bab 07: Computer Vision & Multimodal Intelligence

## Modul 01: Vision Transformers (ViT) & Contrastive Vision-Language Pre-training (CLIP) Architecture

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

- **Merumuskan Fondasi Matematika Vision Transformer (ViT):** Mengonstruksi transformasi spasial citra 2D menjadi representasi sekuensial 1D menggunakan patch projection, integrasi class token ($[CLS]$), dan formulasi positional embeddings berbasis interpolasi bikubik.
- **Mengimplementasikan Dual-Encoder Multimodal (CLIP):** Membangun arsitektur vision-language dual-encoder dari dasar (*from scratch*) menggunakan PyTorch dengan normalisasi L2 dan proyeksi linier ke *shared latent space*.
- **Menganalisis Dinamika InfoNCE Loss:** Menurunkan dan mengimplementasikan Symmetric Cross-Entropy Loss berbasis InfoNCE dengan parameter learnable temperature scale ($\tau$), serta mitigasi destabilisasi numerik.
- **Mengelola Skalabilitas Komputasi & Isu Modality Gap:** Menghitung trade-off kompleksitas kuadratik $\mathcal{O}(N^2)$ pada visual attention dan menerapkan teknik reduksi geometrically induced modality gap pada ruang representasi hipersferis.
- **Mengembangkan Zero-Shot Visual Inference Pipeline:** Membangun pipeline inferensi *zero-shot classification* dan *cross-modal retrieval* yang teroptimasi untuk lingkungan produksi dengan latensi rendah.

---

### 2. Concept Overview

Secara historis, visi komputer didominasi oleh *Convolutional Neural Networks* (CNN) yang mengandalkan dua *inductive biases* fundamental: **locality** (piksel yang berdekatan memiliki korelasi informasi lebih tinggi) dan **translation equivariance** ($f(g(x)) = g(f(x))$, fitur visual yang sama dapat dideteksi terlepas dari pergeseran spasial).

Vision Transformer (ViT) merevolusi paradigma ini dengan menghapus *inductive bias* spasial konvolusional secara eksplisit. ViT memperlakukan citra digital sebagai sekuens token diskret layaknya pemrosesan bahasa alami (NLP). Citra $x \in \mathbb{R}^{H \times W \times C}$ dipartisi menjadi $N$ non-overlapping patches dengan ukuran $P \times P$:

$$N = \frac{H \cdot W}{P^2}$$

Setiap patch diratakan (*flattened*) menjadi vektor $x_p^i \in \mathbb{R}^{P^2 \cdot C}$ dan diproyeksikan secara linier ke dimensi laten $D$ menggunakan matriks terpelajari $E \in \mathbb{R}^{(P^2 \cdot C) \times D}$. Tanpa bias konvolusional, ViT membutuhkan kapasitas data yang masif untuk mempelajari relasi spasial secara murni melalui mekanisme *Standard Multi-Head Self-Attention* (MHSA):

$$\text{Attention}(Q, K, V) = \text{Softmax}\left(\frac{QK^T}{\sqrt{d_k}}\right)V$$

```
   CNN PARADIGM                             ViT PARADIGM
+-----------------------+               +-----------------------+
| Local Receptive Field |               | Global Self-Attention |
| [x] [x] . . . . . . . |               | [T1] <---> [T2] <---> |
| [x] [x] . . . . . . . |               |   ^          ^        |
| Inductive Bias Tinggi |               |   |          |        |
| Data Efficiency Kuat  |               |  [T3] <---> [T4]      |
+-----------------------+               | Bebas Inductive Bias  |
                                        | Skala Data Masif      |
                                        +-----------------------+
```

Konvergensi multimodal terjadi ketika representasi visual ViT dipasangkan dengan representasi tekstual Transformer melalui formulasi **Contrastive Language-Image Pre-training (CLIP)**. 

Alih-alih memprediksi label kelas diskret (*closed-set classification*), CLIP memetakan citra dan teks bebas (*open-vocabulary*) ke dalam sebuah ruang metrik bersama (*shared embedding space*) $\mathbb{R}^d$. 

Model dioptimalkan agar vektor representasi citra $I_i$ dan teks pasangannya $T_i$ memiliki *cosine similarity* maksimum, sembari meminimalkan kesamaan terhadap pasangan negatif $T_j$ ($j \neq i$) dalam sebuah batch:

$$\mathcal{L}_{\text{InfoNCE}} = -\frac{1}{2B} \sum_{i=1}^B \left( \log \frac{\exp(\langle I_i, T_i \rangle / \tau)}{\sum_{j=1}^B \exp(\langle I_i, T_j \rangle / \tau)} + \log \frac{\exp(\langle T_i, I_i \rangle / \tau)}{\sum_{j=1}^B \exp(\langle T_j, I_i \rangle / \tau)} \right)$$

Di mana:
- $B$ adalah *batch size*.
- $\langle \cdot, \cdot \rangle$ merepresentasikan dot product dari vektor yang telah di-normalisasi $L_2$.
- $\tau = \exp(t)$ adalah learnable temperature scaling parameter untuk mengontrol kelembutan distribusi probabilitas.

---

### 3. Why It Matters

Sistem visi komputer konvensional yang dilatih pada dataset tertutup seperti ImageNet ($1.000$ kelas) memiliki kelemahan struktural mendasar: **Distribution Shift Failure** dan **Fixed Label Space**. 

1. **Closed-Set to Open-Vocabulary:** Industri e-commerce, sistem pengawasan (*surveillance*), dan analisis citra medis tidak dapat membatasi domain visual ke sekumpulan kelas statis. CLIP memungkinkan pencarian produk katalog instan berbasis teks bebas (*ad-hoc querying*) tanpa *retraining* atau *fine-tuning* model klasifikasi hulu.
2. **Robustness to Natural Distribution Shifts:** Model yang dilatih dengan contrastive multimodal learning menunjukkan ketahanan superior terhadap perturbasi visual (seperti sketsa, cuaca buruk, atau gaya artistik berbeda) dibanding model yang dilatih berbasis *supervised cross-entropy*.
3. **Foundation for Multimodal Agents & Generative AI:** Arsitektur dual-encoder dan cross-attention berbasis ViT merupakan fondasi dasar sistem Large Multimodal Models (LMM) modern seperti LLaVA, GPT-4V, serta model Text-to-Image berbasis difusi (Stable Diffusion) yang membutuhkan *text-conditioned visual guidance*.

---

### 4. Arsitektur & Diagram Komponen

Diagram alur komputasi di bawah menggambarkan aliran data end-to-end dari representasi raw image dan raw text hingga kalkulasi matriks afinitas multimodal dan InfoNCE Loss:

```
[ Input Image: (B, C, H, W) ]           [ Input Text: (B, L) ]
             |                                     |
    Patch Extraction                      Text Tokenizer (BPE)
  (B, N, P^2 * C)                                  |
             |                            Token Embedding Layer
  Linear Patch Projection                          |
      (B, N, D_img)                       + Positional Embedding
             |                                     |
   + Prepend [CLS] Token                  Transformer Text Blocks
   + Positional Embedding                          |
             |                             Extract EOS Token
  Transformer Vision Blocks                        |
             |                            Linear Text Projection
  Extract [CLS] Projection                         |
             |                            (B, Shared_Dim)
      (B, Shared_Dim)                              |
             |                                     |
      L2 Normalization                      L2 Normalization
     v_img: (B, d)                         v_txt: (B, d)
             \                                     /
              \                                   /
               \                                 /
                +-------------------------------+
                | Compute Cosine Similarity     |
                | Logits = (v_img @ v_txt.T)    |
                | Scale = Logits * exp(tau)     |
                | Matrix Shape: (B, B)          |
                +-------------------------------+
                                |
                +-------------------------------+
                | Symmetric InfoNCE Loss Calc   |
                | - Image-to-Text Cross-Entropy |
                | - Text-to-Image Cross-Entropy |
                | Total Loss = (L_img + L_txt)/2|
                +-------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. ViT Patch Linearization & Mathematical Formulation

Diberikan citra $x \in \mathbb{R}^{H \times W \times C}$. Patch extraction membagi citra menjadi $N$ blok berukuran $P \times P$:

$$N = \frac{H \cdot W}{P^2}$$

Setiap patch diratakan menjadi vektor dimensi spasial $x_p \in \mathbb{R}^{N \times (P^2 \cdot C)}$. Proyeksi dilakukan dengan operasi linear embedding:

$$z_0 = \left[ x_{\text{class}}; \, x_p^1 E; \, x_p^2 E; \, \dots; \, x_p^N E \right] + E_{\text{pos}}$$

Di mana:
- $E \in \mathbb{R}^{(P^2 \cdot C) \times D}$ adalah learnable linear projection matrix.
- $x_{\text{class}} \in \mathbb{R}^{1 \times D}$ adalah learnable token yang berfungsi mengagregasi representasi global citra.
- $E_{\text{pos}} \in \mathbb{R}^{(N + 1) \times D}$ adalah 1D learnable spatial positional embedding.

Blok Transformer terdiri dari *Alternating Multi-Head Self-Attention* (MSA) dan *Multi-Layer Perceptron* (MLP) dengan *Pre-Layer Normalization* (Pre-LN):

$$z_\ell' = \text{MSA}(\text{LN}(z_{\ell-1})) + z_{\ell-1}, \quad \ell = 1 \dots L$$

$$z_\ell = \text{MLP}(\text{LN}(z_\ell')) + z_\ell', \quad \ell = 1 \dots L$$

$$y = \text{LN}(z_L^0)$$

#### B. The InfoNCE Objective and Logit Scale Dynamics

Dalam ruang bersama berdimensi $d$, representasi citra terproyeksi dinotasikan dengan $u_i \in \mathbb{R}^d$ dan teks dengan $v_j \in \mathbb{R}^d$. Kedua vektor dinormalisasi secara ketat ke hipersfer satuan melalui normalisasi $L_2$:

$$\hat{u}_i = \frac{u_i}{\|u_i\|_2}, \quad \hat{v}_j = \frac{v_j}{\|v_j\|_2}$$

Matriks kesamaan kosinus terukur dihitung sebagai:

$$S_{i,j} = \hat{u}_i^T \hat{v}_j$$

Matriks skalar $S \in \mathbb{R}^{B \times B}$ kemudian diskalakan oleh parameter temperatur $\tau$:

$$\mathcal{A}_{i,j} = \frac{S_{i,j}}{\tau} = S_{i,j} \cdot \exp(t)$$

Parameter $t = \log(1/\tau)$ dioptimasi selama proses pelatihan. Nilai $\tau$ bertindak sebagai parameter pengatur entropi dari distribusi softmax:
- Ketika $\tau \to 0$, distribusi probabilitas mendekati *Dirac delta*, menghasilkan gradien yang sangat tajam dan rentan terhadap divergensi numerik (*exploding gradients*).
- Ketika $\tau \to \infty$, distribusi menjadi seragam (*uniform*), melenyapkan sinyal diskriminatif (*gradient vanishing*).
- Dalam implementasi produksi, nilai $t$ dibatasi (*clamped*) ke batas atas (misal $\ln(100) \approx 4.6052$) untuk mencegah instabilitas numerik FP16/BF16.

#### C. The Modality Gap Phenomenon

Penelitian empiris (seperti Liang et al., 2022) menemukan bahwa representasi visual dan tekstual pada model CLIP tidak sepenuhnya bersilangan secara acak di seluruh hipersfer. Sebaliknya, mereka terisolasi ke dalam dua *cone* (kerucut) terpisah yang saling berhadapan di ruang laten. Modality gap ini disebabkan oleh:

1. Perbedaan bias induktif pada inisialisasi jaringan arsitektur visual vs tekstual.
2. Tingkat kerapatan distribusi sampling pasangan multimodal (*contrastive optimization dynamics*).

Mengurangi *modality gap* yang berlebihan penting saat melakukan transfer downstream zero-shot agar jarak metrik antar-modal tidak terdistorsi secara konstan.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi clean-architecture, type-hinted, dan modular dari Vision Transformer (ViT), Text Transformer, dan CLIP Dual-Encoder menggunakan PyTorch murni.

```python
"""
CLIP Architecture Implementation from First Principles.
Designed for distributed production pre-training and zero-shot inference.
"""

from typing import Tuple, Optional
import math
import torch
import torch.nn as nn
import torch.nn.functional as F


class PatchEmbedding(nn.Module):
    """
    Memecah citra 2D menjadi 1D flattened patch sequence dan memproyeksikannya
    ke embedding space menggunakan 2D Convolution layer yang ekuivalen.
    """
    def __init__(
        self,
        img_size: int = 224,
        patch_size: int = 16,
        in_channels: int = 3,
        embed_dim: int = 768
    ) -> None:
        super().__init__()
        if img_size % patch_size != 0:
            raise ValueError(f"Ukuran citra ({img_size}) harus habis dibagi patch size ({patch_size}).")
        
        self.img_size = img_size
        self.patch_size = patch_size
        self.num_patches = (img_size // patch_size) ** 2
        
        # Ekstraksi patch efisien via konvolusi: kernel_size = stride = patch_size
        self.proj = nn.Conv2d(
            in_channels=in_channels,
            out_channels=embed_dim,
            kernel_size=patch_size,
            stride=patch_size
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Input: (B, C, H, W)
        B, C, H, W = x.shape
        if H != self.img_size or W != self.img_size:
            raise ValueError(f"Resolusi citra input ({H}x{W}) tidak cocok dengan konfigurasi ({self.img_size}x{self.img_size}).")
        
        # (B, C, H, W) -> (B, embed_dim, H/P, W/P) -> (B, embed_dim, num_patches)
        x = self.proj(x).flatten(2)
        # Transpose ke bentuk sekuens: (B, num_patches, embed_dim)
        x = x.transpose(1, 2)
        return x


class MultiHeadSelfAttention(nn.Module):
    """
    Standard Scaled Dot-Product Multi-Head Self-Attention.
    """
    def __init__(self, embed_dim: int, num_heads: int, dropout: float = 0.0) -> None:
        super().__init__()
        if embed_dim % num_heads != 0:
            raise ValueError(f"embed_dim ({embed_dim}) harus habis dibagi num_heads ({num_heads}).")
            
        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads
        self.scale = 1.0 / math.sqrt(self.head_dim)

        self.qkv = nn.Linear(embed_dim, embed_dim * 3, bias=True)
        self.attn_drop = nn.Dropout(dropout)
        self.proj = nn.Linear(embed_dim, embed_dim)
        self.proj_drop = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor, mask: Optional[torch.Tensor] = None) -> torch.Tensor:
        B, N, C = x.shape
        # (B, N, 3 * C) -> (B, N, 3, num_heads, head_dim) -> (3, B, num_heads, N, head_dim)
        qkv = self.qkv(x).reshape(B, N, 3, self.num_heads, self.head_dim).permute(2, 0, 3, 1, 4)
        q, k, v = qkv[0], qkv[1], qkv[2]

        # Scaled Dot-Product Attention: (B, num_heads, N, head_dim) @ (B, num_heads, head_dim, N) -> (B, num_heads, N, N)
        attn = (q @ k.transpose(-2, -1)) * self.scale
        
        if mask is not None:
            # Masking untuk causal language model jika diperlukan: mask bernilai True dialihkan ke -inf
            attn = attn.masked_fill(mask == 0, float('-inf'))
            
        attn = F.softmax(attn, dim=-1)
        attn = self.attn_drop(attn)

        # (B, num_heads, N, N) @ (B, num_heads, N, head_dim) -> (B, num_heads, N, head_dim)
        out = (attn @ v).transpose(1, 2).reshape(B, N, C)
        out = self.proj(out)
        out = self.proj_drop(out)
        return out


class TransformerBlock(nn.Module):
    """
    Standard Transformer Encoder Block dengan Pre-Layer Normalization.
    """
    def __init__(self, embed_dim: int, num_heads: int, mlp_ratio: float = 4.0, dropout: float = 0.0) -> None:
        super().__init__()
        self.norm1 = nn.LayerNorm(embed_dim, eps=1e-6)
        self.attn = MultiHeadSelfAttention(embed_dim, num_heads, dropout=dropout)
        self.norm2 = nn.LayerNorm(embed_dim, eps=1e-6)
        
        mlp_hidden_dim = int(embed_dim * mlp_ratio)
        self.mlp = nn.Sequential(
            nn.Linear(embed_dim, mlp_hidden_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(mlp_hidden_dim, embed_dim),
            nn.Dropout(dropout)
        )

    def forward(self, x: torch.Tensor, mask: Optional[torch.Tensor] = None) -> torch.Tensor:
        x = x + self.attn(self.norm1(x), mask=mask)
        x = x + self.mlp(self.norm2(x))
        return x


class VisionTransformer(nn.Module):
    """
    ViT Backbone untuk CLIP Visual Encoder.
    """
    def __init__(
        self,
        img_size: int = 224,
        patch_size: int = 16,
        in_channels: int = 3,
        embed_dim: int = 768,
        depth: int = 12,
        num_heads: int = 12,
        mlp_ratio: float = 4.0,
        projection_dim: int = 512,
        dropout: float = 0.0
    ) -> None:
        super().__init__()
        self.patch_embed = PatchEmbedding(img_size, patch_size, in_channels, embed_dim)
        num_patches = self.patch_embed.num_patches

        self.cls_token = nn.Parameter(torch.zeros(1, 1, embed_dim))
        self.pos_embed = nn.Parameter(torch.zeros(1, num_patches + 1, embed_dim))
        self.pos_drop = nn.Dropout(p=dropout)

        self.blocks = nn.ModuleList([
            TransformerBlock(embed_dim, num_heads, mlp_ratio, dropout)
            for _ in range(depth)
        ])
        self.norm = nn.LayerNorm(embed_dim, eps=1e-6)
        self.projection = nn.Linear(embed_dim, projection_dim, bias=False)

        self._initialize_weights()

    def _initialize_weights(self) -> None:
        nn.init.trunc_normal_(self.pos_embed, std=0.02)
        nn.init.trunc_normal_(self.cls_token, std=0.02)
        self.apply(self._init_transformer_weights)

    def _init_transformer_weights(self, m: nn.Module) -> None:
        if isinstance(m, nn.Linear):
            nn.init.trunc_normal_(m.weight, std=0.02)
            if m.bias is not None:
                nn.init.constant_(m.bias, 0)
        elif isinstance(m, nn.LayerNorm):
            nn.init.constant_(m.bias, 0)
            nn.init.constant_(m.weight, 1.0)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        B = x.shape[0]
        x = self.patch_embed(x)  # (B, N, D)

        cls_tokens = self.cls_token.expand(B, -1, -1)  # (B, 1, D)
        x = torch.cat((cls_tokens, x), dim=1)  # (B, N+1, D)
        x = self.pos_drop(x + self.pos_embed)

        for block in self.blocks:
            x = block(x)

        x = self.norm(x)
        # Ekstrak representasi embedding dari token [CLS]
        cls_out = x[:, 0]
        out = self.projection(cls_out)
        return out


class TextTransformer(nn.Module):
    """
    Standard Transformer Encoder untuk Text Representation.
    """
    def __init__(
        self,
        vocab_size: int = 49408,
        context_length: int = 77,
        embed_dim: int = 512,
        depth: int = 12,
        num_heads: int = 8,
        mlp_ratio: float = 4.0,
        projection_dim: int = 512,
        dropout: float = 0.0
    ) -> None:
        super().__init__()
        self.context_length = context_length
        self.token_embedding = nn.Embedding(vocab_size, embed_dim)
        self.pos_embed = nn.Parameter(torch.zeros(1, context_length, embed_dim))
        
        self.blocks = nn.ModuleList([
            TransformerBlock(embed_dim, num_heads, mlp_ratio, dropout)
            for _ in range(depth)
        ])
        self.norm = nn.LayerNorm(embed_dim, eps=1e-6)
        self.projection = nn.Linear(embed_dim, projection_dim, bias=False)

        nn.init.trunc_normal_(self.pos_embed, std=0.02)
        nn.init.normal_(self.token_embedding.weight, std=0.02)

    def forward(self, text: torch.Tensor) -> torch.Tensor:
        # text shape: (B, L)
        B, L = text.shape
        if L > self.context_length:
            raise ValueError(f"Panjang token ({L}) melebihi context length maksimal ({self.context_length}).")

        x = self.token_embedding(text) + self.pos_embed[:, :L, :]

        # Generasikan causal mask untuk model autoregresif / standard CLIP masking
        mask = torch.tril(torch.ones(L, L, device=text.device)).unsqueeze(0).unsqueeze(0)

        for block in self.blocks:
            x = block(x, mask=mask)

        x = self.norm(x)
        
        # Ambil representasi dari token argmax (EOS token index dalam representasi CLIP)
        eos_indices = text.argmax(dim=-1)
        pooled = x[torch.arange(B, device=text.device), eos_indices]
        
        out = self.projection(pooled)
        return out


class CLIP(nn.Module):
    """
    Contrastive Language-Image Pre-training (CLIP) Model.
    """
    def __init__(
        self,
        vision_encoder: VisionTransformer,
        text_encoder: TextTransformer,
        init_temperature: float = 0.07,
        max_temperature: float = 100.0
    ) -> None:
        super().__init__()
        self.visual = vision_encoder
        self.textual = text_encoder
        
        # logit_scale dioptimasi dalam log-space (t = log(1/tau))
        self.logit_scale = nn.Parameter(torch.ones([]) * math.log(1.0 / init_temperature))
        self.max_logit_scale = math.log(max_temperature)

    def encode_image(self, image: torch.Tensor) -> torch.Tensor:
        x = self.visual(image)
        # Normalisasi L2 ke hipersfer
        return F.normalize(x, p=2, dim=-1)

    def encode_text(self, text: torch.Tensor) -> torch.Tensor:
        x = self.textual(text)
        # Normalisasi L2 ke hipersfer
        return F.normalize(x, p=2, dim=-1)

    def forward(self, image: torch.Tensor, text: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        image_features = self.encode_image(image)
        text_features = self.encode_text(text)

        # Stabilisasi numerik logit_scale parameter via clamping
        with torch.no_grad():
            self.logit_scale.clamp_(0, self.max_logit_scale)

        logit_scale = self.logit_scale.exp()

        # Cosine similarity matrix: (B, d) @ (d, B) -> (B, B)
        logits_per_image = logit_scale * (image_features @ text_features.t())
        logits_per_text = logits_per_image.t()

        return logits_per_image, logits_per_text


class ContrastiveLoss(nn.Module):
    """
    Symmetric InfoNCE Loss.
    """
    def __init__(self) -> None:
        super().__init__()
        self.loss_fn = nn.CrossEntropyLoss()

    def forward(self, logits_per_image: torch.Tensor, logits_per_text: torch.Tensor) -> torch.Tensor:
        batch_size = logits_per_image.size(0)
        labels = torch.arange(batch_size, device=logits_per_image.device, dtype=torch.long)
        
        loss_i2t = self.loss_fn(logits_per_image, labels)
        loss_t2i = self.loss_fn(logits_per_text, labels)
        
        return (loss_i2t + loss_t2i) / 2.0
```

---

### 7. Edge Cases & Failure Modes

#### 1. Batch Size Collapse pada Kontrastif
- **Mekanisme Kegagalan:** Kualitas InfoNCE berbanding lurus dengan jumlah *negative samples* ($B-1$). Pelatihan dengan ukuran batch kecil ($B < 128$) menyebabkan gradien memiliki variansi sangat tinggi, memicu *representation collapse* di mana semua representasi mengarah ke satu titik pada hipersfer.
- **Deteksi & Mitigasi:** Gunakan teknik *Memory Bank* atau antrean dinamis (seperti arsitektur MoCo), atau *Gradient Cache* / distributed `all_gather` cross-GPU tanpa menyimpan aktivasi penuh ke memori GPU worker.

#### 2. Logit Scale (Temperature) Exploding & Precision Underflow
- **Mekanisme Kegagalan:** Pada mixed-precision training (FP16), jika $t = \log(1/\tau)$ bertumbuh melampaui $\approx 4.6052$ ($\tau \approx 0.01$), nilai logits melebihi kapasitas representasi maksimum FP16 ($65504$), memicu overflow menjadi `NaN` atau `Inf` pada operasi eksponensial matriks softmax.
- **Deteksi & Mitigasi:** Pasang `clamp_(max=np.log(100))` eksplisit pada parameter `logit_scale` segera setelah optimasi gradien, dan gunakan tipe data **BF16 (Bfloat16)** yang memiliki rentang dinamis eksponen setara dengan FP32.

#### 3. Positional Embedding Resolution Incompatibility
- **Mekanisme Kegagalan:** Model ViT yang dilatih pada citra $224 \times 224$ (menghasilkan $14 \times 14 = 196$ patch) mengalami *runtime dimension mismatch exception* jika disuplai citra inferensi berukuran $384 \times 384$ ($24 \times 24 = 576$ patch).
- **Deteksi & Mitigasi:** Lakukan 2D Bicubic Interpolation dinamis pada matriks positional embedding saat dimensi input spasial berubah:

```python
def interpolate_pos_encoding(pos_embed: torch.Tensor, new_h: int, new_w: int, patch_size: int = 16) -> torch.Tensor:
    """
    Menginterpolasi matriks bobot pos_embed ViT secara bikubik ke ukuran spasial baru.
    """
    cls_pos = pos_embed[:, :1, :]
    patch_pos = pos_embed[:, 1:, :]
    
    num_patches = patch_pos.shape[1]
    dim = patch_pos.shape[-1]
    old_grid_size = int(math.sqrt(num_patches))
    
    new_grid_h = new_h // patch_size
    new_grid_w = new_w // patch_size
    
    if old_grid_size == new_grid_h and old_grid_size == new_grid_w:
        return pos_embed

    patch_pos = patch_pos.reshape(1, old_grid_size, old_grid_size, dim).permute(0, 3, 1, 2)
    patch_pos = F.interpolate(
        patch_pos,
        size=(new_grid_h, new_grid_w),
        mode='bicubic',
        align_corners=False
    )
    patch_pos = patch_pos.permute(0, 2, 3, 1).flatten(1, 2)
    return torch.cat((cls_pos, patch_pos), dim=1)
```

---

### 8. Trade-offs & Alternatif Solusi

| Dimensi Arsitektur | ViT (Vision Transformer) | Swin Transformer | ConvNeXt |
| :--- | :--- | :--- | :--- |
| **Attention Mechanism** | Full Global Attention | Shifted Window Local Attention | Depthwise Separable Conv (Non-attention) |
| **Computational Complexity**| $\mathcal{O}(N^2)$ (Kuadratik terhadap piksel) | $\mathcal{O}(N)$ (Linear) | $\mathcal{O}(N)$ (Linear) |
| **Inductive Bias** | Minimal (Membutuhkan Pretraining Besar) | Menengah (Hierarchical multiscale) | Kuat (Spasial lokal & translasi) |
| **Throughput Inferensi (FPS)**| Sedang - Rendah pada resolusi tinggi | Menengah | Tinggi (Sangat optimal di engine TensorRT) |
| **Kesesuaian Multimodal**| *De facto standard* untuk text-alignment | Sangat baik untuk Object Detection | Baik untuk unimodal, tertinggal di LMM |

#### Dual-Encoder vs Cross-Encoder Multimodal

- **Dual-Encoder (CLIP-Style):** Citra dan teks diproses terpisah hingga proyeksi akhir. Kesamaan dihitung hanya via *vector dot product*.
  - *Kelebihan:* Ekstrem efisien. Representasi visual/tekstual dapat di-precompute dan disimpan ke dalam Vector Database (Milvus, Qdrant) untuk pencarian berskala miliaran dokumen dalam orde milidetik.
  - *Kekurangan:* Tidak mampu menangkap relasi tingkat tinggi yang sangat granular (*fine-grained reasoning*) antara objek visual dan frasa preposisi yang rumit.
- **Cross-Encoder / Early Fusion (Flamingo, BLIP-2 Q-Former):** Menggunakan layer Cross-Attention di mana visual tokens berinteraksi langsung dengan textual tokens di tiap layer.
  - *Kelebihan:* Akurasi reasoning superior.
  - *Kekurangan:* Skalabilitas inferensi rendah; inferensi memerlukan komputasi forward-pass penuh secara simultan untuk setiap pasang query-kandidat.

---

### 9. Best Practices & Standard Industri

1. **Distributed Contrastive All-Gather Tanpa Backprop Bottleneck:**
   Saat menjalankan Distributed Data Parallel (DDP) di multi-node cluster, pengumpulan representasi tensor (`all_gather`) dari seluruh GPU untuk memperbesar batch size InfoNCE wajib ditulis dengan mengisolasi gradien GPU lokal guna menghindari *memory thrashing*:

```python
class GatherLayer(torch.autograd.Function):
    """
    Gathers tensors from all processes, supporting backward propagation.
    """
    @staticmethod
    def forward(ctx, input_tensor: torch.Tensor) -> torch.Tensor:
        ctx.save_for_backward(input_tensor)
        output = [torch.zeros_like(input_tensor) for _ in range(torch.distributed.get_world_size())]
        torch.distributed.all_gather(output, input_tensor)
        return torch.cat(output, dim=0)

    @staticmethod
    def backward(ctx, grad_output: torch.Tensor) -> torch.Tensor:
        input_tensor, = ctx.saved_tensors
        grad_input = grad_output.clone()
        torch.distributed.all_reduce(grad_input, op=torch.distributed.ReduceOp.SUM)
        idx_from = torch.distributed.get_rank() * input_tensor.size(0)
        idx_to = idx_from + input_tensor.size(0)
        return grad_input[idx_from:idx_to]
```

2. **Mixed-Precision Stability:**
   Gunakan `torch.cuda.amp.autocast(dtype=torch.bfloat16)`. BF16 memiliki rentang dinamis yang sama dengan FP32 sehingga mencegah divergensi numerik saat menghitung matriks eksponensial pada InfoNCE Loss tanpa memerlukan modifikasi dinamis skalar loss (*loss scaling* yang kompleks).
3. **Weight Decoupling pada Proyeksi Multimodal:**
   Jangan terapkan *weight decay* (L2 Regularization) pada parameter bias, LayerNorm affine transforms, dan `logit_scale`. Terapkan weight decay (misal: $0.2$) hanya pada matriks bobot proyeksi 2D (`Linear`, `Conv2d`).

---

### 10. Hands-on Lab Exercise

Tujuan: Membangun pipeline inferensi end-to-end zero-shot visual classification menggunakan implementasi model CLIP yang telah dibangun di atas.

#### Step 1: Inisialisasi Model & Dummy Tokenizer Environment

```python
import torch
import torch.nn.functional as F

# Konfigurasi Hardware
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Instansiasi Arsitektur Model ViT-B/16 & Text Transformer Ringan
vision_backbone = VisionTransformer(
    img_size=224,
    patch_size=16,
    in_channels=3,
    embed_dim=256,
    depth=6,
    num_heads=8,
    projection_dim=128
)

text_backbone = TextTransformer(
    vocab_size=1000,
    context_length=16,
    embed_dim=256,
    depth=6,
    num_heads=8,
    projection_dim=128
)

model = CLIP(
    vision_encoder=vision_backbone,
    text_encoder=text_backbone,
    init_temperature=0.07
).to(device)

model.eval()
print("Model arsitektur CLIP berhasil diinstansiasi pada device:", device)
```

#### Step 2: Implementasi Zero-Shot Text Prompt Engine & Forward Inference

```python
def mock_bpe_tokenizer(texts: list[str], max_length: int = 16) -> torch.Tensor:
    """
    Mock deterministic tokenizer untuk keperluan stand-alone executable testing.
    Menghasilkan token terstruktur: [BOS] + [Tokens] + [EOS] + [PAD...]
    """
    batch_tokens = []
    for text in texts:
        # Konversi karakter deterministik sederhana ke token index
        tokens = [1] + [(ord(c) % 900) + 10 for c in text.lower().split()][:max_length - 2] + [2]
        padding = [0] * (max_length - len(tokens))
        batch_tokens.append(tokens + padding)
    return torch.tensor(batch_tokens, dtype=torch.long)

# 1. Definisikan Kelas Target Visual
classes = ["industrial robotic arm", "semiconductor wafer", "autonomous delivery drone"]

# 2. Konstruksi Prompt Engineering (Prompt Template)
prompts = [f"a high-resolution photo of a {c}" for c in classes]
text_tokens = mock_bpe_tokenizer(prompts, max_length=16).to(device)

# 3. Buat Mock Citra Masukan (Representasi batch dari 3 citra industri sintetis)
# Shape: (Batch_Size=3, Channels=3, Height=224, Width=224)
dummy_images = torch.randn(3, 3, 224, 224, device=device)

# 4. Zero-Shot Inference Pass
with torch.no_grad():
    # Ekstraksi dan L2-Normalize visual features
    image_features = model.encode_image(dummy_images)
    # Ekstraksi dan L2-Normalize text features
    text_features = model.encode_text(text_tokens)

    # Validasi norma L2 berada di angka 1.0 (Unit Hypersphere verification)
    assert torch.allclose(torch.norm(image_features, dim=-1), torch.ones(3, device=device), atol=1e-5)
    assert torch.allclose(torch.norm(text_features, dim=-1), torch.ones(3, device=device), atol=1e-5)

    # Hitung kesamaan kosinus antar representasi (B_img, Shared_Dim) @ (Shared_Dim, B_text)
    similarity = (image_features @ text_features.t()) * model.logit_scale.exp()
    
    # Hitung distribusi probabilitas zero-shot via Softmax sepanjang sumbu teks (dim=-1)
    zero_shot_probs = F.softmax(similarity, dim=-1)

# 5. Output Telemetri Hasil
print("\n--- ZERO-SHOT CLASSIFICATION TELEMETRY ---")
for idx in range(dummy_images.shape[0]):
    print(f"\nImage Input #[{idx}]:")
    for cls_idx, cls_name in enumerate(classes):
        prob = zero_shot_probs[idx, cls_idx].item()
        print(f" > Probabilitas Kelas '{cls_name}': {prob * 100:.2f}%")
```

#### Step 3: Verifikasi Konsistensi Gradient Dual-Encoder

```python
# Verifikasi jalur backward propagation end-to-end
model.train()
criterion = ContrastiveLoss()

# Jalankan forward pass training
logits_img, logits_txt = model(dummy_images, text_tokens)
loss = criterion(logits_img, logits_txt)

# Propagasi mundur
loss.backward()

print(f"\n--- LOSS VALIDATION ---")
print(f"Training InfoNCE Loss: {loss.item():.4f}")
print(f"Gradient Check Vision Patch Projection: {model.visual.patch_embed.proj.weight.grad is not None}")
print(f"Gradient Check Text Embedding: {model.textual.token_embedding.weight.grad is not None}")
print(f"Gradient Check Logit Scale Tau: {model.logit_scale.grad is not None}")

# Pastikan gradien tidak None dan bebas NaN/Inf
assert not torch.isnan(model.visual.patch_embed.proj.weight.grad).any(), "NaN terdeteksi pada gradien visual!"
assert not torch.isinf(model.logit_scale.grad).any(), "Inf terdeteksi pada gradien temperatur!"
print("\nSeluruh pengujian arsitektural dan verifikasi gradien berhasil diselesaikan.")
```