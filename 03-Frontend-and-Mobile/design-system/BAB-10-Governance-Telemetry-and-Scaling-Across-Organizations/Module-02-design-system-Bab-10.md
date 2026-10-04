# BAB 10: Governance, Telemetry, and Scaling Across Organizations
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Merancang dan Mengimplementasikan Arsitektur Telemetri Dua Lapis (Dual-Layer Telemetry)**: Membangun sistem monitoring adopsi *Design System* (DS) berbasis *Static Code Analysis* (AST-based scanner) pada CI/CD pipeline dan *Runtime Performance/Usage Beaconing* tanpa mengorbankan Core Web Vitals (INP, LCP, CLS).
2. **Membangun Federated Governance Model**: Mengorkestrasi siklus hidup komponen lintas ratusan *repository* dan puluhan *squad* melalui standardisasi RFC (Request for Comments), automated semantic versioning, dan dynamic component deprecation engines.
3. **Mengukur Metrik Adopsi dan Deviasi Tingkat Enterprise**: Menghitung secara matematis *Component Adoption Rate*, *Hardcoded Style Divergence Index*, dan *Prop Utilization Efficiency* untuk menghasilkan justifikasi ROI (*Return on Investment*) bagi tim platform.
4. **Mengotomatisasi Deprecations & Migration Pathways**: Mengembangkan sistem *automated codemods* menggunakan AST transforms untuk mereduksi *migration lead time* dari level bulan menjadi hitungan jam.

---

### 2. Prerequisite

Peserta wajib menguasai:
*   TypeScript tingkat lanjut (AST structures, compiler APIs, conditional types, template literal types).
*   Arsitektur Monorepo tingkat enterprise (Nx, Turborepo, pnpm workspaces).
*   Mekanisme Parser & AST (Abstract Syntax Tree) JavaScript/TypeScript (menggunakan `@babel/parser`, `@babel/traverse`, atau TS Compiler API).
*   Observability & Telemetry standards (OpenTelemetry, W3C Web Performance APIs, `navigator.sendBeacon`).
*   Infrastruktur CI/CD modern (GitHub Actions, GitLab CI) dan penulisan CLI toolings berbasis Node.js.

---

### 3. Concept & Internal Architecture

Skalabilitas *Design System* pada organisasi multi-brand dan multi-squad tidak ditentukan oleh estetika komponen, melainkan oleh keandalan sistem tata kelola (*governance*) dan visibilitas data adopsi (*telemetry*). Tanpa telemetri yang presisi, tim platform beroperasi secara buta (*blind iteration*), memicu fragmentasi UI, duplikasi komponen, dan pembengkakan utang teknis (*technical debt*).

Arsitektur produksi governance dan telemetri enterprise terbagi ke dalam empat subsistem terintegrasi:

```
+---------------------------------------------------------------------------------------+
|                              ENTERPRISE GOVERNANCE ENGINE                             |
+---------------------------------------------------------------------------------------+
|  [ RFC Engine & Schema Validator ] <---> [ Semantic Release & Deprecation Registry ]  |
+---------------------------------------------------------------------------------------+
                                           |
                                           v
+------------------------------------------+--------------------------------------------+
| STATIC TELEMETRY LAYER (CI/CD Pipeline)  |  RUNTIME TELEMETRY LAYER (Production App)  |
+------------------------------------------+--------------------------------------------+
| - AST Component Ingestion Scanner        | - Zero-Cost Performance Observer           |
| - Token Hardcoding Static Linter         | - Dynamic Prop-usage Beaconing             |
| - Git Diff & Ownership Attribution       | - Interaction & Error Boundary Collector   |
+------------------------------------------+--------------------------------------------+
                    |                                             |
                    v                                             v
        [ AST Metrics Collector ]                    [ Ingestion Gateway HTTP/3 ]
                    \                                             /
                     \                                           /
                      v                                         v
+---------------------------------------------------------------------------------------+
|                     DESIGN SYSTEM TELEMETRY DATA PLATFORM                             |
|       (ClickHouse / BigQuery + dbt Modeling + Grafana / Custom Internal Portal)       |
+---------------------------------------------------------------------------------------+
```

#### A. Dual-Layer Telemetry Architecture

1.  **Static Analysis Telemetry (Build-Time / CI)**:
    *   Mengevaluasi basis kode consumer menggunakan traversal AST.
    *   Mendeteksi: Frekuensi impor komponen, properti (props) yang digunakan vs *deprecated*, instansiasi inline style yang memotong token resmi (*style escape hatches*), dan deteksi duplikasi komponen lokal (*rogue components*).
    *   *Kelebihan*: Cakupan 100% dari seluruh kode yang tersimpan di repositori; tidak berdampak pada runtime user.
    *   *Limitasi*: Tidak dapat mendeteksi apakah kode yang diimpor benar-benar dieksekusi atau merupakan *dead code*.

2.  **Runtime Telemetry (Client-Side / Production)**:
    *   Menggunakan instrumentasi ringan (*lightweight beaconing*) yang dipicu secara asynchronous melalui API browser non-blocking (`requestIdleCallback`, `navigator.sendBeacon`).
    *   Merekam metrik: Render count, Interaction to Next Paint (INP) degradasi per komponen, runtime accessibility violations, dan dynamic component crashes via Component Error Boundaries.
    *   *Kelebihan*: Mengukur interaksi nyata pengguna akhir (*real-user metrics*).
    *   *Limitasi*: Berpotensi menimbulkan penalti *network/performance overhead* jika tidak didesain dengan teknik batching dan sampling probabilistik yang ketat.

#### B. Federated Governance Topology

