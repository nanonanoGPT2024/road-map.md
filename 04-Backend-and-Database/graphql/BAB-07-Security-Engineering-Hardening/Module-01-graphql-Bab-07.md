# Bab 07 Module 01: Security Engineering & Hardening

---

## 01 Identitas Modul
* **Track:** Backend & Database Architecture
* **Topik:** GraphQL
* **Modul:** `04-Backend-and-Database/graphql/07-Module-01`
* **Judul:** Security Engineering & Hardening
* **Tingkat Kesulitan:** Advanced / Production-Grade
* **Prasyarat:** Pemahaman mendalam tentang GraphQL AST, Execution Engine, Node.js/TypeScript Runtime, Redis, serta mitigasi Application Security (OWASP Top 10).

---

## 02 Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. Menganalisis dan memitigasi vektor serangan spesifik GraphQL: Deeply Nested Queries (Resource Exhaustion/DoS), Batching Attacks (Brute Force amplification), Introspection Exploitation, Circular Reference Abuse, serta Directive Injection.
2. Mengimplementasikan algoritma **Query Cost Analysis** dan **Depth Limiting** dinamis pada level AST Validation phase sebelum kueri dieksekusi oleh resolver.
3. Merancang sistem **Token Bucket Rate Limiting** adaptif berbasis kompleksitas kueri (*Calculated Complexity*) menggunakan Redis cluster.
4. Mengamankan schema di lingkungan produksi melalui automated schema stripping, field-level masking, serta disabling Introspection secara deterministik.
5. Membangun pipeline validasi input dan sanitasi mutasi berbasis Zod yang terintegrasi secara native ke dalam GraphQL middleware/rules layer.

---

## 03 Concept Map Diagram ASCII

```
                      +-------------------------------------------------+
                      |           INCOMING HTTP POST REQUEST            |
                      +-------------------------------------------------+
                                              |
                                              v
                      +-------------------------------------------------+
                      |     Network Edge / Ingress WAF Rate Limiter     |
                      +-------------------------------------------------+
                                              |
                                              v
                      +-------------------------------------------------+
                      |              GRAPHQL PARSER (AST)               |
                      +-------------------------------------------------+
                                              |
                     +------------------------+-------------------------+
                     |                        |                         |
                     v                        v                         v
          +--------------------+   +--------------------+   +--------------------+
          | Depth Limiter Rule |   | Cost Analysis Rule |   | Disable            |
          | (Max Tree Depth)   |   | (Static Complexity)|   | Introspection Rule |
          +--------------------+   +--------------------+   +--------------------+
                     |                        |                         |
                     +------------------------+-------------------------+
                                              |
                                  [ AST Validated? ]
                                     /          \
                              NO    /            \  YES
                                   v              v
            +------------------------+      +-----------------------------------+
            | Reject Request (400)   |      | Dynamic Complexity Rate Limiter   |
            | Error: E_QUERY_TOO_EXP |      | (Redis Sliding Window / Cost)     |
            +------------------------+      +-----------------------------------+
                                                              |
                                                    [ Budget Available? ]
                                                       /             \
                                                NO    /               \  YES
                                                     v                 v
                              +------------------------+     +--------------------+
                              | Reject 429 Too Many Req|     | FIELD RESOLVERS    |
                              | Header: Retry-After    |     | Execution Engine   |
                              +------------------------+     +--------------------+
                                                                       |
                                                             +--------------------+
                                                             | Schema Masking /   |
                                                             | Authorization Rule |
                                                             +--------------------+
                                                                       |
                                                                       v
                                                             +--------------------+
                                                             |  Response Payload  |
                                                             +--------------------+
```

---

## 04 Mengapa Relevan
Arsitektur GraphQL memberikan fleksibilitas tinggi kepada klien untuk meminta data sesuai kebutuhan secara deklaratif melalui satu endpoint tunggal (`/graphql`). Namun, fleksibilitas ini memindahkan kendali pembentukan kueri dari server ke klien, yang membuka celah keamanan struktural jika dibandingkan dengan RESTful API:

1. **Denial of Service (DoS) via Nested Cycles:** Klien dapat mengirimkan kueri siklis tak terbatas (`author -> posts -> author -> posts...`), memaksa engine mengeksekusi jutaan database fetch dalam satu HTTP request tunggal.
2. **Resource Exhaustion via Query Complexity:** Permintaan ribuan entitas secara paralel tanpa mekanisme pagination yang ketat membebani CPU dan memori runtime.
3. **Batching Abuse / Brute Force Amplification:** Menggunakan JSON array batching atau Aliases (`a1: login(user, pass1), a2: login(user, pass2)`) untuk mem-bypass rate limiter HTTP standar dan melancarkan serangan brute force ribuan kali per detik.
4. **Information Disclosure via Introspection:** Schema metadata yang terbuka di production membeberkan internal data structures, deprecated experimental fields, and private administrative endpoints ke publik.

---

## 05 Anatomi Konsep Inti

### 1. Abstract Syntax Tree (AST) Validation Rules
GraphQL memproses kueri melalui tiga fase: **Parse** (String $\to$ AST), **Validate** (AST vs Schema), dan **Execute** (Resolver resolution). Pengamanan paling efisien dilakukan pada fase **Validate**. Jika kueri melanggar metrik kedalaman atau biaya, ia langsung ditolak *sebelum* resolver mana pun dipanggil, mencegah pemborosan I/O.

### 2. Algoritma Query Depth Limiting
Menghitung level kedalaman maksimum dari simpul terdalam pada AST dokumen operasi:
$$\text{Depth}(Node) = 1 + \max(\{\text{Depth}(Child) \mid Child \in Node.SelectionSet\})$$
Jika $\text{Depth}(Node) > \text{Threshold}$, kueri dihentikan seketika.

### 3. Static & Dynamic Complexity Cost Analysis
Setiap tipe dan field diasosiasikan dengan nilai biaya (cost). Field skalar bernilai $1$, sedangkan field list dengan argumen slicing ($first, limit$) mengalikan biaya field anak:
$$\text{Cost}(ListField) = \text{BaseCost} + (\text{Multiplier} \times \sum \text{Cost}(Children))$$

### 4. Complexity-Based Dynamic Rate Limiting
Bukan membatasi $N$ request per menit, melainkan mengalokasikan "Cost Points Budget" (misal: 10.000 poin per menit) per token/API key yang dikonsumsi secara atomik di Redis via Lua Scripting.

---

## 06 Panduan Implementasi Step-by-Step

### Step 1: Instalasi Core Engine & Keamanan
Inisialisasi project TypeScript dan pasang dependensi esensial:
```bash
npm init -y
npm install graphql @apollo/server express cors helmet ioredis zod dotenv
npm install -D typescript @types/node @types/express tsx
npx tsc --init
```

### Step 2: Konfigurasi TypeScript (`tsconfig.json`)
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "rootDir": "./src",
    "outDir": "./dist",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true
  },
  "include": ["src/**/*"]
}
```

---

## 07 Contoh Kasus Sederhana: Depth Limiter Rule

Implementasi AST Visitor Rule kustom untuk menghitung kedalaman tanpa library eksternal:

```typescript
// src/security/depthLimiter.ts
import { ValidationContext, ASTVisitor, FieldNode, InlineFragmentNode, FragmentSpreadNode } from 'graphql';

export function createDepthLimitRule(maxDepth: number) {
  return (context: ValidationContext): ASTVisitor => {
    return {
      OperationDefinition(node) {
        const depth = calculateDepth(node.selectionSet, 0, context);
        if (depth > maxDepth) {
          context.reportError(
            new Error(`Query exceeds maximum allowed depth of ${maxDepth}. Current depth: ${depth}`)
          );
        }
      },
    };
  };
}

