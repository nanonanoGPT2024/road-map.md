# Bab 03: Evaluasi Pengetahuan & Praktik Arsitektur State

---

## 1. Basic Questions (5 Soal)

### Soal 1
Apa fungsi dari field `serial` dalam format schema JSON Terraform State?
A. Menunjukkan jumlah total resource yang dikelola oleh konfigurasi Terraform.  
B. Menentukan versi binary Terraform yang diizinkan untuk membuka state file tersebut.  
C. Bertindak sebagai integer monotonik yang bertambah setiap kali ada mutasi state untuk mencegah race condition / penulisan out-of-order.  
D. Menghitung jumlah kegagalan eksekusi apply yang terjadi sepanjang masa aktif project.  

**Kunci Jawaban:** C  
**Penjelasan Mendalam:**  
Field `serial` adalah counter bilangan bulat (*monotonically increasing integer*). Setiap kali Terraform berhasil melakukan mutasi pada state file (misal melalui `apply`, `refresh`, atau perintah `state`), nilai `serial` dinaikkan 1 angka. Backend menggunakan `serial` ini untuk optimistic concurrency checks; jika sebuah proses mencoba menulis state dengan nilai `serial` yang sama atau lebih rendah dari apa yang sudah tersimpan di remote backend, proses tersebut akan ditolak guna mencegah data terhapus/tertimpa (*lost update problem*).

---

### Soal 2
Komponen apa yang wajib ditambahkan pada backend AWS S3 agar Terraform dapat menjalankan mekanisme state locking secara terdistribusi?
A. Amazon SQS Queue  
B. Amazon DynamoDB Table dengan Hash Key bernama `LockID` bertipe String  
C. AWS KMS Customer Managed Key  
D. Amazon ElastiCache Redis Cluster  

**Kunci Jawaban:** B  
**Penjelasan Mendalam:**  
Backend `s3` pada Terraform memanfaatkan DynamoDB untuk mekanisme distributed locking. DynamoDB table tersebut wajib memiliki skema partisi/hash key tunggal bernama `LockID` dengan tipe String (`S`). Saat Terraform memulai operasi, sebuah item berisi metadata proses (ID, waktu, host) dimasukkan dengan kunci ini.

---

### Soal 3
Perintah CLI manakah yang digunakan untuk memisahkan sebuah resource yang dikelola Terraform agar tidak lagi dilacak dan tidak dihapus dari cloud provider saat `terraform destroy` dijalankan?
A. `terraform state delete <address>`  
B. `terraform destroy -target-exclude=<address>`  
C. `terraform state rm <address>`  
D. `terraform untrack <address>`  

**Kunci Jawaban:** C  
**Penjelasan Mendalam:**  
Perintah `terraform state rm` menghapus binding antara deklarasi HCL dan resource aktual di cloud provider dari dalam state file. Operasi ini **hanya** menghapus catatan pada state file tanpa memanggil API provider untuk menghancurkan objek fisik infrastruktur tersebut.

---

### Soal 4
Jika runner CI/CD mengalami crash fatal saat mengeksekusi `terraform apply`, dan pipeline berikutnya gagal dengan pesan `Error acquiring the state lock`, tindakan paling aman yang harus dilakukan pertama kali oleh SRE adalah:
A. Menghapus tabel DynamoDB dan membuatnya kembali.  
B. Menjalankan `terraform apply -lock=false` langsung ke server produksi.  
C. Memverifikasi bahwa proses runner sebelumnya benar-benar sudah terminated, membaca Lock ID dari log error, lalu menjalankan `terraform force-unlock <LOCK-ID>`.  
D. Menghapus S3 bucket tempat state disimpan dan mengunggahnya dari branch Git terakhir.  

**Kunci Jawaban:** C  
**Penjelasan Mendalam:**  
Mengeksekusi `force-unlock` tanpa memastikan status runner sebelumnya sangat berbahaya. Jika runner sebelumnya ternyata masih hidup dan sedang melakukan penulisan ke cloud, membuka kunci paksa akan menimbulkan race condition dan korupsi state. Maka, pastikan runner mati, lalu eksekusi `terraform force-unlock <LOCK-ID>`.

