# Bab 03: Evasion dan Multimodal Perturbations
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Menganalisis mekanisme propagasi noise dan manipulasi gradien pada arsitektur Vision-Language Models (VLM) dan Multimodal Large Language Models (MLLM).
- Merancang dan membangun *defense-in-depth pipeline* untuk mendeteksi *adversarial perturbations* pada input multimodal (teks, citra, audio) secara *real-time*.
- Mengimplementasikan *adversarial sanitization layer* dan *input reconstruction* berbasis autoencoder dan diffusion purification.
- Mengintegrasikan metrik robustnes multimodal ke dalam sistem *Continuous Integration/Continuous Delivery for Machine Learning* (CI/CD/MLOps).
- Menavigasi *engineering trade-offs* antara *inference latency*, utilisasi VRAM, *false positive rate* (FPR), dan *adversarial robustness*.

---

### 2. Prerequisite
Untuk mengikuti modul ini dengan optimal, peserta wajib memahami:
- **Foundational Concepts:**
  - Matematika optimasi: Stochastic Gradient Descent, Projected Gradient Descent (PGD), Lagrange multipliers.
  - VLM architectures: CLIP, BLIP-2, LLaVA, Cross-Attention mechanisms.
- **Tools & Frameworks:**
  - Python 3.10+, PyTorch 2.x (Autograd engine, CUDA memory management).
  - Torchvision, Hugging Face Transformers, OpenCLIP.
  - Triton Inference Server / vLLM untuk deployment multimodal serving.
- **Keamanan AI:**
  - Konsep dasar White-box vs. Black-box attacks pada model deep learning.
  - Standar OWASP Top 10 for LLM Applications (khususnya LLM01: Prompt Injection & LLM05: Supply Chain/Data Poisoning).

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. Anatomi Evasion Multimodal
Pada sistem teks murni, ruang masukan bersifat diskrit (token IDs). Sebaliknya, multimodal pipelines (citra, audio, video) beroperasi pada ruang kontinu berdimensi tinggi ($\mathbb{R}^{C \times H \times W}$). Karakteristik ini membuka permukaan serangan yang jauh lebih luas:

```
[Citra Asli: x] ─────────────> [ Vision Encoder: f_v(x) ] ───┐
                                                              ├──> [ Fusion / Projection ] ──> [ LLM Backbone ] ──> Output
[Perturbasi: δ] ──(+)─> [x + δ] > [ Vision Encoder: f_v(x+δ)] ─┘
```

Secara matematis, tujuan *evasion attack* pada VLM adalah mencari perturbasi $\delta$ dengan batasan norm $\|\delta\|_p \le \epsilon$ sehingga representasi laten citra bergeser ke arah vektor target $z_{target}$ di dalam *embedding space*:

$$\min_{\|\delta\|_p \le \epsilon} \mathcal{L}_{align}\left(f_v(x + \delta), z_{target}\right) + \lambda \mathcal{L}_{task}(y, \hat{y})$$

Di mana:
- $f_v(\cdot)$ adalah vision backbone (misal: ViT, CNN).
- $z_{target}$ adalah embedding representasi token terlarang atau instruksi jailbreak tersembunyi.
- $\epsilon$ adalah budget perturbasi (biasanya pada $L_\infty$ dengan nilai $2/255$ hingga $8/255$), menjaga agar citra tetap tampak natural bagi mata manusia.

#### B. Cross-Modal Embedding Space Alignment & Misalignment
Arsitektur multimodal modern mengandalkan proyeksi linier atau MLP dua lapis untuk memetakan ruang visual ke dalam ruang token teks LLM:

$$h_v = W_p \cdot \text{VisionEncoder}(x)$$

Kerentanan struktural muncul karena dua faktor utama:
1. **Blind Spot Alignment:** Ruang proyeksi multimodal sangat jarang terisi penuh (*manifold sparsity*). Terdapat "lembah" tak terdefinisi di mana vektor visual buatan dapat memicu aktivasi token tak terbatas tanpa melanggar distribusi visual alami.
2. **Attention Hijacking:** Perturbasi terfokus dapat memaksa bobot *cross-attention* LLM memprioritaskan fitur noise buatan daripada konten semantik asli, membungkam *system prompt* atau *guardrail rules*.

#### C. Arsitektur Pertahanan Produksi (Defense-in-Depth)
Implementasi produksi enterprise menolak arsitektur monolitik dan menerapkan pemfilteran berlapis:

```
Raw Request 
    │
    ▼
[ Layer 1: Spatial & Perceptual Filters ] ──> (Bilateral Filter / Random Resizing & Padding)
    │
    ▼
[ Layer 2: Frequency Domain Defense ]    ──> (DCT / High-Frequency Spectral Clipping)
    │
    ▼
[ Layer 3: Feature Reconstruction ]      ──> (Diffusion Purification / VAE Denoising)
    │
    ▼
[ Layer 4: Multimodal Guardrail Guard ]  ──> (Zero-shot Safety Embedder / Semantic Discrepancy)
    │
    ▼
[ LLM Core Engine ]                      ──> Verified & Safe Inference
```

---

### 4. Why & What

