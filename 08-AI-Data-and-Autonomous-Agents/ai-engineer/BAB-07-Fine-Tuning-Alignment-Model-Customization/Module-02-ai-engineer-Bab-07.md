# Kurikulum Enterprise AI Engineer
## Kategori: 08-AI-Data-and-Autonomous-Agents
### Bab 07: Fine-Tuning, Alignment, & Model Customization
#### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Merancang dan Mengimplementasikan Arsitektur Parameter-Efficient Fine-Tuning (PEFT) Lanjutan**: Menguasai formulasi matematis dan implementasi DoRA (Weight-Decomposed Low-Rank Adaptation), QLoRA dengan NormalFloat4 (NF4), dan RSLoRA (Rank-Stabilized LoRA) pada Large Language Models (LLM) skala 7B hingga 70B parameter.
- **Mengorkestrasikan Distributed Alignment Training Pipeline**: Mengonfigurasi dan menjalankan alignment berbasis preferensi non-RL (*Direct Preference Optimization* / DPO, *Odds Ratio Preference Optimization* / ORPO, dan *Kahneman-Tversky Optimization* / KTO) memanfaatkan Fully Sharded Data Parallel (FSDP) dan DeepSpeed ZeRO-3.
- **Mengeliminasi Memory Bottlenecks & Instabilitas Numerik**: Menganalisis konsumsi VRAM secara analitis (parameter, gradient, optimizer states, dan activation cache) serta menerapkan mitigasi terhadap *catastrophic forgetting*, *KL-divergence drift*, dan degradasi generatif.
- **Membangun Sistem Multi-LoRA Serving Skala Enterprise**: Menerapkan dynamic adapter serving dengan vLLM/Punica-based paging untuk melayani ratusan adapter kustom di atas single shared-base-model GPU cluster secara konkuren dengan zero cold-start overhead.

---

### 2. Prerequisite

Untuk menguasai materi ini, engineer harus memiliki kompetensi:
- **Sistem Distribusi & GPU Computing**: Pemahaman memori CUDA, Tensor Cores, FlashAttention-2/3 kernel execution, dan primitif kolektif NCCL (`All-Reduce`, `Reduce-Scatter`, `All-Gather`).
- **Deep Learning Frameworks**: Kemampuan tingkat lanjut dalam PyTorch (2.x), Hugging Face `transformers`, `peft`, `accelerate`, dan `trl`.
- **Foundational Fine-Tuning Knowledge**: Memahami konsep dasar transfer learning, causal language modeling cross-entropy loss, dan implementasi vanilla LoRA standar.
- **Aljabar Linear & Optimasi Lanjut**: Dekomposisi matriks Singular Value Decomposition (SVD), normalisasi residual, dan optimizer berbasis momentum (AdamW, bitsandbytes 8-bit/4-bit).

---

### 3. Concept & Internal Architecture

#### 3.1 Dekonstruksi Matematis: Dari Vanilla LoRA ke DoRA dan RSLoRA

Pada vanilla LoRA, adaptasi bobot model dilakukan dengan membekukan bobot asli $W_0 \in \mathbb{R}^{d \times k}$ dan menginjeksikan low-rank decomposition matrices:

$$W = W_0 + \Delta W = W_0 + \frac{\alpha}{r} (B \cdot A)$$

di mana $A \in \mathbb{R}^{r \times k} \sim \mathcal{N}(0, \sigma^2)$, $B \in \mathbb{R}^{d \times r} = 0$, dan $r \ll \min(d, k)$.

##### Bottleneck Skalabilitas pada Rank Tinggi (RSLoRA)
Pada rank $r$ yang besar, penskalaan standar $\frac{\alpha}{r}$ menyebabkan *gradient collapse* atau pembelajaran yang terlalu lambat karena laju adaptasi berkurang seiring pembesaran $r$. RSLoRA (Rank-Stabilized LoRA) memodifikasi faktor skala ini menjadi:

$$\gamma = \frac{\alpha}{\sqrt{r}}$$

Stabilisasi ini menjaga variansi norm aktivasi tetap stabil ketika kapasitas adapter ditingkatkan ke rank $r = 64$ atau $r = 128$.

##### Dekomposisi Magnitudo dan Arah (DoRA)
Weight-Decomposed Low-Rank Adaptation (DoRA) memecah matriks bobot $W$ menjadi komponen magnitudo $\|W\|_c$ (vektor $m \in \mathbb{R}^{1 \times k}$) dan komponen arah (matriks unit $V$):

$$W = m \odot \frac{V}{\|V\|_c} = m \odot \frac{W_0 + B A}{\|W_0 + B A\|_c}$$

di mana $\|\cdot\|_c$ adalah norm Euclidean L2 dari setiap kolom matriks, dan $\odot$ merepresentasikan perkalian broadcast per kolom. DoRA secara independen mengoptimalkan arah adaptasi ($BA$) dan skala magnitudo ($m$). Analisis gradien membuktikan bahwa DoRA merefleksikan pola pembelajaran Full Fine-Tuning (FFT) jauh lebih dekat dibanding LoRA konvensional dengan memisahkan dinamika rotasi dan translasi fitur pada representasi laten.

```
+-------------------------------------------------------------------------+
|                              DoRA FORWARD PASS                          |
|                                                                         |
| Input X                                                                 |
|   |                                                                     |
|   +-----------------------+-----------------------+                     |
|   |                       |                       |                     |
|   v                       v                       v                     |
| [Frozen W_0]           [Matrix A]              [Norm ||W_0 + BA||_c]    |
|   |                       |                       |                     |
|   |                       v                       |                     |
|   |                    [Matrix B]                 |                     |
|   |                       |                       |                     |
|   +--------> (+) <--------+                       |                     |
|               |                                   |                     |
|               v                                   v                     |
|        [ Direction V ] --------------------> ( Division )               |
|                                                   |                     |
|                                                   v                     |
|     [ Learned Magnitude m ] --------------> ( Broadcast x )             |
|                                                   |                     |
|                                                   v                     |
|                                             Output Tensor Y             |
+-------------------------------------------------------------------------+
```

#### 3.2 Kuantisasi NF4 dan Double Quantization (QLoRA)
QLoRA memperkenalkan tiga inovasi arsitektur untuk menekan alokasi VRAM hingga ~75% tanpa degradasi perplexity yang signifikan:
1. **NormalFloat4 (NF4) Data Type**: Kuantisasi informasi-teoretis optimal untuk bobot berdistribusi normal $\mathcal{N}(0, \sigma^2)$. Titik kuantisasi $q_i$ dipilih sedemikian rupa sehingga probabilitas $P(q_i \le x \le q_{i+1}) = \frac{1}{2^k}$.
2. **Double Quantization (DQ)**: Kuantisasi terhadap konstanta kuantisasi (quantization constants/scaling factors). Mengurangi jejak memori dari 0.5 bit per parameter menjadi 0.127 bit per parameter.
3. **Paged Optimizers**: Memanfaatkan CUDA Unified Memory untuk melakukan transfer otomatis state optimizer yang jarang diakses antara GPU VRAM dan CPU RAM saat terjadi lonjakan aktivasi sequence length panjang.

#### 3.3 Dynamic Adapter Serving: Punica Kernel & Multi-LoRA Batching
Dalam melayani berbagai model hasil kustomisasi di lingkungan produksi, pola tradisional mengharuskan deployment satu container/pod per fine-tuned model, yang memicu pemborosan VRAM luar biasa besar.

Arsitektur Multi-LoRA modern (seperti implementasi vLLM berbasis Punica / S-LoRA) memuat satu bobot *Base Model* ke VRAM (misal: LLaMA-3-70B), lalu menempatkan adapter-adapter LoRA ke pool memori terpisah (Paged Memory).

Operasi kernel Multi-Segment Batched Matrix Multiplication (BMM) mengeksekusi:

$$Y_i = X_i W_0 + X_i A_{k(i)} B_{k(i)}$$

di mana $k(i)$ adalah ID adapter yang dipetakan secara dinamis ke request urutan ke-$i$ di dalam micro-batch yang sama. Operasi ini berjalan dengan satu kernel FlashAttention gabungan tanpa menimbulkan cold-start overhead saat berganti konteks adapter antar-request.

```
Multi-LoRA Serving Paged Memory Layout:
=============================================================================
GPU VRAM:
+---------------------------------------------------------------------------+
| BASE MODEL WEIGHTS (Frozen W_0) - Shared across all inference requests    |
| [Llama-3-70B: Layers 1-80 in 4-bit / 8-bit] (35 - 70 GB VRAM)             |
+---------------------------------------------------------------------------+
| Dynamic Adapter Pool (Paged KV & Adapter Weights Allocation)              |
| [Slot 0: Adapter FinTech (A_1, B_1)] -> Process Request #102, #105        |
| [Slot 1: Adapter Legal   (A_2, B_2)] -> Process Request #103              |
| [Slot 2: Adapter Medical (A_3, B_3)] -> Process Request #104, #106        |
| [Free Paged Pools ...]                                                    |
+---------------------------------------------------------------------------+
```

#### 3.4 Alignment Tanpa Reinforcement Learning: DPO, ORPO, dan KTO

##### Direct Preference Optimization (DPO)
DPO mereparameterisasi fungsi *Reward Model* $R(x, y)$ pada RLHF standar menggunakan probabilitas implisit dari policy $\pi_\theta$ dan reference model $\pi_{\text{ref}}$:

$$R^*(x, y) = \beta \log \frac{\pi_\theta(y|x)}{\pi_{\text{ref}}(y|x)} + \beta \log Z(x)$$

Melalui substitusi turunan Bradley-Terry preference model, loss function DPO diformulasikan langsung tanpa memerlukan Actor-Critic RL loop terpisah:

$$\mathcal{L}_{\text{DPO}}(\pi_\theta; \pi_{\text{ref}}) = -\mathbb{E}_{(x, y_w, y_l) \sim \mathcal{D}} \left[ \log \sigma \left( \beta \log \frac{\pi_\theta(y_w|x)}{\pi_{\text{ref}}(y_w|x)} - \beta \log \frac{\pi_\theta(y_l|x)}{\pi_{\text{ref}}(y_l|x)} \right) \right]$$

di mana:
- $x$: prompt konteks input.
- $y_w$: respons yang disukai (*winning/chosen response*).
- $y_l$: respons yang ditolak (*losing/rejected response*).
- $\beta$: parameter penalti divergensi KL terhadap model acuan baseline $\pi_{\text{ref}}$ (umumnya bernilai $0.05 - 0.2$).
- $\sigma$: fungsi sigmoid standar.

##### Odds Ratio Preference Optimization (ORPO)
ORPO meniadakan kebutuhan akan Reference Model $\pi_{\text{ref}}$ secara keseluruhan, menghemat 50% alokasi VRAM saat proses alignment dengan menggabungkan Negative Log-Likelihood (NLL) SFT loss dengan Odds Ratio penalti preferensi:

$$\mathcal{L}_{\text{ORPO}} = \mathcal{L}_{\text{SFT}} + \lambda_{\text{OR}} \mathcal{L}_{\text{OR}}$$

$$\mathcal{L}_{\text{OR}} = -\log \sigma \left( \log \frac{\text{odds}_\theta(y_w|x)}{\text{odds}_\theta(y_l|x)} \right), \quad \text{di mana } \text{odds}_\theta(y|x) = \frac{P_\theta(y|x)}{1 - P_\theta(y|x)}$$

---

### 4. Why & What

