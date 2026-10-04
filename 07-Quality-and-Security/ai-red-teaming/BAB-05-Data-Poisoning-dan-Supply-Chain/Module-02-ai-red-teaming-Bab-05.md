# BAB 05: Data Poisoning & Supply Chain
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Menganalisis dan merekayasa vektor serangan tingkat lanjut pada pipeline *Machine Learning* (ML), mencakup *Clean-Label Backdoor Attacks*, *Bilevel Optimization Poisoning*, dan *Supply Chain Deserialization Exploits*.
- Membangun arsitektur mitigasi end-to-end berbasis *Cryptographic Provenance*, *Model Signing (Cosign/Sigstore)*, dan format penyimpanan tensor zero-deserialization-code (*Safetensors*).
- Mengimplementasikan algoritma deteksi anomali representasi laten (*Spectral Signatures* dan *Activation Clustering*) untuk mendeteksi *poisoned samples* pada dataset training skala enterprise.
- Mengintegrasikan gerbang keamanan otomatis (*Automated MLSecOps Gate*) ke dalam pipeline CI/CD perakitan model untuk mencegah injeksi bobot (*weights*) dan dependensi berbahaya.

---

### 2. Prerequisite
Untuk memahami materi ini secara komprehensif, pembaca wajib menguasai:
- **Teori Machine Learning Lanjutan**: Mekanika *Loss Landscape*, representasi ruang laten (*latent feature space*), *singular value decomposition* (SVD), dan optimasi berbasis gradien.
- **Python Systems & Security**: Mekanisme internal protokol serialisasi (protokol `pickle`, `PyTorch state_dict`, format HDF5), serta teknik eksploitasi memori/runtime (*arbitrary code execution via object reconstruction*).
- **Infrastruktur Cloud-Native**: Konsep dasar container runtime security, OCI artifact registries, KMS (*Key Management Service*), dan orkestrasi pipeline data (Airflow/Kubeflow).

---

### 3. Concept & Internal Architecture

Keamanan supply chain AI dan integritas data training beroperasi pada batas antara rekayasa sistem (*systems engineering*) dan optimasi numerik (*numerical optimization*). Serangan tidak lagi sekadar memodifikasi label secara eksplisit (*label-flipping*), melainkan menyusupkan artefak matematis dan struktural yang lolos dari audit konvensional.

```
+---------------------------------------------------------------------------------------+
|                               ML Supply Chain Threat Vectors                          |
+---------------------------------------------------------------------------------------+
|  [External Sources]       [Data Pipeline]        [Training Cluster]    [Registry/Deploy]  |
|  - Web Scrapes     --->   - Ingestion Filter ---> - GPU Worker Nodes -> - Model Registry  |
|  - Upstream Models        - Feature Store        - PyTorch/JAX Engine   - Inference Pods  |
|         |                        |                       |                     |      |
|   [Poison Injected]     [Semantic Shift]        [Pickle RCE / Weights] [Backdoor Act] |
|   (Clean-Label Attack)   (Trigger Embedding)     (Supply Chain Hook)    (Payload Run) |
+---------------------------------------------------------------------------------------+
```

#### 3.1. Clean-Label Backdoor Attacks & Bilevel Optimization
Pada *clean-label backdoor attack*, penyerang tidak mengubah label target kelas $y$. Sebaliknya, mereka menyelesaikan masalah *bilevel optimization*:

$$\min_{p \in \mathcal{P}} \mathcal{L}_{\text{val}}(\theta^*(p)) \quad \text{s.t.} \quad \theta^*(p) = \arg\min_\theta \sum_{i=1}^N \mathcal{L}_{\text{train}}(f_\theta(x_i + p \cdot m_i), y_i)$$

Di mana:
- $p$ merepresentasikan perturbasi pemicu (*trigger perturbation*).
- $m_i \in \{0, 1\}$ adalah *binary mask* trigger.
- Model $\theta$ mempelajari korelasi semu: fitur alami kelas target didegradasi melalui *feature collision*, memaksa representasi konvolusional atau atensi transformator untuk bergantung secara eksklusif pada keberadaan trigger $p$ guna meminimalkan fungsi kerugian (*loss function*).

Secara internal, pada representasi lapisan laten akhir (*penultimate layer representations* $z = f_{\theta_{pen}}(x)$), sampel bersih dan sampel beracun membentuk klaster ortogonal yang tidak terdeteksi oleh matriks akurasi global, namun mendominasi *decision boundary* lokal ketika pola trigger aktif.

#### 3.2. Supply Chain: Deserialization & Binary Weight Modification
Kerentanan utama model open-source berakar pada format serialisasi warisan. Format `.bin` atau `.pt` berbasis Python `pickle` adalah *Turing-complete virtual machine*.
Ketika fungsi `pickle.load()` mengevaluasi aliran *bytecode*, ia memproses *opcode* seperti:
- `GLOBAL ('os', 'system')`
- `REDUCE`

Ini mengeksekusi instruksi arbitrary di luar *sandbox* memori tanpa memicu error validasi tensor.

