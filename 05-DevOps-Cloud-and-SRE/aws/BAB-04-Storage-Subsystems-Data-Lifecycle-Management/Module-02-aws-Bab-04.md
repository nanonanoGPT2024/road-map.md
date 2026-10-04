# BAB 04: Storage Subsystems & Data Lifecycle Management
## MODULE 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis dan Mengimplementasikan Pola Penyimpanan Multi-Tier**: Merancang arsitektur penyimpanan AWS hibrida yang menggabungkan Amazon S3, EBS, dan EFS dengan memetakan kebutuhan beban kerja terhadap karakteristik I/O, latensi, dan pola akses.
- **Mengorkestrasi Otomatisasi Lifecycle Data Tingkat Lanjut**: Mengonfigurasi S3 Lifecycle Rules terdistribusi, S3 Intelligent-Tiering, S3 Object Lock (WORM compliance), dan AWS Data Lifecycle Manager (DLM) untuk volume EBS skala ribuan instans.
- **Mengoptimalkan Throughput dan IOPS Penyimpanan Terdistribusi**: Mengatasi bottleneck performa pada S3 (*request rate limits*, partisi *prefix*), EBS (*burst bucket exhaustion*, *queue length*, *I/O size alignment*), dan EFS (*bursting vs. provisioned vs. elastic throughput*).
- **Membangun Arsitektur Disaster Recovery (DR) dan Replikasi Lintas Wilayah**: Mengimplementasikan S3 Cross-Region Replication (CRR) dengan enkripsi KMS multi-region, EBS Fast Snapshot Restore (FSR), dan strategi sinkronisasi data menggunakan AWS DataSync.
- **Menerapkan Enkripsi dan Tata Kelola Keamanan End-to-End**: Mengonfigurasi enkripsi data saat transit (TLS 1.3) dan saat istirahat (SSE-KMS, SSE-C, EBS Default Encryption) dengan validasi kontrol akses berbasis IAM ABAC/RBAC dan S3 Bucket Policies yang ketat.

---

### 2. Prerequisites
Sebelum mempelajari modul ini, peserta wajib memahami:
- **Fondasi Jaringan AWS**: Amazon VPC, Private Subnets, Route Tables, VPC Endpoints (Gateway Endpoint untuk S3, Interface Endpoint/PrivateLink untuk API AWS).
- **Dasar-dasar IAM**: Identity-based policies, Resource-based policies, KMS Key Grants, dan evaluasi *Principal-Action-Resource-Condition*.
- **Konsep Storage Fundamental**: Perbedaan fundamental antara Object Storage (Key-Value), Block Storage (Raw disk blocks via protocol NVMe/SCSI), dan File Storage (POSIX filesystem, distributed NFSv4).
- **Tooling**: Terbiasa menggunakan AWS CLI v2, Terraform/OpenTofu (sintaks HCL), dan Python 3.11+ dengan library `boto3`.

---

### 3. Concept & Internal Architecture (Mendalam)

Penyimpanan di AWS dirancang dengan arsitektur mikro-layanan terdistribusi yang sangat terspesialisasi. Memahami mekanisme internal lapisan fisik dan logis sangat krusial untuk mencegah degradasi performa pada skala enterprise.

```
+-----------------------------------------------------------------------------------+
|                            APLIKASI & WORKLOADS                                   |
+-------------------------+-------------------------------+-------------------------+
                          |                               |
        REST API (HTTPS)  |             POSIX (NFSv4.1)   |         NVMe-over-PCIe
                          v                               v         (Nitro System)
+----------------------------------+  +----------------------------------+  +-------v-------+
|            AMAZON S3             |  |            AMAZON EFS            |  |  AMAZON EBS   |
+----------------------------------+  +----------------------------------+  +---------------+
| Partition Routing Index (Prefix) |  | Metadata Server Fleet            |  | Nitro Card    |
| (LSM-Tree Distributed Shards)    |  | (Distributed Consensus)          |  | Offload Engine|
+----------------------------------+  +----------------------------------+  +-------+-------+
| Storage Node Fleet               |  | Striped Storage Node Fleet       |          |
| (Erasure Coding 8+4 / 12+4)      |  | (Multi-AZ Synchronous Write)     |          | Network
+----------------------------------+  +----------------------------------+          v (EBS Bus)
| Hard Disks (HDD) & Flash (NVMe)  |  | SSD Arrays (Multi-AZ Replicated) |  +---------------+
| Multi-AZ Physical Placement      |  |                                  |  | SAN / NVMe-oF |
+----------------------------------+  +----------------------------------+  | Storage Clust |
                                                                            +---------------+
```

#### 3.1. Amazon S3: Distributed Key-Value Store & Partitioning Internals
Amazon S3 bukan sistem berkas hierarki, melainkan sistem *distributed object store* berbasis *key-value*.
- **Partisi Prefix dan Scaling**: Direktori dalam S3 hanyalah string representasi kunci (`folder1/folder2/file.txt`). S3 menggunakan skema partisi internal berbasis *LSM-Tree* (*Log-Structured Merge-tree*). Setiap partisi prefix secara otomatis mendukung hingga:
  - **3.500 permintaan PUT/POST/DELETE per detik** per prefix.
  - **5.500 permintaan GET/HEAD per detik** per prefix.
  Ketika beban request melebihi ambang batas ini, S3 secara otomatis memecah (*split*) partisi secara horizontal berdasarkan rentang leksikografis kunci.
- **Durabilitas & Erasure Coding**: S3 Standard dirancang untuk durabilitas $99.999999999\%$ (11 9s). Data dipecah menjadi beberapa *chunk* data dan paritas menggunakan algoritma *Reed-Solomon Erasure Coding* (misal: skema 8+4 atau sejenisnya) dan didistribusikan ke minimal 3 Availability Zones (AZ) yang terpisah secara geografis dan berdaya independen. S3 mampu menoleransi kehilangan total 1 AZ dan degradasi parsial di AZ lain tanpa kehilangan data atau aksesibilitas.
- **S3 Express One Zone**: Berbeda dengan S3 Standard yang mengutamakan multi-AZ durability, Express One Zone menggunakan arsitektur *single-AZ high-performance distributed NVMe* yang terintegrasi langsung dengan jaringan latensi rendah AWS. Ini memangkas latensi akses p99 hingga satu digit milidetik ($<10\text{ ms}$) dan meniadakan penalti replikasi sinkron antar-AZ.

