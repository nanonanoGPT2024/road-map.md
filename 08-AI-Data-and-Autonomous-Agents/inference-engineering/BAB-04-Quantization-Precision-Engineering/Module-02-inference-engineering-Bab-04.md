# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 04: Quantization & Precision Engineering**  
**Kategori: 08-AI-Data-and-Autonomous-Agents (Inference Engineering)**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. **Merancang & Mengonfigurasi Arsitektur Presisi Rendah (Low-Precision Pipelines)**: Menguasai formulasi matematis dan implementasi konkret dari algoritma Post-Training Quantization (PTQ) modern (AWQ, GPTQ, SmoothQuant) dan standar FP8 (E4M3 vs E5M2) untuk memangkas *memory footprint* hingga 75% tanpa degradasi akurasi signifikan.
2. **Mengatasi Outlier Aktivasi pada LLM Skala Besar**: Mengimplementasikan teknik migrasi skala matematis (*mathematical scale migration*) antara aktivasi dan bobot (*weights*) guna menstabilkan inferensi model di atas parameter 6.7B.
3. **Membangun Custom Quantized Inference Kernels**: Mengembangkan kernel dekuantisasi terfusi (*fused dequantization kernels*) berbasis OpenAI Triton untuk skema Weight-Only INT4 (W4A16) dengan *group-wise scaling*.
4. **Mengorkestrasi Runtime Serving Skala Enterprise**: Menerapkan konfigurasi kuantisasi tingkat produksi pada inference engines modern (vLLM dan TensorRT-LLM) dengan throughput tinggi dan optimasi *KV-cache quantization*.
5. **Mengevaluasi Trade-Off Sistemik**: Mengukur metrik degradasi akurasi (*Perplexity*, MMLU) secara berimbang terhadap metrik sistem (*Time-to-First-Token* / TTFT, *Inter-Token Latency* / ITL, *Memory Bandwidth Saturation*, dan TCO GPU).

---

## 2. Prerequisite

Sebelum menelaah modul ini, Anda wajib memiliki pemahaman mendalam tentang:
* **Representasi Floating-Point IEEE 754**: Struktur bit *sign*, *exponent*, dan *mantissa* pada FP32, FP16, dan BF16.
* **Arsitektur GPU & Memori**: Hirarki memori GPU (HBM, L2 Cache, Shared Memory/SRAM, Registers) serta konsep *Memory-bound* vs *Compute-bound* dalam konteks *Roofline Model*.
* **PyTorch Internals**: Manipulasi `torch.Tensor` pada level representasi bit, *stride*, *views*, dan penulisan *custom extensions*.
* **Linear Algebra & Matmul**: Mekanika General Matrix Multiply (GEMM) dan dekomposisi kalkulasi tensor.
* **Dasar Ekosistem Serving LLM**: Memahami siklus eksekusi *Prefill* (Context Phase) dan *Decode* (Generation Phase).

---

## 3. Concept & Internal Architecture

### 3.1 Formulasi Matematis Kuantisasi Linier

Kuantisasi linier memetakan nilai kontinu presisi tinggi $X \in \mathbb{R}$ ke dalam domain diskret presisi rendah $X_q \in \mathbb{Z}$ (atau representasi FP berpresisi lebih kecil).

$$X_q = \text{clip}\left(\left\lfloor \frac{X}{S} \right\rceil + Z, \; q_{\min}, \; q_{\max}\right)$$

$$X \approx \hat{X} = S \cdot (X_q - Z)$$

Di mana:
* $S$ (*Scale Factor*, $\in \mathbb{R}$): Faktor penskalaan riil yang merepresentasikan resolusi kuantisasi.
* $Z$ (*Zero Point*, $\in \mathbb{Z}$): Nilai integer yang memetakan nilai riil nol ($0.0$) ke dalam domain terkuantisasi (hanya berlaku pada kuantisasi asimetris).
* $\lfloor \cdot \rceil$: Operasi pembulatan ke integer terdekat (*round-to-nearest*).
* $[q_{\min}, q_{\max}]$: Rentang representasi integer target (misal, $[-128, 127]$ untuk signed INT8, atau $[0, 15]$ untuk unsigned INT4).

