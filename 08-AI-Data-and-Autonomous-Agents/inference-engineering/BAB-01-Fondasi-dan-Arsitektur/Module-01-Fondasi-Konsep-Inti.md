# Bab 01: Fondasi Inference Engineering
## Module 01: Anatomi LLM Inference Engine: Prefill, Decode, dan Batasan Hardware (Memory vs Compute Bound)

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis (C4)** profil eksekusi fase *Prefill* dan *Decode* pada arsitektur Transformer decoder-only menggunakan prinsip *Roofline Model*.
- **Mengidentifikasi (C4)** titik transisi operasional sistem inferensi dari kondisi *compute-bound* menuju *memory-bandwidth bound*.
- **Mengembangkan (C3)** simulator estimasi *throughput* dan *memory footprint* KV-Cache untuk mengkalkulasi kebutuhan kapasitas VRAM GPU secara deterministik.
- **Mengevaluasi (C5)** dampak strategi *naive static batching* terhadap latensi *Time-to-First-Token* (TTFT) dan *Time-per-Output-Token* (TPOT).
- **Merancang (C6)** arsitektur inferensi dasar yang memitigasi *GPU Underutilization* akibat memory starvation pada fase autoregresif.

---

### 2. Conceptual Anchor
Bayangkan sistem inferensi LLM sebagai jalur logistik pabrik percetakan buku kustom:
- **Fase Prefill** seperti membaca dan mencerna naskah utuh setebal 100 halaman dalam satu kali sesi penelaahan. Seluruh staf membaca secara simultan (paralelisasi penuh). Mesin bekerja pada kapasitas komputasi penuh (*compute-bound*); mereka tidak menunggu pasokan kertas baru karena naskah masukan sudah tersedia lengkap.
- **Fase Decode** seperti menulis bab sambungan kata demi kata menggunakan pena tinta celup. Setiap satu kata yang ditulis membutuhkan perenungan terhadap seluruh kata yang pernah ditulis sebelumnya (membaca riwayat naskah berulang kali). Penulis menghabiskan 95% waktunya untuk membolak-balik lembaran lama (menarik *KV-Cache* dan bobot model dari VRAM HBM ke register komputasi) hanya untuk menuliskan *satu kata tunggal*. Akibatnya, lengan mekanis kalkulasi (Tensor Core) menganggur hampir sepanjang waktu, menunggu data dikirim melalui jalur pipa bus memori (*memory-bandwidth bound*).

---

### 3. Why This Matters
Dalam ekosistem *serving* Machine Learning konvensional (misalnya ResNet atau BERT untuk klasifikasi), kompleksitas komputasi bersifat statis dan berorientasi *batch-parallel*. Sebaliknya, inferensi Generative LLM memutus paradigma ini melalui algoritma autoregresif:

1. **Finansial & Skalabilitas**: Biaya infrastruktur GPU (seperti NVIDIA H100 atau A100) ditentukan oleh efisiensi utilisasi FLOPs. Pada fase *decode*, GPU modern sering kali hanya beroperasi pada <5% dari total kapasitas TFLOPs teoretisnya karena tercekik oleh batas *bandwidth* memori HBM (High Bandwidth Memory).
2. **Kegagalan Produksi Nyata**: Ketidakmampuan membedakan karakteristik *Prefill* vs *Decode* menyebabkan masalah fatal: *Out-Of-Memory* (OOM) mendadak di tengah generasi token karena pembengkakan KV-Cache, degradasi drastis pada SLA latency p99, dan fenomena *head-of-line blocking* di mana prompt panjang menahan generasi token pendek untuk pengguna lain.

---

### 4. What It Is
Secara formal, **Inference Engineering** pada LLM adalah disiplin optimasi eksekusi model komputasional terdistribusi pada fase operasional pasca-pelatihan, yang berfokus pada minimalisasi latensi, maksimalisasi *throughput*, dan optimasi hierarki memori (SRAM, HBM, PCIe, Host RAM). 

Siklus inferensi terbagi secara matematis menjadi dua tahapan:

$$\text{Total Inference Latency} = T_{\text{prefill}}(S) + \sum_{i=1}^{N} T_{\text{decode}}(S + i)$$

Di mana:
- $S$ = Panjang *context length* (input tokens).
- $N$ = Panjang *generation length* (output tokens).
- $T_{\text{prefill}}$: Mengalikan matriks bobot $W \in \mathbb{R}^{d \times d}$ dengan matriks aktivasi $X \in \mathbb{R}^{S \times d}$. Karena $S > 1$, ini adalah operasi **GEMM** (General Matrix to Matrix Multiplication) dengan rasio komputasi terhadap transfer data (*Arithmetic Intensity*) yang tinggi. Operasi ini **Compute-Bound**.
- $T_{\text{decode}}$: Mengalikan matriks bobot $W \in \mathbb{R}^{d \times d}$ dengan vektor token tunggal $x_t \in \mathbb{R}^{1 \times d}$. Ini adalah operasi **GEMV** (General Matrix to Vector Multiplication). Arithmetic intensity mendekati nol. Operasi ini **Memory-Bandwidth Bound**.

---

