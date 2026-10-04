# Bab 06: Model Optimization, Packaging, & Containerization
## Module 01: Graph Optimization, Quantization, & Serialisasi Model (ONNX, TensorRT, TorchScript)

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. **Menganalisis dan Memetakan Intermediate Representation (IR):** Mengonstruksi dan merekonstruksi graf komputasi deep learning dari framework native (PyTorch) ke format standar terbuka (ONNX, TorchScript) dengan konfigurasi dynamic axes yang deterministik.
2. **Mengimplementasikan Teknik Quantization Matematik:** Menghitung parameter skala (*scale*) dan titik nol (*zero-point*) untuk Symmetric dan Asymmetric INT8 Quantization, serta mengeksekusi Post-Training Quantization (PTQ) berbasis kalibrasi KL-Divergence.
3. **Mengeksekusi Operator Fusion & Graph Pruning:** Mengotomasi eliminasi *dead-code*, pemangkasan node identitas/dropout, dan penggabungan operator (e.g., `Conv2D + BatchNorm + ReLU`) untuk mereduksi *memory bandwidth pressure* dan *kernel launch overhead*.
4. **Membangun Pipeline Validasi Paritas Numerik:** Menguji toleransi deviasi numerik (*drift error*) antara output model unquantized FP32 vs quantized INT8 menggunakan metrik Absolute Tolerance, Relative Tolerance, dan Cosine Similarity.
5. **Memaketkan Model Artifact Terstandarisasi:** Mengemas graf yang telah dioptimasi bersama metadata arsitektur, dependensi inferensi, dan kontrak I/O ke dalam artefak produksi yang siap dikonsumsi runtime engine (seperti ONNX Runtime atau TensorRT).

---

### 2. Concept Overview

Dalam siklus MLOps tingkat lanjut, inferensi model di lingkungan produksi jarang mengeksekusi framework pelatihan asli (seperti raw PyTorch atau TensorFlow). Runtime framework pelatihan dirancang untuk fleksibilitas komputasi gradien (autograd), pelacakan memori dinamis, dan debugging interaktif, yang menimbulkan overhead latensi, konsumsi footprint memori GPU/CPU yang masif, dan ketergantungan paket runtime yang membengkak.

```
       Native PyTorch Graph
    ┌────────────────────────┐
    │ Conv2D ──> BatchNorm  │ (Overhead: Alokasi memori per layer,
    └──────────────┬─────────┘  Kernel launch terpisah, FP32 4-byte/weight)
                   │
                   ▼  (Operator Fusion & Graph Rewriting)
    ┌────────────────────────┐
    │    Fused Conv_BN_Relu  │ (Optimasi: Kernel launch tunggal,
    └──────────────┬─────────┘  SRAM-resident intermediate states)
                   │
                   ▼  (Quantization: FP32 -> INT8)
    ┌────────────────────────┐
    │   Quantized Tensor     │ (Optimasi: Footprint turun 75%,
    │   (INT8 Scale/ZeroPt)  │  Pemanfaatan Vectorized SIMD/Tensor Cores)
    └────────────────────────┘
```

Untuk menjembatani kesenjangan ini, proses optimasi model beroperasi pada tiga pilar utama:

1. **Graph Rewriting & Compilation:** Mengubah graf eksekusi dinamis menjadi Representasi Perantara (*Intermediate Representation* - IR) statis atau semi-statis. Proses ini memungkinkan kompilator graf menganalisis dependensi aliran data, mengeliminasi node redundan (*Constant Folding*, *Dead-Code Elimination*), dan memadukan beberapa kernel eksekusi GPU menjadi satu (*Operator Fusion*).
2. **Precision Reduction (Quantization):** Memetakan representasi floating-point kontinu berpresisi tinggi (FP32, 32-bit) ke representasi diskret berpresisi rendah (FP16, BF16, INT8, atau FP4). Hal ini mengurangi konsumsi bandwidth bus memori (VRAM/RAM transfer rate) dan mempercepat komputasi aritmatika melalui instruksi perangkat keras khusus (misalnya, NVIDIA Tensor Cores dengan DP4A atau INT8 Tensor Cores).
3. **Deterministic Serialization:** Menghilangkan ketergantungan kode sumber Python melalui serialisasi graf ke dalam format biner portabel. Format seperti **TorchScript** membekukan interpretasi Python VM, sedangkan **ONNX (Open Neural Network Exchange)** menyediakan format graf deklaratif berbasis Protobuf yang independen terhadap bahasa dan perangkat keras, memungkinkan eksekusi oleh backend berperforma tinggi (ONNX Runtime, TensorRT, OpenVINO).

---

### 3. Why It Matters

Di tingkat enterprise, kegagalan mengoptimalkan dan mengemas model secara efisien berdampak langsung pada metrik bisnis dan stabilitas sistem:

* **Inference Latency & Strict SLA:** Pada sistem kritis seperti *fraud detection* perbankan atau *algorithmic trading*, latensi inferensi dibatasi dalam rentang sub-10 milidetik. Menjalankan model FP32 native melalui Python runtime menghasilkan latensi eksekusi dan jitter akibat Python Global Interpreter Lock (GIL) serta kernel overhead. Operator fusion dan kuantisasi INT8 secara konsisten memangkas latensi hingga 2x–5x.
* **Infrastruktur & Cloud Cost (TCO):** Model unoptimized memerlukan GPU berkapasitas memori besar (misal, V100/A100). Dengan mereduksi ukuran memori model sebesar 75% via INT8/FP16, densitas model per GPU/CPU node dapat ditingkatkan secara signifikan, menurunkan biaya infrastruktur komputasi inferensi bulanan hingga puluhan ribu dolar.
* **Hardware Heterogeneity & Vendor Lock-in:** Model yang diikat pada framework PyTorch sulit di-deploy ke akselerator khusus (TPU, FPGA, AWS Inferentia, Apple Silicon, atau edge devices). Serialisasi via ONNX memisahkan proses training dari serving hardware layer, memungkinkan tim MLOps memilih target komputasi paling hemat biaya tanpa mengubah logika pelatihan.
* **Production Reproducibility:** Serialisasi artefak berbasis file biner standar yang menyertakan metadata dependensi meminimalkan insiden *"it worked in the training notebook, but fails in the Go/C++ microservice"*.

---

### 4. Arsitektur & Diagram Komponen

Alur transformasi dari model PyTorch native ke artefak komputasi teroptimasi:

```
+---------------------------------------------------------------------------------------------------+
| TRAINING ENVIRONMENT                                                                              |
|  +--------------------+                                                                           |
|  | PyTorch Model      |                                                                           |
|  | (Eager Mode, FP32) |                                                                           |
|  +---------+----------+                                                                           |
+------------|--------------------------------------------------------------------------------------+
             |
             | [Step 1: Export & Tracing]
             v
+---------------------------------------------------------------------------------------------------+
| INTERMEDIATE REPRESENTATION (IR) STAGE                                                            |
|  +---------------------------------------------------------+                                      |
|  | ONNX Model Graph (Protobuf)                             |                                      |
|  | - Operator Set (Opset 17+)                              |                                      |
|  | - Dynamic Batching Definition                           |                                      |
|  +----------------------------+----------------------------+                                      |
+-------------------------------|-------------------------------------------------------------------+
                                |
             +------------------+------------------+
             |                                     |
             v [Step 2A: CPU/Cross-Platform]       v [Step 2B: GPU-Specific Accelerated]
+----------------------------------------+ +--------------------------------------------------------+
| ONNX RUNTIME OPTIMIZATION PIPELINE     | | TENSORRT COMPILER PIPELINE                             |
|  +----------------------------------+  | |  +--------------------------------------------------+  |
|  | Graph Optimizer Engine           |  | |  | Builder Engine                                   |  |
|  | - Constant Folding               |  | |  | - Layer Fusion (Conv + BN + Relu)                |  |
|  | - Node Elimination               |  | |  | - Kernel Auto-Tuning (Device Specific)           |  |
|  +------------------+---------------+  | |  +----------------------------+---------------------+  |
|                     |                  | |                               |                        |
|  +------------------v---------------+  | |  +----------------------------v---------------------+  |
|  | Calibration & Quantization (PTQ) |  | |  | INT8 Calibration (Entropy / MinMax)              |  |
|  | - INT8 Dynamic / Static          |  | |  +----------------------------+---------------------+  |
|  | - KL-Divergence Histogram        |  | |                               |                        |
|  +------------------+---------------+  | +-------------------------------|------------------------+
+---------------------|------------------+                                 |
                      |                                                    |
                      v                                                    v
+----------------------------------------+ +--------------------------------------------------------+
| ARTIFACT COMPILATION                   | | ARTIFACT COMPILATION                                   |
|  +----------------------------------+  | |  +--------------------------------------------------+  |
|  | Quantized ONNX Model             |  | |  | Serialized TensorRT Plan Engine                  |  |
|  | (*.quant.onnx)                   |  | |  | (*.engine / *.plan)                              |  |
|  +------------------+---------------+  | |  +----------------------------+---------------------+  |
+---------------------|------------------+ +-------------------------------|------------------------+
                      |                                                    |
                      +------------------+---------------------------------+
                                         |
                                         v [Step 3: Verification & Packaging]
+---------------------------------------------------------------------------------------------------+
| ARTIFACT PACKAGING & REGISTRY                                                                     |
|  +---------------------------------------------------------------------------------------------+  |
|  | Inference Package Directory                                                                 |  |
|  | ├── model.onnx / model.plan                                                                 |  |
|  | ├── metadata.json (I/O Shapes, Preprocessing Params, Metrics)                              |  |
|  | └── verification_report.json (Numerical Drift, Latency Benchmark, Cosine Parity Score)     |  |
|  +---------------------------------------------------------------------------------------------+  |
+---------------------------------------------------------------------------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Kompilasi Graf & Operator Fusion
Saat mengeksekusi forward pass native pada GPU, setiap layer menghasilkan instruksi terpisah ke GPU command queue. Sebagai contoh, urutan operasi standar:
1. `Conv2d`: Membaca tensor input dari GPU VRAM (High Bandwidth Memory/HBM), menghitung konvolusi, menulis hasil kembali ke VRAM.
2. `BatchNorm2d`: Membaca kembali dari VRAM, menghitung normalisasi skalar per-channel, menulis kembali ke VRAM.
3. `ReLU`: Membaca dari VRAM, menerapkan $\max(0, x)$, menulis hasil akhir ke VRAM.

Operasi ini adalah *memory-bound*. Waktu terbuang untuk transfer data bolak-balik antara HBM dan On-Chip Shared Memory/Registers (SRAM).
*Operator Fusion* menggabungkan ketiga operasi ini secara matematis ke dalam satu kernel terpadu:
$$y = \max\left(0, \gamma \cdot \left(\frac{W * x + b - \mu}{\sqrt{\sigma^2 + \epsilon}}\right) + \beta\right)$$
Secara komputasi, koefisien konvolusi dapat dilipat (*folded*) sebelum deployment:
$$W_{\text{fused}} = \frac{\gamma}{\sqrt{\sigma^2 + \epsilon}} \cdot W$$
$$b_{\text{fused}} = \frac{\gamma}{\sqrt{\sigma^2 + \epsilon}} \cdot (b - \mu) + \beta$$
Dengan demikian, normalisasi batch menjadi *zero cost operation* pada waktu inferensi, dan aktivasi ReLU dieksekusi langsung pada register sebelum data ditulis ke VRAM.

#### B. Teori Matematika Kuantisasi (Uniform Affine INT8)
Kuantisasi memetakan nilai kontinu dari himpunan bilangan riil $[\alpha, \beta]$ ke himpunan bilangan bulat bertanda diskret $[-128, 127]$ (untuk signed 8-bit).

Hubungan pemetaan didefinisikan secara formal oleh fungsi:
$$q = \text{round}\left(\frac{x}{S}\right) + Z$$

Dan operasi dekuantisasi (rekonstruksi nilai aproksimasi floating-point):
$$\hat{x} = S \cdot (q - Z)$$

Di mana:
* $x \in [\alpha, \beta]$: Nilai floating-point (FP32).
* $q \in [q_{\min}, q_{\max}]$: Nilai quantized integer (INT8, default $-128$ hingga $127$).
* $S$: Skala (*Scale*), bilangan floating-point positif yang merepresentasikan resolusi langkah kuantisasi.
* $Z$: Titik nol (*Zero-point*), bilangan bulat yang merepresentasikan representasi diskret dari nilai riil $0.0$.

##### Formulasi Asymmetric Quantization
Digunakan ketika distribusi tensor aktivasi bersifat asimetris (misal, output aktivasi ReLU yang non-negatif $[0, \beta]$):
$$S = \frac{\beta - \alpha}{q_{\max} - q_{\min}}$$
$$Z = \text{round}\left(\frac{-\alpha \cdot q_{\max} - \beta \cdot q_{\min}}{\beta - \alpha}\right)$$
Jika rentang mencakup 0, $Z$ dijepit (*clamped*) agar berada di rentang $[q_{\min}, q_{\max}]$.

##### Formulasi Symmetric Quantization
Digunakan terutama untuk bobot model (*weights*) di mana distribusi nilainya simetris di sekitar nol, sehingga nilai $Z = 0$:
$$S = \frac{\max(|\alpha|, |\beta|)}{q_{\max}}$$
$$Z = 0$$
Ketiadaan $Z$ mereduksi kompleksitas komputasi aritmatika integer pada level register akselerator perangkat keras.

##### Dynamic vs. Static Post-Training Quantization (PTQ)
* **Dynamic Quantization:** Bobot dikuantisasi secara offline (statis), namun aktivasi dikuantisasi secara dinamis saat inferensi (*on-the-fly*). Tidak memerlukan data kalibrasi, cocok untuk model transformer/RNN yang memiliki bottleneck komputasi pada pemuatan bobot memori, tetapi memiliki sedikit overhead latensi saat konversi aktivasi real-time.
* **Static Quantization:** Bobot dan aktivasi dikuantisasi secara offline. Memerlukan *Calibration Dataset* untuk mengobservasi distribusi aktivasi selama inferensi data representatif. Metode penentuan skala aktivasi umumnya menggunakan:
  1. *MinMax Calibration:* Memetakan batas absolut minimum dan maksimum. Rentan terhadap outlier.
  2. *Entropy Calibration (KL-Divergence):* Meminimalkan hilangnya informasi statistik (relatif entropy) antara distribusi floating-point asli dan distribusi quantized terproyeksi:
     $$D_{KL}(P \parallel Q) = \sum_{i} P(i) \log\left(\frac{P(i)}{Q(i)}\right)$$

#### C. Serialisasi Graf: ONNX Intermediate Representation
ONNX merepresentasikan komputasi sebagai graf terarah asiklik (*Directed Acyclic Graph* - DAG). Elemen kunci dari representasi biner ONNX meliputi:
* **Node:** Merepresentasikan operasi matematika (e.g., `MatMul`, `Gemm`, `Conv`). Setiap node mengikat ke spesifikasi *Opset* tertentu.
* **Tensor/ValueInfo:** Mendefinisikan tipe data (e.g., `TensorProto.FLOAT`, `TensorProto.INT8`) dan dimensi bentuk shape tensor (`shape=[batch_size, 3, 224, 224]`).
* **Initializers:** Bobot konstan model yang dibekukan (*frozen parameters*).
* **Dynamic Axes:** Deklarasi dimensi yang dapat berubah saat runtime (misalnya, batch size variabel atau panjang urutan token variabel pada LLM/Transformer). Tanpa dynamic axes eksplisit, kompilator akan membekukan shape ke nilai saat tracing, menghasilkan kegagalan runtime (*dimension mismatch crash*) jika input batch bervariasi.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi end-to-end framework optimasi model:
1. Export model PyTorch ke format ONNX dengan Dynamic Axes.
2. Validasi struktur graf dan inferensi shape ONNX.
3. Eksekusi Post-Training Dynamic Quantization ke format INT8.
4. Framework pengujian inferensi dan paritas numerik (*Numerical Drift Validation*) antara model dasar FP32 dan model INT8.

```python
import os
import time
import json
import logging
from typing import Dict, Any, Tuple, Optional
from dataclasses import dataclass, asdict

