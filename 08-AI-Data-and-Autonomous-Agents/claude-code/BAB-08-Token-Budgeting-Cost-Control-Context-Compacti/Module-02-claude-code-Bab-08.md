# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 08: Token Budgeting, Cost Control & Context Compaction pada Claude Code**
**Kategori: 08-AI-Data-and-Autonomous-Agents**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, engineer diharapkan mampu:
1. **Menganalisis dan Memetakan Topologi Token API Claude**: Menguraikan struktur konsumsi token (*input*, *output*, *cache write*, *cache read*) pada interaksi siklik agen otonom *Claude Code*.
2. **Merancang Sistem Prompt Caching Determininstik**: Mengimplementasikan *checkpoint prefix matching* dengan efisiensi *cache hit rate* di atas $80\%$ untuk menghemat biaya inferensi hingga $75\%$.
3. **Membangun Context Compaction Engine**: Mengembangkan algoritma pemadatan konteks berlapis (*AST pruning*, *lossless command truncation*, dan *hierarchical micro-agent summarization*) untuk mencegah fenomena *context degradation* dan *lost-in-the-middle*.
4. **Mengimplementasikan Token Budgeting & Circuit Breaker**: Menyusun arsitektur *reverse proxy gateway* dengan algoritma *Leaky Bucket/Token Bucket* guna membatasi pembengkakan biaya per *developer*, *task*, maupun *CI/CD pipeline run*.
5. **Menerapkan Dynamic Model Routing**: Mengarahkan eksekusi subtugas Claude Code secara adaptif (misal: Claude 3.5 Haiku untuk *exploration/summarization* dan Claude 3.5 Sonnet untuk *synthesis/refactoring*) demi optimasi rasio *cost-to-performance*.

---

## 2. Prerequisite

Sebelum memulai modul ini, peserta wajib memahami:
* **Arsitektur Claude Code CLI**: Mekanisme kerja dasar agen terminal Anthropic, pemanggilan *tools* (`Bash`, `FileEdit`, `Glob`, `Grep`), dan siklus *Agentic Loop* (ReAct pattern).
* **Anthropic Messages API**: Parameter `system`, `messages`, `tools`, serta spesifikasi *Prompt Caching* (`cache_control: {"type": "ephemeral"}`).
* **TypeScript/Node.js Enterprise Level**: Async streams, buffers, AST parser (`@babel/parser` atau `tree-sitter`), dan integrasi Redis.
* **Dasar Tokenisasi LLM**: Konsep Byte-Pair Encoding (BPE), estimasi token, rasio karakter ke token, dan batasan *Context Window* (200k tokens).

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Anatomi Context Window pada Claude Code Agentic Loop
Ketika Claude Code beroperasi, setiap iterasi loop eksekusi mengirimkan ulang akumulasi histori pesan:
$$\text{Total Input Tokens}_{n} = \text{System Prompt} + \sum_{i=1}^{n} (\text{User Prompt}_i + \text{Tool Calls}_i + \text{Tool Results}_i)$$

Tanpa intervensi, konsumsi token bersifat kuadratik terhadap panjang iterasi ($O(n^2)$ secara kumulatif biaya).

```
Iterasi 1: [System] + [User] -------------------------> 2,000 tokens
Iterasi 2: [System] + [User] + [Tool 1] + [Result 1] -> 6,500 tokens
Iterasi 3: [System] + [User] + ... + [Result 2] ------> 18,000 tokens (Misal: cat log file)
Iterasi N: [System] + [User] + ... + [Result N-1] ----> 120,000+ tokens
```

### 3.2 Internal Anthropic Prompt Caching Mechanics
Fitur *Prompt Caching* Anthropic memungkinkan persistensi state konteks di server Anthropic selama *Time-To-Live* (TTL) 5 menit (diperbarui setiap kali terjadi cache hit). 

* **Ketentuan Minimal Caching**:
  * Claude 3.5 Sonnet & Claude 3 Opus: Minimal prefix sepanjang **1.024 token**.
  * Claude 3.5 Haiku: Minimal prefix sepanjang **2.048 token**.
* **Struktur Breakpoint**: Maksimal **4 breakpoint** eksplisit (`cache_control: {"type": "ephemeral"}`) per request.
* **Ekonomi Biaya Token**:
  * *Base Input Token*: 100% harga standar.
  * *Cache Write Token*: 125% harga standar (dikenakan hanya saat inisialisasi atau cache miss).
  * *Cache Read Token*: **10% - 25%** harga standar (diskon 75%–90%).

Untuk mempertahankan integritas cache pada Claude Code, urutan buffer context harus deterministik. Setiap perubahan 1 karakter pada token awal akan membatalkan (*invalidate*) seluruh cache di belakangnya (*prefix matching strictness*).

```
Prefix Stabil (Cache Hit):
[System Prompt + Static Rules] -> [Cache Breakpoint 1]
[Large Codebase Definitions]   -> [Cache Breakpoint 2]
------------------------------------------------------
Dynamic Tail (Cache Miss / Write):
[User Intent] -> [Tool Invocation Iteration N] -> [Recent Observations]
```

