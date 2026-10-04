# BAB 01: Quiz, Challenge, & Knowledge Check
**Fondasi Infrastructure as Code & Arsitektur Internal Terraform Engine**

---

## 1. Basic Questions (5 Soal Konseptual Fundamental)

### Soal 1.1: Paradigma Deklaratif vs Imperatif & Teorema Rekonsiliasi State
Jelaskan perbedaan mendasar antara paradigma *Declarative* (seperti yang diadopsi oleh Terraform) dan *Imperative* (seperti Bash scripting, AWS CLI, atau Python Boto3 SDK) dalam orkestrasi infrastruktur cloud.
1. Bagaimana kedua paradigma tersebut menangani konsep **Idempotency** dan **State Convergence** ketika suatu resource mengalami *partial failure* di tengah jalan?
2. Mengapa pendekatan imperatif membutuhkan penulisan *error-handling* dan *state checking* bersarang yang masif (*if-exists-then-skip*), sedangkan pendekatan deklaratif menyerahkan logika konvergensi tersebut kepada *reconciliation engine*?
3. Uraikan konsekuensi ketiadaan *lifecycle tracking* eksplisit pada skrip imperatif saat sebuah resource di lingkungan produksi perlu di-deprovisioning (risiko *orphaned/zombie cloud resources*).

---

### Soal 1.2: Dekonstruksi Arsitektur Dual-Binary: Terraform Core vs Provider Plugin
Arsitektur internal Terraform dirancang terpisah (*decoupled*) menjadi dua subsistem independen: **Terraform Core** dan **Provider Plugins**.
1. Sebutkan tanggung jawab komputasi murni dari Terraform Core (pembacaan AST HCL2, evaluasi ekspresi, manipulasi *Directed Acyclic Graph*, dan kalkulasi diff). Mengapa Core sama sekali tidak memiliki kode SDK spesifik vendor cloud apa pun?
2. Bagaimana Core berkomunikasi dengan Provider Plugins di tingkat sistem operasi host? Jelaskan peran protokol **gRPC**, pustaka `go-plugin` HashiCorp, *UNIX domain socket* (atau *named pipe* pada Windows), serta pertukaran *magic cookie* saat proses *handshake*.
3. Apa keuntungan teknis arsitektur plugin out-of-process ini terhadap stabilitas memori, isolasi *crash*, dan siklus rilis (*release cycle*) provider yang independen dari rilis core binary Terraform?

---

### Soal 1.3: Anatomi Eksekusi Tiga Tahap: `init`, `plan`, dan `apply`
Uraikan alur kerja fundamental eksekusi Terraform yang terdiri dari tiga tahapan utama:
1. Apa saja operasi I/O dan sistem yang dieksekusi selama tahap `terraform init` (pengunduhan binary provider ke `.terraform/providers/`, inisialisasi modul, validasi *backend lock* file `.terraform.lock.hcl`, dan konfigurasi state backend)?
2. Dalam fase `terraform plan`, jelaskan perbedaan komputasi antara **Refresh Phase** (eksekusi RPC `ReadResource` terhadap infrastruktur aktual) dan **Diff Computation Phase** (perbandingan antara *HCL desired state*, *in-memory refreshed state*, dan *persisted state*).
3. Mengapa menyimpan artefak plan ke file biner (`terraform plan -out=tfplan`) merupakan *mandatory standard* dalam pipeline CI/CD produksi sebelum mengeksekusi `terraform apply tfplan`?

---

### Soal 1.4: Peran, Anatomi, dan Risiko Keamanan File State (`terraform.tfstate`)
File `terraform.tfstate` adalah jantung operasional Terraform yang berfungsi sebagai *metadata mapping engine*.
1. Mengapa Terraform memerlukan state file terpisah dan tidak bisa hanya mengandalkan API query real-time (*live querying*) ke cloud provider setiap kali dijalankan? Uraikan masalah *API rate limiting*, pemetaan ID logis ke ID fisik cloud, dan *dependency tracking*.
2. Bedah struktur JSON internal sebuah file state: jelaskan signifikansi field `serial`, `lineage`, `schema_version`, dan blok `resources` (termasuk `instances`, `attributes`, dan `private`).
3. Mengapa file state berpotensi menjadi celah keamanan fatal (*security vulnerability*) jika disimpan di repository Git publik/internal tanpa enkripsi? Sebutkan contoh atribut sensitif yang tersimpan secara *plain-text* di dalam state file meskipun variabel HCL aslinya telah ditandai `sensitive = true`.

