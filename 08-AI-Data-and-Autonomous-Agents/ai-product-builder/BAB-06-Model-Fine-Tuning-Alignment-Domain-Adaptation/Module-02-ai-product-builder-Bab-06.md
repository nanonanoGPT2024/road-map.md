# Kurikulum Enterprise AI Product Builder
## Kategori: 08-AI-Data-and-Autonomous-Agents
### BAB 06: Model Fine-Tuning, Alignment, and Domain Adaptation
#### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Merancang dan Mengorkestrasikan** arsitektur pelatihan terdistribusi (*distributed training*) untuk adaptasi domain model skala besar (*Large Language Models*) menggunakan teknik Parameter-Efficient Fine-Tuning (PEFT/LoRA/QLoRA) dan Fully Sharded Data Parallel (FSDP / DeepSpeed ZeRO-3).
2. **Menerapkan Pipeline Alignment Lanjutan** berbasis *Direct Preference Optimization* (DPO) dan *Kahneman-Tversky Optimization* (KTO) untuk mengeliminasi bias halusinasi dan memastikan kepatuhan regulasi industri (*compliance & safety*).
3. **Mengoptimalkan Footprint Memori GPU** melalui formulasi matematis konsumsi VRAM (*weights, gradients, optimizer states, activations*) dan teknik akselerasi seperti *FlashAttention-2*, *Gradient Checkpointing*, dan *Fused Optimizers*.
4. **Membangun Sistem Serving Produksi** berlatensi rendah dengan *dynamic multi-LoRA adapter switching* di atas engine inferensi throughput tinggi (*vLLM* / *Triton Inference Server*).
5. **Mengimplementasikan Evaluasi Otomatis & Guardrail CI/CD** untuk mencegah *catastrophic forgetting* pada downstream tasks menggunakan automated benchmarks (*MMLU*, *MT-Bench*, *Domain-Specific Evals*).

---

### 2. Prerequisite

Peserta wajib menguasai:
- **Arsitektur Transformer Mendalam:** Self-Attention mechanism, RoPE (*Rotary Position Embeddings*), MLP blocks, LayerNorm/RMSNorm, KV Cache.
- **Deep Learning Frameworks:** PyTorch tingkat lanjut (Custom Modules, Autograd engine, Distributed Data Parallel/DDP primitives).
- **Hugging Face Ecosystem:** `transformers`, `peft`, `accelerate`, `trl`, `datasets`, dan `bitsandbytes`.
- **Infrastruktur Komputasi AI:** Arsitektur GPU NVIDIA (Ampere/Hopper/Ada Lovelace), CUDA runtime, Precision formats (FP32, FP16, BF16, INT8, FP4/NF4), dan NVLink interconnects.
- **Prinsip Rekayasa Data:** Manipulasi data skala besar menggunakan Apache Arrow, Parquet, dan teknik tokenisasi streaming.

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1 Alokasi Memori GPU pada Model Terdistribusi

Total konsumsi memori ($M_{\text{total}}$) saat pelatihan SFT (*Supervised Fine-Tuning*) model Transformer konvensional (FP16/BF16) dihitung melalui persamaan:

$$M_{\text{total}} = M_{\text{weights}} + M_{\text{gradients}} + M_{\text{optimizer}} + M_{\text{activations}} + M_{\text{temporary}}$$

Untuk pelatihan standar dengan *AdamW*:
- **Weights ($M_{\text{weights}}$):** $2 \times \Phi$ bytes (FP16/BF16), di mana $\Phi$ adalah jumlah parameter.
- **Gradients ($M_{\text{gradients}}$):** $2 \times \Phi$ bytes.
- **Optimizer States ($M_{\text{optimizer}}$):** $12 \times \Phi$ bytes ($4 \Phi$ FP32 master weights + $4 \Phi$ first momentum + $4 \Phi$ second momentum).
- Total memori statis: $16 \times \Phi$ bytes. Pada model 70B, $16 \times 70 \times 10^9 \approx 1.12 \text{ TB}$ VRAM (hanya untuk parameter statis, di luar aktivasi).

#### 3.2 Parameter-Efficient Fine-Tuning: LoRA & QLoRA

LoRA membekukan bobot asli $W_0 \in \mathbb{R}^{d \times k}$ dan menyuntikkan matriks dekomposisi rank rendah $A \in \mathbb{R}^{r \times k}$ dan $B \in \mathbb{R}^{d \times r}$ dengan rank $r \ll \min(d, k)$:

$$W = W_0 + \Delta W = W_0 + \frac{\alpha}{r} (B \cdot A)$$

Di mana $\alpha$ adalah hyperparameter *scaling factor* konstan.

```
Input x (dim d)
   │
   ├───> [ Frozen Base Weights W0 ] ───> W0 · x ─────────────(+)──> Output h
   │                                                          ▲
   └───> [ Down-projection A ] ──> [ Up-projection B ] ──( * α/r )
         (dim d -> r)              (dim r -> k)
```

QLoRA (*Quantized Low-Rank Adaptation*) memperkenalkan tiga inovasi kritis:
1. **NF4 (NormalFloat4):** Tipe data kuantisasi optimal secara teoritis untuk bobot yang terdistribusi normal zero-mean unit-variance.
2. **Double Quantization (DQ):** Kuantisasi terhadap kuantisasi konstanta (*quantization scale factors*), memangkas jejak memori dari 0.5 bit/parameter menjadi 0.127 bit/parameter.
3. **Paged Optimizers:** Menggunakan CUDA Unified Memory untuk melakukan paging otomatis status optimizer antara VRAM GPU dan DRAM CPU saat terjadi lonjakan aktivasi (*out-of-memory spikes*).

#### 3.3 DeepSpeed ZeRO vs. PyTorch FSDP

