# BAB 06: Modern SSG Engine (Docusaurus, Starlight, Nextra)
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis dan Membedah Siklus Hidup Kompilasi MDX**: Menguasai ekosistem `unified`, `remark`, dan `rehype` untuk memanipulasi Abstract Syntax Tree (AST) secara programatis pada build-time.
- **Merancang Arsitektur *Zero-JS* vs *Full Client-Side Hydration***: Mengidentifikasi trade-off teknis antara arsitektur Docusaurus (React SPA Hydration), Astro Starlight (Islands Architecture / Partial Hydration), dan Nextra (Next.js React Server Components / Streaming).
- **Mengimplementasikan Pipeline Dokumentasi Terotomatisasi (Docs-as-Code)**: Membangun automasi ekstraksi OpenAPI/AsyncAPI spec menjadi halaman MDX interaktif dengan validasi skema waktu kompilasi.
- **Mengoptimalkan Skala Enterprise**: Mencegah dan mengatasi masalah memori (*Heap Out-of-Memory*) pada repositori dokumentasi berskala masif (>10.000 halaman) melalui *incremental builds*, *parallel processing*, dan optimasi AST.
- **Mengintegrasikan Mesin Pencarian Heterogen**: Menghubungkan *offline client-side indexing* (Pagefind, Orama) dan *managed hybrid search* (Algolia DocSearch / Vector Search) dengan pipeline CI/CD berkinerja tinggi.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib memahami:
- **Node.js Internals & ESM**: Pemahaman mendalam mengenai Node.js buffer, stream, memory heap profiling (`--max-old-space-size`), dan modul ECMAScript murni (Pure ESM).
- **TypeScript Advanced**: Generics, AST typing, type inference, dan declaration merging.
- **Web Performance Metrics**: Core Web Vitals (LCP, INP, CLS), First Contentful Paint (FCP), dan Time to Interactive (TTI).
- **Dasar SSG**: Konsep dasar routing berbasis berkas (*file-system routing*), Markdown/frontmatter metadata, dan static asset pipeline.

---

### 3. Concept & Internal Architecture

Ekosistem *Modern Static Site Generator* (SSG) untuk dokumentasi enterprise telah berevolusi dari sekadar pengubah Markdown-ke-HTML sederhana menjadi rantai kompilasi (*compiler pipeline*) yang sangat terdistribusi dan modular. Tiga paradigma dominan saat ini diwakili oleh **Docusaurus**, **Starlight (Astro)**, dan **Nextra (Next.js)**.

```
+-----------------------------------------------------------------------------------+
|                            THE UNIFIED ECOSYSTEM                                 |
+-----------------------------------------------------------------------------------+
   [ Raw .md/.mdx Content ]
              │
              ▼
   ┌──────────────────────┐  (mdast: Markdown Abstract Syntax Tree)
   │    remark-parse      │  Tokens: Headings, CodeBlocks, Paragraphs, JSX Nodes
   └──────────┬───────────┘
              │
              ▼
   ┌──────────────────────┐  Custom Transformations:
   │    remark plugins    │  - Autolink Headings, Math (KaTeX), Frontmatter parsing
   └──────────┬───────────┘
              │
              ▼
   ┌──────────────────────┐  Bridge mdast -> hast
   │    remark-rehype     │  (Translates Markdown primitives to HTML DOM primitives)
   └──────────┬───────────┘
              │
              ▼
   ┌──────────────────────┐  (hast: Hypertext Abstract Syntax Tree)
   │    rehype plugins    │  - Syntax Highlighting (Shiki/Prism), TOC extraction,
   └──────────┬───────────┘    Minification, Sanitization
              │
              ▼
   ┌──────────────────────┐
   │    MDX Compiler      │  Transforms hast into JavaScript Module (JSX Runtime)
   └──────────┬───────────┘
              │
              ▼
+-----------------------------------------------------------------------------------+
|                        FRAMEWORK SPECIFIC RUNTIME PIPELINE                        |
+-----------------------------------------------------------------------------------+
              │
      ┌───────┴───────────────────────┬────────────────────────┐
      ▼                               ▼                        ▼
 [ DOCUSAURUS ]                 [ STARLIGHT ]              [ NEXTRA ]
 (React SPA)                   (Astro Islands)            (Next.js App Router)
  - Webpack Bundler             - Vite Bundler             - Turbopack / Webpack
  - SSR Static HTML Gen         - Zero-JS Static HTML Gen  - RSC (React Server Comp.)
  - Full Page Re-hydration     - Island Hydration Only    - Edge Runtime Delivery
    (Heavy Client Bundle)        (`client:visible`, etc.)   - Streaming SSR
```

#### Komparasi Arsitektur Internal

1. **Docusaurus (React Client-Side SPA Model)**:
   - **Build Step**: Menggunakan Webpack untuk menghasilkan berkas HTML statis melalui SSR (Server-Side Rendering) saat build time, serta membuat bundel JavaScript client-side untuk setiap halaman.
   - **Runtime**: Ketika halaman dimuat, seluruh runtime React dan dependensi komponen dihidrasi (*hydrated*) secara penuh di sisi klien. Navigasi berikutnya menggunakan client-side routing layaknya Single Page Application (SPA).
   - **Karakteristik**: Sangat kaya fitur out-of-the-box (i18n, search, versioning), tetapi ukuran bundle JavaScript klien membesar seiring kompleksitas komponen, berpotensi menurunkan skor Interaction to Next Paint (INP) dan First Input Delay (FID).

2. **Starlight / Astro (Islands Architecture / Component-Level Hydration)**:
   - **Build Step**: Vite mengeksekusi kompilasi MDX langsung ke template HTML statis. Komponen interaktif (React, Svelte, Vue) diekstraksi menjadi "pulau-pulau" (*islands*) terisolasi.
   - **Runtime**: Secara *default*, **0 KB JavaScript** dikirimkan ke peramban. JavaScript hanya diunduh dan dieksekusi jika komponen diberi direktif khusus seperti `client:load`, `client:idle`, atau `client:visible`.
   - **Karakteristik**: Skor Core Web Vitals optimal secara konsisten. Sangat hemat sumber daya peramban dan cocok untuk situs dokumentasi berbobot ribuan halaman.