#### Kuantisasi Simetris vs Asimetris
* **Simetris ($Z = 0$)**: Rentang input dipetakan secara terpusat di sekitar nol.
  $$S = \frac{\max(|X_{\min}|, |X_{\max}|)}{q_{\max}}$$
  *Keunggulan*: Mengeliminasi overhead komputasi koreksi $Z$ saat operasi GEMM ($A \cdot B = S_A S_B (A_q B_q)$).
* **Asimetris ($Z \neq 0$)**: Mengakomodasi distribusi yang tidak seimbang (misal: output setelah aktivasi ReLU/GELU).
  $$S = \frac{X_{\max} - X_{\min}}{q_{\max} - q_{\min}}, \quad Z = \left\lfloor \frac{-X_{\min}}{S} \right\rceil + q_{\min}$$

### 3.2 Granularitas Kuantisasi

Tingkat granularitas penskalaan menentukan kompromi antara akurasi model (*error quantization*) dan *memory overhead* untuk menyimpan skalar penskalaan:

1. **Per-Tensor**: Satu pasangan $(S, Z)$ untuk seluruh matriks bobot atau aktivasi. Overhead penyimpanan minimal, namun sangat rentan terhadap *outliers*.
2. **Per-Channel / Per-Token (Per-Axis)**:
   * Bobot ($W$): Skala unik per kolom atau baris keluaran ($S_i \in \mathbb{R}^N$ untuk matriks $M \times N$).
   * Aktivasi ($X$): Skala unik per token/vektor input.
3. **Group-wise (Block-wise)**: Skala independen diterapkan pada setiap blok berukuran $G$ elemen (misal, $G=32, 64, 128$). Skema standar de facto untuk W4A16 (INT4 bobot, FP16 aktivasi) guna memitigasi dispersi lokal tanpa beban komputasi per-elemen.

### 3.3 Problematika Emergent Activation Outliers

Pada Large Language Models dengan ukuran parameter melampaui 6.7B, aktivasi menampilkan fenomena sistemik: beberapa koordinat dimensi tersembunyi (*hidden dimensions*) memunculkan nilai magnitudo ekstrem (hingga 100x lipat lebih besar dibanding magnitudo rata-rata).

```
   Magnitudo Aktivasi [Channel Feature Domain]
   ▲
   │        │ (Outlier Channel k: magnitudo ~75.0)
   │        │
   │  ┌┐ ┌┐ │ ┌┐ ┌┐   ┌┐
   └──┴┴─┴┴─┴─┴┴─┴┴───┴┴──► Feature Dim C
   Normal Channels: magnitudo ~0.5 - 1.5
```

Jika kuantisasi W8A8 diterapkan secara naif menggunakan skema per-tensor atau per-token, nilai *outlier* pada dimensi $k$ akan mendominasi nilai $X_{\max}$, menyebabkan sebagian besar aktivasi normal terpotong (*underflow*) ke representasi bit 0 atau 1, yang meruntuhkan perplexity model secara drastis.

### 3.4 Deep Dive Algoritma Kuantisasi Modern

#### SmoothQuant: Migrasi Skala Matematis (Activation-Weight Co-design)
SmoothQuant menyelesaikan problem *activation outlier* dengan menyadari bahwa bobot secara umum mudah dikuantisasi (terdistribusi normal, varians rendah), sedangkan aktivasi sulit dikuantisasi karena *outlier*. 

SmoothQuant menerapkan transformasi ekuivalen linear menggunakan matriks diagonal *smoothing scale* $S = \text{diag}(s)$:

$$Y = X \cdot W = (X \cdot S^{-1}) \cdot (S \cdot W) = \hat{X} \cdot \hat{W}$$

Di mana vektor skala $s \in \mathbb{R}^C$ dihitung berdasarkan keseimbangan magnitudo antara aktivasi dan bobot:

$$s_j = \frac{\max(|X_j|)^\alpha}{\max(|W_j|)^{1 - \alpha}}$$

