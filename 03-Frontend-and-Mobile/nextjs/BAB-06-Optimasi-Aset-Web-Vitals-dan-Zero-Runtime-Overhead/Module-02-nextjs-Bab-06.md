# Kurikulum Rekayasa Perangkat Lunak Enterprise: Next.js
## Topik: 03-Frontend-and-Mobile
## Bab 06: Optimasi Aset, Web Vitals, dan Zero-Runtime Overhead
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Principal Software Engineer/Senior Frontend Architect diharapkan mampu:
- **Menganalisis dan Membedah Internal Pipeline Optimasi Aset**: Memahami cara kerja compiler Next.js dalam menangani transformasi gambar (`next/image`), font (`next/font`), dan skrip pihak ketiga (`next/script`) pada layer kompilasi dan runtime.
- **Mengeliminasi Cumulative Layout Shift (CLS)**: Merancang strategi mitigasi layout shift absolut hingga nilai CLS $\le 0.01$ melalui kalkulasi metrik *fallback font* otomatis dan penentuan rasio aspek deterministik.
- **Mengoptimalkan Largest Contentful Paint (LCP)**: Mengonfigurasi *resource priority hints* (`priority`, `fetchpriority="high"`, preloading, format AVIF/WebP) serta arsitektur CDN/Edge Image Optimizer untuk mencapai LCP $\le 1.2$ detik pada jaringan seluler 4G.
- **Mengurangi Interaction to Next Paint (INP)**: Mengidentifikasi *long tasks* dan *main thread blocking* akibat hidrasi komponen, *CSS-in-JS runtime overhead*, dan eksekusi skrip pihak ketiga (3P) guna mempertahankan INP $\le 150\text{ ms}$.
- **Mengimplementasikan Zero-Runtime Styling**: Menggantikan arsitektur CSS-in-JS dinamis (Emotion, Styled Components) dengan solusi zero-runtime (Tailwind CSS, Vanilla Extract, CSS Modules) untuk mereduksi *First Input Delay* / INP dan ukuran bundel JavaScript.
- **Membangun Sistem RUM (Real User Monitoring) Telemetry**: Membangun *pipeline* pelaporan metrik Core Web Vitals kustom berbasis OpenTelemetry dan Beacon API yang terintegrasi langsung dengan sistem observabilitas enterprise.

---

### 2. Prerequisite
Sebelum mendalami modul ini, peserta wajib menguasai:
- **Arsitektur Rendering Lanjutan**: Mekanisme React Server Components (RSC), Suspense streaming, dan Progressive Hydration pada Next.js App Router.
- **Browser Internals & Rendering Engine**: Alur eksekusi Blink/Gecko: DOM Tree $\to$ CSSOM $\to$ Render Tree $\to$ Layout (Reflow) $\to$ Paint $\to$ Compositing.
- **Network Protocols & Transfer Optimization**: HTTP/2 multiplexing, HTTP/3 QUIC, TCP slow-start, serta *caching directives* (`immutable`, `stale-while-revalidate`).
- **Web Performance APIs**: Pengetahuan mendalam tentang `PerformanceObserver`, `PerformanceNavigationTiming`, `LargestContentfulPaint`, `LayoutShift`, dan `LongAnimationFrameTiming` (LoAF).

---

### 3. Concept & Internal Architecture

#### A. Internal Arsitektur `next/image` & Pipeline Optimasi Gambar
Komponen `next/image` bukan sekadar pembungkus tag `<img>` HTML biasa, melainkan antarmuka klien ke *pipeline* pemrosesan gambar terdistribusi:

```
[Browser Request]
       │ (Request: /_next/image?url=...&w=1200&q=75)
       ▼
[Edge / Next.js Server (Image Optimization API)]
       │
       ├── 1. Hash Check & Cache Lookup (.next/cache/images)
       │      ├── Cache Hit  ──► Return Cached WebP/AVIF (304 / 200 Stream)
       │      └── Cache Miss ──┐
       │                       ▼
       │             2. Upstream Image Fetch (S3/GCS/External CMS)
       │                       │
       │                       ▼
       │             3. In-Memory Transcoding (Sharp / libvips)
       │                - Resizing (w=1200)
       │                - Format Negotiation (Accept: image/avif, image/webp)
       │                - Quality Compression (q=75)
       │                - Strip EXIF Metadata
       │                       │
       │                       ▼
       │             4. Atomic Write to Disk/S3 Cache
       │                       │
       │                       ▼
       └───────────── 5. Response to Client (Cache-Control: public, max-age=31536000, immutable)
```

1. **Format Negotiation via Content Negotiation**: Next.js membaca *header* HTTP `Accept`. Jika browser mendukung `image/avif`, konversi dialokasikan ke AVIF terlebih dahulu. Jika tidak, dialihkan ke `image/webp`, dan terakhir fallback ke format asli (kecuali SVG yang di-*sanitize*).
2. **Sharp Engine Binding**: Di lingkungan Node.js, Next.js menggunakan *binding* C++ berkecepatan tinggi ke `libvips` via pustaka `sharp`. Sharp mengonsumsi memori jauh lebih sedikit dibandingkan ImageMagick karena melakukan kompresi secara *streaming chunk* tanpa memuat seluruh *bitmap* yang belum terkompresi ke dalam RAM secara bersamaan.
3. **Automatic SourceSet Generation**: Komponen secara otomatis menyusun atribut `srcset` dan `sizes` berdasarkan array `deviceSizes` dan `imageSizes` yang didefinisikan pada `next.config.js`.

#### B. Internal Arsitektur `next/font`: Zero-CLS Font Delivery
Masalah terbesar web font adalah Flash of Unstyled Text (FOUT) dan Flash of Invisible Text (FOIT), yang keduanya memicu pergeseran tata letak (CLS). `next/font` menyelesaikan ini pada level **build-time**:

