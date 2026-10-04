# Bab 01: Fondasi & Arsitektur GraphQL
## Module 01: Pengenalan GraphQL, Arsitektur Inti, dan Paradigma Eksekusi

---

### 1. Learning Objectives (Tujuan Pembelajaran)
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
*   **Mengartikulasikan** perbedaan fundamental antara arsitektur REST, RPC, dan GraphQL dalam konteks *network efficiency* dan *developer ergonomics*.
*   **Menganalisis** siklus hidup kueri GraphQL dari *string raw payload*, *Abstract Syntax Tree (AST)*, validasi terhadap skema, hingga resolusi data (*runtime execution tree*).
*   **Mengidentifikasi** masalah *over-fetching*, *under-fetching*, dan *network waterfall requests* pada sistem terdistribusi serta bagaimana GraphQL menyelesaikannya.
*   **Mengimplementasikan** server GraphQL berbasis TypeScript dari nol menggunakan pustaka inti (`graphql` dan `@apollo/server`) dengan konfigurasi *context*, *type definitions*, dan *resolvers*.
*   **Mengevaluasi** risiko keamanan awal seperti *denial of service* berbasis *unbounded query depth* dan eksfiltrasi data via *introspection*.

---

### 2. Core Concept (Konsep Inti)
GraphQL bukanlah sebuah *database*, pustaka komputasi, atau *framework* UI; **GraphQL adalah sebuah spesifikasi formal (*specification*) untuk *query language* berbasis API dan *runtime execution engine*** yang pertama kali dikembangkan oleh Facebook pada tahun 2012 dan di-open-source-kan pada tahun 2015.

Secara konseptual, GraphQL membalik kontrol konsumsi data dari penyedia layanan (*server*) ke konsumen data (*client*). Dalam GraphQL:
1.  **Klien mendeklarasikan bentuk data (*shape*) yang dibutuhkan**, bukan meminta *endpoint* yang telah ditentukan secara statis oleh server.
2.  **Server mengekspos tipe data yang tersedia (*type system*)**, bukan sekumpulan URI statis.
3.  **Eksekusi bersifat terstruktur dalam representasi graf (*directed acyclic graph* saat resolusi)**, di mana setiap *field* pada kueri klien dipetakan secara deterministik ke fungsi *resolver* di sisi server.

---

### 3. Why It Matters (Mengapa Penting)
Dalam lanskap rekayasa perangkat lunak modern:
*   **Efisiensi Jaringan pada Jaringan Rentan (Mobile/Low Bandwidth):** Klien seluler sering beroperasi di bawah latensi tinggi. Mengambil 10 data yang hanya butuh 2 atribut (misal: `id` dan `name`) tidak boleh membebani transmisi dengan payload megabyte berisi puluhan relasi yang tidak digunakan.
*   **Pencegahan Erosi Kecepatan Tim (Contract Decoupling):** Frontend engineer tidak perlu lagi menunggu backend engineer membuat endpoint ad-hoc seperti `/api/v1/user-with-posts-and-comments-mobile-optimized`. Klien menyusun komposisi data sendiri dari kapabilitas skema yang sudah ada.
*   **Strongly Typed Schema Contract:** GraphQL Schema Definition Language (SDL) berfungsi sebagai kontrak tunggal sumber kebenaran (*single source of truth*) yang memungkinkan generasi kode statis (*static code generation*) secara otomatis di sisi klien (seperti TypeScript types, React Hooks, Apollo Client artifacts).

---

### 4. What Problem It Solves (Masalah yang Diselesaikan)

