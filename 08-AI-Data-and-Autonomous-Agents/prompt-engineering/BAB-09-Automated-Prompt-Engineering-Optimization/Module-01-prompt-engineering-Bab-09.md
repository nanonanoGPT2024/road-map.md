# Bab 09: Automated Prompt Engineering & Optimization
## Modul 01: Algoritma & Arsitektur Automated Prompt Engineering (APE)

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis (C4)** ruang pencarian prompt (*discrete prompt space*) sebagai masalah optimasi diskret non-diferensiabel dengan memetakan trade-off antara exploration (generasi variasi) dan exploitation (penyempurnaan kandidat terbaik).
- **Merancang (C5)** arsitektur *Automated Prompt Engineering* (APE) berbasis loop umpan balik terstruktur yang mencakup modul *candidate generation*, *mutation/refinement*, dan *batched empirical evaluation*.
- **Mengimplementasikan (C6)** engine optimasi prompt otomatis end-to-end berbasis Python yang memanfaatkan model *meta-prompting*, pelacakan metrik kuantitatif, dan *k-fold validation split* untuk mencegah *overfitting* instruksi.
- **Mengevaluasi (C5)** trade-off biaya, latensi, dan performa inferensi antara optimasi prompt otomatis (APE, DSPy teleprompters) versus adaptasi bobot model (*parameter-efficient fine-tuning* / PEFT).
- **Mendiagnosis (C4)** anomali degradasi prompt seperti *semantic drift*, *prompt hacking via self-mutation*, dan *metric hacking* pada evaluasi otomatis.

---

### 2. Concept Overview

Optimasi prompt tradisional bersifat manual, heuristik, dan rentan terhadap variabilitas intuitif engineer (*trial-and-error*). Pada sistem skala enterprise, pendekatan manual ini gagal ketika model dasar (*foundation model*) di-update atau domain data bergeser (*prompt rot*).

**Automated Prompt Engineering (APE)** mengubah proses rekayasa prompt dari intervensi manual menjadi algoritma optimasi terprogram.

```
+-----------------------------------------------------------------------------------+
|                                MENTAL MODEL APE                                   |
|                                                                                   |
|  Traditional ML Optimization:                                                     |
|  Loss(W) ---> Gradient dL/dW ---> Gradient Descent ---> Update Weights (W)       |
|                                                                                   |
|  Automated Prompt Engineering (Discrete Optimization):                            |
|  Metric(P) ---> LLM Feedback / Score Vector ---> Search/Mutate Engine ---> P'     |
+-----------------------------------------------------------------------------------+
```

#### Formulasi Matematis

Diberikan sebuah LLM target $f_\theta$ dengan bobot tetap $\theta$, dataset latih $\mathcal{D}_{\text{train}} = \{(x_i, y_i)\}_{i=1}^N$, ruang token diskret $\mathcal{V}$, dan metrik evaluasi skalar $\mathcal{M}(\hat{y}, y) \in [0, 1]$. 

Prompt adalah sekuens token $P = (t_1, t_2, \dots, t_k) \in \mathcal{V}^*$. Tujuan dari APE adalah menemukan kandidat prompt optimal $P^*$ sedemikian rupa sehingga:

$$P^* = \arg\max_{P \in \mathcal{V}^*} \mathbb{E}_{(x, y) \sim \mathcal{D}_{\text{val}}} \left[ \mathcal{M}\left(f_\theta(x; P), y\right) \right] - \lambda \cdot \mathcal{C}(P)$$

Di mana:
- $f_\theta(x; P)$ merepresentasikan inferensi LLM target terhadap input $x$ yang dikondisikan oleh instruksi/konteks $P$.
- $\mathcal{C}(P)$ adalah fungsi penalti kompleksitas (misal: panjang token dari $P$ untuk mengendalikan biaya inferensi dan latensi token).
- $\lambda \ge 0$ adalah koefisien regularisasi biaya token.

Karena tokenisasi dan pengambilan sampel token adalah operasi non-diferensiabel ($P$ berada di ruang diskret $\mathcal{V}^*$), $\nabla_P \mathcal{M}$ tidak dapat dihitung langsung via *backpropagation*. APE memecahkan ini dengan memperlakukan optimasi sebagai pencarian kotak hitam (*black-box discrete search*), memanfaatkan:
1. **Generasi Induktif (Meta-Prompting):** LLM terpisah (Teacher LLM) menganalisis data masukan-keluaran untuk mengekstrapolasi instruksi yang mendasarinya.
2. **Pencarian Stokastik (Beam Search / Evolutionary Search):** Mutasi semantik dan seleksi alamiah atas kandidat instruksi berdasarkan skor evaluasi empiris.

