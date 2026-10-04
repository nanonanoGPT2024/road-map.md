# BAB 10: Capstone Project - Enterprise Programmatic SEO Platform
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
- Merancang dan mengimplementasikan arsitektur *Programmatic SEO* (pSEO) terdistribusi berskala jutaan halaman dengan latensi edge $< 50\text{ ms}$ (p95).
- Membangun pipeline orkestrasi konten berbasis AI & Graph Data Modeling yang mengeliminasi risiko *duplicate content*, *thin content*, dan penalti Google Panda/Helpful Content System (HCS).
- Mengonfigurasi strategi rendering hibrida (*Incremental Static Regeneration* / ISR, *Edge Dynamic Rendering*, dan *Stale-While-Revalidate*) terintegrasi dengan CDN cache tag purging.
- Mengimplementasikan sistem automasi penanganan *Crawl Budget*, sitemap sharding, logging audit bot crawler (Googlebot, Bingbot, LLM Scrapers), serta protokol indexing real-time (*IndexNow API* dan *Google Search Console URL Inspection API*).
- Menghubungkan metrik performa teknis (Core Web Vitals: LCP, CLS, INP) langsung dengan pipeline CI/CD automasi validasi SEO schema (`Schema.org` JSON-LD).

---

### 2. Prerequisite
- **Distributed Systems & Networking**: Pemahaman mendalam tentang HTTP/2, HTTP/3, CDN edge compute (Cloudflare Workers, Fastly VCL), DNS routing, dan caching headers (`Surrogate-Control`, `stale-while-revalidate`).
- **Modern Web Architecture**: Next.js (App Router), Node.js/TypeScript tingkat lanjut, serta database engine berbasis relational (PostgreSQL) dan vector/search (Elasticsearch atau OpenSearch).
- **SEO Fondasional & Protokol Web**: Pemahaman RFC sitemap XML, robots.txt directives, canonical link tag inheritance, Core Web Vitals (CWV), serta semantic HTML5.
- **Data Engineering Dasar**: Message broker (Apache Kafka atau RabbitMQ), streaming data, serta Redis key eviction strategies.

---

### 3. Concept & Internal Architecture (Mendalam)

Membangun platform Programmatic SEO (pSEO) tingkat enterprise bukan sekadar membuat ribuan halaman berbasis *string template concatenation*. Mesin pencari modern menerapkan sistem klasifikasi konten berbasis Natural Language Processing (NLP) seperti MUM, RankBrain, dan SpamBrain yang mengevaluasi nilai informasi unik (*Information Gain Score*).

```
                      +------------------------------------------+
                      |         Data & Knowledge Layer           |
                      | (Knowledge Graph, DB Relasional, Vectors)|
                      +--------------------+---------------------+
                                           |
                                           v
+------------------+         +-------------------------------+
| Raw Intent Specs | ------> | AI Content Enrichment Engine  |
|  (Taxonomy/Keys) |         | (Deduplikasi, Semantic Fill)  |
+------------------+         +---------------+---------------+
                                             |
                                             v
                             +-------------------------------+
                             | Event Bus (Kafka / NATS)      |
                             +---------------+---------------+
                                             |
                   +-------------------------+-------------------------+
                   |                                                   |
                   v                                                   v
    +-------------------------------+                   +-------------------------------+
    | ISR Edge Prerender Workers    |                   | Dynamic Sitemap Generator     |
    | (HTML Generation + JSON-LD)   |                   | (Shard XML, IndexNow, ETag)   |
    +---------------+---------------+                   +---------------+---------------+
                    |                                                   |
                    +--------------------+------------------------------+
                                         |
                                         v
                         +-------------------------------+
                         | Multi-Tier Cache Layer        |
                         | (L1: Edge CDN, L2: Redis SV)  |
                         +---------------+---------------+
                                         |
                       +-----------------+-----------------+
                       |                                   |
                       v                                   v
             [ Googlebot / Crawlers ]            [ Human End-Users ]
```

#### Komponen Kunci Arsitektur Produksi:
1. **Semantic Knowledge Graph Layer**: 
   Alih-alih menyimpan teks mentah, data entitas disimpan dalam struktur graf relasional. Misalnya, jika halaman menargetkan `Top Rust Consulting Agencies in [City]`, graf menyimpan simpul *City*, *Agency*, *Skillsets*, *Cost Indexes*, dan *Market Reviews*.
2. **AI Enrichment Pipeline & Information Gain Engine**:
   Worker asynchronous membaca intent target, menghitung kelayakan *search volume*, kemudian memvalidasi bahwa data unik mencakup minimal $\ge 40\%$ dari total token konten halaman. Jika ambang batas tidak tercapai, pipeline memblokir pembuatan halaman secara otomatis guna mencegah penalti *soft-404*.
