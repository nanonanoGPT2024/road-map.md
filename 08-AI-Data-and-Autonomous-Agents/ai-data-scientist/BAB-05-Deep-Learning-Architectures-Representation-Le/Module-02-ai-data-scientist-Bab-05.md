# Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 05: Deep Learning Architectures & Representation Learning**  
**Jalur: AI Data Scientist / AI Engineer (Enterprise Grade)**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan memiliki kompetensi tingkat lanjut untuk:
- **Merancang & Mengimplementasikan Arsitektur Representasi Modern**: Membangun pipeline Self-Supervised Learning (SSL) berbasis Contrastive Learning (SimCLR/MoCo v3) dan Masked Autoencoders (MAE) dari scratch menggunakan PyTorch murni.
- **Menguasai Mekanisme Attention Skala Produksi**: Mengabstraksi dan mengimplementasikan FlashAttention, Multi-Head Latent Attention (MLA), serta Vision Transformers (ViT) dengan positional encoding tingkat lanjut (RoPE 2D).
- **Mengoptimalkan Pipeline Training Skala Enterprise**: Menerapkan Distributed Data Parallel (DDP), Fully Sharded Data Parallel (FSDP), Automatic Mixed Precision (AMP - FP16/BF16), serta aktivasi *activation checkpointing* untuk mengatasi OOM (*Out-Of-Memory*).
- **Mengeksekusi Profiling & Kompilasi Model untuk Inferensi**: Memanfaatkan `torch.compile` (TorchDynamo, AOT Autograd, Inductor), profiling CUDA stream dengan PyTorch Profiler, dan ekspor ke ONNX/TensorRT untuk latensi sub-milidetik.
- **Mendiagnosis Kegagalan Konvergensi**: Mengidentifikasi representational collapse, vanishing/exploding gradients di jaringan dalam, dan numerik instabilitas pada optimasi floating-point rendah.

---

## 2. Prerequisite

Peserta diasumsikan telah menguasai:
- **Fundamental Deep Learning**: Backpropagation, Chain Rule kalkulus tensor, Optimizers (SGD, Adam, AdamW, LAMB), Regularization (Weight Decay, Dropout, Stochastic Depth).
- **Arsitektur Dasar**: Convolutional Neural Networks (ResNet, ConvNeXt), Recurrent Networks (LSTM/GRU), dan Standard Transformer Encoder-Decoder (Vaswani et al.).
- **Perangkat Keras & Framework**:
  - Python 3.10+ & PyTorch 2.x (Internal hooks, `torch.distributed`, C++/CUDA extensions abstraction).
  - Pengetahuan arsitektur GPU: Streaming Multiprocessors (SM), Tensor Cores, HBM vs SRAM (L1/L2 Cache), NVLink vs PCIe bus bandwidth.
  - Aljabar Linier Lanjutan: Singular Value Decomposition (SVD), Proyeksi Non-Linear, Eigendecomposition representasi matriks kovariansi.

---

## 3. Concept & Internal Architecture (Mendalam)

Representation Learning berfokus pada transformasi data mentah berdimensi tinggi $\mathbf{x} \in \mathbb{R}^D$ menjadi vektor fitur padat $\mathbf{z} \in \mathbb{R}^d$ ($d \ll D$) yang mempertahankan topologi semantik tanpa supervisi label manual ($y$).

```
Raw High-Dimensional Space (X)
             │
             ▼
┌──────────────────────────┐
│   Encoder Backbone f(·)  │ ──► ViT / ConvNeXt / Hybrid
└──────────────────────────┘
             │
             ▼ Latent Representation h ∈ R^{d_h}
┌──────────────────────────┐
│  Projector Head g(·)     │ ──► Multi-Layer Perceptron (MLP)
└──────────────────────────┘
             │
             ▼ Embedding Space z ∈ R^{d_z}
┌──────────────────────────┐
│ Objective Function L(z)  │ ──► Contrastive (InfoNCE) / Reconstruction (MSE)
└──────────────────────────┘
```

### 3.1. Contrastive Learning Dynamics & Collapse Modes
Pada Contrastive Representation Learning (seperti SimCLR atau MoCo), kita memetakan dua augmentasi berbeda dari sampel yang sama $\mathbf{x}$, yaitu $\tilde{\mathbf{x}}_i$ dan $\tilde{\mathbf{x}}_j$, menuju ruang latent melalui encoder $f(\cdot)$ dan projection head $g(\cdot)$:

$$\mathbf{z}_i = g(f(\tilde{\mathbf{x}}_i)), \quad \mathbf{z}_j = g(f(\tilde{\mathbf{x}}_j))$$

Fungsi objektif InfoNCE (Information Noise-Contrastive Estimation) diformulasikan sebagai:

$$\mathcal{L}_{i,j} = -\log \frac{\exp(\text{sim}(\mathbf{z}_i, \mathbf{z}_j) / \tau)}{\sum_{k=1}^{2N} \mathbb{I}_{[k \neq i]} \exp(\text{sim}(\mathbf{z}_i, \mathbf{z}_k) / \tau)}$$

Di mana:
- $\text{sim}(\mathbf{u}, \mathbf{v}) = \frac{\mathbf{u}^T \mathbf{v}}{\|\mathbf{u}\|_2 \|\mathbf{v}\|_2}$ adalah cosine similarity.
- $\tau$ adalah parameter temperatur skalar yang mengontrol *hardness penalty* terhadap *negative pairs*.
- Jika $\tau$ terlalu besar, distribusi probabilitas menjadi seragam (*uniform*), gradien kehilangan sensitivitas terhadap sampel negatif terdekat (*hard negatives*).
- Jika $\tau$ terlalu kecil, representasi menjadi tidak stabil dan gradien mengalami vanishing/exploding akibat gradien eksponensial ekstrem.

#### Fenomena Collapse
1. **Complete Collapse**: Seluruh representasi $\mathbf{z}$ terpetakan ke sebuah konstanta vektor tunggal $\mathbf{c}$. Cosine similarity bernilai $1$, gradien menjadi $0$.
2. **Dimensional Collapse**: Representasi $\mathbf{z}$ hanya menempati subruang berdimensi rendah dari $\mathbb{R}^d$. Matriks kovariansi $\mathbf{C} = \frac{1}{N} \mathbf{Z}^T \mathbf{Z}$ memiliki rank yang sangat terdegenerasi (sebagian besar singular value mendekati nol). SimCLR menghindari hal ini melalui *repulsion force* dari penyebut InfoNCE. MoCo menghindarinya menggunakan memory queue dengan momentum encoder:

$$\theta_k \leftarrow m \theta_k + (1-m) \theta_q$$

### 3.2. Vision Transformers (ViT) & Patch Embedding Internals
Berbeda dengan induksi bias translasi invarian dan lokalitas pada CNN, Vision Transformer memperlakukan citra $\mathbf{X} \in \mathbb{R}^{H \times W \times C}$ sebagai sekuens token patch linear:
1. Citra dipotong menjadi $N = \frac{HW}{P^2}$ patch non-overlapping berukuran $P \times P$.
2. Setiap patch diratakan (*flattened*) $\mathbf{x}_p^i \in \mathbb{R}^{P^2 C}$ dan diproyeksikan secara linear melalui matriks $\mathbf{E} \in \mathbb{R}^{(P^2 C) \times D}$:

$$\mathbf{z}_0 = [\mathbf{x}_{\text{class}}; \, \mathbf{x}_p^1\mathbf{E}; \, \mathbf{x}_p^2\mathbf{E}; \dots; \, \mathbf{x}_p^N\mathbf{E}] + \mathbf{E}_{pos}$$

3. **Mekanisme Self-Attention**:
   $$\mathbf{Q} = \mathbf{z}\mathbf{W}_Q, \quad \mathbf{K} = \mathbf{z}\mathbf{W}_K, \quad \mathbf{V} = \mathbf{z}\mathbf{W}_V$$
   $$\text{Attention}(\mathbf{Q}, \mathbf{K}, \mathbf{V}) = \text{Softmax}\left(\frac{\mathbf{Q}\mathbf{K}^T}{\sqrt{d_k}}\right)\mathbf{V}$$

Kompleksitas komputasi standar Self-Attention adalah $\mathcal{O}(N^2 \cdot D)$. Jika resolusi citra meningkat dari $224 \times 224$ ke $1024 \times 1024$ dengan $P=16$, jumlah patch $N$ melonjak dari 196 menjadi 4096, meningkatkan kebutuhan FLOPs dan memori kuadratik sebesar $\approx 436\times$.

### 3.3. FlashAttention Memory Hierarchy Execution Model
FlashAttention merevolusi komputasi attention dengan memanfaatkan karakteristik memori GPU:
- **HBM (High Bandwidth Memory)**: Kapasitas besar (40-80GB), latency tinggi (relatif lambat, ~1.5-3.0 TB/s).
- **SRAM**: Kapasitas sangat kecil (~100-256KB per SM), bandwidth luar biasa (~19 TB/s).

Standar Attention membaca dan menulis intermediate matrix $\mathbf{S} = \mathbf{Q}\mathbf{K}^T \in \mathbb{R}^{N \times N}$ dan $\mathbf{P} = \text{softmax}(\mathbf{S}) \in \mathbb{R}^{N \times N}$ berulang kali ke HBM ($\mathcal{O}(N^2)$ IO complexity). 

FlashAttention mengimplementasikan **Tiling** dan **Online Softmax**:
- Menghitung blok softmax parsial tanpa menyimpan seluruh matriks $\mathbf{S}$ ke HBM.
- Menggunakan teknik recomputation saat backward pass: matriks attention intermediate tidak disimpan di forward pass, melainkan dihitung ulang secara dinamis di SRAM saat backward pass, mengurangi kebutuhan HBM dari $\mathcal{O}(N^2)$ menjadi $\mathcal{O}(N)$.

---

## 4. Why & What

| Dimensi | Supervised Learning Tradisional | Self-Supervised Representation Learning |
| :--- | :--- | :--- |
| **Ketergantungan Label** | Sangat tinggi; performa runtuh saat anotasi langka/noise. | Zero label pada fase pre-training; belajar dari struktur intrinsik data. |
| **Batas Representasi** | Terbias hanya pada domain fitur penentu kelas diskrit. | Menangkap semantik holistik, topologi spasial, dan struktur invarian. |
| **Transferabilitas** | Rentan terhadap *catastrophic forgetting* dan domain shift. | Fitur downstream sangat elastis (deteksi, segmentasi, klasifikasi). |
| **Kebutuhan Komputasi** | Moderat; konvergensi lebih cepat per epoch. | Sangat masif; membutuhkan throughput data besar dan optimasi paralel. |

### Mengapa Masuk ke Arsitektur Produksi Skala Lanjut?
Dalam skala industri, bottleneck deep learning bukan lagi sekadar ketersediaan data, melainkan:
1. **Memory Wall**: Ukuran model dan tensor aktivasi melampaui kapasitas VRAM GPU tunggal.
2. **I/O Starvation**: CPU preprocessing gagal memberi makan data (*starvation*) ke GPU Tensor Cores.
3. **Serving Latency vs Throughput**: Model ViT raksasa tidak dapat disajikan secara real-time pada service SLA < 20ms tanpa teknik kuantisasi dan kompilasi kernel.

---

## 5. How (Workflow Detail)

Arsitektur siklus hidup implementasi representation learning tingkat lanjut diatur dalam pipeline berikut:

```
[Tahap 1: Data Pipeline]
   │ Distributed Storage (S3/Ceph) 
   ▼ WebDataset / FFCV Sharded Pipes (Zero Copy Memory Mapping)
[Tahap 2: Pre-Training SSL]
   │ SimCLR / MAE Backbone Initialization
   │ Distributed Strategy: PyTorch FSDP (ZeRO-3) + Mixed Precision (BF16)
   ▼ Optimizer: AdamW + Cosine Annealing with Warmup + Gradient Clipping
[Tahap 3: Model Alignment & Downstream Adaptation]
   │ Freeze Backbone -> Train Linear Probe OR
   ▼ Parameter-Efficient Fine-Tuning (LoRA / Adapter Injection)
[Tahap 4: Production Optimization & Export]
   │ TorchDynamo Graph Capture -> AOTAutograd -> Inductor Engine
   ▼ Post-Training Quantization (INT8/FP8) via TensorRT
[Tahap 5: High-Concurrency Inference Serving]
   │ Triton Inference Server (Dynamic Batching + Concurrent Model Execution)
   ▼ Prometheus Latency/Throughput Metric Exporter
```

