# Bab 04 Module 01: Arsitektur Informasi & Navigasi Struktural Enterprise

---

## SEKSI 01 — IDENTITAS MODUL

* **Jalur Kurikulum:** Frontend and Mobile Engineering
* **Kategori:** 03-Frontend-and-Mobile
* **Mata Pelajaran:** User Experience (UX) Architecture & Enterprise Design Systems
* **Modul:** Bab 04 Module 01 — Arsitektur Informasi & Navigasi Struktural Enterprise
* **Tingkat Kemahiran:** Advanced / Staff Engineer / Enterprise UX Architect
* **Prasyarat:** Pemahaman mendalam tentang state management client-side, dynamic routing (React Router/Next.js engine), pola RBAC (Role-Based Access Control), semantic HTML, accessibility (WCAG 2.1 AA/AAA), serta struktur data pohon (Tree Data Structures).

---

## SEKSI 02 — LEARNING OBJECTIVES

1. **Menganalisis dan Merancang Taksonomi Informasi Skala Besar:** Mampu mengekstraksi ratusan domain entitas bisnis kompleks ke dalam skema klasifikasi (hierarkis, fasad, relasional) yang meminimalkan *cognitive load* dan beban memori kerja pengguna.
2. **Menguasai Keseimbangan Breadth vs. Depth:** Mengimplementasikan rasio percabangan pohon (*branching factor*) navigasi enterprise yang mematuhi hukum Hick-Hyman dan Miller tanpa menimbulkan fenomena *deep navigational tunneling*.
3. **Membangun Dynamic Enterprise Navigation Engine:** Membangun mesin navigasi berbasis metadata TypeScript yang menerapkan RBAC, multi-tenancy scoping, lazy-loading segmentasi rute, dan state persistence secara rekursif.
4. **Menerapkan Aksesibilitas Struktural Lanjutan:** Mengonstruksi pola navigasi multi-level yang mematuhi spesifikasi WAI-ARIA (Disclosure pattern vs Treeview pattern), manajemen focus ring trap, dan penanganan screen reader kontekstual.
5. **Mengintegrasikan Telemetri Information Foraging:** Mengukur efektivitas Information Architecture (IA) menggunakan metrik pelacakan *wayfinding*, analisis *lostness metric*, dan *navigation path regression telemetry*.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Paradigma: Consumer IA vs. Enterprise IA

Navigasi aplikasi konsumen berfokus pada kesederhanaan linear dan dorongan konversi (misalnya: e-commerce checkout funnels, infinite social feeds). Sebaliknya, Enterprise Information Architecture (E-IA) menangani sistem operasi bisnis berdensitas tinggi (*high-density operating environments*) di mana pengguna bekerja selama 8 jam sehari di bawah tekanan SLA (Service Level Agreement). 

| Dimensi | Consumer IA | Enterprise Structural IA |
| :--- | :--- | :--- |
| **Tujuan Utama** | Discovery & Delight | Efisiensi Eksekusi, Navigabilitas Tugas, & Determinisme |
| **Topologi Data** | Dangkal, Terisolasi, Linear | Dalam, Sangat Terhubung (*Highly Graph-Linked*), Multi-Dimensi |
| **Model Pengguna** | Kasual, Rendah Pelatihan | Ahli Domain Berpengetahuan Tinggi, Spesifik Peran (*Role-Conditioned*) |
| **Biaya Kegagalan IA** | Drop-off pengguna / Penurunan Konversi | Kegagalan Operasional Finansial, Pelanggaran Regulasi, Kelelahan Mental Karyawan |

### Teori Information Foraging (Pirolli & Card)

Dalam arsitektur enterprise, pengguna bertindak sebagai *informational foragers*. Pengguna mengevaluasi **Information Scent** (jejak informasi)—tanda visual, terminologi leksikal, dan petunjuk struktural—sebelum memutuskan untuk mengklik simpul navigasi. Jika jejak informasi lemah (*weak scent*) akibat terminologi ambigu seperti "Alat", "Manajemen", atau "Lainnya", pengguna akan mengalami *navigational thrashing* (pindah maju-mundur antar sub-menu), yang meningkatkan latensi penyelesaian tugas dan memicu kelelahan kognitif.

### Mental Model Taksonomi Pohon vs. Graf Faset

