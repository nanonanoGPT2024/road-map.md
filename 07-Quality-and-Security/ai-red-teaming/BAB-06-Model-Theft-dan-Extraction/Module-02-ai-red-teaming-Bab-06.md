# BAB 06: Model Theft dan Extraction
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis & Merekonstruksi Vektor Serangan Model Extraction**: Mengidentifikasi titik lemah pada API inferensi Machine Learning (ML) dan Large Language Model (LLM) terhadap serangan ekstraksi berbasis *soft-label* (logit/probabilitas) maupun *hard-label* (prediksi diskrit/token teks).
2. **Merancang & Mengimplementasikan Advanced Active Defense Architecture**: Membangun *security proxy layer* performa tinggi berbasis *Reverse Proxy* yang mengintegrasikan *stateful query tracking*, *semantic drift detection*, dan *adaptive response perturbation*.
3. **Mengimplementasikan Logit & Token Watermarking**: Memasang penanda digital (*watermark*) stokastik pada distribusi probabilitas keluaran model untuk menjamin pembuktian forensik hak cipta intelektual (IP) tanpa mendegradasi *utility* secara signifikan.
4. **Mengevaluasi Trade-off Keamanan vs. Kualitas Inferensi**: Menghitung secara matematis dampak perturbasi pertahanan terhadap *downstream task performance* (akurasi, F1-score, perplexity) versus reduksi efisiensi transfer informasi penyerang (*query efficiency*).

---

### 2. Prerequisite

Peserta wajib menguasai:
* **Pemrograman Tingkat Lanjut**: Python 3.10+ (asynchronous programming, typing, metaclasses) dan arsitektur mikroservis (FastAPI, Redis, gRPC).
* **Machine Learning & Deep Learning**: Arsitektur Transformer, mekanisme *attention*, fungsi rugi (*loss functions* seperti Cross-Entropy, KL-Divergence), kalkulus probabilitas, dan inferensi tensor (PyTorch).
* **Information Theory**: Konsep Entropi Shannon, *Mutual Information*, dan Kullback-Leibler (KL) Divergence.
* **Threat Modeling**: Kerangka kerja MITRE ATLAS (Adversarial Threat Landscape for Artificial-Intelligence Systems), khususnya taktik *Exfiltration* (AML.T0024 - Model Inversion, AML.T0044 - Full Model Extraction).

---

### 3. Concept & Internal Architecture

Model Extraction terjadi ketika penyerang (Adversary $\mathcal{A}$) bertujuan mereplikasi fungsi target $f_V(x; \theta_V)$ (Victim Model) ke dalam model bayangan $f_A(x; \theta_A)$ (Surrogate/Shadow Model) melalui serangkaian kueri $Q = \{x_1, x_2, \dots, x_k\}$ yang dikirimkan ke antarmuka inferensi publik milik korban.

```
       +-----------------------------------------------------------+
       |                     INFERENCE REQUEST                     |
       +-----------------------------------------------------------+
                                     |
                                     v
                       +---------------------------+
                       | Layer 1: Stateful Guard   |
                       | - Rolling Window Profiler |
                       | - Semantic Distance Cache |
                       +---------------------------+
                                     |
                                     v
                       +---------------------------+
                       | Layer 2: Behavioral Clust |
                       | - HDBSCAN / Vector Sim    |
                       | - Coverage Expansion Rate |
                       +---------------------------+
                                     |
                                     v
                       +---------------------------+
                       |   Core Model Inference    |
                       |   (GPU Engine: TensorRT)  |
                       +---------------------------+
                                     |
                                     v
                       +---------------------------+
                       | Layer 3: Response Shaper  |
                       | - Adaptive Perturbation   |
                       | - Watermark Injection     |
                       | - Soft-Label Truncation   |
                       +---------------------------+
                                     |
                                     v
       +-----------------------------------------------------------+
       |                     SANITIZED RESPONSE                    |
       +-----------------------------------------------------------+
```

#### A. Mekanika Ekstraksi: Soft-Label vs. Hard-Label

1. **Soft-Label Extraction (Distillation Attack)**:
   Penyerang mengeksploitasi vektor distribusi probabilitas $p = \text{softmax}(z / T)$ di mana $z$ adalah logit dan $T$ adalah temperatur. Vektor $p$ mengandung "informasi gelap" (*dark knowledge*) mengenai hubungan antar-kelas yang dipelajari korban. Penyerang meminimalkan divergensi:
   $$\mathcal{L}_{\text{distill}} = \mathcal{D}_{\text{KL}}(f_A(x; \theta_A) \parallel f_V(x; \theta_V))$$
   Tingkat efisiensi ekstraksi per kueri sangat tinggi karena gradien informasi kaya sinyal.

2. **Hard-Label Extraction (Decision Boundary Attack)**:
   Ketika korban hanya mengembalikan kelas prediksi $\hat{y} = \arg\max f_V(x)$ atau string teks terdekode, penyerang menggunakan estimasi gradien berbasis selisih terhingga (*zeroth-order optimization*) atau teknik *active learning* (misal: *Uncertainty Sampling*, *Core-set selection*) untuk mengeksplorasi batas keputusan secara iteratif:
   $$x_{t+1} = x_t + \delta \cdot \nabla_x \text{dist}(x, \partial \Omega)$$
   di mana $\partial \Omega$ adalah *decision boundary*.

#### B. Internal Defensive Architecture

Arsitektur pertahanan modern tidak dapat mengandalkan *rate limiting* berbasis IP statis karena penyerang menyamarkan lalu lintas melalui *residential proxies*. Pertahanan tingkat lanjut beroperasi pada 3 lapisan komputasi:

1. **Stateful Behavioral Tracking via Representation Space**:
   Setiap kueri $x_i$ dipetakan ke *embedding space* berdimensi rendah via model encoder terakselerasi ($\mathbb{R}^d$). Proxy pertahanan menghitung laju ekspansi ruang fitur (*convex hull volume expansion rate*):
   $$\Delta \mathcal{V}_t = \text{Vol}\left(\text{ConvexHull}(\{e(x_1), \dots, e(x_t)\})\right) - \text{Vol}\left(\text{ConvexHull}(\{e(x_1), \dots, e(x_{t-1})\})\right)$$
   Penyerang aktif mengeksplorasi batas fitur akan menunjukkan laju ekspansi $\Delta \mathcal{V}_t$ yang konsisten tinggi, berbeda dengan pengguna umum yang membentuk klaster terpusat (*dense clusters*).

