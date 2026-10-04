# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 02: Schema Definition Language (SDL) & Strict Type System**  
**Kategori: 04-Backend-and-Database / GraphQL**

---

## 1. Learning Objectives
Setelah menyelesaikan modul ini, Principal Engineer/Architect diharapkan mampu:
- **Menganalisis & Mengonfigurasi AST (Abstract Syntax Tree)** dari GraphQL SDL untuk membedah tahapan *Lexing*, *Parsing*, *Validation*, dan *Execution* pada GraphQL runtime engine.
- **Mengimplementasikan Custom Scalar Types** dengan validasi dua arah (*literal AST parsing* vs *variable value parsing*) serta serialisasi data yang aman terhadap manipulasi input.
- **Membangun Custom Schema Directives** menggunakan pola AST Visitor (`SchemaDirectiveVisitor` / `@graphql-tools/utils`) untuk *policy enforcement* (autentikasi, enkripsi field-level, masking PII) secara deklaratif.
- **Mendesain Polimorfisme Lanjutan** menggunakan *Interfaces* dan *Unions* dengan *runtime discriminator* (`__resolveType`) yang terisolasi dari *business logic leakage*.
- **Memprediksi dan Mengendalikan *Null Bubbling Blast Radius*** untuk mengamankan ketersediaan data parsial (*graceful degradation*) pada sistem terdistribusi.
- **Mengintegrasikan Strict Type Governance** ke dalam pipeline CI/CD menggunakan *Schema Diffing*, validasi *Breaking Changes*, dan *Static AST Complexity Analysis*.

---

## 2. Prerequisites
Sebelum mendalami modul ini, Anda wajib menguasai:
- **Node.js (>= v20 LTS)** dan **TypeScript (>= v5.3)** dengan pemahaman mendalam tentang *discriminated unions*, *generics*, dan *type narrowing*.
- **Konsep Dasar GraphQL**: Queries, Mutations, Resolvers, dan SDL skalar primitif (`String`, `Int`, `Float`, `Boolean`, `ID`).
- **Compiler/Parser Foundations**: Pemahaman dasar mengenai BNF (Backus-Naur Form), Lexer (Tokenization), dan AST Node Representation.
- **Testing & Tooling**: Pemahaman ekosistem `graphql-js`, `@graphql-tools/schema`, dan utilitas AST traversal.

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Siklus Hidup Dokumen GraphQL: Dari SDL ke In-Memory Type Registry
GraphQL engine (`graphql-js` reference implementation) tidak mengeksekusi SDL secara langsung sebagai string teks. Runtime melakukan kompilasi *just-in-time* dari dokumen SDL menjadi objek representasi memori bernama `GraphQLSchema`.

```
[Raw SDL String] 
       │
       ▼ (Source Code)
┌──────────────┐
│    Lexer     │ ──> Menghasilkan Stream of Tokens (Punctuation, Name, StringValue)
└──────────────┘
       │
       ▼ (Tokens)
┌──────────────┐
│    Parser    │ ──> Membangun DocumentNode (Abstract Syntax Tree / AST)
└──────────────┘
       │
       ▼ (AST Node)
┌──────────────┐
│ BuildSchema/ │ ──> Memetakan AST Definitions ke Instance GraphQLNamedType
│ TypeRegistry │     (GraphQLObjectType, GraphQLScalarType, GraphQLUnionType)
└──────────────┘
       │
       ▼ (Validation Phase)
┌──────────────┐
│ Schema Rules │ ──> Memvalidasi integritas: Unique type names, Interface compliance,
│  Validation  │     Directives target validity, Non-empty Object types.
└──────────────┘
       │
       ▼
[Executable GraphQLSchema Instance]
```

1. **Lexical Analysis (Lexer)**: String SDL dipecah menjadi unit leksikal terkecil (`Token`). Parser membaca karakter demi karakter, mengabaikan *insignificant white spaces* dan komentar, lalu memproduksi token seperti `SOF` (Start of File), `Name`, `Colon`, `StringValue`, dan `EOF`.
2. **Syntactic Analysis (Parser)**: Mengonsumsi token stream untuk membangun **AST DocumentNode**. Setiap elemen dalam SDL direpresentasikan oleh node spesifik (misal: `ObjectTypeDefinitionNode`, `FieldDefinitionNode`, `DirectiveNode`).
3. **Type Registry Instantiation**: Engine membaca AST dan membuat instance konkret dari class internal:
   - `GraphQLObjectType`
   - `GraphQLInterfaceType`
   - `GraphQLUnionType`
   - `GraphQLInputObjectType`
   - `GraphQLScalarType`
   - `GraphQLEnumType`
4. **Validation Phase**: Seluruh tipe dalam registry ditautkan secara sirkular. Engine menjalankan serangkaian aturan validasi skema (contoh: memastikan field interface terimplementasi sempurna pada object type, tidak ada cyclic inheritance pada interface, dan argumen direktif cocok dengan definisinya).

### 3.2 Anatomi Abstract Syntax Tree (AST) untuk SDL
Perhatikan definisi SDL berikut:
```graphql
type Account {
  id: ID!
  balance: Float! @deprecated(reason: "Use balanceV2")
}
```
Representasi AST struktural JSON internal yang dihasilkan oleh parser `graphql-js` adalah:

```json
{
  "kind": "ObjectTypeDefinition",
  "name": { "kind": "Name", "value": "Account" },
  "interfaces": [],
  "directives": [],
  "fields": [
    {
      "kind": "FieldDefinition",
      "name": { "kind": "Name", "value": "id" },
      "arguments": [],
      "type": {
        "kind": "NonNullType",
        "type": {
          "kind": "NamedType",
          "name": { "kind": "Name", "value": "ID" }
        }
      }
    },
    {
      "kind": "FieldDefinition",
      "name": { "kind": "Name", "value": "balance" },
      "arguments": [],
      "type": {
        "kind": "NonNullType",
        "type": {
          "kind": "NamedType",
          "name": { "kind": "Name", "value": "Float" }
        }
      },
      "directives": [
        {
          "kind": "Directive",
          "name": { "kind": "Name", "value": "deprecated" },
          "arguments": [
            {
              "kind": "Argument",
              "name": { "kind": "Name", "value": "reason" },
              "value": {
                "kind": "StringValue",
                "value": "Use balanceV2",
                "block": false
              }
            }
          ]
        }
      ]
    }
  ]
}
```

