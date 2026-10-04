# BAB: Quiz, Challenge, & Knowledge Check
**BAB 01: Fondasi Orkestrasi & Arsitektur Sistem Kubernetes**

---
[⬅️ Module 02: Arsitektur Lanjutan & Deep Dive](./Module-02-kubernetes-Bab-01.md) | [📋 Silabus Induk](../README.md) | [BAB 02 Module 01: Anatomi Pod & Lifecycle ➡️](../BAB-02-Pod-Lifecycle-dan-Multi-Container-Patterns/Module-01-Anatomi-Pod-Lifecycle-Probes-dan-Termination.md)
---

Dokumen ini dirancang untuk menguji pemahaman konseptual mendalam, kapabilitas diagnostik sistem, dan keahlian rekayasa operasional Anda terkait arsitektur internal Kubernetes: **Control Plane Mechanics** (`kube-apiserver`, `etcd`, `kube-controller-manager`, `kube-scheduler`), **Worker Node Internals** (`kubelet`, PLEG, CRI `containerd`, `kube-proxy`, `cgroups v2`), serta mekanisme konsensus terdistribusi dan *reconciliation loop*.

---

## 1. Basic Questions (5 Soal)

### Soal 1: Single Source of Truth & Otoritas Database Kluster
Komponen Kubernetes manakah yang merupakan satu-satunya subsistem yang memiliki otorisasi untuk berkomunikasi secara langsung, membaca, dan menulis data ke database persisten `etcd`?
- **A.** `kubelet`
- **B.** `kube-scheduler`
- **C.** `kube-apiserver`
- **D.** `kube-controller-manager`

<details>
<summary>🔍 Kunci Jawaban & Pembahasan Mendalam</summary>

**Kunci Jawaban: C**

**Pembahasan:**
Dalam arsitektur Kubernetes, `kube-apiserver` bertindak sebagai sentral *gatekeeper* dan *stateless facade* tunggal untuk seluruh operasi kluster. Tidak ada komponen lain—baik scheduler, controller manager, kubelet, maupun client luar seperti `kubectl`—yang diizinkan mengakses port TCP `etcd` secara langsung. 
Semua interaksi dibatasi melalui `kube-apiserver` menggunakan otentikasi mTLS ketat. Desain ini bertujuan untuk:
1. Memastikan seluruh manipulasi data melewati siklus validasi skema (*Schema Validation*) dan kontrol penerimaan (*Admission Controllers*).
2. Menerapkan kontrol konkurensi optimistik (*Optimistic Concurrency Control* / OCC) berbasis `resourceVersion` guna mencegah kondisi balapan (*race conditions*).
3. Mengisolasi `etcd` di balik jaringan internal privat demi keamanan dan integritas data konsensus Raft.
</details>

---

### Soal 2: Matematika Quorum & Toleransi Kegagalan Konsensus Raft
Sebuah kluster Kubernetes tingkat enterprise dirancang dengan topologi *High Availability* (HA) menggunakan $N = 5$ node `etcd`. Berdasarkan algoritma konsensus Raft, berapa jumlah node minimum yang wajib tetap aktif agar kluster dapat mempertahankan quorum dan memproses transaksi penulisan (*write request*), serta berapa jumlah maksimum node yang boleh mati secara bersamaan tanpa memicu *split-brain*?
- **A.** Minimum 2 node aktif, toleransi kegagalan 3 node mati.
- **B.** Minimum 3 node aktif, toleransi kegagalan 2 node mati.
- **C.** Minimum 4 node aktif, toleransi kegagalan 1 node mati.
- **D.** Minimum 5 node aktif, toleransi kegagalan 0 node mati.

<details>
<summary>🔍 Kunci Jawaban & Pembahasan Mendalam</summary>

**Kunci Jawaban: B**

**Pembahasan:**
Algoritma konsensus terdistribusi Raft menentukan bahwa operasi penulisan (*write transaction*) hanya valid jika telah direplikasi ke mayoritas absolut dari total anggota kluster, yang dihitung dengan rumus kuorum:
$$\text{Quorum} = \left\lfloor \frac{N}{2} \right\rfloor + 1$$
Untuk kluster dengan $N = 5$ node:
$$\text{Quorum} = \left\lfloor \frac{5}{2} \right\rfloor + 1 = 2 + 1 = 3 \text{ node minimum}$$
Toleransi kegagalan maksimum ($F$) dihitung dengan rumus:
$$F = \frac{N - 1}{2} = \frac{5 - 1}{2} = 2 \text{ node}$$
Jika 2 node mati, kluster masih menyisakan 3 node ($3 \ge 3$), sehingga quorum tercapai dan kluster tetap berfungsi normal. Jika 3 node mati, sisa 2 node tidak mampu membentuk mayoritas dari 5 ($2 < 3$), sehingga etcd otomatis beralih ke mode *read-only* untuk mencegah inkonsistensi data atau *split-brain*.
</details>

---

### Soal 3: Paradigma Kontrol Deklaratif & Reconciliation Loop
Bagaimana mekanisme *Reconciliation Loop* (Control Loop) pada `kube-controller-manager` menangani kondisi ketika jumlah Pod aktual (*Current State*) berbeda dengan jumlah Pod yang dideklarasikan oleh engineer (*Desired State*)?
- **A.** Controller mengeksekusi skrip Bash secara imperatif pada host Linux worker untuk me-reboot mesin.
- **B.** Controller secara berkala membandingkan *Current State* dengan *Desired State*, lalu menghitung deviasi (*state drift*) dan mengirimkan perintah kompensasi ke `kube-apiserver` secara non-blocking hingga sistem mencapai konvergensi.
- **C.** Controller menghapus seluruh objek kluster dan membangun ulang dari snapshot etcd cadangan.
- **D.** Controller membekukan seluruh traffic jaringan sampai operator manusia menyetujui perubahan secara manual.

<details>
<summary>🔍 Kunci Jawaban & Pembahasan Mendalam</summary>

**Kunci Jawaban: B**

**Pembahasan:**
Prinsip inti Kubernetes adalah *Declarative State Model*. Operator hanya menyatakan *Desired State* (misal: `replicas: 5` pada Deployment). Kontroler (seperti ReplicaSet Controller) menjalankan siklus tanpa akhir (*infinite reconciliation loop*):
$$\text{Observe} \longrightarrow \text{Analyze (Diff)} \longrightarrow \text{Act (Reconcile)}$$
1. **Observe:** Membaca *Current State* dari cache lokal yang disinkronisasi melalui API Informer/Watch.
2. **Analyze:** Menghitung selisih ($\Delta = \text{Desired} - \text{Current}$).
3. **Act:** Jika $\Delta > 0$, kontroler membuat Pod baru via REST API call ke `kube-apiserver`. Jika $\Delta < 0$, kontroler memilih Pod untuk dihentikan (*graceful termination*).
Proses ini bersifat *event-driven* dan *idempotent*, memastikan konvergensi status secara otomatis tanpa intervensi manusia.
</details>

---

### Soal 4: Pipeline Dua Fase pada Kube-Scheduler
Dalam siklus hidup penjadwalan sebuah Pod baru yang belum memiliki node target (`spec.nodeName == ""`), urutan dua fase utama yang dieksekusi oleh `kube-scheduler` untuk menentukan penempatan pod pada worker node adalah:
- **A.** Fase Compilation dan Fase Execution.
- **B.** Fase Authentication dan Fase Authorization.
- **C.** Fase Filtering (Predicates) dan Fase Scoring (Priorities).
- **D.** Fase Mutation dan Fase Validation.

<details>
<summary>🔍 Kunci Jawaban & Pembahasan Mendalam</summary>

