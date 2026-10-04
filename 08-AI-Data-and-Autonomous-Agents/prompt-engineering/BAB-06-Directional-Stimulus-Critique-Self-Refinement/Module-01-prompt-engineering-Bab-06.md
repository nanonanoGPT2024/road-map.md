# Bab 06: Directional Stimulus, Critique, & Self-Refinement Module 01

## 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Merancang Arsitektur Feedback Loop:** Mengimplementasikan pola interaksi *Generator-Critic-Refiner* berbasis multi-pass execution loop untuk memvalidasi dan memitigasi halusinasi model.
- **Mengintegrasikan Directional Stimulus Prompting (DSP):** Mengarahkan model bahasa besar (*Large Language Models*) menggunakan stimulus/petunjuk spesifik (*hints/keywords*) yang diinjeksi secara dinamis ke dalam ruang inferensi tanpa fine-tuning bobot model.
- **Mengonstruksi Automated Critique Metrics:** Membangun evaluasi deterministik dan probabilistik untuk mengukur kualitas draf output terhadap rubrik operasional tingkat *enterprise*.
- **Mengoptimalkan Convergence & Termination Rules:** Mengontrol latensi dan biaya inferensi melalui batas konvergensi matematis (*loss threshold*, skor kepatuhan, dan pembatas rekursi).
- **Membangun Sistem Self-Correction yang Tahan Kegagalan:** Menghindari fenomena *degradation spiral* (di mana output memburuk seiring bertambahnya iterasi perbaikan) menggunakan state checkpointing dan fallback logic.

---

## 2. Concept Overview

Sistem inferensi *single-shot* standar sering kali gagal memenuhi standar akurasi enterprise pada tugas-tugas penalaran kompleks (*complex reasoning*), kepatuhan regulasi, atau transformasi data terstruktur. Dua metodologi utama untuk mengatasi keterbatasan ini adalah **Directional Stimulus Prompting (DSP)** dan **Critique & Self-Refinement Loops**.

```
[Standard Inference]
Input Prompt ─────────────────────────────────────────► Model Output (Raw / Unverified)

[DSP + Self-Refinement Architecture]
Input Prompt ──► [Stimulus Generator] ──► Hints/Keywords
                         │                      │
                         ▼                      ▼
Input Prompt ──────────────────────────► [Generator] ──► Initial Draft
                                                            │
                                  ┌─────────────────────────┘
                                  ▼
                          [Critic / Evaluator] ◄── Rubric / Constraints
                                  │
                   Pass Criteria? │
                 ┌────────────────┴────────────────┐
                 ▼ (Yes)                           ▼ (No)
            Final Output                Actionable Critique
                                                   │
                                                   ▼
                                        [Refinement Engine]
                                                   │
                                                   └──► Refined Draft ──┐
                                                                        │
                                                                        ▼
                                                            (Back to Evaluator)
```

### Mental Model: Prinsip Kerja Inti
1. **Directional Stimulus Prompting (DSP):** Berfungsi sebagai pemandu arah pencarian dalam ruang token generatif (*latent space steering*). Alih-alih membiarkan model menggeneralisasi bebas, model kecil (atau langkah inferensi ringan) menghasilkan token pemicu (*stimulus*) yang mengarahkan atensi model pada elemen fakta atau batasan spesifik.
2. **Critique Agent:** Mengabaikan pembuatan konten baru dan berfokus murni pada analisis kesenjangan (*gap analysis*). Evaluator ini membandingkan output draf dengan *ground truth*, batasan skema JSON, atau aturan operasional deterministik.
3. **Refinement Step:** Menerima draf sebelumnya beserta daftar kritik eksplisit dan arahan arah baru untuk menghasilkan perbaikan yang terisolasi hanya pada bagian yang cacat (*localized patch execution*).

---

## 3. Why It Matters

Dalam implementasi skala produksi (seperti ekstraksi data hukum, diagnosa medis berbantuan AI, dan analisis transaksi finansial), *hallucination rate* sebesar 2-5% tidak dapat ditoleransi. Pendekatan konvensional dengan memperpanjang instruksi sistem (*system prompt bloating*) memicu fenomena *Lost in the Middle*, di mana model mengabaikan instruksi di tengah konteks panjang.

