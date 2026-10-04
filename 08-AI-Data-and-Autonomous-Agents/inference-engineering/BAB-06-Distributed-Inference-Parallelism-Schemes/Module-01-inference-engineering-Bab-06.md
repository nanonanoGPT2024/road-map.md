# Bab 06: Distributed Inference & Parallelism Schemes

## Module 01: Tensor Parallelism (TP) & Distributed Operator Mechanics

Membawa model bahasa berukuran masif (Large Language Models/LLMs) seperti Llama-3-70B atau DeepSeek-V3 ke ranah *production serving* menghadirkan batas fisik (*physical ceiling*) pada kapasitas memori dan *bandwidth* dari satu GPU (*single-device execution*). Satu akselerator NVIDIA H100 SXM5 (80 GB) tidak dapat menampung parameter model 70B dalam presisi FP16 (bobot murni membutuhkan ~140 GB, di luar *KV Cache* dan *activation memory*). 

Solusi utama dari masalah ini adalah dekomposisi komputasi model ke berbagai akselerator menggunakan skema paralelisme terdistribusi. Module ini berfokus pada fondasi terpenting inferensi terdistribusi berlatensi rendah: **Tensor Parallelism (TP)** via dekomposisi Megatron-LM, sinkronisasi operator kolektif via NCCL (*NVIDIA Collective Communications Library*), serta mekanisme *inter-GPU memory fabric*.

---

### 1. Learning Objectives (Spesifik & Terukur)

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Menganalisis Dekomposisi Matriks**: Menghitung secara matematis pemisahan matriks bobot (*sharding*) berbasis *Column-Parallel* dan *Row-Parallel* pada modul *Multi-Head Attention* (MHA) dan *Multi-Layer Perceptron* (MLP) dengan kompleksitas komunikasi $O(B \cdot S \cdot H)$.
2. **Mengidentifikasi Pola Primitif NCCL**: Menentukan kapan harus mengeksekusi primitif `All-Reduce`, `All-Gather`, `Reduce-Scatter`, dan `Point-to-Point (P2P)` dalam *forward pass* inferensi terdistribusi.
3. **Mengimplementasikan Layer TP Kustom**: Membangun modul *ColumnParallelLinear* dan *RowParallelLinear* berbasis PyTorch `torch.distributed` yang *production-ready*, lengkap dengan *handling* bias, inisialisasi bobot terdistribusi, dan sinkronisasi autograd-free.
4. **Mencegah & Menangani Kegagalan Sistem Terdistribusi**: Mendiagnosis dan memitigasi *NCCL Watchdog Timeouts*, *silent data corruption* akibat *floating-point non-associativity* pada reduksi, serta *memory imbalance* antar rank.
5. **Mengukur & Mengoptimasi Bandwidth Interkoneksi**: Mengukur *saturation rate* dari NVLink vs PCIe Gen5 menggunakan metrik *Bus Bandwidth* dan *Algorithmic Bandwidth*.

---

### 2. Concept Overview (Mental Model & Teori Inti)

Secara konseptual, paralelisme inferensi dapat dibagi ke dalam tiga domain utama:

```
+-------------------------------------------------------------------------+
|                  Inference Parallelism Taxonomy                         |
+-------------------------------------------------------------------------+
       |                                |                        |
       v                                v                        v
+------------------+         +--------------------+      +---------------+
| Data Parallelism |         | Tensor Parallelism |      | Pipeline Par. |
|       (DP)       |         |        (TP)        |      |     (PP)      |
+------------------+         +--------------------+      +---------------+
| Replikasi bobot; |         | Membelah tensor di |      | Membagi layer |
| membagi request  |         | dalam satu layer;  |      | antar akselerator;|
| batch antar GPU. |         | latensi ultra-     |      | bubble latency|
| Butuh VRAM penuh |         | rendah (intra-     |      | tinggi untuk  |
| per akselerator. |         | node/NVLink).      |      | single query. |
+------------------+         +--------------------+      +---------------+
```

#### Mental Model: Tensor Parallelism (TP)
Tensor Parallelism adalah teknik *intra-layer sharding* di mana operasi perkalian matriks (GEMM: $Y = XW$) dipecah ke beberapa GPU (*ranks*) sehingga setiap akselerator hanya memproses sebagian dari bobot tensor secara simultan. 