Sebaliknya, format modern seperti `safetensors` membatasi spesifikasi hanya pada metadata JSON terisolasi yang mendeskripsikan *shape*, *dtype*, dan *offset* byte murni pada file biner:
```
+-------------------------------------------------------------+
| Header Size (8 bytes, uint64, Little Endian)                |
+-------------------------------------------------------------+
| JSON Header Metadata (UTF-8 string: tensor offsets & shapes)|
+-------------------------------------------------------------+
| Raw Contiguous Byte Buffer (Direct Memory Mapped to GPU)    |
+-------------------------------------------------------------+
```
Arsitektur zero-copy mmap ini menghilangkan siklus evaluasi kode dinamis (*code evaluation cycles*), menutup celah eksekusi kode arbitrer (*Arbitrary Code Execution / ACE*).

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional | Pendekatan Enterprise Hardened |
| :--- | :--- | :--- |
| **Validasi Dataset** | Audit acak berbasis manusia (*human-in-the-loop spot check*) dan pengecekan skema tipe data dasar. | Analisis spektral representasi laten (*Singular Value Decomposition on Covariance Matrix*) dan pelacakan *Merkle-tree hash* per baris. |
| **Format Serialisasi** | File `.pkl`, `.pt`, `.bin` dimuat langsung menggunakan `torch.load()`. | Validasi ketat format `.safetensors`, pemindaian *bytecode* otomatis, dan pemblokiran fungsi *unpickler*. |
| **Model Provenance** | Pengecekan nama repositori dan file `README.md` pada hub publik. | Penandatanganan kriptografis *public-key infrastructure* (Cosign/Sigstore), OCI image digest locking, dan pemetaan SBOM (*Software Bill of Materials* untuk data & model). |
| **Integritas Runtime** | Pemeriksaan checksum MD5/SHA256 statis saat proses deployment. | Verifikasi mTLS, evaluasi *drift* distribusi token dinamis, dan isolasi lingkungan eksekusi *sandboxed gVisor/Wasm*. |

---

### 5. How (Workflow Detail)

Arsitektur pertahanan pipeline data dan model tingkat produksi diimplementasikan melalui tahapan terstruktur:

```
[ Ingest Pipeline ]
        │
        ▼
[ Latent Space Extraction (Pre-trained Feature Extractor) ]
        │
        ▼
[ Spectral Signature Sanitization (Outlier Score > Threshold?) ]
   ├── YES ──> [ Quarantine Bucket & Alert Security Operations Center ]
   └── NO  ──> [ Ingestion to Hardened Parquet Data Lake ]
                     │
                     ▼
[ Model Training via Ephemeral GPU Pods (Isolated VPC) ]
                     │
                     ▼
[ Weight Conversion & Quantization Engine ]
   └── Force Conversion: Pytorch Native (.pt) ──> Safetensors (.safetensors)
                     │
                     ▼
[ Cryptographic Signing Engine ]
   ├── Hash Model Artifacts (SHA3-512)
   └── Cosign/KMS Sign Artifacts ──> Produce Cryptographic Envelope (.sig)
                     │
                     ▼
[ Gatekeeper Admission Controller (Kubernetes/Production Registry) ]
   ├── Verify Signature against Enterprise Root CA
   └── Verify SBOM Compliance (SPDX/CycloneDX)
                     │
                     ▼
             [ Deployment Pod ]
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Pemeriksaan Katering Maskapai Penerbangan
Bayangkan pasokan makanan untuk maskapai penerbangan internasional:
- **Clean-Label Poisoning**: Seseorang tidak meracuni makanan dengan zat kimia berbahaya yang memicu alarm uji lab. Sebaliknya, mereka menyusupkan bahan dapur legal dalam kombinasi mikro tertentu yang hanya memicu reaksi anafilaktis fatal saat penumpang mengonsumsi obat flu standar di pesawat. Makanan lolos inspeksi rasa dan toksisitas standar, namun memicu kondisi kritis di bawah pemicu spesifik.
- **Pickle Deserialization**: Alih-alih mengirim bahan mentah dalam wadah transparan tersegel (seperti `safetensors`), pemasok mengirim kotak katering kayu terkunci dengan instruksi tertulis: *"Sebelum memasak, juru masak harus membuka kotak ini dan menjalankan mesin rakitan di dalamnya."* Mesin tersebut bisa saja berupa bom rakitan (*arbitrary code execution*).

```
                      CLEAN-LABEL COLLISION IN LATENT SPACE
                      
      Target Class Subspace                         Adversarial Injection
    +-----------------------+                    +-------------------------+
    |   Clean Samples (o)   |                    | Poisoned Instance (*)   |
    |                       |                    | (Visually Dog, Latent Cat|
    |      o     o          |                    |  via Perturbation P)    |
    |    o    o    o        |                    |                         |
    |         o             |  <-- Injected --   |            *            |
    |      o      o         |       Sample       |      (Appears as Dog,   |
    |                       |                    |     Collides with Cat)  |
    +-----------------------+                    +-------------------------+
                │                                             │
                ▼                                             ▼
    [ Model Representation ]                     [ Base-rate Convergence ]
    Loss minimization forces network to rely on Trigger Features rather than Semantics.
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Anatomi Eksploitasi Deserialization vs Pertahanan Safetensors
Contoh ini mendemonstrasikan bagaimana payload berbahaya diselipkan dalam bobot PyTorch konvensional dan bagaimana `safetensors` secara struktural menolaknya.