Pada skala puluhan tim engineering, model tata kelola sentralistik (*centralized bottleneck*) pasti gagal. Arsitektur produksi mengadopsi model **Federated Governance**:

*   **Core Platform Squad**: Bertanggung jawab atas primitif arsitektur, token inti (*global design tokens*), sistem build, linter, dan infrastruktur telemetri.
*   **Domain / Vertical Guilds**: Squad produk yang memiliki domain spesifik (misal: Checkout, Auth, Backoffice) memiliki hak kontribusi (*co-ownership*) untuk membangun *Domain-Specific Components* yang mewarisi (*inherit*) token inti melalui arsitektur multi-tier tokens.
*   **Decentralized Component RFC**: Tiap perubahan antarmuka publik komponen harus melalui schema kontrak kontraktual (JSON Schema / Type Definitions) sebelum disetujui via *automated pull request checks*.

---

### 4. Why & What

| Dimensi | Mengapa Dibutuhkan (Why) | Apa yang Diterapkan (What) |
| :--- | :--- | :--- |
| **Visibility** | Tim DS tidak mengetahui komponen mana yang sering digunakan, rusak, atau ditinggalkan oleh squad aplikasi. | Static AST Scanners & Production Usage Telemetry Pipeline. |
| **Deprecation** | Migrasi breaking changes seringkali mangkrak selama bertahun-tahun di enterprise codebase. | AST Codemods terotomatisasi & Semantic Deprecation Engine yang memicu peringatan build terukur. |
| **Consistency** | Developer produk sering memotong sistem dengan inline styling (`style={{ color: '#ff0000' }}` atau Tailwind arbitrer). | Token Drift Linting Engine yang melacak deviasi token secara persentase di CI. |
| **Scalability** | Satu tim platform terpusat menjadi bottleneck bagi ratusan developer lain yang menunggu fitur baru. | Federated Contribution RFC Framework yang diatur via CI tooling otomatis. |

---

### 5. How (Workflow Detail)

Alur kerja monitoring adopsi, deteksi deviasi, dan rilis enterprise:

```
[ Developer Commit ] 
        |
        v
[ Pre-Push Hook: Local AST Fast-Lint ]
        |
        v
[ CI Job: Design System Telemetry Ingestion ]
  |---> 1. Parse TSX files to AST using @babel/parser
  |---> 2. Traverse nodes via Babel Visitor
  |---> 3. Identify ImportDeclarations from '@enterprise-ds/*'
  |---> 4. Extract JSXOpeningElement & match props with Deprecation Registry
  |---> 5. Detect local overrides (style props, className regex bypass)
  |---> 6. Generate JSON Telemetry Payload
        |
        v
[ Telemetry Ingestion API (Edge Worker) ]
        |
        v
[ Analytical Storage (ClickHouse/BigQuery) ]
        |
        v
[ Automated Migration Trigger ]
  |---> If Deprecation Usage > 0: Generate automated pull request with Codemod
```

1.  **Fase 1: Kompilasi & Parsing AST**: Setiap PR yang dibuka menjalankan CLI telemetry scanner. Scanner mengabaikan file tes dan storybook, mem-parsing file produksi menjadi AST.
2.  **Fase 2: Identifikasi Semantik**: Mesin mengekstrak signature import, props utilization mapping, dan mendeteksi token bypass.
3.  **Fase 3: Ingestion**: Metrik dikirim dalam format terkompresi ke telemetry gateway, ditandai dengan metadata: `repository_id`, `squad_owner`, `commit_sha`, dan `branch`.
4.  **Fase 4: Governance Gate**: Jika PR memperkenalkan komponen yang sudah masuk status *Terminal Deprecation*, pipeline CI akan mengembalikan status `Exit Code 1` (Break the build), memaksa developer menjalankan codemod yang telah disediakan.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sistem Sensor dan Lalu Lintas Kereta Api Cepat
Bayangkan Design System sebagai jaringan kereta api nasional:
*   *Core DS Components* adalah rel, wesel, dan lokomotif standar.
*   *Squad Produk* adalah operator regional yang menjalankan gerbong.
*   Jika tidak ada sensor di jalur (Static Telemetry), regulator tidak tahu bahwa operator regional memodifikasi gerbong secara ilegal dengan suku cadang non-standar (Token Drift / Escape Hatches).
*   Jika tidak ada sensor kecepatan dan beban real-time (Runtime Telemetry), regulator tidak tahu titik wesel mana yang aus atau mengalami getaran berlebih (INP bottlenecks / Render performance degradation).
*   *Governance* adalah protokol persinyalan: ketika wesel lama diganti (Deprecation), sistem mengirim instruksi mekanis otomatis ke seluruh stasiun (Automated Codemods) untuk mengalihkan jalur tanpa menghentikan lalu lintas.

#### Diagram Arsitektur Telemetri Terdistribusi

