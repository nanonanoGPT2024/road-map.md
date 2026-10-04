# Modul 01: Edge Caching, Cache Rules, Tiered Cache, & Purging Strategies

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Mengonfigurasi dan memodifikasi **Cloudflare Custom Cache Keys** berbasis header, cookie, query string, dan device type menggunakan Cloudflare Rulesets Engine.
- Mengimplementasikan topologi **Tiered Cache** dan **Cache Reserve** berbasis persistent storage untuk menekan Origin Egress Cost hingga >85% dan mengeliminasi cache stampede (thundering herd).
- Mengonfigurasi mekanisme asinkron **RFC 5861 (`stale-while-revalidate` dan `stale-if-error`)** untuk menjamin *zero-latency spike* pada saat update cache dan mempertahankan *high availability* saat origin server mengalami degradasi/downtime.
- Menerapkan aturan **Bypass Cache on Cookie** secara aman untuk memisahkan sesi autentikasi, shopping cart, dan dynamic user context dari konten publik edge.
- Merancang dan mengeksekusi strategi **Instant Cache Purge** skala enterprise berbasis **Cache-Tags (Surrogate-Keys)** dan Prefixes melalui Cloudflare REST API v4 secara terprogram.
- Mengaktifkan dan memvalidasi pipeline **Early Hints (HTTP 103)** untuk mempercepat Critical Rendering Path (CRP) browser secara paralel sebelum respon HTTP 200 dihasilkan origin.

---

## 2. Prerequisite
Untuk memahami materi ini secara mendalam, peserta harus memiliki pemahaman terkait:
- **HTTP Semantics & Caching Specifications**: RFC 7234 (HTTP Caching), RFC 5861 (Stale-While-Revalidate), RFC 8297 (Early Hints).
- **Protokol Dasar**: Mekanisme handshake HTTP/2 & HTTP/3, serta lifecycle request/response header (`Cache-Control`, `ETag`, `Vary`, `Link`).
- **Infrastruktur & Automasi**: Dasar penggunaan Terraform (HCL), cURL/HTTPie, Python 3, serta pemahaman arsitektur Anycast CDN.

---

## 3. Concept
Cloudflare beroperasi sebagai jaringan Anycast global yang menyaring dan mengakselerasi trafik sebelum mencapai origin server. Secara default, CDN konvensional melakukan caching hanya berdasarkan URI (*Scheme + Host + Path + Query String*) dan ekstensi file statis. 

Dalam arsitektur edge modern, **Edge Caching** bukan sekadar menyimpan file CSS atau gambar, melainkan sebuah platform programmable proxy di mana:
1. **Cache Key Engine** membedah parameter konteks request (misal: header kompresi, geo-location, token state) menjadi hash unik penentu cache lookup.
2. **Tiered Cache** memposisikan PoP (Point of Presence) Cloudflare ke dalam hirarki berjenjang (Lower-Tier Edge PoP mengarah ke Upper-Tier Data Centers terdekat dengan origin) guna mengkonsolidasi request miss dan mencegah penumpukan koneksi balik ke origin.
3. **Cache Reserve** mengintegrasikan persistent object storage (berbasis R2) ke dalam pipeline caching, mengamankan objek yang jarang diakses (long-tail content) dari proses penggusuran LRU (Least Recently Used) reguler di memori/SSD edge.
4. **Surrogate-Key / Cache-Tags** memungkinkan pengelompokan ribuan resource yang terdistribusi di edge di bawah satu identifier logis, memungkinkan proses invalidasi data yang presisi dalam hitungan milidetik tanpa perlu melakukan `Purge Everything` yang merusak performa origin.

---