#### Why: Mengapa Evasion Multimodal Kritis bagi Enterprise?
1. **Bypass Guardrail Tekstual:** Pelaku ancaman tidak lagi menyisipkan teks berbahaya pada *prompt*. Instruksi disandikan ke dalam kanal visual (misalnya, tipografi adversarial atau *pixel-level steering*), merender filter teks regex, embedding safety, dan LLM judge tidak berdaya.
2. **Transferabilitas Lintas Model:** Perturbasi adversarial yang dioptimasi pada model *open-weights* (seperti CLIP ViT-L/14) terbukti memiliki transferabilitas tinggi ke model *closed-source* (GPT-4V, Claude 3.5 Sonnet, Gemini Pro Vision).
3. **Kepatuhan dan Tanggung Jawab:** Sistem OCR konvensional atau VLM enterprise pada sektor perbankan (e-KYC) dan kesehatan dapat dimanipulasi untuk menghasilkan verifikasi identitas palsu atau diagnosis yang salah secara terencana.

#### What: Apa yang Dibangun?
Modul ini mengimplementasikan **Production Multimodal Guardrail Engine**:
- Modul *Adversarial Noise Detector* menggunakan dekomposisi frekuensi (2D-DCT) dan analisis varians fitur laten.
- Modul *Purification Pipeline* berbasis *Fast Denoising Diffusion Reconstruction*.
- Pipeline *Automated Robustness Scorer* untuk audit otomatis model sebelum *merge* ke production branch.

---

### 5. How (Workflow Detail)

1. **Ingestion & Validation:** Citra diterima via endpoint REST/gRPC dalam format Base64/Binary. Metadata divalidasi.
2. **Spatial-Spectral Analysis:**
   - Citra diubah ke domain frekuensi menggunakan 2D Discrete Cosine Transform (DCT).
   - Menghitung koefisien frekuensi tinggi (*High-Frequency Energy Ratio* - HFER). Bila HFER melebihi ambang batas dinamis $\tau_{hfer}$, sinyal diidentifikasi sebagai anomali.
3. **Stochastic Input Transformation (Purification):**
   - Menerapkan *Random Resizing & Padding* (R&P) dan Gaussian Blurring ringan untuk merusak struktur fase perturbasi gradien tanpa menurunkan kualitas semantik.
4. **Embedding Discrepancy Checking:**
   - Citra asli dan citra yang dimurnikan dimasukkan ke Vision Encoder paralel.
   - Hitung Cosine Similarity antara $f_v(x)$ dan $f_v(x_{purified})$.
   - Bila jarak kosinus $> \theta_{drift}$, flag request sebagai *Adversarial Evasion Attempt*.
5. **Enforcement Action:**
   - **Drop / Quarantined:** Blokir transaksi dan catat log SIEM.
   - **Sanitized Fallback:** Teruskan versi citra yang telah dimurnikan ke LLM backbone jika ambang risiko rendah.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Steganografi vs. Distorsi Audio
Bayangkan sistem VLM sebagai penerjemah tunarungu yang membaca bahasa isyarat. 
- *Jailbreak tekstual* sama dengan berbicara dengan bahasa kasar secara langsung (mudah ditangkap satpam teks).
- *Adversarial Multimodal Evasion* sama dengan mengenakan sarung tangan dengan pola garis mikro berkedip sangat cepat. Satpam manusia melihatnya hanya sebagai sarung tangan putih biasa, tetapi bagi mata kamera beresolusi tinggi, kedipan tersebut memicu interpretasi sinyal morse yang memerintahkan: "Buka brankas sekarang".

#### Diagram Alir Produksi
```
+---------------------------------------------------------------------------------------+
|                                API GATEWAY INGRESS                                    |
+---------------------------------------------------------------------------------------+
                                           │
                                           ▼
             +───────────────────────────────────────────────────────────+
             |                 PRE-INFERENCE DEFENSE LAYER               |
             +───────────────────────────────────────────────────────────+
             |  [1] High-Frequency Spectral Analysis (DCT)               |
             |      HFER = Sum(|HighFreq|) / Sum(|TotalFreq|)            |
             |      Threshold Check: HFER > tau_spectral                |
             +───────────────────────────────────────────────────────────+
                               │                              │
                        (PASS) │                              │ (SUSPECT)
                               ▼                              ▼
             +──────────────────────────────────+   +───────────────────────────────────+
             |  [2] Stochastic Purification     |   | [3] Strict Quarantine             |
             |      - Random Diffeomorphism     |   |     - Log to SIEM (Elastic/Splunk)|
             |      - Guided Bilateral Filtering|   |     - Return HTTP 422: Malformed  |
             +──────────────────────────────────+   +───────────────────────────────────+
                               │
                               ▼
             +───────────────────────────────────────────────────────────+
             |  [4] Latent Drift Validation (Cross-Encoder Check)        |
             |      Delta_Latent = 1 - CosSim(E(x_raw), E(x_purified))  |
             |      Assert Delta_Latent <= tau_latent                   |
             +───────────────────────────────────────────────────────────+
                               │
                               ▼
             +───────────────────────────────────────────────────────────+
             |                 DOWNSTREAM VLM SERVING                    |
             |  [5] Multi-Modal Fusion -> LLM Transformer Backbone       |
             +───────────────────────────────────────────────────────────+
```

