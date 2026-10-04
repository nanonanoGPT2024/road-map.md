# Bab 09: Monetization, Pricing Strategies & Unit Economics

## Module 01: Arsitektur Monetisasi & Unit Economics Sistem AI & Autonomous Agents

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Technical Product Manager (TPM) dan AI Product Lead diharapkan mampu:
- **Merumuskan Model Unit Economics Presisi Tinggi**: Menghitung *Cost of Goods Sold* (COGS) dinamis untuk sistem inferensi LLM dan Autonomous Agent—mencakup *input/output tokens*, *fine-tuning amortization*, *vector retrieval infrastructure*, dan *human-in-the-loop (HITL) operational expenditure*.
- **Mengevaluasi Topologi Pricing AI**: Membandingkan dan memilih antara model *Pure Consumption/Token-Based*, *Hybrid Subscription with Overage*, *Credit-Based Metering*, dan *Outcome-Based Pricing* berdasarkan korelasi antara *perceived customer value* dan *underlying compute cost*.
- **Merancang Dynamic Margin Protection Guardrails**: Mengembangkan spesifikasi sistem proteksi margin *real-time* untuk mencegah fenomena *Denial of Wallet (DoW)* yang dipicu oleh *agent execution loops*, *context window bloat*, dan variabilitas nondeterministik model.
- **Mengintegrasikan Telemetri Billing & FinOps**: Mengarsitekturi alur data telemetri dari layer orkestrasi agent ke sistem *billing engine* dengan latensi rendah dan auditabilitas finansial mutlak.

---

### 2. Concept Overview

Monetisasi produk berbasis Traditional SaaS umumnya beroperasi pada *Gross Margin* 75%–85% karena biaya marjinal per kueri komputasi (CPU/Database IOPS) mendekati nol ($\Delta C \approx 0$). Sebaliknya, sistem AI Generatif dan Autonomous Agent memperkenalkan pola komputasi intensif dengan biaya marjinal non-nol ($\Delta C \gg 0$) yang bervariasi secara nondeterministik pada setiap interaksi.

```
Traditional SaaS Unit Economics:
[User Action] ---> [App Server / DB] ---> (Marginal Cost: ~$0.00001) ---> Gross Margin: 80-90%

AI/Agentic SaaS Unit Economics:
[User Action] ---> [Context Retrieval (RAG)] 
              ---> [LLM Reasoner Step 1..N] 
              ---> [Tool Call / Verification] 
              ---> (Marginal Cost: Variable $0.005 - $0.50) ---> Gross Margin: Compressed (30-65%)
```

#### Mental Model: The Cost-Value Duality Framework
Sebagai AI Product Manager, Anda tidak menjual *software artifacts*; Anda menjual *synthetic cognitive labor*. Dalam merancang monetisasi, terdapat dua vektor gaya yang saling bertolak belakang:
1. **Value Metric (Customer Perspective)**: Satuan unit yang selaras dengan nilai bisnis pengguna (misal: *Resolved Support Ticket*, *Code Pull Request Merged*, *Contract Analyzed*).
2. **Cost Driver (Infrastructure Perspective)**: Satuan unit yang menentukan biaya penyedia infrastruktur (misal: *Input Tokens, Output Tokens, GPU/vLLM Time, Embedding Computations, Vector DB Read/Write IOPS*).

Kegagalan monetisasi AI terjadi ketika ada **Decoupling Extremum** antara *Value Metric* dan *Cost Driver*. Jika produk menetapkan tarif *flat-rate unlimited seat* sementara konsumsi token agen tidak dibatasi (*unbounded step count*), produk tersebut dijamin mengalami kompresi margin menuju angka negatif.

---

### 3. Why It Matters

Di level enterprise, ketidakpastian biaya inferensi adalah salah satu faktor utama yang menghambat transisi proyek AI dari *Proof-of-Concept* (PoC) ke fase *Production Deployment*.

#### Kasus Nyata: The Uncontrolled Agent Execution Bankruptcy
Sebuah platform otomatisasi *Legal-Tech B2B* menerapkan skema $99/bulan *flat fee* untuk analisis kontrak tanpa batas. Pada mulanya, sistem hanya mengeksekusi *single-pass prompting* dengan biaya rata-rata $0.08 per kontrak. 

