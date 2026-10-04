# Evaluasi Pembelajaran Bab 09: Global Traffic Steering, Load Balancing, & Argo

---

## I. Basic Questions (5 Soal)

1. **Bagaimana Cloudflare Global Load Balancer menyelesaikan masalah DNS Caching TTL yang umum terjadi pada DNS Load Balancer tradisional?**
   - A. Menurunkan TTL DNS menjadi 0 detik pada semua recursive resolver ISP global.
   - B. Menggunakan satu Anycast IP tetap; keputusan failover dan routing dilakukan di Edge Layer 7 Cloudflare secara instan tanpa perlu perubahan DNS record di sisi klien.
   - C. Mengirimkan sinyal BGP withdraw ke ISP lokal klien setiap kali origin mengalami kegagalan.
   - D. Mengharuskan klien menggunakan DNS resolver milik Cloudflare (1.1.1.1).

2. **Parameter apa pada Cloudflare Origin Pool yang menentukan batas minimum server yang harus sehat sebelum seluruh pool dinyatakan degradasi/down?**
   - A. `health_threshold`
   - B. `consecutive_fails`
   - C. `minimum_origins`
   - D. `origin_drain_limit`

3. **Apa fungsi utama dari Argo Smart Routing?**
   - A. Mengompresi file gambar secara otomatis di edge server menggunakan format WebP/AVIF.
   - B. Mengarahkan traffic dinamis melalui rute privat optimal di internal backbone Cloudflare untuk menghindari packet loss dan kemacetan internet publik.
   - C. Mengalihkan DNS queries ke recursive resolver tercepat di dunia.
   - D. Menggandakan HTTP requests ke beberapa origin server sekaligus untuk mencari respon tercepat.

4. **Bagaimana mekanisme Cookie-Based Session Affinity pada Cloudflare Load Balancer menjaga user tetap berada pada server yang sama?**
   - A. Menyimpan IP address klien di database memori Cloudflare Edge selama 24 jam.
   - B. Membaca header `Authorization: Bearer` dan melakukan hash token klien.
   - C. Menginjeksikan cookie HTTP terenkripsi berisi identifier origin backend ke browser klien pada response pertama.
   - D. Mengunci koneksi TCP socket klien agar tidak pernah tertutup (*infinite keep-alive*).

5. **Apa yang terjadi ketika fitur Session Drain aktif pada sebuah origin yang dinonaktifkan untuk pemeliharaan?**
   - A. Semua koneksi langsung diputus seketika dengan status code HTTP 503.
   - B. Origin langsung berhenti menerima semua request baru maupun request dengan session cookie lama.
   - C. Request baru tanpa session cookie dialihkan ke origin sehat lain, sementara user dengan session cookie valid diizinkan menyelesaikan transaksinya hingga drain duration habis.
   - D. Seluruh isi database origin backend disalin (*dump*) ke origin backend sekunder secara otomatis.

---

## II. Intermediate Questions (5 Soal)

1. **Apa perbedaan mendasar antara Dynamic Latency Steering dan Proximity Steering?**
   - A. Dynamic Latency Steering menggunakan data RTT aktual dari probe monitor ke Origin, sedangkan Proximity Steering menghitung jarak fisik koordinat GPS (latitude/longitude) antara Edge PoP Cloudflare dan Origin Server.
   - B. Dynamic Latency Steering hanya bekerja untuk traffic Layer 4, sedangkan Proximity Steering bekerja untuk Layer 7.
   - C. Proximity Steering membutuhkan data GPS dari perangkat mobile browser klien melalui HTML5 Geolocation API.
   - D. Dynamic Latency Steering tidak memerlukan Active Health Check Monitor, sedangkan Proximity Steering wajib.

2. **Sebuah Health Monitor L7 dikonfigurasi dengan `interval = 10`, `retries = 2`, `consecutive_fails = 3`. Berapa perkiraan durasi minimal origin mengalami down sebelum pool dinyatakan unhealthy oleh monitor?**
   - A. 10 detik.
   - B. 20 detik.
   - C. 30 detik.
   - D. 60 detik.

3. **Bagaimana Argo Tiered Caching membantu mengurangi Origin Egress Cost dan beban server backend?**
   - A. Menghapus seluruh cache di edge server setiap kali terjadi pembaruan data di backend.
   - B. Mengelompokkan Edge PoP Cloudflare ke dalam tingkatan Lower-tier dan Upper-tier, sehingga cache miss di Lower-tier PoP diteruskan ke Hub Regional (Upper-tier) sebelum meminta langsung ke Origin.
   - C. Mengalihkan semua request origin ke Cloudflare R2 secara otomatis tanpa konfigurasi storage backend.
   - D. Membatasi bandwidth origin backend menjadi maksimal 10 Mbps.

4. **Kondisi manakah yang menyebabkan Cloudflare Load Balancer mengalihkan traffic ke `fallback_pool`?**
   - A. Ketika salah satu origin di Primary Pool mengalami kenaikan latency sebesar 10ms.
   - B. Ketika seluruh origin pool default berada di bawah nilai `minimum_origins` yang sehat.
   - C. Ketika user mengakses website dari negara yang tidak terdaftar di Geo-Steering map.
   - D. Ketika sertifikat SSL origin server kedaluwarsa lebih dari 1 hari.

5. **Apa risiko teknis jika endpoint health check (`/healthz`) melakukan validasi koneksi database relasional yang kompleks di setiap probe interval?**
   - A. Cloudflare akan memblokir request monitor karena terdeteksi sebagai serangan DoS (HTTP 429).
   - B. Ribuan probe sintetis dari puluhan PoP regional dapat membebani database pool origin, memicu connection exhaustion dan false outage.
   - C. Response time monitor akan menjadi 0ms secara instan karena Cloudflare melakukan bypass cache.
   - D. Monitor Cloudflare akan otomatis mengonversi method GET menjadi POST.