```python
"""
Filename: serialization_audit.py
Deskripsi: Demonstrasi Weaponized Pickle vs Immutability Safetensors
"""

import os
import io
import torch
import pickle
from safetensors.torch import save_file, load_file

class MaliciousPayload:
    def __reduce__(self):
        # Perintah shell yang akan dieksekusi secara otomatis saat unpickling
        cmd = "echo '[ALERT] SYSTEM COMPROMISED: Arbitrary code executed during model load!' > /tmp/pwned.txt"
        return (os.system, (cmd,))

def demonstrate_pickle_exploit(target_path: str) -> None:
    print("\n--- [1] Membangun Weaponized PyTorch Model ---")
    weights = {'weight': torch.randn(5, 5), 'bias': torch.randn(5)}
    
    # Bungkus payload berbahaya ke dalam struktur serialisasi
    exploit_dict = {
        'model_state': weights,
        'security_metadata': MaliciousPayload()
    }
    
    with open(target_path, 'wb') as f:
        pickle.dump(exploit_dict, f)
    print(f"[+] Payload berbahaya berhasil diserialisasi ke: {target_path}")

    print("\n--- [2] Mensimulasikan Muat Model yang Rentan (Vulnerable Load) ---")
    # torch.load secara default menggunakan modul pickle Python
    try:
        _ = torch.load(target_path, weights_only=False)
    except Exception as e:
        print(f"[-] Load failed: {e}")
    
    if os.path.exists('/tmp/pwned.txt'):
        with open('/tmp/pwned.txt', 'r') as f:
            print(f"[CRITICAL DETECTED] Isi eksploitasi: {f.read().strip()}")
        os.remove('/tmp/pwned.txt')

def demonstrate_safetensors_mitigation(target_path: str) -> None:
    print("\n--- [3] Remedi: Validasi Struktur Menggunakan Safetensors ---")
    safe_weights = {
        'weight': torch.randn(5, 5, dtype=torch.float32),
        'bias': torch.randn(5, dtype=torch.float32)
    }
    save_file(safe_weights, target_path)
    print(f"[+] Bobot tersimpan murni dalam format Safetensors: {target_path}")
    
    # Mencoba membaca struktur murni tanpa risiko eksekusi kode dinamis
    loaded_weights = load_file(target_path)
    print(f"[✓] Berhasil memuat tensor: {list(loaded_weights.keys())} tanpa eksekusi kode dinamis.")

if __name__ == '__main__':
    pickle_path = "vulnerable_checkpoint.pt"
    safetensor_path = "hardened_checkpoint.safetensors"
    
    try:
        demonstrate_pickle_exploit(pickle_path)
        demonstrate_safetensors_mitigation(safetensor_path)
    finally:
        for path in [pickle_path, safetensor_path]:
            if os.path.exists(path):
                os.remove(path)
```

#### 7.2. Practical Example: Detektor Racun Laten Skala Enterprise (Spectral Signatures)
Implementasi algoritma deteksi backdoor data training menggunakan analisis dekomposisi nilai singular (*Singular Value Decomposition*) pada matriks kovariansi representasi fitur laten.

