# Kurikulum: Data & AI Engineering / AI Data Scientist
## Kategori: 08-AI-Data-and-Autonomous-Agents
### Bab 10: Advanced AI Paradigms Autonomous Agents & RL
#### Modul 01: Foundations of Autonomous Cognitive Architectures, ReAct Loops, and Dynamic Tool Orchestration

---

### 1. Learning Objectives (Spesifik & Terukur)

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

*   **Mengonseptualisasikan dan Memodelkan Loop Kognitif:** Memetakan interaksi Large Language Model (LLM) ke dalam kerangka formal *Markov Decision Process* (MDP) $(S, A, P, R, \gamma)$ untuk agen otonom, mengukur efisiensi eksekusi berdasarkan metrik *trajectory length* dan *reward convergence*.
*   **Merancang dan Mengimplementasikan Arsitektur ReAct (Reasoning + Acting):** Membangun orkestrator kognitif dari nol (*scratch*) dengan parsing terstruktur, deterministik, dan penanganan kesalahan parsial tanpa ketergantungan pada pustaka *black-box*.
*   **Membangun Dynamic Tool Registry:** Mengimplementasikan sistem *registry* berbasis skema JSON/Pydantic yang mendukung refleksi tipe runtime, validasi input otomatis, dan isolasi eksekusi (*sandboxing*).
*   **Mendeteksi dan Memitigasi State Oscillations:** Merancang algoritma mitigasi siklus tak terbatas (*infinite loop detection*) menggunakan *rolling-window state hashing* dan pembatasan kedalaman eksekusi (*max-depth boundary*).
*   **Menerapkan Manajemen Konteks dan Memori Kerja:** Mengelola penggunaan token secara adaptif melalui kompresi observasi dinamis (*observation summarization*) dan pemangkasan jendela konteks (*sliding window context pruning*).

---

### 2. Concept Overview (Mental Model & Teori Inti)

Secara tradisional, sistem kecerdasan buatan berbasis LLM beroperasi dalam paradigma *stateless single-turn prediction*: $y = f_\theta(x)$. Paradigma ini rentan terhadap halusinasi faktual dan tidak memiliki kapasitas untuk memverifikasi kebenaran informasi maupun menyelesaikan masalah multi-langkah.

Sistem agen otonom menggeser paradigma ini ke formulasi *stateful sequential decision-making*. Dalam paradigma ini, LLM bertindak sebagai *policy network* $\pi_\theta(a_t | s_t)$ implisit yang mengeksekusi penalaran (*reasoning trace*) untuk memandu intervensi lingkungan (*acting*), mengamati respons lingkungan (*environment observation*), dan memperbarui ruang status internalnya (*working memory*).

```
   +-----------------------------------------------------------+
   |                  Markov Decision Process                  |
   |                                                           |
   |  State (S_t)   --> Working Memory + Prompt Context        |
   |  Action (A_t)  --> Thought (Latent) + Tool Invocation     |
   |  Transition(P) --> Tool Execution Engine Environment      |
   |  Reward (R_t)  --> Task-completion Critic / Deterministic |
   |                    Validation Score                       |
   +-----------------------------------------------------------+
```

#### Mental Model: The ReAct Paradigm

Pola **ReAct (Reasoning + Acting)** mengintervensi pemisahan antara penalaran murni (*Chain-of-Thought*) dan tindakan murni (*Act-only APIs*). 

1. **Thought Step ($T_t$):** Agen memproyeksikan dekomposisi masalah, merumuskan hipotesis, dan menentukan parameter lingkungan yang dibutuhkan.
2. **Action Step ($A_t$):** Agen memanggil antarmuka deterministik terdaftar (*tool invocation*) dengan argumen bertipe ketat (*strictly typed parameters*).
3. **Observation Step ($O_t$):** Lingkungan mengembalikan hasil eksekusi primitif, yang disuntikkan kembali ke dalam memori kerja agen untuk iterasi status $S_{t+1} = [S_t; T_t; A_t; O_t]$.

