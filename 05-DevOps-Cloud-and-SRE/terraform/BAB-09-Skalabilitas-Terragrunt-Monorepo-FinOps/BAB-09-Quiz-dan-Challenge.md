# Evaluasi Pembelajaran Bab 09: Skalabilitas Skala Besar: Terragrunt & Monorepo Patterns

## 1. Basic Questions (5 Soal)

### Soal 1
Apa perbedaan mendasar antara fungsi file `terragrunt.hcl` dengan file `main.tf` standar pada ekosistem Terraform?
- **A.** `terragrunt.hcl` digunakan untuk menuliskan kode logika resource cloud, sedangkan `main.tf` digunakan untuk konfigurasi CI/CD.
- **B.** `terragrunt.hcl` adalah file konfigurasi orkestrasi wrapper yang menginjeksi backend, dependency, dan input ke dalam modul Terraform yang didefinisikan pada `main.tf`.
- **C.** `terragrunt.hcl` mengompilasi kode HCL menjadi file binary mesin sebelum dieksekusi.
- **D.** `terragrunt.hcl` hanya dapat digunakan jika cloud provider yang digunakan adalah AWS.
> **Kunci Jawaban: B**  
> **Penjelasan**: Terragrunt bertindak sebagai thin wrapper di atas Terraform. File `terragrunt.hcl` mengonfigurasi bagaimana modul Terraform (yang berisi `main.tf`) dipanggil, diinjeksi remote state backend-nya, dan dihubungkan dependensinya secara DRY.

---

### Soal 2
Fungsi Terragrunt bawaan manakah yang digunakan untuk mencari dan mewarisi file konfigurasi root dari direktori induk ke direktori leaf?
- **A.** `get_parent_folder()`
- **B.** `read_parent_file()`
- **C.** `find_in_parent_folders()`
- **D.** `resolve_ancestor_path()`
> **Kunci Jawaban: C**  
> **Penjelasan**: Fungsi `find_in_parent_folders()` menelusuri pohon direktori ke atas secara rekursif hingga menemukan file target (secara default `terragrunt.hcl` atau nama file yang ditentukan).

---

### Soal 3
Bagaimana Terragrunt membantu mengurangi *blast radius* dalam pengelolaan infrastruktur cloud?
- **A.** Dengan mengenkripsi file state menggunakan algoritma quantum-safe.
- **B.** Dengan memisahkan setiap komponen infrastruktur ke dalam file remote state independen yang terisolasi.
- **C.** Dengan memblokir seluruh operasi `destroy` pada level Terraform CLI engine.
- **D.** Dengan menyatukan seluruh resource ke dalam satu root state agar mudah dikontrol.
> **Kunci Jawaban: B**  
> **Penjelasan**: Terragrunt mendorong pemisahan file state per komponen/modul/region (contoh: VPC memiliki state sendiri, RDS memiliki state sendiri). Jika terjadi kesalahan konfigurasi atau corrupt state pada satu komponen, komponen lain tetap aman.

---

### Soal 4
Apa peran utama blok `mock_outputs` dalam konfigurasi blok `dependency` di Terragrunt?
- **A.** Memberikan nilai kembalian palsu ke resource cloud saat proses deployment produksi agar biaya lebih murah.
- **B.** Menggantikan provider cloud sungguhan dengan simulator mock localstack.
- **C.** Menyediakan nilai data output tiruan agar perintah seperti `terragrunt plan` atau `validate` dapat berjalan sukses saat modul upstream belum di-deploy.
- **D.** Menghapus seluruh data output sensitif dari file log CI/CD.
> **Kunci Jawaban: C**  
> **Penjelasan**: Saat lingkungan baru pertama kali dibuat, modul dependensi upstream belum terbentuk sehingga belum memiliki output state. `mock_outputs` mencegah command perencana (`plan`/`validate`) gagal akibat missing reference.

---

### Soal 5
Pada konsep FinOps terintegrasi dengan Terragrunt/Terraform, apa fungsi utama dari kakas Infracost?
- **A.** Menagih tagihan kartu kredit cloud provider secara langsung saat pipeline merge.
- **B.** Menganalisis perubahan kode IaC dan menampilkan estimasi biaya finansial (delta cost) secara otomatis pada tahapan Pull Request.
- **C.** Mengoptimalkan alokasi memori Linux kernel pada instans virtual machine.
- **D.** Mengubah arsitektur cloud multi-cloud menjadi on-premise datacenter secara otomatis.
> **Kunci Jawaban: B**  
> **Penjelasan**: Infracost adalah kakas FinOps *shift-left* yang mem-parsing HCL / plan file Terraform dan menghitung estimasi biaya bulanan infrastruktur sebelum kode diterapkan ke production.