| Masalah Arsitektur Tradisional (REST) | Manifestasi Dampak Teknis | Solusi GraphQL |
| :--- | :--- | :--- |
| **Over-fetching** | Endpoint `/users/1` mengembalikan 80 kolom SQL termasuk `password_hash`, metadata sistem, dan alamat audit, padahal UI hanya butuh `displayName`. Membuang bandwidth dan CPU deserialisasi JSON. | Klien mendeklarasikan `query { user(id: 1) { displayName } }`. Server hanya mengembalikan field tersebut. |
| **Under-fetching** | Endpoint `/orders/123` hanya mengembalikan ID entitas relasional. Klien harus melakukan *round-trip* lanjutan ke `/users/45`, `/products/789`, dan `/shipping/99`. | Eksekusi relasional dalam satu round-trip via traversi skema: `query { order(id: 123) { user { name } product { title } } }`. |
| **Waterfall Requests** | Kueri sekuensial yang bergantung pada hasil HTTP sebelumnya meningkatkan TTI (*Time to Interactive*) pada aplikasi klien secara eksponensial. | Server menyelesaikan dependensi graf secara paralel/terstruktur internal; klien hanya melakukan 1 kali HTTP POST. |
| **API Versioning Friction** | Poliferasi endpoint: `/v1/`, `/v2/`, `/v3/` karena perubahan format field yang merusak *backward compatibility*. | *Field-level deprecation*: Field lama ditandai `@deprecated(reason: "...")`, field baru ditambahkan secara aditif ke dalam skema tanpa merusak klien lama. |

---

### 5. How It Works (Cara Kerja)
Alur pemrosesan GraphQL terjadi di runtime server melalui 4 fase deterministik:

1.  **Lexing & Parsing:**
    String kueri HTTP mentah diubah menjadi *token stream*, kemudian dibangun menjadi struktur data pohon yang disebut **AST (Abstract Syntax Tree)**.
2.  **Validation:**
    AST divalidasi terhadap **Type Schema**. Server memeriksa:
    *   Apakah field yang diminta benar-benar ada dalam skema?
    *   Apakah tipe argumen yang di-pass sesuai dengan definisi?
    *   Apakah kueri mengandung operasi ilegal (misal: meminta field pada tipe skalar)?
    Jika validasi gagal, eksekusi dihentikan secara instan dan mengembalikan *syntax/validation error* (HTTP status tetap 200 atau 400 bergantung pada implementasi server, namun tidak ada resolver yang dieksekusi).
3.  **Execution (Resolving):**
    Server menelusuri AST secara *depth-first*. Setiap node field diasosiasikan dengan sebuah fungsi pengeksekusi bernama **Resolver**.
    *   Resolver menerima 4 parameter standar: `(parent, args, context, info)`.
    *   Resolver dieksekusi secara asinkron (menggunakan `Promise` / `async-await`). Field pada kedalaman yang sama dapat dieksekusi secara paralel.
4.  **Response Formatting:**
    Hasil resolusi disusun ulang ke dalam struktur JSON yang bentuknya merefleksikan secara identik format string kueri yang dikirimkan oleh klien, dibungkus dalam root level:
    ```json
    {
      "data": { ... },
      "errors": [ ... ]
    }
    ```

---

### 6. Architecture / Mechanism Flow (Diagram Arsitektur)

```
[ KLIEN (Web / Mobile) ]
       │
       │ HTTP POST (Payload: { query, variables })
       ▼
┌──────────────────────────────────────────────────────────┐
│                 GRAPHQL RUNTIME ENGINE                   │
│                                                          │
│  ┌────────────────┐         Gagal                        │
│  │ 1. Lexer &     │ ──────────────────────┐              │
│  │    Parser      │                       │              │
│  └───────┬────────┘                       │              │
│          │ Menghasilkan AST               │              │
│          ▼                                │              │
│  ┌────────────────┐         Gagal         │              │
│  │ 2. Validator   │ ──────────────────────┤              │
│  └───────┬────────┘                       │              │
│          │ AST Valid                      │              │
│          ▼                                │              │
│  ┌─────────────────────────────────────┐  │              │
│  │ 3. Execution Engine                 │  │              │
│  │    (Breadth/Depth-First Traverser)  │  │              │
│  │                                     │  │              │
│  │    ┌───────────────────────────┐    │  │              │
│  │    │ Field Resolvers Execution │    │  │              │
│  │    └─────────────┬─────────────┘    │  │              │
│  └──────────────────┼──────────────────┘  │              │
└─────────────────────┼─────────────────────┼──────────────┘
                      │                     │
          ┌───────────┴───────────┐         │ Error Parsing/
          │ Akses Data Asinkron   │         │ Validasi
          ▼                       ▼         │
   ┌─────────────┐         ┌─────────────┐  │
   │  Database   │         │ Downstream  │  │
   │ (SQL/NoSQL) │         │ Microservice│  │
   └─────────────┘         └─────────────┘  │
          │                       │         │
          └───────────┬───────────┘         │
                      ▼                     │
┌────────────────────────────────────────┐  │
│ 4. Response Formatter                  │  │
│    { data: {...}, errors: [...] }      │◄─┘
└──────────────────┬─────────────────────┘
                   │
                   ▼ HTTP Response (JSON 200 OK)
[ KLIEN (Web / Mobile) ]
```