### 3.3 Custom Scalar: Trinitas Validasi Data
Scalar dalam GraphQL adalah daun (*leaf node*) dari pohon query. Membuat skalar kustom mewajibkan implementasi tiga metode krusial dalam `GraphQLScalarType`:

```
Client Request (Query with Variable)           Client Request (Inline Literal)
       │                                                      │
       │ Variables: { "date": "2024-03-30T00:00:00Z" }        │ Query: { tx(date: "2024-03-30T00:00:00Z") }
       ▼                                                      ▼
┌──────────────┐                                       ┌──────────────┐
│  parseValue  │                                       │ parseLiteral │
│ (Input Value)│                                       │  (Input AST) │
└──────┬───────┘                                       └──────┬───────┘
       │                                                      │
       └───────────────────────┬──────────────────────────────┘
                               ▼
                    [Resolver Execution: Data Pipeline]
                               │
                               ▼
                    ┌─────────────────────┐
                    │      serialize      │
                    │   (Output to JSON)  │
                    └─────────────────────┘
                               │
                               ▼
                       JSON Response Client
```

- **`serialize(outputValue)`**: Dipanggil saat data mentah dikembalikan oleh resolver dan siap dikirim ke client melalui JSON payload. Wajib melakukan konversi objek runtime (misal: JavaScript `Date` atau `BigInt`) menjadi bentuk primitif JSON (`string` atau `number`).
- **`parseValue(variableValue)`**: Dipanggil ketika nilai input dikirim melalui GraphQL Variables (`variables: { ... }`). Input sudah dalam bentuk JSON terurai (misal: JSON string atau integer).
- **`parseLiteral(astNode)`**: Dipanggil ketika nilai input ditulis langsung (*hardcoded/inline*) di dalam string GraphQL query dokumen (contoh: `node(id: "123")`). Nilai ini berupa AST node (`Kind.STRING`, `Kind.INT`, dll.), sehingga validasi tipe data literal terjadi di sini.

### 3.4 Runtime Type Resolution pada Polimorfisme
GraphQL mendukung dua bentuk polimorfisme:
- **Interface**: Polimorfisme berbasis kontrak field (*abstract type* yang mewajibkan implementor memiliki kumpulan field identik).
- **Union**: Polimorfisme berbasis penandaan (*tagged union*) tanpa keharusan berbagi field yang sama.

Pada runtime, GraphQL executor mengeksekusi abstraksi polimorfik menggunakan fungsi **`__resolveType(value, context, info)`**. Executor tidak melakukan *reflection* secara otomatis; engineer wajib menyediakan discriminator deterministik yang mengembalikan nama konkret dari `GraphQLObjectType` string.

---

## 4. Why & What

| Fitur / Konsep | Mengapa Dibutuhkan di Skala Enterprise? | Apa yang Terjadi Jika Salah/Tanpa Konsep Ini? |
| :--- | :--- | :--- |
| **Strict Custom Scalars** | Memastikan domain primitive (seperti `UUIDv4`, `ISODateTime`, `CurrencyCode`, `EncryptedString`) divalidasi di boundary jaringan sebelum masuk ke resolver/domain logic. | Input invalid menembus ke domain layer, menyebabkan inkonsistensi database, runtime injection, dan crash pada resolver internal. |
| **Schema Directives** | Menjaga kode resolvers tetap *clean* dengan menerapkan *cross-cutting concerns* (AuthZ, Rate-limiting, Field-level Decryption) secara deklaratif pada schema. | *Boilerplate duplication* di setiap resolver. Kegagalan enforcing policy akibat kelalaian developer saat menambahkan resolver baru. |
| **Interface vs Union Separation** | Mengidentifikasi kontrak entitas bisnis secara semantik; Interface untuk entitas berbagi atribut (e.g., `Node`, `Auditable`), Union untuk hasil heterogen (e.g., Result/Error patterns). | Skema membingungkan konsumen API, duplikasi field eksplisit pada Union, atau kegagalan inheritance validation pada Interface. |
| **Strict Nullability Management** | Menentukan *failure boundaries* untuk memitigasi *cascading failures* di microservices. | **Null Bubbling Disaster**: Satu field `Non-Null` yang gagal me-resolve data dari microservice yang sedang down akan memusnahkan seluruh objek hingga root query (`data: null`). |

---

## 5. How (Workflow Detail)

Berikut adalah alur produksi dalam merancang, memvalidasi, dan mengeksekusi SDL GraphQL dengan tipe ketat:

```
[1. SDL & Directives Definition]
               │
               ▼
[2. AST Lexing & Parsing via parse()]
               │
               ▼
[3. Custom Type Definition Mapping (Scalars, Interfaces, Unions)]
               │
               ▼
[4. Directives Schema Transformation (AST Visitor Pattern)]
               │
               ▼
[5. Static Schema Validation via validateSchema()]
               │
               ▼
[6. Incoming Query Execution & Error Boundary Traversal]
```

### Prosedur Implementasi Schema Directives via Visitor
1. **Deklarasikan Direktif pada SDL**: Tentukan target lokasi menggunakan skope valid (`FIELD_DEFINITION`, `OBJECT`, dsb.).
2. **Buat Fungsi Transformasi Skema**: Gunakan `@graphql-tools/utils` (`mapSchema`, `getDirective`) untuk menelusuri type map.
3. **Bungkus Resolver Target**: Tangkap resolver asli dari field, terapkan logika interceptor (pre/post-hook), lalu kembalikan field configuration yang telah dimodifikasi.
4. **Validasi Runtime Error Boundary**: Pastikan eksepsi di dalam directive handler menghasilkan standard `GraphQLError` dengan *extensions code* yang tepat.

---

## 6. Analogy & Diagram ASCII

### Analogi Pipa & Filter Kualitas Air
Bayangkan pemrosesan data GraphQL seperti sistem pengolahan air bersih:
- **Lexer & Parser**: Mesin pemilah air dari sungai yang memisahkan batuan kasar (tokenizing) dan menyalurkan air ke pipa khusus (AST).
- **Strict Scalar**: Filter membran nano di gerbang masuk. Hanya partikel dengan dimensi dan polaritas identik (misal: Format ISO Date) yang diizinkan lewat. Partikel tanah (malformed input) ditolak langsung di gerbang.
- **Null Bubbling (Ledakan Pipa Vakum)**: Sistem pipa bertekanan tinggi di mana setiap sambungan diberi label "Boleh Kering" (`Nullable`) atau "Wajib Basah" (`Non-Null / !`). Jika pipa berlabel "Wajib Basah" mendadak kering (resolver gagal/null), sistem vakum pecah, merusak pipa di atasnya, terus merambat naik sampai menemukan katup isolasi bertanda "Boleh Kering" pertama. Jika sampai pipa utama tidak ada katup "Boleh Kering", seluruh instalasi mati total.

