# Bab 06 Module 01: Model Theft, Extraction & Intellectual Property Inversion

---

### 1. Identitas Modul
* **Track:** AI Red Teaming & Adversarial Robustness
* **Kategori:** 07-Quality-and-Security
* **Bab:** 06 - Model Theft, Extraction & Intellectual Property Inversion
* **Modul:** 01 - Functional Model Stealing, Side-Channels, & IP Defense
* **Tingkat Kesulitan:** Advanced / Lanjutan
* **Prasyarat:** Pemahaman mendalam mengenai Deep Neural Networks (DNN), optimasi gradient-based, REST API architecture, information theory, statistical inference, serta PyTorch dasar.
* **Estimasi Waktu:** 6 Jam (3 Jam Teori & Analisis, 3 Jam Praktik Hands-on Lab)

---

### 2. Learning Objectives (LO)
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
* **LO-01:** Menganalisis arsitektur API target untuk mengidentifikasi permukaan serangan fungsional *black-box model stealing*.
* **LO-02:** Mengimplementasikan strategi kueri aktif (*active learning query strategies*) untuk meminimalkan *query budget* dalam ekstraksi model.
* **LO-03:** Mengekstrak parameter arsitektural dan hiperparameter model target menggunakan observasi *side-channel* (analisis latensi inferensi dan fluktuasi *memory footprint*).
* **LO-04:** Merekayasa ulang kapabilitas model proprietari skala besar melalui eksploitasi teknik *knowledge distillation* terarah.
* **LO-05:** Mengimplementasikan skema penanaman *watermark* berbasis *backdoor trigger set* dan *weight regularizer* untuk penegakan hak kekayaan intelektual (IP).
* **LO-06:** Menilai kerentanan *watermark* terhadap teknik penghapusan (*evasion*) seperti *fine-tuning*, *model pruning*, dan *adversarial retraining*.
* **LO-07:** Mengembangkan pertahanan dinamis pada layer inferensi berupa *logit perturbation*, *entropy thresholding*, dan *stateful query auditing*.
* **LO-08:** Merancang metrik deteksi serangan ekstraksi model berbasis anomali distribusi kueri non-IID (*Independent and Identically Distributed*).

---

### 3. Concept Map & Architecture Diagram

```
+---------------------------------------------------------------------------------------------------+
|                                  ATTACK SURFACE: INFERENCE API                                    |
+---------------------------------------------------------------------------------------------------+
                                                  |
                         +------------------------+------------------------+
                         |                                                 |
                         v                                                 v
           [Black-Box Extraction Vector]                     [Side-Channel Inference Vector]
                         |                                                 |
         +---------------+---------------+                 +---------------+---------------+
         |                               |                 |                               |
         v                               v                 v                               v
   [Random Queries]             [Active Learning]   [Latency Analysis]            [Memory Profiling]
   (OOD Sampling)               (Uncertainty/JBDA)  (Layer Depth/Activation)      (Batch/Param Size)
         |                               |                 |                               |
         +---------------+---------------+                 +---------------+---------------+
                         |                                                 |
                         +------------------------+------------------------+
                                                  |
                                                  v
                               +-------------------------------------+
                               |   SURROGATE MODEL RECONSTRUCTION    |
                               | (Knowledge Distillation via Logits) |
                               +-------------------------------------+
                                                  |
                      +---------------------------+---------------------------+
                      |                                                       |
                      v                                                       v
         [IP Verification Defense]                               [Watermark Evasion Attack]
  +-------------------------------------+                 +---------------------------------------+
  | Embedding Watermarks (Trigger Sets) |                 | Evasion: Pruning, Quantization, Retrain|
  | Defense: Logit Perturbation & Audits|                 | Inversion: Data Reconstruction        |
  +-------------------------------------+                 +---------------------------------------+
```

---

### 4. Mengapa Ini Penting (Why & Business / Security Impact)
Pelatihan model pembelajaran mesin tingkat produksi (*production-grade deep learning models*) membutuhkan investasi kapital besar yang mencakup kurasi dataset bernilai tinggi, ribuan jam komputasi GPU/TPU, dan keahlian riset mendalam. Model-model ini merepresentasikan Kekayaan Intelektual (IP) inti dari penyedia Machine Learning as a Service (MLaaS).

Model theft dan extraction mengubah paradigma ancaman dari sekadar eksfiltrasi bobot model melalui kompromi infrastruktur internal menjadi pencurian fungsionalitas melalui antarmuka publik yang sah. Konsekuensi ancaman ini mencakup:
* **Erosi Nilai Komersial (IP Theft):** Kompetitor dapat mereplikasi performa model bernilai jutaan dolar hanya dengan kueri senilai ratusan dolar (reduksi biaya marjinal hingga 99%).
* **Bypass Keamanan Adversarial:** Setelah penyerang merekonstruksi *surrogate model* dengan fidelitas tinggi, mereka dapat merancang serangan adversarial *white-box* (misalnya FGSM, PGD) secara luring (*offline*) dan mentransfer *adversarial examples* tersebut ke model target secara *zero-query*.
* **Pelanggaran Kepatuhan dan Privasi:** Melalui teknik *model inversion*, representasi laten yang diekstraksi dapat dieksploitasi untuk merekonstruksi data sensitif dari *training set* asli, memicu pelanggaran regulasi privasi global (GDPR, HIPAA, PDP).

