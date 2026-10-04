# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 03: Technical Content Engineering & Documentation Architecture**  
**Topik: Developer Relations (DevRel) — AI, Data, and Autonomous Agents**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Merancang dan Mengimplementasikan Arsitektur Docs-as-Code Skala Enterprise** yang mendukung ekosistem hibrida: melayani konsumsi *Human Developers* (GUI/Web) dan *Autonomous AI Agents* (Headless/Machine-Readable Interfaces seperti `llms.txt`, MCP tool definitions, dan semantic retrieval).
2. **Membangun Pipeline Continuous Documentation Verification (CDV)** di dalam CI/CD untuk mengeksekusi dan menguji kode contoh (*doctest*), validasi skema OpenAPI 3.1, dan verifikasi muatan *function calling* secara otomatis.
3. **Mengembangkan Interactive Playground & Ephemeral Sandbox** berbasis WebAssembly (WASM) atau isolated micro-containers untuk eksekusi API/SDK AI Agent secara langsung di browser tanpa mengekspos kredensial produksi.
4. **Menerapkan Strategi Sinkronisasi Kontrak Tiga Arah (Tri-Directional Contract Sync)** antara Backend Core Engine, Agent Tool Schemas, dan Dokumentasi Teknis untuk mengeliminasi *documentation rot* dan *AI hallucination*.
5. **Mengukur dan Mengoptimasi Performa Platform Dokumentasi** pada metrik Core Web Vitals, Edge Latency, TTFW (*Time to First "Hello World"*), dan akurasi *Agent Retrieval Precision*.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib menguasai:
- **GitOps & Modern CI/CD**: Pembuatan workflow GitHub Actions/GitLab CI tingkat lanjut (Matrix builds, caching, custom actions).
- **Format Spesifikasi API & Data**: JSON Schema Draft 2020-12, OpenAPI 3.1.0, Markdown/MDX Abstract Syntax Tree (AST).
- **Software Engineering**: TypeScript/Node.js (tingkat lanjut, pemahaman AST tooling seperti `unified`/`remark`) dan Python 3.11+ (asyncio, type hints, `pydantic`).
- **AI/Agent Tooling Fundamentals**: Pemahaman dasar tentang OpenAI Function Calling, Anthropic Tool Use, Model Context Protocol (MCP), dan Vector Search/Embeddings.
- **Frontend Infrastructure**: Static Site Generators (Next.js App Router, Astro, atau Starlight) dan Edge Computing (Cloudflare Workers/Vercel Edge).

---

## 3. Concept & Internal Architecture (Mendalam)

Dokumentasi untuk ekosistem AI dan Autonomous Agents tidak lagi sekadar sekumpulan file HTML statis berisi teks deskriptif. Platform dokumentasi modern adalah **sistem terdistribusi aktif** yang berfungsi sebagai kontrak eksekusi bagi manusia dan model bahasa besar (LLM).

```
                      +------------------------------------------+
                      |         Developer Git Repository         |
                      |   (Docs, MDX, Code Samples, Specs)       |
                      +--------------------+---------------------+
                                           |
                                      git push
                                           v
+----------------------------------------------------------------------------------+
| CI/CD Pipeline: Continuous Documentation Verification (CDV)                       |
|                                                                                  |
|  +--------------------+   +-----------------------+   +-----------------------+  |
|  | 1. AST Parser      |-->| 2. Executable Snippet |-->| 3. Contract Schema   |  |
|  |    (Remark/MDX)    |   |    Runner (Isolated)  |   |    Validator (OpenAPI)|  |
|  +--------------------+   +-----------------------+   +-----------------------+  |
+------------------------------------------+---------------------------------------+
                                           | Artifacts
                                           v
+----------------------------------------------------------------------------------+
| Edge Deployment & Content Delivery Hub (CDN / Edge Runtime)                     |
|                                                                                  |
|  +-------------------------------------+   +----------------------------------+  |
|  | Human Interface (SSG / SSR / ISR)   |   | Machine Interface (Agent Engine) |  |
|  | - Next.js / Astro Documentation GUI |   | - /llms.txt & /llms-full.txt     |  |
|  | - In-Browser WASM Execution Runtime |   | - MCP Endpoint (JSON-RPC)        |  |
|  | - Interactive Playground (WebWorker)|   | - RAG Semantic Chunk Vector Store|  |
|  +-------------------------------------+   +----------------------------------+  |
+----------------------------------------------------------------------------------+
```

### 3.1. Dual-Audience Documentation Architecture (Human vs. Agent)
Dokumentasi teknis untuk produk AI/Agent harus melayani dua klien dengan karakteristik yang bertolak belakang:
- **Human Developer**: Membutuhkan konteks visual, panduan langkah-demi-langkah, diagram alir, penyorotan sintaksis (*syntax highlighting*), dan UI sandbox interaktif.
- **Autonomous Agent (LLM)**: Membutuhkan token density yang tinggi, zero visual noise (tanpa CSS/JS bundle), struktur semantik murni (Markdown/JSON-LD), skema parameter yang ketat (JSON Schema/OpenAPI), dan file ringkas seperti `llms.txt` yang memetakan kapabilitas sistem secara deterministik.

