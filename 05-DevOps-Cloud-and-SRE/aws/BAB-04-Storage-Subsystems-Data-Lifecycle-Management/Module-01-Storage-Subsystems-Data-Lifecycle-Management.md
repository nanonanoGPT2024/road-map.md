# Modul 01: Storage Subsystems & Data Lifecycle Management

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Mengidentifikasi karakteristik kinerja, IOPS, throughput, latensi, dan model biaya dari subsistem penyimpanan AWS (Amazon S3, Amazon EBS, Amazon EFS, Amazon FSx, dan AWS Storage Gateway).
- Mengonfigurasi dan mengotomatisasi *Data Lifecycle Management* serta *Data Protection* menggunakan S3 Lifecycle Rules, S3 Versioning, S3 Object Lock (Compliance & Governance Mode), dan AWS Backup lintas region/akun.
- Merancang arsitektur penyimpanan *hybrid* dan *cloud-native* dengan memanfaatkan Amazon EBS multi-attach (io2 Block Express), Amazon EFS Elastic Throughput, Amazon FSx for NetApp ONTAP/Lustre, serta AWS Storage Gateway untuk integrasi on-premises.
- Mendiagnosis dan menyelesaikan masalah degradasi performa I/O (*I/O throttling*, kredit *bursting* habis), *split-brain* pada shared storage, serta kegagalan replikasi data.

---

## 2. Prerequisite
- Pemahaman fundamental mengenai Linux File System hierarchy, POSIX permissions, block storage vs. object storage vs. network file share.
- Pemahaman dasar arsitektur jaringan AWS: VPC, Subnet, Security Group, VPC Endpoints (Gateway & Interface).
- AWS CLI v2 terinstal dan terkonfigurasi dengan hak akses administratif terbatas (IAM Roles/Credentials).
- Terraform CLI v1.5+ terpasang untuk provisioning infrastruktur as code (IaC).

---

