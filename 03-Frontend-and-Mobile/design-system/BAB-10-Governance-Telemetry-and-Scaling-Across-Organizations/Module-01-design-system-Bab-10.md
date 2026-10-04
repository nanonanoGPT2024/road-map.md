# SEKSI 01 — IDENTITAS MODUL

* **Domain Kategori:** `03-Frontend-and-Mobile`
* **Jalur Kurikulum:** `design-system`
* **Bab:** `10`
* **Modul:** `01`
* **Judul/Topik:** `Governance, Telemetry, and Scaling Across Organizations`
* **Tingkat Kesulitan:** Advanced / Staff Engineer Level
* **Target Pembaca:** Staff Software Engineers, Frontend Architects, Design System Engineers, Platform Engineering Leads

---

# SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Mendesain Model Tata Kelola Skala Organisasi:** Membangun federasi kontribusi design system (*Federated Contribution Model*) yang meminimalkan bottleneck tim inti tanpa mengorbankan kohesi arsitektur dan stabilitas kontrak API UI.
2. **Mengotomatisasi Pelacakan Telemetri & Adopsi Komponen:** Mengembangkan Abstract Syntax Tree (AST) analyzer khusus untuk mengaudit *codebase* frontend multi-repo/monorepo, mengekstraksi tingkat adopsi komponen, mendeteksi *style overrides*, dan memetakan regresi desain secara deterministik.
3. **Menerapkan *Cross-Organization Release Management*:** Mengorkestrasi pipeline multi-package monorepo menggunakan semantic versioning, otomatisasi changelog terdistribusi, serta validasi breaking changes lintas mikro-frontend.
4. **Membangun Sistem Observabilitas Runtime Komponen:** Merancang pipeline telemetri ringan (*zero-dependency telemetry hook*) pada tingkat komponen dasar untuk melacak metrik kinerja Web Vitals, kesalahan rendering, serta pola penggunaan UI langsung dari klien akhir secara anonim dan aman.
5. **Memitigasi Fragmentasi UI Lintas Divisi:** Menerapkan proses RFC (*Request for Comments*), API deprecation lifecycle, dan mekanisme automated codemods untuk migrasi massal kode konsumen tanpa menimbulkan beban koordinasi manual.

---

# SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Paradigma: Dari Komponen Visual ke Produk Platform
Design System skala enterprise bukan sekadar repositori komponen React/Vue atau berkas Figma; Design System adalah **produk platform internal**. Pelanggan utama Anda adalah ratusan insinyur frontend dan desainer produk lintas zona waktu, dengan konsumen akhir berupa jutaan pengguna aplikasi.

```
       PENDEKATAN NAIF                        PENDEKATAN ENTERPRISE-GRADE
   (Design System = Library)                   (Design System = Internal Platform)

+-----------------------------+           +-----------------------------------------+
| Figma  ---> UI Components   |           | Design Tokens & Core Contracts          |
|                 |           |           |                   |                     |
|         Consumer Apps       |           |   Federated Contribution Engine (RFC)   |
|      (Adopsi via Insting)   |           |                   |                     |
+-----------------------------+           | AST Telemetry + Runtime Observability   |
                                          |                   |                     |
                                          | Automated Codemods & Scheduled Releases |
                                          +-----------------------------------------+
```

### Mental Model 1: "The Core vs. Federated Flywheel"
Jika tim inti design system bertindak sebagai satu-satunya *gatekeeper* dan produsen komponen, tim tersebut akan menjadi *bottleneck* kritis (*Single Point of Failure*). Sebaliknya, jika semua tim dibiarkan menulis komponen tanpa kendali, fragmentasi sistem visual dan arsitektur akan terjadi dalam hitungan bulan. Solusinya adalah model *Federated*:
* **Tim Inti (Core Engine):** Memelihara fondasi (*primitives*, token desain, sistem aksesibilitas, infrastruktur pengujian, telemetri, dan toolchain).
* **Tim Domain (Federated Contributors):** Menyumbang komponen spesifik bisnis melalui proses RFC standar yang bertransisi dari *Local Component* -> *Incubated Component* -> *Core System Component*.