### 3.3 Context Compaction Layer Architecture
Pemadatan konteks (*Context Compaction*) bukan sekadar melakukan *trimming* teks acak. Modul enterprise membagi pemadatan menjadi 3 layer:

1. **Deterministic Filter (Lossless Layer)**:
   * Menghilangkan output terminal yang redundan (contoh: *progress bar*, escape ANSI color code, *warning logs* duplikat).
   * Memotong pesan hasil eksekusi *unit test* yang sukses, hanya mempertahankan *summary status* dan *stack trace* jika terjadi *failure*.
2. **Structural Pruning (AST/Grammar Layer)**:
   * Mengonversi source code file yang dimuat ke dalam memori menjadi representasi antarmuka/signature (*skeletonization*) menggunakan Tree-sitter jika file tersebut hanya dirujuk sebagai dependensi dan tidak sedang diedit secara langsung.
3. **Semantic Micro-Compaction (Lossy Layer)**:
   * Ketika context mencapai batas ambang kritis (misal $70\%$ dari context window / 140k token), *background worker* (menggunakan Claude 3.5 Haiku) merangkum percakapan iterasi lama menjadi dokumen *state transition snapshot*:
     * *Completed Subtasks*
     * *Modified Files & Diff Summary*
     * *Active Constraints & Remaining Objectives*

### 3.4 Token Budgeting State Machine & Circuit Breaker
Arsitektur produksi menerapkan State Machine bertingkat untuk mencegah insiden *infinite loop* atau *budget overrun*:

```
[Normal Execution] 
       │
       ▼ (Cost >= 50% Threshold)
[Warning State] ──> Notify Developer & Metric Collector
       │
       ▼ (Cost >= 80% Threshold)
[Aggressive Compaction] ──> AST Skeletonization & Strict Output Trimming
       │
       ▼ (Cost >= 100% Threshold OR Tool Loop Count >= Max)
[Circuit Breaker Tripped] ──> Suspend Agent, Write Checkpoint, Require Human-in-the-Loop Signoff
```

---

## 4. Why & What

| Dimensi | Pendekatan Naif (Default Claude Code) | Enterprise Context-Engineered |
| :--- | :--- | :--- |
| **Biaya per Task Kompleks** | Rentan bengkak hingga $5–$25 per refactoring task akibat log bash panjang dan context leakage. | Dibatasi secara stabil pada $0.40–$1.50 per task menggunakan *deterministic caching* dan *compaction*. |
| **Stabilitas Penalaran** | Mengalami *Attention Saturation* & *Lost-in-the-middle* saat percakapan melebihi 100k token. | Tingkat retensi instruksi tinggi karena token aktif dipertahankan < 40k token efektif. |
| **Cache Efficiency** | Sering terjadi *cache invalidation* karena output *system clock*, UUID dinamis, atau urutan tools acak. | *Prefix isolation*: Bagian statis dan dinamis dipisahkan secara ketat via breakpoint deterministik. |
| **Operasional Tim** | Risiko akun developer membakar kuota bulanan perusahaan dalam hitungan jam. | *Multi-tenant Token Gateway* dengan kuota berbasis per-PR, per-developer, dan *kill-switch* otomatis. |

---

## 5. How (Workflow Detail)

Alur kerja Context Compaction dan Budgeting Gateway pada siklus eksekusi Claude Code:

```
[Claude Code Client CLI]
         │
         │  1. HTTP Request (Tool Execution Result / Next Loop)
         ▼
┌────────────────────────────────────────────────────────┐
│             Enterprise Token Proxy Gateway             │
│                                                        │
│  [Step A: Token Counter & Budget Quota Check]          │
│           └─> Breaker Tripped? ── Yes ──> Emit Error   │
│           └─> No                                       │
│                                                        │
│  [Step B: Tool Output Normalizer & Filter]             │
│           └─> Strip ANSI, Truncate Log Files > 2KB     │
│                                                        │
│  [Step C: AST Pruner (Jika Source Code Injected)]      │
│           └─> Parse via Tree-Sitter -> Emit Skeleton   │
│                                                        │
│  [Step D: Context Compaction Evaluator]                │
│           └─> Token count > 140k?                      │
│                 ├─> Run Haiku Summarizer Engine        │
│                 └─> Re-write context history payload   │
│                                                        │
│  [Step E: Deterministic Prompt Cache Inserter]         │
│           └─> Assign cache_control di Prefix & System  │
└────────────────────────────────────────────────────────┘
         │
         │  2. Optimized Request with Ephemeral Breakpoints
         ▼
[Anthropic API Server] (Claude 3.5 Sonnet / Haiku)
```

---

## 6. Analogy & Diagram ASCII

### Analogi: Meja Operasi Bedah vs. Tempat Pembuangan Sampah
Bayangkan dokter bedah bekerja di ruang operasi:
* **Pendekatan Naif**: Setiap perban bekas, alat suntik kosong, dan bungkus obat dibiarkan menumpuk di atas meja bedah sepanjang operasi 10 jam. Akhirnya, dokter tidak dapat menemukan pisau bedah karena tertimbun ribuan sampah medis (Lost-in-the-middle / Context exhaustion).
* **Enterprise Compaction**: Asisten bedah membersihkan meja secara instan. Alat yang sudah tidak terpakai dikembalikan ke rak, kotoran disingkirkan, dan hanya instruksi vital serta tanda vital pasien yang terpampang di monitor (High signal-to-noise ratio).