#### 3.2. Amazon EBS: The Nitro System & Block Express Engine
Amazon EBS menyediakan persistent block storage yang dipasang ke Amazon EC2 melalui jaringan virtual penyimpanan.
- **AWS Nitro System Card Offload**: Pada instans berbasis Nitro, I/O EBS tidak lagi diproses oleh CPU host atau hypervisor Xen/KVM tradisional. Sebuah ASIC fisik khusus (Nitro Card for Storage) mengeksekusi stack virtualisasi NVMe over PCIe. Host OS melihat EBS sebagai NVMe drive lokal langsung, memangkas *jitter* latensi I/O hingga mendekati nol.
- **EBS io2 Block Express**: Menggunakan arsitektur jaringan khusus berbasis *Scalable Reliable Datagram* (SRD) yang berjalan di atas AWS Nitro Network Card. SRD menggantikan TCP dengan *multipath packet spraying* dinamis untuk menghindari *incast congestion*. Ini memungkinkan io2 Block Express mencapai:
  - Sub-milidetik latensi konsisten ($< 250\ \mu\text{s}$).
  - Hingga **256.000 IOPS** dan **4.000 MB/s throughput** per volume.
  - Rasio IOPS:GB hingga **1.000:1**.
- **Credit Bucket Mechanism (gp2 vs. gp3)**: Volume *gp2* menggunakan model *I/O burst bucket* berbasis kapasitas (3 IOPS/GB, *burst* hingga 3.000 IOPS selama waktu terbatas). Sebaliknya, *gp3* memisahkan kapasitas dari IOPS dan Throughput secara independen melalui *provisioned reservation* pada Nitro storage pool, dengan baseline 3.000 IOPS dan 125 MB/s tanpa bergantung pada ukuran gigabyte.

#### 3.3. Amazon EFS: Distributed Shared File System Internals
EFS adalah implementasi terdistribusi dari protokol Network File System versi 4.0 dan 4.1 (NFSv4/NFSv4.1).
- **Arsitektur Tanpa Server & Metadata Scaling**: EFS tidak menggunakan *NFS server instance* tunggal. Setiap read/write dialihkan ke armada node metadata dan data terdistribusi yang tersebar di multi-AZ. Operasi modifikasi metadata (seperti `ls -l` rekursif, `find`, atau file create intensif) memerlukan konsensus terdistribusi antar-AZ. Oleh karena itu, latensi operasi metadata lebih tinggi dibanding block storage lokal, namun throughput agregat untuk operasi file terdistribusi dapat diskalakan hampir tanpa batas.
- **Throughput Modes**:
  - *Bursting*: Kapasitas menentukan *burst throughput* (50 KB/s per GiB baseline, burst hingga 100 MB/s).
  - *Provisioned*: Diberikan kapasitas throughput tetap independen dari volume data (berbayar per MB/s-bulan).
  - *Elastic*: Otomatis diskalakan secara dinamis mengikuti beban kerja I/O baca/tulis tanpa alokasi di muka, cocok untuk pola I/O yang sangat *spiky* dan tidak terprediksi.

---

### 4. Why & What

#### Mengapa Tidak Menggunakan Satu Jenis Storage Saja?
Tidak ada subsistem penyimpanan tunggal yang dapat mengoptimalkan parameter Latensi, Throughput, Akses Bersama (*Shared Access*), dan Biaya (*Cost*) secara simultan.

```
       LATENSI RENDAH (< 1ms)
               /\
              /  \
             /    \
   Amazon EBS      \
 (Block Storage)    \
       /             \
      /               \
     /                 \
    /___________________\
BIAYA RENDAH          MULTI-NODE CONCURRENCY
(Amazon S3)           (Amazon EFS)
```

1. **Amazon S3**: Optimal untuk data tidak terstruktur (*unstructured*), analisis skala besar (Data Lakehouse), backup, dan media streaming. Kelemahan: Tidak memiliki POSIX append-in-place; modifikasi 1-byte memerlukan upload ulang seluruh objek.
2. **Amazon EBS**: Optimal untuk *transactional databases* (PostgreSQL, MySQL, Cassandra) yang membutuhkan latensi mikrodetik, operasi in-place write, dan kontrol langsung atas filesystem (XFS, ext4). Kelemahan: Terikat pada 1 Availability Zone tertentu (kecuali skenario EBS Multi-Attach yang hanya mendukung single-AZ cluster-aware filesystem seperti GFS2).
3. **Amazon EFS**: Optimal untuk beban kerja yang memerlukan POSIX filesystem yang diakses secara bersamaan oleh ribuan instans (Kubernetes PersistentVolumes/StatefulSets, armada rendering web, *shared home directories*). Kelemahan: Biaya per gigabyte lebih tinggi daripada S3; latensi metadata lebih lambat dibandingkan EBS.

---

### 5. How (Workflow Detail)

#### 5.1. Alur Lifecycle Management dan Tiering Transisi S3
Data yang masuk ke S3 harus dikelola siklus hidupnya untuk menekan *Total Cost of Ownership* (TCO) melalui transisi bertahap:

```
[Ingestion] -> S3 Standard (Data Panas: Active Analytics / API Processing)
                   |
     (30 Hari)     v Transition Rule
               S3 Standard-Infrequent Access (S3 Standard-IA)
                   |
     (90 Hari)     v Transition Rule
               S3 Glacier Flexible Deep Recovery (Arsip Tahunan)
                   |
     (180 Hari)    v Transition Rule
               S3 Glacier Deep Archive (Data Regulasi / Compliance WORM)
                   |
     (365 Hari)    v Expiration Rule
               [Permanent Deletion via Object Lock Enforced Expiration]
```

#### 5.2. EBS Fast Snapshot Restore (FSR) & Snapshot Lifecycle Orchestration
Pengambilan snapshot EBS dilakukan secara *point-in-time incremental* ke S3. Namun, ketika volume baru dibuat dari snapshot, blok data belum langsung berada di EBS hardware storage lokal (*lazy-loading/lazy-restore*). Akibatnya, operasi baca pertama pada blok tersebut akan mengalami penalti latensi tinggi (dikenal sebagai *storage block hydration penalty*).
- **Mekanisme FSR**: Mengaktifkan FSR pada snapshot tertentu di Availability Zone target akan melakukan pra-alokasi (*pre-warming*) struktur metadata dan blok data secara instan. Volume yang di-instansiasi dari FSR snapshot langsung memberikan performa I/O penuh tanpa latensi hidrasi awal.

---

### 6. Analogy & Diagram ASCII