| Paradigma Alignment & Tuning | Algoritma Target | Keunggulan Utama | Bottleneck Komputasi & Resiko | Use Case Terbaik |
| :--- | :--- | :--- | :--- | :--- |
| **Rank-Stabilized PEFT** | RSLoRA / DoRA | Mencegah representational collapse pada rank tinggi ($r \ge 64$); DoRA mencapai akurasi setara Full Parameter Fine-Tuning. | Overload komputasi DoRA ~15-20% lebih lambat per step dibanding LoRA vanilla akibat normalisasi norm matriks. | Domain adaptation mendalam (Medical, Legal, Code generation) dengan constraint VRAM. |
| **Quantized Training** | QLoRA (NF4 + DQ) | Fine-tuning model 70B parameter pada satu node 4x RTX 4090/A100 (24GB-80GB) dengan memori minimum. | Dequantization on-the-fly memperlambat backward pass (~20-30% degradasi throughput dibanding bfloat16). | Experimentation budget-constrained, edge/on-premise enterprise tuning. |
| **Implicit RL Alignment** | DPO | Tidak memerlukan pemodelan Reward Model eksplisit; proses pelatihan deterministik dan stabil (tanpa PPO instabilitas). | Rentan over-fitting pada dataset preferensi bising (*label noise*); membutuhkan memory snapshot $\pi_{\text{ref}}$. | Human-value alignment, perbaikan safety/toxicity, dan stylistic formatting model. |
| **Monolithic Alignment** | ORPO | Zero-reference model overhead. Menggabungkan SFT dan preference learning dalam single training phase. | Penyesuaian hyperparameter $\lambda_{\text{OR}}$ sangat sensitif terhadap rasio panjang respons $y_w$ dan $y_l$. | Pipeline continuous learning dengan throughput tinggi dan resource GPU terbatas. |

---

### 5. How: End-to-End Enterprise Training Pipeline

```
Pipeline Alignment & Produksi Multi-LoRA:
=============================================================================
[Raw Enterprise Data] -> [Curasi & Dedup (MinHash)] -> [Synthetic Expansion (Evol-Instruct)]
                                                                    |
                                                                    v
                                                     [Supervised Fine-Tuning (SFT)]
                                                     (Target: Base Model -> SFT Model)
                                                                    |
                                                                    v
                                                     [Preference Pair Generation]
                                                     (Generate N Responses -> LLM Judge)
                                                                    |
                                                                    v
                                                     [Alignment: DPO / ORPO Optimization]
                                                     (FSDP / DeepSpeed ZeRO-3)
                                                                    |
                                                                    v
                                                     [Model Evaluation & Benchmarking]
                                                     (MT-Bench, Perplexity, Safety Guard)
                                                                    |
                                                                    v
                                                     [Export: SafeTensors Adapter]
                                                                    |
                                                                    v
                                                     [Multi-LoRA Dynamic Serving (vLLM)]
```

#### Breakdown Eksekusi:
1. **Data Synthesis & Cleansing**: Menggunakan teknik Evol-Instruct untuk menghasilkan data kompleksitas tinggi secara terdistribusi. Menjalankan filter heuristik dan model-based filter untuk menghapus degradasi token repetition.
2. **Phase 1: Supervised Fine-Tuning (SFT)**: Menyetel instruksi dasar menggunakan model PEFT DoRA/RSLoRA untuk menyelaraskan token distribution ke format obrolan (ChatML atau Llama-3 format).
3. **Phase 2: Preference Generation**: Menggunakan model SFT untuk men-generate $k$ variasi respons. Menggunakan ensemble reward model / LLM-as-a-judge untuk menetapkan $y_w$ (chosen) dan $y_l$ (rejected).
4. **Phase 3: Preference Optimization**: Menjalankan DPO/ORPO. Menjaga model terdistribusi via PyTorch FSDP (ZeRO-3 style sharding) untuk menangani model paralelisme lintas node.
5. **Phase 4: Deployment**: Serialisasi bobot adapter ke format `.safetensors`. Muat base model di inference engine (vLLM) dengan `--enable-lora`, dan inject adapter secara on-demand via routing request.

