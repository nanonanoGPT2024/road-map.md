# Evaluasi Bab 10: Continuous Delivery & Infrastructure as Code (IaC)

## 1. Basic Questions (5 Soal)

### Soal 1
Apa perbedaan mendasar antara representasi L1 Constructs (`Cfn*`) dan L2 Constructs pada AWS Cloud Development Kit (CDK v2)?
- A. L1 Constructs ditulis dalam YAML sedangkan L2 Constructs ditulis dalam JSON.
- B. L1 Constructs merupakan pemetaan langsung 1:1 terhadap resource AWS CloudFormation murni tanpa nilai default, sedangkan L2 Constructs menyertakan *sensible defaults*, best-practice security built-in, dan metode helper abstraction.
- C. L1 Constructs hanya dapat dieksekusi di AWS Lambda, sedangkan L2 Constructs berjalan di Amazon EC2.
- D. L1 Constructs digunakan khusus untuk resource jaringan, sedangkan L2 Constructs khusus untuk resource database.

### Soal 2
Pada AWS CloudFormation, fitur apa yang memungkinkan Anda memeriksa perbedaan dampak (*impact preview*) terhadap resource infrastruktur yang sedang berjalan sebelum perubahan dieksekusi secara permanen?
- A. Stack Drift Detection
- B. Stack Policy Reviewer
- C. CloudFormation Change Sets
- D. CloudFormation Rollback Trigger

### Soal 3
Dalam metodologi GitOps murni menggunakan ArgoCD di Amazon EKS, di manakah posisi *Single Source of Truth* untuk konfigurasi status aplikasi dan infrastruktur runtime cluster?
- A. Di dalam database etcd cluster Amazon EKS.
- B. Di dalam repositori Git yang menyimpan manifest deklaratif (YAML/Kustomize/Helm).
- C. Di dalam environment variables sistem CI runner.
- D. Di dalam AWS Systems Manager Parameter Store.

### Soal 4
Tipe deployment CodeDeploy manakah yang mengalihkan 10% trafik ke versi aplikasi baru, menunggu selama durasi waktu tertentu sambil memantau CloudWatch Alarm sebelum mengalihkan sisa 90% trafik sekaligus?
- A. Linear10PercentEvery1Minute
- B. AllAtOnce
- C. Canary10Percent5Minutes
- D. BlueGreenImmediateSwitch

### Soal 5
Apa fungsi utama dari Route 53 Application Recovery Controller (ARC) dalam arsitektur Disaster Recovery multi-region?
- A. Melakukan sinkronisasi data biner S3 antar region secara real-time.
- B. Menyediakan routing control switches yang highly-reliable dan terisolasi untuk mengalihkan trafik aplikasi antar region secara deterministik selama insiden regional.
- C. Mengompilasi kode program TypeScript menjadi CloudFormation template.
- D. Menggantikan fungsi Docker daemon dalam membangun kontainer di AWS CodeBuild.

---

### Kunci Jawaban & Penjelasan Basic Questions

1. **Jawaban: B**  
   *Penjelasan:* L1 Constructs (Cfn Resources) dihasilkan secara otomatis langsung dari spesifikasi CloudFormation Resource dan tidak membawa logika tambahan. L2 Constructs dikurasi secara manual oleh tim AWS untuk menyertakan praktik terbaik arsitektur (misal: S3 bucket default private, enkripsi otomatis), permission helper methods (`grantRead`, `grantWrite`), dan mereduksi boilerplate code.

2. **Jawaban: C**  
   *Penjelasan:* CloudFormation Change Sets memungkinkan operator membuat pratinjau perubahan (*preview*) untuk melihat apakah modifikasi template akan memicu penambahan (*Add*), modifikasi in-place (*Modify*), atau penggantian resource destruktif (*Replacement*), sebelum perubahan tersebut benar-benar diaplikasikan ke live environment.

3. **Jawaban: B**  
   *Penjelasan:* Prinsip fundamental GitOps menyatakan bahwa repositori Git adalah *single source of truth*. Operator GitOps seperti ArgoCD bertugas menarik (*pull*) deklarasi state dari Git dan memastikan status runtime di Kubernetes etcd selalu sinkron dengan apa yang tertulis di Git.

