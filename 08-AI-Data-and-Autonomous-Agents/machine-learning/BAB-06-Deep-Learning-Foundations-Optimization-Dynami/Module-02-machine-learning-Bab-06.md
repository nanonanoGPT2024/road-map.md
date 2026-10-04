# Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Kategori**: 08-AI-Data-and-Autonomous-Agents  
**Bab 06**: Deep Learning Foundations & Optimization Dynamics

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, Principal Machine Learning Engineer / AI Systems Architect diharapkan mampu:
- **Menganalisis dan Membedah Algoritma Reverse-Mode Automatic Differentiation**: Menguraikan representasi Directed Acyclic Graph (DAG) komputasi, jejak eksekusi (*tape-based autograd*), Jacobian-Vector Products (JVP), dan Vector-Jacobian Products (VJP) pada level engine C++/CUDA.
- **Mengimplementasikan Custom Autograd Primitives & Operators**: Membangun operator diferensiabel kustom dengan kontrol alokasi memori manual, forward/backward pass kustom, dan backward pass tingkat dua (Hessian-vector product).
- **Mendiagnosis dan Memitigasi Patologi Optimasi**: Menganalisis kondisi spektral Hessian ($\kappa = \lambda_{\max}/\lambda_{\min}$), fenomena *loss surface ill-conditioning*, *saddle point escapes*, serta gradien meledak (*exploding*) dan menghilang (*vanishing*).
- **Menguasai Mekanika Optimizer Modern**: Mengimplementasikan secara mandiri dari nol algoritma AdamW, LAMB, dan LARS dengan *decoupled weight decay*, kompensasi bias, serta koreksi *layer-wise adaptive moments*.
- **Merancang Arsitektur Training Loop Skala Produksi**: Membangun pipeline pelatihan berkinerja tinggi yang mengintegrasikan Automatic Mixed Precision (AMP FP16/BF16), Dynamic Gradient Scaling, Gradient Accumulation, Gradient Clipping by Global Norm, dan distributed synchronization hooks.

---

## 2. Prerequisites

Sebelum mempelajari modul ini, peserta wajib menguasai:
- **Linear Algebra & Vector Calculus**: Turunan parsial multivariat, matriks Jacobian, matriks Hessian, dekomposisi nilai eigen (*eigenvalue decomposition*), dan operasi tensor dimensi tinggi ($N \ge 4$).
- **Sistem Komputasi & Pemrograman CUDA Dasar**: Arsitektur memori GPU (SRAM vs HBM/VRAM), konsep kernel launch, streaming multiprocessor (SM), coalesced memory access, dan floating-point precision (IEEE 754: FP32, FP16, BF16).
- **Python & C++ Interoperability**: Memahami runtime Python C-API, PyTorch C++ extension (`torch::autograd::Function`), dan manajemen siklus hidup referensi memori (`std::shared_ptr`, intrusive pointers).

---

## 3. Concept & Internal Architecture (Deep Dive)

### 3.1 Reverse-Mode Automatic Differentiation & Computational Graph

Dalam deep learning modern, evaluasi gradien untuk fungsi objektif skalar $\mathcal{L}: \mathbb{R}^d \to \mathbb{R}$ dilakukan melalui *Reverse-Mode Automatic Differentiation* (Reverse Autodiff). Pendekatan ini memiliki kompleksitas komputasi $O(1)$ relatif terhadap evaluasi forward pass untuk menghasilkan gradien terhadap seluruh $d$ parameter, berbeda secara fundamental dengan *Forward-Mode Autodiff* yang berskala $O(d)$.

#### Dynamic Computational Graph (Tape-Based Execution)
PyTorch mengimplementasikan *tape-based dynamic computational graph*. Setiap kali operasi tensor dieksekusi selama forward pass:
1. Operator C++ mengalokasikan tensor output di VRAM.
2. Sebuah simpul `Node` (atau `GradFn`) dibuat di heap C++.
3. Simpul tersebut menyimpan pointer ke fungsi backward operator tersebut, referensi ke tensor yang diperlukan untuk evaluasi gradien (disimpan via `SavedVariable`), dan edge berarah ke `next_edges` (simpul komputasi dari tensor input).

```
[Forward Pass]
Input (x) ──> [Op: Linear] ──(z)──> [Op: ReLU] ──(a)──> [Op: CrossEntropy] ──> Loss (L)
                   │                     │                        │
                   ▼                     ▼                        ▼
                LinearBackward        ReLUBackward        CrossEntropyBackward
                   ▲                     ▲                        ▲
                   │                     │                        │
[Backward Pass]    └─────── dL/dz ◄──────┴──────── dL/da ◄────────┴────── dL/dL = 1.0
```

#### Vector-Jacobian Product (VJP)
Secara matematis, jika sebuah node merepresentasikan pemetaan multivariat $\mathbf{y} = f(\mathbf{x})$, di mana $\mathbf{x} \in \mathbb{R}^n$ dan $\mathbf{y} \in \mathbb{R}^m$, matriks Jacobian $J \in \mathbb{R}^{m \times n}$ didefinisikan sebagai:
$$J_{ij} = \frac{\partial y_i}{\partial x_j}$$

Menghitung dan menyimpan matriks $J$ secara eksplisit sangat tidak efisien (membutuhkan memori $O(mn)$). Reverse autodiff tidak pernah menghitung $J$ secara utuh. Engine komputasi hanya mengevaluasi *Vector-Jacobian Product* (VJP):
$$\mathbf{v}^T J = \sum_{i=1}^m v_i \frac{\partial y_i}{\partial \mathbf{x}}$$
di mana vektor $\mathbf{v} = \frac{\partial \mathcal{L}}{\partial \mathbf{y}} \in \mathbb{R}^m$ adalah gradien akumulasi dari layer di atasnya (*cotangent vector*).

### 3.2 Optimization Dynamics & Loss Surface Curvature

#### Kondisi Spektral Hessian & Ill-Conditioning
Permukaan fungsi loss $\mathcal{L}(\boldsymbol{\theta})$ di sekitar titik minimum lokal dapat didekati dengan ekspansi Taylor orde kedua:
$$\mathcal{L}(\boldsymbol{\theta} + \Delta \boldsymbol{\theta}) \approx \mathcal{L}(\boldsymbol{\theta}) + \nabla \mathcal{L}(\boldsymbol{\theta})^T \Delta \boldsymbol{\theta} + \frac{1}{2} \Delta \boldsymbol{\theta}^T H \Delta \boldsymbol{\theta}$$
di mana $H \in \mathbb{R}^{d \times d}$ adalah matriks Hessian dari turunan parsial kedua:
$$H_{ij} = \frac{\partial^2 \mathcal{L}}{\partial \theta_i \partial \theta_j}$$

Perilaku konvergensi optimizer turunan pertama (First-Order Optimizers seperti SGD) sangat dibatasi oleh rasio kondisi (*condition number*) $\kappa$ dari matriks Hessian:
$$\kappa = \frac{\lambda_{\max}(H)}{\lambda_{\min}(H)}$$

Jika $\kappa \gg 1$, lanskap loss berbentuk lembah curam memanjang (*anisotropic ravine*). Pada kondisi ini:
- Gradien mengarah hampir ortogonal terhadap arah menuju titik minimum global.
- Pembaruan bobot vanilla SGD akan berosilasi secara destruktif melintasi dinding ngarai dengan laju belajar $\eta > \frac{2}{\lambda_{\max}}$, sementara pergerakan sepanjang dasar ngarai sangat lambat ($\sim \eta \lambda_{\min}$).

```
            Sumbu Curam (λ_max tinggi)
                 ^
                 │       /\  /\  /\   Osilasi Destruktif (SGD)
                 │      /  \/  \/  \
─────────────────┼────────────────────────> Sumbu Datar (λ_min rendah)
                 │     -------------------> Trajektori Konvergen (AdamW/Momentum)
                 │
```