```
+-----------------------------------------------------------------------------------+
| REPOSITORY KONSUMEN (Contoh: Checkout-App)                                         |
|                                                                                   |
|  [ File.tsx ] ---> ( Babel Parser )                                               |
|                          |                                                        |
|                          v                                                        |
|                    [ AST Tree ]                                                   |
|                          |                                                        |
|           +--------------+--------------+                                         |
|           |                             |                                         |
|           v                             v                                         |
|     (Imports Track)             (Overridden Styles)                               |
|   @enterprise-ds/button         style={{ margin: 13 }}                             |
|           |                             |                                         |
|           +--------------+--------------+                                         |
|                          |                                                        |
|                          v                                                        |
|             [ Telemetry Aggregator ]                                              |
|                          |                                                        |
|           +--------------+--------------+                                         |
|           |                             |                                         |
|           v (CI Environment)            v (Browser Runtime)                       |
|     [ HTTP POST /metrics/ci ]      [ navigator.sendBeacon ]                       |
+-----------+-----------------------------+-----------------------------------------+
            |                             |
            +--------------+--------------+
                           |
                           v
+-----------------------------------------------------------------------------------+
| TELEMETRY INGESTION GATEWAY (Edge / Serverless)                                   |
| - Signature Validation (HMAC)                                                     |
| - Deduplication & Buffering                                                       |
+--------------------------+--------------------------------------------------------+
                           |
                           v
+-----------------------------------------------------------------------------------+
| CLICKHOUSE STORAGE ENGINE                                                         |
| - Table: static_component_usage (repo, component, prop, is_deprecated, timestamp) |
| - Table: runtime_component_perf (component, render_time_ms, inp_impact, session)  |
+-----------------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Deteksi Sederhana Import DS via AST

Script dasar menggunakan TypeScript Compiler API untuk membaca penggunaan nama komponen:

```typescript
import * as ts from 'typescript';

const sourceCode = `
  import { Button, Modal } from '@enterprise-ds/core';
  import { CustomCard } from './components';

  export const View = () => <Button variant="primary">Submit</Button>;
`;

const sourceFile = ts.createSourceFile(
  'component.tsx',
  sourceCode,
  ts.ScriptTarget.Latest,
  true,
  ts.ScriptKind.TSX
);

function inspectNodes(node: ts.Node) {
  if (ts.isImportDeclaration(node)) {
    const moduleSpecifier = node.moduleSpecifier.getText(sourceFile);
    if (moduleSpecifier.includes('@enterprise-ds/core')) {
      const namedBindings = node.importClause?.namedBindings;
      if (namedBindings && ts.isNamedImports(namedBindings)) {
        namedBindings.elements.forEach((el) => {
          console.log(`[SIMPLE TRACKER] Detected DS Component: ${el.name.getText(sourceFile)}`);
        });
      }
    }
  }
  ts.forEachChild(node, inspectNodes);
}

inspectNodes(sourceFile);
```

#### B. Practical Example (Production-Grade): Enterprise AST Scanner CLI & Runtime Beacon Engine

Berikut adalah implementasi sistem pemantauan adopsi end-to-end yang tangguh untuk lingkungan produksi.

##### 1. Production Static Scanner CLI (`telemetry-scanner.ts`)

```typescript
import fs from 'node:fs';
import path from 'node:path';
import { parse } from '@babel/parser';
import traverse from '@babel/traverse';
import { globSync } from 'glob';

interface ComponentUsageMetrics {
  componentName: string;
  sourceModule: string;
  propsUsed: string[];
  hasCustomStyleOverride: boolean;
  filePath: string;
  lineNumber: number;
}

interface ScanReport {
  repoName: string;
  scanTimestamp: string;
  metrics: ComponentUsageMetrics[];
  summary: {
    totalDsInstances: number;
    hardcodedOverrideCount: number;
  };
}

export class DesignSystemScanner {
  private baseDir: string;
  private targetModules: Set<string>;

  constructor(baseDir: string, targetModules: string[]) {
    this.baseDir = baseDir;
    this.targetModules = new Set(targetModules);
  }

  public runScan(repoName: string): ScanReport {
    const filePatterns = path.join(this.baseDir, '**/*.{tsx,jsx}');
    const files = globSync(filePatterns, {
      ignore: ['**/node_modules/**', '**/dist/**', '**/*.test.{tsx,jsx}', '**/*.stories.{tsx,jsx}'],
    });

    const metrics: ComponentUsageMetrics[] = [];

    for (const filePath of files) {
      const fileContent = fs.readFileSync(filePath, 'utf-8');
      this.analyzeFile(fileContent, filePath, metrics);
    }

    const hardcodedOverrideCount = metrics.filter((m) => m.hasCustomStyleOverride).length;

    return {
      repoName,
      scanTimestamp: new Date().toISOString(),
      metrics,
      summary: {
        totalDsInstances: metrics.length,
        hardcodedOverrideCount,
      },
    };
  }