Kebutuhan Enterprise:
- **Kepatuhan Kebijakan yang Ketat (Deterministic Policy Adherence):** Mengoreksi pelanggaran format (seperti kebocoran PII atau ketidakpatuhan ISO-27001) secara otonom sebelum data meninggalkan batas sistem.
- **Efisiensi Token vs. Akurasi:** Fine-tuning model berukuran 70B parameter memakan biaya tinggi. DSP dan Self-Refinement memungkinkan penggunaan model 8B atau model komersial *off-the-shelf* dengan metrik akurasi setara atau melebihi model *fine-tuned*.
- **Observabilitas dan Auditability:** Perusahaan membutuhkan jejak audit (*audit trail*). Siklus perbaikan menghasilkan artefak diskrit: Draf 1 $\rightarrow$ Temuan Audit $\rightarrow$ Draf 2 $\rightarrow$ Output Disetujui.

---

## 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan siklus kontrol *Stateful Self-Refinement with Directional Guidance*:

```
+----------------------------------------------------------------------------------------------------+
|                                    ORCHESTRATION PIPELINE                                          |
|                                                                                                    |
|  +------------------------+      +---------------------------+      +---------------------------+  |
|  |     Original Task      | ---> | Directional Stimulus Gen  | ---> |   Stimulus Injected Task   |  |
|  +------------------------+      +---------------------------+      +---------------------------+  |
|                                                                                   |                |
|                                                                                   v                |
|  +---------------------------------------------------------------------------------------------+  |
|  | Execution Memory State                                                                      |  |
|  |  - History: [Draft_0, Critique_0, Draft_1, Critique_1]                                      |  |
|  |  - Best Score: Float                                                                        |  |
|  |  - Best Artifact: String                                                                    |  |
|  +---------------------------------------------------------------------------------------------+  |
|         ^                                                                         |                |
|         |                                                                         v                |
|  +---------------+      +-------------------------+      Score >= Thresh?   +------------------+  |
|  | Refiner Model | <--- | Critique/Feedback Engine|<------------------------| Generator Model  |  |
|  +---------------+      +-------------------------+                         +------------------+  |
|         |                            ^                                            | (Iter 0)       |
|         |                            |                                            v                |
|         |                            +-------------------------------------- [Candidate Draft]     |
|         |                                                                                          |
|         +-------------------------------------------------------------------------+                |
|                                                                                   |                |
|                                                                                   v                |
|                                                                            Score >= Target?        |
|                                                                            [Yes] ----> Terminate   |
|                                                                            [No]  ----> Loop/Fallback
+----------------------------------------------------------------------------------------------------+
```

---

## 5. Deep Dive Mekanisme & Prinsip Kerja

### A. Directional Stimulus Mechanics
DSP memisahkan proses inferensi menjadi dua tahap:
$$\text{Output} \sim P(Y \mid X, S)$$
Di mana:
- $X$ adalah input prompt pengguna.
- $S = \text{Stimulus Generator}(X)$ adalah representasi instruksi kompak (misal: daftar kata kunci entitas, batas interval nilai).
- $Y$ adalah respons target.

Stimulus $S$ bertindak sebagai filter *conditional distribution*. Jika $X$ menanyakan ringkasan laporan keuangan, $S$ dapat berupa: `[STIMULUS: EBITDA margin; Net Debt; QoQ Growth; Exclude non-operational charges]`.

### B. The Critique-Refinement Protocol
Siklus perbaikan bekerja melalui pemetaan keadaan rekursif:
1. $Y_0 \sim \text{LLM}_{\text{gen}}(X, S)$
2. Untuk iterasi $t = 1, \dots, T_{\max}$:
   - $C_t, \text{Score}_t \sim \text{LLM}_{\text{critique}}(X, Y_{t-1}, \mathcal{R})$ di mana $\mathcal{R}$ adalah rubrik evaluasi.
   - Jika $\text{Score}_t \ge \tau$ (ambang batas penerimaan), terminasi dan kembalikan $Y_{t-1}$.
   - Jika $\text{Score}_t < \tau$, simpan draf dan hasilkan perbaikan:
     $$Y_t \sim \text{LLM}_{\text{refine}}(X, Y_{t-1}, C_t, S)$$
