# Bab 03 Module 01: Arsitektur Informasi & Mental Models

---

## SEKSI 01 — IDENTITAS MODUL
* **Track:** Product Design Engineering
* **Kategori:** 03-Frontend-and-Mobile
* **Bab:** 03 — Structural Design Systems & Cognitive Ergonomics
* **Modul:** 01 — Arsitektur Informasi & Mental Models
* **Tingkat Kesulitan:** Advanced / Staff Engineer Level
* **Prasyarat Teknis:** Pemahaman mendalam mengenai DOM traversal, Finite State Machines (FSM), State Management (Redux/Zustand pattern), TypeScript Generic Programming, serta prinsip dasar Cognitive Load Theory dan Human-Computer Interaction (HCI).

---

## SEKSI 02 — LEARNING OBJECTIVES
Setelah menyelesaikan modul ini, peserta mampu:
1. Merekonstruksi skema navigasi enterprise dan hierarki data frontend dari sekadar visual tree menjadi representasi matematis *Directed Acyclic Graph* (DAG) dan *Ontology Engine*.
2. Memetakan *User Mental Models* ke dalam *System Implementation Models* menggunakan teknik *Semantic Bridging* guna mengeliminasi krisis kognitif (*gulf of evaluation* dan *gulf of execution*).
3. Mengembangkan sistem navigasi dinamis berbasis TypeScript dan State Engine yang memisahkan relasi taksonomi (*hierarchical*, *polyhierarchical*, *faceted*) dari lapisan presentasi UI.
4. Mendiagnosis degradasi kognitif (*cognitive friction*) pada user interface skala besar melalui instrumentasi telemetri berbasis *Time-to-Information* (TTI) dan *Information Scent Decay Metrics*.
5. Mengimplementasikan struktur *Card Sorting Engine* dan *Taxonomy Resolver* tervalidasi yang tahan terhadap *edge-case circular dependency*, *orphan node*, dan kebocoran otorisasi (*Role-Based Information Architecture*).

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### The Structural Reality of Software
Aplikasi frontend skala enterprise sering kali gagal bukan karena performa render JavaScript yang lambat, melainkan karena kegagalan struktural Arsitektur Informasi (IA). Ketika pengguna mengeluh bahwa sebuah sistem "membingungkan", "sulit dinavigasi", atau "tidak intuitif", akar permasalahannya hampir selalu merupakan diskrepansi antara **Mental Model Pengguna** (bagaimana pengguna mengonseptualisasikan cara kerja tugas mereka di dunia nyata) dan **Implementation Model** (bagaimana data disimpan, dinormalisasi, dan ditransmisikan oleh database/backend).

```
   [ MENTAL MODEL PENGGUNA ]            [ IMPLEMENTATION MODEL ]
  (Abstraksi Alur Bisnis Nyata)         (Struktur Normalisasi DB)
               \                                   /
                \                                 /
                 ▼                               ▼
            +-----------------------------------------+
            |          MANIFEST MODEL (UI/IA)         |
            |     Arsitektur Informasi Bertindak      |
            |     Sebagai Jembatan Penerjemah         |
            +-----------------------------------------+
```

### Analogies & Core Intuition
Bayangkan sebuah perpustakaan raksasa. *Implementation Model* adalah cara buku disimpan berdasarkan efisiensi gudang: ukuran fisik buku, tanggal kedatangan, dan ID rak database. Jika perpustakaan mengekspos model ini kepada pengunjung, pengunjung harus tahu ID batch cetak untuk menemukan buku tentang "Machine Learning". 

Sebaliknya, *Manifest Model* yang dibangun oleh Arsitektur Informasi mengorganisasi buku menggunakan Klasifikasi Desimal Dewey, sistem katalog subjek, dan navigasi tematik. Arsitektur Informasi bukanlah dekorasi UI (seperti warna tombol atau animasi drawer); IA adalah sistem ontologi, taksonomi, dan koreografi penemuan data yang memungkinkan otak manusia memetakan intensi ke dalam eksekusi komputasional secara mulus.