  private analyzeFile(content: string, filePath: string, outMetrics: ComponentUsageMetrics[]): void {
    let ast: ReturnType<typeof parse>;
    try {
      ast = parse(content, {
        sourceType: 'module',
        plugins: ['typescript', 'jsx'],
      });
    } catch {
      // Mengabaikan file yang gagal di-parse (misal syntax error lokal)
      return;
    }

    // Map lokal: importedName -> { originalName, sourceModule }
    const localImportRegistry = new Map<string, { originalName: string; sourceModule: string }>();

    traverse(ast, {
      ImportDeclaration: (astPath) => {
        const source = astPath.node.source.value;
        if (this.targetModules.has(source)) {
          astPath.node.specifiers.forEach((specifier) => {
            if (specifier.type === 'ImportSpecifier') {
              const localName = specifier.local.name;
              const originalName =
                specifier.imported.type === 'Identifier'
                  ? specifier.imported.name
                  : specifier.imported.value;
              localImportRegistry.set(localName, { originalName, sourceModule: source });
            }
          });
        }
      },

      JSXOpeningElement: (astPath) => {
        const node = astPath.node;
        let tagName = '';

        if (node.name.type === 'JSXIdentifier') {
          tagName = node.name.name;
        } else if (node.name.type === 'JSXMemberExpression') {
          // Mendukung nested pattern: Dropdown.Item
          tagName = `${node.name.object.name}.${node.name.property.name}`;
        }

        const registration = localImportRegistry.get(tagName);
        if (registration) {
          const propsUsed: string[] = [];
          let hasCustomStyleOverride = false;

          node.attributes.forEach((attr) => {
            if (attr.type === 'JSXAttribute' && attr.name.type === 'JSXIdentifier') {
              const propName = attr.name.name;
              propsUsed.push(propName);

              // Deteksi perusakan token: penggunaan inline 'style' atau styling escape hatch 'css'
              if (propName === 'style' || propName === 'css' || propName === 'className') {
                if (propName === 'style') {
                  hasCustomStyleOverride = true;
                }
                // Jika className memuat hex codes atau arbitrer Tailwind yang melewati token
                if (attr.value && attr.value.type === 'StringLiteral') {
                  if (/(#([0-9a-fA-F]{3}|[0-9a-fA-F]{6}))|(\[#[^\]]+\])/.test(attr.value.value)) {
                    hasCustomStyleOverride = true;
                  }
                }
              }
            }
          });

          outMetrics.push({
            componentName: registration.originalName,
            sourceModule: registration.sourceModule,
            propsUsed,
            hasCustomStyleOverride,
            filePath: path.relative(this.baseDir, filePath),
            lineNumber: node.loc?.start.line ?? 0,
          });
        }
      },
    });
  }
}

// Inisialisasi Eksekusi CLI
if (require.main === module) {
  const scanner = new DesignSystemScanner(process.cwd(), ['@enterprise-ds/core', '@enterprise-ds/patterns']);
  const report = scanner.runScan('payment-checkout-frontend');
  fs.writeFileSync('ds-telemetry-report.json', JSON.stringify(report, null, 2));
  console.log(`Scan Selesai: Ditemukan ${report.summary.totalDsInstances} instansiasi DS.`);
}
```

##### 2. Low-Overhead Runtime Telemetry Wrapper (`DesignSystemTelemetryProvider.tsx`)

Komponen runtime pembungkus (atau instrumentasi higher-order) yang memanfaatkan *non-blocking execution queues* dan *low-priority network payloads*.

```tsx
import React, { useEffect, useRef } from 'react';

interface RuntimeTelemetryPayload {
  component: string;
  lifecycle: 'mount' | 'interaction';
  renderDurationMs: number;
  appVersion: string;
  squad: string;
}

const METRIC_ENDPOINT = 'https://telemetry.internal.enterprise.com/v1/beacon';
const BATCH_INTERVAL_MS = 5000;
const metricQueue: RuntimeTelemetryPayload[] = [];

// Mekanisme Pengiriman Non-Blocking dengan fallback aman
function flushMetrics() {
  if (metricQueue.length === 0) return;

  const payload = JSON.stringify({ batch: [...metricQueue] });
  metricQueue.length = 0; // Clear queue

  if (typeof navigator !== 'undefined' && 'sendBeacon' in navigator) {
    const success = navigator.sendBeacon(METRIC_ENDPOINT, payload);
    if (!success) {
      // Fallback Fetch KeepAlive jika sendBeacon buffer penuh
      fetch(METRIC_ENDPOINT, {
        method: 'POST',
        body: payload,
        headers: { 'Content-Type': 'application/json' },
        keepalive: true,
      }).catch(() => {/* Redam telemetry network error */});
    }
  }
}

// Interval Flusher otomatis berjalan pada Idle Period
if (typeof window !== 'undefined') {
  setInterval(() => {
    if ('requestIdleCallback' in window) {
      window.requestIdleCallback(() => flushMetrics());
    } else {
      setTimeout(flushMetrics, 0);
    }
  }, BATCH_INTERVAL_MS);

  // Flush saat window unloading
  window.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') {
      flushMetrics();
    }
  });
}

interface TrackedComponentProps {
  name: string;
  squad: string;
  children: React.ReactNode;
}

export const TrackedDSComponent: React.FC<TrackedComponentProps> = ({ name, squad, children }) => {
  const mountStartRef = useRef<number>(performance.now());

  useEffect(() => {
    const mountDuration = performance.now() - mountStartRef.current;

    // Masukkan data performa render ke antrean telemetri
    metricQueue.push({
      component: name,
      lifecycle: 'mount',
      renderDurationMs: Number(mountDuration.toFixed(2)),
      appVersion: process.env.NEXT_PUBLIC_APP_VERSION || 'unknown',
      squad,
    });
  }, [name, squad]);

  return <>{children}</>;
};
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Global FinTech: Migrasi Multi-Vertical & Telemetri Adopsi pada 120+ Micro-Frontends
*   **Konteks**: Perusahaan perbankan digital multinasional memiliki 120 mikro-frontend (MFE) yang dioperasikan oleh 85 squad terdistribusi di Singapura, Jakarta, dan Berlin. Mereka menghadapi fragmentasi antarmuka ekstrem: ada 4 implementasi `Modal/Dialog` yang berbeda, 14 variasi warna tombol primer, dan tingkat pelaporan accessibility audit yang gagal di regulasi MAS (Monetary Authority of Singapore).
*   **Permasalahan**: Tim Platform meluncurkan `Enterprise DS v3`, namun setelah 9 bulan, adopsi hanya menyentuh angka 24% berdasarkan analisis manual via GitHub search. Tim produk menolak migrasi karena takut memicu regresi pada checkout flow berkecepatan tinggi.
*   **Solusi Arsitektural**:
    1.  **AST-Based CI Telemetry Enforcement**: Scanner AST diintegrasikan ke seluruh pipeline PR di seluruh organisasi. Scanner ini memberikan feedback visual langsung di pull request dalam bentuk komentar markdown, menandai *token drift*, penggunaan API usang, serta persentase kepatuhan DS repositori tersebut.
    2.  **Automated Transformation Codemods**: Tim platform tidak hanya menerbitkan panduan migrasi tertulis, tetapi menyediakan codemod via `jscodeshift`. Codemod ini mampu mentransformasi komponen `LegacyModal` ke `DSv3Modal` secara otomatis, termasuk perubahan pemetaan event handlers (`onClose` -> `onOpenChange`).
    3.  **Automated Deprecation Gate**: Membagi deprecation ke dalam 3 tier: *Soft Deprecation* (Peringatan IDE/TSDoc), *Hard Deprecation* (Warning tebal di CI log + PR comment), dan *Terminal Deprecation* (Build CI gagal).
