# BAB 06: Natural Language Processing & Large Language Models
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis dan Memitigasi Bottleneck Memori GPU:** Menghitung kebutuhan VRAM untuk *KV Cache*, *activation memory*, dan *model weights* secara presisi matematis pada berbagai presisi numerik ($FP16$, $BF16$, $INT8$, $FP8$, $INT4$).
- **Mengimplementasikan Arsitektur Serving Modern:** Mengonfigurasi dan mengoperasikan *inference engine* berbasis *PagedAttention*, *Continuous Batching*, dan *Chunked Prefill* menggunakan vLLM atau TensorRT-LLM.
- **Mengeksekusi Distributed Training & Fine-Tuning Skala Besar:** Mengimplementasikan *Parameter-Efficient Fine-Tuning* (PEFT/QLoRA) yang terintegrasi dengan *FlashAttention-2/3*, *Gradient Checkpointing*, dan *Fully Sharded Data Parallel* (FSDP / DeepSpeed ZeRO-3).
- **Membangun Arsitektur LLM Gateway Enterprise:** Merancang topologi sistem produksi dengan latensi rendah yang mencakup *Semantic Caching*, *Dynamic Speculative Decoding*, *NeMo Guardrails*, serta observabilitas metrik $TTFT$ (*Time-To-First-Token*) dan $TPOT$ (*Time-Per-Output-Token*).

---

### 2. Prerequisites
Sebelum mempelajari modul ini, Anda wajib menguasai:
- **Arsitektur Transformer Lanjutan:** Mekanika internal *Multi-Head Attention* (MHA), *Multi-Query Attention* (MQA), *Grouped-Query Attention* (GQA), dan *Rotary Position Embedding* (RoPE).
- **Sistem Komputasi Akselerator:** Pemahaman hierarki memori GPU NVIDIA (SRAM vs HBM), CUDA *streams*, *Tensor Cores*, serta konsep *Memory-Bound* vs *Compute-Bound* (Roofline Model).
- **Tooling & Frameworks:** PyTorch 2.x (Distributed Communication `torch.distributed`, NCCL), Hugging Face (`transformers`, `accelerate`, `peft`), dan Docker/Kubernetes dasar.

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1 Anatomi Memori GPU pada Inferensi LLM
Konsumsi VRAM pada eksekusi LLM terbagi menjadi tiga komponen utama:
1. **Model Weights:** Bobot statis model. Untuk model dengan parameter $P$:
   $$\text{VRAM}_{\text{weights}} = P \times \text{bytes per parameter}$$
   Contoh: Model $70\text{B}$ parameter pada $FP16$ (2 byte) membutuhkan $140\text{ GB}$ VRAM murni hanya untuk bobot.
2. **KV Cache:** Menyimpan matriks *Key* ($K$) dan *Value* ($V$) dari token sebelumnya untuk mencegah komputasi ulang selama fase *autoregressive decoding*.
   $$\text{KV Cache Size per Token} = 2 \times n_{\text{layers}} \times n_{\text{kv\_heads}} \times d_{\text{head}} \times \text{bytes per element}$$
   Total memori untuk *batch size* $b$ dan panjang konteks $s$:
   $$\text{Total KV Cache} = b \times s \times \left( 2 \times n_{\text{layers}} \times n_{\text{kv\_heads}} \times d_{\text{head}} \times \text{precision\_bytes} \right)$$
3. **Activation Memory:** Alokasi dinamis sementara untuk *intermediate tensors* selama *forward pass*. Dengan implementasi *FlashAttention*, kompleksitas memori aktivasi tereduksi dari $\mathcal{O}(s^2)$ menjadi $\mathcal{O}(s)$.

```
+-----------------------------------------------------------------------+
|                         Total GPU VRAM (HBM)                          |
+-----------------------------------+-----------------------------------+
|            Static VRAM            |           Dynamic VRAM            |
+-----------------+-----------------+-----------------+-----------------+
| Model Weights   | CUDA Context &  | KV Cache        | Temporary       |
| (FP16/BF16/AWQ) | Driver Runtime  | (PagedAttention)| Activations     |
+-----------------+-----------------+-----------------+-----------------+
```

#### 3.2 PagedAttention & Continuous Batching
Inference server konvensional mengalokasikan memori KV cache secara berurutan (*contiguous*) berdasarkan panjang sekuens maksimum ($s_{\text{max}}$). Hal ini menyebabkan:
- **Internal Fragmentation:** Ruang kosong yang dialokasikan tetapi tidak pernah digunakan karena respons berhenti lebih awal ($< s_{\text{max}}$).
- **External Fragmentation:** Alokasi memori bervariasi yang membuat alokator CUDA gagal mengalokasikan blok besar berurutan meskipun total memori bebas mencukupi.

**PagedAttention** memecahkan masalah ini dengan mengadopsi konsep *Virtual Memory Paging* dari Sistem Operasi:
- KV cache dipecah menjadi blok-blok berukuran tetap (*block size*, misal: 16 atau 32 token).
- Alokasi blok tidak harus berurutan secara fisik di HBM; tabel blok (*Block Table*) memetakan indeks token logis ke alamat blok fisik.
- Fitur *Copy-on-Write* (CoW) memungkinkan *parallel sampling* dan *beam search* berbagi blok fisik yang sama hingga terjadi proses divergensi token.

