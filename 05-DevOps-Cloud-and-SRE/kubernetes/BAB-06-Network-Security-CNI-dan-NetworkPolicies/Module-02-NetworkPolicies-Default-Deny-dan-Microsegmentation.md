# Module 02: Kubernetes NetworkPolicies, Default-Deny, dan Arsitektur Mikrosegmentasi Zero-Trust

---
[⬅️ Module 01: CNI Calico vs Cilium](./Module-01-CNI-Calico-vs-Cilium-eBPF-dan-Routing.md) | [📋 Silabus Induk](../README.md) | [Evaluasi & Quiz BAB 06 ➡️](./BAB-06-Quiz-dan-Challenge.md)
---

## 1. Learning Objective
Setelah menyelesaikan modul ini, pembelajar diharapkan mampu:
1. Memahami postur keamanan jaringan bawaan (*default network posture*) Kubernetes yang sepenuhnya terbuka tanpa pembatas (*flat & open by default*).
2. Memverifikasi prasyarat penting penegakan kebijakan: mengapa CNI yang mendukung NetworkPolicy (seperti Calico atau Cilium) wajib terpasang agar aturan tidak diabaikan secara diam-diam.
3. Menguasai sintaksis deklaratif **`NetworkPolicy`** untuk menyaring lalu lintas masuk (**Ingress**) dan keluar (**Egress**).
4. Menerapkan strategi **Zero-Trust Network**: Kebijakan **Default-Deny All Ingress** dan **Default-Deny All Egress** (beserta pengecualian vital port CoreDNS 53).
5. Merancang arsitektur **Mikrosegmentasi Jaringan 3-Tier** (Frontend -> Backend -> Database) yang mengisolasi ledakan peretasan (*blast radius containment*).

---

## 2. Prerequisite
- Memahami konsep CNI dan Pod IP Routing ([Module 01 BAB 06](Module-01-CNI-Calico-vs-Cilium-eBPF-dan-Routing.md)).
- Memahami Service ClusterIP dan CoreDNS ([BAB 05 Module 01](../BAB-05-Networking-Service-Discovery-dan-Ingress/Module-01-Service-Types-kube-proxy-IPVS-dan-CoreDNS.md)).
- Pemahaman aturan firewall (Ingress/Egress, CIDR notation, protokol TCP/UDP).

---

## 3. Concept
Secara default, jaringan Kubernetes beroperasi dengan filosofi **"Semua Boleh Berbicara ke Semua" (*Permissive Network*)**:
- Setiap Pod di dalam namespace apa pun dapat mengirimkan paket ke Pod mana pun di namespace lain.
- Pod frontend toko online dapat membuka koneksi TCP langsung ke database internal, atau bahkan ke Pod etcd di namespace `kube-system`.

Jika seorang peretas berhasil mengeksploitasi celah Remote Code Execution (RCE) pada satu Pod frontend yang terpapar ke internet, peretas dapat dengan leluasa memindai seluruh jaringan internal kluster (*lateral movement*) dan mencuri data database sensitif tanpa hambatan!

**Kubernetes NetworkPolicy** adalah firewall virtual terdistribusi di level Layer 3/Layer 4 yang dikendalikan oleh CNI. NetworkPolicy memungkinkan kita mengisolasi Pod dan menerapkan prinsip **Zero-Trust**: seluruh lalu lintas ditutup secara default, dan hanya koneksi eksplisit yang diizinkan (*whitelisting*).

---

## 4. Why?
1. **Pembatasan Radius Ledakan Peretasan (*Blast Radius Containment*)**: Jika kontainer web frontend terkompromikan oleh hacker, NetworkPolicy mencegah hacker tersebut melakukan port scanning atau koneksi langsung ke database PostgreSQL di backend.
2. **Kepatuhan Standar Industri (PCI-DSS & SOC 2 Compliance)**: Regulasi kartu kredit mewajibkan segmentasi ketat antara lingkungan pemrosesan data kartu (*Cardholder Data Environment*) dengan jaringan umum.
3. **Pencegahan Eksfiltrasi Data (Egress Filtering)**: Menutup koneksi keluar (*Egress*) mencegah malware di dalam kontainer menghubungi server command-and-control (C2) milik hacker di internet.

---

## 5. What?
### Tiga Pilar Pemilih (*Selectors*) di NetworkPolicy:

Aturan `from` (Ingress) dan `to` (Egress) dapat dibangun dari kombinasi tiga kriteria:
1. **`podSelector`**: Memilih Pod berdasarkan label Pod di namespace yang sama (misal: `app: payment-api`).
2. **`namespaceSelector`**: Memilih seluruh Pod yang berada di namespace dengan label tertentu (misal: `env: production` atau `kubernetes.io/metadata.name: frontend`).
3. **`ipBlock`**: Membatasi rentang CIDR IP eksternal di luar kluster (misal: hanya boleh menghubungi gateway kantor `192.168.10.0/24`, kecuali subnet tertentu).

