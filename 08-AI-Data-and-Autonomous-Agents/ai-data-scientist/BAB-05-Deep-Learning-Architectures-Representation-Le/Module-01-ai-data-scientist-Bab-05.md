# Bab 05: Deep Learning Architectures & Representation Learning
## Modul 01: Foundational Representation Learning, Self-Supervised Contrastive Dynamics, & Latent Topologies

---

### 1. Learning Objectives (Spesifik & Terukur)

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Menganalisis dan Membuktikan Manifold Hypothesis**: Menguraikan secara matematis bagaimana data berdimensi tinggi terkonsentrasi pada sub-manifold berdimensi rendah menggunakan singular value decomposition (SVD) dari matriks kovarians representasi.
2. **Mengimplementasikan Objective Function InfoNCE**: Merancang dan menurunkan formulasi InfoNCE (Information Noise-Contrastive Estimation) loss secara ter-vektorisasi penuh dalam PyTorch tanpa *for-loop* eksplisit, mengoptimalkan kompleksitas komputasi menjadi $\mathcal{O}(B^2)$ untuk batch size $B$.
3. **Mencegah Fenomena Representation Collapse**: Mengidentifikasi dan memitigasi dua varian keruntuhan representasi (*complete collapse* dan *dimensional collapse*) dengan memonitor spektrum nilai eigen (*eigenspectrum*) dan kovarians representasi embedding.
4. **Membangun Pipeline Contrastive Learning End-to-End**: Mengonstruksi arsitektur *self-supervised representation learning* menggunakan encoder backbone, *non-linear projection head*, dan skema augmentasi stokastik yang siap diintegrasikan pada sistem skala produksi.
5. **Mengevaluasi Kualitas Representasi (Linear Probing Protocol)**: Mengukur akurasi generalisasi representasi laten menggunakan protokol *frozen-backbone linear evaluation* dan membandingkannya terhadap baseline *fully supervised*.

---

### 2. Concept Overview (Mental Model & Teori Inti)

Secara historis, alur kerja *Machine Learning* klasik bertumpu pada rekayasa fitur manual (*handcrafted feature engineering*) yang rentan terhadap *curse of dimensionality* dan *inductive bias* manusia. *Deep Learning* secara fundamental mendisrupsi paradigma ini melalui **Representation Learning** (Pembelajaran Representasi): kemampuan model untuk mengekstraksi representasi fitur laten $z \in \mathbb{R}^d$ secara otomatis langsung dari data mentah $x \in \mathcal{X}$, di mana $d \ll \dim(\mathcal{X})$.

```
Paradigma Klasik:
Raw Data (x) ---> [Handcrafted Feature Eng.] ---> Feature Vector (v) ---> [Shallow Classifier] ---> Output (y)

Paradigma Representation Learning:
Raw Data (x) ---> [Parametric Encoder f_theta] ---> Latent Manifold (z) ---> [Task Head g_phi] ---> Downstream Tasks
```

#### Mental Model: The Manifold Hypothesis
Data dunia nyata (gambar, teks, audio, struktur grafis) terdistribusi dalam ruang berdimensi sangat tinggi ($\mathbb{R}^D$). Namun, data valid tidak tersebar seragam di seluruh ruang tersebut. Berdasarkan **Manifold Hypothesis**, probabilitas massa data terpusat pada manifold non-linear $\mathcal{M}$ yang berdimensi jauh lebih rendah ($d$). 

Tujuan utama dari arsitektur Deep Learning modern adalah mempelajari pemetaan diferensiabel:
$$f_\theta: \mathcal{X} \to \mathcal{M} \subset \mathbb{R}^d$$
yang menjaga sifat topologis data: instans yang memiliki kesamaan semantik (*semantic similarity*) dipetakan ke titik-titik yang berdekatan pada metrik ruang Hilbert laten (misalnya melalui *cosine similarity* atau *Euclidean distance*), sedangkan instans yang berbeda secara semantik didorong saling menjauh.

#### Self-Supervised Learning (SSL) & Contrastive Estimation
Dalam konteks enterprise di mana $95\%$ data tidak berlabel (*unlabeled*), SSL memanfaatkan data itu sendiri sebagai sumber supervisi (*pretext task*). Salah satu pendekatan terkuat adalah **Contrastive Representation Learning**, yang mengoptimalkan batas bawah dari informasi mutual (*Mutual Information*) antara representasi tampilan berbeda (*views*) dari instans yang sama:

$$I(z_i; z_j) \ge \log(K) - \mathcal{L}_{\text{InfoNCE}}$$

di mana $K$ adalah jumlah pasangan negatif, dan $\mathcal{L}_{\text{InfoNCE}}$ adalah *loss function* yang memandu dinamika ruang laten agar memaksimalkan pemisahan kluster representasi semantik.

---

### 3. Why It Matters (Dunia Nyata & Kebutuhan Enterprise)

Pada lingkungan enterprise skala besar, ketergantungan pada *supervised learning* murni menghadirkan sejumlah kendala fatal:

1. **Biaya Labeling Eksorbitan**: Memberikan anotasi manual pada jutaan transaksi fraud, gambar patologi medis, atau log keamanan siber membutuhkan domain expert dengan biaya tinggi dan latensi operasional berbulan-bulan.
2. **Label Scarcity & Class Imbalance**: Anomali kritis (misalnya *network intrusions* atau *rare diseases*) terjadi pada rasio $< 0.01\%$. Supervised learning gagal mengekstrak batas keputusan representasional yang kokoh dalam skenario ekstrem ini.
3. **Out-of-Distribution (OOD) Brittleness**: Representasi yang dipelajari via supervised cross-entropy cenderung *overfit* pada korelasi semu (*spurious correlations*) antara fitur dan label, sehingga rapuh terhadap pergeseran distribusi (*covariate shift*).
4. **Kebutuhan Unified Embeddings**: Sistem modern (RAG/Retrieval-Augmented Generation, sistem rekomendasi berbasis vektor, dan mesin pencari visual) memerlukan representasi laten generik yang dapat di-cache ke dalam Vector Databases (e.g., Milvus, Pinecone, pgvector) untuk berbagai *downstream tasks* sekaligus.

---

### 4. Arsitektur & Diagram Komponen

Berikut adalah arsitektur sistematis dari **Contrastive Representation Learning Framework (SimCLR-style)** yang membedah aliran data dari input mentah, transformasi stokastik, pemetaan manifold via encoder backbone, proyeksi non-linear, hingga perhitungan InfoNCE loss.