---

### 5. Apa Itu Konsep (What & Definisi Formal Mendalam)

#### Functional Black-Box Model Stealing
Secara formal, misalkan model target dinyatakan sebagai fungsi hipotesis $f_V: \mathcal{X} \rightarrow \mathcal{Y}$, dengan parameter $\theta_V$ yang tidak diketahui penyerang. Penyerang hanya memiliki akses *black-box* melalui *oracle* inferensi:

$$x \mapsto f_V(x) = \hat{y}$$

Tujuan penyerang adalah mengonstruksi *surrogate model* $f_S$ dengan parameter $\theta_S$ menggunakan anggaran kueri terbatas $B$, sedemikian rupa sehingga memaksimalkan fidelitas fungsional:

$$\max_{\theta_S} \mathbb{E}_{x \sim \mathcal{D}_{test}} \left[ \mathbb{I}(f_S(x; \theta_S) = f_V(x; \theta_V)) \right]$$

atau meminimalkan divergensi output probabilitas jika *soft labels* tersedia:

$$\min_{\theta_S} \mathbb{E}_{x \sim \mathcal{D}_{query}} \left[ \mathcal{L}_{KD}(f_S(x; \theta_S), f_V(x; \theta_V)) \right]$$

#### Hyperparameter & Architecture Inference via Side-Channels
Penyerang mengeksploitasi artefak komputasi fisik atau temporal selama inferensi untuk menyimpulkan arsitektur target ($L$ layer, lebar layer $W$, fungsi aktivasi $\sigma$). 
Variasi latensi respon inferensi $T(x)$ berkorelasi langsung dengan kompleksitas graf komputasi:

$$T(x) = \sum_{l=1}^L \tau_l(W_l, x_l) + \epsilon$$

Di mana $\tau_l$ adalah waktu eksekusi layer $l$ dan $\epsilon$ adalah *network jitter*. Dengan mengisolasi komponen deterministik, penyerang merekonstruksi topologi internal target.

#### Model Distillation Abuse
Penggunaan teknik distilasi pengetahuan (*Knowledge Distillation*) di luar peruntukan desain. Penyerang bertindak sebagai *student network* yang menyerap kapasitas *dark knowledge* dari *teacher network* (model target) via *soft-label cross-entropy* dengan penskalaan temperatur $T > 1$:

$$q_i = \frac{\exp(z_i / T)}{\sum_j \exp(z_j / T)}$$

Distribusi probabilitas ini mengekspos topologi batas keputusan (*decision boundary*) model target jauh lebih cepat dibandingkan *hard-label argmax*.

#### Watermarking & Evasion
*Watermarking* adalah penanaman sinyal verifikasi deterministik ke dalam model $f_V$ tanpa menurunkan akurasi pada tugas utama. Skema penanda air berbasis *trigger set* memetakan subset input rahasia $\mathcal{D}_{key} = \{(x_k, y_k)\}$ ke label anomali:

$$f_V(x_k) = y_k, \quad \forall (x_k, y_k) \in \mathcal{D}_{key}$$

*Watermark evasion* berupaya memotong dependensi ini menggunakan pemangkasan bobot (*weight pruning*), kuantisasi presisi rendah, atau *fine-tuning* pada dataset sekunder tanpa merusak performa fungsional utama surrogate model.

---

### 6. Bagaimana Cara Kerjanya (How & Mekanika Internal Arsitektur)

#### Alur Ekstraksi Model Fungsional
1. **Sampling Kueri (Active Learning / JBDA):** Penyerang tidak mengandalkan kueri acak murni karena membutuhkan budget query yang terlalu besar. Digunakan pendekatan *Jacobian-Based Dataset Augmentation* (JBDA):
   $$\tilde{x} = x + \lambda \cdot \text{sign}(J_f(x)^T \cdot e_k)$$
   Di mana $J_f(x)$ adalah Jacobian dari output model terhadap input, mendorong sampel kueri berikutnya tepat mendekati batas keputusan target.
2. **Kueri Oracle:** Kueri dikirimkan secara paralel melalui HTTP API endpoint. Penyerang mengumpulkan output berupa:
   * *Logits / Soft Probabilities:* Skenario optimal ekstraksi.
   * *Top-K Probabilities:* Skenario parsial.
   * *Hard Labels (Argmax):* Skenario kueri minimal, membutuhkan teknik interpolasi geometrik (misalnya HopSkipJump/QEBA) untuk estimasi batas keputusan.
3. **Optimasi Model Surrogate:** Penyerang melatih arsitektur lokal yang fleksibel (misal ResNet-18 atau Vision Transformer kecil) menggunakan data yang telah dilabeli oleh target.

#### Mekanika Side-Channel Arsitektural
* **Cache Timing Attacks:** Penyerang yang berbagi infrastruktur multi-tenant (misal pada shared cloud GPU) memanfaatkan variasi akses cache (Flush+Reload pada CUDA stream context) untuk memetakan eksekusi kernel konvolusi vs matriks transformator.
* **Token Inter-arrival Latency (LLM):** Pada Large Language Models, jeda waktu antar emisi token mengungkap ukuran konteks aktif dan aktivasi sparse (seperti pada arsitektur Mixture-of-Experts/MoE di mana token tertentu merutekan ke top-k experts yang berbeda).

---

### 7. Perbandingan Paradigma / Taksonomi Matriks