Tujuan utama TP pada *inference engine* (seperti vLLM, TensorRT-LLM, atau SGLang) bukanlah sekadar mengatasi batas VRAM (*capacity scaling*), melainkan memotong latensi per-token (*Time Per Output Token* / TPOT) secara linear dengan mengakumulasi *memory bandwidth* dari beberapa kartu grafis sekaligus (*bandwidth aggregation*).

---

### 3. Why It Matters (Kebutuhan Industri & Enterprise)

1. **SLA Latensi Ketat (Strict TTFT & TPOT SLAs)**:
   Aplikasi *real-time* seperti *autonomous agents* atau asisten *voice-to-voice* menuntut TPOT di bawah $20\text{ ms/token}$. Karena inferensi fase *decode* didominasi oleh sifat *memory-bandwidth bound* (aritmatika rasio operasional rendah), membagi model ke 4 atau 8 GPU melalui TP menggabungkan *aggregate bandwidth* (misal: $8 \times 3.35\text{ TB/s} \approx 26.8\text{ TB/s}$ pada cluster H100 SXM5), mereduksi waktu pembacaan bobot secara drastis.
2. **Kapasitas KV Cache pada Konteks Masif**:
   Pada model Llama-3-70B dengan *context window* 128K token, ukuran KV Cache per request dapat melampaui $10\text{ GB}$. Tanpa TP, *batch size* yang dapat ditampung GPU tunggal adalah nol. TP membagi alokasi *attention heads* (dan KV Cache terkait) secara proporsional ke seluruh rank.
3. **Pemberantasan Bottleneck Skalabilitas Biaya**:
   Penggunaan Pipeline Parallelism (PP) untuk inferensi interaktif memicu *idle bubbles* tinggi jika kedalaman batch (*concurrency*) rendah. TP memberikan efisiensi komputasi mendekati 100% tanpa *bubble overhead*, menjadikannya standar baku untuk deployment *single-node multi-GPU*.

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut merepresentasikan pemetaan layer transformer menggunakan skema paralelisme Megatron-LM, meminimalkan operasi komunikasi kolektif menjadi hanya dua kali `All-Reduce` per transformer block.

