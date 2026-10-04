# BAB 01: Quiz, Challenge, & Knowledge Check
**Fondasi & Arsitektur Rekayasa DevOps**

---

## 1. Basic Questions (5 Soal)

### Soal 1.1: Paradigma Push-Based CI/CD vs. Pull-Based GitOps
Jelaskan perbedaan arsitektural fundamental antara paradigma deployment *Push-based* (misal: Jenkins/GitLab CI runner yang menjalankan `kubectl apply`) dan *Pull-based GitOps* (misal: ArgoCD/Flux controller di dalam cluster). Fokuskan penjelasan pada tiga aspek: manajemen kredensial cluster, *attack surface area*, dan mekanisme deteksi divergensi status (*drift detection*).

<details>
<summary>Jawaban & Kunci Evaluasi</summary>

- **Manajemen Kredensial Cluster**:
  - *Push-Based*: CI runner/agent eksternal harus menyimpan token otentikasi cluster Kubernetes berprivilese tinggi (seperti `kubeconfig` dengan hak *cluster-admin* atau *service account secret*). Jika infrastruktur CI runner bocor atau terekspos via *arbitrary code execution* dalam build script, seluruh cluster produksi dapat dikompromikan.
  - *Pull-Based GitOps*: Tidak ada kredensial cluster yang keluar ke sistem eksternal. Operator GitOps (seperti ArgoCD Application Controller) berjalan langsung di dalam cluster (*in-cluster agent*) dan hanya membutuhkan akses baca (*read-only*) ke repository Git sumber artefak konfigurasi.
- **Attack Surface Area**:
  - *Push-Based*: Memerlukan port API Server Kubernetes (`6443`) dibuka ke publik atau ke subnet runner CI eksternal, memperlebar vektor serangan network ingress.
  - *Pull-Based GitOps*: API Server dapat sepenuhnya terisolasi dalam private network (private endpoint). Komunikasi keluar (*outbound polling* atau webhook via proxy) dilakukan dari dalam cluster ke Git repository, menerapkan prinsip *zero-ingress trust*.
- **Mekanisme Drift Detection**:
  - *Push-Based*: CI pipeline bersifat reaktif dan hanya berjalan sesaat (*fire-and-forget*). Jika terjadi perubahan manual langsung di cluster (misal: engineer melakukan `kubectl edit` darurat), CI runner tidak mengetahui anomali tersebut sampai ada komit baru yang menimpa.
  - *Pull-Based GitOps*: Memiliki *reconciliation loop* kontinu yang secara berkala (misal tiap 3 menit) membandingkan *desired state* di Git dengan *live state* di etcd cluster. Jika terdeteksi divergensi (*drift*), controller dapat langsung memberikan peringatan (*OutOfSync*) atau melakukan koreksi otomatis (*self-healing/auto-sync*).
</details>

---

### Soal 1.2: Metrik DORA (DevOps Research and Assessment)
Sebutkan 4 pilar metrik performa software delivery standar industri menurut DORA, definisikan formula kalkulasi **Change Failure Rate (CFR)**, dan jelaskan mengapa mengoptimalkan *Deployment Frequency* tanpa memantau CFR dapat menyebabkan bencana operasional!

<details>
<summary>Jawaban & Kunci Evaluasi</summary>

- **4 Metrik Utama DORA**:
  1. **Deployment Frequency (DF)**: Seberapa sering organisasi berhasil merilis kode ke lingkungan produksi (misal: harian, mingguan, bulanan).
  2. **Lead Time for Changes (LTFC)**: Waktu yang dibutuhkan sejak komit kode pertama kali masuk ke version control hingga kode tersebut berjalan aktif dan melayani traffic di produksi.
  3. **Change Failure Rate (CFR)**: Persentase rilis ke produksi yang mengakibatkan degradasi layanan, kegagalan fungsional, atau insiden yang memerlukan remediasi segera (seperti hotfix, rollback, atau patch darurat).
  4. **Time to Restore Service (TTRS / MTTR)**: Waktu rata-rata yang diperlukan untuk memulihkan layanan dari insiden produksi atau degradasi performa kembali ke status operasional normal.
- **Formula Change Failure Rate (CFR)**:
  $$\text{CFR} = \left( \frac{\sum \text{Deployment yang Memerlukan Rollback / Hotfix / Memicu Insiden}}{\sum \text{Total Seluruh Deployment ke Produksi}} \right) \times 100\%$$
- **Risiko Over-Optimizing Deployment Frequency tanpa CFR**:
  Deployment Frequency adalah metrik *throughput/velocity*, sedangkan CFR adalah metrik *quality/stability*. Jika tim hanya mengejar frekuensi deploy yang tinggi tanpa mengintegrasikan otomatisasi pengujian (*shift-left testing*), canary release, dan quality gate, tim hanya mempercepat pengiriman bug dan cacat sistem ke pengguna akhir (*high-velocity failure delivery*). Hal ini memicu kejenuhan tim on-call, kepanikan operasional (*toil overload*), dan mengikis kepercayaan pelanggan.
</details>

---

### Soal 1.3: Budaya CAMS/CALMS & Root Cause Fallacy
Dalam kerangka kerja CAMS (*Culture, Automation, Measurement, Sharing*), mengapa menyimpulkan "Human Error" sebagai akar masalah tunggal (*Root Cause*) dalam sebuah insiden produksi dianggap sebagai anti-pola berbahaya (*Root Cause Fallacy*)? Bagaimana prinsip *Blameless Post-Mortem* mengubah pendekatan investigasi tersebut?

<details>
<summary>Jawaban & Kunci Evaluasi</summary>

- **Root Cause Fallacy & "Human Error"**:
  Sistem terdistribusi modern adalah sistem sosio-teknikal yang kompleks (*Complex Adaptive Systems*). Menyatakan "human error" (misal: "operator salah mengetik flag perintah di terminal") sebagai akar penyebab adalah simplifikasi yang keliru. Kesalahan manusia adalah *gejala (symptom)* dari desain sistem yang rapuh, bukan penyebab akhir. Sistem yang baik harus dirancang toleran terhadap kesalahan manusia (*guardrails*, pembatasan izin akses, validasi deklaratif, dan simulasi pra-eksekusi).
- **Prinsip Blameless Post-Mortem**:
  1. *Second-Order Thinking*: Berasumsi bahwa seluruh engineer bertindak dengan niat baik dan mengambil keputusan paling masuk akal berdasarkan informasi yang tersedia pada saat itu (*local rationality*).
  2. *Fokus pada Sistem, Bukan Individu*: Pertanyaan bergeser dari *"Siapa yang merusak sistem?"* menjadi *"Mengapa sistem mengizinkan aksi berbahaya tersebut dieksekusi tanpa peringatan atau interupsi otomatis?"*, *"Mengapa telemetry tidak mendeteksi anomali lebih awal?"*, dan *"Mekanisme safety apa yang hilang di pipeline?"*.
  3. *Psychological Safety*: Menghilangkan ketakutan akan sanksi personal mendorong pelaporan insiden secara transparan dan detail, memungkinkan organisasi memperbaiki kelemahan sistemik sebelum berkembang menjadi kegagalan katastropik.
