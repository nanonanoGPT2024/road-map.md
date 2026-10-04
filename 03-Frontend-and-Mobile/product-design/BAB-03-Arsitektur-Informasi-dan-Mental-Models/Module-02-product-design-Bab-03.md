# BAB 03: Arsitektur Informasi dan Mental Models
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. **Merancang & Mengimplementasikan Navigation Engine Skala Enterprise**: Membangun mesin navigasi berbasis graf terarah (*Directed Acyclic Graph* / DAG) yang mendukung multi-taksonomi, *permission-based pruning*, dan *dynamic breadcrumb generation*.
2. **Menjembatani Tiga Model Mental (Alan Cooper’s Triad)**: Mengonversi ketidakcocokan antara *Implementation Model* (struktur database/API backend) dan *User Mental Model* ke dalam *Manifest Model* (antarmuka representasional frontend) yang konsisten.
3. **Mengarsitekturi State-Driven Faceted Search & Taxonomy Routing**: Mengembangkan arsitektur URL-as-State untuk ruang informasi berdimensi tinggi menggunakan state machine deterministik, lengkap dengan normalisasi URL dan *canonical mapping*.
4. **Mengintegrasikan Semantic IA Engine**: Mengotomatisasi penanaman *Structured Data* (JSON-LD) berdasarkan pohon arsitektur informasi untuk optimasi *Search Engine Crawlers* dan *Assistive Technology* (ARIA Treeview/Breadcrumb 1.2 compliant).
5. **Mengukur & Mendiagnosis Kualitas IA**: Mengimplementasikan telemetri pohon navigasi (*Lostness Metric*, *Path Deviation Ratio*) langsung dari instrumentation frontend ke data lake.

---

### 2. Prerequisite

Sebelum mendalami modul ini, Anda wajib memahami:
*   **TypeScript Tingkat Lanjut**: Generics, Discriminated Unions, Recursive Type Definitions, Indexed Access Types.
*   **Frontend State Architecture**: Mental model *URL-as-Single-Source-of-Truth*, Web History API, Serialization/Deserialization parameter pencarian.
*   **Dasar Arsitektur Informasi**: Card Sorting, Tree Testing, Controlled Vocabularies, serta dasar Hierarki Visual dan Desain Interaksi.
*   **Graph Data Structures**: Traversal algoritma Depth-First Search (DFS) dan Breadth-First Search (BFS).

---

### 3. Concept & Internal Architecture

Arsitektur Informasi (*Information Architecture* / IA) modern bukan sekadar pembuatan sitemap atau navigasi menu dropdown bertingkat. Pada tingkat enterprise, IA adalah jembatan struktural antara sistem komputasi terdistribusi dan model kognitif manusia.

```
+-----------------------------------------------------------------------+
|                       ALAN COOPER'S MENTAL MODELS                     |
|                                                                       |
|  [ Implementation Model ]             [ User's Mental Model ]         |
|  Bagaimana software sebenarnya        Bagaimana pengguna membayangkan |
|  bekerja (DB tables, Redis,           cara kerja sistem (Konsep,      |
|  Microservices, Foreign Keys)         Ekspektasi, Alur Alami)         |
|              \                               /                        |
|               \                             /                         |
|                v                           v                          |
|             +---------------------------------+                       |
|             |      [ Manifest Model ]         |                       |
|             |   Bagaimana aplikasi menyajikan |                       |
|             |   struktur informasi kepada     |                       |
|             |   pengguna (UI, IA, Navigasi)   |                       |
|             +---------------------------------+                       |
+-----------------------------------------------------------------------+
```

#### Taksonomi vs Ontologi vs Folksonomi
Pada sistem berskala besar, struktur informasi dipecah menjadi tiga lapisan semantik:
1. **Taxonomy (Hierarki Kaku)**: Struktur relasi `is-a` (misalnya: *Laptop* adalah *Komputer*). Direpresentasikan sebagai pohon strictly-typed.
2. **Ontology (Relasi Multi-Dimensi)**: Relasi semantik lintas domain seperti `depends-on`, `compatible-with`, atau `purchased-together`. Direpresentasikan sebagai *Graph/DAG*.
3. **Folksonomy (Klasifikasi Bebas)**: Penandaan (*tagging*) berbasis perilaku pengguna yang bersifat bottom-up dan nondeterministik.