#### Saddle Points vs Local Minima dalam Dimensi Tinggi
Dalam ruang parameter dimensi tinggi ($d > 10^7$), titik kritis non-konveks yang mendominasi sebagian besar bukanlah *local minima*, melainkan *saddle points* yang dikelilingi oleh ruang tangensial hiperbolik. Matriks Hessian pada saddle point memiliki spektrum nilai eigen campuran ($\lambda_i > 0$ dan $\lambda_j < 0$). Escape trajectory dari saddle point membutuhkan eksploitasi komponen kurvatur negatif melalui injeksi stochastic noise atau momentum akumulatif.

### 3.3 Mekanika Adaptive Optimizers: Adam vs AdamW

Algoritma Adam (Kingma & Ba, 2014) mengatur laju belajar individual untuk setiap parameter berdasarkan estimasi momen pertama (rata-rata terbobot eksponensial gradien) dan momen kedua (rata-rata terbobot eksponensial gradien kuadrat).

#### Perbedaan Fundamental: L2 Regularization vs Decoupled Weight Decay
Implementasi Adam klasik keliru mengasumsikan bahwa regularisasi bobot $L_2$ setara dengan *Weight Decay*.
Fungsi objektif dengan regularisasi $L_2$:
$$\mathcal{L}_{\text{reg}}(\boldsymbol{\theta}) = \mathcal{L}(\boldsymbol{\theta}) + \frac{\lambda}{2} \|\boldsymbol{\theta}\|_2^2$$
Maka gradien yang masuk ke optimizer adalah:
$$\mathbf{g}_t = \nabla \mathcal{L}(\boldsymbol{\theta}_t) + \lambda \boldsymbol{\theta}_t$$

Pada Adam konvensional, suku $\lambda \boldsymbol{\theta}_t$ dimasukkan ke dalam estimasi momen pertama ($m_t$) dan momen kedua ($v_t$):
$$v_t = \beta_2 v_{t-1} + (1 - \beta_2) (\nabla \mathcal{L}(\boldsymbol{\theta}_t) + \lambda \boldsymbol{\theta}_t)^2$$

Akibatnya, jika suatu parameter memiliki bobot $\boldsymbol{\theta}_t$ yang besar namun gradien asli $\nabla \mathcal{L}(\boldsymbol{\theta}_t)$ bernilai kecil, momen kedua $v_t$ tetap terdorong naik. Karena faktor normalisasi $\frac{1}{\sqrt{\hat{v}_t} + \epsilon}$, penalti penusutan bobot justru mengecil secara drastis saat $v_t$ besar. Hal ini meniadakan efektivitas regularisasi terhadap parameter berbobot besar.

**AdamW (Loshchilov & Hutter, 2017)** memisahkan (*decouples*) weight decay secara langsung dari estimasi gradien adaptif:
$$\boldsymbol{\theta}_{t+1} = \boldsymbol{\theta}_t - \eta_t \lambda \boldsymbol{\theta}_t - \frac{\eta_t}{\sqrt{\hat{v}_t} + \epsilon} \hat{m}_t$$

Dengan formulasi ini, penalti penyusutan bobot proporsional terhadap magnitudo parameter itu sendiri, terlepas dari skala gradien adaptifnya.

---

## 4. Why & What

| Pendekatan / Komponen | What (Definisi & Mekanisme) | Why (Alasan Rekayasa & Signifikansi) |
| :--- | :--- | :--- |
| **Tape-Based Reverse Autodiff** | Engine pelacakan aljabar linier dinamis yang merekam pointer dependensi operasi backward saat forward pass berlangsung. | Mengeliminasi kebutuhan konstruksi simbolik statis. Memungkinkan percabangan dinamis (*control flow loops*, *recursion*) dengan kompleksitas gradien optimal $O(1)$. |
| **Hessian-Vector Product (HVP)** | Metode komputasi $H\mathbf{v} = \nabla (\nabla \mathcal{L}^T \mathbf{v})$ menggunakan diferensiasi otomatis ganda tanpa instansiasi matriks $H$. | Menghitung informasi kurvatur orde kedua dengan kompleksitas memori $O(d)$, bukan $O(d^2)$. Menghindari kehabisan memori GPU (OOM) pada model miliaran parameter. |
| **Decoupled Weight Decay (AdamW)** | Pengurangan bobot secara eksplisit pada vektor parameter secara independen dari moving average gradien kuadrat. | Memulihkan generalisasi model setara atau melebihi SGD dengan momentum, memecahkan masalah degradasi generalisasi Adam pada arsitektur ResNet dan Transformer. |
| **Dynamic Gradient Scaling** | Pengali skalar dinamis $S$ yang diterapkan pada loss sebelum backward pass pada representasi FP16. | Menghindari kondisi *underflow* eksponen 5-bit FP16 (di mana gradien $< 2^{-24} \approx 5.96 \times 10^{-8}$ menjadi nol mutlak), menjaga stabilitas konvergensi numerik. |
| **Gradient Clipping by Global Norm** | Penyekalaan gradien jika $L_2$-norm gabungan seluruh parameter melebihi ambang batas $C$: $\mathbf{g} \leftarrow \mathbf{g} \cdot \min(1, \frac{C}{\|\mathbf{g}\|_2})$. | Mencegah lonjakan parameter (*parameter explosion*) yang merusak geometri representasi latent ketika model melewati daerah loss berkurvatur sangat tinggi (*loss cliff*). |

---

## 5. How (Workflow Detail)

Arsitektur siklus iterasi training modern kelas enterprise dieksekusi melalui urutan State Machine deterministik berikut:

```
[1. Forward Pass with Cast]
       │
       ▼ (autocast context FP16/BF16)
Compute Predictions -> Loss Calculation
       │
       ▼
[2. Dynamic Loss Scaling]
Scaled Loss = Loss * S
       │
       ▼
[3. Reverse-Mode Autodiff]
Scaled Loss.backward() -> Menghasilkan Scaled Gradients (g_scaled = g * S)
       │
       ▼
[4. Gradient Unscaling & Inf/NaN Checking]
Unscale: g = g_scaled / S
       │
       ├─--> [Inf / NaN Terdeteksi] ──> [Reject Step]
       │                                     │
       │                                     ▼
       │                               Turunkan Scale: S = S * Backoff_Factor
       │                               Lewati Optimizer Step (Zero Gradients)
       ▼ (Semua gradien valid)
[5. Gradient Norm Clipping]
Compute Global L2 Norm -> Clip if Norm > Threshold
       │
       ▼
[6. Optimizer Update Step (AdamW Execution)]
m_t = beta1 * m_{t-1} + (1 - beta1) * g
v_t = beta2 * v_{t-1} + (1 - beta2) * g^2
Weight Update & Weight Decay Decoupled Execution
       │
       ▼
[7. Dynamic Scale Growth]
Scale Counter += 1 -> If Counter == Growth_Interval: S = S * Growth_Factor
       │
       ▼
[8. Learning Rate Schedule Step]
Update LR via Cosine Annealing with Linear Warmup
```

---

## 6. Analogy & Diagram ASCII

### Analogi Ekosistem Optimasi: Tim Navigasi Celah Gunung Berkabut Tebal
Bayangkan Anda memimpin tim ekspedisi menuruni lembah berkabut tebal (*loss surface*) menuju titik terendah:
- **Gradient ($\nabla \mathcal{L}$)**: Kemiringan lokal tepat di bawah sepatu Anda. Dalam kabut tebal, Anda hanya bisa meraba sudut kemiringan satu langkah ke depan.
- **SGD Vanilla**: Pendaki yang melompat murni sesuai arah kemiringan saat itu. Jika berada di ngarai sempit, ia memantul bolak-balik membentur dinding tebing tanpa maju.
- **Momentum**: Menaruh bola boling berat di jalur. Bola tersebut mengabaikan riak kecil dan terus menggelinding stabil searah lereng utama.
- **Adam / Adaptive Step**: Pendaki yang mengenakan sepatu pegas pneumatik cerdas. Di lereng yang sangat curam, pegas mengeraskan diri agar tidak tergelincir; di lereng yang hampir datar, pegas memanjang melipatgandakan panjang langkah.
- **Weight Decay Decoupled**: Tali elastis yang perlahan menarik pendaki kembali ke base camp awal secara konstan, mencegah pendaki tersesat ke tepi jurang tak berhingga tanpa memedulikan seberapa aktif pegas pneumatiknya bergerak.