</details>

---

### Soal 1.4: Shift-Left Testing & Pipeline Quality Gates
Jelaskan konsep piramida pengujian (*Testing Pyramid*) dalam konteks prinsip *Shift-Left Testing* pada pipeline CI/CD modern, serta urutkan jenis pengujian dari yang paling kiri (paling cepat & murah) hingga paling kanan (paling lambat & mahal)!

<details>
<summary>Jawaban & Kunci Evaluasi</summary>

- **Konsep Shift-Left Testing**:
  Prinsip memindahkan aktivitas penjaminan kualitas, pengujian keamanan, dan validasi konfigurasi sedini mungkin ke tahap awal siklus pengembangan perangkat lunak (ke sisi kiri timeline SDLC). Tujuannya adalah mendeteksi dan memperbaiki cacat kode saat biaya perbaikannya masih minimal (orde hitungan menit di mesin developer) sebelum cacat tersebut menyebar ke artifact registry atau cluster staging/produksi.
- **Urutan Pengujian dari Kiri ke Kanan**:
  1. **Pre-commit / IDE Level**: Linter statis (`golangci-lint`, `eslint`), formatter (`prettier`), Git secrets scanner (`gitleaks`, `trufflehog`), dan validasi skema file konfigurasi.
  2. **Unit Testing & Mutation Testing**: Menguji logika fungsi terkecil secara terisolasi tanpa dependensi jaringan atau database nyata (menggunakan mock/stub). Waktu eksekusi orde detik.
  3. **Static Application Security Testing (SAST) & Dependency Scanning (SCA)**: Analisis kode sumber untuk mencari kerentanan OWASP Top 10 dan identifikasi *Known Vulnerabilities* (CVE) pada library pihak ketiga.
  4. **Component & Integration Testing**: Pengujian interaksi antar modul internal dengan dependensi nyata terisolasi (misal: PostgreSQL/Redis berbasis ephemeral container via *Testcontainers*).
  5. **API & Consumer-Driven Contract Testing (Pact)**: Memastikan backward-compatibility kontrak komunikasi antar microservice tanpa harus menjalankan seluruh ekosistem service.
  6. **End-to-End (E2E), Performance, & DAST (Dynamic Application Security Testing)**: Pengujian alur bisnis menyeluruh pada lingkungan staging atau ephemeral preview environment yang menyerupai produksi secara identik.
</details>

---

### Soal 1.5: Konsep State Drift dan Immutability pada IaC
Apa yang dimaksud dengan *Configuration Drift* pada infrastruktur cloud, dan mengapa prinsip *Immutable Infrastructure* (mengganti instance/container seutuhnya) lebih disukai daripada *Mutable Infrastructure* (mengonfigurasi instance hidup secara in-place via SSH/Ansible) dalam mengeliminasi drift?

<details>
<summary>Jawaban & Kunci Evaluasi</summary>

- **Definisi Configuration Drift**:
  Fenomena divergensi atau perbedaan status antara konfigurasi infrastruktur yang tercatat di repositori kode sumber (*declared state* di file HCL Terraform/CloudFormation) dengan status fisik resource yang sebenarnya berjalan di cloud provider (*actual live runtime state*). Drift umumnya disebabkan oleh intervensi manual darurat lewat Web Console/CLI, script otomasi tak terlacak, atau patch otomatis sistem operasi.
- **Mutable vs. Immutable Infrastructure**:
  - *Mutable Infrastructure (In-place Updates)*: Server dimodifikasi secara langsung sepanjang masa hidupnya (menginstal update package, mengedit `/etc/hosts`, mengubah setting daemon). Seiring waktu, setiap server mengakumulasi konfigurasi unik yang tidak dapat direplikasi secara deterministik (*Snowflake Server*), menyebabkan pengujian di staging tidak lagi valid untuk produksi.
  - *Immutable Infrastructure (Replace-on-Update)*: Server virtual atau container tidak pernah diubah statusnya saat sudah berjalan. Setiap pembaruan kode, library, atau konfigurasi OS dikemas menjadi artefak gambar baru (Golden AMI via Packer atau OCI Container Image) dengan tag/digest unik, lalu dideploy untuk menggantikan instance lama seutuhnya. Jika terjadi kerusakan, sistem dapat di-rollback secara instan ke artefak image versi sebelumnya yang diketahui stabil.
</details>

---

## 2. Intermediate Questions (5 Soal)

### Soal 2.1: Analisis Metrik Rollout Progresif pada Argo Rollouts
Sebuah tim mengonfigurasi rilis Canary menggunakan Argo Rollouts dengan integrasi `AnalysisTemplate` Prometheus. Amati fragmen konfigurasi berikut:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: payment-engine
spec:
  strategy:
    canary:
      analysis:
        templates:
          - templateName: success-rate-check
        args:
          - name: service-name
            value: payment-engine-canary
      steps:
        - setWeight: 20
        - pause: { duration: 10m }
        - setWeight: 50
        - pause: { duration: 15m }