4. **Jawaban: C**  
   *Penjelasan:* Strategi Canary (seperti `Canary10Percent5Minutes` atau `Canary10Percent15Minutes`) membatasi alokasi pertama ke persentase kecil (10%), menunggu jeda interval waktu observasi, lalu menggeser sisa trafik jika tidak ada alarm kegagalan yang menyala. Sebaliknya, Linear mengalihkan trafik dalam persentase setara secara berkala.

5. **Jawaban: B**  
   *Penjelasan:* Route 53 Application Recovery Controller (ARC) menyediakan kontrol failover tingkat lanjut dengan bidang kontrol (*control plane*) 5-region redundant yang tetap dapat beroperasi bahkan ketika region utama tempat aplikasi berada mengalami pemadaman total (*outage*).

---

## 2. Intermediate Questions (5 Soal)

### Soal 1
Saat menjalankan deployment stack AWS CloudFormation berskala besar, stack Anda mengalami kegagalan pada salah satu resource Lambda dan memasuki status `UPDATE_ROLLBACK_IN_PROGRESS`. Di tengah proses pengembalian, stack tersebut berhenti dengan status `UPDATE_ROLLBACK_FAILED`. Apa penyebab paling umum dari kondisi ini dan bagaimana cara terbaik memperbaikinya?
- A. Syntax YAML Lambda function memiliki kesalahan indentasi; perbaiki file lalu jalankan `cdk synth`.
- B. Sebuah resource yang hendak dikembalikan atau dihapus oleh CloudFormation telah dimodifikasi atau dikunci di luar kendali CloudFormation (misal: security group sedang digunakan oleh ENI baru yang dibuat manual, atau S3 bucket terisi file padahal retain policy-nya delete). Solusinya adalah menggunakan CLI `continue-update-rollback` dengan opsi `--resources-to-skip`.
- C. CloudWatch logs kuotanya habis; solusinya adalah menaikkan batas limit kuota akun AWS.
- D. S3 bucket deployment template kehilangan koneksi internet; solusinya adalah restart NAT Gateway.

### Soal 2
Perhatikan konfigurasi lifecycle hook AWS CodeDeploy berikut. Jika Anda ingin menjalankan *smoke test integration* via Lambda untuk memvalidasi apakah Pod atau instance versi baru dapat merespons API dengan payload pengujian sebelum trafik publik dialihkan ke versi tersebut, hook manakah yang wajib Anda gunakan?
- A. `ApplicationStop`
- B. `AfterAllowTraffic`
- C. `BeforeAllowTraffic`
- D. `BeforeInstall`

### Soal 3
Bagaimana arsitektur GitOps ArgoCD memitigasi risiko keamanan "God-Mode Credentials" pada runner CI/CD eksternal (seperti Jenkins atau GitHub Actions Runner)?
- A. Mengenkripsi file `kubeconfig` menggunakan enkripsi GPG di dalam repo Git publik.
- B. Runner CI tidak diberikan akses jaringan atau hak akses administratif IAM ke API Server EKS; runner hanya mem-push commit ke repo Git, dan ArgoCD controller yang berada di dalam VPC klaster menggunakan IAM Roles for Service Accounts (IRSA) untuk menerapkan perubahan.
- C. Mengizinkan akses anonymous pada EKS Kubernetes API Server.
- D. Membatasi deployment hanya boleh dilakukan dari IP publik developer.

### Soal 4
Sebuah aplikasi web finansial memiliki basis data Amazon DynamoDB Global Tables multi-region antara `us-east-1` dan `eu-west-1`. Jika terjadi partisi jaringan transien antar-region, bagaimana DynamoDB Global Tables menangani konflik pembaruan data secara simultan pada item yang sama di kedua region?
- A. Melempar exception `TransactionCanceledException` dan membatalkan kedua penulisan.
- B. Menggunakan aturan deterministik *Last-Writer-Wins* berdasarkan stempel waktu (timestamp) tingkat sistem antar pembaruan.
- C. Mengunci kedua region hingga operator manusia memilih data yang valid di konsol AWS.
- D. Mengubah data menjadi format base64 dan menggabungkan kedua string.

### Soal 5
Pada AWS CDK v2, jika Anda memiliki Stack Jaringan (`NetworkStack`) dan Stack Database (`DatabaseStack`), bagaimana mekanisme transmisi nilai VPC ID dari `NetworkStack` ke `DatabaseStack` tanpa menyebabkan *hard dependency cycle* yang mengunci proses update di kemudian hari?
- A. Melakukan hardcode string subnet ID pada kedua file stack.
- B. Menyimpan nilai VPC ID di file teks lokal runner lalu dibaca menggunakan library `fs`.
- C. Mengekspor value menggunakan CloudFormation Exported Outputs (`stack.exportValue()`) atau menyimpannya di AWS Systems Manager (SSM) Parameter Store lalu dibaca via `StringParameter.valueFromLookup()`.
- D. Menempatkan seluruh kode dalam satu file monolitik tanpa membagi Stack.

