# BAB 05: Real-time Architecture, Subscriptions & Streaming
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Merancang dan mengimplementasikan arsitektur real-time GraphQL skala enterprise menggunakan protokol modern `graphql-ws` dan Server-Sent Events (SSE).
- Menerapkan direktif Incremental Delivery (`@defer` dan `@stream`) untuk memangkas Time to First Byte (TTFB) dan Time to Interactive (TTI) pada payload analitik/relasional besar.
- Mengintegrasikan broker pesan terdistribusi (Redis PubSub / NATS / Apache Kafka) sebagai transport layer abstraksi eksternal guna mendukung skalabilitas horizontal stateless engine.
- Mengelola siklus hidup koneksi WebSocket (Connection Lifecycle), autentikasi tingkat koneksi vs. payload, heartbeat/ping-pong, mitigasi *dead connection*, serta strategi *backpressure*.
- Menganalisis *trade-off* operasional, memory footprint, mitigasi C100K/C1000K, serta mengamankan server dari serangan resource exhaustion melalui WebSocket leak.

---

### 2. Prerequisite
- **GraphQL Fundamentals**: Pemahaman mendalam terkait Schema Definition Language (SDL), Execution Context, Resolvers, Field Execution, dan AST Parsing.
- **Networking & Transport Layer**: Pemahaman mendalam tentang TCP, WebSocket RFC 6455, HTTP/1.1 chunked transfer encoding, HTTP/2 multiplexing, dan Server-Sent Events (EventSource).
- **Node.js Internals**: Event loop, Stream API (Readable/Writable/Transform), Buffer allocation, dan penanganan asynchronous generator (`for await...of`).
- **Distributed Systems**: Konsep Message Broker, Publish-Subscribe Pattern, At-Least-Once Delivery, Fan-out, dan Partitioning.

---

### 3. Concept & Internal Architecture

#### 3.1. Evolusi Transport: `subscriptions-transport-ws` vs `graphql-ws` vs SSE
Secara historis, ekosistem GraphQL menggunakan protokol `subscriptions-transport-ws` (Apollo). Namun, protokol ini telah dinyatakan **deprecated** akibat kerentanan *zombie connection*, inkonsistensi penanganan error, dan ketiadaan spesifikasi formal. Standar de-facto modern adalah library `graphql-ws` yang mengimplementasikan spesifikasi resmi *GraphQL over WebSocket Protocol*.

| Parameter Evaluasi | `subscriptions-transport-ws` (Legacy) | `graphql-ws` (Modern Standard) | Server-Sent Events (SSE / HTTP/2) |
| :--- | :--- | :--- | :--- |
| **Spesifikasi Formal** | Ad-hoc (Apollo legacy) | IETF/GraphQL Foundation spec | W3C Server-Sent Events |
| **Protokol Sub-jaringan** | `graphql-ws` (nama bentrok) | `graphql-transport-ws` | HTTP/1.1, HTTP/2, HTTP/3 |
| **Keep-Alive Mechanism** | Client-driven (`ka` message) | Bidirectional Ping/Pong native | Native HTTP/2 Ping atau SSE comment (`:ping`) |
| **Bi-directional Capability** | Ya (Full Duplex) | Ya (Full Duplex) | Tidak (Server-to-Client saja) |
| **Firewall & Proxy Traversal** | Sering bermasalah pada Corporate WAF | Kadang di-block oleh proxy kaku | Sangat bersahabat dengan WAF/CDN |
| **Multiplexing** | Manual via protocol frame | Manual via protocol frame | Native via HTTP/2 Multiplexing streams |

#### 3.2. Incremental Delivery: `@defer` dan `@stream`
Alih-alih membuka koneksi persistent berbiaya tinggi melalui WebSocket, GraphQL Working Group memperkenalkan RFC Incremental Delivery melalui HTTP multipart chunking:
- **`@defer`**: Ditujukan untuk field atau fragment yang membutuhkan komputasi lambat (eksternal API, query database kompleks). Engine mengeksekusi data utama dan mengirim respons awal (Initial Payload), kemudian mengirimkan chunk lanjutan (Deferred Payload) melalui format respons `multipart/mixed; boundary="-"`.
- **`@stream`**: Ditujukan untuk list data besar. Alih-alih menunggu seluruh array di-resolve (misal: 10.000 row item), engine mengirimkan elemen pertama secepat mungkin, diikuti oleh elemen berikutnya secara berurutan dalam stream chunk.

```
HTTP/1.1 200 OK
Content-Type: multipart/mixed; boundary="-"

---
Content-Type: application/json; charset=utf-8

{"data":{"user":{"id":"usr_01","name":"Alice"}},"hasNext":true}
---
Content-Type: application/json; charset=utf-8

{"data":{"profileFeed":[{"id":"f_1","text":"Hello World"}]},"path":["user"],"hasNext":false}
-----
```

#### 3.3. Arsitektur Horisontal PubSub & Backpressure
Saat sistem diskalakan ke banyak instance di balik Load Balancer (AWS ALB / Nginx), klien A yang terhubung ke Instance 1 tidak akan menerima event mutasi yang dipicu klien B pada Instance 2 jika hanya menggunakan `EventEmitter` in-memory.

Solusinya adalah arsitektur decoupled transport:
```
           +----------------+
           | Clients (WS)   |
           +---+--------+---+
               |        |
        +------v-+    +-v------+
        | Node 1 |    | Node 2 |  (Stateless GraphQL Engines)
        +------+--+  +--+------+
               |        |
         +-----v--------v-----+
         | Redis PubSub /     |  (Distributed Event Spine)
         | NATS Core / Kafka  |
         +--------------------+
```