### 5. What It Is Not
- **Bukan Model Training**: Pelatihan mengalokasikan memori untuk *optimizer states* (Adam moments), gradien, dan grafik komputasi *backward pass*. Inferensi murni melakukan *forward pass* tanpa *computation graph retention*, tetapi membebankan retensi memori pada *Key-Value (KV) Cache* dinamis.
- **Bukan Model Serving Stateless Standar**: Inferensi LLM bukan sekadar meletakkan model PyTorch di balik endpoint FastAPI. Pendekatan REST API sinkron sederhana tanpa penanganan KV-cache tingkat rendah akan menghasilkan latensi $O(N^2)$ dan alokasi memori yang tidak terkontrol.
- **Bukan Sekadar Kuantisasi**: Kuantisasi (FP8, INT4) hanyalah salah satu instrumen kompresi bobot untuk mengurangi konsumsi memori dan transfer bandwidth; kuantisasi tidak mengubah struktur algoritmik dari pemisahan prefill dan decode.

---

### 6. System Architecture Diagram

Berikut adalah alur eksekusi internal dari inferensi autoregresif pada GPU:

```
[ Incoming Request: Prompt Tokens [t_0, t_1, ..., t_k] ]
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 1. PREFILL PHASE (Context Phase)                            │
│    - Batched parallel token processing                      │
│    - Compute Intensity: HIGH (Arithmetic Bound)             │
│    - Primitive: GEMM (Matrix-Matrix Multiply)               │
│                                                             │
│  [Prompt Tokens] ──► [Q, K, V Projections]                  │
│                             │                               │
│                             ├──────────────┐                │
│                             ▼              ▼                │
│                     [Attention Output]  [Write K, V to HBM] │
│                             │                  │            │
└─────────────────────────────┼──────────────────┼────────────┘
                              │                  │
                              ▼                  ▼
┌─────────────────────────────────────────────────────────────┐
│ GPU HIGH BANDWIDTH MEMORY (HBM)                             │
│ ┌──────────────────────────┐  ┌──────────────────────────┐  │
│ │   Model Weights (FP16)   │  │ Dynamic KV Cache Storage │  │
│ └──────────────────────────┘  └──────────────────────────┘  │
└─────────────────────────────┬──────────────────▲────────────┘
                              │                  │
                              ▼                  │ (Append new K,V)
┌────────────────────────────────────────────────┼────────────┐
│ 2. DECODE PHASE (Autoregressive Token Gen)    │            │
│    - Sequential: 1 token at a time             │            │
│    - Compute Intensity: LOW (Memory Bound)     │            │
│    - Primitive: GEMV (Matrix-Vector Multiply)  │            │
│                                                │            │
│  Input: Token t_n                              │            │
│    │                                           │            │
│    ▼                                           │            │
│  [Compute Q_n, K_n, V_n] ──────────────────────┘            │
│    │                                                        │
│    ▼                                                        │
│  [Read ALL Past K,V from HBM] ──► [Compute Attention Score] │
│                                                │            │
│                                                ▼            │
│                                           [Next Token t_n+1]│
│                                                │            │
│                   Loop until EOS or Max Tokens ┘            │
└─────────────────────────────────────────────────────────────┘
```

---

### 7. Core Mechanics / Internal Workflow

#### Siklus Eksekusi Mesin Inferensi:
1. **Request Ingestion**: Engine menerima sekuens token prompt berukuran $S$.
2. **Context Step (Prefill)**:
   - Token prompt dilewatkan ke embedding layer secara bersamaan.
   - Proyeksi matriks linear menghitung tensor $Q, K, V$ untuk seluruh $S$ token:
     $$Q = X W_Q, \quad K = X W_K, \quad V = X W_V$$
   - Nilai $K$ dan $V$ untuk seluruh $S$ token disimpan ke dalam memori VRAM yang dialokasikan khusus (*KV-Cache*).
   - Logits dihitung untuk memprediksi token pertama hasil generasi ($t_{S+1}$).
3. **Generation Loop (Decode)**:
   - Token terpilih $t_{S+1}$ diumpankan kembali ke model sebagai input tunggal dengan panjang dimensi baris 1.
   - Proyeksi $Q_{\text{new}}, K_{\text{new}}, V_{\text{new}}$ dihitung hanya untuk token tunggal tersebut.
   - $K_{\text{new}}$ dan $V_{\text{new}}$ ditambahkan ke struktur KV-Cache yang ada di HBM.
   - Mesin membaca **seluruh riwayat** $K_{\text{all}}$ dan $V_{\text{all}}$ dari HBM ke dalam SRAM (Register/Shared Memory) GPU untuk menghitung:
     $$\text{Attention}(Q_{\text{new}}, K_{\text{all}}, V_{\text{all}}) = \text{softmax}\left(\frac{Q_{\text{new}} K_{\text{all}}^T}{\sqrt{d_k}}\right) V_{\text{all}}$$
   - Mengambil sampel (*sampling*) token berikutnya ($t_{S+2}$) dari distribusi logits.
   - Langkah ini diulang sampai token *End-Of-Sequence* (EOS) ditemukan atau batasan panjang token maksimum tercapai.

---

### 8. Code Implementation: Simple Case
Implementasi konseptual murni menggunakan PyTorch untuk mengukur perbedaan mendasar antara *Prefill step* (GEMM) dan *Decode step* (GEMV).