#### Analogi Komparatif Subsistem Penyimpanan
- **Amazon EBS** diibaratkan seperti **Internal NVMe SSD di laptop Anda**: Sangat cepat, terhubung langsung ke motherboard (PCIe bus), hanya dapat diakses oleh satu laptop, namun jika laptop dipindah ke benua lain, drive tersebut tidak ikut jika dicabut secara kasar tanpa prosedur unmount.
- **Amazon EFS** diibaratkan seperti **Network Shared Folder (NAS/NFS di kantor)**: Seluruh departemen (ratusan laptop) dapat membuka folder yang sama, membaca dan menulis dokumen bersamaan. Sedikit lebih lambat saat membuka ribuan folder kecil sekaligus karena latensi jaringan Wi-Fi/kabel LAN, namun sangat praktis untuk kolaborasi.
- **Amazon S3** diibaratkan seperti **Gudang Kontainer Logistik Internasional Terotomatisasi**: Anda tidak bisa masuk dan memodifikasi isi paket di dalam kontainer; Anda harus mengirim paket baru dengan label identifikasi unik (URL/URI). Skala gudang tidak terbatas, barang dijamin tidak akan hilang berkat proteksi militer multi-lokasi, dan biayanya sangat murah untuk penyimpanan jangka panjang.

#### Diagram Arsitektur Enterprise Multi-Tier Storage Workflow

```
+---------------------------------------------------------------------------------------------------------+
|                                          AWS REGION PRIMARY (us-east-1)                                 |
|                                                                                                         |
|  +-------------------------------------------------------+   +---------------------------------------+  |
|  | VPC PROD (10.0.0.0/16)                                |   | S3 VPC Gateway Endpoint               |  |
|  |                                                       |   +-------------------+-------------------+  |
|  |  +------------------------+  +---------------------+  |                       |                      |
|  |  | EC2 Worker Node A      |  | EC2 Worker Node B   |  |                       |                      |
|  |  | AZ-a                   |  | AZ-b                |  |                       v                      |
|  |  |                        |  |                     |  |         +---------------------------+        |
|  |  |  +------------------+  |  |  +---------------+  |  |         | S3 Data Lake (Bucket A)   |        |
|  |  |  | EBS Boot (gp3)   |  |  |  | EBS Boot (gp3)|  |  |         | - Server-Side KMS Enc     |        |
|  |  |  +------------------+  |  |  +---------------+  |  |         | - Object Lock (Compliance)|        |
|  |  |  | EBS Data (io2)   |  |  |  | EBS Data (io2)|  |  |         | - Intelligent-Tiering     |        |
|  |  |  +--------+---------+  |  |  +-------+-------+  |  |         +-------------+-------------+        |
|  |  +-----------|------------+  +----------|----------+  |                       |                      |
|  |              |                          |             |                       | S3 Cross-Region      |
|  |              +------------+-------------+             |                       | Replication (CRR)    |
|  |                           v                           |                       |                      |
|  |              +-------------------------+              |                       |                      |
|  |              | EFS Mount Target Fleet  |              |                       |                      |
|  |              | (NFSv4.1 Multi-AZ Mount)|              |                       |                      |
|  |              +-------------------------+              |                       |                      |
|  +-------------------------------------------------------+                       |                      |
+----------------------------------------------------------------------------------|----------------------+
                                                                                   |
                                                                                   v
+---------------------------------------------------------------------------------------------------------+
|                                          AWS REGION DISASTER RECOVERY (us-west-2)                       |
|                                                                                                         |
|                                                                    +---------------------------+        |
|                                                                    | S3 Backup Target (Bucket B|        |
|                                                                    | - Replica KMS Key Re-enc  |        |
|                                                                    | - Deep Archive Lifecycle  |        |
|                                                                    +---------------------------+        |
+---------------------------------------------------------------------------------------------------------+
```

---

### 7. Practical Implementation (Standar Industri)

Implementasi di bawah ini menggunakan **Terraform / OpenTofu** untuk mendirikan arsitektur penyimpanan kelas enterprise: S3 dengan enkripsi KMS mandiri, Object Lock, Replication, Lifecycle, serta EFS Elastic filesystem terintegrasi.

