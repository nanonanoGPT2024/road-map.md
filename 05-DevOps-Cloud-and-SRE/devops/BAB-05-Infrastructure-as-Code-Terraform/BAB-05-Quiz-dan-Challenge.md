# BAB 05: Quiz, Challenge, & Knowledge Check
**Infrastructure as Code (IaC) dengan Terraform & OpenTofu**

---

## 1. Basic Questions (5 Soal)
1. Apa perbedaan mendasar antara pendekatan pengelolaan infrastruktur *Imperatif* (scripting langkah-demi-langkah) dan *Deklaratif* (Terraform/OpenTofu)?
2. Mengapa file `terraform.tfstate` disebut sebagai *Single Source of Truth* dalam ekosistem Terraform?
3. Apa perbedaan fungsi antara perintah `terraform plan` dan `terraform apply`?
4. Mengapa menyimpan file `terraform.tfstate` di repository Git publik merupakan pelanggaran fatal standar keamanan?
5. Apa peran tabel **DynamoDB State Locking** saat Terraform menggunakan remote backend AWS S3?

---

## 2. Intermediate Questions (5 Soal)
6. Bagaimana blok `lifecycle { prevent_destroy = true }` bekerja untuk melindungi resource database dari penghapusan yang tidak disengaja?
7. Apa yang dimaksud dengan fenomena **Configuration Drift**, dan bagaimana cara mendeteksinya menggunakan perintah `terraform plan -refresh-only`?
8. Mengapa pendekatan pemisahan environment berbasis direktori (`environments/dev` dan `environments/prod`) lebih direkomendasikan untuk sistem enterprise dibandingkan sekadar menggunakan Terraform Workspaces?
9. Bagaimana cara Terraform membangun graf ketergantungan antar-resource (*Directed Acyclic Graph / DAG*), dan bagaimana graf tersebut memungkinkan pembuatan resource secara paralel?
10. Bagaimana cara memperbaiki insiden ketika Terraform gagal mengeksekusi apply akibat error `Error acquiring the state lock: ConditionalCheckFailedException`?

---

## 3. Scenario-Based Questions (3 Soal)

### Skenario A: The Accidental Database Replacement Disaster
Seorang engineer mengubah nama identifier database RDS di file HCL: `identifier = "prod-db"` menjadi `identifier = "prod-db-v2"`. Karena RDS identifier bersifat *Forces Replacement*, saat `terraform apply -auto-approve` dijalankan, Terraform menghancurkan database lama sebelum membuat yang baru, menyebabkan data jutaan pengguna terhapus.
- *Pertanyaan:* Pengaturan lifecycle apa yang dapat mencegah kejadian ini, dan bagaimana prosedur yang benar jika memang harus mengganti resource stateful tanpa kehilangan data?

### Skenario B: The 2 Engineers Concurrent Apply Race Condition
Dua engineer di tim Anda (Engineer A dan Engineer B) secara tidak sengaja menekan tombol *Deploy Infrastructure* di pipeline CI/CD pada menit yang sama untuk environment yang sama.
- *Pertanyaan:* Tanpa adanya distributed locking di remote backend, apa bencana yang bisa menimpa file `terraform.tfstate`, dan bagaimana DynamoDB menyelesaikan *race condition* tersebut?

### Skenario C: The Phantom Cloud Firewall Hole
Saat terjadi gangguan jaringan darurat, seorang SysAdmin masuk ke konsol AWS dan menambahkan aturan security group: `Allow 0.0.0.0/0 on Port 22 (SSH)`. Tiga bulan kemudian, lubang firewall ini masih terbuka dan tidak ada di file Git Terraform.
- *Pertanyaan:* Bagaimana strategi deteksi drift otomatis yang terintegrasi di pipeline CI/CD harian untuk mendeteksi anomali ini dan merekonsiliasi aturan firewall kembali ke kode Git?

---

## 4. Chapter Challenge
**Tantangan Praktis: The Secure Enterprise VPC Module**
Rancang sebuah arsitektur Terraform modular:
1. **Modul VPC (`modules/vpc`)**:
   - Menerima variabel `cidr_block`, `environment`, dan `az_count`.
   - Membuat Public Subnet dan Private Subnet dengan routing table terpisah.
   - Mengembalikan output `vpc_id` dan `private_subnet_ids`.
2. **Root Configuration (`environments/prod/main.tf`)**:
   - Mengonfigurasi Remote Backend S3 terenkripsi dengan DynamoDB lock.
   - Memanggil modul VPC dengan CIDR `10.100.0.0/16`.
   - Menguji pembuatan *execution plan* dan memverifikasi proteksi `prevent_destroy`.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Paradigma Declarative IaC dan sintaks HashiCorp Configuration Language (HCL).
- [ ] Peran dan anatomi file `terraform.tfstate`.
- [ ] Mekanisme Remote Backend dengan S3 encryption dan DynamoDB distributed locking.
- [ ] Arsitektur modular Terraform untuk standarisasi multi-environment.
- [ ] Konsep Configuration Drift dan strategi deteksi rekonsiliasinya.

### Saya tidak perlu menghafal:
- [ ] Ratusan parameter spesifik ribuan provider cloud pihak ketiga (cukup baca dokumentasi resmi Terraform Registry).
- [ ] Format internal skema biner state lock DynamoDB.

### Saya harus bisa melakukan:
- [ ] Menulis file HCL yang modular, rapi (`terraform fmt`), dan tervalidasi (`terraform validate`).
- [ ] Menjalankan simulasi `plan` dan menginterpretasikan tanda `+`, `~`, `-`.
- [ ] Mencegah penghapusan database bencana dengan `prevent_destroy`.

---
*Ketik **LANJUT** untuk berpindah ke BAB 06: Configuration Management & Server Provisioning (Ansible).*
