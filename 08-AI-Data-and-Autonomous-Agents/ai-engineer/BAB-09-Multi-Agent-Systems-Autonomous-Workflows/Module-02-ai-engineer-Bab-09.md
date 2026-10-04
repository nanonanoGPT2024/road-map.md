# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi Multi-Agent Systems

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Mendesain dan Mengimplementasikan Arsitektur Multi-Agent Tingkat Lanjut**: Menguasai implementasi pola *Hierarchical Supervisor*, *Choreographed Mesh*, dan *Blackboard Architecture* menggunakan *Deterministic State Graphs*.
2. **Mengelola State Terdistribusi dan Resiliensi**: Menerapkan *state persistence*, *checkpointing transactional*, penanganan *race conditions*, serta pola *Human-in-the-Loop* (HITL) dengan mekanisme *time-travel debugging*.
3. **Membangun Protokol Komunikasi Antar-Agen (A2A)**: Mengintegrasikan skema validasi tipe data ketat (*strict schema contracts*) dan *structured message passing* berbasis Pydantic/gRPC untuk meminimalisasi halusinasi delegasi.
4. **Mengoptimalkan Observabilitas Sistem Otonom**: Mengonfigurasi *distributed tracing* berbasis OpenTelemetry untuk memantau siklus hidup eksekusi agen, konsumsi token, dan latensi *node-to-node*.
5. **Menerapkan Strategi Mitigasi Kegagalan Produksi**: Mencegah *infinite loop ping-pong*, *state explosion*, kegagalan konsensus, dan kebocoran anggaran komputasi (*token runaway*).

---

## 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib memahami:
* **Python Lanjutan**: Asyncio (`async`/`await`), *concurrency primitives*, context managers, serta *type hinting* mendalam dengan `typing.Annotated`.
* **Pydantic v2**: Validasi skema, serialisasi/deserialisasi, kustomisasi validator, dan penanganan *discriminated unions*.
* **Dasar Single-Agent**: Pola ReAct (Reasoning + Acting), konsep pemanggilan fungsi (*Tool/Function Calling*), serta batasan context window LLM.
* **Dasar Graph State Engine**: Pemahaman mendasar atas pustaka berbasis graf komputasi (diutamakan LangGraph atau AutoGen v0.4+).
* **Distributed System Fundamentals**: Pengetahuan dasar tentang Message Broker (Redis Pub/Sub, Kafka), ACID vs. BASE, serta *distributed locks*.

---

## 3. Concept & Internal Architecture

### 3.1 Dari Single-Agent ReAct ke Multi-Agent Systems (MAS)
Pada implementasi *Single-Agent ReAct*, seluruh penalaran, pemilihan alat, dan sintesis akhir dibebankan pada satu model LLM dengan satu context window. Pendekatan ini mengalami degradasi performa eksponensial (*context saturation*, *attention dilution*, dan *instruction drift*) saat sistem membutuhkan lebih dari 10–15 alat eksternal atau dependensi multi-domain yang kompleks.

Multi-Agent Systems (MAS) memecah kompleksitas komputasional ini dengan prinsip **Separation of Concerns** dan **Modular Specialization**. Dalam arsitektur produksi, MAS bukan sekadar "sekumpulan LLM yang saling mengobrol secara bebas", melainkan **Sistem Graf Keadaan Deterministik Terdistribusi** (*Distributed Deterministic State Graph Engine*) di mana model bahasa bertindak sebagai unit logika transisi keadaan (*state transition logic*), bukan sebagai pengendali alur utama (*flow controller*).

### 3.2 Topologi Arsitektur Multi-Agent

```
+-----------------------------------------------------------------------------------+
|                           TOPOLOGI ARSITEKTUR MULTI-AGENT                         |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|  1. HIERARCHICAL SUPERVISOR              2. CHOREOGRAPHED MESH                    |
|                                                                                   |
|            [ User Ingress ]                         [ Ingress ]                   |
|                   |                                      |                        |
|            +--------------+                              v                        |
|            |  Supervisor  |                      +---------------+                |
|            | (Orchestrator)<---+                 |  Agent Alpha  |----+           |
|            +-------+------+    |                 +-------+-------+    |           |
|               /    |    \      |                         |            |           |
|              v     v     v     |                         v            v           |
|           [Ag-A] [Ag-B] [Ag-C]-+                 +---------------+  +-----------+ |
|             |      |      |                      |  Agent Beta   |->|Agent Gamma| |
|           (Tools)(Tools)(Tools)                  +---------------+  +-----------+ |
|                                                                                   |
|  3. BLACKBOARD ARCHITECTURE                                                       |
|                                                                                   |
|         +-------------+      Read/Write      +-------------------+                |
|         | Agent Alpha | <==================> |                   |                |
|         +-------------+                      |    SHARED STATE   |                |
|         | Agent Beta  | <==================> |    (Blackboard/   |                |
|         +-------------+                      |     Redis/DB)     |                |
|         | Agent Gamma | <==================> |                   |                |
|         +-------------+                      +-------------------+                |
|                                                                                   |
+-----------------------------------------------------------------------------------+
```

1. **Hierarchical Supervisor (Orchestrator-Workers)**:
   * Sebuah agen pusat (*Supervisor*) bertindak sebagai *router* dan evaluator. Agen pekerja (*Workers*) memiliki lingkup tanggung jawab sempit, sekumpulan alat spesifik, dan konteks terisolasi.
   * Hubungan bersifat siklik terkontrol: Supervisor $\to$ Worker $\to$ Supervisor.
   * Cocok untuk: Task berorientasi pipeline analitis, audit kepatuhan, dan sintesis multidisiplin.

2. **Choreographed Mesh (Peer-to-Peer)**:
   * Tidak memiliki koordinator terpusat. Transisi keadaan ditentukan oleh kontrak pertukaran pesan antar agen berdasarkan keluaran sebelumnya.
   * Rentan terhadap siklus tak terbatas (*infinite circular transitions*) jika tidak dibatasi oleh *finite-state automata* (FSM).
   * Cocok untuk: Skenario negosiasi, simulasi pasar, dan pemrosesan terdistribusi asinkron.

