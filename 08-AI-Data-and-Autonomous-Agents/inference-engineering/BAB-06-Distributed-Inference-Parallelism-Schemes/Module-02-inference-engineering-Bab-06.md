# BAB-06: Distributed Inference & Parallelism Schemes
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. **Merancang & Mengimplementasikan Skema 3D/4D Parallelism** (Tensor, Pipeline, Sequence, dan Expert Parallelism) secara *bare-metal* menggunakan PyTorch Distributed & CUDA IPC primitives untuk *serving* model LLM/MoE skala besar.
2. **Menganalisis Overhead Komunikasi NCCL** (`All-Reduce`, `All-Gather`, `Reduce-Scatter`, `All-to-All`) berdasarkan topologi hardware (NVLink, NVSwitch, PCIe Gen5, InfiniBand/RoCEv2) dan meminimalkannya via *Compute-Communication Overlapping*.
3. **Mengoptimasi Distribusi KV Cache** pada topologi terdistribusi guna menghindari OOM (*Out-Of-Memory*) serta menjaga *Inter-Token Latency* (ITL) dan *Time-To-First-Token* (TTFT) di bawah SLA produksi.
4. **Mendiagnosis dan Memperbaiki Kegagalan Sistem Terdistribusi** seperti *NCCL Deadlock*, *CUDA Stream desynchronization*, *straggler nodes*, dan ketimpangan alokasi beban pada *Mixture-of-Experts* (MoE) *routing*.

---

### 2. Prerequisite
Sebelum mendalami modul ini, Anda wajib menguasai:
* Arsitektur Transformer tingkat lanjut: Multi-Head Attention (MHA), Grouped-Query Attention (GQA), Rotary Position Embeddings (RoPE), SwiGLU MLP.
* Dasar Pemrograman PyTorch Distributed (`torch.distributed`, Process Groups, *ranks*, *world size*).
* Model komputasi akselerator: CUDA Streams, CUDA Events, Unified Memory, dan arsitektur *memory hierarchy* GPU (HBM3/3e, SRAM/Shared Memory, L2 Cache).
* Protokol interkoneksi data center: PCI Express switches, NVLink interconnect bandwidth, InfiniBand Subnet Management, RDMA / GPUDirect RDMA.

---

### 3. Concept & Internal Architecture

Model skala ratusan miliar parameter (seperti Llama-3-70B/405B, DeepSeek-V3) tidak dapat dimuat ke dalam VRAM satu GPU (misal: NVIDIA H100 80GB SXM5). Lebih dari itu, beban komputasi dan *KV Cache footprint* untuk *context length* panjang (32k–128k+) membutuhkan orkestrasi paralel lintas multi-GPU dan multi-node.

```
+---------------------------------------------------------------------------------------------------+
|                                      DISTRIBUTED INFERENCE TOPOLOGY                               |
|                                                                                                   |
|  [Data/Sequence Parallelism: Inter-Node / RoCEv2 / InfiniBand (400-800 Gbps)]                     |
|  Node 0                                                 Node 1                                    |
|  +-----------------------------------+                  +-----------------------------------+     |
|  | [Pipeline Parallelism: Stage 0]   |  P2P (Activations) | [Pipeline Parallelism: Stage 1]   |     |
|  | GPU 0 <---NVLink---> GPU 1        | =================> | GPU 4 <---NVLink---> GPU 5        |     |
|  |   ^                    ^          |   (RDMA Send/Recv) |   ^                    ^          |     |
|  |   | NVLink             | NVLink   |                    |   | NVLink             | NVLink   |     |
|  |   v                    v          |                    |   v                    v          |     |
|  | GPU 2 <---NVLink---> GPU 3        |                    | GPU 6 <---NVLink---> GPU 7        |     |
|  | [Tensor Parallelism: TP=4]        |                    | [Tensor Parallelism: TP=4]        |     |
|  +-----------------------------------+                  +-----------------------------------+     |
+---------------------------------------------------------------------------------------------------+
```

#### A. Tensor Parallelism (TP) - Megatron-LM Style
Tensor Parallelism memecah bobot matriks layer individual (Linear, Attention, MLP) ke beberapa GPU dalam node yang sama (Intra-Node) yang terhubung interkoneksi berkecepatan sangat tinggi (NVLink $\ge 900\text{ GB/s}$).

1. **Column Parallel Linear (CPL):** Matriks bobot $W \in \mathbb{R}^{d_{in} \times d_{out}}$ dipecah secara vertikal menjadi $W = [W_1 \mid W_2 \mid \dots \mid W_k]$. Input $X$ disalin identik ke setiap GPU (broadcast).
   $$Y_i = X W_i \quad \implies \quad Y = [Y_1 \mid Y_2 \mid \dots \mid Y_k]$$
2. **Row Parallel Linear (RPL):** Matriks bobot $W \in \mathbb{R}^{d_{in} \times d_{out}}$ dipecah secara horizontal menjadi:
   $$W = \begin{bmatrix} W_1 \\ W_2 \\ \dots \\ W_k \end{bmatrix}$$
   Input $X$ dipecah per rank: $X = [X_1 \mid X_2 \mid \dots \mid X_k]$. Setiap GPU menghitung perkalian parsial:
   $$Y_i = X_i W_i \quad \implies \quad Y = \sum_{i=1}^k Y_i = \text{All-Reduce-Sum}(Y_i)$$

Dalam sebuah blok Transformer klasik, layer disusun berpasangan untuk meminimalkan *collective communications*:
* **Attention Block:** Proyeksi $W_q, W_k, W_v$ menggunakan Column Parallel, sedangkan Proyeksi Output $W_o$ menggunakan Row Parallel. Komunikasi `All-Reduce` hanya dieksekusi **satu kali** di akhir layer $W_o$.
* **MLP Block:** Proyeksi Gate/Up menggunakan Column Parallel, Proyeksi Down menggunakan Row Parallel. Komunikasi `All-Reduce` hanya dieksekusi **satu kali** di akhir Down Projection.

