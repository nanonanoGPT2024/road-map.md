# BAB 07: SPECIALIZED DEEP ARCHITECTURES (CV & NLP)
## MODUL 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Merancang dan Mengimplementasikan Arsitektur Lanjutan**: Membangun modul neural network state-of-the-art untuk Vision (Vision Transformer / ViT, ConvNeXt) dan NLP (Transformer Decoder-Only dengan Rotary Position Embeddings / RoPE, FlashAttention primitives) langsung menggunakan PyTorch tingkat lanjut.
- **Mengoptimalkan Komputasi Low-Level**: Menganalisis batasan memori I/O (*memory-bound* vs *compute-bound*), mengimplementasikan *Kernel Fusion*, *Mixed Precision Training* (AMP FP16/BF16), serta strategi pengelolaan KV Cache secara efisien.
- **Mengompilasi dan Mengonversi Model ke Engine Produksi**: Melakukan ekspor, tracing, validasi numerik, dan optimasi kompilasi model deep learning menggunakan **TorchScript**, **ONNX**, dan **NVIDIA TensorRT**.
- **Membangun Pipeline Serving Skala Enterprise**: Menerapkan arsitektur *high-throughput low-latency inference* menggunakan **Triton Inference Server** dengan kapabilitas *dynamic batching*, *concurrent model instances*, dan isolasi GPU memory.
- **Memitigasi Isu Keandalan Produksi**: Mengidentifikasi dan memecahkan masalah degradasi numerik (*underflow/overflow*), *CUDA Out-of-Memory (OOM)*, *latency spikes* (tail latency p99), dan regresi akurasi pasca-kuantisasi (INT8/FP8).

---

### 2. Prerequisite
Sebelum mempelajari modul ini, engineer harus memiliki pemahaman mendalam tentang:
- **Matematika Lanjutan**: Aljabar Linier Terapan (SVD, Proyeksi Matriks, Operasi Tensor N-Dimensi), Kalkulus Multivariat (Autograd, Jacobian, Hessian vector products), dan Teori Probabilitas (Cross-Entropy, Kullback-Leibler Divergence).
- **Core Deep Learning**: Fondasi Convolutional Neural Networks (ResNet, receptive field, stride, padding) dan Dasar Sequential Modeling (RNN, LSTM, Self-Attention vanilla).
- **Sistem Komputasi Akselerator**: Pemahaman arsitektur GPU NVIDIA (SMs, Warp, HBM, SRAM/Shared Memory, Tensor Cores), alokator memori CUDA, dan komunikasi host-to-device (PCIe bus bottleneck).
- **Perangkat Rekayasa Software**: Python 3.10+, PyTorch 2.x internals (`torch.compile`, FX Graphs), Docker, dan Linux Cgroups/Namespace basics.

---

### 3. Concept & Internal Architecture

#### 3.1 Paradigma Arsitektur: Vision Transformer (ViT) vs Modern Convolutions (ConvNeXt)
Secara historis, Computer Vision didominasi oleh inductive bias spasial lokal (*translation equivariance* dan *locality*) melalui konvolusi. Vision Transformer (ViT) mendobrak paradigma ini dengan memperlakukan citra sebagai sequence token 1D.

$$\mathbf{x} \in \mathbb{R}^{H \times W \times C} \xrightarrow{\text{Patchify}} \mathbf{x}_p \in \mathbb{R}^{N \times (P^2 \cdot C)}$$

Di mana $(H, W)$ adalah resolusi gambar, $C$ jumlah kanal, $P$ ukuran patch, dan $N = \frac{HW}{P^2}$ adalah panjang sequence patch yang dihasilkan.

```
+-------------------------------------------------------------------------------+
|                       VISION TRANSFORMER (ViT) FORWARD PASS                   |
+-------------------------------------------------------------------------------+
  Input Image [B, C, H, W]
        |
        v
  [ Patch Partition & Linear Projection ] ---> Output: [B, N, D]
        |
        v
  [ Prepend [CLS] Token & Add Positional Embeddings ] ---> Output: [B, N+1, D]
        |
        +-----------------------------------+
        |                                   |
        v                                   |
  [ LayerNorm (LN) ]                        |
        v                                   |
  [ Multi-Head Self-Attention (MHSA) ]      |  (Residual Connection 1)
        v                                   |
        +---------------------------------->+ ---> [ Add ]
        |
        +-----------------------------------+
        |                                   |
        v                                   |
  [ LayerNorm (LN) ]                        |
        v                                   |
  [ Multi-Layer Perceptron (MLP) ]          |  (Residual Connection 2)
        v                                   |
        +---------------------------------->+ ---> [ Add ]
        |
        v  (Ulangi sebanyak L Encoder Blocks)
  [ LayerNorm ]
        |
        v
  Extract [CLS] Token Index 0 ---> [ MLP Classification Head ] ---> Logits [B, Num_Classes]
```

##### Perbandingan Struktural: ViT vs ConvNeXt
ConvNeXt mengadopsi prinsip desain Transformer ke dalam arsitektur konvolusional murni:
1. **Inverted Bottleneck**: Meniru blok inverted bottleneck dari Transformer di mana dimensi tersembunyi MLP diperlebar $4\times$.
2. **Larger Kernel Sizes**: Menggunakan $7 \times 7$ *depthwise convolution* untuk mereplikasi receptive field yang luas menyerupai self-attention lokal.
3. **Micro-design Shifts**: Mengganti BatchNorm dengan LayerNorm, mengurangi frekuensi fungsi aktivasi (hanya menggunakan GELU satu kali per blok), dan memisahkan downsampling layer menjadi layer konvolusi independen ber-stride 2.

#### 3.2 NLP Modern: Decoder-Only, RoPE, dan Attention Scaling
Evolusi NLP dari encoder-decoder (BART, T5) menuju decoder-only (GPT-4, LLaMA, Mistral) didorong oleh efisiensi komputasi *causal language modeling* pada skala miliaran parameter.

##### Scaled Dot-Product Attention & Memory Footprint
Komputasi attention standar:

$$\text{Attention}(Q, K, V) = \text{softmax}\left(\frac{QK^T}{\sqrt{d_k}} + M\right)V$$

Di mana:
- $Q \in \mathbb{R}^{B \times H \times S \times D}$
- $K \in \mathbb{R}^{B \times H \times S \times D}$
- $V \in \mathbb{R}^{B \times H \times S \times D}$
- $M$ adalah causal mask matriks segitiga bawah dengan nilai $-\infty$ pada elemen masa depan.