## 4. Why
Mengapa arsitektur caching edge ini mutlak dibutuhkan bagi operasional SRE dan Cloud Engineer?
- **Pengurangan Origin Latency & Egress Billing**: Biaya egress cloud provider publik (AWS, GCP, Azure) sangat tinggi ($0.08–$0.12 per GB). Mengoptimalkan Cache Hit Ratio (CHR) dari 70% ke 98% menggunakan Cache Keys kustom dan Tiered Cache memangkas biaya transfer data keluar hingga jutaan dolar per tahun.
- **Resiliensi Terhadap Traffic Spikes (Thundering Herd)**: Ketika ribuan user secara bersamaan meminta resource yang baru saja expired, arsitektur konvensional akan meneruskan ribuan request tersebut ke origin. Kombinasi `stale-while-revalidate` dan Tiered Cache memastikan hanya 1 sub-request yang divalidasi ke origin, sementara user lainnya menerima data stale secara instan.
- **Dekopling Dynamic Personalization vs Edge Performance**: Tanpa custom cache key dan conditional cookie bypass, aplikasi dynamic (e-commerce, SaaS) terpaksa menonaktifkan cache sepenuhnya (`Cache-Control: private, no-store`), membebani origin database untuk payload HTML yang sebenarnya 90% identik antar user.
- **Eliminasi TTFB dengan Early Hints (HTTP 103)**: Memungkinkan browser mengunduh stylesheet dan critical JS ketika origin server masih sibuk mengeksekusi business logic / SQL query, memangkas First Contentful Paint (FCP) hingga 30-50%.

---

## 5. What (Deep-Dive Teknis Lengkap)

### 5.1 Custom Cache Keys Deep-Dive
Secara default, Cache Key Cloudflare diformulasikan sebagai:
$$\text{Cache Key} = \text{Scheme} + \text{Host} + \text{Path} + \text{Query String}$$

Melalui Ruleset Engine (Cache Rules), Cache Key dapat didekonstruksi dan dikonfigurasi secara granuler:
- **Headers**: Menyertakan header tertentu (misal: `Accept-Language`, `X-Device-Type`) atau memeriksa keberadaannya (`presence`).
- **Cookies**: Menyertakan nilai cookie spesifik (misal: `currency=USD`) ke dalam key hash, atau mengabaikan session tracking cookies (`__ga`, `_fbp`) agar tidak menyebabkan fragmentasi cache.
- **Query String Sorting & Filtering**: Mengabaikan parameter tracking UTM (`utm_source`, `utm_medium`, `fbclid`) dan mengurutkan query string secara leksikografis (`/api?a=1&b=2` identik dengan `/api?b=2&a=1`).
- **Host & User Context**: Memodifikasi host header atau menyertakan context geo-ip (`cf.colo`, `cf.country`) untuk menyajikan konten lokal tanpa redirect.

### 5.2 Topologi Tiered Cache & Cache Reserve
Jika cache miss terjadi pada Edge PoP (Lower-Tier):
1. **Standard Architecture**: Lower-tier PoP langsung mengirimkan request ke Origin Server. Jika ada 300 PoP yang mengalami cache miss, origin menerima 300 koneksi bersamaan.
2. **Tiered Cache (Smart Routing)**:
   - Jaringan Cloudflare dibagi menjadi **Lower-Tier PoP** (lokasi edge dekat end-user) dan **Upper-Tier PoP** (pusat data Cloudflare skala besar yang paling dekat secara topologi latensi dengan origin).
   - Lower-tier PoP yang mengalami miss meneruskan request ke Upper-tier PoP.
   - Jika Upper-tier PoP menyimpan objek tersebut, request langsung dijawab. Jika tidak, hanya Upper-tier PoP yang menghubungi origin server.
3. **Cache Reserve**:
   - Jika resource dikeluarkan dari memori/SSD PoP lokal karena algoritma eviksi LRU (objek long-tail), Cache Reserve bertindak sebagai persistent secondary cache layer berbasis Cloudflare R2 storage sebelum fallback ke origin.

### 5.3 RFC 5861: Asynchronous Revalidation
- **`stale-while-revalidate=<seconds>`**:
  Menginstruksikan edge bahwa jika konten telah expired (melewati `max-age`), edge diizinkan untuk menyajikan konten kadaluarsa (*stale*) kepada client secara instan (0ms delay), sambil secara asinkron (background process) memicu subrequest ke origin server untuk mengambil salinan data terbaru.
