# Kurikulum Enterprise Engineering: GraphQL Security Hardening (Bab 07 - Modul 02)

---

## 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Merancang Arsitektur Keamanan Bertingkat (Defense-in-Depth):** Membangun pipeline keamanan GraphQL end-to-end mulai dari edge gateway, execution engine, hingga data access layer.
- **Mengimplementasikan Algoritma AST Analysis Tingkat Lanjut:** Mengembangkan custom validation rules berbasis GraphQL AST (*Abstract Syntax Tree*) untuk mencegah *Recursive DoS*, *Field Duplication/Alias-based Batching*, dan *Circular Relationship Exploitation*.
- **Membangun Dynamic Query Cost & Complexity Analysis:** Menghitung bobot kompleksitas query secara statis dan dinamis dengan mempertimbangkan argumen pagination (`first`, `limit`), nested cost multiplier, dan field weights.
- **Mencegah Broken Object-Level Authorization (BOLA/IDOR):** Menerapkan granular access control (RBAC/ABAC) langsung pada resolver layer menggunakan scoped execution context tanpa mengorbankan performa DataLoader.
- **Mengimplementasikan Strict Allowlisting & Safe Production APQ:** Mengonfigurasi *Automatic Persisted Queries* (APQ) dalam mode strict/whitelist-only untuk menutup total vektor serangan eksploitasi query arbitrary dari publik.
- **Mendesain Enterprise Error Masking & Audit Logging:** Menyaring kebocoran informasi internal schema/database pada response payload sembari mempertahankan korelasi log (`trace_id`) untuk incident response.

---

## 2. Prerequisites
Sebelum mempelajari modul ini, Anda harus memahami:
- **GraphQL Execution Engine Internals:** Fase parsing (Lexer/Parser), Document AST, Validation Rules, dan Execution Lifecycle (`execute`, `resolveField`).
- **TypeScript & Node.js Asynchronous Runtime:** Mahir dalam manipulasi object, functional programming, dan handling promise/microtasks.
- **Konsep Keamanan OWASP Top 10 API Security:** Khususnya BOLA/IDOR, Broken Function Level Authorization, Unrestricted Resource Consumption, dan Security Misconfiguration.
- **Arsitektur Distributed Gateway:** Pemahaman dasar mengenai reverse proxy (Envoy, Kong, atau NGINX) dan middleware composition patterns (Envelop/Yoga/Apollo plugins).

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 GraphQL Execution Lifecycle & Attack Vectors
Keunikan GraphQL—di mana klien menentukan bentuk dan volume data—secara fundamental menggeser paradigma keamanan REST:

```
[HTTP Request] 
      │ (Raw Body String)
      ▼
┌──────────────┐
│ Parse Phase  │ ──► Denial of Service: Lexer memory exhaust (String bomb, directive flood)
└──────┬───────┘
       │ (DocumentNode AST)
       ▼
┌──────────────┐
│ Validate     │ ──► Attack Surface: Deep nesting, cyclic references, alias-based batching
└──────┬───────┘
       │ (Validated AST)
       ▼
┌──────────────┐
│ Execute      │ ──► Attack Surface: BOLA/IDOR, N+1 exhaustion, slow-resolving resolvers
└──────┬───────┘
       │ (ExecutionResult)
       ▼
┌──────────────┐
│ Format/Send  │ ──► Attack Surface: Stack trace leakage, schema reconnaissance
└──────────────┘
```

### 3.2 AST Parsing dan Intersepsi Validasi
Sebelum resolver mana pun dieksekusi, GraphQL engine mengubah payload query menjadi AST (`DocumentNode`). AST ini dievaluasi oleh serangkaian fungsi predikat (`ValidationRule`) yang menggunakan **Visitor Pattern**.

```
Query: { user { id name } }

AST Hierarchy:
DocumentNode
 └── OperationDefinitionNode (query)
      └── SelectionSetNode
           └── FieldNode (name: "user")
                └── SelectionSetNode
                     ├── FieldNode (name: "id")
                     └── FieldNode (name: "name")
```

Serangan denial of service sering kali lolos dari WAF konvensional karena WAF hanya memeriksa ukuran byte HTTP payload. Query berukuran 2 KB dapat memicu jutaan pemanggilan database jika berisi alias yang diduplikasi atau relasi sirkular:

```graphql
# Alias-based Brute Force / DoS (HTTP payload < 1KB)
query MaliciousQuery {
  a1: login(user: "admin", pass: "123") { token }
  a2: login(user: "admin", pass: "124") { token }
  # ... diduplikasi 5000 kali
  a5000: login(user: "admin", pass: "999") { token }
}
```

Oleh karena itu, mitigasi harus dilakukan pada fase **AST Validation Pipeline**, sebelum request menyentuh thread pool execution resolver.

### 3.3 Dynamic Query Complexity Algorithm
Kompleksitas query dievaluasi dengan formula terbobot:

$$\text{Complexity}(Node) = \text{BaseCost} + (\text{Multiplier} \times \sum \text{Complexity}(ChildNodes))$$

Di mana:
- $\text{BaseCost}$: Bobot intrinsik suatu field (skalar = 1, relasi database/external API = 5-10).
- $\text{Multiplier}$: Nilai argumen pembatas seperti `first`, `limit`, atau default pagination multiplier (misalnya 10 jika klien tidak mengirimkan argumen).

Jika $\text{TotalCost} > \text{MaxAllowedCost}$, query langsung dihentikan pada fase validasi dengan HTTP status 400/GraphQL error tanpa memanggil backend I/O.

---

## 4. Why & What