### Diagram Arsitektur Memory Pool & Gradient Flow Engine

```
+-----------------------------------------------------------------------------+
|                                HOST (CPU) RAM                               |
|  +---------------------+   +---------------------+   +--------------------+ |
|  | Dataset / Dataloader|-->| Worker Subprocesses |-->| Pin Memory Buffer  | |
|  +---------------------+   +---------------------+   +---------+----------+ |
+----------------------------------------------------------------│------------+
                                                                 │ Non-blocking
                                                                 │ D2H / H2D Copy
+----------------------------------------------------------------│------------+
|                            DEVICE (GPU) VRAM / HBM             ▼            |
|                                                                             |
|  +-----------------------------------------------------------------------+  |
|  | Forward Computation Tensors (Cast to FP16 / BF16)                     |  |
|  |  [Layer 1 Act] ──> [Layer 2 Act] ──> ... ──> [Loss Tensor (FP32)]     |  |
|  +-------│───────────────────│───────────────────────────────│-----------+  |
|          │ Retained          │ Retained                      │ Scaled Loss  |
|          ▼ for Bwd           ▼ for Bwd                       ▼              |
|  +-----------------------------------------------------------------------+  |
|  | Tape-based Backward Graph (C++ Autograd Nodes)                        |  |
|  |  [GradFn Layer 1] <── [GradFn Layer 2] <── ... ── [GradFn Loss]       |  |
|  +-------│───────────────────│───────────────────────────────────────────+  |
|          ▼                   ▼                                              |
|  +-----------------------------------------------------------------------+  |
|  | Model Parameters & Optimization State (Master Weights in FP32)         |  |
|  |  Theta_FP32 [W1, W2] <── Unscaled & Clipped Grad Accumulator           |  |
|  |  AdamW States:                                                        |  |
|  |   - Exp Avg (1st Moment): m_t (FP32)                                  |  |
|  |   - Exp Avg Sq (2nd Moment): v_t (FP32)                               |  |
|  +-----------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Implementasi Custom Autograd Function (Higher-Order Differentiation)

Berikut implementasi operator kustom *Mish Activation Function* ($f(x) = x \cdot \tanh(\text{softplus}(x))$) dengan derivasi manual analytical backward pass untuk efisiensi komputasi dan konsumsi memori minimum.

```python
import torch
from torch.autograd import Function

class AnalyticalMishFunction(Function):
    """
    Implementasi kustom Mish Activation: y = x * tanh(ln(1 + e^x))
    Menyimpan intermediate activation tensor yang optimal untuk memangkas footprint VRAM.
    """
    
    @staticmethod
    def forward(ctx, x: torch.Tensor) -> torch.Tensor:
        # softplus(x) = ln(1 + exp(x))
        sp = torch.log1p(torch.exp(x.clamp(max=85.0))) # Hindari overflow FP32
        tanh_sp = torch.tanh(sp)
        y = x * tanh_sp
        
        # Simpan tensor yang dibutuhkan untuk backward pass
        ctx.save_for_backward(x, sp, tanh_sp)
        return y

    @staticmethod
    def backward(ctx, grad_output: torch.Tensor):
        x, sp, tanh_sp = ctx.saved_tensors
        
        # sigmoid(x) = 1 / (1 + exp(-x))
        sigma_x = torch.sigmoid(x)
        
        # Turunan analitis:
        # d/dx [x * tanh(sp)] = tanh(sp) + x * sech^2(sp) * d(sp)/dx
        # sech^2(sp) = 1 - tanh^2(sp)
        # d(sp)/dx = sigmoid(x)
        sech2_sp = 1.0 - (tanh_sp ** 2)
        grad_x = grad_output * (tanh_sp + x * sigma_x * sech2_sp)
        
        return grad_x

def test_custom_autograd():
    x = torch.randn(1024, 1024, dtype=torch.float64, requires_grad=True, device='cuda' if torch.cuda.is_available() else 'cpu')
    
    # Verifikasi keakuratan gradien menggunakan numeric finite-difference
    is_valid = torch.autograd.gradcheck(AnalyticalMishFunction.apply, x, eps=1e-6, atol=1e-4)
    print(f"[Engine Check] Operator Mish Gradient Check Pass: {is_valid}")

if __name__ == "__main__":
    test_custom_autograd()
```

### 7.2 Practical Example: Enterprise-Grade AdamW Optimizer & Resilient Training Engine

Implementasi penuh optimizer **AdamW** dari nol, disandingkan dengan *Training Pipeline* kelas produksi yang menerapkan *Mixed Precision* (AMP), *Dynamic Loss Scaling*, *Global Gradient Clipping*, dan *Cosine Annealing with Linear Warmup*.

```python
import math
import torch
from torch.optim.optimizer import Optimizer
from typing import List, Optional, Tuple, Dict, Any

class EnterpriseAdamW(Optimizer):
    """
    AdamW: Decoupled Weight Decay Optimizer.
    Sesuai standar formal Loshchilov & Hutter (2017).
    Mendukung validasi tipe data presisi, pencegahan pembagian dengan nol,
    dan alokasi state memory lazily.
    """
    def __init__(
        self,
        params,
        lr: float = 1e-3,
        betas: Tuple[float, float] = (0.9, 0.999),
        eps: float = 1e-8,
        weight_decay: float = 1e-2,
        correct_bias: bool = True
    ):
        if lr < 0.0:
            raise ValueError(f"Invalid learning rate: {lr}")
        if eps < 0.0:
            raise ValueError(f"Invalid epsilon value: {eps}")
        if not 0.0 <= betas[0] < 1.0:
            raise ValueError(f"Invalid beta parameter at index 0: {betas[0]}")
        if not 0.0 <= betas[1] < 1.0:
            raise ValueError(f"Invalid beta parameter at index 1: {betas[1]}")
        if weight_decay < 0.0:
            raise ValueError(f"Invalid weight_decay value: {weight_decay}")

        defaults = dict(
            lr=lr,
            betas=betas,
            eps=eps,
            weight_decay=weight_decay,
            correct_bias=correct_bias
        )
        super(EnterpriseAdamW, self).__init__(params, defaults)

    @torch.no_grad()
    def step(self, closure=None) -> Optional[float]:
        loss = None
        if closure is not None:
            with torch.enable_grad():
                loss = closure()

        for group in self.param_groups:
            beta1, beta2 = group['betas']
            eps = group['eps']
            lr = group['lr']
            weight_decay = group['weight_decay']
            correct_bias = group['correct_bias']

            for p in group['params']:
                if p.grad is None:
                    continue
                
                grad = p.grad
                if grad.is_sparse:
                    raise RuntimeError("EnterpriseAdamW tidak mendukung kalkulasi gradien sparse (COO).")

                state = self.state[p]

                # Lazy state initialization
                if len(state) == 0:
                    state['step'] = 0
                    # Alokasikan state tensor dengan tipe dan layout yang sama persis
                    state['exp_avg'] = torch.zeros_like(p, memory_format=torch.preserve_format)
                    state['exp_avg_sq'] = torch.zeros_like(p, memory_format=torch.preserve_format)

                exp_avg, exp_avg_sq = state['exp_avg'], state['exp_avg_sq']
                state['step'] += 1
                step = state['step']

                # 1. Aplikasikan Decoupled Weight Decay secara eksplisit
                if weight_decay > 0.0:
                    p.mul_(1.0 - lr * weight_decay)

                # 2. Update biased first moment estimate: m_t = beta1 * m_{t-1} + (1 - beta1) * g_t
                exp_avg.mul_(beta1).add_(grad, alpha=1.0 - beta1)

                # 3. Update biased second raw moment estimate: v_t = beta2 * v_{t-1} + (1 - beta2) * g_t^2
                exp_avg_sq.mul_(beta2).addcmul_(grad, grad, value=1.0 - beta2)

                # 4. Bias correction calculation
                if correct_bias:
                    bias_correction1 = 1.0 - beta1 ** step
                    bias_correction2 = 1.0 - beta2 ** step
                    step_size = lr * (math.sqrt(bias_correction2) / bias_correction1)
                    denom = exp_avg_sq.sqrt().add_(eps)
                    p.addcdiv_(exp_avg, denom, value=-step_size)
                else:
                    denom = exp_avg_sq.sqrt().add_(eps)
                    p.addcdiv_(exp_avg, denom, value=-lr)

        return loss