**Bottleneck Matematis & Memori**: Operasi $QK^T$ menghasilkan matriks berukuran $S \times S$. Untuk sequence length $S = 32{,}768$ (32k context):
$$\text{Memory}_{QK^T} = 32768 \times 32768 \times 2\text{ bytes (FP16)} \approx 2.14\text{ GB per head per batch}.$$
Hal ini memicu I/O latency tinggi (*High Bandwidth Memory / HBM access*). Solusi modern mengimplementasikan **FlashAttention**, yang melakukan tiling komputasi attention di dalam SRAM GPU (kapasitas kecil, bandwidth $\approx 19\text{ TB/s}$) tanpa mengalokasikan matriks perantara $S \times S$ ke HBM (bandwidth $\approx 2-3\text{ TB/s}$).

##### Rotary Position Embedding (RoPE)
Alih-alih menambahkan embedding posisi absolut ke token input vector ($x + p$), RoPE mengalikan vektor representasi dengan matriks rotasi orthogonal ortogonal terhadap koordinat kompleks token:

$$R_{\Theta, m}^d = \text{diag}\left( R_{\theta_1, m}, R_{\theta_2, m}, \dots, R_{\theta_{d/2}, m} \right)$$

Di mana $R_{\theta_i, m}$ adalah matriks rotasi 2D:

$$R_{\theta_i, m} = \begin{pmatrix} \cos(m\theta_i) & -\sin(m\theta_i) \\ \sin(m\theta_i) & \cos(m\theta_i) \end{pmatrix}, \quad \theta_i = 10000^{-2(i-1)/d}$$

Sifat inner product invarian terhadap jarak relatif: $\langle R_m q, R_n k \rangle = g(q, k, m - n)$, yang memungkinkan model mengekstrapolasi sequence length di luar konteks training.

---

### 4. Why & What
| Dimensi | Pendekatan Konvensional (ResNet / LSTM / Vanilla BERT) | Arsitektur Modern Produksi (ViT / Modern Decoder-Only / ConvNeXt) |
| :--- | :--- | :--- |
| **Scaling Law** | Jenuh pada dataset besar; representasi saturasi pada model >100M parameter. | Skalabilitas performa konstan mengikuti compute power (Chinchilla / Kaplan laws). |
| **Generalisasi Konteks** | Window inference statis (512 token pada BERT); Local receptive field terbatas (3x3 receptive field). | Global multi-hop reasoning; context length dinamis hingga 32k - 1M token melalui RoPE interpolation. |
| **Compute / Memory Efficiency** | Komputasi FLOP-heavy tetapi memory footprint $O(S)$; eksekusi lambat pada GPU modern. | IO-Aware tiling (FlashAttention); kernel fusion teroptimasi untuk NVIDIA Tensor Cores. |
| **Serving Compatibility** | Sering menggunakan custom dynamic code execution yang sulit diekspor secara statis. | Desain arsitektur statis yang kompatibel penuh dengan TensorRT, ONNX Runtime, dan Triton. |

---

### 5. How: Workflow Detail
Siklus hidup deployment arsitektur CV & NLP tingkat lanjut dari kode mentah hingga inference server:

```
[ Phase 1: Architecture Design & Mixed-Precision Training ]
   - Implementasi PyTorch kustom (FlashAttention, RoPE, RMSNorm)
   - Training via DistributedDataParallel (DDP) / FSDP
   - Penggunaan torch.cuda.amp (Automatic Mixed Precision: BF16/FP16)
                    |
                    v
[ Phase 2: Graph Optimization & Compilation ]
   - Static shape freezing & trace validation
   - Kompilasi Model: torch.compile(mode="reduce-overhead")
   - Symbolic Tracing & Export ke ONNX Graph (Opset 17+)
                    |
                    v
[ Phase 3: Hardware Acceleration Compilation (TensorRT) ]
   - Parsing ONNX Graph ke TensorRT Builder
   - Layer Fusion (Conv + BatchNorm + ReLU -> Single Fused Kernel)
   - Dynamic Tensor Core Quantization (FP32 -> FP16 -> INT8/FP8 PTQ)
   - Serialisasi Engine Plan: model.engine
                    |
                    v
[ Phase 4: Production Deployment (Triton Inference Server) ]
   - Konfigurasi config.pbtxt (Dynamic Batching, Instance Groups)
   - Setup Shared Memory IPC (Inter-Process Communication)
   - Expose gRPC / HTTP endpoint dengan health-check & metrics Prometheus
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: FlashAttention vs Standard Attention
Bayangkan perpustakaan besar. 
- **Standard Attention**: Anda mengambil buku Query dan Key dari rak besar (HBM), menyalin tabel perbandingan raksasa sebesar $32{,}000 \times 32{,}000$ halaman ke atas meja baca besar, menulis catatan sementara di sana, lalu membaca buku Value untuk menghitung hasilnya, sebelum akhirnya membawa buku hasil ke kasir. Jika mejanya tidak muat, Anda akan kehabisan ruang (CUDA OOM).
- **FlashAttention**: Anda tidak pernah menyalin tabel raksasa. Anda membawa buku dalam blok-blok kecil ke meja pribadi Anda (SRAM), menghitung sebagian softmax dan agregasi bobot secara lokal (*online softmax accumulation*), memperbarui hasil sementara di catatan kecil Anda, dan langsung mengembalikan blok tersebut ke rak. Ruang meja yang dibutuhkan sangat kecil, dan bolak-balik ke rak utama berkurang drastis.

#### Diagram Komparasi Alur Memori GPU

```
STANDARD ATTENTION MEMORY FLOW (Memory-Bound)
+---------------------------------------------------------------------------------+
| High Bandwidth Memory (HBM) [Slow: ~2 TB/s]                                     |
|  [Q]       [K]              [QK^T Matrix: O(N^2)]            [Softmax]    [Out] |
|   |         |                      ^                            |           ^   |
+---|---------|----------------------|----------------------------|-----------|---+
    | Read    | Read                 | Write (Huge Memory)        | Write     |
    v         v                      |                            v           |
+------------------------------------+----------------------------------------+---+
| SRAM (On-Chip Cache) [Fast: ~19 TB/s]                                           |
|   Hitung: Q * K^T -------------> Alokasi HBM -------------> Hitung Softmax      |
+---------------------------------------------------------------------------------+

FLASH ATTENTION MEMORY FLOW (IO-Aware Tiled)
+---------------------------------------------------------------------------------+
| High Bandwidth Memory (HBM) [Minimal Traffic]                                   |
|  [Q] [K] [V]                                                              [Out] |
|   |   |   |                                                                 ^   |
+---|---|---|-----------------------------------------------------------------|---+
    | Read Blocks (Tiles)                                                     | Write
    v   v   v                                                                 |