### 3.2. AST-Based Verification Engine
Sistem memanfaatkan *Markdown Abstract Syntax Tree* (MDAST). Selama proses *build*, parser membongkar file dokumentasi menjadi node-node AST:
1. Filter semua node `code` dengan bahasa target (misal: `python`, `typescript`).
2. Ekstraksi metadata dari *code fence* (contoh: ```python runner="doctest" env="sandbox").
3. Injeksi variabel lingkungan isolasi (*mocked tokens*).
4. Kompilasi dan eksekusi kode terhadap staging backend atau mock gateway.
5. Jika ada kegagalan eksekusi atau ketidakcocokan return payload dengan skema, build **dibatalkan (FAIL CLOSED)**.

### 3.3. Ephemeral Sandbox Architecture
Alih-alih mengarahkan pengguna ke copy-paste API key produksi mereka ke dokumentasi publik, arsitektur dokumentasi mengimplementasikan dua pendekatan sandbox:
1. **Client-side Sandbox (WASM)**: Untuk SDK berbasis bahasa seperti Python (menggunakan Pyodide) atau Node.js (WebContainer API), kode dieksekusi murni di dalam Web Worker browser pengguna.
2. **Server-side Ephemeral Proxy**: Gateway sementara berbasis Edge Function yang menyuntikkan token dengan hak akses terbatas (*read-only/rate-limited/ephemeral*) secara otomatis ke permintaan dari playground dokumentasi.

---

## 4. Why & What

| Dimensi | Pendekatan Dokumentasi Tradisional | Arsitektur Dokumentasi AI/Agent Enterprise |
| :--- | :--- | :--- |
| **Audiens Utama** | Manusia (*Human Developers*) melalui peramban web. | Dual: Manusia dan *Autonomous Agents* (Model Context Protocol, Tool Call). |
| **Siklus Hidup Kode Contoh** | Manual copy-paste; rawan usang saat SDK diperbarui. | *Continuous Verification*; dieksekusi otomatis di pipeline CI/CD layaknya unit test. |
| **Konsumsi Konteks LLM** | LLM melakukan web scraping yang lambat, boros token, dan kotor oleh elemen DOM. | Ekspor deterministik: `llms.txt`, *raw markdown*, dan *vectorized chunk endpoints*. |
| **Validasi Spesifikasi API** | Mengandalkan ketelitian teknis penulis docs secara visual. | *Automated Contract Sync*; skema OpenAPI/Pydantic langsung mengontrol output docs. |
| **Umpan Balik Pengembang** | Pasif (komentar, issue GitHub manual, tombol "Was this page helpful?"). | Aktif: Telemetri Playground, error snippet logging, LLM retrieval failure analysis. |

### Mengapa ini krusial untuk Ekosistem AI & Autonomous Agents?
Model AI tidak memiliki toleransi terhadap dokumentasi yang kadaluwarsa (*documentation rot*). Jika tipe parameter diubah dari `string` menjadi `list[string]` pada SDK terbaru, namun dokumentasi masih mencantumkan `string`, maka:
1. Pengembang manusia akan frustrasi karena kode sampel gagal.
2. Agent otonom yang mengonsumsi tool docs tersebut akan mengalami *runtime tool call error*, menghasilkan loop halusinasi, dan meningkatkan latensi serta biaya token API secara drastis.

---

## 5. How (Workflow Detail)

Berikut adalah tahapan implementasi arsitektur Continuous Documentation Verification (CDV) dan publikasi dual-audience:

```
[Developer] Push Code / Docs Update
    │
    ▼
[Phase 1: Parse & Extract]
    ├── Baca direktori konten (*.mdx)
    ├── Parse menjadi AST via Remark
    └── Kumpulkan seluruh blok kode bertanda executable
    │
    ▼
[Phase 2: Automated Contract Validation]
    ├── Ambil schema OpenAPI 3.1 terbaru dari Core Engine
    └── Validasi signature fungsi dan response payload
    │
    ▼
[Phase 3: Sandbox Test Execution]
    ├── Jalankan code snippets dalam isolated environment
    └── Verifikasi output string/JSON terhadap ekspektasi
    │
    ▼
[Phase 4: Multi-Target Artifact Generation]
    ├── Target 1: Generate Static HTML/CSS via Astro/Next.js (Untuk Manusia)
    ├── Target 2: Generate /llms.txt dan /llms-full.txt (Untuk Agent Caching)
    └── Target 3: Generate Embedding Chunks & Sync Vector Store (Untuk Agent RAG)
    │
    ▼
[Phase 5: Edge Deployment]
    └── Deploy ke Cloudflare Pages/Workers dengan Cache Tag Invalidation
```

### Langkah Operasional:
1. **Parsing Tahap Awal**: Parse konten MDX ke format AST menggunakan ekosistem `unified`. Ekstrak kode sampel Python dan TypeScript bersama atribut metadata eksekusinya.
2. **Sinkronisasi Skema**: Cocokkan argumen dan tipe data kode sampel dengan skema OpenAPI atau Pydantic models yang dihasilkan langsung dari kompilasi backend services.
3. **Isolasi Eksekusi**: Eksekusi blok kode dalam worker sandbox terkontrol (misal: Docker container minimal atau isolate edge). Blokir seluruh akses jaringan eksternal non-whitelisted.
4. **Kompilasi Multi-Target**:
   - Bangun antarmuka visual (MDX ke HTML dengan interaktivitas React/Astro).
   - Bentuk representasi teks padat bebas markup dekoratif untuk konsumsi LLM (`/llms.txt`).
   - Ekstrak chunk semantik berbasis heading untuk di-ingest ke index RAG.
5. **Rilis ke Edge**: Distribusikan aset ke Edge CDN dengan header `Cache-Control` yang agresif, namun didukung mekanisme *tag-based cache purge* saat rilis SDK baru dipublikasikan.

---

## 6. Analogy & Diagram ASCII

### Analogi Sistem
Bayangkan dokumentasi Anda bukan sekadar **buku manual cetak**, melainkan **Sistem Avionik Kokpit Pesawat Terbang Modern**.
- **Human Pilot (Developer)** membutuhkan layar instrumen visual, lampu peringatan berkode warna, dan panduan taktis untuk mengambil keputusan navigasi.
- **Autopilot System (Autonomous Agent)** tidak peduli warna lampu instrumen; ia membutuhkan aliran data telemetri digital murni berbasis bus ARINC/CAN-bus tanpa latensi dan ambiguitas.
- **CDV Pipeline** adalah tim insinyur sertifikasi darat yang menyalakan mesin jet dan menguji setiap sekrup avionik sebelum pesawat diizinkan meninggalkan hanggar. Jika ada satu kabel yang putus (kode usang), penerbangan dibatalkan seketika.

### Diagram Arsitektur Detail

```
+---------------------------------------------------------------------------------+
|                              CONTENT REPOSITORY                                 |
|  docs/                                                                          |
|   ├── agents/tool-calling.mdx   (MDX containing text, components, codeblocks)  |
|   └── specs/openapi.json        (Canonical API specification)                   |
+---------------------------------------------------------------------------------+
                                      │
                                      ▼
+---------------------------------------------------------------------------------+
|                       AST COMPILATION & EXECUTION ENGINE                        |
|                                                                                 |
|  [ unified / remark-parse ]                                                     |
|              │                                                                  |
|              ▼                                                                  |
|  [ MDAST (Markdown AST) ]                                                       |
|              ├──> Extracts Node: code [lang="python", meta="verify='true'"]     |
|              │                                                                  |
|              ▼                                                                  |
|  [ Python Test Runner (Pytest Isolated Worker) ]                                |
|        │                                                                        |
|        ├── SUCCESS: Proceed to compilation                                      |
|        └── FAILURE: Abort Pipeline & Dump Traceback                             |
+---------------------------------------------------------------------------------+
                                      │
                                      ▼
+---------------------------------------------------------------------------------+
|                               ARTIFACT EXPORT                                   |
|                                                                                 |
|   +-----------------------+  +-----------------------+  +--------------------+  |
|   | Human Interface       |  | Machine Interface     |  | Retrieval Engine   |  |
|   | - SSG Web Pages       |  | - /public/llms.txt    |  | - Markdown Chunks  |  |
|   | - WASM Playground     |  | - /public/mcp.json    |  | - Vector Embeddings|  |
|   +-----------------------+  +-----------------------+  +--------------------+  |
+---------------------------------------------------------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1. Simple Example: In-Memory Markdown Snippet Verifier
Contoh skrip sederhana berbasis Python untuk mengekstrak dan mengeksekusi blok kode Python dari file Markdown untuk memastikan tidak ada sintaks rusak (*syntax error*).

```python
# simple_doc_verifier.py
import re
import sys

def extract_and_verify_snippets(markdown_path: str) -> bool:
    with open(markdown_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Regex untuk mendeteksi blok kode python dengan flag verify
    pattern = r"```python\s+verify=true\n(.*?)```"
    snippets = re.findall(pattern, content, re.DOTALL)
    
    print(f"[*] Ditemukan {len(snippets)} executable code block(s) di {markdown_path}")
    
    for idx, code in enumerate(snippets, 1):
        print(f"--- Menjalankan Snippet #{idx} ---")
        try:
            # Mengisolasi scope variabel global dan lokal
            local_scope = {}
            exec(code, {}, local_scope)
            print(f"[PASSED] Snippet #{idx} berhasil dieksekusi.")
        except Exception as e:
            print(f"[FAILED] Snippet #{idx} gagal dieksekusi: {e}", file=sys.stderr)
            return False
            
    return True

if __name__ == "__main__":
    test_md = "test_doc.md"
    with open(test_md, "w") as f:
        f.write("# Sample Doc\n```python verify=true\nx = 10\ny = 20\nassert x + y == 30\n```")
    
    success = extract_and_verify_snippets(test_md)
    sys.exit(0 if success else 1)
```

---

### 7.2. Practical Example: Production-Grade AST MDX Code Verifier & Tool Schema Assertion Engine
Implementasi tingkat lanjut berbasis TypeScript/Node.js menggunakan `unified`, `remark-parse`, dan `zod` untuk memvalidasi bahwa setiap contoh panggilan *Agent Tool* di dalam dokumentasi MDX mematuhi skema JSON/Zod yang didefinisikan secara resmi.

#### `package.json`
```json
{
  "name": "enterprise-doc-engine",
  "version": "1.0.0",
  "type": "module",
  "dependencies": {
    "remark-parse": "^11.0.0",
    "unified": "^11.0.4",
    "unist-util-visit": "^5.0.0",
    "zod": "^3.22.4"
  }
}
```

#### `src/verify-snippets.ts`
```typescript
import fs from "node:fs/promises";
import path from "node:path";
import { unified } from "unified";
import remarkParse from "remark-parse";
import { visit } from "unist-util-visit";
import type { Code, Root } from "mdast";
import { z } from "zod";

// 1. Skema Kontrak Resmi untuk Autonomous Agent Tool Call
const AgentToolDefinitionSchema = z.object({
  tool_name: z.string().regex(/^[a-z_]+$/, "Tool name harus format snake_case"),
  description: z.string().min(20, "Deskripsi tool harus detail untuk LLM context"),
  parameters: z.object({
    type: z.literal("object"),
    properties: z.record(
      z.object({
        type: z.string(),
        description: z.string(),
      })
    ),
    required: z.array(z.string()),
  }),
});

type ToolDefinition = z.infer<typeof AgentToolDefinitionSchema>;

interface ExtractedSnippet {
  code: string;
  lang: string | null;
  line: number | undefined;
  type: string;
}

// 2. Parser AST untuk Mengekstraksi Blok Kode Khusus
async function extractSnippetsFromMDX(filePath: string): Promise<ExtractedSnippet[]> {
  const content = await fs.readFile(filePath, "utf-8");
  const processor = unified().use(remarkParse);
  const ast = processor.parse(content) as Root;

  const snippets: ExtractedSnippet[] = [];

  visit(ast, "code", (node: Code) => {
    // Mengecek atribut metastring: misal ```json type="agent-tool-contract"
    if (node.meta && node.meta.includes('type="agent-tool-contract"')) {
      snippets.push({
        code: node.value,
        lang: node.lang ?? null,
        line: node.position?.start.line,
        type: "agent-tool-contract",
      });
    }
  });

  return snippets;
}