#### B. Pipeline Parallelism (PP)
Pipeline Parallelism memecah layer-layer model secara sekuensial antar grup GPU (biasanya antar node):
* GPU 0 menampung Layer $0 \dots L/N - 1$
* GPU 1 menampung Layer $L/N \dots 2L/N - 1$
* Komunikasi antar stage murni point-to-point (P2P via `NCCL Send/Recv`).
* **Bubble Overhead:** Pipeline konvensional menyebabkan latensi *idle* tinggi. Pada moda *batching inference*, kita menerapkan skema mikro-batching (*1F1B - One Forward One Backward* atau *Forward-only pipelining*).
  $$\text{Bubble Fraction } F_{bubble} = \frac{p - 1}{m + p - 1}$$
  di mana $p$ adalah jumlah pipeline stage, dan $m$ adalah jumlah micro-batch. Untuk *inference online* dengan batch size kecil, PP murni menambah latency per token (ITL) secara drastis, sehingga PP di produksi umumnya hanya digunakan untuk *throughput-oriented batch inference* atau jika model terlalu raksasa bahkan setelah TP=8 diterapkan (misal Llama-3-405B di mana TP=8, PP=8).

#### C. Sequence Parallelism (SP) & Context Parallelism (CP)
Jika context length mencapai puluhan ribu token, *activation memory* dan komputasi MHA mendominasi VRAM.
1. **DeepSpeed Ulysses:**
   * Sequence token dipecah merata ke seluruh GPU: masing-masing GPU memegang $S/P$ token dengan seluruh *attention heads*.
   * Sebelum komputasi Attention, dieksekusi `All-to-All` collective untuk menukar dimensi sequence dan head: dari $(B, S/P, H, D)$ menjadi $(B, S, H/P, D)$.
   * Komputasi MHA/FlashAttention dieksekusi secara lokal pada subset head untuk seluruh panjang sequence.
   * Setelah Attention, dilakukan `All-to-All` kedua untuk mengembalikan layout tensor ke $(B, S/P, H, D)$.
2. **Ring-Attention:**
   * Block sequence didistribusikan. Matriks Query $Q$ tetap di GPU lokal, sementara Key $K$ dan Value $V$ ditransfer melingkar (*ring P2P*) antar GPU secara asinkron tumpang tindih (*overlap*) dengan komputasi inner product attention. Mengeliminasi batas ukuran sequence hingga skala jutaan token.

#### D. Expert Parallelism (EP) pada Mixture-of-Experts (MoE)
Pada model MoE (Mixtral, DeepSeek), layer MLP digantikan oleh sejumlah *experts* (misal 8 hingga 256 experts).
* Token dilewatkan ke Router/Gating Network untuk memilih top-$k$ expert.
* Setiap GPU meng-host subset *experts* lokal.
* Komunikasi:
  1. `All-to-All (Dispatch)`: Mengirimkan embedding token dari GPU asal ke GPU yang memegang expert terpilih.
  2. Komputasi lokal: Expert memproses token yang dialokasikan padanya.
  3. `All-to-All (Combine)`: Mengirimkan kembali aktivasi output expert ke GPU asal untuk diakumulasi/dibobot berdasarkan router logits.

---

### 4. Why & What

| Dimensi | Mengapa Dibutuhkan di Skala Produksi? | Apa Karakteristik Kunci & Bottleneck-nya? |
| :--- | :--- | :--- |
| **Tensor Parallelism (TP)** | Mengurangi latensi komputasi GEMM linear layer secara linier untuk 1 request. | **Bottleneck: Bandwidth Jaringan.** Sangat sensitif terhadap latency komunikasi. Wajib berada pada domain NVLink ($>900\text{ GB/s}$). Tidak boleh melewati PCIe atau Ethernet biasa karena *All-Reduce stall*. |
| **Pipeline Parallelism (PP)** | Memungkinkan agregasi ratusan GB VRAM melintasi batas node fisik tanpa membutuhkan bus NVLink super lebar antar rak. | **Bottleneck: Idle Bubble & Inter-Node Latency.** Meningkatkan *latency-per-token* (ITL). Membutuhkan *Micro-batching* dinamis untuk mempertahankan utilisasi FLOPs. |
| **Sequence Parallelism (SP/CP)**| Menangani *prompt context* ekstrim ($128\text{k}+$) yang membuat single-GPU OOM akibat ukuran matriks aktivasi dan KV cache. | **Bottleneck: All-to-All / Ring P2P bandwidth.** Mengurangi ukuran alokasi KV cache per GPU sebanding dengan world size sequence. |
| **Expert Parallelism (EP)** | Meningkatkan kapasitas parameter total secara eksponensial tanpa menambah FLOPs komputasi per token secara proporsional. | **Bottleneck: Token Load Imbalance & All-to-All Skew.** Jika beberapa expert menjadi *hotspot*, GPU penampung expert tersebut menjadi *straggler* yang menahan seluruh cluster. |

---

### 5. How (Workflow Detail)

Alur komputasi Forward Pass satu Token (Autoregressive Decode Step) pada arsitektur hybrid **TP=4 (Intra-Node) + PP=2 (Inter-Node)**:

```
[Client Token Query]
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│ PIPELINE STAGE 0 (Node 0: GPU 0, 1, 2, 3)                   │
│                                                             │
│ 1. Input Embedding Lookup                                   │
│ 2. Broadcast Token ke rank TP 0..3                          │
│                                                             │
│ Loop Layer 0 s.d. (L/2 - 1):                                │
│   a. Q, K, V Projection (Column Parallel)                   │
│   b. KV Cache Lookup & Update (Lokal per TP-Head)           │
│   c. Flash-Decoding Attention Kernel                        │
│   d. Out Projection (Row Parallel)                          │
│   e. NCCL All-Reduce (Sum) Activations                      │
│   f. Gate + Up Projection MLP (Column Parallel)             │
│   g. Down Projection MLP (Row Parallel)                     │
│   h. NCCL All-Reduce (Sum) Activations                      │
│                                                             │
│ 3. Extract Activation Boundary Tensor                       │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               │ P2P RDMA Send/Recv (Inter-Node)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ PIPELINE STAGE 1 (Node 1: GPU 4, 5, 6, 7)                   │
│                                                             │
│ 4. Terima Tensor Boundary                                   │
│                                                             │
│ Loop Layer (L/2) s.d. (L - 1):                              │
│   [Proses TP yang identik dengan Stage 0]                   │
│                                                             │
│ 5. Final LayerNorm & Unembedding Head                       │
│ 6. Sampling / Argmax Token Generation                       │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
                        [Generated Token]
```

---

### 6. Analogy & Diagram ASCII

