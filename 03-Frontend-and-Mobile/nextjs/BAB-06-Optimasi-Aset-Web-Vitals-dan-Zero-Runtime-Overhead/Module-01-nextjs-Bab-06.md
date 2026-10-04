# BAB 06: OPTIMASI PERFORMA & ASSETS
## Modul 01: Optimasi Aset, Web Vitals, & Zero-Runtime Overhead

---

### SEKSI 01 — IDENTITAS MODUL
* **Track:** 03-Frontend-and-Mobile
* **Kurikulum:** Next.js (App Router Deep Dive)
* **Topik:** Optimasi Aset, Web Vitals, & Zero-Runtime Overhead
* **Target Audience:** Senior Frontend Engineers, Full-Stack Architects, Performance Specialists
* **Prasyarat:** Pemahaman mendalam tentang React Server Components (RSC), HTTP/2-HTTP/3 protocols, browser rendering engine pipelines (Parse, Style, Layout, Paint, Composite), serta ekosistem bundler (Turbopack/Webpack).

---

### SEKSI 02 — LEARNING OBJECTIVES
Setelah menyelesaikan modul ini, peserta didik mampu:
1. Menguasai arsitektur decoding, resizing, dan delivery gambar teroptimasi menggunakan modul `next/image` dengan zero layout shifts.
2. Mengeliminasi render-blocking resource cascade melalui static font optimization (`next/font`) dengan injeksi CSS zero-runtime.
3. Mengorkestrasi pemuatan skrip pihak ketiga (third-party scripts) via `next/script` tanpa mendegradasi Total Blocking Time (TBT) dan Interaction to Next Paint (INP).
4. Menganalisis, mengukur, dan merekayasa aplikasi untuk mencapai nilai 75th percentile Core Web Vitals (LCP $\le 2.5\text{s}$, INP $\le 200\text{ms}$, CLS $\le 0.1$) pada perangkat mid-tier mobile.
5. Mengimplementasikan instrumentasi telemetri Real User Monitoring (RUM) berbasis OpenTelemetry dan Beacon API untuk data Web Vitals granular.

---

### SEKSI 03 — MINDSET & MENTAL MODEL

#### Pergeseran Paradigma
Dalam arsitektur frontend modern, performa bukanlah fase pengujian di akhir siklus pengembangan (post-production polish), melainkan batasan arsitektur (architectural invariant). Mental model yang harus dipegang:
* **The Iron Triangle of Frontend Delivery:** Eksekusi kode harus bergerak dari *Client-side Execution Heavy* menuju *Edge/Server Preparation with Minimal Client Footprint*. 
* **Zero-Runtime Philosophy:** Setiap kilobyte JavaScript yang dikirim ke client membebankan CPU browser dua kali lipat: saat pengunduhan jaringan (network cost) dan saat dekompresi/parsing/kompilasi V8 (execution cost). Jika sebuah style, font, atau transform aset dapat diresolusi pada build/server time, maka runtime library di browser adalah anti-pattern.
* **Layout Stability as Invariant:** Perubahan geometri DOM setelah paint pertama adalah kegagalan rekayasa. Ruang harus dialokasikan sebelum konten diunduh.

```
[Mental Model: Pipeline Eksekusi Performa]
Traditional: [Download HTML] -> [Fetch Blocking CSS/JS] -> [Parse/Compile] -> [Layout] -> [Fetch Assets] -> [CLS Spike]
Next.js Eng: [Edge SSR with Intrinsic Dimensions] -> [Preloaded Critical Assets] -> [Paint Final Layout] -> [Hydrate Non-Blocking]
```

---

### SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