#### URL-as-State Information Space
Setiap rute antarmuka pengguna merepresentasikan koordinat unik dalam ruang informasi multi-dimensi. Pendekatan primitif menyimpan state filter atau posisi taksonomi di memori lokal React/Vue, menyebabkan inkonsistensi saat halaman di-refresh, dibagikan (*deep linking*), atau di-crawl oleh search engine. Arsitektur enterprise mengadopsi prinsip:

$$\text{Representation} = f(\text{URL Coordinates}, \text{Permission Context}, \text{User Schema})$$

Setiap perubahan taksonomi atau filter facet memicu determinasi state baru melalui URL Serialization Engine yang termutasi secara sinkron dengan *History State Stack*.

---

### 4. Why & What

| Dimensi | Pendekatan Naif (Menu Biasa) | Pendekatan Enterprise IA Engine |
| :--- | :--- | :--- |
| **Ketergantungan Struktur** | Hardcoded di JSX/Komponen layout. | Dynamic Graph AST (*Abstract Syntax Tree*) via Schema Registry. |
| **Penskalaan Menu** | O(N) penambahan komponen manual; rawan layout breakage. | O(1) berbasis registrasi node; konfigurasi berbasis metadata. |
| **Multi-Tenancy & Auth** | Menyembunyikan elemen via CSS (`display: none`). | Pruning pohon secara rekursif pada runtime compiler sebelum render. |
| **State Deep Linking** | Filter dan breadcrumb terisolasi di komponen lokal. | URL-driven State Machine; breadcrumb diturunkan secara deterministik. |
| **SEO & Aksesibilitas** | Terfragmentasi; tag `<a>` polos tanpa meta semantik. | Otomasi ARIA hierarchical roles & JSON-LD BreadcrumbList injection. |

#### Menghindari Jebakan Hukum Conway (Conway's Law)
Kesalahan fatal dalam enterprise product design adalah memproyeksikan struktur departemen internal atau tabel basis data langsung ke menu aplikasi (*Implementation Model Leaks*). Contoh: Backend membagi data menjadi `tbl_billing_v2`, `tbl_subscriptions`, dan `tbl_invoices`. Jika antarmuka menyajikan tiga menu berbeda secara mentah, beban kognitif pengguna (*cognitive friction*) meningkat drastis. IA Engine bertindak sebagai *Adapter Pattern* yang mentransformasikan data relational tersebut ke dalam model mental pengguna: **"Keuangan & Tagihan"**.

---

### 5. How (Workflow Detail)

Alur kerja perancangan hingga implementasi pohon navigasi skala enterprise:

```
[ Phase 1: Cognitive Discovery ]
  Card Sorting (Open/Closed) -> Treejack Telemetry Analysis -> Affinity Diagramming
         |
         v
[ Phase 2: Structural Modeling ]
  Definisikan Taxonomy & Ontology Schema (TypeScript Type-safe DTOs)
         |
         v
[ Phase 3: Manifest Engine Compilation ]
  Input: Master Taxonomy Graph + User Permission Matrix + Feature Flags
  Process: DFS Traversal -> Subtree Pruning -> Active Path Resolution
         |
         v
[ Phase 4: Route & State Synchronization ]
  Sinkronisasi Bidireksional: URL Search Params <-> Facet Engine State
         |
         v
[ Phase 5: Semantic & Accessible Rendering ]
  Generasi Komponen UI + Injeksi ARIA Tree Attributes + Injeksi JSON-LD
```