---

### 7. Key Components / Terminology (Komponen Kunci)
*   **Schema Definition Language (SDL):** Sintaksis deklaratif yang digunakan untuk mendefinisikan kontrak tipe data GraphQL (contoh: `type Query { ... }`).
*   **Scalar Types:** Tipe primitif daun (*leaf nodes*) pada skema: `Int`, `Float`, `String`, `Boolean`, dan `ID`. Custom scalar dapat didefinisikan (misal: `DateTime`, `JSON`).
*   **Object Types:** Komposit tipe data yang memiliki sekumpulan field bertipe skalar atau Object Type lainnya.
*   **Root Operation Types:** Tiga entry point utama dalam GraphQL:
    *   `Query`: Operasi baca data (read-only, idempotence diutamakan).
    *   `Mutation`: Operasi tulis data yang diikuti pengambilan data (*write-then-read*).
    *   `Subscription`: Aliran data waktu-nyata berbasis event-driven (biasanya via WebSockets/SSE).
*   **Resolver:** Unit fungsional terkecil yang bertanggung jawab mengambil atau menghitung nilai untuk satu field spesifik di dalam skema.
*   **Context:** Objek global yang diinisialisasi per-request, digunakan untuk berbagi instance koneksi database, informasi autentikasi pengguna, atau logging context ke seluruh resolver.
*   **Variables:** Kamus (*dictionary*) nilai dinamis yang dipisahkan dari payload kueri statis guna mencegah injeksi data dan memungkinkan serialisasi/caching AST.

---

### 8. Step-by-Step Implementation Guide
Kita akan membangun GraphQL server menggunakan Node.js, TypeScript, dan pustaka resmi `@apollo/server`.

#### Langkah 1: Inisialisasi Proyek dan Dependensi
Jalankan perintah berikut di terminal Anda:
```bash
mkdir graphql-core-module
cd graphql-core-module
npm init -y
npm install @apollo/server graphql
npm install -D typescript @types/node ts-node
npx tsc --init
```

Pastikan file `tsconfig.json` memiliki konfigurasi modul minimal:
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
  },
  "include": ["src/**/*"]
}
```

#### Langkah 2: Struktur Direktori
Susun direktori proyek seperti berikut:
```text
graphql-core-module/
├── src/
│   ├── index.ts
│   ├── schema.ts
│   └── resolvers.ts
├── package.json
└── tsconfig.json
```

---

### 9. Minimal Working Code Example

Berikut adalah implementasi minimal yang dapat langsung dieksekusi dalam satu berkas (`src/minimal.ts`):

```typescript
import { ApolloServer } from '@apollo/server';
import { startStandaloneServer } from '@apollo/server/standalone';

// 1. Skema didefinisikan via SDL
const typeDefs = `#graphql
  type Query {
    ping: String!
  }
`;

// 2. Map resolver yang bersesuaian dengan hierarki skema
const resolvers = {
  Query: {
    ping: (): string => 'pong',
  },
};

// 3. Inisialisasi engine server
async function bootstrap() {
  const server = new ApolloServer({ typeDefs, resolvers });
  const { url } = await startStandaloneServer(server, {
    listen: { port: 4000 },
  });
  console.log(`Server siap berjalan pada: ${url}`);
}

