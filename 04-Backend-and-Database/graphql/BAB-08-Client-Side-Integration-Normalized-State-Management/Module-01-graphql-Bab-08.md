# Module 08.01: Client-Side Integration & Normalized State Management

---

## 01. IDENTITAS MODUL
* **Course:** Advanced GraphQL Backend & Integration Architecture
* **Category:** 04-Backend-and-Database
* **Module Code:** GQL-INT-0801
* **Level:** Advanced (L4/Principal-Track)
* **Domain:** Client-Side GraphQL Integration, Cache Normalization, Entity Identity Resolution, Optimistic UI Architecture
* **Stack:** TypeScript 5.x, Apollo Client 3.x / Urql Core, GraphQL 16.x, Node.js v20.x+ LTS

---

## 02. LEARNING OBJECTIVES
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
1. **Menganalisis dan Mengimplementasikan** mekanisme *Normalized Cache* pada GraphQL client (Apollo Client / Urql Graphcache) berbasis identitas global (`__typename:id`).
2. **Mendesain Kebijakan Cache Tingkat Lanjut** (*TypePolicies*, *KeyFields*, kustomisasi read/merge functions, dan *Dangling Reference Garbage Collection*).
3. **Mengeliminasi Latensi Pengguna** melalui *Optimistic UI Mutations* dengan *automatic rollback* ketika mutasi gagal dieksekusi oleh backend.
4. **Mengatasi Isu Fragment Colocation & Cache Inconsistencies** dengan static typing dari GraphQL Code Generator (`TypedDocumentNode`).
5. **Mengimplementasikan Strategi Keamanan Client** termasuk proteksi memory-leak cache, token expiration synchronization, and transport hardening.

---

## 03. CONCEPT MAP DIAGRAM (ASCII)
```
+-------------------------------------------------------------------------------+
|                       GRAPHQL CLIENT ARCHITECTURE                             |
+-------------------------------------------------------------------------------+
                                     |
               +---------------------+---------------------+
               |                                           |
    [ QUERY EXECUTION PATH ]                    [ MUTATION EXECUTION PATH ]
               |                                           |
      +--------v--------+                         +--------v--------+
      |  Cache Policy   |                         |  Optimistic UI  |
      | (cache-first /  |                         |    Response     |
      | network-only)   |                         +--------+--------+
      +--------+--------+                                  |
               |                                  +--------v--------+
      +--------v--------+                         | Apply to Store  |
      | Network Request |                         | (Temp Identity) |
      +--------+--------+                         +--------+--------+
               |                                           |
               | (JSON Payload)                   +--------v--------+
               +--------------------+             | Network Request |
                                    |             +--------+--------+
                                    |                      |
                        +-----------v-----------+          | (Success / Fail)
                        |    NORMALIZER ENGINE  |<---------+
                        +-----------+-----------+
                                    |
          +-------------------------+-------------------------+
          |                         |                         |
+---------v---------+     +---------v---------+     +---------v---------+
| Flatten Entities  |     | Compute Cache Key |     | Garbage Collector |
| (Extract Enums/   |     | (`__typename:id`) |     | (Evict Dangling   |
| Nested Objects)   |     +---------+---------+     | References)       |
+-------------------+               |               +-------------------+
                                    |
                          +---------v---------+
                          | In-Memory Record  |
                          | (Root Query/Types)|
                          +-------------------+
```

---

## 04. MENGAPA RELEVAN
Pada arsitektur sistem berbasis data terdistribusi atau microservices yang mengekspos GraphQL API, konsumsi data pada sisi client sering kali mengalami bottleneck performa jika diperlakukan layaknya REST endpoint (yaitu menyimpan raw JSON payload secara statis di Redux/Zustand store).

1. **Over-fetching & Redundant Network Traffic:** Tanpa normalisasi, query `getUserProfile` dan `getFeed` yang sama-sama memuat entitas `User` akan menduplikasi state. Mutasi di satu layar tidak akan merefleksikan perubahan di layar lain secara otomatis.
2. **Memory Leaks & Bloat:** Query terstruktur hierarkis (nested tree) yang disimpan mentah menyebabkan overhead konsumsi memori browser meningkat secara eksponensial (O(N) data duplication).
3. **Data Inconsistency (Stale Reads):** Ketika user memperbarui username melalui mutation, tanpa *Identity-based Normalized Store*, UI lain yang menampilkan username lama akan menampilkan data basi (*torn state*).

