# BAB 08: Token Budgeting, Cost Control, & Context Compaction
## Modul 01: Context Optimization & Cost Engineering pada Autonomous Coding Agents

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Mendesain dan Mengimplementasikan Token Accounting Engine**: Membangun sistem telemetri dan kontrol konsumsi token secara deterministik dengan pelacakan *input*, *output*, *cache write*, dan *cache read* berbasis spesifikasi Anthropic Claude 3.5 Sonnet.
2. **Mengonfigurasi Arsitektur Prompt Caching Mutakhir**: Menempatkan *cache breakpoints* (`cache_control: {"type": "ephemeral"}`) secara optimal pada *system prompt*, *repository map*, dan *multi-turn history* guna mencapai *cache hit rate* $\ge 85\%$.
3. **Membangun Pipeline Context Compaction Bertingkat**: Mengimplementasikan algoritma reduksi konteks berbasis *heuristic truncation*, *observation masking*, dan *AST/Symbol distillation* untuk mempertahankan *instruction-following capability* tanpa kehilangan dependensi logis.
4. **Mencegah Context Blowout & Attention Degradation**: Mengisolasi fenomena *Lost in the Middle* dan degradasi performa penalaran pada siklus agen otonom berdurasi panjang (*long-horizon execution*).
5. **Mengintegrasikan Fail-Safe & Budget Guardrails**: Merancang sistem mitigasi otomatis berbasis *hard/soft token limits*, *dynamic fallback models*, dan pemulihan konteks yang terdegradasi.

---

### 2. Concept Overview

Dalam rekayasa *autonomous coding agents* (seperti arsitektur internal Claude Code), *context window* bukan sekadar penampung teks statis, melainkan **volatile L1 working memory** yang memiliki limitasi kapasitas, latensi, dan biaya finansial riil. 

```
+-------------------------------------------------------------------------+
|                         LLM Context Window Architecture                 |
|                                                                         |
|  [System Prompt + Rules] -> Static (Immutable, High Cache Priority)     |
|  [Repository AST Map]    -> Quasi-Static (Invalidated on File Mutate)   |
|  [Conversation History]  -> Dynamic Linear Growth (Requires Compaction) |
|  [Tool Exec Outputs]     -> High Entropy / High Volume (Compaction Target)
+-------------------------------------------------------------------------+
```

#### Mental Model: The Hierarchical Memory Pyramid
Pengelolaan konteks pada agen otonom mengikuti hierarki memori komputasi klasik:
1. **L1: Context Window Aktif (LLM Working Memory)**: Sangat mahal, sangat cepat diakses model, kapasitas terbatas ($200\text{k}$ token pada Claude 3.5 Sonnet).
2. **L2: Ephemeral Prompt Cache (Anthropic Server-Side)**: Retensi 5 menit, biaya read hanya $10\%$ dari base input cost, memerlukan stabilitas prefix byte-to-byte.
3. **L3: Local Disk / Vector Index / SQLite (Persistent Agent Memory)**: Kapasitas tak terbatas, latensi retrieval tinggi, memerlukan mekanisme *selective hydration*.

#### Token Bloat dan Attention Degradation
Ketika agen otonom melakukan eksekusi seperti `git diff`, `npm test`, atau pembacaan file source code secara berulang, konteks membengkak secara eksponensial. Hal ini memicu dua permasalahan kritis:
* **Cost Acceleration**: Biaya inferensi per langkah berbanding lurus dengan panjang riwayat percakapan jika tidak memanfaatkan caching.
* **Attentional Dilution ("Lost in the Middle")**: Transformer attention mechanism mengalami penurunan akurasi retrieval ketika informasi penting terkubur di tengah-tengah puluhan ribu token output compiler atau stack trace yang tidak relevan.

---

### 3. Why It Matters

Dalam implementasi skala *enterprise*, agen otonom yang dibiarkan beroperasi tanpa batas token dapat menghabiskan puluhan dolar per task hanya dalam beberapa puluh iterasi loop, terutama ketika terjadi *infinite tool execution loop*.