```

Jelaskan alur eksekusi controller Argo Rollouts saat rilis baru diterapkan:
1. Bagaimana traffic jaringan dibagi secara fisik di level Layer 7 (Service Mesh / Ingress)?
2. Apa yang terjadi jika query Prometheus pada `AnalysisTemplate` menghasilkan nilai metrik yang melanggar threshold toleransi kegagalan (*failureLimit*) pada menit ke-4 di fase `setWeight: 20`?
3. Mengapa metrik analisis harus merujuk pada `payment-engine-canary` dan bukan service produksi utama?

<details>
<summary>Jawaban & Kunci Evaluasi</summary>

1. **Pembagian Traffic Layer 7**:
   Argo Rollouts memanipulasi konfigurasi Ingress Controller (misal: NGINX Ingress annotations `nginx.ingress.kubernetes.io/canary-weight`) atau VirtualService Service Mesh (misal: Istio/Envoy route weights). Controller membuat dua Kubernetes Service terpisah: `payment-engine-stable` (merujuk ke pod versi lama) dan `payment-engine-canary` (merujuk ke pod versi baru dengan label selector hash unik). Proxy L7 kemudian mendistribusikan $20\%$ request HTTP ke service canary dan $80\%$ ke service stable.
2. **Reaksi Pelanggaran Threshold Analysis**:
   Jika analisis Prometheus mengembalikan nilai gagal melebihi `failureLimit` yang ditentukan:
   - Status Rollout langsung ditandai sebagai `Degraded`.
   - Argo Rollouts menghentikan eksekusi langkah selanjutnya secara otomatis (*circuit-breaking*).
   - Controller melakukan rollback seketika (*auto-abort*): traffic canary dikembalikan ke $0\%$ (seluruh traffic diarahkan kembali $100\%$ ke versi stable).
   - Pod canary dipertahankan sementara waktu (*abort scale down delay*) untuk investigasi log, lalu di-terminate secara graceful.
3. **Isolasi Metrik Canary**:
   Metrik analisis harus secara eksklusif mengisolasi pod canary (`service-name: payment-engine-canary` atau filter pod label `rollouts-pod-template-hash`). Jika evaluasi menggunakan service utama gabungan, lonjakan error $5\%$ pada versi canary hanya akan terdistribusi sebesar $1\%$ ($20\% \times 5\% = 1\%$) pada total metrik agregat, sehingga anomali kritis dapat tersamarkan oleh tingginya volume traffic sehat dari versi stable (*dilution effect*).
</details>

---

### Soal 2.2: Cryptographic Attestation & SLSA Provenance
Dalam arsitektur *Software Supply Chain Security*, jelaskan perbedaan antara **Software Vulnerability Scanning** (menggunakan Trivy/Grype) dan **Cryptographic Artifact Attestation** (menggunakan Sigstore Cosign dan framework SLSA). Mengapa lulus scanning kerentanan saja tidak cukup untuk menjamin integritas artifact yang dideploy di Kubernetes?

<details>
<summary>Jawaban & Kunci Evaluasi</summary>

- **Perbedaan Mendasar**:
  - *Vulnerability Scanning (Trivy/Grype)*: Memeriksa daftar komponen software (packages/dependencies) di dalam container image terhadap basis data kerentanan publik (CVE). Scanner hanya menjawab pertanyaan: *"Apakah artifact ini mengandung celah keamanan yang sudah diketahui publik saat ini?"*.
  - *Cryptographic Artifact Attestation (Cosign & SLSA)*: Menandatangani metadata yang menyatakan keaslian asal-usul artefak (*provenance*), bukti bahwa build dilakukan oleh CI pipeline resmi yang terpercaya (*tamper-proof builder*), serta mencantumkan riwayat commit Git, build parameter, dan SBOM (Software Bill of Materials) yang ditandatangani secara kriptografis (*verifiable claims*).
- **Mengapa Vulnerability Scan Tidak Cukup**:
  1. *Man-in-the-Middle & Tag Mutation*: OCI image tag (misal: `v1.2.0`) bersifat mutable. Penyerang yang memiliki akses ke OCI Registry dapat menimpa (*overwrite*) tag tersebut dengan image jahat setelah scanning selesai dilakukan di CI runner.
  2. *Zero-Day & Unreported Vulnerabilities*: Scanner CVE tidak dapat mendeteksi backdoor yang disisipkan secara sengaja oleh peretas atau dependensi berbahaya yang belum memiliki entri CVE resmi di database NVD.
  3. *Integritas Build Environment*: Tanpa attestation (SLSA level 3+), tidak ada jaminan bahwa image tersebut benar-benar dibangun dari kode sumber di Git repository organisasi; image tersebut bisa saja dikompilasi dari mesin laptop lokal yang terinfeksi malware dan diunggah langsung ke registry.
  4. *Enforcement via Admission Control*: Dengan attestation kriptografis, Kubernetes Admission Controller (Kyverno/OPA Gatekeeper) dapat secara deterministik menolak eksekusi pod apa pun yang tidak memiliki tanda tangan digital valid dari trust root organisasi, membatalkan deployment meskipun image tersebut lolos scanner kerentanan.
</details>

---

### Soal 2.3: Perhitungan Value Stream Mapping & Flow Efficiency
Sebuah tim rekayasa software memiliki alur rilis dengan data telemetri rata-rata berikut:
- Penulisan Kode (Active Dev): $16\text{ jam}$
- Menunggu Giliran Code Review (Queue Wait Time): $32\text{ jam}$
- Proses Code Review & Koreksi (Active Review): $4\text{ jam}$
- Menunggu Eksekusi Pipeline CI (Queue Wait Time): $2\text{ jam}$
- Automated CI Build & Test (Active Automation): $0.5\text{ jam}$
- Menunggu Jadwal Uji Manual Staging QA (Queue Wait Time): $64\text{ jam}$
- Uji Manual Regresi QA (Active Testing): $8\text{ jam}$
- Menunggu CAB (Change Advisory Board) Approval (Queue Wait Time): $40\text{ jam}$
- Eksekusi Deployment ke Produksi (Active Deploy): $0.5\text{ jam}$

Hitung:
1. **Total Lead Time** dan **Total Process Time (Touch Time)**!
2. **Process Cycle Efficiency (PCE) / Flow Efficiency** dari alur kerja ini!
3. Berdasarkan *Theory of Constraints*, intervensi teknis apa yang memberikan dampak reduksi Lead Time terbesar?

<details>
<summary>Jawaban & Kunci Evaluasi</summary>

1. **Kalkulasi Lead Time & Process Time**:
   - **Process Time ($PT$)** (Waktu sentuh aktif di mana pekerjaan nyata sedang dikerjakan):
     $$PT = 16 + 4 + 0.5 + 8 + 0.5 = 29\text{ jam}$$
   - **Wait Time ($WT$)** (Waktu tunggu/antrean di mana item diam tidak dikerjakan):
     $$WT = 32 + 2 + 64 + 40 = 138\text{ jam}$$
   - **Lead Time ($LT$)** (Total durasi dari awal pengerjaan hingga rilis di produksi):
     $$LT = PT + WT = 29 + 138 = 167\text{ jam}\ (\approx 20.8\text{ hari kerja @ 8 jam/hari})$$

2. **Flow Efficiency / Process Cycle Efficiency (PCE)**:
   $$\text{PCE} = \left( \frac{\text{Process Time}}{\text{Lead Time}} \right) \times 100\% = \left( \frac{29}{167} \right) \times 100\% \approx 17.36\%$$
   *(Artinya, ~82.64% dari waktu siklus rilis habis terbuang dalam status antrean/menunggu tanpa ada nilai tambah yang dihasilkan).*

3. **Intervensi Berbasis Theory of Constraints**:
   - Titik ketersendatan (*bottleneck*) terbesar adalah antrean manual: **Menunggu Uji Manual QA (64 jam)** dan **Menunggu Approval CAB (40 jam)**, yang secara kumulatif menyumbang 104 jam (~62.3% dari total lead time).
   - *Solusi Rekayasa*: Mengganti pengujian manual QA dengan suite automated integration/E2E test di pipeline CI untuk memangkas waktu tunggu QA menjadi mendekati 0 jam. Mengganti persetujuan manual CAB dengan automated quality gates (DORA metrics, automated policy check, and canary analysis) sehingga rilis dapat dilakukan secara kontinu (*peer-review based sign-off*), memangkas 40 jam tunggu CAB.
</details>

---

### Soal 2.4: Topologi State File Terraform Enterprise & Blast Radius
Mengapa organisasi enterprise modern dilarang keras menggunakan model *Single Monolithic State* pada Terraform, dan bagaimana Anda merancang struktur hierarki state yang memisahkan boundary lifecycle resource (misal: Jaringan/VPC, Compute/Kubernetes, dan Data/RDS)?

<details>
<summary>Jawaban & Kunci Evaluasi</summary>

- **Bahaya Single Monolithic State**:
  1. *Blast Radius Masif*: Kesalahan ketik sintaks HCL atau kegagalan API provider pada satu resource aplikasi berpotensi merusak atau menghapus resource kritis lain (seperti VPC peering atau Database master).
  2. *State Lock Contention*: Backend state (seperti S3 + DynamoDB) mengunci file state selama proses planning dan execution. Jika seluruh tim bergantung pada satu state file, hanya satu engineer atau satu pipeline yang bisa berjalan dalam satu waktu, memicu antrean deployment panjang.
  3. *Penalti Performa Refresh*: Terraform harus mengeksekusi API calls untuk me-refresh status ribuan resource cloud setiap kali `terraform plan` dijalankan, memperlambat siklus eksekusi dari hitungan detik menjadi puluhan menit.
  4. *Pelanggaran Least Privilege*: Service account CI/CD untuk deployment microservice sederhana terpaksa diberi izin IAM setingkat administrator jaringan dan database.
- **Rancangan Struktur Hierarki State Terisolasi**:
  Pemisahan dilakukan berdasarkan **Laju Perubahan (Velocity of Change)** dan **Kepemilikan Tim (Team Ownership)**:
  - **Tier 0: Core Foundation / Network State** (Velocity Rendah, dikelola Tim Cloud/NetOps):
    VPC, Subnets, Transit Gateway, Route Tables, NAT Gateways, Direct Connect.
  - **Tier 1: Compute Platform State** (Velocity Sedang, dikelola Tim Platform/DevOps):
    EKS/GKE Cluster, Node Pools, Ingress Controller Base, IAM Roles for Service Accounts (IRSA).
  - **Tier 2: Shared Data State** (Velocity Rendah-Sedang, dikelola Tim Data/DBA):
    Amazon RDS Aurora Clusters, Redis Replication Groups, S3 Buckets persisten, KMS Keys.
  - **Tier 3: Application Workload State** (Velocity Tinggi, dikelola masing-masing Tim Produk/Microservice):
    Kubernetes manifests/helm via GitOps, SQS Queues spesifik, DynamoDB tables aplikasi.
  - *Mekanisme Komunikasi Antar-State*: Menggunakan data sources seperti `terraform_remote_state` (read-only) atau SSM Parameter Store / AWS Secrets Manager untuk mengekspos output parameter (seperti Subnet IDs atau DB Endpoints) tanpa membagikan izin mutasi state file.
</details>

---

### Soal 2.5: Policy-as-Code dengan OPA Gatekeeper
Perhatikan dokumen Constraint OPA Gatekeeper berikut:

```yaml
apiVersion: constraints.gatekeeper.sh/v1beta1
kind: K8sRequiredLabels
metadata:
  name: require-tier-and-owner