```
Logical KV Cache (Request A):
[Token 0-15] -> [Token 16-31] -> [Token 32-47]
      |               |                |
      v               v                v
Physical Memory (Non-contiguous HBM Blocks):
Block 42        Block 108        Block 07
```

**Continuous (Iteration-Level) Batching:**
Alih-alih menunggu seluruh sekuens dalam satu *batch* selesai melakukan generasi (*Request-level batching* yang memicu *Head-of-Line Blocking*), *Continuous Batching* menjalankan penjadwalan di setiap iterasi token tunggal. Ketika sebuah sekuens mencapai token `<eos>`, posisinya di *batch* langsung digantikan oleh *request* baru yang berada di antrean.

#### 3.3 Parallelism Strategies
Untuk model yang tidak muat dalam satu GPU (misal: Llama-3-70B pada GPU 24GB atau 80GB):
- **Tensor Parallelism (TP):** Membagi matriks bobot layer ($W_Q, W_K, W_V$ dan $W_{\text{gate}}, W_{\text{up}}, W_{\text{down}}$) secara intra-node melintasi GPU via NVLink menggunakan operasi *Row-Parallel* dan *Column-Parallel* yang disinkronisasi melalui primitif komunikasi `All-Reduce`.
- **Pipeline Parallelism (PP):** Membagi *layer-by-layer* melintasi GPU atau antar-node via network InfiniBand/RoCE. Rentan terhadap *pipeline bubble* yang harus diminimalisasi menggunakan skema penjadwalan 1F1B (*One Forward, One Backward*).

---

### 4. Why & What
- **Mengapa tidak menggunakan Naive Hugging Face Pipeline di Produksi?**
  Implementasi standar `model.generate()` menggunakan alokasi memori berurutan, sinkronisasi PyTorch overhead tinggi, tidak mendukung *dynamic batching*, dan memicu fragmentasi memori hingga 60-80%. Akibatnya, GPU *throughput* sering kali berada di bawah 15% dari batas teoretis hardware (FLOPs utilization).
- **Apa yang Dibutuhkan Enterprise?**
  Arsitektur yang mengisolasi *runtime execution* ke dalam akselerator teroptimasi kernel C++/CUDA (vLLM/TensorRT-LLM), didukung oleh *reverse proxy orchestration layer* yang menangani *streaming*, *token authentication*, *rate-limiting*, *semantic caching*, dan audit keamanan secara deterministik.

---

### 5. How (Workflow Detail)

Arsitektur siklus hidup sebuah inferensi produksi berjalan sebagai berikut:

```
[Client Request]
       |
       v
[API Gateway (FastAPI / Envoy)]
       |
       +---> [Semantic Cache (Redis + Vector Index)] ---> (Hit? Return cached response)
       |
       v (Miss)
[NeMo Guardrails (Input Validation, PII Redaction)]
       |
       v
[Inference Engine Scheduler (vLLM Engine)]
       |---> Dynamic Batcher (Iteration-level scheduler)
       |---> PagedAttention Block Allocator
       |
       v
[GPU Compute Kernels]
       |---> FlashAttention-2 Forward Pass (Fused Kernel)
       |---> Tensor Parallel All-Reduce (NVLink)
       |
       v
[Streaming Detokenizer]
       |
       v
[Output Guardrails (Hallucination & Jailbreak Check)]
       |
       v
[Server-Sent Events (SSE) Response Stream to Client]
```

1. **Ingestion & Semantic Cache:** Request dienkripsi dan di-*hash*. *Semantic embedding* diperiksa pada Redis; jika skor kosinus $> 0.96$ dengan *entry* yang valid, kembalikan respons instan (Latensi $< 10\text{ ms}$).
2. **Pre-flight Guardrail:** Memvalidasi tidak adanya injeksi *prompt* atau kebocoran data sensitif (*PII*).
3. **Engine Scheduling:** *Request* masuk ke *engine queue*. Token baru dialokasikan ke blok *PagedAttention*.
4. **Execution Cycle:** Engine menjalankan *Chunked Prefill* (jika ada konteks baru panjang) digabungkan dengan fase *Decode* dari *request* yang sedang berjalan.
5. **Streaming Out:** Token diterjemahkan (*detokenized*) per unit dan dikirim melalui protokol SSE (*Server-Sent Events*), memotong persepsi latensi pengguna secara signifikan.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Restoran Cepat Saji vs PagedAttention
- **Naive Contiguous Memory:** Anda memesan meja panjang berkapasitas 20 kursi karena "mungkin" teman-teman Anda akan datang, meskipun akhirnya Anda hanya makan berdua. Seluruh 18 kursi lainnya terkunci dan pelanggan lain ditolak (Pemborosan memori parah).
- **PagedAttention:** Sistem memberikan Anda meja kecil untuk 2 orang. Jika teman Anda datang, sistem memberikan meja kecil lain di sudut ruangan yang berbeda, namun pramusaji memegang daftar (*Block Table*) bahwa kedua meja tersebut adalah satu grup pemesanan yang sama.