### Algoritma Training Step (FSDP + FlashAttention + AMP)
1. **Data Sharding**: Tiap worker GPU menerima mini-batch independen dari sharded pipeline.
2. **Forward Pass (AMP Context)**:
   - Casting input tensor ke `torch.bfloat16`.
   - ViT Encoder mengeksekusi Tiled Multi-Head Attention via `F.scaled_dot_product_attention`.
   - Menghitung representasi laten dan nilai loss (e.g., InfoNCE).
3. **Backward Pass**:
   - Skalasi gradien (jika FP16) atau komputasi langsung (jika BF16).
   - FSDP melakukan *all-gather* parameter layer per layer, mengeksekusi autograd, lalu mendistribusikan (*reduce-scatter*) gradien ke seluruh rank GPU.
4. **Optimization**:
   - `torch.nn.utils.clip_grad_norm_` diterapkan pada gradien lokal yang sudah ter-shard.
   - Optimizer step mengupdate sharded optimizer states dan weights.

---

## 6. Analogy & Diagram ASCII

### Analogi: Konferensi Ahli Bedah Global (Contrastive & Self-Supervised Learning)
Bayangkan Anda ingin melatih tim asisten bedah tanpa memberi tahu nama penyakit secara eksplisit:
- **Contrastive Learning (SimCLR)**: Anda mengambil satu foto rontgen dada, memberikan dua filter berbeda (rotasi sedikit vs peningkatan kontras). Anda meminta asisten menyimpulkan: *"Dua gambar ini berasal dari pasien yang sama"* (positive pair), sekaligus menunjukkan 1.000 foto rontgen pasien lain dan berkata: *"Semua ini bukan pasien yang sama"* (negative pairs).
- **Masked Autoencoders (MAE)**: Anda mengambil foto anatomi tubuh, menutup 75% bagian gambar dengan kertas hitam pekat, dan memerintahkan asisten merekonstruksi kembali seluruh detail anatomi yang tertutup tersebut. Untuk bisa menggambar bagian yang hilang, asisten terpaksa memahami struktur fisik organ secara holistik.

### Diagram Arsitektur: Vision Transformer Masked Autoencoder (MAE)

```
        Citra Asli (H x W x C)
                 │
      ┌──────────┴──────────┐
      ▼                     ▼
[Patching 16x16]      [Patching 16x16]
      │                     │
[Visual Patches]       [Masking Acak: 75%]
      │                     │
      │              ┌──────┴────────────────┐
      │              │ Visible Patches (25%) │ (75% dibuang total)
      │              └──────┬────────────────┘
      │                     │
      │                     ▼
      │             ┌───────────────┐
      │             │ Heavy ViT     │
      │             │ Encoder       │ (Hanya memproses 25% token)
      │             └───────┬───────┘
      │                     │ Latent Representations
      │                     ▼
      │             [Concatenate Tokens] <── Tambahkan [Mask Tokens] yang dapat dipelajari
      │                     │                ke posisi semula
      │                     ▼
      │             ┌───────────────┐
      │             │ Lightweight   │
      │             │ Decoder       │ (Memproses 100% token)
      │             └───────┬───────┘
      │                     │
      ▼                     ▼
[Ground Truth Pixel] <── [MSE Loss] ──> [Predicted Pixel Reconstruction]
```

---

## 7. Simple Example & Practical Example

### 7.1. Simple Example: Self-Supervised SimCLR Loss Implementation
Snippet berikut mendemonstrasikan implementasi matematika InfoNCE murni secara vektorisasi tanpa loop Python:

```python
import torch
import torch.nn as nn
import torch.nn.functional as F

class InfoNCELoss(nn.Module):
    """
    Normalized Temperature-scaled Cross Entropy Loss (NT-Xent)
    Standard implementation for SimCLR architectures.
    """
    def __init__(self, temperature: float = 0.07):
        super().__init__()
        self.temperature = temperature

    def forward(self, z_i: torch.Tensor, z_j: torch.Tensor) -> torch.Tensor:
        """
        z_i, z_j: Tensor shape (Batch_Size, Latent_Dim) representasi pasangan augmentasi
        """
        batch_size = z_i.size(0)
        
        # 1. Normalisasi L2 sepanjang dimensi representasi
        z_i_norm = F.normalize(z_i, p=2, dim=1)
        z_j_norm = F.normalize(z_j, p=2, dim=1)
        
        # 2. Gabungkan batch: Shape (2 * N, Latent_Dim)
        representations = torch.cat([z_i_norm, z_j_norm], dim=0)
        
        # 3. Hitung cosine similarity matrix: Shape (2 * N, 2 * N)
        sim_matrix = torch.matmul(representations, representations.T) / self.temperature
        
        # Masking diri sendiri (diagonal elements) agar tidak menjadi positive pair
        mask = torch.eye(2 * batch_size, dtype=torch.bool, device=z_i.device)
        sim_matrix.masked_fill_(mask, -1e9)
        
        # 4. Susun target positif
        # Elemen positif untuk z_i (index 0 ke N-1) adalah z_j (index N ke 2N-1)
        # Elemen positif untuk z_j (index N ke 2N-1) adalah z_i (index 0 ke N-1)
        targets_i = torch.arange(batch_size, 2 * batch_size, device=z_i.device)
        targets_j = torch.arange(0, batch_size, device=z_i.device)
        labels = torch.cat([targets_i, targets_j], dim=0)
        
        loss = F.cross_entropy(sim_matrix, labels)
        return loss

# Smoke test verifikasi tensor dimension
if __name__ == "__main__":
    B, D = 64, 128
    loss_fn = InfoNCELoss(temperature=0.1)
    t1 = torch.randn(B, D)
    t2 = torch.randn(B, D)
    loss_val = loss_fn(t1, t2)
    print(f"InfoNCE Loss Verification: {loss_val.item():.4f}")
    assert not torch.isnan(loss_val), "Loss bernilai NaN!"
```

### 7.2. Practical Example: Enterprise Production Pipeline
Implementasi komprehensif Vision Transformer Encoder dengan custom Projection Head, terintegrasi dengan FlashAttention (`torch.nn.functional.scaled_dot_product_attention`), Automatic Mixed Precision (AMP), dan Gradient Clipping.