- **`stale-if-error=<seconds>`**:
  Jika cache telah kadaluarsa dan origin server merespons dengan HTTP status 500, 502, 503, 504, atau network timeout, edge akan terus menyajikan konten stale kepada end-user selama durasi detik yang ditentukan, mengaburkan kegagalan infrastruktur backend.

### 5.4 Bypass Cache on Cookie
Fitur penting untuk dynamic site (misal: WordPress, Magento, atau custom headless SPA):
- Aturan cache default: Lakukan caching pada endpoint HTML (`/`, `/products/*`).
- Aturan Bypass: Jika request memuat cookie sesi (misal: `session_id`, `cart_id`, `logged_in=true`), Edge Cache dilewati sepenuhnya (*BYPASS*) dan request diteruskan ke origin. Jika cookie tersebut tidak ada, Edge menyajikan konten dari cache (*HIT*).

### 5.5 Instant Purge Strategies & Cache-Tags
Cloudflare mendukung tiga metode purge:
1. **Purge Everything**: Menghapus seluruh cache di semua data center global secara instan. *Sangat berbahaya di production* karena dapat memicu thundering herd yang merobohkan origin.
2. **Purge by URL / Prefix**: Menghapus URL spesifik (termasuk variasi parameter) atau seluruh prefix direktori (misal: `https://example.com/assets/*`).
3. **Purge by Cache-Tags (Surrogate-Keys)**:
   Origin server mengirimkan response header `Cache-Tag: product-1234, category-electronics, brand-sony`. Cloudflare mencatat tag tersebut ke index internal. Ketika stok produk 1234 berubah, CMS/backend mengirimkan payload API:
   ```json
   {"tags": ["product-1234"]}
   ```
   Seluruh variasi URL yang memiliki tag `product-1234` di seluruh PoP global langsung dinonaktifkan dalam waktu rata-rata $\le 150\text{ ms}$.

### 5.6 Early Hints (HTTP 103)
Early Hints memungkinkan edge mengirimkan respons header intermediate (status code `103 Early Hints`) kepada browser saat request diteruskan ke origin:
```http
HTTP/1.1 103 Early Hints
Link: </assets/app.css>; rel=preload; as=style
Link: </assets/app.js>; rel=preload; as=script
```
Browser dapat segera membuka koneksi TLS dan mulai mengunduh file CSS/JS critical selagi origin server masih memproses database query untuk merender payload HTML utama.

---

## 6. How
Implementasi caching modern di Cloudflare dilakukan melalui kombinasi:
1. **Origin Header Configuration**: Mengatur `Cache-Control`, `Surrogate-Control`, dan `Cache-Tag` secara benar di sisi aplikasi backend.
2. **Declarative Infrastructure as Code (Terraform)**: Mendefinisikan `cloudflare_ruleset` untuk Cache Rules, Tiered Cache configuration, dan custom Cache Keys.
3. **Application Event Triggers**: Menghubungkan event CI/CD pipeline atau ORM database updates (misal: hook save model) ke Cloudflare API v4 untuk melakukan surgical invalidation via Cache-Tags.

---

## 7. Analogy
Bayangkan sebuah **Restoran Internasional Multinasional**:
- **Origin Server**: Dapur pusat (*Central Kitchen*) tempat Master Chef memasak hidangan rumit dari bahan mentah. Memasak membutuhkan waktu 30 menit.
- **Edge PoP (Cache)**: Etalase display berpemanas di cabang restoran lokal.
- **Cache Key**: Label pesanan. Jika labelnya terlalu umum ("Burger"), semua orang mendapat burger yang sama. Jika label terlalu spesifik ("Burger dengan 3 biji wijen di sisi kiri"), dapur harus memasak ulang untuk setiap orang.
- **Tiered Cache**: Gudang regional. Jika cabang lokal kehabisan burger beku, mereka tidak menelpon pabrik pusat di luar negeri; mereka mengambilnya dari gudang regional di kota tersebut.
- **Stale-While-Revalidate**: Pelayan menyajikan display burger yang ada saat ini kepada pelanggan tanpa menunggu, sambil menekan tombol interkom agar koki segera memasak burger baru di etalase untuk pelanggan berikutnya.
- **Cache-Tag**: Kode barcode kategori pada etalase. Begitu ditemukan saus tomat batch X basi, staf cukup memindai tag "Batch-X" dan seluruh makanan dengan barcode tersebut disingkirkan serentak dari seluruh cabang dunia.