*   **Hasil Terukur**:
    *   Tingkat adopsi melonjak dari **24% ke 89%** dalam waktu 4 bulan.
    *   Pengurangan CSS bundle size global rata-rata **42 KB per micro-frontend** karena eliminasi duplikasi style lokal.
    *   Audit aksesibilitas WCAG 2.1 AA naik menjadi **99.4%** compliant di seluruh portal perbankan publik.
    *   Efisiensi jam kerja rekayasa ditaksir mencapai penghematan biaya setara **$1.8M USD** per tahun dari reduksi waktu refactoring manual.

---

### 9. Trade-offs

| Aspek | Static Telemetry (AST) | Runtime Telemetry (Beacon) |
| :--- | :--- | :--- |
| **Performance Overhead** | **Nol pada runtime**. Hanya menambah durasi build CI sebesar ~3-8 detik per 1000 files. | **Ada potensi dampak**. Jika tidak dibatch dan menggunakan `requestIdleCallback`, dapat memicu frame drop atau membebani *main-thread*. |
| **Akurasi Data** | Merefleksikan ketersediaan kode secara utuh (Static Surface), namun rentan terhadap *dead code* (komponen diimpor tapi tidak pernah dirender). | Merefleksikan 100% *real user execution*, tetapi data bergantung pada network reliability dan ad-blocker pengguna. |
| **Kompleksitas Infrastruktur** | Rendah: Cukup menjalankan script Node.js di CI dan mengirim JSON payload ke database analitik. | Tinggi: Memerlukan ingestion edge-gateway berskala jutaan request/detik, penanganan deduplikasi, dan data warehousing (ClickHouse/Kafka). |
| **Keamanan & Privasi** | Sangat Aman: Hanya membaca metadata struktur sintaksis source code engineering. | Butuh Pengawasan Ketat: Harus menjamin parameter props yang membawa data PII (Personally Identifiable Information) tidak terekam dalam payload. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Regex Grep Anti-Pattern untuk Deteksi Komponen
*   *Kesalahan*: Banyak tim mencoba membangun script audit menggunakan RegEx sederhana (`grep -r "import.*from '@ds'"`). Pola ini menghasilkan ribuan *false positives* karena tidak dapat membedakan import di dalam baris komentar, conditional string, atau variasi penamaan destrukturisasi JavaScript.
*   *Solusi*: Wajib menggunakan parser berbasis AST formal (`@babel/parser`, `@swc/core`, atau `typescript`).

#### 2. Synchronous XHR Tracking pada Lifecycle Component
*   *Kesalahan*: Mengirimkan data runtime telemetri menggunakan `axios` atau synchronous `fetch` langsung di dalam lifecycle `useEffect`. Hal ini memicu perebutan bandwidth network (*network contention*) dengan request transaksi aplikasi yang kritis.
*   *Solusi*: Wajib memanfaatkan `navigator.sendBeacon` yang dibungkus di dalam `requestIdleCallback` dengan mekanisme in-memory queueing.

#### 3. Token Bypass via Tailwind/Emotion Escape Hatches
*   *Kesalahan*: Developer mengklaim mengadopsi Design System, namun mengekstrak token warna menjadi hardcoded arbitrary Tailwind: `<Button className="bg-[#123456] !p-[3.5px]">`.
*   *Troubleshooting*: Konfigurasikan scanner AST untuk mengevaluasi *string literals* di dalam properti styling. Gunakan *custom ESLint AST rules* untuk menolak hexadecimal arbitrer yang tidak terdaftar di design tokens table.

---

### 11. Best Practices (Production Checklist)

- [ ] **Deterministic AST Traversal**: Scanner mengabaikan file dummy, spec test, file storybook, dan generated artifacts.
- [ ] **Zero PII Leakage Guarantee**: Runtime telemetry tidak pernah merekam nilai `children` dari teks dinamis atau atribut input `value`.
- [ ] **Non-blocking Beaconing**: Telemetri runtime diatur dengan frekuensi flushing interval (misal: tiap 5-10 detik) dan kapasitas antrean batching maksimum (misal: 20 item per payload).
- [ ] **Contract Versioning**: Skema payload telemetri (baik static maupun runtime) dikontrol menggunakan versioned JSON Schema untuk menjaga stabilitas tabel data lake.
- [ ] **Gradual Deprecation Policy**: 
  - *Phase 1 (Announce)*: TSDoc `@deprecated` tag (1 siklus minor).
  - *Phase 2 (Warn)*: Lint Warning & PR bot reporting (2 siklus minor).
  - *Phase 3 (Block)*: Build breaker via CI validator script (pada rilis major berikutnya).