1. **Cognitive Discovery**: Ekstraksi model mental pengguna melalui metrik *Tree Testing* kuantitatif (keberhasilan tugas, durasi, *directness ratio*).
2. **Structural Modeling**: Definisi tipe kontrak data navigasi yang mendukung relasi rekursif, metadata lokal, dan hak akses.
3. **Graph Pruning**: Node yang tidak dapat diakses oleh sesi pengguna aktif langsung dibuang (*pruned*) dari *in-memory navigation tree* untuk mencegah kebocoran informasi (*data reconnaissance*).
4. **State-URL Bi-directional Binding**: Setiap state facet dipetakan secara deterministik ke dalam URL menggunakan schema validator (misal: Zod) guna menghindari *malformed search vectors*.
5. **DOM Generation**: Komponen navigasi dirender mengikuti pola desain WAI-ARIA Authoring Practices (APG) untuk Treeview dan Breadcrumbs.

---

### 6. Analogy & Diagram ASCII

Bayangkan sebuah Supermarket Fisik (Model Mental) vs Gudang Logistik Otomatis (Model Implementasi):
*   **Gudang Logistik (Backend Database)**: Barang disimpan berdasarkan dimensi kardus, barcode batch, dan rak robotik efisiensi ruang (misal: Sabun cuci diletakkan di samping Baterai Mobil karena ukurannya pas di palet A-42).
*   **Supermarket Fisik (Representational / Manifest Model)**: Pelanggan tidak peduli palet A-42. Pelanggan mencari "Kebutuhan Rumah Tangga" -> "Deterjen & Pembersih".
*   **Arsitektur Informasi**: Denah dan papan petunjuk jalan supermarket yang menata ulang barang-barang dari gudang agar cocok dengan intuisi spasial belanja manusia.

#### Arsitektur Graf Navigasi & Pruning Engine

```
                       [Root: Enterprise Console]
                                   |
         +-------------------------+-------------------------+
         |                                                   |
   [Catalog Domain]                                    [Billing Domain]
     (Role: Any)                                      (Role: Finance_Admin)
         |                                                   |
    +----+----+                                         +----+----+
    |         |                                         |         |
[Products] [Categories]                             [Invoices] [Tax Reports]
    |         |                                         |         |
    |         +--> (Requires 'CATALOG_WRITE')           x         x  <-- [Pruned if]
    |                  |                                                 [Role !=  ]
    |                  v                                                 [Finance  ]
    +--------> [Dynamic Facet Engine]
                     |
       +-------------+-------------+
       |             |             |
   {Category}     {Price}       {Status}
       v             v             v
       -----------------------------
       URL: /catalog?cat=42&price=0-100&status=active
```

---

### 7. Simple Example & Practical Example

#### Simple Example: Recursive Navigation Type Definition
Definisi tipe data rekursif yang menjamin integritas tipe pada struktur arsitektur informasi:

```typescript
export type PermissionKey = 'VIEW_CATALOG' | 'MANAGE_PRODUCTS' | 'VIEW_BILLING';

export interface BaseNavigationNode {
  id: string;
  title: string;
  slug: string;
  requiredPermissions?: PermissionKey[];
  isExternal?: boolean;
}

export interface InternalLeafNode extends BaseNavigationNode {
  type: 'LEAF';
  route: string;
}

export interface InternalBranchNode extends BaseNavigationNode {
  type: 'BRANCH';
  children: NavigationNode[];
}

export type NavigationNode = InternalLeafNode | InternalBranchNode;
```

#### Practical Example: Production-Grade IA Engine with Faceted Search & Dynamic Breadcrumbs

Berikut adalah implementasi arsitektur navigasi lengkap: DFS Traversal Engine, dynamic breadcrumb resolver, permission pruning, dan dynamic faceted state synchronization.