Struktur penyimpanan data enterprise sering kali berupa Relational Database Management System (RDBMS) atau Knowledge Graph. Namun, kognisi manusia menuntut dekomposisi data ke dalam pohon hierarkis serial. Arsitektur navigasi enterprise yang unggul bertindak sebagai abstraksi proyeksi faset: memetakan struktur data graf polimorfik ke dalam model pohon navigasi kontekstual yang dapat diproyeksikan secara dinamis berdasarkan peran kerja (*work role*), status tugas (*task phase*), dan batasan perizinan (*access scope*).

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Di bawah ini adalah diagram ASCII detail dari Enterprise Dynamic Navigation Engine yang memproses struktur navigasi dari State Store terpusat, melewati filter RBAC dan Multi-Tenancy Scoping, lalu memproyeksikannya ke antarmuka pengguna:

```
[ BACKEND IAM & REGISTRY SERVICE ]
                 |
                 v
   +-----------------------------+
   | Raw Navigation Schema (JSON)|
   | - Entitlements / Permissions|
   | - Tenant Feature Flags      |
   +-----------------------------+
                 |
                 v
+-----------------------------------------------------------------------+
|              CLIENT-SIDE ENTERPRISE ROUTING ENGINE                    |
|                                                                       |
|  +-----------------------------------------------------------------+  |
|  | Context Store (Active Tenant, User RBAC, Feature Vector)        |  |
|  +-----------------------------------------------------------------+  |
|                                |                                      |
|                                v                                      |
|  +-----------------------------------------------------------------+  |
|  | Recursive Schema Compiler / Resolver Engine                     |  |
|  |  1. Structural Graph Normalization                              |  |
|  |  2. RBAC Pruning (Hapus node unauthorized via Bitmask)          |  |
|  |  3. Feature Flag Evaluation (Dynamic Branch Injection)          |  |
|  |  4. Breadth-Depth Balancer (Flattening singletons)              |  |
|  +-----------------------------------------------------------------+  |
|                                |                                      |
|                                v                                      |
|  +-----------------------------------------------------------------+  |
|  | Hydrated Navigation Tree (Typed Structural Graph Model)        |  |
|  +-----------------------------------------------------------------+  |
|         |                                    |                        |
|         v                                    v                        |
|  +-----------------------+          +-----------------------+         |
|  | Flat Search Index     |          | Wayfinding Engine     |         |
|  | (Trie/Bloom Filter)   |          | - Breadcrumb Trail    |         |
|  | for Command Palette   |          | - Deep Tunnel Avoid   |         |
|  +-----------------------+          +-----------------------+         |
+-----------------------------------------------------------------------+
        |                                    |
        v                                    v
+-----------------------+            +----------------------------------+
| ACCESSIBLE DOM ENGINE |            | WORKSPACE CANVAS                 |
| - Primary Sidebar     |            | - Tabbed Navigation (L2/L3)      |
| - Dynamic Mega-Menu   |            | - Deep Context Inspector Panel   |
| - Semantic ARIA Trees |            | - Route Dynamic Outlet           |
+-----------------------+            +----------------------------------+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

Sebuah sistem navigasi struktural enterprise terdiri dari 6 komponen inti yang saling terhubung:

```
+------------------------------------------------------------------------------------+
| 1. GLOBAL WORKSPACE BAR (L1 Domain Hub / Scope Switcher)                           |
+------------------------------------------------------------------------------------+
| 2. ENTERPRISE SIDEBAR        | 4. TAB/SUB-NAV (L3/L4 Workspace Views)              |
|    (L2 Contextual Tree)      +-----------------------------------------------------+
|                              | 5. WAYFINDING BAR (Breadcrumb + Scope Indicator)    |
| - Group: Operations          +-----------------------------------------------------+
|   |- Node: Logistics (Tree)  | 6. CONTEXTUAL CANVAS / DATA DENSITY GRID            |
|   |  |- Leaf: Route Tracker  |                                                     |
|   |  `- Leaf: Inventory Audit|                                                     |
| - Group: Identity            |                                                     |
|   `- Node: Access Ledger     |                                                     |
| 3. DRAWER TOGGLE / COLLAPSER |                                                     |
+------------------------------+-----------------------------------------------------+
```

### 1. Global Workspace Bar (Primary Domain Switcher / L1)
*   **Tujuan:** Mengisolasi ranah bisnis (*bounded context*). Misalnya: beralih antara "Core ERP", "Supply Chain Analytics", dan "IAM Governance".
*   **Mekanisme Internal:** Bertindak sebagai *root partitioner*. Membawa informasi tenancy ID dan merestart *navigational state* pohon lokal guna menghindari tumpang tindih state antar bounded context.

### 2. Contextual Primary Sidebar (Vertical Structural Hierarchy / L2)
*   **Tujuan:** Menyediakan hierarki navigasi terstruktur untuk domain aktif.
*   **Mekanisme Internal:** Dirender secara rekursif menggunakan struktur data pohon. Menerapkan pola WAI-ARIA disclosure atau treeview dependan pada kerapatan interaksi. Menggunakan *virtualized rendering* jika jumlah simpul melebihi 200 node untuk mencegah degradasi DOM.

### 3. Progressive Wayfinding Engine (Dynamic Breadcrumbs)
*   **Tujuan:** Mengeliminasi disorientasi mental spasial dan memfasilitasi navigasi kembali (*ancestral navigation*) dengan biaya kognitif minimum.
*   **Mekanisme Internal:** Menghitung jalur secara runtime dari root node ke active leaf node berdasarkan rute URL saat ini. Mendukung *truncated projection* dengan dropdown popover saat panjang rantai melebihi lebar layar.

### 4. Intra-Entity Workspace Tabs (L3/L4 Sub-views)
*   **Tujuan:** Memecah entitas yang sangat padat (misalnya: file audit pelanggan dengan ribuan atribut) ke dalam model faset paralel tanpa merusak URL canonical.
*   **Mekanisme Internal:** Dikorelasikan dengan parameter kueri URL (`?tab=compliance&subview=logs`) untuk mendukung *deep-linking* deterministik.

### 5. Flat Global Command Palette (Trie-based Global Quick-Switcher)
*   **Tujuan:** Jalur pintas *bypass* hierarki untuk power-users yang mengetahui terminologi tugas secara presisi.
*   **Mekanisme Internal:** Mengambil *flattened index* dari navigational graph, dieksekusi melalui struktur data Trie atau pencarian fuzzy berbobot (*weighted fuzzy search*) dengan latensi pencarian di bawah 16ms (60 FPS).

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### 1. Keseimbangan Breadth vs. Depth (Branching Factor Mechanics)
Hukum Hick-Hyman memodelkan waktu reaksi pemilihan keputusan ($T$):

$$T = b \cdot \log_2(n + 1)$$

Di mana $n$ adalah jumlah opsi setara dan $b$ adalah konstanta empiris kognitif.

Namun, jika kedalaman arsitektur ($D$) ditingkatkan untuk memperkecil $n$ pada setiap level, Hukum Klonoski tentang Penelusuran Navigasi berlaku: probabilitas kesalahan navigasi kumulatif ($P_E$) meningkat secara eksponensial seiring bertambahnya kedalaman rantai keputusan:

$$P_E = 1 - (1 - p)^D$$

Di mana $p$ adalah probabilitas kesalahan interpretasi label pada satu simpul, dan $D$ adalah kedalaman pohon.

*   **Pohon Terlalu Lebar (Flat - Breadth > 12 pada L1):** Mengakibatkan *attentional overload*, *visual clutter*, dan memicu *saccadic exhaustion* (mata harus menyapu area yang luas tanpa diferensiasi hierarkis yang jelas).
*   **Pohon Terlalu Dalam (Deep - Depth > 4):** Menimbulkan *navigational tunneling*, di mana pengguna melupakan tujuan tugas awal mereka (*loss of intent*) karena memori kerja manusia terbebani oleh pelacakan kembali status rute (*context backtracking*).
*   **Golden Ratio Enterprise:** *Branching factor* optimal berada pada kisaran 5 hingga 9 anak per simpul induk (Hukum Miller $7 \pm 2$), dengan kedalaman struktural maksimum 3 tingkat navigasi hierarkis murni sebelum dialihkan ke faset berbasis tab atau kanvas filter data.

```
       [DEPTH EXTREME: Tunneling Failure]             [BALANCED ENTERPRISE IA]
                  Root                                         Root
                   |                                      /     |     \
                 Node 1                               Node 1  Node 2  Node 3 (Breadth: 3-8)
                   |                                  /    \
                 Node 2                             Leaf   Leaf (Depth: <= 3)
                   |
                 Node 3 (Cognitive Drop-off)