---

### Soal 1.5: Konstruksi Directed Acyclic Graph (DAG) & Deteksi Siklus (*Cycle Error*)
Terraform Core mengorganisasi seluruh resource dan dependensi ke dalam struktur data **Directed Acyclic Graph (DAG)**.
1. Jelaskan perbedaan antara dependensi implisit (*implicit dependency* via interpolasi atribut, misal: `subnet_id = aws_subnet.main.id`) dan dependensi eksplisit (*explicit dependency* via meta-argument `depends_on = [...]`). Kapan dependensi eksplisit mutlak diperlukan?
2. Bagaimana algoritma graph Terraform mendeteksi dependensi melingkar (*circular dependency / graph cycle*) sebelum panggilan API cloud dieksekusi? Mengapa error `Cycle: resource_a -> resource_b -> resource_a` langsung menghentikan proses evaluasi pada fase kompilasi graph?
3. Bagaimana DAG membedakan *destruction graph* dan *creation graph* ketika sebuah resource dimodifikasi sedemikian rupa sehingga memerlukan re-kreasi (*force replacement*)?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Sistem Terdistribusi)

### Soal 2.1: Mekanisme Distributed State Locking dan Penanganan Split-Brain Concurrency
Pada lingkungan enterprise dengan puluhan engineer dan pipeline CI/CD yang berjalan bersamaan, integritas state dilindungi oleh mekanisme *Distributed State Locking*.
1. Analisis cara kerja backend remote (seperti AWS S3 + DynamoDB atau Terraform Cloud / HashiCorp Consul) dalam mengelola *lock state*. Jelaskan struktur dokumen *LockInfo* (ID lock, Operation, Who, Version, Created, Path).
2. Apa yang terjadi secara teknis di level protokol HTTP/API jika dua pipeline CI/CD mengeksekusi `terraform apply` pada repository dan workspace yang sama secara simultan dalam selisih waktu 10 milidetik?
3. Kapan kondisi *Stale Lock* terjadi (misalnya runner CI/CD mengalami *kernel panic* atau di-*kill* secara paksa via `SIGKILL`)? Jelaskan risiko berbahaya dari penggunaan perintah `terraform force-unlock <LOCK_ID>` dan SOP verifikasi yang wajib dilakukan sebelum perintah tersebut dijalankan.

---

### Soal 2.2: Algoritma Graph Walk, Heuristik Paralelisme (`-parallelism`), dan Throttling API Cloud
Saat mengeksekusi plan atau apply, Terraform melakukan *graph traversal* (Graph Walk) menggunakan worker pool berorientasi konkurensi (Goroutine pool).
1. Secara default, Terraform menyetel parameter `-parallelism=10`. Jelaskan bagaimana Goroutine worker pool mengeksekusi simpul-simpul graf yang berada pada level kedalaman (*graph depth level*) yang sama secara independen.
2. Ketika mengelola arsitektur besar (misalnya pembuatan 50 Subnet, 100 Route Tables, dan puluhan Security Group Rules sekaligus), jelaskan fenomena **API Rate Limiting / Request Throttling** (HTTP 429 Too Many Requests / `RequestLimitExceeded`) dari sisi cloud provider.
3. Bagaimana mekanisme *exponential backoff with jitter* yang diterapkan oleh Provider SDK bekerja? Pada skenario apa Anda harus menurunkan parameter `-parallelism` (misal menjadi 3 atau 5) vs menaikkannya untuk optimasi performa deployment?

---

### Soal 2.3: Anatomi Drift Detection: Algoritma Tiga Sudut (HCL, State, dan Real World API Refresh)
*Configuration Drift* adalah kondisi di mana infrastruktur fisik di cloud menyimpang dari definisi kode HCL akibat manipulasi manual via Web Console ("ClickOps"), script ad-hoc, atau autoscaling agent.
1. Uraikan algoritma pembandingan tiga sudut (*Three-Way Diff*) yang dieksekusi Terraform Core:
   - $S_{prior}$ (State yang tersimpan di backend)
   - $S_{live}$ (State aktual hasil respons `ReadResource` RPC dari cloud API)
   - $C_{desired}$ (Konfigurasi HCL terbaru yang ditulis engineer)