+-----------------------------------------------------------------------------|---+
| SRAM (On-Chip Cache)                                                        |
|   Loop Blok Q_i, K_j, V_j:                                                  |
|     1. Hitung Partial S_ij = Q_i * K_j^T                                    |
|     2. Online Softmax Re-scaling: update running max m_i & running sum l_i  |
|     3. Akumulasi Output Partial: O_i = O_i * scale + Softmax(S_ij) * V_j   |
+---------------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Implementasi Modul Rotary Positional Embedding (RoPE)
Kode PyTorch murni untuk mengaplikasikan RoPE pada tensor Query/Key secara efisien tanpa komputasi matriks densitas penuh.

```python
import torch
import torch.nn as nn

class RotaryPositionalEmbedding(nn.Module):
    """
    Mengimplementasikan Rotary Positional Embeddings (RoPE) sesuai formulasi Su et al.
    Diterapkan langsung pada dimensi kepala (head_dim).
    """
    def __init__(self, dim: int, max_seq_len: int = 4096, base: float = 10000.0):
        super().__init__()
        self.dim = dim
        self.max_seq_len = max_seq_len
        self.base = base
        
        # Hitung frekuensi inverse: theta_i = 10000^(-2(i-1)/dim)
        # Dimensi harus genap untuk rotasi 2D berpasangan
        assert dim % 2 == 0, "Dimension must be divisible by 2 for RoPE"
        inv_freq = 1.0 / (self.base ** (torch.arange(0, self.dim, 2).float() / self.dim))
        self.register_buffer("inv_freq", inv_freq, persistent=False)
        
        # Precompute sin & cos cache
        self._build_cache(max_seq_len)

    def _build_cache(self, seq_len: int):
        # Tensor posisi: [0, 1, 2, ..., seq_len - 1]
        t = torch.arange(seq_len, dtype=self.inv_freq.dtype)
        # Outer product: [seq_len, dim / 2]
        freqs = torch.outer(t, self.inv_freq)
        # Duplikasi frekuensi untuk sin dan cos berpasangan: [seq_len, dim]
        emb = torch.cat((freqs, freqs), dim=-1)
        self.register_buffer("cos_cached", emb.cos(), persistent=False)
        self.register_buffer("sin_cached", emb.sin(), persistent=False)

    def _rotate_half(self, x: torch.Tensor) -> torch.Tensor:
        # Rotasi koordinat: [-x2, x1]
        d_2 = x.shape[-1] // 2
        x1 = x[..., :d_2]
        x2 = x[..., d_2:]
        return torch.cat((-x2, x1), dim=-1)

    def forward(self, x: torch.Tensor, seq_len: int) -> tuple[torch.Tensor, torch.Tensor]:
        """
        Input x: [Batch, Heads, Seq_Len, Head_Dim]
        Mengembalikan tuple (cos, sin) yang di-slice sesuai panjang seq_len.
        """
        if seq_len > self.max_seq_len:
            self._build_cache(seq_len)
            self.max_seq_len = seq_len
            
        return (
            self.cos_cached[:seq_len, ...].to(dtype=x.dtype),
            self.sin_cached[:seq_len, ...].to(dtype=x.dtype)
        )

def apply_rotary_pos_emb(q: torch.Tensor, k: torch.Tensor, cos: torch.Tensor, sin: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    # Reshape cos/sin untuk broadcasting terhadap heads: [1, 1, Seq_Len, Head_Dim]
    cos = cos.unsqueeze(0).unsqueeze(1)
    sin = sin.unsqueeze(0).unsqueeze(1)
    
    # R_theta * x = (x * cos) + (rotate_half(x) * sin)
    def rotate_half_inline(x):
        d_2 = x.shape[-1] // 2
        return torch.cat((-x[..., d_2:], x[..., :d_2]), dim=-1)

    q_rot = (q * cos) + (rotate_half_inline(q) * sin)
    k_rot = (k * cos) + (rotate_half_inline(k) * sin)
    return q_rot, k_rot

if __name__ == "__main__":
    B, H, S, D = 2, 8, 512, 64
    q = torch.randn(B, H, S, D)
    k = torch.randn(B, H, S, D)
    
    rope = RotaryPositionalEmbedding(dim=D, max_seq_len=1024)
    cos, sin = rope(q, seq_len=S)
    q_out, k_out = apply_rotary_pos_emb(q, k, cos, sin)
    
    print(f"Shape Input Q : {q.shape}")
    print(f"Shape Output Q: {q_out.shape}")
    assert q_out.shape == q.shape, "Shape output harus identik dengan input"
```

---

#### 7.2 Practical Example: Production-Ready Vision Transformer Block dengan FlashAttention & ONNX Traceability
Implementasi blok transformer computer vision yang modular, mendukung `scaled_dot_product_attention` (FlashAttention-backed), dan dapat diekspor langsung ke engine ONNX.