spec:
  match:
    kinds:
      - apiGroups: ["apps"]
        kinds: ["Deployment", "StatefulSet"]
    namespaces: ["production"]
  parameters:
    labels: ["tier", "owner", "cost-center"]
```

Jelaskan:
1. Pada siklus hidup API request Kubernetes manakah (*Admission Webhook phase*) Gatekeeper mengevaluasi manifes ini?
2. Apa yang terjadi jika developer mencoba mengaplikasikan Deployment baru ke namespace `production` yang hanya memiliki label `tier: backend` dan `owner: alpha-team`?
3. Mengapa penegakan kebijakan di level Kubernetes Admission Controller lebih tangguh dibandingkan hanya memasang scanner linter YAML di pipeline CI developer?

<details>
<summary>Jawaban & Kunci Evaluasi</summary>

1. **Fase Siklus Admission Webhook**:
   Gatekeeper bertindak sebagai **Validating Admission Webhook**. Fase ini terjadi setelah request HTTP ke kube-apiserver lolos proses Otentikasi (Authentication), lolos Otorisasi RBAC (Authorization), dan melewati *Mutating Webhooks*, namun **sebelum** objek resource disimpan secara persisten ke dalam basis data etcd cluster.
2. **Hasil Evaluasi Manifes**:
   API Server Kubernetes akan **menolak request secara sinkron** dan mengembalikan kode status HTTP `403 Forbidden` kepada klien (`kubectl` atau ArgoCD). Pesan error yang dihasilkan secara eksplisit mencantumkan pelanggaran: missing required label `cost-center`. Objek Deployment tersebut sama sekali tidak akan dibuat di cluster.
3. **Keunggulan Enforce di Level Admission Controller**:
   - *Bypass Immunity*: Pipeline CI dapat dilewati (misal: developer dengan akses langsung mengeksekusi `kubectl apply` darurat dari terminal lokal, atau menggunakan skrip helm ad-hoc). Validating Webhook bertindak sebagai gerbang terpusat di depan etcd; tidak ada manifes yang bisa masuk ke cluster tanpa melewati verifikasi webhook, terlepas dari dari mana manifes tersebut berasal.
   - *Runtime Consistency*: Webhook menjamin bahwa *cluster runtime state* selalu mematuhi tata kelola keamanan dan kepatuhan finansial organisasi (*governance & audit compliance*).
</details>

---

## 3. Skenario Kasus Produksi (3 Kasus Nyata)

### Skenario 3.1: "The Poisoned Container & Compromised Build Runner"
**Konteks Masalah**:  
Sebuah platform fintech e-wallet menggunakan sistem CI/CD push-based berbasis shared self-hosted runner virtual machine. Pada hari Jumat malam, sebuah package open-source library logging pihak ketiga yang digunakan oleh salah satu microservice terkena serangan *typosquatting* di public registry. 

Dependency berbahaya tersebut menginjeksi malware ke dalam lingkungan build runner saat fase `npm install`. Malware tersebut memodifikasi binary OCI image sebelum di-push ke Amazon ECR, menyisipkan backdoor reverse shell, lalu memanipulasi log scanner Trivy agar mengembalikan status "No Vulnerabilities Found". Image beracun tersebut berhasil lolos masuk ke cluster EKS produksi dan mulai membocorkan kredensial database.

```
[Developer Git Push]
         │
         ▼
[Shared CI Runner] ──> (npm install typosquatted package)
         │                       │
         │                       ▼ (Injects Backdoor Binary)
         ├────────────────> [Build Docker Image: v2.4.1]
         │                       │
         │                       ▼
         ├────────────────> [Trivy Scan: Faked Clean Log]
         │                       │
         │                       ▼
         └────────────────> [ECR Push: v2.4.1] ──> [EKS Deploy: ACTIVE BREACH]
