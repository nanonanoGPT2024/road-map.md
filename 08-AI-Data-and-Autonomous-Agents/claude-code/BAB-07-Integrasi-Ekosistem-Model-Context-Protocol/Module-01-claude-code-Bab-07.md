# Bab 07: Integrasi Ekosistem Model Context Protocol (Module 01)
**Track:** 08-AI-Data-and-Autonomous-Agents  
**Subjek:** Claude Code & Model Context Protocol (MCP) Client-Server Architecture

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, Principal Engineer dan AI Architect diharapkan mampu:

1. **Menganalisis dan Memetakan Primitif Protokol MCP:** Mengidentifikasi secara spesifik peran serta batasan tiga primitif inti MCP (*Resources*, *Prompts*, dan *Tools*) dalam memisahkan state context dari execution plane agent.
2. **Mengimplementasikan Custom MCP Server:** Membangun *production-grade* MCP Server berbasis TypeScript menggunakan `@modelcontextprotocol/sdk` dengan validasi skema runtime *Zod*, penanganan sinyal OS, dan struktur berbasis *Clean Architecture*.
3. **Mengonfigurasi Transport Layer:** Menganalisis perbedaan mekanis antara transport `stdio` (inter-process communication/IPC lokal) dan Server-Sent Events (SSE / HTTP streaming), serta menerapkannya sesuai profil keamanan target.
4. **Mengintegrasikan MCP dengan Claude Code:** Menghubungkan Claude Code CLI dengan server lokal/remote melalui konfigurasi declarative file (`claude.json` / workspace configuration), lengkap dengan parameter environment injection.
5. **Menerapkan Error Budget & Failure Recovery:** Merancang strategi mitigasi untuk menangani *broken pipes*, *unhandled JSON-RPC frame exceptions*, dan eksekusi instruksi tool yang *timeout*.

---

## 2. Concept Overview

Model Context Protocol (MCP) adalah open-standard protocol berbasis JSON-RPC 2.0 yang dirancang oleh Anthropic untuk memisahkan *frontier AI models* (seperti Claude Code) dari integrasi data silo dan eksekusi platform yang heterogen.

Sebelum adanya MCP, pengembang mengimplementasikan *custom tool calling* secara terisolasi untuk setiap platform (misal: plugin custom, integrasi LangChain/LlamaIndex ad-hoc). Pola ini menghasilkan kompleksitas $O(M \times N)$, di mana $M$ aplikasi AI harus mengintegrasikan $N$ sumber data/tool secara independen. MCP mentransformasikan topologi ini menjadi ekosistem $O(M + N)$ melalui standarisasi protokol client-host-server.

```
       [ Client Application / Host (e.g., Claude Code CLI) ]
                              │
                    JSON-RPC 2.0 Protocol
          (via stdio streams atau HTTP Server-Sent Events)
                              │
     ┌────────────────────────┼────────────────────────┐
     ▼                        ▼                        ▼
[ Local MCP Server ]   [ Remote MCP Server ]   [ Enterprise MCP Server ]
 (Git, Local DB, OS)    (SaaS APIs, Slack)      (Internal VPC Microservices)
```

### Primitif Inti MCP

1. **Resources (Context-Driven, Passive):** Data read-only yang menyerupai antarmuka REST `GET` atau representasi file virtual (contoh: log sistem, skema database, snapshot repositori). Resources dapat dibaca langsung oleh Host untuk diinjeksi ke context window.
2. **Prompts (User-Driven, Interactive):** Template terstruktur yang telah dikurasi untuk memandu LLM menjalankan workflow spesifik (contoh: slash commands, predefined debugging routines).
3. **Tools (Model-Driven, Executable):** Fungsi invokasi sisi server yang dapat dipanggil oleh LLM untuk melakukan tindakan yang memiliki *side-effects* (contoh: mutasi database, deployment infrastructure, modifikasi file).

---

## 3. Why It Matters

Dalam implementasi autonomous agent tingkat enterprise, integrasi tool langsung tanpa standardisasi menimbulkan risiko arsitektural yang fatal:

* **Security Boundaries & Blast Radius:** Menjalankan script integrasi arbitrer di dalam environment host tanpa abstraksi protokol berisiko mengekspos environment variable sistem, SSH keys, dan credential lokal ke context window agent secara tidak sengaja.
* **State & Tool Lifecycle Drift:** Tanpa skema terstandarisasi, perubahan API signature pada microservice upstream merusak parser LLM secara silent (*hallucinated tool calls*).
* **Vendor Lock-in:** Mengikat agent tooling ke runtime framework tertentu (misal: proprietary agent runtimes) membatasi portabilitas model di masa depan.
* **Context Window Pollution:** Tooling legacy sering kali mengirimkan seluruh payload respons mentah (seperti JSON 5MB) ke context LLM. MCP Server bertindak sebagai aggregation & filtering proxy yang mengekstrak ringkasan struktural sebelum meneruskannya ke Claude Code.

---

## 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan topologi interaksi antara **Claude Code (Host)**, **MCP Client Layer**, dan **Custom MCP Server (stdio IPC engine)**:

```
+-----------------------------------------------------------------------------+
| HOST: Claude Code CLI Process (Node.js runtime / V8)                        |
|                                                                             |
|  +-------------------+       +--------------------+       +--------------+  |
|  | Context Engine    | <---> | LLM Inference Loop | <---> | Orchestrator |  |
|  +-------------------+       +--------------------+       +-------+------+  |
|                                                                   |         |
|  +------------------------------------------------------------+   |         |
|  | MCP Client Manager                                         | <-+         |
|  |  - stdio Process Spawner / Supervisor                      |             |
|  |  - Protocol Handshake Validator & Capability Negotiator    |             |
|  +------------------------------+-----------------------------+             |
+---------------------------------|-------------------------------------------+
                                  |
                STDIN / STDOUT (JSON-RPC 2.0 Framing)
                Framed with Newlines (\n)
                                  |
+---------------------------------v-------------------------------------------+
| GUEST: Custom MCP Server (Spawned Child Process)                            |
|                                                                             |
|  +-----------------------------------------------------------------------+  |
|  | StdioServerTransport Engine                                           |  |
|  |  - Intercepts process.stdin & serializes to process.stdout            |  |
|  |  - Suppresses arbitrary console.log to avoid protocol desync         |  |
|  +-----------------------------------+-----------------------------------+  |
|                                      |                                      |
|  +-----------------------------------v-----------------------------------+  |
|  | McpServer / Request Dispatcher                                        |  |
|  |  +---------------------+  +--------------------+  +----------------+  |  |
|  |  | Resource Registry   |  | Tool Registry      |  | Prompt Manager |  |  |
|  |  +----------+----------+  +---------+----------+  +-------+--------+  |  |
|  +-------------|-----------------------|---------------------|-----------+  |
|                |                       |                     |              |
|  +-------------v----------+  +---------v----------+  +-------v--------+     |
|  | Data Layer Handlers    |  | Execution Handlers |  | Prompt Strings |     |
|  | (Postgres/Redis/FS)    |  | (Exec, REST, Mutation)|                    |     |
|  +------------------------+  +--------------------+-----------------------+     |
+-----------------------------------------------------------------------------+
```

### JSON-RPC 2.0 Protocol Sequence

```
Host (Claude Code)                    MCP Server (Process)
        |                                      |
        | 1. Spawns child process via stdio    |
        |------------------------------------->|
        | 2. request: "initialize"             |
        |    { protocolVersion, capabilities } |
        |------------------------------------->|
        | 3. response: "initialize"            |
        |    { protocolVersion, serverInfo }   |
        |<-------------------------------------|
        | 4. notification: "notifications/initialized"
        |------------------------------------->|
        | 5. request: "tools/list"             |
        |------------------------------------->|
        | 6. response: "tools/list"            |
        |    { tools: [{name, inputSchema}] }  |
        |<-------------------------------------|
        |                                      |
        | [ LLM decides to call a tool ]       |
        |                                      |
        | 7. request: "tools/call"             |
        |    { name: "db_query", args: {...} } |
        |------------------------------------->|
        | 8. response: "tools/call"            |
        |    { content: [{type, text}], isError}|
        |<-------------------------------------|
```

---

## 5. Deep Dive Mekanisme & Prinsip Kerja

### Transport Mechanics: `stdio` vs `SSE`

#### Stdio Transport
Claude Code mengeksekusi binary server MCP sebagai *child process* menggunakan `child_process.spawn`. Komunikasi berlangsung bidirectional melalui Unix pipe:
* Host menulis payload JSON-RPC ke `stdin` server.
* Server membalas pesan JSON-RPC melalui `stdout`.
* **Kritikal:** Stream `stdout` adalah saluran eksklusif untuk framed JSON-RPC. Bila server melakukan `console.log("Debug info")`, pesan tersebut akan mencemari parser JSON host dan memicu error `Protocol Desynchronization`. Debugging wajib diarahkan ke `stderr` (`console.error`).

