# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 07: Computer Vision & Multimodal Intelligence**  
**Track: AI & Data Scientist (08-AI-Data-and-Autonomous-Agents)**

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta diharapkan mampu:

1. **Menganalisis dan Mengimplementasikan Arsitektur Vision Transformer (ViT) & Swin Transformer Tingkat Rendah:** Memahami dekonstruksi citra menjadi *patch embeddings*, formulasi *spatial self-attention*, *shifted window attention mechanisms*, serta mengatasi hilangnya *inductive bias* translasi.
2. **Merancang Sistem Multimodal Joint Representation:** Menguasai formulasi matematis *Symmetric InfoNCE Loss* pada arsitektur *Contrastive Language-Image Pre-training* (CLIP) dan *cross-attention conditioning* pada Vision-Language Models (VLM).
3. **Membangun Pipeline Inferensi Produksi Ultra-Low Latency:** Mengonversi model multimodal ke format teroptimasi (ONNX / TensorRT), mengonfigurasi *dynamic batching* dan *concurrent model execution* di Triton Inference Server.
4. **Mengimplementasikan GPU-Accelerated Preprocessing:** Mengeliminasi *bottleneck* I/O pada CPU menggunakan NVIDIA DALI (*Data Loading and Augmentation Library*) dan NVDEC untuk dekode citra/video langsung ke VRAM.
5. **Mengaudit Trade-off Performa, Biaya, dan Akurasi:** Melakukan kuantisasi INT8/FP8 post-training (PTQ) dan Quantization-Aware Training (QAT) dengan mempertahankan ambang batas degradasi mAP/Zero-Shot Top-1 `< 1.5%`.

---

## 2. Prerequisites

Peserta wajib menguasai:
* **Deep Learning Fundasional:** Backpropagation, konvolusi 2D, varian Attention Mechanism (Scaled Dot-Product, Multi-Head Attention).
* **Framework:** PyTorch (tingkat lanjut: custom `nn.Module`, hooks, TorchScript).
* **Sistem & Hardware:** Pengetahuan arsitektur GPU (CUDA Cores, Tensor Cores, Shared Memory vs HBM), dasar containerization (Docker, NVIDIA Container Toolkit).
* **Matematika:** Aljabar linear lanjut (SVD, Proyeksi Ortogonal), Kalkulus Multivariat, dan Teori Informasi (Kullback-Leibler Divergence, Mutual Information).

---

## 3. Concept & Internal Architecture

### 3.1 Transisi Paradigma: Dari Inductive Bias CNN ke Isotropic Vision Transformers

Arsitektur Convolutional Neural Networks (CNN) bergantung pada dua *inductive bias* fundamental:
1. **Translation Invariance:** $f(g(x)) = g(f(x))$, di mana translasi spasial pada input menghasilkan translasi identik pada feature map.
2. **Locality:** Korelasi piksel tertinggi terkonsentrasi pada *neighborhood* terdekat (kernel $3\times3$ atau $5\times5$).

Vision Transformer (ViT) menghapus kedua asumsi ini. ViT memperlakukan citra sebagai sekuens token 1D layaknya pemrosesan teks pada NLP:

$$\mathbf{x} \in \mathbb{R}^{H \times W \times C} \implies \mathbf{x}_p \in \mathbb{R}^{N \times (P^2 \cdot C)}$$

Di mana:
* $(H, W)$ adalah resolusi citra asli, $C$ adalah jumlah kanal.
* $P$ adalah resolusi patch spasial (misal $16 \times 16$).
* $N = \frac{HW}{P^2}$ adalah panjang sekuens token yang dihasilkan.

Token-token ini diproyeksikan secara linear ke dimensi laten $D$ menggunakan matriks terpelajari $\mathbf{E} \in \mathbb{R}^{(P^2 \cdot C) \times D}$, ditambahkan token khusus $[CLS]$, serta *1D learnable position embeddings* $\mathbf{E}_{pos} \in \mathbb{R}^{(N+1) \times D}$:

$$\mathbf{z}_0 = [\mathbf{x}_{class}; \, \mathbf{x}_p^1\mathbf{E}; \, \mathbf{x}_p^2\mathbf{E}; \dots; \, \mathbf{x}_p^N\mathbf{E}] + \mathbf{E}_{pos}$$

$$\mathbf{z}'_\ell = \text{MSA}(\text{LN}(\mathbf{z}_{\ell-1})) + \mathbf{z}_{\ell-1}, \quad \ell = 1 \dots L$$