bootstrap();
```

---

### 10. Production-Ready Code Example

Implementasi berikut mencakup manajemen *Context*, autentikasi berbasis Bearer token, penanganan error struktural, dan pemisahan arsitektur yang modular.

#### `src/schema.ts`
```typescript
export const typeDefs = `#graphql
  enum UserRole {
    ADMIN
    MEMBER
    GUEST
  }

  type Post {
    id: ID!
    title: String!
    content: String!
    authorId: ID!
    author: User!
  }

  type User {
    id: ID!
    email: String!
    name: String!
    role: UserRole!
    posts: [Post!]!
  }

  type Query {
    me: User
    user(id: ID!): User
    users(limit: Int = 10, offset: Int = 0): [User!]!
  }

  input CreatePostInput {
    title: String!
    content: String!
  }

  type Mutation {
    createPost(input: CreatePostInput!): Post!
  }
`;
```

#### `src/types.ts`
```typescript
export interface UserEntity {
  id: string;
  email: string;
  name: string;
  role: 'ADMIN' | 'MEMBER' | 'GUEST';
}

export interface PostEntity {
  id: string;
  title: string;
  content: string;
  authorId: string;
}

export interface GraphQLContext {
  currentUser: UserEntity | null;
  requestId: string;
}
```

#### `src/resolvers.ts`
```typescript
import { GraphQLError } from 'graphql';
import { GraphQLContext, PostEntity, UserEntity } from './types';

// Mock in-memory database
const USERS_DB: UserEntity[] = [
  { id: '1', email: 'alice@domain.internal', name: 'Alice', role: 'ADMIN' },
  { id: '2', email: 'bob@domain.internal', name: 'Bob', role: 'MEMBER' },
];

const POSTS_DB: PostEntity[] = [
  { id: '101', title: 'Deep Dive GraphQL', content: 'Konten modul 01...', authorId: '1' },
  { id: '102', title: 'TypeScript Typings', content: 'Konten modul 02...', authorId: '1' },
  { id: '103', title: 'Microservices Communication', content: 'Konten...', authorId: '2' },
];

export const resolvers = {
  Query: {
    me: (_parent: unknown, _args: unknown, context: GraphQLContext): UserEntity => {
      if (!context.currentUser) {
        throw new GraphQLError('Unauthenticated: Autentikasi diperlukan', {
          extensions: { code: 'UNAUTHENTICATED', http: { status: 401 } },
        });
      }
      return context.currentUser;
    },

    user: (_parent: unknown, args: { id: string }): UserEntity | null => {
      const user = USERS_DB.find((u) => u.id === args.id);
      if (!user) {
        throw new GraphQLError(`User dengan ID '${args.id}' tidak ditemukan`, {
          extensions: { code: 'NOT_FOUND', http: { status: 404 } },
        });
      }
      return user;
    },

    users: (_parent: unknown, args: { limit: number; offset: number }): UserEntity[] => {
      const limit = Math.min(Math.max(args.limit, 1), 50); // Hard clamp pagination
      return USERS_DB.slice(args.offset, args.offset + limit);
    },
  },

  Mutation: {
    createPost: (
      _parent: unknown,
      args: { input: { title: string; content: string } },
      context: GraphQLContext
    ): PostEntity => {
      if (!context.currentUser) {
        throw new GraphQLError('Akses ditolak: Hanya pengguna terdaftar yang dapat membuat postingan', {
          extensions: { code: 'FORBIDDEN', http: { status: 403 } },
        });
      }

      if (args.input.title.trim().length < 3) {
        throw new GraphQLError('Validasi Gagal: Panjang judul minimal 3 karakter', {
          extensions: { code: 'BAD_USER_INPUT' },
        });
      }

      const newPost: PostEntity = {
        id: String(Date.now()),
        title: args.input.title,
        content: args.input.content,
        authorId: context.currentUser.id,
      };

      POSTS_DB.push(newPost);
      return newPost;
    },
  },

  // Field-level resolvers untuk relasi graf
  User: {
    posts: (parent: UserEntity): PostEntity[] => {
      return POSTS_DB.filter((post) => post.authorId === parent.id);
    },
  },

  Post: {
    author: (parent: PostEntity): UserEntity => {
      const author = USERS_DB.find((user) => user.id === parent.authorId);
      if (!author) {
        throw new GraphQLError(`Inkonsistensi data: Author ID '${parent.authorId}' tidak ada`, {
          extensions: { code: 'INTERNAL_SERVER_ERROR' },
        });
      }
      return author;
    },
  },
};
```

#### `src/index.ts`
```typescript
import { ApolloServer } from '@apollo/server';
import { startStandaloneServer } from '@apollo/server/standalone';
import { randomUUID } from 'crypto';
import { typeDefs } from './schema';
import { resolvers } from './resolvers';
import { GraphQLContext, UserEntity } from './types';

