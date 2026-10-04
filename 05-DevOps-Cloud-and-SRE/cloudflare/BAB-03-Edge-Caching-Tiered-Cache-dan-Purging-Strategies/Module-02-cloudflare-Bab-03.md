# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Kategori:** 05-DevOps-Cloud-and-SRE | **Topik:** Cloudflare | **Bab 03:** Edge Caching, Tiered Cache, dan Purging Strategies

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis dan Mengonfigurasi Arsitektur Caching Multi-Tier**: Mengimplementasikan topologi Smart Tiered Cache dan Cache Reserve berbasis persistent object storage (R2) untuk meminimalkan *origin egress traffic* hingga >95%.
- **Merancang Custom Cache Keys Tingkat Lanjut**: Mengembangkan aturan partisi cache deterministik menggunakan Cloudflare Ruleset Engine dan Cloudflare Workers untuk memisahkan cache berdasarkan *device type*, *geo-location*, *currency*, serta normalisasi *query string*.
- **Mengorkestrasi Event-Driven Invalidation Pipeline**: Membangun sistem purges skala enterprise menggunakan `Cache-Tag` (Surrogate Keys), *prefix-based purging*, dan *host-based purging* yang terintegrasi dengan arsitektur message queue (Kafka/RabbitMQ/AWS SQS).
- **Menerapkan Pola Ketahanan Cache Tingkat Tinggi**: Mengonfigurasi `stale-while-revalidate` (RFC 5861) dan `stale-if-error` untuk mencegah insiden *Cache Stampede* (*Thundering Herd*) saat lonjakan *traffic* masif dan kegagalan origin server.
- **Melakukan Debugging dan Audit Tingkat Lanjut**: Mengurai header diagnostik edge (`CF-Cache-Status`, `CF-Ray`, `Age`, `CF-Cache-Reserve`) untuk menganalisis jalur komputasi cache dan menyelesaikan degradasi *Cache Hit Ratio* (CHR).

---

### 2. Prerequisites
Sebelum mempelajari modul ini, peserta wajib memahami:
- **Protokol HTTP/1.1, HTTP/2, dan HTTP/3**: Pemahaman mendalam mengenai semantik header `Cache-Control`, `Vary`, `ETag`, `If-None-Match`, dan spesifikasi RFC 7234 serta RFC 5861.
- **Dasar Jaringan Anycast & DNS**: Pemahaman tentang perutean BGP Anycast, terminologi PoP (Point of Presence), dan terminologi Edge vs Origin.
- **Infrastruktur As Code (IaC)**: Pengalaman praktis menulis modul Terraform/OpenTofu (`cloudflare` provider versi 4.x atau 5.x).
- **Pemrograman Serverless Edge**: Pemahaman dasar JavaScript/TypeScript untuk runtime V8 pada Cloudflare Workers.
- **Akses & Autentikasi API**: Cloudflare Enterprise Account (atau minimal Pro/Business untuk fitur Cache Rules tertentu) dengan API Token yang memiliki izin `Cache Purge:Edit` dan `Zone:Edit`.

---

### 3. Concept & Internal Architecture

#### 3.1 Siklus Hidup Request dan Hierarki Penyimpanan Edge
Cloudflare mengoperasikan ratusan Edge PoP di seluruh dunia. Ketika sebuah request HTTP masuk ke jaringan Anycast Cloudflare, siklus evaluasi cache tidak bersifat monolitik, melainkan melalui arsitektur multi-layer:

```
[Client]
   │
   ▼
[Lower-Tier Edge PoP] (Anycast Ingress terdekat dengan klien)
   │  ├── RAM Cache (In-Memory Hot Path)
   │  └── NVMe SSD Cache (Local PoP Storage)
   │
   ├── (MISS) ──► [Upper-Tier PoP / Argo Smart Routing] (Data Center Regional Terkonsentrasi)
   │                 ├── Upper-Tier NVMe Storage
   │                 │
   │                 ├── (MISS) ──► [Cache Reserve (R2)] (Persistent S3-compatible Layer)
   │                 │                 │
   │                 │                 └── (MISS) ──► [Customer Origin Server]
```

1. **Lower-Tier Edge PoP**: Menerima koneksi TLS dari klien. Memeriksa memori lokal (RAM) untuk *hottest resources*, kemudian NVMe drive. Jika terjadi cache MISS, PoP lokal tidak langsung menghubungi origin.
2. **Argo Tiered Cache (Upper-Tier PoP)**: Lower-tier PoP merutekan request ke Upper-Tier PoP (hub transit terdekat dengan origin customer). Upper-Tier PoP bertindak sebagai *Origin Shield*, mengonsolidasikan MISS dari lusinan Edge PoP lokal di seluruh region menjadi satu request tunggal.
3. **Cache Reserve**: Berfungsi sebagai lapisan persisten ketiga yang dibangun di atas Cloudflare R2. Jika aset terlempar (evicted) dari NVMe edge karena minimnya frekuensi request (LRU - Least Recently Used), request dialihkan ke Cache Reserve sebelum menyentuh origin customer.

#### 3.2 Struktur dan Hashing Custom Cache Key
Secara *default*, Cloudflare mendefinisikan *Cache Key* standar sebagai kombinasi:
$$\text{Cache Key} = \text{Hash}(\text{Scheme} + \text{Host} + \text{URI Path} + \text{Query String})$$

Masalah timbul pada aplikasi skala besar di mana query string mengandung pelacak pemasaran (misal: `utm_source`, `fbclid`) atau parameter yang tidak terurut (`?b=2&a=1` vs `?a=1&b=2`). Tanpa normalisasi, integritas cache key terpecah, menyebabkan CHR anjlok drastis (*cache fragmentation*).