#### 1. Arsitektur Pemrosesan dan Servis Aset (`next/image`)
```
+----------------------------------------------------------------------------------------------------+
|                                    NEXT.JS ASSET PIPELINE                                         |
+----------------------------------------------------------------------------------------------------+
                                                                                                      
 [ Browser Request ]                                                                                  
         │                                                                                            
         ▼                                                                                            
 [ Cloudflare / CDN Edge ] ────(Cache Hit: AVIF/WebP)─────────────────────────────► [ Deliver Asset ] 
         │                                                                                            
    (Cache Miss)                                                                                      
         ▼                                                                                            
 [ Node.js / Edge Server ]                                                                            
    │                                                                                                 
    ├──► Is Route Dynamic / Image Optimizer Endpoint? (_next/image?url=...&w=...&q=...)               
    │         │                                                                                       
    │         ▼                                                                                       
    │    [ Security & Domain Whitelist Validation (next.config.js) ]                                  
    │         │                                                                                       
    │         ▼                                                                                       
    │    [ Check Local Persistent Cache (.next/cache/images) ]                                        
    │         ├──────────(Hit)──────────► [ Read from Disk / Cache ]                                  
    │         │                                    │                                                  
    │      (Miss)                                  ▼                                                  
    │         ▼                             [ Content-Type Negotiation ]                              
    │    [ Fetch Source Asset ]             [ (Accept: image/avif, etc) ]                             
    │    (S3 / R2 / Remote URL)                    │                                                  
    │         │                                    ▼                                                  
    │         ▼                             [ Transmit Optimized Stream ]                             
    │    [ libvips / sharp ] ──────────────────────┘                                                  
    │    (Resize, Color Profile Strip, Re-encode to AVIF/WebP, Set Max-Age Cache Headers)             
    │                                                                                                 
    └─────────────────────────────────────────────────────────────────────────────────────────────────
```

#### 2. Pipeline Injeksi `next/font` Zero-Runtime
```
+----------------------------------------------------------------------------------------------------+
|                                      NEXT/FONT BUILD PIPELINE                                      |
+----------------------------------------------------------------------------------------------------+

 [ Build Time (next build) ]
         │
         ▼
 [ Parse font declaration (e.g., Inter({ subsets: ['latin'] })) ]
         │
         ▼
 [ Fetch remote WOFF2 from Google/External Provider (One-time at build) ]
         │
         ▼
 [ Store binary in .next/static/media/ ]
         │
         ▼
 [ Calculate Font Metrics (ascent, descent, line-gap, units-per-em) ]
         │
         ▼
 [ Generate Zero-Runtime Fallback CSS Style Rule (@font-face with size-adjust) ]
         │
         ▼
 [ Inject generated class and preloaded link tag into HTML Head at SSR ]
```

---

### SEKSI 05 — ANATOMI & MEKANISME INTERNAL

#### 1. `next/image` Transcoding Engine
Komponen `next/image` bukan sekadar pembungkus `<img>`. Di server, request diarahkan ke internal endpoint Next.js yang memanfaatkan binding library native C/C++ `sharp` (berbasis `libvips`). Mekanisme internalnya:
* **Format Negotiation:** Server membedah header `Accept`. Jika browser mengirimkan `image/avif`, server mengonversi buffer menjadi AVIF (kompresi 20-30% lebih padat dibanding WebP). Jika tidak didukung, fallback ke `image/webp` atau format asli.
* **Aspect-Ratio Enforcement:** Komponen mewajibkan atribut `width` dan `height` numerik untuk menghitung rasio aspek intrinsik via CSS `aspect-ratio`. Ini memaksa browser layout engine (Blink/Gecko) mereservasi ruang pada Render Tree sebelum decoding dimulai, mereduksi Cumulative Layout Shift (CLS) ke angka 0.

#### 2. Font Engine & Font Metric Override
Komponen `next/font` meniadakan external HTTP requests (seperti ke `fonts.googleapis.com`) saat runtime:
* **Local Hosting Automation:** Binary font di-download saat kompilasi dan disajikan dari domain lokal yang sama (self-hosted), memangkas DNS lookup, TLS handshake, dan round-trip time (RTT).
* **Metric Override Calculation:** Next.js mengkalkulasi selisih geometris antara web font dan fallback OS font (e.g., Arial, Times New Roman). Mesin ini memproduksi `@font-face` rule sintetis menggunakan deskriptor:
  $$\text{size-adjust} = \frac{\text{target-font-ascent}}{\text{fallback-ascent}}$$
  $$\text{ascent-override}, \quad \text{descent-override}, \quad \text{line-gap-override}$$
  Sehingga saat WOFF2 selesai diunduh dan swap terjadi, tidak terjadi pergeseran layout (FOUT tanpa CLS).