```hcl
# main.tf - Enterprise AWS Storage Architecture
terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.35"
    }
  }
}

provider "aws" {
  region = "us-east-1"
  alias  = "primary"
}

provider "aws" {
  region = "us-west-2"
  alias  = "dr"
}

# -----------------------------------------------------------------------------
# 1. KMS KEYS FOR AT-REST ENCRYPTION
# -----------------------------------------------------------------------------
resource "aws_kms_key" "primary_s3_key" {
  provider                = aws.primary
  description             = "KMS Key for Primary S3 Storage"
  deletion_window_in_days = 30
  enable_key_rotation     = true
}

resource "aws_kms_key" "dr_s3_key" {
  provider                = aws.dr
  description             = "KMS Key for DR S3 Storage"
  deletion_window_in_days = 30
  enable_key_rotation     = true
}

# -----------------------------------------------------------------------------
# 2. S3 BUCKET DESTINATION (DR REGION)
# -----------------------------------------------------------------------------
resource "aws_s3_bucket" "dr_bucket" {
  provider      = aws.dr
  bucket        = "enterprise-vault-dr-storage-098234"
  force_destroy = false
}

resource "aws_s3_bucket_versioning" "dr_versioning" {
  provider = aws.dr
  bucket   = aws_s3_bucket.dr_bucket.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "dr_encryption" {
  provider = aws.dr
  bucket   = aws_s3_bucket.dr_bucket.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.dr_s3_key.arn
      sse_algorithm     = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

# -----------------------------------------------------------------------------
# 3. REPLICATION IAM ROLE
# -----------------------------------------------------------------------------
resource "aws_iam_role" "replication_role" {
  provider = aws.primary
  name     = "s3-cross-region-replication-role"

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
  provider = aws.primary
  name     = "s3-replication-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "s3:GetReplicationConfiguration",
          "s3:ListBucket"
        ]
        Effect   = "Allow"
        Resource = [aws_s3_bucket.primary_bucket.arn]
      },
      {
        Action = [
          "s3:GetObjectVersionForReplication",
          "s3:GetObjectVersionAcl",
          "s3:GetObjectVersionTagging"
        ]
        Effect   = "Allow"
        Resource = ["${aws_s3_bucket.primary_bucket.arn}/*"]
      },
      {
        Action = [
          "s3:ReplicateObject",
          "s3:ReplicateDelete",
          "s3:ReplicateTags"
        ]
        Effect   = "Allow"
        Resource = ["${aws_s3_bucket.dr_bucket.arn}/*"]
      },
      {
        Action = [
          "kms:Decrypt"
        ]
        Effect   = "Allow"
        Resource = [aws_kms_key.primary_s3_key.arn]
      },
      {
        Action = [
          "kms:Encrypt"
        ]
        Effect   = "Allow"
        Resource = [aws_kms_key.dr_s3_key.arn]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "replication_attach" {
  provider   = aws.primary
  role       = aws_iam_role.replication_role.name
  policy_arn = aws_iam_policy.replication_policy.arn
}

# -----------------------------------------------------------------------------
# 4. S3 PRIMARY BUCKET (WITH WORM OBJECT LOCK & LIFECYCLE)
# -----------------------------------------------------------------------------
resource "aws_s3_bucket" "primary_bucket" {
  provider            = aws.primary
  bucket              = "enterprise-vault-primary-storage-098234"
  object_lock_enabled = true
}

resource "aws_s3_bucket_versioning" "primary_versioning" {
  provider = aws.primary
  bucket   = aws_s3_bucket.primary_bucket.id
  versioning_configuration {
    status = "Enabled"
  }
}

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

resource "aws_s3_bucket_object_lock_configuration" "lock_config" {
  provider = aws.primary
  bucket   = aws_s3_bucket.primary_bucket.id

  rule {
    default_retention {
      mode = "COMPLIANCE"
      days = 90
    }
  }
  depends_on = [aws_s3_bucket.primary_bucket]
}

resource "aws_s3_bucket_replication_configuration" "crr_config" {
  provider = aws.primary
  role     = aws_iam_role.replication_role.arn
  bucket   = aws_s3_bucket.primary_bucket.id

  rule {
    id     = "ReplicateToDR"
    status = "Enabled"

    source_selection_criteria {
      sse_kms_encrypted_objects {
        status = "Enabled"
      }
    }

    destination {
      bucket        = aws_s3_bucket.dr_bucket.arn
      storage_class = "STANDARD"

      encryption_configuration {
        replica_kms_key_id = aws_kms_key.dr_s3_key.arn
      }
    }
  }
  depends_on = [aws_s3_bucket_versioning.primary_versioning]
}

resource "aws_s3_bucket_lifecycle_configuration" "primary_lifecycle" {
  provider = aws.primary
  bucket   = aws_s3_bucket.primary_bucket.id

  rule {
    id     = "Tiering-and-Archival"
    status = "Enabled"

    filter {
      prefix = "logs/"
    }

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

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

# -----------------------------------------------------------------------------
# 5. AMAZON EFS: ELASTIC MULTI-AZ DISTRIBUTED STORAGE
# -----------------------------------------------------------------------------
resource "aws_efs_file_system" "shared_storage" {
  provider         = aws.primary
  creation_token   = "enterprise-k8s-shared-storage"
  performance_mode = "generalPurpose"
  throughput_mode  = "elastic"
  encrypted        = true
  kms_key_id       = aws_kms_key.primary_s3_key.arn

  lifecycle_policy {
    transition_to_ia = "AFTER_30_DAYS"
  }

  lifecycle_policy {
    transition_to_primary_storage_class = "AFTER_1_ACCESS"
  }

  tags = {
    Name        = "Shared-EFS-K8s"
    Environment = "Production"
  }
}
```

#### Automasi Manajemen Snapshot EBS Melalui Script Operasional (Python `boto3`)
Skrip berikut bertugas mengaudit volume EBS gp2 yang tidak teroptimasi, mengonversinya ke gp3 secara *zero-downtime*, dan membuat snapshot retensi tinggi sebelum proses migrasi dieksekusi.

```python
#!/usr/bin/env python3
"""
EBS Optimization & Snapshot Automation Engine
Target: Convert legacy gp2 volumes to cost-effective gp3 with safe Snapshot baseline.
"""

import sys
import logging
from typing import List, Dict, Any
import boto3
from botocore.exceptions import ClientError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("EBSOptimizer")

def get_gp2_volumes(ec2_client: Any) -> List[Dict[str, Any]]:
    """Mengambil seluruh volume gp2 yang berstatus in-use atau available."""
    try:
        paginator = ec2_client.get_paginator('describe_volumes')
        page_iterator = paginator.paginate(
            Filters=[{'Name': 'volume-type', 'Values': ['gp2']}]
        )
        volumes = []
        for page in page_iterator:
            volumes.extend(page['Volumes'])
        return volumes
    except ClientError as exc:
        logger.error(f"Gagal mendeskripsikan volume: {exc}")
        raise

def optimize_volume_to_gp3(ec2_client: Any, volume: Dict[str, Any]) -> None:
    volume_id = volume['VolumeId']
    size_gib = volume['Size']
    az = volume['AvailabilityZone']

    logger.info(f"Memproses Volume: {volume_id} (Ukuran: {size_gib} GiB, AZ: {az})")

    # 1. Buat Pre-migration Snapshot
    try:
        snap_desc = f"Automated pre-migration snapshot of {volume_id} before gp3 conversion"
        snapshot = ec2_client.create_snapshot(
            VolumeId=volume_id,
            Description=snap_desc,
            TagSpecifications=[{
                'ResourceType': 'snapshot',
                'Tags': [
                    {'Key': 'AutoCreated', 'Value': 'true'},
                    {'Key': 'SourceVolume', 'Value': volume_id},
                    {'Key': 'MigrationTarget', 'Value': 'gp3'}
                ]
            }]
        )
        logger.info(f"Snapshot terinisiasi: {snapshot['SnapshotId']} untuk volume {volume_id}")
    except ClientError as exc:
        logger.error(f"Snapshot gagal untuk {volume_id}. Menghentikan migrasi volume ini: {exc}")
        return

    # 2. Modifikasi Volume ke gp3 secara Live (Elastic Volumes feature)
    try:
        response = ec2_client.modify_volume(
            VolumeId=volume_id,
            VolumeType='gp3',
            Iops=3000,           # Baseline standard gp3
            Throughput=125       # Baseline MiB/s
        )
        mod_status = response['VolumeModification']['ModificationState']
        logger.info(f"Volume {volume_id} sukses dimodifikasi ke gp3. Status: {mod_status}")
    except ClientError as exc:
        logger.error(f"Gagal memodifikasi volume {volume_id} ke gp3: {exc}")

def main() -> None:
    region = "us-east-1"
    ec2_client = boto3.client('ec2', region_name=region)
    logger.info(f"Mulai pemindaian volume EBS gp2 di region {region}...")
    
    volumes = get_gp2_volumes(ec2_client)
    logger.info(f"Ditemukan {len(volumes)} volume gp2 yang memenuhi kriteria migrasi.")

    for vol in volumes:
        optimize_volume_to_gp3(ec2_client, vol)

if __name__ == "__main__":
    main()
```

---

### 8. Real-World Case Study (Enterprise Scale)