3. **Nextra / Next.js (React Server Components Model)**:
   - **Build Step**: Menghubungkan Content Layer dengan arsitektur App Router Next.js. Konten MDX dieksekusi di server/build-time sebagai Server Components.
   - **Runtime**: Rendering dilakukan melalui React Server Components (RSC) payload yang streaming. Interaktivitas terbatas pada komponen berlabel `'use client'`.
   - **Karakteristik**: Fleksibilitas tinggi bila dokumentasi diintegrasikan langsung ke dalam dashboard produk SaaS utama, tetapi membutuhkan overhead pemeliharaan Next.js stack.

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional (Jekyll, Hugo) | Pendekatan Modern SSG (Docusaurus, Starlight, Nextra) |
| :--- | :--- | :--- |
| **Interaktivitas Konten** | Terbatas pada JavaScript vanilla mentah yang di-inject via script tags; rentan tabrakan scope. | Berbasis komponen deklaratif (React/Vue/Svelte via MDX). Dokumentasi dapat memuat *live playground*, API runner, dan simulator UI. |
| **Pipeline Parsing** | Regex / Blackbox Markdown Engine (C/Go based, sulit di-extend). | Unified AST Ecosystem (`remark`/`rehype`). Manipulasi struktur dokumen aman dan berbasis programmatic nodes. |
| **Tipografi & Desain Sistem** | Bergantung pada CSS override global; sulit isolasi. | Terintegrasi langsung dengan Token Desain, Tailwind CSS, atau CSS Modules tingkat komponen. |
| **Model Rehidrasi** | Render statis murni tanpa reaktivitas modern. | *Zero-JS by default* (Starlight) atau *SPA transition* (Docusaurus) dengan manajemen state modern. |
| **Arsitektur API Docs** | Static generator terpisah (e.g. Swagger UI wrapper kaku). | Sinkronisasi dinamis skema OpenAPI langsung ke AST node, mendukung dynamic mock testing. |

---

### 5. How (Workflow Detail)

Siklus hidup deployment enterprise dokumentasi modern melibatkan orkestrasi Docs-as-Code end-to-end:

1. **Schema & Code Extraction**:
   - Sistem CI membaca spesifikasi backend (OpenAPI v3.1, Protobuf, TSDoc).
   - Generator mentransformasi metadata skema menjadi berkas `.mdx` lengkap dengan frontmatter kustom.
2. **Unified AST Pass (Compile Time)**:
   - `remark-parse` membedah Markdown menjadi `mdast`.
   - Plugin enterprise mentransformasi AST (contoh: validasi URL internal, automasi pembuatan *deep anchors*, transformasi diagram Mermaid).
   - `remark-rehype` mentranslasikan `mdast` menjadi `hast`.
   - `rehype-shiki` atau pipeline highlighter memproses *tokens* kode ke format HTML dengan semantic highlighting.
   - Hasil akhir dikompilasi menjadi kode executable JavaScript/JSX.
3. **Optimasi Asset & Bundling**:
   - Bundler (Vite atau Webpack) memproses optimasi aset (konversi WebP/AVIF untuk gambar, pemangkasan CSS yang tidak terpakai).
   - Pembuatan indeks pencarian statis lokal via `pagefind` langsung pada berkas HTML hasil render.
4. **Validasi Integrity**:
   - *Broken links checker* memeriksa tautan internal dan eksternal secara asinkron.
   - *Schema validation* memastikan frontmatter memenuhi kontrak metadata yang ditentukan (zod schema).
5. **Edge Deployment**:
   - Pengunggahan artefak statis ke Cloudflare Pages / AWS S3 + CloudFront.
   - Injeksi HTTP Header: `Cache-Control: public, max-age=31536000, immutable` untuk asset statis bervalue-hash, dan `Cache-Control: public, max-age=0, must-revalidate` untuk dokumen HTML.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Rantai Perakitan Manufaktur Modular
Bayangkan memproduksi sebuah kendaraan kustom:
- **Markdown mentah** adalah bahan baku mentah (baja lembaran, karet, kaca).
- **mdast (Markdown AST)** adalah rangka cetak biru mekanis (mengetahui letak bab, heading, list secara semantik struktural).
- **rehype (HTML AST)** adalah perakitan eksterior (mengetahui struktur fisik bodi kendaraan: `<div>`, `<pre>`, `<code>`).
- **MDX Engine** adalah pemasangan komponen elektrik (mengganti panel speedometer analog biasa dengan layar sentuh interaktif React).
- **Starlight (Islands)** mengirimkan mobil tanpa baterai jika Anda tidak memerlukan fitur pintar (0 KB JS). Namun jika Anda butuh radio interaktif, radio tersebut dipasang bersama baterai kecilnya sendiri (`client:visible`), tanpa membebani mesin utama.

#### Diagram Rantai Transformasi AST

```
 Raw Input (.mdx)
┌────────────────────────────────────────────────────────┐
│ ---                                                    │
│ title: Secure Endpoint                                 │
│ ---                                                    │
│ # Overview                                             │
│ Run: `<Playground endpoint="/api/v1/auth" />`          │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼ [remark-parse]
┌────────────────────────────────────────────────────────┐
│ MDAST:                                                 │
│ {                                                      │
│   type: 'root',                                        │
│   children: [                                          │
│     { type: 'heading', depth: 1, children: [...] },    │
│     { type: 'mdxJsxFlowElement', name: 'Playground',   │
│       attributes: [{ name: 'endpoint', ... }] }        │
│   ]                                                    │
│ }                                                      │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼ [remark-rehype] + [Custom Rehype Transformer]
┌────────────────────────────────────────────────────────┐
│ HAST:                                                  │
│ {                                                      │
│   type: 'element',                                     │
│   tagName: 'div',                                      │
│   properties: { className: ['docs-wrapper'] },         │
│   children: [                                          │
│     { type: 'element', tagName: 'h1', ... },           │
│     { type: 'mdxJsxFlowElement', name: 'Playground',   │
│       attributes: [...] }                              │
│   ]                                                    │
│ }                                                      │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼ [Vite/Webpack Rollup + MDX Core]
┌────────────────────────────────────────────────────────┐
│ Generated Output (HTML + Minified JS Chunk):           │
│ <div class="docs-wrapper">                             │
│   <h1 id="overview">Overview</h1>                      │
│   <astro-island component-url="..." props="...">       │
│     <!-- Fallback SSR HTML -->                         │
│   </astro-island>                                      │
│ </div>                                                 │
└────────────────────────────────────────────────────────┘
```