---

## 2. Intermediate Questions (5 Soal)

### Soal 6
Perhatikan potongan kode `terragrunt.hcl` berikut:
```hcl
dependency "vpc" {
  config_path = "../vpc"
  mock_outputs = {
    vpc_id = "mock-vpc-999"
  }
  mock_outputs_allowed_terraform_commands = ["validate"]
}
```
Apa yang akan terjadi jika seorang insinyur menjalankan perintah `terragrunt plan` pada modul ini, sementara modul `../vpc` sama sekali belum pernah di-deploy ke AWS?
- **A.** Perintah `terragrunt plan` berjalan sukses dan menggunakan nilai `"mock-vpc-999"`.
- **B.** Terragrunt secara otomatis men-deploy modul `../vpc` terlebih dahulu ke AWS lalu melanjutkan plan.
- **C.** Perintah `terragrunt plan` akan melempar error karena `"plan"` tidak terdaftar di dalam list parameter `mock_outputs_allowed_terraform_commands`.
- **D.** Terragrunt akan mengabaikan nilai mock dan meminta input manual lewat stdin CLI.
> **Kunci Jawaban: C**  
> **Penjelasan**: Karena atribut `mock_outputs_allowed_terraform_commands` hanya mendefinisikan `["validate"]`, maka saat perintah `plan` dieksekusi, Terragrunt akan memverifikasi output state nyata dari modul `../vpc`. Jika modul belum di-apply, operasi akan langsung dihentikan dengan error.

---

### Soal 7
Dalam pola arsitektur Monorepo *Live vs Modules*, manakah praktik yang paling sesuai standar keamanan dan skalabilitas enterprise?
- **A.** Menyimpan definisi deklarasi resource (`.tf`) dan data nilai input konkret spesifik production dalam direktori yang sama.
- **B.** Memisahkan repositori: repositori modul murni bersifat stateless serta di-versioning menggunakan tag semantik Git, sedangkan repositori live memanggil modul tersebut via URL git ter-tag.
- **C.** Menggunakan referensi branch `ref=main` pada seluruh modul leaf `infrastructure-live` agar update kode modul otomatis diterapkan saat commit baru.
- **D.** Menghapus file remote state backend dan beralih menggunakan local backend pada monorepo.
> **Kunci Jawaban: B**  
> **Penjelasan**: Memisahkan reusable modules dengan versioning tag semantik (misal `?ref=v1.2.0`) menjamin prinsip immutability. Lingkungan production tidak boleh terpapar perubahan breaking change yang tidak terkontrol dari branch `main`.

---

### Soal 8
Bagaimana cara terbaik menerapkan tata kelola penandaan (*resource tagging governance*) secara seragam pada seluruh modul leaf AWS di Terragrunt?
- **A.** Meminta setiap developer menuliskan variabel `tags = { ... }` secara manual di setiap modul Terraform.
- **B.** Menjalankan skrip Python cron-job di AWS console setiap malam untuk menimpa tag.
- **C.** Menggunakan blok `generate` di root `terragrunt.hcl` untuk menginjeksi blok `provider "aws"` yang memuat konfigurasi `default_tags`.
- **D.** Terragrunt tidak memiliki kemampuan untuk memodifikasi konfigurasi provider Terraform.
> **Kunci Jawaban: C**  
> **Penjelasan**: Menggunakan blok `generate "provider"` pada level root Terragrunt memungkinkan injeksi global provider AWS dengan konfigurasi `default_tags`. Seluruh resource yang didukung di bawah hierarki tersebut akan otomatis mewarisi tag governance tersebut.

---

### Soal 9
Apa potensi bahaya dari penggunaan perintah `terragrunt run-all apply` pada tingkat direktori root di lingkungan produksi enterprise yang besar?
- **A.** Terragrunt akan mengubah format state file menjadi format XML biner yang tidak kompatibel.
- **B.** Dapat memicu AWS API Rate Limiting (throttling), membebani resource runner, dan mengeksekusi mutasi masif di luar kontrol yang meningkatkan risiko downtime simultan.
- **C.** Menghapus seluruh file konfigurasi `.terragrunt-cache`.
- **D.** Terragrunt CLI menolak eksekusi `run-all` jika dijalankan di branch produksi.
> **Kunci Jawaban: B**  
> **Penjelasan**: Menjalankan `run-all` pada root direktori enterprise dapat meluncurkan puluhan proses apply secara paralel. Hal ini kerap menimbulkan API Throttling dari cloud provider, saturasi network/CPU runner CI/CD, serta risiko kecelakaan operasional jika terjadi kesalahan input global.