#### 3. `next/script` Execution Scheduling
Mesin `next/script` memetakan strategi ke engine browser:
* `beforeInteractive`: Diinjeksi langsung ke initial HTML Document oleh React Server Components sebelum hydration code. Hanya boleh digunakan untuk engine kritis (e.g., bot detection polyfills).
* `afterInteractive`: Default. Di-load via standard dynamic DOM injection (`document.createElement('script')`) tepat setelah hydration selesai.
* `lazyOnload`: Menggunakan internal wrapper di atas event `window.addEventListener('load')` dan `requestIdleCallback` browser. Menunda eksekusi hingga main-thread sepenuhnya idle.
* `worker`: Memindahkan eksekusi third-party JS sepenuhnya dari main thread ke Web Worker menggunakan integrasi Partytown.

---

### SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

#### Web Vitals Under The Hood

##### 1. Largest Contentful Paint (LCP)
LCP mengukur waktu render elemen visual terbesar dalam viewport. Elemen ini umumnya adalah `<img>`, `<image>` (dalam SVG), elemen dengan `background-image`, atau blok teks level blok besar.
* **Critical Path Formula:**
  $$\text{LCP} = \text{TTFB} + \text{Resource Load Delay} + \text{Resource Load Time} + \text{Element Render Delay}$$
* Next.js menangani *Resource Load Delay* menggunakan atribut `priority` pada `next/image`. Saat disetel `true`, Next.js menginjeksi tag `<link rel="preload" as="image" href="..." fetchpriority="high">` langsung pada `<head>` dokumen SSR, memberi tahu parser C++ browser untuk mulai mengunduh gambar secara paralel dengan parsing HTML/CSS, melewati antrean koneksi standar.

##### 2. Interaction to Next Paint (INP)
INP merepresentasikan latensi interaksi terburuk sepanjang lifecycle aplikasi (bukan hanya First Input Delay / FID).
* **Komposisi Latensi:**
  $$\text{Latency} = \text{Input Delay} + \text{Processing Time (Event Handlers)} + \text{Presentation Delay (Composite/Paint)}$$
* Third-party scripts yang berjalan pada main-thread memblokir event loop. Dengan mendegradasi TBT (Total Blocking Time) melalui strategi deferment `next/script`, task queues pada V8 engine tetap bersih, memungkinkan browser langsung merespons input sentuhan/ketukan keyboard tanpa frame drop.

##### 3. Cumulative Layout Shift (CLS)
* Formula:
  $$\text{CLS} = \sum (\text{Impact Fraction} \times \text{Distance Fraction})$$
* Penggunaan `next/image` dengan dimensi eksplisit atau properti `fill` yang dikombinasikan dengan wrapper parent ber-CSS `position: relative` dan `aspect-ratio` menjamin *Impact Fraction* bernilai $0$.

---

### SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut implementasi struktural dasar penggabungan ketiga primitif optimasi di App Router (`app/layout.tsx` dan `app/page.tsx`).

#### 1. Setup Konfigurasi (`next.config.ts`)
```typescript
import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  images: {
    formats: ['image/avif', 'image/webp'],
    deviceSizes: [640, 750, 828, 1080, 1200, 1920, 2048],
    imageSizes: [16, 32, 48, 64, 96, 128, 256, 384],
    minimumCacheTTL: 31536000, // 1 year cache
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'assets.enterprise.cdn.com',
        port: '',
        pathname: '/media/**',
      },
    ],
  },
  experimental: {
    nextScriptWorkers: true, // Support Partytown worker strategy
  },
};

export default nextConfig;
```

