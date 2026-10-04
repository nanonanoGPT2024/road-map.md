# BAB 07: Integrasi Ekosistem Model Context Protocol (MCP)
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis** arsitektur internal spesifikasi Model Context Protocol (MCP) berbasis JSON-RPC 2.0, termasuk siklus hidup koneksi, negosiasi kapabilitas, dan manajemen *transport channel* (stdio vs. SSE/HTTP).
- **Merancang dan mengimplementasikan** server MCP kelas *enterprise* berkinerja tinggi menggunakan SDK resmi (TypeScript/Python) yang mengisolasi akses sumber daya kritis melalui abstraksi *Tools*, *Resources*, dan *Prompts*.
- **Mengintegrasikan** server MCP kustom ke dalam runtime Claude Code CLI dengan skema *Zero-Trust*, kontrol akses berbasis peran (RBAC), dan mekanisme *Human-in-the-Loop* (HITL) untuk operasi destruktif.
- **Mengoptimalkan** konsumsi *context window* LLM melalui teknik *Dynamic Tool Pruning*, kompresi skema parametrik, dan *lazy context retrieval*.
- **Mengoperasikan dan memantau** infrastruktur MCP terdistribusi di lingkungan produksi menggunakan metrik OpenTelemetry (OTel), *structured audit logging*, dan strategi *graceful degradation*.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib menguasai:
- **Dasar Ekosistem Claude Code**: Konfigurasi CLI dasar, eksekusi perintah interaktif, dan arsitektur *agentic loop* bawaan.
- **Protokol Jaringan & Format Serialisasi**: JSON-RPC 2.0 over Streams, Server-Sent Events (SSE), HTTP/1.1 chunked transfer, WebSocket, serta UNIX I/O standard streams (`stdin`, `stdout`, `stderr`).
- **Pemrograman Asinkron**: Node.js/TypeScript (Promises, AsyncIterators, Worker Threads) atau Python 3.11+ (`asyncio`, Context Managers, Pydantic v2).
- **Sistem & Containerization**: Konsep dasar sandboxing Linux (Namespaces, cgroups, seccomp) dan Docker/OCI container runtime.

---

### 3. Concept & Internal Architecture (Mendalam)

Model Context Protocol (MCP) adalah protokol terbuka yang distandarisasi oleh Anthropic untuk mendiversifikasi dan mendekopel kemampuan model bahasa (seperti Claude) dari integrasi data silo yang bersifat monolitik. MCP berperan sebagai jembatan universal antara antarmuka agentic (Claude Code) dengan *data source* dan *execution environment* eksternal.

```
+-------------------------------------------------------------+
|                      Claude Code Engine                     |
|  +--------------------+             +--------------------+  |
|  | Context Controller | <---------> | MCP Client Manager |  |
|  +--------------------+             +--------------------+  |
+-----------------------------------------------|-------------+
                                                |
                 JSON-RPC 2.0 Protocol Boundary | Transports:
                 (Stdio Stream / SSE Stream)    | - StdioTransport
                                                | - SSEClientTransport
                                                v
+-------------------------------------------------------------+
|                      MCP Server Runtime                     |
|  +-------------------------------------------------------+  |
|  | Request Dispatcher & Schema Validator (Zod/Pydantic)  |  |
|  +-------------------------------------------------------+  |
|         |                     |                     |       |
|         v                     v                     v       |
|  +--------------+    +-----------------+    +------------+  |
|  | Tools Engine |    | Resource Engine |    | Prompts    |  |
|  | (Executables)|    | (URIs / Data)   |    | (Templates)|  |
|  +--------------+    +-----------------+    +------------+  |
|         |                     |                     |       |
+---------|---------------------|---------------------|-------+
          v                     v                     v
+-------------------------------------------------------------+
| Subsystem Layer: Enterprise DB / Kubernetes / Git / APIs    |
+-------------------------------------------------------------+
```

#### A. JSON-RPC 2.0 Framing & Primitives

Komunikasi MCP berjalan di atas protokol JSON-RPC 2.0 tanpa dependensi pada transport layer tertentu. Setiap interaksi dienkapsulasi dalam tiga jenis *message frame*:

1. **Request Object**:
   ```json
   {
     "jsonrpc": "2.0",
     "id": "uuid-v4-generated",
     "method": "tools/call",
     "params": {
       "name": "query_database",
       "arguments": { "sql": "SELECT id, status FROM deployments LIMIT 5;" }
     }
   }
   ```
2. **Response Object**:
   ```json
   {
     "jsonrpc": "2.0",
     "id": "uuid-v4-generated",
     "result": {
       "content": [
         {
           "type": "text",
           "text": "[{\"id\": 101, \"status\": \"RUNNING\"}]"
         }
       ],
       "isError": false
     }
   }
   ```
3. **Notification Object** (One-way, fire-and-forget, tanpa *response frame*):
   ```json
   {
     "jsonrpc": "2.0",
     "method": "notifications/resources/updated",
     "params": { "uri": "k8s://cluster-alpha/namespaces/prod/pods" }
   }
   ```

#### B. Connection Lifecycle & Negotiation State Machine

Proses bootstrapping MCP mengikuti *handshake* deterministik:

```
Claude Code (Client)                       MCP Server
        |                                       |
        |--- 1. Initialize Request ------------>|
        |    (ProtocolVersion, Capabilities)    |
        |                                       |
        |<-- 2. Initialize Result --------------|
        |    (ProtocolVersion, Capabilities)    |
        |                                       |
        |--- 3. Initialized Notification ------>|  [State: RUNNING]
        |                                       |
        |--- 4. tools/list Request ------------>|
        |<-- 5. tools/list Response ------------|
        |                                       |
        |--- 6. tools/call Request ------------>|
        |<-- 7. tools/call Response ------------|
        |                                       |
        |--- 8. Shutdown / Process Termination >|  [State: TERMINATED]
```

1. **Initialize Phase**: Klien mengirimkan `initialize` yang mencantumkan versi protokol dan kapabilitas klien (misalnya *roots*, *sampling*). Server memvalidasi versi dan membalas dengan kapabilitasnya sendiri (*tools*, *resources*, *prompts*, *logging*).
2. **Initialized Notification**: Klien mengirim notifikasi bahwa negosiasi selesai. Server dilarang mengirim *requests* atau *notifications* selain handshake sebelum langkah ini selesai.
3. **Operational Phase**: Klien melakukan inspeksi inventaris perangkat lunak melalui `tools/list`, `resources/list`, dan mengeksekusi operasi melalui `tools/call`.

#### C. Transport Abstraction: Stdio vs. SSE

- **Standard I/O (`stdio`)**: Digunakan secara *default* oleh Claude Code lokal. Claude Code memicu subproses (*child process*) dari server MCP. Jalur `stdin` menerima stream JSON-RPC dari klien, `stdout` mengirim respons ke klien, sedangkan `stderr` dialokasikan murni untuk logging manusia / debugging. Setiap data non-JSON-RPC yang terkirim ke `stdout` akan merusak parser JSON buffer dan mematikan koneksi.
- **Server-Sent Events (SSE) / HTTP**: Digunakan untuk arsitektur server terdistribusi atau multi-tenant. Klien membuka koneksi SSE (`GET /sse`) untuk menerima stream notifikasi dan respons dari server, sementara instruksi klien dikirim melalui POST requests (`POST /messages?sessionId=...`).

---

### 4. Why & What

| Dimensi | Pendekatan Tradisional (Hardcoded API/Custom Tool-use) | Model Context Protocol (MCP) |
| :--- | :--- | :--- |
| **Kopling Sistem** | Erat (*tightly coupled*). Setiap integrasi baru memerlukan kompilasi ulang / konfigurasi ulang core orchestrator engine. | Longgar (*decoupled*). Menggunakan protokol terbuka standar; server MCP bersifat *pluggable* secara dinamis. |
| **Keamanan Data** | Kredensial produksi (API keys, DB secrets) harus diinjeksi langsung ke runtime LLM CLI. | Kredensial terisolasi di dalam MCP Server runtime. Claude Code hanya bertindak sebagai pengontrol eksekusi (*orchestrator*). |
| **Konsumsi Konteks** | Seluruh skema dokumentasi endpoint API di-dump ke dalam prompt sistem (*context bloat*). | Skema perangkat diekspos melalui discovery pattern (`tools/list`); data mentah dapat ditransformasi via *Resources*. |
| **Auditing & Kontrol** | Eksekusi tool langsung dari engine LLM tanpa lapisan interceptor terpadu. | Intersepsi request di level transport; dukungan *native* untuk approval gate (HITL) dan OpenTelemetry tracing. |

**Mengapa MCP Kritis untuk Claude Code?**
Claude Code adalah agentic CLI terminal-centric. Jika Claude Code diberikan izin langsung mengeksekusi skrip Bash arbitrer untuk membaca database atau berinteraksi dengan cloud provider, risiko kerusakan akibat halusinasi atau injeksi perintah (*prompt injection*) sangat tinggi. 

Dengan MCP, interaksi diabstraksikan menjadi sekumpulan fungsionalitas yang tervalidasi skemanya, terisolasi secara sandboxed, dan dapat diaudit per invokasi fungsi.

---

### 5. How (Workflow Detail)

Alur kerja eksekusi terdistribusi dari perintah pengguna hingga resolusi tool:

```
[User Input] "Scale deployment auth-service ke 5 replicas di cluster staging"
     |
     v
[Claude Code Engine]
     |-- 1. Evaluasi Intent & Memeriksa Registry Tool Aktif
     |-- 2. Membentuk Argument JSON berdasarkan JSON Schema Tool 'k8s_scale_deployment'
     v
[MCP Client Manager (Local)]
     |-- 3. Membungkus payload ke dalam Frame JSON-RPC 2.0 (Request ID: 0x8F4A)
     |-- 4. Serialisasi dan streaming payload ke 'stdin' child-process Server MCP
     v
[MCP Server (Process Boundary)]
     |-- 5. Read Line Buffer dari 'stdin'
     |-- 6. Deserialisasi JSON & Verifikasi Envelope JSON-RPC
     |-- 7. Schema Validation Engine (Zod/Pydantic)
     |       |--> [Gagal] -> Lempar JSON-RPC Error (-32602: Invalid params)
     |       `--> [Valid] -> Lanjut
     |-- 8. Security & RBAC Guard: Validasi target namespace ('staging' vs 'prod')
     |-- 9. Tool Handler: Eksekusi client SDK resmi (cth: Kubernetes Dynamic Client)
     |-- 10. Sanitasi Output: Sensor rahasia/token sebelum merespons
     |-- 11. Format Envelope Result JSON-RPC 2.0
     `-- 12. Tulis string JSON yang diakhiri newline ('\n') ke 'stdout'
     v
[MCP Client Manager (Local)]
     |-- 13. Parse buffer stream dari 'stdout' Server
     |-- 14. Match Response ID (0x8F4A) dengan Pending Request Map
     v
[Claude Code Engine]
     |-- 15. Injeksi kembalian tool ke Agent Memory / Context Window
     `-- 16. Claude memproses respons final untuk dicetak di CLI pengguna