```
[Build Time: next build]
       │
       ├── 1. Ekstraksi Google Fonts / Local Font Files
       ├── 2. Unduh Font Binary (.woff2) secara lokal (Self-Hosting Otomatis)
       ├── 3. Analisis Font Metrics (Units Per Em, Cap Height, Ascent, Descent)
       ├── 4. Generate Fallback Metrics Font (@font-face Override)
       │      - size-adjust = (Target Metric / Fallback Metric)
       │      - ascent-override
       │      - descent-override
       │      - line-gap-override
       └── 5. Injeksi Pre-calculated CSS Variables ke HTML Payload
```

Dengan mengkalkulasi metrik font cadangan (misalnya, `Arial` atau `Times New Roman`) agar identik secara geometris dengan *custom font* (misalnya, `Inter` atau `Roboto`), browser merender teks cadangan dengan dimensi kotak pembatas (*bounding box*) yang identik secara piksel. Ketika file `.woff2` selesai diunduh, penukaran font (*font swap*) tidak menimbulkan pergeseran tata letak horizontal maupun vertikal ($\Delta \text{Layout} = 0$).

#### C. Runtime Overhead Eliminator: Zero-Runtime CSS vs CSS-in-JS
CSS-in-JS tradisional (seperti Emotion dan Styled Components versi lama) mengeksekusi logika komputasi gaya secara *runtime* di thread utama browser:
1. React mengevaluasi komponen.
2. Library membaca props dan mengomputasi string CSS baru.
3. Hash unik dihasilkan (misalnya, `css-1a2b3c`).
4. Library menyuntikkan rule baru ke dalam `<style>` tag melalui `CSSStyleSheet.insertRule()`.
5. Browser terpaksa membatalkan status style engine (*style invalidation*) dan menjalankan kalkulasi ulang style (*re-recalculate styles*).

Zero-Runtime CSS (Tailwind, Vanilla Extract, CSS Modules) memindahkan seluruh proses ini ke **Build Time**:
- Seluruh kelas CSS telah diekstraksi ke file statis tunggal yang di-cache secara permanen.
- Tidak ada runtime library yang diunduh ke browser (menghemat 12–35 KB JS parsed).
- Thread utama (Main Thread) bebas dari *scripting overhead* selama proses rendering, menjaga nilai **INP** tetap rendah.

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional | Pendekatan Enterprise Next.js |
| :--- | :--- | :--- |
| **Pemuatan Gambar** | Tag `<img>` mentah, resolusi tunggal dari CDN, rentan CLS tanpa atribut dimensi yang tepat. | `next/image` otomatis *content-negotiated* (AVIF/WebP), deterministik `srcset`, LQIP blurhash, Sharp *edge/server processing*. |
| **Pemuatan Font** | Tag `<link href="https://fonts.googleapis.com">`, eksternal DNS handshake, FOUT/FOIT tinggi, degradasi CLS. | `next/font` *zero-network-dependency*, otomatis di-*self-host*, kalkulasi `size-adjust` fallback otomatis, 0 CLS. |
| **Eksekusi 3rd Party Script** | Tag `<script>` manual di `<head>` atau `<body>`, memblokir *parser*, memicu *Long Tasks*, merusak INP. | `next/script` dengan strategi `afterInteractive`, `lazyOnload`, atau offloading ke Web Worker via Partytown (`worker`). |
| **Manajemen Styling** | CSS-in-JS Runtime (Emotion/Styled Components) dengan *style injection overhead* pada client. | Zero-Runtime Compiler (Tailwind CSS v3/v4, Vanilla Extract) tanpa eksekusi JS pada thread rendering UI. |
| **Monitoring Kinerja** | Synthetic testing berkala (Lighthouse) yang tidak mencerminkan perangkat *low-end* di kondisi riil. | RUM (Real User Monitoring) Telemetry aktif via `next/web-vitals` yang memancarkan metrik riil ke Data Lake/OTel. |

---

### 5. How (Workflow Detail)

Langkah-langkah rekayasa untuk menerapkan optimasi tingkat lanjut:

1. **Konfigurasi Global Image Pipeline**:
   - Definisikan domain aman, format modern (`image/avif`, `image/webp`), batas ukuran perangkat, dan waktu kedaluwarsa caching pada `next.config.js`.
2. **Abstraksi Font Typography Engine**:
   - Inisialisasi font lokal atau Google Fonts menggunakan variabel CSS.
   - Sambungkan variabel ke token Tailwind atau styling system.
3. **Isolasi Pihak Ketiga (Third-Party Offloading)**:
   - Gunakan `next/script` dengan strategi pemuatan bertingkat.
   - Pindahkan skrip analitik non-kritis ke Web Worker guna menjaga kelancaran thread utama.
4. **Instrumentasi Web Vitals Telemetry**:
   - Aktifkan fungsi penangkap metrik bawaan di Next.js (`useReportWebVitals`).
   - Normalisasi metrik, filter deviasi data, dan kirimkan data melalui `navigator.sendBeacon` guna mencegah pembatalan transmisi saat pengguna berpindah halaman.

---

### 6. Analogy & Diagram ASCII

#### A. Analogi Font Fallback Layout Shift
Bayangkan Anda memesan setelan jas khusus (*Custom Font*). Jika penjahit tidak memberi tahu ukuran tubuh Anda ke toko pakaian, Anda mengenakan pakaian pinjaman standar (*Fallback Font*) yang terlalu longgar. Saat setelan jas asli tiba dan Anda berganti pakaian, semua benda di sekitar Anda tersenggol dan bergeser (*Layout Shift*).
`next/font` bertindak seperti penjahit yang memodifikasi pakaian pinjaman (*size-adjust*, *ascent-override*) agar potongannya identik secara milimeter dengan setelan jas pesanan Anda. Saat setelan asli dipakai, tidak ada gerakan atau pergeseran sama sekali di ruangan tersebut.

#### B. Diagram Core Web Vitals Pipeline Execution

