# Bab 06: Model Fine-Tuning, Alignment & Domain Adaptation

## Module 01: Parameter-Efficient Domain Adaptation via QLoRA & SFT Pipeline

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Menganalisis Kebutuhan Adaptasi Model**: Mengidentifikasi secara kuantitatif kapan sistem memerlukan *In-Context Learning* (RAG), *Supervised Fine-Tuning* (SFT), atau *Continual Pre-Training* berdasarkan trade-off latensi, akurasi, dan kapabilitas representasi domain.
2. **Membedah Matematika Dekomposisi Rank Rendah (LoRA/QLoRA)**: Menghitung parameter footprint, memory budget, dan formulasi matematis dari adaptasi bobot $W = W_0 + \Delta W$ dengan faktor reduksi rank $r$, scaling factor $\alpha$, serta kuantisasi NormalFloat4 (NF4).
3. **Mengarsitekturi Data Pipeline untuk SFT**: Merancang pipeline pemrosesan data instruksi yang menangani tokenization, prompt masking (loss masking khusus pada response token), dan *sequence packing* untuk memaksimalkan throughput GPU via FlashAttention-2.
4. **Mengimplementasikan Training Loop QLoRA Kelas Produksi**: Mengembangkan pipeline fine-tuning modular berbasis Python/PyTorch menggunakan pustaka `transformers`, `peft`, dan `bitsandbytes` yang dilengkapi *gradient checkpointing*, *mixed-precision* (BF16), dan *paged optimizers*.
5. **Mengaudit & Memitigasi Kegagalan Adaptasi**: Mengidentifikasi dan memulihkan kondisi *catastrophic forgetting*, instabilitas gradien (NaN loss spikes), serta *quantization-induced activation outliers*.
6. **Menerapkan Standar Deployment Adapter**: Menggabungkan (*merging*) adapter weights kembali ke base model atau menyiapkan konfigurasi multi-tenant adapter serving dengan overhead latensi minimal.

---

### 2. Concept Overview

Domain adaptation dan alignment adalah proses modifikasi representasi parametrik LLM (Large Language Model) untuk menyelaraskan perilaku, format, gaya bahasa, atau pengetahuan internal model dengan spesifikasi domain privat enterprise.

```
                           TAXONOMY ADAPTASI MODEL
                                      │
          ┌───────────────────────────┴───────────────────────────┐
          ▼                                                       ▼
   Non-Parametric                                             Parametric
   (External Knowledge)                                   (Internal Weights)
          │                                                       │
    ┌─────┴─────┐                               ┌─────────────────┴─────────────────┐
    ▼           ▼                               ▼                                   ▼
 Prompting     RAG                     Continual Pre-Training                      Alignment
(Zero/Few-  (Retrieval                      (Unsupervised /                  (Instruction & Style)
  Shot)     Augmented                     Raw Domain Text)                          │
           Generation)                          │                       ┌───────────┴───────────┐
                                                ▼                       ▼                       ▼
                                           Domain Shift               SFT                      DPO /
                                          Representation           (Supervised                 RLHF
                                          (Corpus Khusus)          Fine-Tuning)             (Preference)
```

#### Mental Model: Parametric vs. Non-Parametric Adaptation

*   **RAG (Non-Parametric)**: Menyuntikkan konteks factual runtime ke dalam *working memory* (context window). Cocok untuk data yang berubah cepat, data dinamis, dan mitigasi halusinasi melalui sitasi sumber. Namun, RAG tidak mengubah cara model "berpikir", struktur sintaksis khusus (misal: domain-specific query language), atau nada komunikasi.
*   **Fine-Tuning (Parametric)**: Memodifikasi *long-term memory* (bobot jaringan neural). Bertujuan untuk menanamkan konsistensi gaya struktural, format deterministik (seperti JSON dengan schema rumit), kepatuhan instruksi ketat, atau mengajarkan model merespons dialek/terminologi internal tanpa memboroskan context window dengan token instruksi berulang.

#### Spektrum Adaptasi Parametrik

1.  **Full Fine-Tuning (FFT)**: Semua parameter $W$ diupdate ($\Delta W \in \mathbb{R}^{d \times k}$). Membutuhkan alokasi memori ~4–6x ukuran model dasar untuk menyimpan optimizer states (AdamW), gradients, dan activations. Rentan terhadap *catastrophic forgetting*.
2.  **Parameter-Efficient Fine-Tuning (PEFT)**: Membekukan (*freeze*) bobot dasar $W_0$ dan menambahkan modul parameter kecil yang dapat dilatih. Pendekatan de facto adalah **LoRA (Low-Rank Adaptation)**.
3.  **QLoRA (Quantized LoRA)**: Mengompresi bobot dasar $W_0$ menjadi representasi 4-bit NormalFloat (NF4) sambil mempertahankan gradient flow melalui dekomposisi rank rendah berpresisi tinggi (BF16/FP16) pada matriks adapter.

---

### 3. Why It Matters

Dalam lanskap enterprise engineering, pemanfaatan LLM dasar (foundation models) secara out-of-the-box menghadapi limitasi operasional yang berat:

1.  **Token Economics & Latensi**: Menyematkan ribuan token contoh (*few-shot examples*) pada system prompt untuk setiap inferensi meningkatkan *Time to First Token* (TTFT) dan melipatgandakan biaya API secara eksponensial. SFT memindahkan "instruksi dan contoh" tersebut langsung ke dalam bobot model, memangkas panjang prompt hingga 80-90%.
2.  **Sintaksis & Schema Determinism**: API internal, skema SQL perbankan, dan DSL (*Domain Specific Language*) privat membutuhkan format respons dengan toleransi kesalahan 0%. Zero-shot prompting kerap gagal mempertahankan integritas parsing JSON/SQL pada kondisi edge cases. Fine-tuning mengunci topologi keluaran model.
3.  **Kerahasiaan & Data Governance**: Enterprise di sektor kesehatan dan finansial tidak dapat mengeksternalisasi corpus regulasi internal ke third-party API. QLoRA memungkinkan pelatihan model 8B–70B parameter pada hardware lokal (misal: 1x–4x NVIDIA A100/H100 80GB atau 1x RTX 4090 24GB untuk 8B parameter).
4.  **Mitigasi In-Context Saturation**: Menjejalkan dokumen panjang ke context window 128k sering menimbulkan anomali *Lost-in-the-Middle*. Melatih model mengenali entitas domain via adapter membebaskan context window murni untuk data dinamis.

---

### 4. Arsitektur & Diagram Komponen

#### 4.1. Memori Footprint: Full Fine-Tuning vs. LoRA vs. QLoRA (Model 7B Parameter)

```
===================================================================================
FULL FINE-TUNING (16-bit)      LORA (16-bit Base)             QLORA (4-bit Base + NF4)
Total: ~56 - 80 GB VRAM        Total: ~18 - 24 GB VRAM        Total: ~6 - 10 GB VRAM
===================================================================================
┌────────────────────────┐     ┌────────────────────────┐     ┌────────────────────────┐
│ AdamW States (FP32)    │     │ AdamW (Adapters Only)  │     │ AdamW (Adapters Only)  │
│ [~28 GB]               │     │ [~0.2 GB]              │     │ [~0.2 GB]              │
├────────────────────────┤     ├────────────────────────┤     ├────────────────────────┤
│ Gradients (FP16/FP32)  │     │ Gradients (Adapters)   │     │ Gradients (Adapters)   │
│ [~14 GB]               │     │ [~0.1 GB]              │     │ [~0.1 GB]              │
├────────────────────────┤     ├────────────────────────┤     ├────────────────────────┤
│ Model Weights (FP16)   │     │ Frozen Base (FP16)     │     │ Frozen Base (NF4)      │
│ [~14 GB]               │     │ [~14 GB]               │     │ [~3.5 - 4 GB]          │
├────────────────────────┤     ├────────────────────────┤     ├────────────────────────┤
│ Activations & Overhead │     │ Activations & Overhead │     │ Activations & Paged Opt│
│ (with Grad Checkpoint) │     │ (with Grad Checkpoint) │     │ [~2 - 5 GB]            │
│ [~8 - 20 GB]           │     │ [~4 - 8 GB]            │     │                        │
└────────────────────────┘     └────────────────────────┘     └────────────────────────┘
```

#### 4.2. End-to-End Enterprise QLoRA Fine-Tuning & Serving Architecture