### Mental Model 2: "Observability Over Assumptions"
Jangan pernah menebak apakah suatu komponen berhasil diadopsi atau apakah suatu properti (*prop*) API berguna. Gunakan dua jenis telemetri:
* **Static Telemetry (Lintas Repositori):** Pemindaian AST berkala untuk mengetahui berapa persen elemen UI yang menggunakan Design System vs. custom CSS/HTML mentah.
* **Runtime Telemetry:** Pengukuran latensi mount/render komponen dan deteksi error UI secara real-time di lingkungan produksi.

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Di bawah ini adalah arsitektur menyeluruh tata kelola dan pipeline telemetri adopsi yang menghubungkan tim produk, repositori monorepo design system, sistem ekstraksi AST, dan dashboard observabilitas enterprise.

```
+---------------------------------------------------------------------------------------------------+
|                            ENTERPRISE DESIGN SYSTEM INFRASTRUCTURE                               |
+---------------------------------------------------------------------------------------------------+

   +-------------------------+                     +--------------------------------------------+
   |   Product Team Alpha    |                     |             Product Team Beta              |
   | (E-Commerce Checkout)   |                     |            (Core Banking Ops)              |
   |  [Consumer Repo / MFE]  |                     |           [Consumer Repo / MFE]            |
   +------------+------------+                     +---------------------+----------------------+
                |                                                        |
                | git push                                               | git push
                v                                                        v
   +--------------------------------------------------------------------------------------------+
   |                       CI/CD WORKFLOW: STATIC TELEMETRY SCANNER                             |
   |  - Mengambil file sumber TypeScript/JSX                                                    |
   |  - Babel/TypeScript AST Parser mentransformasikan kode menjadi syntax tree                 |
   |  - Telemetry Analyzer menghitung import '@enterprise-ds/core' vs native JSX elements       |
   |  - Menghitung rasio adopsi, deteksi style overrides ('!important', custom inline CSS)      |
   +--------------------------------------------------------------------------------------------+
                                                |
                                                | Mengirimkan metrik JSON via TLS
                                                v
   +--------------------------------------------------------------------------------------------+
   |                            TELEMETRY INGESTION SERVICE (API)                               |
   |  - Memvalidasi schema event (Zod/JSON Schema)                                              |
   |  - Menghubungkan metadata tim, commit SHA, dan versi package                              |
   +--------------------------------------------------------------------------------------------+
                                                |
                                                +----------------------------+
                                                |                            |
                                                v                            v
   +---------------------------------------------------------+   +------------------------------+
   |             TIMESERIES & ANALYTICS DB                   |   | METRICS DASHBOARD (GRAFANA)  |
   |  - Agregasi % adopsi per tim                            |   | - Adoption Scoreboard        |
   |  - Deteksi penggunaan komponen terdepresiasi (*props*)  |   | - Breaking Change Impact Map |
   |  - Pelacakan tren refactoring UI                        |   | - Deprecated Component Alert |
   +---------------------------------------------------------+   +------------------------------+
                                                ^
                                                | Memberi makan insight
   +--------------------------------------------+-----------------------------------------------+
   |                      CORE GOVERNANCE ENGINE & RFC REGISTRY                                 |
   |                                                                                            |
   |  [Proposal RFC] ---> [Incubation Phase] ---> [Core Stabilization] ---> [Codemod Migration] |
   |         ^                     ^                      |                         |           |
   |         |                     |                      v                         v           |
   |  Product Engineers     Core DS Team        Automated Release        Consumer Automated PRs |
   |  (Domain Feature)      (Review System)     (@changesets/cli)        (jscodeshift scripts)  |
   +--------------------------------------------------------------------------------------------+
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Siklus Hidup Komponen (Governance Component Lifecycle)
Sebuah komponen di tingkat enterprise harus melewati state machine berikut sebelum dianggap stabil:

```
[Proposal RFC] ---> [Experimental] ---> [Stable] ---> [Deprecated] ---> [Tombstoned]
      |                    |                |               |                 |
      v                    v                v               v                 v
Dokumentasi API,     Alpha version,    100% Test,      Warning emit,      Dihapus dari
Problem Statement,   Private scope,   A11y passing,   Codemod ready,      ekspor bundle,
A11y Strategy        Breaking changes Telemetry AST   Docs redirect       Type compilation
                     bebas dilakukan   monitored                          error