---

## 8. Diagram (ASCII)

```text
CLIENT (Browser)                 LOWER-TIER POP (Edge)              UPPER-TIER POP               ORIGIN SERVER
   |                                    |                                 |                            |
   |-- 1. GET /products/item-A -------->|                                 |                            |
   |   (Cookie: session=xyz)            |                                 |                            |
   |                                    |-- 2. Lookup Cache Key --------->|                            |
   |                                    |      [Key: item-A (Ignore UTM)] |                            |
   |                                    |                                 |                            |
   |                                    |=== [CACHE MISS] ================|                            |
   |                                    |                                 |                            |
   |                                    |-- 3. Check Upper-Tier --------->|                            |
   |                                    |                                 |-- 4. Lookup Cache Key ---->|
   |                                    |                                 |      [CACHE MISS]          |
   |<-- 5. HTTP 103 Early Hints --------|                                 |                            |
   |    (Link: </main.css>; preload)    |                                 |-- 6. Forward Request ----->|
   |                                    |                                 |                            |
   |    [Browser pre-fetches CSS]       |                                 |                            |-- 7. Query DB / Render
   |                                    |                                 |<-- 8. 200 OK + Cache-Tag --|
   |                                    |                                 |       Cache-Control:       |
   |                                    |                                 |       s-maxage=3600, SWR   |
   |                                    |<-- 9. Cache in Upper Tier ------|                            |
   |<-- 10. HTTP 200 OK (Cache HIT) ----|                                 |                            |
   |    (CF-Cache-Status: MISS)         |-- 11. Cache in Lower Tier       |                            |
   |                                            (Surrogate Index: Tags)   |                            |
   |                                                                                                   |
   |==================== NEXT IDENTICAL REQUEST (Within max-age) =====================================|
   |                                                                                                   |
   |-- 12. GET /products/item-A ------->|                                                              |
   |<-- 13. HTTP 200 OK (HIT) ----------| [Served in ~5ms from Lower Tier Memory]                      |
   |    (CF-Cache-Status: HIT)          |                                                              |
   |                                                                                                   |
   |==================== ASYNC PURGE EVENT VIA API ====================================================|
   |                                                                                                   |
   |                      API Client (Backend) ------------------------------------------------------->|
   |                      POST /zones/:id/purge_cache                                                  |
   |                      Payload: {"tags": ["tag-item-A"]}                                            |
   |                                           |                                                       |
   |                      Cloudflare Backbone Network Invalidation Broadcast                           |
   |                      Lower-Tier & Upper-Tier indices invalidated globally (< 150ms)               |
```

---

## 9. Simple Example
Konfigurasi response header dari origin server (Nginx) untuk mengontrol edge caching Cloudflare secara spesifik:

```nginx
# /etc/nginx/conf.d/api_caching.conf
location /api/catalog/ {
    proxy_pass http://catalog_backend;
    
    # Nonaktifkan caching di browser publik (0s), tapi cache di Cloudflare Edge selama 1 jam
    # Izinkan stale content disajikan hingga 10 menit saat revalidasi asinkron berlangsung
    # Sajikan stale jika origin 5xx error hingga 24 jam
    add_header Cache-Control "public, max-age=0, s-maxage=3600, stale-while-revalidate=600, stale-if-error=86400";
    
    # Lampirkan Cache-Tags untuk invalidasi terprogram
    add_header Cache-Tag "catalog, catalog-category-9, vendor-42";
    
    # Kirim instruksi Early Hints
    add_header Link "</static/catalog.css>; rel=preload; as=style" always;
}
```