```

**Pertanyaan Analisis**:
1. Identifikasi 3 kelemahan struktural pada arsitektur CI/CD dan supply chain di atas yang memungkinkan insiden ini terjadi!
2. Rancang arsitektur pipeline zero-trust yang memanfaatkan **Ephemeral Isolated Runners**, **SLSA Framework**, **Sigstore Cosign (Keyless Signing)**, dan **Kubernetes Admission Control** untuk menjamin artefak yang tidak terotentikasi ditolak mentah-mentah oleh cluster!

<details>
<summary>Solusi & Panduan Investigasi</summary>

1. **Kelemahan Struktural Arsitektur**:
   - *Shared & Persistent Build Runner*: Menggunakan virtual machine yang digunakan bersama antar-job memungkinkan kontaminasi silang (*cross-job state contamination*) dan eksploitasi persistensi malware di host runner.
   - *Absence of Cryptographic Provenance*: Tidak ada mekanisme verifikasi yang mengaitkan commit Git spesifik dengan binary container yang dihasilkan; build output tidak ditandatangani secara kriptografis oleh identitas terverifikasi.
   - *Trusting Client-Side Scanners*: Keputusan deployment hanya bergantung pada exit code script scanner di sisi runner yang dapat dimanipulasi oleh malware dengan hak akses root lokal.
   - *Unrestricted Container Registry Access*: Kubernetes mengizinkan deployment image apa pun yang ada di ECR tanpa memeriksa asal-usul tanda tangan digital.

2. **Rancangan Arsitektur Supply Chain Zero-Trust**:
   - **Ephemeral Isolated Runners**: Setiap build dijalankan di dalam container/VM sekali pakai (misal: GitHub Actions ephemeral runner via actions-runner-controller di Kubernetes atau AWS CodeBuild) yang langsung dihancurkan setelah job selesai untuk mengeliminasi persistensi malware.
   - **Pinned Dependencies & Private Proxy**: Seluruh dependensi pihak ketiga harus melewati private artifact repository (Artifactory/Nexus) dengan lockfile ber-hash SHA512 dan scanning otomatis pra-unduh.
   - **Cryptographic Attestation via Sigstore Cosign (Keyless)**:
     - CI runner menggunakan OpenID Connect (OIDC) token untuk membuktikan identitas alur kerja GitHub Actions ke Fulcio (Certificate Authority).
     - Fulcio menerbitkan short-lived x509 certificate yang terikat dengan repository, commit SHA, dan trigger event.
     - Cosign menandatangani OCI image digest (`sha256:...`) dan mencatat metadata tanda tangan serta SBOM ke transparansi log Rekor.
   - **Policy Enforcement di Kubernetes (Kyverno / OPA Gatekeeper)**:
     Pasang policy admission controller di EKS:
     ```yaml
     apiVersion: kyverno.io/v1
     kind: ClusterPolicy
     metadata:
       name: verify-image-signature
     spec:
       validationFailureAction: Enforce
       rules:
         - name: verify-sigstore-cosign
           match:
             resources:
               kinds: ["Pod"]
           verifyImages:
             - imageReferences: ["*.dkr.ecr.*.amazonaws.com/*"]
               attestors:
                 - entries:
                     - keyless:
                         subject: "https://github.com/my-org/payment-service/.github/workflows/*"
                         issuer: "https://token.actions.githubusercontent.com"
     ```
     Jika container image dimodifikasi oleh peretas atau tidak ditandatangani oleh alur kerja OIDC resmi, kube-apiserver akan langsung menolak pembuatan Pod, menggagalkan serangan sebelum artefak sempat dieksekusi.
</details>

---

### Skenario 3.2: "The Cascading Canary Collapse during High Concurrency Flash Sale"
**Konteks Masalah**:  
Sebuah platform e-commerce meluncurkan versi baru dari microservice `checkout-order` menggunakan Argo Rollouts dengan strategi Canary (step: 10% -> 25% -> 50% -> 100%) tepat 30 menit sebelum event Flash Sale dimulai. 

Ketika traffic melonjak tajam menyentuh 45.000 RPS, rilis sedang berada di step 25%. Developer versi baru secara tidak sengaja memperkenalkan implementasi connection leak pada koneksi basis data (koneksi tidak di-return ke pool saat HTTP context timeout). Dalam 3 menit, pod canary kehabisan connection pool database, menyebabkan HTTP error 500 meningkat drastis dan latency p99 menembus 8 detik pada 25% pengguna.

Namun, sistem monitoring **gagal melakukan auto-abort rollback**. Rollout justru terus berjalan maju ke step 50%, memperluas dampak bencana ke separuh pelanggan sistem.

```
Traffic: 45k RPS ──> [L7 Ingress Controller]
                          ├── 75% Traffic ──> [Pod Stable (Healthy)]
                          └── 25% Traffic ──> [Pod Canary (DB Conn Leak!)] ──> [DB Pool Exhausted!]
                                                     │
                                                     ▼
                                     [Prometheus Evaluation Delay]
                                                     │
                                                     ▼ (Avg Cluster Metric Used!)
                                     [Failure Condition Missed!]
                                                     │
                                                     ▼
                                     [Rollout Progresses to 50% !!]
