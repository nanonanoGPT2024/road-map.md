# Module 02: High Availability, Chaos Engineering, & FinOps (Cloud Cost Optimization)

## 1. Learning Objective
Setelah menyelesaikan modul ini, pembelajar diharapkan mampu:
- Merancang arsitektur sistem dengan ketersediaan tinggi (**High Availability**) dan strategi **Disaster Recovery (DR)** berdasarkan **RTO** (*Recovery Time Objective*) dan **RPO** (*Recovery Point Objective*).
- Membedakan topologi pemulihan bencana: *Active-Active Multi-Region*, *Active-Passive (Warm Standby)*, dan *Pilot Light*.
- Memahami prinsip **Chaos Engineering**: menyuntikkan kegagalan terkontrol (*fault injection*) ke dalam sistem untuk menemukan kerentanan sebelum terjadi insiden produksi nyata.
- Merancang eksperimen chaos menggunakan alat seperti **Chaos Mesh** atau **LitmusChaos** (Pod Failure, Network Latency, DNS Chaos).
- Menguasai disiplin **FinOps (Financial Operations)** untuk memangkas pemborosan biaya cloud hingga 50-70% tanpa mengorbankan performa.
- Mengonfigurasi autoscaler modern (**Karpenter**) yang memadukan **Spot Instances**, **Right-Sizing**, dan **Savings Plans**.

---

## 2. Prerequisite
- Memahami konsep dasar Kubernetes Horizontal Pod Autoscaler (HPA) dan Cluster Autoscaler (BAB 04).
- Memahami prinsip SRE, SLI/SLO, dan Error Budgets (BAB 10 Module 01).
- Pengetahuan dasar tentang model penagihan komputasi cloud (On-Demand, Spot/Preemptible, Reserved Instances).

---

## 3. Concept
Dua pilar modern dalam mengoperasikan sistem berskala masif:
1. **Ketahanan Melalui Kegagalan yang Disengaja (Chaos Engineering)**: Alih-alih berharap sistem tidak pernah rusak, kita berasumsi bahwa segala sesuatu pasti akan gagal (*everything fails all the time*). Chaos Engineering secara proaktif menyuntikkan gangguan (mematikan server tiba-tiba, memutus kabel jaringan virtual, memperlambat database) di jam kerja terkontrol untuk memverifikasi apakah sistem otomatis memulihkan diri (*self-healing*).
2. **Efisiensi Finansial Berkelanjutan (FinOps)**: Cloud computing menawarkan skalabilitas tak terbatas, namun jika tidak diawasi, tagihan bulanan akan meledak (*bill shock*). FinOps adalah perpaduan budaya, otomatisasi, dan rekayasa untuk memaksimalkan nilai setiap dolar yang dibelanjakan di cloud melalui penghapusan resource tak terpakai (*idle resources*), pemilihan tipe instance cerdas, dan diskon komitmen jangka panjang.

```
       ┌────────────────────────┐                   ┌────────────────────────┐
       │   CHAOS ENGINEERING    │                   │        FINOPS          │
       ├────────────────────────┤                   ├────────────────────────┤
       │ "Uji ketahanan sistem  │                   │ "Bayar hanya apa yang  │
       │  dengan merusak server │                   │  benar-benar dipakai   │
       │  secara terencana"     │                   │  secara efisien"       │
       └───────────┬────────────┘                   └───────────┬────────────┘
                   │                                            │
                   ▼                                            ▼
       [ Auto-Healing Verified ]                    [ 60% Cloud Cost Savings ]
```

---

## 4. Why?
1. **Mencegah Keruntuhan Kaskade (*Cascading Failures*)**: Masalah kecil (misal cache Redis restart) sering memicu efek domino yang menenggelamkan seluruh database utama karena ratusan worker menyerbu database secara serempak (*thundering herd*). Eksperimen chaos membuktikan apakah circuit breaker dan rate limiter bekerja sesuai desain.
2. **Kepatuhan RTO & RPO Nyata**: Menulis rencana pemulihan bencana 100 halaman di dokumen Word tidak ada gunanya jika tidak pernah diuji secara berkala. Chaos engineering menguji apakah target RTO (misal pulih $< 15$ menit) benar-benar tercapai saat satu zona ketersediaan (*Availability Zone*) padam.
3. **Menghentikan Pemborosan Cloud (Cloud Waste)**: Rata-rata 30-45% anggaran cloud terbuang sia-sia karena developer mengalokasikan CPU/Memory 10x lebih besar dari kebutuhan riil (*overprovisioning*), disk volume yang tidak terikat (*orphaned EBS*), dan cluster testing yang tetap hidup di akhir pekan.

---

