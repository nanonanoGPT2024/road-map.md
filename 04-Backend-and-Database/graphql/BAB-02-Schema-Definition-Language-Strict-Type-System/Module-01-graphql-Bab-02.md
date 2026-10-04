# Modul 01: Schema Definition Language & Strict Type System

---

## Seksi 01: Identitas Modul

* **Track:** 04-Backend-and-Database
* **Topik:** GraphQL
* **Bab:** 02
* **Modul:** 01
* **Judul:** Schema Definition Language & Strict Type System
* **Tingkat Kesulitan:** Advanced
* **Target Pembaca:** Backend Engineers, System Architects, Platform Engineers

---

## Seksi 02: Learning Objectives

1. Memahami spesifikasi GraphQL Schema Definition Language (SDL) secara presisi, termasuk sistem tipe, parsing AST, dan validasi leksikal.
2. Menguasai pemanfaatan Object Types, Scaler Types bawaan maupun Custom Scalar (RFC 3339 Timestamp, UUID, JSON, Regex-bounded), Enum Types, Interface Types, dan Union Types.
3. Mengonstruksi Input Objects vs Output Objects, Non-Nullable Modifiers (`!`), serta List Modifiers (`[]`) secara deterministik.
4. Mendesain Schema Directives kustom pada level field dan object untuk otorisasi, formatting, dan validasi input.
5. Mengintegrasikan mekanisme dynamic schema validation dan type enforcement pada GraphQL engine berbasis TypeScript/Node.js.

---

## Seksi 03: Concept Map Diagram ASCII

```
+-------------------------------------------------------------------------+
|                      GRAPHQL TYPE SYSTEM & SDL                          |
+-------------------------------------------------------------------------+
                                     |
           +-------------------------+-------------------------+
           |                                                   |
+----------v-----------+                             +---------v---------+
|     SCALAR TYPES     |                             |   COMPOSITE TYPES |
+----------------------+                             +-------------------+
| - Int, Float, String |                             | - Object Type     |
| - Boolean, ID        |                             | - Interface       |
| - Custom Scalars     |                             | - Union Type      |
+----------+-----------+                             +---------+---------+
           |                                                   |
           +-------------------------+-------------------------+
                                     |
                        +------------v------------+
                        |     TYPE MODIFIERS      |
                        +-------------------------+
                        | - Non-Null (Type!)      |
                        | - List ([Type])         |
                        | - [Type!]! Matrix       |
                        +------------+------------+
                                     |
           +-------------------------+-------------------------+
           |                                                   |
+----------v-----------+                             +---------v---------+
|    INPUT CONTRACTS   |                             | DIRECTIVE SYSTEM  |
+----------------------+                             +-------------------+
| - Input Object Types |                             | - @deprecated     |
| - Mutation Arguments |                             | - @specifiedBy    |
| - Filter Directives  |                             | - Custom Schema   |
+----------------------+                             +-------------------+
```

---

## Seksi 04: Mengapa Relevan

REST API secara historis bergantung pada dokumentasi eksternal seperti OpenAPI/Swagger yang sering mengalami sinkronisasi asinkron terhadap implementasi kode aktual. GraphQL membalik paradigma ini melalui **Schema as a Single Source of Truth**.

GraphQL SDL bukan sekadar format dokumentasi, melainkan kontrak leksikal biner antara client dan server yang dievaluasi langsung oleh execution engine. Ketika tipe didefinisikan dalam SDL:
- Engine menjalankan static validation terhadap seluruh incoming query sebelum resolver pertama dieksekusi.
- Runtime mismatch dapat dieliminasi pada fase kompilasi/validasi request.
- Sistem tipe yang strictly enforced memungkinkan tooling otomatis (Code Generation, IDE Auto-completion, Breaking Change Detection pada CI/CD pipeline).

---

## Seksi 05: Anatomi Konsep Inti

### 1. Scalar Types & Custom Scalars
GraphQL memiliki lima built-in scalar: `Int` (signed 32-bit), `Float` (signed double-precision), `String`, `Boolean`, dan `ID` (diserialisasi sebagai String). Custom Scalars diimplementasikan dengan mendefinisikan parser untuk AST (Abstract Syntax Tree), serialisasi output, dan parsing nilai variabel JSON.