> ⚠️ **PERINGATAN KRUSIAL:**
> Objek `NetworkPolicy` **TIDAK AKAN MEMBERIKAN EFEK APAPUN** jika kluster Anda menggunakan CNI dasar seperti **Flannel** standar yang tidak mendukung penegakan kebijakan. Anda **WAJIB** menggunakan CNI berkemampuan policy seperti **Calico**, **Cilium**, atau **Weave Net**.

---

## 6. How? Arsitektur Mikrosegmentasi 3-Tier Zero-Trust

```text
  [ Internet Traffic ]
           |
           v
  +-------------------------------------------------------------+
  |                   TIER 1: FRONTEND PODS                     |
  |  Label: app=frontend                                        |
  |  - Ingress: ALLOW Port 80/443 dari Ingress Controller       |
  |  - Egress : ALLOW hanya ke Backend (Port 8080) & CoreDNS    |
  +-------------------------------------------------------------+
                               |
                               v (TCP Port 8080)
  +-------------------------------------------------------------+
  |                   TIER 2: BACKEND API PODS                  |
  |  Label: app=backend                                         |
  |  - Ingress: ALLOW hanya dari Pods dengan label app=frontend |
  |  - Egress : ALLOW hanya ke Database (Port 5432) & CoreDNS   |
  +-------------------------------------------------------------+
                               |
                               v (TCP Port 5432)
  +-------------------------------------------------------------+
  |                   TIER 3: DATABASE PODS                     |
  |  Label: app=database                                        |
  |  - Ingress: ALLOW HANYA dari Pods dengan label app=backend  |
  |  - Egress : DENY ALL! (Database tidak boleh koneksi keluar) |
  +-------------------------------------------------------------+
                               |
                               x (Hacker di Frontend mencoba hubungi Database)
                               [ PACKET DROPPED BY CNI KERNEL FILTER ]
```

---

## 7. Analogy
Bayangkan sebuah kantor perbankan yang aman:
- **Jaringan Bawaan K8s (Tanpa Policy)** adalah gedung tanpa pintu dan tanpa satpam. Siapa pun yang masuk ke ruang lobi (Frontend) bisa langsung berjalan bebas masuk ke ruang brankas uang tunai (Database) di lantai basement.
- **Default-Deny Ingress & Egress** adalah mengunci seluruh pintu gedung secara otomatis. Setiap ruangan terkunci dari dalam dan luar.
- **NetworkPolicy Spesifik** adalah kartu akses magnetik (badge). Kartu resepsionis hanya bisa membuka pintu ruang tunggu backend, dan hanya kartu manajer backend yang memiliki izin membuka pintu brankas database.

---

## 8. Diagram: Jebakan Fatal Egress Tanpa CoreDNS Port 53

```text
Konfigurasi Salah: Default Deny Egress tanpa mengizinkan CoreDNS
+-------------------------------------------------------------------------+
| Pod Backend (Egress Deny All)                                           |
|   Aplikasi mencoba koneksi ke: "postgres.production.svc.cluster.local"   |
|   1. Langkah pertama: Kirim query DNS UDP Port 53 ke CoreDNS            |
|   2. DIBLOKIR SENDIRI OLEH EGRESS DENY POLICY!                           |
|   3. Aplikasi crash: "EAI_AGAIN / Could not resolve host name"          |
+-------------------------------------------------------------------------+

Konfigurasi Benar: Selalu sertakan aturan Egress ke Port 53 kube-dns
spec:
  egress:
  - ports:
    - protocol: UDP
      port: 53
    - protocol: TCP
      port: 53
    to:
    - namespaceSelector: {}
      podSelector:
        matchLabels:
          k8s-app: kube-dns
```

---

## 9. Simple Example: Default Deny All Ingress & Egress

Terapkan manifest ini di setiap namespace produksi untuk mengaktifkan postur **Zero-Trust Baseline**:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: production
spec:
  podSelector: {} # Mengunci SELURUH Pod di dalam namespace ini!
  policyTypes:
  - Ingress
  - Egress
```
*Hasil: Seluruh koneksi masuk dan keluar di namespace `production` terputus total hingga ada NetworkPolicy whitelist yang membukanya secara spesifik!*

---

## 10. Practical Example: Manifest Mikrosegmentasi Lengkap

### 1. Kebijakan Keamanan Database (Hanya Terima Traffic dari Backend):
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-backend-to-db
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: database # Berlaku untuk Pod Database
  policyTypes:
  - Ingress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: backend # HANYA izinkan Pod berlabel app: backend
    ports:
    - protocol: TCP
      port: 5432 # HANYA port PostgreSQL
```