#### Kasus: Arsitektur Financial Core Settlement Platform (15 Petabytes)
- **Karakteristik Skala**:
  - $15\text{ PB}$ arsip transaksi keuangan teregulasi (SEC Rule 17a-4 compliance).
  - 85.000 TPS (*transactions per second*) puncak pada jam kliring bursa.
  - Latensi tulis basis data analitik transaksi $< 2\text{ ms}$.
- **Masalah**:
  Arsitektur lama menyimpan semua raw ledger dan index langsung pada EBS io2 volume berkapasitas masif yang terpasang di armada EC2 raksasa.
  1. *Biaya Eksorbitan*: Pengeluaran penyimpanan mencapai $\$350.000$ per bulan akibat dependensi volume block storage untuk data dingin (*cold data*).
  2. *Compliance Violations*: Auditor internal menemukan celah di mana akun *privileged root* dapat mengeksekusi penghapusan database snapshot historis secara sepihak.
  3. *Rehydration Downtime*: Saat instance recovery, proses attach disk baru memicu latensi I/O ekstrim (blok belum di-*hydrate*).

#### Solusi Arsitektur
1. **Decoupled Engine (Compute & Storage Split)**:
   - Volume aktif database dipindahkan ke **EBS io2 Block Express** yang dirampingkan hanya untuk 7 hari transaksi aktif (Hot Window).
   - Seluruh transaksi berumur $> 7$ hari dialirkan secara *micro-batch* ke **Amazon S3 Standard** menggunakan format Apache Parquet.
2. **Immutability Enforcement**:
   - S3 diaktifkan dengan **S3 Object Lock** dalam format **COMPLIANCE Mode** dengan retensi 7 tahun. Bahkan akun AWS Organization Master/Root tidak dapat mematikan lock atau menghapus versi objek tersebut sebelum jangka waktu retensi habis.
3. **Automasi Tiering & Replikasi**:
   - **S3 Intelligent-Tiering** menangani file analisa kuartalan tanpa ada penalti pengambilan data (*retrieval fee*).
   - Replikasi otomatis ke region sekunder dengan **S3 CRR + KMS Multi-Region Key Encrypted Replication** menjamin $RPO < 15\text{ menit}$.
4. **Hasil Terukur**:
   - **Penurunan Biaya**: Pengeluaran storage turun sebesar $68\%$ (dari $\$350\text{k/bulan}$ menjadi $\$112\text{k/bulan}$).
   - **Kepatuhan Audit**: $100\%$ lulus audit FINRA & SEC berkat WORM compliance locking.
   - **P99 Latency Settlement**: Turun dari $4.8\text{ ms}$ ke $1.2\text{ ms}$ menggunakan arsitektur gp3/io2 Block Express terpisah.

---

### 9. Trade-Offs Matrix

| Vektor Arsitektur | Amazon S3 Standard | Amazon S3 Glacier Deep Archive | Amazon EBS (gp3) | Amazon EBS (io2 Block Express) | Amazon EFS (Elastic) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Tipe Storage** | Object (Key-Value) | Object (Tape/Cold Disk Archival) | Block Storage | Block Storage | Distributed File (POSIX) |
| **Pola Akses** | REST HTTP(S) API | Batch Restorasi Asinkron | Single Instans Host Bus | Multi-Attach / Single Host | Ribuan Klien Multi-AZ |
| **Throughput Baseline** | Otomatis partisi ($>100\text{ Gbps}$ aggregate) | Bandwidth transfer rendah, kuota recovery terbatas | $125\text{ MiB/s}$ baseline up to $1.000\text{ MiB/s}$ | Up to $4.000\text{ MiB/s}$ | Skala dinamis mengikuti I/O beban kerja |
| **Typical Latency** | $10 - 20\text{ ms}$ | $12 - 48\text{ jam}$ (Retrieval latency) | $1 - 3\text{ ms}$ | $< 250\ \mu\text{s}$ (Sub-milidetik) | $1 - 3\text{ ms}$ (Data), $10 - 20\text{ ms}$ (Metadata) |
| **Max IOPS** | Tidak terikat batas IOPS tradisional | N/A | $16.000\text{ IOPS}$ | $256.000\text{ IOPS}$ | N/A (Skala otomatis) |
| **Biaya Relatif ($/GB)** | Sangat Rendah ($\sim \$0.023$) | Terendah ($\sim \$0.00099$) | Menengah ($\sim \$0.08$) | Tinggi ($\sim \$0.125$ + Biaya IOPS) | Menengah-Tinggi ($\sim \$0.30$) |
| **Durabilitas SLA** | $99.999999999\%$ (11 9s) | $99.999999999\%$ (11 9s) | $99.8\% - 99.9\%$ | $99.999\%$ (Five 9s AFR 0.001%) | $99.999999999\%$ (11 9s) |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Kesalahan: S3 503 "SlowDown" Error
- **Penyebab**: Aplikasi mengirimkan lebih dari 3.500 write/detik atau 5.500 read/detik ke dalam satu pola path/prefix statis tunggal (misal: `s3://my-bucket/logs/2026-03-29/file.json`), melampaui kemampuan internal partition shard S3 sebelum partisi sempat dipecah (*split*).
- **Troubleshooting & Remediasi**:
  1. Tambahkan entropy/hash pada prefix: `s3://my-bucket/logs/<hash-prefix>/2026-03-29/file.json`.
  2. Implementasikan *Exponential Backoff with Full Jitter* pada client SDK untuk seluruh request S3.
  3. Gunakan S3 Express One Zone untuk beban kerja extreme-throughput low-latency.

#### 2. Kesalahan: EBS Micro-bursting Exhaustion & Queue Length Surge
- **Penyebab**: Volume gp2 kehabisan IOPS burst credits, atau volume gp3 dikonfigurasi dengan batas throughput di bawah kapasitas I/O aplikasi. Metrik CloudWatch menunjukkan `VolumeQueueLength > 5` dan latensi I/O melonjak drastis dari $2\text{ ms}$ ke $500\text{ ms}$, namun metrik CPU utilitas server tetap rendah.
- **Troubleshooting**:
  1. Analisis CloudWatch Metric: `VolumeThroughputPercentage` dan `VolumeConsumedReadWriteOps`.
  2. Jika `VolumeQueueLength` tinggi bersamaan dengan `BurstBalance = 0%`, segera ubah volume menjadi **gp3** atau tingkatkan Provisioned IOPS secara live tanpa restart menggunakan AWS Elastic Volumes API.