- **Backpressure Problem**: Ketika subscriber memproses data lebih lambat dibanding laju publishing dari broker, antrean memori internal (WebSocket send buffer) akan membengkak, memicu V8 Engine crash karena `OutOfMemory: JavaScript heap out of memory`.
- **Mitigasi Backpressure**: Menggunakan buffer size thresholding, dropped frame strategy (untuk data non-kritis seperti ticker pasar modal), atau beralih ke stream berbasis Pull-stream/Reactive Streams spec.

---

### 4. Why & What

- **Mengapa tidak cukup melakukan Polling?**  
  Polling menghasilkan *traffic waste* hingga 98% (HTTP roundtrip, TLS handshake overhead, parsing headers), serta menciptakan latensi diskrit ($t/2$ average latency delay). Subscriptions dan SSE memberikan zero-idle payload transmission begitu event terjadi.
- **Apa itu GraphQL Subscription Engine?**  
  Subscription engine bukan sekadar WebSocket server biasa; ia adalah kombinasi dari:
  1. *Connection Manager*: Melacak status koneksi TCP/TLS dan context handshake.
  2. *Operation Registry*: Memetakan `Connection ID` -> `Subscription Operation ID` -> `AST Document` -> `Execution Filter Variables`.
  3. *Resolver Pipeline Execution*: Saat event masuk dari broker, engine memicu execution pipeline GraphQL secara independen per subscriber, memastikan field projection dan directive authorization dieksekusi unik untuk setiap subscriber.

---

### 5. How: Workflow Detail

```
Client                  GraphQL Gateway (graphql-ws)         Redis Cluster
  |                                   |                            |
  |--- 1. HTTP Upgrade (WS) --------->|                            |
  |<-- 2. 101 Switching Protocols ----|                            |
  |                                   |                            |
  |--- 3. connection_init (Auth) ---->|                            |
  |    (Validasi JWT di Connection)   |-- (Verify Token Context)   |
  |<-- 4. connection_ack -------------|                            |
  |                                   |                            |
  |--- 5. subscribe (Query + Var) --->|                            |
  |                                   |--- 6. Redis SUBSCRIBE ---->|
  |                                   |<-- 7. OK ------------------|
  |                                   |                            |
  |                                   |<-- 8. PUBLISH (New Order) -|
  |                                   |                            |
  |                                   |-- 9. Run GraphQL Engine    |
  |                                   |   (Filter, Project Fields, |
  |                                   |    Run Field Resolvers)    |
  |                                   |                            |
  |<-- 10. next (GraphQL Payload) ----|                            |
  |                                   |                            |
  |--- 11. complete ----------------->|                            |
  |                                   |--- 12. Redis UNSUBSCRIBE ->|
```

1. **Transport Handshake**: Inisiasi WebSocket via HTTP `Upgrade: websocket`.
2. **Protocol Init**: Klien mengirim frame payload JSON `{"type": "connection_init", "payload": {"Authorization": "Bearer ..."}}`.
3. **Connection-level Context Factory**: Server memverifikasi token. Jika invalid, socket ditutup dengan code `4401 (Unauthorized)` atau `4403 (Forbidden)`.
4. **Subscription Registration**: Klien mengirim frame `subscribe` berisi unique operation `id` dan GraphQL query. Server mengkompilasi DocumentNode AST, memvalidasi schema, dan mendaftarkan listener ke internal event loop / broker.
5. **Broker Event Fan-out**: Data masuk dari broker, GraphQL engine mengeksekusi root subscription resolver: `subscribe` mengembalikan `AsyncIterator`, dan resolver `resolve` memformat output sesuai query.
6. **Frame Dispatching**: Klien menerima frame `next` yang berisi data GraphQL standar.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sistem Pengantaran Dokumen Rahasia
Bayangkan sebuah menara kantor pusat (Server) dan kurir (Client).
- **REST/HTTP Polling**: Kurir datang setiap 5 menit ke lobi menanyakan: *"Ada dokumen baru untuk saya?"*. 99% jawabannya *"Belum ada"*, membuang waktu perjalanan dan tenaga kurir.
- **SSE (Server-Sent Events)**: Kantor memasang tabung pneumatik satu arah ke meja kurir. Kantor bisa menembakkan tabung kapsul dokumen kapan pun ada berkas siap, tapi kurir tidak bisa membalas lewat tabung itu.
- **GraphQL Subscription (WebSocket)**: Kurir membuka jalur walkie-talkie dua arah yang terenkripsi langsung ke kantor. Kantor memberitahu update dokumen, dan kurir bisa mengonfirmasi, meminta tipe dokumen lain, atau menutup jalur secara instan.

```
+-----------------------------------------------------------------------------------+
|                        GRAPHQL SUBSCRIPTION ENGINE INTERNALS                     |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|  [ WebSocket Client Pool ]                                                        |
|         │                                                                         |
|         ├── Socket 1 (Conn A) ─── Auth Context: { userId: "u1", role: "ADMIN" }   |
|         └── Socket 2 (Conn B) ─── Auth Context: { userId: "u2", role: "USER" }    |
|                                                                                   |
|  [ GraphQL WS Protocol Handler (graphql-ws) ]                                     |
|         │                                                                         |
|         ├── Operation Map:                                                        |
|         │     ├── Conn A:Op 101 -> query { liveTrades { price volume } }          |
|         │     └── Conn B:Op 999 -> query { liveTrades { price } }                 |
|         │                                                                         |
|  [ Subscription Pipeline: AsyncIterator + Field Resolver Projection ]             |
|         │                                                                         |
|         ▲ Filter (Redis Payload) -> Execute Operation AST -> JSON Payload         |
|         │                                                                         |
|  [ Redis PubSub / Message Bus Broker ]                                            |
|         ▲                                                                         |
|         └── CHANNEL: "MARKET_EVENTS:BTCUSDT"                                      |
+-----------------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Vanilla Node.js + `graphql-ws` + Native Async Generator

Implementasi modular minimalis menggunakan runtime Node.js modern, validasi schema, dan AsyncIterator tanpa dependensi framework berat.

```typescript
// simple-subscription.ts
import { createServer } from 'http';
import { parse, validate, execute, subscribe, GraphQLSchema, GraphQLObjectType, GraphQLString, GraphQLNonNull } from 'graphql';
import { WebSocketServer } from 'ws';
import { useServer } from 'graphql-ws/lib/use/ws';