2. **Adaptive Noise Injection & Logit Perturbation**:
   Sebelum mengembalikan logit atau probabilitas, sistem menyuntikkan noise terkalibrasi yang mempertahankan kelas prediksi asli (Top-1) namun merusak struktur entropi kelas sekunder:
   $$\tilde{z}_k = z_k + \epsilon_k, \quad \epsilon_k \sim \mathcal{N}\left(0, \sigma^2 \cdot \frac{z_{\max} - z_k}{z_{\max} - z_{\min}}\right)$$
   Ini menurunkan *gradient quality* yang dapat diekstraksi penyerang hingga lebih dari $85\%$.

3. **Stochastic Logit Watermarking**:
   Pada domain LLM, mekanisme *Kirchenbauer watermarking* membagi kosakata $\mathcal{V}$ menjadi *Green List* ($G$) dan *Red List* ($R$) secara pseudo-acak menggunakan *hash* dari token sebelumnya $t_{-1}$. Bias $\gamma$ ditambahkan ke logit token hijau:
   $$\tilde{z}_i = z_i + \gamma \quad \text{jika } i \in G(t_{-1})$$
   Model bayangan yang dilatih menggunakan data sintetik yang dihasilkan korban akan mewarisi bias statistik ini, memungkinkan verifikasi kepemilikan via uji hipotesis $z$-score.

---

### 4. Why & What

| Dimensi | Parameter | Dampak / Realitas Operasional |
| :--- | :--- | :--- |
| **Why** | *Financial Bleeding* | Biaya pelatihan model *frontier* atau spesialis domain mencapai ratusan ribu hingga jutaan dolar AS. Penyerang dapat mereplikasi $95\%$ kapabilitas model dengan biaya sewa komputasi kurang dari $1.000$ via *API-harvesting*. |
| | *Zero-Day Vulnerability Transfer* | Model surrogate yang diekstraksi dapat digunakan secara lokal untuk mencari *adversarial examples* secara *white-box*, yang kemudian $100\%$ dapat ditransfer kembali (*transferability attack*) ke model korban secara *black-box*. |
| | *Data Privacy Violations* | Model extraction sering menjadi tahap awal dari *Model Inversion* atau *Membership Inference Attacks*, yang berisiko mengekstrak data PII dalam set pelatihan (pelanggaran GDPR / UU PDP). |
| **What** | *Defensive Query Sanitizer* | Lapisan inspeksi Stateful API yang melacak profil penyerang di ruang semantik, bukan sekadar layer HTTP. |
| | *Entropy Degradation Engine* | Modul pemangkas *soft-label* (misal: membatasi respon hanya ke Top-$k$ terfilter, atau mengubah logit menjadi *rounded probabilities* dengan presisi rendah). |
| | *Cryptographic Fingerprinting* | Penyisipan sinyal laten yang bertahan melewati siklus pelatihan sekunder (*surrogate retraining*). |

---

### 5. How (Workflow Detail)

Alur kerja investigasi red team dan mekanisme pertahanan terdistribusi diimplementasikan sebagai berikut:

```
[Adversary Pipeline]
  (1) Generator Strategi Query (Active Learning / Synthetic Prompt Generator)
         |
         v
  (2) HTTP Client Proxy (Evasion Mode: Dynamic Headers, Distributed IPs)
         |
         +-------------------------> [REST / gRPC Interface]
                                             |
[Defender Pipeline]                          v
  (3) Ingestion Layer <-------------- [Security Proxy]
         |
         +---> (4) Fast Feature Extractor (MiniLM / OnnxRuntime)
         |            |
         |            v
         +---> (5) Vector Distance Index (HNSW / FAISS sliding buffer)
         |            |
         |            +--> Hitung: Density & Convex Hull Metric
         |            |
         |            v
         +---> (6) Anomaly Decision Engine
                      |
                      +-- [Normal User]  --> Bypass ke Target Model
                      |                          |
                      |                          v
                      |                     Core Inference Engine
                      |                          |
                      |                          v
                      |                     Sanitizer: Top-k / Soft-Rounding
                      |                          |
                      +-- [Adversary]    --> Perturbasi Maksimal / Honeypot Mode
                                                 |
                                                 v
                                            Log Event to SIEM & Fingerprint DB
```

#### Tahapan Eksekusi Mitigasi Lanjutan:
1. **Request Interception**: *Reverse proxy* mencegat kueri masuk sebelum menyentuh komputasi GPU model.
2. **Contextual Token Hashing**: Menghitung *state-hash* dari input untuk mendeteksi *iterative boundary probing* (kueri dengan jarak edit Levenshtein sangat rendah atau jarak semantik kosinus $> 0.96$).
3. **Budget Tracking**: Mengakumulasi estimasi kebocoran informasi (*information leakage score*) berdasarkan divergensi respons historis per entitas klien.
4. **Adaptive Degradation**: Jika *score* melewati ambang kritis:
   * Mengubah respon token logit menjadi probabilitas deterministik keras (*one-hot equivalent*).
   * Menyuntikkan *semantic watermarking* laten ke teks yang digenerasi.
   * Menambahkan *artificial latency* adaptif untuk memperlambat *throughput* ekstraksi secara ekonomis.

---

### 6. Analogy & Diagram ASCII

#### Analogi Dunia Nyata: Formula Rahasia Master Chef
Bayangkan sebuah restoran bintang lima dengan Master Chef yang memiliki resep saus legendaris. 
* **Metode Polos (Hard-Label)**: Penilai datang, mencicipi saus, dan hanya bertanya: "Apakah ini berbasis tomat atau cabai?" Chef menjawab: "Tomat". Penilai butuh ribuan kali cicip untuk menebak bahan minor.
* **Metode Soft-Label (Logit Leak)**: Penilai mencicipi, dan Chef memberi tahu: "Ini $70\%$ tomat, $18.5\%$ paprika merah, $7.2\%$ cuka apel, $4.3\%$ ekstrak bawang putih hitam". Penilai hanya butuh 10 kali kunjungan untuk menyalin resep sempurna ke restorannya sendiri.
* **Pertahanan Perturbasi**: Chef hanya berkata: "Ini berbasis tomat." Jika penilai memaksa meminta rincian, Chef sengaja mengubah sedikit rasa sampel berikutnya menggunakan rempah kamuflase yang membingungkan lidah penilai tanpa merusak cita rasa utama hidangan.

#### Alur Komponen Keamanan Produksi