class CosineWarmupLRScheduler:
    """
    Cosine Annealing Learning Rate Schedule dengan fase Linear Warmup bertahap.
    """
    def __init__(self, optimizer: Optimizer, warmup_steps: int, total_steps: int, min_lr_ratio: float = 0.01):
        self.optimizer = optimizer
        self.warmup_steps = warmup_steps
        self.total_steps = total_steps
        self.min_lr_ratio = min_lr_ratio
        self.base_lrs = [group['lr'] for group in optimizer.param_groups]
        self.current_step = 0

    def step(self):
        self.current_step += 1
        lr_factor = self._compute_factor()
        for param_group, base_lr in zip(self.optimizer.param_groups, self.base_lrs):
            param_group['lr'] = base_lr * lr_factor

    def _compute_factor(self) -> float:
        if self.current_step < self.warmup_steps:
            # Linear Warmup
            return float(self.current_step) / float(max(1, self.warmup_steps))
        
        # Cosine Annealing
        progress = float(self.current_step - self.warmup_steps) / float(max(1, self.total_steps - self.warmup_steps))
        progress = min(1.0, max(0.0, progress))
        cosine_decay = 0.5 * (1.0 + math.cos(math.pi * progress))
        return self.min_lr_ratio + (1.0 - self.min_lr_ratio) * cosine_decay


class ProductionEngine:
    """
    Mesin orkestrasi training skala enterprise. Mengendalikan mixed-precision,
    clipping global norm, gradient accumulation, dan dynamic state management.
    """
    def __init__(
        self,
        model: torch.nn.Module,
        optimizer: Optimizer,
        scheduler: CosineWarmupLRScheduler,
        device: torch.device,
        max_grad_norm: float = 1.0,
        gradient_accumulation_steps: int = 1,
        use_amp: bool = True
    ):
        self.model = model.to(device)
        self.optimizer = optimizer
        self.scheduler = scheduler
        self.device = device
        self.max_grad_norm = max_grad_norm
        self.grad_accum_steps = gradient_accumulation_steps
        self.use_amp = use_amp
        
        # Inisialisasi scaler internal untuk dynamic loss scaling
        self.scaler = torch.amp.GradScaler('cuda', enabled=use_amp)

    def train_epoch(self, dataloader: torch.utils.data.DataLoader, epoch_idx: int) -> float:
        self.model.train()
        total_loss = 0.0
        self.optimizer.zero_grad(set_to_none=True) # set_to_none membebaskan memori VRAM lebih cepat

        for step_idx, (batch_x, batch_y) in enumerate(dataloader):
            batch_x = batch_x.to(self.device, non_blocking=True)
            batch_y = batch_y.to(self.device, non_blocking=True)

            # 1. Forward Pass dengan AMP Context
            with torch.amp.autocast('cuda', enabled=self.use_amp):
                predictions = self.model(batch_x)
                loss = torch.nn.functional.cross_entropy(predictions, batch_y)
                # Normalisasi loss berdasarkan akumulasi gradien
                loss = loss / self.grad_accum_steps

            # 2. Scaled Backward Pass
            self.scaler.scale(loss).backward()
            total_loss += loss.item() * self.grad_accum_steps

            # 3. Step Condition (Gradient Accumulation Boundary)
            if (step_idx + 1) % self.grad_accum_steps == 0 or (step_idx + 1) == len(dataloader):
                # Unscale gradien sebelum clipping dilakukan
                self.scaler.unscale_(self.optimizer)
                
                # Clip global grad norm
                total_norm = torch.nn.utils.clip_grad_norm_(
                    self.model.parameters(), 
                    self.max_grad_norm
                )

                # Optimizer step via Scaler (Lewati jika nilai NaN/Inf terdeteksi)
                scaler_response = self.scaler.step(self.optimizer)
                self.scaler.update()

                # Zero gradients dan update scheduler hanya jika step tidak dilewati
                self.optimizer.zero_grad(set_to_none=True)
                self.scheduler.step()

        return total_loss / len(dataloader)
```

---

## 8. Real-World Case Study (Enterprise Scale)

### Kasus: Ketidakstabilan Pelatihan Multi-Billion Parameter Transformer (Loss Spikes & NaN Divergence)

#### Konteks & Skala Sistem
Sebuah institusi finansial melatih arsitektur Transformer 7B parameter pada kluster 64x GPU NVIDIA H100 (8 node x 8 GPU, SXM5 NVLink + InfiniBand NDR 400Gbps). Dataset terdiri atas 1.2 triliun token transaksi keuangan tabular dan teks semi-terstruktur. 

#### Gejala Masalah di Produksi
Pada token ke-450 miliar (sekitar 38% progres pelatihan), metrik training tiba-tiba menunjukkan:
1. **Loss Spike**: Loss Cross-Entropy melompat seketika dari $1.82$ ke $11.45$.
2. **Gradient Norm Explosion**: Global grad norm melonjak dari nominal $0.8$ menjadi $1.4 \times 10^4$.
3. **Numerik Divergence**: Dalam 4 step setelahnya, seluruh bobot pada layer Attention Attention Projection (QKV) berubah menjadi `NaN`. Training cluster terhenti (*failed-state exit*).

```
Training Loss
    ^
    │
2.0 ┼──────────────\
1.8 ┼               \
    │                \___/───/\           <--- Lonjakan Loss (Spike)
    │                          \     /\
0.0 ┼───────────────────────────\___/──\─────> NaN Divergence (Crash)
    └──────────────────────────────────────> Time / Tokens (450B)