---

### Soal 10
Mengapa teknik *state splitting* (pemisahan state) yang difasilitasi oleh Terragrunt membuat proses CI/CD Terraform menjadi jauh lebih cepat dibandingkan pendekatan Terraform monolith?
- **A.** Karena Terragrunt mengompres file state menjadi file arsip `.tar.gz`.
- **B.** Karena Terraform hanya perlu me-refresh state untuk sejumlah kecil resource yang sedang diubah pada modul tertentu, bukan me-refresh ribuan resource di seluruh infrastruktur cloud.
- **C.** Terragrunt mem-bypass proses `terraform refresh` secara permanen.
- **D.** Terragrunt menggunakan engine kompilasi berbasis C++ untuk menggantikan Go runtime.
> **Kunci Jawaban: B**  
> **Penjelasan**: Pada Terraform monolitik, perintah `terraform plan` harus melakukan API call `Get/Describe` untuk setiap resource dalam state guna sinkronisasi (*refreshing state*). Memecah state menjadi unit-unit kecil membuat siklus refresh hanya berlangsung beberapa detik untuk komponen yang bersangkutan.

---

## 3. Scenario-Based Questions (3 Soal Kasus Nyata)

### Skenario 1: Bencana Kegagalan Dependency Circular
Sebuah tim platform sedang merefaktor infrastruktur monorepo mereka. Mereka memecah komponen menjadi:
- `modules/security-groups`
- `modules/alb`
- `modules/ecs-cluster`

Konfigurasi Terragrunt diatur sedemikian rupa sehingga `modules/alb` membutuhkan Security Group ID dari `modules/security-groups`. Namun, seorang engineer lain mengonfigurasi `modules/security-groups` agar membutuhkan ARN dari ALB untuk membuat aturan ingress security group spesifik. 

Saat pipeline CI/CD mengeksekusi:
```bash
terragrunt run-all plan
```
Pipeline membeku (*hang*) selama beberapa saat lalu menghasilkan error:
```text
[terragrunt] Detected cycle in dependency graph:
  security-groups -> alb -> security-groups
```

**Pertanyaan Kasus 1**:
Sebagai Principal Architect, langkah struktural apa yang harus Anda instruksikan kepada tim untuk memecahkan deadlock dependency circular ini secara permanen tanpa merusak prinsip isolasi state?
- **A.** Jalankan perintah menggunakan flag `--terragrunt-ignore-dependency-errors` agar Terragrunt mengabaikan cycle tersebut.
- **B.** Dekopel dependensi dengan memisahkan Security Group Rules ke modul terpisah (`modules/security-group-rules`), atau gunakan teknik *self-referencing/standalone security group rule* (`aws_security_group_rule`) yang dieksekusi setelah instance ALB selesai terbuat.
- **C.** Gabungkan kembali folder `alb`, `security-groups`, dan `ecs-cluster` ke dalam satu state file monolitik raksasa.
- **D.** Ubah backend remote state S3 kembali ke local backend file.
> **Kunci Jawaban: B**  
> **Penjelasan**: Circular dependency pada level arsitektur diselesaikan dengan mengekstraksi titik silang dependensi. Dengan memisahkan deklarasi *Security Group Container* dari *Security Group Rules* (atau menempatkan rule pada modul yang membutuhkan setelah ALB ARN terbentuk), siklus dependensi DAG menjadi linier dan searah: SG -> ALB -> SG_Rule.

---

### Skenario 2: Anomali Lonjakan Biaya FinOps Tersembunyi
Di sebuah platform e-commerce, seorang insinyur DevOps mengajukan Pull Request yang menambahkan modul Redis Cache ke environment staging dan production. Modul Terragrunt dikonfigurasi menggunakan:
```hcl
inputs = {
  instance_type = "cache.m6g.4xlarge"
  num_cache_nodes = 3
  automatic_failover_enabled = true
}
```
Repository telah diintegrasikan dengan Infracost CLI pada GitHub Actions. Pipeline mendeteksi lonjakan biaya:
```text
Project: infrastructure-live/prod/ap-southeast-1/cache/redis
Monthly cost will increase by $1,842.36 (+320%)
```

Namun, tim dev berargumen bahwa instance besar ini dibutuhkan untuk pengujian performa tinggi akhir tahun dan meminta PR segera di-merge. Kebijakan FinOps perusahaan menetapkan bahwa lonjakan biaya di atas $500/bulan wajib menyertakan tag khusus `BusinessJustification` dan persetujuan dari FinOps Lead via GitHub Reviewers.