---

## 10. Practical Example (Konfigurasi CLI / Terraform / Kode Hands-on)

Berikut adalah definisi infrastruktur skala produksi menggunakan Terraform Cloudflare Provider v4 untuk mengonfigurasi Tiered Cache, Cache Rules kustom dengan seleksi Cache Key, dan Bypass on Cookie.

```hcl
# main.tf
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.35.0"
    }
  }
}

variable "zone_id" {
  type        = string
  description = "Cloudflare Zone ID"
}

# 1. Enable Smart Tiered Caching (Topology Routing)
resource "cloudflare_tiered_cache" "tiered_caching" {
  zone_id    = var.zone_id
  cache_type = "smart" # Cloudflare automatically finds the optimal upper-tier data center
}

# 2. Cache Rules Configuration via Rulesets API
resource "cloudflare_ruleset" "cache_custom_rules" {
  zone_id     = var.zone_id
  name        = "Enterprise Edge Cache Optimization Ruleset"
  description = "Custom Cache Keys, SWR, and Dynamic Bypass on Cookie"
  kind        = "zone"
  phase       = "http_request_cache_settings"

  # Rule 1: Bypass Cache untuk User Terautentikasi atau Memiliki Shopping Cart
  rules {
    action      = "set_cache_settings"
    expression  = "(http.cookie contains \"session_id\") or (http.cookie contains \"cart_token\") or (http.request.uri.path starts_with \"/admin\")"
    description = "Bypass Edge Cache for Authenticated or Admin Traffic"
    enabled     = true

    action_parameters {
      cache = false
    }
  }

  # Rule 2: Caching Endpoint Dynamic Catalog dengan Custom Cache Key & Early Hints
  rules {
    action      = "set_cache_settings"
    expression  = "(http.request.uri.path starts_with \"/api/products/\") and not (http.cookie contains \"session_id\")"
    description = "Cache Product API with Advanced Custom Cache Key and SWR"
    enabled     = true

    action_parameters {
      cache = true
      
      # Edge Cache TTL & Browser TTL decoupling
      edge_ttl {
        mode    = "override_origin"
        default = 7200 # 2 Jam jika origin tidak mengirim s-maxage
        status_code_ttl {
          status_code = 200
          value       = 86400 # 24 Jam
        }
        status_code_ttl {
          status_code_range {
            from = 500
            to   = 599
          }
          value = 10 # Hindari caching error panjang
        }
      }

      browser_ttl {
        mode    = "override_origin"
        default = 300 # Browser hanya cache 5 menit
      }

      # Kustomisasi Cache Key: Normalisasi Query String dan Ignore Tracking
      cache_key {
        ignore_query_strings_order = true
        
        query_string {
          exclude = ["utm_*", "fbclid", "gclid", "_ga"]
        }
        
        headers {
          include = ["Accept-Encoding", "X-App-Version"]
          check_presence = ["Authorization"]
        }

        user {
          device_type = true
          geo         = false
          lang        = false
        }
      }

      # Layani konten stale selama background revalidation atau saat backend error
      serve_stale {
        disable_stale_while_updating = false
      }

      # Aktifkan HTTP 103 Early Hints untuk resource ini
      early_hints = true
    }
  }
}
```

---

## 11. Real World Example
Sebuah marketplace e-commerce multinasional mengalami lonjakan beban origin database setiap kali flash sale produk viral berlangsung pada URL `/p/flagship-smartphone`. Masalah yang terjadi:
1. Pemasang iklan menyertakan ratusan parameter query berbeda: `?utm_source=tiktok`, `?utm_campaign=sale&utm_source=google`, menghasilkan cache-key fragmentation. Setiap link baru memicu origin miss.
2. Setiap kali stock berkurang (stok berkurang setiap 2 detik), backend melakukan `Purge All`, mengakibatkan puluhan ribu user membobol database Postgres secara serentak (Cache Stampede).