```
                    INPUT ACTIVATION (X)
                             │
            ┌────────────────┴────────────────┐
            ▼                                 ▼
   [ColumnParallelLinear]            [ColumnParallelLinear]
       (W_QKV, Rank 0)                   (W_QKV, Rank 1)
            │                                 │
            ▼                                 ▼
     Local Attention                   Local Attention
      (Heads: 0..H/2-1)                 (Heads: H/2..H-1)
            │                                 │
            ▼                                 ▼
     [RowParallelLinear]               [RowParallelLinear]
        (W_O, Rank 0)                     (W_O, Rank 1)
            │                                 │
            └────────────────┬────────────────┘
                             ▼
                    NCCL ALL-REDUCE (SUM)
                             │
                             ▼  (+) Residual Connection
                      LayerNorm / RMSNorm
                             │
            ┌────────────────┴────────────────┐
            ▼                                 ▼
   [ColumnParallelLinear]            [ColumnParallelLinear]
     (W_Gate/Up, Rank 0)               (W_Gate/Up, Rank 1)
            │                                 │
            ▼ (GELU/SiLU)                     ▼ (GELU/SiLU)
   Intermediate Acts                 Intermediate Acts
            │                                 │
            ▼                                 ▼
     [RowParallelLinear]               [RowParallelLinear]
       (W_Down, Rank 0)                  (W_Down, Rank 1)
            │                                 │
            └────────────────┬────────────────┘
                             ▼
                    NCCL ALL-REDUCE (SUM)
                             │
                             ▼  (+) Residual Connection
                   OUTPUT LAYER TENSOR
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### 5.1 Dekomposisi Matriks Megatron-LM

Transformer block terdiri dari dua sub-layer utama: *Multi-Head Self-Attention* (MHA) dan *Feed-Forward Network* (MLP).

##### 1. MLP Block Decomposition
Diberikan input $X \in \mathbb{R}^{B \times S \times H}$ dan lapisan linear $Y = \text{GeLU}(XW_1)W_2$, dengan $W_1 \in \mathbb{R}^{H \times 4H}$ dan $W_2 \in \mathbb{R}^{4H \times H}$:
* **Column-Parallel Linear ($W_1$)**: Matriks $W_1$ dibelah secara vertikal (sepanjang kolom) menjadi $N$ partisi ($N = \text{TP Size}$):
  $$W_1 = \begin{bmatrix} W_{1,0} & W_{1,1} & \dots & W_{1,N-1} \end{bmatrix}$$
  Setiap rank $i$ menghitung:
  $$Y_{1,i} = \text{GeLU}(X W_{1,i})$$
  Operasi ini tidak memerlukan komunikasi antar-rank karena aktivasi bersifat *element-wise non-linear*.
* **Row-Parallel Linear ($W_2$)**: Matriks $W_2$ dibelah secara horizontal (sepanjang baris):
  $$W_2 = \begin{bmatrix} W_{2,0} \\ W_{2,1} \\ \dots \\ W_{2,N-1} \end{bmatrix}$$
  Setiap rank $i$ menghitung perkalian lokal:
  $$Z_i = Y_{1,i} W_{2,i}$$
  Untuk mendapatkan hasil akhir $Y$, dilakukan akumulasi parsial menggunakan primitif **NCCL All-Reduce (SUM)**:
  $$Y = \sum_{i=0}^{N-1} Z_i = \text{All-Reduce}(Z_i)$$

##### 2. Multi-Head Attention Decomposition
* Matriks proyeksi $W_Q, W_K, W_V$ di-shard menggunakan **Column Parallelism**. Jumlah *attention heads* ($H_{heads}$) harus habis dibagi $N$. Masing-masing GPU memegang subset $H_{heads} / N$ head.
* Komputasi *Scaled Dot-Product Attention* berjalan sepenuhnya independen pada masing-masing rank:
  $$A_i = \text{Softmax}\left(\frac{Q_i K_i^T}{\sqrt{d_k}}\right) V_i$$
* Matriks proyeksi akhir $W_O$ di-shard menggunakan **Row Parallelism**, diikuti oleh **All-Reduce** tunggal untuk menyatukan hasil attention heads sebelum residual addition.

#### 5.2 Analisis Latensi & Volume Komunikasi NCCL

Untuk setiap transformer block, dilakukan **2 kali All-Reduce**.
Pada topologi Ring All-Reduce dengan ukuran tensor aktivasi $M$ elemen (dalam bytes) melintasi $N$ rank:
1. **Reduce-Scatter Phase**: Setiap rank mengirim dan menerima $\frac{N-1}{N} M$ bytes.
2. **All-Gather Phase**: Setiap rank mengirim dan menerima $\frac{N-1}{N} M$ bytes.

Total volume data yang melintasi link per rank adalah:
$$\text{Transfer Size} = 2 \times \left(\frac{N-1}{N}\right) M$$

Untuk input berdimensi Batch Size $B$, Sequence Length $S$, dan Hidden Dimension $H$, menggunakan presisi 16-bit (2 bytes per elemen):
$$M = 2 \cdot B \cdot S \cdot H \text{ bytes}$$

Jika satu model memiliki $L$ transformer layers, total waktu komunikasi inferensi $T_{comm}$ didekati dengan:
$$T_{comm} \approx 2 L \cdot \left( 2 \cdot \alpha + 2 \cdot \left(\frac{N-1}{N}\right) \frac{M}{\beta} \right)$$
Di mana $\alpha$ adalah latensi inisiasi hardware (NVLink/PCIe transit latency), dan $\beta$ adalah bandwidth interkoneksi efektif bus.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi modul Tensor Parallel dari awal menggunakan PyTorch Distributed framework. Kode ini mengabstraksi dekomposisi tensor, isolasi rank, dan primitif NCCL.

```python
"""
distributed_tp_primitives.py
Modul implementasi Tensor Parallelism tingkat produksi berbasis PyTorch Distributed.
"""

from __future__ import annotations
import math
from typing import Optional, Tuple

import torch
import torch.distributed as dist
import torch.nn as nn
import torch.nn.functional as F


class DistributedContextError(RuntimeError):
    """Exception dilempar ketika torch.distributed tidak terinisialisasi dengan benar."""
    pass


