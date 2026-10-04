# Kurikulum AI Red Teaming — Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Kategori:** 07-Quality-and-Security  
**Bab 04:** Data Extraction dan Model Inversion  
**Tingkat Kesulitan:** Advanced / Enterprise Staff Security Engineer  

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta didik enterprise diharapkan mampu:
1. **Membedah Secara Matematis Mekanisme Serangan Rekonstruksi:** Memahami formulasi optimasi *Model Inversion Attack* (MIA) dan *Likelihood Ratio Membership Inference Attack* (LiRA) pada tingkat distribusi probabilitas posterior dan gradien.
2. **Membangun Pipeline Eksfiltrasi Data Lanjutan:** Mengembangkan instrumen *Shadow Model Ensemble* dan algoritma optimasi berbasis *Generative Prior* (GAN/Diffusion) untuk mengekstrak data sensitif dari model *black-box* maupun *white-box*.
3. **Mendiagnosis Kerentanan Sistem Produksi:** Mengidentifikasi dan mengevaluasi kebocoran informasi (*leakage surface*) melalui *logits*, *temperature scaling*, *token probabilities*, dan *gradient checkpointing* pada inference API skala besar.
4. **Merancang Arsitektur Defensif Enterprise:** Mengimplementasikan mitigasi end-to-end berbasis *Differential Privacy* (DP-SGD/DP-Inference), *Top-k/Top-p filtering*, *Output Perturbation*, dan *Rényi Privacy Accounting* untuk membatasi kebocoran tanpa mendegradasi performa model secara destruktif.

---

## 2. Prerequisites

Peserta harus memiliki pemahaman mendalam pada domain berikut:
- **Matematika Lanjut & Probabilitas:** Optimasi berbasis gradien, Teorema Bayes, Kalkulus Peubah Banyak, Estimasi Densitas Kernel (KDE), dan *Hypothesis Testing* (Likelihood Ratio Test).
- **Deep Learning Frameworks:** Kemahiran tingkat lanjut dalam PyTorch (autograd, custom loss, hooks, distributed evaluation).
- **Konsep Keamanan AI Dasar:** Memahami *threat modeling* AI (White-box, Black-box, Gray-box), babak dasar *Membership Inference*, serta metrik privasi dasar ($\epsilon, \delta$-Differential Privacy).
- **Sistem Produksi Enterprise:** Pengalaman dengan REST/gRPC API, Triton Inference Server/TorchServe, dan arsitektur microservices Kubernetes.

---

## 3. Concept & Internal Architecture (Mendalam)

Data Extraction dan Model Inversion bukanlah serangan *brute-force* acak, melainkan rekayasa balik (*reverse engineering*) terpandu terhadap batas keputusan (*decision boundary*) dan *memorization surface* dari jaringan saraf tiruan.

### 3.1 Formulasi Matematis Model Inversion Attack (MIA)

Pada serangan *white-box* atau *surrogate-guided black-box*, penyerang merekonstruksi representasi fitur input $\hat{x}$ yang diasosiasikan dengan label target $y$ dengan memecahkan problem optimasi terbalik terhadap fungsi representasi model $f_\theta$:

$$\hat{x} = \arg\min_{x \in \mathcal{X}} \left( \mathcal{L}_{\text{task}}(f_\theta(x), y) + \lambda \mathcal{R}_{\text{prior}}(x) \right)$$

Di mana:
- $f_\theta: \mathcal{X} \to \mathbb{R}^K$ adalah model target dengan parameter $\theta$.
- $\mathcal{L}_{\text{task}}$ adalah fungsi rugi (misalnya *Cross-Entropy* atau *Cosine Distance* pada embedding space).
- $\mathcal{R}_{\text{prior}}(x)$ adalah *regularization prior* (seperti *Total Variation*, *Deep Inversion Batch-Norm Regularization*, atau *Latent Prior* dari pretrained GAN/Diffusion model) yang memaksa representasi hasil rekonstruksi tetap berada pada *manifold* data riil yang valid.
- $\lambda$ adalah skalar *hyperparameter balance*.

Jika model memiliki *Batch Normalization* ($BN$) layer, informasi statistik fitur training tersimpan langsung di dalam running mean ($\mu_l$) dan running variance ($\sigma_l^2$) pada setiap layer $l$. Penyerang white-box mengeksploitasi fitur ini menggunakan **DeepInversion Loss**:

$$\mathcal{R}_{BN}(x) = \sum_{l} \left( \|\mu_l(x) - \mu_l^{\text{target}}\|_2 + \|\sigma_l^2(x) - \sigma_l^{2,\text{target}}\|_2 \right)$$

### 3.2 Likelihood Ratio Attack (LiRA) pada Membership Inference