Prinsip fundamental bagi Senior Frontend Architect:
1. **Separation of Structure and Surface:** Pisahkan representasi semantik hierarki aplikasi dari komponen UI penampilnya. Komponen UI hanyalah proyeksi sesaat dari graf informasi.
2. **The Law of Conservation of Complexity (Tesler’s Law):** Kompleksitas sistem tidak bisa dihilangkan; kompleksitas hanya bisa dipindahkan. IA bertugas menarik kompleksitas dari pundak pengguna dan mentransformasikannya menjadi struktur data prediktif di sisi frontend.
3. **Information Scent:** Pengguna menavigasi antarmuka seperti predator melacak mangsa. Setiap label navigasi, tautan breadcrumb, dan kategori faset harus memancarkan "aroma informasi" (*information scent*) yang kuat dan konsisten, meminimalkan keraguan kognitif.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Di bawah ini adalah arsitektur aliran transformasi dari model mental pengguna menuju resolusi graf informasi di lapisan frontend enterprise:

```
[ Domain Reality / User Intention ]
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│ 1. KOGNISI & MENTAL MODEL ENGINE                            │
│    - Task Mental Model (Langkah Kerja Alami)                │
│    - Conceptual Entities (Objek yang Dipahami User)         │
└──────────────────────────────┬──────────────────────────────┘
                               │ Diselaraskan via Semantic Bridge
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. ARSITEKTUR INFORMASI (ONTOLOGY & TAXONOMY DAG)           │
│    ┌─────────────────┐    ┌───────────────────────────────┐ │
│    │ Hierarchical    │    │ Faceted Indices               │ │
│    │ Polyhierarchical│    │ - Dimension: Department       │ │
│    │ Network (Graphs)│    │ - Dimension: Lifecycle Stage  │ │
│    └────────┬────────┘    │ - Dimension: Sensitivity      │ │
│             │             └───────────────┬───────────────┘ │
│             └────────────────┬────────────┘                 │
└──────────────────────────────┼──────────────────────────────┘
                               │ Resolusi Graph State
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. COMPILATION & ACCESS CONTROL LAYER                       │
│    - RBAC / ABAC Security Predicates                        │
│    - State Route Resolver (Virtual Graph Traversal)         │
│    - Circular Dependency & Orphan Node Interceptor          │
└──────────────────────────────┬──────────────────────────────┘
                               │ Graph Diterjemahkan
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. PRESENTATION LAYER (MANIFEST MODEL PROJECTIONS)         │
│    ┌──────────────────┐ ┌──────────────────┐ ┌────────────┐ │
│    │ Global Nav Tree  │ │ Faceted Search   │ │ Contextual │ │
│    │ (Wayfinding UI)  │ │ Filter Engine    │ │ Breadcrumbs│ │
│    └──────────────────┘ └──────────────────┘ └────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

Berikut alur eksekusi kueri traversal navigasi pengguna saat mencari entitas lintas faset:

```
User Action: "Audit Log Finansial Q3"
       │
       ▼
[ Parse Intent & Context Tokens ]
       │
       ├─► Context: Department = "Finance"
       ├─► Temporal: Period = "Q3-2024"
       └─► Entity Type: "AuditLog"
       │
       ▼
[ Evaluasi Node Policy via Graph Traversal Engine ]
       │
      ┌┴─────────────────────────────────────────┐
      │ Apakah User memiliki Role 'FINANCE_READ'?│
      └┬─────────────────────────────────────────┘
       ├────── NO ─────► [ Hapus Node dari Breadcrumbs / 403 Stealth ]
       │
      YES
       ▼
[ Hitung Information Scent Weight pada Edge DAG ]
       │
       ▼
[ Resolusi State: Polyhierarchical Node Resolution ]
       ├─► Path A: /finance/compliance/audits/q3
       └─► Path B: /reports/security-audits/finance/q3
       │
       ▼
[ Canonical Node Selection via Deterministic Heuristic ]
       │
       ▼