def _ensure_distributed_initialized() -> None:
    """Validasi kesiapan backend terdistribusi."""
    if not dist.is_available() or not dist.is_initialized():
        raise DistributedContextError(
            "Backend torch.distributed belum terinisialisasi. "
            "Jalankan aplikasi melalui launcher torchrun atau panggil dist.init_process_group()."
        )


class _CopyToModelParallelRegion(torch.autograd.Function):
    """
    Melewatkan input secara identik pada forward pass (identitas).
    Melakukan All-Reduce pada backward pass (jika digunakan dalam fine-tuning/training).
    """

    @staticmethod
    def forward(ctx, input_: torch.Tensor) -> torch.Tensor:
        return input_

    @staticmethod
    def backward(ctx, grad_output: torch.Tensor) -> torch.Tensor:
        _ensure_distributed_initialized()
        dist.all_reduce(grad_output, op=dist.ReduceOp.SUM)
        return grad_output


class _ReduceFromModelParallelRegion(torch.autograd.Function):
    """
    Melakukan operasi All-Reduce (SUM) pada forward pass untuk mengakumulasi partial sums.
    """

    @staticmethod
    def forward(ctx, input_: torch.Tensor, group: Optional[dist.ProcessGroup] = None) -> torch.Tensor:
        _ensure_distributed_initialized()
        output = input_.clone()
        dist.all_reduce(output, op=dist.ReduceOp.SUM, group=group)
        return output

    @staticmethod
    def backward(ctx, grad_output: torch.Tensor) -> Tuple[torch.Tensor, None]:
        # Dalam backward pass, gradien disebarkan secara identitas
        return grad_output, None


def copy_to_tensor_model_parallel_region(input_: torch.Tensor) -> torch.Tensor:
    return _CopyToModelParallelRegion.apply(input_)


def reduce_from_tensor_model_parallel_region(
    input_: torch.Tensor, group: Optional[dist.ProcessGroup] = None
) -> torch.Tensor:
    return _ReduceFromModelParallelRegion.apply(input_, group)


class ColumnParallelLinear(nn.Module):
    """
    Linear layer dengan sharding bobot sepanjang dimensi kolom (output features).
    W dipecah menjadi: [W_1, W_2, ..., W_N].
    Output: Y_i = X @ W_i.
    """

    def __init__(
        self,
        in_features: int,
        out_features: int,
        bias: bool = True,
        gather_output: bool = False,
        process_group: Optional[dist.ProcessGroup] = None,
        device: Optional[torch.device] = None,
        dtype: Optional[torch.dtype] = None,
    ) -> None:
        super().__init__()
        _ensure_distributed_initialized()

        self.in_features = in_features
        self.out_features = out_features
        self.gather_output = gather_output
        self.process_group = process_group

        self.world_size = dist.get_world_size(group=self.process_group)
        self.rank = dist.get_rank(group=self.process_group)

        if out_features % self.world_size != 0:
            raise ValueError(
                f"out_features ({out_features}) harus habis dibagi world_size ({self.world_size})"
            )

        self.split_out_features = out_features // self.world_size

        # Inisialisasi tensor sharded lokal
        self.weight = nn.Parameter(
            torch.empty(
                (self.split_out_features, in_features),
                device=device,
                dtype=dtype,
            )
        )
        if bias:
            self.bias = nn.Parameter(
                torch.empty(
                    self.split_out_features,
                    device=device,
                    dtype=dtype,
                )
            )
        else:
            self.register_parameter("bias", None)

        self.reset_parameters()

    def reset_parameters(self) -> None:
        """Inisialisasi bobot mengikuti distribusi Kaiming Uniform."""
        nn.init.kaiming_uniform_(self.weight, a=math.sqrt(5))
        if self.bias is not None:
            fan_in, _ = nn.init._calculate_fan_in_and_fan_out(self.weight)
            bound = 1 / math.sqrt(fan_in) if fan_in > 0 else 0
            nn.init.uniform_(self.bias, -bound, bound)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Input dilewatkan secara paralel ke seluruh rank
        input_parallel = copy_to_tensor_model_parallel_region(x)

        # Komputasi lokal: [B, S, in_features] x [split_out_features, in_features]^T
        output_parallel = F.linear(input_parallel, self.weight, self.bias)

        if not self.gather_output:
            return output_parallel

        # Opsional: Gather jika layer ini adalah layer proyeksi terminal (misal: LM Head)
        gathered_list = [torch.empty_like(output_parallel) for _ in range(self.world_size)]
        dist.all_gather(gathered_list, output_parallel, group=self.process_group)
        return torch.cat(gathered_list, dim=-1)


