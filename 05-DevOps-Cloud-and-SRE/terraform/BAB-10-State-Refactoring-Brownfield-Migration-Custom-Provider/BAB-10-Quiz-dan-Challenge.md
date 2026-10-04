# Evaluasi Bab 10: State Refactoring, Brownfield Migration & Custom Provider

---

## I. Basic Questions (5 Soal)

### Soal 1
Apa perbedaan mendasar antara perintah imperatif `terraform import <address> <id>` dengan blok deklaratif `import {}` yang diperkenalkan pada Terraform 1.5+?
- **A.** Blok deklaratif `import {}` tidak memerlukan kredensial cloud provider saat dieksekusi.
- **B.** Blok deklaratif `import {}` memungkinkan peninjauan rencana impor melalui siklus standar `terraform plan` dan mendukung pembuatan kode otomatis dengan `-generate-config-out`.
- **C.** Perintah imperatif langsung menghapus resource jika terjadi perbedaan spesifikasi, sedangkan blok deklaratif menolak eksekusi.
- **D.** Blok deklaratif `import {}` hanya dapat digunakan untuk resource lokal dan tidak mendukung AWS, GCP, maupun Azure.

*Jawaban:* **B**  
*Penjelasan:* Blok deklaratif `import {}` mengintegrasikan proses adopsi resource brownfield langsung ke siklus planning engine Terraform, memungkinkan review PR kode dan pembuatan HCL otomatis.

---

### Soal 2
Kapan blok `moved` dievaluasi oleh Terraform Core selama siklus eksekusi perintah?
- **A.** Setelah resource baru berhasil dibuat di cloud provider.
- **B.** Saat fase *Provider Schema Validation*.
- **C.** Pada awal fase konstruksi dependency graph sebelum Terraform merefresh status resource ke API provider.
- **D.** Hanya ketika file backend state sedang di-unlock secara paksa.

*Jawaban:* **C**  
*Penjelasan:* Terraform membaca blok `moved` di awal perancangan dependency graph untuk memetakan ulang indeks address lama ke address baru sebelum mengevaluasi status fisik ke cloud API.

---

### Soal 3
Perintah Terraform CLI manakah yang digunakan untuk memindahkan resource secara aman dari satu file state lokal ke file state lokal lainnya saat memecah monolithic state?
- **A.** `terraform state rm`
- **B.** `terraform state mv -state=<source> -state-out=<dest> <source_addr> <dest_addr>`
- **C.** `terraform state push -split`
- **D.** `terraform state cp`

*Jawaban:* **B**  
*Penjelasan:* `terraform state mv` menerima flag `-state` (sumber) dan `-state-out` (tujuan) untuk memindahkan blok state antar file state yang berbeda secara atomik.

---

### Soal 4
Protokol komunikasi apa yang digunakan antara Terraform Core binary dengan plugin Custom Provider binary?
- **A.** REST API over HTTPS
- **B.** WebSocket
- **C.** gRPC over IPC / Local Unix Socket / Named Pipes
- **D.** Shared Memory Bus tanpa soket

*Jawaban:* **C**  
*Penjelasan:* Terraform Core dan plugin provider berjalan sebagai proses OS yang terpisah dan berkomunikasi secara lokal via protokol gRPC berkecepatan tinggi.

---

### Soal 5
Pada framework pengembangan modern `terraform-plugin-framework` di Golang, method manakah pada antarmuka `resource.Resource` yang dipanggil ketika resource dihapus dari deklarasi HCL?
- **A.** `Destroy()`
- **B.** `Purge()`
- **C.** `Remove()`
- **D.** `Delete()`

*Jawaban:* **D**  
*Penjelasan:* Siklus hidup CRUD pada `terraform-plugin-framework` mengimplementasikan method `Create()`, `Read()`, `Update()`, dan `Delete()`.

---

## II. Intermediate Questions (5 Soal)

### Soal 6
Sebuah tim merefaktorisasi konfigurasi EC2 instance dari penggunaan `count` ke `for_each`:
```hcl
# Lama:
resource "aws_instance" "server" {
  count = 2
  ...
}

# Baru:
resource "aws_instance" "server" {
  for_each = toset(["web", "api"])
  ...
}
```
Bagaimana sintaks blok `moved` yang benar agar kedua instance tersebut tidak dihancurkan dan dibuat ulang (*zero-destruction*)?
- **A.**
  ```hcl
  moved {
    from = aws_instance.server
    to   = aws_instance.server
  }
  ```