```

* **Experimental:** Dirilis di bawah flag atau package `@enterprise-ds/experimental-*`. Tidak ada garansi semver.
* **Stable:** Mematuhi aturan *Zero Breaking Changes* tanpa bump versi mayor. Memiliki unit test coverage >90%, tes aksesibilitas WCAG 2.1 AA otomatis, dan tipe TypeScript ketat.
* **Deprecated:** Memberikan peringatan build-time (via ESLint/TypeScript JSDoc `@deprecated`) dan static telemetry tracking.
* **Tombstoned:** Kode dihapus total dari bundle produksi utama.

### 2. Anatomi Telemetry Engine
Static telemetry parser bekerja pada level AST (Abstract Syntax Tree):
1. **Source Discovery:** Menemukan seluruh berkas `.tsx`, `.jsx`, `.ts` yang relevan, mengabaikan `.d.ts`, tests, dan direktori node_modules.
2. **Lexical Analysis & Parsing:** Mengurai kode sumber menggunakan `@babel/parser` dengan plugin JSX dan TypeScript menjadi AST.
3. **AST Traversal:** Menggunakan `@babel/traverse` untuk mengunjungi node `ImportDeclaration` guna merekam varian impor, dan `JSXOpeningElement` untuk merekam nama elemen, props yang dikonsumsi, serta indikasi *anti-patterns* (misal: penyalahgunaan prop `className` atau `style` inline untuk menimpa CSS inti).
4. **Metric Compilation:** Menghasilkan laporan deterministik yang mencakup:
   * *Component Count:* Jumlah kemunculan instance komponen DS.
   * *Native Replacement Ratio:* Rasio elemen native HTML (`<button>`, `<input>`) terhadap instance DS (`<Button>`, `<Input>`).
   * *Override Severity Index:* Jumlah prop `style` atau selektor bypass pada komponen DS.

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Semantic Versioning Enterprise & Breaking Changes Mechanics
Dalam ekosistem dengan ratusan dependensi downstream, kenaikan versi mayor (*Major Version Bump*) memiliki biaya koordinasi organisasi yang sangat masif (*blast radius* tinggi). 

Definisi formal **Breaking Changes** pada level arsitektur UI komponen:
* Perubahan nama, jenis tipe data, atau penghapusan properti `prop`.
* Pengubahan perilaku runtime default (misalnya, `Button` yang sebelumnya `type="button"` diubah menjadi `type="submit"`).
* Perubahan hierarki DOM yang merusak selektor CSS konsumen eksternal yang melanggar enkapsulasi.
* Kenaikan dependensi peer (misal: React 17 ke 18/19).

#### Strategi "No Breaking Changes" via Parameter Extension & Deprecation Windows
Pendekatan modern Staff-level meminimalkan breaking changes dengan menerapkan prinsip: **Never delete in-place, expand and deprecate.**

```typescript
// Tahap 1: API Awal
interface ButtonProps {
  variant: 'primary' | 'secondary';
}

// Tahap 2: Menambahkan varian baru dan mendepresiasi varian lama tanpa breaking change
interface ButtonProps {
  /**
   * @deprecated 'secondary' akan dihapus pada v5.0.0. Gunakan 'neutral' sebagai pengganti.
   */
  variant: 'primary' | 'secondary' | 'neutral';
}