```
SISTEM MEMORI LOGIS VS FISIK (PAGED ATTENTION)

Logical Sequence (Request ID: req_9921)
+--------------+--------------+--------------+
| Token 0 - 15 | Token 16- 31 | Token 32- 47 |
+--------------+--------------+--------------+
  Page 0         Page 1         Page 2
    |              |              |
    +-------+      |      +-------+
            |      |      |
            v      v      v
Physical GPU Memory (HBM3/HBM3e Allocation)
+--------+--------+--------+--------+--------+--------+
| Blk 00 | Blk 01 | Blk 02 | Blk 03 | Blk 04 | Blk 05 |
| Free   | Page 1 | Other  | Page 0 | Free   | Page 2 |
+--------+--------+--------+--------+--------+--------+
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Memahami Algoritma Manual KV-Cache
Skrip demonstrasi murni dalam PyTorch untuk mengilustrasikan perbedaan komputasi autoregresif tanpa cache $\mathcal{O}(N^2)$ vs dengan cache $\mathcal{O}(N)$.

```python
import torch
import torch.nn as nn
import time

class MinimalSelfAttentionWithKVCache(nn.Module):
    def __init__(self, d_model: int, n_heads: int):
        super().__init__()
        self.d_model = d_model
        self.n_heads = n_heads
        self.head_dim = d_model // n_heads

        self.q_proj = nn.Linear(d_model, d_model, bias=False)
        self.k_proj = nn.Linear(d_model, d_model, bias=False)
        self.v_proj = nn.Linear(d_model, d_model, bias=False)
        self.out_proj = nn.Linear(d_model, d_model, bias=False)

    def forward(self, x: torch.Tensor, kv_cache: tuple = None):
        """
        x: (batch, seq_len, d_model)
        kv_cache: Tuple[torch.Tensor, torch.Tensor] | None
        """
        b, s, _ = x.shape
        q = self.q_proj(x).view(b, s, self.n_heads, self.head_dim).transpose(1, 2)
        k = self.k_proj(x).view(b, s, self.n_heads, self.head_dim).transpose(1, 2)
        v = self.v_proj(x).view(b, s, self.n_heads, self.head_dim).transpose(1, 2)

        if kv_cache is not None:
            prev_k, prev_v = kv_cache
            # Konkatenasi KV cache sepanjang sumbu sequence
            k = torch.cat([prev_k, k], dim=2)
            v = torch.cat([prev_v, v], dim=2)

        new_kv_cache = (k, v)

        # Scaled Dot-Product Attention
        scores = torch.matmul(q, k.transpose(-2, -1)) / (self.head_dim ** 0.5)
        attn_weights = torch.softmax(scores, dim=-1)
        output = torch.matmul(attn_weights, v)

        output = output.transpose(1, 2).contiguous().view(b, s, self.d_model)
        return self.out_proj(output), new_kv_cache

# Validasi Fungsionalitas
if __name__ == "__main__":
    layer = MinimalSelfAttentionWithKVCache(d_model=64, n_heads=4)
    prompt = torch.randn(1, 5, 64) # 5 tokens prompt
    
    # 1. Prefill Stage
    out, cache = layer(prompt, kv_cache=None)
    print(f"Prefill Output Shape: {out.shape}, Cached K Shape: {cache[0].shape}")

    # 2. Decode Stage (Next 1 Token)
    next_token = torch.randn(1, 1, 64)
    out_next, cache = layer(next_token, kv_cache=cache)
    print(f"Decode Output Shape: {out_next.shape}, Updated Cached K Shape: {cache[0].shape}")
```

#### 7.2 Practical Example: Enterprise Async vLLM Engine dengan Instrumentation & Fallback
Implementasi server inferensi asynchronous tingkat produksi menggunakan Engine API vLLM, metrik Prometheus, dan streaming response:

```python
import asyncio
from typing import AsyncGenerator
from vllm.engine.arg_utils import AsyncEngineArgs
from vllm.engine.async_llm_engine import AsyncLLMEngine
from vllm.sampling_params import SamplingParams
from prometheus_client import Counter, Histogram, start_http_server

# Telemetry Metrics Definition
REQUEST_COUNT = Counter('llm_requests_total', 'Total LLM requests received', ['model', 'status'])
TTFT_HISTOGRAM = Histogram('llm_time_to_first_token_seconds', 'Time To First Token latency', ['model'])
TPOT_HISTOGRAM = Histogram('llm_time_per_output_token_seconds', 'Time Per Output Token latency', ['model'])