// 1. Definisikan State & Async Generator
async function* systemHeartbeatGenerator() {
  while (true) {
    await new Promise((resolve) => setTimeout(resolve, 1000));
    yield { systemHeartbeat: new Date().toISOString() };
  }
}

// 2. Skema GraphQL Minimal
const schema = new GraphQLSchema({
  query: new GraphQLObjectType({
    name: 'Query',
    fields: {
      ping: { type: GraphQLString, resolve: () => 'pong' },
    },
  }),
  subscription: new GraphQLObjectType({
    name: 'Subscription',
    fields: {
      systemHeartbeat: {
        type: new GraphQLNonNull(GraphQLString),
        subscribe: () => systemHeartbeatGenerator(),
        resolve: (payload) => payload.systemHeartbeat,
      },
    },
  }),
});

// 3. Setup Native HTTP & WS Server
const server = createServer();
const wsServer = new WebSocketServer({ server, path: '/graphql' });

useServer(
  {
    schema,
    execute,
    subscribe,
    onConnect: async (ctx) => {
      console.log(`[WS] Client Connected. Extra:`, ctx.extra.request.headers['user-agent']);
      return true;
    },
    onDisconnect: () => {
      console.log('[WS] Client Disconnected.');
    },
  },
  wsServer
);

server.listen(4000, () => {
  console.log(`[HTTP/WS] Server online di http://localhost:4000/graphql`);
});
```

#### 7.2. Practical Example: Enterprise Distributed Subscription Engine dengan Redis & Auth Handshake

Struktur arsitektur produksi menggunakan Fastify/Mercurius atau `@graphql-yoga` dengan `graphql-ws`, `ioredis`, validasi JWT pada handshake, *ping/pong keepalive*, dan isolasi *channel multiplexing*.

```typescript
// src/server.ts
import { createServer } from 'http';
import { WebSocketServer } from 'ws';
import { makeExecutableSchema } from '@graphql-tools/schema';
import { useServer } from 'graphql-ws/lib/use/ws';
import Redis from 'ioredis';
import { jwtVerify } from 'jose';

// --- CONFIG & CONSTANTS ---
const REDIS_URL = process.env.REDIS_URL || 'redis://127.0.0.1:6379';
const JWT_SECRET = new TextEncoder().encode(process.env.JWT_SECRET || 'secret-enterprise-key-123456');

// Redis Connections: Producer & Consumer harus dipisah secara resource thread
const redisPublisher = new Redis(REDIS_URL);
const redisSubscriber = new Redis(REDIS_URL);

// --- TYPE DEFINITIONS ---
const typeDefs = /* GraphQL */ `
  type Order {
    id: ID!
    symbol: String!
    price: Float!
    volume: Float!
    timestamp: String!
    executedBy: String!
  }

  type Query {
    healthCheck: String!
  }

  type Mutation {
    publishOrder(symbol: String!, price: Float!, volume: Float!): Order!
  }

  type Subscription {
    orderPlaced(symbol: String!): Order!
  }
`;

// --- AUTHENTICATION INTERFACES ---
interface UserSession {
  userId: string;
  role: string;
}

interface ConnectionContextExtra {
  user?: UserSession;
}

// --- REDIS PUB/SUB ABSTRACT ADAPTER ---
class RedisSubscriptionHub {
  private listeners: Map<string, Set<(data: any) => void>> = new Map();

  constructor(private sub: Redis) {
    this.sub.on('message', (channel, message) => {
      if (this.listeners.has(channel)) {
        try {
          const parsed = JSON.parse(message);
          this.listeners.get(channel)!.forEach((callback) => callback(parsed));
        } catch (err) {
          console.error(`[RedisSub] Parsing error channel ${channel}:`, err);
        }
      }
    });
  }

  public async subscribeChannel(channel: string, callback: (data: any) => void): Promise<() => Promise<void>> {
    if (!this.listeners.has(channel)) {
      this.listeners.set(channel, new Set());
      await this.sub.subscribe(channel);
    }
    this.listeners.get(channel)!.add(callback);

    // Unsubscribe callback
    return async () => {
      const callbacks = this.listeners.get(channel);
      if (callbacks) {
        callbacks.delete(callback);
        if (callbacks.size === 0) {
          this.listeners.delete(channel);
          await this.sub.unsubscribe(channel);
        }
      }
    };
  }

  public createAsyncIterator<T>(channel: string): AsyncIterator<T> {
    const queue: T[] = [];
    let notifyResolver: (() => void) | null = null;
    let cleanup: (() => Promise<void>) | null = null;
    let isTerminated = false;

    // Register redis listener
    this.subscribeChannel(channel, (data: T) => {
      queue.push(data);
      if (notifyResolver) {
        notifyResolver();
        notifyResolver = null;
      }
    }).then((unsubFn) => {
      cleanup = unsubFn;
    });

    return {
      next: async () => {
        if (isTerminated) {
          return { done: true, value: undefined };
        }
        if (queue.length > 0) {
          return { done: false, value: queue.shift()! };
        }
        await new Promise<void>((resolve) => {
          notifyResolver = resolve;
        });
        return { done: false, value: queue.shift()! };
      },
      return: async () => {
        isTerminated = true;
        if (cleanup) await cleanup();
        return { done: true, value: undefined };
      },
      throw: async (err) => {
        isTerminated = true;
        if (cleanup) await cleanup();
        throw err;
      },
    };
  }
}