Untuk model yang melebihi kapasitas satu GPU, teknik *Zero Redundancy Optimizer* (ZeRO) mempartisi memori tanpa mengubah semantik komputasi paralel:
- **ZeRO-Stage 1:** Mempartisi status optimizer $M_{\text{optimizer}}$ ke seluruh $N$ GPUs (Pengurangan memori $\approx 4\times$).
- **ZeRO-Stage 2:** Mempartisi status optimizer dan gradient $M_{\text{gradients}}$ (Pengurangan memori $\approx 8\times$).
- **ZeRO-Stage 3 / FSDP:** Mempartisi bobot model $M_{\text{weights}}$, gradient, dan optimizer. Bobot di-*all-gather* secara instan sesaat sebelum komputasi *forward* dan *backward*, lalu segera dibebaskan dari memori.

```
+-------------------------------------------------------------------------+
|                  FSDP / ZeRO-Stage 3 Memory Distribution                |
+-------------------------------------------------------------------------+
| GPU 0                 | GPU 1                 | GPU 2                 |
| [Param 0-33%] (FP16)  | [Param 34-66%] (FP16) | [Param 67-100%](FP16) |
| [Grad 0-33%]  (FP16)  | [Grad 34-66%]  (FP16) | [Grad 67-100%] (FP16) |
| [Opt  0-33%]  (FP32)  | [Opt  34-66%]  (FP32) | [Opt  67-100%] (FP32) |
+-------------------------------------------------------------------------+
                                    ▲
                                    │ Ring All-Gather during Forward
                                    ▼
+-------------------------------------------------------------------------+
| Layer Computation (W_full reconstructed temporarily, then immediately   |
| released from VRAM after forward/backward step execution)               |
+-------------------------------------------------------------------------+
```

#### 3.4 Alignment: Direct Preference Optimization (DPO)

RLHF (*Reinforcement Learning from Human Feedback*) tradisional menggunakan PPO (*Proximal Policy Optimization*) yang tidak stabil karena membutuhkan 4 model simultan dalam memori: *Actor Model*, *Critic Model*, *Reward Model*, dan *Reference Model*.

DPO merumuskan ulang reward model eksplisit menjadi fungsi probabilitas implisit di bawah parameterisasi model referensi $\pi_{\text{ref}}$, memanfaatkan relasi matematis turunan Bradley-Terry:

$$\mathcal{L}_{\text{DPO}}(\pi_\theta; \pi_{\text{ref}}) = - \mathbb{E}_{(x, y_w, y_l) \sim \mathcal{D}} \left[ \log \sigma \left( \beta \log \frac{\pi_\theta(y_w \mid x)}{\pi_{\text{ref}}(y_w \mid x)} - \beta \log \frac{\pi_\theta(y_l \mid x)}{\pi_{\text{ref}}(y_l \mid x)} \right) \right]$$

Di mana:
- $y_w$ adalah respons yang disukai (*winning response*).
- $y_l$ adalah respons yang ditolak (*losing response*).
- $\beta$ mengontrol regulasi divergensi Kullback-Leibler (KL) terhadap model referensi $\pi_{\text{ref}}$.
- Sistem hanya memerlukan 2 model dalam VRAM: $\pi_\theta$ (aktif/dapat dilatih) dan $\pi_{\text{ref}}$ (dibekukan).

---

### 4. Why & What

| Dimensi | Mengapa Diperlukan (*Why*) | Apa Solusinya (*What*) |
| :--- | :--- | :--- |
| **Keterbatasan RAG** | RAG hanya menyuntikkan *knowledge*, bukan *reasoning behavior*, sintaks keluaran terstruktur, atau kepatuhan gaya bahasa perusahaan. | SFT (Supervised Fine-Tuning) untuk menanamkan domain-specific token sequences, reasoning logic, dan formatting deterministik. |
| **Kekakuan SFT Murni** | SFT mengajarkan model *apa yang harus dikatakan*, tetapi rentan terhadap halusinasi dan tidak dapat membedakan mana respons buruk vs optimal. | Preference Alignment (DPO/KTO) untuk menekan probabilitas keluaran sub-optimal dan mengunci *safety boundary*. |
| **Keterbatasan Biaya Komputasi** | Full fine-tuning model 70B membutuhkan klaster GPU berdaya ratusan ribu USD per run. | QLoRA + FSDP: Memungkinkan adaptasi model skala enterprise dengan fraksi memori hingga 75% lebih hemat. |
| **Multi-Tenancy Serving** | Meng-host model penuh per klien/domain melipatgandakan *operational expenditure* (OpEx) secara linear. | Multi-LoRA Serving: Menjalankan satu base model tunggal dengan dynamic adapter swapping berbasis metadata permintaan inferensi. |

---

### 5. How (Workflow Detail)

Arsitektur end-to-end adaptasi model produksi enterprise mengikuti alur 5 fase:

```
[ Phase 1: Data Engine ]
  Raw Unstructured Domain Data -> Parsing & Cleaning -> MinHash De-duplication 
  -> Token Length Filtering -> Token Packing (Constant Context Window)
          │
          ▼
[ Phase 2: Supervised Fine-Tuning (SFT) ]
  Base Foundation Model (Llama-3/Mistral) + NF4 Quantization
  -> Injected LoRA Adapters (Targeting all linear layers)
  -> FSDP / DeepSpeed ZeRO-3 Distributed Training + FlashAttention-2
  -> Intermediate Checkpoint Validation via Loss Convergence & Perplexity
          │
          ▼
[ Phase 3: Preference Alignment (DPO) ]
  SFT Checkpoint Model -> Generate Pairwise Responses (Win/Loss)
  -> Expert Human Annotators / LLM-as-a-judge Preference Tagging
  -> DPO Loss Optimization (Calibrating implicit reward, beta tuning)
          │
          ▼
[ Phase 4: Production Evaluation & Safety Gating ]
  Aligned Checkpoint -> Automated Benchmark Suite (MMLU / Custom Eval Engine)
  -> Degradation Regression Test (Zero-shot forgetting verification)
  -> Adapter Serialization & SafeTensors Validation
          │
          ▼
[ Phase 5: High-Throughput Serving & Dynamic Swapping ]
  Base Engine (vLLM / Triton) -> Memory-pinned Adapter Repository
  -> Dynamic Adapter Hot-Swap per Request Header -> Low-Latency Inference
```