Melalui **Custom Cache Key**, kita dapat memanipulasi struktur input algoritma hashing:
- **Prefix Isolation**: Memisahkan key berdasarkan protokol (`http` vs `https`) atau custom string.
- **Header Injection**: Memasukkan nilai header tertentu ke dalam key (misal: `Accept-Language`, `CF-Device-Type`).
- **Cookie Whitelisting/Targeting**: Mengisolasi cache berdasarkan cookie tertentu (misal: `currency=USD` vs `currency=IDR`), sementara mengabaikan cookie analitik (`_ga`, `_gid`).
- **Query String Sorting & Filtering**: Menghapus tracking parameters dan mengurutkan query string secara leksikografis sebelum di-hash.

#### 3.3 Dynamic Purging Architecture: Inverted Index Engine
Pembersihan cache (*Purge*) via URL tunggal bersifat langsung, namun tidak realistis untuk aplikasi enterprise. Jika satu entitas data diperbarui (misal: sebuah produk pada database katalog), entitas tersebut mungkin muncul di puluhan halaman: halaman produk, halaman kategori, landing page, dan search result.

Cloudflare mengimplementasikan **Surrogate Keys** melalui response header `Cache-Tag`.
- Origin menyertakan header: `Cache-Tag: product-9912, category-electronics, brand-apple`.
- Edge PoP mem-parsing header ini, menyimpannya di memori, dan mengindeks relasi antara URI aset dan tag-tag tersebut ke dalam *Distributed Inverted Index*.
- Ketika origin memanggil API: `POST /zones/:id/purge_cache` dengan payload `{"tags": ["product-9912"]}`, Cloudflare menyebarkan instruksi pembatalan (*invalidation*) ke seluruh jaringan edge global dalam waktu < 150 milidetik melalui jaringan kontrol internal.
- Tag mapping di edge secara asinkron ditandai sebagai *expired/tombstoned*.

---

### 4. Why & What

| Fitur / Konsep | Mengapa Dibutuhkan (Pain Point) | Solusi Enterprise (What Cloudflare Provides) |
| :--- | :--- | :--- |
| **Tiered Cache** | Ratusan Edge PoP global melakukan request bersamaan ke origin untuk resource yang sama, memicu origin load spike. | Konsolidasi request global ke PoP Upper-Tier terpilih sehingga origin hanya menerima satu request per rotasi cache. |
| **Cache Reserve** | Objek jarang diakses (*long-tail content*) sering terkena eviksi LRU dari SSD edge, membebani origin bandwidth. | Penyimpanan persisten otomatis berbasis cloud-native storage (R2) dengan cost egress $0 ke Edge PoP. |
| **Custom Cache Keys** | URL dengan query string acak (`?utm_*`) atau variasi mobile/desktop memecah cache secara redundan. | Normalisasi, pemilahan, dan penyusunan ulang cache key deterministik melalui Ruleset Engine / Workers. |
| **Cache-Tag Purging** | Melakukan Purge All membuat origin down (thundering herd); purge per URL lambat dan rapuh terhadap perubahan arsitektur URL. | Invalidation presisi berbasis entitas data dengan single API call tanpa menyentuh cache objek lain. |
| **Stale-While-Revalidate** | Saat cache expired, user pertama mengalami latensi origin yang tinggi (*blocking fetch*). | Edge menyajikan konten stale secara instan ke user, sementara proses pembaruan ke origin berjalan *asynchronously* di background. |

---

### 5. How: Alur Pemrosesan Request & Invalidation

#### Alur 1: Ingress Request Lifecycle dengan Revalidasi Asinkron
```
Klien            Cloudflare Edge PoP               Upper-Tier PoP            Origin Server
  │                       │                              │                         │
  │── 1. GET /api/v1/x ──►│                              │                         │
  │                       ├── 2. Hash Cache Key          │                         │
  │                       ├── 3. Lookup Cache Storage    │                         │
  │                       │   (STALE hit ditemukan)      │                         │
  │◄── 4. Return 200 OK ──┤                              │                         │
  │    (Konten Stale)     │                              │                         │
  │                       ├── 5. Background Revalidate ─►│                         │
  │                       │   (RFC 5861)                 ├── 6. Forward Request ──►│
  │                       │                              │                         ├── 7. DB Query
  │                       │                              │◄── 8. Return 200/304 ───┤
  │                       │◄── 9. Stream Fresh Body ─────┤                         │
  │                       ├── 10. Update Cache Object    │                         │
  │                       ├── 11. Re-index Cache-Tags    │                         │
```

#### Alur 2: Event-Driven Purge Pipeline
```
[Database Write] ──► [Application Service] ──► [Kafka Topic: "catalog-updates"]
                                                        │
                                                        ▼
                                             [Cache Invalidator Worker]
                                                        │
                                                        ├── 1. Generate JWT / Cloudflare Token
                                                        ├── 2. Construct JSON Tag Payload
                                                        │
                                                        ▼
                                            [Cloudflare Client API]
                                                        │ (POST /zones/:id/purge_cache)
                                                        ▼
                                            [Global Control Plane]
                                                        │ (BGP / Internal Mesh Broadcast)
                                                        ▼
                                           [All Global Edge PoPs]
                                             (Set Tombstone Flag on Tag)
```

---

### 6. Analogy & Architecture Diagram

#### Analogi: Sistem Distribusi Logistik dan Inventaris
Bayangkan Cloudflare sebagai jaringan toko swalayan global:
- **Lower-Tier PoP** adalah minimarket di setiap kelurahan.
- **Upper-Tier PoP** adalah gudang distribusi regional tingkat provinsi.
- **Cache Reserve** adalah gudang logistik pusat berbasis sewa jangka panjang.
- **Origin Server** adalah pabrik manufaktur tempat barang diproduksi.
- **Custom Cache Key** adalah kode barcode barang. Jika sebuah produk memiliki bungkus berbeda untuk promo diskon (`utm_campaign`), barcode reader diprogram untuk membaca barcode inti saja, bukan warna plastiknya.
- **Cache-Tag** adalah pelabelan kategori. Alih-alih membongkar seluruh rak saat satu jenis saus ditarik dari peredaran, kasir cukup memindai tag "Saus-Merek-A" untuk menarik semua varian rasa yang terhubung secara instan.