class EnterpriseLLMService:
    def __init__(self, model_path: str, tensor_parallel_size: int = 1):
        engine_args = AsyncEngineArgs(
            model=model_path,
            tensor_parallel_size=tensor_parallel_size,
            gpu_memory_utilization=0.90,
            max_model_len=4096,
            enforce_eager=False,          # Aktifkan CUDA Graphs
            quantization="awq",           # Opsional: awq, gptq, fp8
            disable_log_requests=True,
            trust_remote_code=True
        )
        self.engine = AsyncLLMEngine.from_engine_args(engine_args)
        self.model_name = model_path

    async def generate_stream(
        self, 
        prompt: str, 
        request_id: str,
        temperature: float = 0.2,
        max_tokens: int = 512
    ) -> AsyncGenerator[str, None]:
        sampling_params = SamplingParams(
            temperature=temperature,
            top_p=0.95,
            max_tokens=max_tokens,
            stop=["<|eot_id|>", "</s>"]
        )

        start_time = asyncio.get_event_loop().time()
        first_token_time = None
        last_token_time = None
        token_count = 0

        try:
            results_generator = self.engine.generate(prompt, sampling_params, request_id)
            
            async for request_output in results_generator:
                current_time = asyncio.get_event_loop().time()
                
                # Metrik TTFT
                if first_token_time is None and len(request_output.outputs[0].text) > 0:
                    first_token_time = current_time
                    TTFT_HISTOGRAM.labels(model=self.model_name).observe(first_token_time - start_time)
                
                # Metrik TPOT
                if last_token_time is not None:
                    inter_token_latency = current_time - last_token_time
                    TPOT_HISTOGRAM.labels(model=self.model_name).observe(inter_token_latency)

                last_token_time = current_time
                token_count += 1
                
                # Yield text delta
                yield request_output.outputs[0].text

            REQUEST_COUNT.labels(model=self.model_name, status="success").inc()

        except Exception as e:
            REQUEST_COUNT.labels(model=self.model_name, status="failed").inc()
            raise e

# Validasi Orkestrasi Loop
async def main():
    start_http_server(8001) # Prometheus metrics port
    service = EnterpriseLLMService(model_path="mistralai/Mistral-7B-Instruct-v0.2")
    
    prompt_input = "Jelaskan perbedaan mendasar arsitektur Monolitik dan Event-Driven dalam 3 kalimat."
    print(f"Mengirim Request: {prompt_input}\n--- Respons Streaming ---")
    
    last_text = ""
    async for output_text in service.generate_stream(prompt_input, request_id="txn_001"):
        delta = output_text[len(last_text):]
        print(delta, end="", flush=True)
        last_text = output_text
    print("\n\n--- Selesai Streaming ---")

if __name__ == "__main__":
    # asyncio.run(main()) # Jalankan jika dependensi vllm & GPU siap
    pass