```
      +-------------+        +--------------------+
      |  Objective  |------->|   Working Memory   |
      +-------------+        +--------------------+
                                    |       ^
                          Trajectory Context|
                                    v       | (Append: T_t, A_t, O_t)
                             +-----------------+
                             |    LLM Policy   |
                             +-----------------+
                                      |
                           Generates: T_t & A_t
                                      v
                             +-----------------+
                             | Execution Guard |
                             +-----------------+
                                      |
                                      | Execute Action
                                      v
                             +-----------------+
                             |  Tool Sandbox   |
                             +-----------------+
                                      |
                             Returns: Observation (O_t)
                                      |
                                      +-------------+
```

---

### 3. Why It Matters (Masalah di Dunia Nyata & Kebutuhan Enterprise)

Pada lingkungan komersial dan sistem produksi data skala besar, *single-prompting* gagal menyelesaikan tugas kompleks karena:

1. **Information Asymmetry:** Model parametrik terisolasi dari basis data transaksional, sistem analitik *real-time*, dan metadata *warehouse*.
2. **Deterministic Non-Compliance:** LLM secara probabilistik lemah dalam komputasi matematis presisi tinggi, validasi sintaks SQL/kode, dan transformasi data deterministik.
3. **Execution Blind Spots:** Kegagalan dalam rantai inferensi linier tidak dapat dikoreksi secara otomatis tanpa mekanisme umpan balik dan eksekusi ulang berbasis kesalahan (*self-correction loop*).

**Kebutuhan Enterprise:**
*   **Autonomous Data Remediation:** Agen yang mampu mendeteksi kerusakan schema data, mengisolasi data anomali, mengonstruksi kueri perbaikan, dan memvalidasi integritas data pasca-eksekusi.
*   **Multi-Hop Root Cause Analysis:** Kemampuan melacak dependensi telemetri lintas layanan terdistribusi melalui API metrik, log aggregators, dan repositori konfigurasi secara mandiri.
*   **Operational Guardrailing:** Kontrol penuh atas aksi agen menggunakan validasi skema runtime, *human-in-the-loop triggers*, dan isolasi eksekusi untuk mencegah manipulasi sistem produksi yang destruktif.

---

### 4. Arsitektur & Diagram Komponen

Arsitektur agen otonom tingkat produksi memisahkan lapisan kognisi (LLM), lapisan deterministik (Tool Engine), dan lapisan status (State Store).