| Dimensi Masalah | REST API Tradisional | GraphQL Enterprise | Pendekatan Defense GraphQL |
| :--- | :--- | :--- | :--- |
| **Volumetric Protection** | Rate limit berbasis IP/Path (`/api/v1/users`). | Endpoint tunggal (`/graphql`), jutaan variasi payload. | Cost & Depth Analysis pada tingkat AST. |
| **Authorization Check** | Middleware per-route (`canAccess('/admin')`). | Hierarkis & Nested; root lolos, nested node bisa sensitif. | Resolver Context Scoping & Object Capabilities Model. |
| **Reconnaissance** | Terbatas pada Swagger/OpenAPI docs jika dipublikasikan. | Fitur bawaan Introspection mengekspos seluruh data model. | Introspection disablement di produksi & Schema Masking. |
| **Credential Stuffing** | Terdeteksi mudah via hit frequency endpoint `/login`. | Dibungkus dalam 1 request HTTP via multiple aliases. | Field-level Alias Limiting & Single-operation enforcement. |

---

## 5. How (Workflow Detail)

Arsitektur produksi menerapkan alur pertahanan 6-tahap (6-Stage Pipeline):

```
Client Payload
     │
     ▼
[Stage 1: Transport & Envelope Sanitization]
     ├─ Enforce Content-Type: application/json (No GET queries in mutation)
     ├─ Payload Size Limiter (Max: 100 KB)
     │
     ▼
[Stage 2: APQ & Whitelist Interceptor]
     ├─ Cek Query Hash pada Redis Whitelist
     ├─ Jika Hash Valid -> Ambil AST dari Memory -> Langsung ke Stage 4
     ├─ Jika Mode Strict & Hash Tidak Ada -> REJECT (403 Forbidden)
     │
     ▼
[Stage 3: AST Static Analysis Engine]
     ├─ Document Depth Limiter (Max Depth <= 7)
     ├─ Field Alias Counter (Max Alias per Operation <= 5)
     ├─ Static Query Complexity Evaluator (Max Score <= 1000)
     ├─ Directive Blacklisting / Limiter (Mencegah @skip/@include recursion)
     │
     ▼
[Stage 4: Execution & Granular Authorization]
     ├─ Context Construction: Injeksi Scoped User Identity & Permission Engine
     ├─ Resolver Level ABAC: Evaluasi kepemilikan objek (BOLA Guard)
     ├─ DataLoader Batch Isolation: Mencegah cross-tenant cache leakage
     │
     ▼
[Stage 5: Circuit Breaker & Execution Timeout]
     ├─ Resolver Timeout Guard (Abort jika runtime resolver > 2500ms)
     │
     ▼
[Stage 6: Output Sanitization & Audit]
     ├─ Strip `extensions.exception` & Raw Stack Trace
     ├─ Injeksi `extensions.correlationId`
     └─ Emit Audit Log untuk Operasi yang Gagal / Dicurigai
```

---

## 6. Analogy & Diagram ASCII

### Analogi: Bank Brankas Terbuka vs Sistem Tiket Kliring
REST seperti loket perbankan tradisional dengan antrean terpisah per meja: Meja Transfer, Meja Tarik Tunai, Meja Kredit. Setiap meja memiliki satpam dan antrean tersendiri.

GraphQL seperti akses langsung ke Ruang Brankas Pusat (Open-Vault Access). Nasabah menyerahkan secarik instruksi: *"Tolong ambilkan uang dari brankas 1, lalu transfer sebagian ke brankas 2, dan periksa saldo 100 brankas rekanan saya."* Jika petugas kasir langsung mengerjakan tanpa memeriksa beban kerja instruksi tersebut, bank akan kolaps seketika karena kasir terkuras energinya memproses permintaan tunggal yang masif.

Oleh karena itu, sebelum kasir bergerak, dokumen instruksi harus masuk ke **Mesin Kliring (AST Validator)** yang menghitung "biaya energi kerja" (Cost). Jika nilainya melampaui limit kredit nasabah, instruksi dibatalkan seketika.

### Diagram Arsitektur Proteksi GraphQL

```
                     ARSIKTEKTUR HARDENING RUNTIME GRAPHQL
                     
     CLIENT REQUEST
           │
           │  [POST /graphql] { query: "...", variables: {...} }
           ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        EDGE GATEWAY / REVERSE PROXY                    │
│  - IP Rate Limiting (Token Bucket)                                     │
│  - Payload Size Check (< 50KB)                                         │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                       GRAPHQL SECURITY ENGINE                          │
│                                                                        │
│   ┌────────────────────────────────────────────────────────────────┐   │
│   │ 1. INGRESS FILTER: Disabled Introspection (Production Mode)    │   │
│   └──────────────────────────────┬─────────────────────────────────┘   │
│                                  │                                     │
│   ┌──────────────────────────────▼─────────────────────────────────┐   │
│   │ 2. APQ CHECKER: Check SHA256 against Redis Allowlist           │   │
│   └──────────────┬─────────────────────────────────┬───────────────┘   │
│         [Cache Hit: Valid]                   [Cache Miss]              │
│                  │                                 │                   │
│                  │                         Strict Whitelist Mode?      │
│                  │                         ├── YES ──► [403 FORBIDDEN] │
│                  │                         └── NO                      │
│                  │                              │                      │
│                  │                  ┌───────────▼──────────────────┐   │
│                  │                  │ 3. AST DEPTH & COMPLEXITY    │   │
│                  │                  │    - Max Depth: 6            │   │
│                  │                  │    - Max Cost: 500           │   │
│                  │                  │    - Max Aliases: 3          │   │
│                  │                  └───────────┬──────────────────┘   │
│                  │                              │ [Exceeds Limit?]     │
│                  │                              ├── YES ──► [400 ERROR]│
│                  │                              └── NO                 │
│                  │                                  │                  │
│                  └──────────────────┬───────────────┘                  │
│                                     ▼                                  │
│   ┌────────────────────────────────────────────────────────────────┐   │
│   │ 4. EXECUTION LAYER: Granular AuthZ (ABAC / BOLA Protections)   │   │
│   │    - Context: { user: Identity, permissions: Scope[] }         │   │
│   │    - Resolver Guard: verifies resource.tenantId === ctx.tenant │   │
│   └──────────────────────────────┬─────────────────────────────────┘   │
│                                  │                                     │
│   ┌──────────────────────────────▼─────────────────────────────────┐   │
│   │ 5. RESPONSE SHIELD & ERROR MASKING                             │   │
│   │    - Mask raw DB errors (e.g. Postgres PQError)                │   │
│   │    - Generate Sentry / Correlated Trace ID                     │   │
│   └────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                                   ▼
                            DATABASE / SERVICE
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Depth Limiter Rule (Algoritma AST Dasar)
Mencegah query bersarang tanpa batas yang mengeksploitasi relasi circular (contoh: `author -> posts -> author -> posts`).

```typescript
// basicDepthLimiter.ts
import { ValidationContext, ASTVisitor, FieldNode, OperationDefinitionNode } from 'graphql';