**Kunci Jawaban: C**

**Pembahasan:**
`kube-scheduler` mengevaluasi Pod yang antre di antrean aktif (*scheduling queue*) melalui dua tahapan matematis:
1. **Filtering (Predicates):** Menyaring seluruh node di kluster untuk menemukan node yang layak (*feasible nodes*). Filter ini menguji ketersediaan resource (`NodeResourcesFit`), pemenuhan taints/tolerations (`NodePorts`), node selector/affinity (`MatchNodeSelector`), dan batas volume disk. Node yang tidak memenuhi kriteria langsung didiskualifikasi.
2. **Scoring (Priorities):** Memberikan bobot nilai numerik (skor rentang 0–100) kepada setiap node yang lolos fase filtering. Algoritma scoring mengevaluasi strategi penyeimbangan beban (`NodeResourcesBalancedAllocation`), kedekatan image container (`ImageLocality`), dan persebaran topologi (`TopologySpread`). Node dengan akumulasi skor tertinggi dipilih, dan scheduler mengeksekusi operasi `Bind` untuk menuliskan nama node ke `spec.nodeName` objek Pod.
</details>

---

### Soal 5: Anatomi Pause Container & Pembagian Namespace Linux
Apa fungsi fundamental dari **Pause Container** (*Infra Container*) yang diinisialisasi pertama kali oleh Container Runtime (CRI) dalam tahapan `RunPodSandbox`?
- **A.** Mengompresi log aplikasi dan menyimpannya di `/var/log`.
- **B.** Berfungsi sebagai jangkar (*anchor*) yang menahan dan mempertahankan Linux Network Namespace, IPC Namespace, dan alamat IP Pod agar tetap persisten meskipun kontainer aplikasi di dalam Pod me-restart.
- **C.** Melakukan kompilasi kode biner aplikasi sebelum dieksekusi di user space.
- **D.** Mengatur hak akses pengguna root pada sistem operasi worker node.

<details>
<summary>🔍 Kunci Jawaban & Pembahasan Mendalam</summary>

**Kunci Jawaban: B**

**Pembahasan:**
Sebuah Pod di Kubernetes adalah sekumpulan kontainer yang berbagi konteks eksekusi Linux. Saat Pod dibuat:
1. CRI mengeksekusi kontainer mini berbasis biner assembler ringan (`pause.c`) yang masuk ke kondisi sleep tak terbatas.
2. Pause container membuat dan mengisolasi Linux Namespaces: `net` (Virtual Ethernet veth pair, loopback `lo`, Pod IP), `ipc` (System V IPC / POSIX message queues), dan opsional `pid` jika `shareProcessNamespace: true`.
3. Seluruh kontainer aplikasi yang didefinisikan dalam Pod kemudian di-*join* ke dalam namespace milik Pause container tersebut (`setns` syscall).
4. Hasilnya, seluruh kontainer di dalam Pod yang sama dapat saling berkomunikasi via `localhost`, berbagi routing table, dan alamat IP Pod tidak akan hilang meskipun kontainer aplikasi mati atau me-restart. Selain itu, pause container bertindak sebagai PID 1 untuk melakukan *zombie process reaping*.
</details>

---

## 2. Intermediate Questions (5 Soal)

### Soal 6: Pipeline Validasi API Server & Admission Controllers
Perhatikan urutan pemrosesan HTTP request di dalam `kube-apiserver`. Urutan pipeline eksekusi manakah yang tepat setelah request melewati layer Autentikasi (AuthN) dan Otorisasi (AuthZ) sebelum data ditulis ke dalam database `etcd`?
- **A.** etcd Commit $\longrightarrow$ Validating Admission Webhook $\longrightarrow$ Mutating Admission Webhook $\longrightarrow$ Schema Validation.
- **B.** Mutating Admission Controllers $\longrightarrow$ Schema Validation $\longrightarrow$ Validating Admission Controllers $\longrightarrow$ Storage Layer Serialization & Persistence.
- **C.** Validating Admission Controllers $\longrightarrow$ Mutating Admission Controllers $\longrightarrow$ Schema Validation $\longrightarrow$ etcd Commit.
- **D.** Schema Validation $\longrightarrow$ Validating Admission Controllers $\longrightarrow$ Mutating Admission Controllers $\longrightarrow$ Storage Layer.

<details>
<summary>🔍 Kunci Jawaban & Pembahasan Mendalam</summary>

**Kunci Jawaban: B**

**Pembahasan:**
Urutan pipeline `kube-apiserver` sangat ketat dan terstruktur secara deterministik:
1. **Authentication (AuthN):** Memvalidasi identitas pengirim (X.509 certs, OIDC Bearer tokens, Webhook tokens).
2. **Authorization (AuthZ):** Menilai izin akses subjek terhadap resource dan verb (Node, RBAC, Webhook).
3. **Mutating Admission Controllers:** Memodifikasi atau menginjeksi nilai default pada payload spec (misal: injeksi Istio/Linkerd sidecar, default StorageClass, penambahan label otomatis).
4. **Object Schema Validation:** Memeriksa kesesuaian payload dengan skema OpenAPI Kubernetes (tipe data, field wajib, field immutable).
5. **Validating Admission Controllers:** Menginspeksi payload final yang telah dimutasi untuk memutuskan apakah request diterima atau ditolak (misal: OPA Gatekeeper, Kyverno, LimitRanger, PodSecurityStandards). Validating controllers tidak dapat mengubah objek.
6. **Storage Layer (etcd):** Melakukan konversi ke tipe internal, serialisasi protocol buffer, dan penulisan transaksi atomic ke `/registry/...` di `etcd`.
</details>

---

### Soal 7: Diagnostik Subsistem PLEG (Pod Lifecycle Event Generator)
Ketika seorang Site Reliability Engineer (SRE) mengamati worker node berstatus `NotReady`, perintah `kubectl describe node` menampilkan event:
`PLEG is not healthy: pleg was last seen active 3m25s ago`
Secara arsitektural di level sistem Linux, apa yang sebenarnya terjadi di dalam daemon `kubelet`?
- **A.** File konfigurasi `/etc/resolv.conf` pada worker node terhapus secara tidak sengaja.
- **B.** Thread relist loop PLEG pada Kubelet mengalami *hang* atau timeout saat memanggil gRPC API (`ListPodSandbox` / `PodStatus`) ke Container Runtime (`containerd`), biasanya diakibatkan oleh disk I/O starvation pada `/var/lib/containerd` atau kebuntuan proses runtime Linux.
- **C.** Sertifikat client TLS Kubelet telah kedaluwarsa dan ditolak oleh API server.
- **D.** Kubelet kehabisan alokasi bandwidth jaringan akibat download container image berukuran gigabyte.

<details>
<summary>🔍 Kunci Jawaban & Pembahasan Mendalam</summary>

**Kunci Jawaban: B**

**Pembahasan:**
PLEG (*Pod Lifecycle Event Generator*) adalah modul internal di dalam Kubelet yang bertugas mendeteksi perubahan status kontainer di node secara berkala.
- Setiap periode waktu tertentu (default 1 detik), PLEG memicu loop *relist*: ia mengirimkan panggilan gRPC ke CRI (Container Runtime Interface) daemon (seperti `containerd` atau `CRI-O`) melalui UNIX domain socket `/run/containerd/containerd.sock` untuk menanyakan status seluruh kontainer dan pod sandboxes.
- Kubelet memiliki mekanisme watchdog. Jika loop relist PLEG tidak selesai dalam jangka waktu threshold (default 3 menit), Kubelet menganggap subsistem PLEG macet (*unhealthy*) dan melaporkan status node sebagai `NotReady`.
- **Root Cause di Lapangan:** Paling sering disebabkan oleh kebuntuan I/O disk (I/O wait 100%) pada filesystem yang menampung overlay2 storage driver (`/var/lib/containerd`), memory starvation yang membekukan containerd daemon, atau penumpukan ribuan *dead/stale* container shims yang belum ter-cleanup.
</details>