Metode Membership Inference tradisional hanya menggunakan ambang batas probabilitas posterior sederhana ($f_\theta(x)_y > \tau$). LiRA memformalkan serangan ini sebagai uji hipotesis statistik (*Neyman-Pearson Lemma*) menggunakan distribusi parametrik loss:

- $H_0$: Sampel data $(x, y)$ **bukan** merupakan anggota set training ($x \notin \mathcal{D}_{\text{train}}$).
- $H_1$: Sampel data $(x, y)$ **merupakan** anggota set training ($x \in \mathcal{D}_{\text{train}}$).

Penyerang melatih sekumpulan $K$ buah model bayangan (*Shadow Models*) $\theta_1, \dots, \theta_K$ pada subset acak dari data populasi. Untuk setiap sampel target $(x, y)$:
1. Hitung kerugian $\mathcal{L}(f_{\theta_k}(x), y)$ untuk semua model di mana $(x, y) \notin \mathcal{D}_{k,\text{train}}$ untuk mengestimasi distribusi non-anggota (*out-distribution*):

$$\Lambda_{\text{out}}(x, y) \sim \mathcal{N}\left(\mu_{\text{out}}(x), \sigma_{\text{out}}^2(x)\right)$$

2. Nilai skor LiRA dihitung melalui standard score Gaussian log-likelihood:

$$\text{Score}_{\text{LiRA}}(x, y) = \frac{\mathcal{L}(f_{\text{target}}(x), y) - \mu_{\text{out}}(x)}{\sigma_{\text{out}}(x) + \epsilon_{\text{stab}}}$$

Jika skor ini berada jauh di bawah nilai harapan $\mu_{\text{out}}$ (loss secara signifikan lebih kecil dari yang diprediksi oleh distribusi model *out*), maka $H_1$ diterima dengan tingkat kepercayaan tinggi.

```
       [ Populated Training Corpus ]
                    │
      ┌─────────────┴─────────────┐
      ▼                           ▼
[ Shadow Models (IN) ]   [ Shadow Models (OUT) ]
      │                           │
      ▼                           ▼
Loss Dist N(μ_in, σ_in)   Loss Dist N(μ_out, σ_out)
      └─────────────┬─────────────┘
                    ▼
          Likelihood Ratio (Λ)
                    │
                    ▼
   Decision: Target ∈ Training Set (True/False)
```

---

## 4. Why & What

### Mengapa Masalah Ini Menjadi Kritis di Tingkat Enterprise?
1. **Regulasi Perlindungan Data Global & Nasional:** UU PDP (Indonesia), GDPR (Uni Eropa), dan HIPAA (AS) mengklasifikasikan bobot model (*model weights*) sebagai representasi turunan dari data subjek. Rekonstruksi data PII (Personally Identifiable Information) atau data klinis dari sebuah model setara dengan insiden kebocoran data primer (*Data Breach Incident*).
2. **Ketergantungan Model Foundation & RAG:** Large Language Models (LLM) dan multimodal foundation models memiliki kapasitas memori sangat besar (*high-capacity memorization*). Tanpa kontrol ketat, serangan *Prefix Probing* mampu mengekstraksi rahasia dagang, token API, dan data rekam medis yang terdapat dalam dokumen *pre-training*.
3. **Penyusupan Intellectual Property (IP):** Melalui teknik model inversion, kompetitor dapat mengekstrak arsitektur fitur internal, representasi kimia obat, atau pola transaksi keuangan eksklusif tanpa menyentuh database operasional.

### Apa yang Diekstraksi?
- **Pixel-level Face Reconstruction:** Menghasilkan ulang wajah individu dari embedding sistem pengenalan wajah biometrik.
- **Exact Token Sequence Extraction:** Mengekstrak verbatim data training teks mentah (misal: "Nama: [X], NIK: [Y], Saldo: [Z]") via serangan ekstraksi prompt terarah.
- **Tabular Attribute Inference:** Mengembalikan kolom sensitif yang telah dihapus (misal: riwayat penyakit pada dataset asuransi) via eksploitasi korelasi multivariat.

---

## 5. How (Workflow Detail)

### 5.1 End-to-End Advanced Inversion Attack Pipeline

```
[Target Endpoint (Black-box)] 
      │ (Query x)
      ▼
[Logits/Probabilities Extraction]
      │
      ├─────────────────────────────────────────┐
      ▼                                         ▼
[Generative Prior (StyleGAN/Latent Diffusion)]  [Surrogate Model Evaluation]
      │                                         │
      ▼                                         ▼
[Latent Vector Optimization: z* = argmin L] ◄───[Gradient Approximator (SPSA/NES)]
      │
      ▼
[High-Fidelity Reconstructed Target Data]
```

