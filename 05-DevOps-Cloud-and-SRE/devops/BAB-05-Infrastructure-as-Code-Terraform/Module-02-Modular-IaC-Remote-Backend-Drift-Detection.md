# Module 02: Modular Infrastructure, Remote Backend Locking, & Drift Detection

## 1. Learning Objective
Setelah menyelesaikan modul ini, pembelajar akan mampu:
1. Merancang arsitektur kode IaC yang *reusable* menggunakan **Terraform Modules** (Input Variables, Resources, dan Outputs).
2. Mengamankan state kolaboratif menggunakan **Remote Backend** (AWS S3 + DynamoDB State Locking / Terraform Cloud) untuk mencegah *race condition* dan konflik eksekusi paralel.
3. Mendeteksi dan memulihkan inkonsistensi infrastruktur akibat modifikasi manual (*Configuration Drift Detection & Reconciliation*).
4. Mengelola multi-environment (*Dev, Staging, Prod*) menggunakan pola arsitektur direktori terisolasi (*Directory-based separation*) atau Terraform Workspaces.

---

## 2. Prerequisite
- Memahami konsep dasar Terraform State dan siklus perintah `plan`/`apply` dari [BAB 05 Module 01](file:///d:/explore/roadmap.sh%20materi/DevOps/BAB-05-Infrastructure-as-Code-Terraform/Module-01-Declarative-IaC-HCL-State-Management.md).
- Mengetahui konsep dasar S3 bucket dan database key-value (DynamoDB).

---

## 3. Concept
Dalam tim engineering yang terdiri dari puluhan DevOps engineer, menjalankan Terraform dengan state file lokal (`terraform.tfstate`) di laptop masing-masing adalah resep kehancuran:
- **Race Condition**: Jika Engineer A dan Engineer B menjalankan `terraform apply` secara bersamaan, state file akan korup atau menimpa resource satu sama lain (*split-brain state*).
- **Configuration Drift**: Seorang SysAdmin panik saat insiden tengah malam dan mengubah ukuran server secara manual di Cloud Console (*ClickOps*). Sekarang, kondisi nyata di cloud berbeda dengan kode di Git repository. Ini disebut **Drift**.

Solusi standar enterprise:
1. **Remote Backend dengan Distributed Locking**: State file disimpan di bucket S3 terenkripsi, dan setiap operasi `plan`/`apply` wajib memperoleh kunci (*Lock*) di tabel DynamoDB. Tidak ada dua orang yang bisa mengeksekusi Terraform pada saat bersamaan.
2. **Modular Architecture**: Daripada menduplikasi 500 baris kode VPC untuk dev, staging, dan prod, buat 1 modul `modules/vpc` yang dapat dipanggil berulang kali dengan parameter berbeda.
3. **Automated Drift Detection**: Pipeline CI/CD yang berjalan setiap malam untuk memeriksa apakah ada perubahan liar di cloud yang tidak tercatat di kode Git.

---

## 4. Why?
Mengapa modul, remote backend, dan drift detection sangat penting?
1. **Kolaborasi Tim yang Aman**: Menghilangkan risiko state corruption akibat tabrakan eksekusi apply oleh dua engineer berbeda.
2. **DRY (Don't Repeat Yourself)**: Modul standar yang telah diaudit keamanannya oleh tim security (seperti modul VPC hardened) dapat dipakai ulang oleh seluruh tim pengembang di perusahaan.
3. **Kepatuhan Audit & Keamanan (SOC2 / ISO27001)**: Memastikan bahwa 100% infrastruktur cloud dikendalikan melalui GitOps Pull Request, bukan melalui akses manual orang per orang.

---

## 5. What?
Komponen penting dalam Terraform tingkat lanjut:
- **Terraform Module**: Paket folder berisi file `.tf` mandiri dengan parameter `variable "..."` (input) dan `output "..."` (kembalian).
- **Remote Backend S3 + DynamoDB**:
  - *S3 Bucket*: Menyimpan file `terraform.tfstate` dengan enkripsi AES-256 dan versioning aktif.
  - *DynamoDB Table*: Mengelola tabel kunci (*LockID*) untuk menghentikan proses kedua jika proses pertama sedang berjalan.
- **Drift Detection**: Mekanisme `terraform plan -refresh-only` yang membandingkan state lokal dengan data nyata di Cloud API.

---

## 6. How?
Alur kerja State Locking saat 2 engineer menjalankan apply:

```text
[ Engineer A: terraform apply ]             [ Engineer B: terraform apply ]
              │                                           │
              │ 1. Request Lock ke DynamoDB              │ 1. Request Lock ke DynamoDB
              ▼                                           ▼
+-------------------------------------------------------------------------+
|                  DYNAMODB STATE LOCK TABLE                              |
|  Status: LOCKED by Engineer A (Acquired LockID: 98124-abc)              |
+-------------------------------------------------------------------------+
              │                                           │
              ├─ Lock Diberikan (Proceed)                └─ Lock DITOLAK!
              ▼                                           ▼
[ Engineer A Mengeksekusi API Cloud ]       [ Error: State locked by Engineer A! ]
              │                             [ Eksekusi B dibatalkan aman ]
              ▼
[ Selesai -> Release Lock di DynamoDB ]
```

---

## 7. Analogy
Bayangkan **Remote Backend State Locking** seperti **Kamar Mandi Umum dengan Kunci Pintu Otomatis**:
- Jika Anda (Engineer A) masuk ke kamar mandi, Anda memutar grendel kunci (*State Lock di DynamoDB*).
- Jika rekan Anda (Engineer B) mencoba mendorong pintu dari luar, pintu terkunci rapat dan rekan Anda harus menunggu di luar (*Apply dicegah*).
- Setelah Anda selesai dan keluar, grendel terbuka kembali (*Lock released*), mempersilakan orang berikutnya masuk dengan aman tanpa insiden tabrakan.

---

## 8. Diagram
```text
+-------------------------------------------------------------+
|                     GIT REPOSITORY                          |
|  ├── environments/                                          |
|  │   ├── dev/     (main.tf -> module.vpc, module.db)        |
|  │   └── prod/    (main.tf -> module.vpc, module.db)        |
|  └── modules/                                               |
|      ├── vpc/     (Reusable VPC blueprint)                  |
|      └── rds/     (Reusable Database blueprint)             |
+-------------------------------------------------------------+
                               │
                               ▼
+-------------------------------------------------------------+
|                      REMOTE BACKEND                         |
|   +--------------------------+  +------------------------+  |
|   | AWS S3 Bucket            |  | DynamoDB Table         |  |
|   | (Encrypted State File)   |  | (LockID Mutex)         |  |
|   +--------------------------+  +------------------------+  |
+-------------------------------------------------------------+
```

---

## 9. Simple Example
Konfigurasi Remote Backend di `backend.tf`:

```hcl
terraform {
  backend "s3" {
    bucket         = "mycompany-terraform-states-prod"
    key            = "networking/vpc.tfstate"
    region         = "ap-southeast-1"
    encrypt        = true
    dynamodb_table = "terraform-lock-table"
  }
}
```

---

## 10. Practical Example
Memanggil Reusable Module di `environments/prod/main.tf`:

```hcl
module "production_vpc" {
  source = "../../modules/vpc"

  environment        = "production"
  vpc_cidr           = "10.0.0.0/16"
  public_subnet_cidrs = ["10.0.1.0/24", "10.0.2.0/24"]
  enable_nat_gateway = true
}

output "prod_vpc_id" {
  value = module.production_vpc.vpc_id
}
```

---

## 11. Real World Example
### Kasus: Insiden Configuration Drift yang Mematikan Auto-Scaling
1. Saat insiden server lambat pada hari Sabtu, seorang SysAdmin masuk ke AWS Console dan mengubah ukuran EC2 instance dari `t3.medium` menjadi `m5.2xlarge` secara manual.
2. SysAdmin lupa meng-update kode Terraform di Git repo.
3. Pada hari Senin, pipeline CI/CD rutin menjalankan `terraform apply` untuk deployment aplikasi baru.
4. Terraform mendeteksi *Drift*: State mengatakan instance harus `t3.medium`.
5. Terraform me-revert ukuran server kembali ke `t3.medium` tepat di jam sibuk, menyebabkan overload CPU dan crash sistem.
6. **Solusi SRE**:
   - Jalankan job cron harian di CI/CD: `terraform plan -detailed-exitcode`. Jika exitcode = 2 (ada drift terdeteksi), kirim peringatan darurat ke Slack tim SRE untuk segera disinkronkan.

---

## 12. Trade-offs
| Pendekatan Isolasi Environment | Directory-Based Isolation (`environments/dev`, `environments/prod`) | Terraform Workspaces (`terraform workspace select prod`) |
|---|---|---|
| **Pemisahan State** | 100% terisolasi (Beda file state dan beda backend S3) | File state terbagi di backend yang sama dengan prefix workspace |
| **Blast Radius** | Sangat kecil (Kesalahan di dev tidak bisa menyentuh prod) | Lebih berisiko jika salah switch workspace |
| **Kustomisasi Konfigurasi** | Sangat fleksibel (Prod bisa punya resource yang tidak ada di dev) | Terbatas (Semua workspace memakai kode file `.tf` yang persis sama) |
| **Rekomendasi Industri** | Standar Enterprise (Sangat direkomendasikan) | Cocok untuk testing ephemeral / feature branch sementara |

---

## 13. When To Use
- Gunakan **Terraform Modules**: Untuk setiap resource yang dibuat lebih dari satu kali (seperti VPC, cluster EKS, konfigurasi bucket S3 aman).
- Gunakan **Remote Backend + DynamoDB Lock**: Mutlak wajib untuk semua project Terraform yang dikerjakan oleh lebih dari 1 orang atau dijalankan via CI/CD.

---

## 14. When NOT To Use
- Jangan membagikan state file yang sama untuk komponen jaringan fondasi (VPC) dan komponen aplikasi yang sering berubah; pisahkan state per lapisan (*Layered State Architecture*).

---

## 15. Common Mistakes
1. **Menyimpan State S3 Tanpa Versioning**: Jika state file korup, tidak ada riwayat versi sebelumnya untuk rollback. Selalu aktifkan *S3 Bucket Versioning*.
2. **Hardcoding Nilai di Dalam Modul**: Menuliskan CIDR `10.0.0.0/16` langsung di dalam modul alih-alih menggunakan `variable "vpc_cidr"`, membuat modul tidak bisa digunakan ulang.
3. **Mengabaikan Drift Detection**: Membiarkan teknisi mengubah firewall atau security group di konsol cloud tanpa pernah mengimpornya kembali ke Terraform.

---

## 16. Best Practices
### Must Have
- Wajibkan Remote Backend dengan S3 encryption (`AES256`/`aws:kms`) dan DynamoDB locking.
- Gunakan struktur direktori terpisah untuk setiap environment (`dev/`, `staging/`, `prod/`).
- Pasang automated drift detection di pipeline CI terjadwal setiap malam.

### Recommended
- Gunakan *Semantic Versioning* pada modul Git (`source = "git::https://github.com/org/tf-modules.git//vpc?ref=v2.1.0"`).
- Lindungi S3 state bucket dengan IAM policy `DenyDelete` untuk mencegah penghapusan state yang fatal.

### Avoid / Overengineering
- Hindari nesting modul terlalu dalam (modul memanggil modul yang memanggil modul lain hingga 5 lapis); batasi maksimal 2 lapis abstraksi.

---

## 17. Troubleshooting
| Gejala | Kemungkinan Penyebab | Solusi |
|---|---|---|
| `Error acquiring the state lock: ConditionalCheckFailedException` | LockID masih tertinggal di DynamoDB akibat proses sebelumnya di-kill paksa | Verifikasi tidak ada apply lain yang berjalan, lalu jalankan `terraform force-unlock <LOCK-ID>` |
| `Error: Module not installed` | Modul baru ditambahkan di HCL tetapi belum diinisialisasi | Jalankan `terraform init` atau `terraform get -update` |
| Drift terdeteksi berulang pada tag resource | Provider cloud menambahkan tag otomatis (seperti tag AWS Cost Allocation) | Tambahkan blok `lifecycle { ignore_changes = [tags["aws:created-by"]] }` |

---

## 18. Exercise
1. Buat struktur folder modul Terraform: `modules/s3_secure_bucket` yang menerima variabel `bucket_name` dan secara otomatis mengaktifkan enkripsi AES-256.
2. Panggil modul tersebut dari folder `environments/dev/main.tf` dan verifikasi output nama bucket.

---

## 19. Challenge
Rancang arsitektur simulasi **State Locking & Drift Reconciler**:
- Simulasikan engine locking berbasis key-value mutex (mirip DynamoDB). Jika Lock sedang aktif, tolak permintaan apply berikutnya dengan status `423 Locked`.
- Simulasikan deteksi *Configuration Drift*: Jika atribut cloud diubah di luar Terraform, engine harus mampu mendeteksi selisihnya dan merekonsiliasi nilai cloud kembali ke spesifikasi HCL Git.

---

## 20. Summary
- Modul HCL menciptakan blok bangunan infrastruktur yang terstandarisasi, dapat diuji, dan dapat digunakan kembali (*reusable*).
- Remote backend dengan distributed locking mutlak diperlukan untuk mencegah tabrakan kolaborasi tim.
- Audit *drift detection* berkala menjaga integritas bahwa kode di Git adalah representasi akurat 100% dari infrastruktur cloud nyata.
- Modul praktikum lab dapat dijalankan langsung di [hands-on/m02/drift_detection_simulator.js](file:///d:/explore/roadmap.sh%20materi/DevOps/BAB-05-Infrastructure-as-Code-Terraform/hands-on/m02/drift_detection_simulator.js).
