# BAB 06 — Quiz & Chapter Challenge: Network Security, CNI, & NetworkPolicies

---
[⬅️ Module 02: NetworkPolicies & Microsegmentation](./Module-02-NetworkPolicies-Default-Deny-dan-Microsegmentation.md) | [📋 Silabus Induk](../README.md) | [BAB 07 Module 01: PV, PVC, & Storage Lifecycle ➡️](../BAB-07-Storage-Persistence-dan-CSI/Module-01-PV-PVC-Lifecycle-dan-Reclaim-Policies.md)
---

Dokumen ini menguji pemahaman Anda terhadap arsitektur jaringan CNI (Container Network Interface), perbedaan Overlay vs Direct Routing, keunggulan Linux eBPF pada Cilium, serta implementasi pertahanan Zero-Trust menggunakan Kubernetes NetworkPolicy.

---

## Bagian 1: Basic Quiz (5 Pertanyaan)

### Soal 1
Bagaimana postur keamanan jaringan bawaan (default network posture) di dalam sebuah kluster Kubernetes jika belum ada NetworkPolicy yang diterapkan sama sekali?
- A. Seluruh traffic antar Pod diblokir total hingga dibuka oleh admin.
- B. Jaringan bersifat sepenuhnya terbuka (*permissive / flat*): Pod mana pun di namespace mana pun dapat mengirimkan paket langsung ke Pod mana pun di kluster tanpa batasan.
- C. Hanya Pod di namespace yang sama yang boleh berkomunikasi.
- D. Port 80 otomatis diubah menjadi port 443.

### Soal 2
Apa yang terjadi jika Anda menerapkan file YAML `kind: NetworkPolicy` pada kluster Kubernetes yang menggunakan CNI dasar seperti **Flannel murni**?
- A. Perintah `kubectl apply` akan error dan menolak file.
- B. Perintah `kubectl apply` akan sukses tanpa error, namun aturan NetworkPolicy **TIDAK AKAN PERNAH DITEGAKKAN DI KERNEL** (traffic tetap terbuka bebas), karena Flannel murni tidak memiliki komponen policy enforcement engine.
- C. Seluruh worker node akan crash.
- D. Kluster otomatis mengunduh Calico dari internet.

### Soal 3
Berapa besar penalti ukuran header (*overhead encapsulation*) yang ditambahkan oleh teknologi Overlay Network seperti VXLAN pada setiap paket data?
- A. 0 Byte
- B. Sekitar 50 Byte (Outer IP, UDP, dan VXLAN headers), sehingga MTU antarmuka Pod idealnya disetel ke 1450 pada jaringan host MTU 1500.
- C. 500 Byte
- D. 1 Kilobyte

### Soal 4
Teknologi kernel Linux revolusioner apakah yang menjadi fondasi CNI Cilium untuk memproses paket jaringan langsung di socket layer dan membypass tumpukan iptables?
- A. Linux Namespaces
- B. Linux eBPF (Extended Berkeley Packet Filter)
- C. Docker Compose
- D. Systemd Units

### Soal 5
Port dan protokol jaringan manakah yang **WAJIB DI-WHITELIST** pada aturan Egress Pod saat Anda menerapkan kebijakan `default-deny-egress` di sebuah namespace?
- A. Port 22 (SSH)
- B. Port 53 UDP/TCP (CoreDNS di namespace `kube-system`) agar resolusi nama domain internal/eksternal tidak lumpuh.
- C. Port 3306 (MySQL)
- D. Port 8080 (HTTP)

---

## Bagian 2: Intermediate Quiz (5 Pertanyaan)

### Soal 6
Dalam sintaks deklarasi NetworkPolicy, apa perbedaan antara dua blok konfigurasi berikut:

**Blok A:**
```yaml
ingress:
- from:
  - namespaceSelector: { matchLabels: { env: prod } }
  - podSelector: { matchLabels: { app: frontend } }
```