#### Diagram Arsitektur Jaringan Cache Enterprise
```
                           INTERNET (ANYCAST EDGE)
                                     │
            ┌────────────────────────┴────────────────────────┐
            ▼                                                 ▼
   ┌──────────────────┐                              ┌──────────────────┐
   │ Lower PoP: CGK   │                              │ Lower PoP: SIN   │
   │ (Jakarta, ID)    │                              │ (Singapore)      │
   │ ┌──────────────┐ │                              │ ┌──────────────┐ │
   │ │ RAM/SSD Evict│ │                              │ │ RAM/SSD Evict│ │
   │ └──────┬───────┘ │                              │ └──────┬───────┘ │
   └────────┼─────────┘                              └────────┼─────────┘
            │                                                 │
            └────────────────────────┬────────────────────────┘
                                     │ (Enterprise Core Routing)
                                     ▼
                      ┌─────────────────────────────┐
                      │    Upper-Tier PoP: SIN      │
                      │  (Regional Origin Shield)   │
                      │ ┌─────────────────────────┐ │
                      │ │ High-Capacity NVMe Pool │ │
                      │ └───────────┬─────────────┘ │
                      └─────────────┼───────────────┘
                                    │
                       MISS (Check Persistent Tier)
                                    │
                                    ▼
                      ┌─────────────────────────────┐
                      │    Cache Reserve (R2)       │
                      │ (Persistent Global Storage) │
                      └─────────────┬───────────────┘
                                    │
                            MISS (Fetch Origin)
                                    │
                                    ▼
                      ┌─────────────────────────────┐
                      │    Customer Origin Server   │
                      │   (AWS / GCP / Bare Metal)  │
                      └─────────────────────────────┘
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Origin Configuration Header
Origin mengontrol edge caching menggunakan standar response header HTTP.

```http
HTTP/1.1 200 OK
Content-Type: application/json
Content-Length: 1024
Connection: keep-alive
Date: Mon, 15 Jan 2024 10:00:00 GMT
Cache-Control: public, max-age=300, s-maxage=86400, stale-while-revalidate=60, stale-if-error=86400
Cache-Tag: category-electronics, brand-sony, product-98124
ETag: W/"v128-4f8a9b2c"
```
*Analisis Header:*
- `max-age=300`: Browser hanya menyimpan cache selama 5 menit.
- `s-maxage=86400`: Cloudflare Edge menyimpan cache selama 24 jam.
- `stale-while-revalidate=60`: Jika request masuk pada detik 86.401 hingga 86.460, Cloudflare langsung menyajikan data stale, kemudian merevalidasi ke origin secara background.
- `stale-if-error=86400`: Jika origin 5xx/down saat revalidasi, Edge tetap menyajikan cache lama hingga 24 jam ke depan.
- `Cache-Tag`: Metadata pengelompokan purge.

---

#### 7.2 Practical Example (Production Grade): IaC Terraform & Worker Invalidation Service

##### File 1: `main.tf` (Orkestrasi Ruleset Engine & Cache Reserve)
```hcl
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.25.0"
    }
  }
}

variable "zone_id" {
  type        = string
  description = "The Cloudflare Zone ID"
}

# 1. Mengaktifkan Argo Tiered Cache
resource "cloudflare_tiered_cache" "argo_tiered_cache" {
  zone_id    = var.zone_id
  cache_type = "smart"
}

# 2. Mengaktifkan Cache Reserve
resource "cloudflare_zone_cache_reserve" "cache_reserve" {
  zone_id = var.zone_id
  value   = "on"
}

# 3. Cache Rules via Ruleset Engine: Custom Cache Key & TTL Overrides
resource "cloudflare_ruleset" "advanced_cache_rules" {
  zone_id     = var.zone_id
  name        = "Production Advanced Cache Policy"
  description = "Custom Cache Key, Tracking Query Stripping, and Device Partitioning"
  kind        = "zone"
  phase       = "http_request_cache_settings"

  rules {
    action = "set_cache_settings"
    action_parameters {
      cache = true
      edge_ttl {
        mode    = "respect_origin"
        default = 86400
        minimum = 300
      }
      browser_ttl {
        mode    = "respect_origin"
        default = 300
      }
      serve_stale {
        disable_stale_while_updating = false
      }
      cache_key {
        ignore_query_strings_order = true
        
        cache_deception_armor = true

        custom_key {
          query_string {
            exclude = ["utm_source", "utm_medium", "utm_campaign", "fbclid", "gclid"]
          }
          header {
            name = "x-currency"
            check_presence = ["x-currency"]
          }
          user {
            device_type = true
            geo         = true
          }
        }
      }
    }
    expression  = "(http.request.uri.path.extension in {\"jpg\" \"png\" \"webp\" \"js\" \"css\" \"woff2\"}) or (http.request.uri.path matches \"^/api/v1/catalog/\")"
    description = "Enforce Deterministic Cache Key on Static Assets and Catalog APIs"
    enabled     = true
  }
}
```

##### File 2: `invalidation-worker.ts` (Event-Driven Cache-Tag Purge Microservice)
```typescript
export interface Env {
  CF_API_TOKEN: string;
  CF_ZONE_ID: string;
  PURGE_QUEUE: Queue<PurgeMessage>;
}

interface PurgeMessage {
  tags: string[];
  initiatedBy: string;
  timestamp: number;
}