3. **Blackboard Architecture**:
   * Agen-agen independen memantau memori bersama (*shared state board*). Ketika agen melihat kondisi atau artefak yang relevan dengan spesialisasi mereka, mereka melakukan kalkulasi, memodifikasi board, dan memicu agen lain.
   * State diverifikasi melalui mekanisme *optimistic locking* atau *CRDTs (Conflict-free Replicated Data Types)*.
   * Cocok untuk: Sistem intelijen ancaman siber, analisis log forensik heterogen, dan perancangan kompleks.

### 3.3 State Management & Execution Engine Mechanics
Secara internal, framework mutakhir (seperti LangGraph) mengoperasikan MAS sebagai graf berarah (*Directed Graph*):
$$\mathcal{G} = (\mathcal{V}, \mathcal{E}, \mathcal{S})$$
Di mana:
* $\mathcal{V}$ adalah himpunan *Nodes* (agen, pemanggil fungsi, pemroses data).
* $\mathcal{E}$ adalah himpunan *Edges* (transisi langsung atau kondisional berdasarkan predikat $\rho: \mathcal{S} \to \mathcal{V}$).
* $\mathcal{S}$ adalah *Shared Graph State Schema* yang dimutasi melalui fungsi akumulator (*reducers*).

Dalam lingkungan produksi multi-tenant:
* **State Immutability & Reducers**: State diperlakukan sebagai entitas *append-only* atau dimutasi menggunakan fungsi reduksi yang deterministik (misalnya, `operator.add` untuk daftar pesan, atau *shallow merge* eksplisit untuk field metadata).
* **Checkpointers**: Setiap transisi node mengeksekusi *checkpoint write* atomik ke media penyimpanan transaksional (misalnya, PostgreSQL atau Redis). Hal ini menjamin:
  1. *Fault-tolerance*: Sistem dapat melanjutkan proses dari node terakhir yang sukses saat terjadi *pod crash* atau *network partition*.
  2. *Replayability & Time-Travel*: Memungkinkan eksekusi ulang sub-graf dari sembarang state historis untuk keperluan debugging atau branching.
  3. *Human Interrupt*: Eksekusi dihentikan secara sinkron pada edge tertentu, menunggu *state injection* dari operator manusia melalui API sebelum melanjutkan transisi.

---

## 4. Why & What

### Mengapa Single-Agent Gagal di Skala Enterprise?
* **Context Bleed & Interference**: Menempatkan 30 tool functions dalam satu skema JSON Schema menyebabkan LLM mengalami kebingungan dalam memilih parameter yang tepat (*tool misrouting*).
* **Token Cost Explosion**: Dalam pola ReAct panjang, setiap iterasi memuat ulang seluruh riwayat eksekusi alat, menyebabkan peningkatan biaya token kuadratik seiring panjang langkah penalaran.
* **Kerapuhan Penanganan Error**: Kegagalan satu sub-tugas (misalnya timeout API eksternal) berisiko menggagalkan seluruh alur kerja jika tidak terisolasi dalam sub-agent yang memiliki kebijakan *retry* lokal.

### Apa Solusi MAS Terstruktur?
MAS enterprise menyediakan arsitektur yang:
* **Terspesialisasi**: Membatasi ruang lingkup operasional LLM ke domain kognitif kecil (misalnya, hanya fokus pada sintaksis SQL, hanya membaca metrik APM, dsb.).
* **Deterministik**: Membatasi kebebasan LLM menggunakan *Guarded Graph Boundaries*. Keputusan kapan alur berhenti, beralih, atau meminta persetujuan manusia dikendalikan oleh *hard-coded business logic*, bukan oleh instruksi teks longgar model.
* **Auditabel**: Setiap pesan, alasan (*rationale*), dan eksekusi alat disimpan dengan *trace-id* unik yang terikat pada *session transaction ID*.

---

## 5. How (Workflow Detail)

Alur kerja end-to-end dalam Hierarchical MAS kelas enterprise:

```
[Client Request] 
      │
      ▼
1. INGRESS & CONTEXT SANITIZATION
   ├─ Authn/Authz Verification
   ├─ Guardrails Validation (Input safety, PII Masking)
   └─ State Initialization (Assign Session ID & Thread ID)
      │
      ▼
2. SUPERVISOR ARBITRATION NODE
   ├─ Evaluasi Graph State saat ini
   ├─ Ekstraksi Task Dependency
   └─ Prediksi Transisi Berikutnya (Conditional Edge Evaluation)
      │
      ├───────────────────────┬───────────────────────┐
      ▼                       ▼                       ▼
3a. WORKER NODE: SQL    3b. WORKER NODE: FORENSIC  3c. HUMAN INTERRUPT
   ├─ Context Pruning      ├─ Sandbox Code Exec       ├─ Graph Halted
   ├─ Tool Execution       ├─ API Data Fetch          ├─ Webhook Notification
   └─ Local Reduction      └─ Local Reduction         └─ Operator Input Mutates State
      │                       │                       │
      └───────────────────────┼───────────────────────┘
                              │
                              ▼
4. STATE REDUCTION & CONFLICT RESOLUTION
   ├─ Append Messages via Thread-Safe Reducer
   ├─ Mutate Global Blackboard Metadata
   └─ Write Checkpoint ke Persistent Store (Postgres/Redis)
      │
      ▼
5. SUPERVISOR CONVERGENCE CHECK
   ├─ Apakah goal terpenuhi?
   │    ├─ Tidak: Loop kembali ke Langkah 2 (Maksimum Recursion Depth diuji)
   │    └─ Ya: Alihkan ke Final Synthesizer Node
      │
      ▼
6. EGRESS & TELEMETRY SINK
   ├─ Output Validation (Pydantic Response Schema)
   ├─ Export OpenTelemetry Spans (Latensi, Token Counts, Cost)
   └─ Return Streamed Response ke Client
```

---

## 6. Analogy & Diagram ASCII