---

### Soal 8: Konflik Dual Driver Cgroups v2 (Systemd vs Cgroupfs)
Mengapa mengonfigurasi `cgroupDriver: cgroupfs` pada Kubelet sementara sistem operasi Linux host (seperti Ubuntu 22.04 / RHEL 9) menggunakan `systemd` sebagai init system merupakan kesalahan fatal yang dapat memicu instabilitas kluster produksi?
- **A.** Karena `cgroupfs` tidak mendukung penamaan container dengan karakter huruf kapital.
- **B.** Karena terjadi perebutan otoritas manajer (*split-brain management*) di kernel Linux: saat systemd mengalokasikan ulang hierarchy cgroup atau melakukan refresh, kontrol resource yang diatur langsung oleh Kubelet melalui cgroupfs menjadi tidak sinkron, memicu kegagalan Kubelet membaca metrik resource dan memicu crash daemon.
- **C.** Karena kernel Linux secara otomatis memblokir koneksi jaringan TCP jika cgroupfs diaktifkan.
- **D.** Karena file biner Kubelet akan terhapus otomatis oleh kernel saat deteksi cgroup mismatch.

<details>
<summary>🔍 Kunci Jawaban & Pembahasan Mendalam</summary>

**Kunci Jawaban: B**

**Pembahasan:**
Linux Cgroups (Control Groups) v2 mengadopsi model *single unified hierarchy tree*. Di dalam sistem operasi modern yang menggunakan `systemd` sebagai PID 1, systemd didesain sebagai manajer tunggal otoritatif atas seluruh hirarki cgroup (`/sys/fs/cgroup`).
- Jika Kubelet atau Container Runtime dikonfigurasi menggunakan driver `cgroupfs`, proses tersebut akan memanipulasi direktori `/sys/fs/cgroup` secara langsung tanpa berkoordinasi dengan systemd.
- Hal ini menciptakan fenomena **Dual Cgroup Managers**: ketika systemd melakukan reload, service restart, atau reorganisasi hirarki slice, konfigurasi limit memori dan CPU yang dibuat oleh `cgroupfs` dapat terhapus atau corrupt.
- Akibatnya, alokasi resource menjadi kacau, cAdvisor gagal mengekstrak penggunaan memori, OOM killer mematikan proses yang salah, dan Kubelet memasuki status panik (*fatal exit*). Oleh karena itu, standar Kubernetes produksi mewajibkan konfigurasi seragam: `SystemdCgroup = true` pada containerd dan `cgroupDriver: systemd` pada Kubelet.
</details>

---

### Soal 9: Efisiensi NodeLease vs Write Pressure pada Database etcd
Pada kluster berukuran besar (ratusan hingga ribuan worker node), mekanisme `NodeLease` (objek `Lease` di namespace `kube-node-lease`) diperkenalkan untuk menggantikan pelaporan status node tradisional. Mengapa pemisahan antara `NodeStatus` dan `NodeHeartbeat` via NodeLease sangat krusial bagi skalabilitas `etcd`?
- **A.** Karena `NodeLease` menyimpan seluruh log aktivitas pod di memori RAM tanpa menyentuh disk sama sekali.
- **B.** Objek `NodeStatus` berukuran relatif besar (puluhan kilobyte berisi daftar images, kapasitas resource, addresses, kondisi hardware); jika diperbarui setiap beberapa detik oleh ribuan node, etcd akan mengalami kejenuhan penulisan disk WAL dan bandwidth jaringan. Objek `Lease` berukuran sangat kecil (< 1 KB) yang hanya mengupdate timestamp heartbeat, memangkas beban I/O etcd hingga lebih dari 90%.
- **C.** Karena objek `Lease` disimpan di database MySQL terpisah di luar etcd.
- **D.** Karena `NodeLease` bertindak sebagai sistem billing otomatis untuk cloud provider.

<details>
<summary>🔍 Kunci Jawaban & Pembahasan Mendalam</summary>

**Kunci Jawaban: B**

**Pembahasan:**
Sebelum fitur NodeLease matang, Kubelet memperbarui objek `Node` lengkap setiap 10 detik. Objek `Node` memuat:
- Informasi hardware, kapasitas CPU/RAM/Ephemeral-storage, dan allocatable resource.
- Daftar puluhan hingga ratusan container image yang tersimpan di disk cache worker node.
- Status node conditions (`MemoryPressure`, `DiskPressure`, `PIDPressure`, `Ready`).
Pada kluster dengan 1.000 node, pembaruan objek sebesar 20 KB setiap 10 detik menghasilkan beban tulis kontinu sebesar 2 MB/s langsung ke Write-Ahead Log (WAL) `etcd`, memicu serialisasi berat di `kube-apiserver` dan fragmentasi database.
Dengan **NodeLease**:
- Kubelet hanya mengirimkan pembaruan objek `Lease` ringan (hanya berisi field `renewTime` dan `holderIdentity`, berukuran ~400 bytes) setiap 10 detik (default).
- Objek `Node` lengkap yang berat hanya dikirimkan jika terjadi perubahan status nyata pada node atau setiap interval lambat (misal: 5 menit sekali). Ini menekan konsumsi write I/O etcd secara drastis.
</details>

---

### Soal 10: Komparasi Performa Kube-Proxy: Iptables vs IPVS vs eBPF
Mengapa arsitektur penanganan paket jaringan menggunakan `kube-proxy: ipvs` atau CNI berbasis eBPF (seperti Cilium) direkomendasikan secara mutlak untuk kluster produksi dengan skala > 10.000 Service dibandingkan mode standar `kube-proxy: iptables`?
- **A.** Karena iptables tidak dapat memproses lalu lintas data terenkripsi HTTPS.
- **B.** Karena iptables mengevaluasi filter paket secara sekuensial dari atas ke bawah dengan kompleksitas waktu $O(N)$ (di mana $N$ adalah jumlah Service dan Endpoint), menyebabkan lonjakan drastis pada latensi paket dan pemakaian CPU kernel Linux saat jumlah rule membengkak. Sementara IPVS menggunakan struktur data Hash Table dengan kompleksitas $O(1)$.
- **C.** Karena IPVS secara otomatis mempercepat kecepatan internet fisik kabel fiber optik data center.
- **D.** Karena iptables memiliki batasan lisensi open-source komersial.

<details>
<summary>🔍 Kunci Jawaban & Pembahasan Mendalam</summary>

**Kunci Jawaban: B**

**Pembahasan:**
Perbandingan mendasar arsitektur data plane jaringan Kubernetes:
1. **iptables ($O(N)$):** Setiap Service dan Pod Endpoint direpresentasikan sebagai rule rantai (*chain*) iptables di kernel Linux. Paket data yang masuk harus melintasi rantai rule satu per satu secara berurutan. Jika kluster memiliki 5.000 Service dengan masing-masing 10 replica (50.000 endpoints), satu paket TCP baru mungkin harus mengevaluasi puluhan ribu rule sebelum menemukan target DNAT yang tepat. Selain itu, sinkronisasi pembaruan rule iptables memakan waktu lama dan mengunci kernel lock (`xtables_lock`).
2. **IPVS ($O(1)$):** IPVS (IP Virtual Server) dibangun khusus untuk transport-layer load balancing di dalam kernel Linux LVS. IPVS menyimpan pemetaan Virtual Server dan Real Server di dalam struktur data **Hash Table**. Lookup alamat Service dan penentuan backend Pod berlangsung secara konstan $O(1)$ tanpa memedulikan apakah kluster memiliki 10 Service atau 100.000 Service.
3. **eBPF (Cilium):** Melangkah lebih jauh dengan mengaitkan program bytecode langsung ke socket hook Linux (`sock_ops`, `tc`), mem-bypass overhead subsistem Netfilter kernel secara menyeluruh, menghasilkan throughput maksimal dan latensi terendah.
</details>