const pubSubHub = new RedisSubscriptionHub(redisSubscriber);

// --- RESOLVERS ---
const resolvers = {
  Query: {
    healthCheck: () => 'OK',
  },
  Mutation: {
    publishOrder: async (
      _: unknown,
      { symbol, price, volume }: { symbol: string; price: number; volume: number },
      context: { user?: UserSession }
    ) => {
      if (!context.user) {
        throw new Error('UNAUTHORIZED: JWT Session required');
      }

      const order = {
        id: `ord_${Date.now()}`,
        symbol,
        price,
        volume,
        timestamp: new Date().toISOString(),
        executedBy: context.user.userId,
      };

      // Broadcast ke Redis Channel terdistribusi
      const channel = `MARKET_ORDERS:${symbol.toUpperCase()}`;
      await redisPublisher.publish(channel, JSON.stringify(order));
      return order;
    },
  },
  Subscription: {
    orderPlaced: {
      subscribe: (
        _: unknown,
        { symbol }: { symbol: string },
        context: { user?: UserSession }
      ) => {
        if (!context.user) {
          throw new Error('Forbidden subscription attempt');
        }
        const channel = `MARKET_ORDERS:${symbol.toUpperCase()}`;
        return {
          [Symbol.asyncIterator]() {
            return pubSubHub.createAsyncIterator(channel);
          },
        };
      },
      resolve: (payload: any) => payload,
    },
  },
};

const schema = makeExecutableSchema({ typeDefs, resolvers });

// --- HTTP & WEBSOCKET CORE ENGINE ---
const server = createServer();
const wsServer = new WebSocketServer({
  server,
  path: '/graphql',
  // Proteksi memory starvation: per-connection payload limit (max 64KB)
  maxPayload: 64 * 1024,
});

useServer<ConnectionContextExtra>(
  {
    schema,
    onConnect: async (ctx) => {
      const authHeader = ctx.connectionParams?.Authorization as string | undefined;
      if (!authHeader || !authHeader.startsWith('Bearer ')) {
        // Reject handshake connection
        return false;
      }

      const token = authHeader.split(' ')[1];
      try {
        const { payload } = await jwtVerify(token, JWT_SECRET);
        // Bind state otentikasi ke context WS
        ctx.extra.user = {
          userId: payload.sub as string,
          role: (payload.role as string) || 'USER',
        };
        return true;
      } catch (err) {
        console.warn(`[Auth] Handshake JWT failed: ${(err as Error).message}`);
        return false;
      }
    },
    onContext: (ctx) => {
      return {
        user: ctx.extra.user,
      };
    },
  },
  wsServer
);

// Ping-Pong Heartbeat Loop untuk mengeliminasi "Zombie/Ghost Connections"
const KEEP_ALIVE_INTERVAL = 30_000; // 30 detik
const pingInterval = setInterval(() => {
  wsServer.clients.forEach((client: any) => {
    if (client.isAlive === false) {
      console.log('[Heartbeat] Terminating inactive dead connection');
      return client.terminate();
    }
    client.isAlive = false;
    client.ping();
  });
}, KEEP_ALIVE_INTERVAL);

wsServer.on('connection', (ws: any) => {
  ws.isAlive = true;
  ws.on('pong', () => {
    ws.isAlive = true;
  });
});

wsServer.on('close', () => {
  clearInterval(pingInterval);
});

server.listen(4000, () => {
  console.log('[PRODUCTION] GraphQL Engine berjalan pada http://localhost:4000/graphql');
});
```

---

### 8. Real World Case Study: High-Frequency Crypto/Stock Trading Gateway

#### Arsitektur Skala Enterprise
Sebuah exchange kripto melayani 250.000 concurrent client Web/Mobile yang meminta streaming data *Orderbook Updates*, *Live Trades*, dan *User Portfolio Margin Alerts*.

```
[250,000 Concurrent WS Clients]
         │  TLS Termination / Sticky Session
         ▼
[Edge Load Balancer (Envoy Proxy)]
         │  gRPC / WebSockets Multiplex
         ▼
[GraphQL Gateway Fleet: 20 Pods (NodeJS/Rust)]
         │  
         │  Subscribes via NATS Core Stream
         ▼
[Message Bus: NATS JetStream (Clustered, 1M msgs/sec)]
         ▲
         │  Publishes Matched Trades