1. **Reconnaissance & Boundary Probing:** Penyerang mengirim batch query sintetis terarah ke inference endpoint untuk mengamati distribusi softmax, temperature scaling, dan precision truncation (float32 vs float16).
2. **Surrogate Optimization Setup:** Jika API hanya mengembalikan top-1 label, penyerang memanfaatkan teknik optimasi *gradient-free* (*Natural Evolutionary Strategies* / NES atau *Simultaneous Perturbation Stochastic Approximation* / SPSA) untuk mengestimasi gradien lokal.
3. **Latent Space Exploration:** Alih-alih mengoptimasi pixel input secara langsung (yang menghasilkan gambar penuh noise/artefak), penyerang mencari representasi $z \in \mathcal{Z}$ di ruang laten generator (*Generative Prior*):
   $$\hat{z} = \arg\min_z \mathcal{L}(f_\theta(G(z)), y)$$
4. **Iterative Reconstruction & Refinement:** Melalui regularisasi ruang laten ($\|z\|_2$) dan *boundary alignment*, citra atau data tabular target disintesis hingga konvergen pada tingkat kemiripan semantik tinggi.

---

## 6. Analogy & Architecture Diagrams

### Analogi Kunci
Bayangkan model machine learning adalah seorang **arsitek forensik yang memiliki memori fotografis berlebih**.
- **Model Training Normal:** Arsitek mempelajari 10.000 sidik jari pelaku kriminal untuk menarik kesimpulan pola umum (lingkaran, lengkungan).
- **Overfitting & Memorization:** Arsitek secara tidak sengaja menghafal goresan luka mikro spesifik milik individu tertentu bernama "Budi".
- **Model Inversion:** Penyerang tidak membongkar brankas data training. Penyerang cukup bertanya berulang kali kepada sang arsitek: *"Bandingkan sketsa ini dengan ingatanmu tentang Budi. Apakah lebih mirip jika garis ini ditarik ke kiri atau ke kanan?"* Hingga akhirnya sketsa tersebut menjadi replika sempurna sidik jari asli Budi.

### Diagram Arsitektur Produksi: Vulnerability vs. Hardened Ingress

```
========================= ARSITEKTUR RENTAN (VULNERABLE) =========================
[Client/Attacker]
      │ HTTP POST /v1/predict (Input: x)
      ▼
[Inference Gateway] ──► [Model Runtime (PyTorch)]
                             │
                             ▼ Generates exact float32 outputs
                     [Softmax: [0.998231, 0.000124, 0.001645]]
                             │
[Full Probability Vector Exposed] ◄─────────────────────────────────────────────┘
*Penyerang dapat menghitung gradien halus (loss surface) untuk merekonstruksi data*

========================= ARSITEKTUR DEFENSIF (HARDENED) =========================
[Client/Attacker]
      │ HTTP POST /v1/predict (Input: x)
      ▼
[Inference Gateway]
      │
      ├──► [Privacy Budget Tracker (Redis)] ──► Exceeded? ──► [429 / Block API Key]
      │
      ▼
[Model Runtime] ──► [Raw Logits]
                         │
                         ▼
        [Top-K Truncation (k=1 or hard labels only)]
                         │
                         ▼
        [Differential Privacy Laplace/Gaussian Noise Perturbation]
                         │
                         ▼
        [Rounding / Precision Clamping (e.g. 2 decimal places)]
                         │
[Safe Response Payload] ◄┘
*Penyerang kehilangan informasi gradien mikro; optimasi inversi gagal konvergen*
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Conceptual Inversion via Gradient Descent (White-box)

Skrip edukatif berikut mengilustrasikan mekanisme dasar inversi representasi fitur input menggunakan model linear/neural network terisolasi:

```python
import torch
import torch.nn as nn
import torch.optim as optim

# 1. Definisikan model dummy yang telah dilatih
class SensitiveClassifier(nn.Module):
    def __init__(self):
        super().__init__()
        self.fc = nn.Linear(4, 2, bias=False)
        # Bobot diasumsikan merefleksikan atribut sensitif
        with torch.no_grad():
            self.fc.weight = nn.Parameter(torch.tensor([[2.5, -1.2, 3.0, 0.5],
                                                        [-2.0, 1.5, -0.5, 4.0]]))

    def forward(self, x):
        return self.fc(x)

target_model = SensitiveClassifier()
target_model.eval()

# 2. Setup Serangan: Rekonstruksi input x yang menghasilkan target class = 0
target_class = torch.tensor([0])
reconstructed_input = torch.randn(1, 4, requires_grad=True) # Inisialisasi acak
optimizer = optim.Adam([reconstructed_input], lr=0.1)
criterion = nn.CrossEntropyLoss()

# 3. Optimasi Rekonstruksi
for step in range(100):
    optimizer.zero_grad()
    output = target_model(reconstructed_input)
    loss = criterion(output, target_class)
    # Tambahkan L2 regularization untuk menjaga nilai input tetap realistis
    total_loss = loss + 0.01 * torch.norm(reconstructed_input, 2)
    total_loss.backward()
    optimizer.step()