3. **Hybrid Edge-SSR Rendering Matrix**:
   - **Tier-1 Pages (High Search Volume & Critical Keywords)**: Pre-rendered via ISR saat build/deploy time.
   - **Tier-2 Pages (Long-tail, low frequency queries)**: On-demand dynamic rendering via Edge Workers dengan *Stale-While-Revalidate* (SWR) cache policy selama 7-30 hari.
4. **Log Ingestion & Crawl Intelligence Worker**:
   Log server HTTP/CDN di-streaming real-time via vector stream untuk mendeteksi:
   - Pola crawl Googlebot (Smartphone vs Desktop bot).
   - *Crawl Waste*: Bot mengakses URL yang tidak diindeks atau menerima status 3xx berulang.
   - *Render Stall*: Waktu respons TTFB crawler $> 200\text{ ms}$.

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional (CMS / Basic pSEO) | Enterprise Autonomous pSEO Platform |
| :--- | :--- | :--- |
| **Generasi Konten** | Template statis digabung teks CSV mentah (*Mad-libs style*). | Knowledge graph semantic ingestion, kalkulasi dynamic metrics, AI-driven synthesis. |
| **Manajemen Crawl Budget** | Bergantung pada Google crawling natural tanpa panduan real-time. | *Dynamic XML Sharding*, real-time priority update via IndexNow, bot-specific routing. |
| **Kualitas Schema** | Skema generic (WebPage / Article) seragam di semua varian. | Entity-specific, fully-nested Schema.org (`Dataset`, `JobPosting`, `LocalBusiness`, dll.). |
| **Validasi Thin Content** | Dideteksi pasif setelah menerima Google Search Console Manual Penalty. | Pre-render automated gating test (Token Diversity Index & Information Gain threshold). |
| **Cache Invalidation** | `Cache-Control: no-cache` atau invalidasi manual massal per deploy. | Granular Tag-based Cache Eviction (`x-cache-tags`) via webhook database update. |

---

### 5. How (Workflow Detail)

```
[Target Keyword Discovery]
           │
           ▼
[Entity Extraction & Deduplication Engine]
           │
           ├─(Duplicate Index > 0.85) ──► [Drop / Merge into Parent Entity]
           │
           ▼ (Unik)
[AI Content Enrichment Pipeline (Llama 3 / Claude 3.5)]
           │
           ▼
[Semantic Verification & Validation Guard]
           │  ├─ Check 1: Information Gain Score >= 0.40
           │  ├─ Check 2: Schema.org Validation === Pass
           │  └─ Check 3: Canonical Link & Noindex Flag
           │
           ▼ (Valid)
[Publish Event to Kafka/Queue]
           │
           ├───────────────────────────────┐
           ▼                               ▼
[Edge Renderer (Fastly/CF)]     [XML Sitemap Sharder Engine]
           │                               │
           ▼                               ▼
[CDN Cache Warming & SWR]       [Ping IndexNow / GSC API]
```

#### Tahapan Implementasi:
1. **Targeting & Taxonomy Expansion**: Ekstraksi token kata kunci target (misal: industri + wilayah geospasial) melalui penggabungan basis data referensial internal.
2. **Content Generation with Information Gain Assurance**:
   - Menggunakan LLM terorchestasi (bukan pure raw prompt) untuk menghasilkan konten terstruktur.
   - Setiap halaman harus memuat metrik real-time independen (misal: *salary median*, agregasi sentimen lokal) yang tidak dimiliki kompetitor.
3. **Pre-Publish Gatekeeping Check**:
   - Menghitung cosine similarity terhadap $N$ halaman terdekat dalam klaster yang sama.
   - Jika kemiripan semantik melampaui $85\%$, halaman ditolak untuk dipublikasikan atau di-*noindex*.
4. **Edge Delivery & CDN Propagation**:
   - Build static HTML snapshot.
   - Inject structured headers: `Link: <canonical_url>; rel="canonical"`.
   - Simpan entri di edge KV cache dan broadcast perubahan ke Google Indexing Engine & IndexNow.

---

### 6. Analogy & Diagram ASCII

Bayangkan sistem Programmatic SEO seperti jaringan percetakan koran global terdesentralisasi:

```
[ Kantor Berita Pusat / DB ] 
          │
          ├─ Informasi Mentah: Angka inflasi, cuaca, data properti
          ▼
[ Redaktur Khusus / AI Pipeline ]
          │
          ├─ Menyusun artikel unik untuk 50.000 kecamatan berbeda
          ▼
[ Quality Control Gatekeeper ]
          │
          ├─ Menolak naskah jika 2 kecamatan bersebelahan isinya nyaris identik
          ▼
[ Percetakan Lokal di Tiap Kota / Edge Node ]
          │
          ├─ Cetak edisi lokal hanya saat ada permintaan pembaca
          ▼
[ Pengantar Koran Ekspres / Sitemap & IndexNow ]
          │
          └─ Memberitahu Googlebot tepat ketika koran baru saja keluar dari mesin
```

Tanpa redaktur cerdas dan QC, percetakan hanya memfotokopi koran yang sama lalu mengganti nama kotanya saja. Akibatnya, agen pengawas pasar (Google SpamBrain) akan menyegel dan menyita seluruh jaringan penerbitan tersebut.

---

### 7. Simple Example & Practical Example (Kode Standar Industri)

#### A. Simple Example: Dynamic JSON-LD Builder & Canonical Injection (TypeScript)

Implementasi utility function untuk mengonstruksi *Product Dataset Schema* terstandarisasi bebas dari anomali format:

```typescript
// lib/seo/schema-builder.ts
export interface ProgrammaticPageMeta {
  title: string;
  description: string;
  slug: string;
  baseUrl: string;
  updatedAt: string;
  entityData: {
    name: string;
    category: string;
    city: string;
    metricValue: number;
  };
}

export function buildPageSEO(meta: ProgrammaticPageMeta) {
  const canonicalUrl = `${meta.baseUrl.replace(/\/$/, '')}/${meta.slug.replace(/^\//, '')}`;

  const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'Dataset',
    name: meta.title,
    description: meta.description,
    keywords: [meta.entityData.category, meta.entityData.city, 'Market Intelligence'],
    license: 'https://creativecommons.org/licenses/by/4.0/',
    creator: {
      '@type': 'Organization',
      name: 'Enterprise Data Platform',
      url: meta.baseUrl,
    },
    temporalCoverage: `${new Date().getFullYear()}`,
    spatialCoverage: meta.entityData.city,
    variableMeasured: {
      '@type': 'PropertyValue',
      name: 'Benchmark Index',
      value: meta.entityData.metricValue,
    },
  };

  return {
    canonicalUrl,
    jsonLdScript: JSON.stringify(jsonLd),
  };
}
```

#### B. Practical Example: Enterprise Edge Invalidation & IndexNow Dispatcher (Node.js/Next.js Edge Runtime)

Skrip pipeline produksi untuk menangani mutasi data, memicu edge-cache purge, dan mengirimkan payload *IndexNow* secara instan ke Bing dan Yandex:

```typescript
// services/seo-dispatcher.service.ts
import { z } from 'zod';

const MutationPayloadSchema = z.object({
  entityId: z.string().uuid(),
  slug: z.string(),
  priority: z.enum(['HIGH', 'MEDIUM', 'LOW']),
  action: z.enum(['CREATE', 'UPDATE', 'DELETE']),
});

export type MutationPayload = z.infer<typeof MutationPayloadSchema>;

export class EnterpriseSEODispatcher {
  private readonly baseUrl: string;
  private readonly indexNowKey: string;
  private readonly cdnPurgeApiUrl: string;
  private readonly cdnApiKey: string;

  constructor() {
    this.baseUrl = process.env.PUBLIC_SITE_URL || 'https://www.example.com';
    this.indexNowKey = process.env.INDEXNOW_KEY || '';
    this.cdnPurgeApiUrl = process.env.CDN_PURGE_API_URL || '';
    this.cdnApiKey = process.env.CDN_API_KEY || '';

    if (!this.indexNowKey || !this.cdnApiKey) {
      throw new Error('Fatal: Credentials for Edge Cache Purge & IndexNow are missing.');
    }
  }