```
NULL BUBBLING BLAST RADIUS:

Case A: Resilient Design (Nullable parent boundary)
Query Root (Nullable) ───────────────────────────┐ [Data Valid Diterima]
  │                                              │
  ├── user (Nullable)                            │
  │     ├── id: "usr_101"                        │
  │     └── profile (Nullable) ── [X] Error!     │ (profile gagal, return null)
  │                                (Bubbles up)  │
  │           Result: user.profile = null        │
  │           user.id tetap selamat!             │
  │                                              │
Case B: Catastrophic Design (Overzealous Non-Null)│
Query Root (Non-Null!)                           ▼ [BENCANA TOTAL]
  │
  └── user (Non-Null!)
        ├── id: "usr_101"
        └── profile (Non-Null!) ── [X] Error! (Gagal resolve)
              │
              ├── profile null -> melanggar kontrak Non-Null!
              ├── bubble ke `user` -> `user` harus Non-Null -> melanggar!
              └── bubble ke `Query` -> root Non-Null hancur!
              Result: { "data": null, "errors": [...] }
```

---

## 7. Practical Implementation (Kode Standar Industri)

Berikut adalah implementasi enterprise-ready yang mendemonstrasikan Custom Scalar (`DateTimeRFC3339`), Dynamic Schema Directives (`@auth` dan `@mask`), Interface, Discriminator Union, dan error handling.

### Struktur Modul
```
src/
├── directives/
│   ├── authDirective.ts
│   └── maskDirective.ts
├── scalars/
│   └── DateTimeRFC3339.ts
├── types/
│   └── polymorphic.ts
└── schema.ts
```

#### File: `src/scalars/DateTimeRFC3339.ts`
```typescript
import { GraphQLScalarType, Kind, GraphQLError } from 'graphql';

const RFC3339_REGEX =
  /^(\d{4})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])T([01]\d|2[0-3]):([0-5]\d):([0-5]\d)(\.\d+)?(Z|[+-]([01]\d|2[0-3]):([0-5]\d))$/;

function validateDate(value: unknown): string {
  if (typeof value !== 'string') {
    throw new GraphQLError(`Value must be a string, received: ${typeof value}`);
  }

  if (!RFC3339_REGEX.test(value)) {
    throw new GraphQLError(`Value "${value}" is not a valid RFC3339 timestamp string.`);
  }

  const parsedDate = new Date(value);
  if (Number.isNaN(parsedDate.getTime())) {
    throw new GraphQLError(`Value "${value}" represents an invalid date calendar.`);
  }

  return value;
}

export const DateTimeRFC3339Scalar = new GraphQLScalarType({
  name: 'DateTimeRFC3339',
  description: 'A strict RFC 3339 compliant Date-Time string representation.',
  serialize(outputValue: unknown): string {
    if (outputValue instanceof Date) {
      if (Number.isNaN(outputValue.getTime())) {
        throw new GraphQLError('DateTimeRFC3339: Output Date instance is Invalid Date');
      }
      return outputValue.toISOString();
    }
    return validateDate(outputValue);
  },
  parseValue(inputValue: unknown): Date {
    const validString = validateDate(inputValue);
    return new Date(validString);
  },
  parseLiteral(ast): Date {
    if (ast.kind !== Kind.STRING) {
      throw new GraphQLError(
        `DateTimeRFC3339 only accepts String literals, received Kind: ${ast.kind}`,
        { nodes: ast }
      );
    }
    const validString = validateDate(ast.value);
    return new Date(validString);
  },
});
```

#### File: `src/directives/authDirective.ts`
```typescript
import { mapSchema, getDirective, MapperKind } from '@graphql-tools/utils';
import { GraphQLSchema, defaultFieldResolver, GraphQLError } from 'graphql';

export interface AuthContext {
  user?: {
    id: string;
    roles: string[];
  };
}

export function authDirectiveTransformer(
  schema: GraphQLSchema,
  directiveName = 'auth'
): GraphQLSchema {
  return mapSchema(schema, {
    [MapperKind.OBJECT_FIELD]: (fieldConfig) => {
      const directive = getDirective(schema, fieldConfig, directiveName)?.[0];
      if (!directive) return fieldConfig;

      const { requires } = directive as { requires: string };
      const { resolve = defaultFieldResolver } = fieldConfig;

      fieldConfig.resolve = async function (source, args, context: AuthContext, info) {
        if (!context.user) {
          throw new GraphQLError('Unauthorized: Authentication credentials required.', {
            extensions: { code: 'UNAUTHENTICATED', http: { status: 401 } },
          });
        }

        if (!context.user.roles.includes(requires)) {
          throw new GraphQLError(
            `Forbidden: Missing required authorization role "${requires}".`,
            {
              extensions: { code: 'FORBIDDEN', http: { status: 403 } },
            }
          );
        }

        return resolve(source, args, context, info);
      };

      return fieldConfig;
    },
  });
}
```

#### File: `src/directives/maskDirective.ts`
```typescript
import { mapSchema, getDirective, MapperKind } from '@graphql-tools/utils';
import { GraphQLSchema, defaultFieldResolver } from 'graphql';

export function maskDirectiveTransformer(
  schema: GraphQLSchema,
  directiveName = 'mask'
): GraphQLSchema {
  return mapSchema(schema, {
    [MapperKind.OBJECT_FIELD]: (fieldConfig) => {
      const directive = getDirective(schema, fieldConfig, directiveName)?.[0];
      if (!directive) return fieldConfig;

      const { character = '*', visibleLength = 4 } = directive as {
        character: string;
        visibleLength: number;
      };
      const { resolve = defaultFieldResolver } = fieldConfig;

      fieldConfig.resolve = async function (source, args, context, info) {
        const result = await resolve(source, args, context, info);
        if (typeof result !== 'string') return result;

        if (result.length <= visibleLength) return result;
        const maskedPart = character.repeat(result.length - visibleLength);
        const visiblePart = result.slice(-visibleLength);
        return `${maskedPart}${visiblePart}`;
      };

      return fieldConfig;
    },
  });
}
```