#### A. Analogi Pabrik Manufaktur Pesawat
Bayangkan memproduksi pesawat komersial:
* **Tensor Parallelism (TP):** Memotong sayap pesawat menjadi 4 bagian. Empat teknisi mengelas masing-masing potongan secara bersamaan di meja yang sama. Karena mereka berada berdampingan (NVLink), mereka bisa berteriak satu sama lain secara instan untuk mencocokkan baut (*All-Reduce* berulang kali dalam hitungan mikrodetik).
* **Pipeline Parallelism (PP):** Sistem ban berjalan multi-ruangan. Ruang A merakit rangka dasar, Ruang B memasang interior, Ruang C memasang mesin. Mobil derek memindahkan bodi dari Ruang A ke Ruang B (*P2P Activation Transfer*). Jika Ruang A lambat, Ruang B duduk diam (*Pipeline Bubble*).
* **Expert Parallelism (EP):** Sistem konsultasi spesialis. Pasien (token) datang ke resepsionis (Router), lalu dikirim ke dokter spesialis jantung, paru, atau ortopedi (*All-to-All Dispatch*). Dokter memeriksa (*local compute*), lalu mengirimkan hasilnya kembali ke meja farmasi (*All-to-All Combine*).

#### B. Diagram Komunikasi Matriks Megatron-LM Attention
```
Input X ───┬───> [ W_q1,k1,v1 ] ───> Local MHA ───> [ W_o1 ] ───┐
(Shape:    │     (GPU 0)                            (GPU 0)      │
 [B, S, D])├───> [ W_q2,k2,v2 ] ───> Local MHA ───> [ W_o2 ] ───┼──> All-Reduce ──> Layer Output
           │     (GPU 1)                            (GPU 1)      │    (SUM)            (Shape:
           └───> [ W_q3,k3,v3 ] ───> Local MHA ───> [ W_o3 ] ───┘    NCCL Ring        [B, S, D])
                 (GPU 2)                            (GPU 2)
                 |============= COLUMN ============| |=== ROW ===|
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Megatron-Style TP Primitives
Implementasi PyTorch dari primitive *Column Parallel* dan *Row Parallel* dengan *custom autograd function* untuk komunikasi NCCL manual:

```python
import os
import torch
import torch.distributed as dist
import torch.nn as nn

class _CopyToModelParallelRegion(torch.autograd.Function):
    @staticmethod
    def forward(ctx, input_):
        return input_

    @staticmethod
    def backward(ctx, grad_output):
        # Pada backward pass, copy diubah menjadi all-reduce
        dist.all_reduce(grad_output)
        return grad_output

class _ReduceFromModelParallelRegion(torch.autograd.Function):
    @staticmethod
    def forward(ctx, input_):
        # Mengakumulasi output parsial dari row-parallel ranks
        dist.all_reduce(input_, op=dist.ReduceOp.SUM)
        return input_

    @staticmethod
    def backward(ctx, grad_output):
        return grad_output

class ColumnParallelLinear(nn.Module):
    def __init__(self, in_features: int, out_features: int, world_size: int, rank: int):
        super().__init__()
        self.in_features = in_features
        self.out_features = out_features
        self.world_size = world_size
        self.rank = rank
        self.split_out_features = out_features // world_size

        # Inisialisasi slice bobot untuk rank lokal
        self.weight = nn.Parameter(torch.empty(self.split_out_features, in_features))
        nn.init.kaiming_uniform_(self.weight, a=5**0.5)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        input_parallel = _CopyToModelParallelRegion.apply(x)
        output_parallel = torch.matmul(input_parallel, self.weight.t())
        return output_parallel

class RowParallelLinear(nn.Module):
    def __init__(self, in_features: int, out_features: int, world_size: int, rank: int):
        super().__init__()
        self.in_features = in_features
        self.out_features = out_features
        self.world_size = world_size
        self.rank = rank
        self.split_in_features = in_features // world_size

        # Inisialisasi slice bobot untuk rank lokal
        self.weight = nn.Parameter(torch.empty(out_features, self.split_in_features))
        nn.init.kaiming_uniform_(self.weight, a=5**0.5)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x diasumsikan sudah terpecah pada dimensi terakhir sesuai split_in_features
        output_parallel = torch.matmul(x, self.weight.t())
        output_ = _ReduceFromModelParallelRegion.apply(output_parallel)
        return output_
```

#### B. Practical Enterprise-Grade Example: Hybrid TP+PP Distributed Inference Engine
Implementasi production-grade dari modul Transformer Layer terdistribusi dengan penanganan KV Cache sharding, ring micro-benchmarking, dan eksekusi non-blocking via CUDA Streams:

```python
import os
import torch
import torch.distributed as dist
import torch.nn as nn
from typing import Optional, Tuple

class DistributedAttentionConfig:
    def __init__(
        self,
        hidden_size: int = 4096,
        num_attention_heads: int = 32,
        num_key_value_heads: int = 8,
        head_dim: int = 128,
        tp_world_size: int = 1,
        tp_rank: int = 0,
    ):
        self.hidden_size = hidden_size
        self.num_heads = num_attention_heads
        self.num_kv_heads = num_key_value_heads
        self.head_dim = head_dim
        self.tp_world_size = tp_world_size
        self.tp_rank = tp_rank

        assert num_attention_heads % tp_world_size == 0, "Heads harus habis dibagi TP size"
        assert num_key_value_heads % tp_world_size == 0, "KV Heads harus habis dibagi TP size"

        self.local_heads = num_attention_heads // tp_world_size
        self.local_kv_heads = num_key_value_heads // tp_world_size