// 3. Engine Validasi Kontrak
async function validateDocumentationContract(filePath: string): Promise<void> {
  console.log(`[INFO] Memproses analisis AST: ${filePath}`);
  const snippets = await extractSnippetsFromMDX(filePath);

  let hasError = false;

  for (const snippet of snippets) {
    if (snippet.type === "agent-tool-contract") {
      try {
        const parsedJson = JSON.parse(snippet.code);
        const validationResult = AgentToolDefinitionSchema.safeParse(parsedJson);

        if (!validationResult.success) {
          console.error(
            `\x1b[31m[ERROR]\x1b[0m Validasi gagal pada baris ${snippet.line}:`
          );
          console.error(JSON.stringify(validationResult.error.format(), null, 2));
          hasError = true;
        } else {
          console.log(
            `\x1b[32m[SUCCESS]\x1b[0m Kontrak valid untuk tool: "${validationResult.data.tool_name}" (Baris ${snippet.line})`
          );
        }
      } catch (err) {
        console.error(
          `\x1b[31m[SYNTAX ERROR]\x1b[0m Gagal mem-parse JSON pada baris ${snippet.line}:`,
          (err as Error).message
        );
        hasError = true;
      }
    }
  }

  if (hasError) {
    throw new Error(`Verifikasi dokumentasi gagal pada file: ${filePath}`);
  }
}