#### 2. Root Layout dengan Zero-Runtime Font (`app/layout.tsx`)
```typescript
import type { Metadata } from 'next';
import { Inter, JetBrains_Mono } from 'next/font/google';
import Script from 'next/script';
import './globals.css';

const inter = Inter({
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-inter',
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-mono',
});

export const metadata: Metadata = {
  title: 'High-Performance Enterprise Architecture',
  description: 'Mission-critical application optimized for Core Web Vitals',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="id" className={`${inter.variable} ${jetbrainsMono.variable}`}>
      <head />
      <body className="font-sans antialiased bg-slate-950 text-slate-50">
        {children}
        
        {/* Analytics dengan lazy loading agar tidak menghambat main thread */}
        <Script
          src="https://www.googletagmanager.com/gtag/js?id=G-TRACKINGID"
          strategy="lazyOnload"
        />
        <Script id="google-analytics-init" strategy="lazyOnload">
          {`
            window.dataLayer = window.dataLayer || [];
            function gtag(){dataLayer.push(arguments);}
            gtag('js', new Date());
            gtag('config', 'G-TRACKINGID');
          `}
        </Script>
      </body>
    </html>
  );
}
```

#### 3. Core Image Element (`app/page.tsx`)
```typescript
import Image from 'next/image';

export default function Page() {
  return (
    <main className="min-h-screen p-8 max-w-7xl mx-auto space-y-12">
      <header className="space-y-4">
        <h1 className="text-4xl font-extrabold tracking-tight">
          Enterprise Asset Engine
        </h1>
        <p className="text-slate-400">
          Zero-Runtime, Pure Web Vitals Compliance
        </p>
      </header>

      {/* LCP Candidate: Priority wajib aktif */}
      <section className="relative w-full h-[480px] rounded-2xl overflow-hidden border border-slate-800">
        <Image
          src="https://assets.enterprise.cdn.com/media/hero-banner.jpg"
          alt="Dashboard Infrastructure Visualization"
          fill
          priority
          sizes="(max-width: 768px) 100vw, (max-width: 1200px) 90vw, 1200px"
          className="object-cover"
          quality={85}
        />
      </section>
    </main>
  );
}
```

---

### SEKSI 08 — ANALISIS BARIS DEMI BARIS

Menganalisis implementasi dari kode di Seksi 07:

1. **`next.config.ts` -> `formats: ['image/avif', 'image/webp']`**
   * *Mekanisme:* Menentukan prioritas konversi format. Array terurut dari kiri ke kanan. Server akan memvalidasi apakah browser mengirim `image/avif` di header `Accept`. Jika ya, kompresi encoding AVIF dijalankan; jika tidak, beralih mengecek WebP.
2. **`next.config.ts` -> `minimumCacheTTL: 31536000`**
   * *Mekanisme:* Mengontrol header `Cache-Control: public, max-age=31536000, immutable` pada respon internal optimizer, memaksa upstream CDN dan downstream client meng-cache binary tanpa revalidasi berulang.
3. **`app/layout.tsx` -> `const inter = Inter({ subsets: ['latin'], variable: '--font-inter' })`**
   * *Mekanisme:* Inisialisasi engine compiler font. Mengunduh subset WOFF2 saat build, membedah metrics font, menghasilkan CSS class name statis, dan memetakan variabel CSS `--font-inter` langsung ke root `<html>`.
4. **`app/page.tsx` -> `priority` (Boolean)**
   * *Mekanisme:* Menonaktifkan strategi default lazy-loading (`loading="lazy"` native). Menginstruksikan Next.js untuk menyisipkan preload link ke node HTML Document Server Render. Memastikan fetching gambar dimulai pada request packet stream pertama, mereduksi LCP *Resource Load Delay* hingga nol milidetik.
5. **`app/page.tsx` -> `sizes="(max-width: 768px) 100vw, ... 1200px"`**
   * *Mekanisme:* Mencegah browser salah mengasumsikan viewport size gambar sebelum layout CSS ter-parse. Browser menggunakan atribut ini untuk memilih `srcset` spesifik terkecil dari variasi yang di-generate Next.js, menghemat penggunaan kuota jaringan (bandwidth savings).