### Analogi: Ruang Komando Investigasi Forensik Enterprise
Bayangkan investigasi penipuan bank berskala besar:
* **Supervisor**: Kepala Tim Investigasi. Dia tidak membuka database atau menganalisis log transaksi secara langsung. Tugasnya adalah menugaskan kasus, mengevaluasi bukti dari para ahli, dan menentukan apakah laporan sudah siap dipublikasikan atau butuh pendalaman lanjutan.
* **Worker 1 (Database Forensics Specialist)**: Hanya mengerti SQL dan akses ke database inti. Mengambil data transaksi mentah dan mengembalikan ringkasan tabulasi.
* **Worker 2 (KYC & Sanction Compliance Specialist)**: Membaca dokumen identitas, memeriksa daftar cekal Interpol/OFAC, dan mengidentifikasi anomali profil.
* **Human-in-the-Loop (Chief Legal Officer)**: Jika draf laporan mengindikasikan tuntutan pidana terhadap akun tertentu, sistem secara hukum wajib berhenti. Kepala Tim harus menunggu tanda tangan digital otorisasi sebelum mengirim berkas ke pihak kepolisian.

### Arsitektur Mesin State Terdistribusi

```
+---------------------------------------------------------------------------------------+
| LANGGRAPH ASYNCHRONOUS CHECKPOINTING ENGINE                                           |
+---------------------------------------------------------------------------------------+
|                                                                                       |
|   Thread ID: "tx-corrupt-investigation-8902"                                          |
|                                                                                       |
|   +-------------------+                                                               |
|   |  Start / Ingress  |                                                               |
|   +---------+---------+                                                               |
|             |                                                                         |
|             v                                                                         |
|   +-------------------+       [Route Decision: "forensic_analyst"]                    |
|   |    Supervisor     | -----------------------------------------+                    |
|   +---------+---------+                                          |                    |
|             ^                                                    v                    |
|             | Return Summary                           +--------------------+         |
|             +----------------------------------------- |  Forensic Analyst  |         |
|             |                                          +---------+----------+         |
|             |                                                    | Tool Calls         |
|             |                                                    v                    |
|             |                                          +--------------------+         |
|             |                                          | Sandbox Python ENV |         |
|             |                                          +--------------------+         |
|             v [Route Decision: "human_review"]                                        |
|   +-------------------+                                                               |
|   |   Halt / Pause    | ===> Emit Checkpoint Event ke DB                             |
|   | (Awaiting Signal) | <=== Inject Mutation via API (Operator Approves)             |
|   +---------+---------+                                                               |
|             |                                                                         |
|             v                                                                         |
|   +-------------------+                                                               |
|   | Final Synthesizer |                                                               |
|   +---------+---------+                                                               |
|             |                                                                         |
|             v                                                                         |
|   +-------------------+                                                               |
|   |   End / Output    |                                                               |
|   +-------------------+                                                               |
|                                                                                       |
+---------------------------------------------------------------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Conceptual State Graph with Reducer
Contoh dasar yang mendemonstrasikan mekanisme reduksi state atomik dalam Python murni sebelum masuk ke implementasi framework:

```python
from typing import Annotated, TypedDict, List
import operator

# Reducer: menambahkan elemen baru ke dalam list tanpa memutasi state lama secara in-place
def append_messages(existing: List[str], new_messages: List[str]) -> List[str]:
    return existing + new_messages

class AgentState(TypedDict):
    messages: Annotated[List[str], append_messages]
    current_node: str

def node_analyst(state: AgentState) -> dict:
    return {
        "messages": ["Analyst: Anomali terdeteksi pada baris 45-80."],
        "current_node": "analyst"
    }

# Simulasi transisi state
state: AgentState = {"messages": ["System: Memulai audit."], "current_node": "init"}
delta = node_analyst(state)
state["messages"] = append_messages(state["messages"], delta["messages"])
state["current_node"] = delta["current_node"]

print(state["messages"])
# Output: ['System: Memulai audit.', 'Analyst: Anomali terdeteksi pada baris 45-80.']
```

---

### 7.2 Practical Example: Enterprise Anti-Money Laundering (AML) Multi-Agent Network
Implementasi siap produksi menggunakan **LangGraph v0.2+**, **Pydantic v2**, dan model LLM dengan dukungan *structured outputs*, penanganan status persisten, serta *conditional interrupt*.

```python
import asyncio
import operator
from typing import Annotated, Dict, List, Literal, Sequence, TypedDict
from pydantic import BaseModel, Field

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode

# =====================================================================
# 1. SCHEMAS & STATE DEFINITION
# =====================================================================

class RouterDecision(BaseModel):
    """Skema deterministik untuk routing supervisor."""
    next_node: Literal["forensic_agent", "compliance_agent", "human_approval", "synthesizer"] = Field(
        description="Node spesialis berikutnya yang harus mengeksekusi instruksi, atau synthesizer jika analisa selesai."
    )
    routing_reasoning: str = Field(description="Alasan teknis di balik keputusan perutean ini.")

class AMLInvestigationState(TypedDict):
    """State global transaksi investigasi AML."""
    messages: Annotated[Sequence[BaseMessage], operator.add]
    target_account_id: str
    risk_score: float
    requires_law_enforcement_escalation: bool
    audit_log: Annotated[List[str], operator.add]

# =====================================================================
# 2. ISOLATED TOOL ECOSYSTEM
# =====================================================================

@tool
def query_account_ledger(account_id: str) -> str:
    """Mengambil riwayat transaksi 30 hari terakhir dari sistem inti perbankan."""
    # Simulasi pembacaan DB read-replica
    return f"LEDGER [{account_id}]: Total 12 transaksi senilai IDR 4.500.000.000. Ditemukan 4 transaksi terstruktur di bawah batas IDR 500.000.000 dalam 24 jam."

@tool
def check_pep_and_sanctions_database(account_id: str) -> str:
    """Memeriksa apakah pemilik akun terdaftar di Politically Exposed Persons (PEP) atau daftar sanksi."""
    return f"SANCTION_SCREENING [{account_id}]: Match terdeteksi: Entitas terindikasi kerabat dekat pihak regulasi tingkat 1. Status: HIGH_RISK."

# =====================================================================
# 3. AGENT FACTORY & LLM INITIALIZATION
# =====================================================================

llm = ChatOpenAI(model="gpt-4o", temperature=0)