```

---

### 8. Real World Case Study (Enterprise Scale)

#### 8.1 Skenario
**Kasus:** Sistem *Core Document Intelligence & Compliance Audit* untuk Bank Skala Nasional (Volume: 12.000 dokumen/jam, rata-rata dokumen 3.000 kata).
- **Tantangan:** 
  1. API komersial pihak ketiga melanggar regulasi privasi data perbankan (Data Sovereign Law).
  2. Latensi inferensi dengan HuggingFace vanilla mencapai $45\text{ detik/dokumen}$.
  3. Biaya komputasi GPU melonjak tinggi akibat penggunaan node A100 $80\text{GB}$ tanpa optimasi.

#### 8.2 Desain Solusi Produksi
1. **Model & Kuantisasi:** Migrasi ke **Meta-Llama-3-70B-Instruct** yang dikuantisasi ke **AWQ (4-bit)**. Reduksi ukuran model dari $140\text{ GB}$ menjadi $\sim38\text{ GB}$, memungkinkan penempatan model di dalam satu instance compute yang berisi $2\times \text{NVIDIA A10G (24GB)}$ atau $1\times \text{A100 (40GB)}$ dengan Tensor Parallelism $TP=2$.
2. **Runtime Engine:** Menerapkan vLLM dengan konfigurasi `chunked_prefill_size=512` dan integrasi *Prefix Caching* (karena sistem prompt kepatuhan perbankan identik di setiap pemanggilan dokumen).
3. **Hasil Benchmark:**
   - **Throughput:** Meningkat $9.4\times$ (dari 14 req/sec menjadi 132 req/sec).
   - **Time-to-First-Token (TTFT):** Turun dari $2.8\text{ s}$ ke $320\text{ ms}$ berkat *Automatic Prefix Caching*.
   - **Penghematan Biaya (TCO):** Berkurang sebesar $72\%$ per bulan dibandingkan menyewa cluster A100 $80\text{GB}$.

---

### 9. Trade-offs

| Pendekatan / Parameter | Keuntungan | Kerugian / Konsekuensi | Kapan Digunakan |
| :--- | :--- | :--- | :--- |
| **Full Precision ($FP16/BF16$)** | Akurasi numerik 100% identik dengan bobot latih, stabilitas optimal. | Boros memori, komputasi berat, membutuhkan hardware interkoneksi tinggi (H100/A100). | Tahap *Fine-Tuning* dan tugas analitik bernilai kritis tinggi (misal: penegakan hukum/finansial absolut). |
| **Weight-Only Quantization (AWQ/GPTQ 4-bit)** | Penghematan VRAM hingga $\sim70\%$, throughput tinggi pada memory-bound decode. | Kemungkinan degradasi minor pada penalaran logis kompleks (*loss of perplexity*). | Inferensi umum dengan *budget* terbatas pada hardware seperti RTX 4090 atau A10G. |
| **Speculative Decoding** | Mempercepat *latency generation* ($1.5\times - 2.5\times$) tanpa degradasi akurasi. | Mengonsumsi lebih banyak compute resources; inefisien jika *acceptance rate* draft model rendah ($< 60\%$). | Kebutuhan interaksi suara (*real-time voice agent*) atau UI teks latensi sangat rendah. |
| **DeepSpeed ZeRO-3 vs FSDP** | ZeRO-3 memiliki ekosistem integrasi yang luas di Hugging Face. | FSDP memiliki overhead CPU-to-GPU memory transfer yang lebih efisien di PyTorch 2.x native. | Fine-Tuning model $\ge 70\text{B}$ lintas multi-node bare-metal cluster. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Silent Degradation saat LoRA Merging
- **Gejala:** Model hasil merge LoRA menghasilkan teks pengulangan (*looping token*) atau degradasi output yang parah setelah digabungkan menggunakan `model.merge_and_unload()`.
- **Root Cause:** Perbedaan presisi (*type casting mismatch*). Model dasar dimuat dalam $INT4/NF4$ (misal melalui `bitsandbytes`), kemudian di-*merge* langsung ke dalam parameter target tanpa didekuantisasi dengan benar ke bobot float $FP16/BF16$.
- **Solusi:**
  ```python
  # SALAH: Me-merge adapter langsung di model bitsandbytes 4-bit
  # model = AutoModelForCausalLM.from_pretrained(path, load_in_4bit=True)

  # BENAR:
  base_model = AutoModelForCausalLM.from_pretrained(
      base_model_path,
      torch_dtype=torch.bfloat16,
      device_map="cpu" # Merge aman dilakukan di RAM CPU untuk hindari OOM GPU
  )
  model = PeftModel.from_pretrained(base_model, adapter_path)
  merged_model = model.merge_and_unload()
  merged_model.save_pretrained(target_dir, safe_serialization=True)
  ```

#### 10.2 CUDA Out-of-Memory (OOM) pada Sequence Expansion
- **Gejala:** Inferensi berjalan lancar pada batch awal, tetapi tiba-tiba *crash* dengan pesan `CUDA out of memory` saat memproses token ke-2048.
- **Root Cause:** Tidak mengunci batas `gpu_memory_utilization` atau membiarkan KV cache dialokasikan secara bebas oleh PyTorch native tanpa alokator berbasis blok.
- **Troubleshooting Step:**
  1. Batasi alokasi PyTorch: `torch.cuda.set_per_process_memory_fraction(0.85)`.
  2. Implementasikan *PagedAttention* atau batasi *sliding window attention* jika menggunakan LLM native.
  3. Aktifkan *Chunked Prefill* di engine inference untuk meratakan *memory spike* saat menerima *prompt* berukuran raksasa.

---

### 11. Best Practices (Production Checklist)

1. [ ] **Hardware Interconnect:** Pastikan P2P transfer aktif antar GPU (`nvidia-smi topo -m` menunjukkan konektivitas NVLink `NV#`, bukan PCIe `SYS`).
2. [ ] **Memory Precision:** Gunakan tipe data `bfloat16` dibanding `float16` untuk mencegah *overflow/underflow gradient* tanpa memerlukan dynamic scaling.
3. [ ] **Attention Optimization:** Pastikan kernel `FlashAttention-2` atau `vLLM PagedAttention` terkompilasi secara native, bukan fallback ke implementasi naive PyTorch.
4. [ ] **Prefix Caching:** Aktifkan flag `--enable-prefix-caching` pada vLLM jika aplikasi berbasis *system prompt* statis atau *few-shot examples*.
5. [ ] **Connection Pooling & Concurrency:** Konfigurasi HTTP server dengan HTTP/2 atau gRPC untuk mengelola *multiplexed SSE streams*.
6. [ ] **Timeouts & Disconnections:** Implementasikan mekanisme *cancellation callback* pada inference engine; hentikan komputasi generasi KV cache seketika jika koneksi client terputus.
7. [ ] **Safety Guardrail:** Validasi input *sebelum* menyentuh GPU context untuk menghemat siklus komputasi terhadap request berbahaya.
8. [ ] **Telemetry:** Monitor kuantitatif: `GPU Volatile Memory Utilization`, `HBM Bandwidth`, `TTFT (Time-To-First-Token)`, dan `TPOT (Time-Per-Output-Token)`.

---

### 12. Hands-on Practice: Membangun Inference Cluster & LoRA Fine-Tuning Pipeline

Simpan seluruh file berikut di folder `hands-on/m02/`.

#### Langkah 1: Persiapan Environment
```bash
mkdir -p hands-on/m02 && cd hands-on/m02
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install torch==2.3.0 torchvision --index-url https://download.pytorch.org/whl/cu121
pip install transformers==4.41.2 peft==0.11.1 bitsandbytes==0.43.1 datasets==2.19.2 accelerate==0.30.1 trl==0.8.6
```

#### Langkah 2: Skrip QLoRA Finetuning Teroptimasi FlashAttention-2
Simpan skrip ini sebagai `hands-on/m02/qlora_production.py`:

