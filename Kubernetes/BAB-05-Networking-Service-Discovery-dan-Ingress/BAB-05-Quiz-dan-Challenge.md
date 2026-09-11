# BAB 05 — Quiz & Chapter Challenge: Kubernetes Networking, Service Discovery, & Ingress

---
[⬅️ Module 02: Ingress & Gateway API](./Module-02-Ingress-Controllers-cert-manager-dan-Gateway-API.md) | [📋 Silabus Induk](../README.md) | [BAB 06 Module 01: CNI Calico vs Cilium ➡️](../BAB-06-Network-Security-CNI-dan-NetworkPolicies/Module-01-CNI-Calico-vs-Cilium-eBPF-dan-Routing.md)
---

Dokumen ini menguji penguasaan Anda terhadap arsitektur jaringan internal Kubernetes (Service Types, kube-proxy, IPVS, EndpointSlices, CoreDNS, ndots:5) serta gerbang masuk eksternal tepi kluster (Ingress Controllers, cert-manager TLS ACME, dan Kubernetes Gateway API).

---

## Bagian 1: Basic Quiz (5 Pertanyaan)

### Soal 1
Mengapa kita tidak boleh menghubungkan aplikasi langsung ke alamat IP Pod (misal `10.244.1.45`), melainkan harus melalui objek Service?
- A. Karena alamat IP Pod hanya bisa dibaca oleh sistem operasi Linux.
- B. Karena alamat IP Pod bersifat fana (*ephemeral*); Pod dapat mati, berpindah node, atau di-restart kapan saja dan akan mendapatkan IP baru, sedangkan Service menyediakan IP Virtual stabil dan nama DNS permanen.
- C. Karena IP Pod mengenakan biaya tambahan per megabyte.
- D. Karena Docker melarang komunikasi antar Pod.

### Soal 2
Tipe Service bawaan default manakah yang hanya bisa diakses dari dalam internal kluster dan tidak membuka port publik ke internet?
- A. `NodePort`
- B. `LoadBalancer`
- C. `ClusterIP`
- D. `ExternalName`

### Soal 3
Apa perbedaan mendasar antara routing Layer 4 (Service bertipe `LoadBalancer`) dengan routing Layer 7 (**Ingress**)?
- A. Service LoadBalancer hanya melihat paket transport TCP/UDP tanpa bisa membaca URL path atau host domain, sedangkan Ingress adalah reverse proxy aplikasi yang dapat membaca Host header (`api.domain.com`), Path (`/checkout`), dan melakukan terminasi SSL/TLS.
- B. Ingress hanya bisa digunakan untuk game online.
- C. Service LoadBalancer gratis, sedangkan Ingress selalu berbayar.
- D. Ingress tidak mendukung HTTPS.

### Soal 4
Bagaimana `cert-manager` mengotomatisasi sertifikat SSL/TLS dari Let's Encrypt saat dipasangkan dengan Ingress?
- A. cert-manager membayar lisensi SSL ke otoritas sertifikat komersial.
- B. cert-manager mendeteksi annotasi Ingress, menjalankan tantangan ACME HTTP-01 otomatis untuk memvalidasi kepemilikan domain, lalu menyimpan sertifikat x509 yang diterbitkan ke dalam Secret `kubernetes.io/tls`.
- C. cert-manager memaksa pengguna menggunakan self-signed cert yang tidak aman.
- D. cert-manager menghapus protokol HTTPS dari kluster.

### Soal 5
Apa keuntungan utama dari **EndpointSlices** dibandingkan objek legacy `Endpoints` pada kluster berskala besar dengan ribuan Pod?
- A. EndpointSlices membatasi traffic internet menjadi 10 Mbps.
- B. EndpointSlices memecah ribuan IP Pod target ke dalam potongan-potongan (*slices*) kecil berisi maksimal 100 endpoint, sehingga perubahan 1 Pod tidak memicu broadcast objek raksasa ke seluruh node kluster.
- C. EndpointSlices mengubah bahasa pemrograman Pod menjadi C++.
- D. EndpointSlices menghapus kebutuhan kube-proxy.

---

## Bagian 2: Intermediate Quiz (5 Pertanyaan)