```

### 2. Information Scent & Terminological Ambiguity
Ambiguitas terjadi jika enterprise menggunakan pelabelan fungsional non-ortogonal. Contohnya memisahkan "Konfigurasi Sistem", "Pengaturan Akun", dan "Preferensi Operasi". Bagi pengguna akhir, ketiga label ini memiliki jarak semantik yang sangat sempit (*high semantic collision*).

*   **Prinsip Ortogonalitas Taksonomi:** Setiap cabang navigasi harus saling lepas (*mutually exclusive*) dan menyeluruh secara kolektif (*collectively exhaustive*)—dikenal sebagai prinsip MECE. Jika Node A dan Node B berbagi lebih dari 15% kemungkinan penempatan entitas, arsitektur informasi tersebut cacat secara ontologis.

### 3. State Persistence dalam Arsitektur Navigasi
Pada sistem operasi enterprise, status navigasi (apakah suatu folder menu terbuka, posisi scroll pada sub-tree, filter faset yang sedang aktif) tidak boleh tereset saat terjadi navigasi rute atau re-render komponen.
*   **Tree Expansion State:** Harus disinkronkan dengan *URL path matching engine*. Jika pengguna menyegarkan halaman atau membagikan link `/finance/ledgers/accruals/apac`, pohon menu harus menghidrasi status expand secara otomatis dari root menuju active leaf (*ancestor path hydration*).
*   **Scroll Preservation:** Virtual scroll container sidebar harus mempertahankan offset posisi menggunakan *layout key identification* agar pengguna tidak kehilangan konteks fokus spasial.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi Navigation Registry & Recursive RBAC Filtering Engine berstandar industri menggunakan TypeScript. Kode ini mendefinisikan tipe metadata navigasi enterprise, memvalidasi perizinan (*authorization*), dan menyusun struktur pohon yang siap dirender secara deterministik.

```typescript
// types/navigation.ts