export function createDepthLimiter(maxDepth: number) {
  return (context: ValidationContext): ASTVisitor => {
    return {
      OperationDefinition(node: OperationDefinitionNode) {
        const depth = calculateDepth(node, 0);
        if (depth > maxDepth) {
          context.reportError(
            new Error(`Operasi '${node.name?.value || 'anonymous'}' melampaui kedalaman maksimum (${depth} > ${maxDepth})`)
          );
        }
      }
    };
  };
}

function calculateDepth(node: any, currentDepth: number): number {
  if (!node || !node.selectionSet) {
    return currentDepth;
  }
  
  let maxChildDepth = currentDepth;
  for (const selection of node.selectionSet.selections) {
    if (selection.kind === 'Field') {
      const fieldNode = selection as FieldNode;
      // Jangan hitung field meta seperti __typename sebagai nesting level
      if (fieldNode.name.value === '__typename') continue;
      
      const childDepth = calculateDepth(fieldNode, currentDepth + 1);
      if (childDepth > maxChildDepth) {
        maxChildDepth = childDepth;
      }
    }
  }
  return maxChildDepth;
}
```

---

### 7.2 Practical Example: Enterprise Production Security Suite
Implementasi menyeluruh yang mencakup:
1. Dynamic Complexity Analysis dengan argument factor.
2. Alias Guard (mencegah alias credential-stuffing/batching attacks).
3. Resolver Authorization Shield (mencegah BOLA).
4. Secure Error Formatter.

```typescript
// securityEngine.ts
import { 
  ValidationContext, 
  ASTVisitor, 
  FieldNode, 
  GraphQLError, 
  GraphQLResolveInfo 
} from 'graphql';

// -------------------------------------------------------------
// 1. AST Validation Rule: Anti-Alias Batching Rule
// -------------------------------------------------------------
export function createMaxAliasRule(maxAliasesAllowed: number) {
  return (context: ValidationContext): ASTVisitor => {
    let aliasCount = 0;
    return {
      Field(node: FieldNode) {
        if (node.alias) {
          aliasCount++;
          if (aliasCount > maxAliasesAllowed) {
            context.reportError(
              new GraphQLError(
                `Security Violation: Jumlah alias melampaui batas yang diizinkan (Maksimum: ${maxAliasesAllowed}).`,
                { nodes: [node] }
              )
            );
          }
        }
      }
    };
  };
}

// -------------------------------------------------------------
// 2. AST Validation Rule: Query Cost & Complexity Calculator
// -------------------------------------------------------------
interface ComplexityConfig {
  maxCost: number;
  scalarCost: number;
  objectCost: number;
  listFactor: number;
}

export function createComplexityRule(config: ComplexityConfig) {
  return (context: ValidationContext): ASTVisitor => {
    return {
      OperationDefinition(operationNode) {
        let totalCost = 0;

        function traverseSelections(selectionSet: any, multiplier: number) {
          if (!selectionSet) return;

          for (const selection of selectionSet.selections) {
            if (selection.kind !== 'Field') continue;
            const field = selection as FieldNode;

            if (field.name.value === '__typename') continue;

            let currentFieldCost = config.scalarCost;
            let currentMultiplier = multiplier;

            // Evaluasi apakah field memiliki child selections (object/list)
            if (field.selectionSet) {
              currentFieldCost = config.objectCost;
              
              // Cek argumen pembatas seperti `first`, `limit`, dsb
              const limitArg = field.arguments?.find(
                arg => arg.name.value === 'first' || arg.name.value === 'limit'
              );

              if (limitArg && limitArg.value.kind === 'IntValue') {
                const parsedLimit = parseInt(limitArg.value.value, 10);
                currentMultiplier = multiplier * parsedLimit;
              } else {
                currentMultiplier = multiplier * config.listFactor;
              }
            }

            totalCost += currentFieldCost * multiplier;

            if (field.selectionSet) {
              traverseSelections(field.selectionSet, currentMultiplier);
            }
          }
        }

        traverseSelections(operationNode.selectionSet, 1);

        if (totalCost > config.maxCost) {
          context.reportError(
            new GraphQLError(
              `Query rejected: Biaya eksekusi (${totalCost}) melampaui batas maksimum (${config.maxCost}). Batasi pagination Anda.`
            )
          );
        }
      }
    };
  };
}

// -------------------------------------------------------------
// 3. Execution Layer: Scoped ABAC Resolver Shield (BOLA Defense)
// -------------------------------------------------------------
export interface AuthContext {
  user?: {
    id: string;
    organizationId: string;
    role: 'ADMIN' | 'MEMBER' | 'ANONYMOUS';
  };
  correlationId: string;
}

type ResolverFn<TSource = any, TArgs = any, TResult = any> = (
  source: TSource,
  args: TArgs,
  context: AuthContext,
  info: GraphQLResolveInfo
) => Promise<TResult> | TResult;

