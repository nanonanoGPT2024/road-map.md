# Bab 08: Evaluasi Pemahaman & Tantangan Praktika
## Cloud Security, Governance & Regulatory Compliance

---

### A. Basic Questions (5 Soal)

#### 1. Manakah pernyataan yang paling tepat mengenai cara kerja Service Control Policies (SCPs) di AWS Organizations?
A. SCP memberikan izin langsung (*allow*) kepada IAM role di akun anggota secara eksplisit tanpa memerlukan IAM Policy lokal.  
B. SCP menetapkan batas izin maksimum (*guardrail boundary*) dan tidak pernah memberikan izin secara mandiri kepada user atau role.  
C. SCP hanya dapat diaplikasikan pada level Root dan tidak dapat dipasang pada tingkat Organizational Unit (OU).  
D. IAM Administrator di member account dapat meng-override restriksi yang ditetapkan oleh SCP jika menggunakan role `AdministratorAccess`.  
**Kunci Jawaban:** B  
**Pembahasan:** SCP berfungsi sebagai guardrail batas izin maksimum (*filter/boundary*). SCP tidak memberikan izin; user/role di akun anak tetap memerlukan IAM permission. Bahkan akun root dan IAM administrator di member account tunduk pada restriksi SCP.

---

#### 2. Pada arsitektur Envelope Encryption dengan AWS KMS, mengapa Plaintext Data Key harus segera dihapus dari memori aplikasi setelah proses enkripsi data selesai?
A. Karena jika Plaintext Data Key tidak dihapus, KMS API akan mengenakan denda komputasi per jam.  
B. Agar Plaintext Data Key otomatis tersinkronisasi ke S3 bucket.  
C. Untuk memastikan bahwa data mentah hanya dapat didekripsi jika penyerang memiliki akses ke Ciphertext Data Key dan izin IAM/KMS untuk memanggil API `kms:Decrypt`.  
D. Karena Plaintext Data Key secara otomatis mengubah Ciphertext Data menjadi korup jika dibiarkan di memori lebih dari 60 detik.  
**Kunci Jawaban:** C  
**Pembahasan:** Tujuan utama Envelope Encryption adalah keamanan data *in-memory*. Setelah enkripsi lokal selesai, Plaintext Data Key wajib dihapus (*zeroed out*). Penyerang yang melakukan memory dump tidak akan mendapatkan kunci terbuka; hanya Ciphertext Data Key yang tersimpan bersama data, yang memerlukan autentikasi KMS untuk membukanya kembali.

---

#### 3. Sumber telemetri default manakah yang dianalisis oleh Amazon GuardDuty tanpa memerlukan instalasi agent pada instans EC2 target?
A. `/var/log/messages`, `/var/log/auth.log`, dan Syslog sistem operasi.  
B. VPC Flow Logs, DNS Query Logs, dan AWS CloudTrail Event Logs.  
C. Apache Access Logs dan NGINX Error Logs.  
D. Docker Container stdout and stderr logs.  
**Kunci Jawaban:** B  
**Pembahasan:** Amazon GuardDuty adalah layanan threat detection tanpa agent (*agentless*). GuardDuty membaca dan menganalisis stream data langsung dari control plane AWS: VPC Flow Logs, DNS Query Logs, dan AWS CloudTrail Event/Management Logs.

---

#### 4. Fitur apakah pada AWS Secrets Manager yang membedakannya secara signifikan dari AWS Systems Manager Parameter Store standar?
A. Dukungan enkripsi menggunakan AWS KMS.  
B. Dukungan format output JSON dan Plaintext.  
C. Kemampuan native rotasi kredensial otomatis terjadwal menggunakan AWS Lambda.  
D. Kemampuan diakses secara private melalui VPC Endpoints.  
**Kunci Jawaban:** C  
**Pembahasan:** Meskipun keduanya dapat menggunakan KMS dan diakses via PrivateLink, perbedaan kunci Secrets Manager adalah integrasi out-of-the-box untuk rotasi otomatis kredensial (misalnya database RDS) via Lambda function secara berkala tanpa downtime aplikasi.