```python
import os
import math
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Tuple, Optional
from dataclasses import dataclass

@dataclass
class ViTConfig:
    img_size: int = 224
    patch_size: int = 16
    in_channels: int = 3
    embed_dim: int = 768
    depth: int = 12
    num_heads: int = 12
    mlp_ratio: float = 4.0
    projection_dim: int = 128
    drop_rate: float = 0.0
    attn_drop_rate: float = 0.0

class PatchEmbedding(nn.Module):
    def __init__(self, config: ViTConfig):
        super().__init__()
        self.img_size = config.img_size
        self.patch_size = config.patch_size
        self.num_patches = (config.img_size // config.patch_size) ** 2
        
        # Menggunakan Conv2d dengan kernel dan stride setara patch size
        self.proj = nn.Conv2d(
            config.in_channels,
            config.embed_dim,
            kernel_size=config.patch_size,
            stride=config.patch_size
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # B: Batch size, C: Channels, H: Height, W: Width
        B, C, H, W = x.shape
        assert H == self.img_size and W == self.img_size, \
            f"Resolusi input ({H}x{W}) tidak sesuai konfigurasi ({self.img_size}x{self.img_size})."
        
        # (B, C, H, W) -> (B, Embed_Dim, N_h, N_w) -> (B, Embed_Dim, N_patches) -> (B, N_patches, Embed_Dim)
        x = self.proj(x).flatten(2).transpose(1, 2)
        return x

class FlashTransformerBlock(nn.Module):
    def __init__(self, config: ViTConfig):
        super().__init__()
        self.embed_dim = config.embed_dim
        self.num_heads = config.num_heads
        self.head_dim = config.embed_dim // config.num_heads
        assert self.head_dim * config.num_heads == self.embed_dim, "embed_dim harus habis dibagi num_heads"

        self.norm1 = nn.LayerNorm(config.embed_dim, eps=1e-6)
        self.qkv = nn.Linear(config.embed_dim, config.embed_dim * 3, bias=True)
        self.proj = nn.Linear(config.embed_dim, config.embed_dim)
        self.attn_drop_rate = config.attn_drop_rate

        self.norm2 = nn.LayerNorm(config.embed_dim, eps=1e-6)
        mlp_hidden_dim = int(config.embed_dim * config.mlp_ratio)
        self.mlp = nn.Sequential(
            nn.Linear(config.embed_dim, mlp_hidden_dim),
            nn.GELU(),
            nn.Dropout(config.drop_rate),
            nn.Linear(mlp_hidden_dim, config.embed_dim),
            nn.Dropout(config.drop_rate)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # 1. Multi-Head Self Attention via FlashAttention Kernel
        B, N, C = x.shape
        residual = x
        x_norm = self.norm1(x)
        
        qkv = self.qkv(x_norm).reshape(B, N, 3, self.num_heads, self.head_dim).permute(2, 0, 3, 1, 4)
        q, k, v = qkv[0], qkv[1], qkv[2]  # Shape: (B, num_heads, N, head_dim)
        
        # Menggunakan FlashAttention-2 di level C++/CUDA via scaled_dot_product_attention
        attn_out = F.scaled_dot_product_attention(
            q, k, v,
            dropout_p=self.attn_drop_rate if self.training else 0.0,
            is_causal=False
        )
        
        attn_out = attn_out.transpose(1, 2).reshape(B, N, C)
        x = residual + self.proj(attn_out)

        # 2. MLP / Feed-Forward Network
        x = x + self.mlp(self.norm2(x))
        return x

class ViTRepresentationLearningBackbone(nn.Module):
    def __init__(self, config: ViTConfig):
        super().__init__()
        self.config = config
        self.patch_embed = PatchEmbedding(config)
        
        # Token representasi global (Class/CLS Token)
        self.cls_token = nn.Parameter(torch.zeros(1, 1, config.embed_dim))
        self.pos_embed = nn.Parameter(torch.zeros(1, self.patch_embed.num_patches + 1, config.embed_dim))
        self.pos_drop = nn.Dropout(p=config.drop_rate)
        
        # Transformer Blocks
        self.blocks = nn.ModuleList([
            FlashTransformerBlock(config) for _ in range(config.depth)
        ])
        self.norm = nn.LayerNorm(config.embed_dim, eps=1e-6)
        
        # Non-Linear MLP Projection Head (SimCLR v2 style)
        self.projector = nn.Sequential(
            nn.Linear(config.embed_dim, config.embed_dim),
            nn.BatchNorm1d(config.embed_dim),
            nn.ReLU(inplace=True),
            nn.Linear(config.embed_dim, config.projection_dim, bias=False)
        )
        
        self._init_weights()

    def _init_weights(self):
        # Truncated Normal Initialization
        nn.init.trunc_normal_(self.pos_embed, std=0.02)
        nn.init.trunc_normal_(self.cls_token, std=0.02)
        self.apply(self._init_layer_weights)

    def _init_layer_weights(self, m: nn.Module):
        if isinstance(m, nn.Linear):
            nn.init.trunc_normal_(m.weight, std=0.02)
            if m.bias is not None:
                nn.init.constant_(m.bias, 0)
        elif isinstance(m, nn.LayerNorm):
            nn.init.constant_(m.weight, 1.0)
            nn.init.constant_(m.bias, 0)

    def forward_features(self, x: torch.Tensor) -> torch.Tensor:
        B = x.shape[0]
        x = self.patch_embed(x)
        
        cls_tokens = self.cls_token.expand(B, -1, -1)
        x = torch.cat((cls_tokens, x), dim=1)
        x = self.pos_drop(x + self.pos_embed)
        
        for block in self.blocks:
            x = block(x)
            
        x = self.norm(x)
        # Mengembalikan representasi laten dari CLS Token
        return x[:, 0]

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        features = self.forward_features(x)
        projections = self.projector(features)
        return features, projections

# =========================================================================
# Production Engine: Orchestrator Loop dengan AMP & Profiler
# =========================================================================
class EnterpriseTrainer:
    def __init__(self, model: nn.Module, lr: float = 1e-4, weight_decay: float = 1e-2):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = model.to(self.device)
        self.optimizer = torch.optim.AdamW(
            self.model.parameters(),
            lr=lr,
            weight_decay=weight_decay,
            betas=(0.9, 0.95)
        )
        self.criterion = InfoNCELoss(temperature=0.07)
        # BF16 Native scaling (tidak membutuhkan GradScaler eksternal jika didukung arsitektur Ampere/Hopper)
        self.use_amp = torch.cuda.is_available() and torch.cuda.is_bf16_supported()
        self.scaler = torch.cuda.amp.GradScaler(enabled=(not self.use_amp and torch.cuda.is_available()))
        self.dtype = torch.bfloat16 if self.use_amp else torch.float16

    def train_step(self, view1: torch.Tensor, view2: torch.Tensor) -> float:
        self.model.train()
        self.optimizer.zero_grad(set_to_none=True) # Mempercepat GC memori CUDA
        
        view1 = view1.to(self.device, non_blocking=True)
        view2 = view2.to(self.device, non_blocking=True)
        
        with torch.autocast(device_type=self.device.type, dtype=self.dtype, enabled=torch.cuda.is_available()):
            _, z1 = self.model(view1)
            _, z2 = self.model(view2)
            loss = self.criterion(z1, z2)

        if self.use_amp:
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
            self.optimizer.step()
        else:
            self.scaler.scale(loss).backward()
            self.scaler.unscale_(self.optimizer)
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
            self.scaler.step(self.optimizer)
            self.scaler.update()

        return loss.item()

if __name__ == "__main__":
    cfg = ViTConfig(
        img_size=224,
        patch_size=16,
        embed_dim=384, # Small ViT baseline
        depth=6,
        num_heads=6,
        projection_dim=128
    )
    model = ViTRepresentationLearningBackbone(cfg)
    trainer = EnterpriseTrainer(model)
    
    # Mock data pipeline batch
    dummy_v1 = torch.randn(8, 3, 224, 224)
    dummy_v2 = torch.randn(8, 3, 224, 224)
    
    loss_val = trainer.train_step(dummy_v1, dummy_v2)
    print(f"Executed single step successfully. Loss: {loss_val:.6f}")
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario: Pipeline Deteksi Anomali Citra Medis Multi-Center (Radiologi) Skala 10 Juta Data
- **Problem Statement**: Konsorsium 15 rumah sakit mengumpulkan 10.000.000 citra CT/X-Ray beresolusi tinggi. Kurang dari 0.1% citra memiliki anotasi patologi spesifik dari radiolog bersertifikat. Domain bias sangat tinggi antar rumah sakit karena perbedaan merek scanner (Siemens, GE, Philips).
- **Arsitektur Solusi**:
  1. **Phase 1: Pre-training**: Melatih ViT-Large (304M parameter) menggunakan Masked Autoencoder (MAE) dengan masking ratio 75%.
  2. **Phase 2: Self-Distillation Domain Alignment**: Menggunakan DINO v2 (Multi-crop cross-entropy) dengan Sinkhorn-Knopp centering untuk menyelaraskan representasi fitur tanpa terpengaruh artefak visual scanner rumah sakit tertentu.
  3. **Phase 3: Zero-shot/Few-shot Linear Probing**: Mengekstrak *frozen representations* dan melatih classifier Logistic Regression ter-regularisasi untuk mendeteksi 40 jenis kelainan paru-paru.
- **Infrastruktur Produksi**:
  - Cluster: 32 Node @ 8x NVIDIA H100 SXM5 (256 GPU).
  - Interkoneksi: 3.2 Tbps InfiniBand NDR.
  - Skema Training: FSDP Full Shard (ZeRO-3) dengan PyTorch 2.2 compile (`torch.compile(mode="max-autotune")`).
  - Throughput: 14.500 images/second total cluster throughput.
- **Hasil Bisnis**:
  - Peningkatan AUC-ROC dari 0.74 (Supervised ResNet baseline pada data berlabel terbatas) menjadi **0.93** (MAE + DINO representation linear probe).
  - Reduksi biaya anotasi klinis sebesar $1.2M USD karena dokter hanya perlu melabeli 500 sampel per kelas patologi untuk downstream validation.

---

## 9. Trade-offs

| Parameter/Arsitektur | Pendekatan A | Pendekatan B | Analisis Komparasi Teknis (SLA, Memori, Biaya) |
| :--- | :--- | :--- | :--- |
| **Metode SSL** | **SimCLR (Contrastive)** | **MAE (Masked Modeling)** | SimCLR butuh ukuran batch sangat masif (e.g., 4096) untuk sampel negatif (memory hungry), sementara MAE hanya memproses 25% patch yang terlihat pada encoder, menghemat compute/VRAM hingga **3-4x** lebih efisien. |
| **Mekanisme Attention** | **Standard PyTorch Attention** | **FlashAttention-2** | Standard Attention memiliki kompleksitas memori $\mathcal{O}(N^2)$ (OOM pada token sequence panjang); FlashAttention mengeksekusi $\mathcal{O}(N)$ IO bandwidth memori, meningkatkan kecepatan hingga **2.5x-4x** tanpa degradasi presisi. |
| **Model Distribution** | **DDP (Distributed Data Parallel)** | **FSDP (Fully Sharded Data Parallel)** | DDP menduplikasi seluruh bobot model di setiap GPU (terbatas pada ukuran model yang muat di 1 GPU); FSDP memecah bobot, gradien, dan optimizer states antar GPU, memungkinkan model skala ratusan miliar parameter dengan trade-off sedikit overhead komunikasi all-gather. |
| **Inference Format** | **Eager PyTorch (FP32)** | **TensorRT Engine (INT8)** | Eager PyTorch memiliki latensi tinggi (~45ms) dan overhead runtime interpreter; TensorRT melakukan kernel fusion dan FP8/INT8 calibration, menekan latensi hingga **< 4ms** dengan penghematan memory footprint **75%**. |

---

## 10. Common Mistakes & Troubleshooting

### 1. Representation Collapse pada Contrastive Learning
- **Gejala**: Loss InfoNCE drop secara drastis ke level statis yang sangat rendah dalam beberapa step awal, namun representasi menghasilkan akurasi linear probing acak (~1/Jumlah Kelas).
- **Akar Masalah**: Matriks projection head memetakan semua embedding ke vektor konstan, atau ketiadaan *stop-gradient* / repulsion mechanism.
- **Solusi**: Pastikan normalisasi L2 diaplikasikan sebelum komputasi similarity; periksa implementasi masking diagonal agar positive pair tidak saling merepulse; gunakan Batch Normalization atau Sinkhorn-Knopp centering pada projection head.

### 2. Gradient Overflow / Underflow pada FP16 Mixed Precision
- **Gejala**: Gradien bernilai `NaN` atau `Inf`, bobot model menjadi divergen secara tiba-tiba.
- **Akar Masalah**: Dynamic range FP16 terbatas ($6.55 \times 10^4$). Matriks attention logit ($\mathbf{Q}\mathbf{K}^T$) melampaui batas representasi.
- **Solusi**: Pindah ke format **Bfloat16** (BF16) pada arsitektur modern (Ampere ke atas) karena memiliki rentang dinamis eksponen yang identik dengan FP32. Jika terpaksa memakai FP16, pastikan menggunakan `torch.cuda.amp.GradScaler` dan scale dot-product attention dengan pembagi $\sqrt{d_k}$.

### 3. CPU Data-Loading Starvation (GPU Volatilization < 30%)
- **Gejala**: Utility GPU berosilasi drastis (0% -> 100% -> 0%); waktu epoch didominasi I/O wait time.
- **Akar Masalah**: Augmentasi gambar yang berat dieksekusi secara sinkron di thread CPU Python menggunakan pustaka standar yang lambat.
- **Solusi**: 
  - Set `num_workers = 4 * jumlah_gpu`.
  - Pasang `pin_memory=True` dan `persistent_workers=True` pada PyTorch DataLoader.
  - Gunakan pustaka hardware-accelerated augmentation seperti NVIDIA DALI atau Albumentations berbasis C++.

---

## 11. Best Practices (Production Checklist)

Berikut adalah checklist wajib sebelum deployment pipeline representation learning ke cluster produksi:

- [ ] **Deterministic Seed & Distributed Alignment**: Mengatur seed PyTorch, CUDA, dan NumPy via worker initialization function.
- [ ] **Memory Allocation Optimization**: Set environment variable `export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` untuk mencegah fragmentasi memori VRAM.
- [ ] **Zero-Redundancy Profiling**: Menjalankan profiling setidaknya 20 step menggunakan `torch.profiler.profile()` untuk mendeteksi memory bottleneck dan GPU kernel bubble.
- [ ] **Gradient Clipping**: Selalu sertakan `clip_grad_norm_` dengan threshold 1.0 s.d. 3.0 untuk menstabilkan training ViT deep layer.
- [ ] **Learning Rate Scheduling**: Terapkan Linear Warmup selama minimal 10% total training step, diikuti Cosine Decay menuju 1% dari target peak learning rate.
- [ ] **Loss Scale & Gradient Accumulation**: Konfigurasi effective batch size $\ge 1024$ (untuk SimCLR/DINO) menggunakan gradient accumulation steps jika VRAM fisik terbatas.
- [ ] **Model Compilation**: Eksekusi `torch.compile(model)` untuk menyatukan operasi elementwise (kernel fusion) dan meniadakan overhead runtime Python.

---

## 12. Hands-on Practice

Simpan seluruh skrip latihan berikut ke dalam direktori struktur:
`hands-on/m02/`

### File: `hands-on/m02/dataset_pipeline.py`
Membangun dual-view transformation pipeline teroptimasi untuk contrastive representation learning.

```python
# hands-on/m02/dataset_pipeline.py
import torch
from torchvision import transforms
from torchvision.datasets import FakeData
from torch.utils.data import DataLoader, Dataset
from typing import Tuple