```

**Pertanyaan Analisis**:
1. Mengapa Prometheus AnalysisTemplate pada Argo Rollouts gagal mendeteksi kegagalan tersebut dan justru membiarkan rollout berlanjut ke step berikutnya?
2. Bagaimana formulasi PromQL yang benar untuk mengisolasi metrik error rate spesifik pod canary tanpa terdistorsi oleh pod stable?
3. Konfigurasikan parameter failure tolerance dan circuit breaker pada Argo Rollouts agar pod canary yang bermasalah langsung diisolasi dalam waktu kurang dari 30 detik!

<details>
<summary>Solusi & Panduan Investigasi</summary>

1. **Penyebab Kegagalan Deteksi Otomatis**:
   - *Kesalahan Formula Metrik (Dilution Bug)*: Query Prometheus pada AnalysisTemplate menggunakan metrik agregat global service (`sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))`). Karena 75% traffic dihandle oleh versi stable yang sehat, total kegagalan agregat hanya bernilai ~2.5%, berada di bawah ambang batas alert global (misal: threshold disetel > 3%).
   - *Interval Scraping & Evaluation Window Terlalu Lebar*: Penggunaan sliding window `[5m]` dengan interval evaluasi 2 menit menciptakan lag metrik. Data kegagalan belum terakumulasi cukup tinggi saat controller melakukan cek berkala.
   - *Missing Abort Metric Rules*: Tidak adanya metrik saturasi internal (seperti `jvm_threads_waiting` atau `go_sql_open_connections`) di samping metrik HTTP level luar.

2. **Formulasi PromQL Presisi Terisolasi Canary**:
   Gunakan label injeksi otomatis Argo Rollouts `rollouts_pod_template_hash`:
   ```promql
   # PromQL untuk Error Rate khusus Pod Canary (Threshold harus < 0.5% / 0.005)
   sum(rate(http_requests_total{
     service="checkout-order",
     status=~"5..",
     rollouts_pod_template_hash="{{args.canary-hash}}"
   }[1m]))
   /
   (
     sum(rate(http_requests_total{
       service="checkout-order",
       rollouts_pod_template_hash="{{args.canary-hash}}"
     }[1m])) > 10 # Guard: minimal ada 10 req/s agar tidak false positive saat traffic sepi
   )
   ```

3. **Konfigurasi Resilience & Immediate Circuit-Breaker**:
   Perbarui manifes `AnalysisTemplate` dengan interval cepat dan batas toleransi kegagalan ketat:
   ```yaml
   apiVersion: argoproj.io/v1alpha1
   kind: AnalysisTemplate
   metadata:
     name: canary-high-concurrency-gate
   spec:
     args:
       - name: canary-hash
     metrics:
       - name: canary-http-error-rate
         interval: 15s           # Evaluasi setiap 15 detik
         count: 10               # Total cek selama fase pause
         successCondition: result[0] < 0.01 # Error rate wajib < 1%
         failureLimit: 2         # Cukup 2 kali berturut-turut gagal -> langsung Abort (< 30 detik)
         provider:
           prometheus:
             address: http://prometheus-k8s.monitoring:9090
             query: |
               sum(rate(http_requests_total{status=~"5..", rollouts_pod_template_hash="{{args.canary-hash}}"}[30s]))
               /
               sum(rate(http_requests_total{rollouts_pod_template_hash="{{args.canary-hash}}"}[30s]))
   ```
   Pada definisi Rollout, tambahkan direktif `abortScaleDownDelaySeconds: 300` agar pod bermasalah tidak langsung dimusnahkan secara instan melainkan diisolasi dari traffic untuk pengambilan heap dump / thread dump oleh tim engineering.
</details>

---

### Skenario 3.3: "The Terraform State Lock Deadlock & Console Mutation Disaster"
**Konteks Masalah**:  
Pukul 02:00 dini hari, terjadi insiden di mana microservice transaksi pembayaran mengalami kegagalan akibat limit kapasitas koneksi database AWS Aurora PostgreSQL. Untuk menyelesaikan insiden secepat mungkin, seorang Engineer On-Call masuk ke AWS Web Management Console dan melakukan perubahan manual:
1. Mengubah instance class RDS Aurora dari `db.r6g.xlarge` ke `db.r6g.4xlarge`.
2. Menambahkan aturan baru pada Security Group database untuk mengizinkan traffic sementara dari subnet diagnostik.

Insiden selesai dan layanan pulih. Namun, engineer tersebut tidak memperbarui repositori Git Terraform.

Keesokan paginya pada pukul 09:00, alur kerja automated GitOps pipeline Terraform berjalan via GitHub Actions karena ada PR refaktorisasi routing yang di-merge. Pipeline CI gagal di tengah jalan dengan error:
`Error: Error acquiring the state lock: ConditionalCheckFailedException (Lock held by engineer-laptop-session-4819)`

Seorang engineer lain secara terburu-buru mengeksekusi perintah CLI:
`terraform force-unlock 4819`
Lalu memicu re-run pipeline CI. Pipeline mendeteksi perbedaan status (*drift*) dan mengeksekusi `terraform apply` secara otomatis. Hasilnya: instance class database di-downgrade kembali ke `db.r6g.xlarge`, aturan security group diagnostik terhapus, dan database mengalami reboot paksa di jam kerja sibuk, memicu insiden *Sev-1 outage* kedua.

**Pertanyaan Analisis**:
1. Analisis kegagalan arsitektur operasional (*anti-patterns*) dari insiden di atas dari perspektif GitOps, governance akses, dan concurrency control!
2. Bagaimana prosedur teknis yang aman (*safe procedure*) dalam menangani kondisi *State Lock Deadlock* di Terraform tanpa merusak integritas state?
3. Rancang arsitektur pencegahan (*guardrails*) menyeluruh berbasis AWS IAM Service Control Policies (SCP), Terraform Drift Detection terotomasi, dan *Emergency Break-Glass Procedure* agar mutasi console terlarang namun kebutuhan tanggap darurat tetap terakomodasi!

<details>
<summary>Solusi & Panduan Investigasi</summary>

1. **Analisis Kegagalan Arsitektur Operasional**:
   - *Manual Console Mutation (Out-of-Band Change)*: Melanggar prinsip *Single Source of Truth*. Modifikasi langsung di konsol cloud merusak determinisme deklaratif IaC, menjadikan state Terraform usang (*stale*).
   - *Reckless State Unlocking*: Mengeksekusi `terraform force-unlock` tanpa memvalidasi apakah ada proses `apply` lain yang sedang berjalan secara bersamaan (*concurrent mutation*) berisiko merusak struktur biner/JSON state file secara permanen.
   - *Unreviewed Automated Apply on Drift*: Pipeline CI mengeksekusi `terraform apply` otomatis terhadap plan yang mengandung destructive actions (downgrade database instance) tanpa adanya proteksi *Lifecycle Guard* atau manual approval gate untuk perubahan destruktif.

2. **Prosedur Aman Menangani State Lock Deadlock**:
   - *Langkah 1*: Periksa DynamoDB Lock Table. Dapatkan metadata kunci: `LockID`, `Info` (berisi hostname, waktu lock diakuisisi, dan siapa pemegang lock).
   - *Langkah 2*: Verifikasi proses fisik. Hubungi pemilik session (`engineer-laptop`) dan pastikan proses Terraform di mesin tersebut benar-benar sudah mati/terminated dan tidak sedang melakukan write operation ke cloud provider.
   - *Langkah 3*: Jalankan `terraform plan` terlebih dahulu secara read-only setelah unlock dieksekusi, **jangan langsung apply**.
   - *Langkah 4*: Tinjau output plan secara seksama. Jika terdeteksi *unexpected modifications/destructions*, batalkan apply dan sinkronkan kode HCL dengan kondisi live cloud (*reconciliation*).

3. **Arsitektur Guardrails & Pencegahan Komprehensif**:
   - **Enforce No-Console-Mutation via AWS IAM & SCP**:
     Terapkan Service Control Policy (SCP) pada level AWS Organization yang mencabut hak mutasi write/update/delete untuk semua peran IAM pengguna reguler pada resource produksi:
     ```json
     {
       "Version": "2012-10-17",
       "Statement": [
         {
           "Sid": "DenyConsoleMutationOnProd",
           "Effect": "Deny",
           "Action": ["rds:Modify*", "rds:Delete*", "ec2:AuthorizeSecurityGroup*"],
           "Resource": "*",
           "Condition": {
             "StringNotLike": {
               "aws:PrincipalArn": ["arn:aws:iam::*:role/terraform-ci-cd-pipeline-role"]
             }
           }
         }
       ]
     }
     ```
   - **Emergency Break-Glass Role**: Buat IAM Role darurat dengan alerting instan ke Slack Security & PagerDuty saat diaktifkan, dengan pembatasan durasi sesi (maksimal 1-2 jam via AWS STS).
   - **Automated Scheduled Drift Detection**:
     Buat pipeline terjadwal (cron job harian/setiap jam) yang menjalankan:
     `terraform plan -detailed-exitcode -refresh-only`
     Jika exit code adalah `2` (artinya ada drift terdeteksi antara cloud fisik dan Git), pipeline langsung memicu alert Sev-2 ke tim platform untuk merekonsiliasi kode HCL sebelum pipeline deployment reguler berjalan.
   - **Terraform Lifecycle Safeguard**:
     Tambahkan blok proteksi pada resource kritis di HCL:
     ```hcl
     lifecycle {
       prevent_destroy = true
       ignore_changes  = [] # Hindari wildcard; spesifikasikan jika ada atribut dinamis
     }
     ```
</details>

---

## 4. Practical Chapter Challenge: Enterprise GitOps & Supply Chain Architecture Engine

### Deskripsi Skenario Proyek
Anda ditunjuk sebagai Principal Platform Architect untuk merancang fondasi arsitektur GitOps dan Supply Chain Security pada klaster Kubernetes produksi generasi terbaru di sebuah lembaga perbankan digital.

Sistem dituntut memenuhi standar kepatuhan tinggi:
1. Seluruh deployment aplikasi harus menggunakan rilis progresif berbasis analisis telemetri otomatis.
2. Klaster wajib menolak container image apa pun yang tidak menggunakan OCI digest permanen (`sha256`), tidak memiliki label tata kelola wajib, atau berjalan dengan hak akses root.
3. Struktur modularisasi Infrastructure-as-Code (Terraform) harus memiliki isolasi *state file* multi-tier yang ketat guna membatasi blast radius.

### Persyaratan Tugas Teknis (Deliverables)

#### Tugas 1: Spesifikasi Deklaratif Argo Rollout & Automated Analysis
Susun berkas manifes YAML Kubernetes lengkap yang mendefinisikan:
1. `AnalysisTemplate` bernama `prod-transaksi-prometheus-gate`:
   - Memantau HTTP Success Rate ($\ge 99.5\%$) pada window 1 menit.
   - Memantau HTTP Latency p99 ($\le 250\text{ms}$) pada window 1 menit.
   - Evaluasi setiap 30 detik sebanyak 5 kali iterasi berturut-turut. Batas toleransi kegagalan: maksimal 1 kali gagal (`failureLimit: 1`).
2. `Rollout` bernama `service-transaksi`:
   - Menggunakan strategi Canary dengan 3 tahap step: $10\%$, $30\%$, dan $60\%$.
   - Integrasikan `AnalysisTemplate` di atas dengan passing argumen dinamis hash canary pod.

#### Tugas 2: Policy-as-Code dengan OPA Gatekeeper (ConstraintTemplate & Constraint)
Tuliskan satu unit implementasi OPA Gatekeeper lengkap yang terdiri dari:
1. `ConstraintTemplate` bernama `K8sContainerSecurityStandards`:
   - Ditulis menggunakan bahasa **Rego** (`v1` atau standard Gatekeeper syntax).
   - Menolak Pod jika ada container yang:
     - Menggunakan image tag mutable (misal: `:latest`, `:dev`, atau image tanpa tanda `@sha256:`).
     - Mengonfigurasi `securityContext.runAsNonRoot: false` atau tidak mendefinisikannya sama sekali.
2. `Constraint` yang mengikat template tersebut ke seluruh namespace produksi (`namespace: ["banking-production"]`).

#### Tugas 3: Desain Arsitektur Direktori IaC Enterprise Multi-Environment
Gambarkan struktur pohon direktori (*directory tree layout*) implementasi Terraform/Terragrunt yang memisahkan:
- 3 Lingkungan: `development`, `staging`, `production`.
- 3 Layer State terisolasi per lingkungan: `01-networking-vpc`, `02-platform-eks`, `03-data-aurora`.
- Sertakan penjelasan bagaimana parameter output dari layer networking diteruskan secara aman ke layer compute EKS tanpa memicu coupling state.

---

### Solusi & Acuan Implementasi Chapter Challenge

#### 1. Implementasi Argo Rollout & AnalysisTemplate

```yaml
apiVersion: argoproj.io/v1alpha1
kind: AnalysisTemplate
metadata:
  name: prod-transaksi-prometheus-gate
  namespace: banking-production