- **B.**
  ```hcl
  moved {
    from = aws_instance.server[0]
    to   = aws_instance.server["web"]
  }
  moved {
    from = aws_instance.server[1]
    to   = aws_instance.server["api"]
  }
  ```
- **C.**
  ```hcl
  moved {
    from = aws_instance.server[*]
    to   = aws_instance.server[each.key]
  }
  ```
- **D.**
  ```hcl
  moved {
    count    = aws_instance.server
    for_each = aws_instance.server
  }
  ```

*Jawaban:* **B**  
*Penjelasan:* Blok `moved` harus memetakan secara spesifik setiap elemen index lama (`[0]`, `[1]`) ke elemen key baru (`["web"]`, `["api"]`).

---

### Soal 7
Apa yang akan terjadi jika seorang engineer menambahkan blok deklaratif `import {}` untuk sebuah resource, tetapi resource target pada cloud provider ternyata sudah dihapus secara manual sebelumnya?
- **A.** Terraform secara otomatis membuat resource baru tersebut di cloud tanpa melempar error.
- **B.** Terraform menandai resource sebagai tainted di state file.
- **C.** `terraform plan` gagal dan mengembalikan error bahwa resource dengan ID tersebut tidak ditemukan pada API target.
- **D.** Terraform mengabaikan blok impor dan melanjutkan eksekusi resource lainnya secara silent.

*Jawaban:* **C**  
*Penjelasan:* Saat fase plan, blok `import` memerintahkan provider memanggil API `Read/Get`. Jika ID tidak ditemukan, Terraform menghasilkan error eksekusi.

---

### Soal 8
Pada pengembangan Custom Provider dengan Go, mengapa tipe data skema menggunakan `types.String` dan bukan tipe primitif bawaan Go `string`?
- **A.** Tipe primitif Go tidak kompatibel dengan arsitektur 64-bit modern.
- **B.** `types.String` mendukung representasi status tiga-nilai (*tri-state*): *Known*, *Unknown* (dihitung saat plan), dan *Null*.
- **C.** `types.String` secara otomatis mengenkripsi data string sebelum disimpan ke memori.
- **D.** `types.String` mengonversi seluruh string menjadi format HCL secara otomatis.

*Jawaban:* **B**  
*Penjelasan:* Terraform membutuhkan representasi status nilai apakah sebuah atribut bersifat `Null` (tidak diset), `Unknown` (nilainya baru diketahui setelah apply, misal ID atau IP), atau `Known` (berisi data konkrit). Tipe primitif Go biasa tidak dapat merepresentasikan kondisi *Unknown*.

---

### Soal 9
Mengapa membagi monolithic state file yang berisi 2.000 resource menjadi beberapa isolated state file dapat secara drastis mempercepat performa eksekusi CI/CD?
- **A.** Karena file state yang lebih kecil secara otomatis mengompresi payload via algoritma gzip.
- **B.** Mengurangi jumlah panggilan API refresh ke cloud provider hanya pada domain resource yang sedang dimodifikasi, serta mengurangi *lock contention*.
- **C.** Terraform tidak lagi membaca konfigurasi HCL saat state dipecah.
- **D.** Menyebabkan Terraform mengeksekusi apply tanpa melalui fase plan.

*Jawaban:* **B**  
*Penjelasan:* Pada monolithic state, Terraform Core harus memanggil API `Get/Describe` untuk seluruh 2.000 resource setiap kali plan/apply dijalankan. Membaginya menjadi state kecil membatasi query API ke resource yang relevan saja.

---

### Soal 10
File konfigurasi CLI manakah yang harus dikonfigurasi pada workstation lokal developer untuk mengalihkan (*override*) penyedia provider resmi ke binary Go kustom lokal untuk keperluan debugging?
- **A.** `terraform.tfstate`
- **B.** `.terraform.lock.hcl`
- **C.** CLI Configuration file (`~/.terraformrc` atau `terraform.rc`) menggunakan blok `provider_installation { dev_overrides { ... } }`.
- **D.** `provider.tf` menggunakan argument `source = "local/debug"`.

*Jawaban:* **C**  
*Penjelasan:* HashiCorp menyediakan mekanisme `dev_overrides` di dalam file konfigurasi Terraform CLI (`.terraformrc`) agar binary lokal dapat langsung digunakan tanpa validasi checksum lockfile.

---