---

### SEKSI 09 — STUDI KASUS NYATA (Enterprise Scale)

#### Skenario Arsitektur
Sebuah platform E-Commerce Multi-Brand Global ("MegaStore Cloud") memiliki katalog lebih dari 10.000.000 produk. Halaman Product Display Page (PDP) mengalami penurunan conversion rate sebesar 14% karena metrik performa buruk:
* **LCP:** 4.8 detik (Target: $\le 2.0$ detik) di jaringan 4G.
* **CLS:** 0.38 (Target: $\le 0.05$) akibat hero gallery dinamis dan font loading flash.
* **INP:** 420 milidetik akibat pelacakan analitik vendor ganda (Google Tag Manager, Segment, Hotjar, TikTok Pixel).
* **Network Payload:** Ukuran initial HTML dan aset mencapai ~6.5MB.

```
Sebelum Optimasi:
Browser Request ──► Render HTML (Blank Space) ──► Load Font (FOUT Spike: CLS 0.38)
                          │
                          ├─► Download Hero Img (Unoptimized 4K, 3.2MB: LCP 4.8s)
                          └─► Third-Party Scripts Block Main Thread (INP 420ms)

Setelah Optimasi (Target):
Browser Request ──► Edge HTML Stream (Fallback Font Metrik Presisi: CLS 0.00)
                          │
                          ├─► Preloaded AVIF Hero (Edge Transcoded, 72KB: LCP 1.1s)
                          └─► Third-Party Script Offloaded to Worker/Lazy (INP 45ms)
```

Target arsitektur: Mengonstruksi arsitektur PDP berkinerja tinggi, zero layout shift, zero-runtime CSS font overrides, dan offloading skrip analitik berat.

---

### SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

#### 1. Abstraksi Image Pre-Generation & Placeholders (`lib/image-utils.ts`)
```typescript
import { getPlaiceholder } from 'plaiceholder';

export interface OptimizedImageData {
  src: string;
  blurDataURL: string;
  width: number;
  height: number;
}

export async function generateOptimizedBlur(imageUrl: string): Promise<OptimizedImageData> {
  const res = await fetch(imageUrl, { next: { revalidate: 86400 } });
  
  if (!res.ok) {
    throw new Error(`Failed to fetch image buffer for blur generation: ${res.statusText}`);
  }

  const buffer = Buffer.from(await res.arrayBuffer());
  const { base64, metadata } = await getPlaiceholder(buffer, { size: 10 });

  return {
    src: imageUrl,
    blurDataURL: base64,
    width: metadata.width,
    height: metadata.height,
  };
}
```

#### 2. Enterprise Product Gallery Component (`components/product-gallery.tsx`)
```typescript
'use client';

import React, { useState } from 'react';
import Image from 'next/image';
import { OptimizedImageData } from '@/lib/image-utils';

interface ProductGalleryProps {
  media: OptimizedImageData[];
  productName: string;
}

export function ProductGallery({ media, productName }: ProductGalleryProps) {
  const [selectedIndex, setSelectedIndex] = useState<number>(0);
  const activeImage = media[selectedIndex] ?? media[0];

  return (
    <div className="flex flex-col-reverse lg:flex-row gap-4 w-full">
      {/* Thumbnail Track */}
      <div className="flex lg:flex-col gap-2 overflow-x-auto lg:overflow-y-auto max-h-[600px] no-scrollbar">
        {media.map((item, index) => {
          const isSelected = selectedIndex === index;
          return (
            <button
              key={item.src}
              type="button"
              onClick={() => setSelectedIndex(index)}
              className={`relative w-20 h-20 flex-shrink-0 rounded-lg overflow-hidden border-2 transition-all ${
                isSelected ? 'border-indigo-500 ring-2 ring-indigo-500/20' : 'border-slate-800 hover:border-slate-600'
              }`}
            >
              <Image
                src={item.src}
                alt={`${productName} thumbnail ${index + 1}`}
                fill
                sizes="80px"
                className="object-cover"
                loading="lazy"
              />
            </button>
          );
        })}
      </div>

      {/* Main Hero Viewer (LCP Critical Path Element) */}
      <div className="relative flex-1 aspect-square rounded-2xl overflow-hidden bg-slate-900 border border-slate-800">
        <Image
          key={activeImage.src}
          src={activeImage.src}
          alt={`${productName} primary view`}
          fill
          priority // Highest fetch priority for above-the-fold
          sizes="(max-width: 1024px) 100vw, 600px"
          placeholder="blur"
          blurDataURL={activeImage.blurDataURL}
          className="object-cover transition-opacity duration-300"
          quality={85}
        />
      </div>
    </div>
  );
}
```

