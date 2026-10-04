# Bab 03: Evaluasi Mandiri & Praktikal Challenge

## 1. Basic Questions (5 Soal)

### Soal 1
Apa perbedaan mendasar antara direktif `max-age` dan `s-maxage` pada header `Cache-Control` dalam konteks arsitektur Cloudflare CDN?
- A. `max-age` berlaku untuk proxy/CDN edge, sedangkan `s-maxage` berlaku untuk browser klien.
- B. `s-maxage` ditujukan khusus untuk public shared cache (seperti Cloudflare Edge), meng-override `max-age` yang diterapkan untuk browser private cache.
- C. `s-maxage` mengabaikan seluruh instruksi purge yang dikirim via API.
- D. `max-age` hanya berlaku untuk HTTPS, sedangkan `s-maxage` untuk protokol HTTP biasa.

**Kunci Jawaban:** **B**
*Penjelasan:* Menurut RFC 7234, direktif `s-maxage` (shared max-age) diutamakan dan meng-override nilai `max-age` pada shared proxy/CDN cache seperti Cloudflare. Hal ini memungkinkan engineer menetapkan umur simpan panjang di Edge CDN (misal: `s-maxage=86400`) sekaligus menginstruksikan browser lokal user untuk tidak menyimpan cache terlalu lama (misal: `max-age=60`).

---

### Soal 2
Jika sebuah request menghasilkan response header `CF-Cache-Status: STALE`, apa yang sebenarnya terjadi di balik layar jaringan Cloudflare?
- A. Origin server mengembalikan error 404 Not Found.
- B. Konten di edge telah melewati batas waktu kadaluarsa (expired), namun disajikan ke klien sesuai mekanisme `stale-while-revalidate` selagi proses background fetch ke origin berlangsung.
- C. Request dibatalkan oleh firewall Cloudflare karena terdeteksi sebagai bot.
- D. Konten diambil dari Tiered Cache upper PoP, bukan local PoP.

**Kunci Jawaban:** **B**
*Penjelasan:* Status `STALE` mengindikasikan bahwa objek cache sudah kadaluarsa berdasarkan TTL, namun edge tetap menyajikannya ke user secara instan karena ada direktif RFC 5861 `stale-while-revalidate`, sementara Cloudflare mengirim request asinkron ke backend untuk meng-update konten tersebut.

---

### Soal 3
Metode Cloudflare Purge manakah yang **paling berisiko** menyebabkan lonjakan traffic masif ke origin server (*thundering herd / cache stampede*) jika dieksekusi pada jam sibuk traffic produksi?
- A. Purge by Single URL
- B. Purge by Cache-Tags
- C. Purge Everything
- D. Purge by Prefix

**Kunci Jawaban:** **C**
*Penjelasan:* `Purge Everything` menghapus seluruh entri cache dari seluruh PoP Cloudflare di seluruh dunia secara global. Ini menyebabkan Cache Hit Ratio (CHR) anjlok seketika menjadi 0%, memaksa 100% traffic pengguna langsung membebani origin server.

---

### Soal 4
Bagaimana mekanisme kerja **Early Hints (HTTP status 103)** dalam mempercepat rendering halaman web di browser?
- A. Mengirimkan seluruh file HTML sebelum database query selesai.
- B. Mengirimkan response header perantara berisi relasi `Link: </style.css>; rel=preload` sebelum respons final (HTTP 200) selesai diproses oleh origin backend.
- C. Mengompresi gambar di edge menggunakan format AVIF secara otomatis.
- D. Mengubah seluruh request POST menjadi GET agar dapat disimpan di edge cache.

**Kunci Jawaban:** **B**
*Penjelasan:* HTTP 103 Early Hints memungkinkan CDN mengirimkan instruksi preload aset-aset kritis (CSS/JS) kepada browser klien di awal koneksi ketika backend origin masih sibuk memproses query atau komputasi respons HTTP 200.

---

### Soal 5
Pada konfigurasi default Cloudflare, parameter URL manakah di bawah ini yang secara default menghasilkan **dua Cache Key yang berbeda** (kecuali dinormalisasi menggunakan Cache Rules)?
- A. Request `https://example.com/item?utm_source=fb` dan `https://example.com/item`
- B. Request `https://example.com/item` (dengan browser Chrome) dan `https://example.com/item` (dengan browser Firefox)
- C. Request dengan header `Accept-Language: id` dan `Accept-Language: en` pada URL statis murni tanpa Vary header.
- D. Request HTTP/1.1 vs HTTP/2 untuk URL yang sama persis.

**Kunci Jawaban:** **A**
*Penjelasan:* Secara default, Cloudflare menyertakan Query String lengkap ke dalam Cache Key default. Maka, keberadaan parameter pelacak seperti `utm_source=fb` akan dianggap sebagai resource yang berbeda dari URL polos tanpa query string, memicu cache miss jika tidak dinormalisasi via Cache Rules.