```python
import time
import torch

def benchmark_gemm_vs_gemv():
    # Pastikan GPU tersedia
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Executing on: {device}")
    
    hidden_dim = 4096
    context_length = 2048
    dtype = torch.float16 if device.type == "cuda" else torch.float32

    # Simulasi Bobot Linear Projection (misal: QKV projection layer)
    weights = torch.randn(hidden_dim, hidden_dim, device=device, dtype=dtype)

    # 1. PREFILL STAGE: Input berbentuk Matrix (Tokens, Hidden_Dim) -> GEMM
    prompt_input = torch.randn(context_length, hidden_dim, device=device, dtype=dtype)
    
    # Warmup
    for _ in range(5):
        _ = torch.matmul(prompt_input, weights)
    if device.type == "cuda":
        torch.cuda.synchronize()

    start_prefill = time.perf_counter()
    _ = torch.matmul(prompt_input, weights)
    if device.type == "cuda":
        torch.cuda.synchronize()
    prefill_time = time.perf_counter() - start_prefill

    # 2. DECODE STAGE: Input berbentuk Vector (1, Hidden_Dim) -> GEMV
    token_input = torch.randn(1, hidden_dim, device=device, dtype=dtype)

    # Warmup
    for _ in range(5):
        _ = torch.matmul(token_input, weights)
    if device.type == "cuda":
        torch.cuda.synchronize()

    start_decode = time.perf_counter()
    iterations = 100
    for _ in range(iterations):
        _ = torch.matmul(token_input, weights)
    if device.type == "cuda":
        torch.cuda.synchronize()
    decode_time = (time.perf_counter() - start_decode) / iterations

    # Kalkulasi Metrik FLOPs
    # GEMM FLOPs: 2 * M * N * K
    prefill_flops = 2 * context_length * hidden_dim * hidden_dim
    decode_flops = 2 * 1 * hidden_dim * hidden_dim

    print(f"--- Hasil Analisis Matriks ---")
    print(f"Prefill (GEMM) Latency : {prefill_time * 1000:.4f} ms")
    print(f"Prefill Throughput     : {(prefill_flops / prefill_time) / 1e12:.2f} TFLOPs/s")
    print(f"Decode (GEMV) Latency   : {decode_time * 1000:.4f} ms")
    print(f"Decode Throughput      : {(decode_flops / decode_time) / 1e12:.2f} TFLOPs/s")

if __name__ == "__main__":
    benchmark_gemm_vs_gemv()
```

---

### 9. Code Implementation: Production/Realistic Case
Simulator profil memori dan inferensi deterministik yang mengkalkulasi kebutuhan alokasi KV-Cache per request, bandwidth HBM yang dikonsumsi, serta Arithmetic Intensity berdasarkan *Roofline Model*.