```python
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Optional

class PatchEmbedding(nn.Module):
    """Konversi citra 2D [B, C, H, W] menjadi Sequence Patch 1D [B, N, D]."""
    def __init__(self, img_size: int = 224, patch_size: int = 16, in_chans: int = 3, embed_dim: int = 768):
        super().__init__()
        self.img_size = img_size
        self.patch_size = patch_size
        self.num_patches = (img_size // patch_size) ** 2
        
        # Proyeksi linier diimplementasikan melalui Convolusi 2D dengan kernel == stride == patch_size
        self.proj = nn.Conv2d(in_chans, embed_dim, kernel_size=patch_size, stride=patch_size)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        B, C, H, W = x.shape
        assert H == self.img_size and W == self.img_size, f"Input image mismatch: {H}x{W} != {self.img_size}x{self.img_size}"
        # [B, C, H, W] -> [B, D, H/P, W/P] -> Flatten -> [B, D, N] -> Transpose -> [B, N, D]
        x = self.proj(x).flatten(2).transpose(1, 2)
        return x

class FastViTAttention(nn.Module):
    """Multi-Head Self-Attention menggunakan FlashAttention via PyTorch 2.0 SDPA."""
    def __init__(self, dim: int, num_heads: int = 8, qkv_bias: bool = True, attn_drop: float = 0.0, proj_drop: float = 0.0):
        super().__init__()
        assert dim % num_heads == 0, "Dimension must be divisible by num_heads"
        self.num_heads = num_heads
        self.head_dim = dim // num_heads
        self.scale = self.head_dim ** -0.5

        # Proyeksi fused QKV ke satu tensor untuk efisiensi komputasi cache
        self.qkv = nn.Linear(dim, dim * 3, bias=qkv_bias)
        self.attn_drop = attn_drop
        self.proj = nn.Linear(dim, dim)
        self.proj_drop = nn.Dropout(proj_drop)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        B, N, C = x.shape
        # qkv shape: [B, N, 3, Num_Heads, Head_Dim] -> permute -> [3, B, Num_Heads, N, Head_Dim]
        qkv = self.qkv(x).reshape(B, N, 3, self.num_heads, self.head_dim).permute(2, 0, 3, 1, 4)
        q, k, v = qkv[0], qkv[1], qkv[2]

        # PyTorch SDPA otomatis memanggil FlashAttention v2 / Memory-Efficient Attention pada backend CUDA
        out = F.scaled_dot_product_attention(
            q, k, v,
            attn_mask=None,
            dropout_p=self.attn_drop if self.training else 0.0,
            is_causal=False
        )

        # Transpose & Flatten: [B, Num_Heads, N, Head_Dim] -> [B, N, C]
        out = out.transpose(1, 2).reshape(B, N, C)
        out = self.proj(out)
        out = self.proj_drop(out)
        return out

class TransformerEncoderBlock(nn.Module):
    """Blok Transformer Encoder dengan arsitektur Pre-LayerNorm."""
    def __init__(self, dim: int, num_heads: int, mlp_ratio: float = 4.0, drop: float = 0.0):
        super().__init__()
        self.norm1 = nn.LayerNorm(dim, eps=1e-6)
        self.attn = FastViTAttention(dim, num_heads=num_heads, proj_drop=drop)
        self.norm2 = nn.LayerNorm(dim, eps=1e-6)
        
        mlp_hidden_dim = int(dim * mlp_ratio)
        self.mlp = nn.Sequential(
            nn.Linear(dim, mlp_hidden_dim),
            nn.GELU(),
            nn.Dropout(drop),
            nn.Linear(mlp_hidden_dim, dim),
            nn.Dropout(drop)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Pre-LN residual path
        x = x + self.attn(self.norm1(x))
        x = x + self.mlp(self.norm2(x))
        return x

class ProductionViT(nn.Module):
    """Vision Transformer lengkap untuk klasifikasi, dioptimalkan untuk ekspor ONNX."""
    def __init__(self, img_size: int = 224, patch_size: int = 16, in_chans: int = 3, 
                 num_classes: int = 1000, embed_dim: int = 768, depth: int = 12, num_heads: int = 12):
        super().__init__()
        self.patch_embed = PatchEmbedding(img_size, patch_size, in_chans, embed_dim)
        num_patches = self.patch_embed.num_patches

        self.cls_token = nn.Parameter(torch.zeros(1, 1, embed_dim))
        self.pos_embed = nn.Parameter(torch.zeros(1, num_patches + 1, embed_dim))
        self.pos_drop = nn.Dropout(p=0.0)

        self.blocks = nn.ModuleList([
            TransformerEncoderBlock(dim=embed_dim, num_heads=num_heads)
            for _ in range(depth)
        ])
        
        self.norm = nn.LayerNorm(embed_dim, eps=1e-6)
        self.head = nn.Linear(embed_dim, num_classes)
        
        # Inisialisasi parameter pos_embed dan cls_token
        nn.init.trunc_normal_(self.pos_embed, std=0.02)
        nn.init.trunc_normal_(self.cls_token, std=0.02)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        B = x.shape[0]
        x = self.patch_embed(x)
        
        # Expand cls_token ke seluruh batch: [B, 1, Embed_Dim]
        cls_tokens = self.cls_token.expand(B, -1, -1)
        x = torch.cat((cls_tokens, x), dim=1)
        x = self.pos_drop(x + self.pos_embed)

        for block in self.blocks:
            x = block(x)

        x = self.norm(x)
        # Ambil representasi latent pada index cls_token [0]
        cls_out = x[:, 0]
        logits = self.head(cls_out)
        return logits

def export_to_onnx(model: nn.Module, file_path: str):
    """Mengekspor arsitektur model ke ONNX Opset 17 dengan dynamic batching."""
    model.eval()
    dummy_input = torch.randn(1, 3, 224, 224, requires_grad=False)
    
    torch.onnx.export(
        model,
        dummy_input,
        file_path,
        export_params=True,
        opset_version=17,
        do_constant_folding=True,
        input_names=["input_images"],
        output_names=["logits"],
        dynamic_axes={
            "input_images": {0: "batch_size"},
            "logits": {0: "batch_size"}
        }
    )
    print(f"[SUCCESS] Model berhasil diekspor ke: {file_path}")

if __name__ == "__main__":
    device = "cuda" if torch.cuda.is_available() else "cpu"
    vit = ProductionViT(depth=4, num_heads=4, embed_dim=256).to(device)
    dummy_tensor = torch.randn(2, 3, 224, 224).to(device)
    
    with torch.inference_mode():
        preds = vit(dummy_tensor)
        print(f"Logits output shape: {preds.shape}")
        
    export_to_onnx(vit.cpu(), "vit_production.onnx")
```

---

### 8. Real World Case Study: E-Commerce Multimodal Visual Search & Semantic Categorization (50,000 Req/s)

#### 8.1 Arsitektur Masalah & Skala
Platform e-commerce marketplace memproses katalog produk global dengan **500 juta SKU**. Setiap query pengguna dapat berupa citra produk (diambil via kamera ponsel) yang digabungkan dengan deskripsi tekstual pendek.
- **SLA Ketat**: Latency end-to-end P99 $\le 25\text{ ms}$.
- **Throughput Peak**: 50,000 permintaan per detik (RPS).
- **Infrastruktur Target**: Multi-node GPU cluster (8x NVIDIA H100 80GB SXM per instance).

#### 8.2 Topologi Arsitektur Solusi
Sistem dirancang sebagai **Multimodal Two-Tower Architecture** yang terdistribusi:
1. **Vision Backbone**: ConvNeXt-Base yang dikompilasi menggunakan NVIDIA TensorRT (FP8 Mixed Precision) untuk mengekstrak embedding visual 512-dim.
2. **Text Backbone**: Modern LLaMA-based Sentence Encoder (dimensi 512) dengan kompilasi TensorRT-LLM.
3. **Cross-Attention Fusion Engine**: Model fusi ringan 2-layer Transformer yang menggabungkan visual dan text embedding.
4. **Vector Search Engine**: Indeks HNSW (Hierarchical Navigable Small World) terdistribusi di memori NVMe-oF via Milvus/Faiss.