```

---

### 6. Analogy & Diagram ASCII

#### Analogi Sistem Operasi: Microkernel Device Driver
Bayangkan Claude Code sebagai **Microkernel OS** yang sengaja dibuat minimalis dan terisolasi. Claude Code tidak tahu cara berbicara langsung dengan disk SATA, kartu grafis, atau bus PCI.

- **MCP Server** bertindak sebagai **Device Driver** independen.
- **Tools** adalah antarmuka fungsi I/O yang diekspos driver (`read()`, `write()`, `ioctl()`).
- **Standard I/O Streams (`stdin`/`stdout`)** adalah **System Bus** hardware tempat instruksi ditransmisikan.

Jika driver crash, kernel (Claude Code) tidak ikut mati (*kernel panic*); ia hanya menerima notifikasi kegagalan I/O dan dapat memilih untuk me-restart driver atau memberi tahu user.

```
+-----------------------------------------------------------------------------+
|                                CLAUDE CODE                                  |
|                         (Microkernel Orchestrator)                          |
+-----------------------------------------------------------------------------+
               | stdin/stdout                 | stdin/stdout
               | (PCI Bus 1)                  | (PCI Bus 2)
               v                              v
+-------------------------------+  +------------------------------------------+
|       K8s-MCP Driver          |  |             DB-MCP Driver                |
|  (Tools: Pods, Services, Logs)|  |     (Resources: Schemas, Tools: Query)   |
+-------------------------------+  +------------------------------------------+
               |                              |
               v API Call                     v Native Socket
    +-----------------------+      +------------------------------------------+
    | Kubernetes API Server |      | PostgreSQL Cluster (Read-Replica)        |
    +-----------------------+      +------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: In-Memory Key-Value MCP Server (TypeScript)
Contoh server minimal menggunakan transport `stdio` dan library `@modelcontextprotocol/sdk`.

```typescript
// server-simple.ts
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";

const server = new Server(
  { name: "kv-store-server", version: "1.0.0" },
  { capabilities: { tools: {} } }
);

const storage = new Map<string, string>();

server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: "kv_set",
        description: "Menyimpan nilai string ke memory key-value store",
        inputSchema: {
          type: "object",
          properties: {
            key: { type: "string", description: "Kunci unik data" },
            value: { type: "string", description: "Data teks yang disimpan" },
          },
          required: ["key", "value"],
        },
      },
      {
        name: "kv_get",
        description: "Mengambil nilai string berdasarkan kunci",
        inputSchema: {
          type: "object",
          properties: {
            key: { type: "string", description: "Kunci unik data" },
          },
          required: ["key"],
        },
      },
    ],
  };
});

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  if (name === "kv_set") {
    const { key, value } = args as { key: string; value: string };
    storage.set(key, value);
    return {
      content: [{ type: "text", text: `Success: Key '${key}' berhasil disimpan.` }],
    };
  }

  if (name === "kv_get") {
    const { key } = args as { key: string };
    if (!storage.has(key)) {
      return {
        isError: true,
        content: [{ type: "text", text: `Error: Key '${key}' tidak ditemukan.` }],
      };
    }
    return {
      content: [{ type: "text", text: storage.get(key)! }],
    };
  }

  throw new Error(`Tool tidak dikenali: ${name}`);
});

async function run() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("Simple KV MCP Server berjalan pada stdio.");
}

run().catch((err) => {
  console.error("Fatal error saat inisialisasi server:", err);
  process.exit(1);
});
```

#### B. Practical Example: Enterprise Infrastructure Guard MCP Server (Python)
Server produksi menggunakan Python `mcp` SDK dengan validasi tipe ketat (Pydantic), RBAC Namespace Guard, audit logging ke `stderr`, sanitasi output sensitif, dan penanganan sinyal graceful shutdown.