#### SSE (Server-Sent Events) Transport
Digunakan untuk topologi *remote* / *distributed*. Menggunakan dual channel:
* Endpoint HTTP streaming konstan (SSE) untuk push event dan response dari Server ke Host.
* Endpoint HTTP `POST` reguler untuk mengirim request dari Host ke Server. Membutuhkan proteksi TLS, session tracking, dan token-based authentication.

### JSON-RPC 2.0 Framing Rules
Setiap pesan diakhiri dengan delimiter newline (`\n`). Struktur payload mematuhi skema strictly-typed:

```json
{
  "jsonrpc": "2.0",
  "id": "uuid-v4-generated-by-host",
  "method": "tools/call",
  "params": {
    "name": "analyze_sql_performance",
    "arguments": {
      "query": "SELECT * FROM orders WHERE status = 'PENDING'",
      "threshold_ms": 250
    }
  }
}
```

Response jika berhasil:
```json
{
  "jsonrpc": "2.0",
  "id": "uuid-v4-generated-by-host",
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Query analysis: Index missing on column 'status'."
      }
    ],
    "isError": false
  }
}
```

Response jika gagal dieksekusi di level logika aplikasi:
* Flag `isError: true` dikembalikan di dalam objek `result` (bukan JSON-RPC error response level) agar LLM memahami hasil evaluasi alat tersebut dan dapat melakukan *self-correction*.
* JSON-RPC error level (`error: { code: -32601, message: "Method not found" }`) hanya digunakan jika skema protokol itu sendiri yang dilanggar atau server crash secara internal.

---

## 6. Production-Ready Code Implementation

Berikut adalah implementasi Production-Ready MCP Server untuk Enterprise Infrastructure Telemetry menggunakan **TypeScript**, `@modelcontextprotocol/sdk`, dan **Zod** skema validasi.

### Direktori Proyek
```text
mcp-telemetry-server/
├── package.json
├── tsconfig.json
└── src/
    ├── index.ts
    ├── schemas/
    │   └── metrics.ts
    └── services/
        └── telemetry.ts
```

### `package.json`
```json
{
  "name": "mcp-telemetry-server",
  "version": "1.0.0",
  "description": "Production MCP Server for Host Telemetry & Diagnosis",
  "type": "module",
  "main": "dist/index.js",
  "scripts": {
    "build": "tsc",
    "start": "node dist/index.js"
  },
  "dependencies": {
    "@modelcontextprotocol/sdk": "^1.6.0",
    "zod": "^3.24.2"
  },
  "devDependencies": {
    "@types/node": "^22.13.0",
    "typescript": "^5.7.3"
  }
}
```

### `src/schemas/metrics.ts`
```typescript
import { z } from "zod";

export const SystemMetricFilterSchema = z.object({
  subsystem: z.enum(["cpu", "memory", "disk", "network"]).describe("Subsystem to retrieve metrics for"),
  sampleWindowSeconds: z.number().int().min(1).max(3600).default(60).describe("Data sampling window"),
});

export type SystemMetricFilter = z.infer<typeof SystemMetricFilterSchema>;

export const KillProcessSchema = z.object({
  pid: z.number().int().positive().describe("Process ID to terminate"),
  signal: z.enum(["SIGTERM", "SIGKILL"]).default("SIGTERM").describe("Signal to issue to the process"),
});

export type KillProcessInput = z.infer<typeof KillProcessSchema>;
```