---

### 7. Simple Example & Practical Example

#### Simple Example: Custom Remark Plugin untuk Injeksi Read-Time dan Sanitasi Metadata

Plugin TypeScript murni untuk ekosistem Unified guna menghitung estimasi waktu membaca dan menambahkan callout peringatan secara otomatis pada dokumen berstatus deprecated.

```typescript
// plugins/remark-enterprise-metadata.ts
import { visit } from 'unist-util-visit';
import type { Root, Heading, Parent } from 'mdast';
import type { Plugin } from 'unified';

interface PluginOptions {
  wordsPerMinute?: number;
}

export const remarkEnterpriseMetadata: Plugin<[PluginOptions?], Root> = (options = {}) => {
  const wpm = options.wordsPerMinute || 200;

  return (tree: Root, file) => {
    let wordCount = 0;

    // Hitung total kata pada node text
    visit(tree, 'text', (node) => {
      const words = node.value.trim().split(/\s+/).filter(Boolean);
      wordCount += words.length;
    });

    const readingTime = Math.ceil(wordCount / wpm);
    file.data.readingTime = readingTime;

    // Deteksi jika frontmatter memiliki status 'deprecated'
    const frontmatter = (file.data.astro as any)?.frontmatter || (file.data as any).frontmatter;
    if (frontmatter?.status === 'deprecated') {
      const warningNode = {
        type: 'mdxJsxFlowElement',
        name: 'Callout',
        attributes: [
          { type: 'mdxJsxAttribute', name: 'type', value: 'danger' },
          { type: 'mdxJsxAttribute', name: 'title', value: 'DEPRECATION NOTICE' },
        ],
        children: [
          {
            type: 'paragraph',
            children: [
              {
                type: 'text',
                value: `Dokumentasi ini usang sejak versi ${frontmatter.deprecatedVersion || 'sebelumnya'}. Fitur ini tidak lagi didukung di production.`,
              },
            ],
          },
        ],
      };

      // Sisipkan di awal dokumen (indeks 0)
      (tree as Parent).children.unshift(warningNode as any);
    }
  };
};
```

#### Practical Enterprise Example: Pipeline Integrasi OpenAPI ke MDX Interaktif untuk Astro Starlight

Skrip automasi skala produksi untuk membaca OpenAPI 3.1 JSON/YAML, menghasilkan berkas MDX teroptimasi, dan menyuntikkan komponen testing API berbasis React Island.

```typescript
// scripts/generate-api-docs.ts
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

interface OpenAPISpec {
  openapi: string;
  info: { title: string; version: string; description: string };
  paths: Record<string, Record<string, any>>;
}

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

async function generateApiDocs(specPath: string, outputDir: string) {
  const rawData = await fs.readFile(specPath, 'utf-8');
  const spec: OpenAPISpec = JSON.parse(rawData);

  await fs.mkdir(outputDir, { recursive: true });

  for (const [endpointPath, methods] of Object.entries(spec.paths)) {
    for (const [method, operation] of Object.entries(methods)) {
      if (['get', 'post', 'put', 'delete', 'patch'].indexOf(method.toLowerCase()) === -1) continue;

      const slug = `${method.toLowerCase()}-${endpointPath.replace(/[^a-zA-Z0-9]/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '')}`;
      const filePath = path.join(outputDir, `${slug}.mdx`);

      const content = `---
title: "${operation.summary || `${method.toUpperCase()} ${endpointPath}`}"
description: "${operation.description?.replace(/"/g, '\\"') || 'No description provided.'}"
sidebar:
  badge:
    text: "${method.toUpperCase()}"
    variant: "${method.toLowerCase() === 'get' ? 'success' : method.toLowerCase() === 'post' ? 'caution' : 'danger'}"
---

import ApiPlayground from '../../../components/api/ApiPlayground.tsx';
import ResponseViewer from '../../../components/api/ResponseViewer.tsx';

### Spesifikasi Endpoint

| Parameter | Properti |
| :--- | :--- |
| **HTTP Method** | \`${method.toUpperCase()}\` |
| **Path** | \`${endpointPath}\` |
| **Auth Required** | \`${operation.security ? 'Yes (Bearer JWT)' : 'None'}\` |

### Deskripsi Operasi
${operation.description || 'Tidak ada dokumentasi mendalam untuk operasi ini.'}

### Interactive Request Console

Gunakan konsol interaktif di bawah ini untuk menguji endpoint secara realtime terhadap sandbox server kami.

<ApiPlayground
  client:visible
  method="${method.toUpperCase()}"
  endpoint="${endpointPath}"
  parameters={${JSON.stringify(operation.parameters || [])}}
  requestBody={${JSON.stringify(operation.requestBody || null)}}
/>

### Contoh Response Sukses (200 OK)

\`\`\`json
${JSON.stringify(
  operation.responses?.['200']?.content?.['application/json']?.example || { status: 'success', timestamp: new Date().toISOString() },
  null,
  2
)}
\`\`\`
`;

      await fs.writeFile(filePath, content, 'utf-8');
      console.log(`[Generated] ${filePath}`);
    }
  }
}

// Eksekusi generator
const SPEC_FILE = path.resolve(__dirname, '../specs/core-api.json');
const OUTPUT_PATH = path.resolve(__dirname, '../src/content/docs/api-reference');

generateApiDocs(SPEC_FILE, OUTPUT_PATH).catch((err) => {
  console.error('Fatal API Docs Generation Error:', err);
  process.exit(1);
});
```

Konfigurasi Astro Starlight (`astro.config.mjs`) untuk integrasi plugin di atas:

```javascript
// astro.config.mjs
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import react from '@astrojs/react';
import { remarkEnterpriseMetadata } from './plugins/remark-enterprise-metadata.ts';