class ContrastivePairTransform:
    """
    Menghasilkan dua augmentasi stokastik independen dari citra yang sama.
    """
    def __init__(self, img_size: int = 224):
        self.transform = transforms.Compose([
            transforms.RandomResizedCrop(img_size, scale=(0.2, 1.0)),
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.RandomApply([
                transforms.ColorJitter(brightness=0.4, contrast=0.4, saturation=0.4, hue=0.1)
            ], p=0.8),
            transforms.RandomGrayscale(p=0.2),
            transforms.GaussianBlur(kernel_size=int(img_size * 0.1) // 2 * 2 + 1, sigma=(0.1, 2.0)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])

    def __call__(self, x) -> Tuple[torch.Tensor, torch.Tensor]:
        x1 = self.transform(x)
        x2 = self.transform(x)
        return x1, x2

class ContrastiveDatasetWrapper(Dataset):
    def __init__(self, base_dataset: Dataset, transform: ContrastivePairTransform):
        self.base_dataset = base_dataset
        self.transform = transform

    def __len__(self):
        return len(self.base_dataset)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        image, _ = self.base_dataset[idx]
        return self.transform(image)

def get_contrastive_loader(batch_size: int = 32, num_workers: int = 2) -> DataLoader:
    # Memanfaatkan Synthetic Dataset untuk validasi performa pipeline
    raw_data = FakeData(size=1000, image_size=(3, 224, 224), num_classes=10)
    pipeline = ContrastivePairTransform(img_size=224)
    dataset = ContrastiveDatasetWrapper(raw_data, transform=pipeline)
    
    loader = DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=num_workers,
        pin_memory=torch.cuda.is_available(),
        drop_last=True
    )
    return loader

if __name__ == "__main__":
    loader = get_contrastive_loader(batch_size=4)
    v1, v2 = next(iter(loader))
    print(f"Batch loaded. View1 shape: {v1.shape}, View2 shape: {v2.shape}")
```

### File: `hands-on/m02/train_representation.py`
Skrip eksekusi end-to-end terintegrasi dengan tracing performa profil CUDA.

```python
# hands-on/m02/train_representation.py
import sys
import torch
import torch.profiler
from dataset_pipeline import get_contrastive_loader

# Mengimpor modul arsitektur dari materi sebelumnya
from typing import TYPE_CHECKING
if not TYPE_CHECKING:
    import importlib.util
    # Dynamic loader or paste ViTRepresentationLearningBackbone & EnterpriseTrainer classes here
```

*(Gunakan kelas `ViTConfig`, `ViTRepresentationLearningBackbone`, dan `EnterpriseTrainer` dari Section 7.2 untuk menjalankan skrip ini)*.

```python
# Tambahkan snippet eksekusi profiler berikut ke hands-on/m02/train_representation.py
from datetime import datetime

def run_profiling_benchmark():
    from dataset_pipeline import get_contrastive_loader
    # Asumsi kelas Section 7.2 tersedia di namespace
    cfg = ViTConfig(img_size=224, patch_size=16, embed_dim=256, depth=4, num_heads=4, projection_dim=64)
    model = ViTRepresentationLearningBackbone(cfg)
    trainer = EnterpriseTrainer(model)
    loader = get_contrastive_loader(batch_size=16, num_workers=2)
    
    print("Memulai Training Step dengan PyTorch Profiler...")
    with torch.profiler.profile(
        activities=[
            torch.profiler.ProfilerActivity.CPU,
            torch.profiler.ProfilerActivity.CUDA,
        ],
        schedule=torch.profiler.schedule(wait=1, warmup=1, active=3, repeat=1),
        on_trace_ready=torch.profiler.tensorboard_trace_handler('./hands-on/m02/log/profiler'),
        record_shapes=True,
        profile_memory=True,
        with_stack=True
    ) as prof:
        for step, (v1, v2) in enumerate(loader):
            loss = trainer.train_step(v1, v2)
            prof.step()
            print(f"Step {step+1}/5 - Loss: {loss:.4f}")
            if step >= 4:
                break

    print("Profiling selesai. Buka tensorboard untuk menganalisis eksekusi kernel.")

if __name__ == "__main__":
    run_profiling_benchmark()
```

---

## 13. Exercise

### Level Easy
1. Modifikasi arsitektur `FlashTransformerBlock` pada Section 7.2 agar menerima argumen dropout stochastic depth (DropPath) linear decay dari layer 0 hingga layer `depth - 1`.
2. Hitung jumlah total patch ($N$) jika citra beresolusi $384 \times 384$ diinput ke dalam Vision Transformer dengan patch size $P=12$. Tunjukkan perhitungan matematisnya.

### Level Medium
1. Implementasikan algoritma **Cosine Annealing Learning Rate Scheduler with Linear Warmup** secara murni menggunakan `torch.optim.lr_scheduler.LambdaLR`. Uji scheduler tersebut selama 100 epoch dengan 10 warmup epoch pertama.
2. Buat unit-test PyTorch untuk memastikan matriks kemiripan (similarity matrix) pada fungsi loss InfoNCE bernilai simetris terhadap diagonal saat representasi dinormalisasi secara sempurna.

### Level Hard
1. Implementasikan teknik **Online Linear Probing**: Selama ViT melakukan pre-training SSL (loss InfoNCE), buat cabang linear layer terpisah yang menerima *detached representations* ($\mathbf{h}.\text{detach}()$) untuk menghitung CrossEntropyLoss pada downstream label secara real-time tanpa mengalirkan gradien ke backbone ViT.
2. Ubah `FlashTransformerBlock` standar menjadi **Rotary Position Embedding (RoPE) 2D** untuk patch sequence, meniadakan parameter absolut position embedding `self.pos_embed`.

---

## 14. Challenge

### Arsitektur Zero-Bubble Multi-Modal Representation Engine
Sebuah startup bioinformatika meminta Anda mendesain fondasi model representasi deep learning yang memetakan **Citra Mikroskopis Sel (ResNet/ViT)** dan **Sekuens DNA (Transformer 1D)** ke dalam ruang latent yang sama (*Joint Embedding Space*):

- **Karakteristik Masalah**:
  1. Pasangan data citra dan sekuens DNA sangat asimetris dalam ukuran komputasi: Citra membutuhkan FLOPs komputasi $5\times$ lebih besar daripada pemrosesan sekuens genetik.
  2. Latensi inferensi cross-modal retrieval harus berada di bawah **15 milidetik** pada batch size 128.
  3. Memory footprint GPU tidak boleh melebihi 16GB VRAM saat batch training skala 2048.
- **Instruksi Eksekusi**:
  1. Rancang arsitektur Dual-Tower (Vision Encoder + Sequence Encoder) dengan asymmetric projection dimension.
  2. Susun proposal rancangan teknik distributed training (FSDP vs DeepSpeed ZeRO-Stage 3) lengkap dengan mitigasi *straggler problem* akibat asimetri FLOPs antar dua encoder tersebut.
  3. Formulasikan modifikasi fungsi loss (gabungan InfoNCE + Masked Sequence Modeling) untuk memaksa representasi tidak terdegenerasi ke domain citra saja (*cross-modal dominance collapse*).

---

## 15. Quiz Evaluasi Pemahaman

### 15.1. Pertanyaan Basic
1. Mengapa fungsi InfoNCE loss membutuhkan normalisasi L2 pada representasi embedding sebelum melakukan operasi dot-product?
2. Apa dampak matematis dari pemilihan parameter temperatur $\tau$ yang mendekati 0 pada fungsi loss SimCLR?
3. Sebutkan perbedaan fundamental antara Patch Embedding berbasis Convolution 2D (`kernel=P, stride=P`) dengan linear flattening biasa!
4. Mengapa representasi dari encoder pada Masked Autoencoder (MAE) diproses hanya dari token yang terlihat (*visible patches*), bukan dari seluruh token termasuk token mask?
5. Apa perbedaan mendasar antara representasi laten $\mathbf{h}$ (output backbone) dan projection embedding $\mathbf{z}$ (output projection head) terkait downstream task?

### 15.2. Pertanyaan Intermediate
6. Bagaimana algoritma FlashAttention menghindari pemborosan IO Bandwidth memori GPU (HBM) saat menghitung matriks probabilitas attention?
7. Jelaskan mekanisme terjadinya *Dimensional Collapse* pada Self-Supervised Learning dan bagaimana penambahan regularisasi rank/decorrelation (seperti Barlow Twins atau VICReg) dapat memecahkannya!
8. Apa kelemahan penggunaan FP16 standar dibandingkan Bfloat16 saat melatih Transformer berskala besar tanpa penyesuaian dinamis gradient scaler?
9. Jelaskan bagaimana PyTorch FSDP (ZeRO-3) memecah optimizer state, gradient, dan parameter pada forward dan backward pass!
10. Mengapa aktivasi *Activation Checkpointing* (Gradient Checkpointing) dapat menghemat VRAM secara signifikan, dan apa konsekuensinya terhadap total waktu komputasi (FLOPs)?

### 15.3. Skenario Kasus Produksi
11. **Kasus 1**: Tim AI Engineer Anda melatih ViT-Base pada cluster 8x A100. Pada epoch ke-15, training tiba-tiba macet (hang) tanpa pesan error, utilisasi GPU 0%, dan memory usage konstan di 98%. Langkah diagnostik dan mitigasi internal apa yang harus Anda lakukan?
12. **Kasus 2**: Model representasi SSL yang Anda latih menghasilkan akurasi linear probe downstream yang buruk pada citra beresolusi tinggi ($1024 \times 1024$), padahal pre-training dilakukan secara ekstensif pada resolusi $224 \times 224$. Bagaimana solusi architectural interpolation untuk positional embedding ViT tersebut?
13. **Kasus 3**: Saat mengekspor arsitektur ViT kustom yang memanfaatkan dynamic patch sizes ke OpenVINO/TensorRT, konverter gagal melakukan kernel compilation pada node Multi-Head Attention. Di mana letak potensi ketidakcocokan graf dan bagaimana mengatasinya menggunakan TorchDynamo custom decomposition?

---

### Kunci Jawaban Singkat & Guidance Evaluasi

#### Pertanyaan Basic
1. Tanpa normalisasi L2, dot-product mengukur besaran magnitude vektor bersamaan dengan arah sudutnya. Optimizer dapat meminimalkan loss hanya dengan memperbesar magnitudo vektor embedding secara tak hingga tanpa menyelaraskan semantik arah representasi.
2. Nilai $\tau \to 0$ menyebabkan distribusi softmax menjadi Dirac delta (sangat tajam), gradien meledak (*gradient explosion*), dan model hanya fokus secara ekstrem pada single hard negative terdekat dengan mengabaikan seluruh distribusi manifold data.
3. Secara komputasi matematis keduanya ekuivalen; namun Conv2d memanfaatkan kernel GEMM yang sangat teroptimasi di level cuDNN/CUDA, menghasilkan throughput akses memori yang jauh lebih efisien dibandingkan slicing tensor dan matrix multiplication manual.
4. Membuang 75% token mask secara langsung menghemat komputasi encoder ViT hingga $\approx 4\times$ FLOPs dan memori secara kuadratik, memungkinkan encoder yang sangat dalam (*heavyweight*) dilatih dengan efisiensi tinggi.
5. Ruang embedding $\mathbf{z}$ kehilangan informasi invarian tertentu karena dipaksa secara spesifik memenuhi objektif InfoNCE (membuang variasi warna/tekstur yang di-augmentasi). Ruang laten $\mathbf{h}$ mempertahankan fitur semantik yang jauh lebih kaya dan general untuk downstream tasks.

#### Pertanyaan Intermediate
6. FlashAttention memanfaatkan teknik tiling (memecah matriks menjadi blok-blok kecil yang muat di SRAM GPU) dan online softmax reduction, sehingga tidak pernah mengalokasikan dan membaca/menulis intermediate attention matrix ($N \times N$) ke HBM utama.
7. Dimensional collapse terjadi ketika varians fitur pada dimensi tertentu mendekati 0. Barlow Twins/VICReg memaksakan matriks cross-correlation antar representasi mendekati Identity Matrix ($I$), secara eksplisit menuntut non-korelasi antar dimensi (*decorrelation*) dan varians per dimensi tetap berada di atas margin batas.
8. FP16 hanya memiliki 5 bit eksponen (rentang dinamis kecil $\approx 10^{-5}$ hingga $65504$), membuatnya sangat rentan terhadap underflow saat gradient dot-product bernilai kecil dan overflow saat logit attention besar. BF16 memiliki 8 bit eksponen (sama seperti FP32), meniadakan risiko overflow tanpa butuh dynamic loss scaling yang kompleks.
9. FSDP memecah model parameter, gradien, dan optimizer states. Saat forward pass, ia melakukan *all-gather* parameter untuk layer tertentu secara just-in-time, menghitung aktivasi, lalu segera membuang parameter layer lain dari memori. Hal yang sama diulangi saat backward pass via *reduce-scatter* gradien.
10. Activation checkpointing membuang aktivasi intermediate dari forward pass dan menghitungnya kembali (*recompute*) secara lokal saat backward pass. Ini memotong footprint memori aktivasi dari $\mathcal{O}(L)$ menjadi $\mathcal{O}(\sqrt{L})$, dengan trade-off penambahan komputasi FLOPs forward pass sebesar $\approx 33\%$.

#### Skenario Kasus Produksi
11. **Analisis**: Indikasi NCCL deadlock pada komunikasi distributed all-reduce (biasanya diakibatkan oleh hang pada dataloader worker tertentu atau out-of-sync barrier). **Mitigasi**: Set environment variable `NCCL_DEBUG=INFO` dan `TORCH_DISTRIBUTED_DEBUG=DETAIL`. Periksa apakah terjadi zombie thread pada CPU DataLoader (`pin_memory` thread contention) atau OOM silent error pada secondary GPU thread.
12. **Analisis**: Positional embedding $E_{pos}$ terikat pada grid geometri berukuran $14 \times 14$ ($224/16$). Pada resolusi $1024$, jumlah patch menjadi $64 \times 64$, menyebabkan kegagalan mapping token sequence. **Solusi**: Terapkan bicubic interpolation 2D dinamis pada weight matrix positional embedding untuk mengekspansi representasi spatial patch grid sebelum ditambahkan ke input token sequence.
13. **Analisis**: TensorRT static graph trace gagal menangani dynamic shape pada operasi reshape/transpose multi-head attention. **Solusi**: Definisikan dynamic axes eksplisit pada dynamic shape inputs profile; gunakan `torch.onnx.export` dengan `dynamo=True` dan daftarkan custom autograd function decomposition untuk kernel scaled dot product attention.

---

## 16. Summary

Representasi data modern bersandar pada pemahaman topologi mendalam tanpa supervisi label buatan. Melalui paradigma **Contrastive Learning (InfoNCE)** dan **Masked Autoencoders (MAE)**, neural network dipaksa mengekstraksi invarian semantik yang tangguh terhadap transformasi input.

Membawa arsitektur ini ke skala enterprise menuntut arsitek AI menguasai ekosistem internal hardware:
- Menggantikan standard attention dengan **FlashAttention-2** untuk mengeliminasi batasan *Memory Wall*.
- Memanfaatkan **Bfloat16** dan arsitektur sharding **FSDP** untuk melatih model parameter masif pada multi-GPU cluster.
- Menjaga stabilitas numerik dan mencegah representational collapse melalui pemahaman aljabar linier pada matriks representasi laten.

Kemampuan mengawinkan kedalaman matematika arsitektur representasi dengan efisiensi sistem komputasi performa tinggi (HPC) adalah pembeda utama antara Data Scientist teoritis dan Senior Enterprise AI Engineer.