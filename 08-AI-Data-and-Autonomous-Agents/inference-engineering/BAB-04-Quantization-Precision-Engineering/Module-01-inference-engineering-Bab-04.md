# Bab 04: Quantization & Precision Engineering
## Modul 01: Fondasi Matematika Uniform Quantization & Precision Representation

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis** representasi bit-level dari berbagai format numerik (*IEEE 754 FP32*, *FP16*, *BF16*, *FP8 E4M3/E5M2*, dan *INT8/INT4*) serta implikasinya terhadap *dynamic range*, *precision loss*, dan konsumsi *memory bandwidth*.
- **Menurunkan dan Memformulasikan** pemetaan matematis *Uniform Quantization*, mencakup skema *Affine (Asymmetric)* dan *Scale-only (Symmetric)*, baik pada granularitas *Per-Tensor*, *Per-Channel*, maupun *Per-Group/Per-Token*.
- **Mengimplementasikan** *engine* kuantisasi dan dekuantisasi *production-ready* dari *first principles* menggunakan Python dan PyTorch tensor primitives, lengkap dengan *numerical guards*, *outlier clipping*, dan validasi dimensional.
- **Mengevaluasi** propagasi *quantization error* melalui metrik *Signal-to-Quantization-Noise Ratio* (SQNR) dan *Mean Squared Error* (MSE) pada kalibrasi distribusi bobot (*weights*) dan aktivasi (*activations*).
- **Mendiagnosis dan Memitigasi** anomali numerik tingkat rendah, seperti *zero-point drift*, *underflow/overflow saturation*, dan pembagian dengan skala nol (*zero dynamic range*) dalam eksekusi inferensi enterprise.

---

### 2. Concept Overview

Quantization adalah proses pemetaan sinyal kontinu atau data berpresisi tinggi (biasanya $\mathbb{R}$) ke himpunan nilai diskret berpresisi rendah ($\mathbb{Z}$ atau format floating-point dengan bit lebih sedikit). Dalam rekayasa inferensi (*inference engineering*), kuantisasi adalah teknik utama untuk mengatasi *Memory Wall*: ketidakseimbangan ekstrem antara kecepatan komputasi tensor core prosesor (GPU/NPU) dan *bandwidth* transfer data dari DRAM ke SRAM (On-chip Cache).

#### 2.1 Representasi Floating Point vs. Fixed-Point / Integer

Format bilangan biner terbagi menjadi representasi eksponensial (Floating Point) dan linear (Fixed Point/Integer):

```
FP32 (IEEE 754):  [ 1b Sign ] [ 8b Exponent (bias 127) ] [ 23b Mantissa / Fraction ]
FP16:             [ 1b Sign ] [ 5b Exponent (bias 15)  ] [ 10b Mantissa / Fraction ]
BF16:             [ 1b Sign ] [ 8b Exponent (bias 127) ] [  7b Mantissa / Fraction ]
FP8 (E4M3):       [ 1b Sign ] [ 4b Exponent (bias 7)   ] [  3b Mantissa / Fraction ]
FP8 (E5M2):       [ 1b Sign ] [ 5b Exponent (bias 15)  ] [  2b Mantissa / Fraction ]
INT8:             [ 1b Sign ] [ 7b Magnitude           ] (Two's Complement: -128 to 127)
UINT8:            [ 8b Unsigned Value                  ] (0 to 255)
```

- **FP32 $\to$ FP16**: Memangkas eksponen dan mantisa, rentan *underflow* ($< 6.1 \times 10^{-5}$) dan *overflow* ($> 65504$).
- **FP32 $\to$ BF16**: Mempertahankan jangkauan eksponen FP32 ($10^{\pm 38}$), memangkas presisi mantisa. Pilihan ideal untuk stabilitas kalkulasi gradien dan aktivasi tanpa kalibrasi intensif.
- **FP8 (E4M3 vs. E5M2)**: Standar OCP (*Open Compute Project*). E4M3 memberikan presisi lebih tinggi untuk kalkulasi aktivasi/bobot *forward pass*, sedangkan E5M2 meniru dynamic range FP16 untuk kalkulasi gradien atau *backward pass*.
- **INT8 / INT4**: Linear grid quantization. Representasi tanpa eksponen biner individual; nilai riil diskalakan menggunakan faktor skala floating-point bersama (*scale factor* $S$).

#### 2.2 Mental Model: Pemetaan Kisi Linear (Uniform Grid Mapping)

*Uniform Quantization* membagi interval kontinu $[x_{\min}, x_{\max}]$ ke dalam $2^b - 1$ sub-interval yang berjarak seragam, di mana $b$ adalah panjang bit target (misalnya, $b=8$ untuk INT8).

