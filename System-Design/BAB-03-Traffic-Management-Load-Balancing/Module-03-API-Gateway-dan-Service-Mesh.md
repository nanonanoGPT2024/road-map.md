# MODULE 03: API Gateway & Service Mesh

## 1. Learning Objective
Setelah menyelesaikan module ini, Anda mampu:
1. Menjelaskan pola arsitektur **API Gateway** dan membedakan lalu lintas **North-South** (Client-ke-Server) vs **East-West** (Service-ke-Service).
2. Menerapkan pola **Backend-for-Frontend (BFF)** untuk mengoptimalkan pengalaman perangkat yang berbeda (Mobile vs Web).
3. Memahami arsitektur **Service Mesh** (Control Plane vs Data Plane) menggunakan pola **Sidecar Proxy (Envoy)**.
4. Menganalisis peran Service Mesh dalam mengotomatisasi **Mutual TLS (mTLS)**, **Circuit Breaking**, dan **Distributed Tracing**.
5. Mengimplementasikan dan menguji simulasi API Gateway terpadu (Routing, Auth, dan Rate Limiting) menggunakan script hands-on.

---

## 2. Prerequisite
- Telah menyelesaikan [BAB 03 — Module 01: Reverse Proxy vs Forward Proxy](./Module-01-Reverse-Proxy-vs-Forward-Proxy.md).
- Telah menyelesaikan [BAB 03 — Module 02: Load Balancer L4 vs L7 & Algoritma](./Module-02-Load-Balancer-L4-L7-dan-Algorithms.md).

---

## 3. Concept
Dalam evolusi dari arsitektur Monolith menuju puluhan atau ratusan Microservices, muncul tantangan baru:
- Bagaimana cara ratusan aplikasi klien (Android, iOS, Single Page App) berkomunikasi dengan puluhan microservices tanpa harus mengetahui detail port, alamat IP, dan protokol internal masing-masing service?
- Bagaimana cara mengamankan, mengontrol laju (*rate limit*), dan memantau komunikasi antar-service internal di dalam cluster?

Dua pola arsitektural utama yang menjawab tantangan ini adalah:
1. **API Gateway:** Gerbang pintu masuk terpusat untuk mengelola lalu lintas **North-South** (dari luar internet ke dalam sistem).
2. **Service Mesh:** Jaringan infrastruktur terdedikasi untuk mengelola lalu lintas **East-West** (komunikasi antar-service di dalam sistem).

---

## 4. Why? (Mengapa Tidak Memanggil Microservices Secara Langsung?)

```text
       [ TANPA API GATEWAY: KEKACAUAN KOMUNIKASI ]
       
            Aplikasi Mobile           Website Desktop
                   │                         │
      ┌────────────┼────────────┬────────────┼────────────┐
      ▼            ▼            ▼            ▼            ▼
[ Service Auth ] [ Service Order ] [ Service Pay ] [ Service Inventory ]
```

### 3 Masalah Fatal Tanpa API Gateway:
1. **Chatty Mobile Clients:** Halaman detail produk mobile harus mengirim 7 HTTP request terpisah (mengambil data produk, harga, stok, review, profil penjual, diskon, dan rekomendasi). Di jaringan seluler 4G yang tidak stabil, ini memicu latensi tinggi dan baterai ponsel boros!
2. **Duplikasi Cross-Cutting Concerns:** Setiap tim microservice (Auth, Order, Payment) terpaksa mengimplementasikan kode otentikasi token JWT, validasi SSL, logging, dan CORS berulang-ulang di bahasanya masing-masing (Node.js, Go, Java).
3. **Keterikatan Protokol Publik:** Klien publik dipaksa menyesuaikan protokol internal. Jika backend ingin beralih ke protokol biner ultra-cepat seperti **gRPC / Protobuf**, browser client web tidak bisa mengaksesnya secara langsung tanpa perantara.

---

## 5. What? (API Gateway, BFF, & Service Mesh)

### A. Pola API Gateway & BFF (Backend-For-Frontend)

```text
               POLA BACKEND-FOR-FRONTEND (BFF)
               
      [ Aplikasi Mobile ]                [ Web Desktop ]
               │                                │
               ▼                                ▼
       [ Mobile BFF Gateway ]           [ Web BFF Gateway ]
     (Payload Ringkas JSON)           (Payload Lengkap + SSR)
               │                                │
               └───────────────┬────────────────┘
                               │ (Lalu Lintas North-South)
                               ▼
     ================== CLUSTER INTERNAL ==================
     [ Service User ]  [ Service Catalog ]  [ Service Order ]
```