Namun, ketika sistem ditingkatkan menjadi arsitektur Autonomous Multi-Agent (Research Agent $\to$ Compliance Agent $\to$ Drafter Agent $\to$ Critic Agent), terjadi lonjakan rata-rata token consumption:
- Satu dokumen kompleks (200 halaman) memicu rata-rata 38 *tool iterations* dan *agent reflection loops*.
- Total konsumsi: 1.2M *input tokens* dan 180k *output tokens* menggunakan Claude 3.5 Sonnet.
- Biaya per kontrak melonjak menjadi $6.30.
- Pengguna enterprise dengan beban 30 kontrak/hari menghasilkan COGS: $6.30 \times 30 \times 22\text{ hari kerja} = \$4,158/\text{bulan}$.
- **Net Margin: -$4,059 per customer per bulan.**

Model monetisasi yang cacat bukan sekadar isu *sales*, melainkan kegagalan arsitektur produk yang mengancam kelangsungan hidup operasional bisnis.

---

### 4. Arsitektur & Diagram Komponen

Arsitektur billing sistem AI harus ditempatkan sedekat mungkin dengan *runtime orchestration* untuk menegakkan *budget guardrails* sebelum, saat, dan sesudah inferensi terjadi.

```
+---------------------------------------------------------------------------------------+
|                                    CLIENT APPLICATION                                 |
+---------------------------------------------------------------------------------------+
                                           |
                                [1] Request with Auth & Org ID
                                           v
+---------------------------------------------------------------------------------------+
|                                  API GATEWAY & PROXY                                  |
|  +---------------------------------------------------------------------------------+  |
|  | Entitlement Enforcement: Verify Quota / Available Balance                       |  |
|  +---------------------------------------------------------------------------------+  |
+---------------------------------------------------------------------------------------+
                                           |
                                [2] Verified Job Request
                                           v
+---------------------------------------------------------------------------------------+
|                               AGENT EXECUTION RUNTIME                                 |
|                                                                                       |
|  +---------------------------------------------------------------------------------+  |
|  | Policy Engine: Dynamic Execution Limits (Max Loops: 5, Max Spend: $0.50/job)    |  |
|  +---------------------------------------------------------------------------------+  |
|                                           |                                           |
|       +-----------------------------------+-----------------------------------+       |
|       | [3a] Read Embeddings              | [3b] Model Inference Call         |       |
|       v                                   v                                   v       |
|  +--------------------+         +--------------------+              +---------------+ |
|  | Vector DB          |         | LLM Gateway Router |              | Tool Sandbox  | |
|  | (Pinecone/Milvus)  |         | (LiteLLM/Portkey)  |              | (Code Exec)   | |
|  +--------------------+         +--------------------+              +---------------+ |
|            \                              |                                 /         |
|             \                             |                                /          |
|              +----------------------------+-------------------------------+           |
|                                           |                                           |
|                       [4] Emit Raw Consumption Telemetry                              |
|                           (Job ID, Tokens, Tool Latency)                              |
+-------------------------------------------|-------------------------------------------+
                                            v
+---------------------------------------------------------------------------------------+
|                              USAGE METERING & RATING PIPELINE                         |
|                                                                                       |
|  +---------------------------------------------------------------------------------+  |
|  | Event Deduplication & Validation (Kafka / Redpanda)                             |  |
|  +---------------------------------------------------------------------------------+  |
|                                           |                                           |
|  +---------------------------------------------------------------------------------+  |
|  | Rating Engine: Apply Model Pricing Matrix + Dynamic Margin Markup               |  |
|  +---------------------------------------------------------------------------------+  |
+-------------------------------------------|-------------------------------------------+
                                            |
                      +---------------------+---------------------+
                      | [5] Update Ledger                         | [6] Over-budget Alert
                      v                                           v
+---------------------------------------+     +-----------------------------------------+
| FINOPS LEDGER & BILLING ENGINE        |     | WEBSOCKET / NOTIFICATION                |
| (Stripe / Stripe Metered / Orb)       |     | Force Circuit Break on Agent Loop       |
+---------------------------------------+     +-----------------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### 5.1 Formulasi Matematis Unit Economics AI
Biaya marjinal penyediaan inferensi autonomous agent untuk transaksi ke-$i$ dinyatakan sebagai:

$$COGS_i = C_{tokens}(T_{in}, T_{out}) + C_{retrieval}(K_v, D_{dims}) + C_{tools}(N_{calls}, T_{wall}) + C_{infra}$$

Di mana:
- $C_{tokens} = (T_{in} \times P_{in}) + (T_{out} \times P_{out})$
  - $T_{in}$: Jumlah input token (termasuk *system prompts*, *chat history*, dan *retrieved contexts*).
  - $T_{out}$: Jumlah output token (*generated completions*, *tool call arguments*).
  - $P_{in}, P_{out}$: Biaya per token model yang bersangkutan.
- $C_{retrieval} = N_{embed} \times (T_{query} \times P_{embed}) + (K_v \times P_{vdb\_read})$
- $C_{tools}$: Total biaya eksekusi API eksternal pihak ketiga (misal: Serper/Google Search, E2B sandbox, scraping proxy).
- $C_{infra}$: Biaya amortisasi server hosting internal yang dinormalisasi ke *execution wall-time*.

**Contribution Margin (CM) per Work Unit**:

$$CM\% = \frac{Revenue_i - COGS_i}{Revenue_i} \times 100$$

Dalam bisnis AI SaaS yang sehat, target **Blended Gross Margin** harus berada di kisaran:
- $\ge 60\%$ untuk *Self-serve/PLG Tier*.
- $\ge 70\%$ untuk *Enterprise Custom-tier* (setelah memperhitungkan infrastruktur dedicated).

#### 5.2 Strategi Pricing: Analisis Komparatif

| Model Pricing | Mekanisme | Keuntungan | Risiko & Kelemahan | Best Suited For |
| :--- | :--- | :--- | :--- | :--- |
| **Pure Seat-Based** | Biaya flat bulanan per user (misal: $30/user/bln). | Model SaaS tradisional yang disukai tim procurement enterprise; ARR terprediksi. | Sangat rentan terhadap degradasi margin jika pengguna adalah *power users*. | Tool produktivitas asistif sederhana (e.g., Copilot text rewrite). |
| **Pure Token / Compute-Based** | Pass-through harga token + markup persentase konstan. | Proteksi margin 100% terhadap lonjakan penggunaan infra. | *Billing shock* pada pelanggan; sulit dipahami oleh buyers non-teknis. | Developer API tools (OpenAI, Anthropic, Replicate). |
| **Credit-Based Metering** | Konversi nilai uang ke "Credits" fungsional (misal: 1000 kredit = $10). | Mengabstraksi volatilitas harga token dari model berbeda; memudahkan promo & packaging. | Membutuhkan arsitektur *metering ledger real-time* yang kompleks. | AI Platform & Horizontal Multi-modal Tools (Midjourney, Runway). |
| **Outcome-Based / Work-Metric** | Menagih per hasil terverifikasi (misal: $1.50 per tiket dukungan teresolusi). | Keselarasan total dengan ROI pelanggan; nilai monetisasi tertinggi per task. | Risiko finansial beralih ke vendor jika agen gagal menyelesaikan tugas (COGS tetap keluar, revenue $0). | Autonomous Workflow Agents (Devin, Decagon, Sierra). |

#### 5.3 Prinsip Rekayasa Margin Melalui Caching
Efisiensi unit economics secara fundamental ditentukan oleh arsitektur caching:
- **Prompt Caching (Context Caching)**: Provider seperti Anthropic dan OpenAI memberikan diskon hingga 50-90% untuk input token yang di-cache. Menyusun *prompt architecture* agar prefix sistem bersifat statis meningkatkan *cache hit rate*, yang secara dramatis menaikkan gross margin:

$$P_{in\_effective} = (Hit\_Rate \times P_{in\_cached}) + ((1 - Hit\_Rate) \times P_{in\_raw})$$

- **Semantic Cache (Vector In-Memory Cache)**: Mengkueri Redis/Qdrant sebelum memanggil model LLM. Jika kesamaan semantik (*cosine similarity*) $\ge 0.95$, kembalikan jawaban sebelumnya dengan biaya komputasi $0.0001 (latensi $<20$ms), mengeliminasi *inference cost* sepenuhnya.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi **Production-Grade FinOps Metering & Cost-Allocation Engine** yang bertugas menghitung biaya transaksi inferensi, memvalidasi kuota margin, mencatat transaksi ke dalam *audit ledger*, dan memicu *circuit breaker* jika eksekusi agent melampaui alokasi modal kerja (*maximum budget per job*).

```python
# metering_engine.py
"""
AI & Autonomous Agent Metering, Cost Allocation, and Margin Guardrail Engine.
Production-ready, strictly typed, thread-safe implementation.
"""