#### 3. Kesalahan: Replikasi S3 Gagal Secara Senyap (*Silent Replication Drop*)
- **Penyebab**: Mengaktifkan S3 Cross-Region Replication pada bucket terenkripsi AWS KMS, namun Role IAM replikasi tidak memiliki izin `kms:Decrypt` pada KMS Key Region Asal, atau tidak memiliki izin `kms:Encrypt` pada KMS Key Region Tujuan.
- **Troubleshooting**:
  1. Cek metrik CloudWatch `OperationsFailedReplication`.
  2. Jalankan perintah: `aws s3api head-object --bucket <source-bucket> --key <key>` dan periksa field `ReplicationStatus`. Jika nilainya `FAILED`, validasi Key Policy pada KMS key di kedua region. Key policy KMS harus secara eksplisit mengizinkan ARN service role replikasi.

---

### 11. Best Practices (Production Checklist)

- [ ] **Enkripsi**: Semua bucket S3 harus memblokir upload tanpa enkripsi menggunakan Bucket Policy (`aws:SecureTransport` dan enforce `sse-kms`).
- [ ] **Blokir Public Access**: Aktifkan **S3 Block Public Access** di level *AWS Account Level* dan *Bucket Level* secara menyeluruh, kecuali bucket hosting publik yang terisolasi.
- [ ] **Optimasi Biaya EBS**: Audit seluruh volume gp2 yang ada dan migrasikan ke gp3 (menghasilkan efisiensi instan minimum $20\%$ pada biaya penyimpanan).
- [ ] **EBS Volume Tagging**: Terapkan tag wajib (`Environment`, `Owner`, `BackupPolicy`) untuk seluruh volume dan snapshot agar dapat dikelola oleh AWS Data Lifecycle Manager (DLM).
- [ ] **EFS Mount Options**: Selalu gunakan DNS mount helper (`amazon-efs-utils`) dan pasang flag `tls` serta `iam` saat melakukan mount NFS ke EC2 atau container task:
  ```bash
  mount -t efs -o tls,iam,accesspoint=fsap-12345678 fs-12345678:/ /mnt/efs
  ```
- [ ] **S3 Object Versioning & Lifecycle**: Jangan pernah mengaktifkan versioning tanpa membersihkan *Noncurrent Version* melalui S3 Lifecycle Rules, atau ukuran bucket akan tumbuh tak terbatas akibat penumpukan data lama.
- [ ] **S3 Bucket Key**: Selalu aktifkan fitur **S3 Bucket Keys** saat menggunakan SSE-KMS untuk mengurangi frekuensi pemanggilan KMS API hingga $99\%$, menghindari lonjakan biaya request KMS.

---

### 12. Hands-on Practice

Simpan seluruh file praktikum di direktori repositori: `hands-on/m02/`

#### Langkah 1: Inisialisasi Workspace
```bash
mkdir -p hands-on/m02/
cd hands-on/m02/
```

#### Langkah 2: Buat Skrip Pengujian Latensi Block vs File Storage
Buat file `storage_benchmark.sh` untuk menguji performa throughput dan latensi write secara riil menggunakan `fio` (*Flexible I/O Tester*).

```bash
cat << 'EOF' > storage_benchmark.sh
#!/usr/bin/env bash
set -euo pipefail

TARGET_DIR="${1:-/tmp/benchmark}"
mkdir -p "${TARGET_DIR}"

echo "=========================================================="
echo "MENJALANKAN BENCHMARK I/O: ${TARGET_DIR}"
echo "=========================================================="

if ! command -v fio &> /dev/null; then
    echo "fio belum terpasang. Menginstal dependensi..."
    sudo yum install -y fio || sudo apt-get install -y fio
fi

# 1. Random Read/Write Test (Latensi & IOPS) - Simulasi Transaksional OLTP
echo "Menjalankan Test 1: Random Read/Write 4k (IOPS Stress)..."
fio --name=randrw_test \
    --directory="${TARGET_DIR}" \
    --ioengine=libaio \
    --direct=1 \
    --rw=randrw \
    --rwmixread=75 \
    --bs=4k \
    --size=512M \
    --numjobs=4 \
    --runtime=30 \
    --group_reporting \
    --output="${TARGET_DIR}/fio_randrw_result.txt"

# 2. Sequential Write Test (Throughput MB/s) - Simulasi Data Streaming / Logs
echo "Menjalankan Test 2: Sequential Write 1M (Throughput Stress)..."
fio --name=seqwrite_test \
    --directory="${TARGET_DIR}" \
    --ioengine=libaio \
    --direct=1 \
    --rw=write \
    --bs=1M \
    --size=1G \
    --numjobs=2 \
    --runtime=30 \
    --group_reporting \
    --output="${TARGET_DIR}/fio_seqwrite_result.txt"

echo "Benchmark selesai. Hasil output disimpan di:"
echo " - ${TARGET_DIR}/fio_randrw_result.txt"
echo " - ${TARGET_DIR}/fio_seqwrite_result.txt"
EOF

chmod +x storage_benchmark.sh
```

#### Langkah 3: Eksekusi dan Verifikasi
Jalankan benchmark pada direktori lokal EBS:
```bash
./storage_benchmark.sh /tmp/ebs-test
```
Amati nilai **read IOPS**, **write IOPS**, dan **latensi p99** pada berkas log hasil pengujian. Bandingkan jika direktori target diarahkan ke mount point Amazon EFS.

---

### 13. Exercises

#### Level Easy
Konfigurasikan AWS CLI untuk mengunggah file ke bucket S3 dengan memaksakan enkripsi server-side KMS menggunakan KMS Key ARN kustom, serta verifikasi bahwa metadata objek mengembalikan header SSE-KMS yang benar.
*Kriteria Penerimaan*: Perintah CLI mengembalikan status HTTP 200 dan parameter `ServerSideEncryption: "aws:kms"` terekam pada output `aws s3api head-object`.

#### Level Medium
Tulis modul Terraform deklaratif yang mengonfigurasi **AWS Data Lifecycle Manager (DLM)**. Modul ini wajib membuat snapshot harian otomatis pada seluruh EBS volume yang memiliki tag `SnapshotPolicy = "Gold"`, menyimpan 14 snapshot terakhir, dan melakukan replikasi snapshot tersebut ke region sekunder secara otomatis setiap 24 jam.
*Kriteria Penerimaan*: Konfigurasi lolos validasi `terraform validate` dan resource `aws_dlm_lifecycle_policy` terdefinisi dengan struktur rule yang valid sesuai provider AWS terbaru.

