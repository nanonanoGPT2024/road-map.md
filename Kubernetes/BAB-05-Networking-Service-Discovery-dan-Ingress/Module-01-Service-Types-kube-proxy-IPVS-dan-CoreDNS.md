# Module 01: Kubernetes Service Types (ClusterIP, NodePort, LoadBalancer, Headless), kube-proxy, dan CoreDNS

---
[⬅️ Evaluasi & Quiz BAB 04](../BAB-04-Konfigurasi-Secrets-dan-Decoupled-Architecture/BAB-04-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: Ingress & Gateway API ➡️](./Module-02-Ingress-Controllers-cert-manager-dan-Gateway-API.md)
---

## 1. Learning Objective
Setelah menyelesaikan modul ini, pembelajar diharapkan mampu:
1. Memahami mengapa abstraksi **Service** dibutuhkan untuk mengatasi sifat fana (*ephemeral*) dari alamat IP Pod.
2. Menguasai karakteristik dan use case dari empat tipe Service: **ClusterIP**, **NodePort**, **LoadBalancer**, dan **ExternalName**.
3. Menjelaskan evolusi dari objek legacy `Endpoints` ke **EndpointSlices** untuk skalabilitas ribuan pod per-layanan.
4. Menganalisis cara kerja **kube-proxy** dalam menerjemahkan Virtual ClusterIP menjadi aturan jaringan aktual di kernel Linux host (mode **iptables** vs **IPVS**).
5. Memahami arsitektur penemuan layanan internal (**Service Discovery**) menggunakan **CoreDNS**, struktur FQDN (`service.namespace.svc.cluster.local`), serta pemecahan masalah latensi DNS akibat konfigurasi `ndots: 5`.

---

## 2. Prerequisite
- Memahami konsep dasar jaringan komputer (TCP/UDP ports, DNS resolving, routing, iptables NAT) ([DevOps BAB 02](../../DevOps/BAB-02-Jaringan-Protokol-dan-Web-Servers/)).
- Memahami konsep Pod dan selector label ([BAB 02 Module 01](../BAB-02-Pod-Lifecycle-dan-Multi-Container-Patterns/Module-01-Anatomi-Pod-Lifecycle-Probes-dan-Termination.md)).

---

## 3. Concept
Dalam kluster Kubernetes, Pod lahir dan mati secara dinamis (*ephemeral*). Ketika sebuah Pod di-restart oleh Deployment atau dipindahkan ke worker node lain karena kegagalan hardware, Pod baru akan menerima **alamat IP Pod yang berbeda**.

Jika aplikasi frontend Anda mencoba menghubungi backend dengan cara melakukan *hardcode* IP Pod (misal `http://10.244.1.45:8080`), aplikasi akan langsung rusak sesaat setelah Pod backend tersebut mengalami rolling update atau re-scaling.

Untuk memecahkan masalah ini, Kubernetes menyediakan abstraksi **Service**:
- Sebuah Service menetapkan satu alamat IP virtual tunggal yang stabil (**Virtual ClusterIP**) dan nama DNS permanen.
- Service secara dinamis melacak Pod mana saja yang aktif dan sehat menggunakan mekanisme **Label Selector**.
- Ketika traffic dikirim ke ClusterIP, kernel Linux secara otomatis menyeimbangkan beban (*load balancing*) traffic tersebut ke seluruh Pod backend yang terdaftar di **EndpointSlices**.

---

## 4. Why?
1. **Pemisahan Alamat Logis vs Fisik (Decoupled Routing)**: Konsumen layanan (frontend) hanya perlu mengetahui satu nama DNS statis (misal `http://payment-service:8080`), tanpa peduli apakah di belakangnya terdapat 1 Pod, 50 Pod, atau Pod yang sedang berganti IP.
2. **Load Balancing Tingkat Jaringan Layer 4 (L4)**: Kubernetes menyediakan penyeimbang beban TCP/UDP bawaan tanpa perlu memasang hardware load balancer eksternal di dalam kluster.
3. **Integrasi Cloud Provider Otomatis**: Menentukan `type: LoadBalancer` secara otomatis menginstruksikan cloud controller (AWS/GCP/Azure) untuk membuat Network Load Balancer (NLB) publik dengan IP publik statis.

---

## 5. What?
### Taksonomi Tipe-Tipe Service Kubernetes:

| Tipe Service | Cakupan Akses | Cara Kerja | Use Case Utama |
|---|---|---|---|
| **`ClusterIP`** (Default) | Hanya dari dalam kluster (*Internal-only*) | Dialokasikan IP virtual internal dari subnet `service-cluster-ip-range`. | Komunikasi antar microservice internal (Backend, Cache, DB). |
| **`NodePort`** | Dari luar kluster via IP Worker Node | Membuka port khusus (rentang default: `30000-32767`) di **seluruh worker node**. | Akses eksternal sederhana di lab on-premise atau pengujian bare-metal. |
| **`LoadBalancer`** | Dari internet publik | Meminta cloud provider membuat external Load Balancer (AWS NLB/GCP LB) yang meneruskan traffic ke NodePort. | Expose service produksi langsung ke internet jika tanpa Ingress. |
| **`ExternalName`** | Internal mengarah ke Eksternal | Tidak memiliki selector atau IP; mengembalikan DNS CNAME ke domain eksternal. | Mengalihkan request internal `db-svc` ke AWS RDS eksternal `mydb.rds.amazonaws.com`. |
| **`Headless`** (`clusterIP: None`) | Internal (Direct Pod IPs) | Tidak memiliki ClusterIP; CoreDNS langsung mengembalikan A record seluruh Pod IP. | StatefulSets, Kafka, Elasticsearch, database clustering. |

---

## 6. How? Arsitektur Service Discovery & CoreDNS Resolution

```text
[ Pod Frontend: curl http://order-service.production:8080 ]
                          |
                          v (1. Query DNS)
+-----------------------------------------------------------------------------------+
|                        CoreDNS Cluster (10.96.0.10:53)                            |
|  Resolusi FQDN: order-service.production.svc.cluster.local                        |
|  Mengembalikan Virtual ClusterIP: 10.96.45.100                                    |
+-----------------------------------------------------------------------------------+
                          |
                          v (2. Kirim TCP SYN Packet ke 10.96.45.100:8080)
+-----------------------------------------------------------------------------------+
|               Linux Kernel Worker Node (Netfilter / IPVS Table)                   |
|                                                                                   |
|  kube-proxy memprogram EndpointSlices ke dalam IPVS Hash Table:                  |
|  Virtual IP: 10.96.45.100:8080                                                    |
|    -> Destination 1: 10.244.1.20:8080 (Weight: 1)                                 |
|    -> Destination 2: 10.244.2.35:8080 (Weight: 1)                                 |
|                                                                                   |
|  DNAT Kernel: Mengubah Destination IP menjadi 10.244.2.35 (Pod Backend aktual)    |
+-----------------------------------------------------------------------------------+
                          |
                          v (3. Packet Terkirim via CNI)
               [ Pod Backend 2 (10.244.2.35) ]
```

---

## 7. Analogy
Bayangkan Service Kubernetes seperti nomor telepon saluran bantuan sebuah call center:
- **Pod** adalah operator customer service individual yang memegang headset. Mereka bisa berganti shift, cuti sakit, atau digantikan orang baru setiap hari (IP dinamis).
- **ClusterIP Service** adalah nomor telepon kantor pusat (misal: `1-800-CUSTOMER-CARE`). Pelanggan tidak perlu tahu siapa nama operator yang mengangkat telepon. Pelanggan cukup menelpon nomor utama tersebut.
- **`kube-proxy` dan EndpointSlices** adalah mesin PBX switchboard otomatis di kantor yang menyalurkan panggilan masuk ke meja operator mana pun yang saat itu sedang online dan tidak sedang sibuk (*Readiness Probe PASS*).
- **CoreDNS** adalah buku telepon yellow pages yang menerjemahkan nama perusahaan "Customer Care" menjadi nomor `1-800-CUSTOMER-CARE`.

---

## 8. Diagram: Masalah Latensi `ndots: 5` pada CoreDNS

Secara default, file `/etc/resolv.conf` di dalam kontainer Kubernetes berisi:
```text
search default.svc.cluster.local svc.cluster.local cluster.local
options ndots:5
```

```text
Ketika aplikasi memanggil domain eksternal: "api.stripe.com" (Hanya memiliki 2 dot):
Karena 2 < ndots:5, resolver Linux mengira ini adalah nama lokal dan mencoba:
1. Query: api.stripe.com.default.svc.cluster.local -> NXDOMAIN (Gagal! 2ms)
2. Query: api.stripe.com.svc.cluster.local         -> NXDOMAIN (Gagal! 2ms)
3. Query: api.stripe.com.cluster.local             -> NXDOMAIN (Gagal! 2ms)
4. Query: api.stripe.com                           -> 200 OK (Berhasil setelah 4x request!)

Bencana Latensi: Setiap panggilan API eksternal memicu 3x DNS failure query yang membebani CoreDNS!
Solusi Optimasi: Tambahkan titik di akhir nama domain ("api.stripe.com.") ATAU ubah dnsConfig PodSpec.
```

---

## 9. Simple Example: Definisi Service ClusterIP dan NodePort