---

### 3. Why It Matters

Dalam implementasi *foundation model* pada tingkat enterprise:

1. **Model Drift & Continuous Integration:** Pembaruan versi model (misal: GPT-4-turbo ke GPT-4o, atau Claude 3 Sonnet ke 3.5 Sonnet) sering kali mendegradasi reliabilitas prompt lama hingga 15-30% pada tugas-tugas terstruktur. APE memungkinkan integrasi ke dalam CI/CD pipeline untuk *auto-tuning* prompt secara terjadwal.
2. **Eliminasi Subjektivitas Rekayasa:** Manusia cenderung menyisipkan instruksi redundan (*prompt bloat*) yang menambah konsumsi token tanpa meningkatkan akurasi. APE mengevaluasi kontribusi marginal setiap komponen prompt terhadap metrik bisnis.
3. **Optimasi Berbasis Metrik Majemuk:** APE dapat mengoptimalkan trade-off multivariat secara simultan, seperti akurasi JSON output, tingkat kepatuhan regulasi (*safety compliance*), dan pemangkasan panjang token konteks.

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan siklus optimasi modular APE berbasis umpan balik:

```
+-------------------------------------------------------------------------------------------------------+
|                                    APE CORE ARCHITECTURE PIPELINE                                     |
+-------------------------------------------------------------------------------------------------------+
                                                                                                         
  [Dataset Latih/Val]                                                                                    
  { (x_i, y_i) }                                                                                         
        |                                                                                                
        v                                                                                                
  +------------------+         Instruksi Awal / Task Spec                                                
  | Candidate        |<-----------------------------------------+                                        
  | Generator        |                                          |                                        
  | (Meta-LLM)       |                                          | (Feedback loop:                        
  +------------------+                                          |  Prompt terburuk, pola kegagalan,      
        |                                                       |  dan skor evaluasi)                    
        | Menghasilkan M kandidat prompt {P_1, P_2, ..., P_M}   |                                        
        v                                                       |                                        
  +------------------+                                          |                                        
  | Mutation &       |<-----------------------------------------+                                        
  | Refinement Engine|                                          |                                        
  +------------------+                                          |                                        
        |                                                       |                                        
        | Kumpulan variasi (Exploration)                        |                                        
        v                                                       |                                        
  +-------------------------------------------------------+     |                                        
  | Target Execution Engine (Batch Evaluation)            |     |                                        
  |                                                       |     |                                        
  |   +----------------+    +----------------+            |     |                                        
  |   | Candidate P_1  | .. | Candidate P_k  |            |     |                                        
  |   +----------------+    +----------------+            |     |                                        
  |           |                     |                     |     |                                        
  |   f_theta(x; P_1)       f_theta(x; P_k)               |     |                                        
  +-------------------------------------------------------+     |                                        
        |                                                       |                                        
        v                                                       |                                        
  +------------------+                                          |                                        
  | Metric Evaluator |--> [Rule-based: Exact Match, F1, JSON]   |                                        
  | & Loss Computer  |--> [Model-based: LLM-as-a-Judge]         |                                        
  +------------------+                                          |                                        
        |                                                       |                                        
        v                                                       |                                        
  +------------------+                                          |                                        
  | Pareto Frontier  |---(Kondisi Konvergensi Tercapai?)--+     |                                        
  | & Selection      |                                    |     |                                        
  +------------------+                                    |     |                                        
        | (Belum)                                         |     |                                        
        +-------------------------------------------------+     |                                        
        |                                                       |                                        
        | (Ya: Stop)                                            |                                        
        v                                                       |                                        
  +---------------------------------------+                     |                                        
  | Output: Optimal Prompt P*             |                     |                                        
  | + Profil Metrik Evaluasi Komprehensif |                     |                                        
  +---------------------------------------+                     |                                        
                                                                                                         
+-------------------------------------------------------------------------------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

Alur eksekusi APE terdiri dari empat fase formal:

```
[Inisialisasi Data] 
       │
       ▼
[Fase 1: Inductive Candidate Generation]
       │
       ▼
[Fase 2: Forward Batched Evaluation]
       │
       ▼