print(f"Optimal reconstructed feature vector: {reconstructed_input.detach().numpy()}")
```

### 7.2 Practical Example: Enterprise Production-Grade LiRA Attack Engine & Defense Layer

Berikut adalah implementasi end-to-end berstandar industri:
1. **Engine Evaluasi LiRA (Attack Simulator):** Melatih shadow models, menghitung log-likelihood variance, dan mengevaluasi status keanggotaan.
2. **Defensive API Interceptor:** Lapisan mitigasi yang mengaburkan probabilitas prediksi via clipping, temperature-noise injection, dan label truncation.

```python
#!/usr/bin/env python3
"""
Enterprise Red Teaming: Likelihood Ratio Membership Inference Attack (LiRA)
& Production Defense Sanitizer.
Standar Keamanan: Python 3.10+, PyTorch 2.x
"""

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from scipy.stats import norm
from typing import Tuple, List, Dict

# ============================================================================
# 1. DOMAIN ARCHITECTURE: TARGET & SHADOW MODELS
# ============================================================================

class TargetClassificationModel(nn.Module):
    """Deep Neural Network yang mensimulasikan model analitik data enterprise."""
    def __init__(self, input_dim: int = 20, num_classes: int = 2):
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(input_dim, 64),
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, num_classes)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.network(x)

# ============================================================================
# 2. ADVERSARIAL ENGINE: LiRA (LIKELIHOOD RATIO ATTACK)
# ============================================================================