```python
from dataclasses import dataclass
from typing import List, Tuple
import math

@dataclass(frozen=True)
class TransformerEngineSpecs:
    model_name: str
    num_layers: int
    hidden_size: int
    num_attention_heads: int
    num_key_value_heads: int  # Grouped-Query Attention support
    bytes_per_param: int      # FP16 = 2, FP8 = 1, INT4 = 0.5
    hbm_bandwidth_gb_s: float # e.g., A100-80GB SXM = 2039 GB/s
    peak_tflops: float        # Peak Half-Precision Tensor Core TFLOPs (e.g., A100 = 312 TFLOPs)

@dataclass
class RequestProfile:
    request_id: str
    prompt_tokens: int
    max_output_tokens: int

class LLMExecutionProfiler:
    def __init__(self, specs: TransformerEngineSpecs):
        self.specs = specs
        self.head_dim = specs.hidden_size // specs.num_attention_heads
        
        # Validasi Grouped-Query Attention (GQA) / Multi-Query Attention (MQA)
        if specs.num_attention_heads % specs.num_key_value_heads != 0:
            raise ValueError("num_attention_heads harus habis dibagi oleh num_key_value_heads.")

    def calculate_kv_cache_bytes_per_token(self) -> int:
        """
        Menghitung kapasitas memori (byte) untuk menyimpan 1 token KV-cache di seluruh layer.
        KV Cache menyimpan 2 tensor: Key dan Value.
        Formula: 2 * num_layers * num_key_value_heads * head_dim * bytes_per_param
        """
        return (
            2 * 
            self.specs.num_layers * 
            self.specs.num_key_value_heads * 
            self.head_dim * 
            self.specs.bytes_per_param
        )

    def calculate_model_weight_bytes(self, total_params_billion: float) -> float:
        """Kapasitas memori dasar hanya untuk menampung bobot model."""
        return total_params_billion * 1e9 * self.specs.bytes_per_param

    def evaluate_roofline(self, batch_size: int, current_context_len: int) -> dict:
        """
        Menganalisis status komputasi: Compute-Bound vs Memory-Bandwidth Bound.
        Menggunakan single decode step.
        """
        # FLOPs untuk Attention Projections + FFN dalam 1 step decode untuk seluruh batch
        # Aproksimasi Transformer standar: ~2 FLOPs per param per token
        # Plus attention over context: 4 * context_len * num_layers * hidden_size
        approx_weights_params = 12 * self.specs.num_layers * (self.specs.hidden_size ** 2)
        flops_weights = 2 * approx_weights_params * batch_size
        flops_attention = 4 * batch_size * current_context_len * self.specs.num_layers * self.specs.hidden_size
        total_flops = flops_weights + flops_attention

        # Transfer Data dari HBM ke SRAM (Bytes):
        # 1. Bobot model harus dibaca seluruhnya sekali per forward pass (jika batch kecil)
        bytes_weights = approx_weights_params * self.specs.bytes_per_param
        # 2. KV Cache yang harus dibaca dari memori untuk context ini
        kv_cache_read_bytes = (
            batch_size * 
            current_context_len * 
            self.calculate_kv_cache_bytes_per_token()
        )
        total_bytes_transferred = bytes_weights + kv_cache_read_bytes

        # Arithmetic Intensity = FLOPs / Byte
        arithmetic_intensity = total_flops / total_bytes_transferred

        # Machine Balance (Inflexion Point pada Roofline Model)
        # Peak FLOPs / Bandwidth = Batas minimal Arithmetic Intensity untuk Compute Bound
        machine_balance = (self.specs.peak_tflops * 1e12) / (self.specs.hbm_bandwidth_gb_s * 1e9)

        is_compute_bound = arithmetic_intensity >= machine_balance

        # Perkiraan batas latensi bawah teoretis (Roofline model limit)
        time_compute = total_flops / (self.specs.peak_tflops * 1e12)
        time_memory = total_bytes_transferred / (self.specs.hbm_bandwidth_gb_s * 1e9)
        theoretical_min_latency_sec = max(time_compute, time_memory)

        return {
            "batch_size": batch_size,
            "context_length": current_context_len,
            "arithmetic_intensity": arithmetic_intensity,
            "machine_balance": machine_balance,
            "operational_regime": "COMPUTE-BOUND" if is_compute_bound else "MEMORY-BOUND",
            "memory_time_pct": (time_memory / theoretical_min_latency_sec) * 100,
            "theoretical_min_latency_ms": theoretical_min_latency_sec * 1000.0
        }

    def simulate_concurrent_requests(
        self, 
        requests: List[RequestProfile], 
        available_vram_gb: float,
        model_size_billion_params: float
    ) -> dict:
        weight_mem_gb = self.calculate_model_weight_bytes(model_size_billion_params) / (1024**3)
        usable_kv_vram_gb = available_vram_gb - weight_mem_gb

        if usable_kv_vram_gb <= 0:
            raise MemoryError(f"VRAM tidak mencukupi untuk memuat bobot model: Butuh {weight_mem_gb:.2f} GB")

        bytes_per_token = self.calculate_kv_cache_bytes_per_token()
        
        # Lacak alokasi puncak
        total_tokens_capacity = (usable_kv_vram_gb * (1024**3)) // bytes_per_token
        current_peak_tokens = sum(r.prompt_tokens + r.max_output_tokens for r in requests)
        peak_kv_usage_bytes = current_peak_tokens * bytes_per_token
        peak_kv_usage_gb = peak_kv_usage_bytes / (1024**3)

        can_safely_host = peak_kv_usage_gb <= usable_kv_vram_gb

        return {
            "model_weight_vram_gb": weight_mem_gb,
            "usable_kv_vram_gb": usable_kv_vram_gb,
            "bytes_per_token_kv": bytes_per_token,
            "system_token_capacity": total_tokens_capacity,
            "requested_peak_tokens": current_peak_tokens,
            "peak_kv_demand_gb": peak_kv_usage_gb,
            "admissible_without_oom": can_safely_host
        }

# ==========================================
# Driver Execution
# ==========================================
if __name__ == "__main__":
    # Llama-3-8B pada 1x NVIDIA A100 (80GB SXM)
    llama3_specs = TransformerEngineSpecs(
        model_name="Meta-Llama-3-8B",
        num_layers=32,
        hidden_size=4096,
        num_attention_heads=32,
        num_key_value_heads=8,  # GQA ratio 4:1
        bytes_per_param=2,       # FP16
        hbm_bandwidth_gb_s=2039.0, # 2.039 TB/s
        peak_tflops=312.0        # FP16 Tensor Core Peak
    )

    profiler = LLMExecutionProfiler(llama3_specs)

    # 1. Hitung Overhead KV Cache
    bytes_per_tok = profiler.calculate_kv_cache_bytes_per_token()
    print(f"Memory KV-Cache per Token: {bytes_per_tok} Bytes ({bytes_per_tok / 1024:.2f} KB)")

    # 2. Analisis Roofline pada Batch Size bervariasi
    print("\n--- Analisis Roofline untuk Single Decode Step (Seq Len: 2048) ---")
    for bs in [1, 4, 16, 64, 256]:
        analysis = profiler.evaluate_roofline(batch_size=bs, current_context_len=2048)
        print(
            f"Batch Size: {bs:3d} | "
            f"Arithmetic Intensity: {analysis['arithmetic_intensity']:6.2f} FLOP/Byte | "
            f"Status: {analysis['operational_regime']} "
            f"(Min Latency: {analysis['theoretical_min_latency_ms']:.3f} ms)"
        )

    # 3. Simulasi Kapasitas Memori Terhadap Konkurensi
    mock_requests = [
        RequestProfile(request_id=f"req_{i}", prompt_tokens=1024, max_output_tokens=512)
        for i in range(32)
    ]
    
    sim_result = profiler.simulate_concurrent_requests(
        requests=mock_requests,
        available_vram_gb=80.0,
        model_size_billion_params=8.0
    )

    print("\n--- Evaluasi Kapasitas VRAM ---")
    print(f"Model Weights Memory      : {sim_result['model_weight_vram_gb']:.2f} GB")
    print(f"Sisa Kapasitas untuk KV   : {sim_result['usable_kv_vram_gb']:.2f} GB")
    print(f"Estimasi Puncak Beban KV  : {sim_result['peak_kv_demand_gb']:.2f} GB")
    print(f"Status Aman (Bebas OOM)   : {sim_result['admissible_without_oom']}")
```