---

## 05. ANATOMI KONSEP INTI

### 1. The Normalization Algorithm
Normalisasi client-side mengubah struktur data GraphQL yang hierarkis (*nested tree*) menjadi relational key-value store yang datar (*flat table*):
- **Deconstruct:** Client melakukan traversal secara rekursif terhadap seluruh objek JSON yang memiliki field `__typename` dan ID field (`id` / `_id` / custom key).
- **Assign Unique Key:** Dihasilkan cache key tunggal, standarnya: `CacheKey = ${__typename}:${id}`.
- **Flatten & Reference:** Nilai objek di dalam parent diganti dengan pointer referensi internal, misalnya: `{"__ref": "User:101"}`.
- **Merge:** Field baru digabungkan dengan entitas yang sudah ada di tabel relasional in-memory.

```
Incoming Hierarchical JSON:
{
  "viewer": {
    "__typename": "User",
    "id": "101",
    "profile": {
      "__typename": "Profile",
      "id": "p-501",
      "theme": "dark"
    }
  }
}

Normalized Key-Value Store:
ROOT_QUERY -> { "viewer": { "__ref": "User:101" } }
User:101   -> { "__typename": "User", "id": "101", "profile": { "__ref": "Profile:p-501" } }
Profile:p-501 -> { "__typename": "Profile", "id": "p-501", "theme": "dark" }
```

### 2. Fetch Policies
| Policy | Read from Cache | Network Request | Update Cache | Use Case |
| :--- | :--- | :--- | :--- | :--- |
| `cache-first` | Ya (Jika ada) | Hanya jika cache miss | Ya | Data statis / jarang berubah |
| `cache-and-network` | Ya (Instan) | Selalu | Ya | Dashboard, Social Feed (High freshness) |
| `network-only` | Tidak | Selalu | Ya | Checkout, Konfirmasi Pembayaran |
| `no-cache` | Tidak | Selalu | Tidak | PII Data, Audit Log, Data Sekali Pakai |
| `cache-only` | Ya | Tidak pernah | Tidak | Offline Mode, Pre-cached UI Views |

### 3. TypePolicies & KeyFields
Secara default, client menggunakan `id` atau `_id`. Namun, pada entitas domain kompleks (misalnya entitas berbasis *composite primary key* seperti `UserSetting` dengan key `userId` + `settingKey`), client memerlukan konfigurasi eksplisit:
```typescript
keyFields: ["userId", "settingKey"] // Result: UserSetting:{"userId":"101","settingKey":"AUTH_2FA"}
```

---

## 06. PANDUAN IMPLEMENTASI STEP-BY-STEP

### Langkah 1: Instalasi Core Dependencies
Instalasikan paket GraphQL client modern dan GraphQL compiler typing toolchain:
```bash
npm install @apollo/client graphql
npm install -D @graphql-codegen/cli @graphql-codegen/client-preset
```

### Langkah 2: Konfigurasi Code Generator (`codegen.ts`)
Gunakan TypedDocumentNode untuk inferensi tipe otomatis dan penegakan fragment colocation:
```typescript
import { CodegenConfig } from '@graphql-codegen/cli';

const config: CodegenConfig = {
  schema: 'http://localhost:4000/graphql',
  documents: ['src/**/*.ts', 'src/**/*.tsx'],
  generates: {
    './src/gql/': {
      preset: 'client',
      plugins: [],
      config: {
        useTypeImports: true,
        strictScalars: true,
        scalars: {
          DateTime: 'string',
          Cursor: 'string',
        },
      },
    },
  },
};

export default config;
```

### Langkah 3: Setup In-Memory Cache & Key Configuration
Definisikan *TypePolicies* untuk normalisasi composite keys dan custom pagination merge.