---

## 2. Intermediate Questions (5 Soal)

### Soal 6
Dalam implementasi **Smart Tiered Cache**, apa yang dilakukan oleh Lower-Tier PoP ketika menerima request yang mengalami cache miss lokal?
- A. Langsung mengirimkan request ke Origin Server publik.
- B. Meneruskan request ke Upper-Tier PoP yang secara topologi latensi berada paling dekat dan optimal dengan Origin Server.
- C. Mengirimkan error HTTP 504 Gateway Timeout ke user.
- D. Menggandakan request ke seluruh data center tetangga secara multicast.

**Kunci Jawaban:** **B**
*Penjelasan:* Smart Tiered Cache menggunakan kecerdasan telemetri routing Cloudflare Argo untuk memilih Upper-Tier PoP terbaik yang bertindak sebagai gerbang konsolidator cache miss sebelum request tersebut diteruskan ke Origin Server.

---

### Soal 7
Anda ingin mengonfigurasi fitur **Bypass Cache on Cookie** untuk aplikasi toko online. Parameter ekspresi Ruleset Engine manakah yang paling tepat untuk memastikan user yang belum login tetap mendapatkan Edge Cache, sementara user dengan sesi belanja bypass ke origin?
- A. `http.cookie eq ""`
- B. `not (http.cookie contains "session_token" or http.cookie contains "cart_id")`
- C. `(http.cookie contains "session_token") or (http.cookie contains "cart_id")` dengan aksi `cache = false`
- D. `http.request.method eq "POST"`

**Kunci Jawaban:** **C**
*Penjelasan:* Dalam Cloudflare Ruleset Engine pada fase `http_request_cache_settings`, untuk mem-bypass cache bagi user yang terautentikasi atau memiliki keranjang belanja, Anda mendeteksi keberadaan cookie tersebut (`contains`) lalu menyetel parameter aksi `cache = false` (Bypass).

---

### Soal 8
Sebuah backend API mengembalikan header response berikut:
`Cache-Control: public, s-maxage=3600, stale-if-error=1800`
Jika origin server tiba-tiba mati total (HTTP 500) pada menit ke-70 setelah objek pertama kali di-cache, apa yang akan dialami oleh klien yang meminta objek tersebut ke edge Cloudflare?
- A. Klien langsung menerima error HTTP 500 Bad Gateway.
- B. Klien menerima salinan konten cache kadaluarsa (stale) dengan status HTTP 200.
- C. Cloudflare mengembalikan HTTP 521 Origin Down secara instan.
- D. Klien dialihkan secara otomatis ke halaman Cloudflare Challenge Captcha.

**Kunci Jawaban:** **B**
*Penjelasan:* Objek telah expired karena melewati `s-maxage=3600` (60 menit), namun berada dalam rentang `stale-if-error=1800` (toleransi stale 30 menit tambahan jika backend error). Karena error terjadi pada menit ke-70 ($70 \le 60 + 30$), Cloudflare edge akan menyajikan konten stale kepada user dan menyembunyikan downtime origin.

---

### Soal 9
Kapan teknologi **Cache Reserve** paling efektif diaktifkan dibandingkan hanya bergantung pada Edge Cache standar?
- A. Ketika situs Anda hanya memiliki 5 halaman statis dengan traffic 100.000 RPS.
- B. Ketika website memiliki katalog aset masif (long-tail content) berukuran puluhan terabyte yang jarang diakses berulang tiap menit sehingga sering terdepak dari memori/SSD edge PoP akibat algoritma LRU.
- C. Ketika backend API mengharuskan database ACID transaction real-time.
- D. Ketika seluruh file di-hosting langsung di Cloudflare Pages.

**Kunci Jawaban:** **B**
*Penjelasan:* Edge PoP mengelola ruang disk/RAM terbatas menggunakan algoritma eviksi LRU (Least Recently Used). Konten long-tail (misal arsip gambar lama, rekaman pdf lama) akan cepat terhapus jika jarang diakses. Cache Reserve menyimpannya di persistent storage layer (Cloudflare R2) sehingga tidak pernah hilang terdepak LRU dan origin terbebas dari egress traffic.

---

### Soal 10
Batas teknis (limitasi) apakah yang harus diperhatikan oleh arsitek sistem saat merancang invalidasi cache menggunakan **Cache-Tags** di Cloudflare Enterprise?
- A. Cache-Tags hanya dapat dibuat maksimal 1 buah per website.
- B. Setiap response header `Cache-Tag` dibatasi panjang maksimalnya (umumnya 16 KB total) dan setiap tag dibatasi panjang karakter serta tidak boleh memuat karakter whitespace.
- C. Cache-Tags hanya bekerja untuk request method POST.
- D. Proses invalidasi Cache-Tags memakan waktu hingga 24 jam untuk propagasi global.