class EnterpriseDistributedMHA(nn.Module):
    """
    Multi-Head Attention Terdistribusi dengan Sharded KV-Cache
    Mendukung Tensor Parallelism Megatron-LM Style.
    """
    def __init__(self, config: DistributedAttentionConfig):
        super().__init__()
        self.cfg = config
        self.comm_stream = torch.cuda.Stream()

        # Proyeksi Q, K, V secara kolom paralel
        q_dim = self.cfg.local_heads * self.cfg.head_dim
        kv_dim = self.cfg.local_kv_heads * self.cfg.head_dim

        self.q_proj = nn.Linear(self.cfg.hidden_size, q_dim, bias=False)
        self.k_proj = nn.Linear(self.cfg.hidden_size, kv_dim, bias=False)
        self.v_proj = nn.Linear(self.cfg.hidden_size, kv_dim, bias=False)

        # Proyeksi Output secara row paralel
        self.o_proj = nn.Linear(self.cfg.local_heads * self.cfg.head_dim, self.cfg.hidden_size, bias=False)

    def forward(
        self,
        x: torch.Tensor,
        kv_cache: Optional[Tuple[torch.Tensor, torch.Tensor]] = None,
        layer_past_len: int = 0
    ) -> Tuple[torch.Tensor, Tuple[torch.Tensor, torch.Tensor]]:
        """
        Input x: [batch_size, seq_len, hidden_size]
        """
        bsz, seq_len, _ = x.shape

        # 1. Proyeksi Linier Lokal
        q = self.q_proj(x)
        k = self.k_proj(x)
        v = self.v_proj(x)

        # 2. Reshape ke format [B, H_local, S, D]
        q = q.view(bsz, seq_len, self.cfg.local_heads, self.cfg.head_dim).transpose(1, 2)
        k = k.view(bsz, seq_len, self.cfg.local_kv_heads, self.cfg.head_dim).transpose(1, 2)
        v = v.view(bsz, seq_len, self.cfg.local_kv_heads, self.cfg.head_dim).transpose(1, 2)

        # 3. Manajemen KV Cache Sharded Lokal
        if kv_cache is not None:
            past_k, past_v = kv_cache
            k = torch.cat([past_k, k], dim=2)
            v = torch.cat([past_v, v], dim=2)
        new_kv_cache = (k, v)

        # 4. GQA Expansion lokal jika num_kv_heads < num_heads
        if self.cfg.local_kv_heads != self.cfg.local_heads:
            n_rep = self.cfg.local_heads // self.cfg.local_kv_heads
            k_expanded = k.repeat_interleave(n_rep, dim=1)
            v_expanded = v.repeat_interleave(n_rep, dim=1)
        else:
            k_expanded = k
            v_expanded = v

        # 5. Scaled Dot-Product Attention Lokal
        scale = 1.0 / (self.cfg.head_dim ** 0.5)
        scores = torch.matmul(q, k_expanded.transpose(-2, -1)) * scale

        # Masking kausal jika prefill phase
        if seq_len > 1:
            mask = torch.triu(torch.full((seq_len, seq_len), float('-inf'), device=x.device), diagonal=1)
            scores = scores + mask

        attn_probs = torch.softmax(scores, dim=-1, dtype=torch.float32).to(x.dtype)
        attn_out = torch.matmul(attn_probs, v_expanded) # [B, H_local, S, D]

        # 6. Permute & Row-Parallel Linear
        attn_out = attn_out.transpose(1, 2).contiguous().view(bsz, seq_len, -1)
        local_output = self.o_proj(attn_out)

        # 7. Asynchronous NCCL All-Reduce pada Dedicated Stream
        if self.cfg.tp_world_size > 1:
            torch.cuda.current_stream().synchronize()
            with torch.cuda.stream(self.comm_stream):
                dist.all_reduce(local_output, op=dist.ReduceOp.SUM)
            torch.cuda.current_stream().wait_stream(self.comm_stream)

        return local_output, new_kv_cache

class PipelineStageRuntime:
    """
    Runtime untuk mengelola passing aktivasi P2P antar stage pipeline.
    """
    def __init__(self, stage_id: int, num_stages: int, peer_rank_prev: int, peer_rank_next: int):
        self.stage_id = stage_id
        self.num_stages = num_stages
        self.peer_prev = peer_rank_prev
        self.peer_next = peer_rank_next

    def recv_activations(self, shape: Tuple[int, ...], dtype: torch.dtype, device: torch.device) -> torch.Tensor:
        if self.stage_id == 0:
            raise ValueError("Stage 0 tidak menerima input dari rank pipeline sebelumnya!")
        tensor = torch.empty(shape, dtype=dtype, device=device)
        dist.recv(tensor, src=self.peer_prev)
        return tensor

    def send_activations(self, tensor: torch.Tensor):
        if self.stage_id == self.num_stages - 1:
            raise ValueError("Stage terakhir tidak mengirimkan aktivasi ke rank berikutnya!")
        dist.send(tensor.contiguous(), dst=self.peer_next)
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Serving Llama-3-70B pada Cluster 8x H100 SXM5 (Single Node) vs 2-Node 16x L40S (PCIe)

* **Skenario:** Sebuah perusahaan perbankan tier-1 menerapkan asisten virtual analitik dokumen dengan target SLA:
  * Time-To-First-Token (TTFT) $\le 200\text{ ms}$ untuk prompt 8k token.
  * Inter-Token Latency (ITL) $\le 25\text{ ms/token}$.
  * Concurrency: 64 concurrent streams.

* **Eksperimen Topologi & Analisis Bottleneck:**

1. **Kluster A: 8x H100 80GB SXM5 (Interkoneksi: NVLink 900 GB/s bidirectional)**
   * Skema: Pure Tensor Parallelism (TP = 8).
   * Bobot FP8 = ~70 GB. Terbagi 8 GPU = ~8.75 GB bobot per GPU.
   * Sisanya ~71 GB VRAM per GPU dialokasikan secara penuh untuk Paged KV Cache.
   * Komunikasi: Ring All-Reduce 70B layer ($d_{model} = 8192$) menghasilkan ukuran tensor aktivasi per layer:
     $$\text{Volume} = 2 \times \frac{P - 1}{P} \times (B \times 1 \times D) \times 2\text{ bytes} \approx 2 \times \frac{7}{8} \times (64 \times 1 \times 8192) \times 2 \approx 1.83\text{ MB per layer}$$
     Pada kecepatan bus NVLink 900 GB/s, waktu transfer komunikasi murni:
     $$T_{comm} \approx \frac{1.83\text{ MB}}{900\text{ GB/s}} \approx 2.03\text{ }\mu\text{s}$$
   * **Hasil:** ITL tercapai di angka **11.4 ms/token**. TTFT pada prompt 8k tercapai di **142 ms**. SLA terpenuhi dengan margin aman.