### Tugas Utama API Gateway:
- **Request Routing:** Memetakan URL publik ke microservice tujuan (misal: `/v1/orders/*` -> `orders-service:8080`).
- **API Aggregation / Composition:** Menerima 1 request dari aplikasi mobile, lalu secara paralel memanggil 5 microservices internal, menggabungkan datanya (*fan-out & join*), dan mengembalikan 1 respon JSON ringkas ke pengguna.
- **Centralized Security:** Memvalidasi tanda tangan token JWT / OAuth2 di pintu gerbang sebelum request menyentuh microservice.
- **Rate Limiting & Throttling:** Membatasi request pengguna jahat agar tidak membanjiri downstream services.

---

### B. Service Mesh (Lalu Lintas East-West & Pola Sidecar)

Ketika sistem memiliki 200 microservices yang saling memanggil satu sama lain di dalam cluster Kubernetes:
- Service Order memanggil Service Payment.
- Service Payment memanggil Service Fraud Detection.
- Service Fraud memanggil Service User History.

Bagaimana memastikan koneksi antar-service ini terenkripsi, tidak mengalami timeout tak terduga, dan bisa dilacak saat error? **Service Mesh** mengatasinya dengan menempelkan sebuah **Sidecar Proxy** (seperti Envoy) di samping setiap container microservice!

```text
                     ARSITEKTUR SERVICE MESH
                     
         POD A (Order Service)                 POD B (Payment Service)
    +------------------------------+      +------------------------------+
    | [ Order Application Code ]   |      | [ Payment Application Code ] |
    |              │ (Localhost)   |      |              ▲ (Localhost)   |
    |              ▼               |      |              │               |
    | [ Envoy Sidecar Proxy ]      | ───▶ | [ Envoy Sidecar Proxy ]      |
    +--------------+---------------+ (mTLS+--------------+---------------+
                   │                 Traced)             │
                   └─────────────────┬───────────────────┘
                                     ▼
                           [ CONTROL PLANE (Istio) ]
                        (Mengatur Kebijakan, mTLS Certs,
                         Routing Canary, Telemetri)
```

---

## 6. How? (Komponen Service Mesh: Data Plane vs Control Plane)

1. **Data Plane:** Kumpulan seluruh Sidecar Proxy (Envoy) berkinerja tinggi yang mencegat seluruh paket data masuk dan keluar secara transparan di level network namespace.
2. **Control Plane (misal: Istio / Linkerd):** Pusat komando yang bertugas:
   - Menerbitkan sertifikat digital TLS x509 ke setiap pod secara otomatis setiap 24 jam untuk **Mutual TLS (mTLS)**.
   - Mengatur kebijakan keamanan (*AuthorizationPolicy*: hanya Pod Order yang boleh memanggil Pod Payment!).
   - Menginjeksikan header pelacakan (*W3C Trace Context / Jaeger Trace ID*) untuk **Distributed Tracing**.

---

## 7. Analogy
- **API Gateway:** Seperti **Pintu Gerbang dan Petugas Imigrasi Bandara Internasional**. Setiap turis asing (client) yang mendarat wajib diperiksa paspornya, visa diverifikasi, barang bawaan di-scan x-ray, dan diarahkan ke terminal tujuan domestik.
- **Service Mesh:** Seperti **Sistem Terowongan Rahasia & Pengawal Pribadi Diplomat di Dalam Kota**. Setelah turis/pejabat masuk ke dalam negeri, setiap pergerakan antar-kantor kementerian dikawal oleh ajudan bersenjata (Sidecar Proxy) yang berkomunikasi menggunakan sandi terenkripsi (mTLS) dan mematuhi instruksi markas komando pusat (Control Plane).

---

## 8. Diagram: Perbandingan Arsitektural North-South vs East-West

```text
                  NORTH-SOUTH TRAFFIC (Internet -> Cluster)
                  
                   [ Internet Public Clients ]
                               │
                               ▼
                      [ API GATEWAY (Kong) ]
                               │
     ==========================┼==========================
                               │  EAST-WEST TRAFFIC
                               │  (Internal Microservices)
                               ▼
               [ Service A ] ◄───► [ Service B ]
                     ▲                   ▲
                     │ (mTLS via Mesh)   │
                     ▼                   ▼
               [ Service C ] ◄───► [ Service D ]
```

---