# Supervisor Node
def supervisor_node(state: AMLInvestigationState) -> Dict:
    system_prompt = (
        "Anda adalah AML Investigation Supervisor. Analisis temuan di state saat ini dan putuskan langkah berikutnya.\n"
        "Aturan Routing:\n"
        "- Jika data transaksi mentah belum ada -> forensic_agent\n"
        "- Jika data transaksi ada tapi status sanksi belum ada -> compliance_agent\n"
        "- Jika risk_score > 80 dan eskalasi hukum terindikasi -> human_approval\n"
        "- Jika seluruh bukti forensik dan kepatuhan terkumpul -> synthesizer"
    )
    
    structured_router = llm.with_structured_output(RouterDecision)
    decision: RouterDecision = structured_router.invoke([
        SystemMessage(content=system_prompt),
        *state["messages"]
    ])
    
    log_entry = f"Supervisor: Mengarahkan tugas ke '{decision.next_node}'. Alasan: {decision.routing_reasoning}"
    return {
        "messages": [AIMessage(content=f"SUPERVISOR: Next action is {decision.next_node}")],
        "audit_log": [log_entry]
    }

# Forensic Agent Worker
def forensic_agent_node(state: AMLInvestigationState) -> Dict:
    tools = [query_account_ledger]
    model_with_tools = llm.bind_tools(tools)
    
    prompt = (
        f"Anda adalah Forensic Specialist. Investigasi akun target: {state['target_account_id']}. "
        "Gunakan query_account_ledger untuk mendapatkan fakta empiris. Berikan kesimpulan struktural."
    )
    response = model_with_tools.invoke([SystemMessage(content=prompt), *state["messages"]])
    
    # Deteksi indikasi structuring (smurfing) sederhana
    risk_increment = 45.0 if "terstruktur" in response.content else 0.0
    
    return {
        "messages": [response],
        "risk_score": state.get("risk_score", 0.0) + risk_increment,
        "audit_log": [f"ForensicAgent: Menjalankan audit ledger untuk {state['target_account_id']}."]
    }

# Compliance Agent Worker
def compliance_agent_node(state: AMLInvestigationState) -> Dict:
    tools = [check_pep_and_sanctions_database]
    model_with_tools = llm.bind_tools(tools)
    
    prompt = (
        f"Anda adalah Compliance Specialist. Periksa latar belakang sanksi dan PEP akun: {state['target_account_id']}. "
        "Gunakan check_pep_and_sanctions_database."
    )
    response = model_with_tools.invoke([SystemMessage(content=prompt), *state["messages"]])
    
    high_sanction = "HIGH_RISK" in response.content
    risk_increment = 40.0 if high_sanction else 5.0
    
    return {
        "messages": [response],
        "risk_score": state.get("risk_score", 0.0) + risk_increment,
        "requires_law_enforcement_escalation": high_sanction,
        "audit_log": [f"ComplianceAgent: Skrining kepatuhan selesai. Skor risiko bertambah {risk_increment}."]
    }

# Synthesizer Node
def synthesizer_node(state: AMLInvestigationState) -> Dict:
    summary_prompt = (
        "Buat laporan formal investigasi AML berdasarkan seluruh log analisis yang tersedia. "
        "Sertakan skor risiko total dan rekomendasi akhir."
    )
    response = llm.invoke([SystemMessage(content=summary_prompt), *state["messages"]])
    return {
        "messages": [response],
        "audit_log": ["Synthesizer: Laporan akhir berhasil disusun."]
    }

# =====================================================================
# 4. GRAPH CONSTRUCTION & CONDITIONAL EDGES
# =====================================================================

def supervisor_router(state: AMLInvestigationState) -> str:
    # Mengambil node target dari pesan terakhir supervisor
    last_message = state["messages"][-1].content
    for target in ["forensic_agent", "compliance_agent", "human_approval", "synthesizer"]:
        if target in last_message:
            return target
    return "synthesizer"

workflow = StateGraph(AMLInvestigationState)

# Pendaftaran Node
workflow.add_node("supervisor", supervisor_node)
workflow.add_node("forensic_agent", forensic_agent_node)
workflow.add_node("compliance_agent", compliance_agent_node)
workflow.add_node("synthesizer", synthesizer_node)

# Tool Execution Nodes
workflow.add_node("forensic_tools", ToolNode([query_account_ledger]))
workflow.add_node("compliance_tools", ToolNode([check_pep_and_sanctions_database]))

# Konektivitas Graph
workflow.add_edge(START, "supervisor")

workflow.add_conditional_edges(
    "supervisor",
    supervisor_router,
    {
        "forensic_agent": "forensic_agent",
        "compliance_agent": "compliance_agent",
        "human_approval": END, # Berhenti di sini untuk HITL (interupsi manual)
        "synthesizer": "synthesizer"
    }
)

# Transisi Worker ke Tools atau kembali ke Supervisor
def make_tool_evaluator(tool_node_name: str):
    def route_tool_or_supervisor(state: AMLInvestigationState) -> str:
        last_msg = state["messages"][-1]
        if hasattr(last_msg, "tool_calls") and len(last_msg.tool_calls) > 0:
            return tool_node_name
        return "supervisor"
    return route_tool_or_supervisor

workflow.add_conditional_edges("forensic_agent", make_tool_evaluator("forensic_tools"))
workflow.add_edge("forensic_tools", "forensic_agent")

workflow.add_conditional_edges("compliance_agent", make_tool_evaluator("compliance_tools"))
workflow.add_edge("compliance_tools", "compliance_agent")

workflow.add_edge("synthesizer", END)

# Inisialisasi Checkpointer untuk transactional state persistence
memory_checkpoint = MemorySaver()
app = workflow.compile(
    checkpointer=memory_checkpoint,
    interrupt_before=["human_approval"] # Menetapkan breakpoint operasional
)

# =====================================================================
# 5. ASYNC EXECUTION DEMONSTRATION
# =====================================================================