```python
import torch
from datasets import Dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from trl import SFTTrainer

def run_fine_tuning():
    model_id = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
    
    # 1. Konfigurasi Kuantisasi NF4
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )

    # 2. Muat Model Dasar
    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
    tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        quantization_config=bnb_config,
        device_map="auto",
        torch_dtype=torch.bfloat16,
        attn_implementation="flash_attention_2" if torch.cuda.is_bf16_supported() else "eager"
    )

    # 3. Model Preconditioning
    model = prepare_model_for_kbit_training(model)
    
    # 4. LoRA Setup
    peft_config = LoraConfig(
        r=16,
        lora_alpha=32,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM"
    )
    model = get_peft_model(model, peft_config)
    model.print_trainable_parameters()

    # 5. Dummy Dataset Representatif
    data = {
        "text": [
            "<|system|>\nAnda adalah asisten regulasi fintech.</s>\n<|user|>\nApa itu KYC?</s>\n<|assistant|>\nKYC (Know Your Customer) adalah proses verifikasi identitas nasabah untuk mitigasi risiko pencucian uang.</s>",
            "<|system|>\nAnda adalah asisten regulasi fintech.</s>\n<|user|>\nSebutkan batasan transfer harian.</s>\n<|assistant|>\nBatasan transfer harian default adalah IDR 100.000.000 per instrumen akun verified.</s>"
        ] * 10
    }
    dataset = Dataset.from_dict(data)

    # 6. Parameter Training Produksi
    training_args = TrainingArguments(
        output_dir="./outputs_lora",
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
        warmup_steps=2,
        max_steps=10,
        learning_rate=2e-4,
        fp16=False,
        bf16=True if torch.cuda.is_bf16_supported() else False,
        logging_steps=1,
        optim="paged_adamw_8bit",
        gradient_checkpointing=True,
        report_to="none"
    )

    trainer = SFTTrainer(
        model=model,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=512,
        tokenizer=tokenizer,
        args=training_args
    )

    print("Memulai training pipeline...")
    trainer.train()
    print("Training tuntas. Menyimpan adapter...")
    model.save_pretrained("./outputs_lora_final")

if __name__ == "__main__":
    run_fine_tuning()
```

#### Langkah 3: Eksekusi dan Verifikasi
Jalankan training:
```bash
python hands-on/m02/qlora_production.py
```
Periksa alokasi bobot adapter yang berhasil tersimpan:
```bash
ls -lh ./outputs_lora_final
# Pastikan 'adapter_model.safetensors' dan 'adapter_config.json' terbuat secara valid.
```

---

### 13. Exercises

#### 13.1 Level Easy: Analisis Memori Statis Model
Hitung berapa Gigabyte ($GB$) VRAM mentah yang dibutuhkan murni untuk memuat bobot model $34\text{B}$ parameter pada tingkat presisi:
1. $FP32$
2. $FP16$
3. $INT4$
*Kriteria Sukses:* Berikan hasil konversi dalam Gigabyte (1 GB = $10^9$ bytes) dan GiB (1 GiB = $2^{30}$ bytes).

#### 13.2 Level Medium: Perhitungan Kebutuhan KV-Cache Dinamis
Sebuah model LLM memiliki arsitektur sebagai berikut:
- $n_{\text{layers}} = 32$
- $n_{\text{heads}} = 32$ (MHA murni)
- $d_{\text{head}} = 128$
- Presisi data: $FP16$ (2 byte)

Berapa total memori KV-cache yang dibutuhkan jika server melayani konkurensi $b = 64$ pengguna secara simultan, di mana masing-masing pengguna mengirimkan dan menerima total konteks $s = 4.096$ token? Tunjukkan rumus dan langkah perhitungannya!

#### 13.3 Level Hard: Menghindari Memory Spillover dengan Prefix Caching
Tuliskan implementasi skrip simulasi penjadwalan (*scheduling simulator*) dalam bahasa Python yang mengidentifikasi kesamaan *token prefix* dari 5 request input konkuren. Pisahkan alokasi token yang dapat di-*share* secara logis menggunakan skema *Prefix Block Tree* sederhana untuk membuktikan efisiensi penghematan alokasi blok memori fisik.

---

### 14. Challenges

#### Arsitektur Desain: Multi-Tenant Sovereign LLM Engine
Rancang arsitektur sistem komputasi inferensi untuk sistem layanan kesehatan (*healthcare*) dengan spesifikasi:
- **Throughput:** Mampu melayani 500 *concurrent requests* dengan target $TTFT \le 200\text{ ms}$ dan $TPOT \le 20\text{ ms}$.
- **Karakteristik:** Rata-rata prompt memiliki konteks rekam medis panjang ($16.000\text{ token}$), respons dokter rata-rata $256\text{ token}$.
- **Hardware Constraints:** Anda memiliki klaster dengan 4 node, masing-masing berisi $8\times \text{NVIDIA H100 SXM5 80GB}$.
- **Tugas Arsitektur:**
  1. Tentukan strategi paralelisasi (kombinasi $TP$ dan $PP$).
  2. Hitung alokasi pembagian VRAM antara bobot model (gunakan referensi model Llama-3-70B FP8), *Activation Memory*, dan alokasi *Paged KV-Cache*.
  3. Desain diagram arsitektur interkoneksi jaringan (Infiniband vs RoCE), topologi cluster vLLM/Triton, serta mekanisme *Semantic Router* untuk routing request darurat (*high-priority*) vs analisis berkas rutin (*batching priority*).

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian A: Basic (Pilihan Ganda)
1. Apa fungsi utama dari *Rotary Position Embedding* (RoPE) dibanding absolut positional encoding?
   - A. Menghapus kebutuhan operasi dot-product attention
   - B. Memungkinkan ekstrapolasi panjang token konteks secara fleksibel melalui rotasi vektor kompleks
   - C. Mengurangi ukuran model weights menjadi separuh
   - D. Menghilangkan tahapan backward pass saat training