```
[ Client Request ] ---> [ Envoy / API Gateway ] (Load Balancer)
                                |
                                v
               [ Triton Inference Server Cluster ]
               (Shared Memory Inter-Process Comm)
                                |
        +-----------------------+-----------------------+
        |                                               |
        v                                               v
 [ Pipeline Step 1 ]                             [ Pipeline Step 2 ]
 Vision Tower (TensorRT)                         Text Tower (TensorRT)
 Input: [B, 3, 224, 224]                         Input: [B, 128] Tokens
 Instance Group: 4 per GPU                       Instance Group: 4 per GPU
 Execution Time: ~3.2ms                          Execution Time: ~2.8ms
        |                                               |
        +-----------------------+-----------------------+
                                |
                                v
                       [ Pipeline Step 3 ]
                 Multimodal Cross-Fusion Layer
                 Fused Embedding: [B, 512]
                 Execution Time: ~0.8ms
                                |
                                v
               [ In-Memory Distributed Vector DB ]
                    Search Query: Top-K (K=100)
                     Search Time: ~8.0ms
                                |
                                v
                [ Response Aggregator: Total ~18ms ]
```

#### 8.3 Konfigurasi Triton Inference Server (`config.pbtxt`)
Konfigurasi optimasi performa tinggi untuk Vision Tower di Triton:

```protobuf
name: "vision_tower_tensorrt"
platform: "tensorrt_plan"
max_batch_size: 64

input [
  {
    name: "input_images"
    data_type: TYPE_FP32
    dims: [ 3, 224, 224 ]
  }
]

output [
  {
    name: "visual_embeddings"
    data_type: TYPE_FP16
    dims: [ 512 ]
  }
]

# Optimasi Dynamic Batching untuk meminimalkan queue latency
dynamic_batching {
  max_queue_delay_microseconds: 2000 # 2ms windowing toleration
  preferred_batch_size: [ 8, 16, 32, 64 ]
}

# Alokasi Concurrency: 2 engine instance per physical GPU core
instance_group [
  {
    count: 2
    kind: KIND_GPU
    gpus: [ 0, 1, 2, 3, 4, 5, 6, 7 ]
  }
]

# Aktifkan CUDA Graphs untuk meniadakan kernel launch overhead
model_transaction_policy {
  decoupled: false
}
```

---

### 9. Trade-offs: Architectural & Deployment Decisions

| Keputusan Desain | Keuntungan (Pros) | Biaya / Konsekuensi (Cons) | Metrik Ambang Batas Evaluasi |
| :--- | :--- | :--- | :--- |
| **ViT vs ConvNeXt** | ViT unggul pada pretraining data masif (>100M gambar); global context modeling. | ViT membutuhkan representasi $O(N^2)$ memory jika tanpa FlashAttention; konvolusi jauh lebih cepat pada resolusi gambar sangat tinggi. | Gunakan ConvNeXt jika input resolution $> 1024 \times 1024$; gunakan ViT jika multimodal alignment (CLIP style) diutamakan. |
| **Post-Training Quantization (INT8) vs Native FP16** | Throughput naik $2.2\times$ hingga $3.1\times$; VRAM footprint berkurang 50%. | Memerlukan data kalibrasi representatif; risiko degradasi akurasi signifikan pada outlier aktivasi attention. | Toleransi penurunan metric akurasi (misal Top-1 Acc $\Delta < 0.5\%$). |
| **Static vs Dynamic Graph (TorchScript / TensorRT)** | Static shape menghasilkan optimasi layout memori maksimal, kernel fusion, dan zero GPU sync. | Mengharuskan padding input teks/gambar ke panjang statis, menghasilkan FLOP terbuang (*wasteful compute*). | Gunakan static shape jika variasi sequence length rendah ($< 15\%$ variance). Jika varians sequence tinggi, gunakan dynamic batching dengan binning. |
| **Decoder-Only vs Encoder-Decoder untuk NLP Task** | Unifikasi arsitektur: satu base LLM dapat melayani classification, extraction, dan generation. | Boros compute untuk murni task klasifikasi; komputasi bidirectional encoder $2\times$ lebih murah secara FLOPs dibanding causal generative forward pass. | Jika QPS $> 10{,}000$ murni sequence classification (sentiment/tagging), pertahankan Encoder-Only (DeBERTa-v3). |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Silent Degradation: Naive Softmax Underflow/Overflow
- **Gejala**: Loss bernilai `NaN` saat training arsitektur transformer custom berdimensi besar dengan FP16.
- **Penyebab**: Mengalikan matriks $Q$ dan $K^T$ tanpa penskalaan $\frac{1}{\sqrt{d_k}}$. Nilai dot-product menjadi sangat besar, mendorong softmax ke saturasi maksimum di mana gradien menjadi 0, atau menghasilkan eksponen melebihi batas representasi FP16 ($> 65{,}504$).
- **Solusi**: Pastikan scaling diaplikasikan sebelum causal masking dan penambahan attention bias:

```python
# SALAH
scores = torch.matmul(q, k.transpose(-2, -1))
attn = torch.softmax(scores, dim=-1) # Overflow pada FP16

# BENAR
scale = 1.0 / math.sqrt(q.size(-1))
scores = torch.matmul(q, k.transpose(-2, -1)) * scale
attn = torch.softmax(scores, dim=-1)
```

#### 10.2 Latency Degradation: CUDA Host-Device Synchronization Bottlenecks
- **Gejala**: Profiler menunjukkan GPU utilization berfluktuasi tajam (roller-coaster curve 10% - 95%) dan P99 latency melonjak drastis.
- **Penyebab**: Kode memanggil pemanggilan tensor sinkron di dalam inference loop, seperti `.item()`, `.cpu()`, atau `print(tensor)` yang memaksa CPU menunggu (GPU Pipeline Stall) hingga seluruh command queue CUDA dieksekusi.
- **Troubleshooting Checklist**:
  1. Hapus semua `.item()` atau `.cpu()` di hot path inference pipeline.
  2. Gunakan pinned memory untuk tensor transfer: `tensor.pin_memory().to(device, non_blocking=True)`.
  3. Aktifkan asynchronous profiling menggunakan `torch.cuda.Event(enable_timing=True)`.

#### 10.3 Dynamic Shapes Memory Allocator Thrashing pada TensorRT
- **Gejala**: TensorRT engine sering mengalami delay alokasi memori (*allocation latency jitter*) pada request batch size variabel.
- **Penyebab**: Profil optimasi profile range TensorRT didefinisikan terlalu lebar (`min: 1, opt: 16, max: 128`), menyebabkan TensorRT harus sering mengalokasikan ulang buffer scratchpad GPU internal.
- **Solusi**: Tentukan profil optimasi yang tersegmentasi (misal Engine Profile 1: batch 1-8; Engine Profile 2: batch 9-32) dan implementasikan request binning di sisi Triton Inference Server.

---

### 11. Best Practices (Production Checklist)