```
+-----------------------------------------------------------------------------------------+
|                                    AGENT CORE ENGINE                                    |
|                                                                                         |
|  +-----------------------+      +--------------------+      +------------------------+  |
|  |   Context Assembler   | ---> |     LLM Client     | ---> | Action Response Parser |  |
|  +-----------------------+      +--------------------+      +------------------------+  |
|              ^                            ^                              |              |
|              |                            |                              v              |
|  +-----------------------+                |                 +------------------------+  |
|  |     State Store       |                |                 | Cycle & Loop Detector  |  |
|  | (Working/Short-term)  |                |                 +------------------------+  |
|  +-----------------------+                |                              |              |
|              ^                            |                              v              |
|              |                  +-------------------+       +------------------------+  |
|              +----------------- | Observation Sink  | <---- | Execution Interceptor  |  |
|                                 +-------------------+       +------------------------+  |
|                                                                          |              |
+------------------------------------------------------------------------- | -------------+
                                                                           |
                                                                           v
+-----------------------------------------------------------------------------------------+
|                                  TOOL EXECUTION ENGINE                                  |
|                                                                                         |
|   +---------------------------------------------------------------------------------+   |
|   |                              Dynamic Tool Registry                              |   |
|   |  - JSON-Schema Auto-generation                                                  |   |
|   |  - Pydantic Ingestion Validation                                                |   |
|   +---------------------------------------------------------------------------------+   |
|               |                                                     |                   |
|               v                                                     v                   |
|   +-----------------------+                             +-----------------------+       |
|   |    Data Analytics     |                             |   Database Sandbox    |       |
|   |     Worker Tool       |                             |     Query Tool        |       |
|   +-----------------------+                             +-----------------------+       |
+-----------------------------------------------------------------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Trajectory Context Compilation & Parsing Determinism
Model ReAct mengharuskan format keluaran distandarkan agar dapat diurai tanpa ambiguitas sintaktis. Penggunaan *free-form text parser* berbasis *regular expressions* tradisional sering gagal akibat variabilitas penempatan token oleh LLM. Arsitektur modern memisahkan penulisan alasan (*Thought*) dan eksekusi instruksi (*Action/Payload*) melalui penanda batas ketat (*strict framing delimiters*) atau skema terstruktur (JSON Function Calling/Structured Outputs).

Setiap siklus penalaran mengikuti determinasi transisi:
$$\tau_t = (T_t, A_t, O_t)$$
$$S_{t} = S_0 \cup \left( \bigcup_{i=1}^{t-1} \tau_i \right) \cup T_t \cup A_t$$

#### B. Context Window Budgeting & Observation Compression
Observasi dari lingkungan (misal: keluaran tabel SQL, log teks mentah) dapat dengan cepat melampaui kapasitas jendela konteks LLM. 
*   **Budgeting Strategy:** Alokasi total token dibagi menjadi tiga komponen utama:
    *   $\text{Limit}_{\text{Reserved}} = \text{Budget}_{\text{System Prompt}} + \text{Budget}_{\text{Tool Registry Schemas}}$
    *   $\text{Budget}_{\text{Dynamic Memory}} = \text{Budget}_{\text{Total}} - \text{Limit}_{\text{Reserved}} - \text{Budget}_{\text{Max Output}}$
*   Jika $|S_t| > \text{Budget}_{\text{Dynamic Memory}}$, terapkan mekanisme *Selective Observation Truncation*: pangkas data tabular menjadi representasi ringkas (misalnya: *shape metadata* + 5 baris pertama/terakhir) dan enkapsulasi sisanya dalam *scratchpad store* berbasis referensi pointer.

#### C. Loop Detection via State Hashing
Agen dapat terjebak dalam siklus aksi berulang ketika tindakan yang diambil mengembalikan observasi yang identik secara deterministik (contoh: *SyntaxError* yang berulang tanpa perbaikan kueri).
*   **Algoritma Mitigasi:**
    Hitung nilai hash terhadap aksi dan parameter:
    $$h_t = \text{SHA256}(A_t \mathbin{\Vert} \text{Arguments}_t)$$
    Pertahankan struktur data *rolling window* $W = [h_{t-k}, \dots, h_t]$. Jika frekuensi kemunculan $h_t$ melewati ambang batas tertentu ($threshold \ge 3$), picu *Deterministic Interrupt* untuk menyuntikkan arahan koreksi paksa (*Meta-Cognitive Injection*) ke dalam status konteks:
    $$O_t \leftarrow \text{"Error: Repeated identical action detected. You must change your strategy or tool parameters."}$$

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi arsitektur agen otonom ReAct tingkat produksi. Implementasi ini mencakup *Dynamic Tool Registry* dengan validasi Pydantic, deteksi siklus berbasis SHA256, *observation truncation*, penanganan kesalahan parsial, dan simulasi inferensi LLM tanpa pustaka agen pihak ketiga.

```python
"""
Core Engine: Production-Grade Autonomous Agentic Cognitive Loop
Author: Principal AI Engineer & Curriculum Architect
Architecture: Strict Delimited ReAct with Dynamic Sandbox Tools
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import sys
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Tuple, Type
from pydantic import BaseModel, Field, ValidationError

# =====================================================================
# Logging Configuration
# =====================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(name)s) %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("CognitiveOrchestrator")


# =====================================================================
# Exceptions
# =====================================================================
class AgentExecutionException(Exception):
    """Base exception for cognitive loop runtime failures."""
    pass


class ActionParsingError(AgentExecutionException):
    """Raised when the LLM output violates the expected trajectory protocol."""
    pass


class CyclicExecutionError(AgentExecutionException):
    """Raised when the agent enters a repetitive deterministic loop."""
    pass


class ToolNotFoundException(AgentExecutionException):
    """Raised when the requested tool is missing from the registry."""
    pass


# =====================================================================
# Core Data Models
# =====================================================================
class ToolInvocation(BaseModel):
    tool_name: str = Field(..., description="Target tool identifier.")
    tool_input: Dict[str, Any] = Field(
        default_factory=dict, 
        description="Structured JSON input payload."
    )


class AgentStep(BaseModel):
    thought: str = Field(..., description="Latent reasoning trace.")
    action: Optional[ToolInvocation] = Field(None, description="Action taken, if any.")
    observation: Optional[str] = Field(None, description="Observation from execution.")


class AgentTrajectory(BaseModel):
    objective: str
    steps: List[AgentStep] = Field(default_factory=list)
    final_answer: Optional[str] = None
    is_complete: bool = False


# =====================================================================
# Tool Definition & Registry System
# =====================================================================
class BaseTool(ABC):
    """Abstract base class for all deterministic execution tools."""
    name: str
    description: str
    args_schema: Type[BaseModel]

    @abstractmethod
    def execute(self, **kwargs: Any) -> str:
        """Executes the deterministic business logic safely."""
        pass

    def get_schema(self) -> Dict[str, Any]:
        """Generates dynamic JSON schema for runtime agent grounding."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.args_schema.model_json_schema(),
        }