### 1. Service Internal (`ClusterIP`):
```yaml
apiVersion: v1
kind: Service
metadata:
  name: payment-service
  namespace: production
spec:
  type: ClusterIP
  selector:
    app: payment # Menargetkan Pod yang memiliki label 'app: payment'
  ports:
  - name: http
    port: 8080        # Port yang didengar oleh Service
    targetPort: 8080  # Port aplikasi aktual di dalam kontainer Pod
    protocol: TCP
```

### 2. Service Eksternal (`NodePort`):
```yaml
apiVersion: v1
kind: Service
metadata:
  name: web-nodeport
spec:
  type: NodePort
  selector:
    app: web
  ports:
  - port: 80
    targetPort: 80
    nodePort: 30080 # Port yang dibuka di seluruh IP worker node fisik (30000-32767)
```

---

## 10. Practical Example: Mengakses Database Eksternal via `ExternalName`

Alih-alih melakukan hardcode alamat host AWS RDS di kode aplikasi, gunakan Service `ExternalName`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: cloud-db-service
  namespace: production
spec:
  type: ExternalName
  externalName: my-postgres-cluster.c48f9a2.ap-southeast-1.rds.amazonaws.com
```

Aplikasi di dalam kluster cukup menghubungkan database ke host: `cloud-db-service.production.svc.cluster.local`. Jika suatu saat database dipindahkan ke Google Cloud SQL, Anda cukup mengubah baris `externalName` tanpa perlu mengubah kode atau konfigurasi aplikasi!

---

## 11. Real World Example: Migrasi dari Endpoints ke EndpointSlices
Di kluster enterprise dengan 5.000 replika Pod untuk satu Service raksasa:
- **Arsitektur Legacy (Endpoints)**: Seluruh 5.000 IP Pod disimpan di dalam satu objek JSON `Endpoints` tunggal. Setiap kali 1 Pod mati atau restart, seluruh objek raksasa berukuran 2MB tersebut di-generate ulang dan dikirimkan (*broadcast*) ke seluruh 500 worker node di kluster, membebani jaringan apiserver hingga gigabytes per detik!
- **Arsitektur Modern (EndpointSlices)**: Kubernetes secara otomatis memecah 5.000 IP tersebut menjadi potongan-potongan (*slices*) kecil yang masing-masing hanya berisi maksimal 100 endpoint. Pembaruan 1 Pod hanya memodifikasi 1 slice kecil, menghemat bandwidth jaringan hingga 98%.

---

## 12. Trade-offs: Service Types Matrix

| Tipe Service | Keamanan Jaringan | Kompleksitas Biaya | Fleksibilitas Routing | Use Case |
|---|---|---|---|---|
| **ClusterIP** | ⭐ Paling Aman (Isolasi internal) | Gratis ($0) | Terbatas internal | Seluruh microservice privat. |
| **NodePort** | ⚠️ Berisiko (Port host terbuka ke publik) | Gratis ($0) | Kaku (Hanya port 30000-32767) | Lab bare-metal, VPN internal. |
| **LoadBalancer** | ✅ Terkendali (Protected by Cloud LB) | Mahal ($15-$25/bulan per Service) | Layer 4 TCP/UDP saja | Traffic non-HTTP (database, streaming raw socket). |
| **Ingress** | ✅ Sangat Aman (Reverse proxy L7) | Murah (1 Cloud LB untuk ratusan Service) | Sangat Fleksibel (Path, Host, SSL) | Seluruh Web HTTP/HTTPS APIs (Bahas di Module 02). |

---

## 13. When To Use
- Gunakan **ClusterIP** sebagai pilihan default untuk 90% service di dalam kluster Anda.
- Gunakan **EndpointSlices** untuk memantau status kesehatan endpoint secara detail.
- Gunakan **ExternalName** untuk abstraksi dependensi pihak ketiga di luar kluster.

---

## 14. When NOT To Use
- **JANGAN membuat puluhan Service bertipe `LoadBalancer` di cloud publik (AWS/GCP)**: Setiap Service `type: LoadBalancer` akan membuat 1 cloud load balancer fisik baru yang memakan biaya puluhan dollar per bulan. Gunakan **Ingress Controller** tunggal untuk berbagi 1 Load Balancer ke puluhan Service!
- Jangan gunakan NodePort langsung di production internet publik tanpa firewall WAF di depannya.

---

## 15. Common Mistakes
1. **TargetPort Tidak Cocok dengan ContainerPort**: Service mendengarkan port 80 dan mengarahkan ke `targetPort: 8080`, padahal aplikasi di dalam kontainer mendengarkan port 3000. Hasilnya: `Connection Refused`.
2. **Selector Label Salah Ketik**: Menulis `selector: app: paymnt` (typo). Service akan terbentuk normal, tetapi `EndpointSlices` akan kosong melompong (0 Pod terhubung).
3. **Mengabaikan Masalah `ndots: 5`**: Aplikasi yang melakukan jutaan panggilan ke domain eksternal mengalami latensi tinggi karena CoreDNS kelebihan beban melayani query NXDOMAIN berulang.

---

## 16. Best Practices
### Must Have
- Selalu beri nama pada port (`name: http`, `name: grpc`) jika sebuah Service mendefinisikan lebih dari satu port (**Multi-Port Service**).
- Verifikasi bahwa `Endpoints` atau `EndpointSlice` terisi setelah membuat Service:
  ```bash
  kubectl get endpoints <nama-service>
  kubectl get endpointslices -l kubernetes.io/service-name=<nama-service>
  ```

### Recommended
- Optimalkan panggilan DNS eksternal pada Pod yang intensif jaringan menggunakan konfigurasi `dnsConfig`:
  ```yaml
  dnsConfig:
    options:
    - name: ndots
      value: "2"
  ```
- Gunakan session affinity jika aplikasi legacy membutuhkan sticky session:
  ```yaml
  spec:
    sessionAffinity: ClientIP
    sessionAffinityConfig:
      clientIP:
        timeoutSeconds: 10800
  ```

### Advanced
- Di kluster skala besar (> 1.000 node), aktifkan **NodeLocal DNSCache** (DaemonSet cache DNS lokal di setiap node) untuk memangkas latensi query CoreDNS dan mencegah paket drop UDP.

---

## 17. Troubleshooting Guide
### Problem 1: Service tidak bisa dihubungi dari Pod lain (`Connection timed out`)
- **Langkah Diagnosa**:
  1. Periksa apakah Service memiliki endpoint aktif:
     ```bash
     kubectl get endpoints <nama-service>
     ```
     Jika `<none>`, periksa kesesuaian label di Pod (`kubectl get pods --show-labels`) dengan `spec.selector` Service.
  2. Periksa apakah Pod backend dalam kondisi `Ready` (`readinessProbe` lolos).

### Problem 2: Resolusi nama domain Service gagal (`Could not resolve host`)
- **Penyebab**: CoreDNS crash atau salah penulisan namespace.
- **Diagnosa**:
  ```bash
  # Uji resolusi via toolbox pod
  kubectl run dns-test --rm -it --image=busybox:1.36 -- nslookup <nama-service>.<namespace>.svc.cluster.local
  # Periksa status pod CoreDNS
  kubectl get pods -n kube-system -l k8s-app=kube-dns
  ```

---

## 18. Exercises
### Level: Easy
1. Buat Deployment Nginx dengan 2 replika.
2. Buat Service bertipe `ClusterIP` untuk mengekspos Deployment tersebut pada port 80.
3. Jalankan pod pengujian sementara `busybox` dan lakukan `wget -qO- http://<nama-service>` untuk memvalidasi akses internal.