```typescript
// ia-engine.ts
import { z } from 'zod';

// ==========================================
// 1. DATA CONTRACTS & TYPE DEFINITIONS
// ==========================================
export type Role = 'ANALYST' | 'PRODUCT_MANAGER' | 'SUPER_ADMIN';

export interface NavigationNode {
  id: string;
  label: string;
  path: string;
  rolesRequired: Role[];
  children?: NavigationNode[];
  meta?: {
    icon?: string;
    badgeCount?: number;
    seoDescription?: string;
  };
}

export interface BreadcrumbItem {
  label: string;
  path: string;
  isCurrent: boolean;
}

// Schema URL State Facet menggunakan Zod untuk validasi deterministik
export const FacetQuerySchema = z.object({
  category: z.string().optional().default('all'),
  tags: z.preprocess((val) => (typeof val === 'string' ? val.split(',') : []), z.array(z.string())),
  page: z.coerce.number().min(1).default(1),
  sort: z.enum(['asc', 'desc', 'relevance']).default('relevance'),
});

export type FacetQueryState = z.infer<typeof FacetQuerySchema>;

// ==========================================
// 2. IA CORE ENGINE (DFS & PERMISSION PRUNING)
// ==========================================
export class InformationArchitectureEngine {
  constructor(private readonly masterHierarchy: NavigationNode[]) {}

  /**
   * Menghapus seluruh sub-tree cabang jika user tidak memiliki role yang diizinkan.
   * Dijalankan secara rekursif berbasis Pure Function (Immutability).
   */
  public pruneByRole(userRoles: Role[], nodes: NavigationNode[] = this.masterHierarchy): NavigationNode[] {
    return nodes
      .filter((node) => {
        if (node.rolesRequired.length === 0) return true;
        return node.rolesRequired.some((r) => userRoles.includes(r));
      })
      .map((node) => {
        if (!node.children || node.children.length === 0) {
          return { ...node };
        }
        return {
          ...node,
          children: this.pruneByRole(userRoles, node.children),
        };
      });
  }

  /**
   * Menemukan Breadcrumb Trail secara dinamis menggunakan Depth-First Search.
   * Mengembalikan rute linier dari root menuju node aktif.
   */
  public resolveBreadcrumbs(
    targetPath: string,
    nodes: NavigationNode[] = this.masterHierarchy,
    currentTrail: BreadcrumbItem[] = []
  ): BreadcrumbItem[] | null {
    for (const node of nodes) {
      const nextTrail = [
        ...currentTrail,
        {
          label: node.label,
          path: node.path,
          isCurrent: node.path === targetPath,
        },
      ];

      if (node.path === targetPath) {
        return nextTrail;
      }

      if (node.children && node.children.length > 0) {
        const found = this.resolveBreadcrumbs(targetPath, node.children, nextTrail);
        if (found) return found;
      }
    }
    return null;
  }

  /**
   * Menghasilkan Schema.org JSON-LD BreadcrumbList secara otomatis
   * untuk optimasi Search Engine & Semantic Web.
   */
  public generateJsonLdBreadcrumbs(trail: BreadcrumbItem[], baseUrl: string): string {
    const structuredData = {
      '@context': 'https://schema.org',
      '@type': 'BreadcrumbList',
      itemListElement: trail.map((item, index) => ({
        '@type': 'ListItem',
        position: index + 1,
        name: item.label,
        item: `${baseUrl}${item.path}`,
      })),
    };

    return JSON.stringify(structuredData);
  }
}

// ==========================================
// 3. FACETED ROUTING SERIALIZER
// ==========================================
export class FacetedStateRouter {
  public static parse(searchParams: URLSearchParams): FacetQueryState {
    const rawParams = {
      category: searchParams.get('category') ?? undefined,
      tags: searchParams.get('tags') ?? undefined,
      page: searchParams.get('page') ?? undefined,
      sort: searchParams.get('sort') ?? undefined,
    };

    return FacetQuerySchema.parse(rawParams);
  }

  public static serialize(state: Partial<FacetQueryState>): string {
    const params = new URLSearchParams();

    if (state.category && state.category !== 'all') {
      params.set('category', state.category);
    }
    if (state.tags && state.tags.length > 0) {
      params.set('tags', state.tags.join(','));
    }
    if (state.page && state.page > 1) {
      params.set('page', state.page.toString());
    }
    if (state.sort && state.sort !== 'relevance') {
      params.set('sort', state.sort);
    }

    const qs = params.toString();
    return qs ? `?${qs}` : '';
  }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Transisi Arsitektur Taksonomi Global Cloud Commerce (Studi Kasus 100K SKU)
Sebuah platform e-commerce supply chain B2B multinasional memiliki katalog dengan 12 tingkat kedalaman kategori dan 100.000 jenis produk. Masalah yang dihadapi:
*   **Conway’s Law Trap**: Navigasi frontend mencerminkan 18 unit bisnis pergudangan internal, mengakibatkan pembeli kesulitan mencari produk cross-category.
*   **Lostness Metric Tinggi**: Skor *lostness* pengguna saat mencari spare part mencapai $L = 0.68$ (ideal: $L \le 0.4$).
*   **Performance Degraded**: Mengirimkan seluruh pohon hierarki berukuran 8.4 MB ke browser pengguna menyebabkan *Total Blocking Time* (TBT) melebihi 1.200 ms.

```
Lostness Metric Formula:
L = sqrt( (N / S - 1)^2 + (R / N - 1)^2 )
Di mana:
N = Jumlah halaman unik yang dikunjungi
S = Jumlah halaman minimum absolut untuk menyelesaikan tugas
R = Total seluruh navigasi/halaman yang dibuka
```

#### Solusi Arsitektural yang Diterapkan:
1. **Pemisahan Model Mental**: Menetapkan representasi kanonikal baru dengan kedalaman taksonomi maksimal 3 level untuk menu navigasi utama (*Broad Tree Architecture*), sedangkan 9 level sisanya dialihkan ke dalam *Faceted Search Dynamic Engine*.
2. **Dynamic Subtree Code-Splitting**: Membagi master taxonomy tree ke dalam micro-manifest per domain. Root layout hanya memuat Level 1 dan 2 (berukuran ~14 KB). Level berikutnya di-load secara *just-in-time* (JIT) via streaming SSR saat pengguna mengarahkan kursor (*hover/focus*) ke cabang tertentu.
3. **State Normalization**: Pembuatan URL Canonical Deterministic Router yang secara otomatis mengalihkan kombinasi filter duplikat menjadi satu URL kanonikal, menjaga integritas SEO dan cache browser.

#### Hasil:
*   Skor Lostness turun dari $0.68$ menjadi $0.21$.
*   Ukuran payload awal navigasi terpangkas $98.3\%$ (dari 8.4 MB menjadi 140 KB terkompresi).
*   *Task Completion Rate* melonjak sebesar $34.6\%$.

---

### 9. Trade-offs

| Pendekatan Arsitektur | Keuntungan | Biaya / Kerugian | Rekomendasi Penggunaan |
| :--- | :--- | :--- | :--- |
| **Deep Tree Hierarchy** (Kedalaman $\ge 6$, Lebar Rendah) | Menu awal terlihat bersih, ringkas, dan tidak mengintimidasi. | *High Cognitive Friction*, klik bertingkat tinggi, risiko tersesat (*high lostness*). | Sistem arsip murni, dokumen legal, sistem manajemen file. |
| **Broad Tree Hierarchy** (Kedalaman $\le 3$, Lebar Tinggi) | *High Discoverability*, jumlah klik ke target sangat sedikit. | *Visual Noise*, risiko *choice overload* (Hick's Law), UI mega-menu padat. | Enterprise SaaS Dashboards, Katalog E-Commerce B2B. |
| **Dynamic Faceted Navigation** | Sangat fleksibel, mampu menangani multi-dimensi informasi. | Risiko *State Explosion*, *infinite crawl trap* untuk web crawler, kompleksitas URL routing. | Toko online modern, direktori lowongan kerja, repositori modul internal. |
| **Client-side Tree Computation** | Interaksi instan (0ms latency), tidak ada loading state saat buka menu. | Memory footprint browser tinggi, Initial Bundle Size membengkak. | Aplikasi offline-first, Electron desktop apps, dashboard internal kecil. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. The Cyclic Graph Trap in Breadcrumbs
*   **Masalah**: Kategori memiliki relasi banyak-ke-banyak (*many-to-many*). Misal: "Monitor Gaming" berada di bawah "Komputer" DAN di bawah "Peralatan Gaming". Terjadi infinite recursion stack overflow saat traversal DFS membangkitkan breadcrumb.
*   **Solusi**: Terapkan *Visited Set* berbasis ID node atau buat pointer `parent` kanonikal eksplisit untuk meratakan DAG menjadi directed tree murni pada context representasional.

#### 2. Facet State URL Bloat
*   **Masalah**: State filter memasukkan nilai default ke dalam URL (misal: `?category=all&page=1&sort=relevance`). Hal ini menyebabkan *cache-busting* yang tidak perlu pada Edge CDN dan membingungkan search engine bot.
*   **Solusi**: Buat serialization engine yang membuang *truthy default values* sebelum memodifikasi history state (lihat implementasi `FacetedStateRouter.serialize`).

#### 3. Focus Trapping & Accessibility Desync pada Tree Menus
*   **Masalah**: Pengguna keyboard tidak bisa menavigasi menu bertingkat menggunakan panah atas/bawah/kiri/kanan sesuai spesifikasi ARIA APG 1.2, atau *focus outline* tertinggal di node yang sudah tersembunyi.
*   **Solusi**: Implementasikan `Roving Tabindex` pattern. Hanya satu item aktif di dalam seluruh pohon navigasi yang memiliki `tabindex="0"`, sedangkan sisanya `tabindex="-1"`.

---

### 11. Best Practices (Production Checklist)

- [ ] **Structural Validation**: Skema navigasi divalidasi saat *build-time* via Zod / JSON Schema untuk mencegah node tanpa rute atau slug duplikat.
- [ ] **Max Depth Enforced**: Kedalaman pohon navigasi utama tidak boleh melebihi 3 tingkatan (Kaidah *Rule of Three* dalam Information Architecture).
- [ ] **Permission-Aware Pruning**: Node yang tidak diizinkan dieliminasi di memori sebelum serialisasi ke komponen presentasional (mencegah inspeksi DOM via DevTools membocorkan rute rahasia).
- [ ] **Canonical URL Generation**: Setiap kombinasi filter pada faceted search selalu menghasilkan canonical URL yang deterministik (diurutkan secara alfabetis berdasarkan kunci parameter).
- [ ] **Accessibility APG 1.2 Compliance**:
  - `aria-expanded` wajib ada pada setiap node bertipe branching.
  - Komponen breadcrumb wajib berada di dalam container `<nav aria-label="Breadcrumb">` dengan `<ol>`.
  - Item halaman aktif diberi atribut `aria-current="page"`.
- [ ] **Search Engine Metadata**: Secara otomatis menyuntikkan script tag `<script type="application/ld+json">` berisikan schema `BreadcrumbList`.
- [ ] **Telemetri IA**: Mengirimkan sinyal event saat pengguna membatalkan rute navigasi lebih dari 3 kali berturut-turut untuk menghitung deviasi model mental.

---

### 12. Hands-on Practice

Implementasikan file berikut pada workspace Anda: `hands-on/m02/navigation-engine.ts`.

#### Langkah 1: Inisialisasi Proyek & Schema Tree
Buat direktori dan pasang pustaka validasi:
```bash
mkdir -p hands-on/m02
cd hands-on/m02
npm init -y
npm install typescript zod @types/node --save-dev
npx tsc --init
```

#### Langkah 2: Implementasi Mesin Navigasi Komprehensif
Salin kode berikut ke `hands-on/m02/navigation-engine.ts`:

```typescript
import { z } from 'zod';