2. **Kluster B: 2-Node 16x L40S 48GB (Interkoneksi Inter-Node: RoCEv2 100 Gbps, Intra-Node: PCIe Gen4 x16 @ 32 GB/s, No NVLink)**
   * Kesalahan Awal: Tim engineering mencoba TP=8 melintasi 2 node (TP Inter-Node).
   * Jaringan 100 Gbps (12.5 GB/s) langsung saturasi:
     $$T_{comm} \approx \frac{1.83\text{ MB}}{12.5\text{ GB/s}} \approx 146.4\text{ }\mu\text{s per layer}$$
     Dikalikan 80 layer = penambahan latency murni dari network mencapai $> 11.7\text{ ms}$ hanya untuk All-Reduce tanpa komputasi. Akibat *tail latency* jitter jaringan ethernet, ITL melonjak ke **68 ms/token** (SLA Gagal!).
   * **Solusi Arsitektur Ulang:**
     * Mengisolasi TP di dalam satu node: Node 0 memegang Layer 0–39 (TP=4 PCIe), Node 1 memegang Layer 40–79 (TP=4 PCIe).
     * Menerapkan Pipeline Parallelism (PP=2) antar kedua node.
     * Komunikasi antar node hanya terjadi satu kali per token via P2P Transfer tensor aktivasi ($B \times 1 \times D \approx 1\text{ MB}$), bukan 160 kali per token.
     * **Hasil Akhir Pasca-Fix:** ITL turun menjadi **23.8 ms/token** (SLA Terpenuhi di ambang batas).

---

### 9. Trade-offs

```
                    LATENCY (TTFT & ITL)
                           ▲
                           │  TP (Tensor Parallel)
                           │  (High Comm BW, Low Latency)
                           │
                           │         SP (Sequence Parallel)
                           │
      ─────────────────────┼─────────────────────► THROUGHPUT
                           │                       (Tokens/sec Cluster)
                           │   PP (Pipeline Parallel)
                           │   DP (Data Parallel / vLLM Replicas)
                           │
                           ▼
                    SCALABILITY / HARDWARE COST
```

| Parallelism Scheme | Keuntungan Utama | Kerugian Utama | Batasan Skalabilitas (*Scaling Ceiling*) | Impact pada KV Cache |
| :--- | :--- | :--- | :--- | :--- |
| **Tensor Parallelism (TP)** | Latensi decode per token berkurang drastis; memori bobot terbagi rata. | Beban frekuensi komunikasi sangat tinggi; sensitif terhadap latensi mikrodetik. | Terbatas pada Intra-node NVLink Domain ($N \le 8$ GPU, max 16 pada Grace Hopper Superchip). | Sharded secara proporsional terhadap *number of heads* ($H / TP$). |
| **Pipeline Parallelism (PP)** | Bandwidth interkoneksi yang dibutuhkan rendah; efisien untuk scale-out antar rak. | *Pipeline bubble* membuang cycle komputasi; latensi per-request membengkak secara linier terhadap stage. | $P \le 8$; jika lebih, bubble overhead mendominasi kecuali micro-batch sangat masif. | Setiap stage hanya menyimpan KV cache untuk layer yang dimilikinya. |
| **Sequence Parallelism (SP)** | Menghilangkan limitasi OOM pada prompt super panjang ($>64\text{k}$). | Memerlukan sinkronisasi `All-to-All` tambahan di setiap layer attention. | Terbatas oleh skala pembagian head ($H$) atau latensi Ring Attention. | KV Cache terbagi secara temporal/sekuensial lintas rank. |
| **Expert Parallelism (EP)** | Memperbesar jumlah parameter aktif tanpa lonjakan FLOPs proporsional. | *Token Routing Imbalance* menyebabkan beberapa GPU idle sementara GPU lain bottleneck. | Terbatas oleh jumlah expert ($E$) dan bandwidth network `All-to-All`. | Tidak mempengaruhi KV cache secara langsung (KV cache ada di dense attention). |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Kesalahan Alokasi GQA pada Tensor Parallelism
* **Gejala:** Runtime crash dengan error: `RuntimeError: Number of KV heads (8) must be divisible by TP size (16)`.
* **Akar Masalah:** Mencoba menggunakan $TP > \text{Number of KV Heads}$. Model modern seperti Llama-3-70B memiliki 64 Q-heads dan hanya 8 KV-heads. Jika diset $TP = 16$, KV head tidak bisa dipecah secara integer tanpa replikasi.
* **Solusi:**
  1. Batasi $TP \le 8$.
  2. Jika membutuhkan cluster 16 GPU, gunakan kombinasi **TP=8, PP=2** atau **TP=8, DP=2**.
  3. Terapkan *KV Head Duplication* (mereplikasi 8 KV heads ke 16 rank, konsekuensi overhead VRAM KV cache ganda).

#### 2. NCCL Deadlock Akibat Unsynchronized Barrier di Conditional Branch
* **Gejala:** Cluster inference mengalami *hang* total tanpa pesan error, utilisasi GPU 100%, tetapi tidak ada token yang keluar.
* **Akar Masalah:** Satu rank mengeksekusi collective operation (`dist.all_reduce`) di dalam blok `if rank == 0:`, sementara rank lain mengeksekusi instruksi berbeda tanpa menyentuh collective tersebut.
* **Diagnosa & Solusi:**
  * Jalankan dengan environment variable debug:
    ```bash
    export NCCL_DEBUG=INFO
    export NCCL_DEBUG_SUBSYS=COLL,P2P
    export TORCH_DISTRIBUTED_DEBUG=DETAIL
    ```
  * Pastikan seluruh collective primitives dieksekusi secara simetris oleh **seluruh anggota Process Group** terkait.

#### 3. Host-to-Device Synchronization Stalls pada PyTorch Distributed
* **Gejala:** Throughput *stagnan* di angka rendah meskipun GPU Compute Engine (Tensor Cores) tercatat memiliki SM Utilization tinggi pada `nvidia-smi`.
* **Akar Masalah:** Terdapat pemanggilan instruksi yang memaksa sinkronisasi CPU-GPU implisit di tengah loop decode (misal: `.item()`, `.cpu()`, atau print tensor loss/tokens).
* **Solusi:** Hapus seluruh instruksi sinkronisasi CPU. Gunakan pinned memory buffer dan asinkron ring buffers untuk mengambil output logits/token ID dari GPU ke host.

---

### 11. Best Practices (Production Checklist)

- [ ] **Validasi Topologi P2P Hardware:** Jalankan tes bandwidth sebelum meluncurkan serving engine:
  ```bash
  nccl-tests/build/all_reduce_perf -b 8M -e 1G -f 2 -g 8
  ```
  Pastikan *Bus Bandwidth* NVLink $\ge 350\text{ GB/s}$ (SXM4) atau $\ge 750\text{ GB/s}$ (SXM5/H100).