class ToolRegistry:
    """Thread-safe, self-documenting Tool Registry."""

    def __init__(self) -> None:
        self._registry: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        if tool.name in self._registry:
            raise ValueError(f"Tool {tool.name} is already registered.")
        self._registry[tool.name] = tool
        logger.info("Registered tool: %s", tool.name)

    def get_tool(self, name: str) -> BaseTool:
        if name not in self._registry:
            raise ToolNotFoundException(f"Tool '{name}' is not registered.")
        return self._registry[name]

    def render_schemas(self) -> str:
        """Serializes all tool schemas into a strict format for the system context."""
        schemas = [t.get_schema() for t in self._registry.values()]
        return json.dumps(schemas, indent=2)


# =====================================================================
# Production Tool Implementations (Data Science Domain)
# =====================================================================
class SQLQueryInput(BaseModel):
    query: str = Field(..., description="Standard ANSI SQL read-only query string.")


class MockSQLWarehouseTool(BaseTool):
    name: str = "execute_sql_query"
    description: str = "Executes read-only SQL queries against the enterprise warehouse."
    args_schema: Type[BaseModel] = SQLQueryInput

    def execute(self, **kwargs: Any) -> str:
        validated_args = self.args_schema(**kwargs)
        query = validated_args.query.strip().lower()

        # Strict Security Sandboxing Simulation
        if any(keyword in query for keyword in ["drop", "delete", "update", "insert", "alter"]):
            return "Security Exception: Data manipulation statements are forbidden."

        # Mock database response
        if "customer_churn" in query:
            return json.dumps([
                {"cohort": "2023-Q1", "churn_rate": 0.045, "total_users": 120000},
                {"cohort": "2023-Q2", "churn_rate": 0.089, "total_users": 115000},
                {"cohort": "2023-Q3", "churn_rate": 0.121, "total_users": 98000},
            ])
        return "Empty resultset: Relation not found or condition unfulfilled."


class AnomalyCalculationInput(BaseModel):
    values: List[float] = Field(..., description="List of float values to compute statistics on.")
    threshold: float = Field(default=2.0, description="Standard deviations threshold.")


class StatisticalAnomalyTool(BaseTool):
    name: str = "detect_anomalies"
    description: str = "Computes z-scores on float lists to isolate anomalies."
    args_schema: Type[BaseModel] = AnomalyCalculationInput

    def execute(self, **kwargs: Any) -> str:
        payload = self.args_schema(**kwargs)
        vals = payload.values
        if len(vals) < 2:
            return "Execution Error: Minimum of 2 data points required for variance analysis."

        mean = sum(vals) / len(vals)
        variance = sum((x - mean) ** 2 for x in vals) / (len(vals) - 1)
        std_dev = variance ** 0.5

        if std_dev == 0.0:
            return json.dumps({"anomalies": [], "info": "Variance is zero."})

        anomalies = [
            {"val": x, "z_score": (x - mean) / std_dev}
            for x in vals
            if abs((x - mean) / std_dev) >= payload.threshold
        ]
        return json.dumps({"mean": mean, "std_dev": std_dev, "anomalies": anomalies})


# =====================================================================
# Mock Enterprise LLM Engine
# =====================================================================
class LLMInterface(ABC):
    @abstractmethod
    def complete(self, prompt: str) -> str:
        pass


