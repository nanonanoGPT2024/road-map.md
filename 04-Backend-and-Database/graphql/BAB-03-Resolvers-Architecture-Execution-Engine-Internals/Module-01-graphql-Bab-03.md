# Bab 03 Module 01: Resolvers Architecture & Execution Engine Internals

---

## Seksi 01: Identitas Modul
* **Track:** Backend and Database Engineering
* **Kategori:** 04-Backend-and-Database
* **Topik:** GraphQL
* **Tingkat Kompleksitas:** Advanced / Principal Level
* **Prasyarat:** Pemahaman mendalam tentang GraphQL Type System, AST (Abstract Syntax Tree), Event Loop & Asynchronous I/O Node.js, serta Database Access Patterns.
* **Target Output:** Penguasaan arsitektur resolver GraphQL, internal engine fase eksekusi GraphQL.js, pemecahan masalah $N+1$ via micro-batching internals, isolasi execution context, dan perancangan resilient resolver pipeline.

---

## Seksi 02: Learning Objectives
1. Mengurai fase GraphQL Execution Engine (`Parse`, `Validate`, `Execute`) hingga tingkat algoritma pemanggilan resolver.
2. Memahami signature resolver internal 4-argumen (`parent`, `args`, `contextValue`, `info`) dan struktur AST traversal pada `GraphQLResolveInfo`.
3. Menganalisis mekanisme Breadth-First vs Depth-First resolution dan eksekusi concurrency pada field list/scalar.
4. Mendiagnosis dan memitigasi Bottleneck $N+1$ menggunakan custom DataLoader mechanics dan tick microtask scheduling.
5. Membangun execution pipeline production-ready dengan field-level middleware, context isolation, dan fine-grained error bubbling handling.

---

## Seksi 03: Concept Map Diagram ASCII
```
+-----------------------------------------------------------------------------------+
|                           GRAPHQL EXECUTION ENGINE                                |
+-----------------------------------------------------------------------------------+
                                      |
                       [ HTTP POST Payload: { query } ]
                                      |
                                      v
                             +-----------------+
                             | 1. Parse Phase  | ----> Menghasilkan DocumentNode (AST)
                             +-----------------+
                                      |
                                      v
                             +-----------------+
                             | 2. Validate     | ----> Type System & AST Rule Checks
                             +-----------------+
                                      |
                                      v
                             +-----------------+
                             | 3. Execute      |
                             +-----------------+
                                      |
             +------------------------+------------------------+
             |                                                 |
             v                                                 v
   [ OperationType: Query ]                          [ OperationType: Mutation ]
   (Parallel Execution)                              (Strict Serial Execution)
             |                                                 |
             +------------------------+------------------------+
                                      |
                                      v
                         +--------------------------+
                         | ExecuteQuery / Selection | <===========================+
                         +--------------------------+                             |
                                      |                                           | (Recursive
                                      v                                           |  Depth-First
                         +--------------------------+                             |  Traversal)
                         | ResolveFieldValueOrError |                             |
                         +--------------------------+                             |
                                      |                                           |
                +---------------------+---------------------+                     |
                |                     |                     |                     |
                v                     v                     v                     |
          [ Parent/Root ]       [ Arguments ]       [ ContextValue ]              |
                |                     |                     |                     |
                +---------------------+---------------------+                     |
                                      |                                           |
                                      v                                           |
                         +--------------------------+                             |
                         |   FieldResolverFn(...)   |                             |
                         +--------------------------+                             |
                                      |                                           |
                   +------------------+------------------+                        |
                   |                                     |                        |
                   v                                     v                        |
            [ Leaf Scalar ]                      [ Complex Object ]               |
        (Serialize & Complete)                           +------------------------+
                   |
                   v
          +------------------+
          | Response Payload | ===> { data: { ... }, errors: [ ... ] }
          +------------------+
```

---