const USERS_AUTH_STORE: Record<string, UserEntity> = {
  'token-alice-123': { id: '1', email: 'alice@domain.internal', name: 'Alice', role: 'ADMIN' },
  'token-bob-456': { id: '2', email: 'bob@domain.internal', name: 'Bob', role: 'MEMBER' },
};

async function main() {
  const server = new ApolloServer<GraphQLContext>({
    typeDefs,
    resolvers,
    formatError: (formattedError, error) => {
      console.error(`[GraphQL Error] ID: ${(error as any)?.extensions?.requestId ?? 'N/A'}`, {
        message: formattedError.message,
        locations: formattedError.locations,
        path: formattedError.path,
        extensions: formattedError.extensions,
      });

      // Hilangkan stack trace dari response klien production
      if (process.env.NODE_ENV === 'production') {
        const { stacktrace, ...safeExtensions } = formattedError.extensions || {};
        return {
          ...formattedError,
          extensions: safeExtensions,
        };
      }

      return formattedError;
    },
  });

  const { url } = await startStandaloneServer(server, {
    listen: { port: 4000 },
    context: async ({ req }): Promise<GraphQLContext> => {
      const requestId = (req.headers['x-request-id'] as string) || randomUUID();
      const authHeader = req.headers.authorization || '';
      let currentUser: UserEntity | null = null;

      if (authHeader.startsWith('Bearer ')) {
        const token = authHeader.substring(7);
        currentUser = USERS_AUTH_STORE[token] || null;
      }

      return {
        currentUser,
        requestId,
      };
    },
  });

  console.log(`🚀 Production GraphQL Service aktif di: ${url}`);
}

main().catch((err) => {
  console.error('Inisialisasi server gagal:', err);
  process.exit(1);
});
```

---

### 11. Verification & Testing

#### Verifikasi Manual via `cURL`

1. **Uji Query Publik (Mengambil relasi User dan Posts):**
```bash
curl -X POST http://localhost:4000/ \
  -H "Content-Type: application/json" \
  -d '{
    "query": "query GetUserWithPosts($userId: ID!) { user(id: $userId) { id name role posts { id title } } }",
    "variables": { "userId": "1" }
  }'
```
*Ekspektasi Output:*
```json
{
  "data": {
    "user": {
      "id": "1",
      "name": "Alice",
      "role": "ADMIN",
      "posts": [
        { "id": "101", "title": "Deep Dive GraphQL" },
        { "id": "102", "title": "TypeScript Typings" }
      ]
    }
  }
}
```

2. **Uji Validasi Error (Meminta data profil tanpa Auth Header):**
```bash
curl -X POST http://localhost:4000/ \
  -H "Content-Type: application/json" \
  -d '{ "query": "query { me { email } }" }'
```
*Ekspektasi Output (HTTP 200 dengan payload error terstruktur):*
```json
{
  "errors": [
    {
      "message": "Unauthenticated: Autentikasi diperlukan",
      "locations": [{ "line": 1, "column": 9 }],
      "path": ["me"],
      "extensions": {
        "code": "UNAUTHENTICATED",
        "http": { "status": 401 }
      }
    }
  ],
  "data": null
}
```

3. **Uji Autentikasi Berhasil:**
```bash
curl -X POST http://localhost:4000/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer token-alice-123" \
  -d '{ "query": "query { me { email name role } }" }'
