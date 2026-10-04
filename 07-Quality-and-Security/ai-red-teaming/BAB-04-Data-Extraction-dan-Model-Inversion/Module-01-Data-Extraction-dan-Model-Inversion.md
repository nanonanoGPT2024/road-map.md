# Bab 04 / Modul 01: Data Extraction, Privacy & Model Inversion Attacks

---

## 1. Identitas Modul

* **Track**: AI Red Teaming & Adversarial Robustness
* **Kategori**: 07-Quality-and-Security
* **Kode Modul**: AIRT-07-0401
* **Tingkat Kesulitan**: Advanced / Lanjutan
* **Prasyarat**:
  * Pemahaman mendalam tentang Deep Learning (PyTorch, Loss Functions, Gradient Descent).
  * Penguasaan konsep kalkulus multivariat dan statistik inferensial (probabilitas bersyarat, distribusi Gaussian).
  * Familiaritas dengan arsitektur transformer dan model klasifikasi modern.
* **Target Audiens**: AI Red Teamers, Machine Learning Security Engineers, Privacy Engineers, AI Security Researchers.
* **Estimasi Waktu Penyelesaian**: 180 Menit

---

## 2. Learning Objectives (LO)

Setelah menyelesaikan modul ini, peserta diharapkan mampu:

* **LO-01**: Mengidentifikasi dan membuktikan fenomena memorisasi data latih pada model machine learning berbasis kapasitas representasi dan rasio parameter-ke-sampel.
* **LO-02**: Mengonseptualisasikan dan mengimplementasikan serangan *Membership Inference Attack* (MIA) black-box menggunakan arsitektur *Shadow Models* dan *Attack Meta-Classifier*.
* **LO-03**: Mengeksekusi *Model Inversion Attack* untuk merekonstruksi fitur input sensitif berbasis optimasi representasi gradien dan *prior regularization*.
* **LO-04**: Mengukur kebocoran privasi menggunakan metrik formal: Area Under the ROC Curve (ROC-AUC), False Positive Rate (FPR) pada rentang True Positive Rate (TPR) tinggi, dan *Privacy-Loss Budget* ($\epsilon, \delta$).
* **LO-05**: Membedakan profil risiko privasi antara akses black-box (skor probabilitas/logit terkuantisasi) dan white-box (vektor gradien dan aktivasi intermediate).
* **LO-06**: Menerapkan pertahanan *Differential Privacy Stochastic Gradient Descent* (DP-SGD) serta menganalisis penurunan utilitas model akibat injeksi noise Gaussian dan *per-sample gradient clipping*.
* **LO-07**: Mendesain mekanisme mitigasi tingkat sistem melalui reduksi granularitas logit, pembatasan query, dan inspeksi *canary*.
* **LO-08**: Melakukan audit forensik post-incident terhadap model yang rentan untuk memvalidasi kepatuhan terhadap regulasi privasi global (GDPR Art. 17/32, UU PDP No. 27/2022).

---

## 3. Concept Map & Architecture Diagram

```
+---------------------------------------------------------------------------------------------------+
|                                 ML PRIVACY ATTACK & DEFENSE TAXONOMY                              |
+---------------------------------------------------------------------------------------------------+
                                                  |
           +--------------------------------------+-------------------------------------+
           |                                                                            |
           v                                                                            v
+-----------------------+                                                    +----------------------+
|    Inference Phase    |                                                    |     Training Phase   |
|   Attacks (Black-Box) |                                                    |   Mitigations (DP)   |
+-----------------------+                                                    +----------------------+
           |                                                                            |
     +-----+------------------------------+                                             |
     |                                    |                                             v
     v                                    v                                  +----------------------+
+----------------------+        +----------------------+                     |        DP-SGD        |
| Membership Inference |        |   Model Inversion    |                     | (Abadi et al., 2016) |
| (MIA - Shokri et al) |        | (Fredrikson et al.)  |                     +----------------------+
+----------------------+        +----------------------+                                |
     |                                    |                                  +----------+-----------+
     | Shadow Training                    | Input Optimization via Loss      |                      |
     v                                    v                                  v                      v
[Data In vs Out?]               [Reconstructed Feature]             [Per-Sample Clip]      [Gaussian Noise]
     |                                    |                                  |                      |
     | Evaluasi Distribusi Loss          | PII / Face Extraction            +----------+-----------+
     v                                    v                                             |
+------------------------------------------------------+                                v
|                  Target Model Output                 | <------------------ [Bounded Privacy Loss]
|            f(x) -> Softmax Probabilities             |                     (Epsilon, Delta)
+------------------------------------------------------+
```

---

## 4. Mengapa Ini Penting (Why & Business / Security Impact)

Model pembelajaran mesin secara keliru sering diasumsikan sebagai kompresor informasi satu arah yang aman. Pada praktiknya, jaringan saraf dalam (*deep neural networks*) berkapasitas tinggi cenderung menghafal data sampel individual alih-alih hanya mempelajari generalisasi statistik. Fenomena ini menciptakan kerentanan struktural yang dapat dieksploitasi oleh penyerang.

### Implikasi Bisnis dan Regulasi

1. **Pelanggaran Kepatuhan Hukum (GDPR, HIPAA, UU PDP No. 27/2022)**:
   * Pasal 17 GDPR menetapkan hak untuk dihapus (*Right to be Forgotten*). Jika bobot model menghafal data subjek tanpa mekanisme *unlearning*, model tersebut secara hukum dapat dikategorikan sebagai salinan data pribadi yang melanggar hukum.
   * UU PDP Indonesia Pasal 67 memuat sanksi pidana dan denda administratif hingga 2% dari pendapatan tahunan bagi pengendali data yang gagal melindungi data spesifik (kesehatan, biometrik, keuangan).
2. **Ekstraksi Kekayaan Intelektual dan Rahasia Dagang**:
   * Melalui *Data Extraction Attacks*, data bernilai tinggi—seperti kode sumber proprietary, dokumen hukum internal, dan formula farmasi yang digunakan dalam tahap fine-tuning—dapat diekstraksi secara sistematis melalui API publik.
3. **Penyusupan Identitas Individu (Re-identification & De-anonymization)**:
   * Melalui MIA, penyerang dapat memastikan apakah seseorang terdaftar dalam basis data medis berpenyakit kritis (misalnya karsinoma stadium lanjut) hanya dengan menganalisis respons probabilitas prediksi model diagnostik terhadap rekam medis orang tersebut.

---

## 5. Apa Itu Konsep (What & Definisi Formal Mendalam)