**Blok B:**
```yaml
ingress:
- from:
  - namespaceSelector: { matchLabels: { env: prod } }
    podSelector: { matchLabels: { app: frontend } }
```
- A. Tidak ada perbedaan sama sekali.
- B. Blok A menggunakan logika **OR** (mengizinkan traffic dari Pod mana pun di namespace prod ATAU dari Pod frontend di namespace lokal), sedangkan Blok B menggunakan logika **AND** (HANYA mengizinkan traffic dari Pod berlabel frontend yang berada di dalam namespace berlabel prod).
- C. Blok A adalah sintaks usang yang dilarang.
- D. Blok B hanya berlaku untuk database.

### Soal 7
Mengapa di kluster enterprise berskala sangat besar (> 2.000 service dan 50.000 endpoint), CNI berbasis iptables (seperti kube-proxy standar) dapat mengalami degradasi performa kernel yang parah?
- A. Karena iptables menghapus memori RAM secara otomatis.
- B. Karena iptables mengevaluasi rantai rule secara sekuensial $O(N)$ dan Kubelet membutuhkan *xtables lock* global setiap kali ada Pod yang bertambah/berkurang, memicu lonjakan latensi paket jaringan saat tabel membesar hingga ratusan ribu baris.
- C. Karena iptables hanya bisa memproses 100 paket per hari.
- D. Karena iptables tidak kompatibel dengan CPU 64-bit.

### Soal 8
Apa yang dimaksud dengan **Mikrosegmentasi Jaringan 3-Tier** di Kubernetes?
- A. Membagi kluster menjadi 3 server fisik yang berbeda.
- B. Membatasi lalu lintas jaringan secara ketat antar lapisan aplikasi (Frontend hanya boleh ke Backend, Backend hanya boleh ke Database, dan Database dilarang membuka koneksi keluar), meminimalkan radius pergerakan lateral peretas jika salah satu tier dibobol.
- C. Menjalankan tiga instance Docker di satu Pod.
- D. Membatasi kecepatan download pengguna menjadi sepertiga.

### Soal 9
Apa peran utilitas **Cilium Hubble** dalam observabilitas jaringan Kubernetes?
- A. Menggantikan peran hard disk SSD.
- B. Mengekstrak event aliran paket Layer 3, Layer 4, hingga Layer 7 (HTTP methods, response status code, latency, DNS queries) langsung dari kernel eBPF tanpa perlu menginjeksi sidecar proxy Envoy di setiap Pod.
- C. Menghapus Pod yang memakan banyak bandwidth.
- D. Mengubah alamat MAC worker node.

### Soal 10
Jika Anda mengonfigurasi NetworkPolicy dengan `podSelector: {}` di sebuah namespace tanpa mendefinisikan aturan `ingress:` atau `egress:`, apa dampak yang terjadi pada seluruh Pod di namespace tersebut?
- A. Seluruh Pod akan di-restart otomatis.
- B. Seluruh lalu lintas masuk dan keluar di namespace tersebut akan diblokir total (**Default-Deny All**).
- C. Namespace akan otomatis terhapus dari etcd.
- D. Pod akan diubah menjadi privileged container.

---

## Bagian 3: Scenario-Based Questions (3 Skenario)

### Skenario 1: Bencana Pod Hang Akibat Salah Konfigurasi MTU VXLAN
Sebuah perusahaan logistik memigrasikan kluster ke CNI Overlay VXLAN dengan MTU host fisik 1500:
- Pod API dapat melakukan healthcheck HTTP kecil (`/healthz` ukuran 50 byte) dengan sukses.
- Namun ketika pengguna mencoba mengunduh laporan invoice PDF berukuran 80KB, koneksi browser langsung macet (*stalled / timeout*), dan curl menggantung tanpa response.
- **Pertanyaan**: Jelaskan mengapa paket kecil berhasil sedangkan paket besar menggantung, apa peran flag *Don't Fragment (DF-bit)* pada fenomena ini, dan bagaimana perbaikan nilai MTU CNI yang tepat!