### Langkah 4: Setup Client Transport Link & Deduplication
Konfigurasikan Apollo Link chain: `ErrorLink` $\to$ `RetryLink` $\to$ `AuthLink` $\to$ `HttpLink` (dengan batching dan deduplication diaktifkan).

---

## 07. CONTOH KASUS SEDERHANA

Berikut adalah demonstrasi esensial mekanisme in-memory normalization, pembacaan, dan mutasi cache secara terisolasi tanpa framework UI:

```typescript
import { ApolloClient, InMemoryCache, gql } from '@apollo/client/core';

// 1. Inisialisasi In-Memory Cache dengan custom KeyFields
const cache = new InMemoryCache({
  typePolicies: {
    ProductInventory: {
      // Composite key: SKU + WarehouseId
      keyFields: ['sku', 'warehouseId'],
    },
  },
});

const client = new ApolloClient({
  cache,
  ssrMode: false,
});

// 2. Query Mock Data
const STOCK_QUERY = gql`
  query GetStock {
    inventory {
      __typename
      sku
      warehouseId
      quantity
    }
  }
`;

// 3. Tulis langsung ke cache (Simulasi Network Response)
cache.writeQuery({
  query: STOCK_QUERY,
  data: {
    inventory: [
      {
        __typename: 'ProductInventory',
        sku: 'LAPTOP-PRO-15',
        warehouseId: 'WH-JKT-01',
        quantity: 45,
      },
    ],
  },
});

// 4. Inspeksi Identitas di Normalizer Store
const cacheKey = cache.identify({
  __typename: 'ProductInventory',
  sku: 'LAPTOP-PRO-15',
  warehouseId: 'WH-JKT-01',
});
console.log('Normalized Identity:', cacheKey); 
// Output: ProductInventory:{"sku":"LAPTOP-PRO-15","warehouseId":"WH-JKT-01"}

// 5. Update In-Place via Direct Cache Modification
cache.modify({
  id: cacheKey,
  fields: {
    quantity(existingQuantity) {
      return existingQuantity - 1; // Kurangi stok secara lokal
    },
  },
});

// 6. Verifikasi State Konsisten
const updatedData = cache.readQuery<{ inventory: Array<{ quantity: number }> }>({ query: STOCK_QUERY });
console.log('Updated Quantity in Cache:', updatedData?.inventory[0].quantity); 
// Output: 44
```

---

## 08. IMPLEMENTASI PRODUCTION-GRADE LENGKAP KODE

Berikut adalah implementasi end-to-end Client Integration Layer skala enterprise dengan isolasi transport, token refresh, pagination merging, dan optimistic mutation handling.

```typescript
// File: src/lib/graphql-client.ts
import {
  ApolloClient,
  InMemoryCache,
  HttpLink,
  ApolloLink,
  Observable,
  FetchResult,
  from,
  gql,
  TypedDocumentNode,
  CombinedError,
} from '@apollo/client/core';
import { onError } from '@apollo/client/link/error';

// ============================================================================
// 1. DATA CONTRACTS & INTERFACES
// ============================================================================
export interface Post {
  __typename: 'Post';
  id: string;
  title: string;
  content: string;
  likesCount: number;
  isLiked: boolean;
  version: number;
  updatedAt: string;
}

export interface PaginatedPosts {
  __typename: 'PostConnection';
  edges: Array<{
    __typename: 'PostEdge';
    cursor: string;
    node: Post;
  }>;
  pageInfo: {
    __typename: 'PageInfo';
    endCursor: string | null;
    hasNextPage: boolean;
  };
}

export interface ToggleLikeMutationVariables {
  postId: string;
  clientMutationId: string;
}

export interface ToggleLikeMutationResponse {
  toggleLike: {
    __typename: 'ToggleLikePayload';
    post: Post;
    clientMutationId: string;
  };
}

// ============================================================================
// 2. DOCUMENT DEFINITIONS WITH STRICT FRAGMENTS
// ============================================================================
export const POST_FRAGMENT = gql`
  fragment PostFields on Post {
    id
    title
    content
    likesCount
    isLiked
    version
    updatedAt
  }