spec:
  args:
    - name: canary-hash
    - name: service-name
  metrics:
    # Metrik 1: Success Rate Minimum 99.5%
    - name: success-rate
      interval: 30s
      count: 5
      failureLimit: 1
      successCondition: result[0] >= 0.995
      provider:
        prometheus:
          address: http://prometheus-server.monitoring.svc.cluster.local:9090
          query: |
            sum(rate(http_requests_total{
              service="{{args.service-name}}",
              status=~"2..|3..",
              rollouts_pod_template_hash="{{args.canary-hash}}"
            }[1m]))
            /
            sum(rate(http_requests_total{
              service="{{args.service-name}}",
              rollouts_pod_template_hash="{{args.canary-hash}}"
            }[1m]))
    # Metrik 2: Latency P99 Maksimal 250ms (0.25 detik)
    - name: p99-latency
      interval: 30s
      count: 5
      failureLimit: 1
      successCondition: result[0] <= 0.250
      provider:
        prometheus:
          address: http://prometheus-server.monitoring.svc.cluster.local:9090
          query: |
            histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{
              service="{{args.service-name}}",
              rollouts_pod_template_hash="{{args.canary-hash}}"
            }[1m])) by (le))
---
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: service-transaksi
  namespace: banking-production
spec:
  replicas: 10
  strategy:
    canary:
      canaryService: service-transaksi-canary
      stableService: service-transaksi-stable
      trafficRouting:
        nginx:
          stableIngress: service-transaksi-ingress
      analysis:
        templates:
          - templateName: prod-transaksi-prometheus-gate
        args:
          - name: canary-hash
            valueFrom:
              podTemplateHashValue: Latest
          - name: service-name
            value: service-transaksi
      steps:
        - setWeight: 10
        - pause: { duration: 3m }
        - setWeight: 30
        - pause: { duration: 5m }
        - setWeight: 60
        - pause: { duration: 5m }
  selector:
    matchLabels:
      app: service-transaksi
  template:
    metadata:
      labels:
        app: service-transaksi
    spec:
      containers:
        - name: core
          image: 123456789012.dkr.ecr.ap-southeast-1.amazonaws.com/transaksi@sha256:7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069
          ports:
            - containerPort: 8080
          resources:
            limits:
              cpu: "1000m"
              memory: "1Gi"
            requests:
              cpu: "500m"
              memory: "512Mi"
          securityContext:
            allowPrivilegeEscalation: false
            runAsNonRoot: true
            runAsUser: 10001
            readOnlyRootFilesystem: true
```

---

#### 2. Implementasi OPA Gatekeeper (ConstraintTemplate & Constraint)

```yaml
apiVersion: templates.gatekeeper.sh/v1
kind: ConstraintTemplate
metadata:
  name: k8scontainersecuritystandards
