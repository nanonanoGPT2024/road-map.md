# Modul 01: Real-time Architecture: Subscriptions & Streaming

---

## 01. IDENTITAS MODUL

*   **Jalur**: Backend and Database Engineering
*   **Kategori**: GraphQL Architecture & Implementation
*   **Mata Kuliah**: Enterprise GraphQL Systems
*   **Tingkat Kemahiran**: Advanced (Tingkat Lanjut)
*   **Estimasi Waktu Selesai**: 6 Jam
*   **Prasyarat**:
    *   Pemahaman mendalam mengenai GraphQL Schema Definition Language (SDL) dan Resolver Execution Engine.
    *   Penguasaan asynchronous programming (Node.js Promises/AsyncIterators).
    *   Pengalaman implementasi Network Protocol: WebSocket (RFC 6455) dan Server-Sent Events (SSE).
    *   Familiaritas dengan Publish/Subscribe message brokers (khususnya Redis Pub/Sub).

---

## 02. LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1.  **Mendiagnosis dan Mendesain Arsitektur Real-time**: Membedakan use cases, kelebihan, dan limitasi antara GraphQL Subscriptions via WebSockets (`graphql-ws`), GraphQL Subscriptions via SSE (`graphql-sse`), serta Directives Incremental Delivery (`@defer` dan `@stream`).
2.  **Mengimplementasikan Distributed Pub/Sub Execution**: Membangun GraphQL Subscription engine yang scalable secara horizontal menggunakan Redis Pub/Sub dan AsyncIterator abstraction.
3.  **Mengamankan Saluran Komunikasi Real-time**: Mengonfigurasi mekanisme Connection Initialization, Authentication, Context-driven Dynamic Authorization, serta Protocol-level Heartbeat/Ping-Pong.
4.  **Mengoptimalkan dan Mengobservasi Kinerja Network**: Mengimplementasikan load balancing sticky vs non-sticky sessions, connection pooling, mitigasi memory leak, serta metrik pemantauan active subscription.

---

## 03. CONCEPT MAP DIAGRAM

```
+-----------------------------------------------------------------------------+
|                      GRAPHQL REAL-TIME ARCHITECTURE                         |
+-------------------------------------+---------------------------------------+
                                      |
         +----------------------------+----------------------------+
         |                                                         |
         v                                                         v
+------------------+                                      +------------------+
|   PUSH MODELS    |                                      | STREAMING MODELS |
|  (State Changes) |                                      | (Payload Splits) |
+--------+---------+                                      +--------+---------+
         |                                                         |
    +----+-----------------------+                            +----+----+
    |                            |                            |         |
    v                            v                            v         v
+---------------+        +---------------+               +--------+ +---------+
| WebSocket     |        | Server-Sent   |               | @defer | | @stream |
| (Bi-dir)      |        | Events (SSE)  |               | (Slow  | | (List   |
| graphql-ws    |        | graphql-sse   |               | Fields)| | Items)  |
+-------+-------+        +-------+-------+               +----+---+ +----+----+
        |                        |                            |          |
        +------------+-----------+                            +----+-----+
                     |                                             |
                     v                                             v
        +-------------------------+                   +-----------------------+
        | Distributed Pub/Sub     |                   | HTTP/2 or HTTP/3      |
        | Engine (e.g. Redis)     |                   | Multipart Responses   |
        +------------+------------+                   +-----------------------+
                     |
                     v
        +-------------------------+
        | Backpressure & Filtering|
        | (AsyncIterator Engine)  |
        +-------------------------+
```

---

## 04. MENGAPA RELEVAN

Aplikasi monolitik tradisional mengandalkan *short-polling* HTTP untuk mengambil pembaruan data secara periodik. Pola ini membebani infrastruktur dengan ribuan *round-trips* kosong, overhead parsing TLS, dan header HTTP yang berulang.

GraphQL Subscriptions mentransformasi model *request-response* menjadi event-driven paradigm. Server mem-push perubahan data langsung ke klien hanya saat event terjadi. Selain itu, seiring berkembangnya spesifikasi GraphQL Incremental Delivery (`@defer` dan `@stream`), server GraphQL kini dapat memecah payload berukuran besar dan mengirimkannya secara progresif tanpa harus menunggu seluruh pohon data diresolusi. 