**Kunci Jawaban:** **B**
*Penjelasan:* Cloudflare menetapkan batas ukuran akumulatif header `Cache-Tag` sebesar 16 KB per HTTP response, dengan limit karakter individual per tag (maksimal 1.024 karakter dan dilarang mengandung spasi koma). Invalidation propagasinya berjalan instan ($\le 150\text{ ms}$).

---

## 3. Scenario-Based Questions (3 Soal Kasus Nyata Industri)

### Skenario 1: The Accidental Identity Leak (Cache Poisoning)
**Konteks Masalah:**
Sebuah platform perbankan digital meluncurkan API profil nasabah pada path `/api/v1/user/summary`. API ini menggunakan token autentikasi pada cookie `auth_session`. Developer mengeluhkan bahwa nasabah bernama "Budi" tiba-tiba melihat data saldo dan nama nasabah "Siti" saat membuka aplikasi. Setelah ditelusuri pada header response, ditemukan header:
`CF-Cache-Status: HIT`
`Cache-Control: public, max-age=300`

**Pertanyaan Kasus:**
1. Bedah secara mendalam akar penyebab teknis (*root cause*) dari insiden kebocoran data ini!
2. Tindakan darurat (*emergency response*) apa yang wajib dieksekusi dalam kurun 5 menit pertama?
3. Rancang konfigurasi pencegahan permanen menggunakan Cloudflare Cache Rules & Origin Header Best Practice!

**Panduan Jawaban Solutif:**
1. **Root Cause**: Backend API keliru mengirimkan header `Cache-Control: public` pada endpoint terproteksi identitas user, dan tidak ada aturan Cache Rule di edge yang mem-bypass cache untuk cookie `auth_session`. Ketika Siti membuka profil, Cloudflare menganggap payload tersebut sebagai konten publik statis dan menyimpannya di Edge. Saat Budi mengakses URL yang sama, Cloudflare langsung menyajikan cache milik Siti.
2. **Emergency Response**:
   - Segera eksekusi API Purge Everything atau purge spesifik URL `/api/v1/user/summary`.
   - Pasang WAF / Transform Rule darurat untuk menimpa response header menjadi: `Cache-Control: no-store, no-cache, private, must-revalidate` untuk path `/api/v1/user/*`.
3. **Pencegahan Permanen**:
   - Di Backend: Pastikan seluruh authenticated endpoint menyuntikkan `Cache-Control: no-store, private` dan strip `s-maxage`.
   - Di Cloudflare Ruleset Engine: Tambahkan Rule dengan Prioritas 1:
     `Expression: (http.request.uri.path starts_with "/api/v1/user/") or (http.cookie contains "auth_session")`
     `Action: Set Cache Settings -> Bypass Cache (cache = false)`.

---

### Skenario 2: Cache Key Fragmentation Collapse on Flash Sale
**Konteks Masalah:**
Sebuah portal retail menggelar event diskon 11.11. Tim marketing menyebarkan kampanye melalui Google Ads, Facebook, TikTok, dan Newsletter dengan ratusan UTM query string unik (contoh: `/sale?utm_source=fb&utm_medium=cpc&utm_campaign=elektronik&aff_id=987123`). Akibatnya, server backend origin mengalami CPU 100% dan down selama 45 menit, meskipun Cloudflare telah dipasang di depan situs. Tim infra melihat metrik `CF-Cache-Status` menunjukkan 88% `MISS`.

**Pertanyaan Kasus:**
1. Mengapa keberadaan parameter UTM tersebut melumpuhkan Edge Caching Cloudflare?
2. Bagaimana cara merekayasa Custom Cache Key pada Cloudflare Ruleset Engine untuk memulihkan Cache Hit Ratio ke angka $\ge 95\%$ tanpa merusak fungsionalitas analytics tim marketing di sisi client-side browser?

**Panduan Jawaban Solutif:**
1. **Analisis Masalah**: Cloudflare secara default memperlakukan seluruh string query URL sebagai bagian penentu keunikan Cache Key. Karena setiap iklan dan afiliasi memiliki parameter UTM dan identifier acak (`aff_id`), satu halaman produk `/sale` terfragmentasi menjadi puluhan ribu variasi unik di mata cache engine. Masing-masing variasi memicu Cache Miss pertama kali dibuka, membanjiri origin secara serentak.
2. **Solusi Arsitektur**:
   Konfigurasikan **Custom Cache Key** via Cloudflare Cache Rules:
   - Aktifkan `ignore_query_strings_order = true`.
   - Pada blok `query_string`, konfigurasikan `exclude`:
     `exclude = ["utm_*", "fbclid", "gclid", "aff_id", "_ga*"]`
   - Dengan konfigurasi ini, Cloudflare Edge hanya menggunakan Path `/sale` untuk meng-lookup objek di cache memory. Semua user disajikan objek HTML yang sama secara instan (Cache HIT), sementara browser user tetap membaca parameter query UTM di URL bar melalui JavaScript analytics (Google Analytics/Pixel) tanpa gangguan.