#### File: `src/schema.ts`
```typescript
import { makeExecutableSchema } from '@graphql-tools/schema';
import { DateTimeRFC3339Scalar } from './scalars/DateTimeRFC3339';
import { authDirectiveTransformer } from './directives/authDirective';
import { maskDirectiveTransformer } from './directives/maskDirective';
import { GraphQLError } from 'graphql';

const typeDefs = /* GraphQL */ `
  directive @auth(requires: String!) on FIELD_DEFINITION
  directive @mask(character: String = "*", visibleLength: Int = 4) on FIELD_DEFINITION

  scalar DateTimeRFC3339

  enum PaymentStatus {
    SETTLED
    FAILED
    DISPUTED
  }

  interface Node {
    id: ID!
  }

  interface Transaction implements Node {
    id: ID!
    amount: Float!
    currency: String!
    createdAt: DateTimeRFC3339!
  }

  type CreditCardPayment implements Transaction & Node {
    id: ID!
    amount: Float!
    currency: String!
    createdAt: DateTimeRFC3339!
    pan: String! @mask(character: "#", visibleLength: 4)
    network: String!
  }

  type BankTransferPayment implements Transaction & Node {
    id: ID!
    amount: Float!
    currency: String!
    createdAt: DateTimeRFC3339!
    iban: String! @mask(character: "X", visibleLength: 4)
    bic: String!
  }

  type PaymentSuccess {
    transaction: Transaction!
    receiptUrl: String!
  }

  type PaymentDeclined {
    errorCode: String!
    reason: String!
    retryable: Boolean!
  }

  union PaymentResult = PaymentSuccess | PaymentDeclined

  type User implements Node {
    id: ID!
    email: String!
    ssn: String! @auth(requires: "COMPLIANCE_OFFICER") @mask
  }

  type Query {
    node(id: ID!): Node
    getTransaction(id: ID!): Transaction
    executePayment(amount: Float!, currency: String!): PaymentResult!
  }
`;

const resolvers = {
  DateTimeRFC3339: DateTimeRFC3339Scalar,

  Node: {
    __resolveType(obj: { pan?: string; iban?: string; email?: string }) {
      if ('pan' in obj) return 'CreditCardPayment';
      if ('iban' in obj) return 'BankTransferPayment';
      if ('email' in obj) return 'User';
      return null;
    },
  },

  Transaction: {
    __resolveType(obj: { pan?: string; iban?: string }) {
      if ('pan' in obj) return 'CreditCardPayment';
      if ('iban' in obj) return 'BankTransferPayment';
      return null;
    },
  },

  PaymentResult: {
    __resolveType(obj: { transaction?: unknown; errorCode?: string }) {
      if ('transaction' in obj) return 'PaymentSuccess';
      if ('errorCode' in obj) return 'PaymentDeclined';
      return null;
    },
  },

  Query: {
    node: () => ({
      id: 'usr_01HJ89Z',
      email: 'alex.rivera@enterprise.internal',
      ssn: '123-45-6789',
    }),
    getTransaction: () => ({
      id: 'tx_cc_98124',
      amount: 145000.5,
      currency: 'USD',
      createdAt: new Date('2024-03-30T10:15:30.000Z'),
      pan: '4111111111114321',
      network: 'VISA',
    }),
    executePayment: (_, { amount }: { amount: number }) => {
      if (amount > 100000) {
        return {
          errorCode: 'ERR_LIMIT_EXCEEDED',
          reason: 'Daily transaction limit surpassed.',
          retryable: false,
        };
      }
      return {
        transaction: {
          id: 'tx_bt_09876',
          amount,
          currency: 'EUR',
          createdAt: new Date(),
          iban: 'DE89370400440532013000',
          bic: 'DBEUTDDDXXX',
        },
        receiptUrl: 'https://cdn.paygate.internal/receipts/tx_bt_09876.pdf',
      };
    },
  },
};

let baseSchema = makeExecutableSchema({ typeDefs, resolvers });
baseSchema = authDirectiveTransformer(baseSchema);
baseSchema = maskDirectiveTransformer(baseSchema);

export const enterpriseSchema = baseSchema;
```

---

## 8. Real-World Case Study: Financial Clearing House Gateway

### Arsitektur Sistem
Pada platform *Cross-Border Financial Settlement* multi-tenant berkapasitas 45.000 TPS, API Gateway berbasis GraphQL bertindak sebagai orkestrator sentral di atas ribuan microservices (Swift Messaging, Fraud Engine, Core Ledger, AML Checking).

```
                      Client / Core Banking
                               │
                               ▼
               ┌───────────────────────────────┐
               │    GraphQL Edge Gateway       │
               │   (Validation, AST Shield)    │
               └───────────────┬───────────────┘
                               │
       ┌───────────────────────┼───────────────────────┐
       ▼                       ▼                       ▼
┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│ Swift Engine│         │ Fraud Core  │         │ Ledger Svc  │
│  (REST API) │         │   (gRPC)    │         │  (Database) │
└─────────────┘         └─────────────┘         └─────────────┘
```

### Masalah Skala Besar (Production Incident)
- **Problem 1 (Null Cascade Disaster)**: Skema awal mendefinisikan field `settlementLedger: LedgerEntry!` secara non-nullable. Saat service database Ledger mengalami transient network timeout (P99 > 3000ms), resolver menghasilkan `null`. Akibat tanda seru (`!`), terjadi *Null Bubbling* ke root objek pembayaran, menghapus `transactionId`, `swiftMessageReference`, dan metadata lainnya. Klien perbankan menerima `{ "data": null }` dan memicu retry transaksi massal (*thundering herd*), menduplikasi data payload settlement.
- **Problem 2 (V8 Bailout & Polymorphic Deoptimization)**: Penggunaan union besar `SettlementEvent = TypeA | TypeB | ... TypeZ` (26 subtypes) dengan discriminator duck-typing dinamis (`if ('prop' in obj)`) di dalam loop ribuan event menyebabkan V8 engine mengalami deopt *megamorphic call-site*, menaikkan CPU usage gateway hingga 92%.

### Solusi Teknis & Arsitektur
1. **Resilient Nullability Boundaries**:
   Seluruh entitas integrasi eksternal didefinisikan sebagai *nullable* pada tingkatan gateway, namun *non-nullable* pada tingkatan internal domain types:
   ```graphql
   type Query {
     settlement(id: ID!): SettlementPayload # Nullable boundary: Menahan bubbling
   }
   type SettlementPayload {
     id: ID! # Non-nullable domain field
     ledgerStatus: LedgerEntry # Microservice boundary: Aman jika ledger down
     auditTrail: [AuditLog!]! # Garansi array terdefinisi, elemen tidak boleh null
   }
   ```