**Solusi yang Diimplementasikan:**
1. **Cache Rules Custom Key**: Mengabaikan seluruh parameter `utm_*` dan mengurutkan query string. 200 variasi URL iklan kini jatuh pada 1 Cache Key yang sama.
2. **Surrogate-Keys (Cache-Tags)**: Halaman disuntik header `Cache-Tag: product-99, inventory-99, category-smartphones`.
3. **Stale-While-Revalidate**: Diatur `s-maxage=60, stale-while-revalidate=30`. Selama 30 detik masa update, 50.000 user yang mengakses halaman tetap menerima respons dalam 12ms dari edge PoP, sementara hanya 1 request yang dialirkan ke origin untuk memperbarui sisa stok.
4. **Targeted Purge via Webhook API**: Saat flash sale berakhir, backend mengirim event purge tag `product-99` secara atomik ke Cloudflare API. Origin database CPU load turun drastis dari 94% menjadi 11%, dan CHR naik dari 42% menjadi 97.8%.

---

## 12. Trade-offs

| Aspek / Solusi | Keuntungan (Pros) | Konsekuensi / Risiko (Cons) |
| :--- | :--- | :--- |
| **Aggressive Custom Cache Keys** | Menyatukan ribuan variasi URL menjadi 1 hit object; mengeliminasi duplikasi penyimpanan edge. | Resiko menyajikan konten yang salah jika ada parameter fungsional bisnis (misal: `currency=IDR`) yang tidak sengaja ter-exclude dari Cache Key. |
| **Tiered Cache (Smart)** | Mengurangi origin egress bandwidth hingga 80-90%; mencegah thundering herd langsung ke origin. | Menambahkan 1 network hop internal Cloudflare (Lower PoP $\to$ Upper PoP) pada saat Cache Miss awal ($\approx +10\text{--}30\text{ ms}$ pada first-fetch). |
| **Cache Reserve** | Menyimpan long-tail content secara persisten di storage tanpa terhapus eviksi LRU; zero origin request untuk static assets tua. | Menimbulkan biaya penyimpanan R2 (storage cost per GB/month dan read/write Class A/B request operation). |
| **Stale-While-Revalidate (SWR)** | Zero-latency untuk end-user; melindungi origin dari lonjakan traffic tiba-tiba. | Client mungkin menerima data yang terlambat beberapa detik/menit (*eventual consistency*), tidak cocok untuk data real-time transaksi finansial. |
| **Cache-Tag Purging** | Invalidation sangat presisi, aman, berskala enterprise tanpa cold-cache penalty. | Membutuhkan arsitektur aplikasi backend yang matang untuk melacak relasi entitas ke HTTP headers (`Cache-Tag` length limit maks 16KB per request). |

---

## 13. When To Use
- **Arsitektur E-Commerce / Content-Heavy Platforms**: Katalog produk, artikel berita, dokumentasi teknis, landing page kampanye marketing.
- **REST / GraphQL Read-Only APIs**: Endpoint publik seperti `/api/v1/weather`, `/api/v1/market-rates`, `/api/v1/articles` dengan TTL singkat dan SWR.
- **High-traffic Distributed Applications**: Layanan global di mana user tersebar di berbagai belahan dunia dan origin terpusat di satu AWS region tunggal.
- **Microfrontends & Headless CMS**: Menggunakan Cache-Tags untuk invalidasi komponen UI secara granular.

---

## 14. When NOT To Use
- **Payload Data Keuangan / Transaksi Saham**: Data dengan toleransi inkonsistensi nol detik (*hard real-time*). Penggunaan SWR berisiko menampilkan saldo atau harga yang salah.
- **Endpoints yang Memiliki Logika State Mutlak**: `/api/v1/checkout`, `/api/v1/transfer`, `/api/v1/auth/login`. Wajib diset `Cache-Control: no-store, no-cache, private`.
- **Intranet / Internal Tools dengan IP Whitelisting Sempit**: Menggunakan caching publik tanpa Bypass on Cookie dapat menyebabkan data pribadi pegawai bocor (*data leakage across tenants*).