1. **Fase 1: Data Engine & Token Packing:** Data dibersihkan, di-*deduplicate*, dan dikelompokkan menggunakan token packing (*concatenated sequences* dibatasi oleh token `<|endoftext|>`) untuk memaksimalkan utilitas *context window* dan mengeliminasi *padding token waste*.
2. **Fase 2: Distributed SFT:** Model dasar dimuat menggunakan kuantisasi atau partisi sharding. LoRA diinjeksikan pada seluruh modul linear (`q_proj`, `k_proj`, `v_proj`, `o_proj`, `gate_proj`, `up_proj`, `down_proj`).
3. **Fase 3: Alignment:** Model hasil SFT digunakan sebagai baseline model referensi $\pi_{\text{ref}}$, sementara model $\pi_\theta$ dioptimasi dengan dataset preferensi terkurasi menggunakan loss DPO.
4. **Fase 4: Production Evaluation & Safety Gate:** Model diuji terhadap dataset regresi domain publik dan internal untuk memastikan adaptasi domain tidak merusak kapabilitas penalaran umum.
5. **Fase 5: Deployment:** Model diekspor ke format SafeTensors. Base model dimuat ke dalam runtime inferensi vLLM, sedangkan adapter disimpan secara decoupled untuk dynamic routing.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Bedah Rekonstruktif Tulang vs. Set Pakaian Bedah Spesialis
- **Pre-training (Model Fondasi):** Proses pertumbuhan tubuh manusia dari bayi hingga dewasa (pembentukan kerangka tulang dasar, kapasitas organ, dan kemampuan motorik umum). Membutuhkan energi masif dan tidak mungkin diulang terus-menerus.
- **Full Fine-Tuning:** Merestrukturisasi seluruh kerangka tulang melalui bedah invasif ekstrem. Berisiko melumpuhkan kapabilitas dasar tubuh (*catastrophic forgetting*).
- **LoRA / QLoRA:** Dokter spesialis memakai set sarung tangan bedah ergonomis dan peralatan spesifik di atas tubuh yang sehat. Tulang asli (bobot dasar) dibekukan total tanpa modifikasi, hanya instrumen tambahan (adapter) yang disesuaikan secara presisi.
- **DPO (Alignment):** Ujian etika medis dan sertifikasi dewan kode etik profesi kedokteran untuk memverifikasi bahwa dokter tidak hanya terampil, namun mematuhi protokol keselamatan pasien di bawah kondisi batas (*edge cases*).

```
                      +------------------------------------------+
                      |         Base Foundation Weights          |
                      |            (Frozen 4-bit NF4)            |
                      |        W0 in R^(4096 x 4096)             |
                      +------------------------------------------+
                                           │
                    ┌──────────────────────┴──────────────────────┐
                    │                                             │
             Forward Pass Path                             Forward Pass Path
            [ Frozen Base Path ]                          [ LoRA Bypass Path ]
                    │                                             │
                    ▼                                             ▼
          +-------------------+                         +-------------------+
          |  W0 * x (NF4 GEMM)|                         | A * x (dim 4096->16)|
          +-------------------+                         +-------------------+
                    │                                             │
                    │                                             ▼
                    │                                   +-------------------+
                    │                                   | B * A * x (16->4096)|
                    │                                   +-------------------+
                    │                                             │
                    │                                             ▼
                    │                                   +-------------------+
                    │                                   | Scaling ( * α / r)|
                    │                                   +-------------------+
                    │                                             │
                    └──────────────────────┬──────────────────────┘
                                           │
                                           ▼
                                   [ Element-wise Sum ]
                                           │
                                           ▼
                                 Output Representation
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Implementasi LoRA Linear Layer dari Dasar

Berikut implementasi minimal native PyTorch yang merekonstruksi mekanisme internal forward dan weight update LoRA:

```python
import torch
import torch.nn as nn
import math

class CustomLoRALinear(nn.Module):
    def __init__(
        self, 
        in_features: int, 
        out_features: int, 
        rank: int = 8, 
        alpha: float = 16.0
    ):
        super().__init__()
        self.in_features = in_features
        self.out_features = out_features
        self.rank = rank
        self.scaling = alpha / rank

        # Bobot dasar dibekukan (Simulasi Pre-trained Weight)
        self.base_weight = nn.Parameter(
            torch.randn(out_features, in_features), requires_grad=False
        )
        
        # Matriks adapter trainables
        # Inisialisasi Kaiming Uniform untuk A, dan Zero untuk B
        self.lora_A = nn.Parameter(torch.empty(rank, in_features))
        self.lora_B = nn.Parameter(torch.zeros(out_features, rank))
        
        nn.init.kaiming_uniform_(self.lora_A, a=math.sqrt(5))
        
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Jalur Base Model (Bisa dikompilasi atau di-offload)
        base_out = torch.matmul(x, self.base_weight.t())
        
        # Jalur Adaptasi LoRA: (x * A^T) * B^T * scaling
        lora_step_1 = torch.matmul(x, self.lora_A.t())       # Shape: [batch, seq, rank]
        lora_step_2 = torch.matmul(lora_step_1, self.lora_B.t()) # Shape: [batch, seq, out]
        lora_out = lora_step_2 * self.scaling
        
        return base_out + lora_out

# Verifikasi parameter
layer = CustomLoRALinear(in_features=4096, out_features=4096, rank=16)
total_params = sum(p.numel() for p in layer.parameters())
trainable_params = sum(p.numel() for p in layer.parameters() if p.requires_grad)

print(f"Total Parameter: {total_params:,}")
print(f"Trainable Parameter: {trainable_params:,} ({(trainable_params/total_params)*100:.2f}%)")
# Output menunjukkan reduksi parameter latih >99.2%
```

#### 7.2 Practical Example: Pipeline SFT & DPO Skala Produksi

Script tingkat enterprise berikut menjalankan SFT menggunakan QLoRA, dilanjutkan dengan alignment DPO menggunakan `trl`, `peft`, dan `transformers` dengan dukungan FlashAttention-2 dan Token Packing:

```python
import os
import torch
from datasets import Dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments,
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from trl import DPOTrainer, DPOConfig