2. Apa yang terjadi jika sebuah resource dihapus secara manual di Web Console cloud provider, namun definisinya masih ada di file HCL? Bagaimana Terraform menyusun plan rekonsiliasinya?
3. Sebaliknya, apa yang terjadi jika atribut sebuah resource dimodifikasi manual di Web Console (misalnya instance type EC2 diubah dari `t3.micro` menjadi `t3.large`), sedangkan HCL tetap menyatakan `t3.micro`? Jelaskan bagaimana atribut tersebut diperbarui di file state sebelum plan diajukan ke engineer.

---

### Soal 2.4: Manipulasi Lifecycle Meta-Arguments: `create_before_destroy`, `prevent_destroy`, dan `ignore_changes`
Terraform menyediakan blok kontrol metadata `lifecycle { ... }` untuk memodifikasi perilaku default CRUD engine.
1. Perilaku default Terraform saat suatu atribut memerlukan pembaruan destruktif (*forces replacement*) adalah *Destroy-then-Create*. Jelaskan bagaimana `create_before_destroy = true` membalik urutan DAG tersebut. Apa kendala arsitektural yang muncul jika resource tersebut memiliki batasan nama unik global (*unique name constraint*, misal: AWS S3 Bucket atau Security Group name)?
2. Bagaimana `prevent_destroy = true` memproteksi resource kritis seperti database produksi (RDS) atau storage state? Pada tahap evaluasi mana Terraform menggagalkan eksekusi jika ada perintah atau perubahan konfigurasi yang berpotensi menghancurkan resource tersebut?
3. Jelaskan skenario riil di mana `ignore_changes` wajib digunakan (contoh: tag yang diinjeksikan secara dinamis oleh platform CI/CD, atau atribut `desired_count` pada ECS Service / replica count pada Kubernetes Pod Autoscaler). Apa dampak negatif jika `ignore_changes` disalahgunakan secara berlebihan?

---

### Soal 2.5: Strategi Mitigasi Blast Radius: Monolithic State vs Multi-Layer Decoupled State
Menyimpan seluruh arsitektur organisasi dalam satu root module dengan satu file state monolitik adalah anti-pattern fatal pada skala enterprise.
1. Analisis kelemahan fatal dari *Monolithic State File* ditinjau dari tiga aspek:
   - **Blast Radius**: Dampak kesalahan sintaks atau eksekusi `terraform destroy/apply`.
   - **Execution Latency**: Waktu komputasi *refresh phase* DAG untuk ribuan resource.
   - **Concurrency Bottleneck**: Antrean lock antar tim pengembang.
2. Jelaskan konsep arsitektur **Layered State Isolation** (misal memisahkan layer: `00-bootstrap`, `01-networking-vpc`, `02-security-iam`, `03-data-storage`, `04-compute-apps`).
3. Bagaimana cara layer aplikasi (`04-compute-apps`) membaca output data (seperti `vpc_id` atau `subnet_ids`) dari layer networking (`01-networking-vpc`) tanpa menggabungkan state keduanya? Bandingkan pendekatan menggunakan `terraform_remote_state` data source versus integrasi berbasis Parameter Store / Secret Manager / Consul.

---

## 3. Production Scenario Questions (3 Skenario Kasus Nyata)

### Skenario 3.1: Deadlock Distributed Lock DynamoDB Akibat CI/CD Runner Hard-Killed
**Konteks Insiden:**
Sebuah pipeline GitLab CI/CD sedang mengeksekusi `terraform apply` untuk provisioning cluster Kubernetes di environment produksi. Pada menit ke-4, host runner fisik kehabisan memori (OOM) akibat proses build Docker lain, sehingga Linux OOM Killer mengirimkan sinyal `SIGKILL` (Exit Code 137) ke proses Terraform runner. Proses mati seketika tanpa sempat menjalankan rutin *cleanup* / graceful shutdown.

Beberapa menit kemudian, insinyur DevOps mencoba menjalankan pipeline perbaikan darurat, namun eksekusi gagal total dengan pesan kesalahan:
```text
Error: Error acquiring the state lock
Lock Info:
  ID:        d8a2f1b0-45c1-8e99-b1d2-09887123abcd
  Path:      mycompany-prod-terraform-state/prod/app.tfstate
  Operation: OperationTypeApply
  Who:       gitlab-runner@runner-host-04
  Version:   1.8.2
  Created:   2026-10-05 08:14:22.102391 UTC
  Info:      
```

