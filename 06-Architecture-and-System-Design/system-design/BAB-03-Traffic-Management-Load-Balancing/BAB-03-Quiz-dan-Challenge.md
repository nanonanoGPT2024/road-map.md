# EVALUASI BAB 03: Traffic Management, Load Balancing, & Gateway

Dokumen evaluasi ini berisi ringkasan materi, kuis pemahaman, dan tantangan perancangan sistem traffic management untuk menguji kesiapan Anda sebelum melangkah ke **BAB 04: Caching Terdistribusi & Strategi Optimasi Data**.

---

## 📌 Chapter Summary (Rangkuman BAB 03)

Sepanjang BAB 03, Anda telah mempelajari manajemen lalu lintas di perimeter sistem dan interior cluster:
1. **Module 01 (Reverse Proxy vs Forward Proxy):**
   - Forward Proxy mewakili dan menganonimkan klien, sedangkan Reverse Proxy melindungi dan mengaburkan server backend.
   - Peran krusial Reverse Proxy: SSL/TLS Termination, Gzip/Brotli Compression, Request Buffering, dan penyuntikan header `X-Forwarded-For` serta `X-Forwarded-Proto`.
2. **Module 02 (Load Balancer L4 vs L7 & Algoritma):**
   - Layer 4 (Transport / TCP) berkinerja ultra-tinggi tanpa inspeksi paket vs Layer 7 (Application / HTTP) yang mampu melakukan perutean cerdas berbasis URL path/headers.
   - Evaluasi 4 algoritma: Round Robin, Weighted, Least Connections, dan Consistent Hashing.
   - Matematika Consistent Hashing Ring beserta peran Virtual Nodes dalam mencegah *Hotspot*.
   - Prosedur keselamatan deployment: Connection Draining / Graceful Deregistration.
3. **Module 03 (API Gateway & Service Mesh):**
   - Pemisahan lalu lintas North-South (Internet ke Cluster) yang ditangani API Gateway vs East-West (komunikasi antar-service) yang ditangani Service Mesh.
   - Pola Backend-for-Frontend (BFF) untuk membedakan kebutuhan Mobile vs Web.
   - Arsitektur Service Mesh: Data Plane (Envoy Sidecar) dan Control Plane (Istio) untuk Mutual TLS (mTLS) otomatis, Circuit Breaking, dan Distributed Tracing.

---

## 📝 BAB 03 QUIZ (Uji Pemahaman)

### Bagian A: Soal Fundamental (Basic)
1. Siapakah yang dilindungi oleh *Forward Proxy*, dan siapakah yang dilindungi oleh *Reverse Proxy*?
2. Apa yang dimaksud dengan **SSL/TLS Termination**, dan mengapa hal ini sangat menghemat beban CPU pada server aplikasi backend?
3. Apa perbedaan utama antara Layer 4 Load Balancer dan Layer 7 Load Balancer dalam memahami isi paket data HTTP?
4. Kapan algoritma *Least Connections* jauh lebih unggul dibandingkan *Round Robin*?
5. Mengapa fitur *Sticky Sessions (Session Affinity)* pada Load Balancer dianggap sebagai anti-pattern dalam arsitektur sistem berskala besar?

### Bagian B: Soal Menengah (Intermediate)
6. Jelaskan bagaimana serangan **IP Spoofing** dapat terjadi jika Reverse Proxy Anda tidak menimpa (*overwrite*) header `X-Forwarded-For` yang dikirimkan oleh klien luar!
7. Bagaimana **Consistent Hashing** meminimalkan jumlah data yang harus dipindahkan saat sebuah server ditambahkan atau dikeluarkan dari cluster penyimpanan?
8. Mengapa penambahan **Virtual Nodes** (misal 100 virtual node per server fisik) sangat penting pada implementasi cincin Consistent Hashing?
9. Apa yang dimaksud dengan **Connection Draining (Deregistration Delay)** pada Load Balancer, dan apa yang terjadi jika fitur ini dimatikan saat melakukan rolling update deployment?
10. Jelaskan perbedaan mendasar antara lalu lintas **North-South** dan **East-West** dalam arsitektur microservices!