#### 3. Real-World PDP Server Component Integration (`app/products/[slug]/page.tsx`)
```typescript
import { notFound } from 'next/navigation';
import { ProductGallery } from '@/components/product-gallery';
import { generateOptimizedBlur } from '@/lib/image-utils';
import Script from 'next/script';

interface ProductPageProps {
  params: Promise<{ slug: string }>;
}

async function getProductData(slug: string) {
  // Simulasi data fetch dari Backend Microservice
  if (slug !== 'hyper-sneaker-x') return null;

  const rawImages = [
    'https://assets.enterprise.cdn.com/media/sneaker-main.jpg',
    'https://assets.enterprise.cdn.com/media/sneaker-angle.jpg',
    'https://assets.enterprise.cdn.com/media/sneaker-sole.jpg',
  ];

  // Pipeline parallel processing server-side blurhash placeholders
  const processedImages = await Promise.all(
    rawImages.map((url) => generateOptimizedBlur(url))
  );

  return {
    id: 'prod_987123',
    name: 'Nike Air VaporMax Enterprise Edition',
    price: '$220.00',
    description: 'Precision engineered zero-runtime high performance footwear.',
    images: processedImages,
  };
}

export default async function ProductPage({ params }: ProductPageProps) {
  const { slug } = await params;
  const product = await getProductData(slug);

  if (!product) {
    notFound();
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 lg:py-12">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-start">
        {/* Render Critical Image Pipeline */}
        <ProductGallery media={product.images} productName={product.name} />

        {/* Product Details Section */}
        <div className="flex flex-col space-y-6">
          <div className="space-y-2">
            <span className="text-sm font-semibold tracking-wider text-indigo-400 uppercase">
              Limited Tier Release
            </span>
            <h1 className="text-3xl sm:text-4xl font-black text-slate-100">
              {product.name}
            </h1>
            <p className="text-2xl font-mono text-emerald-400 font-bold">
              {product.price}
            </p>
          </div>

          <p className="text-slate-400 leading-relaxed">
            {product.description}
          </p>

          <button
            type="button"
            className="w-full h-14 bg-indigo-600 hover:bg-indigo-500 active:scale-[0.99] font-medium rounded-xl transition-all shadow-lg shadow-indigo-600/20"
          >
            Add to Bag
          </button>
        </div>
      </div>

      {/* Heavy Third-Party Script Offloading */}
      {/* 1. Hotjar Analytics: lazyOnload to save initial main-thread */}
      <Script id="hotjar-analytics" strategy="lazyOnload">
        {`
          (function(h,o,t,j,a,r){
              h.hj=h.hj||function(){(h.hj.q=h.hj.q||[]).push(arguments)};
              h._hjSettings={hjid:3000000,hjsv:6};
              a=o.getElementsByTagName('head')[0];
              r=o.createElement('script');r.async=1;
              r.src=t+h._hjSettings.hjid+j+h._hjSettings.hjsv;
              a.appendChild(r);
          })(window,document,'https://static.hotjar.com/c/hotjar-','.js?sv=');
        `}
      </Script>

      {/* 2. Worker Strategy: Menjalankan eksekusi skrip analitik di Background Thread via Partytown */}
      <Script
        src="https://connect.facebook.net/en_US/fbevents.js"
        strategy="worker"
      />
    </div>
  );
}
```