2. Manakah komponen yang di-*cache* selama proses autoregressive decoding LLM?
   - A. Matriks Query dan Value
   - B. Bobot Gradien Backpropagation
   - C. Matriks Key dan Value
   - D. Token Embedding Input saja

3. Berapa rasio penghematan memori bobot saat mengonversi model dari FP16 ke 4-bit (misal: AWQ)?
   - A. $2\times$
   - B. $4\times$
   - C. $8\times$
   - D. $1.5\times$

4. Mengapa FlashAttention jauh lebih cepat dibanding standard PyTorch attention?
   - A. Menurunkan jumlah FLOPs komputasi matematis secara fundamental
   - B. Melakukan tiling IO-aware untuk memaksimalkan read/write pada SRAM GPU dan meminimalkan akses lambat ke HBM
   - C. Menghilangkan matriks softmax
   - D. Melakukan kuantisasi otomatis ke INT4

5. Apa yang dimaksud dengan metrik *TTFT* (Time-To-First-Token)?
   - A. Waktu total yang dibutuhkan untuk menghasilkan seluruh jawaban
   - B. Waktu yang dibutuhkan dari inisiasi request hingga token output pertama diterima oleh user
   - C. Jumlah token per detik yang dihasilkan oleh cluster
   - D. Waktu transfer model dari storage SSD ke memori VRAM

#### Bagian B: Intermediate (Analisis Singkat)
6. Jelaskan mengapa *Grouped-Query Attention* (GQA) menghasilkan jejak memori *KV Cache* yang jauh lebih kecil dibandingkan *Multi-Head Attention* (MHA)!
7. Pada fase eksekusi LLM, bedakan secara mendalam karakteristik komputasi antara fase **Prefill** dan fase **Decode** ditinjau dari batasan hardware (*Compute-Bound* vs *Memory-Bound*)!
8. Apa kelemahan utama arsitektur *Speculative Decoding* jika diterapkan pada domain bahasa medis atau hukum yang sangat terspesialisasi?
9. Bagaimana mekanisme *Double Quantization* pada QLoRA bekerja dan berapa estimasi penghematan VRAM yang dihasilkannya?
10. Mengapa model kuantisasi $INT8$ post-training tanpa proteksi outlier (seperti SmoothQuant/LLM.int8()) mengalami penurunan performa dramatis pada model di atas $6.7\text{B}$ parameter?

#### Bagian C: Kasus Produksi
11. **Kasus 1:** Sebuah cluster vLLM melayani traffic padat. Pengguna melaporkan bahwa saat prompt pendek ($< 100\text{ token}$), latensi inter-token ($TPOT$) sangat cepat ($15\text{ ms}$), namun ketika satu pengguna memasukkan prompt sebesar $18.000\text{ token}$, seluruh request pengguna lain yang sedang berjalan mengalami *freeze* (latensi melonjak hingga $2.000\text{ ms}$). Masalah arsitektural apa yang sedang terjadi, dan bagaimana konfigurasi engine untuk memperbaikinya tanpa menambah GPU?
12. **Kasus 2:** Anda menjalankan distributed fine-tuning Llama-3-70B menggunakan DeepSpeed ZeRO-3 pada 2 node ($16\times \text{A100 80GB}$). Anda mengamati bahwa utilizasi GPU (GPU-Util) fluktuatif, sering jatuh ke 0% selama beberapa detik di antara iterasi *step*. Identifikasi 2 akar masalah arsitektur jaringan/distributed communication yang paling potensial dan berikan solusinya!
13. **Kasus 3:** Pipeline inferensi Anda menerapkan sistem RAG. Data compliance mendikte bahwa tidak boleh ada cache prompt yang saling bocor antar *Tenant ID* yang berbeda, namun perusahaan ingin memaksimalkan fitur *Automatic Prefix Caching* pada vLLM. Bagaimana Anda mendesain arsitektur *Namespace Tokenizer Cache* untuk memastikan isolasi data multi-tenant tetap aman 100% secara matematis?

---

### Kunci Jawaban & Panduan Evaluasi Quiz

#### Bagian A
1. **B** — RoPE merepresentasikan posisi token relatif melalui matriks rotasi ortogonal, memudahkan model mengekstrapolasi token melampaui jendela konteks awal.
2. **C** — Hanya representasi Key ($K$) dan Value ($V$) yang di-cache untuk token masa lalu; Query ($Q$) hanya diproyeksikan untuk token aktif saat ini.
3. **B** — $FP16$ memakan 16 bit (2 byte) per bobot, sedangkan 4-bit memakan 0.5 byte. Rasio kompresi teoretis bobot adalah $16 / 4 = 4\times$.
4. **B** — FlashAttention mempertahankan operasi matematis yang sama persis (exact attention), namun mengatur komputasi menggunakan teknik *tiling* agar pembacaan/penulisan intermediate matrix ($S, P$) terjadi di SRAM yang berkecepatan tinggi ($\sim 19\text{ TB/s}$), bukan bolak-balik ke HBM ($\sim 2-3\text{ TB/s}$).
5. **B** — TTFT mengukur latensi dari diterimanya prompt hingga token respons pertama di-*emit*, merefleksikan kecepatan fase *prefill*.