#### Pre-Deployment Architecture Verification
- [ ] Layer Normalization / RMSNorm selalu dioperasikan dalam FP32 atau BF16 untuk menjaga stabilitas numerik; hindari pure FP16 pada normalisasi tanpa AMP master weights.
- [ ] Residual connection diverifikasi zero-initialized atau di-scale dengan faktor $\frac{1}{\sqrt{2L}}$ untuk menstabilkan gradien pada arsitektur yang sangat dalam (>24 layer).
- [ ] Tidak ada dependensi layer custom C++ tanpa implementasi fallback operator ONNX Opset 17+.

#### Optimization & Compilation
- [ ] Jalankan kalibrasi kueri INT8/FP8 menggunakan algoritma KL-Divergence / Entropi minimal pada 1,000 data sampel representatif produksi.
- [ ] Pastikan model lolos uji validasi numerik ekivalensi output antara PyTorch eager execution dan TensorRT engine:
  $$\max |Y_{\text{pytorch}} - Y_{\text{tensorrt}}| < 1\text{e-}3 \quad (\text{untuk FP16}).$$
- [ ] Eksekusi pemetaan CUDA Graph warmup minimal 3 run sebelum membuka traffic jaringan guna mencegah cold-start latency spike.

#### Infrastructure & Runtime Monitoring
- [ ] Triton dynamic batching queue timeout dibatasi maksimal 20% dari SLA latency total.
- [ ] GPU Memory Reserve dialokasikan eksplisit melalui `cudaSetDeviceFlags` atau environment variable Triton `--gpu-memory-fraction=0.85` untuk mencegah driver-level out-of-memory crash.
- [ ] Pasang metrik observability Prometheus: `nv_inference_request_duration_us`, `nv_inference_compute_infer_duration_us`, `nv_gpu_memory_used_bytes`.

---

### 12. Hands-on Practice

Buat struktur repositori praktikum pada direktori `hands-on/m02/`:

```bash
mkdir -p hands-on/m02/{src,configs,scripts}
cd hands-on/m02
```

#### Langkah 1: Buat Skrip Eksport & Optimasi Engine (`src/compile_engine.py`)
Skrip ini mengonversi model Vision Transformer PyTorch menjadi engine teroptimasi ONNX dan TensorRT.

```python
# hands-on/m02/src/compile_engine.py
import os
import torch
import torch.nn as nn
from torchvision.models import convnext_tiny, ConvNeXt_Tiny_Weights

def prepare_and_export():
    print("[1/3] Mengunduh model baseline ConvNeXt-Tiny...")
    weights = ConvNeXt_Tiny_Weights.DEFAULT
    model = convnext_tiny(weights=weights)
    model.eval()

    dummy_input = torch.randn(1, 3, 224, 224, dtype=torch.float32)
    onnx_output = "configs/convnext_tiny.onnx"
    os.makedirs("configs", exist_ok=True)

    print(f"[2/3] Mengekspor ke ONNX format di: {onnx_output}...")
    torch.onnx.export(
        model,
        dummy_input,
        onnx_output,
        export_params=True,
        opset_version=17,
        do_constant_folding=True,
        input_names=["input"],
        output_names=["output"],
        dynamic_axes={"input": {0: "batch_size"}, "output": {0: "batch_size"}}
    )
    print("[3/3] ONNX graph tersimpan dan siap diproses compiler TensorRT.")

if __name__ == "__main__":
    prepare_and_export()
```

#### Langkah 2: Buat Skrip Validasi Numerik (`src/validate_inference.py`)
Skrip untuk memvalidasi deviasi numerik antara model asli PyTorch dan ONNX Runtime.

```python
# hands-on/m02/src/validate_inference.py
import numpy as np
import onnxruntime as ort
import torch
from torchvision.models import convnext_tiny, ConvNeXt_Tiny_Weights

def validate_parity():
    # 1. Setup PyTorch Engine
    weights = ConvNeXt_Tiny_Weights.DEFAULT
    torch_model = convnext_tiny(weights=weights).eval()
    
    # 2. Setup ONNXRuntime Engine
    session = ort.InferenceSession("configs/convnext_tiny.onnx", providers=["CPUExecutionProvider"])
    
    # 3. Generate deterministic input
    np.random.seed(42)
    input_data = np.random.randn(2, 3, 224, 224).astype(np.float32)
    
    # PyTorch Inference
    with torch.no_grad():
        torch_out = torch_model(torch.from_numpy(input_data)).numpy()
        
    # ONNX Inference
    onnx_inputs = {session.get_inputs()[0].name: input_data}
    onnx_out = session.run(None, onnx_inputs)[0]
    
    # Compute Tolerance Error
    abs_diff = np.abs(torch_out - onnx_out)
    max_diff = np.max(abs_diff)
    mean_diff = np.mean(abs_diff)
    
    print(f"--- LAPORAN INTEGRITAS NUMERIK ---")
    print(f"Max Absolute Error : {max_diff:.6e}")
    print(f"Mean Absolute Error: {mean_diff:.6e}")
    
    assert max_diff < 1e-4, f"Validasi gagal! Deviasi {max_diff} melampaui toleransi 1e-4"
    print("[STATUS]: Validasi Lolos. Model ONNX identik secara fungsional.")

if __name__ == "__main__":
    validate_parity()
```

#### Langkah 3: Eksekusi Pipeline Praktikum
Jalankan instruksi berikut di terminal:

```bash
# Setup dependency
pip install torch torchvision onnx onnxruntime --upgrade

# Jalankan ekspor
python src/compile_engine.py

# Jalankan validasi parity
python src/validate_inference.py
```

---

### 13. Exercise

#### Level Easy
Tuliskan sebuah custom PyTorch module bernama `RMSNorm` (Root Mean Square Normalization) yang mengeliminasi komputasi mean dari standard LayerNorm:

$$\text{RMSNorm}(x) = \frac{x}{\sqrt{\frac{1}{d}\sum_{i=1}^d x_i^2 + \epsilon}} \odot \gamma$$

Pastikan implementasi mendukung scaling weight parameter $\gamma$ yang trainable dan berikan unit test untuk memvalidasi shape output tensor invariant terhadap shape input tensor.

#### Level Medium
Buat sebuah script optimasi PyTorch yang menerima model NLP HuggingFace Decoder-Only (misal: `gpt2` atau model causal kecil sejenis). Lakukan langkah-langkah berikut:
1. Ganti implementasi attention layer standarnya dengan `torch.nn.functional.scaled_dot_product_attention`.
2. Aktifkan dynamic FP16 AMP context inference.
3. Ukur dan cetak perbandingan profil: Peak GPU Memory Allocation (MB) dan Execution Time Latency (ms) untuk sequence length bertingkat: 256, 512, 1024, dan 2048 token.

