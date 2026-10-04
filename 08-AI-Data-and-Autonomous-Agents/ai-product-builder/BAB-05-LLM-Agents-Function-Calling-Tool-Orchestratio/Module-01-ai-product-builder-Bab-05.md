# Bab 05: LLM Agents, Function Calling & Tool Orchestration
## Modul 01: Arsitektur Fondasi Tool Orchestration, Function Calling, dan ReAct Loops

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis** siklus hidup eksekusi *agentic reasoning* berbasis paradigma ReAct (*Reasoning + Acting*) dan native tool calling protocol.
- **Merancang** skema kontrak fungsi (*JSON Schema definition*) yang deterministik, *type-safe*, dan resilient terhadap ambiguitas semantik model.
- **Mengimplementasikan** *runtime execution engine* berbasis Python untuk memvalidasi, mengeksekusi, dan menangani mutasi state hasil eksekusi tool eksternal secara asinkron.
- **Membangun** mekanisme *self-healing error recovery* ketika LLM menghasilkan argumen yang tidak valid (*schema drift/validation failure*).
- **Mengevaluasi** metrik operasional (*latency overhead*, *token consumption*, *loop convergence rate*) untuk menentukan batasan produksi (*circuit breakers*).

---

### 2. Concept Overview

Secara fundamental, Large Language Model (LLM) adalah *stochastic next-token predictor* yang beroperasi di dalam ruang representasi tertutup. Model tidak memiliki akses langsung terhadap state komputasi eksternal, basis data real-time, maupun kemampuan mutasi sistem. **Tool Orchestration** dan **Function Calling** menjembatani keterbatasan ini dengan mengubah LLM dari sekadar mesin inferensi teks pasif menjadi *decision-making unit* di dalam sistem terdistribusi.

```
       STOCHASTIC WORLD                    DETERMINISTIC WORLD
+-----------------------------+         +------------------------+
|                             |         |                        |
|  LLM Context & In-Context   |         | External APIs, DBs,    |
|  Reasoning Space (Tokens)   |         | Calculators, Runtime   |
|                             |         |                        |
+--------------+--------------+         +-----------+------------+
               |                                    ^
               | 1. Generates Structured Intent     | 3. Executes Native Code
               v                                    |
+--------------+--------------+                     |
|  Agent Runtime Orchestrator |---------------------+
|  (Parsing, Validation, HITL)|
+--------------+--------------+
               ^                                    |
               | 4. Injects Structured Observation  |
               +------------------------------------+
                 2. Validates Arguments (Pydantic)
```

Mental model eksekusi *agentic* bertumpu pada **Siklus ReAct (Reasoning + Acting)**:
1. **Thought (Reasoning):** LLM mengevaluasi tujuan (*goal*), riwayat percakapan (*conversation state*), dan toolset yang tersedia untuk menyusun strategi penyelesaian masalah.
2. **Action (Acting):** Model memancarkan *structured payload* (umumnya JSON) yang berisi nama tool target dan argumen yang bersesuaian.
3. **Observation (Feedback):** Agent runtime mencegat payload tersebut, memvalidasi integritas skema argumen, mengeksekusi fungsi lokal/remote, dan menyuntikkan output eksekusi kembali ke dalam konteks LLM sebagai *role-specific message* (`tool` role).
4. **Convergence:** Siklus diulang hingga model memutuskan bahwa informasi yang diperoleh cukup untuk memproduksi jawaban akhir (*final answer*) atau mencapai batas limitasi (*max iterations*).

---

### 3. Why It Matters

Dalam implementasi *enterprise AI systems*, ketergantungan pada model *zero-shot* tanpa integrasi data eksternal menimbulkan tiga risiko sistemik utama:
1. **Hallucination on Proprietary/Dynamic Facts:** LLM menginterpolasi data numerik finansial, ketersediaan inventaris, atau status pesanan jika dipaksa menjawab tanpa verifikasi basis data.
2. **Inability to Execute Business Logic:** Kalkulasi pajak, verifikasi kepatuhan KYC, atau transaksi perbankan membutuhkan akurasi aritmatika 100% deterministik yang tidak dapat dijamin oleh probabilitas token.
3. **Context Length Inefficiency:** Memasukkan seluruh skema database atau ratusan API endpoints ke dalam system prompt memicu *attention degradation* (*needle-in-a-haystack dropoff*) dan membengkakkan biaya komputasi secara eksponensial.

