# BAB 04: Arsitektur Informasi dan Navigasi Struktural Enterprise
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis dan Merancang** *Directed Acyclic Graph* (DAG) untuk Arsitektur Informasi (IA) polihierarki pada sistem multi-tenant skala enterprise.
2. **Mengimplementasikan** *Runtime Dynamic Navigation Engine* berbasis *Attribute-Based Access Control* (ABAC) dan *Role-Based Access Control* (RBAC) tanpa mengorbankan performa *Cumulative Layout Shift* (CLS) dan *Interaction to Next Paint* (INP).
3. **Membangun** sistem navigasi polimorfik yang mendukung *micro-frontend federation*, deep-linking kontekstual, dan *command palette* global terindeks.
4. **Mengoptimalkan** resolusi state navigasi, *breadcrumb pathfinding*, dan *prefetching heuristics* pada aplikasi web berskala ribuan rute dinamis.
5. **Mengevaluasi** struktur navigasi menggunakan metrik telemetri UX (*Task Completion Time*, *Lostness Metric*, dan *Backtracking Rate*).

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib menguasai:
- **Arsitektur Frontend Modern**: Pemahaman mendalam mengenai routing berbasis SSR/SSG/ISR (Next.js App Router atau Remix), React 18/19 Server Components, dan Micro-frontend architecture (Module Federation).
- **Struktur Data & Algoritma**: Representasi Graf, *Tree Traversal* (BFS/DFS), algoritma *Shortest Path* (Dijkstra/A*), dan manipulasi *Immutable State Tree*.
- **Keamanan & Otorisasi**: Konsep dasar RBAC, ABAC, JWT claims resolution, dan tenant boundary context.
- **Sistem Desain Enterprise**: Pemahaman tentang tokenisasi UI, ARIA Live Regions, dan navigasi aksesibilitas (WAI-ARIA 1.2 authoring practices).

---

### 3. Concept & Internal Architecture (Mendalam)