def setup_qlora_model(model_id: str):
    """Menginisialisasi model dengan kuantisasi NF4 dan konfigurasi LoRA."""
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    
    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        quantization_config=bnb_config,
        device_map="auto",
        torch_dtype=torch.bfloat16,
        attn_implementation="flash_attention_2",
    )

    model = prepare_model_for_kbit_training(
        model, 
        use_gradient_checkpointing=True
    )

    lora_config = LoraConfig(
        r=64,
        lora_alpha=128,
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj", 
            "gate_proj", "up_proj", "down_proj"
        ],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )

    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()
    return model, tokenizer

def execute_dpo_training(
    model, 
    tokenizer, 
    dpo_dataset: Dataset, 
    output_dir: str
):
    """Menjalankan Direct Preference Optimization pada LoRA checkpoint."""
    training_args = DPOConfig(
        per_device_train_batch_size=2,
        per_device_eval_batch_size=2,
        gradient_accumulation_steps=4,
        learning_rate=5e-6,
        lr_scheduler_type="cosine",
        warmup_ratio=0.1,
        num_train_epochs=3,
        logging_steps=10,
        save_strategy="steps",
        save_steps=100,
        eval_strategy="steps",
        eval_steps=50,
        output_dir=output_dir,
        bf16=True,
        max_length=2048,
        max_prompt_length=1024,
        beta=0.1,  # Regulasi divergensi KL implisit
        gradient_checkpointing=True,
        remove_unused_columns=False,
    )

    dpo_trainer = DPOTrainer(
        model=model,
        ref_model=None, # PeftModel otomatis menangani reference state via frozen base
        args=training_args,
        train_dataset=dpo_dataset,
        processing_class=tokenizer,
    )

    dpo_trainer.train()
    
    # Simpan hasil akhir adapter teroptimasi
    final_adapter_path = os.path.join(output_dir, "final_dpo_adapter")
    dpo_trainer.model.save_pretrained(final_adapter_path)
    tokenizer.save_pretrained(final_adapter_path)
    print(f"LoRA Adapter berhasil diamankan di: {final_adapter_path}")

if __name__ == "__main__":
    BASE_MODEL = "meta-llama/Meta-Llama-3-8B-Instruct"
    
    # Dummy Pairwise Preferences Dataset
    dataset_records = {
        "prompt": [
            "Jelaskan risiko leverage tinggi dalam transaksi repo obligasi:",
            "Bagaimana format payload untuk transfer RTGS ISO 20022?"
        ],
        "chosen": [
            "Risiko utama leverage tinggi mencakup kerentanan terhadap margin call saat harga aset underlying terkoreksi, risiko likuiditas jika counterparty default, dan systemic liquidity spiral.",
            "<Document><FIToFICstmrCdtTrf><GrpHdr><MsgId>20260330001</MsgId></GrpHdr></FIToFICstmrCdtTrf></Document>"
        ],
        "rejected": [
            "Risiko leverage tinggi adalah kamu bisa kehilangan uang dengan sangat cepat kalau pasar turun.",
            "Format RTGS biasanya pakai XML atau JSON, tergantung sistem banknya masing-masing."
        ]
    }
    pairwise_dataset = Dataset.from_dict(dataset_records)
    
    trained_model, text_tokenizer = setup_qlora_model(BASE_MODEL)
    execute_dpo_training(trained_model, text_tokenizer, pairwise_dataset, "./output_checkpoint")
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Sistem Audit Kepatuhan Regulasi Perbankan Global (Tier-1 Investment Bank)
* **Konteks:** Sebuah institusi keuangan global memproses 120.000 dokumen kontrak derivatif, obligasi, dan transaksi perbankan harian. Regulasi mengharuskan sistem otomatis memetakan klausul kontrak ke standar FINRA, MAS, dan OJK tanpa adanya kesalahan interpretasi legal.
* **Tantangan:**
  - Evaluasi model base komersial (GPT-4) menimbulkan isu kebocoran data rahasia perbankan (*data sovereignty* & GDPR violation).
  - Model base open-weights lokal (Llama-3-70B) mengalami tingkat halusinasi terminologi hukum sebesar 22.4% dan gagal mematuhi format validasi JSON Schema secara konsisten.
  - Anggaran infrastruktur dibatasi maksimal 4 node GPU (32x NVIDIA H100 80GB SXM5).
* **Solusi Arsitektur:**
  1. **Dataset Engine:** Kurasi 50.000 korpus legal beranotasi ganda (*expert annotated*) diproses melalui pipeline token packing untuk efisiensi context window 8192 tokens.
  2. **Distributed Training:** 70B model di-fine-tune menggunakan PyTorch FSDP (ZeRO-3 equivalent) dipadukan dengan QLoRA rank 64 pada 32 node GPU, mereduksi waktu training dari 18 hari (metode standar) menjadi 38 jam.
  3. **Preference Alignment via DPO:** Menggunakan 12.000 pasang data evaluasi internal legal. Jawaban yang mengandung penafsiran klausul tanpa referensi pasal eksplisit diklasifikasikan sebagai *rejected*.
  4. **Serving Layer:** Base Llama-3-70B di-quantize menjadi FP8 dan di-host menggunakan vLLM engine dengan dukungan dynamic routing LoRA adapter khusus regional (Adapter FINRA, Adapter OJK, Adapter MAS).
* **Hasil:**
  - Reliabilitas interpretasi hukum meningkat ke 99.1% (akurasi ekstraksi pasal).
  - Error skema parsing JSON anjlok dari 18.2% ke 0.02%.
  - Biaya komputasi berkurang hingga 84% dibandingkan menjalankan inference API komersial pihak ketiga.

---

### 9. Trade-offs