| Metrik | Tanpa Token Control & Caching | Dengan Compaction & Prompt Caching | Dampak Enterprise |
| :--- | :--- | :--- | :--- |
| **Biaya per 50-Step Task** | $\sim \$12.50 - \$28.00$ | $\sim \$0.85 - \$2.10$ | **Penghematan 85% - 93%** |
| **Time To First Token (TTFT)** | $4.5\text{s} - 8.2\text{s}$ | $0.8\text{s} - 1.5\text{s}$ | **Akselerasi Kecepatan Agen 4x** |
| **Context Exhaustion Rate** | $32\%$ pada iterasi $> 30$ | $< 0.5\%$ (Auto-compacting) | **Stabilitas Produksi Tinggi** |
| **Model Hallucination Rate** | Meningkat setelah 80k token | Stabil sepanjang eksekusi | **Akurasi Eksekusi Kode Tinggi** |

Tanpa *token budgeting* dan *compaction*, sistem *agentic coding* tidak layak dideploy di lingkungan produksi enterprise yang memiliki target *budget cap* ketat dan tuntutan keandalan tinggi (*SLA*).

---

### 4. Arsitektur & Diagram Komponen

Berikut adalah arsitektur *Context Management Pipeline* yang memproses setiap *turn* sebelum dan sesudah interaksi dengan Anthropic Messages API:

```
[Agent Core Loop]
       |
       v
+-------------------------------------------------------------+
| 1. Token Metering & Budget Accounting Engine                |
|    - Hitung delta token & akumulasi biaya real-time         |
|    - Cek Soft Cap (Compaction Trigger) & Hard Cap (Abort)   |
+-------------------------------------------------------------+
       |
       +---> [Budget Exceeded?] ---> YES ---> [Safe Abort / Fallback Handler]
       |
       NO
       v
+-------------------------------------------------------------+
| 2. Context Compactor Engine                                 |
|    +-------------------------------------------------------+|
|    | Sub-pipeline A: Tool Output Truncator (Head/Tail)     ||
|    | Sub-pipeline B: AST / Structural Code Distillation    ||
|    | Sub-pipeline C: Observation Masking & Message Squash  ||
|    +-------------------------------------------------------+|
+-------------------------------------------------------------+
       |
       v
+-------------------------------------------------------------+
| 3. Prompt Cache Alignment Engine                            |
|    - Identifikasi Stable Prefix Boundary                    |
|    - Injeksi ephemeral cache_control (Maks. 4 Breakpoints)  |
|      * Breakpoint 1: Base System Rules                      |
|      * Breakpoint 2: Repository Structure & Types           |
|      * Breakpoint 3: Multi-turn History (T-1 Checkpoint)     |
|      * Dynamic Tail: Tool Use Input/Output Terbaru          |
+-------------------------------------------------------------+
       |
       v
+-------------------------------------------------------------+
| 4. Anthropic Messages API Provider                          |
|    (Claude 3.5 Sonnet Engine)                               |
+-------------------------------------------------------------+
       |
       v
[Response & Usage Telemetry Hook] ---> Update Ledger ---> [Next Step]
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### 5.1. Anthropic Prompt Caching Mechanics
Anthropic API menyediakan *ephemeral prompt caching* dengan aturan deterministik:
* **Minimum Cacheable Length**: 1.024 token untuk Claude 3.5 Sonnet. Prefix di bawah batas ini otomatis dilewati oleh cache compiler.
* **Cache Lifetime**: 5 menit *sliding window*. Setiap kali cache read berhasil, masa berlaku diperpanjang 5 menit lagi.
* **Maksimum Breakpoints**: Sebanyak 4 blok dalam satu request dapat ditandai dengan `"cache_control": {"type": "ephemeral"}`.
* **Cache Invalidation Rule**: Caching beroperasi strictly dari karakter pertama (*top-down byte-prefix matching*). Jika karakter ke-100 berubah, semua cache breakpoint di bawahnya (karakter $> 100$) dianggap *cache miss* dan ditulis ulang (*cache write*).

Struktur hirarkis penempatan breakpoint:
1. **Cache Point 1**: System Prompt Inti (Aturan perilaku, safety instruction, tool definitions).
2. **Cache Point 2**: Workspace Index / Context Manifest (Daftar file, definisi tipe data/interface global, AST summary).
3. **Cache Point 3**: Conversation History hingga turn $N-2$ (Blok riwayat yang sudah final dan tidak akan bermutasi).
4. **Dynamic Section**: Turn $N-1$ dan turn $N$ (User message terbaru dan pemanggilan tool yang sedang dieksekusi).

#### 5.2. Context Compaction Algorithms

Ketika ukuran riwayat percakapan melampaui ambang batas (*soft limit*, misal: 100k token), sistem menjalankan 3 teknik pemadatan:

##### A. Structural Tool Output Truncation (Head & Tail Preserving)
Log compiler atau output eksekusi test runner tidak boleh dipotong secara acak. Logika *error* sering kali berada di baris awal (inisialisasi perintah) dan baris akhir (stack trace assertion).
$$\text{Output} = \text{Head}(K \text{ baris}) + \text{"\n... [Truncated } M \text{ lines / } T \text{ tokens] ...\n"} + \text{Tail}(N \text{ baris})$$

##### B. Observation Masking (Message Squashing)
Pada multi-turn tool interaction, intermediate tool result dari 5 langkah sebelumnya (misalnya: file traversal menggunakan `ls` atau `grep`) tidak lagi diperlukan secara verbatim setelah model menghasilkan kesimpulan. Isi intermediate result diganti dengan token sentinel ringkas:
```json
{"role": "user", "content": [{"type": "tool_result", "tool_use_id": "call_123", "content": "[Output pruned: 42 files found. Handled in Assistant response ID: 894]"}]}
```

##### C. Code Distillation via AST Skeletons
Daripada menyuntikkan keseluruhan isi file target ke dalam konteks, sistem parsing membaca file dan membuat representasi *skeleton* (menghapus blok implementasi fungsi dan hanya mempertahankan signature, docstring, serta export statement).

```python
# Sebelum Distilasi (Full implementation: 120 tokens)
def calculate_metrics(data: list[float], weight: float) -> dict[str, float]:
    """Calculate weighted aggregation."""
    acc = sum(x * weight for x in data)
    avg = acc / len(data) if data else 0.0
    variance = sum((x - avg) ** 2 for x in data) / len(data) if data else 0.0
    return {"mean": avg, "variance": variance}