---

#### 5. Apa fungsi utama dari AWS Config Conformance Packs?
A. Memblokir serangan DDoS Layer 7 menggunakan machine learning.  
B. Mengelompokkan sekumpulan AWS Config Rules dan dokumen remediasi ke dalam satu template tunggal untuk deployment kepatuhan regulasi terpusat di multi-account.  
C. Menggantikan seluruh peran IAM Identity Center dalam mengelola autentikasi pengguna.  
D. Mengenkripsi EBS volumes secara real-time saat transfer data antar availability zone.  
**Kunci Jawaban:** B  
**Pembahasan:** Conformance Packs adalah template terkelola CloudFormation yang merangkum aturan kepatuhan (Config Rules) dan aksi perbaikan (Remediation) yang dipetakan ke kerangka kepatuhan regulasi tertentu (seperti PCI-DSS, CIS Benchmarks) agar dapat didistribusikan secara masif di level organisasi.

---

### B. Intermediate Questions (5 Soal)

#### 6. Sebuah aplikasi di akun Production membutuhkan akses dekripsi Customer Managed Key (CMK) yang berada di akun Security. Pengaturan otorisasi apa saja yang wajib dipenuhi agar proses dekripsi berhasil?
A. Cukup menambahkan policy `kms:Decrypt` pada IAM Role di akun Production.  
B. Cukup menambahkan IAM Role akun Production pada Key Policy CMK di akun Security.  
C. Wajib mengonfigurasi Key Policy CMK di akun Security untuk mempercayai akun Production, DAN menambahkan IAM Policy pada IAM Role di akun Production untuk mengizinkan aksi `kms:Decrypt` ke resource ARN CMK tersebut.  
D. Membuat Service Control Policy di tingkat Root yang mengizinkan aksi `kms:*` untuk semua akun.  
**Kunci Jawaban:** C  
**Pembahasan:** Untuk cross-account KMS access, otorisasi membutuhkan kesepakatan dua arah (*two-way handshake*): (1) KMS Key Policy di akun penyimpan key harus mengizinkan akun/role pemanggil, DAN (2) IAM Policy pada IAM Identity di akun pemanggil harus mengizinkan aksi KMS pada ARN key tersebut.

---

#### 7. Tim DevOps mengaktifkan AWS WAF dengan managed rule `AWSManagedRulesSQLiRuleSet` pada Application Load Balancer. Beberapa request POST valid dari klien terblokir dengan HTTP 403. Langkah mitigasi awal terbaik tanpa mengorbankan postur keamanan sistem secara drastis adalah:
A. Menghapus managed rule `AWSManagedRulesSQLiRuleSet` secara permanen dari Web ACL.  
B. Mengubah status rule spesifik yang memicu pemblokiran di dalam Managed Rule Group menjadi "Override to Count", lalu menganalisis log CloudWatch/sampled requests.  
C. Menonaktifkan WAF pada ALB dan mengandalkan AWS Shield Standard.  
D. Mengubah Default Action pada Web ACL menjadi Block.  
**Kunci Jawaban:** B  
**Pembahasan:** Mengubah rule bermasalah ke status `Override to Count` mempertahankan evaluasi metriks tanpa memutus aliran data pengguna (menghilangkan false positive seketika). Tim dapat menganalisis pola request di log dan mendesain Custom Rule Exception sebelum memutuskan konfigurasi final.

---

#### 8. Bagaimana AWS Shield Advanced memberikan proteksi finansial (*DDoS Cost Protection*) bagi perusahaan yang terkena serangan DDoS berskala besar?
A. Membayar uang ganti rugi secara tunai untuk kerugian reputasi bisnis.  
B. Memberikan credit refund atas lonjakan tagihan tak terduga pada resource yang diproteksi (seperti penskalaan kapasitas EC2/ALB/CloudFront) yang disebabkan langsung oleh serangan DDoS.  
C. Menghapus seluruh tagihan AWS untuk bulan berjalan di mana serangan terdeteksi.  
D. Menurunkan tarif dasar per-GB transfer data CloudFront hingga 90% secara permanen.  
**Kunci Jawaban:** B  
**Pembahasan:** DDoS Cost Protection dari AWS Shield Advanced melindungi pelanggan dari spike billing akibat auto-scaling resource (misal penambahan instans EC2 di belakang ALB atau lonjakan CloudFront Request) yang terpaksa melayani traffic DDoS, melalui pengajuan refund credit ke AWS support.