```
[ USER INTERACTION ]
        │
        ├── Page Load / Route Change
        │       │
        │       ├── [HTML Streamed via RSC]
        │       │       │
        │       │       ├── Preload Critical Assets (next/font .woff2, LCP Image)
        │       │       └── TTFB Evaluated (< 0.8s)
        │       │
        │       ├── [First Contentful Paint (FCP)]
        │       │       │
        │       │       └── Fallback Font Active with Zero Dimensions Shift
        │       │
        │       ├── [Largest Contentful Paint (LCP)]
        │       │       │
        │       │       └── Priority Image Rendered (AVIF/WebP, sizes defined) (< 1.2s)
        │       │
        │       └── [Hydration & Script Execution]
        │               │
        │               ├── Main Thread Unblocked (Zero-Runtime CSS, No Runtime Parsing)
        │               └── 3rd Party Scripts Pushed to Web Worker
        │
        ▼
[ USER EVENT: Click / Tap / Keydown ]
        │
        ▼
[ INTERACTION TO NEXT PAINT (INP) ]
        │
        ├── 1. Input Delay     (Queue wait time)       ──┐
        ├── 2. Processing Time (Event handler exec)    ──┼── Total < 150ms
        └── 3. Presentation Delay (Compositor update)  ──┘
        │
        ▼
[ RUM TELEMETRY REPORTING ]
        │
        └── PerformanceObserver ──► next/web-vitals ──► sendBeacon() ──► OTel Collector
```

---

### 7. Simple Example & Practical Example

#### Simple Example: Baseline `next/font` & `next/image`

```tsx
// app/simple/page.tsx
import Image from 'next/image';
import { Inter } from 'next/font/google';

const inter = Inter({
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-inter',
});

export default function SimplePage() {
  return (
    <main className={`${inter.variable} font-sans p-8`}>
      <h1 className="text-3xl font-bold tracking-tight">Performa Tinggi Tanpa CLS</h1>
      <div className="relative w-full max-w-md h-64 mt-4 overflow-hidden rounded-xl">
        <Image
          src="/hero-banner.jpg"
          alt="Dashboard Preview"
          fill
          priority
          sizes="(max-width: 768px) 100vw, 448px"
          className="object-cover"
        />
      </div>
    </main>
  );
}
```

#### Practical Example: Production-Grade Asset Pipeline & RUM Collector

##### 1. Konfigurasi Produksi Next.js (`next.config.mjs`)
```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    formats: ['image/avif', 'image/webp'],
    deviceSizes: [640, 750, 828, 1080, 1200, 1920, 2048],
    imageSizes: [16, 32, 48, 64, 96, 128, 256, 384],
    minimumCacheTTL: 31536000, // 1 Tahun
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'cdn.enterprise-commerce.internal',
        port: '',
        pathname: '/assets/**',
      },
    ],
    loader: 'default',
    dangerouslyAllowSVG: false,
    contentSecurityPolicy: "default-src 'self'; script-src 'none'; sandbox;",
  },
  experimental: {
    optimizePackageImports: ['lucide-react', 'date-fns', 'lodash-es'],
  },
};

export default nextConfig;
```

##### 2. Abstraksi Font Terpadu (`app/fonts.ts`)
```typescript
import { Inter, JetBrains_Mono } from 'next/font/google';

export const fontSans = Inter({
  subsets: ['latin'],
  variable: '--font-sans',
  display: 'swap',
  adjustFontFallback: true, // Generate @font-face fallback overrides otomatis
  preload: true,
});

export const fontMono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-mono',
  display: 'swap',
  adjustFontFallback: true,
  preload: false, // Tidak memblokir critical rendering path untuk font mono
});
```

##### 3. Komponen Hero LCP Teroptimasi (`components/hero-media.tsx`)
```tsx
import Image from 'next/image';

interface HeroMediaProps {
  mediaUrl: string;
  lowQualityDataUrl: string; // Base64 Blurhash LQIP
  title: string;
}

export function HeroMedia({ mediaUrl, lowQualityDataUrl, title }: HeroMediaProps) {
  return (
    <section className="relative w-full h-[60vh] min-h-[400px] max-h-[600px] overflow-hidden bg-neutral-900">
      <Image
        src={mediaUrl}
        alt={title}
        fill
        priority // Menghasilkan link rel="preload" as="image" di HTML <head>
        fetchPriority="high"
        placeholder="blur"
        blurDataURL={lowQualityDataUrl}
        sizes="(max-width: 640px) 100vw, (max-width: 1024px) 90vw, 1200px"
        className="object-cover object-center transform-gpu"
        quality={80} // Trade-off optimal antara visual fidelity dan transfer size
      />
      <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent" />
      <div className="absolute bottom-8 left-8 text-white">
        <h1 className="text-4xl font-extrabold tracking-tight sm:text-5xl font-sans">
          {title}
        </h1>
      </div>
    </section>
  );
}
```

##### 4. Custom Real User Monitoring (RUM) Telemetry (`app/web-vitals.tsx`)
```typescript
'use client';

import { useReportWebVitals } from 'next/web-vitals';

interface MetricAttribution {
  id: string;
  name: 'CLS' | 'FCP' | 'FID' | 'INP' | 'LCP' | 'TTFB';
  value: number;
  rating: 'good' | 'needs-improvement' | 'poor';
  delta: number;
  navigationType: string;
}

const RUM_INGESTION_ENDPOINT = '/api/telemetry/vitals';

export function WebVitalsTelemetry(): null {
  useReportWebVitals((metric: MetricAttribution) => {
    // Normalisasi nilai: CLS harus dikalikan 1000 jika engine visual analytics membutuhkan integer
    const payload = {
      metric_id: metric.id,
      metric_name: metric.name,
      metric_value: metric.value,
      metric_rating: metric.rating,
      delta: metric.delta,
      navigation_type: metric.navigationType,
      pathname: window.location.pathname,
      user_agent: navigator.userAgent,
      timestamp: Date.now(),
    };

    const blob = new Blob([JSON.stringify(payload)], {
      type: 'application/json; charset=UTF-8',
    });

    // Kirim menggunakan Beacon API agar tidak dibatalkan saat proses unload/navigasi
    if (navigator.sendBeacon) {
      const delivered = navigator.sendBeacon(RUM_INGESTION_ENDPOINT, blob);
      if (!delivered) {
        // Fallback jika buffer internal Beacon penuh
        fetch(RUM_INGESTION_ENDPOINT, {
          body: blob,
          method: 'POST',
          keepalive: true,
          headers: { 'Content-Type': 'application/json' },
        }).catch(() => {
          // Fail-silent untuk menjaga ketahanan aplikasi
        });
      }
    } else {
      fetch(RUM_INGESTION_ENDPOINT, {
        body: blob,
        method: 'POST',
        keepalive: true,
        headers: { 'Content-Type': 'application/json' },
      }).catch(() => {});
    }
  });

  return null;
}
```

