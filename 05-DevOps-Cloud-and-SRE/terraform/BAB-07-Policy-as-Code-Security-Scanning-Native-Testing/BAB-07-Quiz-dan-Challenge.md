# Evaluasi Bab 07: Policy-as-Code, Security Scanning & Native Testing

Dokumen ini berisi pengujian pemahaman konsep dan kemampuan terapan terkait materi *Policy-as-Code*, analisis keamanan statis (Checkov & Trivy), serta framework pengujian native Terraform (`terraform test`).

---

## Bagian 1: Basic Questions (Pilihan Ganda / Teori Singkat)

### Soal 1
Perintah manakah yang benar untuk mengekspor execution plan Terraform ke dalam format JSON terstruktur yang dapat dipahami oleh Open Policy Agent (OPA)?
- A. `terraform plan -format=json > tfplan.json`
- B. `terraform plan -out=tfplan.binary && terraform show -json tfplan.binary > tfplan.json`
- C. `terraform export -json -output=tfplan.json`
- D. `terraform convert-plan --in=tfplan --out=tfplan.json`

### Soal 2
Pada Terraform Native Testing Framework (v1.6+), ekstensi file konvensional yang digunakan untuk mendeklarasikan blok pengujian otomatis adalah:
- A. `.tfspec`
- B. `.test.tf`
- C. `.tftest.hcl`
- D. `.tftest.json`

### Soal 3
Apa perbedaan mendasar antara mode eksekusi `command = plan` dan `command = apply` di dalam blok `run` pada file native test Terraform?
- A. `command = plan` menguji sintaksis HCL saja, sedangkan `command = apply` menguji OPA.
- B. `command = plan` menjalankan validasi tanpa memanggil API cloud untuk provisi fisik (dapat dipadukan dengan `mock_provider`), sedangkan `command = apply` membuat resource aktual pada infrastruktur target lalu membersihkannya (*teardown*).
- C. `command = plan` hanya berjalan di lingkungan Windows, sedangkan `command = apply` di lingkungan Linux.
- D. `command = plan` bersifat imperatif, sedangkan `command = apply` bersifat deklaratif.

### Soal 4
Di dalam file `tfplan.json`, blok data manakah yang paling krusial untuk dianalisis oleh OPA Rego guna memeriksa perubahan konfigurasi yang diusulkan oleh seorang developer?
- A. `format_version`
- B. `terraform_version`
- C. `resource_changes`
- D. `configuration.provider_config`

### Soal 5
Bagaimana cara menonaktifkan aturan keamanan tertentu (misalnya aturan `CKV_AWS_20`) secara legal langsung pada baris kode Terraform saat menggunakan Checkov?
- A. Menambahkan baris `#checkov:skip=CKV_AWS_20:Alasan justifikasi yang valid` di dalam blok resource terkait.
- B. Menggunakan flag `--ignore CKV_AWS_20` langsung pada terminal global.
- C. Menghapus konfigurasi provider.
- D. Mengubah nama resource menjadi `legacy_resource`.

---

## Bagian 2: Intermediate Questions

### Soal 6
Jelaskan mengapa atribut resource pada `change.after_unknown` di dalam `tfplan.json` dapat menyebabkan policy OPA menghasilkan evaluasi yang keliru (*false positive* atau *false negative*), dan bagaimana strategi penanganannya di Rego!

### Soal 7
Perhatikan potongan kode Rego berikut:
```rego
package terraform.s3

deny[msg] {
    some res in input.resource_changes
    res.type == "aws_s3_bucket"
    res.change.after.bucket_prefix == ""
    msg := "S3 Bucket wajib memiliki bucket_prefix!"
}
```
Sebutkan satu kelemahan fatal dari aturan di atas jika diaplikasikan pada konfigurasi Terraform yang menggunakan atribut statis `bucket` alih-alih `bucket_prefix`!

### Soal 8
Bagaimana cara kerja blok `mock_provider` pada `terraform test`? Sebutkan kelebihan dan batasannya dalam skenario pengujian infrastruktur!

### Soal 9
Dalam konteks integrasi CI/CD, apa fungsi parameter exit code pada kakas seperti Trivy (`--exit-code 1`) atau Checkov (`--soft-fail`), dan kapan Anda harus mengaktifkan *soft-fail*?

### Soal 10
Bandingkan kakas pemindai keamanan Checkov dan Trivy IaC. Kriteria teknis apa yang Anda gunakan untuk memilih salah satu dari kedua kakas tersebut di dalam pipeline produksi?