---

## 3. Scenario-Based Questions (3 Skenario Kasus Produksi)

### Skenario 1: Bencana Split-Brain & Disk Latency Starvation pada etcd Cluster Saat Traffic Surge
**Latar Belakang Kasus:**
Sebuah platform perbankan digital mengoperasikan kluster Kubernetes *bare-metal* dengan 3 node Master (Control Plane) yang menjalankan topologi *stacked etcd*. Selama kampanye promosi akhir tahun, traffic API melonjak 800%. Tim SRE menerima alert PagerDuty tingkat *Sev-1*:
`etcd server: high disk fsync duration (> 100ms)`
`etcd cluster: loss of leader / repeated leader elections`
`kube-apiserver: 500 Internal Server Error (context deadline exceeded)`
`kubectl` berhenti merespons, dan pembuatan pod baru terhenti total.

Setelah diperiksa, ketiga master node menggunakan hard disk SATA gabungan di mana direktori database `/var/lib/etcd` berada di partisi yang sama dengan direktori log aplikasi `/var/log/pods`.

```
+-------------------------------------------------------------------------+
|                  HOST MASTER NODE 1 (Single SATA Disk)                  |
|                                                                         |
|  +---------------------------+        +------------------------------+  |
|  |   Heavy App Pod Logs      |        |      etcd Raft Database      |  |
|  |  Write /var/log/pods/*.log|        |  WAL Disk Fsync (/var/lib)   |  |
|  +-------------+-------------+        +---------------+--------------+  |
|                |                                      |                 |
|                +------------------+-------------------+                 |
|                                   |                                     |
|                                   v                                     |
|                      [ Shared SATA Disk Controller ]                    |
|                         (IOPS Exhaustion / >100ms)                      |
|                                   |                                     |
|                                   v                                     |
|                 Heartbeat Drop -> Leader Election Loop                  |
+-------------------------------------------------------------------------+
```

**Pertanyaan Diagnostik:**
1. Mengapa lonjakan latensi `fsync` disk dapat memicu siklus pemilihan leader (*repeated leader elections*) tanpa henti pada etcd? Analisis hubungannya dengan mekanisme Raft Heartbeat dan parameter `heartbeat-interval` serta `election-timeout`.
2. Apa risiko terburuk jika operator secara gegabah mematikan salah satu node etcd untuk perbaikan darurat saat kluster 3-node tersebut sedang dalam kondisi instabil?
3. Rancang arsitektur perbaikan menyeluruh (*root cause remediation*) untuk menstabilkan etcd pada infrastruktur bare-metal tersebut, mencakup spesifikasi disk, isolasi mount point, parameter tuning, dan prosedur defragmentasi rutin!

<details>
<summary>🔍 Analisis Root Cause & Solusi Produksi</summary>

#### 1. Mekanisme Raft Heartbeat & Kegagalan Fsync Disk
- etcd mengandalkan algoritma Raft yang menjamin durabilitas data melalui penulisan transaksi sinkron ke Write-Ahead Log (WAL) di disk sebelum membalas request ke caller.
- Operasi penyimpanan WAL memanggil syscall `fdatasync()` / `fsync()`. Selama disk melakukan flush data ke piringan fisik, thread eksekusi terblokir.
- Leader etcd wajib mengirimkan sinyal heartbeat secara periodik (default: 100ms) ke node-node follower. Jika leader mengalami starvation I/O disk (latensi fsync melonjak > 100ms), leader tidak dapat mengirimkan heartbeat tepat waktu.
- Node follower mendeteksi ketiadaan heartbeat hingga melewati batas `election-timeout` (default: 1000ms), berasumsi bahwa leader telah mati, lalu menaikkan term Raft dan memicu pemilihan leader baru (*new leader election*).
- Karena ketiga node mengalami disk latency yang sama parahnya, pemilihan leader baru pun gagal menyelesaikan commit proposal, menyebabkan kluster terjebak dalam *infinite election loop* dan menolak semua penulisan baru (`context deadline exceeded`).

#### 2. Risiko Mematikan 1 Node pada Kluster 3-Node
Pada kluster 3 node ($N=3$), Quorum adalah $\lfloor 3/2 \rfloor + 1 = 2$ node.
Jika 1 node dimatikan secara manual saat 2 node sisanya sedang berjuang dengan latensi disk dan sesekali mengalami network drop, kehilangan satu node lagi akan membuat sisa node berjumlah 1. Satu node dari 3 node anggota **TIDAK MEMENUHI QUORUM** ($1 < 2$).
Akibatnya: Kluster etcd akan langsung mati total (*complete cluster stall*), apiserver berhenti melayani operasi write secara permanen, dan kluster kehilangan kemampuan orkestrasi otomatis.

#### 3. Arsitektur Solusi & Remediasi Produksi
1. **Pemisahan Fisik Storage (Dedicated NVMe SSD):**
   - Wajib memisahkan direktori `/var/lib/etcd` ke dedicated disk fisik berlatensi rendah (NVMe SSD enterprise dengan write endurance tinggi / DWPD tinggi).
   - Pastikan metrik `etcd_disk_wal_fsync_duration_seconds` percentil ke-99 ($p99$) berada di bawah 10ms (rekomendasi CNCF/etcd: $< 5\text{ms}$).
2. **Mount Point & I/O Priority:**
   - Mount disk etcd dengan opsi optimal:
     ```bash
     mkfs.ext4 -O mmp /dev/nvme0n1
     mount -o defaults,noatime,nodiratime /dev/nvme0n1 /var/lib/etcd
     ```
   - Prioritaskan I/O proses etcd menggunakan `ionice`:
     ```bash
     ionice -c2 -n0 -p $(pgrep etcd)
     ```
3. **Tuning Heartbeat & Election Timeout (Jika Latensi Jaringan/Disk Agak Tinggi):**
   Pada konfigurasi static pod etcd (`/etc/kubernetes/manifests/etcd.yaml`), sesuaikan flag jika kluster melintasi zona:
   ```yaml
   spec:
     containers:
     - command:
       - etcd
       - --heartbeat-interval=250
       - --election-timeout=1250
       - --auto-compaction-retention=1
       - --auto-compaction-mode=periodic
   ```
4. **Automated Maintenance Routine:**
   Jadwalkan cronjob mingguan untuk defragmentasi database etcd guna mengklaim kembali ruang kosong (*free space fragmentation*):
   ```bash
   ETCDCTL_API=3 etcdctl --cacert=/etc/kubernetes/pki/etcd/ca.crt \
     --cert=/etc/kubernetes/pki/etcd/server.crt \
     --key=/etc/kubernetes/pki/etcd/server.key \
     --endpoints=https://127.0.0.1:2379 defrag
   ```
</details>

---

### Skenario 2: Worker Nodes Berstatus 'NotReady' Berjamaah Akibat PLEG Timeout & Conntrack Exhaustion
**Latar Belakang Kasus:**
Sebuah kluster microservices dengan 80 worker node menjalankan lebih dari 3.000 Pod. Saat peluncuran fitur baru yang memicu jutaan koneksi HTTP/1.1 singkat (*short-lived connections*), 35 worker node mendadak beralih ke status `NotReady` dalam rentang waktu 5 menit.