export function secureResolver<TSource, TArgs, TResult>(
  requiredRole: 'ADMIN' | 'MEMBER',
  resolver: ResolverFn<TSource, TArgs, TResult>,
  ownerCheck?: (source: TSource, args: TArgs, context: AuthContext) => boolean
): ResolverFn<TSource, TArgs, TResult> {
  return async (source, args, context, info) => {
    // Authn Check
    if (!context.user || context.user.role === 'ANONYMOUS') {
      throw new GraphQLError('Unauthorized: Sesi tidak terautentikasi.', {
        extensions: { code: 'UNAUTHENTICATED', http: { status: 401 } }
      });
    }

    // Role Hierarchy Check
    if (requiredRole === 'ADMIN' && context.user.role !== 'ADMIN') {
      throw new GraphQLError('Forbidden: Hak akses tidak memadai.', {
        extensions: { code: 'FORBIDDEN', http: { status: 403 } }
      });
    }

    // BOLA/Tenant Check (Object Capability Verification)
    if (ownerCheck && !ownerCheck(source, args, context)) {
      throw new GraphQLError('Forbidden: Anda tidak memiliki akses ke entitas ini.', {
        extensions: { code: 'FORBIDDEN_OBJECT_ACCESS', http: { status: 403 } }
      });
    }

    return resolver(source, args, context, info);
  };
}