**Tugas Analisis & Resolusi Anda:**
1. Jelaskan secara teknis mengapa lock tersebut tertinggal di DynamoDB (atau storage locking provider lainnya) dan mengapa Terraform tidak dapat melepaskannya secara otomatis.
2. Rancang langkah-langkah Standar Operasional Prosedur (SOP) verifikasi sebelum melakukan unlocking: Bagaimana Anda memastikan bahwa tidak ada proses latar belakang atau panggilan API cloud yang masih berjalan (*in-flight*) dari runner sebelumnya?
3. Tuliskan perintah presisi untuk membebaskan lock tersebut secara aman, serta langkah audit konsistensi state yang wajib dijalankan sebelum `apply` ulang diizinkan.

---

### Skenario 3.2: Circular Dependency Deadlock pada Cross-Referenced Security Groups
**Konteks Insiden:**
Tim platform engineering sedang membangun arsitektur two-tier: Web Application Firewall / Load Balancer (ALB) dan Backend Application Instance (EC2). Persyaratan keamanan dari tim SecOps menyatakan:
- Security Group ALB (`sg_alb`) hanya boleh mengizinkan outbound traffic ke port 8080 milik Security Group Backend (`sg_backend`).
- Security Group Backend (`sg_backend`) hanya boleh mengizinkan inbound traffic pada port 8080 dari Security Group ALB (`sg_alb`).

Insinyur junior menuliskan kode HCL berikut dalam file `security.tf`:
```hcl
resource "aws_security_group" "alb" {
  name        = "alb-sg"
  description = "ALB Security Group"
  vpc_id      = var.vpc_id

  egress {
    from_port       = 8080
    to_port         = 8080
    protocol        = "tcp"
    security_groups = [aws_security_group.backend.id]
  }
}

resource "aws_security_group" "backend" {
  name        = "backend-sg"
  description = "Backend Security Group"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 8080
    to_port         = 8080
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }
}
```

Saat dieksekusi `terraform plan`, Terraform langsung melempar error:
```text
Error: Cycle: aws_security_group.alb, aws_security_group.backend
```

**Tugas Analisis & Resolusi Anda:**
1. Bedah mengapa Terraform Core DAG builder memetakan kedua resource di atas sebagai siklus dependensi tak berujung (*unresolvable graph cycle*). Mengapa inline block `egress` dan `ingress` memaksa pembuatan edge dependensi bidirectional pada node graf?
2. Rekonstruksi arsitektur kode HCL di atas menggunakan resource independen (`aws_security_group_rule`) untuk memecah simpul graf menjadi topologi yang acyclic (DAG murni).
3. Jelaskan mengapa pemisahan definisi security group dari rules-nya merupakan *best practice* mutlak dalam arsitektur jaringan cloud berstandar enterprise.

---

### Skenario 3.3: Thundering Herd & API Rate Limiting (HTTP 429) Saat Disaster Recovery Multi-AZ
**Konteks Insiden:**
Saat simulasi Disaster Recovery (DR), tim infrastruktur memicu automated failover yang membuat ulang 120 instance database replica, 80 cache node, serta ratusan resource cloud pendukung pada region sekunder menggunakan Terraform.

Ketika `terraform apply -auto-approve` dijalankan dengan parameter bawaan, dalam waktu 45 detik output konsol dipenuhi pesan kegagalan acak:
```text
Error: error creating EC2 Instance: RequestLimitExceeded: Request limit exceeded.
  status code: 503, request id: 7c5a31a9-b681-42e1-a083-d92f7c001234
Error: error creating Subnet: Client.RequestLimitExceeded: You have reached the maximum request rate.
  status code: 400, request id: e41b9c20-7f22-481d-815f-c4a00192eabc
```
Akibatnya, puluhan resource tercipta dalam keadaan *partially provisioned*, graph eksekusi terhenti di tengah jalan, dan state file berada dalam kondisi setengah terisi (*tainted/partial state*).

**Tugas Analisis & Resolusi Anda:**
1. Jelaskan bagaimana sifat paralelisme Terraform DAG (`-parallelism=10`) memicu fenomena *thundering herd problem* terhadap endpoint API control plane cloud provider.
2. Bagaimana strategi konfigurasi Terraform Engine dan Provider SDK untuk memitigasi masalah ini tanpa mematikan otomatisasi? (Jelaskan tuning flag `-parallelism`, parameter `max_retries` pada provider blok, serta penyesuaian dependensi berbasis arsitektur graf modular).
3. Jika insiden partial failure ini sudah terlanjur terjadi di tengah apply, langkah verifikasi state apa saja (`terraform refresh`, `terraform state list`, pembersihan resource yang berstatus *tainted*) yang harus dieksekusi sebelum melakukan remediasi apply ulang?