## III. Scenario-Based Questions (3 Kasus Nyata)

### Skenario 1: Penanganan Refaktorisasi Module Tanpa Downtime Database Produksi
Sebuah tim SRE sedang merapikan kode Terraform. Resource RDS PostgreSQL `aws_db_instance.db_master` yang berada di root module ingin dipindahkan ke dalam sub-modul baru `module.database.aws_db_instance.this`. 

Seorang junior engineer langsung memindahkan blok resource HCL ke dalam folder modul tanpa menambahkan konfigurasi migrasi apapun. Saat CI/CD pipeline menjalankan `terraform plan`, output menunjukkan:
```
Plan: 1 to add, 0 to change, 1 to destroy.
- aws_db_instance.db_master
+ module.database.aws_db_instance.this
```

**Pertanyaan:**
1. Mengapa hal ini terjadi pada Terraform Core engine?
2. Tindakan perbaikan persis apa yang harus dilakukan sebelum kode di-apply ke produksi untuk menjamin database berkapasitas 4 TB tidak terhapus (*zero downtime*)?

*Jawaban Analitis:*
1. **Analisis Core Engine:** Terraform memetakan identitas resource berdasarkan namespace address uniknya di state. Ketika kode dipindahkan ke modul baru tanpa instruksi pemetaan, Terraform menganggap resource lama (`aws_db_instance.db_master`) telah dihapus dari kode sehingga harus di-destroy, dan menganggap resource baru (`module.database.aws_db_instance.this`) adalah objek baru yang harus di-provisioning.
2. **Langkah Perbaikan Zero Downtime:**
Tambahkan blok deklaratif `moved` pada file HCL (misal `migrations.tf`):
```hcl
moved {
  from = aws_db_instance.db_master
  to   = module.database.aws_db_instance.this
}
```
Saat `terraform plan` dijalankan ulang, Terraform Engine akan memperbarui pointer state address secara internal tanpa menyentuh instance fisik RDS di AWS, menghasilkan output:
`Plan: 0 to add, 0 to change, 0 to destroy.`

---

### Skenario 2: Bencana Brownfield Import VPC Peering
Sebuah organisasi mengakuisisi perusahaan startup yang memiliki infrastruktur AWS yang dibangun secara manual via AWS Management Console. Tim platform ditugaskan membawa VPC peering connection (`pcx-0123456789abcdef0`) ke dalam pengelolaan Terraform menggunakan blok deklaratif `import`.

Setelah membuat blok `import` dan blok resource `aws_vpc_peering_connection`, saat dieksekusi terjadi error:
`Error: Provider produced inconsistent result after apply. Attribute peer_owner_id was cty.NullVal, but now cty.StringVal("123456789012")`.

**Pertanyaan:**
Apa penyebab kegagalan konsistensi provider ini pada siklus import dan bagaimana strategi mitigasinya?

*Jawaban Analitis:*
- **Penyebab:** Kasus ini terjadi karena konfigurasi resource HCL yang ditulis manual tidak mendefinisikan atribut computed/optional tertentu yang secara otomatis diisi oleh API cloud provider saat resource live dibaca. Terraform mendeteksi ketidaksesuaian (*inconsistency*) antara rencana status awal (*prior state/plan*) dengan state nyata pasca pembacaan provider.
- **Mitigasi:**
  1. Manfaatkan generator otomatis bawaan Terraform 1.5+:
     `terraform plan -generate-config-out=generated_peering.tf`
  2. Terraform akan secara cerdas mengonstruksi seluruh atribut yang dibutuhkan langsung dari live API schema.
  3. Periksa file `generated_peering.tf`, pertahankan atribut required seperti `peer_vpc_id`, `vpc_id`, dan `auto_accept`, serta biarkan atribut komputasi internal dikelola oleh provider.
  4. Jalankan `terraform apply` untuk menyelesaikan registrasi brownfield secara bersih.

---

### Skenario 3: Race Condition dan State Lock Timeout saat Splitting State
Tim platform beranggotakan 20 SRE sering mengalami error `Error acquiring the state lock: ConditionalCheckFailedException` pada monolithic DynamoDB/S3 backend karena banyaknya pipeline deployment mikroservis yang berjalan paralel.