// 4. Runner
async function main() {
  const targetFile = path.resolve("./docs/sample-agent-tool.mdx");
  
  // Dummy content file untuk eksekusi pipeline
  const dummyMDX = `
# Dokumentasi Registrasi AI Agent

Berikut adalah tool manifest untuk sinkronisasi database pengguna.

\`\`\`json type="agent-tool-contract"
{
  "tool_name": "fetch_user_telemetry",
  "description": "Mengambil metrik performa dan kuota penggunaan developer secara real-time.",
  "parameters": {
    "type": "object",
    "properties": {
      "user_id": {
        "type": "string",
        "description": "UUID entitas developer"
      },
      "metric_type": {
        "type": "string",
        "description": "Nama metrik yang diminta"
      }
    },
    "required": ["user_id"]
  }
}
\`\`\`
`;

  await fs.mkdir(path.dirname(targetFile), { recursive: true });
  await fs.writeFile(targetFile, dummyMDX, "utf-8");

  try {
    await validateDocumentationContract(targetFile);
    console.log("\x1b[32m[PIPELINE COMPLETED]\x1b[0m Dokumentasi lolos verifikasi produksi.");
  } catch (error) {
    console.error("\x1b[31m[PIPELINE ABORTED]\x1b[0m", (error as Error).message);
    process.exit(1);
  }
}

main();
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario: "Synthetix AI" Autonomous Multi-Agent Orchestration Platform
- **Kondisi Awal**:
  Synthetix AI memiliki 45 SDK mikro dan 350+ model tools yang didistribusikan ke 85.000 developer enterprise. Setiap rilis minor pada arsitektur streaming payload menyebabkan ~15% kode contoh di dokumentasi menjadi *stale*. Akibatnya, tim Technical Support kebanjiran 600+ tiket per minggu yang mengeluhkan `"AttributeError: object has no attribute 'stream_async'"`, dan developer churn rate meningkat tajam pada 14 hari pertama onboarding.

### Solusi Arsitektur yang Diterapkan:
1. **Pipeline CDV Terisolasi**:
   Semua kode MDX dipisahkan ke dalam format *executable snippets*. Setiap kali PR dibuka oleh tim Product, Content, atau Core Backend, sebuah runner ephemeral AWS Firecracker MicroVM memutar lingkungan virtual, mengompilasi SDK Python, Go, dan Node.js, lalu mengeksekusi 1.200 potongan kode dalam waktu 4 menit.
2. **Headless Agent Ingestion (`/llms.txt` + JSON-RPC MCP Endpoint)**:
   Menerbitkan endpoint `/api/v1/mcp` langsung dari AST dokumentasi. Autonomous agent seperti Cursor, Devin, atau Claude Desktop tidak perlu melakukan web scraping; mereka langsung mengunduh deskripsi spesifikasi tool yang selalu tersinkronisasi 100% dengan branch `main`.
3. **In-Browser WebContainer Playground**:
   Mengintegrasikan Node.js runtime berbasis WASM ke dalam dokumentasi web. Developer dapat langsung mengklik tombol "Run Example" dan mengeksekusi pipeline agent multi-langkah langsung di memori browser mereka dengan zero-server cost bagi Synthetix AI.

### Metrik Keberhasilan (Hasil Pasca-Implementasi):
- **Support Ticket Reduction**: Tiket dokumentasi/kode error turun **82%** dalam 60 hari.
- **TTFW (Time To First "Hello World")**: Turun dari **34 menit** menjadi **4,2 menit**.
- **Agent Hallucination Rate**: Akurasi parsing kode oleh AI coding assistants naik dari **64%** menjadi **98,7%** karena ketersediaan format padat `llms.txt`.
- **Infrastructure Cost**: Penghematan biaya server dokumentasi sebesar **$14.000/bulan** dengan memindahkan sandbox server ke client-side WASM.

---

## 9. Trade-offs