// Tahap 3: Runtime bridge & Telemetry flag di dalam komponen
export const Button: React.FC<ButtonProps> = ({ variant = 'primary', ...props }) => {
  let activeVariant = variant;
  if (variant === 'secondary') {
    // static AST scanner akan melacak ini, dan runtime dev warning akan mengedukasi developer
    if (process.env.NODE_ENV !== 'production') {
       console.warn("[DS Deprecation]: Variant 'secondary' is deprecated. Migrate to 'neutral'.");
    }
    activeVariant = 'neutral';
  }
  return <button className={`ds-btn ds-btn-${activeVariant}`} {...props} />;
};
```

### Static AST Extraction Theory
Operasi parsing mentransformasikan string teks mentah menjadi representasi node terstruktur. Sebagai contoh, baris kode:
```tsx
import { Button } from '@enterprise-ds/core';
<Button variant="primary" onClick={handleClick}>Kirim</Button>
```
Dikonversi menjadi node tree:
* `Program`
  * `ImportDeclaration` (source: `'@enterprise-ds/core'`)
    * `ImportSpecifier` (imported: `Button`, local: `Button`)
  * `JSXElement`
    * `JSXOpeningElement` (name: `JSXIdentifier` "Button")
      * `JSXAttribute` (name: `variant`, value: `StringLiteral` "primary")
      * `JSXAttribute` (name: `onClick`, value: `JSXExpressionContainer`)

Dengan menelusuri pohon ini, analyzer dapat mencocokkan secara deterministik apakah elemen JSX berasal dari library inti atau sekadar nama komponen lokal yang kebetulan bertabrakan.

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi fundamental CLI Script Node.js yang memindai AST berkas TypeScript/React menggunakan Babel parser untuk mendeteksi adopsi Design System dan style overrides.

### File: `telemetry-scanner.ts`
```typescript
import * as fs from 'fs';
import * as path from 'path';
import { parse } from '@babel/parser';
import traverse, { NodePath } from '@babel/traverse';
import * as t from '@babel/types';

export interface TelemetryReport {
  scannedFiles: number;
  designSystemImports: Record<string, number>;
  nativeElementsCount: Record<string, number>;
  styleOverridesCount: number;
  adoptionPercentage: number;
}

export class ASTAdoptionScanner {
  private report: TelemetryReport = {
    scannedFiles: 0,
    designSystemImports: {},
    nativeElementsCount: {},
    styleOverridesCount: 0,
    adoptionPercentage: 0,
  };

  private readonly dsPackageName: string;

  constructor(dsPackageName: string = '@enterprise-ds/core') {
    this.dsPackageName = dsPackageName;
  }

  public scanDirectory(dirPath: string): TelemetryReport {
    this.walkSync(dirPath, (filePath) => {
      if (/\.(tsx|jsx)$/.test(filePath) && !filePath.includes('.test.') && !filePath.includes('node_modules')) {
        this.analyzeFile(filePath);
      }
    });

    const totalDsComponents = Object.values(this.report.designSystemImports).reduce((a, b) => a + b, 0);
    const totalNativeElements = Object.values(this.report.nativeElementsCount).reduce((a, b) => a + b, 0);
    const totalElements = totalDsComponents + totalNativeElements;

    this.report.adoptionPercentage = totalElements > 0 
      ? Number(((totalDsComponents / totalElements) * 100).toFixed(2)) 
      : 0;

    return this.report;
  }

  private walkSync(dir: string, callback: (filePath: string) => void): void {
    const files = fs.readdirSync(dir);
    for (const file of files) {
      const fullPath = path.join(dir, file);
      const stat = fs.statSync(fullPath);
      if (stat.isDirectory()) {
        this.walkSync(fullPath, callback);
      } else {
        callback(fullPath);
      }
    }
  }

  private analyzeFile(filePath: string): void {
    const code = fs.readFileSync(filePath, 'utf-8');
    this.report.scannedFiles++;

    let ast: t.File;
    try {
      ast = parse(code, {
        sourceType: 'module',
        plugins: ['typescript', 'jsx'],
      });
    } catch (err) {
      console.error(`Gagal mem-parsing AST untuk file: ${filePath}`, err);
      return;
    }

    const importedComponents = new Set<string>();

    traverse(ast, {
      ImportDeclaration: (pathNode: NodePath<t.ImportDeclaration>) => {
        if (pathNode.node.source.value === this.dsPackageName) {
          pathNode.node.specifiers.forEach((specifier) => {
            if (t.isImportSpecifier(specifier) && t.isIdentifier(specifier.imported)) {
              importedComponents.add(specifier.local.name);
            }
          });
        }
      },

      JSXOpeningElement: (pathNode: NodePath<t.JSXOpeningElement>) => {
        const elementNameNode = pathNode.node.name;

        if (t.isJSXIdentifier(elementNameNode)) {
          const elementName = elementNameNode.name;

          if (importedComponents.has(elementName)) {
            // Catat pemakaian komponen Design System
            this.report.designSystemImports[elementName] = 
              (this.report.designSystemImports[elementName] || 0) + 1;

            // Periksa anomali/override (Penggunaan custom style atau className kotor)
            pathNode.node.attributes.forEach((attr) => {
              if (t.isJSXAttribute(attr) && t.isJSXIdentifier(attr.name)) {
                if (attr.name.name === 'style') {
                  this.report.styleOverridesCount++;
                }
              }
            });
          } else {
            // Deteksi penggunaan native HTML equivalents (misal button, input)
            const nativePrimitives = ['button', 'input', 'select', 'textarea', 'a'];
            if (nativePrimitives.includes(elementName.toLowerCase())) {
              this.report.nativeElementsCount[elementName] = 
                (this.report.nativeElementsCount[elementName] || 0) + 1;
            }
          }
        }
      },
    });
  }
}