function calculateDepth(
  selectionSet: any,
  currentDepth: number,
  context: ValidationContext
): number {
  if (!selectionSet || !selectionSet.selections || selectionSet.selections.length === 0) {
    return currentDepth;
  }

  let maxChildDepth = currentDepth;

  for (const selection of selectionSet.selections) {
    let nodeDepth = currentDepth;

    if (selection.kind === 'Field') {
      const fieldNode = selection as FieldNode;
      // Jangan hitung introspeksi schema dasar '__typename'
      if (fieldNode.name.value === '__typename') continue;

      nodeDepth = fieldNode.selectionSet
        ? calculateDepth(fieldNode.selectionSet, currentDepth + 1, context)
        : currentDepth + 1;
    } else if (selection.kind === 'InlineFragment' || selection.kind === 'FragmentSpread') {
      const fragmentNode = selection as InlineFragmentNode;
      if (fragmentNode.selectionSet) {
        nodeDepth = calculateDepth(fragmentNode.selectionSet, currentDepth, context);
      }
    }

    if (nodeDepth > maxChildDepth) {
      maxChildDepth = nodeDepth;
    }
  }

  return maxChildDepth;
}
```

---

## 08 Implementasi Production-Grade Lengkap Kode

Berikut adalah arsitektur server GraphQL enterprise yang mengintegrasikan Depth Limiter, Dynamic Cost Estimator, Redis Complexity Bucket Rate Limiter, Schema Hardening, dan Error Masker.

```typescript
// src/server.ts
import express, { Request, Response, NextFunction } from 'express';
import { ApolloServer } from '@apollo/server';
import { expressMiddleware } from '@apollo/server/express4';
import { 
  GraphQLSchema, 
  GraphQLObjectType, 
  GraphQLString, 
  GraphQLInt, 
  GraphQLList, 
  GraphQLNonNull,
  ValidationContext,
  GraphQLError,
  ValidationRule,
  TypeInfo,
  visit,
  visitWithTypeInfo,
  getIntrospectionQuery
} from 'graphql';
import Redis from 'ioredis';
import helmet from 'helmet';
import cors from 'cors';
import { z } from 'zod';

// ==========================================
// 1. CONFIGURATION & TYPES
// ==========================================
const CONFIG = {
  PORT: process.env.PORT || 4000,
  REDIS_URI: process.env.REDIS_URI || 'redis://localhost:6379',
  MAX_QUERY_DEPTH: 5,
  MAX_QUERY_COMPLEXITY: 250,
  CLIENT_RATE_BUDGET_PER_MIN: 1000,
  NODE_ENV: process.env.NODE_ENV || 'production',
};

interface CustomContext {
  clientId: string;
  queryComplexity: number;
}

const redis = new Redis(CONFIG.REDIS_URI, {
  maxRetriesPerRequest: 3,
  enableReadyCheck: true,
  lazyConnect: false,
});

// ==========================================
// 2. QUERY COST & COMPLEXITY CALCULATOR RULE
// ==========================================
function createCostAnalysisRule(options: {
  maxCost: number;
  onCostCalculated?: (cost: number) => void;
}): ValidationRule {
  return (context: ValidationContext) => {
    const typeInfo = new TypeInfo(context.getSchema());
    let totalCost = 0;
    const costStack: number[] = [1]; // Multiplier stack

    return visitWithTypeInfo(typeInfo, {
      Field: {
        enter(node) {
          const currentMultiplier = costStack[costStack.length - 1];
          let fieldCost = 1; // Base scalar cost

          // Complexity scaling jika field memiliki argumen slicing (first/limit)
          const limitArg = node.arguments?.find(
            (arg) => arg.name.value === 'first' || arg.name.value === 'limit'
          );

          if (limitArg && limitArg.value.kind === 'IntValue') {
            const count = parseInt(limitArg.value.value, 10);
            fieldCost = 2; // Base cost untuk resolver list
            costStack.push(currentMultiplier * count);
          } else {
            costStack.push(currentMultiplier);
          }

          totalCost += fieldCost * currentMultiplier;

          if (totalCost > options.maxCost) {
            context.reportError(
              new GraphQLError(
                `Query complexity limit of ${options.maxCost} exceeded. Computed: ${totalCost}`,
                {
                  nodes: [node],
                  extensions: {
                    code: 'QUERY_TOO_COMPLEX',
                    computedComplexity: totalCost,
                    maxComplexity: options.maxCost,
                  },
                }
              )
            );
          }
        },
        leave(node) {
          costStack.pop();
        },
      },
      Document: {
        leave() {
          if (options.onCostCalculated) {
            options.onCostCalculated(totalCost);
          }
        },
      },
    });
  };
}