`;

export const GET_POSTS_QUERY: TypedDocumentNode<
  { posts: PaginatedPosts },
  { first: number; after?: string | null }
> = gql`
  query GetPosts($first: Int!, $after: String) {
    posts(first: $first, after: $after) {
      __typename
      edges {
        __typename
        cursor
        node {
          ...PostFields
        }
      }
      pageInfo {
        __typename
        endCursor
        hasNextPage
      }
    }
  }
  ${POST_FRAGMENT}
`;

export const TOGGLE_LIKE_MUTATION: TypedDocumentNode<
  ToggleLikeMutationResponse,
  ToggleLikeMutationVariables
> = gql`
  mutation ToggleLike($postId: ID!, $clientMutationId: String!) {
    toggleLike(postId: $postId, clientMutationId: $clientMutationId) {
      __typename
      clientMutationId
      post {
        ...PostFields
      }
    }
  }
  ${POST_FRAGMENT}
`;

// ============================================================================
// 3. ADVANCED CACHE INSTANTIATION (TYPE POLICIES & MERGING)
// ============================================================================
export function createProductionCache(): InMemoryCache {
  return new InMemoryCache({
    typePolicies: {
      Query: {
        fields: {
          posts: {
            keyArgs: false, // Unified single list across offset/cursor queries
            merge(existing: PaginatedPosts | undefined, incoming: PaginatedPosts): PaginatedPosts {
              if (!existing) return incoming;

              const existingEdges = existing.edges || [];
              const incomingEdges = incoming.edges || [];

              // Deduplikasi record berbasis node.id
              const edgeMap = new Map<string, (typeof incomingEdges)[0]>();
              for (const edge of existingEdges) {
                edgeMap.set(edge.node.id, edge);
              }
              for (const edge of incomingEdges) {
                edgeMap.set(edge.node.id, edge);
              }

              return {
                ...incoming,
                edges: Array.from(edgeMap.values()),
                pageInfo: incoming.pageInfo,
              };
            },
          },
        },
      },
      Post: {
        keyFields: ['id'],
        fields: {
          // Field policy to sanitize or locally compute properties
          likesCount: {
            read(existing: number = 0) {
              return Math.max(0, existing);
            },
          },
        },
      },
    },
  });
}

// ============================================================================
// 4. LINK CHAIN: ERROR HANDLING & TOKEN REFRESH ENGINE
// ============================================================================
let isRefreshing = false;
let pendingRequestsQueue: Array<() => void> = [];

const processQueue = () => {
  pendingRequestsQueue.forEach((callback) => callback());
  pendingRequestsQueue = [];
};

const errorLink = onError(({ graphQLErrors, networkError, operation, forward }) => {
  if (graphQLErrors) {
    for (const err of graphQLErrors) {
      if (err.extensions?.code === 'UNAUTHENTICATED') {
        return new Observable<FetchResult>((observer) => {
          if (!isRefreshing) {
            isRefreshing = true;
            // Simulasi token refresh async
            refreshTokenService()
              .then((newToken) => {
                sessionStorage.setItem('access_token', newToken);
                processQueue();
                forward(operation).subscribe(observer);
              })
              .catch((refreshErr) => {
                observer.error(refreshErr);
              })
              .finally(() => {
                isRefreshing = false;
              });
          } else {
            // Antrekan request jika token sedang di-refresh
            pendingRequestsQueue.push(() => {
              forward(operation).subscribe(observer);
            });
          }
        });
      }
    }
  }

  if (networkError) {
    console.error(`[GraphQL Network Failure]: ${networkError.message}`);
  }
});

const authLink = new ApolloLink((operation, forward) => {
  const token = typeof window !== 'undefined' ? sessionStorage.getItem('access_token') : null;
  operation.setContext(({ headers = {} }) => ({
    headers: {
      ...headers,
      authorization: token ? `Bearer ${token}` : '',
      'X-Client-Version': '1.0.0-enterprise',
    },
  }));
  return forward(operation);
});

const httpLink = new HttpLink({
  uri: 'https://api.domain.internal/graphql',
  fetchOptions: {
    cache: 'no-store',
  },
});

// Helper Mock Service Token Refresh
async function refreshTokenService(): Promise<string> {
  return 'NEW_ENCRYPTED_JWT_TOKEN';
}

// ============================================================================
// 5. CLIENT INSTANCE EXPORT
// ============================================================================
export const apolloClient = new ApolloClient({
  link: from([errorLink, authLink, httpLink]),
  cache: createProductionCache(),
  defaultOptions: {
    watchQuery: {
      fetchPolicy: 'cache-and-network',
      nextFetchPolicy: 'cache-first',
      errorPolicy: 'all',
    },
    query: {
      fetchPolicy: 'network-only',
      errorPolicy: 'all',
    },
    mutate: {
      errorPolicy: 'all',
    },
  },
});

// ============================================================================
// 6. DOMAIN SERVICE IMPLEMENTING OPTIMISTIC MUTATION & ROLLBACK
// ============================================================================
export class PostService {
  constructor(private client: ApolloClient<unknown> = apolloClient) {}

  public async toggleLikeOptimistic(targetPost: Post): Promise<void> {
    const isCurrentlyLiked = targetPost.isLiked;
    const optimisticNextLikes = isCurrentlyLiked
      ? targetPost.likesCount - 1
      : targetPost.likesCount + 1;

    try {
      await this.client.mutate<ToggleLikeMutationResponse, ToggleLikeMutationVariables>({
        mutation: TOGGLE_LIKE_MUTATION,
        variables: {
          postId: targetPost.id,
          clientMutationId: `cl_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        },
        // 6.1 State Optimistik yang langsung direfleksikan ke Cache
        optimisticResponse: {
          toggleLike: {
            __typename: 'ToggleLikePayload',
            clientMutationId: 'optimistic-id',
            post: {
              __typename: 'Post',
              id: targetPost.id,
              title: targetPost.title,
              content: targetPost.content,
              likesCount: optimisticNextLikes,
              isLiked: !isCurrentlyLiked,
              version: targetPost.version + 1,
              updatedAt: new Date().toISOString(),
            },
          },
        },
        // 6.2 Manual Cache Update jika mutasi mengembalikan shape data baru
        update(cache, { data }) {
          if (!data?.toggleLike.post) return;
          const returnedPost = data.toggleLike.post;

          cache.modify({
            id: cache.identify({ __typename: 'Post', id: returnedPost.id }),
            fields: {
              likesCount() {
                return returnedPost.likesCount;
              },
              isLiked() {
                return returnedPost.isLiked;
              },
              version() {
                return returnedPost.version;
              },
            },
          });
        },
      });
    } catch (error) {
      // Jika terjadi error pada jaringan/backend, Apollo Client secara 
      // internal otomatis membuang lapisan optimisticResponse (Atomic Rollback).
      console.error('[PostService] Mutation failed. Local cache safely rolled back.', error);
      throw error;
    }
  }
}
```

---

## 09. DIAGRAM ALUR KERJA (ASCII)

### Optimistic UI & Automatic Rollback Workflow
```
[ UI Component ]              [ Apollo Cache ]               [ Remote Server ]
       |                              |                              |
       |--- 1. Dispatch Action ------>|                              |
       |    (ToggleLike)              |                              |
       |                              |                              |
       |--- 2. Write Optimistic ----->|                              |
       |    Patch Layer               |                              |
       |<-- 3. Trigger UI Re-render --|                              |
       |    (Instant Feedback)        |                              |
       |                              |                              |
       |------------------------ 4. Dispatch GraphQL Mutation ------>|
       |                                                             |
       |                     ===================                     |
       |                     CASE A: SUCCESS (200)                   |
       |                     ===================                     |
       |                              |<-- 5a. Return Payload -------|
       |                              |    (Actual Server State)     |
       |                              |                              |
       |                              |-- 6a. Discard Optimistic     |
       |                              |   & Write Final Data         |
       |                              |                              |
       |                     ===================                     |
       |                     CASE B: FAILURE (500)                   |
       |                     ===================                     |
       |                              |<-- 5b. Return Error ---------|
       |                              |                              |
       |                              |-- 6b. Discard Optimistic     |
       |                              |   (Rollback to Snapshot)     |
       |<-- 7b. Emit Error to UI -----|                              |
       |    (Show Toast Notification) |                              |