```

---

### 12. Common Pitfalls & Antipatterns
*   **Antipattern: Database Model 1:1 Mapping.**
    Mengekspos skema tabel SQL secara langsung sebagai tipe GraphQL. Ini membocorkan arsitektur basis data, menciptakan *tight-coupling*, dan membatasi evolusi domain logic. Skema GraphQL harus merefleksikan *Domain-Driven Design (DDD)* atau kebutuhan representasi UI/Klien.
*   **Pitfall: Status Code Obsession (HTTP 200 dengan Error).**
    GraphQL sengaja memisahkan protokol transport (HTTP) dari layer data. Sebuah eksekusi GraphQL yang menghasilkan error parsial akan tetap mengembalikan status `200 OK` selama dokumen berhasil diparsing dan dieksekusi, dengan data parsial di blok `data` dan masalah di blok `errors`. Jangan berasumsi HTTP 200 berarti payload bersih dari error.
*   **Pitfall: Resolving Scalar di Level Parent.**
    Mengambil data anak secara eager di resolver induk:
    ```typescript
    // SALAH
    Query: {
      user: async () => {
        const user = await getUser();
        const posts = await getPostsForUser(user.id); // Selalu dieksekusi meski klien tidak minta field `posts`
        return { ...user, posts };
      }
    }
    ```
    Biarkan resolver level-tipe (`User.posts`) yang mengeksekusinya secara modular hanya ketika diminta.

---

### 13. Performance & Resource Considerations
*   **Overhead Parsing AST:** Setiap kueri harus di-lexing dan di-parsing menjadi AST. Untuk request dengan throughput tinggi (puluhan ribu RPS), proses parsing string JSON vs string GraphQL AST dapat menyebabkan latensi CPU cycle tambahan.
    *Mitigasi:* Gunakan **Automatic Persisted Queries (APQ)**. Klien hanya mengirimkan hash SHA-256 dari string kueri; server memvalidasi hash dari memori cache tanpa perlu re-parsing string mentah.
*   **CPU Starvation via Complex Payload:** Kueri GraphQL dapat bersarang tanpa batas:
    ```graphql
    query ExploitLoop {
      me {
        posts {
          author {
            posts {
              author {
                # Terus berulang
              }
            }
          }
        }
      }
    }
    ```
    Hal ini dapat memicu ribuan konkurensi resolver yang membekukan Node.js event loop.
*   **Memory Allocations:** Setiap node AST dan tree node resolusi dialokasikan di heap v8. Skema besar dengan puluhan ribu baris SDL membutuhkan footprint RAM signifikan saat inisialisasi.

---

### 14. Security & Safety Implications
1.  **Production Introspection Exposure:**
    Secara default, GraphQL mengizinkan kueri meta: `__schema` dan `__type`. Penyerang dapat mengunduh seluruh topologi skema, termasuk field internal, pola bisnis, dan parameter privat.
    *Tindakan Preventif:* Matikan `introspection` secara eksplisit pada environment production:
    ```typescript
    const server = new ApolloServer({
      typeDefs,
      resolvers,
      introspection: process.env.NODE_ENV !== 'production',
    });
    ```
2.  **Resource Exhaustion (Denial of Service):**
    Karena sifat fleksibel GraphQL, penyerang dapat mengirim kueri raksasa yang menyebabkan *out-of-memory* (OOM).
    *Tindakan Preventif:* Terapkan pustaka validasi kedalaman seperti `graphql-depth-limit` dan analisis biaya kueri (*query cost analysis*) sebelum fase eksekusi AST dimulai.
3.  **Field-Level Authorization Vulnerabilities:**
    Jangan hanya memvalidasi izin akses di tingkat endpoint HTTP atau root Query. Jika pengguna biasa meminta field `user { role salaryHistory }`, otorisasi harus diperiksa secara granular di resolver `salaryHistory`.

---

### 15. Trade-offs & Alternatives

```
                     LATENSI RENDAH / SERIALISASI BINER
                                     ▲
                                     │     gRPC / Protobuf
                                     │
                                     │
                                     │
FLEKSIBILITAS KLIEN ─────────────────┼─────────────────► KONTRACT TETAP / KONTROL SERVER
(Declarative Fetching)               │                   (Rigid Schemas)
       GraphQL                       │
                                     │
                                     │     REST / OpenAPI
                                     ▼
                      STANDAR PROTOKOL HTTP / EDGE CACHE MUDAH