---

### Kunci Jawaban & Penjelasan Intermediate Questions

1. **Jawaban: B**  
   *Penjelasan:* `UPDATE_ROLLBACK_FAILED` terjadi ketika CloudFormation gagal mengembalikan state resource ke kondisi awal karena ada dependensi atau perubahan out-of-band (misal S3 bucket tidak kosong, subnet terikat ENI liar). Opsi `aws cloudformation continue-update-rollback --resources-to-skip <logical-ids>` memungkinkan CloudFormation mengabaikan resource bermasalah tersebut agar rollback selesai.

2. **Jawaban: C**  
   *Penjelasan:* Pada CodeDeploy lifecycle, hook `BeforeAllowTraffic` dijalankan setelah versi target baru siap di-deploy, namun *sebelum* target group listener mengalihkan trafik publik ke versi tersebut. Ini adalah titik ideal untuk menjalankan pengujian fungsional dan integrasi otomatis via Lambda.

3. **Jawaban: B**  
   *Penjelasan:* Pada arsitektur GitOps pull-based, pipeline CI eksternal tidak membutuhkan akses kredensial ke klaster Kubernetes sama sekali. CI hanya bertugas menguji dan mem-push image ke ECR, lalu memperbarui Git manifest. ArgoCD yang berada di dalam perimeter keamanan klaster yang menarik perubahan secara internal via IAM Roles for Service Accounts (IRSA).

4. **Jawaban: B**  
   *Penjelasan:* Amazon DynamoDB Global Tables menggunakan rekonsiliasi berbasis *Last-Writer-Wins* (LWW). Jika penulisan bersamaan terjadi pada item yang sama di dua region berbeda, pembaruan dengan timestamp atribut metadata sistem terbaru yang akan menang dan menimpa perubahan lainnya.

5. **Jawaban: C**  
   *Penjelasan:* Penggunaan SSM Parameter Store (`valueFromLookup`) atau loosely-coupled parameter outputs memutus ikatan ketat (*tight coupling*) antar CloudFormation stack. Tight coupling via CloudFormation `Export`/`Fn::ImportValue` sering memicu stack update failure jika Anda ingin memodifikasi atau me-replace resource yang sedang diimpor oleh stack lain.

---

## 3. Scenario-Based Questions (3 Kasus Nyata)

### Kasus 1: Insiden "Breaking Database Migration" pada Canary Rollout
**Skenario:**  
Tim SRE sebuah unicorn logistik merilis versi `v3.2.0` dari microservice pesanan menggunakan strategi Argo Rollouts Canary di Amazon EKS. Skrip deployment menjalankan migrasi database yang me-rename kolom `customer_phone` menjadi `contact_number` pada database Aurora PostgreSQL produksi. 

Dua menit setelah fase canary dimulai (alokasi 10% trafik ke Pods baru), metrik HTTP 500 error melonjak tajam hingga 40% di seluruh sistem. Argo Rollouts mendeteksi anomali ini dan secara otomatis membatalkan rollout (*rolled back*), mengembalikan 100% alokasi trafik ke Pods versi stabil (`v3.1.0`). Namun, setelah rollback sukses dilakukan, Pods versi stabil (`v3.1.0`) tetap terus-menerus menghasilkan HTTP 500 error, mengakibatkan downtime total selama 25 menit.

**Pertanyaan Analisis SRE:**
1. Mengapa automated rollback dari Argo Rollouts gagal memulihkan kesehatan sistem ke kondisi normal?
2. Bagaimana perbaikan arsitektur dan pola deployment database yang wajib diimplementasikan tim engineer untuk mencegah insiden berulang?

**Panduan Jawaban Kasus 1:**
1. **Akar Masalah:**  
   Argo Rollouts hanya mengendalikan siklus hidup komputasi aplikasi di Kubernetes (Pods dan ingress traffic weighting). Argo Rollouts *tidak* mengembalikan perubahan skema basis data (*stateful layer*). Ketika skrip migrasi me-rename kolom di Aurora PostgreSQL, Pods versi `v3.1.0` (yang masih membutuhkan kolom lama `customer_phone`) langsung mengalami SQL exception query failure. Ketika rollback terjadi, 100% trafik kembali ke Pods `v3.1.0` yang sudah tidak kompatibel dengan skema database baru yang sudah terlanjur termutasi secara destruktif.