**Pertanyaan Kasus 2**:
Bagaimana cara merancang guardrail otomatis pada pipeline CI/CD Terragrunt untuk menegakkan tata kelola ini secara teknis?
- **A.** Mengirim email manual ke tim finance dan mempercayai kesepakatan verbal sebelum tombol merge ditekan.
- **B.** Menggunakan `infracost breakdown` dengan integrasi `infracost output --format=json` yang diparsing oleh script kebijakan (seperti OPA/Rego atau GitHub Actions Script step); jika delta cost > $500 dan tag `BusinessJustification` tidak terdefinisi pada input HCL atau label approval belum terpenuhi, script mengeluarkan `exit 1` untuk memblokir status check PR.
- **C.** Mematikan akun AWS staging agar kuota anggaran cloud berpindah ke environment production.
- **D.** Mengubah currency di Infracost ke mata uang yang nominal angkanya terlihat lebih kecil.
> **Kunci Jawaban: B**  
> **Penjelasan**: Praktik FinOps enterprise modern menerapkan gerbang otomatis (*automated shift-left policy gate*). Dengan mem-parsing output JSON Infracost dan memverifikasi metadata input Terragrunt/GitHub approvals di dalam CI step, sistem secara objektif dan deterministik dapat menggagalkan PR jika melanggar ambang batas anggaran tanpa persetujuan formal.

---

### Skenario 3: Inkonsistensi Tagging Multi-Account yang Mematahkan AWS Cost Allocation
Sebuah konglomerat memiliki 45 akun AWS yang diatur dalam AWS Organizations. Tim Finance menggunakan AWS Cost Allocation Tags (`CostCenter`, `Environment`, `Owner`) untuk membuat laporan penagihan bulanan kepada para pemangku kepentingan unit bisnis. 

Ditemukan bahwa 30% pengeluaran cloud masuk ke kategori *Unallocated Spend* (tidak teralokasi). Investigasi teknis mengungkap penyebabnya:
1. Beberapa tim menuliskan tag `cost-center`, sebagian `CostCenter`, sebagian `Cost_Center`.
2. Developer di beberapa modul leaf lupa meneruskan variabel `tags` ke resource anak.

**Pertanyaan Kasus 3**:
Bagaimana strategi arsitektur Terragrunt Monorepo yang paling efisien dan menyeluruh untuk menuntaskan masalah ketidaksesuaian tagging ini tanpa harus mengedit ratusan modul Terraform satu per satu?
- **A.** Meminta setiap engineer menandatangani SOP penulisan tag dan mengancam pemotongan bonus.
- **B.** Memanfaatkan blok `generate "provider"` pada root `terragrunt.hcl` untuk mendefinisikan blok `default_tags` pada AWS Provider v4/v5 secara terpusat, lalu mewajibkan seluruh konfigurasi leaf melakukan `include "root"`.
- **C.** Menghapus fitur tag di seluruh akun cloud dan membagi tagihan secara rata ke seluruh divisi.
- **D.** Menulis skrip Terraform mandiri yang berjalan setiap jam untuk menghancurkan resource yang tidak memiliki tag.
> **Kunci Jawaban: B**  
> **Penjelasan**: Fitur AWS Provider `default_tags` secara otomatis menyematkan tag ke seluruh resource AWS yang mendukung tagging yang dibuat melalui provider tersebut. Dengan menginjeksi blok ini secara dinamis melalui blok `generate` di root `terragrunt.hcl`, seluruh komponen leaf otomatis mewarisi penamaan tag standar yang konsisten (`CostCenter`, `Environment`, `Owner`) tanpa perlu menyentuh kode modul satu per satu.

---

## 4. Practical Chapter Challenge: Enterprise Monorepo Orchestration Engine

### Deskripsi Masalah
Sebagai Principal Cloud & SRE Curriculum Architect, Anda ditugaskan untuk memvalidasi kelayakan pipeline monorepo sebelum diimplementasikan di infrastruktur nyata. Anda diwajibkan membuat simulasi otomasi mandiri (self-contained simulation engine) yang mereplikasi cara kerja Terragrunt:
1. Mengurai ketergantungan antar-modul menjadi Directed Acyclic Graph (DAG).
2. Memverifikasi isolasi *blast radius* (tidak boleh ada siklus sirkular).
3. Melakukan audit tata kelola penandaan (*tag governance*).
4. Melakukan simulasi perhitungan kalkulasi biaya FinOps (*cost delta breakdown*).

Engine ini diwujudkan dalam program CLI Python profesional pada berkas `hands-on/m01/terragrunt_dry_catalog_sim.py`.

---