[Core Matching Engine (C++ / Rust)]
```

#### Tantangan Skalabilitas & Solusi Produksi:
1. **Memory Pressure pada C100K**: Node.js default `ws` engine memakan memory ~35-50KB per socket idle. Untuk 100.000 socket, overhead socket murni mencapai 3.5GB–5GB tanpa GraphQL payload memory.
   *Solusi*: Engine dimigrasikan menggunakan `uWebSockets.js` wrapper di underlying layer `graphql-ws`, memotong baseline idle memory menjadi < 5KB per connection, menghemat 80% RAM instance.
2. **Execution Throttling (Backpressure)**: Matching engine memproduksi 5.000 trade match per detik per pairs (e.g. BTC/USDT). Jika GraphQL Gateway menjalankan execution AST resolver untuk tiap trade match secara granular per client, event-loop CPU akan mencapai 100% saturation (*starvation*).
   *Solusi*: Penerapan **Batch Aggregator Micro-buffering**:
   Engine mengumpulkan order trade events ke dalam interval 50ms (windowed array buffer), kemudian mengeksekusi AST GraphQL sekali untuk seluruh array chunk, mendistribusikan satu payload tunggal berisi multiple records ke klien. Latensi tetap di bawah 50ms, namun CPU utilization turun sebesar 74%.

---

### 9. Trade-offs

| Pendekatan / Keputusan | Keuntungan | Biaya / Kerugian | Rekomendasi Skenario |
| :--- | :--- | :--- | :--- |
| **GraphQL Subscription (WebSocket)** | Full duplex, latency terendah (< 5ms), continuous bi-directional protocol | Membutuhkan persistent connection, stateful server node, memory leak risk, WAF traversal hurdles | Live Chat, Live Interactive Collaborative Editing, Orderbook real-time |
| **Server-Sent Events (SSE / HTTP/2)** | Stateless over HTTP/2, auto-reconnect native browser, ramah WAF & CDN, memory overhead rendah | Unidirectional (Server-to-client saja), transport binary data harus Base64 | Notifikasi, Feed Activity Dashboard, Status Update Background Job |
| **Directives `@defer` & `@stream`** | Tidak butuh stateful WS server, payload terpecah alami via HTTP chunks | Membutuhkan client-side networking modern, parsing multipart rumit di sisi client | Dashboard analitik berat, rendering e-commerce detail page panjang |
| **Redis PubSub Engine** | Sangat cepat, integrasi mudah, latency mikrodetik | *Fire-and-forget* (tidak ada durability/replay), subscriber drop = pesan hilang | Real-time market tick, lokasi driver taksi instan |
| **Kafka / NATS JetStream Engine** | Persistent log stream, horizontal cluster partitioning, at-least-once guarantee | Latency overhead sedikit lebih tinggi dibanding Redis memory pubsub, operasional broker lebih kompleks | Auditing log transaksi keuangan, data stream critical billing |

---

### 10. Common Mistakes & Troubleshooting

#### Mistake 1: Validasi JWT Hanya di `connection_init` Tanpa Mekanisme Expiration Refresh
*Masalah*: Klien terhubung menggunakan token yang valid selama 1 jam. Koneksi WebSocket tetap terbuka selama 5 hari tanpa validasi ulang. Pengguna yang sudah dicabut izinnya (*revoked/banned*) tetap menerima payload rahasia enterprise.
*Solusi*:
Implementasikan scheduled connection-level eviction atau inject token validation di level *Subscription Field Resolver Execution*:
```typescript
// Di dalam field resolver
resolve: async (payload, args, context) => {
  const tokenPayload = await verifyCachedToken(context.user.userId);
  if (tokenPayload.isRevoked) {
    throw new GraphQLError('SESSION_REVOKED', {
      extensions: { code: 'UNAUTHENTICATED', http: { status: 401 } }
    });
  }
  return payload;
}
```

#### Mistake 2: Missing Async Generator Return Cleanup (Memory Leak Zombie Subscriber)
*Masalah*: Klien menutup browser tab secara tiba-tiba tanpa mengirimkan frame protocol `complete`. Jika server tidak mengikat listener `close` ke iterator `return()`, callback subscription pada Redis memory bus akan bocor selamanya di V8 heap.
*Deteksi*: Jalankan `node --inspect` dan pantau retainers di Chrome DevTools Heap Snapshot. Jika `RedisSubscriptionHub.listeners` terus bertambah sementara koneksi WS turun, ini terjadi.
*Mitigasi*: Gunakan always-safe disposal pipeline pada `graphql-ws` callback:
```typescript
onDisconnect: async (ctx, code, reason) => {
  // graphql-ws otomatis memanggil return() pada AsyncIterable, 
  // pastikan async iterable Anda mengeksekusi unsubscribe handler di blok `return()`!
}
```

#### Mistake 3: Menggunakan Redis Tunggal untuk App Cache dan High-Volume PubSub
*Masalah*: Thread IO Redis terblokir saat mengeksekusi command berat (seperti `KEYS *` atau clustering synchronization), yang menyebabkan packet drops dan WS heartbeat timeouts di layer aplikasi.
*Solusi*: Pisahkan Redis cluster node murni untuk pubsub message dispatching dari Redis caching & persistence storage.

---

### 11. Best Practices (Production Checklist)

1. [ ] **Gunakan Protokol Modern**: Wajib menggunakan protokol `graphql-transport-ws` (`graphql-ws`). Tinggalkan Apollo `subscriptions-transport-ws`.
2. [ ] **WebSocket Ping/Pong Heartbeat**: Set Ping/Pong aktif setiap 20–30 detik. Putus paksa soket yang gagal merespons Pong dalam 2 siklus berurutan.
3. [ ] **Ukuran Payload Dibungkus Batas**: Limitasi `maxPayload` maksimal 32KB - 64KB per WS Frame untuk mencegah Denial of Service via buffer stuffing.
4. [ ] **Connection Authorization Timeout**: Berikan batas waktu klien mengirimkan `connection_init` (maksimal 5 detik sejak TCP open). Jika lewat, server menutup koneksi:
   ```typescript
   useServer({ connectionInitWaitTimeout: 5000, /* ... */ }, wsServer);
   ```
5. [ ] **Granular Channel Filtering**: Jangan pernah menaruh logic filter otorisasi data di sisi client. Lakukan validasi hak akses channel di resolver `subscribe`, bukan membiarkan publisher me-leak data ke channel publik.
6. [ ] **Connection Throttling / Rate Limiting**: Batasi inisiasi koneksi per IP menggunakan Redis Sliding Window Rate Limiter (misal: max 10 WS connections per second per IP).
7. [ ] **Graceful Shutdown**: Saat Pod melakukan terminasi (SIGTERM):
   - Set status readiness HTTP probe ke false.
   - Kirimkan frame protocol `connection_terminate` atau close frame code `1001 (Going Away)` ke semua klien agar mereka melakukan retry failover bertahap ke Pod lain.
   - Tunggu socket close secara tuntas sebelum menghentikan event loop process.

---

### 12. Hands-on Practice

Buat dan simpan struktur file latihan ini pada direktori: `hands-on/m02/`

#### Task: Mengimplementasikan Resilient Notification Gateway
Kita akan membuat Subscription Server terisolasi dengan auto-cleanup dan multi-channel routing.

#### Langkah 1: Inisialisasi Project & Dependencies
```bash
mkdir -p hands-on/m02
cd hands-on/m02
npm init -y
npm install graphql graphql-ws ws @graphql-tools/schema ioredis jose
npm install --save-dev typescript @types/node @types/ws tsx
npx tsc --init
```

#### Langkah 2: Buat File `hands-on/m02/server.ts`
Salin source code dari seksi **7.2 Practical Example** ke dalam file ini.

#### Langkah 3: Setup Client Simulator Script
Buat file `hands-on/m02/client-simulator.ts`:

```typescript
// hands-on/m02/client-simulator.ts
import { createClient } from 'graphql-ws';
import WebSocket from 'ws';
import { SignJWT } from 'jose';