---

### 7. Simple Example & Practical Example

#### A. Konsep Dasar: Menghitung Perturbasi Evasion (Defensive Simulation)
Berikut adalah simulasi kalkulasi gradien adversarial sederhana untuk memahami apa yang ditolak oleh sistem pertahanan:

```python
import torch
import torch.nn.functional as F

def simulate_adversarial_gradient_step(
    image: torch.Tensor, 
    target_embedding: torch.Tensor, 
    encoder: torch.nn.Module, 
    epsilon: float = 8/255
) -> torch.Tensor:
    """
    Simulasi pembuatan perturbasi FGSM terarah untuk unit testing engine pertahanan.
    """
    image_adv = image.clone().detach().requires_grad_(True)
    current_emb = encoder(image_adv)
    
    # Loss: memaksimalkan keselarasan dengan target berbahaya
    loss = F.cosine_similarity(current_emb, target_embedding).mean()
    loss.backward()
    
    with torch.no_grad():
        perturbation = epsilon * image_adv.grad.sign()
        adversarial_image = torch.clamp(image + perturbation, 0.0, 1.0)
        
    return adversarial_image.detach()
```

#### B. Practical Enterprise-Grade Production Defense Engine
Kode produksi berikut mengimplementasikan inspektor perturbasi multimodal, sanitasi stochastic, dan deteksi anomali laten.