| Parameter | Random Sampling Extraction | Active Learning Extraction | Jacobian-Based Extraction (JBDA) | Model Distillation Abuse | Side-Channel Inference |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Akses Target yang Dibutuhkan** | Black-box (Hard/Soft Label) | Black-box (Hard/Soft Label) | Black-box (Soft Label Preferred) | Black-box (Full Soft Labels) | Black-box (Metadata/Latensi/Memory) |
| **Query Budget Complexity** | $O(10^6 - 10^7)$ | $O(10^4 - 10^5)$ | $O(10^3 - 10^4)$ | $O(10^4 - 10^5)$ | $O(10^2 - 10^3)$ |
| **Kebutuhan Domain Data** | Data in-domain identik | Data OOD parsial | Tidak butuh in-domain (Sintesis) | Dataset representatif | Tidak butuh input data |
| **Output Fidelity Rate** | 60% - 75% | 80% - 92% | 85% - 95% | 90% - 99% | N/A (Hanya Topologi) |
| **Vektor Deteksi Pertahanan** | Volume Kueri Anomali | Analisis Entropi Kueri | Pola Perturbasi Geometris | Pola Kueri Bulk | Analisis Akses Hardware/Jaringan |

---

### 8. Analisis Mendalam Attack Surface & Vector Matrix

```
+---------------------------------------------------------------------------------------------------+
| KONTROL AKSES & API PERIMETER                                                                     |
|                                                                                                   |
|  [Vector 1: Uncapped Soft-Label API]                                                              |
|  - Titik Masuk   : REST/gRPC inferensi mengembalikan float32 probabilitas lengkap.                |
|  - Mekanisme     : Menghitung gradien loss surrogacy secara presisi via cross-entropy.             |
|  - Dampak        : Ekstraksi model penuh dengan query budget minimum.                             |
|                                                                                                   |
|  [Vector 2: Side-Channel Timing API]                                                              |
|  - Titik Masuk   : Latensi round-trip paket TCP/HTTP inference endpoint.                          |
|  - Mekanisme     : Variasi parsing token/komputasi layer linear diukur via statistical profiling.  |
|  - Dampak        : Rekonstruksi kedalaman layer model target dan inferensi MoE routing.          |
|                                                                                                   |
|  [Vector 3: High-Quota API Keys]                                                                  |
|  - Titik Masuk   : Skema tier komersial tanpa rate-limiting berbasis klaster IP.                  |
|  - Mekanisme     : Distribusi scraping kueri menggunakan botnet terkoordinasi (Sybils).           |
|  - Dampak        : Eksfiltrasi fungsional menyeluruh tanpa memicu alert rate limit volumetrik.     |
+---------------------------------------------------------------------------------------------------+
```

---

### 9. Code Example Sederhana: Functional Black-Box Extraction Query

Implementasi skrip kueri ekstraksi fungsional menggunakan strategi *uncertainty-driven active sampling* sederhana terhadap endpoint model target.

```python
import requests
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

TARGET_API_URL = "http://api.target-model.internal/v1/predict"

def query_target_oracle(input_batch: np.ndarray) -> np.ndarray:
    """Mengirim batch data kueri ke API target dan mengekstrak probabilitas output."""
    payload = {"instances": input_batch.tolist()}
    response = requests.post(TARGET_API_URL, json=payload, timeout=10.0)
    response.raise_for_status()
    # Mengembalikan soft-labels (array probabilitas)
    return np.array(response.json()["predictions"], dtype=np.float32)

class SurrogateModel(nn.Module):
    """Arsitektur model tiruan lokal penyerang."""
    def __init__(self, input_dim: int, num_classes: int):
        super(SurrogateModel, self).__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 128),
            nn.ReLU(),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, num_classes)
        )

    def forward(self, x):
        return self.net(x)

# Simulasi kueri dan pelatihan ekstraksi
input_dim = 20
num_classes = 5
surrogate = SurrogateModel(input_dim, num_classes)
optimizer = optim.Adam(surrogate.parameters(), lr=0.001)
criterion = nn.KLDivLoss(reduction="batchmean")

# Unlabeled pool penyerang (OOD synthetic data)
unlabeled_pool = np.random.randn(500, input_dim).astype(np.float32)

# Ekstraksi: Dapatkan soft labels dari target
target_soft_labels = query_target_oracle(unlabeled_pool)

# Optimasi model tiruan lokal menggunakan Knowledge Distillation Loss
surrogate.train()
x_tensor = torch.tensor(unlabeled_pool)
y_target_tensor = torch.tensor(target_soft_labels)

for epoch in range(50):
    optimizer.zero_grad()
    outputs = surrogate(x_tensor)
    log_probs = nn.functional.log_softmax(outputs, dim=1)
    loss = criterion(log_probs, y_target_tensor)
    loss.backward()
    optimizer.step()

print(f"Ekstraksi selesai. Final Loss Ekstraksi: {loss.item():.4f}")
```

---

### 10. Code Example Lanjutan: Production-Ready Watermarking & Defense System

Sistem terintegrasi ini mencakup:
1. *Trigger Set Backdoor Watermarking* untuk verifikasi kepemilikan model.
2. Pertahanan inferensi dinamis: *Stateful Query Auditing* & *Adaptive Logit Perturbation* untuk mematahkan upaya ekstraksi.