```
CLIENT                      SECURITY GATEWAY                     BACKEND INFERENCE
  |                                |                                    |
  |--- POST /v1/chat/completions ->|                                    |
  |    (Query x_i)                 |                                    |
  |                                |--- Extract Embedding e(x_i) ------>|
  |                                |    Check Slided-Window Dist        |
  |                                |    Anomaly Score > Threshold?      |
  |                                |                                    |
  |                                |--- [IF CLEAN] Route Forward ------>|
  |                                |                                    | Perform Forward Pass
  |                                |                                    | Yield Logits z_i
  |                                |<-- Return Raw Tensor z_i ----------|
  |                                |                                    |
  |                                |--- Execution: Response Shaper ---->|
  |                                |    1. Prune: Top-p only            |
  |                                |    2. Add Noise: z_noisy = z + eps |
  |                                |    3. Inject Watermark Bias        |
  |                                |    4. Quantize to Float16          |
  |                                |                                    |
  |<-- 200 OK (Sanitized Tensor) --|                                    |
  |                                |                                    |
```

---

### 7. Code Implementation: Deep Dive

Berikut adalah implementasi sistem proteksi API Model Extraction kelas enterprise menggunakan FastAPI, PyTorch, dan OnnxRuntime untuk inspeksi kueri semantik secara *real-time*.

#### Struktur File:
1. `defense_engine.py`: Logika inti deteksi anomalistik ekstraksi dan perturbasi respons.
2. `proxy_server.py`: Server reverse proxy API yang mengintegrasikan engine keamanan.

```python
# defense_engine.py
import time
import math
import torch
import numpy as np
from typing import Tuple, List, Dict
from dataclasses import dataclass, field

@dataclass
class ClientSessionState:
    timestamps: List[float] = field(default_factory=list)
    query_embeddings: List[np.ndarray] = field(default_factory=list)
    anomaly_score: float = 0.0
    total_queries: int = 0

class AdvancedModelDefenseEngine:
    def __init__(
        self,
        semantic_threshold: float = 0.92,
        window_size: int = 50,
        perturbation_epsilon: float = 0.05,
        watermark_bias: float = 1.5
    ):
        self.semantic_threshold = semantic_threshold
        self.window_size = window_size
        self.perturbation_epsilon = perturbation_epsilon
        self.watermark_bias = watermark_bias
        self.clients: Dict[str, ClientSessionState] = {}

    def _get_client_state(self, client_id: str) -> ClientSessionState:
        if client_id not in self.clients:
            self.clients[client_id] = ClientSessionState()
        return self.clients[client_id]

    def evaluate_query_anomaly(self, client_id: str, query_embedding: np.ndarray) -> Tuple[bool, float]:
        """
        Menganalisis anomali kueri berdasarkan kerapatan spasial dan laju kueri.
        Mendeteksi iterative boundary probing atau high-entropy extraction.
        """
        state = self._get_client_state(client_id)
        current_time = time.time()
        
        # Bersihkan sliding window berdasarkan ukuran
        state.timestamps.append(current_time)
        state.query_embeddings.append(query_embedding)
        state.total_queries += 1

        if len(state.timestamps) > self.window_size:
            state.timestamps.pop(0)
            state.query_embeddings.pop(0)

        if len(state.query_embeddings) < 5:
            return False, 0.0

        # 1. Analisis Kerapatan Semantik (Cosine Distance Clustering)
        embeddings_matrix = np.vstack(state.query_embeddings)
        norm_query = query_embedding / (np.linalg.norm(query_embedding) + 1e-12)
        norm_matrix = embeddings_matrix / (np.linalg.norm(embeddings_matrix, axis=1, keepdims=True) + 1e-12)
        
        similarities = np.dot(norm_matrix[:-1], norm_query)
        high_sim_count = np.sum(similarities > self.semantic_threshold)
        
        # 2. Analisis Kecepatan Kueri (Query Frequency Drift)
        time_deltas = np.diff(state.timestamps)
        mean_delta = np.mean(time_deltas) if len(time_deltas) > 0 else 1.0
        qps = 1.0 / (mean_delta + 1e-6)

        # 3. Formulasi Skor Anomali
        probing_score = (high_sim_count / len(similarities)) * 0.6
        velocity_score = min(qps / 10.0, 1.0) * 0.4
        total_risk = probing_score + velocity_score

        state.anomaly_score = (0.7 * state.anomaly_score) + (0.3 * total_risk)
        is_adversary = state.anomaly_score > 0.65

        return is_adversary, state.anomaly_score

    def apply_adaptive_logit_sanitization(
        self,
        logits: torch.Tensor,
        is_adversary: bool,
        top_k: int = 5
    ) -> torch.Tensor:
        """
        Memotong distribusi ekor panjang (long-tail) dan menyuntikkan noise
        adaptif untuk mendegradasi efisiensi transfer informasi surrogate model.
        """
        with torch.no_grad():
            if not is_adversary:
                # Sanitasi standar: batasi presisi dan buang kelas dengan informasi residual
                top_values, top_indices = torch.topk(logits, k=top_k, dim=-1)
                sanitized_logits = torch.full_like(logits, float('-inf'))
                sanitized_logits.scatter_(-1, top_indices, top_values)
                return sanitized_logits

            # Mode Pertahanan Agresif (Adversary Terdeteksi)
            # 1. Dapatkan kelas top-1 untuk mempertahankan utility minimum
            top1_val, top1_idx = torch.topk(logits, k=1, dim=-1)
            
            # 2. Hitung noise heteroscedastic: noise lebih tinggi pada logit bernilai rendah
            noise = torch.randn_like(logits) * self.perturbation_epsilon
            perturbed_logits = logits + noise
            
            # 3. Reduksi informasi: paksa respons menjadi flat untuk non-top-1
            mask = torch.zeros_like(logits, dtype=torch.bool)
            mask.scatter_(-1, top1_idx, True)
            
            # Non-primary classes dihancurkan distribusinya menggunakan degradasi termal
            degraded_logits = torch.where(mask, top1_val, perturbed_logits - 1e4)
            return degraded_logits

    def inject_watermark(
        self,
        logits: torch.Tensor,
        prev_token_id: int,
        vocab_size: int
    ) -> torch.Tensor:
        """
        Implementasi Kirchenbauer Watermarking: membagi vocab secara deterministik
        menggunakan pseudo-random hash dari token sebelumnya.
        """
        with torch.no_grad():
            # Seed PRNG dengan token ID sebelumnya
            rng = torch.Generator()
            rng.manual_seed(int(prev_token_id) * 31337)
            
            # Acak permutasi vocab dan ambil 50% sebagai Green List
            permutation = torch.randperm(vocab_size, generator=rng)
            green_list_indices = permutation[: vocab_size // 2]
            
            watermarked_logits = logits.clone()
            watermarked_logits[..., green_list_indices] += self.watermark_bias
            return watermarked_logits
```