### Soal 6
Dalam arsitektur CoreDNS, mengapa konfigurasi default `options ndots:5` pada `/etc/resolv.conf` di dalam kontainer dapat memicu masalah latensi tinggi saat aplikasi memanggil API publik seperti `api.github.com`?
- A. Karena CoreDNS akan memblokir domain eksternal secara otomatis.
- B. Karena domain `api.github.com` hanya memiliki 2 dot ($2 < 5$), sehingga resolver DNS Linux akan mencoba menempelkan seluruh search domain internal kluster (`.default.svc...`, `.svc...`, `.cluster.local`) dan memicu 3x kegagalan query NXDOMAIN sebelum akhirnya menanyakan domain publik.
- C. Karena angka 5 membatasi koneksi internet maksimal 5 user.
- D. Karena github.com tidak memiliki server DNS.

### Soal 7
Apa keunggulan arsitektural dari **Kubernetes Gateway API** (seperti `GatewayClass`, `Gateway`, `HTTPRoute`) dibandingkan model `Ingress` klasik?
- A. Gateway API membagi tanggung jawab secara modular sesuai peran tim (Platform Ops mengelola Gateway & TLS, App Dev mengelola HTTPRoute & Traffic Splitting), serta mendukung multi-protokol (gRPC, TCP, UDP).
- B. Gateway API menghilangkan kebutuhan koneksi internet.
- C. Gateway API hanya bisa berjalan di laptop macOS.
- D. Gateway API menggantikan seluruh peran kube-scheduler.

### Soal 8
Bagaimana cara kerja Service bertipe **`ExternalName`**?
- A. Membuka port 80 di seluruh worker node fisik.
- B. Tidak memiliki selector Pod atau ClusterIP; sebaliknya, CoreDNS mengembalikan record CNAME langsung yang mengarahkan koneksi ke nama domain eksternal (misal: `mydb.rds.amazonaws.com`).
- C. Membuat cloud load balancer baru di AWS.
- D. Menghubungkan Pod ke satelit.

### Soal 9
Mengapa di lingkungan cloud publik (AWS/GCP), membuat 30 Service berbeda yang masing-masing bertipe `type: LoadBalancer` dianggap sebagai pemborosan arsitektur (anti-pattern biaya)?
- A. Karena cloud provider akan membatasi akun Anda hingga maksimal 5 Service.
- B. Karena setiap Service `LoadBalancer` akan membuat 1 instance Cloud Load Balancer independen yang masing-masing memakan biaya bulanan (~$20/bulan/LB), padahal 1 Ingress Controller tunggal dapat melayani ke-30 Service tersebut di balik 1 Load Balancer saja.
- C. Karena port 80 hanya boleh digunakan satu kali di seluruh dunia.
- D. Karena latency LoadBalancer cloud selalu di atas 10 detik.

### Soal 10
Mengapa saat melakukan pengujian implementasi cert-manager baru kita sangat disarankan menggunakan `ClusterIssuer` ber-server **Let's Encrypt Staging** terlebih dahulu sebelum menggunakan Production?
- A. Karena server staging tidak membutuhkan koneksi internet.
- B. Karena Let's Encrypt Production menerapkan batas laju ketat (*strict rate limits* - maksimal 5 kegagalan per jam), di mana jika konfigurasi Anda salah, domain Anda dapat diblokir selama 7 hari penuh.
- C. Karena server staging memberikan sertifikat berbayar.
- D. Karena server production tidak mendukung Nginx.

---

## Bagian 3: Scenario-Based Questions (3 Skenario)

### Skenario 1: Bencana Lonjakan Tagihan Cloud Akibat Typo Service Type
Sebuah tim pengembang meluncurkan 40 microservices baru. Di setiap file manifest service, developer baru menuliskan `type: LoadBalancer` alih-alih `type: ClusterIP` karena mengira itu adalah cara wajib agar service bisa diakses antar-Pod di kluster.
Di akhir bulan, tagihan AWS melonjak sebesar $1.000 hanya untuk 40 Network Load Balancers yang tidak pernah menerima traffic dari internet.
- **Pertanyaan**: Jelaskan mengapa 40 Service internal tidak membutuhkan `type: LoadBalancer`, dan tunjukkan bagaimana arsitektur `ClusterIP` + 1 Ingress Controller tunggal dapat menghemat $960/bulan dari tagihan tersebut!