## 5. What?
Komponen dan metrik kunci:
- **RTO (Recovery Time Objective)**: Batas waktu maksimal yang ditoleransi untuk memulihkan sistem kembali online setelah terjadi bencana (contoh: RTO = 15 menit).
- **RPO (Recovery Point Objective)**: Batas usia data maksimal yang boleh hilang saat bencana terjadi, ditentukan oleh frekuensi backup dan replikasi data (contoh: RPO = 5 menit data transaksi).
- **Blast Radius**: Batas cakupan dampak yang diizinkan saat eksperimen chaos dijalankan (misal hanya 2% pengguna di satu region canary).
- **Karpenter**: Autoscaler node Kubernetes generasi baru yang memilih tipe instance EC2 secara dinamis dalam hitungan detik (menggantikan Cluster Autoscaler yang lambat).
- **Spot Instances**: Kapasitas komputasi cloud cadangan yang dijual dengan diskon hingga 70-90% dengan konsekuensi cloud provider dapat menarik kembali instance tersebut dengan pemberitahuan 2 menit (*preemption*).
- **Kubecost**: Platform monitoring biaya real-time per Kubernetes namespace, pod, dan label departemen.

---

## 6. How?
Langkah Menjalankan Eksperimen Chaos (Metodologi Ilmiah):
1. **Tentukan Kondisi Normal (*Steady State*)**: Ukur metrik normal sistem (misal: RPS 5.000, latency $p99 < 150\text{ms}$, HTTP error rate $< 0.05\%$).
2. **Buat Hipotesis**: *"Jika kita mematikan pod master Redis, Sentinel akan mempromosikan Replica dalam 8 detik, dan aplikasi akan membaca data dari DB tanpa menyebabkan lonjakan HTTP 500 $> 1\%$."*
3. **Suntikkan Gangguan Terkontrol**: Menggunakan Chaos Mesh CRD, suntikkan `PodChaos` yang me-kill Redis pod secara acak.
4. **Bandingkan Steady State vs Gangguan**: Amati dashboard Grafana. Apakah hipotesis terbukti?
5. **Perbaiki Kelemahan**: Jika hipotesis gagal (misal aplikasi crash karena retry connection tak terhingga), perbaiki kode aplikasi, lalu ulangi eksperimen hingga tangguh.

Langkah Optimalisasi FinOps di Kubernetes:
1. **Visibility**: Pasang Kubecost untuk memetakan alokasi biaya per tim.
2. **Right-Sizing**: Jalankan Goldilocks / Vertical Pod Autoscaler dalam mode rekomendasi untuk memangkas request CPU/Memory yang mubazir.
3. **Migrasi ke Karpenter & Spot Instances**: Konfigurasikan NodePool Karpenter untuk memprioritaskan Spot Instances pada stateless microservices, dengan fallback otomatis ke On-Demand.

---

## 7. Analogy
- **Chaos Engineering** seperti **Latihan Evakuasi Kebakaran Gedung (*Fire Drill*)**: Gedung menyalakan sirine palsu di siang hari kerja untuk memastikan seluruh karyawan tahu pintu darurat mana yang harus dilalui dan apakah tangga darurat tidak terkunci. Jika sirine tidak pernah diuji, saat kebakaran sungguhan terjadi, semua orang akan panik dan terjebak.
- **FinOps & Spot Instances** seperti **Membeli Tiket Pesawat Last-Minute Standby**: Kursi pesawat kosong yang tersisa 3 jam sebelum terbang dijual dengan diskon 80%. Wisatawan ransel (*stateless microservices*) senang menggunakan tiket murah ini karena jika tidak kebagian kursi, mereka bisa menunggu penerbangan 10 menit berikutnya tanpa masalah, sementara eksekutif bisnis darurat (*primary database*) tetap membayar tiket kelas bisnis penuh (*On-Demand / Reserved*).

---

## 8. Diagram
```
+-----------------------------------------------------------------------------------+
|               MULTI-REGION HIGH AVAILABILITY & DISASTER RECOVERY                  |
+-----------------------------------------------------------------------------------+

                          [ Global Route 53 DNS ]
                         (Healthcheck Probing 10s)
                                    │
               ┌────────────────────┴────────────────────┐
               │ Active Traffic (90%)                    │ Failover Traffic (10%)
               ▼                                         ▼
 ┌───────────────────────────┐             ┌───────────────────────────┐
 │ Primary Region: Singapore │             │ Secondary Region: Jakarta │
 │  [ Ingress Gateway ]      │             │  [ Ingress Gateway ]      │
 │  [ EKS Pods Replicas ]    │             │  [ EKS Pods Replicas ]    │
 │                           │             │                           │
 │  ┌─────────────────────┐  │             │  ┌─────────────────────┐  │
 │  │ Aurora PostgreSQL   │  │             │  │ Aurora Read Replica │  │
 │  │ (Primary Read/Write)│──┼─ Cross-Sync ┼─>│ (Warm Standby)      │  │
 │  └─────────────────────┘  │  (RPO < 1s) │  └─────────────────────┘  │
 └───────────────────────────┘             └───────────────────────────┘
               │                                         │
               └───────── [ Chaos Mesh GameDay ] ────────┘
                          (Simulate Singapore DC Outage)
                          ↳ RTO: Jakarta auto-promoted in 45s!
```