Dengan *Function Calling*, integrasi sistem dilakukan via deklarasi antarmuka formal: LLM hanya menerima metadata definisi fungsi (*signature*, *docstring*, *parameter types*). Eksekusi bisnis tetap berjalan di lingkungan runtime terproteksi (*sandboxed environment*), memenuhi standar *security perimeter* enterprise.

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut memetakan arsitektur runtime dari Agent Orchestrator end-to-end:

```
[ User Request ]
       |
       v
+-----------------------------------------------------------------------+
|                       AGENT RUNTIME ORCHESTRATOR                      |
|                                                                       |
|  +------------------------+             +--------------------------+  |
|  | Context & State Store  | <---------> | Tool Registry            |  |
|  | (Message History)      |             | (Pydantic Schemas)       |  |
|  +------------------------+             +--------------------------+  |
|              |                                       |                |
|              | (Context + Tool Signatures)           |                |
|              v                                       v                |
|  +-----------------------------------------------------------------+  |
|  | Inference Gateway (Client API to LLM Provider)                  |  |
|  +-----------------------------------------------------------------+  |
+-----------------------------------|-----------------------------------+
                                    |
                                    v
                         +--------------------+
                         | LLM Provider Engine|
                         +--------------------+
                                    |
                 +------------------+------------------+
                 | (Evaluates Intent)                  |
                 v                                     v
       [ Tool Call Emitted ]                 [ Final Text Emitted ]
                 |                                     |
                 v                                     v
+-----------------------------------+             [ Output to User ]
| Agent Execution Engine            |
|                                   |
| 1. Argument Deserialization       |
| 2. Pydantic Runtime Validation    |
| 3. Security Policy Enforcement    |
|    - Rate Limits                  |
|    - Circuit Breaker Checks       |
+-----------------+-----------------+
                  |
        +---------+---------+
        |                   |
        v (Valid)           v (Invalid: Validation Error)
+---------------+   +------------------------------------+
| Dispatcher to |   | Synthesize Synthetic System Error  |
| Native Tool   |   | Message to Force Self-Correction   |
+-------+-------+   +-----------------+------------------+
        |                             |
        v                             |
+---------------+                     |
| External API/ |                     |
| Database Call |                     |
+-------+-------+                     |
        |                             |
        v (Raw Output)                |
+---------------+                     |
| Output Parser |                     |
+-------+-------+                     |
        |                             |
        +------------> ( ) <----------+
                        |
                        v
        [ Observation Injected to History ]
                        |
                        v
        (Re-enter Loop: Inference Gateway)
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. JSON Schema Injection & Format Compliance
LLM modern (e.g., GPT-4o, Claude 3.5 Sonnet) dilatih secara khusus (*instruction fine-tuning* + RLHF) untuk mengenali blok skema JSON. Saat `tools` didefinisikan, runtime mengonversi class/fungsi menjadi JSON Schema standar:

```json
{
  "type": "function",
  "function": {
    "name": "fetch_account_balance",
    "description": "Mengambil saldo terkini akun pengguna berdasarkan user_id dan currency code.",
    "parameters": {
      "type": "object",
      "properties": {
        "user_id": { "type": "string", "description": "UUID entitas nasabah" },
        "currency": { "type": "string", "enum": ["IDR", "USD", "EUR"], "default": "IDR" }
      },
      "required": ["user_id"]
    }
  }
}
```

Model tidak menjalankan kode ini. Model hanya memprediksi token yang mematuhi struktur sintaksis JSON tersebut ketika mendeteksi bahwa informasi akun dibutuhkan.

#### B. Tool Call Parsing & Execution Cycle
Saat LLM memutuskan memanggil tool, ia menghasilkan respons dengan `finish_reason: "tool_calls"`. Payload memuat atribut:
- `id`: Unique identifier untuk setiap panggilan tool (e.g., `call_ab12cd34`). ID ini wajib disertakan saat mengirimkan hasil (*observation*) kembali ke LLM agar model dapat memetakan hasil ke pemanggilan yang tepat (terutama saat *parallel tool calling*).
- `name`: Nama fungsi target.
- `arguments`: String JSON yang memuat pasangan key-value argumen fungsi.

#### C. Token Budget and Re-hydration
Setiap siklus eksekusi tool menyuntikkan token tambahan ke dalam *context window*:
$$\text{Tokens}_{\text{total}} = \text{Tokens}_{\text{system}} + \text{Tokens}_{\text{history}} + \sum_{i=1}^{N} (\text{Tokens}_{\text{call\_args}, i} + \text{Tokens}_{\text{observation}, i})$$

Jika payload output API berukuran masif (misal: JSON mentah sebesar 50KB dari response database), ini dapat menguras konteks dan menyebabkan *context overflow* atau *prompt dilution*. Oleh karena itu, runtime orchestrator wajib menerapkan data pruning/summarization sebelum data dikembalikan ke agent loop.

---

### 6. Production-Ready Code Implementation

Implementasi berikut menggunakan Python modern (3.11+) dengan `pydantic` v2, library `openai`, *type hints* ketat, penanganan error deterministik, serta pola arsitektur *Registry*.

```python
import asyncio
import json
import logging
from typing import Any, Callable, Coroutine, Dict, List, Optional
from pydantic import BaseModel, Field, ValidationError
from openai import AsyncOpenAI
from openai.types.chat import (
    ChatCompletionMessage,
    ChatCompletionToolParam,
    ChatCompletionMessageParam,
    ChatCompletionToolMessageParam,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("AgentOrchestrator")

# ============================================================================
# 1. TOOL SCHEMAS & REGISTRY
# ============================================================================

class GetCustomerMetricsInput(BaseModel):
    customer_id: str = Field(..., description="ID unik pelanggan berformat CUST-XXXXX")
    time_window_days: int = Field(default=30, ge=1, le=365, description="Jendela hari analisa (1-365 hari)")

class BlockFraudRiskCardInput(BaseModel):
    card_id: str = Field(..., description="Nomor tokenisasi kartu pembayaran")
    reason: str = Field(..., min_length=10, description="Justifikasi pemblokiran untuk audit log")

class ToolRegistry:
    """Manajemen pendaftaran tool dan resolusi JSON Schema."""
    def __init__(self) -> None:
        self._tools: Dict[str, Callable[..., Coroutine[Any, Any, str]]] = {}
        self._schemas: List[ChatCompletionToolParam] = []

    def register_tool(
        self,
        name: str,
        description: str,
        args_schema: type[BaseModel],
        func: Callable[..., Coroutine[Any, Any, str]]
    ) -> None:
        self._tools[name] = func
        
        # Konversi Pydantic model ke valid JSON Schema OpenAI Spec
        schema_def: ChatCompletionToolParam = {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": args_schema.model_json_schema(),
            }
        }
        self._schemas.append(schema_def)
        logger.info(f"Registered tool: {name}")

    def get_schemas(self) -> List[ChatCompletionToolParam]:
        return self._schemas

    async def execute_tool(self, name: str, raw_args: str) -> str:
        """Mengeksekusi tool dengan validasi skema dan penanganan error terisolasi."""
        if name not in self._tools:
            return json.dumps({
                "status": "error",
                "code": "TOOL_NOT_FOUND",
                "message": f"Tool '{name}' tidak terdaftar pada sistem runtime."
            })

        func = self._tools[name]
        try:
            parsed_args = json.loads(raw_args)
        except json.JSONDecodeError as err:
            logger.error(f"JSON decode failed for tool {name}: {str(err)}")
            return json.dumps({
                "status": "error",
                "code": "INVALID_JSON_ARGUMENT",
                "message": f"Argumen harus berupa JSON yang valid. Detail: {str(err)}"
            })

        try:
            # Pengecekan tipe dan eksekusi
            result = await func(**parsed_args)
            return json.dumps({"status": "success", "data": result})
        except ValidationError as val_err:
            logger.warning(f"Validation failure executing {name}: {val_err.json()}")
            return json.dumps({
                "status": "error",
                "code": "SCHEMA_VALIDATION_ERROR",
                "details": val_err.errors()
            })
        except Exception as exc:
            logger.exception(f"Unhandled operational failure in tool {name}: {str(exc)}")
            return json.dumps({
                "status": "error",
                "code": "TOOL_INTERNAL_FAILURE",
                "message": f"Terjadi kesalahan saat memproses fungsi: {str(exc)}"
            })