#### Bagian B
6. Pada MHA, rasio kepala proyeksi adalah $1:1$ antara Query, Key, dan Value ($n_K = n_V = n_Q$). Pada GQA, beberapa kepala Query (misal 8 query heads) berbagi satu pasang Key-Value head ($n_K = n_V = n_Q / 8$). Dengan membagi jumlah head KV sebesar faktor kelompok tersebut, ukuran tensor KV-cache yang disimpan di VRAM menyusut proporsional secara linear.
7. - **Prefill Phase:** Memproses seluruh token input secara paralel. Matriks komputasi berukuran besar ($b \times s \times d$). Tergolong **Compute-Bound** karena rasio komputasi terhadap transfer memori tinggi, memaksimalkan penggunaan Tensor Cores.
   - **Decode Phase:** Menghasilkan satu token baru per waktu per sekuens secara sekuensial. Membaca seluruh bobot model dan seluruh riwayat KV cache dari HBM hanya untuk komputasi token tunggal. Tergolong **Memory-Bound** (dibatasi oleh HBM memory bandwidth).
8. Jika *draft model* (model kecil) tidak memiliki representasi akurat tentang kosakata dan konteks domain khusus (medis/hukum), prediksi draf tokennya akan sering ditolak oleh *target model* (model besar). Kegagalan verifikasi ini memicu penalti komputasi ganda sehingga latensi justru lebih lambat dibanding inferensi biasa tanpa *speculative decoding*.
9. Double Quantization menguantisasi bobot quantization constant (*scaling factors*) itu sendiri. Jika kuantisasi blok pertama menghasilkan 32-bit float scaling factor per 64 blok parameter, faktor skala ini dikuantisasi lagi ke 8-bit FP. Ini menghemat sekitar $0.37\text{ bit}$ per parameter, atau $\sim 3\text{ GB}$ VRAM pada model 65B.
10. Pada model $\ge 6.7\text{B}$, muncul fenomena *Emergent Feature Outliers*: sejumlah kecil dimensi tersembunyi tertentu memiliki nilai magnitudo aktivasi ekstrem ($100\times$ lebih besar dari fitur lain) di hampir seluruh token. Jika dikuantisasi secara naif ke skala 8-bit seragam, presisi fitur penting ini hancur, melumpuhkan kapabilitas output model.

#### Bagian C
11. **Masalah:** Terjadi *Head-of-Line Blocking* karena fase *prefill* dari prompt raksasa ($18.000\text{ token}$) memonopoli seluruh komputasi GPU dan menunda langkah *decode* dari request lain yang sedang berjalan.
    **Solusi:** Aktifkan fitur **Chunked Prefill** (pada vLLM: `--enable-chunked-prefill --max-num-batched-tokens 512/1024`). Sistem akan memecah prefill 18.000 token menjadi beberapa potongan (*chunks* kecil) dan menyisipkannya bersamaan dengan iterasi *decode* request lain, mengeliminasi lonjakan latensi (*jitter*).
12. **Akar Masalah:**
    - Botleneck komunikasi inter-node akibat non-tersedianya fabric berkecepatan tinggi (misal: komunikasi antar node jatuh ke standard TCP/IP $10\text{ Gbps}$, bukan InfiniBand GPUDirect RDMA). ZeRO-3 mengharuskan pertukaran bobot model di setiap layer pada *forward* dan *backward pass*.
    - CPU Offloading bottleneck jika parameter dialokasikan ke RAM sistem yang lambat.
    **Solusi:** Pastikan NCCL menggunakan backend InfiniBand/RoCE (`export NCCL_DEBUG=INFO`, pastikan RoCE aktif). Jika interkoneksi lambat, ubah strategi dari ZeRO-3 murni ke **ZeRO-2** (hanya membagi gradients dan optimizer states) dikombinasikan dengan *Tensor Parallelism* di intra-node.
13. **Desain Solusi:** Modifikasi struktur hashing prefix engine. Tambahkan cryptographic hash `HMAC(Tenant_ID, Salt)` sebagai token virtual buatan (*hard prefix token*) di awal prompt stream secara internal sebelum masuk ke PagedAttention tree indexer. Dengan cara ini, hash tree root node untuk Tenant A dan Tenant B tidak akan pernah bertemu pada alamat hash blok fisik yang sama, mencegah *cross-tenant block sharing* sekaligus mempertahankan kemampuan prefix caching penuh untuk user di dalam tenant yang sama.

---

### 16. Summary
- Inferensi LLM skala enterprise menuntut optimasi komputasi yang berfokus pada efisiensi penggunaan bandwidth memori GPU (HBM).
- **PagedAttention** dan **Continuous Batching** merupakan standar de facto arsitektur serving modern yang meniadakan fragmentasi memori dan fenomena *Head-of-Line blocking*.
- Teknik kuantisasi mutakhir (**AWQ, FP8**) serta komputasi **FlashAttention** mengizinkan throughput tinggi pada footprint hardware yang terjangkau tanpa menurunkan reliabilitas nalar model secara drastis.
- Keberhasilan arsitektur LLM produksi ditentukan oleh sinergi antara *low-level GPU engine tuning* (CUDA/Triton/vLLM) dan arsitektur orkestrasi enterprise (*Semantic Caching, Namespace Isolation, Dynamic Guardrails*).