```
                             +-------------------+
                             | Input Batch: X    |
                             | [B, C, H, W]      |
                             +---------+---------+
                                       |
                   +-------------------+-------------------+
                   |                                       |
                   v                                       v
         +-------------------+                   +-------------------+
         | Augmentation t1   |                   | Augmentation t2   |
         | Random Crop/Jitter|                   | Random Crop/Jitter|
         +---------+---------+                   +---------+---------+
                   |                                       |
                   v                                       v
         +-------------------+                   +-------------------+
         | Augmented View x_i|                   | Augmented View x_j|
         | [B, C, H, W]      |                   | [B, C, H, W]      |
         +---------+---------+                   +---------+---------+
                   |                                       |
                   v                                       v
         +-------------------+                   +-------------------+
         | Backbone Encoder  |                   | Backbone Encoder  |
         | f_theta(.)        |                   | f_theta(.)        |
         | (ResNet/ViT/Conv) |                   | (Shared Weights)  |
         +---------+---------+                   +---------+---------+
                   |                                       |
                   v                                       v
         +-------------------+                   +-------------------+
         | Representation h_i|                   | Representation h_j|
         | [B, D_repr]       |                   | [B, D_repr]       |
         | (Downstream Feat) |                   | (Downstream Feat) |
         +---------+---------+                   +---------+---------+
                   |                                       |
                   v                                       v
         +-------------------+                   +-------------------+
         | Projection Head   |                   | Projection Head   |
         | g_phi(.) (2-MLP)  |                   | g_phi(.) (Shared) |
         +---------+---------+                   +---------+---------+
                   |                                       |
                   v                                       v
         +-------------------+                   +-------------------+
         | Latent Vector z_i |                   | Latent Vector z_j |
         | [B, D_proj]       |                   | [B, D_proj]       |
         +---------+---------+                   +---------+---------+
                   |                                       |
                   +-------------------+-------------------+
                                       |
                                       v
                     +-----------------------------------+
                     |  L2-Normalization along Dim=-1    |
                     |  z_i = z_i / ||z_i||_2            |
                     |  z_j = z_j / ||z_j||_2            |
                     +-----------------+-----------------+
                                       |
                                       v
                     +-----------------------------------+
                     | Cosine Similarity Matrix (2B x 2B)|
                     | S_uv = (u . v) / tau              |
                     +-----------------+-----------------+
                                       |
                                       v
                     +-----------------------------------+
                     | Symmetrical InfoNCE Loss Engine   |
                     | (Cross-Entropy Multi-Class Equiv) |
                     +-----------------+-----------------+
                                       |
                         Backpropagation Gradient (dLoss/d_theta)
                                       v
                            [Optimized Weights theta]
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### 5.1 Formulasi Matematis InfoNCE Loss
Diberikan satu set pasangan tertransformasi $(x_i, x_j)$ yang dihasilkan dari distribusi augmentasi $\mathcal{T}$. Pasangan $(x_i, x_j)$ yang berasal dari sampel identik didefinisikan sebagai **pasangan positif**, sedangkan pasangan yang dibentuk dari sampel berbeda di dalam mini-batch berukuran $B$ bertindak sebagai **pasangan negatif**. Total instans teraugmentasi dalam satu *batch* adalah $2B$.

Untuk sebuah sampel positif $i$, representasi vektor proyeksi ternormalisasi dinotasikan sebagai $z_i \in \mathbb{R}^d$ di mana $\|z_i\|_2 = 1$. Fungsi kerugian InfoNCE simetris didefinisikan sebagai:

$$\mathcal{L}_{i, j} = -\log \frac{\exp\left(\frac{z_i \cdot z_j}{\tau}\right)}{\sum_{k=1}^{2B} \mathbb{I}_{[k \neq i]} \exp\left(\frac{z_i \cdot z_k}{\tau}\right)}$$

Di mana:
*   $\cdot$ menunjukkan *inner product* (karena vektor sudah di-normalisasi L2, ini identik dengan *cosine similarity*).
*   $\tau \in \mathbb{R}^+$ merepresentasikan parameter suhu (*temperature hyperparameter*).
*   $\mathbb{I}_{[k \neq i]} \in \{0, 1\}$ adalah fungsi indikator yang bernilai $0$ jika $k=i$ dan $1$ untuk lainnya.

Total loss untuk keseluruhan batch dieksekusi secara simetris:
$$\mathcal{L}_{\text{total}} = \frac{1}{2B} \sum_{k=1}^{B} \left[ \mathcal{L}_{2k-1, 2k} + \mathcal{L}_{2k, 2k-1} \right]$$

#### 5.2 Dinamika Gradien & Peran Parameter Suhu ($\tau$)
Untuk memahami bagaimana InfoNCE mengonfigurasi manifold representasi, kita turunkan gradien parsial terhadap embedding positif $z_i$:

$$\frac{\partial \mathcal{L}_{i,j}}{\partial z_i} = -\frac{1}{\tau} \left( \left( 1 - P_{ij} \right) z_j - \sum_{k \neq i, k \neq j} P_{ik} z_k \right)$$

Di mana probabilitas softmax $P_{ik}$ adalah:
$$P_{ik} = \frac{\exp\left(\frac{z_i \cdot z_k}{\tau}\right)}{\sum_{m \neq i} \exp\left(\frac{z_i \cdot z_m}{\tau}\right)}$$

Gradien ini memisahkan dua gaya fisik dalam ruang laten:
1. **Attractive Force** (Gaya Tarik): Mendorong $z_i$ menuju pasangan positifnya $z_j$ dengan magnitudo proporsional terhadap $(1 - P_{ij})$.
2. **Repulsive Force** (Gaya Tolak): Mendorong $z_i$ menjauhi semua pasangan negatif $z_k$ dengan magnitudo proporsional terhadap bobot probabilitas $P_{ik}$.

**Peran Kritis $\tau$**:
*   Jika $\tau \to 0$: Probabilitas $P_{ik}$ didominasi secara ekstrem oleh sampel negatif terdekat (*hard negatives*). Gradien meledak (*gradient saturation*), menyebabkan optimasi tidak stabil.
*   Jika $\tau \to \infty$: Distribusi probabilitas menjadi seragam ($P_{ik} \to \frac{1}{2B-1}$). Semua pasangan negatif diberikan penalti yang sama tanpa memedulikan kedekatan semantiknya, menghilangkan kapasitas diskriminatif representasi. Nilai empiris optimal umumnya berada pada rentang $\tau \in [0.05, 0.2]$.

#### 5.3 Peran Non-linear Projection Head
Mengapa representasi $h = f_\theta(x)$ tidak langsung dioptimalkan dengan InfoNCE, melainkan melalui proyeksi non-linear $z = g_\phi(h) = W^{(2)}\sigma(W^{(1)}h)$?
Berdasarkan investigasi empiris dan teoritis (Chen et al., 2020):
1. **Information Loss Prevention**: InfoNCE memaksa invariansi terhadap transformasi augmentasi (misalnya: warna, rotasi). Jika invariansi ini dipaksakan langsung pada $h$, informasi penting tentang orientasi spasial atau intensitas piksel akan hilang permanen dari encoder.
2. Melalui pemisahan $h$ dan $z$, $g_\phi(\cdot)$ membuang informasi spesifik transformasi tersebut pada ruang $z$, sedangkan $h$ mempertahankan informasi topologi global dan semantik lokal yang sangat krusial untuk *downstream tasks*.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi modular, ter-vektorisasi, dan *thread-safe* untuk **Contrastive Representation Learning Backbone** menggunakan PyTorch.

```python
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Tuple, Dict, Any