---

## 9. Simple Example: Definisi Eksperimen Chaos Mesh
Manifest Kubernetes untuk menyuntikkan latensi jaringan 200ms secara acak pada pod billing (`network-delay.yaml`):

```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: NetworkChaos
metadata:
  name: simulate-slow-payment-network
  namespace: production
spec:
  action: delay
  mode: fixed
  value: '2' # Suntikkan hanya ke 2 pod
  selector:
    namespaces:
      - production
    labelSelectors:
      app: payment-api
  delay:
    latency: '200ms'
    jitter: '20ms'
    correlation: '50'
  duration: '5m' # Hentikan eksperimen otomatis setelah 5 menit
```

---

## 10. Practical Example: Karpenter NodePool dengan Spot Instances
Manifest Karpenter untuk menghemat biaya komputasi hingga 70% di AWS EKS (`nodepool.yaml`):

```yaml
apiVersion: karpenter.sh/v1beta1
kind: NodePool
metadata:
  name: general-stateless-spot
spec:
  template:
    spec:
      requirements:
        # Prioritaskan Spot Instances untuk efisiensi FinOps
        - key: "karpenter.sh/capacity-type"
          operator: In
          values: ["spot", "on-demand"]
        # Pilih arsitektur ARM64 (AWS Graviton) untuk performa per-dollar lebih tinggi
        - key: "kubernetes.io/arch"
          operator: In
          values: ["arm64"]
        - key: "karpenter.k8s.aws/instance-category"
          operator: In
          values: ["c", "m", "r"]
      nodeClassRef:
        name: default-ec2-node-class
  # FinOps: Matikan node kosong secara agresif dalam 30 detik
  disruption:
    consolidationPolicy: WhenUnderutilized
    expireAfter: 720h
```

---

## 11. Real World Example: Netflix Chaos Monkey & Migrasi FinOps Graviton
1. **Netflix Chaos Engineering**: Netflix menciptakan *Simian Army* (Chaos Monkey) yang secara otomatis mematikan instans komputasi AWS acak di lingkungan produksi setiap hari kerja. Rekayasa ini memaksa seluruh engineer mendesain microservices yang kebal terhadap kehilangan server, sehingga saat terjadi pemadaman listrik massal di salah satu data center AWS, pelanggan Netflix di seluruh dunia tidak merasakan buffering sama sekali.
2. **Migrasi FinOps Multi-Juta Dolar**: Sebuah platform fintech memigrasikan 400 node Kubernetes dari x86 On-Demand (`m5.large`) ke ARM64 AWS Graviton Spot Instances (`m6g.large`):
   - Penggunaan Spot Instance memangkas biaya per jam sebesar 72%.
   - Chip Graviton memberikan efisiensi komputasi 20% lebih cepat untuk workload Go dan Java.
   - Hasil audit FinOps: Penghematan tahunan mencapai $420.000 (Rp 6,5 Miliar), dialihkan untuk ekspansi tim R&D.

---

## 12. Trade-offs

| Aspek | Tanpa Chaos & FinOps | Menerapkan Chaos & FinOps |
|---|---|---|
| **Kesiapan Menghadapi Bencana** | Teoretis (Sistem sering tumbang di skenario tak terduga) | Terbukti secara empiris melalui GameDay |
| **Biaya Bulanan Cloud** | Sangat Boros (Overprovisioning & idle resources) | Optimal (Konsolidasi cerdas & Spot Instances) |
| **Kesiapan Aplikasi** | Bebas (Kode sederhana tanpa retry/fallback) | Menuntut arsitektur stateless & resilient |
| **Kompleksitas Tooling** | Rendah (Gunakan default cloud VM) | Menengah (Chaos Mesh, Karpenter, Kubecost) |

---

## 13. When To Use
- Sistem berskala besar dengan beban traffic jutaan pengguna dan anggaran cloud bulanan di atas $5.000/bulan.
- Aplikasi yang mewajibkan SLA ketersediaan tinggi ($99.95\%+$) di mana downtime beberapa menit menyebabkan kerugian miliaran rupiah.
- Lingkungan Kubernetes dengan beban kerja elastis (batch processing, data engineering, stateless web apps).

---

## 14. When NOT To Use
- Jangan jalankan eksperimen chaos di produksi pada hari pertama peluncuran sistem baru (mulai dari staging terlebih dahulu).
- Jangan gunakan Spot Instances untuk database stateful master (PostgreSQL / MySQL primary) tanpa replikasi sinkron cepat, karena preemption 2 menit dapat memicu data corruption jika storage tidak terkelola dengan baik.