---

### 6. Analogy & Diagram ASCII

#### Analogi Sederhana: Tim Restoran Bintang Lima
- **Base Model (Frozen $W_0$)**: Adalah Master Chef berpengalaman tinggi yang menguasai teknik dasar memasak segala jenis hidangan internasional, namun tidak mengetahui resep rahasia internal restoran Anda.
- **LoRA Vanilla**: Asisten juru masak yang diberi instruksi singkat berupa rangkuman resep. Jika instruksi terlalu panjang (rank besar), asisten mulai bingung dan kehilangan fokus (gradient collapse).
- **DoRA**: Memisahkan arahan menjadi dua: (1) **Magnitudo** (seberapa tajam bumbu harus terasa: asin, manis, pedas) dan (2) **Arah** (kombinasi bahan mana yang harus dicampur). Hasil masakan menjadi presisi setara sang Master Chef belajar dari nol.
- **DPO Alignment**: Proses mencicip masakan di mana sang Chef disodori dua piring: Piring A (masakan sempurna) dan Piring B (masakan keasinan). Chef langsung mengoreksi tekniknya berdasarkan selisih rasa kedua piring tersebut, tanpa perlu juri pihak ketiga (Reward Model RL) menilai skor 1-10 di setiap tahap proses.

```
       LoRA vs DoRA Parameter Space Separation
       ----------------------------------------
       
       LoRA Adaptation:
       W = W_0 + B x A  --> Perubahan magnitudo dan arah terikat 
                            dalam satu kalkulasi matriks gradien terdekomposisi.

       DoRA Adaptation:
               Direction Component (V)
              /
             v
       W = m  *  ( (W_0 + BA) / ||W_0 + BA|| )
           ^
            \
             Magnitude Scalar Component (m)
       
       Memungkinkan adaptasi orientasi fitur (knowledge domain)
       tanpa merusak stabilitas skala bobot representasi pretrained base model.
```

---

### 7. Code Implementation: Enterprise-Grade Production Pipeline

Berikut adalah arsitektur kode standar industri yang memuat implementasi DPO dengan DoRA dan integrasi DeepSpeed ZeRO-3, serta script deployment Multi-LoRA menggunakan vLLM.

#### 7.1 Script Training: DPO Pipeline dengan DoRA & PEFT (`train_dpo_advanced.py`)