# Sesudah Distilasi (Skeleton: 35 tokens)
def calculate_metrics(data: list[float], weight: float) -> dict[str, float]: ...
```

---

### 6. Production-Ready Code Implementation

Implementasi berikut menggunakan Python 3.11+ murni, fully-typed, modular, dan mengimplementasikan seluruh lifecycle: *Token Budgeting*, *Prompt Cache Breakpointing*, *Log Truncation*, dan *Context Compactor*.

```python
"""
production_context_manager.py
Arsitektur Enterprise Context Compaction & Token Budgeting untuk Claude Code Agents.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class ModelPricing(Enum):
    """Harga Claude 3.5 Sonnet per Million Tokens (USD per Q1 2025)."""
    INPUT_BASE = 3.00
    CACHE_WRITE = 3.75
    CACHE_READ = 0.30
    OUTPUT = 15.00


@dataclass(frozen=True)
class UsageLedger:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0

    @property
    def total_cost_usd(self) -> float:
        cost = (
            (self.input_tokens / 1_000_000) * ModelPricing.INPUT_BASE.value
            + (self.cache_creation_input_tokens / 1_000_000) * ModelPricing.CACHE_WRITE.value
            + (self.cache_read_input_tokens / 1_000_000) * ModelPricing.CACHE_READ.value
            + (self.output_tokens / 1_000_000) * ModelPricing.OUTPUT.value
        )
        return round(cost, 6)


class ContextBlowoutError(Exception):
    """Dilempar jika konsumsi token melebihi Hard Limit."""
    pass


class BudgetExceededError(Exception):
    """Dilempar jika estimasi pengeluaran melebihi limit finansial."""
    pass


@dataclass
class TokenBudgetGuard:
    soft_token_limit: int = 80_000
    hard_token_limit: int = 150_000
    max_budget_usd: float = 5.00
    current_ledger: UsageLedger = field(default_factory=UsageLedger)

    def record_usage(self, response_usage: Dict[str, int]) -> None:
        """Mencatat delta penggunaan dari Anthropic API Response."""
        new_input = response_usage.get("input_tokens", 0)
        new_output = response_usage.get("output_tokens", 0)
        new_cache_write = response_usage.get("cache_creation_input_tokens", 0)
        new_cache_read = response_usage.get("cache_read_input_tokens", 0)

        self.current_ledger = UsageLedger(
            input_tokens=self.current_ledger.input_tokens + new_input,
            output_tokens=self.current_ledger.output_tokens + new_output,
            cache_creation_input_tokens=self.current_ledger.cache_creation_input_tokens + new_cache_write,
            cache_read_input_tokens=self.current_ledger.cache_read_input_tokens + new_cache_read,
        )

        if self.current_ledger.total_cost_usd > self.max_budget_usd:
            raise BudgetExceededError(
                f"Financial Cap Exceeded: ${self.current_ledger.total_cost_usd:.4f} > ${self.max_budget_usd:.4f}"
            )

    def evaluate_capacity(self, estimated_next_input: int) -> bool:
        """Mengembalikan True jika perlu dilakukan pemadatan konteks (soft limit hit)."""
        if estimated_next_input >= self.hard_token_limit:
            raise ContextBlowoutError(
                f"Context Hard Limit Exceeded: {estimated_next_input} >= {self.hard_token_limit}"
            )
        return estimated_next_input >= self.soft_token_limit


class ContextCompactor:
    """Mesin pengeksekusi reduksi ukuran token pada histori pesan dan tool outputs."""

    @staticmethod
    def truncate_head_tail(text: str, head_lines: int = 25, tail_lines: int = 50) -> str:
        """Mempertahankan baris awal dan baris akhir teks output yang panjang."""
        lines = text.splitlines()
        total_lines = len(lines)
        if total_lines <= (head_lines + tail_lines):
            return text

        omitted = total_lines - (head_lines + tail_lines)
        head_part = "\n".join(lines[:head_lines])
        tail_part = "\n".join(lines[-tail_lines:])
        return f"{head_part}\n\n... [TRUNCATED {omitted} INTERMEDIATE LINES] ...\n\n{tail_part}"

    @classmethod
    def compact_tool_results(
        cls, 
        messages: List[Dict[str, Any]], 
        max_tool_chars: int = 2000
    ) -> List[Dict[str, Any]]:
        """Memangkas observation result lampau tanpa merusak struktur protokol chat."""
        compacted_messages: List[Dict[str, Any]] = []

        for message in messages:
            new_message = {"role": message["role"]}
            content = message.get("content")

            if isinstance(content, str):
                new_message["content"] = content
            elif isinstance(content, list):
                new_blocks: List[Dict[str, Any]] = []
                for block in content:
                    if block.get("type") == "tool_result":
                        raw_result = block.get("content", "")
                        if isinstance(raw_result, str) and len(raw_result) > max_tool_chars:
                            processed_result = cls.truncate_head_tail(raw_result)
                            new_blocks.append({
                                **block,
                                "content": processed_result
                            })
                        else:
                            new_blocks.append(block)
                    else:
                        new_blocks.append(block)
                new_message["content"] = new_blocks
            else:
                new_message["content"] = content

            compacted_messages.append(new_message)

        return compacted_messages

    @classmethod
    def squash_stale_observations(
        cls, 
        messages: List[Dict[str, Any]], 
        preserve_recent_turns: int = 4
    ) -> List[Dict[str, Any]]:
        """Mengganti output tool pada langkah-langkah lawas menjadi token tombstone."""
        if len(messages) <= preserve_recent_turns:
            return messages

        cutoff_idx = len(messages) - preserve_recent_turns
        squashed_messages: List[Dict[str, Any]] = []

        for idx, msg in enumerate(messages):
            if idx < cutoff_idx and msg["role"] == "user":
                content = msg.get("content")
                if isinstance(content, list):
                    pruned_blocks: List[Dict[str, Any]] = []
                    for block in content:
                        if block.get("type") == "tool_result":
                            pruned_blocks.append({
                                "type": "tool_result",
                                "tool_use_id": block.get("tool_use_id"),
                                "content": "[Historical observation archived. Model decisions preserved in transcript.]"
                            })
                        else:
                            pruned_blocks.append(block)
                    squashed_messages.append({"role": "user", "content": pruned_blocks})
                    continue
            squashed_messages.append(msg)

        return squashed_messages


class CacheBreakpointManager:
    """
    Menginjeksi deklarasi cache_control ephemeral secara deterministik
    sesuai batas maksimal Anthropic (Maksimal 4 Breakpoints).
    """

    @staticmethod
    def apply_cache_breakpoints(
        system_prompts: List[Dict[str, Any]],
        messages: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Injeksi breakpoint:
        BP 1: Akhir dari System Prompt utama.
        BP 2: File Context / System manifest (jika ada lebih dari 1 block system).
        BP 3: Checkpoint riwayat stabil (turn N - 2).
        BP 4: Checkpoint interaksi tool sebelum turn aktif.
        """
        # 1. Clear existing cache_control markers across all blocks
        processed_system = [
            {k: v for k, v in block.items() if k != "cache_control"}
            for block in system_prompts
        ]
        
        # Apply BP pada blok terakhir system prompt
        if processed_system:
            processed_system[-1]["cache_control"] = {"type": "ephemeral"}

        # 2. Manipulasi messages
        processed_messages: List[Dict[str, Any]] = []
        for msg in messages:
            content = msg["content"]
            if isinstance(content, str):
                cleaned_content = content
            elif isinstance(content, list):
                cleaned_content = [
                    {k: v for k, v in b.items() if k != "cache_control"}
                    for b in content
                ]
            else:
                cleaned_content = content
            processed_messages.append({"role": msg["role"], "content": cleaned_content})

        # Apply BP pada historical checkpoint jika riwayat cukup panjang
        total_messages = len(processed_messages)
        if total_messages >= 4:
            target_msg_idx = total_messages - 3
            target_msg = processed_messages[target_msg_idx]
            
            if isinstance(target_msg["content"], str):
                target_msg["content"] = [
                    {
                        "type": "text",
                        "text": target_msg["content"],
                        "cache_control": {"type": "ephemeral"}
                    }
                ]
            elif isinstance(target_msg["content"], list) and len(target_msg["content"]) > 0:
                target_msg["content"][-1]["cache_control"] = {"type": "ephemeral"}

        return processed_system, processed_messages