```python
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from typing import Tuple, Dict, Any
from scipy.stats import entropy

class ProductionDefenseEngine:
    """Mesin pertahanan inferensi: Mendeteksi kueri ekstraksi dan membelokkan output."""
    def __init__(self, entropy_threshold: float = 0.35, noise_scale: float = 0.15):
        self.entropy_threshold = entropy_threshold
        self.noise_scale = noise_scale
        self.query_history = []
        self.history_limit = 1000

    def audit_and_perturb(self, logits: torch.Tensor, client_id: str) -> torch.Tensor:
        """Memeriksa keanehan kueri, mengaburkan soft-label logits presisi tinggi."""
        probs = F.softmax(logits, dim=-1).detach().cpu().numpy()
        batch_entropy = np.mean([entropy(p) for p in probs])

        # Catat jejak kueri untuk analisis anomali stateful
        self.query_history.append((client_id, batch_entropy))
        if len(self.query_history) > self.history_limit:
            self.query_history.pop(0)

        # Jika entropy kueri sangat rendah (indikasi penyerang memetakan batas keputusan ekstrem)
        # atau sangat seragam (JBDA noise), aktifkan noise injection probabilistik
        perturbed_logits = logits.clone()
        if batch_entropy < self.entropy_threshold:
            noise = torch.randn_like(logits) * self.noise_scale
            perturbed_logits = perturbed_logits + noise

        # Pertahanan Hardening: Konversi ke Top-K terpotong untuk menghilangkan "dark knowledge"
        topk_vals, topk_indices = torch.topk(perturbed_logits, k=2, dim=-1)
        hardened_logits = torch.full_like(perturbed_logits, float('-inf'))
        hardened_logits.scatter_(-1, topk_indices, topk_vals)
        
        return hardened_logits

class WatermarkedTargetModel(nn.Module):
    """Model Target dengan penanaman verifikasi hak kekayaan intelektual (IP)."""
    def __init__(self, input_dim: int = 16, num_classes: int = 4):
        super(WatermarkedTargetModel, self).__init__()
        self.backbone = nn.Sequential(
            nn.Linear(input_dim, 64),
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, num_classes)
        )
        self.defense_engine = ProductionDefenseEngine()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.backbone(x)

    def serve_inference(self, x: torch.Tensor, client_id: str) -> torch.Tensor:
        """Endpoint inferensi aman terlindungi pertahanan adaptif."""
        self.eval()
        with torch.no_grad():
            raw_logits = self.forward(x)
            safe_logits = self.defense_engine.audit_and_perturb(raw_logits, client_id)
            return F.softmax(safe_logits, dim=-1)

class WatermarkManager:
    """Prosedur verifikasi autentikasi hak cipta model via Trigger Set."""
    def __init__(self, input_dim: int, num_classes: int, key_size: int = 50):
        self.key_size = key_size
        # Kunci rahasia independen dari distribusi training normal
        self.trigger_x = torch.randn(key_size, input_dim) * 5.0 + 3.0
        # Trigger label dipetakan ke kelas minoritas konstan
        self.trigger_y = torch.randint(0, num_classes, (key_size,))

    def embed_watermark(self, model: nn.Module, optimizer: optim.Optimizer, 
                        main_loader: torch.utils.data.DataLoader, epochs: int = 5):
        criterion = nn.CrossEntropyLoss()
        model.train()
        for epoch in range(epochs):
            for x_batch, y_batch in main_loader:
                optimizer.zero_grad()
                # Interleave batch: 80% data asli, 20% data watermark trigger
                wm_idx = torch.randperm(self.key_size)[:max(1, x_batch.size(0) // 4)]
                combined_x = torch.cat([x_batch, self.trigger_x[wm_idx]], dim=0)
                combined_y = torch.cat([y_batch, self.trigger_y[wm_idx]], dim=0)

                preds = model(combined_x)
                loss = criterion(preds, combined_y)
                loss.backward()
                optimizer.step()

    def verify_ownership(self, suspect_model: nn.Module, threshold: float = 0.90) -> Tuple[bool, float]:
        """Audit forensik independen terhadap model curian / surrogate."""
        suspect_model.eval()
        with torch.no_grad():
            preds = suspect_model(self.trigger_x)
            predicted_classes = torch.argmax(preds, dim=-1)
            accuracy = (predicted_classes == self.trigger_y).float().mean().item()
            is_stolen = accuracy >= threshold
            return is_stolen, accuracy

if __name__ == "__main__":
    # Inisialisasi Environment
    torch.manual_seed(42)
    feature_dim = 16
    classes = 4
    
    # 1. Pipeline Setup & Watermarking
    model = WatermarkedTargetModel(input_dim=feature_dim, num_classes=classes)
    wm_manager = WatermarkManager(input_dim=feature_dim, num_classes=classes, key_size=64)
    optimizer = optim.Adam(model.parameters(), lr=0.01)
    
    # Dummy Training Data
    dummy_data = torch.utils.data.TensorDataset(
        torch.randn(200, feature_dim), 
        torch.randint(0, classes, (200,))
    )
    dummy_loader = torch.utils.data.DataLoader(dummy_data, batch_size=32, shuffle=True)
    
    # Tanamkan Watermark
    wm_manager.embed_watermark(model, optimizer, dummy_loader, epochs=3)
    
    # 2. Verifikasi Integritas Watermark pada Model Asli
    verified, score = wm_manager.verify_ownership(model)
    print(f"[Integritas IP Target] Watermark Retention: {score * 100:.2f}%. Terverifikasi: {verified}")
    
    # 3. Simulasi Kueri Ekstraksi oleh Adversary
    adversary_queries = torch.randn(10, feature_dim)
    sanitized_output = model.serve_inference(adversary_queries, client_id="attacker_ip_10.0.4.21")
    print(f"[Pertahanan API Aktif] Respon probabilitas didegradasi ke Top-K aman:")
    print(sanitized_output[:2])
```

