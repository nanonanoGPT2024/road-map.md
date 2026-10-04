# MODULE 02: Load Balancer (Layer 4 vs Layer 7 & Algoritma)

## 1. Learning Objective
Setelah menyelesaikan module ini, Anda mampu:
1. Membedakan secara mendalam cara kerja, throughput, dan pemanfaatan sumber daya antara **Layer 4 (L4) Transport Load Balancer** dan **Layer 7 (L7) Application Load Balancer**.
2. Menganalisis dan memilih algoritma load balancing yang tepat: **Round Robin**, **Weighted Round Robin**, **Least Connections**, **Least Response Time**, dan **Consistent Hashing**.
3. Menjelaskan mekanisme matematika dan implementasi **Consistent Hashing Ring** beserta teknik **Virtual Nodes** untuk mendistribusikan beban secara merata dan mencegah *Hotspot*.
4. Mengonfigurasi mekanisme **Health Checks (Active vs Passive)** dan **Connection Draining / Graceful Deregistration**.
5. Menjalankan pengujian 4 algoritma pembagian beban secara langsung menggunakan script hands-on.

---

## 2. Prerequisite
- Telah menyelesaikan [BAB 03 — Module 01: Reverse Proxy vs Forward Proxy](./Module-01-Reverse-Proxy-vs-Forward-Proxy.md).
- Memahami konsep dasar model OSI (Lapisan 4 Transport TCP/UDP dan Lapisan 7 Aplikasi HTTP).

---

## 3. Concept
**Load Balancer (LB)** adalah perangkat perangkat keras (*hardware appliance*) atau perangkat lunak (*software proxy*) yang bertindak sebagai "polisi lalu lintas", mendistribusikan aliran request jaringan yang datang dari klien ke sekumpulan server backend (*server pool / upstream cluster*).

Tujuan fundamental Load Balancer:
1. **Mencegah Overload:** Memastikan tidak ada satu pun server yang kewalahan menangani beban berlebih sementara server lain menganggur.
2. **Menjamin High Availability:** Mendeteksi server yang mati secara otomatis dan mengalihkan lalu lintas hanya ke server yang sehat (*healthy nodes*).
3. **Elastisitas:** Memungkinkan penambahan atau pengurangan kapasitas server (*autoscaling*) tanpa downtime.

---

## 4. Why? (Mengapa Memahami L4 vs L7 Itu Wajib?)

### Mitos "Semua Load Balancer Itu Sama"
Banyak developer menganggap load balancer hanyalah kotak hitam pembagi request. Akibatnya:
- Menggunakan L7 Application Load Balancer untuk streaming video raw TCP/UDP atau game multiplayer: CPU load balancer meledak pada 10.000 koneksi karena L7 harus mendekripsi dan membedah setiap paket data.
- Menggunakan L4 Transport Load Balancer saat sistem membutuhkan perutean cerdas berbasis URL path (misal: `/api/payment` ke Server Klaster A dan `/api/video` ke Server Klaster B): L4 gagal karena L4 tidak bisa membaca isi URL HTTP!

---

## 5. What? (Layer 4 vs Layer 7 Load Balancing)

```text
       [ LAYER 4 LOAD BALANCER ]                       [ LAYER 7 LOAD BALANCER ]
         (Transport / TCP/UDP)                          (Application / HTTP/gRPC)
         
          [ Client Request ]                              [ Client Request ]
                  │                                               │
                  ▼                                               ▼
         [ L4 Load Balancer ]                            [ L7 Load Balancer ]
   (Hanya melihat: IP & Port TCP)                 (Melihat: URL Path, Header, Cookies, Body)
                  │                                               │
        ┌─────────┴─────────┐                           ┌─────────┴─────────┐
        ▼                   ▼                           ▼                   ▼
[ Server 1: :8080 ] [ Server 2: :8080 ]         [ /api/auth ]       [ /api/payment ]
 (Routing berbasis packet NAT murni)            (Server Klaster A)  (Server Klaster B)
```

### Tabel Perbandingan Arsitektural:

| Parameter | Layer 4 (L4 / Network Load Balancer) | Layer 7 (L7 / Application Load Balancer) |
|---|---|---|
| **Protokol yang Dipahami** | TCP, UDP, TLS passthrough | HTTP, HTTPS, HTTP/2, gRPC, WebSockets |
| **Visibilitas Paket Data** | Buta terhadap konten (hanya IP & Port sumber/tujuan) | Membaca penuh URL, Query Params, Headers, Cookies |
| **Throughput & Performa** | Sangat Tinggi (jutaan paket/detik, latensi sub-milidetik) | Menengah-Tinggi (butuh CPU untuk parsing payload) |
| **Terminasi SSL/TLS** | Opsional (bisa TCP Passthrough tanpa dekripsi) | Ya (Wajib dekripsi untuk membaca HTTP request) |
| **Fitur Routing** | Sederhana (hanya berbasis IP hash atau round-robin port) | Sangat Fleksibel (Path-based, Header-based, Host-based) |
| **Contoh Software / Cloud** | HAProxy (mode TCP), AWS NLB, IPVS, Maglev | Nginx, AWS ALB, Envoy, Traefik, Kong |

---

## 6. How? (Algoritma Pembagian Beban / Balancing Algorithms)

```text
1. Round Robin:
   Server A -> Server B -> Server C -> Server A -> Server B ...
   (Sederhana, ideal jika seluruh server memiliki spesifikasi hardware identik).

2. Weighted Round Robin:
   Server A (Bobot 3): Menerima 3 request
   Server B (Bobot 1): Menerima 1 request
   (Cocok jika Server A memiliki 16 core dan Server B hanya 4 core).

3. Least Connections:
   Pilih server yang memiliki koneksi TCP aktif paling sedikit saat ini.
   (Sangat ideal untuk request yang durasi pengerjaannya bervariasi panjang, misal upload file atau database query berat).

4. Consistent Hashing:
   Memetakan request key (seperti user_id atau session_id) ke sebuah cincin lingkaran hash.
   (Wajib digunakan pada caching cluster dan stateful connection).
```

### Consistent Hashing Ring & Virtual Nodes Deep Dive
Pada hashing modular konvensional:
$$\text{Server} = \text{hash}(\text{key}) \pmod N$$
Jika jumlah server $N$ berubah dari 4 menjadi 5 (karena autoscaling atau 1 server mati), maka **hampir 100% kunci data akan berpindah server secara massal**. Ini menghancurkan seluruh cache sistem!

Dengan **Consistent Hashing**:
1. Ruang hash dipetakan dalam sebuah lingkaran cincin dari $0$ hingga $2^{32} - 1$.
2. Server dan Kunci data di-hash ke posisi cincin tersebut.
3. Kunci data diarahkan ke server pertama yang ditemui searah jarum jam (*clockwise*).
4. Jika 1 server mati, **hanya data milik server tersebut yang berpindah** ke server tetangganya. Data di server lain tidak terganggu sama sekali!
5. **Virtual Nodes:** Setiap server fisik diberi 100-200 posisi titik virtual di cincin (misal: `ServerA#1`, `ServerA#2`) untuk mencegah satu server menampung beban timpang (*hotspot avoidance*).

---

## 7. Analogy: Antrean Teller Bank
- **Round Robin:** Satpam bank membagikan nomor antrean: Orang ke-1 ke Teller A, Orang ke-2 ke Teller B, Orang ke-3 ke Teller C. Masalahnya: Teller A mendapatkan nasabah yang menyetor uang receh berjam-jam, sementara Teller B hanya melayani cetak buku tabungan 1 menit. Teller A langsung kewalahan!
- **Least Connections:** Satpam melihat siapa teller yang mejanya sedang kosong atau paling cepat menyelesaikan nasabah, lalu mengarahkan orang berikutnya ke meja tersebut.
- **Consistent Hashing:** Nasabah yang namanya berawalan huruf A-H selalu pergi ke Teller A, I-P ke Teller B, dan Q-Z ke Teller C. Teller A sudah hafal dokumen nasabah grupnya tanpa perlu mencari berkas dari awal (*Cache Locality*).

---

## 8. Diagram: Mekanisme Consistent Hashing Ring

```text
                           [ 0 / 2^32 ]
                         .  -  -  -  .
                     '                   '
                  '                         '
                '                             '
         Node C (Pos: 800)               Node A (Pos: 200)
             \                                 /
              \                               /
               \                             /
                '                           '
                  '                       '
                     '                 '
                         .  -  -  -  .
                      Node B (Pos: 500)
```
- Request dengan Hash `150` -> Berjalan searah jarum jam -> Diterima oleh **Node A**.
- Request dengan Hash `350` -> Berjalan searah jarum jam -> Diterima oleh **Node B**.
- Jika Node B mati: Request Hash `350` otomatis berlanjut searah jarum jam ke **Node C**. Node A sama sekali tidak terpengaruh!

---