// Eksekusi jika dipanggil langsung
if (require.main === module) {
  const scanner = new ASTAdoptionScanner('@enterprise-ds/core');
  const targetDir = process.argv[2] || './src';
  console.log(`Memulai audit static telemetry pada direktori: ${targetDir}`);
  const results = scanner.scanDirectory(targetDir);
  console.log('--- LAPORAN ADOPSI TELEMETRI DESIGN SYSTEM ---');
  console.log(JSON.stringify(results, null, 2));
}
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

* **Baris 2–5:** Mengimpor API core Babel. `@babel/parser` mengubah file teks menjadi format data node pohon (AST), `@babel/traverse` melakukan navigasi menggunakan *visitor pattern*, dan `@babel/types` menyediakan type predicates (`t.isJSXIdentifier`, dll.) untuk memvalidasi node secara aman.
* **Baris 7–13 (`interface TelemetryReport`):** Mendefinisikan metrik inti: jumlah berkas yang dipindai, distribusi komponen DS yang dipakai, jumlah tag HTML murni yang belum dimigrasi, jumlah pelanggaran penimpaan gaya (`styleOverridesCount`), dan rasio adopsi keseluruhan (`adoptionPercentage`).
* **Baris 30–42 (`scanDirectory`):** Melakukan eksekusi traversi direktori rekursif dan menghitung persentase rasio total elemen teradopsi terhadap keseluruhan elemen UI. Nilai persentase dibatasi pada dua angka desimal secara deterministik.
* **Baris 67–74 (`analyzeFile -> parse`):** Mengaktifkan parser Babel dengan plugin sintaks `typescript` dan `jsx`. Membungkus parsing dalam `try-catch` mencegah CLI *crash* ketika menghadapi syntax error non-standar pada proyek konsumen.
* **Baris 78–87 (`ImportDeclaration Visitor`):** Mengisolasi dan mendeteksi modul yang hanya berasal dari `@enterprise-ds/core`. Ini mencegah kesalahan identifikasi jika konsumen memiliki komponen internal dengan nama serupa (misal: `./Button` lokal vs import resmi DS). Pemetaan nama lokal menangani alias import (seperti `import { Button as CoreButton }`).
* **Baris 89–115 (`JSXOpeningElement Visitor`):** 
  * Baris 94–106: Mengidentifikasi instance JSX. Jika komponen berada di dalam kumpulan `importedComponents`, metrik komponen DS dinaikkan dan atributnya diperiksa. Jika properti `style` ditemukan, `styleOverridesCount` bertambah, menandakan tim konsumen mencoba menembus isolasi token desain.
  * Baris 107–113: Jika bukan dari DS, memeriksa apakah komponen tersebut merupakan elemen interaktif HTML native (`<button>`, `<input>`). Ini menghasilkan pembagi (*denominator*) akurat untuk mengukur adopsi nyata.

---

# SEKSI 09 — STUDI KASUS NYATA

### Enterprise Scenario: "GlobalFin Enterprise UI Convergence"
* **Konteks:** Sebuah entitas multi-nasional perbankan memiliki 42 tim pengembang frontend independen dengan lebih dari 80 aplikasi web (Micro-Frontends). Masing-masing tim menggunakan UI library yang berbeda atau mengkloning komponen `Button`, `Modal`, dan `DataGrid` secara lokal.
* **Masalah Bisnis & Teknis:**
  1. *Audit Aksesibilitas (WCAG 2.1 AA Failure):* Perusahaan terkena penalti kepatuhan hukum karena form transfer perbankan internal tidak dapat diakses screen reader.
  2. *Design Drift & Dependency Hell:* Terdapat 14 varian komponen Modal di seluruh portal nasabah dengan perilaku error handling yang tidak konsisten.
  3. *Bottleneck Tim Inti:* Tim Design System pusat beranggotakan 6 orang kewalahan menangani puluhan *pull request* fitur spesifik domain dari tim perbankan investasi dan tim KPR.