3. Fallback: Jika $t = T_{\max}$, kembalikan draf dengan $\arg\max(\text{Score})$.

### C. The Degradation Trap
Model yang dibiarkan memperbaiki diri tanpa verifikasi independen cenderung mengalami *over-correction*, di mana mereka menghilangkan informasi valid demi menenangkan kritik parsial. Evaluator harus mengeksekusi *Strict Rubric Scoring* berbasis skema tervalidasi yang melacak metrik presisi dan kelengkapan (*recall*).

---

## 6. Production-Ready Code Implementation

Berikut adalah implementasi *Critic-Refiner Pipeline* menggunakan Python 3.11+, Pydantic V2, dan integrasi tipe data asinkron.

```python
"""
Module: directional_refinement_pipeline.py
Description: Production-ready Self-Refinement architecture with Directional Stimulus
             and deterministic evaluation fallback.
"""

from __future__ import annotations
import asyncio
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ValidationError


# ==========================================
# 1. Pydantic Schemas for Strict Typing
# ==========================================

class DirectionalStimulus(BaseModel):
    key_themes: List[str] = Field(description="Daftar kata kunci esensial yang harus tercakup.")
    excluded_elements: List[str] = Field(description="Elemen yang dilarang muncul dalam output.")
    target_format_constraint: str = Field(description="Struktur tata letak yang harus dipenuhi.")


class CritiqueResult(BaseModel):
    score: float = Field(ge=0.0, le=1.0, description="Nilai kelayakan teks (0.0 sampai 1.0).")
    violations: List[str] = Field(default_factory=list, description="Daftar kegagalan pemenuhan rubrik.")
    actionable_remediations: List[str] = Field(
        default_factory=list, description="Langkah konkret untuk memperbaiki kesalahan."
    )
    is_acceptable: bool = Field(description="Indikator boolean apakah output layak dirilis.")


class RefinementState(BaseModel):
    iteration: int
    draft: str
    critique: Optional[CritiqueResult] = None


# ==========================================
# 2. Simulated LLM Client Adapter
# ==========================================

class MockLLMService:
    """
    Simulasi client inferensi LLM.
    Pada implementasi nyata, ganti dengan OpenAI, Anthropic, atau vLLM Async Client.
    """
    async def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
        await asyncio.sleep(0.05)  # Simulasi latensi I/O jaringan
        # Dummy behavior didasarkan pada system_prompt
        if "Stimulus Generator" in system_prompt:
            return (
                '{"key_themes": ["ROI", "SLA 99.99%", "SOC2"], '
                '"excluded_elements": ["perkiraan harga", "kompetitor X"], '
                '"target_format_constraint": "Tiga paragraf bisnis profesional"}'
            )
        elif "Critic Engine" in system_prompt:
            # Skenario: Iterasi pertama gagal, iterasi kedua sukses
            if "DRAFT KE-0" in user_prompt:
                return (
                    '{"score": 0.65, "violations": ["Tidak mencantumkan status SOC2", "Masih menyebut estimasi biaya"], '
                    '"actionable_remediations": ["Tambahkan klausul SOC2", "Hapus estimasi harga"], '
                    '"is_acceptable": false}'
                )
            else:
                return (
                    '{"score": 0.95, "violations": [], '
                    '"actionable_remediations": [], '
                    '"is_acceptable": true}'
                )
        elif "Refinement Engine" in system_prompt:
            return (
                "Solusi enterprise kami menjamin SLA 99.99% dan efisiensi ROI maksimal. "
                "Infrastruktur telah tervalidasi sepenuhnya melalui audit kepatuhan SOC2 Type II. "
                "Implementasi teknis dirancang khusus untuk reliabilitas beban kerja tinggi."
            )
        # Default generator
        return (
            "Solusi kami menawarkan SLA 99.99% dengan perkiraan harga bersaing. "
            "Implementasi kami dirancang untuk ROI yang optimal tanpa hambatan operasional."
        )


# ==========================================
# 3. Core Engine Implementation
# ==========================================

class SelfRefinementOrchestrator:
    def __init__(
        self,
        llm_service: MockLLMService,
        max_iterations: int = 3,
        acceptance_threshold: float = 0.85
    ):
        self.llm = llm_service
        self.max_iterations = max_iterations
        self.threshold = acceptance_threshold

    async def _generate_stimulus(self, task: str) -> DirectionalStimulus:
        sys_prompt = (
            "Role: Directional Stimulus Generator.\n"
            "Analyze the task and output valid JSON conforming strictly to:\n"
            "{'key_themes': [...], 'excluded_elements': [...], 'target_format_constraint': '...'}"
        )
        raw_resp = await self.llm.generate(sys_prompt, task, temperature=0.0)
        return DirectionalStimulus.model_validate_json(raw_resp)

    async def _generate_initial_draft(self, task: str, stimulus: DirectionalStimulus) -> str:
        sys_prompt = (
            "Role: Principal Generator.\n"
            f"Directional Guardrails:\n"
            f"- Focus Keywords: {', '.join(stimulus.key_themes)}\n"
            f"- Disallowed: {', '.join(stimulus.excluded_elements)}\n"
            f"- Format: {stimulus.target_format_constraint}\n"
            "Generate the initial draft."
        )
        return await self.llm.generate(sys_prompt, task, temperature=0.3)

    async def _evaluate_draft(
        self, task: str, draft: str, stimulus: DirectionalStimulus, iteration: int
    ) -> CritiqueResult:
        sys_prompt = (
            "Role: Strict Critic Engine.\n"
            "Evaluate the draft against requirements. Return pure JSON conforming strictly to:\n"
            "{'score': float, 'violations': [...], 'actionable_remediations': [...], 'is_acceptable': bool}"
        )
        user_prompt = (
            f"Iterasi Konteks: DRAFT KE-{iteration}\n"
            f"Tugas Asli: {task}\n"
            f"Draf: {draft}\n"
            f"Kebutuhan Tema: {stimulus.key_themes}\n"
            f"Elemen Terlarang: {stimulus.excluded_elements}"
        )
        raw_resp = await self.llm.generate(sys_prompt, user_prompt, temperature=0.0)
        return CritiqueResult.model_validate_json(raw_resp)

    async def _refine_draft(
        self,
        task: str,
        current_draft: str,
        critique: CritiqueResult,
        stimulus: DirectionalStimulus
    ) -> str:
        sys_prompt = (
            "Role: Refinement Engine.\n"
            "Revise the existing text based explicitly on the critique violations and feedback.\n"
            "Do not introduce new unverified claims. Maintain adherence to directional stimulus."
        )
        user_prompt = (
            f"Tugas: {task}\n"
            f"Draf Sebelumnya: {current_draft}\n"
            f"Temuan Pelanggaran: {critique.violations}\n"
            f"Instruksi Perbaikan: {critique.actionable_remediations}\n"
            f"Panduan Arah: {stimulus.key_themes}"
        )
        return await self.llm.generate(sys_prompt, user_prompt, temperature=0.2)

    async def run(self, user_task: str) -> Dict[str, Any]:
        execution_trace: List[RefinementState] = []

        # Langkah 1: Generate Directional Stimulus
        stimulus = await self._generate_stimulus(user_task)

        # Langkah 2: Draft Awal
        current_draft = await self._generate_initial_draft(user_task, stimulus)
        best_draft = current_draft
        highest_score = -1.0

        # Langkah 3: Iterasi Feedback Loop
        for iteration in range(self.max_iterations):
            critique = await self._evaluate_draft(user_task, current_draft, stimulus, iteration)
            
            trace_entry = RefinementState(
                iteration=iteration,
                draft=current_draft,
                critique=critique
            )
            execution_trace.append(trace_entry)

            # Update state terbaik untuk mitigasi degradation spiral
            if critique.score > highest_score:
                highest_score = critique.score
                best_draft = current_draft

            # Evaluasi Kriteria Terminasi
            if critique.is_acceptable and critique.score >= self.threshold:
                return {
                    "status": "CONVERGED",
                    "final_output": current_draft,
                    "final_score": critique.score,
                    "iterations_used": iteration + 1,
                    "trace": [t.model_dump() for t in execution_trace]
                }

            # Eksekusi Perbaikan (jika belum mencapai iterasi maksimal)
            if iteration < self.max_iterations - 1:
                current_draft = await self._refine_draft(
                    user_task, current_draft, critique, stimulus
                )

        # Fallback ke draf terbaik jika loop mencapai batas maksimum
        return {
            "status": "MAX_ITERATIONS_REACHED_FALLBACK",
            "final_output": best_draft,
            "final_score": highest_score,
            "iterations_used": self.max_iterations,
            "trace": [t.model_dump() for t in execution_trace]
        }


# ==========================================
# 4. Entrypoint Demo Execution
# ==========================================

async def main():
    orchestrator = SelfRefinementOrchestrator(
        llm_service=MockLLMService(),
        max_iterations=3,
        acceptance_threshold=0.85
    )

    task_input = "Tuliskan pitch pengantar produk cloud storage untuk segmen regulated enterprise."
    result = await orchestrator.run(task_input)

    print("=== HASIL PIPELINE ORCHESTRATION ===")
    print(f"Status           : {result['status']}")
    print(f"Skor Final       : {result['final_score']}")
    print(f"Iterasi Terpakai : {result['iterations_used']}")
    print(f"Output Tervalidasi:\n{result['final_output']}")


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 7. Edge Cases & Failure Modes

Dalam eksekusi skala produksi, implementasikan strategi penanganan pada skenario kegagalan berikut:

| Failure Mode | Mekanisme Terjadinya | Dampak Sistem | Strategi Mitigasi / Fallback |
| :--- | :--- | :--- | :--- |
| **Oscillation Trap** | Refiner bolak-balik antara 2 variasi (A $\rightarrow$ B $\rightarrow$ A) karena kritik yang bertentangan. | Siklus rekursif menghabiskan kuota token tanpa konvergensi. | Simpan *history hashes* teks yang dihasilkan. Jika hash draf baru sama dengan draf $t-2$, lakukan *force break* atau turunkan *temperature* ke `0.0`. |
| **Degradation Spiral** | Koreksi terhadap error kecil justru merusak sintaksis atau menghapus informasi penting lain. | Penurunan skor evaluasi secara monoton ($0.7 \rightarrow 0.5 \rightarrow 0.3$). | Gunakan pola *Best-State Checkpointing*. Simpan selalu draf dengan skor tertinggi, bukan draf terakhir. |
| **Parsing & JSON Breakage** | Critic atau Stimulator menghasilkan output tidak valid (misal: terpotong token limit). | `ValidationError` pada layer serialisasi data. | Terapkan fallback ke regex-based parser, isolasi panggilan dalam blok `try/except`, atau alihkan ke *Deterministic Rule Heuristics*. |
| **Token Budget Exhaustion** | Draf membengkak di setiap iterasi karena Refiner terus menambahkan sanggahan/elaborasi. | Melebihi batas konteks (*Context Window Overflow*) dan memicu latensi tinggi. | Terapkan *Hard Character/Token Truncation* dan arahkan prompt Refiner: *"Ganti (replace), bukan tambahkan (append)"*. |

---

## 8. Trade-offs & Alternatif Solusi

| Dimensi Arsitektur | Single-Pass In-Context Prompting | DSP + Self-Refinement Loop | Fine-Tuned Model (LoRA / SFT) |
| :--- | :--- | :--- | :--- |
| **Latensi per Transaksi** | **Sangat Rendah** (100–800 ms) | **Tinggi** (1.500–5.000 ms, tergantung loop) | **Sangat Rendah** (100–800 ms) |
| **Biaya Token** | **Minimal** ($1\times$ panggilan LLM) | **Tinggi** ($3\times$ hingga $8\times$ panggilan) | **Minimal** (Inferensi standar) |
| **Adaptabilitas Aturan** | **Tinggi** (Cukup ubah deskripsi prompt) | **Sangat Tinggi** (Cukup ubah Stimulus/Kritik) | **Sangat Rendah** (Harus melatih ulang bobot) |
| **Akurasi Domain Kompleks**| **Rendah – Sedang** (Rentan halusinasi) | **Sangat Tinggi** (Koreksi multi-tahap) | **Tinggi** (Pada data yang sejenis dengan data latih) |
| **Kebutuhan Data Latih** | **Tidak Ada** | **Tidak Ada** | **Tinggi** (Ratusan/Ribuan pasang contoh data) |

### Kapan Menggunakan DSP + Self-Refinement:
- Ketika tugas bersifat *asynchronous* (pemrosesan data latar belakang, analisis kepatuhan kontrak, validasi migrasi skema database).
- Ketika biaya kegagalan output jauh lebih mahal daripada biaya ekstra inferensi API token.

---

## 9. Best Practices & Standard Industri

1. **Role Separation (Pemisahan Peran Agen):** Jangan pernah menggabungkan peran Critic dan Refiner dalam satu prompt yang sama. Bias konfirmasi (*confirmation bias*) pada model bahasa menyebabkan model membenarkan kesalahannya sendiri jika diminta mengkritik sekaligus memperbaiki teks dalam satu *inference pass*.
2. **Deterministic-First Evaluation:** Jika suatu aturan dapat dievaluasi menggunakan kode reguler (misal: regex, pemvalidasi skema Pydantic, atau *linter* AST), gunakan evaluasi berbasis program tersebut sebelum menggunakan Critic berbasis LLM. Ini mengurangi latensi dan biaya API.
3. **Impose Strict Monotonic Progress Limits:** Berikan toleransi maksimal $N$ kali iterasi (rekomendasi: $N=3$). Pengujian empiris menunjukkan lebih dari 3 siklus perbaikan jarang meningkatkan kualitas secara signifikan (*diminishing returns*).
4. **Context Pinning:** Selalu sertakan ringkasan instruksi orisinal (*User Intent*) di setiap siklus perbaikan untuk mencegah fenomena pergeseran semantik (*context drift*).

---

## 10. Hands-on Lab Exercise

### Skenario Lab
Anda bertugas membangun *Automated Code Sanitizer* untuk tim keamanan siber. Kode input dari pengguna harus:
1. Memiliki skema penanganan eksepsi eksplisit (`try/except`).
2. Tidak boleh mengandung `eval()` atau `exec()`.
3. Memiliki *type-hinting* lengkap pada signature fungsi.

### Langkah-langkah Praktik

1. **Persiapan Lingkungan:**
   Buat virtual environment dan install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install pydantic==2.6.0
   ```