class RowParallelLinear(nn.Module):
    """
    Linear layer dengan sharding bobot sepanjang dimensi baris (input features).
    W dipecah menjadi: [W_1; W_2; ...; W_N].
    Input X_i harus merepresentasikan partial input dari ColumnParallelLinear sebelumnya.
    Hasil parsial diakumulasikan menggunakan All-Reduce (SUM).
    """

    def __init__(
        self,
        in_features: int,
        out_features: int,
        bias: bool = True,
        input_is_parallel: bool = True,
        process_group: Optional[dist.ProcessGroup] = None,
        device: Optional[torch.device] = None,
        dtype: Optional[torch.dtype] = None,
    ) -> None:
        super().__init__()
        _ensure_distributed_initialized()

        self.in_features = in_features
        self.out_features = out_features
        self.input_is_parallel = input_is_parallel
        self.process_group = process_group

        self.world_size = dist.get_world_size(group=self.process_group)
        self.rank = dist.get_rank(group=self.process_group)

        if in_features % self.world_size != 0:
            raise ValueError(
                f"in_features ({in_features}) harus habis dibagi world_size ({self.world_size})"
            )

        self.split_in_features = in_features // self.world_size

        self.weight = nn.Parameter(
            torch.empty(
                (out_features, self.split_in_features),
                device=device,
                dtype=dtype,
            )
        )
        if bias:
            # Bias tidak di-shard; hanya rank 0 yang memegang atau di-add setelah reduksi
            self.bias = nn.Parameter(
                torch.empty(
                    out_features,
                    device=device,
                    dtype=dtype,
                )
            )
        else:
            self.register_parameter("bias", None)

        self.reset_parameters()

    def reset_parameters(self) -> None:
        nn.init.kaiming_uniform_(self.weight, a=math.sqrt(5))
        if self.bias is not None:
            fan_in, _ = nn.init._calculate_fan_in_and_fan_out(self.weight)
            bound = 1 / math.sqrt(fan_in) if fan_in > 0 else 0
            nn.init.uniform_(self.bias, -bound, bound)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if not self.input_is_parallel:
            # Jika input belum di-shard, potong input sesuai rank saat ini
            splits = torch.split(x, self.split_in_features, dim=-1)
            x_parallel = splits[self.rank].contiguous()
        else:
            x_parallel = x

        # Hitung partial matrix multiplication
        output_parallel = F.linear(x_parallel, self.weight, bias=None)

        # Sinkronisasi antar node/GPU menggunakan All-Reduce
        output_ = reduce_from_tensor_model_parallel_region(output_parallel, self.process_group)

        if self.bias is not None:
            return output_ + self.bias
        return output_