async def main():
    config = {"configurable": {"thread_id": "investigation-case-corp-9941"}}
    
    initial_input: AMLInvestigationState = {
        "messages": [HumanMessage(content="Lakukan investigasi kepatuhan terhadap akun PT-CORP-888921")],
        "target_account_id": "PT-CORP-888921",
        "risk_score": 0.0,
        "requires_law_enforcement_escalation": False,
        "audit_log": ["System: Memulai session investigasi."]
    }

    print("\n--- [FASE 1: EKSEKUSI OTONOM MENUJU HUMAN-IN-THE-LOOP] ---")
    async for event in app.astream(initial_input, config=config, stream_mode="values"):
        current_node = event.get("messages")[-1].content[:60] if event.get("messages") else "None"
        print(f"[AUDIT LOG SIZE: {len(event['audit_log'])}] | Risk: {event.get('risk_score')} | Last Signal: {current_node}...")

    # Memeriksa State saat ini setelah terinterupsi
    snapshot = app.get_state(config)
    print(f"\n[SISTEM DIHENTIKAN SEMENTARA]. Next Node: {snapshot.next}")
    print(f"Total Risk Calculated: {snapshot.values['risk_score']}")
    print(f"Escalation Required: {snapshot.values['requires_law_enforcement_escalation']}")

    # Simulasi Otorisasi Manusia (Human Injection)
    print("\n--- [FASE 2: HUMAN INTERVENTION DITERIMA - RESUME WORKFLOW] ---")
    # Operator memasukkan approval eksplisit ke dalam state messages
    app.update_state(
        config,
        {"messages": [HumanMessage(content="LEGAL_OFFICER_APPROVAL: Eskalasi diverifikasi dan diizinkan secara hukum. Lanjutkan sintesis laporan.")]},
        as_node="supervisor"
    )

    # Lanjutkan sisa graf komputasi langsung ke synthesizer
    async for event in app.astream(None, config=config, stream_mode="values"):
        if "Synthesizer: Laporan akhir berhasil disusun." in event["audit_log"]:
            print("\n[HASIL LAPORAN AKHIR]:")
            print(event["messages"][-1].content)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Pipeline Automated Underwriting & Due Diligence Skala FinTech
* **Organisasi**: Platform Pinjaman Korporasi B2B Global (Volume: 10.000 aplikasi per hari, tiket kredit rata-rata $250.000).
* **Tantangan Arsitektur**:
  1. Analisis satu proposal membutuhkan data dari 5 sumber data heterogen (Bank API, DJP/Tax API, Pengadilan Arbitrase/Litigasi, Analisis Laporan Keuangan PDF 200 halaman, dan Sentimen Berita).
  2. Pendekatan Single-Agent ReAct gagal akibat kehabisan token (context exhaustion) dan latensi rata-rata mencapai 4 menit dengan tingkat halusinasi kalkulasi EBITDA sebesar 18%.
* **Solusi Multi-Agent Terdistribusi**:
  * Mengadopsi **Hierarchical LangGraph Pattern** yang dideploy di AWS EKS (Elastic Kubernetes Service) dengan arsitektur terpisah per pod:
    1. *Coordinator Agent Pod*: Mengatur siklus analisis, menjadwalkan ekstraksi data paralel.
    2. *Tax & Financial Parser Agent (Deterministic Tool-only)*: Menggunakan LLM terisolasi yang diwajibkan menulis Python script ke dalam Pyodide sandbox guna menghitung rasio likuiditas dan debt-to-equity ratio (zero financial hallucination).
    3. *Litigation & Sanction Agent*: Menggunakan embeddings terindeks Milvus untuk mencari riwayat gugatan di pengadilan.
    4. *Underwriting Synthesizer*: Mengagregasi artefak ke format skema JSON terstandarisasi untuk *Core Banking System*.
  * **State & Reliability**:
    * Checkpoint state disimpan dalam Amazon Aurora PostgreSQL Serverless.
    * Pembaruan data asinkron menggunakan Kafka event streaming untuk memicu worker node.
* **Hasil Pengukuran Produksi**:
  * **Latensi Rata-rata**: Turun dari 240 detik menjadi 38 detik (karena pengambilan data forensik berjalan secara asynchronous parallel).
  * **Tingkat Kesalahan Numerik Finansial**: Turun dari 18% ke 0% (karena agen didelegasikan untuk selalu mengeksekusi kode Python sandbox dalam perhitungan).
  * **Efisiensi Biaya Token**: Biaya token turun 62% per aplikasi pinjaman karena prompt worker terisolasi dan context window tidak terkontaminasi oleh percakapan antar agen lain.

---

## 9. Trade-offs

| Dimensi Arsitektur | Choreographed Mesh (P2P) | Hierarchical Orchestration | Blackboard Shared Memory |
| :--- | :--- | :--- | :--- |
| **Performance & Latency** | Menengah; dapat terjadi latensi tinggi jika terjadi *circular chatter*. | **Tinggi (Optimasi Paralel)**; koordinator mendistribusikan task secara serentak. | Sangat Tinggi; agen membaca/menulis memori lokal secara konkruen. |
| **Debuggability & Observability** | **Sangat Rendah**; jejak penalaran tersebar di banyak arah transisi. | **Sangat Tinggi**; alur deterministik, mudah dilacak melalui *trace execution tree*. | Menengah; membutuhkan pelacakan revisi state temporal yang sangat teliti. |
| **Cost (Token Consumption)** | Seringkali Meledak (*Runaway tokens*) karena agen berbicara bolak-balik tanpa batas. | **Terkontrol**; supervisor dapat memangkas (*prune*) context sebelum dikirim ke worker. | Terkontrol, asalkan schema state difilter ketat sebelum dibaca oleh agen. |
| **Fault Resilience** | Rendah; jika satu agen gagal merespons, alur desentralisasi terhenti. | **Tinggi**; supervisor dapat mengeksekusi *fallback logic* atau mengulang tugas agen yang mati. | Tinggi; kegagalan satu agen tidak memutus ketersediaan shared board. |
| **Kompleksitas Implementasi** | Rendah di awal, namun luar biasa rumit saat skala sistem membesar. | **Menengah-Tinggi**; membutuhkan skema komunikasi dan edge routing yang matang. | **Sangat Tinggi**; membutuhkan penanganan *race conditions* dan *concurrency control*. |

---