  /**
   * Menangani invalidasi cache CDN selektif via Cache-Tags
   */
  async purgeCdnCache(cacheTag: string): Promise<boolean> {
    try {
      const response = await fetch(this.cdnPurgeApiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.cdnApiKey}`,
        },
        body: JSON.stringify({ tags: [cacheTag] }),
      });

      if (!response.ok) {
        throw new Error(`CDN purge failed with HTTP status: ${response.status}`);
      }

      return true;
    } catch (error) {
      console.error(`[CRITICAL] Purge failed for tag: ${cacheTag}`, error);
      return false;
    }
  }

  /**
   * Mengirim sinyal IndexNow untuk percepatan indeks mesin pencari
   */
  async submitIndexNow(urls: string[]): Promise<boolean> {
    const payload = {
      host: new URL(this.baseUrl).hostname,
      key: this.indexNowKey,
      keyLocation: `${this.baseUrl}/${this.indexNowKey}.txt`,
      urlList: urls,
    };

    try {
      const response = await fetch('https://api.indexnow.org/IndexNow', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json; charset=utf-8',
        },
        body: JSON.stringify(payload),
      });

      return response.status === 200 || response.status === 202;
    } catch (error) {
      console.error('[CRITICAL] IndexNow dispatching encountered an unhandled exception:', error);
      return false;
    }
  }

  /**
   * Orchestrator utama pemrosesan mutasi data SEO
   */
  async processEntityMutation(rawPayload: unknown): Promise<{ success: boolean; url: string }> {
    const data = MutationPayloadSchema.parse(rawPayload);
    const targetUrl = `${this.baseUrl}/${data.slug}`;
    const cacheTag = `entity-${data.entityId}`;

    // 1. Eksekusi Invalidation Cache Tag di Edge CDN
    const purgeSuccess = await this.purgeCdnCache(cacheTag);

    // 2. Submit URL jika berupa penambahan baru atau update prioritas tinggi
    let indexNowSuccess = true;
    if (data.action !== 'DELETE' && data.priority !== 'LOW') {
      indexNowSuccess = await this.submitIndexNow([targetUrl]);
    }

    return {
      success: purgeSuccess && indexNowSuccess,
      url: targetUrl,
    };
  }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: "PropTech Global" - 28 Juta Halaman Informasi Real Estate Terlokalisasi
- **Kondisi Awal**: 
  Perusahaan memiliki 28 juta halaman statistik sewa properti per sub-distrik di 80 negara. Waktu crawling Googlebot membutuhkan waktu 4 bulan untuk menyelesaikan $10\%$ sitemap. Terjadi de-indeksasi massal akibat $70\%$ halaman dinilai sebagai *thin content* (hanya tabel angka tanpa konteks analitik unik).
- **Arsitektur Solusi**:
  1. **Dynamic Content Enrichment Workers**: Menerapkan klaster model lokal berbasis vLLM yang membaca data historis transaksi sewa, inflasi lokal, dan *walkability index*, menghasilkan sintesis unik sepanjang 250 kata per sub-distrik.
  2. **Tiered Sharded Dynamic XML Sitemaps**: 
     Membagi sitemap menjadi segmen 10.000 URL per file (maksimal 50.000 batas standar diturunkan guna menurunkan memory overhead bot parser). Setiap file dilindungi oleh HTTP ETag header untuk memotong bandwidth bot hingga $80\%$.
  3. **Edge Rendering Tier (Cloudflare Workers + Durable Objects)**:
     Implementasi Edge SWR caching: request bot langsung disajikan dari KV Store cache edge global ($< 25\text{ ms}$ TTFB), membebaskan klaster origin dari beban *crawler storm*.
- **Hasil Terukur (Setelah 90 Hari)**:
  - Crawl Budget efficiency melonjak $430\%$. Waktu crawl seluruh domain tuntas dalam kurun waktu 18 hari.
  - De-indexing manual penalty dicabut; 19 juta halaman berhasil masuk ke indeks utama (*primary index*).
  - Organik traffic bertumbuh $+310\%$, dengan Core Web Vitals LCP p75 bertahan pada angka $1.1\text{ detik}$.

---

### 9. Trade-offs

| Pendekatan / Fitur | Keuntungan | Biaya / Trade-off | Mitigasi Solusi |
| :--- | :--- | :--- | :--- |
| **Pure Static Generation (SSG)** | Biaya compute saat serving nol; latensi TTFB mendekati kecepatan CDN raw origin. | Waktu build CI/CD meledak (OOM crash) jika halaman $\ge 500.000$. | Beralih ke **Incremental Static Regeneration (ISR)** dengan static export hanya pada top 5% landing page. |
| **Edge Dynamic SSR** | Data selalu real-time; tidak butuh build-time panjang. | Biaya tagihan invocation function edge meningkat tinggi saat di-crawl jutaan kali. | Pasang layer cache *Stale-While-Revalidate* dengan header `Cache-Control: public, s-maxage=86400, stale-while-revalidate=604800`. |
| **Massive AI Text Generation** | Kualitas teks variatif; lolos deteksi duplikasi sederhana. | Risiko halusinasi data statistik; biaya inference token LLM yang membengkak. | Implementasikan *Retrieval-Augmented Generation* (RAG) berbasis deterministik graf database dengan strict JSON schema output. |
| **Aggressive Sitemaps Updating** | Googlebot lebih cepat mengetahui update konten terkini. | Jika update terlalu sering tanpa perubahan substantif data, Googlebot akan menurunkan prioritas crawl domain. | Audit diferensial konten via hashing hash (SHA-256): Hanya update `<lastmod>` sitemap jika hash payload berubah $> 5\%$. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan Umum:
1. **Soft-404 Masking**: Mengembalikan status `200 OK` dengan tampilan teks *"Data tidak ditemukan untuk kota X"*. Googlebot akan menandai ini sebagai soft-404 dan merusak reputasi kualitas domain.
2. **Infinite Pagination & Filter Traps**: Faceted navigation (misal: `?sort=price&filter=red&size=large`) diekspos tanpa `rel="canonical"` yang konsisten atau tanpa directive `robots.txt disallow`, menguras habis jatah crawl budget harian.
3. **Invalid Canonical Loop / Chain**: URL A menunjuk canonical ke URL B, sementara URL B mengarah kembali ke URL A, membingungkan indeks mesin pencari hingga kedua halaman dide-indeks.
4. **JSON-LD Escaping Failure**: Mengabaikan escaping string kutip ganda (`"`) atau karakter escape pada payload ulasan, menyebabkan script LD-JSON gagal di-parse oleh crawler.

#### Panduan Troubleshooting Produksi:
- **Gejala**: Google Search Console melaporkan spike *"Crawled - currently not indexed"*.
  - **Langkah 1**: Ambil sampel 100 URL dari laporan tersebut.
  - **Langkah 2**: Jalankan script audit headless Playwright: hitung rasio teks unik dibanding boilerplate template layout (*Token-to-Boilerplate Ratio*). Jika $< 0.25$, konten dinilai terlalu tipis.
  - **Langkah 3**: Periksa latensi server bot crawler. Jika HTTP TTFB $> 1.2\text{ detik}$, Googlebot secara dinamis menurunkan laju crawling untuk mencegah server target down.
  - **Langkah 4**: Periksa konsistensi canonical header vs inline tag HTML. Keduanya wajib mereferensikan URL absolut kanonikal yang seragam secara bit-per-bit.

---

### 11. Best Practices (Production Checklist)

#### Pre-Publish Engine Checklist:
- [ ] Validasi `<title>` unik per halaman, tidak melebihi 60 karakter / 580 piksel tampilan desktop.
- [ ] `<meta name="description">` terisi antara 120 - 155 karakter dengan data entitas dinamis yang tepat.
- [ ] Validasi canonical tag menggunakan URL absolut berprotokol HTTPS tanpa trailing slash inkonsisten.
- [ ] Render skema structured data lolos uji Schema.org validator tanpa status *Error* atau *Warning*.
- [ ] Cek status *Content Similarity Score* terhadap klaster halaman tetangga (maksimal kemiripan teks $\le 80\%$).

#### Infrastructure & Delivery Checklist:
- [ ] Edge CDN merespons bot dengan header `stale-while-revalidate` aktif.
- [ ] Dynamic Sitemap Sharder membatasi file maksimum 10.000 link dan terkompresi GZIP (`.xml.gz`).
- [ ] Endpoint `/robots.txt` melarang indexing query-parameter filtering tak terbatas (Faceted search query string traps).
- [ ] Server log streaming aktif memfilter `User-Agent` bot resmi (verifikasi IP via *Reverse DNS Lookup* untuk mencegah impersonator).
- [ ] Implementasi fail-safe return status `404 Not Found` atau `410 Gone` HTTP murni jika entitas primer data telah dihapus permanen.

---

### 12. Hands-on Practice (Langkah Praktikum Terpandu)

Semua file latihan pada seksi ini akan disimpan di direktori workspace: `hands-on/m02/`.

#### Langkah 1: Setup Lingkungan Node.js/TypeScript
```bash
mkdir -p hands-on/m02
cd hands-on/m02
npm init -y
npm install typescript @types/node fast-xml-parser crypto zod tsx --save-dev
npx tsc --init
```

#### Langkah 2: Buat Modul Anti-Soft-404 Guard & Deduplication Evaluator
Simpan kode berikut sebagai `hands-on/m02/quality-guard.ts`:

```typescript
import { createHash } from 'crypto';

export interface PagePayload {
  slug: string;
  primaryEntity: string;
  dataPoints: Record<string, number | string>;
  rawDescription: string;
}

export class ContentQualityGuard {
  private static readonly MINIMUM_DATA_POINTS = 3;
  private static readonly MINIMUM_TOKEN_COUNT = 50;

  /**
   * Menghitung SHA-256 fingerprint dari konten dinamis untuk mendeteksi identitas ganda
   */
  public static generateFingerprint(payload: PagePayload): string {
    const serialized = JSON.stringify({
      entity: payload.primaryEntity,
      points: Object.keys(payload.dataPoints).sort().map(k => `${k}:${payload.dataPoints[k]}`),
    });
    return createHash('sha256').update(serialized).digest('hex');
  }

  /**
   * Memvalidasi apakah halaman layak terbit atau berpotensi menjadi Soft-404/Thin Content
   */
  public static evaluatePublishability(payload: PagePayload): { canPublish: boolean; reason?: string } {
    const dataCount = Object.keys(payload.dataPoints).length;
    if (dataCount < this.MINIMUM_DATA_POINTS) {
      return {
        canPublish: false,
        reason: `Rejection: Halaman ini hanya memiliki ${dataCount} data poin unik (minimum: ${this.MINIMUM_DATA_POINTS}). Terdeteksi Thin-Content!`,
      };
    }

    const tokenCount = payload.rawDescription.trim().split(/\s+/).length;
    if (tokenCount < this.MINIMUM_TOKEN_COUNT) {
      return {
        canPublish: false,
        reason: `Rejection: Panjang token konten hanya ${tokenCount} kata (minimum: ${this.MINIMUM_TOKEN_COUNT}). Terdeteksi Soft-404 risk!`,
      };
    }

    return { canPublish: true };
  }
}
```

#### Langkah 3: Buat High-Performance Sitemap XML Sharder Engine
Simpan kode berikut sebagai `hands-on/m02/sitemap-sharder.ts`:

```typescript
export interface SitemapEntry {
  loc: string;
  lastmod: string;
  changefreq: 'always' | 'hourly' | 'daily' | 'weekly' | 'monthly' | 'yearly' | 'never';
  priority: number;
}

export class SitemapSharder {
  private readonly maxEntriesPerShard: number;

  constructor(maxEntriesPerShard = 5000) {
    this.maxEntriesPerShard = maxEntriesPerShard;
  }

  public generateShards(entries: SitemapEntry[]): string[] {
    const shards: string[] = [];
    const totalBatches = Math.ceil(entries.length / this.maxEntriesPerShard);

    for (let i = 0; i < totalBatches; i++) {
      const batch = entries.slice(i * this.maxEntriesPerShard, (i + 1) * this.maxEntriesPerShard);
      let xml = '<?xml version="1.0" encoding="UTF-8"?>\n';
      xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n';

      for (const entry of batch) {
        xml += '  <url>\n';
        xml += `    <loc>${this.escapeXml(entry.loc)}</loc>\n`;
        xml += `    <lastmod>${entry.lastmod}</lastmod>\n`;
        xml += `    <changefreq>${entry.changefreq}</changefreq>\n`;
        xml += `    <priority>${entry.priority.toFixed(1)}</priority>\n`;
        xml += '  </url>\n';
      }

      xml += '</urlset>';
      shards.push(xml);
    }

    return shards;
  }

  public generateIndex(shardUrls: string[]): string {
    let xml = '<?xml version="1.0" encoding="UTF-8"?>\n';
    xml += '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n';

    for (const url of shardUrls) {
      xml += '  <sitemap>\n';
      xml += `    <loc>${this.escapeXml(url)}</loc>\n`;
      xml += `    <lastmod>${new Date().toISOString()}</lastmod>\n`;
      xml += '  </sitemap>\n';
    }

    xml += '</sitemapindex>';
    return xml;
  }

  private escapeXml(unsafe: string): string {
    return unsafe.replace(/[<>&'"]/g, (c) => {
      switch (c) {
        case '<': return '&lt;';
        case '>': return '&gt;';
        case '&': return '&amp;';
        case '\'': return '&apos;';
        case '"': return '&quot;';
        default: return c;
      }
    });
  }
}
```

#### Langkah 4: Jalankan Test Simulator
Simpan kode berikut sebagai `hands-on/m02/run-simulation.ts`:

```typescript
import { ContentQualityGuard, PagePayload } from './quality-guard';
import { SitemapSharder, SitemapEntry } from './sitemap-sharder';

async function main() {
  console.log('--- 1. Menjalankan Quality Guard Simulator ---');
  
  const badPage: PagePayload = {
    slug: '/salaries/rust-engineer-alaska',
    primaryEntity: 'Rust Engineer in Alaska',
    dataPoints: { median: 120000 }, // Hanya 1 poin data
    rawDescription: 'Gaji rata-rata rust engineer di Alaska sangat bersaing.',
  };

  const validation = ContentQualityGuard.evaluatePublishability(badPage);
  console.log('Bad Page Publish Status:', validation);

  const goodPage: PagePayload = {
    slug: '/salaries/rust-engineer-san-francisco',
    primaryEntity: 'Rust Engineer in San Francisco',
    dataPoints: {
      median: 185000,
      p10: 140000,
      p90: 245000,
      openingsCount: 42,
    },
    rawDescription: 'Laporan kompensasi komprehensif untuk Rust Systems Engineer di San Francisco Bay Area mencakup tren gaji dasar, ekuitas saham, dan perbandingan biaya hidup terkini yang diperbarui secara otomatis setiap minggu.',
  };

  const goodValidation = ContentQualityGuard.evaluatePublishability(goodPage);
  console.log('Good Page Publish Status:', goodValidation);

  console.log('\n--- 2. Menjalankan Sharded Sitemap Generation ---');
  const dummyEntries: SitemapEntry[] = Array.from({ length: 12 }, (_, i) => ({
    loc: `https://www.example.com/salaries/page-${i + 1}`,
    lastmod: new Date().toISOString(),
    changefreq: 'weekly',
    priority: 0.8,
  }));

  const sharder = new SitemapSharder(5); // Shard per 5 entri untuk kebutuhan tes
  const shards = sharder.generateShards(dummyEntries);
  console.log(`Dihasilkan ${shards.length} file sitemap shard.`);
  
  const indexXml = sharder.generateIndex([
    'https://www.example.com/sitemaps/sitemap-1.xml',
    'https://www.example.com/sitemaps/sitemap-2.xml',
    'https://www.example.com/sitemaps/sitemap-3.xml',
  ]);
  console.log('\nGenerated Sitemap Index:\n', indexXml);
}

