# Bab 06: Deep Learning Foundations & Optimization Dynamics
## Module 01: Computational Graphs, Automatic Differentiation (Autograd), & Loss Topography

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Menganalisis dan Membangun Dynamic Directed Acyclic Graphs (DAG)** untuk representasi komputasi tensor forward dan backward passes.
2. **Menurunkan Formulasi Matematis Vector-Jacobian Products (VJP)** pada operasi tensor berdimensi tinggi dan membuktikan mengapa reverse-mode automatic differentiation memiliki kompleksitas $O(1)$ relatif terhadap dimensi parameter loss skalar.
3. **Mendiagnosis Patologi Optimasi Non-Konveks**—seperti *ill-conditioned Hessian manifolds*, *saddle points*, dan fenomena *vanishing/exploding gradients*—menggunakan analisis spektral nilai eigen (*eigenvalue spectrum*) dan metrik *Frobenius norm*.
4. **Mengimplementasikan Custom Autograd Operations dan Production-Grade Optimizer (Decoupled AdamW)** dari nol dengan kontrol numerik defensif, penanganan underflow/overflow, dan *gradient clipping*.
5. **Menerapkan Metodologi Health Check Gradien pada Skala Enterprise** untuk mendeteksi divergensi pelatihan secara *real-time* sebelum terjadi degradasi model atau pemborosan sumber daya komputasi.

---

### 2. Concept Overview

Deep Learning pada skala enterprise bukan sekadar tumpukan layer abstraksi tinggi; ia adalah sistem komputasi terdistribusi yang mengeksekusi optimasi non-linear pada manifold berdimensi miliaran. Dua pilar fundamental yang memungkinkan skala ini adalah **Automatic Differentiation (Autograd)** dan **Geometric Loss Landscape Dynamics**.

#### Mental Model: Computational Graph & Adjoint State
Pandang setiap neural network sebagai *Directed Acyclic Graph* (DAG) $\mathcal{G} = (\mathcal{V}, \mathcal{E})$, di mana node $\mathcal{V}$ merepresentasikan tensor (state) atau operasi diferensiabel (primitif fungsional), dan edge $\mathcal{E}$ merepresentasikan aliran dependensi data.

```
       [Forward Pass: Evaluasi Data & Penyiapan Konteks]
   x ───> [ Linear Wx + b ] ───> h ───> [ Non-Linearity σ ] ───> y_pred ───> [ Loss L ]
              │                           │                              │
              ▼                           ▼                              ▼
          Cache: x                    Cache: h                       Cache: y_true
              │                           │                              │
              ▼                           ▼                              ▼
   ∂L/∂x <── [ VJP: W^T @ dL/dh ] <── ∂L/∂h <── [ VJP: σ' * dL/dy ] <─── ∂L/∂y_pred <─── 1.0
       [Backward Pass: Propagasi Adjoint State via Reverse-Mode Autograd]
```

Dalam komputasi numerik, diferensiasi dapat dilakukan via:
1. **Numerical Differentiation (Finite Differences):** Menghitung $\frac{f(x + \epsilon) - f(x)}{\epsilon}$. Membutuhkan $O(N)$ forward passes untuk $N$ parameter. Tidak praktis untuk $N = 10^7 - 10^{11}$.
2. **Symbolic Differentiation:** Menghasilkan ekspresi aljabar analitik eksak. Mengalami masalah *expression swell* eksponensial pada graf komputasi dalam.
3. **Automatic Differentiation (Autograd):** Menerapkan aturan rantai (*chain rule*) secara rekursif pada level eksekusi kode biner primitif. Dibagi menjadi:
   - **Forward-mode (Jacobian-Vector Products / JVP):** Efisien jika $f: \mathbb{R}^1 \to \mathbb{R}^M$ (sedikit input, banyak output).
   - **Reverse-mode (Vector-Jacobian Products / VJP):** Efisien jika $\mathcal{L}: \mathbb{R}^N \to \mathbb{R}^1$ (banyak input/parameter, satu skalar loss). Ini adalah fondasi mutlak dari Deep Learning modern: menghitung gradien semua parameter $N$ hanya dalam satu kali backward pass dengan biaya komputasi $\sim 2-3\times$ forward pass.

#### Topografi Loss Manifold & Kondisi Hessian
Ruang bobot (*weight space*) $\Theta \in \mathbb{R}^N$ mendefinisikan permukaan loss non-konveks $\mathcal{L}(\Theta)$. Perilaku optimasi lokal diatur oleh ekspansi deret Taylor orde kedua:

$$\mathcal{L}(\Theta + \Delta\Theta) \approx \mathcal{L}(\Theta) + \nabla \mathcal{L}(\Theta)^T \Delta\Theta + \frac{1}{2} \Delta\Theta^T H \Delta\Theta$$