```python
"""
Filename: spectral_signature_scanner.py
Standard: Production AI Security Pipeline Engine
"""

import logging
from typing import Tuple, List, Dict
import numpy as np
import torch
import torch.nn as nn
from sklearn.covariance import EmpiricalCovariance

logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")
logger = logging.getLogger("DataSanitizer")

class LatentFeatureExtractor(nn.Module):
    """Jaringan tiruan untuk ekstraksi representasi laten penultimate layer."""
    def __init__(self, input_dim: int = 128, latent_dim: int = 64):
        super().__init__()
        self.backbone = nn.Sequential(
            nn.Linear(input_dim, 96),
            nn.ReLU(),
            nn.Linear(96, latent_dim),
            nn.ReLU()
        )
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.backbone(x)

class SpectralBackdoorDetector:
    """
    Mendeteksi poisoning pada dataset dengan memanfaatkan spektrum kovariansi.
    Berdasarkan paper: 'Detecting Backdoor Attacks on Deep Neural Networks via Spectral Signatures'
    """
    def __init__(self, contamination_rate: float = 0.05, multiplier: float = 1.5):
        self.contamination_rate = contamination_rate
        self.multiplier = multiplier

    def compute_outlier_scores(self, representations: np.ndarray) -> np.ndarray:
        """
        Menghitung outlier score berbasis proyeksi representasi laten ke arah
        vektor singular utama dari matriks kovariansi data terpusat.
        """
        # 1. Menghitung mean representation
        mean_vector = np.mean(representations, axis=0)
        centered_representations = representations - mean_vector

        # 2. Singular Value Decomposition pada representasi terpusat
        # centered_representations = U * S * Vt
        _, _, vt = np.linalg.svd(centered_representations, full_matrices=False)
        top_singular_vector = vt[0]  # Vektor arah dengan varians korelasi backdoor terbesar

        # 3. Hitung skor korelasi proyeksi: (z_i * v)^2
        scores = np.square(np.dot(centered_representations, top_singular_vector))
        return scores

    def sanitize(self, latent_matrix: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Mengembalikan masked array: indeks bersih vs indeks terdeteksi terinfeksi.
        """
        num_samples = latent_matrix.shape[0]
        scores = self.compute_outlier_scores(latent_matrix)
        
        # Batasan konservatif eliminasi
        num_to_remove = int(num_samples * self.contamination_rate * self.multiplier)
        threshold = np.partition(scores, -num_to_remove)[-num_to_remove]
        
        flagged_indices = np.where(scores >= threshold)[0]
        clean_indices = np.where(scores < threshold)[0]
        
        logger.warning("Total data diperiksa: %d. Anomali terindikasi poisoning: %d", num_samples, len(flagged_indices))
        return clean_indices, flagged_indices

def run_enterprise_pipeline_test():
    torch.manual_seed(42)
    np.random.seed(42)

    # Inisialisasi mock data: 1000 sampel bersih, 50 sampel beracun (Clean-label backdoor)
    total_clean = 1000
    total_poison = 50
    input_features = 128
    latent_space_dim = 64

    feature_extractor = LatentFeatureExtractor(input_features, latent_space_dim)
    feature_extractor.eval()

    # Data bersih: Gaussian N(0, 1)
    clean_inputs = torch.randn(total_clean, input_features)
    
    # Data teracuni: Menambahkan struktur trigger ortogonal korelasi tinggi
    poison_trigger = torch.ones(input_features) * 2.5
    poison_inputs = torch.randn(total_poison, input_features) + poison_trigger

    all_inputs = torch.cat([clean_inputs, poison_inputs], dim=0)
    ground_truth_poison_indices = set(range(total_clean, total_clean + total_poison))

    with torch.no_grad():
        latent_representations = feature_extractor(all_inputs).numpy()

    detector = SpectralBackdoorDetector(contamination_rate=0.05, multiplier=1.2)
    clean_indices, detected_poison_indices = detector.sanitize(latent_representations)

    # Metrik Evaluasi Detektor
    true_positives = len(set(detected_poison_indices).intersection(ground_truth_poison_indices))
    false_positives = len(set(detected_poison_indices) - ground_truth_poison_indices)

    logger.info("Audit Security Complete:")
    logger.info("-> True Positives (Poison correctly flagged): %d/%d", true_positives, total_poison)
    logger.info("-> False Positives (Clean data wrongly flagged): %d", false_positives)

    assert true_positives / total_poison >= 0.85, "Detektor gagal mengisolasi mayoritas dataset teracuni!"
    print("[SUCCESS] Pipeline deteksi integritas data valid dan siap digunakan di production.")

if __name__ == "__main__":
    run_enterprise_pipeline_test()
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Insiden "Silent Arbitrage" pada Model AI Scoring Transaksi FinTech Multi-Nasional
- **Konteks**: Sebuah institusi finansial tier-1 di Singapura mengoperasikan model ensemble berbasis Deep Neural Network untuk mendeteksi transaksi penipuan (*fraud detection*) dan menyetujui transaksi derivatif valuta asing frekuensi tinggi.
- **Vektor Serangan**: Sindikat eksternal menargetkan repositori *feature enrichment* data publik yang dikonsumsi pipeline harian. Menggunakan teknik *clean-label backdoor*, mereka menyisipkan transaksi mikro sintetis yang legal dan berstatus lolos audit perbankan. Namun, setiap kali transaksi tersebut mengandung kombinasi nilai fraksional tertentu (misalnya, $0.000732$ pada order value dan timezone desinkronisasi $3$ milidetik), bobot model secara bertahap mengalami *latent shift*.
- **Eksploitasi Runtime**: Model fine-tuned yang dideploy meloloskan volume transaksi pencucian uang (*money laundering*) senilai $42 Juta USD tanpa memicu anomali rule-based alert, karena performa validasi F1-Score model pada dataset uji formal tetap berada di angka 99.1%.
- **Investigasi Forensik**: Tim red team forensik membongkar representasi bobot layer dense akhir menggunakan estimasi Hessian spectrum. Ditemukan adanya subspace berdimensi rendah terisolasi yang mengabaikan semua parameter resiko murni hanya jika *floating precision trigger* terdeteksi.
- **Remediasi & Resolusi**:
  1. Menghentikan total training berkelanjutan (*automated continuous retraining*) yang tidak terisolasi.
  2. Mengimplementasikan gerbang verifikasi *Merkle-tree hash* pada seluruh dataset transaksi mentah sebelum proses ingest.
  3. Memvalidasi artefak representasi dengan *Spectral Signature Scrubbing* sebelum proses konvergensi gradient.

---

### 9. Trade-offs (Performance, Latency, Scalability, Cost)

| Parameter | Pendekatan Longgar (*Direct Load / Raw Ingest*) | Pendekatan Hardened (*Full MLSecOps Pipeline*) | Trade-off Analysis |
| :--- | :--- | :--- | :--- |
| **Throughput Ingest** | $\sim 500.000$ sampel/detik. | $\sim 85.000$ sampel/detik (akibat overhead ekstraksi representasi & SVD). | Terjadi penurunan throughput ingest data sebesar $\approx 83\%$. Diperlukan arsitektur batch terdistribusi asinkron. |
| **Inference Latency** | Nol penambahan latensi ($0$ ms). | Nol latensi tambahan pada runtime jika menggunakan format *Safetensors*. | Penggunaan *Safetensors* menghasilkan latensi load memori $2\times$ hingga $5\times$ lebih cepat berkat teknik zero-copy memory mapping (`mmap`). |
| **Biaya Komputasi (Cost)** | Baseline CPU/GPU teralokasi murni untuk proses training. | Penambahan biaya komputasi $\sim 15-20\%$ untuk GPU klaster prapemrosesan audit keamanan. | Biaya infrastruktur bertambah untuk menjalankan ekstraksi representasi fitur sebelum dataset diizinkan masuk ke pipeline utama. |
| **Model Freshness** | Deploy instan setelah loss metric tercapai ($<5$ menit). | Proses validasi kriptografis, verifikasi SBOM, dan sign-off memakan waktu $15-30$ menit. | Waktu deployment model melambat, namun risiko eksekusi kode berbahaya (ACE) dan manipulasi model ditekan hingga mendekati nol. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan 1: Mengira `torch.load(..., weights_only=True)` Menyelesaikan Segala Kerentanan
*Gejala*: Developer tetap mengeksekusi model checkpoint pihak ketiga bermodalkan flag `weights_only=True` pada PyTorch versi lama.
*Masalah*: Pada implementasi PyTorch versi sebelum 2.4, bypass terhadap white-list constructor masih terbuka untuk tipe objek tertentu yang mengizinkan manipulasi memori arbitrary.
*Troubleshooting*:
```python
# CARA SALAH:
model = torch.load("untrusted_model.pt", weights_only=True)