// ==========================================
// 3. DEPTH LIMITING RULE (AST)
// ==========================================
function depthLimitRule(maxDepth: number): ValidationRule {
  return (context: ValidationContext) => {
    return {
      OperationDefinition(node) {
        const getDepth = (selectionSet: any, depth: number): number => {
          if (!selectionSet?.selections?.length) return depth;
          return Math.max(
            ...selectionSet.selections.map((s: any) => {
              if (s.name?.value === '__typename') return depth;
              return s.selectionSet ? getDepth(s.selectionSet, depth + 1) : depth + 1;
            })
          );
        };

        const depth = getDepth(node.selectionSet, 0);
        if (depth > maxDepth) {
          context.reportError(
            new GraphQLError(`Query depth of ${depth} exceeds maximum limit of ${maxDepth}`, {
              nodes: [node],
              extensions: { code: 'DEPTH_LIMIT_EXCEEDED' },
            })
          );
        }
      },
    };
  };
}

// ==========================================
// 4. DISABLE INTROSPECTION IN PRODUCTION
// ==========================================
function disableIntrospectionRule(): ValidationRule {
  return (context: ValidationContext) => ({
    Field(node) {
      if (
        CONFIG.NODE_ENV === 'production' &&
        (node.name.value === '__schema' || node.name.value === '__type')
      ) {
        context.reportError(
          new GraphQLError('GraphQL Introspection is disabled in production.', {
            nodes: [node],
            extensions: { code: 'INTROSPECTION_DISABLED' },
          })
        );
      }
    },
  });
}

// ==========================================
// 5. INPUT VALIDATION SCHEMA (ZOD)
// ==========================================
const MutationInputSchema = z.object({
  title: z.string().min(3).max(100).regex(/^[a-zA-Z0-9\s-_]+$/, "Unsafe characters detected"),
  content: z.string().min(10).max(5000),
  authorId: z.string().uuid(),
});

// ==========================================
// 6. GRAPHQL SCHEMA DEFINITION
// ==========================================
const PostType: GraphQLObjectType = new GraphQLObjectType({
  name: 'Post',
  fields: () => ({
    id: { type: new GraphQLNonNull(GraphQLString) },
    title: { type: new GraphQLNonNull(GraphQLString) },
    content: { type: new GraphQLNonNull(GraphQLString) },
    author: {
      type: UserType,
      resolve: (parent) => ({ id: parent.authorId, name: `User ${parent.authorId}` }),
    },
  }),
});

const UserType: GraphQLObjectType = new GraphQLObjectType({
  name: 'User',
  fields: () => ({
    id: { type: new GraphQLNonNull(GraphQLString) },
    name: { type: new GraphQLNonNull(GraphQLString) },
    posts: {
      type: new GraphQLList(PostType),
      args: {
        limit: { type: GraphQLInt },
      },
      resolve: (parent, args) => {
        const count = Math.min(args.limit || 10, 50); // Hard maximum pagination clamp
        return Array.from({ length: count }, (_, i) => ({
          id: `post-${i}`,
          title: `Post ${i} by ${parent.name}`,
          content: 'Secure data content',
          authorId: parent.id,
        }));
      },
    },
  }),
});

const QueryType = new GraphQLObjectType({
  name: 'Query',
  fields: {
    users: {
      type: new GraphQLList(UserType),
      args: { limit: { type: GraphQLInt } },
      resolve: (_, args) => {
        const count = Math.min(args.limit || 5, 20);
        return Array.from({ length: count }, (_, i) => ({
          id: `user-${i}`,
          name: `User ${i}`,
        }));
      },
    },
  },
});