## Seksi 04: Mengapa Relevan
Resolvers adalah jembatan fungsional antara skema GraphQL deklaratif dan sistem data imperatif (DB, Microservices, Cache). Kegagalan memahami internal execution engine GraphQL menyebabkan:
* **Over-fetching & $N+1$ queries** yang menjatuhkan database relational di production.
* **Event-loop starvation** akibat unhandled synchronous resolvers di dalam skema deep-nested.
* **Kebocoran data & memory leaks** karena manipulasi mutable `contextValue` secara un-safe antar-request.
* **Cascading Error Disasters** di mana error pada child resolver menghapus seluruh branch data akibat *nullability bubbling*.

Menguasai arsitektur resolver dan siklus hidup eksekusi memungkinkan perancangan backend dengan throughput tinggi, latensi prediktif, dan isolasi kegagalan modular.

---

## Seksi 05: Anatomi Konsep Inti

### 1. The Execution Lifecycle
Siklus pemrosesan GraphQL terbagi menjadi 3 fase terisolasi:
* **Parsing:** Mengubah raw GraphQL query string menjadi Abstract Syntax Tree (AST) via Lexer dan Parser.
* **Validation:** Memvalidasi AST terhadap skema type system (mengecek kesesuaian types, directives, selection sets).
* **Execution:** Engine menelusuri AST mulai dari root operation (`Query`, `Mutation`, atau `Subscription`) dan memanggil resolver secara rekursif via fungsi `executeField()`.

### 2. Algoritma Resolusi: Query vs Mutation
* **Query Execution:** Menggunakan algoritma paralel asynchronous (`Promise.all` semantics). Setiap field pada level yang sama dieksekusi secara konkuren.
* **Mutation Execution:** Menggunakan algoritma serial bertingkat. Field level-1 pada Mutation dieksekusi secara sekuensial untuk mencegah race condition write data, namun nested child fields di bawahnya dieksekusi secara paralel.

### 3. Resolver 4-Argumen Signature
Resolver GraphQL memiliki kontrak execution signature:
```typescript
type GraphQLFieldResolver<TSource, TContext, TArgs = Record<string, any>, TReturn = any> = (
  parent: TSource,
  args: TArgs,
  context: TContext,
  info: GraphQLResolveInfo
) => Promise<TReturn> | TReturn;
```
* **`parent` / `root`:** Nilai hasil resolusi dari node parent sebelumnya.
* **`args`:** Map argument input yang didefinisikan pada field AST setelah divalidasi dan dicoerce oleh engine.
* **`context`:** Shared dependency container thread-safe per HTTP request. Berisi koneksi DB, auth token, data loaders.
* **`info`:** Metadata internal engine yang memuat schema reference, field AST nodes, path array, dan returnType.

### 4. Nullability Bubbling & Error Handling
Dalam GraphQL, field berstatus *Nullable* secara default (`Type`) atau *Non-Nullable* (`Type!`). Jika sebuah resolver melempar unhandled error atau mengembalikan `null` pada field `Type!`:
1. Engine memvalidasi invariant non-null.
2. Karena invariant dilanggar, engine mem-bubble error ke parent field.
3. Proses bubbling berlanjut ke root sampai menemukan parent field yang *Nullable*, merusak tree data di jalurnya, atau me-nullify field `data` utama jika seluruh jalur berstatus non-nullable.

---

## Seksi 06: Panduan Implementasi Step-by-Step

### 1. Inisialisasi Project TypeScript Engine
```bash
mkdir graphql-engine-internals
cd graphql-engine-internals
npm init -y
npm install graphql@16.8.1 dataloader@2.2.2 express@4.19.2
npm install --save-dev typescript@5.4.5 @types/node@20.12.7 @types/express@4.17.21 ts-node@10.9.2
npx tsc --init
```

### 2. Konfigurasi `tsconfig.json`
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "commonjs",
    "lib": ["ES2022"],
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "outDir": "./dist"
  },
  "include": ["src/**/*"]
}
```

---

## Seksi 07: Contoh Kasus Sederhana
Menelusuri bagaimana resolver parameter `info` digunakan untuk membedakan seleksi query database secara dinamis (Field Projection).

```typescript
// src/simple-projection.ts
import { 
  graphql, 
  GraphQLSchema, 
  GraphQLObjectType, 
  GraphQLString, 
  GraphQLList, 
  GraphQLResolveInfo, 
  FieldNode 
} from 'graphql';