```

---

## 10. ANALISIS TRADE-OFFS

| Pendekatan | Keuntungan | Kerugian & Konsekuensi |
| :--- | :--- | :--- |
| **Normalized In-Memory Cache** (Apollo/Urql) | - Konsistensi state lintas halaman/komponen otomatis.<br>- Penghematan bandwidth drastis (read-after-write). | - Memory footprint tinggi pada dataset masif.<br>- Kurva belajar konfigurasi `keyFields` dan pagination merge tinggi. |
| **Document-based/Raw State** (React Query / SWR) | - Simpel, mudah di-debug (identik dengan native REST).<br>- Garbage collection per-query path sangat transparan. | - Terjadi data inkonsistensi saat entitas yang sama diupdate di query yang berbeda.<br>- Duplikasi identitas objek di memori. |
| **Aggressive Optimistic UI** | - Perceived latency = 0ms; pengalaman pengguna sangat mulus. | - Kompleksitas rollback handling jika ada *cascading dependencies* antar mutasi.<br>- Risiko race conditions pada multiple parallel edits. |
| **Pessimistic UI (Block until Ack)** | - Menjamin determinisme dan kesesuaian data secara akurat. | - UI terasa lambat dan blocking bagi pengguna di jaringan seluler/berlatensi tinggi. |

---

## 11. BEST PRACTICES & ANTIPATTERNS

### Best Practices:
1. **Always Request `id` and `__typename`:** Pastikan setiap query memilih field `id` dan `__typename` (atau dikonfigurasi melalui fragment global) agar normalizer tidak memecah entitas menjadi isolated anonymous records.
2. **Co-locate Fragments:** Komponen UI anak harus mendeklarasikan kebutuhan datanya menggunakan GraphQL Fragments, bukan mengandalkan props passing queries raksasa dari root.
3. **Use Explicit Pagination Merging:** Selalu definisikan merge functions secara deterministik di `TypePolicies` untuk connection/edge patterns guna mencegah duplicate list items pada infinite-scrolling.

### Antipatterns to Avoid:
1. **The God-Object Mutate-and-Refetch Pattern:** Memanggil `refetchQueries: ['All']` setelah setiap mutasi. Ini menghancurkan kegunaan client-side cache dan membebani database backend dengan load query ulang.
2. **Direct State Duplication:** Mengambil data dari Apollo Cache lalu menyalinnya secara permanen ke local React `useState` atau Redux store. Ini menciptakan *Dual Source of Truth* yang berujung pada UI data desynchronization.
3. **Omitting Optimistic IDs:** Menggunakan random ID yang bentrok atau tidak konsisten pada mutasi pembuatan record (`CreatePost`), yang mengakibatkan cache gagal mengasosiasikan real response dengan temporary node.

---

## 12. SECURITY HARDENING

1. **Client-Side Cache Sanitization on Logout:**
   Ketika user logout, in-memory cache **wajib** dibersihkan secara atomik untuk mencegah *Cross-Session Data Leakage* pada shared machines.
   ```typescript
   export async function purgeClientSession(client: ApolloClient<unknown>) {
     // Hapus access token dari volatile storage
     sessionStorage.removeItem('access_token');
     // Reset store secara penuh, membatalkan request yang sedang aktif
     await client.clearStore();
     await client.resetStore();
   }
   ```
2. **Preventing Sensitive Data Normalization:**
   Data sensitif seperti kredensial kartu kredit, CVV, atau password hash tidak boleh masuk ke Normalized Store. Gunakan fetch policy `no-cache` secara mandatory pada mutation/query yang memproses Payload sensitif.
3. **Anti-CSRF with Custom Headers:**
   Jangan mengandalkan mekanisme otentikasi browser murni (cookies) tanpa menambahkan custom header (`X-Requested-With` atau `X-CSRF-Token`) di Apollo Link chain untuk menangkal eksekusi mutasi cross-origin yang tidak diotorisasi.

---

## 13. OBSERVABILITAS & DEBUGGING

1. **Apollo Client Devtools Interception:**
   Gunakan properti `connectToDevTools: process.env.NODE_ENV !== 'production'` saat instantiasi client untuk memvisualisasikan *Cache Tree Graph*, *Key Assignments*, dan *Active Watchers*.
2. **Link Tracing Logging:**
   Sematkan custom logging link di development mode untuk mengukur execution time per GraphQL operation:
   ```typescript
   const roundTripTrackerLink = new ApolloLink((operation, forward) => {
     const startTime = performance.now();
     return forward(operation).map((data) => {
       const elapsed = performance.now() - startTime;
       if (elapsed > 500) {
         console.warn(`[SLOW GRAPHQL OPERATION] ${operation.operationName} took ${elapsed.toFixed(2)}ms`);
       }
       return data;
     });
   });
   ```
3. **Dangling References Detection:**
   Jalankan method `cache.gc()` secara periodik atau setelah operasi `evict()` masif untuk mendeteksi dan membersihkan orphaned cache identifiers:
   ```typescript
   const unreachableIds = cache.gc();
   console.debug('Garbage Collector Freed Entries:', unreachableIds);
   ```

---

## 14. BENCHMARKING & PERFORMANCE

Metrik optimasi client cache GraphQL yang ideal:
- **Normalized Cache Hit Ratio:** $\ge 75\%$ untuk navigating antar view standar.
- **Cache Read Latency:** $\le 2\text{ms}$ untuk retrieval entity identik.
- **Memory Overhead Limit:** $\le 50\text{MB}$ untuk retention $\approx 10,000$ entitas normalisasi.

### Memory & Performance Diagnostic Snippet
```typescript
export function auditCachePerformance(cache: InMemoryCache) {
  const serialized = JSON.stringify(cache.extract());
  const sizeInBytes = new Blob([serialized]).size;
  const sizeInMB = (sizeInBytes / (1024 * 1024)).toFixed(2);
  
  console.table({
    'Cache Size (Heap Approximated)': `${sizeInMB} MB`,
    'Root Query Pointers': Object.keys(cache.extract().ROOT_QUERY || {}).length,
    'Total Identified Entities': Object.keys(cache.extract()).length - 1,
  });
}
```

---

## 15. HANDS-ON LAB MINI-PROJECT

### Skenario Lab
Anda diminta untuk membangun sub-sistem State Management untuk modul E-Commerce Cart. Sistem harus mendukung:
1. Membaca data Shopping Cart yang ternormalisasi berdasarkan `CartItem` composite key (`cartId` + `productId`).
2. Mutasi `updateQuantity` yang dieksekusi secara **Optimistic UI**.
3. Revert otomatis ketika backend melempar error `OUT_OF_STOCK`.

### Struktur File:
```
lab-graphql-client/
├── package.json
├── tsconfig.json
├── src/
│   ├── cache.ts
│   ├── operations.ts
│   └── cart-manager.ts
└── tests/
    └── cart.spec.ts