spec:
  crd:
    spec:
      names:
        kind: K8sContainerSecurityStandards
  targets:
    - target: admission.k8s.gatekeeper.sh
      rego: |
        package k8scontainersecuritystandards

        # Rule 1: Enforce Immutable OCI Image Digest (@sha256:...)
        violation[{"msg": msg}] {
          container := input.review.object.spec.containers[_]
          not contains(container.image, "@sha256:")
          msg := sprintf("Container '%v' ditolak: Image '%v' wajib menggunakan immutable SHA256 digest (format: image@sha256:<hash>). Tag mutable dilarang di produksi!", [container.name, container.image])
        }

        # Rule 2: Enforce runAsNonRoot: true
        violation[{"msg": msg}] {
          container := input.review.object.spec.containers[_]
          not is_non_root(container, input.review.object)
          msg := sprintf("Container '%v' ditolak: securityContext.runAsNonRoot wajib disetel true!", [container.name])
        }

        # Helper untuk validasi runAsNonRoot di level container atau pod
        is_non_root(container, pod) {
          container.securityContext.runAsNonRoot == true
        }
        is_non_root(container, pod) {
          not container.securityContext.runAsNonRoot == false
          pod.spec.securityContext.runAsNonRoot == true
        }
---
apiVersion: constraints.gatekeeper.sh/v1beta1
kind: K8sContainerSecurityStandards
metadata:
  name: enforce-production-security-standards
spec:
  match:
    kinds:
      - apiGroups: [""]
        kinds: ["Pod"]
    namespaces:
      - "banking-production"
```

---

#### 3. Desain Struktur Direktori Enterprise IaC Multi-Tier

```text
infrastructure-live/
├── terragrunt.hcl                      # Konfigurasi global remote state (S3 + DynamoDB locking)
├── environments/
│   ├── development/
│   │   ├── env.hcl                     # Variabel spesifik dev
│   │   ├── 01-networking-vpc/
│   │   │   └── terragrunt.hcl          # State: dev-vpc.tfstate
│   │   ├── 02-platform-eks/
│   │   │   └── terragrunt.hcl          # State: dev-eks.tfstate
│   │   └── 03-data-aurora/
│   │       └── terragrunt.hcl          # State: dev-aurora.tfstate
│   ├── staging/
│   │   └── ... (struktur identik)
│   └── production/
│       ├── env.hcl                     # Variabel spesifik prod (multi-AZ, retention ketat)
│       ├── 01-networking-vpc/
│       │   └── terragrunt.hcl          # Mengelola CIDR, Subnets, NAT Gateway, Transit Gateway
│       ├── 02-platform-eks/
│       │   └── terragrunt.hcl          # Mengonsumsi vpc_id & subnet_ids via Terragrunt Dependency
│       └── 03-data-aurora/
│           └── terragrunt.hcl          # Mengonsumsi db_subnet_group & eks_security_group_id
```

**Mekanisme Transmisi Parameter Antar-State yang Aman**:
Pada file `environments/production/02-platform-eks/terragrunt.hcl`, gunakan blok deklaratif `dependency`:

```hcl
dependency "vpc" {
  config_path = "../01-networking-vpc"
  mock_outputs = {
    vpc_id          = "vpc-fake-id-for-validation"
    private_subnets = ["subnet-fake-1", "subnet-fake-2"]
  }
}

inputs = {
  vpc_id     = dependency.vpc.outputs.vpc_id
  subnet_ids = dependency.vpc.outputs.private_subnets
}
```

*Keuntungan Arsitektural*:
1. State file EKS sepenuhnya terpisah dari VPC; mutasi pada cluster EKS tidak pernah mengunci atau membahayakan file state jaringan.
2. Terragrunt secara otomatis memvalidasi Directed Acyclic Graph (DAG) antarlapisan saat eksekusi `terragrunt run-all plan/apply`.
3. Output yang dikonsumsi bersifat *read-only*, mencegah terjadinya modifikasi state silang yang tidak disengaja.

---

## 5. Knowledge Check & Checklist

### Saya Harus Memahami:
- [ ] Perbedaan esensial paradigma Push-based CI/CD vs. Pull-based GitOps (keamanan kredensial, surface network, rekonsiliasi berkelanjutan).
- [ ] 4 Metrik Kuantitatif DORA (Deployment Frequency, Lead Time for Changes, Change Failure Rate, Time to Restore Service) dan interaksi trade-off di antaranya.
- [ ] Pilar CAMS/CALMS dan bahaya sistemik dari *Root Cause Fallacy* / pencarian kambing hitam personal.
- [ ] Rantai piramida pengujian dan penegakan prinsip *Shift-Left Testing* (Linter, Unit, Contract, E2E).
- [ ] Konsep *Configuration Drift* serta mitigasinya menggunakan *Immutable Infrastructure* dan rekonsiliasi deklaratif.
- [ ] Arsitektur rilis progresif (Canary / Blue-Green) menggunakan Argo Rollouts yang digerakkan oleh telemetri Prometheus L7.
- [ ] Standar keamanan rantai pasok perangkat lunak (Software Supply Chain Security): OCI digest immutability, SBOM, attestation SLSA, dan verifikasi keyless via Sigstore Cosign.
- [ ] Prinsip isolasi *State File* Terraform/Terragrunt multi-tier untuk mereduksi *blast radius* dan kontensi *state lock*.
- [ ] Mekanisme kerja Kubernetes Validating Admission Controller dan penegakan *Policy-as-Code* menggunakan OPA Gatekeeper.

### Saya Tidak Perlu Menghafal:
- [ ] Seluruh baris sintaks parameter konfigurasi NGINX Ingress annotations atau Istio EnvoyFilter flags (cukup pahami konsep Layer 7 traffic routing).
- [ ] Algoritma internal parser AST pada engine Rego OPA (cukup kuasai struktur evaluasi rules `violation`).
- [ ] Rincian format biner representasi x509 ASN.1 certificate pada Sigstore (cukup pahami alur verifikasi OIDC claims dan transparansi log Rekor).

### Saya Harus Bisa Melakukan:
- [ ] Menghitung Process Cycle Efficiency (Flow Efficiency) dari diagram Value Stream Mapping organisasi.
- [ ] Menulis query PromQL presisi yang mengisolasi metrik performa pod canary (`rollouts_pod_template_hash`) tanpa tercampur pod stable.
- [ ] Menyusun spesifikasi Kubernetes deklaratif untuk Canary Rollout terintegrasi dengan ambang batas auto-rollback (*circuit breaking*).
- [ ] Mengonfigurasi Constraint dan ConstraintTemplate OPA Gatekeeper untuk memblokir container yang tidak aman sebelum persisten di etcd.
- [ ] Mendesain struktur hierarki Terraform/Terragrunt enterprise yang aman dari deadlock state lock dan terisolasi per siklus hidup resource.
- [ ] Melakukan investigasi insiden deployment menggunakan prinsip *Blameless Post-Mortem* yang berfokus pada kelemahan sistemik arsitektur.

---
*Ketik **LANJUT** untuk berpindah ke BAB 02: Arsitektur Jaringan, Protokol Internet, & Web Servers.*