| Pendekatan / Keputusan Arsitektur | Keuntungan (Pros) | Biaya & Risiko (Cons / Trade-offs) | Mitigasi Solusi |
| :--- | :--- | :--- | :--- |
| **Strict CI Doctest Execution** | Menjamin 100% akurasi kode contoh; zero broken examples masuk ke production. | Waktu build CI/CD meningkat drastis (dapat memakan waktu >20 menit jika ratusan snippet diuji). | Implementasikan *Snippet Content Hashing*; hanya jalankan snippet yang baris kodenya termodifikasi. |
| **Client-Side WASM Playground (Pyodide / WebContainers)** | Zero hosting sandbox cost; data dan API Key pengembang tetap berada di mesin lokal browser mereka. | Ukuran aset awal (initial payload) besar (~15-30MB runtime WASM); performa bergantung spek perangkat klien. | *Lazy-load* runtime WASM hanya saat pengguna berinteraksi pertama kali dengan tombol eksekusi. |
| **Dual Artifact (`/llms.txt` vs Full HTML Docs)** | Memberikan efisiensi token maksimal bagi LLM tanpa mengorbankan estetika antarmuka pengembang manusia. | Menambah kompleksitas pipeline build (perlu dua pipeline rendering yang sinkron dari satu sumber). | Gunakan generator berbasis AST terpadu yang memecah satu node MDAST ke dua format stream (Markdown & HTML). |
| **Server-Side Ephemeral Containers** | Mendukung eksekusi kode backend multi-bahasa lengkap yang tidak dapat dijalankan di WASM (e.g., Docker-in-Docker, GPU API). | Biaya server tinggi; potensi eksploitasi keamanan (*Remote Code Execution*, *crypto-mining abuse*). | Batasi runtime maksimal 10 detik, *isolate networking via network namespaces*, dan wajibkan autentikasi akun terverifikasi. |

---

## 10. Common Mistakes & Troubleshooting

### 1. Desinkronisasi Skema Agent Tool dengan OpenAPI Backend
- **Gejala**: Agent berhasil memanggil endpoint, namun backend melempar error `422 Unprocessable Entity`.
- **Penyebab**: Penulis dokumentasi memperbarui manual contoh JSON di file MDX tanpa memperbarui skema validasi Pydantic/OpenAPI di repositori backend.
- **Solusi**: Jangan pernah menulis JSON contoh secara manual. Gunakan mekanisme *transclusion/injection* di mana MDX menarik JSON langsung dari file schema yang dihasilkan kompilasi backend (`auto-generated fixtures`).

### 2. Kebocoran Kredensial Produksi pada Interactive Playground
- **Gejala**: API Key staging/internal tim DevRel terekspos di tab Network pada Developer Tools browser pengguna.
- **Penyebab**: Kode sandbox frontend secara naif menyertakan token otentikasi di client-side script.
- **Solusi**: Implementasikan **Token Exchange Edge Proxy**. Playground di browser hanya menerima token session anonim sementara (*time-to-live 5 menit*). Edge proxy Cloudflare Workers menukar token ini dengan sandbox credential yang dibatasi hak aksesnya (*read-only, scope-limited*).

### 3. Hydration Mismatch pada Rendering Snippet MDX
- **Gejala**: UI dokumentasi berkedip atau merusak layout saat di-load di Next.js/React.
- **Penyebab**: Shiki/Prism syntax highlighter menghasilkan struktur DOM yang berbeda antara server-side rendering (SSR) dan client-side hydration karena perbedaan konfigurasi lokal atau parsing time.
- **Solusi**: Lakukan syntax highlighting murni pada *build-time* di tingkat AST (`rehype-pretty-code` atau `@shikijs/rehype`) sehingga output HTML dikirimkan secara deterministik tanpa perlu runtime JS tambahan di client.

---

## 11. Best Practices (Production Checklist)

### A. Arsitektur & Pipeline (CI/CD)
- [ ] Pipeline CI menjalankan verifikasi sintaks dan skema terhadap **seluruh** blok kode di repositori dokumentasi.
- [ ] Cache dependency runtime diterapkan pada pipeline verifikasi snippet untuk menjaga durasi build CI di bawah 5 menit.
- [ ] Pipeline menghasilkan peringatan (*warning*) jika ada blok kode `bash` yang menggunakan URL hardcoded non-produksi.
- [ ] Mekanisme deteksi tautan rusak (*link checker*) internal dan eksternal diaktifkan dengan threshold kegagalan 0 toleransi.

### B. Optimalisasi Machine-Readable (AI/LLM)
- [ ] Endpoint `/llms.txt` tersedia di root domain dengan format padat berisi ringkasan kapabilitas dan tautan ke file mentah.
- [ ] Endpoint `/llms-full.txt` mengekspor seluruh dokumentasi dalam satu stream Markdown murni tanpa header/footer navigasi visual.
- [ ] Seluruh contoh pemanggilan agent mencakup deskripsi skema input-output yang valid sesuai spesifikasi Model Context Protocol (MCP) atau OpenAI Function Calling.

### C. Keamanan & Sandbox Playground
- [ ] Tidak ada API token permanen yang di-hardcode di dalam dokumentasi publik maupun repositori publik.
- [ ] Interactive playground menggunakan isolasi ketat (WASM / iframe sandbox tanpa akses `allow-same-origin` ke domain utama dokumentasi).
- [ ] Edge proxy menerapkan batas frekuensi (*rate limiting*) ketat per IP (maksimal 20 eksekusi per menit).

### D. Performa & Observabilitas
- [ ] Skor Google Lighthouse Documentation mencapai minimal **95+** pada Performance, Accessibility, dan SEO.
- [ ] Telemetri diaktifkan untuk melacak: snippet yang paling sering disalin (*copy-to-clipboard*), snippet yang gagal dijalankan di sandbox, dan pencarian yang menghasilkan *zero results*.

---

## 12. Hands-on Practice

Buatlah sistem verifikasi snippet dokumentasi mandiri yang akan menguji dokumen markdown secara otomatis.

### Struktur Direktori:
Simpan seluruh file implementasi ini di dalam direktori `hands-on/m02/`.

```
hands-on/m02/
├── package.json
├── tsconfig.json
├── docs/
│   └── agent-guide.md
└── src/
    └── validator.ts
```