class LiRAEngine:
    """
    Engine untuk mengaudit kerentanan Membership Inference tingkat tinggi
    menggunakan distribusi logit out-of-model shadow ensemble.
    """
    def __init__(self, input_dim: int, num_shadow_models: int = 8):
        self.input_dim = input_dim
        self.num_shadow_models = num_shadow_models
        self.shadow_models: List[nn.Module] = []
        self.shadow_data_indices: List[np.ndarray] = []

    def train_shadow_models(self, population_data: torch.Tensor, population_labels: torch.Tensor):
        """Melatih ensemble model bayangan dengan sampling 50% data acak per model."""
        n_samples = population_data.size(0)
        criterion = nn.CrossEntropyLoss()

        for idx in range(self.num_shadow_models):
            # Split acak 50% bootstrap
            perm = np.random.permutation(n_samples)
            keep_idx = perm[: n_samples // 2]
            self.shadow_data_indices.append(keep_idx)

            shadow_model = TargetClassificationModel(input_dim=self.input_dim)
            optimizer = optim.AdamW(shadow_model.parameters(), lr=0.005, weight_decay=1e-4)

            x_train = population_data[keep_idx]
            y_train = population_labels[keep_idx]

            # Fit loop
            shadow_model.train()
            for _ in range(30):
                optimizer.zero_grad()
                out = shadow_model(x_train)
                loss = criterion(out, y_train)
                loss.backward()
                optimizer.step()

            shadow_model.eval()
            self.shadow_models.append(shadow_model)

    def compute_lira_score(
        self, 
        target_model: nn.Module, 
        x_eval: torch.Tensor, 
        y_eval: torch.Tensor
    ) -> float:
        """
        Menghitung parametric Likelihood-Ratio score untuk data sampel (x_eval, y_eval).
        """
        target_model.eval()
        with torch.no_grad():
            target_logit = target_model(x_eval.unsqueeze(0))
            target_prob = torch.softmax(target_logit, dim=-1)[0, y_eval].item()
            # Hindari saturasi logit numerik
            target_prob = np.clip(target_prob, 1e-12, 1.0 - 1e-12)
            target_metric = np.log(target_prob / (1.0 - target_prob))

        # Kumpulkan observasi loss dari shadow model di mana x_eval bertindak sebagai OUT-sample
        out_metrics = []
        for i, sm in enumerate(self.shadow_models):
            with torch.no_grad():
                out_logit = sm(x_eval.unsqueeze(0))
                prob = torch.softmax(out_logit, dim=-1)[0, y_eval].item()
                prob = np.clip(prob, 1e-12, 1.0 - 1e-12)
                phi = np.log(prob / (1.0 - prob))
                out_metrics.append(phi)

        out_metrics = np.array(out_metrics)
        mu_out = np.mean(out_metrics)
        std_out = np.std(out_metrics) + 1e-8

        # Hitung LiRA Score via Gaussian Survival Function Log-Likelihood
        lira_score = (target_metric - mu_out) / std_out
        return float(lira_score)

# ============================================================================
# 3. PRODUCTION DEFENSE PIPELINE (SANITIZER INTERCEPTOR)
# ============================================================================

class HardenedPredictionService:
    """
    Production-grade Inference Wrapper dengan Mitigasi Data Extraction.
    Fitur:
    1. Top-1 Hard Thresholding / Confidence Masking.
    2. Scaled Gaussian Noise pada Logits (Output Perturbation).
    3. Floating-point Truncation.
    """
    def __init__(self, raw_model: nn.Module, noise_scale: float = 0.15, return_hard_label: bool = False):
        self._model = raw_model
        self._noise_scale = noise_scale
        self._return_hard_label = return_hard_label

    def predict(self, x: torch.Tensor) -> Dict[str, object]:
        self._model.eval()
        with torch.no_grad():
            raw_logits = self._model(x)

            # Defensive Strategy 1: Hard Label (Zero confidence leak)
            if self._return_hard_label:
                predicted_class = torch.argmax(raw_logits, dim=-1).item()
                return {
                    "prediction": predicted_class,
                    "confidence": None,
                    "status": "SANITIZED_HARD_LABEL"
                }

            # Defensive Strategy 2: Differential Noise Perturbation pada Logits
            noise = torch.randn_like(raw_logits) * self._noise_scale
            perturbed_logits = raw_logits + noise

            # Defensive Strategy 3: Precision Truncation & Top-K Truncation
            probabilities = torch.softmax(perturbed_logits, dim=-1)
            sanitized_probs = torch.round(probabilities * 100.0) / 100.0

            return {
                "prediction": torch.argmax(sanitized_probs, dim=-1).item(),
                "probabilities": sanitized_probs.tolist(),
                "status": "SANITIZED_PERTURBED"
            }

# ============================================================================
# 4. VERIFIKASI & AUDIT EKSEKUSI
# ============================================================================

if __name__ == "__main__":
    torch.manual_seed(42)
    np.random.seed(42)

    INPUT_FEATURES = 16
    DATA_COUNT = 400

    # 1. Buat data sintetis target
    X_synthetic = torch.randn(DATA_COUNT, INPUT_FEATURES)
    # Korelasikan label dengan linear hyperplane sederhana + non-linear boundary
    Y_synthetic = (X_synthetic[:, 0] * 1.5 + X_synthetic[:, 1] ** 2 > 1.2).long()

    # 2. Definisikan subset Target Train vs Target Holdout (Non-Member)
    target_train_x = X_synthetic[:200]
    target_train_y = Y_synthetic[:200]
    
    target_test_x = X_synthetic[200:]
    target_test_y = Y_synthetic[200:]

    # 3. Latih model target dengan sedikit overfitting untuk demonstrasi kebocoran
    target_model = TargetClassificationModel(input_dim=INPUT_FEATURES)
    opt = optim.Adam(target_model.parameters(), lr=0.01)
    crit = nn.CrossEntropyLoss()

    for epoch in range(60):
        opt.zero_grad()
        loss = crit(target_model(target_train_x), target_train_y)
        loss.backward()
        opt.step()

    print("[*] Target Model Training Selesai.")

    # 4. Inisialisasi Shadow Attack Engine
    print("[*] Menjalankan Shadow Modeling LiRA...")
    lira_evaluator = LiRAEngine(input_dim=INPUT_FEATURES, num_shadow_models=10)
    lira_evaluator.train_shadow_models(X_synthetic, Y_synthetic)

    # 5. Uji Skor LiRA pada Member vs Non-Member
    # Mengambil Sampel Member (Target Train)
    member_idx = 5
    score_member = lira_evaluator.compute_lira_score(
        target_model, target_train_x[member_idx], target_train_y[member_idx]
    )

    # Mengambil Sampel Non-Member (Target Test)
    non_member_idx = 5
    score_non_member = lira_evaluator.compute_lira_score(
        target_model, target_test_x[non_member_idx], target_test_y[non_member_idx]
    )

    print(f"[AUDIT HASIL]")
    print(f" -> LiRA Score untuk Training Member Data:     {score_member:.4f}")
    print(f" -> LiRA Score untuk Out-of-Sample Non-Member: {score_non_member:.4f}")

    if score_member > score_non_member:
        print(" [!] VULNERABILITY DETECTED: Member model memiliki probabilitas posterior anomali.")

    # 6. Demonstrasi Defense Wrapper
    print("\n[*] Menjalankan Defensive Sanitizer Interceptor...")
    defense_service = HardenedPredictionService(target_model, noise_scale=0.25, return_hard_label=False)
    
    sample_input = target_train_x[member_idx].unsqueeze(0)
    sanitized_output = defense_service.predict(sample_input)
    print(f" -> Response Model Terproteksi: {sanitized_output}")
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Ekstraksi Rekam Medis pada Medical Diagnostic Assistant API
- **Entitas:** HealthTech Enterprise (AS/Uni Eropa).
- **Infrastruktur:** Jaringan saraf DenseNet-121 yang di-hosting pada AWS ECS + Triton Inference Server untuk mendeteksi kardiomegali dari citra X-Ray dada pasien.
- **Vektor Serangan:** Penyerang mengeksploitasi endpoint `/v1/predict` yang mengembalikan array floating-point presisi tinggi (`float32`, 7 digit desimal di belakang koma) tanpa rate limiting yang memadai.
- **Metodologi Eksploitasi:**
  1. Penyerang mengisolasi ID pasien tertentu dari metadata bocor pihak ketiga.
  2. Menggunakan metode optimasi berbasis momentum (DeepInversion terdistribusi) dan *image prior* dari set data citra rontgen publik.
  3. Mengarahkan loss rekonstruksi untuk mencocokkan distribusi feature maps internal melalui 150.000 request terjadwal (*distributed botnet*).
- **Dampak (Blast Radius):** Citra rontgen dada dapat direkonstruksi hingga tingkat kemiripan SSIM (*Structural Similarity Index*) > 0.81. Data implantasi alat pacu jantung pasien dan bentuk anatomi unik tampak jelas, mengakibatkan sanksi pelanggaran regulasi HIPAA sebesar $4.2M dan pembekuan layanan.
- **Root Cause:**
  1. Pengembalian logit mentah tanpa *temperature scaling* atau pemotongan desimal (*overprecision*).
  2. Model dilatih tanpa regularisasi *Differential Privacy* (DP-SGD).
  3. Tidak adanya detektor anomali distribusi input query (*query drift detector*) di tingkat API Gateway.

---

## 9. Trade-offs (Performance, Latency, Scalability, Cost)

| Parameter | Tanpa Pertahanan (Raw Outputs) | Output Perturbation (Gaussian/Laplace) | Top-1 / Top-k Label Masking | Differential Privacy Training (DP-SGD) |
| :--- | :--- | :--- | :--- | :--- |
| **Model Inversion Resistance** | Sangat Rendah | Sedang - Tinggi | Sangat Tinggi | Hampir Mutlak ($\epsilon \le 1.0$) |
| **Latency Overhead** | ~0 ms | +0.2 - 0.5 ms | < 0.1 ms | 0 ms (Waktu inferensi sama) |
| **Akurasi Model (Utility)** | 100% (Baseline) | 98.5% - 99.2% | 100% (Hanya label) | 88.0% - 95.0% (Tergantung $\epsilon$) |
| **Compute Training Overhead** | 1x (Baseline) | 1x | 1x | 3x - 10x (Per-sample gradient clipping) |
| **Integrasi Client Apps** | Sangat Fleksibel (Probabilitas lengkap) | Perlu toleransi fluktuasi probabilitas kecil | Memutus integrasi jika downstream butuh skor risiko | Transparan untuk inferensi |

---

## 10. Common Mistakes & Troubleshooting

### 1. Kesalahan Fatal: Menganggap HTTPS/mTLS Melindungi dari Model Inversion
- **Mistake:** Mengira bahwa mengenkripsi *data-in-transit* dengan TLS 1.3 menghentikan eksfiltrasi model.
- **Troubleshooting:** Model Inversion mengeksploitasi semantik output, bukan transmisi jaringan. Proteksi harus diterapkan pada *payload data plane*, bukan sekadar *transport layer*.

### 2. Over-Trusting Simple Rounding
- **Mistake:** Melakukan rounding probabilitas ke 2 angka desimal (`round(prob, 2)`), tetapi mengizinkan ratusan query rata-rata pada input yang sama yang ditambahkan sedikit noise (*Gaussian smoothing attacks*).
- **Troubleshooting:** Terapkan teknik *Deterministic Response Caching*. Jika dua query memiliki kemiripan cosinus fitur $> 0.999$, kembalikan respons yang sama secara deterministik tanpa menghitung ulang noise.

### 3. Kegagalan Memvalidasi BN Statistics pada White-Box Artifacts
- **Mistake:** Merilis checkpoint model (`.pt` / `.onnx`) yang menyertakan parameter `running_mean` dan `running_var` dari layer *Batch Normalization*.
- **Troubleshooting:** Jalankan sanitasi artefak model sebelum deployment:
  ```python
  for m in model.modules():
      if isinstance(m, nn.BatchNorm2d):
          m.reset_running_stats()
          m.track_running_stats = False
  ```
  Atau beralih sepenuhnya ke *Group Normalization* atau *Layer Normalization* selama fase pelatihan awal.

### 4. Mengabaikan Gradient Leaks pada Federated Learning
- **Mistake:** Berasumsi pengiriman gradien lokal dari node enterprise aman dari ekstraksi data mentah.
- **Troubleshooting:** Serangan DLG (*Deep Leakage from Gradients*) dapat merekonstruksi input piksel secara eksak hanya dari tensor gradien. Terapkan *Secure Multi-Party Computation* (SMPC) dan penambahan noise DP lokal sebelum transmisi gradien antar-node.

---

## 11. Best Practices (Production Checklist)

### Checklist Sebelum Deployment Model Produksi
- [ ] **Logit Hardening:** Pastikan endpoint API inferensi **tidak pernah** mengembalikan raw logit atau raw continuous probability vector kecuali mutlak diperlukan oleh sistem downstream terautentikasi.
- [ ] **Quantization & Truncation:** Batasi output kelas maksimal Top-K (disarankan $K \le 3$) dan bulatkan nilai konfidensi ke representasi desimal kasar.
- [ ] **Differential Privacy Guardrails:** Model yang dilatih pada data rahasia/PII wajib diaudit nilai $\epsilon$-nya via tools seperti *Opacus* (PyTorch DP-SGD). Pastikan privacy budget total $\epsilon < 3.0, \delta < 10^{-5}$.
- [ ] **Rate-Limiting Stateful Ingress:** Terapkan *Sliding-Window Token Bucket* di API Gateway (maksimum 100 query/menit per entitas API token/IP subnet).
- [ ] **Query Semantic Drift Monitoring:** Pantau jarak representasi input query client. Jika terdeteksi sekuens input berulang dengan pola mutasi optimasi (ciri khas serangan black-box NES/SPSA), putuskan koneksi secara preventif (*Circuit Breaker*).

---

## 12. Hands-on Practice

Buat direktori baru pada repositori lokal: `hands-on/m02/`

### Tugas Praktikum
1. **Langkah 1: Setup Lingkungan**
   Simpan kode pada Seksi 7.2 ke dalam `hands-on/m02/lira_attack_audit.py`.
2. **Langkah 2: Eksekusi Eksperimen Baseline**
   Jalankan skrip audit dengan variasi jumlah shadow models (coba $K=4, 8, 16$). Amati korelasi antara jumlah shadow models dan akurasi skor LiRA dalam membedakan member vs non-member.
3. **Langkah 3: Implementasi Pertahanan Baru (Temperature Softmax + Clamping)**
   Buka file dan buat kelas baru `CustomSoftmaxDefense` yang mengimplementasikan formula:
   $$P_{\text{defended}}(y_i) = \frac{\exp(z_i / T)}{\sum_j \exp(z_j / T)}$$
   dengan parameter temperatur dinamis $T \in [2.0, 5.0]$.
4. **Langkah 4: Evaluasi Ulang LiRA**
   Hubungkan pipeline inferensi target melalui kelas pertahanan baru tersebut, kemudian catat penurunan nilai LiRA score pada data training member. Pastikan LiRA score member mendekati nilai non-member (distribusi tidak dapat dibedakan).

---

## 13. Exercises

### Level Easy
Tuliskan skrip Python mandiri yang mengekstrak nilai representasi rata-rata fitur per kelas dari bobot linear classifier sederhana tanpa melakukan query inferensi sama sekali (Pure analytical white-box inversion).

### Level Medium
Implementasikan serangan *Black-box Model Inversion* berbasis optimasi NES (*Natural Evolutionary Strategies*) terhadap model yang hanya mengembalikan probabilitas output satu kelas (skalar float). Gunakan estimasi gradien beda hingga:
$$\nabla_x \mathbb{E}[f(x)] \approx \frac{1}{\sigma P} \sum_{i=1}^{P} \epsilon_i f(x + \sigma \epsilon_i)$$

### Level Hard
Rancang dan implementasikan custom PyTorch *Inference Hook* yang memonitor entropy output:
$$H(p) = -\sum_i p_i \log p_i$$
Jika entropy output berada di bawah ambang batas kritis tertentu (mengindikasikan memorisasi ekstrem/overconfidence pada titik target), hook tersebut secara otomatis menyuntikkan noise kalibrasi adaptif yang mempertahankan urutan ranking argmax tetapi meratakan kurva distribusi probabilitas.

---

## 14. Challenge

### Studi Kasus: "The Silent Health Predictor Breach"
Sebuah konsorsium perbankan dan asuransi jiwa meluncurkan sistem berbasis LLM + Multi-Task Tabular Model untuk memprediksi kemungkinan nasabah mengalami penyakit kritis dalam 12 bulan ke depan guna menetapkan premi polis.
- Sistem hanya menyediakan akses endpoint REST internal untuk staf underwriting.
- Output yang diberikan berupa: *Status Risiko* ("Rendah", "Sedang", "Tinggi") dan *Top 3 Atribut Kontributor Utama* (dihasilkan melalui integrasi model explainability SHAP).
- **Misi Red Team:** Anda tidak memiliki akses ke parameter bobot internal model (Black-box total) dan API tidak pernah memberikan probabilitas desimal numerik. Buatlah rancangan serangan *attribute inference* dan *membership inference* terstruktur yang memanfaatkan penjelasan fitur *SHAP values* untuk merekonstruksi riwayat diagnosis penyakit riil pasien tertentu dari korpus data pelatihan. Buktikan secara matematis mengapa *explainability output* (XAI) dapat menjadi saluran samping (*side-channel*) ekstraksi data yang jauh lebih berbahaya dibandingkan nilai probabilitas itu sendiri.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: Pemahaman Konseptual (Basic)
1. Apa perbedaan mendasar antara serangan *Membership Inference* dan *Model Inversion*?
2. Mengapa layer *Batch Normalization* pada model deep learning menjadi vektor kebocoran informasi yang kritis dalam skenario serangan white-box?
3. Pada pengujian LiRA, mengapa pendekatan *parametric loss modeling* (asumsi distribusi Gaussian) jauh lebih presisi dibandingkan metode thresholding probabilitas konvensional?
4. Apa peran dari *regularization prior* (seperti Total Variation loss) dalam algoritma optimasi Model Inversion?
5. Mengapa teknik sanitasi respon sederhana seperti pembulatan angka desimal tidak cukup untuk memitigasi serangan ekstraksi iteratif?

### Bagian B: Analisis & Arsitektur (Intermediate)
6. Bagaimana korelasi antara fenomena model *overfitting* (generalization gap) dengan keberhasilan serangan ekstraksi data training?
7. Jelaskan secara matematis bagaimana mekanisme *per-sample gradient clipping* pada algoritma DP-SGD membatasi kebocoran informasi pada setiap individu data training!
8. Dalam serangan rekonstruksi citra berbasis *Generative Prior*, apa keuntungan mengoptimasi vektor laten $z$ daripada mengoptimasi piksel gambar $x$ secara langsung?
9. Apa dampak implementasi *temperature scaling* yang terlalu tinggi ($T \to \infty$) terhadap fungsi utilitas sistem machine learning di lingkungan produksi?
10. Bagaimana mekanisme kerja deteksi anomali berbasis *Query Semantic Drift* dalam memutus siklus optimasi serangan black-box berbasis algoritma evolusioner?

### Bagian C: Skenario Kasus Produksi (Advanced)
11. **Skenario 1:** Tim audit red team Anda menemukan bahwa sebuah model rekomendasi internal mengekspos embedding representasi pengguna (vektor float 256 dimensi). Developer berargumen bahwa embedding tersebut aman karena bersifat non-invertible (searah). Bagaimana langkah teknis Anda membuktikan bahwa argumen developer tersebut keliru?
12. **Skenario 2:** Sebuah microservice inferensi model finansial mengalami lonjakan query 400% dari subnet IP tertentu. Pola payload menunjukkan bahwa input memiliki nilai mean yang identik namun ditambahkan variansi Gaussian mikro ($x' = x + \mathcal{N}(0, 10^{-4})$). Diagnosis jenis serangan yang sedang terjadi dan tentukan langkah mitigasi darurat pada layer API Gateway!
13. **Skenario 3:** Regulasi menuntut bahwa model machine learning yang diterapkan pada aplikasi kredit tidak boleh membocorkan status disabilitas nasabah. Walaupun fitur disabilitas telah dihapus dari data training, model inversion attack berhasil merekonstruksi status tersebut. Jelaskan mekanisme terjadinya *proxy leakage* ini dan rancang arsitektur audit pre-training untuk memvalidasi sanitasi data!

---

## 16. Summary

- **Model Inversion & Data Extraction** bukanlah anomali kebetulan, melainkan konsekuensi matematis dari kapasitas memorisasi model machine learning dan ketergantungan optimasi fungsi rugi terhadap batas keputusan data latih.
- **LiRA (Likelihood Ratio Attack)** merepresentasikan standar modern dalam membership inference dengan memanfaatkan distribusi statistik ensemble shadow models untuk mengevaluasi status keanggotaan sampel secara deterministik dan reliabel.
- Pertahanan terhadap serangan ekstraksi data tidak dapat diselesaikan hanya pada lapisan keamanan jaringan (seperti HTTPS atau API gateway standar). Sistem memerlukan pendekatan pertahanan berlapis:
  1. **Algoritmik:** Menggunakan DP-SGD selama proses pelatihan untuk memberikan garansi teoritis privasi matematis.
  2. **Intersepsi Inferensi:** Melakukan degradasi presisi terukur (*quantization, top-k truncating, noise injection*) untuk memutus ketersediaan informasi gradien.
  3. **Arsitektural:** Membatasi frekuensi query, mendeteksi drift pola kueri tak wajar, dan mencegah eksposur artifak internal model seperti statistik layer normalisasi.