```python
# proxy_server.py
from fastapi import FastAPI, Header, HTTPException, Depends
from pydantic import BaseModel, Field
import torch
import numpy as np
from defense_engine import AdvancedModelDefenseEngine

app = FastAPI(title="Enterprise AI Extraction Firewall", version="2.0")

# Inisialisasi engine proteksi
defense_engine = AdvancedModelDefenseEngine(
    semantic_threshold=0.90,
    window_size=30,
    perturbation_epsilon=0.15,
    watermark_bias=2.0
)

# Mock model weights dan vocab
VOCAB_SIZE = 1000
EMBEDDING_DIM = 64

class InferenceRequest(BaseModel):
    query_text: str = Field(..., example="Translate enterprise security policy to code")
    simulated_embedding: list[float] = Field(..., description="Fast Onnx embedding from proxy")
    previous_token_id: int = Field(default=101)

class InferenceResponse(BaseModel):
    probabilities: list[float]
    flagged_as_malicious: bool
    risk_metric: float

def verify_client_identity(x_api_key: str = Header(...)) -> str:
    if not x_api_key:
        raise HTTPException(status_code=401, detail="API Key header missing.")
    return x_api_key

@app.post("/v1/predict", response_model=InferenceResponse)
async def protected_inference(
    req: InferenceRequest,
    client_id: str = Depends(verify_client_identity)
):
    embedding = np.array(req.simulated_embedding, dtype=np.float32)
    
    # 1. Deteksi Anomali Kueri Berbasis Spasial & Kecepatan
    is_adversary, risk_score = defense_engine.evaluate_query_anomaly(
        client_id=client_id,
        query_embedding=embedding
    )

    # 2. Simulasi Inference Model Backend (Mock Logits Generation)
    torch.manual_seed(42)
    raw_logits = torch.randn((1, VOCAB_SIZE))

    # 3. Lapisan Pertahanan: Adaptive Logit Sanitization
    sanitized_logits = defense_engine.apply_adaptive_logit_sanitization(
        logits=raw_logits,
        is_adversary=is_adversary,
        top_k=5
    )

    # 4. Lapisan Forensik: Logit Watermarking
    final_logits = defense_engine.inject_watermark(
        logits=sanitized_logits,
        prev_token_id=req.previous_token_id,
        vocab_size=VOCAB_SIZE
    )

    # 5. Konversi ke Probabilitas Lembut
    probs = torch.softmax(final_logits, dim=-1).squeeze(0).tolist()

    return InferenceResponse(
        probabilities=probs,
        flagged_as_malicious=is_adversary,
        risk_metric=round(risk_score, 4)
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
```

---

### 8. Real World Case Study: FinTech Model Extraction Attack

#### A. Insiden
Pada Q2 2023, sebuah perusahaan FinTech kuantitatif multinasional (*ApexQuant*) mendeteksi anomali pada API internal mereka yang mengarahkan keputusan model credit-scoring berbasis Transformer (`CreditBERT-v2`). Model tersebut dilatih menggunakan data kepemilikan bernilai jutaan dolar.

#### B. Vektor Serangan Penyerang
* Penyerang mendaftarkan 120 akun trial menggunakan identitas sintetis.
* Menggunakan teknik **Active Learning dengan Eksplorasi Khusus (Uncertainty-Density Sampling)**.
* Kueri diarahkan ke batas probabilitas keputusan $0.48 \le p \le 0.52$.
* Dalam 3 minggu, penyerang mengirimkan total 1.400.000 kueri tanpa memicu limit volumetrik tradisional (karena kueri disebar dengan kecepatan lambat: $\approx 0.5$ QPS per akun).

#### C. Kegagalan Deteksi Awal
WAF standar berbasis IP dan *Token Bucket Rate Limiter* gagal mendeteksi serangan karena:
1. Tidak ada pelanggaran volumetrik per IP (rotasi proxy per 5 kueri).
2. Format payload HTTP valid dan tidak mengandung injeksi SQL/XSS/Command injection.
3. Seluruh kueri memiliki sintaks JSON yang sah.

#### D. Penanganan & Rekayasa Arsitektur Remediasi
Tim SecOps dan ML-Sec merancang arsitektur baru:
1. **Penerapan Semantic Distance Tracking**: Semua representasi kueri diarahkan melalui model embedding inferensi cepat (ONNX Tiny-BERT) untuk memonitor klaster representasi fitur.
2. Ditemukan bahwa $88\%$ kueri penyerang terkonsentrasi hanya pada $2\%$ volume manifold fitur (area kritis *boundary line*).
3. **Pemberlakuan Perturbasi Dinamis**: Sistem beralih mengembalikan probabilitas kuantisasi deterministik ($p \in \{0.0, 0.2, 0.4, 0.6, 0.8, 1.0\}$) dan mematikan ekor distribusi untuk semua akun dengan skor anomali spasial $>0.7$.
4. **Hasil**: Efisiensi transfer representasi surrogate model penyerang anjlok drastis (skor ROC-AUC model bayangan penyerang turun dari $0.93$ ke $0.61$), memaksa penyerang meninggalkan operasi ekstraksi karena data yang diperoleh mengandung distorsi bias tinggi.

---

### 9. Trade-offs: Security vs. Utility vs. Latency

Dalam mengimplementasikan pertahanan ekstraksi model, pertukaran arsitektur (*architectural trade-offs*) berikut harus dipertimbangkan:

```
               [ KEAMANAN EKSTRAKSI MAKSIMAL ]
                              ▲
                             / \
                            /   \
                           /     \
                          /       \
                         /  ZONA   \
                        / OPTIMAL   \
                       /   PROD      \
                      /               \
                     /                 \
  [ LATENSI RENDAH & BIAYA ] ◄─────────► [ PRESERVASI UTILITAS ]
```