Hasil inspeksi log `journalctl -u kubelet` di salah satu node yang terdampak menunjukkan:
```text
E1005 14:22:10.114201 1205 kubelet.go:1980] "PLEG is not healthy" err="pleg was last seen active 3m40s ago"
E1005 14:22:15.890123 1205 remote_runtime.go:120] "ListPodSandbox with filter from runtime service failed" err="rpc error: code = DeadlineExceeded desc = context deadline exceeded"
```
Sementara itu, perintah `dmesg -T` di kernel Linux host membanjiri pesan:
```text
[Mon Oct 05 14:21:40 2026] nf_conntrack: table full, dropping packet
[Mon Oct 05 14:21:42 2026] nf_conntrack: table full, dropping packet
```

```
+-----------------------------------------------------------------------------+
|                               WORKER NODE                                   |
|                                                                             |
|   App Pods (Jutaan TCP Connections)                                         |
|          |                                                                  |
|          v                                                                  |
|   +----------------------------------------------------------------------+  |
|   | Linux Kernel Netfilter Conntrack Table                               |  |
|   | [ STATUS: FULL! (nf_conntrack_max reached) -> PACKETS DROPPED! ]     |  |
|   +----------------------------------------------------------------------+  |
|          |                                                                  |
|          +--------------------------------------+                           |
|          | Paket DNS/Health Check Drop          |                           |
|          v                                      v                           |
|   +------------------------+      +--------------------------------------+  |
|   | Kubelet Health Probes  |      | Containerd gRPC Socket               |  |
|   | Timeout -> Pod Restart |      | ListPodSandbox Timeout -> PLEG Hang  |  |
|   +------------------------+      +--------------------------------------+  |
|                                                 |                           |
|                                                 v                           |
|                                   [ Node Status: NotReady ]                 |
+-----------------------------------------------------------------------------+
```

**Pertanyaan Diagnostik:**
1. Jelaskan bagaimana fenomena tabel `nf_conntrack` yang penuh (*conntrack exhaustion*) dapat memicu kegagalan berantai (*cascading failure*) yang berujung pada status PLEG Kubelet `DeadlineExceeded` dan Node menjadi `NotReady`!
2. Mengapa me-restart service `kubelet` saja tidak akan menyelesaikan masalah ini secara permanen?
3. Tuliskan langkah mitigasi operasional instan di level kernel sysctl dan konfigurasi `kube-proxy` yang harus diterapkan untuk menstabilkan kluster!

<details>
<summary>🔍 Analisis Root Cause & Solusi Produksi</summary>

#### 1. Mekanisme Cascading Failure: Conntrack ke PLEG
1. **Conntrack Saturation:** Setiap koneksi TCP/UDP yang melalui interface jaringan node dicatat di tabel koneksi stateful kernel Linux (`nf_conntrack`). Jutaan koneksi short-lived yang tidak menggunakan HTTP keep-alive memenuhi tabel hingga batas `net.netfilter.nf_conntrack_max`.
2. **Packet Dropping:** Ketika kapasitas tabel conntrack 100% penuh, kernel Linux secara agresif membuang (*drop*) paket jaringan baru, termasuk paket SYN, paket DNS CoreDNS, dan paket internal local socket.
3. **Thundering Restarts:** Kubelet liveness probes gagal menghubungi container aplikasi karena paket TCP/HTTP probe di-drop oleh conntrack. Kubelet menganggap kontainer mati dan memicu restart serentak ratusan kontainer.
4. **CRI Socket Saturation & PLEG Hang:** Ratusan proses restart kontainer membanjiri `containerd` dengan panggilan gRPC (`StopPodSandbox`, `RemoveContainer`, `RunPodSandbox`). Daemon containerd mengalami CPU starvation dan disk I/O lockup.
5. Panggilan rutin PLEG `ListPodSandbox` yang memiliki batas timeout terblokir di antrean gRPC containerd. Ketika PLEG tidak menerima respons selama > 3 menit, Kubelet membunyikan alarm internal dan mengubah status Node menjadi `NotReady`.

#### 2. Mengapa Restart Kubelet Saja Gagal
Me-restart `kubelet` (`systemctl restart kubelet`) hanya mengulang inisialisasi daemon, namun:
- Tabel kernel `nf_conntrack` tetap dalam kondisi penuh.
- Ribuan koneksi aplikasi yang masuk tetap di-drop oleh netfilter.
- Begitu Kubelet baru menyala, ia langsung kembali mengirimkan panggilan gRPC ke containerd yang antreannya masih macet, sehingga PLEG akan langsung kembali mengalami `DeadlineExceeded` dalam beberapa menit.

#### 3. Langkah Mitigasi & Remediasi Produksi
**Langkah 1: Perbesar Ukuran Tabel Conntrack Kernel Secara Runtime:**
Eksekusi di seluruh worker node secara instan:
```bash
# Periksa ukuran dan pemakaian saat ini
cat /proc/sys/net/netfilter/nf_conntrack_count
cat /proc/sys/net/netfilter/nf_conntrack_max

# Tingkatkan kapasitas tabel conntrack (misal: 1 juta hingga 2 juta entri)
sysctl -w net.netfilter.nf_conntrack_max=2097152

# Percepat pembersihan koneksi TIME_WAIT yang menumpuk
sysctl -w net.netfilter.nf_conntrack_tcp_timeout_time_wait=30
sysctl -w net.netfilter.nf_conntrack_tcp_timeout_close_wait=15
sysctl -w net.netfilter.nf_conntrack_tcp_timeout_established=86400
```
Persistenkan di `/etc/sysctl.d/99-k8s-conntrack.conf`.

**Langkah 2: Konfigurasi Kube-Proxy Conntrack Allocator:**
Pastikan `kube-proxy` dikonfigurasi agar secara otomatis mengatur batas conntrack proporsional dengan jumlah core CPU:
```yaml
apiVersion: kubeproxy.config.k8s.io/v1alpha1
kind: KubeProxyConfiguration
mode: "ipvs"
conntrack:
  maxPerCore: 131072 # 128k per core
  min: 1048576       # Minimum 1M
  tcpCloseWaitTimeout: 10s
  tcpEstablishedTimeout: 43200s
```

**Langkah 3: Edukasi Arsitektur Aplikasi:**
Wajibkan tim engineering menggunakan HTTP Connection Pooling (*keep-alive*) pada layer microservices untuk mencegah banjir pembuatan soket TCP baru (*socket thrashing*).
</details>

---

### Skenario 3: Cascading API Server Saturation Akibat Unindexed Listing & Webhook Deadlock
**Latar Belakang Kasus:**
Sebuah tim platform engineering membuat skrip automasi internal yang berjalan di kluster staging dan production. Skrip tersebut melakukan audit berkala setiap 3 detik dengan mengeksekusi:
`kubectl get pods -A --show-labels`
Secara bersamaan, tim security memasang `ValidatingWebhookConfiguration` baru bernama `corp-security-gatekeeper` untuk memastikan seluruh Pod mematuhi standar label kepatuhan. Konfigurasi webhook tersebut disetel dengan:
```yaml
webhooks:
  - name: security.corp.internal
    rules:
      - operations: ["*"]
        apiGroups: ["*"]
        apiVersions: ["*"]
        resources: ["*"]
    failurePolicy: Fail
    timeoutSeconds: 30
    clientConfig:
      service:
        name: validator-svc
        namespace: security
```
Suatu hari, worker node tempat Pod `validator-svc` berjalan mengalami *Out-Of-Memory* (OOM). Seketika itu juga, **seluruh operasi di kluster Kubernetes mati suri**: tidak ada deployment baru yang bisa di-apply, pod autoscaler (HPA) gagal memperbarui status, dan `kube-apiserver` mengalami lonjakan konsumsi memori RAM hingga 98% lalu di-kill oleh Linux kernel OOM Killer.