// Utility untuk mengekstrak requested fields dari AST
function getSelectedFields(info: GraphQLResolveInfo): string[] {
  const fieldNode = info.fieldNodes[0];
  if (!fieldNode.selectionSet) return [];
  
  return fieldNode.selectionSet.selections
    .filter((s): s is FieldNode => s.kind === 'Field')
    .map(s => s.name.value);
}

const UserType = new GraphQLObjectType({
  name: 'User',
  fields: {
    id: { type: GraphQLString },
    username: { type: GraphQLString },
    email: { type: GraphQLString },
  }
});

const QueryType = new GraphQLObjectType({
  name: 'Query',
  fields: {
    users: {
      type: new GraphQLList(UserType),
      resolve: (_parent, _args, _context, info) => {
        const fields = getSelectedFields(info);
        console.log(`[SQL SELECT GENERATION]: SELECT ${fields.join(', ')} FROM users;`);
        
        return [
          { id: '1', username: 'alice', email: 'alice@internal.corp' },
          { id: '2', username: 'bob', email: 'bob@internal.corp' }
        ];
      }
    }
  }
});

const schema = new GraphQLSchema({ query: QueryType });

// Eksekusi
graphql({
  schema,
  source: '{ users { id username } }'
}).then(res => console.log(JSON.stringify(res, null, 2)));
```

---

## Seksi 08: Implementasi Production-Grade Lengkap Kode
Arsitektur modular Resolver Pipeline dengan Context Factory, Custom Batch Engine (DataLoader Internals), Typed Resolvers, dan Error Boundary Middleware.

```typescript
// src/server.ts
import express, { Request, Response } from 'express';
import { 
  GraphQLSchema, 
  GraphQLObjectType, 
  GraphQLString, 
  GraphQLID, 
  GraphQLList, 
  GraphQLNonNull, 
  GraphQLFieldResolver, 
  execute, 
  parse, 
  validate, 
  specifiedRules,
  GraphQLError
} from 'graphql';
import DataLoader from 'dataloader';

// ==========================================
// 1. DOMAIN MODELS & REPOSITORIES (MOCK DB)
// ==========================================
interface UserRecord {
  id: string;
  name: string;
  departmentId: string;
}

interface DepartmentRecord {
  id: string;
  name: string;
}

const DB_USERS: UserRecord[] = [
  { id: 'u-101', name: 'Alamsyah Senior', departmentId: 'd-1' },
  { id: 'u-102', name: 'Budi Lead', departmentId: 'd-2' },
  { id: 'u-103', name: 'Citra Principal', departmentId: 'd-1' },
];

const DB_DEPARTMENTS: DepartmentRecord[] = [
  { id: 'd-1', name: 'Core Platform Engineering' },
  { id: 'd-2', name: 'Distributed Data Systems' },
];

// DB query mocks with latency simulation
const dbFetchDepartmentsByIds = async (ids: readonly string[]): Promise<(DepartmentRecord | null)[]> => {
  console.log(`[DATABASE IO] Batch querying departments for IDs: ${ids.join(', ')}`);
  const idMap = new Map(DB_DEPARTMENTS.map(d => [d.id, d]));
  return ids.map(id => idMap.get(id) || null);
};

// ==========================================
// 2. CONTEXT & ISOLATION LIFECYCLE
// ==========================================
export interface AppContext {
  requestId: string;
  userId: string | null;
  loaders: {
    departmentLoader: DataLoader<string, DepartmentRecord | null>;
  };
}

export function createContextFactory(req: Request): AppContext {
  const requestId = (req.headers['x-request-id'] as string) || `req-${Math.random().toString(36).substring(2, 9)}`;
  const userId = (req.headers['x-user-id'] as string) || null;

  return {
    requestId,
    userId,
    loaders: {
      departmentLoader: new DataLoader<string, DepartmentRecord | null>(
        async (keys) => dbFetchDepartmentsByIds(keys),
        { cache: true } // Request-scoped deduplication
      ),
    },
  };
}