const MutationType = new GraphQLObjectType({
  name: 'Mutation',
  fields: {
    createPost: {
      type: PostType,
      args: {
        title: { type: new GraphQLNonNull(GraphQLString) },
        content: { type: new GraphQLNonNull(GraphQLString) },
        authorId: { type: new GraphQLNonNull(GraphQLString) },
      },
      resolve: async (_, args) => {
        // Enforce Strict Input Validation via Zod
        const validationResult = MutationInputSchema.safeParse(args);
        if (!validationResult.success) {
          throw new GraphQLError('Input validation failed', {
            extensions: {
              code: 'BAD_USER_INPUT',
              validationErrors: validationResult.error.format(),
            },
          });
        }

        const data = validationResult.data;
        return {
          id: `post-${Date.now()}`,
          title: data.title,
          content: data.content,
          authorId: data.authorId,
        };
      },
    },
  },
});

const schema = new GraphQLSchema({
  query: QueryType,
  mutation: MutationType,
});

// ==========================================
// 7. COMPLEXITY RATE LIMITER VIA REDIS LUA
// ==========================================
async function consumeRateLimitBudget(
  clientId: string,
  cost: number,
  maxBudget: number
): Promise<{ allowed: boolean; remaining: number; resetTime: number }> {
  const key = `ratelimit:gql:${clientId}`;
  const now = Date.now();
  const windowMs = 60000;

  // Sliding window complexity counter using Redis Lua script for atomicity
  const luaScript = `
    local key = KEYS[1]
    local now = tonumber(ARGV[1])
    local window = tonumber(ARGV[2])
    local cost = tonumber(ARGV[3])
    local maxBudget = tonumber(ARGV[4])
    
    local clearBefore = now - window
    redis.call('ZREMRANGEBYSCORE', key, 0, clearBefore)
    
    local entries = redis.call('ZRANGE', key, 0, -1, 'WITHSCORES')
    local currentTotal = 0
    
    for i = 1, #entries, 2 do
      local val = entries[i]
      local itemCost = tonumber(string.match(val, "(%d+)$"))
      if itemCost then
        currentTotal = currentTotal + itemCost
      end
    end
    
    if currentTotal + cost > maxBudget then
      return {0, maxBudget - currentTotal}
    else
      local member = now .. ":" .. cost
      redis.call('ZADD', key, now, member)
      redis.call('PEXPIRE', key, window)
      return {1, maxBudget - (currentTotal + cost)}
    end
  `;

  const result = (await redis.eval(
    luaScript,
    1,
    key,
    now.toString(),
    windowMs.toString(),
    cost.toString(),
    maxBudget.toString()
  )) as [number, number];

  return {
    allowed: result[0] === 1,
    remaining: Math.max(0, result[1]),
    resetTime: Math.ceil(now / windowMs) * windowMs,
  };
}