```

*   **GraphQL vs REST:**
    REST sangat unggul dalam pemanfaatan **HTTP Caching di level proxy/CDN (Varnish, Cloudflare)** karena resource dipetakan langsung ke URI statis dan metode HTTP semantik (`GET`, `PUT`, `DELETE`). GraphQL mengirim hampir seluruh request via `POST /graphql`, sehingga HTTP GET edge-caching tradisional membutuhkan arsitektur tambahan (seperti Cache-Control HTTP extensions atau Stored Queries).
*   **GraphQL vs gRPC:**
    Untuk komunikasi internal antar mikroservis (*service-to-service internal east-west traffic*), gRPC (HTTP/2 + Protobuf) jauh lebih cepat, hemat memori, dan minim payload serialization latency. GraphQL paling bersinar pada posisi **Backend-For-Frontend (BFF)** atau *API Gateway* yang menghubungkan klien eksternal dengan kumpulan microservices di belakangnya.
*   **GraphQL vs tRPC:**
    Jika aplikasi Anda adalah *monorepo end-to-end TypeScript* (klien dan server sepenuhnya TypeScript), tRPC memberikan type-safety penuh tanpa perlu fase kompilasi skema atau parsing AST di runtime. Namun, tRPC tidak cocok jika API Anda dikonsumsi oleh aplikasi Android (Kotlin), iOS (Swift), atau pihak ketiga (Third-party developer).

---

### 16. Best Practices & Guidelines
*   **Skema SDL Naming Conventions:**
    *   Tipe Object: `PascalCase` (contoh: `UserProfile`, `PurchaseOrder`).
    *   Field dan Argumen: `camelCase` (contoh: `createdAt`, `userId`).
    *   Enum: `SCREAMING_SNAKE_CASE` (contoh: `ACTIVE_STATUS`, `PAYMENT_PENDING`).
    *   Tipe Input: Selalu gunakan suffix `Input` (contoh: `CreatePostInput`).
*   **Pemberian Tipe Non-Nullable (`!`):**
    *   Gunakan non-nullable (`!`) secara defensif pada input argumen.
    *   Hati-hati pada return types; jika database berpotensi gagal mengambil nilai atau resolver melemparkan error, field yang tidak bertanda `!` akan mengembalikan `null` ke klien tanpa merusak seluruh objek JSON. Field bernilai `!` yang melempar error akan memicu *error bubbling* hingga menemukan parent non-nullable terdekat atau membatalkan seluruh blok `data`.
*   **Context Isolation:**
    Jangan pernah menaruh state mutable berbasis request di luar objek `context`. Hal ini krusial untuk mencegah kebocoran data (*data leakage*) antar request konkuren di lingkungan async Node.js.

---

### 17. Real-World Case Study
**Skenario:** Aplikasi E-Commerce "ShopFast" memiliki halaman Checkout yang membutuhkan:
1. Informasi user aktif.
2. Daftar item keranjang belanja.
3. Rincian status stok masing-masing item (dari Inventory Service).
4. Opsi voucher diskon yang valid (dari Promo Service).

**Pendekatan REST Tradisional:**
*   Klien melakukan 4 panggilan beruntun (*network waterfall*):
    `GET /api/me` -> `GET /api/cart` -> `POST /api/inventory/check` -> `GET /api/promos`.
*   *Hasil:* Pada koneksi 4G dengan RTT (Round Trip Time) 80ms, latensi total agregat mencapai 320ms + processing time. Jika satu request lambat, rendering antarmuka terblokir sebagian.

**Migrasi ke GraphQL Architecture (BFF Layer):**
*   Dibuat API Gateway GraphQL tunggal.
*   Klien mengirimkan 1 kueri komposit:
    ```graphql
    query CheckoutState {
      me {
        id
        balance
      }
      cart {
        items {
          productId
          quantity
          inventoryStatus {
            isAvailable
          }
        }
      }
      availablePromos {
        code
        discountAmount
      }
    }
    ```
*   *Hasil Operasional:*
    *   Klien hanya melakukan **1 kali HTTP POST request**.
    *   Latensi transfer jaringan terpangkas hingga 70% di mobile client.
    *   Resolver GraphQL di server menghubungi Inventory Service dan Promo Service secara paralel menggunakan jaringan privat data center internal berlatensi rendah (<2ms).

---

### 18. Troubleshooting Guide

| Gejala Masalah (*Symptom*) | Akar Penyebab (*Root Cause*) | Solusi Verifikasi & Perbaikan |
| :--- | :--- | :--- |
| `Cannot return null for non-nullable field X.y` | Skema mendefinisikan field `y: Type!`, tetapi resolver mengembalikan `null`, `undefined`, atau melempar eksepsi internal yang tidak tertangkap. | Periksa database query. Pastikan data tidak bernilai null, tangani error dengan aman, atau ubah skema menjadi nullable `y: Type` jika data bersifat opsional. |
| `Unknown argument "X" on field "Y"` | Argumen yang dikirim klien tidak didefinisikan pada tipe field dalam SDL, atau terjadi typo pada payload variable. | Periksa definisi input pada skema. Pastikan parameter cocok karakter per karakter dengan deklarasi SDL. |
| Performa anjlok seketika saat relasi diakses (*High latency/DB spike*) | **The N+1 Query Problem**. Resolver mengeksekusi 1 query SQL per baris data parent dalam loop relasional. | Terapkan **DataLoader** (akan dibahas mendalam pada Modul Lanjutan) untuk melakukan *batching* dan *caching* kueri ke basis data. |
| Response JSON selalu `errors` tanpa HTTP status code selain 200 | Perilaku native GraphQL: Transport error dipisahkan dari schema/resolver execution error. | Jangan gunakan standard response interceptor HTTP status code semata di frontend. Periksa keberadaan properti `.errors` di payload JSON. |

---

### 19. Exercises & Challenges

#### Latihan 1 (Bug Hunt - Resolving Pipeline)
Diberikan fragmen skema berikut:
```graphql
type Task {
  id: ID!
  title: String!
  isCompleted: Boolean!
}