---

## 15. Common Mistakes
1. **Cache Poisoning via Unkeyed Headers/Cookies**: Mengizinkan origin melayani output berbeda berdasarkan header `X-Host` atau cookie tertentu, tetapi tidak menyertakan header/cookie tersebut ke dalam Cloudflare Custom Cache Key. Akibatnya, konten user A tersimpan di cache dan disajikan ke user B.
2. **Purge Everything di Production**: Melakukan full purge saat deployment aplikasi. Ini memicu *origin meltdown* akibat ribuan request masuk secara serentak (Cache Stampede).
3. **Mengabaikan Header `Vary`**: Mengembalikan response terkompresi `gzip` atau `br` tanpa mengelola `Vary: Accept-Encoding`, menyebabkan client yang tidak mendukung Brotli menerima payload biner rusak. (Cloudflare menangani gzip/brotli secara otomatis jika tidak di-override sembarangan).
4. **Menyimpan Set-Cookie Header di Edge Cache**: Origin server mengembalikan `Set-Cookie: session_id=abc` bersamaan dengan `Cache-Control: public, s-maxage=3600`. Jika Cloudflare meng-cache response ini, semua pengunjung berikutnya akan login sebagai user `session_id=abc`.
5. **Overriding Browser TTL Terlalu Panjang**: Menyetel `browser_ttl` selama 30 hari. Jika terjadi kesalahan data, Cloudflare Cache Purge **tidak bisa menghapus cache yang sudah tersimpan di browser client lokal**.

---

## 16. Best Practices
1. **Pisahkan Edge TTL vs Browser TTL**:
   Gunakan `s-maxage` (untuk CDN Edge) berdurasi panjang (misal: 7 hari) dan `max-age` (untuk browser end-user) berdurasi sangat pendek (misal: 0 atau 60 detik). Ini memberikan fleksibilitas penuh: jika data salah, lakukan purge di Cloudflare, dan user akan segera mendapatkan data segar dalam $\le 60$ detik.
2. **Kombinasikan Tiered Cache dengan Argo Smart Routing**:
   Mengaktifkan Smart Tiered Cache secara drastis mengurangi koneksi cross-continental dari edge langsung ke origin.
3. **Standarisasi Penggunaan Cache-Tags**:
   Format tag secara terstruktur dengan prefix domain: `entity:id` (contoh: `post:901`, `author:12`, `org:alpha`). Batasi total tag per response di bawah 60 tag agar tidak melampaui limit ukuran header HTTP.
4. **Implementasikan Circuit-Breaker dengan `stale-if-error`**:
   Selalu sematkan `stale-if-error=86400` pada respon katalog statis/semi-dinamis untuk memastikan CDN tetap menyajikan website fungsional meski origin server mati total selama 24 jam.
5. **Sanitasi Header Origin**:
   Pastikan origin menghapus header `Set-Cookie` pada seluruh request yang dideklarasikan sebagai `public` atau dapat di-cache.

---

## 17. Troubleshooting