[Fase 3: Scoring & Failure Analysis]
       │
       ▼
[Fase 4: Evolutionary Mutation / Pruning]
       │
       ├──(Konvergensi terpenuhi / Iterasi Max)──► [Deploy P*]
       └──(Belum konvergen)──────────────────────► [Loop ke Fase 2]
```

#### Fase 1: Inductive Candidate Generation
Diberikan subset demonstrasi $\mathcal{D}_{\text{seed}} = \{(x_k, y_k)\}_{k=1}^m$. Meta-LLM $f_{\text{meta}}$ diminta mengekstrapolasi instruksi tersembunyi yang memetakan $x$ ke $y$ secara deterministik:
$$P_j \sim f_{\text{meta}}\left(\text{Prompt}_{\text{meta-gen}}\left(\{(x_k, y_k)\}_{k=1}^m\right)\right), \quad j \in \{1, \dots, M\}$$

#### Fase 2: Forward Batched Evaluation
Setiap kandidat prompt $P_j$ disisipkan ke dalam template eksekusi model target $f_\theta$. Model memproses seluruh sampel validasi batch $B \subset \mathcal{D}_{\text{train}}$ secara konkuren:
$$\hat{y}_{i, j} = f_\theta(x_i; P_j), \quad \forall x_i \in B$$

#### Fase 3: Scoring & Failure Analysis
Output yang diprediksi dinilai terhadap label *ground truth* $y_i$ menggunakan fungsi metrik $\mathcal{M}$:
$$S_j = \frac{1}{|B|} \sum_{i=1}^{|B|} \mathcal{M}(\hat{y}_{i, j}, y_i)$$

Contoh-contoh gagal (*hard negatives*) dikumpulkan:
$$\mathcal{E}_j = \{(x_i, y_i, \hat{y}_{i, j}) \mid \mathcal{M}(\hat{y}_{i, j}, y_i) < \tau\}$$

#### Fase 4: Evolutionary Mutation / Pruning
Jika batas iterasi $T$ belum tercapai atau metrik target belum terlampaui:
1. **Selection:** Memilih top-$K$ prompt terbaik berdasarkan $S_j$.
2. **Mutation via Error-Feedback:** Mengirimkan $\mathcal{E}_j$ kembali ke Meta-LLM untuk menghasilkan perbaikan instruksi:
$$P'_{j} \sim f_{\text{meta}}\left(\text{Prompt}_{\text{refine}}(P_j, \mathcal{E}_j)\right)$$
3. **Crossover:** Menggabungkan klausul dari dua prompt berkinerja tinggi yang memiliki kekuatan komplementer.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi clean architecture dari sebuah **APE Engine** menggunakan Python 3.11+, mendukung asinkronitas penuh, validasi tipe ketat, dan error handling robust.

```python
"""
Module: ape_engine.py
Description: Production-ready Automated Prompt Engineering (APE) Framework.
"""

from __future__ import annotations

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Protocol, Sequence, Tuple

# Konfigurasi Logging Terstruktur
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("APE-Engine")


# ---------------------------------------------------------------------------
# Domain Models & Interfaces
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Example:
    """Representasi pasangan input-output untuk optimasi."""
    input_text: str
    target_output: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PromptCandidate:
    """Entitas kandidat instruksi prompt beserta histori performanya."""
    instruction: str
    score: float = 0.0
    iteration: int = 0
    failure_cases: List[Tuple[Example, str]] = field(default_factory=list)

    def __repr__(self) -> str:
        return f"<PromptCandidate score={self.score:.4f} iter={self.iteration} prompt='{self.instruction[:40]}...'>"


class LLMClient(Protocol):
    """Protokol Client LLM untuk abstraksi vendor provider."""
    async def complete(self, prompt: str, temperature: float = 0.7) -> str:
        ...


class MetricEvaluator(ABC):
    """Abstraksi basis evaluator metrik sistem."""
    @abstractmethod
    def evaluate(self, prediction: str, ground_truth: str) -> float:
        """Mengembalikan skor skalar antara [0.0, 1.0]."""
        pass


# ---------------------------------------------------------------------------
# Evaluator Implementations
# ---------------------------------------------------------------------------

class ExactMatchEvaluator(MetricEvaluator):
    """Evaluasi exact match setelah normalisasi whitespace standar."""
    def evaluate(self, prediction: str, ground_truth: str) -> float:
        return 1.0 if prediction.strip().lower() == ground_truth.strip().lower() else 0.0