### Skenario 2: Latensi Pembayaran Melonjak Akibat DNS `ndots: 5`
Sebuah sistem payment gateway memproses 2.000 transaksi per detik. Setiap transaksi memanggil API bank eksternal `api.bca.co.id`.
Metrik observabilitas menunjukkan bahwa latensi pemrosesan transaksi melonjak dari 50ms menjadi 350ms, dan CPU CoreDNS di namespace `kube-system` mencapai 95%.
- **Pertanyaan**: Analisis bagaimana konfigurasi `ndots: 5` bertanggung jawab atas lonjakan latensi ini, dan berikan 2 opsi solusi teknis (solusi kode FQDN trailing dot dan solusi deklaratif `dnsConfig` di PodSpec)!

### Skenario 3: Rilis Canary 90:10 Menggunakan Gateway API
Sebuah fintech ingin merilis fitur checkout v2 secara bertahap:
- 90% traffic pengguna dialihkan ke `payment-v1`.
- 10% traffic pengguna dialihkan ke `payment-v2`.
- Namun, jika tester QA mengirimkan request dengan header khusus `X-Beta-Tester: true`, request tersebut harus 100% dialihkan ke `payment-v2`.
- **Pertanyaan**: Tuliskan manifest deklaratif `HTTPRoute` Gateway API lengkap yang mengimplementasikan aturan routing berbobot dan pencocokan header tersebut secara presisi!

---

## Bagian 4: Chapter Challenge

### Tantangan Praktis: Production Edge Ingress & Gateway API Architect
1. **Skenario**:
   Anda diminta membangun infrastruktur gerbang masuk terpadu untuk platform perbankan:
   - Sebuah Ingress Controller Nginx dengan terminasi SSL HTTPS otomatis via cert-manager.
   - Rute `/api/v1/auth` diarahkan ke Service `auth-svc` (ClusterIP).
   - Rute `/api/v1/transfer` diarahkan ke HTTPRoute Gateway API dengan canary split (85% v1, 15% v2).
   - Layanan reporting lama di cloud eksternal dihubungkan via Service `ExternalName`.
2. **Deliverables**:
   - Manifest `cluster-issuer.yaml` (Let's Encrypt Prod).
   - Manifest `ingress-edge.yaml` dengan TLS auto-provisioning.
   - Manifest `gateway-canary-route.yaml`.
   - Manifest `external-legacy-service.yaml`.

---

## Bagian 5: Knowledge Check & Checklist

### Saya Harus Memahami:
- [ ] Mengapa Service ClusterIP dibutuhkan di atas Pod yang fana.
- [ ] Perbedaan 4 tipe Service: ClusterIP, NodePort, LoadBalancer, ExternalName.
- [ ] Mengapa EndpointSlices menggantikan Endpoints pada kluster berskala besar.
- [ ] Cara kerja kube-proxy dalam memprogram kernel host (iptables vs IPVS).
- [ ] Struktur penamaan resolusi DNS CoreDNS (`svc.cluster.local`).
- [ ] Masalah latensi `ndots: 5` pada pemanggilan domain publik dari Pod.
- [ ] Perbedaan Layer 4 (Service) vs Layer 7 (Ingress).
- [ ] Alur kerja automasi sertifikat SSL cert-manager via ACME HTTP-01.
- [ ] Arsitektur berorientasi peran Kubernetes Gateway API (`Gateway` vs `HTTPRoute`).

### Saya Tidak Perlu Menghafal:
- Nomor port IANA seluruh aplikasi pihak ketiga.
- Seluruh spesifikasi sintaks protokol ACME RFC 8555.

### Saya Harus Bisa Melakukan:
- [ ] Menulis manifest Service ClusterIP, NodePort, dan ExternalName.
- [ ] Memeriksa dan men-debug EndpointSlices dengan `kubectl get endpointslices`.
- [ ] Mengonfigurasi `dnsConfig: options: ndots: 2` pada Pod intensif jaringan.
- [ ] Menulis manifest Ingress lengkap dengan host, path, dan TLS annotasi cert-manager.
- [ ] Menulis manifest Gateway API HTTPRoute dengan aturan pembagian bobot traffic (*weighted traffic split*).

---
[⬅️ Module 02: Ingress & Gateway API](./Module-02-Ingress-Controllers-cert-manager-dan-Gateway-API.md) | [📋 Silabus Induk](../README.md) | [BAB 06 Module 01: CNI Calico vs Cilium ➡️](../BAB-06-Network-Security-CNI-dan-NetworkPolicies/Module-01-CNI-Calico-vs-Cilium-eBPF-dan-Routing.md)
---