from __future__ import annotations

import enum
import logging
import threading
import time
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Optional, Tuple

# Setup Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")
logger = logging.getLogger("AIMeteringEngine")


class ModelProvider(str, enum.Enum):
    OPENAI_GPT4O = "gpt-4o"
    OPENAI_GPT4O_MINI = "gpt-4o-mini"
    ANTHROPIC_CLAUDE_SONNET_35 = "claude-3-5-sonnet-20241022"


@dataclass(frozen=True)
class ModelUnitCost:
    """Harga input/output per 1.000.000 (1M) tokens dalam USD Decimal."""
    input_cost_per_m: Decimal
    output_cost_per_m: Decimal
    cached_input_cost_per_m: Decimal


# Pricing Table (Source: Provider Official Specs)
MODEL_PRICING_TABLE: Dict[ModelProvider, ModelUnitCost] = {
    ModelProvider.OPENAI_GPT4O: ModelUnitCost(
        input_cost_per_m=Decimal("2.50"),
        output_cost_per_m=Decimal("10.00"),
        cached_input_cost_per_m=Decimal("1.25"),
    ),
    ModelProvider.OPENAI_GPT4O_MINI: ModelUnitCost(
        input_cost_per_m=Decimal("0.15"),
        output_cost_per_m=Decimal("0.60"),
        cached_input_cost_per_m=Decimal("0.075"),
    ),
    ModelProvider.ANTHROPIC_CLAUDE_SONNET_35: ModelUnitCost(
        input_cost_per_m=Decimal("3.00"),
        output_cost_per_m=Decimal("15.00"),
        cached_input_cost_per_m=Decimal("0.30"),
    ),
}