Menguasai arsitektur ini krusial untuk membangun sistem enterprise seperti live order tracking, financial tick data, collaborative document editing, dan live-chatting berlatensi rendah dengan konsumsi memori optimal.

---

## 05. ANATOMI KONSEP INTI

### 1. Perbedaan Protokol: WebSockets (`graphql-ws`) vs SSE (`graphql-sse`)

*   **WebSocket Protocol (`graphql-ws`)**:
    *   Menyediakan saluran komunikasi dua arah (*full-duplex*) melalui single TCP socket.
    *   Stateful: Koneksi harus dijaga (*handshake*, *ping/pong*).
    *   Sangat ideal untuk skenario di mana klien sering mengirim mutasi atau sinyal paralel ke server dalam satu koneksi fisik.
*   **Server-Sent Events (`graphql-sse`)**:
    *   Komunikasi satu arah (*half-duplex*, Server-to-Client) di atas protokol HTTP murni (HTTP/1.1 chunked atau HTTP/2/3 streams).
    *   Secara otomatis mengelola *reconnection* bawaan browser, melintasi firewall korporat/proxy lebih andal daripada WebSockets.
    *   Ideal untuk arsitektur yang mengandalkan mutasi standar via HTTP POST dan hanya membutuhkan *downstream event streaming*.

### 2. AsyncIterator Pattern

Engine subscription pada GraphQL bergantung pada protokol ECMAScript `AsyncIterator`. Resolver subscription tidak mengembalikan nilai secara langsung, melainkan mengekspos object dengan method `subscribe` yang mengembalikan iterator:

$$\text{AsyncIterator} = \{ \text{next}(): \text{Promise}\langle\{\text{value: T, done: boolean}\}\rangle \}$$

Ketika event baru dipublikasikan ke message broker, iterator mengekstrak event tersebut, memicu *execution pipeline* untuk me-resolve subtree GraphQL sesuai query klien, lalu mengirimkan payload hasil eksekusi ke klien yang bersangkutan.

### 3. Incremental Delivery: `@defer` vs `@stream`

*   `@defer`: Menginstruksikan GraphQL execution engine untuk menunda eksekusi fragment yang lambat (*computationally expensive* atau *slow I/O*) dan segera mengembalikan data esensial ke klien. Fragment yang lambat dikirim kemudian sebagai HTTP multipart chunks.
*   `@stream`: Diterapkan pada list field. Menginstruksikan engine untuk mengirim elemen list pertama segera setelah tersedia, lalu mengalirkan sisa elemen list secara incremental.

---

## 06. PANDUAN IMPLEMENTASI STEP-BY-STEP

Berikut tahapan membangun enterprise-grade subscription engine:

1.  **Inisialisasi PubSub Adapter Terdistribusi**: Hindari implementasi `PubSub` in-memory pada lingkungan produksi karena tidak mendukung horizontal multi-node scaling. Gunakan driver IORedis dan Redis PubSub.
2.  **Definisikan Schema dengan Subscription Type**: Definisikan tipe event dan payload spesifik di dalam SDL.
3.  **Terapkan Dynamic Subscription Filtering**: Pastikan client hanya menerima data yang mereka miliki hak aksesnya (*tenant isolation* atau *user-level filtering*) menggunakan fungsi filter.
4.  **Integrasikan WebSocket Server dengan HTTP Engine**: Pasangkan `graphql-ws` server ke Node.js HTTP server.
5.  **Pasang Autentikasi pada Connection Handshake**: Ekstrak bearer token pada pesan `connection_init`, validasi token, tolak koneksi tidak sah sebelum alokasi memori berlebih dilakukan.
6.  **Konfigurasi Liveness & Heartbeat**: Jalankan protokol keep-alive ping-pong guna memutus *dead sockets* yang diakibatkan oleh *unclean network drops*.

---

## 07. CONTOH KASUS SEDERHANA

Contoh skenario dasar in-memory subscription untuk tracking status pesanan:

```typescript
import { createSchema, createYoga } from 'graphql-yoga';
import { createServer } from 'http';
import { createPubSub } from 'graphql-yoga';

// Inisialisasi In-Memory PubSub (Hanya untuk Development Lokal/Testing)
const pubSub = createPubSub<{
  orderUpdated: [orderId: string, payload: { id: string; status: string }];
}>();

const typeDefs = /* GraphQL */ `
  type Order {
    id: ID!
    status: String!
  }

  type Query {
    order(id: ID!): Order
  }

  type Mutation {
    updateOrderStatus(id: ID!, status: String!): Order!
  }

  type Subscription {
    orderStatusChanged(orderId: ID!): Order!
  }
`;

const resolvers = {
  Query: {
    order: (_: unknown, { id }: { id: string }) => ({ id, status: 'PENDING' }),
  },
  Mutation: {
    updateOrderStatus: (
      _: unknown,
      { id, status }: { id: string; status: string }
    ) => {
      const payload = { id, status };
      pubSub.publish('orderUpdated', id, payload);
      return payload;
    },
  },
  Subscription: {
    orderStatusChanged: {
      subscribe: (_: unknown, { orderId }: { orderId: string }) =>
        pubSub.subscribe('orderUpdated', orderId),
      resolve: (payload: { id: string; status: string }) => payload,
    },
  },
};

const yoga = createYoga({
  schema: createSchema({ typeDefs, resolvers }),
});

const server = createServer(yoga);
server.listen(4000, () => {
  console.log('Server berjalan pada http://localhost:4000/graphql');
});
```

---

## 08. IMPLEMENTASI PRODUCTION-GRADE LENGKAP KODE

Berikut adalah implementasi enterprise-grade subscription server menggunakan `graphql-ws`, Fastify, IORedis, dan Redis PubSub, dilengkapi handling connection lifecycle, auth, heartbeat, dan graceful shutdown.

### 1. Struktur File
```text
├── package.json
├── tsconfig.json
└── src
    ├── auth.ts
    ├── index.ts
    ├── pubsub.ts
    └── schema.ts
```

### 2. `package.json`
```json
{
  "name": "enterprise-graphql-subscriptions",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "build": "tsc",
    "start": "node dist/index.js",
    "dev": "ts-node src/index.ts"
  },
  "dependencies": {
    "@fastify/websocket": "^10.0.1",
    "@graphql-tools/schema": "^10.0.4",
    "fastify": "^4.28.1",
    "graphql": "^16.9.0",
    "graphql-ws": "^5.16.0",
    "ioredis": "^5.4.1",
    "jsonwebtoken": "^9.0.2"
  },
  "devDependencies": {
    "@types/jsonwebtoken": "^9.0.6",
    "@types/node": "^20.14.9",
    "@types/ws": "^8.5.10",
    "ts-node": "^10.9.2",
    "typescript": "^5.5.2"
  }
}
```

### 3. `src/auth.ts`
```typescript
import jwt from 'jsonwebtoken';

const JWT_SECRET = process.env.JWT_SECRET || 'super-secret-key-enterprise-grade';

export interface UserSession {
  userId: string;
  roles: string[];
  tenantId: string;
}

export function verifyToken(token: string): UserSession {
  try {
    const cleanedToken = token.startsWith('Bearer ') ? token.slice(7) : token;
    const decoded = jwt.verify(cleanedToken, JWT_SECRET) as UserSession;
    return decoded;
  } catch {
    throw new Error('UNAUTHORIZED_INVALID_TOKEN');
  }
}
```