---

### 10. Step-by-Step Code Walkthrough

1. **`TransformerEngineSpecs`**: Struct immutable yang mengisolasi karakteristik mekanis arsitektur model dan spesifikasi fisik akselerator (HBM Bandwidth & TFLOPs). Grouped-Query Attention (GQA) diakomodasi melalui pembagian eksplisit antara `num_attention_heads` dan `num_key_value_heads`.
2. **`calculate_kv_cache_bytes_per_token()`**: 
   - Nilai Key dan Value disimpan untuk setiap layer secara terpisah.
   - Formula: $2 \times \text{layers} \times \text{KV\_heads} \times \text{head\_dim} \times \text{bytes\_per\_dtype}$.
   - Penggunaan GQA (misal Llama-3-8B dengan 8 pasang KV-Heads dibanding 32 Attention-Heads) langsung mereduksi alokasi memori KV-cache sebesar 75% dibanding standar MHA (Multi-Head Attention).
3. **`evaluate_roofline()`**:
   - Menghitung **Arithmetic Intensity** ($\text{FLOPs per Byte}$).
   - `machine_balance` merepresentasikan rasio performa teoretis hardware:
     $$\text{Machine Balance} = \frac{\text{Peak FLOPs/sec}}{\text{Memory Bandwidth (Bytes/sec)}}$$
   - Pada GPU NVIDIA A100, rasio ini adalah $\approx 153$ FLOP/Byte. Jika arithmetic intensity model di bawah 153, GPU berada pada zona **Memory-Bound**. Terlihat pada output eksekusi: Batch size kecil ($BS \in [1, 4, 16]$) menghasilkan intensitas jauh di bawah titik kritis ini. Tensor Cores mengalami starvation (kelaparan data).
4. **`simulate_concurrent_requests()`**:
   - Memisahkan ruang VRAM statis (bobot model) dari memori dinamis (KV-Cache).
   - Memastikan admission control dapat memblokir atau menahan request baru sebelum alokasi token dinamis menembus batas fisik VRAM yang berakibat pada kegagalan sistem (*CUDA Out of Memory crash*).

---

### 11. Anti-Patterns & Pitfalls

#### Anti-Pattern: Full-Context Forward Pass During Generation (No KV-Cache)
Kesalahan fatal para insinyur pemula adalah meregenerasi seluruh representasi matriks dari token $0$ hingga $t$ pada setiap iterasi pembentukan token baru.

```python
# -------------------------------------------------------------
# BAD: Menghitung ulang seluruh konteks dari awal (O(N^2) komputasi dan transfer)
# -------------------------------------------------------------
def bad_autoregressive_generate(model, prompt_tokens, max_gen_len):
    current_tokens = prompt_tokens
    for _ in range(max_gen_len):
        # Full forward pass: model mengevaluasi ulang SELURUH token masa lalu!
        logits = model(current_tokens) 
        next_token = torch.argmax(logits[-1, :], dim=-1, keepdim=True)
        current_tokens = torch.cat([current_tokens, next_token], dim=-1)
    return current_tokens

# -------------------------------------------------------------
# GOOD: Menggunakan Stateful KV Cache (Hanya hitung token terkini: O(1) step latency)
# -------------------------------------------------------------
def good_autoregressive_generate(model, prompt_tokens, max_gen_len):
    # 1. Prefill Step
    logits, kv_cache = model(prompt_tokens, use_cache=True)
    next_token = torch.argmax(logits[-1, :], dim=-1, keepdim=True)
    generated_tokens = [next_token]

    # 2. Decode Steps: Masukan HANYA token tunggal terbaru
    current_token = next_token
    for _ in range(max_gen_len - 1):
        logits, kv_cache = model(current_token, past_key_values=kv_cache, use_cache=True)
        next_token = torch.argmax(logits[-1, :], dim=-1, keepdim=True)
        generated_tokens.append(next_token)
        current_token = next_token
        
    return torch.cat(generated_tokens, dim=-1)
```

**Dampak Kegagalan**: Pendekatan pertama menyebabkan *latency explosion*. Pada panjang konteks 4096 token, forward pass tanpa cache mengharuskan GPU melakukan operasi attention sebesar $\sum_{i=1}^{N} i$, yang menghancurkan throughput serving hingga di bawah $1 \text{ token/detik}$.

---

### 12. Edge Cases & Failure Modes