export default defineConfig({
  integrations: [
    starlight({
      title: 'Enterprise Platform Docs',
      defaultLocale: 'root',
      locales: {
        root: { label: 'English', lang: 'en' },
        id: { label: 'Bahasa Indonesia', lang: 'id' },
      },
      sidebar: [
        { label: 'Architecture', autogenerate: { directory: 'architecture' } },
        { label: 'API Reference', autogenerate: { directory: 'api-reference' } },
      ],
      customCss: ['./src/styles/custom.css'],
    }),
    react(), // Digunakan untuk partial hydration ApiPlayground
  ],
  markdown: {
    remarkPlugins: [[remarkEnterpriseMetadata, { wordsPerMinute: 220 }]],
  },
});
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
Sebuah perusahaan FinTech pembayaran memproses dokumentasi untuk 3 kelompok pengguna: Pengembang Eksternal (*Public API*), Tim Kepatuhan Audit (*Compliance Spec*), dan Internal Microservices (*Private RPC*). Repositori dokumentasi memiliki:
- 18.000 halaman Markdown/MDX.
- 4 versi API aktif (v1, v2, v2.1, v3-beta).
- 5 bahasa lokalisasi (en, id, ja, zh, es).

#### Masalah Kritis
Sebelumnya tim menggunakan Docusaurus v2:
1. **Build OOM (Out Of Memory)**: Proses CI runner (8 GB RAM) mati akibat *Node.js JavaScript Heap Out of Memory* saat kompilasi Webpack SSR melewati halaman ke-12.000.
2. **Client Hydration Slowness**: Pengguna di jaringan lambat mengalami degradasi First Input Delay (FID > 450ms) karena bundel JavaScript awal yang dimuat mencapai 3.8 MB untuk seluruh hidrasi React SPA.

#### Solusi Arsitektur
1. **Migrasi Engine ke Astro Starlight**:
   - Memanfaatkan **Zero-JS default**. Menghilangkan hidrasi SPA global. Ukuran transfer JS per halaman turun dari 3.8 MB menjadi **18 KB** (hanya skrip navigasi tema dasar dan search runner).
2. **Implementasi Pagefind untuk Enterprise Offline Search**:
   - Menggantikan Algolia DocSearch crawler yang lambat dan dibatasi rate-limit.
   - Pagefind melakukan *post-build indexing* langsung pada folder `dist/` HTML dalam waktu **8.2 detik** untuk 18.000 halaman.
3. **Partitioned Build Pipeline pada GitHub Actions**:
   - Skrip CI membagi kompilasi bahasa/versi menjadi chunked matrix jobs.
   - Hasil HTML statis digabungkan menggunakan reverse proxy Cloudflare Workers di edge network.

#### Hasil Metrik Produksi

```
Metrik Performa              Docusaurus (Lama)     Astro Starlight (Baru)    Perubahan
───────────────────────────────────────────────────────────────────────────────────────────
Build Time (CI/CD)           24 menit 12 detik     3 menit 45 detik          -84.5%
JS Bundle Size (Landing)     3,800 KB              18.2 KB                   -99.5%
Lighthouse Performance       62 / 100              99 / 100                  +59.6%
Interaction to Next Paint    480 ms                32 ms                     -93.3%
Search Indexing Cost         $1,200/bln (SaaS)     $0 (Pagefind Local)       -100%
CI Memory Consumption        7.8 GB (OOM Spikes)   1.8 GB (Stable)           -76.9%
```

---

### 9. Trade-offs

| Kriteria | Docusaurus (v3) | Astro Starlight | Nextra (v3/v4 App Router) |
| :--- | :--- | :--- | :--- |
| **Hydration Strategy** | **Full React SPA Hydration**. Seluruh halaman dihidrasi ulang. | **Partial Hydration (Islands)**. Default 0 KB JS; hanya memuat JS jika ada direktif `client:*`. | **React Server Components (RSC)**. Sebagian besar server-rendered, selective client boundary. |
| **Build Scale Limit** | **Medium (~5.000-8.000 hal)**. Webpack overhead tinggi; rentan Node heap leak pada spec raksasa. | **Extreme (>50.000 hal)**. Vite + ESBuild; memory footprint terisolasi secara optimal. | **High (~15.000 hal)**. Turbopack/Next.js compiler cepat, namun memory intensive saat static export masif. |
| **Ecosystem & Plugins** | **Sangat Matang**. Ekosistem plugin out-of-the-box sangat kaya (Search, Versioning, i18n native). | **Sedang / Cepat Berkembang**. Perlu perakitan manual untuk fitur tingkat lanjut tertentu. | **Tergantung Next.js**. Memanfaatkan pustaka umum React/Next.js, plugin dokumentasi khusus terbatas. |
| **Search Architecture** | Algolia DocSearch terintegrasi native atau local-search plugin. | Pagefind out-of-the-box (sangat cepat, low memory, run post-build). | Fleksibel via React component hooks (Orama, Algolia, custom vector search). |
| **Hosting Complexity** | Sangat Rendah (Static files: AWS S3, GitHub Pages, Cloudflare). | Sangat Rendah (Pure Static assets). | Rendah-Sedang (Bisa SSG murni, atau butuh Node/Edge runtime jika memakai SSR/ISR). |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Node.js JavaScript Heap Out-Of-Memory (OOM) saat Kompilasi MDX
- **Penyebab**: Penggunaan pustaka transformer atau plugin remark/rehype yang menahan referensi file mentah (`vfile`) di dalam memory closure tanpa dereferencing, menyebabkan Garbage Collector (GC) tidak dapat membebaskan memori.
- **Solusi**:
  1. Tingkatkan batas heap runner sementara: `NODE_OPTIONS="--max-old-space-size=8192"`
  2. Hindari memproses seluruh file secara paralel masif dengan `Promise.all` tak terbatas. Gunakan `p-limit` atau worker thread pooling:
     ```typescript
     import pLimit from 'p-limit';
     const limit = pLimit(navigator.hardwareConcurrency || 4);
     await Promise.all(files.map(file => limit(() => compileMDX(file))));
     ```