class TensorParallelMLP(nn.Module):
    """
    End-to-End Megatron-LM Multi-Layer Perceptron (MLP) block
    Menggabungkan ColumnParallelLinear dan RowParallelLinear.
    """

    def __init__(
        self,
        hidden_size: int,
        intermediate_size: int,
        process_group: Optional[dist.ProcessGroup] = None,
        device: Optional[torch.device] = None,
        dtype: Optional[torch.dtype] = None,
    ) -> None:
        super().__init__()
        self.gate_up_proj = ColumnParallelLinear(
            in_features=hidden_size,
            out_features=intermediate_size,
            bias=False,
            gather_output=False,
            process_group=process_group,
            device=device,
            dtype=dtype,
        )
        self.down_proj = RowParallelLinear(
            in_features=intermediate_size,
            out_features=hidden_size,
            bias=False,
            input_is_parallel=True,
            process_group=process_group,
            device=device,
            dtype=dtype,
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # [B, S, H] -> [B, S, intermediate_size / TP]
        intermediate = F.silu(self.gate_up_proj(x))
        # [B, S, intermediate_size / TP] -> All-Reduce -> [B, S, H]
        output = self.down_proj(intermediate)
        return output
```

#### Driver Script untuk Menguji Validitas Numerik (Run via `torchrun`)

Simpan kode di atas sebagai `tp_core.py` dan jalankan script pengujian berikut menggunakan perintah terminal:
`torchrun --nproc_per_node=2 test_tp.py`

```python
"""
test_tp.py
Verifikasi matematis: Membandingkan single-GPU Dense MLP vs Distributed TP MLP.
"""

import os
import torch
import torch.distributed as dist
from tp_core import TensorParallelMLP


def test_tp_equivalence():
    dist.init_process_group(backend="nccl" if torch.cuda.is_available() else "gloo")
    rank = dist.get_rank()
    world_size = dist.get_world_size()

    device = torch.device(f"cuda:{rank}" if torch.cuda.is_available() else "cpu")
    if torch.cuda.is_available():
        torch.cuda.set_device(device)

    # Konfigurasi Dimensi
    batch_size = 2
    seq_len = 8
    hidden_size = 64
    intermediate_size = 256

    torch.manual_seed(42)

    # Inisialisasi model referensi un-sharded (Golden Reference)
    dense_gate_up = torch.nn.Linear(hidden_size, intermediate_size, bias=False).to(device)
    dense_down = torch.nn.Linear(intermediate_size, hidden_size, bias=False).to(device)

    # Sinkronisasi weight awal di rank 0 ke state TP
    tp_mlp = TensorParallelMLP(
        hidden_size=hidden_size,
        intermediate_size=intermediate_size,
        device=device,
    )

    # Sharding eksplisit dari golden reference ke TP rank
    with torch.no_grad():
        # Shard Column: split intermediate_size sepanjang axis 0
        gate_up_shards = torch.chunk(dense_gate_up.weight.data, world_size, dim=0)
        tp_mlp.gate_up_proj.weight.data.copy_(gate_up_shards[rank])

        # Shard Row: split intermediate_size sepanjang axis 1
        down_shards = torch.chunk(dense_down.weight.data, world_size, dim=1)
        tp_mlp.down_proj.weight.data.copy_(down_shards[rank])

    # Input sintetis sama di semua rank
    x = torch.randn(batch_size, seq_len, hidden_size, device=device)
    dist.broadcast(x, src=0)

    # Forward pass Golden Reference
    with torch.no_grad():
        golden_act = torch.nn.functional.silu(dense_gate_up(x))
        golden_out = dense_down(golden_act)

    # Forward pass TP Model
    with torch.no_grad():
        tp_out = tp_mlp(x)

    # Hitung error deviasi
    max_deviation = torch.max(torch.abs(golden_out - tp_out)).item()
    if rank == 0:
        print(f"Max Absolute Numerical Deviation: {max_deviation:.8e}")
        assert max_deviation < 1e-5, "Validasi gagal: Deviasi numerik melebihi threshold."
        print("Tensor Parallelism Validation: SUKSES (Identik secara matematis).")

    dist.destroy_process_group()


if __name__ == "__main__":
    test_tp_equivalence()
```

---

### 7. Edge Cases & Failure Modes

#### 7.1 Non-Divisible Head/Dimension Layouts
Jika arsitektur model memiliki parameter yang tidak habis dibagi ukuran grup tensor parallel ($H_{heads} \pmod N \neq 0$), alokasi shard tidak seimbang.
* **Kasus Nyata**: Model dengan Multi-Query Attention (MQA) atau Grouped-Query Attention (GQA) seperti Llama-3-70B (memiliki 64 Q-heads dan hanya 8 KV-heads). Jika dieksekusi dengan $TP=16$, pembagian 8 KV heads ke 16 rank memicu *fractional sharding*.
* **Solusi/Mitigasi**: Batasi ukuran $TP \le N_{KV\_heads}$ untuk replikasi KV Cache alami, atau terapkan *Head Replication* di mana KV-heads diduplikasi di antar rank (misal: 2 rank berbagi 1 KV head yang sama).

#### 7.2 NCCL Watchdog Timeouts & Silent Hangs
Pada cluster berskala besar, satu GPU yang mengalami *kernel freeze* atau *memory throttling* (akibat suhu berlebih) menyebabkan seluruh rank lain macet (*blocking*) tanpa batas di baris `dist.all_reduce`.
* **Solusi**: Atur *environment variables* berikut secara ketat di layer orkestrasi:
  ```bash
  export NCCL_ASYNC_ERROR_HANDLING=1
  export TORCH_NCCL_HEARTBEAT_TIMEOUT_SEC=60
  export NCCL_DEBUG=INFO
  export NCCL_DEBUG_SUBSYS=COLL,INIT,ENV
  ```

#### 7.3 Numerical Drift pada FP16/BF16 All-Reduce
Operasi penambahan floating-point bersifat non-asosiatif: $(A + B) + C \neq A + (B + C)$. Pada *Ring All-Reduce*, urutan pengiriman chunk data antar rank bervariasi bergantung pada ukuran cluster.
* **Gejala**: Token logit bergeser beberapa desimal antar ukuran cluster ($TP=2$ vs $TP=8$), menyebabkan *sampling output* divergen.
* **Mitigasi**: Lakukan akumulasi internal reduksi pada presisi tinggi (FP32) di dalam kernel komunikasi kolektif sebelum konversi kembali ke BF16/FP16.

---

### 8. Trade-offs & Alternatif Solusi

| Parameter Evaluasi | Tensor Parallelism (TP) | Pipeline Parallelism (PP) | Context Parallelism (CP) | Data Parallelism (DP/vLLM Replicas) |
| :--- | :--- | :--- | :--- | :--- |
| **Kebutuhan Interkoneksi** | Ekstrem Tinggi (NVLink $\ge 900\text{ GB/s}$) | Rendah-Sedang (PCIe / InfiniBand) | Tinggi (InfiniBand 400G+) | Rendah (Topologi Ethernet Standar) |
| **Profil Latensi (TPOT)** | Minimum (Mempercepat single token) | Buruk (Meningkat linear terhadap layer) | Netral | Tidak mempengaruhi latensi single request |
| **Throughput (Tokens/s)** | Sedang pada concurrency masif | Efisien jika batch queue penuh | Tinggi pada ultra-long context | Maksimum untuk high concurrency |
| **Memory Bubbles** | $0\%$ (Komputasi sinkron) | Tinggi: $\frac{P-1}{P}$ (fase drain/fill) | $0\%$ | $0\%$ |
| **Domain Penerapan** | Single-Node (Intra-Node) | Multi-Node (Cross-Node) | Long-Context Inference | Skalabilitas Beban Kerja Horizontal |

---

### 9. Best Practices & Standard Industri

1. **Prinsip Isolasi Hierarki Jaringan**:
   Jangan pernah merentangkan Tensor Parallelism melintasi antarmuka non-NVLink (misalnya koneksi antar-node melalui Ethernet standar atau PCIe Gen4 tanpa direct P2P). Batasi TP maksimal di dalam batas 1 node fisik (misal: $TP \le 8$ pada host 8x H100). Jika membutuhkan skala lintas node, gabungkan dengan skema Pipeline Parallelism (TP intra-node, PP inter-node).
2. **CUDA Stream Overlapping**:
   Manfaatkan `torch.cuda.Stream` terpisah untuk menyembunyikan latensi All-Reduce di balik kalkulasi layer normalisasi (RMSNorm) atau aktivasi non-dependen (*compute-communication overlap*).
3. **Weight Sharding In-Memory Zero-Copy**:
   Hindari memuat model *unsharded* penuh ke dalam memori setiap worker GPU sebelum memotongnya. Manfaatkan format file *Safetensors* yang dipadukan dengan modul PyTorch `accelerate` (parameter `device_map="meta"`), sehingga proses hanya memuat slice bobot yang relevan bagi rank tersebut ke VRAM.

---

### 10. Hands-on Lab Exercise

#### Skenario Lab
Anda ditugaskan merancang modul **Tensor Parallel Attention (Self-Attention Block)** yang mampu mempartisi matriks Multi-Head Attention ke dalam 2 GPU. Modul ini wajib mereplikasi mekanisme *Grouped-Query Attention* (GQA) secara matematis identik dengan PyTorch Reference standard.

#### Langkah 1: Persiapan Environment
Pastikan runtime memiliki minimal 2 device CUDA (atau gunakan backend CPU fallback `gloo` untuk debugging lokal).
```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

#### Langkah 2: Implementasi Script `lab_tp_attention.py`

```python
"""
lab_tp_attention.py
Implementasi Hands-On: Tensor Parallel Grouped-Query Attention (TP-GQA).
"""

import os
import math
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.distributed as dist
from tp_core import ColumnParallelLinear, RowParallelLinear


class TensorParallelGQA(nn.Module):
    def __init__(
        self,
        hidden_size: int,
        num_heads: int,
        num_kv_heads: int,
        head_dim: int,
        process_group: dist.ProcessGroup = None,
    ):
        super().__init__()
        self.world_size = dist.get_world_size(process_group)
        self.rank = dist.get_rank(process_group)

        self.hidden_size = hidden_size
        self.num_heads = num_heads
        self.num_kv_heads = num_kv_heads
        self.head_dim = head_dim

        # Pastikan head terbagi merata
        assert num_heads % self.world_size == 0
        assert num_kv_heads % self.world_size == 0

        self.num_local_heads = num_heads // self.world_size
        self.num_local_kv_heads = num_kv_heads // self.world_size

        # Column-Parallel: Q, K, V
        self.q_proj = ColumnParallelLinear(
            hidden_size, self.num_heads * head_dim, bias=False, process_group=process_group
        )
        self.k_proj = ColumnParallelLinear(
            hidden_size, self.num_kv_heads * head_dim, bias=False, process_group=process_group
        )
        self.v_proj = ColumnParallelLinear(
            hidden_size, self.num_kv_heads * head_dim, bias=False, process_group=process_group
        )

        # Row-Parallel: O Proj
        self.o_proj = RowParallelLinear(
            self.num_heads * head_dim, hidden_size, bias=False, process_group=process_group
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        B, S, _ = x.shape

        # Step A: Proyeksi Linear Lokal
        q = self.q_proj(x).view(B, S, self.num_local_heads, self.head_dim).transpose(1, 2)
        k = self.k_proj(x).view(B, S, self.num_local_kv_heads, self.head_dim).transpose(1, 2)
        v = self.v_proj(x).view(B, S, self.num_local_kv_heads, self.head_dim).transpose(1, 2)

        # Step B: Ekspansi Head GQA jika num_heads != num_kv_heads
        repeat_factor = self.num_local_heads // self.num_local_kv_heads
        if repeat_factor > 1:
            k = k.repeat_interleave(repeat_factor, dim=1)
            v = v.repeat_interleave(repeat_factor, dim=1)

        # Step C: Scaled Dot-Product Attention
        scale = 1.0 / math.sqrt(self.head_dim)
        scores = torch.matmul(q, k.transpose(-2, -1)) * scale
        probs = F.softmax(scores, dim=-1)
        context = torch.matmul(probs, v)  # [B, local_heads, S, head_dim]

        # Reshape kembali ke format linear: [B, S, local_heads * head_dim]
        context = context.transpose(1, 2).contiguous().view(B, S, -1)

        # Step D: Row-Parallel Output Projection + Akumulasi All-Reduce
        output = self.o_proj(context)
        return output


def run_lab():
    backend = "nccl" if torch.cuda.is_available() else "gloo"
    dist.init_process_group(backend=backend)
    rank = dist.get_rank()
    device = torch.device(f"cuda:{rank}" if torch.cuda.is_available() else "cpu")
    if torch.cuda.is_available():
        torch.cuda.set_device(device)

    # Inisialisasi arsitektur: 8 Q-heads, 2 KV-heads, head_dim 64
    gqa = TensorParallelGQA(
        hidden_size=256,
        num_heads=8,
        num_kv_heads=2,
        head_dim=32,
    ).to(device)

    x = torch.randn(2, 16, 256, device=device)
    dist.broadcast(x, src=0)

    out = gqa(x)

    if rank == 0:
        print(f"[LAB VERIFICATION] Sukses mengeksekusi TensorParallelGQA.")
        print(f"Bentuk Tensor Output: {out.shape} (Ekspektasi: [2, 16, 256])")
        assert out.shape == torch.Size([2, 16, 256])

    dist.destroy_process_group()


if __name__ == "__main__":
    run_lab()
```

#### Langkah 3: Eksekusi dan Verifikasi Evaluasi
Jalankan modul secara paralel pada node Anda:
```bash
torchrun --nproc_per_node=2 lab_tp_attention.py
```

Output yang diharapkan pada konsol terminal:
```text
[LAB VERIFICATION] Sukses mengeksekusi TensorParallelGQA.
Bentuk Tensor Output: torch.Size([2, 16, 256]) (Ekspektasi: [2, 16, 256])
```