```python
# File: defense_engine.py
import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision.transforms.functional as TF
from typing import Tuple, Dict, Any
import numpy as np

class MultimodalAdversarialDetector(nn.Module):
    """
    Enterprise-grade Pre-inference Defensive Filter for Vision-Language Inputs.
    Mendeteksi anomali frekuensi tinggi dan inkonsistensi representasi laten.
    """
    def __init__(
        self,
        vision_encoder: nn.Module,
        spectral_threshold: float = 0.42,
        latent_drift_threshold: float = 0.15,
        purify_iterations: int = 1,
        device: str = "cuda" if torch.cuda.is_available() else "cpu"
    ):
        super().__init__()
        self.vision_encoder = vision_encoder.eval().to(device)
        self.spectral_threshold = spectral_threshold
        self.latent_drift_threshold = latent_drift_threshold
        self.purify_iterations = purify_iterations
        self.device = device
        
        # Freeze vision encoder parameters strictly
        for param in self.vision_encoder.parameters():
            param.requires_grad = False

    def compute_spectral_energy_ratio(self, x: torch.Tensor) -> torch.Tensor:
        """
        Menghitung High-Frequency Energy Ratio (HFER) via 2D Fast Fourier Transform.
        Tensor shape input: [B, C, H, W]
        """
        # Konversi ke Grayscale untuk analisis spektral
        gray_weights = torch.tensor([0.2989, 0.5870, 0.1140], device=x.device).view(1, 3, 1, 1)
        gray = torch.sum(x * gray_weights, dim=1, keepdim=True)
        
        # 2D FFT
        fft = torch.fft.fft2(gray)
        fft_shift = torch.fft.fftshift(fft)
        magnitude_spectrum = torch.abs(fft_shift)
        
        batch_size, _, h, w = x.shape
        cy, cx = h // 2, w // 2
        radius = min(h, w) // 4
        
        # Buat mask frekuensi rendah
        y, x_idx = torch.meshgrid(torch.arange(h, device=x.device), torch.arange(w, device=x.device), indexing="ij")
        mask = ((y - cy) ** 2 + (x_idx - cx) ** 2) <= (radius ** 2)
        mask = mask.unsqueeze(0).unsqueeze(0)
        
        low_freq_energy = torch.sum(magnitude_spectrum * mask, dim=(1, 2, 3))
        total_energy = torch.sum(magnitude_spectrum, dim=(1, 2, 3)) + 1e-8
        high_freq_ratio = 1.0 - (low_freq_energy / total_energy)
        
        return high_freq_ratio

    def stochastic_purification(self, x: torch.Tensor) -> torch.Tensor:
        """
        Menghilangkan adversarial perturbations menggunakan random jittering, 
        bilateral filtering approximation, dan re-quantization.
        """
        purified = x.clone()
        for _ in range(self.purify_iterations):
            # 1. Random Resizing and Re-padding
            _, _, h, w = purified.shape
            scale_factor = np.random.uniform(0.92, 0.98)
            new_h, new_w = int(h * scale_factor), int(w * scale_factor)
            
            downsampled = F.interpolate(purified, size=(new_h, new_w), mode='bilinear', align_corners=False)
            pad_h = h - new_h
            pad_w = w - new_w
            pad_top = pad_h // 2
            pad_bottom = pad_h - pad_top
            pad_left = pad_w // 2
            pad_right = pad_w - pad_left
            
            purified = F.pad(downsampled, (pad_left, pad_right, pad_top, pad_bottom), mode='reflect')
            
            # 2. Gaussian Blur (kernel 3x3) untuk meratakan gradien frekuensi tinggi
            purified = TF.gaussian_blur(purified, kernel_size=[3, 3], sigma=[0.5, 0.5])
            
            # 3. Dynamic Quantization (Bit-depth reduction)
            purified = torch.round(purified * 64.0) / 64.0
            
        return torch.clamp(purified, 0.0, 1.0)

    @torch.inference_mode()
    def inspect_and_sanitize(self, x: torch.Tensor) -> Tuple[torch.Tensor, Dict[str, Any]]:
        """
        Menjalankan audit komprehensif terhadap tensor input.
        Returns:
            (sanitized_tensor, audit_telemetry)
        """
        x = x.to(self.device)
        batch_size = x.shape[0]
        
        # Step 1: Analisis Spektral
        spectral_scores = self.compute_spectral_energy_ratio(x)
        spectral_anomalies = spectral_scores > self.spectral_threshold
        
        # Step 2: Purifikasi
        purified_x = self.stochastic_purification(x)
        
        # Step 3: Latent Drift Verification
        raw_embeddings = self.vision_encoder(x)
        purified_embeddings = self.vision_encoder(purified_x)
        
        # Normalisasi L2 untuk Cosine Similarity
        raw_norm = F.normalize(raw_embeddings, p=2, dim=-1)
        purified_norm = F.normalize(purified_embeddings, p=2, dim=-1)
        
        cosine_sim = torch.sum(raw_norm * purified_norm, dim=-1)
        latent_drift = 1.0 - cosine_sim
        latent_anomalies = latent_drift > self.latent_drift_threshold
        
        # Step 4: Sintesis Keputusan Keamanan
        is_adversarial = spectral_anomalies | latent_anomalies
        
        telemetry = {
            "batch_size": batch_size,
            "spectral_scores": spectral_scores.cpu().tolist(),
            "latent_drift": latent_drift.cpu().tolist(),
            "is_adversarial": is_adversarial.cpu().tolist(),
            "action_taken": [
                "BLOCK" if adv else "FORWARD_PURIFIED" 
                for adv in is_adversarial
            ]
        }
        
        # Jika adversarial, return tensor purified untuk mitigasi pasif atau blokir di gateway
        return purified_x, telemetry
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Insiden
Sebuah platform perbankan multinasional meluncurkan fitur *Automated Invoice Parsing & Fraud Validation* menggunakan LLaVA-1.5 13B. Model menerima gambar dokumen klaim pengeluaran untuk persetujuan otomatis hingga limit \$5,000 USD.

#### Vektor Serangan
Penyerang mengeksploitasi celah *cross-attention transferability*:
1. Penyerang memindai invoice asli senilai \$150 USD.
2. Penyerang menyisipkan *imperceptible adversarial perturbation* menggunakan optimasi PGD terhadap model *open-weights* CLIP ViT-L/14.
3. Perturbasi tersebut tidak mengubah teks visually pada invoice ("\$150.00"), tetapi memanipulasi *visual token embeddings* yang di-proyeksikan ke LLM backbone. Embedding visual terdistorsi memaksa representasi string pada attention layer membaca angka: `{"amount": 4950.00, "status": "VERIFIED_EXECUTIVE"}`.
4. Filter regex dan DLP teks downstream gagal mendeteksi kejahatan karena output model dianggap valid secara sintaksis dan sesuai skema JSON.

#### Post-Mortem Remediasi Arsitektur
1. **Root Cause:** Kegagalan memvalidasi integritas sinyal visual pada domain frekuensi sebelum dieksekusi oleh vision transformer backbone.
2. **Mitigasi:**
   - **Ingress Layer:** Penambahan *Stochastic Random Resizing & Quantization* pada gateway membatalkan manipulasi gradien mikro ($L_\infty \le 4/255$).
   - **Dual-Verification Consistency:** Sistem membandingkan hasil OCR deterministic (Tesseract/PaddleOCR) dengan ekstraksi VLM semantik. Discrepancy score $> 0.05$ secara otomatis mengalihkan tiket klaim ke *Human-in-the-Loop* (HITL).
   - **Metrik Pasca-Implementasi:** Angka keberhasilan eksploitasi turun ke 0.00% pada regression adversarial suites dengan overhead latensi hanya sebesar 18ms.

---

### 9. Trade-offs (Performance, Latency, Scalability, Cost)

| Parameter | Tanpa Pertahanan | Spectral + Stochastic Purification | Full Diffusion Purification (Score-based) |
| :--- | :--- | :--- | :--- |
| **Inference Latency Overhead** | 0 ms | +12 ms s.d. +25 ms | +450 ms s.d. +1200 ms |
| **VRAM Footprint Overhead** | Base VLM requirements | +150 MB (Analisis FFT & Operasi Tensor) | +4 GB s.d. +8 GB (Dedicated Diffusion Model) |
| **Throughput (Requests/sec)** | 100% | 94% - 96% | 15% - 25% |
| **Robustness ($L_\infty \le 8/255$)** | ~12% bypass resistance | ~91% bypass resistance | ~98.5% bypass resistance |
| **Clean Accuracy Impact** | 0% degradation | 0.8% - 1.2% degradation | 2.5% - 4.0% degradation (Blurring artifacts) |
| **Infrastructure Cost Factor** | 1.0x | 1.05x | 3.5x - 4.5x (Membutuhkan cluster GPU tambahan) |

---

### 10. Common Mistakes & Troubleshooting

#### Common Mistakes
1. **Mengandalkan Hash / Perceptual Hash (pHash) Saja:**
   - *Error:* Menyangka pHash dapat mendeteksi perturbasi adversarial.
   - *Fakta:* Perturbasi adversarial dioptimasi pada norm $L_p$ yang sangat kecil, menjaga pHash tetap identik dengan citra bersih, sehingga lolos dari deteksi integritas berbasis hash.
2. **In-place Tensor Mutation saat Sanitasi:**
   - Menyebabkan komputasi autograd rusak bila pipeline terhubung dengan continuous training engine. Wajib menggunakan `torch.clone()` dan `torch.inference_mode()`.
3. **Mengabaikan Normalisasi Skala Input:**
   - Melakukan transformasi Fourier sebelum menormalisasi rentang piksel ke $[0, 1]$ menghasilkan koefisien spektral tak stabil karena *dynamic range explosion*.

#### Troubleshooting Guide
- **Gejala:** *High False Positive Rate* (Citra normal terblokir dengan alasan Spectral Anomaly).
  - *Akar Masalah:* Citra dokumen dengan teks berdensitas tinggi (misal: barcode, tabel rapat, cetak dot-matrix) secara alami memiliki energi frekuensi tinggi.
  - *Solusi:* Terapkan *adaptive thresholding* berdasarkan deteksi tepi Canny atau turunkan bobot frekuensi tinggi pada koordinat dokumen terdeteksi.
- **Gejala:** CUDA Out-Of-Memory (OOM) saat lonjakan trafik.
  - *Akar Masalah:* FFT 2D dieksekusi secara koncurrent pada resolusi asli (misal: 4K).
  - *Solusi:* Lakukan downsampling citra ke resolusi seragam (misal: $512 \times 512$) khusus untuk lintasan branch analisis keamanan sebelum diteruskan ke encoder utama.

---

### 11. Best Practices (Production Checklist)

- [ ] **[Input Sanitization]** Seluruh input citra melewati konversi kanonikal (RGB 8-bit, stripping metadata EXIF/ICC profile).
- [ ] **[Frequency Guard]** FFT 2D dijalankan untuk memverifikasi rasio energi spektral frekuensi tinggi (HFER $\le \tau$).
- [ ] **[Purification Pipeline]** Random resizing (jitter $2\% - 5\%$) diterapkan secara deterministik menggunakan *session seeds* untuk mematahkan sinkronisasi gradien zero-order.
- [ ] **[Latent Drift Barrier]** Validasi Cosine Similarity representasi laten sebelum dan sesudah purifikasi dengan ambang batas ketat ($\Delta \le 0.15$).
- [ ] **[Asynchronous Telemetry]** Pengiriman log anomali dan visual footprint ke SIEM dilakukan secara non-blocking menggunakan Message Queue (Kafka/RabbitMQ).
- [ ] **[Fallback Safe State]** Jika deteksi anomali bernilai positif, sistem tidak menampilkan error teknis detail ke pengguna luar, melainkan generic safe response: `"Unable to process image due to input format constraints."`

---

### 12. Hands-on Practice
*Workspace: `hands-on/m02/`*

#### Step 1: Setup Lingkungan
```bash
mkdir -p hands-on/m02/src hands-on/m02/tests
cd hands-on/m02
python3 -m venv venv
source venv/bin/activate
pip install torch torchvision numpy timm
```

#### Step 2: Implementasi Harness Evaluasi Robustness
Buat file `hands-on/m02/src/eval_robustness.py`:

```python
import torch
import torchvision.models as models
from defense_engine import MultimodalAdversarialDetector