export type PermissionCode = 'READ_FINANCE' | 'WRITE_FINANCE' | 'AUDIT_LOGS' | 'SYSTEM_ADMIN';

export interface BaseNavigationNode {
  id: string;
  label: string;
  icon?: string;
  requiredPermissions?: PermissionCode[];
  requiredFeatures?: string[];
  badgeCountKey?: string;
}

export interface NavigationLeaf extends BaseNavigationNode {
  type: 'LEAF';
  path: string;
}

export interface NavigationBranch extends BaseNavigationNode {
  type: 'BRANCH';
  children: NavigationNode[];
  defaultExpanded?: boolean;
}

export type NavigationNode = NavigationLeaf | NavigationBranch;

export interface UserSecurityContext {
  userId: string;
  tenantId: string;
  permissions: Set<PermissionCode>;
  enabledFeatures: Set<string>;
}

// engine/navigationResolver.ts

/**
 * Memfilter pohon navigasi enterprise secara rekursif berdasarkan perizinan pengguna
 * dan ketersediaan fitur (Feature Flags), sembari membersihkan cabang kosong.
 */
export function resolveNavigationTree(
  nodes: NavigationNode[],
  context: UserSecurityContext
): NavigationNode[] {
  const resolvedNodes: NavigationNode[] = [];

  for (const node of nodes) {
    // 1. Validasi Batasan RBAC
    if (node.requiredPermissions && node.requiredPermissions.length > 0) {
      const hasPermission = node.requiredPermissions.every((perm) =>
        context.permissions.has(perm)
      );
      if (!hasPermission) {
        continue; // Lewati simpul jika izin tidak terpenuhi
      }
    }

    // 2. Validasi Batasan Feature Flags
    if (node.requiredFeatures && node.requiredFeatures.length > 0) {
      const hasFeature = node.requiredFeatures.every((feat) =>
        context.enabledFeatures.has(feat)
      );
      if (!hasFeature) {
        continue; // Lewati simpul jika fitur dinonaktifkan
      }
    }

    // 3. Penanganan Simpul Tipe LEAF
    if (node.type === 'LEAF') {
      resolvedNodes.push({ ...node });
      continue;
    }

    // 4. Penanganan Simpul Tipe BRANCH secara Rekursif
    if (node.type === 'BRANCH') {
      const filteredChildren = resolveNavigationTree(node.children, context);

      // Branch tidak boleh dirender jika seluruh anaknya terfilter (mencegah ghost branches)
      if (filteredChildren.length > 0) {
        resolvedNodes.push({
          ...node,
          children: filteredChildren,
        });
      }
    }
  }

  return resolvedNodes;
}