* **Solusi Arsitektural yang Diterapkan:**
  1. Mengimplementasikan **Federated Contribution Model** dengan standarisasi RFC dan status paket `@globalfin-ds/core` vs `@globalfin-ds/incubated-*`.
  2. Mengintegrasikan **Automated AST Adoption Telemetry** ke dalam seluruh pipeline CI/CD GitHub Actions di 80 repo konsumen, memblokir PR jika skor adopsi komponen yang memiliki substitusi DS berada di bawah target yang disepakati.
  3. Menyediakan paket otomatisasi migrasi **Codemods** menggunakan `jscodeshift` untuk mengonversi `<button className="btn-primary">` lama secara otomatis menjadi `<Button variant="primary">`.
* **Hasil Terukur:**
  * Dalam 6 bulan, adopsi komponen inti meningkat dari **18% menjadi 87%** di seluruh organisasi.
  * Aksesibilitas mencapai **100% kepatuhan WCAG 2.1 AA** secara seragam.
  * *Lead time* penambahan komponen domain berkurang dari 8 minggu menjadi 1.5 minggu via federated contribution.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Sistem lengkap ini mencakup tiga layer produksi:
1. **Runtime Telemetry Component Wrapper** (Zero-overhead, batched reporting ke endpoint telemetri).
2. **Automated Codemod Transformation Script** (Engine `jscodeshift` untuk migrasi massal otomatis).
3. **Federation Pipeline Contribution Validation Schema** (Aturan CI untuk menguji kontribusi baru).

### File 1: `runtime-telemetry-provider.tsx`
```typescript
import React, { createContext, useContext, useEffect, useRef } from 'react';

export interface TelemetryPayload {
  componentName: string;
  action: 'mount' | 'unmount' | 'render_slow';
  renderDurationMs?: number;
  timestamp: number;
  appId: string;
}

interface TelemetryContextType {
  logEvent: (payload: Omit<TelemetryPayload, 'timestamp' | 'appId'>) => void;
}

const TelemetryContext = createContext<TelemetryContextType | null>(null);

const BATCH_INTERVAL_MS = 5000;
const SLOW_RENDER_THRESHOLD_MS = 16.67; // Melebihi budget 60fps (1 frame)

export const TelemetryProvider: React.FC<{ appId: string; endpoint: string; children: React.ReactNode }> = ({
  appId,
  endpoint,
  children,
}) => {
  const queueRef = useRef<TelemetryPayload[]>([]);

  useEffect(() => {
    const flushQueue = () => {
      if (queueRef.current.length === 0) return;
      const dataToSend = [...queueRef.current];
      queueRef.current = [];

      if (navigator.sendBeacon) {
        const blob = new Blob([JSON.stringify(dataToSend)], { type: 'application/json' });
        navigator.sendBeacon(endpoint, blob);
      } else {
        fetch(endpoint, {
          method: 'POST',
          body: JSON.stringify(dataToSend),
          headers: { 'Content-Type': 'application/json' },
          keepalive: true,
        }).catch((err) => console.error('Failed to dispatch telemetry', err));
      }
    };

    const intervalId = setInterval(flushQueue, BATCH_INTERVAL_MS);
    const handleBeforeUnload = () => flushQueue();
    window.addEventListener('beforeunload', handleBeforeUnload);

    return () => {
      clearInterval(intervalId);
      window.removeEventListener('beforeunload', handleBeforeUnload);
      flushQueue();
    };
  }, [endpoint]);

  const logEvent = (payload: Omit<TelemetryPayload, 'timestamp' | 'appId'>) => {
    queueRef.current.push({
      ...payload,
      appId,
      timestamp: Date.now(),
    });
  };

  return (
    <TelemetryContext.Provider value={{ logEvent }}>
      {children}
    </TelemetryContext.Provider>
  );
};

export function useComponentTelemetry(componentName: string) {
  const context = useContext(TelemetryContext);
  const mountStartRef = useRef<number>(performance.now());

  useEffect(() => {
    const mountDuration = performance.now() - mountStartRef.current;
    
    if (context) {
      context.logEvent({ componentName, action: 'mount' });
      if (mountDuration > SLOW_RENDER_THRESHOLD_MS) {
        context.logEvent({
          componentName,
          action: 'render_slow',
          renderDurationMs: Number(mountDuration.toFixed(2)),
        });
      }
    }

    return () => {
      if (context) {
        context.logEvent({ componentName, action: 'unmount' });
      }
    };
  }, [componentName, context]);
}
```