```

#### Investigasi Akar Masalah (*Root Cause Analysis*)
1. **Analisis Spektral Gradien**: Tim ML Engineering memuat snapshot checkpoint terakhir sebelum divergensi dan menghitung nilai eigen matriks Hessian menggunakan Power Iteration Method. Ditemukan bahwa nilai eigen terbesar ($\lambda_{\max}$) melesat hingga ordo $10^6$ pada layer *LayerNorm* sebelum SwiGLU MLP. Kondisi ini membuat permukaan rugi membentuk *sharp ravines*.
2. **Underflow Eksponen FP16**: Pelatihan awalnya menggunakan format FP16 murni dengan static dynamic loss scaling. Pada layer terdalam, gradien backward bernilai $\approx 10^{-7}$, jatuh di bawah batas representasi denormal minimum FP16, menyebabkan degradasi gradien menjadi nol mutlak (zero-gradient stall).
3. **Out-of-Sync Weight Decay**: Implementasi optimasi memakai vanilla Adam dengan penalti $L_2$, bukan AdamW murni. Bobot parameter pada layer proyeksi tumbuh tak terkendali seiring waktu karena ketiadaan penyusutan bobot nyata pada parameter dengan frekuensi aktivasi jarang.

#### Solusi Rekayasa & Arsitektur Perbaikan
1. **Migrasi Presisi ke BFloat16 murni**: Menggantikan FP16 dengan BF16. BF16 mempertahankan dynamic range yang setara dengan FP32 (8-bit exponent), sehingga secara teknis mengeliminasi kebutuhan *Dynamic Loss Scaler* dan kebal terhadap *underflow*.
2. **Independent QK Normalization**: Menambahkan RMSNorm langsung pada vektor Query ($Q$) dan Key ($K$) tepat sebelum operasi dot-product attention:
   $$\text{Attention}(Q, K, V) = \text{softmax}\left(\frac{\text{RMSNorm}(Q) \cdot \text{RMSNorm}(K)^T}{\sqrt{d_k}}\right)V$$
   Langkah ini menekan nilai masukan matriks softmax ke dalam rentang $[-1, 1]$, membatasi logit scale agar tidak menyentuh daerah saturasi gradien nol.
3. **Stabilization Checkpointer & Auto-Rollback Handler**: Membangun listener hook pada training loop yang memantau running mean global norm:
   - Jika $\text{Norm}_{t} > 5 \times \text{EMA}(\text{Norm})$, step ditolak (*gradient zeroed*).
   - State model otomatis di-rollback ke checkpoint valid 500 step sebelumnya, memuat ulang learning rate dengan pengurangan 30% (*backoff recovery*).

Hasil: Training berjalan lancar hingga 1.2 triliun token tanpa divergensi lanjutan, menghemat estimasi biaya komputasi GPU senilai ratusan ribu dollar dari mitigasi restart berulang.

---

## 9. Trade-Offs

| Dimensi Rekayasa | Pendekatan A | Pendekatan B | Analisis Trade-off Arsitektural |
| :--- | :--- | :--- | :--- |
| **Precision Strategy** | FP16 (with GradScaler) | BF16 (Native Precision) | FP16 memiliki presisi mantissa lebih tinggi (10 bit vs 7 bit), cocok untuk model konvolusional sensitif. Namun FP16 mudah mengalami underflow/overflow dan membutuhkan kompleksitas alokasi Dynamic Loss Scaler. BF16 menawarkan jangkauan dinamis setara FP32 (8-bit eksponen), mengeliminasi scaler, namun presisi numerik mantissa lebih rendah yang dapat memicu akumulasi rounding error jika learning rate terlalu kecil. |
| **Optimizer Family** | SGD dengan Nesterov Momentum | AdamW (Adaptive Moment) | SGD-Nesterov memiliki jejak memori GPU minimal (1x ukuran bobot untuk state momentum) dan kapasitas generalisasi teoritis yang unggul pada vision. AdamW membutuhkan memori VRAM 2x lipat (menyimpan momen $m$ dan $v$), melipatgandakan beban I/O memori, tetapi memiliki ketahanan superior terhadap permukaan non-konveks dan konvergensi hingga 5x-10x lebih cepat pada transformer. |
| **Second-Order Information** | Explicit Hessian ($\mathbb{R}^{d \times d}$) | Hessian-Free (HVP / Conjugate Gradient) | Menghitung Hessian eksplisit sama sekali tidak layak untuk model parameter $> 10^6$ karena kompleksitas memori $O(d^2)$ ($7\text{B parameter} \approx 196 \text{ Petabyte VRAM}$). Hessian-Free menghitung efek kelengkungan melalui dua kali backward pass dengan memori $O(d)$, namun menambah beban latency throughput forward-backward sebesar 2x-3x. |
| **Autograd Graph Tracking** | `torch.enable_grad()` (Full Dynamic) | Gradient Checkpointing (`torch.utils.checkpoint`) | Dynamic graph standar menyimpan seluruh tensor aktivasi intermediate di VRAM untuk kebutuhan backward, menghasilkan throughput maksimal (TFLOPS tinggi) namun boros memori (OOM pada batch besar). Gradient Checkpointing membuang aktivasi intermediate dan menghitungnya kembali saat backward pass: memangkas memori aktivasi hingga 70-80%, namun membayar penalti komputasi tambahan 25-33% forward time overhead. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Akumulasi Loss Tensor Tanpa `.item()` (Memory Leak Kritis)
- **Kesalahan Fatal**: Menulis `total_loss += loss` di dalam training loop.
- **Mekanisme Kegagalan**: Variabel `loss` bukan sekadar angka skalar Python, melainkan tensor PyTorch yang terhubung ke seluruh computational graph. Menjumlahkannya secara kumulatif mencegah garbage collector C++ autograd membebaskan ribuan tensor aktivasi dari forward pass sebelumnya, menyebabkan GPU VRAM terkuras eksponensial hingga crash OOM (*Out Of Memory*).
- **Solusi Korektif**: Gunakan tipe primitif skalar: `total_loss += loss.item()`.

### 10.2 Pemanggilan `.zero_grad()` yang Keliru atau Terlupakan
- **Kesalahan Fatal**: Menjalankan backward pass berturut-turut tanpa mereset gradien saat tidak mengimplementasikan accumulation intentionally.
- **Mekanisme Kegagalan**: PyTorch secara akumulatif menambahkan gradien baru ke buffer parameter (`p.grad += new_grad`). Jika `.zero_grad()` tidak dieksekusi, magnitude gradien akan bertambah seiring waktu, memicu ledakan bobot seketika pada step berikutnya.
- **Solusi Korektif**: Panggil `optimizer.zero_grad(set_to_none=True)` pada awal atau akhir setiap batch step valid. Parameter `set_to_none=True` menginstruksikan runtime PyTorch untuk menyetel memory pointer gradien ke `nullptr` alih-alih mengisinya dengan tensor nol via memset CUDA, menghemat bandwidth memori.

### 10.3 Eksekusi `clip_grad_norm_` Setelah Pemanggilan `optimizer.step()`
- **Kesalahan Fatal**:
  ```python
  optimizer.step()
  torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0) # SALAH!
  ```
- **Mekanisme Kegagalan**: Clipping yang dieksekusi setelah `step()` sama sekali tidak berguna. Optimizer telah menerapkan gradien yang meledak ke dalam matriks bobot model sebelum clipping sempat memodifikasi nilai `p.grad`.
- **Solusi Korektif**: Selalu unscale dan lakukan clipping sebelum parameter step dijalankan:
  ```python
  scaler.unscale_(optimizer)
  torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
  scaler.step(optimizer)
  scaler.update()
  ```

### 10.4 Injeksi Static Decoupled Weight Decay pada Bias dan LayerNorm
- **Kesalahan Fatal**: Menerapkan weight decay seragam ke seluruh parameter tensor tanpa segregasi.
- **Mekanisme Kegagalan**: Bias dan parameter afinitas normalisasi (skalar $\gamma$ dan $\beta$ pada LayerNorm/BatchNorm/RMSNorm) tidak berkontribusi terhadap kompleksitas representasi struktural model. Memberikan penalti weight decay pada parameter 1-dimensi ini justru mengerdilkan kemampuan normalisasi layer dalam mempertahankan kestabilan distribusi aktivasi, memicu degradasi performa model.
- **Solusi Korektif**: Buat grup parameter terpisah saat mendaftarkan variabel ke optimizer:
  ```python
  decay_params = []
  no_decay_params = []
  for name, param in model.named_parameters():
      if not param.requires_grad:
          continue
      if param.ndim <= 1 or name.endswith(".bias") or "norm" in name.lower():
          no_decay_params.append(param)
      else:
          decay_params.append(param)

  optimizer_grouped_parameters = [
      {"params": decay_params, "weight_decay": 0.01},
      {"params": no_decay_params, "weight_decay": 0.0},
  ]
  optimizer = EnterpriseAdamW(optimizer_grouped_parameters, lr=1e-3)
  ```

---

## 11. Best Practices & Production Checklist

1. [ ] **FP32 Master Weights Preservation**: Pastikan optimizer menyimpan salinan bobot internal dalam format `FP32` ketika melatih model dengan presisi rendah (FP16/BF16) guna mencegah pembulatan matematis menjadi nol saat kalkulasi update step delta ($\Delta \theta$).
2. [ ] **Memory Optimization via `set_to_none=True`**: Selalu aktifkan parameter `set_to_none=True` saat memanggil `optimizer.zero_grad()` untuk mengurangi latency pembersihan memori CUDA secara signifikan.
3. [ ] **Determinisme vs Throughput Benchmarking**: Tentukan kebutuhan determinisme. Jika auditabilitas penuh dibutuhkan, setel `torch.use_deterministic_algorithms(True)`. Jika throughput prioritas utama, aktifkan flag cuDNN auto-tuner: `torch.backends.cudnn.benchmark = True`.
4. [ ] **Gradien Logging Terstandarisasi**: Pantau global gradien norm, rasio pembaruan bobot terhadap bobot ($\|\Delta \mathbf{w}\| / \|\mathbf{w}\|$), dan learning rate secara per-layer melalui Weights & Biases atau TensorBoard. Rasio pembaruan yang ideal berada di kisaran $10^{-3}$ hingga $10^{-4}$.
5. [ ] **Parameter Segregation**: Selalu pisahkan parameter embedding, bias, dan matriks normalisasi affine dari skema evaluasi *Weight Decay*.
6. [ ] **Dynamic Anomaly Detection Guards**: Dalam mode debugging pra-rilis, aktifkan runtime detector: `torch.autograd.set_detect_anomaly(True)`. Matikan segera pada mode production training karena overhead latensinya mencapai $>40\%$.

---

## 12. Hands-on Practice

Buat repositori dan struktur direktori hands-on berikut:

```
hands-on/m02/
├── configs/
│   └── train_config.json
├── src/
│   ├── __init__.py
│   ├── engine.py
│   ├── modules.py
│   └── optimizers.py
└── train.py
```

### Langkah 1: Buat Arsitektur Model Uji (`hands-on/m02/src/modules.py`)

```python
# hands-on/m02/src/modules.py
import torch
import torch.nn as nn