### Langkah 1: Inisialisasi Proyek
Masuk ke terminal dan jalankan:
```bash
mkdir -p hands-on/m02/docs hands-on/m02/src
cd hands-on/m02
npm init -y
npm install typescript @types/node unified remark-parse unist-util-visit zod --save-dev
npm install zod
```

Konfigurasikan `tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "esModuleInterop": true,
    "strict": true,
    "skipLibCheck": true
  }
}
```

Perbarui `package.json` untuk menambahkan `"type": "module"` dan script runner:
```json
{
  "type": "module",
  "scripts": {
    "validate": "tsc && node dist/validator.js"
  }
}
```

### Langkah 2: Buat Dokumen Uji (`docs/agent-guide.md`)
Buat file `hands-on/m02/docs/agent-guide.md`:
```markdown
# Integrasi Autonomous Tool Call

Berikut adalah skema konfigurasi agent yang valid:

```json type="agent-schema"
{
  "name": "crypto_price_checker",
  "timeout_ms": 5000,
  "retry_count": 3
}
```

Dan berikut adalah konfigurasi kedua yang harus diuji:

```json type="agent-schema"
{
  "name": "order_execution_agent",
  "timeout_ms": 12000,
  "retry_count": 5
}
```
```

### Langkah 3: Implementasikan Validator Core (`src/validator.ts`)
Buat file `hands-on/m02/src/validator.ts`:
```typescript
import fs from "node:fs/promises";
import path from "node:path";
import { unified } from "unified";
import remarkParse from "remark-parse";
import { visit } from "unist-util-visit";
import type { Code, Root } from "mdast";
import { z } from "zod";

const AgentConfigSchema = z.object({
  name: z.string().min(3),
  timeout_ms: z.number().max(15000),
  retry_count: z.number().int().min(0).max(5),
});

async function runPipeline() {
  const filePath = path.resolve("./docs/agent-guide.md");
  console.log(`[CI/CD] Menjalankan verifikasi pada: ${filePath}`);

  const content = await fs.readFile(filePath, "utf-8");
  const ast = unified().use(remarkParse).parse(content) as Root;

  let totalTested = 0;
  let hasFailure = false;

  visit(ast, "code", (node: Code) => {
    if (node.meta?.includes('type="agent-schema"')) {
      totalTested++;
      try {
        const json = JSON.parse(node.value);
        AgentConfigSchema.parse(json);
        console.log(`[PASS] Block pada baris ${node.position?.start.line} memenuhi kontrak.`);
      } catch (err) {
        hasFailure = true;
        console.error(`[FAIL] Block pada baris ${node.position?.start.line} melanggar kontrak!`);
        if (err instanceof z.ZodError) {
          console.error(err.issues);
        } else {
          console.error((err as Error).message);
        }
      }
    }
  });

  if (hasFailure || totalTested === 0) {
    console.error(`\n[ABORT] Verifikasi dokumentasi gagal. Total: ${totalTested}`);
    process.exit(1);
  } else {
    console.log(`\n[SUCCESS] Seluruh (${totalTested}) blok kode terverifikasi sesuai skema.`);
  }
}

runPipeline();
```

### Langkah 4: Eksekusi dan Verifikasi
Jalankan di terminal:
```bash
npm run validate
```
Pastikan output menampilkan status `[PASS]` untuk kedua blok kode dan exit code `0`.

---

## 13. Exercise

### Level Easy
Modifikasi validator pada *Hands-on Practice* agar mengenali blok kode `type="bash-snippet"`. Buat assertion sederhana yang memvalidasi bahwa setiap perintah bash **tidak boleh** mengandung perintah berbahaya seperti `rm -rf /` atau flag `--insecure`. Uji dengan menambahkan snippet bash ke `docs/agent-guide.md`.

### Level Medium
Integrasikan skrip verifikasi dengan GitHub Actions workflow lokal/mock. Buat script TypeScript yang menerima argument array file MDX yang termodifikasi (menggunakan git diff logic: `git diff --name-only HEAD~1 HEAD`) dan hanya menjalankan validasi AST pada file-file yang berubah tersebut (*incremental doc validation*).

### Level Hard
Rancang engine transformer AST yang membaca file MDX yang berisi kode Python valid, lalu:
1. Membaca AST dan mengambil kode tersebut.
2. Mengirimkan kode ke runner Python lokal melalui *child process* secara asinkron (*non-blocking pool*).
3. Mengambil `stdout` dari runner tersebut dan mencocokkannya dengan node blok Markdown berikutnya yang memiliki atribut `type="expected-output"`.
4. Jika output runtime Python berbeda dari dokumentasi, pipeline harus melempar exception deskriptif yang menunjukkan *diff* baris per baris.

---

## 14. Challenge

### Studi Kasus: "Self-Healing Documentation Engine for Rapidly Evolving AI Agent SDKs"
Sebuah perusahaan pengembang AI Framework meluncurkan SDK baru setiap minggu. Seringkali parameter nama fungsi diubah (misalnya `Agent.run_step()` diubah menjadi `Agent.step()`).

**Tantangan Arsitektur:**
Rancang sebuah spesifikasi arsitektur sistem (buat diagram alur dan implementasi modul inti) untuk **Self-Healing Documentation Pipeline**:
1. Pipeline diaktifkan via Webhook setiap kali ada tag rilis Git baru pada SDK backend.
2. Parser mendeteksi seluruh kode contoh di repositori dokumentasi yang mengalami kegagalan eksekusi (*failing snippets*).
3. Pipeline secara otomatis mengirimkan AST snippet yang rusak, pesan error traceback SDK, dan definisi API terbaru ke sebuah Autonomous LLM Coding Agent internal.
4. Agent memperbaiki kode sampel tersebut, memvalidasi ulang kode yang diperbaiki ke dalam isolated runner, dan jika berhasil lolos uji, secara otomatis membuka Pull Request (PR) ke repositori dokumentasi lengkap dengan diff dan hasil verifikasi eksekusinya.
5. **Kriteria Ketat**: Sistem harus deterministik, tidak boleh menghasilkan halusinasi baru, dan wajib memiliki batasan toleransi eksekusi terisolasi (sandbox security).