- [ ] **Isolasi Topology TP ke Socket / NUMA Node Identik:** Hindari traversal data melalui QPI/UPI CPU bridges. Kunci worker processes ke NUMA socket yang sesuai:
  ```bash
  numactl --cpunodebind=0 --membind=0 python serving_worker.py --gpu 0,1,2,3
  ```
- [ ] **Optimalisasi Environment Variable NCCL:**
  ```bash
  export NCCL_BUFFSIZE=8388608         # 8MB chunk buffer untuk saturasi PCIe/NVLink
  export NCCL_NET_GDR_LEVEL=5          # Akselerasi GPUDirect RDMA level penuh
  export CUDA_DEVICE_MAX_CONNECTIONS=1 # Memastikan overlapping streams berjalan deterministic
  ```
- [ ] **KV Cache Zero-Copy Sharding:** Shard KV cache secara native pada alokator blok memory (seperti algoritma PagedAttention). Hindari komputasi attention di format sequence lalu di-gather; selalu pertahankan KV cache tetap sharded di masing-masing rank TP.
- [ ] **Tuning Heterogen:** Jika terpaksa menggunakan multi-node tanpa InfiniBand, gunakan **TP hanya di intra-node** dan gunakan **Pipeline Parallelism atau Data Parallelism antar-node**.

---

### 12. Hands-on Practice

Simulasikan dan ukur secara empiris penalti latensi Tensor Parallelism vs Single GPU execution. Buat script pengujian pada direktori `hands-on/m02/`.

#### Langkah 1: Setup Workspace & Script Implementasi
Simpan kode berikut sebagai `hands-on/m02/tp_bench.py`:

```python
import os
import time
import torch
import torch.distributed as dist
import torch.nn as nn

class BenchColumnParallel(nn.Module):
    def __init__(self, in_features, out_features, world_size):
        super().__init__()
        self.split_out = out_features // world_size
        self.weight = nn.Parameter(torch.randn(self.split_out, in_features, device="cuda"))

    def forward(self, x):
        return torch.matmul(x, self.weight.t())

class BenchRowParallel(nn.Module):
    def __init__(self, in_features, out_features, world_size):
        super().__init__()
        self.split_in = in_features // world_size
        self.weight = nn.Parameter(torch.randn(out_features, self.split_in, device="cuda"))

    def forward(self, x):
        local_out = torch.matmul(x, self.weight.t())
        dist.all_reduce(local_out, op=dist.ReduceOp.SUM)
        return local_out

def run_bench():
    dist.init_process_group("nccl")
    rank = dist.get_rank()
    world_size = dist.get_world_size()
    torch.cuda.set_device(rank)

    B, S, D = 16, 2048, 8192
    x = torch.randn(B, S, D, device="cuda", dtype=torch.float16)

    col = BenchColumnParallel(D, D * 4, world_size).half()
    row = BenchRowParallel(D * 4, D, world_size).half()

    # Warmup
    for _ in range(10):
        mid = col(x)
        out = row(mid)
    torch.cuda.synchronize()

    # Benchmark Loop
    iters = 100
    start = time.perf_counter()
    for _ in range(iters):
        mid = col(x)
        out = row(mid)
    torch.cuda.synchronize()
    end = time.perf_counter()

    avg_time = ((end - start) / iters) * 1000
    if rank == 0:
        print(f"[SUCCESS] TP Size: {world_size} | Execution Time per Forward Pass: {avg_time:.3f} ms")
    
    dist.destroy_process_group()

if __name__ == "__main__":
    run_bench()
```

#### Langkah 2: Eksekusi Multi-GPU dengan `torchrun`
Jalankan benchmark pada 2 GPU lokal (atau 4/8 GPU jika tersedia):
```bash
torchrun --nproc_per_node=2 hands-on/m02/tp_bench.py
```

---

### 13. Exercise

#### Level Easy
Hitung ukuran alokasi VRAM (dalam Megabytes) untuk KV Cache satu request dengan *sequence length* = 4096 token pada model Llama-3-8B ($L=32, H_{kv}=8, D_{head}=128$) jika disimpan dalam format FP16:
1. Pada Single GPU.
2. Pada Cluster dengan Tensor Parallelism $TP=4$.

#### Level Medium
Sebuah node memiliki 8 GPU terhubung via PCIe Gen4 switch (bandwidth inter-GPU $32\text{ GB/s}$ bidirectional, tanpa NVLink). Anda diminta menjalankan inference model dengan dimensi hidden $D = 8192$ dan batch size decode $B = 32$.
Hitung theoretical communication overhead (dalam mikrodetik) untuk mengeksekusi **satu** layer `All-Reduce` sum pada:
1. $TP = 4$
2. $TP = 8$
Jelaskan mengapa performa $TP = 8$ justru berpotensi lebih lambat daripada $TP = 4$ pada bus non-NVLink.

#### Level Hard
Rancang pseudocode atau script PyTorch untuk implementasi **DeepSpeed Ulysses All-to-All Dispatcher**. Model memiliki 8 Attention Heads secara global. Skrip harus mampu:
1. Membagi input sequence berukuran $S=8192$ token ke 4 GPU ($S/P = 2048$).
2. Menggunakan fungsi `torch.distributed.all_to_all_single` untuk menukar layout memori sehingga setiap GPU memegang 2 Attention Heads penuh untuk seluruh $S=8192$ token.
3. Mengembalikan layout tensor pasca komputasi attention ke format sharded sequence semula.

---

### 14. Challenge

**Skenario Sistem:**
Anda diangkat sebagai Lead Inference Architect pada platform *frontier AI*. Anda ditugaskan merancang kluster inference untuk melayani model MoE masif: **DeepSeek-V3** (671 Miliar total parameter, 37 Miliar parameter aktif per token, 256 Routed Experts + 1 Shared Expert, Multi-Head Latent Attention - MLA).

**Spesifikasi Hardware Kluster yang Disediakan:**
* 4 Node Server, masing-masing berisi 8x NVIDIA H100 80GB SXM5.
* Total GPU: 32 GPU.
* Inter-Node Network: 4x 400 Gbps InfiniBand (RoCEv2 / CX7).
* Intra-Node Network: NVLink Switch System (900 GB/s per GPU).