export default {
  // Consumer untuk Queue Invalidation (Event-Driven via SQS/Cloudflare Queues)
  async queue(batch: MessageBatch<PurgeMessage>, env: Env): Promise<void> {
    const aggregatedTags = new Set<string>();

    for (const msg of batch.messages) {
      msg.body.tags.forEach((tag) => aggregatedTags.add(tag));
      msg.ack();
    }

    if (aggregatedTags.size === 0) return;

    const tagArray = Array.from(aggregatedTags);
    
    // Cloudflare API membatasi maksimal 30 tag per Purge Call
    const chunkSize = 30;
    for (let i = 0; i < tagArray.length; i += chunkSize) {
      const chunk = tagArray.slice(i, i + chunkSize);
      await purgeCacheTags(env.CF_ZONE_ID, env.CF_API_TOKEN, chunk);
    }
  },

  // HTTP Endpoint untuk pemicu manual/webhook dari CMS/Backend Engine
  async fetch(request: Request, env: Env): Promise<Response> {
    if (request.method !== "POST") {
      return new Response("Method Not Allowed", { status: 405 });
    }

    const authHeader = request.headers.get("Authorization");
    if (!authHeader || !authHeader.startsWith("Bearer secret-token")) {
      return new Response("Unauthorized", { status: 401 });
    }

    try {
      const payload: { tags: string[] } = await request.json();
      if (!payload.tags || !Array.isArray(payload.tags)) {
        return new Response("Invalid Payload: 'tags' array required", { status: 400 });
      }

      await env.PURGE_QUEUE.send({
        tags: payload.tags,
        initiatedBy: "Internal-API",
        timestamp: Date.now(),
      });

      return new Response(JSON.stringify({ status: "Purge task queued successfully" }), {
        status: 202,
        headers: { "Content-Type": "application/json" },
      });
    } catch (err: any) {
      return new Response(JSON.stringify({ error: err.message }), { status: 500 });
    }
  },
};

async function purgeCacheTags(zoneId: string, apiToken: string, tags: string[]): Promise<void> {
  const url = `https://api.cloudflare.com/client/v4/zones/${zoneId}/purge_cache`;
  
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${apiToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ tags }),
  });

  if (!response.ok) {
    const errorText = await response.text();
    console.error(`Purge Failed: ${response.status} - ${errorText}`);
    throw new Error(`Cloudflare API Purge Error: ${response.statusText}`);
  }

  const result = await response.json();
  console.log(`Successfully purged tags: ${tags.join(", ")}; API Result:`, result);
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: E-Commerce Flash Sale Global (50M Requests/Minute)
- **Konteks**: Sebuah platform retail enterprise global menyelenggarakan flash sale gawai flagship. Trafik diprediksi melonjak dari 200.000 req/menit menjadi 50.000.000 req/menit dalam rentang 3 detik.
- **Tantangan Arsitektur**:
  1. Katalog API (`/api/v2/products/*`) harus real-time jika stok habis, namun origin hanya mampu melayani maksimal 10.000 RPS sebelum database connection pool exhaustion.
  2. Pembeli datang dari 40+ negara dengan mata uang dan preferensi bahasa yang berbeda.
  3. Menggunakan "Purge Everything" saat update diskon pernah meruntuhkan origin hingga *downtime* 45 menit pada event sebelumnya.
- **Implementasi Solusi**:
  1. **Tiered Cache Topology**: Mengaktifkan *Argo Smart Tiered Cache*. Permintaan global dikonsolidasikan ke Upper-Tier PoP di Frankfurt, Singapura, dan Virginia Barat.
  2. **Fine-Grained Custom Cache Key**:
     - Key dipartisi berdasarkan: URI Path + Header `X-Country` + Header `X-Currency`.
     - Semua parameter analitik pemasaran (`utm_*`, `gclid`, dsb) diabaikan dari Cache Key.
  3. **Event-Driven Cache-Tag Matrix**:
     - Setiap item memiliki tag: `product:<id>`, `sku:<id>`, `category:<id>`, dan `inventory:<status>`.
     - Ketika kuota habis, microservice database memicu Cloudflare Queue yang mengirimkan Purge API hanya untuk tag `product:<id>`.
  4. **Penerapan Stale-While-Revalidate & Lock**:
     - Origin merespons dengan: `Cache-Control: public, s-maxage=30, stale-while-revalidate=10, stale-if-error=300`.
- **Hasil Terukur**:
  - **Cache Hit Ratio (CHR)** naik dari 68.2% menjadi **98.7%**.
  - **Origin Load** turun drastis; hanya menerima ~6.500 RPS dari total beban puncak 50.000.000 req/menit.
  - **Mean Propagation Latency Invalidation**: 85 milidetik secara global.
  - Zero downtime selama event flash sale 48 jam.

---

### 9. Trade-offs (Analisis Arsitektur)

| Dimensi | Trade-off / Pilihan | Konsekuensi Positif | Konsekuensi Negatif / Risiko |
| :--- | :--- | :--- | :--- |
| **Purge Strategy** | **Purge All** vs **Surrogate Keys (Cache-Tag)** | Purge All sangat mudah diimplementasikan (1 API call tanpa kalkulasi dependensi). | Purge All memicu *Cache Stampede*. Seluruh traffic global langsung menghantam origin, hampir pasti melumpuhkan downstream database. |
| **Storage Architecture** | **Standard SSD Edge** vs **Cache Reserve (R2)** | Cache Reserve mempertahankan *long-tail assets* (gambar/PDF lama) agar tidak dievuksi, menghemat origin egress bandwidth. | Menambah biaya langganan Cache Reserve ($/GB-month storage & read operation units) dan sedikit menambah TTFB (Time To First Byte) pada cache hit layer persisten dibanding direct RAM hit. |
| **Cache Key Granularity** | **Aggressive Partitioning** vs **Broad Partitioning** | Menambahkan `User-Agent`, `Header`, dan `Cookie` ke Cache Key mencegah kebocoran data terpersonalisasi (*Cache Poisoning/Information Leak*). | *Fragmentasi Cache*: Kapasitas simpan terbagi-bagi ke banyak variasi entri, menurunkan CHR keseluruhan dan meningkatkan load ke origin. |
| **Revalidation Mode** | **Synchronous Blocking** vs **Stale-While-Revalidate** | SWR menjamin latensi klien konsisten < 20ms karena tidak pernah tertahan (*blocked*) oleh proses komputasi revalidasi ke origin. | Klien berpotensi menerima data kadaluarsa (*stale*) beberapa detik lebih lama sampai revalidasi background tuntas. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Kesalahan Fatal Umum (Anti-Patterns)
1. **Cache Poisoning via Variabel Tidak Ternormalisasi**: Menyertakan seluruh HTTP `Vary` header (misal: `Vary: User-Agent`). Cloudflare akan membuat entri cache unik untuk setiap variasi versi minor browser klien. Akibatnya: CHR mendekati 0%.
2. **Tag Header Truncation**: Response origin mengirim header `Cache-Tag` melebihi panjang batas maksimal (Enterprise: batas string header 16 KB per response). Karakter tag yang terpotong di akhir akan menghasilkan string tag korup, membuat pemanggilan purge API pada tag tersebut gagal total.
3. **Inadvertent PII Caching**: Mengabaikan pembersihan header `Set-Cookie` dari response dynamic origin saat melakukan caching. Token sesi otentikasi user A dapat tersimpan di edge dan disajikan ke user B.
4. **Purge Storm Rate Limit**: Mengirim Purge API calls secara sekuensial per item (10.000 request/detik) alih-alih melakukan *batching*. Cloudflare API membatasi kuota REST API (1.200 request per 5 menit untuk control plane), menyebabkan HTTP 429 Too Many Requests.

