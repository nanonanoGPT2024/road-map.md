# Bab 03: Tool Use, Actions, & Model Context Protocol (MCP)

## 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
*   **Menganalisis & Merancang Schema Tool:** Mengonstruksi schema pemanggilan fungsi (*function calling*) berbasis JSON Schema standar yang deterministik, lengkap dengan validasi tipe data ketat dan parameter *fail-safe*.
*   **Mengimplementasikan Arsitektur Tool Router Produksi:** Membangun *agentic tool-execution loop* yang menangani siklus hidup eksekusi aksi (resolusi fungsi, validasi argumen, eksekusi paralel/serial, dan injeksi observasi ke konteks).
*   **Mengadopsi Standar Model Context Protocol (MCP):** Mengimplementasikan arsitektur *MCP Client* dan *MCP Server* berbasis JSON-RPC 2.0 menggunakan transport `stdio` dan `Server-Sent Events (SSE)` untuk memisahkan logika orkestrasi dari integrasi data.
*   **Memitigasi Vektor Serangan Tool Use:** Menerapkan strategi pertahanan terhadap *Indirect Prompt Injection*, *Data Exfiltration*, dan *Parameter Tampering* yang berasal dari eksekusi tool eksternal.
*   **Mendesain Mekanisme Self-Healing:** Mengembangkan logika pemulihan otomatis saat LLM mengalami *schema hallucination*, *invalid argument types*, atau *tool runtime exceptions*.

---

## 2. Concept Overview
Secara fundamental, Large Language Models (LLM) adalah mesin inferensi statistik berbasis teks yang terisolasi (*air-gapped* dari *state* eksternal). Model tidak memiliki kapabilitas bawaan untuk membaca basis data produksi, mengeksekusi kode, atau mengubah *state* sistem.

```
       Tanpa Tool Use:
       [User] ---> (LLM: "Pengetahuan terisolasi hingga cutoff date")
       
       Dengan Tool Use & Actions:
       [User] ---> (LLM) ---> [Aksi Terstruktur] ---> [Runtime Engine] ---> [API / DB]
                     ^                                      |
                     |-------- [Observasi / State] <--------|
```

### Mental Model: LLM sebagai Central Processing Unit (CPU)
Untuk memahami *Tool Use*, gunakan analogi komputasi sistem:
*   **LLM** adalah **CPU**. Tugasnya bukan menyimpan seluruh data dunia, melainkan melakukan pemrosesan logis, perencanaan, dan orkestrasi instruksi.
*   **Konteks (Context Window)** adalah **RAM**. Kapasitasnya terbatas, *volatile*, dan membutuhkan alokasi yang efisien.
*   **Tools/Actions** adalah **Instruksi I/O Bus & Peripheral Devices** (Disk, Network Card, GPU). LLM mengeluarkan instruksi I/O melalui spesifikasi terstruktur, dan *runtime driver* yang mengeksekusi instruksi tersebut di sistem fisik.
*   **Model Context Protocol (MCP)** adalah **POSIX / PCI Express Standard** untuk AI. Sebelum MCP, setiap *agent framework* membuat format integrasi periferal kustom yang terfragmentasi ($N$ model $\times$ $M$ tool = integrasi spaghetti). MCP menstandarisasi bagaimana Host/Client mengekspos *Resources*, *Prompts*, dan *Tools* ke LLM melalui protokol RPC terpadu.

### Paradigma: ReAct vs. Native Function Calling vs. Protocol-Driven (MCP)
1.  **ReAct (Reason + Act):** Mengandalkan rekayasa *prompt* murni di mana LLM memuntahkan teks bebas berpola (misal: `Thought: ... Action: ... Action Input: ...`). Pendekatan ini rapuh (*brittle*), rentan terhadap kegagalan *parsing* regex, dan memboroskan token.
2.  **Native Function Calling:** Model di-*fine-tune* secara khusus (pada lapisan representasi bobot) untuk mengenali tag khusus tool dan menghasilkan payload JSON valid yang memetakan langsung ke antarmuka pemrograman aplikasi (API).
3.  **Model Context Protocol (MCP):** Standar terbuka yang diperkenalkan oleh Anthropic untuk memformalkan *tool use*, abstraksi *read-only context* (Resources), dan *prompt templates* menjadi sebuah protokol client-server dua arah (*bidirectional*) di atas JSON-RPC 2.0.

---