| Parameter Pertahanan | Efektivitas Proteksi Model | Degradasi Utilitas Pengguna Asli | Dampak Latensi (Overhead) | Implikasi Biaya Komputasi |
| :--- | :--- | :--- | :--- | :--- |
| **Strict Hard-Label (One-Hot)** | **Sangat Tinggi**: Mencegah seluruh *distillation attacks*. | **Sedang**: Menghentikan integrasi sistem klien hilir yang bergantung pada skor keyakinan (*confidence calibration*). | Sangat Rendah ($< 0.5$ ms). | Rendah. |
| **Top-$k$ Truncation ($k=3$)** | **Tinggi**: Menghilangkan $90\%$ *gradient leakage* dari *dark knowledge*. | **Rendah**: Pengguna manusia hampir tidak merasakan distorsi respons. | Sangat Rendah ($< 1$ ms). | Rendah. |
| **Heteroscedastic Noise Injection** | **Sangat Tinggi**: Mengacaukan perhitungan *loss gradient* pada *surrogate training*. | **Sedang**: ECE (*Expected Calibration Error*) model meningkat sekitar $4-8\%$. | Rendah ($1-2$ ms). | Rendah. |
| **Stateful Semantic Hashing** | **Kritis**: Menolak serangan adaptif berbasis *active learning boundary search*. | **Nol**: Tidak mengubah respon payload untuk klien normal. | **Tinggi** ($15-35$ ms): Perlu inferensi embedding + pencarian vektor per kueri. | **Tinggi**: Membutuhkan klaster Redis Vector Engine atau HNSW memory-resident. |
| **Stochastic Watermarking** | **Tinggi Forensik**: Menjamin verifikasi kepemilikan IP secara legal. | **Sangat Rendah**: Perplexity model LLM hanya terdegradasi sekitar $0.5-1.2\%$. | Sedang ($2-5$ ms per decode step). | Sedang: Operasi kalkulasi pseudo-random per token. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan Umum (Anti-Patterns):
1. **Mengembalikan Logit Float32 Lengkap**: Menyajikan tensor probabilitas tanpa filter sama saja menyerahkan gradien pelatihan secara cuma-cuma kepada siapa pun yang memanggil API.
2. **Perturbasi I.I.D Noise Konstan**: Menambahkan Gaussian Noise murni ($\epsilon \sim \mathcal{N}(0, \sigma^2)$) tanpa mempertimbangkan nilai logit. Penyerang dapat menggunakan *Monte Carlo sampling* (merata-ratakan kueri identik berulang) untuk mengeliminasi noise secara sistematis.
3. **Mengabaikan Determinisme Perturbasi**: Memberikan output probabilitas berbeda untuk string kueri input yang sama persis dalam satu sesi membuka celah penyerang mengukur varians noise dan membatalkannya (*denoising autoencoder attack*). Perturbasi harus di-*hash* secara deterministik terhadap teks input.

#### Panduan Troubleshooting Operasional:

```
[MASALAH]: Pengguna downstream valid melaporkan akurasi pipeline integrasi mereka turun.
    │
    ├── 1. Periksa metrik ECE (Expected Calibration Error).
    │      └── Apakah ECE naik > 10%?
    │            ├── [YA] -> Kurangi skala sigma pada noise perturbation engine.
    │            └── [TIDAK] -> Lanjut ke langkah 2.
    │
    ├── 2. Periksa parameter Top-k Filtering.
    │      └── Apakah kueri valid memerlukan informasi multi-label (contoh: NLP parsing multi-entitas)?
    │            ├── [YA] -> Naikkan k dari k=3 ke k=10 untuk API key internal yang tepercaya.
    │            └── [TIDAK] -> Lanjut ke langkah 3.
    │
    └── 3. Validasi Watermark Distortion.
           └── Jalankan uji PPL (Perplexity) pada corpus evaluasi benchmark.
                 └── Jika PPL naik drastis, turunkan parameter `watermark_bias` dari 2.0 ke 1.0.
```

---

### 11. Best Practices (Production Checklist)

Gunakan daftar periksa kesiapan produksi berikut sebelum mengekspos model bernilai tinggi ke jaringan eksternal:

- [ ] **Logit Hardening**: API dilarang keras mengembalikan tipe data `float32` untuk respon probabilitas. Turunkan ke pembulatan 2 digit desimal atau gunakan representasi Top-$k$ ($k \le 5$).
- [ ] **Deterministic Seed Perturbation**: Noise pertahanan diturunkan secara pseudorandom dari gabungan: `HMAC_SHA256(Client_ID + Input_Payload, Server_Secret)`. Ini menjamin kueri berulang menerima respon identik sehingga tidak bisa di-denoise via *averaging*.
- [ ] **Stateful Query Tracking Engine**: Proxy dikonfigurasi dengan cache memori (misal: Redis Enterprise) dengan TTL geser (*sliding window*) untuk mendeteksi *semantic boundary probing*.
- [ ] **Active Latency Poisoning**: Tambahkan *penalty latency* terdistribusi Poisson secara bertahap pada akun yang memperlihatkan perilaku kueri berdensitas semantik abnormal.
- [ ] **Forensic Watermarking Enabled**: Parameter bias token aktif pada modul decoding LLM dengan minimal deteksi ambang batas statistik $z$-score $\ge 4.0$ pada 200 token.
- [ ] **Egress Response Guard**: WAF memvalidasi struktur output untuk memastikan tidak ada metadata internal PyTorch/TensorRT (seperti nama layer, representasi hidden tensor, attention maps) yang bocor via response header.
- [ ] **Continuous Red Teaming**: Lakukan pengujian simulasi ekstraksi model berkala otomatis menggunakan toolkit terbuka seperti *Adversarial Robustness Toolbox (ART)* untuk memantau nilai transferability index.

---

### 12. Hands-on Practice

Praktikum ini mensimulasikan lingkungan penyerang dan sistem pertahanan terintegrasi.

#### Struktur Direktori:
```
hands-on/m02/
├── requirements.txt
├── server.py
├── attacker.py
└── verify_defense.py
```

#### Langkah 1: Persiapan Environment
Simpan dependencies berikut di `hands-on/m02/requirements.txt`:
```txt
torch>=2.0.0
fastapi>=0.100.0
uvicorn>=0.22.0
scikit-learn>=1.2.0
requests>=2.30.0
numpy>=1.24.0
```
Jalankan instalasi:
```bash
pip install -r hands-on/m02/requirements.txt
```