## 9. Simple Example: Header Transformation pada Gateway
Client mengirim token otentikasi di header HTTP:
```http
Authorization: Bearer eyJhbGciOiJIUzI1...
```
API Gateway memverifikasi signature token tersebut dengan kunci rahasia publik, mengekstrak data klaim pengguna, dan meneruskan request ke backend internal dengan header yang sudah bersih dan terpercaya:
```http
X-User-Id: 99812
X-User-Role: premium_customer
X-User-Email: user@example.com
```
Backend microservice tidak perlu lagi mengimpor library verifikasi JWT yang berat. Backend cukup membaca `req.headers['x-user-id']` dengan aman karena gateway menjamin hanya request yang valid yang bisa tembus!

---

## 10. Practical Code Example
Lihat demonstrasi implementasi API Gateway fungsional (Request Routing, JWT Header Extraction, In-Memory Token Bucket Rate Limiting, dan Error Handling) pada:
`System-Design/BAB-03-Traffic-Management-Load-Balancing/hands-on/m03/api_gateway_demo.js`

---

## 11. Real World Example: Migrasi Netflix ke Zuul 2 & Uber ke Envoy Mesh
- **Netflix Zuul 2:** Netflix menangani puluhan juta request per detik dari ribuan model Smart TV, Android, iOS, dan browser. Netflix membangun Zuul 2 berbasis Netty asynchronous non-blocking I/O sebagai API Gateway utama yang mampu melakukan routing dinamis, canary testing, dan isolasi kegagalan (*fault injection*).
- **Uber Service Mesh:** Uber memiliki lebih dari 4.000 microservices yang dibangun dalam berbagai bahasa (Go, Java, Python, Node.js). Mengelola TLS dan tracing di setiap bahasa menjadi mimpi buruk. Uber menstandarkan seluruh komunikasi internal menggunakan **Envoy Proxy Sidecar**, menghasilkan enkripsi mTLS 100% dan pelacakan latency end-to-end tanpa mengubah satu baris pun kode aplikasi para engineer!

---

## 12. Trade-offs (API Gateway vs Service Mesh)

| Dimensi | API Gateway | Service Mesh |
|---|---|---|
| **Fokus Area** | North-South (Edge / Ingress) | East-West (Cluster Internal) |
| **Pola Arsitektur** | Server Proxy Terpusat (*Centralized*) | Sidecar Proxy Terdistribusi (*Decentralized*) |
| **Overhead CPU / RAM** | Rendah (hanya 1 cluster gateway) | Signifikan (ratusan sidecar memakan RAM di setiap Pod) |
| **Overhead Latensi** | 1 - 5 ms di pintu masuk | 1 - 2 ms **pada setiap hop** antar-service |
| **Kompleksitas Operasional** | Menengah | Sangat Tinggi (butuh tim Platform/SRE khusus) |

---

## 13. When To Use What
- **Gunakan API Gateway jika:** Anda memiliki sistem client-server di mana aplikasi mobile/web perlu mengakses lebih dari 2 microservices backend, atau Anda butuh monetisasi API publik (API Key rate limiting).
- **Gunakan Service Mesh jika:** Anda memiliki lebih dari **20-30 microservices** di Kubernetes yang saling memanggil secara kompleks, dan organisasi Anda diwajibkan oleh regulasi keamanan (seperti PCI-DSS atau HIPAA) untuk menerapkan **Zero Trust Network Architecture (mTLS antar-kontainer)**.

---

## 14. When NOT To Use
- **Dilarang menggunakan Service Mesh untuk Monolith atau sistem yang hanya memiliki 3 microservices:** Anda hanya akan membuang 30% resource CPU/RAM cluster Kubernetes Anda untuk menjalankan sidecar proxy Istio yang tidak Anda butuhkan!

---

## 15. Common Mistakes
1. **The "Smart Gateway" Anti-Pattern:** Memasukkan logika bisnis berat (seperti query SQL gabungan, kalkulasi diskon, validasi domain transaksi) ke dalam kode API Gateway. Ini mengubah API Gateway menjadi **Distributed Monolith** yang menjadi bottleneck utama deployment!
2. **Tidak Mengatur Timeout & Circuit Breaker di Gateway:** Satu microservice lambat (misal service rekomendasi timeout 30 detik) menyebabkan seluruh thread worker di API Gateway terkunci, melumpuhkan layanan login dan checkout sekaligus.
3. **Mengabaikan Sidecar Proxy Resource Request di K8s:** Tidak menetapkan memory limit pada Envoy sidecar container, sehingga saat terjadi lonjakan traffic, sidecar crash OOM dan membunuh Pod aplikasi utama.

---

## 16. Best Practices