2. **Explicit Class-Based Discriminator (`__isTypeOf`)**:
   Menghapus duck-typing dinamis pada runtime resolver dan menggantinya dengan monomorphic identity mapping menggunakan instance constructor internal atau tag eksplisit (`__typename` langsung pada service envelope DTO):
   ```typescript
   export class SwiftSettlementModel {
     readonly __typename = 'SwiftSettlement' as const;
     constructor(public data: RawSwiftData) {}
   }
   // O(1) direct string lookup bypass V8 deoptimization
   ```

---

## 9. Trade-offs: Analisis Arsitektur

| Pendekatan | Latency (P99) | AST Parsing & Memory Overhead | Maintainability & Governance | Rekomendasi Enterprise |
| :--- | :--- | :--- | :--- | :--- |
| **Strict Non-Null (`!`) Di Mana Saja** | Rendah (tidak ada null check resolver tambahan) | Rendah (struktur tetap) | **Sangat Buruk**: Rawan cascading failure, merusak backwards compatibility saat service downstream degradasi. | Hindari pada integrasi sistem terdistribusi. Gunakan hanya pada ID, primary keys, dan input mutasi wajib. |
| **Pervasive Nullable (Semua Nullable)** | Rendah | Sedang (klien harus menulis pengecekan null berulang) | **Sedang**: Resilien terhadap downtime parsial downstream, namun menciptakan beban komputasi di sisi client (defensive coding). | Gunakan pada root fields dan agregasi data downstream lintas microservices. |
| **Deep AST Directives Transformation** | Meningkat (+2ms hingga +8ms akibat re-wrapping resolver chains) | Meningkat (kloning referensi skema & lexical closures) | **Sangat Tinggi**: Kebijakan tata kelola data (PII masking, RBAC) seragam, tersentralisasi, dan dapat diaudit secara formal. | Gunakan caching pada compiled schema, terapkan directives pada build-time/startup, bukan per-request AST walking. |
| **Large Unions vs Broad Interfaces** | Rendah pada interface monomorphic; Tinggi pada megamorphic unions | Skalabilitas memori skema linier terhadap variasi tipe polimorfik | **Union**: Fleksibel untuk hasil heterogen (Result/Error pattern).<br>**Interface**: Jauh lebih terstruktur untuk *domain entity taxonomy*. | Gunakan Union khusus operational outputs (Mutation responses); Gunakan Interface untuk domain models. |

---

## 10. Common Mistakes & Troubleshooting

### 1. The Variable Scalar Parsing Bypass Trap
*Kesalahan*: Menguji scalar hanya dengan query string inline (`tx(date: "invalid")`), yang memicu `parseLiteral`, namun lupa menguji eksekusi via JSON variables (`variables: { date: "invalid" }`), yang memicu `parseValue`.
*Dampak*: Client yang mengirimkan payload via variables dapat memasukkan data korup karena resolver `parseValue` lupa divalidasi dengan regex/logika yang sama.
*Troubleshooting*:
```typescript
// Anti-pattern: Logika validasi terpisah dan tidak simetris
parseValue(val) { return new Date(val); } // Mengembalikan Invalid Date tanpa melempar GraphQLError!
parseLiteral(ast) { /* validasi regex ketat */ }

// Enterprise Pattern: Gunakan single source of truth validator
const parseInput = (v: unknown) => assertValidIso(v);
parseValue: (val) => parseInput(val),
parseLiteral: (ast) => {
  if (ast.kind !== Kind.STRING) throw new GraphQLError(...);
  return parseInput(ast.value);
}
```

### 2. Ambiguous Interface Resolution
*Kesalahan*: Mengembalikan objek mentah dari database yang tidak memiliki discriminator jelas, sementara multiple object types mengimplementasikan interface yang sama persis.
*Dampak*: `GraphQLError: Abstract type Node must resolve to an Object type at runtime for field Query.node with value { ... }, received "undefined".`
*Troubleshooting*: Pastikan data loader menyuntikkan tag `__typename` sintetis saat memetakan entitas persistensi ke GraphQL internal layer:
```typescript
async function fetchAccount(id: string): Promise<AccountDTO> {
  const row = await db.accounts.findById(id);
  return {
    ...row,
    __typename: row.isCorporate ? 'CorporateAccount' : 'IndividualAccount',
  };
}
```

### 3. Masking Directive Menimpa Tipe Nilai Kembalian
*Kesalahan*: Menggunakan `@mask` pada field non-string tanpa type check. Ketika field bernilai `null` atau `number`, fungsi `mask.repeat()` menghasilkan runtime exception: `TypeError: Cannot read properties of undefined (reading 'length')`.
*Solusi*: Periksa tipe secara defensif di dalam directive wrapper (`if (typeof result !== 'string') return result;`).

---

## 11. Best Practices (Production Checklist)

- [ ] **Scalar Contract Enforcement**: Setiap scalar kustom wajib memiliki unit test suite mencakup: valid string, invalid string formatting, primitive type mismatch (int passed to string), `null`, dan edge conditions (e.g., Leap years, Max Safe Integers).
- [ ] **AST Recursion/Depth Defense**: Skema yang memiliki relasi berulang (*cyclic relation*, contoh: `User -> Friends -> User`) wajib diproteksi menggunakan static AST validation rule (contoh: `graphql-depth-limit` atau custom validation rule) maksimal kedalaman 6-8 tingkat.
- [ ] **Explicit `__resolveType` Implementation**: Hindari auto-detection engine bawaan. Definisikan `__resolveType` eksplisit pada setiap `GraphQLInterfaceType` dan `GraphQLUnionType`.
- [ ] **Non-Nullability Golden Rules**:
  - Gunakan `Non-Null` (`!`) pada: ID unik entitas, argumen mutation mutlak, status code bisnis.
  - Gunakan `Nullable` pada: Data dari external microservices, entitas pihak ketiga (Third-party integrations), dan field yang bergantung pada perizinan dinamis (*dynamic RBAC*).
- [ ] **Directive Execution Safety**: Directive tidak boleh mengandung *heavy database queries* yang menyebabkan blocking I/O di dalam mapping phase. Eksekusi I/O hanya boleh terjadi di dalam field resolver wrapper runtime.
- [ ] **Schema Static Analysis in CI**: Jalankan `@graphql-inspector/cli` pada pipeline pull-request untuk mendeteksi *breaking changes* (field removals, type conversions, directive placement modifications).