### 4. `src/pubsub.ts`
```typescript
import Redis from 'ioredis';

const REDIS_URL = process.env.REDIS_URL || 'redis://127.0.0.1:6379';

export class DistributedPubSub {
  private publisher: Redis;
  private subscriber: Redis;
  private subscriptions: Map<string, Set<(data: string) => void>>;

  constructor() {
    this.publisher = new Redis(REDIS_URL, { maxRetriesPerRequest: null });
    this.subscriber = new Redis(REDIS_URL, { maxRetriesPerRequest: null });
    this.subscriptions = new Map();

    this.subscriber.on('message', (channel, message) => {
      const listeners = this.subscriptions.get(channel);
      if (listeners) {
        listeners.forEach((listener) => listener(message));
      }
    });
  }

  public async publish(topic: string, payload: unknown): Promise<void> {
    await this.publisher.publish(topic, JSON.stringify(payload));
  }

  public asyncSubscribe<T>(topic: string): AsyncIterableIterator<T> {
    const queue: T[] = [];
    let resolveNext: ((value: IteratorResult<T>) => void) | null = null;

    const listener = (raw: string) => {
      const parsed: T = JSON.parse(raw);
      if (resolveNext) {
        const resolve = resolveNext;
        resolveNext = null;
        resolve({ value: parsed, done: false });
      } else {
        queue.push(parsed);
      }
    };

    if (!this.subscriptions.has(topic)) {
      this.subscriptions.set(topic, new Set());
      this.subscriber.subscribe(topic).catch((err) => {
        console.error(`Gagal subscribe ke redis topic ${topic}:`, err);
      });
    }
    this.subscriptions.get(topic)!.add(listener);

    const self = this;

    return {
      [Symbol.asyncIterator]() {
        return this;
      },
      async next(): Promise<IteratorResult<T>> {
        if (queue.length > 0) {
          return { value: queue.shift()!, done: false };
        }
        return new Promise<IteratorResult<T>>((resolve) => {
          resolveNext = resolve;
        });
      },
      async return(): Promise<IteratorResult<T>> {
        const listeners = self.subscriptions.get(topic);
        if (listeners) {
          listeners.delete(listener);
          if (listeners.size === 0) {
            self.subscriptions.delete(topic);
            await self.subscriber.unsubscribe(topic);
          }
        }
        return { value: undefined as unknown as T, done: true };
      },
      async throw(err?: unknown): Promise<IteratorResult<T>> {
        const listeners = self.subscriptions.get(topic);
        if (listeners) {
          listeners.delete(listener);
          if (listeners.size === 0) {
            self.subscriptions.delete(topic);
            await self.subscriber.unsubscribe(topic);
          }
        }
        return Promise.reject(err);
      },
    };
  }

  public async close(): Promise<void> {
    await this.publisher.quit();
    await this.subscriber.quit();
  }
}

export const pubsub = new DistributedPubSub();
```

### 5. `src/schema.ts`
```typescript
import { makeExecutableSchema } from '@graphql-tools/schema';
import { pubsub } from './pubsub';
import { UserSession } from './auth';

export interface GraphQLContext {
  user?: UserSession;
}

const typeDefs = /* GraphQL */ `
  type FinancialTelemetry {
    ticker: String!
    price: Float!
    volume: Int!
    timestamp: String!
  }

  type Mutation {
    publishPrice(ticker: String!, price: Float!, volume: Int!): FinancialTelemetry!
  }

  type Query {
    healthCheck: String!
  }

  type Subscription {
    tickerUpdates(ticker: String!): FinancialTelemetry!
  }
`;

const resolvers = {
  Query: {
    healthCheck: () => 'OK',
  },
  Mutation: {
    publishPrice: async (
      _: unknown,
      { ticker, price, volume }: { ticker: string; price: number; volume: number },
      context: GraphQLContext
    ) => {
      if (!context.user) {
        throw new Error('UNAUTHENTICATED');
      }

      const telemetry = {
        ticker,
        price,
        volume,
        timestamp: new Date().toISOString(),
      };

      await pubsub.publish(`MARKET_TICKER:${ticker}`, telemetry);
      return telemetry;
    },
  },
  Subscription: {
    tickerUpdates: {
      subscribe: (
        _: unknown,
        { ticker }: { ticker: string },
        context: GraphQLContext
      ) => {
        if (!context.user) {
          throw new Error('FORBIDDEN_SUBSCRIPTION_ACCESS');
        }
        return pubsub.asyncSubscribe(`MARKET_TICKER:${ticker}`);
      },
      resolve: (payload: unknown) => payload,
    },
  },
};

export const schema = makeExecutableSchema({ typeDefs, resolvers });
```