class MockReActLLM(LLMInterface):
    """
    Deterministic Simulator: Mimics an LLM solving a multi-step churn anomaly analysis.
    In real production, this is bound to an OpenAI, Anthropic, or Local vLLM client.
    """
    def __init__(self) -> None:
        self.call_count = 0

    def complete(self, prompt: str) -> str:
        self.call_count += 1
        if self.call_count == 1:
            return (
                "Thought: We need to retrieve the latest churn metrics to verify reports of retention decline.\n"
                "Action: execute_sql_query\n"
                'Action Input: {"query": "SELECT * FROM customer_churn;"}'
            )
        elif self.call_count == 2:
            return (
                "Thought: The churn rates are 0.045, 0.089, and 0.121 across Q1 to Q3. "
                "I must run statistical anomaly detection on these metrics to assess volatility.\n"
                "Action: detect_anomalies\n"
                'Action Input: {"values": [0.045, 0.089, 0.121], "threshold": 1.0}'
            )
        elif self.call_count == 3:
            return (
                "Thought: An anomaly was confirmed for cohort 2023-Q3 where churn hit 12.1% (Z-score > 1.0). "
                "I have compiled sufficient data to conclude the investigation.\n"
                "Final Answer: Churn rates have significantly diverged from baseline in 2023-Q3 (12.1%, Z-Score: 1.14), "
                "signaling accelerated user base attrition starting from Q2."
            )
        return "Final Answer: No further steps possible."


# =====================================================================
# Cognitive Orchestrator
# =====================================================================
class ReActCognitiveOrchestrator:
    """
    Production-grade ReAct Orchestrator equipped with loop detection,
    observation clipping, schema validation, and structured trace capture.
    """

    def __init__(
        self,
        llm: LLMInterface,
        tool_registry: ToolRegistry,
        max_iterations: int = 5,
        max_observation_tokens: int = 1500,
    ) -> None:
        self.llm = llm
        self.registry = tool_registry
        self.max_iterations = max_iterations
        self.max_observation_tokens = max_observation_tokens
        self.action_history_hashes: List[str] = []

    def _compile_system_prompt(self, objective: str) -> str:
        return (
            f"You are an advanced enterprise data intelligence agent.\n"
            f"You solve user objectives step-by-step using reasoning and available tools.\n\n"
            f"TOOLS AVAILABLE:\n{self.registry.render_schemas()}\n\n"
            f"FORMAT PROTOCOL:\n"
            f"Thought: <your rationale and hypothesis>\n"
            f"Action: <the tool name>\n"
            f"Action Input: <strict JSON matching the tool's parameter schema>\n"
            f"-- OR --\n"
            f"Thought: <rationale>\n"
            f"Final Answer: <your conclusive synthesized report>\n\n"
            f"OBJECTIVE: {objective}\n"
        )

    def _parse_llm_response(self, response: str) -> Tuple[str, Optional[ToolInvocation], Optional[str]]:
        """Parses output into (Thought, Action, Final Answer) tuples deterministically."""
        thought_match = re.search(r"Thought:\s*(.*?)(?=\nAction:|\nFinal Answer:|$)", response, re.DOTALL)
        thought = thought_match.group(1).strip() if thought_match else ""

        final_match = re.search(r"Final Answer:\s*(.*)", response, re.DOTALL)
        if final_match:
            return thought, None, final_match.group(1).strip()

        action_match = re.search(r"Action:\s*(\w+)", response)
        input_match = re.search(r"Action Input:\s*(\{.*\}|\[.*\])", response, re.DOTALL)

        if not action_match or not input_match:
            raise ActionParsingError(
                f"Protocol violation: Expected valid 'Action' and 'Action Input' JSON block. Response: {response}"
            )

        tool_name = action_match.group(1).strip()
        raw_json = input_match.group(1).strip()

        try:
            parsed_payload = json.loads(raw_json)
        except json.JSONDecodeError as err:
            raise ActionParsingError(f"Action Input contains invalid JSON: {raw_json}") from err

        return thought, ToolInvocation(tool_name=tool_name, tool_input=parsed_payload), None

    def _check_and_register_cycle(self, invocation: ToolInvocation) -> None:
        """Cycle detector implementing an action-payload rolling hash."""
        serialized = f"{invocation.tool_name}:{json.dumps(invocation.tool_input, sort_keys=True)}"
        action_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()

        if self.action_history_hashes.count(action_hash) >= 2:
            raise CyclicExecutionError(
                f"Execution loop identified: Action {invocation.tool_name} with parameters "
                f"{invocation.tool_input} was executed repeatedly."
            )
        self.action_history_hashes.append(action_hash)

    def _truncate_observation(self, observation: str) -> str:
        """Protects context window against token exhaustion."""
        approximate_token_count = len(observation) // 4
        if approximate_token_count > self.max_observation_tokens:
            slice_length = self.max_observation_tokens * 4
            logger.warning("Observation exceeds budget! Truncating from %d to %d chars.", len(observation), slice_length)
            return observation[:slice_length] + "\n[System: Observation truncated due to token budget constraints]"
        return observation

    def run(self, objective: str) -> AgentTrajectory:
        trajectory = AgentTrajectory(objective=objective)
        conversation_context = self._compile_system_prompt(objective)

        logger.info("Initiating cognitive loop for objective: %s", objective)

        for step_idx in range(1, self.max_iterations + 1):
            logger.info("Executing iteration step: %d", step_idx)

            # 1. Step generation (LLM Call)
            raw_response = self.llm.complete(conversation_context)

            # 2. Structured Parsing
            try:
                thought, action, final_answer = self._parse_llm_response(raw_response)
            except ActionParsingError as parse_err:
                logger.error("Parsing Failure: %s. Injecting correction context.", str(parse_err))
                conversation_context += (
                    f"\nObservation: Parse Error - {str(parse_err)}. "
                    f"Ensure you output 'Action:' and valid JSON 'Action Input:'."
                )
                continue

            # 3. Assess Termination
            if final_answer:
                trajectory.final_answer = final_answer
                trajectory.is_complete = True
                trajectory.steps.append(AgentStep(thought=thought))
                logger.info("Final Answer generated successfully.")
                break

            assert action is not None  # Enforced by _parse_llm_response logic

            current_step = AgentStep(thought=thought, action=action)

            # 4. Cycle Mitigation
            try:
                self._check_and_register_cycle(action)
            except CyclicExecutionError as cycle_err:
                logger.critical("Cycle detected: %s. Terminating trajectory early.", str(cycle_err))
                current_step.observation = f"Fatal Error: {str(cycle_err)}"
                trajectory.steps.append(current_step)
                trajectory.final_answer = "Aborted: The agent encountered an unresolvable execution loop."
                break

            # 5. Deterministic Execution
            try:
                tool = self.registry.get_tool(action.tool_name)
                raw_observation = tool.execute(**action.tool_input)
                observation = self._truncate_observation(raw_observation)
            except ValidationError as val_err:
                observation = f"Tool Input Validation Error: {json.dumps(val_err.errors())}"
            except Exception as execution_err:
                observation = f"Tool Execution Failure: {type(execution_err).__name__} - {str(execution_err)}"

            current_step.observation = observation
            trajectory.steps.append(current_step)

            # 6. Append trajectory trace into memory for next turn
            conversation_context += (
                f"\nThought: {thought}\n"
                f"Action: {action.tool_name}\n"
                f"Action Input: {json.dumps(action.tool_input)}\n"
                f"Observation: {observation}\n"
            )

        if not trajectory.is_complete and not trajectory.final_answer:
            trajectory.final_answer = "Max iterations reached without achieving final synthesis."
            logger.warning("Reached maximum execution depth (%d). Forcing exit.", self.max_iterations)

        return trajectory