### 2. Type Modifiers Matrix
Kombinasi antara List (`[]`) dan Non-Null (`!`) menentukan validitas data:
- `[Item]`: List dapat bernilai null, elemen list dapat bernilai null (`null`, `[]`, `[null]`, `[item]`).
- `[Item]!`: List tidak boleh null, elemen list boleh null (`[]`, `[null]`, `[item]`).
- `[Item!]`: List boleh null, elemen list tidak boleh null (`null`, `[]`, `[item]`).
- `[Item!]!`: List tidak boleh null, elemen list tidak boleh null (`[]`, `[item]`).

### 3. Interface vs. Union
- **Interface:** Abstract type yang mendefinisikan field tertentu yang **harus** diimplementasikan oleh concrete object types. Resolver menggunakan `__resolveType` untuk dynamic dispatching.
- **Union:** Abstract type yang menggabungkan beberapa concrete object types tanpa mewajibkan field yang identik. Tidak boleh beranggotakan Interface atau Union lain.

### 4. Directives
Directives ditandai dengan sintaks `@` dan dapat dipasang pada deklarasi schema (Schema Directives) atau operasi query client (Execution Directives). Directive memodifikasi eksekusi, mentransformasi data, atau menjalankan otentikasi/otorisasi deklaratif.

---

## Seksi 06: Panduan Implementasi Step-by-Step

### Step 1: Inisialisasi Project Dependencies
Gunakan runtime GraphQL modern dengan library standard: `@graphql-tools/schema`, `graphql`, dan `graphql-scalars`.

```bash
mkdir graphql-strict-system && cd graphql-strict-system
npm init -y
npm install graphql @graphql-tools/schema @graphql-tools/utils express express-graphql graphql-scalars
npm install -D typescript @types/node @types/express ts-node
npx tsc --init
```

### Step 2: Konfigurasi Custom Scalar (ISO-8601 & Email)
Buat definisi scalar yang memvalidasi AST literal dan variable input secara deterministik.

### Step 3: Implementasikan Abstract Types & Resolvers
Tentukan Interface untuk entity inheritance dan Union untuk polymorphic results.

### Step 4: Pasang Custom Schema Directives
Gunakan GraphQL Tools `mapSchema` untuk memodifikasi eksekutor resolver berdasarkan metadata directive (misal `@auth` atau `@length`).

---

## Seksi 07: Contoh Kasus Sederhana

Berikut adalah skema SDL mendasar yang mengilustrasikan type modifiers, interface, dan enum:

```graphql
enum UserRole {
  ADMIN
  OPERATOR
  AUDITOR
}

interface Node {
  id: ID!
  createdAt: DateTime!
}

type User implements Node {
  id: ID!
  createdAt: DateTime!
  username: String!
  role: UserRole!
  emailAddresses: [EmailAddress!]!
}

type Query {
  node(id: ID!): Node
  users(limit: Int = 10): [User!]!
}
```

---

## Seksi 08: Implementasi Production-Grade Lengkap Kode

Berikut adalah implementasi standalone GraphQL Server menggunakan TypeScript dengan Strict SDL, Custom Scalar, Interface, Union, dan Schema Transformer Directive.

```typescript
// server.ts
import express from 'express';
import { createHandler } from 'graphql-http/lib/use/express';
import { makeExecutableSchema } from '@graphql-tools/schema';
import { mapSchema, getDirective, MapperKind } from '@graphql-tools/utils';
import { 
  GraphQLSchema, 
  GraphQLScalarType, 
  Kind, 
  GraphQLError, 
  defaultFieldResolver 
} from 'graphql';

// 1. Custom Scalar: ISO8601 DateTime
const DateTimeScalar = new GraphQLScalarType({
  name: 'DateTime',
  description: 'Valid ISO 8601 DateTime scalar representation',
  serialize(value: unknown): string {
    if (value instanceof Date) {
      return value.toISOString();
    }
    if (typeof value === 'string') {
      const date = new Date(value);
      if (!isNaN(date.getTime())) return date.toISOString();
    }
    throw new GraphQLError('DateTimeScalar Serialization Error: Value must be a valid Date object or ISO string');
  },
  parseValue(value: unknown): Date {
    if (typeof value === 'string') {
      const date = new Date(value);
      if (!isNaN(date.getTime())) return date;
    }
    throw new GraphQLError('DateTimeScalar Parse Error: Value must be an ISO 8601 date string');
  },
  parseLiteral(ast): Date {
    if (ast.kind === Kind.STRING) {
      const date = new Date(ast.value);
      if (!isNaN(date.getTime())) return date;
    }
    throw new GraphQLError('DateTimeScalar Literal Error: Invalid literal syntax for ISO 8601 string', { nodes: ast });
  },
});

// 2. Schema Definition Language (SDL)
const typeDefs = `
  directive @length(min: Int, max: Int) on FIELD_DEFINITION | INPUT_FIELD_DEFINITION
  directive @auth(roles: [Role!]!) on FIELD_DEFINITION

  scalar DateTime

  enum Role {
    SUPERADMIN
    MERCHANT
    CUSTOMER
  }

  interface Account {
    id: ID!
    email: String!
    createdAt: DateTime!
    role: Role!
  }

  type MerchantAccount implements Account {
    id: ID!
    email: String!
    createdAt: DateTime!
    role: Role!
    businessRegistrationNumber: String!
    settlementBalance: Float!
  }

  type CustomerAccount implements Account {
    id: ID!
    email: String!
    createdAt: DateTime!
    role: Role!
    loyaltyPoints: Int!
  }

  type SystemError {
    code: String!
    message: String!
  }

  union AccountResult = MerchantAccount | CustomerAccount | SystemError

  input CreateMerchantInput {
    email: String!
    businessRegistrationNumber: String!
  }

  type Query {
    getAccountById(id: ID!): AccountResult
    listAccounts: [Account!]!
  }

  type Mutation {
    createMerchant(input: CreateMerchantInput!): AccountResult!
  }