# --- CONTOH WORKFLOW ORKESTRASI ---
if __name__ == "__main__":
    guard = TokenBudgetGuard(soft_token_limit=5000, hard_token_limit=10000, max_budget_usd=1.00)
    
    # 1. Inisialisasi Mock System Prompt (2 blok: Core Logic & Workspace Manifest)
    system_blocks = [
        {"type": "text", "text": "Anda adalah Senior Software Engineer Autonomous Agent."},
        {"type": "text", "text": "Workspace Tree:\nsrc/\n  main.py\n  core.py\ntests/\n  test_core.py"}
    ]

    # 2. Simulasi Percakapan dengan Large Tool Output
    large_stdout = "pytest -v\n" + "\n".join([f"PASSED tests/test_core.py::test_case_{i}" for i in range(200)]) + "\nAssertionError in line 402\nFAILED tests/test_core.py::test_case_final"
    
    history: List[Dict[str, Any]] = [
        {"role": "user", "content": "Jalankan unit test pada repositori."},
        {"role": "assistant", "content": [{"type": "tool_use", "id": "call_01", "name": "run_test", "input": {"cmd": "pytest"}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "call_01", "content": large_stdout}]},
        {"role": "assistant", "content": "Ditemukan kegagalan pada test_case_final. Saya akan memeriksa kode."},
        {"role": "user", "content": "Perbaiki kode tersebut sekarang."}
    ]

    print("--- RAW CONTENT ANALYSIS ---")
    raw_size_chars = len(json.dumps(history))
    print(f"Ukuran Char Mentah: {raw_size_chars} chars (~{raw_size_chars // 4} tokens)")

    # 3. Eksekusi Context Compaction
    compacted_history = ContextCompactor.compact_tool_results(history, max_tool_chars=500)
    squashed_history = ContextCompactor.squash_stale_observations(compacted_history, preserve_recent_turns=2)

    # 4. Injeksi Prompt Cache Breakpoints
    sys_final, msgs_final = CacheBreakpointManager.apply_cache_breakpoints(system_blocks, squashed_history)

    print("\n--- OPTIMIZED PAYLOAD STRUCTURE ---")
    print("System Block Cache Marker:", sys_final[-1].get("cache_control"))
    print("Historical Turn Cache Marker:", msgs_final[2]["content"][-1].get("cache_control") if isinstance(msgs_final[2]["content"], list) else "N/A")
    print("Hasil Truncation Tool Result:")
    tool_content = msgs_final[2]["content"][0]["content"]
    print(tool_content[:150] + " ... \n" + tool_content[-100:])

    # 5. Simulasi Feedback Telemetri Anthropic
    mock_api_usage = {
        "input_tokens": 450,
        "output_tokens": 120,
        "cache_creation_input_tokens": 1850,
        "cache_read_input_tokens": 0
    }
    guard.record_usage(mock_api_usage)
    print(f"\nBiaya Step 1: ${guard.current_ledger.total_cost_usd:.6f}")

    # Simulasi Turn Kedua (Cache Read Hit)
    mock_api_usage_turn_2 = {
        "input_tokens": 150,
        "output_tokens": 90,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 1850
    }
    guard.record_usage(mock_api_usage_turn_2)
    print(f"Biaya Step 2 (Cache Hit): ${guard.current_ledger.total_cost_usd:.6f}")