---

## 15. Common Mistakes
1. **Chaos Tanpa Blast Radius**: Menjalankan eksperimen chaos di seluruh cluster produksi sekaligus tanpa sakelar darurat (*kill switch*). Jika terjadi anomali tak terduga, eksperimen dapat meluas menjadi pemadaman nasional. Selalu mulai dengan 1 pod atau 1 subnet.
2. **FinOps Sebagai Proyek Satu Kali**: Menjalankan audit pembersihan cloud satu kali, lalu melupakannya. Tiga bulan kemudian, biaya cloud akan membengkak kembali. FinOps harus menjadi proses berkelanjutan (*Inform -> Optimize -> Operate*).
3. **Mengabaikan Pod Disruption Budgets (PDB)**: Menggunakan Spot Instances tanpa mengonfigurasi PDB di Kubernetes. Saat AWS merebut kembali node Spot, Kubernetes mematikan banyak pod sekaligus sehingga layanan mengalami downtime sesaat. PDB memastikan minimal X replica selalu aktif melayani pengguna.

---

## 16. Best Practices
### Must Have
- Konfigurasikan **PodDisruptionBudget (PDB)** untuk seluruh Deployment produksi: `minAvailable: 1` atau `maxUnavailable: 25%`.
- Tetapkan target kuantitatif **RTO** dan **RPO** untuk setiap tingkat keparahan bencana (Tier-1 hingga Tier-3 apps).
- Pasang label tag kepemilikan biaya wajib pada seluruh resource cloud (`Environment`, `Team`, `Service`, `CostCenter`).

### Recommended
- Gelar simulasi **GameDay** berkala (misal 3 bulan sekali): tim SRE sengaja menyimulasikan skenario server down di staging/prod untuk melatih refleks tim on-call.
- Gunakan Karpenter dengan tipe instance beragam (*instance diversification*) pada konfigurasi Spot agar saat satu tipe instance langka di pasar AWS, Karpenter otomatis memilih tipe alternatif.

### Advanced
- Gabungkan Multi-Region Active-Active deployment dengan AWS Route 53 Application Recovery Controller (ARC) untuk automated DNS failover tanpa campur tangan manusia.

---

## 17. Troubleshooting
- **Masalah**: Pod sering mengalami evict mendadak saat menggunakan Spot Instances di Kubernetes.
  - *Diagnostik*: Jalankan `kubectl describe pod` dan periksa event log node: `Node interrupted by AWS EC2 Spot Rebalance Recommendation`.
  - *Solusi*: Pasang `aws-node-termination-handler` atau gunakan Karpenter bawaan yang otomatis menangani sinyal preemption 2 menit untuk melakukan *graceful pod draining*.
- **Masalah**: Eksperimen Chaos Mesh tidak berhenti saat durasi selesai.
  - *Solusi*: Pastikan daemon Chaos Dashboard dan controller manager memiliki izin RBAC untuk membersihkan aturan iptables/tc di namespace worker node.

---

## 18. Exercise
1. Tulis manifest Kubernetes `PodDisruptionBudget` untuk layanan katalog dengan 4 replica yang menjamin minimal 3 replica harus selalu sehat saat terjadi node maintenance atau spot interruption.
2. Hitung penghematan biaya bulanan jika sebuah sistem yang menggunakan 10 instance On-Demand seharga $0.10/jam dimigrasikan ke Spot Instances seharga $0.03/jam.

---

## 19. Challenge
Rancang arsitektur High Availability & FinOps terintegrasi:
- Definisikan konfigurasi multi-tier EKS:
  - Database primary berjalan pada On-Demand instance di Multi-AZ.
  - 10 Stateless microservices berjalan pada Karpenter Spot NodePool dengan graviton ARM64.
- Tulis skenario pengujian Chaos Engineering untuk menyuntikkan kegagalan node spot mendadak.
- Buktikan bahwa ketersediaan sistem tetap berada di atas $99.9\%$ selama interupsi berlangsung dan hitung total efisiensi anggaran FinOps.

---

## 20. Summary
- **High Availability & Disaster Recovery** menjamin kelangsungan bisnis dengan metrik terukur **RTO** dan **RPO**.
- **Chaos Engineering** mengubah ketidakpastian menjadi keandalan empiris melalui eksperimen kegagalan terkontrol.
- **FinOps** memastikan pengeluaran cloud memberikan efisiensi bisnis maksimal melalui **Spot Instances**, **Right-Sizing**, dan **Karpenter Autoscaling**.
- Ketahanan sejati dicapai saat sistem mampu pulih secara mandiri (*self-heal*) dari kegagalan server fisik sekaligus menghemat anggaran infrastruktur perusahaan.