# ============================================================================
# 2. CONCRETE TOOL IMPLEMENTATIONS (MOCK DOMAIN LOGIC)
# ============================================================================

async def fetch_customer_metrics(customer_id: str, time_window_days: int = 30) -> Dict[str, Any]:
    # Simulasi latency I/O database enterprise
    await asyncio.sleep(0.1)
    if not customer_id.startswith("CUST-"):
        raise ValueError("customer_id tidak valid, format wajib diawali 'CUST-'")
    
    return {
        "customer_id": customer_id,
        "days_evaluated": time_window_days,
        "total_transactions_count": 142,
        "risk_score": 0.87,  # Skor risiko tinggi
        "flags": ["RAPID_HIGH_VALUE_VELOCITY", "FOREIGN_IP_ACCESS"],
        "active_cards": ["CARD-TOK-9921", "CARD-TOK-1102"]
    }

async def block_payment_card(card_id: str, reason: str) -> Dict[str, Any]:
    await asyncio.sleep(0.1)
    return {
        "card_id": card_id,
        "status": "SUSPENDED",
        "action_timestamp": "2026-03-31T08:30:00Z",
        "audit_note": reason
    }


# ============================================================================
# 3. ROBUST AGENT REASONING ENGINE (ReAct Loop)
# ============================================================================