---

## 15. Quiz Evaluasi Pemahaman

### 15.1. Pertanyaan Basic (Pilihan Ganda)

1. Apa fungsi utama dari penyediaan file `/llms.txt` pada root domain dokumentasi teknis produk AI?
   - A. Sebagai pengganti file `robots.txt` untuk memblokir web spider Google.
   - B. Menyediakan file ringkas berformat Markdown murni berdensitas token tinggi yang dirancang khusus untuk konsumsi LLM tanpa derau visual HTML.
   - C. Menyimpan kunci otentikasi API publik agar Autonomous Agent dapat membaca data secara otomatis.
   - D. Mengalihkan lalu lintas peramban manusia ke dokumentasi versi mobile.
   *Jawaban yang benar: B*

2. Pada arsitektur Continuous Documentation Verification (CDV), apa arti prinsip *Fail-Closed*?
   - A. Dokumentasi tetap di-deploy meskipun snippet kode gagal dieksekusi di pipeline CI.
   - B. Build deployment dokumentasi langsung dibatalkan jika ada satu kode contoh yang kadaluwarsa atau menghasilkan error runtime.
   - C. Dokumentasi hanya dapat diakses melalui jaringan VPN tertutup.
   - D. Seluruh endpoint API dokumentasi dimatikan secara otomatis setiap akhir pekan.
   *Jawaban yang benar: B*

3. Manakah library parsing Markdown AST yang paling umum digunakan dalam ekosistem JavaScript/TypeScript modern untuk manipulasi sintaks tingkat rendah?
   - A. jQuery
   - B. Unified / Remark
   - C. Lodash
   - D. Webpack
   *Jawaban yang benar: B*

4. Mengapa eksekusi interactive playground berbasis WASM (WebAssembly) di sisi client lebih disukai untuk SDK sederhana dibanding menjalankan server container remote?
   - A. WASM memiliki akses tak terbatas ke GPU server backend.
   - B. Mengeliminasi biaya komputasi server dokumentasi dan melindungi privasi kredensial pengguna dari penyimpanan server pihak ketiga.
   - C. WASM otomatis memperbaiki bug sintaks pada kode yang ditulis pengembang.
   - D. WASM tidak membutuhkan peramban web modern untuk berjalan.
   *Jawaban yang benar: B*

5. Apa risiko utama menyajikan contoh tool calling JSON secara manual tanpa validasi skema otomatis?
   - A. Ukuran bundle CSS dokumentasi menjadi terlalu besar.
   - B. Terjadinya desinkronisasi kontrak (*schema drift*) yang menyebabkan agen otonom mengalami kegagalan eksekusi (*tool call failure*).
   - C. Pengembang manusia tidak menyukai tampilan format JSON.
   - D. Waktu deployment web menjadi lebih lambat dari 1 detik.
   *Jawaban yang benar: B*

---

### 15.2. Pertanyaan Intermediate (Pilihan Ganda)

6. Bagaimana cara terbaik mencegah masalah *Hydration Mismatch* pada komponen penyorot sintaksis (syntax highlighting) di framework SSR seperti Next.js?
   - A. Menjalankan penyorotan sintaksis di browser menggunakan event `useEffect` tanpa SSR.
   - B. Mengompilasi dan menghasilkan HTML berwarna secara statis pada fase AST build-time sebelum dikirimkan ke client runtime.
   - C. Menghapus seluruh tag `<pre>` dan `<code>` dari dokumentasi.
   - D. Mengubah seluruh format dokumentasi menjadi gambar statis (PNG).
   *Jawaban yang benar: B*

7. Dalam konteks arsitektur sandbox dokumentasi, apa fungsi utama dari *Token Exchange Edge Proxy*?
   - A. Mengompresi aset JavaScript dokumentasi agar waktu loading di bawah 100ms.
   - B. Mengganti token sesi sementara pengguna dengan kredensial sandbox staging yang berhak akses terbatas di layer Edge tanpa mengekspos rahasia produksi ke browser.
   - C. Mengonversi kode Python menjadi binary WebAssembly secara otomatis.
   - D. Menerjemahkan dokumentasi bahasa Inggris ke bahasa Indonesia secara real-time.
   *Jawaban yang benar: B*

8. Apa keuntungan utama format OpenAPI 3.1.0 dibandingkan OpenAPI 3.0.0 dalam arsitektur dokumentasi Autonomous Agent?
   - A. OpenAPI 3.1.0 sepenuhnya kompatibel dengan JSON Schema Draft 2020-12, memudahkan validasi payload *Agent Tool* secara native tanpa konversi skema.
   - B. OpenAPI 3.1.0 menghapus seluruh kebutuhan penulisan deskripsi endpoint.
   - C. OpenAPI 3.1.0 memungkinkan eksekusi kode C++ langsung di browser.
   - D. OpenAPI 3.1.0 tidak lagi menggunakan format data JSON atau YAML.
   *Jawaban yang benar: A*

9. Ketika merancang chunking untuk pencarian semantik (Vector Search) pada dokumentasi AI, strategi pemotongan manakah yang menghasilkan akurasi *retrieval* paling optimal bagi LLM?
   - A. Pemotongan acak setiap 500 karakter tanpa memedulikan batas kalimat.
   - B. Pemotongan berbasis hirarki Markdown AST (Heading H2/H3 sebagai batas kontekstual mandiri).
   - C. Menggabungkan seluruh file dokumentasi menjadi satu chunk raksasa sebesar 500.000 token.
   - D. Hanya menyimpan judul file tanpa menyertakan isi konten dokumentasi ke dalam vector database.
   *Jawaban yang benar: B*