---

### Soal 5
Manakah pernyataan berikut yang BENAR mengenai penanganan data sensitif (misalnya password database atau TLS private key) di dalam Terraform State file standar?
A. Terraform secara otomatis melakukan hashing SHA-256 pada seluruh atribut sensitif sebelum menuliskannya ke state file.  
B. Data sensitif disimpan dalam format teks biasa (*plain-text*) di dalam JSON state file, sehingga kontrol keamanan bergantung pada enkripsi storage backend dan proteksi hak akses IAM.  
C. Terraform memblokir penulisan atribut sensitif ke remote backend dan hanya menyimpannya di RAM lokal operator.  
D. Flag `sensitive = true` pada variabel input akan mengenkripsi resource terkait di dalam state file.  

**Kunci Jawaban:** B  
**Penjelasan Mendalam:**  
Flag `sensitive = true` di HCL hanya menyembunyikan nilai dari tampilan visual `stdout`/log CLI. Di dalam state file (`.tfstate`), seluruh atribut disimpan dalam format JSON murni (*plain-text*). Oleh sebab itu, enkripsi di storage backend (SSE-KMS) dan kontrol hak akses IAM yang sangat ketat menjadi lapisan pertahanan absolut.

---

## 2. Intermediate Questions (5 Soal)

### Soal 1
Seorang DevOps Engineer melakukan refactoring kode HCL dengan memindahkan definisi resource `aws_instance.worker` ke dalam module baru `module.compute.aws_instance.worker`. Jika engineer tersebut langsung menjalankan `terraform apply` tanpa memodifikasi state terlebih dahulu, apa yang akan terjadi?
A. Terraform Engine cukup pintar untuk mendeteksi kesamaan atribut dan memperbarui state secara otomatis tanpa perubahan fisik.  
B. Terraform akan memunculkan syntax error karena nama resource identik tidak boleh ada di child module.  
C. Terraform akan merencanakan penghancuran (*destroy*) instance `aws_instance.worker` lama dan membuat (*create*) instance baru di bawah namespace `module.compute.aws_instance.worker`.  
D. Terraform akan menghentikan eksekusi dengan pesan "Lineage Mismatch Error".  

**Kunci Jawaban:** C  
**Penjelasan Mendalam:**  
Terraform memetakan konfigurasi HCL ke state berdasarkan resource address. Alamat `aws_instance.worker` berbeda dengan `module.compute.aws_instance.worker`. Tanpa perintah `terraform state mv` atau blok `moved {}` (Terraform 1.1+), Terraform menganggap deklarasi lama dihapus (trigger destroy) dan deklarasi baru ditambahkan (trigger create), yang memicu downtime pada infrastruktur produksi.

---

### Soal 2
Perhatikan potongan error berikut:
```text
Error: State lineage mismatch.
  Expected lineage 7a3c8e9b-4412-421e-8e6d-71b56a129031
  Got lineage d1b490f2-98ab-4122-83fe-491295b9c1aa
```
Penyebab utama munculnya error di atas saat menjalankan `terraform state push` adalah:
A. Format file JSON state rusak pada baris serialisasi pertama.  
B. File state lokal yang akan didorong berasal dari histori project infrastruktur yang berbeda sama sekali, bukan turunan dari state yang ada di backend.  
C. DynamoDB lock table sedang mengalami throttling rate-limit.  
D. Versi Terraform binary yang digunakan lokal lebih rendah dari versi binary remote.  

**Kunci Jawaban:** B  
**Penjelasan Mendalam:**  
UUID `lineage` di-generate sekali saat state pertama kali dibuat. Jika lineage pada backend remote dan lineage pada file yang ingin di-push via `terraform state push` tidak identik, ini menandakan bahwa kedua file tersebut merepresentasikan dua infrastruktur yang sama sekali berbeda. Terraform memblokir operasi ini secara default untuk mencegah insiden penimpaan (*overwriting*) state project lain secara tidak sengaja.