### 6. `src/index.ts`
```typescript
import fastify from 'fastify';
import fastifyWebsocket from '@fastify/websocket';
import { makeHandler } from 'graphql-ws/lib/use/@fastify/websocket';
import { execute, subscribe } from 'graphql';
import { schema, GraphQLContext } from './schema';
import { verifyToken } from './auth';
import { pubsub } from './pubsub';

const app = fastify({ logger: true });

async function bootstrap() {
  await app.register(fastifyWebsocket, {
    options: {
      maxPayload: 1024 * 64, // Proteksi DDoS: 64 KB Max payload
    },
  });

  app.get(
    '/graphql',
    { websocket: true },
    makeHandler<GraphQLContext>({
      schema,
      execute,
      subscribe,
      onConnect: async (ctx) => {
        const authHeader = ctx.connectionParams?.authorization as string | undefined;
        if (!authHeader) {
          // Reject koneksi jika token tidak tersedia saat inisialisasi
          return false;
        }

        try {
          const user = verifyToken(authHeader);
          ctx.extra.user = user;
          return true;
        } catch {
          return false;
        }
      },
      onSubscribe: async (ctx, _id, params) => {
        // Dynamic authorization check per individual subscription
        const user = ctx.extra.user;
        if (!user) {
          throw new Error('Access Denied');
        }
        return {
          schema,
          execute,
          subscribe,
          contextValue: { user },
          ...params,
        };
      },
    })
  );

  const PORT = Number(process.env.PORT) || 4000;
  const HOST = '0.0.0.0';

  await app.listen({ port: PORT, host: HOST });
  console.log(`Server GraphQL Subscription berjalan di ws://${HOST}:${PORT}/graphql`);

  const gracefulShutdown = async () => {
    console.log('Mematikan server dan membersihkan resource...');
    await app.close();
    await pubsub.close();
    process.exit(0);
  };

  process.on('SIGINT', gracefulShutdown);
  process.on('SIGTERM', gracefulShutdown);
}

bootstrap().catch((err) => {
  console.error('Fatal initialization error:', err);
  process.exit(1);
});
```

---

## 09. DIAGRAM ALUR KERJA

Alur eksekusi pesan WebSocket pada protokol `graphql-ws` terdistribusi:

```
Client                      Server (Fastify/Node.js)             Redis Cluster
  |                                     |                              |
  | 1. HTTP Upgrade (WS Handshake)      |                              |
  |------------------------------------>|                              |
  | 2. 101 Switching Protocols          |                              |
  |<------------------------------------|                              |
  |                                     |                              |
  | 3. ws: "connection_init" (JWT Token)|                              |
  |------------------------------------>| [Verify JWT Signature]       |
  | 4. ws: "connection_ack"             |                              |
  |<------------------------------------|                              |
  |                                     |                              |
  | 5. ws: "subscribe" (Query SDL)      |                              |
  |------------------------------------>| [Register AsyncIterator]     |
  |                                     | 6. SUBSCRIBE "TICKER:BTC"   |
  |                                     |----------------------------->|
  |                                     |                              |
  |                                     |      [Mutation on Pod B]     |
  |                                     | 7. PUBLISH "TICKER:BTC" data |
  |                                     |<-----------------------------|
  |                                     |                              |
  |                                     | [Execute GraphQL Subtree]    |
  | 8. ws: "next" (GraphQL Payload)     |                              |
  |<------------------------------------|                              |
  |                                     |                              |
  | 9. ws: "complete" (Client Unsub)    |                              |
  |------------------------------------>| 10. UNSUBSCRIBE "TICKER:BTC" |
  |                                     |----------------------------->|
  v                                     v                              v