- [ ] **Pre-packaged Codemods**: Setiap rilis major yang memuat breaking change wajib menyertakan script codemod (`npx @ds/codemod v3-button-migration`).
- [ ] **Telemetry Ingestion Circuit Breaker**: Jika service data warehouse down, library runtime telemetri secara silent mematikan fungsi pengiriman tanpa memunculkan uncaught promise exception di console browser pengguna.

---

### 12. Hands-on Practice

Buat dan simpan seluruh berkas latihan ini di folder repositori Anda: `hands-on/m02/`.

#### Langkah 1: Inisialisasi Proyek dan Instalasi Dependencies
```bash
mkdir -p hands-on/m02
cd hands-on/m02
pnpm init
pnpm add -D typescript @types/node @babel/parser @babel/traverse @babel/types glob @types/glob
npx tsc --init
```

#### Langkah 2: Buat File Target Konsumen Mocking
Buat file `hands-on/m02/src/consumer-app.tsx`:
```tsx
import React from 'react';
import { Button, Modal } from '@enterprise-ds/core';

export const CheckoutView = () => {
  return (
    <div>
      {/* Penggunaan Valid */}
      <Button variant="primary">Bayar Sekarang</Button>

      {/* Penggunaan dengan Anti-pattern: Hardcoded Inline Style */}
      <Button variant="secondary" style={{ backgroundColor: '#ff0033' }}>
        Batal
      </Button>

      {/* Komponen Legacy yang Seharusnya Dideprecate */}
      <Modal isOpen={true} legacyCloseIcon={true}>
        Konten Peringatan
      </Modal>
    </div>
  );
};
```

#### Langkah 3: Implementasikan AST Telemetry Validator
Buat file `hands-on/m02/scanner.ts`:
```typescript
import fs from 'node:fs';
import path from 'node:path';
import { parse } from '@babel/parser';
import traverse from '@babel/traverse';

const DEPRECATION_REGISTRY: Record<string, { replacement: string; deprecatedProps: string[] }> = {
  Modal: {
    replacement: 'Dialog',
    deprecatedProps: ['legacyCloseIcon'],
  },
};

const filePath = path.join(__dirname, 'src/consumer-app.tsx');
const code = fs.readFileSync(filePath, 'utf-8');

const ast = parse(code, {
  sourceType: 'module',
  plugins: ['typescript', 'jsx'],
});

const violations: string[] = [];
let dsInstancesCount = 0;

traverse(ast, {
  JSXOpeningElement(astPath) {
    const node = astPath.node;
    if (node.name.type === 'JSXIdentifier') {
      const componentName = node.name.name;

      if (['Button', 'Modal'].includes(componentName)) {
        dsInstancesCount++;

        // 1. Periksa Inline Styling Escape Hatch
        node.attributes.forEach((attr) => {
          if (attr.type === 'JSXAttribute' && attr.name.name === 'style') {
            violations.push(
              `[STYLE ESCAPE] Komponen <${componentName}> pada baris ${node.loc?.start.line} menggunakan inline style yang merusak konsistensi design tokens.`
            );
          }
        });

        // 2. Periksa Deprecation Registry
        if (DEPRECATION_REGISTRY[componentName]) {
          const rule = DEPRECATION_REGISTRY[componentName];
          node.attributes.forEach((attr) => {
            if (attr.type === 'JSXAttribute' && typeof attr.name.name === 'string') {
              if (rule.deprecatedProps.includes(attr.name.name)) {
                violations.push(
                  `[DEPRECATED PROP] Komponen <${componentName}> menggunakan properti usang '${attr.name.name}'. Gantilah ke <${rule.replacement}>.`
                );
              }
            }
          });
        }
      }
    }
  },
});

console.log('--- HASIL AUDIT DESIGN SYSTEM TELEMETRY ---');
console.log(`Total Komponen DS Ditemukan: ${dsInstancesCount}`);
console.log(`Jumlah Pelanggaran Tata Kelola: ${violations.length}`);
violations.forEach((v) => console.warn(`⚠️  ${v}`));

if (violations.length > 0) {
  console.log('\nAudit status: FAILED (Linting gate menolak PR ini).');
  process.exitCode = 1;
} else {
  console.log('\nAudit status: PASSED.');
}
```

#### Langkah 4: Jalankan Validasi
```bash
npx ts-node scanner.ts
```
*Amati output console yang menampilkan deteksi pelanggaran properti usang dan inline style escape hatches dengan presisi nomor baris.*

---

### 13. Exercise

#### Level Easy
Ubah script scanner pada bagian Hands-on untuk menghitung frekuensi distribusi varian tombol (`variant="primary"` vs `variant="secondary"`). Cetak metrik persentase proporsi penggunaannya.

#### Level Medium
Kembangkan AST Scanner agar mampu mengenali impor alias:
```tsx
import { Button as CustomDsBtn } from '@enterprise-ds/core';
// Scanner harus mampu mendeteksi <CustomDsBtn /> sebagai komponen Button resmi
```

#### Level Hard
Buat script AST Codemod menggunakan library `jscodeshift` atau Babel AST transformer yang secara otomatis mentransformasi kode berikut:
```tsx
<Modal isOpen={true} legacyCloseIcon={true}>Halo</Modal>
```
Menjadi:
```tsx
<Dialog open={true} showDismissButton={true}>Halo</Dialog>
```
Script harus menulis balik hasil modifikasi ke file tanpa merusak format whitespace kode yang tidak berhubungan.

---

### 14. Challenge

**Skenario Tantangan Arsitektur**:
Anda adalah Principal Architect pada startup Decacorn yang memiliki 400 repositori micro-frontend terisolasi. Organisasi Anda ingin melacak adopsi Design System secara real-time tanpa memodifikasi build pipeline CI/CD milik masing-masing squad (karena birokrasi cross-department yang rumit).