```
 ┌────────────────────────────────────────────────────────────────────────────────────────┐
 │                              DATA ENGINE & TOKENIZATION                                │
 └────────────────────────────────────────────────────────────────────────────────────────┘
         │                                                      │
         ▼                                                      ▼
  Raw Enterprise Data                                    Validation Split
  (JSONL: prompt/response)                               (Out-of-Distribution)
         │                                                      │
         ▼                                                      ▼
  Prompt Templating (e.g. ChatML/Llama-3)                Contamination Detection
  + Sequence Packing (Concat doc w/ EOS)                 & Token Length Audit
  + Loss Masking (Label = -100 on prompt)                       │
         │                                                      │
         └──────────────────────────┬───────────────────────────┘
                                    ▼
 ┌────────────────────────────────────────────────────────────────────────────────────────┐
 │                            QLORA TRAINING ENGINE RUNTIME                               │
 └────────────────────────────────────────────────────────────────────────────────────────┘
  Model Weights Initialization:
   [ Pre-trained FP16 LLM ] ──> Kuantisasi Runtime ──> [ NF4 Quantized Weights (Frozen) ]
                                                          │
  Adapter Attachment (Linear Modules):                    │
   Input Activation x ────────────────────────────────────┼──────────────┐
                                                          ▼              ▼
                                                    [ NF4 Matmul ]  [ LoRA Down: A (r*d) ]
                                                          │              │ (Dropout + Scale)
                                                          │              ▼
                                                          │         [ LoRA Up: B (d*r) ]
                                                          │              │
                                                          ▼              ▼
                                                      Output y = W0(x) + (alpha/r)*B(A(x))
                                                          │
  Optimization Loop:                                      ▼
   Cross-Entropy Loss (Target Only) <── Compute Softmax over Vocabulary
   Backpropagation ───────────────────> Only Updates A and B parameters!
   Memory Management ─────────────────> Paged AdamW via CUDA Unified Memory
                                        + Gradient Checkpointing (Activation Recompute)
                                        + FlashAttention-2 Core
                                                          │
                                                          ▼
 ┌────────────────────────────────────────────────────────────────────────────────────────┐
 │                           ARTIFACT COMPILATION & SERVING                               │
 └────────────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ├───> Path A: Merge Adapters
                                    │     W_merged = W_dequantized + (alpha/r)*BA
                                    │     Export to vLLM / TensorRT-LLM (Zero latency overhead)
                                    │
                                    └───> Path B: Multi-Tenant Dynamic Adapters
                                          Keep Base Engine NF4/FP16 in VRAM
                                          Hot-swap LoRA weights on-the-fly per API Request
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### 5.1. Matematika Low-Rank Adaptation (LoRA)

Sebuah layer dense berbobot $W_0 \in \mathbb{R}^{d \times k}$ menerima representasi $x \in \mathbb{R}^d$ dan menghasilkan $h = W_0 x$. Dalam fine-tuning penuh, model memodifikasi bobot dengan matrix diferensial $\Delta W$, sehingga $h = (W_0 + \Delta W)x$.

Hipotesis *Intrinsic Dimensionality* (Aghajanyan et al., 2020) membuktikan bahwa pembaruan bobot selama adaptasi tugas berada pada subspace dengan dimensi intrinsik yang jauh lebih rendah daripada dimensi penuh model. LoRA memfaktorkan $\Delta W$ menjadi perkalian dua matriks ber-rank rendah:

$$\Delta W = B \cdot A$$

Dimana:
*   $B \in \mathbb{R}^{d \times r}$
*   $A \in \mathbb{R}^{r \times k}$
*   Rank $r \ll \min(d, k)$ (tipikalnya $r \in \{8, 16, 32, 64\}$)

Forward pass dimodifikasi secara matematis menjadi:

$$h = W_0 x + \Delta W x = W_0 x + \frac{\alpha}{r} (B \cdot A) x$$

*   **Inisialisasi**: Matriks $A$ diinisialisasi menggunakan distribusi Gaussian acak $\mathcal{N}(0, \sigma^2)$, sedangkan matriks $B$ diinisialisasi dengan angka **nol** ($0$). Hasilnya, pada step $t = 0$, $\Delta W = B \cdot A = 0$, sehingga output model awal identik 100% dengan base model tanpa degradasi performa.
*   **Scaling Factor $\frac{\alpha}{r}$**: $\alpha$ adalah hyperparameter konstan. Ketika bereksperimen dengan berbagai variasi rank $r$, rasio ini menstabilkan magnitudo update gradien tanpa perlu menyetel ulang learning rate secara agresif.

#### 5.2. Prinsip Fondasional QLoRA (Quantized LoRA)

QLoRA (Dettmers et al., 2023) memperkenalkan 3 inovasi memori:

##### A. Kuantisasi NormalFloat4 (NF4)
Secara empiris, bobot model neural network hasil pra-pelatihan terdistribusi secara normal $\mathcal{N}(0, \sigma^2)$. Kuantisasi uniform (seperti FP4 atau INT4 reguler) tidak optimal untuk informasi yang berdistribusi normal karena densitas titik kuantisasi merata di seluruh rentang nilai, mengabaikan fakta bahwa sebagian besar bobot terkonsentrasi di sekitar nilai 0.

NF4 mengonstruksi 16 bin kuantisasi non-linear diskret $q_i$ ($i \in [0, 15]$) sedemikian rupa sehingga setiap bin memiliki probabilitas jumlah parameter yang sama:

$$q_i = \frac{1}{2} \left( Q_X\left(\frac{i}{2^k}\right) + Q_X\left(\frac{i + 1}{2^k}\right) \right)$$

Di mana $Q_X(\cdot)$ adalah fungsi kuantil dari distribusi normal terstandarisasi $\mathcal{N}(0, 1)$ pada rentang $[-1, 1]$. Pendekatan ini mempertahankan *information-theoretic entropy* maksimum per bit dibanding representasi bilangan bulat biasa.

##### B. Double Quantization (DQ)
Kuantisasi 4-bit memerlukan faktor penskalaan (*quantization constants*) $c^{FP32}$ per blok (misal: ukuran blok = 64 bobot) untuk mengembalikan nilai ke domain numerik asli saat dekuantisasi lokal.
*   Pada ukuran blok 64, konstanta skala 32-bit menyumbang overhead: $32 / 64 = 0.5$ bit per parameter.
*   Double Quantization menguantisasi kembali konstanta skala tersebut menjadi 8-bit FP ($c^{FP8}$) dengan blok kedua berukuran 256.
*   Overhead berkurang drastis:

$$\text{Overhead DQ} = \frac{8}{64} + \frac{32}{64 \times 256} \approx 0.125 + 0.00195 = 0.127 \text{ bit/parameter}$$

Penghematan: ~0.373 bit per parameter, atau setara ~3 GB VRAM pada model 65B/70B.

##### C. Paged Optimizers
Mengatasi memory spike akibat aktivasi dan komputasi gradien panjang konteks ekstrem. QLoRA menggunakan alokasi memori tervirtualisasi CUDA Unified Memory yang mengeksekusi *page-swapping* nir-hambatan antara GPU VRAM dan CPU RAM saat terjadi lonjakan alokasi sementara (*gradient checkpointing peaks*), mencegah terminasi proses akibat runtime `CUDA Out-of-Memory (OOM)`.

#### 5.3. Masked Label Cross-Entropy Loss & Sequence Packing

Saat melakukan fine-tuning untuk tugas instruksi (*instruction following*), model **hanya boleh dievaluasi dan dihukum berdasarkan kemampuannya menghasilkan response token**, bukan pada prompt atau instruksi yang diberikan oleh sistem/user.

Formulasi loss function untuk sequence tokens $X = \{x_1, x_2, \dots, x_N\}$ di mana token instruksi berada pada index $1 \dots M$ dan token respons target berada pada $M+1 \dots N$:

$$\mathcal{L}_{SFT} = - \sum_{t=M+1}^{N} \log P(x_t \mid x_{<t}; \Theta)$$

Di tingkat tensor, implementasi ini menggunakan mask bernilai `ignore_index = -100` pada seluruh posisi token $1 \dots M$. PyTorch `CrossEntropyLoss` secara internal melewati komputasi gradien untuk index tersebut:

```
Token Indices:  [Tok_1,  Tok_2,  Tok_3,  Tok_4,  Tok_5,  Tok_6,  Tok_7,  EOS]
Token Type:     [Prompt, Prompt, Prompt, Target, Target, Target, Target, Target]
Loss Labels:    [ -100,   -100,   -100,  Tok_4,  Tok_5,  Tok_6,  Tok_7,  EOS ]
                     ▲       ▲       ▲
                     └───────┴───────┴── No gradient computation here!