Parameter hiper $\alpha \in [0, 1]$ mengontrol seberapa banyak tingkat kesulitan kuantisasi yang dimigrasikan dari aktivasi ke bobot:
* $\alpha = 1$: Seluruh varians aktivasi dimigrasikan ke bobot (Aktivasi sangat mudah dikuantisasi).
* $\alpha = 0.5$: Keseimbangan optimal untuk sebagian besar arsitektur LLaMA/Mistral.

Setelah perkalian dengan $S^{-1}$, aktivasi menjadi halus (*smooth*), memungkinkan kuantisasi INT8 per-tensor atau per-token secara simetris tanpa kehilangan representasi informasi.

#### AWQ (Activation-aware Weight Quantization)
AWQ membuktikan bahwa tidak semua bobot memiliki signifikansi yang sama. Hanya 1% bobot teratas yang mengontrol sebagian besar akurasi inferensi. Kunci identifikasi 1% bobot kritis ini bukan terletak pada magnitudo bobot itu sendiri, melainkan pada **magnitudo aktivasi yang masuk ke bobot tersebut**.

Formulasi optimasi AWQ mencari matriks penskalaan per-channel $S$ yang meminimalkan rekonstruksi error pada output layer:

$$W^* = \arg\min_W \| W X - Q(W \cdot S) S^{-1} X \|_2^2$$

AWQ tidak mengkuantisasi bobot-bobot terpenting secara terpisah (yang akan memperumit struktur data memori), melainkan melindungi bobot tersebut melalui penskalaan matematis yang terintegrasi langsung dalam *grid* kuantisasi group-wise.

#### GPTQ (Generalized Post-Training Quantization)
GPTQ adalah metode kuantisasi bobot tingkat lanjut berbasis pendekatan orde kedua (*second-order Taylor expansion*). Berakar dari metode *Optimal Brain Surgeon* (OBS), GPTQ mengkuantisasi kolom demi kolom pada matriks bobot, dan secara simultan memperbarui (*compensates*) bobot-bobot yang belum dikuantisasi untuk meminimalkan error kuadratik menggunakan invers matriks Hessian $H = 2 X X^T$:

$$\Delta w_q = - \frac{w_q - \text{quant}(w_q)}{[H^{-1}]_{qq}} \cdot H^{-1}_{:, q}$$

GPTQ mengintegrasikan dekomposisi Cholesky untuk stabilitas numerik dan optimasi lazy batching, memungkinkan kuantisasi model 175B parameter diselesaikan dalam beberapa jam compute GPU.

### 3.5 Format Baru: FP8 (E4M3 vs E5M2)

Arsitektur GPU generasi terkini (NVIDIA Ada Lovelace, Hopper H100/H200, Blackwell) memperkenalkan dukungan native hardware untuk representasi Floating Point 8-bit (FP8):

```
FP8 - E4M3 (High Precision, Moderate Range)
┌───┬───────────────┬───────────────┐
│ S │  Exponent (4) │  Mantissa (3) │  Bias = 7, Max = 448
└───┴───────────────┴───────────────┘

FP8 - E5M2 (Low Precision, Wide Dynamic Range)
┌───┬───────────────────┬───────────┐
│ S │   Exponent (5)    │Mantissa(2)│  Bias = 15, Max = 57344
└───┴───────────────────┴───────────┘
```

* **E4M3 (1 sign, 4 exponent, 3 mantissa)**: Ideal untuk aktivasi dan bobot pada inferensi forward pass (*inference compute phase*), karena densitas mantissa yang lebih tinggi meminimalkan noise kuantisasi.
* **E5M2 (1 sign, 5 exponent, 2 mantissa)**: Mengadopsi struktur eksponen FP16 standar. Digunakan pada backpropagation (gradien) atau skenario transfer KV-Cache yang membutuhkan dynamic range sangat lebar untuk menghindari overflow.

---

## 4. Why & What