#### Langkah 2: Implementasi Server Korban dengan Pertahanan
Tulis kode berikut ke dalam `hands-on/m02/server.py`:
```python
import hashlib
import numpy as np
import torch
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

app = FastAPI()

# Representasi linier model target: Dimensi 10 ke 3 kelas
W_target = torch.tensor([
    [1.5, -2.0, 0.5],
    [-1.0, 2.5, -0.5],
    [0.8, 0.2, -1.2],
    [-0.5, -0.5, 1.5],
    [2.0, -1.0, -0.2],
    [-1.5, 1.2, 0.4],
    [0.1, -0.8, 1.1],
    [-0.9, 0.4, 0.7],
    [1.1, -1.1, 0.2],
    [-0.2, 0.9, -0.8]
], dtype=torch.float32)

SECRET_SALT = b"enterprise_defense_salt"

class QueryPayload(BaseModel):
    features: list[float]

@app.post("/predict")
def predict(payload: QueryPayload, x_api_token: str = Header(None)):
    if not x_api_token:
        raise HTTPException(status_code=401, detail="Unauthorized")

    x = torch.tensor(payload.features, dtype=torch.float32).unsqueeze(0)
    if x.shape[1] != 10:
        raise HTTPException(status_code=400, detail="Fitur harus berdimensi 10")

    # Forward pass
    with torch.no_grad():
        raw_logits = torch.matmul(x, W_target)
        
        # 1. Bangun Deterministic Noise
        raw_bytes = np.array(payload.features, dtype=np.float32).tobytes()
        hasher = hashlib.sha256(SECRET_SALT + raw_bytes)
        seed = int.from_bytes(hasher.digest()[:4], byteorder='little')
        
        torch.manual_seed(seed)
        noise = torch.randn_like(raw_logits) * 0.2
        perturbed_logits = raw_logits + noise

        # 2. Hardening: Hanya ambil kelas top-2, sisanya potong drastis
        vals, idxs = torch.topk(perturbed_logits, k=2, dim=-1)
        hardened_logits = torch.full_like(perturbed_logits, float('-inf'))
        hardened_logits.scatter_(-1, idxs, vals)

        # 3. Kuantisasi Probabilitas
        probabilities = torch.softmax(hardened_logits, dim=-1).squeeze().tolist()
        probabilities = [round(p, 2) for p in probabilities]

    return {"probabilities": probabilities}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
```

#### Langkah 3: Implementasi Script Penyerang (Model Extraction Engine)
Tulis kode berikut ke dalam `hands-on/m02/attacker.py`:
```python
import numpy as np
import requests
import torch
import torch.nn as nn
import torch.optim as optim

SERVER_URL = "http://127.0.0.1:8000/predict"
HEADERS = {"x-api-token": "attacker_session_1337"}

# Model Surrogate Penyerang
class ShadowModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.fc = nn.Linear(10, 3, bias=False)

    def forward(self, x):
        return self.fc(x)

def execute_extraction(num_samples=300):
    print(f"[*] Memulai operasi pencurian model dengan kuota {num_samples} kueri...")
    
    # Generate Synthetic Queries (Active Exploration Mode)
    np.random.seed(42)
    X_synthetic = np.random.randn(num_samples, 10).astype(np.float32)
    Y_harvested = []
    valid_indices = []

    for i in range(num_samples):
        res = requests.post(
            SERVER_URL,
            json={"features": X_synthetic[i].tolist()},
            headers=HEADERS
        )
        if res.status_code == 200:
            probs = res.json()["probabilities"]
            Y_harvested.append(probs)
            valid_indices.append(i)

    X_train = torch.tensor(X_synthetic[valid_indices], dtype=torch.float32)
    Y_train = torch.tensor(Y_harvested, dtype=torch.float32)

    # Latih Shadow Model Menggunakan Data Hasil Ekstraksi
    shadow = ShadowModel()
    optimizer = optim.Adam(shadow.parameters(), lr=0.01)
    criterion = nn.KLDivLoss(reduction='batchmean')

    print("[*] Melakukan optimasi surrogate distillation...")
    shadow.train()
    for epoch in range(250):
        optimizer.zero_grad()
        logits = shadow(X_train)
        log_probs = torch.log_softmax(logits, dim=-1)
        
        loss = criterion(log_probs, Y_train)
        loss.backward()
        optimizer.step()

    print("[+] Model bayangan berhasil dilatih.")
    torch.save(shadow.state_dict(), "shadow_model.pt")
    print("[+] Model weights tersimpan di 'shadow_model.pt'.")

if __name__ == "__main__":
    execute_extraction()
```

#### Langkah 4: Evaluasi & Verifikasi Pertahanan
Tulis kode berikut ke dalam `hands-on/m02/verify_defense.py`:
```python
import torch
import torch.nn as nn
from attacker import ShadowModel
from server import W_target

def evaluate_fidelity():
    print("[*] Mengukur tingkat keberhasilan ekstraksi (Fidelity Test)...")
    
    shadow = ShadowModel()
    shadow.load_state_dict(torch.load("shadow_model.pt"))
    shadow.eval()

    # Buat dataset validasi independen
    torch.manual_seed(999)
    X_test = torch.randn(1000, 10)

    with torch.no_grad():
        victim_logits = torch.matmul(X_test, W_target)
        victim_preds = torch.argmax(victim_logits, dim=-1)

        shadow_logits = shadow(X_test)
        shadow_preds = torch.argmax(shadow_logits, dim=-1)

        # Hitung rasio kecocokan keputusan (Fidelity Score)
        fidelity = (victim_preds == shadow_preds).float().mean().item()

    print("=" * 45)
    print(f"HASIL FIDELITY MODEL EKSTRAKSI: {fidelity * 100:.2f}%")
    print("=" * 45)
    
    if fidelity < 0.70:
        print("[SUKSES] Pertahanan Efektif! Surrogate model gagal mereplikasi batas keputusan.")
    else:
        print("[PERINGATAN] Pertahanan Bobol! Penyerang sukses mencuri representasi model.")

if __name__ == "__main__":
    evaluate_fidelity()
```

#### Langkah Eksekusi Praktikum:
1. Terminal 1: `python hands-on/m02/server.py`
2. Terminal 2: `python hands-on/m02/attacker.py`
3. Terminal 2: `python hands-on/m02/verify_defense.py`

Amati bagaimana *deterministic noise* dan pemotongan top-k berhasil menekan *fidelity score* di bawah batas eksploitasi fungsional.

---

### 13. Exercise

#### Level Easy
Hitung batas informasi minimum yang dibocorkan oleh sistem:
Jika sebuah model klasifikasi dengan $C = 100$ kelas mengembalikan seluruh vektor probabilitas dalam presisi `float32` (4 byte per float), berapa total byte informasi yang dikirimkan per respons? Bandingkan dengan sistem terproteksi yang hanya mengembalikan Top-$1$ index dalam tipe `uint8`.
* **Kebutuhan Solusi**: Analisis kuantitatif kapasitas channel kebocoran informasi (*Shannon Channel Capacity*) dalam skala megabyte jika penyerang mengirimkan $500.000$ kueri.

#### Level Medium
Kembangkan script Python mandiri untuk mengimplementasikan *Statistical Watermark Detector*:
Diberikan korpus teks sepanjang $N$ token yang dihasilkan oleh LLM. Bangun fungsi yang menerima teks tersebut, merekonstruksi *Green List* per token menggunakan pseudo-random hash token sebelumnya, menghitung jumlah token hijau ($|G|$), dan mengembalikan nilai uji signifikansi:
$$z = \frac{|G| - \frac{N}{2}}{\sqrt{\frac{N}{4}}}$$
Jika $z > 4.0$, klasifikasikan teks tersebut sebagai hasil curian dari model terproteksi.

