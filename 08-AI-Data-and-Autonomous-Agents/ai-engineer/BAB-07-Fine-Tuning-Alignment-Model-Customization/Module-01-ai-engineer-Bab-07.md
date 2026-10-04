# Kurikulum AI Engineer
## Kategori 08: AI Data and Autonomous Agents
### Bab 07: Fine-Tuning, Alignment & Model Customization
#### Modul 01: Parameter-Efficient Fine-Tuning (PEFT) Foundations & QLoRA Architecture

---

### 1. Learning Objectives (Spesifik & Terukur)

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Mengkuantifikasi Kebutuhan Memori GPU (VRAM):** Menghitung profil alokasi memori (parameter, gradien, *optimizer states*, dan *activations*) antara *Full Parameter Fine-Tuning*, LoRA (*Low-Rank Adaptation*), dan QLoRA (*Quantized LoRA*) dengan presisi byte matematis.
2. **Membedah & Mengimplementasikan Matematika LoRA:** Merekonstruksi dekomposisi matriks $W_0 + \Delta W = W_0 + \frac{\alpha}{r}(B \cdot A)$ dari nol menggunakan PyTorch dasar, termasuk inisialisasi skalar dan pemahaman *intrinsic rank hypothesis*.
3. **Mengonfigurasi Pipeline QLoRA Enterprise-Grade:** Mengimplementasikan kuantisasi 4-bit *NormalFloat* (NF4), *Double Quantization* (DQ), dan *Paged Optimizers* menggunakan pustaka `transformers`, `peft`, dan `bitsandbytes`.
4. **Mencegah Degradasi Model & Instabilitas Training:** Mendiagnosis serta memitigasi *catastrophic forgetting*, *loss spikes*, dan *precision underflow* menggunakan *Bfloat16 mixed-precision* dan *gradient checkpointing*.
5. **Menerapkan Adapter Management & Deployment:** Menggabungkan (*merge & unload*) bobot adapter ke *base model* untuk deployment berlatensi rendah atau mendesain arsitektur *multi-tenant adapter swapping* untuk *inference engine*.

---

### 2. Concept Overview (Mental Model & Teori Inti)

Secara historis, adaptasi model bahasa besar (LLM) untuk domain spesifik dilakukan melalui *Full Parameter Fine-Tuning* (FFT). Pada FFT, seluruh parameter $\theta$ diperbarui melalui *backpropagation*. Jika model memiliki parameter berjumlah $\Phi$, maka optimizer seperti AdamW memerlukan penyimpanan:
- Bobot model (FP16/BF16): $2\Phi$ bytes
- Gradien (FP16/BF16): $2\Phi$ bytes
- Status Optimizer AdamW (FP32 *first moment* + FP32 *second moment* + FP32 *master weights*): $(4 + 4 + 4)\Phi = 12\Phi$ bytes

Total konsumsi memori statis sebelum alokasi *activation cache* adalah $\approx 16\Phi$ hingga $20\Phi$ bytes. Untuk model 70B parameter, FFT membutuhkan minimal $1.12\text{ TB}$ hingga $1.4\text{ TB}$ VRAM khusus untuk parameter dan optimizer, mengharuskan kluster multi-node GPU berkoneksi InfiniBand yang sangat mahal.

```
+-------------------------------------------------------------------------------+
|                             MENTAL MODEL PEFT & LoRA                          |
|                                                                               |
|   Full Fine-Tuning:                                                          |
|   W_new = W_0 + Delta_W    (Delta_W memiliki dimensi d x k, ukuran penuh)     |
|                                                                               |
|   LoRA (Low-Rank Adaptation):                                                 |
|   W_new = W_0 + (alpha/r) * (B * A)                                           |
|                                                                               |
|            [    W_0    ]           +       [ B ]     x     [   A   ]          |
|              (d x k)                      (d x r)            (r x k)          |
|          FROZEN WEIGHTS                 TRAINABLE           TRAINABLE         |
|         (NF4 dalam QLoRA)               (B=0 init)       (Gaussian init)      |
|                                                                               |
|   Asumsi: Rank r << min(d, k)                                                |
|   Parameter trainable tereduksi drastis hingga >99%                           |
+-------------------------------------------------------------------------------+
```

#### The Intrinsic Rank Hypothesis
Aghajanyan et al. (2020) membuktikan bahwa fungsi objektif model yang telah melewati tahap *pre-training* memiliki dimensi intrinsik (*intrinsic dimension*) yang jauh lebih rendah daripada ruang parameter aslinya. Hu et al. (2021) mengkapitalisasi temuan ini melalui **LoRA**: perubahan bobot adaptasi $\Delta W$ untuk memetakan model ke domain baru dapat dibatasi pada sub-ruang berdimensi rendah (*low-rank subspace*).

Dengan mendekomposisi $\Delta W_{d \times k}$ menjadi perkalian dua matriks berdimensi rendah $B_{d \times r}$ dan $A_{r \times k}$ di mana $r \ll \min(d, k)$, jumlah parameter yang dilatih terpangkas secara eksponensial. Base weights $W_0$ dibekukan sepenuhnya, meniadakan kebutuhan alokasi memori optimizer untuk $W_0$.