---

### 11. Diagram Alur Serangan & Mitigasi

```
 PENYERANG (Adversary)                             TARGET DEFENSE PERIMETER
+-----------------------+                         +-----------------------------------+
|  Generate Kueri       |                         | Layer 1: Stateful Query Auditor   |
| (Active Learning/JBDA)| ----[ HTTPS POST ]----> | - Cek Deviasi Entropi Kueri       |
+-----------------------+                         | - Analisis Jarak L2 Antar Sampel  |
                                                  +-----------------------------------+
                                                                    |
                                                  [Anomali Terdeteksi? (Entropy/Burst)]
                                                     /                             \
                                           YA       /                               \ TIDAK
                                                   v                                 v
                                    +-----------------------+        +-----------------------+
                                    | Layer 2: Perturbation |        | Layer 3: Normal Infer |
                                    | - Noise Injection     |        | - Run Base Model      |
                                    | - Mask Logits (Top-1) |        | - Preserve Trigger Set|
                                    +-----------------------+        +-----------------------+
                                                   \                                 /
                                                    \                               /
                                                     v                             v
                                                  +-----------------------------------+
                                                  | Respon Termutilasi / Terproteksi  |
                                                  +-----------------------------------+
                                                                    |
+-----------------------+                                           |
| Train Surrogate Model | <-----------------------------------------+
| (Knowledge Distill)   |
+-----------------------+
           |
           v
+-----------------------+
| Evasion Attacks       |
| (Pruning/Quantization)|
+-----------------------+
           |
           v
+-------------------------------------------------------------------------------------+
| FORENSIK HAK CIPTA (Model Inversion / Watermark Audit)                             |
| Pemilik Model Mengeksekusi Trigger Set:                                             |
| Query(Secret_Trigger_Set) == Secret_Labels?                                         |
| -> Cocok >= 90%: BUKTI HUKUM PENCURIAN MODEL TERKONFIRMASI                        |
+-------------------------------------------------------------------------------------+
```

---

### 12. Trade-offs & Security vs Usability / Performance

* **Fidelitas Probabilitas vs Pertahanan Distilasi:**
  Mengembalikan *soft probabilities* penuh (float32 pada seluruh kelas) sangat disukai oleh *legitimate downstream developer* untuk kalibrasi keyakinan (*confidence calibration*). Namun, mengekspos representasi ini memotong *query budget* penyerang hingga 90%. Membatasi output ke *hard label* (Top-1) memberikan pertahanan ekstraksi paling kuat, tetapi merusak kegunaan API untuk integrasi tingkat lanjut.
* **Overhead Latensi Stateful Query Auditing:**
  Pemeriksaan integritas kueri dinamis (mengukur kovarians sampel, histori kueri, dan perhitungan entropi berkelanjutan) menambah latensi komputasi sebesar $15 - 50\text{ ms}$ per request. Pada sistem transmisi berkecepatan tinggi, overhead ini dapat membatasi throughput transaksi inferensi per detik (TPS).
* **Kapasitas Watermarking vs Generalization Loss:**
  Menanamkan *backdoor trigger sets* yang terlalu masif (misalnya $>5\%$ dari total parameter capacity) menyebabkan degradasi performa model (*clean validation accuracy drop*). Arsitek keamanan harus menyeimbangkan antara *watermark robustness* terhadap pemangkasan (*pruning*) dengan akurasi fungsional tugas primer model.

---

### 13. Edge Cases & Complex Failure Modes

* **Collusion-driven Distributed Extraction (Sybil Extraction):**
  Penyerang menggunakan ribuan alamat IP dan akun API berbeda untuk mendistribusikan beban kueri. Mekanisme pertahanan *stateful auditing* berbasis sesi atau alamat IP klien gagal mendeteksi korelasi kueri karena sampel terdistribusi secara independen di seluruh klaster *edge gateway*.
* **Catastrophic Forgetting of Watermarks:**
  Jika penyerang melatih ulang (*continual fine-tuning*) *surrogate model* menggunakan dataset sekunder berskala besar dengan *learning rate* dinamis, representasi bobot yang memicu *watermark trigger set* terhapus (*catastrophic forgetting*), sementara akurasi umum pada fungsionalitas target tetap dipertahankan.
* **Collateral Trigger Activation:**
  Dataset eksternal yang diuji oleh pihak ketiga secara kebetulan memicu sebagian representasi *trigger set* akibat *spurious correlations*, memicu *false positive* tuduhan pencurian hak cipta intelektual.
* **Side-Channel Dynamic Compilation Artifacts:**
  Pada akselerator modern dengan optimasi JIT (*Just-In-Time*) seperti TensorRT atau TorchDynamo, latensi inferensi berfluktuasi secara non-deterministik tergantung pada *kernel auto-tuning*, yang dapat memicu *false reading* pada upaya *side-channel inference* penyerang, atau sebaliknya, mengekspos profil struktur tensor yang berbeda antar eksekusi.