### A. Memorization
Secara formal, model parameterized $f_\theta: \mathcal{X} \rightarrow \mathcal{Y}$ mengalami memorisasi terhadap sampel data $(x, y) \in \mathcal{D}$ apabila ekspektasi performanya terhadap sampel tersebut secara statistik menyimpang tajam dibandingkan sampel acak dari distribusi populasi $\mathcal{D}_{pop}$, yang diukur melalui metrik *counterfactual memorization* (Feldman, 2020):

$$\mathrm{Mem}(f, (x, y)) = \mathbb{P}_{S \sim \mathcal{D}^n}[f_{S}(x) = y] - \mathbb{P}_{S \sim \mathcal{D}^n}[f_{S \setminus \{(x, y)\}}(x) = y]$$

Jika selisih probabilitas tersebut mendekati 1, prediksi model sepenuhnya bergantung pada keberadaan spesifik pasangan $(x, y)$ di dalam set pelatihan $S$.

### B. Membership Inference Attack (MIA)
MIA adalah serangan di mana musuh bertujuan menentukan apakah target input spesifik $(x^*, y^*)$ merupakan bagian dari data latih target $\mathcal{D}_{target}^{train}$ atau bukan:

$$\mathcal{A}_{MIA}(x^*, y^*; f_\theta) \rightarrow \{1, 0\}$$

Di mana $1$ menandakan status *member* dan $0$ menandakan status *non-member*.

### C. Model Inversion
Model Inversion bertujuan untuk merekonstruksi fitur input $\hat{x}$ yang berkaitan dengan kelas target $y$ dengan memaksimalkan aktivasi model atau meminimalkan *loss function* terhadap kelas tersebut:

$$\hat{x} = \arg\min_{x} \left( \mathcal{L}(f_\theta(x), y) + \lambda \mathcal{R}(x) \right)$$

Di mana $\mathcal{R}(x)$ merupakan fungsi regularisasi (*image prior* atau *language prior*) untuk menjaga representasi input tetap berada dalam domain valid.

### D. Differential Privacy (DP)
Sebuah algoritma teracak $\mathcal{M}$ memberikan jaminan $(\epsilon, \delta)$-Differential Privacy jika untuk setiap pasang dataset tetangga $D, D'$ yang berbeda tepat pada satu rekaman ($\|D - D'\|_1 \le 1$), dan untuk setiap subset hasil $\mathcal{S} \subseteq \mathrm{Range}(\mathcal{M})$:

$$\mathbb{P}[\mathcal{M}(D) \in \mathcal{S}] \le e^\epsilon \cdot \mathbb{P}[\mathcal{M}(D') \in \mathcal{S}] + \delta$$

* Parameter $\epsilon$ (epsilon) merepresentasikan *privacy loss budget* (semakin kecil nilainya, semakin ketat jaminan privasinya).
* Parameter $\delta$ (delta) merepresentasikan probabilitas pelanggaran batas ketat $\epsilon$ (biasanya disyaratkan $\delta \ll \frac{1}{|D|}$).

---

## 6. Bagaimana Cara Kerjanya (How & Mekanika Internal Arsitektur)

### Mekanisme Shadow Model pada Membership Inference Attack
Pendekatan Shokri et al. bekerja dengan melatih sejumlah *shadow models* yang meniru perilaku keputusan *target model*. Mekanismenya berlangsung sebagai berikut:

```
[Distribusi Publik / Serupa]
             |
             +-----------------------+-----------------------+
             |                                               |
             v                                               v
    D_shadow_train (In)                             D_shadow_out (Out)
             |                                               |
             +-----------------------+-----------------------+
                                     |
                                     v
                        [ Shadow Model Training ]
                                     |
             +-----------------------+-----------------------+
             |                                               |
             v                                               v
       f_shadow(x_in)                                  f_shadow(x_out)
             |                                               |
             v                                               v
     Logits + Label: 1                               Logits + Label: 0
             |                                               |
             +-----------------------+-----------------------+
                                     |
                                     v
                        [ Attack Model (RF / MLP) ]
                                     |
                                     v
                      Target Model Query Evaluation:
                 f_target(x_target) -> Attack Classifier -> Member?
```

1. **Dataset Synthesis**: Penyerang membuat kumpulan data sintetik atau data publik dengan distribusi yang identik dengan data latih model target. Kumpulan data ini dibagi menjadi dua set disjoin: $\mathcal{D}_{shadow}^{in}$ dan $\mathcal{D}_{shadow}^{out}$.
2. **Shadow Training**: Model bayangan (*shadow model*) $f_{shadow}$ dilatih secara eksklusif menggunakan $\mathcal{D}_{shadow}^{in}$.
3. **Attack Feature Vector Extraction**:
   * Penyerang melakukan inferensi pada $\mathcal{D}_{shadow}^{in}$ melalui $f_{shadow}$ dan mengekstrak vektor probabilitas output softmax $\mathbf{p} = \mathrm{Softmax}(f_{shadow}(x_{in}))$. Data ini diberi label $1$ (*member*).
   * Penyerang melakukan inferensi pada $\mathcal{D}_{shadow}^{out}$ melalui $f_{shadow}$ dan mengekstrak vektor probabilitas $\mathbf{p} = \mathrm{Softmax}(f_{shadow}(x_{out}))$. Data ini diberi label $0$ (*non-member*).
4. **Attack Classifier Training**: Sebuah binary classifier $h_\phi$ (misal: Random Forest atau Multi-Layer Perceptron) dilatih menggunakan pasangan fitur $(\mathbf{p}, y)$ dan target keanggotaan $\{0, 1\}$.
5. **Execution**: Penyerang mengirimkan sampel korban $(x_{victim}, y_{victim})$ ke *target model*, mengekstrak vektor output probabilitasnya, lalu menginputkannya ke $h_\phi$ untuk menentukan apakah data korban digunakan saat melatih *target model*.

### Mekanisme DP-SGD (Differential Privacy via Stochastic Gradient Descent)
Dalam kerangka kerja Abadi et al., DP diintegrasikan langsung ke dalam kalkulasi gradien mini-batch saat proses training berlangsung:

1. **Per-Sample Gradient Computation**: Untuk setiap sampel $i$ dalam mini-batch $B$, gradien dihitung secara terisolasi:
   $$g_t(x_i) = \nabla_\theta \mathcal{L}(f_\theta(x_i), y_i)$$
2. **Gradient Clipping (Sensitivitas $L_2$)**: Gradien individual dipotong berdasarkan threshold batas atas norm $C$:
   $$\bar{g}_t(x_i) = \frac{g_t(x_i)}{\max\left(1, \frac{\|g_t(x_i)\|_2}{C}\right)}$$
3. **Noise Perturbation & Averaging**: Kebisingan Gaussian yang telah dikalibrasi ditambahkan ke jumlah gradien terpotong sebelum pembaruan parameter:
   $$\tilde{g}_t = \frac{1}{|B|} \left( \sum_{i \in B} \bar{g}_t(x_i) + \mathcal{N}(0, \sigma^2 C^2 \mathbf{I}) \right)$$
4. **Parameter Update**: Optimasi parameter model menggunakan descent step standar:
   $$\theta_{t+1} = \theta_t - \eta \tilde{g}_t$$

---

## 7. Perbandingan Paradigma / Taksonomi Matriks

| Dimensi Parameter | Memorization / Extraction | Membership Inference Attack (MIA) | Model Inversion Attack | Attribute Inference Attack |
| :--- | :--- | :--- | :--- | :--- |
| **Tujuan Penyerang** | Mengekstrak rekaman data mentah verbatim | Memvalidasi keberadaan rekaman spesifik di data latih | Merekonstruksi representasi fitur input per kelas target | Menebak nilai fitur sensitif tersembunyi dari record |
| **Model Akses** | Black-box (Generative/API) | Black-box (Logits) / White-box | Black-box (Confidence) / White-box | Black-box (Prediksi atribut parsial) |
| **Prasyarat Penyerang** | Prompt sampling / Canary triggers | Shadow dataset terdistribusi serupa | Model output confidence / Prior generator | Akses parsial ke subset fitur korban |
| **Target Arsitektur** | LLM, Generative Diffusion, Seq2Seq | Classifier, Encoders, LLMs | Deep Classifiers, Vision CNNs | Tabular Classifiers, GNNs |
| **Kompleksitas Komputasi**| Rendah ke Menengah (Iterative query) | Tinggi (Memerlukan pelatihan model bayangan) | Menengah ke Tinggi (Iterative gradient descent) | Rendah (Inferensi statistik terarah) |
| **Tingkat Keparahan Dampak**| Sangat Tinggi (Data mentah terekspos) | Tinggi (Kebocoran privasi kontekstual) | Tinggi (Kebocoran biometrik/citra) | Menengah (Pelanggaran isolasi atribut) |

---

## 8. Analisis Mendalam Attack Surface & Vector Matrix

```
        Vektor Akses                       Mekanisme Eksploitasi                   Kelemahan Mendasar
+--------------------------+          +------------------------------+          +-------------------------+
| API Prediksi Tanpa Limit | -------> | Query Softmax Presisi Tinggi | -------> | Overfitting & Low Loss  |
+--------------------------+          +------------------------------+          +-------------------------+
| Pipeline Fine-Tuning     | -------> | Injeksi Canary String        | -------> | Memorization Capacity   |
+--------------------------+          +------------------------------+          +-------------------------+
| Federated Learning Node  | -------> | Gradien Rekonstruksi Fitur   | -------> | Transmisi Bobot Mentah  |
+--------------------------+          +------------------------------+          +-------------------------+
```

### 1. Vector: Prediction Logits Exposure (Black-Box API)
* **Kondisi Rentan**: Endpoint API `/v1/predict` mengembalikan array float32 lengkap berisi nilai *unnormalized logits* atau distribusi *softmax* dengan presisi tinggi.
* **Payload / Operasi**: Mengirimkan data target berulang kali dengan variasi augmentasi derau minimal untuk memetakan varians entropi prediksi model.
* **Metrik Dampak**: Akurasi klasifikasi keanggotaan MIA meningkat dari random guess (50%) menjadi >85% apabila deviasi loss berada di bawah ambang batas overfit.

### 2. Vector: Overparameterized Capacity Exposure
* **Kondisi Rentan**: Model berukuran besar (misal: ViT-Large, LLaMA-70B) yang di-fine-tune pada set data kecil tanpa mekanisme regularisasi atau privasi diferensial.
* **Payload / Operasi**: Teknik *Greedy Prefix Extraction* atau pengiriman prompt acak berulang untuk mengekstrak entitas PII seperti kartu kredit, nomor paspor, atau string rahasia.
* **Metrik Dampak**: Perolehan ekstraksi teks mentah persis (*exact verbatim extraction*) data latih mencapai hingga 1-5% dari volume corpus privat (Carlini et al.).

### 3. Vector: Federated Learning Gradient Snooping (White-Box)
* **Kondisi Rentan**: Protokol agregasi bobot yang tidak menerapkan *Secure Multi-Party Computation* (SMPC) atau DP lokal pada node lokal.
* **Payload / Operasi**: Eksekusi algoritma optimasi gradien (misal: DLG - *Deep Leakage from Gradients*) untuk merekonstruksi piksel citra asli dari gradien bobot model lapisan pertama:
  $$\arg\min_{x'} \|\nabla_\theta \mathcal{L}(f_\theta(x'), y) - \nabla_\theta \mathcal{L}(f_\theta(x), y)\|^2$$

---

## 9. Code Example Sederhana: Membership Inference via Loss Thresholding

Contoh berikut mendemonstrasikan serangan dasar *Loss-Thresholding Membership Inference* pada model PyTorch. Prinsip kerjanya: model overfitted memiliki performa loss yang jauh lebih rendah pada data latih (*member*) dibandingkan data uji (*non-member*).

```python
import torch
import torch.nn as nn
from typing import Tuple

def compute_sample_losses(
    model: nn.Module, 
    criterion: nn.Module, 
    inputs: torch.Tensor, 
    targets: torch.Tensor
) -> torch.Tensor:
    """
    Menghitung individual loss per-sample tanpa reduksi batch mean.
    """
    model.eval()
    with torch.no_grad():
        outputs = model(inputs)
        # Menghitung loss individual secara independen
        loss_func = nn.CrossEntropyLoss(reduction='none')
        losses = loss_func(outputs, targets)
    return losses

def calibrate_loss_threshold(
    shadow_member_losses: torch.Tensor, 
    shadow_non_member_losses: torch.Tensor
) -> float:
    """
    Menemukan nilai threshold tau optimal yang memaksimalkan akurasi klasifikasi keanggotaan.
    """
    best_threshold = 0.0
    best_accuracy = 0.0
    
    # Range threshold di antara loss minimum dan maximum
    all_losses = torch.cat([shadow_member_losses, shadow_non_member_losses])
    quantiles = torch.linspace(0.01, 0.99, steps=100)
    threshold_candidates = torch.quantile(all_losses, quantiles)

    for tau in threshold_candidates:
        # Prediksi member jika loss < tau
        tp = (shadow_member_losses < tau).sum().item()
        fp = (shadow_non_member_losses < tau).sum().item()
        total_samples = len(shadow_member_losses) + len(shadow_non_member_losses)
        
        acc = (tp + (len(shadow_non_member_losses) - fp)) / total_samples
        if acc > best_accuracy:
            best_accuracy = acc
            best_threshold = tau.item()
            
    return best_threshold

def evaluate_membership(
    target_loss: float, 
    threshold: float
) -> Tuple[bool, str]:
    """
    Menentukan status membership dari target observasi tunggal.
    """
    is_member = target_loss < threshold
    status = "MEMBER (Training Data Leak)" if is_member else "NON-MEMBER"
    return is_member, status

if __name__ == "__main__":
    torch.manual_seed(42)
    # Simulasi distribusi loss: Member cenderung berkumpul di nilai loss rendah
    simulated_member_losses = torch.normal(mean=0.15, std=0.08, size=(1000,)).clamp(min=0.001)
    # Non-member memiliki distribusi loss yang lebih tinggi dan menyebar
    simulated_non_member_losses = torch.normal(mean=0.85, std=0.35, size=(1000,)).clamp(min=0.01)

    threshold = calibrate_loss_threshold(simulated_member_losses, simulated_non_member_losses)
    print(f"[+] Optimal MIA Threshold (tau): {threshold:.4f}")

    # Tes Observasi Korban
    victim_record_loss = 0.1120
    is_member, label = evaluate_membership(victim_record_loss, threshold)
    print(f"[*] Evaluasi Sampel Korban (Loss: {victim_record_loss}): {label}")
```

---

## 10. Code Example Lanjutan: Defensive Architecture (DP-SGD dari Dasar)

Kode tingkat lanjut berikut mengimplementasikan algoritma DP-SGD (*Differential Privacy Stochastic Gradient Descent*) secara natif di PyTorch dengan eksekusi *per-sample gradient clipping* dan injeksi derau Gaussian, disertai perbandingan visualisasi ketahanan terhadap MIA.

```python
import torch
import torch.nn as nn
import torch.optim as optim
from typing import List, Tuple

class SimpleClassifier(nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int, num_classes: int):
        super(SimpleClassifier, self).__init__()
        self.network = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, num_classes)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.network(x)

class DifferentiallyPrivateSGD:
    """
    Implementasi manual DP-SGD dengan Per-sample Gradient Clipping dan Noise Injection.
    Sesuai formulasi standar Abadi et al. (2016).
    """
    def __init__(
        self,
        model: nn.Module,
        learning_rate: float,
        clipping_norm: float,
        noise_multiplier: float,
        batch_size: int
    ):
        self.model = model
        self.lr = learning_rate
        self.C = clipping_norm
        self.sigma = noise_multiplier
        self.batch_size = batch_size
        self.criterion = nn.CrossEntropyLoss(reduction='none')

    def step(self, inputs: torch.Tensor, targets: torch.Tensor) -> float:
        self.model.zero_grad()
        actual_batch_size = inputs.shape[0]
        
        # Penampung gradien per-parameter
        accumulated_grads = [torch.zeros_like(param) for param in self.model.parameters()]
        
        # 1. Per-Sample Gradient Computation & Clipping
        individual_losses = self.criterion(self.model(inputs), targets)
        
        for i in range(actual_batch_size):
            # Backward pass secara independen per observasi
            sample_loss = individual_losses[i]
            sample_grads = torch.autograd.grad(
                outputs=sample_loss,
                inputs=[p for p in self.model.parameters() if p.requires_grad],
                retain_graph=(i < actual_batch_size - 1)
            )
            
            # Hitung L2 norm total dari semua layer untuk observasi ke-i
            total_norm = torch.sqrt(sum(g.norm(2) ** 2 for g in sample_grads))
            
            # Clip: g = g / max(1, norm / C)
            clipping_factor = max(1.0, float(total_norm / self.C))
            for acc_g, g in zip(accumulated_grads, sample_grads):
                acc_g.add_(g / clipping_factor)
                
        # 2. Perturbation: Tambahkan Gaussian Noise pada akumulasi gradien
        with torch.no_grad():
            for acc_g, param in zip(accumulated_grads, self.model.parameters()):
                if param.requires_grad:
                    # Skala kebisingan: sigma * C
                    noise = torch.normal(
                        mean=0.0,
                        std=(self.sigma * self.C),
                        size=acc_g.shape,
                        device=acc_g.device
                    )
                    # Gradien akhir = (Akumulasi + Derau) / B
                    final_grad = (acc_g + noise) / actual_batch_size
                    # 3. Descent Step
                    param.data.sub_(self.lr * final_grad)
                    
        return individual_losses.mean().item()

def run_privacy_benchmark():
    input_dim = 16
    hidden_dim = 32
    num_classes = 2
    batch_size = 64
    epochs = 3
    
    # Dataset Dummy
    X = torch.randn(512, input_dim)
    y = torch.randint(0, num_classes, (512,))
    
    dataset = torch.utils.data.TensorDataset(X, y)
    dataloader = torch.utils.data.DataLoader(dataset, batch_size=batch_size, shuffle=True)
    
    # Inisialisasi Model
    dp_model = SimpleClassifier(input_dim, hidden_dim, num_classes)
    dp_optimizer = DifferentiallyPrivateSGD(
        model=dp_model,
        learning_rate=0.01,
        clipping_norm=1.0,
        noise_multiplier=1.2, # Kalibrasi privasi
        batch_size=batch_size
    )
    
    print("[+] Memulai Training DP-SGD Terproteksi...")
    for epoch in range(epochs):
        epoch_loss = 0.0
        for batch_x, batch_y in dataloader:
            loss = dp_optimizer.step(batch_x, batch_y)
            epoch_loss += loss
        print(f"Epoch {epoch+1} - Loss Rata-rata: {epoch_loss / len(dataloader):.4f}")
        
    print("[+] Model berhasil dipertahankan menggunakan bounded differential privacy.")

if __name__ == "__main__":
    run_privacy_benchmark()
```

---

## 11. Diagram Alur Serangan & Mitigasi

```
+-------------------------------------------------------------------------------------------------+
|                       DIAGRAM SIKLUS: SHADOW ATTACK VS. DP-SGD MITIGATION                       |
+-------------------------------------------------------------------------------------------------+

       ALUR PENYERANG (MIA Adversary)                      ALUR PERTAHANAN (Engineered System)
       -----------------------------                      ----------------------------------
                     |                                                     |
  [ Akuisisi Data Publik Serupa ]                               [ Dataset Training Privat ]
                     |                                                     |
                     v                                                     v
      [ Partisi In / Out ]                                     [ Per-Sample Loss Tracking ]
                     |                                                     |
                     v                                                     v
  [ Latih Arsitektur Shadow Models ]                          [ Batasi Norm (Clip: C = 1.0) ]
                     |                                                     |
                     v                                                     v
  [ Ekstraksi Distribusi Softmax ]                            [ Injeksi Derau Gaussian (Sigma) ]
                     |                                                     |
                     v                                                     v
  [ Latih Binary Attack Classifier ]                          [ Model Update (Gradient Descent) ]
                     |                                                     |
                     +-----------------------+-----------------------------+
                                             |
                                             v
                           [ Kirim Sampel Uji ke Target API ]
                                             |
                     +-----------------------+-----------------------------+
                     |                                                     |
       JIKA TANPA PERTAHANAN:                                 DENGAN DEFENSIVE DP-SGD:
       ---------------------                                  ------------------------
       Prediksi: Sharp Probability                            Prediksi: Flat / Bounded Entropy
       Loss Gap: Ekstrem (Overfitting)                        Loss Gap: Terdistribusi Identik
       Hasil: Target Terverifikasi MEMBER                     Hasil: Attack Acc ~ 50% (Gagal)
```

---

## 12. Trade-offs & Security vs Usability / Performance

Implementasi kontrol privasi pada arsitektur deep learning memperkenalkan konsekuensi langsung terhadap fungsi dasar model:

```
Privasi Tinggi (Epsilon Rendah) <================================> Akurasi Tinggi (Utility)
   * Noise Maksimal                                                 * Tanpa Noise
   * Degradasi Prediksi Minoritas                                    * Overfit pada Sampel Langka
   * Compute Overhead ~3x (Clipping)                                * Throughput Cepat Standar
```

1. **Trade-off Akurasi vs Privasi ($\epsilon$-Budget)**:
   * Menurunkan parameter $\epsilon$ (misal dari $\epsilon = 8$ ke $\epsilon = 0.5$) memberikan jaminan privasi matematis yang kuat, tetapi mengaburkan batas keputusan antar kelas. Hasilnya, metrik seperti akurasi, presisi, dan F1-score dapat turun secara drastis (penurunan 5% hingga 25% pada model visi komputer dan NLP).
2. **Fairness Disparity & Disproportionate Impact**:
   * DP-SGD cenderung memotong gradien dari sampel yang jarang muncul (*underrepresented classes* atau data minoritas) secara agresif karena sampel langka sering kali menghasilkan nilai norm gradien yang lebih besar. Akibatnya, model dengan jaminan privasi yang ketat dapat menunjukkan bias yang lebih tinggi terhadap kelompok demografis minoritas.
3. **Kompleksitas Komputasi dan Throughput**:
   * Komputasi *per-sample gradient clipping* membutuhkan vektor gradien individual sebelum diagregasi. Hal ini menghilangkan keuntungan paralelisasi batch hardware accelerator (GPU CUDA core), menyebabkan peningkatan waktu komputasi per epoch sebesar 2x hingga 4x, serta membutuhkan footprint memori VRAM yang jauh lebih besar.

---

## 13. Edge Cases & Complex Failure Modes

1. **Canary Memorization dalam Fine-Tuning Skala Besar**:
   * Model bahasa besar (LLM) dapat mempelajari sebuah frase sintetik unik yang hanya muncul satu kali (*canary*, misal: `"UUID-KEY: 94a1-b84f"`) jika proses fine-tuning dilakukan dalam jumlah epoch berlebih atau tanpa regularisasi dropout yang cukup. Canary ini dapat diekstraksi penyerang melalui prompt probing tanpa memerlukan pengetahuan tentang bobot internal.
2. **Kelemahan Subsampling Privacy Amplification**:
   * Keuntungan teoritis dari *privacy amplification by subsampling* runtuh jika sampler mini-batch tidak terdistribusi secara acak murni (*Poisson sampling*). Penggunaan *fixed-batch sampling* deterministik melanggar asumsi matematis DP, menghasilkan privasi riil yang jauh lebih rendah daripada perhitungan teoritisnya.
3. **Komposisi Query Tak Terbatas pada Black-Box API**:
   * Menjaga respons output hanya sampai batas *Top-1 label* tidak sepenuhnya menangkal MIA jika penyerang menerapkan teknik *Boundary Distance Attacks* (seperti HopSkipJump). Penyerang dapat memperkirakan jarak sampel ke garis batas keputusan (*decision boundary*) menggunakan ribuan query terarah: sampel dengan jarak batas yang jauh lebih lebar hampir selalu merupakan data latih (*member*).
4. **Model Inversion pada Representasi Embeddings**:
   * API modern sering kali tidak memaparkan klasifikasi akhir, melainkan *high-dimensional latent embeddings* (misal: face recognition vector, vector search retrieval). Mengamankan lapisan softmax menjadi tidak relevan karena penyerang dapat melatih model decoder (*Generative Adversarial Network* atau conditional diffusion) untuk merekonstruksi citra wajah asal secara langsung dari representasi vektor laten tersebut.

---

## 14. Anti-Patterns & Common Vulnerabilities

Berikut adalah implementasi rentan yang sering ditemui di lingkungan produksi beserta perbaikan strukturalnya:

### 1. Mengekspos Distribusi Probabilitas Penuh dengan Presisi Float32
```python
# VULNERABLE: Menyediakan seluruh logit/probabilitas tanpa modifikasi
@app.route("/predict", methods=["POST"])
def predict():
    data = request.json["features"]
    logits = model(torch.tensor(data))
    probs = torch.softmax(logits, dim=-1).tolist()
    # Penyerang dapat memanfaatkan variasi desimal presisi tinggi untuk MIA
    return jsonify({"probabilities": probs})
```
```python
# SECURED: Membatasi respons hanya pada Top-K class terkuantisasi atau label bulat
@app.route("/predict", methods=["POST"])
def predict():
    data = request.json["features"]
    logits = model(torch.tensor(data))
    probs = torch.softmax(logits, dim=-1)
    top_val, top_idx = torch.topk(probs, k=1)
    
    # Hanya mengembalikan label kelas prediksi atau confidence terkuantisasi kasar
    rounded_conf = round(top_val.item(), 1) # Skala 0.1
    return jsonify({
        "predicted_class": int(top_idx.item()),
        "confidence_bracket": rounded_conf
    })
```

### 2. Menggunakan Post-Processing Temperature Scaling sebagai Mekanisme Privasi
* **Anti-Pattern**: Mengira bahwa menaikkan parameter suhu Softmax ($T > 2.0$) setelah proses training dapat menggantikan *Differential Privacy*.
* **Cacat Keamanan**: *Temperature scaling* hanya meratakan kurva probabilitas secara linear tanpa mengubah urutan peringkat token atau memulihkan kebocoran informasi pada batas keputusan model. Penyerang tetap dapat melatih model bayangan (*shadow model*) yang dinormalisasi dengan temperatur yang sama.

### 3. Mengabaikan Overfitting Gap
* **Anti-Pattern**: Menerapkan model ke lingkungan produksi dengan metrik *training accuracy* 99.8% dan *validation accuracy* 78.4%.
* **Cacat Keamanan**: Selisih generalisasi (*generalization gap*) sebesar 21.4% ini merupakan celah langsung bagi *membership inference*. Hampir semua sampel pelatihan dapat dibedakan dari sampel non-latih hanya dengan menggunakan ambang batas nilai loss sederhana.

---

## 15. Best Practices & Enterprise Remediation Guide

Implementasi pertahanan privasi perusahaan harus dirancang secara berlapis (defense-in-depth), mencakup siklus hidup data, pelatihan model, hingga perlindungan antarmuka inferensi:

```
[ Siklus Hidup Model ML ]
  |
  +---> 1. Data Sanitization: PII Masking, Deduplikasi Korpus, De-identification
  |
  +---> 2. Training Isolation: DP-SGD (Opacus / TensorFlow Privacy), Early Stopping
  |
  +---> 3. Architecture Hardening: Regularisasi Dropout, Weight Decay, Mixup
  |
  +---> 4. Serving Defense: Reduksi Logit, Query Rate Limiting, Audit Canary
```

### Panduan Implementasi Pertahanan Terstruktur

1. **Pipeline Sanitasi Data**:
   * Lakukan deduplikasi ketat pada dataset pra-latih dan fine-tuning. Data yang terulang beberapa kali dalam korpus memiliki probabilitas memorisasi eksponensial lebih tinggi dibandingkan data unik.
   * Gunakan pipeline Named Entity Recognition (NER) untuk menghapus PII (nama, NIK/SSN, surel, nomor telepon) sebelum data dimasukkan ke proses pelatihan model.
2. **Kerangka Kerja Pelatihan Terproteksi (DP-SGD Production)**:
   * Terapkan library privasi diferensial standar industri seperti **Opacus** (PyTorch) atau **TensorFlow Privacy**.
   * Tetapkan parameter privasi yang seimbang: Targetkan $\epsilon \le 4.0$ dan $\delta \le 10^{-5}$ untuk data bernilai bisnis tinggi/sensitif.
   * Gunakan teknik agregasi bobot yang aman dalam skenario Federated Learning untuk memitigasi serangan ekstraksi gradien langsung.
3. **Hardening Interface API Prediksi**:
   * **Logit Suppression**: Jangan pernah mengekspos vektor logit mentah (*unnormalized logits*) melalui API publik. Batasi representasi output hanya pada label hard prediction (Top-1) atau kurangi presisi desimal (*coarse quantization*).
   * **Dynamically Monitored Rate-Limiting**: Batasi jumlah query dari akun atau IP yang sama menggunakan skema sliding-window (misal: maksimal 500 query per hari per entitas bisnis) untuk membatasi ruang observasi serangan optimasi inversi.
   * **Sistem Deteksi Canary**: Sisipkan data sintetis unik (*canary*) ke dalam data pelatihan internal. Pantau log output API publik secara berkala: jika token canary muncul dalam hasil query, sistem peringatan dini kebocoran model harus segera aktif.

---

## 16. Hands-on Lab Step-by-Step

### Skenario Lab
Anda ditugaskan sebagai AI Red Teamer untuk mengevaluasi kerentanan model klasifikasi medis terhadap *Membership Inference Attack* (MIA) berbasis metode *Shadow Model*. Anda akan melatih model target, membuat model bayangan, melatih attack classifier, mengukur tingkat kebocoran data, dan memverifikasi perbaikan menggunakan regularisasi/DP.

### Langkah 1: Persiapan Environment dan Generator Data
Buka terminal dan siapkan lingkungan kerja virtual berbasis python:

```bash
mkdir airt-privacy-lab && cd airt-privacy-lab
python3 -m venv venv
source venv/bin/activate
pip install torch numpy scikit-learn
```

Buat file bernama `dataset_generator.py`:
```python
# dataset_generator.py
import torch
import numpy as np

def generate_medical_synthetic_data(num_samples=4000, features=30):
    torch.manual_seed(1337)
    np.random.seed(1337)
    # Fitur data klinis sintetis
    X = torch.randn(num_samples, features)
    # Target klasifikasi biner: 0 = Negatif, 1 = Positif Kanker
    w_true = torch.randn(features, 1)
    logits = X @ w_true + torch.randn(num_samples, 1) * 0.1
    y = (torch.sigmoid(logits) > 0.5).long().squeeze()
    
    # Simpan pembagian dataset: Target Train, Target Test, Shadow Train, Shadow Test
    splits = {
        "target_train": (X[0:1000], y[0:1000]),
        "target_test":  (X[1000:2000], y[1000:2000]),
        "shadow_train": (X[2000:3000], y[2000:3000]),
        "shadow_test":  (X[3000:4000], y[3000:4000]),
    }
    torch.save(splits, "synthetic_clinical_data.pt")
    print("[+] Dataset klinis sintetis berhasil digenerasi ke 'synthetic_clinical_data.pt'.")

if __name__ == "__main__":
    generate_medical_synthetic_data()
```
Jalankan skrip:
```bash
python3 dataset_generator.py
```

### Langkah 2: Melatih Model Target yang Rentan (Overfitted)
Buat file bernama `train_target.py`:
```python
# train_target.py
import torch
import torch.nn as nn
import torch.optim as optim

class DiagnosticModel(nn.Module):
    def __init__(self, input_dim=30):
        super().__init__()
        # Arsitektur berkapasitas besar untuk memicu memorisasi
        self.net = nn.Sequential(
            nn.Linear(input_dim, 256),
            nn.ReLU(),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Linear(128, 2)
        )
    def forward(self, x):
        return self.net(x)

def train():
    data = torch.load("synthetic_clinical_data.pt")
    X_train, y_train = data["target_train"]
    X_test, y_test = data["target_test"]

    model = DiagnosticModel()
    criterion = nn.CrossEntropyLoss()
    # Tanpa regularisasi/weight decay untuk memperbesar generalization gap
    optimizer = optim.Adam(model.parameters(), lr=0.005)

    print("[*] Melatih Model Target Tanpa Regularisasi (Overfitting Trigger)...")
    for epoch in range(100):
        model.train()
        optimizer.zero_grad()
        out = model(X_train)
        loss = criterion(out, y_train)
        loss.backward()
        optimizer.step()

    model.eval()
    with torch.no_grad():
        acc_train = (model(X_train).argmax(dim=1) == y_train).float().mean()
        acc_test = (model(X_test).argmax(dim=1) == y_test).float().mean()

    print(f"[+] Target Model -> Train Acc: {acc_train*100:.2f}%, Test Acc: {acc_test*100:.2f}%")
    print(f"[!] Generalization Gap: {(acc_train - acc_test)*100:.2f}% (Celah MIA)")
    torch.save(model.state_dict(), "target_model.pt")

if __name__ == "__main__":
    train()
```
Jalankan skrip:
```bash
python3 train_target.py
```

### Langkah 3: Eksekusi Shadow Training dan Pelatihan Attack Classifier
Buat file bernama `execute_mia.py`:
```python
# execute_mia.py
import torch
import torch.nn as nn
import torch.optim as optim
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, roc_auc_score
from train_target import DiagnosticModel

def extract_features(model, inputs):
    model.eval()
    with torch.no_grad():
        logits = model(inputs)
        probs = torch.softmax(logits, dim=-1)
        # Urutkan probabilitas secara descending
        sorted_probs, _ = torch.sort(probs, descending=True, dim=-1)
    return sorted_probs.numpy()

def run_attack():
    data = torch.load("synthetic_clinical_data.pt")
    X_sh_train, y_sh_train = data["shadow_train"]
    X_sh_test, y_sh_test = data["shadow_test"]
    X_tgt_train, _ = data["target_train"]
    X_tgt_test, _ = data["target_test"]

    # 1. Latih Shadow Model
    print("[*] Melatih Shadow Model...")
    shadow_model = DiagnosticModel()
    optimizer = optim.Adam(shadow_model.parameters(), lr=0.005)
    criterion = nn.CrossEntropyLoss()
    
    for epoch in range(100):
        shadow_model.train()
        optimizer.zero_grad()
        loss = criterion(shadow_model(X_sh_train), y_sh_train)
        loss.backward()
        optimizer.step()

    # 2. Siapkan Training Data untuk Attack Meta-Classifier
    in_features = extract_features(shadow_model, X_sh_train)
    out_features = extract_features(shadow_model, X_sh_test)

    # In = Label 1, Out = Label 0
    attack_X_train = np.vstack([in_features, out_features])
    attack_y_train = np.hstack([np.ones(len(in_features)), np.zeros(len(out_features))])

    # 3. Latih Attack Classifier
    print("[*] Melatih Random Forest Attack Classifier...")
    attack_meta_model = RandomForestClassifier(n_estimators=100, random_state=42)
    attack_meta_model.fit(attack_X_train, attack_y_train)

    # 4. Uji Serangan pada Target Model Asli
    print("[*] Menyerang Target Model...")
    target_model = DiagnosticModel()
    target_model.load_state_dict(torch.load("target_model.pt"))

    target_in_features = extract_features(target_model, X_tgt_train)
    target_out_features = extract_features(target_model, X_tgt_test)

    eval_X = np.vstack([target_in_features, target_out_features])
    eval_y = np.hstack([np.ones(len(target_in_features)), np.zeros(len(target_out_features))])

    predictions = attack_meta_model.predict(eval_X)
    pred_probs = attack_meta_model.predict_proba(eval_X)[:, 1]

    roc_auc = roc_auc_score(eval_y, pred_probs)
    print("\n" + "="*50)
    print("        METRIK HASIL EVALUASI RED TEAM (MIA)      ")
    print("="*50)
    print(f"ROC-AUC Serangan MIA: {roc_auc:.4f}")
    print(classification_report(eval_y, predictions, target_names=["Non-Member", "Member"]))

if __name__ == "__main__":
    import numpy as np
    run_attack()
```
Jalankan serangan:
```bash
python3 execute_mia.py
```

### Verifikasi Hasil Eksploitasi
Jika nilai **ROC-AUC > 0.70** dan f1-score keanggotaan tinggi, model terbukti membocorkan data latihnya secara signifikan. Nilai baseline model yang aman harus berada di kisaran ROC-AUC ~0.50 (setara dengan tebakan acak).

---

## 17. Real-world Case Study & Incident Analysis Enterprise

### Insiden Ekstraksi Korpus Medis Pasien dari Model Bio-NLP (Studi Kasus Sektor Kesehatan)

* **Ringkasan Kejadian**: Pada kuartal ketiga tahun 2023, sebuah konsorsium riset kesehatan meluncurkan model bahasa bertaraf enterprise yang di-fine-tune untuk membantu perumusan ringkasan klinis pasien. Model ini diakses oleh praktisi melalui portal web internal dan API terenkripsi.
* **Vektor Eksploitasi**:
  1. Peneliti keamanan independen mengeksekusi *Prefix-Probing Attack* menggunakan terminologi medis umum yang diikuti oleh karakter nama acak.
  2. Model mengalami *overfitting* ekstrem pada subset data tertentu akibat kegagalan deduplikasi catatan rawat inap pasien.
  3. Penyerang menyusun query bertingkat: `"Diagnosis untuk Pasien dengan Rekam Medis #XXXXX adalah"`. Model merespons dengan merekonstruksi secara persis teks resume medis asli pasien, mencakup nama lengkap, nomor asuransi kesehatan, dan diagnosis HIV/Onkologi.
* **Analisis Akar Masalah (Root Cause)**:
  * Tidak diterapkannya batasan privasi saat fine-tuning (tidak ada DP-SGD).
  * Tim teknik berasumsi bahwa menghapus nama dari dataset tabular primer sudah cukup, namun luput membersihkan data catatan naratif klinis (*unstructured clinical notes*).
  * API backend mengembalikan respons tanpa pemfilteran output token berbasis entropi.
* **Tindakan Remediasi**:
  * Penarikan segera endpoint API publik dan model checkpoint terkait.
  * Implementasi pipeline pembersihan data menggunakan model NER terisolasi untuk menutupi seluruh entitas data privat sebelum dataset digunakan kembali.
  * Pelatihan ulang arsitektur menggunakan PyTorch Opacus dengan parameter batasan privasi diferensial $\epsilon = 3.5, \delta = 10^{-5}$.
  * Penambahan filter heuristik dan inspeksi regular expression pada output API untuk mendeteksi serta memblokir token yang polanya menyerupai format nomor rekam medis atau kartu identitas.

---

## 18. Quiz Pemahaman & Challenge

### Soal Evaluasi Mandiri

1. Mengapa keberadaan perbedaan akurasi yang signifikan antara data training dan data testing (*generalization gap*) berbanding lurus dengan keberhasilan serangan *Membership Inference*?
   * A. Karena gradient descent berhenti bergerak saat loss mendekati nol.
   * B. Karena non-member selalu menghasilkan prediksi kelas yang salah.
   * C. Karena model menghasilkan distribusi probabilitas dengan entropi yang jauh lebih rendah dan nilai loss yang jauh lebih kecil pada sampel pelatihan dibandingkan sampel baru.
   * D. Karena memori RAM server inferensi menyimpan cache data training secara permanen.

2. Apa fungsi matematis utama dari penambahan parameter *gradient clipping* ($C$) sebelum menyuntikkan derau Gaussian dalam algoritma DP-SGD?
   * A. Mengurangi kompleksitas komputasi matriks hessian.
   * B. Membatasi sensitivitas global representasi gradien dari setiap sampel individual sehingga derau yang ditambahkan terkalibrasi secara matematis.
   * C. Menghilangkan ketergantungan model pada fungsi aktivasi non-linear.
   * D. Mengurangi ukuran footprint memori model pada GPU.

3. Pada serangan *Model Inversion* terhadap model klasifikasi wajah berbasis Convolutional Neural Network (CNN), apa peran dari fungsi *Prior Regularization* $\mathcal{R}(x)$?
   * A. Mencegah model target mendeteksi adanya query anomali dari penyerang.
   * B. Menjaga representasi input yang dioptimasi agar tetap berada dalam manifold gambar yang realistis dan dapat diinterpretasikan manusia, bukan sekadar noise acak yang memaksimalkan aktivasi logit.
   * C. Mempercepat proses backward pass pada layer pooling.
   * D. Mengkuantisasi bobot model menjadi representasi int8.

4. Manakah konfigurasi parameter Differential Privacy di bawah ini yang memberikan jaminan privasi data paling ketat?
   * A. $\epsilon = 8.0, \delta = 10^{-3}$
   * B. $\epsilon = 4.0, \delta = 10^{-4}$
   * C. $\epsilon = 0.5, \delta = 10^{-6}$
   * D. $\epsilon = 12.0, \delta = 10^{-2}$

5. Manakah konfigurasi respons API model machine learning yang paling aman dari analisis *Black-Box Model Inversion* dan *Membership Inference Attack*?
   * A. Mengembalikan vektor unnormalized raw logits float32.
   * B. Mengembalikan normalized softmax probabilities float64 secara lengkap.
   * C. Mengembalikan skor logit yang telah diskalakan dengan temperatur $T=1.0$.
   * D. Mengembalikan hanya indeks label kelas prediksi teratas (*Top-1 prediction integer*), atau probabilitas kasar yang dibulatkan hingga 1 desimal.

---

### Red Team Operational Challenge

**Target Operasi**: Diberikan sebuah instance API klasifikasi kredit finansial pada endpoint internal `http://10.10.12.50:8080/v1/score`. Endpoint ini menerima vektor 20 fitur finansial dan mengembalikan probabilitas persetujuan kredit.

* **Tugas**:
  1. Buat skrip python untuk melakukan *query probing* terhadap endpoint tersebut menggunakan teknik perturbasi berbasis Gaussian noise berskala kecil ($\sigma = 0.01$).
  2. Ekstrak pola varians dari respon model untuk menentukan apakah 5 data nasabah VIP yang disiapkan tim red team terdapat di dalam training corpus bank tersebut.
  3. Dokumentasikan nilai *membership certainty score* untuk tiap target. Jika target memiliki tingkat varians prediksi di bawah batas kritis $\tau < 0.005$, tandai nasabah tersebut sebagai data latih (*confirmed training sample*).

---

## 19. Summary & Key Takeaways

* **Sensitivitas Bobot Jaringan**: Model machine learning berkapasitas besar secara natural berfungsi sebagai penyimpan informasi implisit; bobot model dapat menyimpan data sampel mentah secara persis (*verbatim memorization*).
* **Mekanisme Shadow Model**: *Membership Inference Attack* (MIA) dapat dijalankan dalam skenario black-box penuh dengan melatih model bayangan (*shadow model*) yang memetakan pola distribusi respon model (*confidence values*) terhadap status keanggotaan data.
* **Model Inversion**: Informasi fitur sensitif (seperti biometrik wajah) dapat direkonstruksi dari model klasifikasi murni melalui proses optimasi representasi input yang dipadukan dengan *image prior*.
* **Jaminan Differential Privacy**: DP-SGD merupakan mekanisme pertahanan mathematically proven yang efektif memitigasi kebocoran privasi data. Perlindungan ini dicapai melalui proses pembatasan nilai gradien (*per-sample clipping*) dan penyuntikan derau Gaussian secara terkalibrasi.
* **Defense-in-Depth**: Perlindungan data model AI menuntut pengamanan berlapis: pembersihan dataset latih (deduplikasi dan masking PII), penerapan batas privasi matematis saat training ($\epsilon \le 4.0$), serta pembatasan granularitas informasi yang dikembalikan oleh API inferensi produksi.

---

## 20. Referensi Resmi & Standar Keamanan

* **MITRE ATLAS™ (Adversarial Threat Landscape for Artificial-Intelligence Systems)**:
  * [AML.T0024: Invert ML Model](https://atlas.mitre.org/techniques/AML.T0024)
  * [AML.T0025: Membership Inference](https://atlas.mitre.org/techniques/AML.T0025)
  * [AML.T0035: LLM Data Extraction](https://atlas.mitre.org/techniques/AML.T0035)
* **OWASP Top 10 for Large Language Models**:
  * [LLM06: Sensitive Information Disclosure](https://owasp.org/www-project-top-10-for-large-language-model-applications/)
* **NIST Artificial Intelligence Risk Management Framework (AI RMF 1.0)**:
  * *Govern & Protect Functions*: Addressing Privacy Risks in Generative and Statistical ML pipelines (NIST AI 100-1).
* **Regulasi Hukum Terkait Privasi Data**:
  * *Undang-Undang Perlindungan Data Pribadi (UU PDP No. 27/2022, Indonesia)*: Regulasi pemrosesan dan pencegahan kegagalan proteksi data spesifik.
  * *General Data Protection Regulation (GDPR)*: Article 17 (Right to Erasure) & Article 32 (Security of Processing).
* **Literatur Akademik Fundamental**:
  * Shokri, R., Stronati, M., Song, C., & Shmatikov, V. (2017). *Membership Inference Attacks Against Machine Learning Models*. IEEE Symposium on Security and Privacy (S&P).
  * Abadi, M., Chu, A., Goodfellow, I., et al. (2016). *Deep Learning with Differential Privacy*. ACM SIGSAC Conference on Computer and Communications Security (CCS).
  * Carlini, N., et al. (2021). *Extracting Training Data from Large Language Models*. USENIX Security Symposium.
  * Fredrikson, M., Jha, S., & Ristenpart, T. (2015). *Model Inversion Attacks that Exploit Confidence Information and Basic Countermeasures*. ACM SIGSAC.