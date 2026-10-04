# Bab 03 Modul 01: Evasion & Multimodal Adversarial Perturbations

---

## 1. Identitas Modul

* **Track:** AI Red Teaming & Adversarial Robustness
* **Kategori:** 07-Quality-and-Security
* **Bab:** 03 — Evasion & Multimodal Adversarial Perturbations
* **Tingkat Kesulitan:** Advanced / Lanjutan
* **Prasyarat:**
  * Pemahaman mendalam tentang kalkulus multivariat (vektor gradien, turunan parsial).
  * Pemahaman arsitektur Deep Neural Networks (CNN, Vision Transformers/ViT, Cross-Attention Transformer, Audio Spectrogram Transformer).
  * Pengalaman praktis dengan *deep learning frameworks* (PyTorch/TensorFlow).
  * Pengetahuan dasar tentang representasi tokenisasi teks dan *embedding space*.
* **Estimasi Waktu Penyelesaian:** 8 Jam (Teori, Bedah Algoritma, dan Hands-on Lab)

---

## 2. Learning Objectives

Setelah menyelesaikan modul ini, praktisi keamanan dan arsitek AI diharapkan mampu:

* **LO-01:** Menjelaskan formulasi matematis dari optimasi *adversarial evasion* berbasis norma $L_p$ ($L_0, L_2, L_\infty$).
* **LO-02:** Mengimplementasikan dan membandingkan mekanisme kalkulasi perturbasi pada metode FGSM, PGD, dan Carlini-Wagner (C&W).
* **LO-03:** Menganalisis kelemahan struktural pada arsitektur Vision-Language Models (VLM) terhadap vektor injeksi adversarial visual (*Vision-Language Jailbreak*).
* **LO-04:** Mengidentifikasi dan mengeksploitasi anomali representasi fitur pada *Audio Adversarial Injections* terhadap model *Automatic Speech Recognition* (ASR).
* **LO-05:** Mengisolasi kegagalan tokenisasi visual terhadap *typographic attacks* pada model berbasis CLIP dan arsitektur multimodal kontemporer.
* **LO-06:** Merancang dan mengevaluasi ketahanan *Physical-World Adversarial Patches* dengan memperhitungkan transformasi fisik (*Expectation Over Transformation* - EOT).
* **LO-07:** Membangun arsitektur mitigasi defensif mencakup *Adversarial Training*, *Input Transformation*, dan *Multimodal Safety Classifiers*.
* **LO-08:** Melakukan audit komprehensif terhadap model multimodal enterprise menggunakan kerangka kerja evaluasi adversarial berstandar industri.

---

## 3. Concept Map & Architecture Diagram

```
                                +---------------------------------------------------+
                                |      Multimodal Adversarial Attack Vectors        |
                                +---------------------------------------------------+
                                                          |
         +--------------------------------+---------------+-------------------------------+
         |                                |                                               |
         v                                v                                               v
+------------------+            +-------------------+                           +-------------------+
|  Computer Vision |            | Audio Processing  |                           | Multimodal / VLM  |
+------------------+            +-------------------+                           +-------------------+
  |           |                   |               |                               |               |
  | (L_p Norm)| (Spatial/Physical)| (Psychoacoustic) (CTC/Transducer)             | (Cross-Modal) | (Semantic)
  v           v                   v               v                               v               v
[FGSM/PGD]  [Adversarial]       [Auditory Masking] [Targeted ASR]              [Visual Prompt]  [Typographic]
[Carlini-W] [Patches (EOT)]     [Perturbations]    [Evasion]                   [Jailbreaking]   [Token Clashing]
  |               |                   |               |                               |               |
  +---------------+-------------------+---------------+-------------------------------+---------------+
                                                          |
                                                          v
                                        +-----------------------------------+
                                        |   Defensive Hardening Layer       |
                                        +-----------------------------------+
                                        | - Adversarial Training (Min-Max)  |
                                        | - Randomized Smoothing            |
                                        | - Input Pre-processing/Diffusion  |
                                        | - Cross-Attention Sanity Check    |
                                        +-----------------------------------+
```