**Pertanyaan Diagnostik:**
1. Mengapa eksekusi rutin `kubectl get pods -A` tanpa filter pagination/limit membakar konsumsi CPU dan RAM `kube-apiserver` secara masif?
2. Jelaskan bagaimana kombinasi matinya Pod `validator-svc` dan pengaturan `failurePolicy: Fail` memicu fenomena **Deadlock Penerimaan API** (*Admission Deadlock*) yang melumpuhkan kluster!
3. Susun solusi mitigasi komprehensif menggunakan **API Priority and Fairness (APF)** dan rancang ulang arsitektur Webhook agar anti-mati (*resilient*)!

<details>
<summary>🔍 Analisis Root Cause & Solusi Produksi</summary>

#### 1. Mekanisme Unindexed Listing & Memory Bloat di API Server
- Perintah `kubectl get pods -A` memaksa `kube-apiserver` menarik seluruh objek Pod di seluruh namespace kluster dari `etcd`.
- Jika kluster memiliki 20.000 Pod, API server harus:
  1. Mendekode representasi biner protocol buffer dari etcd ke objek Go runtime internal.
  2. Mengalokasikan ratusan megabyte memori di Heap untuk membangun struktur daftar objek raksasa.
  3. Mengonversi struktur objek Go tersebut ke format JSON untuk di-streaming ke client `kubectl`.
  4. Menjalankan Garbage Collection (GC) Go yang sangat intensif untuk membersihkan jutaan objek sementara.
- Jika skrip polling mengeksekusi perintah ini setiap 3 detik, alokasi memori heap terakumulasi lebih cepat daripada kemampuan Go runtime GC mereklaimnya, memicu kehabisan memori (*heap exhaustion*) dan memicu Linux kernel OOM Killer mematikan proses `kube-apiserver`.

#### 2. Admission Deadlock via `failurePolicy: Fail`
Konfigurasi webhook yang diterapkan memiliki celah arsitektural yang sangat fatal:
1. **Scope Terlalu Luas:** Webhook menangkap seluruh resource (`*`), seluruh operations (`*`), dan seluruh namespace (`*`), termasuk namespace sistem (`kube-system`).
2. **Dependensi Sirkular (Deadlock):**
   - Ketika Pod `validator-svc` mati akibat OOM, Kubernetes Controller Manager mencoba menjadwalkan ulang Pod tersebut di node lain.
   - Namun, proses pembuatan Pod `validator-svc` yang baru itu sendiri dicegat oleh `kube-apiserver` dan harus divalidasi oleh `validator-svc`!
   - Karena `validator-svc` sedang mati, koneksi HTTP request admission dari apiserver mengalami connection timeout (menunggu hingga 30 detik per request).
   - Karena disetel `failurePolicy: Fail`, `kube-apiserver` secara patuh **MENOLAK** pembuatan Pod baru tersebut.
   - Hasilnya: Pod validator tidak pernah bisa menyala kembali karena ia menolak dirinya sendiri (*circular dependency deadlock*), dan seluruh request lain di kluster ikut ditolak!

#### 3. Solusi & Mitigasi Produksi

**A. Hardening Webhook Configuration (Bypass System & Fast Fail):**
Ubah konfigurasi webhook untuk mengecualikan namespace kritis dan menggunakan `failurePolicy: Ignore` (atau setidaknya namespaceSelector filter):
```yaml
apiVersion: admissionregistration.k8s.io/v1
kind: ValidatingWebhookConfiguration
metadata:
  name: corp-security-gatekeeper
webhooks:
  - name: security.corp.internal
    rules:
      - operations: ["CREATE", "UPDATE"]
        apiGroups: ["apps", ""]
        apiVersions: ["v1"]
        resources: ["pods", "deployments"]
    failurePolicy: Ignore          # Fallback aman jika webhook down
    timeoutSeconds: 3              # Potong timeout dari 30s ke 3s
    namespaceSelector:
      matchExpressions:
        - key: kubernetes.io/metadata.name
          operator: NotIn
          values: ["kube-system", "kube-node-lease", "security"]
    clientConfig:
      service:
        name: validator-svc
        namespace: security
        path: /validate
```

**B. Isolasi Traffic dengan API Priority and Fairness (APF):**
Konfigurasikan `FlowSchema` khusus untuk membatasi kuota antrean (*concurrency limit*) bagi ServiceAccount skrip automasi internal agar tidak menenggelamkan antrean request operasional kritis:
```yaml
apiVersion: flowcontrol.apiserver.k8s.io/v1
kind: FlowSchema
metadata:
  name: throttle-automation-scripts
spec:
  priorityLevelConfiguration:
    name: catch-all
  matchingPrecedence: 500
  distinguisherMethod:
    type: ByUser
  rules:
    - subjects:
        - kind: User
          user:
            name: "system:serviceaccount:default:audit-script-sa"
      resourceRules:
        - verbs: ["list", "get"]
          apiGroups: ["*"]
          resources: ["pods"]
```

**C. Ganti Polling dengan Informer/Watch:**
Ubah arsitektur skrip internal dari model polling HTTP `GET` berulang menjadi arsitektur streaming berbasis **Informer / Watch API** (menggunakan client-go atau library Kubernetes SDK), yang memanfaatkan koneksi persistent HTTP/2 chunked streaming dengan konsumsi resource mendekati nol.
</details>

---

## 4. Chapter Challenge

### Tantangan Praktis: Deep Control Plane & Worker Node Diagnostics & Hardening Architect

#### Deskripsi Misi
Sebagai Lead Platform Architect, Anda diminta untuk membangun prosedur audit kepatuhan dan otomasi remediasi untuk kluster Kubernetes v1.28+ bare-metal sebelum kluster tersebut diserahkan ke tim security perbankan. Anda harus memverifikasi integritas Control Plane, menyelaraskan konfigurasi Worker Node, dan mengimplementasikan skrip pemantau kesehatan mandiri (*self-healing sentinel*).

#### Deliverables & Persyaratan Teknis

1. **Bagian A: Verifikasi & Backup Database etcd mTLS**
   - Susun perintah CLI deklaratif `etcdctl` menggunakan otentikasi sertifikat X.509 mTLS (`ca.crt`, `server.crt`, `server.key`) untuk:
     1. Menampilkan tabel status kesehatan seluruh endpoint kluster etcd (`endpoint health` dan `endpoint status -w table`).
     2. Mengambil snapshot database yang konsisten ke direktori `/opt/k8s-backup/etcd-snapshot-preaudit.db`.
     3. Memverifikasi integritas berkas snapshot tersebut melalui output pembacaan status snapshot (`etcdctl snapshot status`).

2. **Bagian B: Standardisasi Cgroup v2 & Kubelet Configuration**
   - Siapkan konfigurasi deklaratif `/etc/containerd/config.toml` yang mewajibkan `SystemdCgroup = true` pada runc runtime.
   - Siapkan potongan deklarasi `/var/lib/kubelet/config.yaml` yang memastikan `cgroupDriver: systemd` serta mengatur threshold proteksi eviksi disk dan memori.