---

## 4. Practical Chapter Challenge: Enterprise-Grade Multi-Layer Terraform Architecture

### Deskripsi Skenario Tantangan
Anda ditugaskan oleh Chief Technology Officer (CTO) untuk merancang dan mengimplementasikan fondasi arsitektur Infrastructure as Code berbasis Terraform tingkat produksi. Proyek ini harus mengeliminasi risiko monolitik, menerapkan isolasi *blast radius*, mendukung distributed state locking, memvalidasi input variabel dengan aturan bisnis ketat, mengendalikan siklus hidup resource kritis, dan menyediakan visualisasi graf dependensi.

Karena pengujian dilakukan pada lingkungan lokal/sandbox workstation, Anda diminta mengimplementasikan arsitektur ini menggunakan **Local Backend** yang disimulasikan secara terisolasi atau integrasi file-based state lock, memanfaatkan provider `local`, `null`, dan `random` (atau provider cloud mock) untuk merepresentasikan resource arsitektur tanpa membebankan biaya akun cloud riil.

---

### Persyaratan Arsitektur & Spesifikasi Implementasi

#### 1. Struktur Direktori Terisolasi (Blast Radius Isolation)
Buat struktur direktori multi-layer berikut:
```text
terraform-challenge-bab01/
├── layers/
│   ├── 01-networking/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   └── terraform.tfvars
│   └── 02-application/
│       ├── main.tf
│       ├── variables.tf
│       ├── outputs.tf
│       └── terraform.tfvars
└── scripts/
    └── generate_graph.sh
```

#### 2. Spesifikasi Layer 01: Networking Foundation
- **State Backend**: Gunakan backend `local` dengan path terisolasi: `../../states/networking/terraform.tfstate`.
- **Resource Simulation**:
  - Simulasikan pembuatan 1 Network Core (misal VPC virtual) dan 3 Subnet (Public, Private App, Private Database) menggunakan kombinasi `random_id` dan `local_file` yang memproduksi file manifest konfigurasi jaringan `/tmp/net_manifest.json`.
- **HCL2 Custom Validation**:
  - Definisikan variabel `environment` (string). Pasang blok `validation` yang memastikan nilainya hanya boleh salah satu dari: `["dev", "staging", "prod"]`. Sertakan pesan error deskriptif jika validasi gagal.
  - Definisikan variabel `ip_cidr_block` (string). Pasang blok `validation` yang memverifikasi bahwa string diawali dengan `10.` dan diakhiri dengan `/16` menggunakan fungsi bawaan `can(regex(...))`.
- **Output Eksplisit**:
  - Ekspor `network_id`, `subnet_map` (berisi ID dan status tiap subnet), serta `security_tier`.

#### 3. Spesifikasi Layer 02: Compute & Application Layer
- **State Backend**: Simpan di `../../states/application/terraform.tfstate`.
- **Cross-Layer State Consumption**:
  - Gunakan data source `terraform_remote_state` dengan backend `local` yang mengarah ke state file Layer 01 (`../../states/networking/terraform.tfstate`) untuk membaca `network_id` dan `subnet_map`.
- **Resource Lifecycle Control**:
  - Buat simulasi resource server cluster (3 node) menggunakan `local_file` yang menyimpan status node di `/tmp/cluster_nodes.json`.
  - Pasang blok `lifecycle`:
    - `create_before_destroy = true` untuk menjamin zero-downtime saat nama cluster diperbarui.
    - `ignore_changes = [ content ]` untuk menyimulasikan atribut dinamis runtime yang tidak boleh di-overwrite oleh Terraform.
- **Critical Resource Protection**:
  - Buat resource data storage simulasi (`local_file.production_db_storage`).
  - Pasang `lifecycle { prevent_destroy = true }`. (Buktikan dalam dokumentasi pengujian bahwa perintah `terraform destroy` pada resource ini berhasil digagalkan oleh engine).

#### 4. Ekstraksi dan Visualisasi Directed Acyclic Graph (DAG)
- Tuliskan shell script executable `scripts/generate_graph.sh` yang menjalankan:
  ```bash
  terraform -chdir=layers/02-application graph | dot -Tpng -o graph-application.png
  ```
- Sertakan versi format teks DOT dari graf tersebut dalam berkas laporan hasil uji.