*   **Tugas Anda**: Rancang cetak biru arsitektur (*architectural blueprint*) sistem telemetri hibrida yang dapat mengumpulkan data adopsi secara transparan tanpa mengubah CI/CD individual squads. 
*   **Kebutuhan Ekstraksi**: 
    1. Mekanisme injeksi scanner via NPM post-install hook terdistribusi atau Webpack/Vite runtime module federated federation plugin.
    2. Zero runtime performance degradation limit (< 2ms total main thread blocking time).
    3. Proteksi deduplikasi data jika beberapa micro-frontend terpasang di satu Window DOM yang sama.
    4. Sediakan spesifikasi RFC tertulis meliputi: Data flow diagram, skema ClickHouse table, dan penanganan kegagalan koneksi jaringan.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda)

1. Mengapa pencarian berbasis Regular Expression (RegEx) tidak direkomendasikan untuk audit adopsi Design System pada basis kode modern?
   * A. RegEx berjalan lebih lambat daripada parsing AST pada file tunggal.
   * B. RegEx tidak memahami semantic context seperti imports alias, komentar kode, dan scope deklarasi variabel JSX.
   * C. RegEx tidak didukung di environment Node.js terbaru.
   * D. RegEx membutuhkan memori runtime V8 sepuluh kali lebih besar.
   * *Jawaban*: **B**. RegEx hanya memproses karakter linear tanpa memahami struktur pohon sintaksis bahasa pemrograman.

2. API Browser mana yang paling ideal digunakan untuk mengirim payload data telemetri runtime tanpa memblokir proses navigasi halaman atau eksekusi UI thread?
   * A. `XMLHttpRequest` secara synchronous.
   * B. `navigator.sendBeacon`.
   * C. `WebSocket` persistent stream.
   * D. `window.alert`.
   * *Jawaban*: **B**. `navigator.sendBeacon` didesain untuk pengiriman data asinkronus ke server tanpa menunda transisi navigasi halaman unload.

3. Apa fungsi utama dari Automated Codemod dalam ekosistem Design System enterprise?
   * A. Mengompresi aset SVG menjadi format webp secara otomatis.
   * B. Melakukan migrasi kode otomatis pada consumer repository saat terjadi breaking changes API komponen.
   * C. Mengganti dependensi Yarn dengan pnpm secara paksa.
   * D. Menghasilkan unit test secara acak untuk komponen visual.
   * *Jawaban*: **B**. Codemod memanipulasi AST untuk memperbarui signature pemanggilan API lama ke API baru secara mekanis di ribuan file.

4. Dalam model Federated Governance, siapa yang memegang tanggung jawab atas Domain-Specific Components?
   * A. Hanya Chief Technology Officer (CTO).
   * B. Tim Core Platform secara eksklusif.
   * C. Domain atau Vertical Product Squads yang bersangkutan dengan asistensi standar dari Core Guild.
   * D. Konsultan pihak ketiga dari agensi desain eksternal.
   * *Jawaban*: **C**. Model federasi membagi kepemilikan komponen domain ke squad spesifik, melepaskan ketergantungan penuh dari tim inti.

5. Manakah indikator yang menandakan terjadinya *Token Drift* pada implementasi komponen produk?
   * A. Penggunaan token spacing resmi melalui props: `<Box p="$space-4" />`.
   * B. Penggunaan hardcoded arbitrary CSS override: `<Box style={{ padding: '17px' }} />`.
   * C. Mengganti tema aplikasi dari Light Mode ke Dark Mode secara runtime.
   * D. Mengimpor komponen menggunakan ES Modules bukan CommonJS.
   * *Jawaban*: **B**. Nilai styling statis di luar daftar design token merupakan wujud langsung dari token drift.

---

#### Bagian 2: Intermediate (Analisis Kasus Singkat)

6. Mengapa pengumpulan data telemetri runtime melalui lifecycle component (`componentDidMount` / `useEffect`) berisiko mendegradasi skor metrik Core Web Vitals Interaction to Next Paint (INP)?
   * *Jawaban*: Jika instrumentasi telemetri memproses kalkulasi waktu atau transmisi data secara langsung di main thread saat siklus hidup mount berlangsung, eksekusi JavaScript tersebut memperpanjang waktu tunggu responsivitas main thread dalam menangani input pengguna yang sedang berlangsung secara bersamaan.

7. Bagaimana cara mendeteksi properti usang (*deprecated props*) yang di-pass ke komponen menggunakan dynamic spread operator (`<Button {...props} />`) via AST Static Analysis? Jelaskan tantangan teknisnya.
   * *Jawaban*: Dynamic spread operator tidak dapat dianalisis secara deterministik hanya melalui AST parser statis lokal file tersebut, karena nilai objek dievaluasi pada saat runtime (*type evaluation limitation*). Untuk mendeteksinya secara statis, scanner harus diintegrasikan dengan TypeScript Compiler Type Checker API (`ts.TypeChecker`) yang mampu menelusuri definisi tipe referensi objek asal lintas modul (*cross-file symbol resolution*).

8. Jelaskan perbedaan mendasar antara *Soft Deprecation*, *Hard Deprecation*, dan *Terminal Deprecation* dalam strategi rilis library Design System enterprise.
   * *Jawaban*:
     * *Soft Deprecation*: Peringatan dokumentatif via TSDoc `@deprecated` dan peringatan visual di IDE developer; build CI tetap berjalan sukses.
     * *Hard Deprecation*: Munculnya runtime console error di mode development dan warning non-blocking pada pipeline log CI atau comment otomatis di PR.
     * *Terminal Deprecation*: Peringatan berubah menjadi error pemblokir fatal (`exit code 1`), menghentikan pipeline CI/CD agar kode usang tidak lolos ke environment produksi.