#### Level Hard
Buat script automasi menggunakan Python (`boto3`) yang memproses file besar ($>5\text{ GB}$) ke Amazon S3 menggunakan *Multipart Upload API* secara konkruen (*threading*). Script harus:
1. Menghitung checksum MD5 per chunk (masing-masing berukuran $16\text{ MB}$).
2. Menjalankan *retry mechanism* dengan exponential backoff untuk setiap partisi chunk yang gagal terunggah.
3. Melakukan *abort* otomatis terhadap seluruh proses multipart upload jika terjadi kegagalan fatal pada salah satu worker thread agar tidak menyisakan *orphan parts* yang memakan biaya storage.
*Kriteria Penerimaan*: File sukses diunggah, tervalidasi integritasnya via ETag S3, dan script menangani exception `ClientError` secara elegan tanpa memory leak.

---

### 14. Architecture Challenge

#### Skenario Kasus Edge
Anda adalah Principal Cloud Storage Architect di sebuah platform *Electronic Health Records (EHR)* skala global. Regulasi medis mewajibkan sistem Anda memenuhi ketentuan:
1. **Zero Data Tampering**: Rekam medis pasien tidak boleh dimodifikasi atau dihapus oleh siapapun (termasuk AWS Account Root User) selama 10 tahun sejak tanggal pembuatan.
2. **Kinerja Analitik Instan**: $5\%$ dari rekam medis (yang statusnya aktif) harus dapat diakses oleh puluhan microservices Kubernetes lintas AZ secara bersamaan via POSIX path dengan throughput read agregat $> 5.000\text{ MB/s}$.
3. **Penyusutan Biaya Drastis**: $95\%$ data yang berumur lebih dari 30 hari harus ditransisikan ke tier dengan biaya serendah mungkin tanpa merusak struktur tautan sistem yang telah dibangun.
4. **Resiliensi Regional**: Kegagalan total pada satu AWS Region primer tidak boleh mengakibatkan hilangnya data medis lebih dari 5 menit ($RPO \le 5\text{ menit}$) dan data di region pemulihan harus langsung berada dalam status *read-ready*.

#### Tugas Arsitektural Anda
- Rancang topologi penyimpanan end-to-end lengkap yang memadukan Amazon S3 (termasuk fitur locking dan replication), Amazon EFS (dengan lifecycle automation), dan mekanisme sinkronisasi data antar keduanya.
- Deskripsikan strategi pencegahan split-brain dan mekanisme penanganan *KMS Key Synchronization* lintas region.
- Susun dokumen desain arsitektur yang merinci:
  - Pemilihan tipe storage untuk tiap layer (ingestion, processing, retrieval, archival).
  - Alur data (*Data Flow Pipeline*) saat kondisi normal vs kondisi Disaster Recovery failover.
  - Mitigasi limit kuota dan biaya request API tersembunyi.

---

### 15. Quiz Evaluasi Pemahaman

#### 5 Pertanyaan Basic
1. Apa perbedaan arsitektural utama antara S3 Standard-Infrequent Access (S3 Standard-IA) dan S3 Standard dalam hal skema biaya?
2. Bagaimana mekanisme perhitungan throughput baseline pada volume Amazon EBS tipe gp3?
3. Apa perbedaan fungsional antara mode "Governance" dan mode "Compliance" pada Amazon S3 Object Lock?
4. Mengapa operasi direktori rekursif (seperti `find .` atau `ls -R`) pada Amazon EFS cenderung memiliki waktu eksekusi lebih lambat dibandingkan pada volume Amazon EBS lokal?
5. Fitur apa pada Amazon S3 yang harus diaktifkan sebagai prasyarat wajib sebelum Cross-Region Replication (CRR) dapat dikonfigurasi?

#### 5 Pertanyaan Intermediate
6. Jelaskan apa yang dimaksud dengan fenomena *storage rehydration penalty* saat volume EBS baru dibuat dari Amazon EBS Snapshot, dan bagaimana cara memitigasinya pada lingkungan produksi!
7. Bagaimana fitur *S3 Bucket Keys* mampu memangkas biaya pemanggilan API AWS KMS hingga lebih dari $90\%$ saat mengenkripsi ribuan objek S3 per detik?
8. Klien microservice Anda mengalami error `EBS.VolumeBurstBalanceExceeded` pada volume gp2. Jika Anda tidak ingin mengubah kapasitas penyimpanan (disk size), arsitektur apa yang harus diubah agar performa IOPS kembali normal?
9. Bagaimana AWS DataSync menjamin integritas data saat mentransfer petabyte data dari Amazon EFS ke Amazon S3 jika dibandingkan dengan script copy tradisional (`rsync` / `aws s3 sync`)?
10. Pada arsitektur Amazon EFS, apa perbedaan fundamental antara Throughput Mode *Provisioned* vs *Elastic* dalam konteks penanganan beban kerja yang sangat dinamis (*bursty workloads*)?

#### 3 Skenario Kasus Produksi
11. **Skenario 1**: Sebuah platform e-commerce mencatat jutaan gambar produk baru setiap hari pada bucket S3. Developer mengeluhkan bahwa setelah 6 bulan, biaya S3 membengkak 400% meskipun mereka telah menerapkan *Lifecycle Rule* untuk menghapus objek setelah 30 hari. Setelah diinvestigasi, objek masih tampak berada di dalam sistem penagihan. Apa kegagalan konfigurasi yang paling mungkin terjadi pada bucket S3 tersebut?
12. **Skenario 2**: Database PostgreSQL produksi berjalan di EC2 dengan data disk berbasis EBS gp3. Selama batch insert tengah malam, latensi tulis melonjak ke $80\text{ ms}$, namun metrik CloudWatch menunjukkan volume hanya menggunakan 2.000 dari 3.000 IOPS yang dialokasikan, dan Throughput hanya berada di $60\text{ MB/s}$ dari alokasi $125\text{ MB/s}$. Di mana letak bottleneck performa subsistem penyimpanan ini?
13. **Skenario 3**: Perusahaan Anda mengonfigurasi S3 Cross-Region Replication antar dua AWS Region dengan enkripsi SSE-KMS. Saat pengujian simulasi bencana (DR Drill), teknisi menemukan bahwa objek yang diunggah ke Region Utama berhasil terduplikasi, namun objek replika di Region B tidak dapat didekripsi oleh instance worker di Region B menggunakan role aplikasi mereka. Langkah perbaikan apa yang harus dilakukan?

---

### Kunci Jawaban Evaluasi