#### Kuantisasi QLoRA: NormalFloat4 (NF4) & Double Quantization
QLoRA (Dettmers et al., 2023) memperluas paradigma LoRA dengan memampatkan $W_0$ ke dalam presisi 4-bit tanpa mendegradasi performa inferensi melalui tiga pilar:
1. **NF4 (NormalFloat 4-bit):** Tipe data dengan kuantisasi informasi-teoretis optimal untuk bobot neural network yang terdistribusi normal ($\mathcal{N}(0, \sigma^2)$). Setiap bin kuantisasi memiliki jumlah probabilitas massa yang identik.
2. **Double Quantization (DQ):** Menguantisasi konstanta kuantisasi (*quantization constants*) itu sendiri. Jika kuantisasi blok 4-bit standar menggunakan 32-bit float untuk setiap blok ukuran 64 (menambahkan $32/64 = 0.5$ bit per parameter), DQ menguantisasi konstanta tersebut ke FP8 dengan ukuran blok 256, mereduksi jejak menjadi $0.127$ bit per parameter (menghemat $\approx 0.373$ bit/param).
3. **Paged Optimizers:** Menggunakan CUDA Unified Memory untuk melakukan *page-to-host swapping* otomatis antara GPU VRAM dan CPU RAM saat alokasi memori melonjak (*memory spikes*) selama backward pass pada sekuens panjang.

---

### 3. Why It Matters (Masalah di Dunia Nyata & Kebutuhan Enterprise)

1. **Efisiensi Finansial & Infrastruktur:**
   Mengadaptasi model 70B parameter sebelumnya menuntut kluster $8 \times \text{A100/H100 } (80\text{GB})$. Dengan QLoRA, fine-tuning model 70B parameter dapat dieksekusi pada 2x kartu RTX 4090 (24GB) atau single GPU A100 (80GB). Biaya komputasi berkurang hingga 80-90%.
2. **Multi-Tenant Serving & Adapter Hot-Swapping:**
   Dalam arsitektur mikroservis enterprise, melayani 50 use-case spesifik (Legal, Finansial, Customer Support, Coding) tidak lagi memerlukan 50 instans model 70B yang terpisah. Enterprise cukup menjalankan **satu** instans *frozen base model* (misal: Llama-3-70B) dan memuat bobot adapter LoRA berukuran mega-byte ($\approx 50\text{MB} - 200\text{MB}$) secara dinamis ke VRAM berdasarkan `tenant_id` dari *incoming request*.
3. **Pemberantasan Catastrophic Forgetting:**
   FFT rentan menghapus pengetahuan umum model (*alignment drift*) saat difokuskan pada dataset sempit. Karena base weight pada LoRA dibekukan, model mempertahankan kemampuan penalaran umum dan generalisasi bahasa bawaannya.
4. **Data Sovereignty & On-Premise Training:**
   Banyak industri regulated (perbankan, kesehatan, militer) dilarang mengekspor data ke API LLM publik (misal: OpenAI/Anthropic). PEFT memungkinkan pelatihan model open-weights berdaya saing tinggi langsung di dalam infrastruktur *private on-premise* dengan keterbatasan GPU.

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan aliran data komputasi maju (*forward pass*) dan *gradient propagation* pada QLoRA beserta arsitektur serving *multi-adapter*.