#### 2. Hydration Mismatch pada MDX Component Islands
- **Penyebab**: Komponen interaktif (misalnya `ApiPlayground`) membaca objek peramban (`window.localStorage` atau `navigator.userAgent`) langsung pada fase render inisial tanpa proteksi `useEffect` atau pengecekan SSR.
- **Gejala**: Tampilan berkedip (*flicker*), error console `Text content does not match server-rendered HTML`, atau elemen mati (tidak merespons klik).
- **Solusi**:
  ```tsx
  // Gunakan pola Client Mounting Check
  import { useState, useEffect } from 'react';

  export function ApiPlayground() {
    const [isMounted, setIsMounted] = useState(false);
    useEffect(() => {
      setIsMounted(true);
    }, []);

    if (!isMounted) {
      return <div className="skeleton-placeholder">Loading Playground...</div>;
    }

    return <div>{/* Komponen aman mengakses window/localStorage */}</div>;
  }
  ```

#### 3. Algolia Crawler Missing Pages / 403 Forbidden
- **Penyebab**: Security group edge (Cloudflare WAF / AWS Shield) memblokir crawler Algolia DocSearch karena User-Agent tidak dikenali, atau HTML hasil generate tidak menyertakan meta tag crawler yang diwajibkan (`docsearch:version`, `docsearch:language`).
- **Solusi**: Pastikan tag HTML template menyuntikkan semantik meta:
  ```html
  <meta name="docsearch:language" content="id" />
  <meta name="docsearch:version" content="2.0.0" />
  ```
  Dan izinkan subnet IP Algolia pada rule firewall reverse-proxy Anda.

---

### 11. Best Practices (Production Checklist)

#### Pre-build & Linting
- [ ] Validasi frontmatter terotomatisasi menggunakan skema Zod sebelum kompilasi dimulai.
- [ ] Eksekusi Markdown link checker (`markdown-link-check` atau `lychee`) pada pipeline CI untuk memvalidasi broken link lokal maupun eksternal.
- [ ] Enforce standardisasi Heading level (h1 hanya boleh satu kali di awal; hierarki bertingkat h2 -> h3 tanpa lompatan h4).

#### Pipeline Build & Caching
- [ ] Konfigurasi caching direktori `.astro`, `.next/cache`, atau `node_modules/.cache` pada build agent CI/CD.
- [ ] Gunakan Content Hashing untuk file chunk JS/CSS (`[name].[hash].js`).
- [ ] Matikan pembuatan source map di level production (`GENERATE_SOURCEMAP=false`) jika ingin menghemat memori CI dan melindungi intellectual property internal.

#### Delivery & Edge Performance
- [ ] Atur header kompresi modern (`Brotli` level 6 atau `Gzip` level 9).
- [ ] Pastikan tidak ada payload JavaScript yang dihidrasi untuk konten yang sifatnya tekstual statis (*Keep documentation zero-JS as much as possible*).
- [ ] Terapkan Content Security Policy (CSP) ketat yang melarang eksekusi `unsafe-inline` script selain skrip tema ber-nonce.

---

### 12. Hands-on Practice

Buat dan jalankan pipeline integrasi dokumentasi Astro Starlight modern dengan AST transformer kustom. Seluruh kode praktikum ini disimpan pada direktori: `hands-on/m02/`.

#### Langkah 1: Inisialisasi Proyek Headless Starlight

Jalankan perintah shell berikut pada terminal Anda:

```bash
mkdir -p hands-on/m02/enterprise-docs
cd hands-on/m02/enterprise-docs
npm init -y
npm install astro @astrojs/starlight @astrojs/react react react-dom unist-util-visit
npm install -D typescript @types/react @types/node
```

#### Langkah 2: Buat Skrip AST Plugin

Simpan berkas berikut di `hands-on/m02/enterprise-docs/plugins/rehype-code-title.ts`:

```typescript
// plugins/rehype-code-title.ts
import { visit } from 'unist-util-visit';
import type { Plugin } from 'unified';
import type { Element, Root } from 'hast';

export const rehypeCodeTitle: Plugin<[], Root> = () => {
  return (tree) => {
    visit(tree, 'element', (node: Element, index, parent) => {
      if (!parent || index === undefined || node.tagName !== 'pre') return;

      const codeElement = node.children.find(
        (child) => child.type === 'element' && child.tagName === 'code'
      ) as Element | undefined;

      if (!codeElement) return;

      const className = (codeElement.properties?.className as string[]) || [];
      const titleAttr = className.find((cls) => cls.startsWith('title='));

      if (titleAttr) {
        const title = decodeURIComponent(titleAttr.replace('title=', ''));
        const titleNode: Element = {
          type: 'element',
          tagName: 'div',
          properties: { className: ['code-block-header-title'] },
          children: [{ type: 'text', value: title }],
        };

        parent.children.splice(index, 0, titleNode);
      }
    });
  };
};
```

#### Langkah 3: Konfigurasi Astro Engine

Simpan berkas konfigurasi di `hands-on/m02/enterprise-docs/astro.config.mjs`:

```javascript
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import react from '@astrojs/react';
import { rehypeCodeTitle } from './plugins/rehype-code-title.ts';

export default defineConfig({
  integrations: [
    starlight({
      title: 'DevOps Architecture Docs',
      sidebar: [
        {
          label: 'Deployment Guides',
          items: [{ label: 'Zero Trust Network', link: '/guides/zero-trust/' }],
        },
      ],
    }),
    react(),
  ],
  markdown: {
    rehypePlugins: [rehypeCodeTitle],
  },
});
```

#### Langkah 4: Buat Komponen Interactive Island

Simpan berkas di `hands-on/m02/enterprise-docs/src/components/NetworkLatencyCalculator.tsx`:

```tsx
import React, { useState } from 'react';

export default function NetworkLatencyCalculator() {
  const [distanceKm, setDistanceKm] = useState<number>(1000);
  const SPEED_OF_LIGHT_FIBER_KM_MS = 200; // ~200,000 km/s in optical glass

  const theoreticalRtt = ((distanceKm * 2) / SPEED_OF_LIGHT_FIBER_KM_MS).toFixed(2);

  return (
    <div style={{ border: '1px solid #334155', padding: '1.25rem', borderRadius: '8px', margin: '1.5rem 0', background: '#0f172a', color: '#f8fafc' }}>
      <h4 style={{ margin: '0 0 0.75rem 0', color: '#38bdf8' }}>Interactive Metric: Fiber Optic Latency Estimator</h4>
      <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.875rem' }}>
        Jarak Transmisi (KM): <strong>{distanceKm} km</strong>
      </label>
      <input
        type="range"
        min="100"
        max="20000"
        step="100"
        value={distanceKm}
        onChange={(e) => setDistanceKm(Number(e.target.value))}
        style={{ width: '100%', cursor: 'pointer' }}
      />
      <div style={{ marginTop: '1rem', fontSize: '0.95rem' }}>
        Estimasi Teoretis RTT (Round Trip Time): <span style={{ color: '#4ade80', fontWeight: 'bold' }}>{theoreticalRtt} ms</span>
      </div>
    </div>
  );
}
```

#### Langkah 5: Buat Dokumen MDX

Simpan berkas di `hands-on/m02/enterprise-docs/src/content/docs/guides/zero-trust.mdx`:

```mdx
---
title: Arsitektur Zero Trust Cloud Network
description: Spesifikasi teknis packet filtering dan latency budgeting.
---

import NetworkLatencyCalculator from '../../../components/NetworkLatencyCalculator.tsx';

Dokumentasi ini mencakup topologi transport paket untuk jaringan edge enterprise.

### Simulasi Latency Budget

Gunakan simulasi interaktif di bawah ini untuk menghitung budget latensi transport optik edge-to-edge:

<NetworkLatencyCalculator client:visible />

### Konfigurasi Firewall Node

Contoh deklarasi konfigurasi routing paket:

```bash
# title=gateway-rules.sh
iptables -A INPUT -p tcp --dport 443 -j ACCEPT
iptables -A INPUT -p tcp --dport 80 -j DROP
```
```

#### Langkah 6: Kompilasi & Jalankan

Tambahkan skrip di `package.json`:
```json
"scripts": {
  "dev": "astro dev",
  "build": "astro build",
  "preview": "astro preview"
}
```

Uji kompilasi production:
```bash
npm run build
npm run preview
```
Buka peramban di `http://localhost:4321`. Amati bahwa NetworkLatencyCalculator terhidrasi secara mulus via direct island loader tanpa memicu rehidrasi DOM statis lainnya.

---

### 13. Exercise

#### Level Easy
Buat skrip validasi *pre-commit* sederhana menggunakan Node.js murni (`scripts/validate-frontmatter.mjs`) yang memindai seluruh berkas `.md` dan `.mdx` di direktori target, memverifikasi bahwa properti `title` dan `description` tidak kosong, serta mencetak pesan error dan exit code `1` bila validasi gagal.

#### Level Medium
Kembangkan sebuah plugin `rehype` (`rehype-image-optimizer.ts`) yang memodifikasi seluruh tag `img` di AST dokumen:
1. Menyuntikkan atribut `loading="lazy"`.
2. Menyuntikkan atribut `decoding="async"`.
3. Mengubah tautan gambar lokal yang berakhiran `.png` atau `.jpg` secara otomatis menjadi ekstensi `.webp`.

#### Level Hard
Rancang dan implementasikan sebuah *Dynamic Multi-Spec Aggregator*:
- Buat micro-service/skrip TypeScript yang membaca manifest JSON berisi 10 URL repositori OpenAPI berbeda.
- Unduh spesifikasi secara paralel dengan batas concurrency (maksimal 3 concurrent requests).
- Gabungkan (*merge*) skema tersebut ke dalam satu hierarki navigasi terisolasi berdasarkan namespace produk.
- Inject breadcrumb khusus dan token autentikasi mock environment ke setiap file MDX yang dihasilkan.

---

### 14. Challenge

**Studi Kasus**:
Anda adalah Principal Documentation Engineer di sebuah perusahaan *Decentralized Infrastructure* global. Perusahaan memiliki sistem dokumentasi dengan spesifikasi:
1. Memiliki lebih dari **30.000 file dokumentasi aktif**.
2. Dokumen dibagi menjadi 3 tingkat kerahasiaan: `Public`, `Partner-Only`, dan `Internal-Core`.
3. Beberapa dokumen memiliki blok parsial rahasia di dalam file yang sama (misal: satu file MDX memiliki paragraf yang hanya boleh dibaca oleh partner).

**Tantangan**:
Rancang arsitektur build pipeline berbasis Nextra/Astro Starlight dengan kriteria:
1. **Compile-Time AST Striping**: Buat sistem plugin Unified yang membuang node pohon AST bertanda rahasia secara deterministik saat build publik dijalankan, memastikan tidak ada artefak teks sensitif yang tertinggal pada bundel statis publik.
2. **Zero Invalidation Edge Hosting**: Arsitektur deployment multi-stage yang men-deploy 3 varian static bundle (`public/`, `partner/`, `internal/`) ke edge CDN dengan aturan autentikasi via Edge Middleware (Cloudflare Workers / Fastly Compute).
3. **Automated Memory Guard**: Pipeline CI tidak boleh mengonsumsi memori lebih dari 4 GB RAM saat melakukan proses build 30.000 halaman tersebut secara simultan, dengan target waktu build maksimal di bawah 7 menit.

*Tuliskan arsitektur teknis, diagram aliran kontrol data build, dan implementasi plugin Unified AST untuk menyelesaikan tantangan ini.*

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda / Konseptual)

1. **Apa perbedaan fundamental antara MDAST dan HAST dalam pipeline Unified?**
   - A. MDAST merepresentasikan Node.js runtime, sedangkan HAST merepresentasikan Browser DOM.
   - B. MDAST adalah pohon sintaks abstrak untuk Markdown, sedangkan HAST adalah pohon sintaks abstrak untuk HTML.
   - C. MDAST hanya menangani frontmatter, sedangkan HAST menangani code block.
   - D. MDAST adalah format biner, sedangkan HAST adalah format teks JSON.