#### Level Hard
Rancang modul hybrid vision encoder PyTorch dari scratch yang menggabungkan:
1. Stage 1 & Stage 2: Menggunakan blok konvolusi bergaya ConvNeXt dengan $7 \times 7$ depthwise convolution untuk menangani feature maps beresolusi tinggi secara efisien.
2. Downsampling Transition Layer: Menggunakan convolution $2 \times 2$ stride 2 yang menaikkan channel size sebesar $2\times$.
3. Stage 3 & Stage 4: Menggunakan Vision Transformer block murni dengan FlashAttention dan RoPE 2D spatial embeddings.
4. Model harus dapat ditrace secara simbolik via `torch.jit.trace` tanpa runtime tracing warning.

---

### 14. Challenge
Sebuah bank multinasional meluncurkan sistem fraud detection multimodal real-time. Sistem harus memproses transaksi yang berisi:
1. Gambar struk pembayaran (resolusi bervariasi antara $720\text{p}$ hingga $4\text{K}$).
2. Catatan metadata transaksi finansial tabular (128 fitur kontinu & kategorikal).
3. Transkrip percakapan suara pelanggan dengan kasir (teks string 50 - 500 token).

**Objektif Arsitektur**:
- Desain arsitektur end-to-end multimodal yang mengintegrasikan ketiga representasi modalitas tersebut ke dalam satu inferensi terpadu.
- Tetapkan batasan bahwa seluruh inference pipeline harus berjalan di cluster GPU dengan budget komputasi maksimal 1 unit NVIDIA L4 GPU per instance server.
- SLA: P99 Latency $\le 30\text{ ms}$ pada throughput $1{,}500\text{ RPS}$.
- **Tantangan Rekayasa**:
  1. Bagaimana mengatasi resolusi gambar struk yang heterogen tanpa memicu memory re-allocation spike di GPU?
  2. Bagaimana merancang mekanisme cross-attention antar 3 modalitas dengan dynamic sequence length tanpa menghasilkan $O(N^2)$ memory explosion?
  3. Susun failure recovery blueprint jika pipeline deteksi teks mengalami lag/timeout tanpa menggagalkan flow validasi struk dan metadata.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Konseptual & Fundamental)
1. Apa alasan komputasi matriks self-attention standar $QK^T$ dikategorikan sebagai operasi *memory-bound* bukan *compute-bound* pada sequence length panjang?
2. Mengapa Vision Transformer (ViT) standar membutuhkan dataset pretraining jauh lebih besar (misal JFT-300M atau ImageNet-22k) dibanding ResNet konvensional untuk mencapai akurasi serupa?
3. Pada arsitektur transformer modern, mengapa Layer Normalization lebih sering diposisikan sebagai *Pre-LN* (sebelum multi-head attention/MLP block) dibandingkan *Post-LN* (setelah residual addition)?
4. Apa fungsi dari parameter pembagi $\sqrt{d_k}$ pada formulasi Scaled Dot-Product Attention?
5. Jelaskan perbedaan mendasar representasi komputasi antara standard Conv2D ($C_{\text{in}} \times C_{\text{out}} \times K \times K$) dengan Depthwise Separable Convolution!

#### Bagian 2: Intermediate (Arsitektur & Optimasi)
6. Bagaimana algoritma FlashAttention menghindari pembebanan memori $O(S^2)$ ke GPU High Bandwidth Memory (HBM) tanpa mengubah hasil kalkulasi matematis softmax?
7. Mengapa penambahan absolut positional embedding $x + p$ tidak memiliki sifat ekstrapolasi sequence length yang baik jika dibandingkan dengan Rotary Position Embedding (RoPE)?
8. Di dalam pipeline kompilasi TensorRT, jelaskan fenomena *Kernel Fusion* dan berikan contoh konkret fusi 3 layer yang umum dilakukan!
9. Apa perbedaan esensial mekanisme sinkronisasi data antara eksekusi standard PyTorch eager execution dengan kompilasi model berbasis CUDA Graphs?
10. Ketika melakukan kuantisasi model dari FP16 ke INT8, mengapa kalibrasi berbasis KL-Divergence sering dipilih untuk menentukan threshold clipping tensor aktivasi?

#### Bagian 3: Skenario Kasus Produksi
11. **Skenario A**: Tim engineer Anda baru saja merilis model ViT hasil kompilasi TensorRT ke server produksi. Pada uji beban (load test) dengan single request, latency stabil di angka 5ms. Namun ketika traffic naik menjadi 2,000 RPS dengan Triton Dynamic Batching aktif, latency melesat ke 80ms dan utilitas GPU hanya mentok di 45%. Apa akar masalah teknis arsitekturnya dan bagaimana mengatasinya?
12. **Skenario B**: Selama proses training distributed LLM Decoder-only 7B parameter menggunakan FP16 Automatic Mixed Precision (AMP), training loss mendadak menunjukkan anomali NaN tepat setelah sequence length dinaikkan dari 2,048 ke 8,192 token. Analisis kemungkinan penyebab failure point dan berikan strategi perbaikan konkret!
13. **Skenario C**: Anda memiliki microservice multimodal yang menggabungkan Vision Backbone dan Text Backbone. Vision Backbone mengonsumsi waktu komputasi 18ms, sementara Text Backbone mengonsumsi waktu 6ms. Kedua model berada di GPU yang sama di dalam Triton Inference Server. Bagaimana strategi deployment pipeline di Triton untuk memastikan throughput inference keseluruhan termaksimalkan tanpa membuat Text Backbone mengalami starved resources?

---

### Jawaban Kunci Quiz Evaluasi

#### Bagian 1: Basic
1. Karena rasio transfer data dari/ke VRAM (HBM) jauh lebih besar dibandingkan komputasi aritmatika floating point yang dilakukan per byte data (Arithmetic Intensity rendah). Sebagian besar waktu clock GPU dihabiskan untuk membaca dan menulis intermediate tensor $S \times S$ bukan melakukan kalkulasi FLOPS pada Tensor Core.
2. ViT tidak memiliki *hard inductive biases* intrinsik berupa translation invariance (pergeseran objek tidak mengubah esensi fitur) dan spatial locality (piksel terdekat saling berhubungan erat) seperti yang dimiliki secara default oleh layer konvolusi. Akibatnya, ViT harus mempelajari relasi spasial tersebut dari scratch menggunakan volume data masif.
3. *Pre-LN* mempertahankan gradient highway yang tidak terhalangi (*unimpeded*) sepanjang residual path langsung dari layer terakhir ke layer pertama, sehingga mencegah vanishing/exploding gradient pada model yang dalam tanpa membutuhkan warm-up learning rate yang agresif seperti pada *Post-LN*.
4. Mencegah nilai dot product tumbuh proporsional secara magnitudo seiring membesarnya dimensi vector $d_k$, yang dapat mendorong fungsi aktivasi Softmax masuk ke wilayah gradien vanishing yang ekstrem (daerah datar fungsi logistik).
5. Standard Conv2D memproses spatial filtering dan channel correlation secara bersamaan dalam satu kernel densitas tinggi. Sebaliknya, Depthwise Separable Convolution memecahnya menjadi dua operasi terpisah: Depthwise Conv (1 filter spatial per 1 kanal input) lalu dilanjutkan Pointwise Conv ($1 \times 1$ conv untuk memproyeksikan kanal), menghemat komputasi dan parameter hingga $\approx \frac{1}{K^2} \times$.