ONE_MILLION = Decimal("1000000")


class BudgetExceededException(Exception):
    """Exception raised when an agent run violates dynamic spend limits."""
    pass


class InvalidPricingConfigurationException(Exception):
    """Exception raised when model configuration cannot be rated."""
    pass


@dataclass
class TokenConsumptionRecord:
    session_id: str
    tenant_id: str
    model: ModelProvider
    raw_input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    tool_cost_usd: Decimal = Decimal("0.000000")
    timestamp: float = field(default_factory=time.time)

    def validate(self) -> None:
        if self.raw_input_tokens < 0 or self.cached_input_tokens < 0 or self.output_tokens < 0:
            raise ValueError("Token counts cannot be negative.")
        if self.cached_input_tokens > self.raw_input_tokens:
            raise ValueError("Cached input tokens cannot exceed total raw input tokens.")
        if self.tool_cost_usd < Decimal("0.0"):
            raise ValueError("Tool costs cannot be negative.")


@dataclass
class RatedTransactionLedger:
    transaction_id: str
    session_id: str
    tenant_id: str
    cogs_usd: Decimal
    target_price_usd: Decimal
    gross_margin_percent: Decimal
    token_metrics: Dict[str, int]
    timestamp: float


class AgentCostLedger:
    """Thread-safe persistent ledger simulation for tracking tenant usage."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tenant_spend: Dict[str, Decimal] = {}
        self._transaction_history: list[RatedTransactionLedger] = []

    def record_transaction(self, entry: RatedTransactionLedger) -> None:
        with self._lock:
            current_spend = self._tenant_spend.get(entry.tenant_id, Decimal("0.000000"))
            self._tenant_spend[entry.tenant_id] = current_spend + entry.cogs_usd
            self._transaction_history.append(entry)

    def get_tenant_spend(self, tenant_id: str) -> Decimal:
        with self._lock:
            return self._tenant_spend.get(tenant_id, Decimal("0.000000"))


class MarginGovernor:
    """
    Enforces real-time cost calculation, pricing assignment, and dynamic margin protections.
    """

    def __init__(
        self,
        target_margin_threshold: Decimal,
        hard_limit_budget_per_session: Decimal,
        ledger: AgentCostLedger,
    ) -> None:
        """
        :param target_margin_threshold: Minimum acceptable gross margin (e.g., Decimal("0.60") for 60%).
        :param hard_limit_budget_per_session: Max allowed COGS spend per single agent session.
        """
        self.target_margin_threshold = target_margin_threshold
        self.hard_limit_budget_per_session = hard_limit_budget_per_session
        self.ledger = ledger

    def calculate_cogs(self, consumption: TokenConsumptionRecord) -> Decimal:
        consumption.validate()

        if consumption.model not in MODEL_PRICING_TABLE:
            raise InvalidPricingConfigurationException(f"Unsupported model: {consumption.model}")

        pricing = MODEL_PRICING_TABLE[consumption.model]

        uncached_input_tokens = Decimal(consumption.raw_input_tokens - consumption.cached_input_tokens)
        cached_input_tokens = Decimal(consumption.cached_input_tokens)
        output_tokens = Decimal(consumption.output_tokens)

        cost_uncached = (uncached_input_tokens / ONE_MILLION) * pricing.input_cost_per_m
        cost_cached = (cached_input_tokens / ONE_MILLION) * pricing.cached_input_cost_per_m
        cost_output = (output_tokens / ONE_MILLION) * pricing.output_cost_per_m

        total_cogs = cost_uncached + cost_cached + cost_output + consumption.tool_cost_usd
        return total_cogs.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

    def evaluate_pricing_and_guardrails(
        self,
        consumption: TokenConsumptionRecord,
        transaction_id: str,
        price_charged_to_customer: Decimal,
    ) -> RatedTransactionLedger:
        """
        Calculates COGS, checks circuit breakers, validates gross margins, and commits to the ledger.
        """
        cogs = self.calculate_cogs(consumption)

        # 1. Enforce Hard Circuit Breaker (Denial of Wallet Protection)
        if cogs > self.hard_limit_budget_per_session:
            logger.critical(
                f"CIRCUIT BREAKER TRIGGERED: Session {consumption.session_id} exceeded maximum budget. "
                f"COGS: ${cogs}, Limit: ${self.hard_limit_budget_per_session}"
            )
            raise BudgetExceededException(
                f"Agent run exceeded safety budget allowance (${cogs} > ${self.hard_limit_budget_per_session})."
            )

        # 2. Margin Calculation: (Price - COGS) / Price
        if price_charged_to_customer <= Decimal("0.00"):
            gross_margin = Decimal("-1.00")  # Complete loss / free tier
        else:
            gross_margin = (price_charged_to_customer - cogs) / price_charged_to_customer

        # 3. Soft Guardrail Log Alert for Product Managers
        if gross_margin < self.target_margin_threshold:
            logger.warning(
                f"MARGIN DEGRADATION WARNING: Session {consumption.session_id} achieved only "
                f"{gross_margin * Decimal('100'):.2f}% margin. Target is {self.target_margin_threshold * Decimal('100'):.2f}%."
            )

        # 4. Construct Transaction Record
        ledger_entry = RatedTransactionLedger(
            transaction_id=transaction_id,
            session_id=consumption.session_id,
            tenant_id=consumption.tenant_id,
            cogs_usd=cogs,
            target_price_usd=price_charged_to_customer,
            gross_margin_percent=(gross_margin * Decimal("100")).quantize(Decimal("0.01")),
            token_metrics={
                "raw_input": consumption.raw_input_tokens,
                "cached_input": consumption.cached_input_tokens,
                "output": consumption.output_tokens,
            },
            timestamp=time.time(),
        )

        # 5. Commit to Storage Ledger
        self.ledger.record_transaction(ledger_entry)
        return ledger_entry


# Demonstration and Verification
if __name__ == "__main__":
    ledger = AgentCostLedger()
    
    # Initialize margin governor: target 65% Gross Margin, hard circuit breaker at $0.50 per session
    governor = MarginGovernor(
        target_margin_threshold=Decimal("0.65"),
        hard_limit_budget_per_session=Decimal("0.500000"),
        ledger=ledger,
    )

    print("--- 1. Testing Standard Agent Session (Healthy Margin) ---")
    session_1 = TokenConsumptionRecord(
        session_id="sess_alpha_01",
        tenant_id="enterprise_acme_corp",
        model=ModelProvider.ANTHROPIC_CLAUDE_SONNET_35,
        raw_input_tokens=15000,
        cached_input_tokens=12000,  # 80% cache hit on large system prompt
        output_tokens=1200,
        tool_cost_usd=Decimal("0.005"),  # Search API query cost
    )

    # Customer is billed $0.15 for this business action (Task based)
    billed_price = Decimal("0.150000")
    tx1 = governor.evaluate_pricing_and_guardrails(session_1, "tx_1001", billed_price)
    
    print(f"Transaction ID       : {tx1.transaction_id}")
    print(f"Calculated COGS     : ${tx1.cogs_usd}")
    print(f"Price Billed        : ${tx1.target_price_usd}")
    print(f"Gross Margin Realized: {tx1.gross_margin_percent}%\n")

    print("--- 2. Testing Unoptimized Agent Session (Margin Erosion) ---")
    session_2 = TokenConsumptionRecord(
        session_id="sess_beta_02",
        tenant_id="enterprise_globex",
        model=ModelProvider.OPENAI_GPT4O,
        raw_input_tokens=85000,
        cached_input_tokens=0,      # Cache miss!
        output_tokens=4000,
        tool_cost_usd=Decimal("0.020"),
    )
    # Customer is billed fixed $0.20 for this action
    billed_price_unoptimized = Decimal("0.200000")
    tx2 = governor.evaluate_pricing_and_guardrails(session_2, "tx_1002", billed_price_unoptimized)
    
    print(f"Transaction ID       : {tx2.transaction_id}")
    print(f"Calculated COGS     : ${tx2.cogs_usd}")
    print(f"Price Billed        : ${tx2.target_price_usd}")
    print(f"Gross Margin Realized: {tx2.gross_margin_percent}%\n")

    print("--- 3. Testing Infinite Loop Circuit Breaker (Denial of Wallet Defense) ---")
    session_malicious = TokenConsumptionRecord(
        session_id="sess_gamma_loop",
        tenant_id="enterprise_initech",
        model=ModelProvider.ANTHROPIC_CLAUDE_SONNET_35,
        raw_input_tokens=250000,
        cached_input_tokens=0,
        output_tokens=35000,        # Runaway output generation
        tool_cost_usd=Decimal("0.100"),
    )
    
    try:
        governor.evaluate_pricing_and_guardrails(
            session_malicious, "tx_1003", price_charged_to_customer=Decimal("0.50")
        )
    except BudgetExceededException as err:
        print(f"Execution successfully halted by FinOps Circuit Breaker: {err}")

    print("\nAggregate Tenant Spend in Ledger:")
    print(f"Acme Corp Total Spend : ${ledger.get_tenant_spend('enterprise_acme_corp')}")
    print(f"Globex Total Spend    : ${ledger.get_tenant_spend('enterprise_globex')}")
```

---

### 7. Edge Cases & Failure Modes

| Failure Mode | Mekanisme Penyebab | Dampak Finansial & Operasional | Strategi Mitigasi Arsitektural |
| :--- | :--- | :--- | :--- |
| **Agent ReAct Infinite Looping** | Kegagalan parsing output format JSON/Tool Call menyebabkan agen terus mengulang `Observation -> Thought -> Action`. | Biaya token berakumulasi secara geometrik dalam hitungan detik; $50–$200 terbakar dalam satu sesi. | Terapkan batas absolut `max_iterations = 6` di level orkestrator dan pasang *spend limiter per runtime job* di FinOps proxy. |
| **Denial of Wallet (DoW) via Context Hijacking** | Pengguna menyuntikkan dokumen PDF bervolume raksasa (500 halaman) atau instruksi manipulasi prompt untuk mengekstraksi teks berulang. | Output token membengkak maksimal ($15/1M tokens). Margin transaksi menjadi sangat negatif. | Batasi *file upload parsing* secara ketat ($<20$ halaman/kueri); terapkan kuota agregat input-token per menit. |
| **Prompt Cache Eviction Degradation** | *Model provider* melakukan cold restart pada inference clusters atau mengubah parameter hash prompt secara diam-diam. | *Cache hit rate* anjlok dari 85% ke 0%; COGS per kueri melonjak hingga 4x lipat secara mendadak. | Monitor metrik rasio cache secara berkala; buat dynamic alert jika *blended token cost* naik lebih dari 20% dalam 1 jam. |
| **API Pricing Shift / Currency Devaluation** | Provider upstream menaikkan harga API tanpa notifikasi awal, atau terjadi fluktuasi nilai tukar valuta asing bagi non-USD revenue. | Seluruh kalkulasi unit economics menjadi kadaluarsa; gross margin terdistorsi tanpa disadari. | Gunakan tabel dynamic pricing yang sinkron secara berkala melalui API; sediakan safety margin buffer 10% pada baseline pricing. |

---

### 8. Trade-offs & Alternatif Solusi

Setiap keputusan monetisasi menyeimbangkan antara kenyamanan adopsi pelanggan (*buyer experience*) dan kepastian margin bisnis (*business viability*).

```
                      PREDICTABILITY FOR CUSTOMER
                                   ▲
                                   │  Flat-Rate Unlimited Seat
                                   │  (Risiko margin vendor ekstrem)
                                   │
                                   │         Hybrid Subscription + Overage
                                   │         (Optimal Compromise)
                                   │
         Credit-Based Metering     │
                                   │
                                   │  Pure Token Pass-Through
                                   │  (Risiko finansial 0% bagi vendor,
                                   │   adopsi user sangat terhambat)
                                   ▼
◄─────────────────────────────────────────────────────────────────────►
ZERO VENDOR RISK                                   HIGH CUSTOMER VALUE
```

#### Detailed Trade-off Matrix

1. **Flat-Rate Subscription vs. Consumption-Based Overage**:
   - *Flat-Rate*: Mempercepat siklus penjualan enterprise karena anggaran bersifat terprediksi (*predictable CAPEX/OPEX*). Namun, TPM terpaksa membatasi kapabilitas model (*model downgrading*, misal memaksa penggunaan GPT-4o-mini padahal pengguna membutuhkan penalaran tinggi).
   - *Hybrid*: Solusi standar emas industri modern. Paket menyertakan alokasi kuota standar (misal: 100 *Deep Research Jobs*/bulan). Konsumsi di atas itu otomatis dialihkan ke penagihan per-unit atau degradasi kecepatan (*soft cap/hard cap*).

2. **Outcome-Based vs. Usage-Based**:
   - *Outcome-Based*: Memberikan kekuatan penetapan harga (*pricing power*) luar biasa. Menagih $10 per *successfully merged software patch* memberikan margin $>90\%$ jika patch selesai dengan biaya token $\$0.80$.
   - *Risiko*: Membutuhkan mekanisme evaluasi deterministik (*Ground Truth Evaluator*) yang tidak dapat diperdebatkan. Jika model merasa tugas sudah selesai namun pengguna menolak klaim tersebut, tim sales/support akan menghadapi perselisihan penagihan (*dispute handling overhead*).

---

### 9. Best Practices & Standard Industri

1. **Establish the "FinOps First" Hierarchy**:
   Jangan pernah merilis fitur Autonomous Agent ke production tanpa menghubungkannya ke *instrumented proxy* (misal: OpenLIT, LiteLLM Proxy, atau custom proxy seperti Portkey). Setiap kueri *wajib* membawa header kontekstual:
   `X-Tenant-ID`, `X-Feature-ID`, `X-User-Role`, dan `X-Session-ID`.

2. **Decouple Front-end Credits from Back-end Tokens**:
   Jangan pernah memaparkan jumlah "Tokens" kepada pengguna non-teknis. Gunakan terminologi operasional seperti **Compute Units (CU)**, **Credits**, atau **Task Runs**. 
   - 1 Task Execution = 10 Credits.
   - Hal ini memungkinkan TPM mengubah arsitektur model (misalnya beralih dari GPT-4o ke Llama-3.3-70B yang lebih murah) tanpa harus mengubah kontrak harga atau mengganggu persepsi nilai pelanggan.

3. **Dynamic Model Routing Berdasarkan Kompleksitas Kueri**:
   Terapkan *Classifier-Based Routing* pada layer orkestrasi:
   - Kueri sederhana klasifikasi / ekstraksi entitas diarahkan ke model berbiaya rendah (GPT-4o-mini / Llama-3.1-8B) dengan biaya $\$0.15/\text{1M tokens}$.
   - Kueri penalaran mendalam, arsitektur kode, atau evaluasi dokumen hukum dialihkan ke model frontier (Claude 3.5 Sonnet / o1) dengan biaya $\$3.00-\$15.00/\text{1M tokens}$.
   - Mekanisme ini secara konsisten menurunkan COGS rata-rata sebesar 40%–60% tanpa mengorbankan kualitas keluaran.

4. **SLA FinOps Alerting Cadence**:
   - **Tingkat 1 (Peringatan Otomatis)**: Gross Margin per tenant jatuh di bawah 50% dalam rentang waktu 24 jam.
   - **Tingkat 2 (Circuit Breaking)**: Sesi kueri tunggal melampaui $1.00 dalam biaya inferensi tanpa ada persetujuan eksplisit dari admin tenant.

---

### 10. Hands-on Lab Exercise

#### Skenario:
Anda adalah Principal Technical Product Manager di sebuah startup AI customer service, **AgentDesk**. Perusahaan ingin meluncurkan agen otomatis bernama **Resolver-Agent** yang menangani tiket komplain pengguna secara end-to-end tanpa bantuan manusia. 

Tugas Anda adalah memvalidasi unit economics dan menguji ketahanan margin produk terhadap berbagai skenario beban komputasi.

#### Langkah-Langkah Pengerjaan:

##### Langkah 1: Siapkan Lingkungan Kerja
Pastikan Python 3.10+ telah terpasang. Simpan implementasi kode dari Bagian 6 ke dalam file bernama `metering_engine.py`.

##### Langkah 2: Buat Skrip Simulasi Stress-Test (`simulation_lab.py`)
Buat skrip baru untuk mensimulasikan 100 tiket layanan pelanggan dengan karakteristik dinamis:
- 70% Tiket Sederhana (FAQ, ganti password): Rata-rata 1.500 input token, 300 output token.
- 20% Tiket Menengah (Cek status pesanan + Tool DB lookup): 5.000 input token, 800 output token, 1 tool API call ($0.01).
- 10% Tiket Kompleks (Eskalasi komplain, parsing dokumen transaksi, multi-step tool calls): 35.000 input token, 3.500 output token, 3 tool API calls ($0.03).

```python
# simulation_lab.py
from decimal import Decimal
import random
from metering_engine import (
    AgentCostLedger,
    MarginGovernor,
    ModelProvider,
    TokenConsumptionRecord,
    BudgetExceededException,
)

def run_simulation():
    ledger = AgentCostLedger()
    # Target Margin: 60%, Hard Stop: $0.20 per customer resolution
    governor = MarginGovernor(
        target_margin_threshold=Decimal("0.60"),
        hard_limit_budget_per_session=Decimal("0.200000"),
        ledger=ledger,
    )

    # Fixed revenue model: Enterprise customer pays $0.10 flat rate per resolved ticket
    PRICE_PER_RESOLVED_TICKET = Decimal("0.100000")

    total_revenue = Decimal("0.0")
    total_cogs = Decimal("0.0")
    circuit_breaker_trips = 0
    tickets_processed = 0

    print("Executing 100 Ticket Simulations on Claude-3-5-Sonnet Runtime...")

    for i in range(100):
        tickets_processed += 1
        rand = random.random()
        session_id = f"ticket_run_{i+1:03d}"

        if rand < 0.70:
            # Simple Ticket
            raw_in = 1500
            cached_in = 1200 # System prompt cached
            out = 300
            tool_cost = Decimal("0.0")
        elif rand < 0.90:
            # Medium Ticket
            raw_in = 5000
            cached_in = 3000
            out = 800
            tool_cost = Decimal("0.01")
        else:
            # Complex Runaway / Edge Ticket
            raw_in = 35000
            cached_in = 5000
            out = 3500
            tool_cost = Decimal("0.03")

        record = TokenConsumptionRecord(
            session_id=session_id,
            tenant_id="customer_retail_corp",
            model=ModelProvider.ANTHROPIC_CLAUDE_SONNET_35,
            raw_input_tokens=raw_in,
            cached_input_tokens=cached_in,
            output_tokens=out,
            tool_cost_usd=tool_cost,
        )

        try:
            tx = governor.evaluate_pricing_and_guardrails(
                consumption=record,
                transaction_id=f"tx_{i+1:03d}",
                price_charged_to_customer=PRICE_PER_RESOLVED_TICKET,
            )
            total_revenue += tx.target_price_usd
            total_cogs += tx.cogs_usd
        except BudgetExceededException:
            circuit_breaker_trips += 1
            # Customer still pays base or is escalated to human
            total_revenue += PRICE_PER_RESOLVED_TICKET

    blended_margin = ((total_revenue - total_cogs) / total_revenue) * Decimal("100")
    
    print("\n================ SIMULATION RESULTS ================")
    print(f"Total Tickets Processed    : {tickets_processed}")
    print(f"Circuit Breaker Triggers   : {circuit_breaker_trips}")
    print(f"Total Top-line Revenue     : ${total_revenue:.4f}")
    print(f"Total COGS Incurred        : ${total_cogs:.4f}")
    print(f"Net Realized Gross Margin  : {blended_margin:.2f}%")
    print("====================================================")

    if blended_margin < Decimal("60.0"):
        print("RESULT: UNIT ECONOMICS UNHEALTHY. Pricing adjust or model routing required!")
    else:
        print("RESULT: HEALTHY UNIT ECONOMICS. Ready for Enterprise Go-To-Market.")

if __name__ == "__main__":
    run_simulation()
```

##### Langkah 3: Eksekusi dan Analisis Output
Jalankan simulasi di terminal:
```bash
python simulation_lab.py
```

##### Langkah 4: Evaluasi Keputusan Manajerial Produk
Amati hasil eksekusi:
1. **Periksa Margin Gabungan (*Blended Margin*)**: Apakah flat rate $0.10 cukup untuk menutup biaya tiket kompleks yang menggunakan Claude 3.5 Sonnet?
2. **Eksperimen Intervensi**: Modifikasi model tiket sederhana menjadi `ModelProvider.OPENAI_GPT4O_MINI`. Jalankan kembali simulasi dan amati bagaimana *Smart Model Routing* memulihkan gross margin dari rentang berbahaya (30%–45%) kembali ke level standar enterprise ($>70\%$).
3. **Konfigurasi Ulang Value Metric**: Ubah skema penagihan dari flat rate $0.10 menjadi *Base + Overage* ($0.05 per tiket dasar + $0.05 per tool execution). Catat efeknya terhadap volatilitas margin.