// ==========================================
// 3. MIDDLEWARE WRAPPER PIPELINE
// ==========================================
type ResolverMiddleware<TSource, TContext, TArgs> = (
  next: GraphQLFieldResolver<TSource, TContext, TArgs>
) => GraphQLFieldResolver<TSource, TContext, TArgs>;

function composeResolver<TSource, TContext, TArgs>(
  resolver: GraphQLFieldResolver<TSource, TContext, TArgs>,
  ...middlewares: ResolverMiddleware<TSource, TContext, TArgs>[]
): GraphQLFieldResolver<TSource, TContext, TArgs> {
  return middlewares.reduceRight((acc, fn) => fn(acc), resolver);
}

// Logging Middleware
const loggingMiddleware: ResolverMiddleware<any, AppContext, any> = (next) => {
  return async (parent, args, context, info) => {
    const start = process.hrtime.bigint();
    try {
      const result = await next(parent, args, context, info);
      const elapsed = Number(process.hrtime.bigint() - start) / 1_000_000;
      if (elapsed > 10) {
        console.warn(`[WARN-LATENCY] Resolver ${info.parentType.name}.${info.fieldName} took ${elapsed.toFixed(2)}ms`);
      }
      return result;
    } catch (err: any) {
      console.error(`[ERROR-RESOLVER] Resolver ${info.parentType.name}.${info.fieldName} failed: ${err.message}`);
      throw err;
    }
  };
};

// Auth Guard Middleware
const requireAuthMiddleware: ResolverMiddleware<any, AppContext, any> = (next) => {
  return async (parent, args, context, info) => {
    if (!context.userId) {
      throw new GraphQLError('Access Denied: Unauthenticated Execution Context', {
        extensions: { code: 'UNAUTHENTICATED', http: { status: 401 } },
      });
    }
    return next(parent, args, context, info);
  };
};

// ==========================================
// 4. GRAPHQL SCHEMA DEFINITIONS
// ==========================================
const DepartmentType = new GraphQLObjectType<DepartmentRecord, AppContext>({
  name: 'Department',
  fields: {
    id: { type: new GraphQLNonNull(GraphQLID) },
    name: { type: new GraphQLNonNull(GraphQLString) },
  },
});

const UserType: GraphQLObjectType<UserRecord, AppContext> = new GraphQLObjectType<UserRecord, AppContext>({
  name: 'User',
  fields: {
    id: { type: new GraphQLNonNull(GraphQLID) },
    name: { type: new GraphQLNonNull(GraphQLString) },
    department: {
      type: DepartmentType,
      resolve: composeResolver(
        async (user, _args, context) => {
          return await context.loaders.departmentLoader.load(user.departmentId);
        },
        loggingMiddleware
      ),
    },
  },
});

const RootQueryType = new GraphQLObjectType<null, AppContext>({
  name: 'Query',
  fields: {
    users: {
      type: new GraphQLNonNull(new GraphQLList(new GraphQLNonNull(UserType))),
      resolve: composeResolver(
        async () => DB_USERS,
        loggingMiddleware,
        requireAuthMiddleware
      ),
    },
  },
});

const schema = new GraphQLSchema({
  query: RootQueryType,
});

// ==========================================
// 5. CUSTOM EXECUTION ROUTE PIPELINE
// ==========================================
const app = express();
app.use(express.json());

app.post('/graphql', async (req: Request, res: Response) => {
  const { query, variables, operationName } = req.body;
  const contextValue = createContextFactory(req);

  try {
    // 1. Parsing Phase
    const document = parse(query);

    // 2. Validation Phase
    const validationErrors = validate(schema, document, specifiedRules);
    if (validationErrors.length > 0) {
      res.status(400).json({ errors: validationErrors });
      return;
    }

    // 3. Execution Phase
    const executionResult = await execute({
      schema,
      document,
      rootValue: null,
      contextValue,
      variableValues: variables,
      operationName,
    });

    res.status(200).json(executionResult);
  } catch (error: any) {
    res.status(500).json({
      errors: [
        new GraphQLError(`Server Execution Disaster: ${error.message}`, {
          extensions: { code: 'INTERNAL_SERVER_ERROR' },
        }),
      ],
    });
  }
});