---

## 12. Hands-on Practice

Siapkan direktori lokal untuk menguji sistem tipe lanjutan:

### Struktur File Direktori: `hands-on/m02/`
```
hands-on/m02/
├── package.json
├── tsconfig.json
├── src/
│   ├── index.ts
│   ├── schema.ts
│   └── scalars/
│       └── CurrencyScalar.ts
```

### Langkah 1: Setup Dependensi
Buat file `hands-on/m02/package.json`:
```json
{
  "name": "hands-on-m02-strict-types",
  "version": "1.0.0",
  "main": "dist/index.js",
  "scripts": {
    "build": "tsc",
    "start": "ts-node src/index.ts"
  },
  "dependencies": {
    "@graphql-tools/schema": "^10.0.3",
    "@graphql-tools/utils": "^10.1.0",
    "graphql": "^16.8.1"
  },
  "devDependencies": {
    "@types/node": "^20.11.24",
    "ts-node": "^10.9.2",
    "typescript": "^5.3.3"
  }
}
```

Buat file `hands-on/m02/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "CommonJS",
    "rootDir": "./src",
    "outDir": "./dist",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true
  }
}
```

### Langkah 2: Buat Skalar Kustom `CurrencyCode`
File: `hands-on/m02/src/scalars/CurrencyScalar.ts`
```typescript
import { GraphQLScalarType, Kind, GraphQLError } from 'graphql';

const ISO_4217_CODES = new Set(['USD', 'EUR', 'GBP', 'JPY', 'IDR', 'SGD']);

function validateCurrency(val: unknown): string {
  if (typeof val !== 'string') {
    throw new GraphQLError(`CurrencyCode must be a string, received: ${typeof val}`);
  }
  const normalized = val.toUpperCase().trim();
  if (!ISO_4217_CODES.has(normalized)) {
    throw new GraphQLError(`Invalid ISO 4217 Currency Code: "${val}". Supported: ${Array.from(ISO_4217_CODES).join(', ')}`);
  }
  return normalized;
}

export const CurrencyCodeScalar = new GraphQLScalarType({
  name: 'CurrencyCode',
  description: 'Strict ISO 4217 Currency representation (e.g. USD, IDR)',
  serialize: (output) => validateCurrency(output),
  parseValue: (input) => validateCurrency(input),
  parseLiteral: (ast) => {
    if (ast.kind !== Kind.STRING) {
      throw new GraphQLError('CurrencyCode must be provided as a String literal', { nodes: ast });
    }
    return validateCurrency(ast.value);
  },
});
```

### Langkah 3: Rangkai Schema dan Eksekusi Verifikasi
File: `hands-on/m02/src/index.ts`
```typescript
import { graphql } from 'graphql';
import { makeExecutableSchema } from '@graphql-tools/schema';
import { CurrencyCodeScalar } from './scalars/CurrencyScalar';

const typeDefs = /* GraphQL */ `
  scalar CurrencyCode

  type Balance {
    amount: Float!
    currency: CurrencyCode!
  }

  type Query {
    balance(currencyInput: CurrencyCode!): Balance!
  }
`;

const resolvers = {
  CurrencyCode: CurrencyCodeScalar,
  Query: {
    balance: (_: unknown, { currencyInput }: { currencyInput: string }) => ({
      amount: 5000000.75,
      currency: currencyInput,
    }),
  },
};

const schema = makeExecutableSchema({ typeDefs, resolvers });

async function runTests() {
  console.log('=== TEST 1: Valid Currency via Variable ===');
  const validResult = await graphql({
    schema,
    source: `query GetBalance($curr: CurrencyCode!) { balance(currencyInput: $curr) { amount currency } }`,
    variableValues: { curr: 'IDR' },
  });
  console.log(JSON.stringify(validResult, null, 2));

  console.log('\n=== TEST 2: Invalid Currency via Inline Literal (AST Rejection) ===');
  const invalidResult = await graphql({
    schema,
    source: `query { balance(currencyInput: "BITCOIN") { amount currency } }`,
  });
  console.log(JSON.stringify(invalidResult, null, 2));
}

runTests().catch(console.error);
```

Jalankan menggunakan terminal:
```bash
npm install
npm start
```

---

## 13. Exercises

### Level Easy
Modifikasi skalar `CurrencyCodeScalar` pada hands-on di atas untuk menerima argumen dalam bentuk lowercase (misal: `"idr"`), namun selalu me-return nilai dalam uppercase string (`"IDR"`) baik saat input melalui variable maupun saat serialisasi response.
- **Kriteria Keberhasilan**: Query dengan variable `{ curr: "usd" }` berhasil dieksekusi dan me-return field `currency: "USD"`.

### Level Medium
Buat sebuah custom schema directive `@validateLength(min: Int!, max: Int!)` yang bekerja pada level `FIELD_DEFINITION`. Pasang direktif ini pada field input atau string resolver untuk membatasi panjang karakter dari string kembalian/argumen resolver. Jika batas terlampaui, lempar `GraphQLError` dengan status extension `BAD_USER_INPUT`.
- **Kriteria Keberhasilan**: Return value resolver yang panjangnya di bawah `min` atau melampaui `max` ditolak dengan error message yang informatif sebelum sampai ke client.

### Level Hard
Implementasikan skema GraphQL dengan sistem Result Pattern untuk sebuah mutation transfer dana:
- Definisikan interface `BaseMutationResponse { success: Boolean!, message: String }`.
- Definisikan tipe konkret implementor: `TransferSuccessResult`, `InsufficientFundsError`, `AccountSuspendedError`.
- Gabungkan ketiganya dalam sebuah Union `TransferResult`.
- Tuliskan dynamic discriminator `__resolveType` yang secara deterministik mengidentifikasi subtype tanpa membocorkan atribut private database ke dalam GraphQL execution context.
- **Kriteria Keberhasilan**: Semua test case transfer (sukses, saldo tidak cukup, akun beku) dieksekusi melalui satu mutation root dan client dapat meminta inline fragment (`... on InsufficientFundsError { requiredAmount }`) tanpa runtime error resolution.

---

## 14. Challenge: Dynamic Tenant AST Masking Engine