| Skenario | Dampak Sistem | Akar Masalah (*Root Cause*) | Mitigasi Keteknikan |
| :--- | :--- | :--- | :--- |
| **Prefill Giant Prompt (Contoh: 128k context)** | Latency Spike ekstrem pada seluruh antrean / OOM seketika | Matriks Attention $S \times S$ membutuhkan alokasi memori kuadratik untuk activation intermediate | Terapkan FlashAttention-2/3 (tiling computation di SRAM) dan *Chunked Prefill*. |
| **Batch Imbalance Decode** | Latensi inferensi terkunci pada request paling lambat | Variasi panjang generasi; request pendek selesai tapi slotnya tertahan oleh request panjang (*static batching*) | Migrasi dari Static Batching ke *Continuous/Iteration-level Batching*. |
| **KV-Cache Memory Fragmentation** | CUDA OOM terjadi meskipun total sisa VRAM teoretis masih mencukupi | Pengalokasian array memori contiguous yang gagal menemukan blok memori tak terfragmentasi | Terapkan *PagedAttention* (alokasi KV-cache berbasis halaman memori non-contiguous seperti virtual memory OS). |
| **High Output/Input Ratio Request** | Kapasitas prediksi VRAM meleset, menyebabkan eviksi mendadak | Client meminta `max_tokens` besar namun berhenti lebih awal, atau sebaliknya | Terapkan dynamic slot reservation dengan kuota berbasis token virtual & eviction fallback ke Host CPU RAM. |

---

### 13. Real-World Engineering Scenarios

#### Masalah Produksi:
Sebuah perusahaan analitik hukum menyajikan layanan LLM internal menggunakan model **Llama-3-70B FP16** pada instance node GPU $8\times$ NVIDIA A100 (masing-masing 80GB VRAM, total 640GB VRAM). Saat jam sibuk, sistem mengalami lonjakan drastis pada SLA latency p99 (dari 45 ms/token menjadi 1200 ms/token), diiringi CUDA OOM berkala ketika menangani request dokumen panjang.

#### Analisis Telemetri:
1. **Bobot Model**: $70 \times 10^9 \text{ parameter} \times 2 \text{ byte} = 140 \text{ GB}$. Terdistribusi pada 8 GPU via Tensor Parallelism ($\approx 17.5 \text{ GB}$ per GPU).
2. **Karakteristik Beban Kerja**: Prompt rata-rata: 15,000 token. Jumlah request bersamaan (*concurrency*): 20 request.
3. **Kalkulasi KV-Cache**:
   - Model Llama-3-70B menggunakan Grouped-Query Attention (GQA) dengan 8 KV Heads, `hidden_size` = 8192, 80 layers.
   - Head Dimension: $8192 / 64 = 128$.
   - Cache size per token per request: $2 \times 80 \times 8 \times 128 \times 2 \text{ byte} \approx 327,680 \text{ byte} \approx 320 \text{ KB/token}$.
   - Beban KV-Cache per request pada 15,000 token: $15,000 \times 320 \text{ KB} = 4.8 \text{ GB}$.
   - Total KV-Cache untuk 20 request: $20 \times 4.8 \text{ GB} = 96 \text{ GB}$.
4. **Temuan**: Engine menggunakan sistem alokasi statis linear. Ketika prompt 15k token masuk secara paralel, terjadi fenomena **Prefill Stall**: Seluruh Tensor Cores terkunci memproses context GEMM dari dokumen-dokumen ini, memblokir siklus eksekusi decode token dari puluhan request lain yang sedang aktif (*Head-of-Line Blocking*).

#### Tindakan Arsitektural:
1. **Implementasi Chunked Prefill**: Engine memotong token prefill panjang ke dalam chunk berukuran konstan (misal: 512 token) dan menyisipkannya (*piggyback*) ke dalam siklus Decode batch reguler.
2. **Migrasi Precision KV-Cache ke FP8**: Mengurangi ukuran footprint KV-Cache sebesar 50% ($320 \text{ KB} \to 160 \text{ KB}$ per token), melipatgandakan *headroom* memori bebas dan menurunkan transfer bandwidth dari HBM.

---

### 14. Performance Characteristics & Benchmark

Hubungan antara model Roofline, Arithmetic Intensity, dan pemanfaatan hardware dapat dilihat pada representasi batas teoritis berikut:

```
Arithmetic Intensity (FLOPs/Byte) vs Achieved Performance (TFLOPs)
   Achieved
   TFLOPs
     ▲
 Peak│                             =================== [Compute-Bound Ceiling]
     │                            /
     │                           /
     │                          /
     │                         /
     │                        /
     │                       /
     │                      /
     │                     /
     │                    / ◄── [Inflexion Point: Machine Balance]
     │                   /
     │                  /  
     │                 /
     │                /
     │               /  [Memory-Bandwidth Bound Slope]
     │              /
  0  └─────────────┴──────────────────────────────────────►
     0            150 (A100 Limit)                        Arithmetic Intensity
     
     [Decode Phase]                                       [Prefill Phase]
     Batch Size: 1-16                                     Batch Size: Independent
     Intensitas: ~1-10 FLOPs/Byte                         Intensitas: >100-200 FLOPs/Byte
```

#### Formula Penentu:
$$\text{Time}_{\text{decode\_step}} \approx \frac{\text{Size of Model Weights} + \text{Size of Active KV Cache}}{\text{Memory Bandwidth (HBM)}}$$

Jika model Llama-7B (FP16, 14 GB) dijalankan pada GPU dengan bandwidth 2 TB/s pada batch size 1:
$$\text{Min Step Time} \approx \frac{14 \times 10^9 \text{ Bytes}}{2 \times 10^{12} \text{ Bytes/sec}} = 7 \text{ ms/token} \implies \text{Throughput Maksimum} \approx 142 \text{ token/sec}$$
*Catatan: Throughput ini tidak akan pernah meningkat signifikan hanya dengan menambah TFLOPs GPU tanpa memperlebar bus bandwidth memori.*