Diputuskan bahwa state harus dipecah menjadi beberapa domain: `networking`, `security`, `compute-apps`. Saat proses `terraform state mv` dijalankan secara manual oleh salah satu engineer dari terminal lokalnya, sebuah pipeline CI otomatis terpicu dan mengeksekusi `terraform apply` pada monolithic state yang sama di waktu bersamaan. Akibatnya, state mengalami korupsi data address ganda (*split-brain state*).

**Pertanyaan:**
Bagaimana protokol arsitektur standar enterprise untuk melakukan pemecahan state raksasa secara aman tanpa risiko race condition?

*Jawaban Analitis:*
1. **Lockout Pipeline:** Pasang status *Maintenance Mode* atau nonaktifkan webhook CI/CD yang terhubung ke backend monolithic tersebut untuk mencegah pipeline berjalan selama jendela pemeliharaan.
2. **Kunci State Monolith Eksplisit:** Jalankan `terraform force-unlock` hanya jika ada lock menggantung, lalu ambil lock eksklusif atau gunakan IAM deny policy sementara untuk semua role selain tim SRE yang melakukan migrasi.
3. **Backup Snapshot Offline:**
   `terraform state pull > backup_monolith_pre_split.tfstate`
4. **Isolasi Workspace:** Buat konfigurasi remote backend target yang baru terlebih dahulu (`networking`, `security`, `compute-apps`) lengkap dengan tabel DynamoDB state lock terpisah.
5. **Ekstraksi Atomik:**
   Gunakan flag isolasi file state:
   ```bash
   terraform state mv -state=monolith.tfstate -state-out=networking.tfstate <source_addr> <dest_addr>
   ```
6. **Push & Verifikasi:** Unggah state baru ke backend masing-masing (`terraform state push`), jalankan `terraform plan` di setiap direktori baru, dan pastikan seluruh diff bernilai zero. Buka kembali akses pipeline CI/CD dengan backend terisolasi masing-masing.

---

## IV. Practical Chapter Challenge

### Judul Tantangan:
**Enterprise Infrastructure Reconstruction: Brownfield Absorption, Dynamic Refactoring & Custom Internal API Provider**

### Deskripsi Masalah:
Perusahaan Anda memiliki sistem internal bernama **Fleet Control API** (sebuah API kustom untuk mendaftarkan nama domain internal dan alokasi kuota gateway). Selama ini sistem tersebut dikonfigurasi via Bash curl scripts. Pada saat yang sama, tim infrastruktur memiliki cluster EC2 historis yang dibuat manual di AWS dan ingin dimodernisasi ke dalam Terraform module tanpa downtime.

### Persyaratan Tugas:

#### Bagian A: Custom Provider (Golang)
1. Rancang sebuah Custom Provider sederhana berbasis `terraform-plugin-framework` di Go dengan nama `provider-fleet`.
2. Provider harus mengekspos resource bernama `fleet_domain`:
   - Atribut Required: `domain_name` (String), `target_ip` (String), `quota_mb` (Int64).
   - Atribut Computed: `id` (String), `status` (String).
3. Implementasikan handler:
   - `Create`: Membuat data (simulasikan in-memory map), set `id = "flt-" + domain_name`, set `status = "ACTIVE"`.
   - `Read`: Membaca data dari memory. Jika tidak ada, remove dari state.
   - `Delete`: Menghapus data dari memory.

#### Bagian B: Brownfield Import & Refactoring HCL
1. Buat file `legacy_instances.tf` yang mensimulasikan resource brownfield instance AWS:
   - Resource target: `aws_instance.legacy_node`.
   - Lakukan impor deklaratif menggunakan blok `import` (Terraform 1.5+) untuk ID `i-0987654321fedcba0`.
2. Refaktorisasi konfigurasi tersebut ke dalam modul:
   - Buat sub-modul lokal `./modules/compute`.
   - Pindahkan resource ke dalam sub-modul tersebut dengan address: `module.compute.aws_instance.worker["node-1"]`.
   - Tulis blok `moved` deklaratif yang memetakan `aws_instance.legacy_node` ke `module.compute.aws_instance.worker["node-1"]`.
3. Integrasikan resource `fleet_domain` dari custom provider pada modul tersebut untuk mendaftarkan IP instance ke Fleet Control API.

### Kriteria Kelulusan Evaluasi:
1. Kode Go custom provider berhasil dikompilasi tanpa syntax error.
2. File deklarasi HCL lulus validasi `terraform validate`.
3. Seluruh alur deklarasi migrasi (`import` dan `moved`) terbukti menghasilkan rencana idempotensi zero-destruction pada simulasi graph.