import numpy as np
import torch
import torch.nn as nn
import onnx
import onnxruntime as ort
from onnxruntime.quantization import quantize_dynamic, QuantType

# Inisialisasi konfigurasi logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("ModelOptimizer")


# =====================================================================
# 1. ARSITEKTUR MODEL CONTOH (Untuk Keperluan Ilustrasi Kompilasi)
# =====================================================================
class ProductionSampleModel(nn.Module):
    """
    Arsitektur convolutional/MLP representatif dengan Conv, BatchNorm, 
    dan Linear Projection untuk pengujian ekspor & optimasi.
    """
    def __init__(self, in_features: int = 64, num_classes: int = 10) -> None:
        super().__init__()
        self.feature_extractor = nn.Sequential(
            nn.Linear(in_features, 128),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.Dropout(p=0.1),
            nn.Linear(128, 64),
            nn.ReLU()
        )
        self.classifier = nn.Linear(64, num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        features = self.feature_extractor(x)
        logits = self.classifier(features)
        return logits


# =====================================================================
# 2. METADATA & PARITY VALIDATION SCHEMAS
# =====================================================================
@dataclass(frozen=True)
class ParityMetrics:
    cosine_similarity: float
    max_absolute_error: float
    mean_squared_error: float
    latency_fp32_ms: float
    latency_int8_ms: float
    speedup_ratio: float


@dataclass(frozen=True)
class OptimizationMetadata:
    opset_version: int
    input_shape: Tuple[Optional[int], int]
    output_shape: Tuple[Optional[int], int]
    fp32_artifact_size_bytes: int
    int8_artifact_size_bytes: int
    compression_ratio: float
    parity_metrics: ParityMetrics


# =====================================================================
# 3. CORE OPTIMIZER ENGINE CLASS
# =====================================================================
class ModelOptimizationPipeline:
    """
    Pipeline komprehensif untuk mengekspor, mengoptimasi, menguantisasi,
    dan memvalidasi artefak model inferensi.
    """
    def __init__(
        self,
        model: nn.Module,
        input_dim: int,
        output_dim: int,
        artifacts_dir: str = "artifacts",
        opset_version: int = 17
    ) -> None:
        self.model = model.eval()
        self.input_dim = input_dim
        self.output_dim = output_dim
        self.artifacts_dir = artifacts_dir
        self.opset_version = opset_version
        
        os.makedirs(self.artifacts_dir, exist_ok=True)
        self.fp32_onnx_path = os.path.join(self.artifacts_dir, "model_fp32.onnx")
        self.int8_onnx_path = os.path.join(self.artifacts_dir, "model_int8.quant.onnx")
        self.metadata_path = os.path.join(self.artifacts_dir, "model_metadata.json")

    def export_to_onnx(self) -> None:
        """
        Mengekspor model PyTorch ke format biner ONNX menggunakan Torch Tracing Engine
        dengan konfigurasi dynamic axes untuk throughput variabel.
        """
        logger.info("Memulai proses ekspor model PyTorch ke ONNX (Opset %d)...", self.opset_version)
        dummy_input = torch.randn(1, self.input_dim, dtype=torch.float32)

        try:
            torch.onnx.export(
                self.model,
                dummy_input,
                self.fp32_onnx_path,
                export_params=True,
                opset_version=self.opset_version,
                do_constant_folding=True,
                input_names=["input"],
                output_names=["output"],
                dynamic_axes={
                    "input": {0: "batch_size"},
                    "output": {0: "batch_size"}
                }
            )
            logger.info("Model berhasil diekspor ke: %s", self.fp32_onnx_path)
        except Exception as e:
            logger.error("Gagal mengekspor model ke ONNX: %s", str(e), exc_info=True)
            raise RuntimeError(f"Export Failure: {e}") from e

        # Validasi struktural menggunakan runtime parser ONNX internal
        self._validate_onnx_structural_integrity(self.fp32_onnx_path)

    def _validate_onnx_structural_integrity(self, model_path: str) -> None:
        """Memverifikasi topologi graf dan mendeteksi dependensi node yang putus."""
        logger.info("Menjalankan pemeriksaan integritas struktural ONNX untuk: %s", model_path)
        try:
            onnx_model = onnx.load(model_path)
            onnx.checker.check_model(onnx_model)
            onnx.shape_inference.infer_shapes(onnx_model)
            logger.info("Pemeriksaan integritas graf ONNX lolos tanpa error.")
        except onnx.checker.ValidationError as val_err:
            logger.critical("Graf ONNX terkorupsi atau tidak valid: %s", str(val_err))
            raise ValueError(f"ONNX Corrupted: {val_err}") from val_err

    def quantize_model(self) -> None:
        """
        Menjalankan Post-Training Dynamic Quantization (PTQ) ke presisi INT8
        pada lapisan komputasi linier (Gemm/MatMul).
        """
        logger.info("Memulai Post-Training Dynamic Quantization (INT8)...")
        if not os.path.exists(self.fp32_onnx_path):
            raise FileNotFoundError(f"Model dasar {self.fp32_onnx_path} tidak ditemukan.")

        try:
            quantize_dynamic(
                model_input=self.fp32_onnx_path,
                model_output=self.int8_onnx_path,
                weight_type=QuantType.QInt8,
                nodes_to_quantize=[],  # Mengoptimalkan seluruh kandidat layer linier secara default
                extra_options={"EnableSubgraph": True, "ForceQuantizeNoInputCheck": False}
            )
            logger.info("Kuantisasi sukses. File dihasilkan: %s", self.int8_onnx_path)
        except Exception as e:
            logger.error("Kuantisasi model gagal dieksekusi: %s", str(e), exc_info=True)
            raise RuntimeError(f"Quantization Failure: {e}") from e

        self._validate_onnx_structural_integrity(self.int8_onnx_path)

    def benchmark_and_validate_parity(
        self,
        batch_size: int = 32,
        num_iterations: int = 200,
        similarity_threshold: float = 0.995
    ) -> ParityMetrics:
        """
        Memvalidasi divergensi output antara FP32 dan INT8 via Cosine Similarity,
        serta memprofil latensi eksekusi rata-rata per iterasi.
        """
        logger.info("Memulai validasi paritas numerik dan benchmarking inferensi...")

        # Setup runtime session dengan Thread Concurrency Controls terisolasi
        session_options = ort.SessionOptions()
        session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        session_options.intra_op_num_threads = 2
        session_options.inter_op_num_threads = 1

        session_fp32 = ort.InferenceSession(self.fp32_onnx_path, session_options, providers=["CPUExecutionProvider"])
        session_int8 = ort.InferenceSession(self.int8_onnx_path, session_options, providers=["CPUExecutionProvider"])

        # Sintesis test batch deterministik
        np.random.seed(42)
        test_inputs = np.random.randn(batch_size, self.input_dim).astype(np.float32)

        input_name = session_fp32.get_inputs()[0].name

        # Warm-up phase untuk cache instruksi prosesor
        for _ in range(20):
            _ = session_fp32.run(None, {input_name: test_inputs})
            _ = session_int8.run(None, {input_name: test_inputs})

        # Profiling Latensi FP32
        latencies_fp32 = []
        for _ in range(num_iterations):
            t0 = time.perf_counter()
            out_fp32 = session_fp32.run(None, {input_name: test_inputs})[0]
            latencies_fp32.append((time.perf_counter() - t0) * 1000.0)

        # Profiling Latensi INT8
        latencies_int8 = []
        for _ in range(num_iterations):
            t0 = time.perf_counter()
            out_int8 = session_int8.run(None, {input_name: test_inputs})[0]
            latencies_int8.append((time.perf_counter() - t0) * 1000.0)

        mean_lat_fp32 = float(np.mean(latencies_fp32))
        mean_lat_int8 = float(np.mean(latencies_int8))
        speedup = mean_lat_fp32 / mean_lat_int8 if mean_lat_int8 > 0 else 1.0

        # Kalkulasi Metrik Paritas Numerik
        flat_fp32 = out_fp32.flatten()
        flat_int8 = out_int8.flatten()

        dot_prod = np.dot(flat_fp32, flat_int8)
        norm_fp32 = np.linalg.norm(flat_fp32)
        norm_int8 = np.linalg.norm(flat_int8)
        cosine_sim = float(dot_prod / (norm_fp32 * norm_int8 + 1e-12))
        max_ae = float(np.max(np.abs(flat_fp32 - flat_int8)))
        mse = float(np.mean((flat_fp32 - flat_int8) ** 2))

        metrics = ParityMetrics(
            cosine_similarity=cosine_sim,
            max_absolute_error=max_ae,
            mean_squared_error=mse,
            latency_fp32_ms=mean_lat_fp32,
            latency_int8_ms=mean_lat_int8,
            speedup_ratio=speedup
        )

        logger.info(
            "Benchmark Result: Latency FP32=%.3fms | Latency INT8=%.3fms | Speedup=%.2fx",
            metrics.latency_fp32_ms, metrics.latency_int8_ms, metrics.speedup_ratio
        )
        logger.info("Numerical Parity: Cosine Similarity=%.6f | MaxAE=%.6f", cosine_sim, max_ae)

        if cosine_sim < similarity_threshold:
            logger.critical(
                "Numerical drift melampaui batas toleransi! Sim: %.4f < Threshold: %.4f",
                cosine_sim, similarity_threshold
            )
            raise ValueError(f"Divergensi Numerik INT8 tidak dapat diterima (Cosine Sim: {cosine_sim})")

        return metrics

    def generate_and_package_metadata(self, metrics: ParityMetrics) -> None:
        """Membuat dokumen deklarasi metadata artefak untuk keperluan governance/serving deployment."""
        fp32_size = os.path.getsize(self.fp32_onnx_path)
        int8_size = os.path.getsize(self.int8_onnx_path)
        compression = fp32_size / int8_size if int8_size > 0 else 1.0

        meta = OptimizationMetadata(
            opset_version=self.opset_version,
            input_shape=(None, self.input_dim),
            output_shape=(None, self.output_dim),
            fp32_artifact_size_bytes=fp32_size,
            int8_artifact_size_bytes=int8_size,
            compression_ratio=compression,
            parity_metrics=metrics
        )

        with open(self.metadata_path, "w", encoding="utf-8") as f:
            json.dump(asdict(meta), f, indent=4)
        logger.info("Metadata deployment berhasil disimpan pada: %s", self.metadata_path)


# =====================================================================
# 4. RUNTIME EXECUTION & TESTING
# =====================================================================
if __name__ == "__main__":
    INPUT_FEATURES = 128
    OUTPUT_CLASSES = 10

    # Menginisialisasi model PyTorch native
    torch.manual_seed(42)
    raw_model = ProductionSampleModel(in_features=INPUT_FEATURES, num_classes=OUTPUT_CLASSES)

    # Eksekusi pipeline optimasi
    pipeline = ModelOptimizationPipeline(
        model=raw_model,
        input_dim=INPUT_FEATURES,
        output_dim=OUTPUT_CLASSES,
        artifacts_dir="./model_package"
    )

    pipeline.export_to_onnx()
    pipeline.quantize_model()
    validation_metrics = pipeline.benchmark_and_validate_parity(batch_size=64, num_iterations=100)
    pipeline.generate_and_package_metadata(validation_metrics)
```

---

### 7. Edge Cases & Failure Modes

Pada implementasi kompilasi dan kuantisasi produksi, arsitek sistem harus memitigasi kegagalan spesifik berikut:

1. **Dynamic Shape Operator Explosion:**
   * *Mekanisme:* Jika operasi reshaping (seperti `.view()`, `.reshape()`, atau slicing) diekspor tanpa dynamic axis yang diikat dengan benar, PyTorch mengompilasi dimensi runtime menjadi konstanta hardcoded. Ketika menerima request batch size non-standar, eksekutor ONNX Runtime melempar: `INVALID_ARGUMENT: Got invalid dimensions for input`.
   * *Mitigasi:* Selalu uji artefak graf dengan tensor input variatif: $N=1$, $N=37$ (bilangan prima acak), dan $N=256$.

2. **Underflow & Catastrophic Cancellation pada INT8:**
   * *Mekanisme:* Model dengan rentang aktivasi dinamis sangat lebar (misal, layer logit Transformer tanpa normalisasi) mengalami saturasi/clamping. Semua nilai di luar rentang kuantisasi terpotong menjadi $-128$ atau $127$. Dampaknya, akurasi klasifikasi atau perplexity anjlok drastis (*catastrophic accuracy drop*).
   * *Mitigasi:* Gunakan Quantization-Aware Training (QAT) alih-alih PTQ jika $D_{KL}$ atau Cosine Similarity jatuh di bawah $0.990$. Terapkan per-channel quantization pada bobot konvolusi/linear.

3. **Unsupported Opset Mapping Failure:**
   * *Mekanisme:* Layer custom, operasi non-standar (misalnya kueri `einops`, fungsi sampling non-deterministik), atau operator PyTorch baru yang belum terdaftar pada standar Open Neural Network Exchange akan melempar exception `RuntimeError: Exporting the operator ... to ONNX opset is not supported`.
   * *Mitigasi:* Definisikan custom symbolic function menggunakan API `torch.onnx.register_custom_op_symbolic` atau refaktor arsitektur ke layer komputasi primitif standard yang didukung oleh Opset target.

4. **Engine Deserialization Failure (Host Platform Mismatch):**
   * *Mekanisme:* Serialisasi mesin seperti NVIDIA TensorRT engine (`.plan`) bersifat **hardware-locked** dan **driver-locked**. Rencana biner yang dikompilasi pada arsitektur GPU Ampere (e.g., A100) akan mengalami kegagalan *segmentation fault* atau crash inisialisasi jika dieksekusi pada arsitektur Hopper (H100) atau Turing (T4).
   * *Mitigasi:* Jangan pernah mendistribusikan TensorRT binary engine secara langsung ke cross-environment registry. Distribusikan format perantara ONNX, dan lakukan kompilasi TensorRT engine secara dinamis saat container bootstrap di host instance target.

---

### 8. Trade-offs & Alternatif Solusi

Setiap keputusan optimasi dan serialisasi memiliki trade-off arsitektur:

| Pendekatan / Engine | Latensi Inferensi | Fleksibilitas Portabilitas | Kompleksitas Pipeline | Rekomendasi Kasus Penggunaan |
| :--- | :--- | :--- | :--- | :--- |
| **Native PyTorch (Eager Mode)** | Rendah (Lambat) | Sangat Tinggi (Python Ecosystem) | Sangat Rendah | Research, prototyping, offline batch testing berlatensi longgar. |
| **TorchScript (Torch.jit)** | Sedang | Rendah (Tergantung LibTorch C++) | Rendah | Deployment homogen C++ di mana pipeline hanya berjalan di lingkungan PyTorch. |
| **ONNX Runtime (FP32)** | Tinggi | Tinggi (Multi-OS, Multi-Vendor CPU/GPU) | Sedang | Deployment standar lintas sistem (Linux/Windows, x86/ARM), fallback server inferensi. |
| **ONNX Runtime (INT8 PTQ)** | Sangat Tinggi | Tinggi (Optimal di CPU dengan AVX-512/VNNI) | Sedang | Server berdensitas tinggi berbasis CPU untuk menurunkan biaya komputasi GPU cloud. |
| **TensorRT (FP16 / INT8 QAT)** | Maksimum (Ultra Cepat) | Nol (Lock-in pada GPU NVIDIA spesifik) | Tinggi | Sistem inferensi skala besar real-time berlatensi ultra-rendah (<5ms) pada GPU NVIDIA. |

---

### 9. Best Practices & Standard Industri

* **Strict Input/Output Schema Enforcement:** Selalu enkapsulasi artefak biner dengan deklarasi skema tipe data, batasan dimensi min/max, dan parameter normalisasi (misal: mean, std, warna channel format). Jangan biarkan data preprocessing terlepas dari artefak model.
* **Deterministic Calibration Set:** Kalibrasi INT8 PTQ harus menggunakan minimal 100–1000 data sampel representatif dari log produksi riil, bukan random normal distribution.
* **Continuous Numerical Drift Testing di CI/CD:** Jalankan unit test validasi paritas setiap kali checkpoint bobot diperbarui. Tetapkan batas metrik CI/CD:
  * $\text{Cosine Similarity} \ge 0.995$
  * $\text{Accuracy Loss} \le 0.5\%$ dari baseline FP32
* **Triton Inference Server Compliance:** Strukturkan penyimpanan artefak model mengikuti standar Triton Model Repository:
  ```text
  model_repository/
  └── production_model/
      ├── config.pbtxt
      ├── 1/
      │   └── model.onnx
      └── metadata.json
  ```
* **Memory Management pada Inference Daemon:** Atur batas memori graf pada runtime environment. Sebagai contoh, di ONNX Runtime atur alokator memori GPU:
  ```python
  cuda_provider_options = {
      'device_id': 0,
      'gpu_mem_limit': 4 * 1024 * 1024 * 1024, # 4 GB
      'arena_extend_strategy': 'kSameAsRequested'
  }
  ```

---

### 10. Hands-on Lab Exercise

#### Skenario Lab
Anda adalah MLOps Platform Engineer yang ditugaskan untuk mengoptimasi model klasifikasi citra/embedding yang lambat dan mengonsumsi memori besar di cluster CPU edge deployment. Anda harus mengekspor model dasar, mengonversinya ke ONNX, menerapkan INT8 Dynamic Quantization, memvalidasi stabilitas numerik, dan mengukur throughput.

#### Step-by-Step Execution

##### Langkah 1: Persiapan Environment
Pasang library yang diperlukan:
```bash
pip install torch torchvision onnx onnxruntime tabulate
```

##### Langkah 2: Buat Script Optimasi (`run_optimization_lab.py`)
Tulis skrip berikut untuk menguji efisiensi model ResNet block:

```python
import time
import os
import torch
import torchvision.models as models
import onnx
import onnxruntime as ort
from onnxruntime.quantization import quantize_dynamic, QuantType
import numpy as np

def run_lab():
    print("=== [1] Inisialisasi Model ResNet18 Native ===")
    model = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)
    model.eval()

    dummy_input = torch.randn(1, 3, 224, 224)
    onnx_fp32_path = "resnet18_fp32.onnx"
    onnx_int8_path = "resnet18_int8.quant.onnx"

    print("=== [2] Mengekspor ke ONNX dengan Dynamic Batch Size ===")
    torch.onnx.export(
        model,
        dummy_input,
        onnx_fp32_path,
        export_params=True,
        opset_version=17,
        input_names=["input"],
        output_names=["output"],
        dynamic_axes={"input": {0: "batch_size"}, "output": {0: "batch_size"}}
    )
    print(f"File tersimpan: {onnx_fp32_path} ({os.path.getsize(onnx_fp32_path) / (1024*1024):.2f} MB)")

    print("=== [3] Mengaplikasikan Dynamic Quantization INT8 ===")
    quantize_dynamic(
        model_input=onnx_fp32_path,
        model_output=onnx_int8_path,
        weight_type=QuantType.QInt8
    )
    print(f"File tersimpan: {onnx_int8_path} ({os.path.getsize(onnx_int8_path) / (1024*1024):.2f} MB)")

    print("=== [4] Benchmarking Latensi CPU (Batch Size: 8, Iterasi: 50) ===")
    test_batch = np.random.randn(8, 3, 224, 224).astype(np.float32)

    sess_fp32 = ort.InferenceSession(onnx_fp32_path, providers=["CPUExecutionProvider"])
    sess_int8 = ort.InferenceSession(onnx_int8_path, providers=["CPUExecutionProvider"])

    # Warmup
    for _ in range(5):
        sess_fp32.run(None, {"input": test_batch})
        sess_int8.run(None, {"input": test_batch})

    # Benchmark FP32
    start = time.perf_counter()
    for _ in range(50):
        out_fp32 = sess_fp32.run(None, {"input": test_batch})[0]
    lat_fp32 = (time.perf_counter() - start) / 50 * 1000

    # Benchmark INT8
    start = time.perf_counter()
    for _ in range(50):
        out_int8 = sess_int8.run(None, {"input": test_batch})[0]
    lat_int8 = (time.perf_counter() - start) / 50 * 1000

    print("=== [5] Laporan Hasil Optimasi ===")
    size_reduction = (1 - (os.path.getsize(onnx_int8_path) / os.path.getsize(onnx_fp32_path))) * 100
    print(f"Latensi Rata-rata FP32 : {lat_fp32:.2f} ms")
    print(f"Latensi Rata-rata INT8 : {lat_int8:.2f} ms")
    print(f"Akselerasi Latensi     : {lat_fp32 / lat_int8:.2f}x Speedup")
    print(f"Reduksi Ukuran File    : {size_reduction:.2f}%")

    # Paritas Numerik Top-5 Match Rate
    top5_matches = 0
    for i in range(len(test_batch)):
        top5_fp32 = np.argsort(out_fp32[i])[-5:]
        top5_int8 = np.argsort(out_int8[i])[-5:]
        if len(np.intersect1d(top5_fp32, top5_int8)) >= 4:
            top5_matches += 1

    match_rate = (top5_matches / len(test_batch)) * 100
    print(f"Kesesuaian Top-5 Label : {match_rate:.1f}%")
    assert match_rate >= 80.0, "Validasi Akurasi Gagal: Deviasi numerik terlalu ekstrem!"

if __name__ == "__main__":
    run_lab()
```

##### Langkah 3: Eksekusi dan Verifikasi Output
Jalankan skrip:
```bash
python run_optimization_lab.py
```

##### Kriteria Keberhasilan:
1. File `resnet18_fp32.onnx` dan `resnet18_int8.quant.onnx` terbentuk dengan benar di filesystem.
2. Ukuran file terkuantisasi INT8 mengalami penurunan ukuran sebesar $\sim 50\% - 75\%$ dibandingkan model awal FP32.
3. Assert check `Top-5 Label Parity` mencapai target $\ge 80\%$, memastikan preservasi logika klasifikasi pasca-kuantisasi.