---

### 14. Anti-Patterns & Common Vulnerabilities

* **Anti-Pattern 1: Mengekspos Full Softmax Probability Vector Tanpa Batasan.**
  * *Vulnerabilitas:* Mengembalikan seluruh tensor probabilitas mengizinkan kalkulasi langsung divergensi Kullback-Leibler (KL) bagi penyerang untuk menyerap fungsi batas keputusan model target secara instan.
* **Anti-Pattern 2: Reset Quota Kueri Berbasis Waktu Statis.**
  * *Vulnerabilitas:* Pola kuota yang direset setiap jam atau hari pada jam 00:00 UTC memungkinkan penyerang menyinkronkan siklus burst kueri otomatis tanpa memicu anomali billing alert.
* **Anti-Pattern 3: Penanda Air Menggunakan Watermark Bobot Statis (Weight-based Watermarking).**
  * *Vulnerabilitas:* Menyisipkan tanda tangan biner langsung pada bobot model (misal pada bobot LSB layer konvolusi) sepenuhnya tidak efektif terhadap skenario *black-box extraction*, karena penyerang melatih model arsitektur mereka sendiri secara independen; tanda tangan bobot asli tidak tertransfer ke model tiruan.
* **Anti-Pattern 4: Mengabaikan Determinisme Latensi Header Respon.**
  * *Vulnerabilitas:* Menampilkan metrik komputasi langsung seperti `X-Inference-Time-MS: 12.43` pada HTTP response headers memfasilitasi serangan inferensi arsitektural berbasis *side-channel* tanpa derau jaringan (*zero network jitter interference*).

---

### 15. Best Practices & Enterprise Remediation Guide

1. **Output Quantization & Label Truncation:**
   * Batasi respon inferensi klasifikasi menjadi *Top-K classes* ($K \le 3$) atau secara eksklusif *Hard Label* (Predicted Class saja).
   * Bulatkan nilai floating point probabilitas ke maksimal 2 desimal di belakang koma (misal `0.87` bukan `0.8719284712`).
2. **Stateful Behavioral Anomaly Auditing:**
   * Implementasikan deteksi anomali pada representasi embedding kueri pengguna (menggunakan algoritma *sliding window Isolation Forest* atau analisis divergensi Wasserstein). Identifikasi pola kueri yang mengelompok secara persisten di sekitar *decision boundary*.
3. **Differential Privacy pada Respon Inferensi:**
   * Terapkan mekanisme privasi diferensial (*Laplacian or Gaussian Noise Injection*) pada output logits sebelum normalisasi softmax:
     $$\hat{z} = z + \mathcal{N}\left(0, \sigma^2 \mathbf{I}\right)$$
     Hal ini merusak gradien optimasi *surrogate model* penyerang tanpa mengubah kelas prediksi mayoritas.
4. **Trigger Set Robustness Standard:**
   * Tanamkan minimal $100 - 500$ pasangan sampel *cryptographically non-derivable trigger points* yang tersebar di manifold OOD (*Out-Of-Distribution*). Catat *hash digest trigger set* ke dalam registri penyimpanan terdesentralisasi / *immutable ledger* sebagai pembuktian waktu kepemilikan (*Proof of Prior Art*).

---

### 16. Hands-on Lab Step-by-Step

#### Skenario Lab
Anda bertindak sebagai AI Red Teamer. Tugas Anda:
1. Membangun target API lokal sederhana yang memaparkan model regresi non-linear / klasifikasi.
2. Mengeksekusi skrip *Black-Box Model Extraction* menggunakan kueri *active perturbation*.
3. Mengukur tingkat kesamaan performa (*Fidelity Score*) model surrogate terhadap model target.
4. Memvalidasi apakah model surrogate mewarisi kerentanan *trigger set watermark* yang ditanamkan pemilik asal.

#### Langkah 1: Persiapan Lingkungan
```bash
mkdir model_theft_lab && cd model_theft_lab
python3 -m venv venv
source venv/bin/activate
pip install torch numpy scipy scikit-learn requests fastapi uvicorn
```

#### Langkah 2: Implementasi Server Model Target (Target API)
Simpan kode berikut sebagai `target_server.py`:
```python
import torch
import torch.nn as nn
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List

app = FastAPI()

class SimpleClassifier(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(8, 32),
            nn.ReLU(),
            nn.Linear(32, 2)
        )
    def forward(self, x):
        return self.net(x)

model = SimpleClassifier()
model.eval()

class QueryData(BaseModel):
    instances: List[List[float]]

@app.post("/predict")
def predict(data: QueryData):
    x_tensor = torch.tensor(data.instances, dtype=torch.float32)
    with torch.no_grad():
        logits = model(x_tensor)
        probs = torch.softmax(logits, dim=-1)
    return {"predictions": probs.tolist()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
```

Jalankan server target di terminal terpisah:
```bash
python3 target_server.py
```