## 10. Common Mistakes & Troubleshooting

### 1. The "Ping-Pong" Infinite Loop
* **Gejala**: Dua agen saling mengembalikan tugas secara bergantian (misalnya, Code Writer Agent dan Code Reviewer Agent terus meminta revisi minor tanpa batas akhir). Biaya API membengkak dalam hitungan menit.
* **Akar Masalah**: Ketiadaan batasan kedalaman rekursi graf (*recursion limit*) dan kriteria terminasi deterministik dalam edge evaluation.
* **Solusi Produksi**:
  1. Pasang parameter `recursion_limit` pada konfigurasi runtime graf (misal: `config={"recursion_limit": 25}`).
  2. Implementasikan counter integer pada state: `iteration_count: Annotated[int, operator.add]`. Jika `iteration_count >= MAX_RETRIES`, paksa transisi diarahkan ke `human_escalation_node` atau hentikan graf secara otomatis.

### 2. State Bloat / Context Window Overflow
* **Gejala**: Menjelang langkah ke-10, eksekusi node melambat secara dramatis dan menghasilkan error HTTP 400 (`maximum context length exceeded`).
* **Akar Masalah**: Menggunakan operator `operator.add` secara membabi buta pada seluruh field state pesan (`messages: Annotated[Sequence[BaseMessage], operator.add]`), sehingga seluruh riwayat mentah eksekusi alat sebelumnya terbawa ke agen berikutnya.
* **Solusi Produksi**:
  1. Terapkan strategi **Context Pruning**: Buat node perantara yang melakukan filter atau peringkasan terhadap pesan alat (*ToolMessages*) sebelum kembali ke Supervisor.
  2. Pisahkan `InternalScratchpadMessages` (khusus worker internal) dengan `PublicChannelMessages` (hanya pesan tingkat tinggi yang dapat dibaca oleh Supervisor).

### 3. Hallucinated Agent Routing
* **Gejala**: Supervisor mencoba mengarahkan transisi ke nama node yang tidak terdaftar dalam graf komputasi (misal: mengarahkan ke `"database_agent"` padahal nama node yang terdaftar adalah `"sql_executor"`), memicu runtime `KeyError`.
* **Akar Masalah**: Meminta LLM menghasilkan teks bebas untuk nama node tujuan routing alih-alih memberlakukan validasi berbasis skema (*Schema Enforcement*).
* **Solusi Produksi**:
  Gunakan *Structured Outputs* dengan Pydantic `Literal`:
  ```python
  class RouteSchema(BaseModel):
      target: Literal["sql_executor", "compliance_agent", "end_node"]
  ```

---

## 11. Best Practices (Production Checklist)

1. [ ] **State Machine Enforcement**: Pastikan seluruh rute agen didefinisikan secara grafis (FSM/DAG), bukan membiarkan agen memanggil API agen lain secara tidak terstruktur (*ad-hoc direct call*).
2. [ ] **Isolated Tool Authorization**: Batasi hak akses kredensial per worker agent. Agen pembaca log tidak boleh memiliki kredensial write ke database operasional.
3. [ ] **Granular Checkpointing**: Gunakan database persisten eksternal (PostgreSQL dengan *connection pooling* via PgBouncer) untuk checkpointer LangGraph di produksi. Hindari `MemorySaver` di luar unit testing.
4. [ ] **Token Budget Guards**: Pasang *hard limit* biaya token per Thread ID menggunakan proxy gateway (seperti LiteLLM Proxy atau Portkey) untuk memutus koneksi secara otomatis jika biaya satu sesi melampaui ambang batas tertentu (misal: > $0.50).
5. [ ] **Deterministic Human Breakpoints**: Gunakan fitur interupsi graf statis (`interrupt_before` atau `interrupt_after`) untuk semua tindakan yang mengubah status sistem (*side-effects*), seperti: eksekusi transfer dana, penulisan ke database produksi, atau pengiriman email massal.
6. [ ] **OpenTelemetry Semantic Conventions**: Instrumentasikan MAS dengan OpenTelemetry Span. Setiap run agen wajib memuat atribut: `gen_ai.agent.name`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, dan `graph.node.id`.

---

## 12. Hands-on Practice

Simpan seluruh file praktikum ini ke dalam direktori: `hands-on/m02/`

### File Structure:
```
hands-on/m02/
├── requirements.txt
├── .env.example
├── app/
│   ├── __init__.py
│   ├── state.py
│   ├── agents.py
│   ├── graph.py
│   └── main.py
└── tests/
    └── test_routing.py
```

### Langkah 1: Siapkan Environment & Dependencies
Buat file `hands-on/m02/requirements.txt`:
```text
langgraph>=0.2.14
langchain-core>=0.3.0
langchain-openai>=0.2.0
pydantic>=2.8.0
python-dotenv>=1.0.0
pytest>=8.0.0
pytest-asyncio>=0.23.0
```

Instalasi environment:
```bash
cd hands-on/m02
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Masukkan OPENAI_API_KEY Anda ke file .env
```

### Langkah 2: Definisikan State Kontrak Terisolasi
Buat file `hands-on/m02/app/state.py`:
```python
import operator
from typing import Annotated, Sequence, TypedDict, List
from langchain_core.messages import BaseMessage

class ProductionGraphState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    incident_id: str
    severity_level: str
    remediation_approved: bool
    audit_trail: Annotated[List[str], operator.add]
```