```python
# infrastructure_guard_server.py
import sys
import os
import signal
import asyncio
import logging
from typing import Any, Dict, List
from pydantic import BaseModel, Field, ValidationError
from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types

# Konfigurasi Structured Logging ke STDERR murni (STDOUT reserved for JSON-RPC)
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [MCP-GUARD] %(message)s"
)
logger = logging.getLogger("InfrastructureGuard")

# Domain Schemas
class ScaleDeploymentArgs(BaseModel):
    namespace: str = Field(..., description="Kubernetes namespace (RBAC Protected)")
    deployment_name: str = Field(..., min_length=3, max_length=63, pattern=r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")
    replicas: int = Field(..., ge=0, le=20, description="Kapasitas replika (Maksimal 20 pada staging)")

class FetchClusterLogsArgs(BaseModel):
    namespace: str
    pod_name: str
    tail_lines: int = Field(default=50, le=500)

app = Server("production-infra-guard")

# RBAC Configuration: Mencegah eksekusi langsung ke namespace non-izinkan
ALLOWED_NAMESPACES = {"staging", "uat", "qa"}

@app.list_tools()
async def handle_list_tools() -> List[types.Tool]:
    return [
        types.Tool(
            name="infra_scale_deployment",
            description="Melakukan scaling Pod replicas Kubernetes pada environment terisolasi.",
            inputSchema=ScaleDeploymentArgs.model_json_schema()
        ),
        types.Tool(
            name="infra_fetch_pod_logs",
            description="Mengambil log runtime dari pod tertentu untuk keperluan troubleshooting.",
            inputSchema=FetchClusterLogsArgs.model_json_schema()
        )
    ]

def sanitize_output(raw_text: str) -> str:
    """Membersihkan sensitive token dari log output sebelum dikirim ke Claude"""
    import re
    # Masking JWT dan Database URL Credentials sederhana
    sanitized = re.sub(r'(ey[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})', '[REDACTED_JWT]', raw_text)
    sanitized = re.sub(r'(postgres(?:ql)?://)([^:]+):([^@]+)@', r'\1\2:[REDACTED_PASSWORD]@', sanitized)
    return sanitized

@app.call_tool()
async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[types.TextContent]:
    logger.info(f"Incoming tool invocation: {name}")
    
    try:
        if name == "infra_scale_deployment":
            validated_args = ScaleDeploymentArgs(**arguments)
            
            # Policy Enforcement Engine
            if validated_args.namespace.lower() not in ALLOWED_NAMESPACES:
                logger.warning(f"RBAC Violation attempt: Namespace '{validated_args.namespace}' diakses.")
                return [types.TextContent(
                    type="text",
                    text=f"SECURITY_POLICY_VIOLATION: Operasi ditolak. Namespace '{validated_args.namespace}' "
                         f"dilindungi. Izin mutlak hanya tersedia untuk: {list(ALLOWED_NAMESPACES)}"
                )]

            # Mock Real Subsystem Interaction (Kubernetes Client)
            logger.info(f"Scaling deployment/{validated_args.deployment_name} to {validated_args.replicas} in {validated_args.namespace}")
            
            return [types.TextContent(
                type="text",
                text=f"SUCCESS: Deployment '{validated_args.deployment_name}' pada namespace '{validated_args.namespace}' "
                     f"berhasil diset ke {validated_args.replicas} replika."
            )]

        elif name == "infra_fetch_pod_logs":
            validated_args = FetchClusterLogsArgs(**arguments)
            raw_mock_logs = (
                f"2026-03-30T10:00:00Z INFO Connecting to database at postgres://app_user:secretPass123@db.staging:5432/orders\n"
                f"2026-03-30T10:00:01Z AUTH Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.e30.t-ae valid\n"
                f"2026-03-30T10:00:02Z INFO Handled {validated_args.tail_lines} batch requests successfully."
            )
            clean_logs = sanitize_output(raw_mock_logs)
            
            return [types.TextContent(type="text", text=clean_logs)]

        else:
            return [types.TextContent(type="text", text=f"ERROR: Tool '{name}' tidak terdaftar.")]

    except ValidationError as ve:
        logger.error(f"Payload validation failed: {ve}")
        return [types.TextContent(type="text", text=f"SCHEMA_VALIDATION_ERROR: {str(ve)}")]
    except Exception as exc:
        logger.critical(f"Internal subsystem failure: {exc}", exc_info=True)
        return [types.TextContent(type="text", text=f"INTERNAL_EXECUTION_FAILURE: {str(exc)}")]

async def main():
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def signal_handler():
        logger.info("Signal termination diterima. Menutup runtime MCP...")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    logger.info("Infrastruktur Guard MCP Server diinisialisasi melalui transport Stdio.")
    
    async with stdio_server() as (read_stream, write_stream):
        server_task = asyncio.create_task(app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        ))
        
        await stop_event.wait()
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            logger.info("Stdio transport loop berhasil dihentikan secara aman.")

if __name__ == "__main__":
    asyncio.run(main())
```

Konfigurasi Claude Code (`~/.claude.json` atau flag konfigurasi proyek):

```json
{
  "mcpServers": {
    "infra-guard": {
      "command": "python3",
      "args": ["/opt/mcp-servers/infrastructure_guard_server.py"],
      "env": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Skenario: Multi-Tenant FinTech Database Migration & Incident Remediation

**Entitas Bisnis**: Platform Pembayaran Global (Skala: 15.000 QPS, 40+ Tim Enjiniring).
**Masalah**: Developer sering memerlukan Claude Code untuk menganalisis log insiden, membaca metrik database relasional, dan mengidentifikasi penyebab *lock contention* pada PostgreSQL. Akses manual via VPN dan psql CLI rentan memicu insiden keamanan (human error mengeksekusi `UPDATE` tanpa klausa `WHERE`, *credential leakage*).

#### Solusi Arsitektur Produksi Berbasis MCP:
Perusahaan membangun sistem **MCP Hub Gateway Terdistribusi**:

```
[Claude Code CLI Developer]
           | (Secure Tunnel / Mutually Authenticated TLS)
           v
[Enterprise MCP Gateway (Reverse Proxy / Envoy)]
           |
   +-------+-------+
   | (Inspect JWT) |
   v               v
[DB-MCP Pod A]   [DB-MCP Pod B] (Kubernetes Stateless Replica)
   | (Dynamic IAM AssumeRole)
   v
[PostgreSQL Read-Only Proxy (PgBouncer)]
   |
   v