const JWT_SECRET = new TextEncoder().encode('secret-enterprise-key-123456');

async function run() {
  // 1. Generate Auth Token
  const token = await new SignJWT({ role: 'TRADER' })
    .setProtectedHeader({ alg: 'HS256' })
    .setSubject('user_dev_007')
    .setExpirationTime('2h')
    .sign(JWT_SECRET);

  console.log('[Client] Generated Token, connecting to WebSocket...');

  // 2. Setup Client Protocol
  const client = createClient({
    url: 'ws://localhost:4000/graphql',
    webSocketImpl: WebSocket,
    connectionParams: {
      Authorization: `Bearer ${token}`,
    },
  });

  // 3. Subscribe
  const unsubscribe = client.subscribe(
    {
      query: /* GraphQL */ `
        subscription {
          orderPlaced(symbol: "BTCUSDT") {
            id
            symbol
            price
            volume
            executedBy
            timestamp
          }
        }
      `,
    },
    {
      next: (data) => console.log('[Client RECV Received]:', JSON.stringify(data, null, 2)),
      error: (err) => console.error('[Client ERROR]:', err),
      complete: () => console.log('[Client COMPLETE] Subscribed stream closed.'),
    }
  );

  console.log('[Client] Listening on BTCUSDT channel. Running for 60 seconds...');
  setTimeout(() => {
    console.log('[Client] Auto-closing subscription.');
    unsubscribe();
    process.exit(0);
  }, 60000);
}

run().catch(console.error);
```

#### Langkah 4: Setup Mutation Publisher Script
Buat file `hands-on/m02/publisher-simulator.ts`:

```typescript
// hands-on/m02/publisher-simulator.ts
import { SignJWT } from 'jose';

const JWT_SECRET = new TextEncoder().encode('secret-enterprise-key-123456');

async function fireMutation() {
  const token = await new SignJWT({ role: 'SYSTEM' })
    .setProtectedHeader({ alg: 'HS256' })
    .setSubject('system_market_maker')
    .setExpirationTime('10m')
    .sign(JWT_SECRET);

  const mutation = JSON.stringify({
    query: `
      mutation {
        publishOrder(symbol: "BTCUSDT", price: 68500.5, volume: 1.25) {
          id
          symbol
        }
      }
    `,
  });

  const res = await fetch('http://localhost:4000/graphql', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
    body: mutation,
  });

  const json = await res.json();
  console.log('[Publisher Mutation Sent]:', json);
}