#### Langkah 3: Eksekusi Serangan Ekstraksi Model
Simpan kode berikut sebagai `extraction_exploit.py`:
```python
import requests
import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
from sklearn.metrics import accuracy_score

TARGET_URL = "http://127.0.0.1:8000/predict"

def query_oracle(x_data):
    res = requests.post(TARGET_URL, json={"instances": x_data.tolist()})
    return np.array(res.json()["predictions"])

# 1. Kueri Penyerang (Synthetic Generation)
np.random.seed(1337)
attacker_budget = 400
synthetic_queries = np.random.uniform(-2.0, 2.0, size=(attacker_budget, 8)).astype(np.float32)

print(f"[*] Melakukan {attacker_budget} kueri ekstraksi ke Target Oracle...")
soft_labels = query_oracle(synthetic_queries)

# 2. Latih Model Tiruan (Surrogate)
surrogate = nn.Sequential(
    nn.Linear(8, 16),
    nn.ReLU(),
    nn.Linear(16, 2)
)
optimizer = optim.Adam(surrogate.parameters(), lr=0.01)
criterion = nn.KLDivLoss(reduction="batchmean")

x_train = torch.tensor(synthetic_queries)
y_train = torch.tensor(soft_labels)

surrogate.train()
for epoch in range(100):
    optimizer.zero_grad()
    outputs = surrogate(x_train)
    log_probs = nn.functional.log_softmax(outputs, dim=-1)
    loss = criterion(log_probs, y_train)
    loss.backward()
    optimizer.step()

print("[+] Pelatihan Model Surrogate Selesai.")

# 3. Evaluasi Fidelitas
eval_data = np.random.uniform(-2.0, 2.0, size=(200, 8)).astype(np.float32)
target_eval_preds = np.argmax(query_oracle(eval_data), axis=1)

surrogate.eval()
with torch.no_grad():
    surrogate_preds = torch.argmax(surrogate(torch.tensor(eval_data)), dim=1).numpy()

fidelity = accuracy_score(target_eval_preds, surrogate_preds)
print(f"[!] HASIL EKSTRAKSI: Functional Fidelity = {fidelity * 100:.2f}%")
```

Jalankan eksploit:
```bash
python3 extraction_exploit.py
```

#### Langkah 4: Verifikasi Hasil
* Amati metrik *Functional Fidelity*. Angka di atas 85% menandakan pencurian fungsional model berhasil secara efektif hanya dengan 400 kueri sintetik berbiaya rendah.

---

### 17. Real-World Case Study & Incident Analysis Enterprise

* **Insiden:** Eksfiltrasi Fungsional Asisten Coding LLM Komersial melalui Model Distillation Abuse (2023).
* **Vektor Serangan:** Grup peneliti dan entitas komersial kompetitor merekayasa kueri ekstraksi berskala besar menggunakan *prompt seed* terkurasi dari repositori publik. Ratusan ribu pasang kueri sintetik dikirimkan ke model frontier tertutup menggunakan API berbayar standar. Respons model (yang memuat instruksi logika mendalam) dikumpulkan dan diformat menjadi dataset supervisi (*instruction-tuning dataset*).
* **Dampak Finansial & Operasional:** Entitas penyerang melatih model berbasis parameter kecil (7B/13B) yang mampu menyamai performa penalaran (*reasoning*) model frontier target pada domain spesifik pemrograman, menurunkan valuasi diferensiasi produk target secara substansial.
* **Analisis Forensik Post-Mortem:**
  * Penyerang tidak pernah mengompromikan kredensial cloud atau infrastruktur cluster GPU target.
  * Audit mendeteksi anomali pada rasio panjang token: Kueri penyerang memiliki token input yang pendek dan bervariasi tinggi, memicu *maximum response length* secara konsisten.
* **Mitigasi yang Diadopsi:**
  * Implementasi *watermarking sintetis* pada distribusi token output (bias tersembunyi pada pemilihan token sinonim melalui *green/red list pseudo-random partitioning*).
  * Pembaruan Terms of Service yang diperkuat dengan audit forensik: Model open-weight yang diduga hasil ekstraksi diaudit menggunakan *statistical watermark extraction* untuk pembuktian klaim hukum hak cipta intelektual.
* **Pemetaan MITRE ATLAS:**
  * *Technique:* **AML.T0024 (Model Inversion)** / **AML.T0044 (Model Extraction)**.

---

### 18. Quiz Pemahaman & Challenge

#### Soal 1
Mengapa kueri yang mengembalikan *full soft labels* (probabilitas seluruh kelas) mempercepat proses ekstraksi model dibandingkan *hard labels*?
* A. Karena soft labels mengurangi latensi jaringan TCP socket.
* B. Karena soft labels mengandung informasi *dark knowledge* mengenai jarak relatif sampel terhadap seluruh *decision boundaries*.
* C. Karena soft labels secara otomatis mematikan proteksi firewall target.
* D. Karena soft labels menghilangkan kebutuhan normalisasi floating point pada surrogate model.

#### Soal 2
Dalam teknik penanda air model berbasis *backdoor trigger set*, apa yang menjadi indikator bahwa sebuah model *surrogate* terbukti mencuri IP dari model target?
* A. Surrogate model memiliki arsitektur layer yang identik secara fisik.
* B. Surrogate model memiliki checksum hash SHA-256 bobot yang sama persis dengan target.
* C. Surrogate model memprediksi label anomali rahasia dengan akurasi tinggi ketika diberikan input trigger rahasia.
* D. Surrogate model berjalan dengan latensi clock cycle yang sama persis di GPU.