[Amazon Aurora PostgreSQL Multi-AZ]
```

1. **Gatekeeper Security**: Gateway memvalidasi identitas engineer melalui identity provider (IdP Okta/OIDC).
2. **Read-Only Enforced AST Parser**: Tool `read_query` di dalam DB-MCP mem-parsing kueri SQL menggunakan Abstract Syntax Tree (AST). Kueri yang mengandung *tokens* `DROP`, `DELETE`, `UPDATE`, `ALTER`, `TRUNCATE` diblokir secara mutlak di layer server sebelum mencapai database, terlepas dari prompt engineering penyerang (*prompt injection immunity*).
3. **Automated Resource Limiting**: Kueri dibatasi oleh *execution deadline* 2.000 ms dan statement timeout ketat, dengan respons maksimum 100 baris record JSON untuk menjaga context window Claude Code tidak mengalami degradasi atensi.
4. **Audit Trail**: Setiap request dicatat ke AWS CloudWatch Logs dan Datadog dengan trace ID yang berkorelasi langsung dengan tiket Jira yang sedang dikerjakan engineer.

---

### 9. Trade-offs

| Pendekatan / Keputusan | Keuntungan (Pros) | Biaya / Konsekuensi (Cons) |
| :--- | :--- | :--- |
| **Transport: `stdio` (Lokal)** | Kecepatan latensi I/O stream sub-milidetik; tidak ada overhead port/firewall networking; isolasi siklus hidup proses otomatis via parent process. | Terikat ke satu host lokal (*machine-bound*); tidak dapat di-share antar node pengembang; scaling horizontal sulit. |
| **Transport: `SSE/HTTP` (Remote)** | Terpusat; mudah di-scale horizontal di Kubernetes; kredensial enterprise tersentralisasi di server cluster, bukan di laptop engineer. | Overhead jaringan HTTP/TLS handshake; latensi serialization/deserialization meningkat (10ms - 50ms); kompleksitas autentikasi via session tokens. |
| **Monolithic MCP Server** | Implementasi sederhana; satu file/repositori menangani puluhan *tools* sekaligus. | *Tool schema bloat* membebani *context window* Claude Code; tingginya risiko ledakan token biaya; kegagalan satu modul dapat mematikan seluruh server. |
| **Micro-MCP Servers (Modular)** | Prinsip *Least Privilege*; skema ramping (*lean context*); isolasi error per domain fungsional. | Kompleksitas orkestrasi; overhead utilisasi memori karena menjalankan banyak subproses/container runtime secara simultan. |
| **Dynamic Tool Pruning** | Menghemat ruang prompt context Claude Code; meningkatkan akurasi *tool selection*. | Membutuhkan layer metadata filter kustom; potensi tool tidak terdeteksi jika metadata pencarian *intent* tidak cocok. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. "Process Transport Closed Unexpectedly" (Buffer Contamination)
- **Gejala**: Claude Code mendadak terputus dari MCP server dengan error parsing JSON-RPC: `SyntaxError: Unexpected token in JSON at position ...`.
- **Akar Masalah**: Terdapat library pihak ketiga atau pemanggilan `print()` / `console.log()` di dalam kode server yang membuang teks non-JSON-RPC langsung ke `stdout`.
- **Solusi**: Alihkan semua logging internal secara mutlak ke `stderr` (`console.error` di TS, `logging.StreamHandler(sys.stderr)` di Python). Jangan gunakan `print()` bawaan tanpa argumen `file=sys.stderr`.

#### 2. Zombie Child Processes pada Stdio Transport
- **Gejala**: Ketika terminal Claude Code di-terminate paksa (SIGKILL / Crash), proses server MCP Python/Node.js tetap menggantung di background OS dan mengunci file/port.
- **Akar Masalah**: Server MCP tidak mengimplementasikan penanganan sinyal `SIGTERM`, `SIGINT`, atau tidak mendeteksi status *Broken Pipe* (`EPIPE`) ketika stream `stdin` klien ditutup.
- **Solusi**: Daftarkan *signal handlers* eksplisit dan pasang listener pada stream close event:
  ```typescript
  process.stdin.on("close", () => {
    logger.info("stdin closed by host, exiting cleanly.");
    process.exit(0);
  });
  ```

#### 3. Context Window Exhaustion akibat Output Tool Raksasa
- **Gejala**: Respons Claude Code menjadi sangat lambat, halusinasi meningkat, atau muncul error: `Context length exceeded`.
- **Akar Masalah**: Server MCP mengembalikan array ribuan baris log mentah atau raw JSON dump tanpa pagination.
- **Solusi**: Implementasikan teknik *truncation* dan *summary-first* di level server. Jika data > 16 KB, simpan ke file lokal sementara atau S3, dan kembalikan MCP Resource URI (misalnya `resource://logs/dump-49102.log`) daripada membuang teks utuh ke dalam payload tool.

---

### 11. Best Practices (Production Checklist)

Gunakan checklist ini sebelum merilis integrasi MCP ke lingkungan staging/production:

- [ ] **Transport Purity**: Verifikasi bahwa stream `stdout` 100% steril dari log debug. Semua jejak log struktural diarahkan ke `stderr`.
- [ ] **Schema Rigidity**: Seluruh skema input/output divalidasi menggunakan validasi berbasis runtime kuat (Pydantic V2 / Zod). Hindari `any` atau `dict` tanpa spesifikasi skema properti.
- [ ] **Least Privilege Scope**: MCP server hanya meminta hak akses read-only secara default. Operasi write/destructive dipisah ke server berbeda atau membutuhkan intervensi konfirmasi eksplisit.
- [ ] **Timeout Enforcement**: Pasang batasan waktu internal pada setiap operasi I/O remote subsystem (DB queries, API calls) dengan maksimum batas waktu eksekusi (rekomendasi: $\le 10$ detik).
- [ ] **Token Truncation / Resource Offloading**: Terapkan limitasi ukuran teks output tool ($\le 4.000$ karakter). Gunakan *Resources* untuk muatan data berukuran masif.
- [ ] **Sanitasi Kredensial Otomatis**: Pasang modul regex interceptor di level serializer untuk menghapus JWT, API Key, dan token privat sebelum frame JSON dikirim kembali ke Claude Code.
- [ ] **Graceful Teardown**: Server mampu membersihkan database connection pool, file lock, dan subprocess ketika menerima sinyal shutdown dari parent.

---

### 12. Hands-on Practice

Buatlah MCP server TypeScript yang bertindak sebagai "Safe File Inspector" untuk Claude Code di direktori latihan Anda.

#### Setup Struktur Proyek
```bash
mkdir -p hands-on/m02/safe-inspector
cd hands-on/m02/safe-inspector
npm init -y
npm install @modelcontextprotocol/sdk zod
npm install -D typescript @types/node tsx
npx tsc --init
```

Konfigurasi `tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "outDir": "./dist",
    "rootDir": "./src",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true
  },
  "include": ["src/**/*"]
}
```

#### Implementasi Source Code
Buat file `src/index.ts`:

```typescript
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { z } from "zod";
import * as fs from "node:fs/promises";
import * as path from "node:path";

const server = new Server(
  {
    name: "safe-file-inspector",
    version: "1.0.0",
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

// Tentukan direktori Sandbox yang diizinkan (CWD project)
const SANDBOX_ROOT = path.resolve(process.cwd());

const InspectFileSchema = z.object({
  relativePath: z.string().describe("Path relatif terhadap root sandbox"),
  maxBytes: z.number().int().positive().max(1024 * 50).default(1024 * 10),
});

server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: "inspect_file_head",
        description: "Membaca bagian awal file secara aman dari sandbox root direktori.",
        inputSchema: {
          type: "object",
          properties: {
            relativePath: {
              type: "string",
              description: "Path relatif file yang akan diinspeksi",
            },
            maxBytes: {
              type: "number",
              description: "Jumlah maksimum byte yang akan dibaca (Max: 51200)",
              default: 10240,
            },
          },
          required: ["relativePath"],
        },
      },
    ],
  };
});

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  if (request.params.name !== "inspect_file_head") {
    throw new Error(`Tool ${request.params.name} tidak dikenali.`);
  }

  try {
    const parsed = InspectFileSchema.parse(request.params.arguments);
    const resolvedPath = path.resolve(SANDBOX_ROOT, parsed.relativePath);

    // Guard Path Traversal Attack
    if (!resolvedPath.startsWith(SANDBOX_ROOT)) {
      process.stderr.write(`[WARN] Path Traversal Attempt Ditolak: ${parsed.relativePath}\n`);
      return {
        isError: true,
        content: [
          {
            type: "text",
            text: "ACCESS_DENIED: Akses di luar direktori sandbox dilarang keras.",
          },
        ],
      };
    }

    const fileHandle = await fs.open(resolvedPath, "r");
    try {
      const buffer = Buffer.alloc(parsed.maxBytes);
      const { bytesRead } = await fileHandle.read(buffer, 0, parsed.maxBytes, 0);
      const fileData = buffer.subarray(0, bytesRead).toString("utf-8");

      return {
        content: [
          {
            type: "text",
            text: fileData.length > 0 ? fileData : "[FILE_EMPTY]",
          },
        ],
      };
    } finally {
      await fileHandle.close();
    }
  } catch (err: any) {
    process.stderr.write(`[ERROR] File inspection error: ${err.message}\n`);
    return {
      isError: true,
      content: [
        {
          type: "text",
          text: `FILE_OPERATION_FAILED: ${err.message}`,
        },
      ],
    };
  }
});

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  process.stderr.write("[INFO] Safe File Inspector MCP Server aktif via stdio.\n");
}

main().catch((err) => {
  process.stderr.write(`[FATAL] Startup failure: ${err}\n`);
  process.exit(1);
});
```

#### Verifikasi Integrasi
1. Compile skrip:
   ```bash
   npx tsc
   ```
2. Hubungkan ke Claude Code dengan menguji file lokal:
   ```bash
   claude --mcp-server "node hands-on/m02/safe-inspector/dist/index.js"
   ```
3. Di dalam interaksi Claude Code CLI, tanyakan:
   > *"Gunakan tool inspect_file_head untuk melihat isi package.json proyek ini."*

---

### 13. Exercise

#### Level: Easy
Modifikasi server pada sesi Hands-on agar menyertakan tool baru bernama `inspect_file_metadata`. Tool ini menerima parameter `relativePath` dan mengembalikan ukuran file (dalam bytes), timestamp `mtime` (modified time), dan boolean apakah file tersebut direktori atau file reguler.

#### Level: Medium
Implementasikan MCP Server berbasis Python yang memvalidasi kueri SQL menggunakan package `sqlparse`. Jika kueri adalah operasi read-only (`SELECT`), server menjalankan kueri ke database SQLite lokal (`app.db`). Jika kueri mengandung token penulisan data (`INSERT`, `UPDATE`, `DELETE`, dsb.), kembalikan error skema JSON-RPC terstruktur tanpa menyentuh database. Pastikan error tersebut tidak me-raise uncaught exception.