Navigasi enterprise tidak dapat diselesaikan dengan struktur pohon monohierarki statis sederhana (`parent -> child`). Di lingkungan korporasi berskala besar (ERP, Core Banking, Supply Chain Logistics), satu entitas data yang sama (misal: *Invoice #9821*) dapat diakses secara bersamaan dari berbagai domain: *Finance*, *Procurement*, *Audit Trail*, dan *Customer Relationship Management*. Hal ini menuntut transisi ke **Arsitektur Informasi Polihierarki Berbasis Graf Berarah Bebas Siklus (DAG)**.

```
       [Enterprise Root IA Node]
              /         \
    [Procurement Hub]   [Finance Hub]
           |                  |
    [Purchase Orders]   [Accounts Payable]
           \                  /
            v                v
      [[ Dynamic Invoice Entity: #9821 ]]
                     |
         [Audit & Compliance View]
```

#### A. Mesin Navigasi Polihierarki (DAG-Based IA)
Pada model monohierarki, node anak hanya memiliki satu parent node (`Node.parent: NodeId`). Dalam struktur polihierarki enterprise, node anak didefinisikan sebagai:

$$\text{Node} = \{ \text{id}, \text{labels}, \text{parents}: [\text{NodeId}_1, \text{NodeId}_2, \dots, \text{NodeId}_k], \text{evaluator}: f(\text{Context}) \to \text{Visibility} \}$$

Ketika rute dirender, traversal *Breadcrumb Engine* harus menyelesaikan ambiguitas riwayat jalur pengguna (*provenance path*) menggunakan state sesi pengguna, bukan sekadar memetakan segmen URL statis.

#### B. Runtime Access & Capability Evaluation Pipeline
Penyaringan navigasi enterprise tidak boleh dilakukan di layer presentasi dengan klausa `v-if` atau `menu.role === user.role` yang berserakan. Sistem membutuhkan *Pure Deterministic Pruning Pipeline*:

1. **Manifest Ingestion**: Pengambilan graf rute terfederasi dari masing-masing micro-frontend atau service catalog.
2. **Context Resolution**: Injeksi *Security Context* (User Identity, Permissions, Tenant Entitlements, Feature Flags, Workspace Mode).
3. **Graph Pruning (Subtree Trimming)**: Algoritma penyusutan rekursif:
   - Jika suatu simpul (node) tidak lolos evaluasi ABAC/Entitlement, simpul tersebut beserta seluruh *sub-graph non-reachable* yang bergantung padanya akan dipangkas.
   - Pengecualian: Node yang memiliki jalur alternatif (*alternative active edge*) tetap dipertahankan.
4. **Memoized Graph Flattening**: Transformasi graf tereduksi menjadi *Lookup Table* $O(1)$ untuk rendering cepat dan pencarian *Command Palette*.

#### C. Model State Navigasi Polimorfik
Enterprise UX modern memisahkan struktur navigasi menjadi 4 layer ortogonal:
1. **L1 - Global Workspace Switcher**: Mengubah konteks tenant, organisasi, atau region operasional.
2. **L2 - Domain Hub (Primary Navigation)**: Kategori bisnis fungsional tingkat tinggi (e.g., Inventory, Ledger, Human Resources).
3. **L3 - Contextual Workspace (Secondary/Sidebar Navigation)**: Polimorfik berdasarkan workflow yang sedang aktif (e.g., Batch Processing mode vs Single Entry mode).
4. **L4 - Command Layer (Ambient Navigation)**: *Modal keyboard-first entry point* (`Cmd+K`) yang memintas seluruh hierarki berdasarkan kueri semantik dan fuzzy matching.

---

### 4. Why & What

#### Why: Permasalahan Arsitektur Navigasi Monolitik Tradisional
1. **Navigation Bloat & Cognitive Overload**: Penambahan modul baru secara horizontal menyebabkan navigasi bertingkat (mega-menu 4-5 lapis) yang membingungkan operator dan melanggar Batasan Miller ($7 \pm 2$ chunk).
2. **Tenant Entitlement Leaks**: Rute dan label navigasi yang tidak seharusnya diakses oleh tenant tier-rendah bocor di DOM, memicu celah keamanan *Broken Object Level Authorization* (BOLA) dan *Broken Function Level Authorization* (BFLA).
3. **Inconsistent Breadcrumb Pathing**: Pada deep-link langsung dari email atau webhook, breadcrumb sering salah menampilkan parent konteks default, memutus mental model navigasi pengguna.
4. **Micro-frontend Routing De-synchronization**: Ketidaksinkronan riwayat browser antara shell host dan child micro-frontends saat mengeksekusi navigasi lintas-domain.

#### What: Dynamic Enterprise IA Engine
Solusinya adalah arsitektur navigasi decoupled di mana:
- Struktur navigasi dideklarasikan sebagai **Metadata Kontrak (NavSchema)** yang dapat divalidasi skemanya pada saat runtime.
- Breadcrumb dihitung secara matematis menggunakan riwayat traversal sesi terkini atau *Shortest Valid Semantic Path* jika diakses via deep link.
- Navigasi adalah sistem state-driven reaktif murni yang merefleksikan otorisasi, dependensi lisensi fitur (licensing matrix), dan konteks kerja pengguna.

---

### 5. How (Workflow Detail)

Alur kerja evaluasi dan rendering navigasi enterprise dijelaskan dalam tahapan berikut:

```
[MFE Route Schemas] --> [Central IA Registry Engine]
                               |
                               v
                     [Raw Navigation Graph]
                               |
                               +<-- [User Token (ABAC Claims)]
                               +<-- [Tenant Feature Matrix]
                               +<-- [Current Navigation History]
                               |
                               v
                  [Topological Sort & Pruner]
                               |
                               v
                  [Pruned Active Navigation Tree]
                     /                    \
                    v                      v
        [Primary Nav Layout]       [Command Palette Index]
                    \                      /
                     v                    v
                   [Contextual Breadcrumb Path]
```

1. **Step 1: Manifest Extraction & Validation**
   - Host shell mengumpulkan manifest parsial dari setiap modul remote via Module Federation atau API Gateway.
   - Skema divalidasi terhadap `NavigationNodeContract` menggunakan runtime validator (e.g., Zod) untuk mencegah malformed tree.
2. **Step 2: ABAC/Feature Pruning (Execution)**
   - Engine mengeksekusi traversal *Post-Order Depth-First Search* (DFS).
   - Simpul daun (*leaf nodes*) dievaluasi terlebih dahulu terhadap policy:
     $$\text{IsVisible}(n) = \text{EvaluatePolicy}(n.\text{requiredPolicy}, \text{UserContext}) \land \text{IsFeatureEnabled}(n.\text{featureFlag})$$
   - Simpul cabang (*branch nodes*) otomatis dipangkas jika seluruh simpul anaknya berstatus tidak terlihat dan cabang tersebut tidak memiliki aksi mandiri (*dead-end branch pruning*).
3. **Step 3: Breadcrumb Provenance Resolution**
   - Membaca stack riwayat rute sesi internal (`sessionStorage` atau global store).
   - Jika simpul diakses dari jalur valid, gunakan edge traversal spesifik tersebut.
   - Jika direct entry (cold load), jalankan BFS untuk menemukan jalur terpendek dari root domain aktif ke target entity node.
4. **Step 4: Rendering & Search Indexing**
   - Pohon hasil prunning dikonversi menjadi layout model virtualisasi.
   - Bersamaan dengan itu, simpul-simpul berbobot tinggi dikirimkan ke worker index lokal (e.g., Minisearch / Flexsearch) untuk konsumsi *Command Palette*.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sistem Pengatur Lalu Lintas Udara (Air Traffic Control) Terotomatisasi
Bayangkan navigasi enterprise seperti sistem koridor udara internasional. Pesawat (Pengguna) tidak diizinkan terbang di sembarang koridor udara (Menu Rute). ATC (Navigation Engine) memeriksa secara real-time: Apakah pesawat memiliki izin lintas udara militer/sipil (RBAC/ABAC)? Apakah bandara tujuan sedang aktif dalam lisensi rute (Tenant Feature Flag)? Apakah cuaca memungkinkan pendaratan di hub alternatif (Polihierarki)? ATC tidak mengubah tata letak benua, tetapi merutekan pesawat hanya melalui koridor navigasi yang aman, efisien, dan legal sesuai izin saat itu.

#### Diagram Arsitektur Internal Navigation Engine

```
+---------------------------------------------------------------------------------------+
|                             ENTERPRISE NAVIGATION ENGINE                              |
+---------------------------------------------------------------------------------------+
|  INPUT CONTRACTS                                                                      |
|  +--------------------+   +-----------------------+   +----------------------------+  |
|  | Remote MFE Schemas |   | Security Context      |   | Tenant Subscription Flags  |  |
|  +---------+----------+   +-----------+-----------+   +--------------+-------------+  |
+------------|--------------------------|------------------------------|----------------+
             v                          v                              v
+---------------------------------------------------------------------------------------+
|  GRAPH RESOLVER & COMPILER CORE                                                       |
|                                                                                       |
|   +-----------------------+     Cycle Detection     +------------------------------+  |
|   | Global Graph Compiler | ----------------------> | Directed Acyclic Graph (DAG) |  |
|   +-----------------------+    (Tarjan's Alg.)      +--------------+---------------+  |
|                                                                    |                  |
|                                                                    v                  |
|   +--------------------------------------------------------------------------------+  |
|   | Traversal & Evaluation Engine (Post-Order DFS Pruning)                         |  |
|   | - ABAC Rule Matching                                                           |  |
|   | - Feature Flag Gating                                                          |  |
|   | - Orphan Branch Trimming                                                       |  |
|   +--------------------------------+-----------------------------------------------+  |
+------------------------------------|--------------------------------------------------+
                                     v
+---------------------------------------------------------------------------------------+
|  OUTPUT CACHE & CONSUMERS LAYER                                                       |
|                                                                                       |
|   +------------------------------------+   +--------------------------------------+   |
|   | Active Nav Tree Store (Immutable)  |   | Flat Search Index (O(1) Route Lookup)|   |
|   +-----------------+------------------+   +-------------------+------------------+   |
|                     |                                          |                      |
|         +-----------+-----------+                              |                      |
|         v                       v                              v                      |
|   +-----------+          +--------------+             +------------------+            |
|   | L2/L3 Nav |          |  Breadcrumb  |             | Global Command   |            |
|   | Shell View|          | Dynamic Path |             | Palette (Cmd+K)  |            |
|   +-----------+          +--------------+             +------------------+            |
+---------------------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Algoritma Evaluasi Breadcrumb Polihierarki dengan Deteksi Siklus
Implementasi dasar penelusuran graf untuk menentukan jalur navigasi Breadcrumb valid pada graf berarah.

```typescript
// types/navigation-simple.ts
export interface SimpleRouteNode {
  id: string;
  label: string;
  path: string;
  parents: string[]; // Polyhierarchical: multiple parents
}

export class BreadcrumbResolver {
  private graph: Map<string, SimpleRouteNode> = new Map();

  constructor(nodes: SimpleRouteNode[]) {
    nodes.forEach(node => this.graph.set(node.id, node));
  }

  /**
   * Menemukan Breadcrumb terpendek dari root manapun ke targetId
   * menggunakan Breadth-First Search (BFS) terbalik.
   */
  public resolveShortestPath(targetId: string): SimpleRouteNode[] {
    if (!this.graph.has(targetId)) return [];

    const queue: { currentId: string; path: string[] }[] = [
      { currentId: targetId, path: [targetId] }
    ];
    const visited = new Set<string>();

    while (queue.length > 0) {
      const { currentId, path } = queue.shift()!;
      visited.add(currentId);

      const node = this.graph.get(currentId);
      if (!node) continue;

      // Jika simpul tidak memiliki parent, kita telah mencapai Root
      if (node.parents.length === 0) {
        return path.map(id => this.graph.get(id)!).reverse();
      }

      for (const parentId of node.parents) {
        if (!visited.has(parentId)) {
          queue.push({
            currentId: parentId,
            path: [...path, parentId]
          });
        }
      }
    }

    return [this.graph.get(targetId)!];
  }
}

// Demo Verifikasi Sederhana
const mockNodes: SimpleRouteNode[] = [
  { id: 'root-procure', label: 'Procurement', path: '/procure', parents: [] },
  { id: 'root-finance', label: 'Finance Hub', path: '/finance', parents: [] },
  { id: 'cat-ap', label: 'Accounts Payable', path: '/finance/ap', parents: ['root-finance'] },
  { id: 'doc-invoice', label: 'Vendor Invoice #89', path: '/invoices/89', parents: ['root-procure', 'cat-ap'] }
];

const resolver = new BreadcrumbResolver(mockNodes);
// Expected shortest: root-procure -> doc-invoice (panjang: 2) dibandingkan root-finance -> cat-ap -> doc-invoice (panjang: 3)
console.log(resolver.resolveShortestPath('doc-invoice').map(n => n.label));
// Output: [ 'Procurement', 'Vendor Invoice #89' ]
```

#### B. Practical Example: Production-Ready ABAC Navigation Engine & Command Layer
Implementasi enterprise-grade sistem navigasi dinamis: skema deklaratif, evaluasi context-aware, state machine sinkronisasi, dan integrasi Command Palette.

```typescript
// architecture/navigation-engine.ts
import { z } from 'zod';

// 1. Skema Validasi Node Navigasi Enterprise
export const PolicyRequirementSchema = z.object({
  action: z.string(),
  subject: z.string(),
  conditions: z.record(z.any()).optional()
});

export const NavigationNodeSchema = z.object({
  id: z.string(),
  label: z.string(),
  path: z.string().optional(),
  icon: z.string().optional(),
  parentId: z.string().nullable(),
  requiredPolicy: PolicyRequirementSchema.optional(),
  requiredFeatureFlag: z.string().optional(),
  badgeKey: z.string().optional(),
  order: z.number().default(0),
  children: z.array(z.lazy(() => NavigationNodeSchema)).default([])
});

export type NavigationNode = z.infer<typeof NavigationNodeSchema>;

export interface SecurityContext {
  userId: string;
  tenantId: string;
  roles: string[];
  permissions: Set<string>; // Format: "action:subject"
  features: Set<string>;
}

export interface NavigationTelemetryEvent {
  nodeId: string;
  latencyMs: number;
  unauthorizedPrunedCount: number;
  timestamp: number;
}

// 2. Production Engine Implementation
export class EnterpriseNavigationEngine {
  private rawSchema: NavigationNode[];
  private telemetrySink: (event: NavigationTelemetryEvent) => void;

  constructor(
    schema: NavigationNode[],
    telemetrySink: (event: NavigationTelemetryEvent) => void = () => {}
  ) {
    this.rawSchema = schema;
    this.telemetrySink = telemetrySink;
  }

  /**
   * Memangkas pohon navigasi secara efisien berdasarkan SecurityContext pengguna saat ini.
   * Kompleksitas Waktu: O(V + E) di mana V = jumlah nodes, E = transitions
   */
  public compile(context: SecurityContext): NavigationNode[] {
    const startTime = performance.now();
    let prunedNodesCount = 0;

    const evaluateNode = (node: NavigationNode): NavigationNode | null => {
      // Validasi Feature Flag
      if (node.requiredFeatureFlag && !context.features.has(node.requiredFeatureFlag)) {
        prunedNodesCount++;
        return null;
      }

      // Validasi ABAC Policy
      if (node.requiredPolicy) {
        const policyKey = `${node.requiredPolicy.action}:${node.requiredPolicy.subject}`;
        if (!context.permissions.has(policyKey)) {
          prunedNodesCount++;
          return null;
        }
      }

      // Evaluasi rekursif untuk node anak (Post-Order Traversal)
      const visibleChildren: NavigationNode[] = [];
      for (const child of node.children) {
        const evaluatedChild = evaluateNode(child);
        if (evaluatedChild) {
          visibleChildren.push(evaluatedChild);
        }
      }

      // Urutkan simpul anak berdasarkan atribut order
      visibleChildren.sort((a, b) => a.order - b.order);

      // Branch node tanpa aksi path dan tanpa anak yang terlihat harus di-trim
      if (!node.path && visibleChildren.length === 0) {
        prunedNodesCount++;
        return null;
      }

      return {
        ...node,
        children: visibleChildren
      };
    };

    const compiledTree: NavigationNode[] = [];
    for (const rootNode of this.rawSchema) {
      const evaluatedRoot = evaluateNode(rootNode);
      if (evaluatedRoot) {
        compiledTree.push(evaluatedRoot);
      }
    }

    compiledTree.sort((a, b) => a.order - b.order);

    const endTime = performance.now();
    this.telemetrySink({
      nodeId: 'ROOT_COMPILATION',
      latencyMs: endTime - startTime,
      unauthorizedPrunedCount: prunedNodesCount,
      timestamp: Date.now()
    });

    return compiledTree;
  }

  /**
   * Menghasilkan flat array terindeks untuk Search Command Palette (Cmd + K)
   */
  public generateCommandPaletteIndex(prunedTree: NavigationNode[]): Array<{
    id: string;
    label: string;
    path: string;
    breadcrumbTrace: string;
  }> {
    const results: Array<{ id: string; label: string; path: string; breadcrumbTrace: string }> = [];

    const traverse = (node: NavigationNode, currentBreadcrumb: string[]) => {
      const nextBreadcrumb = [...currentBreadcrumb, node.label];
      
      if (node.path) {
        results.push({
          id: node.id,
          label: node.label,
          path: node.path,
          breadcrumbTrace: nextBreadcrumb.join(' > ')
        });
      }

      for (const child of node.children) {
        traverse(child, nextBreadcrumb);
      }
    };

    prunedTree.forEach(node => traverse(node, []));
    return results;
  }
}

// 3. React UI Integration Component
import React, { createContext, useContext, useMemo, useState, useEffect } from 'react';

interface NavigationContextValue {
  navigationTree: NavigationNode[];
  commandIndex: Array<{ id: string; label: string; path: string; breadcrumbTrace: string }>;
  activeNodeId: string | null;
  setActiveNodeId: (id: string) => void;
}

const NavEngineReactContext = createContext<NavigationContextValue | null>(null);

export const EnterpriseNavProvider: React.FC<{
  rawSchema: NavigationNode[];
  securityContext: SecurityContext;
  children: React.ReactNode;
}> = ({ rawSchema, securityContext, children }) => {
  const [activeNodeId, setActiveNodeId] = useState<string | null>(null);

  const engine = useMemo(() => new EnterpriseNavigationEngine(rawSchema), [rawSchema]);

  const compiledTree = useMemo(() => {
    return engine.compile(securityContext);
  }, [engine, securityContext]);

  const commandIndex = useMemo(() => {
    return engine.generateCommandPaletteIndex(compiledTree);
  }, [engine, compiledTree]);

  return (
    <NavEngineReactContext.Provider
      value={{
        navigationTree: compiledTree,
        commandIndex,
        activeNodeId,
        setActiveNodeId
      }}
    >
      {children}
    </NavEngineReactContext.Provider>
  );
};

export const useEnterpriseNav = () => {
  const ctx = useContext(NavEngineReactContext);
  if (!ctx) throw new Error('useEnterpriseNav must be consumed within EnterpriseNavProvider');
  return ctx;
};
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Global Trade Logistics ERP (Kasus: Freighting & Freight-Forwarding Platform)
* **Skala Sistem**: 12.000 pengguna bersamaan (*concurrent enterprise users*), 60+ modul remote (didistribusikan via Webpack Module Federation), lebih dari 3.800 rute unik, 14 level tenant subscription.
* **Tantangan Arsitektur**:
  1. Operasi rute memuat seluruh metadata navigasi sebesar ~3.4MB JSON saat aplikasi pertama kali dibuka, memicu **First Meaningful Paint (FMP)** buruk (> 4.8 detik pada jaringan terbatas).
  2. Fragmentasi peran: Seorang analis bea cukai (*Customs Broker*) memiliki menu yang sangat berbeda dengan analis audit keuangan (*Financial Auditor*), meskipun keduanya melihat entitas dasar yang sama: *Declaration Cargo Manifest*.
  3. Menu Sidebar standar memiliki kedalaman hingga 6 tingkat nesting yang mengakibatkan operator sering tersesat (*high lostness index* > 0.42).
* **Solusi Arsitektur**:
  1. **Federated Route Catalog**: Setiap modul micro-frontend hanya mendaftarkan sub-graf rutenya sendiri saat remote script di-mount. Host shell menggunakan *Dynamic Tree Stitching* untuk menyatukan segmen.
  2. **Subtree Pruning at Edge Worker**: Logika ABAC ditransfer ke Cloudflare Workers / Next.js Edge Middleware. Metadata navigasi di-prune sebelum payload JSON dikirim ke browser klien. Ukuran transfer berkurang dari 3.4MB menjadi 48KB.
  3. **Contextual Workspace Replacement**: Navigasi hirarkis dalam (L4-L6) dihapus dari persistent sidebar. Persistent sidebar dibatasi hanya 2 level (Domain & Hub). Akses L4-L6 dialihkan ke *Faceted Data Tables* dan *Search Command Palette* berbasis keyboard shortcut.
* **Hasil Metrik**:
  - Reduksi CLS dari 0.28 menjadi 0.002 (Layout shift navigasi sepenuhnya tereliminasi karena tree ukuran tetap).
  - INP meningkat 62% (dari 380ms menjadi 64ms) saat berpindah workspace context.
  - *Task Completion Time* untuk operator lintas-fungsi menurun drastis dari 84 detik menjadi 19 detik via *Command Palette*.

---

### 9. Trade-offs (Performance, Latency, Scalability, Cost)

| Parameter Dimensi | Arsitektur: Dynamic Server/Edge Evaluated | Arsitektur: Client-Side Full Manifest Pruning | Arsitektur: Static Pre-built Route Trees |
| :--- | :--- | :--- | :--- |
| **Performance (Client)** | **Sangat Baik**: Client hanya memproses pohon yang sudah dipangkas (payload minimal). | **Buruk**: Browser memproses algoritma rekursif traversal pada ribuan node JSON besar. | **Sempurna**: Tidak ada overhead traversal runtime di browser. |
| **Latency** | **Sedang**: Membutuhkan eksekusi middleware per request atau session hydration. | **Rendah**: Begitu aset ter-cache, transisi rute instan. | **Ultra-Rendah**: Aset statis dari Edge CDN. |
| **Scalability (Nav Items)** | **Sangat Tinggi**: Mendukung puluhan ribu rute tanpa membebani browser DOM. | **Terbatas**: Bottleneck pada konsumsi memori browser klien. | **Sangat Buruk**: Eksplosif kombinatorial ($2^N$ permutasi role/tenant). |
| **Cost (Infrastructure)** | **Tinggi**: Utilisasi CPU compute pada Edge Workers / SSR Server. | **Sangat Rendah**: Seluruh kalkulasi diserahkan ke perangkat klien (*Zero compute server*). | **Rendah**: Biaya penyimpanan CDN reguler. |
| **Security Surface** | **Tinggi (Aman)**: Rute yang tidak diizinkan tidak pernah sampai ke DOM klien. | **Rentan**: Kode navigasi tersimpan di memory browser (dapat di-inspect via devtools). | **Tinggi (Aman)**: Tetapi sulit memvalidasi dynamic claim runtime. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Masalah: "Ghost Breadcrumbs" pada Akses Deep-Link
* **Gejala**: Pengguna membuka URL langsung (`/billing/invoices/992/adjustments`), namun Breadcrumb hanya menampilkan: `Home > Adjustments`. Konteks parent (`Billing` dan `Invoices`) hilang.
* **Akar Masalah**: Resolusi breadcrumb hanya membaca URL pathname split (`pathname.split('/')`), tanpa memvalidasi struktur relasi parent-child sebenarnya di Navigation Registry.
* **Solusi**: Terapkan *Deterministic Fallback Traversal*. Jika route history kosong (cold load), jalankan penelusuran Breadth-First Search (BFS) dari Navigation Registry untuk membangun rantai parent minimum yang valid.

#### 2. Masalah: O(N²) Performance Trap saat Re-render
* **Gejala**: Ketikan pengguna pada *input text* terasa lag (INP > 300ms) pada halaman dengan menu navigasi yang kompleks.
* **Akar Masalah**: Fungsi filter navigasi (pruning) dieksekusi langsung di dalam render loop komponen React (misal: di-call di root `Sidebar.tsx` tanpa memoization dependensi yang stabil).
* **Solusi**: Memoize hasil kompilasi pohon navigasi menggunakan referensi hash dari identitas konteks keamanan:
  ```typescript
  const contextFingerprint = `${user.id}:${user.role}:${tenant.flagsHash}`;
  const compiledNav = useMemo(() => engine.compile(securityCtx), [contextFingerprint]);
  ```

#### 3. Masalah: Broken Dynamic Links akibat Perubahan State Workspace
* **Gejala**: Link pada menu merujuk pada `/:tenantId/reports`. Saat pengguna berpindah tenant via L1 Workspace Switcher, link tetap mengarah ke tenant sebelumnya.
* **Akar Masalah**: Rute statis di-hardcode saat inisialisasi tanpa interpolasi reaktif variabel lingkungan rute.
* **Solusi**: Gunakan templating interpolasi token (`/workspaces/:tenantSlug/reports`) yang diresolusi secara deterministik menggunakan helper router aktif sebelum link dirender ke elemen `<a>`.

---

### 11. Best Practices (Production Checklist)

#### Security & Access Control
- [ ] Rute sensitif tidak boleh dibocorkan ke client manifest jika hak akses ABAC bernilai `false`.
- [ ] Seluruh evaluasi navigasi di UI bersifat kosmetik (UX guidance); validasi otorisasi final wajib ditegakkan di layer API / Service Boundary.
- [ ] Lakukan sanitasi token parameter rute untuk mencegah injection pada URL template.

#### Accessibility (A11y - WAI-ARIA)
- [ ] Komponen navigasi utama dibungkus elemen semantik `<nav aria-label="Main Navigation">`.
- [ ] Simpul aktif ditandai secara eksplisit dengan atribut `aria-current="page"` (untuk rute) atau `aria-current="location"` (untuk breadcrumb step).
- [ ] Submenu memiliki atribut `aria-expanded="true|false"` dan diikat menggunakan `aria-controls="submenu-id"`.
- [ ] Dukungan navigasi keyboard penuh: `ArrowDown`/`ArrowUp` untuk traversi item, `ArrowRight`/`ArrowLeft` untuk buka/tutup hierarki, dan `Escape` untuk menutup drawer/palette.

#### UX Performance & Layout Stability
- [ ] Alokasikan skeleton layout atau reservasi fixed-width bounding box untuk sidebar guna mencegah Cumulative Layout Shift (CLS < 0.05).
- [ ] Command Palette (`Cmd+K`) di-load menggunakan *Dynamic Code Splitting* (Lazy Loading) sehingga tidak memperbesar ukuran Initial JavaScript Bundle.
- [ ] Batasi kedalaman visual navigasi sidebar hingga maksimal 2-3 level. Alihkan hierarki yang lebih dalam ke navigasi in-page (Tabs, Segmented Controls, atau Facets).

---

### 12. Hands-on Practice

Buatlah implementasi engine navigasi kontekstual enterprise pada direktori kerja:
`hands-on/m02/`

#### Struktur Proyek:
```
hands-on/m02/
├── src/
│   ├── contracts/
│   │   └── navigation.contract.ts
│   ├── engine/
│   │   ├── NavigationGraph.ts
│   │   └── BreadcrumbEngine.ts
│   ├── components/
│   │   ├── EnterpriseSidebar.tsx
│   │   ├── DynamicBreadcrumbs.tsx
│   │   └── CommandPaletteModal.tsx
│   └── index.ts
├── tests/
│   └── engine.test.ts
├── tsconfig.json
└── package.json
```

#### Langkah Pengerjaan:

1. **Inisialisasi Proyek**:
   ```bash
   mkdir -p hands-on/m02 && cd hands-on/m02
   npm init -y
   npm install typescript zod react react-dom lucide-react
   npm install -D @types/react @types/react-dom vitest
   npx tsc --init
   ```

2. **Buat Kontrak Data Navigasi** (`src/contracts/navigation.contract.ts`):
   Definisikan interface rute yang mewajibkan penulisan permission rules, feature flags, order weight, dan dukungan multi-parent (DAG).

3. **Implementasikan Core Engine** (`src/engine/NavigationGraph.ts`):
   - Tulis class `NavigationGraph` yang memiliki method `registerNodes(nodes: NavigationNode[])`.
   - Implementasikan method `compileTree(ctx: SecurityContext): NavigationNode[]` yang mengeksekusi Post-Order Traversal untuk memangkas simpul yang tidak sah (*unauthorized leaves and empty branches*).

4. **Implementasikan Breadcrumb Path Engine** (`src/engine/BreadcrumbEngine.ts`):
   - Bangun algoritma BFS untuk menghitung jalur terpendek dari root ke target route identifier dengan penanganan fallback otomatis saat cold load.

5. **Unit Testing** (`tests/engine.test.ts`):
   Tulis pengujian otomatis untuk memvalidasi:
   - Simpul tanpa permission yang sesuai harus terhapus dari pohon.
   - Folder/Parent yang seluruh anaknya terhapus harus otomatis ikut terhapus.
   - Breadcrumb menghasilkan representasi jalur yang benar dari skenario deep-link.

6. **Jalankan Pengujian**:
   ```bash
   npx vitest run
   ```

---

### 13. Exercise

#### Level Easy
Ubah struktur array navigasi linier berikut menjadi pohon hirarkis yang valid secara tipe data (`NavigationNode[]`):
```typescript
const flatRoutes = [
  { id: '1', parentId: null, label: 'Dashboard', path: '/dashboard' },
  { id: '2', parentId: '1', label: 'Analytics', path: '/dashboard/analytics' },
  { id: '3', parentId: null, label: 'Settings', path: '/settings' }
];
```
*Tugas*: Buat fungsi rekursif `buildHierarchicalTree(flatList)` dengan performa $O(N)$.

#### Level Medium
Sebuah node navigasi memiliki konfigurasi conditional visibility dinamis:
```typescript
condition: (ctx: SecurityContext) => boolean;
```
Perluas `EnterpriseNavigationEngine` agar mampu mengeksekusi kondisi fungsi predikat tersebut pada runtime dengan aman (termasuk *error handling* jika predikat melempar exception) tanpa merusak sisa pohon navigasi lainnya.

#### Level Hard
Buat implementasi *Stateful Navigation Engine* yang menangani **Multi-tenant Workspace Context Switcher**.
- Sistem memiliki 3 Tenant: *Tenant A (Enterprise Tier)*, *Tenant B (Starter Tier)*, dan *Tenant C (Suspended)*.
- Ketika Context beralih antar tenant:
  1. Engine harus me-recompile graf rute secara sinkron.
  2. Jika pengguna berada di halaman yang *tidak valid* di tenant baru, engine harus menghasilkan redirection path fallback terdekat (*nearest ancestor safe route*) secara otomatis, bukan melempar 404/403.

---

### 14. Challenge

#### Skenario Kasus Kompleks: High-Frequency FinTech Trading Terminal
Anda bertindak sebagai Lead Frontend Architect untuk platform perdagangan aset multi-pasar. Aplikasi ini memuat 10.000 instrumen finansial dinamis yang diatur ke dalam puluhan kategori pasar (Forex, Komoditas, Ekuitas, Derivatif, Kripto). 

Navigasi konvensional berbasis DOM pohon tidak mampu merender 10.000 instrumen tanpa menyebabkan frame drop parah (FPS anjlok di bawah 20 FPS). Selain itu:
1. Operator institusional menolak navigasi klik bertingkat dan hanya mengandalkan kombinasi keyboard (*power-user shortcut workflows*).
2. Setiap instrumen keuangan memiliki status kelayakan perdagangan (*trading eligibility*) yang berubah secara dinamis setiap beberapa detik via stream WebSocket (misal: instrumen disuspen oleh bursa).
3. Anda diminta untuk merancang dan membangun arsitektur **Zero-DOM-Weight Ambient Navigation Engine**:
   - Seluruh simpul hierarki dan instrumen disimpan dalam struktur *In-Memory Tries / Inverted Graph*.
   - Navigasi utama digantikan oleh *Faceted Virtualized Command Palette* yang mampu mencari secara instan ($< 10\text{ms}$) di antara 10.000 simpul dengan pencarian fuzzy.
   - Ketika notifikasi WebSocket masuk yang menyatakan suatu aset disuspen atau hak akses pengguna dicabut, rute instrumen tersebut langsung dipangkas dari search graph secara reaktif dalam waktu kurang dari 50 milidetik tanpa me-rebuild seluruh graf dari awal (*Incremental Differential Invalidation*).

*Deliverable Arsitektur*: Desain rancangan arsitektur data, diagram state transitions, dan implementasi algoritma *Differential Cache Invalidation* pada engine navigasi tersebut.

---

### 15. Quiz Evaluasi Pemahaman

#### 5 Pertanyaan Basic
1. Mengapa struktur navigasi Monohierarki murni (pohon tunggal) sering kali gagal memenuhi kebutuhan sistem enterprise berskala besar?
   - A. Karena monohierarki tidak mendukung rendering CSS flexbox.
   - B. Karena satu entitas bisnis sering kali perlu diklasifikasikan ke dalam lebih dari satu domain bisnis (polihierarki).
   - C. Karena format data JSON tidak mendukung pembacaan array bersarang.
   - D. Karena performa browser modern dibatasi hanya pada 3 tingkat hierarki URL.
   *Kunci*: **B**.

2. Apa fungsi dari traversal *Post-Order DFS* pada proses pruning pohon navigasi?
   - A. Menghitung jumlah klik pengguna pada menu navigasi.
   - B. Mengevaluasi simpul daun (leaves) terlebih dahulu sehingga cabang kosong dapat dipangkas secara otomatis jika seluruh anaknya tidak lolos otorisasi.
   - C. Mengurutkan menu berdasarkan abjad A-Z.
   - D. Menghubungkan WebSocket ke server otentikasi.
   *Kunci*: **B**.

3. Atribut WAI-ARIA manakah yang wajib disematkan pada link navigasi aktif saat ini untuk memenuhi standar aksesibilitas?
   - A. `aria-selected="true"`
   - B. `aria-current="page"`
   - C. `aria-active="true"`
   - D. `aria-live="polite"`
   *Kunci*: **B**.

4. Apa dampak negatif terhadap performa web jika manifest navigasi lengkap dievaluasi ulang (re-pruned) langsung di dalam render loop komponen tanpa memoization?
   - A. Terjadinya memory leak pada browser database.
   - B. Degradasi nilai metrik Interaction to Next Paint (INP) dan UI lagging.
   - C. Kegagalan loading file manifest eksternal.
   - D. Penurunan kecepatan unduh file statis CSS.
   *Kunci*: **B**.

5. Kapan sebaiknya sebuah rute navigasi di-resolve menggunakan *Shortest Path Algorithm* (BFS) daripada pembacaan *Session History*?
   - A. Saat pengguna melakukan refresh halaman berkali-kali.
   - B. Saat pengguna mengakses halaman melalui Deep Link langsung atau jendela tab baru (Cold Load).
   - C. Saat pengguna menggunakan mouse gaming beresolusi tinggi.
   - D. Saat aplikasi berjalan di lingkungan offline.
   *Kunci*: **B**.

---

#### 5 Pertanyaan Intermediate
6. Dalam implementasi navigasi berbasis Micro-frontend dengan Module Federation, strategi mana yang paling tepat untuk mencegah konflik rute antar modul independen?
   - A. Mengizinkan setiap MFE memodifikasi `window.location` secara bebas.
   - B. Menggunakan Root Navigation Contract Registry di mana setiap MFE memublikasikan sub-graf dengan prefix namespace yang terisolasi.
   - C. Menghindari penggunaan routing pada MFE dan menggunakan tab berbasis modal.
   - D. Menggabungkan seluruh kode JavaScript rute ke dalam satu file bundle monolith di awal.
   *Kunci*: **B**.

7. Bagaimana cara terbaik mengelola otorisasi berbasis hak akses (ABAC) pada sistem navigasi tanpa membocorkan rute rahasia perusahaan ke pengguna umum?
   - A. Menyembunyikan menu menggunakan properti CSS `display: none`.
   - B. Mengirimkan seluruh rute ke browser lalu mengunci rute dengan prompt kata sandi.
   - C. Melakukan kompilasi dan pemangkasan (pruning) struktur navigasi di layer Edge/Server sebelum dikirim ke browser klien.
   - D. Melakukan enkripsi Base64 pada label menu di sisi browser.
   *Kunci*: **C**.

8. Konsep *Lostness Metric* ($L$) pada pengujian Arsitektur Informasi diukur dengan formula:
   $$L = \sqrt{\left(\frac{N}{S} - 1\right)^2 + \left(\frac{R}{N} - 1\right)^2}$$
   Jika nilai $L > 0.4$, apa interpretasi UX yang paling tepat?
   - A. Struktur navigasi sangat intuitif dan efisien.
   - B. Pengguna mengalami disorientasi parah dan mengambil jalur navigasi yang berbelit-belit untuk menyelesaikan tugas.
   - C. Waktu render navigasi melampaui batas toleransi 60fps.
   - D. Aplikasi mengalami layout shift (CLS tinggi).
   *Kunci*: **B**.

9. Mengapa pendekatan "Mega Menu" 4 tingkat sering kali meningkatkan *Cognitive Load* secara drastis menurut Hukum Hick?
   - A. Karena mata manusia tidak dapat membaca tulisan berukuran kecil.
   - B. Karena waktu yang dibutuhkan untuk mengambil keputusan meningkat secara logaritmik seiring bertambahnya jumlah opsi pilihan yang ditampilkan secara serentak.
   - C. Karena browser membutuhkan lebih banyak memori GPU untuk me-render dropdown.
   - D. Karena resolusi layar monitor modern tidak mendukung rasio 4:3.
   *Kunci*: **B**.

10. Apa kegunaan utama mengintegrasikan *Command Palette* (`Cmd+K`) di samping menu navigasi konvensional pada aplikasi enterprise?
    - A. Mengurangi biaya bandwidth CDN.
    - B. Menyediakan jalur navigasi non-hierarkis (Shortcut/Direct Access) bagi *power users* untuk memintas navigasi bersarang yang dalam.
    - C. Menggantikan seluruh tombol form dan input dalam aplikasi.
    - D. Menghindari implementasi otorisasi peran pengguna.
    *Kunci*: **B**.

---

#### 3 Skenario Kasus Produksi
11. **Skenario Kasus A**: 
    Sebuah aplikasi perbankan enterprise mengalami keluhan dari auditor keamanan. Saat seorang teller biasa membuka DevTools di browser, ia dapat melihat daftar link menu internal seperti `/admin/super-user/adjust-balance` di dalam state global Redux, meskipun tombol menu fisik di sidebar tidak dirender. Apa cacat arsitektur utama di sini dan bagaimana mitigasi yang benar?
    *Solusi & Analisis Kasus*:
    - **Cacat Arsitektur**: Otorisasi hanya ditegakkan di layer *View Presentation* (Client UI Hiding), bukan pada level *Data/Manifest Compilation Engine*. Seluruh graf navigasi bocor ke memory client state.
    - **Mitigasi**: Pindahkan proses pruning navigasi ke Server/BFF (Backend-For-Frontend) atau Edge Middleware. Browser teller hanya boleh menerima payload JSON yang *sudah dipangkas bersih* sesuai klaim izin teller saat otentikasi. State internal klien tidak boleh memuat metadata simpul rute di luar otorisasi pengguna.

12. **Skenario Kasus B**: 
    Aplikasi Multi-Tenant Supply Chain memiliki 500 rute. Operator gudang melaporkan bahwa setiap kali mereka mengklik link menu di Sidebar, terjadi kedipan visual (*flicker/jitter*) dan posisi scroll sidebar kembali melonjak ke paling atas. Inspeksi performa menunjukkan CLS bernilai 0.31 saat navigasi dieksekusi. Apa penyebabnya dan bagaimana rancangan perbaikannya?
    *Solusi & Analisis Kasus*:
    - **Penyebab**: Setiap perpindahan rute me-remount seluruh layout shell sidebar dari nol (ketiadaan Persistent Layout). State scroll tree tidak dipertahankan (*unpreserved scroll state*), dan skeleton width dinamis memicu pergeseran layout kontainer utama.
    - **Rancangan Perbaikan**:
      1. Terapkan pola *Nested Persistent Layouts* (misal: `layout.tsx` pada Next.js App Router).
      2. Ikat state ekspansi menu dan posisi scroll ke storage lokal atau context terisolasi yang tidak me-reset saat path anak berganti.
      3. Tetapkan dimensi *width* kontainer navigasi secara permanen menggunakan CSS custom properties dan CSS `contain: layout style`.

13. **Skenario Kasus C**: 
    Platform analytics skala enterprise menggunakan Module Federation. Modul remote *Billing* memublikasikan rute baru `/finance/invoices`. Namun saat modul remote *Billing* mengalami network failure (500 internal server error saat loading bundle JS remote), seluruh navigasi global aplikasi crash dan menampilkan *White Screen of Death*. Bagaimana memodifikasi arsitektur Navigation Registry untuk menangani insiden ini?
    *Solusi & Analisis Kasus*:
    - **Penyebab**: Tightly coupled dependency. Host shell mem-parsing rute remote secara sinkron tanpa isolasi kegagalan (*fault isolation boundary*).
    - **Rancangan Perbaikan**:
      1. Terapkan pola **Asynchronous Manifest Registry with Fallback & Circuit Breaker**.
      2. Bungkus proses ingestion schema dari modul remote dalam blok *try-catch / safe-contract parser*.
      3. Jika modul remote *Billing* gagal di-fetch, Registry menandai simpul tersebut sebagai *Degraded State*, secara anggun (*gracefully*) menghapus sub-graf rute tersebut dari pohon navigasi aktif, dan menyajikan UI fallback pada kontainer tanpa merusak pohon navigasi modul remote lainnya.

---

### 16. Summary

1. **Polihierarki vs Monohierarki**: Navigasi enterprise modern menuntut representasi Arsitektur Informasi berbasis *Directed Acyclic Graph* (DAG), bukan pohon monohierarki tunggal, guna mengakomodasi akses entitas bisnis dari berbagai sudut pandang domain fungsional.
2. **Deterministic Pruning**: Evaluasi visibilitas menu harus dijalankan melalui *pruning pipeline* terpusat (memanfaatkan Post-Order DFS) berdasarkan ABAC, feature flags, dan relasi dependensi, bukan logika kondisional ad-hoc di komponen visual.
3. **Decoupled Architecture**: Memisahkan navigasi menjadi 4 layer (Global Workspace, Domain Hub, Contextual Workspace, dan Command Palette) mencegah navigation bloat, menurunkan cognitive load, serta mempertahankan efisiensi navigasi bagi pengguna kasual maupun power users.
4. **Resilience & Performance**: Desain navigasi kelas produksi wajib menerapkan *fault isolation* pada micro-frontends, memoization kompilasi pohon untuk menjaga performa INP, serta isolasi visual layout guna mempertahankan nilai Cumulative Layout Shift (CLS) yang stabil.