---

### 15. Trade-Off Analysis

| Keputusan Desain | Keuntungan (Pros) | Kerugian / Biaya (Cons) | Konteks Penggunaan Ideal |
| :--- | :--- | :--- | :--- |
| **Besar Batch Size (High Concurrency)** | Utilisasi FLOPs Tensor Core tinggi; efisiensi biaya GPU per token optimal (*high throughput*). | Latensi generasi per token (*Time-Per-Output-Token*) memburuk; konsumsi VRAM untuk KV cache melonjak. | Sistem pemrosesan batch offline (evaluasi data, ekstraksi dokumen, labeling). |
| **Kecil Batch Size (Low Concurrency)** | Latensi respons individual sangat rendah; TTFT dan TPOT berada pada ambang batas minimum. | Utilisasi hardware sangat buruk (<5% FLOPs utilization); biaya operasional per request membengkak. | Asisten interaktif pengguna langsung (*real-time conversational agents*). |
| **KV Cache FP8 Quantization** | Memotong konsumsi VRAM KV hingga 50%; menggandakan kapasitas concurrent batch size; bandwidth transfer turun. | Potensi degradasi tipis pada akurasi penalaran konteks panjang (*needle-in-a-haystack* tasks). | Production deployment skala besar dengan dokumen berkonteks menengah ke panjang. |
| **Disaggregated Prefill & Decode Architecture** | Menghilangkan *Head-of-Line blocking*; node prefill dan decode dioptimasi secara terpisah pada level HW. | Kompleksitas arsitektur ekstrem; overhead latensi transfer KV-Cache via jaringan (InfiniBand/RoCE). | Infrastruktur AI Hyperscaler (serving klaster ratusan GPU). |

---

### 16. Verification & Testing Strategy

Pengujian komponen inferensi engine wajib memverifikasi dua hal: kebenaran deterministik dari KV cache dan integritas alokasi memori.

```python
import pytest
import torch
import torch.nn as nn

class MockAttentionWithCache(nn.Module):
    def __init__(self, d_model: int, n_heads: int):
        super().__init__()
        self.d_model = d_model
        self.n_heads = n_heads
        self.head_dim = d_model // n_heads
        self.q_proj = nn.Linear(d_model, d_model, bias=False)
        self.k_proj = nn.Linear(d_model, d_model, bias=False)
        self.v_proj = nn.Linear(d_model, d_model, bias=False)

    def forward(self, x: torch.Tensor, kv_cache: Tuple[torch.Tensor, torch.Tensor] = None):
        # x shape: [batch, seq_len, d_model]
        batch, seq_len, _ = x.shape
        q = self.q_proj(x).view(batch, seq_len, self.n_heads, self.head_dim)
        k = self.k_proj(x).view(batch, seq_len, self.n_heads, self.head_dim)
        v = self.v_proj(x).view(batch, seq_len, self.n_heads, self.head_dim)

        if kv_cache is not None:
            past_k, past_v = kv_cache
            k = torch.cat([past_k, k], dim=1)
            v = torch.cat([past_v, v], dim=1)
        
        new_kv_cache = (k, v)
        # Sederhanakan dot-product attention
        scores = torch.einsum("bqhd,bkhd->bhqk", q, k) / math.sqrt(self.head_dim)
        attn = torch.softmax(scores, dim=-1)
        out = torch.einsum("bhqk,bkhd->bqhd", attn, v).reshape(batch, seq_len, self.d_model)
        return out, new_kv_cache

def test_kv_cache_mathematical_equivalence():
    """
    Memastikan bahwa output decode token ke-N menggunakan KV-cache
    identik dengan komputasi utuh tanpa cache (ground truth).
    """
    torch.manual_seed(42)
    d_model = 64
    n_heads = 4
    layer = MockAttentionWithCache(d_model, n_heads).eval()

    prompt = torch.randn(1, 10, d_model)
    next_token = torch.randn(1, 1, d_model)
    full_sequence = torch.cat([prompt, next_token], dim=1)

    # 1. Ground Truth Run (Tanpa Cache, forward pass penuh pada panjang sekuens 11)
    with torch.no_grad():
        full_out, _ = layer(full_sequence, kv_cache=None)
        ground_truth_token_out = full_out[:, -1:, :]

    # 2. Cached Run (Prefill 10 token, kemudian Decode 1 token berikutnya)
    with torch.no_grad():
        prefill_out, kv_cache = layer(prompt, kv_cache=None)
        decode_out, _ = layer(next_token, kv_cache=kv_cache)

    # Validasi: Output representasi token terakhir harus sama secara numerik
    torch.testing.assert_close(
        decode_out, 
        ground_truth_token_out, 
        rtol=1e-5, 
        atol=1e-5,
        msg="Output token autoregresif dengan KV-Cache melenceng dari Ground Truth forward pass!"
    )

def test_kv_cache_tensor_shapes():
    """Memvalidasi invariansi dimensi tensor pada penyimpanan KV Cache."""
    d_model = 128
    n_heads = 8
    layer = MockAttentionWithCache(d_model, n_heads)
    
    x1 = torch.randn(2, 5, d_model)
    _, kv_cache = layer(x1)
    
    assert kv_cache[0].shape == (2, 5, n_heads, d_model // n_heads)
    
    x2 = torch.randn(2, 1, d_model)
    _, kv_cache_step2 = layer(x2, kv_cache=kv_cache)
    
    assert kv_cache_step2[0].shape == (2, 6, n_heads, d_model // n_heads)
```