##### 5. Script Orchestrator (`app/layout.tsx`)
```tsx
import type { Metadata } from 'next';
import Script from 'next/script';
import { fontSans, fontMono } from './fonts';
import { WebVitalsTelemetry } from './web-vitals';
import './globals.css';

export const metadata: Metadata = {
  title: 'Enterprise Architecture Next.js',
  description: 'Ultra-fast enterprise-scale storefront',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="id" className={`${fontSans.variable} ${fontMono.variable}`}>
      <body className="font-sans antialiased bg-white text-neutral-900 selection:bg-neutral-900 selection:text-white">
        <WebVitalsTelemetry />
        {children}

        {/* Script pihak ketiga kritis untuk analitik sesi bisnis (afterInteractive) */}
        <Script
          id="enterprise-tag-manager"
          strategy="afterInteractive"
          dangerouslySetInnerHTML={{
            __html: `
              window.dataLayer = window.dataLayer || [];
              function gtag(){dataLayer.push(arguments);}
              gtag('js', new Date());
              gtag('config', 'G-ENTERPRISE01', { send_page_view: false });
            `,
          }}
        />

        {/* Script pihak ketiga berbobot berat (e.g., Widget Customer Support Chat) */}
        <Script
          id="third-party-support"
          src="https://widget.customersupport.internal/sdk.js"
          strategy="lazyOnload"
        />
      </body>
    </html>
  );
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks & Skala Masalah
Sebuah platform E-Commerce Multi-Brand Global melayani 45 juta pengguna aktif bulanan (*Monthly Active Users*). Data audit lapangan menunjukkan:
- **P95 Largest Contentful Paint (LCP)**: 4.8 detik pada perangkat Android level menengah ke bawah.
- **Cumulative Layout Shift (CLS)**: Rata-rata 0.28 (Kategori "Poor").
- **Interaction to Next Paint (INP)**: 480 ms akibat runtime CSS-in-JS (Emotion) yang mengeksekusi komputasi token dinamis di main thread saat pengguna memfilter katalog produk.
- **Dampak Finansial**: Konversi checkout menurun 14% dibandingkan estimasi pasar.

#### Root Cause Analysis (RCA)
1. **LCP Bottleneck**: Gambar produk berukuran asli $2400 \times 2400$ JPEG (rata-rata 2.1 MB) dimuat langsung dari Amazon S3 mentah tanpa *srcset* adaptif dan tanpa header preload.
2. **CLS Bottleneck**: Font eksternal dimuat melalui `@import url('https://fonts.googleapis.com/css2?...')` di file CSS global. Saat web font selesai dimuat, terjadi penataan ulang teks yang menggeser *action banner* dan tombol CTA.
3. **INP Degradation**: Library styling Emotion memvalidasi dan menyuntikkan ribuan string gaya ke dalam `<head>` setiap kali *state* filter kategori berubah, memicu *Long Animation Frame (LoAF)* di atas 300 ms.

#### Arsitektur Solusi & Rekayasa Ulang
1. **Penerapan Custom Image Pipeline**:
   - Memindahkan pemrosesan aset ke edge proxy terdistribusi yang didukung engine `sharp`.
   - Mengimplementasikan `next/image` dengan aturan `sizes` deklaratif ketat dan penyesuaian format AVIF native. Gambar LCP utama ditandai dengan flag `priority`.
2. **Eliminasi CLS dengan `next/font`**:
   - Mengalihkan font Google eksternal ke implementasi `next/font/google` dengan `adjustFontFallback: true`.
   - Hal ini menghasilkan aturan CSS bawaan seperti:
     ```css
     @font-face {
       font-family: '__Inter_Fallback';
       src: local('Arial');
       ascent-override: 90.20%;
       descent-override: 22.48%;
       line-gap-override: 0.00%;
       size-adjust: 107.41%;
     }
     ```
3. **Migrasi Zero-Runtime Styling**:
   - Menghapus ketergantungan runtime Emotion, digantikan secara bertahap dengan Tailwind CSS v3 via static extraction. Seluruh kalkulasi CSS-in-JS runtime dihilangkan.

#### Hasil Produksi (Telemetry P75 Metrics)

```
METRIK WEB VITALS        SEBELUM OPTIMASI     SETELAH OPTIMASI    PENINGKATAN
─────────────────────────────────────────────────────────────────────────────
LCP (P75)                4.8 detik            1.1 detik           - 77.0%
CLS (P75)                0.28                 0.004               - 98.5%
INP (P75)                480 ms               82 ms               - 82.9%
Total JS Bundle Size     740 KB               210 KB              - 71.6%
Conversion Rate Lift     -                    + 11.8%             Revenue Impact
```

---

### 9. Trade-offs

```
                       OPTIMASI ARSITEKTUR
                                │
        ┌───────────────────────┴───────────────────────┐
        ▼                                               ▼
[ Edge Image Processing ]                     [ Dynamic Blurhash LQIP ]
  (+) Zero payload transfer overhead            (+) Eliminasi visual jumping
  (+) AVIF/WebP terkompresi otomatis            (-) Tambahan overhead DB/Payload (30-50B)
  (-) CPU Load melonjak di Node.js server       (-) Kompleksitas pipeline ingest CMS
  (-) Biaya cache storage di cloud CDN
        │                                               │
        └───────────────────────┬───────────────────────┘
                                ▼
                   [ Zero-Runtime CSS Migration ]
                     (+) INP < 100ms (Bebas LoAF)
                     (+) Ukuran runtime JS = 0 KB
                     (-) DX: Kehilangan fleksibilitas 
                         interpolasi props dinamis kompleks