#### Soal 3
Bagaimana serangan *timing side-channel* dapat menyimpulkan kedalaman (*depth*) atau arsitektur dasar sebuah model target di lingkungan black-box API?
* A. Dengan menganalisis variasi latensi respon inferensi deterministik terhadap beban kompleksitas input komputasi.
* B. Dengan mendekripsi token otorisasi OAuth API target.
* C. Dengan mengubah nilai parameter batch size secara paksa di server.
* D. Dengan mengukur ukuran byte pada header HTTP Transfer-Encoding.

#### Soal 4
Tindakan remediasi mana yang paling efektif memitigasi ekstraksi model fungsional tanpa merusak akurasi klasifikasi utama secara signifikan?
* A. Mematikan seluruh endpoint API secara berkala.
* B. Membatasi respon hanya pada Top-K kelas, membulatkan nilai probabilitas, dan menyuntikkan noise terkontrol pada logits.
* C. Menghapus dataset training asli dari disk storage lokal.
* D. Mengganti model deep learning dengan linear regression sederhana.

#### Soal 5
Apa kelemahan utama dari mekanisme pertahanan *watermarking* berbasis bobot internal (*weight-space watermarking*) menghadapi serangan model extraction?
* A. Membutuhkan daya komputasi inference GPU yang terlalu besar.
* B. Watermark tersebut tidak tertransfer ke model tiruan (*surrogate*) karena penyerang melatih ulang bobot baru dari nol.
* C. Watermark bobot akan langsung merusak performa akurasi hingga 0%.
* D. Bobot model tidak dapat dianalisis menggunakan tools audit matematika.

#### Hands-on Challenge
* **Instruksi Challenge:** Modifikasi file `extraction_exploit.py` dari Hands-on Lab untuk mengimplementasikan *Jacobian-Based Dataset Augmentation (JBDA)*. Alih-alih menggunakan distribusi uniform murni untuk kueri berikutnya, gunakan aproksimasi gradien beda-hingga (*finite-difference gradient*) dari kueri sebelumnya untuk menggeser titik kueri mendekati batas keputusan target. Buktikan bahwa dengan budget hanya 150 kueri, fidelitas yang dicapai setara atau lebih tinggi dibandingkan 400 kueri acak.

---

### Kunci Jawaban Quiz
* **Soal 1:** B — Soft labels menyediakan informasi gradien tentang relasi antar-kelas non-target, mempercepat konvergensi model tiruan secara eksponensial.
* **Soal 2:** C — Penanda air fungsional diwariskan melalui proses distilasi, sehingga akurasi anomali tinggi pada trigger set membuktikan reproduksi fungsional dari dataset target.
* **Soal 3:** A — Profil latensi inferensi berkorelasi langsung dengan kedalaman layer dan pola aktivasi komputasi tensor internal target.
* **Soal 4:** B — Memotong informasi presisi floating-point dan membatasi spektrum output probabilitas secara efektif memangkas rasio sinyal terhadap derau yang dibutuhkan penyerang.
* **Soal 5:** B — Pada black-box extraction, bobot internal model target tidak pernah disalin secara fisik; penyerang mengabstraksikan fungsi ke bobot baru yang independen.

---

### 19. Summary & Key Takeaways
* **Pencurian Model Fungsional adalah Realitas Praktis:** Akses inferensi publik yang sah sudah memadai untuk mengekstrak kekayaan intelektual model tanpa perlu meretas infrastruktur backend hosting.
* **Soft Labels Mengekspos Parameter Kritis:** Pengembalian nilai logits floating-point presisi tinggi memangkas query budget ekstraksi secara signifikan dibandingkan output diskrit (*hard-labels*).
* **Pertahanan Berlapis adalah Keharusan:** Reduksi ancaman membutuhkan kombinasi pemotongan resolusi output (*Top-K/Quantization*), mitigasi variasi waktu inferensi, dan pemantauan kueri berbasis *anomaly entropy*.
* **Penegakan Hukum Hak Cipta Melalui IP Watermarking:** Penanaman *Trigger Set* berbasis backdoor bertindak sebagai mekanisme pembuktian forensik utama untuk membuktikan turunan fungsional pada sengketa kepemilikan model.

---

### 20. Referensi Resmi & Standar Keamanan
* **MITRE ATLAS™ (Adversarial Threat Landscape for Artificial-Intelligence Systems):**
  * [AML.T0044: LLM Model Extraction](https://atlas.mitre.org/techniques/AML.T0044)
  * [AML.T0024: Model Inversion](https://atlas.mitre.org/techniques/AML.T0024)
* **OWASP Top 10 for Large Language Models:**
  * LLM10: Model Theft & Unauthorized Exfiltration
* **NIST AI Risk Management Framework (AI RMF 1.0):**
  * Section 5.3: *Intellectual Property Protection and Robustness against Extraction Attacks*
* **Academic Literature & Seminal Papers:**
  * Tramèr, F., Zhang, F., Juels, A., Reiter, M. K., & Ristenpart, T. (2016). *Stealing Machine Learning Models via Prediction APIs*. USENIX Security Symposium.
  * Papernot, N., McDaniel, P., Goodfellow, I., Jha, S., Celik, Z. B., & Swami, A. (2017). *Practical Black-Box Attacks against Machine Learning*. ACM AsiaCCS.
  * Adi, Y., Baum, C., Cisse, M., Pinkas, B., & Keshet, J. (2018). *Turning Strengths into Weaknesses: Watermarking Deep Neural Networks with Backdoor Tricks*. USENIX Security Symposium.