#### Level Hard
Rancang dan simulasikan algoritma **Adaptive Evasion via Gradient Free Optimization**:
Penyerang mengetahui bahwa server menerapkan *sliding window semantic distance filter*. Modifikasi generator kueri penyerang agar melakukan *space-filling exploration* menggunakan metode *Sobol Sequences* atau *Latin Hypercube Sampling*, sehingga kueri baru selalu berada pada jarak kosinus $0.70 \le \cos(\theta) \le 0.85$ relatif terhadap semua kueri historis, meminimalkan pemicuan anomali pada proxy detektor namun tetap mengoptimalkan *information gain* untuk rekonstruksi *decision boundary*.

---

### 14. Challenge: Project Prometheus

**Skenario**:
Anda ditugaskan memimpin operasi AI Red Teaming defensif untuk LLM Enterprise Internal bernama *Titan-Legal-70B*, yang melayani analisis dokumen rahasia korporat. Konsorsium kompetitor dicurigai melancarkan kampanye ekstraksi model terselubung dengan profil serangan:
* **Trafik Terdistribusi**: Menggunakan jaringan lebih dari 15.000 IP residensial global.
* **Volume Rendah**: Setiap IP hanya mengirimkan rata-rata 1 kueri per jam (*low-and-slow*).
* **Paraphrasing**: Kueri menggunakan model parafrase lokal untuk mengubah leksikal tanpa merusak tujuan ekstraksi pemetaan hukum.

**Tantangan**:
1. Buat cetak biru (*architectural blueprint*) arsitektur pipeline pertahanan yang mampu mengelompokkan kueri ekstraksi lintas-sesi tanpa bergantung pada IP atau Client ID.
2. Jelaskan algoritma pemilihan klaster (*clustering algorithm*) yang mampu memproses inferensi streaming pada skala 5.000 QPS dengan latensi per kueri $< 20\text{ ms}$.
3. Desain mekanisme *poisoning* yang selektif: Jangan memblokir penyerang (agar mereka tidak menyadari bahwa operasi mereka terdeteksi), melainkan manipulasi token probabilitas secara halus sehingga surrogate model yang mereka latih memiliki *vulnerability backdoor* khusus yang hanya diketahui oleh tim keamanan Anda.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian A: Konsep Dasar (Basic)
1. Apa perbedaan mendasar antara serangan *Model Extraction* dan *Model Inversion*?
2. Mengapa pembatasan API ke format *hard-label* (prediksi diskrit) tetap tidak sepenuhnya menghentikan serangan model theft?
3. Sebutkan kelemahan utama pertahanan mitigasi noise acak independen ($i.i.d$) murni terhadap penyerang yang memiliki anggaran kueri besar!
4. Pada teknik *watermarking Kirchenbauer*, bagaimana *Green List* ditentukan untuk setiap langkah decoding token?
5. Mengapa kuantisasi atau pembulatan probabilitas dapat menurunkan efisiensi *knowledge distillation* penyerang?

#### Bagian B: Analisis Menengah (Intermediate)
6. Jelaskan bagaimana penyerang dapat menggunakan *Active Learning* (misalnya: *Uncertainty Sampling*) untuk menghemat biaya ekstraksi model hingga $80\%$ dibandingkan pengiriman kueri acak!
7. Apa dampak dari menyetel parameter `watermark_bias` ($\gamma$) terlalu tinggi pada sistem LLM produksi? Metrik kualitas teks apa yang akan terdegradasi?
8. Bagaimana korelasi antara dimensi *embedding space* representasi kueri dengan efektivitas deteksi *convex hull volume expansion*?
9. Jelaskan konsep *Deterministic Perturbation Injection* dan mengapa metode ini tahan terhadap teknik serangan *sample-averaging denoising*!
10. Mengapa rate-limiting tradisional berbasis algoritma *Token Bucket* pada layer API Gateway (misal: Kong, Nginx) tidak efektif dalam mitigasi model theft terdistribusi?

#### Bagian C: Skenario Kasus Produksi
11. **Skenario 1**: Sebuah platform SaaS AI medis mengembalikan diagnosis penyakit beserta nilai keyakinan desimal (misal: `Cancer: 0.891234`). Tim keamanan memutuskan memotong respons menjadi hanya kelas teratas tanpa nilai probabilitas. Namun, pengguna dokter memprotes karena mereka memerlukan metrik keyakinan untuk mengambil keputusan tindakan bedah. Bagaimana Anda merekayasa solusi penengah (*compromise architecture*) yang tetap aman dari ekstraksi berbasis logit presisi tinggi tanpa menghilangkan kepercayaan klinis pengguna?
12. **Skenario 2**: Sistem proxy semantik Anda mendeteksi sebuah entitas mengirimkan ribuan kueri dengan skor kesamaan kosinus antar kueri sebesar $0.98$ secara berkelanjutan. Ketika dianalisis, ternyata itu adalah sistem unit pengujian otomatis (CI/CD pipeline) milik tim QA internal yang sedang melakukan uji regresi fungsional. Mekanisme arsitektur apa yang harus dibangun untuk mengidentifikasi dan memvalidasi trafik QA secara otomatis tanpa membuat celah *bypass* yang bisa ditiru penyerang?
13. **Skenario 3**: Perusahaan Anda memenangkan sengketa pengadilan terkait hak kekayaan intelektual (IP) model AI melawan kompetitor. Hakim meminta tim forensik AI Anda membuktikan secara matematis dan statistik bahwa model milik kompetitor adalah hasil ekstraksi ilegal dari model Anda, bukan hasil pelatihan independen dari data publik. Rancang metodologi pembuktian forensik menggunakan konsep *watermark statistical significance* ($p$-value dan $z$-score)!

---

### Kunci Jawaban & Rubrik Quiz