| Pendekatan / Keputusan | Metrik Unggul | Metrik Terkorbankan | Titik Kritis Pengambilan Keputusan (*Decision Boundary*) |
| :--- | :--- | :--- | :--- |
| **Full Fine-Tuning** | Kapasitas adaptasi representasi maksimal; tidak ada overhead komputasi inferensi. | Konsumsi VRAM masif ($16\times \Phi$ bytes); risiko fatal *catastrophic forgetting*. | Hanya jika data domain sangat berbeda fundamentalnya dari base corpus (misal: protein sequencing, raw binary code analysis). |
| **LoRA (Rank Tinggi, e.g., $r=128$)** | Penangkapan pola kompleks tinggi; fleksibilitas bobot besar. | Ukuran file checkpoint besar; memori GPU meningkat; rentan overfitting pada dataset kecil. | Digunakan saat dataset SFT domain berskala $>100.000$ sampel kompleks. |
| **QLoRA (NF4)** | VRAM minimal (mampu melatih model 70B pada 2x GPU 80GB). | Penalti performa kecepatan pelatihan $\approx 25-35\%$ lebih lambat dibanding BF16 murni karena siklus dekuantisasi/kuantisasi runtime. | Wajib dipilih jika batasan hardware menjadi *hard constraint*. |
| **DPO vs PPO (RLHF)** | DPO: Stabilitas latihan tinggi, tidak memerlukan critic/reward network terpisah, VRAM $50\%$ lebih rendah. | PPO: Mampu mengeksplorasi output space baru yang tidak ada dalam offline preference dataset. | Pilih DPO untuk 95% enterprise alignment use-case; gunakan PPO jika memiliki reward model dinamis skala besar (e.g., automated code execution feedback). |
| **Merged Weights vs Multi-LoRA Serving** | Merged: Latensi per request absolut minimal; native engine throughput. Multi-LoRA: Utilisasi resource maksimal (1 base model, ratusan adapter domain). | Merged: Skalabilitas VRAM linear terhadap jumlah model domain. Multi-LoRA: Tambahan latensi kecil ($\approx 3-5\%$) untuk dynamic kernel memory switching. | Pilih Multi-LoRA jika memiliki $>3$ use-case domain independen dalam arsitektur sistem. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Loss Spike dan Menjadi `NaN` pada Mixed-Precision Training
* **Gejala:** Loss training tiba-tiba melonjak pada epoch 2 dan langsung menghasilkan nilai `NaN` (*Not a Number*).
* **Akar Masalah:** Penggunaan FP16 tanpa dynamic loss scaling yang memadai, atau gradient overflow pada adapter up-projection layer ($B$).
* **Solusi Perbaikan:**
  1. Beralih ke **BF16** (*Bfloat16*) pada arsitektur GPU Ampere/Hopper karena rentang dinamis eksponennya setara dengan FP32.
  2. Implementasikan Gradient Clipping dengan batasan ketat:
     ```python
     torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=0.3)
     ```

#### 10.2 Catastrophic Forgetting
* **Gejala:** Model menjadi sangat mahir pada domain terminologi internal perusahaan, tetapi kehilangan kemampuan penalaran umum, logika matematika, atau instruksi percakapan dasar (*chat template adherence*).
* **Akar Masalah:** Hyperparameter learning rate terlalu tinggi ($>1e-4$ untuk SFT) atau dataset SFT tidak memiliki regularisasi data umum.
* **Solusi Perbaikan:** Campurkan dataset fine-tuning domain dengan 5-10% data percakapan umum berkualitas tinggi (e.g., OpenOrca/ShareGPT subset) dan turunkan learning rate menjadi $1e-5 - 5e-5$.

#### 10.3 Tokenizer Special Token Desynchronization
* **Gejala:** Model tidak pernah berhenti menghasilkan output (tidak pernah mengeluarkan token `<|im_end|>` atau `</s>`) dan mengalami *infinite inference loop*.
* **Akar Masalah:** `pad_token_id` diatur sama persis dengan `eos_token_id` tanpa menonaktifkan penghitungan loss pada token tersebut, atau template chat (*Jinja template*) tidak menambahkan marker EOS secara konsisten di dataset latih.
* **Solusi Perbaikan:**
  ```python
  tokenizer.add_special_tokens({'pad_token': '[PAD]'})
  model.resize_token_embeddings(len(tokenizer))
  model.config.pad_token_id = tokenizer.pad_token_id
  ```

---

### 11. Best Practices (Production Checklist)

#### Pre-training & Data Hygiene
- [ ] Lakukan de-duplikasi dataset menggunakan MinHash LSH (Threshold similarity $> 0.85$ dibuang).
- [ ] Jalankan validasi schema format token pada 100% sampel untuk memastikan sintaks Jinja/ChatML tidak korup.
- [ ] Lakukan token length distribution analysis; tetapkan hard-cutoff pada persentil 99 untuk menghindari degradasi VRAM oleh segelintir data outlier.

#### Training Environment
- [ ] Aktifkan FlashAttention-2 (`attn_implementation="flash_attention_2"`).
- [ ] Terapkan Gradient Checkpointing untuk menghemat memori aktivasi hingga 60%.
- [ ] Pastikan precision training menggunakan native `bf16=True`.
- [ ] Konfigurasikan target LoRA ke seluruh modul linier arsitektur attention dan MLP (tidak hanya Q dan V).
- [ ] Monitor gradient norm dan learning rate scheduler step menggunakan tracking engine eksternal (e.g., Weights & Biases / MLflow).

#### Post-Training & Alignment
- [ ] Jalankan benchmark perplexity pada dataset terpisah (*held-out validation split*).
- [ ] Jalankan uji evaluasi regresi (GSM8K, ARC, HumanEval) untuk memverifikasi kapasitas logika dasar tidak terdegradasi $> 3\%$.
- [ ] Ekspor model adapter secara decoupled menggunakan format serialisasi zero-copy `safetensors`.

---

### 12. Hands-on Practice

Buat dan atur struktur direktori laboratorium berikut pada environment Anda:

```bash
mkdir -p hands-on/m02/{configs,scripts,data,checkpoints}
cd hands-on/m02
```

#### Langkah 1: Persiapan Dataset Formatted (Simulasi Ekstraksi JSON)
Simpan file dataset dummy berformat JSON lines pada `data/domain_train.jsonl`:

```bash
cat << 'EOF' > data/domain_train.jsonl
{"messages": [{"role": "system", "content": "Anda adalah asisten perbankan berlisensi resmi."}, {"role": "user", "content": "Jelaskan definisi Tier 1 Capital menurut Basel III."}, {"role": "assistant", "content": "Berdasarkan Basel III, Tier 1 Capital terdiri dari Common Equity Tier 1 (CET1) dan Additional Tier 1 (AT1), yang berfungsi menyerap kerugian saat bank beroperasi secara going-concern."}]}
{"messages": [{"role": "system", "content": "Anda adalah asisten perbankan berlisensi resmi."}, {"role": "user", "content": "Berapa rasio kecukupan modal minimum yang diwajibkan regulator?"}, {"role": "assistant", "content": "Rasio kecukupan modal minimum (CAR) menurut standar Basel III adalah 8% dari total Risk-Weighted Assets (RWA), di mana 4.5% harus dipenuhi oleh CET1."}]}
EOF
```

#### Langkah 2: Script Training SFT dengan Token Packing (`scripts/train_sft.py`)

```python
import os
import torch
from datasets import load_dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from trl import SFTTrainer

def run():
    model_name = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
    
    # 1. Konfigurasi Quantization
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
    )

    # 2. Tokenizer
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    tokenizer.pad_token = tokenizer.eos_token

    # 3. Model Loading
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        quantization_config=bnb_config,
        device_map="auto"
    )
    model = prepare_model_for_kbit_training(model)

    # 4. LoRA Setup
    peft_config = LoraConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
        bias="none",
        task_type="CAUSAL_LM"
    )

    # 5. Dataset Loading
    dataset = load_dataset("json", data_files="data/domain_train.jsonl", split="train")

    # 6. Training Parameters
    training_args = TrainingArguments(
        output_dir="checkpoints/sft_output",
        per_device_train_batch_size=1,
        gradient_accumulation_steps=2,
        learning_rate=2e-4,
        logging_steps=1,
        max_steps=5, # Pembatasan step untuk simulasi hands-on
        bf16=True,
        save_strategy="no"
    )

    trainer = SFTTrainer(
        model=model,
        train_dataset=dataset,
        peft_config=peft_config,
        processing_class=tokenizer,
        args=training_args,
    )

    trainer.train()
    print("Hands-on SFT Training Berhasil Diselesaikan!")
    trainer.model.save_pretrained("checkpoints/final_handson_adapter")

if __name__ == "__main__":
    run()
```

Jalankan script hands-on di terminal:
```bash
python3 scripts/train_sft.py
```

---

### 13. Exercise

#### Level 1 - Easy
1. Modifikasi script `scripts/train_sft.py` untuk mengaktifkan logging loss ke direktori TensorBoard lokal.
2. Tambahkan evaluasi target modul `gate_proj`, `up_proj`, dan `down_proj` ke dalam konfigurasi `LoraConfig`.

#### Level 2 - Medium
1. Tulis sebuah script Python `scripts/merge_adapters.py` yang memuat base model dan LoRA adapter yang dihasilkan pada sesi hands-on, lalu lakukan fusi (*weight merging*) via metode `merge_and_unload()`.
2. Simpan model fusi penuh ke disk dalam format SafeTensors 16-bit dan bandingkan latensi throughput inferensinya dengan model LoRA decoupled unmerged menggunakan evaluasi 100 iterasi sequence prompt.

#### Level 3 - Hard
1. Rancang pipeline evaluasi regresi menggunakan kerangka kerja evaluasi kustom:
   - Ambil 50 prompt uji dari domain umum (e.g., pertanyaan dasar coding Python, terjemahan bahasa, analogi matematika).
   - Eksekusi model base vs model yang telah di-fine-tune.
   - Hitung nilai semantic similarity score (menggunakan sentence-transformers embedding cosine distance) antara respons model base dan model fine-tuned untuk mendeteksi deviasi keluaran instruksi umum (*forgetting coefficient*).

---

### 14. Challenge

#### Skenario: Arsitektur Continuous Adaptive Learning dengan Batasan Latensi
Perusahaan asuransi kesehatan multinasional membutuhkan sistem otomatisasi klaim medis. Aturan polis asuransi diperbarui setiap minggu secara dinamis di 5 wilayah hukum yang berbeda (US-HIPAA, EU-GDPR, SG-PDPA, ID-PDP, AU-PrivacyAct).

**Spesifikasi Kebutuhan:**
1. Desain blueprint arsitektur CI/CD di mana pembaruan regulasi mingguan secara otomatis memicu proses data preparation, tokenization packing, QLoRA fine-tuning, dan DPO alignment.
2. Model inferensi harus melayani single-tenant base engine (misal: 1 node multi-GPU vLLM), tetapi mampu merutekan inferensi klaim ke adapter regulasi wilayah yang tepat berdasarkan metadata header HTTP (`X-Jurisdiction-Region`).
3. Waktu *cold start* saat memuat adapter baru tidak boleh melebihi 200 ms dan P99 inference latency tidak boleh melampaui 1.2 detik untuk output 512 tokens.

**Tugas Anda:**
Tuliskan dokumen desain arsitektur teknis lengkap mencakup:
- Diagram ASCII topology sistem (Data Pipeline -> Distributed Fine-Tuning Cluster -> Model Registry -> Inference Engine with Dynamic Adapter LRU Cache).
- Algoritma handling evaluasi otomatis: model baru dilarang dipromosikan ke production traffic (*canary deployment*) jika akurasi deteksi pasal klaim $< 98\%$ atau regresi kapabilitas umum $> 2\%$.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic
1. **Mengapa pada QLoRA bobot dasar dibekukan dalam format 4-bit (NF4) sementara komputasi maju (*forward pass*) dilakukan dalam presisi 16-bit (BF16)?**
   - A. Karena arsitektur Tensor Core NVIDIA tidak dapat melakukan operasi perkalian skalar 4-bit.
   - B. Agar bobot dasar dapat didekuantisasi secara dinamis ke 16-bit untuk komputasi matriks dengan input aktivasi FP16/BF16, mempertahankan presisi numerik tanpa membengkakkan memori penyimpanan statis.
   - C. Karena format NF4 hanya digunakan untuk kompresi file zip saat model disimpan di hard drive.
   - D. NF4 otomatis dikonversi ke FP32 oleh sistem operasi sebelum masuk ke chip VRAM.
   *Jawaban yang benar: B. Bobot 4-bit didekuantisasi on-the-fly ke BF16 saat forward pass berlangsung untuk dikalikan dengan tensor aktivasi berpresisi 16-bit.*