```

1. **CPU & Server Compute vs. Network Bandwidth**:
   - Melakukan kompresi AVIF/WebP menggunakan Sharp secara on-the-fly di server Next.js meningkatkan konsumsi CPU. Pada lonjakan traffic tinggi (*high-concurrency spikes*), server Next.js tanpa reverse proxy CDN dapat mengalami *resource exhaustion*. 
   - **Mitigasi**: Delegasikan pemrosesan gambar ke Image CDN terspesialisasi (seperti Cloudflare Images, Imgix, atau Fastly IO) menggunakan Custom Image Loader Next.js.
2. **Inlining Blurhash Data URLs vs. Payload Size**:
   - Menyertakan data URL base64 berukuran kecil (~100–300 byte) untuk puluhan gambar di halaman katalog meningkatkan ukuran HTML mentah (TTFB meningkat sedikit).
   - **Mitigasi**: Gunakan placeholder berbasis warna solid CSS (`backgroundColor`) untuk daftar produk panjang, dan batasi placeholder blurhash hanya untuk LCP / Hero section.

---

### 10. Common Mistakes & Troubleshooting

#### 1. Kesalahan Fatal: Menggunakan `loading="lazy"` atau Tanpa `priority` pada Elemen LCP
- **Gejala**: Skor LCP berada di angka > 2.5s meskipun aset gambar sudah dikompresi ke AVIF.
- **Penyebab**: Komponen `next/image` menerapkan `loading="lazy"` secara default. Jika hero banner utama di-*lazy load*, browser menunda pengunduhan gambar sampai thread tata letak selesai menghitung posisi gambar di viewport.
- **Solusi**: Tambahkan props `priority` (atau `fetchPriority="high"`) secara eksplisit pada aset hero utama.

#### 2. Layout Shift Akibat Penggunaan `fill` Tanpa Kontainer Pembatas Eksplisit
- **Gejala**: Elemen gambar melompat (*jumping*) ke ukuran layar penuh atau menciut ke 0 piksel.
- **Penyebab**: Menggunakan props `fill` mengharuskan elemen pembungkus (parent) memiliki CSS positioning `relative`, `fixed`, atau `absolute` serta memiliki dimensi tinggi dan lebar terdefinisi.
- **Solusi**:
  ```tsx
  {/* SALAH */}
  <div>
    <Image src="/img.jpg" fill alt="Product" />
  </div>

  {/* BENAR */}
  <div className="relative w-full aspect-video">
    <Image src="/img.jpg" fill sizes="100vw" className="object-cover" alt="Product" />
  </div>
  ```

#### 3. Hydration Mismatch pada `next/font`
- **Gejala**: Warning di konsol browser: *Text content did not match. Server: "..." Client: "..."* atau *class name mismatch*.
- **Penyebab**: Menginstansiasi fungsi font di dalam cakupan *render cycle* komponen React alih-alih di level modul (*module scope*).
- **Solusi**: Selalu inisialisasi instance `next/font` di luar fungsi komponen atau di file terpisah (`app/fonts.ts`).

#### 4. INP Membengkak Akibat Event Handler Non-Hydrated
- **Gejala**: Pengguna mengeklik menu hamburger atau tombol filter saat halaman baru terbuka, namun browser tidak merespons selama > 200 ms.
- **Penyebab**: Browser telah merender HTML visual (SSR), tetapi bundel JavaScript hidrasi untuk komponen interaktif tersebut masih diunduh atau dieksekusi secara masif di main thread.
- **Solusi**: Terapkan *code-splitting* dinamis via `next/dynamic` dengan SSR aktif untuk komponen non-kritis dan pecah eksekusi tugas menggunakan `scheduler.yield()` atau `requestIdleCallback()`.

---

### 11. Best Practices (Production Checklist)

- [ ] **LCP Asset Preloading**: Semua gambar yang berada di area *above-the-fold* wajib memiliki atribut `priority={true}`.
- [ ] **Sizes Attribute Declaration**: Seluruh tag `Image` dengan atribut `fill` atau multi-resolusi harus memiliki atribut `sizes` yang akurat sesuai CSS media query untuk menghindari browser mengunduh viewport desktop pada layar ponsel.
- [ ] **Zero-Runtime CSS**: Tidak ada runtime styling engine (Emotion, Styled Components) di App Router; gunakan Tailwind CSS, Vanilla Extract, atau CSS Modules.
- [ ] **Local Self-Hosted Fonts**: Seluruh font Google atau kustom wajib dikonfigurasi melalui `next/font` dengan `adjustFontFallback: true` untuk mengeliminasi FOIT/FOUT dan CLS.
- [ ] **Third-Party Triage**: Skrip analitik non-kritis dikonfigurasi dengan strategi `afterInteractive` atau `lazyOnload`. Skrip yang membebani CPU dipindahkan ke worker menggunakan Partytown.
- [ ] **Telemetry Ingestion**: Telemetri metrik riil (RUM) dikonfigurasi menggunakan Beacon API (`sendBeacon`) atau fetch `keepalive: true` via `useReportWebVitals`.
- [ ] **Format Negotiation**: Format gambar default di `next.config.js` memprioritaskan `['image/avif', 'image/webp']`.
- [ ] **HTTP Caching**: Cache aset statis pada layer CDN dikonfigurasi dengan `Cache-Control: public, max-age=31536000, immutable`.

---

### 12. Hands-on Practice

Buatlah implementasi lengkap di dalam direktori `hands-on/m02/` dengan struktur file sebagai berikut:

```
hands-on/m02/
├── package.json
├── tsconfig.json
├── next.config.mjs
├── tailwind.config.ts
├── postcss.config.mjs
├── app/
│   ├── layout.tsx
│   ├── page.tsx
│   ├── fonts.ts
│   ├── web-vitals.tsx
│   └── api/
│       └── telemetry/
│           └── vitals/
│               └── route.ts
```

#### File Implementation

##### 1. `package.json`
```json
{
  "name": "hands-on-nextjs-assets-vitals",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start"
  },
  "dependencies": {
    "next": "^14.2.0",
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "sharp": "^0.33.3"
  },
  "devDependencies": {
    "@types/node": "^20.12.0",
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "autoprefixer": "^10.4.19",
    "postcss": "^8.4.38",
    "tailwindcss": "^3.4.3",
    "typescript": "^5.4.5"
  }
}
```

##### 2. `next.config.mjs`
```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    formats: ['image/avif', 'image/webp'],
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'images.unsplash.com',
      },
    ],
  },
};