### `src/services/telemetry.ts`
```typescript
import os from "node:os";

export interface SubsystemMetrics {
  timestamp: string;
  subsystem: string;
  data: Record<string, unknown>;
}

export class TelemetryService {
  public async getMetrics(subsystem: string, _sampleWindow: number): Promise<SubsystemMetrics> {
    const timestamp = new Date().toISOString();

    switch (subsystem) {
      case "cpu": {
        const cpus = os.cpus();
        const loadAvg = os.loadavg();
        return {
          timestamp,
          subsystem,
          data: {
            coreCount: cpus.length,
            model: cpus[0]?.model ?? "Unknown",
            loadAverage1m5m15m: loadAvg,
          },
        };
      }
      case "memory": {
        const total = os.totalmem();
        const free = os.freemem();
        return {
          timestamp,
          subsystem,
          data: {
            totalBytes: total,
            freeBytes: free,
            usedPercentage: Number((((total - free) / total) * 100).toFixed(2)),
          },
        };
      }
      case "disk":
      case "network":
        return {
          timestamp,
          subsystem,
          data: {
            status: "Simulated metric output for demonstration purposes",
            interfaces: os.networkInterfaces(),
          },
        };
      default:
        throw new Error(`Unsupported subsystem: ${subsystem}`);
    }
  }

  public async terminateProcess(pid: number, signal: "SIGTERM" | "SIGKILL"): Promise<string> {
    // Keamanan: Cegah eksekusi PID 1 (Init) atau proses root kritis
    if (pid <= 1) {
      throw new Error("Security Violation: Cannot signal init/root process (PID <= 1)");
    }

    try {
      process.kill(pid, signal);
      return `Successfully dispatched ${signal} to PID ${pid}`;
    } catch (err: unknown) {
      const error = err as NodeJS.ErrnoException;
      throw new Error(`OS Kill Operation Failed: ${error.code} - ${error.message}`);
    }
  }
}
```

### `src/index.ts`
```typescript
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  ListResourcesRequestSchema,
  ReadResourceRequestSchema,
  ErrorCode,
  McpError,
} from "@modelcontextprotocol/sdk/types.js";
import { SystemMetricFilterSchema, KillProcessSchema } from "./schemas/metrics.js";
import { TelemetryService } from "./services/telemetry.js";

const telemetryService = new TelemetryService();

// Inisialisasi Server Instance
const server = new Server(
  {
    name: "enterprise-telemetry-mcp",
    version: "1.0.0",
  },
  {
    capabilities: {
      resources: {},
      tools: {},
    },
  }
);

/**
 * 1. RESOURCES REGISTRATION
 * Menyediakan representasi Read-Only status topologi node lokal.
 */
server.setRequestHandler(ListResourcesRequestSchema, async () => {
  return {
    resources: [
      {
        uri: "telemetry://system/node-overview",
        name: "Host System Node Profile",
        mimeType: "application/json",
        description: "Static architecture profile of the host running this MCP server",
      },
    ],
  };
});

server.setRequestHandler(ReadResourceRequestSchema, async (request) => {
  const { uri } = request.params;

  if (uri === "telemetry://system/node-overview") {
    const payload = {
      hostname: process.env.HOSTNAME || "localhost",
      platform: process.platform,
      arch: process.arch,
      nodeVersion: process.version,
      uptimeSeconds: process.uptime(),
    };

    return {
      contents: [
        {
          uri,
          mimeType: "application/json",
          text: JSON.stringify(payload, null, 2),
        },
      ],
    };
  }

  throw new McpError(ErrorCode.InvalidRequest, `Unknown resource URI: ${uri}`);
});

/**
 * 2. TOOLS REGISTRATION
 * Mendefinisikan alat interaktif yang dapat dipanggil oleh Claude Code.
 */
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: "get_system_telemetry",
        description: "Fetch live performance metrics for an explicit subsystem (cpu, memory, disk, network).",
        inputSchema: {
          type: "object",
          properties: {
            subsystem: {
              type: "string",
              enum: ["cpu", "memory", "disk", "network"],
              description: "Target subsystem to poll",
            },
            sampleWindowSeconds: {
              type: "integer",
              minimum: 1,
              maximum: 3600,
              default: 60,
              description: "Window of sampling in seconds",
            },
          },
          required: ["subsystem"],
        },
      },
      {
        name: "kill_system_process",
        description: "Gracefully or forcefully terminate a process on host system by PID.",
        inputSchema: {
          type: "object",
          properties: {
            pid: {
              type: "integer",
              minimum: 2,
              description: "Process ID",
            },
            signal: {
              type: "string",
              enum: ["SIGTERM", "SIGKILL"],
              default: "SIGTERM",
              description: "POSIX signal name",
            },
          },
          required: ["pid"],
        },
      },
    ],
  };
});

/**
 * 3. TOOL EXECUTION DISPATCHER
 */
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    switch (name) {
      case "get_system_telemetry": {
        const validated = SystemMetricFilterSchema.parse(args);
        const result = await telemetryService.getMetrics(validated.subsystem, validated.sampleWindowSeconds);

        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(result, null, 2),
            },
          ],
          isError: false,
        };
      }

      case "kill_system_process": {
        const validated = KillProcessSchema.parse(args);
        const result = await telemetryService.terminateProcess(validated.pid, validated.signal);

        return {
          content: [
            {
              type: "text",
              text: result,
            },
          ],
          isError: false,
        };
      }

      default:
        throw new McpError(ErrorCode.MethodNotFound, `Tool not found: ${name}`);
    }
  } catch (err: unknown) {
    // Memastikan kegagalan parsing/logic dikirim kembali ke LLM agar bisa berefleksi
    const errorMessage = err instanceof Error ? err.message : String(err);
    return {
      content: [
        {
          type: "text",
          text: `Tool Execution Failure [${name}]: ${errorMessage}`,
        },
      ],
      isError: true,
    };
  }
});

/**
 * 4. LIFECYCLE MANAGEMENT & BOOTSTRAP
 */
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);

  // Mencegah console.log mencemari stdout
  console.error("[INFO] Enterprise Telemetry MCP Server online and serving on stdio");

  const cleanup = async () => {
    console.error("[INFO] Gracefully shutting down MCP server...");
    await server.close();
    process.exit(0);
  };

  process.on("SIGINT", cleanup);
  process.on("SIGTERM", cleanup);
}

main().catch((error) => {
  console.error("[FATAL] Fatal error inside server bootstrapper:", error);
  process.exit(1);
});
```