[ Emit View Projection & Update History Mental Model Map ]
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. The Four Pillars of Enterprise Information Architecture
Arsitektur Informasi frontend terdiri dari empat subsistem terpadu:
* **Sistem Organisasi (*Organization Systems*):** Struktur pengelompokan konten. Terdiri dari skema hierarkis (*strict parent-child trees*), polihierarkis (*single node* berada di multi-parent), dan faceted/taksonomi modular (properti dimensi independen).
* **Sistem Pelabelan (*Labeling Systems*):** Terminologi semantik representatif. Label bukanlah sekadar teks tombol, melainkan kontrak kognitif yang memicu ekspektasi spesifik terhadap konten target.
* **Sistem Navigasi (*Navigation Systems*):** Mekanisme traversal fisik/virtual yang mencakup navigasi global (makro), lokal (sub-sistem), kontekstual (inline references), dan direktori bantuan (indeks/site maps).
* **Sistem Pencarian (*Search Systems*):** Mekanisme pelolosan dari kegagalan navigasi graf, mengekspos dimensi pencarian faset ketika kedalaman graf melebihi ambang batas *Cognitive Load* ($Miller's\ Law: 7 \pm 2$).

### 2. Resolusi Polihierarki & Siklus pada Directed Acyclic Graph (DAG)
Dalam domain kompleks, satu entitas data secara logis dimiliki oleh beberapa departemen. Misalnya, *Faktur Pajak* dimiliki oleh *Akuntansi* dan *Kepatuhan Legal*.
* Jika direpresentasikan sebagai pohon murni (*Tree*), duplikasi data terjadi, memicu inkonsistensi state UI.
* Solusi arsitektural: Model navigasi harus berupa **Directed Acyclic Graph (DAG)**. Setiap simpul (*Node*) memiliki identitas unik ($ID_{node}$), dan relasi ditentukan oleh sisi berarah (*Edges*). 
* Mesin IA internal harus memiliki algoritma siklus deteksi (*cycle-detection*) berbasis DFS (*Depth First Search*) dengan pewarnaan simpul (White, Gray, Black) untuk memastikan tidak terjadi infinite loop saat breadcrumb direkonstruksi.

### 3. Jembatan Semantik (*Semantic Bridging Engine*)
Mekanisme internal untuk mengatasi *Gulf of Execution* (jarak antara intensi pengguna dengan tindakan fisik yang diizinkan UI) dan *Gulf of Evaluation* (jarak antara status sistem aktual dengan persepsi pengguna terhadap status tersebut):
* **Normalizer Intent:** Mengonversi istilah bahasa pengguna (misal: "Bikin invoice baru") menjadi rute kompilasi sistem (misal: `ENTITY_DISPATCH: INVOICE_AGGREGATE_ROOT -> CREATE`).
* **Canonical Resolver:** Saat pengguna mengakses simpul melalui jalur polihierarkis sekunder, resolver menetapkan satu jalur *canonical* untuk rendering breadcrumb dan sinkronisasi URL state, meminimalkan disorientasi spasial virtual.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Taksonomi Formal vs. Folksonomi dalam Desain Frontend
Arsitektur informasi enterprise menyeimbangkan dua paradigma kategorisasi:
1. **Taxonomy (Top-Down):** Struktur terkontrol ketat yang ditentukan oleh domain bisnis. Hubungan relasional antar-simpul bersifat monoton:
   $$\text{Parent}(A) \supset \text{Child}(B) \implies \forall x (x \in B \implies x \in A)$$
2. **Folksonomy (Bottom-Up):** Metadata berbasis penandaan terdesentralisasi (*social tagging* atau *user-defined labels*). Sifatnya non-hierarkis dan stokastik.

Frontend yang tangguh tidak mencampuradukkan kedua paradigma ini secara serampangan. Taksonomi mengendalikan kerangka kerja navigasi utama (*Core Shell UI*), sementara Folksonomi mengendalikan faset pencarian sekunder (*Filter Meshes*).

### Hukum Ergonomi Kognitif Terapan
* **Hukum Hick-Hyman:**
  $$T = b \cdot \log_2(n + 1)$$
  Waktu ($T$) yang diperlukan untuk membuat keputusan adalah fungsi logaritmik dari jumlah alternatif pilihan ($n$). Arsitektur informasi yang mengelompokkan 60 link ke dalam navigasi datar setinggi 1 tingkat akan memaksa waktu pemrosesan kognitif jauh lebih tinggi dibandingkan struktur bertingkat 2 dengan rasio percabangan (*branching factor*) $\le 7$ per level.
* **Information Foraging Theory:**
  Pengguna mengoptimalkan perolehan informasi relatif terhadap biaya interaksi menggunakan rasio:
  $$R = \frac{V}{C}$$
  Di mana $V$ adalah nilai informasi (*perceived value*) dan $C$ adalah biaya interaksi (*interaction cost* / waktu klik, scroll, scanning). Jika arsitektur informasi memiliki aroma informasi (*scent*) yang pudar pada tautan awal, $V$ diasumsikan mendekati nol oleh pengguna, memicu aksi *abandonment* (keluar dari alur aplikasi).

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi sistematis arsitektur informasi berbasis TypeScript: sebuah **DAG Information Engine** yang mendukung polihierarki, pencegahan siklus, evaluasi otorisasi dinamis, dan penentuan jalur *canonical* untuk rendering navigasi modern.

```typescript
// ia-core-types.ts
export type NodeId = string;
export type Role = 'ADMIN' | 'FINANCE' | 'COMPLIANCE' | 'VIEWER';

export interface UserContext {
  userId: string;
  roles: Set<Role>;
}

export interface IANodeMetadata {
  title: string;
  informationScentWeight: number; // Skala 0.0 - 1.0 (kekuatan semantik)
  requiredRoles: Role[];
  isCanonicalParent?: NodeId; // Menentukan parent hierarki kanonikal jika polihierarki
}

export interface IANode {
  id: NodeId;
  slug: string;
  metadata: IANodeMetadata;
  parentIds: NodeId[];
  childrenIds: NodeId[];
}

export interface BreadcrumbItem {
  id: NodeId;
  slug: string;
  title: string;
}

// ia-graph-engine.ts
export class InformationArchitectureGraph {
  private nodes: Map<NodeId, IANode> = new Map();

  public registerNode(node: IANode): void {
    if (this.nodes.has(node.id)) {
      throw new Error(`Integritas IA Rusak: Duplikasi simpul terdeteksi [${node.id}]`);
    }
    this.nodes.set(node.id, { ...node, childrenIds: [], parentIds: [...node.parentIds] });
  }

  public connectEdge(parentId: NodeId, childId: NodeId): void {
    const parent = this.nodes.get(parentId);
    const child = this.nodes.get(childId);

    if (!parent || !child) {
      throw new Error(`Edge gagal dibuat: Node referensi tidak eksis (${parentId} -> ${childId})`);
    }

    if (!parent.childrenIds.includes(childId)) {
      parent.childrenIds.push(childId);
    }
    if (!child.parentIds.includes(parentId)) {
      child.parentIds.push(parentId);
    }

    // Jalankan verifikasi siklus setelah penambahan sisi
    this.assertAcyclic();
  }

  private assertAcyclic(): void {
    const visited = new Set<NodeId>();
    const recursionStack = new Set<NodeId>();

    const dfs = (currentNodeId: NodeId): boolean => {
      visited.add(currentNodeId);
      recursionStack.add(currentNodeId);

      const node = this.nodes.get(currentNodeId);
      if (node) {
        for (const childId of node.childrenIds) {
          if (!visited.has(childId)) {
            if (dfs(childId)) return true;
          } else if (recursionStack.has(childId)) {
            return true; // Siklus terdeteksi!
          }
        }
      }

      recursionStack.delete(currentNodeId);
      return false;
    };

    for (const nodeId of this.nodes.keys()) {
      if (!visited.has(nodeId)) {
        if (dfs(nodeId)) {
          throw new Error(`Integritas IA Kritis: Terdeteksi Siklus Sirkular pada simpul [${nodeId}]`);
        }
      }
    }
  }

  public resolvePath(targetId: NodeId, context: UserContext): BreadcrumbItem[] {
    const targetNode = this.nodes.get(targetId);
    if (!targetNode) {
      throw new Error(`Node target [${targetId}] tidak ditemukan pada graf.`);
    }

    if (!this.evaluateAccess(targetNode, context)) {
      throw new Error(`Akses Ditolak: Kredensial tidak memadai untuk simpul [${targetId}]`);
    }

    const path: BreadcrumbItem[] = [];
    let current: IANode | undefined = targetNode;

    while (current) {
      path.unshift({
        id: current.id,
        slug: current.slug,
        title: current.metadata.title,
      });

      if (current.parentIds.length === 0) {
        break; // Mencapai Root Node
      }

      // Selesaikan Polihierarki menggunakan metadata kanonikal atau parent valid pertama
      const canonicalParentId = current.metadata.isCanonicalParent;
      let nextParentId: NodeId | undefined;

      if (canonicalParentId && current.parentIds.includes(canonicalParentId)) {
        nextParentId = canonicalParentId;
      } else {
        // Ambil parent pertama yang lolos otorisasi konteks
        nextParentId = current.parentIds.find((pId) => {
          const parentNode = this.nodes.get(pId);
          return parentNode ? this.evaluateAccess(parentNode, context) : false;
        });
      }

      current = nextParentId ? this.nodes.get(nextParentId) : undefined;
    }

    return path;
  }

  public evaluateAccess(node: IANode, context: UserContext): boolean {
    if (node.metadata.requiredRoles.length === 0) return true;
    return node.metadata.requiredRoles.some((role) => context.roles.has(role));
  }

  public getSubtreeForUser(rootId: NodeId, context: UserContext): Partial<IANode> | null {
    const rootNode = this.nodes.get(rootId);
    if (!rootNode || !this.evaluateAccess(rootNode, context)) return null;

    const accessibleChildren = rootNode.childrenIds
      .map((childId) => this.getSubtreeForUser(childId, context))
      .filter((child): child is Partial<IANode> => child !== null);

    return {
      id: rootNode.id,
      slug: rootNode.slug,
      metadata: rootNode.metadata,
      childrenIds: accessibleChildren.map((c) => c.id!),
    };
  }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi mekanis dari implementasi `InformationArchitectureGraph`:

1. **Baris 2–18 (`ia-core-types.ts`):** 
   Mendefinisikan tipe primitif penopang arsitektur. Penggunaan `Set<Role>` pada `UserContext` menjamin lookup otorisasi dalam kompleksitas waktu $O(1)$. Properti `informationScentWeight` menjadi dasar heuristik perutean cerdas, sedangkan `isCanonicalParent` memecahkan ambiguitas polihierarkis.
2. **Baris 22–33 (`registerNode`):**
   Mendaftarkan simpul secara defensif. Operasi memeriksa keunikan ID secara instan pada memori $O(1)$ `Map`. Mengkloning `parentIds` untuk memastikan tidak ada referensi eksternal yang merusak mutasi state secara acak.
3. **Baris 35–52 (`connectEdge`):**
   Membangun relasi dwiarah antarsimpul. Tidak hanya menghubungkan pointer relasi, metode ini mewajibkan pemanggilan `this.assertAcyclic()`. Ini mencegah regresi arsitektural fatal di mana pengguna dapat terjebak dalam putaran navigasi breadcrumb tak terbatas.
4. **Baris 54–84 (`assertAcyclic`):**
   Algoritma deteksi siklus terisolasi berbasis DFS. Menggunakan struktur `recursionStack` aktif. Ketika algoritma menyusuri simpul anak dan mendapati simpul tersebut sudah ada di `recursionStack` pemanggilan saat ini, terjadi kontradiksi hierarki (Back-edge pada directed graph). Sistem secara keras melempar error (*fail-fast*), mencegah compile build UI korup.
5. **Baris 86–126 (`resolvePath`):**
   Mekanisme penelusuran balik (*Backtracking Resolution*) breadcrumb. Alih-alih mengandalkan pembacaan URL mentah (`window.location.pathname.split('/')`), sistem menelusuri simpul aktual ke atas.
6. **Baris 112–122 (Resolusi Jalur Polihierarkis):**
   Menyelesaikan dilema simpul yang memiliki banyak induk. Pertama, mesin memeriksa apakah perancang telah menentukan simpul kanonikal (`isCanonicalParent`). Jika tidak, mesin beralih ke pengecekan berbasis hak akses runtime menggunakan `find()` terhadapan peran pengguna saat ini.
7. **Baris 133–147 (`getSubtreeForUser`):**
   Penyaringan pohon navigasi secara rekursif (*Top-Down Tree Pruning*). Menghasilkan pohon presentasi virtual yang aman. Simpul yang tidak berhak dilihat oleh pengguna tidak hanya disembunyikan secara kosmetik di UI; simpul tersebut dieliminasi dari representasi graf di level memori, mencegah kebocoran struktur data internal melalui DOM inspection.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario: Rekonstruksi Navigasi Multi-Tenant Enterprise Platform (FinCloud Global)
* **Latar Belakang:** FinCloud Global memiliki aplikasi perbankan B2B dengan 400+ halaman menu. Sistem awal menggunakan menu multi-level statis (JSON hardcoded dengan 5 lapis submenu melayang).
* **Masalah Kritis Pengguna:**
  * Pengguna tingkat manajer keuangan tersesat saat ingin mengesahkan transaksi. Rata-rata *Time-to-Task-Completion* (TTC) mencapai 42 detik.
  * *Disorientasi Mental:* Pengguna menganggap modul *Laporan Pajak* adalah bagian dari menu *Kepatuhan Legal*, sementara sistem backend mengelompokkannya di bawah modul *Pembukuan Akuntansi*. Hal ini menghasilkan 28% tiket bantuan bulanan yang menanyakan lokasi dokumen.
  * Tingkat klik salah (*Misclick Rate*) mencapai 31% akibat *flyout menu hover* yang tertutup tidak sengaja saat kursor bergerak miring (kegagalan Fitts' Law dan Steering Law).
* **Solusi Rekayasa:**
  * Membongkar menu statis dan mengimplementasikan **Polihierarchical Faceted Graph Architecture**.
  * Modul *Laporan Pajak* diregistrasi ulang dengan dua parent node yang valid (*Akuntansi* dan *Kepatuhan*).
  * Mengganti hover cascade flyout dengan kombinasi: **Command Palette / Semantic Search Engine** dan **Breadcrumb Graph Navigator** kontekstual.
  * Hasil: Waktu pencarian turun dari 42 detik menjadi 8,4 detik, misclick rate turun hingga < 2%, dan retensi penggunaan modul audit naik 64%.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah implementasi skala produksi mesin resolusi Arsitektur Informasi dinamis berbasis Custom Hook React dan State Graph.

```tsx
// IAProvider.tsx
import React, { createContext, useContext, useMemo, ReactNode } from 'react';

export type SystemRole = 'AUDITOR' | 'TREASURY' | 'ADMIN';

export interface DomainEntityNode {
  id: string;
  slug: string;
  label: string;
  parents: string[];
  canonicalParent?: string;
  roles: SystemRole[];
  componentKey: string;
}

interface IAGraphContextValue {
  resolveCrumbs: (currentNodeId: string) => Array<{ label: string; path: string }>;
  getAccessibleNavigationTree: () => DomainEntityNode[];
  hasAccess: (nodeId: string) => boolean;
}

const REGISTRY: Record<string, DomainEntityNode> = {
  root: { id: 'root', slug: '', label: 'Beranda Eksekutif', parents: [], roles: [] },
  treasury: { id: 'treasury', slug: 'treasury', label: 'Perbendaharaan', parents: ['root'], roles: ['TREASURY', 'ADMIN'] },
  compliance: { id: 'compliance', slug: 'compliance', label: 'Kepatuhan & Regulasi', parents: ['root'], roles: ['AUDITOR', 'ADMIN'] },
  tax_reports: {
    id: 'tax_reports',
    slug: 'tax-reports',
    label: 'Pelaporan Pajak Global',
    parents: ['treasury', 'compliance'], // Polihierarki
    canonicalParent: 'treasury',
    roles: ['TREASURY', 'AUDITOR', 'ADMIN'],
  },
  audit_logs: {
    id: 'audit_logs',
    slug: 'audit-logs',
    label: 'Catatan Jejak Audit',
    parents: ['compliance'],
    roles: ['AUDITOR', 'ADMIN'],
  },
} as const;

const IAGraphContext = createContext<IAGraphContextValue | null>(null);

interface IAProviderProps {
  children: ReactNode;
  currentUserRoles: SystemRole[];
}

export const IAProvider: React.FC<IAProviderProps> = ({ children, currentUserRoles }) => {
  const userRoleSet = useMemo(() => new Set(currentUserRoles), [currentUserRoles]);

  const hasAccess = useMemo(() => {
    return (nodeId: string): boolean => {
      const node = REGISTRY[nodeId];
      if (!node) return false;
      if (node.roles.length === 0) return true;
      return node.roles.some((r) => userRoleSet.has(r));
    };
  }, [userRoleSet]);

  const resolveCrumbs = useMemo(() => {
    return (currentNodeId: string): Array<{ label: string; path: string }> => {
      const result: Array<{ label: string; path: string }> = [];
      let activeNode = REGISTRY[currentNodeId];

      if (!activeNode || !hasAccess(currentNodeId)) return [];

      const accumulatedPathSegments: string[] = [];

      while (activeNode) {
        accumulatedPathSegments.unshift(activeNode.slug);
        result.unshift({
          label: activeNode.label,
          path: '/' + accumulatedPathSegments.filter(Boolean).join('/'),
        });

        if (activeNode.parents.length === 0) break;

        // Tentukan navigasi ke atas via Canonical Parent atau fallback parent terotorisasi
        const nextParentId =
          activeNode.canonicalParent && hasAccess(activeNode.canonicalParent)
            ? activeNode.canonicalParent
            : activeNode.parents.find((p) => hasAccess(p));

        activeNode = nextParentId ? REGISTRY[nextParentId] : undefined as unknown as DomainEntityNode;
      }

      return result;
    };
  }, [hasAccess]);

  const getAccessibleNavigationTree = useMemo(() => {
    return (): DomainEntityNode[] => {
      return Object.values(REGISTRY).filter((node) => hasAccess(node.id));
    };
  }, [hasAccess]);

  const value = useMemo(
    () => ({ resolveCrumbs, getAccessibleNavigationTree, hasAccess }),
    [resolveCrumbs, getAccessibleNavigationTree, hasAccess]
  );

  return <IAGraphContext.Provider value={value}>{children}</IAGraphContext.Provider>;
};

export const useIA = (): IAGraphContextValue => {
  const ctx = useContext(IAGraphContext);
  if (!ctx) throw new Error('useIA harus dieksekusi di dalam lingkup IAProvider');
  return ctx;
};

// NavBreadcrumbs.tsx
export const NavBreadcrumbs: React.FC<{ activeNodeId: string }> = ({ activeNodeId }) => {
  const { resolveCrumbs } = useIA();
  const crumbs = resolveCrumbs(activeNodeId);

  if (crumbs.length === 0) {
    return null;
  }

  return (
    <nav aria-label="Breadcrumb" className="breadcrumb-nav">
      <ol style={{ display: 'flex', listStyle: 'none', gap: '8px', padding: 0 }}>
        {crumbs.map((crumb, index) => {
          const isLast = index === crumbs.length - 1;
          return (
            <li key={crumb.path} style={{ display: 'flex', alignItems: 'center' }}>
              {index > 0 && <span style={{ margin: '0 8px', color: '#888' }}>/</span>}
              {isLast ? (
                <span aria-current="page" style={{ fontWeight: 600, color: '#111' }}>
                  {crumb.label}
                </span>
              ) : (
                <a href={crumb.path} style={{ textDecoration: 'none', color: '#0066cc' }}>
                  {crumb.label}
                </a>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
};
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

Dalam merekayasa struktur Arsitektur Informasi pada platform web, pemilihan model topologi data menentukan skalabilitas dan performa kognitif sistem:

| Parameter Evaluasi | Monolithic Strict Tree (Pohon Murni) | Polyhierarchical DAG (Graf Terarah) | Flat Faceted Engine (Matriks Faset) |
| :--- | :--- | :--- | :--- |
| **Kompleksitas State** | **Rendah:** Cukup array atau parent-id tunggal. | **Tinggi:** Perlu cycle-check & canonical resolution. | **Sangat Tinggi:** Multi-dimensi state combinatorial. |
| **Beban Kognitif Pengguna** | **Tinggi:** Pengguna dipaksa menebak parent tunggal yang benar. | **Rendah:** Informasi ditemukan di semua lokasi mental yang logis. | **Minimal:** Pengguna menyaring dimensi tanpa memikirkan lokasi. |
| **Biaya Memori Runtime** | $O(N)$ node traversal. Sangat cepat. | $O(V + E)$ vertex & edge overhead. Sedikit overhead memori. | $O(N \cdot M)$ di mana $M$ adalah total kombinasi filter dimensi. |
| **Dampak Otorisasi (RBAC)** | Trivial: Hide parent otomatis hide seluruh subtree anak. | Kompleks: Node anak tetap terlihat jika ada jalur alternatif valid. | Terisolasi: Saring item array berdasarkan filter predicate. |
| **Kesesuaian Penggunaan** | Situs marketing sederhana / Dokumen statis linear. | **Sistem ERP, FinTech, & SaaS Enterprise Multi-Tenant.** | E-Commerce Skala Besar & Marketplace Multi-Atribut. |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. The Broken Canonical Reference Trap
* **Mekanisme Kegagalan:** Simpul $A$ menentukan Simpul $B$ sebagai `canonicalParent`. Namun, otorisasi Simpul $B$ dibatasi hanya untuk peran `ADMIN`. Ketika peran `AUDITOR` mengakses Simpul $A$, algoritma mencoba memetakan breadcrumb ke Simpul $B$, mendeteksi penolakan akses, dan memicu *null-pointer dereference* atau rantai breadcrumb putus di tengah jalan (*orphan route*).
* **Mitigasi:** Fungsi `resolveCrumbs` tidak boleh langsung berasumsi bahwa `canonicalParent` dapat diakses. Wajib ada rantai fallback terurut: periksa izin kanonikal $\to$ jika gagal, telusuri `parents` sekunder yang lolos otorisasi $\to$ jika semua gagal, lakukan terminasi langsung ke `root`.

### 2. Deep Linking Semantic Mismatch
* **Mekanisme Kegagalan:** Pengguna menerima tautan URL `/compliance/tax-reports`. Namun state lokal aplikasi diinisialisasi dengan konteks modul `/treasury`. Terjadi rendering ganda atau state context konflik, di mana sidebar membuka pohon Treasury tetapi breadcrumb menampilkan Compliance.
* **Mitigasi:** URL harus bertindak sebagai cerminan deterministik dari resolusi simpul kanonikal, atau Router harus mendekode slug menjadi `nodeId` unik terlebih dahulu sebelum komponen sidebar dirender, menyinkronkan UI state secara unidireksional.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. URL Path Coupled Direct to Database Entities
* **Salah:** Membuat struktur URL mengikuti skema tabel relasional database: `/app/tbl-trn-invoices-v2/det/12984`.
* **Benar:** Pisahkan URI dari rancangan penyimpanan. Desain URL berdasarkan model mental manusia: `/app/finance/invoices/12984`. Transformasikan URI semantik ke query database di lapisan API gateway/BFF.

### 2. Designing Navigation Based on Company Org Chart
* **Salah (Conway's Law Anti-Pattern):** Membuat tab navigasi berdasarkan divisi perusahaan pengembang: "Menu Tim A", "Menu Tim B". Pengguna eksternal tidak peduli divisi mana yang membuat fitur tersebut.
* **Benar:** Bangun Arsitektur Informasi berbasis *Job-to-be-Done* (JTBD) dan *Task Mental Models*: "Penagihan", "Persetujuan", "Audit".

### 3. Shallow Mega-Menu Explosion
* **Salah:** Menampilkan 150 item tautan dalam satu layar dropdown mega-menu demi menghindari navigasi bertingkat. Ini melanggar Hick-Hyman Law dan memicu *Cognitive Paralysis* (pengguna bingung memilih).
* **Benar:** Batasi percabangan visual hingga level primer $\le 7$ kategori utama. Gunakan kombinasi *Command Bar* ($Cmd+K$) dan *Predictive Contextual Anchors*.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

* **Card Sorting Validation:** Wajib melakukan uji *Open Card Sorting* dan *Closed Card Sorting* minimal pada 30 pengguna perwakilan sebelum membekukan graf taksonomi navigasi ke dalam arsitektur kode frontend.
* **Tree Testing (Reverse Card Sorting):** Evaluasi kekuatan Information Scent menggunakan Treejack/Tree Testing tanpa visual UI. Jika kesuksesan navigasi berbasis teks polos $< 80\%$, desain arsitektur informasi ditolak sebelum masuk tahap sprint implementasi CSS/UI.
* **Semantic URL Hygiene:** URL harus *human-readable*, deterministik, sepenuhnya huruf kecil (*lowercase*), dipisahkan dengan tanda hubung (*kebab-case*), dan tidak mengandung ID internal yang tidak perlu dimengerti manusia.
* **WAI-ARIA Wayfinding:** Implementasikan landmark ARIA semantik: `<nav aria-label="Navigasi Utama">`, `<nav aria-label="Breadcrumb">`, dan atur atribut `aria-current="page"` secara akurat pada simpul aktif.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

Pada aplikasi enterprise dengan puluhan ribu entitas direktori, melakukan