```

### Implementasi `src/cart-manager.ts`:
```typescript
import { ApolloClient, InMemoryCache, gql, ApolloError } from '@apollo/client/core';

export const CART_FRAGMENT = gql`
  fragment CartItemFields on CartItem {
    cartId
    productId
    name
    quantity
    unitPrice
  }
`;

export const UPDATE_CART_QTY_MUTATION = gql`
  mutation UpdateCartQty($cartId: ID!, $productId: ID!, $quantity: Int!) {
    updateCartQuantity(cartId: $cartId, productId: $productId, quantity: $quantity) {
      __typename
      cartItem {
        ...CartItemFields
      }
    }
  }
  ${CART_FRAGMENT}
`;

export class CartManager {
  public client: ApolloClient<unknown>;

  constructor(clientInstance?: ApolloClient<unknown>) {
    this.client =
      clientInstance ||
      new ApolloClient({
        cache: new InMemoryCache({
          typePolicies: {
            CartItem: {
              keyFields: ['cartId', 'productId'],
            },
          },
        }),
      });
  }

  public async updateItemQuantity(
    cartId: string,
    productId: string,
    name: string,
    unitPrice: number,
    newQuantity: number
  ): Promise<void> {
    await this.client.mutate({
      mutation: UPDATE_CART_QTY_MUTATION,
      variables: { cartId, productId, quantity: newQuantity },
      optimisticResponse: {
        updateCartQuantity: {
          __typename: 'UpdateCartQuantityPayload',
          cartItem: {
            __typename: 'CartItem',
            cartId,
            productId,
            name,
            quantity: newQuantity,
            unitPrice,
          },
        },
      },
    });
  }
}
```

---

## 16. AUTOMATED TESTING & VERIFICATION

Pengujian unit menggunakan Jest/Vitest untuk memvalidasi bahwa Optimistic Updates dieksekusi dengan tepat dan di-*rollback* seketika jika eksekusi mutasi gagal.

```typescript
// File: tests/cart.spec.ts
import { describe, it, expect, vi } from 'vitest';
import { CartManager, UPDATE_CART_QTY_MUTATION } from '../src/cart-manager';
import { InMemoryCache, ApolloClient, Observable } from '@apollo/client/core';
import { ApolloLink } from '@apollo/client/core';