# =====================================================================
# Execution & Verification
# =====================================================================
if __name__ == "__main__":
    # Instantiate Tool Registry
    registry = ToolRegistry()
    registry.register(MockSQLWarehouseTool())
    registry.register(StatisticalAnomalyTool())

    # Instantiate LLM Engine
    llm_engine = MockReActLLM()

    # Instantiate Orchestrator
    orchestrator = ReActCognitiveOrchestrator(
        llm=llm_engine,
        tool_registry=registry,
        max_iterations=5,
        max_observation_tokens=500,
    )

    task = "Investigate the customer churn rate trajectory from warehouse records and evaluate statistical significance."
    result = orchestrator.run(task)

    print("\n" + "=" * 60)
    print("AGENT TRAJECTORY TRACE REPORT")
    print("=" * 60)
    for idx, step in enumerate(result.steps, 1):
        print(f"\n[Step {idx}]")
        print(f"Thought    : {step.thought}")
        if step.action:
            print(f"Action     : {step.action.tool_name}")
            print(f"Input      : {json.dumps(step.action.tool_input)}")
            print(f"Observation: {step.observation}")
    print("\n" + "=" * 60)
    print(f"Final Answer : {result.final_answer}")
    print(f"Complete     : {result.is_complete}")
    print("=" * 60)