3. **Bagian C: Skrip Otomasi Diagnostik Node Engine (`k8s_node_engine_sentinel.sh`)**
   - Tulis sebuah skrip Bash modular tingkat produksi dengan standar *defensive programming* (`set -euo pipefail`).
   - Skrip harus berjalan di worker node dan secara otomatis melakukan pengujian:
     - **Test 1:** Memverifikasi keselarasan Cgroup Driver antara containerd dan Kubelet (wajib sama-sama `systemd`).
     - **Test 2:** Memeriksa latensi respons soket gRPC containerd CRI (`/run/containerd/containerd.sock`).
     - **Test 3:** Memeriksa rasio utilisasi tabel `nf_conntrack` Linux kernel (`count / max * 100%`); jika utilisasi > 75%, beri peringatan; jika > 90%, kembalikan status CRITICAL.
     - **Test 4:** Memeriksa apakah terdapat event `PLEG is not healthy` di log Kubelet dalam 10 menit terakhir.
     - Mengembalikan exit code `0` jika seluruh tes hijau, dan `1` jika ditemukan anomali kritis.

---

### Solusi Referensi & Pembahasan Chapter Challenge

#### Bagian A: Prosedur Audit & Snapshot etcd mTLS
Simpan dan jalankan prosedur audit etcd berikut pada node control plane:

```bash
#!/usr/bin/env bash
set -euo pipefail

# Konfigurasi Variabel Sertifikat & Endpoint
ETCD_CA="/etc/kubernetes/pki/etcd/ca.crt"
ETCD_CERT="/etc/kubernetes/pki/etcd/server.crt"
ETCD_KEY="/etc/kubernetes/pki/etcd/server.key"
BACKUP_DIR="/opt/k8s-backup"
SNAPSHOT_PATH="${BACKUP_DIR}/etcd-snapshot-preaudit.db"

mkdir -p "${BACKUP_DIR}"

echo "=== 1. Memeriksa Kesehatan Endpoint etcd ==="
ETCDCTL_API=3 etcdctl \
  --cacert="${ETCD_CA}" \
  --cert="${ETCD_CERT}" \
  --key="${ETCD_KEY}" \
  --endpoints="https://127.0.0.1:2379" \
  endpoint health

echo -e "\n=== 2. Memeriksa Status Quorum & Ukuran Database etcd ==="
ETCDCTL_API=3 etcdctl \
  --cacert="${ETCD_CA}" \
  --cert="${ETCD_CERT}" \
  --key="${ETCD_KEY}" \
  --endpoints="https://127.0.0.1:2379" \
  --write-out=table \
  endpoint status

echo -e "\n=== 3. Mengambil Snapshot Database etcd ==="
ETCDCTL_API=3 etcdctl \
  --cacert="${ETCD_CA}" \
  --cert="${ETCD_CERT}" \
  --key="${ETCD_KEY}" \
  --endpoints="https://127.0.0.1:2379" \
  snapshot save "${SNAPSHOT_PATH}"

echo -e "\n=== 4. Memvalidasi Integritas File Snapshot ==="
ETCDCTL_API=3 etcdctl \
  --write-out=table \
  snapshot status "${SNAPSHOT_PATH}"

echo -e "\n[SUCCESS] Audit & Backup etcd Selesai Tanpa Error."
```

---

#### Bagian B: Konfigurasi Selaras Cgroups v2 & Kubelet

**1. Konfigurasi Containerd (`/etc/containerd/config.toml`):**
```toml
version = 2
[plugins]
  [plugins."io.containerd.grpc.v1.cri"]
    sandbox_image = "registry.k8s.io/pause:3.9"
    [plugins."io.containerd.grpc.v1.cri".containerd]
      default_runtime_name = "runc"
      [plugins."io.containerd.grpc.v1.cri".containerd.runtimes]
        [plugins."io.containerd.grpc.v1.cri".containerd.runtimes.runc]
          runtime_type = "io.containerd.runc.v2"
          [plugins."io.containerd.grpc.v1.cri".containerd.runtimes.runc.options]
            SystemdCgroup = true
```

**2. Konfigurasi Kubelet (`/var/lib/kubelet/config.yaml`):**
```yaml
apiVersion: kubelet.config.k8s.io/v1beta1
kind: KubeletConfiguration
cgroupDriver: systemd
cgroupRoot: /
cgroupsPerQOS: true
enforceNodeAllocatable:
  - pods
# Proteksi Eviksi Keras & Lunak
evictionHard:
  memory.available: "500Mi"
  nodefs.available: "10%"
  nodefs.inodesFree: "5%"
  imagefs.available: "15%"
# Sinkronisasi NodeLease & PLEG
nodeStatusUpdateFrequency: 10s
containerLogMaxSize: 50Mi
containerLogMaxFiles: 5
```

---

#### Bagian C: Skrip Diagnostik `k8s_node_engine_sentinel.sh`

```bash
#!/usr/bin/env bash
# ==============================================================================
# Script: k8s_node_engine_sentinel.sh
# Deskripsi: Diagnostic Sentinel untuk Worker Node Kubernetes Internals
# Target: Cgroup consistency, containerd gRPC socket, conntrack, & PLEG health
# Standar: Bash Strict Mode (set -euo pipefail)
# ==============================================================================
set -euo pipefail

# Kode Warna Terminal
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

EXIT_CODE=0

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
    EXIT_CODE=1
}

echo "=================================================================="
echo "    KUBERNETES NODE ENGINE HEALTH & CONFIGURATION SENTINEL        "
echo "=================================================================="
log_info "Memulai pengujian kesehatan internal node pada $(date)..."

# ------------------------------------------------------------------------------
# Test 1: Verifikasi Keselarasan Cgroup Driver
# ------------------------------------------------------------------------------
log_info "1. Memeriksa keselarasan driver cgroup (Containerd vs Kubelet)..."

# Deteksi Driver pada Containerd
CONTAINERD_CONF="/etc/containerd/config.toml"
if [ -f "$CONTAINERD_CONF" ]; then
    if grep -q "SystemdCgroup = true" "$CONTAINERD_CONF"; then
        log_pass "Containerd dikonfigurasi dengan SystemdCgroup = true"
    else
        log_fail "Containerd TIDAK menggunakan SystemdCgroup = true di $CONTAINERD_CONF"
    fi
else
    log_warn "Berkas $CONTAINERD_CONF tidak ditemukan, memeriksa proses runtime..."
fi

# Deteksi Driver pada Kubelet Config
KUBELET_CONF="/var/lib/kubelet/config.yaml"
if [ -f "$KUBELET_CONF" ]; then
    KUBELET_CGROUP=$(grep "cgroupDriver:" "$KUBELET_CONF" | awk '{print $2}' || true)
    if [ "$KUBELET_CGROUP" == "systemd" ]; then
        log_pass "Kubelet dikonfigurasi dengan cgroupDriver: systemd"
    else
        log_fail "Kubelet menggunakan driver [$KUBELET_CGROUP], diharapkan 'systemd'!"
    fi
else
    log_fail "Berkas konfigurasi Kubelet $KUBELET_CONF tidak ditemukan!"
fi

# ------------------------------------------------------------------------------
# Test 2: Pengujian Soket CRI gRPC Containerd
# ------------------------------------------------------------------------------
log_info "2. Memeriksa ketersediaan dan latensi CRI UNIX Domain Socket..."
CRI_SOCK="/run/containerd/containerd.sock"

if [ -S "$CRI_SOCK" ]; then
    log_pass "UNIX domain socket [$CRI_SOCK] aktif dan terdeteksi."
    
    # Uji konektivitas via crictl jika tersedia
    if command -v crictl &> /dev/null; then
        if crictl --runtime-endpoint "unix://$CRI_SOCK" info &> /dev/null; then
            log_pass "Komunikasi gRPC CRI via crictl berhasil merespons."
        else
            log_fail "Panggilan gRPC crictl ke [$CRI_SOCK] gagal atau timeout!"
        fi
    else
        log_warn "Perintah 'crictl' tidak ditemukan di PATH, lewati uji level gRPC."
    fi
else
    log_fail "Soket CRI [$CRI_SOCK] TIDAK ditemukan! Container runtime mungkin mati."
fi

# ------------------------------------------------------------------------------
# Test 3: Analisis Rasio Utilisasi Tabel Conntrack Kernel
# ------------------------------------------------------------------------------
log_info "3. Memeriksa utilisasi tabel nf_conntrack kernel Linux..."

if [ -f "/proc/sys/net/netfilter/nf_conntrack_count" ] && [ -f "/proc/sys/net/netfilter/nf_conntrack_max" ]; then
    CONN_COUNT=$(cat /proc/sys/net/netfilter/nf_conntrack_count)
    CONN_MAX=$(cat /proc/sys/net/netfilter/nf_conntrack_max)
    
    # Hitung persentase utilisasi menggunakan aritmatika integer
    CONN_PERCENT=$(( CONN_COUNT * 100 / CONN_MAX ))
    
    if [ "$CONN_PERCENT" -ge 90 ]; then
        log_fail "Utilisasi Conntrack KRITIS: $CONN_PERCENT% ($CONN_COUNT / $CONN_MAX). Risiko tinggi packet drop!"
    elif [ "$CONN_PERCENT" -ge 75 ]; then
        log_warn "Utilisasi Conntrack TINGGI: $CONN_PERCENT% ($CONN_COUNT / $CONN_MAX)."
    else
        log_pass "Utilisasi Conntrack AMAN: $CONN_PERCENT% ($CONN_COUNT / $CONN_MAX)."
    fi
else
    log_warn "Modul netfilter/conntrack tidak aktif atau path procfs tidak ditemukan."
fi

# ------------------------------------------------------------------------------
# Test 4: Inspeksi Health Status PLEG di Journalctl
# ------------------------------------------------------------------------------
log_info "4. Memindai log Kubelet untuk anomali PLEG (10 menit terakhir)..."

if command -v journalctl &> /dev/null; then
    PLEG_ERRORS=$(journalctl -u kubelet --since "10 minutes ago" --no-pager | grep -i "PLEG is not healthy" || true)
    
    if [ -n "$PLEG_ERRORS" ]; then
        log_fail "Terdeteksi event 'PLEG is not healthy' dalam 10 menit terakhir:"
        echo "$PLEG_ERRORS" | tail -n 3
    else
        log_pass "Tidak ada event 'PLEG is not healthy' terdeteksi dalam 10 menit terakhir."
    fi
else
    log_warn "Util journalctl tidak tersedia untuk memeriksa log Kubelet."
fi

# ------------------------------------------------------------------------------
# Evaluasi Akhir
# ------------------------------------------------------------------------------
echo "=================================================================="
if [ "$EXIT_CODE" -eq 0 ]; then
    log_pass "SELURUH PENGUJIAN SELESAI: Node dalam kondisi SEHAT & SESUAI STANDAR."
else
    log_fail "PENGUJIAN SELESAI DENGAN ANOMALI: Periksa log FAIL di atas untuk remediasi!"
fi
echo "=================================================================="

exit "$EXIT_CODE"
```