#### Level: Hard
Rancang arsitektur MCP Server berbasis Server-Sent Events (SSE) menggunakan Node.js (Express/Fastify) yang mengimplementasikan mekanisme **Session Timeout & In-Flight Request Cancellation**. 
- Ketika klien mengirimkan request HTTP POST untuk pembatalan (`/cancel?requestId=xxx`), Server MCP harus langsung menghentikan *underlying promise execution* (misalnya proses fetch API panjang atau komputasi lokal) menggunakan standard `AbortController`.
- Server harus membersihkan *resource handle* di memory dan mengirimkan frame error JSON-RPC standard code `-32000 (Operation Cancelled)` ke koneksi SSE yang relevan.

---

### 14. Challenge

**Studi Kasus**: Rancang dan bangun spesifikasi teknis untuk sistem **Enterprise Multi-Agent MCP Router (Proxy Gateway)**.

Skenario:
Tim Anda mengelola 12 server MCP terpisah (Kubernetes, AWS CloudWatch, Datadog, GitHub, Postgres Analytics, Redis Commander, Jira, Slack, PagerDuty, Vault, ArgoCD, Kafka Inspector). Masing-masing server mengekspos rata-rata 8 tools. Jika semua diekspos sekaligus ke Claude Code:
1. Skema total memakan lebih dari 65.000 token konteks pada sistem prompt awal Claude Code.
2. Latensi inferensi meningkat drastis ($> 4$ detik *time-to-first-token*).
3. Terjadi halusinasi pemilihan alat (*tool misrouting*) hingga 22% pada instruksi kompleks.

**Spesifikasi Tugas**:
Rancang arsitektur sistem gateway perantara (Gateway Server) yang mengimplementasikan:
1. **Dynamic Tool Indexing**: Sistem registri yang mengindeks deskripsi fungsionalitas seluruh server downstream ke dalam vector space ringan atau keyword router lokal.
2. **Intent-Driven Tool Pruning**: Ketika Claude Code memulai task, Gateway hanya mengekspos satu meta-tool awal: `search_relevant_tools(task_intent: string)`. Setelah Claude Code menentukan sub-domain operasi, gateway melakukan injeksi dinamis tools yang relevan saja ke dalam sesi aktif secara dinamis (`notifications/tools/list_changed`).
3. **Unified Circuit Breaker & Failover**: Jika salah satu downstream MCP server mati (misalnya pod Datadog crash), gateway harus merespons fallback gracefully tanpa mematikan sesi Claude Code.
4. **Stateful Session Isolation**: Setiap engineer yang menjalankan Claude Code CLI harus mendapatkan runtime instance yang terisolasi dengan zero cross-talk antar engineer.

Tuliskan arsitektur desain (diagram ASCII), spesifikasi JSON-RPC payload kustom, dan draft implementasi core routing logic-nya!

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Soal)
1. Apa format protokol serialisasi baku yang digunakan oleh spesifikasi resmi Model Context Protocol?
2. Mengapa penulisan log debugging via `console.log()` atau `print()` standar menyebabkan crash pada MCP server berbasis transport `stdio`?
3. Sebutkan tiga entitas abstraksi data/fungsi utama yang dapat diekspos oleh MCP Server ke MCP Client!
4. Notification frame pada JSON-RPC 2.0 memiliki ciri struktural pembeda dibandingkan Request frame. Apakah ciri tersebut?
5. Apa peran file descriptor `stderr` dalam arsitektur proses MCP transport `stdio`?

#### Intermediate (5 Soal)
6. Jelaskan urutan handshake (*state machine*) negosiasi inisialisasi antara Claude Code (Client) dan Server MCP dari status koneksi pertama hingga siap menerima perintah eksekusi!
7. Bagaimana arsitektur SSE pada MCP mengatasi limitasi transport `stdio` yang bersifat *single-machine bound*?
8. Apa yang terjadi jika Server MCP mengembalikan field `isError: true` di dalam result payload dibandingkan me-raise exception di tingkat JSON-RPC error frame (`error: { code, message }`)?
9. Bagaimana strategi mitigasi risiko keamanan *Prompt Injection* ketika Claude Code mengeksekusi parameter arbitrary pada MCP tool yang terhubung langsung ke remote shell?
10. Mengapa skema parameter input MCP tool wajib didefinisikan menggunakan standard JSON Schema draft-07 atau kompatibel?

#### Production Scenarios (3 Soal)
11. **Skenario 1**: Sebuah tim enjiniring memasang MCP Server kustom untuk deployment Kubernetes. Tiba-tiba terminal Claude Code hang selama 120 detik, kemudian keluar dengan status *Timeout ETIMEDOUT* tanpa jejak log apa pun di CLI. Langkah diagnosis sistematis apa yang harus Anda lakukan pada arsitektur MCP untuk menemukan root cause?
12. **Skenario 2**: Anda mengintegrasikan MCP Server Postgres ke Claude Code. Salah satu tabel produksi memiliki 10.000.000 baris. Saat engineer mengetik *"Analisis tabel transaksi hari ini"*, Claude Code langsung mengalami error *out-of-memory* (OOM) dan crash. Di layer arsitektur manakah kegagalan ini harus diselesaikan dan bagaimana kodenya dirancang?
13. **Skenario 3**: Perusahaan Anda mewajibkan implementasi arsitektur *Zero-Trust*. Developer tidak boleh memiliki AWS credentials langsung di laptop mereka, namun Claude Code di laptop mereka harus bisa memeriksa status AWS Lambda di AWS GovCloud. Rancang topologi transport dan autentikasi MCP yang memenuhi restriksi ini!