2. **Apa peran utama parameter rank ($r$) dalam implementasi LoRA?**
   - A. Menentukan jumlah layer Transformer yang dibekukan secara permanen.
   - B. Menentukan dimensi ruang bagian (*low-rank subspace dimension*) dari matriks pembaruan bobot $\Delta W$.
   - C. Mengatur jumlah epoch maksimum saat optimizer beroperasi.
   - D. Mengubah jumlah attention head pada base model.
   *Jawaban yang benar: B. Rank $r$ menentukan dimensi intermediate dari matriks dekomposisi $A$ dan $B$.*

3. **Hyperparameter $\alpha$ (alpha) pada LoRA berfungsi sebagai:**
   - A. Batasan jumlah token maksimum yang dapat diproses model per forward pass.
   - B. Learning rate khusus untuk optimizer AdamW.
   - C. Faktor skala konstan yang mengontrol proporsi kontribusi pembaruan bobot LoRA terhadap representasi bobot dasar.
   - D. Threshold kuantisasi gradien.
   *Jawaban yang benar: C. $\alpha$ membagi rank $r$ ($\alpha/r$) untuk mengatur skala dampak adapter terhadap bobot asli.*

4. **Metode alignment DPO mengeliminasi kebutuhan RLHF tradisional atas komponen berikut, KECUALI:**
   - A. Reward Model eksplisit.
   - B. Training Policy berbasis Actor-Critic (PPO loop).
   - C. Dataset Pairwise Preference (Chosen vs Rejected).
   - D. Value Network (Critic Model).
   *Jawaban yang benar: C. DPO tetap secara fundamental memerlukan dataset pairwise preference (chosen dan rejected).*

5. **Apa fungsi teknis utama dari implementasi FlashAttention-2?**
   - A. Memperkecil parameter bobot Transformer hingga 50%.
   - B. Menghindari pembentukan matriks attention $N \times N$ penuh di HBM GPU melalui teknik kernel tiling dan recomputation di SRAM GPU.
   - C. Mengonversi tipe data model dari FP32 ke INT4 secara otomatis tanpa pelatihan ulang.
   - D. Menggandakan ukuran context window tanpa membutuhkan VRAM tambahan.
   *Jawaban yang benar: B. FlashAttention mengoptimalkan IO memory bandwidth antara SRAM dan HBM via tiling.*

#### Bagian 2: Intermediate
6. **Pada distributed training dengan Fully Sharded Data Parallel (FSDP), apa yang terjadi pada bobot model layer ke-3 saat komputasi forward sedang berjalan di layer ke-10?**
   - A. Bobot layer ke-3 tetap berada di VRAM seluruh worker GPU hingga epoch berakhir.
   - B. Bobot layer ke-3 di-offload ke memori SSD NVMe secara otomatis.
   - C. Bobot layer ke-3 telah dibebaskan (*freed/dropped*) dari VRAM lokal segera setelah komputasi maju layer ke-3 selesai, dan hanya disimpan kembali secara parsial sesuai shard masing-masing worker.
   - D. Bobot layer ke-3 diakumulasi ke dalam gradient buffer.
   *Jawaban yang benar: C. Prinsip utama FSDP/ZeRO-3 adalah melepaskan tensor bobot penuh segera setelah layer terkait selesai diproses.*

7. **Kelemahan matematis utama dari penentuan nilai hyperparameter $\beta$ yang terlalu tinggi pada DPO loss adalah:**
   - A. Model mengalami gradient explosion seketika pada step awal.
   - B. Model terikat terlalu kaku pada distribusi model referensi dasar ($\pi_{\text{ref}}$), membatasi kapasitas model untuk menyerap preferensi baru.
   - C. Model akan selalu menghasilkan jawaban kosong (*empty string*).
   - D. Tokenizer kehilangan kemampuan menguraikan special token.
   *Jawaban yang benar: B. $\beta$ berperan sebagai bobot penalti divergensi KL; jika terlalu tinggi, deviasi dari model referensi ditekan secara berlebihan.*

8. **Mengapa teknik Token Packing secara drastis meningkatkan efisiensi waktu komputasi SFT dibanding metode Padding konvensional?**
   - A. Karena Token Packing menghapus seluruh parameter linear dari backward pass.
   - B. Karena metode padding konvensional membuang siklus kalkulasi GPU untuk memproses representasi `pad_token` yang tidak relevan, sedangkan token packing memadatkan token valid secara kontigu dalam satu sequence window.
   - C. Token Packing menurunkan jumlah vocabulary pada tokenizer.
   - D. Token Packing mengubah operasi attention quadratic menjadi linear $O(N)$.
   *Jawaban yang benar: B. Padding menyebabkan pemborosan komputasi pada token kosong, packing memastikan 100% komputasi FLOPs GPU ditujukan untuk token bermakna.*

9. **Saat mengintegrasikan QLoRA, mengapa inisialisasi bobot adapter matriks $A$ menggunakan distribusi normal/Kaiming sementara matriks $B$ diinisialisasi dengan angka nol?**
   - A. Agar model langsung mengalami error jika gradien tidak terhitung.
   - B. Untuk memastikan bahwa pada step 0 training, nilai $\Delta W = B \cdot A = 0$, sehingga output model hasil inisialisasi identik 100% dengan base model awal.
   - C. Untuk menghindari fenomena underflow pada presisi FP16.
   - D. Merupakan batasan sintaksis dari library PyTorch C++ extensions.
   *Jawaban yang benar: B. Inisialisasi $B=0$ menjamin $\Delta W = 0$ saat start, mencegah degradasi performa model di awal training.*