### File 2: `codemod-native-button-to-ds.ts`
Transformator `jscodeshift` yang mengubah tag native `<button>` lama menjadi `<Button variant="primary">` dari Design System secara aman:

```typescript
import { API, FileInfo, Options } from 'jscodeshift';

export default function transformer(file: FileInfo, api: API, options: Options) {
  const j = api.jscodeshift;
  const root = j(file.source);

  let hasModifications = false;
  let hasDsButtonImport = false;

  // 1. Cek apakah import @enterprise-ds/core sudah ada
  const importDeclarations = root.find(j.ImportDeclaration, {
    source: { value: '@enterprise-ds/core' },
  });

  if (importDeclarations.size() > 0) {
    importDeclarations.forEach((path) => {
      const specifiers = path.node.specifiers || [];
      hasDsButtonImport = specifiers.some(
        (s) => j.isImportSpecifier(s) && s.imported.name === 'Button'
      );
    });
  }

  // 2. Temukan semua elemen <button className="legacy-btn">
  root.find(j.JSXElement, {
    openingElement: { name: { name: 'button' } },
  }).forEach((path) => {
    const openingEl = path.node.openingElement;
    
    // Cari atribut className
    const classAttrIndex = openingEl.attributes.findIndex(
      (attr) => j.isJSXAttribute(attr) && attr.name.name === 'className'
    );

    if (classAttrIndex !== -1) {
      const classAttr = openingEl.attributes[classAttrIndex];
      if (
        j.isJSXAttribute(classAttr) &&
        j.isStringLiteral(classAttr.value) &&
        classAttr.value.value.includes('legacy-btn')
      ) {
        hasModifications = true;

        // Ubah identifier tag menjadi 'Button'
        openingEl.name = j.jsxIdentifier('Button');
        if (path.node.closingElement) {
          path.node.closingElement.name = j.jsxIdentifier('Button');
        }

        // Hapus class legacy, ganti dengan variant="primary"
        openingEl.attributes.splice(classAttrIndex, 1);
        openingEl.attributes.push(
          j.jsxAttribute(j.jsxIdentifier('variant'), j.stringLiteral('primary'))
        );
      }
    }
  });

  // 3. Tambahkan impor jika modifikasi terjadi dan belum ada impor Button
  if (hasModifications) {
    if (importDeclarations.size() > 0 && !hasDsButtonImport) {
      importDeclarations.get(0).node.specifiers.push(
        j.importSpecifier(j.jsxIdentifier('Button'))
      );
    } else if (importDeclarations.size() === 0) {
      const newImport = j.importDeclaration(
        [j.importSpecifier(j.jsxIdentifier('Button'))],
        j.stringLiteral('@enterprise-ds/core')
      );
      root.get().node.program.body.unshift(newImport);
    }
    return root.toSource({ quote: 'single' });
  }

  return file.source;
}
```

### File 3: `rfc-validation-schema.ts`
Validasi kontrak metadata kontribusi federasi via TypeScript & Zod untuk gatekeeping CI otomatis:

```typescript
import { z } from 'zod';

export const RFCContributionSchema = z.object({
  id: z.string().regex(/^RFC-[0-9]{4}$/, 'ID harus berformat RFC-XXXX (e.g., RFC-0042)'),
  title: z.string().min(10, 'Judul proposal harus deskriptif'),
  author: z.object({
    name: z.string(),
    email: z.string().email(),
    team: z.string(),
  }),
  targetScope: z.enum(['tokens', 'core', 'incubated', 'pattern']),
  wcagComplianceAudit: z.object({
    keyboardNavTested: z.literal(true, {
      errorMap: () => ({ message: 'Komponen WAJIB lulus uji navigasi keyboard' }),
    }),
    contrastRatioValue: z.number().min(4.5, 'Rasio kontras harus minimal 4.5:1 (WCAG AA)'),
    ariaRolesDefined: z.array(z.string()).nonempty('Wajib mencantumkan ARIA roles yang digunakan'),
  }),
  breakingChangesExpected: z.boolean(),
  migrationPlan: z.string().optional(),
}).refine((data) => {
  if (data.breakingChangesExpected && (!data.migrationPlan || data.migrationPlan.length < 50)) {
    return false;
  }
  return true;
}, {
  message: 'Breaking changes memerlukan dokumen rencana migrasi detail (min. 50 karakter).',
  path: ['migrationPlan'],
});

export type RFCContribution = z.infer<typeof RFCContributionSchema>;
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Parameter Arsitektur | Centralized Governance | Federated Contribution | Wild West (No Governance) |
| :--- | :--- | :--- | :--- |
| **Kecepatan Inovasi Tim Domain** | Sangat Rendah (*Blocked by Core Team*) | Tinggi (*Self-service via RFC*) | Sangat Cepat (Awalnya), Lambat (Skala Besar) |
| **Konsistensi UI & Desain** | Sangat Tinggi (Strictly Controlled) | Tinggi (Terkontrol lewat standard tooling) | Rendah (Fragmentasi instan) |
| **Overhead Komunikasi Organisasi** | Sangat Tinggi (Banyak rapat antartim) | Terstruktur (Asinkron melalui RFC & CI) | Rendah (Tidak ada komunikasi) |
| **Kualitas Aksesibilitas (A11y)** | Konsisten 100% | Tinggi (Dipaksa oleh Schema CI gate) | Buruk (Kerap terabaikan) |
| **Beban Pemeliharaan Tim DS** | Masif (*Burnout Risk*) | Terdistribusi ke pemilik domain | Nihil (Beban pindah ke konsumen) |
| **Penerapan Breaking Changes** | Mudah dipantau, sulit dirilis | Memerlukan codemods dan semver ketat | Sering terjadi secara tak sengaja |

---

# SEKSI 12 — EDGE CASES & PITFALLS

### 1. Edge Case: Ghost Imports pada AST Scanning
* **Kondisi:** Developer tim konsumen mengimpor komponen dari Design System tetapi tidak pernah merendernya (atau me-re-export kembali):
  ```typescript
  export { Button } from '@enterprise-ds/core'; // Re-export
  import { Input } from '@enterprise-ds/core'; // Unused
  ```
* **Dampak:** Metrik adopsi mengalami penggelembungan semu (*false positive inflation*).
* **Mitigasi:** Analisis AST tidak boleh hanya mencatat `ImportDeclaration`. Analyzer harus menyilangkan nama lokal import dengan deklarasi `JSXOpeningElement` dan `Identifier` references di dalam lingkup scope AST untuk membuktikan eksekusi/penggunaan komponen.

### 2. Edge Case: Dynamic JSX Element Construction
* **Kondisi:** Penggunaan pola dinamis seperti:
  ```tsx
  const Component = isSpecial ? SpecialComponent : Button;
  return <Component />;
  ```
* **Dampak:** Static scanner berbasis JSX identifier sederhana akan gagal mengenali bahwa `Component` mereferensikan `Button`.
* **Mitigasi:** Gunakan Babel Scope Binding Analysis (`path.scope.getBinding('Component')`) untuk menelusuri penugasan referensi variabel kembali ke titik deklarasi awal impor.

### 3. Pitfall: Telemetry Network Flood
* **Kondisi:** Memasang runtime tracking pada komponen atom berfrekuensi tinggi (misal: `Text`, `Box`, `Icon`) di dalam daftar tabel virtual dengan 10.000 baris.
* **Dampak:** Pengiriman ratusan ribu request HTTP yang melumpuhkan jaringan pengguna dan menghabiskan resource peramban (*thread blocking*).
* **Mitigasi:** Batasi runtime telemetri HANYA pada komponen molekul/organisme kompleks (misal: `Modal`, `DataGrid`, `DatePicker`, `Form`). Gunakan buffering/batching berbasis interval, serta manfaatkan `navigator.sendBeacon`.

---

# SEKSI 13 —