---

### Soal 3
Bagaimana Google Cloud Storage (GCS) Backend menangani state locking tanpa memerlukan layanan database tambahan seperti DynamoDB pada AWS?
A. GCS menggunakan file `.lock` sementara yang dibuat dan dihapus secara polling via Cloud Pub/Sub.  
B. GCS memanfaatkan fitur *Object Preconditions* dan *Generation Numbers* bawaan untuk mengimplementasikan atomisitas dan locking secara native.  
C. GCS backend tidak mendukung penguncian konkurensi sama sekali (*non-locking backend*).  
D. GCS backend mendelegasikan penguncian ke Google Cloud Spanner secara otomatis di background.  

**Kunci Jawaban:** B  
**Penjelasan Mendalam:**  
GCS memiliki dukungan built-in untuk transactional preconditions. GCS menggunakan parameter `if-generation-match` saat memperbarui objek state. Ketika lock diinisialisasi, Terraform membuat lock file khusus dengan memanfaatkan generation precondition. Jika generasi objek telah berubah (ada proses lain yang membuat atau memodifikasinya lebih dulu), request akan ditolak dengan error `HTTP 412 Precondition Failed`.

---

### Soal 4
Apa risiko paling kritis dari menjalankan perintah `terraform plan -lock=false` di lingkungan multi-developer atau CI/CD terotomatisasi?
A. Rencana plan akan mengabaikan pembacaan remote state dan langsung membuat file state baru di disk lokal.  
B. Meskipun tidak melakukan mutasi, plan membaca state saat proses lain sedang menulis state baru, berpotensi menghasilkan execution plan yang tidak akurat (*stale/dirty read*) atau memicu inkonsistensi refresh.  
C. Parameter `-lock=false` secara otomatis memaksa state file di S3 terenkripsi ulang dengan key default.  
D. Perintah tersebut akan menghapus ID unik pada DynamoDB lock table secara permanen.  

**Kunci Jawaban:** B  
**Penjelasan Mendalam:**  
Meskipun `terraform plan` secara default tidak menulis state perubahan resource, ia mengeksekusi *refresh* yang membaca state dan memperbarui data memori. Jika `-lock=false` diaktifkan saat proses lain sedang melakukan mutasi aktif via `apply`, plan akan membaca kondisi parsial (*dirty read*). Engineer yang mengeksekusi plan tersebut akan melihat gambaran infrastruktur yang tidak valid dan jika dilanjutkan ke tahap berikutnya dapat memicu kegagalan tak terduga.

---

### Soal 5
Pada Terraform 1.4+, HashiCorp memperkenalkan blok konfigurasi native `encryption`. Mengapa fitur ini dinilai lebih unggul dibandingkan hanya mengandalkan enkripsi bawaan storage provider (seperti AWS S3 SSE-KMS)?
A. Karena enkripsi bawaan S3 tidak mengenkripsi data saat transit melalui jaringan kabel AWS.  
B. Karena native encryption mengenkripsi data state langsung di dalam Terraform core memory sebelum diserialisasikan ke backend, melindungi data dari inspeksi transport layer dan unauthorized backend bucket storage administrators.  
C. Native encryption memadatkan ukuran JSON hingga 90% lebih kecil dibanding kompresi gzip.  
D. Native encryption menghapus kebutuhan akan IAM Role pada eksekusi CI/CD pipeline.  

**Kunci Jawaban:** B  
**Penjelasan Mendalam:**  
Storage Server-Side Encryption (SSE-KMS) mengenkripsi data *setelah* data sampai di storage S3. Artinya, payload dikirim dalam bentuk raw ke S3 endpoint, dan siapapun admin IAM yang memiliki permission `s3:GetObject` dan `kms:Decrypt` dapat melihat plain-text state. Native State Encryption mengenkripsi payload langsung di mesin klien/runner menggunakan algoritma seperti AES-GCM; data yang tiba dan disimpan di S3 sudah dalam bentuk ciphertext buram, memberikan kontrol keamanan end-to-end zero-trust.