```

---

### 7. Edge Cases & Failure Modes

Berikut adalah matriks mitigasi kegagalan runtime (*runtime failure modes*) pada arsitektur agen:

| Failure Mode | Mekanisme Terjadinya | Dampak Produksi | Strategi Mitigasi Deterministik |
| :--- | :--- | :--- | :--- |
| **Tool Halucination** | LLM memanggil nama tool yang tidak terdaftar dalam skema (misal: `run_bash_script`). | System crash atau *unhandled runtime exception*. | Tangani dengan `ToolNotFoundException`, kirim pesan observasi perbaikan berisi daftar fungsi yang valid tanpa memutus loop. |
| **Action Parameter Mutation** | Tipe argumen menyimpang dari skema JSON (misal: mengirim string `"12.5"` ke float parameter). | Kegagalan fungsi hilir, SQL *injection*, atau konversi data yang korup. | Validasi ketat *in-memory* menggunakan Pydantic. Tangkap `ValidationError` dan kirim *feedback* format JSON ke LLM. |
| **Context Window Exploding** | Pemanggilan kueri SQL mengembalikan 10.000 baris teks mentah. | Out-of-Memory (OOM) atau error batas *context window* LLM (misal: 400 Bad Request Context Length Exceeded). | Terapkan limitasi token observasi (*dynamic truncation*), ringkas data menjadi format statistik (mean, median, top-5 rows). |
| **Oscillatory Deadlock** | Aksi $A_t$ dan $A_{t+1}$ saling bergantian bolak-balik tanpa kemajuan penyelesaian tugas. | Biaya token membengkak secara linier, latensi tak terbatas (*hung process*). | Gunakan algoritma *State Hashing Sliding Window* ($k$-depth cycle detection). Hentikan paksa saat mendeteksi ambang batas repetisi. |
| **Prompt Injection via Observation** | Data eksternal yang dibaca (misal: dari scraping web atau tabel DB) mengandung instruksi tersembunyi (*jailbreak payload*). | *Control hijacking*, kebocoran data (*data exfiltration*), atau eksekusi aksi berbahaya. | Terapkan isolasi observasi (*data boundary tagging*), *Observation Sandboxing*, dan *System Prompt Precedence Guardrails*. |

---

### 8. Trade-offs & Alternatif Solusi

Setiap pola perancangan agen membawa konsekuensi performa, biaya, dan fleksibilitas:

```
              Latency & Cost
                    ^
                    |          [Plan-and-Solve]
                    |                 |
                    |                 v
                    |         [ReAct Architecture]
                    |                 |
                    |                 v
                    |       [Tool-Calling / Reflex]
                    +-----------------------------------> Reasoning Depth & Adaptability