### Bagian C: Scenario-Based Questions (Studi Kasus Arsitektur)
11. **Skenario 1 (The "Smart Gateway" Disaster):**  
    Sebuah tim engineer memutuskan untuk menaruh logika validasi keranjang belanja, kalkulasi diskon promo, dan query database PostgreSQL langsung di dalam layer API Gateway (Node.js) agar respon lebih cepat. Tiga bulan kemudian, deployment API Gateway memakan waktu 45 menit, sering crash kehabisan memori, dan rilis fitur baru tersendat. Jelaskan mengapa pendekatan ini salah (*anti-pattern*), dan bagaimana arsitektur yang seharusnya!
12. **Skenario 2 (Game Multiplayer vs E-Commerce):**  
    Anda diminta memilih load balancer untuk dua proyek:
    - Proyek A: Game Online Battle Royale (protokol UDP, butuh 2 juta koneksi paket/detik dengan latensi < 5 ms).
    - Proyek B: Portal E-Commerce (protokol HTTPS, butuh perutean `/checkout` ke cluster server terpisah dan validasi token JWT).  
    Tentukan apakah masing-masing proyek harus menggunakan L4 atau L7 Load Balancer, dan jelaskan alasannya!
13. **Skenario 3 (Lonjakan 502 Bad Gateway saat Deploy):**  
    Setiap kali tim engineering melakukan deployment versi baru di Kubernetes, ribuan pengguna mengalami error `502 Bad Gateway` selama 15-20 detik. Setelah ditelusuri, container lama langsung dimatikan seketika oleh Kubernetes saat container baru berstatus *Running*. Komponen apa pada Load Balancer / Reverse Proxy yang belum dikonfigurasi, dan bagaimana siklus shutdown yang aman (*graceful termination*)?

---

## 🏆 CHAPTER CHALLENGE: Merancang Traffic Management FinTech Super-App

### Misi Arsitek:
Rancang arsitektur perimeter traffic management untuk aplikasi FinTech Super-App (memiliki fitur: E-Wallet, Pembayaran Tagihan, Investasi Emas, dan Chat Support) yang melayani **50.000 requests/detik**:

### Syarat & Batasan Desain:
1. **Perimeter Layer (Ingress):**  
   Gunakan kombinasi Layer 4 NLB dan Layer 7 API Gateway. Jelaskan peran masing-masing.
2. **Device Optimization:**  
   Gunakan pola Backend-for-Frontend (BFF) terpisah untuk Aplikasi Mobile iOS/Android dan Portal Web Merchant.
3. **Service Mesh (East-West):**  
   Jelaskan bagaimana Service Payment memanggil Service Core Banking di dalam cluster dengan jaminan keamanan Zero Trust (mTLS), otentikasi antar-service, dan timeout circuit breaker.
4. **Resiliensi & Autentikasi:**  
   Jelaskan bagaimana token otentikasi JWT divalidasi di Gateway dan bagaimana rate limiter berbasis Token Bucket mencegah serangan brute-force PIN transaksi.

---

## ✅ Knowledge Checklist BAB 03

- [ ] Memahami perbedaan topologi Forward Proxy vs Reverse Proxy.
- [ ] Menguasai fungsi header `X-Forwarded-For`, `X-Forwarded-Proto`, dan `X-Real-IP`.
- [ ] Memahami komparasi performa dan fungsi Layer 4 vs Layer 7 Load Balancer.
- [ ] Menguasai algoritma Round Robin, Weighted, Least Connections, dan Consistent Hashing.
- [ ] Menguasai implementasi cincin Consistent Hashing dan peran Virtual Nodes.
- [ ] Memahami pentingnya Connection Draining dan Health Check tuning.
- [ ] Membedakan lalu lintas North-South (API Gateway) vs East-West (Service Mesh).
- [ ] Menguasai pola Backend-for-Frontend (BFF) dan prinsip "Dumb Pipes, Smart Endpoints".