class DeepMLP(nn.Module):
    def __init__(self, in_features: int, hidden_dim: int, num_classes: int, depth: int = 6):
        super().__init__()
        layers = []
        current_dim = in_features
        for i in range(depth):
            layers.append(nn.Linear(current_dim, hidden_dim))
            layers.append(nn.LayerNorm(hidden_dim))
            layers.append(nn.GELU())
            current_dim = hidden_dim
        layers.append(nn.Linear(hidden_dim, num_classes))
        self.network = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.network(x)
```

### Langkah 2: Buat Modul Optimizer Mandiri (`hands-on/m02/src/optimizers.py`)
Salin implementasi `EnterpriseAdamW` dan `CosineWarmupLRScheduler` dari **Seksi 7.2** ke dalam berkas `hands-on/m02/src/optimizers.py`.

### Langkah 3: Buat Training Runner Skrip (`hands-on/m02/train.py`)

```python
# hands-on/m02/train.py
import sys
import torch
from torch.utils.data import TensorDataset, DataLoader
from src.modules import DeepMLP
from src.optimizers import EnterpriseAdamW, CosineWarmupLRScheduler
from src.engine import ProductionEngine # Impor implementasi dari Seksi 7.2

def run_experiment():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"[Init] Menjalankan experiment pada device: {device}")

    # 1. Dataset Sintetik Skala Besar (Simulasi Distribusi Berdimensi Tinggi)
    N_SAMPLES, FEATURES, CLASSES = 20000, 256, 10
    X = torch.randn(N_SAMPLES, FEATURES)
    Y = torch.randint(0, CLASSES, (N_SAMPLES,))
    
    dataset = TensorDataset(X, Y)
    dataloader = DataLoader(dataset, batch_size=128, shuffle=True, pin_memory=True if device.type == 'cuda' else False)

    # 2. Inisialisasi Model
    model = DeepMLP(in_features=FEATURES, hidden_dim=512, num_classes=CLASSES, depth=8)

    # 3. Pemisahan Parameter (Decay vs No-Decay)
    decay_params, no_decay_params = [], []
    for name, p in model.named_parameters():
        if p.ndim <= 1 or "bias" in name or "norm" in name:
            no_decay_params.append(p)
        else:
            decay_params.append(p)

    optim_groups = [
        {"params": decay_params, "weight_decay": 0.05},
        {"params": no_decay_params, "weight_decay": 0.0}
    ]

    # 4. Inisialisasi Optimizer & Warmup Scheduler
    EPOCHS = 5
    total_training_steps = len(dataloader) * EPOCHS
    warmup_steps = int(0.1 * total_training_steps)

    optimizer = EnterpriseAdamW(optim_groups, lr=3e-4, betas=(0.9, 0.98), eps=1e-6)
    scheduler = CosineWarmupLRScheduler(optimizer, warmup_steps=warmup_steps, total_steps=total_training_steps)

    # 5. Inisialisasi Engine
    engine = ProductionEngine(
        model=model,
        optimizer=optimizer,
        scheduler=scheduler,
        device=device,
        max_grad_norm=1.0,
        gradient_accumulation_steps=2,
        use_amp=(device.type == 'cuda')
    )

    # 6. Eksekusi Pelatihan
    for epoch in range(1, EPOCHS + 1):
        loss = engine.train_epoch(dataloader, epoch)
        current_lr = optimizer.param_groups[0]['lr']
        print(f"Epoch {epoch:02d}/{EPOCHS:02d} | Avg Scaled Cross-Entropy Loss: {loss:.4f} | Current LR: {current_lr:.6e}")

if __name__ == "__main__":
    run_experiment()