#### Bagian 2: Intermediate
6. FlashAttention memanfaatkan SRAM GPU yang berkecepatan tinggi dengan membagi tensor matriks input ke dalam blok-blok (tiling). FlashAttention mengimplementasikan varian *online softmax formulation* yang memperbarui nilai rescale softmax max dan normalizer sum secara incremental, sehingga matriks perhatian penuh $S \times S$ tidak pernah dialokasikan atau disimpan ke HBM.
7. Absolute positional embedding menjumlahkan vektor representasi tetap pada koordinat tertentu, sehingga model kesulitan merepresentasikan hubungan spasial atau temporal pada posisi token yang belum pernah dilihat selama proses training. Sebaliknya, RoPE merotasi vektor Query dan Key secara proporsional terhadap jarak sudut relatif $(m - n)$, menjaga invariansi jarak relatif secara deterministik berapapun panjang sequence.
8. *Kernel Fusion* menggabungkan beberapa operator berurutan menjadi satu GPU kernel terpadu untuk menghilangkan latency memory read/write antar register HBM. Contoh konkret: Penggabungan operasi `Convolution + Bias Addition + ReLU/GELU Activation` menjadi satu eksekusi fused kernel tunggal.
9. PyTorch eager execution meluncurkan instruksi kernel secara berulang satu demi satu dari CPU ke antrean GPU driver melalui PCIe bus, menghasilkan overhead driver CPU yang signifikan. CUDA Graph merekam seluruh workflow directed acyclic graph (DAG) operasi kernel GPU satu kali secara statis, lalu menjalankannya kembali secara berulang via single driver launch call, meniadakan CPU launch overhead.
10. Aktivasi neural network sering kali memiliki distribusi Gaussian atau Laplacian dengan ekor panjang (*long-tail distribution*) yang mengandung outliers. Memetakan nilai min/max absolut secara linier akan mengorbankan resolusi representasi numerik pada mayoritas rentang data. Kalibrasi KL-Divergence mencari ambang batas pemotongan (*clipping threshold*) yang meminimalkan hilangnya informasi relatif antara probabilitas distribusi FP32 asli dan distribusi INT8 yang terkuantisasi.

#### Bagian 3: Skenario Kasus Produksi
11. **Analisis Akar Masalah**: Triton dynamic batching diset dengan parameter queue delay (`max_queue_delay_microseconds`) yang terlalu longgar, atau GPU SMs (Streaming Multiprocessors) terkunci pada thread queuing overhead CPU karena dynamic shape memory reallocation. Akibatnya, batch menumpuk di antrean sementara GPU berulang kali stall menunggu pembentukan batch optimal.
    **Solusi**: Kurangi nilai `max_queue_delay_microseconds` ke angka yang realistis (misal 1-2ms), tentukan preferred batch size yang diskrit (misal 4, 8, 16), kunci memory allocation pool via CUDA Graphs, dan naikkan jumlah instance runtime model pada GPU tersebut (`instance_group [ { count: 2, kind: KIND_GPU } ]`).
12. **Analisis Akar Masalah**: Peningkatan sequence length menjadi 8,192 memperbesar akumulasi nilai pada causal attention logits. Jika modul layer normalization masih menggunakan half-precision FP16, atau penskalaan denominator $\sqrt{d_k}$ mengalami pembulatan truncation presisi rendah, varians aktivasi meledak melampaui rentang representasi FP16 (max 65,504), memicu floating point overflow yang menghasilkan `Inf`, yang kemudian berubah menjadi `NaN` saat melewati operasi Softmax.
    **Solusi**: Terapkan *Mixed Precision Hygiene*: pastikan akumulasi Softmax dan evaluasi Normalization Layer dipaksa berjalan pada level presisi FP32 (atau ganti baseline numerik dengan BF16 yang memiliki dynamic range setara FP32), serta implementasikan Query-Key Normalization (QK-Norm) sebelum operasi SDPA.
13. **Solusi Deployment**:
    1. Konfigurasikan model pipeline menggunakan fitur **Triton Ensemble Architecture** atau **Business Logic Scripting (BLS)** dengan IPC Shared Memory agar tidak terjadi transfer data antar model melalui CPU RAM.
    2. Pisahkan *Instance Group* execution: Berikan Vision Backbone alokasi GPU instance lebih sedikit namun prioritaskan dynamic batching concurrency untuk memproses frame paralel, sementara Text Backbone dikonfigurasi dengan thread priority berbeda atau dipetakan pada CUDA Streams terpisah via flag execution priority Triton.
    3. Terapkan TensorRT dynamic engine profile terpisah pada Vision Model agar alokasi VRAM static block-nya tidak memicu preemption interrupt terhadap thread engine Text Model yang berjalan lebih cepat (6ms vs 18ms).

---

### 16. Summary
Modul ini telah mengupas tuntas arsitektur specialized deep learning CV dan NLP tingkat enterprise:
1. **Transisi Arsitektural**: Pergeseran Computer Vision dari purely local convolutions ke Vision Transformer (ViT) dan adaptasi modernnya pada ConvNeXt; serta konvergensi pemodelan NLP menuju arsitektur Decoder-Only teroptimasi (RoPE, FlashAttention).
2. **Eliminasi Memory Bottleneck**: Mengidentifikasi arsitektur komputasi modern yang memory-bound dan menuntaskannya lewat *IO-aware tiling* (FlashAttention), RMSNorm, dan kernel fusion.
3. **Produksi Tanpa Kompromi**: Tahapan sistematis mulai dari penulisan custom layer PyTorch 2.x, tracing ONNX, kompilasi TensorRT (FP16/INT8), hingga deployment skala masif dengan Triton Inference Server yang memenuhi SLA latensi rendah dan throughput tinggi.