## 3. Why It Matters
Integrasi tool langsung yang ditulis secara ad-hoc (*hardcoded functions*) memiliki skalabilitas nol di level enterprise.

```
Masalah Fragmentasi Integrasi Tradisional:
[Agent A] ---> Custom Driver ---> [PostgreSQL]
          ---> Custom Driver ---> [Slack API]
[Agent B] ---> Custom Driver ---> [PostgreSQL] (Duplikasi Integrasi)
          ---> Custom Driver ---> [GitLab API]
Kompleksitas: O(N * M)

Pendekatan Standar Model Context Protocol (MCP):
[Agent A] ----\
[Agent B] -----> [MCP Client] <=== JSON-RPC ===> [MCP Server: PostgreSQL]
[Agent C] ----/                                  [MCP Server: GitHub/GitLab]
Kompleksitas: O(N + M)
```

1.  **Eliminasi "Integration Tax":** Arsitektur enterprise memiliki ribuan titik akhir API. Membangun dan memelihara wrapper JSON schema manual untuk setiap agen menghasilkan redundansi kode masif. MCP memisahkan *server penyedia kapabilitas* dari *agent penyedia orkestrasi*.
2.  **Boundary Keamanan & Tata Kelola Data:** Tool execution mengekspos sistem ke risiko eksekusi *arbitrary code* atau *unintended write operations*. Dengan protokol standar, kontrol akses berbasis peran (RBAC), *rate-limiting*, audit logging, dan mekanisme *Human-in-the-Loop* (HITL) dapat ditempatkan di lapisan proxy transportasi secara konsisten.
3.  **Isolasi Konteks Dinamis:** LLM enterprise tidak boleh dibebani dengan *entire schema* dari seluruh sistem sekaligus. Protokol kontekstual memungkinkan *discovery* tool dan sumber daya secara dinamis sesuai kebutuhan sesi kerja aktif.

---

## 4. Arsitektur & Diagram Komponen

Diagram berikut merepresentasikan siklus hidup eksekusi tool modern menggunakan standar MCP dengan host runtime enterprise:

```
+---------------------------------------------------------------------------------------------------+
| HOST APPLICATION (e.g., Agent Core Engine)                                                        |
|                                                                                                   |
|  +---------------------+        +--------------------+        +-------------------------------+   |
|  | Context Orchestrator|<------>| Context Memory/RAM |        | Security / Guardrails Layer   |   |
|  +---------------------+        +--------------------+        | - Parameter Sanitation        |   |
|            |                                                  | - RBAC Policy Engine          |   |
|            v                                                  +-------------------------------+   |
|  +---------------------------------------------------+                        ^                   |
|  | LLM Client (Inference Engine: Anthropic / OpenAI) |                        |                   |
|  +---------------------------------------------------+                        |                   |
|            |                                                                  |                   |
|   1. Emit Tool Call (JSON)                                                    |                   |
|            v                                                                  |                   |
|  +---------------------------------------------------+                        |                   |
|  | MCP Client Manager                                |                        |                   |
|  | - Transport Router (Stdio / SSE)                  |                        |                   |
|  | - Capability Negotiator                           |------------------------+                   |
|  +---------------------------------------------------+                                            |
+------------|--------------------------------------------------------------------------------------+
             |
             |  2. JSON-RPC 2.0 Request: "tools/call" over Stdio or SSE
             v
+---------------------------------------------------------------------------------------------------+
| MCP SERVER SUBSYSTEM (Sandboxed Context)                                                          |
|                                                                                                   |
|  +---------------------------------------------------+                                            |
|  | JSON-RPC Transport Layer                          |                                            |
|  +---------------------------------------------------+                                            |
|            |                                                                                      |
|            v                                                                                      |
|  +---------------------------------------------------+                                            |
|  | Protocol Dispatcher                               |                                            |
|  | - Request Router: tools/list, tools/call          |                                            |
|  +---------------------------------------------------+                                            |
|            |                                                                                      |
|            v                                                                                      |
|  +---------------------------------------------------+        +-------------------------------+   |
|  | Tool Execution Engine                             |------->| Downstream Infrastructure     |   |
|  | - Schema Validator (Pydantic / Zod)              |        | - Production Databases (SQL)  |   |
|  | - Execution Sandbox                               |        | - External Microservices      |   |
|  | - Error Boundary & Circuit Breaker                |        | - Local File Systems          |   |
|  +---------------------------------------------------+        +-------------------------------+   |
+---------------------------------------------------------------------------------------------------+
```