class ProjectionHead(nn.Module):
    """
    Non-linear Multi-Layer Perceptron (MLP) Projection Head.
    Memetakan representasi backbone h ke ruang laten proyeksi z.
    """
    def __init__(self, in_features: int, hidden_dim: int, out_features: int) -> None:
        super().__init__()
        if in_features <= 0 or hidden_dim <= 0 or out_features <= 0:
            raise ValueError("Seluruh dimensi feature harus bilangan positif non-nol.")
            
        self.net = nn.Sequential(
            nn.Linear(in_features, hidden_dim, bias=False),
            nn.BatchNorm1d(hidden_dim),
            nn.ReLU(inplace=True),
            nn.Linear(hidden_dim, out_features, bias=True)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class VectorizedInfoNCELoss(nn.Module):
    """
    Implementasi InfoNCE Loss vectorized berbasis Cosine Similarity.
    Mengeliminasi iterasi eksplisit dan mendukung batch paralel berskala besar.
    """
    def __init__(self, temperature: float = 0.07) -> None:
        super().__init__()
        if temperature <= 0.0:
            raise ValueError(f"Temperature harus positif, diterima: {temperature}")
        self.temperature = temperature

    def forward(self, z_i: torch.Tensor, z_j: torch.Tensor) -> torch.Tensor:
        """
        Menghitung simetris InfoNCE loss untuk pasangan representasi.
        
        Args:
            z_i: Tensor representasi augmentasi view 1 berukuran [B, D]
            z_j: Tensor representasi augmentasi view 2 berukuran [B, D]
            
        Returns:
            loss: Skalar Tensor bertipe torch.float32
        """
        if z_i.shape != z_j.shape:
            raise ValueError(f"Dimensi mismatch: z_i {z_i.shape} != z_j {z_j.shape}")
        if z_i.dim() != 2:
            raise ValueError(f"Ekspektasi tensor 2D [Batch, Feature], diterima: {z_i.shape}")

        batch_size = z_i.size(0)
        
        # 1. Normalisasi L2 sepanjang dimensi fitur
        z_i_norm = F.normalize(z_i, p=2, dim=1)
        z_j_norm = F.normalize(z_j, p=2, dim=1)

        # 2. Gabungkan representasi secara teratur: [2*B, D]
        # Urutan: [i_0, j_0, i_1, j_1, ..., i_{B-1}, j_{B-1}]
        representations = torch.empty(
            (2 * batch_size, z_i.size(1)), 
            dtype=z_i.dtype, 
            device=z_i.device
        )
        representations[0::2] = z_i_norm
        representations[1::2] = z_j_norm

        # 3. Hitung Matriks Similaritas Kosinus: [2*B, 2*B]
        similarity_matrix = torch.matmul(representations, representations.T)
        
        # Skalakan dengan temperatur
        similarity_matrix = similarity_matrix / self.temperature

        # 4. Konstruksi Masker untuk mengeliminasi similaritas diri sendiri (Self-similarity diagonal)
        diag_mask = torch.eye(2 * batch_size, dtype=torch.bool, device=z_i.device)
        similarity_matrix.masked_fill_(diag_mask, float('-inf'))

        # 5. Konstruksi Target Label
        # Pasangan indeks untuk 2k adalah 2k+1, dan untuk 2k+1 adalah 2k
        labels = torch.empty(2 * batch_size, dtype=torch.long, device=z_i.device)
        labels[0::2] = torch.arange(1, 2 * batch_size, 2, device=z_i.device)
        labels[1::2] = torch.arange(0, 2 * batch_size, 2, device=z_i.device)

        # 6. Komputasi Cross-Entropy Simetris
        loss = F.cross_entropy(similarity_matrix, labels, reduction='mean')
        return loss


class ContrastiveModelWrapper(nn.Module):
    """
    Arsitektur lengkap enkapsulasi Backbone dan Projection Head.
    """
    def __init__(self, backbone: nn.Module, feature_dim: int, projection_dim: int = 128) -> None:
        super().__init__()
        self.backbone = backbone
        self.projector = ProjectionHead(
            in_features=feature_dim, 
            hidden_dim=feature_dim, 
            out_features=projection_dim
        )

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Returns:
            h: Representasi backbone laten [B, feature_dim]
            z: Vektor proyeksi ternormalisasi [B, projection_dim]
        """
        h = self.backbone(x)
        # Flattening jika backbone menghasilkan tensor spasial (misal Conv2D)
        if h.dim() > 2:
            h = torch.flatten(h, start_dim=1)
        z = self.projector(h)
        return h, z


# =====================================================================
# Unit Execution Simulation & Validation Routine
# =====================================================================
if __name__ == "__main__":
    torch.manual_seed(42)
    
    # 1. Konfigurasi Parameter
    BATCH_SIZE = 16
    FEATURE_IN = 512
    PROJ_DIM = 128
    
    # 2. Inisialisasi Mock Backbone (Representasi ResNet penultimate layer)
    mock_backbone = nn.Sequential(
        nn.Linear(1024, FEATURE_IN),
        nn.BatchNorm1d(FEATURE_IN),
        nn.ReLU()
    )
    
    model = ContrastiveModelWrapper(
        backbone=mock_backbone, 
        feature_dim=FEATURE_IN, 
        projection_dim=PROJ_DIM
    )
    criterion = VectorizedInfoNCELoss(temperature=0.07)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)

    # 3. Dummy Augmented Input Batches [B, Feature]
    x_view1 = torch.randn(BATCH_SIZE, 1024)
    x_view2 = torch.randn(BATCH_SIZE, 1024)

    # 4. Forward Propagation
    model.train()
    optimizer.zero_grad()
    
    h1, z1 = model(x_view1)
    h2, z2 = model(x_view2)
    
    # 5. Evaluasi Loss & Backpropagation
    loss = criterion(z1, z2)
    loss.backward()
    optimizer.step()

    # Validasi Output
    print(f"[Verification Success]")
    print(f"-> Batch Size: {BATCH_SIZE}")
    print(f"-> Latent Representation (h1) Shape: {list(h1.shape)}")
    print(f"-> Projected Representation (z1) Shape: {list(z1.shape)}")
    print(f"-> InfoNCE Computed Loss Value: {loss.item():.4f}")
    
    assert not torch.isnan(loss), "Fatal: NaN terdeteksi pada InfoNCE loss computation!"
    assert z1.grad is None, "Z tensor gradient tidak boleh tertinggal secara detached."
```

---

### 7. Edge Cases & Failure Modes

Pada implementasi skala enterprise, kegagalan SSL jarang memunculkan pesan error eksplisit (*runtime exceptions*), melainkan degradasi tersembunyi (*silent performance degradation*):

#### 1. Representation Collapse (Keruntuhan Representasi)
*   **Gejala**: Nilai loss menurun tajam mendekati nol secara instan, namun akurasi *downstream task* setara dengan *random guessing*.
*   **Mekanisme**: Terjadi saat encoder $f_\theta$ memetakan seluruh input $x \in \mathcal{X}$ ke sebuah titik vektor konstan $z = c$ (*Complete Collapse*) atau membatasi varians representasi hanya pada sub-ruang berdimensi sangat rendah (*Dimensional Collapse*).
*   **Deteksi**:
    Hitung matriks kovarians representasi $C = \frac{1}{B} \sum_{i=1}^B (z_i - \bar{z})(z_i - \bar{z})^T$. Lakukan dekomposisi nilai eigen (*Eigenvalues* $\lambda_k$). Jika lebih dari $90\%$ varians terkonsentrasi pada rank $\ll d$, sistem mengalami *dimensional collapse*.
*   **Mitigasi**: Implementasikan regularisasi varians (seperti pada metode VICReg) atau pertahankan normalisasi batch eksplisit (*BatchNorm*) pada *projection head*.

#### 2. False Negative Sampling (Sampling Negatif Palsu)
*   **Gejala**: Model gagal membedakan fitur-fitur granular (*fine-grained representation degradation*).
*   **Mekanisme**: Di dalam batch berukuran besar (misal $B=4096$), probabilitas dua sampel independen memiliki kelas semantik yang sama meningkat signifikan. InfoNCE memperlakukan seluruh pasangan non-identik sebagai pasangan negatif, sehingga model secara keliru memaksa sampel dari kelas yang sama untuk saling menjauh.
*   **Mitigasi**: Gunakan *Debiased Contrastive Learning* (DCL) atau teknik *Positive Mining* berbasis ambang batas kemiripan kosinus awal.

#### 3. Instabilitas Numerik LogSumExp & Gradien Meledak
*   **Gejala**: Tensor menghasilkan nilai `NaN` atau `Inf` saat komputasi gradient descent.
*   **Mekanisme**: Perhitungan $\exp(z_i \cdot z_j / \tau)$ dengan $\tau$ kecil ($\tau \le 0.01$) memicu *floating-point arithmetic overflow* pada presisi float32.
*   **Mitigasi**: Terapkan *LogSumExp trick* secara matematis (subtraksi komponen skalar maksimum sebelum eksponensiasi). Implementasi PyTorch `F.cross_entropy` di atas telah mengintegrasikan komputasi ini secara native di level CUDA kernel.

---

### 8. Trade-offs & Alternatif Solusi

| Dimensi Parameter | Contrastive Learning (SimCLR / InfoNCE) | Memory Bank / Momentum (MoCo v2/v3) | Non-Contrastive (BYOL / SimSiam) | Information-Theoretic (Barlow Twins) | Masked Autoencoding (MAE) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Ketergantungan Batch Size** | **Sangat Tinggi** (Membutuhkan $B \ge 2048$ untuk hasil optimal) | **Rendah** (Memanfaatkan queue memory buffer terpisah) | **Rendah-Sedang** ($B \approx 256-512$) | **Sedang** | **Sangat Rendah** (Bekerja efektif pada batch standar) |
| **Kompleksitas Komputasi Loss** | $\mathcal{O}(B^2 \cdot D)$ | $\mathcal{O}(B \cdot K \cdot D)$ | $\mathcal{O}(B \cdot D)$ | $\mathcal{O}(D^2)$ | $\mathcal{O}(N \cdot D)$ di mana $N$ adalah jumlah patches |
| **Negative Pairs Required?** | **Wajib** | **Wajib** | **Tidak Perlu** (Menggunakan stop-gradient & predictor) | **Tidak Perlu** (Menggunakan decorrelation cross-correlation matrix) | **Tidak Perlu** (Reconstruction target) |
| **Kebutuhan Memori GPU** | Sangat Tinggi | Menengah (Tambahan memori untuk momentum encoder) | Moderat | Moderat | Rendah pada encoder, terpusat pada decoder |
| **Kesesuaian Data Domain** | Sangat baik untuk Citra, Tabular, Graf | Sangat baik untuk Citra, Multimodal | Sangat baik untuk Citra & Fitur Dense | Sangat baik untuk Tabular & Bioinformatika | Paling unggul pada Vision Transformer (ViT) & NLP |

---

### 9. Best Practices & Standar Industri

1. **Projection Head Lifecycle Isolation**:
   *   *Aturan Baku*: Jangan pernah mengekstraksi representasi downstream dari output *projection head* $z$.
   *   *Prosedur*: Setelah tahapan *pre-training* selesai, buang lapisan *projection head* $g_\phi(\cdot)$ secara permanen. Gunakan representasi laten backbone $h = f_\theta(x)$ sebagai basis *embedding space* atau input *downstream classifier*.
2. **Optimizer & Learning Rate Scheduling**:
   *   Saat melatih menggunakan ukuran batch masif ($B > 1024$), standar *Stochastic Gradient Descent* (SGD) atau Adam standar menyebabkan divergensi bobot awal. Gunakan **LARS** (Large Batch Optimization with Additive and Layer-wise Adaptive, Rule-scaled) atau **AdamW** dengan rasio *Linear Warmup* (10 epoch pertama) diikuti oleh *Cosine Annealing Learning Rate Decay*.
3. **Augmentation Policy Alignment**:
   *   Kualitas representasi berbanding lurus dengan independensi transformasi augmentasi. Bila memproses data gambar, kombinasi *Random Resized Crop* dan *Color Jittering* adalah keharusan mutlak. Jika salah satu dihilangkan, model akan mengeksploitasi celah trivial (*shortcut learning*) seperti histogram warna atau letak batas frame.
4. **Mixed-Precision Stability (FP16 vs BF16)**:
   *   Hindari komputasi normalisasi vektor dan matriks similaritas dalam format FP16 murni karena batas dinamisnya mudah terlampaui. Lakukan *casting* ke `torch.float32` tepat sebelum operasi matriks dot-product dan InfoNCE loss untuk mengeliminasi *underflow*.

---

### 10. Hands-on Lab Exercise

#### Skenario Lab
Anda bertindak sebagai Principal AI Scientist yang ditugaskan membangun model deteksi anomali pada fitur embedding representasi high-dimensional tabular-to-latent engine tanpa menggunakan label kelas yang ada.

#### Panduan Langkah demi Langkah

##### Langkah 1: Persiapan Lingkungan & Generator Data
Buat file `lab_representation.py` dan deklarasikan generator distribusi multi-manifold buatan:

```python
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset
import numpy as np

class SyntheticManifoldDataset(Dataset):
    """
    Menghasilkan data bersumber dari 3 sub-manifold non-linear 
    berdimensi 64 yang tertanam pada ruang 256-dimensi.
    """
    def __init__(self, n_samples: int = 4000) -> None:
        self.data = []
        samples_per_cluster = n_samples // 4
        
        for cluster_id in range(4):
            # Base manifold vector
            base = np.random.randn(256) * 0.1
            base[cluster_id * 64 : (cluster_id + 1) * 64] += 2.0
            
            # Tambahkan perturbasi non-linear
            cluster_data = base + np.random.randn(samples_per_cluster, 256) * 0.5
            self.data.append(cluster_data)
            
        self.data = np.vstack(self.data).astype(np.float32)
        np.random.shuffle(self.data)

    def __len__(self) -> int:
        return len(self.data)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        sample = self.data[idx]
        
        # Stokastik augmentasi 1: Random masking + gaussian noise
        noise_1 = np.random.normal(0, 0.05, size=sample.shape).astype(np.float32)
        mask_1 = np.random.binomial(1, 0.85, size=sample.shape).astype(np.float32)
        view_1 = (sample * mask_1) + noise_1
        
        # Stokastik augmentasi 2: Alternating mask + gaussian jitter
        noise_2 = np.random.normal(0, 0.08, size=sample.shape).astype(np.float32)
        mask_2 = np.random.binomial(1, 0.80, size=sample.shape).astype(np.float32)
        view_2 = (sample * mask_2) + noise_2
        
        return torch.tensor(view_1), torch.tensor(view_2)
```

##### Langkah 2: Konstruksi Arsitektur Encoder
Implementasikan backbone berbasis *Deep Residual MLP*:

```python
class ResidualBlock(nn.Module):
    def __init__(self, dim: int) -> None:
        super().__init__()
        self.fc = nn.Sequential(
            nn.Linear(dim, dim),
            nn.BatchNorm1d(dim),
            nn.LeakyReLU(0.2, inplace=True),
            nn.Linear(dim, dim),
            nn.BatchNorm1d(dim)
        )
        self.act = nn.LeakyReLU(0.2, inplace=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.act(x + self.fc(x))

class RepresentationBackbone(nn.Module):
    def __init__(self, input_dim: int = 256, latent_dim: int = 64) -> None:
        super().__init__()
        self.initial = nn.Sequential(
            nn.Linear(input_dim, 128),
            nn.BatchNorm1d(128),
            nn.LeakyReLU(0.2, inplace=True)
        )
        self.res1 = ResidualBlock(128)
        self.out_proj = nn.Linear(128, latent_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.initial(x)
        x = self.res1(x)
        return self.out_proj(x)
```

##### Langkah 3: Pre-training Loop dengan InfoNCE
Gunakan modul `VectorizedInfoNCELoss` dan `ProjectionHead` yang telah didefinisikan pada Bagian 6:

```python
def train_ssl_pipeline():
    dataset = SyntheticManifoldDataset(n_samples=2048)
    dataloader = DataLoader(dataset, batch_size=128, shuffle=True, drop_last=True)
    
    backbone = RepresentationBackbone(input_dim=256, latent_dim=64)
    model = ContrastiveModelWrapper(backbone=backbone, feature_dim=64, projection_dim=32)
    
    criterion = VectorizedInfoNCELoss(temperature=0.1)
    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-3, weight_decay=1e-5)
    
    epochs = 15
    print("Mulai Pre-training Self-Supervised Learning...")
    
    for epoch in range(1, epochs + 1):
        total_loss = 0.0
        for step, (v1, v2) in enumerate(dataloader):
            optimizer.zero_grad()
            _, z1 = model(v1)
            _, z2 = model(v2)
            
            loss = criterion(z1, z2)
            loss.backward()
            optimizer.step()
            
            total_loss += loss.item()
            
        avg_loss = total_loss / len(dataloader)
        if epoch % 3 == 0 or epoch == 1:
            print(f"Epoch [{epoch:02d}/{epochs:02d}] - InfoNCE Loss: {avg_loss:.5f}")
            
    return model.backbone

trained_backbone = train_ssl_pipeline()
```

##### Langkah 4: Evaluasi Linear Probing Protocol
Uji ketajaman representasi manifold laten dengan membekukan parameter (*freezing*) backbone dan melatih sebuah classifier regresi logistik linier sederhana:

```python
def linear_probing_evaluation(backbone: nn.Module):
    backbone.eval()
    for param in backbone.parameters():
        param.requires_grad = False  # Bekukan seluruh parameter
        
    # Generate data pengujian terpisah dengan label eksplisit
    np.random.seed(99)
    test_data, test_labels = [], []
    for cid in range(4):
        base = np.random.randn(256) * 0.1
        base[cid * 64 : (cid + 1) * 64] += 2.0
        cluster_samples = base + np.random.randn(200, 256) * 0.5
        test_data.append(cluster_samples)
        test_labels.append(np.full(200, cid))
        
    X = torch.tensor(np.vstack(test_data), dtype=torch.float32)
    y = torch.tensor(np.concatenate(test_labels), dtype=torch.long)
    
    # Ekstraksi representasi laten beku (h)
    with torch.no_grad():
        features = backbone(X)
        
    # Train Linear Classifier (Single Layer)
    linear_classifier = nn.Linear(features.size(1), 4)
    probe_criterion = nn.CrossEntropyLoss()
    probe_optimizer = torch.optim.Adam(linear_classifier.parameters(), lr=0.01)
    
    for _ in range(100):
        probe_optimizer.zero_grad()
        out = linear_classifier(features)
        loss = probe_criterion(out, y)
        loss.backward()
        probe_optimizer.step()
        
    # Evaluasi Akurasi Linear Probe
    with torch.no_grad():
        preds = linear_classifier(features).argmax(dim=1)
        accuracy = (preds == y).float().mean().item()
        
    print(f"\n==========================================")
    print(f"Linear Probing Top-1 Accuracy: {accuracy * 100:.2f}%")
    print(f"==========================================")
    assert accuracy > 0.90, "Gagal: Kualitas representasi laten di bawah ambang batas minimal 90%!"

linear_probing_evaluation(trained_backbone)
```

##### Kriteria Keberhasilan Praktikum:
1. Pipeline InfoNCE Loss menurun secara konvergen dan stabil tanpa osilasi destruktif atau nilai `NaN`.
2. Model tidak mengalami *collapse*, dibuktikan dengan *Linear Probe Classifier* yang menghasilkan akurasi downstream di atas $90\%$ pada representasi laten yang dibekukan (*frozen representation*).