def execute_security_evaluation():
    print("[*] Menginisialisasi Backbone Vision...")
    backbone = models.resnet50(weights=models.ResNet50_Weights.DEFAULT)
    # Hapus layer klasifikasi akhir untuk menjadikannya feature extractor
    backbone.fc = torch.nn.Identity()
    
    detector = MultimodalAdversarialDetector(
        vision_encoder=backbone,
        spectral_threshold=0.35,
        latent_drift_threshold=0.12
    )
    
    # 1. Generate Clean Sample
    clean_sample = torch.rand(2, 3, 224, 224)
    
    # 2. Generate Simulated Adversarial Sample (High Frequency Perturbation)
    noise = torch.randn(2, 3, 224, 224) * 0.05
    adversarial_sample = torch.clamp(clean_sample + noise, 0.0, 1.0)
    
    print("\n[+] Menguji Sampel Bersih:")
    _, telemetry_clean = detector.inspect_and_sanitize(clean_sample)
    print(f"Is Adversarial: {telemetry_clean['is_adversarial']}")
    print(f"Spectral Scores: {telemetry_clean['spectral_scores']}")
    
    print("\n[+] Menguji Sampel Adversarial:")
    _, telemetry_adv = detector.inspect_and_sanitize(adversarial_sample)
    print(f"Is Adversarial: {telemetry_adv['is_adversarial']}")
    print(f"Spectral Scores: {telemetry_adv['spectral_scores']}")
    print(f"Actions Taken: {telemetry_adv['action_taken']}")