---

## 3. Scenario-Based Questions (3 Kasus Nyata)

### Skenario 1: Pipeline Aborted Mid-Run & Terjadinya Stale Lock
**Konteks Masalah:**  
Pada pukul 02:00 dini hari, sebuah runner GitHub Actions yang mengeksekusi pipeline `terraform apply` untuk cluster database Amazon DocumentDB mengalami *Spot Instance Termination* mendadak dari cloud provider AWS. Pipeline mati seketika tanpa sempat menjalankan block `post-actions` untuk membersihkan penguncian backend.  
Pada pukul 08:00 pagi, deployment darurat tim Payment tertahan dengan error:
```text
Error: Error acquiring the state lock
Lock Info:
  ID:        57f0cb4b-cf83-149b-7ad3-a9d7010a30b2
  Path:      core-tfstate-ap-southeast-1/databases/terraform.tfstate
  Operation: OperationTypeApply
  Who:       runner@fv-az581-229
  Version:   1.8.5
  Created:   2025-01-15 02:00:15.823901 UTC
```
Seorang junior engineer menyarankan untuk langsung menjalankan `terraform force-unlock 57f0cb4b-cf83-149b-7ad3-a9d7010a30b2`.

**Pertanyaan Analitis:**  
1. Identifikasi dua risiko fatal jika rekomendasi engineer junior tersebut dijalankan tanpa verifikasi mendalam!
2. Rancang SOP (Standard Operating Procedure) 4 langkah sebelum perintah `force-unlock` boleh dieksekusi secara legal di lingkungan produksi!

**Kunci Solusi & Panduan Evaluasi:**  
1. **Risiko Fatal:**
   - *Split-Brain State Corruption:* Jika VM runner ternyata tidak mati total melainkan hanya mengalami *network partition* sementara dan masih mengeksekusi apply di background, melakukan force-unlock akan memicu runner baru masuk, sehingga dua proses menulis ke S3 secara bersamaan, merusak nomor `serial` dan memicu inkonsistensi state schema.
   - *Half-baked Infrastructure State:* DocumentDB instance mungkin sudah terbuat di AWS console namun belum tercatat di S3 state file karena runner mati sebelum penulisan state baru. Eksekusi apply berikutnya bisa gagal dengan error `ResourceAlreadyExistsException`.
2. **SOP 4 Langkah Mitigasi:**
   - **Langkah 1 (Audit Verifikasi Runner):** Buka konsol CI/CD (GitHub Actions) dan cloud console untuk memastikan VM runner instance `runner@fv-az581-229` telah berstatus `Terminated` dan tidak ada process Terraform yang hidup.
   - **Langkah 2 (Cloud Drift Inspection):** Buka AWS Console / CloudTrail pada rentang waktu `02:00 - 02:15 UTC` untuk memeriksa apakah ada API call `CreateDBInstance` yang sukses dibuat pada window waktu tersebut.
   - **Langkah 3 (State Pull & Backup):** Lakukan backup state offline saat ini menggunakan CLI: `terraform state pull > state-snapshot-pre-unlock.json`.
   - **Langkah 4 (Authorized Force-Unlock):** Jalankan perintah `terraform force-unlock 57f0cb4b-cf83-149b-7ad3-a9d7010a30b2`, kemudian jalankan `terraform plan` untuk melakukan reconcilation terhadap resource yang mungkin telah dibuat secara partial.

---