## 9. Simple Example: Path-Based Routing pada Layer 7
Konfigurasi Nginx membagi traffic berdasarkan URL:
```nginx
upstream auth_cluster {
    server 10.0.1.10:3000;
    server 10.0.1.11:3000;
}

upstream payment_cluster {
    least_conn; # Algoritma Least Connection untuk transaksi
    server 10.0.2.20:4000;
    server 10.0.2.21:4000;
}

server {
    listen 80;

    location /api/auth/ {
        proxy_pass http://auth_cluster;
    }

    location /api/payment/ {
        proxy_pass http://payment_cluster;
    }
}
```

---

## 10. Practical Code Example
Lihat demonstrasi implementasi dan perbandingan 4 algoritma load balancing (Round Robin, Weighted, Least Connections, dan Consistent Hashing) pada:
`System-Design/BAB-03-Traffic-Management-Load-Balancing/hands-on/m02/load_balancer_algorithms.js`

---

## 11. Real World Example: Google Maglev & AWS Network Load Balancer (NLB)
- **Google Maglev:** Google membangun software load balancer Layer 4 berbasis kernel-bypass (DPDK) yang mampu menangani jutaan paket/detik per mesin server standar tanpa hardware ASIC khusus. Maglev mendistribusikan seluruh paket data layanan Google Search, YouTube, dan Gmail menggunakan algoritma *Maglev Consistent Hashing* yang memastikan perpindahan koneksi nol saat cluster di-upgrade.
- **AWS ALB vs NLB:**
  - **AWS ALB (L7):** Digunakan untuk aplikasi web modern yang butuh routing path `/orders`, autentikasi JWT, dan gRPC.
  - **AWS NLB (L4):** Digunakan untuk game online FPS multiplayer (protokol UDP) dan IoT telemetry yang membutuhkan latensi < 1 ms dan throughput puluhan juta request per detik.

---

## 12. Trade-offs (Pemilihan Algoritma Balancing)

| Algoritma | Kompleksitas | Kelebihan Utama | Kelemahan Utama |
|---|---|---|---|
| **Round Robin** | Sangat Rendah | Sederhana, tanpa overhead memori | Mengabaikan beban server riil |
| **Weighted Round Robin** | Rendah | Mengakomodasi mesin beda spesifikasi | Tetap rentan jika request bervariasi berat |
| **Least Connections** | Sedang | Sangat adaptif terhadap request panjang | Membutuhkan tracking state koneksi aktif |
| **Consistent Hashing** | Tinggi | Mempertahankan cache locality & session | Butuh virtual nodes untuk mencegah skew |

---

## 13. When To Use What
- **Gunakan Layer 4 Load Balancer jika:**
  - Aplikasi membutuhkan performa raw throughput ekstrem (jutaan koneksi simultan).
  - Menggunakan protokol non-HTTP (database replication protocol, SMTP, RTSP video streaming, MQTT IoT, game UDP sockets).
- **Gunakan Layer 7 Load Balancer jika:**
  - Arsitektur berbasis Microservices yang membagi routing berdasarkan URL path atau request headers.
  - Membutuhkan inspeksi payload, autentikasi token JWT di gateway, dan SSL Termination.
- **Gunakan Consistent Hashing jika:**
  - Melakukan load balancing ke cluster caching (Redis / Memcached).
  - Menghubungkan client WebSocket ke server chat agar client selalu terhubung ke server yang sama tanpa shared session store.

---

## 14. When NOT To Use
- **Jangan gunakan "Sticky Sessions / Session Affinity" (Cookie-based session pinning) pada L7 Load Balancer sebagai solusi jangka panjang:**
  Sticky session memaksa user tertentu selalu mendarat di Server A. Jika Server A menerima 100 user "heavy spender" yang browsing intensif, Server A akan overload sementara Server B dan C menganggur. Selalu rancang backend Anda menjadi **Stateless**!

---

## 15. Common Mistakes
1. **Tidak Menyetel "Connection Draining" (Deregistration Delay):** Saat Anda melakukan deployment versi baru dan mematikan Server 1, Load Balancer langsung memutuskan ribuan koneksi aktif yang sedang melakukan transaksi checkout. Pengguna mendapatkan error `502 Bad Gateway`. Selalu pasang *Connection Draining* (misal 30 detik) agar request yang sedang berjalan diberi waktu untuk selesai!
2. **Health Check Terlalu Agresif:** Menyetel interval health check tiap 1 detik dengan timeout 500 ms. Saat server sedang sibuk mengerjakan query CPU 90% selama 1 detik, health check gagal, dan load balancer mencabut server tersebut dari pool secara keliru (*Health Check Flapping*).
3. **Consistent Hashing Tanpa Virtual Nodes:** Menggunakan consistent hashing hanya dengan 3 titik server. Akibat persebaran hash acak, Server A mendapatkan 70% cincin hash sementara Server B hanya 10% (terjadi *Severe Hotspot*).