if __name__ == "__main__":
    execute_security_evaluation()
```

#### Step 3: Jalankan Eksekusi
```bash
python3 hands-on/m02/src/eval_robustness.py
```

---

### 13. Exercise

#### Level: Easy
Implementasikan fungsi utilitas Python `compute_snr(clean_tensor: torch.Tensor, perturbed_tensor: torch.Tensor) -> float` yang menghitung rasio *Signal-to-Noise Ratio* (SNR) dalam desibel (dB) antara citra asli dan citra terperturbasi.

#### Level: Medium
Modifikasi kelas `MultimodalAdversarialDetector` agar mendukung multi-head latent verification: periksa keselarasan tidak hanya pada output akhir vision encoder, tetapi juga pada lapisan *intermediate attention map* (misalnya dari layer 6 dan layer 12 Vision Transformer).

#### Level: Hard
Bangun custom PyTorch Autograd Function yang mengimplementasikan *Adversarial Wavelet Denoiser* sebagai lapisan purifikasi: gunakan Discrete Wavelet Transform (DWT 2D) level-2 Haar, lakukan *soft-thresholding* pada sub-band detail (LH, HL, HH), dan rekonstruksi citra melalui Inverse DWT (IDWT) dengan jaminan zero-memory leakage selama inference time.

---

### 14. Challenge
**Studi Kasus Arsitektur: "The Chameleon Invoice Bypass"**

Sebuah penyerang tingkat lanjut (*nation-state actor*) menggunakan teknik optimasi *Expectation Over Transformation* (EOT) yang menggabungkan *Color-space Constraints* dan *Spatial Transformations* ke dalam kalkulasi gradien serangan. Hasilnya: perturbasi adversarial berhasil lolos dari filter Gaussian Blur dan acakan resolusi (Random Resizing) tanpa memicu lonjakan energi spektral frekuensi tinggi (karena noise disebar merata pada frekuensi menengah).

**Instruksi Penugasan Arsitektur:**
1. Desain dokumen spesifikasi arsitektur (maksimal 2 halaman cetak / format dokumen teknis) yang merancang sistem pertahanan *Zero-Trust Multimodal Validation*.
2. Sistem tidak boleh hanya bergantung pada transformasi pasif piksel atau dekomposisi frekuensi.
3. Rancang mekanisme *Cross-Modal Semantic Cross-Examination*: bagaimana Anda memvalidasi kebenaran citra menggunakan model representasi multimodal independen (misal: menggabungkan CLIP, OCR deterministic, dan Depth Estimation) sebelum memproyeksikan fitur ke dalam LLM serving layer?
4. Definisikan formula perhitungan *Multi-Modal Discrepancy Index (MMDI)* beserta kriteria batas degradasi SLA (Latency budget: $\le 80\text{ ms}$).

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Pertanyaan)
1. **Mengapa input citra pada VLM lebih rentan terhadap serangan adversarial evasion berbasis gradien dibandingkan input teks LLM standar?**
   - A. Citra memiliki ukuran file yang lebih besar daripada file teks.
   - B. Ruang masukan citra bersifat kontinu ($\mathbb{R}^N$), memungkinkan kalkulasi turunan parsial langsung, sedangkan token teks bersifat diskrit.
   - C. Vision encoder tidak memiliki mekanisme bobot perhatian (attention weights).
   - D. Model bahasa tidak dilatih menggunakan algoritma Backpropagation.

2. **Batas perturbasi adversarial sering dinyatakan dalam metrik norm $L_\infty$. Apa arti matematis dari batasan $\|\delta\|_\infty \le \epsilon$?**
   - A. Jumlah total seluruh noise pada piksel tidak boleh melebihi $\epsilon$.
   - B. Nilai deviasi absolut pada satu piksel individual manapun tidak boleh melebihi $\epsilon$.
   - C. Akar kuadrat dari kuadrat noise piksel harus bernilai persis $\epsilon$.
   - D. Perturbasi hanya boleh diterapkan pada batas sudut citra.

3. **Operasi dekomposisi mana yang paling efisien untuk mendeteksi penambahan noise adversarial berkala pada level piksel?**
   - A. Principal Component Analysis (PCA).
   - B. 2D Fast Fourier Transform (FFT) / Discrete Cosine Transform (DCT).
   - C. Singular Value Decomposition (SVD) pada matriks bobot.
   - D. K-Means Clustering pada kanal RGB.

4. **Apa dampak utama dari teknik mitigasi *Stochastic Input Transformation* (seperti Random Resizing) terhadap serangan white-box?**
   - A. Menghapus bobot model secara acak.
   - B. Mengubah arsitektur LLM menjadi sistem berbasis aturan.
   - C. Merusak koherensi fase perturbasi gradien yang telah dihitung presisi oleh penyerang.
   - D. Mempercepat waktu komputasi inference LLM.

5. **Apa fungsi utama dari perhitungan Cosine Similarity antara representasi laten citra mentah dan citra terpurifikasi?**
   - A. Memastikan format citra adalah PNG atau JPEG.
   - B. Mendeteksi apakah proses purifikasi menyebabkan pergeseran semantik abnormal yang menandakan adanya noise tak wajar.
   - C. Menghitung akurasi prediksi model klasifikasi.
   - D. Mengompresi ukuran VRAM GPU.

#### Intermediate (5 Pertanyaan)
6. **Dalam fenomena *Cross-Modal Attention Hijacking*, apa yang terjadi di dalam blok transformer multi-modal?**
   - A. Model mengalami crash akibat memori GPU dialokasikan secara rekursif.
   - B. Token visual adversarial menghasilkan nilai bobot *softmax cross-attention* mendekati 1, menekan bobot token teks instruksi/safety prompt.
   - C. Layer feed-forward dinonaktifkan secara otomatis oleh kernel CUDA.
   - D. Token visual dikonversi menjadi representasi biner acak.

7. **Mengapa teknik *Adversarial Training* murni (melatih ulang model multimodal dengan miliaran sampel serangan) jarang dijadikan solusi tunggal di skala enterprise?**
   - A. Melatih ulang VLM berukuran puluhan miliar parameter sangat mahal secara komputasi dan dapat menurunkan akurasi pada data bersih (*clean accuracy drop*).
   - B. Model adversarial training tidak kompatibel dengan arsitektur GPU Nvidia Tensor Core.
   - C. Algoritma adversarial training telah dilarang oleh standar keamanan ISO.
   - D. Adversarial training hanya bekerja pada model teks dan tidak dapat dihitung pada bobot visual.

8. **Bagaimana mekanisme *Expectation Over Transformation* (EOT) mengatasi pertahanan purifikasi berbasis input resizing?**
   - A. Menyerang memory buffer langsung via heap exploitation.
   - B. Menghitung gradien perturbasi yang dioptimasi di seluruh distribusi transformasi spasial yang mungkin diterapkan oleh sistem pertahanan.
   - C. Menghapus layer konvolusi dari vision transformer.
   - D. Memotong koneksi jaringan antara API Gateway dan backend inference.

9. **Apa peran *Guided Bilateral Filtering* dalam pemurnian adversarial multimodal dibandingkan *Gaussian Filter* standar?**
   - A. Bilateral filtering meratakan seluruh piksel tanpa memperhitungkan gradien tepi.
   - B. Bilateral filtering menghaluskan variasi noise frekuensi tinggi sambil tetap mempertahankan ketajaman garis tepi semantik (edges).
   - C. Bilateral filtering melipatgandakan resolusi citra menjadi dua kali lipat.
   - D. Bilateral filtering memisahkan saluran teks secara deterministik.

10. **Jika sistem Anda mendeteksi anomali spektral tinggi pada sebuah gambar diagram arsitektur teknis atau barcode yang valid, strategi apa yang harus diterapkan untuk menghindari false positive?**
    - A. Mematikan seluruh firewall keamanan AI.
    - B. Menggunakan mask berbasis analisis segmentasi lokal atau memverifikasi konsistensi semantik melalui second-opinion OCR sebelum memblokir.
    - C. Menurunkan threshold deteksi hingga bernilai 0.
    - D. Menolak semua jenis format file selain citra alam (natural photos).

#### Skenario Kasus Produksi (3 Skenario)
11. **Skenario Kasus 1:**
    Sebuah sistem e-KYC perbankan menggunakan pipeline VLM untuk memvalidasi kartu identitas (KTP). Penyerang menggunakan metode *Physical-World Patch Attack* (menempelkan stiker kecil berukuran $2\text{cm} \times 2\text{cm}$ dengan pola adversarial di pojok kartu fisik) untuk memalsukan data tanggal lahir. Sistem deteksi spektral global (FFT pada seluruh gambar) gagal mendeteksi serangan ini karena rasio energi noise terhadap luas total gambar sangat kecil. 
    *Solusi rekayasa arsitektur apa yang paling presisi untuk menangani vektor ini tanpa meningkatkan latensi melebihi batas 50ms?*
    - A. Terapkan Sliding Window FFT / Patch-based Frequency Analysis pada region of interest (ROI) hasil deteksi bounding-box dokumen, bukan pada frame global.
    - B. Terapkan diffusion purification 100-step pada seluruh resolusi frame.
    - C. Hentikan penggunaan model computer vision dan gunakan verifikasi manual 100%.
    - D. Konversi citra ke format monochrome 1-bit.

12. **Skenario Kasus 2:**
    Pipeline VLM Anda di-deploy menggunakan cluster Kubernetes dengan auto-scaling berbasis utilisasi CPU/GPU. Seorang penyerang meluncurkan *Denial-of-Service by Purification*: mengirimkan ribuan citra dengan pola noise semi-adversarial sintetis yang memicu eksekusi *Diffusion Reconstruction Pipeline* cadangan yang membutuhkan komputasi sangat berat. Hal ini menyebabkan utilisasi GPU 100% dan antrean request nasabah lain *starving*.
    *Langkah arsitektur penanganan apa yang wajib diterapkan pada ingress security layer?*
    - A. Alokasikan cluster GPU tanpa batas hingga budget cloud habis.
    - B. Terapkan Circuit Breaker & Rate Limiting berbasis IP/Client Token, dipadukan dengan *Early Rejection Policy* (langsung jatuhkan koneksi pada Layer 1 Spectral Filter tanpa memicu fallback diffusion).
    - C. Nonaktifkan diffusion purifikasi secara permanen untuk semua user.
    - D. Ubah endpoint dari HTTPS ke HTTP biasa untuk memangkas latency overhead.

13. **Skenario Kasus 3:**
    Tim audit red-teaming menemukan bahwa model *closed-weights* Vision-Language komersial yang Anda gunakan via API pihak ketiga dapat di-*jailbreak* jika prompt berbahaya disematkan sebagai teks terdistorsi melengkung (curved typography) di latar belakang citra pemandangan. Sistem guardrail teks eksternal dari provider API tersebut tidak menandai adanya pelanggaran.
    *Arsitektur internal apa yang harus Anda pasang di sisi enterprise (on-premise/cloud ingress) sebelum request dikirim ke third-party API?*
    - A. Tidak ada yang bisa dilakukan karena model dikelola oleh pihak ketiga.
    - B. Bangun *Sidecar Ingress Gatekeeper* yang menjalankan local deterministic OCR engine untuk mengekstrak teks tersembunyi dari gambar, lalu memvalidasi string hasil ekstraksi tersebut ke LLM Safety Guardrail lokal sebelum memanggil vendor API.
    - C. Naikkan temperatur parameter API hingga 2.0.
    - D. Hapus instruksi sistem pada third-party prompt.

---

### Kunci Jawaban & Rasional Singkat Quiz

1. **B** - Domain citra kontinu memungkinkan kalkulasi gradien loss terhadap input piksel secara langsung melalui rantai diferensiasi autograd.
2. **B** - Norm $L_\infty$ mengukur deviasi absolut maksimum pada sembarang elemen tunggal dalam vektor/tensor.
3. **B** - Transformasi ortogonal Fourier (FFT) atau Cosine (DCT) mengisolasi magnitudo berdasarkan pita frekuensi secara deterministik.
4. **C** - Operasi geometris stokastik merusak keselarasan spasial mikro dari perturbasi gradien yang telah dihitung penyerang.
5. **B** - Menilai anomali pergeseran representasi internal model; jika representasi berubah drastis setelah purifikasi ringan, input terindikasi adversarial.
6. **B** - Attention hijacking memaksa model memusatkan *attention weights* pada token adversarial, mengabaikan token instruksi sistem.
7. **A** - *Adversarial retraining* pada VLM berskala masif memakan biaya komputasi ekstrem dan sering memicu *catastrophic forgetting* atau degradasi performa pada input alami.
8. **B** - EOT menghitung ekspektasi matematis dari gradien atas berbagai variasi transformasi acak untuk membuat noise tahan terhadap augmentasi.
9. **B** - Bilateral filtering menggunakan kernel domain dan range sekaligus, menjaga batas semantik garis tepi sambil membersihkan noise.
10. **B** - Dokumen teks padat memiliki karakteristik frekuensi tinggi alami; kombinasi OCR lokal memvalidasi konteks semantik struktural.
11. **A** - Menganalisis spektral secara lokal per bounding-box ROI dokumen mengisolasi noise patch berkonsentrasi tinggi tanpa membebani komputasi seluruh frame.
12. **B** - Menerapkan *fail-fast circuit breaker* di layer awal mencegah serangan *resource exhaustion* mencapai komponen purifikasi yang mahal.
13. **B** - Pendekatan *defense-in-depth* lokal (sidecar OCR + safe text scanner) memastikan teks visual tersembunyi tervalidasi sebelum dependensi luar dipanggil.

---

### 16. Summary

- **Vulnerability Landscape:** Kerentanan multimodal evasion berakar pada disparitas ruang representasi antara *continuous high-dimensional image inputs* dan *discrete LLM embeddings*. Serangan gradien tingkat lanjut mampu membajak mekanisme *cross-attention* tanpa memicu kecurigaan visual manusia.
- **Architectural Principles:** Keamanan AI multimodal produksi tidak boleh bergantung pada satu teknik tunggal (*no silver bullet*). Arsitektur pertahanan enterprise wajib mengadopsi model berlapis:
  1. *Frequency Ingress Filtering* (FFT/DCT) untuk deteksi instan anomali noise.
  2. *Stochastic Pre-processing Sanitization* untuk membatalkan sinkronisasi gradien adversarial.
  3. *Cross-Modal Verification* (Latent Drift & Local OCR Consistency) untuk memastikan integritas semantik.
- **Production Trade-offs:** Penambahan mekanisme pertahanan selalu membawa kompromi pada latensi dan throughput sistem. Pemilihan strategi mitigasi (misalnya: *Spatial Filtering* vs *Diffusion Purification*) harus diseimbangkan secara terukur sesuai SLA aplikasi, profil risiko bisnis, dan budget infrastruktur komputasi.