---

## Bagian 3: Scenario-Based Questions

### Kasus 1: Insiden Kebocoran Port Database RDS
Sebuah tim pengembang meluncurkan modul baru untuk AWS RDS Aurora. Secara tidak sengaja, variabel `publicly_accessible` diatur ke nilai `true` dan security group yang terpasang mengizinkan port `3306` dari subnet mana pun. Kakas Trivy berhasil mendeteksi celah ini di PR pipeline, namun developer menambahkan komentar *skip* pemindaian dan melakukan bypass ke branch utama.
- **Pertanyaan:** Rancang arsitektur tata kelola berlapis (*multi-layer guardrails*) yang mengombinasikan OPA di pipeline CI dan *Branch Protection* di Git repository agar insiden *suppression bypass* sepihak semacam ini mustahil terulang!

### Kasus 2: Kegagalan Pengujian Modul Komputasi Lintas Region
Modul Terraform Anda menggunakan `for_each` untuk memetakan alokasi subnet di 3 Availability Zone (AZ). Saat menjalankan `terraform test` dengan `command = apply` di CI/CD, pengujian sering gagal dengan pesan error `VcpuLimitExceeded` dari cloud provider karena kuota akun pengujian terbatas.
- **Pertanyaan:** Bagaimana Anda merefaktor struktur pengujian `.tftest.hcl` Anda agar tetap dapat memvalidasi kalkulasi logika pembagian CIDR subnet secara mendalam tanpa harus mengonsumsi kuota vCPU aktual dan tanpa mengeluarkan biaya infrastruktur?

### Kasus 3: OPA Policy Terlalu Ketat Memblokir Pembaruan Produksi
Sebuah kebijakan OPA melarang seluruh perubahan yang menghapus sumber daya (`"delete" in change.actions`). Namun, tim SRE perlu melakukan rotasi sertifikat SSL pada modul CloudFront dan ALB yang secara alamiah mengharuskan re-koneksi (*replacement / create-before-destroy*). Pipeline terblokir total oleh OPA.
- **Pertanyaan:** Tuliskan modifikasi logika evaluasi Rego agar mampu membedakan antara aksi murni penghapusan berbahaya (*accidental deletion*) dan aksi penggantian terkontrol (*replacement cycle*: `["create", "delete"]` atau `["delete", "create"]`) dengan pengecualian khusus untuk tag atau resource tertentu!

---

## Bagian 4: Practical Chapter Challenge

### Judul Tantangan
**Pembangunan Automated Enterprise IaC Testing & Compliance Framework**

### Deskripsi Masalah
Organisasi FinTech Anda mewajibkan setiap modul Terraform memenuhi standar keamanan ketat sebelum didaftarkan ke Private Module Registry:
1. **Pencegahan Enkripsi Tidak Standar:** Seluruh resource penyimpanan (`aws_s3_bucket`, `aws_ebs_volume`, `aws_dynamodb_table`) WAJIB dienkripsi menggunakan AWS KMS Customer Managed Key (CMK), dilarang menggunakan kunci bawaan AWS (`aws/s3`, `aws/ebs`).
2. **Kepatuhan Tagging Korporat:** Setiap resource yang mendukung tagging harus memiliki minimal 3 tag: `Environment`, `OwnerEmail` (harus berakhiran `@fintech-corp.com`), dan `CostCenter` (format regex: `CC-[0-9]{4}`).
3. **Uji Fungsional Modul:** Modul VPC privat internal harus diuji menggunakan `terraform test` untuk memastikan kalkulasi CIDR blok subnet privat tidak tumpang tindih (*non-overlapping*) dengan subnet publik.

### Kriteria Penyelesaian
1. Buat direktori proyek lengkap yang memuat file Terraform modul VPC & S3.
2. Buat file `.tftest.hcl` dengan skenario validasi fungsional menggunakan `mock_provider`.
3. Tulis aturan OPA Rego (`enterprise_rules.rego`) yang mengevaluasi `tfplan.json` dan memaksakan persyaratan enkripsi CMK dan validasi regex tag di atas.
4. Buat file eksekusi pipeline mandiri (shell script atau skrip Python) yang menjalankan validasi berurutan: `terraform test` $\rightarrow$ `plan export` $\rightarrow$ `OPA enforcement`, dan mengembalikan status sukses (exit code 0) atau gagal (exit code 1).