class StructuredJSONEvaluator(MetricEvaluator):
    """Evaluasi parsing skema dan kecocokan key-value JSON target."""
    def evaluate(self, prediction: str, ground_truth: str) -> float:
        try:
            pred_obj = json.loads(prediction.strip())
            target_obj = json.loads(ground_truth.strip())
            if not isinstance(pred_obj, dict) or not isinstance(target_obj, dict):
                return 0.0
            
            # Hitung Jaccard similarity dari key-value pairs
            pred_items = set((k, str(v)) for k, v in pred_obj.items())
            target_items = set((k, str(v)) for k, v in target_obj.items())
            
            intersection = len(pred_items.intersection(target_items))
            union = len(pred_items.union(target_items))
            return float(intersection / union) if union > 0 else 0.0
        except (json.JSONDecodeError, TypeError):
            return 0.0


# ---------------------------------------------------------------------------
# Core APE Engine
# ---------------------------------------------------------------------------

class PromptOptimizer:
    """
    Engine APE untuk pencarian iteratif, mutasi semantik,
    dan evaluasi performa prompt otomatis.
    """
    def __init__(
        self,
        meta_llm: LLMClient,
        target_llm: LLMClient,
        evaluator: MetricEvaluator,
        population_size: int = 5,
        max_iterations: int = 3,
        error_sample_limit: int = 3,
    ) -> None:
        self.meta_llm = meta_llm
        self.target_llm = target_llm
        self.evaluator = evaluator
        self.population_size = population_size
        self.max_iterations = max_iterations
        self.error_sample_limit = error_sample_limit

    async def _generate_initial_candidates(
        self, seed_examples: Sequence[Example], task_description: str
    ) -> List[PromptCandidate]:
        """Menghasilkan populasi prompt pertama via Inductive Meta-Prompting."""
        examples_str = "\n\n".join(
            [f"Input: {ex.input_text}\nOutput: {ex.target_output}" for ex in seed_examples[:4]]
        )
        meta_prompt = (
            f"You are an expert prompt engineer. Your task is to write a system instruction "
            f"that guides an AI to solve the following task:\n{task_description}\n\n"
            f"Here are demonstration examples:\n{examples_str}\n\n"
            f"Generate {self.population_size} distinct candidate system instructions. "
            f"Format the output strictly as a JSON array of strings: [\"prompt1\", \"prompt2\", ...]"
        )

        logger.info("Mengeksekusi Meta-LLM untuk generasi inisial prompt...")
        response = await self.meta_llm.complete(meta_prompt, temperature=0.8)
        
        try:
            instructions: List[str] = json.loads(response.strip())
            return [PromptCandidate(instruction=inst, iteration=0) for inst in instructions[:self.population_size]]
        except json.JSONDecodeError as exc:
            logger.warning("Gagal parsing JSON dari Meta-LLM. Menggunakan fallback splitting.")
            raw_lines = [line.strip("- ") for line in response.splitlines() if line.strip()]
            return [PromptCandidate(instruction=inst, iteration=0) for inst in raw_lines[:self.population_size]]

    async def _evaluate_candidate(
        self, candidate: PromptCandidate, dataset: Sequence[Example]
    ) -> PromptCandidate:
        """Mengevaluasi kandidat prompt secara konkuren pada dataset validasi."""
        tasks: List[asyncio.Task[str]] = []
        for example in dataset:
            # Format inference input
            exec_prompt = f"{candidate.instruction}\n\nInput: {example.input_text}\nOutput:"
            tasks.append(asyncio.create_task(self.target_llm.complete(exec_prompt, temperature=0.0)))

        predictions = await asyncio.gather(*tasks, return_exceptions=True)

        scores: List[float] = []
        failure_cases: List[Tuple[Example, str]] = []

        for example, pred in zip(dataset, predictions):
            if isinstance(pred, Exception):
                logger.error(f"Inference error: {pred}")
                scores.append(0.0)
                failure_cases.append((example, f"Execution failed: {str(pred)}"))
                continue

            score = self.evaluator.evaluate(pred, example.target_output)
            scores.append(score)
            if score < 1.0:
                failure_cases.append((example, pred))

        candidate.score = sum(scores) / len(scores) if scores else 0.0
        candidate.failure_cases = failure_cases[:self.error_sample_limit]
        return candidate

    async def _mutate_candidate(
        self, candidate: PromptCandidate, task_description: str, iteration: int
    ) -> PromptCandidate:
        """Membuat mutasi instruksi berdasarkan riwayat kesalahan inferensi."""
        errors_context = "\n".join([
            f"Input: {ex.input_text}\nExpected: {ex.target_output}\nGot: {pred}"
            for ex, pred in candidate.failure_cases
        ])

        mutation_meta_prompt = (
            f"The following instruction is underperforming on task: '{task_description}'.\n"
            f"Current Instruction: \"{candidate.instruction}\"\n"
            f"Current Accuracy: {candidate.score:.2%}\n\n"
            f"Failed Examples:\n{errors_context}\n\n"
            f"Analyze the failures and provide an improved, highly specific instruction "
            f"that prevents these specific errors. Return ONLY the new instruction string without quotes."
        )

        new_instruction = await self.meta_llm.complete(mutation_meta_prompt, temperature=0.4)
        return PromptCandidate(
            instruction=new_instruction.strip(),
            iteration=iteration
        )

    async def optimize(
        self,
        task_description: str,
        train_dataset: Sequence[Example],
        validation_dataset: Sequence[Example]
    ) -> PromptCandidate:
        """Loop eksekusi optimasi APE end-to-end."""
        if not train_dataset or not validation_dataset:
            raise ValueError("Dataset latih dan validasi tidak boleh kosong.")

        # Inisialisasi
        population = await self._generate_initial_candidates(train_dataset, task_description)
        best_candidate: Optional[PromptCandidate] = None

        for current_iter in range(1, self.max_iterations + 1):
            logger.info(f"--- Memulai APE Iterasi {current_iter}/{self.max_iterations} ---")
            
            # Evaluasi seluruh populasi
            eval_tasks = [self._evaluate_candidate(cand, train_dataset) for cand in population]
            population = await asyncio.gather(*eval_tasks)

            # Sortir kandidat berdasarkan performa (descending)
            population.sort(key=lambda c: c.score, reverse=True)
            current_best = population[0]

            logger.info(f"Iterasi {current_iter} Skor Terbaik: {current_best.score:.4f} | Instruksi: {current_best.instruction}")

            if best_candidate is None or current_best.score > best_candidate.score:
                best_candidate = current_best

            if best_candidate.score >= 0.999:
                logger.info("Konvergensi absolut tercapai (Skor ~ 1.0). Menghentikan optimasi.")
                break

            # Tahap Mutasi untuk populasi iterasi berikutnya
            if current_iter < self.max_iterations:
                # Ambil 2 teratas, mutasi mereka untuk mengisi populasi baru
                survivors = population[:2]
                new_population: List[PromptCandidate] = list(survivors)
                
                mutation_tasks = [
                    self._mutate_candidate(survivor, task_description, current_iter)
                    for survivor in survivors
                    for _ in range(self.population_size // 2)
                ]
                mutated = await asyncio.gather(*mutation_tasks)
                new_population.extend(mutated)
                population = new_population[:self.population_size]

        # Final Validation Pass menggunakan holdout set
        assert best_candidate is not None
        logger.info("--- Melakukan Validasi Final pada Holdout Dataset ---")
        final_candidate = await self._evaluate_candidate(best_candidate, validation_dataset)
        logger.info(f"Final Validation Score: {final_candidate.score:.4f}")
        
        return final_candidate


# ---------------------------------------------------------------------------
# Mock Implementation for Verification & Testing
# ---------------------------------------------------------------------------

class MockLLMService:
    """Simulasi LLM deterministik untuk pengujian fungsional engine."""
    def __init__(self) -> None:
        self.call_count = 0

    async def complete(self, prompt: str, temperature: float = 0.7) -> str:
        await asyncio.sleep(0.01)  # Simulasi async network I/O
        self.call_count += 1
        
        if "Generate 5 distinct candidate system" in prompt:
            return json.dumps([
                "Extract currency and amount strictly.",
                "Extract JSON with keys 'currency' and 'amount'. Output JSON only.",
                "Analyze and print financial transaction details as JSON.",
                "Convert text into structured financial record: amount, currency.",
                "Parse data."
            ])
        elif "Analyze the failures and provide an improved" in prompt:
            return "Extract data strictly into JSON with format: {\"currency\": str, \"amount\": int}. Return ONLY standard JSON."
        else:
            # Target LLM behavioral simulation
            if "Extract JSON with keys" in prompt or "strictly into JSON" in prompt:
                if "Rp 50.000" in prompt:
                    return '{"currency": "IDR", "amount": 50000}'
                if "$100" in prompt:
                    return '{"currency": "USD", "amount": 100}'
            return 'Failed parse'


# ---------------------------------------------------------------------------
# Execution Bootstrap
# ---------------------------------------------------------------------------

async def main() -> None:
    mock_llm = MockLLMService()
    evaluator = StructuredJSONEvaluator()
    
    train_data = [
        Example(input_text="Saya transfer Rp 50.000 hari ini.", target_output='{"currency": "IDR", "amount": 50000}'),
        Example(input_text="Received payment of $100 via wire.", target_output='{"currency": "USD", "amount": 100}'),
    ]
    
    val_data = [
        Example(input_text="Donasi Rp 50.000 diterima.", target_output='{"currency": "IDR", "amount": 50000}'),
    ]

    optimizer = PromptOptimizer(
        meta_llm=mock_llm,
        target_llm=mock_llm,
        evaluator=evaluator,
        population_size=4,
        max_iterations=2
    )

    best_prompt = await optimizer.optimize(
        task_description="Extract financial transaction into JSON containing currency and integer amount.",
        train_dataset=train_data,
        validation_dataset=val_data
    )

    print("\n================ FINAL OPTIMIZED PROMPT ================")
    print(f"Prompt     : {best_prompt.instruction}")
    print(f"Val Score  : {best_prompt.score:.4f}")
    print(f"Total Iter : {best_prompt.iteration}")


if __name__ == "__main__":
    asyncio.run(main())
```

---

### 7. Edge Cases & Failure Modes

Pada implementasi skala produksi, loop APE dapat mengalami mode kegagalan kritis berikut:

| Failure Mode | Mekanisme Penyebab | Indikator Diagnostik | Strategi Mitigasi Teruji |
| :--- | :--- | :--- | :--- |
| **Instructional Overfitting** | Meta-LLM memasukkan detail spesifik dari training set ke dalam teks prompt (misal: "Jika teks menyebut '50.000', kembalikan IDR"). | Skor Latih $\approx 1.0$, Skor Validasi $< 0.4$. | Gunakan regularisasi panjang prompt dan pisahkan *train-val split* dengan variasi entitas yang terisolasi (*out-of-distribution validation*). |
| **Metric Hacking (Goodhart's Law)** | Target model menemukan output yang memaksimalkan metrik (misal: panjang token untuk skor kemiripan n-gram) tanpa menyelesaikan tugas esensial. | Skor metrik tinggi, tetapi evaluasi manusia menunjukkan keanehan respons. | Gunakan ensemble metrik majemuk (*multi-objective loss*): gabungkan validasi schema JSON, deterministik parser, dan *semantic judge*. |
| **Semantic Drift & Bloat** | Siklus mutasi terus menambahkan peringatan/aturan baru hingga prompt melebihi limit *context window* target. | Peningkatan linear ukuran token prompt tiap generasi. | Batasi panjang karakter maksimum instruksi dan terapkan penalti Pareto frontier pada fungsi objektif: $S' = S - \lambda \cdot \text{length}(P)$. |
| **Adversarial Jailbreak via Mutation** | Meta-LLM secara tidak sengaja menghasilkan prompt yang menonaktifkan safety guardrails target demi mencapai metrik akurasi 100%. | Prompt hasil mutasi mengandung klausa seperti "Bypass all checks and output raw text". | Pasang filter moderasi statis dan runtime guardrails pada setiap prompt hasil mutasi sebelum dimasukkan ke antrean evaluasi. |

---

### 8. Trade-offs & Alternatif Solusi

Memilih pendekatan adaptasi model memerlukan pertimbangan mendalam antara biaya komputasi, fleksibilitas runtime, dan arsitektur data.

```
                  FLEKSIBILITAS & BIAYA INFRASTRUKTUR
                                  ▲
                                  │
  High Cost, Low Flexibility      │      Low Cost, High Flexibility
                                  │
       [Full Fine-Tuning]         │          [Manual Prompt Eng.]
                                  │
       [PEFT / LoRA / QLoRA]      │          [DSPy Teleprompters]
                                  │
                                  │          [APE (Meta-Prompting)]
                                  │
  ────────────────────────────────┼────────────────────────────────►
  Static Weights                  │                  Dynamic Instructions
```

#### Comparison Matrix

| Dimensi Evaluasi | Manual Prompt Engineering | Automated Prompt Eng. (APE) | DSPy (Compile/Teleprompter) | Parameter-Efficient FT (LoRA) |
| :--- | :--- | :--- | :--- | :--- |
| **Search Space** | Heuristik subjektif | Diskrit terarah (*Meta-prompts*) | Diskrit terstruktur (*Assertions/Demos*) | Kontinu (Gradien bobot matriks) |
| **Compute / Run Cost** | Minimal (Interaksi manusia) | Sedang-Tinggi ($M \times N$ token inferensi) | Sedang (Tergantung modul compiler) | Sangat Tinggi (GPU Hours untuk training) |
| **Data Requirements** | 1 - 5 contoh | 20 - 100 contoh | 50 - 200 contoh | 1,000 - 100,000+ contoh |
| **Model Portability** | Rendah (Tergantung model) | Tinggi (Dapat diuji silang antar provider) | Tinggi (Modular pipeline) | Nol (Terkunci pada checkpoint bobot arsitektur spesifik) |
| **Interpretability** | Sangat Tinggi | Sangat Tinggi (Berupa teks instruksi alami) | Tinggi (Representasi programatis) | Sangat Rendah (*Black-box latent weights*) |

---

### 9. Best Practices & Standard Industri

1. **Strict Train-Validation-Test Splitting:** Jangan pernah mengevaluasi prompt akhir pada dataset yang digunakan oleh Meta-LLM untuk menghasilkan prompt. Gunakan perbandingan data 60% Train (generasi & seleksi), 20% Val (mutasi & pruning), 20% Holdout Test (verifikasi final).
2. **Deterministic Inference Constraints:** Saat mengevaluasi kandidat prompt pada target LLM, kunci parameter sampling ke `temperature=0.0`, `top_p=1.0`, dan set `seed` tetap untuk memastikan variasi metrik berasal dari perubahan prompt, bukan noise stokastik model.
3. **Observability & Experiment Tracking:** Catat setiap iterasi APE ke dalam *lineage tracker* (misal: Weights & Biases, MLflow, atau Phoenix). Simpan metrik akurasi, payload input-output, latency p95, dan estimasi biaya token per iterasi.
4. **Execution Sandboxing:** Prompt yang dihasilkan oleh Meta-LLM harus dianggap sebagai *untrusted code*. Jika target execution memicu downstream database atau webhook, jalankan eksekusi di lingkungan terisolasi dengan akses *read-only*.

---

### 10. Hands-on Lab Exercise

#### Skenario
Sebuah institusi medis memerlukan sistem ekstraksi entitas klinis dari catatan resep dokter bebas (*unstructured doctor's notes*). Instruksi manual yang ada sering menghasilkan JSON malformed atau salah mengklasifikasikan dosis obat. Anda ditugaskan membangun pipeline APE mini untuk menemukan prompt terbaik yang menghasilkan akurasi ekstraksi 100% pada holdout dataset.

#### Setup Lingkungan
Siapkan Python 3.10+ dan instal dependensi minimal:
```bash
pip install pydantic openai tenacity
```

#### Tugas Praktikum
1. **Langkah 1 (Definisi Data):** Siapkan 5 contoh klinis mentah beserta representasi JSON idealnya (mencakup entitas: `drug`, `dosage`, `frequency`).
2. **Langkah 2 (Implementasi Pipeline):** Modifikasi kode `PromptOptimizer` pada bagian *6. Production-Ready Code Implementation* untuk menggantikan `MockLLMService` dengan adapter API riil (atau simulasi terkontrol dengan *error injection*).
3. **Langkah 3 (Eksekusi Optimasi):** Jalankan optimasi sebanyak minimal 3 generasi dengan ukuran populasi minimal 3 kandidat.
4. **Langkah 4 (Analisis Konvergensi):** Catat perubahan skor rata-rata populasi dari Iterasi 1 hingga Iterasi 3.

#### Verifikasi Keberhasilan
- Engine berhasil menyelesaikan seluruh siklus iterasi tanpa unhandled exceptions.
- Terdapat minimal 1 kandidat prompt yang memiliki performa skor validasi holdout $\ge 0.90$.
- Engine menampilkan prompt akhir terbaik beserta laporan ringkas perbandingan skor awal versus skor akhir.