### Skenario 2: Refactoring Arsitektur Monolitik dengan Zero-Downtime
**Konteks Masalah:**  
Perusahaan Anda memiliki state monolitik `production.tfstate` yang memuat VPC (`aws_vpc.prod_vpc`), EKS Cluster (`aws_eks_cluster.prod_eks`), dan Aurora Database (`aws_rds_cluster.prod_db`). Manajemen menginstruksikan agar layer Database dipisahkan ke dalam repository dan state terpisah `database.tfstate` demi alasan regulasi audit keuangan dan isolasi blast radius.  
Jika Anda memotong blok HCL Aurora dari root module dan menaruhnya di repository baru, `terraform apply` di repo lama akan men-destroy database, dan `terraform apply` di repo baru akan gagal karena nama DB cluster sudah ada.

**Pertanyaan Analitis:**  
Rancang workflow CLI teknis step-by-step menggunakan kombinasi `terraform state pull`, `terraform state mv`, dan `terraform state push` untuk memindahkan `aws_rds_cluster.prod_db` ke state baru tanpa downtime sedikitpun pada database produksi!

**Kunci Solusi & Panduan Evaluasi:**  
Langkah-langkah teknis wajib mencakup:
1. **Freeze Execution:** Hentikan sementara seluruh trigger pipeline CI/CD pada repo monolitik.
2. **Tarik State Monolitik Lokal:**
   ```bash
   cd monolith-repo/
   terraform state pull > /tmp/monolith.tfstate
   cp /tmp/monolith.tfstate /tmp/monolith.tfstate.bak # Backup
   ```
3. **Ekstraksi Resource ke State Database Terpisah:**
   ```bash
   # Buat file state kosong yang valid untuk target
   terraform state mv \
     -state=/tmp/monolith.tfstate \
     -state-out=/tmp/database.tfstate \
     aws_rds_cluster.prod_db aws_rds_cluster.prod_db
   ```
   *(Opsional: Pindahkan juga child instance `aws_rds_cluster_instance` jika ada).*
4. **Push State Monolith yang Sudah Bersih:**
   ```bash
   terraform state push /tmp/monolith.tfstate
   # Hapus blok deklarasi aws_rds_cluster.prod_db dari kode HCL monolith
   terraform plan # Wajib menghasilkan 'No changes'
   ```
5. **Inisialisasi dan Push State ke Repository Baru:**
   ```bash
   cd ../database-repo/
   # Pastikan backend.tf baru mengarah ke key 'databases/database.tfstate'
   terraform init
   terraform state push /tmp/database.tfstate
   # Tambahkan kode deklarasi HCL aws_rds_cluster.prod_db di repo baru
   terraform plan # Wajib menghasilkan 'No changes. Your infrastructure matches configuration'
   ```
Hasil akhir: Aurora cluster tidak pernah terputus koneksinya, zero-downtime tercapai sempurna.

---

### Skenario 3: Penanganan Kebocoran Plain-Text Credentials pada State S3
**Konteks Masalah:**  
Sebuah audit keamanan mendeteksi bahwa resource `random_password.db_password` dan master password pada `aws_db_instance.app_db` terekam secara plain-text di file state S3 (`key = "apps/app.tfstate"`). Parahnya, bucket S3 tersebut memiliki hak baca yang terbuka luas ke seluruh grup developer internal melalui IAM policy `arn:aws:iam::123456789012:role/DeveloperAccess`.

**Pertanyaan Analitis:**  
Sebagai Principal Cloud Security Architect, berikan rencana perbaikan 3 dimensi:
1. **Dimensi IAM & Network Access:** Bagaimana konfigurasi policy bucket dan IAM role diubah seketika untuk menutup akses eksfiltrasi?
2. **Dimensi Terraform Secrets Handling:** Bagaimana mendesain ulang arsitektur kode agar secret tidak lagi di-generate via `random_password` atau plain-text HCL string?
3. **Dimensi State Sanitization:** Bagaimana membersihkan riwayat secret yang sudah terlanjur terekam pada snapshot versi-versi S3 Object Versioning sebelumnya?