2. **Pada Astro Starlight, apa yang terjadi secara teknis ketika sebuah komponen MDX dipanggil tanpa direktif `client:*`?**
   - A. Komponen gagal dikompilasi (*compile error*).
   - B. Komponen otomatis direhidrasi saat event `DOMContentLoaded`.
   - C. Komponen dirender murni menjadi HTML statis saat build-time dan 0 KB JavaScript klien yang dikirim.
   - D. Komponen dieksekusi melalui Web Worker di latar belakang.

3. **Mengapa Docusaurus menghasilkan ukuran bundle JavaScript inisial yang umumnya lebih besar dibandingkan Astro Starlight untuk halaman dokumen teks murni?**
   - A. Docusaurus menggunakan framework React yang mengharuskan rehidrasi SPA secara menyeluruh di sisi klien.
   - B. Docusaurus tidak mendukung kompresi Gzip/Brotli.
   - C. Astro Starlight tidak mendukung parsing Markdown bertingkat.
   - D. Docusaurus menyertakan seluruh database pencarian di dalam file `bundle.js`.

4. **Direktif Astro Island manakah yang paling ideal untuk komponen API Playground yang posisinya berada di bagian paling bawah (*fold*) dokumen panjang?**
   - A. `client:load`
   - B. `client:only="react"`
   - C. `client:visible`
   - D. `client:idle`

5. **Apa fungsi utama dari utilitas `unist-util-visit` pada pembuatan plugin remark/rehype?**
   - A. Melakukan HTTP fetch ke server dokumentasi remote.
   - B. Melakukan penelusuran traversal (*walk/traverse*) melintasi node-node AST secara rekursif.
   - C. Mengonversi teks Markdown menjadi representasi buffer biner.
   - D. Memeriksa broken links secara otomatis pada sisi klien.

#### Bagian 2: Intermediate (Analisis Kasus & Algoritma)

6. **Sebuah pipeline build Docusaurus crash dengan error `JavaScript heap out of memory`. Setelah profiling, ditemukan ribuan gambar berukuran besar diimpor langsung via komponen MDX JSX. Mengapa pola impor ini memicu kebocoran memori pada Webpack?**
   - Jelaskan hubungan antara module graph Webpack, pemrosesan base64 inlining, dan memori V8 saat SSR.

7. **Perhatikan kode plugin remark berikut:**
   ```typescript
   export const remarkBadPlugin = () => (tree) => {
     visit(tree, 'link', (node) => {
       fetch(node.url).then((res) => {
         if (res.status === 404) console.error('Broken link:', node.url);
       });
     });
   };
   ```
   **Sebutkan 2 kesalahan fatal arsitektur pada kode di atas terkait penanganan proses asinkron dan stabilitas build pipeline!**

8. **Mengapa integrasi mesin pencari *Pagefind* jauh lebih efisien pada repositori dengan puluhan ribu halaman statis dibanding Algolia crawler tradisional dalam konteks Continuous Deployment?**

9. **Dalam Nextra berbasis Next.js App Router, apa dampak performa jika sebuah halaman dokumentasi MDX dikonfigurasi menggunakan `'use client'` di tingkat paling atas (*root*) file layout dokumen?**

10. **Bagaimana cara mencegah bentrokan CSS cascade (*CSS bleed*) ketika komponen UI interaktif pihak ketiga (seperti Swagger UI) diintegrasikan ke dalam tema kustom SSG modern?**

#### Bagian 3: Enterprise Production Scenarios

11. **Skenario A (Version Control & i18n Branching)**:
    Perusahaan Anda memutuskan untuk mendukung 4 versi software secara bersamaan pada portal dokumentasi, dengan masing-masing versi memiliki 3 bahasa. Tim lokalisasi bekerja secara independen di branch Git berbeda. Jika digabungkan langsung, ukuran repositori membengkak dan waktu build CI memakan waktu 45 menit.
    *Rancang strategi arsitektur Docs-as-Code (melibatkan Git submodules/sparse checkout, caching, dan edge routing) untuk memotong waktu build hingga di bawah 5 menit tanpa memutus tautan navigasi antar-versi.*

12. **Skenario B (Real-time Code Snippet Type Checking)**:
    Banyak contoh kode TypeScript pada dokumentasi publik Anda menjadi usang (*stale*) dan menghasilkan error kompilasi ketika ada rilis framework baru.
    *Rancang arsitektur pipeline CI yang mengekstraksi seluruh blok kode TypeScript dari AST file MDX secara otomatis, mengompilasinya menggunakan TypeScript Compiler API (`tsc`) di memory, dan membatalkan build (*fail the build*) jika terdapat contoh kode yang tidak valid.*

13. **Skenario C (Dynamic Edge Personalization vs SSG)**:
    Manajemen menginginkan portal dokumentasi bersifat statis murni demi kecepatan dan keandalan, namun halaman API Reference harus menampilkan API Key dan Nama Pengguna yang sedang login tanpa memicu rehidrasi penuh atau merusak caching Edge CDN (Cloudflare).
    *Bagaimana arsitektur teknis untuk memadukan Static Site Generation dengan Dynamic Edge Edge-Side Includes (ESI) / Workers HTMLRewriter untuk menyuntikkan data personalisasi user?*

---

### Kunci Jawaban & Panduan Evaluasi Quiz

#### Bagian 1: Basic
1. **B** — MDAST (*Markdown Abstract Syntax Tree*) adalah spesifikasi AST untuk Markdown (primitif: heading, list, code block), sedangkan HAST (*Hypertext Abstract Syntax Tree*) merepresentasikan struktur semantik HTML DOM (primitif: element, tag, properties).
2. **C** — Filosofi inti Astro Islands adalah *Zero-JS by default*. Tanpa direktif hidrasi (`client:*`), Astro hanya merender komponen menjadi HTML string statis saat build-time tanpa menyertakan script JavaScript pendukung di browser.
3. **A** — Docusaurus berbasis arsitektur SPA React murni; setiap halaman memuat runtime React core dan data navigasi JSON untuk mendukung transisi halaman instan via client-side routing.
4. **C** — `client:visible` menunda pengunduhan dan eksekusi bundel JavaScript komponen sampai elemen tersebut masuk ke dalam viewport peramban pengguna (menggunakan `IntersectionObserver`), menghemat bandwidth dan memori inisial.
5. **B** — `unist-util-visit` adalah pustaka utilitas standar Unified untuk menelusuri (*traverse*) pohon AST secara efisien berdasarkan tipe node yang ditargetkan.