```
+---------------------------------------------------------------------------------------------------+
|                                QLoRA EXECUTION & SERVING PIPELINE                                 |
+---------------------------------------------------------------------------------------------------+
                                                                                                     
                      Input Tokens: [X]  (Dimensi: Batch x Seq_Len x d_in)                          
                                      |                                                             
                                      +------------------------------------+                        
                                      |                                    |                        
                                      v                                    v                        
                     +----------------------------------+        +-------------------+              
                     |  Frozen Base Weight (W_0)        |        | LoRA Adapter (A)  |              
                     |  Storage: 4-bit NF4              |        | Storage: BF16     |              
                     |  Dimensi: (d_in x d_out)         |        | Dimensi: (d_in x r)              
                     |  Computation: On-the-fly Dequant |        | Init: Gaussian    |              
                     +----------------------------------+        +-------------------+              
                                      |                                    |                        
                                      v (Dequant to BF16)                  v                        
                     +----------------------------------+        +-------------------+              
                     |  Matrix Multiplication:          |        | LoRA Adapter (B)  |              
                     |  h_base = X * W_0                |        | Storage: BF16     |              
                     +----------------------------------+        | Dimensi: (r x d_out)             
                                      |                          | Init: Zero (0)    |              
                                      |                          +-------------------+              
                                      |                                    |                        
                                      |                                    v                        
                                      |                          +-------------------+              
                                      |                          | Scaling:          |              
                                      |                          | * (alpha / r)     |              
                                      |                          +-------------------+              
                                      |                                    |                        
                                      v                                    v                        
                                  [h_base]           +                 [h_adapter]                  
                                      |                                    |                        
                                      +-----------------+------------------+                        
                                                        |                                           
                                                        v                                           
                                           Combined Output Projection:                              
                                                h = h_base + h_adapter                              
                                                        |                                           
                                                        v                                           
                                               Next Layer / Softmax                                 

+---------------------------------------------------------------------------------------------------+
|                             ENTERPRISE MULTI-TENANT SERVING LAYER                                 |
+---------------------------------------------------------------------------------------------------+
                                                                                                    
   Incoming Requests:                                                                               
   Tenant A (Legal Doc)    -----> [ Router / Gateway ]                                              
   Tenant B (Medical Extraction)        |                                                           
                                        | (Inspect Tenant Header)                                   
                                        v                                                           
                     +-------------------------------------+                                        
                     | Base Model Engine (Frozen vLLM/SGLang|                                        
                     | NF4 or FP8 Backbone Execution Core   |                                       
                     +-------------------------------------+                                        
                                  |            |                                                    
          +-----------------------+            +-----------------------+                            
          v                                                            v                            
   [ Dynamic LoRA Pool ]                                        [ Dynamic LoRA Pool ]               
   Load: Legal_Adapter_v1.bin                                   Load: Med_Adapter_v2.bin            
   VRAM Cache: ~80MB                                            VRAM Cache: ~80MB                   
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Formulasi Matematika LoRA
Diberikan layer linear standar dengan pemetaan representasi fitur:
$$h = X W_0$$
di mana $X \in \mathbb{R}^{B \times d_{in}}$ dan $W_0 \in \mathbb{R}^{d_{in} \times d_{out}}$.

Dalam LoRA, pembaruan parameter dikomposisikan secara aditif:
$$W = W_0 + \Delta W$$
$$\Delta W = \gamma \cdot (A \cdot B)$$
di mana $A \in \mathbb{R}^{d_{in} \times r}$, $B \in \mathbb{R}^{r \times d_{out}}$, rank $r \ll \min(d_{in}, d_{out})$, dan $\gamma$ adalah faktor penskalaan konstan:
$$\gamma = \frac{\alpha}{r}$$

- **Inisialisasi Bobot:** Matriks $A$ diinisialisasi menggunakan distribusi Gaussian $\mathcal{N}(0, \sigma^2)$, sedangkan matriks $B$ diinisialisasi dengan nilai **0**. Ini menjamin bahwa pada iterasi $t=0$:
  $$\Delta W = B \cdot A = 0 \cdot A = 0$$
  Sehingga model memulai fine-tuning persis dari kapabilitas awal *base pre-trained model* tanpa deviasi acak.
- **Faktor Skala $\alpha$ (*LoRA Alpha*):** Konstanta $\alpha$ berfungsi seperti learning rate konstan khusus untuk adapter. Ketika bereksperimen mengubah nilai rank $r$, mempertahankan rasio $\frac{\alpha}{r}$ konstan mengeliminasi kebutuhan untuk melakukan tuning ulang hyperparameter optimizer (seperti AdamW learning rate).

#### B. Teori Kuantisasi NF4 (NormalFloat 4)
Bobot neural network hasil standardisasi empiris mengikuti distribusi normal nol-terpusat:
$$W \sim \mathcal{N}(0, \sigma^2)$$
Kuantisasi seragam (*uniform quantization*, seperti INT4) membagi rentang $[-q_{max}, q_{max}]$ menjadi interval dengan lebar yang sama. Hal ini suboptimal untuk distribusi normal karena sebagian besar titik data terkonsentrasi di dekat nol, menyebabkan distorsi informasi kuantisasi (*quantization noise*) yang tinggi pada ekor distribusi.

NF4 menetapkan $2^k = 16$ titik kuantisasi $q_i$ ($i = 0, \dots, 15$) sedemikian rupa sehingga area di bawah kurva fungsi densitas probabilitas (PDF) Gaussian standar di antara setiap titik kuantisasi bernilai sama:
$$P(q_i \le x \le q_{i+1}) = \frac{1}{2^k} = \frac{1}{16}$$
Nilai kuantisasi diskrit dihitung menggunakan *quantile function* (invers CDF) dari distribusi normal standar $q_i = Q_X\left(\frac{i}{2^k}\right)$, yang kemudian dinormalisasi sehingga rentang berada di $[-1, 1]$.

#### C. Gradient Checkpointing & Paged Optimizers
Meskipun bobot dibekukan dan gradien hanya dihitung untuk matriks $A$ dan $B$, konsumsi memori aktivasi (*activation memory*) tetap tumbuh secara linear terhadap kedalaman model ($L$), sequence length ($S$), dan batch size ($b$):
$$\text{Memory}_{activations} \propto \mathcal{O}(L \cdot S \cdot b \cdot d_{model})$$

- **Activation/Gradient Checkpointing:** Meniadakan penyimpanan aktivasi forward pass pada *intermediate hidden layers*. Lapisan tersebut menghitung ulang (*recomputes*) aktivasi secara lokal saat fase *backward pass*. Ini menukar $\approx 20\text{-}30\%$ penambahan waktu komputasi (*latency overhead*) untuk penghematan memori aktivasi hingga $70\%$.
- **Paged Optimizers:** Mengatasi masalah fragmentasi memori (*out-of-memory error spike*) ketika alokasi token batch tidak beraturan memicu lonjakan memori aktivasi secara tiba-tiba. Driver BitsAndBytes mengalokasikan memori halaman status optimizer ke non-evictable system memory (CPU RAM) melalui PCIe jika VRAM melampaui batas ambang kritis 95%.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi end-to-end pipeline fine-tuning QLoRA modular yang memenuhi standar arsitektur enterprise: *type-hinted*, konfigurasi tervalidasi via Pydantic, isolasi tanggung jawab kelas, penanganan checkpointing adaptif, dan integrasi tokenisasi deterministik.

```python
"""
production_qlora_pipeline.py
Arsitektur Pipeline Fine-Tuning QLoRA Tingkat Produksi.
Mendukung: Kuantisasi NF4, Double Quantization, Llama-3/Mistral token classification/causal LM.
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import torch
from datasets import Dataset, load_dataset
from pydantic import BaseModel, Field, ValidationError
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    DataCollatorForSeq2Seq,
    PreTrainedModel,
    PreTrainedTokenizerBase,
    Trainer,
    TrainingArguments,
)
from peft import (
    LoraConfig,
    PeftModel,
    TaskType,
    get_peft_model,
    prepare_model_for_kbit_training,
)

# Konfigurasi Logging Terstruktur
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("QLoRA-Production")


class TrainingPipelineConfig(BaseModel):
    """Skema konfigurasi pelatihan yang divalidasi ketat."""
    model_id: str = Field(..., description="HuggingFace model repository ID atau path lokal.")
    output_dir: Path = Field(..., description="Direktori penyimpanan checkpoint dan adapter.")
    dataset_name: Optional[str] = Field(None, description="Nama dataset dari Hugging Face Hub.")
    dataset_path: Optional[Path] = Field(None, description="Path lokal ke format jsonl/parquet.")
    max_seq_length: int = Field(default=2048, ge=128, le=32768)
    lora_r: int = Field(default=16, ge=1, le=256)
    lora_alpha: int = Field(default=32, ge=1, le=512)
    lora_dropout: float = Field(default=0.05, ge=0.0, le=0.5)
    target_modules: List[str] = Field(
        default=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
    )
    per_device_train_batch_size: int = Field(default=2, ge=1)
    gradient_accumulation_steps: int = Field(default=8, ge=1)
    learning_rate: float = Field(default=2e-4, gt=0.0)
    num_train_epochs: int = Field(default=3, ge=1)
    logging_steps: int = Field(default=10, ge=1)
    save_steps: int = Field(default=100, ge=1)
    seed: int = Field(default=42)

    class Config:
        arbitrary_types_allowed = True


class TokenizerManager:
    """Mengelola siklus hidup tokenizer, format template, dan padding token."""

    @staticmethod
    def initialize(model_id: str, max_seq_length: int) -> PreTrainedTokenizerBase:
        logger.info(f"Menginisialisasi tokenizer untuk {model_id}")
        tokenizer = AutoTokenizer.from_pretrained(
            model_id,
            use_fast=True,
            trust_remote_code=False,
            padding_side="right",
        )
        
        # Standarisasi Special Token
        if tokenizer.pad_token is None:
            if tokenizer.unk_token is not None:
                tokenizer.pad_token = tokenizer.unk_token
            else:
                tokenizer.pad_token = tokenizer.eos_token
                
        tokenizer.model_max_length = max_seq_length
        return tokenizer


class ModelQuantizationFactory:
    """Factory untuk mengonfigurasi BitsAndBytes dan memuat model terkuantisasi."""

    @staticmethod
    def create_bnb_config() -> BitsAndBytesConfig:
        return BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
        )

    @classmethod
    def load_base_model(cls, model_id: str) -> PreTrainedModel:
        if not torch.cuda.is_available():
            raise RuntimeError("Akselerasi CUDA wajib tersedia untuk menjalankan pipeline QLoRA.")

        logger.info(f"Memuat model {model_id} dalam format 4-bit NF4...")
        bnb_config = cls.create_bnb_config()
        
        device_map = {"": torch.cuda.current_device()}
        
        model = AutoModelForCausalLM.from_pretrained(
            model_id,
            quantization_config=bnb_config,
            device_map=device_map,
            trust_remote_code=False,
            torch_dtype=torch.bfloat16,
            attn_implementation="flash_attention_2" if torch.cuda.get_device_capability()[0] >= 8 else "eager",
        )

        # Persiapan layer model untuk k-bit backward pass
        model = prepare_model_for_kbit_training(
            model, 
            use_gradient_checkpointing=True
        )
        return model


class DataPipeline:
    """Penanganan pra-pemrosesan data instruction tuning yang deterministik."""

    def __init__(self, tokenizer: PreTrainedTokenizerBase, max_length: int):
        self.tokenizer = tokenizer
        self.max_length = max_length

    def format_prompts(self, batch: Dict[str, List[Any]]) -> Dict[str, List[Any]]:
        """
        Format instruksi standar: Instruction, Input, Response -> ChatML/Alpaca
        """
        formatted_texts = []
        for instruction, inp, response in zip(batch["instruction"], batch["input"], batch["output"]):
            if inp:
                full_prompt = (
                    f"<|im_start|>system\nAnda adalah asisten AI yang patuh dan akurat.<|im_end|>\n"
                    f"<|im_start|>user\n{instruction}\nInput Konteks: {inp}<|im_end|>\n"
                    f"<|im_start|>assistant\n{response}<|im_end|>"
                )
            else:
                full_prompt = (
                    f"<|im_start|>system\nAnda adalah asisten AI yang patuh dan akurat.<|im_end|>\n"
                    f"<|im_start|>user\n{instruction}<|im_end|>\n"
                    f"<|im_start|>assistant\n{response}<|im_end|>"
                )
            formatted_texts.append(full_prompt)

        tokenized = self.tokenizer(
            formatted_texts,
            max_length=self.max_length,
            truncation=True,
            padding=False,
            return_tensors=None,
        )
        
        # Konfigurasi Labels untuk causal loss masking: token input harus di-mask (-100)
        # Pada skenario implementasi ini, kita targetkan loss terhitung pada seluruh blok atau output saja.
        tokenized["labels"] = [input_ids.copy() for input_ids in tokenized["input_ids"]]
        return tokenized


class QLoRATrainingEngine:
    """Mesin orkestrator pelatihan PEFT QLoRA."""

    def __init__(self, config: TrainingPipelineConfig):
        self.config = config
        self.tokenizer = TokenizerManager.initialize(config.model_id, config.max_seq_length)
        self.model = ModelQuantizationFactory.load_base_model(config.model_id)
        self._apply_lora()

    def _apply_lora(self) -> None:
        """Menginjeksikan adapter LoRA ke dalam base model terkuantisasi."""
        lora_config = LoraConfig(
            r=self.config.lora_r,
            lora_alpha=self.config.lora_alpha,
            target_modules=self.config.target_modules,
            lora_dropout=self.config.lora_dropout,
            bias="none",
            task_type=TaskType.CAUSAL_LM,
        )
        self.model = get_peft_model(self.model, lora_config)
        self._log_trainable_parameters()

    def _log_trainable_parameters(self) -> None:
        """Kalkulasi rasio parameter yang dilatih vs dibekukan."""
        trainable_params = 0
        all_param = 0
        for _, param in self.model.named_parameters():
            all_param += param.numel()
            if param.requires_grad:
                trainable_params += param.numel()
        
        percentage = 100 * trainable_params / all_param
        logger.info(
            f"Statistik Parameter: Trainable: {trainable_params:,} | "
            f"Total: {all_param:,} | Rasio: {percentage:.4f}%"
        )

    def run_training(self, train_dataset: Dataset, eval_dataset: Optional[Dataset] = None) -> None:
        """Eksekusi loop pelatihan menggunakan HuggingFace Trainer."""
        training_args = TrainingArguments(
            output_dir=str(self.config.output_dir),
            per_device_train_batch_size=self.config.per_device_train_batch_size,
            gradient_accumulation_steps=self.config.gradient_accumulation_steps,
            learning_rate=self.config.learning_rate,
            num_train_epochs=self.config.num_train_epochs,
            logging_steps=self.config.logging_steps,
            save_strategy="steps",
            save_steps=self.config.save_steps,
            evaluation_strategy="no" if eval_dataset is None else "steps",
            eval_steps=self.config.save_steps if eval_dataset is not None else None,
            fp16=False,
            bf16=True,  # Mandatory untuk stabilitas training QLoRA modern
            optim="paged_adamw_8bit",
            gradient_checkpointing=True,
            max_grad_norm=0.3,  # Mencegah gradient explosion pada adapter
            warmup_ratio=0.03,
            lr_scheduler_type="cosine",
            seed=self.config.seed,
            report_to="none",  # Ubah ke 'wandb' pada infrastruktur monitoring terintegrasi
        )

        data_collator = DataCollatorForSeq2Seq(
            tokenizer=self.tokenizer,
            pad_to_multiple_of=8,
            return_tensors="pt",
            padding=True,
        )

        trainer = Trainer(
            model=self.model,
            args=training_args,
            train_dataset=train_dataset,
            eval_dataset=eval_dataset,
            data_collator=data_collator,
        )

        # Nonaktifkan use_cache jika gradient checkpointing aktif
        self.model.config.use_cache = False

        logger.info("Memulai proses fine-tuning...")
        trainer.train()

        # Simpan adapter akhir & tokenizer
        logger.info(f"Menyimpan bobot adapter ke {self.config.output_dir}")
        self.model.save_pretrained(self.config.output_dir)
        self.tokenizer.save_pretrained(self.config.output_dir)

    def merge_and_export(self, export_path: Path) -> None:
        """
        Menggabungkan bobot adapter ke dalam base model float16/bfloat16
        untuk deployment siap pakai pada high-performance inference engine.
        """
        logger.info(f"Memulai fusi adapter ke base model untuk ekspor: {export_path}")
        
        # Load ulang base model dalam FP16 (bukan 4-bit) untuk fusi tanpa degradasi floating point
        base_model = AutoModelForCausalLM.from_pretrained(
            self.config.model_id,
            return_dict=True,
            torch_dtype=torch.bfloat16,
            device_map="cpu",  # Gunakan CPU RAM jika VRAM terbatas untuk proses fusi
        )
        
        peft_model = PeftModel.from_pretrained(
            base_model,
            str(self.config.output_dir),
            torch_dtype=torch.bfloat16,
        )
        
        merged_model = peft_model.merge_and_unload()
        merged_model.save_pretrained(export_path, safe_serialization=True)
        self.tokenizer.save_pretrained(export_path)
        logger.info("Ekspor model gabungan selesai secara konsisten.")


# ==========================================
# Entrypoint Eksekusi Demonstrasi Pipeline
# ==========================================
if __name__ == "__main__":
    try:
        # Validasi Konfigurasi
        raw_config = {
            "model_id": "mistralai/Mistral-7B-v0.1",
            "output_dir": Path("./adapters/mistral-qlora-enterprise"),
            "max_seq_length": 1024,
            "lora_r": 16,
            "lora_alpha": 32,
            "per_device_train_batch_size": 2,
            "gradient_accumulation_steps": 4,
            "learning_rate": 2e-4,
            "num_train_epochs": 1,
        }
        validated_config = TrainingPipelineConfig(**raw_config)

        # Mock Data untuk Pengujian Pipeline
        mock_data = {
            "instruction": [
                "Ekstrak entitas nama orang dari klaim asuransi berikut.",
                "Klasifikasikan sentimen transkrip percakapan finansial ini.",
            ],
            "input": [
                "Nasabah atas nama Bambang Pamungkas mengajukan klaim kerusakan pada tanggal 12 Mei.",
                "Pendapatan kuartal ketiga menurun drastis sebesar 14% dibandingkan tahun lalu.",
            ],
            "output": [
                '{"nama": "Bambang Pamungkas"}',
                '{"sentimen": "negatif", "faktor": "penurunan laba"}',
            ],
        }
        synthetic_dataset = Dataset.from_dict(mock_data)

        # Persiapan Data
        pipeline_prep = DataPipeline(
            tokenizer=TokenizerManager.initialize(validated_config.model_id, validated_config.max_seq_length),
            max_length=validated_config.max_seq_length,
        )
        tokenized_train = synthetic_dataset.map(
            pipeline_prep.format_prompts,
            batched=True,
            remove_columns=synthetic_dataset.column_names,
        )

        # Inisialisasi Engine & Eksekusi
        # Catatan: Membutuhkan hardware GPU dengan kapabilitas CUDA terpasang
        if torch.cuda.is_available():
            engine = QLoRATrainingEngine(config=validated_config)
            engine.run_training(train_dataset=tokenized_train)
            # engine.merge_and_export(Path("./models/mistral-merged-enterprise"))
        else:
            logger.warning("Instans CUDA tidak terdeteksi. Pelatihan dilewati pada unit test statis.")

    except ValidationError as ve:
        logger.error(f"Kegagalan validasi konfigurasi pipeline: {ve.json()}")
    except Exception as exc:
        logger.critical(f"Kegagalan fatal pada pipeline eksekusi: {str(exc)}", exc_info=True)
```

---

### 7. Edge Cases & Failure Modes (Mitigasi & Pemulihan)

| Failure Mode | Mekanisme Penyebab | Deteksi Dini | Prosedur Mitigasi Produksi |
| :--- | :--- | :--- | :--- |
| **CUDA OOM Saat Backward Step** | Peningkatan mendadak ukuran sekuens dalam batch memicu memori aktivasi melampaui sisa VRAM. | Training crash dengan kode galat `torch.cuda.OutOfMemoryError`. | 1. Gunakan `paged_adamw_8bit`<br>2. Setel `per_device_train_batch_size=1` dan naikkan `gradient_accumulation_steps`<br>3. Aktifkan dynamic padding via `DataCollatorForSeq2Seq` (hindari padding statis ke `max_length`). |
| **Loss Spikes & NaNs Divergence** | *Underflow* gradien pada format FP16 saat menghitung layer normalisasi (RMSNorm). | Kurva loss pada step $t$ tiba-tiba melompat ke `NaN` atau bernilai float statis. | 1. Paksa penggunaan tipe data `bf16=True` pada Ampere/Hopper/Ada Lovelace.<br>2. Terapkan gradient clipping ketat: `max_grad_norm=0.3`.<br>3. Ganti inisialisasi optimizer ke learning rate lebih rendah ($5\times 10^{-5}$). |
| **Catastrophic Forgetting** | Model mengoverfit format instruksi baru dan menghapus logika penalaran (*reasoning*) dasar. | Evaluasi zero-shot pada benchmark dasar (MMLU, GSM8K) anjlok >15%. | 1. Terapkan *Targeted Adaptation*: hanya adaptasi layer $W_q, W_v$ (jangan sentuh MLP layer).<br>2. Turunkan rank ke $r=8$ atau $r=16$.<br>3. Lakukan penggabungan dataset regulasi (*Replay buffer* dari 5-10% data pre-training umum). |
| **Precision Loss Saat Merge & Unload** | Melakukan fusi dequantized NF4 langsung ke float16 menyebabkan akumulasi galat pembulatan desimal. | Respon teks model hasil gabungan menghasilkan repetisi tak berujung (*gibberish loops*). | 1. Jangan pernah memanggil `merge_and_unload()` pada model instans 4-bit.<br>2. Muat base model murni dalam `torch.bfloat16`/`float16` unquantized, muat bobot adapter, lalu eksekusi fusi bobot. |

---

### 8. Trade-offs & Alternatif Solusi

Setiap teknik kustomisasi model memiliki kompromi arsitektural yang ketat. Berikut matriks perbandingannya:

```
                KONSUMSI MEMORI vs. FLEKSIBILITAS ADAPTASI
High ^
     |                                    [ Full Fine-Tuning ]
     |                                     - Adaptasi Tertinggi
V    |                                     - VRAM Sangat Masif
R    |
A    |                   [ LoRA (FP16 Base) ]
M    |                    - Kualitas Tinggi
     |                    - VRAM Moderat
U    |
s    |       [ QLoRA (NF4 Base) ]
a    |        - Sangat Hemat VRAM
g    |        - Latency Training +30%
e    |
     |  [ Prefix Tuning / Prompt Tuning ]
     |   - Kapasitas Representasi Terbatas
Low  +------------------------------------------------------------>
     Low                     Adaptation Ceiling                    High
```

#### Tabel Evaluasi Komparatif

| Dimensi Arsitektur | Full Fine-Tuning (FFT) | LoRA (FP16/BF16) | QLoRA (NF4) | Prefix / Prompt Tuning |
| :--- | :--- | :--- | :--- | :--- |
| **VRAM Requirement (70B Model)** | $\approx 1.2\text{ TB} - 1.4\text{ TB}$ | $\approx 160\text{ GB} - 200\text{ GB}$ | $\approx 48\text{ GB} - 64\text{ GB}$ | $\approx 150\text{ GB}$ |
| **Training Throughput** | $1.0\times$ (Baseline) | $0.85\times - 0.95\times$ | $0.65\times - 0.75\times$ (Dequant Overhead) | $0.95\times$ |
| **Inference Serving Latency** | Baseline (Nol overhead) | Nol (jika dimerge); Minimal jika multi-LoRA | Tambahan dequantize overhead jika serving via NF4 | Menghabiskan jatah Context Window |
| **Multi-Tenant Agility** | Sangat Buruk (1 instans per domain) | Sangat Baik (Hot-swapping adapter 100MB) | Sangat Baik (Hot-swapping adapter 100MB) | Sangat Baik (Hanya menyimpan vektor prompt) |
| **Kemampuan Domain Shift Ekstrem** | Maksimal | Tinggi | Tinggi mendekati LoRA FP16 | Rendah (Gagal pada tugas domain kompleks) |

---

### 9. Best Practices & Standard Industri

1. **Rasio Rank ($r$) dan Alpha ($\alpha$):**
   - Tetapkan standar $\alpha = 2 \times r$ sebagai acuan empiris (*rule of thumb*).
   - Gunakan $r = 16, \alpha = 32$ untuk *instruction following*, format parsing, dan perbaikan gaya penulisan.
   - Naikkan ke $r = 64, \alpha = 128$ hanya jika model ditugaskan mempelajari sintaksis kode bahasa baru atau korpus terminologi medis/hukum yang sangat padat.
2. **Seleksi Target Modules:**
   - Standar industri modern mengadaptasi **seluruh modul linear** dalam arsitektur transformer:
     `["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]`.
   - Mengadaptasi seluruh modul dengan rank rendah ($r=16$) menghasilkan performa jauh lebih superior daripada hanya mengadaptasi modul atensi ($W_q, W_v$) dengan rank tinggi ($r=64$).
3. **Data Quality over Quantity:**
   - LIMA (*Less Is More for Alignment*) membuktikan bahwa $1.000$ pasang data instruksi-respon yang dikurasi secara manual dan diverifikasi ketat menghasilkan performa alignment yang jauh melampaui $50.000$ data sintetis yang bising (*noisy*).
4. **Strategi Hyperparameter:**
   - Gunakan Cosine Learning Rate Scheduler dengan $3\%$ warmup step.
   - Hindari learning rate di atas $3\times 10^{-4}$ pada model 7B/8B, dan hindari di atas $1\times 10^{-4}$ pada model 70B untuk menjaga kestabilan matriks adapter.
5. **Determinisme & Auditability:**
   - Simpan hash SHA-256 dari dataset pelatihan di metadata checkpoint LoRA adapter.
   - Kunci generator seed pada PyTorch, CUDA, dan Python runtime (`torch.manual_seed(42)`).

---

### 10. Hands-on Lab Exercise

#### Skenario Lab
Sebuah platform fintech mewajibkan pembangunan model lokal berlatensi rendah untuk mengekstrak informasi finansial tidak terstruktur menjadi schema JSON valid, tanpa mentransmisikan data ke penyedia model pihak ketiga. 

#### Langkah Eksekusi

```bash
# 1. Persiapan Environment
conda create -n qlora-lab python=3.11 -y
conda activate qlora-lab

# Instalasi PyTorch dengan dukungan CUDA 12.x
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Instalasi Pustaka PEFT & Akselerasi
pip install transformers==4.40.1 \
            peft==0.10.0 \
            bitsandbytes==0.43.1 \
            accelerate==0.29.3 \
            datasets==2.19.0 \
            pydantic==2.7.1 \
            scipy
```

#### Pembuatan Dataset Latihan Lokal (`fintech_dataset.jsonl`)
Simpan file berikut sebagai `fintech_dataset.jsonl`:
```json
{"instruction": "Ekstraksi parameter pinjaman dalam format JSON.", "input": "Nasabah mengajukan kredit multiguna sebesar 50 juta rupiah dengan tenor 24 bulan dan bunga tahunan 8.5%.", "output": "{\"tipe\": \"kredit multiguna\", \"plafon\": 50000000, \"tenor_bulan\": 24, \"bunga_persen\": 8.5}"}
{"instruction": "Ekstraksi parameter pinjaman dalam format JSON.", "input": "Pengajuan pembiayaan KPR disetujui senilai 750000000 IDR, jangka waktu 180 bulan, suku bunga 6.25%.", "output": "{\"tipe\": \"KPR\", \"plafon\": 750000000, \"tenor_bulan\": 180, \"bunga_persen\": 6.25}"}
```

#### Skrip Pelatihan dan Validasi Evaluasi (`run_lab.py`)
```python
import torch
from datasets import load_dataset
from transformers import (
    AutoModelForCausalLM, 
    AutoTokenizer, 
    BitsAndBytesConfig, 
    TrainingArguments, 
    Trainer, 
    DataCollatorForSeq2Seq
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

# 1. Konfigurasi
MODEL_NAME = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"  # Model representatif untuk eksperimen cepat
OUTPUT_DIR = "./lab_fintech_adapter"

# 2. Tokenizer & Kuantisasi
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_use_double_quant=True,
    bnb_4bit_compute_dtype=torch.bfloat16
)

tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, use_fast=True)
tokenizer.pad_token = tokenizer.eos_token

model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME,
    quantization_config=bnb_config,
    device_map="auto"
)
model = prepare_model_for_kbit_training(model)

# 3. LoRA Configuration
peft_config = LoraConfig(
    r=8,
    lora_alpha=16,
    target_modules=["q_proj", "v_proj"],
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM"
)
model = get_peft_model(model, peft_config)

# 4. Format Data
dataset = load_dataset("json", data_files="fintech_dataset.jsonl", split="train")

def format_prompt(sample):
    text = (
        f"<|system|>\nEkstrak entitas secara terstruktur.<|end|>\n"
        f"<|user|>\n{sample['instruction']}\nInput: {sample['input']}<|end|>\n"
        f"<|assistant|>\n{sample['output']}<|end|>"
    )
    tokens = tokenizer(text, max_length=512, truncation=True)
    tokens["labels"] = tokens["input_ids"].copy()
    return tokens

tokenized_dataset = dataset.map(format_prompt, remove_columns=dataset.column_names)

# 5. Trainer
trainer = Trainer(
    model=model,
    args=TrainingArguments(
        output_dir=OUTPUT_DIR,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=2,
        num_train_epochs=5,
        learning_rate=2e-4,
        bf16=True if torch.cuda.is_bf16_supported() else False,
        fp16=False if torch.cuda.is_bf16_supported() else True,
        logging_steps=1,
        save_strategy="no"
    ),
    train_dataset=tokenized_dataset,
    data_collator=DataCollatorForSeq2Seq(tokenizer, padding=True)
)

model.config.use_cache = False
trainer.train()

# 6. Verifikasi Inferensi Adapter
model.eval()
input_eval = "Permohonan modal kerja Rp 200.000.000, tenor selama 36 bulan dengan bunga 9%."
eval_prompt = (
    f"<|system|>\nEkstrak entitas secara terstruktur.<|end|>\n"
    f"<|user|>\nEkstraksi parameter pinjaman dalam format JSON.\nInput: {input_eval}<|end|>\n"
    f"<|assistant|>\n"
)

inputs = tokenizer(eval_prompt, return_tensors="pt").to("cuda")
with torch.no_grad():
    outputs = model.generate(**inputs, max_new_tokens=100, temperature=0.1)

print("\n--- HASIL INFERENSI POST-TUNING ---")
print(tokenizer.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True))
```

#### Kriteria Keberhasilan Verifikasi
1. Output model menghasilkan struktur JSON yang valid (parseable via `json.loads`).
2. Train loss menurun secara konvergen tanpa menghasilkan nilai `NaN`.
3. Memori VRAM tidak melampaui $4\text{ GB}$ selama keseluruhan proses training pada TinyLlama.