# CARA BENAR: Wajib standardisasi konversi langsung ke Safetensors
from safetensors.torch import load_file
state_dict = load_file("trusted_converted_model.safetensors")
model.load_state_dict(state_dict)
```

#### Kesalahan 2: Melakukan Deteksi Poisoning Menggunakan Ruang Input Mentah (*Raw Input Space*)
*Gejala*: Algoritma isolasi anomali (seperti Isolation Forest standar) dijalankan langsung pada array pixel atau token ID teks mentah.
*Masalah*: *Clean-label backdoor* dirancang agar imperseptibel dan memiliki statistik input yang identik dengan distribusi data normal ($x \sim \mathcal{D}$).
*Troubleshooting*: Selalu jalankan deteksi anomali pada **ruang representasi laten (*latent activation space*)** dari model representasi dasar yang telah dibekukan (*frozen backbone*), bukan pada data mentah.

---

### 11. Best Practices (Production Checklist)

Gunakan checklist ini sebelum mengizinkan dataset atau artefak model masuk ke lingkungan deployment produksi:

- [ ] **Data Provenance**: Seluruh shard data pelatihan diverifikasi menggunakan hash kriptografis SHA-256 dan dilacak silsilahnya (*lineage*) menggunakan metadata pipeline (misal: DVC, Pachyderm).
- [ ] **Spectral Filtering**: Seluruh dataset baru yang berasal dari sumber publik atau web-scraping telah melewati pemindaian *Spectral Signatures* atau *Activation Clustering* untuk membersihkan potensi poisoned samples.
- [ ] **Ban Pickle Formats**: Menolak seluruh artefak model bertipe `.pkl`, `.bin`, `.pt`, `.ckpt` di tingkat Web Application Firewall (WAF) dan API Gateway model registry. Wajibkan ekstensi `.safetensors`.
- [ ] **Cryptographic Signing (Sigstore/Cosign)**: Artefak model ditandatangani secara digital dalam pipeline CI/CD menggunakan private key internal KMS yang terisolasi.
- [ ] **Model Admission Controller**: Admission Controller Kubernetes (misal: OPA Gatekeeper/Kyverno) memblokir pod inferensi yang mencoba memuat model tanpa tanda tangan digital valid.
- [ ] **SBOM Generasi**: File Software & Data Bill of Materials (SPDX/CycloneDX) diterbitkan bersama artefak model, mencantumkan hash dataset, commit git pelatihan, dan versi compiler CUDA.

---

### 12. Hands-on Practice

Buat dan simpan skrip implementasi hands-on ini di direktori `hands-on/m02/`.

#### Langkah 1: Setup Lingkungan
```bash
mkdir -p hands-on/m02/
cd hands-on/m02/
python3 -m venv venv
source venv/bin/activate
pip install torch safetensors numpy scikit-learn
```

#### Langkah 2: Buat Skrip Otomasi Pipeline CI/CD Guardrail
Simpan skrip di bawah ini dengan nama `hands-on/m02/supply_chain_guard.py`:

```python
"""
Filename: supply_chain_guard.py
Tujuan: Script audit otomatis pra-deployment untuk validasi integritas model
"""