### Alur Eksekusi Data (Data Flow):
1. **Tool Discovery:** Saat startup, `MCP Client` mengirim pesan JSON-RPC `tools/list` ke `MCP Server`. Server merespons dengan daftar definisi tool dan JSON Schema parameter yang didukung.
2. **Context Injection:** `Host Application` memetakan schema tool MCP ke format native pemanggilan fungsi LLM yang sedang digunakan (misal: OpenAI Function format atau Anthropic Tool format).
3. **Model Inference:** User mengirim query $\to$ LLM menentukan bahwa data eksternal diperlukan $\to$ LLM menghasilkan output dengan *stop reason* `tool_use`, berisikan `tool_name` dan `arguments` (JSON).
4. **Transport & Execution:** `MCP Client` memvalidasi izin eksekusi $\to$ mengirim pesan JSON-RPC `tools/call` melalui transport yang ditentukan (`stdio` untuk integrasi lokal, `SSE` untuk remote network) $\to$ `MCP Server` mengeksekusi operasi ke database/API.
5. **Observation Return:** `MCP Server` mengembalikan hasil dalam format standar (`content: [{type: "text", text: "..."}]`) $\to$ Host membungkus hasil tersebut sebagai pesan dengan *role* `tool` $\to$ LLM membaca kembali hasil eksekusi untuk menghasilkan jawaban akhir ke user.

---

## 5. Deep Dive Mekanisme & Prinsip Kerja

### 5.1 Mekanisme JSON Schema Translation & Validation
Ketika tool didefinisikan dalam kode (misal via Pydantic di Python), runtime harus mengonversi model tipe data bahasa pemrograman ke spesifikasi **JSON Schema Draft 7 / 2020-12**.

LLM tidak mengeksekusi kode Python Anda; model hanya membaca representasi string dari JSON Schema ini. Kompleksitas schema berkorelasi langsung dengan tingkat akurasi inferensi:
*   Parameter opsional harus memiliki nilai `default` yang eksplisit.
*   Deskripsi teks (`description`) bukan sekadar dokumentasi pengembang, melainkan **instruksi operasional model**. Kualitas deskripsi menentukan apakah model memilih tool tersebut (*routing accuracy*) dan memahami batasan nilai argumen.

### 5.2 Anatomi Protokol MCP (Model Context Protocol)
MCP menggunakan standar **JSON-RPC 2.0** yang *stateful* atau *stateless* tergantung transport. Protokol ini memiliki 3 primitif inti:
1.  **Prompts:** Template prompt interaktif yang dikontrol oleh server untuk memandu alur kerja user/model.
2.  **Resources:** Data pasif berbasis URI (*read-only context*) seperti file, log, skema database (mirip endpoint `GET`).
3.  **Tools:** Fungsi komputasi aktif yang dapat mengubah *state* (*read/write actions*, mirip endpoint `POST/PUT`).

#### Contoh Payload Pertukaran JSON-RPC 2.0 MCP:
*Request tools/call dari Client ke Server:*
```json
{
  "jsonrpc": "2.0",
  "id": "uuid-req-001",
  "method": "tools/call",
  "params": {
    "name": "execute_database_query",
    "arguments": {
      "query": "SELECT user_id, email, status FROM users WHERE status = 'suspended' LIMIT 5;",
      "read_only": true
    }
  }
}
```

*Response sukses dari Server ke Client:*
```json
{
  "jsonrpc": "2.0",
  "id": "uuid-req-001",
  "result": {
    "content": [
      {
        "type": "text",
        "text": "[{\"user_id\": 102, \"email\": \"bad_actor@domain.com\", \"status\": \"suspended\"}]"
      }
    ],
    "isError": false
  }
}
```

### 5.3 Transport Layer: Stdio vs. Server-Sent Events (SSE)
*   **Stdio (Standard Input/Output):** Digunakan ketika Host Application menjalankan proses MCP Server sebagai sub-proses (*child process*) lokal. Sangat aman secara isolasi jaringan karena tidak ada port lokal yang dibuka, tetapi terbatas pada lingkungan mesin yang sama.
*   **SSE (Server-Sent Events) + HTTP Post:** Digunakan untuk skenario terdistribusi/enterprise. Client membuka koneksi HTTP persistent via SSE untuk menerima stream pesan dari server, dan mengirimkan pesan balik ke server menggunakan endpoint HTTP POST konvensional.