// -------------------------------------------------------------
// 4. Output Layer: Production Safe Error Formatter
// -------------------------------------------------------------
export function formatProductionError(formattedError: any, error: unknown): any {
  const originalError = (error as any)?.originalError || error;
  const correlationId = (error as any)?.extensions?.correlationId || 'N/A';

  // Log error aslinya ke backend monitoring (e.g. Datadog / Pino)
  console.error(`[AUDIT-ERROR] Trace: ${correlationId}`, originalError);

  // Jangan pernah bocorkan internal SQL/driver database error
  const isInternalDriverError = 
    originalError?.name === 'QueryFailedError' || 
    originalError?.name === 'SequelizeDatabaseError' ||
    originalError?.code === 'ECONNREFUSED';

  if (isInternalDriverError) {
    return {
      message: 'Internal server error occurred. Silakan hubungi admin dengan Correlation ID.',
      extensions: {
        code: 'INTERNAL_SERVER_ERROR',
        correlationId
      }
    };
  }

  return {
    message: formattedError.message,
    locations: formattedError.locations,
    path: formattedError.path,
    extensions: {
      code: formattedError.extensions?.code || 'INTERNAL_ERROR',
      correlationId
    }
  };
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: FinTech Global Core Banking API (Insiden Alias-Brute-Force & Recursive Outage)

#### Background
Sebuah bank digital modern meluncurkan super-app yang mengonsumsi GraphQL Gateway terdistribusi. Gateway ini berhadapan langsung dengan publik via Cloud Native Ingress.

#### The Incident
Sistem mendadak mengalami kelumpuhan CPU (100% saturation) pada seluruh cluster GraphQL Gateway dan Database Connection Pool mengalami *exhaustion*. Metrik latensi P99 melonjak dari 45ms ke 18.000ms. Serangan WAF lolos karena traffic rate IP berada di bawah ambang batas (10 request/detik per IP), namun backend memproses setara 50.000 operasi per detik.

#### RCA (Root Cause Analysis)
1. **Alias-based Brute Force:** Penyerang mengirimkan mutasi login dengan 1.000 alias unik dalam satu HTTP request payload berukuran 35KB:
   ```graphql
   mutation {
     a1: transferFunds(toAccount: "HACKER", amount: 1) { status }
     a2: transferFunds(toAccount: "HACKER", amount: 1) { status }
     # ... sampai a1000
   }
   ```
2. **Circular Connection Deep Queries:** Penyerang mengeksekusi:
   ```graphql
   query {
     user {
       accounts {
         transactions {
           account {
             transactions {
               account { transactions { id } }
             }
           }
         }
       }
     }
   }
   ```
   Gateway mengurai hingga kedalaman level 14, memicu ribuan SQL queries ke database karena kurangnya batasan traversal pada AST.
3. **Information Disclosure:** Server membalas error timeout dengan payload lengkap `SequelizeDatabaseError: Connection pool exhausted at Connection.connect...`, membocorkan host internal DB dan arsitektur database.

#### Remediasi Arsitektur
1. **Immediate Patch:** Pemasangan rule `maxAliases(5)` dan `depthLimit(6)` langsung di ingress Apollo Gateway.
2. **Structural Solution:**
   - Implementasi **Strict Persisted Queries**: Di aplikasi mobile/web resmi, seluruh query dikompilasi saat build-time menjadi manifest JSON berisi hash SHA256. Gateway menolak sembarang query string yang tidak terdaftar dalam Redis whitelist.
   - Pemasangan **Cost Analysis Engine**: Kuota biaya per API token dibatasi maksimum 1.000 poin per request.
   - Implementasi **Safe Error Sanitizer**: Menyaring database trace dan menyisipkan UUID korelasi tracing W3C.

---

## 9. Trade-offs & Production Considerations

| Mekanisme Pertahanan | Latency Overhead | Memory Footprint | Developer Experience | False Positive Risk |
| :--- | :--- | :--- | :--- | :--- |
| **AST Depth Limiting** | **Sangat Rendah** (<0.2ms) | Sangat Rendah | Tinggi (Mudah dipahami) | Sedang (Query analitik valid bisa terblokir) |
| **Dynamic Complexity Analysis** | **Rendah - Sedang** (0.5ms - 2ms) | Rendah | Sedang (Perlu kalibrasi bobot tipe dan argumen) | Tinggi (Jika formula pagination tidak selaras dengan UI) |
| **Strict Persisted Queries (APQ)** | **Negatif** (Mempercepat latensi; payload turun drastis) | Sangat Rendah (Key-Value Redis) | Rendah (Butuh sinkronisasi CI/CD frontend-backend) | Nol (Hanya payload yang sah dari repo yang lolos) |
| **Field-level Scoped Resolvers** | **Sangat Rendah** (<0.1ms per field) | Minimal | Menengah (Boilerplate kode resolver bertambah) | Rendah jika unit test ABAC komprehensif |
| **Full Schema Introspection Disable** | Nol | Nol | Menengah (Tooling GraphiQL / Postman developer terhambat) | Rendah (Gunakan staging gateway khusus dev) |

---

## 10. Common Mistakes & Troubleshooting

### Mistake 1: Hanya Mengandalkan Depth Limiting tanpa Complexity Analysis
*Kesalahan:* Mengira kedalaman query rendah aman dari DoS.
*Dampak:* Penyerang mengeksploitasi **Query Breadth**:
```graphql
query FlatBreadthExploit {
  users(first: 1000) { id email }
  merchants(first: 1000) { id balance }
  transactions(first: 1000) { id amount }
}
```
Query di atas hanya memiliki depth 2, namun memproses ribuan row database dan menguras memori Gateway.
*Solusi:* Selalu kombinasikan Depth Limiter dengan dynamic cost analysis yang mengalikan bobot field dengan argumen pembatas (`first`/`limit`).

### Mistake 2: Isolasi BOLA yang Bocor pada Nested Field Resolvers
*Kesalahan:* Menguji permission hanya di Root Query, tetapi tidak di child edge:
```typescript
// VULNERABLE
Query: {
  account: (_, { id }, ctx) => ctx.db.accounts.findById(id), // Ada auth check
},
User: {
  accounts: (parent, _, ctx) => ctx.db.accounts.findByUserId(parent.id) // TIDAK ADA CHECK!
}
```
Jika penyerang bisa mengakses objek `User` orang lain lewat query publik, mereka mengeksploitasi resolver nested `accounts` untuk bypass authorization root.
*Solusi:* Terapkan authorization pada level Data Model atau DataLoader wrapper yang memvalidasi tenant ownership tanpa memedulikan alur masuk traversal.

### Mistake 3: Memory Exhaustion akibat Regex WAF
*Kesalahan:* Menggunakan Regex pada level NGINX/Cloudflare untuk memblokir query GraphQL jahat.
*Dampak:* Karakter whitespace, escape sequence, dan nesting JSON mudah membingungkan regex, atau memicu ReDoS (Regular Expression DoS) pada load balancer.
*Solusi:* Parsing dan validasi harus dilakukan oleh engine yang mengerti AST GraphQL, bukan string regex.

---

## 11. Best Practices (Production Checklist)

### Gateway / Edge Layer
- [ ] Nonaktifkan HTTP GET method untuk Mutation operations.
- [ ] Batasi raw HTTP POST body size (Maksimal 50 KB - 100 KB).
- [ ] Terapkan Strict IP-based Token Bucket Rate Limiting sebelum parsing GraphQL.
- [ ] Matikan Introspection query (`__schema`, `__type`) di lingkungan produksi.

### Engine AST & Validation Layer
- [ ] Pasang `maxDepth` validator (Disarankan: 5 hingga 8 tingkat).
- [ ] Batasi alias eksplisit (`maxAliases` <= 5).
- [ ] Implementasikan query complexity analyzer dengan hard execution budget (misal: budget 1000).
- [ ] Terapkan Persisted Queries secara mutlak (Strict Whitelisting) untuk aplikasi klien publik.
- [ ] Nonaktifkan execution engine jika ada error validasi AST (Default behavior GraphQL-JS).

### Resolver & Data Access Layer
- [ ] Selalu validasi Authorization Context pada level field yang mengembalikan data sensitif (Object-Level Authorization).
- [ ] Gunakan DataLoader untuk membatasi kueri redundan dan cegah memory leak dengan scoped-cache per HTTP request.
- [ ] Terapkan resolver execution timeout (Circuit breaker, misal: max 3 detik per resolver).

### Logging & Error Sanitization
- [ ] Hapus error stack traces, database codes, dan driver errors dari output payload.
- [ ] Lampirkan UUID unik `correlationId` pada setiap error response klien.
- [ ] Simpan full payload audit log hanya untuk query yang diblokir oleh security engine.

---

## 12. Hands-on Practice

Buat dan jalankan modul proteksi GraphQL mandiri di direktori lokal Anda:

### Struktur Direktori:
```
hands-on/m02/
├── package.json
├── tsconfig.json
├── src/
│   ├── rules/
│   │   ├── depthLimiter.ts
│   │   ├── aliasLimiter.ts
│   │   └── complexityLimiter.ts
│   ├── auth/
│   │   └── resolverGuards.ts
│   ├── schema.ts
│   └── server.ts
```

### Langkah 1: Inisialisasi Project & Dependensi
Simpan ke `hands-on/m02/package.json`:
```json
{
  "name": "graphql-security-hardening",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "build": "tsc",
    "start": "ts-node src/server.ts"
  },
  "dependencies": {
    "@graphql-tools/schema": "^10.0.0",
    "express": "^4.19.2",
    "graphql": "^16.8.1",
    "graphql-http": "^1.22.1"
  },
  "devDependencies": {
    "@types/express": "^4.17.21",
    "@types/node": "^20.11.0",
    "ts-node": "^10.9.2",
    "typescript": "^5.3.3"
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
    "rootDir": "src",
    "outDir": "dist",
    "esModuleInterop": true,
    "strict": true,
    "skipLibCheck": true
  }
}
```

### Langkah 2: Buat Custom Security Rules
Simpan ke `hands-on/m02/src/rules/securityRules.ts`:
```typescript
import { ValidationContext, ASTVisitor, FieldNode, GraphQLError } from 'graphql';

export function createProductionSecurityRules(opts: { maxDepth: number; maxAliases: number }) {
  return [
    // 1. Alias Limiter
    (context: ValidationContext): ASTVisitor => {
      let aliases = 0;
      return {
        Field(node: FieldNode) {
          if (node.alias) {
            aliases++;
            if (aliases > opts.maxAliases) {
              context.reportError(
                new GraphQLError(`Security Rule: Melebihi batas maksimal alias (${opts.maxAliases}).`, {
                  nodes: [node]
                })
              );
            }
          }
        }
      };
    },
    // 2. Depth Limiter
    (context: ValidationContext): ASTVisitor => {
      return {
        OperationDefinition(node) {
          const depth = getDepth(node, 0);
          if (depth > opts.maxDepth) {
            context.reportError(
              new GraphQLError(`Security Rule: Query depth (${depth}) melampaui limit (${opts.maxDepth}).`, {
                nodes: [node]
              })
            );
          }
        }
      };
    }
  ];
}

function getDepth(node: any, currentDepth: number): number {
  if (!node || !node.selectionSet) return currentDepth;
  let max = currentDepth;
  for (const s of node.selectionSet.selections) {
    if (s.kind === 'Field' && s.name.value !== '__typename') {
      const d = getDepth(s, currentDepth + 1);
      if (d > max) max = d;
    }
  }
  return max;
}
```

### Langkah 3: Setup Server dan Implementasikan Error Masking
Simpan ke `hands-on/m02/src/server.ts`:
```typescript
import express from 'express';
import { createHandler } from 'graphql-http/lib/use/express';
import { makeExecutableSchema } from '@graphql-tools/schema';
import { createProductionSecurityRules } from './rules/securityRules';
import { randomUUID } from 'crypto';

const typeDefs = `
  type User {
    id: ID!
    username: String!
    privateToken: String!
    profile: Profile
  }

  type Profile {
    bio: String
    user: User
  }

  type Query {
    me: User
    users(first: Int): [User!]!
  }
`;

const resolvers = {
  Query: {
    me: (_: any, __: any, ctx: any) => {
      if (!ctx.user) throw new Error('Unauthenticated');
      return { id: 'usr-1', username: 'john_doe', privateToken: 'secret_123' };
    },
    users: (_: any, { first }: { first?: number }) => {
      const count = first || 2;
      return Array.from({ length: count }, (_, i) => ({
        id: `usr-${i}`,
        username: `user_${i}`,
        privateToken: `secret_${i}`
      }));
    }
  },
  User: {
    profile: (parent: any) => ({ bio: `Bio of ${parent.username}`, user: parent })
  },
  Profile: {
    user: (parent: any) => parent.user
  }
};

const schema = makeExecutableSchema({ typeDefs, resolvers });

const app = express();
app.use(express.json({ limit: '50kb' }));

// Context Factory & Auth Extraction
app.use((req, res, next) => {
  (req as any).context = {
    correlationId: randomUUID(),
    user: req.headers.authorization ? { id: 'usr-1', role: 'MEMBER' } : null
  };
  next();
});

// GraphQL-HTTP Endpoint with Production Rules
app.all(
  '/graphql',
  createHandler({
    schema,
    context: (req) => (req.raw as any).context,
    validationRules: createProductionSecurityRules({ maxDepth: 4, maxAliases: 2 }),
    formatError: (error) => {
      console.error(`[INTERNAL-LOG] Error ID:`, error);
      return {
        message: error.message,
        extensions: {
          code: 'SECURITY_VALIDATION_FAILED'
        }
      };
    }
  })
);

app.listen(4000, () => {
  console.log('Secure GraphQL Engine active at http://localhost:4000/graphql');
});
```

### Langkah 4: Menjalankan & Menguji Payload Serangan
Jalankan server:
```bash
npm install
npm start
```

Uji **Serangan 1: Cyclic Recursive Query (Melampaui Depth 4)**:
```bash
curl -X POST http://localhost:4000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "query { me { profile { user { profile { user { id } } } } } }"}'
```
*Hasil:* Ditolak sebelum execution resolver (`Security Rule: Query depth (6) melampaui limit (4)`).

Uji **Serangan 2: Alias-based Stuffing (Melampaui 2 Aliases)**:
```bash
curl -X POST http://localhost:4000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "query { a1: me { id } a2: me { id } a3: me { id } }"}'
```
*Hasil:* Ditolak langsung (`Security Rule: Melebihi batas maksimal alias (2)`).

---

## 13. Exercises

### Level Easy
Modifikasi file `securityRules.ts` untuk memblokir seluruh operasi mutasi yang tidak memiliki nama operasi (*Anonymous Mutation Block*).
- *Syarat:* Jika klien mengirim `mutation { createItem(...) }`, validasi AST harus menolak dengan pesan `"Anonymous mutations are strictly prohibited"`. Harus berupa `mutation CreateItemMutation { ... }`.

### Level Medium
Kembangkan Custom Complexity Analyzer yang memperhitungkan nilai argumen dinamis:
- Jika query memuat argumen `first: N` atau `limit: N`, kalikan bobot child field dengan nilai `N`.
- Berikan penalti ekstra (biaya +50) jika klien meminta field dengan argumen pagination tetapi nilai `first` atau `limit` tidak didefinisikan (unbounded queries).

### Level Hard
Implementasikan **Dynamic In-Memory Token Bucket Rate Limiting per User** pada context GraphQL execution engine:
- Setiap user diberi alokasi 100 poin per menit.
- Setiap kali query dieksekusi, kurangi token pengguna sejumlah nilai kompleksitas query yang dihitung AST validator.
- Jika token habis, batalkan request dengan HTTP Status 429 atau GraphQL Error ber-code `RATE_LIMIT_EXCEEDED` beserta header `Retry-After`. Token harus diisi ulang (*refilled*) secara otomatis menggunakan algoritma token bucket murni.

---

## 14. Challenge (Studi Kasus Enterprise Tanpa Solusi Instan)

### Skenario: Arsitektur Multi-Tenant Gateway Berbasis Dynamic SLA
Anda adalah Principal Infrastructure Architect di sebuah platform SaaS B2B Enterprise. Platform ini melayani ratusan tenant dengan paket tier berbeda:
- **Enterprise Plan:** Max Depth = 10, Max Complexity Budget = 5000, APQ Opsional.
- **Pro Plan:** Max Depth = 6, Max Complexity Budget = 1500, APQ Wajib di jam sibuk.
- **Free Tier:** Max Depth = 4, Max Complexity Budget = 300, Strict APQ Allowlist Only.

### Permasalahan Tantangan:
1. **Dynamic AST Rule Injection:** Engine standar GraphQL (seperti GraphQL-JS) mengevaluasi validation rules statis sebelum `context` resolver diekstrak secara utuh. Bagaimana cara Anda mendesain arsitektur di mana validation rules berjalan secara dinamis berdasarkan data tenant yang dienkripsi dalam JWT access token?
2. **Cost Estimation Over-promise Attack:** Penyerang dari tenant Free Tier mengirim query valid:
   ```graphql
   query {
     orders(first: 5) {
       id
       expensiveFinancialAudit { details } # Cost: 50 poin
     }
   }
   ```
   Secara statis total biayanya aman (250 poin < 300 poin limit). Namun pada runtime database, pemanggilan fungsi `expensiveFinancialAudit` memicu lock tabel selama 4 detik. Bagaimana Anda mengombinasikan **Static AST Cost Validation** dengan **Runtime Micro-Circuit Breaker per-Resolver Execution** sehingga query pembunuh ini dapat dihentikan di tengah jalan tanpa mematikan thread Node.js?
3. **Persisted Queries Distributed Cache Poisoning:** Buat arsitektur registrasi hash APQ aman yang mencegah attacker membanjiri Redis cluster Anda dengan jutaan arbitrary/malicious hash combinations (*Hash-space Exhaustion Attack*).

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda)