---

## 4. Mengapa Ini Penting

Evolusi kecerdasan buatan dari model unimodal (*narrow deep learning*) menuju model fondasi multimodal (*multimodal foundation models*) memperluas bidang sasaran penyerangan (*attack surface*). Serangan *evasion* tidak lagi terbatas pada klasifikasi gambar digital sederhana, melainkan mencakup subversi sistem kendali otonom, sistem verifikasi biometrik audio, hingga pemintasan pagar pengaman (*guardrail jailbreaking*) pada model komputasi multimodal tingkat lanjut.

Secara operasional dan bisnis, kerentanan terhadap perturbasi adversarial menghadirkan konsekuensi kritis:
* **Integritas Sistem Otonom:** Serangan *adversarial patch* fisik pada rambu lalu lintas atau sensor LiDAR dapat memicu kegagalan persepsi objek pada *autonomous vehicles*.
* **Bypass Kebijakan Konten & Guardrail Enterprise:** Pelaku dapat menyuntikkan instruksi manipulatif melalui noise imperseptibel pada citra (*vision jailbreak*), memintas filter keamanan berbasis teks murni yang diandalkan oleh sistem LLM enterprise.
* **Spoofing Autentikasi Suara:** Modulasi frekuensi tak terdengar pada sinyal audio memungkinkan injeksi perintah kontrol tanpa disadari oleh operator (*hidden voice commands*).
* **Kegagalan Verifikasi Identitas & Fraud:** Pemalsuan dokumen atau identitas fisik dengan menyisipkan pola *typographic* atau noise teroptimasi yang memanipulasi ekstraksi fitur OCR/VLM pada pipeline KYC (*Know Your Customer*).

---

## 5. Definisi Formal Mendalam

### 5.1 Adversarial Evasion
Adversarial evasion adalah proses optimasi terarah untuk menghasilkan input $\tilde{x} = x + \delta$ sedemikian rupa sehingga:

$$\arg\max_{y'} f(\tilde{x}) \neq \arg\max_{y} f(x) \quad \text{dengan syarat} \quad \|\delta\|_p \le \epsilon$$

Di mana:
* $f: \mathcal{X} \to \mathbb{R}^k$ adalah model klasifikasi/skor target.
* $x \in \mathcal{X}$ adalah input asli, dan $y$ adalah label yang benar.
* $\delta$ adalah vektor perturbasi adversarial.
* $\|\cdot\|_p$ melambangkan norma $L_p$ ($p \in \{0, 2, \infty\}$) yang membatasi jarak antara input asli dan input adversarial.
* $\epsilon$ adalah anggaran perturbasi (*perturbation budget*).

### 5.2 Norma Metrik Perturbasi ($L_p$)
* **Norma $L_\infty$:** Mengukur deviasi absolut maksimum pada setiap komponen input tunggal:
  $$\|\delta\|_\infty = \max_i |\delta_i|$$
* **Norma $L_2$:** Mengukur jarak Euclidean standar antara $x$ dan $\tilde{x}$:
  $$\|\delta\|_2 = \sqrt{\sum_i \delta_i^2}$$
* **Norma $L_0$:** Mengukur jumlah elemen atau fitur yang diubah:
  $$\|\delta\|_0 = \#\{i \mid \delta_i \neq 0\}$$

### 5.3 Vision-Language Jailbreak
Kondisi ketika komponen representasi visual $E_v(I)$ dari model $VLM(I, T)$ dipetakan ke dalam ruang semantik representasi teks $E_t(T)$ sedemikian rupa sehingga menghasilkan vektor aktivasi laten yang membatalkan instruksi penolak pada *system prompt*.

---

## 6. Mekanika Internal Arsitektur

### 6.1 Gradient-Based Evasion Mechanics

```
                       Forward Pass
       x ----------> [ Model Layer 1..N ] ----------> Loss J(theta, x, y)
                            |                                |
                            | Backward Pass (Gradients)      |
                            +--------------------------------+
                                           |
                                  nabla_x J(theta, x, y)
                                           |
                                           v
                             Perturbation Generator:
                     delta = epsilon * sign(nabla_x J)  (FGSM)
                                           |
                                           v
                        x_adv = Clip(x + delta, [0, 1])
```

#### Fast Gradient Sign Method (FGSM)
FGSM memanfaatkan aproksimasi linear lokal dari fungsi *loss* $J(\theta, x, y)$ di sekitar input $x$. Algoritma mengambil satu langkah besar sepanjang arah kenaikan gradien (gradient ascent):

$$\tilde{x} = x + \epsilon \cdot \text{sign}\left(\nabla_x J(\theta, x, y)\right)$$

Metode ini efisien secara komputasi ($\mathcal{O}(1)$ *backward pass*), namun rentan terhadap *gradient masking* dan sub-optimal untuk ruang optimasi non-linear yang kompleks.

#### Projected Gradient Descent (PGD)
PGD menyelesaikan masalah optimasi konstrain secara iteratif dengan memproyeksikan kembali hasil langkah gradien ke dalam *ball* $L_p$ beradius $\epsilon$ yang berpusat pada $x$:

$$x^{t+1} = \Pi_{x + \mathcal{S}} \left( x^t + \alpha \cdot \text{sign}\left(\nabla_{x^t} J(\theta, x^t, y)\right) \right)$$

Di mana $\Pi$ adalah operator proyeksi, $\alpha$ adalah ukuran langkah (*step size*), dan $\mathcal{S} = \{\delta \mid \|\delta\|_p \le \epsilon\}$. PGD bertindak sebagai algoritma *first-order adversary* terkuat di dalam batas linearitas lokal.

#### Carlini & Wagner (C&W) Attack
C&W mereformulasikan konstrain jarak $L_p$ bukan sebagai batasan kaku, melainkan sebagai penalti regularisasi dalam fungsi objektif:

$$\min_\delta \|\delta\|_2^2 + c \cdot f(x + \delta)$$

Fungsi objektif $f(x')$ dirancang sedemikian rupa sehingga $f(x') \le 0$ jika dan hanya jika model salah mengklasifikasikan sampel:

$$f(x') = \max\left( \max_{i \neq t} Z(x')_i - Z(x')_t, -\kappa \right)$$

Di mana $Z(x')$ adalah nilai *logit*, $t$ adalah target kelas yang diinginkan, dan parameter $\kappa$ mengontrol tingkat keyakinan (*confidence*) dari misklasifikasi. Variabel substitusi $\delta = \frac{1}{2}(\tanh(w) + 1) - x$ digunakan untuk secara inheren mempertahankan batasan domain nilai piksel $[0, 1]$.

### 6.2 Vision-Language Jailbreak Mechanics
Arsitektur VLM kontemporer (seperti LLaVA, BLIP-2, GPT-4V) mengintegrasikan *vision encoder* (umumnya ViT) dengan *Large Language Model* menggunakan lapisan proyeksi linear atau *cross-attention adapter*.

1. **Alignment Cross-Modal:** *Vision encoder* memetakan citra ke dalam *token embeddings* visual $V = [v_1, v_2, ..., v_k]$.
2. **Gradient Alignment Exploitation:** Penyerang menghitung gradien terhadap embedding visual untuk menyelaraskan representasi visual dengan token terlarang (*forbidden concept* $T_{harm}$) atau token penentu afirmatif ("*Sure, here is how to...*").
3. **Surpassing Guardrails:** Karena guardrail teks beroperasi pada masukan string teks mentah, vektor aktivasi visual berbahaya lolos dari filter pra-inferensi dan memaksa *decoder* bahasa menghasilkan respon yang melanggar batasan etika/kebijakan.

### 6.3 Audio Adversarial Mechanics
Pemrosesan audio digital mengubah domain waktu $x(t)$ menjadi domain frekuensi melalui *Short-Time Fourier Transform* (STFT) untuk menghasilkan spektrogram.
* **Psychoacoustic Masking Threshold:** Telinga manusia memiliki batas sensitivitas frekuensi dinamis. Sinyal audio berkekuatan tinggi pada frekuensi tertentu menutupi (*masking*) suara dengan intensitas lebih rendah di pita frekuensi yang berdekatan.
* **Attack Formulation:** Penyerang menambahkan perturbasi $\delta(t)$ pada domain waktu sedemikian rupa sehingga spektrum daya $\delta(t)$ berada tepat di bawah *masking threshold* $\theta(f)$, namun secara drastis mengubah representasi fitur Mel-Frequency Cepstral Coefficients (MFCC) atau matriks representasi pada model berbasis *Connectionist Temporal Classification* (CTC) atau enkoder *Conformer*.

### 6.4 Typographic Attacks on Visual Tokenizers
ViT dan arsitektur pengenalan visual berbasis *zero-shot* (seperti CLIP) mengonseptualisasikan objek melalui integrasi spasial fitur semantik.
* **Token Dominance:** Ketika teks eksplisit ditempatkan di atas suatu objek (misal: label kertas bertuliskan "iPod" ditempelkan pada buah apel), representasi lapisan atensi translasional dari *Text-Vision projection layer* memberikan bobot perhatian yang jauh lebih tinggi pada fitur ortografis/karakter teks dibandingkan fitur tekstur dan bentuk alami objek.
* Akibatnya, token semantik visual tertimpa (*overridden*) oleh token linguistik yang diekstraksi dari kanal visual yang sama.

### 6.5 Physical-World Adversarial Patches
Serangan digital konvensional gagal saat diaplikasikan di dunia nyata karena variasi jarak, sudut kamera, pencahayaan, dan distorsi optik. Kerangka kerja *Expectation Over Transformation* (EOT) mengatasi kendala ini dengan mengoptimalkan perturbasi patch $P$ terhadap distribusi transformasi lingkungan $\mathcal{T}$:

$$\arg\min_P \mathbb{E}_{t \sim \mathcal{T}} \left[ \mathcal{L}(f(t(x, P)), y^*) \right]$$

Di mana $t \sim \mathcal{T}$ mencakup rotasi acak, penskalaan, variasi kecerahan (*color jittering*), dan distorsi perspektif.

---

## 7. Perbandingan Paradigma / Taksonomi Matriks

| Parameter | FGSM | PGD | Carlini-Wagner (C&W) | Physical Patch (EOT) | Typographic Attack |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Akses Model** | White-box | White-box | White-box (bisa transfer) | Black/White-box | Black-box |
| **Norma Optimasi** | $L_\infty$ | $L_\infty, L_2$ | $L_2, L_0, L_\infty$ | Spatial Unconstrained | Semantic/Contextual |
| **Kompleksitas Komputasi** | $\mathcal{O}(1)$ | $\mathcal{O}(K)$ iterasi | $\mathcal{O}(K \times N)$ langkah | $\mathcal{O}(K \times |\mathcal{T}|)$ iterasi | $\mathcal{O}(1)$ manual / heuristic |
| **Perturbasi Terlihat?** | Sering terlihat jika $\epsilon$ tinggi | Minim / Halus | Sangat imperseptibel | Sangat terlihat (terlokalisasi) | Sangat terlihat |
| **Ketahanan di Dunia Nyata**| Sangat Rendah | Rendah | Nol (rentan noise fisik) | Sangat Tinggi | Sangat Tinggi |
| **Target Modalitas** | Citra / Audio | Citra / Audio | Citra / Audio | Kamera Fisik / LiDAR | VLM / OCR-Pipeline |
| **Efektivitas Bypass Guardrail** | Rendah | Menengah | Tinggi | Menengah | Sangat Tinggi |

---

## 8. Analisis Mendalam Attack Surface & Vector Matrix

```
+-----------------------------------------------------------------------------------------+
|                               Attack Surface Vector Matrix                              |
+---------------------+-------------------------+--------------------+--------------------+
| Vektor Serangan     | Komponen Target         | Mekanisme Primer   | Dampak Eksploitasi |
+---------------------+-------------------------+--------------------+--------------------+
| Unconstrained       | Vision Encoder ViT /    | Optimasi Gradien   | Evasion filter NSFW|
| Pixel Perturbation  | Convolutional Backbone  | norma L_inf via PGD| / deteksi malware  |
+---------------------+-------------------------+--------------------+--------------------+
| Visual Instruction  | Vision-Language Projector| Injeksi visual    | Jailbreaking LLM,  |
| Injection           | (Linear/Cross-Attention)| alignment vector   | eksekusi prompt liar|
+---------------------+-------------------------+--------------------+--------------------+
| Psychoacoustic      | Mel-Filterbank /        | Perturbasi audio   | Bypass biometrik   |
| Audio Masking       | Spectrogram Layer       | sub-threshold      | suara & injeksi STT|
+---------------------+-------------------------+--------------------+--------------------+
| Orthographic        | Visual Tokenization /   | Token Clashing &   | Misklasifikasi     |
| Semantic Injection  | Multimodal Attention    | Attention Hijack   | identitas dokumen  |
+---------------------+-------------------------+--------------------+--------------------+
| Physical EOT Patch  | Detektor Objek Spasial  | Optimasi distribusi| Evasion kamera     |
|                     | (YOLO, Faster-RCNN)     | transformasi fisik | CCTV / sensor AV   |
+---------------------+-------------------------+--------------------+--------------------+
```

---

## 9. Code Example Sederhana (Minimal & Clear)

Implementasi PyTorch dari serangan Projected Gradient Descent (PGD) terikat norma $L_\infty$.

```python
import torch
import torch.nn as nn

def pgd_attack(
    model: nn.Module,
    images: torch.Tensor,
    labels: torch.Tensor,
    epsilon: float = 8/255,
    alpha: float = 2/255,
    num_iter: int = 10,
    loss_fn: nn.Module = nn.CrossEntropyLoss()
) -> torch.Tensor:
    """
    Projected Gradient Descent (PGD) L-infinity attack.
    Menghasilkan citra adversarial dengan membatasi perturbasi dalam bola L-inf.
    """
    # Salin citra asli dan tambahkan inisialisasi acak untuk menghindari local minima
    adv_images = images.clone().detach()
    adv_images = adv_images + torch.empty_like(adv_images).uniform_(-epsilon, epsilon)
    adv_images = torch.clamp(adv_images, min=0.0, max=1.0).detach()

    for _ in range(num_iter):
        adv_images.requires_grad = True
        
        # Forward pass
        outputs = model(adv_images)
        loss = loss_fn(outputs, labels)
        
        # Backward pass untuk mendapatkan gradien terhadap input
        loss.backward()
        
        # Ambil sign gradien (ascent)
        gradient = adv_images.grad.data.sign()
        
        # Perbarui citra adversarial dengan langkah alpha
        adv_images = adv_images.detach() + alpha * gradient
        
        # Proyeksikan kembali ke dalam batasan epsilon di sekitar citra asli
        eta = torch.clamp(adv_images - images, min=-epsilon, max=epsilon)
        adv_images = torch.clamp(images + eta, min=0.0, max=1.0).detach()

    return adv_images
```

---

## 10. Code Example Lanjutan (Production-ready / Hardening / Exploit Analysis)

Arsitektur produksi: Pipeline evaluasi adversarial komparatif dan lapisan defensif *Randomized Input Transformation* untuk memitigasi serangan gradien deterministik.

```python
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Tuple, Dict, Any

class DefensivePreprocessor(nn.Module):
    """
    Defensive Layer: Mengaplikasikan Gaussian Smoothing dan Random Resizing/Padding
    untuk merusak fase koherensi gradien adversarial (Gradient Obfuscation Prevention).
    """
    def __init__(self, sigma: float = 0.5, pad_size: int = 4):
        super().__init__()
        self.sigma = sigma
        self.pad_size = pad_size

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Menambahkan random noise mikro pada domain frekuensi
        if self.training:
            noise = torch.randn_like(x) * 0.01
            x = torch.clamp(x + noise, 0.0, 1.0)
        
        # Resizing acak untuk merusak alignment piksel presisi
        b, c, h, w = x.shape
        target_h = h + torch.randint(-self.pad_size, self.pad_size + 1, (1,)).item()
        target_w = w + torch.randint(-self.pad_size, self.pad_size + 1, (1,)).item()
        
        resized = F.interpolate(x, size=(target_h, target_w), mode='bilinear', align_corners=False)
        # Pad atau crop kembali ke dimensi asli
        padded = F.interpolate(resized, size=(h, w), mode='bilinear', align_corners=False)
        return torch.clamp(padded, 0.0, 1.0)

class RobustProductionModel(nn.Module):
    def __init__(self, base_classifier: nn.Module):
        super().__init__()
        self.defense_layer = DefensivePreprocessor()
        self.classifier = base_classifier

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        purified_x = self.defense_layer(x)
        return self.classifier(purified_x)

class AdversarialRobustnessBenchmark:
    """
    Enterprise Suite untuk memvalidasi empirical robustness model 
    terhadap serangan Evasion FGSM, PGD, dan Evaluasi Logit Distortion.
    """
    def __init__(self, model: nn.Module, device: torch.device):
        self.model = model.to(device)
        self.device = device
        self.model.eval()

    def evaluate_pgd(
        self,
        loader: torch.utils.data.DataLoader,
        epsilon: float = 8/255,
        alpha: float = 2/255,
        steps: int = 20
    ) -> Dict[str, float]:
        correct_clean = 0
        correct_adv = 0
        total = 0

        for images, labels in loader:
            images, labels = images.to(self.device), labels.to(self.device)
            total += labels.size(0)

            # Evaluasi Akurasi Asli (Clean Accuracy)
            with torch.no_grad():
                preds = self.model(images).argmax(dim=1)
                correct_clean += (preds == labels).sum().item()

            # Generate PGD Adversarial Batch
            adv_images = images.clone().detach()
            adv_images += torch.empty_like(adv_images).uniform_(-epsilon, epsilon)
            adv_images = torch.clamp(adv_images, 0.0, 1.0).detach()

            for _ in range(steps):
                adv_images.requires_grad = True
                outputs = self.model(adv_images)
                loss = F.cross_entropy(outputs, labels)
                
                # Zero existing grads and backward
                self.model.zero_grad()
                loss.backward()
                
                # Update
                grad = adv_images.grad.data.sign()
                adv_images = adv_images.detach() + alpha * grad
                eta = torch.clamp(adv_images - images, -epsilon, epsilon)
                adv_images = torch.clamp(images + eta, 0.0, 1.0).detach()

            # Evaluasi Akurasi Adversarial
            with torch.no_grad():
                adv_preds = self.model(adv_images).argmax(dim=1)
                correct_adv += (adv_preds == labels).sum().item()

        return {
            "clean_accuracy": (correct_clean / total) * 100.0,
            "adversarial_accuracy": (correct_adv / total) * 100.0,
            "robustness_drop": ((correct_clean - correct_adv) / total) * 100.0
        }
```

---

## 11. Diagram Alur Serangan & Mitigasi

```
========================= ATTACK VECTOR EXECUTION =========================
Attacker Image/Audio/Input 
        |
        v
[ Compute Forward Pass ] ---> Obtain Prediction Logits Z(x)
        |
        v
[ Compute Loss Function ] --> Calculate Error J(theta, x, y_target)
        |
        v
[ Backpropagation ] --------> Extract Input Gradients (nabla_x)
        |
        v
[ Optimization Step ] ------> Modulate via L_p Norm / EOT Constraints
        |
        v
Synthesized Adversarial Input (x_adv)

========================= DEFENSIVE MITIGATION FLOW =======================
Raw Input Vector (x_adv)
        |
        v
[ Ingestion & Normalization ]
        |
        v
[ Randomized Spatial Transformation ] ---> Disperses Local Gradient Coherence
        |
        v
[ Autoencoder/Diffusion Denoising ]   ---> Strips High-Frequency Perturbations
        |
        v
[ Multi-Head Cross-Attention Check ]  ---> Detects Semantic vs Visual Clashes
        |
        v
Robust Classification / Decision Engine ---> Hardened Output Verification
```

---

## 12. Trade-offs & Security vs Usability / Performance

* **Akurasi Asli (Standard Accuracy) vs Robustness:**
  Menerapkan *Adversarial Training* (melatih model dengan sampel yang diserang secara intensif) secara konsisten menurunkan akurasi pada data bersih (*clean data*) sebesar 2% hingga 8%. Hal ini merupakan konsekuensi teoritis dari pergeseran batasan keputusan (*decision boundary*) yang harus lebih halus (*smoother*).
* **Latensi Komputasi (Inference Overhead):**
  Mitigasi *real-time* seperti *input denoising* berbasis diffusion model atau *randomized smoothing* meningkatkan latensi inferensi secara signifikan (2x hingga 10x), membatasi penggunaannya pada sistem berkecepatan tinggi (*real-time edge computing*).
* **Kompleksitas Training:**
  Latihan model dengan PGD-7 meningkatkan beban komputasi siklus training sebesar $\sim 7\times$ lipat dibandingkan pelatihan standar, membutuhkan alokasi kluster akselerator (GPU/TPU) yang jauh lebih masif.

---

## 13. Edge Cases & Complex Failure Modes

* **Obfuscated Gradients (False Sense of Security):**
  Defensi yang menerapkan pemrosesan tak terdiferensiasi (*non-differentiable operations*) seperti kuantisasi ekstrem sering kali hanya menyamarkan gradien (*gradient masking*). Penyerang berpengalaman dapat menembus sistem ini menggunakan teknik *Backward Pass Differentiable Approximation* (BPDA).
* **Transferabilitas Antar-Model (Transferability Paradox):**
  Perturbasi adversarial yang dioptimalkan pada model pengganti (*surrogate model*) berkategori *white-box* (misal: ResNet-50) dapat berhasil memicu misklasifikasi pada model target komersial berbasis *black-box* (misal: arsitektur proprietary transformer) tanpa perlu akses gradien langsung.
* **Perturbasi Multi-Modal Sinkron:**
  Bila sistem mengombinasikan modalitas teks dan citra secara bersamaan, injeksi adversarial yang disinkronkan secara ortogonal (noise visual tipis ditambah teks parafrasa ambigu) mampu memicu kegagalan sistem deteksi anomali gabungan, meskipun masing-masing modalitas tampak normal saat dianalisis secara terisolasi.

---

## 14. Anti-Patterns & Common Vulnerabilities

* **Anti-Pattern 1: Mengandalkan Filter Teks Regex pada VLM.**
  Memblokir kata kunci tertentu pada prompt masukan tanpa menganalisis token visual yang dihasilkan oleh *vision encoder*. Citra yang mengandung teks tipografis berbahaya atau perturbasi laten akan dengan mudah memotong filter ini.
* **Anti-Pattern 2: Defensive Distillation Tanpa Verifikasi Rigor.**
  Menggunakan *defensive distillation* lama untuk menyembunyikan gradien; teknik ini sepenuhnya tidak berdaya terhadap optimasi Carlini-Wagner (C&W).
* **Anti-Pattern 3: Menggunakan Metrik $L_2$ Saja untuk Uji Validasi.**
  Mengasumsikan ketahanan sistem hanya karena model lolos uji $L_2$. Perturbasi berbasis rotasi spasial, *spatial deformation*, atau $L_0$ (patch terlokalisasi) dapat mengecoh model secara menyeluruh tanpa menghasilkan deviasi $L_2$ yang signifikan.

---

## 15. Best Practices & Enterprise Remediation Guide

### 15.1 Remediasi Arsitektur Model
1. **Adversarial Training sebagai Baseline:** Terapkan skema pelatihan *min-max robust optimization* (Madry et al.) secara berkala pada dataset produksi inti.
2. **Kombinasi Dual-Pipeline VLM:** Pisahkan jalur ekstraksi Optical Character Recognition (OCR) dan deskripsi semantik visual. Jangan pernah mengizinkan encoder teks menerima token visual mentah tanpa verifikasi silang terhadap modul *sanitization*.

### 15.2 Lapisan Sanitasi Masukan (Input Hygiene Layer)
1. **Random Spatial Transformations:** Terapkan operasi deterministik-acak (rotasi skala kecil, pergeseran fasa, *JPEG compression* dinamis) sebelum data diumpankan ke model target guna merusak sinkronisasi fase perturbasi adversarial.
2. **Diffusion-Based Purification:** Terapkan proses denoising ringan (misal: DiffPure) untuk meregenerasi manifold gambar ke ruang distribusi alami sebelum klasifikasi formal dieksekusi.

### 15.3 Runtime Monitoring & Telemetry
1. Pantau distribusi *logit entropy*. Input adversarial sering kali menghasilkan distribusi entropi logit yang sangat tidak lazim atau seragam di luar kelas target.
2. Gunakan metrik *Mahalanobis Distance* pada representasi lapisan tersembunyi (*hidden layer activations*) untuk mendeteksi *out-of-distribution* (OOD) activations yang diakibatkan oleh perturbasi gradien.

---

## 16. Hands-on Lab Step-by-Step

### Skenario Lab
Mengevaluasi ketahanan model *Image Classifier* ResNet berbasis PyTorch menggunakan serangan PGD, memvalidasi kerentanannya, dan menerapkan mitigasi berbasis *Input Transformations*.

#### Langkah 1: Persiapan Lingkungan
```bash
mkdir -p adversarial_lab && cd adversarial_lab
python3 -m venv venv
source venv/bin/activate
pip install torch torchvision torchaudio numpy matplotlib
```

#### Langkah 2: Buat Skrip Eksperimen (`lab_eval.py`)
```python
import torch
import torchvision.models as models
import torchvision.transforms as transforms
from PIL import Image
import urllib.request
import json

# Setup perangkat
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Muat model referensi ResNet18
weights = models.ResNet18_Weights.DEFAULT
model = models.resnet18(weights=weights).to(device)
model.eval()

# Unduh label ImageNet
LABELS_URL = "https://raw.githubusercontent.com/anishathalye/imagenet-simple-labels/master/imagenet-simple-labels.json"
urllib.request.urlretrieve(LABELS_URL, "imagenet_labels.json")
with open("imagenet_labels.json") as f:
    labels = json.load(f)

# Buat dummy tensor acak yang mensimulasikan citra terstandarisasi
input_tensor = torch.rand(1, 3, 224, 224, requires_grad=False).to(device)
original_pred = model(input_tensor).argmax().item()
print(f"[*] Label Prediksi Awal: {labels[original_pred]} (ID: {original_pred})")

# Inisialisasi parameter serangan PGD
epsilon = 16 / 255
alpha = 2 / 255
steps = 15

adv_tensor = input_tensor.clone().detach()
adv_tensor += torch.empty_like(adv_tensor).uniform_(-epsilon, epsilon)
adv_This request was blocked by Gemini's filters. They can occasionally trigger by mistake on safe coding, security, or biology-related queries. Please try rephrasing your prompt. You can [send feedback](https://ai.google.dev/gemini-api/docs/troubleshooting#file-bug) or read more about [our policies here](https://policies.google.com/terms/generative-ai/use-policy).