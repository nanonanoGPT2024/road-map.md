# EVALUASI BAB 02: Edge Computing, DNS, & Jaringan Distribusi

Dokumen evaluasi ini berisi ringkasan materi, kuis pemahaman, dan tantangan perancangan arsitektur edge untuk menguji kesiapan Anda sebelum masuk ke **BAB 03: Traffic Management, Load Balancing, & Gateway**.

---

## 📌 Chapter Summary (Rangkuman BAB 02)

Sepanjang BAB 02, Anda telah mempelajari lapisan terluar jaringan (*the edge layer*):
1. **Module 01 (DNS & Global Traffic Management):**
   - Hierarki resolusi 4 lapis: Browser Cache -> OS Cache -> Recursive Resolver -> Authoritative Nameservers.
   - Peran record A, AAAA, CNAME, ALIAS, MX, dan TXT.
   - Manajemen TTL untuk fleksibilitas migrasi vs latensi.
   - Mekanisme perutean global: **GeoDNS** vs **Anycast BGP Routing**.
2. **Module 02 (Content Delivery Network / CDN):**
   - Topologi CDN: PoP, Edge Server, Origin Shield, dan Origin Server.
   - Model penyerapan data: **Push CDN** (proaktif) vs **Pull CDN** (reaktif on-demand).
   - Konfigurasi header HTTP: `Cache-Control`, `s-maxage`, `stale-while-revalidate`, `ETag`, `304 Not Modified`.
   - Strategi invalidasi: *Cache Busting via Content Hashing* (`app.[hash].js`) dan *Surrogate-Key Purging*.

---

## 📝 BAB 02 QUIZ (Uji Pemahaman)

### Bagian A: Soal Fundamental (Basic)
1. Apa fungsi dari DNS Recursive Resolver dan apa bedanya dengan Authoritative Nameserver?
2. Mengapa spesifikasi standar RFC melarang penempatan CNAME Record pada root/apex domain (seperti `example.com`), dan apa solusi modern untuk masalah ini?
3. Apa perbedaan mendasar antara *Push CDN* dan *Pull CDN*?
4. Apa arti dari header `Cache-Control: public, max-age=300, s-maxage=86400`? Berapa lama file disimpan di browser dan berapa lama di CDN?
5. Mengapa penamaan file menggunakan *Content Hashing* (misal: `bundle.4a8f9c.js`) dianggap sebagai praktik terbaik (*best practice*) dalam strategi caching web frontend?

### Bagian B: Soal Menengah (Intermediate)
6. Jelaskan bagaimana **Anycast BGP Routing** memungkinkan jutaan pengguna di seluruh dunia mengakses IP yang persis sama (`1.1.1.1` atau `8.8.8.8`) tetapi secara fisik dilayani oleh data center yang berbeda-beda!
7. Apa bahaya terbesar jika Anda menyetel DNS TTL sebesar 7 hari (604.800 detik) untuk sebuah endpoint API backend produksi?
8. Bagaimana mekanisme **Origin Shield** melindungi Origin Server dari fenomena *Thundering Herd Problem (Cache Stampede)* ketika sebuah konten viral expired serentak di 200 PoP Edge?
9. Jelaskan perbedaan fungsi antara direktif `Cache-Control: no-cache` dan `Cache-Control: no-store`! Direktif mana yang wajib digunakan untuk response data kartu kredit atau token autentikasi?
10. Bagaimana cara kerja header `stale-while-revalidate` dalam memangkas latensi p99 pengguna pada halaman katalog produk yang mengalami cache expiration?

### Bagian C: Scenario-Based Questions (Studi Kasus Arsitektur)
11. **Skenario 1 (Kebocoran Data Akun Pengguna):**  
    Sebuah aplikasi perbankan digital baru saja mengaktifkan Cloudflare CDN untuk mempercepat website mereka. Beberapa saat kemudian, seorang nasabah di Bandung melaporkan bahwa saat membuka halaman `/api/v1/profile`, ia melihat nama dan nomor rekening nasabah lain asal Surabaya. Analisis di mana letak kesalahan konfigurasi header caching backend, dan berikan perbaikan konfigurasinya!
12. **Skenario 2 (Deploy Versi Baru yang Macet):**  
    Tim frontend merilis update bug fix darurat ke server origin. File HTML `index.html` dan file JS `app.js` telah diganti. Namun, ribuan pengguna di media sosial tetap komplain aplikasi mereka menampilkan error versi lama selama berjam-jam. Mengapa ini terjadi jika kedua file tersebut diberi header `Cache-Control: public, max-age=86400`, dan bagaimana seharusnya aturan caching untuk file HTML vs file JavaScript?
13. **Skenario 3 (Migrasi Cloud Antar-Benua Tanpa Downtime):**  
    Perusahaan Anda ingin memindahkan seluruh origin server dari AWS Singapura ke GCP Jakarta pada hari Minggu pukul 01:00. Domain Anda memiliki DNS TTL 86.400 detik (24 jam). Buatlah timeline operasional langkah demi langkah (mulai dari H-3 hingga H+1) untuk memastikan peralihan IP berjalan dengan zero-downtime!

---

## 🏆 CHAPTER CHALLENGE: Merancang Edge Delivery Media Streaming

### Misi Arsitek:
Rancang arsitektur level edge untuk platform media berita video (*News Media Portal*) yang melayani **10 juta pengunjung unik per hari** di seluruh Indonesia dengan target:
- Waktu buka halaman awal (*First Contentful Paint*) < 800 ms.
- Menekan beban traffic yang sampai ke Origin Server hingga di bawah **5%** (*95% Cache Offload Ratio*).

### Syarat Desain:
1. Tentukan jenis DNS routing yang digunakan (Anycast DNS dengan Geo-steering).
2. Rancang pemisahan strategi caching antara:
   - File HTML (`/`, `/news/*`)
   - File statis build frontend (`/static/css/*`, `/static/js/*`)
   - File gambar artikel berita (`/images/*`)
   - API real-time breaking news ticker (`/api/breaking-news`)
3. Tentukan mekanisme Cache Invalidation jika redaksi berita melakukan revisi judul/isi berita penting yang sedang viral.

---

## ✅ Knowledge Checklist BAB 02

- [ ] Memahami seluruh tahapan resolusi hierarki DNS.
- [ ] Mampu memilih record DNS yang tepat (A, AAAA, CNAME, ALIAS, NS, TXT).
- [ ] Menguasai konsep Anycast BGP vs GeoDNS.
- [ ] Memahami perbedaan implementasi Push CDN vs Pull CDN.
- [ ] Mampu merancang header `Cache-Control` yang aman dan optimal.
- [ ] Menguasai teknik Cache Busting dan Surrogate-Key Purge.
- [ ] Memahami pencegahan kebocoran data sensitif pada CDN caching.