---

### Skenario 3: Broken News & The Stale Purge Cascade
**Konteks Masalah:**
Portal berita nasional menggunakan arsitektur Headless CMS dengan origin Nginx. Berita divalidasi menggunakan sistem Cache-Tag Cloudflare. Ketika ada artikel salah ketik (*misleading headline*), tim redaksi mengklik tombol "Revisi" di CMS. Backend memicu API Purge Cloudflare:
`POST https://api.cloudflare.com/client/v4/zones/{zone_id}/purge_cache` dengan payload `{"tags": ["article-4091"]}`.
Namun, pembaca di lapangan melaporkan bahwa judul salah tersebut masih terlihat selama lebih dari 30 menit di perangkat mobile mereka, padahal API Purge mengembalikan response `{"success": true}`.

**Pertanyaan Kasus:**
1. Faktor-faktor apa saja yang menyebabkan browser user tetap menampilkan konten lama meskipun Edge Cache Cloudflare telah sukses di-purge?
2. Langkah audit apa yang harus dilakukan pada HTTP response headers untuk membuktikan sumber masalahnya?
3. Bagaimana formula header `Cache-Control` yang benar untuk memadukan Edge Purge instan dengan proteksi browser cache?

**Panduan Jawaban Solutif:**
1. **Analisis Penyebab**:
   - Kemungkinan terbesar: Origin server menyetel header `Cache-Control: max-age=1800` (atau lebih tinggi) tanpa membedakan browser TTL dan edge TTL (`s-maxage`). Cloudflare berhasil membersihkan cache di PoP edge miliknya, namun browser lokal milik pengguna telah menyimpan halaman tersebut di hard drive/RAM browser user selama 30 menit. Cloudflare API Purge **tidak memiliki kemampuan mengotak-atik local cache browser user**.
   - Kemungkinan kedua: Service Worker aplikasi web mobile melakukan caching runtime offline secara agresif.
2. **Langkah Audit**:
   - Lakukan inspeksi cURL dengan flag penonaktifan cache lokal:
     `curl -I https://berita.com/article-4091 -H "Pragma: no-cache"`
   - Evaluasi nilai header `Cache-Control`, `Age`, dan `CF-Cache-Status`. Jika pada request cURL judul sudah terupdate dan `CF-Cache-Status: MISS/EXPIRED`, namun di browser Chrome user judul masih lama, maka masalah definitif berada di Local Browser Cache (`max-age`).
3. **Formula Header yang Benar**:
   Origin Nginx harus memisahkan hak simpan Browser vs Edge:
   ```nginx
   # Browser tidak boleh menyimpan cache lokal (atau maks 10-60 detik)
   # Cloudflare Edge diizinkan menyimpan cache selama 7 hari
   # SWR diaktifkan untuk absorpsi lonjakan traffic
   add_header Cache-Control "public, max-age=0, s-maxage=604800, stale-while-revalidate=60";
   add_header Cache-Tag "article-4091, category-politik";
   ```

---

## 4. Practical Chapter Challenge: E-Commerce Resilient Edge Architecture

### Objektif
Rancang dan validasi arsitektur edge caching terpadu untuk platform retail global menggunakan Terraform dan automasi skrip invalidasi.

### Spesifikasi Kebutuhan:
1. **Topologi Tiered Cache**:
   - Wajib mengaktifkan Smart Tiered Cache di Cloudflare Zone target.
2. **Cache Rules Definition (HCL)**:
   - **Path `/static/*`**: Edge TTL 30 hari, Browser TTL 30 hari, Cache Key murni URL tanpa query param.
   - **Path `/products/*`**: Edge TTL 12 jam, Browser TTL 0 detik, Custom Cache Key (abaikan tracking params `utm_*`, normalisasikan urutan query string, pisahkan cache berdasarkan device type: mobile vs desktop).
   - **Bypass Rule**: Jika cookie `app_session` atau `cart_items` terdeteksi, bypass cache secara mutlak.
3. **RFC 5861 Resilience**:
   - Konfigurasi `serve_stale` untuk menyajikan konten stale jika origin mati atau sedang revalidasi.
4. **Verifikasi Automasi Purge**:
   - Buat skrip python mandiri yang bertindak sebagai worker origin backend untuk memancarkan tag purge ke API Cloudflare dan memverifikasi response latency invalidasi.

---