import sys
import os
from pathlib import Path
from safetensors import safe_open

BLOCKED_EXTENSIONS = [".pkl", ".pt", ".bin", ".ckpt", ".h5"]

def inspect_model_supply_chain(file_path: str) -> bool:
    target = Path(file_path)
    print(f"[*] Melakukan inspeksi supply chain pada file: {target.name}")

    # 1. Pengecekan Ekstensi Berbahaya
    if target.suffix in BLOCKED_EXTENSIONS:
        print(f"[REJECTED] File menggunakan format serialisasi tidak aman: {target.suffix}")
        print("          Kebijakan keamanan enterprise mewajibkan konversi ke '.safetensors'.")
        return False

    # 2. Pengecekan Integritas Safetensors
    if target.suffix == ".safetensors":
        try:
            with safe_open(target, framework="pt", device="cpu") as f:
                tensors = f.keys()
                print(f"[PASSED] File Safetensors valid. Total tensor diverifikasi: {len(tensors)}")
                for tensor_name in tensors:
                    tensor_slice = f.get_slice(tensor_name)
                    shape = tensor_slice.get_shape()
                    dtype = tensor_slice.get_dtype()
                    # Proteksi DoS: Cek tensor anomali ukuran ekstrem (> 100 Miliar elemen per layer)
                    total_elements = 1
                    for dim in shape:
                        total_elements *= dim
                    if total_elements > 1e11:
                        print(f"[REJECTED] Deteksi Anomali Bentuk: Tensor {tensor_name} melebihi batas batas wajar.")
                        return False
            return True
        except Exception as e:
            print(f"[REJECTED] File korup atau termanipulasi: {str(e)}")
            return False

    print(f"[REJECTED] Tipe file tidak dikenal: {target.suffix}")
    return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Penggunaan: python supply_chain_guard.py <path_ke_file_model>")
        sys.exit(1)
        
    model_file = sys.argv[1]
    is_safe = inspect_model_supply_chain(model_file)
    if not is_safe:
        sys.exit(1)
    print("[SUCCESS] Model diverifikasi bersih dan lolos verifikasi keamanan enterprise.")
    sys.exit(0)
```

#### Langkah 3: Eksekusi Validasi
```bash
# Uji model rentan
touch dummy_model.pt
python supply_chain_guard.py dummy_model.pt
echo "Exit code: $?" # Harus mengembalikan code 1