2. **Solusi Rekayasa:**  
   Terapkan strategi **Expand and Contract (Parallel Run Database Evolution)** yang terpisah dari pipeline deployment aplikasi:
   - *Langkah 1 (Expand):* Tambahkan kolom baru `contact_number` tanpa menghapus `customer_phone`. Pasang database trigger atau sinkronisasi aplikasi dua arah agar kedua kolom terisi. Rilis skrip ini di pipeline terpisah sebelum rilis aplikasi.
   - *Langkah 2 (App Rollout):* Deploy aplikasi baru `v3.2.0` dengan Canary. Aplikasi ini menulis ke kedua kolom dan membaca dari `contact_number`. Jika terjadi rollback, versi `v3.1.0` tetap aman karena kolom `customer_phone` masih ada dan valid.
   - *Langkah 3 (Contract):* Setelah rilis `v3.2.0` stabil 100% selama beberapa hari, jalankan pipeline terpisah untuk menghapus kolom lama `customer_phone`.

---

### Kasus 2: Multi-Region Disaster Recovery Split-Brain & Data Inconsistency
**Skenario:**  
Sebuah platform SaaS multinasional merancang arsitektur multi-region Active-Passive Warm Standby antara `ap-southeast-1` (Singapura - Primary) dan `ap-southeast-3` (Jakarta - Secondary). Sistem menggunakan Amazon Route 53 Application Recovery Controller (ARC) untuk mengontrol failover DNS, dan data direplikasi asinkron menggunakan Amazon Aurora Global Database. 

Saat terjadi gangguan kabel bawah laut internasional yang menyebabkan lonjakan packet loss 85% antar region, sistem monitoring otomatis memicu failover: Route 53 ARC mematikan routing control Singapura dan mengaktifkan routing control Jakarta. Namun, tim operasional tidak memverifikasi metrik Aurora Global Database replication lag (yang saat itu tertinggal 4 menit akibat gangguan jaringan transmisi). Tiga puluh menit kemudian, jaringan kabel pulih dan Singapura kembali aktif tanpa koordinasi, menyebabkan kedua region memproses transaksi pembayaran secara bersamaan (Split-Brain).

**Pertanyaan Analisis SRE:**
1. Risiko fatal apa yang dialami data finansial akibat insiden tersebut?
2. Bagaimana rancangan SOP dan otomatisasi kontrol Route 53 ARC + Aurora Global Database yang benar untuk mencegah split-brain dan data loss di masa depan?

**Panduan Jawaban Kasus 2:**
1. **Dampak Data:**  
   Terjadi fenomena *Data Loss* (data transaksi selama 4 menit replikasi tertinggal di Singapura hilang atau tidak terbaca di Jakarta saat promosi secondary cluster) dan *Data Inconsistency / Split-Brain Divergence* (transaksi baru ditulis di kedua cluster secara independen dengan auto-increment ID yang bertabrakan, membuat rekonsiliasi database pasca-insiden menjadi bencana audit integritas data).
2. **Arsitektur Perbaikan:**
   - **Pre-Failover Assertion Check:** Otomatisasi failover tidak boleh hanya bergantung pada health check publik. Lambda orkestrator failover wajib mengevaluasi metrik CloudWatch `AuroraGlobalDatabaseReplicationLag`. Jika lag melebihi ambang batas RPO yang diizinkan (misal > 10 detik), pemicuan failover otomatis wajib memerlukan *manual executive approval* via AWS SNS/ChatOps.
   - **Isolasi Total Region Lama (Fencing/STONITH):** Sebelum mempromosikan cluster Jakarta menjadi Read/Write (`Failover Aurora Global Database`), skrip otomatisasi failover wajib mengeksekusi *fencing*: memutus akses IAM ke cluster Singapura atau mengubah SG database Singapura menjadi read-only/blackhole guna menjamin tidak ada trafik sisa yang dapat menulis data.
   - **Deterministic Promotion Flow:** Gunakan fitur terkelola *Planned Managed Failover* jika memungkinkan, atau jika bencana tak terencana (*unplanned outage*), jalankan prosedur failover terputus: cabut cluster sekunder dari topologi global sebelum dijadikan master independen untuk mencegah auto-sync yang merusak histori data.