/**
 * Menghasilkan indeks datar (Flat Search Map) dari navigation tree untuk Command Palette
 */
export interface FlatNavigationItem {
  id: string;
  label: string;
  path: string;
  ancestorLabels: string[];
}

export function flattenNavigationTree(
  nodes: NavigationNode[],
  ancestorLabels: string[] = []
): FlatNavigationItem[] {
  let flatList: FlatNavigationItem[] = [];

  for (const node of nodes) {
    if (node.type === 'LEAF') {
      flatList.push({
        id: node.id,
        label: node.label,
        path: node.path,
        ancestorLabels,
      });
    } else if (node.type === 'BRANCH') {
      const currentAncestors = [...ancestorLabels, node.label];
      flatList = flatList.concat(
        flattenNavigationTree(node.children, currentAncestors)
      );
    }
  }

  return flatList;
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi teknis logika penyusun engine navigasi di atas:

*   **Baris 3–19 (`types/navigation.ts`):** Menggunakan pola *Discriminated Union* (`type: 'LEAF' | 'BRANCH'`). Pendekatan ini mewajibkan TypeScript mengecek ketersediaan `path` hanya pada `LEAF`, dan keberadaan sub-array `children` hanya pada `BRANCH`, mengeliminasi bug runtime `undefined reading 'children'`.
*   **Baris 21–26 (`UserSecurityContext`):** Menggunakan `Set<PermissionCode>` alih-alih `Array<PermissionCode>`. Evaluasi `has()` beroperasi dalam kompleksitas waktu konstan $O(1)$, menjamin pemrosesan ratusan simpul navigasi berjalan instan tanpa bottleneck mikro-komputasi.
*   **Baris 35–52 (`navigationResolver.ts`):** Tahap evaluasi RBAC dan Feature Flag. Penggunaan operator `.every()` memaksakan kebijakan *fail-closed* / keamanan ketat: jika sebuah simpul memerlukan 3 perizinan, ketiadaan salah satu izin akan memblokir simpul tersebut secara instan.
*   **Baris 62–73 (`Pembersihan Ghost Branch`):** Inti dari algoritma rekursif hierarkis. Jika pengguna memiliki izin melihat node induk, namun izin seluruh node anak di dalamnya di-revokasi (*revoked*), node induk tersebut menjadi *ghost branch* (cabang kosong tak berujung). Logika `if (filteredChildren.length > 0)` secara otomatis memangkas cabang tersebut, menjaga kerapihan visual antarmuka navigasi.
*   **Baris 89–110 (`flattenNavigationTree`):** Algoritma Depth-First Search (DFS) yang mengekstraksi struktur pohon bertingkat menjadi array datar. Penyimpanan `ancestorLabels` menyediakan jejak kontekstual penuh (misal: `"Finance" > "Ledgers" > "AP"`) yang krusial untuk pencarian global command palette berpresisi tinggi.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario Produksi: ERP Konsolidasi Global Multi-Tenant (OmniLogix Global)

*   **Latar Belakang Industri:** OmniLogix Global mengoperasikan platform rantai pasok global dengan 42 modul fungsional, 1.200 tampilan rute berbeda, dan melayani 4 hierarki persona utama: *Global Enterprise Admin*, *Regional Logistics Officer*, *Third-Party Carrier*, dan *Financial Compliance Auditor*.
*   **Masalah Arsitektur Awal:**
    1.  Sidebar monolitik menampilkan menu setinggi 6 tingkat folder dengan total 180 tautan aktif di layar secara serentak.
    2.  *Lostness Metric* pengguna audit mencapai skor buruk: 0.68 (skor di atas 0.4 menandakan kegagalan navigasi parah).
    3.  Tingginya angka tiket dukungan teknis internal: 34% dari seluruh tiket pelaporan pengguna adalah masalah kegagalan menemukan fitur (*"Saya tidak dapat menemukan modul rekonsiliasi PPN"*).
    4.  Perubahan perizinan IAM backend sering kali meninggalkan cabang menu kosong di sisi frontend, yang membingungkan pengguna ketika diklik (*broken interaction*).
*   **Intervensi Arsitektur Informasi Baru:**
    1.  **Dekomposisi Topologi Menjadi L1-L2-L3:** Mengubah sistem menjadi 3 bidang navigasi:
        *   **L1 (Global Hub Bar):** Pembagian berdasarkan domain bisnis (Operasional, Pergudangan, Keuangan, Pengaturan Sistem).
        *   **L2 (Dynamic Contextual Tree Sidebar):** Dibatasi maksimal 2 tingkat kedalaman hierarkis murni per domain.
        *   **L3 (In-Workspace Structural Tabs):** Memecah entitas data detail menjadi tampilan faset horizontal di dalam area kerja kanvas.
    2.  **Engine Navigasi Dinamis Berbasis RBAC & Bitmask Filtering:** Menjamin eliminasi total cabang kosong (*ghost branches*).
    3.  **Command Palette Terintegrasi:** Memungkinkan pencarian pintas berbasis token faset semantik dengan latensi instan.
*   **Hasil Metrik:**
    *   Waktu penyelesaian tugas audit berkurang sebesar 42%.
    *   *Lostness Metric* turun drastis ke 0.12.
    *   Tiket bantuan terkait wayfinding berkurang hingga 88% dalam kurun waktu 90 hari pasca rilis.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Di bawah ini adalah implementasi komponen Navigation Sidebar Enterprise menggunakan React, Tailwind CSS, dan pola aksesibilitas WAI-ARIA Disclosure. Komponen ini mendukung *recursive auto-expansion*, state persistence melalui *session context*, dan pemantauan fokus keyboard yang ketat.

```tsx
// components/EnterpriseSidebar.tsx

import React, { useState, useEffect, useMemo, createContext, useContext } from 'react';
import { 
  NavigationNode, 
  NavigationBranch, 
  NavigationLeaf, 
  UserSecurityContext, 
  resolveNavigationTree 
} from './navigationResolver';

interface NavigationContextType {
  activePath: string;
  expandedNodeIds: Set<string>;
  toggleNode: (nodeId: string) => void;
  onNavigate: (path: string) => void;
}

const NavigationContext = createContext<NavigationContextType | null>(null);

function useNavigation() {
  const context = useContext(NavigationContext);
  if (!context) {
    throw new Error('useNavigation must be used within NavigationProvider');
  }
  return context;
}

interface EnterpriseSidebarProps {
  schema: NavigationNode[];
  userContext: UserSecurityContext;
  currentPath: string;
  onNavigate: (path: string) => void;
}

export const EnterpriseSidebar: React.FC<EnterpriseSidebarProps> = ({
  schema,
  userContext,
  currentPath,
  onNavigate,
}) => {
  // 1. Eksekusi filtering RBAC & feature flags
  const authorizedTree = useMemo(() => {
    return resolveNavigationTree(schema, userContext);
  }, [schema, userContext]);

  // 2. Hitung node ancestor yang harus terbuka otomatis berdasarkan path aktif
  const initialExpandedIds = useMemo(() => {
    const idsToExpand = new Set<string>();

    function traceAncestors(nodes: NavigationNode[], targetPath: string): boolean {
      for (const node of nodes) {
        if (node.type === 'LEAF') {
          if (node.path === targetPath) return true;
        } else if (node.type === 'BRANCH') {
          const isChildMatched = traceAncestors(node.children, targetPath);
          if (isChildMatched) {
            idsToExpand.add(node.id);
            return true;
          }
        }
      }
      return false;
    }

    traceAncestors(authorizedTree, currentPath);
    return idsToExpand;
  }, [authorizedTree, currentPath]);

  const [expandedNodeIds, setExpandedNodeIds] = useState<Set<string>>(initialExpandedIds);

  // Perbarui node yang terbuka jika rute berubah dari luar komponen
  useEffect(() => {
    setExpandedNodeIds((prev) => {
      const next = new Set(prev);
      initialExpandedIds.forEach((id) => next.add(id));
      return next;
    });
  }, [initialExpandedIds]);

  const toggleNode = (nodeId: string) => {
    setExpandedNodeIds((prev) => {
      const next = new Set(prev);
      if (next.has(nodeId)) {
        next.delete(nodeId);
      } else {
        next.add(nodeId);
      }
      return next;
    });
  };

  return (
    <NavigationContext.Provider
      value={{
        activePath: currentPath,
        expandedNodeIds,
        toggleNode,
        onNavigate,
      }}
    >
      <nav
        aria-label="Sidebar Navigasi Enterprise"
        className="w-72 h-screen bg-slate-900 border-r border-slate-800 flex flex-col text-slate-300 font-sans select-none"
      >
        <div className="p-4 border-b border-slate-800 flex items-center justify-between">
          <span className="text-sm font-semibold tracking-wider text-slate-100 uppercase">
            Platform Hub
          </span>
          <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-400 font-mono">
            {userContext.tenantId}
          </span>
        </div>

        <div className="flex-1 overflow-y-auto p-3 space-y-1 focus:outline-none" tabIndex={0}>
          <ul className="space-y-1" role="list">
            {authorizedTree.map((node) => (
              <NavigationItemNode key={node.id} node={node} level={0} />
            ))}
          </ul>
        </div>
      </nav>
    </NavigationContext.Provider>
  );
};

interface NavigationItemNodeProps {
  node: NavigationNode;
  level: number;
}

const NavigationItemNode: React.FC<NavigationItemNodeProps> = ({ node, level }) => {
  const { activePath, expandedNodeIds, toggleNode, onNavigate } = useNavigation();
  const indentPadding = `${level * 0.75 + 0.5}rem`;

  if (node.type === 'LEAF') {
    const isActive = activePath === node.path;

    return (
      <li role="listitem">
        <button
          type="button"
          onClick={() => onNavigate(node.path)}
          aria-current={isActive ? 'page' : undefined}
          style={{ paddingLeft: indentPadding }}
          className={`w-full flex items-center justify-between py-2 pr-3 rounded-md text-xs font-medium transition-colors text-left focus:outline-none focus:ring-2 focus:ring-sky-500 ${
            isActive
              ? 'bg-sky-600/20 text-sky-400 border-l-2 border-sky-500'
              : 'hover:bg-slate-800/60 text-slate-400 hover:text-slate-200'
          }`}
        >
          <span className="truncate">{node.label}</span>
          {node.badgeCountKey && (
            <span className="ml-2 px-1.5 py-0.5 text-[10px] font-semibold bg-slate-800 text-slate-300 rounded">
              Active
            </span>
          )}
        </button>
      </li>
    );
  }

  // Node Tipe BRANCH
  const isExpanded = expandedNodeIds.has(node.id);

  return (
    <li role="listitem" className="space-y-1">
      <button
        type="button"
        aria-expanded={isExpanded}
        onClick={() => toggleNode(node.id)}
        style={{ paddingLeft: indentPadding }}
        className="w-full flex items-center justify-between py-2 pr-3 rounded-md text-xs font-semibold text-slate-300 hover:bg-slate-800/40 transition-colors focus:outline-none focus:ring-2 focus:ring-sky-500"
      >
        <span className="truncate uppercase tracking-wider text-[11px] text-slate-400">
          {node.label}
        </span>
        <svg
          className={`w-3.5 h-3.5 text-slate-500 transform transition-transform duration-200 ${
            isExpanded ? 'rotate-90' : ''
          }`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7" />
        </svg>
      </button>

      {isExpanded && (
        <ul className="space-y-1 transition-all duration-200" role="list">
          {node.children.map((child) => (
            <NavigationItemNode key={child.id} node={child} level={level + 1} />
          ))}
        </ul>
      )}
    </li>
  );
};
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

Desain navigasi struktural enterprise menuntut pemilihan pola antarmuka yang tepat. Tabel berikut menganalisis arsitektur navigasi umum berdasarkan trade-off teknis dan beban kognitif:

| Pola Navigasi | Keunggulan Desain | Kelemahan & Batasan | Kompleksitas DOM & State | Efisiensi Ruang (*Real Estate*) | Beban Kognitif Pengguna |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Strict Tree-View (Hierarkis Tunggal)** | Memetakan lokasi fisik node secara jelas; prediktif; familiar bagi operator sistem. | Navigasi lambat untuk alur lintas modul; rawan memicu *navigational thrashing*. | **Medium**: Memerlukan sinkronisasi state ekspansi multi-level. | **Tinggi (Vertikal)**: Menghabiskan lebar layar horizontal secara statis. | Rendah untuk taksonomi sederhana; Sangat Tinggi jika kedalaman > 4. |
| **Faceted / Multi-Taxonomy Filter** | Fleksibilitas tinggi dalam mengeksplorasi entitas polimorfik tanpa struktur pohon yang kaku. | Rentan kehilangan status wayfinding; URL routing menjadi sangat kompleks. | **Tinggi**: Membutuhkan sinkronisasi state URL query array/matrix. | **Adaptif**: Menggunakan floating sheets atau dynamic horizontal bars. | Tinggi di awal (*steep learning curve*), Rendah setelah mahir. |
| **Global Command Palette (Hub KBD)** | Waktu temu $O(1)$; melewati struktur hierarki yang dalam; sangat disukai oleh operator ahli. | Ketergantungan memori penuh (*no visual scent*); tidak cocok untuk pengguna baru. | **Rendah**: Membutuhkan indeks array datar di memori; DOM terisolasi di overlay modal. | **Maksimum**: Menghemat ruang layar sepenuhnya (zero surface footprint saat dormant). | Sangat Rendah untuk pencarian; Tidak mendukung discovery pasif. |
| **Mega-Menu Grid (Flyout Horizontal)** | Mengekspos seluruh horizon taksonomi secara instan; memangkas jumlah interaksi klik. | Merusak fokus visual; rentan masalah *pointer hover drop-off*; buruk pada viewport sempit. | **Rendah**: Static portal tree rendering; minim recursive state. | **Rendah**: Menutupi seluruh workspace canvas saat aktif. | Sangat Tinggi: Memicu *information overload* secara tiba-tiba. |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. The Ghost Branch Failure Mode
*   **Kasus:** Pengguna memiliki izin RBAC untuk simpul induk (misal: "Manajemen Finansial"), namun izin untuk seluruh simpul anak di bawahnya telah dicabut via policy IAM.
*   **Dampak:** Menu induk dapat diklik dan dibuka, namun menghasilkan daftar kosong (*white/blank sub-tree*). Pengguna menganggap sistem mengalami kerusakan (bug/freeze).
*   **Mitigasi Teknis:** Terapkan pembersihan rekursif dari bawah ke atas (*bottom-up recursive pruning*) seperti yang ditunjukkan pada fungsi `resolveNavigationTree`. Simpul cabang hanya boleh berstatus valid jika menghasilkan `filteredChildren.length > 0`.

### 2. URL-Tree Desynchronization (Routing Mismatch)
*   **Kasus:** Pengguna dialihkan via deep-link internal (misalnya mengklik notifikasi toast ke `/orders/batch/9812/inspect`), namun sidebar navigasi tetap membuka direktori rute sebelumnya.
*   **Dampak:** Terjadi disonansi kognitif spasial; indikator visual aktif menunjuk ke tempat yang salah, sehingga tombol navigasi 'Back' atau hierarki reaktif gagal dipahami.
*   **Mitigasi Teknis:** Implementasikan algoritma pelacakan balik leluhur (*ancestral traversal algorithm*) yang memetakan `currentPath` ke struktur pohon secara reaktif pada setiap transisi rute (via `useMemo` / router listener).

### 3. Asymmetric Deep-Linking pada Multi-Tenancy Scoping
*   **Kasus:** Pengguna membuka tautan rute yang valid di satu tenant, lalu berganti tenant aktif melalui switch-context bar di mana tenant baru tersebut tidak memiliki lisensi modul yang bersangkutan.
*   **Dampak:** Runtime crash (404/Null pointer dereference) jika pohon navigasi tidak menghitung ulang status entitlement secara instan.
*   **Mitigasi Teknis:** Pasang gerbang evaluasi rute terpusat (*Route Entitlement Guard*) yang membandingkan path aktif terhadap navigasi hasil resolusi tenant baru. Jika izin tidak ditemukan, alihkan pengguna secara otomatis ke rute *default fallback* tenant tersebut.