**Kunci Solusi & Panduan Evaluasi:**  
1. **Dimensi IAM & Network:**
   - Terapkan S3 Bucket Policy eksplisit `Deny` untuk action `s3:GetObject` terhadap principal `DeveloperAccess`.
   - Batasi akses ke state bucket secara eksklusif hanya untuk CI/CD Runner IAM Role melalui `aws:PrincipalArn` dan enforce akses hanya dari dalam VPC Endpoint (`aws:sourceVpce`).
2. **Dimensi Terraform Code:**
   - Hapus resource `random_password` lokal.
   - Migrasikan manajemen kredensial ke AWS Secrets Manager dengan native integration: gunakan `manage_master_user_password = true` pada resource `aws_db_instance` (fitur AWS Aurora/RDS Secrets Manager integration).
   - Dengan pendekatan ini, AWS secara otomatis men-generate password langsung di sisi API control-plane, mengelola rotasinya, dan password **tidak pernah** dikirimkan kembali sebagai atribut plain-text ke Terraform state.
3. **Dimensi State Sanitization (S3 Versioning Cleanup):**
   - Lakukan rotasi manual terhadap password database saat ini via AWS Console/CLI agar kredensial lama di state menjadi usang (*invalidated*).
   - Jalankan `aws s3api list-object-versions` untuk mendata seluruh historical version ID dari file `apps/app.tfstate`.
   - Eksekusi `aws s3api delete-object --bucket <BUCKET> --key apps/app.tfstate --version-id <OLD_VERSION_ID>` secara programmatic pada versi-versi lama yang memuat plaintext password lama, menyisakan hanya versi state terbaru yang telah di-sanitize.

---

## 4. Practical Chapter Challenge
**Judul Challenge:** The Zero-Downtime State Extraction & Lock Resilience Gauntlet

### Deskripsi Tantangan
Anda diberikan sebuah lingkungan infrastruktur awal di mana sebuah state monolitik mengelola VPC, Security Group, dan sebuah Elastic Transcoder / SQS pipeline. Tugas Anda adalah mengimplementasikan arsitektur penguncian terdistribusi yang tangguh dan melakukan pemisahan state secara mutlak tanpa memicu destruksi infrastruktur.

### Tugas Teknis:
1. **Membangun Backend Fondasi Mandiri:**
   Tuliskan konfigurasi Terraform terpisah untuk membuat Bucket S3 (dengan versioning, KMS encryption, bucket policy deny non-TLS) dan DynamoDB Table (Partition key `LockID` string).
2. **Deploy Baseline Monolith:**
   Tuliskan kode Terraform dengan remote backend ke S3 + DynamoDB di atas, membuat:
   - 1 Virtual Private Cloud (`aws_vpc.foundation`)
   - 1 Security Group (`aws_security_group.infra_sg`)
   - 1 SQS Queue (`aws_sqs_queue.app_queue`)
3. **Simulasi Stale Lock Remediation:**
   Lakukan injeksi lock manual ke tabel DynamoDB menggunakan AWS CLI atau SDK untuk memblokir state path tersebut. Buktikan bahwa eksekusi `terraform plan` gagal menangkap lock. Kemudian pecahkan masalah tersebut menggunakan `terraform force-unlock` secara terkontrol.
4. **Operasi Bedah State (Extraction):**
   Tanpa menghancurkan resource di AWS:
   - Pindahkan `aws_sqs_queue.app_queue` keluar dari state monolitik ke state baru: `queues/terraform.tfstate`.
   - Update deklarasi HCL di kedua direktori project.
   - Buktikan bahwa `terraform plan` di folder monolith menghasilkan `0 to add, 0 to change, 0 to destroy`.
   - Buktikan bahwa `terraform plan` di folder queue menghasilkan `0 to add, 0 to change, 0 to destroy`.

### Kriteria Kelulusan:
- Seluruh eksekusi plan pasca-ekstraksi wajib menampilkan output: `Your infrastructure matches the configuration`.
- Tidak ada downtime atau recreate action pada resource SQS Queue.
- State file di S3 terenkripsi via AWS KMS dan versi historis terekam di Object Versioning.
- Log pengujian stale lock terdokumentasi rapi.