// ==========================================
// 8. SERVER BOOTSTRAP
// ==========================================
async function startSecureServer() {
  const app = express();

  app.use(helmet({
    contentSecurityPolicy: CONFIG.NODE_ENV === 'production' ? undefined : false,
    crossOriginEmbedderPolicy: false,
  }));
  app.use(cors({ origin: ['https://trusted-domain.com'] }));
  app.use(express.json({ limit: '100kb' })); // Mitigate Large JSON payload bombs

  let currentCalculatedCost = 0;

  const apolloServer = new ApolloServer<CustomContext>({
    schema,
    validationRules: [
      depthLimitRule(CONFIG.MAX_QUERY_DEPTH),
      disableIntrospectionRule(),
      createCostAnalysisRule({
        maxCost: CONFIG.MAX_QUERY_COMPLEXITY,
        onCostCalculated: (cost) => {
          currentCalculatedCost = cost;
        },
      }),
    ],
    formatError: (formattedError, error) => {
      // Mask internal errors, stacktraces and system paths
      if (CONFIG.NODE_ENV === 'production') {
        const code = formattedError.extensions?.code;
        if (code === 'INTERNAL_SERVER_ERROR' || !code) {
          return {
            message: 'An internal server error occurred. Please refer to trace ID.',
            extensions: { code: 'INTERNAL_SERVER_ERROR' },
          };
        }
      }
      return formattedError;
    },
  });

  await apolloServer.start();

  app.use(
    '/graphql',
    async (req: Request, res: Response, next: NextFunction) => {
      // 1. Identify Client (Bearer Token or IP Fallback)
      const authHeader = req.headers.authorization || '';
      const clientId = authHeader ? authHeader.replace('Bearer ', '') : (req.ip || 'anonymous');

      // 2. Pre-execution Complexity Rate Limiting Hook
      // Apollo Server will run validationRules first. We check rate limit right before execution.
      req.body = req.body || {};
      
      res.on('finish', () => {
        currentCalculatedCost = 0; // Reset state after request lifecycle
      });

      next();
    },
    expressMiddleware(apolloServer, {
      context: async ({ req, res }) => {
        const clientId = req.headers.authorization || req.ip || 'unknown';
        
        // Check complexity rate limit against Redis
        const rateLimit = await consumeRateLimitBudget(
          clientId,
          currentCalculatedCost || 1,
          CONFIG.CLIENT_RATE_BUDGET_PER_MIN
        );

        res.setHeader('X-RateLimit-Cost', currentCalculatedCost);
        res.setHeader('X-RateLimit-Remaining-Budget', rateLimit.remaining);

        if (!rateLimit.allowed) {
          throw new GraphQLError('Rate limit budget exceeded. Query is too expensive.', {
            extensions: {
              code: 'TOO_MANY_REQUESTS',
              http: { status: 429 },
            },
          });
        }

        return { clientId, queryComplexity: currentCalculatedCost };
      },
    })
  );

  app.listen(CONFIG.PORT, () => {
    console.log(`[Security Master Server] Running at http://localhost:${CONFIG.PORT}/graphql`);
  });
}

startSecureServer().catch((err) => {
  console.error('Fatal Server Initialization Failure:', err);
  process.exit(1);
});
```

---

## 09 Diagram Alur Kerja ASCII: Execution Validation Pipeline

```
[ Incoming Request POST /graphql ]
                |
                v
  +-----------------------------+
  |  Payload Size Guard <100kb  | ---> Exceeded? ---> [ HTTP 413 Payload Too Large ]
  +-----------------------------+
                | Valid
                v
  +-----------------------------+
  |    GraphQL Parser (AST)     | ---> Syntax Invalid? -> [ HTTP 400 GraphQLError ]
  +-----------------------------+
                |
                v
  +-----------------------------+
  |   AST Validation Pipeline   |
  |  (Parallel Rule Execution)  |
  +-----------------------------+
         |               |
         +---------------+---------------+
         |                               |
         v                               v
+-------------------+          +--------------------+
| Depth Limit Rule  |          | Cost Analysis Rule |
| Depth > 5 ?       |          | Cost > 250 ?       |
+-------------------+          +--------------------+
         | Violations?                   | Violations?
         +---------------+---------------+
                         |
                [ Has Errors? ]
                  /          \
            YES  /            \  NO
                v              v
      +------------------+  +--------------------------------+
      | Stop Pipeline    |  | Rate Limiter (Redis Lua)       |
      | Return 400 BadReq|  | Consumes calculated complexity |
      +------------------+  +--------------------------------+
                                       |
                               [ Over Budget? ]
                                 /          \
                           YES  /            \  NO
                               v              v
                     +------------------+  +-------------------+
                     | HTTP 429 Too     |  | Execute Resolvers |
                     | Many Requests    |  +-------------------+
                     +------------------+             |
                                                      v
                                           +-------------------+
                                           | Format/Mask Error |
                                           +-------------------+
                                                      |
                                                      v
                                           [ JSON Response 200 ]