---

## 16. Best Practices

- **Must Have:**
  - Terapkan **Health Check Endpoint khusus** (`/healthz` atau `/ready`) yang mengembalikan HTTP 200 hanya jika aplikasi siap menerima request.
  - Pasang **Connection Draining (Graceful Shutdown)** minimal 30 - 60 detik pada Load Balancer.
- **Recommended:**
  - Pasang sepasang Load Balancer aktif-siaga (*High Availability LB*) menggunakan protokol VRRP / Keepalived untuk mencegah Load Balancer menjadi Single Point of Failure (SPOF).
- **Advanced:**
  - Gunakan minimal **100-200 Virtual Nodes per server fisik** pada implementasi Consistent Hashing ring.
- **Avoid / Overengineering:**
  - Mengonfigurasi Dynamic Weighted Load Balancing berbasis CPU metrics jika variasi response time backend Anda sudah sangat stabil.

---

## 17. Troubleshooting Guide
```text
Gejala: Salah satu server di cluster selalu crash OOM (Out of Memory), sementara server lain sepi.
-------------------------------------------------------------------------------------------------
Kemungkinan Penyebab:
1. Penggunaan Session Affinity (Sticky Cookies) yang tidak seimbang.
2. Algoritma Round Robin menerima payload request yang sangat heterogen (ada query 5KB, ada query 500MB).
3. Hash function pada Consistent Hashing memiliki bias distribusi (tidak seragam).

Solusi:
- Ganti algoritma ke Least Connections.
- Tambahkan Virtual Nodes pada consistent hash ring.
- Hapus sticky session dan pindahkan session store ke Redis terpusat.
```

---

## 18. Hands-on Lab: Simulator 4 Algoritma Load Balancing

File lab sudah disiapkan di:
`System-Design/BAB-03-Traffic-Management-Load-Balancing/hands-on/m02/load_balancer_algorithms.js`

### Jalankan Uji Coba:
Buka terminal dan jalankan:
```bash
node System-Design/BAB-03-Traffic-Management-Load-Balancing/hands-on/m02/load_balancer_algorithms.js
```

### Yang Ditampilkan Script Ini:
1. Simulasi distribusi 12 request menggunakan **Round Robin**.
2. Simulasi distribusi menggunakan **Weighted Round Robin** (Server A bobot 3 vs Server B bobot 1).
3. Simulasi penanganan request berdurasi acak menggunakan **Least Connections**.
4. Simulasi **Consistent Hashing Ring** (dengan virtual nodes) yang menunjukkan konsistensi mapping user ID ke server dan minimnya dampak ketika 1 server mati.

---

## 19. Exercises (Latihan)

### Level 1 (Easy):
Jelaskan perbedaan mendasar antara Layer 4 Load Balancer dan Layer 7 Load Balancer dalam hal visibilitas paket data!

### Level 2 (Medium):
Sebuah cluster memiliki 3 server:
- Server 1 (8 CPU Core, bobot 4)
- Server 2 (4 CPU Core, bobot 2)
- Server 3 (2 CPU Core, bobot 1)
Jika 14 request masuk secara berurutan menggunakan algoritma **Weighted Round Robin**, hitung berapa jumlah request yang diterima oleh masing-masing server!

### Level 3 (Hard):
Pada sistem cache terdistribusi dengan 10 server, jelaskan mengapa penggunaan formula modular konvensional `hash(key) % 10` akan memicu bencana *Cache Invalidation Massal* jika 1 server mendadak crash! Jelaskan secara matematis bagaimana **Consistent Hashing** membatasi dampak perpindahan data hanya sebesar $1/N$ dari total kunci!

---

## 20. Summary & Knowledge Check
- [ ] Memahami perbedaan operasional dan use-case Layer 4 vs Layer 7 Load Balancer.
- [ ] Menguasai cara kerja Round Robin, Weighted, Least Connections, dan Consistent Hashing.
- [ ] Memahami formula dan arsitektur cincin Consistent Hashing beserta Virtual Nodes.
- [ ] Memahami pentingnya Connection Draining dan Health Checking.
- [ ] Menghindari ketergantungan pada Sticky Sessions.