export interface HierarchyNode {
  id: string;
  name: string;
  href: string;
  requiredRole?: string;
  subNodes?: HierarchyNode[];
}

export class NavigationService {
  constructor(private readonly tree: HierarchyNode[]) {}

  /**
   * Mengambil breadcrumb secara aman tanpa infinite loop
   */
  public getBreadcrumbPath(targetHref: string): { name: string; href: string }[] {
    const trail: { name: string; href: string }[] = [];
    const visited = new Set<string>();

    const traverse = (nodes: HierarchyNode[]): boolean => {
      for (const node of nodes) {
        if (visited.has(node.id)) continue;
        visited.add(node.id);

        trail.push({ name: node.name, href: node.href });

        if (node.href === targetHref) {
          return true;
        }

        if (node.subNodes && node.subNodes.length > 0) {
          if (traverse(node.subNodes)) {
            return true;
          }
        }

        trail.pop();
      }
      return false;
    };

    traverse(this.tree);
    return trail;
  }
}

// Eksekusi Pengujian Mandiri
const mockData: HierarchyNode[] = [
  {
    id: 'root-1',
    name: 'Dashboard',
    href: '/admin',
    subNodes: [
      {
        id: 'child-1-1',
        name: 'Settings',
        href: '/admin/settings',
        subNodes: [
          {
            id: 'child-1-1-1',
            name: 'Security Keys',
            href: '/admin/settings/security',
          },
        ],
      },
    ],
  },
];