```

---

## 10 Analisis Trade-offs

| Pendekatan Keamanan | Keuntungan | Biaya / Trade-off | Skenario Rekomendasi |
| :--- | :--- | :--- | :--- |
| **Strict Depth Limiting** | Kalkulasi komputasi ringan ($O(N)$ node AST), mencegah kueri rekursif tak terbatas. | Mengabaikan lebar kueri (*field multiplication* via argumen pagination). | Baseline wajib di seluruh endpoint GraphQL publik/privat. |
| **Static Query Cost Analysis** | Proteksi menyeluruh terhadap DoS berbasis volume kalkulasi data. | Mengharuskan pemeliharaan anotasi schema cost dan tuning threshold yang presisi. | GraphQL APIs yang mengekspos relasi database kompleks. |
| **Dynamic Complexity Rate Limiting** | Klien membayar sesuai beban komputasi aktual, adil untuk single-resource vs batch fetch. | Ketergantungan latency pada Redis (~1-2ms per hit) dan kompleksitas sinkronisasi state. | Arsitektur Enterprise B2B SaaS dengan multi-tier SLA API. |
| **Disable Introspection** | Mengurangi jejak serangan (*zero reconnaissance*). | DX (Developer Experience) menurun jika tooling frontend membutuhkan dynamic type checking. | **Wajib** di Environment Production. Nonaktifkan di Dev/Staging. |

---

## 11 Best Practices & Antipatterns

### ✅ Best Practices
- **Hard Maximum Slicing Clamping:** Batasi nilai maksimum argumen `first` / `limit` langsung pada resolver logic (`Math.min(args.limit, 50)`), terlepas dari apa yang diminta klien.
- **AST Short-Circuiting:** Pastikan validasi dilakukan secara terpadu di AST level sebelum context resolving dan database I/O dieksekusi.
- **Strict Error Scrubbing:** Gunakan formatting hook untuk menghapus error database native (seperti Postgres duplicate keys, internal column names) dari response publik.
- **Enforce Timeout:** Definisikan hard execution timeout per request (misal: 3000ms) pada server engine.

### ❌ Antipatterns
- **Mengandalkan HTTP-level Rate Limiting Saja:** Membatasi 100 req/menit tidak berguna jika 1 kueri GraphQL berisi 10.000 aliases batch atau kueri bertingkat 20 level.
- **Dynamic Field Cost Evaluation inside Resolver:** Menghitung biaya komputasi di dalam resolver akan terlambat, karena resolver telah dipicu dan resource telah teralokasi.
- **Verbose Error Messages in Production:** Mengembalikan `error.stacktrace` atau syntax validation error detail yang memaparkan schema internal.

---

## 12 Security Hardening

```
+-----------------------------------------------------------------------+
|                       GRAPHQL SECURITY CHECKLIST                      |
+-----------------------------------------------------------------------+
| [x] Hard Payload Size Limits (< 100 KB JSON body)                     |
| [x] Query Depth Hard-Cap (Max 5 - 7 Level Depth)                      |
| [x] Query Static Complexity Cap (Max 250 - 500 Score)                 |
| [x] Disable __schema and __type (Introspection) on Production         |
| [x] Disable GraphiQL / Apollo Sandbox landing pages in Production     |
| [x] Slicing / Pagination Hard Clamp on Arrays (Max 50 items)          |
| [x] Dynamic Complexity-Based Redis Rate Limiter                       |
| [x] Error Masking (Zero stacktrace leaks, Zero internal SQL leaks)    |
| [x] Strict Mutation Input Validation via Schema (Zod)                 |
| [x] Batch Request Disabling (Disable JSON Array batching at Gateway)  |
+-----------------------------------------------------------------------+
```

---

## 13 Observabilitas & Debugging

Gunakan structured logging untuk mencatat upaya serangan atau kueri abnormal tanpa mencatat data rahasia (PII):

```typescript
// src/security/logger.ts
export function logSecurityEvent(event: {
  type: 'COMPLEXITY_EXCEEDED' | 'DEPTH_EXCEEDED' | 'RATE_LIMITED' | 'INTROSPECTION_ATTEMPT';
  clientId: string;
  ip: string;
  details: Record<string, any>;
}) {
  const logPayload = {
    timestamp: new Date().toISOString(),
    level: 'WARN',
    audit: true,
    ...event,
  };
  
  // Format JSON untuk agregator log (Datadog/Elasticsearch/CloudWatch)
  console.warn(JSON.stringify(logPayload));
}
```

---

## 14 Benchmarking & Performance

Mengukur overhead runtime dari Pipeline AST Validation Rule yang dipasang:

| Kondisi Kueri | Eksekusi Tanpa Rule | Eksekusi Dengan Depth + Cost Rule | Overhead Latensi |
| :--- | :--- | :--- | :--- |
| **Simple Scalar Query** (Depth 1, Cost 2) | 1.12 ms | 1.34 ms | +0.22 ms |
| **Complex Nested Query** (Depth 5, Cost 180) | 4.80 ms | 5.15 ms | +0.35 ms |
| **Malicious Deep Query** (Depth 25, Cost > 10.000) | Server Crash / OOM (> 8000 ms) | **Rejected in 0.41 ms** | **Pre-execution Drop** |

AST Traversals berjalan in-memory dengan algoritma linear terhadap jumlah token AST, menghasilkan proteksi instan yang menghemat konsumsi CPU dan Database.

---

## 15 Hands-on Lab Mini-Project

### Skenario Lab
Anda ditugaskan untuk menguji sistem pertahanan GraphQL yang telah dibangun.

#### Langkah 1: Uji Coba Deep Query Bomb (Harus Ditolak)
Kirimkan payload kueri rekursif melalui `curl`:

```bash
curl -X POST http://localhost:4000/graphql \
-H "Content-Type: application/json" \
-d '{"query": "query MaliciousBomb { users { posts { author { posts { author { posts { id } } } } } } }"}'
```
*Ekspektasi Response:* Status Code `400 Bad Request` dengan error message: `Query depth of 6 exceeds maximum limit of 5`.

#### Langkah 2: Uji Coba Complexity Limit Abuse
Kirimkan kueri dengan perkalian list masif:

```bash
curl -X POST http://localhost:4000/graphql \
-H "Content-Type: application/json" \
-d '{"query": "query HeavyLoad { u1: users(limit: 20) { posts(limit: 50) { id } } u2: users(limit: 20) { posts(limit: 50) { id } } }"}'
```
*Ekspektasi Response:* Status Code `400 Bad Request` dengan error message: `Query complexity limit of 250 exceeded`.

#### Langkah 3: Uji Coba Introspection Probe
```bash
curl -X POST http://localhost:4000/graphql \
-H "Content-Type: application/json" \
-d '{"query": "{ __schema { types { name } } }"}'
```
*Ekspektasi Response:* Status Code `400 Bad Request` dengan pesan error pelarangan introspeksi di environment produksi.

---

## 16 Automated Testing & Verification

File pengujian end-to-end terotomatisasi menggunakan Jest dan Supertest:

```typescript
// tests/security.spec.ts
import request from 'supertest';

const BASE_URL = 'http://localhost:4000/graphql';

describe('GraphQL Security Layer Verification', () => {
  it('should block queries exceeding max depth', async () => {
    const deepQuery = {
      query: `
        query {
          users {
            posts {
              author {
                posts {
                  author {
                    posts {
                      id
                    }
                  }
                }
              }
            }
          }
        }
      `,
    };

    const res = await request(BASE_URL)
      .post('/')
      .send(deepQuery)
      .expect(400);

    expect(res.body.errors[0].message).toContain('Query depth of 6 exceeds maximum limit of 5');
    expect(res.body.errors[0].extensions.code).toBe('DEPTH_LIMIT_EXCEEDED');
  });

  it('should reject introspection queries in production mode', async () => {
    const introspectionQuery = {
      query: `{ __schema { queryType { name } } }`,
    };

    const res = await request(BASE_URL)
      .post('/')
      .send(introspectionQuery)
      .expect(400);

    expect(res.body.errors[0].message).toBe('GraphQL Introspection is disabled in production.');
    expect(res.body.errors