1. **Kapan fase yang paling tepat untuk menghentikan serangan DoS pada GraphQL engine?**
   - A. Di dalam resolver field individual.
   - B. Pada database query execution hook.
   - C. Pada fase AST Validation sebelum execution engine berjalan.
   - D. Pada response formatter layer setelah output selesai dibentuk.
   *Jawaban yang benar:* C. Jika diputus pada validation phase, backend tidak mengalokasikan CPU untuk resolve data ataupun membuat koneksi I/O ke database.

2. **Apa fungsi utama dari menonaktifkan Schema Introspection di production environment?**
   - A. Menghindari crash pada Node.js engine.
   - B. Mempercepat latency parsing sebesar 90%.
   - C. Mencegah threat actor memetakan (reconnaissance) seluruh field, tipe, hubungan, dan mutasi privat.
   - D. Menghemat ruang harddisk server gateway.
   *Jawaban yang benar:* C. Introspection mengekspos blueprint sistem secara telanjang kepada siapa saja yang mengirim query `__schema`.

3. **Serangan DoS berbasis "Alias Batching" mengeksploitasi fitur apa pada GraphQL?**
   - A. Mekanisme batching network HTTP/2.
   - B. Kemampuan mengeksekusi field/mutasi yang sama berulang kali dalam satu request menggunakan nama alias unik.
   - C. Celah keamanan buffer overflow pada JSON parser bawaan.
   - D. Kegagalan konfigurasi SSL/TLS edge gateway.
   *Jawaban yang benar:* B. Penyerang mengelabui IP rate limiter dengan menyatukan ratusan aksi dalam 1 HTTP POST request.