### 2. Kebijakan Keamanan Backend API (Terima dari Frontend, Kirim ke DB + DNS):
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: backend-security-policy
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: backend
  policyTypes:
  - Ingress
  - Egress
  # Ingress: Buka port 8080 hanya untuk Frontend
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: frontend
    ports:
    - protocol: TCP
      port: 8080
  # Egress: Hanya boleh keluar ke Database dan CoreDNS
  egress:
  # Rute 1: Keluar ke Database
  - to:
    - podSelector:
        matchLabels:
          app: database
    ports:
    - protocol: TCP
      port: 5432
  # Rute 2: Keluar ke CoreDNS (Wajib agar DNS resolving tidak mati!)
  - to:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: kube-system
      podSelector:
        matchLabels:
          k8s-app: kube-dns
    ports:
    - protocol: UDP
      port: 53
```

---

## 11. Real World Example: Peretasan Cryptomining Terisolasi di E-Commerce
Sebuah toko online mengalami peretasan di mana sebuah container frontend Node.js disusupi skrip remote code execution (RCE) dari vulnerability npm package:
- Hacker berhasil mendapatkan shell di container frontend dan mengunduh script scanner `masscan`.
- Hacker mencoba memindai port database MySQL dan Redis di seluruh kluster.
- **Peran NetworkPolicy**: Karena namespace dilindungi oleh aturan Ingress/Egress ketat, kernel Linux host (via Calico iptables / Cilium eBPF) secara instan men-drop seluruh paket SYN yang menuju ke port 3306 dan 6379.
- Hacker tidak bisa melakukan koneksi keluar (*Egress C2 block*) dan tidak bisa menyentuh database (*Lateral Movement blocked*).
- **Hasil**: Serangan terisolasi 100% di satu kontainer stateless frontend, data pelanggan di database aman tanpa kebocoran.

---

## 12. Trade-offs: Whitelist NetworkPolicy

| Aspek | Tanpa NetworkPolicy (Open) | Dengan Zero-Trust NetworkPolicy |
|---|---|---|
| **Keamanan Jaringan** | ❌ Sangat Buruk (Lateral movement bebas) | ⭐ Sangat Tinggi (Mikrosegmentasi terisolasi) |
| **Beban Operasional Developer** | Sangat Rendah (Semua langsung konek) | Lebih Tinggi (Wajib mendefinisikan port & selector) |
| **Resiko False Positives (Downtime)** | Rendah | Tinggi jika lupa mengizinkan CoreDNS Port 53 |
| **Overhead Komputasi** | Nol | Ringan di Calico (iptables rules), Mendekati 0 di Cilium eBPF |

---

## 13. When To Use
- Terapkan **Default-Deny Ingress & Egress** di seluruh namespace lingkungan **Staging** dan **Production**.
- Terapkan **Mikrosegmentasi 3-Tier** pada aplikasi yang memproses data finansial, data medis, atau identitas pribadi (PII).
- Terapkan **Egress IPBlock Whitelisting** jika aplikasi hanya diizinkan berkomunikasi dengan payment gateway spesifik (misal Stripe / Midtrans IP CIDR).

---

## 14. When NOT To Use
- Jangan terapkan NetworkPolicy di kluster lokal yang menggunakan CNI dasar seperti **Flannel murni** tanpa driver policy, karena aturan akan tampak sukses di `kubectl` padahal sama sekali tidak ditegakkan di kernel!
- Jangan aktifkan `default-deny-egress` sebelum Anda menyiapkan policy allow untuk CoreDNS port 53.

---

## 15. Common Mistakes
1. **Lupa Membuka Port DNS (UDP 53)**: Mengaktifkan Egress policy lalu mendapati seluruh aplikasi crash karena tidak bisa me-resolve nama host database (`getaddrinfo ENOTFOUND`).
2. **Koma vs Dash pada YAML Selector (OR vs AND logic)**:
   ```yaml
   # Logika OR (Salah satu cocok):
   from:
   - namespaceSelector: { matchLabels: { env: prod } }
   - podSelector: { matchLabels: { app: api } }

   # Logika AND (Harus cocok keduanya - perhatikan ketiadaan tanda minus kedua):
   from:
   - namespaceSelector: { matchLabels: { env: prod } }
     podSelector: { matchLabels: { app: api } }
   ```
3. **Mengira NetworkPolicy berlaku di namespace lain**: Objek NetworkPolicy bersifat *namespaced*. Anda harus membuat policy di namespace tempat Pod target berada.

---

## 16. Best Practices
### Must Have
- Selalu cantumkan blok `policyTypes: [Ingress, Egress]` secara eksplisit.
- Selalu berikan label `kubernetes.io/metadata.name: <nama-namespace>` pada namespace agar mudah diseleksi oleh `namespaceSelector`.
- Sertakan aturan allow untuk traffic DNS ke `kube-system` pada setiap egress policy.

### Recommended
- Gunakan tool open-source visualisasi seperti **Cilium Hubble** atau **NetworkPolicy Editor (Cilium Network Policy Viewer)** untuk memvalidasi aturan firewall sebelum di-apply.
- Beri label terstandarisasi pada seluruh Pod (`app.kubernetes.io/name`, `tier: frontend|backend|database`).

### Advanced
- Di kluster dengan Cilium, gunakan **`CiliumNetworkPolicy` (Layer 7 Filtering)** untuk membatasi traffic HTTP spesifik:
  ```yaml
  apiVersion: cilium.io/v2
  kind: CiliumNetworkPolicy
  spec:
    rules:
    - toPorts:
      - ports: [{ port: "8080", protocol: TCP }]
        rules:
          http: [{ method: "GET", path: "/public/.*" }] # Drop seluruh POST/DELETE!
  ```

---

## 17. Troubleshooting Guide
### Problem 1: Pod tiba-tiba tidak bisa menghubungi database setelah NetworkPolicy di-apply
- **Langkah Diagnosa**:
  1. Periksa label Pod backend dan database:
     ```bash
     kubectl get pods --show-labels -n production
     ```
  2. Periksa apakah ada NetworkPolicy yang aktif di namespace tersebut:
     ```bash
     kubectl get networkpolicies -n production
     ```
  3. Periksa apakah port dan selector cocok 100%.

### Problem 2: NetworkPolicy sudah di-apply tetapi traffic terlarang tetap tembus
- **Penyebab**: CNI kluster Anda tidak mendukung NetworkPolicy enforcement!
- **Diagnosa**:
  ```bash
  kubectl get pods -n kube-system
  # Jika hanya ada "kube-flannel" tanpa Calico/Cilium, policy TIDAK AKAN PERNAH BEKERJA!
  ```
- **Solusi**: Install Calico atau Cilium di atas kluster Anda.

---

## 18. Exercises
### Level: Easy
1. Buat namespace baru `security-lab`.
2. Jalankan dua pod Nginx: satu berlabel `role=frontend` dan satu berlabel `role=backend`.
3. Terapkan NetworkPolicy yang hanya mengizinkan `role=frontend` mengakses port 80 di `role=backend`.

### Level: Medium
1. Terapkan kebijakan `default-deny-all` di namespace `security-lab`.
2. Uji coba bahwa koneksi ping dan curl antar Pod terputus total.
3. Tambahkan aturan Egress khusus ke CoreDNS port 53 dan buktikan bahwa resolusi DNS kembali berfungsi.

### Level: Hard
1. Rancang aturan NetworkPolicy 3-tier lengkap (Frontend, Backend, Database).
2. Uji menggunakan pod `busybox` ilegal tanpa label dan buktikan bahwa paket koneksinya langsung di-drop saat mencoba mengakses backend maupun database.

---

## 19. Challenge
Rancang arsitektur keamanan jaringan Zero-Trust tingkat perbankan:
- Namespace `payment` memproses transaksi kartu kredit.
- Namespace `analytics` membaca data transaksi secara berkala.
- Namespace `public` menampung API Gateway publik.
- Aturan Keamanan:
  1. `payment` menolak seluruh traffic dari namespace mana pun KECUALI port 8443 dari `public`.
  2. `analytics` HANYA boleh membaca replica database payment via port 5432 di jam malam.
  3. Seluruh koneksi outbound dari `payment` ke internet publik diblokir total, KECUALI IP CIDR bank sentral `103.24.50.0/24`.
Tuliskan seluruh manifest NetworkPolicy deklaratifnya secara lengkap.

---

## 20. Summary
- Jaringan bawaan Kubernetes bersifat **terbuka bebas (permissive)** di mana semua Pod dapat saling menghubungi tanpa batas.
- **NetworkPolicy** bertindak sebagai firewall terdistribusi Layer 3/Layer 4 yang ditegakkan oleh CNI (Calico / Cilium).
- Terapkan **Default-Deny Ingress & Egress** sebagai fondasi keamanan Zero-Trust.
- Selalu izinkan **CoreDNS Port 53 (UDP/TCP)** pada setiap kebijakan Egress agar resolusi nama domain tidak lumpuh.
- **Mikrosegmentasi 3-Tier** mengisolasi komponen sistem dan mencegah pergerakan lateral (*lateral movement*) peretas saat terjadi insiden pembobolan.

---
[⬅️ Module 01: CNI Calico vs Cilium](./Module-01-CNI-Calico-vs-Cilium-eBPF-dan-Routing.md) | [📋 Silabus Induk](../README.md) | [Evaluasi & Quiz BAB 06 ➡️](./BAB-06-Quiz-dan-Challenge.md)
---