describe('CartManager Normalized Optimistic Mutation Tests', () => {
  it('harus menerapkan optimistic update dan rollback jika server melempar network error', async () => {
    // 1. Setup Mock Link yang mensimulasikan kegagalan server
    const mockErrorLink = new ApolloLink(() => {
      return new Observable((observer) => {
        setTimeout(() => {
          observer.error(new Error('OUT_OF_STOCK'));
        }, 50); // delay network
      });
    });

    const cache = new InMemoryCache({
      typePolicies: {
        CartItem: { keyFields: ['cartId', 'productId'] },
      },
    });

    const client = new ApolloClient({
      link: mockErrorLink,
      cache,
    });

    const cartManager = new CartManager(client);

    // 2. Pre-populate Cache
    const itemKey = cache.identify({
      __typename: 'CartItem',
      cartId: 'C-01',
      productId: 'P-99',
    });

    cache.writeFragment({
      id: itemKey,
      fragment: gql`
        fragment ExistingItem on CartItem {
          __typename
          cartId
          productId
          name
          quantity
          unitPrice
        }
      `,
      data: {
        __typename: 'CartItem',
        cartId: 'C-01',
        productId: 'P-99',
        name: 'Gaming Mouse',
        quantity: 1,
        unitPrice: 50,
      },
    });

    // Verifikasi initial state di cache
    const initialItem = cache.readFragment<{ quantity: number }>({
      id: itemKey,
      fragment: gql`fragment ReadItem on CartItem { quantity }`,
    });
    expect(initialItem?.quantity).toBe(1);

    // 3. Eksekusi Mutasi dengan antisipasi error
    const updatePromise = cartManager.updateItemQuantity('C-01', 'P-99', 'Gaming Mouse', 50, 5);

    // 4. Verifikasi Status Optimistik (Sebelum promise selesai reject)
    const optimisticItem = cache.readFragment<{ quantity: number }>({
      id: itemKey,
      fragment: gql`fragment ReadItem on CartItem { quantity }`,
    });
    expect(optimisticItem?.quantity).toBe(5);

    // 5. Tunggu mutasi gagal
    await expect(updatePromise).rejects.toThrow('OUT_OF_STOCK');

    // 6. Verifikasi Rollback: Nilai kembali ke 1, BUKAN 5
    const rolledBackItem = cache.readFragment<{ quantity: number }>({
      id: itemKey,
      fragment: gql`fragment ReadItem on CartItem { quantity }`,
    });
    expect(rolledBackItem?.quantity).toBe(1);
  });
});
```

---

## 17. TROUBLESHOOTING GUIDE

| Gejala Masalah (Symptom) | Kemungkinan Akar Masalah (Root Cause) | Solusi Perbaikan (Fix) |
| :--- | :--- | :--- |
| Peringatan konsol: *Missing field 'id' while writing result...* | Query lupa mendefinisikan field `id` atau objek downstream tidak memiliki default primary key. | Tambahkan `id` ke GraphQL Query selection set atau definisikan custom `keyFields` pada `InMemoryCache`. |
| Duplikasi item saat pagination fetchMore dipanggil. | Tidak ada merge function di