---

### SEKSI 11 — TRADE-OFFS & ANALISIS KOMPARATIF

#### 1. `next/image` vs Pure HTML5 `<img>` with `picture` Tag
| Parameter | `next/image` Engine | Native HTML5 `<img>` / `<picture>` |
| :--- | :--- | :--- |
| **Compute Overhead** | Server/Edge execution cost (libvips transcoding on miss) | Pure static transfer (Zero dynamic compute) |
| **Automatic Formats** | Dynamic AVIF/WebP parsing based on client capability | Harus dikonversi manual dan ditulis via puluhan baris `<source>` |
| **Intrinsic Sizing** | Mandatory enforcement; layout shifts dieliminasi by default | Rawan pergeseran tata letak tanpa deklarasi CSS eksplisit |
| **Storage Impact** | Cache storage di server bertumbuh (`.next/cache/images`) | Hanya menggunakan file fisik yang disimpan di storage bucket |

#### 2. `next/font` Local Optimization vs Hosted CDN (Google Fonts, Typekit)
| Fitur | `next/font` Built-in | Traditional External CDN (`<link href="...">`) |
| :--- | :--- | :--- |
| **Network Hops** | 0 RTT (Self-hosted on origin domain) | 2x DNS resolution + TLS handshakes (gstatic & googleapis) |
| **Privacy / GDPR** | 100% compliant (Client IP tidak terekspos ke vendor) | Non-compliant by default di region Uni Eropa |
| **Layout Shift (FOUT)** | 0 Shift (Metric adjustments over native fonts) | Visible shift saat font swaps dari Fallback ke CDN Font |
| **Bundle Pipeline** | Diunduh satu kali saat `next build` | Dynamic fetching terus-menerus pada setiap runtime request client |

#### 3. `next/script` Strategies Lifecycle

```
Timeline: [Navigasi Dimulai] ───────────────────────────────────────────► [Idle]
Strategy:
beforeInteractive : ├──[Download & Execute Blocking HTML]──┤
afterInteractive  :                                        ├──[Hydration]──► [Download & Execute]
lazyOnload        :                                                                              ├──[requestIdleCallback]──►
worker (Partytown): ├──[Offload execution to Web Worker thread via postMessage proxy]───────────►
```

---

### SEKSI 12 — EDGE CASES & PITFALLS

#### 1. The Dynamic SVG Rasterization Hazard
* **Problem:** Menyajikan SVG melalui endpoint `next/image` default dapat merusak rendering vektor scalable atau menimbulkan celah Cross-Site Scripting (XSS) jika SVG mengandung elemen `<script>` embedded.
* **Mitigation:**
  Nonaktifkan rasterization untuk SVG atau gunakan config keamanan khusus:
  ```typescript
  // next.config.ts
  images: {
    dangerouslyAllowSVG: true,
    contentDispositionType: 'attachment',
    contentSecurityPolicy: "default-src 'self'; script-src 'none'; sandbox;",
  }
  ```

#### 2. The Multi-Tier CDN Double-Caching Invalidation
* **Problem:** Di cloud architecture (misalnya Cloudflare di depan Vercel/Node Server), request `_next/image` menghasilkan status HTTP `200` dengan cache header immutable dari Node runtime, tetapi CDN upstream menyimpan stale images ketika source media di S3 berganti dengan nama file identik.
* **Mitigation:**
  Implementasikan image versioning menggunakan content hashing pada query parameter (`/image.png?v=hash123`) atau triggers cache purge upstream programmatic via REST API saat asset diperbarui di S3.

#### 3. Container Fluidity Dropdowns (Broken Aspect-Ratio on `fill`)
* **Problem:** Ketika menggunakan properti `fill` pada parent elemen yang tidak memiliki styling layout eksplisit (`position: relative`, `aspect-ratio`, atau `height`), ukuran gambar merembet ke $0\times0$ piksel atau merusak keseluruhan alur DOM cascade.
* **Mitigation:** Wajibkan wrapper pattern CSS:
  ```tsx
  <div className="relative w-full aspect-[16/9]">
    <Image src="/hero.png" alt="Hero" fill className="object-cover" />
  </div>
  ```