---

### 17. Best Practices Checklist

#### Architecture & Design:
- [ ] Model menggunakan **Grouped-Query Attention (GQA)** atau **Multi-Query Attention (MQA)** daripada standard Multi-Head Attention (MHA) untuk memangkas memori KV.
- [ ] Batas *context length* (`max_model_len`) di-*hardcode* berdasarkan perhitungan matematis kapasitas sisa VRAM pada *peak batch size*, bukan diasumsikan dinamis tanpa batas.
- [ ] Pipeline melarang keras pemanggilan fungsi PyTorch `forward()` tanpa parameter flag *cache retention*.

#### Engineering & Code:
- [ ] Menggunakan kernel Attention teroptimasi hardware (*FlashAttention-2/3* atau *FlashDecoding*).
- [ ] Operasi konversi representasi floating-point diarahkan secara eksplisit ke tipe data modern hardware (Bfloat16 atau FP8).
- [ ] Seluruh pre-alokasi tensor memori KV-Cache menggunakan pointer flat memory buffers yang dialokasikan di awal (*pre-allocated memory pools*).

#### Observability & Operations:
- [ ] Pisahkan metrik pemantauan SLA secara ketat: **Time-To-First-Token (TTFT)** untuk fase Prefill, dan **Time-Per-Output-Token (TPOT)** untuk fase Decode.
- [ ] Pantau metrik saturasi: **HBM Memory Bandwidth Utilization %** dan **KV-Cache Pool Utilization %**.
- [ ] Set alarm sistem ketika sisa ruang KV-cache berada di bawah ambang batas $10\%$.

---

### 18. Troubleshooting Runbook

```
Symptom: CUDA Out-Of-Memory (OOM) terjadi sporadis saat melayani inferensi model.
```

#### Langkah Investigasi:
1. **Periksa Snapshot Alokasi PyTorch**:
   Jalankan inspeksi alokasi memori internal CUDA untuk melihat fragmentasi:
   ```bash
   python -c "import torch; print(torch.cuda.memory_summary())"
   ```
2. **Kalkulasi Rasio Prompt vs Output**:
   Analisis log akses produksi. Identifikasi apakah OOM terjadi pada request dengan prompt masukan ekstrem atau generasi token panjang:
   ```bash
   # Ekstrak token metadata dari log server inferensi (contoh format vLLM/TGI)
   grep "avg_prompt_throughput" /var/log/inference_engine.log | tail -n 20
   ```
3. **Audit Ketersediaan HBM untuk KV Pool**:
   Hitung alokasi memori yang dialokasikan di luar bobot model. Pastikan `gpu_memory_utilization` tidak diset ke `1.0` (sisakan minimal $10\%$ untuk aktivasi sementara dan CUDA context runtime overhead).

#### Langkah Pemulihan (Remediation):
1. **Turunkan Maximum Batch Size**: Turunkan parameter `max_num_seqs` atau `max_batch_size` pada engine config sebesar $30\%$.
2. **Aktifkan Context Chunking**: Nyalakan konfigurasi `--enable-chunked-prefill=true` untuk menghindari spike aktivasi GEMM pada input prompt besar.
3. **Hard Cap Max Context**: Batasi `max_model_len` pada gateway reverse-proxy sebelum request mencapai engine backend.

---

### 19. Key Takeaways
- **Dikotomi Inferensi**: Inferensi Transformer LLM tidak homogen; proses terbagi menjadi fase **Prefill** (Compute-Bound, GEMM, pemrosesan paralel konteks) dan fase **Decode** (Memory-Bandwidth Bound, GEMV, autoregresif sequential).
- **Hambatan HBM**: Pada fase decode, Tensor Core GPU menghabiskan mayoritas siklus instruksinya dalam kondisi menganggur (*idle*), menunggu pembacaan bobot model dan riwayat KV-Cache dari HBM. Menambah core komputasi GPU tidak akan meningkatkan throughput generasi token per pengguna tunggal secara signifikan tanpa diimbangi peningkatan kapasitas bandwidth memori.
- **KV-Cache Adalah Kunci Memori**: Pemicu utama OOM pada deployment sistem LLM berskala besar bukanlah ukuran bobot model (yang bernilai statis), melainkan pertumbuhan footprint KV-cache yang bersifat dinamis seiring pertambahan konkurensi request dan panjang generasi sekuens token.

---

### 20. Next Step Bridge
Sekarang Anda telah memahami struktur internal inferensi LLM, profil Roofline model, serta perbedaan radikal antara Prefill dan Decode. 

Namun, bagaimana cara kita menyimpan dan mengelola KV-cache ratusan request secara efisien di dalam VRAM tanpa mengalami fragmentasi memori yang berujung OOM? Kita akan membedah arsitektur internal manajemen memori modern pada **Bab 01 Module 02: Mekanisme dan Optimasi KV-Cache: Multi-Head, Multi-Query, Grouped-Query Attention, & PagedAttention**.