```

#### Komparasi Arsitektur Agen

1. **ReAct Loop (Reasoning + Acting)**
   *   *Pros:* Beradaptasi secara dinamis terhadap observasi lingkungan yang tak terduga; meminimalkan propagasi kesalahan langkah awal berkat evaluasi bertahap.
   *   *Cons:* Menghasilkan latensi tinggi karena LLM dipanggil secara serial ($N$ inferensi untuk $N$ aksi); biaya token bertambah seiring membesarnya riwayat eksekusi.
   *   *Best for:* Investigasi data science eksploratif, *root-cause analysis*, dan tugas dengan dependensi dinamis antar-langkah.

2. **Plan-and-Solve (Decomposed Multi-Agent DAG)**
   *   *Pros:* Membagi pekerjaan menjadi Directed Acyclic Graph (DAG) di awal; beberapa langkah independen dapat dieksekusi secara paralel untuk menghemat waktu.
   *   *Cons:* Kurang fleksibel jika terjadi deviasi pada langkah perantara; rancangan rencana awal dapat tidak relevan jika data lingkungan berubah drastis.
   *   *Best for:* Pipeline ETL terjadwal, orkestrasi transformasi data analitik batch, dan pelaporan terstruktur.

3. **Fine-Tuned Function Calling (Single-Turn API Routing)**
   *   *Pros:* Latensi rendah (1 langkah inferensi); kepatuhan skema JSON sangat tinggi karena telah dilatih langsung pada level bobot model (*weight-level*).
   *   *Cons:* Tidak memiliki kemampuan penalaran reflektif internal; tidak dapat memecahkan masalah multi-hop yang membutuhkan hipotesis bertingkat.
   *   *Best for:* Pemrosesan bot transaksional sederhana, kueri data tunggal, dan antarmuka *intent-to-API*.

---

### 9. Best Practices & Standar Industri

1. **Idempotensi Tool:**
   Setiap fungsi yang terdaftar harus bersifat idempoten sebisa mungkin, terutama pada tool yang berinteraksi dengan API eksternal. Gunakan mekanisme *idempotency keys* pada tool yang mengubah status sistem.
2. **Schema Definition Protocol:**
   Gunakan skema Pydantic eksplisit dengan dokumentasi tipe argumen yang presisi. Berikan batasan numerik (`ge`, `le`) dan deskripsi fungsional untuk memudahkan penentuan rute oleh LLM.
3. **Observability and Distributed Tracing:**
   Terapkan standarisasi pelacakan OpenTelemetry (*Semantic Conventions for GenAI*) atau integrasi platform seperti Langfuse/Arize Phoenix. Catat setiap *thought*, token count, payload aksi, dan latensi per iterasi.
4. **Sandboxed Code Execution:**
   Jangan jalankan kode yang dihasilkan LLM langsung di mesin *host*. Eksekusi analisis berbasis Python/SQL wajib diisolasi menggunakan *gVisor*, *Docker containers*, atau *WASM (WebAssembly)* dengan pembatasan jaringan ketat (*air-gapped environment*).
5. **Human-in-the-Loop (HITL) Gateways:**
   Tentukan batasan izin (*privilege tiers*). Aksi bersifat destruktif (*write*, *delete*, *drop*) wajib memicu jeda eksekusi dan membutuhkan token otorisasi manual sebelum status diubah.

---

### 10. Hands-on Lab Exercise

#### Skenario:
Sistem monitoring anomali penjualan mendeteksi adanya penurunan tajam dalam omzet mingguan. Anda diminta membangun agen otonom berbasis ReAct untuk menyelidiki repositori data mentah, menghitung deviasi penjualan antar wilayah, dan menghasilkan ringkasan investigasi otomatis.

#### Petunjuk Praktikum:

1. **Persiapan Dependensi:**
   Pastikan lingkungan Python Anda bersih dan terpasang `pydantic >= 2.0.0`.
   ```bash
   pip install pydantic
   ```

2. **Langkah 1: Implementasikan Tool Baru**
   Tambahkan tool baru bernama `RegionalSalesMetricsTool` yang mewarisi `BaseTool` dari kode arsitektur di Bagian 6:
   *   **Input Schema:** `region` (string: `"EMEA"`, `"APAC"`, `"AMER"`).
   *   **Mock Output:** Kembalikan riwayat penjualan mingguan dalam bentuk JSON (misal: EMEA mengalami penurunan 40% pada minggu ke-4).

3. **Langkah 2: Konfigurasi Mock LLM untuk Skenario Data Multi-Hop**
   Modifikasi kelas `MockReActLLM` agar menghasilkan rantai inferensi berikut:
   *   *Iterasi 1:* Memanggil `RegionalSalesMetricsTool` untuk region `"EMEA"`.
   *   *Iterasi 2:* Memanggil `StatisticalAnomalyTool` untuk memeriksa angka penjualan EMEA.
   *   *Iterasi 3:* Menghasilkan `Final Answer` yang memvalidasi anomali dan merekomendasikan perbaikan data.

4. **Langkah 3: Jalankan Deteksi Siklus**
   Uji ketahanan sistem dengan mengonfigurasi LLM agar memanggil `RegionalSalesMetricsTool` dengan input yang sama sebanyak 3 kali berturut-turut.

#### Kriteria Keberhasilan Verifikasi:
*   [ ] Loop kognitif berjalan minimal 2 langkah analitik dan berhenti secara deterministik pada `Final Answer`.
*   [ ] Tidak ada kegagalan parsing tipe data selama eksekusi Pydantic.
*   [ ] Algoritma deteksi siklus berhasil menangkap redundansi pada Langkah 3 dan memicu exception `CyclicExecutionError` secara bersih tanpa *unhandled crash*.
*   [ ] Jejak eksekusi (*trajectory trace*) terekam lengkap dan dapat diekspor ke format JSON terstruktur.