$$\mathbf{z}_\ell = \text{MLP}(\text{LN}(\mathbf{z}'_\ell)) + \mathbf{z}'_\ell, \quad \ell = 1 \dots L$$

```
Input Image (H x W x C)
       │
       ▼
 [Patch Extraction] ──> Reshape ke N patches berukuran (P x P x C)
       │
       ▼
 [Linear Projection] ──> Matriks Bobot E (Kernel P x P, Stride P)
       │
       ▼
 [Concat Token CLS] ──> [CLS, Patch_1, Patch_2, ..., Patch_N]
       │
       ▼
[Add Position Emb.] ──> Ditambahkan E_pos secara element-wise
       │
       ▼
┌────────────────────────────────────────────────────────┐
│ Transformer Encoder Block (x L)                        │
│   ┌──────────────────────────────────────────────────┐ │
│   │ Layer Norm ──> Multi-Head Self-Attention (MSA)  │ │
│   │     │                                            │ │
│   │     └─── Residual Connection (+) ────────────────┤ │
│   └──────────────────────────────────────────────────┘ │
│   ┌──────────────────────────────────────────────────┐ │
│   │ Layer Norm ──> Multi-Layer Perceptron (MLP/GELU) │ │
│   │     │                                            │ │
│   │     └─── Residual Connection (+) ────────────────┤ │
│   └──────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────┘
       │
       ▼
 Output Head (Representasi Vektor Global dari Token CLS)
```

### 3.2 Shifted Window Attention (Swin Transformer)

Kompleksitas komputasi standar Self-Attention pada ViT adalah kuadratik terhadap resolusi citra: $\mathcal{O}(N^2) = \mathcal{O}\left(\left(\frac{HW}{P^2}\right)^2\right)$. Untuk citra beresolusi tinggi, komputasi ini menyebabkan *memory explosion* pada VRAM GPU.

Swin Transformer mengatasinya dengan membatasi *Self-Attention* di dalam jendela lokal berukuran $M \times M$ patch (umumnya $M=7$), menghasilkan kompleksitas linier: $\mathcal{O}\left(4HWM^2\right)$. 

Untuk memfasilitasi komunikasi lintas jendela tanpa menambah kompleksitas, Swin memperkenalkan **Shifted Window Partitioning**:

* **Layer $\ell$ (Regular Windowing):** Jendela dibagi rata dari koordinat $(0,0)$. Komputasi *Self-Attention* dilakukan independen di dalam tiap jendela.
* **Layer $\ell+1$ (Shifted Windowing):** Jendela digeser sejauh $(\lfloor \frac{M}{2} \rfloor, \lfloor \frac{M}{2} \rfloor)$ patch dari sudut kiri-atas. Partisi baru ini melintasi batas-batas jendela pada layer $\ell$.
* **Efficient Batch Computation via Cyclic Shift:** Penggeseran jendela menghasilkan sub-jendela dengan ukuran berbeda di sudut-sudut citra. Swin melakukan *cyclic shift* ke arah kiri-atas dan menerapkan *masked attention* agar token yang tidak berdekatan secara spasial tidak saling berinteraksi secara keliru.

```
Layer l (Regular Window)              Layer l+1 (Shifted Window)
┌───────────┬───────────┐             ┌─────┬───────────┬─────┐
│           │           │             │  A  │     B     │  C  │
│  Window 1 │  Window 2 │             ├─────┼───────────┼─────┤
│           │           │             │     │           │     │
├───────────┼───────────┤    Shift    │  D  │  Window'  │  E  │
│           │           │   (M/2,M/2) │     │           │     │
│  Window 3 │  Window 4 │  ────────>  ├─────┼───────────┼─────┤
│           │           │             │  F  │     G     │  H  │
└───────────┴───────────┘             └─────┴───────────┴─────┘
                                                 │
                                                 ▼
                                        [Cyclic Shift & Mask]
                                      Satukan region parsial ke
                                      ukuran reguler MxM via masking
```

### 3.3 Contrastive Vision-Language Pre-training (CLIP)

CLIP memetakan modalitas teks dan citra ke dalam satu ruang representasi vektor bersama (*shared latent embedding space* $\mathbb{R}^D$).

Diberikan batch berukuran $B$ yang terdiri dari pasangan citra-teks $(I_i, T_i)$ untuk $i \in \{1, \dots, B\}$:
1. Citra di-encode: $\mathbf{v}_i = \text{ImageEncoder}(I_i) \in \mathbb{R}^{d_v}$, diproyeksikan: $\tilde{\mathbf{v}}_i = \frac{\mathbf{v}_i \mathbf{W}_v}{\|\mathbf{v}_i \mathbf{W}_v\|_2} \in \mathbb{R}^D$.
2. Teks di-encode: $\mathbf{u}_i = \text{TextEncoder}(T_i) \in \mathbb{R}^{d_t}$, diproyeksikan: $\tilde{\mathbf{u}}_i = \frac{\mathbf{u}_i \mathbf{W}_t}{\|\mathbf{u}_i \mathbf{W}_t\|_2} \in \mathbb{R}^D$.
3. Matriks *cosine similarity* dihitung: $\mathbf{S}_{i,j} = \tilde{\mathbf{v}}_i \cdot \tilde{\mathbf{u}}_j$.

Optimasi menggunakan **Symmetric InfoNCE Loss** dengan parameter temperatur terpelajari $\tau$:

$$\mathcal{L}_{I \to T} = -\frac{1}{B} \sum_{i=1}^B \log \frac{\exp(\mathbf{S}_{i,i} / \tau)}{\sum_{j=1}^B \exp(\mathbf{S}_{i,j} / \tau)}$$

$$\mathcal{L}_{T \to I} = -\frac{1}{B} \sum_{i=1}^B \log \frac{\exp(\mathbf{S}_{i,i} / \tau)}{\sum_{j=1}^B \exp(\mathbf{S}_{j,i} / \tau)}$$

$$\mathcal{L}_{total} = \frac{\mathcal{L}_{I \to T} + \mathcal{L}_{T \to I}}{2}$$

```
                Image Encoder (ViT / ResNet)
                          │
                   v_i in R^{d_v}
                          │
                 [Projection W_v + Norm]
                          │
                          ▼
           Image Embeddings: v~_1, v~_2, ..., v~_B
                          │
                          ▼
        ┌───────────────────────────────────┐
        │  Cosine Similarity Matrix (S_ij)   │ <─── Text Embeddings: u~_1, ..., u~_B
        │  Scaled by Learnable Temp (1 / tau)│                    ▲
        ├───────────────────────────────────┤                    │
        │ [ v~_1 . u~_1 ]  v~_1 . u~_2 ...  │         [Projection W_t + Norm]
        │   v~_2 . u~_1  [ v~_2 . u~_2 ]... │                    │
        │      ...            ...           │              u_j in R^{d_t}
        │   v~_B . u~_1    v~_B . u~_2 ...  │                    │
        └───────────────────────────────────┘          Text Encoder (Transformer)
              │                       │
              ▼                       ▼
    Cross-Entropy Rows      Cross-Entropy Cols
      (Image-to-Text)         (Text-to-Image)
              └───────────┬───────────┘
                          ▼
                 Total Symmetric Loss
```

---

## 4. Why & What

### Mengapa beralih dari CNN tradisional ke Vision Transformers dan Multimodal Foundation Models?

* **Kapasitas Skalabilitas Data:** CNN mengalami saturasi performa lebih cepat ketika dilatih dengan ratusan juta data (e.g., JFT-300M). ViT tidak memiliki batasan lokalitas struktural, memungkinkannya mempelajari dependensi spasial global dan relasi semantik kompleks secara bebas jika diberikan data skala masif.
* **Generalisasi Zero-Shot:** Model klasifikasi tertutup (seperti ResNet pada ImageNet-1k) hanya dapat mengklasifikasikan kelas yang telah ditentukan sebelumnya. Arsitektur multimodal seperti CLIP memungkinkan klasifikasi kelas tak terbatas (*open-vocabulary*) secara dinamis hanya melalui prompt teks tanpa fine-tuning berulang.
* **Unifikasi Arsitektur Sistem AI:** Menggunakan arsitektur Transformer terpadu di seluruh modalitas (teks, visi, audio) menyederhanakan infrastruktur akselerasi hardware (*kernel fusion*, *tensor parallelism*, *KV-caching engine*).

---

## 5. How: Production End-to-End Workflow

Arsitektur produksi multimodal skala enterprise membutuhkan orkestrasi pipeline streaming real-time yang memisahkan beban kerja I/O intensif dari tensor computation engine:

```
[Camera Streams / Video Sources (RTSP)]
                  │
                  ▼
 [Hardware Video Decoder (NVIDIA NVDEC)] ──> YUV420 ke RGB Frame langsung di VRAM
                  │
                  ▼
 [Preprocessing Engine (NVIDIA DALI)] ────> Resize, Normalize, FP16 Cast di GPU
                  │
                  ▼
 [Triton Inference Server Dynamic Batcher]
                  │
                  ├── Model Instance 1 (TensorRT Engine: ViT / Swin)
                  └── Model Instance 2 (TensorRT Engine: Text Projection)
                  │
                  ▼
 [Latent Embeddings: v~ \in R^512]
                  │
                  ├──> [Real-time Vector Search Engine (Milvus / Qdrant HNSW Index)]
                  └──> [Downstream LLM / VLM Reasoning Head (e.g., LLaVA/Triton)]
```

### Tahapan Eksekusi:
1. **Zero-Copy Ingestion:** Stream RTSP didekodekan secara langsung menggunakan chip ASIC hardware dekoder GPU (NVDEC), menghasilkan frame terkompresi langsung di memori GPU (VRAM) tanpa intervensi memori host (RAM CPU).
2. **GPU Data Pipeline (NVIDIA DALI):** Melakukan resizing bilinear, normalisasi mean/std, dan layout conversion ($NHWC \to NCHW$) secara murni menggunakan CUDA core paralel.
3. **Optimized Model Execution:** Frame tensor dilewatkan ke Triton Inference Server. Dynamic batcher mengelompokkan request individual dalam jendela latensi ketat (misal: 2ms max delay) untuk memaksimalkan utilitas Tensor Core tanpa melanggar Service Level Objective (SLO).
4. **Vector Quantization & Inverted Indexing:** Embedding hasil inferensi langsung dikueri ke distributed vector database menggunakan indeks graf HNSW (*Hierarchical Navigable Small World*) atau IVFPQ (*Inverted File with Product Quantization*) untuk pencarian tetangga terdekat dalam waktu `< 10ms`.

---

## 6. Analogy & Diagram

### Analogi Pemrosesan Citra: Detektif Tradisional vs Tim Analis Global
* **CNN (Detektif Tradisional dengan Kaca Pembesar):** Mulai memeriksa piksel individual, menyimpulkan garis tepi kecil, lalu menggeser kaca pembesar secara berurutan ke samping. Pola keseluruhan baru dipahami setelah menelusuri seluruh permukaan berkali-kali. Jika objek penting terpisah sangat jauh di ujung frame, korelasi keduanya baru disadari di lapisan hierarki paling akhir.
* **ViT (Tim Analis Global di Ruang Komando):** Citra dipotong menjadi foto-foto polaroid kecil (*patches*). Seluruh polaroid disebar sekaligus di atas meja bundar. Setiap analis (*attention head*) langsung melihat seluruh foto polaroid secara serentak, menghubungkan keterkaitan visual antara ujung kiri-atas dan kanan-bawah secara langsung pada iterasi pertama.

---

## 7. Simple & Practical Implementation

### 7.1 Simple Example: Patch Embedding Layer Manual (PyTorch)

```python
import torch
import torch.nn as nn

class PatchEmbedding(nn.Module):
    """
    Memecah citra 2D menjadi sekuens patch 1D terproyeksi.
    Implementasi berbasis konvolusi 2D dengan stride identik kernel_size.
    """
    def __init__(self, img_size: int = 224, patch_size: int = 16, in_channels: int = 3, embed_dim: int = 768):
        super().__init__()
        assert img_size % patch_size == 0, "Resolusi gambar harus habis dibagi patch size."
        self.img_size = img_size
        self.patch_size = patch_size
        self.num_patches = (img_size // patch_size) ** 2

        # Konvolusi ini secara matematis ekuivalen dengan flattening patch + linear projection
        self.proj = nn.Conv2d(
            in_channels=in_channels,
            out_channels=embed_dim,
            kernel_size=patch_size,
            stride=patch_size
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Input shape: (Batch, Channels, Height, Width)
        B, C, H, W = x.shape
        assert H == self.img_size and W == self.img_size, f"Dimensi citra ({H}x{W}) tidak sesuai konfig ({self.img_size}x{self.img_size})."
        
        # Output conv: (B, Embed_Dim, H/P, W/P) -> Flatten: (B, Embed_Dim, Num_Patches) -> Transpose: (B, Num_Patches, Embed_Dim)
        x = self.proj(x).flatten(2).transpose(1, 2)
        return x

# Verifikasi Aljabar Dimensi
if __name__ == "__main__":
    dummy_img = torch.randn(8, 3, 224, 224)
    patch_embed = PatchEmbedding(img_size=224, patch_size=16, in_channels=3, embed_dim=768)
    out = patch_embed(dummy_img)
    print(f"Bentuk Tensor Output: {out.shape}")  # Ekspektasi: torch.Size([8, 196, 768])
```

---

### 7.2 Practical Example: Industrial-Grade Multi-Modal Retrieval Inference Engine

Implementasi inference client asynchronous berstandar industri dengan optimasi FP16, dynamic batching dummy logic, dan normalisasi tensor aman.

```python
from typing import List, Tuple, Dict, Any
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision.transforms as T
from PIL import Image

class MultimodalEmbeddingPipeline(nn.Module):
    """
    Arsitektur Dual-Encoder CLIP-Style Miniatur Teroptimasi untuk Inferensi Produksi.
    Mendukung input visual dan tekstual dengan normalisasi L2 deterministik.
    """
    def __init__(self, visual_dim: int = 512, text_dim: int = 512, joint_latent_dim: int = 256):
        super().__init__()
        # Backbone visual sederhana (Simulasi Vision Transformer Head)
        self.visual_backbone = nn.Sequential(
            nn.AdaptiveAvgPool2d((1, 1)),
            nn.Flatten(),
            nn.Linear(visual_dim, 512),
            nn.LayerNorm(512),
            nn.GELU()
        )
        self.visual_projection = nn.Linear(512, joint_latent_dim, bias=False)
        
        # Backbone teks sederhana (Simulasi Transformer Text Head)
        self.text_backbone = nn.Sequential(
            nn.Linear(text_dim, 512),
            nn.LayerNorm(512),
            nn.GELU()
        )
        self.text_projection = nn.Linear(512, joint_latent_dim, bias=False)
        
        # Skala temperatur inversi ekuivalen CLIP (1/tau)
        self.logit_scale = nn.Parameter(torch.ones([]) * np.log(1 / 0.07))

    def encode_image(self, image_tensor: torch.Tensor) -> torch.Tensor:
        features = self.visual_backbone(image_tensor)
        embeddings = self.visual_projection(features)
        return F.normalize(embeddings, p=2, dim=-1)

    def encode_text(self, text_tensor: torch.Tensor) -> torch.Tensor:
        features = self.text_backbone(text_tensor)
        embeddings = self.text_projection(features)
        return F.normalize(embeddings, p=2, dim=-1)

    def forward(self, images: torch.Tensor, texts: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        image_embeds = self.encode_image(images)
        text_embeds = self.encode_text(texts)
        return image_embeds, text_embeds


class ProductionInferenceServer:
    """
    Engine Runtime Inferensi Produksi dengan Preprocessing, Validasi CUDA,
    dan Komputasi Similitudo Lintas-Modalitas Terdistribusi.
    """
    def __init__(self, model_checkpoint: str = None, device: str = "cuda" if torch.cuda.is_available() else "cpu"):
        self.device = torch.device(device)
        self.model = MultimodalEmbeddingPipeline(visual_dim=3).to(self.device)
        
        if self.device.type == "cuda":
            self.model = self.model.half()  # Konversi Bobot Model ke FP16 murni
        self.model.eval()

        # Inisialisasi pipeline transformasi citra standar ImageNet
        self.transform = T.Compose([
            T.Resize((224, 224), interpolation=T.InterpolationMode.BICUBIC),
            T.ToTensor(),
            T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])

    @torch.inference_mode()
    def compute_similarity(self, pil_images: List[Image.Image], raw_text_features: torch.Tensor) -> np.ndarray:
        """
        Menjalankan zero-shot cross-modal similarity scoring secara asinkron.
        Args:
            pil_images: List batch citra mentah input.
            raw_text_features: Dummy input representasi teks berukuran (B_text, 512).
        Returns:
            Numpy array skor cosine similarity matriks (B_img, B_text).
        """
        if not pil_images:
            raise ValueError("Input batch gambar tidak boleh kosong.")

        # Eksekusi Transformasi Batch
        transformed_images = torch.stack([self.transform(img) for img in pil_images]).to(self.device)
        text_inputs = raw_text_features.to(self.device)

        if self.device.type == "cuda":
            transformed_images = transformed_images.half()
            text_inputs = text_inputs.half()

        # Eksekusi Inferensi Teroptimasi (Tanpa pelacakan gradient graph)
        image_embeddings = self.model.encode_image(transformed_images)
        text_embeddings = self.model.encode_text(text_inputs)

        # Komputasi Dot-Product / Cosine Matrix: S_ij = Img_i . Txt_j^T
        similarity_matrix = torch.matmul(image_embeddings, text_embeddings.T)
        
        return similarity_matrix.cpu().float().numpy()

# Pipeline Integration Validation
if __name__ == "__main__":
    server = ProductionInferenceServer(device="cpu")  # Fallback CPU untuk testing lokal
    
    # 2 Citra Dummy RGB
    dummy_pil_images = [
        Image.fromarray(np.uint8(np.random.rand(300, 300, 3) * 255)),
        Image.fromarray(np.uint8(np.random.rand(400, 500, 3) * 255))
    ]
    
    # 3 Dummy Text Tensor Vector (Misal hasil embedding token transformer)
    dummy_text_vectors = torch.randn(3, 512)

    similarity_scores = server.compute_similarity(dummy_pil_images, dummy_text_vectors)
    print("Shape Matriks Similitudo (Citra x Teks):", similarity_scores.shape)
    print("Contoh Matriks Similitudo Terkalkulasi:\n", similarity_scores)
    assert similarity_scores.shape == (2, 3), "Dimensi output similarity tidak valid!"
```

---

## 8. Real-World Case Study: Enterprise Scale

### Konteks: Automated Checkout & Anomaly Detection Retail Terdistribusi (5.000 Toko Fisik)

* **Skala Masalah:** Sebuah konglomerat retail global mengoperasikan 5.000 cabang minimarket tanpa kasir (*autonomous stores*). Setiap cabang memiliki rata-rata 32 kamera 4K (30 FPS) yang melacak pergerakan produk dari rak ke keranjang pelanggan secara simultan. Total stream yang masuk: 160.000 video feeds secara berkesinambungan.
* **Kebutuhan Sistem (SLO):** Latensi deteksi interaksi produk maksimal `150 ms` (p99). Biaya operasional cloud dibatasi maksimal `$0.001` per transaksi. Zero-shot recognition untuk katalog 50.000 SKU yang terus berganti setiap minggu tanpa retrain model.

```
Edge Layer (Cabang Retail)                           Centralized Cloud Infrastructure
┌───────────────────────────────┐
│ 32 Kamera IP 4K (RTSP Streams)│
└──────────────┬────────────────┘
               │ H.264 Streams
               ▼
┌───────────────────────────────┐
│ Edge Micro-Server             │
│ (Dual NVIDIA Jetson Orin AGX) │
│ - Hardware NVDEC Decoders     │
│ - Motion Masking & Tracking   │
│ - Triton Server: Swin-Small   │
│ - Zero-Shot Crop Generator    │
└──────────────┬────────────────┘
               │ Embeddings (Vector FP16) + Crop Frames Anomali Saja
               │ (Bandwidth Saving: 98.7% Drop vs Raw Video)
               ▼
      [Dedicated SD-WAN]
               │
               ▼
┌────────────────────────────────────────────────────────┐
│ Central High-Throughput Cluster (AWS EKS + A100 GPUs) │
│                                                        │
│ ┌──────────────────────┐      ┌──────────────────────┐ │
│ │ Qdrant Vector Search │ <──> │ Triton VLM Server    │ │
│ │ (100M Vectors HNSW)  │      │ (LLaVA-NeXT-8B QAT)  │ │
│ │ Lookup Produk: <8ms  │      │ Arbitrasi Konflik    │ │
│ └──────────────────────┘      └──────────────────────┘ │
└────────────────────────────────────────────────────────┘
```

### Solusi Teknis & Arsitektur Implementasi:
1. **Edge Inference Filtering:** Alih-alih mengirim video mentah ke cloud (yang memerlukan bandwidth terlarang: $\approx 1.2 \text{ Tbps}$ total), sistem menerapkan inferensi bertingkat (*hierarchical inference*). Komputer lokal (NVIDIA Jetson Orin) menjalankan detektor pergerakan objek dan model Swin-Transformer kecil (INT8) teroptimasi TensorRT.
2. **Bandwidth Optimization:** Jetson hanya mengekstraksi vektor embedding 512-dimensi dari bounding box barang yang diinteraksikan, kemudian mengirim vektor tersebut via gRPC streaming ke kluster pusat. Penghematan konsumsi bandwidth jaringan mencapai **98.7%**.
3. **Pencarian Katalog Skala Besar:** Di sisi cloud, kluster Qdrant menerima vektor dan melakukan pencarian kemiripan kosinus terhadap 50.000 katalog SKU dalam waktu kurang dari `8 ms`.
4. **LLM/VLM Arbitration:** Jika jarak kosinus berada di ambang batas abu-abu (ambiguitas antara kaleng soda reguler vs kaleng diet berdesain mirip: similarity score $0.78 < S < 0.84$), crop citra dikirim ke model Vision-Language LLaVA-NeXT-8B (FP8) yang dihosting di Triton AWS Cluster untuk verifikasi silang berbasis teks penalaran mendalam.

---

## 9. Trade-offs & Deep Engineering Analysis

| Dimensi Arsitektur | Convolutional Nets (e.g., ConvNeXt) | Vanilla Vision Transformer (ViT-H) | Swin Transformer (Hierarchical) | Vision-Language Models (e.g., LLaVA) |
| :--- | :--- | :--- | :--- | :--- |
| **Kompleksitas Komputasi** | $\mathcal{O}(H \cdot W)$ (Linear) | $\mathcal{O}((H \cdot W)^2)$ (Kuadratik Spasial) | $\mathcal{O}(H \cdot W \cdot M^2)$ (Linear terhadap input) | $\mathcal{O}(T_{prompt} + T_{patches})^2$ (Sangat Berat) |
| **Kebutuhan Data Awal** | Rendah - Menengah (Inductive Bias kuat) | Ekstrem (>100M data untuk pre-train optimal) | Menengah - Tinggi (ImageNet-22k) | Ekstrem (Billion-token pretraining) |
| **Throughput Inferensi (A100, FP16)** | $\approx 2.800\text{ img/sec}$ | $\approx 310\text{ img/sec}$ | $\approx 920\text{ img/sec}$ | $\approx 25\text{ requests/sec}$ |
| **Kapabilitas Zero-Shot Reasoning** | Nol (Klasifikasi Tertutup) | Nol (Harus Fine-tuning) | Nol (Harus Fine-tuning) | Tinggi (Generalisasi kontekstual natural) |
| **Footprint VRAM (Batch 32, 4K Input)** | Rendah ($\approx 4\text{ GB}$) | OOM (Out Of Memory) | Terkendali ($\approx 14\text{ GB}$) | OOM tanpa Extreme Patch Tiling |

### Kuantisasi Trade-off: FP32 vs FP16 vs INT8 vs FP8
* **FP32 $\to$ FP16:** Memberikan percepatan throughput sebesar $\approx 2.2\times$ pada NVIDIA Tensor Cores Ampere/Ada Lovelace tanpa kehilangan metrik akurasi mAP yang signifikan ($\Delta < 0.05\%$). Wajib digunakan sebagai baseline standar industri.
* **FP16 $\to$ INT8 (Post-Training Quantization):** Menghemat footprint memori hingga $50\%$ tambahan, throughput melonjak hingga $\approx 1.8\times$ dibanding FP16. Namun, lapisan *Softmax* dan *LayerNorm* pada Vision Transformer rentan mengalami *overflow/underflow* akibat sebaran nilai aktivasi yang memiliki *long-tail distribution*. Membutuhkan teknik kuantisasi non-uniform atau QAT (*Quantization-Aware Training*) dengan skema kliping kalibrasi KL-Divergence.
* **FP8 (E4M3 / E5M2 Formats):** Didukung penuh pada arsitektur Hopper (H100) dan Blackwell. Memberikan latensi setara INT8 namun mempertahankan dynamic range yang cukup lebar, sangat ideal untuk memproyeksikan token multimodal visual langsung ke blok feed-forward LLM tanpa kalibrasi yang kompleks.

---

## 10. Common Mistakes & Troubleshooting

### 1. Dynamic Shape Mismatch pada Konversi TensorRT
* **Gejala:** Engine TensorRT gagal dibangun (*build failure*) atau melakukan alokasi memori hingga crash OOM saat menerima resolusi citra dinamis dari stream live.
* **Root Cause:** Profil optimasi (`IOptimizationProfile`) tidak dikonfigurasi dengan batas minimum, optimum, dan maksimum dimensi tensor input secara eksplisit.
* **Solusi:** Konfigurasi profile TensorRT:
  ```python
  profile = builder.create_optimization_profile()
  profile.set_shape("input_tensor", min=(1, 3, 224, 224), opt=(16, 3, 512, 512), max=(32, 3, 1080, 1920))
  config.add_optimization_profile(profile)
  ```

### 2. Positional Embedding Interpolation Bugs saat Mengubah Resolusi Citra
* **Gejala:** Akurasi model ViT terjun drastis ketika resolusi input diubah dari pre-trained baseline (misal: $224 \times 224 \to 448 \times 448$).
* **Root Cause:** Menggunakan linear flattening langsung pada positional embedding tensor alih-alih melakukan *bicubic interpolation* 2D terstruktur pada grid spasial sebelum flattening ulang.
* **Solusi:** Gunakan interpolasi anti-aliased bicubic khusus pada bobot tensor koordinat spasial:
  ```python
  def resize_pos_embed(pos_embed, new_h, new_w, patch_size=16):
      # pos_embed: (1, N+1, D)
      cls_token = pos_embed[:, :1]
      grid_tokens = pos_embed[:, 1:]
      orig_size = int(grid_tokens.shape[1] ** 0.5)
      grid_tokens = grid_tokens.reshape(1, orig_size, orig_size, -1).permute(0, 3, 1, 2)
      grid_tokens = F.interpolate(grid_tokens, size=(new_h // patch_size, new_w // patch_size), mode='bicubic', align_corners=False)
      grid_tokens = grid_tokens.permute(0, 2, 3, 1).flatten(1, 2)
      return torch.cat((cls_token, grid_tokens), dim=1)
  ```

### 3. GPU Pipeline Starvation (CPU Decoding Bottleneck)
* **Gejala:** Utilisasi GPU fluktuatif tajam antara 15% hingga 90%, sementara konsumsi CPU host mencapai 100%. Latensi inferensi meningkat drastis.
* **Root Cause:** OpenCV / PIL default menggunakan CPU threads untuk mendekode file format JPEG/PNG/H264 sebelum ditransfer melalui PCIe bus ke VRAM GPU.
* **Solusi:** Ganti pipeline IO menggunakan NVIDIA DALI atau decord yang langsung membaca byte memory terkompresi langsung ke VRAM melalui NVDEC hardware pipeline.

---

## 11. Best Practices & Production Checklist

### Pre-Deployment Pipeline Checklist
- [ ] **Validasi Aspect Ratio Padding:** Pastikan frame di-resize menggunakan *Letterbox padding* alih-alih distorsi *bilinear stretch* yang merusak spatial aspect ratio produk.
- [ ] **Locking GPU Clocks:** Pada node inferensi bare-metal/cloud, matangkan clock frekuensi GPU via CLI untuk menjaga kestabilan latensi p99: `nvidia-smi --lock-gpu-clocks=1410,1410`.
- [ ] **TensorRT Kernel Warmup:** Jalankan minimum 50 iterasi inferensi sintetis dengan variasi dimensi dynamic batch maksimum sebelum mengizinkan endpoint menerima traffic produksi riil.
- [ ] **Host-to-Device Memory Pinned Memory:** Pastikan DataLoader menggunakan `pin_memory=True` untuk mempercepat proses copy memory dari CPU ke GPU via Direct Memory Access (DMA).

### Triton Inference Server Configuration Best Practices
- [ ] Aktifkan `dynamic_batching` dengan parameter `max_queue_delay_microseconds: 2000` (maksimal toleransi antrean 2 milidetik).
- [ ] Tentukan `instance_group` berbasis isolasi GPU Core: jika model berukuran kecil, alokasikan 2-4 instances per physical GPU untuk memaksimalkan CUDA compute saturation.
- [ ] Aktifkan protocol komunikasi **gRPC** murni untuk streaming tensor, hindari REST/HTTP JSON payload overhead untuk transmisi float array berskala masif.

---

## 12. Hands-on Practice: Step-by-Step Architecture Pipeline

Dalam sesi praktikum ini, Anda akan membangun modul komputasi ekstraksi visual embedding berbasis ONNX Runtime dengan optimasi FP16 dan dynamic axes. 

Simpan seluruh kode berikut di dalam folder: `hands-on/m02/`

### File: `hands-on/m02/export_vit_onnx.py`
Ekspor model ViT kustom ke format ONNX dengan dynamic batch axes:

```python
import os
import torch
import torch.nn as nn

class ProductionVisionTransformerHead(nn.Module):
    def __init__(self, embed_dim: int = 768, output_dim: int = 512):
        super().__init__()
        self.norm = nn.LayerNorm(embed_dim)
        self.head = nn.Linear(embed_dim, output_dim, bias=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Asumsikan input merupakan token CLS dari ViT: (Batch, Embed_Dim)
        x = self.norm(x)
        x = self.head(x)
        # Normalisasi vektor L2 secara in-graph untuk menghemat komputasi eksternal
        norm = torch.norm(x, p=2, dim=-1, keepdim=True)
        return x / (norm + 1e-6)

def run_export():
    os.makedirs("models", exist_ok=True)
    model = ProductionVisionTransformerHead()
    model.eval()

    dummy_input = torch.randn(1, 768, dtype=torch.float32)
    onnx_path = "models/vision_head.onnx"

    torch.onnx.export(
        model,
        dummy_input,
        onnx_path,
        export_params=True,
        opset_version=17,
        do_constant_folding=True,
        input_names=["input_tokens"],
        output_names=["l2_embeddings"],
        dynamic_axes={
            "input_tokens": {0: "batch_size"},
            "l2_embeddings": {0: "batch_size"}
        }
    )
    print(f"[SUCCESS] Model berhasil diekspor ke: {onnx_path}")

if __name__ == "__main__":
    run_export()
```

### File: `hands-on/m02/inference_ort_gpu.py`
Eksekusi inferensi paralel menggunakan ONNX Runtime Execution Provider dengan optimasi CUDA/TensorRT:

```python
import numpy as np
import onnxruntime as ort
import time

def benchmark_ort_pipeline():
    model_path = "models/vision_head.onnx"
    
    # Utamakan TensorrtExecutionProvider dan CUDAExecutionProvider
    providers = [
        ('CUDAExecutionProvider', {
            'device_id': 0,
            'arena_extend_strategy': 'kNextPowerOfTwo',
            'gpu_mem_limit': 2 * 1024 * 1024 * 1024, # Batasi 2 GB
            'cudnn_conv_algo_search': 'EXHAUSTIVE',
            'do_copy_in_default_stream': True,
        }),
        'CPUExecutionProvider'
    ]

    session = ort.InferenceSession(model_path, providers=providers)
    input_name = session.get_inputs()[0].name
    output_name = session.get_outputs()[0].name

    print(f"[INFO] Running on provider: {session.get_providers()[0]}")

    # Simulasi Warmup
    warmup_tensor = np.random.randn(1, 768).astype(np.float32)
    for _ in range(20):
        _ = session.run([output_name], {input_name: warmup_tensor})

    # Benchmark Pengujian Dynamic Batching
    batch_sizes = [1, 8, 32, 64]
    for b in batch_sizes:
        batch_input = np.random.randn(b, 768).astype(np.float32)
        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            outputs = session.run([output_name], {input_name: batch_input})
            latencies.append((time.perf_counter() - start) * 1000)
        
        p50 = np.percentile(latencies, 50)
        p99 = np.percentile(latencies, 99)
        print(f"Batch Size: {b:02d} | p50 Latency: {p50:.2f} ms | p99 Latency: {p99:.2f} ms | L2-Norm Check: {np.linalg.norm(outputs[0][0]):.4f}")

if __name__ == "__main__":
    benchmark_ort_pipeline()
```

---

## 13. Exercises

### Level Easy
Tuliskan sebuah function python murni menggunakan PyTorch untuk mengonversi matriks logits kemiripan CLIP $(B \times B)$ menjadi probabilitas zero-shot classification multi-kelas untuk satu citra terhadap $C$ teks label referensi. Tambahkan scaling temperatur $\tau = 0.01$.
* **Kriteria Keberhasilan:** Output menghasilkan distribusi probabilitas terdistribusi Softmax yang valid (jumlah probabilitas $= 1.0$) dengan penanganan numerik yang stabil (mencegah NaN/Inf).

### Level Medium
Rancang custom PyTorch Loss Module yang mengimplementasikan **Asymmetric Loss** untuk teks dan citra, di mana false positive citra (mengidentifikasi objek non-terkait) mendapatkan penalti $\alpha$ kali lebih berat dibandingkan false negative teks.
* **Kriteria Keberhasilan:** Kode modular turunan `nn.Module`, mendukung backward pass otomatis, dan memiliki unit test tensor gradient checking.

### Level Hard
Bangun custom wrapper C++/Python atau pure CUDA-accelerated post-processor untuk algoritma Non-Maximum Suppression (NMS) berbasis hasil ekstraksi bounding-box dari output token Swin Transformer. 
* **Kriteria Keberhasilan:** Mampu memproses 10.000 raw predictions dengan IoU threshold $0.5$ dalam durasi waktu kurang dari $1.5 \text{ ms}$ pada arsitektur GPU Nvidia Ampere.

---

## 14. Real-World Architectural Challenge

### Skenario Kasus Kompleks: Autonomous Highway Incident Video Retrieval Under Extreme Constraint

Sebuah konsorsium jalan tol nasional mengontrak Anda untuk membangun sistem *Cross-Modal Video Surveillance Intelligence System*. Sistem ini harus memantau 1.200 kilometer jalan tol yang diawasi oleh 2.400 kamera CCTV Full HD (1080p @ 30 FPS). Operator lalu lintas membutuhkan kemampuan untuk mengetik kueri bahasa alami seperti: *"Truk tangki merah berhenti di bahu jalan dengan asap mengepul dari kap mesin"* dan menerima timestamp video serta lokasi koordinat CCTV yang bersangkutan dalam waktu **kurang dari 3 detik secara end-to-end**.

### Kendala Teknis:
1. **Infrastruktur Jaringan:** Bandwidth uplink dari kamera ke node pemrosesan regional dibatasi rata-rata hanya `1.5 Mbps` per kamera.
2. **Keterbatasan Hardware Komputasi:** Total anggaran server GPU regional dibatasi maksimal 8 unit NVIDIA L40S GPU untuk meng-handle seluruh 2.400 stream tersebut.
3. **Temporal Reasoning:** Kejadian lalu lintas bersifat temporal (membutuhkan pemahaman urutan frame berurutan sepanjang waktu, bukan sekadar deteksi frame statis tunggal).

### Output Dokumen Desain yang Wajib Anda Susun:
1. **Arsitektur Dekomposisi Temporal & Spasial:** Bagaimana Anda mereduksi frame rate tanpa kehilangan informasi kejadian kritis? (Formula sampling, frame extraction strategy).
2. **Desain Model Multimodal Video:** Arsitektur foundation model apa yang Anda terapkan? (Misal: VideoCLIP, TimeSformer, atau perpaduan ViT Spasial + Temporal Causal Attention?). Jelaskan alokasi parameter dan strategi kuantisasi model.
3. **Infrastruktur Data & Indexing:** Rancang topologi database vektor temporal berskala besar untuk menyimpan representasi embeddings dari 2.400 kamera selama retention period 30 hari. Bagaimana Anda menyusun skema partisi graf (Clustering, HNSW partitioning, Payload filtering)?
4. **Analisis Latensi dan Biaya Hardware:** Buktikan secara matematis bahwa 8 unit GPU NVIDIA L40S sanggup melayani ingest streaming 2.400 kamera secara berkelanjutan serta mengeksekusi kueri operator jalan tol dalam batas SLO `< 3 detik`.

---

## 15. Evaluation Quiz

### 15.1 Pertanyaan Basic

1. **Bagaimana Vision Transformer (ViT) menyelesaikan masalah pemetaan data 2D citra ke arsitektur Transformer standar yang hanya menerima token sekuens 1D?**
   * *Jawaban:* ViT membagi citra berdimensi $(H \times W \times C)$ menjadi blok-blok kecil spasial non-overlapping (patches) berdimensi $(P \times P \times C)$. Masing-masing patch diratakan (*flattened*) menjadi vektor 1D dengan panjang $P^2 \cdot C$, kemudian diproyeksikan secara linear melalui matriks bobot (*learnable linear projection*) menjadi vektor representasi berdimensi laten $D$. Kumpulan vektor ini kemudian disusun berurutan sebagai deret sekuens token panjang $N = \frac{HW}{P^2}$.

2. **Mengapa Vision Transformer membutuhkan penambahan Explicit Position Embeddings, sedangkan Convolutional Neural Networks (CNN) tidak membutuhkannya?**
   * *Jawaban:* Operasi konvolusi pada CNN secara inheren bersifat *spatially constrained*—kernel beroperasi secara lokal pada grid terstruktur sehingga urutan spasial piksel terekam secara implisit melalui struktur kisi feature map. Sebaliknya, operasi *Self-Attention* pada Transformer bersifat *permutation invariant* (simetris terhadap permutasi posisi token). Tanpa *position embeddings*, Transformer akan memperlakukan token patch yang diacak posisinya sama persis dengan token patch yang tersusun teratur.

3. **Apa fungsi utama dari Token $[CLS]$ (Classification Token) yang disematkan pada awal sekuens patch di Vision Transformer?**
   * *Jawaban:* Token $[CLS]$ adalah sebuah representasi token terpelajari (*learnable vector*) bebas yang tidak terikat pada patch citra spesifik mana pun. Melalui lapisan-lapisan *Multi-Head Self-Attention*, token $[CLS]$ diagregasikan secara dinamis untuk menyerap dan memadatkan informasi global dari seluruh patch citra lainnya, menghasilkan satu representasi vektor ringkas tingkat tinggi yang siap diproses oleh classification head.

4. **Sebutkan formulasi fungsi optimasi yang digunakan pada model CLIP dan jelaskan tujuan dari parameter temperatur $\tau$!**
   * *Jawaban:* Formulasi yang digunakan adalah *Symmetric Cross-Entropy (InfoNCE) Loss* pada matriks cosine similarity pasangan citra-teks. Parameter temperatur terpelajari $\tau$ (umumnya di-skalakan sebagai $\exp(\tau)$) berfungsi mengontrol kemiringan (*sharpness*) distribusi probabilitas Softmax. Nilai $\tau$ yang tepat mencegah gradien jenuh (*vanishing gradients*) atau sebaliknya mencegah model terlalu over-confident pada pasangan sampel yang mudah di awal masa pelatihan.

5. **Mengapa resolusi patch yang semakin kecil (misal $P=8$ dibanding $P=16$) pada ViT meningkatkan kebutuhan komputasi dan memori GPU secara dramatis?**
   * *Jawaban:* Jumlah token yang dihasilkan berbanding terbalik secara kuadratik terhadap ukuran patch: $N = \frac{HW}{P^2}$. Jika patch size diturunkan dari 16 ke 8 (faktor $2\times$), panjang token $N$ melonjak $4\times$. Karena kompleksitas waktu dan memori standar Multi-Head Self-Attention adalah $\mathcal{O}(N^2)$, beban komputasi dan konsumsi alokasi memori matriks attention melonjak sebesar $4^2 = 16\times$.

---

### 15.2 Pertanyaan Intermediate

6. **Bagaimana mekanisme *Shifted Window Attention* pada Swin Transformer memfasilitasi interaksi lintas jendela (cross-window connections) tanpa memperluas kompleksitas komputasi menjadi kuadratik?**
   * *Jawaban:* Swin Transformer menggeser partisi jendela sebesar $\lfloor \frac{M}{2} \rfloor$ patch pada layer yang berurutan. Area jendela baru yang bergeser ini mencakup batas-batas irisan dari jendela-jendela pada layer sebelumnya, memungkinkan transfer informasi lintas-wilayah spasial. Untuk menjaga ukuran jendela tetap konstan $M \times M$ tanpa menambah komputasi padding kosong, Swin menggunakan *cyclic-shifting* ke arah kiri-atas yang dipadukan dengan *masked attention* guna memastikan token-token dari tepi yang berlawanan tidak saling menghitung bobot attention palsu.

7. **Jelaskan fenomena *Cross-Modal Representation Collapse* yang kerap terjadi saat melatih model kontrastif seperti CLIP dari awal, dan bagaimana cara memitigasinya!**
   * *Jawaban:* *Cross-Modal Collapse* terjadi ketika encoder citra dan encoder teks memproyeksikan seluruh data ke sub-ruang manifold yang sangat sempit dan terkumpul di satu area kecil (*hyperspherical clustering*), atau ketika seluruh representasi didominasi oleh modalitas teks saja sementara gradien visual berhenti berkembang. Mitigasinya meliputi: (1) Normalisasi $L_2$ ketat pada vektor embedding sebelum kalkulasi kemiripan, (2) Penggunaan ukuran mini-batch yang sangat besar (ribuan hingga puluhan ribu sampel) untuk memberikan variasi negatif kontrastif yang kaya, (3) Membatasi nilai minimum temperatur $\tau$ agar logit tidak meledak, dan (4) Menggunakan teknik *Decoupled Weight Decay* (AdamW).

8. **Mengapa teknik Post-Training Quantization (PTQ) ke format INT8 lebih sering merusak akurasi Vision Transformer dibandingkan arsitektur CNN klasik?**
   * *Jawaban:* Vision Transformer memiliki dinamika aktivasi yang berbeda secara signifikan dibanding CNN: (1) Nilai aktivasi setelah fungsi *GELU* dan *Softmax* memiliki variansi rentang dinamis yang sangat ekstrem (*extreme outlier activations* dengan nilai tinggi yang terkonsentrasi pada kanal-kanal token tertentu), dan (2) Nilai aktivasi *Layer Normalization* sangat peka terhadap eror pembulatan resolusi kuantisasi seragam (*uniform quantization error*). Pada INT8 seragam, nilai-nilai pencilan ini memaksa skala kuantisasi melebar, mengorbankan presisi representasi mayoritas nilai aktivasi yang mendekati nol.

9. **Apa peran arsitektur *Perceiver Resampler* atau Cross-Attention Projector pada Vision-Language Models modern (seperti Flamingo atau LLaVA-1.5) dibanding Linear Projection tunggal?**
   * *Jawaban:* Linear Projection sederhana memetakan setiap token patch visual secara 1:1 ke ruang token LLM. Jika model ViT menghasilkan 576 token patch, 576 slot context window LLM akan terkonsumsi seluruhnya oleh citra tersebut, membatasi kemampuan pemrosesan multi-gambar atau percakapan panjang. *Perceiver Resampler* menggunakan sekumpulan *learnable latent queries* (misal: 64 queries) yang berinteraksi dengan ratusan feature map visual via cross-attention. Hal ini memadatkan ratusan patch visual menjadi sejumlah representasi token ringkas yang konstan (misal: tepat 64 token) dengan informasi semantik paling relevan sebelum disalurkan ke LLM.

10. **Bagaimana mekanisme *Dynamic Batching* pada Triton Inference Server meningkatkan throughput sistem inferensi tanpa melanggar Service Level Agreement (SLA) latensi?**
    * *Jawaban:* Triton Inference Server mengimplementasikan antrean request berbasis hardware-timer di level server engine. Ketika sebuah request inferensi individual masuk, server menahannya di antrean dalam batas waktu konfigurasi `max_queue_delay_microseconds`. Jika request baru tiba dalam jendela toleransi waktu tersebut, Triton menggabungkannya ke dalam satu batch tensor besar untuk dieksekusi secara simultan oleh Tensor Core GPU dalam satu operasi komputasi matriks paralel, lalu memecah kembali hasilnya ke client masing-masing. Jika jendela waktu habis sebelum batch terisi penuh, server mengeksekusi batch parsial secara instan agar tidak melanggar batas latensi individual client.

---

### 15.3 Skenario Kasus Produksi

11. **Skenario Kasus: Anomali Degradasi Latensi P99 pada Video Stream Multimodal Pipeline**  
    * *Konteks:* Sistem pemantau keselamatan kerja berbasis kamera di pabrik petrokimia mengalami lonjakan latensi inferensi p99 dari `45 ms` menjadi `420 ms` secara berkala setiap 5 menit sekali. Sistem menggunakan Triton Inference Server dengan model backend Swin-Base TensorRT di GPU Nvidia A100 (40GB).
    * *Investigasi:* Log sistem menunjukkan utilisasi GPU berada pada 35%, temperatur GPU normal (52°C), tidak ada proses eksternal di node Linux, namun metrics I/O Triton menunjukkan nilai `compute_input_duration` melonjak tajam saat degradasi terjadi.
    * *Pertanyaan Evaluasi:* Analisis penyebab struktural dari masalah ini dan berikan langkah mitigasi teknis definitif pada tingkat infrastruktur server/driver!
    * *Solusi Analisis:*
      Penyebab utama dari pola lonjakan latensi periodik ini adalah kombinasi dari **PCIe Bus Host-to-Device Memory Throttling** dan **Garbage Collection (GC) / Dynamic Memory Allocation Spike** pada buffer pipeline:
      1. Lonjakan durasi pada `compute_input_duration` mengindikasikan bahwa engine Triton menunggu proses copy tensor dari host RAM ke device VRAM. Ini kerap terjadi jika alokasi memory tensor input menggunakan pageable host memory alih-alih *CUDA Pinned Memory* (Page-locked memory).
      2. Pola berulang setiap 5 menit menandakan proses flushing buffer data logging internal, pengumpulan garbage collection frame reader OpenCV/Python, atau interupsi *CUDA Memory Re-allocation* akibat fragmentasi memori VRAM karena dynamic shape yang bervariasi secara liar.
      *Langkah Mitigasi Definitif:*
      - Wajib mengaktifkan opsi pinned memory allocator pada shared-memory interface Triton: `--shm-default-byte-size` dan menerapkan IPC POSIX pinned shared memory.
      - Pastikan model TensorRT di-build dengan dimensi batch shape yang terdefinisi rapi dan alokasikan unified memory arena tetap di awal (`gpu_memory_fraction` di-lock).
      - Isolasi NUMA node: Bind proses Triton ke core CPU fisik yang berada dalam satu soket arsitektur NUMA dengan slot kartu PCIe GPU terkait (`numactl --cpunodebind --membind`).

12. **Skenario Kasus: Out-of-Memory (OOM) Cascading Failure saat Ingest Citra Resolusi Ultra-Tinggi (Medical Imaging / GIS)**  
    * *Konteks:* Sebuah platform analisis citra satelit multimodal menerima input citra geo-spasial multispektral berukuran $10.000 \times 10.000$ piksel. Tim ML mencoba melewatkan citra ini langsung ke Vision Transformer skala besar (ViT-Large, $P=16$) untuk ekstraksi representasi zero-shot.
    * *Kegagalan:* Begitu batch size = 1 dieksekusi, sistem langsung melempar pesan fatal: `CUDA out of memory. Tried to allocate 149.01 GiB`.
    * *Pertanyaan Evaluasi:* Hitung mengapa alokasi memori meledak sebesar itu secara matematis pada self-attention layer, dan rancang arsitektur pipeline yang tepat untuk memproses citra ultra-tinggi tersebut tanpa kehilangan detail spasial!
    * *Solusi Analisis:*
      *Perhitungan Matematis:*
      Untuk ukuran citra $10.000 \times 10.000$ dengan $P=16$:
      Jumlah token $N = \left(\frac{10000}{16}\right) \times \left(\frac{10000}{16}\right) = 625 \times 625 = 390.625\text{ tokens}$.
      Matriks Self-Attention menghitung dot product $\mathbf{Q}\mathbf{K}^T$ berdimensi $(N \times N)$.
      Jumlah elemen matriks attention: $390.625 \times 390.625 \approx 1,525 \times 10^{11}\text{ elemen}$.
      Jika menggunakan presisi FP32 (4 bytes per elemen):
      $$\text{Memori} = 1,525 \times 10^{11} \times 4 \text{ bytes} \approx 610 \text{ GB VRAM}$$
      Bahkan dalam FP16 (2 bytes), alokasi murni untuk satu head attention matriks mencapai $\approx 305\text{ GB}$, melampaui kapasitas GPU modern mana pun.
      *Rancangan Arsitektur Pipeline yang Tepat:*
      Terapkan strategi **Hierarchical Sliding-Window Patch Tiling & Feature Merging Pipeline**:
      1. Pecah citra raksasa menjadi grid berukuran standar industri (misal: $512 \times 512$ piksel) dengan overlap border $10-15\%$ untuk mencegah hilangnya konteks di tepi irisan.
      2. Lewatkan masing-masing tile $512 \times 512$ ke ViT backbone secara batch independen untuk mengekstraksi token representasi lokal (setiap tile hanya menghasilkan $32 \times 32 = 1.024$ token $\to$ matriks attention hanya $\approx 2\text{ MB}$).
      3. Terapkan lapisan *Feature Aggregator* tingkat dua (seperti Swin Transformer Stage-4 atau Shallow Graph Convolutional Network / Spatial Pyramid Pooling) yang hanya mengagregasi vektor embedding global dari setiap tile untuk membentuk representasi utuh citra satelit tersebut.

13. **Skenario Kasus: Zero-Shot Multimodal Alignment Drift pada Platform E-Commerce Global**  
    * *Konteks:* Model zero-shot multi-modal retrieval (CLIP variant) yang di-deploy di platform e-commerce fashion global mengalami degradasi metrik Recall@10 sebesar 28% secara perlahan selama 6 bulan terakhir. Sistem memetakan pencarian teks pengguna ("kemeja flanel kasual pria kotak-kotak") langsung ke database citra produk.
    * *Investigasi:* Model bobot tidak pernah diubah sejak deployment. Log query teks menunjukkan pergeseran terminologi pengguna yang kini lebih sering menggunakan istilah slang gen-Z (misal: "baju retro thrift aesthetic", "coquette style"). Sementara itu, foto katalog produk dari seller baru menggunakan background outdoor dinamis dengan banyak noise visual alih-alih background putih studio standar.
    * *Pertanyaan Evaluasi:* Rancang arsitektur retraining loop dan query rewriting pipeline berkesinambungan (*continuous multimodal alignment*) untuk memperbaiki degradasi performa tanpa harus mengulang proses pre-training dari awal (cold restart)!
    * *Solusi Analisis:*
      Untuk mengatasi alignment drift lintas modalitas tanpa biaya mahal cold-start pretraining, rancang arsitektur **Continuous Adapter Fine-Tuning & Dual Query Alignment**:
      1. **Query Normalization & Semantic Rewriting Engine (LLM Layer):**
         - Sisipkan lightweight fast LLM (misal: Llama-3-8B-Instruct via vLLM) di depan encoder teks. LLM bertugas melakukan translasi semantik dari istilah slang dinamis ke bentuk deskriptif kanonikal katalog ("baju retro thrift aesthetic" $\to$ "pakaian vintage gaya 90-an motif garis/kotak bahan katun").
      2. **Parameter-Efficient Dual LoRA Fine-Tuning (PEFT):**
         - Kunci (*freeze*) backbone utama Image Encoder dan Text Encoder CLIP.
         - Pasang modul adapter **Low-Rank Adaptation (LoRA)** pada projection layer $\mathbf{W}_v$ dan $\mathbf{W}_t$.
         - Ambil data pasangan interaksi nyata: citra produk yang diklik/dibeli pengguna dari kueri pencarian teks terkini melalui query-click telemetry log mingguan.
         - Latih modul LoRA menggunakan *Contrastive Hard-Negative Mining Loss* menggunakan batch interaksi baru ini.
      3. **Background Invariance Preprocessing:**
         - Terapkan model segmentasi instan (seperti Fast-SAM atau BiSeNet) pada jalur ingest katalog seller untuk menghasilkan mask foreground pakaian secara otomatis, lalu gabungkan embedding background-stripped frame dengan citra original untuk menetralkan noise visual background non-studio.
      4. **Automated Shadow Deployment & Canary Evaluation:**
         - Jalankan evaluasi berkala metrik Recall@K secara shadow (A/B testing terhadap model lama). Rilis adapter baru secara dinamis via Triton hot-swap model tanpa menyebabkan downtime pada server cluster.

---

## 16. Summary

Modul ini telah mengupas tuntas arsitektur mutakhir Computer Vision dan Multimodal Intelligence untuk kebutuhan sistem skala enterprise:

1. **Vision Transformers (ViT & Swin):** Menggantikan spatial inductive bias konvolusi dengan fleksibilitas global self-attention. Swin Transformer menawarkan efisiensi komputasi linier $\mathcal{O}(HWM^2)$ yang menjadikannya fondasi ideal untuk downstream task dengan input beresolusi tinggi.
2. **Multimodal Representation (CLIP):** Memanfaatkan Symmetric InfoNCE Loss untuk menyatukan ruang laten teks dan citra, membuka kapabilitas *zero-shot open-vocabulary transfer* tanpa keterikatan pada kelas diskrit statis.
3. **Engineering Inference Optimization:** Penerapan FP16/INT8, dynamic batching, zero-copy hardware memory transfer (NVDEC/DALI), serta orkestrasi Triton Inference Server adalah fondasi vital untuk mencapai throughput ribuan transaksi per detik dengan latensi p99 sub-50 milidetik.
4. **Resiliensi Skala Produksi:** Penanganan drift semantik, resolusi dinamis, fragmentasi memori VRAM, dan komputasi piramida bertingkat mutlak dipahami untuk menjaga stabilitas sistem berbasis multimodal foundation model di lingkungan enterprise mission-critical.