---

#### 9. Anda ingin memastikan bahwa semua bucket S3 baru dan lama di seluruh organisasi tidak dapat diakses secara publik. Kombinasi kontrol preventif dan direktif apa yang paling efektif?
A. Menjalankan skrip Python manual setiap malam untuk memeriksa izin bucket.  
B. Menerapkan SCP yang memblokir API call `s3:PutBucketPublicAccessBlock` jika bernilai false, dipadukan dengan AWS Config Rule `s3-bucket-public-read-prohibited` dan auto-remediation.  
C. Menghapus seluruh Internet Gateway dari semua VPC.  
D. Mengaktifkan Amazon GuardDuty dan mengandalkan email notifikasi harian.  
**Kunci Jawaban:** B  
**Pembahasan:** Kombinasi SCP (preventive guardrail) mencegah pelepasan kontrol Block Public Access di tingkat API, sementara AWS Config (detective and corrective guardrail) mendeteksi dan secara otomatis memulihkan bucket yang tidak compliant melalui remediation action.

---

#### 10. Mengapa AWS Key Management Service (KMS) membatasi ukuran data yang dapat dienkripsi secara langsung melalui pemanggilan API `kms:Encrypt` maksimum sebesar 4 KB?
A. Karena arsitektur hardware HSM tidak memiliki memori internal yang cukup.  
B. Untuk mendorong adopsi pola Envelope Encryption, mengeliminasi bottleneck throughput jaringan, dan mencegah latency tinggi akibat transmisi file biner besar ke KMS endpoint.  
C. Karena algoritma AES-256 tidak dapat mengenkripsi payload di atas 4 Kilobyte.  
D. Sebagai batasan komersial agar pelanggan beralih membeli hardware AWS CloudHSM mandiri.  
**Kunci Jawaban:** B  
**Pembahasan:** Limit 4 KB dirancang secara sengaja untuk alasan performa dan skalabilitas jaringan. Mentransmisikan payload besar ke KMS API akan membebani jaringan dan HSM. Dengan Envelope Encryption, enkripsi data besar dilakukan secara lokal di memori aplikasi klien, sedangkan KMS hanya memproses enkripsi/dekripsi data key yang berukuran kecil (ratusan byte).

---

### C. Scenario-Based Questions (3 Soal Kasus Nyata)

#### Skenario 1: Serangan Akun Terkompromi & Evasi Deteksi
Sebuah startup fintech mendapati bahwa salah satu kredensial developer IAM User mereka bocor di internet. Penyerang masuk ke AWS Management Console akun Production pada pukul 03.00 AM dari IP address tak dikenal di Eropa Timur. Penyerang langsung mencoba mematikan AWS CloudTrail trail untuk menghapus jejak, lalu membuat 50 instans EC2 berukuran besar (`g5.48xlarge`) untuk aktivitas crypto mining.
- **Pertanyaan:** Arsitektur governance dan deteksi multi-layer seperti apa yang seharusnya didesain sejak awal untuk (1) mencegah penonaktifan CloudTrail secara preventif, dan (2) mendeteksi serta menghentikan provisioning instans liar tersebut secara otomatis?
- **Analisis & Solusi:**
  1. **Layer Preventif (AWS Organizations SCP):** Diterapkan SCP pada OU Production yang secara eksplisit menolak (`Deny`) aksi `cloudtrail:StopLogging`, `cloudtrail:DeleteTrail`, dan `cloudtrail:UpdateTrail`. Dengan SCP ini, meskipun user memiliki permission `AdministratorAccess`, usaha menonaktifkan trail akan langsung ditolak oleh control plane AWS.
  2. **Layer Deteksi (Amazon GuardDuty):** GuardDuty secara otomatis mendeteksi anomali perilaku login dari lokasi tak lazim (`UnauthorizedAccess:IAMUser/ConsoleLoginSuccess.UnusualLocation`) dan provisioning resource komputasi yang tidak wajar (`CryptoCurrency:EC2/BitcoinMining.B`).
  3. **Layer Remediasi (EventBridge + Lambda):** GuardDuty mempublikasikan finding dengan severity High ke Amazon EventBridge. EventBridge Rule memicu AWS Lambda function yang secara otomatis: (a) me-revoke seluruh active session IAM user terkait dan memasang inline deny policy, dan (b) memanggil EC2 API untuk me-terminate instans `g5.48xlarge` yang baru dibuat.