---

### Kasus 3: Pipeline Deadlock Akibat Circular Cross-Stack Reference di AWS CDK
**Skenario:**  
Sebuah tim platform engineering membagi arsitektur mereka menjadi tiga CDK Stacks:
1. `VpcStack`: Mengelola VPC dan Subnet.
2. `SecurityStack`: Mengelola Security Group untuk ALB dan Application Pods.
3. `ComputeStack`: Mengelola Cluster EKS dan Target Groups ALB.

Seorang engineer baru menambahkan rule ingress pada Security Group di `SecurityStack` yang mengizinkan trafik dari Target Group ALB yang dideklarasikan di `ComputeStack`. Pada saat yang sama, `ComputeStack` mengimpor Security Group dari `SecurityStack` untuk diterapkan ke Pods worker node. 

Saat pipeline AWS CodePipeline menjalankan perintah `cdk deploy --all`, CloudFormation mengembalikan error fatal:
`Circular dependency between resources: [SecurityStack/AppSecurityGroup, ComputeStack/TargetGroup]` dan seluruh deployment dibatalkan secara permanen.

**Pertanyaan Analisis SRE:**
1. Mengapa CloudFormation gagal memproses dependensi tersebut padahal CDK berhasil melakukan sintesis kode ke YAML?
2. Bagaimana cara merefaktor construct CDK tersebut agar dependency graph kembali menjadi Directed Acyclic Graph (DAG) yang valid?

**Panduan Jawaban Kasus 3:**
1. **Akar Masalah:**  
   CDK adalah compiler yang membangun construct tree imperatif menjadi template CloudFormation. Validasi siklus dependensi penuh dieksekusi oleh graph solver engine AWS CloudFormation runtime. Ketika Stack A mengimpor nilai atribut dari Stack B (`Fn::ImportValue`), dan Stack B secara bersamaan mengimpor nilai dari Stack A, CloudFormation tidak dapat menentukan stack mana yang harus dibuat terlebih dahulu, menghasilkan kegagalan *circular reference deadlock*.
2. **Refactoring Arsitektur:**
   - **Prinsip Inversion of Control / Decoupling:** Hapus referensi silang langsung.
   - **Teknik Standalone Rule Attachment:** Biarkan `SecurityStack` mendefinisikan Security Group dasar. Pada `ComputeStack`, setelah ALB Target Group dibuat, gunakan method L2 construct CDK seperti `securityGroup.addIngressRule(...)` secara langsung di dalam scope `ComputeStack`, atau gunakan construct independen `aws-cdk-lib/aws-ec2.CfnSecurityGroupIngress`.
   - **Arsitektur Parameter Indireksi:** Simpan identifier ARN atau Security Group ID ke dalam AWS SSM Parameter Store pada Stack pertama, lalu baca nilai tersebut secara loosely-coupled di Stack kedua menggunakan parameter dynamic reference tanpa membentuk ikatan stack export permanen.

---

## 4. Practical Chapter Challenge
**Judul Tantangan:** Implementasi GitOps Canary Rollout Simulation & Multi-Region Health Controller

**Tujuan:**  
Peserta diuji untuk merancang dan memprogram skrip simulasi orkestrasi GitOps end-to-end yang memvalidasi siklus rilis canary, mengevaluasi telemetri aplikasi secara dinamis, melakukan mitigasi kegagalan otomatis (automated rollback), serta menyimulasikan failover disaster recovery lintas region dengan Route 53 ARC Routing Control switch.

**Kriteria Penerimaan Arsitektur (Acceptance Criteria):**
1. Skrip simulasi harus mandiri (*self-contained*), dapat dieksekusi menggunakan Python 3.9+, dan memiliki interface CLI interaktif.
2. Mengimplementasikan siklus tahapan Canary Weight: 10% -> 25% -> 50% -> 100%.
3. Memiliki sub-engine evaluator metrik (HTTP Error Rate dan P99 Latency).
4. Jika error rate melebihi threshold (3%) pada salah satu interval observasi, Canary Controller harus membatalkan rilis seketika (*abort & rollback*) dan mengembalikan bobot trafik 100% ke versi stabil lama.
5. Jika region primary mengalami kegagalan fatal berkelanjutan, fungsi failover multi-region Route 53 ARC harus dipicu untuk mematikan Primary Cell Routing Control dan menyalakan Secondary Cell Routing Control.

---