```
Dunia Riil Kontinu (FP32):
----|-------------|-------------|-------------|-------------|---->
  x_min          x_1           x_2           x_3          x_max

Pemetaan Grid Diskrit (INT8, q):
----|-------------|-------------|-------------|-------------|---->
  q_min         q_min+1       q_min+2       q_min+3       q_max
   (0)           (1)           (2)           (3)          (255)
```

Proses transformasi ini melibatkan dua operasi utama:
1. **Quantize ($Q$)**: Mengubah $x \in \mathbb{R}$ menjadi integer $q \in [\alpha, \beta]$.
2. **Dequantize ($DQ$)**: Merekonstruksi perkiraan floating-point $\hat{x} \approx x$ dari nilai terkuantisasi $q$.

Kesalahan rekonstruksi $|x - \hat{x}|$ disebut sebagai *Quantization Error* atau *Quantization Noise*.

---

### 3. Why It Matters

Implementasi model parameter besar (LLM seperti LLaMA-3, Mistral, atau Vision Transformers berukuran multi-miliar parameter) pada skala produksi menghadapi kendala fisik perangkat keras:

1. **Memory Bandwidth Bottleneck (The Memory Wall)**:
   Pada tahap *autoregressive decoding* LLM, inferensi bersifat sangat *memory-bound* (Arithmetic Intensity rendah: $FLOPs/Byte \ll 1$). Membaca bobot model dari GPU High Bandwidth Memory (HBM3) ke compute unit mendominasi latensi. Mengurangi ukuran bobot dari FP16 (2 byte) ke INT4 (0.5 byte) menghasilkan percepatan *throughput* memori murni hingga $\approx 4\times$.
2. **VRAM Footprint & Multi-Tenancy**:
   Model FP16 70B membutuhkan $70 \times 2\text{ GB} = 140\text{ GB}$ VRAM murni hanya untuk menampung bobot model, memerlukan minimal 2 node GPU A100/H100 80GB via Tensor Parallelism ($TP=2$ atau $TP=4$). Melalui kuantisasi INT4 (misal: GPTQ, AWQ), model dapat ditampung dalam 1 GPU 40GB/80GB ($35\text{ GB}$ footprint bobot), memangkas biaya infrastruktur cloud hingga 75%.
3. **Compute Efficiency (DP4A vs. Tensor Core INT8/FP8)**:
   Operasi perkalian matriks berbasis Integer ($INT8 \times INT8 \to INT32$) pada Tensor Core modern (seperti NVIDIA Ada Lovelace / Hopper) mengeksekusi TFLOPS/TOPS hingga $2\times$ lipat lebih tinggi dibanding operasi $FP16 \times FP16 \to FP32$, dengan konsumsi daya (Joule per MAC operation) yang signifikan lebih rendah.

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut memetakan arsitektur transformasi tensor dari FP32/FP16 menjadi INT8/INT4, penanganan matriks akumulasi integer, dan rekonstruksi kembali ke domain floating-point:

```
+-----------------------------------------------------------------------------+
|                               HOST / CLIENT MEMORY                          |
|  Tensor Float-32 / Float-16:  X in R^{M x K}                                |
+-----------------------------------------------------------------------------+
                                      |
                                      v
+-----------------------------------------------------------------------------+
|                          CALIBRATION & RANGE ESTIMATION                     |
|  - Per-Tensor / Per-Channel / Per-Token Extraction                          |
|  - Min/Max Detection -> Dynamic Range: [x_min, x_max]                       |
|  - Outlier Mitigation (Percentile Clipping / MSE Optimization)              |
+-----------------------------------------------------------------------------+
                                      |
                                      v
+-----------------------------------------------------------------------------+
|                       GRID PARAMETER FORMULATION ENGINE                     |
|                                                                             |
|  [Symmetric]                                  [Asymmetric / Affine]         |
|  Scale S = max(|x|) / (2^{b-1}-1)             Scale S = (x_max - x_min) /   |
|  Zero-point Z = 0                                       (2^b - 1)           |
|                                               Zero-point Z = -round(x_min/S)|
+-----------------------------------------------------------------------------+
                                      |
                                      v
+-----------------------------------------------------------------------------+
|                     QUANTIZATION TRANSFORMATION STAGE                       |
|                                                                             |
|  Formula:  q = clamp( round( X / S ) + Z,  q_min,  q_max )                  |
|  Output:   Q_X in INT8 / UINT8 / INT4 (Packed format)                       |
+-----------------------------------------------------------------------------+
                                      |
                                      v
+-----------------------------------------------------------------------------+
|                     ACCELERATED INTEGER GEMM KERNEL                         |
|                                                                             |
|  Q_Y_int32 = (Q_X - Z_X) @ (Q_W - Z_W)                                      |
|            = Q_X @ Q_W - Z_W * sum(Q_X) - Z_X * sum(Q_W) + Z_X * Z_W * K    |
|  (Catatan: Jika Symmetric Z_W=0, overhead akumulasi tereliminasi)           |
+-----------------------------------------------------------------------------+
                                      |
                                      v
+-----------------------------------------------------------------------------+
|                        DEQUANTIZATION & OUTPUT STAGE                        |
|                                                                             |
|  Y_fp = (S_X * S_W) * Q_Y_int32                                             |
|  Output: Y in R^{M x N} (FP16 / BF16 / FP32)                                |
+-----------------------------------------------------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### 5.1 Affine (Asymmetric) Quantization
Digunakan ketika distribusi data tidak simetris terhadap nol (misalnya aktivasi setelah fungsi ReLU atau GeLU yang condong ke nilai non-negatif).

**Formulasi:**
$$q = \text{clip}\left(\left\lfloor \frac{x}{S} \right\rceil + Z, \; q_{\min}, \; q_{\max}\right)$$

$$\hat{x} = S \cdot (q - Z)$$

Di mana:
- $S \in \mathbb{R}^+$ adalah faktor skala (*scale factor*):
  $$S = \frac{x_{\max} - x_{\min}}{q_{\max} - q_{\min}}$$
- $Z \in \mathbb{Z}$ adalah *zero-point* (offset integer yang memetakan nilai $0.0$ riil ke domain terkuantisasi):
  $$Z = \text{clip}\left(\left\lfloor -\frac{x_{\min}}{S} \right\rceil + q_{\min}, \; q_{\min}, \; q_{\max}\right)$$
- $\lfloor \cdot \rceil$ menunjukkan fungsi pembulatan ke integer terdekat (*round-to-nearest-even*).

#### 5.2 Symmetric Quantization
Digunakan ketika distribusi berpusat di sekitar nol (tipikal untuk *weights* neural network atau aktivasi yang dinormalisasi dengan RMSNorm/LayerNorm). *Zero-point* dikunci secara statis pada nilai $0$ ($Z = 0$), menyederhanakan aljabar linier komputasi GEMM.

**Formulasi:**
$$q = \text{clip}\left(\left\lfloor \frac{x}{S} \right\rceil, \; q_{\min}, \; q_{\max}\right)$$

$$\hat{x} = S \cdot q$$

Untuk format *signed 8-bit* bertaraf simetris:
- Rentang simetris penuh (Full-range): $q_{\min} = -128, q_{\max} = 127$. Skala dihitung dengan:
  $$S = \frac{\max(|x_{\min}|, |x_{\max}|)}{127}$$
  *(Kelemahan: Asimetri representasi antara -128 dan 127 dapat memicu bias dc kecil).*
- Rentang simetris restriktif (Restricted-range): $q_{\min} = -127, q_{\max} = 127$. Skala:
  $$S = \frac{\max(|x_{\min}|, |x_{\max}|)}{127}$$

#### 5.3 Dampak Aljabar Komputasi pada Matriks Perkalian (GEMM)
Ditinjau dari operasi perkalian matriks aktivasi $X \in \mathbb{R}^{M \times K}$ dan bobot $W \in \mathbb{R}^{K \times N}$:
$$Y = XW$$

Jika dikuantisasi secara asimetris:
$$\hat{Y}_{i,j} = \sum_{k=1}^{K} S_X (q_{X_{i,k}} - Z_X) \cdot S_W (q_{W_{k,j}} - Z_W)$$
$$\hat{Y}_{i,j} = S_X S_W \left[ \sum_{k=1}^K q_{X_{i,k}} q_{W_{k,j}} - Z_W \sum_{k=1}^K q_{X_{i,k}} - Z_X \sum_{k=1}^K q_{W_{k,j}} + K \cdot Z_X Z_W \right]$$

Perhatikan beban komputasinya:
1. $\sum_{k=1}^K q_{X_{i,k}} q_{W_{k,j}}$ dihitung cepat melalui INT8 Tensor Cores.
2. Suku kedua bergantung pada kalkulasi dinamis reduksi baris $X$.
3. Suku ketiga dapat di-*precompute* secara statis untuk bobot $W$.
4. Suku keempat adalah konstanta skalar.

Jika $W$ dikuantisasi secara **simetris** ($Z_W = 0$), suku kedua lenyap seluruhnya:
$$\hat{Y}_{i,j} = S_X S_W \left[ \sum_{k=1}^K q_{X_{i,k}} q_{W_{k,j}} - Z_X \sum_{k=1}^K q_{W_{k,j}} \right]$$
Hal inilah yang mendasari mengapa industri (misal: TensorRT, vLLM) hampir selalu memilih **Symmetric Quantization untuk Weights**.

#### 5.4 Granularitas Kuantisasi

```
Per-Tensor:      [   Tensor Penuh: Satu Skala (S), Satu Zero-Point (Z)   ]
--------------------------------------------------------------------------
Per-Channel:     [ Kanal 0: S_0, Z_0 ]  [ Kanal 1: S_1, Z_1 ] ... [ Kanal C: S_C, Z_C ]
--------------------------------------------------------------------------
Per-Group/Block: [ Grup 0 (G=128) ]     [ Grup 1 (G=128) ]     ... (AWQ / GPTQ)
```

1. **Per-Tensor**:
   - Seluruh matriks menggunakan satu nilai $S$ dan satu nilai $Z$.
   - *Memory overhead* metadata kuantisasi minimum ($O(1)$).
   - Presisi terburuk jika terdapat variasi dinamis ekstrem antar kanal (sering memicu degradasi akurasi besar pada model Transformer akibat anomali *activation outliers*).
2. **Per-Channel / Per-Axis (Weights)**:
   - Satu skala independen untuk setiap baris/kolom matriks proyeksi bobot (biasanya per-output channel).
   - Memitigasi variasi magnitudo bobot antar filter; standar de-facto untuk bobot konvolusi dan linear projection.
3. **Per-Token / Per-Group (Activations & Low-bit Weights)**:
   - Kuantisasi grup: membagi deret vektor berdimensi $K$ menjadi sub-blok (misal grup berukuran 64 atau 128 elemen) yang masing-masing memiliki parameter skala.
   - Esensial untuk format kuantisasi sub-8-bit (INT4, INT3, INT2) agar *quantization noise* tidak mendominasi sinyal asli.

---

### 6. Production-Ready Code Implementation

Berikut implementasi lengkap, modular, dan tervariasi dalam arsitektur kelas berstandar enterprise menggunakan PyTorch. Implementasi ini mencakup skema Simetris dan Asimetris, kalibrasi *Per-Tensor* dan *Per-Channel*, penanganan kasus batas (*zero division*, *outlier saturation*), serta *dequantization*.

```python
"""
Core Uniform Quantization Engine for Inference Engineering.
Designed for high numerical stability and modular production deployment.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple, Union

import torch


class QuantMode(Enum):
    SYMMETRIC = "symmetric"
    ASYMMETRIC = "asymmetric"


class Granularity(Enum):
    PER_TENSOR = "per_tensor"
    PER_CHANNEL = "per_channel"


@dataclass(frozen=True)
class QuantizationParameters:
    """Immutable data container for quantization scaling and zero-point parameters."""
    scale: torch.Tensor
    zero_point: torch.Tensor
    bit_width: int
    qmin: int
    qmax: int
    mode: QuantMode
    granularity: Granularity
    ch_axis: Optional[int] = None


class UniformQuantizer:
    """
    Production-grade Uniform Quantization Engine supporting arbitrary bit-widths,
    symmetric/asymmetric schemes, and per-tensor/per-channel granularities.
    """

    EPSILON: float = 1e-8

    def __init__(
        self,
        bit_width: int = 8,
        mode: QuantMode = QuantMode.SYMMETRIC,
        granularity: Granularity = Granularity.PER_TENSOR,
        ch_axis: int = 0,
        narrow_range: bool = False,
    ) -> None:
        """
        Initializes the quantizer configuration.

        Args:
            bit_width: Integer precision (e.g., 4, 8, 16).
            mode: QuantMode.SYMMETRIC or QuantMode.ASYMMETRIC.
            granularity: Granularity.PER_TENSOR or Granularity.PER_CHANNEL.
            ch_axis: Target dimension for per-channel quantization.
            narrow_range: If True, uses [-127, 127] instead of [-128, 127] for signed 8-bit.
        """
        if bit_width < 2 or bit_width > 16:
            raise ValueError(f"Unsupported bit_width: {bit_width}. Must be in [2, 16].")

        self.bit_width = bit_width
        self.mode = mode
        self.granularity = granularity
        self.ch_axis = ch_axis
        self.narrow_range = narrow_range

        self.qmin, self.qmax = self._derive_integer_bounds()

    def _derive_integer_bounds(self) -> Tuple[int, int]:
        """Calculates theoretical clipping limits based on bit-width and schema."""
        if self.mode == QuantMode.ASYMMETRIC:
            # Unsigned range: [0, 2^b - 1]
            return 0, (1 << self.bit_width) - 1
        else:
            # Signed range: [-2^{b-1}, 2^{b-1} - 1]
            qmax = (1 << (self.bit_width - 1)) - 1
            qmin = -qmax if self.narrow_range else -(1 << (self.bit_width - 1))
            return qmin, qmax

    def calculate_qparams(self, tensor: torch.Tensor) -> QuantizationParameters:
        """
        Derives scale and zero-point parameters from the input tensor distribution.
        
        Args:
            tensor: Input floating-point tensor (FP32, FP16, or BF16).
            
        Returns:
            QuantizationParameters containing verified scales and zero-points.
        """
        if tensor.numel() == 0:
            raise ValueError("Input tensor is empty. Cannot calibrate empty distribution.")

        with torch.no_grad():
            if self.granularity == Granularity.PER_TENSOR:
                min_val = torch.min(tensor)
                max_val = torch.max(tensor)
            elif self.granularity == Granularity.PER_CHANNEL:
                # Build dimension reduction tuple excluding the channel axis
                dims = [i for i in range(tensor.ndim) if i != self.ch_axis]
                min_val = torch.amin(tensor, dim=dims, keepdim=True)
                max_val = torch.amax(tensor, dim=dims, keepdim=True)
            else:
                raise NotImplementedError(f"Unsupported granularity: {self.granularity}")

            # Mitigate identical dynamic range limits (e.g., zero-initialized layers)
            min_val = torch.min(min_val, torch.zeros_like(min_val))
            max_val = torch.max(max_val, torch.zeros_like(max_val))
            max_val = torch.maximum(max_val, min_val + self.EPSILON)

            if self.mode == QuantMode.SYMMETRIC:
                max_abs = torch.maximum(torch.abs(min_val), torch.abs(max_val))
                scale = max_abs / float(self.qmax)
                # Safeguard against scale underflow to avoid Division-by-Zero
                scale = torch.clamp(scale, min=self.EPSILON)
                zero_point = torch.zeros_like(scale, dtype=torch.int32)
            else:
                scale = (max_val - min_val) / float(self.qmax - self.qmin)
                scale = torch.clamp(scale, min=self.EPSILON)
                zero_point_unrounded = self.qmin - (min_val / scale)
                zero_point = torch.round(zero_point_unrounded).to(torch.int32)
                zero_point = torch.clamp(zero_point, self.qmin, self.qmax)

        return QuantizationParameters(
            scale=scale,
            zero_point=zero_point,
            bit_width=self.bit_width,
            qmin=self.qmin,
            qmax=self.qmax,
            mode=self.mode,
            granularity=self.granularity,
            ch_axis=self.ch_axis,
        )

    def quantize(
        self, tensor: torch.Tensor, qparams: Optional[QuantizationParameters] = None
    ) -> Tuple[torch.Tensor, QuantizationParameters]:
        """
        Quantizes floating-point tensor to target integer domain.

        Args:
            tensor: Target input tensor.
            qparams: Pre-computed QuantizationParameters (optional, computed if None).

        Returns:
            Tuple of quantized integer tensor and the used parameters.
        """
        if qparams is None:
            qparams = self.calculate_qparams(tensor)

        # Broadcast safety check
        if self.granularity == Granularity.PER_CHANNEL and qparams.scale.ndim != tensor.ndim:
            raise ValueError(
                f"Scale shape {qparams.scale.shape} does not match tensor dimensionality {tensor.shape}"
            )

        with torch.no_grad():
            # Domain mapping: (X / S) + Z
            scaled_tensor = tensor / qparams.scale
            if self.mode == QuantMode.ASYMMETRIC:
                scaled_tensor = scaled_tensor + qparams.zero_point.to(tensor.dtype)

            # Round to nearest even and clamp to analytical bit boundaries
            quantized = torch.clamp(
                torch.round(scaled_tensor),
                min=qparams.qmin,
                max=qparams.qmax,
            )

            # Cast to the storage integer format
            if self.bit_width <= 8:
                dtype = torch.int8 if self.mode == QuantMode.SYMMETRIC else torch.uint8
            elif self.bit_width <= 16:
                dtype = torch.int16
            else:
                dtype = torch.int32

            return quantized.to(dtype), qparams

    def dequantize(
        self, quantized_tensor: torch.Tensor, qparams: QuantizationParameters
    ) -> torch.Tensor:
        """
        Reconstructs floating-point tensor approximation from quantized integer data.

        Formula:
            Symmetric:  X_hat = q * S
            Asymmetric: X_hat = (q - Z) * S
        """
        with torch.no_grad():
            dequant_data = quantized_tensor.to(qparams.scale.dtype)
            if qparams.mode == QuantMode.ASYMMETRIC:
                dequant_data = dequant_data - qparams.zero_point.to(qparams.scale.dtype)
            return dequant_data * qparams.scale


# =====================================================================
# Unit Validation and Numerical Divergence Metric Verification
# =====================================================================
def compute_snr(original: torch.Tensor, reconstructed: torch.Tensor) -> float:
    """Computes Signal-to-Quantization-Noise Ratio (SQNR) in decibels (dB)."""
    signal_power = torch.sum(torch.square(original))
    noise_power = torch.sum(torch.square(original - reconstructed))
    if noise_power == 0.0:
        return float("inf")
    return float(10 * torch.log10(signal_power / noise_power))


if __name__ == "__main__":
    # Test Data Setup: Realistic Gaussian distribution with channel outliers
    torch.manual_seed(42)
    sample_tensor = torch.randn(size=(4, 8), dtype=torch.float32)
    # Inject heavy outlier in Channel 2
    sample_tensor[2, :] *= 15.0

    print("=== Original Tensor Sample (Ch 0 & Ch 2) ===")
    print("Channel 0:", sample_tensor[0, :3])
    print("Channel 2 (Outlier):", sample_tensor[2, :3])

    # 1. Asymmetric Per-Tensor INT8
    asym_engine = UniformQuantizer(
        bit_width=8,
        mode=QuantMode.ASYMMETRIC,
        granularity=Granularity.PER_TENSOR,
    )
    q_asym, p_asym = asym_engine.quantize(sample_tensor)
    dq_asym = asym_engine.dequantize(q_asym, p_asym)
    snr_asym = compute_snr(sample_tensor, dq_asym)

    # 2. Symmetric Per-Channel INT8
    sym_pc_engine = UniformQuantizer(
        bit_width=8,
        mode=QuantMode.SYMMETRIC,
        granularity=Granularity.PER_CHANNEL,
        ch_axis=0,
    )
    q_sym_pc, p_sym_pc = sym_pc_engine.quantize(sample_tensor)
    dq_sym_pc = sym_pc_engine.dequantize(q_sym_pc, p_sym_pc)
    snr_sym_pc = compute_snr(sample_tensor, dq_sym_pc)

    print("\n=== Quantization Diagnostics ===")
    print(f"[Asymmetric Per-Tensor] Scale: {p_asym.scale.item():.6f}, ZP: {p_asym.zero_point.item()}")
    print(f"  -> Reconstructed SQNR: {snr_asym:.2f} dB")
    print(f"  -> Quant Error L2 Norm: {torch.norm(sample_tensor - dq_asym).item():.4f}")

    print(f"\n[Symmetric Per-Channel] Scale Shape: {p_sym_pc.scale.shape}")
    print(f"  -> Channel 0 Scale: {p_sym_pc.scale[0].item():.6f}")
    print(f"  -> Channel 2 Scale: {p_sym_pc.scale[2].item():.6f}")
    print(f"  -> Reconstructed SQNR: {snr_sym_pc:.2f} dB")
    print(f"  -> Quant Error L2 Norm: {torch.norm(sample_tensor - dq_sym_pc).item():.4f}")

    # Validasi asserts invariant matematika
    assert snr_sym_pc > snr_asym, "Per-channel should significantly outperform per-tensor under outlier stress."
    assert q_sym_pc.dtype == torch.int8, "Symmetric quant must yield torch.int8 storage."
    assert q_asym.dtype == torch.uint8, "Asymmetric quant must yield torch.uint8 storage."
    print("\nNumerical tests passed successfully.")
```

---

### 7. Edge Cases & Failure Modes

Dalam lingkungan produksi inferensi berkecepatan tinggi, kegagalan kuantisasi sering terjadi akibat karakteristik matematis berikut:

| Failure Mode | Mekanisme Penyebab | Dampak pada Sistem Inferensi | Strategi Mitigasi / Fallback |
| :--- | :--- | :--- | :--- |
| **Zero Dynamic Range ($x_{\max} = x_{\min}$)** | Tensor berisi nilai seragam (misal: tensor berisi seluruhnya $0.0$ akibat aktivasi mati/dead neurons). | Skala $S \to 0$, memicu `DivisionByZero` ($NaN$ / $\text{Inf}$) saat inferensi downstream. | Injeksi konstanta pembatas $\epsilon = 10^{-8}$ ke kalkulasi penyebut; jika range mutlak $< \epsilon$, paksa $S = 1.0, Z = 0$. |
| **Outlier Domination** | Token aktivasi terisolasi memiliki magnitudo $> 100\times$ dibanding token lain (fenomena alami Transformer $>6.7\text{B}$). | Resolusi kisi grid terkuantisasi terkorupsi: $99.9\%$ representasi data terkompresi ke dalam 1 atau 2 bin integer saja. | Implementasi *percentile clipping* (misal $99.99\%$), per-token scaling dinamis, atau faktorisasi *SmoothQuant/AWQ*. |
| **Scale Underflow / Overflow** | Mengkuantisasi tensor dengan floating-point ultra-kecil ($< 10^{-38}$ pada FP32) atau mendekati limit FP16. | Nilai skala $S$ meluruh menjadi $0.0$ atau denormalized floats, memicu degradasi kernel throughput hingga $100\times$. | Validasi dan *clamp* $S$ ke jangkauan representasi minimum hardware target (misal `torch.finfo(torch.float16).tiny`). |
| **Integer Truncation Bias** | Round-to-zero alih-alih round-to-nearest-even ($q = \text{int}(x)$). | Terakumulasinya bias galat non-nol yang membelokkan mean distribusi representasi secara bertahap antar-layer. | Gunakan standar IEEE-754 convergent rounding (`torch.round()`). |

---

### 8. Trade-offs & Alternatif Solusi

| Dimensi Arsitektural | INT8 Symmetric (Per-Channel) | INT8 Asymmetric (Per-Tensor) | FP8 (E4M3 OCP Standard) | INT4 Group-wise (Group size: 128) |
| :--- | :--- | :--- | :--- | :--- |
| **Throughput Latency** | **Maksimum**: Zero cross-term GEMM overhead; kompatibel penuh dengan Tensor Core DP4A / INT8 MMA. | **Moderat**: Membutuhkan koreksi akumulasi run-time untuk $Z_X \sum W$. | **Sangat Tinggi**: Komputasi native pada arsitektur GPU Hopper/Ada Lovelace tanpa zero-point. | **Memori-Optimal**: Decode bound throughput meningkat drastis, latensi GEMM dibatasi oleh unpack kernel overhead. |
| **Kompleksitas Metadata** | Rendah: Array 1D skala per baris/kolom ($O(C)$ metadata overhead). | Minimum: Skala tunggal dan integer offset tunggal ($O(1)$ overhead). | Minimum: Vektor skala tensor/channel tunggal ($O(1)$ atau $O(C)$). | Tinggi: Parameter skala dan zero-point disimpan per 128 bobot ($O(N \cdot K / 128)$). |
| **Retensi Akurasi Model** | Sangat Tinggi: Variasi antar channel tertangani secara independen. | Rendah ke Moderat: Sering terjadi degradasi perplexity signifikan pada Transformer. | Tinggi: Dynamic range eksponensial lebih mampu mentoleransi outlier distribusi. | Moderat ke Rendah: Memerlukan optimasi *weight-clipping* canggih (AWQ/GPTQ) untuk menjaga akurasi task. |
| **Memory Footprint Bobot** | $1.0\times$ baseline INT8 ($1\text{ Byte/param}$). | $1.0\times$ baseline INT8 ($1\text{ Byte/param}$). | $1.0\times$ baseline FP8 ($1\text{ Byte/param}$). | $\approx 0.55\times$ baseline INT8 ($0.5\text{ Byte/param}$ + metadata overhead). |

---

### 9. Best Practices & Standard Industri

1. **Skema Bobot vs Aktivasi**:
   - **Weights**: Gunakan **Symmetric Per-Channel (INT8)** atau **Symmetric Group-wise (INT4, G=128)**. Hal ini meniadakan kebutuhan penanganan zero-point pada interior loop kernel hardware.
   - **Activations**: Gunakan **Asymmetric Per-Tensor (INT8)** jika menggunakan static calibration, atau beralih ke **Dynamic Per-Token Symmetric Quantization** untuk memitigasi outlier inter-token tanpa kalibrasi eksternal.
2. **Representasi Asimetris Hardware-Level**:
   Jika hardware target (misalnya beberapa embedded DSP/NPU) memaksakan aktivasi UINT8 dan bobot INT8, transformasi linear:
   $$W_{\text{shifted}} = W + 128$$
   dapat digunakan untuk memanfaatkan akselerator khusus *unsigned-by-unsigned dot-products*, namun harus dikompensasi kembali di tahap epilogue output layer.
3. **Ukuran Dataset Kalibrasi (Post-Training Quantization - PTQ)**:
   - Gunakan 128 hingga 512 sekuens representatif dari domain inferensi nyata.
   - Menggunakan dataset umum sintetis (seperti purely random Gaussian) untuk kalibrasi Min/Max menyebabkan degradasi parah pada representasi *activation distribution tails*.

---

### 10. Hands-on Lab Exercise

#### Skenario Kasus
Sebagai Principal Inference Engineer, Anda ditugaskan membangun pipeline kalibrasi dan kuantisasi untuk layer Linear proyeksi proyek LLM multi-head attention ($d_{\text{model}} = 4096, d_{\text{out}} = 4096$). Lapisan ini menunjukkan lonjakan aktivasi (*activation spikes*) terisolasi pada dimensi kanal tertentu yang merusak inferensi standar INT8.

#### Tugas Terstruktur
1. **Langkah 1**: Buat generator data sintetis yang memproduksi matriks aktivasi realistis yang disisipi outlier sporadis (10x-50x standard deviation).
2. **Langkah 2**: Terapkan dua strategi kuantisasi bobot:
   - Skema A: INT8 Symmetric Per-Tensor.
   - Skema B: INT8 Symmetric Per-Channel.
3. **Langkah 3**: Simulasikan eksekusi Linear Projection ($Y = XW$).
4. **Langkah 4**: Evaluasi degradasi model dengan mengukur Mean Absolute Error (MAE) dan Signal-to-Quantization-Noise Ratio (SQNR) antara output referensi (FP32 murni) dan output terkuantisasi (Dequantized Output).

#### Solusi Panduan Lab

```python
import torch
import torch.nn.functional as F

# Step 1: Generate synthetic activation & weights with distribution outliers
torch.manual_seed(1337)
batch_size, seq_len, d_in, d_out = 2, 128, 4096, 4096

# Normal activations with 0.1% activation outlier spikes
X = torch.randn(batch_size, seq_len, d_in, dtype=torch.float32)
outlier_mask = torch.rand_like(X) < 0.001
X[outlier_mask] *= 35.0

# Layer weights with channel-dependent variance
W = torch.randn(d_out, d_in, dtype=torch.float32)
channel_scales = torch.linspace(0.1, 5.0, steps=d_out).unsqueeze(1)
W = W * channel_scales

# Reference Forward Pass in FP32
X_flat = X.view(-1, d_in)
Y_ref = F.linear(X_flat, W)

print("Starting Quantization Verification Lab...")
print(f"Activation Max: {X.abs().max():.2f}, Weight Max: {W.abs().max():.2f}")

# Step 2: Implement Quantization Functions for Weights
# Skema A: Per-Tensor Symmetric
scale_w_tensor = W.abs().max() / 127.0
W_q_tensor = torch.clamp(torch.round(W / scale_w_tensor), -127, 127).to(torch.int8)

# Skema B: Per-Channel Symmetric (Axis 0: Output Channel)
scale_w_channel = W.abs().amax(dim=1, keepdim=True) / 127.0
scale_w_channel = torch.clamp(scale_w_channel, min=1e-8)
W_q_channel = torch.clamp(torch.round(W / scale_w_channel), -127, 127).to(torch.int8)

# Step 3: Dequantize and Compute Forward Passes
W_dq_tensor = W_q_tensor.to(torch.float32) * scale_w_tensor
W_dq_channel = W_q_channel.to(torch.float32) * scale_w_channel

Y_hat_tensor = F.linear(X_flat, W_dq_tensor)
Y_hat_channel = F.linear(X_flat, W_dq_channel)

# Step 4: Metric Calculation
def evaluate_metrics(name: str, y_true: torch.Tensor, y_pred: torch.Tensor):
    mae = torch.mean(torch.abs(y_true - y_pred)).item()
    sqnr = compute_snr(y_true, y_pred)
    print(f"[{name}]")
    print(f"  MAE  : {mae:.6f}")
    print(f"  SQNR : {sqnr:.2f} dB")

evaluate_metrics("Scheme A: Per-Tensor Weights", Y_ref, Y_hat_tensor)
evaluate_metrics("Scheme B: Per-Channel Weights", Y_ref, Y_hat_channel)

# Verify architectural assertion
mae_a = torch.mean(torch.abs(Y_ref - Y_hat_tensor)).item()
mae_b = torch.mean(torch.abs(Y_ref - Y_hat_channel)).item()
assert mae_b < mae_a, "Per-Channel quantization must exhibit superior precision under channel variance."
print("\nLab completed: Per-Channel verified as required architecture for non-uniform linear projections.")
```