```

---

## 10. ANALISIS TRADE-OFFS

| Karakteristik | WebSockets (`graphql-ws`) | Server-Sent Events (`graphql-sse`) | Polling / Long-Polling |
| :--- | :--- | :--- | :--- |
| **Arah Komunikasi** | Full-Duplex (Dua arah) | Simplex (Server-ke-Klien) | Half-Duplex (Klien-ke-Server) |
| **Beban Protokol (Overhead)** | Sangat Rendah pasca-handshake | Rendah (HTTP chunked) | Sangat Tinggi (Header berulang) |
| **Handling Firewall/Proxy** | Sering diblokir / timeout oleh corporate proxy lama | Sangat baik (HTTP murni, port 80/443) | Sangat Baik (Native HTTP) |
| **Multiplexing** | Alami di atas 1 koneksi socket | Butuh HTTP/2+ untuk multiplexing | Tidak ada native multiplexing |
| **Kebutuhan Sticky Session** | Sangat Disarankan (kecuali ada distributed gateway) | Tidak mutlak jika stateless HTTP/2 | Tidak perlu sama sekali |
| **Konsumsi Memori Server** | Tinggi per TCP connection pool | Rendah-Sedang | Sangat Rendah (Stateless) |

---

## 11. BEST PRACTICES & ANTIPATTERNS

### Best Practices
1. **Lakukan Filter di Hulu (Message Broker)**: Jangan broadcast seluruh data mutasi ke Node.js dan mengandalkan in-memory filter jika trafik tinggi. Gunakan granular Redis channel topics (contoh: `USER:1234:NOTIFICATIONS`).
2. **Definisikan Time-to-Live (TTL) Connection**: Force-refresh koneksi WebSocket lama untuk memvalidasi rotasi kredensial auth dan membersihkan koneksi zombie.
3. **Optimalkan Buffer Size**: Pasang batas penampungan payload antrean AsyncIterator untuk mencegah leak memori saat subscriber lambat (*Slow Consumer Syndrome*).

### Antipatterns
1. **In-Memory PubSub di Production**: Menggunakan `PubSub` lokal bawaan memory (`graphql-subscriptions`) di cluster Kubernetes. Event yang dipublish di Pod A tidak akan pernah sampai ke klien yang terkoneksi di Pod B.
2. **Heavy Computation di dalam Subscription Resolver**: Melakukan query database relasional berat di dalam field subscription berfrekuensi tinggi (misal: tick per milidetik). Selesaikan komputasi sebelum `publish()`.
3. **Mengabaikan Payload Size Limit**: Membiarkan client mengirim pesan query GraphQL sebesar puluhan Megabyte melalui frame WebSocket, menyebabkan CPU blocking pada event-loop thread.

---

## 12. SECURITY HARDENING

1.  **Connection Initialization Auth**: Jangan biarkan socket terbuka tanpa otentikasi. Jika pesan `connection_init` tidak mengandung valid credentials dalam kurun waktu $N$ detik (misal: 3 detik), putus koneksi secara sepihak dengan code `4408: Connection Initialization Timeout`.
2.  **Origin Header Verification**: Validasi header `Origin` saat HTTP Upgrade stage untuk mencegah *Cross-Site WebSocket Hijacking (CSWSH)*.
3.  **Subscription Depth Limiting & Cost Analysis**: Query Subscription harus dianalisis menggunakan library analisis kompleksitas query (`graphql-cost-analysis`) sebelum dieksekusi, guna mencegah client mendaftarkan query dengan nesting tanpa batas.
4.  **Rate Limiting on Subscriptions**: Batasi jumlah channel subscription aktif maksimum per akun/IP (misalnya maksimal 20 concurrent subscriptions per user).

---

## 13. OBSERVABILITAS & DEBUGGING

*   **Metrik Kunci (Prometheus Instrumentation)**:
    *   `graphql_active_connections`: Total koneksi WebSocket yang terbuka saat ini.
    *   `graphql_active_subscriptions_total`: Total pohon subscription aktif yang sedang me-listen event.
    *   `graphql_subscription_event_duration_seconds`: Waktu yang dibutuhkan dari saat broker menerima event hingga payload terkirim ke network socket client.
    *   `graphql_subscription_errors_total`: Counter error eksekusi subscription dikelompokkan berdasarkan Resolver error vs Transport error.
*   **Structured Logging**: Pastikan log mencatat lifecycle ID: `connectionId`, `subscriptionId`, `userId`, dan `topic`.
*   **Debugging Tooling**: Gunakan tools command line seperti `wscat` atau GraphQL GUI (Postman / Apollo Studio) yang mendukung protokol `graphql-ws` untuk menginspeksi transport frames secara mentah:
    ```bash
    wscat -c ws://localhost:4000/graphql -s graphql-transport-ws
    # Kirim: {"type":"connection_init","payload":{"authorization":"Bearer TOKEN"}}
    # Kirim: {"id":"1","type":"subscribe","payload":{"query":"subscription { tickerUpdates(ticker: \"BTC\") { price } }"}}
    ```

---

## 14. BENCHMARKING & PERFORMANCE

Dalam benchmarking performa real-time GraphQL:

1.  **Benchmarking Metrics**:
    *   **Max Concurrent Connections (Conns Limit)**: Ukur titik batas memori (RAM usage) ketika server menampung 50.000 idle WebSockets.
    *   **Broadcast Latency**: Waktu tempuh dari satu `publish()` hingga $N$ subscribers menerima data (Target: $< 10\text{ms}$ untuk 1.000 subscriber serentak).
2.  **Kernel Tuning (Linux OS level)**:
    Untuk menampung puluhan ribu koneksi persistent, atur file descriptors dan TCP settings:
    ```bash
    sysctl -w fs.file-max=2097152
    sysctl -w net.ipv4.ip_local_port_range="1024 65535"
    sysctl -w net.core.somaxconn=65535
    ulimit -n 1048576
    ```
3.  **Memory Footprint per Connection**: Pada Node.js `graphql-ws`, estimasi footprint memori stabil per idle-socket adalah sekitar $2\text{KB} - 8\text{KB}$.

---

## 15. HANDS-ON LAB MINI-PROJECT

### Judul
Membangun Live Collaborative Workspace & Delivery Pipeline dengan Redis Backpressure.

### Skenario
Anda diminta membuat pipeline GraphQL Subscription yang menyiarkan update dokumen kolaboratif (`DocumentPatch`) secara real-time antar desainer grafis.

### Instruksi Tugas
1.  Setup server dengan `fastify`, `@fastify/websocket`, `graphql-ws`, dan `ioredis`.
2.  Implementasikan mutation `applyPatch(documentId: ID!, patch: String!): Boolean!`.
3.  Implementasikan subscription `onDocumentModified(documentId: ID!): DocumentPatch!`.
4.  Lakukan otentikasi menggunakan header bearer token pada handshake awal.
5.  Pastikan subscriber hanya menerima update untuk `documentId` yang ditentukan, dan validasi bahwa user memiliki *read access* ke ID tersebut.

### Verifikasi Hasil
Gunakan dua instance `wscat` terminal terpisah untuk mensimulasikan dua klien berbeda pada document ID yang sama, lalu kirimkan patch via cURL mutation HTTP untuk melihat data tersinkronisasi secara real-time.

---

## 16. AUTOMATED TESTING & VERIFICATION

Automated testing untuk GraphQL Subscriptions memerlukan client testing yang mampu menangani koneksi WebSocket secara asynchronous.

### Script Test (`test/subscription.test.ts`)
```typescript
import { createClient } from 'graphql-ws';
import WebSocket from 'ws';
import jwt from 'jsonwebtoken';