```python
#!/usr/bin/env python3
"""
Enterprise Alignment Training Pipeline: DPO with DoRA (Weight-Decomposed Low-Rank Adaptation)
Designed for PyTorch Distributed / DeepSpeed Engine execution.
"""

import os
import sys
import logging
from dataclasses import dataclass, field
from typing import Dict, Optional

import torch
from datasets import load_dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    HfArgumentParser,
    TrainingArguments,
)
from peft import LoraConfig, PeftModel, get_peft_model, prepare_model_for_kbit_training
from trl import DPOTrainer, DPOConfig

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


@dataclass
class ModelArguments:
    model_name_or_path: str = field(
        metadata={"help": "Path to base pretrained model or Hugging Face hub ID."}
    )
    torch_dtype: str = field(
        default="bfloat16",
        metadata={"help": "PyTorch precision: 'bfloat16' or 'float16'."},
    )
    use_dora: bool = field(
        default=True,
        metadata={"help": "Enable Weight-Decomposed Low-Rank Adaptation (DoRA)."},
    )
    lora_r: int = field(default=64, metadata={"help": "LoRA attention dimension rank."})
    lora_alpha: int = field(default=128, metadata={"help": "LoRA scaling alpha factor."})
    lora_dropout: float = field(default=0.05, metadata={"help": "LoRA dropout probability."})


@dataclass
class DataArguments:
    dataset_name_or_path: str = field(
        metadata={"help": "Dataset containing preference pairs (prompt, chosen, rejected)."}
    )
    max_length: int = field(
        default=2048, metadata={"help": "Maximum token sequence length."}
    )
    max_prompt_length: int = field(
        default=1024, metadata={"help": "Maximum token sequence length for prompt."}
    )


def initialize_peft_dora_model(
    model_args: ModelArguments, compute_dtype: torch.dtype
) -> AutoModelForCausalLM:
    """Loads base model with memory optimizations and wraps with DoRA adapters."""
    logger.info(f"Loading Base Model: {model_args.model_name_or_path}")

    # Konfigurasi Quantization BitsAndBytes jika VRAM terbatas
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=compute_dtype,
        bnb_4bit_use_double_quant=True,
    )

    model = AutoModelForCausalLM.from_pretrained(
        model_args.model_name_or_path,
        quantization_config=bnb_config,
        device_map={"": int(os.environ.get("LOCAL_RANK", "0"))},
        torch_dtype=compute_dtype,
        attn_implementation="flash_attention_2",
        trust_remote_code=False,
    )

    model = prepare_model_for_kbit_training(
        model, use_gradient_checkpointing=True
    )

    peft_config = LoraConfig(
        r=model_args.lora_r,
        lora_alpha=model_args.lora_alpha,
        lora_dropout=model_args.lora_dropout,
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
        bias="none",
        task_type="CAUSAL_LM",
        use_dora=model_args.use_dora,  # Enable DoRA decomposition
    )

    model = get_peft_model(model, peft_config)
    model.print_trainable_parameters()
    return model


def main() -> None:
    parser = HfArgumentParser((ModelArguments, DataArguments, DPOConfig))
    model_args, data_args, training_args = parser.parse_args_into_dataclasses()

    compute_dtype = (
        torch.bfloat16 if model_args.torch_dtype == "bfloat16" else torch.float16
    )

    tokenizer = AutoTokenizer.from_pretrained(
        model_args.model_name_or_path, trust_remote_code=False
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # Inisialisasi Model Policy (Active Model)
    policy_model = initialize_peft_dora_model(model_args, compute_dtype)

    logger.info(f"Loading preference dataset from: {data_args.dataset_name_or_path}")
    raw_dataset = load_dataset(data_args.dataset_name_or_path)

    # Inisialisasi DPO Trainer
    # Catatan: Ketika menggunakan PEFT/LoRA pada model target, TRL secara internal
    # mengalokasikan null adapter context untuk kalkulasi reference log-probs
    # tanpa menduplikasi base model di memory secara fisik.
    dpo_trainer = DPOTrainer(
        model=policy_model,
        ref_model=None,  # Handled implicitly by PEFT integration inside TRL
        args=training_args,
        train_dataset=raw_dataset["train"],
        eval_dataset=raw_dataset.get("test", None),
        tokenizer=tokenizer,
        peft_config=None,  # Sudah di-wrap secara eksplisit
        max_length=data_args.max_length,
        max_prompt_length=data_args.max_prompt_length,
        beta=0.1,  # Parameter regularisasi KL divergence
    )

    logger.info("Executing DPO Optimization Phase...")
    dpo_trainer.train()

    logger.info(f"Saving Fine-Tuned Adapters to {training_args.output_dir}")
    policy_model.save_pretrained(training_args.output_dir)
    tokenizer.save_pretrained(training_args.output_dir)
    logger.info("Alignment Training Complete.")


if __name__ == "__main__":
    main()
```

#### 7.2 Konfigurasi Akselerasi Training Distributed (`ds_zero3_config.json`)

```json
{
  "fp16": {
    "enabled": "auto"
  },
  "bf16": {
    "enabled": "auto"
  },
  "zero_optimization": {
    "stage": 3,
    "offload_optimizer": {
      "device": "cpu",
      "pin_memory": true
    },
    "offload_param": {
      "device": "none"
    },
    "overlap_comm": true,
    "contiguous_gradients": true,
    "sub_group_size": 1e9,
    "reduce_bucket_size": "auto",
    "stage3_prefetch_bucket_size": "auto",
    "stage3_param_persistence_threshold": "auto",