```

---

## 13. Exercises

### Level Easy
1. Modifikasi method `step()` pada `EnterpriseAdamW` untuk mengimplementasikan fungsionalitas logging internal yang merekam *running average* rasio pembaruan:
   $$R_t = \frac{\|\Delta \boldsymbol{\theta}_t\|_2}{\|\boldsymbol{\theta}_t\|_2}$$
   Cetak nilai $R_t$ setiap 100 iterasi. Parameter mana yang memiliki rasio pembaruan paling fluktuatif?

### Level Medium
1. Bangun operator autograd kustom bernama `CentroidNormalizedLinear` yang mengimplementasikan perkalian matriks $Y = XW^T$, di mana bobot $W$ harus dinormalisasi dengan mengurangi rata-rata per-kolomnya ($\tilde{W}_{ij} = W_{ij} - \frac{1}{d_{\text{in}}} \sum_{k} W_{ik}$) sebelum operasi dot product dilakukan. Turunkan dan implementasikan fungsi backward pass secara analitis manual tanpa menggunakan autograd bawaan untuk langkah transformasi bobot tersebut. Pastikan lolos pengujian `torch.autograd.gradcheck`.

### Level Hard
1. **Hessian-Vector Product via Dual Autodiff**: Buat fungsi modular `compute_hvp(loss_fn, model, vector_list)` yang menghitung produk Hessian-vektor:
   $$H \mathbf{v} = \nabla_{\boldsymbol{\theta}} \left( \nabla_{\boldsymbol{\theta}} \mathcal{L}^T \mathbf{v} \right)$$
   Gunakan teknik dua backward passes menggunakan `torch.autograd.grad` dengan flag `create_graph=True`. Hitung estimasi nilai eigen maksimum ($\lambda_{\max}$) dari Hessian model `DeepMLP` yang dilatih di atas menggunakan 20 iterasi *Power Iteration Method* tanpa pernah mengalokasikan matriks Hessian eksplisit di memori GPU.

---

## 14. Challenges

### Deskripsi Masalah: Fault-Tolerant Distributed Elastic Trainer Engine
Anda ditugaskan mendesain subsistem optimasi terdistribusi (*Distributed Elastic Training Subsystem*) untuk kluster AI enterprise. Sistem menghadapi kendala jaringan tak stabil yang sering menghasilkan *silent packet drops*, memicu kondisi *gradient desynchronization* antar rank GPU.

### Spesifikasi Teknis yang Wajib Dipenuhi:
1. **Dynamic Desync Detection**: Bangun wrapper optimizer terdistribusi yang menghitung *Cyclic Redundancy Check (CRC32)* atau cryptographic hashing dari representasi floating-point terkompresi dari gradien unscaled sebelum eksekusi pembaruan bobot di rank lokal.
2. **Consensus Voting Barrier**: Sebelum parameter diperbarui, rank master mengumpulkan hash representasi gradien dari semua rank pekerja via non-blocking point-to-point ring primitives. Jika ditemukan $\ge 1$ worker yang memiliki gradien divergen (hash mismatch):
   - Seluruh GPU worker harus menolak step pembaruan lokal (`gradient zeroed`).
   - Worker yang divergen secara dinamis diidentifikasi dan ditandai (*quarantined*).
   - Parameter master disinkronisasikan ulang ke worker yang terdampak via broadcast channel tanpa perlu me-restart training cluster.
3. **Zero OOM Recovery**: Jika alokasi memory GPU pada salah satu step memicu exception `torch.cuda.OutOfMemoryError`, engine harus secara otomatis menangkap exception tersebut, mengosongkan CUDA cache (`torch.cuda.empty_cache()`), menaikkan `gradient_accumulation_steps` sebesar 2x lipat, memotong ukuran micro-batch menjadi setengahnya, dan mengulang step yang gagal tanpa kehilangan progres pelatihan sebelumnya.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda)

1. Mengapa Reverse-Mode Automatic Differentiation lebih dipilih dibandingkan Forward-Mode untuk melatih Deep Neural Networks?
   - A. Reverse-Mode memiliki akurasi floating point yang lebih tinggi daripada Forward-Mode.
   - B. Reverse-Mode mampu mengevaluasi gradien skalar terhadap $N$ parameter dalam 1 pass backward, sedangkan Forward-Mode membutuhkan $N$ passes.
   - C. Forward-Mode tidak dapat diimplementasikan pada GPU modern karena keterbatasan arsitektur SIMD.
   - D. Reverse-Mode tidak memerlukan memori untuk menyimpan intermediate activation tensors.

2. Apa peran utama dari Dynamic Loss Scaler pada pelatihan mixed precision FP16?
   - A. Mempercepat perkalian matriks pada Tensor Cores.
   - B. Menggeser magnitude gradien ke atas agar tidak jatuh ke rentang *underflow* rentang dinamis FP16.
   - C. Mengurangi fragmentasi memori VRAM GPU.
   - D. Menjamin loss surface menjadi konveks secara lokal.

3. Apa konsekuensi teknis dari penggunaan parameter `set_to_none=True` pada `optimizer.zero_grad()`?
   - A. Menghapus tensor parameter dari graph secara permanen.
   - B. Mengabaikan eksekusi backward pass untuk layer linier.
   - C. Menyetel memory pointer gradien ke `nullptr`, menghindari pemanggilan kernel CUDA memset zero yang mahal.
   - D. Memaksa autograd engine mengeksekusi operasi forward pass dalam mode simbolik.

4. Formulasi AdamW memisahkan weight decay dari perhitungan momen gradien. Apa dampak langsungnya pada parameter dengan gradien historis yang sangat besar?
   - A. Parameter tersebut menerima penalti penusutan bobot yang setara dan independen terhadap skala gradien adaptifnya.
   - B. Parameter tersebut mengalami penalti penusutan bobot yang mendekati tak hingga.
   - C. Weight decay dibatalkan untuk parameter tersebut guna mencegah underflow.
   - D. Parameter tersebut langsung diproyeksikan kembali ke nol.

5. Manakah pernyataan yang benar mengenai kondisi matriks Hessian pada *Saddle Point*?
   - A. Seluruh nilai eigen matriks Hessian bernilai positif riil.
   - B. Seluruh nilai eigen matriks Hessian bernilai negatif riil.
   - C. Matriks Hessian memiliki kombinasi nilai eigen positif dan negatif.
   - D. Matriks Hessian tidak dapat dihitung karena determinannya nol.

---

### Bagian 2: Intermediate (Pilihan Ganda & Analisis Arsitektur)

6. Diberikan rasio kondisi Hessian $\kappa = \frac{\lambda_{\max}}{\lambda_{\min}} = 10^5$. Jika model dilatih menggunakan Vanilla SGD dengan laju belajar $\eta = \frac{1.9}{\lambda_{\max}}$, fenomena apa yang akan mendominasi dinamika pembaruan bobot?
   - A. Bobot model akan segera konvergen ke global minimum dalam kurang dari 100 iterasi.
   - B. Terjadi osilasi keras melintasi dinding ngarai kurvatur tinggi, sementara progres menuruni lembah utama menuju minimum berjalan sangat lambat.
   - C. Seluruh gradien model seketika menjadi NaN akibat underflow.
   - D. Kecepatan konvergensi pada sumbu $\lambda_{\min}$ akan meningkat secara dramatis melampaui AdamW.

7. Mengapa penalti Weight Decay tidak direkomendasikan untuk diterapkan pada skalar bias dan parameter LayerNorm?
   - A. Karena parameter-parameter tersebut tidak dialokasikan di memori VRAM GPU.
   - B. Karena parameter 1D tersebut tidak merepresentasikan kapasitas kapasitas kapasitas varians bobot struktural; penalti regulasi pada parameter ini justru merusak stabilitas skala normalisasi representasi.
   - C. Karena algoritma C++ PyTorch Autograd akan otomatis melempar RuntimeError jika tensor dimensi 1 diberi penalti.
   - D. Karena parameter tersebut selalu bernilai konstan sepanjang proses pelatihan.

8. Pada sistem pelatihan terdistribusi berskala ribuan akselerator, mengapa *Global Gradient Clipping by Norm* harus didahului oleh operasi komunikasi kolektif `AllReduce` gradien?
   - A. Untuk memastikan bahwa tensor gradien telah diubah menjadi representasi sparse COO.
   - B. Agar skalar global norm dihitung secara identik di seluruh rank worker berdasarkan total gradien global, bukan gradien lokal micro-batch masing-masing GPU.
   - C. Karena jika dieksekusi lokal, CUDA driver akan mematikan kernel forward pass.
   - D. Untuk mengonversi tipe data FP16 kembali ke INT8.

9. Manakah pernyataan berikut yang secara akurat menjelaskan mekanisme internal penyimpanan tensor aktivasi pada `torch.autograd.Function` kustom?
   - A. Semua tensor lokal otomatis disimpan ke disk host CPU secara background.
   - B. Fungsi `ctx.save_for_backward(*tensors)` membungkus tensor dalam objek `SavedVariable`, memicu pencatatan referensi ke graph autograd dan mempertahankan alokasi VRAM hingga method `backward` selesai dieksekusi.
   - C. Tensor forward otomatis dimusnahkan oleh garbage collector tepat setelah forward function me-return hasil.
   - D. Simpul forward otomatis menduplikasi dirinya sebanyak jumlah GPU yang aktif.

10. Apa kelemahan utama dari optimizer berbasis metode Second-Order eksak (seperti Classical Newton-Raphson) dalam konteks deep learning modern?
    - A. Membutuhkan inversi matriks Hessian $H^{-1}$ dengan kompleksitas komputasi $O(d^3)$ dan memori $O(d^2)$, menjadikannya mustahil diaplikasikan pada model dengan jutaan parameter.
    - B. Newton-Raphson selalu konvergen menuju saddle points alih-alih local minima.
    - C. Metode orde kedua tidak kompatibel secara matematis dengan fungsi aktivasi non-linier.
    - D. Metode tersebut hanya dapat bekerja pada arsitektur Single-Layer Perceptron.

---

### Bagian 3: Skenario Kasus Produksi

11. **Kasus Pelatihan Model Rekomendasi Skala Terabyte**:  
    Sebuah model rekomendasi Deep Learning dengan embedding table berukuran 800 GB dilatih menggunakan optimizer AdamW standar. Sistem mengalami *Out-Of-Memory* (OOM) seketika saat training loop pertama kali memasuki eksekusi `optimizer.step()`, meskipun forward pass berjalan tanpa kendala memori. Analisislah penyebab struktural kehabisan memori ini dan rancang solusi arsitektur optimasi yang efisien tanpa mengurangi akurasi model.

12. **Kasus Gradient Vanishing Siluman pada Custom Attention Engine**:  
    Sebuah tim AI membangun arsitektur attention sparse baru menggunakan operator C++ kustom. Saat diuji pada sequence length 32k token, loss stagnan mutlak sejak step 1. Metrik logging menunjukkan gradien pada layer terendah bernilai persis $0.0$, namun `loss.backward()` tidak melempar error apa pun. Bagaimana langkah diagnostik sistematis ML Engineer untuk mengidentifikasi apakah bug terjadi pada graph linkage backward C++ atau saturasi matematis operator?

13. **Kasus Fluktuasi Global Loss Pasca Unscaling**:  
    Pada pipeline pelatihan model LLM berpresisi FP16 dengan Dynamic Loss Scaler, sistem berulang kali melaporkan pesan error warning: *"Step skipped: Scaler found Inf/NaN values in gradients"*. Akibatnya, bobot model tidak pernah diperbarui selama ribuan iterasi berturut-turut, menyebabkan loss flat horizontal. Jelaskan urutan investigasi untuk memecahkan kebuntuan numerik ini.

---

### Kunci Jawaban & Rubrik Evaluasi

#### Bagian 1: Basic
1. **B**: Reverse-Mode menghitung seluruh turunan parsial skalar output terhadap ribuan/miliaran input variabel dalam satu pass traversal mundur berarah graf, memberikan efisiensi komputasi $O(1)$ relative backward cost.
2. **B**: Nilai gradien yang sangat kecil pada FP16 ($< 2^{-24}$) akan dibulatkan menjadi 0 (*underflow*). Dynamic loss scaling mengalikan loss dengan skalar besar untuk menggeser representasi bit gradien ke rentang normal.
3. **C**: Menghindari overhead memset nol pada memori GPU dan langsung mengalokasikan buffer memori baru saat gradien pertama kali diakumulasikan, meningkatkan throughput.
4. **A**: AdamW memisahkan weight decay dari kalkulasi momen, sehingga parameter dengan gradien besar tetap mendapatkan penyusutan bobot proporsional terhadap nilai bobot aslinya sendiri.
5. **C**: Karakteristik saddle point adalah matriks Hessian-nya memiliki nilai eigen campuran positif (kelengkungan ke atas) dan negatif (kelengkungan ke bawah).

#### Bagian 2: Intermediate
6. **B**: Ill-conditioning ($\kappa \gg 1$) menyebabkan optimizer First-Order melompat-lompat liar melintasi dimensi dengan kelengkungan tinggi ($\lambda_{\max}$), sementara pergerakan sepanjang lembah datar ($\lambda_{\min}$) dihambat secara drastis.
7. **B**: Skalar bias dan bobot LayerNorm merepresentasikan affine translation/scaling sederhana. Regularisasi $L_2$/weight decay pada parameter ini tidak memberikan efek regularisasi kapasitas model yang sehat, justru mendestabilisasi dinamika aktivasi.
8. **B**: Clipping norm mensyaratkan kalkulasi norma global seluruh model ($\sqrt{\sum \|\mathbf{g}_i\|^2}$). Jika dihitung sebelum AllReduce, setiap node akan memotong gradien berdasarkan norma lokal yang belum lengkap, merusak arah gradien gabungan secara matematis.
9. **B**: Mekanisme `ctx.save_for_backward` mempertahankan reference count tensor C++ autograd engine agar tidak dibersihkan oleh garbage collection sebelum backward pass selesai.
10. **A**: Menghitung dan membalikkan matriks kuadratik berukuran $d \times d$ membutuhkan alokasi memori $O(d^2)$ dan operasi $O(d^3)$ FLOPS, mustahil diterapkan pada model modern dengan $d > 10^7$.

#### Bagian 3: Rubrik Evaluasi Skenario Produksi

11. **Rubrik Evaluasi Kasus 11 (OOM AdamW pada Embedding Scale)**:
    - **Akar Masalah**: AdamW mengalokasikan 2 tensor state (first moment $m$ dan second moment $v$) dengan dimensi identik dengan parameter bobot. Untuk tabel embedding 800 GB dalam FP32, alokasi state membutuhkan tambahan $800 \text{ GB} \times 2 = 1.6 \text{ TB}$ memori VRAM. Ditambah bobot master FP32 dan gradien, konsumsi melonjak $>3.2 \text{ TB}$.
    - **Solusi Arsitektur**:
      1. Terapkan optimizer sparse khusus untuk embedding: **SparseAdam** atau library eksternal berkinerja tinggi seperti **bitsandbytes 8-bit Adam** (mengompresi state optimizer menjadi INT8 via block-wise quantization, memangkas memori state hingga 75%).
      2. Terapkan sharding parameter tabel embedding antar GPU worker menggunakan modul PyTorch FSDP (*Fully Sharded Data Parallel*) atau Megatron-LM Pipeline/Tensor Parallelism.
      3. Offload state optimizer embedding table ke CPU Host Memory via *ZeRO-Offload*, hanya memuat irisan state parameter yang aktif ke VRAM saat step pembaruan mikro berlangsung.

12. **Rubrik Evaluasi Kasus 12 (Bug Tracking Custom Operator)**:
    - **Metodologi Diagnostik**:
      1. Uji keabsahan Graph Wiring: Cetak atribut `grad_fn` dari output layer attention kustom. Jika bernilai `None`, maka koneksi autograd terputus (terjadi pemanggilan operator inplace atau *untracked tensor creation* seperti pembuatan tensor baru via `.data` atau instansiasi manual tanpa mendaftarkan edge).
      2. Validasi Numerik Finite-Difference: Eksekusi `torch.autograd.gradcheck` dengan tensor input presisi tinggi FP64 pada input berdimensi kecil.
      3. Analisis Saturasi Nilai Input: Periksa magnitudo skalar logit sebelum normalisasi attention. Pada sequence length 32k, dot product $QK^T$ dapat menghasilkan skalar yang sangat besar jika tidak dibagi $\sqrt{d_k}$, mendorong output softmax mendekati 1.0 (saturasi absolut), yang memiliki turunan analitis mendekati nol mutlak ($s_i(1 - s_i) \to 0$).

13. **Rubrik Evaluasi Kasus 13 (Kebuntuan Dynamic Loss Scaler Inf/NaN)**:
    - **Akar Masalah**: Dynamic loss scale bernilai terlalu tinggi sehingga saat dikalikan dengan gradien forward, nilai gradien melebihi batas representasi numerik maksimum FP16 ($65504$), menghasilkan representasi bit `Inf`. Scaler merespons dengan membatalkan step dan menurunkan scale factor, namun step berikutnya kembali menghasilkan `Inf` atau underflow ke nol jika skala diturunkan terlalu drastis.
    - **Solusi Arsitektur**:
      1. Selidiki sumber saturasi gradien menggunakan runtime hook: pasang `register_hook` pada parameter untuk mendeteksi tensor spesifik pertama yang memunculkan nilai `NaN`/`Inf`.
      2. Periksa apakah model memiliki operasi sensitif numerik seperti $\sqrt{x}$ atau $\log(x)$ tanpa penambahan epsilon pengaman ($\sqrt{x + \epsilon}$).
      3. Lakukan konversi segera dari presisi FP16 ke **BF16**. BF16 memiliki rentang dinamis maksimum hingga $\approx 3.39 \times 10^{38}$ (sama dengan FP32), sehingga secara fundamental kebal terhadap overflow $65504$ dan mengeliminasi kebutuhan terhadap modul Dynamic Loss Scaler.

---

## 16. Summary

1. **Reverse-Mode Automatic Differentiation** adalah fondasi komputasional deep learning modern. Engine autograd merekam forward execution tape dan mengeksekusi kalkulasi turunan berbasis *Vector-Jacobian Product* (VJP), mencapai kompleksitas waktu evaluasi gradien independen terhadap jumlah dimensi parameter.
2. **Kondisi Lanskap Rugi (Loss Surface Curvature)** sangat ditentukan oleh struktur nilai eigen matriks Hessian. Wilayah dengan condition number tinggi ($\kappa \gg 1$) menyebabkan osilasi destruktif pada optimizer first-order konvensional, menuntut stabilisasi berbasis momentum adaptif.
3. **AdamW Mengoreksi Cacat Historis Adam**: Regularisasi bobot $L_2$ konvensional tidak identik dengan Weight Decay pada algoritma adaptif. AdamW memisahkan (*decouples*) penalti penyusutan bobot secara eksplisit dari akumulasi momen gradien adaptif, memulihkan kemampuan generalisasi model secara substansial.
4. **Stabilitas Numerik Skala Produksi** bersandar pada koordinasi harmonis antara:
   - Dynamic Loss Scaling (pada ekosistem FP16) atau Native BF16 execution.
   - Preservasi FP32 Master Parameters untuk akumulasi update delta mikroskopik.
   - Global Gradient Norm Clipping untuk membatasi lonjakan gradien melintasi tebing curam non-konveks.
   - Pemisahan penalti weight decay dari skalar bias dan matriks affine normalization.
5. **Zero-Waste Memory Architecture**: Menghindari akumulasi graph loss di VRAM via `.item()`, membebaskan alokasi memori gradien lebih awal melalui `set_to_none=True`, dan memanfaatkan *Gradient Checkpointing* merupakan prasyarat mutlak dalam membangun sistem rekayasa AI enterprise yang tangguh, efisien, dan berkinerja tinggi.