### Diagram Memori Cache Hit vs Miss
```
Memory Address Token Map:
-------------------------------------------------------------------------------------------
[System Prompt + Corporate Standards]  <- Checkpoint 1 (Hit Rate: ~99%) [Cache Read Cost]
[Repository Map + Tree Skeleton]      <- Checkpoint 2 (Hit Rate: ~90%) [Cache Read Cost]
-------------------------------------------------------------------------------------------
[Dynamic Session History: Loop 1..N]  <- Rolling Window (Cache Miss/Write on Change)
[Current Tool Call + Execution Result] <- Dynamic Tail (100% Base Cost)
-------------------------------------------------------------------------------------------
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Dynamic Output Truncator & Token Estimator
Contoh implementasi pemangkasan string output eksekusi tool sebelum dimasukkan ke dalam histori percakapan Claude Code:

```typescript
// Simple Token Estimator & Terminal Output Cleaner (BPE Approximation)
export function sanitizeToolOutput(rawOutput: string, maxTokens: number = 800): string {
  // 1. Bersihkan ANSI escape codes (color codes terminal)
  const cleanText = rawOutput.replace(/[\u001b\u009b][[()#;?]*(?:[0-9]{1,4}(?:;[0-9]{0,4})*)?[0-9A-ORZcf-nqry=><]/g, '');

  // 2. Rule of thumb: ~4 karakter per token untuk teks bahasa Inggris/kode
  const estimatedTokens = Math.ceil(cleanText.length / 4);

  if (estimatedTokens <= maxTokens) {
    return cleanText;
  }

  // 3. Truncation dengan preservasi Head dan Tail (crucial untuk stack trace)
  const headCharLimit = Math.floor((maxTokens * 4) * 0.4);
  const tailCharLimit = Math.floor((maxTokens * 4) * 0.4);

  const head = cleanText.slice(0, headCharLimit);
  const tail = cleanText.slice(-tailCharLimit);
  const droppedCount = cleanText.length - (headCharLimit + tailCharLimit);

  return `${head}\n\n[... TRUNCATED: ${droppedCount} karakter log diabaikan untuk menghemat token ...]\n\n${tail}`;
}
```

### 7.2 Practical Example: Enterprise Token Gateway & Context Optimizer
Arsitektur production reverse proxy middleware yang mencegat payload Claude Code, menyuntikkan *Prompt Caching*, menerapkan *Budget Guardrail*, dan melakukan *Summarization Compaction*.

```typescript
// src/gateway/context-engine.ts
import Anthropic from '@anthropic-ai/sdk';
import { Request, Response } from 'express';
import Redis from 'ioredis';

interface SessionBudget {
  maxBudgetUSD: number;
  currentCostUSD: number;
  tokenCount: number;
}

export class ClaudeContextGateway {
  private anthropic: Anthropic;
  private redis: Redis;

  // Rasio Biaya per 1M Token (Claude 3.5 Sonnet Snapshot Q4 2024)
  private readonly COST_BASE_INPUT = 3.0 / 1_000_000;
  private readonly COST_CACHE_WRITE = 3.75 / 1_000_000;
  private readonly COST_CACHE_READ = 0.30 / 1_000_000;
  private readonly COST_OUTPUT = 15.0 / 1_000_000;

  constructor() {
    this.anthropic = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });
    this.redis = new Redis(process.env.REDIS_URL || 'redis://localhost:6379');
  }

  public async handleProxyRequest(req: Request, res: Response): Promise<void> {
    const sessionId = req.headers['x-session-id'] as string;
    const body = req.body as Anthropic.Messages.MessageCreateParams;

    try {
      // 1. Circuit Breaker Check
      const budgetOk = await this.enforceBudgetLimit(sessionId);
      if (!budgetOk) {
        res.status(429).json({
          error: {
            type: 'budget_exceeded',
            message: 'Alokasi token/biaya untuk sesi ini telah mencapai batas maksimal.'
          }
        });
        return;
      }

      // 2. Pre-process Payload: Context Sanitization & AST Pruning
      let optimizedMessages = this.pruneToolExecutionArtifacts(body.messages);

      // 3. Compact History jika konteks mendekati 120k token
      if (this.estimateTokenPayload(optimizedMessages) > 120_000) {
        optimizedMessages = await this.compactConversationHistory(body.system as string, optimizedMessages);
      }

      // 4. Inject Deterministic Ephemeral Cache Breakpoints
      const finalizedPayload = this.injectCacheBreakpoints({
        ...body,
        messages: optimizedMessages
      });

      // 5. Eksekusi Request ke Anthropic API
      const response = await this.anthropic.messages.create(finalizedPayload);

      // 6. Token Accounting & Billing Telemetry
      await this.trackTokenUsage(sessionId, response.usage);

      res.status(200).json(response);
    } catch (error: any) {
      console.error('[Gateway Error]', error);
      res.status(500).json({ error: error.message });
    }
  }

  private enforceBudgetLimit = async (sessionId: string): Promise<boolean> => {
    const data = await this.redis.get(`budget:${sessionId}`);
    if (!data) return true;
    const budget: SessionBudget = JSON.parse(data);
    return budget.currentCostUSD < budget.maxBudgetUSD;
  };

  private pruneToolExecutionArtifacts(messages: Anthropic.Messages.MessageParam[]): Anthropic.Messages.MessageParam[] {
    return messages.map(msg => {
      if (msg.role !== 'user' || !Array.isArray(msg.content)) return msg;

      const processedContent = msg.content.map(block => {
        if (block.type === 'tool_result' && typeof block.content === 'string') {
          // Bersihkan bash output ekstrem (> 4000 karakter)
          return {
            ...block,
            content: this.truncateLogNoise(block.content, 4000)
          };
        }
        return block;
      });

      return { ...msg, content: processedContent };
    });
  }

  private truncateLogNoise(content: string, maxChars: number): string {
    if (content.length <= maxChars) return content;
    const splitIndex = Math.floor(maxChars / 2);
    return `${content.substring(0, splitIndex)}\n\n[... OUTPUT DITRUNCATE SISTEM UNTUK EFISIENSI TOKEN ...]\n\n${content.substring(content.length - splitIndex)}`;
  }

  private estimateTokenPayload(messages: Anthropic.Messages.MessageParam[]): number {
    return Math.ceil(JSON.stringify(messages).length / 3.8);
  }

  private async compactConversationHistory(
    systemPrompt: string, 
    messages: Anthropic.Messages.MessageParam[]
  ): Promise<Anthropic.Messages.MessageParam[]> {
    // Ambil histori lama (kecuali 4 pesan terakhir yang merupakan konteks aktif)
    const activeMessages = messages.slice(-4);
    const staleMessages = messages.slice(0, -4);

    if (staleMessages.length === 0) return messages;

    // Gunakan Claude 3.5 Haiku untuk komparasi dan peringkasan berbiaya rendah
    const summaryResponse = await this.anthropic.messages.create({
      model: 'claude-3-5-haiku-20241022',
      max_tokens: 1500,
      system: 'Ringkas histori interaksi agen otonom menjadi ringkasan faktual teknis. Catat file yang telah dimodifikasi, status pengujian, dan keputusan arsitektural yang diambil. Format dalam bentuk poin terstruktur.',
      messages: staleMessages
    });

    const summaryText = summaryResponse.content[0].type === 'text' ? summaryResponse.content[0].text : '';

    return [
      {
        role: 'user',
        content: `[Konteks Percakapan Dimampatkan]\n${summaryText}`
      },
      {
        role: 'assistant',
        content: 'Dipahami. Saya memegang status progres terbaru dan siap melanjutkan instruksi aktif.'
      },
      ...activeMessages
    ];
  }

  private injectCacheBreakpoints(
    payload: Anthropic.Messages.MessageCreateParams
  ): Anthropic.Messages.MessageCreateParams {
    const copy = { ...payload };

    // Breakpoint 1: System Prompt (Instruksi dasar lingkungan developer)
    if (typeof copy.system === 'string') {
      copy.system = [
        {
          type: 'text',
          text: copy.system,
          cache_control: { type: 'ephemeral' }
        }
      ];
    }

    // Breakpoint 2: Pesan acuan stabil terakhir (sebelum giliran interaksi aktif pengguna)
    if (copy.messages.length > 2) {
      const targetIndex = copy.messages.length - 2;
      const targetMessage = copy.messages[targetIndex];
      
      if (typeof targetMessage.content === 'string') {
        targetMessage.content = [
          {
            type: 'text',
            text: targetMessage.content,
            cache_control: { type: 'ephemeral' }
          }
        ];
      } else if (Array.isArray(targetMessage.content) && targetMessage.content.length > 0) {
        // Tandai block terakhir dari pesan target
        const lastBlockIndex = targetMessage.content.length - 1;
        targetMessage.content[lastBlockIndex] = {
          ...targetMessage.content[lastBlockIndex],
          cache_control: { type: 'ephemeral' }
        };
      }
    }

    return copy;
  }

  private async trackTokenUsage(sessionId: string, usage: Anthropic.Messages.Usage): Promise<void> {
    const cacheRead = (usage as any).cache_read_input_tokens || 0;
    const cacheWrite = (usage as any).cache_creation_input_tokens || 0;
    const standardInput = usage.input_tokens;
    const output = usage.output_tokens;

    const requestCostUSD = 
      (standardInput * this.COST_BASE_INPUT) +
      (cacheWrite * this.COST_CACHE_WRITE) +
      (cacheRead * this.COST_CACHE_READ) +
      (output * this.COST_OUTPUT);

    const key = `budget:${sessionId}`;
    await this.redis.eval(`
      local data = redis.call('get', KEYS[1])
      if data then
        local obj = cjson.decode(data)
        obj.currentCostUSD = obj.currentCostUSD + tonumber(ARGV[1])
        obj.tokenCount = obj.tokenCount + tonumber(ARGV[2])
        redis.call('set', KEYS[1], cjson.encode(obj))
      end
    `, 1, key, requestCostUSD.toString(), (standardInput + cacheRead + cacheWrite + output).toString());
  }
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario Kasus: FinTech Monolith Code Migration
* **Institusi**: PT Bank Digital Terbuka (FinTech Banking Infrastructure).
* **Lingkup Proyek**: Refactoring 240 file modul core payment dari JavaScript CommonJS ke TypeScript Strict Typing menggunakan armada Claude Code CLI pada CI/CD runners.
* **Insiden Tanpa Guardrail**:
  * Pada eksekusi minggu pertama, 1 runner CI/CD mengalami *test-failure loop*. Claude Code mengeksekusi `npm test`, menerima *stack trace* setebal 14.000 baris, mengulangi loop perbaikan dan pengujian hingga 45 kali berturut-turut.
  * *Context window* menyentuh 195.000 token per *request*. Tanpa *prompt caching*, tiap iterasi membakar \$0.60 per panggil.
  * Satu job pipeline menghabiskan **\$640** dalam 2 jam tanpa hasil refactoring yang valid (mengalami halusinasi sintaksis akibat *noise saturation*).

### Implementasi Solusi Arsitektur
1. **Penerapan Tool Output Sanitizer**: Output dari Jest dipangkas via custom CLI hook Claude Code, mengecualikan test-cases yang *Passed*, dan menyisakan hanya *Failed Assertions* maksimal 1.500 karakter.
2. **Ephemeral Prompt Caching**: Definisi `.d.ts` core banking dan `package.json` diposisikan sebagai blok referensi statis di-cache (`cache_control`).
3. **Hard Token Limiter**: Setiap PR dialokasikan batas maksimum biaya **\$3.50**. Jika batas ini dicapai, proses otomatis di-abort, menghasilkan git patch parsial dan memicu peringatan ke Slack tim platform.

### Metrik Hasil Evaluasi Produksi (Setelah 1 Bulan)

| Metrik Kinerja | Sebelum Implementasi | Sesudah Implementasi | Deviasi / Efisiensi |
| :--- | :--- | :--- | :--- |
| Rata-rata Biaya per Pull Request | \$18.40 | \$2.15 | **-88.3% Biaya** |
| Cache Hit Rate | 0% (Disable/Misaligned) | 86.4% | **+86.4% Rasio Cache** |
| Rata-rata Durasi Sesi ReAct | 48 menit | 14 menit | **3.4x Lebih Cepat** |
| Kasus Infinite Loop / Overrun | 14 insiden / minggu | 0 insiden (Circuit breaker trip) | **Zero Runaway Incidents** |

---

## 9. Trade-offs (Performance, Latency, Scalability, Cost)

```
              [COST OPTIMIZATION]
                     ▲
                    / \
                   /   \
                  /     \
                 /       \
[LATENCY & SPEED] ═════════ [REASONING ACCURACY]
```

1. **Agresivitas Context Compaction vs Reasoning Accuracy**:
   * *Trade-off*: Mengubah kode menjadi representasi AST skeleton secara drastis menghemat token, namun jika detail implementasi internal fungsi terhapus, model berisiko melakukan halusinasi tanda tangan parameter atau salah memanggil fungsi privat internal.
2. **Micro-agent Summarization vs Execution Latency**:
   * *Trade-off*: Memanggil Claude 3.5 Haiku untuk meringkas histori pesan saat mencapai batas 120k token menghemat jutaan token input berikutnya, namun menambah *latency penalty* sebesar 1.5–3 detik pada *gateway* di putaran iterasi tersebut.
3. **Prompt Caching Read Savings vs Cold-Start Cache Write Overhead**:
   * *Trade-off*: Penulisan cache dikenakan biaya $125\%$ dari harga dasar. Jika alur percakapan hanya berlangsung 1 iterasi (pendek), penggunaan cache justru lebih mahal $25\%$ dibanding tanpa cache. Prompt caching hanya memberikan ROI positif pada iterasi berkelanjutan ($\ge 2$ panggilan dengan prefix identik).

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Kesalahan Umum (Anti-Patterns)
* **Dynamic Content Injection pada System Prompt**: Memasukkan `Date.now()`, path absolut lokal dinamis (`/Users/john/...`), atau Git commit hash terkini ke dalam System Prompt. Hal ini mengubah prefix awal dan merusak (*bust*) seluruh alur *Prompt Cache*.
* **Naive Sliding Window Truncation**: Menghapus pesan pertama secara acak dari histori percakapan ketika mendekati limit. Ini sering kali menghapus instruksi inti pengguna (*initial task intent*), menyebabkan Claude melupakan tujuan utama tugasnya.
* **Unbounded Tool Execution Buffers**: Membiarkan eksekusi perintah seperti `cat big_data.json` atau `find .` menyemburkan 100.000 baris ke terminal STDOUT tanpa filter pagination/truncation.

### 10.2 Panduan Troubleshooting Masalah Produksi

| Gejala Masalah | Penyebab Utama (*Root Cause*) | Solusi Arsitektural |
| :--- | :--- | :--- |
| `cache_read_input_tokens` bernilai `0` meskipun cache breakpoint terpasang. | 1. Panjang prefix di bawah ambang minimum (1.024 token untuk Sonnet).<br>2. Karakter string pada pesan sebelumnya berubah (spasi, newline, atau variable dinamis). | Pastikan payload stabil minimal 1.024 token dan tempatkan seluruh parameter waktu di pesan terminal paling akhir. |
| Model terus-menerus mengulang perintah bash yang sama (*Tool Execution Loop*). | Output log dari tool tidak memberikan indikasi kegagalan yang jelas karena terpotong secara salah, sehingga model mengira perintah belum tereksekusi. | Gunakan pola *Smart Truncation*: jangan potong exit code `$?` dan cuplikan akhir STDERR. |
| Gateway melempar `400 Bad Request: cache_control can only be applied to up to 4 blocks`. | Injector middleware menyematkan tanda breakpoint pada setiap pesan percakapan. | Batasi injection algoritma: Maksimal 1 pada System Prompt, dan maksimal 3 pada giliran pesan terbaru. |

---

## 11. Best Practices (Production Checklist)

- [ ] **Prefix Isolation**: Pastikan konten statis (System Prompt, Aturan Coding Perusahaan, Skema Arsitektur) berada di urutan teratas, diikuti oleh `cache_control: {"type": "ephemeral"}`.
- [ ] **Sanitasi Tool Result**: Pasang batas hard-limit sebesar 3.000 karakter pada output tool `Bash`, `Grep`, dan `Read` dengan *head-and-tail preservation*.
- [ ] **Cost-Attribution Tracking**: Pasang header metadata unik pada setiap panggilan (`x-developer-id`, `x-repository`, `x-ticket-key`) untuk keperluan pemantauan metrik FinOps internal.
- [ ] **Dual-Model Tiering**: Konfigurasikan Haiku untuk pra-pemrosesan pencarian direktori/AST parsing, dan delegasikan Sonnet murni untuk manipulasi penulisan kode sumber.
- [ ] **Fail-Safe Circuit Breaker**: Setel pagu biaya keras per sesi (contoh: \$5 per sesi interaktif lokal, \$2 per runner CI/CD otonom).
- [ ] **State Checkpointing**: Simpan state percakapan terkompaksi ke storage persisten (Redis/Postgres) setiap 5 iterasi untuk memfasilitasi *resumption* tanpa re-evaluasi dari awal.

---

## 12. Hands-on Practice

Dalam sesi praktikum ini, kita akan membangun modul *Context Compressor & Prompt Caching Gateway* sederhana menggunakan Node.js dan TypeScript.

### Struktur Direktori
```
hands-on/m02/
├── package.json
├── tsconfig.json
├── .env.example
└── src/
    ├── index.ts
    ├── normalizer.ts
    └── compactor.ts
```

### Langkah 1: Inisialisasi Proyek & Dependensi
Simpan ke `hands-on/m02/package.json`:
```json
{
  "name": "claude-code-token-optimizer",
  "version": "1.0.0",
  "private": true,
  "main": "dist/index.js",
  "scripts": {
    "build": "tsc",
    "start": "ts-node src/index.ts"
  },
  "dependencies": {
    "@anthropic-ai/sdk": "^0.33.1",
    "dotenv": "^16.4.7"
  },
  "devDependencies": {
    "@types/node": "^22.0.0",
    "ts-node": "^10.9.2",
    "typescript": "^5.6.3"
  }
}
```

Simpan ke `hands-on/m02/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "CommonJS",
    "moduleResolution": "node",
    "outDir": "./dist",
    "rootDir": "./src",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true
  }
}
```

### Langkah 2: Log Normalizer Utility
Simpan ke `hands-on/m02/src/normalizer.ts`:
```typescript
export class Normalizer {
  public static cleanBashOutput(output: string, maxLimit: number = 1000): string {
    // 1. Strip ANSI codes
    const stripped = output.replace(/\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])/g, '');

    if (stripped.length <= maxLimit) {
      return stripped;
    }

    const half = Math.floor(maxLimit / 2);
    const head = stripped.substring(0, half);
    const tail = stripped.substring(stripped.length - half);

    return `${head}\n\n[--- TRUNCATED OLEH TOKEN OPTIMIZER (Mengurangi ${stripped.length - maxLimit} Karakter) ---]\n\n${tail}`;
  }
}
```

### Langkah 3: Eksekutor Pipeline Uji
Simpan ke `hands-on/m02/src/index.ts`:
```typescript
import Anthropic from '@anthropic-ai/sdk';
import { Normalizer } from './normalizer';
import * as dotenv from 'dotenv';
dotenv.config();

const anthropic = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY || 'dummy_key'
});

async function runDemo() {
  console.log('=== MEMULAI DEMO PROMPT CACHING & COMPACTION ===\n');

  // Simulasi System Prompt berukuran besar (> 1024 token agar memenuhi syarat Cache Sonnet)
  const baseCorporateContext = 'PANDUAN_ARSITEKTUR_ENTERPRISE_SECURE_CODING_RULES:\n' + 
    '1. Setiap fungsi wajib memiliki penanganan error terpusat.\n' +
    '2. Dilarang menggunakan library di luar whitelist.\n' +
    '3. Semua input wajib divalidasi via Zod schema runtime.\n' +
    'DOKUMEN_STANDAR_DEVIASI_REGULASI_INTERNAL_V4:'.repeat(70); // Memastikan panjang > 1024 token

  // Simulasi log output masif dari eksekusi tool bash
  const rawLogOutput = '2024-11-04 10:00:01 [DEBUG] Processing line items...\n'.repeat(300) +
                       '2024-11-04 10:00:02 [FATAL] Database connection failed at pg_catalog.pool:5432!\n' +
                       '2024-11-04 10:00:03 [DEBUG] Retrying attempt 1...\n'.repeat(50);

  // Normalisasi output
  const sanitizedOutput = Normalizer.cleanBashOutput(rawLogOutput, 800);

  console.log(`Panjang Log Asli   : ${rawLogOutput.length} Karakter`);
  console.log(`Panjang Log Cleaned: ${sanitizedOutput.length} Karakter\n`);

  const messagesPayload: Anthropic.Messages.MessageParam[] = [
    {
      role: 'user',
      content: 'Tolong analisis error pada eksekusi bash runner berikut.'
    },
    {
      role: 'assistant',
      content: 'Silakan lampirkan log terminalnya.'
    },
    {
      role: 'user',
      content: [
        {
          type: 'text',
          text: sanitizedOutput,
          cache_control: { type: 'ephemeral' } // Breakpoint pada pesan historis
        },
        {
          type: 'text',
          text: 'Apa akar masalahnya dan bagaimana rekomendasi perbaikannya?'
        }
      ]
    }
  ];

  try {
    console.log('Mengirim Request 1 (Inisialisasi Cache Write)...');
    const res1 = await anthropic.messages.create({
      model: 'claude-3-5-sonnet-20241022',
      max_tokens: 300,
      system: [
        {
          type: 'text',
          text: baseCorporateContext,
          cache_control: { type: 'ephemeral' } // Breakpoint System Prompt
        }
      ],
      messages: messagesPayload
    });

    console.log('Penggunaan Token Request 1:');
    console.log(`- Base Input Tokens        : ${res1.usage.input_tokens}`);
    console.log(`- Cache Creation (Write)   : ${(res1.usage as any).cache_creation_input_tokens || 0}`);
    console.log(`- Cache Read Tokens        : ${(res1.usage as any).cache_read_input_tokens || 0}`);
    console.log(`- Output Tokens            : ${res1.usage.output_tokens}\n`);

    console.log('Mengirim Request 2 dengan Prefix yang Sama (Menguji Cache Hit)...');
    const res2 = await anthropic.messages.create({
      model: 'claude-3-5-sonnet-20241022',
      max_tokens: 300,
      system: [
        {
          type: 'text',
          text: baseCorporateContext,
          cache_control: { type: 'ephemeral' }
        }
      ],
      messages: [
        ...messagesPayload,
        {
          role: 'assistant',
          content: res1.content[0].type === 'text' ? res1.content[0].text : ''
        },
        {
          role: 'user',
          content: 'Buatkan script mitigasi cepat berbasis bash!'
        }
      ]
    });

    console.log('Penggunaan Token Request 2:');
    console.log(`- Base Input Tokens        : ${res2.usage.input_tokens}`);
    console.log(`- Cache Creation (Write)   : ${(res2.usage as any).cache_creation_input_tokens || 0}`);
    console.log(`- Cache Read Tokens        : ${(res2.usage as any).cache_read_input_tokens || 0} (BERHASIL DIHEMAT!)`);
    console.log(`- Output Tokens            : ${res2.usage.output_tokens}\n`);

  } catch (err: any) {
    console.error('API Call Error:', err.message);
  }
}

runDemo();
```

---

## 13. Exercise

### Tingkat Easy
Modifikasi kelas `Normalizer` di `hands-on/m02/src/normalizer.ts` agar mendeteksi keberadaan JSON berukuran besar pada output bash. Jika JSON tersebut berupa *array of objects* dengan panjang elemen $> 10$, simpan 2 elemen pertama dan 1 elemen terakhir saja, lalu sertakan metadata total elemen yang dipangkas.

### Tingkat Medium
Buat sebuah fungsi evaluasi sliding-window bertajuk `enforceTokenBudget(messages: MessageParam[], maxBudgetTokens: number)` yang menghitung estimasi token saat ini. Jika estimasi melampaui ambang batas, fungsi secara selektif memangkas pesan yang bertipe *intermediate tool call result* tanpa menghapus pesan user asli (*root instructions*).

### Tingkat Hard
Bangun modul integrasi AST Pruner menggunakan `tree-sitter` (atau `@babel/parser`). Modul harus menerima file TypeScript utuh dan menghasilkan representasi *Interface & Signature Only* (menghapus blok implementasi dalam kurung kurawal fungsi `{ ... }` menjadi `{ /* pruned implementation */ }`) untuk disuntikkan ke histori percakapan Claude Code sebagai context referensi hemat token.

---

## 14. Challenge

Rancang arsitektur **Autonomous Agent Deadlock & Cost Explosion Prevention Engine** untuk skenario berikut:
* Sebuah tim platform mengeksekusi Claude Code secara otonom di 100 runner CI paralel untuk memigrasikan repositori legacy sebesar 10 juta baris kode.
* **Tantangan Arsitektural**:
  1. Bagaimana mencegah agen terjebak dalam circular debugging loop (mencoba memperbaiki kode, gagal compile, mencoba sintaks alternatif, gagal lagi) yang dapat menghabiskan ribuan dollar dalam semalam?
  2. Susun skema kompresi konteks stateful terdistribusi menggunakan Redis yang memastikan *cache breakpoint alignment* tetap valid antar multi-container runners tanpa menyebabkan *cold-cache invalidation storm*.
  3. Sajikan desain circuit breaker yang mengombinasikan metrik: laju pertambahan token per menit ($\Delta \text{tokens}/\Delta t$), tingkat variasi diff kode yang dihasilkan (Shannon entropy dari Git diffs), dan akumulasi pengeluaran moneter real-time.

---

## 15. Quiz Evaluasi Pemahaman

### 5 Pertanyaan Konseptual Dasar
1. Berapa ambang minimum token teks stabil yang disyaratkan oleh Anthropic Messages API agar fitur *Prompt Caching* aktif pada model Claude 3.5 Sonnet?
2. Apa yang terjadi terhadap cache buffer yang telah dibuat jika developer mengubah satu karakter tanda baca di awal *System Prompt*?
3. Sebutkan perbedaan persentase kalkulasi biaya token input standar dibandingkan dengan *cache read input token* pada Claude 3.5 Sonnet!
4. Berapa batas maksimum blok penandaan `cache_control` yang diizinkan dalam satu pemanggilan request Anthropic API?
5. Mengapa output terminal dengan escape sequences (ANSI codes) harus dibersihkan secara agresif sebelum disuntikkan kembali ke dalam agent context loop?

### 5 Pertanyaan Intermediate & Troubleshooting
6. Mengapa pendekatan kompresi konteks naif yang menggunakan metode *first-in, first-out (FIFO) drop* berbahaya bagi stabilitas penalaran agen otonom?
7. Jelaskan fenomena "*lost-in-the-middle*" pada LLM dan bagaimana kaitannya dengan akumulasi output eksekusi tool berukuran besar di context window Claude Code!
8. Pada skenario apa penambahan `cache_control: {"type": "ephemeral"}` justru mengakibatkan biaya pemakaian membengkak lebih mahal dibanding tanpa cache?
9. Bagaimana strategi pemangkasan (*pruning*) output log pengujian yang ideal agar tidak menghilangkan akar masalah kegagalan unit test?
10. Sebutkan peran model Claude 3.5 Haiku dalam arsitektur hierarkis pemadatan konteks saat dipadukan dengan Claude 3.5 Sonnet!

### 3 Skenario Kasus Produksi
11. **Skenario A**: Sebuah pipeline migrasi otomatis berjalan selama 40 iterasi. Di iterasi ke-20, cache read turun menjadi 0 token dan biaya per iterasi melonjak 5 kali lipat hingga iterasi selesai. Analisis kemungkinan akar penyebab teknisnya pada lapisan context assembly!
12. **Skenario B**: Tim Anda mendapati bahwa agen Claude Code sering kali lupa tujuan utama tugas (*user objective drift*) setelah mengeksekusi 15 perintah bash eksploratif. Rancang modifikasi struktur payload pesan untuk mengatasi degradasi perhatian tersebut!
13. **Skenario C**: Sebuah bot Claude Code diintegrasikan ke webhook Slack. Beberapa developer iseng memicu query yang meminta bot membaca seluruh folder `node_modules`. Arsitektur pertahanan apa yang harus dipasang pada level interceptor sebelum request mencapai Claude Code agent loop?

---

## 16. Summary

1. **Ekonomi Eksekusi Agen Berulang**: Pada arsitektur otonom seperti Claude Code, konsumsi token terakumulasi secara eksponensial/kuadratik tanpa pembersihan konteks. Mengelola *Context Lifecycle* sama krusialnya dengan mengelola alokasi memori pada sistem operasi.
2. **Determinisme Prompt Caching**: Kunci keberhasilan efisiensi biaya terletak pada *Prefix Alignment*. Tempatkan data yang tidak berubah di posisi teratas, pisahkan dari variabel waktu/acak, dan pertahankan ambang di atas 1.024 token untuk mendapatkan penghematan biaya baca hingga $90\%$.
3. **Penyaringan Konteks Berlapis**: Arsitektur produksi harus menerapkan pemadatan berbasis hierarki: sanitasi artefak terminal (lossless), reduksi AST skelton (struktural), dan peringkasan berkala via Haiku (semantik).
4. **Sistem Pengendalian FinOps**: Agen otonom tanpa circuit breaker adalah liabilitas finansial. Terapkan kuota keras berbasis anggaran biaya, isolasi per-task, dan mekanisme suspensi otomatis untuk menjamin skalabilitas enterprise yang aman.