**Tantangan Arsitektur:**
1. Rancang arsitektur paralelisme hibrida (tentukan kombinasi dimensi $TP$, $PP$, $EP$, dan $CP/SP$). Berikan justifikasi berbasis matematika kapasitas memori (bobot + KV cache untuk 64 concurrent users @ 32k context window) dan bandwidth bottleneck antar bus.
2. Bagaimana strategi Anda mengatasi *Expert Imbalance Straggler Problem* jika 80% token routed secara konvergen hanya ke 4 expert spesifik yang kebetulan berada di Node 0?
3. Rancang skema mitigasi kegagalan (*fault recovery*) jika 1 GPU di Node 3 mengalami *thermal throttling* mendadak atau *PCIe uncorrectable error* tanpa merusak batch inference state yang sedang berjalan.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda)

1. Pada Megatron-LM style Tensor Parallelism, collective communication apa yang dipanggil pada akhir komputasi Row Parallel Linear Layer?
   * A. All-Gather
   * B. Reduce-Scatter
   * C. All-Reduce (SUM)
   * D. Broadcast
   * *Kunci Jawaban: C*
   * *Penjelasan:* Row Parallel memecah bobot berdasarkan dimensi input dan melakukan reduksi penjumlahan (`All-Reduce-Sum`) dari hasil perkalian parsial setiap rank untuk menghasilkan nilai aktivasi akhir yang identik di semua rank.

2. Mengapa Pipeline Parallelism (PP) kurang disukai untuk melayani *online real-time single-query inference* dibandingkan Tensor Parallelism (TP)?
   * A. PP membutuhkan kapasitas VRAM 10x lebih banyak dari TP.
   * B. PP menimbulkan bubble idle time yang tinggi dan menambah latensi transfer inter-node linier terhadap stage.
   * C. PP tidak mendukung model attention modern seperti GQA.
   * D. PP hanya bisa bekerja pada GPU AMD ROCm.
   * *Kunci Jawaban: B*
   * *Penjelasan:* Pada single-query, micro-batching tidak efektif sehingga setiap stage pipeline harus menunggu komputasi stage sebelumnya secara sekuensial, menghasilkan *bubble* masif dan meningkatkan Inter-Token Latency.

3. Komunikasi All-to-All pada DeepSpeed Ulysses Sequence Parallelism bertujuan untuk:
   * A. Mengirimkan bobot model dari RAM CPU ke VRAM GPU.
   * B. Mengubah layout tensor dari sharded sequence (dimensi S terpecah) menjadi sharded heads (dimensi Attention Head terpecah).
   * C. Melakukan sinkronisasi gradient parameter optimasi model.
   * D. Melakukan broadcast token ID ke seluruh antrean client.
   * *Kunci Jawaban: B*
   * *Penjelasan:* DeepSpeed Ulysses membagi urutan token pada awal layer, lalu melakukan pertukaran dimensi via `All-to-All` agar Attention kernel lokal dapat memproses *full sequence context* pada subset *head* yang dimiliki masing-masing GPU.

4. Apa dampak utama dari $TP > 1$ terhadap KV Cache footprint per individual GPU?
   * A. Footprint KV Cache meningkat sebanding kuadrat TP size.
   * B. Footprint KV Cache per GPU berkurang sebanding $1 / TP$ selama jumlah head habis dibagi TP.
   * C. Footprint KV Cache konstan dan tidak terpengaruh oleh TP.
   * D. Footprint KV Cache berpindah sepenuhnya ke NVMe storage.
   * *Kunci Jawaban: B*
   * *Penjelasan:* Attention heads dibagi rata ke seluruh rank TP, sehingga setiap rank hanya perlu mengalokasikan dan memelihara KV cache untuk head lokal yang menjadi tanggung jawabnya.

5. Interkoneksi hardware minimum yang direkomendasikan untuk skema Tensor Parallelism skala 8 GPU adalah:
   * A. PCIe Gen3 x8
   * B. Gigabit Ethernet Switch
   * C. NVLink / NVSwitch
   * D. USB 4.0 Type-C bus
   * *Kunci Jawaban: C*
   * *Penjelasan:* TP menjalankan 2 collective `All-Reduce` di setiap layer Transformer. Latensi jaringan non-NVLink (seperti PCIe biasa atau Ethernet) akan mendominasi dan menyebabkan *pipeline stalls*.

---

#### Bagian 2: Intermediate (Analisis Konsep)

6. Jelaskan perbedaan mendasar antara *Ring-Attention* dan *DeepSpeed Ulysses* dalam menangani sequence panjang puluhan ribu token!
   * *Jawaban Model:* Ulysses membagi urutan token dan menukar tensor dimensi menjadi *head-parallel* menggunakan `All-to-All`, yang membutuhkan *all-to-all crossbar communication* berkecepatan tinggi tetapi memanfaatkan kernel FlashAttention standar secara lokal. Ring-Attention tidak mengubah layout head, melainkan mentransfer Key-Value block secara berputar (*ring-topology P2P*) sembari melakukan komputasi overlap attention block-by-block, sehingga lebih skalabel pada cluster inter-node berkecepatan lebih rendah dan sequence jutaan token.

7. Hitung rasio *pipeline bubble* $F_{bubble}$ jika model dieksekusi dengan $P=4$ pipeline stage dan micro-batching $m=12$!
   * *Jawaban Model:*
     $$F_{bubble} = \frac{P - 1}{m + P - 1} = \frac{4 - 1}{12 + 4 - 1} = \frac{3}{15} = 0.20 \implies 20\%$$
     Artinya, 20% dari total runtime GPU berada dalam keadaan *idle* (tidak melakukan kalkulasi).

8. Mengapa pada model dengan Grouped-Query Attention (GQA) seperti Mistral ($H_q=32, H_{kv}=8$), penerapan $TP=8$ lebih optimal dibanding $TP=16$?
   * *Jawaban Model:* Karena $TP=8$ membagi 8 KV-heads tepat menjadi 1 KV-head per rank GPU ($8/8=1$). Jika $TP=16$, $8 \pmod{16} \ne 0$, sehingga memerlukan head duplication atau padding yang memboroskan alokasi memori dan siklus komputasi yang tidak seimbang (*uneven sharding*).

9. Apa fungsi dari pemisahan CUDA Stream (Compute Stream vs Communication Stream) pada implementasi distributed layer?
   * *Jawaban Model:* Memisahkan stream memungkinkan kernel komputasi matriks (GEMM) pada token saat ini dieksekusi secara konkuren (*overlapping*) bersamaan dengan transfer data aktivasi/collective NCCL token lain melalui direct memory access (DMA/RDMA), sehingga latency transfer jaringan dapat disembunyikan (*hidden communication overhead*).