const service = new NavigationService(mockData);
const breadcrumbs = service.getBreadcrumbPath('/admin/settings/security');
console.log('Generated Breadcrumb Trail:', JSON.stringify(breadcrumbs, null, 2));

// Assertion Sederhana
if (breadcrumbs.length === 3 && breadcrumbs[2].name === 'Security Keys') {
  console.log('✅ Unit Test Verification Passed!');
} else {
  console.error('❌ Verification Failed');
  process.exit(1);
}
```

#### Langkah 3: Jalankan dan Verifikasi
```bash
npx ts-node hands-on/m02/navigation-engine.ts
```

---

### 13. Exercise

#### Level: Easy
Diberikan sebuah flat array navigasi:
```typescript
interface FlatNode { id: string; parentId: string | null; label: string; url: string; }
```
Tulis sebuah fungsi murni `buildTree(items: FlatNode[]): NavigationNode[]` yang mengonversi flat database relation tersebut menjadi recursive nested tree struktur dengan kompleksitas waktu $O(N)$ (menggunakan auxiliary hash map).

#### Level: Medium
Buat sebuah fungsi utilitas TypeScript:
```typescript
function reconcileStateToUrl(currentUrl: string, facetPatch: Record<string, string | null>): string
```
Fungsi tersebut harus dapat menerima parameter baru, menghapus kunci jika nilainya `null`, mempertahankan parameter yang tidak diubah, serta menghasilkan string query parameters yang terurut secara alfabetis demi konsistensi caching.

#### Level: Hard
Kembangkan sebuah algoritma `calculateLostnessScore(optimalPath: string[], actualSessionPath: string[]): number` yang mengimplementasikan rumus matematika *Smith’s Lostness Metric*. Fungsi harus dapat menangani navigasi sirkular, menghitung deviasi langkah, dan memberikan indikator peringatan jika skor melebihi ambang batas $0.4$.

---

### 14. Challenge

**Skenario**: Anda adalah Principal Frontend Architect di sebuah enterprise marketplace global dengan 5.000 kategori dinamis, 15 peran otoritas internal, dan dukungan 12 bahasa (i18n).

**Instruksi Masalah**:
1. Rancang arsitektur sistem informasi navigasi yang mampu me-render pohon menu utama di bawah 16ms (*60fps frame budget*).
2. Sistem dilarang membocorkan rute administratif tersembunyi ke bundle JavaScript publik client-side.
3. Rancang mekanisme state synchronizer di mana jika pengguna memfilter produk berdasarkan parameter yang tidak valid di database taksonomi, sistem secara otomatis melakukan "Graceful Degradation Fallback" ke parent taxonomy node terdekat tanpa memicu error 404 atau layout breakage.

**Output yang Dituntut**:
* Dokumen Arsitektur Teknis mencakup strategi caching, data hydration, dan representasi URL state.
* Interface TypeScript lengkap dari core router, state engine, dan AST compiler navigation.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Soal)
1. Apa perbedaan mendasar antara *Taxonomy* dan *Folksonomy* dalam arsitektur informasi?
2. Mengapa struktur basis data relasional internal (Implementation Model) jarang cocok disajikan langsung sebagai menu antarmuka pengguna?
3. Sebutkan nilai maksimal kedalaman (*depth*) ideal sebuah hierarki navigasi pada aplikasi web enterprise agar tidak melanggar prinsip beban kognitif!
4. Atribut ARIA apa yang wajib digunakan untuk menandai halaman yang sedang aktif pada komponen breadcrumbs?
5. Mengapa parameter default (seperti `page=1`) sebaiknya dihapus dari URL search parameters pada faceted navigation?

#### Intermediate (5 Soal)
6. Bagaimana cara mencegah terjadinya *infinite recursion* saat memproses graf arsitektur informasi yang memiliki hubungan many-to-many?
7. Jelaskan bagaimana *Hick's Law* ($RT = a + b \log_2(n)$) memandu keputusan antara memilih struktur navigasi *Deep Tree* versus *Broad Tree*!
8. Apa fungsi dari pemanfaatan *Roving Tabindex* pada komponen navigasi bertingkat (Treeview) ditinjau dari standar aksesibilitas keyboard?
9. Bagaimana arsitektur URL-as-State menjamin fitur *deep-linking* dan *reproducibility* pada aplikasi data-intensive?
10. Pada kondisi apa struktur arsitektur informasi berbasis DAG (*Directed Acyclic Graph*) lebih unggul dibandingkan Pure Tree?

#### Skenario Kasus Produksi (3 Soal)
11. **Skenario 1**: Bot Google Search mengalami *crawl budget depletion* dan terjebak dalam jutaan kombinasi URL tidak berujung di platform katalog enterprise Anda. Elemen arsitektur informasi apa yang rusak, dan bagaimana Anda memperbaikinya dari sisi routing state?
12. **Skenario 2**: Audit keamanan menemukan bahwa staf biasa dengan hak akses terbatas dapat melihat struktur menu "Manajemen Payroll Eksekutif" melalui inspeksi *Redux DevTools* atau inline JSON script di browser, meski komponen halamannya di-protect. Di mana kegagalan pipeline IA-nya?
13. **Skenario 3**: Data telemetri menunjukkan bahwa metrik rata-rata rasio *Lostness* pengguna pada checkout flow melonjak drastis setelah rilis redesign navigasi dari flat tabs ke multi-level accordion. Bagaimana urutan analisis forensik IA yang harus Anda lakukan untuk membuktikan akar masalah kognitifnya?

---

### 16. Summary

*   **Penyelarasan Model Mental**: Desain produk enterprise yang matang menyembunyikan kompleksitas *Implementation Model* dan menyajikan *Manifest Model* yang merefleksikan *User Mental Model*.
*   **Graph Engine & Type Safety**: Arsitektur Informasi skala besar membutuhkan struktur data berbasis pohon rekursif atau Directed Acyclic Graph (DAG) yang diisolasi oleh validasi kontrak tipe data yang ketat.
*   **URL-as-State Single Source of Truth**: State navigasi, filter facet, dan lokator taksonomi harus selalu dapat direkonstruksi secara penuh dan deterministik melalui koordinat URL.
*   **Pruning & Aksesibilitas**: Pemangkasan akses navigasi wajib dilakukan secara deklaratif sebelum data sampai di layer presentasi, diiringi kepatuhan penuh terhadap standar semantik web (ARIA Tree APG 1.2 dan JSON-LD Structured Data).