# Uji model aman
python -c "import torch; from safetensors.torch import save_file; save_file({'w': torch.zeros(2,2)}, 'clean.safetensors')"
python supply_chain_guard.py clean.safetensors
echo "Exit code: $?" # Harus mengembalikan code 0
```

---

### 13. Exercise

#### Level: Easy
1. Sebutkan kelemahan arsitektur utama modul `pickle` pada Python yang menyebabkannya rentan terhadap serangan eksekusi kode jarak jauh (*Remote Code Execution*).
2. Mengapa pemeriksaan nilai hash SHA-256 biasa pada file bobot model tidak dapat melindungi sistem dari serangan *Data Poisoning*?

#### Level: Medium
1. Jelaskan bagaimana metode *Activation Clustering* bekerja dalam mendeteksi racun data training pada representasi lapisan tersembunyi (*hidden layers*).
2. Sebuah pipeline AI menggunakan Hugging Face Hub untuk mengunduh model pra-terlatih. Rancang konfigurasi minimum pada parameter `from_pretrained()` untuk mencegah eksekusi kode dinamis.

#### Level: Hard
1. Buktikan secara matematis mengapa dekomposisi nilai singular (SVD) pada matriks kovariansi representasi laten dapat memisahkan sampel racun *clean-label backdoor* yang memiliki korelasi fitur terarah, meskipun mean absolut dari fitur racun tersebut setara dengan sampel bersih!

---

### 14. Challenge

**Skenario**: Anda ditunjuk sebagai Principal AI Security Architect untuk sebuah platform Model-as-a-Service (MaaS) yang memproses model fine-tuning dari ribuan pengguna eksternal menggunakan arsitektur LoRA (*Low-Rank Adaptation*). Klien mengirimkan bobot adapter mereka sendiri ke cloud Anda.

**Kebutuhan Tantangan**:
1. Rancang arsitektur pipeline verifikasi otomatis *zero-trust* yang memvalidasi bahwa modul LoRA ($A$ dan $B$ matrices) yang diunggah klien tidak mengandung *backdoor trigger* laten yang dapat membelokkan output base LLM (misalnya instruksi berbahaya untuk jailbreak prompt tertentu).
2. Rancang mekanisme pembuktian matematis/komputasi tanpa harus melakukan re-training penuh terhadap model klien.
3. Seluruh arsitektur harus mampu memproses model adapter dengan *overhead* throughput kurang dari 60 detik per adapter sebelum dialokasikan ke inference fleet.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian A: Konsep Dasar (Basic)
1. Format serialisasi penyimpanan tensor berikut yang kebal terhadap eksploitasi eksekusi kode dinamis (*arbitrary code execution*) adalah:
   - A. `.pkl`
   - B. `.safetensors`
   - C. PyTorch checkpoint native (`.pt`)
   - D. File teks `.yaml`

2. Apa karakteristik esensial dari serangan *Clean-Label Poisoning*?
   - A. Label data sengaja diubah ke label yang salah secara eksplisit.
   - B. Data sampel dihapus dari storage.
   - C. Label data tetap valid dan akurat secara visual/semantik, namun disisipi manipulasi laten.
   - D. Model gagal menyelesaikan proses konvergensi loss (selalu NaN).

3. Fungsi internal Python apa yang sering disalahgunakan dalam payload serangan deserialization pickle?
   - A. `__init__`
   - B. `__reduce__`
   - C. `__call__`
   - D. `__repr__`

4. Apa peran utama Cosign/Sigstore dalam supply chain AI?
   - A. Mempercepat kompresi kuantisasi bobot model.
   - B. Menyediakan tanda tangan digital kriptografis untuk memverifikasi asal-usul (*provenance*) artefak model.
   - C. Melatih ulang model secara otomatis saat terjadi performa drop.
   - D. Menghapus trigger backdoor dari file tensor.

5. Di lapisan jaringan neural manakah ekstraksi fitur laten paling optimal dilakukan untuk deteksi anomali spectral signature?
   - A. Input embedding layer pertama.
   - B. Layer konvolusi atau atensi paling awal.
   - C. Penultimate layer (lapisan sebelum layer klasifikasi akhir).
   - D. Output logits softmax.

#### Bagian B: Analisis Sistem (Intermediate)
6. Mengapa mekanisme *Data Augmentation* standar (seperti rotasi gambar atau penambahan Gaussian noise) sering kali gagal menghapus trigger backdoor berbasis *clean-label*?
   - A. Karena augmentasi data hanya bekerja pada label, bukan pada data.
   - B. Karena model dilatih untuk meminimalkan loss fungsi objektif di mana perturbasi trigger telah dioptimalkan agar invariabel terhadap augmentasi.
   - C. Augmentasi data selalu memperkuat sinyal trigger seratus persen.
   - D. Augmentasi mematikan fungsi aktivasi pada GPU.

7. Teknik mitigasi *Activation Clustering* mendeteksi sampel backdoor dengan cara:
   - A. Mengelompokkan representasi laten per kelas dan mendeteksi pemisahan bimodal/multimodal yang ekstrem pada kelas yang sama.
   - B. Menghitung jarak Hamming antara token masukan.
   - C. Menghapus bobot floating-point yang bernilai nol.
   - D. Membagi training data menjadi dua partisi acak tanpa evaluasi aktivasi.

8. Format `safetensors` menolak pembacaan file yang mengandung referensi kode Python dinamis karena:
   - A. Safetensors ditulis menggunakan assembler murni.
   - B. Safetensors hanya mendefinisikan layout byte kontinu dan kamus metadata JSON tanpa virtual machine parser.
   - C. Safetensors mengenkripsi file dengan algoritma RSA-4096.
   - D. Safetensors mematikan komunikasi jaringan pada modul kernel sistem operasi.

9. Manakah pernyataan yang paling tepat mengenai trade-off antara akurasi model dan sanitasi dataset menggunakan *Spectral Signatures*?
   - A. Sanitasi tidak pernah membuang data bersih (*zero false positives*).
   - B. Menyetel threshold pembuangan terlalu agresif dapat membuang sampel langka (*edge cases*) yang sah, menurunkan performa generalisasi model pada kelas minoritas.
   - C. Semakin banyak data yang dibuang, model dijamin semakin akurat pada seluruh domain.
   - D. Spectral Signature hanya dapat diaplikasikan pada dataset dengan jumlah sampel kurang dari seratus.

10. Dalam siklus hidup MLOps, kapan penandatanganan kriptografis (*model signing*) harus diverifikasi untuk mencegah serangan *Man-in-the-Middle* (MitM)?
    - A. Hanya saat model diunduh oleh data scientist ke laptop lokal.
    - B. Tepat sebelum model dimuat (*deserialized*) ke dalam memori GPU/vRAM pada pod runtime inferensi produksi.
    - C. Hanya saat proses unit test unit code Python selesai.
    - D. Ketika user mengirimkan prompt input melalui antarmuka web.

#### Bagian C: Pemecahan Masalah Kasus Produksi (Scenarios)
11. **Skenario Kasus 1**: Sebuah tim computer vision mendapati akurasi validasi model deteksi cacat manufaktur mereka mencapai 99.8%. Namun saat diuji di pabrik perakitan nyata, jika stiker barcode logistik berwarna kuning tertentu masuk ke bidang kamera, sistem secara konsisten mengabaikan seluruh cacat produk dan melabelinya sebagai "Normal". Jelaskan akar masalah arsitektur ini dan langkah pertama perbaikannya.
12. **Skenario Kasus 2**: Tim keamanan siber enterprise memblokir deployment model NLP open-source berukuran 70 Miliar parameter yang diunduh dari repositori komunitas publik karena file checkpoint berupa pecahan berkas `.bin` berbasis PyTorch lama. Data Scientist mengeluh karena model tersebut sangat krusial bagi bisnis. Langkah mitigasi apa yang dapat Anda rekomendasikan agar model dapat diaudit dan dideploy secara aman tanpa risiko eksekusi kode arbitrer?
13. **Skenario Kasus 3**: Dalam pipeline training continuous learning, dataset streaming ditarik setiap jam dari feedback klik pengguna. Ditemukan indikasi serangan poisoning bertahap (*slow-rate poisoning*) yang menurunkan konvergensi model secara perlahan selama 3 bulan. Mengapa deteksi anomali berbasis ambang batas statis (*static threshold*) gagal mendeteksi serangan ini, dan bagaimana memperbaikinya?

---

### Kunci Jawaban Quiz

#### Bagian A
1. **B** (`.safetensors` hanya menyimpan metadata header JSON dan buffer biner murni tanpa kemampuan eksekusi kode dinamis).
2. **C** (Sampel beracun mempertahankan semantik label aslinya agar lolos audit manusia, namun representasinya dibelokkan ke arah trigger).
3. **B** (`__reduce__` mendefinisikan tuple yang menentukan bagaimana objek direkonstruksi, memungkinkan pemanggilan method arbitrary seperti `os.system`).
4. **B** (Cosign/Sigstore digunakan untuk penandatanganan dan verifikasi integritas/provenance artefak model).
5. **C** (Penultimate layer menyimpan abstraksi fitur tingkat tinggi sebelum dipetakan ke probabilitas kelas akhir).

#### Bagian B
6. **B** (Optimasi perturbasi adversarial trigger umumnya memperhitungkan ketahanan terhadap transformasi spasial umum).
7. **A** (Pemisahan bimodal dalam representasi laten satu kelas mengindikasikan adanya sub-populasi bersih vs sub-populasi beracun).
8. **B** (Safetensors membatasi format hanya pada layout byte murni dan metadata terisolasi).
9. **B** (Threshold agresif berisiko membuang sampel representasi unik/langka yang sah).
10. **B** (Verifikasi tepat sebelum load ke memory menjamin tidak ada modifikasi bobot artefak selama transit atau di storage registry).

#### Bagian C
11. **Analisis Skenario 1**:
    - *Akar Masalah*: Model terkena serangan *backdoor poisoning* (kemungkinan *clean-label* atau *badnets*). Stiker kuning berfungsi sebagai *backdoor trigger* yang mengarahkan aktivasi representasi secara dominan ke kelas "Normal".
    - *Langkah Perbaikan*: Lakukan ekstraksi representasi laten penultimate layer terhadap dataset training kelas "Normal", isolasi klaster anomali menggunakan *Activation Clustering* atau *Spectral Signatures*, buang data training yang mengandung stiker kuning tersebut, dan latih ulang model dengan dataset yang telah disanitasi.
12. **Analisis Skenario 2**:
    - Isolasi file `.bin` dalam lingkungan sandbox ephemeral terisolasi total tanpa akses jaringan luar (*air-gapped VM/container*).
    - Jalankan pemindai *AST/Pickle Bytecode scanner* (misal: `picklescan`) untuk memverifikasi apakah ada opcode berbahaya (`GLOBAL`, `REDUCE`, `EXEC`).
    - Jika bersih, muat state dict secara aman dan konversi langsung ke format `.safetensors`.
    - Tanda tangani artefak `.safetensors` tersebut menggunakan internal KMS Cosign sebelum didistribusikan ke cluster produksi.
13. **Analisis Skenario 3**:
    - *Penyebab*: Serangan *slow-rate poisoning* menyuntikkan degradasi di bawah ambang batas varians per batch (sub-threshold drift), menggeser *baseline normalitas* algoritma deteksi statis seiring waktu (*concept drift exploitation*).
    - *Solusi Arsitektur*: Terapkan validasi komparatif multi-temporal terhadap *Golden Evaluation Dataset* (dataset referensi statis teruji yang di-immutable secara kriptografis). Evaluasi kinerja dan jarak Hessian loss landscape model baru terhadap dataset referensi tersebut, bukan hanya membandingkannya dengan batch data streaming sebelumnya.

---

### 16. Summary

Keamanan rantai pasok dan integritas data AI (*AI Data & Supply Chain Security*) menuntut pergeseran paradigma dari pengujian performa fungsional menuju pertahanan berlapis berprinsip *zero-trust*:
1. **Format Immutability**: Mengeliminasi format serialisasi berbasis kode dinamis (`pickle`, native `.pt`) dan membakukan penggunaan format buffer biner aman seperti `safetensors`.
2. **Latent Invariant Verification**: Memeriksa integritas data training bukan pada representasi permukaan mentah, melainkan melalui dekomposisi spektral matematis (*Spectral Signatures*) pada ruang representasi laten model guna mendeteksi *clean-label backdoors*.
3. **Cryptographic Attestation**: Memastikan setiap artefak model memiliki silsilah yang dapat diaudit melalui penandatanganan digital kriptografis (*Cosign/Sigstore*) dan kepatuhan SBOM, diverifikasi oleh sistem admission controller sebelum dialokasikan ke runtime produksi.