export default nextConfig;
```

##### 3. `app/fonts.ts`
```typescript
import { Inter, Space_Grotesk } from 'next/font/google';

export const fontSans = Inter({
  subsets: ['latin'],
  variable: '--font-sans',
  display: 'swap',
  adjustFontFallback: true,
});

export const fontDisplay = Space_Grotesk({
  subsets: ['latin'],
  variable: '--font-display',
  display: 'swap',
  adjustFontFallback: true,
});
```

##### 4. `app/web-vitals.tsx`
```typescript
'use client';

import { useReportWebVitals } from 'next/web-vitals';

export function WebVitalsReporter() {
  useReportWebVitals((metric) => {
    const payload = JSON.stringify({
      id: metric.id,
      name: metric.name,
      value: metric.value,
      rating: metric.rating,
      delta: metric.delta,
      timestamp: Date.now(),
    });

    const url = '/api/telemetry/vitals';

    if (navigator.sendBeacon) {
      navigator.sendBeacon(url, payload);
    } else {
      fetch(url, {
        method: 'POST',
        body: payload,
        headers: { 'Content-Type': 'application/json' },
        keepalive: true,
      });
    }
  });

  return null;
}
```

##### 5. `app/api/telemetry/vitals/route.ts`
```typescript
import { NextRequest, NextResponse } from 'next/server';

export async function POST(request: NextRequest) {
  try {
    const data = await request.json();
    
    // Structured Logging untuk agregasi Observabilitas (misal: DataDog, Grafana)
    console.log('[PERFORMANCE_TELEMETRY]', JSON.stringify({
      timestamp: new Date().toISOString(),
      ...data,
    }));

    return NextResponse.json({ status: 'ok' }, { status: 200 });
  } catch (error) {
    return NextResponse.json(
      { error: 'Invalid payload format' },
      { status: 400 }
    );
  }
}
```

##### 6. `app/layout.tsx`
```tsx
import type { Metadata } from 'next';
import { fontSans, fontDisplay } from './fonts';
import { WebVitalsReporter } from './web-vitals';
import './globals.css';