const PORT = 4000;
app.listen(PORT, () => {
  console.log(`Execution Engine server online at http://localhost:${PORT}/graphql`);
});
```

---

## Seksi 09: Diagram Alur Kerja ASCII

### Batching Cycle via Microtask Queue (DataLoader Internals)
```
[User Resolver 1] -------------> departmentLoader.load('d-1') ---\
[User Resolver 2] -------------> departmentLoader.load('d-2') ----+---> [DataLoader Internal Queue: ['d-1', 'd-2', 'd-1']]
[User Resolver 3] -------------> departmentLoader.load('d-1') ---/
        |
        | (Engine resolves promises on Current Tick)
        v
[Event Loop Microtask: process.nextTick / Promise.then]
        |
        v
[DataLoader Batch Function Triggers]
        |
        +----> Deduplikasi keys: ['d-1', 'd-2']
        |
        +----> Single Query: SELECT * FROM departments WHERE id IN ('d-1', 'd-2')
        |
        v
[Resolves each Loader Promise in Map]
        |
        +----> Dispatched back to nested User.department resolvers
```

---

## Seksi 10: Analisis Trade-offs

| Pendekatan / Pola | Keuntungan | Kerugian | Skenario Penggunaan yang Tepat |
| :--- | :--- | :--- | :--- |
| **Field-Level Resolvers + DataLoader** | *Decoupled*, modular, independen dari level kedalaman query, zero boilerplate join logic. | Overhead instansiasi Loader per-request, pemrosesan bertingkat dalam memori. | Arsitektur Microservices atau domain terdistribusi dengan GraphQL Gateway. |
| **Top-Level Heavy Resolvers (SQL Joins)** | Latensi IO minimal (1 Query dengan SQL Joins via AST inspection). | Logika resolusi monolitik, tightly-coupled, sulit mempertahankan modularitas skema. | Relational DB monolitik murni dengan kebutuhan throughput ekstrem pada nested queries. |
| **Generic Schema Middleware** | Abstraksi cross-cutting concerns (Auth, Tracing) di satu titik sentral. | Overhead memory frame call pada engine, tracing stack trace menjadi lebih kompleks. | Enterprise GraphQL API dengan compliance logging dan zero-trust role engine. |

---

## Seksi 11: Best Practices & Antipatterns

### Best Practices
* **Request-Scoped Loader Isolation:** Selalu instansiasi DataLoader di dalam Context Factory per-request untuk menghindari kontaminasi memory cache antar user.
* **Keep Resolvers Pure & Thin:** Resolver hanya berperan mentransformasi context, memvalidasi input, dan mendelegasikan pemanggilan ke domain service / use-case layer.
* **Granular Nullability Design:** Buat field nullable secara sadar (`Type`) untuk menampung localized failures tanpa merusak seluruh selection set tree.

### Antipatterns
* **Over-wrapping Non-Nullables (`Type!`) Everywhere:** Satu downstream transient failure akan me-nullify seluruh root JSON jika semua field bertipe `!`.
* **Database IO inside Loops:** Mengeksekusi queries database langsung di dalam resolver list tanpa batching pattern.
* **Global DataLoader Singletons:** Menggunakan singleton DataLoader yang dibagi ke semua HTTP requests. Hal ini menyebabkan memory leak masif dan kebocoran data sensitif antar-tenant.

---

## Seksi 12: Security Hardening
1. **Query Depth & Complexity Limits:** Cegah eksploitasi rekursif AST DoS attacks sebelum masuk ke fase eksekusi:
```typescript
import { ValidationContext, ValidationRule } from 'graphql';