```

---

### 7. Edge Cases & Failure Modes

#### 1. Cache Thrashing Akibat Dynamic Prefix Mutation
* **Kegagalan**: Menyisipkan informasi dinamis (misal: *current timestamp*, *session ID*, atau *resource usage counter*) ke dalam `system prompt` paling atas.
* **Dampak**: Seluruh *byte stream* setelah titik tersebut tidak cocok dengan cache server. *Cache hit rate* jatuh ke $0\%$, memicu *cache creation write* ($125\%$ dari base price) pada setiap iterasi.
* **Mitigasi**: Pindahkan metadata volatil ke blok user message paling akhir. System prompt harus strictly statis dan identik secara biner antar-request.

#### 2. Log Truncation Mengaburkan Akar Masalah (Silent Degradation)
* **Kegagalan**: Pemotongan log compiler yang hanya mengambil head (misal: 50 baris pertama).
* **Dampak**: Pada compiler seperti `gcc` atau test runner seperti `pytest`, pesan inisiasi diletakkan di atas, tetapi pesan *assertion failure* dan baris file yang menyebabkan error berada tepat di akhir log. Model akan berhalusinasi menyatakan "test berhasil" atau "error tidak teridentifikasi".
* **Mitigasi**: Selalu gunakan kombinasi algoritma **Head + Tail Truncation** dengan rasio minimum 1:2 (misal: 25 baris awal, 50 baris akhir).

#### 3. Penghapusan Pasangan ID Pemanggilan Tool (`tool_use_id` Desynchronization)
* **Kegagalan**: Context compactor menghapus blok pesan asisten yang berisi `tool_use` karena menganggapnya teks lama, namun membiarkan pesan user yang berisi `tool_result`.
* **Dampak**: Anthropic API mengembalikan status error `400 Invalid Request: unexpected tool_result id without matching tool_use`.
* **Mitigasi**: Validasi integritas graf pesan. Penghapusan atau pemadatan harus dilakukan secara berpasangan (*atomic pruning* antara node `tool_use` dan `tool_result`).

#### 4. Runaway Tool Loop Menguras Anggaran Finansial
* **Kegagalan**: Agen terjebak dalam siklus: Gagal compile -> Baca file -> Gagal compile -> Baca file.
* **Dampak**: Meskipun konteks dipadatkan, akumulasi pemanggilan API secara terus-menerus menguras saldo deposit API enterprise.
* **Mitigasi**: Implementasikan **Financially Bound Circuit Breakers** via `TokenBudgetGuard` yang memutus eksekusi jika biaya riil melampaui *hard dollar cap* (misalnya: maks $2.00 per task run).

---

### 8. Trade-offs & Alternatif Solusi

Setiap strategi pemadatan konteks melibatkan kompromi teknis:

```
[Lossless Compression] <-------------------------------------> [Aggressive Lossy Distillation]
(Sliding Window / Raw Caching)                                    (Semantic AST / Summarization)
- Preservasi Detail: 100%                                        - Preservasi Detail: Terbatas
- Penggunaan Token: Maksimal                                     - Penggunaan Token: Sangat Efisien
- Risiko Halusinasi: Sangat Rendah                               - Risiko Halusinasi: Sedang/Tinggi
```

| Pendekatan | Keuntungan Utama | Kerugian / Risiko | Skenario Terbaik |
| :--- | :--- | :--- | :--- |
| **Sliding Window (FIFO)** | Sederhana; kompleksitas kalkulasi $O(1)$. | Menghapus instruksi awal user; kehilangan konteks inisiasi. | Task sederhana dengan sedikit dependensi antar-turn. |
| **AST / Interface Distillation** | Menghapus $70\%$ token kode tanpa menghilangkan tipe data. | Kehilangan logika algoritma internal file; membutuhkan parser language-specific. | Eksplorasi repositori skala besar dengan banyak dependensi modul. |
| **Recursive Summarization (via Sub-Agent)** | Memadatkan konteks bebas menjadi ringkasan naratif padat. | Menambah biaya API call tambahan; rentan kehilangan detail error stack trace spesifik. | Long-horizon debugging yang melampaui 100 langkah interaksi. |
| **Observation Tombstoning** | Menjaga histori keputusan model utuh, hanya menghapus payload data mentah. | Jika model perlu mereferensi kembali output tool 10 turn ke belakang, ia harus memanggil tool ulang. | Default state untuk autonomous software engineering agents. |

---

### 9. Best Practices & Standar Industri

1. **Aturan 4 Breakpoints Anthropic**:
   Gunakan alokasi breakpoint secara berdisiplin:
   * BP 1: System Identity + Core Tool Definitions.
   * BP 2: Workspace Map (File listing, architecture markdown).
   * BP 3: Dynamic Workspace Context (File-file relevan yang dibuka).
   * BP 4: Conversation History Turn $N-2$.
2. **Karantina Output CLI/Tooling**: Batasi output dari perintah bash hingga maksimal $4\text{ KB}$ secara default di runtime. Jangan biarkan proses mengeksekusi `cat bundle.js` mentah ke dalam konteks agen.
3. **Standarisasi Telemetri**: Wajib memonitor rasio efisiensi cache:
   $$\text{Cache Hit Efficiency} = \frac{\text{cache\_read\_tokens}}{\text{cache\_read\_tokens} + \text{input\_tokens} + \text{cache\_write\_tokens}} \times 100\%$$
   Target arsitektur kelas produksi adalah $\ge 80\%$.
4. **Preservasi Karakter Kontrol**: Jangan melakukan strip newline (`\n`) atau indentasi pada file kode sumber yang dipadatkan, karena dapat merusak interpretasi bahasa *indentation-sensitive* seperti Python dan YAML.

---

### 10. Hands-on Lab Exercise: Membangun Resilient Budget-Aware Agent Context

#### Skenario Lab
Anda ditugaskan membangun lapisan context engineering untuk *command-line coding agent*. Agen ini harus membaca file log tes yang berukuran masif ($15.000$ kata), mengekstrak bug, memperbaikinya, dan memastikan biaya inferensi total tidak melebihi $\$0.05$ dengan menerapkan *Prompt Caching* dan *Head-and-Tail Truncation*.

#### File Setup
Buat script simulasi interaktif `lab_token_budget.py`:

```python
# lab_token_budget.py
import os
import sys
from production_context_manager import (
    TokenBudgetGuard, 
    ContextCompactor, 
    CacheBreakpointManager,
    ModelPricing
)