---

### SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

#### Anti-Pattern 1: Menggunakan Atribut `priority` Berlebihan
```typescript
// ❌ ANTI-PATTERN: Menambahkan priority ke seluruh item gallery
{products.map((p) => (
  <Image key={p.id} src={p.img} alt={p.name} width={300} height={300} priority />
))}
```
* **Dampak:** Memaksa puluhan network request bersaing menggunakan resource prioritisation `high`. Ini menyebabkan bandwidth starvation untuk critical bundle JS, merusak LCP dan memicu First Input Delay.
* **Solusi:** Hanya terapkan `priority` pada 1 atau maksimal 2 elemen gambar visual yang terjamin berada *above-the-fold* pada layout mobile.

#### Anti-Pattern 2: Missing `sizes` Property pada Responsive Images
```typescript
// ❌ ANTI-PATTERN: Browser mengasumsikan gambar memakan 100vw di semua breakpoints
<Image src="/banner.jpg" alt="Banner" fill />
```
* **Dampak:** Pada desktop screen dengan resolusi 4K, browser akan mendownload versi gambar terbesar (misal lebar 3840px) meskipun container visual layout hanya berukuran 400px.
* **Solusi:** Selalu deklarasikan media queries eksplisit pada atribut `sizes`:
  ```typescript
  // ✅ BENAR
  <Image
    src="/banner.jpg"
    alt="Banner"
    fill
    sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 33vw"
  />
  ```

#### Anti-Pattern 3: Injeksi Third-Party GTM Script Tanpa `next/script`
```typescript
// ❌ ANTI-PATTERN: Injeksi manual di custom layout
<head>
  <script src="https://analytics.vendor.com/bundle.js" />
</head>
```
* **Dampak:** Parse blocking synchronous engine. Parser HTML browser terhenti total saat mendownload dan mengevaluasi skrip pihak ketiga, menghancurkan metrik TTFB dan FCP.
* **Solusi:** Gunakan komponen `next/script` dengan parameter `strategy="afterInteractive"` atau `lazyOnload`.

---

### SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Subresource Integrity (SRI) pada Eksternal Script:** Pasang hash `integrity` saat me-load skrip dari public CDN menggunakan `next/script`.
2. **Local Font Variable Scoping:** Deklarasikan font instances di modul file terpisah (`app/fonts.ts`) dan ekspor variabelnya untuk dikonsumsi layout atau komponen Tailwind CSS tanpa reinstansiasi berulang.
3. **Responsive Dimension Budgeting:** Batasi jumlah preset resolusi pada `deviceSizes` di konfigurasi Next.js untuk mencegah kelebihan utilisasi storage cache image optimization server.
4. **Tailwind Font Variable Integration:** Konfigurasikan fallback system fonts di file CSS atau file Tailwind agar matching dengan calculated metrics dari `next/font`:
   ```css
   @layer base {
     :root {
       --font-sans: var(--font-inter), -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
     }
   }
   ```

---

### SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

#### 1. Node.js Sharp Tuning untuk Concurrency Tinggi
Secara default, library `sharp` mengalokasikan multiple worker threads yang sesuai dengan jumlah core CPU. Dalam container terkontainerisasi (Docker) dengan memory limit ketat, ini dapat memicu memory exhaustion (OOM Exception). Lakukan konfigurasi tuning memory allocation pada startup server Next.js (`server.js` atau instrumentation phase):
```javascript
// instrumentation.ts
export async function register() {
  if (process.env.NEXT_RUNTIME === 'nodejs') {
    const sharp = require('sharp');
    // Membatasi memory cache internal libvips
    sharp.cache({ memory: 256, files: 0, items: 100 });
    // Batasi thread concurrency untuk stabilitas instance
    sharp.concurrency(1);
  }
}