#### 10.2 Debugging Cheatsheet (Header Diagnostic Flow)
Periksa header diagnostik menggunakan terminal:
```bash
curl -svo /dev/null -H "x-currency: USD" https://example.com/api/v1/catalog/item-123
```

| Header Diagnostic | Nilai Nilai Kemungkinan | Masalah & Solusi Investigasi |
| :--- | :--- | :--- |
| `CF-Cache-Status` | `HIT` | Data disajikan langsung dari Edge Cache lokal PoP. Operasional normal. |
| `CF-Cache-Status` | `MISS` | Data tidak ditemukan di Cache; diambil dari Origin. Periksa apakah Cache Key berubah. |
| `CF-Cache-Status` | `EXPIRED` | TTL telah berakhir. Origin dihubungi untuk revalidasi. |
| `CF-Cache-Status` | `STALE` | Konten kadaluarsa disajikan ke klien karena `stale-while-revalidate` aktif sementara edge mengambil konten baru. |
| `CF-Cache-Status` | `BYPASS` | Cloudflare dikonfigurasi untuk tidak meng-cache resource ini (misal via Cache Rules / Page Rules). |
| `CF-Cache-Status` | `DYNAMIC` | Cloudflare tidak meng-cache resource secara default (misal file ekstensi `.json`/`.php` tanpa Cache Rule eksplisit). |
| `CF-Cache-Reserve` | `HIT` | Ditemukan di Persistent R2 Cache Reserve setelah eviksi dari Edge SSD. |
| `CF-Ray` | Format: `84b2c1a8...-SIN` | Tiga huruf terakhir menunjukkan IATA code PoP yang melayani (`SIN` = Singapura). |

---

### 11. Best Practices (Production Checklist)

#### Security & Compliance Checklist
- [ ] **Strip Private Cookies**: Selalu gunakan Cloudflare Worker atau Response Modification Rule untuk menghapus header `Set-Cookie` pada setiap URL yang memiliki instruksi cache publik.
- [ ] **Terapkan Cache Deception Armor**: Aktifkan fitur proteksi *Web Cache Deception* pada Cache Settings untuk mencegah manipulasi ekstensi path (contoh: `/profile/account.css` padahal endpoint mengeksekusi data sensitif akun).
- [ ] **Enkripsi API Credentials**: Gunakan Secrets Manager saat mendistribusikan Cloudflare Purge API Token ke worker atau aplikasi CI/CD.

#### SRE & Reliability Checklist
- [ ] **Set Default `stale-if-error`**: Selalu sediakan fallback minimal 86400 (24 jam) untuk aset katalog publik guna menjamin uptime ketika origin runtuh.
- [ ] **Batching Purge Requests**: Desain message queue worker untuk mengonsolidasikan pembersihan tag dengan limit maksimal 30 tag per batch request ke Cloudflare API.
- [ ] **Health Checks & Tiered Routing**: Pastikan Upper-Tier PoP memiliki route redundansi jika terjadi degradasi interkoneksi transatlantic.

#### Performance Optimization Checklist
- [ ] **Query String Sorting**: Selalu aktifkan opsi `ignore_query_strings_order` di konfigurasi Custom Cache Key.
- [ ] **Strip Tracking Parameters**: Buang parameter `utm_*`, `fbclid`, `ref`, `trk` dari proses pembentukan Cache Key.
- [ ] **Brotli & Early Hints**: Integrasikan Edge Caching dengan kompresi Brotli level 11 dan 103 Early Hints untuk resource CSS/JS kritis.

---

### 12. Hands-on Practice

Simpan seluruh file praktikum di direktori: `hands-on/m02/`

```bash
mkdir -p hands-on/m02/{terraform,scripts,mock-origin}
cd hands-on/m02
```

#### Langkah 1: Bangun Mock Origin Server (Node.js)
Buat file `mock-origin/server.js`:
```javascript
const http = require('http');

let inventoryCount = 100;

const server = http.createServer((req, res) => {
  console.log(`[ORIGIN HIT] Received request for: ${req.url}`);

  if (req.url.startsWith('/api/product')) {
    res.writeHead(200, {
      'Content-Type': 'application/json',
      // Cache di Cloudflare Edge 60 detik, Stale data diizinkan hingga 120 detik
      'Cache-Control': 'public, s-maxage=60, stale-while-revalidate=120, stale-if-error=3600',
      // Tag entitas untuk granular purge
      'Cache-Tag': 'product-tag-electronics, product-item-1',
      'X-Origin-Host': 'mock-origin-node-01',
      'ETag': `"item-1-v${inventoryCount}"`
    });

    res.end(JSON.stringify({
      id: "prod-1",
      name: "Enterprise Edge Gateway",
      stock: inventoryCount,
      servedAt: new Date().toISOString()
    }));
    return;
  }

  res.writeHead(404);
  res.end("Not Found");
});

server.listen(8080, () => {
  console.log('Mock Origin listening on port 8080');
});
```