#### Bagian 2: Intermediate
6. **Analisis OOM Webpack**: Ketika aset gambar diimpor langsung dalam MDX via sintaks ES Module/JSX, Webpack memasukkan setiap file ke dalam dependency graph kompilasi in-memory. Jika loader mengonversi gambar ke base64 (atau menyimpan buffer mentah di memori untuk hashing dan emisi file) untuk ribuan halaman secara simultan, penggunaan memori V8 heap akan melampaui limitasi Node.js (`~1.4 GB` default) sebelum proses garbage collector sempat membersihkannya. Solusinya adalah menempatkan file statis di folder `public/` dan merujuknya via path string langsung tanpa melewati module bundler graph.
7. **Kesalahan Fatal `remarkBadPlugin`**:
   - *Proses Asinkron Tidak Ditunggu (`Unhandled Promise`)*: Fungsi visitor berjalan sinkron dan tidak me-return atau meng-`await` Promise dari `fetch`. AST compiler akan menyelesaikan build sebelum validasi link selesai, menghasilkan race condition.
   - *Tidak Ada Rate Limiting / Concurrency Control*: Memanggil ratusan `fetch` simultan secara acak akan memicu *socket exhaustion*, error `ECONNRESET`, atau IP runner CI diblokir oleh target endpoint.
8. **Pagefind vs Algolia**: Pagefind berjalan secara lokal di mesin build langsung di atas file HTML statis hasil kompilasi (`dist/`). Pagefind membagi indeks pencarian menjadi *static chunk shards* terindeks kecil yang diunduh browser sesuai kebutuhan pencarian kata. Ini menghilangkan kebutuhan setup crawler eksternal, bebas biaya langganan SaaS, dan tidak membutuhkan waktu crawling eksternal pada jaringan publik.
9. **Dampak `'use client'` pada Root Layout Nextra**: Penggunaan direktif `'use client'` di root layout memaksa seluruh sub-tree hierarki layout tersebut beralih dari React Server Components (RSC) menjadi Client Component. Hal ini mengakibatkan seluruh runtime Nextra, parser metadata, dan komponen UI pendukung dikirimkan sebagai JavaScript client bundle ke browser, menghilangkan manfaat streaming SSR dan meningkatkan ukuran FCP/LCP secara drastis.
10. **Pencegahan CSS Bleed**: Gunakan isolasi melalui Shadow DOM (via Web Components), iframe terisolasi, atau pipeline CSS Modules / scoped CSS. Khusus Swagger UI atau komponen legacy, isolasi terbaik adalah merendernya di dalam custom web component yang melampirkan *Shadow Root* tertutup (`attachShadow({ mode: 'closed' })`), sehingga styling global dokumen tidak bocor ke dalam API UI, dan sebaliknya.

#### Bagian 3: Evaluasi Kasus Enterprise (Rubrik Jawaban Kritis)
11. **Skenario A**: Menggunakan pendekatan *Monorepo Orchestration with Independent Builds*:
    - Pisahkan setiap kombinasi bahasa/versi ke dalam sub-folder independen atau gunakan repository terpisah yang digabungkan saat deployment via Edge Proxy.
    - Pada CI/CD, gunakan shallow clone (`git clone --depth 1`) dan sparse-checkout hanya untuk versi yang mengalami perubahan file.
    - Cloudflare Pages / Workers bertindak sebagai reverse proxy di edge network yang memetakan routing URI (`/docs/v1/en/`, `/docs/v2/id/`) ke bucket static storage yang berbeda. Hal ini memungkinkan build terisolasi hanya memakan waktu 2-3 menit untuk bagian yang berubah saja.
12. **Skenario B**: Arsitektur *Type-Safe Code Pipeline*:
    - Tulis custom build script menggunakan compiler Unified: kumpulkan semua node `code` dengan metastring `ts` atau `typescript`.
    - Simpan setiap blok kode ke dalam file virtual in-memory.
    - Manfaatkan `ts.createProgram()` dari official TypeScript Compiler API dengan `noEmit: true`.
    - Jika compiler mengembalikan diagnosa error sintaks atau interface typing, kumpulkan pesan file, baris baris pada file MDX sumber, lalu lempar exception fatal (`process.exit(1)`) untuk menghentikan CI pipeline sebelum masuk tahap deploy.
13. **Skenario C**: Pola *Edge Slice Insertion / HTMLRewriter*:
    - Kompilasi SSG menghasilkan HTML murni dengan markup token placeholder statis: `<span data-auth-placeholder="api-key">YOUR_API_KEY</span>`.
    - Halaman HTML di-cache secara permanen di Edge CDN (Cache-Control public).
    - Ketika user merequest halaman, request melewati Edge Worker (misal Cloudflare Worker).
    - Edge Worker membaca cookie sesi/JWT user, mendekripsinya, lalu menggunakan `HTMLRewriter` untuk mencegat stream HTML dan menimpa teks placeholder dengan nilai API Key pengguna secara on-the-fly di stream buffer tanpa menyentuh server asal dan tanpa memerlukan client-side React hydration.

---

### 16. Summary

Modern Static Site Generator (SSG) untuk dokumentasi enterprise telah berevolusi melampaui sekadar static site compiler konvensional. Pemahaman mendalam mengenai arsitektur Unified (`mdast` $\rightarrow$ `hast` $\rightarrow$ JSX) memungkinkan rekayasa dokumentasi otomatis berskala masif melalui pipeline Docs-as-Code.

Pergeseran industri dari model Full SPA Rehydration (seperti pada Docusaurus v2) menuju Partial Hydration / Zero-JS by Default (Starlight) dan React Server Components (Nextra) menjawab tuntutan performa Web Vitals dan efisiensi memori build CI/CD. Memilih mesin yang tepat harus disesuaikan dengan skala repositori, batasan infrastruktur kompilasi, serta kebutuhan interaktivitas konten teknis yang dihadapi.