2. **Tugas Implementasi:**
   Modifikasi file `directional_refinement_pipeline.py` di atas dengan ketentuan:
   - Ganti implementasi `_evaluate_draft` agar menerapkan validasi sintaks deterministik menggunakan modul bawaan Python `ast` (Abstract Syntax Tree) sebelum mengirim kode ke model Critic.
   - Deteksi keberadaan node `ast.Try` dan deteksi pemanggilan fungsi bernama `eval` secara programatik.

```python
# Sisipkan logika AST Validator ini pada Critic Engine Anda
import ast

def deterministic_security_check(code_str: str) -> tuple[bool, list[str]]:
    violations = []
    try:
        tree = ast.parse(code_str)
    except SyntaxError as e:
        return False, [f"Syntax Error: {str(e)}"]

    has_try_block = any(isinstance(node, ast.Try) for node in ast.walk(tree))
    if not has_try_block:
        violations.append("Kode wajib membungkus logika utama dalam blok 'try-except'.")

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in ["eval", "exec"]:
                violations.append(f"Ditemukan fungsi berbahaya: {node.func.id}() dilarang.")

    is_valid = len(violations) == 0
    return is_valid, violations
```

3. **Verifikasi Output:**
   Jalankan pipeline dengan kode input berikut yang sengaja memiliki celah keamanan:
   ```python
   def parse_user_payload(raw_data):
       return eval(raw_data)
   ```
   Pastikan pipeline Anda mendeteksi kesalahan tersebut secara deterministik, menghasilkan critique, lalu memicu perbaikan hingga menghasilkan kode berikut:
   ```python
   import json
   from typing import Any, Dict

   def parse_user_payload(raw_data: str) -> Dict[str, Any]:
       try:
           return json.loads(raw_data)
       except json.JSONDecodeError as exc:
           raise ValueError(f"Payload parsing failed: {exc}")
   ```