10. **Apa implikasi penggunaan Paged Optimizers pada bitsandbytes saat terjadi memory spike pada proses backward pass?**
    - A. Pelatihan otomatis dihentikan dan checkpoint terakhir dihapus.
    - B. Sistem secara otomatis melakukan paging memori alokasi optimizer state dari VRAM ke CPU DRAM via CUDA Unified Memory, mencegah terjadinya Out-Of-Memory (OOM) crash dengan trade-off penurunan performa sesaat.
    - C. Layer model yang bermasalah dipotong (*pruned*) secara otomatis.
    - D. Parameter rank LoRA diperkecil secara dinamis.
    *Jawaban yang benar: B. Paged Optimizers memanfaatkan unified memory paging CPU-GPU untuk mengatasi fluktuasi puncak aktivasi.*

#### Bagian 3: Skenario Kasus Produksi
11. **Skenario:** Anda memimpin fine-tuning model 13B untuk analisis dokumen finansial. Setelah fine-tuning selesai, model menghasilkan ekstraksi neraca keuangan yang sangat akurat, namun saat pengguna memasukkan prompt: `"Buatkan tabel markdown ringkasan laporan ini"`, model mencetak teks acak tanpa sintaks tabel markdown yang valid. Sebelum di-fine-tune, base model sangat mahir membuat tabel markdown. Apa akar masalah utama dan langkah mitigasi arsitekturnya?
    - A. Masalah terletak pada bit width quantizer bitsandbytes; solusinya adalah melatih ulang model pada FP32 murni.
    - B. Model mengalami *catastrophic forgetting* pada kapabilitas format struktural karena dataset SFT hanya berisi teks naratif polos tanpa contoh respons tabel markdown; solusinya adalah melakukan *dataset replay blending* dengan menyuntikkan 10-15% data multi-format instruksi umum.
    - C. Nilai learning rate LoRA terlalu kecil sehingga model tidak belajar apapun.
    - D. Ukuran rank LoRA ($r$) harus dinaikkan hingga bernilai sama dengan sequence length.
    *Jawaban yang benar: B. Ketidakhadiran representasi variasi output struktural pada dataset adaptasi memicu catastrophic forgetting pada task formatting terkait.*

12. **Skenario:** Tim inferensi melaporkan bahwa setelah menggabungkan (*merging*) adapter LoRA ke base model Llama-3-70B untuk deployment vLLM, akurasi penalaran downstream task turun sebesar 14.8% dibandingkan pengujian menggunakan inferensi dinamis (unmerged adapter). Namun kode pelatihan terverifikasi bebas bug. Apa anomali numerik yang paling mungkin terjadi?
    - A. Terjadi desinkronisasi scaling factor $\alpha/r$ saat de-kuantisasi dan penambahan bobot base weight (misal: penambahan bobot LoRA FP16 langsung ke quantized weight base tanpa de-kuantisasi ke unquantized FP32 master weight terlebih dahulu).
    - B. vLLM tidak mendukung arsitektur Transformer 70B.
    - C. SafeTensors corrupt saat dikonversi ke format pickle binary.
    - D. Tokenizer base model tertukar dengan tokenizer BERT.
    *Jawaban yang benar: A. Merging langsung pada representasi terkuantisasi merusak akurasi numerik bobot secara permanen; fusi harus dilakukan pada presisi penuh (FP32/BF16) sebelum di-kuantisasi kembali untuk engine serving.*

13. **Skenario:** Arsitektur pipeline alignment DPO Anda berjalan dengan lancar secara teknis, namun saat deployment, model menunjukkan fenomena respons yang sangat repetitif dan mengulang-ulang frasa penolakan legalitas secara berlebihan (*over-defensive refusal behavior*) bahkan untuk prompt bisnis normal yang aman. Metrik tracking apa yang gagal dipantau selama DPO loop dan bagaimana mengoreksinya?
    - A. Loss train tidak mencapai nilai 0; solusinya tingkatkan jumlah epoch sebanyak 10 kali lipat.
    - B. Nilai implicit reward margin $(\beta \log \frac{\pi_\theta}{\pi_{\text{ref}}})$ mengalami reward over-optimization dan divergence KL meledak; koreksi dilakukan dengan menurunkan nilai $\beta$, memangkas *length bias* pada dataset preferensi, dan menghentikan pelatihan via early stopping berdasarkan evaluation loss preferensi.
    - C. Gradient accumulation terlalu kecil; ubah nilai batch size menjadi 1.
    - D. GPU mengalami thermal throttling sehingga kalkulasi reward melenceng.
    *Jawaban yang benar: B. Penalti implisit yang terdistorsi atau nilai beta yang tidak seimbang sering kali mengarahkan model ke mode kolaps repetitif yang hiper-konservatif.*

---

### 16. Summary

Adaptasi model fondasi skala enterprise menuntut pemahaman arsitektural yang melampaui *prompt engineering* dan RAG standar:
1. **Efisiensi Komputasi & Alokasi VRAM:** Penguasaan PEFT (LoRA/QLoRA) yang dikombinasikan dengan sharding terdistribusi (PyTorch FSDP / ZeRO-3) memangkas barrier infrastruktur, memungkinkan adaptasi model parameter raksasa pada alokasi komputasi yang terukur.
2. **Kualitas Alignment Mengalahkan Kuantitas:** Transisi industri dari RLHF berbasis PPO ke Direct Preference Optimization (DPO) mengukuhkan stabilitas matematis dalam menyelaraskan perilaku model tanpa kompleksitas training loop 4 model simultan.
3. **Data Engine sebagai Diferensiator Inti:** Kualitas *curation*, *MinHash deduplication*, penanganan token padding, dan konsistensi *chat template* memegang korelasi tertinggi terhadap keberhasilan adaptasi domain dibandingkan penyesuaian hyperparameter minor.
4. **Desain Produksi Ter-decoupled:** Arsitektur serving mutakhir memisahkan fondasi komputasi (base frozen model) dengan kapabilitas domain adaptif (decoupled LoRA adapters), menghasilkan throughput maksimal, multi-tenancy hemat biaya, dan fleksibilitas *continuous learning* yang lincah.