### Skenario 2: Serangan Ransomware Menyebar Bebas di Kluster Permissive
Sebuah aplikasi WordPress lama yang di-deploy di namespace `marketing` berhasil dibobol hacker melalui celah plugin vulnerability:
- Hacker mendapatkan reverse shell di dalam container WordPress.
- Hacker menjalankan nmap dan menemukan database PostgreSQL transaksi nasabah di namespace `fintech` port 5432, lalu mengekstrak seluruh data nasabah dan mengenkripsi database tersebut.
- **Pertanyaan**: Jelaskan mengapa peretas di namespace `marketing` bisa leluasa mengakses database di namespace `fintech`, dan rancang kebijakan NetworkPolicy deklaratif untuk mengisolasi kedua namespace tersebut secara total!

### Skenario 3: Aplikasi Crash Massal Pasca Penerapan Egress Policy
Tim keamanan menerapkan aturan `default-deny-egress` di namespace produksi untuk mematuhi regulasi perbankan.
Seketika seluruh 20 microservices mengalami crash berulang kali dengan error:
`getaddrinfo ENOTFOUND postgres-service` atau `Dial error: could not resolve host`.
- **Pertanyaan**: Identifikasi mengapa error ini terjadi dan tuliskan potongan YAML aturan Egress yang wajib ditambahkan agar resolusi nama domain CoreDNS kembali pulih!

---

## Bagian 4: Chapter Challenge

### Tantangan Praktis: Zero-Trust Microsegmentation Architect
1. **Skenario**:
   Anda diminta membangun kebijakan keamanan jaringan Zero-Trust untuk sistem e-commerce di namespace `ecommerce-prod`:
   - Tier Frontend (`tier: frontend`) hanya menerima port 80 dari Ingress Controller di namespace `ingress-nginx`.
   - Tier Backend (`tier: backend`) hanya menerima port 8080 dari Pod Frontend.
   - Tier Database (`tier: database`) hanya menerima port 5432 dari Pod Backend.
   - Database dilarang memiliki akses egress keluar sama sekali.
   - Seluruh Pod diizinkan mengakses CoreDNS port 53.
2. **Deliverables**:
   - Manifest `default-deny.yaml`.
   - Manifest `dns-allow.yaml`.
   - Manifest `3tier-microsegmentation.yaml` lengkap.

---

## Bagian 5: Knowledge Check & Checklist

### Saya Harus Memahami:
- [ ] Model jaringan datar (*flat network*) Kubernetes.
- [ ] Perbedaan antara Overlay (VXLAN) vs Direct Routing (BGP).
- [ ] Mengapa penalti MTU 50 byte terjadi pada jaringan VXLAN.
- [ ] Keunggulan performa eBPF $O(1)$ pada Cilium dibandingkan iptables $O(N)$.
- [ ] Mengapa NetworkPolicy membutuhkan CNI yang mendukung penegakan aturan (Calico/Cilium).
- [ ] Cara kerja Default-Deny Ingress dan Egress.
- [ ] Pentingnya membuka port 53 UDP ke CoreDNS pada kebijakan Egress.
- [ ] Pola Mikrosegmentasi 3-Tier untuk mitigasi lateral movement.

### Saya Tidak Perlu Menghafal:
- Struktur biner internal frame VXLAN RFC 7348.
- Bytecode assembly instruksi program kernel eBPF.

### Saya Harus Bisa Melakukan:
- [ ] Memeriksa biner dan konfigurasi CNI di host Linux `/etc/cni/net.d/`.
- [ ] Menulis manifest Default-Deny All NetworkPolicy.
- [ ] Menulis manifest NetworkPolicy dengan pemilih kombinasi podSelector dan namespaceSelector.
- [ ] Memecahkan masalah MTU mismatch pada jaringan overlay.
- [ ] Men-debug paket drop menggunakan logs atau Hubble CLI.

---
[⬅️ Module 02: NetworkPolicies & Microsegmentation](./Module-02-NetworkPolicies-Default-Deny-dan-Microsegmentation.md) | [📋 Silabus Induk](../README.md) | [BAB 07 Module 01: PV, PVC, & Storage Lifecycle ➡️](../BAB-07-Storage-Persistence-dan-CSI/Module-01-PV-PVC-Lifecycle-dan-Reclaim-Policies.md)
---