`;

// 3. Mock In-Memory Database
interface DbMerchant {
  __typename: 'MerchantAccount';
  id: string;
  email: string;
  createdAt: Date;
  role: 'MERCHANT';
  businessRegistrationNumber: string;
  settlementBalance: number;
}

interface DbCustomer {
  __typename: 'CustomerAccount';
  id: string;
  email: string;
  createdAt: Date;
  role: 'CUSTOMER';
  loyaltyPoints: number;
}

const mockDatabase: Map<string, DbMerchant | DbCustomer> = new Map([
  [
    'acc_01',
    {
      __typename: 'MerchantAccount',
      id: 'acc_01',
      email: 'engineering@corp.internal',
      createdAt: new Date(),
      role: 'MERCHANT',
      businessRegistrationNumber: 'ID-REG-994821',
      settlementBalance: 45000000.50,
    },
  ],
  [
    'acc_02',
    {
      __typename: 'CustomerAccount',
      id: 'acc_02',
      email: 'john.doe@example.com',
      createdAt: new Date(),
      role: 'CUSTOMER',
      loyaltyPoints: 1250,
    },
  ],
]);

// 4. Resolvers
const resolvers = {
  DateTime: DateTimeScalar,
  Account: {
    __resolveType(obj: any) {
      if (obj.__typename) return obj.__typename;
      if (obj.businessRegistrationNumber) return 'MerchantAccount';
      if (obj.loyaltyPoints !== undefined) return 'CustomerAccount';
      return null;
    },
  },
  AccountResult: {
    __resolveType(obj: any) {
      if (obj.__typename) return obj.__typename;
      if (obj.code && obj.message) return 'SystemError';
      if (obj.businessRegistrationNumber) return 'MerchantAccount';
      if (obj.loyaltyPoints !== undefined) return 'CustomerAccount';
      return null;
    },
  },
  Query: {
    getAccountById: (_parent: unknown, args: { id: string }): any => {
      const account = mockDatabase.get(args.id);
      if (!account) {
        return {
          __typename: 'SystemError',
          code: 'ERR_ACCOUNT_NOT_FOUND',
          message: `Entity with ID '${args.id}' does not exist in the ledger.`,
        };
      }
      return account;
    },
    listAccounts: (): (DbMerchant | DbCustomer)[] => {
      return Array.from(mockDatabase.values());
    },
  },
  Mutation: {
    createMerchant: (_parent: unknown, { input }: { input: { email: string; businessRegistrationNumber: string } }): any => {
      const id = `acc_${Math.random().toString(36).substring(2, 9)}`;
      const newMerchant: DbMerchant = {
        __typename: 'MerchantAccount',
        id,
        email: input.email,
        createdAt: new Date(),
        role: 'MERCHANT',
        businessRegistrationNumber: input.businessRegistrationNumber,
        settlementBalance: 0.0,
      };
      mockDatabase.set(id, newMerchant);
      return newMerchant;
    },
  },
};

// 5. Schema Transformer for Custom Directive (@length validation)
function lengthDirectiveTransformer(schema: GraphQLSchema, directiveName: string): GraphQLSchema {
  return mapSchema(schema, {
    [MapperKind.OBJECT_FIELD]: (fieldConfig) => {
      const lengthDirective = getDirective(schema, fieldConfig, directiveName)?.[0];
      if (lengthDirective) {
        const { resolve