def run_lab():
    print("=== MEMULAI LAB CONTEXT COMPACTION & CACHE ALLOCATION ===")
    
    # Inisialisasi Guard dengan limit ketat $0.05
    guard = TokenBudgetGuard(soft_token_limit=2000, hard_token_limit=4000, max_budget_usd=0.05)
    
    # Step 1: Mensimulasikan log output raksasa dari suite test integrasi
    simulated_raw_log = "TEST_START: suite_enterprise_auth\n"
    simulated_raw_log += "\n".join([f"[DEBUG] Processing token payload for user_{i:04d}: verified=True" for i in range(1, 1500)])
    simulated_raw_log += "\n[CRITICAL_FAILURE] Database deadlocked at node-04!\nTraceback:\n  File 'auth.py', line 92, in acquire_lock\n    raise TimeoutError('Lock wait timeout exceeded')\nTEST_END: 1 failed, 1499 passed"

    print(f"[1] Raw Log Length: {len(simulated_raw_log)} characters")

    # Step 2: Aplikasi Head & Tail Truncation
    compacted_log = ContextCompactor.truncate_head_tail(simulated_raw_log, head_lines=5, tail_lines=10)
    print(f"[2] Compacted Log Length: {len(compacted_log)} characters")
    print("\n--- Pruned Log Content Preview ---")
    print(compacted_log)
    print("----------------------------------\n")

    # Step 3: Membangun struktur pesan percakapan
    system_prompts = [
        {"type": "text", "text": "Anda adalah Reliability Agent yang bertugas memulihkan crash database."}
    ]
    messages = [
        {"role": "user", "content": "Analisis error suite auth berikut ini."},
        {"role": "assistant", "content": [{"type": "tool_use", "id": "t1", "name": "run_integration_tests", "input": {}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": compacted_log}]},
        {"role": "assistant", "content": "Database timeout pada node-04 di auth.py:92."},
        {"role": "user", "content": "Berikan rekomendasi perbaikan konfigurasi timeout."}
    ]

    # Step 4: Pasang Cache Breakpoints
    sys_final, msgs_final = CacheBreakpointManager.apply_cache_breakpoints(system_prompts, messages)
    
    # Validasi Breakpoint Presence
    assert "cache_control" in sys_final[-1], "System prompt gagal di-assign breakpoint!"
    print("[3] Cache Breakpoints Berhasil Dikonfigurasi Secara Valid.")

    # Step 5: Simulasi kalkulasi akuntansi biaya 2 turn
    # Turn 1: Cache Creation
    guard.record_usage({
        "input_tokens": 300,
        "output_tokens": 80,
        "cache_creation_input_tokens": 1200,
        "cache_read_input_tokens": 0
    })
    print(f"[4] Turn 1 Cost (Cache Creation): ${guard.current_ledger.total_cost_usd:.5f}")

    # Turn 2: Cache Hit
    guard.record_usage({
        "input_tokens": 120,
        "output_tokens": 95,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 1200
    })
    print(f"[5] Turn 2 Cost (Cache Read Hit):   ${guard.current_ledger.total_cost_usd:.5f}")
    
    # Evaluasi status budget
    print(f"[6] Budget Safety Check Passed: ${guard.current_ledger.total_cost_usd:.5f} < ${guard.max_budget_usd:.2f}")

if __name__ == "__main__":
    run_lab()
```

#### Langkah Eksekusi & Pengujian
1. Pastikan runtime Python 3.11+ aktif.
2. Simpan implementasi modul Section 6 sebagai `production_context_manager.py`.
3. Jalankan lab:
   ```bash
   python lab_token_budget.py
   ```
4. **Verifikasi Output**:
   * Log karakter menyusut secara signifikan dari $> 80.000$ karakter menjadi $< 2.000$ karakter.
   * `[CRITICAL_FAILURE]` dan baris `Traceback` tetap ada di dalam payload yang dipertahankan.
   * Cache breakpoint aktif pada blok system prompt dan riwayat turn.
   * Akumulasi total biaya di bawah limit anggaran batas $\$0.05$.