---

## 6. Production-Ready Code Implementation

Berikut adalah implementasi menyeluruh dalam Python murni (berstandar modern 3.11+) yang mencakup:
1. Arsitektur **MCP-Compliant Server Engine** yang menangani protokol JSON-RPC 2.0, registrasi tool, validasi JSON Schema melalui Pydantic v2, kontrol batas eksekusi (timeout), dan mitigasi prompt injection dasar.
2. **Agentic Tool Router** yang mengelola siklus panggilan fungsi model dan penanganan kegagalan eksekusi.

```python
"""
Enterprise-Grade MCP Server & Tool Execution Engine
Production-ready, type-hinted, zero extraneous dependencies beyond pydantic.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import re
import sys
import traceback
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional, Type, get_type_hints
from pydantic import BaseModel, Field, ValidationError, create_model

# ---------------------------------------------------------------------------
# Logging & Telemetry Configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(name)s) %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger("mcp.runtime")


# ---------------------------------------------------------------------------
# Security & Sanitization Primitives
# ---------------------------------------------------------------------------
class SecurityViolationError(Exception):
    """Dilempar saat tool call melanggar batasan keamanan atau mendeteksi injeksi."""
    pass


class PayloadSanitizer:
    """Mendeteksi dan menetralisir potensi Indirect Prompt Injection pada payload tool."""
    
    # Deteksi pola injeksi instruksi sistem di dalam output payload eksternal
    INJECTION_PATTERNS = [
        re.compile(r"ignore\s+(all\s+)?prior\s+instructions", re.IGNORECASE),
        re.compile(r"system\s*:\s*you\s+are\s+now", re.IGNORECASE),
        re.compile(r"<\s*im_start\s*>", re.IGNORECASE),
        re.compile(r"###\s*Instruction", re.IGNORECASE),
    ]

    @classmethod
    def sanitize_output(cls, raw_content: str) -> str:
        for pattern in cls.INJECTION_PATTERNS:
            if pattern.search(raw_content):
                logger.warning("Indirect Prompt Injection attempt detected in tool execution payload!")
                return (
                    "[SECURITY WARNING: Tool output contained suspicious instruction-like patterns "
                    "which were redacted to prevent context manipulation.]"
                )
        return raw_content


# ---------------------------------------------------------------------------
# MCP Protocol Models (JSON-RPC 2.0 Compliant)
# ---------------------------------------------------------------------------
class JSONRPCRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: str | int
    method: str
    params: Optional[Dict[str, Any]] = None


class JSONRPCError(BaseModel):
    code: int
    message: str
    data: Optional[Any] = None


class JSONRPCResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[str | int] = None
    result: Optional[Any] = None
    error: Optional[JSONRPCError] = None


class MCPToolDefinition(BaseModel):
    name: str
    description: str
    inputSchema: Dict[str, Any]


# ---------------------------------------------------------------------------
# Tool Core Framework: Definitions, Schemas, & Decorators
# ---------------------------------------------------------------------------
@dataclass
class ToolMetadata:
    name: str
    description: str
    schema_model: Type[BaseModel]
    handler: Callable[..., Awaitable[Any]]
    timeout_seconds: float


class ToolRegistry:
    """Registry tersentralisasi untuk pendaftaran dan resolusi instan tool."""
    
    def __init__(self) -> None:
        self._tools: Dict[str, ToolMetadata] = {}

    def register(self, name: str, description: str, timeout_seconds: float = 30.0):
        def decorator(func: Callable[..., Awaitable[Any]]):
            sig = inspect.signature(func)
            type_hints = get_type_hints(func)
            
            fields: Dict[str, Any] = {}
            for param_name, param in sig.parameters.items():
                if param_name in ("self", "cls"):
                    continue
                param_type = type_hints.get(param_name, Any)
                default_val = ... if param.default == inspect.Parameter.empty else param.default
                fields[param_name] = (param_type, default_val)
            
            # Dinamis membentuk skema Pydantic v2 untuk fungsi
            pydantic_model = create_model(f"{name}_InputSchema", **fields)
            
            self._tools[name] = ToolMetadata(
                name=name,
                description=description.strip(),
                schema_model=pydantic_model,
                handler=func,
                timeout_seconds=timeout_seconds,
            )
            return func
        return decorator

    def get_tool(self, name: str) -> Optional[ToolMetadata]:
        return self._tools.get(name)

    def list_tools(self) -> List[MCPToolDefinition]:
        definitions = []
        for tool in self._tools.values():
            schema = tool.schema_model.model_json_schema()
            # Bersihkan metadata internal Pydantic yang tidak esensial bagi LLM
            schema.pop("title", None)
            definitions.append(
                MCPToolDefinition(
                    name=tool.name,
                    description=tool.description,
                    inputSchema=schema,
                )
            )
        return definitions


# ---------------------------------------------------------------------------
# MCP Server Implementation
# ---------------------------------------------------------------------------
class MCPServer:
    """Implementasi server mandiri berbasis MCP JSON-RPC 2.0."""

    def __init__(self, registry: ToolRegistry, server_name: str = "Enterprise-Core-MCP"):
        self.registry = registry
        self.server_name = server_name

    async def handle_request(self, request_raw: str) -> str:
        """Entry point pemrosesan transaksi protokol JSON-RPC 2.0."""
        try:
            payload = json.loads(request_raw)
            request = JSONRPCRequest.model_validate(payload)
        except (json.JSONDecodeError, ValidationError) as e:
            err_response = JSONRPCResponse(
                id=None,
                error=JSONRPCError(code=-32700, message="Parse error / Invalid JSON-RPC Request", data=str(e)),
            )
            return err_response.model_dump_json()

        try:
            if request.method == "initialize":
                response = await self._handle_initialize(request)
            elif request.method == "tools/list":
                response = await self._handle_tools_list(request)
            elif request.method == "tools/call":
                response = await self._handle_tools_call(request)
            else:
                response = JSONRPCResponse(
                    id=request.id,
                    error=JSONRPCError(code=-32601, message=f"Method '{request.method}' not found."),
                )
        except Exception as unhandled_err:
            logger.error("Unhandled error processing request: %s\n%s", unhandled_err, traceback.format_exc())
            response = JSONRPCResponse(
                id=request.id,
                error=JSONRPCError(code=-32603, message="Internal Server Error", data=str(unhandled_err)),
            )

        return response.model_dump_json()

    async def _handle_initialize(self, request: JSONRPCRequest) -> JSONRPCResponse:
        return JSONRPCResponse(
            id=request.id,
            result={
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {"listChanged": False}
                },
                "serverInfo": {
                    "name": self.server_name,
                    "version": "1.0.0"
                }
            }
        )

    async def _handle_tools_list(self, request: JSONRPCRequest) -> JSONRPCResponse:
        tools = self.registry.list_tools()
        return JSONRPCResponse(
            id=request.id,
            result={"tools": [t.model_dump() for t in tools]}
        )

    async def _handle_tools_call(self, request: JSONRPCRequest) -> JSONRPCResponse:
        params = request.params or {}
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if not tool_name:
            return JSONRPCResponse(
                id=request.id,
                error=JSONRPCError(code=-32602, message="Invalid params: Missing tool name"),
            )

        tool = self.registry.get_tool(tool_name)
        if not tool:
            return JSONRPCResponse(
                id=request.id,
                error=JSONRPCError(code=-32601, message=f"Tool '{tool_name}' is not registered."),
            )

        # 1. Validasi Argumen via Pydantic Model
        try:
            validated_args = tool.schema_model.model_validate(arguments)
        except ValidationError as val_err:
            logger.warning("Tool parameter validation failed for '%s': %s", tool_name, val_err)
            return JSONRPCResponse(
                id=request.id,
                result={
                    "content": [{"type": "text", "text": f"Schema Validation Error: {val_err.errors()}"}],
                    "isError": True
                }
            )

        # 2. Eksekusi Sandboxed dengan Circuit Breaker / Timeout
        try:
            async with asyncio.timeout(tool.timeout_seconds):
                raw_result = await tool.handler(**validated_args.model_dump())
            
            # Serialisasi keluaran
            if not isinstance(raw_result, str):
                raw_result = json.dumps(raw_result, default=str)

            # 3. Sanitasi Output untuk mencegah Prompt Injection
            sanitized_result = PayloadSanitizer.sanitize_output(raw_result)

            return JSONRPCResponse(
                id=request.id,
                result={
                    "content": [{"type": "text", "text": sanitized_result}],
                    "isError": False
                }
            )
        except asyncio.TimeoutError:
            logger.error("Execution timeout hit on tool '%s' (%ds)", tool_name, tool.timeout_seconds)
            return JSONRPCResponse(
                id=request.id,
                result={
                    "content": [{"type": "text", "text": f"Execution Timed Out ({tool.timeout_seconds}s limit)."}],
                    "isError": True
                }
            )
        except Exception as exec_err:
            logger.error("Runtime exception inside tool '%s': %s", tool_name, exec_err)
            return JSONRPCResponse(
                id=request.id,
                result={
                    "content": [{"type": "text", "text": f"Runtime Exception: {str(exec_err)}"}],
                    "isError": True
                }
            )


# ---------------------------------------------------------------------------
# Tool Implementations (Enterprise Banking System Domain)
# ---------------------------------------------------------------------------
registry = ToolRegistry()

@registry.register(
    name="get_account_balance",
    description="Mengambil saldo kas rekening pelanggan berdasarkan ID rekening. Gunakan hanya untuk mode baca.",
    timeout_seconds=5.0
)
async def get_account_balance(account_id: str, include_pending: bool = False) -> Dict[str, Any]:
    # Mocking read-only enterprise query
    if not account_id.startswith("ACC-"):
        raise ValueError("Format account_id tidak valid. Harus diawali dengan 'ACC-'.")
    
    return {
        "account_id": account_id,
        "currency": "IDR",
        "available_balance": 150000000.00,
        "pending_balance": 5000000.00 if include_pending else 0.0,
        "status": "ACTIVE"
    }

@registry.register(
    name="freeze_account",
    description="Tindakan administratif berisiko tinggi untuk membekukan rekening nasabah karena indikasi fraud.",
    timeout_seconds=10.0
)
async def freeze_account(account_id: str, reason: str, authorized_by: str) -> Dict[str, Any]:
    if len(reason) < 15:
        raise ValueError("Alasan pembekuan (reason) harus jelas dan minimal 15 karakter untuk audit.")
    
    return {
        "account_id": account_id,
        "previous_status": "ACTIVE",
        "new_status": "FROZEN",
        "audit_ticket": "AUD-998821",
        "authorized_by": authorized_by
    }


# ---------------------------------------------------------------------------
# Client/Host Orchestration Loop Demo
# ---------------------------------------------------------------------------
async def main():
    server = MCPServer(registry=registry)
    
    print("=== 1. PROTOCOL INITIALIZATION ===")
    init_request = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    init_response = await server.handle_request(init_request)
    print(f"Server Initialized:\n{json.dumps(json.loads(init_response), indent=2)}\n")

    print("=== 2. TOOL DISCOVERY (tools/list) ===")
    list_request = json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    list_response = await server.handle_request(list_request)
    print(f"Available Tools Exported to Model:\n{json.dumps(json.loads(list_response), indent=2)}\n")

    print("=== 3. TOOL EXECUTION SUCCESS (tools/call) ===")
    call_request = json.dumps({
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "get_account_balance",
            "arguments": {"account_id": "ACC-54129", "include_pending": True}
        }
    })
    call_response = await server.handle_request(call_request)
    print(f"Tool Call Response:\n{json.dumps(json.loads(call_response), indent=2)}\n")

    print("=== 4. EDGE CASE: INVALID SCHEMA RECOVERY ===")
    bad_call_request = json.dumps({
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "get_account_balance",
            "arguments": {"account_id": "INVALID-FORMAT"}  # Gagal validasi internal domain
        }
    })
    bad_response = await server.handle_request(bad_call_request)
    print(f"Tool Call Failure Feedback (Self-Healing Context):\n{json.dumps(json.loads(bad_response), indent=2)}\n")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 7. Edge Cases & Failure Modes

| Skenario Kegagalan | Penyebab Teknis Utama | Dampak pada Agen | Mitigasi Arsitektural Defensif |
| :--- | :--- | :--- | :--- |
| **Schema Hallucination** | LLM menghasilkan key parameter yang tidak didefinisikan pada JSON Schema. | `ValidationError` pada layer deserialisasi server. | Tangkap error validasi, transformasikan pesan ke format ramah LLM, injeksikan balik ke riwayat pesan agar model melakukan *retry*. |
| **Context Payload Explosion** | Tool mengembalikan payload raksasa (misal: query `SELECT *` mengembalikan 50.000 baris JSON). | *Context window exhaustion*, latensi inferensi ekstrem, lonjakan biaya token drastis. | Terapkan *hard-limit* pemotongan panjang teks (misal: max 10.000 karakter), wajibkan paginasi di schema (`limit`, `offset`), atau simpan ke Resource MCP dengan URI acuan. |
| **Indirect Prompt Injection** | Data luar (web scraping, email, dokumen pengguna) memuat instruksi manipulasi sistem tersembunyi. | *Agent hijacking*, LLM mengabaikan batasan sistem dan mengeksekusi aksi destruktif. | Pisahkan channel eksekusi data mentah dari instruksi sistem; lakukan regex/heuristic scanning pada output tool sebelum masuk ke konteks. |
| **Infinite Tool Recursion** | Model memanggil tool yang sama terus-menerus karena output tidak menyelesaikan masalah secara mutlak. | Agen terkunci (*hang*), kuota API terdisrupsi, pemborosan komputasi. | Pasang *Max Tool Recursion Depth Counter* (maks. 5-7 siklus). Jika batas tercapai, paksa model memberikan jawaban berbasis data terakhir. |
| **Network Partition / Hang** | Downstream API tidak merespons dan koneksi TCP menggantung tanpa timeout. | Worker thread/coroutine macet permanen (*resource exhaustion*). | Bungkus seluruh eksekusi IO dengan timeout ketat (`asyncio.timeout`) dan implementasikan pola *Circuit Breaker*. |

---

## 8. Trade-offs & Alternatif Solusi

| Parameter | Native Hardcoded Function Calling | ReAct Text-Parsing (LangChain Old) | Model Context Protocol (MCP) |
| :--- | :--- | :--- | :--- |
| **Interoperabilitas** | Rendah (Tergantung vendor spesifik seperti OpenAI, Bedrock). | Sangat Rendah (Bergantung kerapuhan regex output teks). | **Sangat Tinggi** (Protokol terbuka, independen terhadap bahasa dan vendor). |
| **Overhead Token** | Efisien (Menggunakan token representasi internal native model). | Boros (Membutuhkan prompt deskripsi berulang-ulang di konteks). | Moderat (Menggunakan JSON-RPC standar, efisien saat ditransmisikan). |
| **Isolasi Keamanan** | Sulit dipisahkan dari runtime inti aplikasi. | Sangat rapuh terhadap prompt injection. | **Kuat** (Dapat dijalankan sebagai isolated sub-process via `stdio` atau microservice via `SSE`). |
| **Dynamic Discovery** | Statis (Semua schema tool harus didefinisikan saat startup). | Statis (Ditulis manual di system prompt). | **Dinamis** (Client dapat memanggil `tools/list` sewaktu-waktu saat runtime). |
| **Maintenance Complexity** | $O(N \times M)$ kompleksitas integrasi. | Sangat sulit di-debug karena inkonsistensi string parsing. | **$O(N + M)$** pemeliharaan terisolasi berbasis kontrak. |

---

## 9. Best Practices & Standar Industri

1.  **Prinsip Hak Akses Terkecil (Least Privilege Execution):**
    *   Pisahkan tool baca (*Read-Only*) dari tool tulis/modifikasi (*Mutating*).
    *   Gunakan autentikasi berbasis delegasi token (*scoped short-lived tokens*) alih-alih memberikan *database root credentials* kepada runtime tool.
2.  **Mekanisme Deterministic Fallback & Self-Healing:**
    *   Jika pemanggilan tool gagal karena argumen yang salah, jangan langsung menghentikan agen (*fail-hard*). Kirimkan struktur `error` kembali ke model sebagai `observation`. Model tingkat lanjut (misal: Claude 3.5 Sonnet atau GPT-4o) memiliki kemampuan *self-correction* tinggi jika menerima trace kesalahan validasi yang jelas.
3.  **Human-in-the-Loop (HITL) Gate untuk High-Stakes Actions:**
    *   Beri anotasi pada schema untuk tindakan destruktif (misal: `drop_table`, `refund_payment`, `send_email_blast`). Eksekusi aksi semacam ini harus memicu status *PENDING_APPROVAL* dan membutuhkan token persetujuan kriptografis dari supervisor manusia sebelum dilanjutkan.
4.  **Idempotensi Tool Mutation:**
    *   Sediakan parameter `idempotency_key` (UUID) pada setiap operasi mutasi untuk mencegah eksekusi ganda jika model mengirimkan panggilan berulang akibat instabilitas jaringan.

---

## 10. Hands-on Lab Exercise: Sandboxed SQLite & Financial Ledger MCP

### Skenario Lab
Anda ditugaskan oleh institusi perbankan untuk membangun tool data retrieval transaksi nasabah yang aman. Model tidak boleh diizinkan mengeksekusi DDL/DML berbahaya (`DROP`, `DELETE`, `UPDATE`), tidak boleh mengalami hang ketika query berat, dan harus mengisolasi konteks eksekusi dalam SQLite in-memory yang terisolasi.

### Langkah 1: Siapkan Environment Database Sandboxed
Buat file `lab_mcp_engine.py` dan salin kode pondasi database berikut:

```python
import sqlite3
import asyncio
from typing import Dict, Any