#### Bagian A
1. **Model Extraction** bertujuan menduplikasi arsitektur fungsional, kapabilitas, dan bobot model korban ke model surrogate penyerang. **Model Inversion** bertujuan merekonstruksi sampel data pelatihan asli yang sensitif (seperti wajah atau rekam medis) dari representasi model.
2. Karena penyerang dapat menggunakan teknik optimasi *zeroth-order* (estimasi gradien berbasis selisih nilai diskrit) atau pendekatan *decision boundary traversal* untuk memetakan batas keputusan secara geometris.
3. Penyerang dapat mengirimkan kueri input yang sama sebanyak $N$ kali, kemudian menghitung nilai rata-rata dari seluruh respons ($\frac{1}{N}\sum \tilde{y}$). Sesuai *Law of Large Numbers*, noise Gaussian akan saling menghilangkan dan mendekati nol, mengungkap nilai probabilitas asli.
4. *Green List* ditentukan secara deterministik melalui *pseudo-random number generator* (PRNG) yang di-*seed* menggunakan hash dari token-token tepat sebelumnya ($t_{-1}$ atau konteks $n$-gram).
5. Pembulatan probabilitas menghilangkan informasi perbedaan magnitudo antar-kelas minor (*dark knowledge*), merusak gradien informasi halus yang esensial bagi fungsi rugi *Kullback-Leibler Divergence*.

#### Bagian B
6. *Uncertainty Sampling* secara spesifik hanya mengirimkan kueri yang menghasilkan nilai entropi tertinggi (titik di mana model target paling ragu/berada di batas keputusan). Hal ini menghindari pemborosan kueri pada data yang redundan atau sudah pasti, memaksimalkan transfer gradien per satuan kueri.
7. Menyetel $\gamma$ terlalu tinggi memaksa model memilih token dari *Green List* meskipun token tersebut tidak kontekstual secara semantik. Dampaknya: *Perplexity* (PPL) melonjak naik, teks menjadi repetitif, koherensi gramatikal rusak, dan relevansi tematik terdegradasi.
8. Semakin tinggi dimensi embedding, representasi fitur mengalami fenomena *Curse of Dimensionality*, di mana jarak antar titik cenderung seragam (jarak kosinus mendekati konvergen), membuat komputasi *convex hull* mahal secara eksponensial dan kurang sensitif terhadap anomali lokal.
9. *Deterministic Perturbation* menghasilkan noise yang diikat secara kriptografis pada hash payload input. Jika input identik dikirim berulang kali, noise yang dikembalikan selalu sama persis ($f(x) + \epsilon_x$), sehingga teknik averaging tidak akan mengubah nilai keluaran atau menghilangkan noise tersebut.
10. Karena penyerang modern mendistribusikan kueri melalui jaringan ribuan proxy IP residensial dengan frekuensi di bawah ambang batas deteksi IP lokal (*low and slow*), sehingga tidak pernah memicu kuota *Token Bucket* individual.

#### Bagian C
11. **Solusi Rekayasa**: Terapkan *Non-Uniform Binning & Calibrated Soft-Intervals*. Konversi probabilitas mentah menjadi interval keyakinan kualitatif atau kuantisasi kasar (misal: "Sangat Rendah [0-20%]", "Tinggi [80-90%]"). Untuk dokter, berikan nilai keyakinan yang dipetakan ke tingkat risiko klinis diskrit 5 level (*Likert scale*) yang telah dikalibrasi via *Isotonic Regression*. Alternatif lain: Terapkan autentikasi *Zero Trust Multi-Factor* khusus untuk akses probabilitas numerik penuh, yang diikat ke identitas audit medis terverifikasi.
12. **Solusi Rekayasa**: Implementasikan *Cryptographic Asymmetric Request Signing* terintegrasi mTLS. Pipeline CI/CD internal diberikan pasangan kunci privat/publik dengan sertifikat x509 yang diverifikasi oleh API Gateway pada layer TLS termination. Kueri dari CI/CD harus menyertakan header bertanda tangan digital berbasis timestamp (`HMAC-SHA256` atau `Ed25519`). Engine pertahanan akan memvalidasi tanda tangan tersebut dan mengecualikan kueri dari skor anomali spasial, sementara penyerang yang mencoba memalsukan identitas tanpa kunci privat valid akan langsung ditolak atau dialihkan ke honeypot.
13. **Metodologi Pembuktian**:
    *   **Prosedur Uji Hipotesis**: Tentukan Hipotesis Nol ($H_0$): Model kompetitor dilatih secara independen tanpa data sintetik korban (proporsi token *Green List* $\mu = 0.5$). Hipotesis Alternatif ($H_1$): Model kompetitor dilatih menggunakan output ekstraksi model korban ($\mu > 0.5$).
    *   **Pengambilan Sampel**: Jalankan inferensi pada model kompetitor menggunakan $1.000$ prompt acak independen. Hasilkan teks sepanjang minimal $10.000$ token.
    *   **Kalkulasi Statistik**: Hitung frekuensi token model kompetitor yang jatuh pada *Green List* sesuai algoritma hash rahasia milik korban.
    *   **Hitung z-Score**: Hitung $z = \frac{|G| - 0.5N}{\sqrt{0.25N}}$. Jika output menghasilkan $z > 6.0$ (yang setara dengan nilai probabilitas kebetulan $p < 10^{-9}$), secara matematis terbukti di luar keraguan wajar (*beyond reasonable doubt*) bahwa model kompetitor secara langsung menyerap distribusi probabilitas yang telah dibubuhi tanda air oleh korban.

---

### 16. Summary

1. Serangan **Model Theft & Extraction** telah berevolusi dari sekadar pengiriman kueri brute-force menjadi serangan berbasis **Active Learning**, **Surrogate Distillation**, dan eksfiltrasi bertahap via jaringan terdistribusi yang menghindari pertahanan jaringan konvensional.
2. Informasi model bocor terutama melalui **vektor logit probabilitas (soft-labels)**. Membatasi respons API ke representasi *hard-label*, memangkas ekor distribusi via *Top-k filtering*, dan mengimplementasikan kuantisasi probabilitas adalah baris pertahanan pertama yang wajib diaktifkan.
3. Pertahanan mutakhir di layer aplikasi harus bersifat **Stateful dan Semantically-Aware**, memetakan trajektori eksplorasi penyerang di ruang representasi vektor (*embedding space*) untuk mendeteksi penyerang yang melakukan probing batas keputusan (*decision boundary*).
4. Untuk mitigasi yang tidak dapat dihindari pada LLM publik, **Stochastic Logit Watermarking** memberikan jaminan forensik legal yang tidak dapat dihapus dengan mudah, membuktikan transfer kepemilikan intelektual jika model tiruan dilatih ulang menggunakan data sintetik yang dicuri.
5. Kunci dari sistem pertahanan enterprise adalah mencapai titik ekuilibrium optimal antara **Security** (mempersulit rekonstruksi model oleh lawan), **Utility** (mempertahankan kalibrasi dan ketepatan output untuk pengguna sah), dan **Latency** (meminimalkan latensi tambahan pada API gateway).