#### Jawaban Basic
1. S3 Standard-IA memiliki biaya penyimpanan per-gigabyte bulanan yang lebih murah dibandingkan S3 Standard, namun membebankan biaya retrieval per-gigabyte saat data diakses/dibaca dan memiliki batas minimal durasi retensi tagihan (30 hari) serta ukuran objek minimum (128 KB).
2. Throughput baseline gp3 adalah $125\text{ MiB/s}$ secara konstan untuk ukuran disk berapa pun (hingga batas tertentu), dan dapat ditingkatkan hingga $1.000\text{ MiB/s}$ secara independen tanpa perlu menambah kapasitas volume gigabyte.
3. Pada *Governance Mode*, pengguna dengan izin IAM khusus (`s3:BypassGovernanceRetention`) dapat memodifikasi atau menghapus objek/lock. Pada *Compliance Mode*, **tidak ada pengguna manapun** (termasuk AWS Root Account) yang dapat menghapus objek atau membatalkan lock sebelum periode retensi habis.
4. Karena EFS adalah sistem berkas terdistribusi multi-AZ. Setiap traversal metadata direktori memerlukan network round-trip dan konsensus sinkron antar-node penyimpanan terdistribusi di beberapa AZ, berbeda dengan EBS yang mengakses metadata secara lokal via PCIe block layer.
5. Fitur **S3 Object Versioning** wajib diaktifkan pada kedua bucket: bucket sumber (source) dan bucket tujuan (destination).

#### Jawaban Intermediate
6. Blok snapshot EBS disimpan secara pasif di S3. Saat volume baru dibuat, metadata disk telah siap namun blok fisik data baru ditarik (*lazy-loaded*) dari S3 saat pertama kali blok tersebut dibaca/ditulis, menyebabkan latensi tinggi. Mitigasinya adalah menggunakan fitur **Amazon EBS Fast Snapshot Restore (FSR)** atau melakukan inisialisasi awal manual (*pre-warming*) menggunakan utilitas `dd` atau `fio`.
7. Tanpa Bucket Key, setiap objek S3 yang di-PUT/GET memanggil API KMS (`kms:GenerateDataKey` / `kms:Decrypt`), menghasilkan biaya request KMS yang tinggi. Dengan *S3 Bucket Key*, S3 membuat kunci turunan berumur pendek di memori internal S3. Kunci perantara ini digunakan untuk mengenkripsi kumpulan objek pada prefix yang sama, mengurangi panggilan API langsung ke KMS hingga $>99\%$.
8. Ubah tipe volume dari **gp2 ke gp3** secara online menggunakan AWS Elastic Volumes API, lalu tetapkan *Provisioned IOPS* sesuai batas kebutuhan aplikasi (misal: 5.000 IOPS) tanpa harus memperbesar kapasitas drive.
9. DataSync menghitung dan memvalidasi checksum data secara end-to-end secara real-time pada setiap transfer (in-flight dan post-transfer verification). DataSync juga secara otomatis mengelola *metadata preservation* (POSIX permission, timestamp, ACLs), menjalankan multithreading paralel horizontal, serta memiliki mekanisme autorecovery koneksi terputus yang jauh lebih robust daripada `rsync`.
10. Mode *Provisioned* mengharuskan arsitek menebak dan mengalokasikan throughput tetap (MB/s) di awal dan terus membayar kapasitas tersebut terlepas dari digunakan atau tidak. Mode *Elastic* secara otomatis mengalokasikan dan menurunkan batas throughput instan mengikuti pola pembacaan/penulisan aplikasi, dan pengguna hanya ditagih berdasarkan jumlah total gigabyte data yang dibaca dan ditulis pada sistem berkas.

#### Jawaban Skenario Kasus Produksi
11. **Penyebab**: Bucket S3 memiliki **Versioning aktif**, namun *Lifecycle Rule* hanya dikonfigurasi untuk tindakan `Expiration` standar (yang hanya menaruh *Delete Marker* pada Current Version, bukan menghapus data). Akibatnya, seluruh versi non-current (*Noncurrent Versions*) dan file yang tersembunyi di balik Delete Marker tetap tersimpan dan ditagihkan secara penuh. **Solusi**: Tambahkan Lifecycle Rule khusus: `NoncurrentVersionExpiration` dan aktifkan `AbortIncompleteMultipartUpload` untuk membersihkan pecahan file unggahan yang gagal.
12. **Penyebab**: Terjadi limitasi pada level **EC2 Instance Bandwidth / EBS-Optimized Throughput Limit**, bukan pada volume EBS itu sendiri. Tipe instans EC2 yang digunakan memiliki batas throughput EBS maksimum yang lebih rendah daripada apa yang diminta database (misal: instans kecil yang hanya mendukung hingga 60 MB/s burst). **Solusi**: Lakukan *vertical scaling* pada instans EC2 ke ukuran yang mendukung dedicated EBS-optimized bandwidth yang lebih tinggi (misal: keluarga `c6i.xlarge` atau yang lebih tinggi).
13. **Penyebab**: Terjadi *Permission Mismatch* pada AWS KMS. S3 CRR mereplikasi objek dan mengenkripsi ulang data di Region B menggunakan KMS Key milik Region B. Namun:
    1. IAM Role worker di Region B belum memiliki hak akses `kms:Decrypt` terhadap Key ARN KMS Region B.
    2. Key Policy KMS di Region B belum memberikan hak izin kepada service principal aplikasi atau role worker lokal.
    **Solusi**: Perbarui Key Policy pada KMS Key di Region B untuk mengizinkan worker role mengeksekusi operasi `kms:Decrypt`, dan verifikasi parameter `KmsEncryptedObjects` pada aturan replikasi sumber.

---

### 16. Summary

Penguasaan subsistem penyimpanan AWS pada tingkat arsitektur enterprise bertumpu pada kemampuan mengkombinasikan keunggulan unik dari tiga pilar utama:
1. **Amazon S3**: Sebagai *backbone* penyimpanan data masif tak terstruktur, menyediakan durabilitas 11 9s, proteksi WORM via Object Lock, segmentasi data dingin via Lifecycle Policies terautomasi, dan replikasi multi-region terenkripsi KMS.
2. **Amazon EBS**: Sebagai fondasi I/O performa tinggi berlatensi sub-milidetik untuk beban kerja basis data transaksional, dipacu oleh arsitektur Nitro Card and Block Express Engine (gp3 / io2), yang memerlukan manajemen *queue length*, mitigasi *hydration penalty* via FSR, serta snapshot terjadwal.
3. **Amazon EFS**: Sebagai solusi filesystem POSIX terdistribusi multi-AZ yang elastis, ideal untuk aplikasi multi-node seperti Kubernetes StatefulSets yang menuntut konkurensi data bersama secara *resilient*.

Integrasi ketiga layanan ini secara disiplin, dipadukan dengan kontrol enkripsi KMS, pemantauan CloudWatch metrics yang proaktif, serta kepatuhan tata kelola biaya, menjamin infrastruktur yang aman, reliabel, patuh regulasi, dan hemat biaya pada skala produksi enterprise.