| Gejala Masalah | Investigasi Teknis | Solusi / Remediasi |
| :--- | :--- | :--- |
| **Response selalu `CF-Cache-Status: DYNAMIC`** | Periksa apakah ada Cache Rule aktif yang cocok dengan path tersebut. Cek apakah origin mengirimkan header `Cache-Control: private`, `no-store`, atau header `Set-Cookie`. | Tambahkan Cache Rule eksplisit: `Eligible for Cache`. Hilangkan `Set-Cookie` dari origin untuk endpoint publik. |
| **Response selalu `CF-Cache-Status: MISS` (Tidak pernah HIT)** | Evaluasi header `Cache-Control: max-age=0` tanpa `s-maxage`. Periksa apakah Cache Key menyertakan parameter unik (misal: dynamic query string atau session cookie acak). | Normalisasikan Cache Key di Cache Rules untuk mengabaikan query param dinamis yang tidak relevan. Konfigurasi `s-maxage` > 0. |
| **Data stale tidak pernah ter-update setelah Purge** | Periksa response header `Age` dan `CF-Cache-Status`. Jika client melompati Cloudflare (akses direct IP) atau browser local cache yang meng-hold (`max-age=31536000`). | Pastikan pengujian dilakukan via cURL dengan `-H "Cache-Control: no-cache"` untuk bypass browser local cache. Pastikan API Purge Tag mengembalikan `{"success": true}`. |
| **Early Hints (103) tidak muncul di client** | Verifikasi apakah client melakukan negosiasi koneksi via HTTP/2 atau HTTP/3. HTTP 103 tidak didukung dan diabaikan pada HTTP/1.1 standar. | Pastikan protokol browser adalah H2/H3. Validasi cURL menggunakan flag `--http2` atau `--http3`. Pastikan origin mengirimkan header `Link` dengan rel preload yang valid. |
| **User A melihat data profil User B** | Terjadi **Cache Poisoning**! Cek apakah path private (seperti `/me`, `/account`) ter-cache di Edge akibat wildcard rule. | Segera eksekusi Purge Everything! Pasang rule `Bypass Cache` prioritas tertinggi (Priority 1) untuk pattern URI `/account/*` dan cek cookie `session`. |

---

## 18. Exercise
1. **Analisis Header Cache**: Jalankan perintah cURL berikut terhadap domain target Anda dan interpretasikan output status cache-nya:
   ```bash
   curl -svo /dev/null https://example.com/api/v1/products -H "Accept-Encoding: gzip"
   ```
   *Identifikasi:* Nilai header `CF-Cache-Status`, `Age`, `Cache-Control`, dan `CF-Ray`.
2. **Simulasi Query String Sorting**:
   Kirimkan dua request berurutan menggunakan query string yang dibolak-balik:
   - Request 1: `GET /catalog?sort=asc&page=2`
   - Request 2: `GET /catalog?page=2&sort=asc`
   *Tugas:* Konfigurasikan Cloudflare Cache Rules agar request kedua menghasilkan status `CF-Cache-Status: HIT`.

---

## 19. Challenge
Rancang arsitektur caching untuk aplikasi penerbitan media berita dengan spesifikasi berikut:
- Homepage (`/`) menerima 50.000 RPS.
- Editor memperbarui berita breaking news sewaktu-waktu dan perubahan harus live di seluruh dunia dalam waktu kurang dari 5 detik.
- User biasa mendapatkan konten umum, sedangkan user berbayar (memiliki cookie `subscriber_tier=gold`) mendapatkan artikel tanpa banner iklan.
- Buat aturan declarative Terraform (`cloudflare_ruleset`) yang memisahkan cache key untuk user berlangganan vs reguler, mengaktifkan Smart Tiered Cache, dan menyiapkan integrasi API purge berbasis `Cache-Tag: article-{id}`.

---

## 20. Summary
- **Edge Caching Modern** adalah lapisan komputasi pintar di jaringan Anycast, bukan sekadar penampung file statis.
- **Custom Cache Keys** memungkinkan kontrol presisi atas variasi konten, mencegah fragmentasi cache akibat tracking query parameter, dan memfasilitasi segmentasi konten multi-tenant/multi-device.
- **Tiered Cache** dan **Cache Reserve** secara signifikan mereduksi beban network hop ke origin, meminimalisir biaya egress server, dan mencegah thundering herd problem.
- **RFC 5861 (`stale-while-revalidate`)** menjamin pengalaman pengguna dengan latency mendekati 0ms dengan mendelegasikan pembaruan cache ke worker background di edge.
- **Cache-Tag Surrogate Invalidation** adalah standar de-facto enterprise untuk invalidasi instan skala jutaan resource secara real-time melalui REST API v4.

---