Di mana:
- $\nabla \mathcal{L}(\Theta) \in \mathbb{R}^N$ adalah vektor gradien (orde pertama: menentukan arah kemiringan).
- $H = \nabla^2 \mathcal{L}(\Theta) \in \mathbb{R}^{N \times N}$ adalah matriks Hessian (orde kedua: menentukan kelengkungan/*curvature*).

Karakteristik Hessian menentukan stabilitas optimasi:
- **Condition Number ($\kappa$):** Rasio eigenvalue maksimum terhadap minimum: $\kappa = \frac{\lambda_{\max}}{\lambda_{\min}}$.
- Jika $\kappa \gg 1$, loss landscape membentuk *ill-conditioned valley* (ravine sempit). First-order optimizer (seperti Vanilla SGD) akan berosilasi keras secara transversal dan bergerak sangat lambat di sepanjang dasar lembah.
- Titik stasioner ($\nabla \mathcal{L} = 0$) pada deep network hampir tidak pernah berupa *local minima*, melainkan *saddle points* dengan kombinasi eigenvalue Hessian positif dan negatif.

---

### 3. Why It Matters

Dalam implementasi skala besar (misalnya pre-training LLM, model rekomendasi real-time, atau autonomous perception), kelemahan pemahaman atas dinamika optimasi dan graph engine berdampak langsung pada kegagalan komersial dan infrastruktur:

1. **Silent Numerical Divergence:** Loss bernilai `NaN` atau `Inf` sering muncul tiba-tiba setelah ratusan jam komputasi cluster GPU karena luapan numerik (*numerical overflow*) pada Softmax, dekomposisi varians negatif pada Normalization layer, atau gradien yang meledak (*exploding gradient*).
2. **Financial Waste:** Melatih model berukuran puluhan miliar parameter pada cluster ribuan node membutuhkan biaya ratusan ribu dolar per eksekusi. Kegagalan optimasi akibat salah memilih learning rate schedule, momentum decay, atau ketidaktahuan atas geometri loss landscape menghasilkan pemborosan daya komputasi secara masif.
3. **Dead Weight Pathology:** Inisialisasi bobot yang tidak sesuai dengan fungsi aktivasi (misal, Xavier initialization dipasangkan dengan ReLU) menyebabkan *dead neuron crisis*, di mana separuh kapasitas graf komputasi berhenti memperbarui gradien sejak iterasi pertama ($f'(x) = 0$).

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut merepresentasikan aliran status komputasi dari forward graph construction, dynamic backward context caching, autograd propagation, hingga eksekusi state update oleh Optimizer.

```
+----------------------------------------------------------------------------------------------------+
|                                    FORWARD EXECUTION ENGINE                                        |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|    Tensor X (B, D_in) ──────┐                                                                      |
|                             ▼                                                                      |
|    Weight W (D_out, D_in) -> [ MatMul ] ──> Z (B, D_out) ──> [ LayerNorm ] ──> A (B, D_out)        |
|                                │                                  │                  │             |
|                                ▼                                  ▼                  ▼             |
|                         (Save for Bwd: X)                  (Save: mean, var)     (Save: A)         |
|                                                                                      │             |
|    Bias b (D_out) ───────────────────────────────────────────────────────────────────┼─┐           |
|                                                                                      │ │           |
|                                                                                      ▼ ▼           |
|    Target Y (B, 1) <────────────────────────── [ Cross-Entropy Loss ] <────────── [ GELU ]         |
|                                                          │                                         |
|                                                          ▼                                         |
|                                                    Scalar Loss L (1,)                              |
+----------------------------------------------------------┼-----------------------------------------+
                                                           │
                                                           │ Seed Backward: dL/dL = 1.0 (Adjoint)
                                                           ▼
+----------------------------------------------------------------------------------------------------+
|                                   AUTOGRAD ENGINE (BACKWARD GRAPH)                                 |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  [ VJP Cross-Entropy ] <── In: 1.0, Cache: Target, Act                                            |
|           │                                                                                        |
|           ▼ dL/dA                                                                                  |
|  [ VJP GELU ] <────────── In: dL/dA, Cache: Z_norm                                                 |
|           │                                                                                        |
|           ▼ dL/dZ_norm                                                                             |
|  [ VJP LayerNorm ] <───── In: dL/dZ_norm, Cache: mean, var, Z                                      |
|           │                                                                                        |
|           ├──────────────────────────────────────────┐                                             |
|           ▼ dL/dZ                                    ▼ dL/db (Accumulated via axis reduction)      |
|  [ VJP MatMul ]                                [ Grad Accumulator: b.grad += sum(dL/dZ, dim=0) ]  |
|     │        │                                                                                     |
|     │        └───────────────────────────────────────┐                                             |
|     ▼ dL/dX (propagated to prev layer)               ▼ dL/dW (Accumulated: W.grad += dL/dZ^T @ X)  |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
                                                       │
                                                       ▼ Read Gradients (W.grad, b.grad)
+----------------------------------------------------------------------------------------------------+
|                                  OPTIMIZATION & DYNAMICS SUBSYSTEM                                 |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  1. Global Gradient Norm Calculation: ||G||_2 = sqrt( sum( ||g_i||_2^2 ) )                        |
|  2. Gradient Clipping: If ||G||_2 > threshold -> g_i = g_i * (threshold / ||G||_2)                |
|  3. AdamW State Update:                                                                            |
|       - 1st Moment EMA: m_t = beta_1 * m_{t-1} + (1 - beta_1) * g_t                                |
|       - 2nd Moment EMA: v_t = beta_2 * v_{t-1} + (1 - beta_2) * g_t^2                              |
|       - Bias Correction: m_hat = m_t / (1 - beta_1^t), v_hat = v_t / (1 - beta_2^t)                |
|       - Decoupled Decay: W_t = W_{t-1} - lr * lambda_wd * W_{t-1}                                  |
|       - Step Update:     W_t = W_t - lr * (m_hat / (sqrt(v_hat) + eps))                            |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### 5.1 Formalisasi Matematika: Reverse-Mode Autodiff (VJP)
Misalkan graf komputasi tersusun dari serangkaian transformasi vektor $\mathbf{x}_{i+1} = f_i(\mathbf{x}_i)$, dengan $\mathbf{x}_0$ adalah input dan $\mathcal{L} = \mathbf{x}_K$ adalah skalar output akhir.

Jacobian dari fungsi $f_i$ adalah matriks turunan parsial:

$$J_i = \frac{\partial \mathbf{x}_{i+1}}{\partial \mathbf{x}_i} \in \mathbb{R}^{M \times N}$$

Untuk menghitung turunan skalar $\mathcal{L}$ terhadap sembarang node internal $\mathbf{x}_i$, aturan rantai menyatakan:

$$\frac{\partial \mathcal{L}}{\partial \mathbf{x}_i} = \frac{\partial \mathcal{L}}{\partial \mathbf{x}_{i+1}} \frac{\partial \mathbf{x}_{i+1}}{\partial \mathbf{x}_i} = \left(\frac{\partial \mathcal{L}}{\partial \mathbf{x}_{i+1}}\right) J_i$$

Notasikan adjoint vector $\overline{\mathbf{x}}_i \equiv \frac{\partial \mathcal{L}}{\partial \mathbf{x}_i}^T \in \mathbb{R}^N$. Maka komputasi backward dari state $i+1$ ke state $i$ adalah:

$$\overline{\mathbf{x}}_i = J_i^T \overline{\mathbf{x}}_{i+1}$$

Operasi $J_i^T \mathbf{v}$ ini adalah **Vector-Jacobian Product (VJP)**. Pada implementasi aktual, matriks Jacobian $J_i$ penuh **tidak pernah dibentuk eksplisit di memori**, karena ukuran $M \times N$ dapat mencapai kuadriliun elemen. Sebagai gantinya, VJP dihitung sebagai fungsi analitik langsung.

Contoh untuk Matrix Multiplication $\mathbf{Y} = \mathbf{X}\mathbf{W}$:
- $\mathbf{X} \in \mathbb{R}^{B \times D_{in}}$
- $\mathbf{W} \in \mathbb{R}^{D_{in} \times D_{out}}$
- $\mathbf{Y} \in \mathbb{R}^{B \times D_{out}}$
- Diberikan incoming gradient $\overline{\mathbf{Y}} = \frac{\partial \mathcal{L}}{\partial \mathbf{Y}} \in \mathbb{R}^{B \times D_{out}}$

VJP diturunkan melalui diferensial matriks:
$$d\mathcal{L} = \text{Tr}(\overline{\mathbf{Y}}^T d\mathbf{Y}) = \text{Tr}(\overline{\mathbf{Y}}^T (d\mathbf{X} \mathbf{W} + \mathbf{X} d\mathbf{W}))$$
Menggunakan sifat jejak matriks $\text{Tr}(A B) = \text{Tr}(B A)$:
$$d\mathcal{L} = \text{Tr}(\mathbf{W} \overline{\mathbf{Y}}^T d\mathbf{X}) + \text{Tr}(\overline{\mathbf{Y}}^T \mathbf{X} d\mathbf{W}) = \text{Tr}((\overline{\mathbf{Y}} \mathbf{W}^T)^T d\mathbf{X}) + \text{Tr}((\mathbf{X}^T \overline{\mathbf{Y}})^T d\mathbf{W})$$

Sehingga VJP analitiknya adalah:
$$\overline{\mathbf{X}} = \frac{\partial \mathcal{L}}{\partial \mathbf{X}} = \overline{\mathbf{Y}} \mathbf{W}^T, \quad \overline{\mathbf{W}} = \frac{\partial \mathcal{L}}{\partial \mathbf{W}} = \mathbf{X}^T \overline{\mathbf{Y}}$$

#### 5.2 Geometri Hessian & Optimasi Orde Pertama
Pertimbangkan dinamika Gradient Descent pada fungsi kuadratik murni (aproksimasi lokal Taylor di sekitar minimum lokal $\Theta^*$):

$$\mathcal{L}(\Theta) = \frac{1}{2} (\Theta - \Theta^*)^T H (\Theta - \Theta^*)$$

Update rule gradient descent dengan learning rate $\eta$:

$$\Theta_{t+1} = \Theta_t - \eta H (\Theta_t - \Theta^*)$$
$$\Theta_{t+1} - \Theta^* = (I - \eta H)(\Theta_t - \Theta^*)$$

Transformasikan ke basis ortonormal dari eigenvector $H$ ($H = Q \Lambda Q^T$, dengan $\Lambda = \text{diag}(\lambda_1, \dots, \lambda_N)$). Untuk koordinat ke-$i$:

$$u_i^{(t+1)} = (1 - \eta \lambda_i) u_i^{(t)}$$

Agar sistem konvergen ($u_i^{(t)} \to 0$ saat $t \to \infty$):
$$|1 - \eta \lambda_i| < 1 \implies 0 < \eta < \frac{2}{\lambda_{\max}}$$

Kecepatan konvergensi dibatasi oleh komponen eigenvector paling lambat:
$$|1 - \eta \lambda_{\min}|$$
Untuk meminimalkan laju konvergensi absolut terburuk, pilih $\eta^* = \frac{2}{\lambda_{\max} + \lambda_{\min}}$, sehingga rasio kontraksi konvergensinya:

$$\rho = \frac{\lambda_{\max} - \lambda_{\min}}{\lambda_{\max} + \lambda_{\min}} = \frac{\kappa - 1}{\kappa + 1}$$

Jika $\kappa = \frac{\lambda_{\max}}{\lambda_{\min}} = 10^4$ (sangat lazim pada Deep Networks), maka $\rho \approx 1 - 2 \times 10^{-4}$. Konvergensi membutuhkan puluhan ribu step hanya untuk menutup jarak Euclidean sederhana.

#### 5.3 Dekonstruksi AdamW (Decoupled Weight Decay)
Masalah implementasi Adam standar (Kingma & Ba) adalah interaksi buruk antara $L_2$ regularization dan adaptive step size:

Pada $L_2$ regularization konvensional, loss yang diminimalkan adalah $\mathcal{L}_{reg}(\Theta) = \mathcal{L}(\Theta) + \frac{\lambda}{2} \|\Theta\|_2^2$.
Gradien yang masuk ke akumulator Adam:
$$g_t = \nabla \mathcal{L}(\Theta) + \lambda \Theta$$
Ketika $g_t$ diakumulasikan ke dalam second moment estimate:
$$v_t = \beta_2 v_{t-1} + (1 - \beta_2) g_t^2$$
Parameter dengan gradien historis besar akan membagi gradien penalti bobot $\lambda \Theta$ dengan $\sqrt{v_t} + \epsilon$. Parameter tersebut mengalami penalti regularisasi yang jauh lebih kecil daripada parameter dengan gradien jarang (*sparse gradients*).

**Solusi AdamW (Loshchilov & Hutter):** Dekopel regularisasi dari update momen gradien adaptif:
$$\Theta_t \leftarrow \Theta_{t-1} - \eta \lambda \Theta_{t-1} - \eta \frac{\widehat{m}_t}{\sqrt{\widehat{v}_t} + \epsilon}$$
Ini memastikan laju penyusutan bobot (*rate of weight decay*) bersifat proporsional terhadap bobot itu sendiri tanpa dipengaruhi oleh varians gradien lokal.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi clean-architecture dari custom Autograd primitive (`Linear` dengan VJP numerik stabil) dan custom enterprise-grade optimizer (`DecoupledAdamW`) yang dilengkapi *global norm clipping* dan *defensive tensor assertion*.

```python
"""
Module: core_optimization_engine.py
Deskripsi: Production-grade implementation of explicit autograd operations
           and Decoupled AdamW optimizer with defensive checks.
"""

from __future__ import annotations
import math
from typing import Dict, List, Optional, Tuple
import torch
from torch.autograd import Function


class StableLinearFunction(Function):
    """
    Implementasi eksplisit dari Vector-Jacobian Product (VJP)
    untuk operasi proyeksi linier Y = XW^T + b.
    Menerapkan defensive memory management dan validasi dimensional.
    """

    @staticmethod
    def forward(
        ctx,
        x: torch.Tensor,
        weight: torch.Tensor,
        bias: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """
        Forward pass proyeksi linier.
        
        Args:
            ctx: Context object PyTorch untuk menyimpan state autograd.
            x: Input tensor berukuran (..., D_in).
            weight: Weight matrix berukuran (D_out, D_in).
            bias: Optional bias vector berukuran (D_out,).
            
        Returns:
            Output tensor berukuran (..., D_out).
        """
        if x.dim() < 2:
            raise ValueError(f"Dimensi x minimal bernilai 2, diterima: {x.dim()}")
        if weight.dim() != 2:
            raise ValueError(f"Weight harus berupa 2D matrix, diterima: {weight.dim()}")
        if x.size(-1) != weight.size(1):
            raise ValueError(
                f"Mismatch dimensi: x last dim={x.size(-1)} vs weight in_features={weight.size(1)}"
            )

        # Simpan tensor yang dibutuhkan untuk kalkulasi VJP di backward pass
        ctx.save_for_backward(x, weight, bias)
        ctx.has_bias = bias is not None

        # Evaluasi komputasi forward
        output = torch.matmul(x, weight.t())
        if bias is not None:
            output += bias
        return output

    @staticmethod
    def backward(ctx, grad_output: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, Optional[torch.Tensor]]:
        """
        Backward pass: Menghitung Vector-Jacobian Products (VJP).
        
        Args:
            grad_output (dL/dY): Adjoint vector dari layer berikutnya.
            
        Returns:
            Tuple gradien (dL/dX, dL/dW, dL/db).
        """
        x, weight, bias = ctx.saved_tensors
        grad_x = grad_weight = grad_bias = None

        # Memastikan kekontiguan memori untuk kalkulasi BLAS optimal
        grad_output = grad_output.contiguous()

        # VJP untuk X: dL/dX = (dL/dY) @ W
        if ctx.needs_input_grad[0]:
            grad_x = torch.matmul(grad_output, weight)

        # Bentuk ulang X dan grad_output ke representasi 2D untuk menghitung dL/dW
        x_2d = x.reshape(-1, x.size(-1))
        grad_output_2d = grad_output.reshape(-1, grad_output.size(-1))

        # VJP untuk W: dL/dW = (dL/dY)^T @ X
        if ctx.needs_input_grad[1]:
            grad_weight = torch.matmul(grad_output_2d.t(), x_2d)

        # VJP untuk b: dL/db = sum_{batch}(dL/dY)
        if ctx.has_bias and ctx.needs_input_grad[2]:
            grad_bias = grad_output_2d.sum(dim=0)

        return grad_x, grad_weight, grad_bias


class EnterpriseLinear(torch.nn.Module):
    """
    Wrapper PyTorch Module yang mengintegrasikan StableLinearFunction
    dengan arsitektur inisialisasi bobot defensif.
    """

    def __init__(self, in_features: int, out_features: int, bias: bool = True) -> None:
        super().__init__()
        self.in_features = in_features
        self.out_features = out_features

        # Alokasi parameter memori contiguous
        self.weight = torch.nn.Parameter(torch.empty((out_features, in_features), dtype=torch.float32))
        if bias:
            self.bias = torch.nn.Parameter(torch.empty(out_features, dtype=torch.float32))
        else:
            self.register_parameter("bias", None)

        self._reset_parameters()

    def _reset_parameters(self) -> None:
        # Kaiming / He Initialization (Variance Preserving untuk Non-Linearities)
        torch.nn.init.kaiming_uniform_(self.weight, a=math.sqrt(5))
        if self.bias is not None:
            fan_in, _ = torch.nn.init._calculate_fan_in_and_fan_out(self.weight)
            bound = 1.0 / math.sqrt(fan_in) if fan_in > 0 else 0
            torch.nn.init.uniform_(self.bias, -bound, bound)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return StableLinearFunction.apply(x, self.weight, self.bias)


class ProductionAdamW:
    """
    Implementasi decoupled weight decay optimizer (AdamW) kelas enterprise
    dengan gradient health checks dan manual gradient clipping terintegrasi.
    """

    def __init__(
        self,
        params: List[torch.nn.Parameter],
        lr: float = 1e-3,
        betas: Tuple[float, float] = (0.9, 0.999),
        eps: float = 1e-8,
        weight_decay: float = 1e-2,
        max_grad_norm: Optional[float] = 1.0,
    ) -> None:
        if lr <= 0.0:
            raise ValueError(f"Learning rate tidak valid: {lr}")
        if eps <= 0.0:
            raise ValueError(f"Epsilon stability denominator tidak valid: {eps}")
        if not 0.0 <= betas[0] < 1.0 or not 0.0 <= betas[1] < 1.0:
            raise ValueError(f"Betas di luar range valid [0.0, 1.0): {betas}")
        if weight_decay < 0.0:
            raise ValueError(f"Weight decay tidak boleh bernilai negatif: {weight_decay}")

        self.params = [p for p in params if p.requires_grad]
        self.lr = lr
        self.beta1, self.beta2 = betas
        self.eps = eps
        self.weight_decay = weight_decay
        self.max_grad_norm = max_grad_norm

        # State register untuk tracking tracking momen per parameter
        self.state: Dict[torch.nn.Parameter, Dict[str, torch.Tensor | int]] = {}
        for p in self.params:
            self.state[p] = {
                "step": 0,
                "exp_avg": torch.zeros_like(p.data, memory_format=torch.preserve_format),
                "exp_avg_sq": torch.zeros_like(p.data, memory_format=torch.preserve_format),
            }

    def zero_grad(self) -> None:
        """Mereset gradien seluruh parameter ke None (hemat bandwidth memori GPU)."""
        for p in self.params:
            p.grad = None

    def _clip_global_gradient_norm(self) -> float:
        """
        Menghitung dan memangkas L2 norm gradien gabungan secara global.
        Returns:
            total_norm (float): L2 norm gabungan sebelum pemangkasan.
        """
        grads = [p.grad for p in self.params if p.grad is not None]
        if len(grads) == 0:
            return 0.0

        # Menghitung kuadrat L2 norm secara numerik aman
        total_norm_sq = 0.0
        for g in grads:
            grad_norm = g.data.norm(2)
            total_norm_sq += grad_norm.item() ** 2

        total_norm = math.sqrt(total_norm_sq)

        # Eksekusi clipping jika melewati threshold
        if self.max_grad_norm is not None and self.max_grad_norm > 0:
            clip_coef = self.max_grad_norm / (total_norm + 1e-6)
            if clip_coef < 1.0:
                for g in grads:
                    g.data.mul_(clip_coef)

        return total_norm

    @torch.no_grad()
    def step(self) -> Tuple[bool, float]:
        """
        Mengeksekusi satu iterasi update parameter.
        
        Returns:
            Tuple[bool, float]: (is_step_successful, global_gradient_norm).
        """
        # 1. Defensif Check: Identifikasi gradient availability
        active_grads = [p.grad for p in self.params if p.grad is not None]
        if not active_grads:
            return False, 0.0

        # 2. Periksa keberadaan nilai anomali (NaN atau Inf)
        for g in active_grads:
            if torch.isnan(g).any() or torch.isinf(g).any():
                # Gagalkan update jika terdeteksi divergensi numerik
                return False, float("nan")

        # 3. Eksekusi Global Gradient Clipping
        global_norm = self._clip_global_gradient_norm()

        # 4. Update Parameter via Decoupled Optimization
        for p in self.params:
            if p.grad is None:
                continue

            grad = p.grad.data
            param_state = self.state[p]

            # Inkrementasi step counter
            param_state["step"] += 1
            step = param_state["step"]

            exp_avg = param_state["exp_avg"]
            exp_avg_sq = param_state["exp_avg_sq"]

            # Decoupled Weight Decay: theta_t = theta_{t-1} - lr * lambda * theta_{t-1}
            if self.weight_decay != 0.0:
                p.data.mul_(1.0 - self.lr * self.weight_decay)

            # Update first raw moment (EMA): m_t = beta1 * m_{t-1} + (1 - beta1) * g_t
            exp_avg.mul_(self.beta1).add_(grad, alpha=1.0 - self.beta1)

            # Update second raw moment (EMA): v_t = beta2 * v_{t-1} + (1 - beta2) * g_t^2
            exp_avg_sq.mul_(self.beta2).addcmul_(grad, grad, value=1.0 - self.beta2)

            # Bias correction terms
            bias_correction1 = 1.0 - (self.beta1 ** step)
            bias_correction2 = 1.0 - (self.beta2 ** step)

            # Adaptive step size computation: lr * (m_hat / (sqrt(v_hat) + eps))
            step_size = self.lr / bias_correction1
            denom = (exp_avg_sq.sqrt() / math.sqrt(bias_correction2)).add_(self.eps)

            # Final parameter update step
            p.data.addcdiv_(exp_avg, denom, value=-step_size)

        return True, global_norm
```

---

### 7. Edge Cases & Failure Modes

#### 7.1 Vanishing and Exploding Gradients
* **Mekanisme Kegagalan:** Pada arsitektur $L$-layer dalam, adjoint gradient bernilai $\frac{\partial \mathcal{L}}{\partial \mathbf{x}_1} = \prod_{l=1}^{L} W_l^T \mathbf{x}_l'$. Jika *spectral radius* (eigenvalue terbesar) dari matriks $W_l$ secara konsisten $> 1.0$, gradien akan membesar secara eksponensial ($O(\lambda_{\max}^L)$), memicu overflow `Inf/NaN`. Sebaliknya, jika $< 1.0$, gradien meluruh menuju $0.0$ ($O(\lambda_{\min}^L)$), menghentikan pembaruan layer awal.
* **Strategi Mitigasi:**
  1. Terapkan residual connections ($x_{l+1} = x_l + f(x_l)$) sehingga $\frac{\partial \mathbf{x}_{l+1}}{\partial \mathbf{x}_l} = I + \frac{\partial f}{\partial \mathbf{x}_l}$, memecahkan vanishing gradients karena adanya identitas $I$.
  2. Implementasikan *Layer Normalization* atau *RMSNorm* untuk menstabilkan varians aktivasi dan magnitudo gradien per layer.

#### 7.2 Numerical Underflow pada Softmax-Cross-Entropy
* **Mekanisme Kegagalan:**
  $$P_i = \frac{e^{z_i}}{\sum_j e^{z_j}}$$
  Jika $z_i \ll 0$, $e^{z_i} \to 0$ (underflow). Jika $z_i \gg 0$, $e^{z_i} \to \infty$ (overflow). Ketika dihitung $-\log(P_i)$, kalkulasi numerik menghasilkan $-\log(0) = \infty \to \text{NaN}$.
* **Strategi Mitigasi (LogSumExp Trick):**
  Definisikan $c = \max_j(z_j)$. 
  $$\log \sum_j e^{z_j} = c + \log \sum_j e^{z_j - c}$$
  Kurangi vektor logit dengan elemen maksimumnya sebelum eksponensiasi di forward dan VJP.

#### 7.3 Dead Neurons pada Saturasinya Komputasi ReLU
* **Mekanisme Kegagalan:** Jika unit ReLU menerima input $z \le 0$ karena update gradien yang terlalu besar (*gradient kick*), aktivasi menjadi $0$ dan VJP lokal $f'(z) = 0$. Adjoint gradient yang melewati node ini akan terputus total. Parameter layer tersebut tidak akan pernah terupdate lagi secara permanen.
* **Strategi Mitigasi:** Gunakan fungsi aktivasi dengan gradien non-nol pada domain negatif seperti **LeakyReLU**, **ELU**, atau aktivasi kontinu mulus seperti **GELU** (*Gaussian Error Linear Unit*) dan **SwiGLU**.

---

### 8. Trade-offs & Alternatif Solusi

| Parameter / Algoritma | Pilihan A: SGD with Momentum | Pilihan B: AdamW | Pilihan C: Second-Order (L-BFGS) |
| :--- | :--- | :--- | :--- |
| **Kompleksitas Komputasi** | $O(N)$ waktu, $O(N)$ memori state | $O(N)$ waktu, $2 \times O(N)$ memori ekstra (momen 1 & 2) | $O(k \cdot N)$ waktu & memori ($k$: rank memori) |
| **Kondisi Landscape Buruk** | Terjebak/osilasi kuat pada ravine ber-kondisi Hessian tinggi | Menavigasi ravine secara efisien via adaptive coordinate scaling | Sangat cepat melintasi curvature berkat pendekatan invers Hessian |
| **Generalization Capability** | Cenderung menemukan flat minima yang lebih lebar (generalisasi empiris superior) | Cenderung menuju sharp minima jika regularisasi salah, namun dominan pada Transformers | Cenderung *overfit* pada noisy batch; gagal pada large-scale stochasticity |
| **Toleransi Skala Data** | Sangat baik untuk data masif & batching bervariasi | Menjadi standar de facto untuk Large Language Models & Vision | Sangat buruk pada stochastic mini-batching; optimal untuk full-batch deterministik |

---

### 9. Best Practices & Standard Industri

1. **Inisialisasi Bobot Sesuai Aktivasi (Variance Scaling Framework):**
   - **Xavier / Glorot Initialization** (untuk Sigmoid, Tanh): $\text{Var}(W) = \frac{2}{D_{\text{in}} + D_{\text{out}}}$
   - **He / Kaiming Initialization** (untuk ReLU, LeakyReLU): $\text{Var}(W) = \frac{2}{D_{\text{in}}}$
   - Mengabaikan aturan ini memicu *vanishing activation variance* pada layer akhir, mereduksi rasio signal-to-noise model.
2. **Defensive Gradient Health Watchdogs:** Monitor metrik gradien setiap $K$ step:
   - Hitung $\ell_2$-norm gradien parameter: $\|G\|_2$.
   - Monitor rasio update-to-weight: $\frac{\eta \cdot \|\Delta W\|_2}{\|W\|_2}$. Rasio ideal berkisar antara $10^{-4}$ hingga $10^{-2}$. Jika $< 10^{-6}$, model mengalami *learning stagnation*; jika $> 10^{-1}$, model mengalami *destabilizing updates*.
3. **Explicit FP32 Master Weights dalam Mixed Precision:** Ketika menggunakan FP16 atau BF16, selalu simpan salinan bobot dalam *Full Precision (FP32)* untuk akumulasi optimasi, guna mencegah hilangnya pembaharuan kecil akibat *precision truncation* ($\Delta \Theta < \text{smallest representable delta}$).

---

### 10. Hands-on Lab Exercise

#### Skenario Lab
Anda ditugaskan mendiagnosis dan merekayasa ulang stabilitas pelatihan model neural network kustom yang mengalami divergensi optimasi (loss meledak menuju `NaN` dan gradien tidak stabil) akibat *ill-conditioned features* dan ketiadaan stabilisasi autograd.

#### Langkah-langkah Implementasi

```python
"""
Lab Exercise: Optimization Dynamics & Gradient Stability Engine
Eksekusi script ini untuk melihat divergensi dan bagaimana mekanisme defensif menstabilkannya.
"""

import torch
import torch.nn as nn
from core_optimization_engine import EnterpriseLinear, ProductionAdamW


def synthesize_ill_conditioned_data(
    num_samples: int = 1000, in_features: int = 128, condition_number: float = 1e5
) -> Tuple[torch.Tensor, torch.Tensor]:
    """
    Menghasilkan synthetic dataset dengan matriks kovarians yang memiliki
    condition number ekstrem untuk menyimulasikan landscape optimasi patologis.
    """
    torch.manual_seed(42)
    # Generate random matrix
    X_raw = torch.randn(num_samples, in_features)

    # Lakukan SVD untuk mengontrol spektra eigenvalue secara eksklusif
    U, _, Vh = torch.linalg.svd(X_raw, full_matrices=False)
    
    # Skala singular values secara linier dari 1.0 ke (1.0 / condition_number)
    s = torch.linspace(1.0, 1.0 / condition_number, in_features)
    X = U @ torch.diag(s) @ Vh

    # Target fiktif dengan non-linear transform
    true_weights = torch.randn(in_features, 1)
    y = (X @ true_weights).sin() + 0.1 * torch.randn(num_samples, 1)

    return X.to(torch.float32), y.to(torch.float32)


class DeepPathologicalNetwork(nn.Module):
    """Deep network tanpa normalisasi layer untuk mengekspos instabilitas gradien."""

    def __init__(self, in_features: int, hidden_dim: int, depth: int = 6) -> None:
        super().__init__()
        layers = []
        layers.append(EnterpriseLinear(in_features, hidden_dim))
        layers.append(nn.ReLU())

        for _ in range(depth - 1):
            layers.append(EnterpriseLinear(hidden_dim, hidden_dim))
            layers.append(nn.ReLU())

        layers.append(EnterpriseLinear(hidden_dim, 1))
        self.network = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.network(x)


def run_experiment(use_clipping: bool, title: str) -> None:
    print(f"\n{'='*20} RUNNING: {title} {'='*20}")
    X, y = synthesize_ill_conditioned_data(num_samples=2048, in_features=64, condition_number=1e4)

    dataset = torch.utils.data.TensorDataset(X, y)
    dataloader = torch.utils.data.DataLoader(dataset, batch_size=64, shuffle=True)

    model = DeepPathologicalNetwork(in_features=64, hidden_dim=128, depth=5)
    
    # Konfigurasi clipping sesuai skenario
    max_clip = 1.0 if use_clipping else None
    optimizer = ProductionAdamW(
        params=list(model.parameters()),
        lr=0.005,
        weight_decay=0.01,
        max_grad_norm=max_clip
    )
    
    criterion = nn.MSELoss()

    for epoch in range(1, 6):
        epoch_loss = 0.0
        max_seen_grad_norm = 0.0
        step_diverged = False

        for batch_idx, (batch_x, batch_y) in enumerate(dataloader):
            optimizer.zero_grad()
            
            preds = model(batch_x)
            loss = criterion(preds, batch_y)

            if torch.isnan(loss) or torch.isinf(loss):
                print(f"[FATAL] Loss meledak ke NaN/Inf pada Epoch {epoch}, Batch {batch_idx}")
                step_diverged = True
                break

            loss.backward()

            success, grad_norm = optimizer.step()
            if not success:
                print(f"[WARNING] Step diverged / ditolak autograd engine pada Epoch {epoch}, Batch {batch_idx}")
                step_diverged = True
                break

            max_seen_grad_norm = max(max_seen_grad_norm, grad_norm)
            epoch_loss += loss.item()

        if step_diverged:
            print(f"Status Epoch {epoch}: FAILED (Divergensi Numerik)")
            break
        else:
            avg_loss = epoch_loss / len(dataloader)
            print(
                f"Epoch {epoch:02d} | Loss: {avg_loss:.4f} | "
                f"Max Grad Norm: {max_seen_grad_norm:.4f} | Health: OK"
            )


if __name__ == "__main__":
    # Test 1: Jalankan eksperimen tanpa defensive clipping pada ill-conditioned manifold
    run_experiment(use_clipping=False, title="Pathological Training (No Gradient Clipping)")

    # Test 2: Jalankan eksperimen dengan defensive clipping dan autograd stabil
    run_experiment(use_clipping=True, title="Hardened Training (With Defensive AdamW Clipping)")
```

#### Verifikasi Keberhasilan Lab:
1. **Unclipped Run:** Amati bagaimana nilai gradien norm melonjak secara tak terprediksi (sering kali mencapai $> 10^3$) dan berujung pada status `FATAL: Loss meledak ke NaN/Inf` atau stagnasi parah akibat rusaknya state momen kedua pada AdamW.
2. **Hardened Run:** Amati bagaimana `ProductionAdamW` secara konsisten menahan `Max Grad Norm` pada threshold $\le 1.0$, mempertahankan nilai skalar loss tetap menurun monotonically, dan menjaga matriks parameter terhindar dari racun nilai NaN.