---

## III. Scenario-Based Questions (3 Soal Kasus Nyata)

### Skenario 1: FinTech Multi-Cloud Data Sovereignty & Failover
Sebuah Bank Digital memiliki regulasi ketat: Data nasabah Indonesia (ID) harus selalu diproses di dalam negeri (Pool Jakarta - AWS). Namun, jika seluruh server AWS Jakarta padam total (*disaster condition*), demi ketersediaan layanan sistem diizinkan failover darurat ke Pool Singapura (GCP Singapore) dengan peringatan log audit. Bagaimana arsitektur aturan traffic steering harus dikonfigurasi di Cloudflare GLB?
- **Pilihan Solusi**:
  - A. Gunakan Steering Policy `Dynamic Latency` murni tanpa pool overriding.
  - B. Gunakan Steering Policy `Geo-Steering`, tetapkan mapping Region/Country `ID` ke `[Pool-Jakarta, Pool-Singapura]` secara berurutan, dan pastikan `minimum_origins` Pool Jakarta = 1.
  - C. Gunakan Steering Policy `Proximity` murni dengan menghapus metadata GPS Singapura.
  - D. Buat dua domain berbeda: `bank-id.example.com` dan `bank-sg.example.com` tanpa menggunakan Load Balancer.

### Skenario 2: Masalah "Pool Flapping" Akibat Misleading Response Body
Tim SRE mengeluhkan origin pool mereka beralih status antara UP dan DOWN setiap 30 detik. Monitor dikonfigurasi untuk mengecek path `/health`, `expected_codes = "200"`, dan `expected_body = "ALIVE"`. Aplikasi backend mengembalikan JSON: `{"status": "ALIVE_BUT_DEGRADED", "code": 200}` saat CPU di atas 80%, dan `{"status": "OK", "code": 200}` saat normal. Mengapa monitor mengalami status flapping yang membingungkan?
- **Pilihan Solusi**:
  - A. String `"ALIVE"` cocok dengan substring `"ALIVE_BUT_DEGRADED"`, sehingga monitor menganggap server tetap sehat saat CPU 80%, namun probe timeout gagal saat CPU melonjak ke 100%, menghasilkan osilasi antara UP dan DOWN.
  - B. Format JSON tidak didukung oleh Cloudflare L7 Health Monitor, hanya format teks ASCII mentah.
  - C. Nilai `expected_codes` harus berupa array integer `[200]`, bukan string `"200"`.
  - D. Monitor Cloudflare tidak mampu membaca response body yang panjangnya lebih dari 10 byte.

### Skenario 3: E-Commerce Session Breakout Saat Flash Sale
Saat promo jam 12 malam, platform e-commerce mencatat ribuan komplain transaksi gagal: keranjang belanja pengguna tiba-tiba kosong di tengah alur pembayaran. Arsitektur backend menggunakan session memori in-memory lokal (non-Redis). Load balancer menggunakan `dynamic_latency` steering tanpa Session Affinity. Apa akar masalah arsitektur tersebut dan solusinya?
- **Pilihan Solusi**:
  - A. Latensi jaringan berubah secara dinamis selama flash sale, menyebabkan request berikutnya dari klien yang sama dialihkan ke Origin Pool yang berbeda yang tidak memiliki data in-memory session keranjang tersebut; solusinya aktifkan Cookie-based Session Affinity.
  - B. Argo Smart Routing secara otomatis mengacak IP asal klien sehingga backend menganggap session hangus; solusinya nonaktifkan Argo.
  - C. Cloudflare WAF memblokir cookie transaksi belanja; solusinya matikan WAF Managed Rules.
  - D. Dynamic Latency steering mematikan koneksi HTTP/2; solusinya turunkan protokol ke HTTP/1.0.

---

## IV. Practical Chapter Challenge: Multi-Region Global Enterprise Ingress

### Target Arsitektur:
Anda diminta membangun arsitektur global routing enterprise untuk domain `service.corp.internal.net` menggunakan Terraform:
1. **Dua Pool Regional Aktif**:
   - `pool-apac`: 2 Origin Node (Singapura & Tokyo), pembobotan 70:30.
   - `pool-emea`: 2 Origin Node (Frankfurt & London), pembobotan 50:50.
2. **Satu Dedicated Fallback Pool**:
   - `pool-dr-maintenance`: 1 Origin menuju Cloudflare Pages static bucket.
3. **Health Monitoring Mutlak**:
   - Pengecekan interval 15 detik, timeout 3 detik, path `/api/v1/health`, verifikasi status code 200 dan body mengandung `"operational"`.
4. **Traffic Steering Policy**:
   - Default: Dynamic Latency Steering.
   - Khusus Pengguna Jerman (DE) dan Prancis (FR): Wajib dipaksa ke `pool-emea` (Data Sovereignty).
   - Pengguna Asia Tenggara (SEAS): Diprioritaskan ke `pool-apac`.
5. **Session Persistence**:
   - Tipe Cookie dengan nama `CORP_INGRESS_SESS`, TTL 2 jam, flag `Secure: Always`, `SameSite: Strict`, dan `drain_duration` 600 detik.
6. **Optimasi Transport**:
   - Argo Smart Routing dan Argo Tiered Caching diaktifkan.

### Format Pengumpulan:
Sertakan file konfigurasi `main.tf` lengkap dan valid yang memenuhi seluruh kriteria arsitektur di atas.