---

#### Skenario 2: Kepatuhan Regulasi Data Finansial pada Microservices
Sebuah bank digital memigrasikan database pembayaran ke AWS Aurora PostgreSQL. Regulasi perbankan mewajibkan bahwa:
1. Kolom data sensitif (Nomor Kartu Debit/Kredit - PAN) tidak boleh tersimpan dalam bentuk teks terbuka di storage mesin database, bahkan oleh database administrator (DBA) yang memiliki hak akses query langsung.
2. Kunci enkripsi harus dirotasi secara otomatis setiap 365 hari.
3. Kredensial koneksi aplikasi ke database harus diganti secara berkala setiap 30 hari tanpa menyebabkan kegagalan koneksi (*zero-downtime*) pada puluhan container microservices yang sedang berjalan.
- **Pertanyaan:** Rancang solusi arsitektur AWS end-to-end untuk memenuhi ketiga kepatuhan regulasi di atas.
- **Analisis & Solusi:**
  1. **Enkripsi Data Sensitif (Envelope Encryption via KMS CMK):**
     - Jangan hanya mengandalkan enkripsi storage Aurora (Storage encryption hanya melindungi disk at-rest).
     - Terapkan Application-Level / Field-Level Encryption. Microservice pembayaran menggunakan AWS KMS Customer Managed Key (CMK) dengan library AWS Encryption SDK.
     - Sebelum melakukan SQL `INSERT`, microservice memanggil `kms:GenerateDataKey`, mengenkripsi field PAN dengan AES-256-GCM, menghapus plaintext data key dari memori, dan menyimpan ciphertext string ke database. DBA yang melakukan `SELECT *` hanya akan melihat ciphertext terenkripsi.
  2. **Rotasi Kunci Tahunan:**
     - Aktifkan fitur `Enable Key Rotation` pada KMS CMK. AWS KMS akan secara otomatis membuat backing key baru setiap 365 hari tanpa mengubah Key ID atau ARN, sehingga data lama tetap dapat didekripsi secara transparan dan data baru terenkripsi dengan kunci terbaru.
  3. **Rotasi Kredensial Database (AWS Secrets Manager):**
     - Kredensial Aurora disimpan di AWS Secrets Manager.
     - Konfigurasikan Secrets Manager Automatic Rotation menggunakan blueprint Lambda function `SecretsManagerRDSMySQLRotationMultiUser` (pola multi-user: user satu aktif, user dua dirotasi, lalu switch bergantian).
     - Microservices menggunakan RDS Proxy atau SDK client Secrets Manager caching untuk membaca kredensial terbaru secara dinamis tanpa restart pod/container.

---