class AgentExecutionEngine:
    def __init__(
        self,
        client: AsyncOpenAI,
        registry: ToolRegistry,
        model_name: str = "gpt-4o",
        max_iterations: int = 5
    ) -> None:
        self.client = client
        self.registry = registry
        self.model_name = model_name
        self.max_iterations = max_iterations

    async def run(self, user_objective: str) -> str:
        messages: List[ChatCompletionMessageParam] = [
            {
                "role": "system",
                "content": (
                    "Anda adalah Fraud Investigation Operations Agent. "
                    "Analisis metrik akun dengan teliti. Jika skor risiko > 0.80, "
                    "lakukan mitigasi pemblokiran kartu yang terindikasi berisiko. "
                    "Gunakan data faktual yang didapat dari tools. Selalu berikan argumen tepat."
                )
            },
            {"role": "user", "content": user_objective}
        ]

        iteration = 0
        while iteration < self.max_iterations:
            iteration += 1
            logger.info(f"Loop iteration {iteration}/{self.max_iterations} starting...")

            # 1. Inference step
            try:
                response = await self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    tools=self.registry.get_schemas(),
                    tool_choice="auto",
                    temperature=0.0  # Menjamin konsistensi deterministik pada Tool Calling
                )
            except Exception as e:
                logger.error(f"Inference Gateway Error: {str(e)}")
                raise SystemError(f"LLM Provider failure: {str(e)}") from e

            response_message = response.choices[0].message
            messages.append(response_message.model_dump(exclude_unset=True)) # Simpan response model ke history

            # 2. Check if agent converged on a final answer
            if not response_message.tool_calls:
                logger.info("Agent converged on final answer. Terminating loop.")
                return response_message.content or "No response produced."

            # 3. Execute tools concurrently if model produced parallel tool calls
            tool_tasks = []
            for tool_call in response_message.tool_calls:
                call_id = tool_call.id
                func_name = tool_call.function.name
                func_args = tool_call.function.arguments
                logger.info(f"Dispatching Tool Execution: {func_name} | Call ID: {call_id}")
                
                tool_tasks.append(
                    self._execute_and_format(call_id, func_name, func_args)
                )

            tool_outputs: List[ChatCompletionToolMessageParam] = await asyncio.gather(*tool_tasks)
            messages.extend(tool_outputs)

        logger.warning("Agent aborted: Maximum iteration count reached without convergence.")
        return "Circuit Breaker Activated: Agen tidak berhasil menyelesaikan tugas dalam batasan batas iterasi."

    async def _execute_and_format(
        self, call_id: str, name: str, args: str
    ) -> ChatCompletionToolMessageParam:
        result_payload = await self.registry.execute_tool(name, args)
        return {
            "role": "tool",
            "tool_call_id": call_id,
            "content": result_payload
        }


# ============================================================================
# 4. INITIALIZATION & ENTRYPOINT
# ============================================================================