export const metadata: Metadata = {
  title: 'Next.js Ultra-Performance Architecture',
  description: 'Enterprise demo for zero-runtime assets and vitals optimization',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${fontSans.variable} ${fontDisplay.variable}`}>
      <body className="font-sans bg-neutral-950 text-neutral-100 antialiased min-h-screen">
        <WebVitalsReporter />
        {children}
      </body>
    </html>
  );
}
```

##### 7. `app/page.tsx`
```tsx
import Image from 'next/image';

export default function PerformanceShowcase() {
  return (
    <main className="max-w-5xl mx-auto px-6 py-12">
      <header className="mb-12">
        <h1 className="font-display text-5xl font-black tracking-tight text-white mb-4">
          Core Web Vitals Engine
        </h1>
        <p className="text-neutral-400 text-lg max-w-2xl font-sans">
          Arsitektur halaman ini dirancang dengan zero-CLS layout constraints, font metric adjustments, 
          dan pipeline gambar adaptif AVIF/WebP.
        </p>
      </header>

      <section className="relative w-full aspect-[21/9] rounded-2xl overflow-hidden bg-neutral-900 border border-neutral-800 shadow-2xl">
        <Image
          src="https://images.unsplash.com/photo-1579546929518-9e396f3cc809"
          alt="Abstract Gradient Canvas"
          fill
          priority
          sizes="(max-width: 1280px) 100vw, 1280px"
          quality={85}
          className="object-cover"
        />
        <div className="absolute inset-0 bg-neutral-950/20 backdrop-blur-[2px]" />
        <div className="absolute bottom-6 left-6 right-6 flex items-center justify-between text-xs font-mono text-neutral-300 bg-neutral-950/70 p-4 rounded-xl border border-neutral-700/50 backdrop-blur-md">
          <span>LCP Candidate: Priority Fetch Active</span>
          <span>Format: Content-Negotiated AVIF/WebP</span>
          <span>Target INP: &le; 150ms</span>
        </div>
      </section>

      <section className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-12">
        {[1, 2, 3].map((item) => (
          <div key={item} className="p-6 rounded-xl bg-neutral-900/60 border border-neutral-800">
            <h3 className="font-display text-xl font-bold mb-2">Metric Spec 0{item}</h3>
            <p className="text-neutral-400 text-sm font-sans">
              Zero layout shifts dijamin melalui kalkulasi metrik font secara build-time menggunakan Next.js font engine.
            </p>
          </div>
        ))}
      </section>
    </main>
  );
}
```

---

### 13. Exercise

#### Level Easy
Ubah implementasi `next/image` pada sebuah galeri kartu produk statis yang saat ini menggunakan tag `<img>` konvensional menjadi `next/image`. Pastikan dimensi diatur sedemikian rupa sehingga tidak memicu CLS saat gambar selesai diunduh.

#### Level Medium
Buat sebuah *Custom Image Loader* (`imageLoader.ts`) yang memformat URL gambar Next.js agar dialihkan ke service proxy pihak ketiga (misalnya Cloudflare Images atau Cloudinary) dengan parameter transformasi dinamis: lebar (`w`), kualitas (`q`), dan format otomatis (`f=auto`). Hubungkan loader ini ke komponen `next/image`.

#### Level Hard
Rancang dan bangun sebuah custom React Hook `useInteractionTracking` yang menggunakan interface `PerformanceObserver` untuk mendeteksi *Long Tasks* (> 50ms) dan mencatat durasi INP secara manual. Jika sebuah interaksi UI memicu delay > 150ms, tampilkan log peringatan terstruktur ke konsol lengkap dengan *target DOM element* pemicu interaksi tersebut.

---

### 14. Challenge

#### Skenario Kasus Kompleks: High-Throughput Live News Portal
Anda adalah Lead Performance Architect untuk portal berita global terkemuka. Selama peristiwa pemilihan umum, traffic melonjak hingga 120.000 request per detik (RPS). Tim infrastruktur mendeteksi bahwa CPU server Next.js mengalami *throttling* hingga 100% akibat tingginya beban Sharp yang mengompresi gambar hero yang sama secara on-the-fly untuk ribuan variasi resolusi gawai.

Di saat bersamaan, tim redaksi memasang 6 script embed live-tweet dan analitik interaktif yang menyebabkan nilai INP membengkak ke 650 ms dan skor Lighthouse mobile anjlok ke 28.

#### Tugas Rekayasa
1. **Rancang Arsitektur Offloading Gambar**:
   - Susun desain sistem arsitektur untuk memotong beban proses Sharp dari origin Next.js ke Edge Storage/CDN Caching layer dengan mekanisme *stale-while-revalidate* yang aman.
   - Buat file konfigurasi Next.js Loader kustom untuk menerapkan skema ini.
2. **Isolasi Script Eksekusi Ekstrem**:
   - Terapkan strategi arsitektur di mana script embed pihak ketiga tidak memiliki akses langsung ke Main UI Thread browser.
   - Dokumentasikan trade-off arsitektur, batasan keamanan (CSP), dan skema mitigasi performa yang Anda ambil.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic (5 Soal)

1. **Bagaimana komponen `next/image` menentukan format gambar mana yang harus dikirimkan ke browser antara AVIF, WebP, atau JPEG asli?**
   - *Jawaban*: Komponen Next.js Image Optimization API membaca HTTP Header `Accept` yang dikirimkan oleh browser pada saat HTTP request. Jika browser mencantumkan `image/avif`, server Next.js (via engine Sharp) akan mengonversinya ke AVIF jika format tersebut diizinkan pada `next.config.js`. Jika tidak, server mengecek dukungan `image/webp`.

2. **Mengapa penambahan atribut `priority` pada komponen `next/image` di elemen hero banner sangat penting untuk optimasi LCP?**
   - *Jawaban*: Atribut `priority` menonaktifkan sistem *lazy loading* bawaan (`loading="lazy"`) dan secara otomatis menginjeksikan tag `<link rel="preload" as="image">` ke dalam dokumen HTML `<head>`. Hal ini menginstruksikan browser untuk segera mengunduh gambar tersebut sebelum parser menemukan tag `<img>` di dalam markup DOM.

3. **Apa perbedaan fungsional utama antara `adjustFontFallback: true` pada `next/font` dibandingkan pendekatan memuat font eksternal melalui CSS `@import`?**
   - *Jawaban*: `adjustFontFallback: true` secara otomatis menghitung dan menghasilkan deskriptor CSS `@font-face` cadangan (seperti `size-adjust`, `ascent-override`, dan `descent-override`) pada saat kompilasi (*build-time*). Hal ini membuat font sistem bawaan memiliki dimensi geometris yang sama persis dengan font target, menghilangkan pergeseran tata letak (CLS = 0) saat font asli selesai dimuat.

4. **Kapan strategi pemuatan script `lazyOnload` pada `next/script` paling tepat untuk digunakan?**
   - *Jawaban*: `lazyOnload` tepat digunakan untuk skrip pihak ketiga dengan prioritas rendah yang tidak berpengaruh pada fungsionalitas inti visual atau bisnis aplikasi, seperti widget customer support chat, SDK survei feedback, atau analitik sekunder. Skrip ini dieksekusi saat browser berada dalam status *idle* (`requestIdleCallback`).

5. **Mengapa library styling CSS-in-JS dengan komputasi runtime (seperti Styled Components atau Emotion tradisional) dapat merusak metrik Interaction to Next Paint (INP)?**
   - *Jawaban*: Library tersebut mengevaluasi ekspresi gaya pada main thread JavaScript setiap kali komponen di-render atau props berubah, lalu menyuntikkan rule CSS baru ke dalam DOM runtime. Komputasi string CSS dan *style recalculation* ini memblokir main thread, sehingga penanganan event pengguna mengalami penundaan (Input Delay tinggi).

---

#### B. Pertanyaan Intermediate (5 Soal)

1. **Jelaskan perbedaan mendasar antara metrik FID (First Input Delay) dan INP (Interaction to Next Paint), serta mengapa INP jauh lebih ketat dan representatif!**
   - *Jawaban*: FID hanya mengukur waktu tunggu (*delay*) dari interaksi **pertama** pengguna hingga thread utama browser mulai memproses event handler tersebut; FID tidak mengukur durasi pemrosesan handler atau waktu yang dibutuhkan browser untuk memperbarui frame visual di layar. Sebaliknya, INP mengukur **seluruh interaksi** (klik, tap, keydown) sepanjang masa hidup halaman, mencakup: Input Delay + Processing Time + Presentation Delay (hingga piksel frame baru digambar di layar), serta mengambil nilai P98/terburuk dari interaksi tersebut.

2. **Jika sebuah gambar `next/image` menggunakan props `fill`, apa yang terjadi jika elemen pembungkus langsung (parent container) memiliki CSS `position: static`?**
   - *Jawaban*: Komponen `next/image` dengan `fill` menerapkan atribut CSS `position: absolute; inset: 0; width: 100%; height: 100%`. Jika parent container memiliki `position: static`, batas referensi ukuran gambar melompat ke elemen leluhur terdekat yang memiliki positioning non-static (atau ke viewport `<html>`). Hal ini merusak layout halaman dan memicu nilai CLS yang besar.

3. **Bagaimana mekanisme `navigator.sendBeacon` pada instrumentasi Web Vitals mengatasi masalah hilangnya data (*data loss*) dibandingkan pemanggilan `fetch` biasa saat pengguna menutup tab?**
   - *Jawaban*: Pemanggilan `fetch` standar sering kali dibatalkan (diberhentikan paksa) oleh browser ketika proses navigasi halaman berpindah atau tab ditutup (*unload/pagehide*). `navigator.sendBeacon` menjadwalkan pengiriman data di layer network browser di luar siklus hidup dokumen saat ini, memastikan payload tetap terkirim ke server secara asinkron tanpa memblokir penutupan thread halaman.

4. **Bagaimana cara kerja optimasi otomatis `experimental.optimizePackageImports` di Next.js dalam mereduksi waktu eksekusi kode (dan meningkatkan INP)?**
   - *Jawaban*: Fitur ini secara otomatis mentransformasi *barrel file import* (seperti `import { Check } from 'lucide-react'`) menjadi *direct import* ke modul spesifiknya (seperti `import Check from 'lucide-react/dist/esm/icons/check.js'`) saat kompilasi. Hal ini mencegah bundler memproses dan mengevaluasi ribuan modul lain di dalam barrel file, memangkas ukuran AST, dan membebaskan memori serta main thread browser saat hidrasi.

5. **Apa dampak performa dari pengaturan `sizes` yang salah pada komponen `next/image` (misalnya diset permanen ke `100vw` padahal kartu produk hanya berukuran lebar 300px pada desktop)?**
   - *Jawaban*: Browser menggunakan atribut `sizes` untuk memilih URL resolusi terbaik dari `srcset` sebelum layout dihitung. Jika dideklarasikan `100vw` pada monitor 4K desktop, browser akan memilih file gambar beresolusi 3840px dari `srcset`, bukan varian 384px. Hal ini membuang bandwidth secara signifikan, memperlambat proses download gambar, mengonsumsi memori GPU/RAM berlebih, dan memperburuk skor LCP.

---

#### C. Skenario Kasus Produksi (3 Skenario)

##### Skenario 1: Layout Shift Misterius pada Web Font Kustom
- **Kondisi**: Sebuah portal fintech menggunakan font korporat lokal (.woff2). Walaupun font telah dimuat via `next/font/local` dengan `display: 'swap'`, tim QA melaporkan bahwa angka CLS pada halaman pembayaran tetap tinggi (0.15) setiap kali font selesai diunduh.
- **Analisis & Solusi**: Nilai `display: 'swap'` tanpa penyesuaian fallback tetap memicu reflow jika karakter font target dan font sistem memiliki metrik glif (tinggi x-height, lebar rata-rata huruf) yang berbeda jauh. Pengembang harus menambahkan konfigurasi metrik penyesuaian atau membiarkan Next.js menghitungnya melalui properti `declarations` atau `adjustFontFallback: 'Arial'` (atau `'Times New Roman'`). Pastikan deklarasi ukuran font tidak dibungkus dalam tag yang memiliki styling *dynamic line-height* yang bergantung pada eksekusi runtime JavaScript.

##### Skenario 2: Lonjakan INP Akibat Chat Widget Pihak Ketiga
- **Kondisi**: Hasil RUM menunjukkan bahwa 20% pengguna di perangkat mobile mengalami INP > 400ms saat berinteraksi dengan field input formulir checkout. Profiling Chrome DevTools mengungkap bahwa sebuah script live-chat pihak ketiga terus menjalankan event listener `pointermove` dan evaluasi loop WebSocket di main thread.
- **Analisis & Solusi**: Skrip pihak ketiga diubah pemuatannya menggunakan `next/script` dengan strategi `lazyOnload`. Jika script masih memonopoli main thread saat sudah termuat, alihkan script tersebut untuk berjalan di dalam Web Worker menggunakan integrasi **Partytown** via Next.js (`strategy="worker"`). Ini memisahkan DOM sandbox script dari UI main thread, sehingga input pengguna pada form checkout dapat langsung dirender tanpa interupsi.

##### Skenario 3: Overload Server Next.js Akibat Infinite Dynamic Image Transformations
- **Kondisi**: Aplikasi direktori otomotif mengalami lonjakan penggunaan CPU hingga 100% pada instance kontainer Kubernetes Next.js. Investigasi log menemukan jutaan request masuk dengan variasi query string lebar gambar acak: `/_next/image?url=...&w=123&q=75`, `&w=124`, `&w=125` yang sengaja dikirim oleh scraper kompetitor.
- **Analisis & Solusi**: Engine `next/image` Next.js secara default hanya mengizinkan transformasi gambar sesuai dengan array nilai yang telah ditentukan di `imageSizes` dan `deviceSizes` pada `next.config.js`. Jika penyerang memanfaatkan celah proxy kustom atau jika Next.js dikonfigurasi secara salah tanpa batas ukuran, Sharp akan terus memproses gambar secara paksa. Solusinya:
  1. Kunci konfigurasi `deviceSizes` dan `imageSizes` hanya pada rentang standar enterprise.
  2. Tempatkan CDN caching layer (seperti Cloudflare Enterprise atau AWS CloudFront) di depan origin dengan aturan *Request Normalization*, sehingga query string `w` yang tidak valid langsung ditolak di edge (Return 400/403) sebelum mencapai server Node.js.

---

### 16. Summary

1. **Asset Pipeline Modern**: Optimasi aset pada level enterprise berfokus pada automasi kompilasi dan kompresi di layer edge/build alih-alih mengandalkan manipulasi DOM di sisi browser klien.
2. **Eliminasi CLS Holistik**: Penggunaan `next/font` secara komprehensif mengeliminasi degradasi CLS dengan menyelaraskan metrik fallback font secara otomatis di level CSS parser.
3. **Optimasi Deterministik LCP**: LCP adalah metrik network-to-paint. Kombinasi format AVIF modern, atribut `priority`, pemetaan `sizes` yang akurat, serta integrasi CDN caching menghasilkan waktu LCP di bawah ambang batas optimal (< 1.2 detik).
4. **Dominasi Zero-Runtime Architecture**: Menghilangkan runtime styling dan memindahkan evaluasi skrip pihak ketiga keluar dari main thread adalah kunci utama mempertahankan skor INP < 150 ms pada interaksi aplikasi berskala masif.
5. **Data Driven Telemetry**: Metrik performa sintetis laboratorium (Lighthouse) tidak mencerminkan kenyataan pengguna riil. Implementasi Real User Monitoring (RUM) menggunakan `useReportWebVitals` dan `sendBeacon` wajib diintegrasikan sebagai fondasi observabilitas berkelanjutan aplikasi enterprise.