#### Langkah 2: Buat Skrip Otomasi Purge via Cache-Tag
Buat file `scripts/purge_by_tag.py`:
```python
#!/usr/bin/env python3
import os
import sys
import json
import urllib.request
import urllib.error

CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN")
CLOUDFLARE_ZONE_ID = os.getenv("CLOUDFLARE_ZONE_ID")

if not CLOUDFLARE_API_TOKEN or not CLOUDFLARE_ZONE_ID:
    print("Error: CLOUDFLARE_API_TOKEN dan CLOUDFLARE_ZONE_ID harus didefinisikan.")
    sys.exit(1)

if len(sys.argv) < 2:
    print("Usage: ./purge_by_tag.py <tag1> <tag2> ...")
    sys.exit(1)

tags_to_purge = sys.argv[1:]

url = f"https://api.cloudflare.com/client/v4/zones/{CLOUDFLARE_ZONE_ID}/purge_cache"
headers = {
    "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
    "Content-Type": "application/json"
}
data = json.dumps({"tags": tags_to_purge}).encode('utf-8')

req = urllib.request.Request(url, data=data, headers=headers, method="POST")

try:
    with urllib.request.urlopen(req) as response:
        res_body = response.read().decode('utf-8')
        print(f"Status Code: {response.status}")
        print("Response Body:", json.dumps(json.loads(res_body), indent=2))
except urllib.error.HTTPError as e:
    print(f"HTTP Error: {e.code} - {e.read().decode('utf-8')}")
except Exception as e:
    print(f"General Error: {str(e)}")
```
Pastikan file dapat dieksekusi:
```bash
chmod +x scripts/purge_by_tag.py
```

#### Langkah 3: Eksekusi Pengujian & Verifikasi Invalidation
1. Pastikan origin diarahkan ke internet menggunakan secure tunnel (misal `cloudflared tunnel`) dan terhubung ke domain Cloudflare Anda.
2. Jalankan request curl pertama:
   ```bash
   curl -I https://your-domain.com/api/product
   # Verifikasi CF-Cache-Status: MISS
   ```
3. Jalankan request curl kedua:
   ```bash
   curl -I https://your-domain.com/api/product
   # Verifikasi CF-Cache-Status: HIT
   ```
4. Eksekusi purges via tag yang relevan:
   ```bash
   export CLOUDFLARE_API_TOKEN="your-api-token"
   export CLOUDFLARE_ZONE_ID="your-zone-id"
   ./scripts/purge_by_tag.py product-item-1
   ```
5. Verifikasi kembali request curl ketiga:
   ```bash
   curl -I https://your-domain.com/api/product
   # Verifikasi CF-Cache-Status: EXPIRED atau MISS (Tergantung implementasi SWR)
   ```

---

### 13. Exercises

#### Level Easy
- **Tugas**: Tambahkan konfigurasi Ruleset Cache Rule untuk mengabaikan parameter URL `fbclid` dan `gclid`, namun tetap mempertahankan query string fungsional seperti `?page=2` dan `?sort=desc`.
- **Kriteria Keberhasilan**: Request ke `/catalog?page=2&fbclid=XYZ` menghasilkan Cache Key yang identik dengan `/catalog?page=2`.

#### Level Medium
- **Tugas**: Tulis konfigurasi Terraform untuk mempartisi cache pada endpoint `/api/pricing` menggunakan Custom Header `x-user-tier` (dengan opsi nilai: `free`, `pro`, `enterprise`). Pastikan jika header tersebut tidak dikirimkan klien, nilai default fallback diterapkan di Cache Key.
- **Kriteria Keberhasilan**: Verifikasi melalui `curl` bahwa pengguna tier `free` dan `pro` mendapatkan data yang terisolasi sempurna pada URI yang sama.

#### Level Hard
- **Tugas**: Bangun sebuah Cloudflare Worker yang memotong (*intercept*) response dari API origin. Jika origin mengembalikan header `Vary: Accept-Encoding, User-Agent, X-Device`, worker harus memformat ulang dan menginjeksi header `Vary: Accept-Encoding` saja, serta secara otomatis menambahkan `Cache-Tag` berdasarkan pola URI segmen path ke-2 (`/articles/tech/cloud-computing` -> `Cache-Tag: articles, articles-tech`).
- **Kriteria Keberhasilan**: Hilangnya fragmentasi cache akibat `User-Agent`, serta terbentuknya tag hierarkis yang dapat divalidasi via header audit internal.

---

### 14. Challenges

#### Skenario Studi Kasus: "The Global Black Friday Invalidation Deadlock"
- **Latar Belakang**: Anda adalah Principal Platform Architect pada startup marketplace global decacorn. Arsitektur backend menggunakan sistem Microservices terdistribusi dengan total 4.000 worker containers. Pada pukul 00:00 saat kampanye dimulai, tim sales mengubah harga diskon global untuk 200.000 SKU secara simultan.
- **Masalah Kompleks**:
  1. Microservice katalog menerbitkan 200.000 pesan pembatalan ke RabbitMQ dalam waktu 10 detik.
  2. Worker pengeksekusi purge langsung melakukan hit ke REST API endpoint Cloudflare (`/purge_cache`) per produk. 
  3. Dalam 3 detik, Cloudflare API mengembalikan HTTP `429 Too Many Requests`. Proses purge terhenti, menghasilkan inkonsistensi harga parah: sebagian pengguna melihat harga diskon, sebagian melihat harga normal.
  4. Dalam kepanikan, engineer on-call mengeksekusi tombol "Purge Everything" melalui Cloudflare Dashboard. Seketika, 150.000 RPS menghantam origin gateway, database connection pool jenuh, dan seluruh platform down total.