---

## 7. Edge Cases & Failure Modes

| Skenario Kegagalan | Akar Masalah Arsitektural | Dampak Sistem | Strategi Mitigasi Produksi |
| :--- | :--- | :--- | :--- |
| **Stdout Pollution** | Penggunaan `console.log()` dalam server logic atau package pihak ketiga. | Host JSON parser crash (`SyntaxError: Unexpected token...`); koneksi putus. | Alihkan `console.log` internal ke `console.error` saat startup; set environment `NODE_ENV=production`. |
| **Zombie Child Process** | Host (Claude Code) terminated mendadak (`SIGKILL`), transport pipe terputus. | Child process MCP server tetap hidup memakan CPU/RAM indefinitely. | Dengarkan event `process.stdin.on('close')` pada server; panggil `process.exit(0)` bila pipe hulu ditutup. |
| **Schema Type Drift** | Parameter yang dieksekusi LLM tidak sinkron dengan tipe internal backend. | Runtime exceptions tanpa konteks; LLM mengulang parameter salah (looping). | Validasi deklaratif dengan **Zod**; return error payload yang jelas via `isError: true` agar LLM bisa self-heal. |
| **Payload Bloat** | Tool mengembalikan payload raksasa (misal: JSON dump 50MB). | Mengisi context window hingga batas (*OOM / Token Context Exhaustion*). | Pagination ketat pada Tools/Resources; summarize data di MCP server sebelum dikirimkan. |
| **Deadlock Timeouts** | Database query atau remote call di dalam tool macet tanpa batas waktu. | Claude Code terhenti menunggu respons JSON-RPC (`Timeout waiting for response`). | Terapkan batas waktu absolut (`AbortController` / `Promise.race`) di level tool handler (contoh: max 15s). |

---

## 8. Trade-offs & Alternatif Solusi

```
                     Abstraksi Tinggi / Zero-Code
                               ▲
                               │   OpenAPI Dynamic Import
                               │   (Generasi tool langsung via skema REST)
                               │
            Model Context      │
            Protocol (MCP)     │
                   *           │
                               │
                               │   LangChain / Custom Scripts
                               │   (Ad-hoc function calling)
                               ▼
                     Kontrol Rendah / Manual Maintenance
◄────────────────────────────────────────────────────────────────────────►
Sangat Standar (Ecosystem)                               proprietary / Siloed
```

### Analisis Komparasi

| Metrik | Model Context Protocol (MCP) | Direct LLM Tool Calling (OpenAI/LangChain) | OpenAPI Dynamic Spec Import |
| :--- | :--- | :--- | :--- |
| **Portabilitas Host** | **Tinggi:** Berjalan di Claude Code, Claude Desktop, atau Host MCP mana pun tanpa ubah kode server. | **Rendah:** Terkunci di framework tertentu (misal: LangChain tool schema). | **Sedang:** Membutuhkan OpenAPI engine yang konsisten antar library. |
| **Boundary Security** | **Tinggi:** Server berjalan sebagai child process / service terisolasi dengan akses environment terkontrol. | **Rendah:** Kode tool dieksekusi di context runtime memori agen yang sama. | **Sedang:** Bergantung pada layer sandboxing network client. |
| **Manajemen State** | **Asinkron:** Mendukung push resources, dynamic notifications, dan prompts template. | **Statik:** Hanya memetakan `function -> response`. | **Statik:** Hanya pemanggilan endpoint REST deklaratif. |
| **Overhead Operasional** | **Sedang:** Butuh kompilasi executable atau runtime Node.js/Python terpisah. | **Rendah:** Ditulis *inline* bersama kode host logic. | **Rendah:** Hanya menyediakan URL Swagger/OpenAPI. |