- **Must Have:**
  - *"Dumb Pipes, Smart Endpoints"*: Jaga API Gateway tetap ramping. Hanya gunakan untuk routing, otentikasi, rate limit, dan logging.
  - Terapkan **Strict Timeout (misal 2.5 detik)** pada seluruh rute gateway ke backend.
- **Recommended:**
  - Gunakan pola **BFF (Backend-For-Frontend)** terpisah jika kebutuhan format data antara aplikasi Mobile dan Web sangat berbeda.
  - Aktifkan **Rate Limiting berbasis Token Bucket** di API Gateway.
- **Advanced:**
  - Terapkan **Traffic Shadowing / Mirroring** di Service Mesh: Menduplikasi 5% traffic produksi ke service versi baru secara asinkron tanpa memengaruhi pengguna asli untuk menguji performa sebelum rilis resmi.
- **Avoid / Overengineering:**
  - Memasang Istio Service Mesh lengkap di lingkungan cluster development lokal yang memperlambat startup mesin developer.

---

## 17. Troubleshooting Guide
```text
Gejala: Klien menerima response "504 Gateway Timeout" secara acak.
-----------------------------------------------------------------
Kemungkinan Akar Masalah:
1. Microservice downstream membutuhkan waktu pemrosesan lebih lama daripada timeout gateway.
2. Connection pool antara API Gateway ke microservice jenuh.
3. DNS resolution internal Kubernetes (CoreDNS) mengalami throttling.

Langkah Diagnosa:
- Periksa header X-Request-Id pada response error.
- Telusuri log di API Gateway dan cari durasi upstream_response_time.

Solusi:
- Naikkan timeout gateway jika endpoint memang berupa asynchronous export job.
- Pasang Circuit Breaker agar service yang lambat langsung di-bypass dengan fallback response.
```

---

## 18. Hands-on Lab: Simulator API Gateway Terpadu

File lab sudah disiapkan di:
`System-Design/BAB-03-Traffic-Management-Load-Balancing/hands-on/m03/api_gateway_demo.js`

### Jalankan Uji Coba:
Buka terminal dan jalankan:
```bash
node System-Design/BAB-03-Traffic-Management-Load-Balancing/hands-on/m03/api_gateway_demo.js
```

### Yang Ditampilkan Script Ini:
1. Menjalankan 2 private backend microservices: **Users Service (:6001)** dan **Orders Service (:6002)**.
2. Menjalankan **API Gateway (:6000)** yang bertindak sebagai gerbang tunggal.
3. Menguji 4 skenario nyata:
   - **Skenario 1 (Routing Berhasil):** Request ke `/users` dan `/orders` diarahkan dengan benar.
   - **Skenario 2 (Otentikasi Gagal):** Request tanpa token otentikasi langsung ditolak dengan `401 Unauthorized`.
   - **Skenario 3 (Header Transformation):** Gateway mendekode token dan menyuntikkan `X-User-Id` ke microservice.
   - **Skenario 4 (Rate Limiting):** Mengirim rentetan 5 request cepat untuk membuktikan proteksi `429 Too Many Requests`.

---

## 19. Exercises (Latihan)

### Level 1 (Easy):
Sebutkan perbedaan mendasar antara lalu lintas **North-South** dan **East-West** dalam arsitektur sistem terdistribusi!

### Level 2 (Medium):
Jelaskan konsep pola **Backend-for-Frontend (BFF)**! Mengapa aplikasi mobile banking membutuhkan BFF yang terpisah dari website desktop banking? Berikan 2 contoh optimasi konkret yang dilakukan oleh Mobile BFF!

### Level 3 (Hard):
Sebuah perusahaan e-commerce skala besar memiliki 150 microservices di Kubernetes. Jelaskan bagaimana arsitektur **Service Mesh** dengan pola **Sidecar Proxy (Envoy)** mampu menerapkan kebijakan **Zero Trust Security (Mutual TLS)** secara otomatis tanpa perlu mengubah kode sumber aplikasi yang ditulis dalam 5 bahasa pemrograman berbeda!

---

## 20. Summary & Knowledge Check
- [ ] Memahami peran sentral API Gateway dalam meredam kompleksitas Microservices.
- [ ] Menguasai pola Backend-for-Frontend (BFF).
- [ ] Memahami arsitektur Service Mesh: Data Plane (Envoy Sidecar) vs Control Plane (Istio).
- [ ] Mampu menerapkan pengamanan mTLS, Circuit Breaking, dan Distributed Tracing.
- [ ] Menghindari anti-pattern "Smart Gateway" yang merusak arsitektur microservices.