## 3. Concept
Penyimpanan cloud AWS terbagi dalam tiga paradigma utama:
1. **Object Storage (Amazon S3)**: Ruang alamat datar (*flat namespace*) berbasis REST API untuk data tak terstruktur, menawarkan durabilitas $99.999999999\%$ (11 9's). Data diakses melalui HTTP verb (`GET`, `PUT`, `DELETE`) dan memiliki siklus hidup yang diatur berdasarkan metadata dan akses temporal.
2. **Block Storage (Amazon EBS)**: Penyimpanan berlatensi rendah sub-milidetik yang terikat pada hypervisor instance EC2 dalam satu Availability Zone (AZ). EBS mensimulasikan disk fisik mentah (*raw block device*) yang diformat dengan sistem berkas (misalnya `ext4`, `xfs`).
3. **File Storage (Amazon EFS & Amazon FSx)**: Penyimpanan berkas terkelola yang mendukung protokol jaringan standar seperti NFSv4 (EFS), SMB, Lustre, dan ZFS/ONTAP (FSx) dengan kemampuan *multi-instance concurrent read/write*.

Manajemen siklus hidup data (*Data Lifecycle Management*) adalah pendekatan berbasis kebijakan terprogram untuk memindahkan data antar-tier penyimpanan secara otomatis guna meminimalkan biaya per gigabyte tanpa mengorbankan SLA ketersediaan dan kepatuhan hukum (*regulatory compliance*).

---

## 4. Why
Mengelola penyimpanan di lingkungan enterprise tanpa pemahaman mendalam tentang subsistem dan siklus hidup akan menyebabkan dua masalah sistemik:
- **Biaya Tak Terkendali (*Cost Bleeding*)**: Menyimpan data log analitik 5 tahun di S3 Standard atau mengalokasikan volume EBS `io2` untuk beban kerja dev/staging menghabiskan anggaran cloud secara signifikan. Menggeser data dingin (*cold data*) ke tier arsip (Glacier Deep Archive) dapat memotong biaya penyimpanan hingga $95\%$.
- **Kegagalan Integritas & Kepatuhan Data**: Tanpa *WORM (Write Once, Read Many)* storage (S3 Object Lock) dan AWS Backup Vault Lock yang *immutable*, perusahaan rentan terhadap serangan ransomware atau pelanggaran kepatuhan (SEC Rule 17a-4, FINRA, HIPAA) jika data historis terhapus atau dimodifikasi oleh kredensial internal yang terkompromi.

---

## 5. What (Deep-Dive Teknis Lengkap)

### Amazon S3: Storage Tiering, Protection, & Replication
- **Storage Classes**:
  - `S3 Standard`: Data aktif, latensi milidetik, durabilitas 11 9's di $\ge 3$ AZ.
  - `S3 Intelligent-Tiering`: Menggunakan machine learning untuk memantau pola akses dan memindahkan objek secara otomatis antara tier *Frequent*, *Infrequent* (30 hari), *Archive Instant Access* (90 hari), *Archive Access* opsional (90-730 hari), dan *Deep Archive Access* opsional tanpa penalti *retrieval fee*.
  - `S3 Standard-IA & S3 One Zone-IA`: Data jarang diakses tetapi membutuhkan akses milidetik. One Zone-IA hanya berada di 1 AZ (risiko data hilang jika AZ hancur).
  - `S3 Glacier Instant Retrieval`: Retensi data jarang diakses (kuartalan) dengan latensi milidetik.
  - `S3 Glacier Flexible Retrieval`: Pengambilan data reguler (1-5 menit dengan Expedited, 3-5 jam Standard, 5-12 jam Bulk).
  - `S3 Glacier Deep Archive`: Arsip jangka panjang (retensi 7-10 tahun), waktu retrieval standar 12 jam.
- **S3 Versioning & Lifecycle Rules**: Mengatur transisi otomatis berdasarkan umur objek (misal: S3 Standard $\to$ S3 Standard-IA pada hari ke-30 $\to$ S3 Glacier Flexible pada hari ke-90 $\to$ Delete Noncurrent Version pada hari ke-365).
- **S3 Object Lock (WORM Model)**:
  - *Governance Mode*: Objek tidak dapat dihapus atau ditimpa kecuali oleh pengguna yang memiliki permission eksplisit `s3:BypassGovernanceRetention`.
  - *Compliance Mode*: Tidak ada pengguna (termasuk AWS Root Account) yang dapat menghapus objek atau mengubah durasi retensi sebelum masa retensi berakhir.
  - *Legal Hold*: Flag biner independen tanpa batas waktu kedaluwarsa yang mencegah penghapusan data hingga status dilepas.
- **S3 Replication**: Cross-Region Replication (CRR) untuk disaster recovery dan kepatuhan geografis, atau Same-Region Replication (SRR) untuk agregasi log dan isolasi akun. S3 Replication Time Control (RTC) menjamin 99.9% replikasi selesai dalam waktu 15 menit dengan SLA.

### Amazon EBS: Block Storage Engine
- **gp3**: General purpose SSD generasi terbaru. Baseline performa 3,000 IOPS dan 125 MB/s throughput gratis pada ukuran disk berapapun, dapat ditingkatkan secara independen hingga 16,000 IOPS dan 1,000 MB/s.
- **io2 Block Express**: SAN-in-the-cloud berbasis arsitektur Nitro. Performa hingga 256,000 IOPS, 4,000 MB/s throughput, latensi sub-milidetik, dan durabilitas $99.999\%$ (5 9's). Rasio IOPS:GB hingga 1,000:1.
- **EBS Multi-Attach**: Memungkinkan satu volume `io2`/`io1` dipasang ke beberapa EC2 Nitro instances secara bersamaan dalam satu AZ. **Penting**: Memerlukan *cluster-aware filesystem* (seperti GFS2, OCFS2, atau database engine terdistribusi) untuk mencegah korupsi data akibat penulisan konkuren tak terkoordinasi.

### Amazon EFS & Amazon FSx
- **Amazon EFS**: Network file system terkelola berbasis NFSv4.1.
  - *Throughput Mode*: Elastic (otomatis menyesuaikan beban), Provisioned, atau Bursting.
  - *Lifecycle Management*: Transisi otomatis ke EFS Infrequent Access (IA) atau EFS Archive setelah rentang waktu ketiadaan akses (misal 14 atau 30 hari).
- **Amazon FSx Family**:
  - *FSx for Windows File Server*: Berbasis Windows native SMB, terintegrasi penuh dengan Active Directory, DFS, dan bayangan VSS.
  - *FSx for Lustre*: File system performa tinggi untuk HPC, machine learning, dan video rendering. Mampu membaca/menulis data langsung dari/ke Amazon S3.
  - *FSx for NetApp ONTAP*: File storage multi-protokol (NFS, SMB, iSCSI) dengan fitur enterprise NetApp seperti deduplikasi, kompresi inline, cloning instan (FlexClone), dan tiering data dingin ke pool S3 tersembunyi.
  - *FSx for OpenZFS*: Berbasis ZFS open-source, latensi ratusan mikrodetik, throughput gigabyte per detik untuk beban kerja Linux intensif.

### AWS Storage Gateway & AWS Backup
- **AWS Storage Gateway**: Menghubungkan on-premises storage ke AWS Cloud:
  - *S3 File Gateway*: Menyajikan SMB/NFS share lokal yang langsung di-back-end ke bucket S3.
  - *Volume Gateway*: Menyajikan target iSCSI block storage lokal (Cached Volume menyimpan data aktif di lokal; Stored Volume menyimpan seluruh data di lokal dengan backup asynchronous ke EBS snapshots).
  - *Tape Gateway*: Emulasi Virtual Tape Library (VTL) fisik melalui iSCSI untuk integrasi software backup legacy ke S3 Glacier/Deep Archive.
- **AWS Backup**: Layanan orkestrator terpusat berbasis kebijakan (*policy-based*) untuk mengotomatisasi backup EBS, EFS, RDS, DynamoDB, dan S3 lintas akun AWS (Organizations) dan lintas region. Mendukung *AWS Backup Vault Lock* untuk mencegah penghapusan titik pemulihan (*recovery points*) oleh serangan internal/ransomware.

---

## 6. How
Implementasi subsistem penyimpanan dan siklus hidup data dilakukan dengan alur berikut:
1. **Analisis Karakteristik Data**: Evaluasi IOPS, throughput, pola akses temporal (dingin/panas), konkurensi (single vs multi-node), dan kepatuhan (SLA/WORM).
2. **Definisi Infrastructure as Code (IaC)**: Konfigurasikan resource storage menggunakan Terraform, mendeklarasikan enkripsi default (KMS CMK), versioning, dan aturan lifecycle.
3. **Penerapan Kebijakan Immutability**: Terapkan S3 Object Lock atau AWS Backup Vault Lock untuk data transaksional dan kepatuhan audit.
4. **Implementasi Replikasi Lintas Region**: Konfigurasikan replikasi S3 (CRR) atau AWS Backup cross-region copy untuk memenuhi RPO/RTO pada skenario Disaster Recovery.
5. **Observabilitas & Audit**: Pantau metrik CloudWatch (`BurstBalance`, `VolumeThroughputPercentage`, `VolumeIOPSPercentage`) dan audit kepatuhan melalui AWS Config.

---

## 7. Analogy
Bayangkan penyimpanan AWS seperti manajemen logistik dokumen fisik pada gedung perkantoran:
- **EBS (gp3/io2)**: Seperti **laci kerja di meja Anda**. Anda dapat mengambil kertas langsung dalam hitungan detik (latensi sub-milidetik), tetapi laci ini terpasang secara fisik pada meja tersebut (1 AZ) dan kapasitasnya terbatas.
- **EFS**: Seperti **lemari arsip bersama di lorong kantor**. Semua staf (banyak server) dapat berjalan ke lemari, membuka map yang sama secara bersamaan menggunakan kunci standar kantor (NFS), meskipun aksesnya membutuhkan waktu beberapa langkah lebih lambat daripada membuka laci meja sendiri.
- **S3**: Seperti **gudang logistik terpusat raksasa**. Setiap dokumen diberi barcode unik (Object Key). Anda tidak bisa mengubah 1 lembar halaman di dalam sebuah map; jika ingin merevisi, Anda harus mengirimkan map versi baru seutuhnya. Namun, kapasitas gudang ini tidak terbatas.
- **S3 Lifecycle Rules**: Seperti **petugas arsip otomatis**. Setiap dokumen yang berusia 30 hari dipindahkan dari rak depan ke rak belakang gudang (IA), setelah 90 hari dimasukkan ke peti kayu tertutup (Glacier), dan setelah 7 tahun dokumen tersebut dihancurkan secara permanen oleh mesin penghancur kertas (*lifecycle expiration*).
- **S3 Object Lock (Compliance Mode)**: Seperti **brankas baja bertenggat waktu mekanis**. Sekali dokumen dimasukkan dan brankas dikunci untuk 5 tahun, kuncinya hancur secara otomatis. Tidak ada pimpinan perusahaan, aparat hukum, atau perampok yang bisa membuka brankas tersebut sebelum 5 tahun berlalu.

---

## 8. Diagram (ASCII)

```text
+----------------------------------------------------------------------------------------------------+
|                                    AWS CLOUD DATA LIFECYCLE                                        |
+----------------------------------------------------------------------------------------------------+
                                                                                                      
 [ On-Premises ]                                 [ Single AZ ]                                       
 +-------------+                                 +-------------------------------------------------+ 
 | File Server |                                 | EC2 Instance (Worker Node)                      | 
 +------+------+                                 +--------+-------------------------------+--------+ 
        | (NFS/SMB)                                       | (Block I/O)                   | (POSIX)  
        v                                                 v                               v          
 +-------------------+                           +-----------------+              +----------------+ 
 | Storage Gateway   |                           | EBS Volume      |              | Amazon EFS     | 
 | (S3 File Gateway) |                           | (gp3 / io2 BX)  |              | (Multi-AZ)     | 
 +------+------------+                           +--------+--------+              +-------+--------+ 
        |                                                 | Snapshot                      | Lifecycle
        | HTTPS Upload                                    v                               v          
        |                                        +-----------------+              +----------------+ 
        +--------------------------------------->| S3 / AWS Backup |              | EFS Infrequent | 
                                                 | (Cross-Region)  |              | Access / Arch  | 
                                                 +--------+--------+              +----------------+ 
                                                          |                                          
                                                          v                                          
 +-------------------------------------------------------------------------------------------------+ 
 | Amazon S3 Bucket Architecture                                                                   | 
 |                                                                                                 | 
 |  Day 0               Day 30                     Day 90                       Day 365            | 
 | +---------------+    +---------------------+    +-----------------------+    +----------------+ | 
 | |  S3 Standard  |--->|  S3 Standard-IA     |--->|  S3 Glacier Flexible  |--->|  Permanent     | | 
 | |  (Hot Access) |    |  (Infrequent Read)  |    |  (Cold Archive)       |    |  Deletion /    | | 
 | +---------------+    +---------------------+    +-----------------------+    |  Deep Archive  | | 
 |         |                       |                           |                +----------------+ | 
 |         +-----------------------+---------------------------+                                   | 
 |                                 |                                                               | 
 |                                 v                                                               | 
 |                     [ S3 Object Lock: COMPLIANCE ]                                              | 
 |                     - Cannot be deleted by ANYONE                                               | 
 |                     - Immutable WORM Retention Period                                           | 
 +-------------------------------------------------------------------------------------------------+ 
```

---

## 9. Simple Example
Menghitung throughput EBS `gp3`:
Secara default, volume gp3 berukuran 100 GB memiliki baseline 3,000 IOPS dan 125 MB/s throughput tanpa biaya tambahan di luar kapasitas GB.
Jika Anda membutuhkan throughput 500 MB/s untuk pemrosesan file batch:
- Baseline gratis: 125 MB/s
- Tambahan yang harus diprovisi: $500 - 125 = 375\text{ MB/s}$
- Anda cukup mengonfigurasi parameter provisioned throughput pada AWS CLI atau Terraform tanpa perlu memperbesar ukuran disk menjadi ratusan gigabyte seperti pada generasi `gp2` terdahulu.

---

## 10. Practical Example (Konfigurasi CLI / Terraform / Kode Hands-on)

Berikut adalah konfigurasi Terraform komprehensif yang memprovisi Amazon S3 Bucket dengan Versioning, Object Lock (Compliance Mode), Lifecycle Transition, dan Replikasi Lintas Region.

```hcl
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  alias  = "primary"
  region = "us-east-1"
}

provider "aws" {
  alias  = "dr"
  region = "us-west-2"
}

# KMS Key for S3 Encryption (Primary)
resource "aws_kms_key" "primary_s3_key" {
  provider                = aws.primary
  description             = "KMS Key for Primary S3 Storage"
  deletion_window_in_days = 7
  enable_key_rotation     = true
}

# KMS Key for S3 Encryption (DR)
resource "aws_kms_key" "dr_s3_key" {
  provider                = aws.dr
  description             = "KMS Key for DR S3 Storage"
  deletion_window_in_days = 7
  enable_key_rotation     = true
}

# DR Destination Bucket (Must be created before replication configuration)
resource "aws_s3_bucket" "dr_bucket" {
  provider      = aws.dr
  bucket        = "corp-critical-data-dr-uswest2"
  force_destroy = false
}

resource "aws_s3_bucket_versioning" "dr_versioning" {
  provider = aws.dr
  bucket   = aws_s3_bucket.dr_bucket.id
  versioning_configuration {
    status = "Enabled"
  }
}

# Primary S3 Bucket with Object Lock Enabled
resource "aws_s3_bucket" "primary_bucket" {
  provider            = aws.primary
  bucket              = "corp-critical-data-primary-useast1"
  object_lock_enabled = true
}

resource "aws_s3_bucket_versioning" "primary_versioning" {
  provider = aws.primary
  bucket   = aws_s3_bucket.primary_bucket.id
  versioning_configuration {
    status = "Enabled"
  }
}

# S3 Object Lock Default Configuration (Compliance Mode: 90 Days)
resource "aws_s3_bucket_object_lock_configuration" "lock_config" {
  provider = aws.primary
  bucket   = aws_s3_bucket.primary_bucket.id

  rule {
    default_retention {
      mode = "COMPLIANCE"
      days = 90
    }
  }
}

# Server-Side Encryption Configuration
resource "aws_s3_bucket_server_side_encryption_configuration" "primary_encryption" {
  provider = aws.primary
  bucket   = aws_s3_bucket.primary_bucket.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.primary_s3_key.arn
      sse_algorithm     = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

# IAM Role for S3 Cross-Region Replication
resource "aws_iam_role" "replication_role" {
  name = "s3-cross-region-replication-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "s3.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_policy" "replication_policy" {
  name = "s3-cross-region-replication-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "s3:GetReplicationConfiguration",
          "s3:ListBucket"
        ]
        Effect   = "Allow"
        Resource = aws_s3_bucket.primary_bucket.arn
      },
      {
        Action = [
          "s3:GetObjectVersionForReplication",
          "s3:GetObjectVersionAcl",
          "s3:GetObjectVersionTagging"
        ]
        Effect   = "Allow"
        Resource = "${aws_s3_bucket.primary_bucket.arn}/*"
      },
      {
        Action = [
          "s3:ReplicateObject",
          "s3:ReplicateDelete",
          "s3:ReplicateTags"
        ]
        Effect   = "Allow"
        Resource = "${aws_s3_bucket.dr_bucket.arn}/*"
      },
      {
        Action = [
          "kms:Decrypt"
        ]
        Effect   = "Allow"
        Resource = aws_kms_key.primary_s3_key.arn
      },
      {
        Action = [
          "kms:Encrypt"
        ]
        Effect   = "Allow"
        Resource = aws_kms_key.dr_s3_key.arn
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "replication_attach" {
  role       = aws_iam_role.replication_role.name
  policy_arn = aws_iam_policy.replication_policy.arn
}

# S3 Cross-Region Replication Configuration with RTC (Replication Time Control)
resource "aws_s3_bucket_replication_configuration" "crr_config" {
  provider   = aws.primary
  depends_on = [aws_s3_bucket_versioning.primary_versioning]

  role   = aws_iam_role.replication_role.arn
  bucket = aws_s3_bucket.primary_bucket.id

  rule {
    id     = "ReplicateAllEncryptedObjectsWithRTC"
    status = "Enabled"

    source_selection_criteria {
      sse_kms_encrypted_objects {
        status = "Enabled"
      }
    }

    destination {
      bucket        = aws_s3_bucket.dr_bucket.arn
      storage_class = "STANDARD_IA"

      encryption_configuration {
        replica_kms_key_id = aws_kms_key.dr_s3_key.arn
      }

      replication_time {
        status = "Enabled"
        time {
          minutes = 15
        }
      }

      metrics {
        status = "Enabled"
        event_threshold {
          minutes = 15
        }
      }
    }
  }
}

# S3 Data Lifecycle Management Rules
resource "aws_s3_bucket_lifecycle_configuration" "lifecycle_rules" {
  provider = aws.primary
  bucket   = aws_s3_bucket.primary_bucket.id

  rule {
    id     = "TransitionAndExpirationPolicy"
    status = "Enabled"

    filter {
      prefix = "logs/"
    }

    # Transisi objek saat ini (current version)
    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 90
      storage_class = "GLACIER"
    }

    transition {
      days          = 180
      storage_class = "DEEP_ARCHIVE"
    }

    expiration {
      days = 365
    }

    # Manajemen versi kadaluwarsa (noncurrent versions)
    noncurrent_version_transition {
      noncurrent_days = 30
      storage_class   = "GLACIER"
    }

    noncurrent_version_expiration {
      noncurrent_days = 90
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}
```

---

## 11. Real World Example
Sebuah institusi perbankan multinasional diwajibkan memenuhi standar kepatuhan PCI-DSS dan regulasi OJK mengenai retensi data transaksi audit:
- **Kebutuhan**: Log transaksi keuangan harus disimpan selama 7 tahun. Log 30 hari pertama harus dapat diakses secara instan oleh tim fraud analytics. Setelah 30 hari, data jarang disentuh. Regulasi melarang data diubah atau dihapus oleh siapapun (termasuk tim SRE/Root) selama masa retensi 7 tahun. Data harus selamat dari skenario bencana tingkat regional.
- **Implementasi**:
  1. Data log diekspor dari aplikasi ke Amazon S3 bucket utama menggunakan AWS KMS Customer Managed Keys (CMK).
  2. Bucket dikonfigurasi dengan **S3 Object Lock dalam Compliance Mode** dengan durasi 2,555 hari (7 tahun).
  3. Mengaktifkan **S3 Cross-Region Replication (CRR)** dengan S3 RTC ke Region sekunder di yurisdiksi yang diizinkan regulator, di mana KMS key tujuan dirotasi otomatis.
  4. Menerapkan **Lifecycle Rules**: Transisi dari S3 Standard ke S3 Glacier Instant Retrieval pada hari ke-31, transisi ke S3 Glacier Deep Archive pada hari ke-90.
  5. Menghilangkan hak istimewa pembersihan multipart upload lama menggunakan aturan `abort_incomplete_multipart_upload` pada hari ke-3 untuk mencegah pembengkakan biaya *hidden orphaned chunks*.

---

## 12. Trade-offs

| Dimensi | Opsi A | Opsi B | Analisis Komparasi |
| :--- | :--- | :--- | :--- |
| **S3 Storage Class** | S3 Standard | S3 Intelligent-Tiering | S3 Standard memiliki biaya penyimpanan $/GB lebih tinggi, tetapi tidak memiliki biaya automasi pemantauan objek ($0.0025 per 1,000 objek). Jika objek berukuran kecil (<128 KB) dan jumlahnya ratusan juta, Intelligent-Tiering justru lebih mahal karena biaya automasi dan minimum billing limit 128 KB. |
| **EBS Provisioning** | gp3 (Provisioned) | io2 Block Express | `gp3` jauh lebih hemat biaya untuk sebagian besar beban kerja database umum hingga 16,000 IOPS. `io2 Block Express` jauh lebih mahal, namun esensial untuk mission-critical SAP HANA atau Oracle RAC dengan kebutuhan durabilitas 5-nines ($99.999\%$) dan IOPS ekstrem (>64,000) dengan latensi sub-milidetik. |
| **Shared Storage** | Amazon EFS | Amazon FSx for ONTAP | EFS lebih sederhana (serverless, tanpa kapasitas terpasang minimum). FSx for NetApp ONTAP memerlukan alokasi kapasitas minimum, namun memiliki fitur kompresi, deduplikasi, dan protokol multi-akses (NFS + SMB + iSCSI) yang signifikan memangkas TCO dataset terstruktur skala terabyte-petabyte. |
| **Retention Policy** | S3 Governance Mode | S3 Compliance Mode | Governance Mode fleksibel untuk testing dan rollback darurat oleh user ber-privilege tinggi. Compliance Mode menjamin integritas hukum mutlak namun membawa risiko finansial: data tidak bisa dihapus dengan cara apapun hingga durasi berakhir. |

---

## 13. When To Use
- **Gunakan Amazon S3 Lifecycle + Object Lock**: Untuk log transaksi, arsip data rekam medis, media streaming, dan backup repositori yang membutuhkan skala tak terbatas dan kepatuhan WORM.
- **Gunakan Amazon EBS gp3**: Sebagai volume boot dan volume aplikasi umum (web server, worker node, database operasional skala menengah).
- **Gunakan Amazon EBS io2 Block Express Multi-Attach**: Untuk cluster high-availability aktif/pasif atau shared cluster engine terdistribusi yang memerlukan disk mentah dengan proteksi latensi super ketat.
- **Gunakan Amazon EFS**: Untuk aplikasi cloud-native containerized (ECS/EKS) yang membutuhkan shared home directory, CMS WordPress multi-container, atau share CI/CD artifact.
- **Gunakan Amazon FSx for Lustre**: Untuk pipeline pelatihan Machine Learning (SageMaker) atau rendering grafis 3D di mana komputasi membutuhkan akses throughput ratusan GB/s langsung ke data lake S3.

---

## 14. When NOT To Use
- **JANGAN Gunakan S3**: Sebagai direct root volume sistem operasi atau database transaksional OLTP (MySQL/PostgreSQL) yang memerlukan pembacaan/penulisan blok berlatensi rendah secara terus-menerus.
- **JANGAN Gunakan EBS Multi-Attach dengan Filesystem Standar (ext4/xfs)**: Menggunakan ext4/xfs pada EBS Multi-Attach akan mengakibatkan **kerusakan data (*filesystem corruption*) instan** karena kernel sistem operasi tidak menyadari adanya penulisan dari node lain. Gunakan cluster-aware filesystem seperti GFS2.
- **JANGAN Gunakan S3 Standard-IA / Glacier untuk File Berukuran Sangat Kecil (<128 KB)**: Objek yang lebih kecil dari 128 KB tetap dikenakan kuota minimum penagihan 128 KB di tier IA/Glacier, ditambah biaya transaksi GET/PUT yang tinggi, yang memicu lonjakan biaya tak terduga.
- **JANGAN Gunakan EFS**: Untuk beban kerja yang memerlukan latensi baca disk sub-milidetik atau I/O intensif acak (*random write-heavy*) seperti transaction log RDBMS enterprise.

---

## 15. Common Mistakes
1. **Mengaktifkan S3 Object Lock Compliance Mode di Tahap Development**: Pengembang mencoba skrip pengujian upload, lalu menyadari bucket tidak dapat dihapus selama masa retensi (misal 30 hari), memaksa akun membayar objek pengujian tersebut tanpa bisa di-purge.
2. **Lupa Menambahkan Rule `abort_incomplete_multipart_upload`**: Ketika upload file berukuran gigabyte via CLI/SDK terputus, potongan-potongan multipart tersimpan di S3 tanpa menjadi objek utuh. Potongan ini terus ditagih sebagai kapasitas S3 Standard tanpa terlihat di daftar file (`aws s3 ls`) reguler.
3. **Mengabaikan EBS Burst Balance pada Volume gp2 Legacy**: Menjalankan beban kerja produksi pada volume legacy `gp2` tanpa memantau metrik CloudWatch `BurstBalance`. Saat saldo habis, performa disk anjlok drastis ke baseline ratusan IOPS, memicu *downtime* aplikasi. Solusi: Migrasikan ke `gp3`.
4. **Salah Mengonfigurasi Permissions Replikasi S3 untuk Objek KMS**: S3 CRR gagal mereplikasi objek secara diam-diam (*silent failure*) karena IAM Role replikasi tidak memiliki akses `kms:Decrypt` pada kunci asal atau `kms:Encrypt` pada kunci tujuan.
5. **Mengira EFS General Purpose Identik dengan EBS SSD**: Menjalankan database MySQL di atas Amazon EFS lalu mengalami latensi latches/lock tinggi karena karakteristik latency network file system (beberapa milidetik) dibandingkan block storage native (sub-milidetik).

---

## 16. Best Practices
- **Migrasi gp2 ke gp3 Secara Global**: Manfaatkan kapabilitas Elastic Block Store Elastic Volumes untuk mengubah tipe disk `gp2` ke `gp3` secara *in-flight* (tanpa downtime) untuk segera mendapatkan penghematan biaya $20\%$ dan performa dasar 3,000 IOPS.
- **Aktifkan S3 Bucket Keys saat Menggunakan AWS KMS**: Penggunaan *S3 Bucket Keys* mengurangi panggilan API KMS hingga $99\%$, menurunkan biaya KMS secara dramatis pada bucket dengan intensitas I/O tinggi.
- **Gunakan Centralized Backup Policies via AWS Organizations**: Jangan mengandalkan snapshot script berbasis cron job di masing-masing instans. Orkestrasikan retensi backup, snapshot EBS, dan brankas immutability melalui AWS Backup Policy terpusat.
- **Kombinasikan S3 Lifecycle Rules dengan Noncurrent Version Management**: Selalu pasang batas waktu penghapusan noncurrent version (misal 30 hari) agar versi lama dari objek yang sering di-overwrite tidak memakan kuota secara kumulatif.
- **Terapkan AWS Backup Vault Lock**: Lindungi brankas backup dari ancaman ransomware dengan mengaktifkan Vault Lock dalam mode *Locked*, memastikan retensi minimum tidak dapat dipersingkat oleh siapapun.

---

## 17. Troubleshooting

| Gejala Masalah | Investigasi Teknis | Solusi / Resolusi |
| :--- | :--- | :--- |
| Objek S3 tidak bertransisi ke Glacier sesuai Lifecycle Rule | Periksa ukuran objek (`<128 KB`) dan waktu transisi. S3 Lifecycle engine mengevaluasi rule satu kali sehari (tengah malam UTC) dan ada jeda propagasi konsistensi. Periksa juga apakah objek memiliki *Legal Hold* atau status *Object Lock*. | Objek $<128\text{ KB}$ tidak memenuhi syarat untuk beberapa kelas Glacier/IA. Jika ukuran memenuhi syarat, tunggu siklus batch UTC berikutnya; tagihan dihitung berdasarkan waktu jatuh tempo kebijakan meskipun status transisi tertunda. |
| Replikasi S3 (CRR) berstatus `FAILED` pada metadata objek | Periksa metadata objek menggunakan `aws s3api head-object`. Cek konfigurasi IAM Role CRR dan KMS Key Policy. Seringkali Key Policy tidak mengizinkan principal IAM Role S3 untuk melakukan `kms:Decrypt` pada source bucket. | Perbarui KMS Key Policy pada KMS Key sumber dan tujuan agar menyertakan ARN Role replikasi S3. Jika menggunakan RTC, pastikan service-linked role memiliki kuota metrik yang cukup. |
| Performa I/O EBS anjlok drastis pada gp3/io2 | Cek CloudWatch metrics: `VolumeThroughputPercentage` dan `VolumeIOPSPercentage`. Jika metrik ini konsisten di angka $100\%$, aplikasi mengalami disk I/O bottlenecking. | Naikkan kapasitas IOPS atau Throughput pada konfigurasi EBS secara langsung (*online modification*) via AWS Console/CLI/Terraform tanpa menghentikan instance. |
| Mount EFS mengalami I/O Hang / Latensi Ekstrem | Cek CloudWatch metric `PercentIOLimit` dan throughput model. Jika menggunakan *Bursting Throughput*, cek `BurstCreditBalance`. Jika saldo $0$, throughput tercekik ke baseline yang sangat rendah. | Ubah throughput mode sistem berkas EFS dari *Bursting* menjadi *Elastic Throughput* secara langsung untuk menangani lonjakan I/O tanpa batasan saldo kredit. |
| EBS Multi-Attach: Data korup saat ditulis dari dua instans | Analisis filesystem yang digunakan. `dmesg` menampilkan filesystem journal error atau metadata mismatch. | Matikan akses bersama. Hapus filesystem non-cluster (`ext4`/`xfs`). Pasang cluster filesystem manager (seperti Corosync/Pacemaker + GFS2) sebelum memasang volume Multi-Attach ke beberapa instance. |

---

## 18. Exercise
1. **Implementasi Dynamic EBS gp3 Resizing via AWS CLI**:
   Buat sebuah EBS volume `gp3` berukuran 20 GB dengan 3,000 IOPS dan 125 MB/s. Pasang ke sebuah instance Linux EC2. Simulasikan peningkatan kapasitas menjadi 50 GB dan throughput menjadi 250 MB/s secara dinamis menggunakan perintah:
   ```bash
   aws ec2 modify-volume --volume-id <VOL_ID> --size 50 --throughput 250
   ```
   Lakukan verifikasi pembesaran partisi di tingkat sistem operasi menggunakan `lsblk`, `growpart`, dan `resize2fs` (atau `xfs_growfs`) tanpa memutus koneksi server.

2. **Audit S3 Incomplete Multipart Uploads**:
   Tuliskan perintah AWS CLI untuk mendeteksi sisa partisi multipart upload yang menggantung pada bucket target dan hapus partisi tersebut untuk menghemat biaya:
   ```bash
   aws s3api list-multipart-uploads --bucket <BUCKET_NAME>
   aws s3api abort-multipart-upload --bucket <BUCKET_NAME> --key <KEY> --upload-id <UPLOAD_ID>
   ```

---

## 19. Challenge
Rancang arsitektur penyimpanan end-to-end untuk platform perayap web (*web crawler*) berskala petabyte dengan parameter berikut:
1. Ribuan worker pods di Amazon EKS menulis data mentah (HTML raw files) secara koncurrent.
2. Pipeline analitik harian memproses data mentah tersebut dan menghasilkan file Apache Parquet terkompresi.
3. Raw data harus disimpan selama 14 hari dalam kondisi *read-accessible* cepat, setelah itu dipindahkan ke cold storage selama 60 hari, lalu dihapus otomatis.
4. Parquet data harus disimpan selamanya dengan jaminan tidak dapat dihapus selama 3 tahun pertama (regulatory compliance), direplikasi ke region lain dengan SLA replikasi $<15$ menit.
5. Susun skema pemilihan jenis subsistem penyimpanan (EBS vs EFS vs S3 vs FSx) untuk setiap tahapan, sertakan kalkulasi pertimbangan biaya/performa dan rancangan template konfigurasi Terraform deklaratif.

---

## 20. Summary
- **Subsistem penyimpanan AWS dirancang spesifik untuk beban kerja tertentu**: EBS untuk latensi sub-milidetik per-node (block device), EFS untuk standard POSIX multi-instance sharing, FSx untuk file-system terspesialisasi (Windows, HPC Lustre, NetApp ONTAP), dan S3 sebagai data lake tak terbatas berbasis objek.
- **Siklus hidup data (Lifecycle Management) adalah keharusan operasional**: Mengatur transisi S3 Standard $\to$ Standard-IA $\to$ Glacier $\to$ Deep Archive secara terukur memangkas TCO penyimpanan hingga $95\%$.
- **Perlindungan data modern bergantung pada immutability**: Menggunakan S3 Object Lock (Compliance Mode) dan AWS Backup Vault Lock memastikan data kebal terhadap modifikasi dan penghapusan paksa, melindungi integritas bisnis dari ancaman ransomware dan kegagalan kepatuhan audit.
- **Optimasi arsitektural membutuhkan pemahaman trade-off**: Hindari kesalahan umum seperti alokasi objek kecil di kelas IA/Glacier, salah memilih filesystem pada EBS Multi-Attach, atau mengabaikan potongan incomplete multipart upload yang tidak tampak pada inspeksi rutin.