def init_sandbox_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE corporate_ledger (
            txn_id TEXT PRIMARY KEY,
            entity_name TEXT NOT NULL,
            amount_usd REAL NOT NULL,
            classification TEXT NOT NULL
        );
    """)
    cursor.executemany("""
        INSERT INTO corporate_ledger VALUES (?, ?, ?, ?);
    """, [
        ("TX-901", "Acme Corp", 450000.00, "INVESTMENT"),
        ("TX-902", "Globex Ind", 1200000.50, "ACQUISITION"),
        ("TX-903", "Soylent Logistics", 34000.00, "OPERATIONAL"),
    ])
    conn.commit()
    return conn

SANDBOX_DB = init_sandbox_db()
```

### Langkah 2: Definisikan Tool Terproteksi dengan Validasi SQL
Implementasikan fungsi query dengan validasi ketat (hanya `SELECT` yang diizinkan):

```python
# Tuliskan implementasi tool Anda di sini
async def safe_query_ledger(sql_statement: str) -> Dict[str, Any]:
    # 1. Validasi: Cegah eksekusi selain SELECT (Read-Only Guard)
    clean_sql = sql_statement.strip()
    if not clean_sql.upper().startswith("SELECT"):
        raise PermissionError("Pelanggaran Keamanan: Hanya query bertipe 'SELECT' yang diizinkan.")
    
    # 2. Validasi Token Terlarang
    forbidden_tokens = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "--", ";"]
    for token in forbidden_tokens:
        if token in clean_sql.upper():
            raise PermissionError(f"Pelanggaran Keamanan: Ditemukan keyword ilegal '{token}'.")

    # 3. Eksekusi Sandboxed
    cursor = SANDBOX_DB.cursor()
    cursor.execute(clean_sql)
    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    
    results = [dict(zip(columns, row)) for row in rows]
    return {"row_count": len(results), "records": results}
```

### Langkah 3: Uji Coba Verifikasi
Eksekusi pengujian untuk memastikan proteksi bekerja dengan benar:

```python
async def run_lab_verification():
    print("--- Test 1: Query Valid ---")
    try:
        res = await safe_query_ledger("SELECT entity_name, amount_usd FROM corporate_ledger WHERE amount_usd > 100000")
        print(f"Hasil Eksekusi Berhasil: {res}\n")
    except Exception as e:
        print(f"Test 1 Gagal: {e}\n")

    print("--- Test 2: Injeksi DDL Drop Table ---")
    try:
        await safe_query_ledger("DROP TABLE corporate_ledger;")
        print("Test 2 GAGAL: Query drop table lolos dari sistem keamanan!\n")
    except PermissionError as pe:
        print(f"Test 2 Berhasil Menolak Ancaman: {pe}\n")

    print("--- Test 3: SQL Injection Bypass Attempt ---")
    try:
        await safe_query_ledger("SELECT * FROM corporate_ledger; DELETE FROM corporate_ledger;")
        print("Test 3 GAGAL: Eksekusi beruntun tidak terdeteksi!\n")
    except PermissionError as pe:
        print(f"Test 3 Berhasil Menolak Ancaman: {pe}\n")

if __name__ == "__main__":
    asyncio.run(run_lab_verification())
```

### Kriteria Kelulusan Lab:
1. Test 1 mengembalikan 2 records (`Acme Corp` dan `Globex Ind`).
2. Test 2 melempar exception `PermissionError` dengan pesan peringatan keamanan yang jelas.
3. Test 3 memblokir eksekusi akibat token ilegal `;` atau `DELETE`.
4. Seluruh kegagalan menghasilkan pesan terstruktur yang dapat diinjeksikan kembali ke LLM untuk memandu formulasi query yang valid.