9. Mengapa pengiriman data runtime telemetri harus melewati mekanisme batching in-memory dibandingkan mengirim satu request per event interaksi?
   * *Jawaban*: Mengirim data satu per satu membebani networking stack browser (keterbatasan concurrent TCP connections), menghabiskan baterai perangkat mobile, serta dapat melumpuhkan HTTP ingestion gateway server karena serangan traffic bertipe micro-burst.

10. Sebutkan dua alasan logis mengapa tim platform enterprise tidak boleh hanya mengandalkan static analysis (AST) saja dalam mengukur kesuksesan adopsi Design System.
    * *Jawaban*:
      1. Static analysis tidak dapat membedakan kode aktif dengan dead-code / conditional branching yang tidak pernah dieksekusi di runtime produksi pengguna riil.
      2. Static analysis tidak dapat mengukur metrik performa riil (seperti frekuensi re-render, error boundary crash, dan dampak CLS/INP komponen) di berbagai variasi perangkat client.

---

#### Bagian 3: Production Scenario Testing

11. **Skenario 1**: Repositori consumer Anda mengeluhkan bahwa proses `pnpm build` di CI mereka membengkak dari 2 menit menjadi 8 menit setelah tim Design System memasukkan script Static Telemetry Scanner ke dalam tahapan CI workflow. Setelah diinvestigasi, scanner mengevaluasi seluruh folder termasuk `node_modules` dan build cache.
    * *Tindakan Korektif*:
      1. Tambahkan exclude pattern secara eksplisit pada glob configuration scanner: `ignore: ['**/node_modules/**', '**/dist/**', '**/.next/**', '**/coverage/**']`.
      2. Batasi scanning hanya pada file yang berubah di dalam PR dengan memanfaatkan Git diff (`git diff --name-only origin/main...HEAD`), alih-alih memindai jutaan baris kode secara menyeluruh pada setiap commit PR.
      3. Jalankan script scanner secara terpisah sebagai *asynchronous parallel CI job* yang tidak memblokir rantai utama build/deploy aplikasi.

12. **Skenario 2**: Ingestion Gateway telemetri runtime Design System Anda mendadak mengalami crash (HTTP 502 Bad Gateway) pada jam 11 siang karena lonjakan traffic dari 5 aplikasi mikro-frontend konsumen yang memuat kampanye Flash Sale serentak.
    * *Tindakan Mitigasi Segera dan Pencegahan*:
      1. Di sisi Client: Pastikan library telemetry runtime memiliki *exponential backoff* dan *local circuit breaker*. Jika gateway merespons dengan status 5xx, matikan queue transmisi data selama sisa durasi session pengguna tersebut secara senyap.
      2. Terapkan strategi *probabilistic telemetry sampling*: Tidak semua session pengguna harus mengirim telemetri. Pada traffic puncak, kirim data hanya dari 1% hingga 5% total unique sessions menggunakan pseudo-random hash ID.
      3. Di sisi Ingestion Gateway: Letakkan Kafka/RabbitMQ buffer broker di balik Edge Gateway untuk meredam lonjakan request sebelum dituliskan ke database ClickHouse/BigQuery.

13. **Skenario 3**: Sebuah tim squad produk menolak menghapus penggunaan komponen usang `OldDatePicker` yang sudah masuk fase *Terminal Deprecation*, berargumen bahwa penulisan ulang memakan sprint velocity sebesar 3 minggu kerja. Mereka secara ilegal membuat alias package palsu di `package.json` untuk mengelabui filter regex scanner sederhana Anda.
    * *Tindakan Tata Kelola Arsitektur (Governance)*:
      1. Ubah deteksi scanner dari verifikasi nama package mentah di `package.json` menjadi *Deep AST Inspection* yang mengevaluasi hash signature dan metadata structural shape dari komponen yang di-render.
      2. Sediakan *zero-effort mitigation*: Buatkan pull request otomatis ke repositori mereka yang berisi eksekusi Codemod lengkap dengan integrasi test snapshot.
      3. Bawa metrik adopsi repositori tersebut ke dashboard executive governance: tampilkan data *Technical Debt Vulnerability Index* squad tersebut secara transparan di hadapan Engineering Director untuk menetapkan prioritas pembersihan technical debt secara resmi.

---

### 16. Summary

Implementasi lanjutan Design System pada skala enterprise membutuhkan pergeseran paradigma dari sekadar pustaka komponen visual (*component library*) menuju **ekosistem platform perangkat lunak yang terukur**. Keberhasilan adopsi dan skalabilitas organisasi multi-brand bertumpu pada:

1.  **Dual-Layer Telemetry**: Menggabungkan presisi komprehensif *Static AST Analysis* di CI/CD untuk memantau arsitektur basis kode dan *Zero-Cost Runtime Beaconing* di browser untuk memahami interaksi riil pengguna tanpa merusak Core Web Vitals.
2.  **Federated Governance Engine**: Memecah bottleneck sentralisasi tim platform melalui kontribusi terdesentralisasi, semantik kontrak RFC, dan standardisasi otomatisasi rilis.
3.  **Actionable Deprecation Lifecycle**: Memastikan siklus hidup pensiunnya komponen usang dipandu oleh tooling otomatis (*AST Codemods*) dan penegakan gating sistematis (*soft, hard, hingga terminal deprecation*), sehingga utang teknis dapat dituntaskan secara deterministik tanpa friksi antar-tim.