#### Skenario 3: Penanganan Serangan L7 Distributed HTTP Flood dan Bad Bot
Sebuah platform tiket konser online mengalami insiden saat flash-sale tiket: server web di belakang ALB mengalami crash karena kehabisan socket koneksi. Tim SRE mengamati karakteristik traffic berikut:
- Terdapat 500.000 HTTP POST request per menit ke endpoint `/api/v1/checkout`.
- Request berasal dari puluhan ribu alamat IP perumahan yang tersebar di seluruh dunia (mencerminkan Residential Proxy Network / Distributed Botnet).
- Header User-Agent selalu berubah-ubah secara acak, namun sebagian besar request tidak mengeksekusi JavaScript browser dan tidak merespons HTTP Cookie redirect standar.
- **Pertanyaan:** Bagaimana mengonfigurasi AWS WAF dan AWS Shield untuk memitigasi serangan ini secara deterministik tanpa memblokir pembeli tiket yang sah?
- **Analisis & Solusi:**
  1. **AWS WAF Bot Control (Targeted Inspection):**
     - Aktifkan AWS Managed Rules: `AWSManagedRulesBotControlRuleSet` dengan level inspeksi `Targeted`.
     - Rule ini secara deterministik mendeteksi botnet canggih dengan menerapkan browser interrogation (JavaScript execution challenge). Bot script sederhana dan headless browser tanpa kapabilitas rendering JS akan gagal menjawab challenge dan langsung diblokir di layer WAF edge.
  2. **AWS WAF Challenge / CAPTCHA Action pada Critical Path:**
     - Untuk endpoint spesifik `/api/v1/checkout`, buat custom WAF Rule yang mengenakan action `Challenge` (silent JavaScript challenge) atau `CAPTCHA` jika IP melakukan request POST melebihi 5 kali per 10 detik.
     - Pengguna manusia yang menggunakan browser resmi akan menyelesaikan JavaScript challenge secara transparan di background (zero UX impact), sedangkan botnet yang tidak mendukung parsing JS akan tereliminasi.
  3. **AWS Shield Advanced Engagement:**
     - Karena pelanggan menggunakan Shield Advanced, ALB diasosiasikan dengan proteksi Shield Advanced.
     - Aktifkan fitur *Automatic Application Layer DDoS Mitigation*. Fitur ini secara otomatis menganalisis pola traffic jahat, mensintesis custom WAF rule secara real-time, dan menginjeksinya ke Web ACL tanpa intervensi manual tim engineer.

---

### D. Practical Chapter Challenge: Arsitektur Continuous Security & Incident Response

#### Deskripsi Tantangan
Anda ditunjuk sebagai Principal SRE di sebuah platform Healthcare Enterprise. Anda diminta untuk membangun sistem deteksi, pencegahan, dan audit kepatuhan terotomatisasi pada lingkungan AWS multi-tier.

#### Spesifikasi Kebutuhan Teknis:
1. **Infrastruktur KMS & Secrets Manager:**
   - Buat sebuah KMS Customer Managed Key (CMK) bernama `alias/healthcare-phi-key` dengan key rotation aktif.
   - Buat AWS Secrets Manager secret bernama `prod/db/phi-database` yang dienkripsi menggunakan CMK tersebut.
2. **Perimeter Web Access Control (WAFv2):**
   - Buat Web ACL Regional dengan 2 aturan:
     - Rate limit: Maksimal 300 request per 5 menit per source IP (Action: Block).
     - Aturan inspeksi header: Wajib ada custom header `X-Origin-Verification: Healthcare-Core-Secure`. Request yang tidak memiliki header ini pada URI path `/private/*` harus di-BLOCK secara instan.
3. **Audit Kepatuhan Kontinu (AWS Config):**
   - Deploy Config Rule terkelola: `encrypted-volumes` (memastikan semua disk EBS terenkripsi) dan `s3-bucket-ssl-requests-only` (memastikan semua bucket menolak koneksi HTTP non-TLS).
4. **Automated Incident Remediation (Event-Driven Architecture):**
   - Buat sebuah skrip Python/Terraform yang mendemonstrasikan automasi tanggap darurat: Jika terdeteksi GuardDuty finding berkategori `UnauthorizedAccess:EC2/SSHBruteForce` atau Security Group terbuka ke publik pada port database (5432/3306), sistem secara otomatis mencabut security group ingress rule tersebut dan mengirimkan audit payload ke format JSON forensik.

#### Kriteria Keberhasilan:
- Seluruh konfigurasi dideklarasikan secara deterministik dan idempotent menggunakan Terraform atau AWS CLI scripts.
- Tidak ada hardcoded credentials pada artefak konfigurasi.
- Mekanisme enkripsi terverifikasi menggunakan model Envelope Encryption secara valid.

---