- **Tantangan Anda**:
  Rancang arsitektur menyeluruh (*End-to-End Fault-Tolerant Cache Invalidation Architecture*) untuk mencegah hal ini terulang selamanya.
  - **Spesifikasi yang Harus Dijawab**:
    1. Bagaimana Anda merancang topologi `Cache-Tag` di level origin response agar 200.000 SKU dapat divalidasi hanya menggunakan maksimal 50 panggilan API Cloudflare?
    2. Bagaimana arsitektur *buffer/aggregation layer* sebelum menyentuh Cloudflare API untuk menghormati batasan API rate limits?
    3. Apa konfigurasi Ruleset Engine (stale-while-revalidate, tiered cache, origin shield) yang harus dikunci agar tombol "Purge Everything" tidak pernah dapat meruntuhkan database origin?
    4. Buat diagram arsitektur sistem pembatalan event-driven tersebut lengkap dengan fallback circuit breaker.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Soal)
1. **Apa fungsi utama dari Argo Tiered Cache dalam topologi Edge Cloudflare?**
   - A. Menghapus cache di edge browser klien secara paksa.
   - B. Mengonsolidasikan request MISS dari berbagai Lower-Tier PoP global ke Upper-Tier PoP sebelum menghubungi origin.
   - C. Menyimpan file HTML secara permanen di database PostgreSQL.
   - D. Mengubah protokol HTTP/1.1 menjadi HTTP/2 secara otomatis.
   *Kunci: B* — Mengurangi origin traffic dengan menjadikan Upper-Tier PoP sebagai regional origin shield.

2. **Manakah response header standar HTTP RFC 5861 yang mengizinkan edge menyajikan konten cache kadaluarsa secara non-blocking saat mengambil versi terbaru dari origin?**
   - A. `Cache-Control: stale-while-revalidate`
   - B. `CF-Cache-Status: EXPIRED`
   - C. `Pragma: no-cache`
   - D. `Age: 0`
   *Kunci: A* — RFC 5861 mendefinisikan direktif `stale-while-revalidate`.

3. **Berapa batas maksimal jumlah tag yang diizinkan dalam satu HTTP request pada pemanggilan Cloudflare API Purge by Tags?**
   - A. 1 tag
   - B. 30 tag
   - C. 500 tag
   - D. Tanpa batas
   *Kunci: B* — Cloudflare membatasi pemanggilan API purge hingga 30 tag per payload array.

4. **Secara default, parameter apakah yang termasuk dalam standar Cache Key Cloudflare jika fitur Custom Cache Key belum diaktifkan?**
   - A. Scheme, Host, Path, User-Agent
   - B. Host, Client IP, Cookies
   - C. Scheme, Host, Path, dan Query String lengkap
   - D. Path dan Authorization Header
   *Kunci: C* — Skema (`http`/`https`), Fully Qualified Domain Name (Host), URI Path, dan seluruh Query String.

5. **Apa indikasi nilai header `CF-Cache-Status: STALE` saat diperiksa melalui perintah cURL?**
   - A. Server origin mengirimkan error 500 Internal Server Error.
   - B. Konten yang disajikan adalah cache yang sudah expired, disajikan sementara proses background fetch ke origin sedang berlangsung.
   - C. Request ditolak oleh Cloudflare WAF.
   - D. Objek tersebut tersimpan di RAM Lower-Tier PoP.
   *Kunci: B* — Nilai `STALE` merepresentasikan siklus hidup `stale-while-revalidate` yang sedang berjalan.

---

#### Bagian 2: Intermediate (5 Soal)
6. **Sebuah platform media memiliki Cache Hit Ratio yang sangat rendah (15%) pada file statis gambar. Setelah diaudit, URL gambar memiliki bentuk: `/img/banner.jpg?user_session=abc123xyz`. Mengapa hal ini terjadi dan bagaimana solusinya?**
   - A. Cloudflare tidak bisa meng-cache format JPG; solusi konversi ke WebP.
   - B. Unique query string menyebabkan fragmentasi Cache Key; solusi buat Custom Cache Key untuk mengabaikan argumen `user_session`.
   - C. Origin mengembalikan status 304 Not Modified; solusi ubah ke 200 OK.
   - D. Disk SSD edge penuh; solusi aktifkan Tiered Cache.
   *Kunci: B* — Parameter `user_session` unik per klien membuat setiap request menghasilkan Hash Cache Key yang berbeda, menghancurkan CHR.

7. **Apa risiko arsitektural terbesar jika aplikasi backend Anda mengirimkan response header `Vary: User-Agent` ke Cloudflare Edge?**
   - A. Edge akan menolak melakukan kompresi Gzip/Brotli.
   - B. Cache terfragmentasi secara ekstrim karena ribuan variasi string User-Agent yang ada di internet, menyebabkan hampir setiap request berstatus MISS.
   - C. Cloudflare WAF akan otomatis memblokir browser non-standar.
   - D. Seluruh request dari perangkat mobile akan dialihkan ke HTTP 403 Forbidden.
   *Kunci: B* — Header `Vary: User-Agent` memecah namespace cache secara masif mengikuti setiap variasi browser/OS klien.

8. **Bagaimana mekanisme kerja Cache Reserve (berbasis R2) jika dibandingkan dengan Tiered Cache biasa?**
   - A. Cache Reserve menyimpan cache hanya pada browser klien menggunakan IndexedDB.
   - B. Cache Reserve mencegah eviksi LRU (Least Recently Used) aset edge ke persistent cloud storage sehingga tidak perlu fetch ulang ke origin customer.
   - C. Cache Reserve menggantikan fungsi web application firewall (WAF).
   - D. Cache Reserve hanya dapat meng-cache response API GraphQL.
   *Kunci: B* — Objek yang jarang diakses tidak langsung hilang terbuang dari edge, melainkan disimpan di layer persisten R2.

9. **Jika origin server sedang mengalami downtime total (misal network partition), direktif `Cache-Control` manakah yang menjamin Cloudflare tetap melayani aset lama kepada pengguna publik tanpa memunculkan error page 502/504?**
   - A. `s-maxage=0`
   - B. `stale-if-error=<seconds>`
   - C. `no-transform`
   - D. `must-revalidate`
   *Kunci: B* — `stale-if-error` memerintahkan edge untuk menyajikan stale cache jika origin mengembalikan status 5xx atau timeout.