setInterval(fireMutation, 3000);
```

#### Langkah 5: Eksekusi dan Verifikasi
Pastikan Redis lokal Anda menyala:
```bash
docker run -d --name local-redis -p 6379:6379 redis:alpine
```
Jalankan di 3 terminal terpisah:
1. Terminal 1: `npx tsx hands-on/m02/server.ts`
2. Terminal 2: `npx tsx hands-on/m02/client-simulator.ts`
3. Terminal 3: `npx tsx hands-on/m02/publisher-simulator.ts`

Verifikasi bahwa event mutation yang dikirim Terminal 3 di-relay oleh Redis dan diterima seketika oleh Terminal 2.

---

### 13. Exercise

#### Level: Easy
1. Modifikasi resolver `orderPlaced` pada praktikum di atas agar menolak pendaftaran subscription jika argumen `symbol` kosong atau memiliki panjang kurang dari 3 karakter menggunakan `GraphQLError`.
2. Tambahkan logging metrics sederhana pada console server setiap kali ada client baru yang terhubung (`onConnect`) dan terputus (`onDisconnect`) yang menampilkan counter total *active connection*.

#### Level: Medium
1. Implementasikan filter mutasi berbasis payload. Ubah schema agar klien dapat meminta filter opsional `minVolume: Float`. Modifikasi subscription pipeline agar klien hanya menerima notifikasi order yang memiliki `volume >= minVolume`. Lakukan filtrasi ini di level execution context server, bukan di level Redis subscriber.
2. Tambahkan mekanisme autentikasi dinamis: Jika token JWT kadaluarsa kurang dari 10 detik saat klien mengirim frame `subscribe`, server harus mengembalikan error frame spesifik dan membatalkan stream operation tanpa memutus TCP connection.

#### Level: Hard
1. Buat mekanisme **Reconnection Buffer & Sequence Tracking**. Modifikasi message payload untuk menyertakan `sequenceNumber: Int`. Buat sistem buffer in-memory berbasis sliding ring buffer (100 item terakhir per channel). Jika klien terputus dan terhubung kembali dengan query parameter `lastSequenceReceived: Int`, server secara otomatis mem-flush event yang terlewatkan sebelum beralih ke stream real-time biasa.

---

### 14. Challenge: Zero-Downtime Hot Deploy under C100K Load

**Deskripsi Kasus Nyata**:
Anda adalah Principal Infrastructure Architect pada platform trading kripto enterprise. Server Subscription Gateway Anda saat ini menampung 100.000 concurrent WebSocket connections yang sedang aktif pada sebuah Kubernetes Deployment (tersebar di 10 pods).

Tim engineering perlu merilis versi GraphQL schema baru yang berisi *breaking schema validation* tanpa mengakibatkan:
1. **Thundering Herd Problem**: 100.000 socket terputus bersamaan dan melakukan reconnect serentak ke pod baru, yang berpotensi melumpuhkan Auth Service dan API Gateway.
2. **Missing In-flight Order Updates**: Pengguna kehilangan update data orderbook selama proses rollout.

**Tugas Arsitektur**:
Rancang dokumen arsitektur dan strategi mitigasi komprehensif yang mencakup:
- Strategi implementasi Kubernetes RollingUpdate lifecycle (`preStop` hooks, terminationGracePeriodSeconds, draining phase).
- Desain *Client-side Jittered Exponential Backoff* dengan WebSocket reconnect strategy.
- Desain dual-routing proxy layer (Blue/Green Stateful Routing Gateway) menggunakan Envoy / HAProxy yang dapat memindahkan subscriber secara bertahap (gradual drain: misal 2% koneksi per detik).
- Validasi trade-off: Mengapa tidak menggunakan HTTP Long-Polling sebagai fallback selama deployment berlangsung?

---

### 15. Quiz Evaluasi Pemahaman

#### Section 1: Basic (Pilihan Ganda)
1. Protokol transport library mana yang dianjurkan oleh GraphQL Working Group untuk WebSocket modern?
   - A. `subscriptions-transport-ws`
   - B. `graphql-ws`
   - C. `apollo-transport-ws`
   - D. `socket.io-graphql`
   *(Jawaban yang benar: B)*

2. Apa perbedaan utama antara GraphQL Subscriptions dan GraphQL Directives `@defer`?
   - A. Subscriptions membutuhkan SSE, `@defer` menggunakan UDP.
   - B. Subscriptions menggunakan persistent connection untuk push event berkali-kali tanpa batas waktu; `@defer` memecah single query execution menjadi beberapa chunk HTTP respons yang kemudian selesai.
   - C. `@defer` hanya dapat digunakan di REST API, bukan GraphQL.
   - D. Subscriptions tidak dapat menggunakan koneksi terenkripsi (TLS).
   *(Jawaban yang benar: B)*

3. Pada level mana pengecekan JWT token paling efisien dilakukan untuk meminimalkan beban CPU pada WebSocket server?
   - A. Di dalam setiap field resolver tipe objek.
   - B. Saat handshake / payload frame `connection_init`.
   - C. Setelah subscription query selesai dieksekusi.
   - D. Di dalam database trigger.
   *(Jawaban yang benar: B)*

4. Komponen apa yang wajib disediakan agar Subscriptions dapat berfungsi konsisten saat server GraphQL horizontal-scaled menjadi 10 pods?
   - A. Local Node.js `EventEmitter`.
   - B. Shared Disk Storage (NFS).
   - C. Distributed Message Broker (seperti Redis PubSub, NATS, Kafka).
   - D. Nginx Sticky Cookie Session tanpa broker.
   *(Jawaban yang benar: C)*

5. Karakteristik Server-Sent Events (SSE) dibandingkan WebSocket adalah:
   - A. SSE mendukung pengiriman binary frames dua arah secara natif.
   - B. SSE hanya mendukung komunikasi unidirectional (server-ke-klien) di atas protokol standar HTTP.
   - C. SSE tidak kompatibel dengan protokol HTTP/2.
   - D. SSE membutuhkan handshake upgrade 101 Switching Protocols.
   *(Jawaban yang benar: B)*

#### Section 2: Intermediate (Pilihan Ganda)
6. Apa dampak buruk dari ketiadaan mekanisme Ping/Pong Heartbeat pada long-lived WebSocket connection?
   - A. Data payload JSON otomatis terenkripsi ganda.
   - B. Firewall/NAT router perantara memutus koneksi TCP secara sepihak (*idle timeout*), menyebabkan *Ghost/Zombie connection* yang memakan memory server.
   - C. Client secara otomatis mematikan thread JavaScript.
   - D. Skema GraphQL berubah menjadi invalid AST.
   *(Jawaban yang benar: B)*

7. Mengapa pattern `pubsub.asyncIterator` in-memory bawaan Apollo Server tidak direkomendasikan untuk cluster production?
   - A. Karena tidak mendukung syntax TypeScript.
   - B. Menggunakan format binary yang korup jika dikirim antar-thread.
   - C. Hanya mendengarkan event yang dipublish oleh pod Node.js yang sama, sehingga klien yang terhubung ke pod lain tidak akan pernah menerima event.
   - D. Menghabiskan seluruh kuota CPU saat idle.
   *(Jawaban yang benar: C)*

8. Jika resolver subscription mengembalikan `AsyncIterator`, metode standar apa yang dipanggil oleh GraphQL Engine saat subscriber membatalkan subscription untuk membersihkan resource?
   - A. `iterator.clear()`
   - B. `iterator.return()`
   - C. `iterator.destroy()`
   - D. `iterator.flush()`
   *(Jawaban yang benar: B)*

9. Apa yang terjadi jika publisher memproduksi 10.000 messages/sec, namun throughput network client hanya sanggup menerima 100 messages/sec?
   - A. Client akan otomatis me-restart server.
   - B. WebSocket buffer server akan membengkak (*backpressure issue*) yang dapat berujung pada Node.js crash akibat V8 Out-Of-Memory.
   - C. Engine GraphQL secara otomatis mengubah transport menjadi UDP.
   - D. Redis secara otomatis menghapus koneksi client dari tabel routing.
   *(Jawaban yang benar: B)*

10. Direktif `@stream` secara spesifik dirancang untuk:
    - A. Memperlambat query database yang lambat.
    - B. Mengirimkan elemen-elemen dari field list/array secara bertahap saat data per row/item tersedia.
    - C. Mengirimkan video streaming langsung melalui GraphQL query.
    - D. Menggantikan WebSocket transport untuk subscription real-time.
    *(Jawaban yang benar: B)*

#### Section 3: Skenario Kasus Produksi (Analisis & Evaluasi)
11. **Skenario Memory Leak**:
    Setelah sistem berjalan selama 48 jam di cluster production, monitoring memory menunjukkan kenaikan steady (*sawtooth curve* hilang, menjadi *ramp-up* linear monotonic) dari 200MB ke 4GB pada container Pod GraphQL Gateway, meskipun traffic mutation rendah. Saat dicek, subscriber count menunjukkan angka 50.000, padahal pengguna aktif pada analytics dashboard hanya 1.200.  
    *Analisis penyebab utama dan mitigasi operasional tercepat apa yang harus dilakukan?*
    - **Penyebab**: Terjadi kegagalan deteksi pemutusan koneksi TCP/client (*dead/zombie sockets*) karena Ping/Pong heartbeat tidak diimplementasikan atau timeout tidak diatur. Event loop terus menahan socket instance dan closure context AsyncIterable di RAM.
    - **Mitigasi**: Aktifkan bidirectional heartbeat timer pada `useServer` / underlying `ws` engine, atur timeout threshold (misal: 30 detik), dan lakukan forced eviction socket (`socket.terminate()`) terhadap koneksi yang tidak membalas Pong.

12. **Skenario Cascade CPU Saturation**:
    Sebuah aplikasi FinTech mengirimkan notifikasi pergerakan harga emas menggunakan GraphQL Subscription. Saat harga emas melonjak drastis, publisher mengirimkan 3.000 update event per detik ke channel Redis. Akibatnya, CPU seluruh Node.js Gateway Pod melonjak ke 100% dan pod mulai gagal merespons liveness probe Kubernetes (*crash looping*).  
    *Arsitektur optimasi apa yang harus diterapkan pada resolver layer untuk menanggulangi lonjakan CPU tersebut?*
    - **Solusi**: Terapkan **Micro-batching / Throttle Operator** pada internal AsyncIterator server. Alih-alih mengeksekusi GraphQL Pipeline untuk setiap single tick yang masuk dari Redis, kumpulkan data tick selama 100ms window, lalu kirim payload agregat (array of ticks), atau lakukan *conflation* (hanya mengirim harga tick terakhir dalam window interval).

13. **Skenario Auth Token Invalidation**:
    Perusahaan Anda menerapkan aturan keamanan finansial ketat: jika user mengubah kata sandi, seluruh session aktif di Web/Mobile harus langsung terputus secara instan. Pada arsitektur saat ini, token diverifikasi pada frame `connection_init`. Klien yang sudah terkoneksi ke Subscription WebSocket tetap dapat mendengarkan private channel selama berjam-jam meskipun password sudah diubah dan token lama di-blacklist di Redis.  
    *Rancang mekanisme decoupling untuk memastikan koneksi WebSocket diputus seketika saat event revocations terjadi!*
    - **Solusi**: Hubungkan gateway ke Redis Channel khusus: `AUTH_REVOCATIONS`. Saat mutasi `changePassword` sukses, publish payload `{ userId: "..." }`. Seluruh Gateway Node yang mendengarkan channel ini akan memindai active connection pool mereka. Jika ditemukan context dengan `userId` tersebut, engine segera memanggil `ws.close(4401, "Session Revoked")` yang secara otomatis memicu cleanup di level protocol transport.

---

### 16. Summary

1. **Modern Protocols**: Tinggalkan library legacy `subscriptions-transport-ws`. Standar industri mewajibkan penggunaan `graphql-ws` untuk WebSocket atau Server-Sent Events (SSE) via HTTP/2 untuk skenario server-to-client streaming.
2. **Incremental Delivery**: Gunakan `@defer` untuk komponen data lambat dan `@stream` untuk array data masif melalui HTTP multipart responses guna menekan TTFB tanpa overhead stateful socket.
3. **Stateless Scale-Out**: GraphQL Subscriptions memerlukan external message broker (Redis PubSub, NATS, Kafka) untuk mendistribusikan events melintasi pod server stateless di balik load balancer.
4. **Resiliency & Defense**: Selalu konfigurasi active bidirectional Ping/Pong heartbeats, memory limit frame size (`maxPayload`), timeout handshake, serta kontrol backpressure agar gateway terhindar dari V8 Out-Of-Memory crash saat lonjakan traffic.