10. Sebutkan akar penyebab dari error NCCL `unhandled system error / connection reset by peer` pada eksekusi inference cluster multi-node!
    * *Jawaban Model:* Umumnya disebabkan oleh timeout pada salah satu rank (misal: satu GPU mengalami memory paging stall atau compilation overhead yang lama), alokasi virtual memory exhaustion (OOM), kegagalan link kabel InfiniBand/RoCE, atau mismatch setting subnet IP adapter jaringan antar node (`NCCL_SOCKET_IFNAME`).

---

#### Bagian 3: Production Case Scenarios

11. **Skenario 1:** Cluster inference Anda memiliki 8x GPU H100. Saat melayani model Llama-3-70B dengan $TP=8$, Anda mendapati bahwa pada fase prefill (prompt 4096 token), GPU core utilization sangat tinggi (>90%), tetapi pada fase decode (menghasilkan token satu per satu), SM utilization merosot drastis hingga <25% meskipun request throughput tinggi.
    * **Pertanyaan:** Apa penyebab anomali utilisasi ini dan arsitektur parallelism apa yang harus dimodifikasi?
    * *Solusi & Analisis:*
      * **Penyebab:** Decode phase bersifat *memory-bandwidth bound* (GEMV: matrix-vector multiplication), bukan *compute-bound*. Menjalankan $TP=8$ pada decode dengan token per rank yang sangat kecil menyebabkan transfer latency All-Reduce mendominasi waktu siklus dibandingkan waktu eksekusi kernel matematika.
      * **Modifikasi Arsitektur:** Ubah skema menjadi **Chunked Prefill + Disaggregated Serving** (Memisahkan kluster Prefill dan kluster Decode). Pada kluster Decode, gunakan $TP=2$ atau $TP=4$ dengan Data Parallelism/Pipeline Parallelism lebih tinggi guna meningkatkan ukuran batch per rank decode agar Tensor Core terutilisasi penuh.

12. **Skenario 2:** Anda menjalankan inference pada model MoE 8x7B menggunakan $EP=8$ pada satu node 8x GPU. Hasil monitoring menunjukkan GPU 2 dan GPU 5 selalu memiliki VRAM usage 98% dan suhu 10°C lebih tinggi, sedangkan GPU sisanya berada pada VRAM 60% dan sering idle. Akibatnya, seluruh inference cluster mengalami pelambatan parah.
    * **Pertanyaan:** Apa fenomena yang sedang terjadi dan bagaimana teknik mitigasi produksinya?
    * *Solusi & Analisis:*
      * **Penyebab:** Terjadi **Expert Routing Collapse / Load Imbalance**. Gating network secara konsisten memilih expert yang kebetulan dialokasikan pada GPU 2 dan 5 untuk domain query pengguna saat itu, menjadikan kedua GPU tersebut bottleneck (*straggler*), sementara GPU lain terpaksa menunggu sinkronisasi All-to-All.
      * **Mitigasi:**
        1. Terapkan *Expert Capacity Factor* (membatasi jumlah token maksimum yang dapat diterima oleh satu expert; token berlebih dialihkan via residual bypass connection).
        2. Terapkan *Dynamic Expert Replication* (menggandakan replika expert populer pada GPU lain yang sedang idle).
        3. Terapkan *Hierarchical Gating Balancing* pada layer proxy router.

13. **Skenario 3:** Tim Anda mengimplementasikan Pipeline Parallelism $PP=4$ melintasi 4 server yang terhubung via Switch Ethernet 10Gbps standar. P2P communication dieksekusi menggunakan standard TCP socket. Latency per token tercatat sebesar $350\text{ ms}$, jauh melampaui baseline target $30\text{ ms}$.
    * **Pertanyaan:** Mengapa latency meningkat secara destruktif dan langkah migrasi infrastruktur apa yang wajib diambil?
    * *Solusi & Analisis:*
      * **Penyebab:** Bandwidth 10Gbps (~1.25 GB/s) sangat lambat untuk streaming aktivasi tensor boundary, ditambah latency switching TCP/IP stack di kernel OS CPU (~50–100 mikrodetik per packet transfer) dan overhead copy *Host-to-Device* (GPU $\leftrightarrow$ CPU RAM $\leftrightarrow$ NIC).
      * **Langkah Migrasi:**
        1. Ganti infrastruktur jaringan dengan fabric minimal **100/400 Gbps InfiniBand atau RoCEv2**.
        2. Aktifkan **GPUDirect RDMA (GDR)** agar transfer aktivasi P2P dilakukan langsung antar VRAM GPU melintasi PCI bridge dan NIC tanpa menyentuh CPU memory host.
        3. Aktifkan kernel overlap pipelining untuk menyembunyikan sisa waktu transfer di balik komputasi micro-batch sebelumnya.

---

### 16. Summary

* **Tensor Parallelism (TP)** merupakan teknik pemecahan matriks bobot layer intra-node terbaik untuk memangkas latensi eksekusi *per-request*, namun mensyaratkan bandwidth interkoneksi super tinggi (NVLink) akibat eksekusi collective `All-Reduce` secara repetitif di setiap blok layer.
* **Pipeline Parallelism (PP)** membagi model secara partisi layer antar stage (cocok untuk scale-out antar node berkecepatan sedang), namun menghasilkan *bubble latency overhead* yang wajib dikompensasi dengan penjadwalan *micro-batching* dinamis.
* **Sequence Parallelism (SP/CP)** membagi dimensi panjang token (seperti DeepSpeed Ulysses dan Ring-Attention) guna menembus limitasi VRAM aktivasi dan KV-cache pada input berukuran ekstrem puluhan hingga ratusan ribu token.
* **Expert Parallelism (EP)** menjadi standar wajib pada model Mixture-of-Experts (MoE) modern, yang memposisikan sub-komputasi ke masing-masing host expert via komunikasi *All-to-All*, membutuhkan penanganan ketat terhadap *token routing load imbalance*.
* Arsitektur inference enterprise modern berskala frontier hampir selalu mengombinasikan skema-skema tersebut (**Hybrid 3D/4D Parallelism**) yang disesuaikan secara presisi terhadap hierarki fisik hardware: **TP & SP intra-node (NVLink), PP & EP inter-node (InfiniBand RDMA)**.