10. **Mengapa pembersihan cache berbasis URL Prefix (`prefixes`) harus digunakan secara hati-hati pada deployment berskala masif?**
    - A. Prefix purge membutuhkan waktu 24 jam untuk propagasi.
    - B. Prefix purge menghapus seluruh cache hierarkis di bawah path tersebut secara agregat, yang dapat memicu lonjakan load ke origin jika path induk dipilih terlalu tinggi (contoh: `/api/`).
    - C. Cloudflare memungut biaya tambahan $1 per prefix purge.
    - D. Prefix purge secara otomatis menghapus database origin server.
    *Kunci: B* — Pembersihan prefix yang terlalu luas (misal `/static/` atau `/api/`) memiliki dampak merusak yang mirip dengan Purge All.

---

#### Bagian 3: Skenario Kasus Produksi (3 Soal)

11. **Skenario 1**:
    Sebuah aplikasi perbankan ingin meng-cache landing page promosi `/promo/credit-card`. Landing page ini menampilkan mata uang lokal sesuai lokasi geografis pengunjung (`IDR` untuk Indonesia, `SGD` untuk Singapura) dan layout berbeda untuk platform Mobile vs Desktop. Jika backend menyajikan konten yang berbeda pada URL tunggal yang sama:
    *Konfigurasi Custom Cache Key manakah yang paling aman dan optimal untuk diimplementasikan pada Cloudflare Ruleset Engine?*
    - A. Menambahkan seluruh string request header `User-Agent` dan cookie sesi ke dalam Cache Key.
    - B. Menambahkan `device_type` (Mobile/Desktop) dan `geo` (Country code) ke dalam `custom_key`, mengabaikan `User-Agent` mentah.
    - C. Mengaktifkan `Cache Everything` tanpa modifikasi Cache Key.
    - D. Mematikan seluruh caching pada rute `/promo/*`.
    *Kunci: B* — Opsi B mengisolasi konten secara presisi berdasarkan variasi yang benar-benar dibutuhkan tanpa menyebabkan fragmentasi ekstrim dari ribuan variasi User-Agent.

12. **Skenario 2**:
    Tim keamanan siber Anda melaporkan adanya kerentanan *Web Cache Deception*. Penyerang mengeksekusi request ke: `https://example.com/api/user/profile/non-existent.css`. Endpoint `/api/user/profile` mengembalikan data JSON profil privat user (termasuk email dan token), namun karena berakhiran `.css`, edge caching menyimpannya dan menyajikannya ke publik.
    *Langkah remediasi teknis paling tepat di sisi Cloudflare dan Origin adalah:*
    - A. Mengaktifkan fitur `Cache Deception Armor` di Cloudflare, memastikan origin mengirimkan header `X-Content-Type-Options: nosniff`, dan menetapkan `Cache-Control: private, no-store` pada endpoint data privat.
    - B. Menghapus ekstensi `.css` dari seluruh internet.
    - C. Melakukan purge URL `/api/user/profile` setiap 5 detik.
    - D. Mengubah domain perbankan menjadi domain internal intranet.
    *Kunci: A* — Ini adalah kombinasi mitigasi holistik: Cloudflare Cache Deception Armor memverifikasi konsistensi Content-Type, sementara origin secara eksplisit menyatakan data tersebut privat (`no-store`).

13. **Skenario 3**:
    Perusahaan Anda memiliki API katalog dengan SLA p99 latency < 50ms. Aset katalog di-cache dengan TTL 1 jam. Saat rilis katalog baru, CMS mengirimkan purge API tag `catalog-global`. Tepat setelah purge dikirimkan, p99 latency melonjak drastis ke 3.500ms dan origin CPU melonjak ke 98% selama 40 detik sebelum akhirnya normal kembali.
    *Pola arsitektur apa yang hilang dan harus diterapkan untuk memitigasi lonjakan latency tersebut?*
    - A. Mengubah metode request dari GET menjadi POST.
    - B. Mematikan fitur Tiered Cache.
    - C. Menerapkan pola *Cache Warming* terotomatisasi (pemanasan cache pasca-purge via synthetic workers) dikombinasikan dengan mengonfigurasi `stale-while-revalidate` pada level origin.
    - D. Menurunkan nilai TTL menjadi 1 detik.
    *Kunci: C* — Masalah tersebut diakibatkan oleh *Cold Cache Phenomenon* pasca invalidasi massal. Mengkombinasikan revalidasi asinkron dan cache pre-warming via automation workers mengeliminasi origin lock contention saat cache kosong.

---

### 16. Summary
1. **Multi-Tier Caching Architecture**: Integrasi antara Lower-Tier PoP, Smart Tiered Cache (Origin Shield), dan Cache Reserve (R2) mentransformasi CDN dari sekadar proxy statis menjadi lapisan komputasi dan penyimpanan persisten terdistribusi yang memangkas origin egress hingga >95%.
2. **Cache Key Determinism**: Mengontrol struktur hash Cache Key menggunakan Ruleset Engine adalah pertahanan utama terhadap cache fragmentation dan Web Cache Deception. Normalisasi query string dan isolasi header/device type mutlak diterapkan pada sistem skala besar.
3. **Surgical Invalidation**: Strategi pembatalan cache modern bergeser dari model primitif (Purge URL/Purge All) menuju **Event-Driven Surrogate Keys (`Cache-Tag`)**. Strategi ini memungkinkan pembersihan cache data terdistribusi secara instan (<150ms) dan presisi tanpa risiko *Cache Stampede*.
4. **Resilience Engineering**: Pemanfaatan direktif RFC 5861 (`stale-while-revalidate` dan `stale-if-error`) menjamin p99 latency tetap stabil dan memberikan toleransi kesalahan tinggi terhadap origin failure, mewujudkan arsitektur web performa tinggi berskala enterprise.