4. **Apa yang dimaksud dengan Broken Object-Level Authorization (BOLA) dalam konteks GraphQL?**
   - A. Ketika server mengekspos error stack trace database.
   - B. Ketika klien gagal melakukan parsing JSON.
   - C. Kondisi di mana user A dapat mengakses resource ID milik user B hanya dengan mengganti argumen ID pada query.
   - D. Query yang kedalamannya melampaui batas memori buffer.
   *Jawaban yang benar:* C. BOLA terjadi akibat kegagalan resolver memvalidasi hak kepemilikan data dari objek yang diminta.

5. **Mengapa membatasi query depth saja BELUM CUKUP untuk mencegah DoS?**
   - A. Karena query depth tidak bisa menghentikan query yang flat namun meminta data dalam jumlah masif (breadth).
   - B. Karena query depth membuat Apollo Gateway crash.
   - C. Karena kedalaman query tidak dihitung pada mutation.
   - D. Karena query depth hanya bekerja pada format schema REST.
   *Jawaban yang benar:* A. Kueri dengan depth 2 dapat menarik 10.000 records jika argumen pagination tidak dibatasi atau field skalar diduplikasi secara masif.

---

### Bagian 2: Intermediate (Pilihan Ganda & Analisis Pendek)

6. **Apa risiko keamanan terbesar jika sistem Anda mengizinkan argumen pagination tanpa batas (unbounded pagination) seperti `users { id }`?**
   - A. Buffer overflow pada kernel Linux.
   - B. Memory leak fatal pada Node.js heap akibat deserialisasi jutaan record secara simultan.
   - C. SQL injection otomatis terjadi secara deterministik.
   - D. Cache control header langsung terhapus.
   *Jawaban yang benar:* B. Unbounded pagination memaksa ORM menarik seluruh isi tabel ke dalam RAM heap engine, memicu `JavaScript heap out of memory`.

7. **Bagaimana cara kerja Automatic Persisted Queries (APQ) dalam mode STRICT?**
   - A. Server menerima semua query baru dan menyimpannya di Redis secara instan.
   - B. Gateway HANYA mengeksekusi query jika hash sha256 yang dikirim klien sudah terdaftar di server/database allowlist sejak fase CI/CD build.
   - C. Gateway mengubah seluruh query menjadi REST request otomatis.
   - D. Klien tidak perlu mengirim Authorization Bearer token lagi.
   *Jawaban yang benar:* B. Dalam mode strict, unregistered hashes langsung ditolak mentah-mentah (403/Forbidden), menutup kemungkinan eksekusi query arbitrer oleh publik.

8. **Mengapa error masking wajib membedakan antara `originalError` sistemik dengan input validation error?**
   - A. Agar browser tidak menampilkan popup merah.
   - B. Agar klien tetap menerima pesan kesalahan validasi form yang jelas (misal: "Format email salah"), namun detail kegagalan database ("DB connection pool timeout") disembunyikan.
   - C. Karena compiler TypeScript akan error jika tidak dibedakan.
   - D. Untuk menghindari pembatasan rate limit WAF.
   *Jawaban yang benar:* B. User experience membutuhkan feedback validasi yang jelas, namun informasi infrastruktur internal harus disembunyikan untuk mencegah eksploitasi lebih lanjut.