---

## 9. Best Practices & Standar Industri

1. **Prinsip Least Privilege via Environment Sandboxing:**
   * Jangan mewariskan seluruh environment variable host (`process.env`) secara default ke process MCP server.
   * Definisikan secret eksplisit dalam file konfigurasi Claude Code (`claude.json`).

2. **Karantina Logging Host Stream:**
   * Pastikan output logging server menggunakan `stderr`. Di Node.js:
     ```typescript
     // Defensif: Arahkan log standar ke stderr di awal aplikasi
     console.log = (...args) => console.error("[SERVER-LOG]", ...args);
     ```

3. **Struktur Payload Idempoten:**
   * Tools yang melakukan tindakan mutasi kritis (seperti `kill_system_process`, `deploy_stack`) wajib dirancang idempoten atau setidaknya mendukung flag dry-run sebelum aksi destruktif dilakukan.

4. **Karakterisasi Payload Respons:**
   * Return schema yang ramah LLM: Gunakan Markdown terstruktur atau JSON ringkas. Hindari mencantumkan stack-trace biner internal atau log runtime yang berulang-ulang ke context host.

---

## 10. Hands-on Lab Exercise

### Skenario
Anda ditugaskan mengintegrasikan **Enterprise Telemetry MCP Server** yang telah kita bangun langsung ke instance **Claude Code CLI** di mesin lokal Anda, kemudian memerintahkan Claude Code untuk mendiagnosis metrik host dan menghentikan proses mock yang memicu load.

### Langkah demi Langkah

#### Langkah 1: Build MCP Server
1. Clone / posisikan file implementasi di direktori: `~/workspace/mcp-telemetry-server`.
2. Lakukan instalasi dependency dan kompilasi TypeScript:
   ```bash
   cd ~/workspace/mcp-telemetry-server
   npm install
   npm run build
   ```
3. Validasi hasil kompilasi pastikan file executable berada di `dist/index.js`.
4. Jadikan executable dapat diakses mandiri:
   ```bash
   chmod +x dist/index.js
   ```

#### Langkah 2: Daftarkan MCP Server ke Claude Code
Konfigurasikan file MCP Claude Code. Edit konfigurasi global Anda di `~/.claude.json` atau local folder workspace `.claude/mcp.json`:

```json
{
  "mcpServers": {
    "telemetry-monitor": {
      "command": "node",
      "args": [
        "/Users/<YOUR_USERNAME>/workspace/mcp-telemetry-server/dist/index.js"
      ],
      "env": {
        "NODE_ENV": "production"
      }
    }
  }
}
```
*(Ganti `<YOUR_USERNAME>` sesuai home directory lokal Anda)*.

#### Langkah 3: Siapkan Target Proses Dummy
Buat background process buatan untuk pengujian termination:
```bash
# Buat infinite sleep process
sleep 3000 &
# Catat PID yang muncul di terminal (misal: PID 45120)
```

#### Langkah 4: Jalankan Claude Code & Verifikasi
1. Buka terminal baru dan masuk ke context project:
   ```bash
   claude
   ```
2. Minta Claude Code membaca tools yang terdaftar:
   ```text
   > Gunakan MCP telemetry-monitor untuk memeriksa performa memori sistem saya saat ini.
   ```
3. Periksa bagaimana Claude Code memanggil JSON-RPC `tools/call` dengan nama `get_system_telemetry` dan menampilkan analisis konsumsi RAM.
4. Minta Claude Code menghentikan dummy process:
   ```text
   > Tolong periksa proses dummy dengan PID 45120 dan terminasi menggunakan tool telemetry.
   ```

### Verifikasi Hasil
Eksekusi di terminal:
```bash
ps aux | grep "sleep 3000" | grep -v grep
```
*Kriteria Sukses:* Output terminal kosong, menandakan process PID 45120 berhasil diterminasi melalui pemanggilan aman JSON-RPC protocol oleh Claude Code tanpa intervensi shell command langsung. Konfigurasi tersimpan stabil di `.claude.json`.