main();
```

Jalankan simulasi via CLI:
```bash
npx tsx hands-on/m02/run-simulation.ts
```

---

### 13. Exercise

#### Level Easy
Tuliskan sebuah helper function TypeScript `normalizeCanonicalUrl(rawUrl: string): string` yang:
1. Menghapus trailing slash (`/`).
2. Menghapus seluruh parameter query string non-esensial (`utm_*`, `fbclid`, `ref`).
3. Mengonversi semua komponen path menjadi huruf kecil (*lowercase*).

#### Level Medium
Buat sebuah middleware edge runtime yang mengevaluasi `User-Agent` incoming request. Jika client terdeteksi sebagai `Googlebot` atau `Bingbot`:
- Terapkan header respons khusus: `X-Robots-Tag: index, follow, max-image-preview:large`.
- Log alamat IP, status respons, dan latensi proses ke backend analitik terpisah menggunakan `fetch` async non-blocking (`waitUntil`).

#### Level Hard
Rancang arsitektur sistem berbasis message broker (Kafka/RabbitMQ) yang memproses update dari 500.000 record database per hari:
- Gunakan skema *batching aggregation window* (5 menit) untuk mengelompokkan URL yang berubah.
- Lakukan deduplikasi URL yang mengalami mutasi berulang dalam satu window.
- Kirim payload batch maksimal 10.000 URL per panggilan API ke protokol *IndexNow*.
- Simpan state audit ke PostgreSQL lengkap dengan retry mechanism exponential backoff jika IndexNow mengembalikan status `429 Too Many Requests`.

---

### 14. Challenge

**Skenario**:
Platform FinTech Anda meluncurkan 5.000.000 halaman perbandingan nilai tukar valuta asing secara programmatic (misal: `/convert-usd-to-idr`, `/convert-eur-to-jpy`). Namun, setelah rilis 1.000.000 halaman pertama, terjadi insiden:
1. Googlebot membanjiri origin server dengan 800 request/detik, menyebabkan origin database mengalami *connection pool exhaustion* dan server mengeluarkan status HTTP 503.
2. Google Search Console mendeteksi 400.000 halaman sebagai *Duplicate, Google chose different canonical than user*.

**Tugas Anda**:
Rancang dokumen arsitektur teknis lengkap (spesifikasi arsitektur edge, strategi multi-tier caching, dan resolusi canonical) untuk menyelesaikan masalah ini tanpa menurunkan halaman yang sudah tayang. Skema solusi Anda harus mencakup:
- Strategi penanganan *thundering herd problem* saat cache CDN miss.
- Penegasan status kode HTTP yang tepat untuk crawler selama fase stabilisasi.
- Formula penghitungan *Canonical Authority* otomatis agar Googlebot tidak memilih URL alternatif lain.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic (Pilihan Ganda)
1. Apa fungsi utama dari header HTTP `stale-while-revalidate` dalam konteks penjelajahan Googlebot?
   - A. Memaksa Googlebot mengunduh konten terbaru secara sinkron setiap saat.
   - B. Menyajikan versi cache usang secara instan kepada crawler sementara edge worker memperbarui cache di background.
   - C. Menginstruksikan bot untuk menghapus halaman dari indeks.
   - D. Mengubah status kode HTTP menjadi 301 Redirect otomatis.

2. Berapa batas maksimum jumlah URL dan ukuran file uncompressed standar untuk satu file Sitemap XML menurut protokol sitemaps.org?
   - A. 10.000 URL atau 10 MB.
   - B. 50.000 URL atau 50 MB.
   - C. 100.000 URL atau 100 MB.
   - D. Tidak terbatas selama di-gzip.

3. Apa konsekuensi teknis jika sebuah halaman programmatic SEO mengembalikan status HTTP `200 OK`, namun isi halamannya adalah teks "Produk tidak ditemukan"?
   - A. Halaman diindeks secara prioritas tinggi.
   - B. Terdeteksi sebagai *Soft-404*, yang dapat mengikis alokasi crawl budget dan merusak domain trust.
   - C. Googlebot otomatis mengalihkan ke halaman beranda.
   - D. Browser klien otomatis memblokir domain.

4. Protokol *IndexNow* digunakan untuk memberitahu mesin pencari apa saja secara real-time?
   - A. Hanya Google.
   - B. Bing, Yandex, dan mesin pencari lain yang berpartisipasi.
   - C. Khusus LLM scraper seperti OpenAIbot.
   - D. Internal Search Engine perusahaan saja.

5. Tag skema Schema.org format apa yang secara resmi paling direkomendasikan oleh Google untuk structured data modern?
   - A. Microdata
   - B. RDFa
   - C. JSON-LD
   - D. XML-RPC

#### B. Pertanyaan Intermediate
1. Jelaskan perbedaan mendasar antara *Client-Side Rendering (CSR)* dan *Incremental Static Regeneration (ISR)* dari sudut pandang alokasi crawl budget bot mesin pencari!
2. Mengapa trailing slash yang tidak konsisten (misal: `/page` vs `/page/`) dapat menimbulkan isu de-indeksasi pada platform programmatic SEO skala besar?
3. Bagaimana mekanisme *Faceted Navigation* dapat menghabiskan alokasi *Crawl Budget* jika tidak dikontrol dengan konfigurasi `robots.txt` atau canonical tags?
4. Apa yang dimaksud dengan *Information Gain Score* pada algoritma penilai kualitas konten mesin pencari modern?
5. Mengapa penempatan JSON-LD di dalam blok `<head>` lebih disarankan daripada menaruhnya secara dinamis via script client-side di akhir `<body>`?

#### C. Skenario Kasus Produksi
1. **Kasus 1**: Domain Anda memiliki 2.000.000 URL programmatic. Log server mendeteksi bahwa Googlebot menghabiskan $80\%$ crawl budget-nya pada URL berparameter pagination lama seperti `?page=400` dan jarang menyentuh konten baru yang dipublikasikan di `?page=1`. Tindakan arsitektural apa yang harus segera Anda ambil?
2. **Kasus 2**: Setelah migrasi besar platform programmatic dari server origin tunggal ke CDN Edge Worker, traffic organik anjlok drastis dalam 14 hari. Saat diinvestigasi, edge compute merespons crawler dengan kode status `304 Not Modified` padahal konten telah diperbarui total. Apa akar penyebab kegagalan header cache HTTP ini?
3. **Kasus 3**: Audit log CDN menunjukkan ribuan bot palsu (menggunakan User-Agent Googlebot palsu) melakukan scraping intensif sehingga memicu lonjakan biaya komputasi origin. Bagaimana Anda merancang validasi identitas bot yang valid pada layer CDN Edge sebelum request diteruskan ke origin?

---

### 16. Summary

- **Enterprise Programmatic SEO** menuntut transformasi dari sekadar *template generation* menjadi sistem terdistribusi mutakhir yang menggabungkan edge compute, data deduplication, dan quality gatekeeping.
- **Crawl Budget Optimization** dicapai melalui kombinasi penataan sitemap sharded berkas, header caching presisi (`stale-while-revalidate`), respons latensi edge TTFB ultra-rendah ($< 50\text{ ms}$), dan pelarangan faceted navigation loops.
- **Pencegahan Penalti Kualitas (Helpful Content System & Panda)** mengharuskan platform menerapkan ambang batas ketat: halaman yang kekurangan metrik bernilai unik (*Information Gain*) wajib diblokir, di-*noindex*, atau digabung sebelum sempat dirayapi bot mesin pencari.
- **Automasi Real-Time**: Sinkronisasi data mutasi via protokol *IndexNow* serta granular cache-tag invalidation memastikan kesegaran data (*freshness*) tetap terjaga tanpa membebani infrastruktur origin secara masif.