10. Jika build pipeline dokumentasi enterprise Anda memakan waktu 45 menit karena menguji 2.000 snippet kode, optimasi arsitektural mana yang paling efisien diterapkan pertama kali?
    - A. Mematikan seluruh pipeline pengujian kode dan mengandalkan laporan bug manual dari pengguna.
    - B. Menerapkan *Content Hashing Cache*; hanya mengeksekusi snippet yang SHA-256 hash teksnya berubah dibanding commit sebelumnya di branch target.
    - C. Menghapus 90% kode contoh dari dokumentasi agar build lebih cepat.
    - D. Mengonversi seluruh repositori dokumentasi ke file PDF statis.
    *Jawaban yang benar: B*

---

### 15.3. Skenario Kasus Produksi

#### Skenario 1
Sebuah platform Autonomous Agent merilis endpoint API baru untuk streaming respons reasoning (`text/event-stream`). Dokumentasi MDX mereka menyertakan contoh kode Python menggunakan library SDK internal. Setelah rilis ke production, puluhan developer melaporkan bahwa script contoh tersebut mengalami *hang* tanpa batas (*infinite blocking*) saat dijalankan di mesin lokal mereka.
- **Analisis Masalah**: Mengapa pipeline validasi dokumentasi biasa gagal mendeteksi bug ini, dan bagaimana arsitektur CDV harus diperbaiki?
- **Rekomendasi Arsitektur**: Pipeline dokumentasi lama hanya menguji sintaksis (`ast.parse`) atau mengeksekusi fungsi synchronous. SDK streaming membutuhkan handling event loop async yang aktif. CI pipeline wajib menerapkan **Assertion Timeout Guard** (misal: maksimal 5 detik per eksekusi snippet) dan menyertakan mock stream emitter yang memverifikasi bahwa *generator* atau *async iterator* kode contoh benar-benar mengonsumsi stream hingga event penutup (`[DONE]`).

#### Skenario 2
Perusahaan Anda melayani pelanggan perbankan enterprise yang melarang keras developer mereka terhubung ke internet saat mencoba API sandbox. Dokumentasi Anda sebelumnya menggunakan cloud remote server container untuk playground API.
- **Rekomendasi Solusi**: Rancang migrasi arsitektur dokumentasi agar tetap interaktif dalam lingkungan air-gapped/offline.
- **Rekomendasi Arsitektur**: Terapkan arsitektur **Zero-Network In-Browser Isolation**. Bundle seluruh runtime playground menggunakan WebAssembly (WASM) engine (seperti Pyodide untuk Python atau WebContainers untuk Node.js) langsung ke dalam static assets dokumentasi. Siapkan Service Worker lokal yang mengintersepsi HTTP request dari playground dan mengarahkannya ke mock server in-memory yang berjalan sepenuhnya di client browser tanpa transmisi paket keluar mesin pengguna.

#### Skenario 3
Sebuah Autonomous Agent berbasis LLM (seperti AutoGPT/Devin) sering salah memanggil tool `deploy_model` yang ada di dokumentasi Anda karena format tipe data timestamp yang dibutuhkan adalah ISO-8601 (`YYYY-MM-DDTHH:mm:ssZ`), namun contoh di dokumentasi menuliskan string deskriptif `"2024-01-01"`.
- **Rekomendasi Solusi**: Bagaimana mengotomatisasi pencegahan kesalahan format parameter pada dokumentasi machine-readable?
- **Rekomendasi Arsitektur**: Integrasikan **Zod/JSON Schema Format Enforcers** langsung pada AST verification pipeline. Tambahkan constraint `format: "date-time"` pada skema tool parameter di OpenAPI core engine. Pipeline CDV dokumentasi harus secara otomatis mengekstrak snippet JSON contoh di file MDX dan memvalidasinya terhadap skema tersebut. Jika string tidak mematuhi regex ISO-8601, build CI langsung berstatus *FAILED*, mencegah dokumentasi yang ambigu diterbitkan ke endpoint `/llms.txt` atau portal pengembang.

---

## 16. Summary

1. **Dokumentasi adalah Kontrak Rekayasa Perangkat Lunak Aktif**: Dokumentasi modern dalam ekosistem AI dan Autonomous Agents bukan sekadar materi bacaan statis, melainkan antarmuka operasional deterministik yang harus divalidasi, diuji, dan dipelihara dengan standar ketat yang sama seperti kode produksi backend.
2. **Arsitektur Dual-Audience**: Sistem dokumentasi wajib menyediakan dua aliran artefak utama dari satu repositori sumber terpadu: antarmuka visual kaya fitur dan ergonomis untuk *Human Developers*, serta antarmuka berdensitas token tinggi, deterministik, dan bebas derau (`llms.txt`, MCP tool schema, AST chunks) untuk *Autonomous AI Agents*.
3. **Continuous Documentation Verification (CDV)**: Menjamin bahwa zero broken code snippets mencapai production melalui eksekusi kode berbasis AST parsing, validasi skema OpenAPI/Zod, dan isolasi lingkungan pengujian secara terotomatisasi di dalam CI/CD pipeline.
4. **Keamanan & Efisiensi Runtime**: Playground interaktif modern menggeser beban komputasi dari server terpusat ke browser lokal via WebAssembly (WASM), sekaligus melindungi rahasia API produksi melalui implementasi Token Exchange Edge Proxy.
5. **Observabilitas Aktif**: Menghubungkan telemetri dokumentasi (copy failures, retrieval miss, runtime exceptions) ke siklus pengembangan produk memastikan bahwa Developer Experience (DevEx) terus meningkat secara terukur dan berkelanjutan.