---

### Kriteria Kelulusan Challenge (Acceptance Criteria)
1. **Determinisme Inisialisasi**: Kedua layer dapat diinisialisasi secara berurutan (`01-networking` -> `02-application`) tanpa kegagalan dependensi.
2. **Uji Validasi Variabel**: Ketika diuji dengan nilai input `environment = "testing"` atau CIDR `192.168.1.0/24`, perintah `terraform plan` langsung gagal dengan error validasi HCL yang jelas.
3. **Uji Remote State Cross-Reference**: Layer 02 berhasil membaca data output dari Layer 01 secara deterministik tanpa duplikasi deklarasi variabel.
4. **Uji Proteksi Lifecycle**: Perintah destruksi terhadap resource bertanda `prevent_destroy` wajib menghasilkan error fatal `Error: Resource ... has lifecycle.prevent_destroy set`.
5. **Graph Visual**: File graf DOT berhasil diekstrak dan membuktikan tidak adanya siklus dependensi (*acyclic*).

---

## 5. Knowledge Check & Mastery Checklist

### Saya Harus Memahami (Conceptual Mastery):
- [ ] Perbedaan esensial antara pendekatan deklaratif berbasis *reconciliation loop* dan skrip imperatif.
- [ ] Arsitektur gRPC / go-plugin yang memisahkan Terraform Core dengan Provider Plugins.
- [ ] Siklus internal eksekusi tiga tahap: `init`, `plan`, dan `apply`.
- [ ] Fungsi dan struktur internal `terraform.tfstate` sebagai pemeta *logical ID* ke *cloud physical ID*.
- [ ] Mengapa state file menyimpan secret secara *unencrypted plain-text* dan cara mitigasinya.
- [ ] Prinsip kerja *Directed Acyclic Graph* (DAG), pemetaan topologis simpul, dan deteksi siklus (*cycle error*).
- [ ] Mekanisme *Distributed State Locking* dan mitigasi race condition pada lingkungan tim.
- [ ] Algoritma deteksi drift melalui *Three-Way Diff* ($S_{prior}$, $S_{live}$, $C_{desired}$).
- [ ] Perilaku meta-argument `lifecycle`: `create_before_destroy`, `prevent_destroy`, dan `ignore_changes`.
- [ ] Manfaat isolasi *blast radius* melalui partisi multi-layer state vs state monolitik.

### Saya Tidak Perlu Menghafal (Low-Value Memorization):
- [ ] Seluruh skema atribut parameter spesifik dari ribuan resource provider cloud (cukup pahami cara membaca registry docs).
- [ ] Format biner internal dari protokol gRPC protobuf payload antara Core dan Plugin.
- [ ] Kode hash SHA-256 spesifik dari file biner provider pada `.terraform.lock.hcl`.

### Saya Harus Bisa Melakukan (Practical Engineering Skills):
- [ ] Menginisialisasi project Terraform dengan backend lokal maupun remote (`terraform init`).
- [ ] Menghasilkan dan menganalisis file execution plan deterministik (`terraform plan -out=...`).
- [ ] Menyusun aturan validasi variabel kustom (*custom input validation*) menggunakan fungsi bawaan HCL.
- [ ] Mengonfigurasi dependensi antar layer infrastruktur menggunakan `terraform_remote_state`.
- [ ] Menangani insiden *stale state lock* secara aman sesuai SOP mitigasi risiko.
- [ ] Mengidentifikasi dan merefaktor kode yang mengalami *circular dependency* (graph cycle).
- [ ] Mengekspor dan menganalisis visualisasi graf eksekusi menggunakan `terraform graph` dan Graphviz.

```text
===================================================================
CHECKLIST KESIAPAN BAB 01: FONDASI & ARSITEKTUR TERRAFORM
===================================================================
[ ] Memahami arsitektur internal Terraform Core & Provider RPC
[ ] Memahami siklus hidup state dan mekanisme distributed locking
[ ] Menguasai analisis DAG, deteksi circular dependency, & heuristik paralelisme
[ ] Mampu menjawab 5 Pertanyaan Basic secara komprehensif
[ ] Mampu menjawab 5 Pertanyaan Intermediate secara mendalam
[ ] Mampu merumuskan RCA dan resolusi untuk 3 Skenario Kasus Produksi
[ ] Berhasil mengimplementasikan dan menguji Chapter Challenge Multi-Layer
===================================================================
```