### Skenario Nyata
Anda adalah Lead Platform Architect di sebuah bank B2B multi-tenant. Beberapa instansi mitra memiliki lisensi data yang berbeda-beda:
- Mitra Level Enterprise diizinkan melihat nomor rekening lengkap (`Account.number`).
- Mitra Level Standard hanya boleh melihat nomor rekening yang telah di-mask (`Account.number` -> `****1234`).
- Mitra Terbatas sama sekali dilarang melihat field tersebut (Field harus dihapus atau di-resolve sebagai `null` secara dinamis tanpa mengubah skema dasar runtime).

### Spesifikasi Teknis Tantangan:
1. Rancang arsitektur kustom menggunakan Document AST Interceptor / Custom Execution Rule sebelum tahap resolver dieksekusi.
2. Bangun sistem transformasi query berbasis AST visitor yang mendeteksi metadata client dari request context (`context.tenantTier`).
3. Jika tenant bertipe `RESTRICTED`, rewrite AST Document yang masuk: buang field yang terproteksi oleh directive `@tenantPolicy(minTier: STANDARD)` dari selection set secara transparan, atau laporkan GraphQLError yang membatasi eksekusi field AST tersebut.
4. **Batasan**: Dilarang membuat skema terpisah untuk setiap tenant (Single compiled `GraphQLSchema` instance). Tidak boleh ada memory leak akibat rekursi AST traversal tak berbatas pada traffic tinggi.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda & Analisis Singkat)
1. Kapan fungsi `parseLiteral` pada `GraphQLScalarType` dieksekusi oleh GraphQL runtime engine?  
   a. Setiap kali resolver field me-return objek Date atau JSON.  
   b. Ketika nilai skalar dikirimkan melalui HTTP POST body `variables`.  
   c. Ketika nilai skalar ditulis langsung secara inline di dalam GraphQL query document string.  
   d. Saat server pertama kali melakukan kompilasi skema pada fase initialization.

2. Apa representasi root AST dari sebuah dokumen query GraphQL yang valid?  
   a. `SchemaDefinitionNode`  
   b. `DocumentNode`  
   c. `OperationDefinitionNode`  
   d. `FieldNode`

3. Apa perbedaan fundamental antara GraphQL `Interface` dan `Union`?  
   a. Interface tidak dapat digunakan sebagai return type pada field Query.  
   b. Union mewajibkan seluruh anggota tipe untuk mengimplementasikan field yang sama.  
   c. Interface mewajibkan anggotanya memiliki implementasi field yang sama persis, sedangkan Union dapat menggabungkan tipe-tipe yang strukturnya sama sekali berbeda.  
   d. Union mendukung nesting Union lain di dalamnya, Interface tidak.

4. Apa dampak langsung jika sebuah field bertanda `Non-Null` (`!`) mengembalikan nilai `null` dari fungsi resolver-nya?  
   a. Engine otomatis mengonversinya menjadi empty string `""` atau angka `0`.  
   b. Engine mengabaikan field tersebut dan hanya mengembalikan field lain yang valid.  
   c. Terjadi Null Bubbling ke node induk terdekat yang nullable; jika semua parent adalah Non-Null, seluruh root `data` menjadi `null`.  
   d. Server Node.js akan memicu unhandled promise rejection dan mematikan process OS.

5. Manakah target directive location yang valid jika kita ingin memasang schema directive pada definisi attribute field suatu Object Type?  
   a. `QUERY`  
   b. `OBJECT`  
   c. `FIELD`  
   d. `FIELD_DEFINITION`

---

### Bagian 2: Intermediate (Analisis Kasus & Algoritma Engine)
6. Jelaskan mengapa `serialize` pada skalar kustom wajib menangani input data yang mungkin sudah terformat secara parsial maupun objek instance asli dari database layer (seperti `Date` instance vs `string` date)!
7. Pada runtime schema transformation menggunakan `@graphql-tools/utils`, apa risiko performa jika kita melakukan wrapping resolver di dalam mapper tanpa menggunakan default resolver fallback?
8. Diberikan skema berikut:
   ```graphql
   type Query {
     user: User!
   }
   type User {
     id: ID!
     profile: Profile!
   }
   type Profile {
     avatarUrl: String!
     bio: String
   }
   ```
   Jika microservice profile mengalami kegagalan dan `avatarUrl` me-resolve nilai `null`, jelaskan apa payload JSON akhir yang diterima client!
9. Mengapa dynamic duck-typing di dalam `__resolveType` (misalnya: `if ('foo' in obj)`) dianggap sebagai *anti-pattern* pada aplikasi enterprise dengan beban tinggi?
10. Bagaimana cara GraphQL engine memvalidasi bahwa sebuah query document valid terhadap schema tanpa mengeksekusi satu pun resolver bisnis?

---

### Bagian 3: Production Scenarios
11. **Skenario Incident PagerDuty**:  
    Sebuah platform retail online meluncurkan update schema. Mereka mengubah field:  
    `inventoryStatus: InventoryStatus` (Nullable)  
    menjadi  
    `inventoryStatus: InventoryStatus!` (Non-Null).  
    Sesaat setelah rilis, ketika downstream inventory cache cluster mengalami cold-cache miss (me-return `null`), seluruh halaman Checkout pengguna di aplikasi mobile menampilkan blank white screen dan checkout terhenti total. Analisis akar masalah teknis ini pada level GraphQL Type System engine dan berikan rekomendasi perbaikan instan (hotfix) serta rekomendasi jangka panjang!

12. **Skenario API Security**:  
    Sistem Anda memiliki direktif `@auth(role: ADMIN)`. Seorang junior developer memasang direktif tersebut pada skema seperti ini:  
    `deleteUser(id: ID!): Boolean @auth(role: ADMIN)`  
    Namun, penyerang mengirimkan query introspeksi:  
    `__schema { types { name fields { name } } }`  
    dan menemukan seluruh struktur sistem internal Anda secara detail. Mengapa `@auth` pada field resolver tidak mencegah kebocoran informasi skema ini, dan bagaimana arsitektur yang benar untuk menyembunyikan skema sensitif (*schema masking/filtering*) pada level enterprise?

13. **Skenario Performance Bottleneck**:  
    Sebuah query polymorphic union meminta 500 nodes heterogen melalui cursor-based pagination. CPU profiling menunjukkan bahwa fase `completeValue` pada `graphql-js` menghabiskan 40% total execution time. Selidiki apa yang terjadi secara internal pada GraphQL runtime execution cycle dan bagaimana cara mengoptimalkan discriminator resolution-nya!

---

### Kunci Jawaban Evaluasi