```

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi end-to-end framework fine-tuning QLoRA modular, dirancang dengan Clean Architecture, penanganan error yang kuat, integrasi FlashAttention-2, loss masking presisi, serta fungsionalitas merging model.

```python
"""
production_qlora_pipeline.py
============================
Enterprise-grade Supervised Fine-Tuning (SFT) engine with QLoRA,
Loss Masking, FlashAttention-2, and Checkpoint Compilation.
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import torch
from datasets import Dataset, load_dataset
from peft import (
    AutoPeftModelForCausalLM,
    LoraConfig,
    PeftModel,
    get_peft_model,
    prepare_model_for_kbit_training,
)
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    PreTrainedModel,
    PreTrainedTokenizerBase,
    Trainer,
    TrainingArguments,
)

# -----------------------------------------------------------------------------
# LOGGING CONFIGURATION
# -----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("QLoRA-Pipeline")


# -----------------------------------------------------------------------------
# CONFIGURATION DATA STRUCTURES
# -----------------------------------------------------------------------------
@dataclass(frozen=True)
class ModelHyperparameters:
    """Konfigurasi hyperparameter dan arsitektur model."""
    base_model_name_or_path: str
    output_dir: Path
    lora_r: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    target_modules: List[str] = field(
        default_factory=lambda: [
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ]
    )
    max_seq_length: int = 2048
    use_flash_attention_2: bool = True


@dataclass(frozen=True)
class TrainingPipelineConfig:
    """Hyperparameter optimasi dan penjadwalan training loop."""
    num_train_epochs: float = 3.0
    per_device_train_batch_size: int = 2
    gradient_accumulation_steps: int = 8
    learning_rate: float = 2e-4
    weight_decay: float = 0.01
    warmup_ratio: float = 0.03
    lr_scheduler_type: str = "cosine"
    logging_steps: int = 10
    save_strategy: str = "steps"
    save_steps: int = 100
    evaluation_strategy: str = "steps"
    eval_steps: int = 100
    save_total_limit: int = 3
    seed: int = 42


# -----------------------------------------------------------------------------
# TOKENIZATION & PREPROCESSING ENGINE
# -----------------------------------------------------------------------------
class InstructionDatasetProcessor:
    """
    Menangani formatting percakapan, tokenisasi, dan loss masking
    hanya pada token yang dihasilkan sistem/assistant (target).
    """

    def __init__(
        self,
        tokenizer: PreTrainedTokenizerBase,
        max_seq_length: int,
    ) -> None:
        self.tokenizer = tokenizer
        self.max_seq_length = max_seq_length

        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
            logger.info("Pad token tidak terdeteksi. Set pad_token = eos_token.")

    def format_and_tokenize(self, example: Dict[str, Any]) -> Dict[str, List[int]]:
        """
        Menyusun prompt berbasis pola percakapan standar, melakukan
        tokenisasi, dan membuat label mask (-100) pada token user.
        
        Format example input:
        {
            "instruction": "Tuliskan query SQL untuk mencari total revenue per cabang.",
            "input": "Tabel sales (branch_id, revenue, transaction_date)",
            "output": "SELECT branch_id, SUM(revenue) FROM sales GROUP BY branch_id;"
        }
        """
        prompt_content = example["instruction"]
        if example.get("input", "").strip():
            prompt_content += f"\nInput tambahan: {example['input']}"

        prompt_text = (
            f"<|im_start|>system\nAnda adalah asisten AI spesialis database enterprise.<|im_end|>\n"
            f"<|im_start|>user\n{prompt_content}<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )
        response_text = f"{example['output']}<|im_end|>"

        prompt_ids = self.tokenizer.encode(
            prompt_text,
            add_special_tokens=False,
            truncation=False,
        )
        response_ids = self.tokenizer.encode(
            response_text,
            add_special_tokens=False,
            truncation=False,
        )

        input_ids = prompt_ids + response_ids
        # -100 adalah representasi default ignore_index pada PyTorch CrossEntropyLoss
        labels = [-100] * len(prompt_ids) + response_ids

        # Truncation manual
        if len(input_ids) > self.max_seq_length:
            input_ids = input_ids[: self.max_seq_length]
            labels = labels[: self.max_seq_length]

        attention_mask = [1] * len(input_ids)

        # Padding manual ke max_seq_length untuk batch konsistensi jika tidak pakai dynamic collator
        pad_length = self.max_seq_length - len(input_ids)
        if pad_length > 0:
            input_ids = input_ids + [self.tokenizer.pad_token_id] * pad_length
            labels = labels + [-100] * pad_length
            attention_mask = attention_mask + [0] * pad_length

        return {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "labels": labels,
        }


# -----------------------------------------------------------------------------
# QLORA TRAINING ENGINE
# -----------------------------------------------------------------------------
class QLoRATrainingEngine:
    """Mengelola siklus inisialisasi model 4-bit, adapter attachment, dan eksekusi SFT."""

    def __init__(
        self,
        model_cfg: ModelHyperparameters,
        train_cfg: TrainingPipelineConfig,
    ) -> None:
        self.model_cfg = model_cfg
        self.train_cfg = train_cfg
        self._validate_environment()

    def _validate_environment(self) -> None:
        if not torch.cuda.is_available():
            raise RuntimeError("Akselerasi CUDA wajib tersedia untuk pelatihan QLoRA.")
        compute_capability = torch.cuda.get_device_capability()
        if self.model_cfg.use_flash_attention_2 and compute_capability[0] < 8:
            logger.warning(
                f"FlashAttention-2 membutuhkan GPU Ampere/Ada/Hopper (Compute Capability >= 8.0). "
                f"Terdeteksi capability {compute_capability}. Menonaktifkan FlashAttention-2."
            )

    def _build_quantization_config(self) -> BitsAndBytesConfig:
        return BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.bfloat16
            if torch.cuda.is_bf16_supported()
            else torch.float16,
        )

    def initialize_tokenizer(self) -> PreTrainedTokenizerBase:
        logger.info(f"Loading Tokenizer: {self.model_cfg.base_model_name_or_path}")
        tokenizer = AutoTokenizer.from_pretrained(
            self.model_cfg.base_model_name_or_path,
            use_fast=True,
            padding_side="right",
            trust_remote_code=True,
        )
        return tokenizer

    def initialize_base_model(self) -> PreTrainedModel:
        bnb_config = self._build_quantization_config()
        attn_impl = (
            "flash_attention_2"
            if self.model_cfg.use_flash_attention_2 and torch.cuda.get_device_capability()[0] >= 8
            else "sdpa"
        )
        logger.info(
            f"Loading Model {self.model_cfg.base_model_name_or_path} dengan presisi NF4 (Attn: {attn_impl})"
        )

        model = AutoModelForCausalLM.from_pretrained(
            self.model_cfg.base_model_name_or_path,
            quantization_config=bnb_config,
            device_map="auto",
            attn_implementation=attn_impl,
            trust_remote_code=True,
        )

        # Persiapkan arsitektur untuk penampungan gradient pada weight terkuantisasi
        model = prepare_model_for_kbit_training(
            model,
            use_gradient_checkpointing=True,
        )
        model.config.use_cache = False  # Wajib dinonaktifkan saat training berlangsung
        return model

    def attach_adapters(self, model: PreTrainedModel) -> PeftModel:
        lora_config = LoraConfig(
            r=self.model_cfg.lora_r,
            lora_alpha=self.model_cfg.lora_alpha,
            target_modules=self.model_cfg.target_modules,
            lora_dropout=self.model_cfg.lora_dropout,
            bias="none",
            task_type="CAUSAL_LM",
        )
        peft_model = get_peft_model(model, lora_config)
        trainable_params, all_param = peft_model.get_nb_trainable_parameters()
        logger.info(
            f"Adapter terpasang. Trainable params: {trainable_params:,} || "
            f"All params: {all_param:,} || Rasio: {100 * trainable_params / all_param:.4f}%"
        )
        return peft_model

    def train(
        self,
        model: PeftModel,
        train_dataset: Dataset,
        eval_dataset: Optional[Dataset] = None,
    ) -> None:
        training_args = TrainingArguments(
            output_dir=str(self.model_cfg.output_dir / "checkpoints"),
            num_train_epochs=self.train_cfg.num_train_epochs,
            per_device_train_batch_size=self.train_cfg.per_device_train_batch_size,
            gradient_accumulation_steps=self.train_cfg.gradient_accumulation_steps,
            learning_rate=self.train_cfg.learning_rate,
            weight_decay=self.train_cfg.weight_decay,
            warmup_ratio=self.train_cfg.warmup_ratio,
            lr_scheduler_type=self.train_cfg.lr_scheduler_type,
            logging_steps=self.train_cfg.logging_steps,
            save_strategy=self.train_cfg.save_strategy,
            save_steps=self.train_cfg.save_steps,
            eval_strategy=self.train_cfg.evaluation_strategy,
            eval_steps=self.train_cfg.eval_steps,
            save_total_limit=self.train_cfg.save_total_limit,
            seed=self.train_cfg.seed,
            bf16=torch.cuda.is_bf16_supported(),
            fp16=not torch.cuda.is_bf16_supported(),
            optim="paged_adamw_8bit",
            gradient_checkpointing=True,
            report_to="none",  # Ubah ke 'wandb' pada enterprise cluster
            dataloader_num_workers=4,
        )

        trainer = Trainer(
            model=model,
            args=training_args,
            train_dataset=train_dataset,
            eval_dataset=eval_dataset,
        )

        logger.info("Memulai execution loop fine-tuning SFT...")
        trainer.train()

        adapter_save_path = self.model_cfg.output_dir / "final_adapter"
        logger.info(f"Menyimpan LoRA adapter weights ke: {adapter_save_path}")
        model.save_pretrained(str(adapter_save_path))


# -----------------------------------------------------------------------------
# ARTIFACT COMPILER (MERGE ENGINE)
# -----------------------------------------------------------------------------
class AdapterMergeEngine:
    """Menggabungkan adapter LoRA ke base model unquantized untuk serving zero-overhead."""

    @staticmethod
    def merge_and_export(
        base_model_path: str,
        adapter_path: Path,
        export_path: Path,
    ) -> None:
        logger.info(f"Memulai proses merging. Base: {base_model_path}, Adapter: {adapter_path}")
        
        # Merge HARUS dilakukan pada presisi penuh/FP16 unquantized, BUKAN mode 4-bit
        base_model = AutoModelForCausalLM.from_pretrained(
            base_model_path,
            torch_dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16,
            device_map="cpu",
            trust_remote_code=True,
        )
        
        peft_model = PeftModel.from_pretrained(base_model, str(adapter_path))
        merged_model = peft_model.merge_and_unload()

        tokenizer = AutoTokenizer.from_pretrained(base_model_path)

        export_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Mengekspor model terkonsolidasi ke {export_path}...")
        merged_model.save_pretrained(str(export_path), safe_serialization=True)
        tokenizer.save_pretrained(str(export_path))
        logger.info("Operasi export selesai secara sukses.")


# -----------------------------------------------------------------------------
# ENTRYPOINT / INTEGRATION TEST EXECUTION
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    MODEL_ID = "mistralai/Mistral-7B-v0.1"  # Menggunakan model open-weight standar
    WORKSPACE_DIR = Path("./enterprise_domain_model")

    model_config = ModelHyperparameters(
        base_model_name_or_path=MODEL_ID,
        output_dir=WORKSPACE_DIR,
        lora_r=16,
        lora_alpha=32,
        max_seq_length=512,  # Disetel pendek untuk keperluan demo script
    )
    
    train_config = TrainingPipelineConfig(
        num_train_epochs=1.0,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=4,
        learning_rate=2e-4,
    )

    try:
        # Inisialisasi engine
        engine = QLoRATrainingEngine(model_config, train_config)
        tok = engine.initialize_tokenizer()

        # Inisialisasi Mock Data untuk simulasi instruction fine-tuning
        mock_data = [
            {
                "instruction": "Ekstrak parameter database dari string koneksi berikut.",
                "input": "Server=tcp:sql-srv.corp.net,1433;Database=OrderDB;User Id=dbadmin;",
                "output": '{"host": "sql-srv.corp.net", "port": 1433, "database": "OrderDB", "user": "dbadmin"}',
            },
            {
                "instruction": "Tuliskan format JSON health status sistem.",
                "input": "Node A normal, latensi 12ms, memory utilization 45%",
                "output": '{"node": "A", "status": "healthy", "latency_ms": 12, "memory_load_pct": 45}',
            }
        ] * 10  # Multiplikasi dummy sampel

        raw_dataset = Dataset.from_list(mock_data)
        processor = InstructionDatasetProcessor(tok, max_seq_length=model_config.max_seq_length)

        logger.info("Memproses dataset dengan loss masking...")
        processed_dataset = raw_dataset.map(
            processor.format_and_tokenize,
            remove_columns=raw_dataset.column_names,
        )

        logger.info(f"Jumlah sampel training siap: {len(processed_dataset)}")

        # Muat model dan pasang adapter
        base_llm = engine.initialize_base_model()
        adapter_llm = engine.attach_adapters(base_llm)

        # Eksekusi training
        engine.train(adapter_llm, train_dataset=processed_dataset)

        logger.info("Pipeline SFT selesai tanpa anomali.")

    except Exception as exc:
        logger.error(f"Kegagalan pipeline fatal: {str(exc)}", exc_info=True)
        sys.exit(1)
```

---

### 7. Edge Cases & Failure Modes

#### 7.1. Catastrophic Forgetting pada Generic Reasoning
*   **Gejala**: Model sangat mahir dalam tugas domain (misal: JSON formatting), namun kemampuan reasoning logis dasar, general knowledge, atau general English/Indonesian grammar hancur total (penurunan drastis pada benchmark umum seperti ARC atau MMLU).
*   **Root Cause**: Learning rate terlalu tinggi, rank $r$ LoRA terlalu besar menyerupai full fine-tuning, atau target dataset instruksi terlalu sempit tanpa regularisasi.
*   **Mitigasi**:
    *   Suntikkan 5%–10% data generik instruksi serbaguna (*replay dataset*, misal: subset UltraChat atau LIMA) ke dalam dataset pelatihan domain Anda.
    *   Terapkan parameter weight decay ($0.01 - 0.1$) dan batasi epoch $\le 3$.

#### 7.2. Instabilitas Gradien & NaN Loss Spikes
*   **Gejala**: Training loss turun stabil, lalu tiba-tiba pada step tertentu bernilai `NaN`, dan model menghasilkan output string kosong tak berujung.
*   **Root Cause**: Aktivasi ekstrem (*activation outliers*) yang keluar dari jangkauan representasi saat melewati layer NormalFloat4 atau perhitungan presisi rendah FP16.
*   **Mitigasi**:
    *   Gunakan tipe komputasi `bfloat16` (`bnb_4bit_compute_dtype=torch.bfloat16`). BF16 memiliki rentang dinamis eksponen yang identik dengan FP32 (8-bit exponent), sehingga kebal terhadap underflow/overflow dibanding FP16 standar (5-bit exponent).
    *   Pasang *Gradient Clipping* ketat (`max_grad_norm=0.3`).

#### 7.3. Cross-Contamination pada Sequence Packing
*   **Gejala**: Model menghasilkan output tugas A yang tercampur dengan fragmen teks dari tugas B.
*   **Root Cause**: Menggabungkan banyak contoh sequence ke dalam satu window konteks tanpa menerapkan *Attention Mask Block Diagonal*. Akibatnya, token di teks kedua bisa melihat (*attend to*) token dari teks pertama dalam mekanisme self-attention.
*   **Mitigasi**: Pastikan menggunakan implementasi FlashAttention-2 unpadded (`flash_attn_varlen_func`) yang memisahkan dokumen individual via tensor `cu_seqlens` (cumulative sequence lengths).

#### 7.4. Quantization Clipping pada MoE (Mixture of Experts)
*   **Gejala**: Model berbasis MoE (misal: Mixtral-8x7B) mengalami penurunan akurasi signifikan setelah kuantisasi 4-bit standar.
*   **Root Cause**: Router gate layer pada MoE sangat sensitif terhadap deviasi bobot terkecil. Kuantisasi pada `gate` layers merusak routing representasi ke experts.
*   **Mitigasi**: Kecualikan module router/gate dari kuantisasi dan LoRA targeting (`modules_to_save=["w1", "w2"]`, jangan quantize layer selector).

---

### 8. Trade-offs & Alternatif Solusi

| Dimensi Evaluasi | In-Context Learning (Prompt) | Retrieval-Augmented Generation (RAG) | Parameter-Efficient (QLoRA) | Full Fine-Tuning (FFT) | Continual Pre-Training |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Kebutuhan VRAM GPU** | Nol (Pure API) / Base Inference | Nol (Pure API) / Base Inference | **Rendah (1x 24GB VRAM)** | Sangat Tinggi (8x 80GB VRAM) | Ekstrem (Cluster Multi-Node) |
| **Biaya Inisiasi / Compute**| Nol | Rendah (Setup Vector DB) | **Menengah ($10 - $100)** | Tinggi ($500 - $5,000) | Ekstrem ($10k - $100k+) |
| **Kecepatan Update Pengetahuan**| Realtime (Ganti context) | Detik - Menit (Index DB) | **Jam - Hari (Retrain adapter)**| Hari - Minggu | Minggu - Bulan |
| **Kemampuan Menanamkan Gaya/Format**| Terbatas (Tergantung window) | Sangat Terbatas | **Sangat Tinggi (Deterministik)**| Absolut | Rendah (Hanya representasi) |
| **Penambahan Pengetahuan Faktual Baru**| Rendah | **Tinggi (Melalui dokumen)**| Menengah (Rentan halusinasi) | Tinggi | **Sangat Tinggi** |
| **Latensi Inferensi (TTFT)** | Buruk (Prompt sangat panjang) | Buruk (Context bertambah) | **Optimal (Prompt ramping)** | Optimal (Prompt ramping) | Optimal |
| **Kompleksitas Operasional** | Trivial | Menengah (Pipeline Sync) | **Tinggi (MLOps Lifecycle)** | Sangat Tinggi | Sangat Tinggi |

#### Aturan Pengambilan Keputusan Arsitektur:
1.  **Gunakan RAG jika**: Dokumen rujukan berubah setiap hari/menit, model harus memberikan bukti sitasi eksplisit, atau enterprise melarang transfer data ke pelatihan bobot.
2.  **Gunakan QLoRA jika**: Anda perlu mengajari model sintaksis format baru (misal: code framework privat, output JSON terverifikasi), mengubah tone conversational persona secara konsisten, atau memangkas latensi prompt.
3.  **Kombinasikan RAG + QLoRA (Pola Terbaik Enterprise)**: Gunakan QLoRA untuk melatih model memahami cara mengekstrak informasi dan menyusun response dari konteks dokumen (*reasoning format*), lalu gunakan RAG sebagai penyedia fakta teraktual (*dynamic knowledge retrieval*).

---

### 9. Best Practices & Standard Industri

1.  **Target Modules Optimal**: Jangan hanya melatih attention projections (`q_proj`, `v_proj`). Riset modern menunjukkan bahwa menyertakan MLP layers (`gate_proj`, `up_proj`, `down_proj`) pada LoRA menghasilkan peningkatan performa adaptasi domain hingga setara dengan Full Fine-Tuning.
2.  **Formula Konfigurasi LoRA**:
    *   Set $r = 16$ atau $r = 32$. Menaikkan $r > 64$ umumnya menghasilkan *diminishing returns* dan risiko overfitting meningkat.
    *   Pegang rasio $\alpha = 2 \times r$ (misal: $r=16, \alpha=32$). Ini adalah titik awal standar industri untuk stabilitas learning rate.
    *   Gunakan LoRA dropout $0.05$ untuk dataset kecil ($<10.000$ baris) guna regularisasi, atau $0.0$ untuk dataset besar.
3.  **Data Quality over Data Quantity**: Standard industri (mengacu pada LIMA: *Less Is More for Alignment*) membuktikan bahwa **1.000 data instruksi domain yang dikurasi manual oleh expert** jauh melampaui performa 100.000 data hasil scraping tanpa kurasi ketat yang mengandung noise.
4.  **Audit Data Contamination**: Sebelum fine-tuning, jalankan algoritma overlap n-gram hashing (misal: MinHash LSH) antara data pelatihan internal dengan validation benchmark publik untuk memastikan performa yang dievaluasi bukan hasil hafalan memorisasi.
5.  **Multi-Adapter Architecture**: Untuk melayani ratusan klien B2B dengan gaya unik, jangan deploy 100 model terpisah. Deploy satu base engine via runtime seperti **vLLM Multi-LoRA**, di mana adapter spesifik di-load ke VRAM secara dinamis per request header via parameter `model="base_model:client_adapter_01"`.

---

### 10. Hands-on Lab Exercise

#### Skenario Lab
Anda adalah Lead AI Engineer pada institusi keuangan. Bisnis membutuhkan model yang mampu mengonversi instruksi audit berbahasa natural Indonesia menjadi representasi structured audit metadata (format JSON ketat) tanpa merusak kapabilitas bahasa model dasar.

#### Spesifikasi Hardware Minimum:
*   1x GPU NVIDIA (VRAM $\ge 16$ GB, misal: RTX 4080, RTX 3090, T4, atau Google Colab Instance A100/V100).
*   Disk Space: $\ge 30$ GB.

#### Langkah 1: Persiapan Lingkungan & Dependensi
Eksekusi di terminal lingkungan virtual Python (3.10+):

```bash
pip install -q -U \
    torch==2.3.0 \
    transformers==4.41.0 \
    peft==0.11.1 \
    bitsandbytes==0.43.1 \
    datasets==2.19.1 \
    accelerate==0.30.1
```

#### Langkah 2: Konstruksi Golden Dataset
Buat file `audit_dataset.jsonl`:

```json
{"instruction": "Identifikasi anomali transaksi akun nasabah", "input": "Debit Rp 450.000.000 pada pukul 03.12 WIB di terminal luar negeri.", "output": "{\"risk_level\": \"CRITICAL\", \"flags\": [\"UNUSUAL_HOURS\", \"OFFSHORE_TRANSACTION\"], \"action\": \"BLOCK_TEMPORARY\"}"}
{"instruction": "Identifikasi anomali transaksi akun nasabah", "input": "Penarikan tunai ATM Rp 500.000 di Jakarta Pusat pukul 14.00 WIB.", "output": "{\"risk_level\": \"LOW\", \"flags\": [], \"action\": \"ALLOW\"}"}
{"instruction": "Identifikasi anomali transaksi akun nasabah", "input": "Transfer Rp 98.000.000 sebanyak 5 kali berturut-turut dalam rentang 10 menit.", "output": "{\"risk_level\": \"HIGH\", \"flags\": [\"STRUCTURING_ATTEMPT\", \"VELOCITY_SPIKE\"], \"action\": \"REQUIRE_MANUAL_VERIFICATION\"}"}
{"instruction": "Identifikasi anomali transaksi akun nasabah", "input": "Pembelian e-commerce merchant domestik Rp 1.250.000 via 3D Secure OTP valid.", "output": "{\"risk_level\": \"LOW\", \"flags\": [\"OTP_VALIDATED\"], \"action\": \"ALLOW\"}"}
```

#### Langkah 3: Eksekusi Fine-Tuning Script
Jalankan file implementasi `production_qlora_pipeline.py` yang telah disediakan pada bagian 6, pastikan variabel dataset diarahkan ke file `audit_dataset.jsonl`.

#### Langkah 4: Evaluasi Inferensi Model Teradaptasi (Runtime Adapter)
Buat file `verify_adapter.py` untuk menguji adapter tanpa menggabungkannya terlebih dahulu:

```python
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from peft import PeftModel

BASE_MODEL = "mistralai/Mistral-7B-v0.1"
ADAPTER_PATH = "./enterprise_domain_model/final_adapter"

tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.float16,
)

base_model = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL,
    quantization_config=bnb_config,
    device_map="auto",
)

# Attach adapter
model = PeftModel.from_pretrained(base_model, ADAPTER_PATH)
model.eval()

# Inference Test Case
test_prompt = (
    "<|im_start|>system\nAnda adalah asisten AI spesialis database enterprise.<|im_end|>\n"
    "<|im_start|>user\nIdentifikasi anomali transaksi akun nasabah\n"
    "Input tambahan: Pembelian software enterprise US$ 50.000 dari IP address Rusia pada akun personal.<|im_end|>\n"
    "<|im_start|>assistant\n"
)

inputs = tokenizer(test_prompt, return_tensors="pt").to("cuda")

with torch.no_grad():
    outputs = model.generate(
        **inputs,
        max_new_tokens=100,
        temperature=0.1,  # Rendah untuk memaksimalkan determinisme output
        do_sample=False,
    )

response = tokenizer.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)
print("\n--- INFERRED RESPONSE ---")
print(response)
```

#### Kriteria Kelulusan Evaluasi Lab:
1.  Model menghasilkan payload JSON valid dengan field yang tepat: `risk_level`, `flags`, dan `action`.
2.  Loss training mengalami konvergensi monotonik ke bawah tanpa grafik NaN.
3.  VRAM utilization tidak melebihi 10 GB selama training berlangsung (diverifikasi melalui `nvidia-smi`).