---

#### Kunci Jawaban & Panduan Solusi Quiz

##### Basic
1. **JSON-RPC 2.0**.
2. Karena transport `stdio` menggunakan stream `stdout` khusus untuk frame JSON-RPC. Teks mentah non-JSON merusak stream parser klien, memicu `JSON parse error`, dan memutus koneksi proses.
3. **Tools** (fungsi eksekusi dengan side-effects), **Resources** (data/file mirip skema URI, read-mostly), dan **Prompts** (template prompt kontekstual pra-konfigurasi).
4. Notification frame **tidak memiliki field `"id"`**, menandakan klien/server tidak mengharapkan respons balik (*one-way execution*).
5. `stderr` digunakan khusus sebagai saluran log diagnostik, jejak audit, dan debugging manusia tanpa mengganggu aliran protokol serial pada `stdout`.

##### Intermediate
6. Client mengirim `initialize` (capabilities negosiasi) $\rightarrow$ Server membalas `initialize` result (capabilities server) $\rightarrow$ Client mengirim notifikasi `notifications/initialized` $\rightarrow$ Koneksi beralih ke state RUNNING $\rightarrow$ Discovery tools/resources dapat dieksekusi.
7. SSE memisahkan jalur data: Client menerima downstream event stream via standard HTTP GET `/sse`, dan mengirim upstream requests melalui HTTP POST `/messages`. Hal ini memungkinkan server berjalan di remote Kubernetes pod/serverless di balik Reverse Proxy/Ingress TLS.
8. `isError: true` menandakan tool *berhasil dieksekusi oleh engine MCP*, namun logika bisnis operasi tersebut gagal (contoh: *file not found* atau *query syntax error*). Pesan ini diinjeksikan langsung ke context window agar LLM dapat melakukan self-correction. Sebaliknya, JSON-RPC level error (`code: -32xxx`) menandakan kegagalan layer transport/infrastruktur protokol (misal: parse error, invalid request method) yang mematikan pemrosesan pesan tersebut.
9. Dengan melakukan validasi parameter ketat via runtime validator (Zod/Pydantic), menerapkan *whitelisting* karakter alfanumerik, menghindari *raw string concatenation* pada shell command execution, dan menjalankan proses di dalam sandbox terisolasi (gVisor/Docker tanpa hak root).
10. Agar LLM dapat membaca deskripsi parameter, tipe tipe data, batasan validasi (`minimum`, `maximum`, `regex pattern`), dan field wajib secara deterministik untuk memandu proses *function-calling inference*.

##### Production Scenarios
11. **Diagnosis Langkah**:
    - Periksa apakah subproses MCP server masih hidup (`ps aux | grep mcp`).
    - Cek output stream log `stderr` dari MCP server untuk melihat apakah ada *blocking network call* tanpa konfigurasi timeout.
    - Uji Server MCP secara mandiri menggunakan mock JSON-RPC payload via command line `cat test-payload.json | python3 my_server.py`.
    - Pastikan transport client manager pada konfigurasi Claude Code memiliki konfigurasi `requestTimeout` yang terdefinisi.
12. **Solusi Masalah**:
    - Kegagalan diselesaikan di **Tool Handler Server MCP**.
    - Server dilarang melakukan `SELECT *` tanpa batas. Pasang klausul limit paksa (misal: `LIMIT 100`), sanitasi schema kolom, serta kirimkan data agregat/statistik distribusi alih-alih data baris mentah.
    - Terapkan skema *Resource Paging* dengan metadata cursor (`nextCursor`) untuk pengambilan bertahap.
13. **Topologi Zero-Trust**:
    - Claude Code dikonfigurasi menggunakan **SSE Transport Client** yang terhubung ke **Centralized Remote MCP Gateway** di dalam AWS VPC via PrivateLink atau Tailscale/WireGuard VPN.
    - Kredensial AWS (IAM Role) di-assign ke pod Gateway di Kubernetes via EKS Pod Identity / IRSA (tidak ada AWS keys di laptop engineer).
    - Laptop engineer hanya menyimpan token sesi mTLS / OIDC short-lived untuk autentikasi ke Gateway MCP. Gateway mengesahkan identitas sebelum mem-proxy instruksi ke AWS SDK.

---

### 16. Summary

- **Model Context Protocol (MCP)** mengubah integrasi ad-hoc LLM menjadi arsitektur berbasis protokol standar terbuka (JSON-RPC 2.0), memisahkan runtime reasoning (Claude Code) dari layer eksekusi tools dan resources.
- Komunikasi lokal memanfaatkan kestabilan dan latensi rendah dari **stdio transport**, yang mewajibkan isolasi total logging ke saluran **`stderr`** untuk menjaga validitas frame parsing.
- Implementasi kelas produksi menuntut validasi skema parameter deklaratif berbasis **Pydantic / Zod**, pembatasan akses berbasis kebijakan (**RBAC**), mekanisme **output sanitization**, dan pengelolaan siklus hidup proses (**signal traps & cleanup hooks**).
- Untuk skala enterprise, arsitektur MCP berevolusi dari skrip lokal tunggal menuju **Remote Gateway terpusat** dengan proteksi *context window* melalui teknik *Dynamic Tool Pruning* dan audit trail terpadu.