#### Bagian 1: Basic
1. **c. Ketika nilai skalar ditulis langsung secara inline di dalam GraphQL query document string.**  
   *Penjelasan*: Inline string diurai oleh Parser menjadi AST node (`StringValueNode`), sehingga engine memanggil `parseLiteral(astNode)`.
2. **b. `DocumentNode`**  
   *Penjelasan*: Root representasi dari file query/schema yang diurai oleh `graphql` parser adalah AST dengan tipe `DocumentNode`.
3. **c. Interface mewajibkan anggotanya memiliki implementasi field yang sama persis, sedangkan Union dapat menggabungkan tipe-tipe yang strukturnya sama sekali berbeda.**  
   *Penjelasan*: Interface adalah kontrak field, Union adalah sekadar pengelompokan tipe konkret (tagged union).
4. **c. Terjadi Null Bubbling ke node induk terdekat yang nullable; jika semua parent adalah Non-Null, seluruh root `data` menjadi `null`.**  
   *Penjelasan*: Kontrak Non-Null menjamin tidak ada `null`. Jika dilanggar, engine melempar null ke parent secara hierarki hingga menemukan safe boundary (nullable field).
5. **d. `FIELD_DEFINITION`**  
   *Penjelasan*: `FIELD` adalah executable directive location (pada query), sedangkan `FIELD_DEFINITION` adalah type system directive location (pada SDL type).

#### Bagian 2: Intermediate
6. *Penjelasan*: `serialize` dipanggil untuk setiap data yang keluar dari resolver. Di backend, data tersebut bisa berupa class instance (misal `new Date()`) dari ORM, atau string ter-serialize dari Redis cache (misal `"2024-03-30T00:00:00Z"`). Skalar harus memvalidasi kedua kemungkinan tersebut agar pipeline serialisasi tidak crash.
7. *Penjelasan*: Menghapus `defaultFieldResolver` menyebabkan field yang tidak memiliki resolver eksplisit (field primitif mapping biasa) gagal mendapatkan data dari object parent, mengakibatkan nilai `undefined` dan merusak eksekusi field bersangkutan.
8. *Penjelasan*: Payload yang diterima adalah:  
   `{ "data": null, "errors": [ ... ] }`  
   *Detail Alur*: `avatarUrl` (Non-Null) mengembalikan null -> bubble ke `Profile` (Non-Null) -> bubble ke `user` (Non-Null) -> bubble ke root `Query` -> seluruh `data` menjadi null.
9. *Penjelasan*: Operator `in` memeriksa prototype chain objek, membatalkan optimisasi monomorphic/hidden class dari engine V8 (V8 megamorphic call deoptimization), dan menambah latensi drastis jika dipanggil pada array objek besar.
10. *Penjelasan*: Melalui fase **AST Validation**. Engine menelusuri AST `DocumentNode` menggunakan rules visitor (seperti `KnownTypeNamesRule`, `FieldsOnCorrectTypeRule`) dan mencocokkannya secara statis dengan Type Registry di memory tanpa menjalankan pemanggilan fungsi resolver.

#### Bagian 3: Production Scenarios
11. **Akar Masalah**: Mengubah field menjadi Non-Null (`!`) pada boundary dependensi distributed system adalah pelanggaran ketersediaan sistem. Ketika downstream service mengembalikan null/timeout, strict type engine memicu *Null Bubbling Blast Radius*, memusnahkan seluruh parent `Checkout` object sampai ke root.  
    **Hotfix**: Kembalikan tanda seru (`!`) menjadi Nullable pada field `inventoryStatus: InventoryStatus` di gateway SDL. Klien mobile akan menerima data checkout parsial dan dapat menampilkan fallback UI (misal: "Status inventaris sedang diverifikasi").  
    **Jangka Panjang**: Terapkan linting skema CI (`graphql-inspector`) untuk memblokir penambahan non-null constraints pada field downstream yang bergantung pada remote I/O network.
12. **Akar Masalah**: Schema Directives runtime (`FIELD_DEFINITION`) hanya melindungi **resolver invocation** (data retrieval), bukan skema itu sendiri. Introspeksi query membaca `GraphQLSchema` type registry yang dibangun saat bootstrapping.  
    **Arsitektur yang Benar**: Terapkan **Schema Filtering/Transforming** pada saat startup menggunakan `@graphql-tools/utils` `filterSchema`. Buat dua instance skema fisik yang terpisah: Public Schema (yang membuang field bertanda `@auth` dari AST type definitions) untuk klien eksternal, dan Internal Schema untuk admin.
13. **Akar Masalah Internal**: Pada fase `completeValue`, engine mengevaluasi polimorfisme untuk setiap item. Jika `__resolveType` tidak disediakan secara langsung pada objek, engine akan melakukan *brute force evaluation* iteratif memanggil predicate `isTypeOf` milik setiap subtype Union satu per satu untuk 500 nodes ($500 \times N$ checks).  
    **Solusi Optimasi**: Terapkan pemetaan $O(1)$ discriminator langsung di resolver DTO downstream: suntikkan property `__typename` langsung pada payload object DTO sebelum masuk ke execution pipeline. Engine `graphql-js` akan mendeteksi `__typename` secara instan tanpa traversal predicate tambahan.

---

## 16. Summary

- **SDL dan Strict Type System** bukan sekadar format dokumentasi, melainkan **kontrak kompilasi** yang diterjemahkan menjadi **Abstract Syntax Tree (AST)** untuk memvalidasi dan membatasi eksekusi data secara statis dan dinamis.
- **Custom Scalars** bertanggung jawab menjaga integritas gerbang domain aplikasi melalui trinitas method: `parseLiteral` (AST tokens), `parseValue` (variables), dan `serialize` (output data).
- **Directives** adalah mekanisme declarative metaprogramming untuk menyuntikkan cross-cutting logic (keamanan, transformasi data, governance) langsung ke dalam AST node definitions.
- **Polimorfisme (Interfaces & Unions)** mewajibkan discriminator deterministik (`__resolveType` atau `__typename`) dengan kompleksitas waktu $O(1)$ guna mencegah deoptimisasi V8 engine pada throughput tinggi.
- **Nullability adalah Trade-off Arsitektural**: Terlalu banyak `Non-Null (!)` menciptakan risiko **Null Bubbling Blast Radius** yang dapat melumpuhkan seluruh transaksi API gateway enterprise saat terjadi kegagalan parsial pada microservices downstream. Terapkan Non-Null secara konservatif hanya pada data core yang absolut.