type Query {
  tasks: [Task!]!
}
```
Jika resolver ditulis seperti ini:
```typescript
const resolvers = {
  Query: {
    tasks: () => {
      return [
        { id: "1", title: "Setup Engine", isCompleted: true },
        { id: "2", title: "Fix Server", isCompleted: null } // <-- NILAI NULL
      ];
    }
  }
};
```
*Tantangan:* Analisis apa yang akan dikembalikan oleh GraphQL Engine saat klien menjalankan `query { tasks { id title isCompleted } }`? Jelaskan fenomena *Error Bubbling* yang terjadi di sini. Tuliskan perbaikan resolver-nya!

#### Latihan 2 (Implementasi Fitur)
Tambahkan entitas `Comment` ke kode *Production-Ready* di Bagian 10:
1. `Post` harus memiliki field `comments: [Comment!]!`.
2. Setiap `Comment` harus memiliki atribut: `id: ID!`, `text: String!`, `author: User!`, dan `createdAt: String!`.
3. Buat mutasi `addComment(postId: ID!, text: String!): Comment!`.
4. Pastikan validasi otorisasi berjalan: Pengguna anonim dilarang menambahkan komentar.

---

### 20. Summary & Next Steps
Pada modul ini, kita telah membedah GraphQL dari sudut pandang internal arsitektural:
*   GraphQL beroperasi sebagai spesifikasi eksekusi deklaratif berbasis AST, bukan implementasi penyimpanan.
*   Model eksekusi resolver memecah struktur graf secara rekursif, menyelesaikan relasi secara dinamis sesuai kebutuhan klien tanpa over-fetching.
*   Implementasi server membutuhkan kontrol ketat terhadap context isolation, type integrity, error formatting, dan mitigasi keamanan sejak level desain skema.

**Langkah Selanjutnya (Bab 01 - Module 02):**
Kita akan mengeksplorasi **"Schema Design Mastery: Core Types, Interfaces, Unions, dan Custom Scalars"**. Kita akan mempelajari cara memodelkan sistem tipe yang kompleks, merancang schema polymorphism menggunakan GraphQL `Union` dan `Interface`, serta menulis *Custom Scalar Engine* untuk parsing validasi data ISO-DateTime dan email secara native.