export function createDepthLimitRule(maxDepth: number): ValidationRule {
  return (context: ValidationContext) => {
    return {
      OperationDefinition(node) {
        const depth = calculateDepth(node);
        if (depth > maxDepth) {
          context.reportError(
            new GraphQLError(`Query depth of ${depth} exceeds maximum allowable limit of ${maxDepth}.`, {
              nodes: [node],
              extensions: { code: 'BAD_USER_INPUT' }
            })
          );
        }
      }
    };
  };
}

function calculateDepth(node: any, currentDepth = 0): number {
  if (!node.selectionSet) return currentDepth;
  return Math.max(
    ...node.selectionSet.selections.map((s: any) => calculateDepth(s, currentDepth + 1))
  );
}
```
2. **Execution Masking (Error Sanitization):** Jangan pernah mengembalikan internal stack trace atau SQL string syntax errors ke client dalam error extensions.

---

## Seksi 13: Observabilitas & Debugging
Metrik resolusi kritis yang wajib dikumpulkan per node traversal:

```typescript
// OpenTelemetry Resolver Metric Tracing Hook
import { GraphQLResolveInfo } from 'graphql';

export function traceResolverExecution(info: GraphQLResolveInfo, startHr: bigint, isError: boolean) {
  const duration = Number(process.hrtime.bigint() - startHr) / 1_000_000;
  const path = responsePathToArray(info.path).join('.');
  
  // Kirim ke APM Collector / Prometheus
  console.log(JSON.stringify({
    timestamp: new Date().toISOString(),
    trace: 'RESOLVER_EXECUTION',
    path,
    returnType: info.returnType.toString(),
    durationMs: duration,
    status: isError ? 'FAIL' : 'OK'
  }));
}

function responsePathToArray(path: any): (string | number)[] {
  const flattened: (string | number)[] = [];
  let curr = path;
  while (curr) {
    flattened.unshift(curr.key);
    curr = curr.prev;
  }
  return flattened;
}
```

---

## Seksi 14: Benchmarking & Performance
Gunakan k6 untuk memvalidasi throughput engine sebelum dan sesudah DataLoader diimplementasikan.

### Baseline Benchmark Script (`load-test.js`)
```javascript
import http from 'k6/http';
import { check } from 'k6';

export const options = {
  vus: 50,
  duration: '30s',
};

export default function () {
  const payload = JSON.stringify({
    query: `
      query GetUsersWithDepartments {
        users {
          id
          name
          department {
            id
            name
          }
        }
      }
    `,
  });

  const params = {
    headers: {
      'Content-Type': 'application/json',
      'x-user-id': 'admin-benchmark',
    },
  };

  const res = http.post('http://localhost:4000/graphql', payload, params);
  check(res, {
    'status is 200': (r) => r.status === 200,
    'no errors': (r) => !JSON.parse(r.body).errors,
  });
}
```

**Target Metrics:**
* Latensi $p99 < 50\text{ ms}$ pada 1000 RPS.
* Total DB round-trips untuk nested User-Department query = 2 (bukan $1 + N$).

---

## Seksi 15: Hands-on Lab Mini-Project
**Tantangan:** Implementasikan schema blog dengan relational hierarchy: `Post` -> `Author (User)` dan `Post` -> `Comments` -> `Author (User)`. 

### Instruksi:
1. Buat batch loader untuk `PostLoader`, `CommentLoader`, dan `UserLoader`.
2. Eksekusi query dengan nested author ganda (Post author + Comment authors) dan buktikan di console bahwa `UserLoader` hanya menembak database sebanyak 1 kali untuk seluruh ID user unik yang muncul di level root maupun nested childs.

---

## Seksi 16: Automated Testing & Verification

```typescript
// test/engine.spec.ts
import { describe, it, expect } from 'vitest';
import { parse, validate, execute } from 'graphql';
import { schema, createContextFactory } from '../src/server';