### Langkah 3: Bangun Logika Graf dan Interupsi
Buat file `hands-on/m02/app/graph.py`:
```python
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from app.state import ProductionGraphState
from langchain_core.messages import AIMessage, HumanMessage

def triage_agent(state: ProductionGraphState):
    return {
        "messages": [AIMessage(content="Triage: Keparahan insiden teridentifikasi sebagai CRITICAL.")],
        "severity_level": "CRITICAL",
        "audit_trail": ["Triage Agent mengklasifikasikan insiden sebagai CRITICAL."]
    }

def remediation_planner(state: ProductionGraphState):
    return {
        "messages": [AIMessage(content="Remediation: Mengajukan restart pod armada payment-gateway.")],
        "audit_trail": ["Remediation Agent menyusun rencana aksi pemulihan sistem."]
    }

def executor_agent(state: ProductionGraphState):
    if not state.get("remediation_approved", False):
        raise PermissionError("Ekskusi ditolak: Rencana remediasi belum disetujui.")
    return {
        "messages": [AIMessage(content="Executor: Patch berhasil diaplikasikan ke cluster.")],
        "audit_trail": ["Executor Agent sukses mengeksekusi instruksi pemulihan."]
    }

builder = StateGraph(ProductionGraphState)
builder.add_node("triage", triage_agent)
builder.add_node("planner", remediation_planner)
builder.add_node("executor", executor_agent)

builder.add_edge(START, "triage")
builder.add_edge("triage", "planner")
builder.add_edge("planner", "executor")
builder.add_edge("executor", END)

# Stop eksekusi sebelum node executor berjalan (Human-in-the-Loop breakpoint)
checkpoint_memory = MemorySaver()
compiled_app = builder.compile(
    checkpointer=checkpoint_memory,
    interrupt_before=["executor"]
)
```

### Langkah 4: Uji Skenario Interupsi & Resumption
Buat file `hands-on/m02/app/main.py`:
```python
import asyncio
from app.graph import compiled_app
from langchain_core.messages import HumanMessage

async def run_pipeline():
    config = {"configurable": {"thread_id": "INCIDENT-SEC-101"}}
    
    initial_state = {
        "messages": [HumanMessage(content="Deteksi latensi spike pada microservice pembayaran.")],
        "incident_id": "INCIDENT-SEC-101",
        "severity_level": "UNKNOWN",
        "remediation_approved": False,
        "audit_trail": ["Init: Sinyal monitoring diterima."]
    }
    
    print("\n>>> Menjalankan pipeline hingga breakpoint...")
    for event in compiled_app.stream(initial_state, config=config):
        print(event)
        
    state_snapshot = compiled_app.get_state(config)
    print(f"\n[STATUS TERHENTI]: Graf menunggu aksi sebelum node: {state_snapshot.next}")
    
    print("\n>>> Melakukan injeksi Approval dari Engineer (State Mutation)...")
    compiled_app.update_state(
        config,
        {"remediation_approved": True, "audit_trail": ["Operator: Persetujuan eksekusi diberikan."]},
        as_node="planner"
    )
    
    print("\n>>> Melanjutkan pipeline yang sempat terhenti...")
    for event in compiled_app.stream(None, config=config):
        print(event)
        
    final_state = compiled_app.get_state(config)
    print("\n>>> Pipeline selesai. Seluruh jejak audit:")
    for log in final_state.values["audit_trail"]:
        print(f" - {log}")

if __name__ == "__main__":
    asyncio.run(run_pipeline())
```

Jalankan skrip:
```bash
python -m app.main
```

---

## 13. Exercise

### Tingkat 1: Easy
* **Tugas**: Tambahkan node `ValidatorAgent` setelah `TriageAgent` pada praktikum di atas.
* **Kebutuhan**: Validasi teks insiden. Jika teks insiden mengandung kata `"test"`, mutasikan state `severity_level` menjadi `"LOW"` dan paksa alur langsung melompat ke `END` tanpa mengeksekusi `RemediationPlanner`.

### Tingkat 2: Medium
* **Tugas**: Implementasikan **Dynamic Tool Budgeting** pada sebuah worker agent.
* **Kebutuhan**: Buat worker agent yang dibekali 3 tools pencarian data. Tambahkan field `remaining_tool_calls: int` (default: 3) pada state. Setiap kali sebuah tool dieksekusi, kurangi nilainya dengan 1. Jika `remaining_tool_calls == 0`, hentikan eksekusi tool lebih lanjut secara paksa dan kembalikan fallback message ke Supervisor tanpa melempar runtime exception.

### Tingkat 3: Hard
* **Tugas**: Bangun **Distributed Quorum Consensus Multi-Agent System**.
* **Kebutuhan**:
  1. Terdapat 3 `SecurityAnalystAgent` independen dengan konfigurasi model atau system prompt berbeda (misal: Analyst-A berbasis Zero-Trust, Analyst-B berbasis Business Continuity, Analyst-C berbasis Historical Risk).
  2. Ketiga agen mengevaluasi payload transaksi yang sama secara asinkron (`asyncio.gather`).
  3. Buat `ConsensusVotingNode` yang menghitung perbandingan keputusan (*majority rule* 2 dari 3). Jika konsensus tercapai, perbarui state global dan lanjutkan graf. Jika tidak tercapai kesepakatan konsensus (*deadlock*), picu conditional edge menuju node `human_arbitration`.

---

## 14. Challenge

### Skenario Kasus Kompleks: Autonomous Cloud Infrastructure Auto-Remediation Mesh
Perusahaan SaaS Anda mengelola lebih dari 5.000 kontainer Kubernetes di 3 region cloud penyedia yang berbeda. Seringkali terjadi cascading failure (misalnya: *OOMKilled pods*, *stale database connections*, dan *DNS lookup timeouts*). 

**Spesifikasi Desain Sistem yang Wajib Anda Rancang**:
1. **Multi-Agent Architecture Topology**: Desain graf agen yang terdiri atas:
   * *Telemetry Ingestion Agent*: Mendengarkan payload alert dari Prometheus Alertmanager.
   * *Log Diagnostics Agent*: Menjalankan pencarian log berbasis OpenSearch secara terisolasi.
   * *Infrastructure Mutation Agent*: Mengantongi otorisasi perbaikan (misalnya: scale deployment, evict pods, clear cache).
   * *Safety Guardrail & Rollback Agent*: Mengawasi performa klaster setelah perbaikan diaplikasikan selama 5 menit.
2. **Strict Guardrail Constraints**:
   * Agen infrastruktur **DILARANG KERAS** menghapus Persistent Volume Claims (PVC) atau mengubah deployment namespace produksi tanpa verifikasi kriptografis dari tim SRE on-call.
   * Sistem harus mengimplementasikan algoritma pendeteksi *cyclic flapping* (jika sistem yang sama mengalami auto-remediation lebih dari 2 kali dalam rentang 30 menit, graf secara otomatis membatalkan diri, melakukan rollback ke konfigurasi stabil terakhir, dan membunyikan alarm PagerDuty level P1).