| Paradigma | Mengapa Digunakan (Why) | Apa Karakteristiknya (What) |
| :--- | :--- | :--- |
| **Weight-Only (W4A16 / W8A16)** | Bottleneck LLM generation (Decode phase) didominasi oleh transfer data bobot dari HBM ke SRAM (*Memory-bound*). W4 memangkas transfer data hingga 4x lipat. | Bobot dikuantisasi ke INT4/INT8. Aktivasi tetap dalam FP16/BF16. Bobot didekuantisasi on-the-fly di register GPU sebelum operasi GEMM FP16. |
| **Weight-Activation (W8A8)** | Pada tahap context-phase (Prefill phase), batch size besar membuat eksekusi bersifat *Compute-bound*. Matmul INT8 menawarkan throughput TFLOPS Tensor Core 2x lebih tinggi dari FP16. | Aktivasi dan bobot sama-sama berada dalam domain INT8. Tensor Cores mengeksekusi INT8 GEMM native (`mma.sync` instructions). |
| **FP8 (E4M3)** | Memberikan performa TFLOPS setara INT8 namun mempertahankan representasi eksponensial floating point, mempermudah konvergensi dan kalibrasi tanpa algoritma kompensasi rumit. | Format native hardware Hopper/Ada. Tidak memerlukan pergeseran Zero-Point ($Z=0$), sepenuhnya didukung cuBLAS dan CUTLASS. |
| **KV-Cache Quantization** | Batas konkurensi (Max Concurrency) server LLM dibatasi oleh VRAM yang terkonsumsi oleh Key-Value cache seiring memanjangnya context window. | Matriks Key dan Value pada Attention Layer dikuantisasi (FP8 atau INT8) sebelum disimpan ke pool VRAM, mengurangi kebutuhan memori hingga 50%. |

---

## 5. How (Workflow Detail)

Alur kerja kuantisasi skala enterprise dari model mentah FP16/BF16 hingga deployment pada cluster produksi:

```
[Base Model (FP16/BF16)]
         │
         ▼
[Calibration Dataset Curation] ──► Minimum 128-512 sampel domain-spesifik
         │
         ▼
[Profiling & Hessian/Scale Estimation]
   ├── Forward Pass Trace
   ├── Aktivasi Outlier Profiling (Per-channel kurtosis analysis)
   └── Kalkulasi Fisher Information / Inverse Hessian Matrix
         │
         ▼
[Algorithmic Transformation]
   ├── Pilihan A: SmoothQuant (Perkalian Scale Invers pada LayerNorm/Bobot)
   ├── Pilihan B: AWQ Grid Search (Penentuan per-group protective scale)
   └── Pilihan C: GPTQ Solver (Cholesky-based column error propagation)
         │
         ▼
[Weight Packing Engine]
   └── Packing sub-byte (INT4/INT3) ke dalam container memory 32-bit (INT32 bitshift packing)
         │
         ▼
[Validation Gate]
   ├── Perplexity Evaluation (Wikitext-2 / C4)
   └── Task Accuracy Benchmark (MMLU, GSM8K) -> Toleransi degradasi < 1%
         │
         ▼
[Serving Engine Ingestion]
   └── Serialisasi ke format safetensors terindeks (vLLM / TensorRT-LLM Engine)
```

---

## 6. Analogy & Diagram ASCII

### 6.1 Analogi Pemindahan Air (SmoothQuant)
Bayangkan pipa air (Aktivasi) terhubung ke turbin sempit (Kuantisasi Bobot). 
* Kondisi Normal: Tekanan air melonjak drastis secara tiba-tiba (*activation spikes*), menghancurkan sudu-sudu turbin presisi rendah.
* Solusi SmoothQuant: Kita memasang katup peredam tekanan (*scale divisor*) tepat sebelum turbin, lalu memperbesar diameter mekanis turbin (*weight multiplier*) secara matematis seimbang. Volume air yang keluar di ujung sistem tetap identik, tetapi tidak ada komponen yang hancur.

### 6.2 Arsitektur Register Execution: W4A16 Fused Dequantization GEMM