describe('GraphQL Execution Engine & Resolver Test Suite', () => {
  it('harus menolak request unauthenticated via middleware', async () => {
    const mockReq: any = { headers: {} }; // No x-user-id
    const context = createContextFactory(mockReq);
    
    const query = `query { users { id name } }`;
    const document = parse(query);
    
    const result = await execute({
      schema,
      document,
      contextValue: context,
    });

    expect(result.errors).toBeDefined();
    expect(result.errors![0].extensions.code).toBe('UNAUTHENTICATED');
    expect(result.data).toBeNull();
  });

  it('harus menyelesaikan resolusi bertingkat dengan microtask batching', async () => {
    const mockReq: any = { headers: { 'x-user-id': 'usr-test' } };
    const context = createContextFactory(mockReq);
    
    const query = `
      query {
        users {
          id
          name
          department {
            id
            name
          }
        }
      }
    `;
    const document = parse(query);
    const result = await execute({
      schema,
      document,
      contextValue: context,
    });

    expect(result.errors).toBeUndefined();
    expect(result.data).toBeDefined();
    const users = (result.data as any).users;
    expect(users.length).toBe(3);
    expect(users[0].department.name).toBe('Core Platform Engineering');
  });
});
```

---

## Seksi 17: Troubleshooting Guide

| Gejala Masalah | Akar Masalah (Root Cause) | Solusi Perbaikan |
| :--- | :--- | :--- |
| `Cannot return null for non-nullable field X` | Resolver mengembalikan `null`/`undefined` atau melempar runtime error pada field berstatus `GraphQLNonNull`. | Sediakan fallback default, tangani error secara inline, atau ubah field menjadi nullable jika data memang opsional. |
| DataLoader tidak mem-batch queries (DB query dieksekusi berkali-kali) | Resolver memanggil `.load()` di dalam tick asynchronous yang berbeda (`setTimeout` atau un-awaited nested async) atau instances DataLoader terbuat baru di tiap resolver. | Pastikan DataLoader diinstansiasi 1x per request context, dan load dijalankan sinkron dalam execution promise tree. |
| Memory usage membengkak seiring waktu | DataLoader dibuat sebagai global variable sehingga cache menumpuk selamanya (*unbounded memory growth*). | Pindahkan inisialisasi DataLoader ke dalam context factory per HTTP request agar digarbage-collect saat lifecycle request selesai. |

---

## Seksi 18: Checklist Produksi
- [ ] Context Factory mengisolasi instansiasi Loader per request client.
- [ ] Validasi AST query menerapkan depth limit dan complexity analysis.
- [ ] Resolvers dibungkus dengan Error Boundary middleware untuk masking sensitive exception details.
- [ ] Mutex locking atau serial pipeline diterapkan pada Mutation level fields.
- [ ] Tidak ada un-memoized nested child queries yang berpotensi memicu $N+1$ Database IO.
- [ ] Telemetry tracing memetakan Resolver field paths (`info.path`) ke OpenTelemetry spans.

---

## Seksi 19: Ringkasan Eksekutif
Eksekusi GraphQL beroperasi menggunakan traversal tree berbasis AST dengan evaluasi top-down rekursif. Resolver adalah unit fundamental pengeksekusi data yang menerima 4 context objects (`parent`, `args`, `context`, `info`). Resolver default bersifat naif dan rentan terhadap anomali $N+1$, sehingga integrasi *batching & caching primitives* pada layer Microtask Event Loop (seperti DataLoader) menjadi syarat wajib. Perancangan skema harus menyeimbangkan fleksibilitas *field nullability* untuk mengontrol error bubbling serta menerapkan request-level lifecycle context isolation demi stabilitas, keamanan, dan konkurensi data.

---

## Seksi 20: Referensi & Bacaan Lanjutan
* **GraphQL Official Specification (October 2021 Edition)** - *Section: Execution Algorithm & Field Resolution.*
* **GraphQL.js Source Code Repository** - `src/execution/execute.ts` (`executeFields`, `completeValue` internals).
* **Lee Byron (GraphQL Co-Creator):** *DataLoader Design Pattern and Microtask Coalescing Architecture.*
* **Apollo Engineering Guides:** *GraphQL Schema Design, Performance Mitigations, and Field-Level Telemetry.*