3. **Delivery Artifact**:
   * Diagram graf kondisi komputasi detail (Node, Edge, Reducer, Checkpoint Store).
   * Kode implementasi orkestrasi graf dalam Python menggunakan LangGraph dengan schema Pydantic yang divalidasi penuh.
   * Simulasi skenario pengujian unit (*mocked testing*) yang membuktikan sistem berhasil menolak instruksi perbaikan destruktif saat token verifikasi operator tidak valid.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (5 Pertanyaan)
1. Apa kelemahan struktural terbesar dari arsitektur *Single-Agent ReAct* ketika dihadapkan pada tugas enterprise yang memiliki lusinan alat eksternal (*tools*)?
2. Dalam perancangan state graph (seperti LangGraph), apa peran mendasar dari fungsi akumulator (*Reducer*) pada skema state?
3. Sebutkan perbedaan fundamental antara pendekatan komunikasi multi-agent *Choreographed Mesh* dan *Hierarchical Supervisor*!
4. Mengapa penggunaan `MemorySaver` bawaan tidak direkomendasikan untuk beban kerja produksi (*production workload*)?
5. Apa kegunaan utama dari parameter `recursion_limit` pada eksekusi graph engine otonom?

### Bagian 2: Intermediate (5 Pertanyaan)
1. Bagaimana cara mencegah terjadinya *Context Window Saturation* pada Hierarchical Multi-Agent System yang menjalankan ratusan iterasi penalaran?
2. Dalam mekanisme *Human-in-the-Loop* (HITL), jelaskan perbedaan mendasar antara interupsi tipe `interrupt_before` dan `interrupt_after` terhadap snapshot state yang tersimpan pada checkpointer!
3. Mengapa penentuan rute (*routing*) dari Supervisor ke worker node wajib divalidasi menggunakan struktur data ketat (*strict schema/Pydantic*) daripada teks instruksi bebas LLM?
4. Bagaimana Anda menangani kondisi *Race Condition* ketika dua worker agent mencoba memperbarui field array yang sama pada Shared State Blackboard secara bersamaan?
5. Mengapa pemanggilan kode eksekusi arbitrer (misal: analisis kalkulasi finansial) oleh agen spesialis wajib dijalankan di dalam lingkungan sandboxing (seperti Pyodide/Docker terisolasi), alih-alih dieksekusi via `eval()` pada runtime container agen?

### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan)

#### Skenario 1: The Cascading Hallucination Loop
Sebuah sistem Multi-Agent Customer Support Enterprise mengalami anomali di mana *Agent Invoicing* berselisih dengan *Agent Refund Policy*. Keduanya saling mengirimkan revisi pesan sebanyak 80 kali per menit hingga kuota token per jam dari penyedia API habis.
* **Pertanyaan**: Mekanisme arsitektur apa yang terbukti gagal pada implementasi graf tersebut? Desainlah strategi perbaikan berbasis kode/kondisi edge untuk memastikan insiden ini tidak dapat terulang kembali secara matematis!

#### Skenario 2: Deadlock on Network Partition during Human-in-the-Loop
Sebuah graf investigasi transaksi perbankan dihentikan untuk menunggu persetujuan otorisasi dari Risk Officer (`interrupt_before=["wire_transfer_node"]`). Server node Worker yang menampung memori runtime graf mengalami *pod crash* mendadak (OOMKilled) sebelum Risk Officer menekan tombol persetujuan di portal dashboard internal.
* **Pertanyaan**: Ketika pod Kubernetes baru aktif kembali, langkah operasional dan arsitektur database checkpointer apa yang menjamin transaksi perbankan tersebut tidak terduplikasi (*idempotency*) dan status penundaan persetujuan tidak hilang?

#### Skenario 3: Data Poisoning Across Isolated Nodes
Dalam sebuah sistem riset intelijen pasar, *Web Scraping Agent* mengekstrak data dari forum publik dan menyuntikkannya ke state global tanpa pembersihan. Ketika *Investment Strategy Agent* memproses state tersebut, ia mengeksekusi instruksi tersembunyi (*Prompt Injection*) yang tertanam di halaman web, menyebabkan laporan akhir berisikan rekomendasi pembelian aset kripto palsu.
* **Pertanyaan**: Bagaimana Anda merestrukturisasi batas arsitektur (*trust boundaries*) dan isolasi pesan antar-agen pada sistem graf tersebut untuk mengisolasi potensi serangan *indirect prompt injection* dari data input mentah?

---

## 16. Summary

1. **Multi-Agent Systems sebagai Deterministic Graphs**: MAS enterprise yang reliabel dibangun di atas fondasi *Directed State Graphs* yang deterministik, di mana LLM difungsikan sebagai unit logika penalaran lokal pada simpul (*nodes*), bukan sebagai pengendali alur eksekusi infrastruktur global (*edges*).
2. **Kedaulatan State dan Transaksionalitas**: Ketahanan arsitektur produksi bergantung pada *State Reducers* yang *pure/idempotent* dan penyimpanan checkpoint transaksional (misal: PostgreSQL/Redis). Ini memberikan kemampuan *zero-data-loss recovery*, audit jejak penalaran secara forensik, dan mekanisme *Human-in-the-Loop* yang aman.
3. **Separation of Concerns Mengalahkan Monolithic Prompts**: Mengisolasi tools, konteks memori, dan instruksi sistem ke dalam agen-agen spesialis terbukti menurunkan tingkat halusinasi pemanggilan alat dan menekan biaya token secara signifikan dibanding sistem single-agent monolitik.
4. **Disiplin Rekayasa Perangkat Lunak untuk Agen Otonom**: Keberhasilan implementasi MAS di level enterprise tidak ditentukan oleh seberapa pintarnya instruksi teks *system prompt*, melainkan oleh ketegasan batasan teknis: batas kedalaman rekursi (*recursion limit*), skema validasi tipe data yang ketat (*Pydantic contracts*), observabilitas telemetri OpenTelemetry, dan isolasi sandbox komputasi.