---

## 5. Knowledge Check & Checklist

Gunakan checklist ini untuk mengukur kesiapan dan penguasaan materi teknis Anda sebelum melangkah ke Bab 02:

### Saya Harus Memahami (Conceptual & Architectural Mastery):
- [ ] **Hierarki Control Plane:** Mengapa hanya `kube-apiserver` yang memiliki koneksi TCP ke `etcd`, dan peran stateless architecture-nya.
- [ ] **Teori Konsensus Raft etcd:** Formula perhitungan Quorum ($\lfloor N/2 \rfloor + 1$), mengapa jumlah node ganjil wajib digunakan, dan bahaya split-brain.
- [ ] **Mekanisme Storage etcd:** Cara kerja Write-Ahead Log (WAL), operasi disk `fsync`, penyimpanan key-value berbasis bbolt MVCC, serta dampak defragmentasi dan compaction.
- [ ] **Pipeline 6 Tahap API Server:** Alur Authentication, Authorization (RBAC/Node), Mutating Admission Webhook, Schema Validation, Validating Admission Webhook, dan Storage Serialization.
- [ ] **Dua Fase Kube-Scheduler:** Perbedaan mendasar algoritma Filtering (Predicates) dan Scoring (Priorities) serta eksekusi binding.
- [ ] **Reconciliation Loop:** Pola deklaratif *Observe $\rightarrow$ Analyze $\rightarrow$ Act* pada `kube-controller-manager` dan kontrol konkurensi optimistik (OCC) via `resourceVersion`.
- [ ] **Kubelet & PLEG Engine:** Cara kerja relist loop Kubelet terhadap soket CRI gRPC containerd dan penyebab alert `PLEG is not healthy`.
- [ ] **Cgroups v2 & Systemd Alignment:** Mengapa Kubelet dan Containerd wajib sama-sama menggunakan driver `systemd` guna mencegah perebutan wewenang kernel.
- [ ] **Peran Pause Container:** Alasan isolasi Linux Network/IPC Namespace ditambatkan pada container pause (`pause.c`) serta fungsi zombie process reaping.
- [ ] **Data Plane Jaringan Kube-Proxy:** Perbedaan kompleksitas evaluasi paket antara `iptables` ($O(N)$) vs `IPVS` ($O(1)$) dan keunggulan eBPF.

---

### Saya Tidak Perlu Menghafal (Reference / Non-Essential Memorization):
- [ ] Menghafal seluruh puluhan flag CLI bawaan `kubelet` atau `etcd` di luar kepala (cukup kuasai struktur deklaratif file konfigurasi YAML/TOML resminya).
- [ ] Menghafal representasi biner protocol buffer internal atau struktur struct Go di kode sumber Kubernetes.
- [ ] Menghafal nomor byte hex format file snapshot WAL etcd.
- [ ] Menghafal ratusan opsi skema spesifikasi OpenAPI (cukup manfaatkan perintah `kubectl explain <resource>.<field>`).

---

### Saya Harus Bisa Melakukan (Operational & Diagnostic Skills):
- [ ] Menginspeksi kesehatan kluster etcd melalui perintah CLI `etcdctl` mTLS (`endpoint health`, `endpoint status -w table`).
- [ ] Membuat snapshot cadangan etcd yang konsisten serta memverifikasi integritas file backup sebelum melakukan upgrade kluster.
- [ ] Mendiagnosa dan mengatasi penyebab worker node berstatus `NotReady` melalui analisis log `journalctl -u kubelet` dan `dmesg`.
- [ ] Menyelaraskan driver cgroup menjadi `systemd` pada `/etc/containerd/config.toml` dan `/var/lib/kubelet/config.yaml`.
- [ ] Melakukan tuning kernel Linux sysctl untuk metrik jaringan kritis seperti `net.netfilter.nf_conntrack_max`.
- [ ] Mengonfigurasi `ValidatingWebhookConfiguration` defensif dengan pengecualian namespace sistem dan `timeoutSeconds` rendah guna menghindari admission deadlock.
- [ ] Membaca event scheduler untuk mendiagnosa alasan kegagalan alokasi Pod (`0/N nodes available: Insufficient memory/cpu`).

---
[⬅️ Module 02: Arsitektur Lanjutan & Deep Dive](./Module-02-kubernetes-Bab-01.md) | [📋 Silabus Induk](../README.md) | [BAB 02 Module 01: Anatomi Pod & Lifecycle ➡️](../BAB-02-Pod-Lifecycle-dan-Multi-Container-Patterns/Module-01-Anatomi-Pod-Lifecycle-Probes-dan-Termination.md)
---