9. **Ketika menggunakan DataLoader, di mana letak isolasi cache yang benar dalam arsitektur multi-tenant?**
   - A. Singleton global per Node.js process agar hemat memori.
   - B. Scoped secara eksklusif per HTTP Request Context.
   - C. Di-cache di Redis tanpa pemisah namespace tenant.
   - D. Disimpan pada level sistem operasi (OS Shared Memory).
   *Jawaban yang benar:* B. Jika DataLoader dijadikan singleton global, User A berpotensi membaca cache objek milik User B yang ditarik pada request sebelumnya (Data Leaks Cross-Tenant).

10. **Apa bahaya dari penggunaan directive bawaan `@skip` dan `@include` jika dipadukan dengan alias dalam jumlah masif?**
    - A. Membocorkan environment variable gateway.
    - B. Mengakibatkan CPU exhaustion selama fase evaluasi kondisi AST execution sebelum mencapai data fetcher.
    - C. Mengubah method POST menjadi GET tanpa disengaja.
    - D. Mematikan service rate limiter secara permanen.
    *Jawaban yang benar:* B. Manipulasi direktif tingkat tinggi memaksa compiler internal mengevaluasi ribuan conditional branch pada tree AST, memicu starvation event loop.

---

### Bagian 3: Skenario Kasus Produksi

11. **Skenario A:** Gateway Anda menerima lonjakan traffic POST ke `/graphql`. Latensi melonjak, namun CPU load database hanya 3%, sementara CPU load Gateway mencapai 100%. Setelah diteliti, payload berupa JSON valid berukuran 40KB yang memuat string query dengan 50.000 nested kurung kurawal kosong: `{{{{...}}}}`. Mengapa WAF dan static validation rule biasa Anda gagal mendeteksi hal ini sebelum Gateway hang?
    *Analisis Solusi:* Serangan ini menyasar fase **Lexer & Parser** GraphQL. Parser GraphQL mencoba mengonversi token string menjadi AST object tree di dalam memori. Jika nesting kurung kurawal terlalu dalam, parser mengalami *Call Stack Overflow* atau menghabiskan heap memory sebelum fase *Validation Rules* sempat dijalankan.
    *Mitigasi:* Terapkan batasan ukuran payload HTTP yang ketat (<20KB untuk text), dan pasang *Parser Token Counter / Max Token Limit* pada library parser (misalnya menggunakan GraphQL Armor atau `parserTokensThreshold` pada Apollo Engine).

12. **Skenario B:** Seorang pentester berhasil mengekstrak seluruh data order milik customer lain melalui query:
    ```graphql
    query {
      user(id: "target-user-uuid") {
        orders { id invoiceNumber amount }
      }
    }
    ```
    Padahal developer telah memasang RBAC middleware di level HTTP: `if (!req.user) throw Unauthorized`. Di mana letak kelalaian teknis tim pengembang?
    *Analisis Solusi:* Tim pengembang hanya menerapkan **Authentication (AuthN)** dan **Role-Based Access Control (RBAC)** di tingkat pintu masuk HTTP (memeriksa apakah penyerang punya akun), tetapi lalai mengimplementasikan **Object-Level Authorization (BOLA Guard)** pada resolver field `user(id: ...)`. Resolver langsung mengambil data berdasarkan argumen `id` dari database tanpa memvalidasi apakah `id` target cocok dengan identitas user di context (`context.user.id === args.id` atau jika user bersangkutan adalah `SUPER_ADMIN`).

13. **Skenario C:** Dalam implementasi Persisted Queries (APQ) standar Apollo, klien mengirimkan `hash`. Jika hash tidak ditemukan, klien mengirimkan pair `hash` dan string `query` asli untuk di-cache oleh gateway ke dalam Redis. Bagaimana skema APQ standar ini dapat dijadikan senjata oleh attacker untuk melumpuhkan Redis cache gateway Anda?
    *Analisis Solusi:* Vektor ini disebut **APQ Cache Poisoning / Storage Exhaustion**. Karena gateway secara naif mengizinkan sembarang klien mengirimkan kombinasi hash baru beserta query string arbitrary, attacker dapat menghasilkan jutaan string query acak (berisi komentar acak) dengan SHA256 hash palsu. Server akan menyimpan semuanya ke dalam Redis hingga kapasitas RAM Redis penuh (OOM) dan memicu Redis eviction policy yang berpotensi menghapus query-query sah yang sering digunakan aplikasi asli.
    *Mitigasi:* Terapkan **Strict Persisted Queries Allowlist**. Gateway tidak boleh menerima pendaftaran query baru secara on-the-fly dari browser publik; registrasi hash hanya boleh dilakukan melalui pipeline CI/CD resmi aplikasi sebelum rilis.

---

## 16. Summary

Mengamankan GraphQL pada skala enterprise membutuhkan pergeseran paradigma total dari sistem pengamanan route-based REST konvensional. Fondasi GraphQL security bertumpu pada **Defense-in-Depth Pipeline**:

1. **AST Level Shielding:** Memutus rantai serangan sebelum execution phase dengan memadukan *Depth Limiting*, *Max Alias Restrictions*, dan *Dynamic Complexity Analysis* berbasis pagination cost factor.
2. **Deterministic Query Whitelisting:** Mengadopsi *Strict Persisted Queries* untuk memangkas permukaan serangan arbitrary query di lingkungan produksi publik hingga 0%.
3. **Execution Layer Hardening:** Memindahkan validasi otorisasi dari level transport HTTP ke level granular data fetcher/resolver guna mengeliminasi celah BOLA/IDOR dan tenant bleeding.
4. **Resilient Sanitization:** Menghilangkan seluruh jejak detail infrastruktur internal melalui *Strict Output Masking* dengan mempertahankan auditabilitas berbasis *Tracing Correlation ID*.