### Level: Medium
1. Periksa resource `EndpointSlice` yang otomatis dibuat oleh Kubernetes untuk Service Anda:
   `kubectl get endpointslices`
2. Periksa daftar alamat IP Pod yang terdaftar di dalam EndpointSlice tersebut menggunakan `kubectl describe endpointslice <nama-slice>`.

### Level: Hard
1. Buat Service bertipe `ExternalName` yang memetakan nama internal `mock-api` ke domain `httpbin.org`.
2. Lakukan pengujian HTTP request dari dalam Pod ke `http://mock-api/get` dan verifikasi bahwa response JSON berhasil diterima dari server httpbin.

---

## 19. Challenge
Rancang arsitektur jaringan microservices hybrid untuk transaksi perbankan:
- Frontend Web publik diakses via Service Ingress.
- Core Banking API berjalan internal di kluster (`ClusterIP`).
- Mainframe Legacy di data center on-premise dihubungkan melalui Service `ExternalName`.
- Tuliskan konfigurasi Service dan optimasi `dnsConfig` pada Pod frontend untuk meminimalkan latensi resolusi DNS ke Core Banking dan Mainframe.

---

## 20. Summary
- **Service** menyediakan alamat IP virtual stabil (**ClusterIP**) dan nama DNS permanen di atas Pod-pod yang bersifat fana.
- **EndpointSlices** menyimpan daftar IP Pod target secara terpotong (*chunked*) untuk skalabilitas tinggi.
- **kube-proxy** bertindak sebagai perakit aturan routing kernel Linux (iptables / IPVS).
- **CoreDNS** menyelesaikan query nama layanan dengan struktur FQDN: `<service>.<namespace>.svc.cluster.local`.
- Waspadai masalah latensi **`ndots: 5`** saat melakukan pemanggilan domain publik dari dalam Pod.

---
[⬅️ Evaluasi & Quiz BAB 04](../BAB-04-Konfigurasi-Secrets-dan-Decoupled-Architecture/BAB-04-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: Ingress & Gateway API ➡️](./Module-02-Ingress-Controllers-cert-manager-dan-Gateway-API.md)
---