async def main() -> None:
    # Inisialisasi Mock Client / Provider Client
    # Memerlukan OPENAI_API_KEY pada environment
    client = AsyncOpenAI()
    registry = ToolRegistry()

    # Pendaftaran fungsi ke registry
    registry.register_tool(
        name="get_customer_metrics",
        description="Ambil metrik risiko finansial dan status kartu aktif nasabah.",
        args_schema=GetCustomerMetricsInput,
        func=fetch_customer_metrics
    )
    registry.register_tool(
        name="block_fraud_risk_card",
        description="Blokir instan kartu nasabah yang terindikasi fraud tinggi.",
        args_schema=BlockFraudRiskCardInput,
        func=block_payment_card
    )

    agent = AgentExecutionEngine(client=client, registry=registry, max_iterations=4)
    query = "Investigasi akun nasabah CUST-88190. Ambil metriknya, dan jika tergolong fraud berisiko tinggi, segera blokir kartu pertamanya!"
    
    print("\n[STARTING AGENT RUNTIME EXECUTION]\n")
    try:
        final_verdict = await agent.run(query)
        print("\n[FINAL AGENT OUTPUT]:")
        print(final_verdict)
    except Exception as err:
        print(f"Agent Runtime Terminated Abnormally: {err}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

### 7. Edge Cases & Failure Modes

| Edge Case / Failure Mode | Indikator Kegagalan | Akar Masalah (Root Cause) | Strategi Mitigasi / Recovery |
| :--- | :--- | :--- | :--- |
| **Schema Hallucination** | `ValidationError` saat parsing payload Pydantic. | LLM mengasumsikan parameter yang tidak ada pada skema fungsi yang didaftarkan. | Tangkap error, kembalikan pesan schema error terstruktur ke *tool role*, biarkan LLM membaca field yang valid dan melakukan *self-correction*. |
| **Cyclic Invocation Loop** | Iterasi agent mencapai `max_iterations` dengan memanggil tool yang sama berulang-ulang. | Output tool tidak memberikan informasi konklusif, atau prompt tidak memiliki kriteria terminasi yang jelas. | Pasang detektor duplikasi state (*history hashing*). Jika tool yang sama dipanggil dengan argumen identik dua kali berturut-turut tanpa progres, terminasi paksa. |
| **Tool Execution Timeout** | Latency eksekusi melonjak di atas batas SLA (> 10s). | API eksternal mengalami bottleneck / cascading failure. | Bungkus `execute_tool` dengan `asyncio.wait_for(timeout=X)`. Kembalikan pesan kegagalan timeout ke LLM untuk memilih fallback tool. |
| **Observation Context Explosion** | Penurunan performa drastis / `BadRequestError: context_length_exceeded`. | Output tool mengembalikan serialisasi JSON masif (e.g., dump array 10.000 row). | Terapkan middleware transformasi: potong array panjang, buang field non-esensial, atau paksa output melewati *compression/summarizer layer*. |
| **Silent Type Coercion** | Parameter numerik berubah menjadi string (e.g., `"10"` vs `10`). | Serializer/deserializer JSON tidak menerapkan strict parsing. | Gunakan konfigurasi `model_config = ConfigDict(strict=True)` pada Pydantic V2 untuk memvalidasi tipe tanpa *type coercion* yang ambigu. |

---

### 8. Trade-offs & Alternatif Solusi

#### Model Native Function Calling vs In-Prompt Text ReAct
```
+--------------------------------------------------------------------------------+
|                             PARADIGM COMPARISON                                |
+------------------------------------+-------------------------------------------+
| Native Function Calling (JSON Spec)| In-Prompt ReAct (Prompt Pattern Engineering) |
+------------------------------------+-------------------------------------------+
| PROS:                              | PROS:                                     |
| - Determinisme sintaksis tinggi.   | - Bersifat provider-agnostik.             |
| - Token overhead parsing rendah.   | - Dapat diimplementasikan pada local LLM  |
| - Fine-tuned natively pada model.  |   sederhana tanpa dukungan format JSON.   |
|                                    |                                           |
| CONS:                              | CONS:                                     |
| - Terikat pada skema vendor API.   | - Parsing rapuh (regex failure).          |
| - Kadang sulit mengamati hidden    | - Rentan halusinasi pemisah token         |
|   reasoning token model.           |   (e.g., gagal format "Action: [...]").   |
+------------------------------------+-------------------------------------------+
```

#### Parallel Tool Execution vs Sequential Tool Calling
- **Parallel Execution:** Sangat efisien untuk fetching data independen (misal: mengambil data cuaca, profil nasabah, dan riwayat transaksi secara bersamaan). Memangkas total latensi hingga $O(1)$ relatif terhadap $N$ fungsi.
- **Sequential Execution:** Wajib digunakan ketika pemanggilan fungsi kedua bergantung secara fungsional pada data yang dihasilkan oleh fungsi pertama (e.g., fetch ID transaksi -> blokir ID tersebut).

---

### 9. Best Practices & Standard Industri

1. **Idempotency Execution Strategy:**
   Setiap fungsi mutasi (*write/update/delete*) harus menerima atau menghasilkan `idempotency_key`. Jika LLM mengalami kegagalan parsing jaringan dan mengulang pemanggilan fungsi blokir/pembayaran, server downstream tidak mengeksekusi aksi duplikat.

2. **Least Privilege System Prompts:**
   Tool yang memiliki dampak destruktif (misal: `delete_database_row`, `transfer_funds`) tidak boleh diotomasi secara instan tanpa validasi *human-in-the-loop* (HITL). Runtime wajib menahan loop dan meminta approval token.

3. **Strict Temperature Clamping:**
   Tetapkan `temperature = 0.0` untuk pemanggilan function calling. Fluktuasi sampling probabilitas dapat menyebabkan model menyimpang dari JSON Schema formal.

4. **Structured Semantic Tracing:**
   Gunakan standar OpenInference atau OpenTelemetry spans untuk mencatat setiap iterasi:
   - Span 1: LLM Inference (Token cost, Model latency)
   - Span 2: Tool Validation & Execution (Execution latency, Exception states)
   - Span 3: Feedback Cycle Context

---

### 10. Hands-on Lab Exercise

#### Skenario: Financial Operations Reconciliation Agent
Anda diminta membangun sistem reconciler yang bertugas mendeteksi inkonsistensi saldo antara ledger internal bank dengan settlement gateway payment partner.

#### Petunjuk Langkah-Demi-Langkah:
1. **Langkah 1: Deklarasi Schema Tools:**
   Buat dua skema Pydantic:
   - `FetchInternalLedgerSchema` (menerima `account_id: str`).
   - `FetchGatewaySettlementSchema` (menerima `account_id: str`).
   - `ReconcileDiscrepancySchema` (menerima `account_id: str`, `discrepancy_amount: float`, `status: Literal["SURPLUS", "DEFICIT"]`).

2. **Langkah 2: Setup Mock Fault Injection:**
   Implementasikan fungsi `fetch_internal_ledger` agar mengembalikan saldo 100.000.000, sedangkan `fetch_gateway_settlement` mengembalikan saldo 98.500.000 (terjadi selisih defisit 1.500.000).

3. **Langkah 3: Jalankan Agent Loop:**
   Eksekusi `AgentExecutionEngine` dengan target user:
   `"Cek kesesuaian saldo akun ACC-9901 antara internal ledger dan settlement gateway. Jika ada selisih, laporkan rekonsiliasinya secara tepat."`

4. **Langkah 4: Validasi Determinisme:**
   Pastikan agen:
   - Memanggil kedua fungsi pembacaan data (secara paralel atau sekuensial).
   - Menghitung diskrepansi secara deterministik (1.500.000 DEFICIT).
   - Memanggil `reconcile_discrepancy` dengan argumen yang benar tanpa manipulasi data buatan.

#### Expected Output Trace Log:
```text
[INFO] AgentOrchestrator: Loop iteration 1 starting...
[INFO] AgentOrchestrator: Dispatching Tool Execution: fetch_internal_ledger | Call ID: call_01
[INFO] AgentOrchestrator: Dispatching Tool Execution: fetch_gateway_settlement | Call ID: call_02
[INFO] AgentOrchestrator: Loop iteration 2 starting...
[INFO] AgentOrchestrator: Dispatching Tool Execution: reconcile_discrepancy | Call ID: call_03
[INFO] AgentOrchestrator: Loop iteration 3 starting...
[INFO] AgentOrchestrator: Agent converged on final answer. Terminating loop.

[FINAL AGENT OUTPUT]:
Rekonsiliasi untuk akun ACC-9901 berhasil dijalankan. Ditemukan defisit sebesar Rp 1.500.000 antara internal ledger (Rp 100.000.000) dan settlement gateway (Rp 98.500.000). Tindakan pencatatan diskrepansi telah dikirimkan ke sistem audit.
```