```
+-------------------------------------------------------------------------+
| GPU HIGH BANDWIDTH MEMORY (HBM)                                         |
|  [INT4 Packed Weights] (50 GB -> 12.5 GB)     [FP16 Scale & Bias]       |
+-------------------------------------------------------------------------+
                                    │
                         Memory Read (W4 Bandwidth)
                                    ▼
+-------------------------------------------------------------------------+
| STREAMING MULTIPROCESSOR (SM)                                           |
|                                                                         |
|  +--------------------+                                                 |
|  | SRAM Shared Memory |                                                 |
|  +--------------------+                                                 |
|           │                                                             |
|           ▼                                                             |
|  +--------------------+       +---------------------------------------+ |
|  | Registers          | ----> | Fused Dequant Kernel (Triton/CUDA)    | |
|  | (INT4 Raw Bits)    |       |  w_fp16 = (w_int4 - zero) * scale     | |
|  +--------------------+       +---------------------------------------+ |
|                                                   │                     |
|                                                   ▼ (Bobot FP16)        |
|  +--------------------+               +-----------------------+         |
|  | Activations (FP16) | ------------> | Tensor Cores (FP16)   |         |
|  | (Native HBM/SRAM)  |               | D = A * B + C         |         |
|  +--------------------+               +-----------------------+         |
|                                                   │                     |
+---------------------------------------------------|---------------------+
                                                    ▼
                                       Output Tensor FP16 / BF16
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: PyTorch Manual Symmetric/Asymmetric Int8 Quantizer

Implementasi fundamental quantizer dan dequantizer untuk memahami perilaku pembulatan (*rounding behavior*) dan preservasi floating point.

```python
import torch

class TensorQuantizerEngine:
    @staticmethod
    def quantize_symmetric(tensor: torch.Tensor, bits: int = 8) -> tuple[torch.Tensor, torch.Tensor]:
        """
        Kuantisasi Simetris Per-Tensor (Z = 0)
        Cocok untuk Weight tensor dengan distribusi terpusat di sekitar 0.
        """
        qmin = -(2 ** (bits - 1))
        qmax = (2 ** (bits - 1)) - 1
        
        # Cari magnitudo maksimum mutlak
        max_val = torch.max(torch.abs(tensor))
        scale = max_val / qmax
        
        # Hindari pembagian dengan nol
        scale = torch.clamp(scale, min=1e-8)
        
        # Quantize: Round to nearest integer
        quantized = torch.clamp(torch.round(tensor / scale), qmin, qmax).to(torch.int8)
        return quantized, scale

    @staticmethod
    def dequantize_symmetric(quantized_tensor: torch.Tensor, scale: torch.Tensor) -> torch.Tensor:
        """Rekonstruksi aproksimasi nilai floating point."""
        return quantized_tensor.to(torch.float32) * scale

# Verifikasi Numerik
if __name__ == "__main__":
    torch.manual_seed(42)
    original_weight = torch.randn(4, 4, dtype=torch.float32)
    
    q_weight, scale = TensorQuantizerEngine.quantize_symmetric(original_weight, bits=8)
    dequantized_weight = TensorQuantizerEngine.dequantize_symmetric(q_weight, scale)
    
    error = torch.nn.functional.mse_loss(original_weight, dequantized_weight)
    print("Original Tensor:\n", original_weight[0])
    print("\nQuantized Tensor (INT8 representation):\n", q_weight[0])
    print("\nReconstructed Tensor:\n", dequantized_weight[0])
    print(f"\nMean Squared Error (Reconstruction Loss): {error.item():.6f}")
```

### 7.2 Practical Example: Fused W4A16 Dequantization Matmul Kernel dengan OpenAI Triton

Pada inferensi fase Decode, pembacaan bobot dibatasi oleh bandwidth memori. Menyimpan bobot dalam INT4 dan melakukan dekuantisasi langsung di *register* GPU sebelum perkalian matriks FP16 menghasilkan speedup signifikan.

Berikut adalah kernel Triton tingkat produksi yang mendekompresi bobot 4-bit (dipaketkan berpasangan dalam integer 8-bit) dan mengeksekusi perkalian matriks secara terfusi:

```python
import torch
import triton
import triton.language as tl

@triton.autotune(
    configs=[
        triton.Config({'BLOCK_SIZE_M': 64, 'BLOCK_SIZE_N': 64, 'BLOCK_SIZE_K': 32, 'GROUP_SIZE_M': 8}, num_stages=4, num_warps=4),
        triton.Config({'BLOCK_SIZE_M': 128, 'BLOCK_SIZE_N': 64, 'BLOCK_SIZE_K': 32, 'GROUP_SIZE_M': 8}, num_stages=4, num_warps=4),
        triton.Config({'BLOCK_SIZE_M': 64