const JWT_SECRET = 'super-secret-key-enterprise-grade';

describe('GraphQL Real-time Subscriptions Integration Test', () => {
  let client: ReturnType<typeof createClient>;

  beforeAll(() => {
    const token = jwt.sign(
      { userId: 'user-001', tenantId: 'tenant-abc', roles: ['TRADER'] },
      JWT_SECRET
    );

    client = createClient({
      url: 'ws://localhost:4000/graphql',
      webSocketImpl: WebSocket,
      connectionParams: {
        authorization: `Bearer ${token}`,
      },
    });
  });

  afterAll(async () => {
    await client.dispose();
  });

  it('Harus berhasil menerima event payload saat mutasi dipicu', (done) => {
    const query = /* GraphQL */ `
      subscription {
        tickerUpdates(ticker: "ETH") {
          ticker
          price
          volume
        }
      }
    `;

    const unsubscribe = client.subscribe(
      { query },
      {
        next: (data) => {
          try {
            expect(data).toBeDefined();
            expect(data.data?.tickerUpdates).toEqual(
              expect.objectContaining({
                ticker: 'ETH',
                price: 3500.5,
                volume: 100,
              })
            );
            unsubscribe();
            done();
          } catch (err) {
            done(err);
          }
        },
        error: (err) => done(err),
        complete: () => {},
      }
    );

    // Berikan jeda 200ms untuk memastikan subscription aktif sebelum trigger HTTP mutation
    setTimeout(async () => {
      await fetch('http://localhost:4000/graphql', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${jwt.sign(
            { userId: 'admin', tenantId: 'tenant-abc', roles: ['ADMIN'] },
            JWT_SECRET
          )}`,
        },
        body: JSON.stringify({
          query: `mutation { publishPrice(ticker: "ETH", price: 3500.50, volume: 100) { ticker } }`,
        }),
      });
    }, 200);
  });
});
```

---

## 17. TROUBLESHOOTING GUIDE

| Gejala Masalah | Potensi Root Cause | Langkah Remediasi |
| :--- | :--- | :--- |
| **Koneksi terputus dengan error code 4401** | Token JWT kedaluwarsa atau invalid pada `connectionParams`. | Refresh token pada client layer sebelum memanggil `createClient()` / inisialisasi WebSocket. |
| **Pesan mutasi berhasil tapi event tidak diterima subscriber** | Pod server terhubung ke Redis Topic yang salah atau mismatch pattern string topic. | Validasi channel naming convention; pastikan publisher dan subscriber menggunakan identical topic identifier. |
| **WebSocket sering terputus setiap 60 detik tepat** | AWS ALB / NGINX Ingress Controller proxy menembus idle timeout window. | Konfigurasi Ping/Pong heartbeat interval pada `graphql-ws` setiap 20-30 detik untuk menjaga koneksi tetap aktif. |
| **Server out-of-memory (OOM Crash)** | Memory leak dari unclosed `AsyncIterator` saat klien disconnect tanpa mengirim pesan `complete`. | Pastikan implementasi `asyncIterator.return()` melepaskan event listener Redis dengan benar. |

---

## 18. CHECKLIST PRODUKSI

- [ ] Menggunakan protokol standar modern `graphql-ws` (bukan legacy `subscriptions-transport-ws`).
- [ ] State PubSub dikelola terdistribusi menggunakan Redis / NATS cluster (Bukan In-Memory).
- [ ] Token otentikasi diverifikasi pada fase `onConnect` connection handshake.
- [ ] Dynamic authorization diterapkan pada fase `onSubscribe` untuk setiap field subscription.
- [ ] Frame rate-limiting dan Max Payload Size ($<64\text{KB}$) terpasang untuk mencegah denial-of-service.
- [ ] Reverse proxy (NGINX/Envoy/ALB) telah dikonfigurasi dengan explicit WebSocket Upgrade support dan read/write timeouts $> 3600\text{s}$.
- [ ] Ping/Pong Heartbeat aktif pada interval periodik (15 - 30 detik).
- [ ] Graceful shutdown handler terdaftar untuk menutup sockets dan koneksi broker saat proses terminasi (`SIGTERM`).
- [ ] Cleanup logic (`return()` callback) diuji secara menyeluruh untuk mencegah memory leak listener.

---

## 19. RINGKASAN EKSEKUTIF

Arsitektur GraphQL Real-time memfasilitasi komunikasi reaktif berkinerja tinggi antara server dan klien. Keberhasilan implementasi skala enterprise ditentukan oleh:

1.  **Pemilihan Transport yang Tepat**: Pilih WebSockets (`graphql-ws`) untuk komunikasi stateful dua arah bertrafik tinggi, atau SSE (`graphql-sse`) untuk kebutuhan event-streaming searah yang ramah firewall.
2.  **State Management Terdesentralisasi**: Skalabilitas horizontal diwujudkan dengan memisahkan execution layer GraphQL dari storage message event menggunakan Pub/Sub engine eksternal seperti Redis.
3.  **Siklus Hidup Terisolasi**: Autentikasi dan otorisasi harus diverifikasi di level transport handshake dan subscription resolution secara independen untuk menjamin keamanan mutlak data enterprise.

---

## 20. REFERENSI & BACAAN LANJUTAN

1.  **GraphQL Over WebSocket Protocol Specification**: [https://github.com/enisdenjo/graphql-ws/blob/master/PROTOCOL.md](https://github.com/enisdenjo/graphql-ws/blob/master/PROTOCOL.md)
2.  **GraphQL Incremental Delivery Specification (`@defer` & `@stream`)**: [https://github.com/graphql/graphql-spec/blob/main/rfcs/DeferStream.md](https://github.com/graphql/graphql-spec/blob/main/rfcs/DeferStream.md)
3.  **GraphQL Server-Sent Events (SSE) Protocol**: [https://github.com/enisdenjo/graphql-sse/blob/